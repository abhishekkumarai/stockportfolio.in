"""Backtesting engine v2 routes: run, optimise, walk-forward, permutation test.

Separate from `/api/backtest`, which stays on the v1 engine so the existing
frontend page is untouched. Everything here is under `/api/engine`.

Grid and permutation sizes are bounded at this edge rather than in the engine:
a walk-forward over a 4x4x4 grid and six folds is 384 backtests, and a request
that asks for that should be told no here rather than timing out on Render.
"""

import logging
from typing import Any, Dict, List, Optional

import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, model_validator

from app import symbols as symbol_master
from app.engine import robustness
from app.engine.broker import CostModel
from app.engine.feed import frame_from_yfinance
from app.engine.runner import BacktestError, run_symbol
from app.engine.sizer import build_sizer
from app.engine.strategies import STRATEGIES, build_strategy, strategy_catalogue

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/engine", tags=["Backtesting v2"])

# A full grid search is quadratic in a hurry. 200 combinations at roughly
# 50ms each is ten seconds, which is the most a synchronous request should
# spend before the platform's own timeout becomes the error message.
MAX_GRID_COMBINATIONS = 200
MAX_PERMUTATIONS = 5000


class CostConfig(BaseModel):
    brokerage_pct: float = Field(0.0003, ge=0, le=0.02)
    brokerage_cap: float = Field(20.0, ge=0)
    stt_pct: float = Field(0.001, ge=0, le=0.02)
    slippage_pct: float = Field(0.0005, ge=0, le=0.05)

    def to_model(self) -> CostModel:
        return CostModel(
            brokerage_pct=self.brokerage_pct,
            brokerage_cap=self.brokerage_cap,
            stt_pct=self.stt_pct,
            slippage_pct=self.slippage_pct,
        )


class SizerConfig(BaseModel):
    name: str = Field("percent", description="fixed | percent | volatility | kelly")
    params: Dict[str, Any] = Field(default_factory=dict)


class RunRequest(BaseModel):
    symbol: str
    start: str = Field(..., description="YYYY-MM-DD")
    end: str = Field(..., description="YYYY-MM-DD")
    strategy: str = "rsi"
    params: Dict[str, Any] = Field(default_factory=dict)
    initial_capital: float = Field(100_000.0, gt=1000)
    sizer: SizerConfig = Field(default_factory=SizerConfig)
    costs: CostConfig = Field(default_factory=CostConfig)
    permutation_test: bool = Field(
        False, description="Also run a Monte Carlo permutation test on the result"
    )
    permutations: int = Field(1000, ge=100, le=MAX_PERMUTATIONS)

    @model_validator(mode="after")
    def check_window(self) -> "RunRequest":
        if pd.Timestamp(self.start) >= pd.Timestamp(self.end):
            raise ValueError("`start` must be before `end`.")
        return self


class WalkForwardRequest(BaseModel):
    symbol: str
    start: str
    end: str
    strategy: str = "rsi"
    ranges: Dict[str, List[Any]] = Field(
        default_factory=dict,
        description="Parameter grid; empty uses the strategy catalogue's defaults",
    )
    folds: int = Field(4, ge=2, le=8)
    in_sample_ratio: float = Field(0.7, ge=0.4, le=0.9)
    objective: str = Field("sharpe", description="sharpe | sortino | calmar | total_return | sqn")
    initial_capital: float = Field(100_000.0, gt=1000)
    sizer: SizerConfig = Field(default_factory=SizerConfig)
    costs: CostConfig = Field(default_factory=CostConfig)


def resolve(symbol: str) -> str:
    """Canonical NSE symbol to a yfinance ticker, rejecting unknown names."""
    yf_symbol = symbol_master.to_yfinance(symbol)
    if yf_symbol:
        return yf_symbol
    probe = symbol.strip().upper()
    if probe.endswith((".NS", ".BO")):
        return probe
    raise HTTPException(
        status_code=404,
        detail=f"Unknown symbol {symbol!r}. Search /api/stocks/lookup for a valid one.",
    )


def build_sizer_or_400(config: SizerConfig):
    try:
        return build_sizer(config.name, **config.params)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=f"Bad sizer configuration: {exc}")


