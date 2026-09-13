import { apiUrl } from "./api";

// ---- types (mirror backend/app/schemas.py and portfolio.py) ----------------

export interface EquityHoldingInput {
  symbol: string;
  quantity: number;
  avg_cost: number;
  buy_date?: string | null;
}

export interface FundHoldingInput {
  scheme_code: number;
  units: number;
  avg_nav: number;
  buy_date?: string | null;
}

export interface PricedRow {
  kind: "equity" | "fund";
  key: string;
  name: string;
  quantity: number;
  avg_cost: number;
  price: number | null;
  price_source: "fyers" | "yfinance" | "mfapi" | null;
  invested: number;
  current_value: number | null;
  pnl: number | null;
  pnl_pct: number | null;
  weight_pct: number | null;
  sector: string | null;
  cap: string | null;
  category: string | null;
  buy_date: string | null;
  warnings: string[];
}

export interface AllocationSlice {
  label: string;
  value: number;
  weight_pct: number | null;
}

export interface PortfolioValuation {
  totals: {
    invested: number;
    current_value: number;
    cash: number;
    pnl: number;
    pnl_pct: number | null;
    holdings: number;
    priced: number;
    unpriced: number;
  };
  holdings: PricedRow[];
  allocation: {
    asset_class: AllocationSlice[];
    sector: AllocationSlice[];
    cap: AllocationSlice[];
    fund_category: AllocationSlice[];
  };
  warnings: string[];
}

export interface DangerFlag {
  severity: "CRITICAL" | "WARNING" | "INFO";
  category: string;
  title: string;
  detail: string;
}

export interface StressScenario {
  scenario_key: string;
  name: string;
  description: string;
  benchmark_drop_pct: number;
  effective_beta: number;
  projected_drawdown_pct: number;
  projected_loss_inr: number;
  projected_recovery_value: number;
}

export interface DangerAnalysis {
  danger_score: number;
  danger_level: string;
  resilience_score: number;
  flags: DangerFlag[];
  metrics: {
    top1_weight_pct: number;
    top3_weight_pct: number;
    hhi: number;
    portfolio_beta: number;
    monthly_var_95_pct: number;
    monthly_cvar_95_pct: number;
    small_micro_weight_pct: number;
  };
  stress_tests: StressScenario[];
}

export interface MonteCarloTrajectory {
  month: number;
  year: number;
  p10_inr: number;
  p25_inr: number;
  median_inr: number;
  p75_inr: number;
  p90_inr: number;
}

export interface GrowthAnalysis {
  growth_score: number;
  growth_level: string;
  pillars: {
    projected_cagr_pct: number;
    expected_volatility_pct: number;
    equity_growth_weight_pct: number;
    fund_growth_weight_pct: number;
  };
  monte_carlo: {
    trajectory: MonteCarloTrajectory[];
    summary: {
      initial_value: number;
      expected_cagr_pct: number;
      assumed_volatility_pct: number;
      year_1_median_inr: number;
      year_3_median_inr: number;
      year_5_median_inr: number;
      prob_doubling_5y_pct: number;
      prob_loss_5y_pct: number;
    };
  };
}

export interface FullAnalysisResponse {
  valuation: PortfolioValuation;
  danger: DangerAnalysis;
  growth: GrowthAnalysis;
  status: string;
}

export interface RebalanceOrder {
  action: "BUY" | "TRIM" | "HOLD";
  key: string;
  name: string;
  kind: string;
  units: number;
  estimated_price: number;
  estimated_amount: number;
  tax_impact_inr: number;
  reason: string;
}

export interface RebalancePlan {
  mode: string;
  cash_allocated_inr?: number;
  cash_remaining_inr?: number;
  orders: RebalanceOrder[];
  tax_summary: {
    total_tax_inr?: number;
    total_estimated_tax_inr?: number;
    tax_loss_harvest_generated_inr?: number;
    net_effective_tax_inr?: number;
    tax_saved_by_inflow_mode_inr?: number;
  };
  notes: string[];
}

export interface NewsArticle {
  symbol: string;
  title: string;
  url: string;
  source: string;
  published_at: string;
  tag: string;
  impact: "BULLISH" | "BEARISH" | "NEUTRAL";
  impact_label: string;
  sentiment_score: number;
}

export interface NewsResponse {
  count: number;
  articles: NewsArticle[];
}

