"""Option chain analytics, Greeks, and portfolio tail hedging.

Two distinct jobs live here, and the second is the one that matters for this
product:

1. **Reading the chain.** PCR, max pain, OI walls, build-up classification and
   IV skew — the standard derivatives dashboard, computed from Fyers'
   authenticated option-chain endpoint rather than scraped off NSE.

2. **Hedging a portfolio.** Given a book's value and beta, how many Nifty puts
   cap the drawdown at 10%, and what does that insurance cost as a percentage
   of the portfolio per year? That question is what makes an option chain
   useful to someone who does not trade options, and it is the reason this
   module exists in a portfolio tool.

Nothing here places an order. The output is a contract count and a premium
estimate; executing it is the user's business, in their broker.

Black-Scholes conventions used throughout: continuous compounding, `r` as a
decimal (0.065 for 6.5%), `T` in years, `sigma` annualised. Indian index
options are European-style, so Black-Scholes is the right model rather than a
binomial approximation.
"""

import logging
import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# The 10-year G-Sec yield is the conventional Indian risk-free proxy. It moves,
# and the Greeks barely care: a 100bp error moves a one-month ATM delta in the
# third decimal.
DEFAULT_RISK_FREE = 0.065

TRADING_DAYS = 252
CALENDAR_DAYS = 365.0

# Nifty's contract multiplier. Fyers reports lot size per symbol, so this is
# only the fallback when the chain does not carry one.
DEFAULT_NIFTY_LOT = 75


# ---- Black-Scholes -------------------------------------------------------


