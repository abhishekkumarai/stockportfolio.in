import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routes.market_data import FEEDS, router

app = FastAPI()
app.include_router(router, prefix="/api")
client = TestClient(app)


@pytest.mark.parametrize("kind", sorted(FEEDS))
def test_every_feed_is_honestly_empty(kind):
    body = client.get(f"/api/market-data/{kind}").json()
    assert body["kind"] == kind
    assert body["items"] == []
    assert body["source"] == "not_connected"
    assert body["reason"]


def test_unknown_feed_is_404():
    assert client.get("/api/market-data/nope").status_code == 404


def test_listing_names_every_feed():
    feeds = client.get("/api/market-data").json()["feeds"]
    assert {f["kind"] for f in feeds} == set(FEEDS)
