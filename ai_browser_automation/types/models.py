"""Core type definitions for AIBrowserAutomation."""

from typing import Union, Optional, List, Dict, Any, TypeVar, Generic, Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing_extensions import Annotated
from enum import Enum
from datetime import datetime


# Type variables
T = TypeVar('T')


class ActionType(str, Enum):
    """Supported browser action types."""
    CLICK = "click"
    FILL = "fill"
    TYPE = "type"
    PRESS = "press"
    SCROLL = "scroll"
    HOVER = "hover"
    DRAG = "drag"
    SCREENSHOT = "screenshot"
    WAIT = "wait"
    NAVIGATE = "navigate"


# For Pydantic v2, we'll use a simple type alias with validation
def validate_encoded_id(v: str) -> str:
    """Validate EncodedId format."""
    if not isinstance(v, str):
        raise TypeError('string required')
    if not v or '-' not in v:
        raise ValueError('must be in format "frameOrdinal-backendNodeId"')
    parts = v.split('-')
    if len(parts) != 2:
        raise ValueError('must contain exactly one hyphen')
    try:
        int(parts[0])
        int(parts[1])
    except ValueError:
        raise ValueError('both parts must be integers')
    return v


# Type alias for EncodedId
EncodedId = Annotated[str, Field(description="Encoded element ID in format: frameOrdinal-backendNodeId")]


class ObserveResult(BaseModel):
    """Result from an observe operation."""
    selector: str
    description: str
    backend_node_id: Optional[int] = None  # Maps to backendNodeId in TS
    method: Optional[str] = None  # Playwright method to use (e.g., 'fill', 'click')
    arguments: Optional[List[str]] = None  # Arguments for the method


class ActOptions(BaseModel):
    """Options for the act method."""
    action: Optional[Union[str, ActionType]] = None
    model_name: Optional[str] = None
    use_vision: bool = True
    strict: bool = False
    coordinate: Optional[tuple[float, float]] = None
    timeout: int = 30000
    wait_for_nav: bool = False
    variable_values: Optional[Dict[str, str]] = None


class ActResult(BaseModel):
    """Result from an act operation."""
    success: bool
    action: ActionType
    selector: Optional[str] = None
    coordinate: Optional[tuple[float, float]] = None
    description: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None


class ExtractOptions(BaseModel, Generic[T]):
    """Options for the extract method."""
    instruction: Optional[str] = None
    response_schema: Any  # Will be a Pydantic model class
    model_name: Optional[str] = None
    content_type: Literal["text", "dom", "all"] = "text"
    chunks_total: int = 1
    chunks_seen: int = 1
    timeout: int = 30000
    use_cache: bool = True


class ExtractResult(BaseModel, Generic[T]):
    """Result from an extract operation."""
    data: T
    metadata: Dict[str, Any] = Field(default_factory=dict)
    usage: Optional[Dict[str, Any]] = None


class ObserveOptions(BaseModel):
    """Options for the observe method."""
    instruction: Optional[str] = None
    model_name: Optional[str] = None  # Maps to modelName in TS
    model_client_options: Optional[Dict[str, Any]] = None  # Maps to modelClientOptions in TS
    dom_settle_timeout_ms: Optional[int] = None  # Maps to domSettleTimeoutMs in TS
    return_action: bool = True  # Whether to return action details - default True to match TS
    only_visible: Optional[bool] = None  # Deprecated, matches onlyVisible in TS
    draw_overlay: bool = False  # Maps to drawOverlay in TS
    iframes: Optional[bool] = None  # Whether to process iframes
    from_act: bool = False  # Internal flag for act method calls


class InitResult(BaseModel):
    """Result from AIBrowserAutomation initialization."""
    debugger_url: str
    session_url: Optional[str] = None
    browserbase_session_id: Optional[str] = None
    session_id: str
    context_id: Optional[str] = None


class ConstructorParams(BaseModel):
    """Parameters for AIBrowserAutomation constructor."""
    env: Literal["LOCAL", "BROWSERBASE"] = "LOCAL"
    verbose: int = 0
    debug_dom: bool = False
    headless: bool = False
    enable_caching: bool = False
    browser_args: List[str] = Field(default_factory=list)
    api_key: Optional[str] = None
    project_id: Optional[str] = None
    browser: Optional[Literal["chromium", "firefox", "webkit"]] = "chromium"
    model_name: str = "gpt-4o"
    model_client_options: Optional[Dict[str, Any]] = None
    experimental_features: bool = False


class AccessibilityNode(BaseModel):
    """Represents a node in the accessibility tree."""
    role: str
    name: Optional[str] = None
    description: Optional[str] = None
    value: Optional[str] = None
    checked: Optional[bool] = None
    pressed: Optional[bool] = None
    level: Optional[int] = None
    expanded: Optional[bool] = None
    disabled: Optional[bool] = None
    multiselectable: Optional[bool] = None
    readonly: Optional[bool] = None
    required: Optional[bool] = None
    selected: Optional[bool] = None
    focused: Optional[bool] = None
    children: List['AccessibilityNode'] = Field(default_factory=list)
    encoded_id: Optional[EncodedId] = None
    tag_name: Optional[str] = None


class AgentAction(BaseModel):
    """Represents an action taken by an agent."""
    type: ActionType
    coordinate: Optional[tuple[float, float]] = None
    text: Optional[str] = None
    direction: Optional[Literal["up", "down", "left", "right"]] = None
    timestamp: datetime = Field(default_factory=datetime.now)


class AgentResult(BaseModel):
    """Result from an agent execution."""
    actions: List[AgentAction]
    messages: List[Dict[str, Any]]
    usage: Dict[str, Any]
    completed: bool
    error: Optional[str] = None


class LLMUsage(BaseModel):
    """Token usage information from LLM calls."""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost: Optional[float] = None


class CacheEntry(BaseModel):
    """Represents a cache entry."""
    timestamp: int
    data: Any
    request_id: str
    ttl: Optional[int] = None


# Update forward references
AccessibilityNode.model_rebuild()