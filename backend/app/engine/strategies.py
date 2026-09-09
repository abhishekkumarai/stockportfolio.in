"""The bundled strategy library.

Six strategies covering the two families that behave differently enough to be
worth comparing: trend-following (SMA cross, MACD, Supertrend, momentum) and
mean-reversion (RSI, Bollinger). Every one is deliberately simple — the point
of this engine is honest measurement, and a strategy with fourteen parameters
would mostly measure how hard the walk-forward optimiser tried.

Each declares `warmup`, the number of bars before its signals mean anything.
The runner will not trade before then, so a 200-day moving average does not
generate a "cross" on day three off half-formed data.
"""

import logging
from typing import Any, Dict, List, Type

import numpy as np

from app.engine.feed import DataFeed
from app.engine.strategy import (
    Context,
    Strategy,
    atr,
    bollinger,
    ema,
    macd,
    rsi,
    sma,
    supertrend,
)

logger = logging.getLogger(__name__)


class RSIStrategy(Strategy):
    """Buy oversold, sell overbought. The canonical mean-reversion baseline."""

    name = "rsi"
    warmup = 30

    def __init__(self, period: int = 14, oversold: float = 30.0, overbought: float = 70.0,
                 stop_atr: float = 2.5, **kwargs):
        super().__init__(period=period, oversold=oversold, overbought=overbought,
                         stop_atr=stop_atr, **kwargs)
        self.period = period
        self.oversold = oversold
        self.overbought = overbought
        self.stop_atr = stop_atr

    def prepare(self, feed: DataFeed) -> None:
        close = feed.frame["Close"].to_numpy(dtype="float64")
        feed.add_line("rsi", rsi(close, self.period))
        feed.add_line(
            "atr",
            atr(
                feed.frame["High"].to_numpy(dtype="float64"),
                feed.frame["Low"].to_numpy(dtype="float64"),
                close,
            ),
        )

    def next(self, context: Context) -> None:
        if not context.ready("rsi"):
            return
        value = context.value("rsi")

        if not context.in_market and value < self.oversold:
            quantity = self.size_for(context)
            if quantity > 0:
                context.buy(quantity, f"RSI {value:.1f} below {self.oversold:.0f}")
                atr_now = context.value("atr")
                if atr_now == atr_now and self.stop_atr:
                    context.set_stop(price=context.close[0] - atr_now * self.stop_atr)
        elif context.in_market and value > self.overbought:
            context.sell(reason=f"RSI {value:.1f} above {self.overbought:.0f}")


class SMACrossStrategy(Strategy):
    """Golden/death cross on two simple moving averages."""

    name = "sma_cross"
    warmup = 60

    def __init__(self, fast: int = 20, slow: int = 50, **kwargs):
        if fast >= slow:
            raise ValueError("The fast period must be shorter than the slow one.")
        super().__init__(fast=fast, slow=slow, **kwargs)
        self.fast = fast
        self.slow = slow
        self.warmup = slow + 5

    def prepare(self, feed: DataFeed) -> None:
        close = feed.frame["Close"].to_numpy(dtype="float64")
        feed.add_line("fast", sma(close, self.fast))
        feed.add_line("slow", sma(close, self.slow))
        feed.add_line(
            "atr",
            atr(
                feed.frame["High"].to_numpy(dtype="float64"),
                feed.frame["Low"].to_numpy(dtype="float64"),
                close,
            ),
        )

    def next(self, context: Context) -> None:
        if not context.ready("fast", "slow"):
            return
        fast_now, fast_prev = context.value("fast", 0), context.value("fast", 1)
        slow_now, slow_prev = context.value("slow", 0), context.value("slow", 1)
        if fast_prev != fast_prev or slow_prev != slow_prev:
            return  # previous bar still warming up

        crossed_up = fast_prev <= slow_prev and fast_now > slow_now
        crossed_down = fast_prev >= slow_prev and fast_now < slow_now

        if crossed_up and not context.in_market:
            quantity = self.size_for(context)
            if quantity > 0:
                context.buy(quantity, f"{self.fast}/{self.slow} SMA golden cross")
        elif crossed_down and context.in_market:
            context.sell(reason=f"{self.fast}/{self.slow} SMA death cross")


