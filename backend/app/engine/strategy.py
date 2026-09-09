"""The Strategy base class and the context it is given each bar.

A strategy sees exactly one thing: a `Context` built from the feed's cursor
position. It can read indicator lines backwards, ask about its own position,
and submit `buy`/`sell` orders — which are queued for the *next* bar's open.
It cannot read a bar index, cannot reach into the DataFrame, and cannot fill
an order itself. Look-ahead is not forbidden by convention here; there is no
API through which to express it.

`prepare()` runs once before the first bar and is where indicators are
attached to the feed. It computes over the whole series for speed — a rolling
mean in numpy is orders of magnitude faster than recomputing it 2,000 times —
but the result becomes a `Line`, which is cursor-bound, so precomputation buys
speed without buying foresight.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from app.engine.broker import Broker, Position, Side
from app.engine.feed import DataFeed, Line

logger = logging.getLogger(__name__)


@dataclass
class Context:
    """What a strategy is allowed to know at one bar."""

    feed: DataFeed
    broker: Broker
    bar_index: int
    equity: float

    @property
    def symbol(self) -> str:
        return self.feed.symbol

    @property
    def close(self) -> Line:
        return self.feed.close

    @property
    def position(self) -> Position:
        return self.broker.position(self.feed.symbol)

    @property
    def in_market(self) -> bool:
        return self.position.is_open

    @property
    def cash(self) -> float:
        return self.broker.cash

    def line(self, name: str) -> Line:
        line = self.feed.lines.get(name)
        if line is None:
            raise KeyError(
                f"Indicator {name!r} was not attached in prepare(). "
                f"Available: {', '.join(sorted(self.feed.lines))}"
            )
        return line

    def value(self, name: str, ago: int = 0) -> float:
        return self.line(name)[ago]

    def ready(self, *names: str) -> bool:
        """True when every named indicator has a real value at this bar."""
        return all(self.line(name).ready for name in names)

    def buy(self, quantity: float, reason: str = "") -> None:
        self.broker.submit(self.symbol, Side.BUY, quantity, self.bar_index, reason)

    def sell(self, quantity: Optional[float] = None, reason: str = "") -> None:
        quantity = self.position.quantity if quantity is None else quantity
        if quantity > 0:
            self.broker.submit(self.symbol, Side.SELL, quantity, self.bar_index, reason)

    def set_stop(self, price: Optional[float] = None, trailing_pct: Optional[float] = None,
                 take_profit: Optional[float] = None) -> None:
        position = self.position
        if price is not None:
            position.stop_loss = price
        if trailing_pct is not None:
            position.trailing_pct = trailing_pct
        if take_profit is not None:
            position.take_profit = take_profit


class Strategy:
    """Subclass this. Override `prepare` to attach indicators, `next` to trade."""

    name = "strategy"
    # Bars of warm-up the strategy needs before its signals mean anything.
    # The runner refuses to trade before this many bars have passed.
    warmup = 0

    def __init__(self, **params: Any):
        self.params = params
        self.sizer = None  # injected by the runner

    def prepare(self, feed: DataFeed) -> None:
        """Attach indicator lines. Called once, before the first bar."""

    def next(self, context: Context) -> None:
        """Called once per tradeable bar. Submit orders through the context."""
        raise NotImplementedError

    def stop(self, context: Context) -> None:
        """Called after the final bar, before open positions are marked out."""

    # ---- helpers for subclasses -----------------------------------------

    def size_for(self, context: Context, atr_name: str = "atr") -> int:
        """Ask the injected sizer how many shares to buy at this bar's close.

        Sizing off the current close is a deliberate approximation: the fill
        happens at tomorrow's open, which is not knowable yet. The broker
        shrinks the order if the gap makes it unaffordable.
        """
        if self.sizer is None:
            return 0
        price = context.close[0]
        atr = context.feed.lines[atr_name][0] if atr_name in context.feed.lines else None
        return self.sizer.size(context.cash, context.equity, price, atr)

    def describe(self) -> Dict[str, Any]:
        return {"name": self.name, "params": self.params, "warmup": self.warmup}


# ---- indicator helpers used by the bundled strategies --------------------
# Kept here rather than imported from app.technicals because that module is
# built around "the latest value of a snapshot dict", while the engine needs
# whole arrays aligned to the feed. The formulas are the same.


def sma(values: np.ndarray, period: int) -> np.ndarray:
    return pd.Series(values).rolling(period, min_periods=period).mean().to_numpy()


def ema(values: np.ndarray, period: int) -> np.ndarray:
    return pd.Series(values).ewm(span=period, adjust=False).mean().to_numpy()


def rsi(values: np.ndarray, period: int = 14) -> np.ndarray:
    series = pd.Series(values)
    delta = series.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    out = 100.0 - (100.0 / (1.0 + rs))
    # Leave the warm-up window as NaN so `Line.ready` reports honestly instead
    # of the strategy trading a filled-in 50 on day two.
    out.iloc[:period] = np.nan
    return out.to_numpy()


def atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
    high_series, low_series = pd.Series(high), pd.Series(low)
    prev_close = pd.Series(close).shift(1)
    true_range = pd.concat(
        [
            high_series - low_series,
            (high_series - prev_close).abs(),
            (low_series - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return true_range.ewm(alpha=1 / period, adjust=False).mean().to_numpy()


def macd(values: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9):
    line = ema(values, fast) - ema(values, slow)
    signal_line = pd.Series(line).ewm(span=signal, adjust=False).mean().to_numpy()
    return line, signal_line, line - signal_line


def bollinger(values: np.ndarray, period: int = 20, num_std: float = 2.0):
    series = pd.Series(values)
    middle = series.rolling(period, min_periods=period).mean()
    deviation = series.rolling(period, min_periods=period).std()
    upper = middle + deviation * num_std
    lower = middle - deviation * num_std
    return upper.to_numpy(), middle.to_numpy(), lower.to_numpy()


def supertrend(high: np.ndarray, low: np.ndarray, close: np.ndarray,
               period: int = 10, multiplier: float = 3.0):
    """Supertrend line and direction (+1 up, -1 down).

    Genuinely path-dependent — each bar's band depends on the previous bar's
    band and direction — so this is a Python loop rather than vectorised. It
    runs once per backtest, not once per bar, which makes that acceptable.
    """
    atr_values = atr(high, low, close, period)
    hl2 = (high + low) / 2.0
    upper = hl2 + multiplier * atr_values
    lower = hl2 - multiplier * atr_values

    direction = np.ones(len(close), dtype="float64")
    line = np.full(len(close), np.nan)

    for i in range(1, len(close)):
        if np.isnan(atr_values[i]):
            continue
        if close[i] > upper[i - 1]:
            direction[i] = 1.0
        elif close[i] < lower[i - 1]:
            direction[i] = -1.0
        else:
            direction[i] = direction[i - 1]
            if direction[i] > 0:
                lower[i] = max(lower[i], lower[i - 1])
            else:
                upper[i] = min(upper[i], upper[i - 1])
        line[i] = lower[i] if direction[i] > 0 else upper[i]

    return line, direction
