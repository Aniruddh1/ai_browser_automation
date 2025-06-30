"""CDP (Chrome DevTools Protocol) utilities for AI Browser Automation."""

from .manager import (
    CDPManager,
    CDPEventListener,
    CDPSessionPool,
    CDPBatchExecutor,
    PartialTreeExtractor,
    FrameChainResolver,
    NetworkInterceptor,
    PerformanceMonitor,
    cdp_manager
)

__all__ = [
    "CDPManager",
    "CDPEventListener", 
    "CDPSessionPool",
    "CDPBatchExecutor",
    "PartialTreeExtractor",
    "FrameChainResolver",
    "NetworkInterceptor",
    "PerformanceMonitor",
    "cdp_manager"
]