import math

import pytest

from app.scoring import (
    NEUTRAL,
    ScoreCard,
    Signal,
    action_for,
    banded_score,
    blend,
    clamp,
    combine,
    conviction_for,
    is_usable,
    linear_score,
    percentile_score,
    rank,
    recommend,
    zscore_to_score,
)


# ---- guards --------------------------------------------------------------


@pytest.mark.parametrize("bad", [None, float("nan"), float("inf"), float("-inf"), "12", [1]])
def test_is_usable_rejects_non_numbers_and_nan(bad):
    """NaN is the dangerous one: it passes `is not None` and poisons arithmetic."""
    assert is_usable(bad) is False


@pytest.mark.parametrize("good", [0, 1.5, -3, True])
def test_is_usable_accepts_finite_numbers(good):
    assert is_usable(good) is True


def test_clamp_bounds():
    assert clamp(-10) == 0.0
    assert clamp(150) == 100.0
    assert clamp(42) == 42


# ---- normalisation -------------------------------------------------------


def test_linear_score_maps_and_clamps():
    assert linear_score(0, 0, 10) == 0.0
    assert linear_score(5, 0, 10) == 50.0
    assert linear_score(10, 0, 10) == 100.0
    assert linear_score(-5, 0, 10) == 0.0
    assert linear_score(99, 0, 10) == 100.0


def test_linear_score_inverts_for_lower_is_better():
    """Bounds stay in natural order; direction is a flag, not reversed arguments."""
    assert linear_score(0, 0, 10, higher_is_better=False) == 100.0
    assert linear_score(10, 0, 10, higher_is_better=False) == 0.0


def test_linear_score_rejects_bad_input():
    assert linear_score(None, 0, 10) is None
    assert linear_score(float("nan"), 0, 10) is None
    assert linear_score(5, 3, 3) is None  # zero-width band


def test_banded_score_picks_first_matching_band():
    rsi_bands = [(30, 90), (40, 75), (60, 50), (70, 30), (math.inf, 10)]
    assert banded_score(25, rsi_bands) == 90
    assert banded_score(35, rsi_bands) == 75
    assert banded_score(50, rsi_bands) == 50
    assert banded_score(85, rsi_bands) == 10


def test_banded_score_boundary_is_exclusive_upper():
    assert banded_score(30, [(30, 90), (100, 10)]) == 10


def test_banded_score_rejects_bad_input():
    assert banded_score(None, [(30, 90)]) is None
    assert banded_score(float("nan"), [(30, 90)]) is None


def test_percentile_score_ranks_within_population():
    peers = [10, 20, 30, 40, 50]
    assert percentile_score(5, peers) == 0.0
    assert percentile_score(55, peers) == 100.0
    assert percentile_score(30, peers) == 50.0  # midrank for the tie


def test_percentile_score_inverts_for_lower_is_better():
    """A low P/E should score well, so cheap ranks high."""
    peers = [10, 20, 30, 40, 50]
    assert percentile_score(5, peers, higher_is_better=False) == 100.0
    assert percentile_score(55, peers, higher_is_better=False) == 0.0


def test_percentile_score_refuses_a_tiny_peer_group():
    """A percentile from two peers is noise dressed up as a measurement."""
    assert percentile_score(5, [1, 2]) is None


def test_percentile_score_ignores_unusable_peers():
    assert percentile_score(30, [10, 20, None, float("nan"), 40, 50]) == 50.0


def test_zscore_to_score():
    assert zscore_to_score(10, mean=10, std=2) == 50.0
    assert zscore_to_score(14, mean=10, std=2) == 100.0  # +2 sigma
    assert zscore_to_score(6, mean=10, std=2) == 0.0
    assert zscore_to_score(14, mean=10, std=2, higher_is_better=False) == 0.0
    assert zscore_to_score(10, mean=10, std=0) is None


# ---- blending ------------------------------------------------------------


def test_blend_is_a_weighted_mean():
    card = blend("t", [Signal("a", 100, weight=1), Signal("b", 0, weight=3)])
    assert card.score == 25.0
    assert card.coverage == 1.0


def test_blend_renormalises_around_missing_inputs():
    """A missing input must not be scored as a neutral 50 — that invents a fact."""
    card = blend(
        "t",
        [Signal("a", 100, weight=0.5), Signal("b", 80, weight=0.3), Signal.missing("c", "gone", 0.2)],
    )
    assert card.score == pytest.approx((100 * 0.5 + 80 * 0.3) / 0.8)
    assert card.coverage == pytest.approx(0.8)
    assert "missing: c" in card.notes[0]


def test_blend_refuses_to_score_below_min_coverage():
    card = blend(
        "t",
        [Signal("a", 90, weight=0.3), Signal.missing("b", "gone", 0.7)],
        min_coverage=0.5,
    )
    assert card.score is None
    assert card.available is False
    assert card.action is None
    assert "not scored" in card.notes[0]


def test_blend_with_no_usable_signals():
    card = blend("t", [Signal.missing("a", "gone"), Signal.missing("b", "gone")])
    assert card.score is None
    assert card.coverage == 0.0


def test_blend_drops_signals_whose_score_is_nan():
    card = blend("t", [Signal("a", 80, weight=0.5), Signal("b", float("nan"), weight=0.5)])
    assert card.score == 80.0


