"""Job triggering and scheduler status.

Guarded by a shared secret in `X-Admin-Token`, because these endpoints run
scraping work and send alerts. If `ADMIN_TOKEN` is unset the routes refuse
everything rather than defaulting open — an unauthenticated endpoint that
launches a 250-symbol scrape is a denial-of-service button with a URL.

The intended production setup is a Render cron job (or any external
scheduler) calling these on a timetable, which works on a service that sleeps
between requests. See `app/scheduler.py` for the in-process alternative.
"""

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, Header, HTTPException

from app import redis_client
from app import scheduler as scheduler_module
from app import secrets as secret_store
from app.db import is_enabled as db_enabled
from app.jobs import PersistenceRequired, job_names, run_job

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["Admin"])


def require_admin(x_admin_token: Optional[str] = Header(None)) -> None:
    expected = secret_store.admin_token()
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="ADMIN_TOKEN is not configured, so admin endpoints are disabled.",
        )
    if not x_admin_token or not secret_store.constant_time_equals(x_admin_token, expected):
        raise HTTPException(status_code=401, detail="Invalid or missing X-Admin-Token.")


@router.get("/jobs", dependencies=[Depends(require_admin)])
def list_jobs():
    return {
        "jobs": job_names(),
        "database_configured": db_enabled(),
        "redis": redis_client.ping(),
        "scheduler": scheduler_module.status(),
    }


@router.post("/jobs/{name}", dependencies=[Depends(require_admin)])
def trigger_job(name: str, params: Dict[str, Any] = Body(default_factory=dict)):
    """Run a job synchronously and return its summary.

    Synchronous on purpose: the caller is a cron job that wants a non-2xx when
    the work failed. A fire-and-forget 202 would report success for a job that
    crashed thirty seconds later.

    Takes the same Redis lock the scheduler does, so an external cron firing at
    22:30 and the worker's own 22:30 trigger cannot run the job twice; the
    loser gets a 409 rather than a duplicate run.
    """
    try:
        with redis_client.lock(f"job:{name}", ttl=scheduler_module.LOCK_TTL_SECONDS) as got:
            if not got:
                raise HTTPException(
                    status_code=409,
                    detail=f"Job {name} is already running (lock held elsewhere).",
                )
            return run_job(name, **params)
    except HTTPException:
        raise
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PersistenceRequired as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except TypeError as exc:
        raise HTTPException(status_code=400, detail=f"Bad parameters for job {name}: {exc}")
    except Exception as exc:
        logger.exception("Job %s failed", name)
        raise HTTPException(status_code=500, detail=f"Job {name} failed: {exc}")


@router.get("/scheduler", dependencies=[Depends(require_admin)])
def scheduler_status():
    return scheduler_module.status()
