"""Core PlaywrightAI class implementation."""

import os
import uuid
from typing import Optional, Dict, Any, List, Union
from contextlib import asynccontextmanager

from playwright.async_api import async_playwright, Browser, BrowserContext, Playwright
from pydantic import ValidationError

from ..types import (
    ConstructorParams,
    InitResult,
    BrowserContextOptions,
    Viewport,
)
from ..utils.logger import configure_logging, PlaywrightAILogger
from .errors import (
    PlaywrightAIError,
    PlaywrightAINotInitializedError,
    MissingEnvironmentVariableError,
    BrowserNotAvailableError,
    ConfigurationError,
)


class PlaywrightAI:
    """
    Main PlaywrightAI class for AI-powered browser automation.
    
    This class provides the primary interface for creating browser contexts
    and pages with enhanced AI capabilities.
    """
    
    def __init__(
        self,
        env: str = "LOCAL",
        verbose: int = 0,
        debug_dom: bool = False,
        headless: bool = False,
        enable_caching: bool = False,
        browser_args: Optional[List[str]] = None,
        api_key: Optional[str] = None,
        project_id: Optional[str] = None,
        browser: str = "chromium",
        model_name: str = "gpt-4o",
        model_client_options: Optional[Dict[str, Any]] = None,
        experimental_features: bool = False,
        **kwargs: Any,
    ):
        """
        Initialize PlaywrightAI with configuration.
        
        Args:
            env: Environment to use ("LOCAL" or "BROWSERBASE")
            verbose: Logging verbosity (0-3)
            debug_dom: Enable DOM debugging
            headless: Run browser in headless mode
            enable_caching: Enable LLM response caching
            browser_args: Additional browser arguments
            api_key: API key for cloud browser service
            project_id: Project ID for cloud browser service
            browser: Browser type ("chromium", "firefox", "webkit")
            model_name: Default LLM model to use
            model_client_options: Options for LLM client
            experimental_features: Enable experimental features
            **kwargs: Additional options
        """
        # Validate and store configuration
        try:
            self.config = ConstructorParams(
                env=env,  # type: ignore
                verbose=verbose,
                debug_dom=debug_dom,
                headless=headless,
                enable_caching=enable_caching,
                browser_args=browser_args or [],
                api_key=api_key,
                project_id=project_id,
                browser=browser,  # type: ignore
                model_name=model_name,
                model_client_options=model_client_options,
                experimental_features=experimental_features,
            )
        except ValidationError as e:
            raise ConfigurationError(f"Invalid configuration: {e}")
        
        # Additional config from kwargs
        self.extra_config = kwargs
        
        # Set up logging
        self.logger = PlaywrightAILogger(
            configure_logging(verbose),
            verbose
        )
        
        # Initialize state
        self.initialized = False
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional['PlaywrightAIContext'] = None  # Forward reference
        self.session_id = str(uuid.uuid4())
        
        # Import here to avoid circular dependency
        from ..llm import LLMProvider
        from ..cache import LLMCache
        
        # Set up LLM provider
        self.llm_provider = LLMProvider(
            logger=self.logger,
            enable_caching=enable_caching,
            default_model=model_name,
            default_options=model_client_options,
        )
        
        # Set up cache if enabled
        self.cache: Optional[LLMCache] = None
        if enable_caching:
            self.cache = LLMCache(self.logger)
        
        self.logger.info(
            "playwright_ai:init",
            "PlaywrightAI initialized",
            env=env,
            model=model_name,
            session_id=self.session_id,
        )
    
    async def init(self) -> InitResult:
        """
        Initialize browser and return session information.
        
        Returns:
            InitResult with session details
            
        Raises:
            BrowserNotAvailableError: If browser fails to start
            MissingEnvironmentVariableError: If required env vars are missing
        """
        if self.initialized:
            self.logger.warn("playwright_ai:init", "Already initialized")
            return self._get_init_result()
        
        try:
            if self.config.env == "BROWSERBASE":
                await self._init_browserbase()
            else:
                await self._init_local()
            
            self.initialized = True
            result = self._get_init_result()
            
            self.logger.info(
                "playwright_ai:init",
                "Initialization complete",
                debugger_url=result.debugger_url,
            )
            
            return result
            
        except Exception as e:
            self.logger.error(
                "playwright_ai:init",
                f"Initialization failed: {e}",
                error=str(e),
            )
            raise BrowserNotAvailableError(str(e))
    
    async def _init_local(self) -> None:
        """Initialize local browser."""
        self.playwright = await async_playwright().start()
        
        # Prepare browser launch arguments
        browser_args = list(self.config.browser_args)
        if not any(arg.startswith("--disable-blink-features") for arg in browser_args):
            browser_args.append("--disable-blink-features=AutomationControlled")
        
        # Launch browser
        browser_type = getattr(self.playwright, self.config.browser)
        self.browser = await browser_type.launch(
            headless=self.config.headless,
            args=browser_args,
        )
        
        # Create context
        await self._create_context()
    
    async def _init_browserbase(self) -> None:
        """Initialize Browserbase cloud browser."""
        # Check for required environment variables
        api_key = self.config.api_key or os.getenv("BROWSERBASE_API_KEY")
        project_id = self.config.project_id or os.getenv("BROWSERBASE_PROJECT_ID")
        
        if not api_key:
            raise MissingEnvironmentVariableError("BROWSERBASE_API_KEY")
        if not project_id:
            raise MissingEnvironmentVariableError("BROWSERBASE_PROJECT_ID")
        
        # TODO: Implement Browserbase SDK integration
        # For now, fall back to local browser
        self.logger.warn(
            "playwright_ai:init",
            "Browserbase support not yet implemented, using local browser"
        )
        await self._init_local()
    
    async def _create_context(self) -> None:
        """Create browser context with PlaywrightAI enhancements."""
        if not self.browser:
            raise BrowserNotAvailableError("Browser not initialized")
        
        # Import here to avoid circular dependency
        from .context import PlaywrightAIContext
        
        # Prepare context options
        context_options: Dict[str, Any] = {
            "viewport": {"width": 1280, "height": 720},
            "user_agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        }
        
        # Apply extra options
        context_options.update(self.extra_config.get("context_options", {}))
        
        # Create Playwright context
        playwright_context = await self.browser.new_context(**context_options)
        
        # Inject DOM scripts into the context
        from ..dom.scripts import DOM_SCRIPTS
        guarded_script = f"""
        if (!window.__aiBrowserAutomationInjected) {{
            {DOM_SCRIPTS}
        }}
        """
        await playwright_context.add_init_script(guarded_script)
        
        # Wrap with PlaywrightAIContext
        self.context = PlaywrightAIContext(
            playwright_context,
            self,
        )
    
    async def page(self) -> 'PlaywrightAIPage':
        """
        Create a new page with AI capabilities.
        
        Returns:
            PlaywrightAIPage instance
            
        Raises:
            PlaywrightAINotInitializedError: If not initialized
        """
        if not self.initialized or not self.context:
            raise PlaywrightAINotInitializedError()
        
        return await self.context.new_page()
    
    @property
    def context_manager(self) -> 'PlaywrightAIContext':
        """
        Get the current context.
        
        Returns:
            PlaywrightAIContext instance
            
        Raises:
            PlaywrightAINotInitializedError: If not initialized
        """
        if not self.context:
            raise PlaywrightAINotInitializedError()
        return self.context
    
    async def close(self) -> None:
        """Clean up resources."""
        self.logger.info("playwright_ai:close", "Closing PlaywrightAI")
        
        # Clean up cache
        if self.cache:
            await self.cache.cleanup()
        
        # Close context
        if self.context:
            await self.context.close()
        
        # Close browser
        if self.browser:
            await self.browser.close()
        
        # Stop playwright
        if self.playwright:
            await self.playwright.stop()
        
        self.initialized = False
        self.logger.info("playwright_ai:close", "PlaywrightAI closed")
    
    def _get_init_result(self) -> InitResult:
        """Get initialization result."""
        debugger_url = "http://localhost:9222"  # Default for local
        
        if self.browser and hasattr(self.browser, "debugger_url"):
            debugger_url = self.browser.debugger_url
        
        return InitResult(
            debugger_url=debugger_url,
            session_url=None,  # TODO: Implement for Browserbase
            browserbase_session_id=None,  # TODO: Implement for Browserbase
            session_id=self.session_id,
            context_id=str(id(self.context)) if self.context else None,
        )
    
    async def __aenter__(self) -> 'PlaywrightAI':
        """Async context manager entry."""
        await self.init()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()
    
    def agent(self, **options: Any) -> 'PlaywrightAIAgent':
        """
        Create an agent for autonomous browser operations.
        
        Args:
            **options: Agent configuration options
            
        Returns:
            PlaywrightAIAgent instance
            
        Raises:
            PlaywrightAINotInitializedError: If not initialized
        """
        if not self.initialized:
            raise PlaywrightAINotInitializedError()
        
        # Import here to avoid circular dependency
        from ..agent import PlaywrightAIAgent
        
        return PlaywrightAIAgent(self, **options)