import { getJson, postJson } from "./http";
import type { StoredPortfolio } from "./portfolioApi";

// Mirrors backend/app/routes/quant.py. Everything here shares one expensive
// precondition — an aligned matrix of daily returns for every equity holding —
// and one distinctive failure: not enough overlapping history, reported as 422.

export type OptimiserMethod = "hrp" | "risk_parity" | "min_variance" | "max_sharpe";

export interface MethodInfo {
  name: OptimiserMethod;
  label: string;
  recommended?: boolean;
  note: string;
}

export interface CoverageReport {
  [key: string]: unknown;
}

export interface FrontierPoint {
  expected_return_pct: number;
  volatility_pct: number;
  sharpe: number;
  weights: Record<string, number>;
}

export interface OptimiseResult {
  method: string;
  converged: boolean;
  weights: Record<string, number>;
  expected_return_pct: number;
  volatility_pct: number;
  sharpe: number;
  effective_holdings: number;
  max_weight: number;
  risk_contributions?: Record<string, number>;
  clustering?: { method: string; leaf_order: string[] };
  why?: string;
  current_weights: Record<string, number>;
  drift: Record<string, number>;
  coverage: CoverageReport;
  frontier?: {
    points: FrontierPoint[];
    min_variance: OptimiseResult;
    max_sharpe: OptimiseResult;
    requested_points: number;
    solved_points: number;
  };
}

export interface FactorBeta {
  beta: number;
  label: string;
  t_stat: number | null;
  contribution_pct: number;
}

export interface FactorResult {
  available: boolean;
  reason?: string;
  observations?: number;
  alpha_annual_pct?: number;
  r_squared?: number;
  adjusted_r_squared?: number;
  betas?: Record<string, FactorBeta>;
  attribution?: {
    total_excess_return_pct: number;
    explained_by_factors_pct: number;
    idiosyncratic_pct: number;
    share_explained: number | null;
  };
  interpretation?: string;
  caveats?: string[];
  missing_factors?: string[];
  rolling?: Record<string, Array<{ date: string; beta: number }>>;
  weights_note?: string;
}

export interface RegimeResult {
  available: boolean;
  reason?: string;
  current_regime?: string;
  current_regime_label?: string;
  days_in_regime?: number;
  guidance?: string;
  metrics?: {
    volatility_ratio: number;
    annualised_volatility_pct: number;
    trend_efficiency: number;
    drawdown_20d_pct: number;
    average_correlation: number | null;
  };
  distribution?: Record<string, number>;
  transitions?: Array<{ date: string; from: string; to: string }>;
  transition_count?: number;
  history?: Array<{ date: string; regime: string }>;
  note?: string;
  benchmark?: string;
  used_portfolio_correlation?: boolean;
}

export interface TargetOrder {
  action: "BUY" | "TRIM" | "HOLD";
  key: string;
  name: string;
  kind: string;
  units: number;
  estimated_price: number;
  estimated_amount: number;
  current_weight_pct: number;
  target_weight_pct: number;
  realised_gain_inr: number;
  tax_treatment: string;
  tax_impact_inr: number;
  reason: string;
}

export interface TargetRebalancePlan {
  mode: string;
  financial_year: string;
  orders: TargetOrder[];
  cash_inflow_inr: number;
  proceeds_from_trims_inr: number;
  cash_deployed_inr: number;
  cash_remaining_inr: number;
  tax_summary: Record<string, number>;
  harvest_candidates: Array<Record<string, unknown>>;
  notes: string[];
  disclaimer: string;
  target_source: string;
  optimisation?: {
    method: string;
    expected_return_pct: number;
    volatility_pct: number;
    effective_holdings: number;
  };
}

const portfolioBody = (portfolio: StoredPortfolio) => ({
  equity: portfolio.equity,
  funds: portfolio.funds,
  cash: portfolio.cash,
});

export const listMethods = (signal?: AbortSignal) =>
  getJson<{ methods: MethodInfo[] }>("/api/quant/methods", { signal });

export const optimise = (
  portfolio: StoredPortfolio,
  options: { method: OptimiserMethod; maxWeight: number; period: string; includeFrontier: boolean },
  signal?: AbortSignal
) =>
  postJson<OptimiseResult>(
    "/api/quant/optimise",
    {
      portfolio: portfolioBody(portfolio),
      method: options.method,
      max_weight: options.maxWeight,
      period: options.period,
      include_frontier: options.includeFrontier,
    },
    { signal }
  );

export const factorExposures = (
  portfolio: StoredPortfolio,
  period: string,
  rolling: boolean,
  signal?: AbortSignal
) =>
  postJson<FactorResult>(
    "/api/quant/factors",
    { portfolio: portfolioBody(portfolio), period, rolling },
    { signal }
  );

export const marketRegime = (
  portfolio: StoredPortfolio | null,
  period: string,
  signal?: AbortSignal
) =>
  postJson<RegimeResult>(
    "/api/quant/regime",
    { portfolio: portfolio ? portfolioBody(portfolio) : null, period },
    { signal }
  );

export const rebalanceToTarget = (
  portfolio: StoredPortfolio,
  options: {
    method: OptimiserMethod;
    cashInflow: number;
    allowSelling: boolean;
    driftTolerance: number;
    maxWeight: number;
    period: string;
    targetWeights?: Record<string, number> | null;
  },
  signal?: AbortSignal
) =>
  postJson<TargetRebalancePlan>(
    "/api/quant/rebalance",
    {
      portfolio: portfolioBody(portfolio),
      method: options.method,
      target_weights: options.targetWeights ?? null,
      cash_inflow: options.cashInflow,
      drift_tolerance: options.driftTolerance,
      allow_selling: options.allowSelling,
      max_weight: options.maxWeight,
      period: options.period,
    },
    { signal }
  );

export const REGIME_TONE: Record<string, string> = {
  trending_up: "var(--color-buy)",
  trending_down: "var(--color-sell)",
  crisis: "var(--color-sell)",
  choppy: "var(--color-hold)",
};
