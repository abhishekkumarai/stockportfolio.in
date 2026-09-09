"""Query helpers over the models — the only place raw SQLAlchemy is written.

Routes and jobs call these instead of building queries inline, so that "the
latest snapshot" or "this account's holdings as a PortfolioRequest" has one
definition. The conversion back into the Pydantic request models matters most:
everything downstream of Phase 1 takes a `PortfolioRequest`, and a stored
portfolio has to enter that same pipeline rather than a parallel one.
"""

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app import secrets as secret_store
from app.db.models import (
    Account,
    AlertEvent,
    AlertRule,
    BrokerCredential,
    DocumentChunk,
    FundamentalSnapshot,
    Holding,
    PortfolioSnapshot,
    ScreenerRun,
    utcnow,
)
from app.schemas import EquityHolding, FundHolding, PortfolioRequest

logger = logging.getLogger(__name__)


# ---- accounts ------------------------------------------------------------


def create_account(session: Session, email: Optional[str] = None,
                   display_name: Optional[str] = None) -> tuple[Account, str]:
    """Create an account and return it with its one-time plaintext access key.

    The key is returned exactly once, here. It is not recoverable afterwards
    because only its hash is stored.
    """
    key = secret_store.new_access_key()
    account = Account(
        email=email,
        display_name=display_name,
        access_key_hash=secret_store.hash_access_key(key),
        last_seen_at=utcnow(),
    )
    session.add(account)
    session.flush()
    return account, key


def account_for_key(session: Session, key: str) -> Optional[Account]:
    if not key:
        return None
    account = session.scalar(
        select(Account).where(Account.access_key_hash == secret_store.hash_access_key(key))
    )
    if account is not None:
        account.last_seen_at = utcnow()
    return account


def all_accounts(session: Session) -> List[Account]:
    return list(session.scalars(select(Account)))


# ---- holdings ------------------------------------------------------------


def replace_holdings(session: Session, account: Account, request: PortfolioRequest) -> int:
    """Overwrite an account's holdings with a posted portfolio.

    Replace rather than merge: the browser owns the list, so a holding the user
    deleted locally has to disappear here too. Merging would resurrect it on
    the next sync.
    """
    session.execute(delete(Holding).where(Holding.account_id == account.id))

    rows: List[Holding] = []
    for equity in request.equity:
        rows.append(
            Holding(
                account_id=account.id,
                kind="equity",
                key=equity.symbol,
                quantity=equity.quantity,
                avg_cost=equity.avg_cost,
                buy_date=equity.buy_date,
                source=equity.source,
            )
        )
    for fund in request.funds:
        rows.append(
            Holding(
                account_id=account.id,
                kind="fund",
                key=str(fund.scheme_code),
                quantity=fund.units,
                avg_cost=fund.avg_nav,
                buy_date=fund.buy_date,
            )
        )
    session.add_all(rows)
    session.flush()
    return len(rows)


def portfolio_for(
    session: Session, account: Account, cash: float = 0.0
) -> Optional[PortfolioRequest]:
    """Rehydrate stored holdings into the request model the engines expect.

    None when the account holds nothing. `PortfolioRequest` rejects an empty
    portfolio - correct for an incoming API request, where an empty body is a
    mistake - but a freshly created account legitimately has no holdings yet,
    and that must not surface as a 500.
    """
    rows = list(
        session.scalars(select(Holding).where(Holding.account_id == account.id))
    )

    equity: List[EquityHolding] = []
    funds: List[FundHolding] = []
    for row in rows:
        try:
            if row.kind == "equity":
                equity.append(
                    EquityHolding(
                        symbol=row.key,
                        quantity=float(row.quantity),
                        avg_cost=float(row.avg_cost),
                        buy_date=row.buy_date,
                        source=row.source,  # type: ignore[arg-type]
                    )
                )
            else:
                funds.append(
                    FundHolding(
                        scheme_code=int(row.key),
                        units=float(row.quantity),
                        avg_nav=float(row.avg_cost),
                        buy_date=row.buy_date,
                    )
                )
        except (ValueError, TypeError) as exc:
            # One unparseable row should not take the whole portfolio down.
            logger.warning("Skipping malformed holding %s/%s: %s", row.kind, row.key, exc)

    if not equity and not funds:
        return None

    return PortfolioRequest(equity=equity, funds=funds, cash=cash)


