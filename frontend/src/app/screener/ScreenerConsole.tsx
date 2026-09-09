"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  ACTION_TONE,
  getScreenerFilters,
  rowsToCsv,
  runScreen,
  type ScreenerFilterVocabulary,
  type ScreenerQuery,
  type ScreenerResponse,
  type ScreenerRow,
} from "@/lib/screenerApi";
import { formatNumber } from "@/lib/portfolioApi";

// Presets exist because the honest default — 300 names with fundamentals — is
// a minute of scraping on a cold cache, and someone landing on this page for
// the first time should not have to discover that by waiting.
const PRESETS: Array<{ key: string; label: string; note: string; query: ScreenerQuery }> = [
  {
    key: "quick",
    label: "Quick technical scan",
    note: "150 names, prices only. Seconds, not minutes.",
    query: { index: "NIFTY200", universe_limit: 150, with_fundamentals: false, limit: 50 },
  },
  {
    key: "quality",
    label: "Quality compounders",
    note: "ROCE above 18%, low leverage, above the 200-day.",
    query: {
      index: "NIFTY500",
      universe_limit: 300,
      with_fundamentals: true,
      fundamental_limit: 60,
      min_roce: 18,
      max_debt_to_equity: 1,
      above_sma200: true,
      limit: 50,
    },
  },
  {
    key: "momentum",
    label: "Trend momentum",
    note: "Golden cross, ADX above 20, RSI still short of exhaustion.",
    query: {
      index: "NIFTY500",
      universe_limit: 300,
      with_fundamentals: false,
      golden_cross: true,
      min_adx: 20,
      rsi_max: 70,
      limit: 50,
    },
  },
  {
    key: "buys",
    label: "Ranked buys only",
    note: "Everything the combined scorer calls a Buy or better.",
    query: {
      index: "NIFTY500",
      universe_limit: 300,
      with_fundamentals: true,
      fundamental_limit: 80,
      actions: ["BUY", "STRONG_BUY"],
      limit: 50,
    },
  },
];

const numberOrUndefined = (value: string): number | undefined =>
  value.trim() === "" ? undefined : Number(value);

