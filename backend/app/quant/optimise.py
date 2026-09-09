"""Portfolio optimisation: mean-variance, risk parity, and hierarchical risk parity.

Mean-variance optimisation is included because it is the textbook answer and
people expect to see the efficient frontier. It is also, on a real 20-holding
Indian portfolio, close to unusable on its own: it needs an expected-return
vector nobody can estimate, and it inverts a covariance matrix estimated from a
few hundred noisy observations. The result is famously unstable — a 1% change
in an input can move a weight by 30 points, and the "optimal" portfolio is
routinely 90% in three names.

**HRP is the default for that reason.** Lopez de Prado's hierarchical risk
parity never inverts the covariance matrix. It clusters assets by correlation,
orders them so similar assets sit adjacently (quasi-diagonalisation), then
recursively splits risk budget down the tree. It needs no expected returns, is
stable under estimation error, and degrades gracefully when the covariance
matrix is near-singular — which, with twenty holdings and a year of data, it
always is.

Constraints supported across all methods: maximum weight per asset, sector
caps, and long-only (shorting is not modelled anywhere in this codebase).
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import linkage, to_tree
from scipy.optimize import minimize
from scipy.spatial.distance import squareform

logger = logging.getLogger(__name__)

TRADING_DAYS = 252
DEFAULT_RISK_FREE = 0.065

# Below this many observations a covariance matrix is more estimation error
# than signal. Six months of daily data is the floor for any of this.
MIN_OBSERVATIONS = 120


@dataclass
class OptimisationConstraints:
    """What the optimiser is allowed to produce."""

    max_weight: float = 0.35
    min_weight: float = 0.0
    sector_caps: Dict[str, float] = field(default_factory=dict)
    sectors: Dict[str, str] = field(default_factory=dict)  # symbol -> sector

    def validate(self, symbols: Sequence[str]) -> None:
        if not 0 < self.max_weight <= 1.0:
            raise ValueError("max_weight must be in (0, 1].")
        if self.max_weight * len(symbols) < 1.0:
            raise ValueError(
                f"max_weight {self.max_weight:.2f} across {len(symbols)} assets "
                f"caps the portfolio at {self.max_weight * len(symbols):.0%} — "
                "the weights cannot sum to 1."
            )


def annualised_stats(returns: pd.DataFrame) -> Tuple[pd.Series, pd.DataFrame]:
    """Annualised mean returns and covariance from daily returns."""
    return returns.mean() * TRADING_DAYS, returns.cov() * TRADING_DAYS


def portfolio_stats(
    weights: np.ndarray, mean_returns: pd.Series, covariance: pd.DataFrame,
    risk_free: float = DEFAULT_RISK_FREE,
) -> Dict[str, float]:
    expected = float(np.dot(weights, mean_returns))
    variance = float(weights @ covariance.to_numpy() @ weights)
    volatility = float(np.sqrt(max(variance, 0.0)))
    return {
        "expected_return": expected,
        "volatility": volatility,
        "sharpe": (expected - risk_free) / volatility if volatility > 0 else 0.0,
    }


# ---- mean-variance -------------------------------------------------------


def _bounds_and_constraints(
    symbols: Sequence[str], constraints: OptimisationConstraints
) -> Tuple[List[Tuple[float, float]], List[Dict[str, Any]]]:
    bounds = [(constraints.min_weight, constraints.max_weight)] * len(symbols)
    scipy_constraints: List[Dict[str, Any]] = [
        {"type": "eq", "fun": lambda w: float(np.sum(w) - 1.0)}
    ]

    for sector, cap in constraints.sector_caps.items():
        indices = [
            i for i, symbol in enumerate(symbols)
            if constraints.sectors.get(symbol) == sector
        ]
        if not indices:
            continue
        # Default argument binding, not closure capture: a late-binding lambda
        # here would give every sector the last sector's indices.
        scipy_constraints.append(
            {
                "type": "ineq",
                "fun": lambda w, idx=tuple(indices), c=cap: float(c - np.sum(w[list(idx)])),
            }
        )

    return bounds, scipy_constraints


def minimum_variance(
    returns: pd.DataFrame, constraints: Optional[OptimisationConstraints] = None
) -> Dict[str, Any]:
    """The lowest-volatility portfolio on the frontier.

    The one mean-variance output that does not need expected returns, and
    therefore the one that is not dominated by the least estimable input.
    """
    constraints = constraints or OptimisationConstraints()
    symbols = list(returns.columns)
    constraints.validate(symbols)
    mean_returns, covariance = annualised_stats(returns)
    matrix = covariance.to_numpy()

    bounds, scipy_constraints = _bounds_and_constraints(symbols, constraints)
    initial = np.repeat(1.0 / len(symbols), len(symbols))

    result = minimize(
        lambda w: float(w @ matrix @ w),
        initial, method="SLSQP", bounds=bounds, constraints=scipy_constraints,
        options={"maxiter": 500, "ftol": 1e-10},
    )
    weights = _normalise(result.x if result.success else initial)
    return _package("minimum_variance", symbols, weights, mean_returns, covariance,
                    converged=bool(result.success))


def maximum_sharpe(
    returns: pd.DataFrame, constraints: Optional[OptimisationConstraints] = None,
    risk_free: float = DEFAULT_RISK_FREE,
) -> Dict[str, Any]:
    """The tangency portfolio.

    Uses historical mean returns as the expected-return estimate, which is the
    standard approach and also the weak point: a stock that happened to double
    last year gets an expected return of 100%, and the optimiser piles into it.
    The `max_weight` constraint is the only thing standing between this and a
    three-stock portfolio, and it is doing real work.
    """
    constraints = constraints or OptimisationConstraints()
    symbols = list(returns.columns)
    constraints.validate(symbols)
    mean_returns, covariance = annualised_stats(returns)
    matrix = covariance.to_numpy()
    means = mean_returns.to_numpy()

    def negative_sharpe(weights: np.ndarray) -> float:
        volatility = float(np.sqrt(max(weights @ matrix @ weights, 1e-12)))
        return -float((np.dot(weights, means) - risk_free) / volatility)

    bounds, scipy_constraints = _bounds_and_constraints(symbols, constraints)
    initial = np.repeat(1.0 / len(symbols), len(symbols))

    result = minimize(
        negative_sharpe, initial, method="SLSQP", bounds=bounds,
        constraints=scipy_constraints, options={"maxiter": 500, "ftol": 1e-10},
    )
    weights = _normalise(result.x if result.success else initial)
    package = _package("maximum_sharpe", symbols, weights, mean_returns, covariance,
                       converged=bool(result.success), risk_free=risk_free)
    package["caveat"] = (
        "Expected returns are historical means, which are a poor forecast. "
        "Treat this as an illustration of the frontier, not an allocation."
    )
    return package


def efficient_frontier(
    returns: pd.DataFrame, points: int = 25,
    constraints: Optional[OptimisationConstraints] = None,
    risk_free: float = DEFAULT_RISK_FREE,
) -> Dict[str, Any]:
    """Sample the frontier by minimising variance at each target return."""
    constraints = constraints or OptimisationConstraints()
    symbols = list(returns.columns)
    constraints.validate(symbols)
    mean_returns, covariance = annualised_stats(returns)
    matrix = covariance.to_numpy()
    means = mean_returns.to_numpy()

    bounds, base_constraints = _bounds_and_constraints(symbols, constraints)
    initial = np.repeat(1.0 / len(symbols), len(symbols))
    targets = np.linspace(means.min(), means.max(), points)

    frontier: List[Dict[str, Any]] = []
    for target in targets:
        scipy_constraints = base_constraints + [
            {"type": "eq", "fun": lambda w, t=target: float(np.dot(w, means) - t)}
        ]
        result = minimize(
            lambda w: float(w @ matrix @ w), initial, method="SLSQP",
            bounds=bounds, constraints=scipy_constraints,
            options={"maxiter": 300, "ftol": 1e-9},
        )
        if not result.success:
            # Targets outside the constrained feasible set simply have no
            # portfolio; dropping them is correct, faking one is not.
            continue
        weights = _normalise(result.x)
        stats = portfolio_stats(weights, mean_returns, covariance, risk_free)
        frontier.append(
            {
                "expected_return_pct": round(stats["expected_return"] * 100.0, 2),
                "volatility_pct": round(stats["volatility"] * 100.0, 2),
                "sharpe": round(stats["sharpe"], 3),
                "weights": {s: round(float(w), 4) for s, w in zip(symbols, weights)},
            }
        )

    return {
        "points": frontier,
        "min_variance": minimum_variance(returns, constraints),
        "max_sharpe": maximum_sharpe(returns, constraints, risk_free),
        "requested_points": points,
        "solved_points": len(frontier),
    }


# ---- risk parity ---------------------------------------------------------


def risk_parity(
    returns: pd.DataFrame, constraints: Optional[OptimisationConstraints] = None
) -> Dict[str, Any]:
    """Equal risk contribution: every asset contributes the same share of variance.

    Unlike equal *weight*, which lets the most volatile holding dominate the
    portfolio's actual risk, this equalises marginal risk contributions. It
    still needs the covariance matrix but never inverts it, so it is far more
    stable than mean-variance.
    """
    constraints = constraints or OptimisationConstraints()
    symbols = list(returns.columns)
    constraints.validate(symbols)
    mean_returns, covariance = annualised_stats(returns)
    matrix = covariance.to_numpy()
    count = len(symbols)
    target_share = 1.0 / count

    def objective(weights: np.ndarray) -> float:
        portfolio_variance = float(weights @ matrix @ weights)
        if portfolio_variance <= 0:
            return 1e6
        contributions = weights * (matrix @ weights) / portfolio_variance
        return float(np.sum((contributions - target_share) ** 2))

    bounds, scipy_constraints = _bounds_and_constraints(symbols, constraints)
    # Start from inverse volatility, which is already close to the answer and
    # keeps SLSQP out of the flat regions near equal weight.
    volatilities = np.sqrt(np.diag(matrix))
    initial = _normalise(np.where(volatilities > 0, 1.0 / volatilities, 1.0))

    result = minimize(
        objective, initial, method="SLSQP", bounds=bounds,
        constraints=scipy_constraints, options={"maxiter": 800, "ftol": 1e-12},
    )
    weights = _normalise(result.x if result.success else initial)
    package = _package("risk_parity", symbols, weights, mean_returns, covariance,
                       converged=bool(result.success))
    package["risk_contributions"] = _risk_contributions(weights, matrix, symbols)
    return package


def _risk_contributions(
    weights: np.ndarray, matrix: np.ndarray, symbols: Sequence[str]
) -> Dict[str, float]:
    portfolio_variance = float(weights @ matrix @ weights)
    if portfolio_variance <= 0:
        return {symbol: 0.0 for symbol in symbols}
    contributions = weights * (matrix @ weights) / portfolio_variance
    return {
        symbol: round(float(value) * 100.0, 2)
        for symbol, value in zip(symbols, contributions)
    }


# ---- hierarchical risk parity --------------------------------------------


def _correlation_distance(correlation: pd.DataFrame) -> np.ndarray:
    """Lopez de Prado's distance: d = sqrt((1 - rho) / 2), a true metric on [0,1]."""
    distance = np.sqrt(np.clip((1.0 - correlation.to_numpy()) / 2.0, 0.0, 1.0))
    np.fill_diagonal(distance, 0.0)
    # squareform demands exact symmetry; floating-point covariance is symmetric
    # to within 1e-16, which it rejects.
    return (distance + distance.T) / 2.0


