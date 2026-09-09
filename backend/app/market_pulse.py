"""NSE Live Market Pulse & Real-Time Scanners.

Delivers high-frequency market posture and tactical breakout scans:
1. Live NSE Advance/Decline breadth ratio & market sentiment
2. Volume Shockers: Institutional accumulation footprint (Volume_t >= 2x SMA20(Volume), Return_t > 0)
3. 52-Week High Breakout Radar with Volatility Contraction Pattern (VCP) filtering

Zero invented/mock data: strictly reports real calculations or structured availability failures.
"""

import logging
import math
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import yfinance as yf

from app import symbols as symbol_master
from app.cache import TTLCache
from app.yf_frames import ticker_frame

logger = logging.getLogger(__name__)

# Cache pulse results for 5 minutes (300 seconds)
_pulse_cache = TTLCache(ttl=300.0, max_entries=16)

# Default liquid universe scanned for shockers and breakouts (NIFTY 50)
DEFAULT_SCAN_INDEX = "NIFTY50"


def calculate_market_breadth(price_changes: pd.Series) -> Dict[str, Any]:
    """Computes Advance/Decline market breadth statistics from price changes (pct or delta).

    Args:
        price_changes: Series of percentage or price changes across the evaluated universe.

    Returns:
        Dict containing advances, declines, unchanged, total, breadth_ratio,
        advance_pct, sentiment, and human-readable description.
    """
    clean = price_changes.dropna()
    total = len(clean)
    if total == 0:
        return {
            "advances": 0,
            "declines": 0,
            "unchanged": 0,
            "total": 0,
            "breadth_ratio": 1.0,
            "advance_pct": 50.0,
            "sentiment": "NEUTRAL",
            "description": "No price change data available to evaluate breadth.",
        }

    advances = int((clean > 0).sum())
    declines = int((clean < 0).sum())
    unchanged = int((clean == 0).sum())

    adv_pct = (advances / total) * 100.0 if total > 0 else 50.0
    breadth_ratio = round(advances / declines, 2) if declines > 0 else float(advances)

    if adv_pct >= 60.0 or breadth_ratio >= 1.5:
        sentiment = "BULLISH_EXPANSION"
        description = (
            f"Strong market breadth ({advances} Advances vs {declines} Declines, {adv_pct:.1f}% positive). "
            "Broad-based institutional participation supporting index uptrend."
        )
    elif adv_pct <= 40.0 or breadth_ratio <= 0.67:
        sentiment = "BEARISH_DIVERGENCE"
        description = (
            f"Weak market breadth ({advances} Advances vs {declines} Declines, only {adv_pct:.1f}% positive). "
            "Broad selling pressure; caution advised on aggressive long entries."
        )
    else:
        sentiment = "NEUTRAL"
        description = (
            f"Balanced market breadth ({advances} Advances, {declines} Declines, {unchanged} Unchanged). "
            "Stock-specific divergence; index consolidating."
        )

    return {
        "advances": advances,
        "declines": declines,
        "unchanged": unchanged,
        "total": total,
        "breadth_ratio": breadth_ratio,
        "advance_pct": round(adv_pct, 1),
        "sentiment": sentiment,
        "description": description,
    }


