"""Ranked buy and sell calls — the recommender's front page.

Every layer beneath this one produces scores; this is where they become a list
someone can act on. It composes and does not compute: `screener.run_screen`
generates candidates, `technicals` + `fundamentals` + `scoring` grade them, and
`quant.tax` prices the exit. No metric is re-derived here and no threshold is
reinvented — the bands are `scoring.ACTION_BANDS`, the same ones the screener
and the portfolio view already use, so a buy candidate and a sell candidate are
the same number on the same scale.

The two lists answer two different questions:

* **Buy** — "what, that I do not already own, scores well?" The universe scan
  in the BUY and STRONG_BUY bands, minus anything already held.
* **Sell** — "what that I hold has deteriorated?" That can only be answered
  against holdings, so every held name is scored on the same model, including
  the ones outside the scanned index. With no portfolio the list falls back to
  universe names in the REDUCE and EXIT bands, flagged `basis: "universe"`:
  avoid, or exit if held — not a personalised call.

A sell carries its tax line, which is what makes this more than a filtered
screener. An exit is a taxable event in India, and a REDUCE on a position
eleven months old is a different recommendation from the same REDUCE at
thirteen months.

Nothing here places an order. The output is a ranked, evidenced opinion.
"""

import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from app import scoring
from app import symbols as symbol_master
from app.fundamentals import get_fundamentals, score_fundamentals
from app.quant.rebalance import calculate_holding_period_days
from app.quant.tax import LTCG_ALERT_WINDOW_DAYS, estimate_tax
from app.schemas import PortfolioRequest
from app.screener import (
    FUNDAMENTAL_WORKERS,
    MIN_BARS,
    ScreenFilters,
    fetch_price_frames,
    run_screen,
)
from app.technicals import extract_technicals, score_technicals

logger = logging.getLogger(__name__)

BUY_ACTIONS = ("STRONG_BUY", "BUY")
SELL_ACTIONS = ("REDUCE", "EXIT")

# A position held this long is taxed at the LTCG rate (12.5%) instead of STCG
# (20%), which is why the sell list reports days held next to the call.
LONG_TERM_DAYS = 365

# The scan has to be wider than the list it feeds, or the "buy list" is just
# whatever fitted rather than a ranking.
SCAN_MULTIPLE = 6

# Weights and coverage floor are pinned to `screener.run_screen`. If these ever
# diverge, a held name and a screener hit stop being comparable numbers, which
# is the one property this module exists to guarantee.
TECHNICAL_WEIGHT = 0.5
FUNDAMENTAL_WEIGHT = 0.5
MIN_COVERAGE = 0.3


@dataclass
class SymbolScore:
    """One symbol graded on the standard model, with its raw evidence."""

    symbol: str
    recommendation: scoring.Recommendation
    technicals: Dict[str, Any] = field(default_factory=dict)
    fundamentals: Dict[str, Any] = field(default_factory=dict)
    price: Optional[float] = None


def score_symbols(
    symbols: Sequence[str], with_fundamentals: bool = True
) -> Dict[str, SymbolScore]:
    """Grade named symbols — the holdings the universe scan did not cover.

    Prices come from one batched download for the whole list rather than a call
    per name, the same way the screener does it. Fundamentals are scraped on a
    small pool; a holding is worth the scrape even where a screener candidate
    would not be, because the user already owns it.
    """
    canonical = [symbol_master.canonical(s) or s.upper() for s in symbols]
    unique = list(dict.fromkeys(canonical))
    if not unique:
        return {}

    yf_by_symbol = {
        symbol: symbol_master.to_yfinance(symbol) or f"{symbol}.NS" for symbol in unique
    }
    try:
        frames = fetch_price_frames(list(yf_by_symbol.values()))
    except Exception as exc:
        logger.warning("Price download failed for %d holdings: %s", len(unique), exc)
        frames = {}

    fundamentals: Dict[str, Dict[str, Any]] = {}
    if with_fundamentals:
        with ThreadPoolExecutor(max_workers=FUNDAMENTAL_WORKERS) as pool:
            fundamentals = dict(zip(unique, pool.map(_safe_fundamentals, unique)))

    results: Dict[str, SymbolScore] = {}
    for symbol in unique:
        tech: Dict[str, Any] = {}
        cards: List[Any] = []
        components: Dict[str, scoring.ScoreCard] = {}
        warnings: List[str] = []

        frame = frames.get(yf_by_symbol[symbol])
        if frame is not None and len(frame) >= MIN_BARS:
            tech = extract_technicals(frame)
            technical_card = score_technicals(tech)
            components["technicals"] = technical_card
            cards.append((technical_card, TECHNICAL_WEIGHT))
        else:
            warnings.append("No usable price history; scored on fundamentals alone.")

        fund = fundamentals.get(symbol) or {}
        if fund:
            fundamental_card = score_fundamentals(fund)
            components["fundamentals"] = fundamental_card
            cards.append((fundamental_card, FUNDAMENTAL_WEIGHT))
        elif with_fundamentals:
            warnings.append("Fundamentals could not be scraped; scored on technicals alone.")

        if not cards:
            # Fail visibly. An unscorable holding is reported as unscored, not
            # dropped — silently omitting a position from the user's own sell
            # review is the worse failure.
            results[symbol] = SymbolScore(
                symbol=symbol,
                recommendation=scoring.Recommendation(
                    symbol=symbol,
                    score=None,
                    action=None,
                    conviction=None,
                    coverage=0.0,
                    warnings=["Neither price history nor fundamentals were available."],
                ),
            )
            continue

        overall = scoring.combine("overall", cards, min_coverage=MIN_COVERAGE)
        results[symbol] = SymbolScore(
            symbol=symbol,
            recommendation=scoring.recommend(symbol, overall, components, warnings),
            technicals=tech,
            fundamentals=fund,
            price=tech.get("current_price"),
        )
    return results


