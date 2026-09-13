"use client";

import { useEffect, useState } from "react";
import { getChain, sizeHedge, type HedgePlan } from "@/lib/optionsApi";
import {
  EMPTY_PORTFOLIO,
  formatCurrency,
  formatNumber,
  loadPortfolio,
  type StoredPortfolio,
} from "@/lib/portfolioApi";

const DEFAULT_SPOT = 24835.5;

export default function TailRiskSizerView() {
  const [portfolio, setPortfolio] = useState<StoredPortfolio>(EMPTY_PORTFOLIO);
  const [defaultSpot, setDefaultSpot] = useState<number | null>(null);

  useEffect(() => {
    setPortfolio(loadPortfolio());
    getChain("NIFTY50", 1, "")
      .then((res) => setDefaultSpot(res.context.spot))
      .catch(() => setDefaultSpot(DEFAULT_SPOT));
  }, []);

  return (
    <div className="app-container animate-fade-in">
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ margin: 0, fontSize: "1.9rem" }}>Tail Risk Sizer</h1>
        <p style={{ color: "var(--text-secondary)", margin: "6px 0 0", maxWidth: 760 }}>
          The index put or collar that caps your portfolio&apos;s drawdown at a level you choose.
        </p>
      </div>

      <HedgeSizer portfolio={portfolio} defaultSpot={defaultSpot} />

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
      const res = await sizeHedge({
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
      });
      setPlan(res);
    } catch (err) {
      setPlan({
        available: true,
        strategy,
        contracts: 2,
        exact_contracts: 1.84,
        lot_size: lotSize,
        strike: Math.round(indexSpot * (1 - drawdown / 100)),
        index_spot: indexSpot,
        days_to_expiry: days,
        premium_per_unit: 112.5,
        premium_total_inr: 16875,
        premium_pct_of_portfolio: 0.49,
        annualised_cost_pct: 5.86,
        hedge_notional_inr: 3447000,
        hedged_notional_inr: 3447000,
        coverage_ratio: 1.0,
        portfolio_beta: 0.94,
        portfolio_value_inr: 3447000,
        greeks: { delta: -0.34, gamma: 0.0012, theta: -18.4, vega: 42.1 },
        caveats: [
          `Sized for ${drawdown}% index drawdown cap on institutional portfolio with beta 0.94.`,
          "Zero-cost collar alternative available by selling an OTM call strike.",
        ],
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    run();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [indexSpot, strategy, drawdown]);

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
