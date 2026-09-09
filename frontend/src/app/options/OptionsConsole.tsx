"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  BarElement,
  CategoryScale,
  Chart as ChartJS,
  Filler,
  Legend,
  LineElement,
  LinearScale,
  PointElement,
  Tooltip,
} from "chart.js";
import { Bar } from "react-chartjs-2";
import {
  BUILDUP_TONE,
  getChain,
  getChainAnalysis,
  sizeHedge,
  type ChainAnalysis,
  type ChainResponse,
  type HedgePlan,
} from "@/lib/optionsApi";
import {
  EMPTY_PORTFOLIO,
  formatCurrency,
  formatNumber,
  getToken,
  loadPortfolio,
  loginUrl,
  type StoredPortfolio,
} from "@/lib/portfolioApi";

ChartJS.register(CategoryScale, LinearScale, BarElement, PointElement, LineElement, Tooltip, Legend, Filler);

const INDEX_SYMBOLS = ["NIFTY50", "NIFTYBANK", "RELIANCE", "HDFCBANK", "TCS", "INFY"];

export default function OptionsConsole() {
  const [symbol, setSymbol] = useState("NIFTY50");
  const [strikeCount, setStrikeCount] = useState(15);
  const [expiry, setExpiry] = useState("");
  const [chain, setChain] = useState<ChainResponse | null>(null);
  const [analysis, setAnalysis] = useState<ChainAnalysis | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [connected, setConnected] = useState(false);
  const [portfolio, setPortfolio] = useState<StoredPortfolio>(EMPTY_PORTFOLIO);

  useEffect(() => {
    setConnected(Boolean(getToken()));
    setPortfolio(loadPortfolio());
  }, []);

  const load = useCallback(
    async (nextExpiry: string) => {
      setLoading(true);
      setError(null);
      try {
        const [chainResult, analysisResult] = await Promise.all([
          getChain(symbol, strikeCount, nextExpiry),
          getChainAnalysis(symbol, strikeCount, nextExpiry),
        ]);
        setChain(chainResult);
        setAnalysis(analysisResult);
        if (!nextExpiry && chainResult.context.expiries?.length) {
          setExpiry(chainResult.context.expiries[0].expiry);
        }
      } catch (err) {
        setError((err as Error).message);
        setChain(null);
        setAnalysis(null);
      } finally {
        setLoading(false);
      }
    },
    [symbol, strikeCount]
  );

  const spot = chain?.context.spot ?? null;

  const oiByStrike = useMemo(() => {
    if (!chain) return null;
    const strikes = Array.from(new Set(chain.rows.map((row) => row.strike))).sort((a, b) => a - b);
    const callOi = strikes.map(
      (strike) => chain.rows.find((r) => r.strike === strike && r.option_type === "CE")?.oi ?? 0
    );
    const putOi = strikes.map(
      (strike) => chain.rows.find((r) => r.strike === strike && r.option_type === "PE")?.oi ?? 0
    );
    return { strikes, callOi, putOi };
  }, [chain]);

  if (!connected) {
    return (
      <div className="app-container animate-fade-in">
        <Heading />
        <div className="glass-panel" style={{ textAlign: "center", padding: "48px 24px" }}>
          <h3 style={{ marginTop: 0 }}>Connect Fyers to read the chain</h3>
          <p style={{ color: "var(--text-secondary)", maxWidth: 560, margin: "0 auto 20px" }}>
            Option chains come from the authenticated broker endpoint, not a public scrape, so this
            page needs a live Fyers token. It expires daily.
          </p>
          <a className="glowing-button" href={loginUrl()} style={{ textDecoration: "none" }}>
            Connect Fyers
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="app-container animate-fade-in">
      <Heading />

      <div className="glass-panel" style={{ marginBottom: 20, display: "flex", gap: 14, flexWrap: "wrap", alignItems: "flex-end" }}>
        <label style={{ flex: "1 1 180px" }}>
          <FieldLabel>Underlying</FieldLabel>
          <input
            list="options-symbols"
            value={symbol}
            onChange={(event) => setSymbol(event.target.value.toUpperCase())}
            style={inputStyle}
          />
          <datalist id="options-symbols">
            {INDEX_SYMBOLS.map((entry) => (
              <option key={entry} value={entry} />
            ))}
          </datalist>
        </label>

        <label style={{ flex: "1 1 160px" }}>
          <FieldLabel>Expiry</FieldLabel>
          <select
            value={expiry}
            onChange={(event) => {
              setExpiry(event.target.value);
              load(event.target.value);
            }}
            style={inputStyle}
          >
            <option value="">Nearest</option>
            {(chain?.context.expiries ?? []).map((entry) => (
              <option key={entry.expiry} value={entry.expiry}>
                {entry.date}
              </option>
            ))}
          </select>
        </label>

        <label style={{ flex: "0 1 150px" }}>
          <FieldLabel>Strikes per side</FieldLabel>
          <input
            type="number"
            min={1}
            max={50}
            value={strikeCount}
            onChange={(event) => setStrikeCount(Number(event.target.value))}
            style={inputStyle}
          />
        </label>

        <button className="glowing-button" onClick={() => load(expiry)} disabled={loading}>
          {loading ? "Reading chain…" : "Load chain"}
        </button>
      </div>

      {error && (
        <div className="glass-panel" style={{ borderColor: "var(--color-sell)", marginBottom: 20 }}>
          <strong style={{ color: "var(--color-sell)" }}>Chain unavailable</strong>
          <p style={{ margin: "6px 0 0", color: "var(--text-secondary)" }}>{error}</p>
        </div>
      )}

      {analysis?.available && (
        <>
          <div className="metrics-grid" style={{ marginBottom: 20 }}>
            <Stat label="Spot" value={formatNumber(spot)} />
            <Stat
              label="OI PCR"
              value={analysis.pcr.oi_pcr === null ? "—" : analysis.pcr.oi_pcr.toFixed(2)}
              sub={analysis.pcr.volume_pcr === null ? undefined : `Volume PCR ${analysis.pcr.volume_pcr.toFixed(2)}`}
            />
            <Stat label="Max pain" value={formatNumber(analysis.max_pain.max_pain_strike, 0)} />
            <Stat
              label="ATM IV"
              value={analysis.iv.available ? `${analysis.iv.atm_iv_pct?.toFixed(1)}%` : "—"}
              sub={
                analysis.iv.available && analysis.iv.skew_pct !== null && analysis.iv.skew_pct !== undefined
                  ? `Put-call skew ${analysis.iv.skew_pct.toFixed(1)} pts`
                  : undefined
              }
            />
          </div>

          <div className="glass-panel" style={{ marginBottom: 20 }}>
            <p style={{ margin: 0, color: "var(--text-secondary)" }}>{analysis.pcr.interpretation}</p>
            {analysis.iv.available && analysis.iv.interpretation && (
              <p style={{ margin: "8px 0 0", color: "var(--text-secondary)" }}>{analysis.iv.interpretation}</p>
            )}
            <p style={{ margin: "8px 0 0", color: "var(--text-muted)", fontSize: "0.82rem" }}>
              {analysis.max_pain.note}
            </p>
          </div>

          {oiByStrike && (
            <div className="glass-panel" style={{ marginBottom: 20 }}>
              <h3 style={{ marginTop: 0 }}>Open interest by strike</h3>
              <div style={{ height: 300 }}>
                <Bar
                  data={{
                    labels: oiByStrike.strikes,
                    datasets: [
                      {
                        label: "Call OI",
                        data: oiByStrike.callOi,
                        backgroundColor: "rgba(239, 68, 68, 0.55)",
                      },
                      {
                        label: "Put OI",
                        data: oiByStrike.putOi,
                        backgroundColor: "rgba(16, 185, 129, 0.55)",
                      },
                    ],
                  }}
                  options={{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { labels: { color: "#475569", font: { family: "Inter", size: 11 } } } },
                    scales: {
                      x: { ticks: { color: "#64748b", font: { size: 10 } }, grid: { display: false } },
                      y: { ticks: { color: "#64748b", font: { family: "JetBrains Mono", size: 10 } }, grid: { color: "#f1f5f9" } },
                    },
                  }}
                />
              </div>
              <div style={{ display: "flex", gap: 32, flexWrap: "wrap", marginTop: 14 }}>
                <Walls title="Resistance (call OI)" rows={analysis.oi_walls.resistance} tone="var(--color-sell)" />
                <Walls title="Support (put OI)" rows={analysis.oi_walls.support} tone="var(--color-buy)" />
              </div>
            </div>
          )}

          <div className="glass-panel" style={{ marginBottom: 20 }}>
            <h3 style={{ marginTop: 0 }}>OI build-up</h3>
            <p style={{ color: "var(--text-muted)", fontSize: "0.82rem", marginTop: 0 }}>
              Open interest against price: fresh positions and unwinding read as opposites even when
              the OI number itself looks the same.
            </p>
            <div className="custom-table-container" style={{ maxHeight: 420, overflowY: "auto" }}>
              <table className="custom-table">
                <thead>
                  <tr>
                    <th>Strike</th>
                    <th>Type</th>
                    <th style={{ textAlign: "right" }}>LTP</th>
                    <th style={{ textAlign: "right" }}>OI</th>
                    <th style={{ textAlign: "right" }}>ΔOI</th>
                    <th style={{ textAlign: "right" }}>ΔPrice</th>
                    <th>Read</th>
                  </tr>
                </thead>
                <tbody>
                  {analysis.buildup.map((row) => (
                    <tr key={`${row.strike}-${row.option_type}`}>
                      <td>{formatNumber(row.strike, 0)}</td>
                      <td>{row.option_type}</td>
                      <td style={{ textAlign: "right" }}>{formatNumber(row.ltp)}</td>
                      <td style={{ textAlign: "right" }}>{formatNumber(row.oi, 0)}</td>
                      <td style={{ textAlign: "right" }}>{formatNumber(row.oi_change, 0)}</td>
                      <td style={{ textAlign: "right" }}>{formatNumber(row.price_change)}</td>
                      <td style={{ color: BUILDUP_TONE[row.buildup] ?? "var(--text-secondary)" }}>
                        {row.buildup_label}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {analysis && !analysis.available && (
        <div className="glass-panel" style={{ marginBottom: 20 }}>
          <strong>No chain analysis</strong>
          <p style={{ margin: "6px 0 0", color: "var(--text-secondary)" }}>{analysis.reason}</p>
        </div>
      )}

      <HedgeSizer portfolio={portfolio} defaultSpot={spot} />

      <p style={{ color: "var(--text-muted)", fontSize: "0.8rem", marginTop: 28 }}>
        Everything on this page is a calculation. This system has no order API and cannot place a
        trade.
      </p>
    </div>
  );
}

function HedgeSizer({
  portfolio,
  defaultSpot,
}: {
  portfolio: StoredPortfolio;
  defaultSpot: number | null;
}) {
  const [strategy, setStrategy] = useState<"protective_put" | "collar">("protective_put");
  const [indexSpot, setIndexSpot] = useState(24000);
  const [drawdown, setDrawdown] = useState(10);
  const [upsideCap, setUpsideCap] = useState(10);
  const [days, setDays] = useState(30);
  const [volatility, setVolatility] = useState(15);
  const [lotSize, setLotSize] = useState(75);
  const [usePortfolio, setUsePortfolio] = useState(true);
  const [manualValue, setManualValue] = useState(1000000);
  const [manualBeta, setManualBeta] = useState(1.0);
  const [plan, setPlan] = useState<HedgePlan | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (defaultSpot) setIndexSpot(Math.round(defaultSpot));
  }, [defaultSpot]);

  const hasHoldings = portfolio.equity.length > 0 || portfolio.funds.length > 0;

  const run = async () => {
    setLoading(true);
    setError(null);
    try {
      setPlan(
        await sizeHedge({
          portfolio:
            usePortfolio && hasHoldings
              ? { equity: portfolio.equity, funds: portfolio.funds, cash: portfolio.cash }
              : undefined,
          portfolio_value: usePortfolio && hasHoldings ? undefined : manualValue,
          portfolio_beta: usePortfolio && hasHoldings ? undefined : manualBeta,
          index_spot: indexSpot,
          strategy,
          target_max_drawdown: drawdown / 100,
          upside_cap: upsideCap / 100,
          lot_size: lotSize,
          days_to_expiry: days,
          volatility: volatility / 100,
        })
      );
    } catch (err) {
      setError((err as Error).message);
      setPlan(null);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="glass-panel glass-panel-cyan" style={{ marginBottom: 20 }}>
      <h3 style={{ marginTop: 0 }}>Tail-risk hedge sizer</h3>
      <p style={{ color: "var(--text-secondary)", marginTop: 0 }}>
        How many index puts cap your drawdown at a chosen level, and what standing protection costs
        annualised. Sizing is beta-weighted notional — a book with beta 1.3 behaves like 1.3× its
        value in index exposure.
      </p>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 14 }}>
        <label>
          <FieldLabel>Structure</FieldLabel>
          <select
            value={strategy}
            onChange={(event) => setStrategy(event.target.value as "protective_put" | "collar")}
            style={inputStyle}
          >
            <option value="protective_put">Protective put</option>
            <option value="collar">Collar (put funded by a short call)</option>
          </select>
        </label>
        <label>
          <FieldLabel>Index spot</FieldLabel>
          <input type="number" value={indexSpot} onChange={(e) => setIndexSpot(Number(e.target.value))} style={inputStyle} />
        </label>
        <label>
          <FieldLabel>Cap drawdown at %</FieldLabel>
          <input type="number" value={drawdown} onChange={(e) => setDrawdown(Number(e.target.value))} style={inputStyle} />
        </label>
        {strategy === "collar" && (
          <label>
            <FieldLabel>Give up upside above %</FieldLabel>
            <input type="number" value={upsideCap} onChange={(e) => setUpsideCap(Number(e.target.value))} style={inputStyle} />
          </label>
        )}
        <label>
          <FieldLabel>Days to expiry</FieldLabel>
          <input type="number" value={days} onChange={(e) => setDays(Number(e.target.value))} style={inputStyle} />
        </label>
        <label>
          <FieldLabel>Implied volatility %</FieldLabel>
          <input type="number" value={volatility} onChange={(e) => setVolatility(Number(e.target.value))} style={inputStyle} />
        </label>
        <label>
          <FieldLabel>Lot size</FieldLabel>
          <input type="number" value={lotSize} onChange={(e) => setLotSize(Number(e.target.value))} style={inputStyle} />
        </label>
      </div>

      <div style={{ display: "flex", gap: 16, flexWrap: "wrap", marginTop: 14, alignItems: "flex-end" }}>
        <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: "0.85rem" }}>
          <input
            type="checkbox"
            checked={usePortfolio && hasHoldings}
            disabled={!hasHoldings}
            onChange={(event) => setUsePortfolio(event.target.checked)}
          />
          Use my saved portfolio{!hasHoldings && " (none saved yet)"}
        </label>
        {(!usePortfolio || !hasHoldings) && (
          <>
            <label>
              <FieldLabel>Portfolio value ₹</FieldLabel>
              <input type="number" value={manualValue} onChange={(e) => setManualValue(Number(e.target.value))} style={inputStyle} />
            </label>
            <label>
              <FieldLabel>Portfolio beta</FieldLabel>
              <input type="number" step="0.05" value={manualBeta} onChange={(e) => setManualBeta(Number(e.target.value))} style={inputStyle} />
            </label>
          </>
        )}
        <button className="glowing-button" onClick={run} disabled={loading}>
          {loading ? "Sizing…" : "Size the hedge"}
        </button>
      </div>

      {error && <p style={{ color: "var(--color-sell)", marginTop: 12 }}>{error}</p>}

      {plan?.available && (
        <div style={{ marginTop: 18 }}>
          <div className="metrics-grid">
            <Stat label="Contracts" value={`${plan.contracts} × ${plan.lot_size}`} />
            <Stat
              label={plan.strategy === "collar" ? "Put / call strike" : "Put strike"}
              value={
                plan.strategy === "collar"
                  ? `${formatNumber(plan.put_strike ?? null, 0)} / ${formatNumber(plan.call_strike ?? null, 0)}`
                  : formatNumber(plan.strike, 0)
              }
            />
            <Stat
              label={plan.strategy === "collar" ? "Net cost" : "Premium"}
              value={formatCurrency(
                plan.strategy === "collar" ? plan.net_cost_inr ?? 0 : plan.premium_total_inr
              )}
              sub={
                plan.strategy === "collar"
                  ? plan.zero_cost
                    ? "Effectively zero-cost"
                    : `${plan.net_cost_pct_of_portfolio?.toFixed(2)}% of portfolio`
                  : `${plan.annualised_cost_pct}% a year if rolled`
              }
            />
            <Stat label="Portfolio beta used" value={String(plan.portfolio_beta)} />
          </div>
          <ul style={{ color: "var(--text-muted)", fontSize: "0.82rem", marginTop: 14, paddingLeft: 18 }}>
            {plan.caveats.map((caveat, index) => (
              <li key={index} style={{ marginBottom: 4 }}>
                {caveat}
              </li>
            ))}
          </ul>
        </div>
      )}

      {plan && !plan.available && (
        <p style={{ color: "var(--color-hold)", marginTop: 12 }}>{plan.reason}</p>
      )}
    </div>
  );
}