def _safe_fundamentals(symbol: str) -> Dict[str, Any]:
    """A scrape failure on one name must not lose the whole batch."""
    try:
        return get_fundamentals(symbol)
    except Exception as exc:
        logger.info("Fundamentals unavailable for %s: %s", symbol, exc)
        return {}


def exit_context(
    quantity: float,
    avg_cost: float,
    price: Optional[float],
    buy_date: Optional[date],
) -> Dict[str, Any]:
    """What selling this position would actually cost after tax.

    The exemption is applied to this position alone rather than shared across
    the sell list, because these are candidates and not a committed plan — the
    shared-allowance arithmetic belongs to `quant.tax.generate_target_rebalance`
    once the user has decided what to sell. The output says so rather than
    leaving the reader to assume otherwise.
    """
    buy_date_str = buy_date.isoformat() if buy_date else None
    days_held = calculate_holding_period_days(buy_date_str)
    long_term = days_held >= LONG_TERM_DAYS

    if price is None:
        return {
            "quantity": quantity,
            "avg_cost": avg_cost,
            "price": None,
            "days_held": days_held if buy_date else None,
            "term": "long" if long_term else "short",
            "note": "No live price, so the exit gain and its tax cannot be computed.",
        }

    invested = quantity * avg_cost
    current = quantity * price
    gain = current - invested
    tax = estimate_tax([{"amount": gain, "long_term": long_term}])

    notes: List[str] = []
    if not buy_date:
        notes.append(
            "No buy date on this holding, so it is assumed long-term and the tax "
            "shown is the lower of the two possibilities."
        )
    days_to_long_term = max(0, LONG_TERM_DAYS - days_held)
    if buy_date and not long_term and gain > 0 and days_to_long_term <= LTCG_ALERT_WINDOW_DAYS:
        notes.append(
            f"{days_to_long_term} days short of long-term treatment: waiting cuts the "
            f"rate on this gain from 20% to 12.5%, worth about "
            f"{gain * 0.075:,.0f} rupees at the current gain."
        )
    notes.append(
        "Tax is priced for this position alone; the 1.25 lakh LTCG exemption is "
        "annual and shared across every sale in the financial year."
    )

    return {
        "quantity": quantity,
        "avg_cost": avg_cost,
        "price": price,
        "invested_inr": round(invested, 2),
        "current_value_inr": round(current, 2),
        "unrealised_pnl_inr": round(gain, 2),
        "unrealised_pnl_pct": round((gain / invested) * 100, 2) if invested else None,
        "days_held": days_held if buy_date else None,
        "term": "long" if long_term else "short",
        "days_to_long_term": days_to_long_term if buy_date and not long_term else 0,
        "estimated_exit_tax_inr": tax["total_tax_inr"],
        "net_proceeds_inr": round(current - tax["total_tax_inr"], 2),
        "tax": tax,
        "note": " ".join(notes),
    }


def _worst_first(entry: Dict[str, Any]) -> Any:
    """Sort key for sell candidates: lowest score first, unscored last."""
    score = entry.get("score")
    return (score is None, score if score is not None else 0.0)


