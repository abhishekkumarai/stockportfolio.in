"use client";

import { formatCurrency } from "@/lib/portfolioApi";
import AnalysisGate from "./AnalysisGate";
import EmptyPortfolioNotice from "./EmptyPortfolioNotice";
import { FALLBACK_DANGER, FALLBACK_GROWTH, usePortfolioContext } from "./PortfolioContext";
import WealthCone from "./WealthCone";

export default function OverviewView() {
  const { danger: rawDanger, growth: rawGrowth } = usePortfolioContext();
  const danger = rawDanger ?? FALLBACK_DANGER;
  const growth = rawGrowth ?? FALLBACK_GROWTH;

  const dangerTone =
    danger.danger_score > 60
      ? "var(--color-sell)"
      : danger.danger_score > 35
        ? "var(--color-hold)"
        : "var(--color-buy)";

  const growthTone =
    growth.growth_score > 70
      ? "var(--color-buy)"
      : growth.growth_score > 45
        ? "var(--accent-cyan)"
        : "var(--text-secondary)";

  return (
    <div>
      <div style={{ marginBottom: 20 }}>
        <h1 style={{ margin: 0, fontSize: "1.6rem" }}>Wealth &amp; VaR Radar</h1>
        <p style={{ color: "var(--text-secondary)", margin: "6px 0 0" }}>
          Real-time capital preservation and growth trajectory diagnostics.
        </p>
      </div>

      <EmptyPortfolioNotice />

      <AnalysisGate>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 16, marginBottom: 20 }}>
        {/* Danger Card */}
        <div className="glass-panel" style={{ borderLeft: `4px solid ${dangerTone}`, padding: "18px 20px" }}>
          <div style={{ color: "var(--text-muted)", fontSize: "0.8rem", textTransform: "uppercase", letterSpacing: "0.05em" }}>
            Danger / Tail Risk Radar
          </div>
          <div style={{ display: "flex", alignItems: "baseline", gap: 10, marginTop: 6 }}>
            <span style={{ fontSize: "2.2rem", fontWeight: 700, color: dangerTone }}>
              {danger.danger_score}
            </span>
            <span style={{ color: "var(--text-muted)", fontSize: "1rem" }}>/ 100</span>
            <span style={{ fontSize: "0.95rem", fontWeight: 600, color: dangerTone, marginLeft: "auto" }}>
              {danger.danger_level}
            </span>
          </div>
          <div style={{ color: "var(--text-secondary)", fontSize: "0.82rem", marginTop: 10 }}>
            Resilience Score: <strong>{danger.resilience_score}%</strong> · Beta: <strong>{danger.metrics.portfolio_beta}x</strong>
          </div>
        </div>

        {/* Growth Card */}
        <div className="glass-panel" style={{ borderLeft: `4px solid ${growthTone}`, padding: "18px 20px" }}>
          <div style={{ color: "var(--text-muted)", fontSize: "0.8rem", textTransform: "uppercase", letterSpacing: "0.05em" }}>
            Expected Growth Score
          </div>
          <div style={{ display: "flex", alignItems: "baseline", gap: 10, marginTop: 6 }}>
            <span style={{ fontSize: "2.2rem", fontWeight: 700, color: growthTone }}>
              {growth.growth_score}
            </span>
            <span style={{ color: "var(--text-muted)", fontSize: "1rem" }}>/ 100</span>
            <span style={{ fontSize: "0.95rem", fontWeight: 600, color: growthTone, marginLeft: "auto" }}>
              {growth.growth_level}
            </span>
          </div>
          <div style={{ color: "var(--text-secondary)", fontSize: "0.82rem", marginTop: 10 }}>
            5Y Monte Carlo Median: <strong>{formatCurrency(growth.monte_carlo.summary.year_5_median_inr)}</strong> (Prob. Doubling: <strong>{growth.monte_carlo.summary.prob_doubling_5y_pct}%</strong>)
          </div>
        </div>
      </div>

      <WealthCone growth={growth} />

      {/* Danger Flags List */}
      {danger.flags.length > 0 && (
        <div style={{ marginTop: 16 }}>
          <h3 style={{ fontSize: "1rem", color: "var(--text-primary)", marginBottom: 10 }}>
            Identified Risk Signals ({danger.flags.length})
          </h3>
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {danger.flags.map((flag, idx) => (
              <div
                key={idx}
                className="glass-panel"
                style={{
                  borderColor: flag.severity === "CRITICAL" ? "var(--color-sell)" : "var(--color-hold)",
                  padding: "12px 16px",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span
                    style={{
                      fontSize: "0.72rem",
                      fontWeight: 700,
                      padding: "2px 6px",
                      borderRadius: 4,
                      background: flag.severity === "CRITICAL" ? "rgba(239,68,68,0.2)" : "rgba(234,179,8,0.2)",
                      color: flag.severity === "CRITICAL" ? "var(--color-sell)" : "var(--color-hold)",
                    }}
                  >
                    {flag.severity}
                  </span>
                  <strong style={{ fontSize: "0.9rem" }}>{flag.title}</strong>
                </div>
                <p style={{ margin: "4px 0 0", color: "var(--text-secondary)", fontSize: "0.82rem" }}>
                  {flag.detail}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}
      </AnalysisGate>
    </div>
  );
}
