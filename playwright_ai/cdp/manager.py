"""Advanced CDP (Chrome DevTools Protocol) manager for Playwright AI."""

import asyncio
from typing import Dict, List, Any, Optional, Callable, Set, Tuple
from collections import defaultdict
from playwright.async_api import CDPSession, Page, Frame
import json
import weakref


class CDPEventListener:
    """Manages CDP event subscriptions."""
    
    def __init__(self):
        self.listeners: Dict[str, List[Callable]] = defaultdict(list)
        self.active_sessions: Set[CDPSession] = set()
        
    async def add_listener(
        self, 
        session: CDPSession, 
        event: str, 
        callback: Callable[[Dict[str, Any]], None]
    ) -> None:
        """
        Add an event listener for a CDP event.
        
        Args:
            session: CDP session to listen on
            event: CDP event name (e.g., 'Network.requestWillBeSent')
            callback: Function to call when event fires
        """
        # Register the callback
        self.listeners[event].append(callback)
        
        # Set up the event handler if this is the first listener
        if len(self.listeners[event]) == 1:
            async def handler(params):
                for cb in self.listeners[event]:
                    try:
                        await cb(params) if asyncio.iscoroutinefunction(cb) else cb(params)
                    except Exception as e:
                        print(f"Error in CDP event handler for {event}: {e}")
            
            session.on(event, handler)
            self.active_sessions.add(session)
    
    async def remove_listener(
        self, 
        event: str, 
        callback: Callable[[Dict[str, Any]], None]
    ) -> None:
        """Remove an event listener."""
        if event in self.listeners and callback in self.listeners[event]:
            self.listeners[event].remove(callback)
            if not self.listeners[event]:
                del self.listeners[event]
    
    def clear(self):
        """Clear all listeners."""
        self.listeners.clear()
        self.active_sessions.clear()


class CDPSessionPool:
    """Manages a pool of CDP sessions for performance."""
    
    def __init__(self):
        # Use WeakKeyDictionary to auto-cleanup sessions when frames are GC'd
        self.frame_sessions: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()  # frame -> session
        self.page_sessions: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()  # page -> main session
        
    async def get_session(self, page: Page, frame: Optional[Frame] = None) -> CDPSession:
        """
        Get or create a CDP session for a frame.
        
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
            if "does not have a separate CDP session" in str(e):
                # Re-use the page's session for same-process iframes
                root_session = await self.get_session(page)  # Recursive call to get page session
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
        all_sessions = list(self.page_sessions.values()) + list(self.frame_sessions.values())
        for session in all_sessions:
            try:
                await session.detach()
            except:
                pass  # Session might already be closed
        self.page_sessions.clear()
        self.frame_sessions.clear()


class CDPBatchExecutor:
    """Batches CDP calls for better performance."""
    
    def __init__(self):
        self.pending_calls: List[Tuple[CDPSession, str, Dict[str, Any], asyncio.Future]] = []
        self.batch_size = 10
        self.batch_timeout = 0.05  # 50ms
        self._batch_task = None
        
    async def execute(
        self, 
        session: CDPSession, 
        method: str, 
        params: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        Execute a CDP command, potentially batching it.
        
        Args:
            session: CDP session
            method: CDP method name
            params: Method parameters
            
        Returns:
            Command result
        """
        # Some commands should not be batched
        no_batch_methods = {
            'Runtime.evaluate',  # Often time-sensitive
            'DOM.getDocument',   # Usually needs immediate result
            'Network.enable',    # State changes
            'Page.navigate'      # Navigation
        }
        
        if method in no_batch_methods:
            return await session.send(method, params or {})
        
        # Add to batch
        future = asyncio.Future()
        self.pending_calls.append((session, method, params or {}, future))
        
        # Start batch processor if not running
        if self._batch_task is None or self._batch_task.done():
            self._batch_task = asyncio.create_task(self._process_batch())
        
        return await future
    
    async def _process_batch(self):
        """Process pending CDP calls in batches."""
        await asyncio.sleep(self.batch_timeout)
        
        while self.pending_calls:
            # Take up to batch_size calls
            batch = self.pending_calls[:self.batch_size]
            self.pending_calls = self.pending_calls[self.batch_size:]
            
            # Group by session for efficiency
            by_session = defaultdict(list)
            for session, method, params, future in batch:
                by_session[session].append((method, params, future))
            
            # Execute calls per session in parallel
            tasks = []
            for session, calls in by_session.items():
                tasks.append(self._execute_session_batch(session, calls))
            
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _execute_session_batch(
        self, 
        session: CDPSession, 
        calls: List[Tuple[str, Dict[str, Any], asyncio.Future]]
    ):
        """Execute a batch of calls for a single session."""
        for method, params, future in calls:
            try:
                result = await session.send(method, params)
                future.set_result(result)
            except Exception as e:
                future.set_exception(e)


