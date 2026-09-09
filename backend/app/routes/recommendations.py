"""Ranked buy / sell recommendation routes.

Two shapes for the same answer. GET is the anonymous, universe-wide view — no
body, cacheable, and what the page loads with. POST carries the portfolio, and
is what turns "avoid this" into "sell this, and here is the tax on the exit".
"""

import logging
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import recommendations
from app.db import get_db, repo
from app.db.models import Account
from app.routes.accounts import current_account
from app.schemas import PortfolioRequest

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/recommendations", tags=["Recommendations"])


class RecommendationRequest(BaseModel):
    """Scan parameters, plus the holdings the sell list is judged against."""

    portfolio: Optional[PortfolioRequest] = Field(
        default=None,
        description="Holdings to review. Omitted, the sell list is universe-wide.",
    )
    index: Optional[str] = Field(default=None, description="Universe, e.g. NIFTY500")
    universe_limit: int = Field(default=300, ge=10, le=2000)
    fundamental_limit: int = Field(default=60, ge=0, le=300)
    with_fundamentals: bool = True
    buy_limit: int = Field(default=20, ge=1, le=100)
    sell_limit: int = Field(default=20, ge=1, le=100)


def _build(request: RecommendationRequest):
    try:
        return recommendations.build(
            portfolio=request.portfolio,
            index=request.index,
            universe_limit=request.universe_limit,
            fundamental_limit=request.fundamental_limit,
            with_fundamentals=request.with_fundamentals,
            buy_limit=request.buy_limit,
            sell_limit=request.sell_limit,
        )
    except Exception as exc:
        logger.exception("Recommendation run failed")
        raise HTTPException(status_code=502, detail=f"Recommendations failed: {exc}")


@router.get("")
def list_recommendations(
    index: Optional[str] = Query(None, description="Universe, e.g. NIFTY500"),
    universe_limit: int = Query(300, ge=10, le=2000),
    fundamental_limit: int = Query(60, ge=0, le=300),
    with_fundamentals: bool = Query(True),
    buy_limit: int = Query(20, ge=1, le=100),
    sell_limit: int = Query(20, ge=1, le=100),
):
    """Ranked buys, and the names to avoid or exit, across the whole universe.

    A cold run over 300 names with fundamentals takes tens of seconds — each
    uncached symbol is a Screener.in fetch — and the underlying scan is cached
    for an hour, so a repeat returns immediately with `universe.cached: true`.
    """
    return _build(
        RecommendationRequest(
            index=index,
            universe_limit=universe_limit,
            fundamental_limit=fundamental_limit,
            with_fundamentals=with_fundamentals,
            buy_limit=buy_limit,
            sell_limit=sell_limit,
        )
    )


@router.post("")
def recommend_for_portfolio(request: RecommendationRequest = Body(default_factory=RecommendationRequest)):
    """The same lists, with the sell side judged against the posted holdings.

    Every held name is scored on the identical model, including holdings
    outside the scanned index, and each sell candidate carries what the exit
    would cost after Indian capital-gains tax.
    """
    return _build(request)


@router.post("/me")
def recommend_for_account(
    request: RecommendationRequest = Body(default_factory=RecommendationRequest),
    account: Account = Depends(current_account),
    session: Session = Depends(get_db),
):
    """As above, against the holdings already stored for this account key.

    Saves the browser from posting a portfolio it has already synced. An
    account with no stored holdings is a 409, not a silent universe-wide
    answer: "nothing to sell" and "nothing was read" are different facts.
    """
    stored = repo.portfolio_for(session, account)
    if stored is None:
        raise HTTPException(
            status_code=409,
            detail=(
                "No holdings are stored for this account. Sync them first, or post "
                "a portfolio to /api/recommendations."
            ),
        )
    return _build(request.model_copy(update={"portfolio": stored}))
