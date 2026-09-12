"""Option chain, Greeks and portfolio hedging routes.

The chain endpoints need a live Fyers token — NSE's own option chain is behind
a cookie wall, and there is no free unauthenticated source that is not a
scrape waiting to break. The hedging endpoints do not: sizing a protective put
is arithmetic over the portfolio's own numbers plus an index level, so it works
for a user who has not connected a broker.
"""

import logging
import math
import os
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field

from app import options as options_engine
from app import symbols as symbol_master
from app.fyers_client import FyersAuthError, FyersClient, FyersError
from app.portfolio import value_portfolio
from app.quant.risk import evaluate_portfolio_danger
from app.schemas import PortfolioRequest

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/options", tags=["Options"])

# Fyers wants the index form for indices and the -EQ form for stocks; the
# symbol master already knows which is which.
INDEX_ALIASES = {
    "NIFTY": "NSE:NIFTY50-INDEX",
    "NIFTY50": "NSE:NIFTY50-INDEX",
    "BANKNIFTY": "NSE:NIFTYBANK-INDEX",
    "NIFTYBANK": "NSE:NIFTYBANK-INDEX",
    "FINNIFTY": "NSE:FINNIFTY-INDEX",
    "MIDCPNIFTY": "NSE:MIDCPNIFTY-INDEX",
}


def _is_production() -> bool:
    return os.getenv("ENV", "").lower() == "production"


def _is_auth_disabled() -> bool:
    return os.getenv("DISABLE_AUTH", "true").lower() in ("true", "1", "yes") and not _is_production()


def require_client(x_fyers_token: Optional[str] = Header(None)) -> Optional[FyersClient]:
    token = x_fyers_token or os.getenv("FYERS_ACCESS_TOKEN")
    if not token:
        return None
    try:
        return FyersClient(access_token=token)
    except FyersError:
        return None


def resolve_symbol(symbol: str) -> str:
    probe = symbol.strip().upper()
    if probe in INDEX_ALIASES:
        return INDEX_ALIASES[probe]
    if ":" in probe:
        return probe
    fyers = symbol_master.to_fyers(probe)
    if fyers:
        return fyers
    raise HTTPException(status_code=404, detail=f"Unknown symbol {symbol!r}.")


def days_until(expiry_epoch: Optional[int]) -> float:
    """Calendar days to an expiry epoch, floored at same-day.

    Floored rather than allowed negative because a stale chain with a passed
    expiry would otherwise produce negative time-to-expiry and nonsense Greeks.
    """
    if not expiry_epoch:
        return 7.0
    try:
        expiry = datetime.fromtimestamp(int(expiry_epoch)).date()
    except (ValueError, OSError, TypeError):
        return 7.0
    return max(0.5, (expiry - date.today()).days)


class HedgeRequest(BaseModel):
    portfolio: Optional[PortfolioRequest] = None
    portfolio_value: Optional[float] = Field(None, gt=0)
    portfolio_beta: Optional[float] = Field(None, gt=0)
    index_spot: float = Field(..., gt=0, description="Current Nifty level")
    target_max_drawdown: float = Field(0.10, ge=0.01, le=0.5)
    upside_cap: float = Field(0.10, ge=0.02, le=0.5, description="Collar only")
    lot_size: int = Field(options_engine.DEFAULT_NIFTY_LOT, ge=1)
    days_to_expiry: float = Field(30.0, ge=1.0, le=400.0)
    volatility: float = Field(0.15, gt=0.01, le=2.0, description="Annualised, decimal")
    strategy: str = Field("protective_put", description="protective_put | collar")


class PayoffLeg(BaseModel):
    option_type: str = Field("CE", description="CE | PE | FUT")
    strike: float = Field(..., gt=0)
    quantity: int = Field(..., description="Negative to sell")
    premium: float = Field(0.0, ge=0.0)
    lot_size: int = Field(options_engine.DEFAULT_NIFTY_LOT, ge=1)


class PayoffRequest(BaseModel):
    spot: float = Field(..., gt=0)
    legs: List[PayoffLeg]
    width: float = Field(0.25, gt=0.01, le=1.0)


@router.get("/{symbol}/chain")
def chain(
    symbol: str,
    strike_count: int = Query(10, ge=1, le=50, description="Strikes per side of ATM"),
    timestamp: str = Query("", description="Expiry epoch from expiryData; blank = nearest"),
    client: Optional[FyersClient] = Depends(require_client),
):
    """The raw normalised chain, plus the expiry list for the picker."""
    fyers_symbol = resolve_symbol(symbol)
    if client is None or not client.access_token:
        return {
            "symbol": fyers_symbol,
            "context": {
                "spot": 0.0,
                "atm": 0.0,
                "pcr": 0.0,
                "max_pain": 0.0,
                "call_wall": 0.0,
                "put_wall": 0.0,
                "total_call_oi": 0,
                "total_put_oi": 0,
                "expiries": [],
            },
            "rows": [],
        }

    try:
        payload = client.option_chain(fyers_symbol, strike_count, timestamp)
    except FyersAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc))
    except FyersError as exc:
        raise HTTPException(status_code=502, detail=f"Fyers option chain failed: {exc}")

    rows, context = options_engine.parse_chain(payload)
    return {
        "symbol": fyers_symbol,
        "context": context,
        "rows": [
            {
                "strike": row.strike,
                "option_type": row.option_type,
                "symbol": row.symbol,
                "ltp": row.ltp,
                "oi": row.oi,
                "oi_change": row.oi_change,
                "volume": row.volume,
                "ltp_change": row.ltp_change,
                "bid": row.bid,
                "ask": row.ask,
            }
            for row in rows
        ],
    }


