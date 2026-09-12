"use client";

import { useEffect, useRef, useState } from "react";
import { apiUrl } from "@/lib/api";
import type { EquityHoldingInput, FundHoldingInput } from "@/lib/portfolioApi";
import { searchFunds, type SchemeSearchResult } from "@/lib/mfApi";

interface StockSuggestion {
  symbol: string;
  name: string;
  sector: string | null;
}

export default function AddHoldingForm({
  onAddEquity,
  onAddFund,
  cash,
  onCashChange,
}: {
  onAddEquity: (holding: EquityHoldingInput) => void;
  onAddFund: (fund: FundHoldingInput) => void;
  cash: number;
  onCashChange: (cash: number) => void;
}) {
  const [tab, setTab] = useState<"stock" | "fund" | "cash">("stock");

  return (
    <div className="glass-panel" style={{ marginBottom: 24, padding: "22px 24px" }}>
      <div style={{ display: "flex", gap: 8, marginBottom: 20, flexWrap: "wrap" }}>
        {(["stock", "fund", "cash"] as const).map((option) => (
          <button
            key={option}
            onClick={() => setTab(option)}
            style={{
              padding: "6px 16px",
              borderRadius: 999,
              border: `1px solid ${tab === option ? "#2563eb" : "var(--border-subtle)"}`,
              background: tab === option ? "#eff6ff" : "#ffffff",
              color: tab === option ? "#2563eb" : "var(--text-secondary)",
              fontWeight: tab === option ? 600 : 500,
              cursor: "pointer",
              transition: "var(--transition-smooth)",
              textTransform: "capitalize",
              fontSize: "0.85rem",
            }}
          >
            {option === "cash" ? "Cash" : `Add ${option}`}
          </button>
        ))}
      </div>

      {tab === "stock" && <StockForm onAdd={onAddEquity} />}
      {tab === "fund" && <FundForm onAdd={onAddFund} />}
      {tab === "cash" && <CashForm cash={cash} onChange={onCashChange} />}
    </div>
  );
}

const row: React.CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))",
  gap: 12,
  alignItems: "end",
};

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label style={{ display: "block" }}>
      <span style={{ display: "block", color: "var(--text-muted)", fontSize: "0.78rem", marginBottom: 4 }}>
        {label}
      </span>
      {children}
    </label>
  );
}

const inputStyle: React.CSSProperties = {
  width: "100%",
  padding: "9px 12px",
  borderRadius: 8,
  border: "1px solid var(--border-subtle)",
  background: "var(--bg-secondary)",
  color: "var(--text-primary)",
  fontSize: "0.92rem",
};

