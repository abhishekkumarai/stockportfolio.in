"use client";

import { useEffect, useMemo, useState } from "react";
import { Filter, RefreshCw, Search, X } from "lucide-react";
import { getPortfolioNews, type FundHoldingInput, type NewsArticle } from "@/lib/portfolioApi";
import EmptyPortfolioNotice from "../EmptyPortfolioNotice";
import { usePortfolioContext } from "../PortfolioContext";
import SampleDataNotice from "../SampleDataNotice";

const SAMPLE_CATALYSTS_NEWS: NewsArticle[] = [
  {
    symbol: "RELIANCE",
    title: "Reliance Retail & Jio Platforms demerger structuring gets in-principle clearance for FY26 listing",
    url: "https://economictimes.indiatimes.com",
    source: "Economic Times",
    published_at: "2 hours ago",
    tag: "Corporate Actions",
    impact: "BULLISH",
    impact_label: "+0.64α Bullish",
    sentiment_score: 0.82,
    kind: "equity",
  },
  {
    symbol: "TCS",
    title: "TCS signs $1.2B multi-year cloud modernisation and sovereign AI transformation deal with European consortium",
    url: "https://www.bseindia.com",
    source: "BSE Corporate Announcement",
    published_at: "4 hours ago",
    tag: "Order Wins & Expansion",
    impact: "BULLISH",
    impact_label: "+0.45α Bullish",
    sentiment_score: 0.76,
    kind: "equity",
  },
  {
    symbol: "Parag Parikh Flexi Cap",
    title: "Parag Parikh Flexi Cap Fund increases cash allocation to 14.8% amidst elevated small & midcap valuations",
    url: "https://economictimes.indiatimes.com",
    source: "Economic Times",
    published_at: "5 hours ago",
    tag: "Earnings & Financials",
    impact: "NEUTRAL",
    impact_label: "⚪ Neutral",
    sentiment_score: 0.05,
    kind: "fund",
    scheme_name: "Parag Parikh Flexi Cap Fund",
  },
  {
    symbol: "HDFCBANK",
    title: "HDFC Bank reports 16.4% YoY net credit expansion with NIM stabilizing at 3.65% post-merger integration",
    url: "https://www.nseindia.com",
    source: "NSE Disclosures",
    published_at: "6 hours ago",
    tag: "Earnings & Financials",
    impact: "BULLISH",
    impact_label: "+0.38α Bullish",
    sentiment_score: 0.69,
    kind: "equity",
  },
  {
    symbol: "HDFC Top 100",
    title: "HDFC Top 100 Fund crosses Rs 42,000 Cr AUM milestone backed by sustained largecap SIP inflows",
    url: "https://moneycontrol.com",
    source: "Moneycontrol",
    published_at: "8 hours ago",
    tag: "Order Wins & Expansion",
    impact: "BULLISH",
    impact_label: "+0.35α Bullish",
    sentiment_score: 0.71,
    kind: "fund",
    scheme_name: "HDFC Top 100 Fund",
  },
  {
    symbol: "INFY",
    title: "Infosys expands generative AI enterprise suite 'Topaz' with 240+ global enterprise production deployments",
    url: "https://moneycontrol.com",
    source: "Moneycontrol",
    published_at: "9 hours ago",
    tag: "Order Wins & Expansion",
    impact: "BULLISH",
    impact_label: "+0.29α Bullish",
    sentiment_score: 0.65,
    kind: "equity",
  },
  {
    symbol: "ICICIBANK",
    title: "ICICI Bank domestic loan book advances 18.2% YoY; Net NPA drops to 0.42% in pristine asset quality cycle",
    url: "https://livemint.com",
    source: "Livemint",
    published_at: "12 hours ago",
    tag: "Earnings & Financials",
    impact: "BULLISH",
    impact_label: "+0.41α Bullish",
    sentiment_score: 0.74,
    kind: "equity",
  },
];

type AssetTypeFilter = "ALL" | "equity" | "fund";

