"use client";

import { useEffect, useMemo, useState } from "react";
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
import {
  OBJECTIVES,
  SIZERS,
  listStrategies,
  runEngine,
  walkForward,
  type EngineRunResult,
  type StrategySpec,
  type WalkForwardResult,
} from "@/lib/engineApi";
import { formatCurrency, formatNumber } from "@/lib/portfolioApi";

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Tooltip, Legend, Filler);

// The v2 engine's whole reason for existing is that it cannot express a
// look-ahead trade: a signal on today's close fills at tomorrow's open. That
// is stated on the page because it is the difference between these numbers
// and the ones the Phase-2 backtester produces.

const today = new Date();
const iso = (date: Date) => date.toISOString().slice(0, 10);
const yearsAgo = (years: number) => {
  const date = new Date(today);
  date.setFullYear(date.getFullYear() - years);
  return iso(date);
};

export default function StrategyLab() {
  const [strategies, setStrategies] = useState<StrategySpec[]>([]);
  const [symbol, setSymbol] = useState("RELIANCE");
  const [strategy, setStrategy] = useState("rsi");
  const [start, setStart] = useState(yearsAgo(5));
  const [end, setEnd] = useState(iso(today));
  const [capital, setCapital] = useState(100000);
  const [sizerName, setSizerName] = useState("percent");
  const [slippage, setSlippage] = useState(0.05);
  const [permutation, setPermutation] = useState(true);

  const [folds, setFolds] = useState(4);
  const [objective, setObjective] = useState("sharpe");

  const [result, setResult] = useState<EngineRunResult | null>(null);
  const [wf, setWf] = useState<WalkForwardResult | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    listStrategies(controller.signal)
      .then((response) => setStrategies(response.strategies))
      .catch(() => setStrategies([]));
    return () => controller.abort();
  }, []);

  const spec = useMemo(
    () => strategies.find((entry) => entry.name === strategy),
    [strategies, strategy]
  );

  const basePayload = () => ({
    symbol,
    start,
    end,
    strategy,
    initial_capital: capital,
    sizer: { name: sizerName, params: {} },
    costs: {
      brokerage_pct: 0.0003,
      brokerage_cap: 20,
      stt_pct: 0.001,
      slippage_pct: slippage / 100,
    },
  });

  const run = async () => {
    setBusy("run");
    setError(null);
    try {
      setResult(
        await runEngine({ ...basePayload(), permutation_test: permutation, permutations: 1000 })
      );
    } catch (err) {
      setError((err as Error).message);
      setResult(null);
    } finally {
      setBusy(null);
    }
  };

  const runWalkForward = async () => {
    setBusy("wf");
    setError(null);
    try {
      setWf(
        await walkForward({
          ...basePayload(),
          folds,
          in_sample_ratio: 0.7,
          objective,
        })
      );
    } catch (err) {
      setError((err as Error).message);
      setWf(null);
    } finally {
      setBusy(null);
    }
  };

  const performance = result?.performance;
  const benchmark = result?.benchmark;

  return (
    <div className="app-container animate-fade-in">
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ margin: 0, fontSize: "1.9rem" }}>Strategy Lab</h1>
        <p style={{ color: "var(--text-secondary)", margin: "6px 0 0", maxWidth: 800 }}>
          The event-driven engine: a signal on today&apos;s close fills at tomorrow&apos;s open,
          with slippage, brokerage and STT charged on every fill. Walk-forward and permutation
          testing are here because a backtest that has never been tested out-of-sample flatters
          whatever was fitted to it.
        </p>
      </div>

      <div className="glass-panel" style={{ marginBottom: 20 }}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 14 }}>
          <label>
            <FieldLabel>Symbol</FieldLabel>
            <input value={symbol} onChange={(e) => setSymbol(e.target.value.toUpperCase())} style={inputStyle} />
          </label>
          <label>
            <FieldLabel>Strategy</FieldLabel>
            <select value={strategy} onChange={(e) => setStrategy(e.target.value)} style={inputStyle}>
              {strategies.map((entry) => (
                <option key={entry.name} value={entry.name}>
                  {entry.label}
                </option>
              ))}
              {strategies.length === 0 && <option value="rsi">RSI mean reversion</option>}
            </select>
          </label>
          <label>
            <FieldLabel>From</FieldLabel>
            <input type="date" value={start} onChange={(e) => setStart(e.target.value)} style={inputStyle} />
          </label>
          <label>
            <FieldLabel>To</FieldLabel>
            <input type="date" value={end} onChange={(e) => setEnd(e.target.value)} style={inputStyle} />
          </label>
          <label>
            <FieldLabel>Capital ₹</FieldLabel>
            <input type="number" value={capital} onChange={(e) => setCapital(Number(e.target.value))} style={inputStyle} />
          </label>
          <label>
            <FieldLabel>Position sizer</FieldLabel>
            <select value={sizerName} onChange={(e) => setSizerName(e.target.value)} style={inputStyle}>
              {SIZERS.map((sizer) => (
                <option key={sizer.name} value={sizer.name}>
                  {sizer.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            <FieldLabel>Slippage %</FieldLabel>
            <input
              type="number"
              step="0.01"
              value={slippage}
              onChange={(e) => setSlippage(Number(e.target.value))}
              style={inputStyle}
            />
          </label>
        </div>

        {spec && (
          <p style={{ color: "var(--text-muted)", fontSize: "0.82rem", marginTop: 12, marginBottom: 0 }}>
            {spec.label} · {spec.family.replace("_", " ")} · defaults{" "}
            {Object.entries(spec.params)
              .map(([key, value]) => `${key}=${value}`)
              .join(", ")}
          </p>
        )}

        <div style={{ display: "flex", gap: 12, marginTop: 16, flexWrap: "wrap", alignItems: "center" }}>
          <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: "0.85rem" }}>
            <input
              type="checkbox"
              checked={permutation}
              onChange={(event) => setPermutation(event.target.checked)}
            />
            Also run a 1,000-shuffle permutation test
          </label>
          <button className="glowing-button" onClick={run} disabled={busy !== null}>
            {busy === "run" ? "Running…" : "Run backtest"}
          </button>
        </div>
      </div>

      {error && (
        <div className="glass-panel" style={{ borderColor: "var(--color-sell)", marginBottom: 20 }}>
          <strong style={{ color: "var(--color-sell)" }}>That run failed</strong>
          <p style={{ margin: "6px 0 0", color: "var(--text-secondary)" }}>{error}</p>
        </div>
      )}

      {result && performance?.available && (
        <>
          <div className="metrics-grid" style={{ marginBottom: 20 }}>
            <Stat
              label="Total return"
              value={`${performance.total_return_pct ?? "—"}%`}
              sub={`CAGR ${performance.cagr_pct ?? "—"}%`}
              tone={(performance.total_return_pct ?? 0) >= 0 ? "var(--color-buy)" : "var(--color-sell)"}
            />
            <Stat
              label="Alpha vs buy & hold"
              value={result.alpha_vs_buy_hold_pct === null ? "—" : `${result.alpha_vs_buy_hold_pct}%`}
              sub={`Benchmark ${benchmark?.total_return_pct ?? "—"}%`}
              tone={(result.alpha_vs_buy_hold_pct ?? 0) >= 0 ? "var(--color-buy)" : "var(--color-sell)"}
            />
            <Stat
              label="Sharpe / Sortino"
              value={`${performance.sharpe ?? "—"} / ${performance.sortino ?? "—"}`}
              sub={`Calmar ${performance.calmar ?? "—"}`}
            />
            <Stat
              label="Max drawdown"
              value={`${performance.max_drawdown_pct ?? "—"}%`}
              sub={performance.drawdown_recovered ? "Recovered" : "Never recovered in window"}
              tone="var(--color-sell)"
            />
          </div>

          <div className="metrics-grid" style={{ marginBottom: 20 }}>
            <Stat label="Final equity" value={formatCurrency(performance.final_equity ?? 0)} />
            <Stat
              label="Trades"
              value={String(performance.trades?.trade_count ?? 0)}
              sub={
                performance.trades?.win_rate_pct !== undefined
                  ? `${performance.trades.win_rate_pct}% won`
                  : performance.trades?.note
              }
            />
            <Stat
              label="Profit factor"
              value={
                performance.trades?.profit_factor === null || performance.trades?.profit_factor === undefined
                  ? "—"
                  : String(performance.trades.profit_factor)
              }
              sub={`Exposure ${performance.exposure_pct ?? "—"}%`}
            />
            <Stat label="Turnover" value={`${performance.turnover_x ?? "—"}×`} sub="per year" />
          </div>

          <div className="glass-panel" style={{ marginBottom: 20 }}>
            <h3 style={{ marginTop: 0 }}>Equity curve</h3>
            <div style={{ height: 320 }}>
              <Line
                data={{
                  labels: result.equity_curve.map((point) => point.date.slice(0, 10)),
                  datasets: [
                    {
                      label: "Strategy equity",
                      data: result.equity_curve.map((point) => point.equity),
                      borderColor: "#2563eb",
                      backgroundColor: "rgba(37, 99, 235, 0.08)",
                      fill: true,
                      pointRadius: 0,
                      borderWidth: 2,
                    },
                    {
                      label: "Cash",
                      data: result.equity_curve.map((point) => point.cash),
                      borderColor: "rgba(100, 116, 139, 0.6)",
                      pointRadius: 0,
                      borderWidth: 1,
                      borderDash: [4, 4],
                    },
                  ],
                }}
                options={{
                  responsive: true,
                  maintainAspectRatio: false,
                  plugins: { legend: { labels: { color: "#475569", font: { family: "Inter", size: 11 } } } },
                  scales: {
                    x: { ticks: { color: "#64748b", maxTicksLimit: 10, font: { size: 10 } }, grid: { display: false } },
                    y: { ticks: { color: "#64748b", font: { family: "JetBrains Mono", size: 10 } }, grid: { color: "#f1f5f9" } },
                  },
                }}
              />
            </div>
            <p style={{ color: "var(--text-muted)", fontSize: "0.8rem", marginBottom: 0 }}>
              {result.bars} bars loaded, {result.warmup_bars} consumed by indicator warm-up,{" "}
              {result.tradeable_bars} tradeable.
            </p>
          </div>

          {result.permutation_test && (
            <div
              className="glass-panel"
              style={{
                marginBottom: 20,
                borderColor: result.permutation_test.significant_at_5pct
                  ? "var(--color-buy)"
                  : "var(--color-hold)",
              }}
            >
              <h3 style={{ marginTop: 0 }}>Is this edge distinguishable from luck?</h3>
              {result.permutation_test.available ? (
                <>
                  <div className="metrics-grid">
                    <Stat label="p (return)" value={String(result.permutation_test.p_value_return)} />
                    <Stat label="p (Sharpe)" value={String(result.permutation_test.p_value_sharpe)} />
                    <Stat label="Actual return" value={`${result.permutation_test.actual_return_pct}%`} />
                    <Stat
                      label="Shuffled p95"
                      value={`${result.permutation_test.permuted_return_p95_pct}%`}
                      sub={`${result.permutation_test.permutations} shuffles`}
                    />
                  </div>
                  <p style={{ color: "var(--text-secondary)", marginTop: 14, marginBottom: 4 }}>
                    {result.permutation_test.verdict}
                  </p>
                  <p style={{ color: "var(--text-muted)", fontSize: "0.82rem", margin: 0 }}>
                    {result.permutation_test.caveat}
                  </p>
                </>
              ) : (
                <p style={{ color: "var(--color-hold)", margin: 0 }}>{result.permutation_test.reason}</p>
              )}
            </div>
          )}

          {result.trades.length > 0 && (
            <div className="glass-panel" style={{ marginBottom: 20 }}>
              <h3 style={{ marginTop: 0 }}>Round trips</h3>
              <div className="custom-table-container" style={{ maxHeight: 360, overflowY: "auto" }}>
                <table className="custom-table">
                  <thead>
                    <tr>
                      <th>Entry</th>
                      <th>Exit</th>
                      <th style={{ textAlign: "right" }}>Qty</th>
                      <th style={{ textAlign: "right" }}>In</th>
                      <th style={{ textAlign: "right" }}>Out</th>
                      <th style={{ textAlign: "right" }}>P&L</th>
                      <th style={{ textAlign: "right" }}>Bars</th>
                      <th>Why it closed</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.trades.map((trade, index) => (
                      <tr key={index}>
                        <td style={{ color: "var(--text-muted)" }}>{trade.entry_date.slice(0, 10)}</td>
                        <td style={{ color: "var(--text-muted)" }}>{trade.exit_date.slice(0, 10)}</td>
                        <td style={{ textAlign: "right" }}>{formatNumber(trade.quantity, 0)}</td>
                        <td style={{ textAlign: "right" }}>{formatNumber(trade.entry_price)}</td>
                        <td style={{ textAlign: "right" }}>{formatNumber(trade.exit_price)}</td>
                        <td
                          style={{
                            textAlign: "right",
                            color: trade.pnl >= 0 ? "var(--color-buy)" : "var(--color-sell)",
                          }}
                        >
                          {formatCurrency(trade.pnl)}
                          <div style={{ fontSize: "0.78rem" }}>{trade.return_pct.toFixed(2)}%</div>
                        </td>
                        <td style={{ textAlign: "right" }}>{trade.bars_held}</td>
                        <td style={{ color: "var(--text-secondary)", fontSize: "0.82rem" }}>{trade.reason}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}

      {result && !result.performance?.available && (
        <div className="glass-panel" style={{ marginBottom: 20 }}>
          <p style={{ margin: 0, color: "var(--color-hold)" }}>{result.performance?.reason}</p>
        </div>
      )}

      <div className="glass-panel glass-panel-cyan" style={{ marginBottom: 20 }}>
        <h3 style={{ marginTop: 0 }}>Walk-forward optimisation</h3>
        <p style={{ color: "var(--text-secondary)", marginTop: 0 }}>
          Fit the parameters on the first part of each fold, measure on the part that follows. The
          out-of-sample number is the only performance figure in this system that was never fitted
          to the data it is measured on.
        </p>
        <div style={{ display: "flex", gap: 14, flexWrap: "wrap", alignItems: "flex-end" }}>
          <label style={{ flex: "0 1 120px" }}>
            <FieldLabel>Folds</FieldLabel>
            <input
              type="number"
              min={2}
              max={8}
              value={folds}
              onChange={(event) => setFolds(Number(event.target.value))}
              style={inputStyle}
            />
          </label>
          <label style={{ flex: "0 1 180px" }}>
            <FieldLabel>Optimise for</FieldLabel>
            <select value={objective} onChange={(event) => setObjective(event.target.value)} style={inputStyle}>
              {OBJECTIVES.map((entry) => (
                <option key={entry} value={entry}>
                  {entry.replace("_", " ")}
                </option>
              ))}
            </select>
          </label>
          <button className="glowing-button" onClick={runWalkForward} disabled={busy !== null}>
            {busy === "wf" ? "Optimising fold by fold…" : "Run walk-forward"}
          </button>
        </div>

        {wf && (
          <div style={{ marginTop: 18 }}>
            <div className="metrics-grid">
              <Stat
                label="Mean in-sample"
                value={wf.mean_in_sample_return_pct === null ? "—" : `${wf.mean_in_sample_return_pct}%`}
              />
              <Stat
                label="Mean out-of-sample"
                value={
                  wf.mean_out_of_sample_return_pct === null ? "—" : `${wf.mean_out_of_sample_return_pct}%`
                }
                tone={(wf.mean_out_of_sample_return_pct ?? 0) >= 0 ? "var(--color-buy)" : "var(--color-sell)"}
              />
              <Stat
                label="Efficiency"
                value={wf.walk_forward_efficiency === null ? "—" : String(wf.walk_forward_efficiency)}
                sub={`${wf.positive_oos_folds} of ${wf.completed_folds} folds positive`}
              />
              <Stat
                label="Parameter stability"
                value={`${wf.distinct_parameter_sets} distinct sets`}
                sub={`${wf.grid_combinations} combinations per fold`}
              />
            </div>
            <p style={{ color: "var(--text-secondary)", marginTop: 14 }}>{wf.verdict}</p>
          </div>
        )}
      </div>

      <p style={{ color: "var(--text-muted)", fontSize: "0.8rem", marginTop: 28 }}>
        Backtests are simulations over past prices. Nothing here is an order, a forecast, or advice.
      </p>
    </div>
  );
}

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

function Stat({ label, value, sub, tone }: { label: string; value: string; sub?: string; tone?: string }) {
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
      <div style={{ fontSize: "1.4rem", fontWeight: 600, marginTop: 6, color: tone ?? "var(--text-primary)" }}>
        {value}
      </div>
      {sub && <div style={{ color: "var(--text-secondary)", fontSize: "0.8rem", marginTop: 2 }}>{sub}</div>}
    </div>
  );
}
