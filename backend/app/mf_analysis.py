"""Mutual fund analytics computed from mfapi.in NAV history.

Everything here works off a NAV series, so it applies equally to any scheme the
upstream API exposes. NAV is total-return by construction for growth plans
(dividends are reinvested into NAV), so plain price maths is valid; IDCW plans
understate returns for the same reason, which is worth remembering when comparing.
"""

import logging
import math
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from app.mfapi_client import DateLike, client, normalize_date

logger = logging.getLogger(__name__)

TRADING_DAYS = 252
DEFAULT_RISK_FREE_RATE = 0.065  # ~India 10Y G-sec, override per request.

# Trailing windows, in calendar days.
TRAILING_PERIODS = {
    "1m": 30,
    "3m": 91,
    "6m": 182,
    "1y": 365,
    "2y": 730,
    "3y": 1095,
    "5y": 1825,
    "10y": 3652,
}


def _round(value: Any, digits: int = 4) -> Optional[float]:
    """JSON-safe rounding: NaN/inf become None rather than invalid JSON."""
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return round(number, digits)


def to_series(nav_data: List[Dict[str, str]]) -> pd.Series:
    """Convert the API's [{date, nav}] list into an ascending float Series."""
    if not nav_data:
        return pd.Series(dtype="float64")

    frame = pd.DataFrame(nav_data)
    frame["date"] = pd.to_datetime(frame["date"], format="%d-%m-%Y", errors="coerce")
    frame["nav"] = pd.to_numeric(frame["nav"], errors="coerce")
    frame = frame.dropna(subset=["date", "nav"])
    # Some schemes carry placeholder zero NAVs around launch; they break ratios.
    frame = frame[frame["nav"] > 0]

    series = frame.set_index("date")["nav"].sort_index()
    return series[~series.index.duplicated(keep="last")]


def _daily(series: pd.Series) -> pd.Series:
    """Calendar-daily series with weekends/holidays forward filled.

    Needed because trailing and rolling windows are expressed in calendar days
    while NAVs only exist on business days.
    """
    if series.empty:
        return series
    return series.asfreq("D") if series.index.freq else series.resample("D").ffill()


def _cagr(start_value: float, end_value: float, days: float) -> Optional[float]:
    if start_value <= 0 or end_value <= 0 or days <= 0:
        return None
    return (end_value / start_value) ** (365.0 / days) - 1.0


def trailing_returns(series: pd.Series) -> Dict[str, Any]:
    """Point-to-point returns over standard windows.

    Windows under a year are absolute; a year and beyond are annualised (CAGR),
    which is how Indian factsheets report them.
    """
    if series.empty:
        return {}

    daily = _daily(series)
    end_date = daily.index[-1]
    end_nav = float(daily.iloc[-1])
    first_date = daily.index[0]

    out: Dict[str, Any] = {}
    for label, days in TRAILING_PERIODS.items():
        target = end_date - pd.Timedelta(days=days)
        if target < first_date:
            out[label] = None
            continue
        start_nav = float(daily.asof(target))
        absolute = end_nav / start_nav - 1.0
        annualised = days >= 365
        out[label] = {
            "return_pct": _round(absolute * 100, 2),
            "annualised": annualised,
            "cagr_pct": _round(_cagr(start_nav, end_nav, days) * 100, 2)
            if annualised
            else None,
            "start_date": target.date().isoformat(),
            "start_nav": _round(start_nav, 4),
        }

    since_days = (end_date - first_date).days
    out["since_inception"] = {
        "return_pct": _round((end_nav / float(daily.iloc[0]) - 1.0) * 100, 2),
        "annualised": since_days >= 365,
        "cagr_pct": _round((_cagr(float(daily.iloc[0]), end_nav, since_days) or 0) * 100, 2)
        if since_days >= 365
        else None,
        "start_date": first_date.date().isoformat(),
        "start_nav": _round(float(daily.iloc[0]), 4),
    }
    return out


