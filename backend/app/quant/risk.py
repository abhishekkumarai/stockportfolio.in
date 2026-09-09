"""Quantitative portfolio risk engine.

Computes Value at Risk (VaR), Conditional VaR (CVaR), Stress Scenarios (2020 COVID,
2008 GFC, 2018 Midcap Meltdown), Concentration metrics (HHI), and the composite
Danger Score (0-100).
"""

import logging
import math
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats

from app import scoring
from app.schemas import EquityHolding, FundHolding

logger = logging.getLogger(__name__)

# Standard Crisis Drawdown Fixtures for Stress Testing
CRISIS_SCENARIOS = {
    "covid_2020": {
        "name": "March 2020 COVID Flash Crash",
        "benchmark_drop": -0.38,
        "high_beta_multiplier": 1.35,
        "description": "Rapid systemic liquidity shock and global market sell-off.",
    },
    "gfc_2008": {
        "name": "2008 Global Financial Crisis",
        "benchmark_drop": -0.52,
        "high_beta_multiplier": 1.45,
        "description": "Multi-month structural credit crisis and deep economic recession.",
    },
    "midcap_2018": {
        "name": "2018 Indian Midcap & Smallcap Meltdown",
        "benchmark_drop": -0.28,
        "high_beta_multiplier": 1.60,
        "description": "SEBI re-categorization and NBFC liquidity crunch disproportionately hurting mid/smallcaps.",
    },
    "rate_shock_2022": {
        "name": "2022 Global Rate Hike & Inflation Shock",
        "benchmark_drop": -0.16,
        "high_beta_multiplier": 1.20,
        "description": "Aggressive central bank rate hikes and valuation compression in high-PE tech/growth.",
    },
}


def calculate_hhi(weights: List[float]) -> float:
    """Herfindahl-Hirschman Index for portfolio concentration.
    weights: list of fractions summing to ~1.0.
    Returns HHI between 0 and 10,000.
    """
    if not weights:
        return 0.0
    return float(sum((w * 100.0) ** 2 for w in weights))


def calculate_var_cvar(
    returns: pd.Series, confidence_level: float = 0.95
) -> Tuple[float, float, float]:
    """Calculates Parametric VaR, Cornish-Fisher VaR, and CVaR (Expected Shortfall).
    Returns (parametric_var, cornish_fisher_var, cvar) as positive percentage decimals.
    """
    clean_returns = returns.dropna()
    if len(clean_returns) < 20:
        return 0.05, 0.05, 0.07  # Conservative default for thin history

    mean = clean_returns.mean()
    std = clean_returns.std()
    z = stats.norm.ppf(1 - confidence_level)

    # 1. Parametric Gaussian VaR
    parametric_var = -(mean + z * std)

    # 2. Cornish-Fisher VaR (adjusted for skewness and kurtosis)
    skew = clean_returns.skew() if len(clean_returns) > 5 else 0.0
    kurt = clean_returns.kurtosis() if len(clean_returns) > 5 else 0.0
    if scoring.is_usable(skew) and scoring.is_usable(kurt):
        z_cf = (
            z
            + (z**2 - 1) * skew / 6.0
            + (z**3 - 3 * z) * kurt / 24.0
            - (2 * z**3 - 5 * z) * (skew**2) / 36.0
        )
        cf_var = -(mean + z_cf * std)
    else:
        cf_var = parametric_var

    # 3. Historical Conditional VaR (CVaR) - average of returns below VaR threshold
    hist_var_threshold = np.percentile(clean_returns, (1 - confidence_level) * 100)
    tail_losses = clean_returns[clean_returns <= hist_var_threshold]
    hist_cvar = -tail_losses.mean() if len(tail_losses) > 0 else parametric_var * 1.3
    cvar = max(float(hist_cvar), float(parametric_var))

    return (
        max(0.001, float(parametric_var)),
        max(0.001, float(cf_var)),
        max(0.001, float(cvar)),
    )



def simulate_stress_scenarios(
    portfolio_value: float, beta: float, smallcap_weight: float
) -> List[Dict[str, Any]]:
    """Simulates how the portfolio would behave during major historical crises."""
    scenarios: List[Dict[str, Any]] = []

    for key, item in CRISIS_SCENARIOS.items():
        base_drop = item["benchmark_drop"]
        # Extra beta drag for small/midcaps in liquidity crises
        effective_beta = beta * (1.0 + smallcap_weight * (item["high_beta_multiplier"] - 1.0))
        projected_drop_pct = base_drop * max(0.5, effective_beta)
        projected_loss_inr = portfolio_value * abs(projected_drop_pct)

        scenarios.append(
            {
                "scenario_key": key,
                "name": item["name"],
                "description": item["description"],
                "benchmark_drop_pct": round(base_drop * 100.0, 1),
                "effective_beta": round(effective_beta, 2),
                "projected_drawdown_pct": round(projected_drop_pct * 100.0, 2),
                "projected_loss_inr": round(projected_loss_inr, 2),
                "projected_recovery_value": round(portfolio_value + (portfolio_value * projected_drop_pct), 2),
            }
        )

    return scenarios


