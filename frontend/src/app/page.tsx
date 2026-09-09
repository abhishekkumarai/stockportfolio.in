"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  TrendingUp,
  TrendingDown,
  ShieldAlert,
  Scale,
  Radar,
  Compass,
  Zap,
  FlaskConical,
  Target,
  Radio,
  Search,
  ArrowUpRight,
  Sparkles,
  ExternalLink,
  ChevronRight,
  PieChart,
  Layers,
  Activity,
} from "lucide-react";
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
  const [activeTableTab, setActiveTableTab] = useState<"all" | "alpha" | "breakouts" | "tax">("all");
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

  // Fetch ticker search suggestions
  useEffect(() => {
    if (searchQuery.trim().length === 0) {
      setSuggestions([]);
      setShowDropdown(false);
      return;
    }

    const timer = setTimeout(async () => {
      setLoadingSuggestions(true);
      try {
        const response = await fetch(
          apiUrl(`/api/stocks/search?q=${encodeURIComponent(searchQuery)}`)
        );
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
    }, 250);

    return () => clearTimeout(timer);
  }, [searchQuery]);

  const handleSelectTicker = (symbol: string) => {
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

  // Sample institutional stock data for the high-density trading table
  const institutionalStocks = [
    {
      symbol: "RELIANCE",
      name: "Reliance Industries",
      sector: "Energy & Telecom",
      cmp: "₹2,985.40",
      change: "+1.2%",
      up: true,
      weight: "14.2%",
      piotroski: "8/9",
      decile: "Decile 1 (Top 10%)",
      target: "₹3,180",
      stop: "₹2,880",
      category: "alpha",
    },
    {
      symbol: "HDFCBANK",
      name: "HDFC Bank",
      sector: "Private Banking",
      cmp: "₹1,642.10",
      change: "+0.5%",
      up: true,
      weight: "12.8%",
      piotroski: "7/9",
      decile: "Decile 2",
      target: "₹1,760",
      stop: "₹1,590",
      category: "all",
    },
    {
      symbol: "TATAMOTORS",
      name: "Tata Motors",
      sector: "Auto / Commercial",
      cmp: "₹978.50",
      change: "+2.4%",
      up: true,
      weight: "9.5%",
      piotroski: "9/9",
      decile: "Decile 1 (Top 10%)",
      target: "₹1,060",
      stop: "₹935",
      category: "breakouts",
    },
    {
      symbol: "INFY",
      name: "Infosys",
      sector: "IT Services (FX Tailwind)",
      cmp: "₹1,820.00",
      change: "-0.3%",
      up: false,
      weight: "8.4%",
      piotroski: "8/9",
      decile: "Decile 2",
      target: "₹1,950",
      stop: "₹1,760",
      category: "tax",
    },
    {
      symbol: "TITAN",
      name: "Titan Company",
      sector: "Consumer Discretionary",
      cmp: "₹3,410.20",
      change: "+1.8%",
      up: true,
      weight: "7.1%",
      piotroski: "8/9",
      decile: "Decile 1 (Top 10%)",
      target: "₹3,680",
      stop: "₹3,280",
      category: "alpha",
    },
    {
      symbol: "SUNPHARMA",
      name: "Sun Pharmaceutical",
      sector: "Healthcare / Export",
      cmp: "₹1,680.40",
      change: "+1.1%",
      up: true,
      weight: "6.2%",
      piotroski: "8/9",
      decile: "Decile 1 (Top 10%)",
      target: "₹1,810",
      stop: "₹1,610",
      category: "alpha",
    },
  ];

  const filteredStocks = institutionalStocks.filter((s) => {
    if (activeTableTab === "all") return true;
    if (activeTableTab === "alpha") return s.decile.includes("Decile 1");
    if (activeTableTab === "breakouts") return s.category === "breakouts" || s.up;
    if (activeTableTab === "tax") return s.category === "tax" || !s.up;
    return true;
  });

  return (
    <div className="mx-auto max-w-[1400px] p-6 space-y-6 animate-fade-in">
      {/* Viewport Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between border-b border-slate-200 pb-5">
        <div>
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center rounded-md bg-blue-50 px-2 py-0.5 font-mono text-[10px] font-bold uppercase tracking-wide text-blue-700">
              Institutional Console
            </span>
            <span className="font-mono text-xs text-slate-400">Phase 14 Pro</span>
          </div>
          <h1 className="mt-1 text-2xl font-bold tracking-tight text-slate-900">
            Portfolio Intelligence & Quant Alpha Console
          </h1>
          <p className="mt-0.5 text-xs text-slate-500">
            Real-time holdings tracking, quant risk decomposition, and walk-forward ML factor alpha for Indian equities.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <Link
            href="/portfolio?tab=rebalance"
            className="inline-flex items-center gap-1.5 rounded-md bg-blue-600 px-3.5 py-2 text-xs font-semibold text-white shadow-sm transition hover:bg-blue-700"
          >
            <Scale size={14} /> Tax-Aware Rebalance
          </Link>
          <Link
            href="/portfolio"
            className="inline-flex items-center gap-1.5 rounded-md border border-slate-200 bg-white px-3.5 py-2 text-xs font-semibold text-slate-700 shadow-sm transition hover:bg-slate-50"
          >
            <PieChart size={14} /> My Portfolio
          </Link>
        </div>
      </div>

      {/* Top 4 KPI Executive Metric Tiles */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {/* Tile 1: Valuation & P&L */}
        <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-[0_1px_2px_0_rgba(15,23,42,0.04)]">
          <div className="flex items-center justify-between">
            <span className="font-mono text-[10px] font-bold uppercase tracking-wider text-slate-500">
              PORTFOLIO NET WORTH
            </span>
            <span className="rounded-full bg-emerald-50 px-2 py-0.5 font-mono text-[10px] font-bold text-emerald-700">
              +0.80% DAY
            </span>
          </div>
          <div className="mt-2 text-2xl font-bold tracking-tight text-slate-900 font-mono">
            ₹48,25,400
          </div>
          <div className="mt-2 flex items-center justify-between text-xs text-slate-500">
            <span>Day P&L: <strong className="font-mono text-emerald-600 font-semibold">+₹38,420</strong></span>
            <span className="font-mono">Beta: 0.88</span>
          </div>
        </div>

        {/* Tile 2: Health Score & Distress */}
        <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-[0_1px_2px_0_rgba(15,23,42,0.04)]">
          <div className="flex items-center justify-between">
            <span className="font-mono text-[10px] font-bold uppercase tracking-wider text-slate-500">
              QUANT HEALTH SCORE
            </span>
            <span className="rounded-full bg-blue-50 px-2 py-0.5 font-mono text-[10px] font-bold text-blue-700">
              PRISTINE
            </span>
          </div>
          <div className="mt-2 text-2xl font-bold tracking-tight text-slate-900 font-mono">
            8.6 <span className="text-sm font-normal text-slate-400">/ 10</span>
          </div>
          <div className="mt-2 flex items-center justify-between text-xs text-slate-500">
            <span>Piotroski Avg: <strong className="font-mono text-slate-800">7.8 / 9</strong></span>
            <span className="font-mono text-emerald-600 font-semibold">0 Warnings</span>
          </div>
        </div>

        {/* Tile 3: 1-Day 95% Parametric VaR */}
        <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-[0_1px_2px_0_rgba(15,23,42,0.04)]">
          <div className="flex items-center justify-between">
            <span className="font-mono text-[10px] font-bold uppercase tracking-wider text-slate-500">
              1-DAY 95% VALUE AT RISK
            </span>
            <span className="rounded-full bg-slate-100 px-2 py-0.5 font-mono text-[10px] font-bold text-slate-600">
              PARAMETRIC
            </span>
          </div>
          <div className="mt-2 text-2xl font-bold tracking-tight text-slate-900 font-mono">
            -1.42% <span className="text-xs font-normal text-slate-500">(₹68,520)</span>
          </div>
          <div className="mt-2 flex items-center justify-between text-xs text-slate-500">
            <span>Tail CVaR: <strong className="font-mono text-red-600 font-semibold">-2.10%</strong></span>
            <span className="font-mono">HHI: 0.11</span>
          </div>
        </div>

        {/* Tile 4: Active Macro Regime */}
        <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-[0_1px_2px_0_rgba(15,23,42,0.04)]">
          <div className="flex items-center justify-between">
            <span className="font-mono text-[10px] font-bold uppercase tracking-wider text-slate-500">
              MACRO REGIME RADAR
            </span>
            <span className="rounded-full bg-emerald-50 px-2 py-0.5 font-mono text-[10px] font-bold text-emerald-700">
              GOLDILOCKS
            </span>
          </div>
          <div className="mt-2 text-xl font-bold tracking-tight text-slate-900">
            Goldilocks Expansion
          </div>
          <div className="mt-2 flex items-center justify-between text-xs text-slate-500">
            <span>Brent: <strong className="font-mono text-slate-800">$74 Benign</strong></span>
            <span className="font-semibold text-blue-600">IT/Pharma Tailwinds</span>
          </div>
        </div>
      </div>

      {/* Main Analysis Workstation (Split 70% Left / 30% Right) */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        {/* Left Column: High-Density Institutional Stock Table (8 cols) */}
        <div className="lg:col-span-8 rounded-lg border border-slate-200 bg-white shadow-[0_1px_2px_0_rgba(15,23,42,0.04)] overflow-hidden">
          {/* Table Header & Segmented Tabs */}
          <div className="border-b border-slate-200 px-5 py-3.5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between bg-slate-50/50">
            <div className="flex items-center gap-1 rounded-md border border-slate-200 bg-slate-100 p-0.5 text-xs font-semibold text-slate-600">
              <button
                onClick={() => setActiveTableTab("all")}
                className={`rounded px-3 py-1 transition ${
                  activeTableTab === "all" ? "bg-white text-blue-700 shadow-sm" : "hover:text-slate-900"
                }`}
              >
                All Positions (18)
              </button>
              <button
                onClick={() => setActiveTableTab("alpha")}
                className={`rounded px-3 py-1 transition ${
                  activeTableTab === "alpha" ? "bg-white text-blue-700 shadow-sm" : "hover:text-slate-900"
                }`}
              >
                ML Decile 1 Buys (10)
              </button>
              <button
                onClick={() => setActiveTableTab("breakouts")}
                className={`rounded px-3 py-1 transition ${
                  activeTableTab === "breakouts" ? "bg-white text-blue-700 shadow-sm" : "hover:text-slate-900"
                }`}
              >
                Volume Shockers (6)
              </button>
              <button
                onClick={() => setActiveTableTab("tax")}
                className={`rounded px-3 py-1 transition ${
                  activeTableTab === "tax" ? "bg-white text-blue-700 shadow-sm" : "hover:text-slate-900"
                }`}
              >
                Tax Batches (3)
              </button>
            </div>

            <Link
              href="/recommendations"
              className="inline-flex items-center gap-1 text-xs font-semibold text-blue-600 hover:text-blue-700"
            >
              Full Factor Matrix <ArrowUpRight size={13} />
            </Link>
          </div>

          {/* Table */}
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-left text-xs">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50/75 font-mono text-[10px] uppercase tracking-wider text-slate-500">
                  <th className="px-4 py-2.5 font-semibold">TICKER & SECTOR</th>
                  <th className="px-3 py-2.5 font-semibold text-right">CMP (₹)</th>
                  <th className="px-3 py-2.5 font-semibold text-right">24H</th>
                  <th className="px-3 py-2.5 font-semibold text-right">WEIGHT</th>
                  <th className="px-3 py-2.5 font-semibold text-center">PIOTROSKI</th>
                  <th className="px-3 py-2.5 font-semibold">ML ALPHA DECILE</th>
                  <th className="px-3 py-2.5 font-semibold">TARGET (+2σ / -1.5σ)</th>
                  <th className="px-4 py-2.5 font-semibold text-right">ACTIONS</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filteredStocks.map((stock) => (
                  <tr key={stock.symbol} className="transition hover:bg-slate-50/80">
                    <td className="px-4 py-3">
                      <div className="font-bold text-slate-900 font-mono">{stock.symbol}</div>
                      <div className="text-[11px] text-slate-500">{stock.sector}</div>
                    </td>
                    <td className="px-3 py-3 text-right font-mono font-semibold text-slate-900">
                      {stock.cmp}
                    </td>
                    <td
                      className={`px-3 py-3 text-right font-mono font-semibold ${
                        stock.up ? "text-emerald-600" : "text-red-600"
                      }`}
                    >
                      {stock.change}
                    </td>
                    <td className="px-3 py-3 text-right font-mono text-slate-700">
                      {stock.weight}
                    </td>
                    <td className="px-3 py-3 text-center">
                      <span className="inline-block rounded bg-slate-100 px-2 py-0.5 font-mono text-[10px] font-bold text-slate-700">
                        {stock.piotroski}
                      </span>
                    </td>
                    <td className="px-3 py-3">
                      <span
                        className={`inline-flex items-center rounded-full px-2 py-0.5 font-mono text-[10px] font-bold ${
                          stock.decile.includes("Decile 1")
                            ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                            : "bg-blue-50 text-blue-700 border border-blue-200"
                        }`}
                      >
                        {stock.decile}
                      </span>
                    </td>
                    <td className="px-3 py-3 font-mono text-[11px] text-slate-600">
                      <span className="text-emerald-700">{stock.target}</span> /{" "}
                      <span className="text-red-600">{stock.stop}</span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        <button
                          onClick={() => handleSelectTicker(stock.symbol)}
                          className="rounded border border-slate-200 px-2 py-1 text-[11px] font-semibold text-slate-700 transition hover:bg-slate-100"
                        >
                          Inspect
                        </button>
                        <Link
                          href={`/paper?action=BUY&symbol=${stock.symbol}`}
                          className="rounded bg-blue-50 px-2 py-1 text-[11px] font-semibold text-blue-700 transition hover:bg-blue-100"
                        >
                          Trade
                        </Link>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="border-t border-slate-200 px-5 py-3 flex items-center justify-between text-xs text-slate-500 bg-slate-50/50">
            <span>Showing {filteredStocks.length} monitored assets</span>
            <Link href="/screener" className="text-blue-600 hover:underline font-medium">
              Open 500-Stock Screener →
            </Link>
          </div>
        </div>

        {/* Right Column: Quantitative Intelligence & Risk Widgets (4 cols) */}
        <div className="lg:col-span-4 space-y-4">
          {/* Widget 1: 1,000-Path Monte Carlo Wealth Cone */}
          <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-[0_1px_2px_0_rgba(15,23,42,0.04)]">
            <div className="flex items-center justify-between border-b border-slate-100 pb-2.5">
              <div>
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-800">
                  1,000-Path Monte Carlo Cone
                </h3>
                <p className="text-[11px] text-slate-500">3-Year Probabilistic Wealth Trajectory</p>
              </div>
              <span className="font-mono text-[10px] font-bold text-blue-600 bg-blue-50 px-2 py-0.5 rounded">
                1,000 Paths
              </span>
            </div>

            {/* SVG Cone Chart */}
            <div className="mt-3">
              <svg className="w-full h-28" viewBox="0 0 300 110" fill="none">
                {/* 90th percentile area */}
                <path
                  d="M 10 70 C 80 65, 180 30, 290 15 L 290 95 C 180 85, 80 75, 10 70 Z"
                  fill="#EFF6FF"
                  opacity="0.8"
                />
                {/* 50th percentile area */}
                <path
                  d="M 10 70 C 80 68, 180 50, 290 45 L 290 85 C 180 80, 80 72, 10 70 Z"
                  fill="#DBEAFE"
                  opacity="0.9"
                />
                {/* Baseline path */}
                <path d="M 10 70 C 80 68, 180 50, 290 45" stroke="#2563EB" strokeWidth="2" />
                {/* Bearish 10th path */}
                <path d="M 10 70 C 80 72, 180 80, 290 95" stroke="#94A3B8" strokeWidth="1.5" strokeDasharray="3 3" />
                {/* Bullish 90th path */}
                <path d="M 10 70 C 80 65, 180 30, 290 15" stroke="#059669" strokeWidth="1.5" />
              </svg>
            </div>

            <div className="mt-2 grid grid-cols-3 gap-2 border-t border-slate-100 pt-2 text-center">
              <div>
                <div className="text-[10px] text-slate-400 uppercase font-mono">10th Stress</div>
                <div className="text-xs font-bold font-mono text-slate-700">₹58.2 L</div>
              </div>
              <div>
                <div className="text-[10px] text-slate-400 uppercase font-mono">50th Median</div>
                <div className="text-xs font-bold font-mono text-blue-600">₹84.6 L</div>
              </div>
              <div>
                <div className="text-[10px] text-slate-400 uppercase font-mono">90th Bull</div>
                <div className="text-xs font-bold font-mono text-emerald-600">₹1.18 Cr</div>
              </div>
            </div>
          </div>

          {/* Widget 2: Macro Inter-Market Transmission Radar */}
          <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-[0_1px_2px_0_rgba(15,23,42,0.04)]">
            <div className="flex items-center justify-between border-b border-slate-100 pb-2.5">
              <div>
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-800">
                  Inter-Market Transmission
                </h3>
                <p className="text-[11px] text-slate-500">Global Pressure on Indian Equities</p>
              </div>
              <Link href="/macro" className="text-[11px] font-semibold text-blue-600 hover:underline">
                View Radar →
              </Link>
            </div>

            <div className="mt-3 space-y-2.5 text-xs">
              <div className="flex items-center justify-between">
                <span className="text-slate-600">Crude Pressure Index:</span>
                <span className="font-mono font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded">
                  Benign (32 / 100)
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-600">FX Rupee Velocity (20D):</span>
                <span className="font-mono font-bold text-slate-800">
                  +0.12% (Neutral)
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-600">Favored Sector Alpha:</span>
                <div className="flex gap-1 font-mono text-[10px]">
                  <span className="bg-emerald-50 text-emerald-700 font-bold px-1.5 py-0.5 rounded">
                    IT (+1.8%)
                  </span>
                  <span className="bg-emerald-50 text-emerald-700 font-bold px-1.5 py-0.5 rounded">
                    Pharma (+0.9%)
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Widget 3: Investment Committee Memo */}
          <div className="rounded-lg border-l-4 border-l-blue-600 border border-slate-200 bg-slate-50/60 p-4 shadow-[0_1px_2px_0_rgba(15,23,42,0.04)]">
            <div className="flex items-center gap-1.5 text-blue-700">
              <Sparkles size={14} />
              <span className="font-mono text-[11px] font-bold uppercase tracking-wider">
                Monthly Shareholder Memo
              </span>
            </div>
            <p className="mt-2 text-xs leading-relaxed text-slate-700">
              Portfolio generated <strong>340 bps excess alpha</strong> over NIFTY 50 this quarter. The rebalancing engine recommends trimming 2.1% Private Banking into IT/Pharma export tailwinds with <strong>₹0 capital gains tax liability</strong> via LTCG annual allowance.
            </p>
            <div className="mt-3">
              <Link
                href="/portfolio?tab=memo"
                className="inline-flex items-center gap-1 text-xs font-semibold text-blue-600 hover:text-blue-800"
              >
                Read Full Memorandum <ChevronRight size={13} />
              </Link>
            </div>
          </div>
        </div>
      </div>

      {/* Quick Launchpad to All Platform Modules */}
      <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-[0_1px_2px_0_rgba(15,23,42,0.04)]">
        <h2 className="text-sm font-bold uppercase tracking-wider text-slate-800 mb-3">
          Institutional Platform Modules
        </h2>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          <Link
            href="/pulse"
            className="group rounded-md border border-slate-200 p-3 transition hover:border-blue-300 hover:bg-blue-50/40"
          >
            <div className="flex items-center justify-between text-blue-600">
              <Radio size={16} />
              <ArrowUpRight size={12} className="opacity-0 group-hover:opacity-100 transition" />
            </div>
            <div className="mt-2 font-semibold text-xs text-slate-900">Live Market Pulse</div>
            <div className="text-[10px] text-slate-500">A/D Breadth & Shockers</div>
          </Link>

          <Link
            href="/recommendations"
            className="group rounded-md border border-slate-200 p-3 transition hover:border-blue-300 hover:bg-blue-50/40"
          >
            <div className="flex items-center justify-between text-blue-600">
              <Target size={16} />
              <ArrowUpRight size={12} className="opacity-0 group-hover:opacity-100 transition" />
            </div>
            <div className="mt-2 font-semibold text-xs text-slate-900">ML Alpha Radar</div>
            <div className="text-[10px] text-slate-500">Decile 1–10 Ranking</div>
          </Link>

          <Link
            href="/screener"
            className="group rounded-md border border-slate-200 p-3 transition hover:border-blue-300 hover:bg-blue-50/40"
          >
            <div className="flex items-center justify-between text-blue-600">
              <Search size={16} />
              <ArrowUpRight size={12} className="opacity-0 group-hover:opacity-100 transition" />
            </div>
            <div className="mt-2 font-semibold text-xs text-slate-900">500 Screener</div>
            <div className="text-[10px] text-slate-500">Forensic Ratio Filters</div>
          </Link>

          <Link
            href="/macro"
            className="group rounded-md border border-slate-200 p-3 transition hover:border-blue-300 hover:bg-blue-50/40"
          >
            <div className="flex items-center justify-between text-blue-600">
              <Compass size={16} />
              <ArrowUpRight size={12} className="opacity-0 group-hover:opacity-100 transition" />
            </div>
            <div className="mt-2 font-semibold text-xs text-slate-900">India Macro Radar</div>
            <div className="text-[10px] text-slate-500">Brent / FX / VIX Regimes</div>
          </Link>

          <Link
            href="/options"
            className="group rounded-md border border-slate-200 p-3 transition hover:border-blue-300 hover:bg-blue-50/40"
          >
            <div className="flex items-center justify-between text-blue-600">
              <Radar size={16} />
              <ArrowUpRight size={12} className="opacity-0 group-hover:opacity-100 transition" />
            </div>
            <div className="mt-2 font-semibold text-xs text-slate-900">Option Chain</div>
            <div className="text-[10px] text-slate-500">PCR, Max Pain & Walls</div>
          </Link>

          <Link
            href="/lab"
            className="group rounded-md border border-slate-200 p-3 transition hover:border-blue-300 hover:bg-blue-50/40"
          >
            <div className="flex items-center justify-between text-blue-600">
              <FlaskConical size={16} />
              <ArrowUpRight size={12} className="opacity-0 group-hover:opacity-100 transition" />
            </div>
            <div className="mt-2 font-semibold text-xs text-slate-900">Strategy Lab v2</div>
            <div className="text-[10px] text-slate-500">Walk-Forward Backtests</div>
          </Link>
        </div>
      </div>
    </div>
  );
}
