"""SQLAlchemy 2.0 models — the durable half of the platform.

Everything through Phase 5 is a pure function of the request body, with
holdings living in the browser's `localStorage`. That works right up to the
point where something has to happen *while nobody is looking*: a nightly
valuation snapshot, an alert that fires at 4pm, a paper trade opened last
Tuesday. None of those can read a browser.

Design notes that matter later:

* **Money is Numeric, never Float.** A float column silently turns ₹1,23,456.78
  into ₹1,23,456.780000001, and a P&L built by summing those drifts. Numeric
  keeps decimal arithmetic exact end to end.
* **Payload columns are JSON, not pickled blobs.** A snapshot's full analysis
  is stored verbatim so a historical row can be re-read by a newer code
  version without a migration, and inspected with plain SQL.
* **Fyers tokens are stored encrypted or not at all** (see `app.secrets`). A
  broker token in a plaintext column is a credential leak waiting for one
  careless database dump.
* **Embeddings are JSON arrays, not a pgvector column.** pgvector is the target
  (Phase 11 concall retrieval), but typing the column as `vector` makes the
  whole schema un-creatable on SQLite, which is what the tests and local dev
  run on. The migration to a native vector column is a Postgres-only concern
  and is left to Alembic.
"""

from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    """Timezone-aware UTC now.

    `datetime.utcnow()` returns a *naive* datetime that claims to be local
    time, and comparing one against an aware timestamp raises. Every timestamp
    in this schema is aware.
    """
    return datetime.now(timezone.utc)


# Money: 18 digits total, 4 after the point. Four is enough for a NAV
# (mfapi quotes 4dp) and for a sub-rupee penny stock.
MONEY = Numeric(18, 4)


class Base(DeclarativeBase):
    pass


class Account(Base):
    """One user. Deliberately minimal — there is no auth product here yet.

    An account is created on first use and identified by an opaque token the
    browser holds, which is enough to give the scheduler something durable to
    attach a portfolio to without building a login flow that nobody asked for.
    """

    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[Optional[str]] = mapped_column(String(320), unique=True)
    password_hash: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    # Hash, never the token itself: a leaked database should not hand over
    # working credentials for every account in it.
    access_key_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    display_name: Mapped[Optional[str]] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    holdings: Mapped[List["Holding"]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )
    snapshots: Mapped[List["PortfolioSnapshot"]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )
    alert_rules: Mapped[List["AlertRule"]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )


