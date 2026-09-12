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
    if (process.env.NEXT_PUBLIC_DISABLE_AUTH === "true") {
      return "DOCKER-LOCAL-DEV-TOKEN";
    }
    return null;
  }
  const token = window.sessionStorage.getItem(TOKEN_KEY);
  if (token) return token;
  if (isAuthDisabled()) {
    return "DOCKER-LOCAL-DEV-TOKEN";
  }
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

// ---- local persistence ----------------------------------------------------

const STORAGE_KEY = "stockportfolio.holdings.v1";

export interface StoredPortfolio {
  equity: EquityHoldingInput[];
  funds: FundHoldingInput[];
  cash: number;
}

export const EMPTY_PORTFOLIO: StoredPortfolio = { equity: [], funds: [], cash: 0 };

export const DEFAULT_INSTITUTIONAL_PORTFOLIO: StoredPortfolio = {
  equity: [
    { symbol: "RELIANCE", quantity: 310, avg_cost: 2740.0, buy_date: "2023-04-12" },
    { symbol: "TCS", quantity: 145, avg_cost: 3820.0, buy_date: "2023-06-18" },
    { symbol: "HDFCBANK", quantity: 380, avg_cost: 1580.0, buy_date: "2023-09-05" },
    { symbol: "INFY", quantity: 260, avg_cost: 1720.0, buy_date: "2023-08-22" },
    { symbol: "ICICIBANK", quantity: 290, avg_cost: 1040.0, buy_date: "2023-10-15" },
    { symbol: "TATAMOTORS", quantity: 340, avg_cost: 920.0, buy_date: "2023-11-02" },
    { symbol: "LT", quantity: 120, avg_cost: 3450.0, buy_date: "2023-07-19" },
    { symbol: "BHARTIARTL", quantity: 250, avg_cost: 1420.0, buy_date: "2024-01-10" },
  ],
  funds: [
    { scheme_code: 120503, units: 1450.5, avg_nav: 68.4, buy_date: "2023-03-15" },
  ],
  cash: 150000,
};

export function loadPortfolio(allowDefaultSeed: boolean = true): StoredPortfolio {
  if (typeof window === "undefined") return allowDefaultSeed ? DEFAULT_INSTITUTIONAL_PORTFOLIO : EMPTY_PORTFOLIO;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      if (allowDefaultSeed) {
        window.localStorage.setItem(STORAGE_KEY, JSON.stringify(DEFAULT_INSTITUTIONAL_PORTFOLIO));
        return DEFAULT_INSTITUTIONAL_PORTFOLIO;
      }
      return EMPTY_PORTFOLIO;
    }
    const parsed = JSON.parse(raw);
    const result: StoredPortfolio = {
      equity: Array.isArray(parsed.equity) ? parsed.equity : [],
      funds: Array.isArray(parsed.funds) ? parsed.funds : [],
      cash: typeof parsed.cash === "number" ? parsed.cash : 0,
    };
    if (allowDefaultSeed && result.equity.length === 0 && result.funds.length === 0) {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(DEFAULT_INSTITUTIONAL_PORTFOLIO));
      return DEFAULT_INSTITUTIONAL_PORTFOLIO;
    }
    return result;
  } catch {
    return allowDefaultSeed ? DEFAULT_INSTITUTIONAL_PORTFOLIO : EMPTY_PORTFOLIO;
  }
}

export function savePortfolio(portfolio: StoredPortfolio): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(portfolio));
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
