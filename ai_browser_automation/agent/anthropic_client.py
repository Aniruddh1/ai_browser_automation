"""Anthropic agent client implementation."""

from typing import Dict, Any, Optional, TYPE_CHECKING, List
import logging
import base64
import time

from .base_multi_step_client import BaseMultiStepClient
from ..types.agent import (
    AgentType,
    AgentResult,
    AgentExecutionOptions,
    AgentAction,
    ResponseInputItem,
    StepResult,
    AgentUsageMetrics,
    ToolUseItem,
    AnthropicMessage,
    AnthropicContentBlock,
    AnthropicTextBlock,
    AnthropicToolResult,
)

if TYPE_CHECKING:
    from ..utils.logger import AIBrowserAutomationLogger


class AnthropicAgentClient(BaseMultiStepClient):
    """
    Anthropic agent client implementation with multi-step execution.
    
    Uses Anthropic's Claude computer use capabilities for autonomous task execution.
    """
    
    def __init__(
        self,
        model_name: str,
        client_options: Dict[str, Any],
        user_provided_instructions: Optional[str] = None,
        logger: Optional['AIBrowserAutomationLogger'] = None,
    ):
        """
        Initialize Anthropic agent client.
        
        Args:
            model_name: Model to use
            client_options: Client configuration
            user_provided_instructions: Additional instructions
            logger: Logger instance
        """
        super().__init__("anthropic", model_name, user_provided_instructions)
        self.client_options = client_options
        self._logger = logger or logging.getLogger(__name__)
        
        # State for multi-step execution
        self.last_message_id: Optional[str] = None
        self.current_viewport = {"width": 1280, "height": 720}
        self.thinking_budget: Optional[int] = client_options.get("thinking_budget")
        
        # Initialize Anthropic client if available
        try:
            import anthropic
            api_key = client_options.get("api_key") or "sk-ant-placeholder"
            self.client = anthropic.Anthropic(api_key=api_key)
            self._log_info(
                "agent:anthropic",
                "Anthropic client initialized for computer use"
            )
        except ImportError:
            self._log_info(
                "agent:anthropic",
                "Anthropic SDK not available, using placeholder mode"
            )
            self.client = None
    
    async def execute_step(
        self,
        input_items: List[ResponseInputItem],
        previous_response_id: Optional[str],
        logger: 'AIBrowserAutomationLogger'
    ) -> StepResult:
        """
        Execute a single step of the agent.
        """
        try:
            # Get response from the model
            result = await self.get_action(input_items)
            content = result.get("content", [])
            usage = result.get("usage", {})
            
            self._log_info(
                "agent:anthropic",
                f"Received response with {len(content)} content blocks"
            )
            
            # Extract actions and tool use items
            step_actions: List[AgentAction] = []
            tool_use_items: List[ToolUseItem] = []
            message = ""
            
            # Process content blocks
            for block in content:
                if block.get("type") == "tool_use":
                    # Tool use block
                    tool_use_item = ToolUseItem(
                        type="tool_use",
                        id=block["id"],
                        name=block["name"],
                        input=block["input"]
                    )
                    tool_use_items.append(tool_use_item)
                    
                    # Convert to action
                    action = self._convert_tool_use_to_action(tool_use_item)
                    if action:
                        step_actions.append(action)
                        
                elif block.get("type") == "text":
                    # Text block
                    message += block.get("text", "") + "\n"
            
            # Execute actions if handler is provided
            if self._action_handler and step_actions:
                for action in step_actions:
                    try:
                        self._log_info(
                            "agent:anthropic",
                            f"Executing action: {action['type']}"
                        )
                        await self._action_handler(action)
                    except Exception as e:
                        self._log_error(
                            "agent:anthropic",
                            f"Error executing action {action['type']}: {e}"
                        )
            
            # Create assistant message with all content blocks
            assistant_message: AnthropicMessage = {
                "role": "assistant",
                "content": content
            }
            
            # Build next input items
            next_input_items = list(input_items)
            next_input_items.append(assistant_message)
            
            # Generate tool results
            if tool_use_items:
                tool_results = await self.take_action(tool_use_items, logger)
                
                if tool_results:
                    # Wrap tool results in user message
                    user_tool_results: AnthropicMessage = {
                        "role": "user",
                        "content": tool_results
                    }
                    next_input_items.append(user_tool_results)
            
            # Step is completed only if no tool use
            completed = len(tool_use_items) == 0
            
            self._log_info(
                "agent:anthropic",
                f"Step processed {len(tool_use_items)} tool use items, completed: {completed}"
            )
            
            return StepResult(
                actions=step_actions,
                message=message.strip(),
                completed=completed,
                next_input_items=next_input_items,
                response_id=result.get("id"),
                usage=AgentUsageMetrics(
                    input_tokens=usage.get("input_tokens", 0),
                    output_tokens=usage.get("output_tokens", 0),
                    inference_time_ms=usage.get("inference_time_ms", 0)
                )
            )
            
        except Exception as e:
            self._log_error(
                "agent:anthropic",
                f"Error executing step: {e}"
            )
            raise
    
    def create_initial_input_items(self, instruction: str) -> List[ResponseInputItem]:
        """
        Create initial conversation items.
        """
        items: List[ResponseInputItem] = []
        
        # System message handled separately in Anthropic API
        items.append({
            "role": "system",
            "content": self.user_provided_instructions or ""
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
        Get next action from Anthropic's computer use API.
        """
        if not self.client:
            # Return empty response in placeholder mode
            return {
                "content": [],
                "id": None,
                "usage": {"input_tokens": 0, "output_tokens": 0, "inference_time_ms": 0}
            }
        
        try:
            # Prepare messages (skip system messages)
            messages: List[AnthropicMessage] = []
            system_content = ""
            
            for item in input_items:
                if item.get("role") == "system":
                    system_content = str(item.get("content", ""))
                elif item.get("role"):
                    messages.append(item)
            
            # Configure thinking if available
            thinking = None
            if self.thinking_budget:
                thinking = {
                    "type": "enabled",
                    "budget_tokens": self.thinking_budget
                }
            
            # Create request parameters
            request_params = {
                "model": self.model_name,
                "max_tokens": 4096,
                "messages": messages,
                "tools": [{
                    "type": "computer_20250124",
                    "name": "computer",
                    "display_width_px": self.current_viewport["width"],
                    "display_height_px": self.current_viewport["height"],
                    "display_number": 1
                }],
                "betas": ["computer-use-2025-01-24"]
            }
            
            # Add system parameter if provided
            if system_content:
                request_params["system"] = system_content
            
            # Add thinking if available
            if thinking:
                request_params["thinking"] = thinking
            
            # TODO: Use actual Anthropic computer use API when available
            # For now, return empty response
            start_time = time.time()
            
            return {
                "content": [],
                "id": None,
                "usage": {
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "inference_time_ms": int((time.time() - start_time) * 1000)
                }
            }
            
        except Exception as e:
            self._log_error(
                "agent:anthropic",
                f"Error getting action from Anthropic: {e}"
            )
            raise
    
    async def take_action(
        self,
        tool_use_items: List[ToolUseItem],
        logger: 'AIBrowserAutomationLogger'
    ) -> List[AnthropicContentBlock]:
        """
        Execute tool use items and prepare results.
        """
        results: List[AnthropicContentBlock] = []
        
        self._log_info(
            "agent:anthropic",
            f"Taking action on {len(tool_use_items)} tool use items"
        )
        
        for item in tool_use_items:
            try:
                self._log_info(
                    "agent:anthropic",
                    f"Processing tool use: {item['name']}, id: {item['id']}"
                )
                
                # For computer tool, capture screenshot and return
                if item["name"] == "computer":
                    action_type = item["input"].get("action", "")
                    self._log_info(
                        "agent:anthropic",
                        f"Computer action type: {action_type}"
                    )
                    
                    # Capture screenshot
                    screenshot = await self._capture_screenshot()
                    
                    # Create tool result with image
                    tool_result: AnthropicToolResult = {
                        "type": "tool_result",
                        "tool_use_id": item["id"],
                        "content": [{
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": screenshot.replace("data:image/png;base64,", "")
                            }
                        }]
                    }
                    
                    # Add current URL if available
                    if self._current_url:
                        tool_result["content"].append({
                            "type": "text",
                            "text": f"Current URL: {self._current_url}"
                        })
                    
                    results.append(tool_result)
                    
                else:
                    # Other tools return simple result
                    results.append({
                        "type": "tool_result",
                        "tool_use_id": item["id"],
                        "content": "Tool executed successfully"
                    })
                    
            except Exception as e:
                self._log_error(
                    "agent:anthropic",
                    f"Error executing tool use: {e}"
                )
                
                # Try to capture screenshot on error
                try:
                    if item["name"] == "computer":
                        screenshot = await self._capture_screenshot()
                        results.append({
                            "type": "tool_result",
                            "tool_use_id": item["id"],
                            "content": [{
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": screenshot.replace("data:image/png;base64,", "")
                                }
                            }, {
                                "type": "text",
                                "text": f"Error: {str(e)}"
                            }]
                        })
                    else:
                        results.append({
                            "type": "tool_result",
                            "tool_use_id": item["id"],
                            "content": f"Error: {str(e)}"
                        })
                except:
                    # If screenshot fails, just send error
                    results.append({
                        "type": "tool_result",
                        "tool_use_id": item["id"],
                        "content": f"Error: {str(e)}"
                    })
        
        return results
    
    def _convert_tool_use_to_action(self, item: ToolUseItem) -> Optional[AgentAction]:
        """
        Convert tool use item to action.
        """
        try:
            name = item["name"]
            input_data = item["input"]
            
            if name == "computer":
                # Computer actions
                action_type = input_data.get("action", "")
                
                if action_type == "screenshot":
                    return AgentAction(type="screenshot", **input_data)
                elif action_type == "click":
                    return AgentAction(
                        type="click",
                        x=input_data.get("x"),
                        y=input_data.get("y"),
                        button=input_data.get("button", "left"),
                        **input_data
                    )
                elif action_type == "type":
                    return AgentAction(
                        type="type",
                        text=input_data.get("text"),
                        **input_data
                    )
                elif action_type == "key" or action_type == "keypress":
                    return AgentAction(
                        type="key",
                        text=input_data.get("text"),
                        keys=input_data.get("keys"),
                        **input_data
                    )
                elif action_type == "scroll":
                    return AgentAction(
                        type="scroll",
                        x=input_data.get("x", 0),
                        y=input_data.get("y", 0),
                        scroll_x=input_data.get("scroll_x", 0),
                        scroll_y=input_data.get("scroll_y", 0),
                        **input_data
                    )
                elif action_type == "drag":
                    return AgentAction(
                        type="drag",
                        path=input_data.get("path"),
                        **input_data
                    )
                elif action_type == "move":
                    return AgentAction(
                        type="move",
                        x=input_data.get("x"),
                        y=input_data.get("y"),
                        **input_data
                    )
                else:
                    return AgentAction(type=action_type, **input_data)
                    
            elif name in ["str_replace_editor", "bash"]:
                # Editor or bash tools
                return AgentAction(
                    type=name,
                    params=input_data
                )
            
            self._log_info(
                "agent:anthropic",
                f"Unknown tool name: {name}"
            )
            return None
            
        except Exception as e:
            self._log_error(
                "agent:anthropic",
                f"Error converting tool use to action: {e}"
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
                    "agent:anthropic",
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