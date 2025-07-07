"""Core PlaywrightAI components."""

from .playwright_ai import PlaywrightAI
from .context import PlaywrightAIContext
from .page import PlaywrightAIPage
from .errors import (
    PlaywrightAIError,
    PlaywrightAINotInitializedError,
    MissingEnvironmentVariableError,
    BrowserNotAvailableError,
    PageNotAvailableError,
    ElementNotFoundError,
    ActionFailedError,
    ExtractionFailedError,
    LLMError,
    LLMProviderError,
    LLMResponseError,
    SchemaValidationError,
    CacheError,
    CDPError,
    TimeoutError,
    ConfigurationError,
    UnsupportedOperationError,
)

__all__ = [
    # Main classes
    "PlaywrightAI",
    "PlaywrightAIContext",
    "PlaywrightAIPage",
    # Errors
    "PlaywrightAIError",
    "PlaywrightAINotInitializedError",
    "MissingEnvironmentVariableError",
    "BrowserNotAvailableError",
    "PageNotAvailableError",
    "ElementNotFoundError",
    "ActionFailedError",
    "ExtractionFailedError",
    "LLMError",
    "LLMProviderError",
    "LLMResponseError",
    "SchemaValidationError",
    "CacheError",
    "CDPError",
    "TimeoutError",
    "ConfigurationError",
    "UnsupportedOperationError",
]