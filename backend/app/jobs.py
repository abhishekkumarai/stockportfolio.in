"""Nightly jobs — the work that happens while nobody is looking.

Every job is a plain function returning a JSON-serialisable summary, so the
same code runs from the scheduler, from a Render cron hitting
`POST /api/admin/jobs/{name}`, and from a test. None of them take a request.

The hard constraint the PRD calls out: **a scheduled job cannot use a user's
Fyers token.** Tokens expire daily and refreshing needs the account PIN, so
overnight work runs on yfinance and mfapi.in only. A stored token is used when
one happens to still be valid, and its absence is never an error.
"""

import logging
from datetime import date
from typing import Any, Callable, Dict, List, Optional

from app import symbols as symbol_master
from app.db import is_enabled, session_scope
from app.db import repo
from app.fyers_client import FyersClient, FyersError
from app.portfolio import value_portfolio
from app.quant.growth import evaluate_portfolio_growth
from app.quant.risk import evaluate_portfolio_danger

logger = logging.getLogger(__name__)

JOBS: Dict[str, Callable[..., Dict[str, Any]]] = {}


def job(name: str):
    def register(fn):
        JOBS[name] = fn
        return fn

    return register


class PersistenceRequired(RuntimeError):
    """Raised when a job needs a database and none is configured."""


def _require_db() -> None:
    if not is_enabled():
        raise PersistenceRequired(
            "DATABASE_URL is not configured, so scheduled jobs have nowhere to "
            "write. Set it to enable snapshots, alerts and paper trading."
        )


def _client_for(token: Optional[str]) -> Optional[FyersClient]:
    """A Fyers client from a stored token, or None. Never fatal."""
    if not token:
        return None
    try:
        return FyersClient(access_token=token)
    except FyersError as exc:
        logger.info("Stored Fyers token unusable: %s", exc)
        return None


# ---- jobs ----------------------------------------------------------------


@job("portfolio_snapshot")
def portfolio_snapshot(as_of: Optional[date] = None) -> Dict[str, Any]:
    """Value and analyse every account's portfolio, one row per account per day.

    This is what turns a portfolio tracker into a portfolio *history*. Without
    it the equity curve can only be reconstructed by assuming today's holdings
    were always held, which is precisely the assumption that makes such a
    reconstruction wrong.
    """
    _require_db()
    written, failed = 0, 0

    with session_scope() as session:
        accounts = repo.all_accounts(session)
        for account in accounts:
            try:
                request = repo.portfolio_for(session, account)
                if request is None:
                    continue
                client = _client_for(repo.broker_token(session, account))
                valuation = value_portfolio(request, client)
                holdings = valuation.get("holdings", [])
                total = (valuation.get("totals") or {}).get("current_value", 0.0)

                analysis = {
                    "valuation": valuation,
                    "danger": evaluate_portfolio_danger(holdings, total, request.cash),
                    "growth": evaluate_portfolio_growth(holdings, total),
                }
                repo.record_snapshot(session, account, analysis, as_of=as_of)
                written += 1
            except Exception:
                logger.exception("Snapshot failed for account %s", account.id)
                failed += 1

    return {"job": "portfolio_snapshot", "accounts": len(accounts), "written": written, "failed": failed}


@job("fundamentals_refresh")
def fundamentals_refresh(
    index: str = "NIFTY500", limit: int = 150
) -> Dict[str, Any]:
    """Re-scrape fundamentals for the universe and store a dated snapshot.

    Bounded by `limit` because each miss is a live page fetch. Over successive
    nights the cache and the snapshot table fill in; a single run is not
    expected to cover the index.
    """
    _require_db()
    from app.fundamentals import get_fundamentals, score_fundamentals

    records = symbol_master.universe(index=index, limit=limit)
    stored, unavailable = 0, 0

    with session_scope() as session:
        for record in records:
            try:
                payload = get_fundamentals(record.symbol)
                if not payload.get("available"):
                    unavailable += 1
                    continue
                card = score_fundamentals(payload)
                repo.record_fundamentals(session, record.symbol, payload, card.score)
                stored += 1
            except Exception:
                logger.exception("Fundamentals refresh failed for %s", record.symbol)
                unavailable += 1

    return {
        "job": "fundamentals_refresh",
        "index": index,
        "attempted": len(records),
        "stored": stored,
        "unavailable": unavailable,
    }


@job("screener_rescan")
def screener_rescan(index: str = "NIFTY500", universe_limit: int = 250) -> Dict[str, Any]:
    """Rerun the universe scan overnight so the morning ranking is warm."""
    _require_db()
    from app.screener import ScreenFilters, run_screen

    result = run_screen(
        filters=ScreenFilters(index=index),
        limit=100,
        universe_limit=universe_limit,
        with_fundamentals=True,
        fundamental_limit=80,
    )
    with session_scope() as session:
        repo.record_screener_run(session, index, result)

    return {
        "job": "screener_rescan",
        "index": index,
        "scanned": result.get("scanned"),
        "matched": result.get("count"),
    }


@job("evaluate_alerts")
def evaluate_alerts() -> Dict[str, Any]:
    """Evaluate every active rule against each account's latest snapshot.

    Runs off the stored snapshot rather than revaluing: the snapshot job has
    already done that work minutes earlier, and re-pricing here would double
    the upstream load to produce the same numbers.
    """
    _require_db()
    from app import alerts

    fired, delivered, delivery_errors = 0, 0, 0

    with session_scope() as session:
        for account in repo.all_accounts(session):
            history = repo.snapshots(session, account, limit=1)
            if not history:
                continue
            analysis = history[0].payload or {}

            for rule in repo.active_rules(session, account):
                cooldown = float((rule.params or {}).get("cooldown_hours", alerts.DEFAULT_COOLDOWN_HOURS))
                if alerts.in_cooldown(rule.last_fired_at, cooldown):
                    continue

                findings = alerts.evaluate(rule.kind, analysis, rule.params or {})
                if not findings:
                    continue

                events = [
                    repo.record_alert_event(
                        session, rule, f.title, f.detail, f.severity, f.symbol
                    )
                    for f in findings
                ]
                fired += len(events)

                try:
                    alerts.deliver(rule.channel, rule.target, findings)
                    for event in events:
                        event.delivered = True
                    delivered += len(events)
                except Exception as exc:
                    # The finding is already persisted; only delivery failed.
                    logger.warning("Alert delivery failed for rule %s: %s", rule.id, exc)
                    for event in events:
                        event.delivery_error = str(exc)
                    delivery_errors += len(events)

    return {
        "job": "evaluate_alerts",
        "fired": fired,
        "delivered": delivered,
        "delivery_errors": delivery_errors,
    }


@job("paper_mark_to_market")
def paper_mark_to_market() -> Dict[str, Any]:
    """Re-price every open paper position against the latest close."""
    _require_db()
    from app.paper.runner import mark_all_to_market

    return mark_all_to_market()


def run_job(name: str, **kwargs: Any) -> Dict[str, Any]:
    """Dispatch by name. Unknown names raise rather than silently no-op."""
    fn = JOBS.get(name)
    if fn is None:
        raise KeyError(f"Unknown job {name!r}. Known: {', '.join(sorted(JOBS))}")
    logger.info("Running job %s", name)
    return fn(**kwargs)


def job_names() -> List[str]:
    return sorted(JOBS)