def _norm_cdf(x: float) -> float:
    """Standard normal CDF via erf — no scipy import for two lines of maths."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def d1_d2(spot: float, strike: float, time_to_expiry: float, volatility: float,
          rate: float = DEFAULT_RISK_FREE) -> Tuple[float, float]:
    if spot <= 0 or strike <= 0 or time_to_expiry <= 0 or volatility <= 0:
        raise ValueError("Black-Scholes needs positive spot, strike, time and volatility.")
    vol_sqrt_t = volatility * math.sqrt(time_to_expiry)
    d1 = (math.log(spot / strike) + (rate + 0.5 * volatility**2) * time_to_expiry) / vol_sqrt_t
    return d1, d1 - vol_sqrt_t


def black_scholes_price(
    spot: float, strike: float, time_to_expiry: float, volatility: float,
    rate: float = DEFAULT_RISK_FREE, option_type: str = "CE",
) -> float:
    """European option price. `option_type` is "CE" or "PE", matching Fyers."""
    if time_to_expiry <= 0:
        # At expiry an option is worth exactly its intrinsic value.
        return max(0.0, spot - strike) if option_type == "CE" else max(0.0, strike - spot)

    d1, d2 = d1_d2(spot, strike, time_to_expiry, volatility, rate)
    discount = math.exp(-rate * time_to_expiry)
    if option_type == "CE":
        return spot * _norm_cdf(d1) - strike * discount * _norm_cdf(d2)
    return strike * discount * _norm_cdf(-d2) - spot * _norm_cdf(-d1)


def greeks(
    spot: float, strike: float, time_to_expiry: float, volatility: float,
    rate: float = DEFAULT_RISK_FREE, option_type: str = "CE",
) -> Dict[str, float]:
    """Delta, gamma, theta, vega, rho.

    Theta is per calendar day and vega per one *percentage point* of implied
    volatility, because those are the units every option screen quotes. The
    raw per-year forms are what the formulas produce and are almost never what
    a reader wants.
    """
    if time_to_expiry <= 0 or volatility <= 0:
        intrinsic_delta = (
            (1.0 if spot > strike else 0.0) if option_type == "CE"
            else (-1.0 if spot < strike else 0.0)
        )
        return {"delta": intrinsic_delta, "gamma": 0.0, "theta": 0.0, "vega": 0.0, "rho": 0.0}

    d1, d2 = d1_d2(spot, strike, time_to_expiry, volatility, rate)
    sqrt_t = math.sqrt(time_to_expiry)
    discount = math.exp(-rate * time_to_expiry)
    pdf_d1 = _norm_pdf(d1)

    gamma = pdf_d1 / (spot * volatility * sqrt_t)
    vega = spot * pdf_d1 * sqrt_t / 100.0

    if option_type == "CE":
        delta = _norm_cdf(d1)
        theta = (
            -spot * pdf_d1 * volatility / (2 * sqrt_t)
            - rate * strike * discount * _norm_cdf(d2)
        ) / CALENDAR_DAYS
        rho = strike * time_to_expiry * discount * _norm_cdf(d2) / 100.0
    else:
        delta = _norm_cdf(d1) - 1.0
        theta = (
            -spot * pdf_d1 * volatility / (2 * sqrt_t)
            + rate * strike * discount * _norm_cdf(-d2)
        ) / CALENDAR_DAYS
        rho = -strike * time_to_expiry * discount * _norm_cdf(-d2) / 100.0

    return {
        "delta": round(delta, 4),
        "gamma": round(gamma, 6),
        "theta": round(theta, 3),
        "vega": round(vega, 3),
        "rho": round(rho, 4),
    }


def implied_volatility(
    market_price: float, spot: float, strike: float, time_to_expiry: float,
    rate: float = DEFAULT_RISK_FREE, option_type: str = "CE",
    tolerance: float = 1e-5, max_iterations: int = 100,
) -> Optional[float]:
    """Back out IV by bisection over 0.1%–500% annualised.

    Bisection rather than Newton-Raphson: vega collapses toward zero for deep
    in- and out-of-the-money strikes, and Newton's step is `price_error / vega`,
    so it diverges spectacularly on exactly the wing strikes an option chain is
    full of. Bisection is slower and cannot fail that way.
    """
    if market_price <= 0 or time_to_expiry <= 0:
        return None

    intrinsic = (
        max(0.0, spot - strike) if option_type == "CE" else max(0.0, strike - spot)
    )
    if market_price < intrinsic - 0.01:
        # Below intrinsic there is no volatility that prices this; the quote is
        # stale or crossed, and inventing an IV would hide that.
        return None

    low, high = 0.001, 5.0
    for _ in range(max_iterations):
        mid = (low + high) / 2.0
        price = black_scholes_price(spot, strike, time_to_expiry, mid, rate, option_type)
        if abs(price - market_price) < tolerance:
            return round(mid, 6)
        if price > market_price:
            high = mid
        else:
            low = mid
    return round((low + high) / 2.0, 6)


# ---- chain analytics -----------------------------------------------------


@dataclass
class ChainRow:
    """One strike/side row, normalised out of Fyers' optionsChain array."""

    strike: float
    option_type: str  # "CE" | "PE"
    symbol: str = ""
    ltp: float = 0.0
    oi: float = 0.0
    prev_oi: float = 0.0
    volume: float = 0.0
    ltp_change: float = 0.0
    bid: float = 0.0
    ask: float = 0.0

    @property
    def oi_change(self) -> float:
        return self.oi - self.prev_oi

    @classmethod
    def from_fyers(cls, row: Dict[str, Any]) -> Optional["ChainRow"]:
        option_type = (row.get("option_type") or "").upper()
        if option_type not in {"CE", "PE"}:
            # The first row of Fyers' chain is the underlying, with an empty
            # option_type. Dropping it here keeps every downstream loop honest.
            return None
        try:
            return cls(
                strike=float(row.get("strike_price") or 0.0),
                option_type=option_type,
                symbol=row.get("symbol") or "",
                ltp=float(row.get("ltp") or 0.0),
                oi=float(row.get("oi") or 0.0),
                prev_oi=float(row.get("prev_oi") or 0.0),
                volume=float(row.get("volume") or 0.0),
                ltp_change=float(row.get("ltpch") or 0.0),
                bid=float(row.get("bid") or 0.0),
                ask=float(row.get("ask") or 0.0),
            )
        except (TypeError, ValueError):
            return None


def parse_chain(payload: Dict[str, Any]) -> Tuple[List[ChainRow], Dict[str, Any]]:
    """Normalise a Fyers option-chain response into rows plus context."""
    data = payload.get("data") or payload
    raw_rows = data.get("optionsChain") or []

    rows = [r for r in (ChainRow.from_fyers(row) for row in raw_rows) if r is not None]

    underlying = next(
        (row for row in raw_rows if not (row.get("option_type") or "").strip()), {}
    )
    context = {
        "underlying_symbol": underlying.get("symbol"),
        "spot": float(underlying.get("ltp") or 0.0) or None,
        "expiries": data.get("expiryData") or [],
        "call_oi_total": data.get("callOi"),
        "put_oi_total": data.get("putOi"),
        "india_vix": (data.get("indiavixData") or {}).get("ltp"),
    }
    return rows, context