def test_top_reasons_rank_by_influence_not_raw_score():
    """A heavy mild positive outweighs a trivial extreme."""
    card = blend(
        "t",
        [
            Signal("heavy", 70, weight=0.8, reason="heavy mild"),
            Signal("light", 100, weight=0.05, reason="light extreme"),
        ],
    )
    assert card.top_reasons(1) == ["heavy mild"]


def test_top_reasons_skips_unavailable_and_unreasoned_signals():
    card = blend(
        "t",
        [
            Signal("a", 90, weight=0.5, reason="said something"),
            Signal("b", 10, weight=0.5, reason=""),
        ],
    )
    assert card.top_reasons() == ["said something"]


def test_combine_blends_child_cards():
    tech = blend("technical", [Signal("a", 80, weight=1)])
    fund = blend("fundamental", [Signal("b", 40, weight=1)])
    overall = combine("overall", [(tech, 0.6), (fund, 0.4)])
    assert overall.score == pytest.approx(80 * 0.6 + 40 * 0.4)


def test_combine_survives_an_unscored_child():
    """No fundamentals should not sink a name that is rankable on technicals."""
    tech = blend("technical", [Signal("a", 80, weight=1)])
    fund = blend("fundamental", [Signal.missing("b", "no data")])
    overall = combine("overall", [(tech, 0.6), (fund, 0.4)], min_coverage=0.5)
    assert overall.score == 80.0
    assert overall.coverage < 1.0


def test_combine_compounds_child_coverage():
    """A parent built from half-evidenced children is not fully evidenced."""
    partial = blend("technical", [Signal("a", 80, weight=0.6), Signal.missing("b", "gone", 0.4)])
    other = blend("fundamental", [Signal("c", 60, weight=1)])
    overall = combine("overall", [(partial, 0.5), (other, 0.5)])
    assert overall.coverage < 1.0


def test_combine_reasons_name_their_component():
    tech = blend("technical", [Signal("a", 90, weight=1, reason="above SMA200")])
    fund = blend("fundamental", [Signal("b", 20, weight=1, reason="P/E stretched")])
    overall = combine("overall", [(tech, 0.5), (fund, 0.5)])
    assert any(r.startswith("Technical:") for r in overall.top_reasons())


# ---- verdicts ------------------------------------------------------------


@pytest.mark.parametrize(
    "score,expected",
    [(95, "STRONG_BUY"), (80, "STRONG_BUY"), (79, "BUY"), (65, "BUY"),
     (64, "HOLD"), (45, "HOLD"), (44, "REDUCE"), (30, "REDUCE"), (29, "EXIT"), (0, "EXIT")],
)
def test_action_bands(score, expected):
    assert action_for(score) == expected


def test_action_for_missing_score():
    assert action_for(None) is None
    assert action_for(float("nan")) is None


def test_conviction_accounts_for_coverage():
    """85 on half the evidence is a weaker statement than 85 on all of it."""
    assert conviction_for(85, 1.0) == "high"
    assert conviction_for(85, 0.5) == "medium"
    assert conviction_for(NEUTRAL + 1, 1.0) == "low"
    assert conviction_for(None, 1.0) is None


def test_conviction_is_symmetric_around_neutral():
    assert conviction_for(90, 1.0) == conviction_for(10, 1.0)


# ---- recommendation ------------------------------------------------------


def test_recommend_bundles_score_action_and_evidence():
    tech = blend("technical", [Signal("rsi", 85, value=28, weight=1, reason="RSI 28 oversold")])
    rec = recommend("RELIANCE", tech, {"technical": tech})
    payload = rec.as_dict()
    assert payload["symbol"] == "RELIANCE"
    assert payload["action"] == "STRONG_BUY"
    assert payload["action_label"] == "Strong Buy"
    assert payload["reasons"] == ["RSI 28 oversold"]
    assert payload["components"]["technical"]["signals"][0]["value"] == 28


def test_recommend_on_an_unscored_card():
    card = ScoreCard(name="technical", score=None)
    payload = recommend("XYZ", card).as_dict()
    assert payload["score"] is None
    assert payload["action"] is None
    assert payload["conviction"] is None


def test_rank_orders_best_first_and_keeps_unscored_last():
    """Unscored names are kept: "could not evaluate" is information too."""
    recs = [
        recommend("LOW", blend("t", [Signal("a", 30, weight=1)])),
        recommend("HIGH", blend("t", [Signal("a", 90, weight=1)])),
        recommend("NONE", ScoreCard(name="t", score=None)),
        recommend("MID", blend("t", [Signal("a", 60, weight=1)])),
    ]
    assert [r.symbol for r in rank(recs)] == ["HIGH", "MID", "LOW", "NONE"]


def test_rank_breaks_ties_on_coverage():
    """Between two 70s, prefer the better-evidenced one."""
    full = blend("t", [Signal("a", 70, weight=1)])
    thin = blend("t", [Signal("a", 70, weight=0.6), Signal.missing("b", "gone", 0.4)])
    ordered = rank([recommend("THIN", thin), recommend("FULL", full)])
    assert [r.symbol for r in ordered] == ["FULL", "THIN"]


def test_signal_as_dict_hides_score_when_unavailable():
    payload = Signal.missing("pe", "Screener had no ratio block", 0.3).as_dict()
    assert payload["score"] is None
    assert payload["available"] is False
    assert payload["reason"] == "Screener had no ratio block"