def detect_volume_shockers(
    ohlcv_by_symbol: Dict[str, pd.DataFrame],
    min_surge: float = 2.0,
) -> List[Dict[str, Any]]:
    """Identifies stocks experiencing an unusual surge in volume alongside positive returns.

    Volume Surge Ratio = Volume_t / SMA_20(Volume) >= min_surge, with Return_t > 0.
    Measures institutional accumulation velocity and breakout confirmation.

    Returns:
        List of shockers sorted by volume_surge_ratio descending.
    """
    shockers: List[Dict[str, Any]] = []

    for sym, df in ohlcv_by_symbol.items():
        if df is None or df.empty or len(df) < 21:
            continue
        if "Close" not in df.columns or "Volume" not in df.columns:
            continue

        closes = df["Close"].dropna()
        volumes = df["Volume"].dropna()

        if len(closes) < 2 or len(volumes) < 21:
            continue

        curr_close = float(closes.iloc[-1])
        prev_close = float(closes.iloc[-2])
        if prev_close <= 0:
            continue

        change_pct = ((curr_close - prev_close) / prev_close) * 100.0
        if change_pct <= 0:
            # Volume shockers must be positive accumulation bars
            continue

        curr_vol = float(volumes.iloc[-1])
        sma20_vol = float(volumes.iloc[-21:-1].mean())

        if sma20_vol <= 0 or curr_vol <= 0:
            continue

        surge_ratio = curr_vol / sma20_vol
        if surge_ratio >= min_surge:
            record = symbol_master.master.lookup(sym)
            name = record.name if record else sym

            tag = "INSTITUTIONAL_ACCUMULATION" if surge_ratio >= 3.0 else "VOLUME_EXPANSION"

            shockers.append(
                {
                    "symbol": sym,
                    "name": name,
                    "current_price": round(curr_close, 2),
                    "change_pct": round(change_pct, 2),
                    "volume": int(curr_vol),
                    "sma20_volume": int(sma20_vol),
                    "volume_surge_ratio": round(surge_ratio, 2),
                    "tag": tag,
                }
            )

    shockers.sort(key=lambda x: x["volume_surge_ratio"], reverse=True)
    return shockers


def check_vcp_contraction(df: pd.DataFrame) -> bool:
    """Checks for a Volatility Contraction Pattern (VCP) prior to breakout.

    VCP criteria:
    The recent 10-day price range / ATR contracted compared to the preceding 20-day base.
    This filters out loose, erratic breakouts in favor of tight, orderly consolidations.
    """
    if len(df) < 30 or "High" not in df.columns or "Low" not in df.columns or "Close" not in df.columns:
        return False

    highs = df["High"].iloc[-30:]
    lows = df["Low"].iloc[-30:]
    closes = df["Close"].iloc[-30:]

    # Range of last 10 days
    recent_range = float(highs.iloc[-10:].max() - lows.iloc[-10:].min())
    # Range of prior 20 days (from day -30 to -10)
    prior_range = float(highs.iloc[:-10].max() - lows.iloc[:-10].min())

    base_price = float(closes.iloc[-10])
    if base_price <= 0 or prior_range <= 0:
        return False

    recent_volatility = recent_range / base_price
    prior_volatility = prior_range / base_price

    # Contraction: recent 10-day volatility is less than 75% of the preceding base
    return recent_volatility < (prior_volatility * 0.75)


def detect_52w_breakouts(
    ohlcv_by_symbol: Dict[str, pd.DataFrame],
    threshold_pct: float = 0.98,
) -> List[Dict[str, Any]]:
    """Detects stocks trading at or within (1 - threshold_pct) of their 52-week high,
    annotating whether they exhibit Volatility Contraction Pattern (VCP) consolidation.

    Returns:
        List of breakout candidates sorted by distance_pct descending.
    """
    breakouts: List[Dict[str, Any]] = []

    for sym, df in ohlcv_by_symbol.items():
        if df is None or df.empty or len(df) < 50:
            continue
        if "Close" not in df.columns or "High" not in df.columns:
            continue

        closes = df["Close"].dropna()
        highs = df["High"].dropna()

        if len(closes) < 2 or len(highs) < 50:
            continue

        curr_close = float(closes.iloc[-1])
        prev_close = float(closes.iloc[-2])
        change_pct = ((curr_close - prev_close) / prev_close) * 100.0 if prev_close > 0 else 0.0

        # Lookback up to 252 trading days for prior 52W high (excluding current bar)
        lookback = min(252, len(highs))
        prior_highs = highs.iloc[-(lookback):-1] if len(highs) > 1 else highs
        high_52w = float(prior_highs.max())

        if high_52w <= 0:
            continue

        ratio = curr_close / high_52w
        if ratio >= threshold_pct:
            distance_pct = ((curr_close - high_52w) / high_52w) * 100.0
            is_vcp = check_vcp_contraction(df)

            if curr_close >= high_52w:
                status = "VCP_BREAKOUT" if is_vcp else "NEW_52W_HIGH"
            else:
                status = "VCP_CONSOLIDATION" if is_vcp else "NEAR_52W_BREAKOUT"

            record = symbol_master.master.lookup(sym)
            name = record.name if record else sym

            breakouts.append(
                {
                    "symbol": sym,
                    "name": name,
                    "current_price": round(curr_close, 2),
                    "high_52w": round(high_52w, 2),
                    "distance_pct": round(distance_pct, 2),
                    "change_pct": round(change_pct, 2),
                    "status": status,
                    "vcp_contracted": is_vcp,
                }
            )

    # Sort so stocks closest to or highest above 52W high appear first
    breakouts.sort(key=lambda x: x["distance_pct"], reverse=True)
    return breakouts


