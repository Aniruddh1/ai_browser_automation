"""XPath generation utilities for robust element identification."""

from typing import List, Dict, Any, Optional, Tuple
import re
import itertools


def escape_xpath_string(value: str) -> str:
    """
    Escape a string for use in XPath expressions.
    Handles both single and double quotes properly.
    """
    if '"' in value and "'" in value:
        # Contains both quotes - need to use concat()
        parts = []
        current = ""
        for char in value:
            if char == '"':
                if current:
                    parts.append(f'"{current}"')
                    current = ""
                parts.append("'\"'")
            elif char == "'":
                if current:
                    parts.append(f'"{current}"')
                    current = ""
                parts.append('"' + "'" + '"')
            else:
                current += char
        if current:
            parts.append(f'"{current}"')
        return f"concat({', '.join(parts)})"
    elif '"' in value:
        # Contains only double quotes - use single quotes
        return f"'{value}'"
    else:
        # No double quotes - use double quotes
        return f'"{value}"'


def generate_xpath_strategies(element: Dict[str, Any], tag_name: str) -> List[str]:
    """
    Generate multiple XPath strategies for an element.
    
    Args:
        element: Element information dictionary
        tag_name: The element's tag name
        
    Returns:
        List of XPath expressions ordered by specificity
    """
    xpaths = []
    
    # Strategy 1: ID-based XPath (most specific)
    elem_id = element.get('id')
    if elem_id and elem_id.strip():
        xpaths.append(f'//*[@id={escape_xpath_string(elem_id)}]')
    
    # Strategy 2: Complex XPath with multiple attributes
    conditions = []
    
    # Add tag name as base
    base_xpath = f'//{tag_name.lower()}'
    
    # Add various attributes
    if elem_id and elem_id.strip():
        conditions.append(f'@id={escape_xpath_string(elem_id)}')
    
    elem_class = element.get('class', '').strip()
    if elem_class:
        # For classes, we need to handle multiple classes
        classes = elem_class.split()
        if len(classes) == 1:
            conditions.append(f'@class={escape_xpath_string(elem_class)}')
        else:
            # Use contains for multiple classes
            for cls in classes[:2]:  # Limit to first 2 classes
                if cls:
                    conditions.append(f'contains(@class, {escape_xpath_string(cls)})')
    
    # Add data attributes
    for attr_name in ['data-testid', 'data-test', 'data-qa', 'data-id', 'data-cy']:
        attr_value = element.get(attr_name)
        if attr_value:
            conditions.append(f'@{attr_name}={escape_xpath_string(attr_value)}')
    
    # Add name attribute
    name = element.get('name')
    if name:
        conditions.append(f'@name={escape_xpath_string(name)}')
    
    # Add role attribute
    role = element.get('role')
    if role:
        conditions.append(f'@role={escape_xpath_string(role)}')
    
    # Add text content for buttons and links
    if tag_name.lower() in ['button', 'a'] and element.get('text'):
        text = element['text'].strip()
        if text and len(text) < 50:  # Only for reasonable length text
            conditions.append(f'normalize-space(text())={escape_xpath_string(text)}')
    
    # Build complex XPath with conditions
    if conditions:
        # Try with all conditions
        if len(conditions) > 1:
            xpaths.append(f'{base_xpath}[{" and ".join(conditions)}]')
        
        # Try with subset of conditions
        if len(conditions) > 2:
            # Use first two most specific conditions
            xpaths.append(f'{base_xpath}[{" and ".join(conditions[:2])}]')
        
        # Try with single condition
        xpaths.append(f'{base_xpath}[{conditions[0]}]')
    
    # Strategy 3: Standard positional XPath (fallback)
    # This would need to be calculated based on element position
    # For now, we'll add a placeholder
    
    return xpaths


async def validate_xpath_uniqueness(page: Any, xpath: str) -> Tuple[bool, int]:
    """
    Validate that an XPath expression selects exactly one element.
    
    Args:
        page: Playwright page instance
        xpath: XPath expression to validate
        
    Returns:
        Tuple of (is_unique, count)
    """
    try:
        count = await page.evaluate(f'''
            (function() {{
                try {{
                    const result = document.evaluate(
                        {repr(xpath)}, 
                        document, 
                        null, 
                        XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, 
                        null
                    );
                    return result.snapshotLength;
                }} catch (e) {{
                    return -1;  // Invalid XPath
                }}
            }})()
        ''')
        
        return count == 1, count
    except Exception:
        return False, -1


