"""Paper-trading routes.

Every route requires an account key and a database: a paper ledger that is not
persisted is a spreadsheet with extra steps, and the entire value of the
feature is that the audit trail survives.

Nothing here can reach a broker's order API. The banner on the list endpoint
says so explicitly, because a screen showing positions and fills should not
leave any doubt about whether real money is involved.
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.db.models import Account
from app.paper import ledger
from app.paper.runner import latest_prices, run_account
from app.routes.accounts import current_account

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/paper", tags=["Paper trading"])

READ_ONLY_BANNER = (
    "Simulated only. This system has no broker order API and cannot place a "
    "live trade."
)


class CreatePaperAccount(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    initial_capital: float = Field(100_000.0, gt=0)
    strategy: Optional[str] = None
    strategy_params: Dict[str, Any] = Field(default_factory=dict)
    backtest_reference: Dict[str, Any] = Field(
        default_factory=dict,
        description="The backtest this deployment is judged against: cagr_pct, max_drawdown_pct, sharpe",
    )


class ManualOrder(BaseModel):
    symbol: str
    side: str = Field(..., pattern="^(BUY|SELL)$")
    quantity: float = Field(..., gt=0)
    price: float = Field(..., gt=0)
    reason: str = ""


class RunRequest(BaseModel):
    symbols: List[str] = Field(..., min_length=1, max_length=50)


def _paper_or_404(session: Session, account: Account, paper_id: int):
    paper = ledger.get_account(session, account, paper_id)
    if paper is None:
        raise HTTPException(status_code=404, detail="Paper account not found.")
    return paper


@router.get("")
def list_paper_accounts(
    account: Account = Depends(current_account), session: Session = Depends(get_db)
):
    accounts = ledger.list_accounts(session, account)
    return {
        "banner": READ_ONLY_BANNER,
        "count": len(accounts),
        "accounts": [
            {
                "id": paper.id,
                "name": paper.name,
                "strategy": paper.strategy,
                "initial_capital": float(paper.initial_capital),
                "cash": float(paper.cash),
                "active": paper.active,
                "created_at": paper.created_at.isoformat() if paper.created_at else None,
            }
            for paper in accounts
        ],
    }


@router.post("")
def create_paper_account(
    body: CreatePaperAccount,
    account: Account = Depends(current_account),
    session: Session = Depends(get_db),
):
    paper = ledger.open_account(
        session, account, body.name, body.initial_capital,
        body.strategy, body.strategy_params, body.backtest_reference,
    )
    return {"id": paper.id, "name": paper.name, "banner": READ_ONLY_BANNER}


@router.get("/{paper_id}")
def paper_account_detail(
    paper_id: int,
    account: Account = Depends(current_account),
    session: Session = Depends(get_db),
):
    """Current valuation, open positions and divergence from the backtest."""
    paper = _paper_or_404(session, account, paper_id)
    symbols = [
        row["symbol"] for row in ledger.valuation(session, paper, {})["open_positions"]
    ]
    prices = latest_prices(symbols) if symbols else {}
    return {
        "banner": READ_ONLY_BANNER,
        "valuation": ledger.valuation(session, paper, prices),
        "divergence": ledger.divergence(session, paper, prices),
        "backtest_reference": paper.backtest_reference,
    }


@router.get("/{paper_id}/orders")
def paper_orders(
    paper_id: int,
    limit: int = 200,
    account: Account = Depends(current_account),
    session: Session = Depends(get_db),
):
    paper = _paper_or_404(session, account, paper_id)
    return {"orders": ledger.order_log(session, paper, limit)}


@router.get("/{paper_id}/signals")
def paper_signals(
    paper_id: int,
    limit: int = 200,
    account: Account = Depends(current_account),
    session: Session = Depends(get_db),
):
    """Every signal generated, executed or not.

    The skipped ones matter as much as the taken ones: without them the ledger
    measures execution, not the strategy.
    """
    paper = _paper_or_404(session, account, paper_id)
    signals = ledger.signal_log(session, paper.id, limit)
    executed = sum(1 for signal in signals if signal["executed"])
    return {
        "count": len(signals),
        "executed": executed,
        "skipped": len(signals) - executed,
        "signals": signals,
    }


@router.post("/{paper_id}/orders")
def place_manual_order(
    paper_id: int,
    body: ManualOrder,
    account: Account = Depends(current_account),
    session: Session = Depends(get_db),
):
    """Record a manual simulated fill."""
    paper = _paper_or_404(session, account, paper_id)
    try:
        order = ledger.execute(
            session, paper, body.symbol.upper(), body.side,
            body.quantity, body.price, body.reason or "Manual paper order",
        )
    except (ledger.InsufficientFunds, ledger.NoPosition) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return {
        "id": order.id,
        "symbol": order.symbol,
        "side": order.side,
        "quantity": float(order.quantity),
        "price": float(order.price),
        "fees": float(order.fees),
        "realised_pnl": float(order.realised_pnl),
        "banner": READ_ONLY_BANNER,
    }


@router.post("/{paper_id}/run")
def run_strategy(
    paper_id: int,
    body: RunRequest,
    account: Account = Depends(current_account),
    session: Session = Depends(get_db),
):
    """Evaluate the bound strategy over a watchlist and act on its signals.

    Synchronous, and bounded to 50 symbols, because each one is a price
    download and a full strategy replay.
    """
    paper = _paper_or_404(session, account, paper_id)
    if not paper.strategy:
        raise HTTPException(
            status_code=400,
            detail=(
                "This paper account has no strategy bound to it. Create one with "
                "a `strategy` field, or place orders manually."
            ),
        )
    try:
        return run_account(paper.id, [s.upper() for s in body.symbols])
    except Exception as exc:
        logger.exception("Paper strategy run failed for account %s", paper_id)
        raise HTTPException(status_code=500, detail=f"Paper run failed: {exc}")
