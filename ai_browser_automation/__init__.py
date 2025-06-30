"""
AIBrowserAutomation - AI-powered browser automation for Python.

AIBrowserAutomation extends Playwright with natural language capabilities,
allowing you to automate browsers using AI.
"""

__version__ = "0.1.0"

from .core import (
    AIBrowserAutomation,
    AIBrowserAutomationContext,
    AIBrowserAutomationPage,
    AIBrowserAutomationError,
    AIBrowserAutomationNotInitializedError,
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
    "AIBrowserAutomation",
    "AIBrowserAutomationContext",
    "AIBrowserAutomationPage",
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
    "AIBrowserAutomationError",
    "AIBrowserAutomationNotInitializedError",
    "BrowserNotAvailableError",
    "PageNotAvailableError",
]