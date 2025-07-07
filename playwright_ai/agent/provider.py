"""Agent provider for creating agent clients."""

from typing import Dict, Any, Optional, TYPE_CHECKING
import logging

from ..types.agent import AgentType
from .client import AgentClient

if TYPE_CHECKING:
    from ..utils.logger import PlaywrightAILogger


class AgentProvider:
    """
    Factory class for creating agent clients.
    
    Provides a unified interface for different agent providers.
    """
    
    def __init__(self, logger: 'PlaywrightAILogger'):
        """
        Initialize agent provider.
        
        Args:
            logger: Logger instance
        """
        self.logger = logger
        self._clients: Dict[str, AgentClient] = {}
    
    def get_client(
        self,
        model_name: str,
        client_options: Optional[Dict[str, Any]] = None,
        user_provided_instructions: Optional[str] = None,
    ) -> AgentClient:
        """
        Get or create an agent client for the specified model.
        
        Args:
            model_name: Model name
            client_options: Client configuration options
            user_provided_instructions: Additional instructions
            
        Returns:
            Agent client instance
        """
        # Check cache
        cache_key = f"{model_name}_{id(client_options)}"
        if cache_key in self._clients:
            return self._clients[cache_key]
        
        # Map specific computer use models to their providers
        computer_use_models = {
            "computer-use-preview": "openai",
            "claude-3-5-sonnet-20240620": "anthropic",
            "claude-3-7-sonnet-20250219": "anthropic",
        }
        
        # Check if this is a specific computer use model
        if model_name in computer_use_models:
            agent_type = computer_use_models[model_name]
            
            if agent_type == "openai":
                from .openai_client import OpenAIAgentClient
                client = OpenAIAgentClient(
                    model_name=model_name,
                    client_options=client_options or {},
                    user_provided_instructions=user_provided_instructions,
                    logger=self.logger,
                )
            else:  # anthropic
                from .anthropic_client import AnthropicAgentClient
                client = AnthropicAgentClient(
                    model_name=model_name,
                    client_options=client_options or {},
                    user_provided_instructions=user_provided_instructions,
                    logger=self.logger,
                )
                
            self.logger.info(
                "agent:provider",
                f"Created {agent_type} agent client for computer use model: {model_name}"
            )
        else:
            # For non-computer use models, use demo client
            self.logger.info(
                "agent:provider",
                f"Model {model_name} is not a computer use model, using demo client"
            )
            
            from .intelligent_demo_client import IntelligentDemoClient
            client = IntelligentDemoClient(
                model_name=model_name,
                client_options=client_options or {},
                user_provided_instructions=user_provided_instructions,
                logger=self.logger,
            )
        
        # Cache and return
        self._clients[cache_key] = client
        return client
    
    def _get_agent_type(self, model_name: str) -> AgentType:
        """
        Determine agent type from model name.
        
        Args:
            model_name: Model name
            
        Returns:
            Agent type
        """
        model_lower = model_name.lower()
        
        # OpenAI models
        if any(name in model_lower for name in ["gpt", "o1", "o3"]):
            return "openai"
        
        # Anthropic models
        if "claude" in model_lower:
            return "anthropic"
        
        # Default to OpenAI
        self.logger.warn(
            "agent:provider",
            f"Unknown model {model_name}, defaulting to OpenAI agent"
        )
        return "openai"