function Walls({
  title,
  rows,
  tone,
}: {
  title: string;
  rows: Array<{ strike: number; oi: number; oi_change: number }>;
  tone: string;
}) {
  return (
    <div>
      <div style={{ color: tone, fontWeight: 600, fontSize: "0.85rem", marginBottom: 6 }}>{title}</div>
      {rows.map((row) => (
        <div key={row.strike} style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>
          {formatNumber(row.strike, 0)} · {formatNumber(row.oi, 0)} OI
          <span style={{ color: row.oi_change >= 0 ? "var(--color-buy)" : "var(--color-sell)" }}>
            {" "}
            ({row.oi_change >= 0 ? "+" : ""}
            {formatNumber(row.oi_change, 0)})
          </span>
        </div>
      ))}
      {rows.length === 0 && <div style={{ color: "var(--text-muted)", fontSize: "0.85rem" }}>None</div>}
    </div>
  );
}

function Heading() {
  return (
    <div style={{ marginBottom: 24 }}>
      <h1 style={{ margin: 0, fontSize: "1.9rem" }}>Option Chain & Hedging Radar</h1>
      <p style={{ color: "var(--text-secondary)", margin: "6px 0 0", maxWidth: 760 }}>
        Positioning read from the live chain — put-call ratio, max pain, OI walls and build-up —
        and the index put or collar that caps your portfolio&apos;s drawdown at a level you choose.
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
      {sub && <div style={{ color: "var(--text-secondary)", fontSize: "0.82rem", marginTop: 2 }}>{sub}</div>}
    </div>
  );
}
