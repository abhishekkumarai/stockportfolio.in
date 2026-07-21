"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { apiUrl } from "@/lib/api";

interface TickerSuggestion {
  symbol: string;
  name: string;
  exchange: string;
}

export default function HomePage() {
  const router = useRouter();
  const [searchQuery, setSearchQuery] = useState("");
  const [suggestions, setSuggestions] = useState<TickerSuggestion[]>([]);
  const [loadingSuggestions, setLoadingSuggestions] = useState(false);
  const [showDropdown, setShowDropdown] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setShowDropdown(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Fetch ticker search recommendations when query changes
  useEffect(() => {
    if (searchQuery.trim().length === 0) {
      setSuggestions([]);
      setShowDropdown(false);
      return;
    }

    const timer = setTimeout(async () => {
      setLoadingSuggestions(true);
      try {
        const response = await fetch(apiUrl(`/api/stocks/search?q=${encodeURIComponent(searchQuery)}`));
        if (response.ok) {
          const data = await response.json();
          setSuggestions(data);
          setShowDropdown(true);
        }
      } catch (err) {
        console.error("Error searching stock tickers:", err);
      } finally {
        setLoadingSuggestions(false);
      }
    }, 300); // 300ms debounce

    return () => clearTimeout(timer);
  }, [searchQuery]);

  const handleSelectTicker = (symbol: string) => {
    // Strip .NS or .BO suffix from symbol before routing
    const cleanSymbol = symbol.replace(/\.(NS|BO)$/i, "");
    router.push(`/analyse/${cleanSymbol}`);
  };

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.trim().length > 0) {
      if (suggestions.length > 0) {
        handleSelectTicker(suggestions[0].symbol);
      } else {
        handleSelectTicker(searchQuery.toUpperCase().trim());
      }
    }
  };

  // Static/Simulated Market Indices
  const marketIndices = [
    { name: "NIFTY 50", value: "23,465.60", change: "+148.95", pct: "+0.64%", up: true },
    { name: "SENSEX", value: "76,992.77", change: "+181.84", pct: "+0.24%", up: true },
    { name: "NIFTY BANK", value: "50,002.30", change: "-124.50", pct: "-0.25%", up: false },
    { name: "NIFTY IT", value: "35,124.95", change: "+345.10", pct: "+0.99%", up: true }
  ];

  // Quick Action Tickers
  const trendingStocks = [
    { symbol: "RELIANCE", name: "Reliance Industries", desc: "Oil & Gas, Telecom, Retail" },
    { symbol: "TCS", name: "Tata Consultancy Services", desc: "IT Consulting Services" },
    { symbol: "INFY", name: "Infosys Limited", desc: "IT and Business Consulting" },
    { symbol: "TATAMOTORS", name: "Tata Motors", desc: "Automobile & Electric Vehicles" },
    { symbol: "HDFCBANK", name: "HDFC Bank", desc: "Banking & Financial Services" },
    { symbol: "SBIN", name: "State Bank of India", desc: "Public Sector Banking" }
  ];

  return (
    <div className="app-container animate-fade-in">
      <section style={{ textAlign: "center", margin: "60px 0", display: "flex", flexDirection: "column", gap: "20px", alignItems: "center" }}>
        <h1 style={{ fontSize: "3.2rem", fontWeight: 800, lineHeight: 1.1, maxWidth: "800px" }}>
          stockportfolio.in | <span style={{ color: "var(--accent-cyan)", textShadow: "0 0 20px var(--accent-cyan-glow)" }}>Stock Sentiment Analyzer</span>
        </h1>
        <p style={{ fontSize: "1.2rem", maxWidth: "600px", margin: "0 auto" }}>
          Instantly evaluate if NSE/BSE stocks are overbought or underbought by cross-referencing real-time price technicals (RSI/SMA) with live web-scraped news sentiment.
        </p>
      </section>

      {/* Market Indices Strip */}
      <div className="metrics-grid" style={{ marginBottom: "50px" }}>
        {marketIndices.map((index) => (
          <div key={index.name} className="glass-panel metric-card" style={{ padding: "18px 22px" }}>
            <div className="title" style={{ fontSize: "0.75rem", fontWeight: 600 }}>{index.name}</div>
            <div className="value" style={{ fontSize: "1.4rem", margin: "4px 0" }}>{index.value}</div>
            <div className={`change ${index.up ? "up" : "down"}`}>
              {index.change} ({index.pct})
            </div>
          </div>
        ))}
      </div>

      {/* Main Search Bar Card */}
      <div className="glass-panel-cyan" style={{ padding: "40px", maxWidth: "800px", margin: "0 auto 60px auto", position: "relative" }}>
        <h3 style={{ fontSize: "1.3rem", fontWeight: 600, marginBottom: "15px" }}>Analyse Stock Ticker</h3>
        
        <form onSubmit={handleSearchSubmit}>
          <div className="search-input-wrapper" ref={dropdownRef}>
            <span style={{
              position: "absolute",
              left: "18px",
              top: "50%",
              transform: "translateY(-50%)",
              color: "var(--text-muted)",
              fontSize: "1.2rem"
            }}>
              🔍
            </span>
            <input
              type="text"
              className="search-input"
              placeholder="Search by stock symbol or name (e.g. RELIANCE, TCS, INFY...)"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onFocus={() => searchQuery.trim().length > 0 && setShowDropdown(true)}
            />

            {/* Autocomplete Dropdown */}
            {showDropdown && (
              <div className="glass-panel" style={{
                position: "absolute",
                top: "100%",
                left: 0,
                right: 0,
                marginTop: "8px",
                zIndex: 50,
                maxHeight: "300px",
                overflowY: "auto",
                borderRadius: "12px",
                padding: "8px",
                border: "1px solid var(--border-glow)",
                boxShadow: "0 10px 30px rgba(0,0,0,0.5)",
                background: "var(--bg-secondary)"
              }}>
                {loadingSuggestions ? (
                  <div style={{ padding: "12px", textAlign: "center", color: "var(--text-secondary)" }}>
                    Searching tickers...
                  </div>
                ) : suggestions.length === 0 ? (
                  <div style={{ padding: "12px", textAlign: "center", color: "var(--text-secondary)" }}>
                    No exact match. Press Enter to search custom ticker.
                  </div>
                ) : (
                  suggestions.map((item) => (
                    <div
                      key={item.symbol}
                      onClick={() => handleSelectTicker(item.symbol)}
                      style={{
                        padding: "12px 16px",
                        cursor: "pointer",
                        borderRadius: "8px",
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        transition: "var(--transition-smooth)"
                      }}
                      onMouseEnter={(e) => e.currentTarget.style.backgroundColor = "rgba(255, 255, 255, 0.05)"}
                      onMouseLeave={(e) => e.currentTarget.style.backgroundColor = "transparent"}
                    >
                      <div>
                        <div style={{ fontWeight: 600, color: "#fff" }}>{item.symbol.replace(/\.(NS|BO)$/i, "")}</div>
                        <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>{item.name}</div>
                      </div>
                      <span style={{
                        fontSize: "0.75rem",
                        fontWeight: 700,
                        padding: "4px 8px",
                        borderRadius: "4px",
                        background: "rgba(255, 255, 255, 0.08)",
                        color: "var(--text-primary)"
                      }}>
                        {item.exchange}
                      </span>
                    </div>
                  ))
                )}
              </div>
            )}
          </div>
        </form>
        <div style={{ marginTop: "15px", fontSize: "0.85rem", color: "var(--text-secondary)", display: "flex", gap: "6px" }}>
          <span>Tip:</span>
          <span>To analyze any stock, just input its symbol (like <strong>RELIANCE</strong> or <strong>TCS</strong>). stockportfolio.in automatically resolves exchange suffixes.</span>
        </div>
      </div>

      {/* Quick Access Section */}
      <section style={{ maxWidth: "1000px", margin: "0 auto" }}>
        <h3 style={{ fontSize: "1.4rem", fontWeight: 700, marginBottom: "20px", display: "flex", alignItems: "center", gap: "8px" }}>
          ⚡ Popular Indian Stocks
        </h3>
        <div style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))",
          gap: "20px"
        }}>
          {trendingStocks.map((stock) => (
            <div
              key={stock.symbol}
              className="glass-panel"
              style={{
                padding: "24px",
                cursor: "pointer",
                display: "flex",
                flexDirection: "column",
                justifyContent: "space-between",
                gap: "12px"
              }}
              onClick={() => handleSelectTicker(stock.symbol)}
            >
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "4px" }}>
                  <h4 style={{ fontSize: "1.2rem", fontWeight: 700 }}>{stock.symbol}</h4>
                  <span style={{ fontSize: "0.75rem", color: "var(--accent-cyan)", fontWeight: 600 }}>NSE</span>
                </div>
                <h5 style={{ fontSize: "0.95rem", color: "#fff", fontWeight: 500 }}>{stock.name}</h5>
                <p style={{ fontSize: "0.85rem", marginTop: "8px" }}>{stock.desc}</p>
              </div>
              <div style={{
                color: "var(--accent-cyan)",
                fontSize: "0.85rem",
                fontWeight: 600,
                alignSelf: "flex-end",
                display: "flex",
                alignItems: "center",
                gap: "4px"
              }}>
                Analyze Stock →
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
