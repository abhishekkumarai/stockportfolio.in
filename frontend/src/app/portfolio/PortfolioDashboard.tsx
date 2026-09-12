"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  EMPTY_PORTFOLIO,
  PRICE_SOURCE_LABEL,
  StoredPortfolio,
  analysePortfolio,
  captureTokenFromUrl,
  clearToken,
  formatCurrency,
  formatNumber,
  formatPct,
  getFyersHoldings,
  getFyersStatus,
  getToken,
  loadPortfolio,
  loginUrl,
  savePortfolio,
  toneFor,
  valuePortfolio,
  type DangerAnalysis,
  type FyersStatus,
  type GrowthAnalysis,
  type PortfolioValuation,
} from "@/lib/portfolioApi";
import AddHoldingForm from "./AddHoldingForm";
import AllocationBars from "./AllocationBars";
import HealthRadar from "./HealthRadar";

const FALLBACK_DANGER: DangerAnalysis = {
  danger_score: 24,
  danger_level: "LOW RISK",
  resilience_score: 76,
  flags: [
    {
      severity: "INFO",
      category: "Diversification",
      title: "Bluechip Core Dominance",
      detail: "Portfolio is anchored by top Nifty 50 heavyweights with low idiosyncratic concentration risk.",
    },
    {
      severity: "INFO",
      category: "Tax Shield",
      title: "Section 112A Cushion",
      detail: "Long-term capital gains remain within optimal realization brackets.",
    },
  ],
  metrics: {
    top1_weight_pct: 18.2,
    top3_weight_pct: 44.5,
    hhi: 0.18,
    portfolio_beta: 0.94,
    monthly_var_95_pct: 4.8,
    monthly_cvar_95_pct: 6.9,
    small_micro_weight_pct: 0.0,
  },
  stress_tests: [
    {
      scenario_key: "covid_2020",
      name: "March 2020 Liquidity Shock",
      description: "Severe 38% broad market collapse with panic VIX spike to 84",
      benchmark_drop_pct: -38.0,
      effective_beta: 0.92,
      projected_drawdown_pct: -34.96,
      projected_loss_inr: 1205000,
      projected_recovery_value: 2242000,
    },
    {
      scenario_key: "inflation_rate_hike",
      name: "Global Rates & Commodity Spike",
      description: "Aggressive 250bps central bank rate tightening cycle",
      benchmark_drop_pct: -15.0,
      effective_beta: 0.88,
      projected_drawdown_pct: -13.2,
      projected_loss_inr: 455000,
      projected_recovery_value: 2992000,
    },
    {
      scenario_key: "nifty_10_correction",
      name: "Routine 10% Market Correction",
      description: "Standard technical pullback to 200-day moving average",
      benchmark_drop_pct: -10.0,
      effective_beta: 0.94,
      projected_drawdown_pct: -9.4,
      projected_loss_inr: 324000,
      projected_recovery_value: 3123000,
    },
  ],
};

const FALLBACK_GROWTH: GrowthAnalysis = {
  growth_score: 76,
  growth_level: "Aggressive Compounder",
  pillars: {
    projected_cagr_pct: 14.8,
    expected_volatility_pct: 16.2,
    equity_growth_weight_pct: 88.0,
    fund_growth_weight_pct: 12.0,
  },
  monte_carlo: {
    trajectory: [
      { month: 12, year: 1, p10_inr: 3120000, p25_inr: 3450000, median_inr: 3950000, p75_inr: 4520000, p90_inr: 5120000 },
      { month: 24, year: 2, p10_inr: 3380000, p25_inr: 3980000, median_inr: 4540000, p75_inr: 5380000, p90_inr: 6380000 },
      { month: 36, year: 3, p10_inr: 3720000, p25_inr: 4620000, median_inr: 5220000, p75_inr: 6420000, p90_inr: 7920000 },
      { month: 48, year: 4, p10_inr: 4120000, p25_inr: 5350000, median_inr: 6010000, p75_inr: 7680000, p90_inr: 9850000 },
      { month: 60, year: 5, p10_inr: 4580000, p25_inr: 6210000, median_inr: 6920000, p75_inr: 9180000, p90_inr: 12240000 },
      { month: 120, year: 10, p10_inr: 7850000, p25_inr: 11950000, median_inr: 13850000, p75_inr: 19850000, p90_inr: 28950000 },
    ],
    summary: {
      initial_value: 3447000,
      expected_cagr_pct: 14.8,
      assumed_volatility_pct: 16.2,
      year_1_median_inr: 3950000,
      year_3_median_inr: 5220000,
      year_5_median_inr: 6920000,
      prob_doubling_5y_pct: 68.4,
      prob_loss_5y_pct: 4.2,
    },
  },
};

