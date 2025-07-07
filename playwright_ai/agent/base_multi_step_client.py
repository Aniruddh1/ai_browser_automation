"""Base class for multi-step agent execution."""

from abc import abstractmethod
from typing import List, Optional, Dict, Any, TYPE_CHECKING
import logging

from .client import AgentClient
from ..types.agent import (
    AgentResult,
    AgentExecutionOptions,
    ResponseInputItem,
    StepResult,
    AgentUsageMetrics,
    AgentAction,
)

if TYPE_CHECKING:
    from ..utils.logger import PlaywrightAILogger


class LoggerMixin:
    """Mixin to handle logger compatibility."""
    
    def __init__(self, *args, logger=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._logger = logger or logging.getLogger(__name__)
    
    def _log_info(self, category: str, message: str, **kwargs) -> None:
        """Log info message compatible with both logger types."""
        if hasattr(self._logger, 'info'):
            # Check if it's a PlaywrightAILogger by checking method signature
            try:
                # Try PlaywrightAILogger style first
                import inspect
                sig = inspect.signature(self._logger.info)
                if len(sig.parameters) >= 2:
                    # Looks like PlaywrightAILogger
                    self._logger.info(category, message, **kwargs)
                else:
                    # Standard logger
                    self._logger.info(f"[{category}] {message}")
            except:
                # Fallback to standard logger format
                self._logger.info(f"[{category}] {message}")
    
    def _log_error(self, category: str, message: str, **kwargs) -> None:
        """Log error message compatible with both logger types."""
        if hasattr(self._logger, 'error'):
            # Check if it's a PlaywrightAILogger by checking method signature
            try:
                # Try PlaywrightAILogger style first
                import inspect
                sig = inspect.signature(self._logger.error)
                if len(sig.parameters) >= 2:
                    # Looks like PlaywrightAILogger
                    self._logger.error(category, message, **kwargs)
                else:
                    # Standard logger
                    self._logger.error(f"[{category}] {message}")
            except:
                # Fallback to standard logger format
                self._logger.error(f"[{category}] {message}")


class BaseMultiStepClient(LoggerMixin, AgentClient):
    """
    Base class for multi-step agent execution.
    
    Implements the common multi-step execution pattern used by
    OpenAI and Anthropic computer use APIs.
    """
    
    async def execute(self, options: AgentExecutionOptions) -> AgentResult:
        """
        Execute agent task with multi-step reasoning.
        
        Args:
            options: Execution options including instruction and logger
            
        Returns:
            Agent result with all actions and final status
        """
        instruction = options.options.instruction
        max_steps = options.options.max_steps or 10
        # Use internal logger
        logger = self._logger
        
        current_step = 0
        completed = False
        all_actions: List[AgentAction] = []
        messages: List[str] = []
        final_message = ""
        
        # Initialize conversation
        input_items = self.create_initial_input_items(instruction)
        previous_response_id: Optional[str] = None
        
        # Track total usage
        total_input_tokens = 0
        total_output_tokens = 0
        total_inference_time = 0
        
        self._log_info(
            "agent",
            f"Starting multi-step execution with instruction: {instruction}"
        )
        
        try:
            # Execute steps until completion or max steps reached
            while not completed and current_step < max_steps:
                self._log_info(
                    "agent",
                    f"Executing step {current_step + 1}/{max_steps}"
                )
                
                # Execute one step
                result = await self.execute_step(
                    input_items,
                    previous_response_id,
                    self._logger
                )
                
                # Accumulate usage metrics
                if result.get('usage'):
                    total_input_tokens += result['usage'].get('input_tokens', 0)
                    total_output_tokens += result['usage'].get('output_tokens', 0)
                    total_inference_time += result['usage'].get('inference_time_ms', 0)
                
                # Add actions to the list
                if result['actions']:
                    self._log_info(
                        "agent",
                        f"Step {current_step + 1} performed {len(result['actions'])} actions"
                    )
                    all_actions.extend(result['actions'])
                
                # Update completion status
                completed = result['completed']
                
                # Update state for next iteration
                input_items = result['next_input_items']
                previous_response_id = result.get('response_id')
                
                # Record message
                if result['message']:
                    messages.append(result['message'])
                    final_message = result['message']
                
                current_step += 1
            
            self._log_info(
                "agent",
                f"Multi-step execution completed: {completed}, "
                f"with {len(all_actions)} total actions performed"
            )
            
            # Return the final result
            return AgentResult(
                success=completed,
                message=final_message,
                actions=all_actions,
                completed=completed,
                usage=AgentUsageMetrics(
                    input_tokens=total_input_tokens,
                    output_tokens=total_output_tokens,
                    inference_time_ms=total_inference_time
                )
            )
            
        except Exception as e:
            error_message = str(e)
            self._log_error(
                "agent",
                f"Error during multi-step execution: {error_message}"
            )
            
            return AgentResult(
                success=False,
                message=f"Failed to execute task: {error_message}",
                actions=all_actions,
                completed=False,
                usage=AgentUsageMetrics(
                    input_tokens=total_input_tokens,
                    output_tokens=total_output_tokens,
                    inference_time_ms=total_inference_time
                )
            )
    
    @abstractmethod
    async def execute_step(
        self,
        input_items: List[ResponseInputItem],
        previous_response_id: Optional[str],
        logger: 'PlaywrightAILogger'
    ) -> StepResult:
        """
        Execute a single step of the agent.
        
        Args:
            input_items: Conversation history and previous results
            previous_response_id: ID of previous response (OpenAI only)
            logger: Logger instance
            
        Returns:
            Step result including actions, completion status, and next input items
        """
        pass
    
    @abstractmethod
    def create_initial_input_items(self, instruction: str) -> List[ResponseInputItem]:
        """
        Create initial conversation items.
        
        Args:
            instruction: User instruction
            
        Returns:
            Initial input items for first step
        """
        pass
    
    @abstractmethod
    async def get_action(
        self,
        input_items: List[ResponseInputItem],
        previous_response_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get next action from the model.
        
        Args:
            input_items: Current conversation state
            previous_response_id: Previous response ID (if applicable)
            
        Returns:
            Model response with actions/tool calls
        """
        pass
    
    @abstractmethod
    async def take_action(
        self,
        output: List[Any],
        logger: 'PlaywrightAILogger'
    ) -> List[ResponseInputItem]:
        """
        Execute actions and prepare results for next step.
        
        Args:
            output: Model output containing actions/tool calls
            logger: Logger instance
            
        Returns:
            Input items for next step (tool results, screenshots, etc.)
        """
        pass