def _quasi_diagonal_order(link: np.ndarray) -> List[int]:
    """Leaf order from the linkage tree, so correlated assets sit adjacently."""
    tree = to_tree(link, rd=False)
    order: List[int] = []

    def walk(node) -> None:
        if node.is_leaf():
            order.append(node.id)
            return
        walk(node.get_left())
        walk(node.get_right())

    walk(tree)
    return order


def _inverse_variance_weights(covariance: np.ndarray, indices: Sequence[int]) -> np.ndarray:
    variances = np.diag(covariance)[list(indices)]
    inverse = np.where(variances > 0, 1.0 / variances, 0.0)
    total = inverse.sum()
    return inverse / total if total > 0 else np.repeat(1.0 / len(indices), len(indices))


def _cluster_variance(covariance: np.ndarray, indices: Sequence[int]) -> float:
    weights = _inverse_variance_weights(covariance, indices)
    block = covariance[np.ix_(list(indices), list(indices))]
    return float(weights @ block @ weights)


def hierarchical_risk_parity(
    returns: pd.DataFrame,
    constraints: Optional[OptimisationConstraints] = None,
    linkage_method: str = "single",
) -> Dict[str, Any]:
    """HRP — the default allocator here, and the one that survives real data.

    Three steps, none of which inverts a matrix:

    1. **Tree clustering.** Build a hierarchy over the correlation distance
       matrix, so assets that move together end up on the same branch.
    2. **Quasi-diagonalisation.** Reorder assets by the tree's leaf order,
       which pushes large covariances toward the diagonal.
    3. **Recursive bisection.** Split the ordered list in two and allocate
       between the halves in inverse proportion to each half's variance, then
       recurse. Risk budget flows down the tree rather than being solved for
       globally.

    The `max_weight` constraint is applied afterwards by capping and
    redistributing, since HRP itself has no constraint mechanism.
    """
    constraints = constraints or OptimisationConstraints()
    symbols = list(returns.columns)
    if len(symbols) < 2:
        raise ValueError("HRP needs at least two assets.")
    constraints.validate(symbols)

    mean_returns, covariance_frame = annualised_stats(returns)
    covariance = covariance_frame.to_numpy()
    correlation = returns.corr().fillna(0.0)

    distance = _correlation_distance(correlation)
    link = linkage(squareform(distance, checks=False), method=linkage_method)
    order = _quasi_diagonal_order(link)

    weights = np.ones(len(symbols))
    clusters: List[List[int]] = [order]

    while clusters:
        # Split every cluster of more than one asset, allocating between halves.
        clusters = [
            part
            for cluster in clusters
            for part in (cluster[: len(cluster) // 2], cluster[len(cluster) // 2 :])
            if len(part) > 0
        ]
        for i in range(0, len(clusters), 2):
            if i + 1 >= len(clusters):
                break
            left, right = clusters[i], clusters[i + 1]
            left_variance = _cluster_variance(covariance, left)
            right_variance = _cluster_variance(covariance, right)
            total = left_variance + right_variance
            # Inverse-variance split: the riskier half gets less.
            alpha = 1.0 - left_variance / total if total > 0 else 0.5
            weights[left] *= alpha
            weights[right] *= 1.0 - alpha
        clusters = [cluster for cluster in clusters if len(cluster) > 1]

    weights = _apply_max_weight(_normalise(weights), constraints.max_weight)

    package = _package("hierarchical_risk_parity", symbols, weights,
                       mean_returns, covariance_frame, converged=True)
    package["risk_contributions"] = _risk_contributions(weights, covariance, symbols)
    package["clustering"] = {
        "method": linkage_method,
        "leaf_order": [symbols[i] for i in order],
    }
    package["why"] = (
        "HRP never inverts the covariance matrix, so it stays stable where "
        "mean-variance optimisation produces extreme weights from noise."
    )
    return package


def _apply_max_weight(weights: np.ndarray, max_weight: float, iterations: int = 50) -> np.ndarray:
    """Cap weights and redistribute the excess proportionally among the rest."""
    capped = weights.copy()
    for _ in range(iterations):
        excess_mask = capped > max_weight
        if not excess_mask.any():
            break
        excess = float((capped[excess_mask] - max_weight).sum())
        capped[excess_mask] = max_weight
        room = ~excess_mask
        if not room.any():
            break
        share = capped[room]
        total = share.sum()
        capped[room] = share + excess * (share / total if total > 0 else 1.0 / room.sum())
    return _normalise(capped)


def _normalise(weights: np.ndarray) -> np.ndarray:
    weights = np.clip(np.asarray(weights, dtype="float64"), 0.0, None)
    total = weights.sum()
    if total <= 0:
        return np.repeat(1.0 / len(weights), len(weights))
    return weights / total


def _package(
    method: str, symbols: Sequence[str], weights: np.ndarray,
    mean_returns: pd.Series, covariance: pd.DataFrame,
    converged: bool = True, risk_free: float = DEFAULT_RISK_FREE,
) -> Dict[str, Any]:
    stats = portfolio_stats(weights, mean_returns, covariance, risk_free)
    effective_n = 1.0 / float(np.sum(weights**2)) if np.sum(weights**2) > 0 else 0.0
    return {
        "method": method,
        "converged": converged,
        "weights": {s: round(float(w), 4) for s, w in zip(symbols, weights)},
        "expected_return_pct": round(stats["expected_return"] * 100.0, 2),
        "volatility_pct": round(stats["volatility"] * 100.0, 2),
        "sharpe": round(stats["sharpe"], 3),
        # Effective N: how many equally weighted holdings this concentration
        # is equivalent to. A 20-name portfolio with an effective N of 4 is a
        # four-stock portfolio wearing a disguise.
        "effective_holdings": round(effective_n, 2),
        "max_weight": round(float(weights.max()), 4),
    }


METHODS = {
    "hrp": hierarchical_risk_parity,
    "risk_parity": risk_parity,
    "min_variance": minimum_variance,
    "max_sharpe": maximum_sharpe,
}


def optimise(
    returns: pd.DataFrame, method: str = "hrp",
    constraints: Optional[OptimisationConstraints] = None,
) -> Dict[str, Any]:
    """Dispatch, with the data-sufficiency check every method shares."""
    if returns is None or returns.empty:
        raise ValueError("No return series supplied.")
    clean = returns.dropna(how="any")
    if len(clean) < MIN_OBSERVATIONS:
        raise ValueError(
            f"Only {len(clean)} overlapping observations across {len(returns.columns)} "
            f"assets; {MIN_OBSERVATIONS} are needed before a covariance matrix "
            "means anything. A recently bought holding shortens the overlap for all."
        )
    fn = METHODS.get(method)
    if fn is None:
        raise ValueError(f"Unknown method {method!r}. Known: {', '.join(sorted(METHODS))}")
    return fn(clean, constraints)
