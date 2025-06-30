"""Core AIBrowserAutomation components."""

from .ai_browser_automation import AIBrowserAutomation
from .context import AIBrowserAutomationContext
from .page import AIBrowserAutomationPage
from .errors import (
    AIBrowserAutomationError,
    AIBrowserAutomationNotInitializedError,
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
    "AIBrowserAutomation",
    "AIBrowserAutomationContext",
    "AIBrowserAutomationPage",
    # Errors
    "AIBrowserAutomationError",
    "AIBrowserAutomationNotInitializedError",
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