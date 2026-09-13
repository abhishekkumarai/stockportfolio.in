"use client";

import {
  PRICE_SOURCE_LABEL,
  clearToken,
  formatCurrency,
  formatNumber,
  formatPct,
  loginUrl,
  toneFor,
  type PortfolioValuation,
} from "@/lib/portfolioApi";
import { usePortfolioContext } from "../PortfolioContext";
import AddHoldingForm from "../AddHoldingForm";
import AllocationBars from "../AllocationBars";

export default function HoldingsView() {
  const {
    portfolio,
    setPortfolio,
    valuation,
    status,
    setStatus,
    loading,
    importing,
    uploadingStatement,
    error,
    notice,
    isEmpty,
    staleCount,
    refresh,
    importHoldings,
    handleStatementFile,
    removeRow,
    statementFileInputRef,
  } = usePortfolioContext();

  const totals = valuation?.totals;

  return (
    <div>
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
          <input
            ref={statementFileInputRef}
            type="file"
            accept=".xlsx"
            style={{ display: "none" }}
            onChange={(e) => {
              const file = e.target.files?.[0];
              e.target.value = "";
              if (file) handleStatementFile(file);
            }}
          />
          <button
            className="secondary-button"
            onClick={() => statementFileInputRef.current?.click()}
            disabled={uploadingStatement}
          >
            {uploadingStatement ? "Importing…" : "📂 Import Statement (.xlsx)"}
          </button>
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
            <button
              className="glowing-button"
              onClick={() => statementFileInputRef.current?.click()}
              disabled={uploadingStatement}
            >
              {uploadingStatement ? "Importing…" : "📂 Import Broker Statement"}
            </button>
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
