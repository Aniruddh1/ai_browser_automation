"""Utilities for detecting scrollable elements."""

from typing import List, Dict, Any, TYPE_CHECKING
import json

if TYPE_CHECKING:
    from playwright.async_api import Page


SCROLLABLE_DETECTION_SCRIPT = """
(function() {
    function isScrollable(element) {
        const style = window.getComputedStyle(element);
        const overflow = style.overflow + style.overflowY + style.overflowX;
        
        // Check if element has scrollable overflow
        if (!overflow.includes('auto') && !overflow.includes('scroll')) {
            return false;
        }
        
        // Check if element actually has scrollable content
        const hasVerticalScroll = element.scrollHeight > element.clientHeight;
        const hasHorizontalScroll = element.scrollWidth > element.clientWidth;
        
        return hasVerticalScroll || hasHorizontalScroll;
    }
    
    function getScrollableElements() {
        const elements = document.querySelectorAll('*');
        const scrollables = [];
        
        for (const element of elements) {
            try {
                if (isScrollable(element)) {
                    // Get XPath for the element
                    let xpath = '';
                    let currentElement = element;
                    
                    while (currentElement && currentElement !== document.documentElement) {
                        let index = 1;
                        let sibling = currentElement.previousSibling;
                        
                        while (sibling) {
                            if (sibling.nodeType === 1 && sibling.tagName === currentElement.tagName) {
                                index++;
                            }
                            sibling = sibling.previousSibling;
                        }
                        
                        const tagName = currentElement.tagName.toLowerCase();
                        xpath = `/${tagName}[${index}]${xpath}`;
                        currentElement = currentElement.parentNode;
                    }
                    
                    xpath = `/html[1]${xpath}`;
                    
                    const rect = element.getBoundingClientRect();
                    scrollables.push({
                        xpath: xpath,
                        tagName: element.tagName.toLowerCase(),
                        className: element.className || '',
                        id: element.id || '',
                        scrollHeight: element.scrollHeight,
                        clientHeight: element.clientHeight,
                        scrollWidth: element.scrollWidth,
                        clientWidth: element.clientWidth,
                        hasVerticalScroll: element.scrollHeight > element.clientHeight,
                        hasHorizontalScroll: element.scrollWidth > element.clientWidth,
                        rect: {
                            top: rect.top,
                            left: rect.left,
                            width: rect.width,
                            height: rect.height
                        }
                    });
                }
            } catch (e) {
                // Skip elements that throw errors
                continue;
            }
        }
        
        return scrollables;
    }
    
    return getScrollableElements();
})();
"""


async def get_scrollable_elements(page: 'Page') -> List[Dict[str, Any]]:
    """
    Get all scrollable elements on the page.
    
    Args:
        page: Playwright Page instance
        
    Returns:
        List of scrollable element information
    """
    try:
        scrollables = await page.evaluate(SCROLLABLE_DETECTION_SCRIPT)
        return scrollables
    except Exception as e:
        # Return empty list on error
        return []


async def mark_scrollable_in_tree(
    simplified_tree: List[Dict[str, Any]], 
    xpath_map: Dict[str, str],
    page: 'Page'
) -> List[Dict[str, Any]]:
    """
    Mark scrollable elements in the accessibility tree.
    
    Args:
        simplified_tree: The simplified accessibility tree
        xpath_map: Mapping of encoded IDs to XPaths
        page: Playwright Page instance
        
    Returns:
        Updated tree with scrollable markers
    """
    # Get scrollable elements
    scrollables = await get_scrollable_elements(page)
    
    # Create XPath to scrollable info map
    scrollable_map = {s['xpath']: s for s in scrollables}
    
    # Mark elements in tree
    for node in simplified_tree:
        encoded_id = node.get('encodedId')
        if encoded_id and encoded_id in xpath_map:
            xpath = xpath_map[encoded_id]
            # Remove xpath= prefix if present
            if xpath.startswith('xpath='):
                xpath = xpath[6:]
            
            if xpath in scrollable_map:
                scroll_info = scrollable_map[xpath]
                node['isScrollable'] = True
                node['scrollInfo'] = {
                    'hasVerticalScroll': scroll_info['hasVerticalScroll'],
                    'hasHorizontalScroll': scroll_info['hasHorizontalScroll'],
                    'scrollHeight': scroll_info['scrollHeight'],
                    'clientHeight': scroll_info['clientHeight']
                }
    
    return simplified_tree