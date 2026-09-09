"""Walk-forward optimisation and Monte Carlo permutation testing.

These are not optional extras bolted onto the backtester. They are the reason
the backtester's numbers can be believed at all.

A backtest over a fixed window, with parameters chosen by looking at that same
window, reports the performance of *hindsight*. Both tools here attack that
from different sides:

* **Walk-forward** splits history into consecutive in-sample/out-of-sample
  folds. Parameters are optimised on the in-sample block and then applied,
  untouched, to the block immediately after. The out-of-sample results
  concatenated end to end are the only performance figure in this codebase
  that was never fitted. The **walk-forward efficiency** — out-of-sample
  return divided by in-sample return — is the headline: below about 0.5, the
  optimiser was fitting noise.

* **Permutation testing** answers "could this edge be luck?". The strategy's
  own daily returns are shuffled thousands of times, destroying their ordering
  while keeping their distribution exactly. If a meaningful share of shuffles
  beats the real sequence, the sequencing — which is all a strategy contributes
  — was not doing any work. The output is an empirical p-value.

Both are expensive. Grid sizes and permutation counts are bounded at the API
edge, not here.
"""

import itertools
import logging
import math
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from app.engine import analyzers
from app.engine.broker import CostModel
from app.engine.feed import DataFeed
from app.engine.runner import BacktestError, run
from app.engine.sizer import Sizer
from app.engine.strategies import build_strategy

logger = logging.getLogger(__name__)

# What "best parameters" means. Sharpe by default rather than raw return,
# because optimising for return alone reliably selects the single most
# leveraged, most drawdown-prone corner of the grid.
OBJECTIVES: Dict[str, Callable[[Dict[str, Any]], Optional[float]]] = {
    "sharpe": lambda result: result["performance"].get("sharpe"),
    "sortino": lambda result: result["performance"].get("sortino"),
    "calmar": lambda result: result["performance"].get("calmar"),
    "total_return": lambda result: result["performance"].get("total_return_pct"),
    "sqn": lambda result: (result["performance"].get("trades") or {}).get("sqn"),
}


def parameter_grid(ranges: Dict[str, Sequence[Any]]) -> List[Dict[str, Any]]:
    """Cartesian product of parameter ranges, as a list of kwargs dicts."""
    if not ranges:
        return [{}]
    keys = list(ranges)
    return [dict(zip(keys, values)) for values in itertools.product(*(ranges[k] for k in keys))]


def _run_slice(
    symbol: str,
    frame: pd.DataFrame,
    strategy_name: str,
    params: Dict[str, Any],
    initial_capital: float,
    sizer: Optional[Sizer],
    cost_model: Optional[CostModel],
) -> Optional[Dict[str, Any]]:
    """One backtest over one slice, returning None if it could not run."""
    try:
        strategy = build_strategy(strategy_name, **params)
        feed = DataFeed(symbol, frame)
        return run(
            [feed], strategy, initial_capital=initial_capital,
            sizer=sizer, cost_model=cost_model, start_index=strategy.warmup,
        )
    except (BacktestError, ValueError) as exc:
        logger.debug("Slice failed for %s: %s", params, exc)
        return None


def optimise(
    symbol: str,
    frame: pd.DataFrame,
    strategy_name: str,
    ranges: Dict[str, Sequence[Any]],
    objective: str = "sharpe",
    initial_capital: float = 100_000.0,
    sizer: Optional[Sizer] = None,
    cost_model: Optional[CostModel] = None,
    min_trades: int = 3,
) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
    """Grid search over one window. Returns (best parameters, all results).

    `min_trades` exists because a grid corner that took one lucky trade will
    otherwise win every objective. A parameter set that barely trades has not
    been measured, whatever its Sharpe says.
    """
    score_of = OBJECTIVES.get(objective)
    if score_of is None:
        raise ValueError(f"Unknown objective {objective!r}. Known: {', '.join(OBJECTIVES)}")

    results: List[Dict[str, Any]] = []
    for params in parameter_grid(ranges):
        result = _run_slice(symbol, frame, strategy_name, params, initial_capital, sizer, cost_model)
        if result is None:
            continue
        trades = (result["performance"].get("trades") or {}).get("trade_count", 0)
        score = score_of(result)
        results.append(
            {
                "params": params,
                "score": score,
                "trades": trades,
                "total_return_pct": result["performance"].get("total_return_pct"),
                "max_drawdown_pct": result["performance"].get("max_drawdown_pct"),
                "eligible": trades >= min_trades and score is not None,
            }
        )

    eligible = [r for r in results if r["eligible"]]
    best = max(eligible, key=lambda r: r["score"]) if eligible else None
    return best, sorted(results, key=lambda r: (r["score"] is None, -(r["score"] or 0)))


