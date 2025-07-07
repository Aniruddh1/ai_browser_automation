"""CDP integration for PlaywrightAIPage."""

from typing import Optional, Callable, Dict, Any, List
import asyncio
from ..cdp import cdp_manager


class CDPIntegration:
    """Mixin class that adds CDP capabilities to PlaywrightAIPage."""
    
    async def add_cdp_listener(self, event: str, callback: Callable) -> None:
        """
        Add a CDP event listener.
        
        Args:
            event: CDP event name (e.g., 'Network.requestWillBeSent')
            callback: Function to call when event fires
            
        Example:
            async def on_request(params):
                print(f"Request: {params['request']['url']}")
            
            await page.add_cdp_listener('Network.requestWillBeSent', on_request)
        """
        session = await cdp_manager.get_session(self._page)
        await cdp_manager.add_listener(session, event, callback)
    
    async def enable_network_interception(
        self, 
        url_pattern: str = '*',
        resource_types: Optional[List[str]] = None
    ) -> None:
        """
        Enable network request interception.
        
        Args:
            url_pattern: URL pattern to intercept
            resource_types: Optional list of resource types to intercept
            
        Example:
            await page.enable_network_interception('**/api/*')
            
            # Set up handler
            async def handle_request(params):
                intercept_id = params['interceptionId']
                # Modify or abort request
                await interceptor.continue_request(intercept_id)
            
            await page.add_cdp_listener('Network.requestIntercepted', handle_request)
        """
        session = await cdp_manager.get_session(self._page)
        interceptor = cdp_manager.get_network_interceptor(session)
        
        await interceptor.enable()
        
        if resource_types:
            for resource_type in resource_types:
                await interceptor.add_request_pattern(url_pattern, resource_type)
        else:
            await interceptor.add_request_pattern(url_pattern)
    
    async def get_performance_metrics(self) -> Dict[str, float]:
        """
        Get performance metrics for the page.
        
        Returns:
            Dictionary of metric names to values
            
        Example metrics:
            - Timestamp
            - Documents
            - Frames
            - JSEventListeners
            - LayoutCount
            - RecalcStyleCount
            - LayoutDuration
            - RecalcStyleDuration
            - ScriptDuration
            - TaskDuration
            - JSHeapUsedSize
            - JSHeapTotalSize
        """
        session = await cdp_manager.get_session(self._page)
        monitor = cdp_manager.get_performance_monitor(session)
        return await monitor.get_metrics()
    
    async def start_performance_timeline(self) -> None:
        """Start recording performance timeline."""
        session = await cdp_manager.get_session(self._page)
        monitor = cdp_manager.get_performance_monitor(session)
        await monitor.start_timeline()
    
    async def stop_performance_timeline(self) -> List[Dict[str, Any]]:
        """Stop recording and get timeline events."""
        session = await cdp_manager.get_session(self._page)
        monitor = cdp_manager.get_performance_monitor(session)
        return await monitor.stop_timeline()
    
    async def execute_cdp_command(
        self, 
        method: str, 
        params: Optional[Dict[str, Any]] = None,
        batch: bool = True
    ) -> Any:
        """
        Execute a raw CDP command.
        
        Args:
            method: CDP method name
            params: Method parameters
            batch: Whether to batch this call
            
        Returns:
            Command result
            
        Example:
            # Get all cookies
            result = await page.execute_cdp_command('Network.getCookies')
            cookies = result['cookies']
        """
        session = await cdp_manager.get_session(self._page)
        return await cdp_manager.execute(session, method, params, batch)
    
    async def observe_with_partial_tree(
        self,
        instruction: Optional[str] = None,
        max_depth: int = 3
    ) -> List[Any]:
        """
        Observe elements using partial accessibility tree for better performance.
        
        Args:
            instruction: Observation instruction
            max_depth: Maximum tree depth to explore
            
        Returns:
            List of observed elements
        """
        # This would integrate with the observe handler
        # Implementation would use cdp_manager.get_partial_tree()
        from ..handlers import ObserveHandler
        
        # Temporarily enable partial trees
        original_setting = getattr(self, '_use_partial_trees', False)
        self._use_partial_trees = True
        self._partial_tree_depth = max_depth
        
        try:
            # Use normal observe but with partial tree settings
            return await self.observe(instruction)
        finally:
            self._use_partial_trees = original_setting
    
    async def monitor_console_logs(self, callback: Callable[[str, str], None]) -> None:
        """
        Monitor console logs via CDP.
        
        Args:
            callback: Function called with (level, message) for each log
            
        Example:
            async def log_handler(level, message):
                print(f"[{level}] {message}")
            
            await page.monitor_console_logs(log_handler)
        """
        async def console_handler(params):
            entry = params.get('entry', {})
            level = entry.get('level', 'log')
            text = entry.get('text', '')
            await callback(level, text) if asyncio.iscoroutinefunction(callback) else callback(level, text)
        
        await self.add_cdp_listener('Log.entryAdded', console_handler)
        
        # Enable Log domain
        session = await cdp_manager.get_session(self._page)
        await cdp_manager.execute(session, 'Log.enable')
    
    async def get_resource_tree(self) -> Dict[str, Any]:
        """
        Get the resource tree showing frame hierarchy.
        
        Returns:
            Resource tree structure
        """
        session = await cdp_manager.get_session(self._page)
        return await cdp_manager.execute(session, 'Page.getResourceTree')
    
    async def capture_snapshot(self) -> str:
        """
        Capture a snapshot of the current DOM.
        
        Returns:
            Serialized DOM snapshot
        """
        session = await cdp_manager.get_session(self._page)
        result = await cdp_manager.execute(session, 'Page.captureSnapshot', {
            'format': 'mhtml'
        })
        return result.get('data', '')
    
    async def emulate_network_conditions(
        self,
        offline: bool = False,
        latency: int = 0,
        download_throughput: int = -1,
        upload_throughput: int = -1
    ) -> None:
        """
        Emulate network conditions.
        
        Args:
            offline: Whether to emulate offline mode
            latency: Additional latency in ms
            download_throughput: Download speed in bytes/sec (-1 for no limit)
            upload_throughput: Upload speed in bytes/sec (-1 for no limit)
        """
        session = await cdp_manager.get_session(self._page)
        await cdp_manager.execute(session, 'Network.emulateNetworkConditions', {
            'offline': offline,
            'latency': latency,
            'downloadThroughput': download_throughput,
            'uploadThroughput': upload_throughput
        })