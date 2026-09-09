"""In-process nightly scheduler.

APScheduler in the web process rather than Celery with a broker: the workload
is four jobs a night over a handful of accounts, and QuantDinger's Celery +
dual-Redis topology would be more infrastructure than computation. The trade is
explicit — an in-process scheduler dies with the process and runs twice if the
service is scaled to two instances.

Both of those are handled:

* **Sleeping web service.** Render's free tier sleeps after ~15 minutes idle,
  and a sleeping process runs nothing. So the same jobs are reachable at
  `POST /api/admin/jobs/{name}` for an external cron to trigger, and that is
  the recommended production setup. The in-process scheduler is for a
  self-hosted always-on container.
* **Duplicate runs.** Jobs are idempotent — snapshots upsert on
  (account, date), alert rules have a cooldown — so a double fire wastes work
  but does not corrupt anything.

When `REDIS_URL` is set both trades improve. The schedule itself moves into a
`RedisJobStore`, so next-run times survive a restart instead of being rebuilt
from scratch, and every run first takes a Redis lock named after the job — so
the api container and the worker container (and any scaled-out replica) share
one nightly run rather than one each. Without Redis the behaviour is exactly
what it was: an in-memory store and unguarded runs, which is correct for a
single process.

Off unless `ENABLE_SCHEDULER=true`, so importing this module in a test or a
one-off script never starts a background thread.
"""

import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# IST. The NSE closes at 15:30 and the mfapi NAV feed updates late evening, so
# jobs are timed after both rather than at a notional midnight UTC.
DEFAULT_TIMEZONE = "Asia/Kolkata"

# (job name, hour, minute, kwargs). Ordered so that the snapshot exists before
# alerts are evaluated against it.
NIGHTLY_JOBS = [
    ("fundamentals_refresh", 21, 30, {}),
    ("screener_rescan", 22, 0, {}),
    ("portfolio_snapshot", 22, 30, {}),
    ("paper_mark_to_market", 22, 45, {}),
    ("evaluate_alerts", 23, 0, {}),
]

# Long enough for the slowest job (a full screener rescan) to finish, short
# enough that a killed container frees the lock before the next night.
LOCK_TTL_SECONDS = 3600

_scheduler = None


def is_enabled() -> bool:
    return (os.getenv("ENABLE_SCHEDULER", "false").strip().lower() in {"1", "true", "yes"})


def start() -> Optional[Any]:
    """Start the background scheduler if enabled and a database is configured."""
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    if not is_enabled():
        logger.info("Scheduler disabled (set ENABLE_SCHEDULER=true to enable).")
        return None

    from app.db import is_enabled as db_enabled

    if not db_enabled():
        # Starting a scheduler whose every job raises PersistenceRequired would
        # produce a nightly stack trace and nothing else.
        logger.warning("ENABLE_SCHEDULER is set but DATABASE_URL is not; not starting.")
        return None

    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:
        logger.error("apscheduler is not installed; scheduled jobs will not run.")
        return None

    from app.jobs import run_job

    timezone = os.getenv("SCHEDULER_TIMEZONE", DEFAULT_TIMEZONE)
    scheduler = BackgroundScheduler(
        timezone=timezone,
        jobstores=_jobstores(),
        job_defaults={
            # A job that overruns must not stack up behind itself, and a job
            # missed because the process was asleep should not fire on wake.
            "coalesce": True,
            "max_instances": 1,
            "misfire_grace_time": 3600,
        },
    )

    for name, hour, minute, kwargs in NIGHTLY_JOBS:
        scheduler.add_job(
            _run_and_log,
            # `timezone=` is not optional here. A CronTrigger built as an object
            # keeps whatever zone it was constructed with, and the default is
            # the *process* local zone - UTC inside the container - not the
            # scheduler's. Without it every job silently moves to 03:00 IST,
            # i.e. before the NAV feed the 21:30 slot was chosen to follow.
            CronTrigger(hour=hour, minute=minute, day_of_week="mon-sat", timezone=timezone),
            id=name,
            args=[name, kwargs],
            replace_existing=True,
        )

    scheduler.start()
    _scheduler = scheduler
    logger.info(
        "Scheduler started (%s, %s store) with %d jobs: %s",
        timezone, store_kind(), len(NIGHTLY_JOBS),
        ", ".join(n for n, _, _, _ in NIGHTLY_JOBS),
    )
    return scheduler


def store_kind() -> str:
    """Which job store the scheduler is using — "redis" or "memory"."""
    from app import redis_client

    return "redis" if redis_client.is_enabled() else "memory"


def _jobstores() -> Dict[str, Any]:
    """A Redis-backed job store when REDIS_URL is set, else APScheduler's default.

    Falls back rather than fails: a scheduler that refuses to start because an
    optional store is unreachable runs nothing at all, which is strictly worse
    than running from memory until Redis comes back.
    """
    from app import redis_client

    if not redis_client.is_enabled():
        return {}

    try:
        import redis as redis_lib
        from apscheduler.jobstores.redis import RedisJobStore

        store = RedisJobStore(
            jobs_key=redis_client.JOBS_KEY,
            run_times_key=redis_client.RUN_TIMES_KEY,
            connection_pool=redis_lib.ConnectionPool.from_url(redis_client.redis_url()),
        )
        # from_url() does not connect, so touch it here: better to discover a
        # dead Redis now, at start, than at 22:30 with no schedule loaded.
        store.redis.ping()
        return {"default": store}
    except Exception as exc:
        logger.warning(
            "Redis job store unavailable (%s); falling back to in-memory schedule.", exc
        )
        return {}


def _run_and_log(name: str, kwargs: Dict[str, Any]) -> None:
    """Run one job under the cross-process lock, swallowing failures.

    The lock is what makes two containers (api + worker) safe to run the same
    schedule. It is held for the length of the run and expires on its own if
    the process dies mid-job, so a crashed worker cannot wedge tomorrow night.
    """
    from app import redis_client
    from app.jobs import run_job

    with redis_client.lock(f"job:{name}", ttl=LOCK_TTL_SECONDS) as acquired:
        if not acquired:
            logger.info("Job %s already running elsewhere; skipping this fire.", name)
            return
        try:
            result = run_job(name, **kwargs)
            logger.info("Job %s finished: %s", name, result)
        except Exception:
            logger.exception("Job %s failed", name)


def shutdown() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("Scheduler stopped.")


def status() -> Dict[str, Any]:
    """What is scheduled and when it next runs — for the admin route."""
    if _scheduler is None:
        return {
            "running": False,
            "enabled": is_enabled(),
            "jobs": [],
            "job_store": store_kind(),
            "note": (
                "Not running. Either ENABLE_SCHEDULER is off, or no DATABASE_URL "
                "is configured. Trigger jobs manually at POST /api/admin/jobs/{name}."
            ),
        }
    from app import redis_client

    jobs: List[Dict[str, Any]] = [
        {
            "id": job.id,
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
        }
        for job in _scheduler.get_jobs()
    ]
    return {
        "running": True,
        "enabled": True,
        "job_store": store_kind(),
        "redis": redis_client.ping(),
        "jobs": jobs,
    }