def evaluate_portfolio_danger(
    holdings_data: List[Dict[str, Any]],
    total_value: float,
    cash_value: float = 0.0,
    daily_returns: Optional[pd.Series] = None,
) -> Dict[str, Any]:
    """Generates the comprehensive Danger Score (0-100) and risk breakdown.
    A score of 0 is ultra-safe/resilient; 100 is extreme critical danger.
    """
    if total_value <= 0 or not holdings_data:
        return {
            "danger_score": 0.0,
            "danger_level": "Low",
            "resilience_score": 100.0,
            "flags": [],
            "metrics": {},
            "stress_tests": [],
        }

    weights = [(h.get("current_value") or 0.0) / total_value for h in holdings_data if h.get("current_value")]
    sorted_weights = sorted(weights, reverse=True)

    top1_weight = sorted_weights[0] if sorted_weights else 0.0
    top3_weight = sum(sorted_weights[:3]) if len(sorted_weights) >= 3 else sum(sorted_weights)
    hhi = calculate_hhi(weights)

    # Asset and cap breakdown weights
    small_micro_weight = sum(
        (h.get("current_value") or 0.0) / total_value
        for h in holdings_data
        if (h.get("cap") or "").lower() in ("small", "micro")
    )

    # Estimate portfolio beta from holdings or default
    equity_weights = [w for h, w in zip(holdings_data, weights) if h.get("kind") == "equity"]
    portfolio_beta = 1.0 + (small_micro_weight * 0.4)  # Approximate baseline

    # VaR / CVaR estimation
    if daily_returns is not None and len(daily_returns) >= 20:
        param_var, cf_var, cvar = calculate_var_cvar(daily_returns, 0.95)
    else:
        # Calibrated 1-Month 95% parametric defaults
        base_monthly_vol = 0.05 * portfolio_beta
        param_var = base_monthly_vol * 1.65
        cf_var = param_var * 1.1
        cvar = param_var * 1.35

    # Danger Flags Identification
    flags: List[Dict[str, str]] = []

    # 1. Concentration Danger
    if top1_weight > 0.25:
        flags.append({
            "severity": "CRITICAL",
            "category": "Concentration",
            "title": f"Single Holding Risk: {top1_weight*100:.1f}% Allocation",
            "detail": "Your largest position exceeds 25% of your total portfolio, creating a single point of failure.",
        })
    elif top1_weight > 0.20:
        flags.append({
            "severity": "WARNING",
            "category": "Concentration",
            "title": f"Elevated Position Weight: {top1_weight*100:.1f}%",
            "detail": "A single stock accounts for over 20% of your portfolio.",
        })

    if top3_weight > 0.60:
        flags.append({
            "severity": "CRITICAL",
            "category": "Concentration",
            "title": f"Top 3 Holdings Concentration: {top3_weight*100:.1f}%",
            "detail": "Over 60% of your capital is concentrated in just 3 instruments.",
        })

    if hhi > 2500:
        flags.append({
            "severity": "WARNING",
            "category": "Concentration",
            "title": f"High Concentration Index (HHI: {hhi:.0f})",
            "detail": "Portfolio diversification is low according to the Herfindahl-Hirschman Index.",
        })

    # 2. Tail Risk / Volatility Danger
    if cvar > 0.12:
        flags.append({
            "severity": "WARNING",
            "category": "Tail Risk",
            "title": f"Elevated Downside Tail Risk (CVaR: {cvar*100:.1f}%)",
            "detail": "Expected loss during extreme 5% market shock events exceeds 12% in a single month.",
        })

    if portfolio_beta > 1.35:
        flags.append({
            "severity": "WARNING",
            "category": "Beta Exposure",
            "title": f"High Portfolio Beta: {portfolio_beta:.2f}x",
            "detail": "Your portfolio moves significantly faster than the broad market, multiplying drawdown depth.",
        })

    # Calculate Composite Danger Score (0 to 100)
    concentration_penalty = min(40.0, (top1_weight * 100.0) * 0.8 + (top3_weight * 100.0) * 0.3)
    volatility_penalty = min(35.0, (cvar * 100.0) * 2.0 + max(0.0, (portfolio_beta - 1.0) * 25.0))
    cap_penalty = min(25.0, small_micro_weight * 40.0)

    danger_score = round(min(100.0, max(0.0, concentration_penalty + volatility_penalty + cap_penalty)), 1)
    resilience_score = round(100.0 - danger_score, 1)

    if danger_score >= 70.0:
        danger_level = "Critical Danger"
    elif danger_score >= 45.0:
        danger_level = "Elevated Risk"
    elif danger_score >= 25.0:
        danger_level = "Moderate Risk"
    else:
        danger_level = "Safe & Resilient"

    # Stress Test Simulation
    stress_tests = simulate_stress_scenarios(total_value, portfolio_beta, small_micro_weight)

    return {
        "danger_score": danger_score,
        "danger_level": danger_level,
        "resilience_score": resilience_score,
        "flags": flags,
        "metrics": {
            "top1_weight_pct": round(top1_weight * 100.0, 2),
            "top3_weight_pct": round(top3_weight * 100.0, 2),
            "hhi": round(hhi, 1),
            "portfolio_beta": round(portfolio_beta, 2),
            "monthly_var_95_pct": round(param_var * 100.0, 2),
            "monthly_cvar_95_pct": round(cvar * 100.0, 2),
            "small_micro_weight_pct": round(small_micro_weight * 100.0, 2),
        },
        "stress_tests": stress_tests,
    }
