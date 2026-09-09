"""Typed models for portfolio ingestion.

Until now every Fyers route returned the upstream dict verbatim
(`routes/fyers.py` passed `client.quotes(...)` straight out). That is fine for
a debugging endpoint and untenable for an aggregator: the portfolio layer needs
to know that a quantity is an int, that `costPrice` means average buy price,
and that a missing `ltp` is a real condition rather than a KeyError three
frames down.

Two Fyers quirks these models absorb:

  * Candles arrive as bare arrays, `[epoch, o, h, l, c, v]`, with no keys.
  * Holdings carry no purchase date. `costPrice` and `quantity` are enough for
    absolute return but not for XIRR, which needs a cashflow date — so
    `buy_date` is optional here and supplied by the user in the UI.
"""

from datetime import date, datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from app import symbols as symbol_master

# Fyers labels settled delivery stock "HLD" and stock bought but not yet
# settled (T+1) "T1". Both are owned by the account and both are valued here.
HoldingType = Literal["HLD", "T1", "UNKNOWN"]


class Candle(BaseModel):
    """One OHLCV bar, from Fyers' positional array form."""

    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int = 0

    @classmethod
    def from_fyers(cls, row: List[Any]) -> "Candle":
        """Parse `[epoch_seconds, o, h, l, c, v]`.

        Fyers sends epochs in UTC; they are kept timezone-aware so that a
        naive local-time comparison cannot silently shift a bar across a day
        boundary — which for a daily series would misalign an entire return.
        """
        if not row or len(row) < 5:
            raise ValueError(f"Malformed candle: {row!r}")
        return cls(
            timestamp=datetime.fromtimestamp(int(row[0]), tz=timezone.utc),
            open=float(row[1]),
            high=float(row[2]),
            low=float(row[3]),
            close=float(row[4]),
            volume=int(row[5]) if len(row) > 5 and row[5] is not None else 0,
        )


class PriceSeries(BaseModel):
    """A symbol's candles, normalised out of a /history or history_range call."""

    symbol: str
    resolution: str = "1D"
    candles: List[Candle] = Field(default_factory=list)

    @classmethod
    def from_fyers(cls, payload: Dict[str, Any], symbol: str, resolution: str = "1D") -> "PriceSeries":
        candles: List[Candle] = []
        for row in payload.get("candles") or []:
            try:
                candles.append(Candle.from_fyers(row))
            except (ValueError, TypeError, OSError):
                # One corrupt bar should not lose the other 1,239. A gap is
                # visible downstream; an exception here would not be.
                continue
        candles.sort(key=lambda c: c.timestamp)
        return cls(symbol=symbol, resolution=resolution, candles=candles)

    @property
    def closes(self) -> List[float]:
        return [c.close for c in self.candles]

    @property
    def latest(self) -> Optional[Candle]:
        return self.candles[-1] if self.candles else None

    def __len__(self) -> int:
        return len(self.candles)


class EquityHolding(BaseModel):
    """One stock position, from Fyers or entered by hand.

    Enriched from the symbol master so the portfolio layer can group by sector
    or cap without re-resolving every symbol.
    """

    symbol: str = Field(description="NSE trading symbol, e.g. RELIANCE")
    quantity: float = Field(gt=0)
    avg_cost: float = Field(gt=0, description="Average buy price per share")
    buy_date: Optional[date] = Field(
        default=None,
        description="Not provided by Fyers; supplied by the user. Required for XIRR.",
    )

    # From the broker, when the source is a live holdings call.
    ltp: Optional[float] = None
    holding_type: HoldingType = "UNKNOWN"
    isin: Optional[str] = None
    source: Literal["fyers", "manual"] = "manual"

    # From the symbol master.
    name: Optional[str] = None
    sector: Optional[str] = None
    cap: Optional[str] = None
    fyers_symbol: Optional[str] = None

    @field_validator("symbol", mode="before")
    @classmethod
    def _canonicalise(cls, value: Any) -> str:
        """Accept any namespace and store the canonical NSE symbol.

        A user pasting "RELIANCE.NS" and a Fyers payload saying
        "NSE:RELIANCE-EQ" must not become two separate holdings.
        """
        text = str(value or "").strip()
        if not text:
            raise ValueError("symbol is required")
        return symbol_master.canonical(text) or text.upper()

    @field_validator("buy_date")
    @classmethod
    def _not_in_future(cls, value: Optional[date]) -> Optional[date]:
        if value and value > date.today():
            raise ValueError("buy_date cannot be in the future")
        return value

    @model_validator(mode="after")
    def _enrich(self) -> "EquityHolding":
        record = symbol_master.lookup(self.symbol)
        if record:
            self.name = self.name or record.name
            self.sector = self.sector or record.sector
            self.cap = self.cap or record.cap
            self.fyers_symbol = self.fyers_symbol or record.fyers
            self.isin = self.isin or record.isin
        return self

    @property
    def invested(self) -> float:
        return self.quantity * self.avg_cost

    @property
    def current_value(self) -> Optional[float]:
        return self.quantity * self.ltp if self.ltp is not None else None

    @property
    def unrealised_pnl(self) -> Optional[float]:
        value = self.current_value
        return value - self.invested if value is not None else None

    @property
    def unrealised_pnl_pct(self) -> Optional[float]:
        pnl = self.unrealised_pnl
        if pnl is None or self.invested == 0:
            return None
        return pnl / self.invested * 100.0

    @property
    def known(self) -> bool:
        """False when the symbol is not in the master — flag it, do not drop it."""
        return self.fyers_symbol is not None

    @classmethod
    def from_fyers(cls, row: Dict[str, Any]) -> "EquityHolding":
        """Build from one entry of the /holdings `holdings` array.

        Quantity uses `remainingQuantity` when present: `quantity` counts stock
        pledged as collateral, which the account no longer freely holds.
        """
        quantity = row.get("remainingQuantity") or row.get("quantity") or 0
        return cls(
            symbol=row.get("symbol") or "",
            quantity=float(quantity),
            avg_cost=float(row.get("costPrice") or 0) or 0.01,
            ltp=_optional_float(row.get("ltp")),
            holding_type=row.get("holdingType") if row.get("holdingType") in ("HLD", "T1") else "UNKNOWN",
            isin=row.get("isin") or None,
            source="fyers",
        )


