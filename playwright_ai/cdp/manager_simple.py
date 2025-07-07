"""Simple CDP (Chrome DevTools Protocol) manager matching TypeScript implementation."""

import weakref
from typing import Dict, Any, Optional
from playwright.async_api import CDPSession, Page, Frame


class SimpleCDPSessionPool:
    """
    Manages CDP sessions with automatic cleanup.
    Matches TypeScript's simple CDP session management.
    """
    
    def __init__(self):
        # Use WeakKeyDictionary to auto-cleanup sessions when frames are GC'd
        self.frame_sessions: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()
        self.page_sessions: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()
        
    async def get_session(self, page: Page, frame: Optional[Frame] = None) -> CDPSession:
        """
        Get or create a CDP session for a frame.
        Matches TypeScript's getCDPClient logic.
        
        Args:
            page: The page to get session for
            frame: Optional frame (None for main frame)
            
        Returns:
            CDP session
        """
        # For main frame, use page-level session
        if frame is None or frame == page.main_frame:
            if page not in self.page_sessions:
                try:
                    session = await page.context.new_cdp_session(page)
                    self.page_sessions[page] = session
                except Exception as e:
                    raise RuntimeError(f"Failed to create CDP session for page: {e}")
            return self.page_sessions[page]
        
        # For subframes, check if we already have a session
        if frame in self.frame_sessions:
            return self.frame_sessions[frame]
        
        # Try to create frame-specific session
        try:
            session = await page.context.new_cdp_session(frame)
            self.frame_sessions[frame] = session
            return session
        except Exception as e:
            # Fallback for same-process iframes that share parent's session
            if "does not have a separate CDP session" in str(e) or "not an OOPIF" in str(e):
                # Re-use the page's session for same-process iframes
                root_session = await self.get_session(page)
                # Cache this alias so we don't try again
                self.frame_sessions[frame] = root_session
                return root_session
            raise RuntimeError(f"Failed to create CDP session for frame: {e}")
    
    async def is_session_valid(self, session: CDPSession) -> bool:
        """Check if a CDP session is still valid."""
        try:
            # Try a simple CDP command to check if session is alive
            await session.send('Runtime.evaluate', {'expression': '1'})
            return True
        except:
            return False
    
    async def cleanup(self):
        """Clean up all sessions."""
        # WeakKeyDictionary handles cleanup automatically when frames/pages are GC'd
        # But we can force cleanup of any remaining sessions
        all_sessions = set(self.page_sessions.values()) | set(self.frame_sessions.values())
        for session in all_sessions:
            try:
                await session.detach()
            except:
                pass  # Session might already be closed
        self.page_sessions.clear()
        self.frame_sessions.clear()


class SimpleCDPManager:
    """
    Simple CDP manager matching TypeScript implementation.
    No batching, event listeners, or other complex features.
    """
    
    def __init__(self):
        self.session_pool = SimpleCDPSessionPool()
        
    async def get_session(self, page: Page, frame: Optional[Frame] = None) -> CDPSession:
        """Get a CDP session from the pool."""
        return await self.session_pool.get_session(page, frame)
    
    async def execute(
        self, 
        session: CDPSession, 
        method: str, 
        params: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        Execute a CDP command.
        Simple passthrough - no batching or complex logic.
        """
        # Check if session is still valid before executing
        if not await self.session_pool.is_session_valid(session):
            raise RuntimeError(f"CDP session is no longer valid for method {method}")
        
        return await session.send(method, params or {})
    
    async def cleanup(self):
        """Clean up resources."""
        await self.session_pool.cleanup()


# Global CDP manager instance
cdp_manager = SimpleCDPManager()