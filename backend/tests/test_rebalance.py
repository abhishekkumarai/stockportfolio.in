"""Unit tests for tax-aware rebalancing."""

from app.quant.rebalance import generate_rebalancing_plan


def test_zero_tax_inflow_rebalancing():
    holdings = [
        {"key": "RELIANCE", "name": "Reliance", "kind": "equity", "current_value": 70000.0, "price": 2500.0},
        {"key": "TCS", "name": "TCS", "kind": "equity", "current_value": 30000.0, "price": 3500.0},
    ]
    # Total = 100,000. Target per holding = 50% = 60,000 with 20k fresh cash
    plan = generate_rebalancing_plan(
        holdings=holdings,
        total_current_value=100000.0,
        cash_inflow=20000.0,
        mode="zero_tax_inflow",
    )
    assert plan["mode"] == "zero_tax_inflow"
    assert len(plan["orders"]) > 0
    # The underweight position (TCS) should receive BUY orders
    tcs_order = next((o for o in plan["orders"] if o["key"] == "TCS"), None)
    assert tcs_order is not None
    assert tcs_order["action"] == "BUY"
    assert plan["tax_summary"]["total_tax_inr"] == 0.0


def test_drift_rebalance_tax_calculation():
    holdings = [
        {
            "key": "RELIANCE",
            "name": "Reliance",
            "kind": "equity",
            "current_value": 80000.0,
            "price": 2500.0,
            "buy_date": "2024-01-01",  # > 365 days -> LTCG
            "pnl": 30000.0,
        },
        {
            "key": "TCS",
            "name": "TCS",
            "kind": "equity",
            "current_value": 20000.0,
            "price": 3500.0,
            "buy_date": "2026-05-01",  # < 365 days -> STCG
            "pnl": 5000.0,
        },
    ]
    plan = generate_rebalancing_plan(
        holdings=holdings,
        total_current_value=100000.0,
        drift_tolerance=0.05,
        mode="drift_rebalance",
    )
    assert plan["mode"] == "drift_rebalance"
    # Reliance is heavily overweight (80% vs 50% target) -> should have TRIM order
    trim_order = next((o for o in plan["orders"] if o["action"] == "TRIM"), None)
    assert trim_order is not None
    assert trim_order["key"] == "RELIANCE"
    assert trim_order["tax_impact_inr"] > 0.0