def put_call_ratio(rows: List[ChainRow]) -> Dict[str, Any]:
    """PCR on open interest and on volume.

    Both are reported because they say different things: OI PCR is positioning
    that has accumulated, volume PCR is what happened today. A high OI PCR with
    a low volume PCR is an old put book that is being unwound, which reads as
    the opposite of the same OI PCR with heavy fresh put buying.
    """
    call_oi = sum(r.oi for r in rows if r.option_type == "CE")
    put_oi = sum(r.oi for r in rows if r.option_type == "PE")
    call_volume = sum(r.volume for r in rows if r.option_type == "CE")
    put_volume = sum(r.volume for r in rows if r.option_type == "PE")

    oi_pcr = (put_oi / call_oi) if call_oi else None
    volume_pcr = (put_volume / call_volume) if call_volume else None

    if oi_pcr is None:
        interpretation = "No call open interest; PCR is undefined."
    elif oi_pcr > 1.3:
        interpretation = (
            f"OI PCR {oi_pcr:.2f}: heavy put writing, conventionally read as "
            "support and a bullish tilt."
        )
    elif oi_pcr < 0.7:
        interpretation = (
            f"OI PCR {oi_pcr:.2f}: heavy call writing, conventionally read as "
            "resistance and a bearish tilt."
        )
    else:
        interpretation = f"OI PCR {oi_pcr:.2f}: balanced positioning."

    return {
        "oi_pcr": round(oi_pcr, 3) if oi_pcr is not None else None,
        "volume_pcr": round(volume_pcr, 3) if volume_pcr is not None else None,
        "call_oi": call_oi,
        "put_oi": put_oi,
        "call_volume": call_volume,
        "put_volume": put_volume,
        "interpretation": interpretation,
    }


def max_pain(rows: List[ChainRow]) -> Dict[str, Any]:
    """The strike where total option-writer payout is smallest.

    For each candidate expiry price S, sum what every open contract would pay
    out: calls below S pay (S - K), puts above S pay (K - S), each weighted by
    open interest. The minimum is "max pain" — the price at which buyers, in
    aggregate, lose the most.

    Worth stating plainly: this is a positioning statistic, not a forecast. It
    moves as OI moves and has no predictive claim behind it.
    """
    strikes = sorted({row.strike for row in rows if row.strike > 0})
    if not strikes:
        return {"max_pain_strike": None, "reason": "No strikes in the chain."}

    by_strike: Dict[float, Dict[str, float]] = {
        strike: {"CE": 0.0, "PE": 0.0} for strike in strikes
    }
    for row in rows:
        if row.strike in by_strike:
            by_strike[row.strike][row.option_type] += row.oi

    curve: List[Dict[str, float]] = []
    for candidate in strikes:
        total = 0.0
        for strike, oi in by_strike.items():
            if candidate > strike:
                total += (candidate - strike) * oi["CE"]
            if candidate < strike:
                total += (strike - candidate) * oi["PE"]
        curve.append({"strike": candidate, "total_pain": round(total, 2)})

    best = min(curve, key=lambda point: point["total_pain"])
    return {
        "max_pain_strike": best["strike"],
        "total_pain_at_max": best["total_pain"],
        "pain_curve": curve,
        "note": (
            "Max pain describes current option positioning, not a price "
            "target. It moves whenever open interest does."
        ),
    }


def oi_walls(rows: List[ChainRow], spot: Optional[float], top: int = 3) -> Dict[str, Any]:
    """The heaviest call and put OI strikes — conventional resistance/support.

    Strikes above spot are filtered for calls and below spot for puts, because
    an in-the-money OI cluster is not a wall, it is a legacy position.
    """
    calls = [r for r in rows if r.option_type == "CE" and (spot is None or r.strike >= spot)]
    puts = [r for r in rows if r.option_type == "PE" and (spot is None or r.strike <= spot)]

    calls.sort(key=lambda r: r.oi, reverse=True)
    puts.sort(key=lambda r: r.oi, reverse=True)

    return {
        "resistance": [
            {"strike": r.strike, "oi": r.oi, "oi_change": r.oi_change} for r in calls[:top]
        ],
        "support": [
            {"strike": r.strike, "oi": r.oi, "oi_change": r.oi_change} for r in puts[:top]
        ],
    }


