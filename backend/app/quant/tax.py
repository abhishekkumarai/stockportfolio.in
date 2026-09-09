"""Indian capital-gains tax, and target-weight rebalancing that respects it.

`rebalance.py` targets equal weight and prices each trim's tax independently.
That is fine as a first pass and wrong in two ways that cost real money:

* **The LTCG exemption is annual, not per trade.** The 1.25 lakh allowance is
  shared across every equity sale in a financial year. Applying it to each
  trade separately can understate the tax on a multi-position rebalance by tens
  of thousands of rupees.
* **Losses offset gains before the rate applies**, and short-term losses are
  worth more against short-term gains (20%) than against long-term ones
  (12.5%). Netting in the right order is not an optimisation; it is what the
  Act actually says.

This module also handles Section 112A grandfathering — for equity bought on or
before 31 January 2018, the cost base steps up to that day's fair market value
where that is higher, so pre-regime gains are not taxed.

Rates as in force for listed equity: STCG 20%, LTCG 12.5% above the 1.25 lakh
annual exemption. Surcharge, cess, prior-year carried-forward losses and
non-equity income are all out of scope and stated as such in the output.
"""

import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from app.quant.rebalance import (
    LTCG_EXEMPTION_INR,
    LTCG_RATE,
    STCG_RATE,
    calculate_holding_period_days,
)

logger = logging.getLogger(__name__)

# Section 112A cut-off. Equity bought on or before this date gets the step-up.
GRANDFATHER_DATE = date(2018, 1, 31)

# Days before the LTCG threshold at which waiting becomes worth flagging.
LTCG_ALERT_WINDOW_DAYS = 45

# How close to 31 March a tax-loss harvesting prompt is useful.
HARVEST_WINDOW_DAYS = 90


def financial_year_bounds(today: Optional[date] = None) -> Tuple[date, date]:
    """Start and end of the Indian financial year containing `today` (Apr-Mar)."""
    today = today or date.today()
    start_year = today.year if today.month >= 4 else today.year - 1
    return date(start_year, 4, 1), date(start_year + 1, 3, 31)


