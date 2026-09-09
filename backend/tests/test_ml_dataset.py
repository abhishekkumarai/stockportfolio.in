"""Unit tests for ML factor matrix dataset extraction and cross-sectional standardization."""

import numpy as np
import pandas as pd
import pytest

from app.ml.dataset import (
    FEATURE_COLUMNS,
    cross_sectional_standardize,
    extract_stock_features,
)


def test_extract_stock_features():
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

    macro_frames = {
        "market": pd.Series([0.001] * 100, index=dates),
        "crude": pd.Series([0.002] * 100, index=dates),
        "inr": pd.Series([0.0005] * 100, index=dates),
    }

    fundamentals = {
        "roce": 22.5,
        "debt_to_equity": 0.2,
        "piotroski": 8,
        "altman_z": 4.5,
    }

    feats = extract_stock_features(df, macro_frames=macro_frames, fundamentals=fundamentals)

    assert not feats.empty
    assert len(feats) == 100
    for col in FEATURE_COLUMNS:
        assert col in feats.columns

    assert feats["roce"].iloc[-1] == 22.5
    assert feats["debt_to_equity"].iloc[-1] == 0.2
    assert feats["ret_20d"].iloc[-1] > 0


def test_cross_sectional_standardize():
    # 5 assets with varying momentum
    df = pd.DataFrame(
        {
            "ret_20d": [0.05, 0.10, -0.02, 0.08, 0.50],  # 0.50 is an extreme outlier
            "atr_ratio": [0.02, 0.025, 0.015, 0.02, 0.03],
        }
    )

    std_df = cross_sectional_standardize(df, feature_cols=["ret_20d", "atr_ratio"], winsorize_sigma=2.5)

    # Standardized mean should be near 0
    assert pytest.approx(std_df["ret_20d"].mean(), abs=1e-5) == 0.0
    # Clipped within +/- 2.5 sigma
    assert std_df["ret_20d"].max() <= 2.5
    assert std_df["ret_20d"].min() >= -2.5