def walk_forward(
    symbol: str,
    frame: pd.DataFrame,
    strategy_name: str,
    ranges: Dict[str, Sequence[Any]],
    folds: int = 4,
    in_sample_ratio: float = 0.7,
    objective: str = "sharpe",
    initial_capital: float = 100_000.0,
    sizer: Optional[Sizer] = None,
    cost_model: Optional[CostModel] = None,
) -> Dict[str, Any]:
    """Anchored-window walk-forward: optimise in-sample, measure out-of-sample.

    Rolling rather than anchored windows: each fold's in-sample block is a
    fixed-length window ending where its out-of-sample block begins, so a
    strategy is never optimised on data from a market regime a decade before
    the period it is then judged on.
    """
    total_bars = len(frame)
    if total_bars < folds * 120:
        raise BacktestError(
            f"{total_bars} bars is too short for {folds} walk-forward folds. "
            "Roughly 120 bars per fold is the practical minimum."
        )

    fold_size = total_bars // folds
    in_sample_size = int(fold_size * in_sample_ratio)

    fold_results: List[Dict[str, Any]] = []
    out_of_sample_returns: List[float] = []
    in_sample_returns: List[float] = []

    for fold in range(folds):
        window_start = fold * fold_size
        split = window_start + in_sample_size
        window_end = min(window_start + fold_size, total_bars)
        if window_end - split < 30:
            continue

        in_sample = frame.iloc[window_start:split]
        out_of_sample = frame.iloc[split:window_end]

        best, _ = optimise(
            symbol, in_sample, strategy_name, ranges, objective,
            initial_capital, sizer, cost_model,
        )
        if best is None:
            fold_results.append(
                {
                    "fold": fold + 1,
                    "skipped": True,
                    "reason": "No parameter set traded enough in-sample to be measurable.",
                }
            )
            continue

        oos = _run_slice(
            symbol, out_of_sample, strategy_name, best["params"],
            initial_capital, sizer, cost_model,
        )
        oos_return = oos["performance"].get("total_return_pct") if oos else None
        oos_benchmark = oos["benchmark"].get("total_return_pct") if oos else None

        if best["total_return_pct"] is not None:
            in_sample_returns.append(best["total_return_pct"])
        if oos_return is not None:
            out_of_sample_returns.append(oos_return)

        fold_results.append(
            {
                "fold": fold + 1,
                "skipped": False,
                "in_sample_bars": len(in_sample),
                "out_of_sample_bars": len(out_of_sample),
                "chosen_params": best["params"],
                "in_sample_score": best["score"],
                "in_sample_return_pct": best["total_return_pct"],
                "out_of_sample_return_pct": oos_return,
                "out_of_sample_benchmark_pct": oos_benchmark,
                "out_of_sample_sharpe": oos["performance"].get("sharpe") if oos else None,
                "out_of_sample_max_drawdown_pct": (
                    oos["performance"].get("max_drawdown_pct") if oos else None
                ),
                "out_of_sample_trades": (
                    (oos["performance"].get("trades") or {}).get("trade_count") if oos else 0
                ),
            }
        )

    mean_in = float(np.mean(in_sample_returns)) if in_sample_returns else None
    mean_out = float(np.mean(out_of_sample_returns)) if out_of_sample_returns else None
    efficiency = (
        (mean_out / mean_in) if (mean_in and mean_out is not None and mean_in > 0) else None
    )

    chosen = [f["chosen_params"] for f in fold_results if not f.get("skipped")]
    stable = len({tuple(sorted(p.items())) for p in chosen}) if chosen else 0

    return {
        "folds": fold_results,
        "completed_folds": len([f for f in fold_results if not f.get("skipped")]),
        "mean_in_sample_return_pct": round(mean_in, 2) if mean_in is not None else None,
        "mean_out_of_sample_return_pct": round(mean_out, 2) if mean_out is not None else None,
        "walk_forward_efficiency": round(efficiency, 3) if efficiency is not None else None,
        "positive_oos_folds": sum(1 for r in out_of_sample_returns if r > 0),
        "distinct_parameter_sets": stable,
        "verdict": _walk_forward_verdict(efficiency, out_of_sample_returns, stable),
    }