export default function ScreenerConsole() {
  const [vocabulary, setVocabulary] = useState<ScreenerFilterVocabulary | null>(null);
  const [query, setQuery] = useState<ScreenerQuery>(PRESETS[0].query);
  const [activePreset, setActivePreset] = useState<string>("quick");
  const [result, setResult] = useState<ScreenerResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<"score" | "rsi14" | "roce_pct" | "pe_ratio">("score");

  useEffect(() => {
    const controller = new AbortController();
    getScreenerFilters(controller.signal)
      .then(setVocabulary)
      .catch(() => setVocabulary(null));
    return () => controller.abort();
  }, []);

  const scan = useCallback(async (next: ScreenerQuery) => {
    setLoading(true);
    setError(null);
    try {
      setResult(await runScreen(next));
    } catch (err) {
      if ((err as Error).name !== "AbortError") setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  const applyPreset = (key: string) => {
    const preset = PRESETS.find((entry) => entry.key === key);
    if (!preset) return;
    setActivePreset(key);
    setQuery(preset.query);
    setResult(null);
  };

  const patch = (changes: Partial<ScreenerQuery>) => {
    setActivePreset("custom");
    setQuery((current) => ({ ...current, ...changes }));
  };

  const rows = useMemo(() => {
    if (!result) return [];
    const copy = [...result.results];
    if (sortKey === "score") return copy;
    // Missing values sort last regardless of direction — a blank P/E is not a
    // cheap one.
    return copy.sort((a, b) => {
      const left = a[sortKey];
      const right = b[sortKey];
      if (left === null || left === undefined) return 1;
      if (right === null || right === undefined) return -1;
      return sortKey === "pe_ratio" ? left - right : right - left;
    });
  }, [result, sortKey]);

  const downloadCsv = () => {
    if (!rows.length) return;
    const blob = new Blob([rowsToCsv(rows)], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `screener-${query.index ?? "nse"}-${new Date().toISOString().slice(0, 10)}.csv`;
    anchor.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="app-container animate-fade-in">
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ margin: 0, fontSize: "1.9rem" }}>NSE Universe Screener</h1>
        <p style={{ color: "var(--text-secondary)", margin: "6px 0 0", maxWidth: 760 }}>
          The whole eligible universe scored on the same technical and fundamental model your
          holdings are, so a screener hit and a position are directly comparable numbers rather
          than two unrelated scales.
        </p>
      </div>

      <div className="bento-grid" style={{ marginBottom: 20 }}>
        {PRESETS.map((preset) => (
          <button
            key={preset.key}
            onClick={() => applyPreset(preset.key)}
            className="bento-card bento-span-6"
            style={{
              textAlign: "left",
              cursor: "pointer",
              borderColor: activePreset === preset.key ? "var(--accent-cyan)" : undefined,
            }}
          >
            <div style={{ fontWeight: 600, marginBottom: 4 }}>{preset.label}</div>
            <div style={{ color: "var(--text-muted)", fontSize: "0.82rem" }}>{preset.note}</div>
          </button>
        ))}
      </div>

      <div className="glass-panel" style={{ marginBottom: 20 }}>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
            gap: 14,
          }}
        >
          <Field label="Index">
            <select
              value={query.index ?? "NIFTY500"}
              onChange={(event) => patch({ index: event.target.value })}
              style={inputStyle}
            >
              {(vocabulary?.indices ?? ["NIFTY500"]).map((index) => (
                <option key={index} value={index}>
                  {index}
                </option>
              ))}
            </select>
          </Field>

          <Field label="Sector">
            <select
              value={query.sector ?? ""}
              onChange={(event) => patch({ sector: event.target.value || undefined })}
              style={inputStyle}
            >
              <option value="">All sectors</option>
              {(vocabulary?.sectors ?? []).map((sector) => (
                <option key={sector} value={sector}>
                  {sector}
                </option>
              ))}
            </select>
          </Field>

          <Field label="Market cap">
            <select
              value={query.cap ?? ""}
              onChange={(event) => patch({ cap: event.target.value || undefined })}
              style={inputStyle}
            >
              <option value="">Any</option>
              {(vocabulary?.caps ?? ["large", "mid", "small", "micro"]).map((cap) => (
                <option key={cap} value={cap}>
                  {cap}
                </option>
              ))}
            </select>
          </Field>

          <Field label="Min score">
            <input
              type="number"
              min={0}
              max={100}
              value={query.min_score ?? ""}
              onChange={(event) => patch({ min_score: numberOrUndefined(event.target.value) })}
              style={inputStyle}
            />
          </Field>

          <Field label="Min ROCE %">
            <input
              type="number"
              value={query.min_roce ?? ""}
              onChange={(event) => patch({ min_roce: numberOrUndefined(event.target.value) })}
              style={inputStyle}
            />
          </Field>

          <Field label="Max P/E">
            <input
              type="number"
              value={query.max_pe ?? ""}
              onChange={(event) => patch({ max_pe: numberOrUndefined(event.target.value) })}
              style={inputStyle}
            />
          </Field>

          <Field label="Max debt/equity">
            <input
              type="number"
              step="0.1"
              value={query.max_debt_to_equity ?? ""}
              onChange={(event) =>
                patch({ max_debt_to_equity: numberOrUndefined(event.target.value) })
              }
              style={inputStyle}
            />
          </Field>

          <Field label="RSI band">
            <div style={{ display: "flex", gap: 6 }}>
              <input
                type="number"
                placeholder="min"
                value={query.rsi_min ?? ""}
                onChange={(event) => patch({ rsi_min: numberOrUndefined(event.target.value) })}
                style={inputStyle}
              />
              <input
                type="number"
                placeholder="max"
                value={query.rsi_max ?? ""}
                onChange={(event) => patch({ rsi_max: numberOrUndefined(event.target.value) })}
                style={inputStyle}
              />
            </div>
          </Field>

          <Field label="Universe size">
            <input
              type="number"
              min={10}
              max={2000}
              value={query.universe_limit ?? 300}
              onChange={(event) => patch({ universe_limit: Number(event.target.value) })}
              style={inputStyle}
            />
          </Field>

          <Field label="Fundamentals scraped">
            <input
              type="number"
              min={0}
              max={300}
              disabled={query.with_fundamentals === false}
              value={query.fundamental_limit ?? 60}
              onChange={(event) => patch({ fundamental_limit: Number(event.target.value) })}
              style={inputStyle}
            />
          </Field>
        </div>

        <div style={{ display: "flex", gap: 18, flexWrap: "wrap", marginTop: 16 }}>
          <Toggle
            label="Above 200-day SMA"
            checked={query.above_sma200 === true}
            onChange={(checked) => patch({ above_sma200: checked || undefined })}
          />
          <Toggle
            label="Golden cross"
            checked={query.golden_cross === true}
            onChange={(checked) => patch({ golden_cross: checked || undefined })}
          />
          <Toggle
            label="F&O names only"
            checked={query.fno_only === true}
            onChange={(checked) => patch({ fno_only: checked || undefined })}
          />
          <Toggle
            label="Score fundamentals"
            checked={query.with_fundamentals !== false}
            onChange={(checked) => patch({ with_fundamentals: checked })}
          />
        </div>

        <div style={{ display: "flex", gap: 10, marginTop: 18, flexWrap: "wrap" }}>
          <button className="glowing-button" onClick={() => scan(query)} disabled={loading}>
            {loading ? "Scanning universe…" : "Run screen"}
          </button>
          <button className="secondary-button" onClick={downloadCsv} disabled={!rows.length}>
            Export CSV
          </button>
          <select
            value={sortKey}
            onChange={(event) => setSortKey(event.target.value as typeof sortKey)}
            style={{ ...inputStyle, maxWidth: 200 }}
          >
            <option value="score">Sort: combined score</option>
            <option value="rsi14">Sort: RSI</option>
            <option value="roce_pct">Sort: ROCE</option>
            <option value="pe_ratio">Sort: cheapest P/E</option>
          </select>
        </div>

        <p style={{ color: "var(--text-muted)", fontSize: "0.8rem", margin: "14px 0 0" }}>
          A cold run over 300 names with fundamentals takes tens of seconds — each uncached symbol
          is a Screener.in page fetch. Results are cached for an hour, so a repeat of the same
          scan returns immediately.
        </p>
      </div>

      {error && (
        <div className="glass-panel" style={{ borderColor: "var(--color-sell)", marginBottom: 20 }}>
          <strong style={{ color: "var(--color-sell)" }}>Screen failed</strong>
          <p style={{ margin: "6px 0 0", color: "var(--text-secondary)" }}>{error}</p>
        </div>
      )}

      {loading && !result && (
        <div className="loading-container">
          <div className="spinner" />
        </div>
      )}

      {result && (
        <>
          <div className="metrics-grid" style={{ marginBottom: 20 }}>
            <Stat label="Ranked" value={String(result.count)} />
            <Stat label="Priced" value={`${result.scanned} of ${result.universe}`} />
            <Stat label="Fundamentals scored" value={String(result.fundamentals_scored)} />
            <Stat label="Source" value={result.cached ? "Cached run" : "Fresh scan"} />
          </div>

          {result.notes.length > 0 && (
            <div className="glass-panel" style={{ marginBottom: 20 }}>
              <ul style={{ color: "var(--text-muted)", fontSize: "0.85rem", paddingLeft: 18 }}>
                {result.notes.map((note, index) => (
                  <li key={index}>{note}</li>
                ))}
              </ul>
            </div>
          )}

          <div className="custom-table-container">
            <table className="custom-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Stock</th>
                  <th style={{ textAlign: "right" }}>Price</th>
                  <th style={{ textAlign: "right" }}>Score</th>
                  <th>Action</th>
                  <th style={{ textAlign: "right" }}>RSI</th>
                  <th style={{ textAlign: "right" }}>ADX</th>
                  <th style={{ textAlign: "right" }}>P/E</th>
                  <th style={{ textAlign: "right" }}>ROCE</th>
                  <th style={{ textAlign: "right" }}>D/E</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {rows.map((row, index) => (
                  <ResultRow
                    key={row.symbol}
                    rank={index + 1}
                    row={row}
                    expanded={expanded === row.symbol}
                    onToggle={() => setExpanded(expanded === row.symbol ? null : row.symbol)}
                  />
                ))}
                {rows.length === 0 && (
                  <tr>
                    <td colSpan={11} style={{ textAlign: "center", color: "var(--text-muted)" }}>
                      Nothing in this universe passed every filter. Loosen one and rescan.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}

      <p style={{ color: "var(--text-muted)", fontSize: "0.8rem", marginTop: 28 }}>
        Scores are diagnostics over public data, not investment advice. A high score is a starting
        point for research, not a reason to buy.
      </p>
    </div>
  );
}

function ResultRow({
  rank,
  row,
  expanded,
  onToggle,
}: {
  rank: number;
  row: ScreenerRow;
  expanded: boolean;
  onToggle: () => void;
}) {
  const tone = ACTION_TONE[row.action ?? ""] ?? "var(--text-secondary)";
  return (
    <>
      <tr>
        <td style={{ color: "var(--text-muted)" }}>{rank}</td>
        <td>
          <Link href={`/analyse/${row.symbol}`} style={{ color: "var(--text-primary)", fontWeight: 600 }}>
            {row.symbol}
          </Link>
          <div style={{ color: "var(--text-muted)", fontSize: "0.78rem" }}>
            {row.name}
            {row.sector && ` · ${row.sector}`}
            {row.cap && ` · ${row.cap}`}
          </div>
        </td>
        <td style={{ textAlign: "right" }}>{formatNumber(row.price)}</td>
        <td style={{ textAlign: "right", fontWeight: 600, color: tone }}>
          {row.score === null ? "—" : row.score.toFixed(1)}
          <div style={{ fontSize: "0.72rem", color: "var(--text-muted)", fontWeight: 400 }}>
            {(row.coverage * 100).toFixed(0)}% covered
          </div>
        </td>
        <td>
          <span style={{ color: tone, fontWeight: 600 }}>{row.action_label ?? "—"}</span>
          {row.conviction && (
            <div style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>{row.conviction}</div>
          )}
        </td>
        <td style={{ textAlign: "right" }}>{formatNumber(row.rsi14, 1)}</td>
        <td style={{ textAlign: "right" }}>{formatNumber(row.adx, 1)}</td>
        <td style={{ textAlign: "right" }}>{formatNumber(row.pe_ratio, 1)}</td>
        <td style={{ textAlign: "right" }}>{formatNumber(row.roce_pct, 1)}</td>
        <td style={{ textAlign: "right" }}>{formatNumber(row.debt_to_equity, 2)}</td>
        <td style={{ textAlign: "right" }}>
          <button
            onClick={onToggle}
            style={{
              background: "none",
              border: "none",
              color: "var(--accent-cyan)",
              cursor: "pointer",
              fontSize: "0.8rem",
            }}
          >
            {expanded ? "Hide" : "Why"}
          </button>
        </td>
      </tr>
      {expanded && (
        <tr>
          <td colSpan={11} style={{ background: "rgba(0,0,0,0.25)" }}>
            <div style={{ padding: "10px 4px" }}>
              <strong style={{ fontSize: "0.85rem" }}>What drove this score</strong>
              <ul style={{ margin: "8px 0 0", paddingLeft: 18, color: "var(--text-secondary)", fontSize: "0.85rem" }}>
                {row.reasons.map((reason, index) => (
                  <li key={index}>{reason}</li>
                ))}
                {row.reasons.length === 0 && <li>No reasons were recorded for this row.</li>}
              </ul>
              <div style={{ display: "flex", gap: 20, marginTop: 10, flexWrap: "wrap" }}>
                {Object.entries(row.components).map(([name, component]) => (
                  <div key={name} style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
                    <span style={{ textTransform: "capitalize" }}>{name}</span>:{" "}
                    <strong style={{ color: "var(--text-primary)" }}>
                      {component.score === null ? "—" : component.score.toFixed(1)}
                    </strong>{" "}
                    ({(component.coverage * 100).toFixed(0)}% covered)
                  </div>
                ))}
              </div>
              {row.warnings.length > 0 && (
                <p style={{ color: "var(--color-hold)", fontSize: "0.8rem", marginTop: 8 }}>
                  {row.warnings.join(" · ")}
                </p>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
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

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label style={{ display: "block" }}>
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
        {label}
      </span>
      {children}
    </label>
  );
}

function Toggle({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: "0.85rem", cursor: "pointer" }}>
      <input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} />
      {label}
    </label>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
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
    </div>
  );
}