function StockForm({ onAdd }: { onAdd: (holding: EquityHoldingInput) => void }) {
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<StockSuggestion | null>(null);
  const [suggestions, setSuggestions] = useState<StockSuggestion[]>([]);
  const [quantity, setQuantity] = useState("");
  const [avgCost, setAvgCost] = useState("");
  const [buyDate, setBuyDate] = useState("");
  const [error, setError] = useState<string | null>(null);
  const boxRef = useRef<HTMLDivElement>(null);

  // Same debounce + abort pattern as the fund search on /funds.
  useEffect(() => {
    if (selected || query.trim().length < 2) {
      setSuggestions([]);
      return;
    }
    const controller = new AbortController();
    const timer = setTimeout(async () => {
      try {
        const response = await fetch(
          apiUrl(`/api/stocks/lookup?q=${encodeURIComponent(query.trim())}&limit=8`),
          { signal: controller.signal }
        );
        if (response.ok) setSuggestions((await response.json()).results ?? []);
      } catch {
        // Aborted or offline; leaving the old suggestions is harmless.
      }
    }, 300);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [query, selected]);

  useEffect(() => {
    const onClickOutside = (event: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(event.target as Node)) setSuggestions([]);
    };
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  const submit = () => {
    const qty = Number(quantity);
    const cost = Number(avgCost);
    if (!selected) return setError("Pick a stock from the suggestions.");
    if (!(qty > 0)) return setError("Quantity must be greater than zero.");
    if (!(cost > 0)) return setError("Average cost must be greater than zero.");

    onAdd({
      symbol: selected.symbol,
      quantity: qty,
      avg_cost: cost,
      buy_date: buyDate || null,
    });
    setQuery("");
    setSelected(null);
    setQuantity("");
    setAvgCost("");
    setBuyDate("");
    setError(null);
  };

  return (
    <div>
      <div style={row}>
        <div style={{ position: "relative", gridColumn: "span 2" }} ref={boxRef}>
          <Field label="Stock">
            <input
              style={inputStyle}
              placeholder="Search NSE, e.g. Reliance"
              value={selected ? `${selected.symbol} — ${selected.name}` : query}
              onChange={(event) => {
                setSelected(null);
                setQuery(event.target.value);
              }}
            />
          </Field>
          {suggestions.length > 0 && (
            <ul
              style={{
                position: "absolute",
                zIndex: 10,
                top: "100%",
                left: 0,
                right: 0,
                margin: 0,
                padding: 0,
                listStyle: "none",
                background: "var(--bg-card)",
                border: "1px solid var(--border-subtle)",
                borderRadius: 8,
                maxHeight: 240,
                overflowY: "auto",
              }}
            >
              {suggestions.map((item) => (
                <li key={item.symbol}>
                  <button
                    onClick={() => {
                      setSelected(item);
                      setSuggestions([]);
                    }}
                    style={{
                      width: "100%",
                      textAlign: "left",
                      padding: "8px 12px",
                      background: "none",
                      border: "none",
                      color: "var(--text-primary)",
                      cursor: "pointer",
                    }}
                  >
                    <strong>{item.symbol}</strong>
                    <span style={{ color: "var(--text-muted)", fontSize: "0.8rem" }}> · {item.name}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
        <Field label="Quantity">
          <input style={inputStyle} type="number" min="0" step="any" value={quantity} onChange={(e) => setQuantity(e.target.value)} />
        </Field>
        <Field label="Avg cost (₹)">
          <input style={inputStyle} type="number" min="0" step="any" value={avgCost} onChange={(e) => setAvgCost(e.target.value)} />
        </Field>
        <Field label="Buy date (optional)">
          <input style={inputStyle} type="date" max={new Date().toISOString().slice(0, 10)} value={buyDate} onChange={(e) => setBuyDate(e.target.value)} />
        </Field>
        <button className="glowing-button" onClick={submit} style={{ height: 38 }}>
          Add
        </button>
      </div>
      {error && <p style={{ color: "var(--color-sell)", fontSize: "0.85rem", marginBottom: 0 }}>{error}</p>}
    </div>
  );
}

function FundForm({ onAdd }: { onAdd: (fund: FundHoldingInput) => void }) {
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<SchemeSearchResult | null>(null);
  const [results, setResults] = useState<SchemeSearchResult[]>([]);
  const [units, setUnits] = useState("");
  const [avgNav, setAvgNav] = useState("");
  const [buyDate, setBuyDate] = useState("");
  const [error, setError] = useState<string | null>(null);
  const boxRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (selected || query.trim().length < 2) {
      setResults([]);
      return;
    }
    const controller = new AbortController();
    const timer = setTimeout(async () => {
      try {
        const response = await searchFunds(query.trim(), true, true, controller.signal);
        setResults(response.results.slice(0, 8));
      } catch {
        // Aborted or offline.
      }
    }, 350);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [query, selected]);

  useEffect(() => {
    const onClickOutside = (event: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(event.target as Node)) setResults([]);
    };
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  const submit = () => {
    const unitCount = Number(units);
    const nav = Number(avgNav);
    if (!selected) return setError("Pick a scheme from the suggestions.");
    if (!(unitCount > 0)) return setError("Units must be greater than zero.");
    if (!(nav > 0)) return setError("Average NAV must be greater than zero.");

    onAdd({
      scheme_code: selected.schemeCode,
      units: unitCount,
      avg_nav: nav,
      buy_date: buyDate || null,
    });
    setQuery("");
    setSelected(null);
    setUnits("");
    setAvgNav("");
    setBuyDate("");
    setError(null);
  };

  return (
    <div>
      <div style={row}>
        <div style={{ position: "relative", gridColumn: "span 2" }} ref={boxRef}>
          <Field label="Scheme">
            <input
              style={inputStyle}
              placeholder="Search direct growth schemes"
              value={selected ? selected.schemeName : query}
              onChange={(event) => {
                setSelected(null);
                setQuery(event.target.value);
              }}
            />
          </Field>
          {results.length > 0 && (
            <ul
              style={{
                position: "absolute",
                zIndex: 10,
                top: "100%",
                left: 0,
                right: 0,
                margin: 0,
                padding: 0,
                listStyle: "none",
                background: "var(--bg-card)",
                border: "1px solid var(--border-subtle)",
                borderRadius: 8,
                maxHeight: 240,
                overflowY: "auto",
              }}
            >
              {results.map((scheme) => (
                <li key={scheme.schemeCode}>
                  <button
                    onClick={() => {
                      setSelected(scheme);
                      setResults([]);
                    }}
                    style={{
                      width: "100%",
                      textAlign: "left",
                      padding: "8px 12px",
                      background: "none",
                      border: "none",
                      color: "var(--text-primary)",
                      cursor: "pointer",
                      fontSize: "0.85rem",
                    }}
                  >
                    {scheme.schemeName}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
        <Field label="Units">
          <input style={inputStyle} type="number" min="0" step="any" value={units} onChange={(e) => setUnits(e.target.value)} />
        </Field>
        <Field label="Avg NAV (₹)">
          <input style={inputStyle} type="number" min="0" step="any" value={avgNav} onChange={(e) => setAvgNav(e.target.value)} />
        </Field>
        <Field label="Buy date (optional)">
          <input style={inputStyle} type="date" max={new Date().toISOString().slice(0, 10)} value={buyDate} onChange={(e) => setBuyDate(e.target.value)} />
        </Field>
        <button className="glowing-button" onClick={submit} style={{ height: 38 }}>
          Add
        </button>
      </div>
      {error && <p style={{ color: "var(--color-sell)", fontSize: "0.85rem", marginBottom: 0 }}>{error}</p>}
    </div>
  );
}

function CashForm({ cash, onChange }: { cash: number; onChange: (value: number) => void }) {
  const [value, setValue] = useState(String(cash || ""));

  return (
    <div style={row}>
      <Field label="Cash / liquid balance (₹)">
        <input
          style={inputStyle}
          type="number"
          min="0"
          step="any"
          value={value}
          onChange={(event) => setValue(event.target.value)}
          onBlur={() => onChange(Number(value) || 0)}
        />
      </Field>
      <p style={{ color: "var(--text-muted)", fontSize: "0.8rem", gridColumn: "span 2", margin: 0 }}>
        Counted in your total and asset mix, but excluded from invested capital so it cannot flatter returns.
      </p>
    </div>
  );
}
