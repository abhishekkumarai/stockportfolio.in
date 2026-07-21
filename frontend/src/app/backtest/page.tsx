"use client";

import { useState } from "react";
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
  ScriptableContext
} from "chart.js";
import { Line } from "react-chartjs-2";
import { apiUrl } from "@/lib/api";

// Register Chart.js components
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

interface Trade {
  date: string;
  type: string;
  price: number;
  shares: number;
  fee: number;
  remaining_cash: number;
  portfolio_value: number;
}

interface BacktestResult {
  summary: {
    symbol: string;
    strategy: string;
    start_date: string;
    end_date: string;
    initial_capital: number;
    final_value: number;
    total_return_pct: number;
    cagr_pct: number;
    benchmark_return_pct: number;
    max_drawdown_pct: number;
    sharpe_ratio: number;
    win_rate_pct: number;
    total_trades: number;
    completed_trades: number;
  };
  trades: Trade[];
  equity_curve: Array<{
    date: string;
    strategy_value: number;
    benchmark_value: number;
  }>;
}

export default function BacktestPage() {
  const [ticker, setTicker] = useState("RELIANCE");
  const [strategy, setStrategy] = useState("RSI");
  const [startDate, setStartDate] = useState("2025-01-01");
  const [endDate, setEndDate] = useState("2025-12-31");
  const [initialCapital, setInitialCapital] = useState(100000);
  const [fee, setFee] = useState(0.001);
  const [rsiOversold, setRsiOversold] = useState(30);
  const [rsiOverbought, setRsiOverbought] = useState(70);
  const [smaFast, setSmaFast] = useState(20);
  const [smaSlow, setSmaSlow] = useState(50);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<BacktestResult | null>(null);

  const handleRunBacktest = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);

    const payload = {
      ticker,
      strategy,
      startDate,
      endDate,
      initialCapital,
      fee,
      rsiOversold,
      rsiOverbought,
      smaFast,
      smaSlow,
    };

    try {
      const response = await fetch(apiUrl("/api/backtest"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        throw new Error(`Server returned error: ${response.status}`);
      }

      const data = await response.json();
      setResult(data);
    } catch (err: any) {
      console.error(err);
      setError(err.message || "An error occurred while running backtest.");
    } finally {
      setLoading(false);
    }
  };

  // Setup Equity Curve Chart Data
  const chartLabels = result ? result.equity_curve.map(d => d.date) : [];
  const chartStrategyData = result ? result.equity_curve.map(d => d.strategy_value) : [];
  const chartBenchmarkData = result ? result.equity_curve.map(d => d.benchmark_value) : [];

  const chartConfigData = {
    labels: chartLabels,
    datasets: [
      {
        label: "Strategy Value",
        data: chartStrategyData,
        borderColor: "#00f0ff",
        borderWidth: 2.5,
        pointRadius: 0,
        pointHoverRadius: 4,
        fill: true,
        backgroundColor: (context: ScriptableContext<"line">) => {
          const ctx = context.chart.ctx;
          const gradient = ctx.createLinearGradient(0, 0, 0, context.chart.height);
          gradient.addColorStop(0, "rgba(0, 240, 255, 0.2)");
          gradient.addColorStop(1, "rgba(0, 240, 255, 0.0)");
          return gradient;
        },
        tension: 0.1,
      },
      {
        label: "Buy & Hold Benchmark",
        data: chartBenchmarkData,
        borderColor: "#64748b",
        borderWidth: 1.5,
        borderDash: [5, 5],
        pointRadius: 0,
        pointHoverRadius: 0,
        fill: false,
        tension: 0.1,
      }
    ]
  };

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        display: true,
        labels: {
          color: "#94a3b8",
          font: { family: "Outfit", size: 12 }
        }
      },
      tooltip: {
        backgroundColor: "rgba(10, 11, 16, 0.95)",
        titleFont: { family: "Outfit", size: 12 },
        bodyFont: { family: "Inter", size: 12 },
        borderColor: "rgba(0, 240, 255, 0.2)",
        borderWidth: 1,
        padding: 12,
        mode: "index" as const,
        intersect: false
      }
    },
    scales: {
      x: {
        grid: { display: false },
        ticks: {
          color: "#64748b",
          font: { family: "Inter", size: 10 },
          maxTicksLimit: 10
        }
      },
      y: {
        grid: { color: "rgba(255, 255, 255, 0.04)" },
        ticks: {
          color: "#64748b",
          font: { family: "Inter", size: 10 },
          callback: (value: any) => `₹${value.toLocaleString()}`
        }
      }
    }
  };

  return (
    <div className="app-container animate-fade-in">
      <section style={{ marginBottom: "40px" }}>
        <h1 style={{ fontSize: "2.5rem", fontWeight: 800, marginBottom: "10px" }}>Historical Strategy Backtester</h1>
        <p>Configure trading strategies and backtest them on historical stock prices (NSE & BSE) to compare performance against a Buy & Hold benchmark.</p>
      </section>

      {/* Grid: Form config (left) vs Results (right) */}
      <div style={{
        display: "grid",
        gridTemplateColumns: "1fr 2fr",
        gap: "30px",
        alignItems: "flex-start",
        marginBottom: "40px"
      }}>
        {/* Strategy Parameters Form */}
        <div className="glass-panel" style={{ padding: "30px" }}>
          <h3 style={{ fontSize: "1.2rem", fontWeight: 600, borderBottom: "1px solid var(--border-subtle)", paddingBottom: "10px", marginBottom: "20px" }}>
            Parameters
          </h3>

          <form onSubmit={handleRunBacktest} style={{ display: "flex", flexDirection: "column", gap: "18px" }}>
            <div>
              <label style={{ fontSize: "0.8rem", color: "var(--text-secondary)", textTransform: "uppercase", display: "block", marginBottom: "6px", fontWeight: 600 }}>
                Stock Ticker
              </label>
              <input
                type="text"
                style={{ width: "100%", background: "rgba(255,255,255,0.03)", border: "1px solid var(--border-subtle)", borderRadius: "8px", padding: "10px 14px", color: "#fff", outline: "none" }}
                value={ticker}
                onChange={(e) => setTicker(e.target.value)}
                placeholder="RELIANCE"
                required
              />
            </div>

            <div>
              <label style={{ fontSize: "0.8rem", color: "var(--text-secondary)", textTransform: "uppercase", display: "block", marginBottom: "6px", fontWeight: 600 }}>
                Strategy
              </label>
              <select
                style={{ width: "100%", background: "rgba(10,11,16,0.95)", border: "1px solid var(--border-subtle)", borderRadius: "8px", padding: "10px 14px", color: "#fff", outline: "none" }}
                value={strategy}
                onChange={(e) => setStrategy(e.target.value)}
              >
                <option value="RSI">RSI (Oversold/Overbought)</option>
                <option value="SMA_Crossover">SMA Crossover (Fast/Slow)</option>
                <option value="Hybrid">Hybrid (RSI + SMA Crossover)</option>
              </select>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
              <div>
                <label style={{ fontSize: "0.8rem", color: "var(--text-secondary)", textTransform: "uppercase", display: "block", marginBottom: "6px", fontWeight: 600 }}>
                  Start Date
                </label>
                <input
                  type="date"
                  style={{ width: "100%", background: "rgba(255,255,255,0.03)", border: "1px solid var(--border-subtle)", borderRadius: "8px", padding: "10px 14px", color: "#fff", outline: "none" }}
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  required
                />
              </div>
              <div>
                <label style={{ fontSize: "0.8rem", color: "var(--text-secondary)", textTransform: "uppercase", display: "block", marginBottom: "6px", fontWeight: 600 }}>
                  End Date
                </label>
                <input
                  type="date"
                  style={{ width: "100%", background: "rgba(255,255,255,0.03)", border: "1px solid var(--border-subtle)", borderRadius: "8px", padding: "10px 14px", color: "#fff", outline: "none" }}
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  required
                />
              </div>
            </div>

            <div>
              <label style={{ fontSize: "0.8rem", color: "var(--text-secondary)", textTransform: "uppercase", display: "block", marginBottom: "6px", fontWeight: 600 }}>
                Initial Capital (INR)
              </label>
              <input
                type="number"
                style={{ width: "100%", background: "rgba(255,255,255,0.03)", border: "1px solid var(--border-subtle)", borderRadius: "8px", padding: "10px 14px", color: "#fff", outline: "none" }}
                value={initialCapital}
                onChange={(e) => setInitialCapital(Number(e.target.value))}
                min="100"
                required
              />
            </div>

            <div>
              <label style={{ fontSize: "0.8rem", color: "var(--text-secondary)", textTransform: "uppercase", display: "block", marginBottom: "6px", fontWeight: 600 }}>
                Broker Fee (Fraction)
              </label>
              <input
                type="number"
                step="0.0001"
                style={{ width: "100%", background: "rgba(255,255,255,0.03)", border: "1px solid var(--border-subtle)", borderRadius: "8px", padding: "10px 14px", color: "#fff", outline: "none" }}
                value={fee}
                onChange={(e) => setFee(Number(e.target.value))}
                min="0"
                max="0.05"
                required
              />
            </div>

            {strategy === "RSI" || strategy === "Hybrid" ? (
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px", borderTop: "1px solid var(--border-subtle)", paddingTop: "14px" }}>
                <div>
                  <label style={{ fontSize: "0.8rem", color: "var(--text-secondary)", textTransform: "uppercase", display: "block", marginBottom: "6px", fontWeight: 600 }}>
                    RSI Buy Thr.
                  </label>
                  <input
                    type="number"
                    style={{ width: "100%", background: "rgba(255,255,255,0.03)", border: "1px solid var(--border-subtle)", borderRadius: "8px", padding: "10px 14px", color: "#fff", outline: "none" }}
                    value={rsiOversold}
                    onChange={(e) => setRsiOversold(Number(e.target.value))}
                    min="5"
                    max="95"
                  />
                </div>
                <div>
                  <label style={{ fontSize: "0.8rem", color: "var(--text-secondary)", textTransform: "uppercase", display: "block", marginBottom: "6px", fontWeight: 600 }}>
                    RSI Sell Thr.
                  </label>
                  <input
                    type="number"
                    style={{ width: "100%", background: "rgba(255,255,255,0.03)", border: "1px solid var(--border-subtle)", borderRadius: "8px", padding: "10px 14px", color: "#fff", outline: "none" }}
                    value={rsiOverbought}
                    onChange={(e) => setRsiOverbought(Number(e.target.value))}
                    min="5"
                    max="95"
                  />
                </div>
              </div>
            ) : null}

            {strategy === "SMA_Crossover" || strategy === "Hybrid" ? (
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px", borderTop: "1px solid var(--border-subtle)", paddingTop: "14px" }}>
                <div>
                  <label style={{ fontSize: "0.8rem", color: "var(--text-secondary)", textTransform: "uppercase", display: "block", marginBottom: "6px", fontWeight: 600 }}>
                    SMA Fast Period
                  </label>
                  <input
                    type="number"
                    style={{ width: "100%", background: "rgba(255,255,255,0.03)", border: "1px solid var(--border-subtle)", borderRadius: "8px", padding: "10px 14px", color: "#fff", outline: "none" }}
                    value={smaFast}
                    onChange={(e) => setSmaFast(Number(e.target.value))}
                    min="2"
                    max="100"
                  />
                </div>
                <div>
                  <label style={{ fontSize: "0.8rem", color: "var(--text-secondary)", textTransform: "uppercase", display: "block", marginBottom: "6px", fontWeight: 600 }}>
                    SMA Slow Period
                  </label>
                  <input
                    type="number"
                    style={{ width: "100%", background: "rgba(255,255,255,0.03)", border: "1px solid var(--border-subtle)", borderRadius: "8px", padding: "10px 14px", color: "#fff", outline: "none" }}
                    value={smaSlow}
                    onChange={(e) => setSmaSlow(Number(e.target.value))}
                    min="5"
                    max="300"
                  />
                </div>
              </div>
            ) : null}

            <button type="submit" className="glowing-button" style={{ marginTop: "10px" }} disabled={loading}>
              {loading ? "Simulating..." : "📈 Run Simulation"}
            </button>
          </form>
        </div>

        {/* Results Area */}
        <div style={{ display: "flex", flexDirection: "column", gap: "30px", minHeight: "450px" }}>
          {loading ? (
            <div className="glass-panel loading-container" style={{ flex: 1 }}>
              <div className="spinner"></div>
              <h3 style={{ color: "var(--text-secondary)" }}>Running Historical Simulation...</h3>
              <p style={{ fontSize: "0.9rem" }}>Downloading historical data and processing day-by-day signals</p>
            </div>
          ) : error ? (
            <div className="glass-panel" style={{ padding: "40px", textAlign: "center", flex: 1, display: "flex", flexDirection: "column", justifyContent: "center", alignItems: "center" }}>
              <div style={{ fontSize: "2.5rem", marginBottom: "15px" }}>❌</div>
              <h3 style={{ marginBottom: "10px" }}>Simulation Failed</h3>
              <p>{error}</p>
            </div>
          ) : !result ? (
            <div className="glass-panel" style={{ padding: "40px", textAlign: "center", flex: 1, display: "flex", flexDirection: "column", justifyContent: "center", alignItems: "center", color: "var(--text-secondary)" }}>
              <div style={{ fontSize: "3rem", marginBottom: "15px" }}>📊</div>
              <h3>No Active Simulation</h3>
              <p style={{ maxWidth: "400px", margin: "10px auto 0 auto" }}>Adjust parameters on the left and click &quot;Run Simulation&quot; to inspect strategy metrics and equity charts.</p>
            </div>
          ) : (
            <>
              {/* Backtest Statistics Cards Grid */}
              <div className="metrics-grid">
                <div className="glass-panel metric-card">
                  <div className="title">Strategy Return</div>
                  <div className="value" style={{ color: result.summary.total_return_pct >= 0 ? "var(--color-buy)" : "var(--color-sell)" }}>
                    {result.summary.total_return_pct >= 0 ? "+" : ""}{result.summary.total_return_pct}%
                  </div>
                  <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: "4px" }}>
                    CAGR: {result.summary.cagr_pct}%
                  </div>
                </div>

                <div className="glass-panel metric-card">
                  <div className="title">Benchmark Return</div>
                  <div className="value" style={{ color: result.summary.benchmark_return_pct >= 0 ? "var(--color-buy)" : "var(--color-sell)" }}>
                    {result.summary.benchmark_return_pct >= 0 ? "+" : ""}{result.summary.benchmark_return_pct}%
                  </div>
                  <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: "4px" }}>
                    Buy & Hold Index
                  </div>
                </div>

                <div className="glass-panel metric-card">
                  <div className="title">Max Drawdown</div>
                  <div className="value" style={{ color: "var(--color-sell)" }}>
                    {result.summary.max_drawdown_pct}%
                  </div>
                  <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: "4px" }}>
                    Peak-to-trough risk
                  </div>
                </div>

                <div className="glass-panel metric-card">
                  <div className="title">Trades Executed</div>
                  <div className="value">{result.summary.total_trades}</div>
                  <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: "4px" }}>
                    Win Rate: {result.summary.win_rate_pct}% (Sharpe: {result.summary.sharpe_ratio})
                  </div>
                </div>
              </div>

              {/* Equity curve chart */}
              <div className="glass-panel" style={{ padding: "30px", minHeight: "380px", display: "flex", flexDirection: "column" }}>
                <h3 style={{ fontSize: "1.2rem", fontWeight: 600, marginBottom: "20px" }}>Portfolio Equity Curve comparison</h3>
                <div style={{ flex: 1, position: "relative", height: "100%", minHeight: "260px" }}>
                  <Line data={chartConfigData} options={chartOptions} />
                </div>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Trades History Table */}
      {result && result.trades.length > 0 && (
        <section className="animate-fade-in" style={{ marginTop: "40px" }}>
          <h3 style={{ fontSize: "1.4rem", fontWeight: 700, marginBottom: "20px" }}>📜 Transaction Log</h3>
          <div className="custom-table-container">
            <table className="custom-table">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Action</th>
                  <th>Execution Price</th>
                  <th>Quantity Traded</th>
                  <th>Broker Fee</th>
                  <th>Remaining Cash</th>
                  <th>Portfolio Valuation</th>
                </tr>
              </thead>
              <tbody>
                {result.trades.map((trade, idx) => (
                  <tr key={idx}>
                    <td>{trade.date}</td>
                    <td>
                      <span style={{
                        fontWeight: 700,
                        padding: "4px 8px",
                        borderRadius: "4px",
                        fontSize: "0.75rem",
                        background: trade.type === "BUY" ? "var(--color-buy-bg)" : "var(--color-sell-bg)",
                        color: trade.type === "BUY" ? "var(--color-buy)" : "var(--color-sell)"
                      }}>
                        {trade.type}
                      </span>
                    </td>
                    <td>₹{trade.price.toLocaleString("en-IN", { minimumFractionDigits: 2 })}</td>
                    <td>{trade.shares.toLocaleString()}</td>
                    <td>₹{trade.fee.toLocaleString("en-IN", { minimumFractionDigits: 2 })}</td>
                    <td>₹{trade.remaining_cash.toLocaleString("en-IN", { minimumFractionDigits: 2 })}</td>
                    <td style={{ fontWeight: 600 }}>₹{trade.portfolio_value.toLocaleString("en-IN", { minimumFractionDigits: 2 })}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {result && result.trades.length === 0 && (
        <div className="glass-panel" style={{ padding: "30px", textAlign: "center", color: "var(--text-secondary)" }}>
          No trades were executed during this period using the current strategy parameters.
        </div>
      )}
    </div>
  );
}
