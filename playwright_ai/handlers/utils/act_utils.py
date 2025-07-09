"""Utility functions for act handler."""

import asyncio
import re
from typing import Any, Dict, List, Optional, Tuple
from playwright.async_api import Page, Locator, ElementHandle, Error as PlaywrightError


async def perform_playwright_method(
    page: Page,
    method: str,
    selector: str,
    args: List[str],
    logger: Any,
    dom_settle_timeout: int = 30000,
) -> Dict[str, Any]:
    """
    Perform a Playwright method on an element.
    
    Args:
        page: Playwright page
        method: Method name to execute
        selector: Element selector
        args: Method arguments
        logger: Logger instance
        dom_settle_timeout: DOM settle timeout in ms
        
    Returns:
        Result dictionary with success status
    """
    # Map of special method handlers
    method_handlers = {
        "click": click_element,
        "fill": fill_or_type,
        "type": fill_or_type,
        "press": press_key,
        "scrollIntoView": scroll_into_view,
        "scrollTo": scroll_to_percentage,
        "scroll": scroll_to_percentage,
        "nextChunk": scroll_to_next_chunk,
        "prevChunk": scroll_to_previous_chunk,
    }
    
    # Clean selector (removes xpath= prefix, ensures starts with /)
    xpath = clean_selector(selector)
    
    # Get the locator with xpath prefix, use .first to handle multiple matches
    # Note: In Python Playwright, .first is a property, not a method
    locator = page.locator(f"xpath={xpath}").first
    
    # Log the action
    logger.debug(
        "action",
        f"Performing {method} on element",
        method=method,
        xpath=xpath,
        args=str(args)
    )
    
    initial_url = page.url
    
    try:
        if method in method_handlers:
            # Use specialized handler
            await method_handlers[method](
                page=page,
                locator=locator,
                xpath=xpath,
                args=args,
                logger=logger,
                initial_url=initial_url,
                dom_settle_timeout=dom_settle_timeout,
            )
        else:
            # Fallback to generic locator method
            await fallback_locator_method(
                locator=locator,
                method=method,
                args=args,
                logger=logger,
            )
        
        return {"success": True}
        
    except Exception as e:
        logger.error(
            "action",
            f"Error performing {method}",
            error=str(e),
            method=method,
            xpath=xpath
        )
        raise


async def click_element(
    page: Page,
    locator: Locator,
    xpath: str,
    args: List[str],
    logger: Any,
    initial_url: str,
    dom_settle_timeout: int,
) -> None:
    """
    Click an element using JavaScript evaluation for better reliability.
    
    This approach matches TypeScript's implementation more closely to avoid
    timing issues with multiple fallback methods.
    """
    logger.debug(
        "action",
        "Page URL before click",
        xpath=xpath,
        url=page.url
    )
    
    # Custom click error for better error messages
    class ClickError(Exception):
        def __init__(self, xpath: str, original_error: str):
            self.xpath = xpath
            self.original_error = original_error
            super().__init__(f"Failed to click element at {xpath}: {original_error}")
    
    try:
        # Primary method: JavaScript click (matching TypeScript)
        await locator.evaluate("""
            (el) => {
                // TypeScript casts to HTMLElement and clicks
                el.click();
            }
        """)
        
        logger.debug(
            "action",
            "Click successful",
            xpath=xpath
        )
        
    except Exception as e:
        # Log the error but follow TypeScript pattern of throwing immediately
        logger.error(
            "action",
            "Error performing click",
            error=str(e),
            trace=str(e.__traceback__),
            xpath=xpath,
            method="click",
            args=args
        )
        raise ClickError(xpath, str(e))
    
    # Handle possible page navigation with tab detection
    await handle_possible_page_navigation(
        action="click",
        xpath=xpath,
        initial_url=initial_url,
        page=page,
        logger=logger,
        timeout=dom_settle_timeout,
    )


async def fill_or_type(
    page: Page,
    locator: Locator,
    xpath: str,
    args: List[str],
    logger: Any,
    initial_url: str,
    dom_settle_timeout: int,
) -> None:
    """Fill or type text into an element."""
    text = args[0] if args else ""
    
    try:
        # Clear existing content first
        await locator.fill("", force=True)
        # Fill with new text
        await locator.fill(text, force=True)
        
    except Exception as e:
        # If fill fails, try typing
        logger.info(
            "action",
            "Fill failed, trying type method",
            error=str(e)
        )
        
        try:
            await locator.clear()
            await locator.type(text)
        except Exception as e2:
            logger.error(
                "action",
                "Type also failed",
                error=str(e2)
            )
            raise


