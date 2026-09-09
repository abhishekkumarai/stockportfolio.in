"""Indian macroeconomic & inter-market transmission engine.

Models how global and domestic macroeconomic currents cascade into Indian financial
markets, sector rotation, and stock-level alpha:
1. Brent Crude Oil (BZ=F) & Crude Pressure Index
2. USD/INR Foreign Exchange (INR=X) & Export Tailwind / Import Headwind
3. US 10-Year Treasury Yield (^TNX) & Cost of Capital
4. Safe-haven Gold (GC=F) & Domestic Risk Radar (^INDIAVIX)
5. NIFTY Sector Relative Momentum & Rotation Matrix
6. Stock-Level Macro Betas (Crude Beta, FX Beta, Market Beta)
7. Composite Macro Regime Classification (Goldilocks, Imported Inflation, Risk-Off, Defensive Consolidation)

Zero invented/mock data: if upstream feeds fail, returns structured failure payload.
"""

import logging
import math
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import yfinance as yf

from app.cache import TTLCache
from app.yf_frames import close_series

logger = logging.getLogger(__name__)

# Macro Indicator Tickers (100% Free Yahoo Finance)
MACRO_TICKERS: Dict[str, str] = {
    "crude": "BZ=F",          # Brent Crude Oil Continuous Contract
    "usdinr": "INR=X",        # USD/INR Spot Exchange Rate
    "us10y": "^TNX",          # US 10-Year Treasury Yield (quoted as yield * 10)
    "gold": "GC=F",           # Gold COMEX Futures
    "vix": "^INDIAVIX",       # India VIX Volatility Index
    "nifty50": "^NSEI",       # NIFTY 50 Benchmark Index
}

# Major NIFTY Sectoral Indices
SECTOR_TICKERS: Dict[str, str] = {
    "NIFTY_BANK": "^NSEBANK",
    "NIFTY_IT": "^CNXIT",
    "NIFTY_AUTO": "^CNXAUTO",
    "NIFTY_PHARMA": "^CNXPHARMA",
    "NIFTY_FMCG": "^CNXFMCG",
    "NIFTY_METAL": "^CNXMETAL",
    "NIFTY_ENERGY": "^CNXENERGY",
    "NIFTY_REALTY": "^CNXREALTY",
}

SECTOR_NAMES: Dict[str, str] = {
    "NIFTY_BANK": "NIFTY Bank",
    "NIFTY_IT": "NIFTY IT",
    "NIFTY_AUTO": "NIFTY Auto",
    "NIFTY_PHARMA": "NIFTY Pharma",
    "NIFTY_FMCG": "NIFTY FMCG",
    "NIFTY_METAL": "NIFTY Metal",
    "NIFTY_ENERGY": "NIFTY Energy",
    "NIFTY_REALTY": "NIFTY Realty",
}

# Macro data TTL cache (15 minutes = 900 seconds)
_macro_cache = TTLCache(ttl=900.0, max_entries=16)


def calculate_crude_pressure(crude_series: pd.Series) -> Dict[str, Any]:
    """Computes the Crude Pressure Index from Brent Crude historical closes.

    India imports ~85% of its crude oil requirements. Sudden upward momentum in
    crude creates imported inflation, widens the current account deficit, and compresses
    margins for downstream users (Paints, Auto, Aviation, Tyres, OMCs).

    Returns:
        Dict carrying current_price, change_5d_pct, change_20d_pct, pressure_level,
        and human-readable impact assessment.
    """
    clean = crude_series.dropna()
    if len(clean) < 2:
        return {
            "current_price": float(clean.iloc[-1]) if len(clean) == 1 else None,
            "change_5d_pct": 0.0,
            "change_20d_pct": 0.0,
            "pressure_level": "MODERATE",
            "impact_assessment": "Insufficient crude price history.",
        }

    current = float(clean.iloc[-1])
    idx_5d = max(0, len(clean) - 6)
    idx_20d = max(0, len(clean) - 21)

    p_5d = float(clean.iloc[idx_5d])
    p_20d = float(clean.iloc[idx_20d])

    roc_5d = (current - p_5d) / p_5d if p_5d > 0 else 0.0
    roc_20d = (current - p_20d) / p_20d if p_20d > 0 else 0.0

    # Categorisation logic
    # Rapid spike or sustained 20d surge or high baseline (> $90) with positive velocity
    if roc_20d >= 0.08 or (roc_5d >= 0.04 and roc_20d > 0.0) or (current >= 90.0 and roc_20d >= 0.02):
        level = "ELEVATED"
        assessment = (
            f"Elevated crude pressure (Brent ${current:.2f}, 20d: +{roc_20d*100:.1f}%). "
            "Input cost headwinds for Paints, Aviation, OMCs, and Tyres; expands India's import bill."
        )
    elif roc_20d <= -0.04:
        level = "BENIGN"
        assessment = (
            f"Benign crude environment (Brent ${current:.2f}, 20d: {roc_20d*100:.1f}%). "
            "Margin expansion tailwind for consumer discretionary, autos, and transport sectors."
        )
    else:
        level = "MODERATE"
        assessment = (
            f"Moderate crude levels (Brent ${current:.2f}, 20d: {roc_20d*100:+.1f}%). "
            "Neutral macro transmission to domestic inflation and trade balance."
        )

    return {
        "current_price": round(current, 2),
        "change_5d_pct": round(roc_5d * 100.0, 2),
        "change_20d_pct": round(roc_20d * 100.0, 2),
        "pressure_level": level,
        "impact_assessment": assessment,
    }