def risk_metrics(
    series: pd.Series, risk_free_rate: float = DEFAULT_RISK_FREE_RATE
) -> Dict[str, Any]:
    """Volatility, Sharpe, Sortino and drawdown, from business-day NAV moves."""
    if len(series) < 30:
        return {"insufficient_data": True}

    returns = series.pct_change().dropna()
    if returns.empty:
        return {"insufficient_data": True}

    volatility = float(returns.std(ddof=1)) * math.sqrt(TRADING_DAYS)
    mean_annual = float(returns.mean()) * TRADING_DAYS
    excess = mean_annual - risk_free_rate

    downside = returns[returns < 0]
    downside_dev = (
        float(downside.std(ddof=1)) * math.sqrt(TRADING_DAYS)
        if len(downside) > 1
        else None
    )

    drawdown = max_drawdown(series)

    return {
        "volatility_pct": _round(volatility * 100, 2),
        "sharpe_ratio": _round(excess / volatility, 2) if volatility else None,
        "sortino_ratio": _round(excess / downside_dev, 2) if downside_dev else None,
        "risk_free_rate_pct": _round(risk_free_rate * 100, 2),
        "best_day_pct": _round(float(returns.max()) * 100, 2),
        "worst_day_pct": _round(float(returns.min()) * 100, 2),
        "positive_days_pct": _round(float((returns > 0).mean()) * 100, 1),
        "observations": int(len(returns)),
        **drawdown,
    }


def max_drawdown(series: pd.Series) -> Dict[str, Any]:
    """Deepest peak-to-trough fall, plus how far below the peak the fund sits now."""
    if series.empty:
        return {}

    running_peak = series.cummax()
    drawdowns = series / running_peak - 1.0
    trough_date = drawdowns.idxmin()
    trough_value = float(drawdowns.min())
    peak_date = series.loc[:trough_date].idxmax()

    # Recovery is the first date after the trough that regains the old peak.
    after = series.loc[trough_date:]
    recovered = after[after >= series.loc[peak_date]]
    recovery_date = recovered.index[0] if len(recovered) else None

    return {
        "max_drawdown_pct": _round(trough_value * 100, 2),
        "max_drawdown_peak_date": peak_date.date().isoformat(),
        "max_drawdown_trough_date": trough_date.date().isoformat(),
        "max_drawdown_recovery_date": recovery_date.date().isoformat()
        if recovery_date is not None
        else None,
        "max_drawdown_recovery_days": int((recovery_date - peak_date).days)
        if recovery_date is not None
        else None,
        "current_drawdown_pct": _round(float(drawdowns.iloc[-1]) * 100, 2),
    }


def rolling_returns(series: pd.Series, years: int = 3) -> Dict[str, Any]:
    """Distribution of annualised returns across every start date in the history.

    More honest than a single trailing number: it shows what an investor who
    picked a random entry day would actually have earned.
    """
    window = int(round(365.25 * years))
    daily = _daily(series)
    if len(daily) <= window:
        return {"years": years, "insufficient_data": True}

    start = daily.shift(window).dropna()
    end = daily.loc[start.index]
    growth = end / start
    annualised = growth ** (1.0 / years) - 1.0
    annualised = annualised.replace([np.inf, -np.inf], np.nan).dropna()

    if annualised.empty:
        return {"years": years, "insufficient_data": True}

    return {
        "years": years,
        "observations": int(len(annualised)),
        "average_pct": _round(float(annualised.mean()) * 100, 2),
        "median_pct": _round(float(annualised.median()) * 100, 2),
        "min_pct": _round(float(annualised.min()) * 100, 2),
        "max_pct": _round(float(annualised.max()) * 100, 2),
        "std_dev_pct": _round(float(annualised.std(ddof=1)) * 100, 2),
        "positive_windows_pct": _round(float((annualised > 0).mean()) * 100, 1),
        "above_10pct_windows_pct": _round(float((annualised > 0.10).mean()) * 100, 1),
        # The series is indexed by window *end* date, so back out the start date.
        "worst_window": _window_dates(annualised.idxmin(), window),
        "best_window": _window_dates(annualised.idxmax(), window),
    }


def _window_dates(end_stamp: pd.Timestamp, window_days: int) -> Dict[str, str]:
    return {
        "start": (end_stamp - pd.Timedelta(days=window_days)).date().isoformat(),
        "end": end_stamp.date().isoformat(),
    }


