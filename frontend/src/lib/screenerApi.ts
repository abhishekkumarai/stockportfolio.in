import { getJson, queryString } from "./http";

// Mirrors backend/app/screener.py — `ScreenRow.as_dict()` is a Recommendation
// with the raw technical and fundamental metrics flattened alongside it.

export interface ScreenerFilterVocabulary {
  indices: string[];
  sectors: string[];
  caps: string[];
  actions: string[];
  symbol_master: Record<string, unknown>;
}

export interface ScoreComponent {
  score: number | null;
  coverage: number;
  reasons?: string[];
  [key: string]: unknown;
}

export interface ScreenerRow {
  symbol: string;
  name: string;
  sector: string | null;
  cap: string | null;
  price: number | null;
  score: number | null;
  action: string | null;
  action_label: string | null;
  conviction: string | null;
  coverage: number;
  reasons: string[];
  components: Record<string, ScoreComponent>;
  warnings: string[];
  rsi14: number | null;
  adx: number | null;
  above_sma200: boolean | null;
  golden_cross: boolean | null;
  pe_ratio: number | null;
  roce_pct: number | null;
  roe_pct: number | null;
  debt_to_equity: number | null;
  pledged_pct: number | null;
  sales_growth_pct: number | null;
}

export interface ScreenerResponse {
  count: number;
  scanned: number;
  universe: number;
  index: string | null;
  fundamentals_scored: number;
  results: ScreenerRow[];
  cached: boolean;
  notes: string[];
}

export interface ScreenerQuery {
  index?: string;
  sector?: string;
  cap?: string;
  fno_only?: boolean;
  min_score?: number;
  actions?: string[];
  rsi_min?: number;
  rsi_max?: number;
  above_sma200?: boolean;
  golden_cross?: boolean;
  min_adx?: number;
  min_roce?: number;
  min_roe?: number;
  max_pe?: number;
  max_debt_to_equity?: number;
  max_pledged_pct?: number;
  min_sales_growth?: number;
  limit?: number;
  universe_limit?: number;
  with_fundamentals?: boolean;
  fundamental_limit?: number;
}

export const getScreenerFilters = (signal?: AbortSignal) =>
  getJson<ScreenerFilterVocabulary>("/api/screener/filters", { signal });

export const runScreen = (query: ScreenerQuery, signal?: AbortSignal) =>
  getJson<ScreenerResponse>(`/api/screener/run${queryString({ ...query })}`, { signal });

export const ACTION_TONE: Record<string, string> = {
  STRONG_BUY: "var(--color-buy)",
  BUY: "var(--color-buy)",
  HOLD: "var(--color-hold)",
  REDUCE: "var(--color-sell)",
  EXIT: "var(--color-sell)",
};

/** A CSV of exactly what the table shows, for a watchlist import elsewhere. */
export function rowsToCsv(rows: ScreenerRow[]): string {
  const header = [
    "symbol", "name", "sector", "cap", "price", "score", "action", "conviction",
    "coverage", "rsi14", "adx", "above_sma200", "golden_cross", "pe_ratio",
    "roce_pct", "roe_pct", "debt_to_equity", "pledged_pct", "sales_growth_pct",
  ];
  const escape = (value: unknown) => {
    if (value === null || value === undefined) return "";
    const text = String(value);
    return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
  };
  const lines = rows.map((row) =>
    header.map((key) => escape((row as unknown as Record<string, unknown>)[key])).join(",")
  );
  return [header.join(","), ...lines].join("\n");
}
