"""Unit tests for ML models, trade structuring, and pipeline components."""

import numpy as np
import pytest

from app.ml.models.gbm import GBTRanker
from app.ml.models.linear import RidgeRanker
from app.ml.pipeline import format_driver_pills, structure_trade_levels


def test_ridge_ranker_convergence():
    np.random.seed(42)
    n_samples = 150
    # 3 features: f1 is strong positive, f2 is mild negative, f3 is noise
    X = np.random.randn(n_samples, 3)
    y = 3.0 * X[:, 0] - 1.5 * X[:, 1] + 0.1 * np.random.randn(n_samples)

    ranker = RidgeRanker(alpha=1.0)
    ranker.fit(X, y, feature_names=["f_momentum", "f_debt", "f_noise"])

    importances = ranker.get_feature_importances()
    weights = ranker.get_raw_weights()

    assert importances["f_momentum"] > importances["f_debt"]
    assert importances["f_debt"] > importances["f_noise"]
    assert weights["f_momentum"] > 0
    assert weights["f_debt"] < 0

    preds = ranker.predict(X[:5])
    assert len(preds) == 5


def test_gbt_ranker_fallback():
    X = np.array([[1.0, 2.0], [2.0, 3.0], [3.0, 4.0], [4.0, 5.0]])
    y = np.array([0.1, 0.2, 0.3, 0.4])

    gbt = GBTRanker(n_estimators=10)
    gbt.fit(X, y, feature_names=["feat1", "feat2"])

    preds = gbt.predict(X)
    assert len(preds) == 4
    importances = gbt.get_feature_importances()
    assert "feat1" in importances
    assert "feat2" in importances


def test_structure_trade_levels():
    current_price = 1000.0
    atr = 25.0

    trade = structure_trade_levels(current_price, atr)

    # Target = 1000 + 2.0 * 25 = 1050
    assert trade["entry_price"] == 1000.0
    assert trade["target_price"] == 1050.0
    # Stop = 1000 - 1.5 * 25 = 962.5
    assert trade["stop_loss"] == 962.5
    assert trade["target_pct"] == 5.0
    assert trade["stop_loss_pct"] == 3.75
    # Risk/Reward ratio = 5.0 / 3.75 = 1.33
    assert trade["risk_reward_ratio"] == 1.33


def test_format_driver_pills():
    stock_z = {
        "ret_20d": 2.1,
        "roce": 1.8,
        "debt_to_equity": -1.5,
        "vol_surge": 0.2,
    }
    raw_weights = {
        "ret_20d": 0.25,
        "roce": 0.20,
        "debt_to_equity": -0.15,  # negative debt is good
        "vol_surge": 0.05,
    }

    pills = format_driver_pills(stock_z, raw_weights)
    assert len(pills) <= 3
    assert "+20d Momentum" in pills
    assert "+High ROCE Quality" in pills
    assert "+Low Leverage" in pills
