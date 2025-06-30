"""Custom exception hierarchy for AIBrowserAutomation."""

from typing import Optional, Any, Dict


class AIBrowserAutomationError(Exception):
    """Base exception for all AIBrowserAutomation errors."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class AIBrowserAutomationNotInitializedError(AIBrowserAutomationError):
    """Raised when AIBrowserAutomation methods are called before initialization."""
    
    def __init__(self):
        super().__init__(
            "AIBrowserAutomation not initialized. Call init() before using other methods.",
            {"error_code": "NOT_INITIALIZED"}
        )


class MissingEnvironmentVariableError(AIBrowserAutomationError):
    """Raised when required environment variables are missing."""
    
    def __init__(self, variable_name: str):
        super().__init__(
            f"Missing required environment variable: {variable_name}",
            {"variable": variable_name, "error_code": "MISSING_ENV_VAR"}
        )


class BrowserNotAvailableError(AIBrowserAutomationError):
    """Raised when browser connection fails."""
    
    def __init__(self, reason: str):
        super().__init__(
            f"Browser not available: {reason}",
            {"reason": reason, "error_code": "BROWSER_NOT_AVAILABLE"}
        )


class PageNotAvailableError(AIBrowserAutomationError):
    """Raised when page operations fail."""
    
    def __init__(self, reason: str):
        super().__init__(
            f"Page not available: {reason}",
            {"reason": reason, "error_code": "PAGE_NOT_AVAILABLE"}
        )


class ElementNotFoundError(AIBrowserAutomationError):
    """Raised when element cannot be found."""
    
    def __init__(self, selector: str, instruction: Optional[str] = None):
        message = f"Element not found: {selector}"
        if instruction:
            message = f"Element not found for instruction: {instruction}"
        super().__init__(
            message,
            {"selector": selector, "instruction": instruction, "error_code": "ELEMENT_NOT_FOUND"}
        )


class ActionFailedError(AIBrowserAutomationError):
    """Raised when an action fails to execute."""
    
    def __init__(self, action: str, reason: str):
        super().__init__(
            f"Action '{action}' failed: {reason}",
            {"action": action, "reason": reason, "error_code": "ACTION_FAILED"}
        )


class ExtractionFailedError(AIBrowserAutomationError):
    """Raised when data extraction fails."""
    
    def __init__(self, reason: str, schema: Optional[Any] = None):
        super().__init__(
            f"Extraction failed: {reason}",
            {"reason": reason, "schema": str(schema), "error_code": "EXTRACTION_FAILED"}
        )


class LLMError(AIBrowserAutomationError):
    """Base class for LLM-related errors."""
    pass


class LLMProviderError(LLMError):
    """Raised when LLM provider operations fail."""
    
    def __init__(self, provider: str, reason: str):
        super().__init__(
            f"LLM provider '{provider}' error: {reason}",
            {"provider": provider, "reason": reason, "error_code": "LLM_PROVIDER_ERROR"}
        )


class LLMResponseError(LLMError):
    """Raised when LLM response is invalid or cannot be parsed."""
    
    def __init__(self, reason: str, response: Optional[Any] = None):
        super().__init__(
            f"Invalid LLM response: {reason}",
            {"reason": reason, "response": str(response), "error_code": "LLM_RESPONSE_ERROR"}
        )


class SchemaValidationError(AIBrowserAutomationError):
    """Raised when schema validation fails."""
    
    def __init__(self, reason: str, data: Optional[Any] = None):
        super().__init__(
            f"Schema validation failed: {reason}",
            {"reason": reason, "data": str(data), "error_code": "SCHEMA_VALIDATION_ERROR"}
        )


class CacheError(AIBrowserAutomationError):
    """Raised when cache operations fail."""
    
    def __init__(self, operation: str, reason: str):
        super().__init__(
            f"Cache {operation} failed: {reason}",
            {"operation": operation, "reason": reason, "error_code": "CACHE_ERROR"}
        )


class CDPError(AIBrowserAutomationError):
    """Raised when Chrome DevTools Protocol operations fail."""
    
    def __init__(self, command: str, reason: str):
        super().__init__(
            f"CDP command '{command}' failed: {reason}",
            {"command": command, "reason": reason, "error_code": "CDP_ERROR"}
        )


class TimeoutError(AIBrowserAutomationError):
    """Raised when operations timeout."""
    
    def __init__(self, operation: str, timeout_ms: int):
        super().__init__(
            f"Operation '{operation}' timed out after {timeout_ms}ms",
            {"operation": operation, "timeout_ms": timeout_ms, "error_code": "TIMEOUT"}
        )


class ConfigurationError(AIBrowserAutomationError):
    """Raised when configuration is invalid."""
    
    def __init__(self, reason: str):
        super().__init__(
            f"Invalid configuration: {reason}",
            {"reason": reason, "error_code": "CONFIGURATION_ERROR"}
        )


class UnsupportedOperationError(AIBrowserAutomationError):
    """Raised when an unsupported operation is attempted."""
    
    def __init__(self, operation: str, reason: Optional[str] = None):
        message = f"Unsupported operation: {operation}"
        if reason:
            message += f" - {reason}"
        super().__init__(
            message,
            {"operation": operation, "reason": reason, "error_code": "UNSUPPORTED_OPERATION"}
        )