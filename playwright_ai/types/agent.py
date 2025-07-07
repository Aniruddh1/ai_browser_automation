"""Agent type definitions."""

from typing import Dict, Any, List, Optional, Literal, Union
from typing_extensions import TypedDict
from pydantic import BaseModel


class AgentAction(TypedDict, total=False):
    """Represents an action to be performed by the agent."""
    type: str
    # Click actions
    x: Optional[float]
    y: Optional[float]
    button: Optional[str]
    # Type/Fill actions
    text: Optional[str]
    selector: Optional[str]
    # Key actions
    keys: Optional[List[str]]
    key: Optional[str]
    # Scroll actions
    scroll_x: Optional[float]
    scroll_y: Optional[float]
    direction: Optional[str]
    amount: Optional[float]
    # Drag actions
    path: Optional[List[Dict[str, float]]]
    # Move actions
    coordinate: Optional[List[float]]
    # Function actions
    name: Optional[str]
    arguments: Optional[Dict[str, Any]]
    # Generic params
    params: Optional[Dict[str, Any]]
    # Other common fields
    description: Optional[str]
    target: Optional[str]
    url: Optional[str]
    timeout: Optional[int]
    success: Optional[bool]


class AgentUsageMetrics(TypedDict, total=False):
    """Usage metrics for agent execution."""
    input_tokens: int
    output_tokens: int
    inference_time_ms: int


# Response types for multi-step execution
class ResponseInputItem(TypedDict, total=False):
    """Input item for agent responses."""
    # For messages
    role: Optional[str]  # "user", "assistant", "system"
    content: Optional[Union[str, List[Dict[str, Any]]]]
    
    # For tool/computer call results
    type: Optional[str]  # "computer_call_output", "function_call_output", "tool_result"
    call_id: Optional[str]
    tool_use_id: Optional[str]
    output: Optional[Union[str, Dict[str, Any]]]
    acknowledged_safety_checks: Optional[List[Dict[str, str]]]


class StepResult(TypedDict):
    """Result of a single agent step."""
    actions: List[AgentAction]
    message: str
    completed: bool
    next_input_items: List[ResponseInputItem]
    response_id: Optional[str]  # For OpenAI
    usage: AgentUsageMetrics


class AgentResult(BaseModel):
    """Result of agent execution."""
    success: bool
    message: str
    actions: List[AgentAction]
    completed: bool
    metadata: Optional[Dict[str, Any]] = None
    usage: Optional[AgentUsageMetrics] = None


class AgentOptions(BaseModel):
    """Options for agent execution."""
    max_steps: int = 10
    auto_screenshot: bool = True
    wait_between_actions: int = 1000  # milliseconds
    context: Optional[str] = None


class AgentExecuteOptions(AgentOptions):
    """Options for executing an agent task."""
    instruction: str


AgentType = Literal["openai", "anthropic"]
AgentProviderType = Literal["openai", "anthropic"]


class AgentClientOptions(TypedDict, total=False):
    """Options for agent client configuration."""
    api_key: str
    organization: Optional[str]
    base_url: Optional[str]
    default_max_steps: Optional[int]


class AgentExecutionOptions(BaseModel):
    """Internal options for agent execution."""
    options: AgentExecuteOptions
    retries: int = 3


class AgentHandlerOptions(BaseModel):
    """Options for agent handler configuration."""
    model_name: str
    client_options: Optional[Dict[str, Any]] = None
    user_provided_instructions: Optional[str] = None
    agent_type: AgentType


class ActionExecutionResult(BaseModel):
    """Result of executing a single action."""
    success: bool
    error: Optional[str] = None
    data: Optional[Any] = None


# Tool/Computer use types
class ToolUseItem(TypedDict):
    """Tool use item for Anthropic."""
    type: Literal["tool_use"]
    id: str
    name: str
    input: Dict[str, Any]


class ResponseItem(TypedDict, total=False):
    """Generic response item."""
    type: str
    id: Optional[str]
    content: Optional[Any]


# Anthropic specific types
class AnthropicContentBlock(TypedDict):
    """Base content block for Anthropic messages."""
    type: str


class AnthropicTextBlock(AnthropicContentBlock):
    """Text content block for Anthropic."""
    type: Literal["text"]
    text: str


class AnthropicToolUse(AnthropicContentBlock):
    """Tool use content block for Anthropic."""
    type: Literal["tool_use"]
    id: str
    name: str
    input: Dict[str, Any]


class AnthropicMessage(TypedDict):
    """Anthropic message format."""
    role: str
    content: Union[str, List[AnthropicContentBlock]]


class AnthropicToolResult(AnthropicContentBlock):
    """Tool result content block for Anthropic."""
    type: Literal["tool_result"]
    tool_use_id: str
    content: str


# OpenAI specific types
class OpenAIAction(TypedDict):
    """OpenAI action format."""
    type: str


class ComputerCallItem(TypedDict):
    """Computer call item for OpenAI."""
    type: Literal["computer_call"]
    call_id: str
    action: OpenAIAction
    pending_safety_checks: Optional[List[Dict[str, str]]]


class FunctionCallItem(TypedDict):
    """Function call item for OpenAI."""
    type: Literal["function_call"]
    call_id: str
    name: str
    arguments: str