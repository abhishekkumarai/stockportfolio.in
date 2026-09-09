"""Scoring primitives — the spine of the recommender.

Every analysis module (technicals, fundamentals, funds, portfolio risk) reduces
raw metrics to a 0-100 score, and those scores blend into a ranked buy/sell/hold
call. This module owns that machinery so the rules live in one place instead of
being reinvented per analyser, the way `analysis.py:186-241` currently does
inline with hardcoded thresholds.

Three principles it enforces:

1. **Nothing is scored without its evidence.** A `Signal` carries the raw value,
   the score, and a human-readable reason. A recommendation that cannot show its
   work is not usable, and this is a recommender.

2. **Missing data is not a neutral 50.** Scoring an absent P/E as "average"
   silently invents a fact. Missing inputs are dropped and the surviving weights
   renormalise, with `coverage` reporting how much of the intended evidence was
   actually present. A 90 backed by 40% coverage is not the same as a 90 backed
   by all of it, and callers can see the difference.

3. **Direction is explicit.** Some metrics are good when high (ROE), others when
   low (debt/equity, P/E). `higher_is_better=False` inverts rather than asking
   every caller to remember to pass reversed bounds.
"""

import logging
import math
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

NEUTRAL = 50.0

# Score bands -> action. Deliberately asymmetric: the top band is narrow because
# a strong buy should be rare, and the sell side is wider because acting on a
# deteriorating holding matters more than shaving a marginal winner.
ACTION_BANDS: Sequence[Tuple[float, str]] = (
    (80.0, "STRONG_BUY"),
    (65.0, "BUY"),
    (45.0, "HOLD"),
    (30.0, "REDUCE"),
    (0.0, "EXIT"),
)

ACTION_LABELS = {
    "STRONG_BUY": "Strong Buy",
    "BUY": "Buy",
    "HOLD": "Hold",
    "REDUCE": "Reduce",
    "EXIT": "Exit",
}


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def is_usable(value: Any) -> bool:
    """True if a metric is present and finite.

    NaN is the trap here: pandas hands back NaN for a missing rolling value,
    NaN passes an `is not None` check, and it then poisons every arithmetic
    operation downstream while looking like a number.
    """
    if value is None:
        return False
    if isinstance(value, bool):
        return True
    if isinstance(value, (int, float)):
        return math.isfinite(value)
    return False


@dataclass
class Signal:
    """One scored metric, with the evidence that produced it."""

    key: str
    score: float
    value: Any = None
    weight: float = 1.0
    reason: str = ""
    available: bool = True
    unit: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "score": round(self.score, 1) if self.available else None,
            "value": self.value,
            "unit": self.unit,
            "weight": self.weight,
            "reason": self.reason,
            "available": self.available,
        }

    @classmethod
    def missing(cls, key: str, reason: str, weight: float = 1.0) -> "Signal":
        """An input we wanted but could not get. Excluded from the blend."""
        return cls(key=key, score=NEUTRAL, weight=weight, reason=reason, available=False)


@dataclass
class ScoreCard:
    """A blended score plus every signal behind it."""

    name: str
    score: Optional[float]
    signals: List[Signal] = field(default_factory=list)
    coverage: float = 0.0
    notes: List[str] = field(default_factory=list)

    @property
    def action(self) -> Optional[str]:
        return action_for(self.score) if self.score is not None else None

    @property
    def available(self) -> bool:
        return self.score is not None

    def top_reasons(self, count: int = 3) -> List[str]:
        """The signals that moved the score furthest from neutral, either way.

        This is what a recommendation shows as its justification, so it is
        ranked by influence — weight times distance from neutral — not by raw
        score. A heavily weighted mild positive can matter more than a trivial
        extreme.
        """
        ranked = sorted(
            (s for s in self.signals if s.available and s.reason),
            key=lambda s: abs(s.score - NEUTRAL) * s.weight,
            reverse=True,
        )
        return [s.reason for s in ranked[:count]]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "score": round(self.score, 1) if self.score is not None else None,
            "action": self.action,
            "coverage": round(self.coverage, 3),
            "signals": [s.as_dict() for s in self.signals],
            "reasons": self.top_reasons(),
            "notes": self.notes,
        }


