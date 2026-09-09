"""NSE universe screener routes."""

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from app.screener import ScreenFilters, available_filters, run_screen

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/screener", tags=["Screener"])


@router.get("/filters")
def get_filters():
    """The filter vocabulary — indices, sectors, caps and action bands."""
    return available_filters()


@router.get("/run")
def screen(
    index: Optional[str] = Query("NIFTY500", description="Index universe, e.g. NIFTY500"),
    sector: Optional[str] = Query(None),
    cap: Optional[str] = Query(None, description="large | mid | small | micro"),
    fno_only: bool = Query(False),
    min_score: Optional[float] = Query(None, ge=0, le=100),
    min_technical_score: Optional[float] = Query(None, ge=0, le=100),
    min_fundamental_score: Optional[float] = Query(None, ge=0, le=100),
    actions: Optional[List[str]] = Query(
        None, description="Keep only these actions, e.g. actions=BUY&actions=STRONG_BUY"
    ),
    rsi_min: Optional[float] = Query(None, ge=0, le=100),
    rsi_max: Optional[float] = Query(None, ge=0, le=100),
    above_sma200: Optional[bool] = Query(None),
    golden_cross: Optional[bool] = Query(None),
    min_adx: Optional[float] = Query(None, ge=0, le=100),
    min_roce: Optional[float] = Query(None),
    min_roe: Optional[float] = Query(None),
    max_pe: Optional[float] = Query(None, gt=0),
    max_debt_to_equity: Optional[float] = Query(None, ge=0),
    max_pledged_pct: Optional[float] = Query(None, ge=0, le=100),
    min_sales_growth: Optional[float] = Query(None),
    limit: int = Query(50, ge=1, le=250),
    universe_limit: int = Query(300, ge=10, le=2000, description="How many symbols to price"),
    with_fundamentals: bool = Query(True),
    fundamental_limit: int = Query(60, ge=0, le=300, description="How many to also scrape"),
):
    """Rank the NSE universe on the same technical + fundamental model as holdings.

    A cold run over 300 symbols with fundamentals takes tens of seconds; the
    result is cached for an hour, so subsequent identical requests return
    immediately with `cached: true`. Lower `universe_limit` and
    `fundamental_limit` for a fast scan.
    """
    filters = ScreenFilters(
        index=index,
        sector=sector,
        cap=cap,
        fno_only=fno_only,
        min_score=min_score,
        min_technical_score=min_technical_score,
        min_fundamental_score=min_fundamental_score,
        actions=tuple(actions) if actions else None,
        rsi_min=rsi_min,
        rsi_max=rsi_max,
        above_sma200=above_sma200,
        golden_cross=golden_cross,
        min_adx=min_adx,
        min_roce=min_roce,
        min_roe=min_roe,
        max_pe=max_pe,
        max_debt_to_equity=max_debt_to_equity,
        max_pledged_pct=max_pledged_pct,
        min_sales_growth=min_sales_growth,
    )

    try:
        return run_screen(
            filters=filters,
            limit=limit,
            universe_limit=universe_limit,
            with_fundamentals=with_fundamentals,
            fundamental_limit=fundamental_limit,
        )
    except Exception as exc:
        logger.exception("Screener run failed")
        raise HTTPException(status_code=502, detail=f"Screener failed: {exc}")