class MACDStrategy(Strategy):
    """MACD line crossing its signal line, gated on the histogram's sign."""

    name = "macd"
    warmup = 40

    def __init__(self, fast: int = 12, slow: int = 26, signal: int = 9, **kwargs):
        super().__init__(fast=fast, slow=slow, signal=signal, **kwargs)
        self.fast, self.slow, self.signal = fast, slow, signal

    def prepare(self, feed: DataFeed) -> None:
        close = feed.frame["Close"].to_numpy(dtype="float64")
        line, signal_line, histogram = macd(close, self.fast, self.slow, self.signal)
        feed.add_line("macd", line)
        feed.add_line("macd_signal", signal_line)
        feed.add_line("macd_hist", histogram)
        feed.add_line(
            "atr",
            atr(
                feed.frame["High"].to_numpy(dtype="float64"),
                feed.frame["Low"].to_numpy(dtype="float64"),
                close,
            ),
        )

    def next(self, context: Context) -> None:
        histogram_now = context.value("macd_hist", 0)
        histogram_prev = context.value("macd_hist", 1)
        if histogram_now != histogram_now or histogram_prev != histogram_prev:
            return

        if not context.in_market and histogram_prev <= 0 < histogram_now:
            quantity = self.size_for(context)
            if quantity > 0:
                context.buy(quantity, "MACD histogram turned positive")
        elif context.in_market and histogram_prev >= 0 > histogram_now:
            context.sell(reason="MACD histogram turned negative")


class BollingerReversionStrategy(Strategy):
    """Buy a close below the lower band, exit back at the middle band."""

    name = "bollinger"
    warmup = 30

    def __init__(self, period: int = 20, num_std: float = 2.0, **kwargs):
        super().__init__(period=period, num_std=num_std, **kwargs)
        self.period, self.num_std = period, num_std
        self.warmup = period + 5

    def prepare(self, feed: DataFeed) -> None:
        close = feed.frame["Close"].to_numpy(dtype="float64")
        upper, middle, lower = bollinger(close, self.period, self.num_std)
        feed.add_line("bb_upper", upper)
        feed.add_line("bb_middle", middle)
        feed.add_line("bb_lower", lower)
        feed.add_line(
            "atr",
            atr(
                feed.frame["High"].to_numpy(dtype="float64"),
                feed.frame["Low"].to_numpy(dtype="float64"),
                close,
            ),
        )

    def next(self, context: Context) -> None:
        if not context.ready("bb_lower", "bb_middle"):
            return
        price = context.close[0]

        if not context.in_market and price < context.value("bb_lower"):
            quantity = self.size_for(context)
            if quantity > 0:
                context.buy(quantity, "Close below the lower Bollinger band")
        elif context.in_market and price >= context.value("bb_middle"):
            context.sell(reason="Reverted to the middle Bollinger band")


class SupertrendStrategy(Strategy):
    """Long while Supertrend is up, flat when it flips down."""

    name = "supertrend"
    warmup = 30

    def __init__(self, period: int = 10, multiplier: float = 3.0, **kwargs):
        super().__init__(period=period, multiplier=multiplier, **kwargs)
        self.period, self.multiplier = period, multiplier

    def prepare(self, feed: DataFeed) -> None:
        high = feed.frame["High"].to_numpy(dtype="float64")
        low = feed.frame["Low"].to_numpy(dtype="float64")
        close = feed.frame["Close"].to_numpy(dtype="float64")
        line, direction = supertrend(high, low, close, self.period, self.multiplier)
        feed.add_line("supertrend", line)
        feed.add_line("supertrend_dir", direction)
        feed.add_line("atr", atr(high, low, close))

    def next(self, context: Context) -> None:
        direction_now = context.value("supertrend_dir", 0)
        direction_prev = context.value("supertrend_dir", 1)

        if not context.in_market and direction_prev <= 0 < direction_now:
            quantity = self.size_for(context)
            if quantity > 0:
                context.buy(quantity, "Supertrend flipped bullish")
        elif context.in_market and direction_prev >= 0 > direction_now:
            context.sell(reason="Supertrend flipped bearish")


