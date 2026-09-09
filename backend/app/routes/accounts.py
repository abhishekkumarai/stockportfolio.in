"""Account, holdings sync, snapshot history and alert-rule routes.

The account model here is deliberately thin: no passwords, no email
verification, no sessions. Creating an account returns an opaque key once; the
browser stores it and sends it as `X-Account-Key`. That is enough to give
nightly jobs a durable portfolio to work on without building a login product
this app has not asked for — and every route below still works without an
account, because the stateless endpoints are unchanged.

All of these answer 503 with a reason when `DATABASE_URL` is unset, rather
than 500ing on a missing engine.
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import alerts as alert_engine
from app import secrets as secret_store
from app.db import get_db, is_enabled
from app.db import repo
from app.db.models import Account, AlertRule
from app.schemas import PortfolioRequest

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/accounts", tags=["Accounts"])


def require_db() -> None:
    if not is_enabled():
        raise HTTPException(
            status_code=503,
            detail=(
                "Persistence is not configured (DATABASE_URL unset). Holdings "
                "continue to work from browser storage via the stateless "
                "/api/portfolio routes."
            ),
        )


def current_account(
    x_account_key: Optional[str] = Header(None),
    session: Session = Depends(get_db),
) -> Account:
    require_db()
    if not x_account_key:
        raise HTTPException(status_code=401, detail="X-Account-Key header is required.")
    account = repo.account_for_key(session, x_account_key)
    if account is None:
        raise HTTPException(status_code=401, detail="Unknown account key.")
    return account


class CreateAccountRequest(BaseModel):
    email: Optional[str] = None
    display_name: Optional[str] = None


class AlertRuleRequest(BaseModel):
    kind: str
    params: Dict[str, Any] = Field(default_factory=dict)
    channel: str = Field("none", description="none | telegram | email")
    target: Optional[str] = None
    active: bool = True


class StoreTokenRequest(BaseModel):
    access_token: str
    broker: str = "fyers"


@router.post("")
def create_account(body: CreateAccountRequest, session: Session = Depends(get_db)):
    """Create an account. The returned `access_key` is shown exactly once."""
    require_db()
    account, key = repo.create_account(session, body.email, body.display_name)
    return {
        "id": account.id,
        "access_key": key,
        "note": (
            "Store this key. Only its hash is kept server-side, so it cannot "
            "be recovered or reset — losing it means creating a new account."
        ),
    }


@router.get("/me")
def whoami(account: Account = Depends(current_account), session: Session = Depends(get_db)):
    request = repo.portfolio_for(session, account)
    return {
        "id": account.id,
        "email": account.email,
        "display_name": account.display_name,
        "created_at": account.created_at.isoformat() if account.created_at else None,
        "holdings": {
            "equity": len(request.equity) if request else 0,
            "funds": len(request.funds) if request else 0,
        },
        "broker_token_stored": repo.broker_token(session, account) is not None,
    }


@router.put("/me/holdings")
def sync_holdings(
    request: PortfolioRequest,
    account: Account = Depends(current_account),
    session: Session = Depends(get_db),
):
    """Replace stored holdings with the posted portfolio.

    Replace, not merge — the browser is the source of truth for the list, so a
    holding deleted locally must not survive here.
    """
    count = repo.replace_holdings(session, account, request)
    return {"stored": count, "equity": len(request.equity), "funds": len(request.funds)}


@router.get("/me/holdings")
def stored_holdings(
    account: Account = Depends(current_account), session: Session = Depends(get_db)
):
    request = repo.portfolio_for(session, account)
    if request is None:
        # Same shape as a stored portfolio, so the browser needs no special
        # case for "account exists but has not synced anything yet".
        return {"equity": [], "funds": [], "cash": 0.0}
    return request.model_dump(mode="json")


@router.post("/me/broker-token")
def store_broker_token(
    body: StoreTokenRequest,
    account: Account = Depends(current_account),
    session: Session = Depends(get_db),
):
    """Persist a Fyers token, encrypted, so nightly jobs can price live.

    Optional and short-lived. Fyers tokens expire daily and refreshing needs
    the account PIN, so this saves a re-login within the same day and nothing
    more — the nightly jobs are built to run without it.
    """
    try:
        credential = repo.store_broker_token(session, account, body.access_token, body.broker)
    except secret_store.EncryptionUnavailable as exc:
        # Refusing is the point: the alternative is a plaintext broker
        # credential in a database column.
        raise HTTPException(status_code=503, detail=str(exc))
    return {
        "broker": credential.broker,
        "expires_at": credential.expires_at.isoformat() if credential.expires_at else None,
    }


@router.get("/me/snapshots")
def snapshot_history(
    limit: int = 365,
    account: Account = Depends(current_account),
    session: Session = Depends(get_db),
):
    """The real equity curve, one point per night the snapshot job ran."""
    curve = repo.equity_curve(session, account, limit)
    return {
        "count": len(curve),
        "curve": curve,
        "note": (
            "Each point is a valuation actually recorded that night, not a "
            "back-projection of today's holdings onto past prices."
        ) if curve else "No snapshots recorded yet; the nightly job has not run.",
    }


@router.get("/me/alerts/rules")
def list_rules(
    account: Account = Depends(current_account), session: Session = Depends(get_db)
):
    rules = repo.active_rules(session, account)
    return {
        "catalogue": alert_engine.available_rules(),
        "rules": [
            {
                "id": rule.id,
                "kind": rule.kind,
                "params": rule.params,
                "channel": rule.channel,
                "target": rule.target,
                "active": rule.active,
                "last_fired_at": rule.last_fired_at.isoformat() if rule.last_fired_at else None,
            }
            for rule in rules
        ],
    }


@router.post("/me/alerts/rules")
def create_rule(
    body: AlertRuleRequest,
    account: Account = Depends(current_account),
    session: Session = Depends(get_db),
):
    if body.kind not in alert_engine.RULES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown rule kind {body.kind!r}. Known: {', '.join(sorted(alert_engine.RULES))}",
        )
    if body.channel not in {"none", "telegram", "email"}:
        raise HTTPException(status_code=400, detail=f"Unsupported channel {body.channel!r}.")

    rule = AlertRule(
        account_id=account.id,
        kind=body.kind,
        params=body.params,
        channel=body.channel,
        target=body.target,
        active=body.active,
    )
    session.add(rule)
    session.flush()
    return {"id": rule.id, "kind": rule.kind}


@router.delete("/me/alerts/rules/{rule_id}")
def delete_rule(
    rule_id: int,
    account: Account = Depends(current_account),
    session: Session = Depends(get_db),
):
    rule = session.get(AlertRule, rule_id)
    if rule is None or rule.account_id != account.id:
        raise HTTPException(status_code=404, detail="Rule not found.")
    session.delete(rule)
    return {"deleted": rule_id}


@router.get("/me/alerts/events")
def alert_events(
    limit: int = 50,
    account: Account = Depends(current_account),
    session: Session = Depends(get_db),
):
    events = repo.recent_alert_events(session, account, limit)
    return {
        "count": len(events),
        "events": [
            {
                "id": event.id,
                "symbol": event.symbol,
                "severity": event.severity,
                "title": event.title,
                "detail": event.detail,
                "fired_at": event.fired_at.isoformat() if event.fired_at else None,
                "delivered": event.delivered,
                "delivery_error": event.delivery_error,
            }
            for event in events
        ],
    }
