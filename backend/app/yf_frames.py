"""One place that knows what shape `yfinance.download` actually returned.

Five call sites batch-download prices with `group_by="ticker"`, and every one
of them used to assume that a single-ticker request comes back with plain
columns (`Open`, `High`, `Close`, …) while a multi-ticker request comes back
with a `(ticker, field)` MultiIndex. That assumption is wrong on current
yfinance: with `group_by="ticker"` the MultiIndex is returned *regardless of
how many tickers were asked for*, so `data["Close"]` raises `KeyError` on a
one-symbol download.

The failure was quiet everywhere it was caught (a holding silently lost its
price) and loud in one place: `quant/prices.fetch_closes` built an empty frame,
whose `RangeIndex` has no `.tz`, and the regime endpoint 500ed.

Both layouts are handled here so no caller has to care, and none of them has to
count tickers to decide.
"""

from typing import Optional

import pandas as pd


def ticker_frame(data: Optional[pd.DataFrame], ticker: str) -> Optional[pd.DataFrame]:
    """The OHLCV frame for one ticker, whichever layout `data` came back in.

    Returns None when the download carried nothing for that ticker, which is a
    normal outcome for a delisted or mistyped symbol and is handled by the
    caller rather than raised.
    """
    if data is None or not isinstance(data, pd.DataFrame) or data.empty:
        return None

    if isinstance(data.columns, pd.MultiIndex):
        if ticker in data.columns.get_level_values(0):
            frame = data[ticker]
            return frame if isinstance(frame, pd.DataFrame) and not frame.empty else None
        # A MultiIndex that does not carry this ticker at all.
        return None

    # Plain columns: a single-ticker download without `group_by`.
    return data if "Close" in data.columns else None


def close_series(data: Optional[pd.DataFrame], ticker: str) -> Optional[pd.Series]:
    """The adjusted close series for one ticker, or None if absent."""
    frame = ticker_frame(data, ticker)
    if frame is None or "Close" not in frame.columns:
        return None
    series = frame["Close"].dropna()
    return series if len(series) else None