export interface FyersHolding {
  symbol: string;
  quantity: number;
  avg_cost: number;
  ltp: number | null;
  name: string | null;
  sector: string | null;
  cap: string | null;
  holding_type: string;
  buy_date: string | null;
}

export interface FyersHoldingsResponse {
  count: number;
  holdings: FyersHolding[];
  total_investment: number;
  total_current_value: number;
  total_pnl: number;
  total_pnl_pct: number | null;
  unknown_symbols: string[];
}

export interface FyersStatus {
  connected: boolean;
  name?: string;
  fy_id?: string;
  email?: string;
  reason?: string;
  login_url?: string;
}

// ---- the Fyers token ------------------------------------------------------

const TOKEN_KEY = "fyers_token";

export function isAuthDisabled(): boolean {
  return (
    process.env.NEXT_PUBLIC_DISABLE_AUTH === "true" ||
    (typeof window !== "undefined" &&
      (window.location.hostname === "localhost" ||
        window.location.hostname === "127.0.0.1"))
  );
}

export function getToken(): string | null {
  if (typeof window === "undefined") {
    return null;
  }
  const token = window.sessionStorage.getItem(TOKEN_KEY);
  if (token) return token;
  return null;
}

export function setToken(token: string): void {
  window.sessionStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  window.sessionStorage.removeItem(TOKEN_KEY);
}

export function captureTokenFromUrl(): boolean {
  if (typeof window === "undefined") return false;
  const hash = window.location.hash;
  if (!hash.includes("fyers_token=")) return false;

  const token = new URLSearchParams(hash.slice(1)).get("fyers_token");
  if (!token) return false;

  setToken(token);
  window.history.replaceState(null, "", window.location.pathname + window.location.search);
  return true;
}

function authHeaders(): HeadersInit {
  const token = getToken();
  return token ? { "X-Fyers-Token": token } : {};
}

async function handle<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      // Non-JSON error body
    }
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}

// ---- calls ----------------------------------------------------------------

export async function getFyersStatus(signal?: AbortSignal): Promise<FyersStatus> {
  const response = await fetch(apiUrl("/api/fyers/status"), {
    headers: authHeaders(),
    signal,
  });
  return handle<FyersStatus>(response);
}

export async function getFyersHoldings(signal?: AbortSignal): Promise<FyersHoldingsResponse> {
  const response = await fetch(apiUrl("/api/fyers/holdings"), {
    headers: authHeaders(),
    signal,
  });
  return handle<FyersHoldingsResponse>(response);
}

export async function valuePortfolio(
  equity: EquityHoldingInput[],
  funds: FundHoldingInput[],
  cash: number,
  signal?: AbortSignal
): Promise<PortfolioValuation> {
  const response = await fetch(apiUrl("/api/portfolio/value"), {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ equity, funds, cash }),
    signal,
  });
  return handle<PortfolioValuation>(response);
}

export async function analysePortfolio(
  equity: EquityHoldingInput[],
  funds: FundHoldingInput[],
  cash: number,
  signal?: AbortSignal
): Promise<FullAnalysisResponse> {
  const response = await fetch(apiUrl("/api/portfolio/analyse"), {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ equity, funds, cash }),
    signal,
  });
  return handle<FullAnalysisResponse>(response);
}

export async function rebalancePortfolio(
  equity: EquityHoldingInput[],
  funds: FundHoldingInput[],
  cash: number,
  cashInflow: number = 0,
  mode: string = "zero_tax_inflow",
  signal?: AbortSignal
): Promise<RebalancePlan> {
  const response = await fetch(apiUrl("/api/portfolio/rebalance"), {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({
      portfolio: { equity, funds, cash },
      cash_inflow: cashInflow,
      drift_tolerance: 0.05,
      mode: mode,
    }),
    signal,
  });
  return handle<RebalancePlan>(response);
}

export async function getPortfolioNews(
  equity: EquityHoldingInput[],
  signal?: AbortSignal
): Promise<NewsResponse> {
  const response = await fetch(apiUrl("/api/portfolio/news"), {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ equity, funds: [], cash: 0 }),
    signal,
  });
  return handle<NewsResponse>(response);
}

export const loginUrl = () => apiUrl("/api/fyers/login");

// ---- offline statement importer -------------------------------------------

export interface OfflineStatementFile {
  name: string;
  size_bytes: number;
  modified_at: string;
}

