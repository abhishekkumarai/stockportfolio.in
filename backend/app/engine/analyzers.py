"""Performance analytics over an equity curve and a trade list.

Every ratio here is annualised from *daily* bars with 252 trading days, and
every one is reported alongside the raw inputs that produced it. A Sharpe of
1.8 computed over eleven trades is not a Sharpe of 1.8, and `trade_count`
sitting next to it is what lets a reader see that.

Deliberate choices:

* **Sortino uses downside deviation about zero**, not about the mean. Punishing
  a strategy for upside volatility — which is what a mean-relative denominator
  does — is the exact objection Sortino exists to answer.
* **Max drawdown is on the equity curve**, not on closed trades. A strategy
  holding through a 40% paper loss and recovering has drawn down 40%, whatever
  its trade log says.
* **SQN** (van Tharp's System Quality Number) is `sqrt(n) * mean / stdev` of
  trade returns. It scales with trade count on purpose: a good system that
  trades often is worth more than the same edge traded rarely.
"""

import logging
import math
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

logger = logging.getLogger(__name__)

TRADING_DAYS = 252
# The Indian risk-free rate. Ignoring it entirely inflates Sharpe by roughly
# 0.4 for a typical equity strategy, which is not a rounding error.
DEFAULT_RISK_FREE = 0.065


def _returns(equity: Sequence[float]) -> np.ndarray:
    values = np.asarray(equity, dtype="float64")
    if len(values) < 2:
        return np.array([])
    previous = values[:-1]
    # A zero-equity bar would divide by zero; it also means the account is
    # blown, so the series is truncated there rather than producing infinities.
    with np.errstate(divide="ignore", invalid="ignore"):
        result = np.where(previous != 0, (values[1:] - previous) / previous, 0.0)
    return np.nan_to_num(result, nan=0.0, posinf=0.0, neginf=0.0)


def cagr(equity: Sequence[float], years: float) -> Optional[float]:
    if len(equity) < 2 or years <= 0 or equity[0] <= 0 or equity[-1] <= 0:
        return None
    return (equity[-1] / equity[0]) ** (1.0 / years) - 1.0


def max_drawdown(equity: Sequence[float]) -> Dict[str, Any]:
    """Deepest peak-to-trough fall, with where it happened and how long it lasted."""
    values = np.asarray(equity, dtype="float64")
    if len(values) < 2:
        return {"max_drawdown_pct": 0.0, "peak_index": 0, "trough_index": 0, "recovery_index": None}

    running_peak = np.maximum.accumulate(values)
    drawdowns = np.where(running_peak > 0, (values - running_peak) / running_peak, 0.0)
    trough = int(np.argmin(drawdowns))
    peak = int(np.argmax(values[: trough + 1])) if trough > 0 else 0

    recovery = None
    after = np.where(values[trough:] >= values[peak])[0]
    if len(after):
        recovery = int(trough + after[0])

    return {
        "max_drawdown_pct": round(float(drawdowns[trough]) * 100.0, 2),
        "peak_index": peak,
        "trough_index": trough,
        "recovery_index": recovery,
        "underwater_bars": (recovery - peak) if recovery is not None else len(values) - peak,
        "recovered": recovery is not None,
    }


def sharpe(returns: np.ndarray, risk_free: float = DEFAULT_RISK_FREE) -> Optional[float]:
    if len(returns) < 2:
        return None
    daily_rf = risk_free / TRADING_DAYS
    excess = returns - daily_rf
    deviation = excess.std(ddof=1)
    if deviation == 0:
        return None
    return float(excess.mean() / deviation * math.sqrt(TRADING_DAYS))


def sortino(returns: np.ndarray, risk_free: float = DEFAULT_RISK_FREE) -> Optional[float]:
    if len(returns) < 2:
        return None
    daily_rf = risk_free / TRADING_DAYS
    excess = returns - daily_rf
    downside = excess[excess < 0]
    if len(downside) == 0:
        # No losing day. Real, and not a number worth reporting as infinity.
        return None
    downside_deviation = math.sqrt(float(np.mean(downside**2)))
    if downside_deviation == 0:
        return None
    return float(excess.mean() / downside_deviation * math.sqrt(TRADING_DAYS))


def calmar(annual_return: Optional[float], max_dd_pct: float) -> Optional[float]:
    if annual_return is None or max_dd_pct >= 0:
        return None
    return float(annual_return / abs(max_dd_pct / 100.0))


def sqn(trade_returns: Sequence[float]) -> Optional[float]:
    values = np.asarray(trade_returns, dtype="float64")
    if len(values) < 2:
        return None
    deviation = values.std(ddof=1)
    if deviation == 0:
        return None
    return float(math.sqrt(len(values)) * values.mean() / deviation)