class PartialTreeExtractor:
    """Extracts partial accessibility trees for better performance."""
    
    async def get_partial_tree(
        self, 
        session: CDPSession, 
        node_id: Optional[str] = None,
        backend_node_id: Optional[int] = None,
        max_depth: int = 3
    ) -> Dict[str, Any]:
        """
        Get a partial accessibility tree starting from a specific node.
        
        Args:
            session: CDP session
            node_id: Accessibility node ID
            backend_node_id: Backend DOM node ID
            max_depth: Maximum depth to traverse
            
        Returns:
            Partial accessibility tree
        """
        params = {}
        if node_id:
            params['nodeId'] = node_id
        if backend_node_id:
            params['backendNodeId'] = backend_node_id
        if max_depth:
            params['depth'] = max_depth
            
        try:
            result = await session.send('Accessibility.getPartialAXTree', params)
            return result.get('nodes', [])
        except Exception as e:
            print(f"Error getting partial tree: {e}")
            # Fallback to full tree
            result = await session.send('Accessibility.getFullAXTree')
            return result.get('nodes', [])


class FrameChainResolver:
    """Resolves frame chains from XPath expressions."""
    
    @staticmethod
    def parse_frame_chain(xpath: str) -> Tuple[List[str], str]:
        """
        Parse an XPath to extract frame chain and element path.
        
        Args:
            xpath: XPath potentially containing iframe steps
            
        Returns:
            Tuple of (frame_selectors, element_xpath)
        """
        # Pattern: //iframe[@id='frame1']//iframe[@id='frame2']//button
        parts = xpath.split('//')
        frame_selectors = []
        element_path = ''
        
        for i, part in enumerate(parts):
            if part.strip() and 'iframe' in part.lower():
                frame_selectors.append('//' + part)
            else:
                # Rest is the element path
                element_path = '//' + '//'.join(parts[i:])
                break
        
        return frame_selectors, element_path
    
    @staticmethod
    async def resolve_frame_chain(
        page: Page, 
        frame_selectors: List[str]
    ) -> Optional[Frame]:
        """
        Resolve a chain of frame selectors to the final frame.
        
        Args:
            page: Starting page
            frame_selectors: List of frame selectors
            
        Returns:
            Final frame or None if not found
        """
        current_frame = page.main_frame
        
        for selector in frame_selectors:
            try:
                # Find iframe element in current frame
                iframe = await current_frame.query_selector(selector)
                if not iframe:
                    return None
                
                # Get the frame from the iframe element
                frame_element = await iframe.content_frame()
                if not frame_element:
                    return None
                    
                current_frame = frame_element
            except Exception as e:
                print(f"Error resolving frame chain: {e}")
                return None
        
        return current_frame


class NetworkInterceptor:
    """Provides network interception capabilities via CDP."""
    
    def __init__(self, session: CDPSession):
        self.session = session
        self.patterns = []
        self.enabled = False
        
    async def enable(self):
        """Enable network interception."""
        if not self.enabled:
            await self.session.send('Network.enable')
            self.enabled = True
    
    async def add_request_pattern(
        self, 
        url_pattern: str = '*',
        resource_type: Optional[str] = None,
        interception_stage: str = 'Request'
    ):
        """
        Add a request interception pattern.
        
        Args:
            url_pattern: URL pattern to match
            resource_type: Optional resource type filter
            interception_stage: 'Request' or 'HeadersReceived'
        """
        pattern = {
            'urlPattern': url_pattern,
            'interceptionStage': interception_stage
        }
        if resource_type:
            pattern['resourceType'] = resource_type
            
        self.patterns.append(pattern)
        await self._update_patterns()
    
    async def _update_patterns(self):
        """Update CDP with current patterns."""
        if self.enabled and self.patterns:
            await self.session.send('Network.setRequestInterception', {
                'patterns': self.patterns
            })
    
    async def continue_request(
        self, 
        interception_id: str,
        url: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        post_data: Optional[str] = None
    ):
        """Continue an intercepted request, optionally modifying it."""
        params = {'interceptionId': interception_id}
        if url:
            params['url'] = url
        if headers:
            params['headers'] = headers
        if post_data:
            params['postData'] = post_data
            
        await self.session.send('Network.continueInterceptedRequest', params)
    
    async def abort_request(self, interception_id: str, error_reason: str = 'Aborted'):
        """Abort an intercepted request."""
        await self.session.send('Network.continueInterceptedRequest', {
            'interceptionId': interception_id,
            'errorReason': error_reason
        })