export interface OfflineImportResult {
  status: string;
  file: string;
  statement: {
    metadata: {
      client_id: string;
      statement_title: string;
      as_of_date: string | null;
      file_name: string;
      sheet_names: string[];
    };
    equity_summary?: {
      invested_value: number;
      present_value: number;
      unrealized_pnl: number;
      unrealized_pnl_pct: number;
    };
    mf_summary?: {
      invested_value: number;
      present_value: number;
      unrealized_pnl: number;
      unrealized_pnl_pct: number;
    };
    combined_summary?: {
      invested_value: number;
      present_value: number;
      unrealized_pnl: number;
      unrealized_pnl_pct: number;
    };
    equity_holdings: Array<{
      symbol: string;
      isin: string;
      sector?: string | null;
      quantity_available: number;
      average_price: number;
      previous_closing_price?: number | null;
      unrealized_pnl?: number | null;
      unrealized_pnl_pct?: number | null;
    }>;
    mf_holdings: Array<{
      symbol: string;
      isin: string;
      instrument_type?: string | null;
      quantity_available: number;
      average_price: number;
      previous_closing_price?: number | null;
      unrealized_pnl?: number | null;
      unrealized_pnl_pct?: number | null;
    }>;
  };
  portfolio: StoredPortfolio;
  report: {
    client_id: string;
    as_of_date: string | null;
    equities_imported: number;
    equities_parsed: number;
    funds_imported: number;
    funds_parsed: number;
    unresolved_funds: any[];
  };
  valuation?: PortfolioValuation;
}

export async function getOfflineFiles(): Promise<{ files: OfflineStatementFile[]; count: number }> {
  const response = await fetch(apiUrl("/api/portfolio/offline/files"));
  return handle(response);
}

export async function importOfflineStatement(filename?: string): Promise<OfflineImportResult> {
  const url = filename
    ? apiUrl(`/api/portfolio/offline/import?filename=${encodeURIComponent(filename)}`)
    : apiUrl("/api/portfolio/offline/import");
  const response = await fetch(url, { method: "POST" });
  return handle<OfflineImportResult>(response);
}

export async function uploadStatementFile(file: File): Promise<OfflineImportResult> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(apiUrl("/api/portfolio/upload-statement"), {
    method: "POST",
    body: formData,
  });
  return handle<OfflineImportResult>(response);
}

// ---- local persistence ----------------------------------------------------

const STORAGE_KEY = "stockportfolio.holdings.v1";

export interface StoredPortfolio {
  equity: EquityHoldingInput[];
  funds: FundHoldingInput[];
  cash: number;
}

export const EMPTY_PORTFOLIO: StoredPortfolio = { equity: [], funds: [], cash: 0 };

export function loadPortfolio(): StoredPortfolio {
  if (typeof window === "undefined") return EMPTY_PORTFOLIO;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return EMPTY_PORTFOLIO;
    const parsed = JSON.parse(raw);
    return {
      equity: Array.isArray(parsed.equity) ? parsed.equity : [],
      funds: Array.isArray(parsed.funds) ? parsed.funds : [],
      cash: typeof parsed.cash === "number" ? parsed.cash : 0,
    };
  } catch {
    return EMPTY_PORTFOLIO;
  }
}

export function savePortfolio(portfolio: StoredPortfolio): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(portfolio));
  window.dispatchEvent(new Event("portfolio-updated"));
}

// ---- formatting -----------------------------------------------------------

export const formatCurrency = (value: number | null): string =>
  value === null
    ? "—"
    : new Intl.NumberFormat("en-IN", {
        style: "currency",
        currency: "INR",
        maximumFractionDigits: 0,
      }).format(value);

export const formatNumber = (value: number | null, digits = 2): string =>
  value === null
    ? "—"
    : new Intl.NumberFormat("en-IN", {
        minimumFractionDigits: digits,
        maximumFractionDigits: digits,
      }).format(value);

export const formatPct = (value: number | null): string =>
  value === null ? "—" : `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;

export const toneFor = (value: number | null): string =>
  value === null
    ? "var(--text-muted)"
    : value > 0
      ? "var(--color-buy)"
      : value < 0
        ? "var(--color-sell)"
        : "var(--text-secondary)";

export const PRICE_SOURCE_LABEL: Record<string, string> = {
  fyers: "Live",
  yfinance: "Delayed",
  mfapi: "NAV",
};
