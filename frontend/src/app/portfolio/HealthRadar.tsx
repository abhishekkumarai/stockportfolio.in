"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";

import {
  DangerAnalysis,
  GrowthAnalysis,
  NewsArticle,
  RebalancePlan,
  formatCurrency,
  formatPct,
  getPortfolioNews,
  rebalancePortfolio,
  type StoredPortfolio,
} from "@/lib/portfolioApi";
import AiMemo from "./AiMemo";
import WealthCone from "./WealthCone";

type Tab = "overview" | "stress" | "rebalance" | "news" | "memo";

const TABS: Tab[] = ["overview", "stress", "rebalance", "news", "memo"];

interface HealthRadarProps {
  danger: DangerAnalysis | null;
  growth: GrowthAnalysis | null;
  portfolio: StoredPortfolio;
  loading: boolean;
}

export default function HealthRadar({
  danger,
  growth,
  portfolio,
  loading,
}: HealthRadarProps) {
  const searchParams = useSearchParams();
  const [activeTab, setActiveTab] = useState<Tab>("overview");

  useEffect(() => {
    const tab = searchParams.get("tab");
    if (tab && TABS.includes(tab as Tab)) {
      setActiveTab(tab as Tab);
      if (tab === "rebalance" && !rebalancePlan) {
        fetchRebalance();
      } else if (tab === "news" && newsArticles.length === 0) {
        fetchNews();
      }
    }
  }, [searchParams]);

  const [rebalancePlan, setRebalancePlan] = useState<RebalancePlan | null>(null);
  const [cashInflow, setCashInflow] = useState<number>(25000);
  const [rebalanceMode, setRebalanceMode] = useState<string>("zero_tax_inflow");
  const [rebalanceLoading, setRebalanceLoading] = useState(false);
  const [newsArticles, setNewsArticles] = useState<NewsArticle[]>([]);
  const [newsLoading, setNewsLoading] = useState(false);


  const fetchRebalance = async () => {
    setRebalanceLoading(true);
    try {
      const plan = await rebalancePortfolio(
        portfolio.equity,
        portfolio.funds,
        portfolio.cash,
        cashInflow,
        rebalanceMode
      );
      setRebalancePlan(plan);
    } catch (err) {
      console.error("Rebalancing fetch failed", err);
    } finally {
      setRebalanceLoading(false);
    }
  };

  const fetchNews = async () => {
    setNewsLoading(true);
    try {
      const res = await getPortfolioNews(portfolio.equity);
      setNewsArticles(res.articles);
    } catch (err) {
      console.error("News fetch failed", err);
    } finally {
      setNewsLoading(false);
    }
  };

  if (loading || !danger || !growth) {
    return (
      <div className="glass-panel" style={{ textAlign: "center", padding: "32px 16px", marginBottom: 24 }}>
        <div className="spinner" style={{ margin: "0 auto 12px" }} />
        <p style={{ color: "var(--text-secondary)", margin: 0 }}>Evaluating Danger Matrix & Expected Growth...</p>
      </div>
    );
  }

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
    <div className="glass-panel" style={{ marginBottom: 24 }}>
      {/* Header Tabs */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1px solid var(--border-color)", paddingBottom: 14, marginBottom: 20, flexWrap: "wrap", gap: 12 }}>
        <div>
          <h2 style={{ margin: 0, fontSize: "1.3rem" }}>Portfolio Intelligence Radar</h2>
          <p style={{ color: "var(--text-secondary)", margin: "4px 0 0", fontSize: "0.85rem" }}>
            Real-time capital preservation and growth trajectory diagnostics.
          </p>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button
            className={activeTab === "overview" ? "glowing-button" : "secondary-button"}
            onClick={() => setActiveTab("overview")}
            style={{ padding: "6px 14px", fontSize: "0.85rem" }}
          >
            Health Overview
          </button>
          <button
            className={activeTab === "stress" ? "glowing-button" : "secondary-button"}
            onClick={() => setActiveTab("stress")}
            style={{ padding: "6px 14px", fontSize: "0.85rem" }}
          >
            Crash Simulator
          </button>
          <button
            className={activeTab === "rebalance" ? "glowing-button" : "secondary-button"}
            onClick={() => {
              setActiveTab("rebalance");
              if (!rebalancePlan) fetchRebalance();
            }}
            style={{ padding: "6px 14px", fontSize: "0.85rem" }}
          >
            Tax Rebalancer
          </button>
          <button
            className={activeTab === "news" ? "glowing-button" : "secondary-button"}
            onClick={() => {
              setActiveTab("news");
              if (newsArticles.length === 0) fetchNews();
            }}
            style={{ padding: "6px 14px", fontSize: "0.85rem" }}
          >
            Holdings News
          </button>
          <button
            className={activeTab === "memo" ? "glowing-button" : "secondary-button"}
            onClick={() => setActiveTab("memo")}
            style={{ padding: "6px 14px", fontSize: "0.85rem" }}
          >
            AI Memo
          </button>
        </div>
      </div>

      {/* TAB 1: OVERVIEW */}
      {activeTab === "overview" && (
        <div>
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
        </div>
      )}

      {/* TAB 2: STRESS TEST SIMULATOR */}
      {activeTab === "stress" && (
        <div>
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
        </div>
      )}

      {/* TAB 3: TAX-AWARE REBALANCER */}
      {activeTab === "rebalance" && (
        <div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12, marginBottom: 16 }}>
            <div>
              <h3 style={{ fontSize: "1.05rem", margin: 0 }}>Indian Tax-Aware Rebalancer</h3>
              <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", margin: "4px 0 0" }}>
                Optimized around STCG (20%), LTCG (12.5% over ₹1.25L), and zero-tax cash inflow routing.
              </p>
            </div>
            <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
              <select
                value={rebalanceMode}
                onChange={(e) => setRebalanceMode(e.target.value)}
                style={{ background: "rgba(255,255,255,0.06)", border: "1px solid var(--border-color)", color: "#fff", padding: "6px 10px", borderRadius: 6 }}
              >
                <option value="zero_tax_inflow">Zero-Tax Cash Inflow Mode</option>
                <option value="drift_rebalance">Full Drift Trimming Mode</option>
              </select>
              {rebalanceMode === "zero_tax_inflow" && (
                <input
                  type="number"
                  placeholder="Cash Inflow (INR)"
                  value={cashInflow}
                  onChange={(e) => setCashInflow(Number(e.target.value))}
                  style={{ width: 130, background: "rgba(255,255,255,0.06)", border: "1px solid var(--border-color)", color: "#fff", padding: "6px 10px", borderRadius: 6 }}
                />
              )}
              <button className="glowing-button" onClick={fetchRebalance} disabled={rebalanceLoading}>
                {rebalanceLoading ? "Calculating..." : "Calculate Orders"}
              </button>
            </div>
          </div>

          {rebalancePlan && (
            <div>
              {rebalancePlan.notes.map((note, idx) => (
                <div key={idx} className="glass-panel" style={{ marginBottom: 12, fontSize: "0.85rem", color: "var(--accent-cyan)" }}>
                  {note}
                </div>
              ))}

              <div className="custom-table-container">
                <table className="custom-table">
                  <thead>
                    <tr>
                      <th>Action</th>
                      <th>Holding</th>
                      <th style={{ textAlign: "right" }}>Units</th>
                      <th style={{ textAlign: "right" }}>Est. Price</th>
                      <th style={{ textAlign: "right" }}>Total (INR)</th>
                      <th style={{ textAlign: "right" }}>Tax Impact</th>
                      <th>Reason</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rebalancePlan.orders.map((o, idx) => (
                      <tr key={idx}>
                        <td>
                          <span
                            style={{
                              fontWeight: 700,
                              fontSize: "0.75rem",
                              padding: "3px 8px",
                              borderRadius: 4,
                              background: o.action === "BUY" ? "rgba(34,197,94,0.2)" : "rgba(239,68,68,0.2)",
                              color: o.action === "BUY" ? "var(--color-buy)" : "var(--color-sell)",
                            }}
                          >
                            {o.action}
                          </span>
                        </td>
                        <td style={{ fontWeight: 600 }}>{o.name}</td>
                        <td style={{ textAlign: "right" }}>{o.units}</td>
                        <td style={{ textAlign: "right" }}>{formatCurrency(o.estimated_price)}</td>
                        <td style={{ textAlign: "right", fontWeight: 600 }}>{formatCurrency(o.estimated_amount)}</td>
                        <td style={{ textAlign: "right", color: o.tax_impact_inr > 0 ? "var(--color-sell)" : "var(--text-muted)" }}>
                          {formatCurrency(o.tax_impact_inr)}
                        </td>
                        <td style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>{o.reason}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {/* TAB 4: HOLDINGS NEWS */}
      {activeTab === "news" && (
        <div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
            <div>
              <h3 style={{ fontSize: "1.05rem", margin: 0 }}>Holdings News & Corporate Filings</h3>
              <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", margin: "4px 0 0" }}>
                Filtered strictly for the stocks you hold (Zero generic market noise).
              </p>
            </div>
            <button className="secondary-button" onClick={fetchNews} disabled={newsLoading}>
              {newsLoading ? "Refreshing..." : "Refresh News"}
            </button>
          </div>

          {newsArticles.length === 0 ? (
            <div style={{ textAlign: "center", padding: "24px 0", color: "var(--text-muted)" }}>
              {newsLoading ? "Fetching disclosures..." : "No adverse news or filings detected for your holdings."}
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {newsArticles.map((art, idx) => (
                <div key={idx} className="glass-panel" style={{ padding: "12px 16px" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                    <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                      <span style={{ fontSize: "0.75rem", fontWeight: 700, padding: "2px 6px", borderRadius: 4, background: "rgba(255,255,255,0.08)" }}>
                        {art.symbol}
                      </span>
                      <span style={{ fontSize: "0.75rem", color: "var(--accent-cyan)", border: "1px solid var(--border-color)", padding: "1px 6px", borderRadius: 4 }}>
                        {art.tag}
                      </span>
                    </div>
                    <span style={{ fontSize: "0.8rem", fontWeight: 600 }}>{art.impact_label}</span>
                  </div>
                  <a
                    href={art.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{ color: "var(--text-primary)", fontWeight: 500, fontSize: "0.92rem", textDecoration: "none" }}
                  >
                    {art.title} ↗
                  </a>
                  <div style={{ color: "var(--text-muted)", fontSize: "0.75rem", marginTop: 4 }}>
                    {art.source} · {art.published_at}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* TAB 5: AI MEMO */}
      {activeTab === "memo" && (
        <div>
          <div style={{ marginBottom: 16 }}>
            <h3 style={{ fontSize: "1.05rem", margin: 0 }}>Monthly Portfolio Memo</h3>
            <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", margin: "4px 0 0" }}>
              An LLM writing over the numbers on this page — never inventing a metric, and every
              figure checked back against the computed data before it is shown.
            </p>
          </div>
          <AiMemo portfolio={portfolio} />
        </div>
      )}
    </div>
  );
}
