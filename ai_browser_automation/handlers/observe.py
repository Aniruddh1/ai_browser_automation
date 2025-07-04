"""ObserveHandler implementation for element detection."""

import json
import re
from typing import List, Dict, Any, Optional
from pydantic import ValidationError

from .base import BaseHandler
from ..types import ObserveResult, ObserveOptions, EncodedId, LLMMessage
from ..types.observe import ObserveElementSchema, ObserveResponseSchema, ActObserveElementSchema
from ..dom import clean_text
from ..dom.debug import draw_element_overlays
from ..core.errors import LLMResponseError
from ..llm.prompt import build_observe_system_prompt, build_observe_user_message, build_act_observe_prompt


class ObserveHandler(BaseHandler[List[ObserveResult]]):
    """
    Handler for observing and detecting elements on a page.
    
    Analyzes the DOM and identifies interactive elements based on
    user instructions or general discovery.
    """
    
    async def handle(
        self,
        page: 'AIBrowserAutomationPage',
        options: ObserveOptions
    ) -> List[ObserveResult]:
        """
        Observe elements on the page.
        
        Args:
            page: AIBrowserAutomationPage instance
            options: Observation options
            
        Returns:
            List of observed elements
        """
        # Set default instruction if not provided (matches TypeScript)
        instruction = options.instruction
        if not instruction:
            instruction = "Find elements that can be used for any future actions in the page. These may be navigation links, related pages, section/subsection links, buttons, or other interactive elements. Be comprehensive: if there are multiple elements that may be relevant for future actions, return all of them."
        
        # Log observation start
        self.logger.log({
            "category": "observation",
            "message": "starting observation",
            "level": 1,
            "auxiliary": {
                "instruction": {"value": instruction, "type": "string"}
            }
        })
        
        # Wait for DOM to settle first (matching TypeScript)
        await page._wait_for_settled_dom()
        
        # Log gathering accessibility tree
        self.logger.log({
            "category": "observation",
            "message": "Getting accessibility tree data",
            "level": 1
        })
        
        # Gather page information
        page_info = await self._gather_page_info(page, include_iframes=options.iframes or False)
        
        # Get LLM response
        try:
            # Get LLM client
            client = self.llm_provider.get_client(options.model_name)
            
            # Determine instruction for LLM
            if options.from_act and instruction:
                # For act observations, use special prompt
                supported_actions = [
                    'click', 'fill', 'type', 'press', 'hover', 'selectOption',
                    'check', 'uncheck', 'focus', 'blur', 'scrollIntoView'
                ]
                instruction = build_act_observe_prompt(
                    instruction,
                    supported_actions,
                    None  # TODO: Add variables support
                )
            else:
                instruction = options.instruction or self._get_default_instruction(options.from_act)
            
            # Create messages using structured prompt builders
            system_prompt = build_observe_system_prompt(
                self.llm_provider.stagehand.user_provided_instructions if hasattr(self.llm_provider, 'stagehand') else None
            )
            user_message = build_observe_user_message(
                instruction,
                page_info.get('simplified', '')
            )
            
            # Keep LLMMessage objects and add JSON instruction
            from ..types.llm import LLMMessage
            
            # Add JSON format instruction to system message content
            if options.return_action:
                # When returnAction is true, include method and arguments
                json_instruction = """

IMPORTANT: You must respond with a valid JSON object in this format:
{
  "elements": [
    {
      "elementId": "the ID string from the accessibility tree (e.g., '0-15'), never include square brackets",
      "description": "a description of the element and its purpose",
      "method": "the playwright method to use (e.g., 'click', 'fill', 'type', 'press', 'hover', 'scrollIntoView')",
      "arguments": ["any", "arguments", "for", "the", "method"]
    }
  ]
}

Only return the JSON object, no other text."""
            else:
                # Regular observation without actions
                json_instruction = """

IMPORTANT: You must respond with a valid JSON object in this format:
{
  "elements": [
    {
      "elementId": "the ID string from the accessibility tree (e.g., '0-15'), never include square brackets",
      "description": "a description of the element and its purpose"
    }
  ]
}

Only return the JSON object, no other text."""
            
            # Append JSON instruction to system prompt
            system_prompt_with_json = LLMMessage(
                role="system",
                content=system_prompt.content + json_instruction
            )
            
            messages = [system_prompt_with_json, user_message]
            
            # Get completion with JSON response format hint
            response = await client.create_chat_completion(
                messages=messages,
                temperature=0.1,  # Low temperature for consistent results
                max_tokens=2000,
                response_format={"type": "json_object"}  # Request JSON response format
            )
            
            # Parse response
            results = self._parse_observe_response(response, page_info, options.from_act, options.return_action)
            
            # Log found elements (matching TypeScript)
            elements_for_log = []
            for result in results:
                element_log = {
                    "selector": result.selector,
                    "description": result.description
                }
                if result.method:
                    element_log["method"] = result.method
                if result.arguments:
                    element_log["arguments"] = result.arguments
                elements_for_log.append(element_log)
            
            self.logger.log({
                "category": "observation",
                "message": "found elements",
                "level": 1,
                "auxiliary": {
                    "elements": {
                        "value": json.dumps(elements_for_log),
                        "type": "object"
                    }
                }
            })
            
            # Add iframe warnings if present (matching TypeScript)
            iframes = page_info.get('iframes', [])
            if iframes and not options.iframes:
                self.logger.log({
                    "category": "observation",
                    "message": f"Warning: found {len(iframes)} iframe(s) on the page. If you wish to interact with iframe content, please make sure you are setting iframes: true",
                    "level": 1
                })
                
                # Add iframe elements to results (matching TypeScript)
                for iframe in iframes:
                    node_id = iframe.get('nodeId')
                    if node_id:
                        # Encode with frame ID (main frame)
                        encoded_id = page.encode_with_frame_id(None, int(node_id))
                        results.append(ObserveResult(
                            selector=f"xpath=",  # Empty xpath like TypeScript
                            description="an iframe",
                            encoded_id=encoded_id,
                            method="not-supported" if options.from_act else None,
                            arguments=[] if options.from_act else None
                        ))
            
            # Draw debug overlays if enabled
            if options.draw_overlay and results:
                self._log_debug("Drawing debug overlays")
                elements_for_overlay = [
                    {
                        'encodedId': r.encoded_id,
                        'isScrollable': any(
                            elem.get('isScrollable') 
                            for elem in page_info['elements'] 
                            if elem.get('encodedId') == r.encoded_id
                        )
                    }
                    for r in results
                ]
                num_drawn = await draw_element_overlays(
                    page._page, 
                    elements_for_overlay, 
                    page_info.get('xpath_map', {})
                )
                self._log_debug(f"Drew {num_drawn} debug overlays")
            
            return results
            
        except Exception as e:
            self._log_error(f"Observation failed: {e}", error=str(e))
            raise
    
    async def _gather_page_info(self, page: 'AIBrowserAutomationPage', include_iframes: bool = False) -> Dict[str, Any]:
        """Gather information about the page."""
        self._log_debug("Gathering page information")
        
        # Import accessibility tree functions
        from ..a11y import get_accessibility_tree, get_accessibility_tree_with_frames
        
        # Wait for DOM to settle first (matching TypeScript)
        await page._wait_for_settled_dom()
        
        try:
            # Get accessibility tree with XPath mappings
            if include_iframes:
                self._log_debug("Getting accessibility tree with frames")
                tree_result = await get_accessibility_tree_with_frames(page)
                # getAccessibilityTreeWithFrames returns different structure
                return {
                    "url": page.url,
                    "title": await page.title(),
                    "simplified": tree_result.get("combinedTree", ""),
                    "xpath_map": tree_result.get("combinedXpathMap", {}),
                    "url_map": tree_result.get("combinedUrlMap", {}),
                    "iframes": [],  # Already included in combined tree
                    "elements": [],  # Not used when iframes=True
                    "text": ""  # Not used when iframes=True
                }
            else:
                self._log_debug("Getting accessibility tree with XPath mappings")
                tree_result = await get_accessibility_tree(page)
            
            # Extract components from tree result (matching TypeScript)
            simplified_tree = tree_result["tree"]
            xpath_map = tree_result.get("xpathMap", {})  # Note: camelCase from TypeScript
            id_to_url = tree_result.get("idToUrl", {})   # Note: camelCase from TypeScript
            iframes = tree_result.get("iframes", [])
            
            # Flatten the tree for processing (matching TypeScript)
            flattened_elements = []
            
            def flatten_tree(nodes: List[Dict[str, Any]]) -> None:
                for node in nodes:
                    # Add the node
                    flattened_elements.append(node)
                    # Recurse into children
                    if "children" in node:
                        flatten_tree(node["children"])
            
            flatten_tree(simplified_tree)
            
            # Get page text for context
            page_text = await page._page.evaluate("() => document.body ? document.body.innerText : ''")
            
            self._log_debug(f"Got {len(flattened_elements)} nodes from accessibility tree")
            
            return {
                "url": page.url,
                "title": await page.title(),
                "elements": flattened_elements,
                "xpath_map": xpath_map,
                "url_map": id_to_url,
                "iframes": iframes,
                "text": clean_text(page_text)[:1000] if page_text else "",
                "simplified": tree_result.get("simplified", "")
            }
        except Exception as e:
            self._log_error(f"Error getting accessibility tree: {e}", error=str(e))
            # Re-raise the error - no fallback (matching TypeScript)
            raise
    
    def _get_default_instruction(self, from_act: bool = False) -> str:
        """Get default instruction when none provided - matches TypeScript."""
        if from_act:
            return ""
        return """Find elements that can be used for any future actions in the page. These may be navigation links, related pages, section/subsection links, buttons, or other interactive elements. Be comprehensive: if there are multiple elements that may be relevant for future actions, return all of them."""
    
    
    def _parse_observe_response(
        self,
        response: Any,
        page_info: Dict[str, Any],
        from_act: bool = False,
        return_action: bool = False
    ) -> List[ObserveResult]:
        """Parse LLM response into ObserveResult objects."""
        try:
            # Extract content from response
            if hasattr(response, 'choices') and response.choices:
                content = response.choices[0].message.content
            else:
                self._log_error("Invalid response structure")
                return []
            
            # Try to parse and validate using schemas
            elements_data = []
            
            try:
                # Always expect the same format: {"elements": [...]}
                try:
                    # Try to parse as JSON object with "elements" key
                    parsed_json = json.loads(content)
                    if isinstance(parsed_json, dict) and "elements" in parsed_json:
                        raw_data = parsed_json["elements"]
                    else:
                        # Fallback to array parsing
                        json_match = re.search(r'\[.*\]', content, re.DOTALL)
                        if json_match:
                            raw_data = json.loads(json_match.group(0))
                        else:
                            raw_data = json.loads(content)
                except json.JSONDecodeError:
                    # If JSON parsing fails, try to extract array
                    json_match = re.search(r'\[.*\]', content, re.DOTALL)
                    if json_match:
                        raw_data = json.loads(json_match.group(0))
                    else:
                        self._log_error(f"Failed to parse JSON from content: {content[:200]}")
                        return []
                    
                # Ensure raw_data is a list
                if not isinstance(raw_data, list):
                    self._log_error(f"Expected list, got {type(raw_data).__name__}")
                    return []
                
                # Validate each element with appropriate schema
                for elem in raw_data:
                    try:
                        # Ensure elem is a dictionary
                        if not isinstance(elem, dict):
                            # Handle case where LLM returns just element IDs
                            if isinstance(elem, (str, int)):
                                elem_id = str(elem).strip('[]')
                                elem_dict = {
                                    "elementId": elem_id,
                                    "description": f"Element {elem_id}"
                                }
                                if return_action:
                                    elem_dict["method"] = "click"
                                    elem_dict["arguments"] = []
                                validated = ObserveElementSchema(**elem_dict) if not return_action else ActObserveElementSchema(**elem_dict)
                                elements_data.append(validated.dict())
                            else:
                                self._log_debug(f"Skipping non-dict element: {type(elem).__name__}")
                            continue
                        
                        # Use appropriate schema based on return_action
                        if return_action:
                            validated = ActObserveElementSchema(**elem)
                        else:
                            validated = ObserveElementSchema(**elem)
                        elements_data.append(validated.dict())
                    except ValidationError as e:
                        self._log_debug(f"Skipping invalid element: {e}")
                        continue
                            
            except (json.JSONDecodeError, ValidationError) as e:
                self._log_error(f"Failed to parse/validate response: {e}")
                # Try fallback regex parsing
                if from_act:
                    json_match = re.search(r'\{[^{}]*"elementId"[^{}]*\}', content, re.DOTALL)
                else:
                    json_match = re.search(r'\[[^\[\]]*\]', content, re.DOTALL)
                
                if json_match:
                    try:
                        raw_data = json.loads(json_match.group(0))
                        if isinstance(raw_data, list):
                            elements_data = raw_data
                        else:
                            elements_data = [raw_data]
                    except:
                        return []
            
            # Convert to ObserveResult objects
            results = []
            xpath_map = page_info.get('xpath_map', {})  # This is set correctly in _gather_page_info
            
            for elem_data in elements_data:
                # Ensure elem_data is a dictionary
                if not isinstance(elem_data, dict):
                    self._log_debug(f"Skipping non-dict element data: {type(elem_data).__name__}")
                    continue
                # Use elementId from LLM response
                encoded_id = elem_data.get('elementId', elem_data.get('encodedId', ''))
                
                # Get XPath from mapping - matching TypeScript
                xpath = xpath_map.get(encoded_id, '')
                
                # If not found, try with frame prefix (TypeScript uses "0-" prefix for main frame)
                if not xpath and not encoded_id.startswith('0-'):
                    prefixed_id = f"0-{encoded_id}"
                    xpath = xpath_map.get(prefixed_id, '')
                
                # Skip text nodes - they cannot be interacted with
                if xpath and "/text()[" in xpath:
                    self._log_debug(
                        f"Skipping text node selector: {xpath}",
                        element_id=encoded_id
                    )
                    # Try to find the parent element instead
                    # Remove the /text()[n] suffix to get parent element xpath
                    parent_xpath = xpath.rsplit('/text()[', 1)[0]
                    # Find the parent element's ID in xpath_map
                    parent_id = None
                    for id, xp in xpath_map.items():
                        if xp == parent_xpath:
                            parent_id = id
                            xpath = parent_xpath
                            encoded_id = parent_id
                            self._log_debug(
                                f"Using parent element instead: {parent_xpath}",
                                element_id=parent_id
                            )
                            break
                    
                    if not parent_id:
                        # Can't find parent, skip this element
                        self._log_debug(
                            f"Cannot find parent element for text node, skipping",
                            element_id=encoded_id
                        )
                        continue
                
                # Always use xpath= prefix, even if xpath is empty (matching TypeScript)
                selector = f"xpath={xpath}"
                
                if not xpath:
                    self._log_debug(
                        f"Empty xpath returned for element: {encoded_id}",
                        element_id=encoded_id
                    )
                
                # Create result matching TypeScript interface
                result = ObserveResult(
                    selector=selector,  # No fallback to "unknown" - matching TypeScript
                    description=elem_data.get('description', 'No description'),
                    backend_node_id=None,  # Could be populated if needed
                    method=elem_data.get('method'),  # Add method for act observations
                    arguments=elem_data.get('arguments', [])  # Add arguments for act observations
                )
                results.append(result)
            
            return results
            
        except Exception as e:
            self._log_error(f"Failed to parse observe response: {e}")
            # Return empty list on parse error
            return []
    
