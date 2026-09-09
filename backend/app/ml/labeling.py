"""Target labeling module for Quant ML Alpha.

Implements:
1. Forward H-day (default 10-day) relative excess return over NIFTY 50 benchmark:
   y_{i, t} = R_{i, t -> t+H} - R_{benchmark, t -> t+H}
2. Volatility-scaled dynamic ternary bands:
   sigma_{h, i, t} = (ATR_14(t) * sqrt(H)) / Price_t
   Upper band = +0.5 * sigma_h
   Lower band = -0.5 * sigma_h
   Classes: BULLISH (+1), NEUTRAL (0), BEARISH (-1)

Strict zero-leakage: all forward targets use .shift(-H). The most recent H bars
evaluate to NaN and are pruned from training sets.
"""

import math
from typing import Optional, Tuple

import numpy as np
import pandas as pd


def compute_forward_returns(prices: pd.Series, horizon: int = 10) -> pd.Series:
    """Computes forward percentage return from bar t to bar t+horizon.

    R_{t -> t+H} = (Price_{t+H} / Price_t) - 1.0

    Uses .shift(-horizon) so that value on date t represents the return over the next H bars.
    Last H values are NaN.
    """
    clean = prices.astype(float)
    forward_price = clean.shift(-horizon)
    return (forward_price - clean) / clean


def compute_forward_excess_returns(
    stock_prices: pd.Series,
    benchmark_prices: pd.Series,
    horizon: int = 10,
) -> pd.Series:
    """Computes forward relative excess return over benchmark:
    Excess_{i, t} = R_{stock, t -> t+H} - R_{benchmark, t -> t+H}
    """
    aligned = pd.DataFrame(
        {
            "stock": stock_prices,
            "benchmark": benchmark_prices,
        }
    ).dropna()

    if len(aligned) == 0:
        return pd.Series(dtype=float)

    stock_fwd = compute_forward_returns(aligned["stock"], horizon=horizon)
    bench_fwd = compute_forward_returns(aligned["benchmark"], horizon=horizon)

    excess = stock_fwd - bench_fwd
    return excess


def compute_volatility_scaled_labels(
    excess_returns: pd.Series,
    stock_prices: pd.Series,
    atr_series: pd.Series,
    horizon: int = 10,
    band_multiplier: float = 0.5,
) -> pd.DataFrame:
    """Generates volatility-scaled ternary classification labels.

    Dynamic threshold scales with realized volatility:
        sigma_h = (ATR_14 * sqrt(horizon)) / Price
        threshold = band_multiplier * sigma_h

    Labels:
        +1: BULLISH  (Excess return > +threshold)
         0: NEUTRAL  (-threshold <= Excess return <= +threshold)
        -1: BEARISH  (Excess return < -threshold)

    Returns:
        DataFrame with columns:
        ['excess_return', 'sigma_h', 'upper_band', 'lower_band', 'label_class', 'label_name']
    """
    df = pd.DataFrame(
        {
            "excess_return": excess_returns,
            "price": stock_prices,
            "atr": atr_series,
        }
    ).dropna()

    if len(df) == 0:
        return pd.DataFrame(
            columns=["excess_return", "sigma_h", "upper_band", "lower_band", "label_class", "label_name"]
        )

    # Calculate expected horizon volatility sigma_h
    sqrt_h = math.sqrt(horizon)
    sigma_h = (df["atr"] * sqrt_h) / df["price"]

    # Floor sigma_h at 0.5% to avoid division / near-zero bands on flat assets
    sigma_h = sigma_h.clip(lower=0.005)

    upper_band = band_multiplier * sigma_h
    lower_band = -band_multiplier * sigma_h

    label_class = np.zeros(len(df), dtype=int)
    label_name = np.array(["NEUTRAL"] * len(df), dtype=object)

    bullish_mask = df["excess_return"] > upper_band
    bearish_mask = df["excess_return"] < lower_band

    label_class[bullish_mask] = 1
    label_name[bullish_mask] = "BULLISH"

    label_class[bearish_mask] = -1
    label_name[bearish_mask] = "BEARISH"

    res = pd.DataFrame(
        {
            "excess_return": df["excess_return"],
            "sigma_h": sigma_h,
            "upper_band": upper_band,
            "lower_band": lower_band,
            "label_class": label_class,
            "label_name": label_name,
        },
        index=df.index,
    )

    return res