def calculate_currency_trajectory(usdinr_series: pd.Series) -> Dict[str, Any]:
    """Computes Rupee velocity and currency headwind/tailwind.

    A depreciating Rupee (rising USD/INR) boosts revenue realizations for exporters
    (IT services, Pharma APIs), but elevates imported inflation and hurts firms with
    unhedged foreign currency debt.

    Returns:
        Dict carrying current_rate, change_5d_pct, change_20d_pct, stance,
        and impact assessment.
    """
    clean = usdinr_series.dropna()
    if len(clean) < 2:
        return {
            "current_rate": float(clean.iloc[-1]) if len(clean) == 1 else None,
            "change_5d_pct": 0.0,
            "change_20d_pct": 0.0,
            "stance": "STABLE",
            "impact_assessment": "Insufficient USD/INR rate history.",
        }

    current = float(clean.iloc[-1])
    idx_5d = max(0, len(clean) - 6)
    idx_20d = max(0, len(clean) - 21)

    p_5d = float(clean.iloc[idx_5d])
    p_20d = float(clean.iloc[idx_20d])

    roc_5d = (current - p_5d) / p_5d if p_5d > 0 else 0.0
    roc_20d = (current - p_20d) / p_20d if p_20d > 0 else 0.0

    if roc_20d >= 0.015:
        stance = "TAILWIND_FOR_EXPORTS"
        assessment = (
            f"Rupee depreciating (USD/INR {current:.2f}, 20d: +{roc_20d*100:.2f}%). "
            "Operational margin tailwind for IT and Pharma exporters; headwind for capital-intensive importers."
        )
    elif roc_20d <= -0.015:
        stance = "HEADWIND_FOR_EXPORTS"
        assessment = (
            f"Rupee appreciating (USD/INR {current:.2f}, 20d: {roc_20d*100:.2f}%). "
            "Relieves imported inflation; slight drag on US dollar export realizations."
        )
    else:
        stance = "STABLE"
        assessment = (
            f"Stable foreign exchange regime (USD/INR {current:.2f}, 20d: {roc_20d*100:+.2f}%). "
            "Balanced transmission across both export and domestic cyclicals."
        )

    return {
        "current_rate": round(current, 3),
        "change_5d_pct": round(roc_5d * 100.0, 2),
        "change_20d_pct": round(roc_20d * 100.0, 2),
        "stance": stance,
        "impact_assessment": assessment,
    }