# ---- normalisation -------------------------------------------------------


def linear_score(
    value: Any,
    low: float,
    high: float,
    higher_is_better: bool = True,
) -> Optional[float]:
    """Map a value onto 0-100 between two bounds, clamped outside them.

    `low` and `high` are the *bounds of the metric*, not of the score, so they
    stay in their natural order regardless of direction — pass
    higher_is_better=False for metrics like debt/equity where less is better.
    """
    if not is_usable(value) or high == low:
        return None
    fraction = (float(value) - low) / (high - low)
    score = clamp(fraction * 100.0)
    return score if higher_is_better else 100.0 - score


def banded_score(value: Any, bands: Sequence[Tuple[float, float]]) -> Optional[float]:
    """Score by threshold bands: [(upper_bound_exclusive, score), ...].

    Bands are checked in order and the first whose bound the value falls under
    wins, so they must be listed ascending. Use for metrics with conventional
    cutoffs rather than a smooth gradient — RSI's 30/70, for instance.
    """
    if not is_usable(value):
        return None
    numeric = float(value)
    for bound, score in bands:
        if numeric < bound:
            return clamp(score)
    return clamp(bands[-1][1]) if bands else None


def percentile_score(
    value: Any,
    population: Iterable[float],
    higher_is_better: bool = True,
) -> Optional[float]:
    """Rank a value within its peer group, 0-100.

    This is how fundamentals get graded: a 25x P/E is expensive for a bank and
    cheap for an FMCG name, so absolute thresholds mislead. Comparing within
    sector removes that bias.
    """
    if not is_usable(value):
        return None
    peers = [float(p) for p in population if is_usable(p)]
    if len(peers) < 3:
        # Too small a peer group to rank against; a percentile from two peers
        # is noise dressed up as a measurement.
        return None
    numeric = float(value)
    below = sum(1 for p in peers if p < numeric)
    ties = sum(1 for p in peers if p == numeric)
    # Midrank for ties, so identical values score identically.
    score = (below + 0.5 * ties) / len(peers) * 100.0
    return clamp(score if higher_is_better else 100.0 - score)


def zscore_to_score(value: Any, mean: float, std: float, higher_is_better: bool = True) -> Optional[float]:
    """Standardise then squash to 0-100, with +/-2 sigma reaching the extremes."""
    if not is_usable(value) or not is_usable(std) or std <= 0:
        return None
    z = (float(value) - mean) / std
    score = clamp(50.0 + z * 25.0)
    return score if higher_is_better else 100.0 - score


# ---- blending ------------------------------------------------------------


def blend(
    name: str,
    signals: Sequence[Signal],
    min_coverage: float = 0.5,
    notes: Optional[List[str]] = None,
) -> ScoreCard:
    """Weighted mean over available signals, renormalising for missing ones.

    Returns a ScoreCard with score=None when coverage falls below
    `min_coverage`. Refusing to score is the right answer for a thinly
    evidenced name — it keeps a stock with one working indicator out of a
    ranked list where it would sit beside fully evidenced peers.
    """
    total_weight = sum(s.weight for s in signals) or 1.0
    usable = [s for s in signals if s.available and is_usable(s.score)]
    covered_weight = sum(s.weight for s in usable)
    coverage = covered_weight / total_weight

    card = ScoreCard(name=name, score=None, signals=list(signals), coverage=coverage,
                     notes=list(notes or []))

    if not usable:
        card.notes.append("No usable inputs.")
        return card
    if coverage < min_coverage:
        card.notes.append(
            f"Only {coverage:.0%} of inputs available (needs {min_coverage:.0%}); not scored."
        )
        return card

    card.score = sum(s.score * s.weight for s in usable) / covered_weight
    if coverage < 1.0:
        missing = [s.key for s in signals if not s.available]
        card.notes.append(f"Scored on {coverage:.0%} of inputs; missing: {', '.join(missing)}.")
    return card


