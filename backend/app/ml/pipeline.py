"""Quant ML Alpha Factor Matrix & Ranking Pipeline.

End-to-end execution:
1. Ingests OHLCV history, macro transmission data, and fundamentals.
2. Extracts point-in-time factor matrix with cross-sectional standardisation.
3. Evaluates Purged Walk-Forward Cross-Validation with 5-day embargo.
4. Checks Calibration & Abstention Gate against naive majority baseline.
5. Trains L2-regularized RidgeRanker.
6. Assigns Deciles 1 to 10 (Decile 10 = institutional Alpha top-tier).
7. Computes structured trade levels: Entry, Target (+2.0 ATR), Stop Loss (-1.5 ATR).
8. Generates feature attribution driver pills (e.g., "+Momentum 20d", "+High ROCE").
9. Encapsulates Indian STCG @ 20% & LTCG @ 12.5% tax context.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import yfinance as yf

from app import symbols as symbol_master
from app.cache import TTLCache
from app.macro import fetch_macro_snapshot
from app.ml.dataset import (
    FEATURE_COLUMNS,
    cross_sectional_standardize,
    extract_stock_features,
)
from app.ml.labeling import compute_forward_excess_returns
from app.ml.models.linear import RidgeRanker
from app.ml.validation import evaluate_out_of_sample_skill, purged_walk_forward_splits
from app.technicals import calculate_atr
from app.yf_frames import ticker_frame

logger = logging.getLogger(__name__)

# Pipeline results cache (1 hour TTL)
_pipeline_cache = TTLCache(ttl=3600.0, max_entries=8)

# Target forward horizon (10 trading days)
FORWARD_HORIZON = 10


def format_driver_pills(
    stock_z_scores: Dict[str, float],
    feature_weights: Dict[str, float],
) -> List[str]:
    """Generates human-readable driver pills explaining top positive model contributions.

    E.g.: "+Momentum 20d", "+Low D/E", "+High ROCE", "+Volume Expansion"
    """
    friendly_names = {
        "ret_20d": "20d Momentum",
        "ret_5d": "5d Velocity",
        "ret_60d": "Quarterly Trend",
        "rsi_14": "RSI Bullish Zone",
        "macd_norm": "MACD Expansion",
        "sma50_dist": "Above 50 SMA",
        "vol_surge": "Volume Accumulation",
        "beta_crude": "Crude Resilience",
        "beta_usdinr": "FX Tailwind",
        "roce": "High ROCE Quality",
        "debt_to_equity": "Low Leverage",
        "piotroski": "Piotroski Health",
        "altman_z": "Solvency Fortress",
    }

    contributions = []
    for feat, z_val in stock_z_scores.items():
        w = feature_weights.get(feat, 0.0)
        contrib = z_val * w
        if contrib > 0.05:
            label = friendly_names.get(feat, feat)
            contributions.append((contrib, f"+{label}"))

    contributions.sort(key=lambda x: x[0], reverse=True)
    return [pill for _, pill in contributions[:3]]


def structure_trade_levels(
    current_price: float,
    atr_value: float,
) -> Dict[str, Any]:
    """Computes structured volatility-scaled trade execution brackets:
    - Target: Price + 2.0 * ATR14
    - Stop Loss: Price - 1.5 * ATR14
    - Risk/Reward Ratio: 1.33:1
    """
    target = current_price + 2.0 * atr_value
    stop = current_price - 1.5 * atr_value
    stop = max(0.05, stop)

    reward_pct = ((target - current_price) / current_price) * 100.0
    risk_pct = ((current_price - stop) / current_price) * 100.0
    rr_ratio = reward_pct / risk_pct if risk_pct > 0 else 1.33

    return {
        "entry_price": round(current_price, 2),
        "target_price": round(target, 2),
        "stop_loss": round(stop, 2),
        "target_pct": round(reward_pct, 2),
        "stop_loss_pct": round(risk_pct, 2),
        "risk_reward_ratio": round(rr_ratio, 2),
        "atr_14": round(atr_value, 2),
    }


def run_quant_alpha_pipeline(
    universe_index: str = "NIFTY50",
    use_cache: bool = True,
) -> Dict[str, Any]:
    """Executes the complete Quant ML Alpha ranking pipeline over the specified universe.

    Returns:
        Structured response containing:
        - available: bool
        - model_metrics: Rank IC, IR, validation folds, abstention recommendation
        - decile_rankings: List of stock recommendations from Decile 10 (top) to Decile 1
        - feature_importances: Normalized model factor weights
    """
    cache_key = f"ml_rankings_{universe_index.upper()}"
    if use_cache:
        cached = _pipeline_cache.get(cache_key)
        if cached is not None:
            return cached

    records = symbol_master.master.universe(index=universe_index)
    if not records:
        return {
            "available": False,
            "reason": f"No symbol records found for universe '{universe_index}'.",
        }

    symbols = [r.symbol for r in records]
    tickers = [f"{s}.NS" for s in symbols]
    benchmark_ticker = "^NSEI"

    all_tickers = tickers + [benchmark_ticker]

    try:
        data = yf.download(
            tickers=all_tickers,
            period="1y",
            interval="1d",
            group_by="ticker",
            auto_adjust=True,
            progress=False,
            threads=True,
        )
    except Exception as exc:
        logger.warning("Failed downloading price data for ML alpha pipeline: %s", exc)
        return {
            "available": False,
            "reason": f"Upstream market data error: {exc}",
        }

    if data is None or data.empty:
        return {
            "available": False,
            "reason": "Empty dataset returned from upstream provider.",
        }

    bench_frame = ticker_frame(data, benchmark_ticker)
    if bench_frame is None or "Close" not in bench_frame.columns:
        return {
            "available": False,
            "reason": "Benchmark NIFTY 50 series missing from download.",
        }

    bench_closes = bench_frame["Close"].dropna()

    # Ingest macro returns for beta calculation
    macro = fetch_macro_snapshot()
    macro_frames = {}
    if macro.get("available"):
        try:
            raw_macro = yf.download(
                tickers=["BZ=F", "INR=X"],
                period="1y",
                interval="1d",
                group_by="ticker",
                auto_adjust=True,
                progress=False,
            )
            crude_f = ticker_frame(raw_macro, "BZ=F")
            inr_f = ticker_frame(raw_macro, "INR=X")
            if crude_f is not None and "Close" in crude_f.columns:
                macro_frames["crude"] = crude_f["Close"].pct_change()
            if inr_f is not None and "Close" in inr_f.columns:
                macro_frames["inr"] = inr_f["Close"].pct_change()
        except Exception:
            pass
    macro_frames["market"] = bench_closes.pct_change()

    # Build feature matrices and labels for each stock
    stock_feature_dfs: Dict[str, pd.DataFrame] = {}
    stock_targets: Dict[str, pd.Series] = {}
    latest_slices: Dict[str, pd.Series] = {}
    latest_atrs: Dict[str, float] = {}
    latest_prices: Dict[str, float] = {}

    for sym, yf_sym in zip(symbols, tickers):
        frame = ticker_frame(data, yf_sym)
        if frame is None or frame.empty or len(frame) < 60:
            continue

        feat_df = extract_stock_features(frame, macro_frames=macro_frames)
        if feat_df.empty:
            continue

        atr_series = calculate_atr(frame, period=14)
        excess_ret = compute_forward_excess_returns(
            frame["Close"],
            bench_closes,
            horizon=FORWARD_HORIZON,
        )

        stock_feature_dfs[sym] = feat_df
        stock_targets[sym] = excess_ret
        latest_slices[sym] = feat_df.iloc[-1]
        latest_prices[sym] = float(frame["Close"].iloc[-1])
        latest_atrs[sym] = float(atr_series.iloc[-1]) if not pd.isna(atr_series.iloc[-1]) else latest_prices[sym] * 0.02

    if len(stock_feature_dfs) < 10:
        return {
            "available": False,
            "reason": "Insufficient eligible symbols with complete history.",
        }

    # Stack point-in-time dataset across time for walk-forward validation
    train_rows_X: List[np.ndarray] = []
    train_rows_y: List[float] = []

    # Align common dates excluding the last FORWARD_HORIZON rows
    common_index = bench_closes.index[:-FORWARD_HORIZON]

    for dt in common_index[60:]:  # warm-up 60 bars for moving averages
        xs = []
        ys = []
        for sym, fdf in stock_feature_dfs.items():
            if dt in fdf.index and dt in stock_targets[sym].index:
                target_val = stock_targets[sym].loc[dt]
                if not pd.isna(target_val):
                    xs.append(fdf.loc[dt, FEATURE_COLUMNS].values.astype(float))
                    ys.append(float(target_val))

        if len(xs) >= 10:
            xs_mat = np.array(xs)
            # Cross-sectional standardization on each historical cross-section
            means = np.mean(xs_mat, axis=0)
            stds = np.std(xs_mat, axis=0)
            stds[stds < 1e-8] = 1.0
            z_xs = np.clip((xs_mat - means) / stds, -3.0, 3.0)

            for z_row, y_val in zip(z_xs, ys):
                train_rows_X.append(z_row)
                train_rows_y.append(y_val)

    X_train_full = np.array(train_rows_X)
    y_train_full = np.array(train_rows_y)

    # Purged Walk-Forward Cross-Validation
    splits = purged_walk_forward_splits(
        n_samples=len(X_train_full),
        n_splits=4,
        purge_window=FORWARD_HORIZON,
        embargo_window=5,
    )

    fold_preds: List[np.ndarray] = []
    fold_trues: List[np.ndarray] = []

    for tr_idx, te_idx in splits:
        ranker_cv = RidgeRanker(alpha=15.0).fit(
            X_train_full[tr_idx],
            y_train_full[tr_idx],
            feature_names=FEATURE_COLUMNS,
        )
        preds = ranker_cv.predict(X_train_full[te_idx])
        fold_preds.append(preds)
        fold_trues.append(y_train_full[te_idx])

    model_metrics = evaluate_out_of_sample_skill(fold_preds, fold_trues)

    # Fit final ranker on all historical observations
    final_ranker = RidgeRanker(alpha=15.0).fit(
        X_train_full,
        y_train_full,
        feature_names=FEATURE_COLUMNS,
    )
    feature_importances = final_ranker.get_feature_importances()
    raw_weights = final_ranker.get_raw_weights()

    # Score current cross-section
    current_symbols = list(latest_slices.keys())
    current_feat_mat = np.array([latest_slices[s][FEATURE_COLUMNS].values.astype(float) for s in current_symbols])

    # Standardize current cross-section
    curr_means = np.mean(current_feat_mat, axis=0)
    curr_stds = np.std(current_feat_mat, axis=0)
    curr_stds[curr_stds < 1e-8] = 1.0
    current_z_mat = np.clip((current_feat_mat - curr_means) / curr_stds, -3.0, 3.0)

    current_scores = final_ranker.predict(current_z_mat)

    # Rank and assign deciles (1 to 10)
    ranked_indices = np.argsort(current_scores)  # ascending
    n_stocks = len(ranked_indices)

    ranked_items: List[Dict[str, Any]] = []

    for rank_pos, idx in enumerate(ranked_indices, start=1):
        sym = current_symbols[idx]
        score = float(current_scores[idx])
        price = latest_prices[sym]
        atr_val = latest_atrs[sym]

        # Decile: 1 (worst) to 10 (top 10% best)
        decile = min(10, max(1, int(np.ceil((rank_pos / n_stocks) * 10))))

        if decile >= 9:
            rating = "STRONG_BUY" if decile == 10 else "BUY"
        elif decile >= 4:
            rating = "HOLD"
        else:
            rating = "REDUCE" if decile >= 2 else "AVOID"

        stock_z = dict(zip(FEATURE_COLUMNS, current_z_mat[idx]))
        driver_pills = format_driver_pills(stock_z, raw_weights)
        trade = structure_trade_levels(price, atr_val)

        record = symbol_master.master.lookup(sym)
        name = record.name if record else sym
        sector = record.sector if record else None

        ranked_items.append(
            {
                "symbol": sym,
                "name": name,
                "sector": sector,
                "alpha_score": round(score, 4),
                "decile": decile,
                "rating": rating,
                "driver_pills": driver_pills,
                "trade": trade,
                "tax_note": "Exit < 365d: STCG @ 20% | Exit >= 365d: LTCG @ 12.5% (>1.25L exemption)",
            }
        )

    # Sort descending by decile and alpha score (Top picks first)
    ranked_items.sort(key=lambda x: (x["decile"], x["alpha_score"]), reverse=True)

    payload = {
        "available": True,
        "universe_index": universe_index.upper(),
        "stocks_ranked": len(ranked_items),
        "model_type": "RidgeRanker (L2 Regularized)",
        "model_metrics": model_metrics,
        "feature_importances": feature_importances,
        "rankings": ranked_items,
    }

    _pipeline_cache.set(cache_key, payload)
    return payload
