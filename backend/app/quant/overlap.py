"""Mutual fund look-through and portfolio stock overlap analyzer."""

import logging
from typing import Any, Dict, List, Set, Tuple

logger = logging.getLogger(__name__)


def calculate_fund_overlap(
    fund_a_stocks: List[Dict[str, Any]], fund_b_stocks: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Calculates holding overlap between two mutual funds.
    Each item is {"symbol": str, "name": str, "weight_pct": float}.
    """
    map_a = {item["symbol"].upper(): item.get("weight_pct", 0.0) for item in fund_a_stocks}
    map_b = {item["symbol"].upper(): item.get("weight_pct", 0.0) for item in fund_b_stocks}

    common_symbols = set(map_a.keys()).intersection(set(map_b.keys()))

    # Overlap is the sum of min(weight_a, weight_b)
    overlap_weight_pct = sum(min(map_a[sym], map_b[sym]) for sym in common_symbols)

    common_holdings = [
        {
            "symbol": sym,
            "weight_in_fund_a_pct": map_a[sym],
            "weight_in_fund_b_pct": map_b[sym],
            "min_overlap_pct": min(map_a[sym], map_b[sym]),
        }
        for sym in sorted(common_symbols, key=lambda s: min(map_a[s], map_b[s]), reverse=True)
    ]

    return {
        "overlap_pct": round(overlap_weight_pct, 2),
        "common_stocks_count": len(common_symbols),
        "common_holdings": common_holdings,
    }
