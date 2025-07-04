"""Scroll-related utilities for DOM manipulation."""

from typing import List, Optional
from playwright.async_api import Page, ElementHandle


async def can_element_scroll(page: Page, element: ElementHandle) -> bool:
    """
    Test if an element can actually scroll.
    Matches TypeScript's canElementScroll implementation.
    
    Args:
        page: Playwright page
        element: Element to test
        
    Returns:
        True if element can scroll
    """
    return await element.evaluate("""
        (el) => {
            // Save current position
            const origX = el.scrollLeft;
            const origY = el.scrollTop;
            
            // Try to scroll
            el.scrollTo(origX + 1, origY + 1);
            
            // Check if it actually scrolled
            const scrolled = el.scrollLeft !== origX || el.scrollTop !== origY;
            
            // Restore original position
            el.scrollTo(origX, origY);
            
            return scrolled;
        }
    """)


async def wait_for_element_scroll_end(page: Page, element: ElementHandle, timeout: int = 1000) -> None:
    """
    Wait for an element's scroll animation to complete.
    
    Args:
        page: Playwright page
        element: Element that is scrolling
        timeout: Maximum time to wait in milliseconds
    """
    await element.evaluate("""
        (el, timeout) => {
            return new Promise((resolve) => {
                let lastScrollTop = el.scrollTop;
                let lastScrollLeft = el.scrollLeft;
                let scrollEndTimer;
                
                const checkScroll = () => {
                    if (el.scrollTop === lastScrollTop && el.scrollLeft === lastScrollLeft) {
                        // Scroll position hasn't changed
                        clearTimeout(scrollEndTimer);
                        resolve();
                    } else {
                        // Still scrolling
                        lastScrollTop = el.scrollTop;
                        lastScrollLeft = el.scrollLeft;
                        scrollEndTimer = setTimeout(checkScroll, 100);
                    }
                };
                
                // Start checking
                scrollEndTimer = setTimeout(checkScroll, 100);
                
                // Timeout fallback
                setTimeout(() => {
                    clearTimeout(scrollEndTimer);
                    resolve();
                }, timeout);
            });
        }
    """, timeout)


async def get_scrollable_elements(page: Page, top_n: Optional[int] = None) -> List[str]:
    """
    Find scrollable elements on the page and return their XPaths.
    
    Args:
        page: Playwright page
        top_n: Optional limit on number of elements to return
        
    Returns:
        List of XPaths for scrollable elements
    """
    return await page.evaluate("""
        (topN) => {
            // Get all elements
            const allElements = document.querySelectorAll('*');
            const scrollableElements = [document.documentElement];
            
            // Find scrollable elements
            for (const elem of allElements) {
                const style = window.getComputedStyle(elem);
                const overflowY = style.overflowY;
                const overflowX = style.overflowX;
                
                const isPotentiallyScrollable = 
                    overflowY === 'auto' || overflowY === 'scroll' || overflowY === 'overlay' ||
                    overflowX === 'auto' || overflowX === 'scroll' || overflowX === 'overlay';
                
                if (isPotentiallyScrollable) {
                    const hasVerticalScroll = elem.scrollHeight > elem.clientHeight;
                    const hasHorizontalScroll = elem.scrollWidth > elem.clientWidth;
                    
                    if (hasVerticalScroll || hasHorizontalScroll) {
                        scrollableElements.push(elem);
                    }
                }
            }
            
            // Sort by scrollHeight (largest first)
            scrollableElements.sort((a, b) => b.scrollHeight - a.scrollHeight);
            
            // Limit if requested
            const limited = topN ? scrollableElements.slice(0, topN) : scrollableElements;
            
            // Convert to XPaths
            return limited.map(elem => {
                const getXPath = (el) => {
                    if (el.id) return `//*[@id="${el.id}"]`;
                    if (el === document.body) return '/html/body';
                    if (el === document.documentElement) return '/html';
                    
                    const parts = [];
                    while (el && el.nodeType === Node.ELEMENT_NODE) {
                        let index = 0;
                        let sibling = el.previousSibling;
                        while (sibling) {
                            if (sibling.nodeType === Node.ELEMENT_NODE && 
                                sibling.nodeName === el.nodeName) {
                                index++;
                            }
                            sibling = sibling.previousSibling;
                        }
                        const tagName = el.nodeName.toLowerCase();
                        const part = index > 0 ? `${tagName}[${index + 1}]` : tagName;
                        parts.unshift(part);
                        el = el.parentNode;
                    }
                    return '/' + parts.join('/');
                };
                
                return getXPath(elem);
            });
        }
    """, top_n)