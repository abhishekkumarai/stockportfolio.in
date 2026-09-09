"""Client-side rate limiting for upstream APIs with hard quotas.

Fyers publishes three simultaneous limits per app: 10 requests/second,
200/minute and 10,000/day. Breaching them returns errors and, sustained, risks
the app key itself — so this throttles locally rather than discovering the
limit by hitting it.

The daily budget is the one that actually bites. A single portfolio analysis
fans out into one history call per holding, and the Phase 5 screener walks a
few hundred symbols, so an unthrottled loop can burn the day's quota in
minutes. `remaining_today()` exists so callers can check the budget and degrade
(fewer symbols, cached data) instead of failing halfway through.

Deliberately in-process and therefore per-worker: two workers each get the full
allowance and can together exceed it. Correct enforcement needs shared state,
which arrives with Postgres in Phase 6. Until then the limits are set below the
real ones to leave headroom.
"""

import logging
import threading
import time
from collections import deque
from typing import Deque, Optional, Tuple

logger = logging.getLogger(__name__)


class RateLimitExceeded(Exception):
    """Raised when a limit cannot be satisfied within the caller's wait budget."""


class _Window:
    """Sliding-window counter: at most `limit` events in any `period` seconds."""

    __slots__ = ("limit", "period", "events", "name")

    def __init__(self, limit: int, period: float, name: str):
        self.limit = limit
        self.period = period
        self.name = name
        self.events: Deque[float] = deque()

    def prune(self, now: float) -> None:
        cutoff = now - self.period
        while self.events and self.events[0] <= cutoff:
            self.events.popleft()

    def wait_needed(self, now: float) -> float:
        """Seconds until this window has room. 0.0 when a slot is free now."""
        self.prune(now)
        if len(self.events) < self.limit:
            return 0.0
        # The oldest event is what frees the next slot when it ages out.
        return max(0.0, self.events[0] + self.period - now)

    def record(self, now: float) -> None:
        self.events.append(now)


class RateLimiter:
    """Multi-window limiter. Blocks the caller until every window has room.

    A sliding window rather than a token bucket: the published limits are
    "N requests in any 60 seconds", which a bucket's steady refill would let
    you exceed in bursts at a window boundary.
    """

    def __init__(
        self,
        limits: Optional[Tuple[Tuple[int, float, str], ...]] = None,
        name: str = "upstream",
    ):
        # (limit, period_seconds, label)
        self._windows = [
            _Window(limit, period, label) for limit, period, label in (limits or ())
        ]
        self._name = name
        self._lock = threading.Lock()
        self._blocked_seconds = 0.0
        self._requests = 0

    def acquire(self, max_wait: float = 30.0) -> float:
        """Claim one request slot, sleeping if needed. Returns seconds waited.

        Raises RateLimitExceeded if the wait would exceed `max_wait` — a request
        stalled behind the daily quota should surface as an error the caller can
        report, not a thread parked for eleven hours.
        """
        waited = 0.0
        while True:
            with self._lock:
                now = time.monotonic()
                wait = max((w.wait_needed(now) for w in self._windows), default=0.0)
                if wait <= 0.0:
                    for window in self._windows:
                        window.record(now)
                    self._requests += 1
                    self._blocked_seconds += waited
                    return waited

                if waited + wait > max_wait:
                    blocker = max(self._windows, key=lambda w: w.wait_needed(now))
                    raise RateLimitExceeded(
                        f"{self._name} {blocker.name} limit reached; "
                        f"next slot in {wait:.1f}s (max_wait={max_wait}s)"
                    )

            # Sleep outside the lock so other threads can still be served.
            time.sleep(min(wait, 0.5))
            waited += min(wait, 0.5)

    def try_acquire(self) -> bool:
        """Non-blocking variant. True if a slot was claimed."""
        with self._lock:
            now = time.monotonic()
            if any(w.wait_needed(now) > 0.0 for w in self._windows):
                return False
            for window in self._windows:
                window.record(now)
            self._requests += 1
            return True

    def remaining(self, label: str) -> Optional[int]:
        """Slots left in the named window, so callers can budget a fan-out."""
        with self._lock:
            now = time.monotonic()
            for window in self._windows:
                if window.name == label:
                    window.prune(now)
                    return max(0, window.limit - len(window.events))
        return None

    def stats(self) -> dict:
        with self._lock:
            now = time.monotonic()
            for window in self._windows:
                window.prune(now)
            return {
                "name": self._name,
                "requests": self._requests,
                "blocked_seconds": round(self._blocked_seconds, 2),
                "windows": {
                    w.name: {"used": len(w.events), "limit": w.limit}
                    for w in self._windows
                },
            }

    def reset(self) -> None:
        with self._lock:
            for window in self._windows:
                window.events.clear()
            self._blocked_seconds = 0.0
            self._requests = 0


# Fyers' documented caps are 10/s, 200/min and 10k/day. These sit deliberately
# below that: the limiter is per-process, so two Render workers each hold their
# own allowance, and the headroom keeps their sum under the real ceiling.
FYERS_LIMITS = (
    (8, 1.0, "per_second"),
    (180, 60.0, "per_minute"),
    (9000, 86400.0, "per_day"),
)

# Module-level singleton: the quota belongs to the Fyers app, not to any one
# client instance, and routes/fyers.py builds a fresh FyersClient per request.
fyers_limiter = RateLimiter(FYERS_LIMITS, name="fyers")