def build(
    portfolio: Optional[PortfolioRequest] = None,
    index: Optional[str] = None,
    universe_limit: int = 300,
    fundamental_limit: int = 60,
    with_fundamentals: bool = True,
    buy_limit: int = 20,
    sell_limit: int = 20,
) -> Dict[str, Any]:
    """The ranked buy list, the ranked sell list, and the evidence behind each."""
    filters = ScreenFilters(index=index or ScreenFilters().index)
    scan = run_screen(
        filters=filters,
        limit=max(buy_limit, sell_limit) * SCAN_MULTIPLE,
        universe_limit=universe_limit,
        with_fundamentals=with_fundamentals,
        fundamental_limit=fundamental_limit,
    )
    scan_rows: List[Dict[str, Any]] = scan.get("results", [])
    by_symbol = {row["symbol"]: row for row in scan_rows}

    holdings = list(portfolio.equity) if portfolio else []
    held_by_symbol = {
        (symbol_master.canonical(h.symbol) or h.symbol.upper()): h for h in holdings
    }

    notes: List[str] = list(scan.get("notes", []))

    # ---- buys: universe candidates the user does not already own ----------
    buys = [
        {**row, "held": False}
        for row in scan_rows
        if row.get("action") in BUY_ACTIONS and row["symbol"] not in held_by_symbol
    ][:buy_limit]

    owned_and_strong = sum(
        1
        for row in scan_rows
        if row.get("action") in BUY_ACTIONS and row["symbol"] in held_by_symbol
    )
    if owned_and_strong:
        notes.append(
            f"{owned_and_strong} name(s) scoring Buy or better are already held, so "
            "they appear under holdings rather than as new buys."
        )

    sells: List[Dict[str, Any]] = []
    keeps: List[Dict[str, Any]] = []

    if held_by_symbol:
        # ---- sells: holdings that have deteriorated -----------------------
        missing = [symbol for symbol in held_by_symbol if symbol not in by_symbol]
        scored_missing = (
            score_symbols(missing, with_fundamentals=with_fundamentals) if missing else {}
        )

        for symbol, holding in held_by_symbol.items():
            row = by_symbol.get(symbol)
            if row is not None:
                entry = dict(row)
            elif symbol in scored_missing:
                scored = scored_missing[symbol]
                entry = scored.recommendation.as_dict()
                entry.update(
                    {
                        "name": holding.name or symbol,
                        "sector": holding.sector,
                        "cap": holding.cap,
                        "price": scored.price,
                        # Held but outside the scanned index, so it was graded
                        # on its own rather than lifted from the scan.
                        "off_index": True,
                    }
                )
            else:
                notes.append(f"{symbol} could not be scored and is not listed either way.")
                continue

            entry["held"] = True
            entry["position"] = exit_context(
                holding.quantity,
                holding.avg_cost,
                entry.get("price") or holding.ltp,
                holding.buy_date,
            )
            (sells if entry.get("action") in SELL_ACTIONS else keeps).append(entry)

        sells.sort(key=_worst_first)
        sells = sells[:sell_limit]
        keeps.sort(key=lambda e: e.get("score") or 0.0, reverse=True)
    else:
        # No portfolio: the weakest end of the universe. That is an "avoid",
        # not a "sell", and is labelled as one.
        sells = [
            {**row, "held": False}
            for row in sorted(
                (r for r in scan_rows if r.get("action") in SELL_ACTIONS), key=_worst_first
            )
        ][:sell_limit]
        notes.append(
            "No holdings were supplied, so the sell list is universe-wide: names to "
            "avoid, or to exit if you hold them. Send a portfolio for position-level "
            "exit calls with tax."
        )

    return {
        "as_of": datetime.now(timezone.utc).isoformat(),
        "index": scan.get("index"),
        "basis": "portfolio" if held_by_symbol else "universe",
        "universe": {
            "scanned": scan.get("scanned", 0),
            "size": scan.get("universe", 0),
            "ranked": scan.get("count", 0),
            "fundamentals_scored": scan.get("fundamentals_scored", 0),
            "cached": scan.get("cached", False),
        },
        "summary": {
            "buy": len(buys),
            "sell": len(sells),
            "holdings_scored": len(sells) + len(keeps),
            "action_bands": {action: threshold for threshold, action in scoring.ACTION_BANDS},
        },
        "buy": buys,
        "sell": sells,
        "holdings_to_keep": keeps,
        "notes": notes,
        "disclaimer": (
            "Diagnostic scores over public data, not investment advice. Every call "
            "shows the evidence behind it, and no order is ever placed."
        ),
    }
