"""LLM portfolio narrative — a narrator over computed numbers, never an analyst.

This is the single most dangerous module in the codebase, because it is the
only one that produces prose a user will read as advice. Everything else
either computes a number or refuses to. So the constraints are structural, not
prompt-level pleading:

1. **The model receives only computed metrics.** It gets a JSON digest built
   by `build_digest` from output the deterministic engines already produced.
   It has no tools, no network, and no way to look anything up — so a metric
   it did not receive is a metric it cannot cite.

2. **It is told, in the system prompt, that inventing a number is the one
   unrecoverable error**, and that the correct response to a missing input is
   to say the input is missing.

3. **Its output is verified after generation.** `find_unsupported_numbers`
   extracts every number in the prose and checks it against the digest. Any
   figure that does not appear there is surfaced to the caller in
   `unsupported_figures`, and the route reports it. A narrator that quietly
   invented a Sharpe ratio should be visible, not trusted.

4. **It never issues a recommendation the scorers did not produce.** Buy/sell/
   hold calls come from `scoring.py`. The narrative explains them.

The rest is craft: `claude-opus-5` with adaptive thinking because the reasoning
is genuinely multi-step, and streaming because a long report at high effort
runs past the default HTTP timeout.
"""

import json
import logging
import re
from datetime import date
from typing import Any, Dict, List, Optional, Sequence, Set

from app.ai.client import (
    AIUnavailable,
    REPORT_MODEL,
    get_client,
    is_configured,
    refused,
    text_of,
)

logger = logging.getLogger(__name__)

MAX_REPORT_TOKENS = 8000

NARRATOR_SYSTEM = """You write the monthly portfolio memo for stockportfolio.in, \
an Indian multi-asset portfolio diagnostics tool.

You are a NARRATOR over numbers that have already been computed. You are not an \
analyst, an adviser, or a forecaster.

Absolute rules:
1. Every figure you state must appear in the JSON you were given. Do not \
compute new ratios, do not annualise anything, do not estimate. If a number \
you want is not in the JSON, say it is not available and move on. Inventing a \
plausible-looking figure is the one error you cannot recover from, because the \
reader has no way to tell it apart from a real one.
2. Do not issue buy, sell or hold calls beyond the `action` values already \
present in the data. You may explain why the engine produced a call. You may \
not disagree with it or add your own.
3. Do not forecast prices, returns or market direction. The Monte Carlo \
percentiles in the data are a distribution under stated assumptions, not a \
prediction — describe them that way.
4. When the data shows low coverage, missing prices or unavailable \
fundamentals, say so plainly. A confident memo over half-missing inputs is \
worse than an honest short one.
5. Write for someone who understands markets but is not a quant. Explain what \
a metric means for their money, not what its formula is.

Tone: direct and unhedged about what the numbers say, explicitly uncertain \
about what they do not. No filler, no "it is important to note", no \
motivational framing. Concrete rupee amounts and percentages over adjectives.

Structure the memo with these markdown sections, in order:
## Where the portfolio stands
## What is working
## What is at risk
## What the engine recommends
## What we could not measure

End with one line: "Diagnostics, not investment advice."
"""


