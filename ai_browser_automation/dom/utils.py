"""DOM utility functions for AIBrowserAutomation."""

import re
from typing import Dict, List, Any, Optional, Tuple
from playwright.async_api import Page, ElementHandle


async def get_element_xpath(page: Page, element: ElementHandle) -> Optional[str]:
    """
    Get XPath for an element.
    
    Args:
        page: Playwright page
        element: Element handle
        
    Returns:
        XPath string or None
    """
    try:
        return await page.evaluate("""
            (element) => {
                if (!element) return null;
                
                const getXPath = (node) => {
                    if (node.id) {
                        return `//*[@id="${node.id}"]`;
                    }
                    
                    if (node === document.body) {
                        return '/html/body';
                    }
                    
                    let position = 0;
                    let sibling = node;
                    while (sibling) {
                        if (sibling.nodeType === 1 && sibling.tagName === node.tagName) {
                            position++;
                        }
                        sibling = sibling.previousSibling;
                    }
                    
                    const parentPath = getXPath(node.parentNode);
                    const tagName = node.tagName.toLowerCase();
                    return `${parentPath}/${tagName}[${position}]`;
                };
                
                return getXPath(element);
            }
        """, element)
    except Exception:
        return None


async def get_clickable_elements(page: Page) -> List[Dict[str, Any]]:
    """
    Get all clickable elements on the page.
    
    Args:
        page: Playwright page
        
    Returns:
        List of element information
    """
    return await page.evaluate("""
        () => {
            // Use injected function if available
            if (window.getInteractiveElements) {
                const interactiveElements = window.getInteractiveElements();
                return interactiveElements.filter(item => {
                    const elem = item.element;
                    const isClickable = (
                        elem.tagName === 'A' ||
                        elem.tagName === 'BUTTON' ||
                        (elem.tagName === 'INPUT' && (elem.type === 'button' || elem.type === 'submit')) ||
                        elem.getAttribute('role') === 'button' ||
                        elem.getAttribute('role') === 'link' ||
                        elem.onclick !== null
                    );
                    return isClickable;
                }).map(item => ({
                    tagName: item.tagName,
                    text: item.text,
                    href: item.attributes.href || null,
                    id: item.attributes.id || null,
                    className: item.attributes.class || '',
                    selector: item.selector,
                    rect: (() => {
                        const rect = item.element.getBoundingClientRect();
                        return {
                            x: Math.round(rect.x),
                            y: Math.round(rect.y),
                            width: Math.round(rect.width),
                            height: Math.round(rect.height)
                        };
                    })()
                }));
            }
            
            // Fallback to original implementation
            const elements = [];
            const seen = new WeakSet();
            
            const clickableSelectors = [
                'a', 'button', 'input[type="button"]', 'input[type="submit"]',
                '[role="button"]', '[onclick]', '[tabindex]:not([tabindex="-1"])'
            ];
            
            clickableSelectors.forEach(selector => {
                try {
                    document.querySelectorAll(selector).forEach(el => {
                        if (seen.has(el)) return;
                        seen.add(el);
                        
                        const rect = el.getBoundingClientRect();
                        const style = window.getComputedStyle(el);
                        
                        if (rect.width > 0 && rect.height > 0 && 
                            style.display !== 'none' && 
                            style.visibility !== 'hidden' &&
                            style.opacity !== '0') {
                            
                            let selector = el.tagName.toLowerCase();
                            if (el.id) {
                                selector = `#${el.id}`;
                            } else if (el.className) {
                                const classes = el.className.split(' ').filter(c => c && !c.startsWith('css-'));
                                if (classes.length > 0) {
                                    selector += '.' + classes.slice(0, 2).join('.');
                                }
                            }
                            
                            elements.push({
                                tagName: el.tagName.toLowerCase(),
                                text: (el.textContent || '').trim().substring(0, 100),
                                href: el.href || null,
                                id: el.id || null,
                                className: el.className || '',
                                selector: selector,
                                rect: {
                                    x: Math.round(rect.x),
                                    y: Math.round(rect.y),
                                    width: Math.round(rect.width),
                                    height: Math.round(rect.height)
                                }
                            });
                        }
                    });
                } catch (e) {
                    // Ignore selector errors
                }
            });
            
            return elements;
        }
    """)