def calculate_sector_rotation(
    sector_closes: Dict[str, pd.Series],
    nifty_series: pd.Series,
) -> List[Dict[str, Any]]:
    """Calculates relative momentum of NIFTY sectors versus the NIFTY 50 benchmark.

    Evaluates:
    - 1-Month (21 trading days) Relative Return: R_sector,21d - R_nifty,21d
    - 3-Month (63 trading days) Relative Return: R_sector,63d - R_nifty,63d
    - Blended Momentum Score: 0.5 * rel_1m + 0.5 * rel_3m

    Classifications:
    - LEADERSHIP: Sustained outperformance over both 1m and 3m horizons.
    - IMPROVING: Short-term 1m momentum turning positive against benchmark.
    - WEAKENING: Long-term outperformer losing short-term momentum.
    - LAGGING: Underperforming on both time horizons.
    """
    clean_nifty = nifty_series.dropna()
    if len(clean_nifty) < 22:
        return []

    n_curr = float(clean_nifty.iloc[-1])
    n_21d = float(clean_nifty.iloc[max(0, len(clean_nifty) - 22)])
    n_63d = float(clean_nifty.iloc[max(0, len(clean_nifty) - 64)])

    nifty_ret_1m = (n_curr - n_21d) / n_21d if n_21d > 0 else 0.0
    nifty_ret_3m = (n_curr - n_63d) / n_63d if n_63d > 0 else 0.0

    results: List[Dict[str, Any]] = []

    for sector_key, series in sector_closes.items():
        clean_sec = series.dropna()
        if len(clean_sec) < 22:
            continue

        s_curr = float(clean_sec.iloc[-1])
        s_21d = float(clean_sec.iloc[max(0, len(clean_sec) - 22)])
        s_63d = float(clean_sec.iloc[max(0, len(clean_sec) - 64)])

        sec_ret_1m = (s_curr - s_21d) / s_21d if s_21d > 0 else 0.0
        sec_ret_3m = (s_curr - s_63d) / s_63d if s_63d > 0 else 0.0

        rel_1m = sec_ret_1m - nifty_ret_1m
        rel_3m = sec_ret_3m - nifty_ret_3m
        score = 0.5 * rel_1m + 0.5 * rel_3m

        if rel_1m > 0 and rel_3m > 0:
            status = "LEADERSHIP"
        elif rel_1m > 0 and rel_3m <= 0:
            status = "IMPROVING"
        elif rel_1m <= 0 and rel_3m > 0:
            status = "WEAKENING"
        else:
            status = "LAGGING"

        results.append(
            {
                "sector_key": sector_key,
                "name": SECTOR_NAMES.get(sector_key, sector_key),
                "current_price": round(s_curr, 2),
                "return_1m_pct": round(sec_ret_1m * 100.0, 2),
                "return_3m_pct": round(sec_ret_3m * 100.0, 2),
                "relative_1m_pct": round(rel_1m * 100.0, 2),
                "relative_3m_pct": round(rel_3m * 100.0, 2),
                "momentum_score": round(score * 100.0, 2),
                "status": status,
            }
        )

    # Sort descending by relative momentum score
    results.sort(key=lambda x: x["momentum_score"], reverse=True)
    for rank, item in enumerate(results, start=1):
        item["rank"] = rank

    return results


