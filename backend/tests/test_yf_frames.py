"""The two layouts `yfinance.download` returns, and the empty case.

The regression these guard against: with `group_by="ticker"` a *single*-ticker
download still comes back with a `(ticker, field)` MultiIndex, so code that
special-cased one ticker with `data["Close"]` raised KeyError and silently
dropped the price — or, in `quant/prices.fetch_closes`, produced an empty frame
whose RangeIndex has no `.tz` and 500ed the regime endpoint.
"""

import pandas as pd
import pytest

from app.yf_frames import close_series, ticker_frame

DATES = pd.date_range("2026-01-01", periods=4, freq="D")


def grouped(tickers):
    """What `yf.download(..., group_by="ticker")` returns: a (ticker, field) MultiIndex."""
    columns = pd.MultiIndex.from_product([tickers, ["Open", "High", "Low", "Close", "Volume"]])
    values = [[float(i + 1)] * len(columns) for i in range(len(DATES))]
    return pd.DataFrame(values, index=DATES, columns=columns)


def flat():
    """What a download without `group_by` returns: plain field columns."""
    return pd.DataFrame(
        {"Open": [1.0, 2, 3, 4], "High": [1.0, 2, 3, 4], "Low": [1.0, 2, 3, 4],
         "Close": [10.0, 11, 12, 13], "Volume": [1, 1, 1, 1]},
        index=DATES,
    )


def test_single_ticker_grouped_download_is_found():
    data = grouped(["RELIANCE.NS"])
    frame = ticker_frame(data, "RELIANCE.NS")
    assert frame is not None
    assert "Close" in frame.columns


def test_multi_ticker_grouped_download_selects_the_right_one():
    data = grouped(["RELIANCE.NS", "TCS.NS"])
    series = close_series(data, "TCS.NS")
    assert series is not None
    assert len(series) == len(DATES)


def test_flat_download_is_accepted():
    assert close_series(flat(), "ANYTHING") is not None


def test_absent_ticker_returns_none_rather_than_raising():
    data = grouped(["RELIANCE.NS"])
    assert ticker_frame(data, "INFY.NS") is None
    assert close_series(data, "INFY.NS") is None


@pytest.mark.parametrize("data", [None, pd.DataFrame()])
def test_empty_download_returns_none(data):
    assert ticker_frame(data, "RELIANCE.NS") is None
    assert close_series(data, "RELIANCE.NS") is None


def test_all_nan_close_is_treated_as_no_data():
    frame = flat()
    frame["Close"] = float("nan")
    assert close_series(frame, "RELIANCE.NS") is None
