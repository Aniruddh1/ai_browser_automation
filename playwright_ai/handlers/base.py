"""Base handler class for all PlaywrightAI handlers."""

from abc import ABC, abstractmethod
from typing import TypeVar, Generic, Any, TYPE_CHECKING

from ..utils.logger import PlaywrightAILogger

if TYPE_CHECKING:
    from ..llm import LLMProvider
    from ..core.page import PlaywrightAIPage

# Type variable for handler return types
T = TypeVar('T')


class BaseHandler(ABC, Generic[T]):
    """
    Abstract base class for all handlers.
    
    Provides common functionality and interface for handler implementations.
    """
    
    def __init__(self, logger: PlaywrightAILogger, llm_provider: 'LLMProvider'):
        """
        Initialize base handler.
        
        Args:
            logger: Logger instance
            llm_provider: LLM provider for AI operations
        """
        self.logger = logger
        self.llm_provider = llm_provider
    
    @abstractmethod
    async def handle(self, page: 'PlaywrightAIPage', *args: Any, **kwargs: Any) -> T:
        """
        Handle the operation.
        
        Args:
            page: PlaywrightAIPage instance
            *args: Positional arguments
            **kwargs: Keyword arguments
            
        Returns:
            Handler-specific result
        """
        pass
    
    async def _take_screenshot(self, page: 'PlaywrightAIPage', full_page: bool = False) -> bytes:
        """
        Take a screenshot of the page.
        
        Args:
            page: PlaywrightAIPage instance
            full_page: Whether to capture full page
            
        Returns:
            Screenshot bytes
        """
        return await page.screenshot(full_page=full_page)
    
    async def _wait_for_load(self, page: 'PlaywrightAIPage', state: str = "domcontentloaded") -> None:
        """
        Wait for page to reach a certain load state.
        
        Args:
            page: PlaywrightAIPage instance
            state: Load state to wait for
        """
        await page.wait_for_load_state(state)
    
    def _log_debug(self, message: str, **kwargs: Any) -> None:
        """Log debug message with handler context."""
        handler_name = self.__class__.__name__
        self.logger.debug(f"handler:{handler_name}", message, **kwargs)
    
    def _log_info(self, message: str, **kwargs: Any) -> None:
        """Log info message with handler context."""
        handler_name = self.__class__.__name__
        self.logger.info(f"handler:{handler_name}", message, **kwargs)
    
    def _log_warning(self, message: str, **kwargs: Any) -> None:
        """Log warning message with handler context."""
        handler_name = self.__class__.__name__
        self.logger.warn(f"handler:{handler_name}", message, **kwargs)
    
    def _log_error(self, message: str, **kwargs: Any) -> None:
        """Log error message with handler context."""
        handler_name = self.__class__.__name__
        self.logger.error(f"handler:{handler_name}", message, **kwargs)