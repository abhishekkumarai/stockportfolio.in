"""Factor exposure regression for Indian equities.

Decomposes a portfolio's returns into what the market and the standard style
factors explain, and what is left over. That residual — alpha — is the only
part a stock picker can claim credit for, and it is usually much smaller than
the headline return suggests. A portfolio that returned 22% while its
factor-mimicking mix returned 20% did not beat the market by 22%.

**Factors are built from index proxies, not from an academic factor library.**
There is no Indian equivalent of the Fama-French data library that is free and
current, so each factor is a long-short spread between two liquid indices:

    Market     Nifty 500 minus the risk-free rate
    Size       Nifty Smallcap 100 minus Nifty 50      (small minus big)
    Value      Nifty 500 Value 50 minus Nifty 500     (value minus market)
    Momentum   Nifty 200 Momentum 30 minus Nifty 200
    Quality    Nifty 200 Quality 30 minus Nifty 200
    Low vol    Nifty 100 Low Volatility 30 minus Nifty 100

These are approximations of the academic constructs, and the index-provider
methodology differs from Fama-French in real ways. They are what is actually
obtainable for free, and they are labelled as proxies everywhere they surface.

Regression is ordinary least squares via `numpy.linalg.lstsq` rather than
statsmodels — the model is a handful of columns, and statsmodels would add tens
of megabytes to a Docker image whose size is already a live concern.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from app.yf_frames import close_series

logger = logging.getLogger(__name__)

TRADING_DAYS = 252
DEFAULT_RISK_FREE = 0.065

# yfinance tickers for the index proxies. Not all are always available; the
# builder drops any leg it cannot fetch and says which factors it lost.
FACTOR_PROXIES: Dict[str, Tuple[str, Optional[str]]] = {
    "market": ("^CRSLDX", None),                    # Nifty 500
    "size": ("^CNXSC", "^NSEI"),                    # Smallcap 100 minus Nifty 50
    "value": ("NIFTY500VALUE50.NS", "^CRSLDX"),
    "momentum": ("NIFTY200MOMENTM30.NS", "^CNX200"),
    "quality": ("NIFTY200QUALTY30.NS", "^CNX200"),
    "low_vol": ("NIFTY100LOWVOL30.NS", "^CNX100"),
}

FACTOR_LABELS = {
    "market": "Market (Nifty 500)",
    "size": "Size (small minus big)",
    "value": "Value (value minus market)",
    "momentum": "Momentum",
    "quality": "Quality",
    "low_vol": "Low volatility",
}

MIN_OBSERVATIONS = 60


@dataclass
class RegressionResult:
    """OLS output, with the diagnostics needed to judge whether to believe it."""

    alpha_daily: float
    betas: Dict[str, float]
    r_squared: float
    adjusted_r_squared: float
    residual_std: float
    observations: int
    standard_errors: Dict[str, float]

    @property
    def alpha_annual(self) -> float:
        return self.alpha_daily * TRADING_DAYS

    def t_stats(self) -> Dict[str, Optional[float]]:
        return {
            name: (beta / self.standard_errors[name] if self.standard_errors.get(name) else None)
            for name, beta in self.betas.items()
        }


def ols(y: np.ndarray, X: np.ndarray, names: Sequence[str]) -> RegressionResult:
    """Least squares with an intercept, plus standard errors and R-squared.

    Standard errors come from the classical `sigma^2 * (X'X)^-1` formula. Daily
    financial returns are heteroskedastic, so these understate uncertainty —
    they are reported to give a sense of scale, not to support a hypothesis
    test, and the caller is told as much.
    """
    design = np.column_stack([np.ones(len(y)), X])
    coefficients, *_ = np.linalg.lstsq(design, y, rcond=None)

    fitted = design @ coefficients
    residuals = y - fitted
    degrees_of_freedom = len(y) - design.shape[1]

    total_ss = float(np.sum((y - y.mean()) ** 2))
    residual_ss = float(np.sum(residuals**2))
    r_squared = 1.0 - residual_ss / total_ss if total_ss > 0 else 0.0
    adjusted = (
        1.0 - (1.0 - r_squared) * (len(y) - 1) / degrees_of_freedom
        if degrees_of_freedom > 0 else r_squared
    )

    errors: Dict[str, float] = {}
    if degrees_of_freedom > 0:
        sigma_squared = residual_ss / degrees_of_freedom
        try:
            covariance = sigma_squared * np.linalg.pinv(design.T @ design)
            diagonal = np.sqrt(np.clip(np.diag(covariance), 0.0, None))
            errors = {name: float(diagonal[i + 1]) for i, name in enumerate(names)}
        except np.linalg.LinAlgError:
            errors = {}

    return RegressionResult(
        alpha_daily=float(coefficients[0]),
        betas={name: float(coefficients[i + 1]) for i, name in enumerate(names)},
        r_squared=r_squared,
        adjusted_r_squared=adjusted,
        residual_std=float(np.std(residuals, ddof=1)) if len(residuals) > 1 else 0.0,
        observations=len(y),
        standard_errors=errors,
    )


def build_factor_returns(
    start: Any, end: Any, factors: Optional[Sequence[str]] = None
) -> Tuple[pd.DataFrame, List[str]]:
    """Daily factor returns from index proxies. Returns (frame, missing factors)."""
    try:
        import yfinance as yf
    except ImportError:
        return pd.DataFrame(), list(FACTOR_PROXIES)

    wanted = list(factors) if factors else list(FACTOR_PROXIES)
    tickers = sorted(
        {ticker for name in wanted for ticker in FACTOR_PROXIES[name] if ticker}
    )

    try:
        data = yf.download(
            tickers, start=start, end=end, progress=False,
            auto_adjust=True, group_by="ticker", threads=True,
        )
    except Exception as exc:
        logger.warning("Factor proxy download failed: %s", exc)
        return pd.DataFrame(), wanted

    closes: Dict[str, pd.Series] = {}
    for ticker in tickers:
        series = close_series(data, ticker)
        if series is not None and len(series) > MIN_OBSERVATIONS:
            closes[ticker] = series

    columns: Dict[str, pd.Series] = {}
    missing: List[str] = []
    for name in wanted:
        long_ticker, short_ticker = FACTOR_PROXIES[name]
        if long_ticker not in closes or (short_ticker and short_ticker not in closes):
            missing.append(name)
            continue
        long_returns = closes[long_ticker].pct_change()
        if short_ticker:
            columns[name] = (long_returns - closes[short_ticker].pct_change()).dropna()
        else:
            columns[name] = (long_returns - DEFAULT_RISK_FREE / TRADING_DAYS).dropna()

    if not columns:
        return pd.DataFrame(), wanted
    return pd.DataFrame(columns).dropna(), missing


def analyse_exposures(
    portfolio_returns: pd.Series,
    factor_returns: pd.DataFrame,
    risk_free: float = DEFAULT_RISK_FREE,
) -> Dict[str, Any]:
    """Regress portfolio returns on the factors and decompose the result."""
    aligned = pd.concat([portfolio_returns.rename("portfolio"), factor_returns], axis=1).dropna()
    if len(aligned) < MIN_OBSERVATIONS:
        return {
            "available": False,
            "reason": (
                f"Only {len(aligned)} overlapping observations; {MIN_OBSERVATIONS} "
                "are needed for a factor regression to mean anything."
            ),
        }

    names = list(factor_returns.columns)
    excess = aligned["portfolio"].to_numpy() - risk_free / TRADING_DAYS
    result = ols(excess, aligned[names].to_numpy(), names)

    # Return attribution: each factor's beta times its realised mean return,
    # annualised. What is left is alpha plus estimation noise.
    contributions = {
        name: round(
            float(result.betas[name] * aligned[name].mean() * TRADING_DAYS) * 100.0, 2
        )
        for name in names
    }
    explained = sum(contributions.values())
    total = float(excess.mean() * TRADING_DAYS) * 100.0
    t_stats = result.t_stats()

    return {
        "available": True,
        "observations": result.observations,
        "alpha_annual_pct": round(result.alpha_annual * 100.0, 2),
        "r_squared": round(result.r_squared, 4),
        "adjusted_r_squared": round(result.adjusted_r_squared, 4),
        "betas": {
            name: {
                "beta": round(result.betas[name], 4),
                "label": FACTOR_LABELS.get(name, name),
                "t_stat": round(t_stats[name], 2) if t_stats.get(name) is not None else None,
                "contribution_pct": contributions[name],
            }
            for name in names
        },
        "attribution": {
            "total_excess_return_pct": round(total, 2),
            "explained_by_factors_pct": round(explained, 2),
            "idiosyncratic_pct": round(total - explained, 2),
            "share_explained": (
                round(explained / total, 3) if abs(total) > 1e-9 else None
            ),
        },
        "interpretation": _interpret(result, contributions, total),
        "caveats": [
            "Factors are index-proxy spreads, not Fama-French constructs. Index "
            "provider methodology differs, so betas are indicative.",
            "Standard errors assume homoskedastic residuals, which daily equity "
            "returns are not. Treat t-statistics as scale, not significance.",
            f"R-squared of {result.r_squared:.2f} means "
            f"{(1 - result.r_squared) * 100:.0f}% of variance is unexplained by "
            "these factors.",
        ],
    }


def _interpret(result: RegressionResult, contributions: Dict[str, float], total: float) -> str:
    market_beta = result.betas.get("market")
    parts: List[str] = []

    if market_beta is not None:
        if market_beta > 1.2:
            parts.append(f"Market beta {market_beta:.2f} — amplifies index moves in both directions.")
        elif market_beta < 0.8:
            parts.append(f"Market beta {market_beta:.2f} — defensive relative to the index.")
        else:
            parts.append(f"Market beta {market_beta:.2f} — broadly index-like.")

    tilts = sorted(
        ((n, b) for n, b in result.betas.items() if n != "market"),
        key=lambda item: abs(item[1]), reverse=True,
    )
    if tilts and abs(tilts[0][1]) > 0.15:
        name, beta = tilts[0]
        direction = "toward" if beta > 0 else "away from"
        parts.append(f"Strongest style tilt is {direction} {FACTOR_LABELS.get(name, name).lower()} (beta {beta:.2f}).")

    alpha = result.alpha_annual * 100.0
    if abs(total) > 1e-9:
        if alpha > 3:
            parts.append(f"Alpha of {alpha:.1f}%/yr is left after factors — genuine selection, or an omitted factor.")
        elif alpha < -3:
            parts.append(f"Alpha of {alpha:.1f}%/yr: the factor mix would have done better than the actual picks.")
        else:
            parts.append(f"Alpha of {alpha:.1f}%/yr is within noise — returns are essentially factor exposure.")

    return " ".join(parts)


def rolling_betas(
    portfolio_returns: pd.Series, factor_returns: pd.DataFrame,
    window: int = 126, step: int = 5,
) -> Dict[str, Any]:
    """Betas re-estimated over a rolling window.

    A single full-period beta hides regime change: a portfolio can be
    defensive for two years and aggressive for the next, and average out to
    index-like. `window` defaults to roughly six months of trading.
    """
    aligned = pd.concat([portfolio_returns.rename("portfolio"), factor_returns], axis=1).dropna()
    if len(aligned) < window + step:
        return {
            "available": False,
            "reason": f"Need more than {window} observations for a {window}-day rolling window.",
        }

    names = list(factor_returns.columns)
    series: List[Dict[str, Any]] = []
    for end in range(window, len(aligned) + 1, step):
        chunk = aligned.iloc[end - window : end]
        result = ols(chunk["portfolio"].to_numpy(), chunk[names].to_numpy(), names)
        series.append(
            {
                "date": chunk.index[-1].isoformat() if hasattr(chunk.index[-1], "isoformat")
                else str(chunk.index[-1]),
                "betas": {name: round(value, 4) for name, value in result.betas.items()},
                "r_squared": round(result.r_squared, 3),
            }
        )

    return {"available": True, "window": window, "step": step, "series": series}
