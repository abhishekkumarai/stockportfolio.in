"use client";

import { use, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler,
  ScriptableContext,
} from "chart.js";
import { Line } from "react-chartjs-2";
import {
  formatDate,
  formatPct,
  getFundAnalysis,
  getNavHistory,
  parseNavDate,
  TRAILING_LABELS,
  type NavHistory,
  type SchemeAnalysis,
} from "@/lib/mfApi";

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend, Filler);

const RANGES = [
  { key: "1y", label: "1Y", years: 1 },
  { key: "3y", label: "3Y", years: 3 },
  { key: "5y", label: "5Y", years: 5 },
  { key: "max", label: "MAX", years: 0 },
] as const;

/** Chart.js slows badly past a few thousand points; NAV curves stay readable when thinned. */
function downsample<T>(points: T[], maxPoints = 400): T[] {
  if (points.length <= maxPoints) return points;
  const step = Math.ceil(points.length / maxPoints);
  const thinned = points.filter((_, index) => index % step === 0);
  // Always keep the final point so the line ends at the latest NAV.
  const last = points[points.length - 1];
  if (thinned[thinned.length - 1] !== last) thinned.push(last);
  return thinned;
}

function MetricCard({
  title,
  value,
  sub,
  tone,
}: {
  title: string;
  value: string;
  sub?: string;
  tone?: "up" | "down";
}) {
  return (
    <div className="glass-panel metric-card" style={{ padding: "18px 22px" }}>
      <div className="title" style={{ fontSize: "0.75rem", fontWeight: 600 }}>
        {title}
      </div>
      <div
        className="value"
        style={{
          fontSize: "1.5rem",
          margin: "6px 0 2px",
          color:
            tone === "up" ? "var(--color-buy)" : tone === "down" ? "var(--color-sell)" : undefined,
        }}
      >
        {value}
      </div>
      {sub && <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>{sub}</div>}
    </div>
  );
}

