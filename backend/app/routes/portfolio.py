"""Portfolio intelligence, danger radar, quant risk, rebalancing, and news routes."""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from app.fyers_client import FyersClient, FyersError
from app.news import get_portfolio_news_digest
from app.portfolio import value_portfolio
from app.quant.growth import evaluate_portfolio_growth
from app.quant.rebalance import generate_rebalancing_plan
from app.quant.risk import evaluate_portfolio_danger
from app.schemas import PortfolioRequest

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/portfolio", tags=["Portfolio"])


def get_optional_client(x_fyers_token: Optional[str] = Header(None)) -> Optional[FyersClient]:
    """A Fyers client when the caller has a token, otherwise None."""
    if not x_fyers_token:
        return None
    try:
        return FyersClient(access_token=x_fyers_token)
    except FyersError as exc:
        logger.warning("Could not build Fyers client: %s", exc)
        return None


class RebalanceRequest(BaseModel):
    portfolio: PortfolioRequest
    cash_inflow: float = Field(0.0, ge=0.0)
    drift_tolerance: float = Field(0.05, ge=0.01, le=0.5)
    mode: str = Field("zero_tax_inflow", description="'zero_tax_inflow' | 'drift_rebalance'")


@router.post("/value")
def value(
    request: PortfolioRequest,
    client: Optional[FyersClient] = Depends(get_optional_client),
):
    """Price a portfolio and return per-holding P&L plus allocation."""
    try:
        return value_portfolio(request, client)
    except Exception as exc:
        logger.exception("Portfolio valuation failed")
        raise HTTPException(status_code=502, detail=f"Valuation failed: {exc}")


@router.post("/analyse")
def analyse(
    request: PortfolioRequest,
    client: Optional[FyersClient] = Depends(get_optional_client),
):
    """Comprehensive Danger vs. Expected Growth Intelligence analysis."""
    try:
        valuation = value_portfolio(request, client)
        holdings = valuation.get("holdings", [])
        total_val = valuation.get("totals", {}).get("current_value", 0.0)
        cash_val = valuation.get("totals", {}).get("cash", 0.0)

        # 1. Danger Matrix Assessment
        danger = evaluate_portfolio_danger(holdings, total_val, cash_val)

        # 2. Expected Growth & Monte Carlo Simulation
        growth = evaluate_portfolio_growth(holdings, total_val)

        return {
            "valuation": valuation,
            "danger": danger,
            "growth": growth,
            "status": "success",
        }
    except Exception as exc:
        logger.exception("Portfolio analysis failed")
        raise HTTPException(status_code=502, detail=f"Analysis failed: {exc}")


@router.post("/rebalance")
def rebalance(
    req: RebalanceRequest,
    client: Optional[FyersClient] = Depends(get_optional_client),
):
    """Generates tax-aware rebalancing buy/trim order sheets."""
    try:
        valuation = value_portfolio(req.portfolio, client)
        holdings = valuation.get("holdings", [])
        total_val = valuation.get("totals", {}).get("current_value", 0.0)

        plan = generate_rebalancing_plan(
            holdings=holdings,
            total_current_value=total_val,
            cash_inflow=req.cash_inflow,
            drift_tolerance=req.drift_tolerance,
            mode=req.mode,  # type: ignore
        )
        return plan
    except Exception as exc:
        logger.exception("Portfolio rebalancing calculation failed")
        raise HTTPException(status_code=502, detail=f"Rebalancing failed: {exc}")


@router.post("/news")
def portfolio_news(request: PortfolioRequest):
    """Pulls free, tagged news catalysts for the user's holdings."""
    try:
        symbols = [h.symbol for h in request.equity]
        digest = get_portfolio_news_digest(symbols)
        return {"count": len(digest), "articles": digest}
    except Exception as exc:
        logger.exception("Portfolio news fetch failed")
        raise HTTPException(status_code=502, detail=f"News fetch failed: {exc}")
