"""Return-series assembly for the quant layer.

The optimiser, the factor regression and the regime detector all need the same
thing: an aligned frame of daily returns for a set of holdings, plus a
benchmark. Building it once here keeps the three from each inventing their own
alignment rules — and alignment is where the subtle errors live.

Two rules, both deliberate:

* **Inner join on dates, then drop any row with a gap.** A holding listed six
  months ago truncates the usable history for every other holding in the
  covariance matrix. That is the correct behaviour — a covariance estimated
  over different windows per pair is not a covariance matrix, and can fail to
  be positive semi-definite. The cost is reported so the caller can see which
  holding is doing the truncating.

* **Funds are excluded from covariance work.** An NAV series is already a
  portfolio of stocks, so mixing fund NAVs and single stocks into one optimiser
  double-counts the underlying exposure. Funds are valued and reported, but the
  optimiser sees equity only, and says so.
"""

import logging
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pandas as pd

from app import symbols as symbol_master
from app.cache import TTLCache, make_key
from app.yf_frames import close_series

logger = logging.getLogger(__name__)

# Price history for a fixed window changes once a day; six hours is a
# reasonable compromise between freshness and not refetching per request.
_PRICE_CACHE = TTLCache(ttl=21600, max_entries=32)

DEFAULT_BENCHMARK_TICKER = "^CRSLDX"  # Nifty 500


def fetch_closes(tickers: Sequence[str], period: str = "2y") -> pd.DataFrame:
    """Adjusted daily closes for a set of yfinance tickers, one batched call."""
    if not tickers:
        return pd.DataFrame()

    cache_key = make_key("closes", tuple(sorted(tickers)), period)
    cached = _PRICE_CACHE.get(cache_key)
    if cached is not None:
        return cached.copy()

    try:
        import yfinance as yf
    except ImportError:
        logger.error("yfinance unavailable; quant routes cannot fetch prices")
        return pd.DataFrame()

    unique = sorted(set(tickers))
    try:
        data = yf.download(
            unique, period=period, interval="1d", progress=False,
            auto_adjust=True, group_by="ticker", threads=True,
        )
    except Exception as exc:
        logger.warning("Price download failed: %s", exc)
        return pd.DataFrame()

    if data is None or data.empty:
        return pd.DataFrame()

    columns: Dict[str, pd.Series] = {}
    for ticker in unique:
        series = close_series(data, ticker)
        if series is not None and len(series) > 30:
            columns[ticker] = series

    frame = pd.DataFrame(columns)
    # An empty frame has a RangeIndex, which has no `.tz` at all — asking for
    # it is how a benchmark outage used to surface as a 500 instead of the
    # empty result every caller already handles.
    if getattr(frame.index, "tz", None) is not None:
        frame.index = frame.index.tz_localize(None)
    _PRICE_CACHE.set(cache_key, frame)
    return frame.copy()


def holdings_returns(
    holdings: Sequence[Dict[str, Any]], period: str = "2y"
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Aligned daily returns for the equity holdings, plus a coverage report.

    The report is not decoration. When the optimiser refuses to run because
    there are 40 overlapping observations, the useful answer is *which holding*
    caused that, and this is where it comes from.
    """
    equity = [h for h in holdings if h.get("kind") == "equity" and h.get("key")]
    if not equity:
        return pd.DataFrame(), {
            "requested": 0,
            "usable": 0,
            "excluded": [],
            "note": "No equity holdings. Fund NAVs are not used for covariance work.",
        }

    by_ticker: Dict[str, str] = {}
    unresolved: List[str] = []
    for holding in equity:
        symbol = holding["key"]
        ticker = symbol_master.to_yfinance(symbol)
        if ticker:
            by_ticker[ticker] = symbol
        else:
            unresolved.append(symbol)

    closes = fetch_closes(list(by_ticker), period)
    if closes.empty:
        return pd.DataFrame(), {
            "requested": len(equity),
            "usable": 0,
            "excluded": unresolved,
            "note": "No price history came back for any holding.",
        }

    closes = closes.rename(columns=by_ticker)
    returns = closes.pct_change()

    # Which column would cost the most history if kept.
    lengths = {column: int(returns[column].dropna().shape[0]) for column in returns.columns}
    aligned = returns.dropna(how="any")

    no_prices = [
        symbol for ticker, symbol in by_ticker.items() if symbol not in returns.columns
    ]

    report = {
        "requested": len(equity),
        "usable": len(aligned.columns),
        "observations": len(aligned),
        "excluded": unresolved + no_prices,
        "per_symbol_observations": lengths,
        "shortest_history": min(lengths, key=lengths.get) if lengths else None,
    }
    if lengths and len(aligned) < min(lengths.values()) * 0.8:
        report["note"] = (
            f"Aligning to common dates cut the usable window to {len(aligned)} "
            f"observations. {report['shortest_history']} has the shortest history "
            "and is the binding constraint."
        )
    return aligned, report


def portfolio_return_series(
    returns: pd.DataFrame, weights: Dict[str, float]
) -> pd.Series:
    """Weighted portfolio returns from per-holding returns.

    Static weights, which assumes the portfolio was rebalanced back to today's
    weights every day. It is an approximation and the honest alternative — a
    true time-weighted series — needs a transaction history that a Fyers
    holdings call does not provide. Every surface that shows this labels it.
    """
    columns = [column for column in returns.columns if column in weights]
    if not columns:
        return pd.Series(dtype="float64")
    vector = pd.Series({column: weights[column] for column in columns})
    total = vector.sum()
    if total <= 0:
        return pd.Series(dtype="float64")
    return (returns[columns] * (vector / total)).sum(axis=1)


def benchmark_series(period: str = "2y", ticker: str = DEFAULT_BENCHMARK_TICKER) -> pd.Series:
    frame = fetch_closes([ticker], period)
    if frame.empty or ticker not in frame.columns:
        return pd.Series(dtype="float64")
    return frame[ticker].dropna()


def weights_from_holdings(holdings: Sequence[Dict[str, Any]]) -> Dict[str, float]:
    """Current equity weights, renormalised to sum to 1 across equity only."""
    equity = [
        h for h in holdings
        if h.get("kind") == "equity" and (h.get("current_value") or 0) > 0
    ]
    total = sum(h["current_value"] for h in equity)
    if total <= 0:
        return {}
    return {h["key"]: h["current_value"] / total for h in equity}
