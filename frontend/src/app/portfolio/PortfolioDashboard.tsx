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
            setValuation(
              await valuePortfolio(portfolio.equity, portfolio.funds, portfolio.cash, signal)
            );
          } catch (fallbackErr) {
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
        <div className="glass-panel" style={{ borderColor: "var(--color-sell)", marginBottom: 20 }}>
          <strong style={{ color: "var(--color-sell)" }}>Something went wrong</strong>
          <p style={{ margin: "6px 0 0", color: "var(--text-secondary)" }}>{error}</p>
        </div>
      )}

      {notice && (
        <div className="glass-panel glass-panel-cyan" style={{ marginBottom: 20 }}>
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
      {!isEmpty && (
        <HealthRadar
          danger={danger}
          growth={growth}
          portfolio={portfolio}
          loading={loading && !danger}
        />
      )}

      {staleCount > 0 && (
        <p style={{ color: "var(--color-hold)", fontSize: "0.85rem", marginTop: -8, marginBottom: 20 }}>
          {staleCount} holding{staleCount === 1 ? " is" : "s are"} priced from delayed data. Connect Fyers for
          live prices.
        </p>
      )}

      {isEmpty ? (
        <div className="glass-panel" style={{ textAlign: "center", padding: "48px 24px", marginBottom: 24 }}>
          <h3 style={{ marginTop: 0 }}>No holdings yet</h3>
          <p style={{ color: "var(--text-secondary)", maxWidth: 480, margin: "0 auto 20px" }}>
            Import your equity holdings from Fyers, or add stocks and mutual funds by hand. Mutual funds
            always have to be added manually — no broker feed carries them.
          </p>
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
        <details className="glass-panel" style={{ marginTop: 24 }}>
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
