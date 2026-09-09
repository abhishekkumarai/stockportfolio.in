"""Quant ML Alpha Factor Matrix & Ranking API routes."""

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Query

from app.ml.pipeline import run_quant_alpha_pipeline

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ml", tags=["Quant ML"])


@router.get("/rankings")
def get_ml_rankings(
    universe: str = Query("NIFTY50", description="Universe index, e.g. NIFTY50"),
    use_cache: bool = Query(True, description="Whether to serve from in-memory TTL cache"),
) -> Dict[str, Any]:
    """Runs the cross-sectional Quant ML Alpha ranker over the universe.

    Returns:
    - Decile 1 to 10 rankings (Decile 10 = Strong Buy top tier)
    - Volatility-scaled trade levels: Entry, Target (+2.0 ATR), Stop Loss (-1.5 ATR)
    - Feature attribution driver pills (e.g., "+Momentum 20d", "+High ROCE Quality")
    - Out-of-sample validation metrics (Rank IC, Information Ratio)
    - Indian tax contextualization (STCG @ 20%, LTCG @ 12.5%)
    """
    return run_quant_alpha_pipeline(universe_index=universe, use_cache=use_cache)


@router.get("/metrics")
def get_model_metrics(
    universe: str = Query("NIFTY50", description="Universe index, e.g. NIFTY50"),
    use_cache: bool = Query(True, description="Whether to serve from in-memory TTL cache"),
) -> Dict[str, Any]:
    """Returns model integrity metrics: Purged Walk-Forward Rank IC, Information Ratio,
    and Abstention Gate status against the naive baseline.
    """
    pipeline_res = run_quant_alpha_pipeline(universe_index=universe, use_cache=use_cache)
    if not pipeline_res.get("available", False):
        return pipeline_res

    return {
        "available": True,
        "universe_index": universe.upper(),
        "model_type": pipeline_res.get("model_type"),
        "model_metrics": pipeline_res.get("model_metrics"),
        "feature_importances": pipeline_res.get("feature_importances"),
    }
