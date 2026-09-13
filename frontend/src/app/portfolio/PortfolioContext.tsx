"use client";

import { createContext, useContext } from "react";
import type {
  DangerAnalysis,
  FyersStatus,
  GrowthAnalysis,
  PortfolioValuation,
  StoredPortfolio,
} from "@/lib/portfolioApi";

export const FALLBACK_DANGER: DangerAnalysis = {
  danger_score: 24,
  danger_level: "LOW RISK",
  resilience_score: 76,
  flags: [
    {
      severity: "INFO",
      category: "Diversification",
      title: "Bluechip Core Dominance",
      detail: "Portfolio is anchored by top Nifty 50 heavyweights with low idiosyncratic concentration risk.",
    },
    {
      severity: "INFO",
      category: "Tax Shield",
      title: "Section 112A Cushion",
      detail: "Long-term capital gains remain within optimal realization brackets.",
    },
  ],
  metrics: {
    top1_weight_pct: 18.2,
    top3_weight_pct: 44.5,
    hhi: 0.18,
    portfolio_beta: 0.94,
    monthly_var_95_pct: 4.8,
    monthly_cvar_95_pct: 6.9,
    small_micro_weight_pct: 0.0,
  },
  stress_tests: [
    {
      scenario_key: "covid_2020",
      name: "March 2020 Liquidity Shock",
      description: "Severe 38% broad market collapse with panic VIX spike to 84",
      benchmark_drop_pct: -38.0,
      effective_beta: 0.92,
      projected_drawdown_pct: -34.96,
      projected_loss_inr: 1205000,
      projected_recovery_value: 2242000,
    },
    {
      scenario_key: "inflation_rate_hike",
      name: "Global Rates & Commodity Spike",
      description: "Aggressive 250bps central bank rate tightening cycle",
      benchmark_drop_pct: -15.0,
      effective_beta: 0.88,
      projected_drawdown_pct: -13.2,
      projected_loss_inr: 455000,
      projected_recovery_value: 2992000,
    },
    {
      scenario_key: "nifty_10_correction",
      name: "Routine 10% Market Correction",
      description: "Standard technical pullback to 200-day moving average",
      benchmark_drop_pct: -10.0,
      effective_beta: 0.94,
      projected_drawdown_pct: -9.4,
      projected_loss_inr: 324000,
      projected_recovery_value: 3123000,
    },
  ],
};

export const FALLBACK_GROWTH: GrowthAnalysis = {
  growth_score: 76,
  growth_level: "Aggressive Compounder",
  pillars: {
    projected_cagr_pct: 14.8,
    expected_volatility_pct: 16.2,
    equity_growth_weight_pct: 88.0,
    fund_growth_weight_pct: 12.0,
  },
  monte_carlo: {
    trajectory: [
      { month: 12, year: 1, p10_inr: 3120000, p25_inr: 3450000, median_inr: 3950000, p75_inr: 4520000, p90_inr: 5120000 },
      { month: 24, year: 2, p10_inr: 3380000, p25_inr: 3980000, median_inr: 4540000, p75_inr: 5380000, p90_inr: 6380000 },
      { month: 36, year: 3, p10_inr: 3720000, p25_inr: 4620000, median_inr: 5220000, p75_inr: 6420000, p90_inr: 7920000 },
      { month: 48, year: 4, p10_inr: 4120000, p25_inr: 5350000, median_inr: 6010000, p75_inr: 7680000, p90_inr: 9850000 },
      { month: 60, year: 5, p10_inr: 4580000, p25_inr: 6210000, median_inr: 6920000, p75_inr: 9180000, p90_inr: 12240000 },
      { month: 120, year: 10, p10_inr: 7850000, p25_inr: 11950000, median_inr: 13850000, p75_inr: 19850000, p90_inr: 28950000 },
    ],
    summary: {
      initial_value: 3447000,
      expected_cagr_pct: 14.8,
      assumed_volatility_pct: 16.2,
      year_1_median_inr: 3950000,
      year_3_median_inr: 5220000,
      year_5_median_inr: 6920000,
      prob_doubling_5y_pct: 68.4,
      prob_loss_5y_pct: 4.2,
    },
  },
};

export interface PortfolioContextValue {
  portfolio: StoredPortfolio;
  hydrated: boolean;
  valuation: PortfolioValuation | null;
  danger: DangerAnalysis | null;
  growth: GrowthAnalysis | null;
  analysisIsSample: boolean;
  status: FyersStatus | null;
  loading: boolean;
  importing: boolean;
  uploadingStatement: boolean;
  error: string | null;
  notice: string | null;
  isEmpty: boolean;
  staleCount: number;
  refresh: (signal?: AbortSignal) => Promise<void>;
  importHoldings: () => Promise<void>;
  handleStatementFile: (file: File) => Promise<void>;
  removeRow: (kind: "equity" | "fund", key: string) => void;
  setPortfolio: React.Dispatch<React.SetStateAction<StoredPortfolio>>;
  setStatus: React.Dispatch<React.SetStateAction<FyersStatus | null>>;
  setNotice: React.Dispatch<React.SetStateAction<string | null>>;
  setError: React.Dispatch<React.SetStateAction<string | null>>;
  statementFileInputRef: React.RefObject<HTMLInputElement | null>;
}

export const PortfolioContext = createContext<PortfolioContextValue | null>(null);

export function usePortfolioContext(): PortfolioContextValue {
  const ctx = useContext(PortfolioContext);
  if (!ctx) {
    throw new Error("usePortfolioContext must be used within the /portfolio layout");
  }
  return ctx;
}
