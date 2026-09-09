"""Pure NumPy/SciPy L2-regularized Ridge Ranker.

Solves the cross-sectional factor ranking problem:
min_w ||X w - y||_2^2 + alpha * ||w||_2^2

Uses direct Cholesky/SVD inversion via scipy.linalg.solve for lightning-fast execution (<5ms)
with zero Docker dependency footprint.
"""

from typing import Any, Dict, List, Optional, Sequence

import numpy as np
from scipy import linalg


class RidgeRanker:
    """L2-regularized linear model optimized for cross-sectional ranking."""

    def __init__(self, alpha: float = 10.0, fit_intercept: bool = True):
        self.alpha = float(alpha)
        self.fit_intercept = fit_intercept
        self.weights_: Optional[np.ndarray] = None
        self.intercept_: float = 0.0
        self.feature_names_: List[str] = []

    def fit(
        self,
        X: np.ndarray,
        y: np.ndarray,
        feature_names: Optional[Sequence[str]] = None,
    ) -> "RidgeRanker":
        """Fits Ridge regression weights on feature matrix X and target y."""
        X_mat = np.asarray(X, dtype=float)
        y_vec = np.asarray(y, dtype=float)

        n_samples, n_features = X_mat.shape

        if feature_names:
            self.feature_names_ = list(feature_names)
        else:
            self.feature_names_ = [f"f_{i}" for i in range(n_features)]

        if self.fit_intercept:
            x_mean = np.mean(X_mat, axis=0)
            y_mean = np.mean(y_vec)
            X_c = X_mat - x_mean
            y_c = y_vec - y_mean
        else:
            X_c = X_mat
            y_c = y_vec
            x_mean = np.zeros(n_features)
            y_mean = 0.0

        # Normal equations: (X^T X + alpha * I) w = X^T y
        A = X_c.T @ X_c + self.alpha * np.eye(n_features)
        b = X_c.T @ y_c

        try:
            self.weights_ = linalg.solve(A, b, assume_a="pos")
        except linalg.LinAlgError:
            # Fallback to pseudoinverse if matrix is ill-conditioned
            self.weights_ = linalg.pinv(A) @ b

        if self.fit_intercept:
            self.intercept_ = float(y_mean - x_mean @ self.weights_)
        else:
            self.intercept_ = 0.0

        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Generates continuous predicted ranking scores."""
        if self.weights_ is None:
            raise ValueError("Model must be fitted before predict() is called.")

        X_mat = np.asarray(X, dtype=float)
        return X_mat @ self.weights_ + self.intercept_

    def get_feature_importances(self) -> Dict[str, float]:
        """Returns normalized absolute feature weights (|w_j| / sum(|w|))."""
        if self.weights_ is None:
            return {}

        abs_w = np.abs(self.weights_)
        total = np.sum(abs_w)
        if total <= 1e-12:
            return {name: 0.0 for name in self.feature_names_}

        norm_w = abs_w / total
        return {
            name: round(float(w), 4)
            for name, w in zip(self.feature_names_, norm_w)
        }

    def get_raw_weights(self) -> Dict[str, float]:
        """Returns signed weights per feature."""
        if self.weights_ is None:
            return {}
        return {
            name: round(float(w), 5)
            for name, w in zip(self.feature_names_, self.weights_)
        }
