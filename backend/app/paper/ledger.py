"""The paper-trading ledger: virtual cash, positions and an append-only order log.

Two properties are non-negotiable here.

**It cannot place a real order.** Nothing in this package imports the Fyers
order API, and `FyersClient` does not implement one — the client is market-data
and login only. Read-only execution is an architectural property of this
codebase, not a runtime check that could be bypassed by a flag.

**The order log is append-only.** A fill is never edited or deleted; positions
are derived state that can be rebuilt from the orders. That is what makes the
ledger an audit trail rather than a scoreboard, and it is the difference
between "this strategy returned 14%" and "this strategy returned 14% and here
is every trade that produced it".

Costs use the same `CostModel` as the backtester, so paper performance and the
backtest that justified deploying the strategy are measured on identical
assumptions. Comparing a cost-free paper run against a cost-modelled backtest
would make every strategy look like it improved out of sample.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Account,
    PaperAccount,
    PaperOrder,
    PaperPosition,
    Signal,
    utcnow,
)
from app.engine.broker import CostModel, Side

logger = logging.getLogger(__name__)

DEFAULT_COSTS = CostModel()


class InsufficientFunds(RuntimeError):
    """Raised when a paper buy exceeds virtual cash."""


class NoPosition(RuntimeError):
    """Raised when a paper sell exceeds the held quantity."""


def open_account(
    session: Session,
    account: Account,
    name: str,
    initial_capital: float,
    strategy: Optional[str] = None,
    strategy_params: Optional[Dict[str, Any]] = None,
    backtest_reference: Optional[Dict[str, Any]] = None,
) -> PaperAccount:
    """Create a paper account, optionally bound to a backtested strategy.

    `backtest_reference` is the whole point of the binding: it records what the
    strategy was *expected* to do, so divergence can be measured later. A paper
    account with no reference can only report its own return, which tells you
    nothing about whether the backtest was honest.
    """
    if initial_capital <= 0:
        raise ValueError("Initial capital must be positive.")

    paper = PaperAccount(
        account_id=account.id,
        name=name,
        strategy=strategy,
        strategy_params=strategy_params or {},
        initial_capital=initial_capital,
        cash=initial_capital,
        backtest_reference=backtest_reference or {},
    )
    session.add(paper)
    session.flush()
    return paper


def get_account(session: Session, account: Account, paper_id: int) -> Optional[PaperAccount]:
    paper = session.get(PaperAccount, paper_id)
    if paper is None or paper.account_id != account.id:
        return None
    return paper


def list_accounts(session: Session, account: Account) -> List[PaperAccount]:
    return list(
        session.scalars(select(PaperAccount).where(PaperAccount.account_id == account.id))
    )


def position_for(session: Session, paper: PaperAccount, symbol: str) -> PaperPosition:
    position = session.scalar(
        select(PaperPosition).where(
            PaperPosition.paper_account_id == paper.id,
            PaperPosition.symbol == symbol,
        )
    )
    if position is None:
        position = PaperPosition(paper_account_id=paper.id, symbol=symbol)
        session.add(position)
        session.flush()
    return position


def execute(
    session: Session,
    paper: PaperAccount,
    symbol: str,
    side: str,
    quantity: float,
    price: float,
    reason: str = "",
    signal_id: Optional[int] = None,
    costs: Optional[CostModel] = None,
) -> PaperOrder:
    """Record a simulated fill and update cash and the position.

    Raises rather than partially filling: a paper ledger that quietly shrinks
    an order teaches the wrong lesson about a strategy that outgrew its
    capital.
    """
    if quantity <= 0 or price <= 0:
        raise ValueError("Quantity and price must be positive.")

    costs = costs or DEFAULT_COSTS
    enum_side = Side.BUY if side.upper() == "BUY" else Side.SELL
    turnover = quantity * price
    fees = costs.charges(turnover, enum_side)
    position = position_for(session, paper, symbol)
    realised = 0.0

    if enum_side is Side.BUY:
        if turnover + fees > float(paper.cash):
            raise InsufficientFunds(
                f"Buy of {quantity} {symbol} at {price:.2f} costs "
                f"{turnover + fees:,.2f} but only {float(paper.cash):,.2f} is available."
            )
        total_cost = float(position.avg_cost) * float(position.quantity) + turnover
        position.quantity = float(position.quantity) + quantity
        position.avg_cost = total_cost / float(position.quantity)
        paper.cash = float(paper.cash) - turnover - fees
    else:
        if quantity > float(position.quantity):
            raise NoPosition(
                f"Sell of {quantity} {symbol} exceeds the held {float(position.quantity)}. "
                "Shorting is not modelled."
            )
        realised = (price - float(position.avg_cost)) * quantity - fees
        position.quantity = float(position.quantity) - quantity
        position.realised_pnl = float(position.realised_pnl) + realised
        if position.quantity <= 1e-9:
            position.quantity = 0.0
            position.avg_cost = 0.0
        paper.cash = float(paper.cash) + turnover - fees

    order = PaperOrder(
        paper_account_id=paper.id,
        symbol=symbol,
        side=enum_side.value,
        quantity=quantity,
        price=price,
        fees=fees,
        realised_pnl=realised,
        reason=reason,
        signal_id=signal_id,
    )
    session.add(order)
    session.flush()
    return order


def record_signal(
    session: Session,
    symbol: str,
    action: str,
    paper_account_id: Optional[int] = None,
    score: Optional[float] = None,
    conviction: Optional[str] = None,
    reference_price: Optional[float] = None,
    executed: bool = False,
    skip_reason: Optional[str] = None,
    evidence: Optional[Dict[str, Any]] = None,
) -> Signal:
    """Persist a generated signal, executed or not.

    Recording the skipped ones is what makes attribution honest. Measuring only
    the trades that were taken answers "how did my executions do", never "was
    the signal any good" — and the gap between those two is exactly what a
    paper ledger exists to expose.
    """
    signal = Signal(
        paper_account_id=paper_account_id,
        symbol=symbol,
        action=action,
        score=score,
        conviction=conviction,
        reference_price=reference_price,
        executed=executed,
        skip_reason=skip_reason,
        evidence=evidence or {},
    )
    session.add(signal)
    session.flush()
    return signal


def valuation(
    session: Session, paper: PaperAccount, prices: Dict[str, float]
) -> Dict[str, Any]:
    """Mark the account to the supplied prices and summarise it.

    A position whose symbol is missing from `prices` is reported at cost with a
    warning rather than dropped — silently excluding it would overstate the
    return on everything else.
    """
    positions = list(
        session.scalars(
            select(PaperPosition).where(
                PaperPosition.paper_account_id == paper.id,
                PaperPosition.quantity > 0,
            )
        )
    )

    rows: List[Dict[str, Any]] = []
    holdings_value = 0.0
    warnings: List[str] = []

    for position in positions:
        quantity = float(position.quantity)
        cost = float(position.avg_cost)
        price = prices.get(position.symbol)
        if price is None:
            price = cost
            warnings.append(f"{position.symbol}: no price available, valued at cost.")
        value = quantity * price
        holdings_value += value
        rows.append(
            {
                "symbol": position.symbol,
                "quantity": round(quantity, 4),
                "avg_cost": round(cost, 2),
                "price": round(price, 2),
                "value": round(value, 2),
                "unrealised_pnl": round((price - cost) * quantity, 2),
                "unrealised_pnl_pct": round((price / cost - 1.0) * 100.0, 2) if cost else None,
                "realised_pnl": round(float(position.realised_pnl), 2),
            }
        )

    cash = float(paper.cash)
    initial = float(paper.initial_capital)
    equity = cash + holdings_value
    realised = sum(float(p.realised_pnl) for p in positions)

    orders = list(
        session.scalars(
            select(PaperOrder).where(PaperOrder.paper_account_id == paper.id)
        )
    )
    closed_realised = sum(float(order.realised_pnl) for order in orders)

    return {
        "paper_account_id": paper.id,
        "name": paper.name,
        "strategy": paper.strategy,
        "initial_capital": round(initial, 2),
        "cash": round(cash, 2),
        "holdings_value": round(holdings_value, 2),
        "equity": round(equity, 2),
        "total_return_inr": round(equity - initial, 2),
        "total_return_pct": round((equity / initial - 1.0) * 100.0, 2) if initial else None,
        "realised_pnl_inr": round(closed_realised, 2),
        "unrealised_pnl_inr": round(sum(r["unrealised_pnl"] for r in rows), 2),
        "open_positions": rows,
        "order_count": len(orders),
        "total_fees_inr": round(sum(float(order.fees) for order in orders), 2),
        "warnings": warnings,
    }


def order_log(session: Session, paper: PaperAccount, limit: int = 200) -> List[Dict[str, Any]]:
    orders = list(
        session.scalars(
            select(PaperOrder)
            .where(PaperOrder.paper_account_id == paper.id)
            .order_by(PaperOrder.filled_at.desc())
            .limit(limit)
        )
    )
    return [
        {
            "id": order.id,
            "symbol": order.symbol,
            "side": order.side,
            "quantity": round(float(order.quantity), 4),
            "price": round(float(order.price), 2),
            "fees": round(float(order.fees), 2),
            "realised_pnl": round(float(order.realised_pnl), 2),
            "reason": order.reason,
            "signal_id": order.signal_id,
            "filled_at": order.filled_at.isoformat() if order.filled_at else None,
        }
        for order in orders
    ]


def signal_log(
    session: Session, paper_account_id: Optional[int] = None, limit: int = 200
) -> List[Dict[str, Any]]:
    query = select(Signal).order_by(Signal.generated_at.desc()).limit(limit)
    if paper_account_id is not None:
        query = query.where(Signal.paper_account_id == paper_account_id)
    return [
        {
            "id": signal.id,
            "symbol": signal.symbol,
            "action": signal.action,
            "score": float(signal.score) if signal.score is not None else None,
            "conviction": signal.conviction,
            "reference_price": float(signal.reference_price) if signal.reference_price else None,
            "executed": signal.executed,
            "skip_reason": signal.skip_reason,
            "generated_at": signal.generated_at.isoformat() if signal.generated_at else None,
        }
        for signal in session.scalars(query)
    ]


def divergence(
    session: Session, paper: PaperAccount, prices: Dict[str, float]
) -> Dict[str, Any]:
    """Paper performance against the backtest that justified deploying it.

    This is the honest test. A strategy that returned 34% a year in a backtest
    and 4% in paper did not get unlucky — it was overfitted, and the backtest
    was measuring the optimiser rather than the edge. The comparison is
    annualised on both sides because the paper run is almost always the shorter
    of the two.
    """
    current = valuation(session, paper, prices)
    reference = paper.backtest_reference or {}
    expected_cagr = reference.get("cagr_pct")
    expected_drawdown = reference.get("max_drawdown_pct")

    started = paper.created_at
    if started is not None and started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    days_live = max(1, (datetime.now(timezone.utc) - started).days) if started else 1
    years = days_live / 365.25

    actual_total = current["total_return_pct"]
    actual_annualised = None
    if actual_total is not None and years > 0.05:
        # Annualising a two-week run produces absurd numbers; below about
        # eighteen days it is not reported at all.
        actual_annualised = ((1 + actual_total / 100.0) ** (1 / years) - 1) * 100.0

    gap = (
        round(actual_annualised - expected_cagr, 2)
        if actual_annualised is not None and expected_cagr is not None
        else None
    )

    return {
        "days_live": days_live,
        "years_live": round(years, 3),
        "paper_total_return_pct": actual_total,
        "paper_annualised_return_pct": round(actual_annualised, 2) if actual_annualised else None,
        "backtest_cagr_pct": expected_cagr,
        "backtest_max_drawdown_pct": expected_drawdown,
        "annualised_gap_pct": gap,
        "verdict": _divergence_verdict(gap, years, current["order_count"]),
        "caveat": (
            "A short live window is dominated by noise, and a single market "
            "regime is not evidence either way. Read this after a year, not a "
            "month."
        ),
    }


def _divergence_verdict(gap: Optional[float], years: float, orders: int) -> str:
    if gap is None:
        return "No backtest reference recorded, so there is nothing to compare against."
    if years < 0.25 or orders < 5:
        return (
            f"Too early to judge: {years * 12:.0f} months live and {orders} orders. "
            "The gap shown is noise."
        )
    if gap < -15:
        return (
            f"Paper trading is running {abs(gap):.1f} points a year below the "
            "backtest. That size of gap usually means the backtest was overfitted."
        )
    if gap < -5:
        return (
            f"Paper is {abs(gap):.1f} points a year behind the backtest. Some decay "
            "out of sample is normal; this is at the upper end of normal."
        )
    if gap > 5:
        return (
            f"Paper is {gap:.1f} points a year ahead of the backtest. Pleasant, and "
            "just as likely to be regime luck as a real improvement."
        )
    return f"Paper is tracking the backtest within {abs(gap):.1f} points a year."
