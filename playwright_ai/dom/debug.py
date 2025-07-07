"""Visual debugging utilities for observed elements."""

from typing import List, Dict, Any, TYPE_CHECKING
import json

if TYPE_CHECKING:
    from playwright.async_api import Page


DRAW_OVERLAY_SCRIPT = """
(function(elements) {
    // Remove any existing overlays
    const existingOverlays = document.querySelectorAll('.playwright-ai-overlay');
    existingOverlays.forEach(el => el.remove());
    
    // Create style element if it doesn't exist
    let styleEl = document.getElementById('playwright-ai-styles');
    if (!styleEl) {
        styleEl = document.createElement('style');
        styleEl.id = 'playwright-ai-styles';
        styleEl.textContent = `
            .playwright-ai-overlay {
                position: absolute;
                border: 2px solid #ff0080;
                background: rgba(255, 0, 128, 0.1);
                pointer-events: none;
                z-index: 999999;
                transition: all 0.3s ease;
            }
            .playwright-ai-overlay:hover {
                background: rgba(255, 0, 128, 0.3);
                border-color: #ff0080;
            }
            .playwright-ai-label {
                position: absolute;
                top: -20px;
                left: 0;
                background: #ff0080;
                color: white;
                font-size: 12px;
                padding: 2px 6px;
                border-radius: 3px;
                font-family: monospace;
                white-space: nowrap;
            }
            .playwright-ai-scrollable {
                border-color: #00ff80 !important;
                background: rgba(0, 255, 128, 0.1) !important;
            }
            .playwright-ai-scrollable .playwright-ai-label {
                background: #00ff80;
                color: black;
            }
        `;
        document.head.appendChild(styleEl);
    }
    
    // Draw overlays for each element
    elements.forEach((element, index) => {
        try {
            let targetEl = null;
            
            // Try to find element by XPath
            if (element.xpath) {
                const xpath = element.xpath.replace('xpath=', '');
                const result = document.evaluate(
                    xpath, 
                    document, 
                    null, 
                    XPathResult.FIRST_ORDERED_NODE_TYPE, 
                    null
                );
                targetEl = result.singleNodeValue;
            }
            
            if (!targetEl) return;
            
            const rect = targetEl.getBoundingClientRect();
            if (rect.width === 0 || rect.height === 0) return;
            
            // Create overlay
            const overlay = document.createElement('div');
            overlay.className = 'playwright-ai-overlay';
            if (element.isScrollable) {
                overlay.className += ' playwright-ai-scrollable';
            }
            
            // Position overlay
            overlay.style.left = `${rect.left + window.scrollX}px`;
            overlay.style.top = `${rect.top + window.scrollY}px`;
            overlay.style.width = `${rect.width}px`;
            overlay.style.height = `${rect.height}px`;
            
            // Add label
            const label = document.createElement('div');
            label.className = 'playwright-ai-label';
            label.textContent = element.encodedId || `elem-${index}`;
            if (element.isScrollable) {
                label.textContent += ' [SCROLL]';
            }
            overlay.appendChild(label);
            
            document.body.appendChild(overlay);
        } catch (e) {
            console.error('Error drawing overlay for element:', e);
        }
    });
    
    // Return number of overlays drawn
    return document.querySelectorAll('.playwright-ai-overlay').length;
})(arguments[0]);
"""


CLEAR_OVERLAYS_SCRIPT = """
(function() {
    const overlays = document.querySelectorAll('.playwright-ai-overlay');
    overlays.forEach(el => el.remove());
    
    const style = document.getElementById('playwright-ai-styles');
    if (style) style.remove();
    
    return overlays.length;
})();
"""


async def draw_element_overlays(
    page: 'Page', 
    elements: List[Dict[str, Any]], 
    xpath_map: Dict[str, str]
) -> int:
    """
    Draw visual overlays on observed elements.
    
    Args:
        page: Playwright Page instance
        elements: List of elements to highlight
        xpath_map: Mapping of encoded IDs to XPaths
        
    Returns:
        Number of overlays drawn
    """
    # Prepare element data for browser
    overlay_data = []
    for elem in elements:
        encoded_id = elem.get('encodedId') or elem.get('encoded_id')
        if encoded_id and encoded_id in xpath_map:
            overlay_data.append({
                'encodedId': encoded_id,
                'xpath': xpath_map[encoded_id],
                'isScrollable': elem.get('isScrollable', False)
            })
    
    # Draw overlays
    try:
        num_drawn = await page.evaluate(DRAW_OVERLAY_SCRIPT, overlay_data)
        return num_drawn
    except Exception as e:
        print(f"Error drawing overlays: {e}")
        return 0


async def clear_element_overlays(page: 'Page') -> int:
    """
    Clear all visual overlays from the page.
    
    Args:
        page: Playwright Page instance
        
    Returns:
        Number of overlays removed
    """
    try:
        num_cleared = await page.evaluate(CLEAR_OVERLAYS_SCRIPT)
        return num_cleared
    except Exception as e:
        print(f"Error clearing overlays: {e}")
        return 0