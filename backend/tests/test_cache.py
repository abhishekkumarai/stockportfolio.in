import time

from app.cache import TTLCache, make_key


def test_returns_value_before_expiry():
    cache = TTLCache(ttl=10.0)
    cache.set("k", {"v": 1})
    assert cache.get("k") == {"v": 1}


def test_expires_after_ttl():
    cache = TTLCache(ttl=0.05)
    cache.set("k", "v")
    time.sleep(0.08)
    assert cache.get("k") is None
    # The expired entry is dropped on read, not merely hidden.
    assert len(cache) == 0


def test_miss_returns_none():
    assert TTLCache(ttl=10.0).get("absent") is None


def test_eviction_respects_max_entries():
    cache = TTLCache(ttl=60.0, max_entries=3)
    for i in range(5):
        cache.set(f"k{i}", i)
    assert len(cache) <= 3


def test_overwriting_existing_key_does_not_evict():
    """Re-setting a key must not count as growth, or a hot key evicts a cold one."""
    cache = TTLCache(ttl=60.0, max_entries=2)
    cache.set("a", 1)
    cache.set("b", 2)
    cache.set("a", 99)
    assert cache.get("a") == 99
    assert cache.get("b") == 2


def test_per_entry_ttl_overrides_default():
    cache = TTLCache(ttl=60.0)
    cache.set("short", "v", ttl=0.05)
    time.sleep(0.08)
    assert cache.get("short") is None


def test_get_or_set_computes_once():
    cache = TTLCache(ttl=60.0)
    calls = []

    def factory():
        calls.append(1)
        return "computed"

    assert cache.get_or_set("k", factory) == "computed"
    assert cache.get_or_set("k", factory) == "computed"
    assert len(calls) == 1


def test_invalidate_and_clear():
    cache = TTLCache(ttl=60.0)
    cache.set("a", 1)
    cache.set("b", 2)
    cache.invalidate("a")
    assert cache.get("a") is None
    assert cache.get("b") == 2
    cache.clear()
    assert len(cache) == 0


def test_make_key_is_order_independent_for_dicts():
    assert make_key("/p", {"a": 1, "b": 2}) == make_key("/p", {"b": 2, "a": 1})


def test_make_key_drops_none_values():
    """Matches how the HTTP clients strip empty query params before sending."""
    assert make_key("/p", {"a": 1, "b": None}) == make_key("/p", {"a": 1})


def test_make_key_distinguishes_different_params():
    assert make_key("/p", {"a": 1}) != make_key("/p", {"a": 2})
    assert make_key("/p", {"a": 1}) != make_key("/q", {"a": 1})


def test_make_key_is_hashable():
    key = make_key("/p", {"a": 1}, ["x", "y"], 5)
    assert hash(key)