def xirr(cashflows: List[Tuple[date, float]]) -> Optional[float]:
    """Annualised money-weighted return for irregular cashflows.

    Bisection rather than Newton: slower, but it cannot diverge, and these are
    tiny problems where robustness matters more than speed.
    """
    if len(cashflows) < 2:
        return None
    flows = sorted(cashflows, key=lambda item: item[0])
    if not (any(amount < 0 for _, amount in flows) and any(amount > 0 for _, amount in flows)):
        return None

    origin = flows[0][0]

    def npv(rate: float) -> float:
        total = 0.0
        for when, amount in flows:
            years = (when - origin).days / 365.0
            total += amount / ((1.0 + rate) ** years)
        return total

    low, high = -0.9999, 10.0
    npv_low, npv_high = npv(low), npv(high)
    if npv_low * npv_high > 0:
        return None

    for _ in range(200):
        mid = (low + high) / 2.0
        value = npv(mid)
        if abs(value) < 1e-7:
            return mid
        if npv_low * value < 0:
            high, npv_high = mid, value
        else:
            low, npv_low = mid, value
    return (low + high) / 2.0


def simulate_lumpsum(
    series: pd.Series, amount: float, start: DateLike = None, end: DateLike = None
) -> Dict[str, Any]:
    """One-shot investment: buy units at the start NAV, value them at the end NAV."""
    daily = _daily(series)
    if daily.empty:
        return {"error": "No NAV data"}

    start_ts = pd.Timestamp(normalize_date(start)) if start else daily.index[0]
    end_ts = pd.Timestamp(normalize_date(end)) if end else daily.index[-1]
    start_ts = max(start_ts, daily.index[0])
    end_ts = min(end_ts, daily.index[-1])
    if start_ts >= end_ts:
        return {"error": "Start date must be before end date and within the NAV history"}

    start_nav = float(daily.asof(start_ts))
    end_nav = float(daily.asof(end_ts))
    units = amount / start_nav
    final_value = units * end_nav
    days = (end_ts - start_ts).days

    return {
        "invested": _round(amount, 2),
        "final_value": _round(final_value, 2),
        "gain": _round(final_value - amount, 2),
        "absolute_return_pct": _round((final_value / amount - 1.0) * 100, 2),
        "cagr_pct": _round((_cagr(amount, final_value, days) or 0) * 100, 2)
        if days >= 365
        else None,
        "units": _round(units, 4),
        "start_date": start_ts.date().isoformat(),
        "end_date": end_ts.date().isoformat(),
        "start_nav": _round(start_nav, 4),
        "end_nav": _round(end_nav, 4),
    }


def simulate_sip(
    series: pd.Series,
    amount: float,
    start: DateLike = None,
    end: DateLike = None,
    day_of_month: int = 1,
) -> Dict[str, Any]:
    """Monthly SIP backtest, reported as XIRR (the only fair measure for staggered flows)."""
    daily = _daily(series)
    if daily.empty:
        return {"error": "No NAV data"}

    start_ts = pd.Timestamp(normalize_date(start)) if start else daily.index[0]
    end_ts = pd.Timestamp(normalize_date(end)) if end else daily.index[-1]
    start_ts = max(start_ts, daily.index[0])
    end_ts = min(end_ts, daily.index[-1])
    if start_ts >= end_ts:
        return {"error": "Start date must be before end date and within the NAV history"}

    installment_dates = pd.date_range(
        start=start_ts, end=end_ts, freq=pd.DateOffset(months=1)
    )
    # Snap to the requested day of month, skipping months that are too short.
    snapped = []
    for stamp in installment_dates:
        day = min(day_of_month, stamp.days_in_month)
        candidate = stamp.replace(day=day)
        if daily.index[0] <= candidate <= end_ts:
            snapped.append(candidate)

    if not snapped:
        return {"error": "No SIP installments fall inside the available NAV history"}

    units = 0.0
    invested = 0.0
    cashflows: List[Tuple[date, float]] = []
    installments = []

    for when in snapped:
        nav = float(daily.asof(when))
        bought = amount / nav
        units += bought
        invested += amount
        cashflows.append((when.date(), -amount))
        installments.append(
            {"date": when.date().isoformat(), "nav": _round(nav, 4), "units": _round(bought, 4)}
        )

    end_nav = float(daily.asof(end_ts))
    final_value = units * end_nav
    cashflows.append((end_ts.date(), final_value))
    rate = xirr(cashflows)

    return {
        "monthly_amount": _round(amount, 2),
        "installments": len(snapped),
        "invested": _round(invested, 2),
        "final_value": _round(final_value, 2),
        "gain": _round(final_value - invested, 2),
        "absolute_return_pct": _round((final_value / invested - 1.0) * 100, 2),
        "xirr_pct": _round(rate * 100, 2) if rate is not None else None,
        "units": _round(units, 4),
        "start_date": snapped[0].date().isoformat(),
        "end_date": end_ts.date().isoformat(),
        "end_nav": _round(end_nav, 4),
        "first_installments": installments[:3],
    }


