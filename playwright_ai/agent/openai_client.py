"""OpenAI agent client implementation."""

from typing import Dict, Any, Optional, TYPE_CHECKING, List
import logging
import base64

from .base_multi_step_client import BaseMultiStepClient
from ..types.agent import (
    AgentType,
    AgentResult,
    AgentExecutionOptions,
    AgentAction,
    ResponseInputItem,
    StepResult,
    AgentUsageMetrics,
    ComputerCallItem,
    FunctionCallItem,
    ResponseItem,
)

if TYPE_CHECKING:
    from ..utils.logger import PlaywrightAILogger


class OpenAIAgentClient(BaseMultiStepClient):
    """
    OpenAI agent client implementation with multi-step execution.
    
    Uses OpenAI's computer use capabilities for autonomous task execution.
    """
    
    def __init__(
        self,
        model_name: str,
        client_options: Dict[str, Any],
        user_provided_instructions: Optional[str] = None,
        logger: Optional['PlaywrightAILogger'] = None,
    ):
        """
        Initialize OpenAI agent client.
        
        Args:
            model_name: Model to use
            client_options: Client configuration
            user_provided_instructions: Additional instructions
            logger: Logger instance
        """
        super().__init__("openai", model_name, user_provided_instructions)
        self.client_options = client_options
        self._logger = logger or logging.getLogger(__name__)
        
        # State for multi-step execution
        self.last_response_id: Optional[str] = None
        self.current_viewport = {"width": 1280, "height": 720}
        self.reasoning_items: Dict[str, ResponseItem] = {}
        self.environment = client_options.get("environment", "browser")
        
        # Initialize OpenAI client if available
        try:
            import openai
            api_key = client_options.get("api_key") or "sk-placeholder"
            self.client = openai.OpenAI(api_key=api_key)
            self._log_info(
                "agent:openai",
                "OpenAI client initialized for computer use"
            )
        except ImportError:
            self._log_info(
                "agent:openai",
                "OpenAI SDK not available, using placeholder mode"
            )
            self.client = None
    
    async def execute_step(
        self,
        input_items: List[ResponseInputItem],
        previous_response_id: Optional[str],
        logger: 'PlaywrightAILogger'
    ) -> StepResult:
        """
        Execute a single step of the agent.
        
        This coordinates the flow: Request → Get Action → Execute Action
        """
        try:
            # Get response from the model
            result = await self.get_action(input_items, previous_response_id)
            output = result.get("output", [])
            response_id = result.get("responseId", None)
            usage = result.get("usage", {})
            
            # Add any reasoning items to our map
            for item in output:
                if item.get("type") == "reasoning":
                    self.reasoning_items[item["id"]] = item
            
            # Extract actions from the output
            step_actions: List[AgentAction] = []
            for item in output:
                if item.get("type") == "computer_call" and self._is_computer_call_item(item):
                    action = self._convert_computer_call_to_action(item)
                    if action:
                        step_actions.append(action)
                elif item.get("type") == "function_call" and self._is_function_call_item(item):
                    action = self._convert_function_call_to_action(item)
                    if action:
                        step_actions.append(action)
            
            # Extract message text
            message = ""
            for item in output:
                if item.get("type") == "message":
                    content = item.get("content", [])
                    if isinstance(content, list):
                        for c in content:
                            if c.get("type") == "output_text" and c.get("text"):
                                message += c["text"] + "\n"
            
            # Take actions and get results
            next_input_items = await self.take_action(output, logger)
            
            # Check if completed
            completed = (
                len(output) == 0 or
                all(item.get("type") in ["message", "reasoning"] for item in output)
            )
            
            return StepResult(
                actions=step_actions,
                message=message.strip(),
                completed=completed,
                next_input_items=next_input_items,
                response_id=response_id,
                usage=AgentUsageMetrics(
                    input_tokens=usage.get("input_tokens", 0),
                    output_tokens=usage.get("output_tokens", 0),
                    inference_time_ms=usage.get("inference_time_ms", 0)
                )
            )
            
        except Exception as e:
            self._log_error(
                "agent:openai",
                f"Error executing step: {e}"
            )
            raise
    
    def create_initial_input_items(self, instruction: str) -> List[ResponseInputItem]:
        """
        Create initial conversation items.
        """
        items: List[ResponseInputItem] = []
        
        if self.user_provided_instructions:
            items.append({
                "role": "system",
                "content": self.user_provided_instructions
            })
        
        items.append({
            "role": "user",
            "content": instruction
        })
        
        return items
    
    async def get_action(
        self,
        input_items: List[ResponseInputItem],
        previous_response_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get next action from OpenAI's computer use API.
        """
        if not self.client:
            # Return empty response in placeholder mode
            return {
                "output": [],
                "responseId": None,
                "usage": {"input_tokens": 0, "output_tokens": 0, "inference_time_ms": 0}
            }
        
        try:
            # Create request parameters
            request_params = {
                "model": self.model_name,
                "tools": [{
                    "type": "computer_use_preview",
                    "display_width": self.current_viewport["width"],
                    "display_height": self.current_viewport["height"],
                    "environment": self.environment
                }],
                "input": input_items,
                "truncation": "auto"
            }
            
            # Add previous response ID if available
            if previous_response_id:
                request_params["previous_response_id"] = previous_response_id
            
            # TODO: Use actual OpenAI computer use API when available
            # For now, return empty response
            return {
                "output": [],
                "responseId": None,
                "usage": {"input_tokens": 0, "output_tokens": 0, "inference_time_ms": 0}
            }
            
        except Exception as e:
            self._log_error(
                "agent:openai",
                f"Error getting action from OpenAI: {e}"
            )
            raise
    
    async def take_action(
        self,
        output: List[Any],
        logger: 'PlaywrightAILogger'
    ) -> List[ResponseInputItem]:
        """
        Execute actions and prepare results for next step.
        """
        next_input_items: List[ResponseInputItem] = []
        
        # Process each output item
        for item in output:
            if item.get("type") == "computer_call" and self._is_computer_call_item(item):
                # Execute the action
                try:
                    action = self._convert_computer_call_to_action(item)
                    
                    if action and self._action_handler:
                        await self._action_handler(action)
                    
                    # Capture a screenshot
                    screenshot = await self._capture_screenshot()
                    
                    # Create computer_call_output for next request
                    output_item: ResponseInputItem = {
                        "type": "computer_call_output",
                        "call_id": item["call_id"],
                        "output": {
                            "type": "input_image",
                            "image_url": screenshot
                        }
                    }
                    
                    # Add current URL if available
                    if self._current_url:
                        output_item["output"]["current_url"] = self._current_url
                    
                    # Add safety checks if needed
                    if item.get("pending_safety_checks"):
                        output_item["acknowledged_safety_checks"] = item["pending_safety_checks"]
                    
                    next_input_items.append(output_item)
                    
                except Exception as e:
                    # Handle errors with screenshot
                    try:
                        screenshot = await self._capture_screenshot()
                        error_output: ResponseInputItem = {
                            "type": "computer_call_output",
                            "call_id": item["call_id"],
                            "output": {
                                "type": "input_image",
                                "image_url": screenshot,
                                "error": str(e)
                            }
                        }
                        next_input_items.append(error_output)
                    except:
                        # If screenshot fails, just send error
                        next_input_items.append({
                            "type": "computer_call_output",
                            "call_id": item["call_id"],
                            "output": f"Error: {str(e)}"
                        })
                        
            elif item.get("type") == "function_call" and self._is_function_call_item(item):
                # Execute function
                try:
                    action = self._convert_function_call_to_action(item)
                    
                    if action and self._action_handler:
                        await self._action_handler(action)
                    
                    next_input_items.append({
                        "type": "function_call_output",
                        "call_id": item["call_id"],
                        "output": "success"
                    })
                    
                except Exception as e:
                    next_input_items.append({
                        "type": "function_call_output",
                        "call_id": item["call_id"],
                        "output": f"Error: {str(e)}"
                    })
        
        return next_input_items
    
    def _is_computer_call_item(self, item: Dict[str, Any]) -> bool:
        """Check if item is a computer call."""
        return (
            item.get("type") == "computer_call" and
            "call_id" in item and
            "action" in item and
            isinstance(item["action"], dict)
        )
    
    def _is_function_call_item(self, item: Dict[str, Any]) -> bool:
        """Check if item is a function call."""
        return (
            item.get("type") == "function_call" and
            "call_id" in item and
            "name" in item and
            "arguments" in item
        )
    
    def _convert_computer_call_to_action(self, call: Dict[str, Any]) -> Optional[AgentAction]:
        """Convert computer call to action."""
        action = call.get("action", {})
        
        # Spread action properties directly
        return AgentAction(
            type=action.get("type", ""),
            **action
        )
    
    def _convert_function_call_to_action(self, call: Dict[str, Any]) -> Optional[AgentAction]:
        """Convert function call to action."""
        try:
            import json
            args = json.loads(call.get("arguments", "{}"))
            
            return AgentAction(
                type=call["name"],
                params=args
            )
        except Exception as e:
            self._log_error(
                "agent:openai",
                f"Error parsing function call arguments: {e}"
            )
            return None
    
    async def _capture_screenshot(self) -> str:
        """Capture screenshot and return as data URL."""
        if self._screenshot_provider:
            try:
                base64_image = await self._screenshot_provider()
                return f"data:image/png;base64,{base64_image}"
            except Exception as e:
                self._log_error(
                    "agent:openai",
                    f"Error capturing screenshot: {e}"
                )
                raise
        
        # Return placeholder if no provider
        return "data:image/png;base64,placeholder"
    
    async def capture_screenshot(self, options: Optional[Dict[str, Any]] = None) -> str:
        """
        Capture a screenshot.
        
        Args:
            options: Screenshot options
            
        Returns:
            Screenshot data URL
        """
        if options and options.get("base64Image"):
            return f"data:image/png;base64,{options['base64Image']}"
        
        return await self._capture_screenshot()
    
    def set_viewport(self, width: int, height: int) -> None:
        """Set viewport dimensions."""
        super().set_viewport(width, height)
        self.current_viewport = {"width": width, "height": height}