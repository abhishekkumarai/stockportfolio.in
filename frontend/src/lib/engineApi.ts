import { getJson, postJson } from "./http";

// Mirrors backend/app/routes/engine.py — the v2 engine, which fills at the
// next bar's open rather than the signal bar's close. The Phase-2 backtester
// behind /api/backtest is left alone; this is the honest one.

export interface StrategySpec {
  name: string;
  label: string;
  family: string;
  params: Record<string, number>;
  ranges: Record<string, Array<number | string>>;
}

export interface TradeStatistics {
  trade_count: number;
  note?: string;
  wins?: number;
  losses?: number;
  win_rate_pct?: number;
  avg_win_inr?: number;
  avg_loss_inr?: number;
  payoff_ratio?: number | null;
  profit_factor?: number | null;
}

export interface Performance {
  available: boolean;
  reason?: string;
  start_date?: string | null;
  end_date?: string | null;
  years?: number;
  initial_capital?: number;
  final_equity?: number;
  total_return_pct?: number | null;
  cagr_pct?: number | null;
  volatility_pct?: number | null;
  sharpe?: number | null;
  sortino?: number | null;
  calmar?: number | null;
  max_drawdown_pct?: number | null;
  drawdown_recovered?: boolean;
  underwater_bars?: number;
  exposure_pct?: number | null;
  turnover_x?: number | null;
  trades?: TradeStatistics;
  risk_free_rate_pct?: number;
}

export interface EngineTrade {
  symbol: string;
  quantity: number;
  entry_date: string;
  entry_price: number;
  exit_date: string;
  exit_price: number;
  pnl: number;
  return_pct: number;
  bars_held: number;
  fees: number;
  reason: string;
}

export interface PermutationTest {
  available: boolean;
  reason?: string;
  permutations?: number;
  observations?: number;
  actual_return_pct?: number;
  actual_sharpe?: number;
  permuted_return_mean_pct?: number;
  permuted_return_p95_pct?: number;
  p_value_return?: number;
  p_value_sharpe?: number;
  significant_at_5pct?: boolean;
  verdict?: string;
  caveat?: string;
}

export interface EngineRunResult {
  strategy: Record<string, unknown>;
  symbol: string;
  bars: number;
  warmup_bars: number;
  tradeable_bars: number;
  performance: Performance;
  benchmark: Performance;
  alpha_vs_buy_hold_pct: number | null;
  equity_curve: Array<{ date: string; equity: number; cash: number }>;
  trades: EngineTrade[];
  orders: Array<Record<string, unknown>>;
  final_cash: number;
  open_positions: Array<{ symbol: string; quantity: number; avg_cost: number }>;
  permutation_test?: PermutationTest;
}

export interface WalkForwardFold {
  fold?: number;
  skipped?: boolean;
  reason?: string;
  in_sample?: Record<string, unknown>;
  out_of_sample?: Record<string, unknown>;
  best_params?: Record<string, number | string>;
  in_sample_return_pct?: number | null;
  out_of_sample_return_pct?: number | null;
  [key: string]: unknown;
}

export interface WalkForwardResult {
  symbol: string;
  strategy: string;
  folds: WalkForwardFold[];
  completed_folds: number;
  mean_in_sample_return_pct: number | null;
  mean_out_of_sample_return_pct: number | null;
  walk_forward_efficiency: number | null;
  positive_oos_folds: number;
  distinct_parameter_sets: number;
  verdict: string;
  grid_combinations: number;
}

export interface CostConfig {
  brokerage_pct: number;
  brokerage_cap: number;
  stt_pct: number;
  slippage_pct: number;
}

export interface RunPayload {
  symbol: string;
  start: string;
  end: string;
  strategy: string;
  params?: Record<string, number>;
  initial_capital: number;
  sizer: { name: string; params: Record<string, number> };
  costs: CostConfig;
  permutation_test?: boolean;
  permutations?: number;
}

export interface WalkForwardPayload {
  symbol: string;
  start: string;
  end: string;
  strategy: string;
  initial_capital: number;
  sizer: { name: string; params: Record<string, number> };
  costs: CostConfig;
  folds: number;
  in_sample_ratio: number;
  objective: string;
  ranges?: Record<string, Array<number | string>>;
}

export const listStrategies = (signal?: AbortSignal) =>
  getJson<{ count: number; strategies: StrategySpec[] }>("/api/engine/strategies", { signal });

export const runEngine = (payload: RunPayload, signal?: AbortSignal) =>
  postJson<EngineRunResult>("/api/engine/run", payload, { signal });

export const walkForward = (payload: WalkForwardPayload, signal?: AbortSignal) =>
  postJson<WalkForwardResult>("/api/engine/walk-forward", payload, { signal });

export const SIZERS = [
  { name: "percent", label: "Percent of equity", note: "A fixed share of the account per position." },
  { name: "fixed", label: "Fixed quantity", note: "The same number of shares every time." },
  { name: "volatility", label: "Volatility-targeted", note: "Smaller positions in noisier names." },
  { name: "kelly", label: "Fractional Kelly", note: "Sized from the strategy's own edge estimate." },
];

export const OBJECTIVES = ["sharpe", "sortino", "calmar", "total_return", "sqn"];
