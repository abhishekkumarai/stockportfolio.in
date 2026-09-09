"""India Macro & Inter-Market Transmission API routes."""

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Query

from app.macro import fetch_macro_snapshot

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/macro", tags=["Macro"])


@router.get("")
@router.get("/")
def get_macro_overview(
    use_cache: bool = Query(True, description="Whether to serve from in-memory TTL cache"),
) -> Dict[str, Any]:
    """Returns the complete Indian Macroeconomic Transmission overview.

    Includes:
    - Macro Regime Classification (Goldilocks, Imported Inflation, Risk-Off, Defensive Consolidation)
    - Crude Pressure Index (Brent Crude momentum & downstream sector impact)
    - Currency Trajectory (USD/INR velocity & export tailwind/headwind)
    - Live Tickers: India VIX, US 10-Year Yield, Safe-haven Gold
    - NIFTY Sector Rotation Matrix (relative momentum vs NIFTY 50)
    """
    return fetch_macro_snapshot(use_cache=use_cache)


@router.get("/regime")
def get_macro_regime(
    use_cache: bool = Query(True, description="Whether to serve from in-memory TTL cache"),
) -> Dict[str, Any]:
    """Returns the current macroeconomic regime archetype, posture, and sector tilts."""
    snapshot = fetch_macro_snapshot(use_cache=use_cache)
    if not snapshot.get("available", False):
        return snapshot

    return {
        "available": True,
        "regime": snapshot.get("regime"),
        "vix": snapshot.get("vix"),
        "crude_pressure": snapshot.get("crude", {}).get("pressure_level"),
        "currency_stance": snapshot.get("currency", {}).get("stance"),
    }


@router.get("/sectors")
def get_sector_rotation(
    use_cache: bool = Query(True, description="Whether to serve from in-memory TTL cache"),
) -> Dict[str, Any]:
    """Returns the ranked NIFTY sector rotation matrix relative to NIFTY 50."""
    snapshot = fetch_macro_snapshot(use_cache=use_cache)
    if not snapshot.get("available", False):
        return snapshot

    return {
        "available": True,
        "sector_rotation": snapshot.get("sector_rotation", []),
    }
