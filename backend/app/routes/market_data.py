"""Market-data feeds that have no connected data source yet.

Each feed returns an honest, empty payload tagged ``source: "not_connected"``
so the UI can say so plainly. Nothing here fabricates figures: when a real
source (NSE/BSE filings, bhavcopy, an IPO feed, ...) is wired in, replace the
body of ``_feed`` for that kind and keep the response shape.
"""

from typing import Any, Dict

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/market-data", tags=["Market Data"])

# kind -> human description of what the feed will carry once connected.
FEEDS: Dict[str, str] = {
    "timeline": "Company announcements and exchange filings",
    "earnings": "Quarterly results, beat rates and earnings trends",
    "bulk-block": "Bulk and block deals",
    "corporate-actions": "Dividends, splits and bonuses",
    "fii-dii": "FII and DII daily flows",
    "ipo": "Upcoming, open and listed IPOs",
    "etf": "Exchange traded funds",
    "indices": "Benchmark and sector indices",
    "sectors": "Sector and industry landscape",
    "concalls": "Earnings concall commentary",
    "movers": "Gainers, losers and most traded",
}


def _feed(kind: str) -> Dict[str, Any]:
    return {
        "kind": kind,
        "description": FEEDS[kind],
        "items": [],
        "source": "not_connected",
        "reason": f"No data source is connected for {FEEDS[kind].lower()} yet.",
    }


@router.get("")
def list_feeds() -> Dict[str, Any]:
    """Which feeds exist and whether each is connected."""
    return {"feeds": [{"kind": k, "description": d, "source": "not_connected"} for k, d in FEEDS.items()]}


@router.get("/{kind}")
def get_feed(kind: str) -> Dict[str, Any]:
    if kind not in FEEDS:
        raise HTTPException(status_code=404, detail=f"Unknown market-data feed '{kind}'")
    return _feed(kind)
