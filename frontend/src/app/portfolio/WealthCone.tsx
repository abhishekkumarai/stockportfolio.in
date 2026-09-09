"use client";

import {
  CategoryScale,
  Chart as ChartJS,
  Filler,
  Legend,
  LineElement,
  LinearScale,
  PointElement,
  Tooltip,
} from "chart.js";
import { Line } from "react-chartjs-2";
import { formatCurrency, type GrowthAnalysis } from "@/lib/portfolioApi";

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Tooltip, Legend, Filler);

// The backend already simulates the full monthly path set; showing only the
// 5-year median throws away the part that matters — how wide the distribution
// is. The p10-p90 band is the honest picture of a projection.

export default function WealthCone({ growth }: { growth: GrowthAnalysis }) {
  const trajectory = growth.monte_carlo.trajectory;
  if (!trajectory || trajectory.length === 0) return null;

  const labels = trajectory.map((point) =>
    point.month % 12 === 0 ? `Y${point.year}` : point.month % 3 === 0 ? `M${point.month}` : ""
  );

  const summary = growth.monte_carlo.summary;

  return (
    <div style={{ marginTop: 20 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", flexWrap: "wrap", gap: 8 }}>
        <div>
          <h3 style={{ fontSize: "1.05rem", margin: 0 }}>Probabilistic wealth cone</h3>
          <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", margin: "4px 0 0" }}>
            10,000 geometric Brownian motion paths at {summary.expected_cagr_pct}% expected CAGR and{" "}
            {summary.assumed_volatility_pct}% volatility. The band is the 10th to 90th percentile.
          </p>
        </div>
        <div style={{ color: "var(--text-muted)", fontSize: "0.8rem", textAlign: "right" }}>
          Doubling within 5 years: <strong style={{ color: "var(--color-buy)" }}>{summary.prob_doubling_5y_pct}%</strong>
          <br />
          Below today&apos;s value at 5 years:{" "}
          <strong style={{ color: "var(--color-sell)" }}>{summary.prob_loss_5y_pct}%</strong>
        </div>
      </div>

      <div style={{ height: 300, marginTop: 14 }}>
        <Line
          data={{
            labels,
            datasets: [
              {
                label: "90th percentile",
                data: trajectory.map((point) => point.p90_inr),
                borderColor: "#059669",
                backgroundColor: "rgba(5, 150, 105, 0.08)",
                fill: "+1",
                pointRadius: 0,
                borderWidth: 1.5,
              },
              {
                label: "Median",
                data: trajectory.map((point) => point.median_inr),
                borderColor: "#2563eb",
                backgroundColor: "rgba(37, 99, 235, 0.05)",
                fill: "+1",
                pointRadius: 0,
                borderWidth: 2,
              },
              {
                label: "10th percentile (Stress)",
                data: trajectory.map((point) => point.p10_inr),
                borderColor: "#dc2626",
                pointRadius: 0,
                borderWidth: 1.5,
                borderDash: [4, 4],
              },
            ],
          }}
          options={{
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: "index", intersect: false },
            plugins: {
              legend: { labels: { color: "#475569", boxWidth: 12, font: { family: "Inter", size: 11 } } },
              tooltip: {
                backgroundColor: "#ffffff",
                titleColor: "#0f172a",
                bodyColor: "#475569",
                borderColor: "#e2e8f0",
                borderWidth: 1,
                padding: 10,
                boxPadding: 4,
                callbacks: {
                  label: (context) =>
                    `${context.dataset.label}: ${formatCurrency(context.parsed.y as number)}`,
                },
              },
            },
            scales: {
              x: { ticks: { color: "#64748b", autoSkip: false, font: { size: 10 } }, grid: { display: false } },
              y: {
                ticks: {
                  color: "#64748b",
                  font: { family: "JetBrains Mono", size: 11 },
                  callback: (value) => formatCurrency(Number(value)),
                },
                grid: { color: "#f1f5f9" },
              },
            },
          }}
        />
      </div>

      <p style={{ color: "var(--text-muted)", fontSize: "0.78rem", marginTop: 8 }}>
        A projection from the portfolio&apos;s own historical drift and volatility, not a forecast.
        Real returns are not lognormal, and the assumed drift is the single most fragile input here.
      </p>
    </div>
  );
}
