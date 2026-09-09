"""Unit tests for Quant ML forward excess return and volatility-scaled labeling."""

import numpy as np
import pandas as pd
import pytest

from app.ml.labeling import (
    compute_forward_excess_returns,
    compute_forward_returns,
    compute_volatility_scaled_labels,
)


def test_compute_forward_returns_zero_leakage():
    prices = pd.Series([100.0, 105.0, 110.0, 115.0, 120.0])
    # Horizon = 2 bars
    fwd = compute_forward_returns(prices, horizon=2)

    # At idx 0: forward price is 110.0 -> return is (110 - 100) / 100 = 0.10
    assert pytest.approx(fwd.iloc[0], rel=1e-5) == 0.10
    # At idx 1: forward price is 115.0 -> return is (115 - 105) / 105 = 0.095238
    assert pytest.approx(fwd.iloc[1], rel=1e-5) == (115.0 - 105.0) / 105.0
    # Last 2 rows must be NaN (strictly preventing future lookahead)
    assert pd.isna(fwd.iloc[-1])
    assert pd.isna(fwd.iloc[-2])


def test_compute_forward_excess_returns():
    stock = pd.Series([100.0, 102.0, 105.0, 110.0, 112.0])
    bench = pd.Series([1000.0, 1010.0, 1020.0, 1040.0, 1050.0])

    excess = compute_forward_excess_returns(stock, bench, horizon=2)

    # At idx 0: stock fwd ret = (105-100)/100 = 0.05, bench fwd ret = (1020-1000)/1000 = 0.02
    # Excess = 0.05 - 0.02 = 0.03
    assert pytest.approx(excess.iloc[0], rel=1e-5) == 0.03
    assert pd.isna(excess.iloc[-1])
    assert pd.isna(excess.iloc[-2])


def test_volatility_scaled_ternary_labels():
    dates = pd.date_range("2024-01-01", periods=6, freq="B")
    prices = pd.Series([100.0] * 6, index=dates)
    atr = pd.Series([2.0] * 6, index=dates)

    # For horizon=4, sqrt(4) = 2.0
    # sigma_h = (2.0 * 2.0) / 100.0 = 0.04 (4%)
    # With multiplier=0.5:
    # upper band = +0.02 (+2%), lower band = -0.02 (-2%)

    # Returns:
    # idx 0: +0.05 (+5% > +2%) -> BULLISH (+1)
    # idx 1: -0.04 (-4% < -2%) -> BEARISH (-1)
    # idx 2: +0.01 (+1% between -2% and +2%) -> NEUTRAL (0)
    # idx 3: -0.01 (-1% between -2% and +2%) -> NEUTRAL (0)
    # idx 4, 5: NaN
    excess_ret = pd.Series([0.05, -0.04, 0.01, -0.01, np.nan, np.nan], index=dates)

    labeled = compute_volatility_scaled_labels(
        excess_returns=excess_ret,
        stock_prices=prices,
        atr_series=atr,
        horizon=4,
        band_multiplier=0.5,
    )

    assert len(labeled) == 4
    assert labeled.loc[dates[0], "label_class"] == 1
    assert labeled.loc[dates[0], "label_name"] == "BULLISH"

    assert labeled.loc[dates[1], "label_class"] == -1
    assert labeled.loc[dates[1], "label_name"] == "BEARISH"

    assert labeled.loc[dates[2], "label_class"] == 0
    assert labeled.loc[dates[2], "label_name"] == "NEUTRAL"