async def get_input_elements(page: Page) -> List[Dict[str, Any]]:
    """
    Get all input elements on the page.
    
    Args:
        page: Playwright page
        
    Returns:
        List of input element information
    """
    return await page.evaluate("""
        () => {
            // Use injected function if available
            if (window.getInteractiveElements) {
                const interactiveElements = window.getInteractiveElements();
                return interactiveElements.filter(item => {
                    const elem = item.element;
                    const isInput = (
                        elem.tagName === 'INPUT' ||
                        elem.tagName === 'TEXTAREA' ||
                        elem.tagName === 'SELECT' ||
                        elem.contentEditable === 'true' ||
                        elem.getAttribute('role') === 'textbox' ||
                        elem.getAttribute('role') === 'searchbox' ||
                        elem.getAttribute('role') === 'combobox'
                    );
                    return isInput;
                }).map(item => {
                    const elem = item.element;
                    return {
                        tagName: item.tagName,
                        type: elem.type || item.type || 'text',
                        name: item.attributes.name || null,
                        id: item.attributes.id || null,
                        placeholder: item.attributes.placeholder || null,
                        value: elem.value || '',
                        required: elem.required || false,
                        disabled: elem.disabled || false,
                        readonly: elem.readOnly || false,
                        selector: item.selector,
                        rect: (() => {
                            const rect = elem.getBoundingClientRect();
                            return {
                                x: Math.round(rect.x),
                                y: Math.round(rect.y),
                                width: Math.round(rect.width),
                                height: Math.round(rect.height)
                            };
                        })()
                    };
                });
            }
            
            // Fallback to original implementation
            const elements = [];
            
            try {
                const inputs = document.querySelectorAll('input, textarea, select, [contenteditable="true"]');
                
                inputs.forEach(el => {
                    const rect = el.getBoundingClientRect();
                    const style = window.getComputedStyle(el);
                    
                    if (rect.width > 0 && rect.height > 0 &&
                        style.display !== 'none' &&
                        style.visibility !== 'hidden') {
                        
                        let selector = el.tagName.toLowerCase();
                        if (el.id) {
                            selector = `#${el.id}`;
                        } else if (el.name) {
                            selector += `[name="${el.name}"]`;
                        } else if (el.className) {
                            const classes = el.className.split(' ').filter(c => c && !c.startsWith('css-'));
                            if (classes.length > 0) {
                                selector += '.' + classes[0];
                            }
                        }
                        
                        elements.push({
                            tagName: el.tagName.toLowerCase(),
                            type: el.type || 'text',
                            name: el.name || null,
                            id: el.id || null,
                            placeholder: el.placeholder || null,
                            value: el.value || '',
                            required: el.required || false,
                            disabled: el.disabled || false,
                            readonly: el.readOnly || false,
                            selector: selector,
                            rect: {
                                x: Math.round(rect.x),
                                y: Math.round(rect.y),
                                width: Math.round(rect.width),
                                height: Math.round(rect.height)
                            }
                        });
                    }
                });
            } catch (e) {
                // Return empty array on error
            }
            
            return elements;
        }
    """)


async def get_page_text(page: Page) -> str:
    """
    Get all visible text content from the page.
    
    Args:
        page: Playwright page
        
    Returns:
        Page text content
    """
    return await page.evaluate("""
        () => {
            // Ensure document.body exists
            if (!document.body) {
                return '';
            }
            
            try {
                const walker = document.createTreeWalker(
                    document.body,
                    NodeFilter.SHOW_TEXT,
                    {
                        acceptNode: (node) => {
                            const parent = node.parentElement;
                            if (!parent) return NodeFilter.FILTER_REJECT;
                            
                            const style = window.getComputedStyle(parent);
                            if (style.display === 'none' || style.visibility === 'hidden') {
                                return NodeFilter.FILTER_REJECT;
                            }
                            
                            if (node.textContent && node.textContent.trim()) {
                                return NodeFilter.FILTER_ACCEPT;
                            }
                            
                            return NodeFilter.FILTER_REJECT;
                        }
                    }
                );
                
                const texts = [];
                let node;
                while (node = walker.nextNode()) {
                    const text = node.textContent.trim();
                    if (text) {
                        texts.push(text);
                    }
                }
                
                return texts.join(' ');
            } catch (e) {
                // Fallback to simple text extraction
                return document.body.innerText || document.body.textContent || '';
            }
        }
    """)


