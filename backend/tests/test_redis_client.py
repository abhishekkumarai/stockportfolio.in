import pytest

from app import redis_client, scheduler


class FakeRedis:
    """Just enough Redis to exercise the lock: SET NX EX and the release eval."""

    def __init__(self, held=None):
        self.store = dict(held or {})
        self.evals = []

    def set(self, key, value, nx=False, ex=None):
        if nx and key in self.store:
            return None
        self.store[key] = value
        return True

    def eval(self, script, numkeys, key, token):
        self.evals.append(key)
        if self.store.get(key) == token:
            del self.store[key]
            return 1
        return 0

    def ping(self):
        return True


@pytest.fixture(autouse=True)
def _clean_client():
    redis_client.reset_client()
    yield
    redis_client.reset_client()


def test_disabled_without_url(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    assert redis_client.is_enabled() is False
    assert redis_client.ping()["configured"] is False


def test_get_client_refuses_without_url(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    with pytest.raises(RuntimeError, match="REDIS_URL"):
        redis_client.get_client()


def test_lock_grants_when_redis_is_not_configured(monkeypatch):
    # A single-process deployment has nobody to race with, so the absence of a
    # coordinator must not stop the job running.
    monkeypatch.delenv("REDIS_URL", raising=False)
    with redis_client.lock("job:portfolio_snapshot") as acquired:
        assert acquired is True


def test_lock_acquires_and_releases(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://redis:6379/0")
    fake = FakeRedis()
    monkeypatch.setattr(redis_client, "get_client", lambda: fake)

    key = f"{redis_client.KEY_PREFIX}:lock:job:evaluate_alerts"
    with redis_client.lock("job:evaluate_alerts") as acquired:
        assert acquired is True
        assert key in fake.store

    assert fake.evals == [key]
    assert key not in fake.store


def test_lock_denied_when_already_held(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://redis:6379/0")
    key = f"{redis_client.KEY_PREFIX}:lock:job:screener_rescan"
    fake = FakeRedis(held={key: "someone-elses-token"})
    monkeypatch.setattr(redis_client, "get_client", lambda: fake)

    with redis_client.lock("job:screener_rescan") as acquired:
        assert acquired is False

    # Not ours, so not released - the holder keeps it.
    assert fake.store[key] == "someone-elses-token"
    assert fake.evals == []


def test_lock_grants_when_redis_is_unreachable(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://redis:6379/0")

    def boom():
        raise ConnectionError("connection refused")

    monkeypatch.setattr(redis_client, "get_client", boom)
    with redis_client.lock("job:portfolio_snapshot") as acquired:
        assert acquired is True


def test_ping_reports_unreachable(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://redis:6379/0")

    def boom():
        raise ConnectionError("connection refused")

    monkeypatch.setattr(redis_client, "get_client", boom)
    result = redis_client.ping()
    assert result == {"configured": True, "reachable": False, "reason": "connection refused"}


def test_store_kind_follows_configuration(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    assert scheduler.store_kind() == "memory"
    monkeypatch.setenv("REDIS_URL", "redis://redis:6379/0")
    assert scheduler.store_kind() == "redis"


def test_jobstores_fall_back_when_redis_is_down(monkeypatch):
    # A dead optional store must degrade to in-memory, never stop the schedule.
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:1/0")
    assert scheduler._jobstores() == {}


def test_scheduler_skips_a_job_held_elsewhere(monkeypatch):
    # app.jobs pulls in the scraper stack; skip where that is not installed
    # (it always is in the container, which is where the stack is exercised).
    pytest.importorskip("curl_cffi")
    monkeypatch.setenv("REDIS_URL", "redis://redis:6379/0")
    key = f"{redis_client.KEY_PREFIX}:lock:job:portfolio_snapshot"
    fake = FakeRedis(held={key: "worker-1"})
    monkeypatch.setattr(redis_client, "get_client", lambda: fake)

    called = []
    monkeypatch.setattr("app.jobs.run_job", lambda name, **kw: called.append(name))

    scheduler._run_and_log("portfolio_snapshot", {})
    assert called == []


def test_cron_triggers_use_the_configured_timezone(monkeypatch):
    # Regression: a CronTrigger constructed without `timezone=` takes the
    # process local zone (UTC in the container), so 21:30 IST became 03:00 IST.
    CronTrigger = pytest.importorskip("apscheduler.triggers.cron").CronTrigger

    trigger = CronTrigger(hour=21, minute=30, day_of_week="mon-sat", timezone="Asia/Kolkata")
    assert str(trigger.timezone) == "Asia/Kolkata"

    source = open("app/scheduler.py", encoding="utf-8").read()
    assert 'day_of_week="mon-sat", timezone=timezone' in source
