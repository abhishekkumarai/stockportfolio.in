"""Unit tests for Macro API endpoints."""

from unittest.mock import patch

from starlette.testclient import TestClient

from app.main import app

client = TestClient(app)

MOCK_MACRO_SNAPSHOT = {
    "available": True,
    "regime": {
        "regime_id": "GOLDILOCKS_EXPANSION",
        "title": "Goldilocks Expansion",
        "posture": "OVERWEIGHT_CYCLICALS",
        "vix_value": 13.5,
        "vix_change_5d_pct": -2.5,
        "us10y_yield": 4.15,
        "narrative": "Subdued volatility and stable currency.",
        "favored_sectors": ["NIFTY Bank", "NIFTY Auto"],
        "unfavored_sectors": ["Defensives"],
    },
    "crude": {
        "current_price": 76.5,
        "change_5d_pct": -1.2,
        "change_20d_pct": -3.5,
        "pressure_level": "BENIGN",
        "impact_assessment": "Benign crude environment.",
    },
    "currency": {
        "current_rate": 83.45,
        "change_5d_pct": 0.1,
        "change_20d_pct": 0.2,
        "stance": "STABLE",
        "impact_assessment": "Stable foreign exchange regime.",
    },
    "gold": {"current_price": 2450.0, "change_5d_pct": 0.8},
    "us10y": {"yield_pct": 4.15},
    "vix": {"current": 13.5, "change_5d_pct": -2.5},
    "sector_rotation": [
        {
            "sector_key": "NIFTY_AUTO",
            "name": "NIFTY Auto",
            "current_price": 25000.0,
            "return_1m_pct": 4.5,
            "return_3m_pct": 12.0,
            "relative_1m_pct": 2.5,
            "relative_3m_pct": 6.0,
            "momentum_score": 4.25,
            "status": "LEADERSHIP",
            "rank": 1,
        }
    ],
}


def test_get_macro_overview():
    with patch("app.routes.macro.fetch_macro_snapshot", return_value=MOCK_MACRO_SNAPSHOT):
        resp = client.get("/api/macro")
        assert resp.status_code == 200
        data = resp.json()
        assert data["available"] is True
        assert data["regime"]["regime_id"] == "GOLDILOCKS_EXPANSION"
        assert data["crude"]["pressure_level"] == "BENIGN"
        assert len(data["sector_rotation"]) == 1


def test_get_macro_regime():
    with patch("app.routes.macro.fetch_macro_snapshot", return_value=MOCK_MACRO_SNAPSHOT):
        resp = client.get("/api/macro/regime")
        assert resp.status_code == 200
        data = resp.json()
        assert data["available"] is True
        assert data["regime"]["regime_id"] == "GOLDILOCKS_EXPANSION"
        assert data["crude_pressure"] == "BENIGN"
        assert data["currency_stance"] == "STABLE"


def test_get_sector_rotation():
    with patch("app.routes.macro.fetch_macro_snapshot", return_value=MOCK_MACRO_SNAPSHOT):
        resp = client.get("/api/macro/sectors")
        assert resp.status_code == 200
        data = resp.json()
        assert data["available"] is True
        assert len(data["sector_rotation"]) == 1
        assert data["sector_rotation"][0]["sector_key"] == "NIFTY_AUTO"
