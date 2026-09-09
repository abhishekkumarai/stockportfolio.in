"""Market regime detection with hysteresis.

Classifies the market into four states — trending up, trending down, choppy,
crisis — from three observables: realised volatility relative to its own
history, trend strength, and cross-sectional correlation. Correlation matters
most: in a crisis everything moves together, which is precisely when
diversification stops working and a portfolio's measured risk understates its
real risk.

**Hysteresis is the whole point.** A classifier that switches state the moment
a threshold is crossed flaps — volatility oscillates around any fixed level, so
a naive detector reports "crisis / normal / crisis / normal" across a single
week and is useless for anything downstream. Two mechanisms prevent it:

1. **Asymmetric thresholds.** Entering a regime needs a stronger reading than
   staying in it, so a marginal reading holds the current state.
2. **A dwell time.** Once a regime is entered it persists for `min_dwell_days`
   regardless, unless the crisis trigger fires — a genuine crash should not
   have to wait out a dwell timer.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

TRADING_DAYS = 252

REGIMES = ("trending_up", "trending_down", "choppy", "crisis")

REGIME_LABELS = {
    "trending_up": "Trending up",
    "trending_down": "Trending down",
    "choppy": "Choppy / rangebound",
    "crisis": "Crisis",
}

REGIME_GUIDANCE = {
    "trending_up": (
        "Trend-following works, mean-reversion fights the tape, and measured "
        "risk understates the drawdown that ends the trend."
    ),
    "trending_down": (
        "Reduce gross exposure before optimising it. Beta is the dominant "
        "exposure and stock selection rarely rescues a falling market."
    ),
    "choppy": (
        "Mean-reversion has the edge and trend-following bleeds on whipsaws. "
        "Transaction costs matter more than usual here."
    ),
    "crisis": (
        "Correlations converge toward 1, so diversification stops working and "
        "VaR estimated on normal conditions is far too optimistic. Hedges and "
        "cash are the only exposures that behave differently."
    ),
}


@dataclass
class RegimeThresholds:
    """Entry thresholds. Exit thresholds are these, softened by `hysteresis`."""

    crisis_vol_ratio: float = 2.0        # realised vol vs its own 1-year median
    high_vol_ratio: float = 1.4
    trend_strength: float = 0.6          # |net move| / sum of absolute moves
    crisis_drawdown: float = -0.12       # 20-day drawdown that forces a crisis call
    crisis_correlation: float = 0.75     # average pairwise correlation
    hysteresis: float = 0.15             # fraction by which exiting is easier
    min_dwell_days: int = 5


def realised_volatility(returns: pd.Series, window: int = 21) -> pd.Series:
    return returns.rolling(window, min_periods=max(5, window // 2)).std() * np.sqrt(TRADING_DAYS)


def trend_strength(returns: pd.Series, window: int = 21) -> pd.Series:
    """Net move divided by total travel — an efficiency ratio in [0, 1].

    Kaufman's ratio. Near 1 the market went somewhere in a straight line; near
    0 it travelled the same distance and ended where it started, which is what
    "choppy" means precisely.
    """
    net = returns.rolling(window, min_periods=max(5, window // 2)).sum().abs()
    travel = returns.abs().rolling(window, min_periods=max(5, window // 2)).sum()
    return (net / travel.replace(0, np.nan)).fillna(0.0)


def rolling_drawdown(prices: pd.Series, window: int = 20) -> pd.Series:
    peak = prices.rolling(window, min_periods=2).max()
    return (prices - peak) / peak.replace(0, np.nan)


def average_correlation(returns: pd.DataFrame, window: int = 42) -> pd.Series:
    """Mean off-diagonal pairwise correlation, rolling.

    The single best crisis indicator available from price data alone: it rises
    toward 1 exactly when the diversification a portfolio was relying on stops
    working.
    """
    if returns.shape[1] < 2:
        return pd.Series(dtype="float64")

    values: List[float] = []
    index: List[Any] = []
    for end in range(window, len(returns) + 1):
        chunk = returns.iloc[end - window : end]
        matrix = chunk.corr().to_numpy()
        upper = matrix[np.triu_indices_from(matrix, k=1)]
        upper = upper[~np.isnan(upper)]
        if len(upper):
            values.append(float(upper.mean()))
            index.append(returns.index[end - 1])
    return pd.Series(values, index=index)


def classify(
    benchmark_prices: pd.Series,
    holdings_returns: Optional[pd.DataFrame] = None,
    thresholds: Optional[RegimeThresholds] = None,
) -> Dict[str, Any]:
    """Classify each day, applying hysteresis and dwell time to the sequence."""
    thresholds = thresholds or RegimeThresholds()
    prices = benchmark_prices.dropna()
    if len(prices) < 60:
        return {
            "available": False,
            "reason": f"Only {len(prices)} price points; at least 60 are needed.",
        }

    returns = prices.pct_change().dropna()
    volatility = realised_volatility(returns)
    baseline = volatility.rolling(TRADING_DAYS, min_periods=60).median()
    vol_ratio = (volatility / baseline.replace(0, np.nan)).fillna(1.0)

    efficiency = trend_strength(returns)
    drawdown = rolling_drawdown(prices)
    direction = returns.rolling(21, min_periods=10).sum()

    correlation = (
        average_correlation(holdings_returns.dropna(how="any"))
        if holdings_returns is not None and holdings_returns.shape[1] >= 2
        else pd.Series(dtype="float64")
    )

    states: List[str] = []
    current = "choppy"
    dwell = 0

    for timestamp in returns.index:
        ratio = float(vol_ratio.get(timestamp, 1.0))
        efficiency_now = float(efficiency.get(timestamp, 0.0))
        drawdown_now = float(drawdown.get(timestamp, 0.0) or 0.0)
        direction_now = float(direction.get(timestamp, 0.0) or 0.0)
        correlation_now = float(correlation.get(timestamp, np.nan)) if len(correlation) else np.nan

        # Softened thresholds while already in a regime, so a marginal reading
        # holds rather than flipping.
        softening = 1.0 - thresholds.hysteresis

        crisis = (
            ratio >= thresholds.crisis_vol_ratio * (softening if current == "crisis" else 1.0)
            and drawdown_now <= thresholds.crisis_drawdown
        ) or (
            correlation_now == correlation_now
            and correlation_now >= thresholds.crisis_correlation
            and ratio >= thresholds.high_vol_ratio
        )

        if crisis:
            # A crash overrides the dwell timer: waiting five days to
            # acknowledge a crisis is the one failure mode worth avoiding.
            proposed = "crisis"
        elif efficiency_now >= thresholds.trend_strength * (
            softening if current in {"trending_up", "trending_down"} else 1.0
        ):
            proposed = "trending_up" if direction_now >= 0 else "trending_down"
        else:
            proposed = "choppy"

        if proposed != current:
            if dwell < thresholds.min_dwell_days and proposed != "crisis":
                proposed = current
            else:
                dwell = 0
        dwell += 1
        current = proposed
        states.append(current)

    series = pd.Series(states, index=returns.index)
    transitions = [
        {
            "date": series.index[i].isoformat() if hasattr(series.index[i], "isoformat")
            else str(series.index[i]),
            "from": series.iloc[i - 1],
            "to": series.iloc[i],
        }
        for i in range(1, len(series))
        if series.iloc[i] != series.iloc[i - 1]
    ]

    latest = series.iloc[-1]
    days_in_regime = 1
    for i in range(len(series) - 2, -1, -1):
        if series.iloc[i] != latest:
            break
        days_in_regime += 1

    return {
        "available": True,
        "current_regime": latest,
        "current_regime_label": REGIME_LABELS[latest],
        "days_in_regime": days_in_regime,
        "guidance": REGIME_GUIDANCE[latest],
        "metrics": {
            "volatility_ratio": round(float(vol_ratio.iloc[-1]), 2),
            "annualised_volatility_pct": round(float(volatility.iloc[-1]) * 100.0, 2),
            "trend_efficiency": round(float(efficiency.iloc[-1]), 3),
            "drawdown_20d_pct": round(float(drawdown.iloc[-1] or 0.0) * 100.0, 2),
            "average_correlation": (
                round(float(correlation.iloc[-1]), 3) if len(correlation) else None
            ),
        },
        "distribution": {
            regime: round(float((series == regime).mean()) * 100.0, 1) for regime in REGIMES
        },
        "transitions": transitions[-20:],
        "transition_count": len(transitions),
        "history": [
            {
                "date": timestamp.isoformat() if hasattr(timestamp, "isoformat") else str(timestamp),
                "regime": state,
            }
            for timestamp, state in list(series.items())[-250:]
        ],
        "note": (
            "Regimes are descriptive, not predictive. They say what the market "
            "has been doing, which is useful for choosing a strategy family and "
            "for reading a risk number in context — not for forecasting."
        ),
    }