export default function NewsView() {
  const { portfolio, valuation } = usePortfolioContext();
  const [newsArticles, setNewsArticles] = useState<NewsArticle[]>(SAMPLE_CATALYSTS_NEWS);
  const [newsIsSample, setNewsIsSample] = useState(true);
  const [newsLoading, setNewsLoading] = useState(false);

  // Filter states
  const [selectedType, setSelectedType] = useState<AssetTypeFilter>("ALL");
  const [selectedTicker, setSelectedTicker] = useState<string>("ALL");
  const [searchQuery, setSearchQuery] = useState<string>("");

  const fetchNews = async () => {
    setNewsLoading(true);
    try {
      const hasHoldings = portfolio.equity.length > 0 || portfolio.funds.length > 0;
      if (!hasHoldings) {
        setNewsArticles(SAMPLE_CATALYSTS_NEWS);
        setNewsIsSample(true);
        return;
      }

      // Enrich fund holdings with human-readable scheme names if resolved by valuation
      const fundsWithNames: FundHoldingInput[] = portfolio.funds.map((f) => {
        const matchingVal = valuation?.holdings.find(
          (h) => h.kind === "fund" && String(h.key) === String(f.scheme_code)
        );
        return {
          ...f,
          scheme_name: matchingVal?.name || undefined,
        };
      });

      const res = await getPortfolioNews(portfolio.equity, fundsWithNames);
      const gotRealNews = Boolean(res?.articles?.length);
      setNewsArticles(gotRealNews ? res.articles : SAMPLE_CATALYSTS_NEWS);
      setNewsIsSample(!gotRealNews);
    } catch (err) {
      console.error("News fetch failed", err);
      setNewsArticles(SAMPLE_CATALYSTS_NEWS);
      setNewsIsSample(true);
    } finally {
      setNewsLoading(false);
    }
  };

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void fetchNews();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Compute ticker metadata and counts
  const { tickerList, equityCount, fundCount } = useMemo(() => {
    let eq = 0;
    let mf = 0;
    const map = new Map<string, { symbol: string; kind: "equity" | "fund"; count: number }>();

    for (const art of newsArticles) {
      const kind = art.kind === "fund" ? "fund" : "equity";
      if (kind === "fund") {
        mf += 1;
      } else {
        eq += 1;
      }

      const existing = map.get(art.symbol);
      if (existing) {
        existing.count += 1;
      } else {
        map.set(art.symbol, { symbol: art.symbol, kind, count: 1 });
      }
    }

    return {
      tickerList: Array.from(map.values()),
      equityCount: eq,
      fundCount: mf,
    };
  }, [newsArticles]);

  // Available tickers matching current Asset Type filter
  const visibleTickers = useMemo(() => {
    return tickerList.filter((t) => {
      if (selectedType === "equity") return t.kind === "equity";
      if (selectedType === "fund") return t.kind === "fund";
      return true;
    });
  }, [tickerList, selectedType]);

  // Filtered articles list
  const filteredArticles = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();

    return newsArticles.filter((art) => {
      const kind = art.kind === "fund" ? "fund" : "equity";

      // 1. Asset type filter
      if (selectedType !== "ALL" && kind !== selectedType) {
        return false;
      }

      // 2. Ticker filter
      if (selectedTicker !== "ALL" && art.symbol !== selectedTicker) {
        return false;
      }

      // 3. Search query filter
      if (q) {
        const matchTitle = art.title.toLowerCase().includes(q);
        const matchSymbol = art.symbol.toLowerCase().includes(q);
        const matchTag = art.tag.toLowerCase().includes(q);
        const matchSource = art.source.toLowerCase().includes(q);
        if (!matchTitle && !matchSymbol && !matchTag && !matchSource) {
          return false;
        }
      }

      return true;
    });
  }, [newsArticles, selectedType, selectedTicker, searchQuery]);

  const handleTypeChange = (type: AssetTypeFilter) => {
    setSelectedType(type);
    // If current selected ticker does not belong to new type, reset to ALL
    if (selectedTicker !== "ALL") {
      const match = tickerList.find((t) => t.symbol === selectedTicker);
      if (match && type !== "ALL" && match.kind !== type) {
        setSelectedTicker("ALL");
      }
    }
  };

  const hasActiveFilter = selectedType !== "ALL" || selectedTicker !== "ALL" || searchQuery.trim() !== "";

  const clearAllFilters = () => {
    setSelectedType("ALL");
    setSelectedTicker("ALL");
    setSearchQuery("");
  };

  return (
    <div>
      <div style={{ marginBottom: 20 }}>
        <h1 style={{ margin: 0, fontSize: "1.6rem" }}>Catalysts &amp; News</h1>
        <p style={{ color: "var(--text-secondary)", margin: "6px 0 0" }}>
          News, mutual fund disclosures, and corporate filings filtered strictly for the assets you hold.
        </p>
      </div>

      <EmptyPortfolioNotice />

      {newsIsSample && (
        <SampleDataNotice text="No real news could be fetched for your holdings — the headlines below are fabricated examples, not real articles." />
      )}

      {/* Header with Title and Refresh */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <div>
          <h3 style={{ fontSize: "1.05rem", margin: 0 }}>Holdings News &amp; Disclosures</h3>
          <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", margin: "4px 0 0" }}>
            Filtered strictly for the stocks &amp; mutual funds you hold (Zero generic market noise).
          </p>
        </div>
        <button
          className="secondary-button"
          onClick={fetchNews}
          disabled={newsLoading}
          style={{ display: "flex", alignItems: "center", gap: 6 }}
        >
          <RefreshCw size={14} className={newsLoading ? "animate-spin" : ""} />
          {newsLoading ? "Refreshing..." : "Refresh News"}
        </button>
      </div>

      {/* Filter Control Bar */}
      <div
        className="glass-panel"
        style={{
          padding: "14px 16px",
          marginBottom: 16,
          display: "flex",
          flexDirection: "column",
          gap: 12,
        }}
      >
        {/* Row 1: Asset Type Selector & Search Bar */}
        <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "space-between", alignItems: "center", gap: 10 }}>
          {/* Asset Type Tabs */}
          <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
            <span style={{ fontSize: "0.8rem", fontWeight: 600, color: "var(--text-muted)", marginRight: 2, display: "flex", alignItems: "center", gap: 4 }}>
              <Filter size={13} /> Asset:
            </span>
            <button
              onClick={() => handleTypeChange("ALL")}
              style={{
                fontSize: "0.78rem",
                fontWeight: selectedType === "ALL" ? 600 : 500,
                padding: "4px 10px",
                borderRadius: 6,
                border: selectedType === "ALL" ? "1px solid #2563eb" : "1px solid var(--border-subtle)",
                background: selectedType === "ALL" ? "#eff6ff" : "white",
                color: selectedType === "ALL" ? "#1d4ed8" : "var(--text-secondary)",
                cursor: "pointer",
                transition: "all 0.15s ease",
              }}
            >
              All Assets ({newsArticles.length})
            </button>
            <button
              onClick={() => handleTypeChange("equity")}
              style={{
                fontSize: "0.78rem",
                fontWeight: selectedType === "equity" ? 600 : 500,
                padding: "4px 10px",
                borderRadius: 6,
                border: selectedType === "equity" ? "1px solid #2563eb" : "1px solid var(--border-subtle)",
                background: selectedType === "equity" ? "#eff6ff" : "white",
                color: selectedType === "equity" ? "#1d4ed8" : "var(--text-secondary)",
                cursor: "pointer",
                transition: "all 0.15s ease",
              }}
            >
              Stocks ({equityCount})
            </button>
            <button
              onClick={() => handleTypeChange("fund")}
              style={{
                fontSize: "0.78rem",
                fontWeight: selectedType === "fund" ? 600 : 500,
                padding: "4px 10px",
                borderRadius: 6,
                border: selectedType === "fund" ? "1px solid #d97706" : "1px solid var(--border-subtle)",
                background: selectedType === "fund" ? "#fffbeb" : "white",
                color: selectedType === "fund" ? "#b45309" : "var(--text-secondary)",
                cursor: "pointer",
                transition: "all 0.15s ease",
              }}
            >
              Mutual Funds ({fundCount})
            </button>
          </div>

          {/* Search Box */}
          <div style={{ position: "relative", minWidth: 220, flex: "1 1 220px", maxWidth: 320 }}>
            <Search
              size={14}
              style={{
                position: "absolute",
                left: 10,
                top: "50%",
                transform: "translateY(-50%)",
                color: "var(--text-muted)",
              }}
            />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Filter headlines or tickers…"
              style={{
                width: "100%",
                padding: "5px 28px 5px 30px",
                fontSize: "0.82rem",
                borderRadius: 6,
                border: "1px solid var(--border-subtle)",
                background: "white",
                color: "var(--text-primary)",
                outline: "none",
              }}
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery("")}
                style={{
                  position: "absolute",
                  right: 8,
                  top: "50%",
                  transform: "translateY(-50%)",
                  background: "transparent",
                  border: "none",
                  cursor: "pointer",
                  color: "var(--text-muted)",
                  padding: 0,
                  display: "flex",
                }}
              >
                <X size={13} />
              </button>
            )}
          </div>
        </div>

        {/* Row 2: Ticker / Holding Pills Filter */}
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <div style={{ fontSize: "0.75rem", fontWeight: 600, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.03em" }}>
            Filter by Ticker / Fund
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6, alignItems: "center" }}>
            {/* All Tickers Chip */}
            <button
              onClick={() => setSelectedTicker("ALL")}
              style={{
                fontSize: "0.75rem",
                fontWeight: selectedTicker === "ALL" ? 700 : 500,
                padding: "3px 10px",
                borderRadius: 9999,
                border: selectedTicker === "ALL" ? "1px solid #2563eb" : "1px solid var(--border-subtle)",
                background: selectedTicker === "ALL" ? "#2563eb" : "white",
                color: selectedTicker === "ALL" ? "#ffffff" : "var(--text-secondary)",
                cursor: "pointer",
                transition: "all 0.15s ease",
              }}
            >
              All Tickers ({visibleTickers.reduce((acc, t) => acc + t.count, 0)})
            </button>

            {/* Individual Ticker Chips */}
            {visibleTickers.map((t) => {
              const isSelected = selectedTicker === t.symbol;
              const isFund = t.kind === "fund";

              return (
                <button
                  key={t.symbol}
                  onClick={() => setSelectedTicker(isSelected ? "ALL" : t.symbol)}
                  title={isFund ? `Mutual Fund: ${t.symbol}` : `Stock: ${t.symbol}`}
                  style={{
                    fontSize: "0.75rem",
                    fontWeight: isSelected ? 700 : 500,
                    padding: "3px 10px",
                    borderRadius: 9999,
                    border: isSelected
                      ? isFund
                        ? "1px solid #d97706"
                        : "1px solid #2563eb"
                      : "1px solid var(--border-subtle)",
                    background: isSelected
                      ? isFund
                        ? "#d97706"
                        : "#2563eb"
                      : isFund
                      ? "#fffdf5"
                      : "white",
                    color: isSelected
                      ? "#ffffff"
                      : "var(--text-primary)",
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    gap: 5,
                    fontFamily: isFund ? "inherit" : "var(--font-mono)",
                    transition: "all 0.15s ease",
                  }}
                >
                  {isFund && (
                    <span
                      style={{
                        fontSize: "0.65rem",
                        padding: "0 4px",
                        borderRadius: 3,
                        background: isSelected ? "rgba(255,255,255,0.25)" : "#fef3c7",
                        color: isSelected ? "#ffffff" : "#92400e",
                        fontWeight: 700,
                      }}
                    >
                      MF
                    </span>
                  )}
                  <span>{t.symbol}</span>
                  <span
                    style={{
                      fontSize: "0.7rem",
                      opacity: isSelected ? 0.9 : 0.6,
                      background: isSelected ? "rgba(255,255,255,0.2)" : "#f1f5f9",
                      color: isSelected ? "#ffffff" : "var(--text-secondary)",
                      padding: "0 5px",
                      borderRadius: 9999,
                    }}
                  >
                    {t.count}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Row 3: Active Filter Status */}
        {hasActiveFilter && (
          <div
            style={{
              paddingTop: 8,
              borderTop: "1px solid var(--border-subtle)",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              fontSize: "0.78rem",
              color: "var(--text-secondary)",
            }}
          >
            <div>
              Showing <strong>{filteredArticles.length}</strong> of {newsArticles.length} items
              {selectedType !== "ALL" && (
                <span>
                  {" "}in <strong>{selectedType === "equity" ? "Stocks" : "Mutual Funds"}</strong>
                </span>
              )}
              {selectedTicker !== "ALL" && (
                <span>
                  {" "}for <strong>{selectedTicker}</strong>
                </span>
              )}
              {searchQuery && (
                <span>
                  {" "}matching &ldquo;<strong>{searchQuery}</strong>&rdquo;
                </span>
              )}
            </div>
            <button
              onClick={clearAllFilters}
              style={{
                background: "transparent",
                border: "none",
                color: "#2563eb",
                cursor: "pointer",
                fontWeight: 600,
                fontSize: "0.78rem",
                display: "flex",
                alignItems: "center",
                gap: 4,
                padding: "2px 6px",
              }}
            >
              <X size={12} /> Clear all filters
            </button>
          </div>
        )}
      </div>

      {/* News Articles Feed */}
      {filteredArticles.length === 0 ? (
        <div
          className="glass-panel"
          style={{
            textAlign: "center",
            padding: "36px 16px",
            color: "var(--text-muted)",
          }}
        >
          {newsLoading ? (
            "Fetching disclosures..."
          ) : hasActiveFilter ? (
            <div>
              <p style={{ margin: "0 0 10px", fontSize: "0.95rem" }}>
                No news found matching your current filter.
              </p>
              <button className="secondary-button" onClick={clearAllFilters}>
                Reset Filters
              </button>
            </div>
          ) : (
            "No adverse news or filings detected for your holdings."
          )}
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {filteredArticles.map((art, idx) => {
            const isFund = art.kind === "fund";
            const isBullish = art.impact === "BULLISH";
            const isBearish = art.impact === "BEARISH";

            return (
              <div key={idx} className="glass-panel" style={{ padding: "14px 18px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                  <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                    {/* Symbol Badge */}
                    <span
                      style={{
                        fontSize: "0.75rem",
                        fontWeight: 700,
                        padding: "2px 8px",
                        borderRadius: 4,
                        background: isFund ? "#fffdf5" : "#f1f5f9",
                        color: isFund ? "#92400e" : "#0f172a",
                        border: isFund ? "1px solid #fde68a" : "1px solid var(--border-subtle)",
                        fontFamily: isFund ? "inherit" : "var(--font-mono)",
                      }}
                    >
                      {art.symbol}
                    </span>

                    {/* Asset Type Badge for Mutual Funds */}
                    {isFund && (
                      <span
                        style={{
                          fontSize: "0.7rem",
                          fontWeight: 600,
                          padding: "1px 6px",
                          borderRadius: 4,
                          background: "#fef3c7",
                          color: "#92400e",
                          border: "1px solid #fde68a",
                        }}
                      >
                        Mutual Fund
                      </span>
                    )}

                    {/* Taxonomy Tag Badge */}
                    <span
                      style={{
                        fontSize: "0.75rem",
                        color: "#2563eb",
                        background: "#eff6ff",
                        border: "1px solid #bfdbfe",
                        padding: "1px 6px",
                        borderRadius: 4,
                        fontWeight: 500,
                      }}
                    >
                      {art.tag}
                    </span>
                  </div>

                  {/* Impact Sentiment Label */}
                  <span
                    style={{
                      fontSize: "0.8rem",
                      fontWeight: 600,
                      color: isBullish
                        ? "var(--color-buy)"
                        : isBearish
                        ? "var(--color-sell)"
                        : "var(--text-secondary)",
                    }}
                  >
                    {art.impact_label}
                  </span>
                </div>

                {/* Article Headline */}
                <a
                  href={art.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{
                    color: "var(--text-primary)",
                    fontWeight: 600,
                    fontSize: "0.92rem",
                    textDecoration: "none",
                    lineHeight: 1.45,
                    display: "inline-block",
                  }}
                >
                  {art.title} ↗
                </a>

                {/* Source & Timestamp */}
                <div style={{ color: "var(--text-muted)", fontSize: "0.75rem", marginTop: 4 }}>
                  {art.source} · {art.published_at}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