def classify_buildup(oi_change: float, price_change: float) -> str:
    """The four-quadrant OI/price read.

    OI up + price up   -> longs being added
    OI up + price down -> shorts being added
    OI down + price up -> shorts covering
    OI down + price down -> longs unwinding
    """
    if oi_change > 0 and price_change > 0:
        return "long_buildup"
    if oi_change > 0 and price_change < 0:
        return "short_buildup"
    if oi_change < 0 and price_change > 0:
        return "short_covering"
    if oi_change < 0 and price_change < 0:
        return "long_unwinding"
    return "neutral"


BUILDUP_LABELS = {
    "long_buildup": "Long build-up (fresh longs)",
    "short_buildup": "Short build-up (fresh shorts)",
    "short_covering": "Short covering",
    "long_unwinding": "Long unwinding",
    "neutral": "No clear build-up",
}


def buildup_table(rows: List[ChainRow]) -> List[Dict[str, Any]]:
    return [
        {
            "strike": row.strike,
            "option_type": row.option_type,
            "ltp": row.ltp,
            "oi": row.oi,
            "oi_change": round(row.oi_change, 0),
            "price_change": row.ltp_change,
            "buildup": (kind := classify_buildup(row.oi_change, row.ltp_change)),
            "buildup_label": BUILDUP_LABELS[kind],
        }
        for row in sorted(rows, key=lambda r: (r.strike, r.option_type))
    ]


def iv_skew(
    rows: List[ChainRow], spot: Optional[float], days_to_expiry: float,
    rate: float = DEFAULT_RISK_FREE,
) -> Dict[str, Any]:
    """Implied volatility per strike, and the put-minus-call wing skew.

    A steep positive skew — out-of-the-money puts priced at materially higher
    IV than equidistant calls — means downside protection is expensive, which
    is exactly the input the hedging sizer below needs to be honest about cost.
    """
    if not spot or days_to_expiry <= 0:
        return {"available": False, "reason": "Need a spot price and a future expiry."}

    time_to_expiry = days_to_expiry / CALENDAR_DAYS
    points: List[Dict[str, Any]] = []
    for row in rows:
        if row.ltp <= 0:
            continue
        iv = implied_volatility(
            row.ltp, spot, row.strike, time_to_expiry, rate, row.option_type
        )
        if iv is None:
            continue
        points.append(
            {
                "strike": row.strike,
                "option_type": row.option_type,
                "iv_pct": round(iv * 100.0, 2),
                "moneyness": round(row.strike / spot, 4),
            }
        )

    if not points:
        return {"available": False, "reason": "No strike produced a solvable implied volatility."}

    atm = min(points, key=lambda p: abs(p["moneyness"] - 1.0))
    otm_puts = [p for p in points if p["option_type"] == "PE" and p["moneyness"] < 0.95]
    otm_calls = [p for p in points if p["option_type"] == "CE" and p["moneyness"] > 1.05]

    put_wing = sum(p["iv_pct"] for p in otm_puts) / len(otm_puts) if otm_puts else None
    call_wing = sum(p["iv_pct"] for p in otm_calls) / len(otm_calls) if otm_calls else None
    skew = (put_wing - call_wing) if (put_wing is not None and call_wing is not None) else None

    return {
        "available": True,
        "atm_iv_pct": atm["iv_pct"],
        "otm_put_iv_pct": round(put_wing, 2) if put_wing is not None else None,
        "otm_call_iv_pct": round(call_wing, 2) if call_wing is not None else None,
        "skew_pct": round(skew, 2) if skew is not None else None,
        "interpretation": (
            "Downside protection is bid up relative to upside — hedges are expensive."
            if skew is not None and skew > 2
            else "Wings are priced broadly symmetrically."
            if skew is not None
            else "Not enough wing strikes to measure skew."
        ),
        "points": sorted(points, key=lambda p: (p["strike"], p["option_type"])),
    }


def analyse_chain(
    payload: Dict[str, Any], days_to_expiry: float = 7.0,
    rate: float = DEFAULT_RISK_FREE,
) -> Dict[str, Any]:
    """The full derivatives read for one chain."""
    rows, context = parse_chain(payload)
    if not rows:
        return {"available": False, "reason": "Option chain returned no CE/PE rows."}

    spot = context.get("spot")
    return {
        "available": True,
        "context": context,
        "pcr": put_call_ratio(rows),
        "max_pain": max_pain(rows),
        "oi_walls": oi_walls(rows, spot),
        "buildup": buildup_table(rows),
        "iv": iv_skew(rows, spot, days_to_expiry, rate),
        "strike_count": len({r.strike for r in rows}),
    }


