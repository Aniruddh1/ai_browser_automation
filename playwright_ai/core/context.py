"""PlaywrightAIContext implementation with proxy pattern."""

import weakref
from typing import Optional, Any, Dict, List, TYPE_CHECKING
from playwright.async_api import BrowserContext, Page

from ..utils.logger import PlaywrightAILogger
from .errors import PageNotAvailableError

if TYPE_CHECKING:
    from .playwright_ai import PlaywrightAI
    from .page import PlaywrightAIPage


class PlaywrightAIContext:
    """
    Enhanced browser context that wraps Playwright's BrowserContext.
    
    Uses proxy pattern to intercept method calls and maintain active page tracking.
    """
    
    def __init__(self, context: BrowserContext, playwright_ai: 'PlaywrightAI'):
        """
        Initialize PlaywrightAIContext.
        
        Args:
            context: Playwright BrowserContext instance
            playwright_ai: Parent PlaywrightAI instance
        """
        self._context = context
        self._ai_browser_automation = playwright_ai
        self._logger = playwright_ai.logger.child(component="context")
        self._active_page_ref: Optional[weakref.ref['PlaywrightAIPage']] = None
        self._pages: List[weakref.ref['PlaywrightAIPage']] = []
        
        # Track context ID for debugging
        self._context_id = id(self)
        
        self._logger.debug(
            "context:init",
            "PlaywrightAIContext created",
            context_id=self._context_id,
        )
    
    @property
    def playwright_ai(self) -> 'PlaywrightAI':
        """Get parent PlaywrightAI instance."""
        return self._ai_browser_automation
    
    @property
    def active_page(self) -> Optional['PlaywrightAIPage']:
        """Get the currently active page."""
        if self._active_page_ref:
            page = self._active_page_ref()
            if page:
                return page
        return None
    
    @active_page.setter
    def active_page(self, page: Optional['PlaywrightAIPage']) -> None:
        """Set the active page."""
        if page:
            self._active_page_ref = weakref.ref(page)
            self._logger.debug(
                "context:active_page",
                "Active page updated",
                page_id=id(page),
            )
        else:
            self._active_page_ref = None
    
    async def new_page(self, **kwargs: Any) -> 'PlaywrightAIPage':
        """
        Create a new PlaywrightAIPage.
        
        Args:
            **kwargs: Options for page creation
            
        Returns:
            PlaywrightAIPage instance
        """
        # Import here to avoid circular dependency
        from .page import PlaywrightAIPage
        
        # Create Playwright page
        playwright_page = await self._context.new_page(**kwargs)
        
        # Wrap with PlaywrightAIPage
        page = PlaywrightAIPage(playwright_page, self)
        
        # Track the page
        self._pages.append(weakref.ref(page))
        self.active_page = page
        
        self._logger.info(
            "context:new_page",
            "Created new page",
            page_id=id(page),
            url="about:blank",
        )
        
        return page
    
    async def pages(self) -> List['PlaywrightAIPage']:
        """
        Get all pages in this context.
        
        Returns:
            List of PlaywrightAIPage instances
        """
        # Clean up dead references
        self._pages = [ref for ref in self._pages if ref() is not None]
        
        # Return live pages
        pages = []
        for ref in self._pages:
            page = ref()
            if page:
                pages.append(page)
        
        return pages
    
    async def close(self) -> None:
        """Close the context and all pages."""
        self._logger.info("context:close", "Closing context")
        
        # Close all pages
        for page in await self.pages():
            try:
                await page.close()
            except Exception as e:
                self._logger.error(
                    "context:close",
                    f"Error closing page: {e}",
                    page_id=id(page),
                    error=str(e),
                )
        
        # Close Playwright context
        await self._context.close()
        
        self._logger.info("context:close", "Context closed")
    
    def __getattr__(self, name: str) -> Any:
        """
        Proxy pattern implementation for method interception.
        
        This allows us to intercept Playwright context methods and
        add our own logic while maintaining compatibility.
        
        Args:
            name: Attribute or method name
            
        Returns:
            Proxied attribute or method
        """
        # Get attribute from wrapped context
        attr = getattr(self._context, name)
        
        # If it's not a method, return as-is
        if not callable(attr):
            return attr
        
        # For methods, wrap them to update active page if needed
        async def wrapper(*args, **kwargs):
            result = await attr(*args, **kwargs) if asyncio.iscoroutinefunction(attr) else attr(*args, **kwargs)
            
            # Special handling for methods that might change active page
            if name in ['bring_to_front', 'focus']:
                # These methods might change which page is active
                # We'd need to update our active_page tracking
                pass
            
            return result
        
        return wrapper
    
    @property
    def browser(self):
        """Get the browser instance."""
        return self._context.browser
    
    @property
    def pages_count(self) -> int:
        """Get the number of pages in this context."""
        # Clean up dead references
        self._pages = [ref for ref in self._pages if ref() is not None]
        return len(self._pages)
    
    def set_default_navigation_timeout(self, timeout: float) -> None:
        """Set default navigation timeout."""
        self._context.set_default_navigation_timeout(timeout)
    
    def set_default_timeout(self, timeout: float) -> None:
        """Set default timeout."""
        self._context.set_default_timeout(timeout)
    
    async def add_cookies(self, cookies: List[Dict[str, Any]]) -> None:
        """Add cookies to the context."""
        await self._context.add_cookies(cookies)
    
    async def clear_cookies(self) -> None:
        """Clear all cookies."""
        await self._context.clear_cookies()
    
    async def grant_permissions(self, permissions: List[str], origin: Optional[str] = None) -> None:
        """Grant permissions."""
        await self._context.grant_permissions(permissions, origin=origin)
    
    async def clear_permissions(self) -> None:
        """Clear all permissions."""
        await self._context.clear_permissions()
    
    async def storage_state(self, path: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get storage state."""
        return await self._context.storage_state(path=path)
    
    def __repr__(self) -> str:
        """String representation."""
        return f"<PlaywrightAIContext id={self._context_id} pages={self.pages_count}>"


# Import asyncio at module level
import asyncio