def combine(
    name: str,
    cards: Sequence[Tuple[ScoreCard, float]],
    min_coverage: float = 0.5,
) -> ScoreCard:
    """Blend ScoreCards into a parent — technical + fundamental -> overall.

    Unscored children drop out and the rest renormalise, the same way `blend`
    treats missing signals. A stock with no fundamentals is still rankable on
    technicals alone; it just reports lower coverage.
    """
    signals = [
        Signal(
            key=card.name,
            score=card.score if card.score is not None else NEUTRAL,
            value=round(card.score, 1) if card.score is not None else None,
            weight=weight,
            # Prefixed with the component: at parent level "Price above both
            # moving averages" alone loses the fact that it is the technical
            # side talking, which is exactly what the reader needs to weigh it.
            reason=(
                f"{card.name.title()}: {'; '.join(card.top_reasons(2))}"
                if card.available and card.top_reasons(2)
                else ""
            ),
            available=card.available,
        )
        for card, weight in cards
    ]
    combined = blend(name, signals, min_coverage=min_coverage)
    # Child coverage compounds: a parent built from half-evidenced children is
    # not fully evidenced, however many children reported in.
    weighted_child_coverage = sum(
        card.coverage * weight for card, weight in cards
    ) / (sum(weight for _, weight in cards) or 1.0)
    combined.coverage = min(combined.coverage, weighted_child_coverage) if combined.available else combined.coverage
    return combined


# ---- verdicts ------------------------------------------------------------


def action_for(score: Optional[float]) -> Optional[str]:
    if score is None or not is_usable(score):
        return None
    for threshold, action in ACTION_BANDS:
        if score >= threshold:
            return action
    return ACTION_BANDS[-1][1]


def conviction_for(score: Optional[float], coverage: float) -> Optional[str]:
    """How much to trust the call: distance from neutral, tempered by coverage.

    A score of 85 on 50% coverage is a weaker statement than 70 on full
    coverage, and the UI needs to say so rather than presenting both as equal.
    """
    if score is None or not is_usable(score):
        return None
    strength = abs(score - NEUTRAL) / NEUTRAL  # 0 at neutral, 1 at either extreme
    adjusted = strength * clamp(coverage, 0.0, 1.0)
    if adjusted >= 0.5:
        return "high"
    if adjusted >= 0.25:
        return "medium"
    return "low"


@dataclass
class Recommendation:
    """The recommender's output for one instrument."""

    symbol: str
    score: Optional[float]
    action: Optional[str]
    conviction: Optional[str]
    coverage: float
    reasons: List[str] = field(default_factory=list)
    components: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "score": round(self.score, 1) if self.score is not None else None,
            "action": self.action,
            "action_label": ACTION_LABELS.get(self.action or "", None),
            "conviction": self.conviction,
            "coverage": round(self.coverage, 3),
            "reasons": self.reasons,
            "components": self.components,
            "warnings": self.warnings,
        }


def recommend(
    symbol: str,
    overall: ScoreCard,
    components: Optional[Dict[str, ScoreCard]] = None,
    warnings: Optional[List[str]] = None,
) -> Recommendation:
    """Assemble a ScoreCard into an explained recommendation."""
    return Recommendation(
        symbol=symbol,
        score=overall.score,
        action=overall.action,
        conviction=conviction_for(overall.score, overall.coverage),
        coverage=overall.coverage,
        reasons=overall.top_reasons(4),
        components={k: v.as_dict() for k, v in (components or {}).items()},
        warnings=list(warnings or []),
    )


def rank(recommendations: Iterable[Recommendation]) -> List[Recommendation]:
    """Best first. Unscored names sort last rather than being dropped.

    They are kept because "we could not evaluate this" is information the user
    needs — silently omitting a holding from its own portfolio view would be
    worse than showing it unranked.
    """
    scored = [r for r in recommendations if r.score is not None]
    unscored = [r for r in recommendations if r.score is None]
    # Coverage breaks ties: between two 72s, prefer the better-evidenced one.
    scored.sort(key=lambda r: (r.score, r.coverage), reverse=True)
    return scored + unscored
