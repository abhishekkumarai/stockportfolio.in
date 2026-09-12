"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Search, TrendingUp, TrendingDown, BarChart2, Shield, ArrowUpRight, Award, Compass } from "lucide-react";
import { apiUrl } from "@/lib/api";

interface StockCard {
  symbol: string;
  name: string;
  sector: string;
  price: number;
  changePct: number;
  piotroski: number;
  pe: number;
  catalyst: string;
}

const FEATURED_STOCKS: StockCard[] = [
  {
    symbol: "RELIANCE",
    name: "Reliance Industries Ltd",
    sector: "Energy & Telecom",
    price: 2985.4,
    changePct: 1.42,
    piotroski: 8,
    pe: 27.8,
    catalyst: "Retail & Jio Demerger Structuring",
  },
  {
    symbol: "TCS",
    name: "Tata Consultancy Services",
    sector: "IT & Software",
    price: 4210.8,
    changePct: 0.85,
    piotroski: 9,
    pe: 31.4,
    catalyst: "$1.2B European Cloud & AI Transformation Deal",
  },
  {
    symbol: "HDFCBANK",
    name: "HDFC Bank Ltd",
    sector: "Banking & Financials",
    price: 1642.1,
    changePct: -0.32,
    piotroski: 7,
    pe: 18.9,
    catalyst: "NIM Expansion & Cost Synergy Acceleration",
  },
  {
    symbol: "INFY",
    name: "Infosys Ltd",
    sector: "IT & Software",
    price: 1890.3,
    changePct: 1.15,
    piotroski: 8,
    pe: 28.2,
    catalyst: "Enterprise Topaz Generative AI Pipeline",
  },
  {
    symbol: "ICICIBANK",
    name: "ICICI Bank Ltd",
    sector: "Banking & Financials",
    price: 1215.6,
    changePct: 1.78,
    piotroski: 9,
    pe: 17.5,
    catalyst: "Industry-leading 18% Credit Growth & Pristine Asset Quality",
  },
  {
    symbol: "TATAMOTORS",
    name: "Tata Motors Ltd",
    sector: "Automotive & EV",
    price: 986.5,
    changePct: 2.35,
    piotroski: 8,
    pe: 16.2,
    catalyst: "JLR Order Book Expansion & Commercial Vehicle Demerger",
  },
  {
    symbol: "LT",
    name: "Larsen & Toubro Ltd",
    sector: "Capital Goods & Infra",
    price: 3620.0,
    changePct: 0.94,
    piotroski: 8,
    pe: 32.1,
    catalyst: "Record ₹4.8 Lakh Crore Domestic & Middle East Order Backlog",
  },
  {
    symbol: "BHARTIARTL",
    name: "Bharti Airtel Ltd",
    sector: "Telecom",
    price: 1540.2,
    changePct: 1.62,
    piotroski: 7,
    pe: 42.0,
    catalyst: "Industry ARPU Expansion to ₹225 & 5G Monetisation",
  },
  {
    symbol: "ITC",
    name: "ITC Ltd",
    sector: "FMCG & Hotels",
    price: 492.8,
    changePct: -0.15,
    piotroski: 9,
    pe: 26.5,
    catalyst: "Hotels Business Demerger & Non-Cigarette FMCG Scale",
  },
  {
    symbol: "SBIN",
    name: "State Bank of India",
    sector: "PSU Banking",
    price: 812.4,
    changePct: 1.08,
    piotroski: 8,
    pe: 10.8,
    catalyst: "RoA expansion above 1.1% & robust corporate capex credit cycle",
  },
];