def _walk_forward_verdict(
    efficiency: Optional[float], oos_returns: List[float], distinct_params: int
) -> str:
    if not oos_returns:
        return "No fold produced a measurable out-of-sample result."
    positive = sum(1 for r in oos_returns if r > 0)
    share = positive / len(oos_returns)

    if efficiency is None:
        return "In-sample returns were not positive, so efficiency is undefined."
    if efficiency < 0.3:
        return (
            f"Efficiency {efficiency:.2f}: out-of-sample performance is a small "
            "fraction of in-sample. The optimiser is fitting noise."
        )
    if efficiency < 0.6 or share < 0.5:
        return (
            f"Efficiency {efficiency:.2f} with {positive}/{len(oos_returns)} folds "
            "positive out-of-sample. Weak and not clearly better than luck."
        )
    if distinct_params > max(2, len(oos_returns) - 1):
        return (
            f"Efficiency {efficiency:.2f} looks healthy, but the optimiser chose "
            "different parameters in nearly every fold — the edge is not stable."
        )
    return (
        f"Efficiency {efficiency:.2f} with {positive}/{len(oos_returns)} folds "
        "positive out-of-sample and reasonably stable parameters. Survives "
        "walk-forward, which is not the same as being profitable live."
    )


def permutation_test(
    strategy_returns: Sequence[float],
    permutations: int = 1000,
    seed: int = 42,
) -> Dict[str, Any]:
    """Empirical p-value for the strategy's edge under return shuffling.

    The null hypothesis is that the *order* of returns carried no information —
    that the same daily returns arranged any other way would have done as well.
    Each permutation reshuffles them and recomputes total return and Sharpe.
    The p-value is the share of shuffles that matched or beat the real sequence.

    What this does and does not test: shuffling preserves the return
    distribution exactly, so it cannot flatter a strategy through fat tails,
    but it also destroys autocorrelation — which means a trend-following
    strategy that genuinely exploits serial correlation should score well here,
    and that is precisely the claim being checked.
    """
    returns = np.asarray([r for r in strategy_returns if r == r], dtype="float64")
    if len(returns) < 30:
        return {
            "available": False,
            "reason": f"Only {len(returns)} return observations; need at least 30.",
        }

    rng = np.random.default_rng(seed)

    def total_return(series: np.ndarray) -> float:
        return float(np.prod(1.0 + series) - 1.0)

    def sharpe_of(series: np.ndarray) -> float:
        deviation = series.std(ddof=1)
        if deviation == 0:
            return 0.0
        return float(series.mean() / deviation * math.sqrt(analyzers.TRADING_DAYS))

    actual_return = total_return(returns)
    actual_sharpe = sharpe_of(returns)

    shuffled = np.empty(permutations)
    shuffled_sharpe = np.empty(permutations)
    working = returns.copy()
    for i in range(permutations):
        rng.shuffle(working)
        shuffled[i] = total_return(working)
        shuffled_sharpe[i] = sharpe_of(working)

    # (count + 1) / (n + 1): the standard small-sample correction. Without it a
    # test that no permutation beat reports p = 0, which claims more certainty
    # than the number of permutations can support.
    p_return = float((np.sum(shuffled >= actual_return) + 1) / (permutations + 1))
    p_sharpe = float((np.sum(shuffled_sharpe >= actual_sharpe) + 1) / (permutations + 1))

    return {
        "available": True,
        "permutations": permutations,
        "observations": len(returns),
        "actual_return_pct": round(actual_return * 100.0, 2),
        "actual_sharpe": round(actual_sharpe, 3),
        "permuted_return_mean_pct": round(float(shuffled.mean()) * 100.0, 2),
        "permuted_return_p95_pct": round(float(np.percentile(shuffled, 95)) * 100.0, 2),
        "p_value_return": round(p_return, 4),
        "p_value_sharpe": round(p_sharpe, 4),
        "significant_at_5pct": p_return < 0.05,
        "verdict": (
            f"p = {p_return:.3f}: fewer than 5% of shuffles matched this result, "
            "so the ordering of returns carried real information."
            if p_return < 0.05
            else f"p = {p_return:.3f}: {p_return*100:.0f}% of random shuffles did as "
            "well or better. This result is indistinguishable from luck."
        ),
        "caveat": (
            "Shuffling preserves the return distribution and destroys its "
            "ordering. It tests whether timing added value, not whether the "
            "strategy will work on unseen data — walk-forward tests that."
        ),
    }


def returns_from_equity(equity_curve: Sequence[Dict[str, Any]]) -> List[float]:
    """Daily returns out of a runner equity curve, for the permutation test."""
    values = [point["equity"] for point in equity_curve]
    return [
        (values[i] - values[i - 1]) / values[i - 1]
        for i in range(1, len(values))
        if values[i - 1] > 0
    ]
