"""Base LLM client interface."""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, TYPE_CHECKING

from ..types import LLMMessage, LLMResponse, LLMUsageMetrics
from ..utils.logger import AIBrowserAutomationLogger

if TYPE_CHECKING:
    from ..cache import LLMCache
    from pydantic import BaseModel


class LLMClient(ABC):
    """
    Abstract base class for LLM clients.
    
    Defines the interface that all LLM provider clients must implement.
    """
    
    def __init__(
        self,
        model_name: str,
        api_key: Optional[str],
        logger: AIBrowserAutomationLogger,
        cache: Optional['LLMCache'] = None,
        **options: Any
    ):
        """
        Initialize LLM client.
        
        Args:
            model_name: Name of the model
            api_key: API key for the provider
            logger: Logger instance
            cache: Optional cache instance
            **options: Provider-specific options
        """
        self.model_name = model_name
        self.api_key = api_key
        self.logger = logger
        self.cache = cache
        self.options = options
        self.has_vision = self._determine_vision_capability(model_name)
    
    @abstractmethod
    async def create_chat_completion(
        self,
        messages: List[LLMMessage],
        temperature: float = 1.0,
        max_tokens: Optional[int] = None,
        response_model: Optional['BaseModel'] = None,
        **kwargs: Any
    ) -> LLMResponse:
        """
        Create a chat completion.
        
        Args:
            messages: List of messages
            temperature: Temperature for sampling
            max_tokens: Maximum tokens to generate
            response_model: Optional Pydantic model for structured output
            **kwargs: Provider-specific parameters
            
        Returns:
            LLM response
        """
        pass
    
    @abstractmethod
    async def generate_object(
        self,
        prompt: str,
        schema: 'BaseModel',
        temperature: float = 1.0,
        max_tokens: Optional[int] = None,
        **kwargs: Any
    ) -> Any:
        """
        Generate a structured object matching the schema.
        
        Args:
            prompt: Prompt text
            schema: Pydantic model class
            temperature: Temperature for sampling
            max_tokens: Maximum tokens to generate
            **kwargs: Provider-specific parameters
            
        Returns:
            Instance of the schema model
        """
        pass
    
    def _determine_vision_capability(self, model_name: str) -> bool:
        """
        Determine if the model has vision capabilities.
        
        Args:
            model_name: Model name
            
        Returns:
            True if model supports vision
        """
        vision_models = [
            "gpt-4-vision",
            "gpt-4o",
            "claude-3",
            "gemini-pro-vision",
            "gemini-1.5",
        ]
        
        return any(vm in model_name.lower() for vm in vision_models)
    
    async def _get_from_cache(self, cache_key: Dict[str, Any], request_id: str) -> Optional[Any]:
        """Get response from cache if available."""
        if self.cache:
            return await self.cache.get(cache_key, request_id)
        return None
    
    async def _save_to_cache(self, cache_key: Dict[str, Any], response: Any, request_id: str) -> None:
        """Save response to cache."""
        if self.cache:
            await self.cache.set(cache_key, response, request_id)
    
    def _build_cache_key(
        self,
        messages: List[LLMMessage],
        temperature: float,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Build cache key for the request."""
        # Convert messages to serializable format
        serializable_messages = [
            {
                "role": msg.role,
                "content": msg.content if isinstance(msg.content, str) else str(msg.content)
            }
            for msg in messages
        ]
        
        return {
            "model": self.model_name,
            "messages": serializable_messages,
            "temperature": temperature,
            **kwargs
        }