export default function EquityDeepDiveIndexPage() {
  const router = useRouter();
  const [search, setSearch] = useState("");
  const [suggestions, setSuggestions] = useState<Array<{ symbol: string; name: string; exchange: string }>>([]);
  const [selectedSector, setSelectedSector] = useState("all");

  useEffect(() => {
    if (!search.trim()) {
      setSuggestions([]);
      return;
    }
    const timer = setTimeout(async () => {
      try {
        const res = await fetch(apiUrl(`/api/stocks/search?q=${encodeURIComponent(search.trim())}`));
        if (res.ok) {
          const data = await res.json();
          setSuggestions(data.slice(0, 8));
        }
      } catch (err) {
        console.error(err);
      }
    }, 200);
    return () => clearTimeout(timer);
  }, [search]);

  const sectors = ["all", "IT & Software", "Banking & Financials", "Energy & Telecom", "Automotive & EV", "Capital Goods & Infra"];

  const filteredStocks = FEATURED_STOCKS.filter((s) => {
    const matchesSector = selectedSector === "all" || s.sector === selectedSector;
    const matchesSearch =
      !search ||
      s.symbol.toLowerCase().includes(search.toLowerCase()) ||
      s.name.toLowerCase().includes(search.toLowerCase());
    return matchesSector && matchesSearch;
  });

  const handleSelect = (sym: string) => {
    const clean = sym.replace(/\.(NS|BO)$/i, "");
    router.push(`/analyse/${clean}`);
  };

  return (
    <div className="app-container animate-fade-in">
      <div style={{ marginBottom: 28 }}>
        <div className="flex items-center gap-2 mb-2">
          <span className="px-2 py-0.5 text-[10px] font-mono font-bold bg-blue-50 text-blue-700 border border-blue-200 rounded uppercase">
            Institutional Research
          </span>
          <span className="text-xs text-slate-400 font-mono">500+ NSE Equities</span>
        </div>
        <h1 style={{ margin: 0, fontSize: "2rem", fontWeight: 800 }}>Equity Deep Dive Terminal</h1>
        <p style={{ color: "var(--text-secondary)", margin: "6px 0 0", maxWidth: 740 }}>
          Comprehensive fundamental & technical forensic diagnostic: Piotroski F-Score breakdown, Moving Average crossovers, Sentiment NLP radar, and Price History telemetry.
        </p>
      </div>

      {/* Universal Equity Search Bar */}
      <div className="glass-panel" style={{ padding: "20px 24px", marginBottom: 28 }}>
        <div style={{ position: "relative" }}>
          <div className="flex items-center gap-3">
            <Search size={18} className="text-slate-400 shrink-0" />
            <input
              type="text"
              placeholder="Search any Indian stock by ticker or company name (e.g., TCS, INFY, HDFCBANK, TATAMOTORS, RELIANCE)..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && search.trim()) {
                  if (suggestions.length > 0) {
                    handleSelect(suggestions[0].symbol);
                  } else {
                    handleSelect(search.trim().toUpperCase());
                  }
                }
              }}
              style={{
                width: "100%",
                background: "transparent",
                border: "none",
                outline: "none",
                fontSize: "1rem",
                color: "var(--text-primary)",
                fontFamily: "var(--font-sans)",
              }}
            />
          </div>

          {/* Autocomplete suggestions */}
          {suggestions.length > 0 && (
            <div
              style={{
                position: "absolute",
                top: "100%",
                left: 0,
                right: 0,
                marginTop: 12,
                background: "#ffffff",
                border: "1px solid var(--border-subtle)",
                borderRadius: 8,
                boxShadow: "0 10px 25px -5px rgba(0,0,0,0.1)",
                zIndex: 30,
                overflow: "hidden",
              }}
            >
              {suggestions.map((item) => (
                <div
                  key={item.symbol}
                  onClick={() => handleSelect(item.symbol)}
                  className="px-4 py-3 hover:bg-slate-50 cursor-pointer flex items-center justify-between border-b border-slate-100 last:border-0"
                >
                  <div className="flex items-center gap-2.5">
                    <span className="font-mono font-bold text-slate-900">{item.symbol}</span>
                    <span className="text-slate-500 text-xs truncate max-w-sm">{item.name}</span>
                  </div>
                  <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-blue-50 text-blue-700 font-semibold uppercase">
                    {item.exchange}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Quick Ticker Chips */}
        <div className="flex items-center gap-2 mt-4 pt-3 border-t border-slate-100 flex-wrap">
          <span className="text-xs text-slate-400 font-medium">Quick Launch:</span>
          {["RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "TATAMOTORS", "LT", "ITC", "BHARTIARTL", "SBIN"].map(
            (sym) => (
              <button
                key={sym}
                onClick={() => handleSelect(sym)}
                className="px-2.5 py-1 text-xs font-mono font-medium rounded-md bg-slate-100 hover:bg-blue-50 hover:text-blue-600 text-slate-700 transition"
              >
                {sym}
              </button>
            )
          )}
        </div>
      </div>

      {/* Sector filter pills */}
      <div className="flex items-center gap-2 mb-6 overflow-x-auto pb-1">
        {sectors.map((sec) => (
          <button
            key={sec}
            onClick={() => setSelectedSector(sec)}
            className={`px-3 py-1.5 rounded-full text-xs font-medium transition ${
              selectedSector === sec
                ? "bg-slate-900 text-white"
                : "bg-slate-100 text-slate-600 hover:bg-slate-200"
            }`}
          >
            {sec === "all" ? "All Sectors" : sec}
          </button>
        ))}
      </div>

      {/* Grid of stock cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {filteredStocks.map((stock) => (
          <Link
            key={stock.symbol}
            href={`/analyse/${stock.symbol}`}
            className="glass-panel p-5 block hover:border-blue-500 hover:shadow-md transition group text-decoration-none"
            style={{ textDecoration: "none" }}
          >
            <div className="flex items-start justify-between mb-2">
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-mono font-bold text-base text-slate-900 group-hover:text-blue-600 transition">
                    {stock.symbol}
                  </span>
                  <span className="text-[10px] font-mono px-1 rounded bg-slate-100 text-slate-500">NSE</span>
                </div>
                <div className="text-xs text-slate-500 truncate max-w-[200px] mt-0.5">{stock.name}</div>
              </div>
              <div className="text-right">
                <div className="font-mono font-bold text-slate-900 text-sm">
                  ₹{stock.price.toLocaleString("en-IN", { minimumFractionDigits: 1 })}
                </div>
                <div
                  className={`text-xs font-mono font-semibold flex items-center justify-end gap-0.5 ${
                    stock.changePct >= 0 ? "text-emerald-600" : "text-red-600"
                  }`}
                >
                  {stock.changePct >= 0 ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
                  {stock.changePct >= 0 ? `+${stock.changePct}%` : `${stock.changePct}%`}
                </div>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2 my-3 py-2 border-y border-slate-100 text-xs">
              <div>
                <span className="text-slate-400 block text-[11px]">Piotroski F-Score</span>
                <span className="font-mono font-bold text-slate-800">
                  {stock.piotroski} / 9{" "}
                  <span className="text-[10px] text-emerald-600 font-normal">
                    ({stock.piotroski >= 8 ? "Pristine" : "Strong"})
                  </span>
                </span>
              </div>
              <div>
                <span className="text-slate-400 block text-[11px]">Sector P/E</span>
                <span className="font-mono font-bold text-slate-800">{stock.pe}x</span>
              </div>
            </div>

            <div className="flex items-center justify-between text-xs pt-1">
              <span className="text-[11px] text-slate-500 truncate max-w-[220px]">
                {stock.catalyst}
              </span>
              <span className="text-blue-600 font-semibold group-hover:translate-x-0.5 transition flex items-center gap-0.5 text-xs">
                Inspect <ArrowUpRight size={14} />
              </span>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
