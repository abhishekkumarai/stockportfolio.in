"""Quant routes: optimisation, factor exposure, regime, and target rebalancing.

All of these take a `PortfolioRequest` and are stateless, like the rest of the
portfolio surface. They are grouped separately from `/api/portfolio` because
they share an expensive precondition — an aligned matrix of daily returns for
every equity holding — and because their failure mode is distinctive: not
enough overlapping history. That is reported as a 422 with the specific
holding responsible, rather than a generic 500.
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from app import symbols as symbol_master
from app.fyers_client import FyersClient, FyersError
from app.portfolio import value_portfolio
from app.quant import factors as factor_engine
from app.quant import prices as price_engine
from app.quant import regime as regime_engine
from app.quant.optimise import METHODS, OptimisationConstraints, optimise
from app.quant.tax import generate_target_rebalance
from app.schemas import PortfolioRequest

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/quant", tags=["Quant"])


def get_optional_client(x_fyers_token: Optional[str] = Header(None)) -> Optional[FyersClient]:
    if not x_fyers_token:
        return None
    try:
        return FyersClient(access_token=x_fyers_token)
    except FyersError:
        return None


class OptimiseRequest(BaseModel):
    portfolio: PortfolioRequest
    method: str = Field("hrp", description="hrp | risk_parity | min_variance | max_sharpe")
    max_weight: float = Field(0.35, gt=0.0, le=1.0)
    sector_caps: Dict[str, float] = Field(default_factory=dict)
    period: str = Field("2y", description="History window, e.g. 1y, 2y, 5y")
    include_frontier: bool = False


class RebalanceToTargetRequest(BaseModel):
    portfolio: PortfolioRequest
    method: str = Field("hrp")
    target_weights: Optional[Dict[str, float]] = Field(
        None, description="Explicit targets; when absent they are optimised"
    )
    cash_inflow: float = Field(0.0, ge=0.0)
    drift_tolerance: float = Field(0.03, ge=0.005, le=0.5)
    allow_selling: bool = Field(
        True, description="False routes fresh cash only, for a zero-tax rebalance"
    )
    ltcg_used_this_year: float = Field(
        0.0, ge=0.0, description="LTCG already realised this financial year"
    )
    max_weight: float = Field(0.35, gt=0.0, le=1.0)
    period: str = "2y"


class FactorRequest(BaseModel):
    portfolio: PortfolioRequest
    period: str = "2y"
    rolling: bool = False


class RegimeRequest(BaseModel):
    portfolio: Optional[PortfolioRequest] = None
    period: str = "2y"


def _priced_holdings(
    request: PortfolioRequest, client: Optional[FyersClient]
) -> tuple[List[Dict[str, Any]], float]:
    valuation = value_portfolio(request, client)
    return valuation.get("holdings", []), (valuation.get("totals") or {}).get("current_value", 0.0)


def _returns_or_422(holdings: List[Dict[str, Any]], period: str):
    returns, report = price_engine.holdings_returns(holdings, period)
    if returns.empty or len(returns.columns) < 2:
        raise HTTPException(
            status_code=422,
            detail={
                "reason": (
                    "At least two equity holdings with overlapping price history "
                    "are needed. Mutual funds are excluded because an NAV series "
                    "is already a portfolio of the same stocks."
                ),
                "coverage": report,
            },
        )
    return returns, report


@router.get("/methods")
def list_methods():
    """Available allocators, with the trade-off each one makes."""
    return {
        "methods": [
            {
                "name": "hrp",
                "label": "Hierarchical risk parity",
                "recommended": True,
                "note": (
                    "Clusters by correlation and allocates risk down the tree. "
                    "Never inverts the covariance matrix, so it stays stable on "
                    "the noisy estimates a 20-holding portfolio produces."
                ),
            },
            {
                "name": "risk_parity",
                "label": "Equal risk contribution",
                "note": "Every holding contributes the same share of portfolio variance.",
            },
            {
                "name": "min_variance",
                "label": "Minimum variance",
                "note": "Lowest-volatility portfolio. Needs no expected-return estimate.",
            },
            {
                "name": "max_sharpe",
                "label": "Maximum Sharpe (tangency)",
                "note": (
                    "Textbook optimum, but historical means are a poor forecast of "
                    "returns and it concentrates hard into recent winners."
                ),
            },
        ]
    }


@router.post("/optimise")
def optimise_portfolio(
    request: OptimiseRequest,
    client: Optional[FyersClient] = Depends(get_optional_client),
):
    """Target weights for the equity sleeve, with risk contributions."""
    if request.method not in METHODS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown method {request.method!r}. Known: {', '.join(sorted(METHODS))}",
        )

    holdings, _ = _priced_holdings(request.portfolio, client)
    returns, report = _returns_or_422(holdings, request.period)

    sectors = {
        h["key"]: h.get("sector") or "Unclassified"
        for h in holdings if h.get("kind") == "equity"
    }
    constraints = OptimisationConstraints(
        max_weight=request.max_weight,
        sector_caps=request.sector_caps,
        sectors=sectors,
    )

    try:
        result = optimise(returns, request.method, constraints)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"reason": str(exc), "coverage": report})

    current = price_engine.weights_from_holdings(holdings)
    result["current_weights"] = {k: round(v, 4) for k, v in current.items()}
    result["drift"] = {
        symbol: round((current.get(symbol, 0.0) - target) * 100.0, 2)
        for symbol, target in result["weights"].items()
    }
    result["coverage"] = report

    if request.include_frontier and request.method in {"min_variance", "max_sharpe"}:
        from app.quant.optimise import efficient_frontier

        result["frontier"] = efficient_frontier(returns, constraints=constraints)

    return result


@router.post("/rebalance")
def rebalance_to_target(
    request: RebalanceToTargetRequest,
    client: Optional[FyersClient] = Depends(get_optional_client),
):
    """A tax-aware order sheet that moves the portfolio toward target weights."""
    holdings, total = _priced_holdings(request.portfolio, client)

    targets = request.target_weights
    optimisation: Optional[Dict[str, Any]] = None
    if not targets:
        returns, report = _returns_or_422(holdings, request.period)
        sectors = {
            h["key"]: h.get("sector") or "Unclassified"
            for h in holdings if h.get("kind") == "equity"
        }
        try:
            optimisation = optimise(
                returns, request.method,
                OptimisationConstraints(max_weight=request.max_weight, sectors=sectors),
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail={"reason": str(exc), "coverage": report})
        targets = optimisation["weights"]

    total_target = sum(targets.values())
    if total_target <= 0:
        raise HTTPException(status_code=400, detail="Target weights sum to zero.")
    if abs(total_target - 1.0) > 0.02:
        # Normalise rather than reject: an equity-only target set against a
        # portfolio holding cash and funds legitimately sums to less than 1.
        targets = {k: v / total_target for k, v in targets.items()}

    plan = generate_target_rebalance(
        holdings=holdings,
        target_weights=targets,
        total_current_value=total,
        cash_inflow=request.cash_inflow,
        drift_tolerance=request.drift_tolerance,
        ltcg_used_this_year=request.ltcg_used_this_year,
        allow_selling=request.allow_selling,
    )
    plan["target_source"] = "explicit" if request.target_weights else request.method
    if optimisation is not None:
        plan["optimisation"] = {
            "method": optimisation["method"],
            "expected_return_pct": optimisation["expected_return_pct"],
            "volatility_pct": optimisation["volatility_pct"],
            "effective_holdings": optimisation["effective_holdings"],
        }
    return plan


@router.post("/factors")
def factor_exposures(
    request: FactorRequest,
    client: Optional[FyersClient] = Depends(get_optional_client),
):
    """Decompose portfolio returns into factor exposure and residual alpha."""
    holdings, _ = _priced_holdings(request.portfolio, client)
    returns, report = _returns_or_422(holdings, request.period)

    weights = price_engine.weights_from_holdings(holdings)
    portfolio_returns = price_engine.portfolio_return_series(returns, weights)
    if portfolio_returns.empty:
        raise HTTPException(
            status_code=422,
            detail={"reason": "Could not build a portfolio return series.", "coverage": report},
        )

    factor_returns, missing = factor_engine.build_factor_returns(
        portfolio_returns.index.min(), portfolio_returns.index.max()
    )
    if factor_returns.empty:
        raise HTTPException(
            status_code=502,
            detail=(
                "No factor proxy index returned data. The regression needs at "
                "least the market leg."
            ),
        )

    result = factor_engine.analyse_exposures(portfolio_returns, factor_returns)
    result["missing_factors"] = missing
    result["coverage"] = report
    result["weights_note"] = (
        "Portfolio returns are reconstructed from today's weights held constant, "
        "not from an actual transaction history."
    )
    if request.rolling and result.get("available"):
        result["rolling"] = factor_engine.rolling_betas(portfolio_returns, factor_returns)
    return result


@router.post("/regime")
def market_regime(
    request: RegimeRequest,
    client: Optional[FyersClient] = Depends(get_optional_client),
):
    """Classify the current market regime, with the portfolio's own correlation.

    The benchmark alone gives volatility and trend; supplying a portfolio adds
    the cross-holding correlation term, which is the most informative crisis
    signal available from price data.
    """
    benchmark = price_engine.benchmark_series(request.period)
    if benchmark.empty:
        raise HTTPException(
            status_code=502, detail="Benchmark index history could not be fetched."
        )

    holdings_returns = None
    if request.portfolio is not None:
        holdings, _ = _priced_holdings(request.portfolio, client)
        candidate, _ = price_engine.holdings_returns(holdings, request.period)
        if not candidate.empty and len(candidate.columns) >= 2:
            holdings_returns = candidate

    result = regime_engine.classify(benchmark, holdings_returns)
    result["benchmark"] = "Nifty 500"
    result["used_portfolio_correlation"] = holdings_returns is not None
    return result
