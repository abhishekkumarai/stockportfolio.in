"use client";

import { formatCurrency } from "@/lib/portfolioApi";
import AnalysisGate from "../AnalysisGate";
import EmptyPortfolioNotice from "../EmptyPortfolioNotice";
import { FALLBACK_DANGER, usePortfolioContext } from "../PortfolioContext";

export default function StressView() {
  const { danger: rawDanger } = usePortfolioContext();
  const danger = rawDanger ?? FALLBACK_DANGER;

  return (
    <div>
      <div style={{ marginBottom: 20 }}>
        <h1 style={{ margin: 0, fontSize: "1.6rem" }}>Crash Simulator</h1>
        <p style={{ color: "var(--text-secondary)", margin: "6px 0 0" }}>
          Historical crisis stress replay for your current holdings.
        </p>
      </div>

      <EmptyPortfolioNotice />

      <AnalysisGate>
        <h3 style={{ fontSize: "1.05rem", marginBottom: 6 }}>Historical Crisis Stress Replay</h3>
        <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", marginBottom: 16 }}>
          Simulates how your current portfolio weights and beta would perform in major historical market crashes.
        </p>
        <div className="custom-table-container">
          <table className="custom-table">
            <thead>
              <tr>
                <th>Crisis Scenario</th>
                <th style={{ textAlign: "right" }}>Nifty Drop</th>
                <th style={{ textAlign: "right" }}>Projected Drop</th>
                <th style={{ textAlign: "right" }}>Estimated Drawdown (INR)</th>
                <th style={{ textAlign: "right" }}>Projected Value</th>
              </tr>
            </thead>
            <tbody>
              {danger.stress_tests.map((s) => (
                <tr key={s.scenario_key}>
                  <td>
                    <div style={{ fontWeight: 600 }}>{s.name}</div>
                    <div style={{ color: "var(--text-muted)", fontSize: "0.78rem" }}>{s.description}</div>
                  </td>
                  <td style={{ textAlign: "right", color: "var(--color-sell)" }}>{s.benchmark_drop_pct}%</td>
                  <td style={{ textAlign: "right", color: "var(--color-sell)", fontWeight: 600 }}>
                    {s.projected_drawdown_pct}%
                  </td>
                  <td style={{ textAlign: "right", color: "var(--color-sell)" }}>
                    -{formatCurrency(s.projected_loss_inr)}
                  </td>
                  <td style={{ textAlign: "right", fontWeight: 600 }}>
                    {formatCurrency(s.projected_recovery_value)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </AnalysisGate>
    </div>
  );
}
