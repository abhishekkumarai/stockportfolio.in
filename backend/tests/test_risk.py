"""Unit tests for portfolio risk, VaR, CVaR, HHI, and stress testing."""

import pandas as pd
from app.quant.risk import (
    calculate_hhi,
    calculate_var_cvar,
    evaluate_portfolio_danger,
    simulate_stress_scenarios,
)


def test_calculate_hhi():
    # 4 equal weights -> (25)^2 * 4 = 2500
    weights = [0.25, 0.25, 0.25, 0.25]
    hhi = calculate_hhi(weights)
    assert hhi == 2500.0

    # 1 concentrated holding -> 10000
    single = [1.0]
    assert calculate_hhi(single) == 10000.0


def test_calculate_var_cvar():
    # 100 daily returns with 0 mean and 0.01 std
    returns = pd.Series([(-0.02 + 0.04 * (i / 100.0)) for i in range(100)])
    p_var, cf_var, cvar = calculate_var_cvar(returns, 0.95)

    assert p_var > 0
    assert cf_var > 0
    assert cvar > 0
    assert cvar >= p_var  # CVaR is expected loss beyond VaR


def test_stress_scenarios():
    scenarios = simulate_stress_scenarios(portfolio_value=1000000.0, beta=1.2, smallcap_weight=0.2)
    assert len(scenarios) == 4
    covid = next(s for s in scenarios if s["scenario_key"] == "covid_2020")
    assert covid["projected_drawdown_pct"] < 0
    assert covid["projected_loss_inr"] > 0


def test_evaluate_portfolio_danger():
    holdings = [
        {"kind": "equity", "symbol": "RELIANCE", "current_value": 400000.0, "cap": "large"},
        {"kind": "equity", "symbol": "TCS", "current_value": 350000.0, "cap": "large"},
        {"kind": "equity", "symbol": "INFY", "current_value": 250000.0, "cap": "large"},
    ]
    danger = evaluate_portfolio_danger(holdings, 1000000.0)

    assert "danger_score" in danger
    assert 0.0 <= danger["danger_score"] <= 100.0
    assert "flags" in danger
    assert len(danger["stress_tests"]) == 4
