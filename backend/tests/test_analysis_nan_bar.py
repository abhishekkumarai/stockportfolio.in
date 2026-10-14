import json
import math

import numpy as np
import pandas as pd
import pytest

from app import analysis


class _FakeTicker:
    """yfinance.Ticker stand-in: 300 daily bars ending in an incomplete (NaN) bar."""

    def __init__(self, symbol):
        self.info = {
            "currentPrice": 3000.0,
            "regularMarketPreviousClose": 2990.0,
            "longName": "Test Co",
            "currency": "INR",
        }

    def history(self, period, interval):
        idx = pd.date_range("2025-01-01", periods=300, freq="D")
        close = np.linspace(2000, 3000, 300)
        df = pd.DataFrame(
            {"Open": close, "High": close + 5, "Low": close - 5, "Close": close, "Volume": 1000},
            index=idx,
        )
        df.iloc[-1, df.columns.get_indexer(["Open", "High", "Low", "Close"])] = np.nan
        return df


def _has_bad_float(obj):
    if isinstance(obj, float):
        return math.isnan(obj) or math.isinf(obj)
    if isinstance(obj, dict):
        return any(_has_bad_float(v) for v in obj.values())
    if isinstance(obj, list):
        return any(_has_bad_float(v) for v in obj)
    return False


@pytest.mark.parametrize("timeframe", ["month", "year"])
def test_trailing_nan_bar_does_not_poison_the_result(monkeypatch, timeframe):
    monkeypatch.setattr(analysis.yf, "Ticker", _FakeTicker)
    result = analysis.get_stock_analysis("TEST.NS", [], timeframe=timeframe)

    assert not _has_bad_float(result)
    json.dumps(result, allow_nan=False)  # what FastAPI's JSON encoder requires
    # The incomplete bar is dropped, not rendered as a zero or carried forward.
    assert len(result["chart_data"]) > 0
    assert all(bar["close"] == bar["close"] for bar in result["chart_data"])
    assert result["technicals"]["sma200"] > 0


def test_all_nan_history_fails_visibly_not_with_a_fabricated_result(monkeypatch):
    class _AllNan(_FakeTicker):
        def history(self, period, interval):
            df = super().history(period, interval)
            df[:] = np.nan
            return df

    monkeypatch.setattr(analysis.yf, "Ticker", _AllNan)
    with pytest.raises(analysis.PriceDataUnavailable):
        analysis.get_stock_analysis("TEST.NS", [])
