"""NSE Live Market Pulse & Real-Time Scanner API routes."""

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Query

from app.market_pulse import fetch_live_market_pulse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/market-pulse", tags=["Market Pulse"])


@router.get("")
@router.get("/")
def get_market_pulse(
    universe: str = Query("NIFTY50", description="Universe index to scan, e.g. NIFTY50"),
    use_cache: bool = Query(True, description="Whether to serve from in-memory TTL cache"),
) -> Dict[str, Any]:
    """Scans the market for live breadth, institutional volume shockers, and 52W breakouts.

    Returns:
    - Live Advance/Decline ratio and sentiment classification
    - Volume Shockers (Volume_t >= 2x SMA20, Return_t > 0)
    - 52-Week High Breakouts & Volatility Contraction Pattern (VCP) consolidation radar
    """
    return fetch_live_market_pulse(universe_index=universe, use_cache=use_cache)


@router.get("/breadth")
def get_market_breadth(
    universe: str = Query("NIFTY50", description="Universe index, e.g. NIFTY50"),
    use_cache: bool = Query(True, description="Whether to serve from in-memory TTL cache"),
) -> Dict[str, Any]:
    """Returns only the Advance/Decline market breadth statistics for the given universe."""
    pulse = fetch_live_market_pulse(universe_index=universe, use_cache=use_cache)
    if not pulse.get("available", False):
        return pulse

    return {
        "available": True,
        "universe_index": universe.upper(),
        "breadth": pulse.get("breadth"),
    }


@router.get("/volume-shockers")
def get_volume_shockers(
    universe: str = Query("NIFTY50", description="Universe index, e.g. NIFTY50"),
    use_cache: bool = Query(True, description="Whether to serve from in-memory TTL cache"),
) -> Dict[str, Any]:
    """Returns ranked volume shockers experiencing institutional accumulation spikes."""
    pulse = fetch_live_market_pulse(universe_index=universe, use_cache=use_cache)
    if not pulse.get("available", False):
        return pulse

    return {
        "available": True,
        "universe_index": universe.upper(),
        "volume_shockers": pulse.get("volume_shockers", []),
    }


@router.get("/breakouts")
def get_52w_breakouts(
    universe: str = Query("NIFTY50", description="Universe index, e.g. NIFTY50"),
    use_cache: bool = Query(True, description="Whether to serve from in-memory TTL cache"),
) -> Dict[str, Any]:
    """Returns stocks trading within 2% of or above their 52-week high with VCP consolidation tags."""
    pulse = fetch_live_market_pulse(universe_index=universe, use_cache=use_cache)
    if not pulse.get("available", False):
        return pulse

    return {
        "available": True,
        "universe_index": universe.upper(),
        "breakouts": pulse.get("breakouts", []),
    }