def build_selector_from_attributes(attributes: Dict[str, str]) -> str:
    """
    Build a CSS selector from element attributes.
    
    Args:
        attributes: Element attributes
        
    Returns:
        CSS selector string
    """
    selector_parts = []
    
    # Priority order for attributes
    if 'id' in attributes and attributes['id']:
        return f"#{attributes['id']}"
    
    if 'data-testid' in attributes:
        selector_parts.append(f'[data-testid="{attributes["data-testid"]}"]')
    elif 'data-qa' in attributes:
        selector_parts.append(f'[data-qa="{attributes["data-qa"]}"]')
    elif 'name' in attributes:
        selector_parts.append(f'[name="{attributes["name"]}"]')
    
    if 'class' in attributes and attributes['class']:
        classes = attributes['class'].strip().split()
        for cls in classes[:2]:  # Use first 2 classes max
            if cls and not cls.startswith('css-'):  # Skip generated classes
                selector_parts.append(f'.{cls}')
    
    return ''.join(selector_parts) if selector_parts else ''


# Unicode constants for text cleaning
PUA_START = 0xE000
PUA_END = 0xF8FF
NBSP_CHARS = {0x00A0, 0x202F, 0x2007, 0xFEFF}  # Various non-breaking space characters


def clean_text(text: str) -> str:
    """
    Clean text content for display by removing private-use unicode characters,
    normalizing whitespace, and trimming the result.
    
    Args:
        text: Raw text content
        
    Returns:
        Cleaned text with PUA characters removed, NBSP variants collapsed,
        consecutive spaces merged, and leading/trailing whitespace trimmed.
    """
    if not text:
        return ""
    
    # Remove PUA characters and normalize whitespace in a single pass
    output = []
    prev_was_space = False
    
    for char in text:
        code = ord(char)
        
        # Skip PUA characters
        if PUA_START <= code <= PUA_END:
            continue
        
        # Convert NBSP variants to regular space
        if code in NBSP_CHARS or char.isspace():
            if not prev_was_space:
                output.append(' ')
                prev_was_space = True
        else:
            output.append(char)
            prev_was_space = False
    
    # Join and trim
    result = ''.join(output).strip()
    
    # Remove zero-width characters that might have been missed
    result = re.sub(r'[\u200b\u200c\u200d\u2060\uFEFF]', '', result)
    
    return result


async def wait_for_selector_stable(
    page: Page,
    selector: str,
    timeout: int = 30000,
    stable_time: int = 500
) -> bool:
    """
    Wait for a selector to be stable (not moving or changing).
    
    Args:
        page: Playwright page
        selector: CSS selector
        timeout: Maximum wait time in ms
        stable_time: Time element must be stable in ms
        
    Returns:
        True if element is stable, False if timeout
    """
    try:
        # Wait for element to exist
        await page.wait_for_selector(selector, timeout=timeout)
        
        # Wait for element to be stable
        await page.evaluate(f"""
            async (selector, stableTime) => {{
                const element = document.querySelector(selector);
                if (!element) return false;
                
                let lastRect = element.getBoundingClientRect();
                let stableStart = Date.now();
                
                while (Date.now() - stableStart < stableTime) {{
                    await new Promise(resolve => setTimeout(resolve, 100));
                    const currentRect = element.getBoundingClientRect();
                    
                    if (lastRect.x !== currentRect.x || 
                        lastRect.y !== currentRect.y ||
                        lastRect.width !== currentRect.width ||
                        lastRect.height !== currentRect.height) {{
                        lastRect = currentRect;
                        stableStart = Date.now();
                    }}
                }}
                
                return true;
            }}
        """, selector, stable_time)
        
        return True
    except Exception:
        return False