# ---- broker credentials --------------------------------------------------


def store_broker_token(
    session: Session,
    account: Account,
    access_token: str,
    broker: str = "fyers",
    ttl_hours: int = 20,
) -> BrokerCredential:
    """Encrypt and persist a broker token. Raises if encryption is unavailable.

    `ttl_hours` defaults to 20 rather than 24: Fyers tokens expire at a fixed
    hour, not 24 hours after issue, so treating one as valid for a full day
    guarantees a window where jobs authenticate with a dead token.
    """
    ciphertext = secret_store.encrypt(access_token)
    existing = session.scalar(
        select(BrokerCredential).where(
            BrokerCredential.account_id == account.id,
            BrokerCredential.broker == broker,
        )
    )
    expires = datetime.now(timezone.utc) + timedelta(hours=ttl_hours)

    if existing is None:
        existing = BrokerCredential(account_id=account.id, broker=broker)
        session.add(existing)
    existing.access_token_encrypted = ciphertext
    existing.expires_at = expires
    session.flush()
    return existing


def broker_token(session: Session, account: Account, broker: str = "fyers") -> Optional[str]:
    """The stored token if it exists and has not expired, else None."""
    credential = session.scalar(
        select(BrokerCredential).where(
            BrokerCredential.account_id == account.id,
            BrokerCredential.broker == broker,
        )
    )
    if credential is None:
        return None
    if credential.expires_at and credential.expires_at < datetime.now(timezone.utc):
        return None
    try:
        return secret_store.decrypt(credential.access_token_encrypted)
    except secret_store.EncryptionUnavailable as exc:
        logger.warning("Stored %s token unusable for account %s: %s", broker, account.id, exc)
        return None


# ---- snapshots -----------------------------------------------------------


def record_snapshot(
    session: Session,
    account: Account,
    analysis: Dict[str, Any],
    as_of: Optional[date] = None,
) -> PortfolioSnapshot:
    """Upsert today's valuation snapshot for an account.

    Upsert, not insert: a job that reruns after a partial failure must not
    leave two rows for one day, which would double-count that day in the
    equity curve.
    """
    as_of = as_of or date.today()
    totals = (analysis.get("valuation") or {}).get("totals") or {}

    snapshot = session.scalar(
        select(PortfolioSnapshot).where(
            PortfolioSnapshot.account_id == account.id,
            PortfolioSnapshot.as_of == as_of,
        )
    )
    if snapshot is None:
        snapshot = PortfolioSnapshot(account_id=account.id, as_of=as_of)
        session.add(snapshot)

    snapshot.invested = totals.get("invested") or 0.0
    snapshot.current_value = totals.get("current_value") or 0.0
    snapshot.pnl = totals.get("pnl") or 0.0
    snapshot.holdings_count = totals.get("holdings") or 0
    snapshot.danger_score = (analysis.get("danger") or {}).get("danger_score")
    snapshot.growth_score = (analysis.get("growth") or {}).get("growth_score")
    snapshot.payload = analysis
    session.flush()
    return snapshot


def snapshots(
    session: Session, account: Account, limit: int = 365
) -> List[PortfolioSnapshot]:
    """Newest first, capped. The equity curve reverses this for charting."""
    return list(
        session.scalars(
            select(PortfolioSnapshot)
            .where(PortfolioSnapshot.account_id == account.id)
            .order_by(PortfolioSnapshot.as_of.desc())
            .limit(limit)
        )
    )


