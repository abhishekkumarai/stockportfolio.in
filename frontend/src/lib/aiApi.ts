import { getJson, postJson } from "./http";
import type { StoredPortfolio } from "./portfolioApi";

// Mirrors backend/app/routes/ai.py. The narrator only ever restates computed
// figures, and the backend checks every number in the prose against the data
// it was given — `unsupported_figures` is that check's output, not something
// invented here.

export interface AiStatus {
  configured: boolean;
  report_model: string;
  classifier_model: string;
  note: string;
}

export interface AiReport {
  available: boolean;
  reason?: string;
  report_markdown?: string;
  model?: string;
  effort?: string;
  period?: string;
  as_of?: string;
  unsupported_figures?: string[];
  verification?: string;
  danger_score?: number | null;
  growth_score?: number | null;
}

export const aiStatus = (signal?: AbortSignal) => getJson<AiStatus>("/api/ai/status", { signal });

export const monthlyReport = (
  portfolio: StoredPortfolio,
  options: { periodLabel?: string; includeNews: boolean; effort: string },
  signal?: AbortSignal
) =>
  postJson<AiReport>(
    "/api/ai/report",
    {
      portfolio: { equity: portfolio.equity, funds: portfolio.funds, cash: portfolio.cash },
      period_label: options.periodLabel || null,
      include_news: options.includeNews,
      effort: options.effort,
    },
    { signal }
  );
