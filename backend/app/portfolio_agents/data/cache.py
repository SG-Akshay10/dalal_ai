"""Thread-safe caching module for market data fetching and deterministic agent calculations."""

from __future__ import annotations

import hashlib
import json
import threading
import time
from typing import Any


class AgentDataCache:
    """Thread-safe in-memory key-value cache with TTL support for expensive calculation steps."""

    def __init__(self, default_ttl_seconds: float = 600.0) -> None:
        self.default_ttl = default_ttl_seconds
        self._cache: dict[str, tuple[float, Any]] = {}
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0

    def make_key(self, prefix: str, *args: Any, **kwargs: Any) -> str:
        """Create a deterministic hash key from prefix and json-serializable arguments."""
        try:
            payload = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True, default=str)
        except Exception:
            payload = str((args, kwargs))
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
        return f"{prefix}:{digest}"

    def get(self, key: str) -> Any | None:
        now = time.time()
        with self._lock:
            if key in self._cache:
                expires_at, val = self._cache[key]
                if now < expires_at:
                    self.hits += 1
                    return val
                else:
                    del self._cache[key]
            self.misses += 1
            return None

    def set(self, key: str, value: Any, ttl_seconds: float | None = None) -> None:
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl
        expires_at = time.time() + ttl
        with self._lock:
            self._cache[key] = (expires_at, value)

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()
            self.hits = 0
            self.misses = 0

    def get_stats(self) -> dict[str, int]:
        with self._lock:
            return {
                "hits": self.hits,
                "misses": self.misses,
                "size": len(self._cache),
            }


global_data_cache = AgentDataCache()