async def press_key(
    page: Page,
    locator: Locator,
    xpath: str,
    args: List[str],
    logger: Any,
    initial_url: str,
    dom_settle_timeout: int,
) -> None:
    """Press a key or key combination."""
    key = args[0] if args else "Enter"
    
    try:
        # Try element-level key press first
        await locator.press(key)
    except Exception as e:
        logger.debug(
            "action",
            "Locator press failed, trying page-level key press",
            error=str(e)
        )
        # Try page-level key press
        await page.keyboard.press(key)
    
    # Handle navigation for keys that might trigger it (Enter, Space on links/buttons)
    if key.lower() in ["enter", "space", " "]:
        await handle_possible_page_navigation(
            action="press",
            xpath=xpath,
            initial_url=initial_url,
            page=page,
            logger=logger,
            timeout=dom_settle_timeout,
        )


async def scroll_into_view(
    page: Page,
    locator: Locator,
    xpath: str,
    args: List[str],
    logger: Any,
    initial_url: str,
    dom_settle_timeout: int,
) -> None:
    """Scroll element into view."""
    await locator.evaluate("""
        (el) => {
            el.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    """)
    await page.wait_for_timeout(500)


async def scroll_to_percentage(
    page: Page,
    locator: Locator,
    xpath: str,
    args: List[str],
    logger: Any,
    initial_url: str,
    dom_settle_timeout: int,
) -> None:
    """Scroll to a percentage of the element or page."""
    percentage_str = args[0] if args else "0%"
    percentage = float(percentage_str.rstrip('%'))
    
    await page.evaluate("""
        ({xpath, percentage}) => {
            const elementNode = window.getNodeFromXpath(xpath);
            if (!elementNode || elementNode.nodeType !== Node.ELEMENT_NODE) {
                console.warn('Could not locate element to scroll on.');
                return;
            }
            
            const element = elementNode;
            
            if (element.tagName.toLowerCase() === 'html' || 
                element.tagName.toLowerCase() === 'body') {
                // Scroll the window
                const scrollHeight = document.body.scrollHeight;
                const viewportHeight = window.innerHeight;
                const scrollTop = (scrollHeight - viewportHeight) * (percentage / 100);
                window.scrollTo({
                    top: scrollTop,
                    behavior: 'smooth'
                });
            } else {
                // Scroll the element
                const scrollHeight = element.scrollHeight;
                const clientHeight = element.clientHeight;
                const scrollTop = (scrollHeight - clientHeight) * (percentage / 100);
                element.scrollTo({
                    top: scrollTop,
                    behavior: 'smooth'
                });
            }
        }
    """, {"xpath": xpath, "percentage": percentage})
    
    await page.wait_for_timeout(500)


async def scroll_to_next_chunk(
    page: Page,
    locator: Locator,
    xpath: str,
    args: List[str],
    logger: Any,
    initial_url: str,
    dom_settle_timeout: int,
) -> None:
    """Scroll to next chunk (one viewport height down)."""
    logger.debug(
        "action",
        "Scrolling to next chunk",
        xpath=xpath
    )
    
    try:
        await page.evaluate("""
            ({xpath}) => {
                const elementNode = window.getNodeFromXpath(xpath);
                if (!elementNode || elementNode.nodeType !== Node.ELEMENT_NODE) {
                    console.warn('Could not locate element to scroll by its height.');
                    return Promise.resolve();
                }
                
                const element = elementNode;
                const tagName = element.tagName.toLowerCase();
                let height;
                
                if (tagName === 'html' || tagName === 'body') {
                    height = window.visualViewport.height;
                    window.scrollBy({
                        top: height,
                        left: 0,
                        behavior: 'smooth'
                    });
                    
                    const scrollingEl = document.scrollingElement || document.documentElement;
                    return window.waitForElementScrollEnd(scrollingEl);
                } else {
                    height = element.getBoundingClientRect().height;
                    element.scrollBy({
                        top: height,
                        left: 0,
                        behavior: 'smooth'
                    });
                    
                    return window.waitForElementScrollEnd(element);
                }
            }
        """, {"xpath": xpath})
    except Exception as e:
        logger.error(
            "action",
            "Error scrolling to next chunk",
            error=str(e),
            trace=str(e.__traceback__),
            xpath=xpath
        )
        raise


async def scroll_to_previous_chunk(
    page: Page,
    locator: Locator,
    xpath: str,
    args: List[str],
    logger: Any,
    initial_url: str,
    dom_settle_timeout: int,
) -> None:
    """Scroll to previous chunk (one viewport height up)."""
    logger.debug(
        "action",
        "Scrolling to previous chunk",
        xpath=xpath
    )
    
    try:
        await page.evaluate("""
            ({xpath}) => {
                const elementNode = window.getNodeFromXpath(xpath);
                if (!elementNode || elementNode.nodeType !== Node.ELEMENT_NODE) {
                    console.warn('Could not locate element to scroll by its height.');
                    return Promise.resolve();
                }
                
                const element = elementNode;
                const tagName = element.tagName.toLowerCase();
                let height;
                
                if (tagName === 'html' || tagName === 'body') {
                    height = window.visualViewport.height;
                    window.scrollBy({
                        top: -height,
                        left: 0,
                        behavior: 'smooth'
                    });
                    
                    const scrollingEl = document.scrollingElement || document.documentElement;
                    return window.waitForElementScrollEnd(scrollingEl);
                } else {
                    height = element.getBoundingClientRect().height;
                    element.scrollBy({
                        top: -height,
                        left: 0,
                        behavior: 'smooth'
                    });
                    
                    return window.waitForElementScrollEnd(element);
                }
            }
        """, {"xpath": xpath})
    except Exception as e:
        logger.error(
            "action",
            "Error scrolling to previous chunk",
            error=str(e),
            trace=str(e.__traceback__),
            xpath=xpath
        )
        raise


