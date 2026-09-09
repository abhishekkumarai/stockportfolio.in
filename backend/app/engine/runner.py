"""The run loop — the engine's equivalent of backtrader's Cerebro.

The order of operations inside one bar is the whole design, and it is what
makes the results honest:

    1. Advance the cursor to bar i. The strategy can now see bars 0..i.
    2. Fill orders queued at bar i-1, at *this* bar's open plus slippage.
    3. Check stops and targets against this bar's high and low.
    4. Run the strategy, which may queue orders — for bar i+1's open.
    5. Mark the account to this bar's close and record the equity point.

Steps 2 and 4 being on opposite sides of the strategy call is the entire
difference from the v1 backtester, which decided and filled at the same close.

The warm-up window is fetched and used for indicators but never traded. It is
trimmed by *skipping* those bars in the loop rather than by slicing the frame,
because slicing would shorten the arrays the indicators were computed over and
silently shift every line by the warm-up length.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence

import pandas as pd

from app.engine import analyzers
from app.engine.broker import Broker, CostModel, Side
from app.engine.feed import DataFeed, frame_from_yfinance
from app.engine.sizer import PercentSizer, Sizer
from app.engine.strategies import build_strategy
from app.engine.strategy import Context, Strategy

logger = logging.getLogger(__name__)


class BacktestError(RuntimeError):
    """Raised when a backtest cannot run. Never satisfied with fake data."""


def run(
    feeds: Sequence[DataFeed],
    strategy: Strategy,
    initial_capital: float = 100_000.0,
    sizer: Optional[Sizer] = None,
    cost_model: Optional[CostModel] = None,
    start_index: Optional[int] = None,
    risk_free: float = analyzers.DEFAULT_RISK_FREE,
    close_at_end: bool = True,
) -> Dict[str, Any]:
    """Run one strategy over one or more feeds and return the full result.

    Multi-feed runs share a single cash balance, so a portfolio strategy
    competes with itself for capital exactly as it would in a real account.
    """
    if not feeds:
        raise BacktestError("No data feeds supplied.")

    strategy.sizer = sizer or PercentSizer(0.95)
    broker = Broker(initial_capital, cost_model)
    by_symbol = {feed.symbol: feed for feed in feeds}

    for feed in feeds:
        strategy.prepare(feed)

    # Bars are aligned on the longest feed's timestamps. Single-symbol runs —
    # which is everything the API exposes today — are the trivial case.
    primary = max(feeds, key=len)
    total_bars = len(primary)
    first_tradeable = start_index if start_index is not None else strategy.warmup
    first_tradeable = max(0, min(first_tradeable, total_bars - 1))

    if total_bars - first_tradeable < 5:
        raise BacktestError(
            f"Only {total_bars - first_tradeable} tradeable bars after a "
            f"{first_tradeable}-bar warm-up. Widen the date range."
        )

    # Entry dates per symbol, so a closed trade reports when it actually
    # opened. The broker records fills but does not track entry timestamps
    # across a position's life.
    entry_dates: Dict[str, datetime] = {}

    for index in range(total_bars):
        for feed in feeds:
            if index < len(feed):
                feed.seek(index)

        if index < first_tradeable:
            continue

        filled = broker.execute_pending(by_symbol, index)
        for order in filled:
            if order.side is Side.BUY:
                entry_dates.setdefault(order.symbol, order.fill_timestamp)
            else:
                entry_dates.pop(order.symbol, None)

        broker.check_protective_exits(by_symbol, index)

        timestamp = primary.bar_at(index).timestamp
        equity = broker.cash + sum(
            position.market_value(by_symbol[symbol].bar_at(index).close)
            for symbol, position in broker.positions.items()
            if position.is_open and index < len(by_symbol[symbol])
        )

        for feed in feeds:
            if index >= len(feed):
                continue
            strategy.next(Context(feed=feed, broker=broker, bar_index=index, equity=equity))

        broker.mark_to_market(by_symbol, index, timestamp)

    last_index = total_bars - 1
    strategy.stop(
        Context(feed=primary, broker=broker, bar_index=last_index, equity=broker.equity)
    )

    if close_at_end:
        # Mark open positions out at the final close so the reported return is
        # what the account is actually worth, not book value plus a hope.
        for symbol, position in list(broker.positions.items()):
            if not position.is_open:
                continue
            feed = by_symbol[symbol]
            bar = feed.bar_at(min(last_index, len(feed) - 1))
            order = broker.submit(symbol, Side.SELL, position.quantity, last_index,
                                  "End of backtest: marked out at the final close")
            if order is not None:
                broker.pending.remove(order)
                broker._fill_sell(order, bar.close, bar, last_index)
        if broker.equity_curve:
            broker.equity_curve[-1] = broker.cash

    # Repair entry dates on trades: the broker stamps the exit bar for both
    # ends because it does not carry position history.
    for trade in broker.trades:
        recorded = entry_dates.get(trade.symbol)
        if recorded is not None and trade.entry_index < trade.exit_index:
            trade.entry_date = recorded

    performance = analyzers.analyse(
        broker.equity_curve, broker.cash_curve, broker.equity_dates,
        broker.trades, initial_capital, risk_free,
    )
    benchmark = analyzers.buy_and_hold(
        [primary.bar_at(i).close for i in range(first_tradeable, total_bars)],
        [primary.bar_at(i).timestamp for i in range(first_tradeable, total_bars)],
        initial_capital, risk_free,
    )

    return {
        "strategy": strategy.describe(),
        "symbol": primary.symbol,
        "bars": total_bars,
        "warmup_bars": first_tradeable,
        "tradeable_bars": total_bars - first_tradeable,
        "performance": performance,
        "benchmark": benchmark,
        "alpha_vs_buy_hold_pct": (
            round(performance["total_return_pct"] - benchmark["total_return_pct"], 2)
            if performance.get("total_return_pct") is not None
            and benchmark.get("total_return_pct") is not None
            else None
        ),
        "equity_curve": [
            {"date": date.isoformat(), "equity": round(value, 2), "cash": round(cash, 2)}
            for date, value, cash in zip(
                broker.equity_dates, broker.equity_curve, broker.cash_curve
            )
        ],
        "trades": [trade.as_dict() for trade in broker.trades],
        "orders": [order.as_dict() for order in broker.orders],
        "final_cash": round(broker.cash, 2),
        "open_positions": [
            {"symbol": p.symbol, "quantity": p.quantity, "avg_cost": round(p.avg_cost, 2)}
            for p in broker.open_positions()
        ],
    }


def run_symbol(
    symbol: str,
    start: str,
    end: str,
    strategy_name: str = "rsi",
    strategy_params: Optional[Dict[str, Any]] = None,
    initial_capital: float = 100_000.0,
    sizer: Optional[Sizer] = None,
    cost_model: Optional[CostModel] = None,
    frame: Optional[pd.DataFrame] = None,
) -> Dict[str, Any]:
    """Fetch, build and run in one call. The route-facing entry point.

    Pass `frame` to run against an already-loaded DataFrame — that is how the
    tests avoid the network, and how walk-forward reuses one download across
    dozens of folds instead of refetching per fold.
    """
    strategy = build_strategy(strategy_name, **(strategy_params or {}))

    if frame is None:
        frame = frame_from_yfinance(symbol, start, end, warmup_days=max(400, strategy.warmup * 2))

    feed = DataFeed(symbol, frame)

    # The warm-up bars are those before the requested start date; the strategy
    # additionally needs its own indicator warm-up on top.
    start_timestamp = pd.Timestamp(start)
    timestamps = feed.timestamps()
    window_start = next(
        (i for i, timestamp in enumerate(timestamps) if timestamp >= start_timestamp),
        0,
    )
    first_tradeable = max(window_start, strategy.warmup)

    return run(
        [feed], strategy, initial_capital=initial_capital, sizer=sizer,
        cost_model=cost_model, start_index=first_tradeable,
    )
