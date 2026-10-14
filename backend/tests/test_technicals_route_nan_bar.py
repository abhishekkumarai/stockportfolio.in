import json

import numpy as np
import pandas as pd
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routes import stocks


class _FakeTicker:
    def __init__(self, symbol):
        self.symbol = symbol

    def history(self, period, interval):
        idx = pd.date_range("2025-01-01", periods=260, freq="D")
        rng = np.random.default_rng(7)
        close = 2000 + np.cumsum(rng.normal(2, 20, 260))
        df = pd.DataFrame(
            {"Open": close, "High": close + 8, "Low": close - 8, "Close": close, "Volume": 5000},
            index=idx,
        )
        df.iloc[-1, df.columns.get_indexer(["Open", "High", "Low", "Close"])] = np.nan  # incomplete bar
        return df


def test_technicals_route_survives_incomplete_latest_bar(monkeypatch):
    import yfinance

    monkeypatch.setattr(yfinance, "Ticker", _FakeTicker)
    app = FastAPI()
    app.include_router(stocks.router, prefix="/api")
    response = TestClient(app).get("/api/stocks/TCS/technicals")

    assert response.status_code == 200
    # Strict JSON: a NaN anywhere would have raised before reaching here, but be explicit.
    json.loads(response.text, parse_constant=lambda c: (_ for _ in ()).throw(ValueError(c)))
    assert response.json()["scorecard"]["score"] is not None
