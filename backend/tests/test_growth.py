"""Unit tests for Expected Growth and Monte Carlo simulations."""

from app.quant.growth import evaluate_portfolio_growth, run_monte_carlo_simulation


def test_monte_carlo_simulation():
    res = run_monte_carlo_simulation(
        initial_value=500000.0,
        expected_cagr=0.14,
        volatility=0.18,
        years=5,
        num_simulations=1000,
        seed=42,
    )
    assert "trajectory" in res
    assert len(res["trajectory"]) == 61  # 0 to 60 months
    summary = res["summary"]
    assert summary["initial_value"] == 500000.0
    assert summary["year_5_median_inr"] > summary["initial_value"]
    assert 0.0 <= summary["prob_doubling_5y_pct"] <= 100.0


def test_evaluate_portfolio_growth():
    holdings = [
        {"kind": "equity", "current_value": 300000.0},
        {"kind": "fund", "current_value": 200000.0},
    ]
    growth = evaluate_portfolio_growth(holdings, 500000.0)
    assert "growth_score" in growth
    assert 0.0 <= growth["growth_score"] <= 100.0
    assert "monte_carlo" in growth
