"""PlaywrightAIPage implementation with AI capabilities."""

import asyncio
import time
import weakref
from typing import Optional, Any, Dict, List, Union, TYPE_CHECKING, TypeVar
from playwright.async_api import Page, CDPSession

from ..types import (
    ActOptions,
    ActResult,
    ExtractOptions,
    ExtractResult,
    ObserveOptions,
    ObserveResult,
    EncodedId,
    FrameInfo,
)
from ..utils.logger import PlaywrightAILogger
from .errors import (
    PageNotAvailableError,
    CDPError,
    TimeoutError,
    UnsupportedOperationError,
)
from .cdp_integration import CDPIntegration

if TYPE_CHECKING:
    from .context import PlaywrightAIContext
    from pydantic import BaseModel
    from ..agent import AgentHandler

T = TypeVar('T')


class PlaywrightAIPage(CDPIntegration):
    """
    Enhanced page that wraps Playwright's Page with AI capabilities and CDP integration.
    
    Provides act(), extract(), and observe() methods for natural language
    browser automation, plus advanced CDP features like network interception,
    performance monitoring, and event listeners.
    """
    
    def __init__(self, page: Page, context: 'PlaywrightAIContext'):
        """
        Initialize PlaywrightAIPage.
        
        Args:
            page: Playwright Page instance
            context: Parent PlaywrightAIContext
        """
        self._page = page
        self._context = context
        self._logger = context.playwright_ai.logger.child(component="page")
        self._cdp_session: Optional[CDPSession] = None
        self._cdp_clients: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()  # CDP session cache
        
        # Frame tracking
        self._frame_ordinals: Dict[Optional[str], int] = {None: 0}  # None for main frame
        self._next_frame_ordinal = 1
        
        # Backend node ID mappings
        self._backend_node_id_to_xpath: Dict[int, str] = {}
        self._backend_node_id_to_tags: Dict[int, str] = {}
        
        # Script injection state
        self._scripts_injected = False
        
        # Page ID for debugging
        self._page_id = id(self)
        
        self._logger.debug(
            "page:init",
            "PlaywrightAIPage created",
            page_id=self._page_id,
        )
        
        # Set this as the active page
        context.active_page = self
        
        # Inject DOM scripts asynchronously
        asyncio.create_task(self._inject_dom_scripts())
    
    @property
    def context(self) -> 'PlaywrightAIContext':
        """Get parent context."""
        return self._context
    
    @property
    def playwright_ai(self):
        """Get parent PlaywrightAI instance."""
        return self._context.playwright_ai
    
    def ordinal_for_frame_id(self, frame_id: Optional[str]) -> int:
        """Get or assign ordinal for frame ID."""
        if frame_id in self._frame_ordinals:
            return self._frame_ordinals[frame_id]
        
        ordinal = self._next_frame_ordinal
        self._frame_ordinals[frame_id] = ordinal
        self._next_frame_ordinal += 1
        return ordinal
    
    def encode_with_frame_id(self, frame_id: Optional[str], backend_id: int) -> str:
        """Encode backend node ID with frame ordinal."""
        ordinal = self.ordinal_for_frame_id(frame_id)
        return f"{ordinal}-{backend_id}"
    
    def reset_frame_ordinals(self) -> None:
        """Reset frame ordinals mapping. Matches TypeScript's resetFrameOrdinals."""
        self._frame_ordinals = {None: 0}  # None for main frame
        self._next_frame_ordinal = 1
    
    async def _inject_dom_scripts(self) -> None:
        """
        Inject DOM helper scripts into the page.
        Matches TypeScript's ensureStagehandScript.
        """
        try:
            # Check if scripts are already injected
            injected = await self._page.evaluate("() => !!window.__aiBrowserAutomationInjected")
            if injected:
                return
            
            # Import the scripts
            from ..dom.scripts import DOM_SCRIPTS
            
            # Guard the script to prevent double injection
            guarded_script = f"""
if (!window.__aiBrowserAutomationInjected) {{
    {DOM_SCRIPTS}
}}
"""
            
            # Add init script for new pages/frames
            await self._page.add_init_script(guarded_script)
            
            # Execute on current page
            await self._page.evaluate(guarded_script)
            
            self._scripts_injected = True
            self._logger.debug("page:dom", "DOM helper scripts injected successfully")
            
        except Exception as e:
            error_str = str(e)
            # This specific error is expected during navigation
            if "Execution context was destroyed" in error_str and "navigation" in error_str:
                self._logger.warn(
                    "page:dom",
                    "DOM script injection interrupted by navigation (this is expected - scripts will be injected when page loads)",
                    error=error_str,
                )
            else:
                # Other errors are more concerning
                self._logger.error(
                    "page:dom",
                    "Failed to inject DOM helper scripts",
                    error=error_str,
                    trace=e.__traceback__ if hasattr(e, '__traceback__') else None,
                )
            # Don't throw - allow page to continue working since add_init_script ensures
            # scripts will be available when the page loads
    
    async def _ensure_dom_scripts(self) -> None:
        """Ensure DOM scripts are injected before operations that need them."""
        if not self._scripts_injected:
            await self._inject_dom_scripts()
    
    async def act(
        self,
        action_or_options: Union[str, ActOptions, ObserveResult],
    ) -> ActResult:
        """
        Perform an action using natural language or specific options.
        
        Args:
            action_or_options: Natural language instruction, ActOptions, or ObserveResult
            
        Returns:
            ActResult with action details
            
        Examples:
            await page.act("Click the login button")
            await page.act(ActOptions(action="fill", selector="#email"))
            await page.act(observe_result)  # From previous observe() call
        """
        self._logger.info(
            "page:act",
            "Executing action",
            action=str(action_or_options)[:100],
        )
        
        # Import handler here to avoid circular dependency
        from ..handlers import ActHandler
        
        # Create handler
        handler = ActHandler(
            logger=self._logger,
            llm_provider=self.playwright_ai.llm_provider,
        )
        
        # Ensure DOM scripts are injected
        await self._ensure_dom_scripts()
        
        # Execute action
        try:
            result = await handler.handle(self, action_or_options)
            
            self._logger.info(
                "page:act",
                "Action completed",
                success=result.success,
                action_type=result.action,
            )
            
            return result
            
        except Exception as e:
            self._logger.error(
                "page:act",
                f"Action failed: {e}",
                error=str(e),
            )
            raise
    
    async def extract(
        self,
        schema: 'BaseModel',
        instruction: Optional[str] = None,
        **options: Any,
    ) -> ExtractResult[T]:
        """
        Extract structured data from the page.
        
        Args:
            schema: Pydantic model defining the data structure
            instruction: Optional extraction instruction
            **options: Additional extraction options
            
        Returns:
            ExtractResult with extracted data
            
        Examples:
            class Product(BaseModel):
                name: str
                price: float
                
            result = await page.extract(Product)
            print(result.data.name, result.data.price)
        """
        self._logger.info(
            "page:extract",
            "Extracting data",
            schema=schema.__name__ if hasattr(schema, '__name__') else str(schema),
            instruction=instruction,
        )
        
        # Import handler here to avoid circular dependency
        from ..handlers import ExtractHandler
        
        # Create extraction options
        extract_options = ExtractOptions(
            response_schema=schema,
            instruction=instruction,
            **options,
        )
        
        # Create handler
        handler = ExtractHandler(
            logger=self._logger,
            llm_provider=self.playwright_ai.llm_provider,
        )
        
        # Ensure DOM scripts are injected
        await self._ensure_dom_scripts()
        
        # Execute extraction
        try:
            result = await handler.handle(self, extract_options)
            
            self._logger.info(
                "page:extract",
                "Extraction completed",
                has_data=result.data is not None,
            )
            
            return result
            
        except Exception as e:
            self._logger.error(
                "page:extract",
                f"Extraction failed: {e}",
                error=str(e),
            )
            raise
    
    async def observe(
        self,
        instruction_or_options: Optional[Union[str, ObserveOptions]] = None,
    ) -> List[ObserveResult]:
        """
        Observe available elements and actions on the page.
        
        Args:
            instruction_or_options: Either a string instruction or ObserveOptions object
            
        Returns:
            List of ObserveResult with found elements
            
        Examples:
            # Find all interactive elements
            elements = await page.observe()
            
            # Find specific elements with string
            buttons = await page.observe("Find all button elements")
            
            # Find elements with options
            elements = await page.observe(ObserveOptions(
                instruction="Find form inputs",
                draw_overlay=True
            ))
        """
        # Parse input to match TypeScript behavior
        if isinstance(instruction_or_options, str):
            observe_options = ObserveOptions(instruction=instruction_or_options)
        elif isinstance(instruction_or_options, ObserveOptions):
            observe_options = instruction_or_options
        elif instruction_or_options is None:
            observe_options = ObserveOptions()
        else:
            raise TypeError("observe() accepts either a string or ObserveOptions object")
            
        self._logger.info(
            "page:observe",
            "Observing page",
            instruction=observe_options.instruction,
        )
        
        # Import handler here to avoid circular dependency
        from ..handlers import ObserveHandler
        
        # Create handler
        handler = ObserveHandler(
            logger=self._logger,
            llm_provider=self.playwright_ai.llm_provider,
        )
        
        # Ensure DOM scripts are injected
        await self._ensure_dom_scripts()
        
        # Execute observation
        try:
            results = await handler.handle(self, observe_options)
            
            self._logger.info(
                "page:observe",
                "Observation completed",
                found_count=len(results),
            )
            
            return results
            
        except Exception as e:
            self._logger.error(
                "page:observe",
                f"Observation failed: {e}",
                error=str(e),
            )
            raise
    
    def agent(self, model_name: Optional[str] = None, **options: Any) -> 'AgentHandler':
        """
        Create an agent for autonomous task execution.
        
        Args:
            model_name: Optional model name override
            **options: Agent configuration options
            
        Returns:
            AgentHandler instance
            
        Examples:
            # Create agent with default model
            agent = page.agent()
            result = await agent.execute("Search for flights to Paris")
            
            # Create agent with specific model
            agent = page.agent("gpt-4o")
            result = await agent.execute({
                "instruction": "Book a hotel",
                "max_steps": 20,
                "context": "Prefer 4-star hotels"
            })
        """
        from ..agent import AgentHandler
        from ..types.agent import AgentHandlerOptions
        
        # Use provided model or default from playwright_ai
        actual_model = model_name or self.playwright_ai.config.model_name
        
        # Create handler options
        handler_options = AgentHandlerOptions(
            model_name=actual_model,
            client_options=options,
            agent_type="openai" if "gpt" in actual_model.lower() else "anthropic"
        )
        
        # Create and return handler
        return AgentHandler(
            playwright_ai=self.playwright_ai,
            ai_browser_automation_page=self,
            logger=self._logger,
            options=handler_options,
        )
    
    async def get_cdp_client(self, target: Optional[Union[Page, Any]] = None) -> CDPSession:
        """
        Get or create a CDP session for the given target.
        Matches TypeScript's getCDPClient method.
        
        Args:
            target: The Page or Frame to talk to (defaults to current page)
            
        Returns:
            CDPSession instance
        """
        if target is None:
            target = self._page
            
        # Check cache first
        cached = self._cdp_clients.get(target)
        if cached:
            return cached
            
        try:
            # Create new CDP session
            session = await self._page.context.new_cdp_session(target)
            self._cdp_clients[target] = session
            return session
        except Exception as err:
            # Fallback for same-process iframes
            error_msg = str(err)
            if "does not have a separate CDP session" in error_msg:
                # Re-use/create the top-level session instead
                root_session = await self.get_cdp_client(self._page)
                # Cache the alias so we don't try again for this frame
                self._cdp_clients[target] = root_session
                return root_session
            raise
    
    async def send_cdp(self, method: str, params: Optional[Dict[str, Any]] = None, target: Optional[Any] = None) -> Any:
        """
        Send a CDP command to the chosen DevTools target.
        Matches TypeScript's sendCDP method.
        
        Args:
            method: Any valid CDP method, e.g. "DOM.getDocument"
            params: Command parameters (optional)
            target: A Page or Frame. Defaults to the main page.
            
        Returns:
            CDP command result
        """
        if params is None:
            params = {}
            
        client = await self.get_cdp_client(target or self._page)
        return await client.send(method, params)
    
    async def enable_cdp(self, domain: str, target: Optional[Any] = None) -> None:
        """
        Enable a CDP domain (e.g. "Network" or "DOM") on the chosen target.
        Matches TypeScript's enableCDP method.
        
        Args:
            domain: CDP domain name
            target: Optional target (defaults to main page)
        """
        await self.send_cdp(f"{domain}.enable", {}, target)
    
    async def disable_cdp(self, domain: str, target: Optional[Any] = None) -> None:
        """
        Disable a CDP domain on the chosen target.
        Matches TypeScript's disableCDP method.
        
        Args:
            domain: CDP domain name
            target: Optional target (defaults to main page)
        """
        await self.send_cdp(f"{domain}.disable", {}, target)
    
    async def _ensure_cdp_session(self) -> CDPSession:
        """
        Ensure CDP session is available.
        
        Returns:
            CDPSession instance
            
        Raises:
            CDPError: If CDP session cannot be created
        """
        if not self._cdp_session:
            try:
                # Use new method
                self._cdp_session = await self.get_cdp_client()
                
                self._logger.debug(
                    "page:cdp",
                    "CDP session created",
                    session_id=id(self._cdp_session),
                )
            except Exception as e:
                raise CDPError("session_create", str(e))
        
        return self._cdp_session
    
    async def _wait_for_settled_dom(self, timeout_ms: Optional[int] = None) -> None:
        """
        Wait for DOM to settle (no network activity).
        Matches TypeScript's _waitForSettledDom implementation.
        
        Args:
            timeout_ms: Maximum time to wait in milliseconds
            
        Raises:
            TimeoutError: If DOM doesn't settle within timeout
        """
        timeout = timeout_ms or self.playwright_ai.config.dom_settle_timeout_ms or 30000
        
        # Get CDP session
        client = await self.get_cdp_client()
        
        # Check if document exists
        try:
            has_doc = bool(await self._page.title())
        except:
            has_doc = False
            
        if not has_doc:
            await self._page.wait_for_load_state("domcontentloaded")
        
        # Enable CDP domains
        await client.send('Network.enable')
        await client.send('Page.enable')
        await client.send('Target.setAutoAttach', {
            'autoAttach': True,
            'waitForDebuggerOnStart': False,
            'flatten': True  # Important for frames
        })
        
        # Track network requests
        inflight: set[str] = set()
        meta: Dict[str, Dict[str, Any]] = {}  # request_id -> {url, start}
        doc_by_frame: Dict[str, str] = {}  # frame_id -> request_id
        
        # Timers
        quiet_timer_handle = None
        stalled_sweep_handle = None
        
        def clear_quiet():
            nonlocal quiet_timer_handle
            if quiet_timer_handle:
                quiet_timer_handle.cancel()
                quiet_timer_handle = None
        
        def maybe_quiet():
            nonlocal quiet_timer_handle
            if len(inflight) == 0 and not quiet_timer_handle:
                quiet_timer_handle = asyncio.get_event_loop().call_later(0.5, resolve_done)
        
        def finish_req(request_id: str):
            if request_id not in inflight:
                return
            inflight.discard(request_id)
            meta.pop(request_id, None)
            # Remove from doc_by_frame if it's there
            for fid, rid in list(doc_by_frame.items()):
                if rid == request_id:
                    doc_by_frame.pop(fid, None)
            clear_quiet()
            maybe_quiet()
        
        # Event handlers
        def on_request_will_be_sent(params: Dict[str, Any]) -> None:
            # Skip WebSocket and EventSource
            if params.get('type') in ('WebSocket', 'EventSource'):
                return
                
            request_id = params.get('requestId', '')
            inflight.add(request_id)
            meta[request_id] = {
                'url': params.get('request', {}).get('url', ''),
                'start': time.time()
            }
            
            # Track document requests by frame
            if params.get('type') == 'Document' and params.get('frameId'):
                doc_by_frame[params['frameId']] = request_id
                
            clear_quiet()
        
        def on_loading_finished(params: Dict[str, Any]) -> None:
            finish_req(params.get('requestId', ''))
        
        def on_loading_failed(params: Dict[str, Any]) -> None:
            finish_req(params.get('requestId', ''))
            
        def on_request_served_from_cache(params: Dict[str, Any]) -> None:
            finish_req(params.get('requestId', ''))
            
        def on_response_received(params: Dict[str, Any]) -> None:
            # Handle data URLs
            if params.get('response', {}).get('url', '').startswith('data:'):
                finish_req(params.get('requestId', ''))
                
        def on_frame_stopped_loading(params: Dict[str, Any]) -> None:
            frame_id = params.get('frameId')
            if frame_id and frame_id in doc_by_frame:
                finish_req(doc_by_frame[frame_id])
        
        # Register listeners
        client.on('Network.requestWillBeSent', on_request_will_be_sent)
        client.on('Network.loadingFinished', on_loading_finished)
        client.on('Network.loadingFailed', on_loading_failed)
        client.on('Network.requestServedFromCache', on_request_served_from_cache)
        client.on('Network.responseReceived', on_response_received)
        client.on('Page.frameStoppedLoading', on_frame_stopped_loading)
        
        # Stalled request sweep timer
        async def stalled_sweep():
            while True:
                await asyncio.sleep(0.5)  # Run every 500ms
                now = time.time()
                for request_id, info in list(meta.items()):
                    if now - info['start'] > 2.0:  # 2 seconds
                        inflight.discard(request_id)
                        meta.pop(request_id, None)
                        self._logger.debug(
                            "page:dom",
                            "⏳ forcing completion of stalled iframe document",
                            url=info['url'][:120]
                        )
                maybe_quiet()
        
        # Create promise-like behavior using asyncio
        done_event = asyncio.Event()
        
        def resolve_done():
            done_event.set()
        
        # Start stalled sweep task
        stalled_sweep_task = asyncio.create_task(stalled_sweep())
        
        # Start with maybe_quiet check
        maybe_quiet()
        
        # Set up timeout guard
        async def timeout_guard():
            await asyncio.sleep(timeout / 1000)  # Convert ms to seconds
            if len(inflight) > 0:
                self._logger.debug(
                    "page:dom", 
                    "⚠️ DOM-settle timeout reached – network requests still pending",
                    count=len(inflight)
                )
            resolve_done()
        
        timeout_task = asyncio.create_task(timeout_guard())
        
        try:
            # Wait for done event
            await done_event.wait()
        finally:
            # Clean up
            client.remove_listener('Network.requestWillBeSent', on_request_will_be_sent)
            client.remove_listener('Network.loadingFinished', on_loading_finished)
            client.remove_listener('Network.loadingFailed', on_loading_failed)
            client.remove_listener('Network.requestServedFromCache', on_request_served_from_cache)
            client.remove_listener('Network.responseReceived', on_response_received)
            client.remove_listener('Page.frameStoppedLoading', on_frame_stopped_loading)
            
            # Cancel tasks
            if quiet_timer_handle:
                quiet_timer_handle.cancel()
            stalled_sweep_task.cancel()
            timeout_task.cancel()
            
            # Suppress cancellation errors
            try:
                await stalled_sweep_task
            except asyncio.CancelledError:
                pass
            try:
                await timeout_task
            except asyncio.CancelledError:
                pass
    
    async def _ensure_ai_automation_scripts(self) -> None:
        """Ensure PlaywrightAI helper scripts are injected."""
        if self._scripts_injected:
            return
        
        # TODO: Implement script injection
        # This will inject DOM helper functions into the page
        
        self._scripts_injected = True
    
    # Proxy methods to underlying Playwright page
    async def goto(self, url: str, **kwargs: Any) -> Any:
        """Navigate to URL."""
        self._logger.info("page:navigate", f"Navigating to {url}")
        return await self._page.goto(url, **kwargs)
    
    async def close(self, **kwargs: Any) -> None:
        """Close the page."""
        self._logger.info("page:close", "Closing page")
        await self._page.close(**kwargs)
    
    @property
    def url(self) -> str:
        """Get current URL."""
        return self._page.url
    
    async def title(self) -> str:
        """Get page title."""
        return await self._page.title()
    
    async def content(self) -> str:
        """Get page content."""
        return await self._page.content()
    
    async def screenshot(self, **kwargs: Any) -> bytes:
        """Take a screenshot."""
        return await self._page.screenshot(**kwargs)
    
    async def evaluate(self, expression: str, *args: Any) -> Any:
        """Evaluate JavaScript in the page."""
        return await self._page.evaluate(expression, *args)
    
    async def wait_for_load_state(self, state: str = "load", **kwargs: Any) -> None:
        """Wait for page load state."""
        await self._page.wait_for_load_state(state, **kwargs)
    
    async def wait_for_selector(self, selector: str, **kwargs: Any) -> Any:
        """Wait for selector."""
        return await self._page.wait_for_selector(selector, **kwargs)
    
    async def click(self, selector: str, **kwargs: Any) -> None:
        """Click an element."""
        await self._page.click(selector, **kwargs)
    
    async def fill(self, selector: str, value: str, **kwargs: Any) -> None:
        """Fill an input."""
        await self._page.fill(selector, value, **kwargs)
    
    async def type(self, selector: str, text: str, **kwargs: Any) -> None:
        """Type text."""
        await self._page.type(selector, text, **kwargs)
    
    async def press(self, selector: str, key: str, **kwargs: Any) -> None:
        """Press a key."""
        await self._page.press(selector, key, **kwargs)
    
    async def hover(self, selector: str, **kwargs: Any) -> None:
        """Hover over an element."""
        await self._page.hover(selector, **kwargs)
    
    async def focus(self, selector: str, **kwargs: Any) -> None:
        """Focus an element."""
        await self._page.focus(selector, **kwargs)
    
    def __getattr__(self, name: str) -> Any:
        """Proxy other attributes to Playwright page."""
        return getattr(self._page, name)
    
    def __repr__(self) -> str:
        """String representation."""
        return f"<PlaywrightAIPage id={self._page_id} url='{self.url}'>"