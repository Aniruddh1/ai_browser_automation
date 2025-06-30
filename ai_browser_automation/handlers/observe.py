"""ObserveHandler implementation for element detection."""

import json
import re
from typing import List, Dict, Any, Optional

from .base import BaseHandler
from ..types import ObserveResult, ObserveOptions, EncodedId, LLMMessage
from ..dom import get_clickable_elements, get_input_elements, get_page_text, clean_text
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
            include_hidden=options.include_hidden,
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
            
            # Combine elements
            all_elements = []
            
            # Add clickable elements
            for idx, elem in enumerate(clickable_elements):
                all_elements.append({
                    "type": "clickable",
                    "element": elem,
                    "encodedId": f"0-{idx + 1}"  # Simple encoding for now
                })
            
            # Add input elements
            for idx, elem in enumerate(input_elements):
                all_elements.append({
                    "type": "input",
                    "element": elem,
                    "encodedId": f"0-{len(clickable_elements) + idx + 1}"
                })
            
            return {
                "url": page.url,
                "title": await page.title(),
                "elements": all_elements,
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
                    prompt += desc + "\n"
                    
                elif role in ['textbox', 'searchbox', 'combobox'] or tag_name in ['INPUT', 'TEXTAREA']:
                    desc = f"- [{encoded_id}] {tag_name or 'INPUT'}"
                    if name:
                        desc += f": \"{name}\""
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
            
            # Try to parse as JSON
            # Handle different response formats based on from_act flag
            if from_act:
                # For act observations, expect a single object
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    elem_data = json.loads(json_match.group(0))
                else:
                    try:
                        elem_data = json.loads(content)
                    except json.JSONDecodeError:
                        self._log_error(f"Failed to parse JSON from response: {content[:200]}")
                        return []
                
                # Wrap single element in a list for consistent processing
                elements_data = [elem_data] if isinstance(elem_data, dict) else []
            else:
                # For regular observations, expect an array
                json_match = re.search(r'\[.*\]', content, re.DOTALL)
                if json_match:
                    elements_data = json.loads(json_match.group(0))
                else:
                    # Fallback: try to parse the whole content
                    try:
                        elements_data = json.loads(content)
                    except json.JSONDecodeError:
                        self._log_error(f"Failed to parse JSON from response: {content[:200]}")
                        return []
                
                # Ensure we have a list
                if not isinstance(elements_data, list):
                    self._log_error(f"Expected list of elements, got {type(elements_data)}")
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
                selector = None
                if encoded_id in xpath_map:
                    # Add xpath= prefix to match TypeScript
                    selector = f"xpath={xpath_map[encoded_id]}"
                elif element_info:
                    if 'element' in element_info:
                        # Using DOM elements
                        elem = element_info['element']
                        selector = elem.get('selector', f"{elem['tagName']}")
                    else:
                        # Using accessibility node - build basic XPath
                        tag_name = element_info.get('tagName', 'div')
                        selector = f"xpath=//{tag_name}"
                else:
                    # No selector found
                    selector = "unknown"
                
                # Create result
                # Make sure encoded_id is a string
                encoded_id_str = str(encoded_id or '0-0')
                
                # Extract attributes
                attributes = None
                if element_info:
                    if 'element' in element_info:
                        # DOM element
                        attributes = self._extract_string_attributes(element_info['element'])
                    else:
                        # Accessibility node - extract basic attributes
                        attributes = {
                            'role': str(element_info.get('role', '')),
                            'name': str(element_info.get('name', '')),
                            'tagName': str(element_info.get('tagName', ''))
                        }
                        # Remove empty values
                        attributes = {k: v for k, v in attributes.items() if v}
                
                result = ObserveResult(
                    selector=selector or "unknown",
                    description=elem_data.get('description', 'No description'),
                    action=elem_data.get('action'),
                    encoded_id=encoded_id_str,
                    attributes=attributes,
                    method=elem_data.get('method'),  # Add method for act observations
                    arguments=elem_data.get('arguments', [])  # Add arguments for act observations
                )
                results.append(result)
            
            return results
            
        except Exception as e:
            self._log_error(f"Failed to parse observe response: {e}")
            # Return empty list on parse error
            return []
    
    def _extract_string_attributes(self, element: Dict[str, Any]) -> Dict[str, str]:
        """Extract only string attributes from element."""
        string_attrs = {}
        for key, value in element.items():
            if isinstance(value, str):
                string_attrs[key] = value
            elif isinstance(value, (int, float, bool)):
                string_attrs[key] = str(value)
            # Skip complex types like dicts and lists
        return string_attrs