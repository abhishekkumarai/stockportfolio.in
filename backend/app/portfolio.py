"""Portfolio valuation.

Phase 1 scope: price every holding, compute P&L, and summarise allocation.
Risk, correlation, attribution and scoring arrive in Phase 4 and build on the
`ValuedPortfolio` this produces.

Pricing has two sources, deliberately ranked:

  * **Fyers** — real-time, and the same numbers the user sees in their broker
    app, which is what makes the totals reconcilable. Needs a token.
  * **yfinance** — delayed by ~15 minutes and occasionally stale on thin
    counters, but needs no auth. This is what lets someone enter holdings by
    hand and get a working portfolio without connecting a broker at all.

Every priced row records which source it came from. A number whose provenance
is invisible is a number the user cannot check, and this is a tool people make
money decisions with. Where neither source has a price the row is returned
unpriced rather than falling back to cost — showing invested value as if it
were current value would silently report 0% return on a position that may have
halved.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from app import symbols as symbol_master
from app.fyers_client import FyersClient, FyersError
from app.mfapi_client import MFApiError, SchemeNotFoundError, client as mf_client
from app.mfapi_client import parse_nav_date
from app.schemas import EquityHolding, FundHolding, PortfolioRequest
from app.yf_frames import close_series

logger = logging.getLogger(__name__)


@dataclass
class PricedRow:
    """One valued holding, flattened for the UI."""

    kind: str  # "equity" | "fund"
    key: str  # symbol or scheme code
    name: str
    quantity: float
    avg_cost: float
    price: Optional[float]
    price_source: Optional[str]
    invested: float
    current_value: Optional[float]
    pnl: Optional[float]
    pnl_pct: Optional[float]
    weight_pct: Optional[float] = None
    sector: Optional[str] = None
    cap: Optional[str] = None
    category: Optional[str] = None
    buy_date: Optional[str] = None
    warnings: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind,
            "key": self.key,
            "name": self.name,
            "quantity": round(self.quantity, 4),
            "avg_cost": round(self.avg_cost, 4),
            "price": round(self.price, 4) if self.price is not None else None,
            "price_source": self.price_source,
            "invested": round(self.invested, 2),
            "current_value": round(self.current_value, 2) if self.current_value is not None else None,
            "pnl": round(self.pnl, 2) if self.pnl is not None else None,
            "pnl_pct": round(self.pnl_pct, 2) if self.pnl_pct is not None else None,
            "weight_pct": round(self.weight_pct, 2) if self.weight_pct is not None else None,
            "sector": self.sector,
            "cap": self.cap,
            "category": self.category,
            "buy_date": self.buy_date,
            "warnings": self.warnings,
        }


def fetch_equity_prices(
    holdings: List[EquityHolding], client: Optional[FyersClient]
) -> Tuple[Dict[str, float], Dict[str, str]]:
    """Best available price per symbol, plus where each came from.

    Tries Fyers for everything first, then fills the gaps from yfinance. Both
    failing is a normal outcome (no token and no network), not an error.
    """
    prices: Dict[str, float] = {}
    sources: Dict[str, str] = {}

    # A holding that arrived from a live /holdings call already carries an ltp.
    for holding in holdings:
        if holding.ltp:
            prices[holding.symbol] = holding.ltp
            sources[holding.symbol] = "fyers"

    wanted = [h for h in holdings if h.symbol not in prices and h.fyers_symbol]

    if client and client.access_token and wanted:
        try:
            # quotes() chunks at the 50-symbol cap internally.
            payload = client.quotes([h.fyers_symbol for h in wanted])
            by_fyers = {h.fyers_symbol: h.symbol for h in wanted}
            for row in payload.get("d") or []:
                symbol = by_fyers.get(row.get("n"))
                price = (row.get("v") or {}).get("lp")
                if symbol and price:
                    prices[symbol] = float(price)
                    sources[symbol] = "fyers"
        except FyersError as exc:
            # Not fatal: yfinance below can still price these.
            logger.warning("Fyers quotes failed, falling back to yfinance: %s", exc)

    missing = [h for h in holdings if h.symbol not in prices]
    if missing:
        _fill_from_yfinance(missing, prices, sources)

    return prices, sources


def _fill_from_yfinance(
    holdings: List[EquityHolding], prices: Dict[str, float], sources: Dict[str, str]
) -> None:
    """Delayed-price fallback. Imported lazily — yfinance is slow to import."""
    try:
        import yfinance as yf
    except ImportError:
        logger.warning("yfinance unavailable; %d holdings unpriced", len(holdings))
        return

    tickers = {h.symbol: symbol_master.to_yfinance(h.symbol) for h in holdings}
    tickers = {k: v for k, v in tickers.items() if v}
    if not tickers:
        return

    try:
        data = yf.download(
            list(tickers.values()),
            period="5d",
            interval="1d",
            progress=False,
            auto_adjust=False,
            group_by="ticker",
        )
    except Exception as exc:
        logger.warning("yfinance download failed: %s", exc)
        return

    for symbol, ticker in tickers.items():
        close = close_series(data, ticker)
        if close is not None:
            prices[symbol] = float(close.iloc[-1])
            sources[symbol] = "yfinance"


def value_equity(
    holdings: List[EquityHolding], client: Optional[FyersClient]
) -> List[PricedRow]:
    prices, sources = fetch_equity_prices(holdings, client)
    rows: List[PricedRow] = []

    for holding in holdings:
        price = prices.get(holding.symbol)
        holding.ltp = price
        warnings: List[str] = []
        if price is None:
            warnings.append("No live price available; value not computed.")
        if not holding.known:
            warnings.append("Symbol not in the NSE master; sector and cap unknown.")
        if holding.buy_date is None:
            warnings.append("No buy date, so holding-period return cannot be computed.")

        rows.append(
            PricedRow(
                kind="equity",
                key=holding.symbol,
                name=holding.name or holding.symbol,
                quantity=holding.quantity,
                avg_cost=holding.avg_cost,
                price=price,
                price_source=sources.get(holding.symbol),
                invested=holding.invested,
                current_value=holding.current_value,
                pnl=holding.unrealised_pnl,
                pnl_pct=holding.unrealised_pnl_pct,
                sector=holding.sector,
                cap=holding.cap,
                buy_date=holding.buy_date.isoformat() if holding.buy_date else None,
                warnings=warnings,
            )
        )
    return rows


def value_funds(holdings: List[FundHolding]) -> List[PricedRow]:
    rows: List[PricedRow] = []

    for holding in holdings:
        warnings: List[str] = []
        try:
            payload = mf_client.get_latest_nav(holding.scheme_code)
            meta = payload.get("meta") or {}
            data = payload.get("data") or []
            holding.scheme_name = meta.get("scheme_name")
            holding.category = meta.get("scheme_category")
            holding.fund_house = meta.get("fund_house")
            if data:
                holding.latest_nav = float(data[0]["nav"])
                holding.latest_nav_date = parse_nav_date(data[0]["date"])
        except SchemeNotFoundError:
            warnings.append(f"Scheme {holding.scheme_code} not found upstream.")
        except (MFApiError, ValueError, KeyError) as exc:
            warnings.append(f"Could not price scheme {holding.scheme_code}: {exc}")

        if holding.latest_nav is None and not warnings:
            warnings.append("No NAV returned for this scheme.")
        if holding.buy_date is None:
            warnings.append("No buy date, so holding-period return cannot be computed.")

        rows.append(
            PricedRow(
                kind="fund",
                key=str(holding.scheme_code),
                name=holding.scheme_name or f"Scheme {holding.scheme_code}",
                quantity=holding.units,
                avg_cost=holding.avg_nav,
                price=holding.latest_nav,
                price_source="mfapi" if holding.latest_nav is not None else None,
                invested=holding.invested,
                current_value=holding.current_value,
                pnl=holding.unrealised_pnl,
                pnl_pct=holding.unrealised_pnl_pct,
                category=holding.category,
                buy_date=holding.buy_date.isoformat() if holding.buy_date else None,
                warnings=warnings,
            )
        )
    return rows


def _group(rows: List[PricedRow], attribute: str, total: float) -> List[Dict[str, Any]]:
    """Sum current value by an attribute, largest slice first."""
    buckets: Dict[str, float] = {}
    for row in rows:
        if row.current_value is None:
            continue
        key = getattr(row, attribute, None) or "Unclassified"
        buckets[key] = buckets.get(key, 0.0) + row.current_value

    return sorted(
        (
            {
                "label": label,
                "value": round(value, 2),
                "weight_pct": round(value / total * 100.0, 2) if total else None,
            }
            for label, value in buckets.items()
        ),
        key=lambda item: item["value"],
        reverse=True,
    )


def value_portfolio(
    request: PortfolioRequest, client: Optional[FyersClient] = None
) -> Dict[str, Any]:
    """Price a portfolio and summarise it. The Phase 1 deliverable."""
    equity_rows = value_equity(request.equity, client)
    fund_rows = value_funds(request.funds)
    rows = equity_rows + fund_rows

    invested = sum(row.invested for row in rows)
    # Cash counts toward the total but has no cost basis, so it is added to
    # current value only — including it in `invested` would understate returns.
    priced = [row for row in rows if row.current_value is not None]
    current = sum(row.current_value for row in priced) + request.cash
    unpriced = [row for row in rows if row.current_value is None]

    for row in priced:
        row.weight_pct = (row.current_value / current * 100.0) if current else None

    pnl = current - invested - request.cash
    equity_value = sum(r.current_value for r in equity_rows if r.current_value is not None)
    fund_value = sum(r.current_value for r in fund_rows if r.current_value is not None)

    asset_mix = [
        {"label": "Equity", "value": round(equity_value, 2)},
        {"label": "Mutual funds", "value": round(fund_value, 2)},
        {"label": "Cash", "value": round(request.cash, 2)},
    ]
    for entry in asset_mix:
        entry["weight_pct"] = round(entry["value"] / current * 100.0, 2) if current else None

    return {
        "totals": {
            "invested": round(invested, 2),
            "current_value": round(current, 2),
            "cash": round(request.cash, 2),
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl / invested * 100.0, 2) if invested else None,
            "holdings": len(rows),
            "priced": len(priced),
            "unpriced": len(unpriced),
        },
        "holdings": [row.as_dict() for row in sorted(
            rows, key=lambda r: r.current_value or 0, reverse=True
        )],
        "allocation": {
            "asset_class": [a for a in asset_mix if a["value"] > 0],
            "sector": _group(equity_rows, "sector", current),
            "cap": _group(equity_rows, "cap", current),
            "fund_category": _group(fund_rows, "category", current),
        },
        "warnings": [
            f"{row.key}: {warning}" for row in rows for warning in row.warnings
        ],
    }