def fetch_live_market_pulse(
    universe_index: str = DEFAULT_SCAN_INDEX,
    use_cache: bool = True,
) -> Dict[str, Any]:
    """Scans the designated index universe for live market breadth, volume shockers,
    and 52-week breakouts.

    Returns:
        Structured payload conforming to MarketPulse response schema, or
        { "available": False, "reason": "..." } on data acquisition failure.
    """
    cache_key = f"market_pulse_{universe_index.upper()}"
    if use_cache:
        cached = _pulse_cache.get(cache_key)
        if cached is not None:
            return cached

    records = symbol_master.master.universe(index=universe_index)
    if not records:
        return {
            "available": False,
            "reason": f"No symbol records found for universe index '{universe_index}'.",
        }

    symbols = [r.symbol for r in records]
    yf_tickers = [f"{s}.NS" for s in symbols]

    try:
        data = yf.download(
            tickers=yf_tickers,
            period="1y",
            interval="1d",
            group_by="ticker",
            auto_adjust=True,
            progress=False,
            threads=True,
        )
    except Exception as exc:
        logger.warning("Failed downloading universe bars for market pulse: %s", exc)
        return {
            "available": False,
            "reason": f"Upstream market data error: {exc}",
        }

    if data is None or data.empty:
        return {
            "available": False,
            "reason": "Empty dataset returned from upstream price provider.",
        }

    # Extract OHLCV frames per symbol
    ohlcv_by_symbol: Dict[str, pd.DataFrame] = {}
    day_changes: Dict[str, float] = {}

    for sym, yf_sym in zip(symbols, yf_tickers):
        frame = ticker_frame(data, yf_sym)
        if frame is not None and not frame.empty:
            ohlcv_by_symbol[sym] = frame
            if "Close" in frame.columns and len(frame["Close"]) >= 2:
                c_curr = float(frame["Close"].iloc[-1])
                c_prev = float(frame["Close"].iloc[-2])
                if c_prev > 0:
                    day_changes[sym] = (c_curr - c_prev) / c_prev

    if not ohlcv_by_symbol:
        return {
            "available": False,
            "reason": "Failed to parse individual ticker frames from batch download.",
        }

    # 1. Market Breadth
    breadth = calculate_market_breadth(pd.Series(day_changes))

    # 2. Volume Shockers
    shockers = detect_volume_shockers(ohlcv_by_symbol, min_surge=2.0)

    # 3. 52W Breakouts with VCP Filter
    breakouts = detect_52w_breakouts(ohlcv_by_symbol, threshold_pct=0.98)

    payload: Dict[str, Any] = {
        "available": True,
        "universe_index": universe_index.upper(),
        "scanned_symbols": len(ohlcv_by_symbol),
        "breadth": breadth,
        "volume_shockers": shockers,
        "breakouts": breakouts,
    }

    _pulse_cache.set(cache_key, payload)
    return payload
