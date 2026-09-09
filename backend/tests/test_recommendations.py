"""The buy/sell lists, built over a stubbed scan so no network is touched."""

from datetime import date, timedelta

import pytest

from app import recommendations
from app.schemas import EquityHolding, PortfolioRequest


def row(symbol, score, action, price=100.0, name=None):
    """A scan row shaped like `screener.ScreenRow.as_dict()`."""
    return {
        "symbol": symbol,
        "name": name or symbol.title(),
        "sector": "IT",
        "cap": "large",
        "price": price,
        "score": score,
        "action": action,
        "action_label": action.replace("_", " ").title(),
        "conviction": "high",
        "coverage": 0.9,
        "reasons": [f"{symbol} reason"],
        "components": {},
        "warnings": [],
    }


SCAN = {
    "index": "NIFTY500",
    "scanned": 5,
    "universe": 500,
    "count": 5,
    "fundamentals_scored": 5,
    "cached": False,
    "notes": [],
    "results": [
        row("ALPHA", 88.0, "STRONG_BUY"),
        row("BETA", 70.0, "BUY"),
        row("GAMMA", 55.0, "HOLD"),
        row("DELTA", 38.0, "REDUCE"),
        row("EPSILON", 12.0, "EXIT"),
    ],
}


@pytest.fixture(autouse=True)
def stub_scan(monkeypatch):
    monkeypatch.setattr(recommendations, "run_screen", lambda **kwargs: dict(SCAN))
    # Canonicalisation would otherwise need the symbol master.
    monkeypatch.setattr(recommendations.symbol_master, "canonical", lambda s: s.upper())


def test_universe_mode_lists_buys_and_avoids():
    result = recommendations.build()

    assert result["basis"] == "universe"
    assert [r["symbol"] for r in result["buy"]] == ["ALPHA", "BETA"]
    # Worst first: an EXIT is a stronger avoid than a REDUCE.
    assert [r["symbol"] for r in result["sell"]] == ["EPSILON", "DELTA"]
    assert any("universe-wide" in note for note in result["notes"])


def test_holdings_drive_the_sell_list():
    portfolio = PortfolioRequest(
        equity=[
            EquityHolding(symbol="DELTA", quantity=10, avg_cost=80.0),
            EquityHolding(symbol="ALPHA", quantity=5, avg_cost=50.0),
        ]
    )
    result = recommendations.build(portfolio=portfolio)

    assert result["basis"] == "portfolio"
    # DELTA is held and deteriorating; ALPHA is held and strong, so it is a
    # keep rather than a new buy.
    assert [r["symbol"] for r in result["sell"]] == ["DELTA"]
    assert [r["symbol"] for r in result["holdings_to_keep"]] == ["ALPHA"]
    assert [r["symbol"] for r in result["buy"]] == ["BETA"]
    assert any("already held" in note for note in result["notes"])


def test_sell_candidate_carries_its_exit_tax():
    portfolio = PortfolioRequest(
        equity=[EquityHolding(symbol="DELTA", quantity=10, avg_cost=50.0)]
    )
    position = recommendations.build(portfolio=portfolio)["sell"][0]["position"]

    # 10 x (100 - 50) = 500 gain, assumed long-term without a buy date, and
    # under the 1.25L exemption - so no tax, and the note says why.
    assert position["unrealised_pnl_inr"] == 500.0
    assert position["term"] == "long"
    assert position["estimated_exit_tax_inr"] == 0.0
    assert "No buy date" in position["note"]


def test_short_term_position_is_taxed_at_the_higher_rate():
    bought = date.today() - timedelta(days=30)
    context = recommendations.exit_context(
        quantity=100, avg_cost=100.0, price=200.0, buy_date=bought
    )

    assert context["term"] == "short"
    assert context["days_held"] == 30
    # 10,000 gain at STCG 20%.
    assert context["estimated_exit_tax_inr"] == pytest.approx(2000.0)
    assert context["net_proceeds_inr"] == pytest.approx(18000.0)


def test_a_position_days_from_ltcg_says_so():
    bought = date.today() - timedelta(days=340)
    context = recommendations.exit_context(
        quantity=10, avg_cost=100.0, price=200.0, buy_date=bought
    )

    assert context["days_to_long_term"] == 25
    assert "short of long-term treatment" in context["note"]


def test_missing_price_does_not_invent_a_gain():
    context = recommendations.exit_context(
        quantity=10, avg_cost=100.0, price=None, buy_date=None
    )

    assert context["price"] is None
    assert "cannot be computed" in context["note"]
    assert "unrealised_pnl_inr" not in context


def test_holdings_outside_the_scanned_index_are_scored_separately(monkeypatch):
    scored = recommendations.SymbolScore(
        symbol="OMEGA",
        recommendation=recommendations.scoring.Recommendation(
            symbol="OMEGA",
            score=25.0,
            action="EXIT",
            conviction="high",
            coverage=0.8,
            reasons=["Below both moving averages"],
        ),
        price=42.0,
    )
    monkeypatch.setattr(recommendations, "score_symbols", lambda symbols, **kw: {"OMEGA": scored})

    portfolio = PortfolioRequest(
        equity=[EquityHolding(symbol="OMEGA", quantity=3, avg_cost=60.0)]
    )
    result = recommendations.build(portfolio=portfolio)

    sell = result["sell"][0]
    assert sell["symbol"] == "OMEGA"
    assert sell["off_index"] is True
    assert sell["position"]["unrealised_pnl_inr"] == pytest.approx(-54.0)


def test_unscorable_holding_is_reported_not_dropped(monkeypatch):
    monkeypatch.setattr(recommendations, "score_symbols", lambda symbols, **kw: {})

    portfolio = PortfolioRequest(
        equity=[EquityHolding(symbol="ZETA", quantity=1, avg_cost=10.0)]
    )
    result = recommendations.build(portfolio=portfolio)

    assert result["sell"] == []
    assert any("ZETA could not be scored" in note for note in result["notes"])


def test_limits_are_respected():
    result = recommendations.build(buy_limit=1, sell_limit=1)
    assert len(result["buy"]) == 1
    assert len(result["sell"]) == 1
    assert result["summary"]["buy"] == 1
