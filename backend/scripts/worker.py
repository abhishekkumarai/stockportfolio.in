"""Scheduler-only process — the nightly jobs, without a web server.

Why a separate container rather than the scheduler thread inside the api:
uvicorn is often run with several workers, and every one of them would import
the same schedule and fire the same job. Splitting them makes ownership
explicit — the api serves requests with `ENABLE_SCHEDULER` off, this process
owns the clock — and the Redis lock in `app.scheduler` covers the rest.

It is the same image and the same code path as `POST /api/admin/jobs/{name}`;
nothing here is worker-only logic.
"""

import logging
import os
import signal
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import scheduler  # noqa: E402

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("worker")

_stop = threading.Event()


def _handle_signal(signum, _frame):
    logger.info("Received signal %s; shutting down.", signum)
    _stop.set()


def main() -> int:
    # The worker exists to schedule, so unlike the api it treats a disabled
    # scheduler as a misconfiguration worth failing on rather than a quiet
    # default. Compose sets ENABLE_SCHEDULER=true for this service only.
    if not scheduler.is_enabled():
        logger.error("ENABLE_SCHEDULER is not true; the worker has nothing to do.")
        return 1

    started = scheduler.start()
    if started is None:
        logger.error("Scheduler did not start (no DATABASE_URL, or apscheduler missing).")
        return 1

    status = scheduler.status()
    logger.info(
        "Worker up: %s job store, %d jobs scheduled.",
        status.get("job_store"), len(status.get("jobs", [])),
    )
    for job in status.get("jobs", []):
        logger.info("  %s -> next run %s", job["id"], job["next_run"])

    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, _handle_signal)

    _stop.wait()
    scheduler.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
