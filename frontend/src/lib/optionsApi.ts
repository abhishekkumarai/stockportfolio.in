import { getJson, postJson, queryString } from "./http";
import type { EquityHoldingInput, FundHoldingInput } from "./portfolioApi";

// Mirrors backend/app/options.py. Every chain call needs a live Fyers token —
// the chain comes from the authenticated broker endpoint, not an NSE scrape.

export interface ChainRow {
  strike: number;
  option_type: "CE" | "PE";
  symbol: string;
  ltp: number;
  oi: number;
  oi_change: number;
  volume: number;
  ltp_change: number;
  bid: number;
  ask: number;
}

export interface ChainExpiry {
  expiry: string;
  date: string;
}

export interface ChainContext {
  underlying_symbol: string | null;
  spot: number | null;
  expiries: ChainExpiry[];
  call_oi_total: number | null;
  put_oi_total: number | null;
  india_vix: number | null;
}

export interface ChainResponse {
  symbol: string;
  context: ChainContext;
  rows: ChainRow[];
}

export interface BuildupRow {
  strike: number;
  option_type: "CE" | "PE";
  ltp: number;
  oi: number;
  oi_change: number;
  price_change: number;
  buildup: string;
  buildup_label: string;
}

export interface ChainAnalysis {
  available: boolean;
  reason?: string;
  symbol: string;
  context: ChainContext;
  pcr: {
    oi_pcr: number | null;
    volume_pcr: number | null;
    call_oi: number;
    put_oi: number;
    call_volume: number;
    put_volume: number;
    interpretation: string;
  };
  max_pain: {
    max_pain_strike: number;
    total_pain_at_max: number;
    pain_curve: Array<{ strike: number; total_pain: number }>;
    note: string;
  };
  oi_walls: {
    resistance: Array<{ strike: number; oi: number; oi_change: number }>;
    support: Array<{ strike: number; oi: number; oi_change: number }>;
  };
  buildup: BuildupRow[];
  iv: {
    available: boolean;
    reason?: string;
    atm_iv_pct?: number;
    otm_put_iv_pct?: number | null;
    otm_call_iv_pct?: number | null;
    skew_pct?: number | null;
    interpretation?: string;
    points?: Array<{ strike: number; option_type: "CE" | "PE"; iv_pct: number; moneyness: number }>;
  };
  strike_count: number;
}

export interface HedgePlan {
  available: boolean;
  reason?: string;
  strategy: string;
  contracts: number;
  exact_contracts: number;
  lot_size: number;
  strike: number;
  index_spot: number;
  days_to_expiry: number;
  premium_per_unit: number;
  premium_total_inr: number;
  premium_pct_of_portfolio: number;
  annualised_cost_pct: number;
  hedge_notional_inr: number;
  hedged_notional_inr: number;
  coverage_ratio: number;
  portfolio_beta: number;
  portfolio_value_inr?: number;
  greeks: Record<string, number>;
  caveats: string[];
  // The collar reports its two legs separately instead of one `strike`.
  put_strike?: number;
  call_strike?: number;
  put_premium_inr?: number;
  call_premium_inr?: number;
  net_cost_inr?: number;
  net_cost_pct_of_portfolio?: number;
  zero_cost?: boolean;
  put_greeks?: Record<string, number>;
  call_greeks?: Record<string, number>;
}

export interface PayoffLeg {
  option_type: "CE" | "PE" | "FUT";
  strike: number;
  premium: number;
  quantity: number;
  lot_size: number;
}

export interface PayoffCurve {
  available: boolean;
  reason?: string;
  curve: Array<{ price: number; payoff: number }>;
  approximate_breakevens: number[];
  max_profit: number | null;
  max_loss: number | null;
  note: string;
}

export const getChain = (
  symbol: string,
  strikeCount: number,
  timestamp: string,
  signal?: AbortSignal
) =>
  getJson<ChainResponse>(
    `/api/options/${encodeURIComponent(symbol)}/chain${queryString({
      strike_count: strikeCount,
      timestamp,
    })}`,
    { signal }
  );

export const getChainAnalysis = (
  symbol: string,
  strikeCount: number,
  timestamp: string,
  signal?: AbortSignal
) =>
  getJson<ChainAnalysis>(
    `/api/options/${encodeURIComponent(symbol)}/analysis${queryString({
      strike_count: strikeCount,
      timestamp,
    })}`,
    { signal }
  );

export interface HedgeRequest {
  portfolio?: { equity: EquityHoldingInput[]; funds: FundHoldingInput[]; cash: number };
  portfolio_value?: number;
  portfolio_beta?: number;
  index_spot: number;
  strategy: "protective_put" | "collar";
  target_max_drawdown: number;
  upside_cap?: number;
  lot_size?: number;
  days_to_expiry?: number;
  volatility?: number;
}

export const sizeHedge = (request: HedgeRequest, signal?: AbortSignal) =>
  postJson<HedgePlan>("/api/options/hedge", request, { signal });

export const payoff = (spot: number, legs: PayoffLeg[], signal?: AbortSignal) =>
  postJson<PayoffCurve>("/api/options/payoff", { spot, legs }, { signal });

export const BUILDUP_TONE: Record<string, string> = {
  long_buildup: "var(--color-buy)",
  short_covering: "var(--color-buy)",
  short_buildup: "var(--color-sell)",
  long_unwinding: "var(--color-hold)",
  neutral: "var(--text-muted)",
};
