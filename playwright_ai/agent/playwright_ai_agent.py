"""Main PlaywrightAIAgent class for agent operations."""

from typing import Union, TYPE_CHECKING
import logging

from ..types.agent import AgentExecuteOptions, AgentResult, AgentExecutionOptions
from .client import AgentClient

if TYPE_CHECKING:
    from ..utils.logger import PlaywrightAILogger


class PlaywrightAIAgent:
    """
    Main interface for agent operations in PlaywrightAI.
    
    This class provides methods for executing tasks with an agent.
    """
    
    def __init__(
        self,
        client: AgentClient,
        logger: 'PlaywrightAILogger'
    ):
        """
        Initialize PlaywrightAIAgent.
        
        Args:
            client: Agent client implementation
            logger: Logger instance
        """
        self.client = client
        self.logger = logger
    
    async def execute(
        self,
        options_or_instruction: Union[AgentExecuteOptions, str]
    ) -> AgentResult:
        """
        Execute an agent task.
        
        Args:
            options_or_instruction: Either full options or just instruction string
            
        Returns:
            Agent execution result
        """
        # Convert string to options if needed
        if isinstance(options_or_instruction, str):
            options = AgentExecuteOptions(instruction=options_or_instruction)
        else:
            options = options_or_instruction
        
        self.logger.info(
            "agent",
            f"Executing agent task: {options.instruction}",
        )
        
        # Create execution options
        execution_options = AgentExecutionOptions(
            options=options,
            retries=3,
        )
        
        # Execute through client
        return await self.client.execute(execution_options)
    
    def get_model_name(self) -> str:
        """Get the model name being used."""
        return self.client.model_name
    
    def get_agent_type(self) -> str:
        """Get the agent type."""
        return self.client.type