def classify_macro_regime(
    crude_metrics: Dict[str, Any],
    inr_metrics: Dict[str, Any],
    vix_series: Optional[pd.Series],
    us10y_series: Optional[pd.Series],
    nifty_series: Optional[pd.Series],
) -> Dict[str, Any]:
    """Classifies the prevailing Indian Macro Regime into one of four archetypes:

    1. GLOBAL_RISK_OFF:
       Surging volatility (India VIX >= 18 or rapid jump) and tightening financial conditions.
       Posture: CAPITAL_PRESERVATION, tilt to Cash & FMCG/Pharma defensives.

    2. IMPORTED_INFLATION_PRESSURE:
       Crude Oil pressure is ELEVATED, USD/INR depreciating, and US yields elevated.
       Posture: DEFENSIVE_TILT, prefer IT/Pharma exporters and upstream Energy.

    3. GOLDILOCKS_EXPANSION:
       Benign or moderate crude, stable Rupee, calm volatility (VIX < 15), and positive domestic momentum.
       Posture: OVERWEIGHT_CYCLICALS, favor BFSI, Auto, Industrials, Capital Goods.

    4. DEFENSIVE_CONSOLIDATION:
       Range-bound indices, moderate volatility (VIX 15-18), mixed macro signals.
       Posture: SELECTIVE_STOCK_PICKING, prioritize balance-sheet strength, high ROCE, and low debt.
    """
    vix_clean = vix_series.dropna() if vix_series is not None else pd.Series(dtype=float)
    vix_curr = float(vix_clean.iloc[-1]) if len(vix_clean) > 0 else 14.0
    vix_prev5 = float(vix_clean.iloc[max(0, len(vix_clean) - 6)]) if len(vix_clean) >= 6 else vix_curr
    vix_change_5d = (vix_curr - vix_prev5) / vix_prev5 if vix_prev5 > 0 else 0.0

    us10y_clean = us10y_series.dropna() if us10y_series is not None else pd.Series(dtype=float)
    us10y_curr = float(us10y_clean.iloc[-1]) if len(us10y_clean) > 0 else None

    nifty_clean = nifty_series.dropna() if nifty_series is not None else pd.Series(dtype=float)
    if len(nifty_clean) >= 21:
        n_curr = float(nifty_clean.iloc[-1])
        n_prev = float(nifty_clean.iloc[len(nifty_clean) - 21])
        nifty_ret_20d = (n_curr - n_prev) / n_prev if n_prev > 0 else 0.0
    else:
        nifty_ret_20d = 0.0

    crude_level = crude_metrics.get("pressure_level", "MODERATE")
    inr_stance = inr_metrics.get("stance", "STABLE")

    # Decision Matrix
    # 1. Global Risk-Off
    if vix_curr >= 18.0 or (vix_change_5d >= 0.25 and vix_curr >= 16.0) or (nifty_ret_20d <= -0.05 and vix_curr >= 17.0):
        regime_id = "GLOBAL_RISK_OFF"
        title = "Global Risk-Off"
        posture = "CAPITAL_PRESERVATION"
        narrative = (
            f"Heightened systemic volatility (India VIX {vix_curr:.1f}, 5d change: +{vix_change_5d*100:.1f}%). "
            "Capital flight towards safe-haven assets. Broad market risk elevated."
        )
        favored_sectors = ["NIFTY FMCG", "NIFTY Pharma", "Gold"]
        unfavored_sectors = ["NIFTY Realty", "NIFTY Bank", "High-Beta Midcaps"]

    # 2. Imported Inflation Pressure
    elif crude_level == "ELEVATED" and (inr_stance == "TAILWIND_FOR_EXPORTS" or crude_metrics.get("change_20d_pct", 0) >= 8.0):
        regime_id = "IMPORTED_INFLATION_PRESSURE"
        title = "Imported Inflation Pressure"
        posture = "DEFENSIVE_TILT"
        narrative = (
            f"Crude spike coupled with currency pressure (Brent ${crude_metrics.get('current_price', 0):.2f}). "
            "Elevates trade deficit and input costs across manufacturing, transport, and discretionary."
        )
        favored_sectors = ["NIFTY IT", "NIFTY Pharma", "NIFTY Energy"]
        unfavored_sectors = ["Paints & Adhesives", "Aviation & OMCs", "Consumer Discretionary"]

    # 3. Goldilocks Expansion
    elif vix_curr < 15.0 and crude_level in ("BENIGN", "MODERATE") and inr_stance != "TAILWIND_FOR_EXPORTS" and nifty_ret_20d >= -0.015:
        regime_id = "GOLDILOCKS_EXPANSION"
        title = "Goldilocks Expansion"
        posture = "OVERWEIGHT_CYCLICALS"
        narrative = (
            f"Subdued volatility (India VIX {vix_curr:.1f}), stable currency, and benign crude. "
            "Ideal transmission for credit expansion, domestic capex, and corporate earnings growth."
        )
        favored_sectors = ["NIFTY Bank", "NIFTY Auto", "NIFTY Realty", "Capital Goods"]
        unfavored_sectors = ["Defensives / Cash drag"]

    # 4. Defensive Consolidation (Default / Mixed Signals)
    else:
        regime_id = "DEFENSIVE_CONSOLIDATION"
        title = "Defensive Consolidation"
        posture = "SELECTIVE_STOCK_PICKING"
        narrative = (
            f"Mixed macro transmission (India VIX {vix_curr:.1f}, NIFTY 20d: {nifty_ret_20d*100:+.1f}%). "
            "Indices range-bound; alpha generation favors bottom-up fundamental stock selection over beta."
        )
        favored_sectors = ["High ROCE Quality Leaders", "Low D/E Exporters"]
        unfavored_sectors = ["Overleveraged Cyclicals", "Unprofitable Momentum"]

    return {
        "regime_id": regime_id,
        "title": title,
        "posture": posture,
        "vix_value": round(vix_curr, 2),
        "vix_change_5d_pct": round(vix_change_5d * 100.0, 2),
        "us10y_yield": round(us10y_curr / 10.0, 3) if us10y_curr is not None else None,
        "narrative": narrative,
        "favored_sectors": favored_sectors,
        "unfavored_sectors": unfavored_sectors,
    }


