"""Redis wiring — coordination, not caching.

`cache.py` deliberately keeps hot market data in-process, and that stays true:
every cached payload there is public, refetchable and cheap, so sharing it
across containers would buy nothing. Redis is here for the one thing an
in-process structure cannot do — let *separate processes* agree on something:

* **A durable APScheduler job store.** With the schedule in Redis the nightly
  jobs and their next run times survive a container restart, so a redeploy at
  22:29 does not silently lose the 22:30 snapshot.
* **A run lock.** The api and worker containers both import the same code, and
  a scaled-out api would import it N times. The lock makes "run this job" mean
  once per night across the whole stack rather than once per process.

Optional exactly like the database: with `REDIS_URL` unset `is_enabled()` is
False, the scheduler falls back to its in-memory store, and `lock()` grants
unconditionally — which is correct for a single-process deployment, where
there is nobody else to race with.
"""

import logging
import os
import threading
from contextlib import contextmanager
from typing import Any, Dict, Iterator, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)

# Namespaced so a shared Redis (one instance, several projects) stays legible
# in `KEYS *` and can be dropped with one `DEL stockportfolio:*` sweep.
KEY_PREFIX = "stockportfolio"
JOBS_KEY = f"{KEY_PREFIX}:apscheduler:jobs"
RUN_TIMES_KEY = f"{KEY_PREFIX}:apscheduler:run_times"

# Release only if we still hold it: a job that overran its TTL must not delete
# the lock the *next* run legitimately acquired.
_RELEASE_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('del', KEYS[1])
else
    return 0
end
"""

_lock = threading.Lock()
_client: Optional[Any] = None


def redis_url() -> str:
    return (os.getenv("REDIS_URL") or "").strip()


def is_enabled() -> bool:
    """True when a Redis URL is configured. Cheap; no connection attempted."""
    return bool(redis_url())


def get_client() -> Any:
    """The process-wide client, created on first use. Raises if unconfigured."""
    global _client
    if _client is not None:
        return _client

    url = redis_url()
    if not url:
        raise RuntimeError(
            "REDIS_URL is not set. Scheduler durability and cross-process job "
            "locking are disabled until it is."
        )

    try:
        import redis
    except ImportError as exc:  # pragma: no cover - dependency is declared
        raise RuntimeError("redis is not installed; cannot use REDIS_URL.") from exc

    with _lock:
        if _client is None:
            _client = redis.Redis.from_url(
                url,
                decode_responses=True,
                # A wedged Redis must not hang a nightly job or an admin probe.
                socket_timeout=5,
                socket_connect_timeout=5,
                health_check_interval=30,
            )
    return _client


def reset_client() -> None:
    """Drop the cached client. Used by tests that swap REDIS_URL."""
    global _client
    with _lock:
        if _client is not None:
            try:
                _client.close()
            except Exception:  # pragma: no cover - best effort
                pass
        _client = None


def ping() -> Dict[str, Any]:
    """Configured / reachable, for /status and the admin route. Never raises."""
    if not is_enabled():
        return {"configured": False, "reachable": False, "reason": "REDIS_URL is not set."}
    try:
        get_client().ping()
        return {"configured": True, "reachable": True, "reason": None}
    except Exception as exc:
        return {"configured": True, "reachable": False, "reason": str(exc)}


@contextmanager
def lock(name: str, ttl: int = 3600) -> Iterator[bool]:
    """Hold a named cross-process lock for the block, yielding whether we got it.

    Yields True — not raises — when Redis is absent or unreachable. A single
    container with no Redis is the deployment this app shipped with, and
    refusing to run the night's jobs because an *optional* coordinator is down
    would trade a duplicate-run risk for a guaranteed no-run.
    """
    if not is_enabled():
        yield True
        return

    key = f"{KEY_PREFIX}:lock:{name}"
    token = uuid4().hex
    client = None
    acquired = False
    try:
        client = get_client()
        acquired = bool(client.set(key, token, nx=True, ex=ttl))
    except Exception as exc:
        logger.warning("Redis lock %s unavailable (%s); running unguarded.", name, exc)
        yield True
        return

    try:
        yield acquired
    finally:
        if acquired and client is not None:
            try:
                client.eval(_RELEASE_SCRIPT, 1, key, token)
            except Exception as exc:  # pragma: no cover - best effort
                logger.warning("Could not release Redis lock %s: %s", name, exc)
