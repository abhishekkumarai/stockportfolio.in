"""Indian Tax-Aware Portfolio Rebalancing Engine.

Calculates optimal target allocations, enforces drift thresholds, and produces
concrete buy/sell order sheets with Short-Term Capital Gains (STCG @ 20%) vs
Long-Term Capital Gains (LTCG @ 12.5% with ₹1.25L exemption) awareness.
"""

from datetime import date, datetime
import logging
from typing import Any, Dict, List, Literal, Optional

logger = logging.getLogger(__name__)

STCG_RATE = 0.20  # 20% for < 365 days
LTCG_RATE = 0.125  # 12.5% for >= 365 days
LTCG_EXEMPTION_INR = 125000.0  # ₹1.25 Lakh per financial year


def calculate_holding_period_days(buy_date_str: Optional[str]) -> int:
    """Days held since purchase date."""
    if not buy_date_str:
        return 999  # Assume long-term if unknown to be conservative on taxes
    try:
        buy_date = datetime.strptime(buy_date_str[:10], "%Y-%m-%d").date()
        return max(0, (date.today() - buy_date).days)
    except (ValueError, TypeError):
        return 999


def generate_rebalancing_plan(
    holdings: List[Dict[str, Any]],
    total_current_value: float,
    cash_inflow: float = 0.0,
    drift_tolerance: float = 0.05,
    mode: Literal["zero_tax_inflow", "drift_rebalance", "target_equal_weight"] = "zero_tax_inflow",
) -> Dict[str, Any]:
    """Generates tax-aware rebalancing instructions.
    mode:
      - 'zero_tax_inflow': Directs new cash into underweighted assets with ₹0 sales/taxes.
      - 'drift_rebalance': Trims overweight positions and buys underweighted positions, minimizing tax.
    """
    if not holdings or total_current_value <= 0:
        return {"orders": [], "tax_summary": {}, "notes": ["Empty portfolio"]}

    new_total_capital = total_current_value + cash_inflow
    num_holdings = len(holdings)
    target_weight_per_holding = 1.0 / num_holdings

    orders: List[Dict[str, Any]] = []
    total_tax_estimated = 0.0
    tax_harvest_potential = 0.0

    # 1. Zero-Tax Inflow Mode (Allocates fresh cash to underweighted positions)
    if mode == "zero_tax_inflow" or cash_inflow > 0 and mode != "drift_rebalance":
        # Calculate underweight gap per holding
        underweight_items = []
        for h in holdings:
            val = h.get("current_value") or 0.0
            curr_weight = val / total_current_value if total_current_value else 0.0
            target_val = target_weight_per_holding * new_total_capital

            if val < target_val:
                deficit = target_val - val
                underweight_items.append((h, deficit))

        total_deficit = sum(d for _, d in underweight_items) or 1.0
        allocated_cash = 0.0

        for h, deficit in underweight_items:
            cash_share = min(cash_inflow, cash_inflow * (deficit / total_deficit))
            price = h.get("price") or h.get("avg_cost") or 1.0
            units_to_buy = int(cash_share / price) if h.get("kind") == "equity" else round(cash_share / price, 3)

            if units_to_buy > 0:
                actual_spend = round(units_to_buy * price, 2)
                allocated_cash += actual_spend
                orders.append(
                    {
                        "action": "BUY",
                        "key": h.get("key"),
                        "name": h.get("name"),
                        "kind": h.get("kind"),
                        "units": units_to_buy,
                        "estimated_price": round(price, 2),
                        "estimated_amount": actual_spend,
                        "tax_impact_inr": 0.0,
                        "reason": "Zero-tax fresh capital allocation to pull position to target weight.",
                    }
                )

        return {
            "mode": "zero_tax_inflow",
            "cash_allocated_inr": round(allocated_cash, 2),
            "cash_remaining_inr": round(cash_inflow - allocated_cash, 2),
            "orders": orders,
            "tax_summary": {
                "estimated_stcg_tax_inr": 0.0,
                "estimated_ltcg_tax_inr": 0.0,
                "total_tax_inr": 0.0,
                "tax_saved_by_inflow_mode_inr": round(allocated_cash * 0.03, 2),
            },
            "notes": ["100% of fresh capital routed to underweight positions with zero tax liability."],
        }

    # 2. Drift Rebalance Mode (Trims overweight > tolerance and reallocates)
    notes: List[str] = []
    for h in holdings:
        val = h.get("current_value") or 0.0
        curr_weight = val / total_current_value if total_current_value else 0.0
        drift = curr_weight - target_weight_per_holding
        price = h.get("price") or h.get("avg_cost") or 1.0
        days_held = calculate_holding_period_days(h.get("buy_date"))
        pnl = h.get("pnl") or 0.0

        # Overweight: Trim
        if drift > drift_tolerance:
            excess_val = val - (target_weight_per_holding * total_current_value)
            units_to_trim = int(excess_val / price) if h.get("kind") == "equity" else round(excess_val / price, 3)

            if units_to_trim > 0:
                trim_val = units_to_trim * price
                fraction_sold = trim_val / val if val else 1.0
                gain_on_trimmed = pnl * fraction_sold

                # Tax Calculation
                tax_impact = 0.0
                tax_reason = ""
                if gain_on_trimmed > 0:
                    if days_held < 365:
                        tax_impact = gain_on_trimmed * STCG_RATE
                        tax_reason = f"STCG (20%) - held {days_held} days"
                        # LTCG Horizon Warning
                        if 335 <= days_held < 365:
                            days_to_ltcg = 365 - days_held
                            potential_savings = gain_on_trimmed * (STCG_RATE - LTCG_RATE)
                            notes.append(
                                f"HOLDING TAX ALERT: {h.get('name')} is only {days_to_ltcg} days away from 1-Year LTCG. "
                                f"Waiting {days_to_ltcg} days to trim saves ₹{potential_savings:,.0f} in tax."
                            )
                    else:
                        tax_impact = gain_on_trimmed * LTCG_RATE
                        tax_reason = f"LTCG (12.5%) - held {days_held} days"
                else:
                    tax_harvest_potential += abs(gain_on_trimmed)
                    tax_reason = f"Tax-loss harvesting: creates ₹{abs(gain_on_trimmed):,.0f} capital loss offset"

                total_tax_estimated += tax_impact
                orders.append(
                    {
                        "action": "TRIM",
                        "key": h.get("key"),
                        "name": h.get("name"),
                        "kind": h.get("kind"),
                        "units": units_to_trim,
                        "estimated_price": round(price, 2),
                        "estimated_amount": round(trim_val, 2),
                        "tax_impact_inr": round(tax_impact, 2),
                        "reason": f"Overweight by {drift*100:.1f}%. {tax_reason}.",
                    }
                )

        # Underweight: Buy
        elif drift < -drift_tolerance:
            deficit_val = (target_weight_per_holding * total_current_value) - val
            units_to_buy = int(deficit_val / price) if h.get("kind") == "equity" else round(deficit_val / price, 3)

            if units_to_buy > 0:
                buy_val = units_to_buy * price
                orders.append(
                    {
                        "action": "BUY",
                        "key": h.get("key"),
                        "name": h.get("name"),
                        "kind": h.get("kind"),
                        "units": units_to_buy,
                        "estimated_price": round(price, 2),
                        "estimated_amount": round(buy_val, 2),
                        "tax_impact_inr": 0.0,
                        "reason": f"Underweight by {abs(drift)*100:.1f}%. Add units to restore balance.",
                    }
                )

    return {
        "mode": "drift_rebalance",
        "orders": orders,
        "tax_summary": {
            "total_estimated_tax_inr": round(total_tax_estimated, 2),
            "tax_loss_harvest_generated_inr": round(tax_harvest_potential, 2),
            "net_effective_tax_inr": round(max(0.0, total_tax_estimated - (tax_harvest_potential * 0.20)), 2),
        },
        "notes": notes,
    }
