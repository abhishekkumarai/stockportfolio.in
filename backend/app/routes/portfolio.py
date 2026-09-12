import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.broker_statement import (
    convert_statement_to_portfolio,
    parse_excel_statement,
)
from app.fyers_client import FyersClient, FyersError
from app.news import get_portfolio_news_digest
from app.portfolio import value_portfolio
from app.quant.growth import evaluate_portfolio_growth
from app.quant.rebalance import generate_rebalancing_plan
from app.quant.risk import evaluate_portfolio_danger
from app.schemas import PortfolioRequest

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/portfolio", tags=["Portfolio"])


def get_optional_client(x_fyers_token: Optional[str] = Header(None)) -> Optional[FyersClient]:
    """A Fyers client when the caller has a token, otherwise None."""
    if not x_fyers_token:
        return None
    try:
        return FyersClient(access_token=x_fyers_token)
    except FyersError as exc:
        logger.warning("Could not build Fyers client: %s", exc)
        return None


class RebalanceRequest(BaseModel):
    portfolio: PortfolioRequest
    cash_inflow: float = Field(0.0, ge=0.0)
    drift_tolerance: float = Field(0.05, ge=0.01, le=0.5)
    mode: str = Field("zero_tax_inflow", description="'zero_tax_inflow' | 'drift_rebalance'")


@router.post("/value")
def value(
    request: PortfolioRequest,
    client: Optional[FyersClient] = Depends(get_optional_client),
):
    """Price a portfolio and return per-holding P&L plus allocation."""
    try:
        return value_portfolio(request, client)
    except Exception as exc:
        logger.exception("Portfolio valuation failed")
        raise HTTPException(status_code=502, detail=f"Valuation failed: {exc}")


@router.post("/analyse")
def analyse(
    request: PortfolioRequest,
    client: Optional[FyersClient] = Depends(get_optional_client),
):
    """Comprehensive Danger vs. Expected Growth Intelligence analysis."""
    try:
        valuation = value_portfolio(request, client)
        holdings = valuation.get("holdings", [])
        total_val = valuation.get("totals", {}).get("current_value", 0.0)
        cash_val = valuation.get("totals", {}).get("cash", 0.0)

        # 1. Danger Matrix Assessment
        danger = evaluate_portfolio_danger(holdings, total_val, cash_val)

        # 2. Expected Growth & Monte Carlo Simulation
        growth = evaluate_portfolio_growth(holdings, total_val)

        return {
            "valuation": valuation,
            "danger": danger,
            "growth": growth,
            "status": "success",
        }
    except Exception as exc:
        logger.exception("Portfolio analysis failed")
        raise HTTPException(status_code=502, detail=f"Analysis failed: {exc}")


@router.post("/rebalance")
def rebalance(
    req: RebalanceRequest,
    client: Optional[FyersClient] = Depends(get_optional_client),
):
    """Generates tax-aware rebalancing buy/trim order sheets."""
    try:
        valuation = value_portfolio(req.portfolio, client)
        holdings = valuation.get("holdings", [])
        total_val = valuation.get("totals", {}).get("current_value", 0.0)

        plan = generate_rebalancing_plan(
            holdings=holdings,
            total_current_value=total_val,
            cash_inflow=req.cash_inflow,
            drift_tolerance=req.drift_tolerance,
            mode=req.mode,  # type: ignore
        )
        return plan
    except Exception as exc:
        logger.exception("Portfolio rebalancing calculation failed")
        raise HTTPException(status_code=502, detail=f"Rebalancing failed: {exc}")


@router.post("/news")
def portfolio_news(request: PortfolioRequest):
    """Pulls free, tagged news catalysts for the user's holdings."""
    try:
        symbols = [h.symbol for h in request.equity]
        digest = get_portfolio_news_digest(symbols)
        return {"count": len(digest), "articles": digest}
    except Exception as exc:
        logger.exception("Portfolio news fetch failed")
        raise HTTPException(status_code=502, detail=f"News fetch failed: {exc}")


def _find_offline_dir() -> Path:
    candidates = [
        Path(__file__).resolve().parent.parent.parent.parent / "ignore_offline",
        Path(__file__).resolve().parent.parent.parent / "ignore_offline",
        Path.cwd() / "ignore_offline",
        Path("/app/ignore_offline"),
    ]
    for c in candidates:
        if c.exists():
            return c
    return candidates[0]


@router.get("/offline/files")
def list_offline_statement_files():
    """List available offline holdings files in the ignore_offline directory."""
    base_dir = _find_offline_dir()
    if not base_dir.exists():
        return {"files": [], "directory": str(base_dir), "count": 0}

    files = []
    for p in sorted(list(base_dir.glob("*.xlsx")) + list(base_dir.glob("*.xls"))):
        files.append({
            "name": p.name,
            "size_bytes": p.stat().st_size,
            "modified_at": datetime.fromtimestamp(p.stat().st_mtime).isoformat(),
        })

    return {"files": files, "directory": str(base_dir), "count": len(files)}


@router.post("/offline/import")
def import_offline_statement(filename: Optional[str] = None):
    """Parse and import a statement from the ignore_offline directory."""
    base_dir = _find_offline_dir()
    if not base_dir.exists():
        raise HTTPException(status_code=404, detail="ignore_offline directory not found.")

    if filename:
        target = base_dir / filename
    else:
        # Default to first found .xlsx
        candidates = sorted(list(base_dir.glob("*.xlsx")) + list(base_dir.glob("*.xls")))
        if not candidates:
            raise HTTPException(status_code=404, detail="No Excel files in ignore_offline.")
        target = candidates[0]

    if not target.exists():
        raise HTTPException(status_code=404, detail=f"File {target.name} not found.")

    try:
        statement = parse_excel_statement(target)
        portfolio_req, report = convert_statement_to_portfolio(statement)
        valuation = value_portfolio(portfolio_req)

        return {
            "status": "success",
            "file": target.name,
            "statement": statement.model_dump(),
            "portfolio": portfolio_req.model_dump(),
            "report": report,
            "valuation": valuation,
        }
    except Exception as exc:
        logger.exception("Failed to import offline statement")
        raise HTTPException(status_code=500, detail=f"Statement import failed: {exc}")


@router.post("/upload-statement")
async def upload_statement(file: UploadFile = File(...)):
    """Upload and parse an Excel broker holding statement (.xlsx) in real-time."""
    if not file.filename or not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Only .xlsx or .xls Excel files are supported.")

    try:
        contents = await file.read()
        statement = parse_excel_statement(contents, file_name=file.filename)
        portfolio_req, report = convert_statement_to_portfolio(statement)
        valuation = value_portfolio(portfolio_req)

        return {
            "status": "success",
            "file": file.filename,
            "statement": statement.model_dump(),
            "portfolio": portfolio_req.model_dump(),
            "report": report,
            "valuation": valuation,
        }
    except Exception as exc:
        logger.exception("Failed to parse uploaded statement")
        raise HTTPException(status_code=500, detail=f"Statement processing failed: {exc}")
