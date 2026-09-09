"use client";

import { useCallback, useEffect, useState } from "react";
import {
  createAccount,
  createPaperAccount,
  listPaperAccounts,
  paperDetail,
  paperOrders,
  paperSignals,
  placeOrder,
  runStrategy,
  type Divergence,
  type PaperAccountSummary,
  type PaperOrder,
  type PaperSignal,
  type PaperValuation,
} from "@/lib/paperApi";
import { clearAccountKey, getAccountKey, setAccountKey } from "@/lib/http";
import { formatCurrency, formatNumber, formatPct, toneFor } from "@/lib/portfolioApi";
import { listStrategies, type StrategySpec } from "@/lib/engineApi";

// The whole point of this page is that the audit trail survives a reload, so
// everything here is server state behind an account key — nothing is kept in
// component state that a refresh would invent differently.

export default function PaperConsole() {
  const [accountKey, setKey] = useState<string | null>(null);
  const [hydrated, setHydrated] = useState(false);
  const [accounts, setAccounts] = useState<PaperAccountSummary[]>([]);
  const [banner, setBanner] = useState<string>("");
  const [selected, setSelected] = useState<number | null>(null);
  const [valuation, setValuation] = useState<PaperValuation | null>(null);
  const [divergence, setDivergence] = useState<Divergence | null>(null);
  const [orders, setOrders] = useState<PaperOrder[]>([]);
  const [signals, setSignals] = useState<PaperSignal[]>([]);
  const [strategies, setStrategies] = useState<StrategySpec[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => {
    setKey(getAccountKey());
    setHydrated(true);
    const controller = new AbortController();
    listStrategies(controller.signal)
      .then((response) => setStrategies(response.strategies))
      .catch(() => setStrategies([]));
    return () => controller.abort();
  }, []);

  const refreshAccounts = useCallback(async () => {
    try {
      const response = await listPaperAccounts();
      setAccounts(response.accounts);
      setBanner(response.banner);
      if (response.accounts.length && selected === null) setSelected(response.accounts[0].id);
    } catch (err) {
      setError((err as Error).message);
    }
  }, [selected]);

  useEffect(() => {
    if (!hydrated || !accountKey) return;
    refreshAccounts();
  }, [hydrated, accountKey, refreshAccounts]);

  const loadDetail = useCallback(async (id: number) => {
    setError(null);
    try {
      const [detail, orderLog, signalLog] = await Promise.all([
        paperDetail(id),
        paperOrders(id),
        paperSignals(id),
      ]);
      setValuation(detail.valuation);
      setDivergence(detail.divergence);
      setOrders(orderLog.orders);
      setSignals(signalLog.signals);
    } catch (err) {
      setError((err as Error).message);
    }
  }, []);

  useEffect(() => {
    if (selected !== null) loadDetail(selected);
  }, [selected, loadDetail]);

  const createIdentity = async () => {
    setBusy("identity");
    setError(null);
    try {
      const response = await createAccount("stockportfolio.in user");
      setAccountKey(response.access_key);
      setKey(response.access_key);
      setNotice(response.note);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(null);
    }
  };

  if (!hydrated) {
    return (
      <div className="app-container">
        <div className="loading-container">
          <div className="spinner" />
        </div>
      </div>
    );
  }

  if (!accountKey) {
    return (
      <div className="app-container animate-fade-in">
        <Heading />
        <div className="glass-panel" style={{ padding: "40px 24px", maxWidth: 640 }}>
          <h3 style={{ marginTop: 0 }}>This page needs a stored account</h3>
          <p style={{ color: "var(--text-secondary)" }}>
            A paper ledger is only useful if it survives a reload, so unlike the rest of the app
            this one is not stateless. Creating an account gives you an opaque key — no password,
            no email verification. It is stored in this browser and sent as a header.
          </p>
          <p style={{ color: "var(--text-muted)", fontSize: "0.85rem" }}>
            Only the key&apos;s hash is kept server-side, so it cannot be recovered. If the backend
            has no <code>DATABASE_URL</code> configured, this will answer 503 and say so.
          </p>
          <button className="glowing-button" onClick={createIdentity} disabled={busy !== null}>
            {busy === "identity" ? "Creating…" : "Create an account key"}
          </button>
          {error && <p style={{ color: "var(--color-sell)", marginTop: 12 }}>{error}</p>}
        </div>
      </div>
    );
  }

  return (
    <div className="app-container animate-fade-in">
      <Heading />

      {banner && (
        <div className="glass-panel glass-panel-cyan" style={{ marginBottom: 20 }}>
          <strong style={{ color: "var(--accent-cyan)" }}>{banner}</strong>
        </div>
      )}

      {notice && (
        <div className="glass-panel" style={{ marginBottom: 20 }}>
          <p style={{ margin: 0, color: "var(--text-secondary)" }}>{notice}</p>
          <code style={{ display: "block", marginTop: 8, wordBreak: "break-all", color: "var(--accent-cyan)" }}>
            {accountKey}
          </code>
        </div>
      )}

      {error && (
        <div className="glass-panel" style={{ borderColor: "var(--color-sell)", marginBottom: 20 }}>
          <strong style={{ color: "var(--color-sell)" }}>Something went wrong</strong>
          <p style={{ margin: "6px 0 0", color: "var(--text-secondary)" }}>{error}</p>
        </div>
      )}

      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginBottom: 20, alignItems: "center" }}>
        {accounts.map((account) => (
          <button
            key={account.id}
            className={selected === account.id ? "glowing-button" : "secondary-button"}
            onClick={() => setSelected(account.id)}
          >
            {account.name}
          </button>
        ))}
        <button
          className="secondary-button"
          onClick={() => {
            clearAccountKey();
            setKey(null);
            setAccounts([]);
            setSelected(null);
          }}
          style={{ marginLeft: "auto" }}
        >
          Forget key on this device
        </button>
      </div>

      <NewLedger
        strategies={strategies}
        onCreated={async (id) => {
          await refreshAccounts();
          setSelected(id);
        }}
        onError={setError}
      />

      {valuation && (
        <>
          <div className="metrics-grid" style={{ margin: "20px 0" }}>
            <Stat label="Equity" value={formatCurrency(valuation.equity)} />
            <Stat
              label="Total return"
              value={formatCurrency(valuation.total_return_inr)}
              sub={formatPct(valuation.total_return_pct)}
              tone={toneFor(valuation.total_return_inr)}
            />
            <Stat label="Cash" value={formatCurrency(valuation.cash)} />
            <Stat
              label="Orders"
              value={String(valuation.order_count)}
              sub={`${formatCurrency(valuation.total_fees_inr)} in fees`}
            />
          </div>

          {valuation.warnings.length > 0 && (
            <div className="glass-panel" style={{ marginBottom: 20, borderColor: "var(--color-hold)" }}>
              <ul style={{ color: "var(--color-hold)", fontSize: "0.85rem", paddingLeft: 18, margin: 0 }}>
                {valuation.warnings.map((warning, index) => (
                  <li key={index}>{warning}</li>
                ))}
              </ul>
            </div>
          )}

          {divergence && <DivergencePanel divergence={divergence} />}

          <div className="glass-panel" style={{ marginBottom: 20 }}>
            <h3 style={{ marginTop: 0 }}>Open positions</h3>
            <div className="custom-table-container">
              <table className="custom-table">
                <thead>
                  <tr>
                    <th>Symbol</th>
                    <th style={{ textAlign: "right" }}>Qty</th>
                    <th style={{ textAlign: "right" }}>Avg cost</th>
                    <th style={{ textAlign: "right" }}>Price</th>
                    <th style={{ textAlign: "right" }}>Value</th>
                    <th style={{ textAlign: "right" }}>Unrealised</th>
                  </tr>
                </thead>
                <tbody>
                  {valuation.open_positions.map((position) => (
                    <tr key={position.symbol}>
                      <td style={{ fontWeight: 600 }}>{position.symbol}</td>
                      <td style={{ textAlign: "right" }}>{formatNumber(position.quantity, 0)}</td>
                      <td style={{ textAlign: "right" }}>{formatNumber(position.avg_cost)}</td>
                      <td style={{ textAlign: "right" }}>{formatNumber(position.price)}</td>
                      <td style={{ textAlign: "right" }}>{formatCurrency(position.value)}</td>
                      <td style={{ textAlign: "right", color: toneFor(position.unrealised_pnl) }}>
                        {formatCurrency(position.unrealised_pnl)}
                        <div style={{ fontSize: "0.78rem" }}>{formatPct(position.unrealised_pnl_pct)}</div>
                      </td>
                    </tr>
                  ))}
                  {valuation.open_positions.length === 0 && (
                    <tr>
                      <td colSpan={6} style={{ textAlign: "center", color: "var(--text-muted)" }}>
                        Flat. No open simulated positions.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {selected !== null && (
            <Actions
              paperId={selected}
              strategyBound={Boolean(valuation.strategy)}
              onDone={(message) => {
                setNotice(message);
                loadDetail(selected);
              }}
              onError={setError}
            />
          )}

          <div className="glass-panel" style={{ marginBottom: 20 }}>
            <h3 style={{ marginTop: 0 }}>Order log</h3>
            <div className="custom-table-container" style={{ maxHeight: 360, overflowY: "auto" }}>
              <table className="custom-table">
                <thead>
                  <tr>
                    <th>Filled</th>
                    <th>Symbol</th>
                    <th>Side</th>
                    <th style={{ textAlign: "right" }}>Qty</th>
                    <th style={{ textAlign: "right" }}>Price</th>
                    <th style={{ textAlign: "right" }}>Realised</th>
                    <th>Why</th>
                  </tr>
                </thead>
                <tbody>
                  {orders.map((order) => (
                    <tr key={order.id}>
                      <td style={{ color: "var(--text-muted)" }}>{order.filled_at?.slice(0, 10) ?? "—"}</td>
                      <td>{order.symbol}</td>
                      <td style={{ color: order.side === "BUY" ? "var(--color-buy)" : "var(--color-sell)" }}>
                        {order.side}
                      </td>
                      <td style={{ textAlign: "right" }}>{formatNumber(order.quantity, 0)}</td>
                      <td style={{ textAlign: "right" }}>{formatNumber(order.price)}</td>
                      <td style={{ textAlign: "right", color: toneFor(order.realised_pnl) }}>
                        {formatCurrency(order.realised_pnl)}
                      </td>
                      <td style={{ color: "var(--text-secondary)", fontSize: "0.82rem" }}>{order.reason}</td>
                    </tr>
                  ))}
                  {orders.length === 0 && (
                    <tr>
                      <td colSpan={7} style={{ textAlign: "center", color: "var(--text-muted)" }}>
                        No fills yet.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          <div className="glass-panel" style={{ marginBottom: 20 }}>
            <h3 style={{ marginTop: 0 }}>Signal log</h3>
            <p style={{ color: "var(--text-muted)", fontSize: "0.82rem", marginTop: 0 }}>
              The skipped signals matter as much as the taken ones. Without them this table measures
              execution rather than the strategy.
            </p>
            <div className="custom-table-container" style={{ maxHeight: 360, overflowY: "auto" }}>
              <table className="custom-table">
                <thead>
                  <tr>
                    <th>Generated</th>
                    <th>Symbol</th>
                    <th>Action</th>
                    <th style={{ textAlign: "right" }}>Score</th>
                    <th>Executed</th>
                    <th>Skip reason</th>
                  </tr>
                </thead>
                <tbody>
                  {signals.map((signal) => (
                    <tr key={signal.id}>
                      <td style={{ color: "var(--text-muted)" }}>{signal.generated_at?.slice(0, 10) ?? "—"}</td>
                      <td>{signal.symbol}</td>
                      <td>{signal.action}</td>
                      <td style={{ textAlign: "right" }}>{formatNumber(signal.score, 1)}</td>
                      <td style={{ color: signal.executed ? "var(--color-buy)" : "var(--text-muted)" }}>
                        {signal.executed ? "Yes" : "No"}
                      </td>
                      <td style={{ color: "var(--text-secondary)", fontSize: "0.82rem" }}>
                        {signal.skip_reason ?? "—"}
                      </td>
                    </tr>
                  ))}
                  {signals.length === 0 && (
                    <tr>
                      <td colSpan={6} style={{ textAlign: "center", color: "var(--text-muted)" }}>
                        No signals generated yet.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function NewLedger({
  strategies,
  onCreated,
  onError,
}: {
  strategies: StrategySpec[];
  onCreated: (id: number) => void;
  onError: (message: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("Paper book 1");
  const [capital, setCapital] = useState(100000);
  const [strategy, setStrategy] = useState("");
  const [cagr, setCagr] = useState(0);
  const [drawdown, setDrawdown] = useState(0);
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setBusy(true);
    try {
      const response = await createPaperAccount({
        name,
        initial_capital: capital,
        strategy: strategy || null,
        backtest_reference:
          cagr || drawdown ? { cagr_pct: cagr, max_drawdown_pct: drawdown } : {},
      });
      setOpen(false);
      onCreated(response.id);
    } catch (err) {
      onError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  if (!open) {
    return (
      <button className="secondary-button" onClick={() => setOpen(true)}>
        + New paper ledger
      </button>
    );
  }

  return (
    <div className="glass-panel" style={{ marginBottom: 20 }}>
      <h3 style={{ marginTop: 0 }}>New paper ledger</h3>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 14 }}>
        <label>
          <FieldLabel>Name</FieldLabel>
          <input value={name} onChange={(event) => setName(event.target.value)} style={inputStyle} />
        </label>
        <label>
          <FieldLabel>Starting capital ₹</FieldLabel>
          <input
            type="number"
            value={capital}
            onChange={(event) => setCapital(Number(event.target.value))}
            style={inputStyle}
          />
        </label>
        <label>
          <FieldLabel>Bound strategy</FieldLabel>
          <select value={strategy} onChange={(event) => setStrategy(event.target.value)} style={inputStyle}>
            <option value="">None — manual orders only</option>
            {strategies.map((entry) => (
              <option key={entry.name} value={entry.name}>
                {entry.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          <FieldLabel>Backtest CAGR %</FieldLabel>
          <input
            type="number"
            value={cagr}
            onChange={(event) => setCagr(Number(event.target.value))}
            style={inputStyle}
          />
        </label>
        <label>
          <FieldLabel>Backtest max drawdown %</FieldLabel>
          <input
            type="number"
            value={drawdown}
            onChange={(event) => setDrawdown(Number(event.target.value))}
            style={inputStyle}
          />
        </label>
      </div>
      <p style={{ color: "var(--text-muted)", fontSize: "0.82rem" }}>
        The backtest figures are what this deployment gets judged against later. Leave them at zero
        if this ledger is not tracking a specific backtested strategy.
      </p>
      <div style={{ display: "flex", gap: 10 }}>
        <button className="glowing-button" onClick={submit} disabled={busy}>
          {busy ? "Creating…" : "Create ledger"}
        </button>
        <button className="secondary-button" onClick={() => setOpen(false)}>
          Cancel
        </button>
      </div>
    </div>
  );
}

function Actions({
  paperId,
  strategyBound,
  onDone,
  onError,
}: {
  paperId: number;
  strategyBound: boolean;
  onDone: (message: string) => void;
  onError: (message: string) => void;
}) {
  const [symbol, setSymbol] = useState("RELIANCE");
  const [side, setSide] = useState<"BUY" | "SELL">("BUY");
  const [quantity, setQuantity] = useState(10);
  const [price, setPrice] = useState(1000);
  const [watchlist, setWatchlist] = useState("RELIANCE, HDFCBANK, INFY");
  const [busy, setBusy] = useState<string | null>(null);

  const fill = async () => {
    setBusy("order");
    try {
      await placeOrder(paperId, { symbol, side, quantity, price, reason: "Manual paper order" });
      onDone(`Recorded a simulated ${side} of ${quantity} ${symbol}.`);
    } catch (err) {
      onError((err as Error).message);
    } finally {
      setBusy(null);
    }
  };

  const evaluate = async () => {
    setBusy("run");
    try {
      const symbols = watchlist
        .split(",")
        .map((entry) => entry.trim())
        .filter(Boolean);
      await runStrategy(paperId, symbols);
      onDone(`Evaluated the bound strategy over ${symbols.length} symbol(s).`);
    } catch (err) {
      onError((err as Error).message);
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="glass-panel" style={{ marginBottom: 20 }}>
      <h3 style={{ marginTop: 0 }}>Act on this ledger</h3>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))", gap: 14, alignItems: "end" }}>
        <label>
          <FieldLabel>Symbol</FieldLabel>
          <input value={symbol} onChange={(e) => setSymbol(e.target.value.toUpperCase())} style={inputStyle} />
        </label>
        <label>
          <FieldLabel>Side</FieldLabel>
          <select value={side} onChange={(e) => setSide(e.target.value as "BUY" | "SELL")} style={inputStyle}>
            <option value="BUY">BUY</option>
            <option value="SELL">SELL</option>
          </select>
        </label>
        <label>
          <FieldLabel>Quantity</FieldLabel>
          <input type="number" value={quantity} onChange={(e) => setQuantity(Number(e.target.value))} style={inputStyle} />
        </label>
        <label>
          <FieldLabel>Price</FieldLabel>
          <input type="number" value={price} onChange={(e) => setPrice(Number(e.target.value))} style={inputStyle} />
        </label>
        <button className="secondary-button" onClick={fill} disabled={busy !== null}>
          {busy === "order" ? "Recording…" : "Record simulated fill"}
        </button>
      </div>

      <div style={{ display: "flex", gap: 14, marginTop: 18, flexWrap: "wrap", alignItems: "flex-end" }}>
        <label style={{ flex: "1 1 320px" }}>
          <FieldLabel>Watchlist for the bound strategy</FieldLabel>
          <input value={watchlist} onChange={(e) => setWatchlist(e.target.value)} style={inputStyle} />
        </label>
        <button className="glowing-button" onClick={evaluate} disabled={busy !== null || !strategyBound}>
          {busy === "run" ? "Evaluating…" : "Run strategy now"}
        </button>
      </div>
      {!strategyBound && (
        <p style={{ color: "var(--text-muted)", fontSize: "0.82rem", marginBottom: 0 }}>
          This ledger has no strategy bound to it, so only manual fills are available.
        </p>
      )}
    </div>
  );
}

function DivergencePanel({ divergence }: { divergence: Divergence }) {
  return (
    <div className="glass-panel glass-panel-cyan" style={{ marginBottom: 20 }}>
      <h3 style={{ marginTop: 0 }}>Live versus the backtest that justified it</h3>
      <div className="metrics-grid">
        <Stat label="Days live" value={String(divergence.days_live)} />
        <Stat
          label="Paper annualised"
          value={
            divergence.paper_annualised_return_pct === null
              ? "—"
              : `${divergence.paper_annualised_return_pct}%`
          }
        />
        <Stat
          label="Backtest CAGR"
          value={divergence.backtest_cagr_pct === null ? "—" : `${divergence.backtest_cagr_pct}%`}
        />
        <Stat
          label="Gap"
          value={divergence.annualised_gap_pct === null ? "—" : `${divergence.annualised_gap_pct}%`}
          tone={toneFor(divergence.annualised_gap_pct)}
        />
      </div>
      <p style={{ color: "var(--text-secondary)", marginBottom: 4, marginTop: 14 }}>{divergence.verdict}</p>
      <p style={{ color: "var(--text-muted)", fontSize: "0.82rem", margin: 0 }}>{divergence.caveat}</p>
    </div>
  );
}

function Heading() {
  return (
    <div style={{ marginBottom: 24 }}>
      <h1 style={{ margin: 0, fontSize: "1.9rem" }}>Paper Trading & Signal Tracking</h1>
      <p style={{ color: "var(--text-secondary)", margin: "6px 0 0", maxWidth: 780 }}>
        A persisted simulated ledger with a full audit trail — every signal, taken or skipped — and
        the honest comparison of live performance against the backtest that justified deploying the
        strategy.
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