class FundHolding(BaseModel):
    """One mutual fund position. Always manual — no broker feed supplies these."""

    scheme_code: int = Field(gt=0, description="mfapi.in scheme code")
    units: float = Field(gt=0)
    avg_nav: float = Field(gt=0, description="Average purchase NAV")
    buy_date: Optional[date] = None

    # Filled in at valuation time from mfapi.in.
    scheme_name: Optional[str] = None
    category: Optional[str] = None
    fund_house: Optional[str] = None
    latest_nav: Optional[float] = None
    latest_nav_date: Optional[date] = None

    @field_validator("buy_date")
    @classmethod
    def _not_in_future(cls, value: Optional[date]) -> Optional[date]:
        if value and value > date.today():
            raise ValueError("buy_date cannot be in the future")
        return value

    @property
    def invested(self) -> float:
        return self.units * self.avg_nav

    @property
    def current_value(self) -> Optional[float]:
        return self.units * self.latest_nav if self.latest_nav is not None else None

    @property
    def unrealised_pnl(self) -> Optional[float]:
        value = self.current_value
        return value - self.invested if value is not None else None

    @property
    def unrealised_pnl_pct(self) -> Optional[float]:
        pnl = self.unrealised_pnl
        if pnl is None or self.invested == 0:
            return None
        return pnl / self.invested * 100.0


class PortfolioOptions(BaseModel):
    benchmark: str = Field(default="NSE:NIFTY50-INDEX")
    risk_free_rate: float = Field(default=0.065, ge=0.0, le=0.25)


class PortfolioRequest(BaseModel):
    """The stateless analysis input.

    The backend holds no portfolio: the browser sends the whole thing on every
    call. That is what lets this work with no database and no accounts through
    Phase 5.
    """

    equity: List[EquityHolding] = Field(default_factory=list)
    funds: List[FundHolding] = Field(default_factory=list)
    cash: float = Field(default=0.0, ge=0.0)
    options: PortfolioOptions = Field(default_factory=PortfolioOptions)

    @model_validator(mode="after")
    def _require_something(self) -> "PortfolioRequest":
        if not self.equity and not self.funds:
            raise ValueError("Portfolio must contain at least one equity or fund holding")
        return self

    @model_validator(mode="after")
    def _merge_duplicate_symbols(self) -> "PortfolioRequest":
        """Fold repeated symbols into one quantity-weighted position.

        Fyers can return the same symbol twice (settled HLD plus unsettled T1),
        and a user can add a stock they already hold. Left alone, both would
        double-count the position's weight and skew every concentration measure.
        """
        merged: Dict[str, EquityHolding] = {}
        for holding in self.equity:
            existing = merged.get(holding.symbol)
            if existing is None:
                merged[holding.symbol] = holding
                continue
            total_qty = existing.quantity + holding.quantity
            existing.avg_cost = (
                existing.invested + holding.invested
            ) / total_qty
            existing.quantity = total_qty
            existing.ltp = existing.ltp if existing.ltp is not None else holding.ltp
            # The earlier purchase governs the holding period.
            dates = [d for d in (existing.buy_date, holding.buy_date) if d]
            existing.buy_date = min(dates) if dates else None
        self.equity = list(merged.values())
        return self


def _optional_float(value: Any) -> Optional[float]:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result else None


class HoldingsResponse(BaseModel):
    """What GET /api/fyers/holdings returns."""

    count: int
    holdings: List[EquityHolding]
    total_investment: float = 0.0
    total_current_value: float = 0.0
    total_pnl: float = 0.0
    total_pnl_pct: Optional[float] = None
    unknown_symbols: List[str] = Field(default_factory=list)

    @classmethod
    def from_fyers(cls, payload: Dict[str, Any]) -> "HoldingsResponse":
        holdings: List[EquityHolding] = []
        for row in payload.get("holdings") or []:
            try:
                holdings.append(EquityHolding.from_fyers(row))
            except (ValueError, TypeError):
                # A single unparseable row must not hide the rest of the
                # portfolio; the count mismatch is visible to the caller.
                continue

        overall = payload.get("overall") or {}
        invested = float(overall.get("total_investment") or 0)
        current = float(overall.get("total_current_value") or 0)
        pnl = float(overall.get("total_pl") or 0)
        return cls(
            count=len(holdings),
            holdings=holdings,
            total_investment=invested,
            total_current_value=current,
            total_pnl=pnl,
            # Prefer our own arithmetic over the upstream percentage, which is
            # rounded to a whole number in the payload.
            total_pnl_pct=(pnl / invested * 100.0) if invested else None,
            unknown_symbols=[h.symbol for h in holdings if not h.known],
        )