# ---- portfolio hedging ---------------------------------------------------


def size_protective_put(
    portfolio_value: float,
    portfolio_beta: float,
    index_spot: float,
    target_max_drawdown: float = 0.10,
    lot_size: int = DEFAULT_NIFTY_LOT,
    days_to_expiry: float = 30.0,
    volatility: float = 0.15,
    rate: float = DEFAULT_RISK_FREE,
    strike_offset: float = 0.0,
) -> Dict[str, Any]:
    """How many index puts cap a portfolio's drawdown, and what that costs.

    The sizing rule is beta-weighted notional: a book with beta 1.3 behaves
    like 1.3x its value in index exposure, so it needs 1.3x the contracts a
    beta-1.0 book would. The strike is placed at the drawdown the user is
    willing to absorb — protecting from -10% means buying the strike 10% below
    spot, so the first 10% is self-insured and the put covers everything below.

    Two honest limits, both reported in the output rather than buried:

    * **Basis risk.** Nifty puts hedge Nifty. A midcap-heavy book can fall
      considerably further than its beta-implied amount in a liquidity event —
      the March 2020 and 2018 scenarios in `quant/risk.py` exist precisely
      because beta understates that.
    * **Contracts are integers.** Rounding up over-hedges slightly; the
      residual is stated so nobody assumes an exact cap.
    """
    if portfolio_value <= 0 or index_spot <= 0:
        return {"available": False, "reason": "Portfolio value and index spot must be positive."}
    if not 0.01 <= target_max_drawdown <= 0.5:
        return {"available": False, "reason": "Target drawdown must be between 1% and 50%."}

    beta = max(0.1, portfolio_beta)
    hedge_notional = portfolio_value * beta
    contract_notional = index_spot * lot_size
    exact_contracts = hedge_notional / contract_notional
    contracts = max(1, math.ceil(exact_contracts))

    offset = strike_offset if strike_offset else target_max_drawdown
    raw_strike = index_spot * (1.0 - offset)
    # Index options trade on a 50-point strike grid.
    strike = round(raw_strike / 50.0) * 50.0

    time_to_expiry = max(days_to_expiry, 1.0) / CALENDAR_DAYS
    premium_per_unit = black_scholes_price(
        index_spot, strike, time_to_expiry, volatility, rate, "PE"
    )
    premium_total = premium_per_unit * lot_size * contracts
    put_greeks = greeks(index_spot, strike, time_to_expiry, volatility, rate, "PE")

    hedged_notional = contracts * contract_notional
    coverage = hedged_notional / hedge_notional if hedge_notional else 0.0
    # Annualising a one-month premium as if it were rolled twelve times is the
    # only number that makes the cost of standing protection legible.
    annual_cost_pct = (premium_total / portfolio_value) * (CALENDAR_DAYS / max(days_to_expiry, 1.0)) * 100.0

    return {
        "available": True,
        "strategy": "protective_put",
        "contracts": contracts,
        "exact_contracts": round(exact_contracts, 2),
        "lot_size": lot_size,
        "strike": strike,
        "index_spot": index_spot,
        "days_to_expiry": days_to_expiry,
        "premium_per_unit": round(premium_per_unit, 2),
        "premium_total_inr": round(premium_total, 2),
        "premium_pct_of_portfolio": round(premium_total / portfolio_value * 100.0, 3),
        "annualised_cost_pct": round(annual_cost_pct, 2),
        "hedge_notional_inr": round(hedge_notional, 2),
        "hedged_notional_inr": round(hedged_notional, 2),
        "coverage_ratio": round(coverage, 3),
        "portfolio_beta": round(beta, 2),
        "greeks": put_greeks,
        "caveats": [
            "Nifty puts hedge Nifty. A mid/smallcap-heavy book can fall further "
            "than its beta implies in a liquidity event — basis risk is not covered.",
            f"Contracts are whole lots, so the hedge covers {coverage*100:.1f}% "
            "of beta-adjusted notional rather than exactly 100%.",
            "The premium is a Black-Scholes estimate at the volatility supplied. "
            "Use the live chain's implied volatility for a tradeable number.",
            "This is a sizing calculation, not an order. Nothing is placed.",
        ],
    }


