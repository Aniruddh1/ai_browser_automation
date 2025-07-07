"""Base cache implementation with file locking."""

import os
import json
import hashlib
import asyncio
import time
import logging
import signal
import random
import inspect
from pathlib import Path
from typing import Any, Dict, Optional, Union
from typing_extensions import TypedDict
from datetime import datetime, timedelta


class CacheEntry(TypedDict):
    timestamp: float
    data: Any
    request_id: str


class CacheStore(TypedDict):
    entries: Dict[str, CacheEntry]


class BaseCache:
    CACHE_MAX_AGE_MS = 7 * 24 * 60 * 60 * 1000  # 1 week in milliseconds
    CLEANUP_PROBABILITY = 0.01  # 1% chance
    LOCK_TIMEOUT_MS = 1000  # 1 second
    LOCK_RETRY_DELAY_MS = 5  # 5ms between retries
    
    def __init__(
        self,
        logger: Optional[Any] = None,
        cache_dir: Optional[str] = None,
        cache_file: str = "cache.json"
    ):
        self.logger = logger or logging.getLogger(__name__)
        
        if cache_dir is None:
            cache_dir = Path.cwd() / "tmp" / ".cache"
        else:
            cache_dir = Path(cache_dir)
            
        self.cache_dir = cache_dir
        self.cache_file = cache_dir / cache_file
        self.lock_file = cache_dir / "cache.lock"
        
        self.lock_acquired = False
        self.lock_acquire_failures = 0
        self.lock_fd: Optional[int] = None
        
        # Track which hashes are used by each request ID
        self.request_id_to_used_hashes: Dict[str, list[str]] = {}
        
        self._ensure_cache_directory()
        self._setup_process_handlers()
    
    def _log_debug(self, message: str, **kwargs: Any) -> None:
        """Log debug message, handling both logger types."""
        if hasattr(self.logger, 'debug') and callable(getattr(self.logger, 'debug')):
            # PlaywrightAILogger
            if kwargs:
                self.logger.debug("cache", message, **kwargs)
            else:
                self.logger.debug("cache", message)
        else:
            # Standard Python logger
            self.logger.debug(f"{message}: {kwargs}" if kwargs else message)
    
    def _log_info(self, message: str, **kwargs: Any) -> None:
        """Log info message, handling both logger types."""
        if hasattr(self.logger, 'info') and len(inspect.signature(self.logger.info).parameters) > 1:
            # PlaywrightAILogger
            if kwargs:
                self.logger.info("cache", message, **kwargs)
            else:
                self.logger.info("cache", message)
        else:
            # Standard Python logger
            self.logger.info(f"{message}: {kwargs}" if kwargs else message)
    
    def _log_warning(self, message: str, **kwargs: Any) -> None:
        """Log warning message, handling both logger types."""
        if hasattr(self.logger, 'warn') and len(inspect.signature(self.logger.warn).parameters) > 1:
            # PlaywrightAILogger
            if kwargs:
                self.logger.warn("cache", message, **kwargs)
            else:
                self.logger.warn("cache", message)
        else:
            # Standard Python logger
            self.logger.warning(f"{message}: {kwargs}" if kwargs else message)
    
    def _log_error(self, message: str, **kwargs: Any) -> None:
        """Log error message, handling both logger types."""
        if hasattr(self.logger, 'error') and len(inspect.signature(self.logger.error).parameters) > 1:
            # PlaywrightAILogger
            if kwargs:
                self.logger.error("cache", message, **kwargs)
            else:
                self.logger.error("cache", message)
        else:
            # Standard Python logger
            self.logger.error(f"{message}: {kwargs}" if kwargs else message)
    
    def _ensure_cache_directory(self) -> None:
        """Create cache directory if it doesn't exist."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._log_debug("Cache directory ensured", cache_dir=str(self.cache_dir))
    
    def _setup_process_handlers(self) -> None:
        """Setup signal handlers to release locks on exit."""
        def release_lock_and_exit(signum, frame):
            self.release_lock()
            exit(0)
        
        signal.signal(signal.SIGINT, release_lock_and_exit)
        signal.signal(signal.SIGTERM, release_lock_and_exit)
    
    def _create_hash(self, data: Union[Dict[str, Any], str]) -> str:
        """Create SHA256 hash of the data."""
        if isinstance(data, str):
            hash_input = data
        else:
            hash_input = json.dumps(data, sort_keys=True)
        return hashlib.sha256(hash_input.encode()).hexdigest()
    
    async def acquire_lock(self) -> bool:
        """Acquire file lock with timeout."""
        start_time = time.time() * 1000  # Convert to milliseconds
        
        while (time.time() * 1000 - start_time) < self.LOCK_TIMEOUT_MS:
            try:
                # Check if lock file exists and is stale
                if self.lock_file.exists():
                    lock_age_ms = (time.time() - self.lock_file.stat().st_mtime) * 1000
                    if lock_age_ms > self.LOCK_TIMEOUT_MS:
                        self.lock_file.unlink()
                        self._log_debug("Removed stale lock file")
                
                # Try to create lock file exclusively
                self.lock_fd = os.open(
                    str(self.lock_file),
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY
                )
                
                # Write PID to lock file
                os.write(self.lock_fd, str(os.getpid()).encode())
                
                self.lock_acquired = True
                self.lock_acquire_failures = 0
                self._log_debug("Lock acquired")
                return True
                
            except FileExistsError:
                # Lock is held by another process
                await asyncio.sleep(self.LOCK_RETRY_DELAY_MS / 1000)
            except Exception as e:
                self._log_error("Error acquiring lock", error=str(e))
                await asyncio.sleep(self.LOCK_RETRY_DELAY_MS / 1000)
        
        # Failed to acquire lock within timeout
        self.lock_acquire_failures += 1
        self._log_warning("Failed to acquire lock after timeout", failures=self.lock_acquire_failures)
        
        if self.lock_acquire_failures >= 3:
            self._log_warning("Failed to acquire lock 3 times. Force releasing lock.")
            self.release_lock()
        
        return False
    
    def release_lock(self) -> None:
        """Release the file lock."""
        try:
            if self.lock_fd is not None:
                os.close(self.lock_fd)
                self.lock_fd = None
            
            if self.lock_file.exists():
                self.lock_file.unlink()
                self._log_debug("Lock released")
            
            self.lock_acquired = False
        except Exception as e:
            self._log_error("Error releasing lock", error=str(e))
    
    def _read_cache(self) -> Dict[str, CacheEntry]:
        """Read cache from disk."""
        if not self.cache_file.exists():
            return {}
        
        try:
            with open(self.cache_file, 'r') as f:
                data = json.load(f)
                return data.get('entries', {})
        except Exception as e:
            self._log_error("Error reading cache file. Resetting cache.", error=str(e))
            self._reset_cache()
            return {}
    
    def _write_cache(self, cache: Dict[str, CacheEntry]) -> None:
        """Write cache to disk."""
        try:
            cache_data = {'entries': cache}
            with open(self.cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2)
            self._log_debug("Cache written to file")
        except Exception as e:
            self._log_error("Error writing cache file", error=str(e))
    
    def _reset_cache(self) -> None:
        """Reset the cache file."""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump({'entries': {}}, f)
            self.request_id_to_used_hashes.clear()
            self._log_info("Cache reset")
        except Exception as e:
            self._log_error("Error resetting cache", error=str(e))
    
    async def cleanup_stale_entries(self) -> None:
        """Remove cache entries older than CACHE_MAX_AGE_MS."""
        if not await self.acquire_lock():
            self._log_warning("Failed to acquire lock for cleanup")
            return
        
        try:
            cache = self._read_cache()
            now = time.time() * 1000  # Current time in milliseconds
            entries_removed = 0
            
            for hash_key, entry in list(cache.items()):
                if now - entry['timestamp'] > self.CACHE_MAX_AGE_MS:
                    del cache[hash_key]
                    entries_removed += 1
            
            if entries_removed > 0:
                self._write_cache(cache)
                self._log_info("Cleaned up stale cache entries", entries_removed=entries_removed)
        
        except Exception as e:
            self._log_error("Error during cache cleanup", error=str(e))
        finally:
            self.release_lock()
    
    def _track_request_id_usage(self, request_id: str, hash_key: str) -> None:
        """Track which cache entries are used by a request ID."""
        if request_id not in self.request_id_to_used_hashes:
            self.request_id_to_used_hashes[request_id] = []
        self.request_id_to_used_hashes[request_id].append(hash_key)
    
    async def get(self, hash_obj: Union[Dict[str, Any], str], request_id: str) -> Optional[Any]:
        """Get data from cache."""
        if not await self.acquire_lock():
            self._log_warning("Failed to acquire lock for cache get")
            return None
        
        try:
            hash_key = self._create_hash(hash_obj)
            cache = self._read_cache()
            
            if hash_key in cache:
                self._track_request_id_usage(request_id, hash_key)
                self._log_debug("Cache hit", request_id=request_id)
                return cache[hash_key]['data']
            
            self._log_debug("Cache miss", request_id=request_id)
            return None
            
        except Exception as e:
            self._log_error("Error getting from cache", error=str(e))
            self._reset_cache()
            return None
        finally:
            self.release_lock()
    
    async def set(self, hash_obj: Dict[str, Any], data: Any, request_id: str) -> None:
        """Store data in cache."""
        if not await self.acquire_lock():
            self._log_warning("Failed to acquire lock for cache set")
            return
        
        try:
            hash_key = self._create_hash(hash_obj)
            cache = self._read_cache()
            
            cache[hash_key] = {
                'data': data,
                'timestamp': time.time() * 1000,  # Store in milliseconds
                'request_id': request_id
            }
            
            self._write_cache(cache)
            self._track_request_id_usage(request_id, hash_key)
            self._log_debug("Data cached", request_id=request_id)
            
        except Exception as e:
            self._log_error("Error setting cache", error=str(e))
            self._reset_cache()
        finally:
            self.release_lock()
            
            # Randomly trigger cleanup
            if random.random() < self.CLEANUP_PROBABILITY:
                await self.cleanup_stale_entries()
    
    async def delete(self, hash_obj: Dict[str, Any]) -> None:
        """Delete a specific cache entry."""
        if not await self.acquire_lock():
            self._log_warning("Failed to acquire lock for cache delete")
            return
        
        try:
            hash_key = self._create_hash(hash_obj)
            cache = self._read_cache()
            
            if hash_key in cache:
                del cache[hash_key]
                self._write_cache(cache)
                self._log_debug("Cache entry deleted")
            else:
                self._log_debug("Cache entry not found to delete")
                
        except Exception as e:
            self._log_error("Error deleting cache entry", error=str(e))
        finally:
            self.release_lock()
    
    async def delete_cache_for_request_id(self, request_id: str) -> None:
        """Delete all cache entries associated with a request ID."""
        if not await self.acquire_lock():
            self._log_warning("Failed to acquire lock for request cache delete")
            return
        
        try:
            cache = self._read_cache()
            hashes = self.request_id_to_used_hashes.get(request_id, [])
            entries_removed = 0
            
            for hash_key in hashes:
                if hash_key in cache:
                    del cache[hash_key]
                    entries_removed += 1
            
            if entries_removed > 0:
                self._write_cache(cache)
                self._log_info("Deleted cache entries", entries_removed=entries_removed, request_id=request_id)
            else:
                self._log_debug("No cache entries found", request_id=request_id)
            
            # Remove the request ID from tracking
            if request_id in self.request_id_to_used_hashes:
                del self.request_id_to_used_hashes[request_id]
                
        except Exception as e:
            self._log_error("Error deleting cache for request", request_id=request_id, error=str(e))
        finally:
            self.release_lock()