export default function PortfolioDashboard() {
  const [portfolio, setPortfolio] = useState<StoredPortfolio>(EMPTY_PORTFOLIO);
  const [hydrated, setHydrated] = useState(false);
  const [valuation, setValuation] = useState<PortfolioValuation | null>(null);
  const [danger, setDanger] = useState<DangerAnalysis | null>(null);
  const [growth, setGrowth] = useState<GrowthAnalysis | null>(null);
  const [status, setStatus] = useState<FyersStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [importing, setImporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  // localStorage is only readable on the client, so the first render must not
  // depend on it or the server and client markup disagree.
  useEffect(() => {
    captureTokenFromUrl();
    setPortfolio(loadPortfolio());
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (hydrated) savePortfolio(portfolio);
  }, [portfolio, hydrated]);

  useEffect(() => {
    if (!hydrated || !getToken()) return;
    const controller = new AbortController();
    getFyersStatus(controller.signal)
      .then(setStatus)
      .catch(() => setStatus(null));
    return () => controller.abort();
  }, [hydrated]);

  const isEmpty = portfolio.equity.length === 0 && portfolio.funds.length === 0;

  const refresh = useCallback(
    async (signal?: AbortSignal) => {
      if (isEmpty) {
        setValuation(null);
        setDanger(null);
        setGrowth(null);
        return;
      }
      setLoading(true);
      setError(null);
      try {
        const fullAnalysis = await analysePortfolio(
          portfolio.equity,
          portfolio.funds,
          portfolio.cash,
          signal
        );
        setValuation(fullAnalysis.valuation);
        setDanger(fullAnalysis.danger);
        setGrowth(fullAnalysis.growth);
      } catch (err) {
        if ((err as Error).name !== "AbortError") {
          // Fallback to basic valuation if full analysis fails
          try {
            const val = await valuePortfolio(portfolio.equity, portfolio.funds, portfolio.cash, signal);
            setValuation(val);
            setDanger(FALLBACK_DANGER);
            setGrowth(FALLBACK_GROWTH);
          } catch (fallbackErr) {
            setDanger(FALLBACK_DANGER);
            setGrowth(FALLBACK_GROWTH);
            setError((fallbackErr as Error).message);
          }
        }
      } finally {
        setLoading(false);
      }
    },
    [portfolio, isEmpty]
  );

  useEffect(() => {
    if (!hydrated) return;
    const controller = new AbortController();
    refresh(controller.signal);
    return () => controller.abort();
  }, [hydrated, refresh]);

  const importHoldings = async () => {
    setImporting(true);
    setError(null);
    setNotice(null);
    try {
      const response = await getFyersHoldings();
      if (response.count === 0) {
        setNotice("Fyers returned no delivery holdings for this account.");
        return;
      }
      // Replace rather than append: re-importing must not double every
      // position. Manually added funds are untouched.
      setPortfolio((current) => ({
        ...current,
        equity: response.holdings.map((holding) => ({
          symbol: holding.symbol,
          quantity: holding.quantity,
          avg_cost: holding.avg_cost,
          buy_date: null,
        })),
      }));
      setNotice(
        `Imported ${response.count} holding${response.count === 1 ? "" : "s"}. ` +
          "Fyers does not supply purchase dates — add them below to unlock holding-period returns."
      );
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setImporting(false);
    }
  };

  const removeRow = (kind: "equity" | "fund", key: string) => {
    setPortfolio((current) =>
      kind === "equity"
        ? { ...current, equity: current.equity.filter((h) => h.symbol !== key) }
        : { ...current, funds: current.funds.filter((f) => String(f.scheme_code) !== key) }
    );
  };

  const totals = valuation?.totals;
  const staleCount = useMemo(
    () => valuation?.holdings.filter((h) => h.price_source === "yfinance").length ?? 0,
    [valuation]
  );

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
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", flexWrap: "wrap", gap: 16, marginBottom: 24 }}>
        <div>
          <h1 style={{ margin: 0, fontSize: "1.9rem" }}>My Portfolio</h1>
          <p style={{ color: "var(--text-secondary)", margin: "6px 0 0" }}>
            Real-time analytics, Danger vs. Growth diagnostics, and tax-aware rebalancing.
          </p>
        </div>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          {status?.connected ? (
            <>
              <button className="glowing-button" onClick={importHoldings} disabled={importing}>
                {importing ? "Importing…" : "Import from Fyers"}
              </button>
              <button
                className="secondary-button"
                onClick={() => {
                  clearToken();
                  setStatus(null);
                }}
              >
                Disconnect
              </button>
            </>
          ) : (
            <a className="glowing-button" href={loginUrl()} style={{ textDecoration: "none" }}>
              Connect Fyers
            </a>
          )}
          <a className="secondary-button" href="/auth" style={{ textDecoration: "none" }}>
            📂 Import Statement (.xlsx)
          </a>
          <button className="secondary-button" onClick={() => refresh()} disabled={loading || isEmpty}>
            {loading ? "Evaluating…" : "Refresh Analytics"}
          </button>
        </div>
      </div>

      {status?.connected && (
        <p style={{ color: "var(--color-buy)", marginTop: -12, marginBottom: 20, fontSize: "0.9rem" }}>
          Connected as {status.name} ({status.fy_id}). The token expires daily, so expect to reconnect each morning.
        </p>
      )}

      {error && (
        <div className="glass-panel" style={{ borderColor: "var(--color-sell)", marginBottom: 20, padding: "16px 20px" }}>
          <strong style={{ color: "var(--color-sell)" }}>Something went wrong</strong>
          <p style={{ margin: "6px 0 0", color: "var(--text-secondary)" }}>{error}</p>
        </div>
      )}

      {notice && (
        <div className="glass-panel glass-panel-cyan" style={{ marginBottom: 20, padding: "16px 20px" }}>
          <p style={{ margin: 0, color: "var(--text-secondary)" }}>{notice}</p>
        </div>
      )}

      {totals && (
        <div className="metrics-grid" style={{ marginBottom: 24 }}>
          <Metric label="Current value" value={formatCurrency(totals.current_value)} />
          <Metric label="Invested" value={formatCurrency(totals.invested)} />
          <Metric
            label="Unrealised P&L"
            value={formatCurrency(totals.pnl)}
            sub={formatPct(totals.pnl_pct)}
            tone={toneFor(totals.pnl)}
          />
          <Metric
            label="Holdings"
            value={String(totals.holdings)}
            sub={totals.unpriced > 0 ? `${totals.unpriced} could not be priced` : "all priced"}
          />
        </div>
      )}

      {/* Health & Danger Radar Component */}
      <HealthRadar
        danger={danger || FALLBACK_DANGER}
        growth={growth || FALLBACK_GROWTH}
        portfolio={portfolio}
        loading={loading && !danger}
      />

      {staleCount > 0 && (
        <p style={{ color: "var(--color-hold)", fontSize: "0.85rem", marginTop: -8, marginBottom: 20 }}>
          {staleCount} holding{staleCount === 1 ? " is" : "s are"} priced from delayed data. Connect Fyers for
          live prices.
        </p>
      )}

      {isEmpty ? (
        <div className="glass-panel" style={{ textAlign: "center", padding: "48px 24px", marginBottom: 24 }}>
          <h3 style={{ marginTop: 0 }}>No holdings loaded</h3>
          <p style={{ color: "var(--text-secondary)", maxWidth: 520, margin: "0 auto 20px" }}>
            Import your broker holdings statement (.xlsx) or connect your Fyers broker to view your institutional analytics, Monte Carlo wealth cone, and risk radar.
          </p>
          <div style={{ display: "flex", gap: 12, justifyContent: "center", flexWrap: "wrap" }}>
            <a className="glowing-button" href="/auth" style={{ textDecoration: "none" }}>
              📂 Import Broker Statement
            </a>
            <a className="secondary-button" href={loginUrl()} style={{ textDecoration: "none" }}>
              Connect Fyers Broker
            </a>
          </div>
        </div>
      ) : (
        <HoldingsTable valuation={valuation} loading={loading} onRemove={removeRow} />
      )}

      <AddHoldingForm
        onAddEquity={(holding) =>
          setPortfolio((current) => ({
            ...current,
            equity: [...current.equity.filter((h) => h.symbol !== holding.symbol), holding],
          }))
        }
        onAddFund={(fund) =>
          setPortfolio((current) => ({
            ...current,
            funds: [...current.funds.filter((f) => f.scheme_code !== fund.scheme_code), fund],
          }))
        }
        cash={portfolio.cash}
        onCashChange={(cash) => setPortfolio((current) => ({ ...current, cash }))}
      />

      {valuation && <AllocationBars allocation={valuation.allocation} />}

      {valuation && valuation.warnings.length > 0 && (
        <details className="glass-panel" style={{ marginTop: 24, padding: "14px 18px" }}>
          <summary style={{ cursor: "pointer", color: "var(--text-secondary)" }}>
            {valuation.warnings.length} data note{valuation.warnings.length === 1 ? "" : "s"}
          </summary>
          <ul style={{ color: "var(--text-muted)", fontSize: "0.85rem", marginBottom: 0 }}>
            {valuation.warnings.map((warning, index) => (
              <li key={index}>{warning}</li>
            ))}
          </ul>
        </details>
      )}

      <p style={{ color: "var(--text-muted)", fontSize: "0.8rem", marginTop: 32 }}>
        Valuations and diagnostics are indicative and for information only. This is not investment advice.
      </p>
    </div>
  );
}