async def fallback_locator_method(
    locator: Locator,
    method: str,
    args: List[str],
    logger: Any,
) -> None:
    """
    Fallback handler for other Playwright locator methods.
    """
    # Get the method from the locator
    locator_method = getattr(locator, method, None)
    
    if not locator_method or not callable(locator_method):
        raise ValueError(f"Method {method} not found on locator")
    
    # Call the method with arguments
    if args:
        await locator_method(*args)
    else:
        await locator_method()


async def handle_possible_page_navigation(
    action: str,
    xpath: str,
    initial_url: str,
    page: Page,
    logger: Any,
    timeout: int = 30000,
) -> None:
    """
    Handle possible page navigation after an action.
    Matches TypeScript's sophisticated navigation detection.
    
    Checks for:
    - New tabs/windows opened
    - URL changes
    - Page reloads
    """
    logger.debug(
        "action",
        f"{action}, checking for page navigation",
        xpath=xpath,
        initial_url=initial_url,
        current_url=page.url
    )
    
    # Get the browser context to monitor for new pages
    context = page.context
    
    # Set up new page detection with timeout
    new_page = None
    async def wait_for_new_page():
        nonlocal new_page
        try:
            # Wait for a new page event with timeout
            # Get current pages
            initial_pages = context.pages
            
            # Wait for page event with timeout
            new_page = await asyncio.wait_for(
                context.wait_for_event("page"),
                timeout=1.5  # 1.5 second timeout like TypeScript
            )
            
            # Verify it's actually a new page
            if new_page not in initial_pages and new_page.url != "about:blank":
                return new_page
            else:
                new_page = None
        except asyncio.TimeoutError:
            new_page = None
        return None
    
    # Start monitoring for new page
    new_page_task = asyncio.create_task(wait_for_new_page())
    
    # Wait a bit for potential new page
    try:
        await asyncio.wait_for(new_page_task, timeout=1.5)
    except asyncio.TimeoutError:
        pass
    
    # Check if we got a new page
    if new_page and new_page.url != "about:blank":
        logger.info(
            "action",
            "New page detected (new tab) with URL",
            url=new_page.url,
            new_tab=True
        )
        
        # Close the new tab and navigate current page to that URL (TypeScript behavior)
        target_url = new_page.url
        await new_page.close()
        await page.goto(target_url)
        await page.wait_for_load_state("domcontentloaded")
        
        logger.debug(
            "action",
            "Navigated current page to new tab URL",
            url=target_url
        )
    else:
        logger.debug(
            "action",
            f"{action} complete",
            new_tab="no new tabs opened"
        )
    
    # Wait for DOM to settle (TypeScript's _waitForSettledDom)
    try:
        # Check if navigation happened
        if page.url != initial_url:
            logger.info(
                "action",
                "Page navigated to new URL",
                from_url=initial_url,
                to_url=page.url
            )
            
            # Wait for the page to load
            try:
                await page.wait_for_load_state("domcontentloaded", timeout=timeout)
            except Exception as e:
                logger.debug(
                    "action",
                    "Page already loaded or timeout",
                    error=str(e)
                )
        
        # Wait for network to be idle (similar to DOM settling)
        try:
            # Try to use our enhanced DOM settling if available
            if hasattr(page, '_wait_for_settled_dom'):
                logger.debug(
                    "action",
                    "Using enhanced DOM settling (network + mutations)"
                )
                await page._wait_for_settled_dom(timeout_ms=min(timeout, 30000))
            else:
                # Fallback to Playwright's networkidle
                await page.wait_for_load_state("networkidle", timeout=min(timeout, 5000))
        except Exception:
            # Network might not become idle, that's ok
            pass
            
    except Exception as e:
        logger.debug(
            "action",
            "Navigation handling timeout hit",
            error=str(e)
        )
    
    logger.debug(
        "action",
        "Finished waiting for (possible) page navigation"
    )


def clean_selector(selector: str) -> str:
    """
    Clean and normalize a selector.
    
    Args:
        selector: Raw selector string
        
    Returns:
        Cleaned selector
    """
    # Remove xpath= prefix if present
    cleaned = selector.replace("xpath=", "").strip()
    
    # Ensure XPath starts with /
    if cleaned and not cleaned.startswith("/"):
        cleaned = "/" + cleaned
    
    return cleaned