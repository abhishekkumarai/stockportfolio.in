"""Unit tests for purged walk-forward cross-validation and Rank IC evaluation."""

import numpy as np
import pytest

from app.ml.validation import (
    evaluate_out_of_sample_skill,
    pearson_ic,
    purged_walk_forward_splits,
    spearman_rank_ic,
)


def test_purged_walk_forward_splits():
    n_samples = 200
    purge = 10
    embargo = 5

    splits = purged_walk_forward_splits(
        n_samples=n_samples,
        n_splits=4,
        train_ratio=0.5,
        purge_window=purge,
        embargo_window=embargo,
    )

    assert len(splits) > 0

    for train_idx, test_idx in splits:
        test_start = test_idx[0]
        train_end = train_idx[-1]

        # Zero leakage guarantee: train set ends at least `purge` bars before test begins
        assert test_start - train_end >= purge
        # Test indices must be strictly ahead of train indices
        assert np.all(test_idx > train_end)


def test_rank_ic_metrics():
    # Perfect alignment
    y_true = np.array([0.01, 0.03, 0.05, 0.07, 0.09])
    y_pred = np.array([1.0, 2.0, 3.0, 4.0, 5.0])

    assert pytest.approx(spearman_rank_ic(y_pred, y_true), abs=1e-5) == 1.0
    assert pytest.approx(pearson_ic(y_pred, y_true), abs=1e-4) == 1.0

    # Perfect inversion
    y_pred_inv = np.array([5.0, 4.0, 3.0, 2.0, 1.0])
    assert pytest.approx(spearman_rank_ic(y_pred_inv, y_true), abs=1e-5) == -1.0


def test_evaluate_out_of_sample_skill_gate():
    # Model showing positive skill across 3 folds (Rank IC > 0.02)
    fold_preds = [
        np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0]),
        np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0]),
        np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0]),
    ]
    fold_targets = [
        np.array([0.01, 0.02, 0.04, 0.05, 0.06, 0.08]),
        np.array([0.01, 0.03, 0.02, 0.05, 0.07, 0.08]),
        np.array([0.02, 0.01, 0.04, 0.06, 0.05, 0.09]),
    ]

    res = evaluate_out_of_sample_skill(fold_preds, fold_targets)
    assert res["rank_ic_mean"] > 0.05
    assert res["abstention_recommended"] is False
    assert res["status"] == "ACTIVE_ALPHA"

    # Model showing negative/zero skill -> Abstention gate triggers
    fold_targets_bad = [
        np.array([0.08, 0.06, 0.05, 0.04, 0.02, 0.01]),
        np.array([0.07, 0.05, 0.03, 0.02, 0.01, 0.00]),
        np.array([0.09, 0.05, 0.06, 0.04, 0.01, 0.02]),
    ]
    res_bad = evaluate_out_of_sample_skill(fold_preds, fold_targets_bad)
    assert res_bad["rank_ic_mean"] < 0.0
    assert res_bad["abstention_recommended"] is True
    assert res_bad["status"] == "ABSTAIN_LOW_SIGNAL"
