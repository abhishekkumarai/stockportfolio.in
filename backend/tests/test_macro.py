"""Unit tests for the Indian Macro & Inter-Market Transmission Engine."""

import pandas as pd
import pytest

from app.macro import (
    calculate_crude_pressure,
    calculate_currency_trajectory,
    calculate_sector_rotation,
    calculate_stock_macro_betas,
    classify_macro_regime,
)


def test_crude_pressure_elevated():
    # 25 days of crude rising by 12% over 20 days
    dates = pd.date_range("2024-01-01", periods=30, freq="B")
    prices = [75.0] * 10 + [75.0 + i * 0.9 for i in range(20)]
    s = pd.Series(prices, index=dates)

    res = calculate_crude_pressure(s)
    assert res["pressure_level"] == "ELEVATED"
    assert res["change_20d_pct"] > 8.0
    assert "Paints" in res["impact_assessment"]


def test_crude_pressure_benign():
    dates = pd.date_range("2024-01-01", periods=30, freq="B")
    prices = [85.0 - i * 0.5 for i in range(30)]
    s = pd.Series(prices, index=dates)

    res = calculate_crude_pressure(s)
    assert res["pressure_level"] == "BENIGN"
    assert res["change_20d_pct"] < -4.0
    assert "Margin expansion" in res["impact_assessment"]


def test_crude_pressure_moderate_and_short():
    # Moderate: flat price
    dates = pd.date_range("2024-01-01", periods=30, freq="B")
    s = pd.Series([75.0] * 30, index=dates)
    res = calculate_crude_pressure(s)
    assert res["pressure_level"] == "MODERATE"
    assert res["change_20d_pct"] == 0.0

    # Short: 1 data point
    s_short = pd.Series([78.0])
    res_short = calculate_crude_pressure(s_short)
    assert res_short["current_price"] == 78.0
    assert res_short["pressure_level"] == "MODERATE"


def test_currency_trajectory():
    dates = pd.date_range("2024-01-01", periods=30, freq="B")

    # Depreciating INR: 83.0 -> 85.0 (+2.4% in 20d)
    depreciating = pd.Series([83.0] * 10 + [83.0 + i * 0.1 for i in range(20)], index=dates)
    res_dep = calculate_currency_trajectory(depreciating)
    assert res_dep["stance"] == "TAILWIND_FOR_EXPORTS"
    assert "IT and Pharma" in res_dep["impact_assessment"]

    # Appreciating INR: 84.0 -> 82.0 (-2.38% in 20d)
    appreciating = pd.Series([84.0] * 10 + [84.0 - i * 0.1 for i in range(20)], index=dates)
    res_app = calculate_currency_trajectory(appreciating)
    assert res_app["stance"] == "HEADWIND_FOR_EXPORTS"

    # Stable INR
    stable = pd.Series([83.5] * 30, index=dates)
    res_stable = calculate_currency_trajectory(stable)
    assert res_stable["stance"] == "STABLE"


def test_sector_rotation():
    dates = pd.date_range("2024-01-01", periods=80, freq="B")

    # NIFTY baseline: flat / mild gain
    nifty = pd.Series([20000.0 + i * 10.0 for i in range(80)], index=dates)

    # Sector A (Strong outperformer: IT): fast gain
    sec_it = pd.Series([30000.0 + i * 100.0 for i in range(80)], index=dates)

    # Sector B (Underperformer: FMCG): mild decline
    sec_fmcg = pd.Series([50000.0 - i * 30.0 for i in range(80)], index=dates)

    sector_closes = {
        "NIFTY_IT": sec_it,
        "NIFTY_FMCG": sec_fmcg,
    }

    rotation = calculate_sector_rotation(sector_closes, nifty)
    assert len(rotation) == 2

    # IT should be ranked 1 with LEADERSHIP
    assert rotation[0]["sector_key"] == "NIFTY_IT"
    assert rotation[0]["rank"] == 1
    assert rotation[0]["status"] == "LEADERSHIP"
    assert rotation[0]["momentum_score"] > 0

    # FMCG should be ranked 2 with LAGGING
    assert rotation[1]["sector_key"] == "NIFTY_FMCG"
    assert rotation[1]["rank"] == 2
    assert rotation[1]["status"] == "LAGGING"
    assert rotation[1]["momentum_score"] < 0


