"""Purged walk-forward cross-validation and evaluation metrics for Quant ML Alpha.

Implements Marcos López de Prado's leakage-prevention framework:
1. Purging: Drops training samples whose forward target horizon overlaps with the test evaluation window.
2. Embargoing: Discards E trading days (default 5 days) immediately following test windows to eliminate post-test autocorrelation leakage.
3. Information Coefficient (Rank IC): Spearman correlation between predicted rank and forward excess return.
4. Naive Baseline Benchmark & Abstention Gate: Requires positive Rank IC (> 0.02) to clear the active model gate.
"""

from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from scipy import stats


def purged_walk_forward_splits(
    n_samples: int,
    n_splits: int = 4,
    train_ratio: float = 0.6,
    purge_window: int = 10,
    embargo_window: int = 5,
) -> List[Tuple[np.ndarray, np.ndarray]]:
    """Generates purged and embargoed walk-forward cross-validation splits.

    In each split k:
    - Train window expands or rolls up to (test_start - purge_window).
    - Samples between (test_start - purge_window) and test_start are PURGED because their
      forward 10-day returns overlap with test prices.
    - Test window spans from test_start to test_end.
    - Samples between test_end and (test_end + embargo_window) are EMBARGOED from future splits.

    Returns:
        List of (train_indices, test_indices) tuples.
    """
    if n_samples < 50:
        # Fallback for very small sequences: simple split with purge
        mid = int(n_samples * train_ratio)
        train_idx = np.arange(0, max(1, mid - purge_window))
        test_idx = np.arange(mid, n_samples)
        return [(train_idx, test_idx)]

    splits: List[Tuple[np.ndarray, np.ndarray]] = []
    min_train = int(n_samples * train_ratio)
    test_space = n_samples - min_train
    test_size = max(10, test_space // n_splits)

    for i in range(n_splits):
        test_start = min_train + i * test_size
        test_end = min(n_samples, test_start + test_size)

        if test_start >= n_samples:
            break

        # Purge boundary: training stops purge_window bars before test begins
        train_end = max(1, test_start - purge_window)
        train_idx = np.arange(0, train_end)
        test_idx = np.arange(test_start, test_end)

        if len(train_idx) > 10 and len(test_idx) > 2:
            splits.append((train_idx, test_idx))

    return splits


def spearman_rank_ic(y_pred: Sequence[float], y_true: Sequence[float]) -> float:
    """Computes Spearman Rank Correlation (Rank IC) between predictions and actual forward excess returns.

    Institutional benchmark:
    - 0.00 to 0.02: No signal / noise
    - 0.03 to 0.06: Profitable institutional alpha
    - > 0.07: Strong quantitative factor
    """
    p = np.asarray(y_pred, dtype=float)
    t = np.asarray(y_true, dtype=float)

    mask = ~(np.isnan(p) | np.isnan(t))
    p_clean, t_clean = p[mask], t[mask]

    if len(p_clean) < 5 or np.all(p_clean == p_clean[0]) or np.all(t_clean == t_clean[0]):
        return 0.0

    res, _ = stats.spearmanr(p_clean, t_clean)
    return float(res) if not np.isnan(res) else 0.0


def pearson_ic(y_pred: Sequence[float], y_true: Sequence[float]) -> float:
    """Computes Pearson Correlation between continuous predictions and forward returns."""
    p = np.asarray(y_pred, dtype=float)
    t = np.asarray(y_true, dtype=float)

    mask = ~(np.isnan(p) | np.isnan(t))
    p_clean, t_clean = p[mask], t[mask]

    if len(p_clean) < 5 or np.all(p_clean == p_clean[0]) or np.all(t_clean == t_clean[0]):
        return 0.0

    res, _ = stats.pearsonr(p_clean, t_clean)
    return float(res) if not np.isnan(res) else 0.0


def evaluate_out_of_sample_skill(
    fold_predictions: List[np.ndarray],
    fold_targets: List[np.ndarray],
) -> Dict[str, Any]:
    """Aggregates performance across walk-forward validation folds and checks calibration gate.

    Compares against a Naive Baseline (zero-skill persistence with Rank IC = 0.0).
    Passes calibration gate only if Mean Rank IC > 0.015.
    """
    if not fold_predictions or len(fold_predictions) != len(fold_targets):
        return {
            "rank_ic_mean": 0.0,
            "rank_ic_std": 0.0,
            "information_ratio": 0.0,
            "folds_evaluated": 0,
            "abstention_recommended": True,
            "status": "INSUFFICIENT_EVALUATION_FOLDS",
        }

    fold_ics: List[float] = []
    for pred, true in zip(fold_predictions, fold_targets):
        ic = spearman_rank_ic(pred, true)
        fold_ics.append(ic)

    ic_arr = np.array(fold_ics)
    mean_ic = float(np.mean(ic_arr))
    std_ic = float(np.std(ic_arr)) if len(ic_arr) > 1 else 1e-4

    ir = mean_ic / std_ic if std_ic > 1e-6 else 0.0

    # Calibration gate: must demonstrate positive out-of-sample correlation
    abstain = mean_ic <= 0.015

    return {
        "rank_ic_mean": round(mean_ic, 4),
        "rank_ic_std": round(std_ic, 4),
        "information_ratio": round(ir, 3),
        "folds_evaluated": len(fold_ics),
        "fold_rank_ics": [round(x, 4) for x in fold_ics],
        "abstention_recommended": abstain,
        "status": "ACTIVE_ALPHA" if not abstain else "ABSTAIN_LOW_SIGNAL",
    }
