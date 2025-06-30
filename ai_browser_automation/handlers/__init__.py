"""Handler system for AIBrowserAutomation."""

from .base import BaseHandler
from .act import ActHandler
from .extract import ExtractHandler
from .observe import ObserveHandler

__all__ = ["BaseHandler", "ActHandler", "ExtractHandler", "ObserveHandler"]