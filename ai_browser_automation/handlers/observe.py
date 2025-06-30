"""ObserveHandler implementation for element detection."""

import json
import re
from typing import List, Dict, Any, Optional
from pydantic import ValidationError

from .base import BaseHandler
from ..types import ObserveResult, ObserveOptions, EncodedId, LLMMessage
from ..types.observe import ObserveElementSchema, ObserveResponseSchema, ActObserveResponseSchema
from ..dom import get_clickable_elements, get_input_elements, get_page_text, clean_text
from ..dom.scrollable import mark_scrollable_in_tree
from ..dom.debug import draw_element_overlays
from ..core.errors import LLMResponseError


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
        self._log_info(
            "Starting observation",
            instruction=options.instruction,
            only_visible=options.only_visible,
            draw_overlay=options.draw_overlay,
            iframes=options.iframes,
        )
        
        # Gather page information
        page_info = await self._gather_page_info(page)
        
        # Build prompt for LLM
        prompt = self._build_observe_prompt(page_info, options)
        
        # Get LLM response
        try:
            # Get LLM client
            client = self.llm_provider.get_client(options.model_name)
            
            # Create messages
            messages = [
                LLMMessage(
                    role="system",
                    content="You are a web automation assistant that identifies interactive elements on web pages."
                ),
                LLMMessage(
                    role="user",
                    content=prompt
                )
            ]
            
            # Get completion
            response = await client.create_chat_completion(
                messages=messages,
                temperature=0.1,  # Low temperature for consistent results
                max_tokens=2000
            )
            
            # Parse response
            results = self._parse_observe_response(response, page_info, options.from_act)
            
            self._log_info(
                "Observation completed",
                found_count=len(results)
            )
            
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
    
    async def _gather_page_info(self, page: 'AIBrowserAutomationPage') -> Dict[str, Any]:
        """Gather information about the page."""
        self._log_debug("Gathering page information")
        
        # Import accessibility tree builder
        from ..a11y import get_accessibility_tree
        
        try:
            # Get accessibility tree with XPath mappings
            self._log_debug("Getting accessibility tree with XPath mappings")
            simplified_tree, xpath_map, url_map = await get_accessibility_tree(page)
            
            # Mark scrollable elements
            self._log_debug("Detecting scrollable elements")
            simplified_tree = await mark_scrollable_in_tree(simplified_tree, xpath_map, page._page)
            
            # Get page text for context
            page_text = await page._page.evaluate("() => document.body ? document.body.innerText : ''")
            
            self._log_debug(f"Got {len(simplified_tree)} nodes from accessibility tree")
            
            return {
                "url": page.url,
                "title": await page.title(),
                "elements": simplified_tree,
                "xpath_map": xpath_map,
                "url_map": url_map,
                "text": clean_text(page_text)[:1000] if page_text else ""
            }
        except Exception as e:
            self._log_error(f"Error getting accessibility tree, falling back to DOM scraping: {e}", error=str(e))
            # Fallback to DOM scraping if CDP fails
            
            # Get elements in parallel
            clickable_task = get_clickable_elements(page._page)
            input_task = get_input_elements(page._page)
            text_task = get_page_text(page._page)
            
            # Wait for all
            clickable_elements = await clickable_task
            input_elements = await input_task
            page_text = await text_task
            
            # Combine elements and build xpath_map
            all_elements = []
            xpath_map = {}  # Create xpath_map for DOM fallback
            
            # Add clickable elements
            for idx, elem in enumerate(clickable_elements):
                encoded_id = f"0-{idx + 1}"
                all_elements.append({
                    "type": "clickable",
                    "element": elem,
                    "encodedId": encoded_id
                })
                # Build XPath from element attributes
                # The selector from DOM scraping is CSS, not XPath
                tag_name = elem['tagName'].lower()
                
                # Build XPath with attributes for uniqueness
                if elem.get('id'):
                    xpath_map[encoded_id] = f"//{tag_name}[@id='{elem['id']}']"
                elif elem.get('className'):
                    # Use first class for XPath
                    classes = elem['className'].split()
                    if classes:
                        xpath_map[encoded_id] = f"//{tag_name}[contains(@class, '{classes[0]}')]"
                    else:
                        xpath_map[encoded_id] = f"//{tag_name}"
                elif elem.get('href'):
                    xpath_map[encoded_id] = f"//{tag_name}[@href='{elem['href']}']"
                elif elem.get('text'):
                    # Use text content for uniqueness
                    text = elem['text'][:50]  # Limit text length
                    xpath_map[encoded_id] = f"//{tag_name}[contains(text(), '{text}')]"
                else:
                    # Fallback to simple tag name
                    xpath_map[encoded_id] = f"//{tag_name}"
            
            # Add input elements
            for idx, elem in enumerate(input_elements):
                encoded_id = f"0-{len(clickable_elements) + idx + 1}"
                all_elements.append({
                    "type": "input",
                    "element": elem,
                    "encodedId": encoded_id
                })
                # Build XPath from element attributes
                # The selector from DOM scraping is CSS, not XPath
                tag_name = elem['tagName'].lower()
                
                # Build XPath with attributes for uniqueness
                if elem.get('id'):
                    xpath_map[encoded_id] = f"//{tag_name}[@id='{elem['id']}']"
                elif elem.get('name'):
                    xpath_map[encoded_id] = f"//{tag_name}[@name='{elem['name']}']"
                elif elem.get('placeholder'):
                    xpath_map[encoded_id] = f"//{tag_name}[@placeholder='{elem['placeholder']}']"
                elif elem.get('type'):
                    xpath_map[encoded_id] = f"//{tag_name}[@type='{elem['type']}']"
                elif elem.get('className'):
                    # Use first class for XPath
                    classes = elem['className'].split()
                    if classes:
                        xpath_map[encoded_id] = f"//{tag_name}[contains(@class, '{classes[0]}')]"
                    else:
                        xpath_map[encoded_id] = f"//{tag_name}"
                else:
                    # Fallback to simple tag name
                    xpath_map[encoded_id] = f"//{tag_name}"
            
            return {
                "url": page.url,
                "title": await page.title(),
                "elements": all_elements,
                "xpath_map": xpath_map,  # Include xpath_map in DOM fallback
                "text": clean_text(page_text)[:1000]  # First 1000 chars
            }
    
    def _build_observe_prompt(
        self,
        page_info: Dict[str, Any],
        options: ObserveOptions
    ) -> str:
        """Build prompt for element observation."""
        # Check if this is an act-specific observation
        if options.from_act and options.instruction:
            return self._build_act_observe_prompt(page_info, options)
        
        # Base prompt
        prompt = f"""Analyze the following web page and identify interactive elements.

Page URL: {page_info['url']}
Page Title: {page_info['title']}

Page Content Preview:
{page_info['text']}

Interactive Elements Found:
"""
        
        # Add elements
        if 'xpath_map' in page_info:
            # Using accessibility tree nodes
            for node in page_info['elements'][:50]:  # Limit to 50 elements
                node_id = node.get('nodeId')
                if not node_id:
                    continue
                    
                encoded_id = f"0-{node_id}"
                role = node.get('role', '')
                name = node.get('name', '')
                tag_name = node.get('tagName', '').upper()
                
                # Build description based on role and tag
                if role in ['link', 'button'] or tag_name in ['A', 'BUTTON']:
                    desc = f"- [{encoded_id}] {tag_name or role.upper()}"
                    if name:
                        desc += f": \"{name[:50]}\""
                    if node.get('isScrollable'):
                        desc += " [SCROLLABLE]"
                    prompt += desc + "\n"
                    
                elif role in ['textbox', 'searchbox', 'combobox'] or tag_name in ['INPUT', 'TEXTAREA']:
                    desc = f"- [{encoded_id}] {tag_name or 'INPUT'}"
                    if name:
                        desc += f": \"{name}\""
                    prompt += desc + "\n"
                elif node.get('isScrollable'):
                    # Include scrollable containers
                    desc = f"- [{encoded_id}] {tag_name or 'DIV'} [SCROLLABLE CONTAINER]"
                    if name:
                        desc += f": \"{name[:50]}\""
                    prompt += desc + "\n"
        else:
            # Fallback: Using DOM elements
            for elem_info in page_info['elements'][:50]:  # Limit to 50 elements
                elem = elem_info['element']
                elem_type = elem_info['type']
                
                if elem_type == "clickable":
                    desc = f"- [{elem_info['encodedId']}] {elem['tagName'].upper()}"
                    if elem['text']:
                        desc += f": \"{elem['text'][:50]}\""
                    if elem['href']:
                        desc += f" (link to {elem['href']})"
                    prompt += desc + "\n"
                    
                elif elem_type == "input":
                    desc = f"- [{elem_info['encodedId']}] INPUT"
                    if elem['type'] != 'text':
                        desc += f" type=\"{elem['type']}\""
                    if elem['placeholder']:
                        desc += f": \"{elem['placeholder']}\""
                    elif elem['name']:
                        desc += f": name=\"{elem['name']}\""
                    prompt += desc + "\n"
        
        # Add instruction
        if options.instruction:
            prompt += f"\n\nUser Instruction: {options.instruction}\n"
        else:
            prompt += "\n\nIdentify the most important interactive elements on this page.\n"
        
        # Add response format
        prompt += """
Return a JSON array of elements in this format:
[
  {
    "elementId": "the encoded ID from above (e.g., 0-15)",
    "description": "Human-readable description",
    "action": "suggested action (click, fill, etc.)"
  }
]

Only include elements that match the user's instruction (if provided) or the most important elements if no instruction is given.
"""
        
        return prompt
    
    def _build_act_observe_prompt(
        self,
        page_info: Dict[str, Any],
        options: ObserveOptions
    ) -> str:
        """Build prompt specifically for act observations."""
        import re
        
        # Supported Playwright methods
        supported_methods = [
            'click', 'fill', 'type', 'press', 'hover', 'selectOption',
            'check', 'uncheck', 'focus', 'blur', 'scrollIntoView'
        ]
        
        prompt = f"""Find the most relevant element to perform an action on given the following action: {options.instruction}

Page URL: {page_info['url']}
Page Title: {page_info['title']}

Interactive Elements Found:
"""
        
        # Add elements
        if 'xpath_map' in page_info:
            # Using accessibility tree nodes
            for node in page_info['elements'][:50]:
                node_id = node.get('nodeId')
                if not node_id:
                    continue
                    
                encoded_id = f"0-{node_id}"
                role = node.get('role', '')
                name = node.get('name', '')
                tag_name = node.get('tagName', '').upper()
                
                # Filter for actionable elements
                if role in ['link', 'button', 'textbox', 'searchbox', 'combobox'] or tag_name in ['A', 'BUTTON', 'INPUT', 'TEXTAREA', 'SELECT']:
                    desc = f"- [{encoded_id}] {tag_name or role.upper()}"
                    if name:
                        desc += f": \"{name[:50]}\""
                    prompt += desc + "\n"
        else:
            # Fallback: Using DOM elements
            for elem_info in page_info['elements'][:50]:
                elem = elem_info['element']
                elem_type = elem_info['type']
                
                if elem_type == "clickable":
                    desc = f"- [{elem_info['encodedId']}] {elem['tagName'].upper()}"
                    if elem['text']:
                        desc += f": \"{elem['text'][:50]}\""
                    if elem['href']:
                        desc += f" (link to {elem['href']})"
                    prompt += desc + "\n"
                    
                elif elem_type == "input":
                    desc = f"- [{elem_info['encodedId']}] INPUT"
                    if elem['type'] != 'text':
                        desc += f" type=\"{elem['type']}\""
                    if elem['placeholder']:
                        desc += f": \"{elem['placeholder']}\""
                    elif elem['name']:
                        desc += f": name=\"{elem['name']}\""
                    prompt += desc + "\n"
        
        prompt += f"""
Provide a Playwright method and arguments for this element. The supported methods are: {', '.join(supported_methods)}

Important:
- For fill/type actions, extract the text to input from the instruction
- For click actions, use the 'click' method with no arguments
- For press actions, extract the key to press (e.g., 'Enter', 'Tab', 'Space')

Examples:
- Instruction: "Fill the search box with 'hello world'" → method: "fill", arguments: ["hello world"]
- Instruction: "Click the submit button" → method: "click", arguments: []
- Instruction: "Press enter" → method: "press", arguments: ["Enter"]

Return ONLY ONE element that best matches the action. Return a JSON object in this format:
{{
  "elementId": "the encoded ID from above (e.g., 0-15)",
  "description": "Human-readable description",
  "method": "playwright method to use",
  "arguments": ["array", "of", "arguments"]
}}
"""
        
        return prompt
    
    def _parse_observe_response(
        self,
        response: Any,
        page_info: Dict[str, Any],
        from_act: bool = False
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
                if from_act:
                    # For act observations, expect a single object
                    json_match = re.search(r'\{.*\}', content, re.DOTALL)
                    if json_match:
                        raw_data = json.loads(json_match.group(0))
                    else:
                        raw_data = json.loads(content)
                    
                    # Validate with schema
                    validated = ActObserveResponseSchema(**raw_data)
                    elements_data = [validated.dict()]
                else:
                    # For regular observations, expect an array
                    json_match = re.search(r'\[.*\]', content, re.DOTALL)
                    if json_match:
                        raw_data = json.loads(json_match.group(0))
                    else:
                        raw_data = json.loads(content)
                    
                    # Validate each element with schema
                    for elem in raw_data:
                        try:
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
            xpath_map = page_info.get('xpath_map', {})
            
            for elem_data in elements_data:
                # Use elementId from LLM response
                encoded_id = elem_data.get('elementId', elem_data.get('encodedId', ''))
                
                # Find element info first
                element_info = None
                for info in page_info['elements']:
                    if isinstance(info, dict):
                        if info.get('encodedId') == encoded_id:
                            element_info = info
                            break
                        elif info.get('nodeId') and f"0-{info['nodeId']}" == encoded_id:
                            element_info = info
                            break
                
                # Build selector - always use XPath from mapping
                # Following TypeScript pattern: always return xpath= prefix
                xpath = xpath_map.get(encoded_id, '')
                
                if not xpath and element_info:
                    # Try to build a fallback XPath if not in map
                    if 'element' in element_info:
                        # Using DOM elements - get selector
                        elem = element_info['element']
                        elem_selector = elem.get('selector', '')
                        if elem_selector.startswith('xpath='):
                            xpath = elem_selector[6:]  # Remove xpath= prefix
                        else:
                            # Build basic XPath from tag
                            xpath = f"//{elem['tagName'].lower()}"
                    else:
                        # Using accessibility node - build basic XPath
                        tag_name = element_info.get('tagName', 'div')
                        xpath = f"//{tag_name.lower()}"
                
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
    