async def find_unique_xpath(page: Any, element: Dict[str, Any], tag_name: str) -> Optional[str]:
    """
    Find the most specific unique XPath for an element.
    
    Args:
        page: Playwright page instance
        element: Element information
        tag_name: Element's tag name
        
    Returns:
        The most specific unique XPath, or None if none found
    """
    xpaths = generate_xpath_strategies(element, tag_name)
    
    for xpath in xpaths:
        is_unique, count = await validate_xpath_uniqueness(page, xpath)
        if is_unique:
            return xpath
    
    return None


def build_positional_xpath(element_path: List[Dict[str, str]]) -> str:
    """
    Build a positional XPath from an element path.
    
    Args:
        element_path: List of dictionaries with 'tagName' and 'index'
        
    Returns:
        Positional XPath string
    """
    if not element_path:
        return ""
    
    xpath_parts = []
    for node in element_path:
        tag = node.get('tagName', 'div').lower()
        index = node.get('index', 1)
        xpath_parts.append(f'{tag}[{index}]')
    
    return '/' + '/'.join(xpath_parts)


XPATH_GENERATION_SCRIPT = """
(function(element) {
    function getElementPath(elem) {
        const path = [];
        let current = elem;
        
        while (current && current !== document.documentElement) {
            let index = 1;
            let sibling = current.previousSibling;
            
            while (sibling) {
                if (sibling.nodeType === 1 && 
                    sibling.tagName === current.tagName) {
                    index++;
                }
                sibling = sibling.previousSibling;
            }
            
            path.unshift({
                tagName: current.tagName.toLowerCase(),
                index: index
            });
            
            current = current.parentElement;
        }
        
        // Add html element
        path.unshift({ tagName: 'html', index: 1 });
        
        return path;
    }
    
    function getElementAttributes(elem) {
        const attrs = {};
        for (const attr of elem.attributes) {
            attrs[attr.name] = attr.value;
        }
        return attrs;
    }
    
    // Get element info
    const info = {
        tagName: element.tagName.toLowerCase(),
        id: element.id || '',
        class: element.className || '',
        name: element.name || '',
        role: element.getAttribute('role') || '',
        text: element.textContent ? element.textContent.trim().substring(0, 100) : '',
        path: getElementPath(element),
        attributes: getElementAttributes(element)
    };
    
    // Add data attributes
    for (const attr of element.attributes) {
        if (attr.name.startsWith('data-')) {
            info[attr.name] = attr.value;
        }
    }
    
    return info;
})(arguments[0]);
"""


def get_combinations(attributes: List[Dict[str, str]], size: int) -> List[List[Dict[str, str]]]:
    """
    Generate all possible combinations of a given array of attributes.
    
    Args:
        attributes: Array of attributes with 'attr' and 'value' keys
        size: The size of each combination
        
    Returns:
        List of attribute combinations
    """
    return list(itertools.combinations(attributes, size))


async def is_xpath_first_result_element(page: Any, xpath: str, target_element: Any = None) -> bool:
    """
    Check if the generated XPath uniquely identifies the target element.
    
    Args:
        page: Playwright page instance
        xpath: The XPath string to test
        target_element: The target DOM element (optional)
        
    Returns:
        True if XPath selects exactly one element (and it's the target if provided)
    """
    try:
        # Get all elements matching the XPath
        elements = await page.locator(f'xpath={xpath}').all()
        
        # Check if we have exactly one element
        if len(elements) != 1:
            return False
            
        # If target element provided, verify it's the same
        if target_element:
            # Compare using element handle evaluation
            is_same = await page.evaluate(
                '(el1, el2) => el1 === el2',
                await elements[0].element_handle(),
                target_element
            )
            return is_same
            
        return True
    except Exception as e:
        # If there's an error evaluating the XPath, consider it not unique
        print(f"Invalid XPath expression: {xpath}, error: {e}")
        return False


async def generate_xpaths_for_element(element: Any, page: Any = None) -> List[str]:
    """
    Generate both a complex XPath and a standard XPath for a given DOM element.
    Matches TypeScript's generateXPathsForElement function.
    
    Args:
        element: The target DOM element (Playwright ElementHandle)
        page: Playwright page instance (optional, for validation)
        
    Returns:
        List of XPaths ordered from most accurate to most cacheable
    """
    if not element:
        return []
    
    # Get element info using our script
    element_info = await element.evaluate(XPATH_GENERATION_SCRIPT)
    
    # Generate the three types of XPaths
    complex_xpath = await generate_complex_xpath(element, element_info, page)
    standard_xpath = await generate_standard_xpath(element)
    id_based_xpath = await generate_id_based_xpath(element, element_info)
    
    # Return in order from most accurate to most cacheable
    xpaths = [standard_xpath]
    if id_based_xpath:
        xpaths.append(id_based_xpath)
    xpaths.append(complex_xpath)
    
    return xpaths


