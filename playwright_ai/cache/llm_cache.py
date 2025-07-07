"""LLM-specific cache implementation."""

import logging
from typing import Any, Dict, Optional
from .base_cache import BaseCache


class LLMCache(BaseCache):
    """Cache specifically for LLM API calls."""
    
    def __init__(
        self,
        logger: Optional[logging.Logger] = None,
        cache_dir: Optional[str] = None,
        cache_file: Optional[str] = None
    ):
        super().__init__(
            logger=logger,
            cache_dir=cache_dir,
            cache_file=cache_file or "llm_calls.json"
        )
    
    async def get(self, options: Dict[str, Any], request_id: str) -> Optional[Any]:
        """Get cached LLM response."""
        data = await super().get(options, request_id)
        if data is not None:
            self._log_info("LLM cache hit")
        return data
    
    async def set(self, options: Dict[str, Any], data: Any, request_id: str) -> None:
        """Cache LLM response."""
        await super().set(options, data, request_id)
        self._log_info("LLM response cached")
    
    async def cleanup(self) -> None:
        """Cleanup cache resources."""
        # Cleanup is handled automatically
        pass