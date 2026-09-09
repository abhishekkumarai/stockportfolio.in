"""Factor matrix and feature engineering dataset module for Quant ML Alpha.

Constructs scale-free, stationary, point-in-time features from:
1. Technical Price Momentum: 5d/20d/60d returns, RSI-14, MACD histogram, SMA50/SMA200 distances
2. Volatility & Liquidity: ATR ratio, 20d volatility, Volume surge ratio
3. Macro Betas: beta_crude, beta_usdinr, beta_market
4. Fundamental Quality: ROCE, Debt/Equity, Piotroski, Altman Z

Includes robust cross-sectional Z-score normalization with +/-3.0 sigma winsorization.
"""

import math
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

from app.macro import calculate_stock_macro_betas
from app.technicals import calculate_atr, calculate_macd, calculate_rsi, calculate_sma

FEATURE_COLUMNS = [
    "ret_5d",
    "ret_20d",
    "ret_60d",
    "rsi_14",
    "macd_norm",
    "sma50_dist",
    "sma200_dist",
    "atr_ratio",
    "vol_surge",
    "volatility_20d",
    "beta_crude",
    "beta_usdinr",
    "beta_market",
]

FUNDAMENTAL_FEATURE_COLUMNS = [
    "roce",
    "debt_to_equity",
    "piotroski",
    "altman_z",
]


def extract_stock_features(
    df: pd.DataFrame,
    macro_frames: Optional[Dict[str, pd.Series]] = None,
    fundamentals: Optional[Dict[str, Any]] = None,
) -> pd.DataFrame:
    """Computes scale-free feature time series for a single stock OHLCV DataFrame.

    Args:
        df: OHLCV DataFrame with DatetimeIndex and ['Open', 'High', 'Low', 'Close', 'Volume'].
        macro_frames: Optional dict with 'crude', 'inr', 'market' return series.
        fundamentals: Optional fundamental ratios (roce, debt_to_equity, piotroski, altman_z).

    Returns:
        DataFrame with datetime index containing all engineered feature columns.
    """
    if df is None or df.empty or len(df) < 30:
        return pd.DataFrame()

    closes = df["Close"].astype(float)
    highs = df["High"].astype(float)
    lows = df["Low"].astype(float)
    volumes = df["Volume"].astype(float)

    # 1. Technical Momentum
    ret_5d = closes.pct_change(5)
    ret_20d = closes.pct_change(20)
    ret_60d = closes.pct_change(60) if len(closes) >= 65 else ret_20d

    rsi = calculate_rsi(closes, period=14) / 100.0  # scale to 0.0 - 1.0

    _, _, macd_hist = calculate_macd(closes)
    macd_norm = macd_hist / closes  # normalize by price

    sma50 = calculate_sma(closes, period=50)
    sma50_dist = (closes - sma50) / sma50

    sma200 = calculate_sma(closes, period=200) if len(closes) >= 200 else sma50
    sma200_dist = (closes - sma200) / sma200

    # 2. Volatility & Liquidity
    atr = calculate_atr(df, period=14)
    atr_ratio = atr / closes

    sma20_vol = calculate_sma(volumes, period=20)
    vol_surge = (volumes / sma20_vol).clip(lower=0.1, upper=10.0)

    daily_ret = closes.pct_change()
    volatility_20d = daily_ret.rolling(20).std() * math.sqrt(252)

    # 3. Macro Betas
    beta_crude_val = 0.0
    beta_inr_val = 0.0
    beta_mkt_val = 1.0

    if macro_frames is not None and "market" in macro_frames:
        crude_ret = macro_frames.get("crude", pd.Series(0.0, index=daily_ret.index))
        inr_ret = macro_frames.get("inr", pd.Series(0.0, index=daily_ret.index))
        mkt_ret = macro_frames.get("market", daily_ret)

        betas = calculate_stock_macro_betas(
            stock_returns=daily_ret,
            crude_returns=crude_ret,
            inr_returns=inr_ret,
            market_returns=mkt_ret,
        )
        beta_crude_val = betas.get("beta_crude", 0.0)
        beta_inr_val = betas.get("beta_usdinr", 0.0)
        beta_mkt_val = betas.get("beta_market", 1.0)

    features = pd.DataFrame(
        {
            "ret_5d": ret_5d,
            "ret_20d": ret_20d,
            "ret_60d": ret_60d,
            "rsi_14": rsi,
            "macd_norm": macd_norm,
            "sma50_dist": sma50_dist,
            "sma200_dist": sma200_dist,
            "atr_ratio": atr_ratio,
            "vol_surge": vol_surge,
            "volatility_20d": volatility_20d,
            "beta_crude": beta_crude_val,
            "beta_usdinr": beta_inr_val,
            "beta_market": beta_mkt_val,
        },
        index=df.index,
    )

    # 4. Fundamental Quality Features (Constant across short lookbacks)
    if fundamentals:
        features["roce"] = float(fundamentals.get("roce", 15.0) or 15.0)
        features["debt_to_equity"] = float(fundamentals.get("debt_to_equity", 0.5) or 0.5)
        features["piotroski"] = float(fundamentals.get("piotroski", 6.0) or 6.0)
        features["altman_z"] = float(fundamentals.get("altman_z", 3.0) or 3.0)

    return features


def cross_sectional_standardize(
    df: pd.DataFrame,
    feature_cols: Sequence[str],
    winsorize_sigma: float = 3.0,
) -> pd.DataFrame:
    """Standardizes feature columns cross-sectionally (Z-score = (x - mean) / std),
    clipping extreme outliers at +/- winsorize_sigma.

    Works on a cross-sectional slice (one row per asset) or grouped cross-sections.
    Missing / NaN values are filled with the cross-sectional mean (0.0 after centering).
    """
    out = df.copy()

    for col in feature_cols:
        if col not in out.columns:
            continue
        series = out[col].astype(float)
        mean = series.mean()
        std = series.std()

        if pd.isna(std) or std < 1e-8:
            out[col] = 0.0
        else:
            z = (series - mean) / std
            out[col] = z.clip(lower=-winsorize_sigma, upper=winsorize_sigma).fillna(0.0)

    return out