def build_digest(
    analysis: Dict[str, Any],
    recommendations: Optional[Sequence[Dict[str, Any]]] = None,
    news: Optional[Sequence[Dict[str, Any]]] = None,
    equity_curve: Optional[Sequence[Dict[str, Any]]] = None,
    period_label: Optional[str] = None,
) -> Dict[str, Any]:
    """Reduce a full analysis payload to what the narrator should see.

    Trimmed rather than passed whole for two reasons. The full payload carries
    a 61-point Monte Carlo trajectory and every signal behind every score,
    which is tens of thousands of tokens of material the memo will never
    mention. And a smaller digest is a smaller surface for the model to
    misread — every field here is one it is expected to use.
    """
    valuation = analysis.get("valuation") or {}
    totals = valuation.get("totals") or {}
    danger = analysis.get("danger") or {}
    growth = analysis.get("growth") or {}
    monte_carlo = (growth.get("monte_carlo") or {}).get("summary") or {}

    holdings = valuation.get("holdings") or []
    ranked = sorted(
        (h for h in holdings if h.get("pnl_pct") is not None),
        key=lambda h: h["pnl_pct"],
        reverse=True,
    )

    def slim(row: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "key": row.get("key"),
            "name": row.get("name"),
            "kind": row.get("kind"),
            "weight_pct": row.get("weight_pct"),
            "pnl": row.get("pnl"),
            "pnl_pct": row.get("pnl_pct"),
            "sector": row.get("sector"),
            "cap": row.get("cap"),
        }

    digest: Dict[str, Any] = {
        "as_of": date.today().isoformat(),
        "period": period_label or "since inception",
        "totals": {
            "invested_inr": totals.get("invested"),
            "current_value_inr": totals.get("current_value"),
            "cash_inr": totals.get("cash"),
            "pnl_inr": totals.get("pnl"),
            "pnl_pct": totals.get("pnl_pct"),
            "holdings": totals.get("holdings"),
            "priced": totals.get("priced"),
            "unpriced": totals.get("unpriced"),
        },
        "allocation": {
            "asset_class": (valuation.get("allocation") or {}).get("asset_class"),
            "top_sectors": ((valuation.get("allocation") or {}).get("sector") or [])[:6],
            "cap_mix": (valuation.get("allocation") or {}).get("cap"),
        },
        "top_contributors": [slim(row) for row in ranked[:5]],
        "worst_detractors": [slim(row) for row in reversed(ranked[-5:])] if ranked else [],
        "danger": {
            "score": danger.get("danger_score"),
            "level": danger.get("danger_level"),
            "flags": danger.get("flags"),
            "metrics": danger.get("metrics"),
            "worst_stress_scenario": (
                min(
                    danger.get("stress_tests") or [],
                    key=lambda s: s.get("projected_drawdown_pct", 0),
                    default=None,
                )
            ),
        },
        "growth": {
            "score": growth.get("growth_score"),
            "level": growth.get("growth_level"),
            "pillars": growth.get("pillars"),
            "monte_carlo_summary": monte_carlo,
        },
        "data_quality": {
            "warnings": (valuation.get("warnings") or [])[:15],
            "unpriced_holdings": totals.get("unpriced"),
        },
    }

    if recommendations:
        digest["recommendations"] = [
            {
                "symbol": rec.get("symbol"),
                "action": rec.get("action"),
                "score": rec.get("score"),
                "conviction": rec.get("conviction"),
                "coverage": rec.get("coverage"),
                "reasons": (rec.get("reasons") or [])[:3],
            }
            for rec in list(recommendations)[:15]
        ]

    if news:
        digest["news_catalysts"] = [
            {
                "symbol": item.get("symbol"),
                "title": item.get("title"),
                "tag": item.get("tag"),
                "impact": item.get("impact"),
            }
            for item in list(news)[:15]
        ]

    if equity_curve:
        points = list(equity_curve)
        digest["equity_curve"] = {
            "points": len(points),
            "first": points[0],
            "last": points[-1],
            "note": "Recorded nightly snapshots, not a back-projection.",
        }

    return digest


# Matches integers, decimals, and comma-grouped Indian/Western numerals.
_NUMBER = re.compile(r"-?\d[\d,]*\.?\d*")


def _numbers_in(value: Any, found: Set[str]) -> None:
    """Collect every number appearing anywhere in a nested structure, as text."""
    if isinstance(value, bool) or value is None:
        return
    if isinstance(value, (int, float)):
        found.add(_canonical_number(value))
        return
    if isinstance(value, str):
        for match in _NUMBER.findall(value):
            found.add(_canonical_number(match))
        return
    if isinstance(value, dict):
        for item in value.values():
            _numbers_in(item, found)
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            _numbers_in(item, found)


def _canonical_number(value: Any) -> str:
    """Normalise a number to a comparable string, tolerating rounding.

    The model will legitimately write 12.3 for a stored 12.34, or 1,23,456 for
    123456.0. Comparing raw strings would flag both as fabricated, so numbers
    are compared at one decimal place with separators stripped.
    """
    try:
        number = float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return str(value)
    return f"{round(number, 1):.1f}"


def find_unsupported_numbers(prose: str, digest: Dict[str, Any]) -> List[str]:
    """Numbers in the memo that do not appear in the data it was given.

    Deliberately lenient in three ways, because a check that cries wolf gets
    switched off: small integers (years, counts, ordinals like "top 3") are
    ignored, values are matched at one decimal place, and a number that appears
    anywhere in the digest counts as supported even if the model used it in a
    different sentence. What survives all that is worth looking at.
    """
    supported: Set[str] = set()
    _numbers_in(digest, supported)
    # Percentages of a value are a legitimate restatement, and so are the
    # rounded-to-integer forms of everything present.
    supported |= {_canonical_number(round(float(value))) for value in
                  (v for v in supported if _is_float(v))}

    unsupported: List[str] = []
    for token in _NUMBER.findall(prose):
        canonical = _canonical_number(token)
        if canonical in supported:
            continue
        try:
            numeric = float(canonical)
        except ValueError:
            continue
        # Small whole numbers are almost always counts, years or list
        # positions rather than claims about the portfolio.
        if numeric == int(numeric) and abs(numeric) <= 100 and "." not in token:
            continue
        if 1900 <= numeric <= 2100:
            continue
        unsupported.append(token)

    seen: Set[str] = set()
    return [n for n in unsupported if not (n in seen or seen.add(n))]


def _is_float(value: str) -> bool:
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


