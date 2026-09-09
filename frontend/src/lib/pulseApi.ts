import { getJson, queryString } from "./http";

export interface MarketBreadth {
  advances: number;
  declines: number;
  unchanged: number;
  total: number;
  breadth_ratio: number;
  advance_pct: number;
  sentiment: "BULLISH_EXPANSION" | "BEARISH_DIVERGENCE" | "NEUTRAL";
  description: string;
}

export interface VolumeShocker {
  symbol: string;
  name: string;
  current_price: number;
  change_pct: number;
  volume: number;
  sma20_volume: number;
  volume_surge_ratio: number;
  tag: "INSTITUTIONAL_ACCUMULATION" | "VOLUME_EXPANSION";
}

export interface BreakoutCandidate {
  symbol: string;
  name: string;
  current_price: number;
  high_52w: number;
  distance_pct: number;
  change_pct: number;
  status: "NEW_52W_HIGH" | "NEAR_52W_BREAKOUT" | "VCP_BREAKOUT" | "VCP_CONSOLIDATION";
  vcp_contracted: boolean;
}

export interface MarketPulseResponse {
  available: boolean;
  reason?: string;
  universe_index?: string;
  scanned_symbols?: number;
  breadth?: MarketBreadth;
  volume_shockers?: VolumeShocker[];
  breakouts?: BreakoutCandidate[];
}

export async function getMarketPulse(
  universe: string = "NIFTY50",
  signal?: AbortSignal
): Promise<MarketPulseResponse> {
  const qs = queryString({ universe });
  return getJson<MarketPulseResponse>(`/api/market-pulse${qs}`, { signal });
}