def equity_curve(session: Session, account: Account, limit: int = 365) -> List[Dict[str, Any]]:
    rows = sorted(snapshots(session, account, limit), key=lambda s: s.as_of)
    return [
        {
            "date": row.as_of.isoformat(),
            "invested": float(row.invested),
            "current_value": float(row.current_value),
            "pnl": float(row.pnl),
            "danger_score": float(row.danger_score) if row.danger_score is not None else None,
            "growth_score": float(row.growth_score) if row.growth_score is not None else None,
        }
        for row in rows
    ]


# ---- fundamentals & screener runs ----------------------------------------


def record_fundamentals(
    session: Session, symbol: str, payload: Dict[str, Any],
    score: Optional[float] = None, as_of: Optional[date] = None,
) -> FundamentalSnapshot:
    as_of = as_of or date.today()
    row = session.scalar(
        select(FundamentalSnapshot).where(
            FundamentalSnapshot.symbol == symbol,
            FundamentalSnapshot.as_of == as_of,
        )
    )
    if row is None:
        row = FundamentalSnapshot(symbol=symbol, as_of=as_of)
        session.add(row)
    row.source = payload.get("source")
    row.score = score
    row.payload = payload
    session.flush()
    return row


def fundamental_history(
    session: Session, symbol: str, limit: int = 90
) -> List[FundamentalSnapshot]:
    return list(
        session.scalars(
            select(FundamentalSnapshot)
            .where(FundamentalSnapshot.symbol == symbol)
            .order_by(FundamentalSnapshot.as_of.desc())
            .limit(limit)
        )
    )


def record_screener_run(
    session: Session, index_name: str, result: Dict[str, Any],
    as_of: Optional[date] = None,
) -> ScreenerRun:
    run = ScreenerRun(
        as_of=as_of or date.today(),
        index_name=index_name,
        scanned=result.get("scanned") or 0,
        matched=result.get("count") or 0,
        payload=result,
    )
    session.add(run)
    session.flush()
    return run


def latest_screener_run(session: Session, index_name: str) -> Optional[ScreenerRun]:
    return session.scalar(
        select(ScreenerRun)
        .where(ScreenerRun.index_name == index_name)
        .order_by(ScreenerRun.as_of.desc(), ScreenerRun.id.desc())
        .limit(1)
    )


# ---- alerts --------------------------------------------------------------


def active_rules(session: Session, account: Optional[Account] = None) -> List[AlertRule]:
    query = select(AlertRule).where(AlertRule.active.is_(True))
    if account is not None:
        query = query.where(AlertRule.account_id == account.id)
    return list(session.scalars(query))


def record_alert_event(
    session: Session, rule: AlertRule, title: str, detail: str,
    severity: str = "WARNING", symbol: Optional[str] = None,
) -> AlertEvent:
    event = AlertEvent(
        rule_id=rule.id,
        symbol=symbol,
        severity=severity,
        title=title,
        detail=detail,
    )
    session.add(event)
    rule.last_fired_at = utcnow()
    session.flush()
    return event


def recent_alert_events(
    session: Session, account: Account, limit: int = 50
) -> List[AlertEvent]:
    return list(
        session.scalars(
            select(AlertEvent)
            .join(AlertRule, AlertEvent.rule_id == AlertRule.id)
            .where(AlertRule.account_id == account.id)
            .order_by(AlertEvent.fired_at.desc())
            .limit(limit)
        )
    )


# ---- document chunks -----------------------------------------------------


def add_document_chunks(session: Session, chunks: Sequence[DocumentChunk]) -> int:
    session.add_all(list(chunks))
    session.flush()
    return len(chunks)


def chunks_for_symbol(
    session: Session, symbol: str, doc_type: Optional[str] = None, limit: int = 500
) -> List[DocumentChunk]:
    query = select(DocumentChunk).where(DocumentChunk.symbol == symbol)
    if doc_type:
        query = query.where(DocumentChunk.doc_type == doc_type)
    return list(session.scalars(query.limit(limit)))
