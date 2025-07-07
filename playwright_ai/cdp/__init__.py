"""CDP (Chrome DevTools Protocol) utilities for Playwright AI."""

# Use simplified CDP manager to match TypeScript implementation
from .manager_simple import (
    cdp_manager,
    SimpleCDPManager,
    SimpleCDPSessionPool,
)

# Keep original complex manager for backwards compatibility if needed
from .manager import (
    CDPManager,
    CDPEventListener,
    CDPSessionPool,
    CDPBatchExecutor,
    PartialTreeExtractor,
    FrameChainResolver,
    NetworkInterceptor,
    PerformanceMonitor,
    cdp_manager as complex_cdp_manager
)

__all__ = [
    "cdp_manager",
    "SimpleCDPManager",
    "SimpleCDPSessionPool",
    "CDPManager",
    "CDPEventListener", 
    "CDPSessionPool",
    "CDPBatchExecutor",
    "PartialTreeExtractor",
    "FrameChainResolver",
    "NetworkInterceptor",
    "PerformanceMonitor",
    "complex_cdp_manager"
]