export default function FundDetailPage({ params }: { params: Promise<{ schemeCode: string }> }) {
  const { schemeCode } = use(params);

  const [analysis, setAnalysis] = useState<SchemeAnalysis | null>(null);
  const [history, setHistory] = useState<NavHistory | null>(null);
  const [range, setRange] = useState<(typeof RANGES)[number]["key"]>("3y");
  const [loading, setLoading] = useState(true);
  const [chartLoading, setChartLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const data = await getFundAnalysis(schemeCode, controller.signal);
        setAnalysis(data);
      } catch (err) {
        if ((err as Error).name !== "AbortError") {
          setError((err as Error).message || "Could not load this scheme.");
        }
      } finally {
        setLoading(false);
      }
    }
    load();
    return () => controller.abort();
  }, [schemeCode]);

  useEffect(() => {
    const controller = new AbortController();
    async function loadHistory() {
      setChartLoading(true);
      try {
        const selected = RANGES.find((r) => r.key === range);
        let startDate: string | undefined;
        if (selected && selected.years > 0) {
          const from = new Date();
          from.setFullYear(from.getFullYear() - selected.years);
          startDate = from.toISOString().slice(0, 10);
        }
        const data = await getNavHistory(schemeCode, startDate, controller.signal);
        setHistory(data);
      } catch (err) {
        if ((err as Error).name !== "AbortError") {
          console.error("Failed to load NAV history:", err);
        }
      } finally {
        setChartLoading(false);
      }
    }
    loadHistory();
    return () => controller.abort();
  }, [schemeCode, range]);

  const chart = useMemo(() => {
    if (!history?.data?.length) return null;
    // The API returns newest first; charts read left to right in time order.
    const ordered = [...history.data].reverse();
    const points = downsample(ordered);
    return {
      labels: points.map((p) =>
        parseNavDate(p.date).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "2-digit" })
      ),
      datasets: [
        {
          label: "NAV (₹)",
          data: points.map((p) => Number(p.nav)),
          borderColor: "#22d3ee",
          borderWidth: 2,
          pointRadius: 0,
          pointHoverRadius: 4,
          tension: 0.15,
          fill: true,
          backgroundColor: (context: ScriptableContext<"line">) => {
            const { ctx, chartArea } = context.chart;
            if (!chartArea) return "rgba(34, 211, 238, 0.1)";
            const gradient = ctx.createLinearGradient(0, chartArea.bottom, 0, chartArea.top);
            gradient.addColorStop(0, "rgba(34, 211, 238, 0)");
            gradient.addColorStop(1, "rgba(34, 211, 238, 0.35)");
            return gradient;
          },
        },
      ],
    };
  }, [history]);

  if (loading) {
    return (
      <div className="app-container loading-container">
        <div className="spinner"></div>
        <h3 style={{ fontWeight: 500, color: "var(--text-secondary)" }}>Loading scheme {schemeCode}...</h3>
      </div>
    );
  }

  if (error || !analysis) {
    return (
      <div className="app-container" style={{ paddingTop: "60px" }}>
        <div className="glass-panel" style={{ padding: "40px", textAlign: "center", maxWidth: "600px", margin: "0 auto" }}>
          <h3 style={{ color: "var(--color-sell)", marginBottom: "10px" }}>Could not load this fund</h3>
          <p style={{ color: "var(--text-secondary)", marginBottom: "24px" }}>{error}</p>
          <Link href="/mutualfunds" className="glowing-button" style={{ textDecoration: "none" }}>
            ← Back to fund search
          </Link>
        </div>
      </div>
    );
  }

  const { meta, nav, trailing_returns: trailing, risk, rolling_returns: rolling } = analysis;
  const oneYear = trailing["1y"];
  const threeYear = trailing["3y"];
  const fiveYear = trailing["5y"];
  const inception = trailing["since_inception"];

  const displayReturn = (entry: typeof oneYear) => {
    if (!entry) return "—";
    return formatPct(entry.annualised ? entry.cagr_pct : entry.return_pct);
  };
  const tone = (entry: typeof oneYear): "up" | "down" | undefined => {
    const value = entry?.annualised ? entry?.cagr_pct : entry?.return_pct;
    if (value === null || value === undefined) return undefined;
    return value >= 0 ? "up" : "down";
  };

  return (
    <div className="app-container animate-fade-in" style={{ paddingBottom: "60px" }}>
      <Link
        href="/mutualfunds"
        style={{ color: "var(--text-secondary)", fontSize: "0.9rem", textDecoration: "none", display: "inline-block", margin: "24px 0 16px" }}
      >
        ← Back to fund search
      </Link>

      {/* Scheme header */}
      <div className="glass-panel-cyan" style={{ padding: "30px", marginBottom: "24px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: "20px" }}>
          <div style={{ flex: "1 1 400px" }}>
            <div style={{ fontSize: "0.8rem", color: "var(--accent-cyan)", fontWeight: 700, marginBottom: "8px" }}>
              {meta.fund_house}
            </div>
            <h1 style={{ fontSize: "1.9rem", fontWeight: 800, lineHeight: 1.2, marginBottom: "12px" }}>
              {meta.scheme_name}
            </h1>
            <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
              {[meta.scheme_category, meta.scheme_type].filter(Boolean).map((tag) => (
                <span
                  key={tag}
                  style={{
                    fontSize: "0.75rem",
                    padding: "4px 10px",
                    borderRadius: "6px",
                    background: "rgba(255,255,255,0.07)",
                    color: "var(--text-secondary)",
                  }}
                >
                  {tag}
                </span>
              ))}
            </div>
          </div>
          <div style={{ textAlign: "right" }}>
            <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", fontWeight: 600 }}>LATEST NAV</div>
            <div style={{ fontSize: "2.4rem", fontWeight: 800, color: "var(--text-primary)", lineHeight: 1.2 }}>
              ₹{nav.latest.toFixed(4)}
            </div>
            <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>
              as on {formatDate(nav.latest_date)}
            </div>
          </div>
        </div>
      </div>

      {/* Headline returns */}
      <div className="metrics-grid" style={{ marginBottom: "24px" }}>
        <MetricCard title="1 YEAR" value={displayReturn(oneYear)} sub="annualised" tone={tone(oneYear)} />
        <MetricCard title="3 YEARS" value={displayReturn(threeYear)} sub="CAGR" tone={tone(threeYear)} />
        <MetricCard title="5 YEARS" value={displayReturn(fiveYear)} sub="CAGR" tone={tone(fiveYear)} />
        <MetricCard
          title="SINCE INCEPTION"
          value={displayReturn(inception)}
          sub={`from ${formatDate(nav.inception_date)}`}
          tone={tone(inception)}
        />
      </div>

      {/* NAV chart */}
      <div className="glass-panel" style={{ padding: "26px", marginBottom: "24px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "18px", flexWrap: "wrap", gap: "12px" }}>
          <h3 style={{ fontSize: "1.15rem", fontWeight: 700 }}>NAV History</h3>
          <div style={{ display: "flex", gap: "8px" }}>
            {RANGES.map((option) => (
              <button
                key={option.key}
                type="button"
                onClick={() => setRange(option.key)}
                style={{
                  padding: "6px 14px",
                  borderRadius: "8px",
                  border: `1px solid ${range === option.key ? "var(--accent-blue)" : "var(--border-subtle)"}`,
                  background: range === option.key ? "rgba(37, 99, 235, 0.08)" : "transparent",
                  color: range === option.key ? "var(--accent-blue)" : "var(--text-secondary)",
                  cursor: "pointer",
                  fontSize: "0.8rem",
                  fontWeight: 600,
                  transition: "var(--transition-smooth)",
                }}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>

        <div style={{ height: "340px", position: "relative" }}>
          {chartLoading && (
            <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", color: "var(--text-secondary)", zIndex: 2 }}>
              Loading NAV history...
            </div>
          )}
          {chart && (
            <Line
              data={chart}
              options={{
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: "index", intersect: false },
                plugins: {
                  legend: { display: false },
                  tooltip: {
                    callbacks: {
                      label: (context) => `NAV: ₹${Number(context.parsed.y).toFixed(4)}`,
                    },
                  },
                },
                scales: {
                  x: {
                    grid: { display: false },
                    ticks: { color: "#64748b", maxTicksLimit: 8, font: { size: 10 } },
                  },
                  y: {
                    grid: { color: "rgba(226, 232, 240, 0.8)" },
                    ticks: { color: "#64748b", font: { size: 10 } },
                  },
                },
              }}
            />
          )}
        </div>
        <div style={{ fontSize: "0.78rem", color: "var(--text-muted)", marginTop: "10px" }}>
          {history ? `${history.count.toLocaleString("en-IN")} NAV points in range` : ""} · Data from mfapi.in
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(400px, 1fr))", gap: "24px", marginBottom: "24px" }}>
        {/* Trailing returns */}
        <div className="glass-panel" style={{ padding: "26px" }}>
          <h3 style={{ fontSize: "1.15rem", fontWeight: 700, marginBottom: "16px" }}>Trailing Returns</h3>
          <div className="custom-table-container">
            <table className="custom-table">
              <thead>
                <tr>
                  <th>Period</th>
                  <th style={{ textAlign: "right" }}>Return</th>
                  <th style={{ textAlign: "right" }}>Basis</th>
                </tr>
              </thead>
              <tbody>
                {TRAILING_LABELS.map(([key, label]) => {
                  const entry = trailing[key];
                  if (!entry) return null;
                  const value = entry.annualised ? entry.cagr_pct : entry.return_pct;
                  return (
                    <tr key={key}>
                      <td>{label}</td>
                      <td
                        style={{
                          textAlign: "right",
                          fontWeight: 700,
                          color:
                            value === null || value === undefined
                              ? "var(--text-muted)"
                              : value >= 0
                              ? "var(--color-buy)"
                              : "var(--color-sell)",
                        }}
                      >
                        {formatPct(value)}
                      </td>
                      <td style={{ textAlign: "right", color: "var(--text-muted)", fontSize: "0.8rem" }}>
                        {entry.annualised ? "CAGR" : "absolute"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <p style={{ fontSize: "0.78rem", color: "var(--text-muted)", marginTop: "12px" }}>
            Periods of a year or more are annualised, matching how Indian factsheets report them.
          </p>
        </div>

        {/* Risk */}
        <div className="glass-panel" style={{ padding: "26px" }}>
          <h3 style={{ fontSize: "1.15rem", fontWeight: 700, marginBottom: "16px" }}>Risk & Drawdown</h3>
          {risk.insufficient_data ? (
            <p style={{ color: "var(--text-secondary)" }}>
              Not enough NAV history to compute risk metrics.
            </p>
          ) : (
            <>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))", gap: "14px", marginBottom: "18px" }}>
                <div>
                  <div style={{ fontSize: "0.72rem", color: "var(--text-muted)", fontWeight: 600 }}>VOLATILITY</div>
                  <div style={{ fontSize: "1.3rem", fontWeight: 700, color: "var(--text-primary)" }}>
                    {risk.volatility_pct?.toFixed(2)}%
                  </div>
                  <div style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>annualised</div>
                </div>
                <div>
                  <div style={{ fontSize: "0.72rem", color: "var(--text-muted)", fontWeight: 600 }}>SHARPE</div>
                  <div style={{ fontSize: "1.3rem", fontWeight: 700, color: "var(--text-primary)" }}>
                    {risk.sharpe_ratio?.toFixed(2) ?? "—"}
                  </div>
                  <div style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>
                    vs {risk.risk_free_rate_pct}% risk-free
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: "0.72rem", color: "var(--text-muted)", fontWeight: 600 }}>SORTINO</div>
                  <div style={{ fontSize: "1.3rem", fontWeight: 700, color: "var(--text-primary)" }}>
                    {risk.sortino_ratio?.toFixed(2) ?? "—"}
                  </div>
                  <div style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>downside only</div>
                </div>
                <div>
                  <div style={{ fontSize: "0.72rem", color: "var(--text-muted)", fontWeight: 600 }}>MAX DRAWDOWN</div>
                  <div style={{ fontSize: "1.3rem", fontWeight: 700, color: "var(--color-sell)" }}>
                    {risk.max_drawdown_pct?.toFixed(2)}%
                  </div>
                  <div style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>peak to trough</div>
                </div>
              </div>

              <div style={{ borderTop: "1px solid var(--border-subtle)", paddingTop: "14px", display: "flex", flexDirection: "column", gap: "8px", fontSize: "0.85rem" }}>
                {risk.max_drawdown_peak_date && risk.max_drawdown_trough_date && (
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span style={{ color: "var(--text-secondary)" }}>Worst fall</span>
                    <span>
                      {formatDate(risk.max_drawdown_peak_date)} → {formatDate(risk.max_drawdown_trough_date)}
                    </span>
                  </div>
                )}
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ color: "var(--text-secondary)" }}>Recovery</span>
                  <span>
                    {risk.max_drawdown_recovery_date
                      ? `${formatDate(risk.max_drawdown_recovery_date)} (${risk.max_drawdown_recovery_days} days)`
                      : "Not yet recovered"}
                  </span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ color: "var(--text-secondary)" }}>Currently below peak</span>
                  <span style={{ color: (risk.current_drawdown_pct ?? 0) < -0.01 ? "var(--color-sell)" : "var(--color-buy)" }}>
                    {risk.current_drawdown_pct?.toFixed(2)}%
                  </span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ color: "var(--text-secondary)" }}>Positive days</span>
                  <span>{risk.positive_days_pct}%</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ color: "var(--text-secondary)" }}>Best / worst day</span>
                  <span>
                    <span style={{ color: "var(--color-buy)" }}>{formatPct(risk.best_day_pct)}</span>
                    {" / "}
                    <span style={{ color: "var(--color-sell)" }}>{formatPct(risk.worst_day_pct)}</span>
                  </span>
                </div>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Rolling returns */}
      {Object.keys(rolling).length > 0 && (
        <div className="glass-panel" style={{ padding: "26px" }}>
          <h3 style={{ fontSize: "1.15rem", fontWeight: 700, marginBottom: "6px" }}>Rolling Returns</h3>
          <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "16px" }}>
            Annualised return across every possible start date — what an investor entering on a random
            day would actually have earned, rather than one lucky window.
          </p>
          <div className="custom-table-container">
            <table className="custom-table">
              <thead>
                <tr>
                  <th>Window</th>
                  <th style={{ textAlign: "right" }}>Average</th>
                  <th style={{ textAlign: "right" }}>Median</th>
                  <th style={{ textAlign: "right" }}>Worst</th>
                  <th style={{ textAlign: "right" }}>Best</th>
                  <th style={{ textAlign: "right" }}>Positive</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(rolling).map(([key, value]) => (
                  <tr key={key}>
                    <td style={{ fontWeight: 600 }}>{value.years} year</td>
                    <td style={{ textAlign: "right", fontWeight: 700 }}>{formatPct(value.average_pct)}</td>
                    <td style={{ textAlign: "right" }}>{formatPct(value.median_pct)}</td>
                    {/* Colour by sign, not by column: a fund's worst rolling window
                        can still be positive, and painting that red misreads it. */}
                    <td
                      style={{
                        textAlign: "right",
                        color: (value.min_pct ?? 0) >= 0 ? "var(--color-buy)" : "var(--color-sell)",
                      }}
                    >
                      {formatPct(value.min_pct)}
                    </td>
                    <td
                      style={{
                        textAlign: "right",
                        color: (value.max_pct ?? 0) >= 0 ? "var(--color-buy)" : "var(--color-sell)",
                      }}
                    >
                      {formatPct(value.max_pct)}
                    </td>
                    <td style={{ textAlign: "right" }}>{value.positive_windows_pct}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <p style={{ fontSize: "0.78rem", color: "var(--text-muted)", marginTop: "24px", textAlign: "center" }}>
        NAV data sourced from mfapi.in (AMFI). Past performance does not indicate future returns. This
        is informational analysis, not investment advice.
      </p>
    </div>
  );
}
