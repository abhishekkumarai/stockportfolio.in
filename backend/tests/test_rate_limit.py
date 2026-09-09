import threading
import time

import pytest

from app.rate_limit import RateLimiter, RateLimitExceeded


def test_allows_burst_up_to_limit_without_blocking():
    limiter = RateLimiter(((5, 1.0, "per_second"),))
    start = time.monotonic()
    for _ in range(5):
        limiter.acquire()
    assert time.monotonic() - start < 0.2


def test_blocks_once_window_is_full():
    limiter = RateLimiter(((3, 1.0, "per_second"),))
    for _ in range(3):
        limiter.acquire()
    start = time.monotonic()
    limiter.acquire()
    # The 4th must wait for the oldest of the first three to age out.
    assert time.monotonic() - start >= 0.7


def test_window_slides_rather_than_resetting():
    """A fixed window would let 2N requests through across a boundary."""
    limiter = RateLimiter(((2, 0.5, "per_second"),))
    limiter.acquire()
    limiter.acquire()
    time.sleep(0.55)
    start = time.monotonic()
    limiter.acquire()
    limiter.acquire()
    assert time.monotonic() - start < 0.2


def test_raises_when_wait_exceeds_budget():
    limiter = RateLimiter(((1, 3600.0, "per_day"),))
    limiter.acquire()
    with pytest.raises(RateLimitExceeded) as exc:
        limiter.acquire(max_wait=1.0)
    assert "per_day" in str(exc.value)


def test_error_names_the_binding_window():
    limiter = RateLimiter(((10, 1.0, "per_second"), (1, 3600.0, "per_day")))
    limiter.acquire()
    with pytest.raises(RateLimitExceeded) as exc:
        limiter.acquire(max_wait=0.5)
    assert "per_day" in str(exc.value)


def test_try_acquire_is_non_blocking():
    limiter = RateLimiter(((1, 60.0, "per_minute"),))
    assert limiter.try_acquire() is True
    start = time.monotonic()
    assert limiter.try_acquire() is False
    assert time.monotonic() - start < 0.05


def test_remaining_tracks_usage():
    limiter = RateLimiter(((5, 60.0, "per_minute"),))
    assert limiter.remaining("per_minute") == 5
    limiter.acquire()
    limiter.acquire()
    assert limiter.remaining("per_minute") == 3
    assert limiter.remaining("nonexistent") is None


def test_strictest_window_governs():
    """Generous per-second is irrelevant when the daily budget is spent."""
    limiter = RateLimiter(((100, 1.0, "per_second"), (2, 3600.0, "per_day")))
    limiter.acquire()
    limiter.acquire()
    assert limiter.try_acquire() is False


def test_reset_clears_state():
    limiter = RateLimiter(((2, 60.0, "per_minute"),))
    limiter.acquire()
    limiter.acquire()
    limiter.reset()
    assert limiter.remaining("per_minute") == 2


def test_no_limits_never_blocks():
    limiter = RateLimiter()
    for _ in range(50):
        limiter.acquire()
    assert limiter.stats()["requests"] == 50


def test_concurrent_callers_do_not_exceed_the_limit():
    """The whole point of the lock: 20 threads must not smuggle in extra slots."""
    limiter = RateLimiter(((5, 60.0, "per_minute"),))
    granted = []
    lock = threading.Lock()

    def worker():
        if limiter.try_acquire():
            with lock:
                granted.append(1)

    threads = [threading.Thread(target=worker) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(granted) == 5


def test_stats_reports_windows():
    limiter = RateLimiter(((5, 60.0, "per_minute"),), name="fyers")
    limiter.acquire()
    stats = limiter.stats()
    assert stats["name"] == "fyers"
    assert stats["requests"] == 1
    assert stats["windows"]["per_minute"] == {"used": 1, "limit": 5}
