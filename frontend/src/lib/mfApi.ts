import { apiUrl } from "@/lib/api";

export interface SchemeSearchResult {
  schemeCode: number;
  schemeName: string;
}

export interface SchemeMeta {
  fund_house: string;
  scheme_type: string;
  scheme_category: string;
  scheme_code: number;
  scheme_name: string;
  isin_growth: string | null;
  isin_div_reinvestment: string | null;
}

export interface TrailingReturn {
  return_pct: number | null;
  annualised: boolean;
  cagr_pct: number | null;
  start_date: string;
  start_nav: number | null;
}

export interface RiskMetrics {
  insufficient_data?: boolean;
  volatility_pct?: number | null;
  sharpe_ratio?: number | null;
  sortino_ratio?: number | null;
  risk_free_rate_pct?: number | null;
  best_day_pct?: number | null;
  worst_day_pct?: number | null;
  positive_days_pct?: number | null;
  observations?: number;
  max_drawdown_pct?: number | null;
  max_drawdown_peak_date?: string;
  max_drawdown_trough_date?: string;
  max_drawdown_recovery_date?: string | null;
  max_drawdown_recovery_days?: number | null;
  current_drawdown_pct?: number | null;
}

export interface RollingReturn {
  years: number;
  insufficient_data?: boolean;
  observations?: number;
  average_pct?: number | null;
  median_pct?: number | null;
  min_pct?: number | null;
  max_pct?: number | null;
  std_dev_pct?: number | null;
  positive_windows_pct?: number | null;
  above_10pct_windows_pct?: number | null;
  worst_window?: { start: string; end: string };
  best_window?: { start: string; end: string };
}

export interface SchemeAnalysis {
  meta: SchemeMeta;
  error?: string;
  nav: {
    latest: number;
    latest_date: string;
    inception_date: string;
    history_days: number;
    observations: number;
  };
  trailing_returns: Record<string, TrailingReturn | null>;
  risk: RiskMetrics;
  rolling_returns: Record<string, RollingReturn>;
}

export interface NavHistory {
  meta: SchemeMeta;
  count: number;
  data: Array<{ date: string; nav: string }>;
}

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(apiUrl(path), { signal });
  if (!response.ok) {
    // The backend puts a human-readable reason in `detail` for 4xx responses;
    // surfacing it beats showing a bare status code.
    let detail = `Request failed with status ${response.status}`;
    try {
      const body = await response.json();
      if (body?.detail) detail = body.detail;
    } catch {
      // Non-JSON error body (e.g. a gateway HTML page) — keep the status text.
    }
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}

export const searchFunds = (query: string, directOnly: boolean, growthOnly: boolean, signal?: AbortSignal) =>
  getJson<{ query: string; count: number; results: SchemeSearchResult[] }>(
    `/api/mf/search?q=${encodeURIComponent(query)}&limit=50` +
      `&direct_only=${directOnly}&growth_only=${growthOnly}`,
    signal
  );

export const getFundAnalysis = (schemeCode: number | string, signal?: AbortSignal) =>
  getJson<SchemeAnalysis>(`/api/mf/${schemeCode}/analysis`, signal);

export const getNavHistory = (
  schemeCode: number | string,
  startDate?: string,
  signal?: AbortSignal
) =>
  getJson<NavHistory>(
    `/api/mf/${schemeCode}${startDate ? `?start_date=${startDate}` : ""}`,
    signal
  );

/** NAV dates arrive as DD-MM-YYYY, which JS Date cannot parse directly. */
export const parseNavDate = (value: string): Date => {
  const [day, month, year] = value.split("-").map(Number);
  return new Date(year, month - 1, day);
};

export const formatDate = (iso: string): string =>
  new Date(iso).toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });

export const formatCurrency = (value: number): string =>
  `₹${value.toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;

/** Signed percentage, e.g. "+13.72%". Nulls render as an em dash. */
export const formatPct = (value: number | null | undefined): string =>
  value === null || value === undefined ? "—" : `${value > 0 ? "+" : ""}${value.toFixed(2)}%`;

export const TRAILING_LABELS: Array<[string, string]> = [
  ["1m", "1 Month"],
  ["3m", "3 Months"],
  ["6m", "6 Months"],
  ["1y", "1 Year"],
  ["3y", "3 Years"],
  ["5y", "5 Years"],
  ["10y", "10 Years"],
  ["since_inception", "Since Inception"],
];
