"""LLM-specific type definitions."""

from typing import Optional, Dict, Any, List, Union, Literal
from enum import Enum
from pydantic import BaseModel, Field


class LLMMessage(BaseModel):
    """Represents a message in LLM conversation."""
    role: Literal["system", "user", "assistant", "tool"]
    content: Union[str, List[Dict[str, Any]]]
    name: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None


class LLMTool(BaseModel):
    """Represents a tool/function available to the LLM."""
    type: Literal["function"] = "function"
    function: Dict[str, Any]


class LLMResponseFormat(BaseModel):
    """Response format specification."""
    type: Literal["text", "json_object", "json_schema"] = "text"
    json_schema: Optional[Dict[str, Any]] = None


class LLMOptions(BaseModel):
    """Options for LLM completion."""
    model: str
    messages: List[LLMMessage]
    temperature: float = 1.0
    max_tokens: Optional[int] = None
    top_p: Optional[float] = None
    frequency_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None
    stop: Optional[Union[str, List[str]]] = None
    tools: Optional[List[LLMTool]] = None
    tool_choice: Optional[Union[str, Dict[str, Any]]] = None
    response_format: Optional[LLMResponseFormat] = None
    seed: Optional[int] = None
    user: Optional[str] = None
    timeout: Optional[float] = None


class LLMUsageMetrics(BaseModel):
    """Token usage metrics from LLM."""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cache_creation_input_tokens: Optional[int] = None
    cache_read_input_tokens: Optional[int] = None


class LLMChoice(BaseModel):
    """A single choice from LLM response."""
    index: int
    message: LLMMessage
    finish_reason: Optional[str] = None
    logprobs: Optional[Dict[str, Any]] = None


class LLMResponse(BaseModel):
    """Complete response from LLM."""
    id: str
    object: str
    created: int
    model: str
    choices: List[LLMChoice]
    usage: Optional[LLMUsageMetrics] = None
    system_fingerprint: Optional[str] = None


class LLMProviderConfig(BaseModel):
    """Configuration for an LLM provider."""
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    organization: Optional[str] = None
    default_model: Optional[str] = None
    timeout: float = 60.0
    max_retries: int = 3
    headers: Dict[str, str] = Field(default_factory=dict)


class ModelInfo(BaseModel):
    """Information about a specific model."""
    name: str
    provider: str
    has_vision: bool = False
    max_tokens: Optional[int] = None
    supports_tools: bool = True
    supports_response_format: bool = True
    cost_per_1k_prompt_tokens: Optional[float] = None
    cost_per_1k_completion_tokens: Optional[float] = None


class ProviderType(str, Enum):
    """Supported LLM providers."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    CEREBRAS = "cerebras"
    GROQ = "groq"
    LANGCHAIN = "langchain"
    

class AnthropicCacheControl(BaseModel):
    """Cache control for Anthropic messages."""
    type: Literal["ephemeral"] = "ephemeral"
    ttl: Optional[int] = None


class AnthropicMessageBlock(BaseModel):
    """Content block for Anthropic messages."""
    type: Literal["text", "image", "tool_use", "tool_result"]
    text: Optional[str] = None
    source: Optional[Dict[str, Any]] = None  # For images
    id: Optional[str] = None  # For tool use
    name: Optional[str] = None  # For tool use
    input: Optional[Dict[str, Any]] = None  # For tool use
    content: Optional[Union[str, List[Dict[str, Any]]]] = None  # For tool result
    is_error: Optional[bool] = None  # For tool result
    cache_control: Optional[AnthropicCacheControl] = None


class GoogleSafetySettings(BaseModel):
    """Safety settings for Google AI."""
    category: str
    threshold: str


class GoogleGenerationConfig(BaseModel):
    """Generation config for Google AI."""
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    top_k: Optional[int] = None
    candidate_count: Optional[int] = None
    max_output_tokens: Optional[int] = None
    stop_sequences: Optional[List[str]] = None


