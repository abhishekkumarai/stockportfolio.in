"""Unit tests for Market Pulse API endpoints."""

from unittest.mock import patch

from starlette.testclient import TestClient

from app.main import app

client = TestClient(app)

MOCK_PULSE = {
    "available": True,
    "universe_index": "NIFTY50",
    "scanned_symbols": 50,
    "breadth": {
        "advances": 35,
        "declines": 15,
        "unchanged": 0,
        "total": 50,
        "breadth_ratio": 2.33,
        "advance_pct": 70.0,
        "sentiment": "BULLISH_EXPANSION",
        "description": "Strong market breadth.",
    },
    "volume_shockers": [
        {
            "symbol": "TATAMOTORS",
            "name": "Tata Motors Ltd",
            "current_price": 980.0,
            "change_pct": 3.4,
            "volume": 12000000,
            "sma20_volume": 4000000,
            "volume_surge_ratio": 3.0,
            "tag": "INSTITUTIONAL_ACCUMULATION",
        }
    ],
    "breakouts": [
        {
            "symbol": "BHARTIARTL",
            "name": "Bharti Airtel Ltd",
            "current_price": 1650.0,
            "high_52w": 1640.0,
            "distance_pct": 0.61,
            "change_pct": 1.2,
            "status": "VCP_BREAKOUT",
            "vcp_contracted": True,
        }
    ],
}


def test_get_market_pulse_overview():
    with patch("app.routes.market_pulse.fetch_live_market_pulse", return_value=MOCK_PULSE):
        resp = client.get("/api/market-pulse")
        assert resp.status_code == 200
        data = resp.json()
        assert data["available"] is True
        assert data["breadth"]["sentiment"] == "BULLISH_EXPANSION"
        assert len(data["volume_shockers"]) == 1
        assert len(data["breakouts"]) == 1


def test_get_market_breadth_route():
    with patch("app.routes.market_pulse.fetch_live_market_pulse", return_value=MOCK_PULSE):
        resp = client.get("/api/market-pulse/breadth?universe=NIFTY50")
        assert resp.status_code == 200
        data = resp.json()
        assert data["available"] is True
        assert data["breadth"]["advances"] == 35


def test_get_volume_shockers_route():
    with patch("app.routes.market_pulse.fetch_live_market_pulse", return_value=MOCK_PULSE):
        resp = client.get("/api/market-pulse/volume-shockers")
        assert resp.status_code == 200
        data = resp.json()
        assert data["available"] is True
        assert len(data["volume_shockers"]) == 1
        assert data["volume_shockers"][0]["symbol"] == "TATAMOTORS"


def test_get_breakouts_route():
    with patch("app.routes.market_pulse.fetch_live_market_pulse", return_value=MOCK_PULSE):
        resp = client.get("/api/market-pulse/breakouts")
        assert resp.status_code == 200
        data = resp.json()
        assert data["available"] is True
        assert len(data["breakouts"]) == 1
        assert data["breakouts"][0]["status"] == "VCP_BREAKOUT"