def write_report(
    analysis: Dict[str, Any],
    recommendations: Optional[Sequence[Dict[str, Any]]] = None,
    news: Optional[Sequence[Dict[str, Any]]] = None,
    equity_curve: Optional[Sequence[Dict[str, Any]]] = None,
    period_label: Optional[str] = None,
    effort: str = "high",
) -> Dict[str, Any]:
    """Generate the monthly memo, verified against the data it was given."""
    if not is_configured():
        return {
            "available": False,
            "reason": (
                "ANTHROPIC_API_KEY is not set, so the narrative layer is off. "
                "Every score, metric and recommendation on this page was "
                "computed deterministically and is unaffected."
            ),
        }

    digest = build_digest(analysis, recommendations, news, equity_curve, period_label)

    try:
        client = get_client()
    except AIUnavailable as exc:
        return {"available": False, "reason": str(exc)}

    prompt = (
        "Write this month's portfolio memo from the data below. Use only "
        "figures that appear in it.\n\n"
        f"```json\n{json.dumps(digest, indent=2, default=str)}\n```"
    )

    try:
        # Streaming because a high-effort report can run past the default
        # request timeout, and `get_final_message` gives the assembled result
        # without hand-rolling event handling.
        with client.messages.stream(
            model=REPORT_MODEL,
            max_tokens=MAX_REPORT_TOKENS,
            system=NARRATOR_SYSTEM,
            # Adaptive thinking: deciding which of forty metrics belong in a
            # five-section memo, and which contradict each other, is genuinely
            # multi-step reasoning.
            thinking={"type": "adaptive"},
            output_config={"effort": effort},
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            response = stream.get_final_message()
    except Exception as exc:
        logger.exception("Narrative generation failed")
        return {"available": False, "reason": f"Report generation failed: {exc}"}

    declined = refused(response)
    if declined:
        return {"available": False, "reason": f"The model declined: {declined}"}

    prose = text_of(response)
    if not prose:
        return {"available": False, "reason": "The model returned no text."}

    unsupported = find_unsupported_numbers(prose, digest)
    if unsupported:
        logger.warning(
            "Narrative contained %d figures absent from the digest: %s",
            len(unsupported), ", ".join(unsupported[:10]),
        )

    usage = getattr(response, "usage", None)
    return {
        "available": True,
        "report_markdown": prose,
        "model": REPORT_MODEL,
        "effort": effort,
        "period": digest["period"],
        "as_of": digest["as_of"],
        "unsupported_figures": unsupported,
        "verification": (
            "Every figure in this memo was checked against the computed data it "
            "was given. Nothing failed that check."
            if not unsupported
            else f"{len(unsupported)} figure(s) in this memo do not appear in the "
                 "computed data and may have been invented. Treat them as unverified: "
                 + ", ".join(unsupported[:10])
        ),
        "usage": {
            "input_tokens": getattr(usage, "input_tokens", None),
            "output_tokens": getattr(usage, "output_tokens", None),
        } if usage else None,
        "disclaimer": (
            "Written by an LLM as a narrator over deterministically computed "
            "metrics. It does not produce its own recommendations, and it is "
            "not investment advice."
        ),
    }


def explain_holding(
    symbol: str,
    recommendation: Dict[str, Any],
    technicals: Optional[Dict[str, Any]] = None,
    fundamentals: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """A short plain-English gloss on one holding's computed call.

    Uses the cheap model: this is a two-paragraph restatement of numbers
    already in hand, called once per holding, so per-call price dominates.
    """
    if not is_configured():
        return {"available": False, "reason": "ANTHROPIC_API_KEY is not set."}

    from app.ai.client import CLASSIFIER_MODEL

    digest = {
        "symbol": symbol,
        "recommendation": recommendation,
        "technicals": technicals or {},
        "fundamentals": {
            key: (fundamentals or {}).get(key)
            for key in (
                "pe_ratio", "roce_pct", "roe_pct", "debt_to_equity",
                "pledged_pct", "sales_growth_pct", "pat_growth_pct",
                "piotroski_f_score", "available", "reason",
            )
        },
    }

    try:
        client = get_client()
        response = client.messages.create(
            model=CLASSIFIER_MODEL,
            max_tokens=700,
            system=(
                "Explain one stock's computed scorecard in two short paragraphs "
                "for an investor who is not a quant. Use only the figures given. "
                "Do not add a recommendation of your own, do not forecast, and "
                "say plainly when data is missing rather than glossing over it."
            ),
            messages=[
                {
                    "role": "user",
                    "content": f"```json\n{json.dumps(digest, indent=2, default=str)}\n```",
                }
            ],
        )
    except AIUnavailable as exc:
        return {"available": False, "reason": str(exc)}
    except Exception as exc:
        logger.warning("Holding explanation failed for %s: %s", symbol, exc)
        return {"available": False, "reason": str(exc)}

    declined = refused(response)
    if declined:
        return {"available": False, "reason": f"The model declined: {declined}"}

    prose = text_of(response)
    return {
        "available": True,
        "symbol": symbol,
        "explanation": prose,
        "unsupported_figures": find_unsupported_numbers(prose, digest),
        "model": CLASSIFIER_MODEL,
    }
