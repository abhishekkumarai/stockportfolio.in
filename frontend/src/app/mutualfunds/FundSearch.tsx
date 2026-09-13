"use client";

import { Search } from "lucide-react";

import { useCallback, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { searchFunds, type SchemeSearchResult } from "@/lib/mfApi";
import MyMutualFunds from "./MyMutualFunds";

const POPULAR_FUNDS = [
  { code: 122639, name: "Parag Parikh Flexi Cap Fund", plan: "Direct · Growth", house: "PPFAS" },
  { code: 120503, name: "Axis ELSS Tax Saver Fund", plan: "Direct · Growth", house: "Axis" },
  { code: 118989, name: "HDFC Mid-Cap Opportunities Fund", plan: "Direct · Growth", house: "HDFC" },
  { code: 119598, name: "SBI Bluechip Fund", plan: "Direct · Growth", house: "SBI" },
  { code: 120465, name: "Mirae Asset Large Cap Fund", plan: "Direct · Growth", house: "Mirae" },
  { code: 125497, name: "HDFC Top 100 Fund", plan: "Direct · Growth", house: "HDFC" },
];

export default function FundSearch() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [query, setQuery] = useState(searchParams.get("q") ?? "");
  const [directOnly, setDirectOnly] = useState(searchParams.get("direct") !== "false");
  const [growthOnly, setGrowthOnly] = useState(searchParams.get("growth") !== "false");
  const [results, setResults] = useState<SchemeSearchResult[]>([]);
  // Which query the current results belong to, so a stale result set is never
  // rendered against a newer query.
  const [resultsFor, setResultsFor] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Derived rather than stored: resetting state from inside the effect would
  // trigger a cascading re-render on every keystroke.
  const activeQuery = query.trim().length >= 2 ? query.trim() : "";
  const showResults = activeQuery !== "" && resultsFor === activeQuery;

  // Keep the query in the URL so a search can be shared or reloaded.
  const syncUrl = useCallback(
    (text: string, direct: boolean, growth: boolean) => {
      const params = new URLSearchParams();
      if (text.trim()) params.set("q", text.trim());
      if (!direct) params.set("direct", "false");
      if (!growth) params.set("growth", "false");
      const qs = params.toString();
      router.replace(qs ? `/mutualfunds?${qs}` : "/mutualfunds", { scroll: false });
    },
    [router]
  );

  useEffect(() => {
    if (!activeQuery) return;

    // Abort in-flight requests so a slow earlier keystroke cannot overwrite the
    // results of a later one.
    const controller = new AbortController();
    const timer = setTimeout(async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await searchFunds(activeQuery, directOnly, growthOnly, controller.signal);
        setResults(data.results);
        setResultsFor(activeQuery);
        syncUrl(activeQuery, directOnly, growthOnly);
      } catch (err) {
        if ((err as Error).name !== "AbortError") {
          setError((err as Error).message || "Could not search mutual funds.");
          setResults([]);
          setResultsFor(activeQuery);
        }
      } finally {
        setLoading(false);
      }
    }, 350);

    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [activeQuery, directOnly, growthOnly, syncUrl]);

  const toggleStyle = (active: boolean): React.CSSProperties => ({
    padding: "8px 16px",
    borderRadius: "999px",
    border: `1px solid ${active ? "var(--accent-cyan)" : "var(--border-subtle)"}`,
    background: active ? "var(--accent-cyan-glow)" : "transparent",
    color: active ? "var(--accent-cyan)" : "var(--text-secondary)",
    cursor: "pointer",
    fontSize: "0.85rem",
    fontWeight: 600,
    transition: "var(--transition-smooth)",
  });

  return (
    <div className="app-container animate-fade-in">
      <section style={{ textAlign: "center", margin: "50px 0 40px" }}>
        <h1 style={{ fontSize: "2.8rem", fontWeight: 800, lineHeight: 1.15, marginBottom: "16px" }}>
          Indian{" "}
          <span style={{ color: "var(--accent-cyan)", textShadow: "0 0 20px var(--accent-cyan-glow)" }}>
            Mutual Fund
          </span>{" "}
          Analysis
        </h1>
        <p style={{ fontSize: "1.1rem", maxWidth: "680px", margin: "0 auto" }}>
          Search any of ~37,000 Indian mutual fund schemes for NAV history, trailing and rolling
          returns, drawdowns and risk-adjusted performance.
        </p>
      </section>

      <MyMutualFunds />

      <div
        className="glass-panel-cyan"
        style={{ padding: "32px", maxWidth: "860px", margin: "0 auto 40px" }}
      >
        <h3 style={{ fontSize: "1.2rem", fontWeight: 600, marginBottom: "16px" }}>
          Search Mutual Fund Schemes
        </h3>

        <div style={{ position: "relative" }}>
          <span
            style={{
              position: "absolute",
              left: "18px",
              top: "50%",
              transform: "translateY(-50%)",
              color: "var(--text-muted)",
              display: "flex",
              pointerEvents: "none",
            }}
          >
            <Search size={15} strokeWidth={1.5} />
          </span>
          <input
            type="text"
            placeholder="Search by fund or AMC name (e.g. Parag Parikh, HDFC, Nifty Index...)"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            autoFocus
            style={{
              width: "100%",
              padding: "12px 16px 12px 44px",
              borderRadius: "10px",
              border: "1px solid var(--border-subtle)",
              background: "var(--bg-secondary)",
              color: "var(--text-primary)",
              fontSize: "0.95rem",
              outline: "none",
            }}
          />
        </div>

        <div style={{ display: "flex", gap: "10px", marginTop: "16px", flexWrap: "wrap" }}>
          <button type="button" style={toggleStyle(directOnly)} onClick={() => setDirectOnly(!directOnly)}>
            Direct plans only
          </button>
          <button type="button" style={toggleStyle(growthOnly)} onClick={() => setGrowthOnly(!growthOnly)}>
            Growth plans only
          </button>
        </div>

        <p style={{ marginTop: "14px", fontSize: "0.85rem", color: "var(--text-secondary)" }}>
          Direct plans carry no distributor commission, and Growth plans reinvest payouts into NAV —
          together they give the cleanest total-return series to compare funds on.
        </p>
      </div>

      <section style={{ maxWidth: "860px", margin: "0 auto" }}>
        {loading && (
          <div style={{ textAlign: "center", padding: "30px", color: "var(--text-secondary)" }}>
            Searching schemes...
          </div>
        )}

        {error && activeQuery && !loading && (
          <div
            className="glass-panel"
            style={{ padding: "24px", textAlign: "center", borderColor: "var(--color-sell)" }}
          >
            <div style={{ color: "var(--color-sell)", fontWeight: 600, marginBottom: "6px" }}>
              Search failed
            </div>
            <div style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>{error}</div>
          </div>
        )}

        {!loading && !error && showResults && results.length === 0 && (
          <div className="glass-panel" style={{ padding: "30px", textAlign: "center" }}>
            <div style={{ fontWeight: 600, marginBottom: "6px" }}>No schemes matched “{query}”</div>
            <div style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>
              Try a shorter name, or turn off the Direct/Growth filters above.
            </div>
          </div>
        )}

        {!loading && showResults && results.length > 0 && (
          <>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                marginBottom: "16px",
              }}
            >
              <h3 style={{ fontSize: "1.1rem", fontWeight: 700 }}>
                {results.length} scheme{results.length === 1 ? "" : "s"} found
              </h3>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
              {results.map((scheme) => (
                <Link
                  key={scheme.schemeCode}
                  href={`/mutualfunds/${scheme.schemeCode}`}
                  className="glass-panel"
                  style={{
                    padding: "18px 22px",
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    gap: "16px",
                    textDecoration: "none",
                    cursor: "pointer",
                  }}
                >
                  <div>
                    <div style={{ fontWeight: 600, color: "var(--text-primary)", marginBottom: "4px" }}>
                      {scheme.schemeName}
                    </div>
                    <div style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
                      Scheme code {scheme.schemeCode}
                    </div>
                  </div>
                  <span
                    style={{
                      color: "var(--accent-blue)",
                      fontSize: "0.85rem",
                      fontWeight: 600,
                      whiteSpace: "nowrap",
                    }}
                  >
                    Analyse →
                  </span>
                </Link>
              ))}
            </div>
          </>
        )}

        {!activeQuery && !loading && (
          <>
            <h3
              style={{
                fontSize: "1.3rem",
                fontWeight: 700,
                marginBottom: "20px",
                display: "flex",
                alignItems: "center",
                gap: "8px",
              }}
            >
              Popular Funds
            </h3>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
                gap: "18px",
              }}
            >
              {POPULAR_FUNDS.map((fund) => (
                <Link
                  key={fund.code}
                  href={`/mutualfunds/${fund.code}`}
                  className="glass-panel"
                  style={{
                    padding: "22px",
                    display: "flex",
                    flexDirection: "column",
                    gap: "10px",
                    textDecoration: "none",
                    cursor: "pointer",
                  }}
                >
                  <div>
                    <div
                      style={{
                        fontSize: "0.75rem",
                        color: "var(--accent-blue)",
                        fontWeight: 700,
                        marginBottom: "6px",
                      }}
                    >
                      {fund.house}
                    </div>
                    <h4 style={{ fontSize: "1.05rem", fontWeight: 700, color: "var(--text-primary)" }}>{fund.name}</h4>
                    <p style={{ fontSize: "0.82rem", marginTop: "6px" }}>{fund.plan}</p>
                  </div>
                  <span
                    style={{
                      color: "var(--accent-blue)",
                      fontSize: "0.85rem",
                      fontWeight: 600,
                      alignSelf: "flex-end",
                    }}
                  >
                    Analyse →
                  </span>
                </Link>
              ))}
            </div>
          </>
        )}
      </section>
    </div>
  );
}