def size_collar(
    portfolio_value: float,
    portfolio_beta: float,
    index_spot: float,
    target_max_drawdown: float = 0.10,
    upside_cap: float = 0.10,
    lot_size: int = DEFAULT_NIFTY_LOT,
    days_to_expiry: float = 30.0,
    volatility: float = 0.15,
    rate: float = DEFAULT_RISK_FREE,
) -> Dict[str, Any]:
    """A collar: long the protective put, short a call to pay for it.

    The trade is explicit and should be stated as such — the call sold caps
    participation above `upside_cap`. A collar that costs nothing is a collar
    that has sold away the good years, which is a defensible choice only if the
    user is told they made it.
    """
    put_leg = size_protective_put(
        portfolio_value, portfolio_beta, index_spot, target_max_drawdown,
        lot_size, days_to_expiry, volatility, rate,
    )
    if not put_leg.get("available"):
        return put_leg

    contracts = put_leg["contracts"]
    call_strike = round(index_spot * (1.0 + upside_cap) / 50.0) * 50.0
    time_to_expiry = max(days_to_expiry, 1.0) / CALENDAR_DAYS

    call_premium_unit = black_scholes_price(
        index_spot, call_strike, time_to_expiry, volatility, rate, "CE"
    )
    call_premium_total = call_premium_unit * lot_size * contracts
    net_cost = put_leg["premium_total_inr"] - call_premium_total

    return {
        "available": True,
        "strategy": "collar",
        "contracts": contracts,
        "lot_size": lot_size,
        "put_strike": put_leg["strike"],
        "call_strike": call_strike,
        "index_spot": index_spot,
        "days_to_expiry": days_to_expiry,
        "put_premium_inr": put_leg["premium_total_inr"],
        "call_premium_inr": round(call_premium_total, 2),
        "net_cost_inr": round(net_cost, 2),
        "net_cost_pct_of_portfolio": round(net_cost / portfolio_value * 100.0, 3),
        "zero_cost": abs(net_cost) < portfolio_value * 0.0005,
        "put_greeks": put_leg["greeks"],
        "call_greeks": greeks(index_spot, call_strike, time_to_expiry, volatility, rate, "CE"),
        "caveats": put_leg["caveats"] + [
            f"The short call caps index participation above {call_strike:.0f} "
            f"(+{upside_cap*100:.0f}%). In a strong rally the portfolio keeps its "
            "stock-specific alpha but gives up beta above that level.",
            "A short call is an unlimited-loss leg if the long put expires or is "
            "closed separately. Both legs must be managed as one position.",
        ],
    }


def payoff_curve(
    legs: List[Dict[str, Any]], spot: float, points: int = 61, width: float = 0.25,
) -> Dict[str, Any]:
    """Expiry payoff for a multi-leg position, for plotting.

    Each leg is `{"option_type": "CE"|"PE"|"FUT", "strike": float,
    "quantity": int (negative to sell), "premium": float, "lot_size": int}`.
    Payoff is at expiry — intrinsic value only, no time value — because that is
    the curve people mean when they say "payoff diagram".
    """
    if spot <= 0 or not legs:
        return {"available": False, "reason": "Need a positive spot and at least one leg."}

    low, high = spot * (1 - width), spot * (1 + width)
    step = (high - low) / max(1, points - 1)

    curve: List[Dict[str, float]] = []
    for index in range(points):
        price = low + step * index
        total = 0.0
        for leg in legs:
            quantity = float(leg.get("quantity", 0))
            lot = float(leg.get("lot_size", 1))
            premium = float(leg.get("premium", 0.0))
            strike = float(leg.get("strike", 0.0))
            kind = (leg.get("option_type") or "CE").upper()

            if kind == "CE":
                intrinsic = max(0.0, price - strike)
            elif kind == "PE":
                intrinsic = max(0.0, strike - price)
            else:  # a futures or cash leg
                intrinsic = price - strike

            total += quantity * lot * (intrinsic - premium)
        curve.append({"price": round(price, 2), "payoff": round(total, 2)})

    payoffs = [point["payoff"] for point in curve]
    # Breakevens are sign changes between adjacent sampled points; with a
    # coarse grid they are approximate, and labelled as such.
    breakevens = [
        round(curve[i]["price"], 2)
        for i in range(1, len(curve))
        if (payoffs[i - 1] < 0 <= payoffs[i]) or (payoffs[i - 1] > 0 >= payoffs[i])
    ]

    return {
        "available": True,
        "curve": curve,
        "max_profit": round(max(payoffs), 2),
        "max_loss": round(min(payoffs), 2),
        "approximate_breakevens": breakevens,
        "note": "Payoff at expiry (intrinsic value only). Breakevens are sampled, not solved.",
    }