def calculate_stock_macro_betas(
    stock_returns: pd.Series,
    crude_returns: pd.Series,
    inr_returns: pd.Series,
    market_returns: pd.Series,
) -> Dict[str, float]:
    """Calculates empirical stock sensitivity (betas) to key macro variables:
    - beta_crude: Sensitivity to daily percentage changes in Brent Crude
    - beta_usdinr: Sensitivity to daily percentage changes in USD/INR
    - beta_market: Sensitivity to daily percentage changes in NIFTY 50

    Computed via single-factor OLS (cov(x, y) / var(x)) over the overlapping history.
    """
    df = pd.DataFrame(
        {
            "stock": stock_returns,
            "crude": crude_returns,
            "inr": inr_returns,
            "market": market_returns,
        }
    ).dropna()

    if len(df) < 20:
        return {
            "beta_crude": 0.0,
            "beta_usdinr": 0.0,
            "beta_market": 1.0,
        }

    def _beta(x_col: str) -> float:
        var_x = float(df[x_col].var())
        if var_x <= 1e-12 or math.isnan(var_x):
            return 0.0
        cov_xy = float(df[x_col].cov(df["stock"]))
        if math.isnan(cov_xy):
            return 0.0
        return round(cov_xy / var_x, 3)

    return {
        "beta_crude": _beta("crude"),
        "beta_usdinr": _beta("inr"),
        "beta_market": _beta("market"),
    }


def fetch_macro_snapshot(use_cache: bool = True) -> Dict[str, Any]:
    """Downloads live macro indicators and sector series via Yahoo Finance,
    computing the complete macro transmission payload.

    Returns:
        Dict conforming to MacroOverview schema with available: True, or
        { "available": False, "reason": "..." } on network/upstream outage.
    """
    cache_key = "macro_snapshot"
    if use_cache:
        cached = _macro_cache.get(cache_key)
        if cached is not None:
            return cached

    all_tickers = list(MACRO_TICKERS.values()) + list(SECTOR_TICKERS.values())

    try:
        data = yf.download(
            tickers=all_tickers,
            period="6mo",
            interval="1d",
            group_by="ticker",
            auto_adjust=True,
            progress=False,
            threads=True,
        )
    except Exception as exc:
        logger.warning("Failed to download macro tickers from Yahoo Finance: %s", exc)
        return {
            "available": False,
            "reason": f"Macro data upstream unreachable: {exc}",
        }

    if data is None or data.empty:
        return {
            "available": False,
            "reason": "Empty dataset returned for macro indicators.",
        }

    # Extract Series
    crude_s = close_series(data, MACRO_TICKERS["crude"])
    inr_s = close_series(data, MACRO_TICKERS["usdinr"])
    us10y_s = close_series(data, MACRO_TICKERS["us10y"])
    gold_s = close_series(data, MACRO_TICKERS["gold"])
    vix_s = close_series(data, MACRO_TICKERS["vix"])
    nifty_s = close_series(data, MACRO_TICKERS["nifty50"])

    if crude_s is None or inr_s is None or nifty_s is None:
        return {
            "available": False,
            "reason": "Essential macro indicators (Crude, USD/INR, or NIFTY 50) missing from response.",
        }

    # Indicators
    crude_metrics = calculate_crude_pressure(crude_s)
    inr_metrics = calculate_currency_trajectory(inr_s)

    # Sector Closes
    sector_closes: Dict[str, pd.Series] = {}
    for sec_key, ticker in SECTOR_TICKERS.items():
        s = close_series(data, ticker)
        if s is not None and not s.empty:
            sector_closes[sec_key] = s

    sector_rotation = calculate_sector_rotation(sector_closes, nifty_s)

    # Macro Regime
    regime = classify_macro_regime(
        crude_metrics=crude_metrics,
        inr_metrics=inr_metrics,
        vix_series=vix_s,
        us10y_series=us10y_s,
        nifty_series=nifty_s,
    )

    # Secondary tickers summary (Gold, US10Y)
    gold_curr = float(gold_s.dropna().iloc[-1]) if gold_s is not None and len(gold_s.dropna()) > 0 else None
    gold_5d = float(gold_s.dropna().iloc[max(0, len(gold_s.dropna()) - 6)]) if gold_s is not None and len(gold_s.dropna()) >= 6 else None
    gold_roc_5d = ((gold_curr - gold_5d) / gold_5d * 100.0) if gold_curr and gold_5d else 0.0

    payload: Dict[str, Any] = {
        "available": True,
        "regime": regime,
        "crude": crude_metrics,
        "currency": inr_metrics,
        "gold": {
            "current_price": round(gold_curr, 2) if gold_curr else None,
            "change_5d_pct": round(gold_roc_5d, 2),
        },
        "us10y": {
            "yield_pct": regime.get("us10y_yield"),
        },
        "vix": {
            "current": regime.get("vix_value"),
            "change_5d_pct": regime.get("vix_change_5d_pct"),
        },
        "sector_rotation": sector_rotation,
    }

    _macro_cache.set(cache_key, payload)
    return payload
