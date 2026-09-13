"use client";

import { useEffect, useState } from "react";
import { formatCurrency, rebalancePortfolio, type RebalancePlan } from "@/lib/portfolioApi";
import EmptyPortfolioNotice from "../EmptyPortfolioNotice";
import { usePortfolioContext } from "../PortfolioContext";
import SampleDataNotice from "../SampleDataNotice";

const SAMPLE_REBALANCE_PLAN: RebalancePlan = {
  mode: "zero_tax_inflow",
  cash_allocated_inr: 25000,
  cash_remaining_inr: 1240,
  orders: [
    {
      action: "BUY",
      key: "HDFCBANK",
      name: "HDFC Bank Ltd",
      kind: "equity",
      units: 8,
      estimated_price: 1642.1,
      estimated_amount: 13136.8,
      tax_impact_inr: 0,
      reason: "Underweight by 2.4% vs optimal risk-parity benchmark. Zero STCG incurred via cash inflow routing.",
    },
    {
      action: "BUY",
      key: "ICICIBANK",
      name: "ICICI Bank Ltd",
      kind: "equity",
      units: 10,
      estimated_price: 1040.0,
      estimated_amount: 10400.0,
      tax_impact_inr: 0,
      reason: "Absorbs cash tranche into highest Sharpe financial holding with zero tax friction.",
    },
  ],
  tax_summary: {
    total_tax_inr: 0,
    total_estimated_tax_inr: 0,
    tax_loss_harvest_generated_inr: 0,
    net_effective_tax_inr: 0,
    tax_saved_by_inflow_mode_inr: 4850,
  },
  notes: [
    "Zero-Tax Mode Active: Rebalanced using incoming cash (₹25,000) rather than selling appreciated winners.",
    "Section 112A LTCG annual exemption of ₹1,25,000 preserved intact.",
    "Estimated ₹4,850 saved in immediate STCG taxes compared to standard selling rebalance.",
  ],
};

export default function RebalanceView() {
  const { portfolio } = usePortfolioContext();
  const [rebalancePlan, setRebalancePlan] = useState<RebalancePlan | null>(SAMPLE_REBALANCE_PLAN);
  const [rebalanceIsSample, setRebalanceIsSample] = useState(true);
  const [cashInflow, setCashInflow] = useState<number>(25000);
  const [rebalanceMode, setRebalanceMode] = useState<string>("zero_tax_inflow");
  const [rebalanceLoading, setRebalanceLoading] = useState(false);

  const fetchRebalance = async () => {
    setRebalanceLoading(true);
    try {
      if (!portfolio.equity.length && !portfolio.funds.length) {
        setRebalancePlan(SAMPLE_REBALANCE_PLAN);
        setRebalanceIsSample(true);
        return;
      }
      const plan = await rebalancePortfolio(
        portfolio.equity,
        portfolio.funds,
        portfolio.cash,
        cashInflow,
        rebalanceMode
      );
      const gotRealPlan = Boolean(plan?.orders?.length);
      setRebalancePlan(gotRealPlan ? plan : SAMPLE_REBALANCE_PLAN);
      setRebalanceIsSample(!gotRealPlan);
    } catch (err) {
      console.error("Rebalancing fetch failed", err);
      setRebalancePlan(SAMPLE_REBALANCE_PLAN);
      setRebalanceIsSample(true);
    } finally {
      setRebalanceLoading(false);
    }
  };

  // Reaching this route is now itself the "user asked for a rebalance" signal
  // (replaces the old query-param-driven fetch-on-tab-click).
  useEffect(() => {
    fetchRebalance();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div>
      <div style={{ marginBottom: 20 }}>
        <h1 style={{ margin: 0, fontSize: "1.6rem" }}>Tax Rebalance</h1>
        <p style={{ color: "var(--text-secondary)", margin: "6px 0 0" }}>
          A tax-aware rebalance order sheet optimized around STCG, LTCG, and zero-tax cash inflow routing.
        </p>
      </div>

      <EmptyPortfolioNotice />

      {rebalanceIsSample && <SampleDataNotice text="No rebalance could be computed — showing an illustrative example order instead." />}
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
            style={{
              background: "var(--bg-secondary)",
              border: "1px solid var(--border-subtle)",
              color: "var(--text-primary)",
              padding: "7px 12px",
              borderRadius: 6,
              fontSize: "0.86rem",
              outline: "none",
            }}
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
              style={{
                width: 140,
                background: "var(--bg-secondary)",
                border: "1px solid var(--border-subtle)",
                color: "var(--text-primary)",
                padding: "7px 12px",
                borderRadius: 6,
                fontSize: "0.86rem",
                outline: "none",
              }}
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
            <div
              key={idx}
              className="glass-panel"
              style={{
                marginBottom: 12,
                padding: "12px 16px",
                fontSize: "0.85rem",
                color: "#1e40af",
                background: "#eff6ff",
                borderColor: "#bfdbfe",
                borderRadius: 6,
              }}
            >
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
  );
}