async def generate_complex_xpath(element: Any, element_info: Dict[str, Any], page: Any = None) -> str:
    """
    Generate a complex XPath using attribute combinations.
    Matches TypeScript's generateComplexXPath function.
    """
    tag_name = element_info['tagName'].lower()
    
    # List of attributes to consider for uniqueness (matching TypeScript)
    attribute_priority = [
        "data-qa",
        "data-component",
        "data-role",
        "role",
        "aria-role",
        "type",
        "name",
        "aria-label",
        "placeholder",
        "title",
        "alt",
    ]
    
    # Collect attributes present on the element
    attributes = []
    element_attrs = element_info.get('attributes', {})
    
    for attr in attribute_priority:
        value = element_attrs.get(attr)
        if value:
            attributes.append({'attr': attr, 'value': value})
    
    # Attempt to find a combination of attributes that uniquely identifies the element
    unique_selector = ""
    
    if page:  # Only validate if page is provided
        for i in range(1, len(attributes) + 1):
            combinations = get_combinations(attributes, i)
            for combo in combinations:
                conditions = []
                for attr_dict in combo:
                    conditions.append(f'@{attr_dict["attr"]}={escape_xpath_string(attr_dict["value"])}')
                
                xpath = f'//{tag_name}[{" and ".join(conditions)}]'
                
                if await is_xpath_first_result_element(page, xpath, element):
                    unique_selector = xpath
                    break
            
            if unique_selector:
                break
    
    if unique_selector:
        return unique_selector.replace('//', '')
    
    # Fallback to positional selector
    return await generate_standard_xpath(element)


async def generate_standard_xpath(element: Any) -> str:
    """
    Generate a standard positional XPath for a given DOM element.
    Matches TypeScript's generateStandardXPath function.
    """
    # Use JavaScript to generate the XPath
    xpath = await element.evaluate("""
        (element) => {
            const parts = [];
            let current = element;
            
            while (current && (current.nodeType === 1 || current.nodeType === 3)) {
                let index = 0;
                let hasSameTypeSiblings = false;
                const siblings = current.parentElement ? Array.from(current.parentElement.childNodes) : [];
                
                for (let i = 0; i < siblings.length; i++) {
                    const sibling = siblings[i];
                    if (sibling.nodeType === current.nodeType && 
                        sibling.nodeName === current.nodeName) {
                        index++;
                        hasSameTypeSiblings = true;
                        if (sibling === current) {
                            break;
                        }
                    }
                }
                
                // Text nodes are selected differently than elements
                if (current.nodeName !== '#text') {
                    const tagName = current.nodeName.toLowerCase();
                    const pathIndex = hasSameTypeSiblings ? `[${index}]` : '';
                    parts.unshift(`${tagName}${pathIndex}`);
                }
                
                current = current.parentElement;
            }
            
            return parts.length ? `/${parts.join('/')}` : '';
        }
    """)
    
    return xpath


async def generate_id_based_xpath(element: Any, element_info: Dict[str, Any]) -> Optional[str]:
    """
    Generate an ID-based XPath if the element has an ID.
    Matches TypeScript's generatedIdBasedXPath function.
    """
    element_id = element_info.get('id')
    if element_id:
        return f"//*[@id='{element_id}']"
    return None


async def get_element_xpath_info(page: Any, element: Any) -> Dict[str, Any]:
    """
    Get comprehensive XPath information for an element.
    
    Args:
        page: Playwright page instance
        element: Playwright element handle
        
    Returns:
        Dictionary with element info and XPath strategies
    """
    # Get element information
    info = await element.evaluate(XPATH_GENERATION_SCRIPT, element)
    
    # Generate XPath strategies
    xpaths = generate_xpath_strategies(info, info['tagName'])
    
    # Build positional XPath
    positional_xpath = build_positional_xpath(info['path'])
    xpaths.append(positional_xpath)
    
    # Find the unique XPath
    unique_xpath = await find_unique_xpath(page, info, info['tagName'])
    
    return {
        'element_info': info,
        'xpath_strategies': xpaths,
        'unique_xpath': unique_xpath or positional_xpath,
        'positional_xpath': positional_xpath
    }