class MomentumStrategy(Strategy):
    """Buy strength: price above its long average and up over the lookback.

    The closest thing here to a factor strategy, and included because momentum
    is the one anomaly that has survived the most out-of-sample scrutiny in
    Indian equities.
    """

    name = "momentum"
    warmup = 210

    def __init__(self, lookback: int = 126, trend: int = 200, exit_lookback: int = 63, **kwargs):
        super().__init__(lookback=lookback, trend=trend, exit_lookback=exit_lookback, **kwargs)
        self.lookback, self.trend, self.exit_lookback = lookback, trend, exit_lookback
        self.warmup = max(trend, lookback) + 10

    def prepare(self, feed: DataFeed) -> None:
        close = feed.frame["Close"].to_numpy(dtype="float64")
        feed.add_line("trend_ma", sma(close, self.trend))
        feed.add_line("momentum", _pct_change(close, self.lookback))
        feed.add_line("exit_momentum", _pct_change(close, self.exit_lookback))
        feed.add_line(
            "atr",
            atr(
                feed.frame["High"].to_numpy(dtype="float64"),
                feed.frame["Low"].to_numpy(dtype="float64"),
                close,
            ),
        )

    def next(self, context: Context) -> None:
        if not context.ready("trend_ma", "momentum"):
            return
        price = context.close[0]
        above_trend = price > context.value("trend_ma")
        momentum = context.value("momentum")

        if not context.in_market and above_trend and momentum > 0:
            quantity = self.size_for(context)
            if quantity > 0:
                context.buy(quantity, f"{self.lookback}-bar momentum +{momentum*100:.1f}% above trend")
                context.set_stop(trailing_pct=0.15)
        elif context.in_market and (not above_trend or context.value("exit_momentum") < 0):
            context.sell(reason="Momentum faded or price lost the long-term average")


def _pct_change(values: np.ndarray, periods: int) -> np.ndarray:
    """Fractional change over `periods` bars, NaN during warm-up."""
    out = np.full(len(values), np.nan)
    if periods < len(values):
        past = values[:-periods]
        out[periods:] = np.where(past != 0, (values[periods:] - past) / past, np.nan)
    return out


STRATEGIES: Dict[str, Type[Strategy]] = {
    "rsi": RSIStrategy,
    "sma_cross": SMACrossStrategy,
    "macd": MACDStrategy,
    "bollinger": BollingerReversionStrategy,
    "supertrend": SupertrendStrategy,
    "momentum": MomentumStrategy,
}

# The v1 API accepted these names; keeping the aliases means /api/backtest and
# its frontend page keep working unchanged.
LEGACY_ALIASES = {
    "RSI": "rsi",
    "SMA_Crossover": "sma_cross",
    "Hybrid": "macd",
}


def build_strategy(name: str, **params: Any) -> Strategy:
    key = LEGACY_ALIASES.get(name, name).lower()
    factory = STRATEGIES.get(key)
    if factory is None:
        raise ValueError(
            f"Unknown strategy {name!r}. Known: {', '.join(sorted(STRATEGIES))}"
        )
    return factory(**params)


def strategy_catalogue() -> List[Dict[str, Any]]:
    """Names, defaults and tunable ranges — for the UI and the optimiser."""
    return [
        {
            "name": "rsi",
            "label": "RSI mean reversion",
            "family": "mean_reversion",
            "params": {"period": 14, "oversold": 30.0, "overbought": 70.0},
            "ranges": {"period": [7, 14, 21], "oversold": [20, 25, 30, 35],
                       "overbought": [65, 70, 75, 80]},
        },
        {
            "name": "sma_cross",
            "label": "SMA crossover",
            "family": "trend",
            "params": {"fast": 20, "slow": 50},
            "ranges": {"fast": [10, 20, 50], "slow": [50, 100, 200]},
        },
        {
            "name": "macd",
            "label": "MACD histogram",
            "family": "trend",
            "params": {"fast": 12, "slow": 26, "signal": 9},
            "ranges": {"fast": [8, 12], "slow": [21, 26], "signal": [5, 9]},
        },
        {
            "name": "bollinger",
            "label": "Bollinger reversion",
            "family": "mean_reversion",
            "params": {"period": 20, "num_std": 2.0},
            "ranges": {"period": [14, 20, 30], "num_std": [1.5, 2.0, 2.5]},
        },
        {
            "name": "supertrend",
            "label": "Supertrend",
            "family": "trend",
            "params": {"period": 10, "multiplier": 3.0},
            "ranges": {"period": [7, 10, 14], "multiplier": [2.0, 3.0, 4.0]},
        },
        {
            "name": "momentum",
            "label": "Momentum rotation",
            "family": "trend",
            "params": {"lookback": 126, "trend": 200, "exit_lookback": 63},
            "ranges": {"lookback": [63, 126, 252], "trend": [100, 200]},
        },
    ]