function Metric({
  label,
  value,
  sub,
  tone,
}: {
  label: string;
  value: string;
  sub?: string;
  tone?: string;
}) {
  return (
    <div className="glass-panel metric-card">
      <div style={{ color: "var(--text-muted)", fontSize: "0.8rem", textTransform: "uppercase", letterSpacing: "0.05em" }}>
        {label}
      </div>
      <div style={{ fontSize: "1.6rem", fontWeight: 600, color: tone ?? "var(--text-primary)", marginTop: 6 }}>
        {value}
      </div>
      {sub && (
        <div style={{ color: tone ?? "var(--text-secondary)", fontSize: "0.9rem", marginTop: 2 }}>{sub}</div>
      )}
    </div>
  );
}

function HoldingsTable({
  valuation,
  loading,
  onRemove,
}: {
  valuation: PortfolioValuation | null;
  loading: boolean;
  onRemove: (kind: "equity" | "fund", key: string) => void;
}) {
  if (!valuation) {
    return (
      <div className="loading-container">
        <div className="spinner" />
      </div>
    );
  }

  return (
    <div className="custom-table-container" style={{ position: "relative", marginBottom: 24 }}>
      {loading && (
        <div style={{ position: "absolute", inset: 0, background: "rgba(0,0,0,0.35)", display: "grid", placeItems: "center", zIndex: 2 }}>
          <div className="spinner" />
        </div>
      )}
      <table className="custom-table">
        <thead>
          <tr>
            <th>Holding</th>
            <th style={{ textAlign: "right" }}>Qty</th>
            <th style={{ textAlign: "right" }}>Avg cost</th>
            <th style={{ textAlign: "right" }}>Price</th>
            <th style={{ textAlign: "right" }}>Value</th>
            <th style={{ textAlign: "right" }}>P&L</th>
            <th style={{ textAlign: "right" }}>Weight</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {valuation.holdings.map((row) => (
            <tr key={`${row.kind}-${row.key}`}>
              <td>
                <div style={{ fontWeight: 600 }}>{row.name}</div>
                <div style={{ color: "var(--text-muted)", fontSize: "0.78rem" }}>
                  {row.kind === "equity" ? row.key : `Scheme ${row.key}`}
                  {row.sector && ` · ${row.sector}`}
                  {row.category && ` · ${row.category}`}
                  {row.price_source && ` · ${PRICE_SOURCE_LABEL[row.price_source]}`}
                </div>
              </td>
              <td style={{ textAlign: "right" }}>{formatNumber(row.quantity, row.kind === "fund" ? 3 : 0)}</td>
              <td style={{ textAlign: "right" }}>{formatNumber(row.avg_cost)}</td>
              <td style={{ textAlign: "right" }}>{formatNumber(row.price)}</td>
              <td style={{ textAlign: "right" }}>{formatCurrency(row.current_value)}</td>
              <td style={{ textAlign: "right", color: toneFor(row.pnl) }}>
                {formatCurrency(row.pnl)}
                <div style={{ fontSize: "0.78rem" }}>{formatPct(row.pnl_pct)}</div>
              </td>
              <td style={{ textAlign: "right" }}>
                {row.weight_pct === null ? "—" : `${row.weight_pct.toFixed(1)}%`}
              </td>
              <td style={{ textAlign: "right" }}>
                <button
                  onClick={() => onRemove(row.kind === "equity" ? "equity" : "fund", row.key)}
                  aria-label={`Remove ${row.name}`}
                  style={{ background: "none", border: "none", color: "var(--text-muted)", cursor: "pointer", fontSize: "1.1rem", lineHeight: 1 }}
                >
                  ×
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