def trade_statistics(trades: Sequence[Any]) -> Dict[str, Any]:
    """Win rate, payoff, profit factor, expectancy, streaks and holding period."""
    if not trades:
        return {
            "trade_count": 0,
            "note": "No round trips were completed, so trade statistics are undefined.",
        }

    pnls = np.array([t.pnl for t in trades], dtype="float64")
    returns = np.array([t.return_pct for t in trades], dtype="float64")
    wins = pnls[pnls > 0]
    losses = pnls[pnls <= 0]

    gross_profit = float(wins.sum())
    gross_loss = float(abs(losses.sum()))

    longest_win_streak = longest_loss_streak = 0
    current_win = current_loss = 0
    for pnl in pnls:
        if pnl > 0:
            current_win, current_loss = current_win + 1, 0
        else:
            current_loss, current_win = current_loss + 1, 0
        longest_win_streak = max(longest_win_streak, current_win)
        longest_loss_streak = max(longest_loss_streak, current_loss)

    win_rate = len(wins) / len(pnls)
    avg_win = float(wins.mean()) if len(wins) else 0.0
    avg_loss = float(abs(losses.mean())) if len(losses) else 0.0

    return {
        "trade_count": len(trades),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate_pct": round(win_rate * 100.0, 2),
        "avg_win_inr": round(avg_win, 2),
        "avg_loss_inr": round(avg_loss, 2),
        "payoff_ratio": round(avg_win / avg_loss, 3) if avg_loss else None,
        # Profit factor above 1 means the winners paid for the losers. Below
        # 1.2 is usually inside the noise of a few hundred trades.
        "profit_factor": round(gross_profit / gross_loss, 3) if gross_loss else None,
        "expectancy_inr": round(float(pnls.mean()), 2),
        "expectancy_pct": round(float(returns.mean()), 3),
        "best_trade_pct": round(float(returns.max()), 2),
        "worst_trade_pct": round(float(returns.min()), 2),
        "longest_win_streak": longest_win_streak,
        "longest_loss_streak": longest_loss_streak,
        "avg_bars_held": round(float(np.mean([t.bars_held for t in trades])), 1),
        "total_fees_inr": round(float(sum(t.fees for t in trades)), 2),
        "sqn": round(sqn(returns), 3) if sqn(returns) is not None else None,
    }


def exposure(equity: Sequence[float], cash: Sequence[float]) -> Optional[float]:
    """Average fraction of the account actually invested.

    A strategy that is in the market 12% of the time and beats buy-and-hold has
    done something remarkable; the same return at 100% exposure has not. Every
    risk-adjusted number below should be read against this.
    """
    if not equity or len(equity) != len(cash):
        return None
    values = np.asarray(equity, dtype="float64")
    cash_values = np.asarray(cash, dtype="float64")
    invested = np.where(values > 0, 1.0 - cash_values / values, 0.0)
    return round(float(np.clip(invested, 0.0, 1.0).mean()) * 100.0, 2)


def turnover(trades: Sequence[Any], initial_capital: float, years: float) -> Optional[float]:
    """Annual traded value as a multiple of the starting account."""
    if not trades or initial_capital <= 0 or years <= 0:
        return None
    traded = sum(t.entry_price * t.quantity + t.exit_price * t.quantity for t in trades)
    return round(traded / initial_capital / years, 2)


def analyse(
    equity: Sequence[float],
    cash: Sequence[float],
    dates: Sequence[datetime],
    trades: Sequence[Any],
    initial_capital: float,
    risk_free: float = DEFAULT_RISK_FREE,
) -> Dict[str, Any]:
    """The full analyzer bundle for one run."""
    if len(equity) < 2:
        return {"available": False, "reason": "Fewer than two equity points; nothing to analyse."}

    returns = _returns(equity)
    span_days = max(1, (dates[-1] - dates[0]).days) if len(dates) >= 2 else len(equity)
    years = span_days / 365.25

    drawdown = max_drawdown(equity)
    annual = cagr(equity, years)
    total_return = (equity[-1] / equity[0] - 1.0) if equity[0] else None

    return {
        "available": True,
        "start_date": dates[0].isoformat() if len(dates) else None,
        "end_date": dates[-1].isoformat() if len(dates) else None,
        "years": round(years, 2),
        "initial_capital": round(initial_capital, 2),
        "final_equity": round(float(equity[-1]), 2),
        "total_return_pct": round(total_return * 100.0, 2) if total_return is not None else None,
        "cagr_pct": round(annual * 100.0, 2) if annual is not None else None,
        "volatility_pct": round(float(returns.std(ddof=1)) * math.sqrt(TRADING_DAYS) * 100.0, 2)
        if len(returns) > 1 else None,
        "sharpe": round(sharpe(returns, risk_free), 3) if sharpe(returns, risk_free) is not None else None,
        "sortino": round(sortino(returns, risk_free), 3) if sortino(returns, risk_free) is not None else None,
        "calmar": round(calmar(annual, drawdown["max_drawdown_pct"]), 3)
        if calmar(annual, drawdown["max_drawdown_pct"]) is not None else None,
        "max_drawdown_pct": drawdown["max_drawdown_pct"],
        "drawdown_recovered": drawdown["recovered"],
        "underwater_bars": drawdown["underwater_bars"],
        "exposure_pct": exposure(equity, cash),
        "turnover_x": turnover(trades, initial_capital, years),
        "trades": trade_statistics(trades),
        "risk_free_rate_pct": round(risk_free * 100.0, 2),
    }


def buy_and_hold(
    closes: Sequence[float], dates: Sequence[datetime], initial_capital: float,
    risk_free: float = DEFAULT_RISK_FREE,
) -> Dict[str, Any]:
    """The benchmark every strategy has to beat to have justified its costs."""
    if len(closes) < 2 or closes[0] <= 0:
        return {"available": False, "reason": "Not enough price history to benchmark."}
    units = initial_capital / closes[0]
    equity = [units * price for price in closes]
    return analyse(equity, [0.0] * len(equity), dates, [], initial_capital, risk_free)
