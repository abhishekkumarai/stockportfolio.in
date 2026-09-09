"""Unit tests for fundamentals and forensic scoring."""

from app.fundamentals import (
    calculate_altman_z_score,
    calculate_piotroski_f_score,
    score_fundamentals,
)


def test_piotroski_f_score():
    healthy_company = {
        "latest_pat_cr": 500.0,
        "roce_pct": 22.0,
        "roe_pct": 20.0,
        "debt_to_equity": 0.2,
        "pledged_pct": 0.0,
        "sales_growth_pct": 18.0,
        "pat_growth_pct": 25.0,
        "peg_ratio": 1.2,
        "pe_ratio": 24.0,
    }
    score = calculate_piotroski_f_score(healthy_company)
    assert score >= 7

    distressed_company = {
        "latest_pat_cr": -50.0,
        "roce_pct": 4.0,
        "roe_pct": 2.0,
        "debt_to_equity": 3.5,
        "pledged_pct": 45.0,
        "sales_growth_pct": -8.0,
        "pat_growth_pct": -20.0,
        "peg_ratio": 4.0,
        "pe_ratio": 95.0,
    }
    distress_score = calculate_piotroski_f_score(distressed_company)
    assert distress_score <= 3


def test_altman_z_score():
    healthy = {"roce_pct": 25.0, "debt_to_equity": 0.1, "pledged_pct": 0.0}
    z, classification = calculate_altman_z_score(healthy)
    assert z >= 2.99
    assert classification == "Safe"

    distressed = {"roce_pct": 2.0, "debt_to_equity": 4.0, "pledged_pct": 50.0}
    z_dist, class_dist = calculate_altman_z_score(distressed)
    assert class_dist == "Distress"


def test_score_fundamentals():
    data = {
        "available": True,
        "symbol": "RELIANCE",
        "pe_ratio": 22.0,
        "peg_ratio": 1.1,
        "roce_pct": 19.5,
        "roe_pct": 17.0,
        "debt_to_equity": 0.35,
        "pledged_pct": 0.0,
    }
    card = score_fundamentals(data)
    assert card.available is True
    assert card.score is not None
    assert card.score > 65.0
    assert card.action in ("BUY", "STRONG_BUY")