def default_ranges(strategy: str) -> Dict[str, List[Any]]:
    for entry in strategy_catalogue():
        if entry["name"] == strategy:
            return {k: list(v) for k, v in entry["ranges"].items()}
    return {}


def grid_size(ranges: Dict[str, List[Any]]) -> int:
    size = 1
    for values in ranges.values():
        size *= max(1, len(values))
    return size


@router.get("/strategies")
def list_strategies():
    """Every strategy with its defaults, tunable ranges and family."""
    return {"count": len(STRATEGIES), "strategies": strategy_catalogue()}


@router.post("/run")
def run_backtest_v2(request: RunRequest):
    """Run one backtest with next-bar-open fills and full cost modelling."""
    if request.strategy not in STRATEGIES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown strategy {request.strategy!r}. Known: {', '.join(sorted(STRATEGIES))}",
        )

    try:
        result = run_symbol(
            symbol=resolve(request.symbol),
            start=request.start,
            end=request.end,
            strategy_name=request.strategy,
            strategy_params=request.params,
            initial_capital=request.initial_capital,
            sizer=build_sizer_or_400(request.sizer),
            cost_model=request.costs.to_model(),
        )
    except BacktestError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except ValueError as exc:
        # frame_from_yfinance raises this when upstream returned nothing. No
        # synthetic series is substituted — that is the whole point.
        raise HTTPException(status_code=502, detail=str(exc))
    except Exception as exc:
        logger.exception("Backtest v2 failed for %s", request.symbol)
        raise HTTPException(status_code=500, detail=f"Backtest failed: {exc}")

    if request.permutation_test:
        result["permutation_test"] = robustness.permutation_test(
            robustness.returns_from_equity(result["equity_curve"]),
            permutations=request.permutations,
        )
    return result


@router.post("/walk-forward")
def walk_forward(request: WalkForwardRequest):
    """Optimise in-sample, measure out-of-sample, fold by fold.

    The only performance number in this system that was never fitted to the
    data it is measured on.
    """
    if request.strategy not in STRATEGIES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown strategy {request.strategy!r}. Known: {', '.join(sorted(STRATEGIES))}",
        )

    ranges = request.ranges or default_ranges(request.strategy)
    if not ranges:
        raise HTTPException(
            status_code=400,
            detail=f"No parameter ranges given and none in the catalogue for {request.strategy!r}.",
        )

    combinations = grid_size(ranges)
    if combinations * request.folds > MAX_GRID_COMBINATIONS * 4:
        raise HTTPException(
            status_code=400,
            detail=(
                f"{combinations} parameter combinations across {request.folds} folds "
                f"is {combinations * request.folds} backtests, past the "
                f"{MAX_GRID_COMBINATIONS * 4} limit for a synchronous request. "
                "Narrow the ranges or reduce folds."
            ),
        )

    yf_symbol = resolve(request.symbol)
    try:
        strategy = build_strategy(request.strategy)
        frame = frame_from_yfinance(
            yf_symbol, request.start, request.end, warmup_days=max(400, strategy.warmup * 2)
        )
        result = robustness.walk_forward(
            symbol=yf_symbol,
            frame=frame,
            strategy_name=request.strategy,
            ranges=ranges,
            folds=request.folds,
            in_sample_ratio=request.in_sample_ratio,
            objective=request.objective,
            initial_capital=request.initial_capital,
            sizer=build_sizer_or_400(request.sizer),
            cost_model=request.costs.to_model(),
        )
    except BacktestError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    except Exception as exc:
        logger.exception("Walk-forward failed for %s", request.symbol)
        raise HTTPException(status_code=500, detail=f"Walk-forward failed: {exc}")

    result["symbol"] = request.symbol
    result["strategy"] = request.strategy
    result["grid_combinations"] = combinations
    return result


@router.post("/permutation-test")
def permutation(
    request: RunRequest,
    permutations: int = Query(1000, ge=100, le=MAX_PERMUTATIONS),
):
    """Run a backtest, then ask whether its edge survives shuffling."""
    result = run_backtest_v2(request)
    return {
        "symbol": request.symbol,
        "strategy": request.strategy,
        "performance": result["performance"],
        "permutation_test": robustness.permutation_test(
            robustness.returns_from_equity(result["equity_curve"]),
            permutations=permutations,
        ),
    }