@router.get("/{symbol}/analysis")
def chain_analysis(
    symbol: str,
    strike_count: int = Query(15, ge=1, le=50),
    timestamp: str = Query(""),
    client: Optional[FyersClient] = Depends(require_client),
):
    """PCR, max pain, OI walls, build-up classification and the IV skew."""
    fyers_symbol = resolve_symbol(symbol)
    if client is None or not client.access_token:
        return {
            "symbol": fyers_symbol,
            "context": {
                "spot": 0.0,
                "atm": 0.0,
                "pcr": 0.0,
                "max_pain": 0.0,
                "call_wall": 0.0,
                "put_wall": 0.0,
                "total_call_oi": 0,
                "total_put_oi": 0,
                "expiries": [],
            },
            "rows": [],
            "max_pain": 0.0,
            "pcr": 0.0,
            "call_wall": 0.0,
            "put_wall": 0.0,
        }

    try:
        payload = client.option_chain(fyers_symbol, strike_count, timestamp)
    except FyersAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc))
    except FyersError as exc:
        raise HTTPException(status_code=502, detail=f"Fyers option chain failed: {exc}")

    data = payload.get("data") or {}
    expiries = data.get("expiryData") or []
    selected = timestamp or (expiries[0].get("expiry") if expiries else None)

    result = options_engine.analyse_chain(payload, days_to_expiry=days_until(selected))
    result["symbol"] = fyers_symbol
    return result


@router.get("/greeks")
def option_greeks(
    spot: float = Query(..., gt=0),
    strike: float = Query(..., gt=0),
    days_to_expiry: float = Query(..., gt=0, le=1000),
    volatility: float = Query(..., gt=0.001, le=5.0, description="Annualised, decimal"),
    option_type: str = Query("CE", pattern="^(CE|PE)$"),
    rate: float = Query(options_engine.DEFAULT_RISK_FREE, ge=0, le=0.5),
):
    """Black-Scholes price and Greeks for one contract. No token needed."""
    time_to_expiry = days_to_expiry / options_engine.CALENDAR_DAYS
    return {
        "price": round(
            options_engine.black_scholes_price(
                spot, strike, time_to_expiry, volatility, rate, option_type
            ),
            2,
        ),
        "greeks": options_engine.greeks(
            spot, strike, time_to_expiry, volatility, rate, option_type
        ),
        "inputs": {
            "spot": spot, "strike": strike, "days_to_expiry": days_to_expiry,
            "volatility": volatility, "rate": rate, "option_type": option_type,
        },
        "note": "Theta is per calendar day; vega is per 1 percentage point of IV.",
    }


@router.post("/hedge")
def hedge(
    request: HedgeRequest,
    x_fyers_token: Optional[str] = Header(None),
):
    """Size the index put or collar that caps a portfolio's drawdown.

    Either supply `portfolio` and let the engine compute value and beta, or
    pass `portfolio_value` and `portfolio_beta` directly for a what-if.
    """
    value = request.portfolio_value
    beta = request.portfolio_beta

    if value is None or beta is None:
        if request.portfolio is None:
            raise HTTPException(
                status_code=400,
                detail="Supply either `portfolio`, or both `portfolio_value` and `portfolio_beta`.",
            )
        client = None
        if x_fyers_token:
            try:
                client = FyersClient(access_token=x_fyers_token)
            except FyersError:
                client = None
        valuation = value_portfolio(request.portfolio, client)
        totals = valuation.get("totals") or {}
        danger = evaluate_portfolio_danger(
            valuation.get("holdings", []), totals.get("current_value", 0.0)
        )
        value = value if value is not None else totals.get("current_value") or 0.0
        beta = beta if beta is not None else (danger.get("metrics") or {}).get("portfolio_beta", 1.0)

    if not value or value <= 0:
        raise HTTPException(status_code=400, detail="Portfolio has no positive current value to hedge.")

    if request.strategy == "collar":
        result = options_engine.size_collar(
            portfolio_value=value,
            portfolio_beta=beta or 1.0,
            index_spot=request.index_spot,
            target_max_drawdown=request.target_max_drawdown,
            upside_cap=request.upside_cap,
            lot_size=request.lot_size,
            days_to_expiry=request.days_to_expiry,
            volatility=request.volatility,
        )
    else:
        result = options_engine.size_protective_put(
            portfolio_value=value,
            portfolio_beta=beta or 1.0,
            index_spot=request.index_spot,
            target_max_drawdown=request.target_max_drawdown,
            lot_size=request.lot_size,
            days_to_expiry=request.days_to_expiry,
            volatility=request.volatility,
        )

    result["portfolio_value_inr"] = round(value, 2)
    return result


@router.post("/payoff")
def payoff(request: PayoffRequest) -> Dict[str, Any]:
    """Expiry payoff curve for an arbitrary multi-leg position."""
    return options_engine.payoff_curve(
        [leg.model_dump() for leg in request.legs],
        spot=request.spot,
        width=request.width,
    )
