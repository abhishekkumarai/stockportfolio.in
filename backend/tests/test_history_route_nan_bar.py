import numpy as np
import pandas as pd
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routes import stocks


class _FakeTicker:
    def __init__(self, symbol):
        pass

    def history(self, period, interval):
        idx = pd.date_range("2025-01-01", periods=30, freq="D")
        close = np.linspace(100, 130, 30)
        df = pd.DataFrame({"Open": close, "High": close + 1, "Low": close - 1, "Close": close, "Volume": 10}, index=idx)
        df.iloc[-1, df.columns.get_indexer(["Open", "High", "Low", "Close"])] = np.nan
        return df


def test_history_drops_incomplete_latest_bar(monkeypatch):
    import yfinance

    monkeypatch.setattr(yfinance, "Ticker", _FakeTicker)
    app = FastAPI()
    app.include_router(stocks.router, prefix="/api")
    response = TestClient(app).get("/api/stocks/history", params={"ticker": "TCS", "period": "1y", "interval": "1d"})

    assert response.status_code == 200
    body = response.json()
    assert body["records_count"] == 29  # 30 bars minus the incomplete one
    assert all(r["close"] == r["close"] for r in body["data"])
