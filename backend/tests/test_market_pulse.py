"""Unit tests for the NSE Market Pulse, Volume Shockers, and Breakouts Engine."""

import pandas as pd
import pytest

from app.market_pulse import (
    calculate_market_breadth,
    check_vcp_contraction,
    detect_52w_breakouts,
    detect_volume_shockers,
)


def test_calculate_market_breadth_bullish():
    # 70 advances, 30 declines
    changes = pd.Series([0.02] * 70 + [-0.01] * 30)
    res = calculate_market_breadth(changes)

    assert res["total"] == 100
    assert res["advances"] == 70
    assert res["declines"] == 30
    assert res["advance_pct"] == 70.0
    assert res["breadth_ratio"] == 2.33
    assert res["sentiment"] == "BULLISH_EXPANSION"


def test_calculate_market_breadth_bearish():
    # 25 advances, 75 declines
    changes = pd.Series([0.01] * 25 + [-0.02] * 75)
    res = calculate_market_breadth(changes)

    assert res["total"] == 100
    assert res["advances"] == 25
    assert res["declines"] == 75
    assert res["advance_pct"] == 25.0
    assert res["sentiment"] == "BEARISH_DIVERGENCE"


def test_calculate_market_breadth_neutral_and_empty():
    # 50 advances, 50 declines
    changes = pd.Series([0.01] * 50 + [-0.01] * 50)
    res = calculate_market_breadth(changes)
    assert res["sentiment"] == "NEUTRAL"
    assert res["breadth_ratio"] == 1.0

    # Empty
    res_empty = calculate_market_breadth(pd.Series([], dtype=float))
    assert res_empty["total"] == 0
    assert res_empty["sentiment"] == "NEUTRAL"


def test_detect_volume_shockers():
    dates = pd.date_range("2024-01-01", periods=30, freq="B")

    # Stock A: Volume surges 3.5x with positive return -> INSTITUTIONAL_ACCUMULATION
    prices_a = [100.0] * 29 + [105.0]
    volumes_a = [10000] * 29 + [35000]
    df_a = pd.DataFrame({"Close": prices_a, "Volume": volumes_a}, index=dates)

    # Stock B: Volume surges 2.2x with positive return -> VOLUME_EXPANSION
    prices_b = [200.0] * 29 + [203.0]
    volumes_b = [5000] * 29 + [11000]
    df_b = pd.DataFrame({"Close": prices_b, "Volume": volumes_b}, index=dates)

    # Stock C: Volume surges 4.0x with NEGATIVE return -> Should be excluded
    prices_c = [300.0] * 29 + [285.0]
    volumes_c = [10000] * 29 + [40000]
    df_c = pd.DataFrame({"Close": prices_c, "Volume": volumes_c}, index=dates)

    # Stock D: Normal volume 1.1x -> Should be excluded
    prices_d = [50.0] * 29 + [51.0]
    volumes_d = [10000] * 29 + [11000]
    df_d = pd.DataFrame({"Close": prices_d, "Volume": volumes_d}, index=dates)

    ohlcv = {"STOCKA": df_a, "STOCKB": df_b, "STOCKC": df_c, "STOCKD": df_d}
    shockers = detect_volume_shockers(ohlcv, min_surge=2.0)

    assert len(shockers) == 2
    # Ranked by surge ratio: Stock A (3.5x) first, then Stock B (2.2x)
    assert shockers[0]["symbol"] == "STOCKA"
    assert shockers[0]["volume_surge_ratio"] == 3.5
    assert shockers[0]["tag"] == "INSTITUTIONAL_ACCUMULATION"

    assert shockers[1]["symbol"] == "STOCKB"
    assert shockers[1]["volume_surge_ratio"] == 2.2
    assert shockers[1]["tag"] == "VOLUME_EXPANSION"


def test_vcp_contraction():
    dates = pd.date_range("2024-01-01", periods=35, freq="B")

    # Case 1: Wide prior range (days 0-24 range: 20 pts), tight recent range (days 25-34 range: 3 pts)
    highs_tight = [110.0] * 25 + [102.0] * 10
    lows_tight = [90.0] * 25 + [99.0] * 10
    closes_tight = [100.0] * 35
    df_tight = pd.DataFrame({"High": highs_tight, "Low": lows_tight, "Close": closes_tight}, index=dates)

    assert check_vcp_contraction(df_tight) is True

    # Case 2: Expanding recent volatility (recent range wider than prior)
    highs_wide = [102.0] * 25 + [120.0] * 10
    lows_wide = [98.0] * 25 + [80.0] * 10
    closes_wide = [100.0] * 35
    df_wide = pd.DataFrame({"High": highs_wide, "Low": lows_wide, "Close": closes_wide}, index=dates)

    assert check_vcp_contraction(df_wide) is False


def test_detect_52w_breakouts():
    dates = pd.date_range("2024-01-01", periods=100, freq="B")

    # Stock 1: Reaches new 52W high (prior high 150, current close 155)
    highs_1 = [150.0] * 99 + [156.0]
    lows_1 = [130.0] * 99 + [149.0]
    closes_1 = [140.0] * 99 + [155.0]
    df_1 = pd.DataFrame({"High": highs_1, "Low": lows_1, "Close": closes_1}, index=dates)

    # Stock 2: Near 52W breakout (high is 200, current price 198 -> 99%)
    highs_2 = [200.0] * 99 + [199.0]
    lows_2 = [180.0] * 99 + [195.0]
    closes_2 = [190.0] * 99 + [198.0]
    df_2 = pd.DataFrame({"High": highs_2, "Low": lows_2, "Close": closes_2}, index=dates)

    # Stock 3: Far below 52W high (high 300, current price 250 -> 83.3%)
    highs_3 = [300.0] * 100
    lows_3 = [240.0] * 100
    closes_3 = [250.0] * 100
    df_3 = pd.DataFrame({"High": highs_3, "Low": lows_3, "Close": closes_3}, index=dates)

    ohlcv = {"SYM1": df_1, "SYM2": df_2, "SYM3": df_3}
    breakouts = detect_52w_breakouts(ohlcv, threshold_pct=0.98)

    assert len(breakouts) == 2
    # SYM1 should be first with distance_pct > 0
    assert breakouts[0]["symbol"] == "SYM1"
    assert breakouts[0]["distance_pct"] > 0
    assert breakouts[0]["status"] in ("NEW_52W_HIGH", "VCP_BREAKOUT")

    # SYM2 is near breakout
    assert breakouts[1]["symbol"] == "SYM2"
    assert breakouts[1]["distance_pct"] < 0
    assert breakouts[1]["status"] in ("NEAR_52W_BREAKOUT", "VCP_CONSOLIDATION")