def effective_cost_base(
    avg_cost: float,
    buy_date_str: Optional[str],
    fmv_31jan2018: Optional[float] = None,
) -> Tuple[float, bool]:
    """Cost base after grandfathering, and whether the step-up applied.

    Without `fmv_31jan2018` the step-up cannot be computed and actual cost is
    used, which *overstates* the tax. That is the safe direction to be wrong
    in: a user who is told they owe more than they do investigates, one told
    they owe less does not.
    """
    if not buy_date_str or fmv_31jan2018 is None:
        return avg_cost, False
    try:
        purchased = datetime.strptime(str(buy_date_str)[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return avg_cost, False
    if purchased > GRANDFATHER_DATE:
        return avg_cost, False
    stepped = max(avg_cost, float(fmv_31jan2018))
    return stepped, stepped > avg_cost


def estimate_tax(
    gains: List[Dict[str, Any]], ltcg_used_this_year: float = 0.0
) -> Dict[str, Any]:
    """Total tax over a set of realised gains, sharing one annual exemption.

    `gains` is a list of `{"amount": float, "long_term": bool}`, where a
    negative amount is a loss.
    """
    short_gains = sum(g["amount"] for g in gains if not g["long_term"] and g["amount"] > 0)
    short_losses = sum(-g["amount"] for g in gains if not g["long_term"] and g["amount"] < 0)
    long_gains = sum(g["amount"] for g in gains if g["long_term"] and g["amount"] > 0)
    long_losses = sum(-g["amount"] for g in gains if g["long_term"] and g["amount"] < 0)

    # Short-term losses go against short-term gains first: those are taxed at
    # 20% against 12.5%, so the offset is worth more there.
    net_short = max(0.0, short_gains - short_losses)
    spare_short_loss = max(0.0, short_losses - short_gains)
    net_long = max(0.0, long_gains - long_losses - spare_short_loss)

    exemption_left = max(0.0, LTCG_EXEMPTION_INR - ltcg_used_this_year)
    exempt_long = min(net_long, exemption_left)
    taxable_long = net_long - exempt_long

    stcg_tax = net_short * STCG_RATE
    ltcg_tax = taxable_long * LTCG_RATE

    return {
        "short_term_gains_inr": round(short_gains, 2),
        "short_term_losses_inr": round(short_losses, 2),
        "long_term_gains_inr": round(long_gains, 2),
        "long_term_losses_inr": round(long_losses, 2),
        "net_short_term_taxable_inr": round(net_short, 2),
        "net_long_term_inr": round(net_long, 2),
        "ltcg_exemption_applied_inr": round(exempt_long, 2),
        "ltcg_exemption_remaining_inr": round(max(0.0, exemption_left - exempt_long), 2),
        "taxable_long_term_inr": round(taxable_long, 2),
        "stcg_tax_inr": round(stcg_tax, 2),
        "ltcg_tax_inr": round(ltcg_tax, 2),
        "total_tax_inr": round(stcg_tax + ltcg_tax, 2),
        "carry_forward_loss_inr": round(
            max(0.0, spare_short_loss - long_gains) + max(0.0, long_losses - long_gains), 2
        ),
    }


def generate_target_rebalance(
    holdings: List[Dict[str, Any]],
    target_weights: Dict[str, float],
    total_current_value: float,
    cash_inflow: float = 0.0,
    drift_tolerance: float = 0.03,
    ltcg_used_this_year: float = 0.0,
    allow_selling: bool = True,
    today: Optional[date] = None,
) -> Dict[str, Any]:
    """Turn optimiser target weights into an order sheet priced for tax.

    Set `allow_selling=False` for the zero-tax path: fresh capital goes
    entirely into underweight positions and nothing is sold, so drift closes
    over successive contributions at a tax cost of exactly zero. For anyone
    still adding to a portfolio that is almost always the right mode, and it is
    the largest tax saving this engine can offer.
    """
    today = today or date.today()
    if not holdings or total_current_value <= 0:
        return {"orders": [], "tax_summary": {}, "notes": ["Empty portfolio."]}

    new_total = total_current_value + cash_inflow
    fy_start, fy_end = financial_year_bounds(today)

    orders: List[Dict[str, Any]] = []
    notes: List[str] = []
    gains: List[Dict[str, Any]] = []
    harvest_candidates: List[Dict[str, Any]] = []

    held_keys = {h.get("key") for h in holdings}
    unknown = [key for key in target_weights if key not in held_keys]
    if unknown:
        notes.append(
            f"Target weights name {len(unknown)} instrument(s) not currently held "
            f"({', '.join(str(u) for u in unknown[:5])}). Those are skipped — this "
            "engine rebalances what you own rather than opening new positions."
        )

    # Pass 1: sells, so proceeds are known before buys are sized.
    proceeds = 0.0
    for holding in holdings:
        key = holding.get("key")
        value = holding.get("current_value") or 0.0
        price = holding.get("price") or holding.get("avg_cost") or 0.0
        if price <= 0:
            notes.append(f"{key}: no price available, so it was left untouched.")
            continue

        days_held = calculate_holding_period_days(holding.get("buy_date"))
        long_term = days_held >= 365
        pnl = holding.get("pnl") or 0.0

        if pnl < 0:
            harvest_candidates.append(
                {
                    "key": key,
                    "name": holding.get("name"),
                    "unrealised_loss_inr": round(abs(pnl), 2),
                    "term": "long" if long_term else "short",
                }
            )

        target_value = target_weights.get(key, 0.0) * new_total
        drift = (value - target_value) / new_total if new_total else 0.0

        if not allow_selling or drift <= drift_tolerance:
            continue

        excess = value - target_value
        units = int(excess / price) if holding.get("kind") == "equity" else round(excess / price, 3)
        if units <= 0:
            continue

        trim_value = units * price
        realised = pnl * (trim_value / value) if value else 0.0
        gains.append({"amount": realised, "long_term": long_term})
        proceeds += trim_value

        reason = [f"Overweight by {drift * 100:.1f}% against target."]
        if realised > 0 and not long_term:
            days_to_ltcg = 365 - days_held
            if days_to_ltcg <= LTCG_ALERT_WINDOW_DAYS:
                saving = realised * (STCG_RATE - LTCG_RATE)
                notes.append(
                    f"LTCG TIMING: {holding.get('name') or key} reaches one year in "
                    f"{days_to_ltcg} days. Waiting saves about Rs {saving:,.0f} in tax "
                    f"on this trim - weigh that against {days_to_ltcg} more days of "
                    "price risk on a position you already consider overweight."
                )
                reason.append(f"{days_to_ltcg} days short of LTCG.")
        elif realised < 0:
            reason.append(f"Realises a Rs {abs(realised):,.0f} loss, usable against other gains.")

        orders.append(
            {
                "action": "TRIM",
                "key": key,
                "name": holding.get("name"),
                "kind": holding.get("kind"),
                "units": units,
                "estimated_price": round(price, 2),
                "estimated_amount": round(trim_value, 2),
                "current_weight_pct": round(value / new_total * 100.0, 2),
                "target_weight_pct": round(target_weights.get(key, 0.0) * 100.0, 2),
                "realised_gain_inr": round(realised, 2),
                "holding_period_days": days_held,
                "tax_treatment": "LTCG" if long_term else "STCG",
                "tax_impact_inr": 0.0,  # filled in below, once the annual netting is known
                "reason": " ".join(reason),
            }
        )

    # Pass 2: buys, funded by fresh cash plus whatever the trims raised.
    budget = cash_inflow + proceeds
    deficits: List[Tuple[Dict[str, Any], float, float]] = []
    for holding in holdings:
        key = holding.get("key")
        value = holding.get("current_value") or 0.0
        price = holding.get("price") or holding.get("avg_cost") or 0.0
        if price <= 0:
            continue
        target_value = target_weights.get(key, 0.0) * new_total
        gap = target_value - value
        if gap > 0 and gap / new_total > drift_tolerance:
            deficits.append((holding, gap, price))

    total_deficit = sum(gap for _, gap, _ in deficits)
    allocated = 0.0
    for holding, gap, price in deficits:
        share = budget * (gap / total_deficit) if total_deficit > 0 else 0.0
        spend = min(share, gap)
        units = int(spend / price) if holding.get("kind") == "equity" else round(spend / price, 3)
        if units <= 0:
            continue
        amount = units * price
        allocated += amount
        key = holding.get("key")
        value = holding.get("current_value") or 0.0
        orders.append(
            {
                "action": "BUY",
                "key": key,
                "name": holding.get("name"),
                "kind": holding.get("kind"),
                "units": units,
                "estimated_price": round(price, 2),
                "estimated_amount": round(amount, 2),
                "current_weight_pct": round(value / new_total * 100.0, 2),
                "target_weight_pct": round(target_weights.get(key, 0.0) * 100.0, 2),
                "realised_gain_inr": 0.0,
                "tax_treatment": "NONE",
                "tax_impact_inr": 0.0,
                "reason": f"Underweight by {gap / new_total * 100:.1f}%. Buying incurs no tax.",
            }
        )

    tax = estimate_tax(gains, ltcg_used_this_year)

    # Attribute the netted tax back across the trims in proportion to each
    # one's taxable gain. Per-order tax is not well defined once losses and a
    # shared exemption are in play, so this is an allocation, and the total is
    # the number that is actually correct.
    total_positive = sum(g["amount"] for g in gains if g["amount"] > 0)
    if total_positive > 0 and tax["total_tax_inr"] > 0:
        for order in orders:
            if order["action"] == "TRIM" and order["realised_gain_inr"] > 0:
                share = order["realised_gain_inr"] / total_positive
                order["tax_impact_inr"] = round(tax["total_tax_inr"] * share, 2)

    if not allow_selling:
        notes.insert(
            0,
            "Zero-tax inflow mode: nothing was sold, so this rebalance costs Rs 0 "
            "in tax. Drift closes gradually as fresh capital is directed to the "
            "underweight positions.",
        )
    if tax["total_tax_inr"] > 0:
        notes.append(
            f"Estimated tax on this rebalance: Rs {tax['total_tax_inr']:,.0f} "
            f"(STCG Rs {tax['stcg_tax_inr']:,.0f} + LTCG Rs {tax['ltcg_tax_inr']:,.0f}). "
            f"Rs {tax['ltcg_exemption_remaining_inr']:,.0f} of the 1.25 lakh LTCG "
            f"exemption remains for FY{fy_start.year}-{str(fy_end.year)[2:]}."
        )

    days_to_year_end = (fy_end - today).days
    if harvest_candidates and 0 <= days_to_year_end <= HARVEST_WINDOW_DAYS:
        total_harvest = sum(c["unrealised_loss_inr"] for c in harvest_candidates)
        notes.append(
            f"TAX-LOSS HARVESTING: {days_to_year_end} days to 31 March. "
            f"Rs {total_harvest:,.0f} of unrealised losses across "
            f"{len(harvest_candidates)} holdings could offset realised gains this "
            "financial year. Selling and repurchasing resets the holding-period "
            "clock, which matters for anything near the one-year LTCG threshold."
        )

    return {
        "mode": "zero_tax_inflow" if not allow_selling else "target_weights",
        "financial_year": f"{fy_start.isoformat()} to {fy_end.isoformat()}",
        "orders": sorted(orders, key=lambda o: (o["action"] != "TRIM", -o["estimated_amount"])),
        "cash_inflow_inr": round(cash_inflow, 2),
        "proceeds_from_trims_inr": round(proceeds, 2),
        "cash_deployed_inr": round(allocated, 2),
        "cash_remaining_inr": round(budget - allocated, 2),
        "tax_summary": tax,
        "harvest_candidates": harvest_candidates,
        "notes": notes,
        "disclaimer": (
            "Tax figures are estimates on the rates in force for listed equity "
            "(STCG 20%, LTCG 12.5% above the 1.25 lakh annual exemption). They "
            "ignore surcharge, cess, losses carried forward from prior years and "
            "any non-equity income. Diagnostics, not tax advice."
        ),
    }