class BrokerCredential(Base):
    """An encrypted broker token, so scheduled jobs are not blocked on a browser.

    Fyers access tokens expire daily and refresh tokens need the account PIN,
    so this can never fully automate broker access — it only spares the user a
    re-login inside the same day. Nightly jobs are built to run without it.
    """

    __tablename__ = "broker_credentials"
    __table_args__ = (UniqueConstraint("account_id", "broker", name="uq_broker_per_account"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"))
    broker: Mapped[str] = mapped_column(String(32), default="fyers")
    # Ciphertext. `app.secrets.encrypt` refuses to run without a key, so this
    # column cannot end up holding a readable token.
    access_token_encrypted: Mapped[str] = mapped_column(Text)
    refresh_token_encrypted: Mapped[Optional[str]] = mapped_column(Text)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class Holding(Base):
    """A position, migrated out of `localStorage`.

    `kind` + `key` rather than two nullable foreign keys: an equity's key is
    its NSE symbol and a fund's is its AMFI scheme code, and forcing both into
    one table keeps portfolio aggregation a single query.
    """

    __tablename__ = "holdings"
    __table_args__ = (
        UniqueConstraint("account_id", "kind", "key", name="uq_holding_per_account"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(8))  # "equity" | "fund"
    key: Mapped[str] = mapped_column(String(32))
    quantity: Mapped[float] = mapped_column(MONEY)
    avg_cost: Mapped[float] = mapped_column(MONEY)
    buy_date: Mapped[Optional[date]] = mapped_column(Date)
    source: Mapped[str] = mapped_column(String(16), default="manual")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    account: Mapped[Account] = relationship(back_populates="holdings")


class PortfolioSnapshot(Base):
    """A nightly valuation, which is the only honest source of an equity curve.

    Reconstructing history from today's holdings and past prices assumes the
    holdings never changed, which is exactly the assumption that makes a
    tracker wrong. Recording the real total each night avoids it.
    """

    __tablename__ = "portfolio_snapshots"
    __table_args__ = (
        UniqueConstraint("account_id", "as_of", name="uq_snapshot_per_day"),
        Index("ix_snapshot_account_date", "account_id", "as_of"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"))
    as_of: Mapped[date] = mapped_column(Date)
    invested: Mapped[float] = mapped_column(MONEY)
    current_value: Mapped[float] = mapped_column(MONEY)
    pnl: Mapped[float] = mapped_column(MONEY)
    danger_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    growth_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    holdings_count: Mapped[int] = mapped_column(Integer, default=0)
    payload: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    account: Mapped[Account] = relationship(back_populates="snapshots")


class FundamentalSnapshot(Base):
    """Nightly fundamentals per symbol, so a scrape outage is not a data gap.

    Also the only way to see *change* — a debt-to-equity that doubled matters
    far more than its level, and the live scraper only ever knows today.
    """

    __tablename__ = "fundamental_snapshots"
    __table_args__ = (
        UniqueConstraint("symbol", "as_of", name="uq_fundamental_per_day"),
        Index("ix_fundamental_symbol_date", "symbol", "as_of"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32))
    as_of: Mapped[date] = mapped_column(Date)
    source: Mapped[Optional[str]] = mapped_column(String(16))
    score: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    payload: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ScreenerRun(Base):
    """A stored universe scan, so the morning's ranking survives the process."""

    __tablename__ = "screener_runs"
    __table_args__ = (Index("ix_screener_index_date", "index_name", "as_of"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    as_of: Mapped[date] = mapped_column(Date)
    index_name: Mapped[str] = mapped_column(String(32))
    scanned: Mapped[int] = mapped_column(Integer, default=0)
    matched: Mapped[int] = mapped_column(Integer, default=0)
    payload: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AlertRule(Base):
    """A standing condition to evaluate nightly against a user's holdings."""

    __tablename__ = "alert_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(48))
    params: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    channel: Mapped[str] = mapped_column(String(16), default="none")  # none|telegram|email
    target: Mapped[Optional[str]] = mapped_column(String(320))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Stops one persistently-breached condition from mailing the user nightly
    # forever; `alerts.py` treats a rule as silent for a cooldown window.
    last_fired_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    account: Mapped[Account] = relationship(back_populates="alert_rules")
    events: Mapped[List["AlertEvent"]] = relationship(
        back_populates="rule", cascade="all, delete-orphan"
    )


class AlertEvent(Base):
    """One firing of a rule. Kept even when delivery fails, so it is auditable."""

    __tablename__ = "alert_events"
    __table_args__ = (Index("ix_alert_event_fired", "rule_id", "fired_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rule_id: Mapped[int] = mapped_column(ForeignKey("alert_rules.id", ondelete="CASCADE"))
    symbol: Mapped[Optional[str]] = mapped_column(String(32))
    severity: Mapped[str] = mapped_column(String(16), default="WARNING")
    title: Mapped[str] = mapped_column(String(256))
    detail: Mapped[Optional[str]] = mapped_column(Text)
    fired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    delivered: Mapped[bool] = mapped_column(Boolean, default=False)
    delivery_error: Mapped[Optional[str]] = mapped_column(Text)

    rule: Mapped[AlertRule] = relationship(back_populates="events")


# ---- paper trading (Phase 10) --------------------------------------------


class PaperAccount(Base):
    """A simulated broker account. Never connected to a live order API."""

    __tablename__ = "paper_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(120))
    strategy: Mapped[Optional[str]] = mapped_column(String(64))
    strategy_params: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    initial_capital: Mapped[float] = mapped_column(MONEY)
    cash: Mapped[float] = mapped_column(MONEY)
    # The backtest that justified deploying this strategy. Divergence between
    # it and live paper performance is the whole point of the ledger.
    backtest_reference: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    positions: Mapped[List["PaperPosition"]] = relationship(
        back_populates="paper_account", cascade="all, delete-orphan"
    )
    orders: Mapped[List["PaperOrder"]] = relationship(
        back_populates="paper_account", cascade="all, delete-orphan"
    )


class PaperPosition(Base):
    __tablename__ = "paper_positions"
    __table_args__ = (
        UniqueConstraint("paper_account_id", "symbol", name="uq_paper_position"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    paper_account_id: Mapped[int] = mapped_column(
        ForeignKey("paper_accounts.id", ondelete="CASCADE")
    )
    symbol: Mapped[str] = mapped_column(String(32))
    quantity: Mapped[float] = mapped_column(MONEY, default=0)
    avg_cost: Mapped[float] = mapped_column(MONEY, default=0)
    realised_pnl: Mapped[float] = mapped_column(MONEY, default=0)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    paper_account: Mapped[PaperAccount] = relationship(back_populates="positions")


class PaperOrder(Base):
    """An immutable fill record. Append-only: the ledger is the audit trail."""

    __tablename__ = "paper_orders"
    __table_args__ = (Index("ix_paper_order_account_time", "paper_account_id", "filled_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    paper_account_id: Mapped[int] = mapped_column(
        ForeignKey("paper_accounts.id", ondelete="CASCADE")
    )
    symbol: Mapped[str] = mapped_column(String(32))
    side: Mapped[str] = mapped_column(String(4))  # BUY | SELL
    quantity: Mapped[float] = mapped_column(MONEY)
    price: Mapped[float] = mapped_column(MONEY)
    fees: Mapped[float] = mapped_column(MONEY, default=0)
    realised_pnl: Mapped[float] = mapped_column(MONEY, default=0)
    reason: Mapped[Optional[str]] = mapped_column(Text)
    signal_id: Mapped[Optional[int]] = mapped_column(Integer)
    filled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    paper_account: Mapped[PaperAccount] = relationship(back_populates="orders")


class Signal(Base):
    """A generated signal, recorded whether or not it was acted on.

    Storing rejected signals too is what makes signal-versus-execution
    attribution possible: without them you only ever measure the trades you
    took, which flatters the strategy.
    """

    __tablename__ = "signals"
    __table_args__ = (Index("ix_signal_symbol_time", "symbol", "generated_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    paper_account_id: Mapped[Optional[int]] = mapped_column(Integer)
    symbol: Mapped[str] = mapped_column(String(32))
    action: Mapped[str] = mapped_column(String(16))
    score: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    conviction: Mapped[Optional[str]] = mapped_column(String(8))
    reference_price: Mapped[Optional[float]] = mapped_column(MONEY)
    executed: Mapped[bool] = mapped_column(Boolean, default=False)
    skip_reason: Mapped[Optional[str]] = mapped_column(Text)
    evidence: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# ---- AI retrieval (Phase 11) ---------------------------------------------


class DocumentChunk(Base):
    """A chunk of a concall transcript or filing, plus its embedding.

    The embedding is a JSON float array so the schema also creates on SQLite.
    On Postgres, Alembic converts this column to `vector` and adds an ivfflat
    index; the retrieval code reads either shape.
    """

    __tablename__ = "document_chunks"
    __table_args__ = (Index("ix_chunk_symbol", "symbol", "doc_type"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32))
    doc_type: Mapped[str] = mapped_column(String(32))  # concall | filing | presentation
    period: Mapped[Optional[str]] = mapped_column(String(16))  # e.g. "FY26Q1"
    source_url: Mapped[Optional[str]] = mapped_column(Text)
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[Optional[List[float]]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
