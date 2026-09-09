"""Gradient Boosted Decision Tree Ranker with graceful RidgeRanker fallback.

If LightGBM is available in the environment, trains a shallow regularized tree ensemble.
If LightGBM is absent, transparently falls back to RidgeRanker with zero disruption.
"""

import logging
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from app.ml.models.linear import RidgeRanker

logger = logging.getLogger(__name__)

try:
    import lightgbm as lgb
    HAS_LIGHTGBM = True
except ImportError:
    HAS_LIGHTGBM = False


class GBTRanker:
    """Gradient boosted tree ranker with automatic linear fallback."""

    def __init__(self, n_estimators: int = 50, learning_rate: float = 0.05, max_depth: int = 3):
        self.n_estimators = n_estimators
        self.learning_rate = learning_rate
        self.max_depth = max_depth
        self.model: Any = None
        self.feature_names_: List[str] = []
        self._fallback = not HAS_LIGHTGBM

    def fit(
        self,
        X: np.ndarray,
        y: np.ndarray,
        feature_names: Optional[Sequence[str]] = None,
    ) -> "GBTRanker":
        if feature_names:
            self.feature_names_ = list(feature_names)
        else:
            self.feature_names_ = [f"f_{i}" for i in range(X.shape[1])]

        if self._fallback:
            self.model = RidgeRanker(alpha=10.0).fit(X, y, feature_names=self.feature_names_)
            return self

        try:
            self.model = lgb.LGBMRegressor(
                n_estimators=self.n_estimators,
                learning_rate=self.learning_rate,
                max_depth=self.max_depth,
                num_leaves=2**self.max_depth,
                random_state=42,
                verbosity=-1,
            )
            self.model.fit(X, y)
        except Exception as exc:
            logger.warning("LightGBM fitting failed (%s); falling back to RidgeRanker.", exc)
            self._fallback = True
            self.model = RidgeRanker(alpha=10.0).fit(X, y, feature_names=self.feature_names_)

        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        if self.model is None:
            raise ValueError("Model must be fitted before predict() is called.")
        return np.asarray(self.model.predict(X), dtype=float)

    def get_feature_importances(self) -> Dict[str, float]:
        if self.model is None:
            return {}
        if self._fallback or not hasattr(self.model, "feature_importances_"):
            return self.model.get_feature_importances()

        raw = np.asarray(self.model.feature_importances_, dtype=float)
        total = np.sum(raw)
        if total <= 1e-12:
            return {name: 0.0 for name in self.feature_names_}
        return {
            name: round(float(w), 4)
            for name, w in zip(self.feature_names_, raw / total)
        }
