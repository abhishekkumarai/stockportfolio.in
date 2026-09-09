"""Technical analysis indicators and scoring engine.

Pure functions operating on OHLCV pandas Series/DataFrames.
Sourced from Fyers historical candles or yfinance.
Integrates with app.scoring to generate structured, evidence-backed ScoreCards.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from app import scoring

logger = logging.getLogger(__name__)


def calculate_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
    """Calculates Relative Strength Index (RSI) using Wilder's exponential smoothing."""
    delta = prices.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi.fillna(50.0)



def calculate_sma(prices: pd.Series, period: int) -> pd.Series:
    """Simple Moving Average."""
    return prices.rolling(window=period, min_periods=max(1, period // 2)).mean()


def calculate_ema(prices: pd.Series, period: int) -> pd.Series:
    """Exponential Moving Average."""
    return prices.ewm(span=period, adjust=False).mean()


def calculate_macd(
    prices: pd.Series, fast: int = 12, slow: int = 26, signal_period: int = 9
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """Calculates MACD line, signal line, and histogram."""
    ema_fast = calculate_ema(prices, fast)
    ema_slow = calculate_ema(prices, slow)
    macd_line = ema_fast - ema_slow
    signal_line = calculate_ema(macd_line, signal_period)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def calculate_bollinger_bands(
    prices: pd.Series, period: int = 20, num_std: float = 2.0
) -> Tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
    """Calculates Bollinger Bands: (Upper, Middle, Lower, %B)."""
    middle = calculate_sma(prices, period)
    std = prices.rolling(window=period, min_periods=max(1, period // 2)).std()
    upper = middle + (std * num_std)
    lower = middle - (std * num_std)
    bandwidth = upper - lower
    pct_b = (prices - lower) / bandwidth.replace(0, np.nan)
    return upper, middle, lower, pct_b.fillna(0.5)


def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average True Range from DataFrame with High, Low, Close columns."""
    if len(df) < 2:
        return pd.Series(0.0, index=df.index)

    high = df["High"]
    low = df["Low"]
    close = df["Close"].shift(1)

    tr1 = high - low
    tr2 = (high - close).abs()
    tr3 = (low - close).abs()

    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / period, adjust=False).mean()
    return atr


def calculate_obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    """On-Balance Volume (OBV)."""
    direction = np.sign(close.diff().fillna(0))
    obv = (direction * volume).cumsum()
    return obv


def calculate_supertrend(
    df: pd.DataFrame, period: int = 10, multiplier: float = 3.0
) -> Tuple[pd.Series, pd.Series]:
    """Calculates Supertrend (trend_line, direction: 1 for Bullish, -1 for Bearish)."""
    if len(df) < period:
        return pd.Series(df["Close"]), pd.Series(1, index=df.index)

    atr = calculate_atr(df, period)
    hl2 = (df["High"] + df["Low"]) / 2.0
    upper_band = hl2 + (multiplier * atr)
    lower_band = hl2 - (multiplier * atr)

    supertrend = pd.Series(index=df.index, dtype="float64")
    direction = pd.Series(1, index=df.index, dtype="int64")

    for i in range(1, len(df)):
        curr_close = df["Close"].iloc[i]
        prev_upper = upper_band.iloc[i - 1]
        prev_lower = lower_band.iloc[i - 1]

        if curr_close > prev_upper:
            direction.iloc[i] = 1
        elif curr_close < prev_lower:
            direction.iloc[i] = -1
        else:
            direction.iloc[i] = direction.iloc[i - 1]
            if direction.iloc[i] == 1 and lower_band.iloc[i] < prev_lower:
                lower_band.iloc[i] = prev_lower
            if direction.iloc[i] == -1 and upper_band.iloc[i] > prev_upper:
                upper_band.iloc[i] = prev_upper

        supertrend.iloc[i] = lower_band.iloc[i] if direction.iloc[i] == 1 else upper_band.iloc[i]

    return supertrend, direction


def calculate_adx(df: pd.DataFrame, period: int = 14) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """Calculates ADX, +DI, and -DI."""
    if len(df) < period + 1:
        return pd.Series(20.0, index=df.index), pd.Series(20.0, index=df.index), pd.Series(20.0, index=df.index)

    high = df["High"]
    low = df["Low"]

    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    atr = calculate_atr(df, period)
    plus_di = 100.0 * (pd.Series(plus_dm, index=df.index).ewm(alpha=1 / period, adjust=False).mean() / atr.replace(0, np.nan))
    minus_di = 100.0 * (pd.Series(minus_dm, index=df.index).ewm(alpha=1 / period, adjust=False).mean() / atr.replace(0, np.nan))

    dx = 100.0 * ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan))
    adx = dx.ewm(alpha=1 / period, adjust=False).mean()

    return adx.fillna(20.0), plus_di.fillna(20.0), minus_di.fillna(20.0)


def extract_technicals(df: pd.DataFrame) -> Dict[str, Any]:
    """Extract current technical indicator snapshot from OHLCV dataframe."""
    if df is None or len(df) < 5:
        return {"available": False, "reason": "Insufficient price data"}

    close = df["Close"]
    volume = df["Volume"] if "Volume" in df.columns else pd.Series(0, index=df.index)

    current_price = float(close.iloc[-1])
    sma20 = float(calculate_sma(close, 20).iloc[-1]) if len(close) >= 20 else current_price
    sma50 = float(calculate_sma(close, 50).iloc[-1]) if len(close) >= 50 else current_price
    sma200 = float(calculate_sma(close, 200).iloc[-1]) if len(close) >= 200 else current_price
    ema50 = float(calculate_ema(close, 50).iloc[-1]) if len(close) >= 50 else current_price
    ema200 = float(calculate_ema(close, 200).iloc[-1]) if len(close) >= 200 else current_price

    rsi_series = calculate_rsi(close, 14)
    rsi14 = float(rsi_series.iloc[-1])

    macd_line, signal_line, hist = calculate_macd(close)
    macd_val = float(macd_line.iloc[-1])
    macd_sig = float(signal_line.iloc[-1])
    macd_hist = float(hist.iloc[-1])

    upper_bb, mid_bb, lower_bb, pct_b = calculate_bollinger_bands(close, 20, 2.0)
    bb_pct = float(pct_b.iloc[-1])

    atr_series = calculate_atr(df, 14)
    atr_val = float(atr_series.iloc[-1]) if len(atr_series) > 0 else 0.0
    atr_pct = (atr_val / current_price * 100.0) if current_price else 0.0

    adx_series, plus_di, minus_di = calculate_adx(df, 14)
    adx_val = float(adx_series.iloc[-1])
    p_di = float(plus_di.iloc[-1])
    m_di = float(minus_di.iloc[-1])

    # Volume dynamics
    vol20 = float(volume.tail(20).mean()) if len(volume) >= 20 else float(volume.mean() or 1)
    current_vol = float(volume.iloc[-1]) if len(volume) > 0 else 0.0
    vol_surge = (current_vol / vol20) if vol20 > 0 else 1.0

    # Trend states
    above_sma50 = current_price >= sma50
    above_sma200 = current_price >= sma200
    above_ema200 = current_price >= ema200
    golden_cross = sma50 >= sma200
    death_cross = sma50 < sma200 and not above_sma200

    return {
        "available": True,
        "current_price": round(current_price, 2),
        "sma20": round(sma20, 2),
        "sma50": round(sma50, 2),
        "sma200": round(sma200, 2),
        "ema50": round(ema50, 2),
        "ema200": round(ema200, 2),
        "rsi14": round(rsi14, 2),
        "macd": round(macd_val, 2),
        "macd_signal": round(macd_sig, 2),
        "macd_histogram": round(macd_hist, 2),
        "bollinger_pct_b": round(bb_pct, 3),
        "atr": round(atr_val, 2),
        "atr_pct": round(atr_pct, 2),
        "adx": round(adx_val, 2),
        "plus_di": round(p_di, 2),
        "minus_di": round(m_di, 2),
        "vol_surge": round(vol_surge, 2),
        "above_sma50": above_sma50,
        "above_sma200": above_sma200,
        "above_ema200": above_ema200,
        "golden_cross": golden_cross,
        "death_cross": death_cross,
    }


def score_technicals(tech: Dict[str, Any]) -> scoring.ScoreCard:
    """Converts a technical indicators dict into an evidence-backed ScoreCard (0-100)."""
    if not tech.get("available"):
        return scoring.ScoreCard(name="technicals", score=None, coverage=0.0, notes=[tech.get("reason", "No data")])

    signals: List[scoring.Signal] = []

    # 1. Trend & Moving Averages (Weight: 30%)
    price = tech["current_price"]
    sma50 = tech["sma50"]
    sma200 = tech["sma200"]

    trend_score = 50.0
    if price > sma50 and price > sma200:
        trend_score = 85.0 if tech["golden_cross"] else 75.0
        trend_reason = "Price trading above both 50 and 200 SMA (Bullish Trend)"
    elif price < sma50 and price < sma200:
        trend_score = 15.0 if tech["death_cross"] else 25.0
        trend_reason = "Price trading below both 50 and 200 SMA (Bearish Breakdown)"
    elif price > sma200:
        trend_score = 60.0
        trend_reason = "Price above 200 SMA support but below 50 SMA"
    else:
        trend_score = 40.0
        trend_reason = "Price below 200 SMA long-term average"

    signals.append(
        scoring.Signal(
            key="trend_moving_averages",
            score=trend_score,
            value={"price": price, "sma50": sma50, "sma200": sma200},
            weight=0.30,
            reason=trend_reason,
        )
    )

    # 2. Momentum / RSI (Weight: 25%)
    rsi = tech["rsi14"]
    if rsi < 30:
        rsi_score = 75.0  # Oversold rebound opportunity
        rsi_reason = f"RSI at {rsi:.1f} is deeply oversold (potential rebound zone)"
    elif rsi > 70:
        rsi_score = 40.0  # Overbought warning
        rsi_reason = f"RSI at {rsi:.1f} is in overbought territory (caution on fresh entries)"
    elif 50 <= rsi <= 65:
        rsi_score = 80.0  # Strong healthy bullish momentum
        rsi_reason = f"RSI at {rsi:.1f} indicates strong, steady upward momentum"
    elif 40 <= rsi < 50:
        rsi_score = 50.0  # Neutral
        rsi_reason = f"RSI at {rsi:.1f} is neutral"
    else:
        rsi_score = 35.0  # Weak momentum
        rsi_reason = f"RSI at {rsi:.1f} shows weak momentum"

    signals.append(
        scoring.Signal(
            key="rsi_momentum",
            score=rsi_score,
            value=rsi,
            unit="points",
            weight=0.25,
            reason=rsi_reason,
        )
    )

    # 3. MACD Histogram & Signal (Weight: 20%)
    macd_hist = tech["macd_histogram"]
    macd_val = tech["macd"]
    if macd_val > 0 and macd_hist > 0:
        macd_score = 80.0
        macd_reason = "MACD is positive and expanding above signal line (Strong Momentum)"
    elif macd_val < 0 and macd_hist < 0:
        macd_score = 20.0
        macd_reason = "MACD is negative and expanding downward (Bearish Momentum)"
    elif macd_hist > 0:
        macd_score = 65.0
        macd_reason = "MACD histogram turned positive (Early Bullish Reversal)"
    else:
        macd_score = 35.0
        macd_reason = "MACD histogram turned negative (Early Bearish Weakness)"

    signals.append(
        scoring.Signal(
            key="macd",
            score=macd_score,
            value=macd_val,
            weight=0.20,
            reason=macd_reason,
        )
    )

    # 4. ADX & Trend Strength (Weight: 15%)
    adx = tech["adx"]
    p_di = tech["plus_di"]
    m_di = tech["minus_di"]
    if adx >= 25 and p_di > m_di:
        adx_score = 85.0
        adx_reason = f"ADX at {adx:.1f} confirms a strong active uptrend (+DI > -DI)"
    elif adx >= 25 and m_di > p_di:
        adx_score = 20.0
        adx_reason = f"ADX at {adx:.1f} confirms a strong active downtrend (-DI > +DI)"
    else:
        adx_score = 50.0
        adx_reason = f"ADX at {adx:.1f} indicates rangebound / consolidating price action"

    signals.append(
        scoring.Signal(
            key="adx_trend_strength",
            score=adx_score,
            value=adx,
            weight=0.15,
            reason=adx_reason,
        )
    )

    # 5. Volume & Volatility / Bollinger Bands (Weight: 10%)
    bb_pct = tech["bollinger_pct_b"]
    vol_surge = tech["vol_surge"]
    vol_score = 50.0
    vol_reason = "Volume and volatility within normal ranges"

    if vol_surge >= 1.5 and price > sma50:
        vol_score = 80.0
        vol_reason = f"Volume surge of {vol_surge:.1f}x confirms bullish accumulation"
    elif vol_surge >= 1.5 and price < sma50:
        vol_score = 20.0
        vol_reason = f"Heavy selling volume ({vol_surge:.1f}x average) confirms institutional distribution"

    signals.append(
        scoring.Signal(
            key="volume_and_volatility",
            score=vol_score,
            value={"vol_surge": vol_surge, "bb_pct_b": bb_pct},
            weight=0.10,
            reason=vol_reason,
        )
    )

    return scoring.blend("technicals", signals, min_coverage=0.6)
