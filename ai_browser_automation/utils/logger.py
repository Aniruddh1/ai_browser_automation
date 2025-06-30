"""Logging configuration for AIBrowserAutomation."""

import sys
import structlog
from typing import Any, Dict, Optional, List
from enum import IntEnum
import os


class LogLevel(IntEnum):
    """Log levels for AIBrowserAutomation."""
    ERROR = 0
    WARN = 1
    INFO = 2
    DEBUG = 3


def configure_logging(verbose: int = 0) -> structlog.BoundLogger:
    """
    Configure structlog for AIBrowserAutomation.
    
    Args:
        verbose: Verbosity level (0-3)
        
    Returns:
        Configured logger instance
    """
    # Determine log level based on verbosity
    log_level = "ERROR"
    if verbose >= 3:
        log_level = "DEBUG"
    elif verbose >= 2:
        log_level = "INFO"
    elif verbose >= 1:
        log_level = "WARNING"
    
    # Check if we're in a terminal
    is_tty = sys.stderr.isatty()
    
    # Configure processors
    processors: List[Any] = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]
    
    if is_tty and os.getenv("NO_COLOR") is None:
        # Use colored output for terminals
        processors.append(structlog.dev.ConsoleRenderer())
    else:
        # Use JSON for non-terminals or when NO_COLOR is set
        processors.append(structlog.processors.JSONRenderer())
    
    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # Configure stdlib logging
    import logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stderr,
        level=getattr(logging, log_level),
    )
    
    # Create and return logger
    logger = structlog.get_logger("ai_browser_automation")
    logger = logger.bind(verbose=verbose)
    
    return logger


class LogLine:
    """Represents a structured log line."""
    
    def __init__(
        self,
        category: str,
        message: str,
        level: LogLevel = LogLevel.INFO,
        auxiliary: Optional[Dict[str, Any]] = None,
    ):
        self.category = category
        self.message = message
        self.level = level
        self.auxiliary = auxiliary or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert log line to dictionary."""
        return {
            "category": self.category,
            "message": self.message,
            "level": self.level.name,
            **self.auxiliary,
        }


class AIBrowserAutomationLogger:
    """Logger wrapper for AIBrowserAutomation with category support."""
    
    def __init__(self, logger: structlog.BoundLogger, verbose: int = 0):
        self.logger = logger
        self.verbose = verbose
    
    def log(self, log_line: LogLine) -> None:
        """Log a structured log line."""
        if log_line.level.value > self.verbose:
            return
        
        log_data = log_line.to_dict()
        level_name = log_line.level.name.lower()
        
        # Use appropriate log method
        log_method = getattr(self.logger, level_name, self.logger.info)
        log_method(log_line.message, **log_data)
    
    def error(self, category: str, message: str, **kwargs: Any) -> None:
        """Log an error message."""
        self.log(LogLine(category, message, LogLevel.ERROR, kwargs))
    
    def warn(self, category: str, message: str, **kwargs: Any) -> None:
        """Log a warning message."""
        self.log(LogLine(category, message, LogLevel.WARN, kwargs))
    
    def info(self, category: str, message: str, **kwargs: Any) -> None:
        """Log an info message."""
        self.log(LogLine(category, message, LogLevel.INFO, kwargs))
    
    def debug(self, category: str, message: str, **kwargs: Any) -> None:
        """Log a debug message."""
        self.log(LogLine(category, message, LogLevel.DEBUG, kwargs))
    
    def child(self, **bindings: Any) -> 'AIBrowserAutomationLogger':
        """Create a child logger with additional context."""
        child_logger = self.logger.bind(**bindings)
        return AIBrowserAutomationLogger(child_logger, self.verbose)