def test_classify_macro_regime():
    dates = pd.date_range("2024-01-01", periods=30, freq="B")

    # 1. Global Risk-Off (Spiking VIX >= 18)
    vix_high = pd.Series([12.0] * 20 + [19.5] * 10, index=dates)
    r1 = classify_macro_regime(
        crude_metrics={"pressure_level": "MODERATE", "change_20d_pct": 1.0},
        inr_metrics={"stance": "STABLE"},
        vix_series=vix_high,
        us10y_series=pd.Series([42.0] * 30, index=dates),
        nifty_series=pd.Series([22000.0] * 30, index=dates),
    )
    assert r1["regime_id"] == "GLOBAL_RISK_OFF"
    assert r1["posture"] == "CAPITAL_PRESERVATION"
    assert "NIFTY FMCG" in r1["favored_sectors"]

    # 2. Imported Inflation Pressure (Crude elevated + depreciating INR)
    vix_calm = pd.Series([13.5] * 30, index=dates)
    r2 = classify_macro_regime(
        crude_metrics={"pressure_level": "ELEVATED", "change_20d_pct": 10.0, "current_price": 88.0},
        inr_metrics={"stance": "TAILWIND_FOR_EXPORTS"},
        vix_series=vix_calm,
        us10y_series=pd.Series([44.0] * 30, index=dates),
        nifty_series=pd.Series([22000.0] * 30, index=dates),
    )
    assert r2["regime_id"] == "IMPORTED_INFLATION_PRESSURE"
    assert r2["posture"] == "DEFENSIVE_TILT"
    assert "NIFTY IT" in r2["favored_sectors"]

    # 3. Goldilocks Expansion (Benign crude + stable INR + calm VIX + positive Nifty)
    nifty_up = pd.Series([21000.0 + i * 50.0 for i in range(30)], index=dates)
    r3 = classify_macro_regime(
        crude_metrics={"pressure_level": "BENIGN", "change_20d_pct": -5.0},
        inr_metrics={"stance": "STABLE"},
        vix_series=vix_calm,
        us10y_series=pd.Series([40.0] * 30, index=dates),
        nifty_series=nifty_up,
    )
    assert r3["regime_id"] == "GOLDILOCKS_EXPANSION"
    assert r3["posture"] == "OVERWEIGHT_CYCLICALS"
    assert "NIFTY Bank" in r3["favored_sectors"]

    # 4. Defensive Consolidation (Mixed)
    vix_mid = pd.Series([16.0] * 30, index=dates)
    nifty_flat = pd.Series([22000.0] * 30, index=dates)
    r4 = classify_macro_regime(
        crude_metrics={"pressure_level": "MODERATE", "change_20d_pct": 1.5},
        inr_metrics={"stance": "STABLE"},
        vix_series=vix_mid,
        us10y_series=pd.Series([42.0] * 30, index=dates),
        nifty_series=nifty_flat,
    )
    assert r4["regime_id"] == "DEFENSIVE_CONSOLIDATION"
    assert r4["posture"] == "SELECTIVE_STOCK_PICKING"


def test_calculate_stock_macro_betas():
    dates = pd.date_range("2024-01-01", periods=50, freq="B")

    # Generate synthetic returns
    market_ret = pd.Series([0.01 * ((-1) ** i) for i in range(50)], index=dates)
    crude_ret = pd.Series([0.015 * ((-1) ** (i % 3)) for i in range(50)], index=dates)
    inr_ret = pd.Series([0.005 * ((-1) ** (i % 4)) for i in range(50)], index=dates)

    # Stock return = 1.2 * market + 0.5 * crude - 0.3 * inr
    stock_ret = 1.2 * market_ret + 0.5 * crude_ret - 0.3 * inr_ret

    betas = calculate_stock_macro_betas(
        stock_returns=stock_ret,
        crude_returns=crude_ret,
        inr_returns=inr_ret,
        market_returns=market_ret,
    )

    assert "beta_crude" in betas
    assert "beta_usdinr" in betas
    assert "beta_market" in betas
    assert isinstance(betas["beta_crude"], float)
    assert isinstance(betas["beta_market"], float)

    # Edge case: series with insufficient data
    short_betas = calculate_stock_macro_betas(
        stock_returns=stock_ret.iloc[:5],
        crude_returns=crude_ret.iloc[:5],
        inr_returns=inr_ret.iloc[:5],
        market_returns=market_ret.iloc[:5],
    )
    assert short_betas["beta_market"] == 1.0
    assert short_betas["beta_crude"] == 0.0
