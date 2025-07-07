"""
PlaywrightAI - AI-powered browser automation for Python.

PlaywrightAI extends Playwright with natural language capabilities,
allowing you to automate browsers using AI.
"""

__version__ = "0.1.0"

from .core import (
    PlaywrightAI,
    PlaywrightAIContext,
    PlaywrightAIPage,
    PlaywrightAIError,
    PlaywrightAINotInitializedError,
    BrowserNotAvailableError,
    PageNotAvailableError,
)

from .types import (
    ActOptions,
    ActResult,
    ExtractOptions,
    ExtractResult,
    ObserveOptions,
    ObserveResult,
    InitResult,
    ConstructorParams,
    ActionType,
)

__all__ = [
    # Version
    "__version__",
    # Main classes
    "PlaywrightAI",
    "PlaywrightAIContext",
    "PlaywrightAIPage",
    # Common types
    "ActOptions",
    "ActResult",
    "ExtractOptions",
    "ExtractResult",
    "ObserveOptions",
    "ObserveResult",
    "InitResult",
    "ConstructorParams",
    "ActionType",
    # Common errors
    "PlaywrightAIError",
    "PlaywrightAINotInitializedError",
    "BrowserNotAvailableError",
    "PageNotAvailableError",
]