"""In-process TTL cache shared by every upstream client.

This started life inside mfapi_client.py. It moved here because three other
callers need the same behaviour: the Screener fundamentals scraper (24h TTL,
because fundamentals only change quarterly), the Fyers quote layer (seconds,
to stay under the rate limits), and the symbol master (days).

Deliberately not Redis. Every cached payload is public, read-only market data
that can be refetched, so a per-process cache is correct here — it just means
each web worker warms its own copy. Anything that must be shared across workers
or survive a restart belongs in Postgres instead, not here.
"""

import logging
import threading
import time
from typing import Any, Callable, Dict, Hashable, Optional, Tuple

logger = logging.getLogger(__name__)


class TTLCache:
    """Tiny thread-safe TTL cache with a bounded size."""

    def __init__(self, ttl: float, max_entries: int = 512):
        self._ttl = ttl
        self._max_entries = max_entries
        self._lock = threading.Lock()
        self._store: Dict[Any, Tuple[float, Any]] = {}

    def get(self, key: Any) -> Any:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            expires_at, value = entry
            if expires_at < time.monotonic():
                self._store.pop(key, None)
                return None
            return value

    def set(self, key: Any, value: Any, ttl: Optional[float] = None) -> None:
        with self._lock:
            if len(self._store) >= self._max_entries and key not in self._store:
                # Cheap eviction: drop whatever expires soonest.
                oldest = min(self._store, key=lambda k: self._store[k][0])
                self._store.pop(oldest, None)
            self._store[key] = (time.monotonic() + (self._ttl if ttl is None else ttl), value)

    def get_or_set(self, key: Any, factory: Callable[[], Any], ttl: Optional[float] = None) -> Any:
        """Return the cached value, or compute and store it.

        `factory` runs outside the lock: these callers do network I/O, and
        holding the lock across a 20-second HTTP request would serialise every
        other cache user behind it. The cost is that a cold key hit by N
        concurrent requests does N fetches — acceptable, since the alternative
        (a per-key lock) buys little for read-only data that is cheap to refetch.
        """
        cached = self.get(key)
        if cached is not None:
            return cached
        value = factory()
        self.set(key, value, ttl=ttl)
        return value

    def invalidate(self, key: Any) -> None:
        with self._lock:
            self._store.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._store)


def make_key(*parts: Any) -> Tuple[Hashable, ...]:
    """Build a stable cache key from mixed arguments.

    Dicts are the awkward case — they are unhashable and their iteration order
    should not change the key — so they are flattened to sorted item tuples with
    None values dropped, matching how the HTTP clients drop empty query params.
    """
    key: list = []
    for part in parts:
        if isinstance(part, dict):
            key.append(tuple(sorted((k, v) for k, v in part.items() if v is not None)))
        elif isinstance(part, (list, set)):
            key.append(tuple(sorted(map(str, part))))
        else:
            key.append(part)
    return tuple(key)
