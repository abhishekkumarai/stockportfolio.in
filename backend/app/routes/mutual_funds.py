import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Path, Query

from app import mf_analysis
from app.mfapi_client import (
    MFApiError,
    SchemeNotFoundError,
    client,
    parse_nav_date,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/mf", tags=["Mutual Funds"])


def _handle(exc: Exception, context: str) -> HTTPException:
    """Map client errors onto sensible HTTP statuses."""
    if isinstance(exc, SchemeNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    logger.error("%s failed: %s", context, exc)
    return HTTPException(status_code=502, detail=f"Upstream mutual fund API error: {exc}")


# Static paths must be declared before /{scheme_code}, otherwise FastAPI tries to
# parse "search" and "compare" as an int scheme code and returns 422.


@router.get("/search")
def search_schemes(
    q: str = Query(..., min_length=2, description="Part of a scheme or fund house name"),
    limit: int = Query(20, ge=1, le=200),
    direct_only: bool = Query(False, description="Keep only Direct plans"),
    growth_only: bool = Query(False, description="Keep only Growth plans (drop IDCW)"),
):
    """Search schemes by name, with optional plan filters.

    The upstream search returns every plan variant of a fund, so the filters are
    usually what you want: Direct + Growth is the comparable, total-return series.
    """
    try:
        results = client.search(q)
    except Exception as exc:
        raise _handle(exc, "scheme search")

    if direct_only:
        results = [r for r in results if "direct" in r.get("schemeName", "").lower()]
    if growth_only:
        results = [r for r in results if "growth" in r.get("schemeName", "").lower()]

    return {"query": q, "count": len(results[:limit]), "results": results[:limit]}


@router.get("/schemes")
def list_schemes(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """Page through the full scheme master (~37k schemes, including ISINs)."""
    try:
        return {"limit": limit, "offset": offset, "results": client.list_schemes(limit, offset)}
    except Exception as exc:
        raise _handle(exc, "scheme listing")


@router.get("/isin/{isin}")
def lookup_isin(isin: str = Path(..., description="ISIN, e.g. INF879O01027")):
    """Resolve an ISIN to its scheme. First call builds an index and is slow (~20s)."""
    try:
        scheme = client.resolve_isin(isin)
    except Exception as exc:
        raise _handle(exc, "ISIN lookup")

    if not scheme:
        raise HTTPException(status_code=404, detail=f"No scheme found for ISIN {isin}")
    return scheme


@router.get("/compare")
def compare(
    codes: str = Query(..., description="Comma-separated scheme codes, e.g. 122639,120503"),
    risk_free_rate: float = Query(mf_analysis.DEFAULT_RISK_FREE_RATE, ge=0, le=0.25),
):
    """Compare up to 5 schemes, including returns over their shared date range."""
    try:
        scheme_codes = [int(part) for part in codes.split(",") if part.strip()]
    except ValueError:
        raise HTTPException(status_code=400, detail="codes must be comma-separated integers")

    if not 2 <= len(scheme_codes) <= 5:
        raise HTTPException(status_code=400, detail="Provide between 2 and 5 scheme codes")

    try:
        return mf_analysis.compare_schemes(scheme_codes, risk_free_rate)
    except Exception as exc:
        raise _handle(exc, "scheme comparison")


@router.get("/{scheme_code}")
def get_scheme(
    scheme_code: int,
    start_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    limit: Optional[int] = Query(None, ge=1, description="Keep only the N most recent NAVs"),
):
    """Scheme metadata plus NAV history, newest first."""
    try:
        payload = client.get_scheme(scheme_code, start_date, end_date)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise _handle(exc, f"scheme {scheme_code}")

    data = payload["data"][:limit] if limit else payload["data"]
    return {"meta": payload["meta"], "count": len(data), "data": data}


@router.get("/{scheme_code}/latest")
def get_latest(scheme_code: int):
    """Most recent NAV for a scheme."""
    try:
        payload = client.get_latest_nav(scheme_code)
    except Exception as exc:
        raise _handle(exc, f"latest NAV for {scheme_code}")

    point = payload["data"][0] if payload["data"] else None
    return {
        "meta": payload["meta"],
        "nav": float(point["nav"]) if point else None,
        "date": parse_nav_date(point["date"]).isoformat() if point else None,
    }


@router.get("/{scheme_code}/analysis")
def analyse(
    scheme_code: int,
    risk_free_rate: float = Query(
        mf_analysis.DEFAULT_RISK_FREE_RATE, ge=0, le=0.25, description="Annual, as a decimal"
    ),
):
    """Trailing returns, risk metrics and rolling-return distributions for a scheme."""
    try:
        return mf_analysis.analyse_scheme(scheme_code, risk_free_rate)
    except Exception as exc:
        raise _handle(exc, f"analysis for {scheme_code}")


@router.get("/{scheme_code}/rolling")
def rolling(
    scheme_code: int,
    years: int = Query(3, ge=1, le=15, description="Rolling window length in years"),
):
    """Annualised returns across every possible start date for the given window."""
    try:
        payload = client.get_scheme(scheme_code)
    except Exception as exc:
        raise _handle(exc, f"rolling returns for {scheme_code}")

    series = mf_analysis.to_series(payload["data"])
    return {"meta": payload["meta"], **mf_analysis.rolling_returns(series, years)}


@router.get("/{scheme_code}/sip")
def sip(
    scheme_code: int,
    amount: float = Query(5000, gt=0, description="Monthly investment in rupees"),
    start_date: Optional[str] = Query(None, description="YYYY-MM-DD; defaults to inception"),
    end_date: Optional[str] = Query(None, description="YYYY-MM-DD; defaults to latest NAV"),
    day_of_month: int = Query(1, ge=1, le=28, description="SIP debit day"),
):
    """Backtest a monthly SIP. Returns XIRR alongside invested and final values."""
    try:
        payload = client.get_scheme(scheme_code)
    except Exception as exc:
        raise _handle(exc, f"SIP backtest for {scheme_code}")

    series = mf_analysis.to_series(payload["data"])
    result = mf_analysis.simulate_sip(series, amount, start_date, end_date, day_of_month)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return {"meta": payload["meta"], **result}


@router.get("/{scheme_code}/lumpsum")
def lumpsum(
    scheme_code: int,
    amount: float = Query(100000, gt=0, description="One-time investment in rupees"),
    start_date: Optional[str] = Query(None, description="YYYY-MM-DD; defaults to inception"),
    end_date: Optional[str] = Query(None, description="YYYY-MM-DD; defaults to latest NAV"),
):
    """Backtest a one-time investment."""
    try:
        payload = client.get_scheme(scheme_code)
    except Exception as exc:
        raise _handle(exc, f"lumpsum backtest for {scheme_code}")

    series = mf_analysis.to_series(payload["data"])
    result = mf_analysis.simulate_lumpsum(series, amount, start_date, end_date)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return {"meta": payload["meta"], **result}
