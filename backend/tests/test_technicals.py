"""Unit tests for technical analysis indicators and scoring."""

import pandas as pd
import pytest

from app.technicals import (
    calculate_adx,
    calculate_atr,
    calculate_bollinger_bands,
    calculate_ema,
    calculate_macd,
    calculate_sma,
    extract_technicals,
    score_technicals,
)


@pytest.fixture
def sample_ohlcv_df():
    """Generates synthetic trending OHLCV series."""
    dates = pd.date_range("2024-01-01", periods=100, freq="B")
    prices = [100.0 + i * 0.5 for i in range(100)]
    df = pd.DataFrame(
        {
            "Open": prices,
            "High": [p + 2.0 for p in prices],
            "Low": [p - 2.0 for p in prices],
            "Close": prices,
            "Volume": [100000 + i * 500 for i in range(100)],
        },
        index=dates,
    )
    return df


def test_sma_ema(sample_ohlcv_df):
    close = sample_ohlcv_df["Close"]
    sma20 = calculate_sma(close, 20)
    ema20 = calculate_ema(close, 20)

    assert len(sma20) == 100
    assert len(ema20) == 100
    assert sma20.iloc[-1] > 0
    assert ema20.iloc[-1] > 0


def test_macd(sample_ohlcv_df):
    close = sample_ohlcv_df["Close"]
    macd_line, sig_line, hist = calculate_macd(close)

    assert len(macd_line) == 100
    assert len(sig_line) == 100
    assert len(hist) == 100
    # In an uptrend, MACD should generally be positive
    assert macd_line.iloc[-1] > 0


def test_bollinger_and_atr(sample_ohlcv_df):
    upper, mid, lower, pct_b = calculate_bollinger_bands(sample_ohlcv_df["Close"], 20)
    atr = calculate_atr(sample_ohlcv_df, 14)

    assert len(upper) == 100
    assert upper.iloc[-1] > lower.iloc[-1]
    assert atr.iloc[-1] > 0


def test_extract_and_score_technicals(sample_ohlcv_df):
    tech = extract_technicals(sample_ohlcv_df)
    assert tech["available"] is True
    assert tech["current_price"] > 0
    assert "rsi14" in tech
    assert "macd" in tech

    scorecard = score_technicals(tech)
    assert scorecard.available is True
    assert scorecard.score is not None
    assert 0.0 <= scorecard.score <= 100.0
    assert scorecard.action in ("BUY", "STRONG_BUY", "HOLD", "REDUCE", "EXIT")
