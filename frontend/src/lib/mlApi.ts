import { getJson, queryString } from "./http";

export interface TradeBracket {
  entry_price: number;
  target_price: number;
  stop_loss: number;
  target_pct: number;
  stop_loss_pct: number;
  risk_reward_ratio: number;
  atr_14: number;
}

export interface RankedStockItem {
  symbol: string;
  name: string;
  sector: string | null;
  alpha_score: number;
  decile: number;
  rating: "STRONG_BUY" | "BUY" | "HOLD" | "REDUCE" | "AVOID";
  driver_pills: string[];
  trade: TradeBracket;
  tax_note: string;
}

export interface MLModelMetrics {
  rank_ic_mean: number;
  rank_ic_std: number;
  information_ratio: number;
  folds_evaluated: number;
  fold_rank_ics: number[];
  abstention_recommended: boolean;
  status: string;
}

export interface MLRankingsResponse {
  available: boolean;
  reason?: string;
  universe_index?: string;
  stocks_ranked?: number;
  model_type?: string;
  model_metrics?: MLModelMetrics;
  feature_importances?: Record<string, number>;
  rankings?: RankedStockItem[];
}

export async function getMLRankings(
  universe: string = "NIFTY50",
  signal?: AbortSignal
): Promise<MLRankingsResponse> {
  const qs = queryString({ universe });
  return getJson<MLRankingsResponse>(`/api/ml/rankings${qs}`, { signal });
}