class PerformanceMonitor:
    """Collects performance metrics via CDP."""
    
    def __init__(self, session: CDPSession):
        self.session = session
        self.enabled = False
        self.metrics = []
        
    async def enable(self):
        """Enable performance monitoring."""
        if not self.enabled:
            await self.session.send('Performance.enable')
            self.enabled = True
    
    async def get_metrics(self) -> Dict[str, float]:
        """Get current performance metrics."""
        if not self.enabled:
            await self.enable()
            
        result = await self.session.send('Performance.getMetrics')
        metrics = {}
        
        for metric in result.get('metrics', []):
            metrics[metric['name']] = metric['value']
            
        return metrics
    
    async def start_timeline(self):
        """Start recording timeline events."""
        await self.session.send('Tracing.start', {
            'categories': 'devtools.timeline',
            'options': 'sampling-frequency=100'
        })
    
    async def stop_timeline(self) -> List[Dict[str, Any]]:
        """Stop recording and get timeline events."""
        await self.session.send('Tracing.end')
        events = []
        
        # Collect trace events
        while True:
            result = await self.session.send('Tracing.getCategories')
            chunk = result.get('value', [])
            if not chunk:
                break
            events.extend(chunk)
            
        return events


class CDPManager:
    """Main manager for all CDP functionality."""
    
    def __init__(self):
        self.session_pool = CDPSessionPool()
        self.event_listener = CDPEventListener()
        self.batch_executor = CDPBatchExecutor()
        self.partial_tree_extractor = PartialTreeExtractor()
        self._interceptors: Dict[CDPSession, NetworkInterceptor] = {}
        self._monitors: Dict[CDPSession, PerformanceMonitor] = {}
        
    async def get_session(self, page: Page, frame: Optional[Frame] = None) -> CDPSession:
        """Get a CDP session from the pool."""
        return await self.session_pool.get_session(page, frame)
    
    async def execute(
        self, 
        session: CDPSession, 
        method: str, 
        params: Optional[Dict[str, Any]] = None,
        batch: bool = True
    ) -> Any:
        """Execute a CDP command, optionally batching."""
        # Check if session is still valid before executing
        if not await self.session_pool.is_session_valid(session):
            raise RuntimeError(f"CDP session is no longer valid for method {method}")
        
        if batch:
            return await self.batch_executor.execute(session, method, params)
        else:
            return await session.send(method, params or {})
    
    async def add_listener(
        self, 
        session: CDPSession, 
        event: str, 
        callback: Callable
    ):
        """Add a CDP event listener."""
        await self.event_listener.add_listener(session, event, callback)
    
    async def get_partial_tree(
        self, 
        session: CDPSession,
        node_id: Optional[str] = None,
        backend_node_id: Optional[int] = None,
        max_depth: int = 3
    ) -> List[Dict[str, Any]]:
        """Get a partial accessibility tree."""
        return await self.partial_tree_extractor.get_partial_tree(
            session, node_id, backend_node_id, max_depth
        )
    
    def get_network_interceptor(self, session: CDPSession) -> NetworkInterceptor:
        """Get or create a network interceptor for a session."""
        if session not in self._interceptors:
            self._interceptors[session] = NetworkInterceptor(session)
        return self._interceptors[session]
    
    def get_performance_monitor(self, session: CDPSession) -> PerformanceMonitor:
        """Get or create a performance monitor for a session."""
        if session not in self._monitors:
            self._monitors[session] = PerformanceMonitor(session)
        return self._monitors[session]
    
    async def cleanup(self):
        """Clean up resources."""
        await self.session_pool.cleanup()
        self.event_listener.clear()


# Global CDP manager instance
cdp_manager = CDPManager()