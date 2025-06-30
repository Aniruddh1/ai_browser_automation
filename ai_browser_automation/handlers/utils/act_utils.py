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
    }
    
    # Clean selector (removes xpath= prefix, ensures starts with /)
    xpath = clean_selector(selector)
    
    # Get the locator with xpath prefix
    locator = page.locator(f"xpath={xpath}")
    
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
    
    This approach bypasses Playwright's built-in click and directly executes
    a click in the browser context, which works better for complex sites.
    """
    logger.debug(
        "action",
        "Clicking element using JavaScript",
        xpath=xpath,
        url=page.url
    )
    
    try:
        # First try to scroll the element into view
        await locator.evaluate("(el) => el.scrollIntoView({ behavior: 'smooth', block: 'center' })")
        await page.wait_for_timeout(500)  # Brief pause for scroll
        
        # Execute click via JavaScript
        await locator.evaluate("(el) => el.click()")
        
    except Exception as e:
        # Fallback to force click if JavaScript click fails
        logger.info(
            "action",
            "JavaScript click failed, trying force click",
            error=str(e)
        )
        
        try:
            await locator.click(force=True)
        except Exception as e2:
            logger.error(
                "action",
                "Force click also failed",
                error=str(e2)
            )
            raise
    
    # Handle possible page navigation
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
        await locator.press(key)
    except Exception as e:
        # Try page-level key press
        await page.keyboard.press(key)


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
    
    Checks for:
    - New tabs/windows opened
    - URL changes
    - Page reloads
    """
    logger.debug(
        "action",
        f"{action} complete, checking for navigation",
        initial_url=initial_url,
        current_url=page.url
    )
    
    # Check if URL changed
    if page.url != initial_url:
        logger.info(
            "action",
            "Page navigated to new URL",
            from_url=initial_url,
            to_url=page.url
        )
        
        # Wait for the new page to load
        try:
            await page.wait_for_load_state("domcontentloaded", timeout=timeout)
        except Exception:
            pass  # Page might already be loaded
    
    # Brief pause to let any animations or transitions complete
    await page.wait_for_timeout(1000)


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