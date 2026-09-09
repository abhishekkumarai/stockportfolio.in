"""Data feeds, and the window that makes look-ahead bias impossible to express.

The existing `backtester.run_backtest` computes indicators over the whole
series, then loops through it deciding trades — so at bar 40 the strategy can
read `hist["Close"].iloc[100]` and nothing stops it. Every overfit backtest
starts there. The fix is not discipline; it is a data structure that has no
future in it.

`BarWindow` is that structure. It is handed to a strategy at bar `i` and can
only see bars `0..i`. Index 0 is *the current bar*, 1 is yesterday, 2 the day
before — reverse indexing, like backtrader's lines, because a strategy asks
"what was the close two bars ago", never "what was the close on bar 173".
Asking for a negative index, which is the natural way to reach forward, raises
`LookAheadError` rather than quietly wrapping around to the end of the array
the way a Python list would.

Indicators are precomputed over the full series for speed, but each is stored
as a `Line` that the window slices to `i` as well, so a 200-day moving average
cannot leak tomorrow's value either.
"""

import logging
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict, Iterator, List, Optional, Sequence

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = ("Open", "High", "Low", "Close")


class LookAheadError(RuntimeError):
    """Raised when code tries to read a bar the strategy cannot legally see."""


class Line:
    """One indicator series, addressable only up to the current bar."""

    __slots__ = ("_values", "_cursor", "name")

    def __init__(self, values: Sequence[float], name: str = ""):
        self._values = np.asarray(values, dtype="float64")
        self._cursor = 0
        self.name = name

    def _seek(self, cursor: int) -> None:
        self._cursor = cursor

    def __getitem__(self, ago: int) -> float:
        """`line[0]` is the current bar, `line[1]` the previous one."""
        if ago < 0:
            raise LookAheadError(
                f"Line {self.name!r} was asked for bar {-ago} in the future. "
                "Negative offsets are forward-looking and are never valid."
            )
        index = self._cursor - ago
        if index < 0:
            return float("nan")
        return float(self._values[index])

    def __len__(self) -> int:
        return self._cursor + 1

    @property
    def ready(self) -> bool:
        """False while the indicator is still warming up (NaN at this bar)."""
        value = self[0]
        return value == value  # NaN is the only value not equal to itself

    def history(self, count: int) -> np.ndarray:
        """The last `count` values ending at the current bar, oldest first."""
        start = max(0, self._cursor - count + 1)
        return self._values[start : self._cursor + 1]


@dataclass
class Bar:
    """One OHLCV bar, plus its position in the feed."""

    index: int
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0

    @property
    def day(self) -> date:
        return self.timestamp.date() if isinstance(self.timestamp, datetime) else self.timestamp


class DataFeed:
    """A symbol's bars plus its indicator lines, with a moving cursor.

    Construct from a DataFrame, attach indicators by name, then iterate. The
    cursor advances once per bar and every attached `Line` moves with it, so
    strategies see a consistent as-of view without any per-strategy slicing.
    """

    def __init__(self, symbol: str, frame: pd.DataFrame):
        missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
        if missing:
            raise ValueError(f"{symbol}: price frame is missing {', '.join(missing)}")

        frame = frame.dropna(subset=["Close"]).copy()
        if frame.empty:
            raise ValueError(f"{symbol}: no usable bars after dropping missing closes")
        frame = frame.sort_index()

        self.symbol = symbol
        self.frame = frame
        self._cursor = -1

        self._open = frame["Open"].to_numpy(dtype="float64")
        self._high = frame["High"].to_numpy(dtype="float64")
        self._low = frame["Low"].to_numpy(dtype="float64")
        self._close = frame["Close"].to_numpy(dtype="float64")
        self._volume = (
            frame["Volume"].to_numpy(dtype="float64")
            if "Volume" in frame.columns
            else np.zeros(len(frame))
        )
        self._timestamps = list(frame.index)

        self.lines: Dict[str, Line] = {}
        # The OHLCV series are lines too, so `data.close[1]` works the same way
        # an indicator does and obeys the same look-ahead rule.
        self.close = self.add_line("close", self._close)
        self.open = self.add_line("open", self._open)
        self.high = self.add_line("high", self._high)
        self.low = self.add_line("low", self._low)
        self.volume = self.add_line("volume", self._volume)

    def add_line(self, name: str, values: Sequence[float]) -> Line:
        if len(values) != len(self._close):
            raise ValueError(
                f"{self.symbol}: line {name!r} has {len(values)} values for "
                f"{len(self._close)} bars"
            )
        line = Line(values, name)
        line._seek(max(0, self._cursor))
        self.lines[name] = line
        return line

    def __len__(self) -> int:
        return len(self._close)

    @property
    def cursor(self) -> int:
        return self._cursor

    def seek(self, index: int) -> None:
        self._cursor = index
        for line in self.lines.values():
            line._seek(index)

    def bar_at(self, index: int) -> Bar:
        """A bar by absolute index. Internal use — the broker fills with it.

        Not exposed to strategies: taking an absolute index is exactly the
        escape hatch that reintroduces look-ahead.
        """
        return Bar(
            index=index,
            timestamp=self._timestamps[index],
            open=float(self._open[index]),
            high=float(self._high[index]),
            low=float(self._low[index]),
            close=float(self._close[index]),
            volume=float(self._volume[index]),
        )

    @property
    def current(self) -> Bar:
        return self.bar_at(self._cursor)

    def has_next(self) -> bool:
        return self._cursor + 1 < len(self._close)

    def timestamps(self) -> List[datetime]:
        return list(self._timestamps)

    def __iter__(self) -> Iterator[Bar]:
        for index in range(len(self._close)):
            self.seek(index)
            yield self.current


def frame_from_yfinance(
    symbol: str, start: Any, end: Any, warmup_days: int = 400
) -> pd.DataFrame:
    """Fetch daily bars, with warm-up history ahead of the test window.

    Indicators need history before the first traded bar or the strategy spends
    its first 200 sessions unarmed. That warm-up is fetched here and trimmed by
    the runner *after* indicators are computed, so the warm-up informs the
    indicators without ever being tradeable.

    Raises rather than fabricating a series — the same rule as everywhere else
    in this codebase, and the one the old backtester broke.
    """
    import yfinance as yf

    start_date = pd.Timestamp(start)
    fetch_from = start_date - pd.Timedelta(days=warmup_days)

    frame = yf.Ticker(symbol).history(start=fetch_from, end=pd.Timestamp(end))
    if frame is None or frame.empty:
        raise ValueError(f"No historical price data available for {symbol}.")
    if frame.index.tz is not None:
        frame.index = frame.index.tz_localize(None)
    return frame
