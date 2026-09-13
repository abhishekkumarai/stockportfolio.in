import { getJson } from "./http";

export interface MacroRegime {
  regime_id: string;
  title: string;
  posture: string;
  vix_value: number;
  vix_change_5d_pct: number;
  us10y_yield: number | null;
  narrative: string;
  favored_sectors: string[];
  unfavored_sectors: string[];
}

export interface CrudeMetrics {
  current_price: number | null;
  change_5d_pct: number;
  change_20d_pct: number;
  pressure_level: "BENIGN" | "MODERATE" | "ELEVATED";
  impact_assessment: string;
}

export interface CurrencyMetrics {
  current_rate: number | null;
  change_5d_pct: number;
  change_20d_pct: number;
  stance: "TAILWIND_FOR_EXPORTS" | "HEADWIND_FOR_EXPORTS" | "STABLE";
  impact_assessment: string;
}

export interface SectorRotationItem {
  sector_key: string;
  name: string;
  current_price: number;
  return_1m_pct: number;
  return_3m_pct: number;
  relative_1m_pct: number;
  relative_3m_pct: number;
  momentum_score: number;
  status: "LEADERSHIP" | "IMPROVING" | "WEAKENING" | "LAGGING";
  rank: number;
}

export interface MacroOverview {
  available: boolean;
  reason?: string;
  regime?: MacroRegime;
  crude?: CrudeMetrics;
  currency?: CurrencyMetrics;
  gold?: {
    current_price: number | null;
    change_5d_pct: number;
  };
  us10y?: {
    yield_pct: number | null;
  };
  vix?: {
    current: number | null;
    change_5d_pct: number;
    change_pct?: number | null;
  };
  indices?: {
    nifty50: { current: number | null; change_pct: number | null };
    sensex: { current: number | null; change_pct: number | null };
  };
  sector_rotation?: SectorRotationItem[];
}

export async function getMacroOverview(signal?: AbortSignal): Promise<MacroOverview> {
  return getJson<MacroOverview>("/api/macro", { signal });
}

export async function getSectorRotation(signal?: AbortSignal): Promise<SectorRotationItem[]> {
  const data = await getJson<{ available: boolean; sector_rotation: SectorRotationItem[] }>("/api/macro/sectors", { signal });
  return data.sector_rotation || [];
}
