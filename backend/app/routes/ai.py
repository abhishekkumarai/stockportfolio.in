"""AI narrative and sentiment routes.

Every response carries whether the AI layer was actually available and, for
the narrative, whether any figure in the prose failed verification against the
computed data. Those two fields are not decoration — a memo that quietly
invented a number should be visible on the wire, not just in a log line.
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from app import symbols as symbol_master
from app.ai import is_configured
from app.ai import narrative as narrative_engine
from app.ai import sentiment as sentiment_engine
from app.fyers_client import FyersClient, FyersError
from app.news import get_portfolio_news_digest
from app.portfolio import value_portfolio
from app.quant.growth import evaluate_portfolio_growth
from app.quant.risk import evaluate_portfolio_danger
from app.schemas import PortfolioRequest

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ai", tags=["AI"])


def get_optional_client(x_fyers_token: Optional[str] = Header(None)) -> Optional[FyersClient]:
    if not x_fyers_token:
        return None
    try:
        return FyersClient(access_token=x_fyers_token)
    except FyersError:
        return None


class ReportRequest(BaseModel):
    portfolio: PortfolioRequest
    period_label: Optional[str] = Field(None, description='e.g. "September 2026"')
    include_news: bool = True
    effort: str = Field("high", pattern="^(low|medium|high|xhigh|max)$")


class SentimentRequest(BaseModel):
    headlines: List[str] = Field(..., min_length=1, max_length=100)
    use_llm: bool = True


class ExplainRequest(BaseModel):
    symbol: str
    include_technicals: bool = True
    include_fundamentals: bool = True


@router.get("/status")
def status():
    """Whether the AI layer is configured, and what it changes when it is not."""
    configured = is_configured()
    return {
        "configured": configured,
        "report_model": narrative_engine.REPORT_MODEL,
        "classifier_model": sentiment_engine.CLASSIFIER_MODEL,
        "note": (
            "The AI layer narrates computed metrics and classifies news "
            "headlines. Without it, every score, risk metric and recommendation "
            "still works; headline sentiment falls back to VADER, which is "
            "unreliable on financial text."
            if not configured
            else "AI narrative and LLM headline classification are active."
        ),
    }


@router.post("/report")
def monthly_report(
    request: ReportRequest,
    client: Optional[FyersClient] = Depends(get_optional_client),
):
    """The monthly portfolio memo, written over computed metrics and verified."""
    try:
        valuation = value_portfolio(request.portfolio, client)
    except Exception as exc:
        logger.exception("Valuation failed before narrative generation")
        raise HTTPException(status_code=502, detail=f"Valuation failed: {exc}")

    holdings = valuation.get("holdings", [])
    total = (valuation.get("totals") or {}).get("current_value", 0.0)

    analysis = {
        "valuation": valuation,
        "danger": evaluate_portfolio_danger(holdings, total, request.portfolio.cash),
        "growth": evaluate_portfolio_growth(holdings, total),
    }

    news = None
    if request.include_news and request.portfolio.equity:
        try:
            news = get_portfolio_news_digest([h.symbol for h in request.portfolio.equity])
        except Exception as exc:
            # A news outage should shorten the memo, not block it.
            logger.warning("News digest unavailable for the report: %s", exc)

    result = narrative_engine.write_report(
        analysis, news=news, period_label=request.period_label, effort=request.effort
    )
    result["danger_score"] = analysis["danger"].get("danger_score")
    result["growth_score"] = analysis["growth"].get("growth_score")
    return result


@router.post("/sentiment")
def classify_headlines(request: SentimentRequest):
    """Classify headlines with the LLM, falling back to VADER per headline."""
    results = sentiment_engine.classify_batch(request.headlines, request.use_llm)
    return {
        "count": len(results),
        "results": [
            {"headline": headline, **result}
            for headline, result in zip(request.headlines, results)
        ],
        "aggregate": sentiment_engine.aggregate(results),
    }


@router.post("/explain")
def explain_holding(request: ExplainRequest):
    """A plain-English gloss on one holding's computed scorecard."""
    from app import scoring
    from app.fundamentals import get_fundamentals, score_fundamentals

    canonical = symbol_master.canonical(request.symbol) or request.symbol.upper()

    technicals: Dict[str, Any] = {}
    technical_card = None
    if request.include_technicals:
        try:
            import yfinance as yf

            from app.technicals import extract_technicals, score_technicals

            yf_symbol = symbol_master.to_yfinance(canonical) or f"{canonical}.NS"
            history = yf.Ticker(yf_symbol).history(period="1y", interval="1d")
            if not history.empty:
                if history.index.tz is not None:
                    history.index = history.index.tz_localize(None)
                technicals = extract_technicals(history)
                technical_card = score_technicals(technicals)
        except Exception as exc:
            logger.warning("Technicals unavailable for %s: %s", canonical, exc)

    fundamentals: Dict[str, Any] = {}
    fundamental_card = None
    if request.include_fundamentals:
        try:
            fundamentals = get_fundamentals(canonical)
            fundamental_card = score_fundamentals(fundamentals)
        except Exception as exc:
            logger.warning("Fundamentals unavailable for %s: %s", canonical, exc)

    cards = [(card, 0.5) for card in (technical_card, fundamental_card) if card is not None]
    if not cards:
        raise HTTPException(
            status_code=502,
            detail=f"Neither technicals nor fundamentals could be computed for {canonical}.",
        )

    overall = scoring.combine("overall", cards, min_coverage=0.3)
    components = {
        name: card
        for name, card in (("technicals", technical_card), ("fundamentals", fundamental_card))
        if card is not None
    }
    recommendation = scoring.recommend(canonical, overall, components).as_dict()

    result = narrative_engine.explain_holding(
        canonical, recommendation, technicals, fundamentals
    )
    result["recommendation"] = recommendation
    return result