def analyse_scheme(
    scheme_code: int,
    risk_free_rate: float = DEFAULT_RISK_FREE_RATE,
    rolling_years: Tuple[int, ...] = (1, 3, 5),
) -> Dict[str, Any]:
    """Full analysis bundle for one scheme: metadata, returns, risk and rolling windows."""
    payload = client.get_scheme(scheme_code)
    series = to_series(payload["data"])
    if series.empty:
        return {"meta": payload["meta"], "error": "No usable NAV history"}

    rolling = {}
    for years in rolling_years:
        result = rolling_returns(series, years)
        if not result.get("insufficient_data"):
            rolling[f"{years}y"] = result

    return {
        "meta": payload["meta"],
        "nav": {
            "latest": _round(float(series.iloc[-1]), 4),
            "latest_date": series.index[-1].date().isoformat(),
            "inception_date": series.index[0].date().isoformat(),
            "history_days": int((series.index[-1] - series.index[0]).days),
            "observations": int(len(series)),
        },
        "trailing_returns": trailing_returns(series),
        "risk": risk_metrics(series, risk_free_rate),
        "rolling_returns": rolling,
    }


def compare_schemes(
    scheme_codes: List[int], risk_free_rate: float = DEFAULT_RISK_FREE_RATE
) -> Dict[str, Any]:
    """Side-by-side comparison, with returns recomputed over the shared date range.

    Comparing raw trailing numbers across funds with different inception dates is
    misleading, so the common-window block is the one to trust.
    """
    results = []
    series_by_code: Dict[int, pd.Series] = {}

    for code in scheme_codes:
        try:
            payload = client.get_scheme(code)
        except Exception as exc:
            results.append({"scheme_code": code, "error": str(exc)})
            continue

        series = to_series(payload["data"])
        if series.empty:
            results.append({"scheme_code": code, "error": "No usable NAV history"})
            continue

        series_by_code[code] = series
        results.append(
            {
                "scheme_code": code,
                "scheme_name": payload["meta"].get("scheme_name"),
                "fund_house": payload["meta"].get("fund_house"),
                "category": payload["meta"].get("scheme_category"),
                "latest_nav": _round(float(series.iloc[-1]), 4),
                "trailing_returns": trailing_returns(series),
                "risk": risk_metrics(series, risk_free_rate),
            }
        )

    common: Dict[str, Any] = {}
    if len(series_by_code) > 1:
        start = max(s.index[0] for s in series_by_code.values())
        end = min(s.index[-1] for s in series_by_code.values())
        days = (end - start).days
        if days > 0:
            common = {
                "start_date": start.date().isoformat(),
                "end_date": end.date().isoformat(),
                "days": int(days),
                "schemes": {},
            }
            for code, series in series_by_code.items():
                daily = _daily(series)
                start_nav = float(daily.asof(start))
                end_nav = float(daily.asof(end))
                common["schemes"][str(code)] = {
                    "return_pct": _round((end_nav / start_nav - 1.0) * 100, 2),
                    "cagr_pct": _round((_cagr(start_nav, end_nav, days) or 0) * 100, 2)
                    if days >= 365
                    else None,
                }

    return {"schemes": results, "common_period": common}
