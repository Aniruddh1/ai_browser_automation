"""Base agent client implementation."""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Callable, Awaitable
from ..types.agent import (
    AgentType,
    AgentResult, 
    AgentExecutionOptions,
    AgentAction,
)


class AgentClient(ABC):
    """
    Abstract base class for agent clients.
    
    This provides a common interface for all agent implementations.
    """
    
    def __init__(
        self,
        agent_type: AgentType,
        model_name: str,
        user_provided_instructions: Optional[str] = None,
    ):
        """
        Initialize agent client.
        
        Args:
            agent_type: Type of agent (openai or anthropic)
            model_name: Model to use
            user_provided_instructions: Optional additional instructions
        """
        self.type = agent_type
        self.model_name = model_name
        self.user_provided_instructions = user_provided_instructions
        self.client_options: Dict[str, Any] = {}
        
        # Callbacks
        self._screenshot_provider: Optional[Callable[[], Awaitable[str]]] = None
        self._action_handler: Optional[Callable[[AgentAction], Awaitable[None]]] = None
        self._current_url: Optional[str] = None
        self._viewport: Optional[tuple[int, int]] = None
    
    @abstractmethod
    async def execute(self, options: AgentExecutionOptions) -> AgentResult:
        """
        Execute agent task.
        
        Args:
            options: Execution options
            
        Returns:
            Agent result
        """
        pass
    
    @abstractmethod
    async def capture_screenshot(self, options: Optional[Dict[str, Any]] = None) -> Any:
        """
        Capture a screenshot.
        
        Args:
            options: Screenshot options
            
        Returns:
            Screenshot data
        """
        pass
    
    def set_viewport(self, width: int, height: int) -> None:
        """
        Set viewport dimensions.
        
        Args:
            width: Viewport width
            height: Viewport height
        """
        self._viewport = (width, height)
    
    def set_current_url(self, url: str) -> None:
        """
        Set current page URL.
        
        Args:
            url: Current URL
        """
        self._current_url = url
    
    def set_screenshot_provider(self, provider: Callable[[], Awaitable[str]]) -> None:
        """
        Set screenshot provider callback.
        
        Args:
            provider: Async function that returns base64 screenshot
        """
        self._screenshot_provider = provider
    
    def set_action_handler(self, handler: Callable[[AgentAction], Awaitable[None]]) -> None:
        """
        Set action handler callback.
        
        Args:
            handler: Async function that executes actions
        """
        self._action_handler = handler