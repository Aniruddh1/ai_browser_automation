"""LLM provider factory and management."""

from typing import Dict, Any, Optional, TYPE_CHECKING
import os

from ..utils.logger import AIBrowserAutomationLogger
from ..core.errors import LLMProviderError, ConfigurationError

if TYPE_CHECKING:
    from .client import LLMClient


class LLMProvider:
    """
    Factory class for creating and managing LLM clients.
    
    Provides a unified interface for different LLM providers.
    """
    
    # Model to provider mapping
    MODEL_TO_PROVIDER = {
        # OpenAI models
        "gpt-4o": "openai",
        "gpt-4o-mini": "openai",
        "gpt-4-turbo": "openai",
        "gpt-4": "openai",
        "gpt-3.5-turbo": "openai",
        "gpt-4-vision-preview": "openai",
        "o1-preview": "openai",
        "o1-mini": "openai",
        "o3-mini": "openai",
        # Anthropic models
        "claude-3-opus": "anthropic",
        "claude-3-sonnet": "anthropic",
        "claude-3-haiku": "anthropic",
        "claude-3-5-sonnet": "anthropic",
        "claude-3.5-sonnet": "anthropic",
        "claude-2.1": "anthropic",
        "claude-2": "anthropic",
        # Google models - Stable
        "gemini-pro": "google",
        "gemini-pro-vision": "google",
        "gemini-2.5-pro": "google",
        "gemini-2.5-flash": "google",
        "gemini-2.0-flash": "google",
        "gemini-2.0-flash-lite": "google",
        "gemini-1.5-pro": "google",
        "gemini-1.5-flash": "google",
        "gemini-1.5-flash-8b": "google",
        # Google models - Preview/Experimental
        "gemini-2.5-flash-lite-preview-06-17": "google",
        "gemini-2.5-flash-preview-native-audio-dialog": "google",
        "gemini-2.5-flash-exp-native-audio-thinking-dialog": "google",
        "gemini-2.5-flash-preview-tts": "google",
        "gemini-2.5-pro-preview-tts": "google",
        "gemini-2.0-flash-preview-image-generation": "google",
        "gemini-2.0-flash-exp": "google",
        "gemini-live-2.5-flash-preview": "google",
        "gemini-2.0-flash-live-001": "google",
        # Google embedding models
        "text-embedding-004": "google",
        "embedding-001": "google",
        "gemini-embedding-exp-03-07": "google",
    }
    
    def __init__(
        self,
        logger: AIBrowserAutomationLogger,
        enable_caching: bool = False,
        default_model: Optional[str] = None,
        default_options: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize LLM provider.
        
        Args:
            logger: Logger instance
            enable_caching: Whether to enable response caching
            default_model: Default model to use
            default_options: Default options for clients
        """
        self.logger = logger
        self.enable_caching = enable_caching
        self.default_model = default_model or "gpt-4o"
        self.default_options = default_options or {}
        self._clients: Dict[str, 'LLMClient'] = {}
        
        # Import cache if needed
        if enable_caching:
            from ..cache import LLMCache
            self.cache = LLMCache(logger)
        else:
            self.cache = None
    
    def get_client(self, model_name: Optional[str] = None, **options: Any) -> 'LLMClient':
        """
        Get or create an LLM client for the specified model.
        
        Args:
            model_name: Model name (uses default if not specified)
            **options: Additional client options
            
        Returns:
            LLMClient instance
            
        Raises:
            LLMProviderError: If provider cannot be determined
            ConfigurationError: If configuration is invalid
        """
        model_name = model_name or self.default_model
        
        # Check if we already have a client for this model
        if model_name in self._clients:
            return self._clients[model_name]
        
        # Merge options with defaults
        client_options = {**self.default_options, **options}
        
        # Determine provider
        provider = self._get_provider_for_model(model_name)
        
        # Create client
        try:
            client = self._create_client(provider, model_name, client_options)
            self._clients[model_name] = client
            return client
        except Exception as e:
            raise LLMProviderError(provider, f"Failed to create client: {e}")
    
    def _get_provider_for_model(self, model_name: str) -> str:
        """
        Determine the provider for a given model.
        
        Args:
            model_name: Model name
            
        Returns:
            Provider name
            
        Raises:
            LLMProviderError: If provider cannot be determined
        """
        # Check for explicit provider format (provider/model)
        if "/" in model_name:
            return model_name.split("/", 1)[0]
        
        # Look up in mapping
        provider = self.MODEL_TO_PROVIDER.get(model_name)
        if not provider:
            raise LLMProviderError(
                "unknown",
                f"Cannot determine provider for model: {model_name}"
            )
        
        return provider
    
    def _create_client(
        self,
        provider: str,
        model_name: str,
        options: Dict[str, Any]
    ) -> 'LLMClient':
        """
        Create a client for the specified provider.
        
        Args:
            provider: Provider name
            model_name: Model name
            options: Client options
            
        Returns:
            LLMClient instance
            
        Raises:
            ConfigurationError: If configuration is invalid
        """
        # Get API key from options or environment
        api_key = options.get('api_key')
        if not api_key:
            env_var_map = {
                'openai': 'OPENAI_API_KEY',
                'anthropic': 'ANTHROPIC_API_KEY',
                'google': 'GOOGLE_API_KEY',
            }
            env_var = env_var_map.get(provider)
            if env_var:
                api_key = os.getenv(env_var)
        
        # Import and create appropriate client
        try:
            if provider == 'openai':
                # Check if API key is available
                if not api_key:
                    raise ValueError("OpenAI API key not found")
                    
                from .openai_client import OpenAIClient
                # Remove api_key from options if it exists to avoid duplicate
                clean_options = {k: v for k, v in options.items() if k != 'api_key'}
                return OpenAIClient(
                    model_name=model_name,
                    api_key=api_key,
                    logger=self.logger,
                    cache=self.cache,
                    **clean_options
                )
            elif provider == 'anthropic':
                # Check if API key is available
                if not api_key:
                    raise ValueError("Anthropic API key not found")
                    
                from .anthropic_client import AnthropicClient
                # Remove api_key from options if it exists to avoid duplicate
                clean_options = {k: v for k, v in options.items() if k != 'api_key'}
                return AnthropicClient(
                    model_name=model_name,
                    api_key=api_key,
                    logger=self.logger,
                    cache=self.cache,
                    **clean_options
                )
            elif provider == 'google':
                # Check if API key is available
                if not api_key:
                    raise ValueError("Google API key not found")
                    
                from .google_client import GoogleClient
                # Remove api_key from options if it exists to avoid duplicate
                clean_options = {k: v for k, v in options.items() if k != 'api_key'}
                return GoogleClient(
                    model_name=model_name,
                    api_key=api_key,
                    logger=self.logger,
                    cache=self.cache,
                    **clean_options
                )
            else:
                # Fall back to mock client for unknown providers
                from .mock_client import MockLLMClient
                self.logger.warn(
                    "llm:provider",
                    f"Using mock LLM client for unknown provider {provider}/{model_name}"
                )
                # Remove api_key from options if it exists to avoid duplicate
                clean_options = {k: v for k, v in options.items() if k != 'api_key'}
                return MockLLMClient(
                    model_name=model_name,
                    api_key=api_key,
                    logger=self.logger,
                    cache=self.cache,
                    **clean_options
                )
        except (ImportError, ValueError, Exception) as e:
            # If provider library not installed or API key missing, use mock
            from .mock_client import MockLLMClient
            self.logger.warn(
                "llm:provider",
                f"Cannot create {provider} client: {e}. Using mock client."
            )
            # Remove api_key from options if it exists to avoid duplicate
            clean_options = {k: v for k, v in options.items() if k != 'api_key'}
            return MockLLMClient(
                model_name=model_name,
                api_key=api_key,
                logger=self.logger,
                cache=self.cache,
                **clean_options
            )
    
    async def cleanup(self) -> None:
        """Clean up resources."""
        if self.cache:
            await self.cache.cleanup()
        
        # Clean up any client resources
        for client in self._clients.values():
            if hasattr(client, 'cleanup'):
                await client.cleanup()