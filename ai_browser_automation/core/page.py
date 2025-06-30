"""AIBrowserAutomationPage implementation with AI capabilities."""

import asyncio
import time
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
from ..utils.logger import AIBrowserAutomationLogger
from .errors import (
    PageNotAvailableError,
    CDPError,
    TimeoutError,
    UnsupportedOperationError,
)
from .cdp_integration import CDPIntegration

if TYPE_CHECKING:
    from .context import AIBrowserAutomationContext
    from pydantic import BaseModel
    from ..agent import AgentHandler

T = TypeVar('T')


class AIBrowserAutomationPage(CDPIntegration):
    """
    Enhanced page that wraps Playwright's Page with AI capabilities and CDP integration.
    
    Provides act(), extract(), and observe() methods for natural language
    browser automation, plus advanced CDP features like network interception,
    performance monitoring, and event listeners.
    """
    
    def __init__(self, page: Page, context: 'AIBrowserAutomationContext'):
        """
        Initialize AIBrowserAutomationPage.
        
        Args:
            page: Playwright Page instance
            context: Parent AIBrowserAutomationContext
        """
        self._page = page
        self._context = context
        self._logger = context.ai_browser_automation.logger.child(component="page")
        self._cdp_session: Optional[CDPSession] = None
        
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
            "AIBrowserAutomationPage created",
            page_id=self._page_id,
        )
        
        # Set this as the active page
        context.active_page = self
    
    @property
    def context(self) -> 'AIBrowserAutomationContext':
        """Get parent context."""
        return self._context
    
    @property
    def ai_browser_automation(self):
        """Get parent AIBrowserAutomation instance."""
        return self._context.ai_browser_automation
    
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
            llm_provider=self.ai_browser_automation.llm_provider,
        )
        
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
            llm_provider=self.ai_browser_automation.llm_provider,
        )
        
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
            llm_provider=self.ai_browser_automation.llm_provider,
        )
        
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
        
        # Use provided model or default from ai_browser_automation
        actual_model = model_name or self.ai_browser_automation.config.model_name
        
        # Create handler options
        handler_options = AgentHandlerOptions(
            model_name=actual_model,
            client_options=options,
            agent_type="openai" if "gpt" in actual_model.lower() else "anthropic"
        )
        
        # Create and return handler
        return AgentHandler(
            ai_browser_automation=self.ai_browser_automation,
            ai_browser_automation_page=self,
            logger=self._logger,
            options=handler_options,
        )
    
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
                # Create CDP session
                client = await self._page.context.new_cdp_session(self._page)
                self._cdp_session = client
                
                self._logger.debug(
                    "page:cdp",
                    "CDP session created",
                    session_id=id(client),
                )
            except Exception as e:
                raise CDPError("session_create", str(e))
        
        return self._cdp_session
    
    async def _wait_for_settled_dom(self, timeout_ms: int = 30000) -> None:
        """
        Wait for DOM to settle (no network activity).
        
        Args:
            timeout_ms: Maximum time to wait in milliseconds
            
        Raises:
            TimeoutError: If DOM doesn't settle within timeout
        """
        self._logger.debug(
            "page:dom",
            "Waiting for DOM to settle",
            timeout_ms=timeout_ms,
        )
        
        # Get CDP session
        cdp = await self._ensure_cdp_session()
        
        # Track network requests
        pending_requests: set[str] = set()
        request_timestamps: Dict[str, float] = {}
        
        # Set up event handlers
        def on_request_will_be_sent(params: Dict[str, Any]) -> None:
            request_id = params.get('requestId', '')
            pending_requests.add(request_id)
            request_timestamps[request_id] = time.time()
        
        def on_loading_finished(params: Dict[str, Any]) -> None:
            request_id = params.get('requestId', '')
            pending_requests.discard(request_id)
            request_timestamps.pop(request_id, None)
        
        def on_loading_failed(params: Dict[str, Any]) -> None:
            request_id = params.get('requestId', '')
            pending_requests.discard(request_id)
            request_timestamps.pop(request_id, None)
        
        # Enable network domain
        await cdp.send('Network.enable')
        
        # Register listeners
        cdp.on('Network.requestWillBeSent', on_request_will_be_sent)
        cdp.on('Network.loadingFinished', on_loading_finished)
        cdp.on('Network.loadingFailed', on_loading_failed)
        
        try:
            # Wait for network quiet period
            start_time = time.time()
            quiet_start: Optional[float] = None
            quiet_period_ms = 500  # 500ms of no network activity
            
            while True:
                # Check timeout
                elapsed_ms = (time.time() - start_time) * 1000
                if elapsed_ms > timeout_ms:
                    raise TimeoutError("wait_for_settled_dom", timeout_ms)
                
                # Clean up stalled requests (> 30s old)
                current_time = time.time()
                stalled_requests = [
                    req_id for req_id, timestamp in request_timestamps.items()
                    if current_time - timestamp > 30
                ]
                for req_id in stalled_requests:
                    pending_requests.discard(req_id)
                    request_timestamps.pop(req_id, None)
                
                # Check if network is quiet
                if not pending_requests:
                    if quiet_start is None:
                        quiet_start = time.time()
                    elif (time.time() - quiet_start) * 1000 >= quiet_period_ms:
                        # Network has been quiet for required period
                        break
                else:
                    quiet_start = None
                
                # Small delay to prevent busy waiting
                await asyncio.sleep(0.1)
                
        finally:
            # Clean up listeners
            cdp.remove_listener('Network.requestWillBeSent', on_request_will_be_sent)
            cdp.remove_listener('Network.loadingFinished', on_loading_finished)
            cdp.remove_listener('Network.loadingFailed', on_loading_failed)
        
        self._logger.debug(
            "page:dom",
            "DOM settled",
            elapsed_ms=int((time.time() - start_time) * 1000),
        )
    
    async def _ensure_ai_automation_scripts(self) -> None:
        """Ensure AIBrowserAutomation helper scripts are injected."""
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
        return f"<AIBrowserAutomationPage id={self._page_id} url='{self.url}'>"