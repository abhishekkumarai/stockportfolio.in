"use client";

import { useEffect, useState } from "react";
import {
  BarElement,
  CategoryScale,
  Chart as ChartJS,
  Legend,
  LinearScale,
  LineElement,
  PointElement,
  Tooltip,
} from "chart.js";
import { Bar, Scatter } from "react-chartjs-2";
import {
  REGIME_TONE,
  factorExposures,
  listMethods,
  marketRegime,
  optimise,
  rebalanceToTarget,
  type FactorResult,
  type MethodInfo,
  type OptimiseResult,
  type OptimiserMethod,
  type RegimeResult,
  type TargetRebalancePlan,
} from "@/lib/quantApi";
import {
  EMPTY_PORTFOLIO,
  formatCurrency,
  formatNumber,
  loadPortfolio,
  type StoredPortfolio,
} from "@/lib/portfolioApi";

ChartJS.register(CategoryScale, LinearScale, BarElement, PointElement, LineElement, Tooltip, Legend);

type Tab = "allocate" | "factors" | "regime" | "orders";

const PERIODS = ["1y", "2y", "3y", "5y"];

export default function QuantConsole() {
  const [portfolio, setPortfolio] = useState<StoredPortfolio>(EMPTY_PORTFOLIO);
  const [hydrated, setHydrated] = useState(false);
  const [tab, setTab] = useState<Tab>("allocate");
  const [methods, setMethods] = useState<MethodInfo[]>([]);

  const [method, setMethod] = useState<OptimiserMethod>("hrp");
  const [maxWeight, setMaxWeight] = useState(35);
  const [period, setPeriod] = useState("2y");
  const [includeFrontier, setIncludeFrontier] = useState(false);

  const [result, setResult] = useState<OptimiseResult | null>(null);
  const [factors, setFactors] = useState<FactorResult | null>(null);
  const [regime, setRegime] = useState<RegimeResult | null>(null);
  const [plan, setPlan] = useState<TargetRebalancePlan | null>(null);

  const [cashInflow, setCashInflow] = useState(0);
  const [allowSelling, setAllowSelling] = useState(true);

  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setPortfolio(loadPortfolio());
    setHydrated(true);
    const controller = new AbortController();
    listMethods(controller.signal)
      .then((response) => setMethods(response.methods))
      .catch(() => setMethods([]));
    return () => controller.abort();
  }, []);

  const equityCount = portfolio.equity.length;

  const guard = async (label: string, work: () => Promise<void>) => {
    setBusy(label);
    setError(null);
    try {
      await work();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(null);
    }
  };

  const runOptimise = () =>
    guard("allocate", async () => {
      setResult(
        await optimise(portfolio, {
          method,
          maxWeight: maxWeight / 100,
          period,
          includeFrontier: includeFrontier && (method === "min_variance" || method === "max_sharpe"),
        })
      );
    });

  const runFactors = () =>
    guard("factors", async () => {
      setFactors(await factorExposures(portfolio, period, false));
    });

  const runRegime = () =>
    guard("regime", async () => {
      setRegime(await marketRegime(equityCount >= 2 ? portfolio : null, period));
    });

  const runOrders = () =>
    guard("orders", async () => {
      setPlan(
        await rebalanceToTarget(portfolio, {
          method,
          cashInflow,
          allowSelling,
          driftTolerance: 0.03,
          maxWeight: maxWeight / 100,
          period,
        })
      );
    });

  if (!hydrated) {
    return (
      <div className="app-container">
        <div className="loading-container">
          <div className="spinner" />
        </div>
      </div>
    );
  }

  return (
    <div className="app-container animate-fade-in">
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ margin: 0, fontSize: "1.9rem" }}>Quant Lab</h1>
        <p style={{ color: "var(--text-secondary)", margin: "6px 0 0", maxWidth: 780 }}>
          Target allocations that survive a noisy covariance matrix, the factor bets you are
          actually running, the regime the market is in, and the tax-aware order sheet that moves
          you from one to the other.
        </p>
      </div>

      {equityCount < 2 && (
        <div className="glass-panel" style={{ marginBottom: 20, borderColor: "var(--color-hold)" }}>
          <strong style={{ color: "var(--color-hold)" }}>Not enough holdings yet</strong>
          <p style={{ margin: "6px 0 0", color: "var(--text-secondary)" }}>
            Everything here needs at least two equity holdings with overlapping price history. Add
            them on the Portfolio page — mutual funds are excluded on purpose, since an NAV series
            is already a portfolio of the same stocks.
          </p>
        </div>
      )}

      <div className="glass-panel" style={{ marginBottom: 20, display: "flex", gap: 14, flexWrap: "wrap", alignItems: "flex-end" }}>
        <label style={{ flex: "1 1 220px" }}>
          <FieldLabel>Allocator</FieldLabel>
          <select
            value={method}
            onChange={(event) => setMethod(event.target.value as OptimiserMethod)}
            style={inputStyle}
          >
            {(methods.length ? methods : FALLBACK_METHODS).map((entry) => (
              <option key={entry.name} value={entry.name}>
                {entry.label}
                {entry.recommended ? " (recommended)" : ""}
              </option>
            ))}
          </select>
        </label>
        <label style={{ flex: "0 1 140px" }}>
          <FieldLabel>Max weight %</FieldLabel>
          <input
            type="number"
            min={5}
            max={100}
            value={maxWeight}
            onChange={(event) => setMaxWeight(Number(event.target.value))}
            style={inputStyle}
          />
        </label>
        <label style={{ flex: "0 1 130px" }}>
          <FieldLabel>History</FieldLabel>
          <select value={period} onChange={(event) => setPeriod(event.target.value)} style={inputStyle}>
            {PERIODS.map((entry) => (
              <option key={entry} value={entry}>
                {entry}
              </option>
            ))}
          </select>
        </label>
        <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: "0.85rem", paddingBottom: 8 }}>
          <input
            type="checkbox"
            checked={includeFrontier}
            disabled={method !== "min_variance" && method !== "max_sharpe"}
            onChange={(event) => setIncludeFrontier(event.target.checked)}
          />
          Solve the efficient frontier
        </label>
      </div>

      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginBottom: 20 }}>
        <TabButton active={tab === "allocate"} onClick={() => setTab("allocate")}>
          Target allocation
        </TabButton>
        <TabButton active={tab === "factors"} onClick={() => setTab("factors")}>
          Factor exposure
        </TabButton>
        <TabButton active={tab === "regime"} onClick={() => setTab("regime")}>
          Market regime
        </TabButton>
        <TabButton active={tab === "orders"} onClick={() => setTab("orders")}>
          Rebalance orders
        </TabButton>
      </div>

      {error && (
        <div className="glass-panel" style={{ borderColor: "var(--color-sell)", marginBottom: 20 }}>
          <strong style={{ color: "var(--color-sell)" }}>That did not run</strong>
          <p style={{ margin: "6px 0 0", color: "var(--text-secondary)" }}>{error}</p>
        </div>
      )}

      {tab === "allocate" && (
        <section>
          <button className="glowing-button" onClick={runOptimise} disabled={busy !== null || equityCount < 2}>
            {busy === "allocate" ? "Optimising…" : "Compute target weights"}
          </button>

          {result && (
            <>
              <div className="metrics-grid" style={{ margin: "20px 0" }}>
                <Stat label="Expected return" value={`${result.expected_return_pct}%`} />
                <Stat label="Volatility" value={`${result.volatility_pct}%`} />
                <Stat label="Sharpe" value={String(result.sharpe)} />
                <Stat
                  label="Effective holdings"
                  value={String(result.effective_holdings)}
                  sub={`of ${Object.keys(result.weights).length} names`}
                />
              </div>

              {result.why && (
                <div className="glass-panel glass-panel-cyan" style={{ marginBottom: 20 }}>
                  <p style={{ margin: 0, color: "var(--text-secondary)" }}>{result.why}</p>
                </div>
              )}

              <div className="custom-table-container" style={{ marginBottom: 20 }}>
                <table className="custom-table">
                  <thead>
                    <tr>
                      <th>Holding</th>
                      <th style={{ textAlign: "right" }}>Current</th>
                      <th style={{ textAlign: "right" }}>Target</th>
                      <th style={{ textAlign: "right" }}>Drift</th>
                      <th style={{ textAlign: "right" }}>Risk share</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(result.weights)
                      .sort((a, b) => b[1] - a[1])
                      .map(([symbol, weight]) => {
                        const drift = result.drift[symbol] ?? 0;
                        return (
                          <tr key={symbol}>
                            <td style={{ fontWeight: 600 }}>{symbol}</td>
                            <td style={{ textAlign: "right" }}>
                              {((result.current_weights[symbol] ?? 0) * 100).toFixed(1)}%
                            </td>
                            <td style={{ textAlign: "right" }}>{(weight * 100).toFixed(1)}%</td>
                            <td
                              style={{
                                textAlign: "right",
                                color: Math.abs(drift) < 1 ? "var(--text-muted)" : drift > 0 ? "var(--color-hold)" : "var(--accent-cyan)",
                              }}
                            >
                              {drift > 0 ? "+" : ""}
                              {drift.toFixed(1)} pts
                            </td>
                            <td style={{ textAlign: "right" }}>
                              {result.risk_contributions
                                ? `${(result.risk_contributions[symbol] ?? 0).toFixed(1)}%`
                                : "—"}
                            </td>
                          </tr>
                        );
                      })}
                  </tbody>
                </table>
              </div>

              {result.frontier && result.frontier.points.length > 0 && (
                <div className="glass-panel" style={{ marginBottom: 20 }}>
                  <h3 style={{ marginTop: 0 }}>Efficient frontier</h3>
                  <div style={{ height: 320 }}>
                    <Scatter
                      data={{
                        datasets: [
                          {
                            label: "Frontier",
                            data: result.frontier.points.map((point) => ({
                              x: point.volatility_pct,
                              y: point.expected_return_pct,
                            })),
                            backgroundColor: "rgba(0, 240, 255, 0.7)",
                          },
                          {
                            label: "This portfolio's target",
                            data: [{ x: result.volatility_pct, y: result.expected_return_pct }],
                            backgroundColor: "rgba(245, 158, 11, 0.9)",
                            pointRadius: 7,
                          },
                        ],
                      }}
                      options={{
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: { legend: { labels: { color: "#94a3b8" } } },
                        scales: {
                          x: {
                            title: { display: true, text: "Volatility %", color: "#64748b" },
                            ticks: { color: "#64748b" },
                            grid: { color: "rgba(255,255,255,0.05)" },
                          },
                          y: {
                            title: { display: true, text: "Expected return %", color: "#64748b" },
                            ticks: { color: "#64748b" },
                            grid: { color: "rgba(255,255,255,0.05)" },
                          },
                        },
                      }}
                    />
                  </div>
                  <p style={{ color: "var(--text-muted)", fontSize: "0.8rem", marginBottom: 0 }}>
                    Expected returns are historical means, which forecast the future poorly. The
                    frontier is a map of the estimate, not of what will happen.
                  </p>
                </div>
              )}
            </>
          )}
        </section>
      )}

      {tab === "factors" && (
        <section>
          <button className="glowing-button" onClick={runFactors} disabled={busy !== null || equityCount < 2}>
            {busy === "factors" ? "Regressing…" : "Run factor regression"}
          </button>

          {factors && !factors.available && (
            <p style={{ color: "var(--color-hold)", marginTop: 16 }}>{factors.reason}</p>
          )}

          {factors?.available && factors.betas && (
            <>
              <div className="metrics-grid" style={{ margin: "20px 0" }}>
                <Stat label="Annual alpha" value={`${factors.alpha_annual_pct}%`} />
                <Stat label="R²" value={String(factors.r_squared)} sub={`${factors.observations} observations`} />
                <Stat
                  label="Explained by factors"
                  value={`${factors.attribution?.explained_by_factors_pct ?? 0}%`}
                />
                <Stat label="Idiosyncratic" value={`${factors.attribution?.idiosyncratic_pct ?? 0}%`} />
              </div>

              <div className="glass-panel" style={{ marginBottom: 20 }}>
                <h3 style={{ marginTop: 0 }}>Factor betas</h3>
                <div style={{ height: 300 }}>
                  <Bar
                    data={{
                      labels: Object.values(factors.betas).map((beta) => beta.label),
                      datasets: [
                        {
                          label: "Beta",
                          data: Object.values(factors.betas).map((beta) => beta.beta),
                          backgroundColor: Object.values(factors.betas).map((beta) =>
                            beta.beta >= 0 ? "rgba(0, 240, 255, 0.6)" : "rgba(239, 68, 68, 0.6)"
                          ),
                        },
                      ],
                    }}
                    options={{
                      indexAxis: "y" as const,
                      responsive: true,
                      maintainAspectRatio: false,
                      plugins: { legend: { display: false } },
                      scales: {
                        x: { ticks: { color: "#64748b" }, grid: { color: "rgba(255,255,255,0.05)" } },
                        y: { ticks: { color: "#94a3b8" }, grid: { display: false } },
                      },
                    }}
                  />
                </div>
              </div>

              <div className="custom-table-container" style={{ marginBottom: 20 }}>
                <table className="custom-table">
                  <thead>
                    <tr>
                      <th>Factor</th>
                      <th style={{ textAlign: "right" }}>Beta</th>
                      <th style={{ textAlign: "right" }}>t-stat</th>
                      <th style={{ textAlign: "right" }}>Return contribution</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(factors.betas).map(([name, beta]) => (
                      <tr key={name}>
                        <td>{beta.label}</td>
                        <td style={{ textAlign: "right" }}>{beta.beta.toFixed(2)}</td>
                        <td style={{ textAlign: "right", color: "var(--text-muted)" }}>
                          {beta.t_stat === null ? "—" : beta.t_stat.toFixed(2)}
                        </td>
                        <td style={{ textAlign: "right" }}>{beta.contribution_pct.toFixed(2)}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {factors.interpretation && (
                <div className="glass-panel glass-panel-cyan" style={{ marginBottom: 16 }}>
                  <p style={{ margin: 0, color: "var(--text-secondary)" }}>{factors.interpretation}</p>
                </div>
              )}

              <ul style={{ color: "var(--text-muted)", fontSize: "0.8rem", paddingLeft: 18 }}>
                {(factors.caveats ?? []).map((caveat, index) => (
                  <li key={index}>{caveat}</li>
                ))}
                {factors.weights_note && <li>{factors.weights_note}</li>}
              </ul>
            </>
          )}
        </section>
      )}

      {tab === "regime" && (
        <section>
          <button className="glowing-button" onClick={runRegime} disabled={busy !== null}>
            {busy === "regime" ? "Classifying…" : "Classify the regime"}
          </button>

          {regime && !regime.available && (
            <p style={{ color: "var(--color-hold)", marginTop: 16 }}>{regime.reason}</p>
          )}

          {regime?.available && regime.metrics && (
            <>
              <div
                className="glass-panel"
                style={{
                  margin: "20px 0",
                  borderColor: REGIME_TONE[regime.current_regime ?? ""] ?? "var(--border-subtle)",
                }}
              >
                <div
                  style={{
                    fontSize: "1.6rem",
                    fontWeight: 700,
                    color: REGIME_TONE[regime.current_regime ?? ""] ?? "var(--text-primary)",
                  }}
                >
                  {regime.current_regime_label}
                </div>
                <div style={{ color: "var(--text-muted)", fontSize: "0.85rem", marginTop: 4 }}>
                  {regime.days_in_regime} sessions in this state · benchmark {regime.benchmark} ·{" "}
                  {regime.used_portfolio_correlation
                    ? "portfolio correlation included"
                    : "benchmark only"}
                </div>
                <p style={{ color: "var(--text-secondary)", marginBottom: 0, marginTop: 10 }}>
                  {regime.guidance}
                </p>
              </div>

              <div className="metrics-grid" style={{ marginBottom: 20 }}>
                <Stat label="Volatility ratio" value={String(regime.metrics.volatility_ratio)} sub="vs its own one-year median" />
                <Stat label="Annualised volatility" value={`${regime.metrics.annualised_volatility_pct}%`} />
                <Stat label="Trend efficiency" value={String(regime.metrics.trend_efficiency)} />
                <Stat
                  label="Average correlation"
                  value={
                    regime.metrics.average_correlation === null
                      ? "—"
                      : String(regime.metrics.average_correlation)
                  }
                  sub="across your holdings"
                />
              </div>

              {regime.distribution && (
                <div className="glass-panel" style={{ marginBottom: 20 }}>
                  <h3 style={{ marginTop: 0 }}>Time spent in each regime</h3>
                  {Object.entries(regime.distribution).map(([name, share]) => (
                    <div key={name} style={{ marginBottom: 10 }}>
                      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.85rem" }}>
                        <span style={{ textTransform: "capitalize" }}>{name.replace("_", " ")}</span>
                        <span style={{ color: "var(--text-muted)" }}>{share}%</span>
                      </div>
                      <div style={{ height: 6, background: "rgba(255,255,255,0.07)", borderRadius: 3, marginTop: 4 }}>
                        <div
                          style={{
                            width: `${share}%`,
                            height: "100%",
                            borderRadius: 3,
                            background: REGIME_TONE[name] ?? "var(--accent-cyan)",
                          }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {regime.transitions && regime.transitions.length > 0 && (
                <div className="glass-panel" style={{ marginBottom: 20 }}>
                  <h3 style={{ marginTop: 0 }}>Recent transitions</h3>
                  <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                    {regime.transitions.slice(-8).reverse().map((transition, index) => (
                      <div key={index} style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>
                        <span style={{ color: "var(--text-muted)" }}>{transition.date.slice(0, 10)}</span>{" "}
                        {transition.from.replace("_", " ")} → {transition.to.replace("_", " ")}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <p style={{ color: "var(--text-muted)", fontSize: "0.8rem" }}>{regime.note}</p>
            </>
          )}
        </section>
      )}

      {tab === "orders" && (
        <section>
          <div className="glass-panel" style={{ marginBottom: 20, display: "flex", gap: 16, flexWrap: "wrap", alignItems: "flex-end" }}>
            <label style={{ flex: "0 1 200px" }}>
              <FieldLabel>Fresh cash to deploy ₹</FieldLabel>
              <input
                type="number"
                min={0}
                value={cashInflow}
                onChange={(event) => setCashInflow(Number(event.target.value))}
                style={inputStyle}
              />
            </label>
            <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: "0.85rem", paddingBottom: 8 }}>
              <input
                type="checkbox"
                checked={allowSelling}
                onChange={(event) => setAllowSelling(event.target.checked)}
              />
              Allow trimming (unchecked routes new cash only — zero realised tax)
            </label>
            <button className="glowing-button" onClick={runOrders} disabled={busy !== null || equityCount < 2}>
              {busy === "orders" ? "Building sheet…" : "Build order sheet"}
            </button>
          </div>

          {plan && (
            <>
              <div className="metrics-grid" style={{ marginBottom: 20 }}>
                <Stat label="Orders" value={String(plan.orders.length)} sub={`target from ${plan.target_source}`} />
                <Stat label="Cash deployed" value={formatCurrency(plan.cash_deployed_inr)} />
                <Stat label="Proceeds from trims" value={formatCurrency(plan.proceeds_from_trims_inr)} />
                <Stat
                  label="Estimated tax"
                  value={formatCurrency(
                    plan.tax_summary.total_estimated_tax_inr ?? plan.tax_summary.total_tax_inr ?? 0
                  )}
                  sub={plan.financial_year}
                />
              </div>

              {plan.notes.length > 0 && (
                <div className="glass-panel" style={{ marginBottom: 20 }}>
                  <ul style={{ color: "var(--text-secondary)", fontSize: "0.85rem", paddingLeft: 18, margin: 0 }}>
                    {plan.notes.map((note, index) => (
                      <li key={index} style={{ marginBottom: 4 }}>
                        {note}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              <div className="custom-table-container" style={{ marginBottom: 20 }}>
                <table className="custom-table">
                  <thead>
                    <tr>
                      <th>Action</th>
                      <th>Holding</th>
                      <th style={{ textAlign: "right" }}>Weight</th>
                      <th style={{ textAlign: "right" }}>Units</th>
                      <th style={{ textAlign: "right" }}>Price</th>
                      <th style={{ textAlign: "right" }}>Amount</th>
                      <th style={{ textAlign: "right" }}>Tax impact</th>
                      <th>Why</th>
                    </tr>
                  </thead>
                  <tbody>
                    {plan.orders.map((order, index) => (
                      <tr key={`${order.key}-${index}`}>
                        <td
                          style={{
                            fontWeight: 600,
                            color:
                              order.action === "BUY"
                                ? "var(--color-buy)"
                                : order.action === "TRIM"
                                  ? "var(--color-sell)"
                                  : "var(--text-muted)",
                          }}
                        >
                          {order.action}
                        </td>
                        <td>
                          <div style={{ fontWeight: 600 }}>{order.name}</div>
                          <div style={{ color: "var(--text-muted)", fontSize: "0.78rem" }}>{order.key}</div>
                        </td>
                        <td style={{ textAlign: "right", color: "var(--text-secondary)", fontSize: "0.82rem" }}>
                          {order.current_weight_pct?.toFixed(1)}% → {order.target_weight_pct?.toFixed(1)}%
                        </td>
                        <td style={{ textAlign: "right" }}>{formatNumber(order.units, 2)}</td>
                        <td style={{ textAlign: "right" }}>{formatNumber(order.estimated_price)}</td>
                        <td style={{ textAlign: "right" }}>{formatCurrency(order.estimated_amount)}</td>
                        <td style={{ textAlign: "right", color: order.tax_impact_inr > 0 ? "var(--color-sell)" : "var(--text-muted)" }}>
                          {formatCurrency(order.tax_impact_inr)}
                        </td>
                        <td style={{ color: "var(--text-secondary)", fontSize: "0.82rem" }}>{order.reason}</td>
                      </tr>
                    ))}
                    {plan.orders.length === 0 && (
                      <tr>
                        <td colSpan={8} style={{ textAlign: "center", color: "var(--text-muted)" }}>
                          Nothing drifted far enough to be worth the friction.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>

              <p style={{ color: "var(--text-muted)", fontSize: "0.8rem" }}>{plan.disclaimer}</p>
            </>
          )}
        </section>
      )}
    </div>
  );
}

const FALLBACK_METHODS: MethodInfo[] = [
  { name: "hrp", label: "Hierarchical risk parity", recommended: true, note: "" },
  { name: "risk_parity", label: "Equal risk contribution", note: "" },
  { name: "min_variance", label: "Minimum variance", note: "" },
  { name: "max_sharpe", label: "Maximum Sharpe", note: "" },
];

const inputStyle: React.CSSProperties = {
  width: "100%",
  background: "var(--bg-secondary)",
  border: "1px solid var(--border-subtle)",
  borderRadius: 8,
  color: "var(--text-primary)",
  padding: "8px 10px",
  fontSize: "0.9rem",
};

function FieldLabel({ children }: { children: React.ReactNode }) {
  return (
    <span
      style={{
        display: "block",
        color: "var(--text-muted)",
        fontSize: "0.72rem",
        textTransform: "uppercase",
        letterSpacing: "0.05em",
        marginBottom: 6,
      }}
    >
      {children}
    </span>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button className={active ? "glowing-button" : "secondary-button"} onClick={onClick}>
      {children}
    </button>
  );
}

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="glass-panel metric-card">
      <div
        style={{
          color: "var(--text-muted)",
          fontSize: "0.75rem",
          textTransform: "uppercase",
          letterSpacing: "0.05em",
        }}
      >
        {label}
      </div>
      <div style={{ fontSize: "1.4rem", fontWeight: 600, marginTop: 6 }}>{value}</div>
      {sub && <div style={{ color: "var(--text-secondary)", fontSize: "0.8rem", marginTop: 2 }}>{sub}</div>}
    </div>
  );
}
