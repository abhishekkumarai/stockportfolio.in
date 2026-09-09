import { getJson, postJson } from "./http";

// Mirrors backend/app/routes/paper.py. Every route here needs both a database
// (503 without one) and an account key (401 without one), because a paper
// ledger whose audit trail does not survive a reload is pointless.

export interface PaperAccountSummary {
  id: number;
  name: string;
  strategy: string | null;
  initial_capital: number;
  cash: number;
  active: boolean;
  created_at: string | null;
}

export interface PaperPosition {
  symbol: string;
  quantity: number;
  avg_cost: number;
  price: number;
  value: number;
  unrealised_pnl: number;
  unrealised_pnl_pct: number | null;
  realised_pnl: number;
}

export interface PaperValuation {
  paper_account_id: number;
  name: string;
  strategy: string | null;
  initial_capital: number;
  cash: number;
  holdings_value: number;
  equity: number;
  total_return_inr: number;
  total_return_pct: number | null;
  realised_pnl_inr: number;
  unrealised_pnl_inr: number;
  open_positions: PaperPosition[];
  order_count: number;
  total_fees_inr: number;
  warnings: string[];
}

export interface Divergence {
  days_live: number;
  years_live: number;
  paper_total_return_pct: number | null;
  paper_annualised_return_pct: number | null;
  backtest_cagr_pct: number | null;
  backtest_max_drawdown_pct: number | null;
  annualised_gap_pct: number | null;
  verdict: string;
  caveat: string;
}

export interface PaperOrder {
  id: number;
  symbol: string;
  side: string;
  quantity: number;
  price: number;
  fees: number;
  realised_pnl: number;
  reason: string | null;
  signal_id: number | null;
  filled_at: string | null;
}

export interface PaperSignal {
  id: number;
  symbol: string;
  action: string;
  score: number | null;
  conviction: string | null;
  reference_price: number | null;
  executed: boolean;
  skip_reason: string | null;
  generated_at: string | null;
}

export const createAccount = (displayName: string) =>
  postJson<{ id: number; access_key: string; note: string }>("/api/accounts", {
    display_name: displayName,
  });

export const whoami = (signal?: AbortSignal) =>
  getJson<{ id: number; display_name: string | null; created_at: string | null }>(
    "/api/accounts/me",
    { signal, account: true }
  );

export const listPaperAccounts = (signal?: AbortSignal) =>
  getJson<{ banner: string; count: number; accounts: PaperAccountSummary[] }>("/api/paper", {
    signal,
    account: true,
  });

export const createPaperAccount = (body: {
  name: string;
  initial_capital: number;
  strategy?: string | null;
  strategy_params?: Record<string, unknown>;
  backtest_reference?: Record<string, unknown>;
}) => postJson<{ id: number; name: string; banner: string }>("/api/paper", body, { account: true });

export const paperDetail = (id: number, signal?: AbortSignal) =>
  getJson<{
    banner: string;
    valuation: PaperValuation;
    divergence: Divergence;
    backtest_reference: Record<string, unknown> | null;
  }>(`/api/paper/${id}`, { signal, account: true });

export const paperOrders = (id: number, signal?: AbortSignal) =>
  getJson<{ orders: PaperOrder[] }>(`/api/paper/${id}/orders`, { signal, account: true });

export const paperSignals = (id: number, signal?: AbortSignal) =>
  getJson<{ count: number; executed: number; skipped: number; signals: PaperSignal[] }>(
    `/api/paper/${id}/signals`,
    { signal, account: true }
  );

export const placeOrder = (
  id: number,
  body: { symbol: string; side: "BUY" | "SELL"; quantity: number; price: number; reason?: string }
) => postJson<PaperOrder & { banner: string }>(`/api/paper/${id}/orders`, body, { account: true });

export const runStrategy = (id: number, symbols: string[]) =>
  postJson<Record<string, unknown>>(`/api/paper/${id}/run`, { symbols }, { account: true });
