"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { loadPortfolio, valuePortfolio, type PricedRow } from "@/lib/portfolioApi";
import { formatCurrency, formatPct, getFundAnalysis, type TrailingReturn } from "@/lib/mfApi";

interface FundRow extends PricedRow {
  schemeCode: number;
}

interface FundGrowth {
  oneYear: TrailingReturn | null;
  threeYear: TrailingReturn | null;
}

function trailingValue(entry: TrailingReturn | null | undefined): number | null {
  if (!entry) return null;
  return entry.annualised ? entry.cagr_pct : entry.return_pct;
}

export default function MyMutualFunds() {
  const [funds, setFunds] = useState<FundRow[] | null>(null);
  const [growth, setGrowth] = useState<Record<number, FundGrowth>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();

    async function load() {
      const portfolio = loadPortfolio();
      if (portfolio.funds.length === 0) {
        setFunds([]);
        setLoading(false);
        return;
      }

      setLoading(true);
      setError(null);
      try {
        const valuation = await valuePortfolio(portfolio.equity, portfolio.funds, portfolio.cash, controller.signal);
        const fundRows = valuation.holdings
          .filter((row) => row.kind === "fund")
          .map((row) => ({ ...row, schemeCode: Number(row.key) }));
        setFunds(fundRows);

        // One fund failing to load its own return history shouldn't blank out the rest.
        const results = await Promise.allSettled(
          fundRows.map((row) => getFundAnalysis(row.schemeCode, controller.signal))
        );
        const nextGrowth: Record<number, FundGrowth> = {};
        results.forEach((result, idx) => {
          if (result.status === "fulfilled") {
            nextGrowth[fundRows[idx].schemeCode] = {
              oneYear: result.value.trailing_returns["1y"] ?? null,
              threeYear: result.value.trailing_returns["3y"] ?? null,
            };
          }
        });
        setGrowth(nextGrowth);
      } catch (err) {
        if ((err as Error).name !== "AbortError") {
          setError((err as Error).message || "Could not load your mutual fund holdings.");
        }
      } finally {
        setLoading(false);
      }
    }

    load();
    return () => controller.abort();
  }, []);

  // Nothing in the portfolio yet, or still figuring that out — stay out of the way
  // of the search/discovery flow below rather than showing an empty panel.
  if (loading || !funds || funds.length === 0) return null;

  return (
    <section style={{ maxWidth: "860px", margin: "0 auto 40px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: "16px", flexWrap: "wrap", gap: "8px" }}>
        <h3 style={{ fontSize: "1.3rem", fontWeight: 700 }}>Your Mutual Funds</h3>
        <Link href="/portfolio/holdings" style={{ fontSize: "0.85rem", color: "var(--accent-blue)", fontWeight: 600, textDecoration: "none" }}>
          Manage holdings →
        </Link>
      </div>

      {error && (
        <div className="glass-panel" style={{ padding: "20px", textAlign: "center", borderColor: "var(--color-sell)", marginBottom: "12px" }}>
          <div style={{ color: "var(--color-sell)", fontWeight: 600, marginBottom: "4px" }}>Could not load your funds</div>
          <div style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>{error}</div>
        </div>
      )}

      <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
        {funds.map((fund) => {
          const fundGrowth = growth[fund.schemeCode];
          const oneYear = trailingValue(fundGrowth?.oneYear);
          const threeYear = trailingValue(fundGrowth?.threeYear);

          return (
            <Link
              key={fund.schemeCode}
              href={`/mutualfunds/${fund.schemeCode}`}
              className="glass-panel"
              style={{ padding: "18px 22px", display: "block", textDecoration: "none" }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "16px", flexWrap: "wrap" }}>
                <div style={{ flex: "1 1 220px", minWidth: 0 }}>
                  <div style={{ fontWeight: 700, color: "var(--text-primary)", marginBottom: "2px" }}>{fund.name}</div>
                  {fund.category && (
                    <div style={{ fontSize: "0.78rem", color: "var(--text-muted)" }}>{fund.category}</div>
                  )}
                </div>

                <div style={{ display: "flex", gap: "24px", flexWrap: "wrap" }}>
                  <Stat label="Invested" value={formatCurrency(fund.invested)} />
                  <Stat label="Value" value={fund.current_value !== null ? formatCurrency(fund.current_value) : "—"} />
                  <Stat
                    label="Your P&L"
                    value={fund.pnl !== null ? `${fund.pnl >= 0 ? "+" : ""}${formatCurrency(fund.pnl)}` : "—"}
                    sub={formatPct(fund.pnl_pct)}
                    tone={fund.pnl === null ? undefined : fund.pnl >= 0 ? "up" : "down"}
                  />
                  <Stat
                    label="Fund 1Y"
                    value={formatPct(oneYear)}
                    tone={oneYear === null ? undefined : oneYear >= 0 ? "up" : "down"}
                  />
                  <Stat
                    label="Fund 3Y CAGR"
                    value={formatPct(threeYear)}
                    tone={threeYear === null ? undefined : threeYear >= 0 ? "up" : "down"}
                  />
                </div>
              </div>
            </Link>
          );
        })}
      </div>
    </section>
  );
}

function Stat({
  label,
  value,
  sub,
  tone,
}: {
  label: string;
  value: string;
  sub?: string;
  tone?: "up" | "down";
}) {
  const color = tone === "up" ? "var(--color-buy)" : tone === "down" ? "var(--color-sell)" : "var(--text-primary)";
  return (
    <div style={{ textAlign: "right", minWidth: "80px" }}>
      <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", fontWeight: 600, textTransform: "uppercase" }}>
        {label}
      </div>
      <div style={{ fontSize: "0.95rem", fontWeight: 700, color }}>{value}</div>
      {sub && <div style={{ fontSize: "0.72rem", color }}>{sub}</div>}
    </div>
  );
}
