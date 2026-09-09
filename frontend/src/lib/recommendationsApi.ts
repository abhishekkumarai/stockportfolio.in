import { getJson, postJson, queryString } from "./http";
import type { EquityHoldingInput, FundHoldingInput } from "./portfolioApi";

// Mirrors backend/app/recommendations.py. A row is a screener row (the same
// Recommendation shape the /screener console renders) with `held` and, for a
// holding, the `position` block that prices the exit after tax.

export interface RecommendationRow {
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
  warnings: string[];
  held: boolean;
  off_index?: boolean;
  position?: ExitPosition;
  rsi14?: number | null;
  pe_ratio?: number | null;
  roce_pct?: number | null;
}

export interface ExitPosition {
  quantity: number;
  avg_cost: number;
  price: number | null;
  invested_inr?: number;
  current_value_inr?: number;
  unrealised_pnl_inr?: number;
  unrealised_pnl_pct?: number | null;
  days_held: number | null;
  term: "long" | "short";
  days_to_long_term?: number;
  estimated_exit_tax_inr?: number;
  net_proceeds_inr?: number;
  note: string;
}

export interface RecommendationsResponse {
  as_of: string;
  index: string | null;
  basis: "portfolio" | "universe";
  universe: {
    scanned: number;
    size: number;
    ranked: number;
    fundamentals_scored: number;
    cached: boolean;
  };
  summary: {
    buy: number;
    sell: number;
    holdings_scored: number;
    action_bands: Record<string, number>;
  };
  buy: RecommendationRow[];
  sell: RecommendationRow[];
  holdings_to_keep: RecommendationRow[];
  notes: string[];
  disclaimer: string;
}

export interface RecommendationQuery {
  index?: string;
  universe_limit?: number;
  fundamental_limit?: number;
  with_fundamentals?: boolean;
  buy_limit?: number;
  sell_limit?: number;
}

export interface PortfolioPayload {
  equity: EquityHoldingInput[];
  funds: FundHoldingInput[];
  cash: number;
}

/** Universe-wide: ranked buys, plus names to avoid or exit if held. */
export async function getRecommendations(
  query: RecommendationQuery = {},
  signal?: AbortSignal
): Promise<RecommendationsResponse> {
  return getJson<RecommendationsResponse>(
    `/api/recommendations${queryString(query as Record<string, unknown>)}`,
    { signal }
  );
}

/** The same lists, with the sell side judged against these holdings. */
export async function getRecommendationsForPortfolio(
  portfolio: PortfolioPayload,
  query: RecommendationQuery = {},
  signal?: AbortSignal
): Promise<RecommendationsResponse> {
  return postJson<RecommendationsResponse>(
    "/api/recommendations",
    { ...query, portfolio },
    { signal }
  );
}

/** Badge variant per action band, so buy and sell read the same everywhere. */
export const ACTION_VARIANT: Record<
  string,
  "default" | "secondary" | "destructive" | "outline"
> = {
  STRONG_BUY: "default",
  BUY: "default",
  HOLD: "secondary",
  REDUCE: "destructive",
  EXIT: "destructive",
};

export const ACTION_COLOR: Record<string, string> = {
  STRONG_BUY: "var(--color-buy)",
  BUY: "var(--color-buy)",
  HOLD: "var(--color-hold)",
  REDUCE: "var(--color-sell)",
  EXIT: "var(--color-sell)",
};
