"""Event-driven backtesting engine (Phase 8).

Replaces the same-close-fill loop in `app.backtester` with an explicit
broker/feed/strategy/sizer/analyzer split, next-bar-open execution, realistic
Indian transaction costs, and the robustness tooling — walk-forward and
permutation testing — that separates an edge from a well-fitted curve.

`app.backtester.run_backtest` remains as a thin adapter so `/api/backtest` and
its frontend page keep working unchanged.
"""

from app.engine.broker import Broker, CostModel, Order, Position, Side, Trade
from app.engine.feed import Bar, DataFeed, Line, LookAheadError
from app.engine.runner import BacktestError, run, run_symbol
from app.engine.sizer import (
    FixedSizer,
    KellySizer,
    PercentSizer,
    VolatilityTargetSizer,
    build_sizer,
)
from app.engine.strategies import STRATEGIES, build_strategy, strategy_catalogue
from app.engine.strategy import Context, Strategy

__all__ = [
    "Bar", "Broker", "CostModel", "Context", "DataFeed", "Line", "LookAheadError",
    "Order", "Position", "Side", "Strategy", "Trade", "BacktestError",
    "FixedSizer", "KellySizer", "PercentSizer", "VolatilityTargetSizer",
    "STRATEGIES", "build_sizer", "build_strategy", "run", "run_symbol",
    "strategy_catalogue",
]
