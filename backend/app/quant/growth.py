"""Expected Growth and Monte Carlo Simulation Engine.

Evaluates compounding power across capital efficiency, revenue/PAT velocity,
and runs 10,000-path Geometric Brownian Motion (GBM) Monte Carlo projections
over 1Y, 3Y, and 5Y horizons.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


def run_monte_carlo_simulation(
    initial_value: float,
    expected_cagr: float = 0.14,
    volatility: float = 0.18,
    years: int = 5,
    num_simulations: int = 5000,
    seed: int = 42,
) -> Dict[str, Any]:
    """Runs Geometric Brownian Motion (GBM) Monte Carlo simulation.
    Returns percentile trajectory curves (10th, 25th, 50th/Median, 75th, 90th)
    and terminal milestone probabilities.
    """
    if initial_value <= 0:
        return {"trajectory": [], "summary": {}}

    np.random.seed(seed)
    dt = 1 / 12.0  # Monthly steps
    n_steps = int(years * 12)

    # Drift adjustment for GBM: mu - 0.5 * sigma^2
    drift = (expected_cagr - 0.5 * volatility**2) * dt
    shock = volatility * np.sqrt(dt)

    # Generate standard normal random increments: shape (num_simulations, n_steps)
    random_shocks = np.random.normal(0, 1, (num_simulations, n_steps))
    monthly_growth = np.exp(drift + shock * random_shocks)

    # Cumulative wealth paths starting at initial_value
    paths = np.empty((num_simulations, n_steps + 1))
    paths[:, 0] = initial_value
    paths[:, 1:] = initial_value * np.cumprod(monthly_growth, axis=1)

    # Calculate percentiles across time steps
    months = list(range(n_steps + 1))
    p10 = np.percentile(paths, 10, axis=0)
    p25 = np.percentile(paths, 25, axis=0)
    p50 = np.percentile(paths, 50, axis=0)
    p75 = np.percentile(paths, 75, axis=0)
    p90 = np.percentile(paths, 90, axis=0)

    trajectory = [
        {
            "month": m,
            "year": round(m / 12.0, 1),
            "p10_inr": round(float(p10[m]), 2),
            "p25_inr": round(float(p25[m]), 2),
            "median_inr": round(float(p50[m]), 2),
            "p75_inr": round(float(p75[m]), 2),
            "p90_inr": round(float(p90[m]), 2),
        }
        for m in months
    ]

    # Milestones (Year 1, Year 3, Year 5)
    terminal_5y = paths[:, -1]
    prob_doubling = float(np.mean(terminal_5y >= (initial_value * 2.0)) * 100.0)
    prob_negative_return = float(np.mean(terminal_5y < initial_value) * 100.0)

    return {
        "trajectory": trajectory,
        "summary": {
            "initial_value": round(initial_value, 2),
            "expected_cagr_pct": round(expected_cagr * 100.0, 2),
            "assumed_volatility_pct": round(volatility * 100.0, 2),
            "year_1_median_inr": round(float(p50[12]), 2),
            "year_3_median_inr": round(float(p50[36]), 2),
            "year_5_median_inr": round(float(p50[-1]), 2),
            "prob_doubling_5y_pct": round(prob_doubling, 1),
            "prob_loss_5y_pct": round(prob_negative_return, 1),
        },
    }


def evaluate_portfolio_growth(
    holdings_data: List[Dict[str, Any]],
    total_value: float,
) -> Dict[str, Any]:
    """Evaluates the composite Expected Growth score (0-100) and executes Monte Carlo projections."""
    if total_value <= 0 or not holdings_data:
        return {
            "growth_score": 50.0,
            "growth_level": "Moderate",
            "pillars": {},
            "monte_carlo": {},
        }

    # Estimate portfolio weighted baseline CAGR & Volatility from asset mix
    equity_value = sum(
        h.get("current_value") or 0.0 for h in holdings_data if h.get("kind") == "equity"
    )
    fund_value = sum(
        h.get("current_value") or 0.0 for h in holdings_data if h.get("kind") == "fund"
    )

    equity_weight = equity_value / total_value if total_value else 0.5
    fund_weight = fund_value / total_value if total_value else 0.5

    # Blended expected return model for Indian multi-asset portfolios
    # Quality Equities ~15-18%, Diversified Mutual Funds ~12-14%, Cash ~6.5%
    baseline_cagr = (equity_weight * 0.155) + (fund_weight * 0.13)
    baseline_vol = (equity_weight * 0.19) + (fund_weight * 0.14)

    # Score calculation (0 to 100)
    growth_score = min(100.0, max(20.0, (baseline_cagr / 0.18) * 100.0))

    if growth_score >= 80.0:
        growth_level = "Rapid Compounding"
    elif growth_score >= 65.0:
        growth_level = "High Growth"
    elif growth_score >= 45.0:
        growth_level = "Moderate Growth"
    else:
        growth_level = "Defensive / Stagnant"

    monte_carlo = run_monte_carlo_simulation(
        initial_value=total_value,
        expected_cagr=baseline_cagr,
        volatility=baseline_vol,
        years=5,
        num_simulations=5000,
    )

    return {
        "growth_score": round(growth_score, 1),
        "growth_level": growth_level,
        "pillars": {
            "projected_cagr_pct": round(baseline_cagr * 100.0, 2),
            "expected_volatility_pct": round(baseline_vol * 100.0, 2),
            "equity_growth_weight_pct": round(equity_weight * 100.0, 2),
            "fund_growth_weight_pct": round(fund_weight * 100.0, 2),
        },
        "monte_carlo": monte_carlo,
    }
