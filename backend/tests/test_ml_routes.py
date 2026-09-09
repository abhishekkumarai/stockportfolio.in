"""Unit tests for Quant ML API endpoints."""

from unittest.mock import patch

from starlette.testclient import TestClient

from app.main import app

client = TestClient(app)

MOCK_ML_RESPONSE = {
    "available": True,
    "universe_index": "NIFTY50",
    "stocks_ranked": 50,
    "model_type": "RidgeRanker (L2 Regularized)",
    "model_metrics": {
        "rank_ic_mean": 0.052,
        "rank_ic_std": 0.018,
        "information_ratio": 2.88,
        "folds_evaluated": 4,
        "abstention_recommended": False,
        "status": "ACTIVE_ALPHA",
    },
    "feature_importances": {
        "ret_20d": 0.25,
        "roce": 0.20,
        "debt_to_equity": 0.15,
    },
    "rankings": [
        {
            "symbol": "INFY",
            "name": "Infosys Ltd",
            "sector": "Information Technology",
            "alpha_score": 0.045,
            "decile": 10,
            "rating": "STRONG_BUY",
            "driver_pills": ["+20d Momentum", "+High ROCE Quality"],
            "trade": {
                "entry_price": 1850.0,
                "target_price": 1920.0,
                "stop_loss": 1797.5,
                "target_pct": 3.78,
                "stop_loss_pct": 2.84,
                "risk_reward_ratio": 1.33,
            },
            "tax_note": "Exit < 365d: STCG @ 20% | Exit >= 365d: LTCG @ 12.5%",
        }
    ],
}


def test_get_ml_rankings():
    with patch("app.routes.ml.run_quant_alpha_pipeline", return_value=MOCK_ML_RESPONSE):
        resp = client.get("/api/ml/rankings")
        assert resp.status_code == 200
        data = resp.json()
        assert data["available"] is True
        assert data["model_type"] == "RidgeRanker (L2 Regularized)"
        assert len(data["rankings"]) == 1
        assert data["rankings"][0]["decile"] == 10
        assert data["rankings"][0]["rating"] == "STRONG_BUY"
        assert data["rankings"][0]["trade"]["risk_reward_ratio"] == 1.33


def test_get_ml_metrics():
    with patch("app.routes.ml.run_quant_alpha_pipeline", return_value=MOCK_ML_RESPONSE):
        resp = client.get("/api/ml/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["available"] is True
        assert data["model_metrics"]["status"] == "ACTIVE_ALPHA"
        assert data["model_metrics"]["rank_ic_mean"] == 0.052
        assert "ret_20d" in data["feature_importances"]
