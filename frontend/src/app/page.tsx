"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  TrendingUp,
  TrendingDown,
  Shield,
  Scale,
  Radar,
  Zap,
  FlaskConical,
  Target,
  Search,
  ArrowUpRight,
  PieChart,
  Activity,
  CheckCircle2,
  AlertTriangle,
  Lock,
  RefreshCw,
  Download,
  Filter,
  X,
  ExternalLink,
  ChevronRight,
  Layers,
  Sparkles,
} from "lucide-react";
import { apiUrl } from "@/lib/api";

interface TickerSuggestion {
  symbol: string;
  name: string;
  exchange: string;
}

interface HoldingItem {
  symbol: string;
  name: string;
  sector: string;
  weight: number;
  qty: number;
  avgBuy: number;
  ltp: number;
  totalValue: number;
  unrealizedPnL: number;
  unrealizedPnLPct: number;
  varContrib: string;
  piotroski: number;
  piotroskiLabel: string;
  catalyst: string;
  status?: string;
  lockWarning?: string;
}

export default function ConsolidatedMasterWorkstation() {
  const router = useRouter();

  // Tab states
  const [activeVisualTab, setActiveVisualTab] = useState<"cone" | "lab" | "oi">("cone");
  const [activeTableTab, setActiveTableTab] = useState<"holdings" | "alpha" | "options" | "backtest">("holdings");
  const [selectedSector, setSelectedSector] = useState("all");
  const [tableSearch, setTableSearch] = useState("");

  // Modals & Execution States
  const [isRebalanceModalOpen, setIsRebalanceModalOpen] = useState(false);
  const [isExecutingBasket, setIsExecutingBasket] = useState(false);
  const [basketExecuted, setBasketExecuted] = useState(false);
  const [selectedForensicHolding, setSelectedForensicHolding] = useState<HoldingItem | null>(null);

  // Keyboard shortcut listener to dismiss modals on Escape
  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setIsRebalanceModalOpen(false);
        setSelectedForensicHolding(null);
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  // Portfolio Holdings Dataset (Aligned strictly with Master Console Spec)
  const holdings: HoldingItem[] = [
    {
      symbol: "RELIANCE",
      name: "Reliance Industries Ltd",
      sector: "Energy & Telecom",
      weight: 16.4,
      qty: 310,
      avgBuy: 2740.0,
      ltp: 2985.4,
      totalValue: 925474.0,
      unrealizedPnL: 76074.0,
      unrealizedPnLPct: 8.96,
      varContrib: "22% VaR",
      piotroski: 8,
      piotroskiLabel: "Strong",
      catalyst: "Retail Demerger H2 (+0.64α)",
    },
    {
      symbol: "TCS",
      name: "Tata Consultancy Services",
      sector: "IT & Software",
      weight: 12.8,
      qty: 145,
      avgBuy: 3820.0,
      ltp: 4210.8,
      totalValue: 610566.0,
      unrealizedPnL: 56666.0,
      unrealizedPnLPct: 10.23,
      varContrib: "16% VaR",
      piotroski: 9,
      piotroskiLabel: "Pristine",
      catalyst: "BFSI Mega-Deal Ramp-up",
    },
    {
      symbol: "HDFCBANK",
      name: "HDFC Bank Ltd",
      sector: "Banking & NBFC",
      weight: 14.2,
      qty: 380,
      avgBuy: 1580.0,
      ltp: 1642.1,
      totalValue: 624000.0,
      unrealizedPnL: 23598.0,
      unrealizedPnLPct: 3.93,
      varContrib: "18% VaR",
      piotroski: 7,
      piotroskiLabel: "Strong",
      catalyst: "NIM Expansion Cycle",
      lockWarning: "Day 342/365: Locked (Save ₹32.6k STCG)",
    },
    {
      symbol: "INFY",
      name: "Infosys Ltd",
      sector: "IT & Software",
      weight: 9.5,
      qty: 260,
      avgBuy: 1720.0,
      ltp: 1890.3,
      totalValue: 491478.0,
      unrealizedPnL: 44278.0,
      unrealizedPnLPct: 9.9,
      varContrib: "11% VaR",
      piotroski: 8,
      piotroskiLabel: "Strong",
      catalyst: "Generative AI Enterprise Spend",
    },
    {
      symbol: "TRENT",
      name: "Trent Ltd (Westside & Zudio)",
      sector: "Retail & Consumption",
      weight: 8.1,
      qty: 120,
      avgBuy: 5400.0,
      ltp: 6840.0,
      totalValue: 820800.0,
      unrealizedPnL: 172800.0,
      unrealizedPnLPct: 26.67,
      varContrib: "14% VaR",
      piotroski: 8,
      piotroskiLabel: "Strong",
      catalyst: "ML Decile 10 Alpha (+4.62%)",
    },
    {
      symbol: "ICICIBANK",
      name: "ICICI Bank Ltd",
      sector: "Banking & NBFC",
      weight: 10.5,
      qty: 410,
      avgBuy: 1120.0,
      ltp: 1245.0,
      totalValue: 510450.0,
      unrealizedPnL: 51250.0,
      unrealizedPnLPct: 11.16,
      varContrib: "12% VaR",
      piotroski: 8,
      piotroskiLabel: "Strong",
      catalyst: "Underweight Target (+16 shares)",
    },
  ];

  // Filtered holdings
  const filteredHoldings = holdings.filter((item) => {
    const matchesSector = selectedSector === "all" || item.sector === selectedSector;
    const matchesSearch =
      item.symbol.toLowerCase().includes(tableSearch.toLowerCase()) ||
      item.name.toLowerCase().includes(tableSearch.toLowerCase());
    return matchesSector && matchesSearch;
  });

  // Handle rebalance execution
  const handleExecuteBasket = () => {
    setIsExecutingBasket(true);
    setTimeout(() => {
      setIsExecutingBasket(false);
      setBasketExecuted(true);
      setTimeout(() => {
        setIsRebalanceModalOpen(false);
        setBasketExecuted(false);
      }, 1600);
    }, 1400);
  };

  return (
    <div className="w-full max-w-full overflow-x-hidden p-4 sm:p-6 space-y-6">
      
      {/* 1. TOP TITLE BANNER & INSTITUTIONAL DISPATCH ACTIONS */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-slate-200 mb-2">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold text-slate-900 tracking-tight">
              StockPortfolio.in Institutional Command Terminal
            </h1>
            <span className="px-2 py-0.5 text-[11px] font-mono font-medium rounded bg-blue-50 text-blue-700 border border-blue-200">
              v4.2 Production
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-1 max-w-3xl">
            Unified multi-asset surveillance: portfolio wealth compounding, Budget 2024-25 tax rebalancing, F&O tail hedging, and quantitative ML alpha discovery.
          </p>
        </div>

        {/* Action Button Suite */}
        <div className="flex items-center gap-2.5 shrink-0">
          <button
            onClick={() => alert("Fyers Broker WebSocket Connected (Token: FYERS-NSE-PRO-8491)")}
            className="inline-flex items-center gap-1.5 px-3 py-2 text-xs font-medium text-slate-800 bg-white hover:bg-slate-50 rounded-md border border-slate-300 shadow-sm transition-all"
          >
            <RefreshCw size={14} className="text-slate-500" />
            <span>Import Fyers Holdings</span>
          </button>
          <button
            onClick={() => alert("Audit trail exported to CSV.")}
            className="inline-flex items-center gap-1.5 px-3 py-2 text-xs font-medium text-slate-800 bg-white hover:bg-slate-50 rounded-md border border-slate-300 shadow-sm transition-all"
          >
            <Download size={14} className="text-slate-500" />
            <span>Export Audit Trail (CSV)</span>
          </button>
          <button
            onClick={() => setIsRebalanceModalOpen(true)}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 rounded-md shadow-sm transition-all"
          >
            <CheckCircle2 size={15} />
            <span>Execute Rebalance Basket</span>
          </button>
        </div>
      </div>

      {/* 2. HERO KPI RISK & VALUATION COCKPIT (4 Large Cards, Responsive 2x2 on Mobile) */}
      <section className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4 w-full min-w-0">
        
        {/* Card 1: Total Portfolio NAV & 1D Delta */}
        <div className="bg-white border border-slate-200 rounded-lg p-4 shadow-[0_1px_2px_0_rgba(15,23,42,0.04)] flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-[10.5px] font-mono font-semibold uppercase text-slate-500 tracking-wider">
                Portfolio NAV & 1D Delta
              </span>
              <PieChart size={16} className="text-slate-400" />
            </div>
            <div className="text-2xl font-bold font-mono text-slate-900 tracking-tight tabular-nums">
              ₹48,25,400.00
            </div>
            <div className="mt-1.5 flex items-center gap-1.5">
              <span className="text-xs font-mono font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200 tabular-nums flex items-center gap-1">
                <TrendingUp size={12} /> +₹1,42,850.00 (+3.05%) Today
              </span>
            </div>
          </div>
          <div className="mt-3.5 pt-2.5 border-t border-slate-100 text-[11px] font-mono text-slate-500 space-y-1">
            <div className="flex justify-between">
              <span>Invested Capital:</span>
              <span className="font-semibold text-slate-800">₹36,41,200.00</span>
            </div>
            <div className="flex justify-between items-center text-[10.5px]">
              <span>Net Gain: <strong className="text-emerald-600 font-semibold">+₹11,84,200 (+32.5%)</strong></span>
              <span className="px-1.5 py-0.2 rounded bg-slate-100 text-slate-700 font-semibold">XIRR 24.8%</span>
            </div>
          </div>
        </div>

        {/* Card 2: Statutory Tax Status (Budget 2024-25 Rules) */}
        <div className="bg-white border border-slate-200 rounded-lg p-4 shadow-[0_1px_2px_0_rgba(15,23,42,0.04)] flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-[10.5px] font-mono font-semibold uppercase text-slate-500 tracking-wider">
                Statutory Tax Status
              </span>
              <CheckCircle2 size={16} className="text-emerald-600" />
            </div>
            <div className="text-2xl font-bold font-mono text-emerald-600 tracking-tight tabular-nums">
              ₹0.00 Tax Drag
            </div>
            <div className="mt-1.5 flex items-center gap-1.5">
              <span className="text-xs font-mono font-medium text-blue-700 bg-blue-50 px-2 py-0.5 rounded border border-blue-200">
                Zero-Tax Inflow Active
              </span>
            </div>
          </div>
          <div className="mt-3.5 pt-2.5 border-t border-slate-100 text-[11px] font-mono text-slate-500 space-y-1">
            <div className="flex justify-between items-center">
              <span>3 in 30D LTCG Window:</span>
              <span className="text-amber-700 font-semibold text-[10px] bg-amber-50 px-1.5 py-0.2 rounded border border-amber-200">Locked</span>
            </div>
            <div className="text-[10.5px] text-slate-500">
              Locked Savings: <strong className="text-emerald-600 font-bold">₹42,800.00</strong> (STCG 20% → LTCG 12.5%)
            </div>
          </div>
        </div>

        {/* Card 3: F&O Tail Hedge Sizing */}
        <div className="bg-white border border-slate-200 rounded-lg p-4 shadow-[0_1px_2px_0_rgba(15,23,42,0.04)] flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-[10.5px] font-mono font-semibold uppercase text-slate-500 tracking-wider">
                F&O Tail Hedge Sizing
              </span>
              <Shield size={16} className="text-blue-600" />
            </div>
            <div className="text-2xl font-bold font-mono text-slate-900 tracking-tight tabular-nums">
              -6.4% Max DD
            </div>
            <div className="mt-1.5 flex items-center gap-1.5">
              <span className="text-xs font-mono font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                Collar Active (Zero Net Cost)
              </span>
            </div>
          </div>
          <div className="mt-3.5 pt-2.5 border-t border-slate-100 text-[11px] font-mono text-slate-500 space-y-1">
            <div className="flex justify-between">
              <span>Put Wall: <strong className="text-slate-800 font-semibold">24,500 PE</strong></span>
              <span className="text-slate-400">1.85 Cr OI</span>
            </div>
            <div className="flex justify-between items-center text-[10.5px]">
              <span>Call Wall: 25,000 CE (1.42 Cr)</span>
              <span className="text-emerald-600 font-semibold">Drag: 0.004%</span>
            </div>
          </div>
        </div>

        {/* Card 4: Quantitative ML Alpha & Risk */}
        <div className="bg-white border border-slate-200 rounded-lg p-4 shadow-[0_1px_2px_0_rgba(15,23,42,0.04)] flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-[10.5px] font-mono font-semibold uppercase text-slate-500 tracking-wider">
                ML Return Alpha & VaR
              </span>
              <Activity size={16} className="text-blue-600" />
            </div>
            <div className="text-2xl font-bold font-mono text-emerald-600 tracking-tight tabular-nums">
              +4.04% Alpha
            </div>
            <div className="mt-1.5 flex items-center gap-1.5">
              <span className="text-xs font-mono font-semibold text-blue-700 bg-blue-50 px-2 py-0.5 rounded border border-blue-200">
                Sharpe: 1.94 | Decile 10
              </span>
            </div>
          </div>
          <div className="mt-3.5 pt-2.5 border-t border-slate-100 text-[11px] font-mono text-slate-500 space-y-1">
            <div className="flex justify-between">
              <span>Hist VaR (95%, 1D):</span>
              <span className="font-semibold text-slate-800">1.48% (₹71,415)</span>
            </div>
            <div className="flex justify-between items-center text-[10.5px]">
              <span>Beta: 0.88 vs NIFTY</span>
              <span className="text-blue-700 font-semibold">IC: 0.084 (t: 4.12)</span>
            </div>
          </div>
        </div>

      </section>

      {/* 3. DUAL ANALYTICS & DECISION COCKPIT (60% / 40% Split) */}
      <section className="grid grid-cols-1 lg:grid-cols-12 gap-5 w-full min-w-0">
        
        {/* LEFT PANEL (60% width): Multi-Model Visual Analytics Console */}
        <div className="lg:col-span-7 min-w-0 w-full flex flex-col bg-white border border-slate-200 rounded-lg p-5 shadow-[0_1px_2px_0_rgba(15,23,42,0.04)] justify-between overflow-hidden">
          <div>
            {/* Header Bar with View Tabs */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-slate-200 gap-3">
              <div>
                <h2 className="text-sm font-bold text-slate-900">Multi-Model Visual Analytics Console</h2>
                <p className="text-[11px] text-slate-500">10-Year Monte Carlo probabilistic compounding & walk-forward folds</p>
              </div>

              {/* Segmented Switcher */}
              <div className="flex items-center bg-slate-100 p-0.5 rounded-md border border-slate-200 text-xs font-medium">
                <button
                  onClick={() => setActiveVisualTab("cone")}
                  className={`px-3 py-1 rounded transition-all ${
                    activeVisualTab === "cone"
                      ? "bg-white text-blue-600 font-semibold shadow-xs"
                      : "text-slate-600 hover:text-slate-900"
                  }`}
                >
                  Wealth Cone (10Y)
                </button>
                <button
                  onClick={() => setActiveVisualTab("lab")}
                  className={`px-3 py-1 rounded transition-all ${
                    activeVisualTab === "lab"
                      ? "bg-white text-blue-600 font-semibold shadow-xs"
                      : "text-slate-600 hover:text-slate-900"
                  }`}
                >
                  Strategy Lab v2
                </button>
                <button
                  onClick={() => setActiveVisualTab("oi")}
                  className={`px-3 py-1 rounded transition-all ${
                    activeVisualTab === "oi"
                      ? "bg-white text-blue-600 font-semibold shadow-xs"
                      : "text-slate-600 hover:text-slate-900"
                  }`}
                >
                  Derivatives OI Payoff
                </button>
              </div>
            </div>

            {/* TAB 1: High-Resolution Wealth Cone SVG Visual */}
            {activeVisualTab === "cone" && (
              <div className="mt-4 relative bg-slate-50 rounded-lg border border-slate-200 p-3.5 overflow-hidden">
                <div className="flex flex-wrap items-center justify-between text-xs font-mono mb-2 gap-2">
                  <div className="flex items-center gap-4">
                    <div className="flex items-center gap-1.5">
                      <span className="w-3 h-0.5 bg-emerald-600 rounded-full"></span>
                      <span className="text-slate-600 text-[11px]">95th %ile (Bull): <strong className="text-slate-900 font-semibold">₹2.92 Cr</strong></span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <span className="w-3 h-0.5 bg-blue-600 rounded-full"></span>
                      <span className="text-slate-600 text-[11px]">50th %ile (Median): <strong className="text-slate-900 font-semibold">₹1.84 Cr</strong></span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <span className="w-3 h-0.5 bg-red-600 rounded-full"></span>
                      <span className="text-slate-600 text-[11px]">5th %ile (Bear): <strong className="text-slate-900 font-semibold">₹1.18 Cr</strong></span>
                    </div>
                  </div>
                  <div className="text-[11px] text-slate-400 hidden sm:block">
                    1,000 Folds • Geometric Brownian Motion
                  </div>
                </div>

                {/* SVG Wealth Cone */}
                <div className="w-full h-56 relative">
                  <svg viewBox="0 0 640 220" className="w-full h-full" preserveAspectRatio="none">
                    <defs>
                      <linearGradient id="bullGradient" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#2563EB" stopOpacity="0.18" />
                        <stop offset="100%" stopColor="#2563EB" stopOpacity="0.02" />
                      </linearGradient>
                      <linearGradient id="bearGradient" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#DC2626" stopOpacity="0.08" />
                        <stop offset="100%" stopColor="#DC2626" stopOpacity="0.01" />
                      </linearGradient>
                    </defs>

                    {/* Grid lines */}
                    <line x1="40" y1="20" x2="620" y2="20" stroke="#E2E8F0" strokeDasharray="3 3" />
                    <text x="35" y="24" textAnchor="end" fontSize="9" fill="#94A3B8" fontFamily="JetBrains Mono">₹3.0 Cr</text>

                    <line x1="40" y1="70" x2="620" y2="70" stroke="#E2E8F0" strokeDasharray="3 3" />
                    <text x="35" y="74" textAnchor="end" fontSize="9" fill="#94A3B8" fontFamily="JetBrains Mono">₹2.0 Cr</text>

                    <line x1="40" y1="125" x2="620" y2="125" stroke="#E2E8F0" strokeDasharray="3 3" />
                    <text x="35" y="129" textAnchor="end" fontSize="9" fill="#94A3B8" fontFamily="JetBrains Mono">₹1.0 Cr</text>

                    <line x1="40" y1="180" x2="620" y2="180" stroke="#E2E8F0" strokeDasharray="3 3" />
                    <text x="35" y="184" textAnchor="end" fontSize="9" fill="#94A3B8" fontFamily="JetBrains Mono">₹48.2 L</text>

                    {/* Vertical Milestone lines */}
                    <line x1="280" y1="20" x2="280" y2="195" stroke="#CBD5E1" strokeWidth="1" strokeDasharray="2 2" />
                    <rect x="245" y="128" width="70" height="16" rx="3" fill="#FFFFFF" stroke="#CBD5E1" />
                    <text x="280" y="140" textAnchor="middle" fontSize="8.5" fill="#2563EB" fontFamily="JetBrains Mono" fontWeight="600">₹1 Cr (~Yr 3.8)</text>

                    <line x1="460" y1="20" x2="460" y2="195" stroke="#CBD5E1" strokeWidth="1" strokeDasharray="2 2" />
                    <rect x="425" y="62" width="70" height="16" rx="3" fill="#FFFFFF" stroke="#CBD5E1" />
                    <text x="460" y="74" textAnchor="middle" fontSize="8.5" fill="#2563EB" fontFamily="JetBrains Mono" fontWeight="600">₹2 Cr (~Yr 7.2)</text>

                    {/* Fan Area Shading */}
                    <polygon points="40,180 160,165 280,135 400,90 520,48 620,24 620,135 520,148 400,162 280,172 160,178 40,180" fill="url(#bullGradient)" />
                    <polygon points="40,180 160,178 280,172 400,162 520,148 620,135 620,145 520,158 400,170 280,177 160,180 40,180" fill="url(#bearGradient)" />

                    {/* Trajectory Curves */}
                    <path d="M40,180 C160,162 280,128 400,82 C480,52 560,34 620,24" fill="none" stroke="#059669" strokeWidth="1.8" />
                    <path d="M40,180 C160,170 280,148 400,118 C480,94 560,78 620,68" fill="none" stroke="#2563EB" strokeWidth="2.5" />
                    <path d="M40,180 C160,178 280,172 400,162 C480,152 560,142 620,135" fill="none" stroke="#DC2626" strokeWidth="1.8" strokeDasharray="4 2" />

                    {/* Milestone Dots */}
                    <circle cx="40" cy="180" r="3.5" fill="#2563EB" stroke="#FFFFFF" strokeWidth="1.5" />
                    <circle cx="280" cy="148" r="3.5" fill="#2563EB" stroke="#FFFFFF" strokeWidth="1.5" />
                    <circle cx="460" cy="98" r="3.5" fill="#2563EB" stroke="#FFFFFF" strokeWidth="1.5" />
                    <circle cx="620" cy="68" r="4.5" fill="#2563EB" stroke="#FFFFFF" strokeWidth="2" />

                    {/* Target Badge */}
                    <rect x="548" y="58" width="68" height="20" rx="3" fill="#2563EB" />
                    <text x="582" y="72" textAnchor="middle" fontSize="9.5" fill="#FFFFFF" fontFamily="JetBrains Mono" fontWeight="700">₹1.84 Cr Med</text>

                    {/* Timeline */}
                    <text x="40" y="208" textAnchor="start" fontSize="9" fill="#64748B" fontFamily="JetBrains Mono">Today (2025)</text>
                    <text x="180" y="208" textAnchor="middle" fontSize="9" fill="#64748B" fontFamily="JetBrains Mono">Yr 2.5</text>
                    <text x="320" y="208" textAnchor="middle" fontSize="9" fill="#64748B" fontFamily="JetBrains Mono">Yr 5.0</text>
                    <text x="470" y="208" textAnchor="middle" fontSize="9" fill="#64748B" fontFamily="JetBrains Mono">Yr 7.5</text>
                    <text x="620" y="208" textAnchor="end" fontSize="9" fill="#64748B" fontFamily="JetBrains Mono">Yr 10.0 (2035)</text>
                  </svg>
                </div>

                <div className="mt-2.5 pt-2 border-t border-slate-200 flex flex-wrap items-center justify-between text-[11px] font-mono text-slate-500">
                  <div>Assumed SIP: <strong className="text-slate-800 font-semibold">+₹25,000/mo</strong></div>
                  <div>Compounding Rate: <strong className="text-blue-600 font-semibold">14.2% CAGR</strong></div>
                  <div>Downside Floor: <strong className="text-slate-800 font-semibold">₹1.18 Cr</strong></div>
                </div>
              </div>
            )}

            {/* TAB 2: Strategy Lab v2 Walk-Forward Metrics */}
            {activeVisualTab === "lab" && (
              <div className="mt-4 bg-slate-50 rounded-lg border border-slate-200 p-4 space-y-3 font-mono text-xs">
                <div className="flex items-center justify-between pb-2 border-b border-slate-200">
                  <span className="font-semibold text-slate-800">Walk-Forward Factor Stability Matrix (5 Folds)</span>
                  <span className="text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200 font-bold">In-Sample vs Out-of-Sample Ratio: 0.89</span>
                </div>
                <div className="grid grid-cols-3 gap-3 text-center">
                  <div className="bg-white p-2.5 rounded border border-slate-200">
                    <div className="text-[10px] text-slate-400">OUT-OF-SAMPLE SHARPE</div>
                    <div className="text-base font-bold text-slate-900 mt-0.5">1.94</div>
                  </div>
                  <div className="bg-white p-2.5 rounded border border-slate-200">
                    <div className="text-[10px] text-slate-400">MAX DRAWDOWN</div>
                    <div className="text-base font-bold text-emerald-600 mt-0.5">-6.4%</div>
                  </div>
                  <div className="bg-white p-2.5 rounded border border-slate-200">
                    <div className="text-[10px] text-slate-400">ANNUALIZED SLIPPAGE</div>
                    <div className="text-base font-bold text-slate-900 mt-0.5">0.08%</div>
                  </div>
                </div>
                <div className="p-3 bg-white rounded border border-slate-200 text-[11px] space-y-1">
                  <div className="flex justify-between">
                    <span>Decile 10 (Long): +18.4% Ann.</span>
                    <span className="text-emerald-600 font-semibold">Alpha: +4.04%</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Decile 1 (Short): +2.1% Ann.</span>
                    <span className="text-slate-500">Spread: +16.3%</span>
                  </div>
                </div>
              </div>
            )}

            {/* TAB 3: Derivatives Open Interest Payoff */}
            {activeVisualTab === "oi" && (
              <div className="mt-4 bg-slate-50 rounded-lg border border-slate-200 p-4 space-y-3 font-mono text-xs">
                <div className="flex items-center justify-between pb-2 border-b border-slate-200">
                  <span className="font-semibold text-slate-800">NIFTY ATM 24,850 OI Walls & Max Pain</span>
                  <span className="text-blue-700 bg-blue-50 px-2 py-0.5 rounded border border-blue-200 font-bold">PCR: 1.18 (Bullish Bias)</span>
                </div>
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between p-2 bg-white rounded border border-slate-200">
                    <span>Put Wall Support: 24,500 PE</span>
                    <span className="text-emerald-700 font-bold">1.85 Cr Open Interest</span>
                  </div>
                  <div className="flex items-center justify-between p-2 bg-white rounded border border-slate-200">
                    <span>Max Pain Strike: 24,800</span>
                    <span className="text-slate-700 font-semibold">Current NIFTY: 24,852.15</span>
                  </div>
                  <div className="flex items-center justify-between p-2 bg-white rounded border border-slate-200">
                    <span>Call Wall Resistance: 25,000 CE</span>
                    <span className="text-red-700 font-bold">1.42 Cr Open Interest</span>
                  </div>
                </div>
              </div>
            )}
          </div>

          <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500">
            <span>Portfolio Simulation Engine: <strong className="font-mono text-slate-700">Geometric Brownian Motion (GBM)</strong></span>
            <Link href="/lab" className="text-blue-600 hover:underline font-semibold flex items-center gap-0.5">
              Launch Quantitative Strategy Lab <ChevronRight size={13} />
            </Link>
          </div>
        </div>

        {/* RIGHT PANEL (40% width): Execution & Rebalance Dispatch Hub */}
        <div className="lg:col-span-5 min-w-0 w-full flex flex-col bg-white border border-slate-200 rounded-lg p-5 shadow-[0_1px_2px_0_rgba(15,23,42,0.04)] justify-between space-y-4">
          <div>
            <div className="flex items-center justify-between pb-3 border-b border-slate-200">
              <div className="flex items-center gap-2">
                <Zap size={16} className="text-blue-600" />
                <h3 className="text-sm font-bold text-slate-900">Execution & Rebalance Dispatch</h3>
              </div>
              <span className="text-[10px] font-mono font-semibold px-2 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200">
                0% Realized STCG
              </span>
            </div>

            {/* Zero-Tax Fresh Capital Allocator */}
            <div className="mt-3.5 p-3 rounded-lg border border-blue-200 bg-blue-50/60 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-900 flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-blue-600"></span>
                  Zero-Tax Fresh Capital Inflow
                </span>
                <span className="text-xs font-mono font-bold text-blue-700 bg-white px-2 py-0.5 rounded border border-blue-200">
                  ₹50,000 Cash
                </span>
              </div>
              <div className="p-2.5 bg-white rounded border border-blue-100 font-mono text-[11px] text-slate-700 space-y-1">
                <div className="flex justify-between">
                  <span>RELIANCE (+10 shares @ ₹2,985.40):</span>
                  <span className="font-semibold text-slate-900">₹29,854.00</span>
                </div>
                <div className="flex justify-between">
                  <span>ICICIBANK (+16 shares @ ₹1,245.00):</span>
                  <span className="font-semibold text-slate-900">₹19,920.00</span>
                </div>
                <div className="pt-1 border-t border-slate-100 flex justify-between text-slate-500 text-[10px]">
                  <span>Unallocated Cash Buffer:</span>
                  <span>₹226.00</span>
                </div>
              </div>
            </div>

            {/* Amber 30-Day LTCG Proximity Gate Warning */}
            <div className="mt-3 p-3 rounded-lg border border-amber-200 bg-amber-50/70 text-xs text-amber-950 space-y-1.5">
              <div className="flex items-center gap-1.5 font-semibold text-amber-900">
                <Lock size={14} className="text-amber-700" />
                <span>30-Day LTCG Proximity Gate Alert</span>
              </div>
              <p className="text-[11px] leading-relaxed text-amber-900">
                <strong>HDFCBANK (Day 342/365)</strong> and <strong>L&T (Day 338/365)</strong> are within 30 days of the 12-month holding mark. Selling now triggers 20% STCG; holding unlocks 12.5% LTCG.
              </p>
              <div className="font-mono text-[10.5px] text-amber-800 font-semibold">
                Locked Tax Savings: ₹32,600.00 (Protected from rebalance trims)
              </div>
            </div>

            {/* Automated Collar Sizer Breakdown */}
            <div className="mt-3 p-3 rounded-lg border border-slate-200 bg-slate-50 space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="font-semibold text-slate-800 flex items-center gap-1">
                  <Shield size={14} className="text-blue-600" />
                  Automated Collar Sizer (26-SEP Expiry)
                </span>
                <span className="text-[10px] font-mono font-bold text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded border border-emerald-200">
                  Net Debit: ₹230
                </span>
              </div>
              <div className="p-2 bg-white rounded border border-slate-200 font-mono text-[11px] space-y-1">
                <div className="flex justify-between">
                  <span>BUY 2 Lots NIFTY 24,200 PE:</span>
                  <span className="text-red-600 font-semibold">@ ₹48.50 (₹2,425)</span>
                </div>
                <div className="flex justify-between">
                  <span>SELL 2 Lots NIFTY 25,400 CE:</span>
                  <span className="text-emerald-600 font-semibold">@ ₹46.20 (₹2,310)</span>
                </div>
              </div>
            </div>
          </div>

          {/* Primary Action Button */}
          <div>
            <button
              onClick={() => setIsRebalanceModalOpen(true)}
              className="w-full py-2.5 px-4 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold rounded-md shadow-sm flex items-center justify-center gap-2 transition-all active:scale-[0.99]"
            >
              <Zap size={15} />
              <span>Execute Consolidated Rebalance & Hedge Basket</span>
            </button>
            <div className="mt-1.5 text-center text-[10px] text-slate-400 font-mono">
              Fyers Direct Order Routing • 0.004% Net Drag • Zero Capital Gains Liability
            </div>
          </div>
        </div>

      </section>

      {/* 4. MASTER MULTI-FACTOR PORTFOLIO & SCREENER TERMINAL TABLE */}
      <section className="bg-white border border-slate-200 rounded-lg shadow-[0_1px_2px_0_rgba(15,23,42,0.04)] overflow-hidden">
        
        {/* Table Controller Header & Segmented Tabs */}
        <div className="px-5 py-3.5 flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-slate-200 bg-slate-50/60">
          <div className="flex flex-wrap items-center bg-white p-0.5 rounded-md border border-slate-200 text-xs font-medium">
            <button
              onClick={() => setActiveTableTab("holdings")}
              className={`px-3 py-1.5 rounded transition flex items-center gap-1.5 ${
                activeTableTab === "holdings"
                  ? "bg-blue-50 text-blue-700 font-bold border border-blue-200 shadow-xs"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              <span>Active Portfolio Holdings & Forensics</span>
              <span className="px-1.5 py-0.2 rounded-full bg-blue-600 text-white text-[10px] font-mono">
                {holdings.length}
              </span>
            </button>
            <button
              onClick={() => setActiveTableTab("alpha")}
              className={`px-3 py-1.5 transition flex items-center gap-1 ${
                activeTableTab === "alpha"
                  ? "bg-blue-50 text-blue-700 font-bold border border-blue-200 shadow-xs"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              <span>NSE 500 Top Alpha Picks</span>
              <span className="text-[10px] font-mono text-slate-400">(D10)</span>
            </button>
            <button
              onClick={() => setActiveTableTab("options")}
              className={`px-3 py-1.5 transition ${
                activeTableTab === "options"
                  ? "bg-blue-50 text-blue-700 font-bold border border-blue-200 shadow-xs"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              Option Chain Matrix (ATM 24,850)
            </button>
            <button
              onClick={() => setActiveTableTab("backtest")}
              className={`px-3 py-1.5 transition ${
                activeTableTab === "backtest"
                  ? "bg-blue-50 text-blue-700 font-bold border border-blue-200 shadow-xs"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              Strategy Backtest Logs
            </button>
          </div>

          {/* Filtering & Table Search */}
          <div className="flex flex-wrap items-center gap-2">
            <div className="relative">
              <Search size={14} className="absolute left-2.5 top-2.5 text-slate-400" />
              <input
                type="text"
                placeholder="Filter ticker / sector..."
                value={tableSearch}
                onChange={(e) => setTableSearch(e.target.value)}
                className="h-8 pl-8 pr-3 text-xs bg-white text-slate-900 rounded border border-slate-300 focus:outline-none focus:border-blue-600 w-44 font-sans"
              />
            </div>

            <select
              value={selectedSector}
              onChange={(e) => setSelectedSector(e.target.value)}
              className="h-8 px-2 text-xs bg-white text-slate-900 rounded border border-slate-300 focus:outline-none focus:border-blue-600 font-sans"
            >
              <option value="all">All Sectors</option>
              <option value="Energy & Telecom">Energy & Telecom</option>
              <option value="Banking & NBFC">Banking & NBFC</option>
              <option value="IT & Software">IT & Software</option>
              <option value="Retail & Consumption">Retail & Consumption</option>
            </select>
          </div>
        </div>

        {/* DESKTOP VIEW: High-Density Institutional Table (Hidden on small mobile) */}
        <div className="hidden md:block overflow-x-auto w-full min-w-0">
          <table className="w-full min-w-[960px] text-left text-xs border-collapse">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200 text-[10.5px] font-mono font-semibold uppercase text-slate-500 tracking-wider">
                <th className="py-2.5 px-4 font-mono">TICKER & ASSET</th>
                <th className="py-2.5 px-3 font-mono">WEIGHT %</th>
                <th className="py-2.5 px-3 font-mono text-right">QTY</th>
                <th className="py-2.5 px-3 font-mono text-right">AVG BUY (₹)</th>
                <th className="py-2.5 px-3 font-mono text-right">LTP (₹)</th>
                <th className="py-2.5 px-3 font-mono text-right">TOTAL VALUE (₹)</th>
                <th className="py-2.5 px-3 font-mono text-right">UNREALIZED P&L</th>
                <th className="py-2.5 px-3 font-mono text-center">VAR CONTRIB</th>
                <th className="py-2.5 px-3 font-mono text-center">PIOTROSKI</th>
                <th className="py-2.5 px-3 font-mono text-center">CATALYST / ML ALPHA</th>
                <th className="py-2.5 px-4 font-mono text-center">QUICK ACTIONS</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 font-sans">
              {filteredHoldings.map((item) => (
                <tr key={item.symbol} className="hover:bg-slate-50/80 transition-colors group">
                  <td className="py-3 px-4">
                    <div className="flex items-center gap-2.5">
                      <div className="w-7 h-7 rounded bg-blue-50 text-blue-700 border border-blue-200 flex items-center justify-center font-mono font-bold text-xs">
                        {item.symbol.charAt(0)}
                      </div>
                      <div>
                        <div className="font-bold text-slate-900 font-mono flex items-center gap-1.5">
                          <span>{item.symbol}</span>
                          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                        </div>
                        <div className="text-[11px] text-slate-400">
                          {item.name} • <span className="text-slate-600 font-medium">{item.sector}</span>
                        </div>
                      </div>
                    </div>
                  </td>

                  {/* Weight Progress */}
                  <td className="py-3 px-3">
                    <div className="flex items-center gap-2">
                      <span className="font-mono font-bold text-slate-900 tabular-nums w-10">
                        {item.weight}%
                      </span>
                      <div className="w-16 h-1.5 bg-slate-200 rounded-full overflow-hidden">
                        <div className="h-full bg-blue-600 rounded-full" style={{ width: `${item.weight * 5}%` }}></div>
                      </div>
                    </div>
                  </td>

                  <td className="py-3 px-3 text-right font-mono font-medium text-slate-800 tabular-nums">
                    {item.qty}
                  </td>
                  <td className="py-3 px-3 text-right font-mono text-slate-500 tabular-nums">
                    ₹{item.avgBuy.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                  </td>
                  <td className="py-3 px-3 text-right font-mono font-semibold text-slate-900 tabular-nums">
                    ₹{item.ltp.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                  </td>
                  <td className="py-3 px-3 text-right font-mono font-bold text-slate-900 tabular-nums">
                    ₹{item.totalValue.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                  </td>

                  {/* Unrealized P&L */}
                  <td className="py-3 px-3 text-right font-mono tabular-nums">
                    <div className="text-emerald-600 font-bold">
                      +₹{item.unrealizedPnL.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                    </div>
                    <div className="text-[10px] text-emerald-600 font-semibold">
                      (+{item.unrealizedPnLPct}%)
                    </div>
                  </td>

                  {/* VaR Contrib */}
                  <td className="py-3 px-3 text-center">
                    <span className="font-mono text-xs font-semibold px-1.5 py-0.5 rounded bg-slate-100 text-slate-700 border border-slate-200">
                      {item.varContrib}
                    </span>
                  </td>

                  {/* Piotroski Score Badge (Clickable for 9-point Forensics) */}
                  <td className="py-3 px-3 text-center">
                    <button
                      onClick={() => setSelectedForensicHolding(item)}
                      className="inline-flex items-center gap-1 font-mono text-xs font-semibold px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 hover:bg-emerald-100 transition"
                    >
                      <span>{item.piotroski}/9</span>
                      <span className="text-[10px]">{item.piotroskiLabel}</span>
                    </button>
                  </td>

                  {/* Catalyst / Signal Tag */}
                  <td className="py-3 px-3 text-center">
                    <div className="flex flex-col items-center gap-0.5">
                      <span className="text-[11px] font-medium text-slate-700 bg-slate-100 px-2 py-0.5 rounded">
                        {item.catalyst}
                      </span>
                      {item.lockWarning && (
                        <span className="text-[9.5px] font-mono text-amber-800 bg-amber-50 border border-amber-200 px-1.5 rounded">
                          {item.lockWarning}
                        </span>
                      )}
                    </div>
                  </td>

                  {/* Actions */}
                  <td className="py-3 px-4 text-center">
                    <div className="flex items-center justify-center gap-1.5">
                      <Link
                        href={`/analyse/${item.symbol}`}
                        className="px-2.5 py-1 text-[11px] font-semibold text-blue-600 hover:bg-blue-50 border border-blue-200 rounded transition"
                      >
                        Deep Dive
                      </Link>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* MOBILE VIEW: Touch-Optimized Holding Cards (390px Viewport Compliant) */}
        <div className="block md:hidden p-3 space-y-2.5">
          {filteredHoldings.map((item) => (
            <div
              key={item.symbol}
              className="bg-white border border-slate-200 rounded-lg p-3 shadow-xs space-y-2 active:bg-slate-50 transition"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="font-mono font-bold text-sm text-slate-900">{item.symbol}</span>
                  <span className="bg-slate-100 text-slate-600 text-[9px] font-mono font-medium px-1.5 py-0.5 rounded">
                    {item.weight}% Alloc
                  </span>
                </div>
                <div className="text-right">
                  <span className="font-mono font-bold text-xs text-slate-900">
                    ₹{item.ltp.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                  </span>
                  <span className="font-mono text-[10px] text-emerald-600 font-semibold ml-1">
                    +{item.unrealizedPnLPct}%
                  </span>
                </div>
              </div>

              <div className="flex items-center justify-between text-[11px] font-mono text-slate-500">
                <span>{item.qty} Qty @ Avg ₹{item.avgBuy}</span>
                <span className="text-emerald-600 font-bold">
                  +₹{item.unrealizedPnL.toLocaleString("en-IN")}
                </span>
              </div>

              <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-[10px]">
                <button
                  onClick={() => setSelectedForensicHolding(item)}
                  className="bg-emerald-50 text-emerald-700 border border-emerald-200 px-2 py-0.5 rounded font-mono font-medium"
                >
                  Piotroski {item.piotroski}/9 {item.piotroskiLabel}
                </button>
                <Link
                  href={`/analyse/${item.symbol}`}
                  className="text-blue-600 font-semibold flex items-center gap-0.5"
                >
                  Deep Dive <ChevronRight size={12} />
                </Link>
              </div>

              {item.lockWarning && (
                <div className="p-1.5 rounded bg-amber-50 border border-amber-200 text-[10px] font-mono text-amber-900 flex items-center gap-1">
                  <Lock size={12} /> {item.lockWarning}
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Sticky Table Summary Footer */}
        <div className="p-4 border-t border-slate-200 bg-slate-50 flex flex-wrap items-center justify-between gap-3 text-xs text-slate-600">
          <div className="flex items-center gap-4 font-mono">
            <span>Aggregated Holdings: <strong className="text-slate-900">6 Core Positions</strong></span>
            <span>Unrealized Gain: <strong className="text-emerald-600 font-bold">+₹4,24,666.00</strong></span>
            <span>Avg Portfolio Piotroski: <strong className="text-slate-900 font-bold">8.17 / 9</strong></span>
          </div>

          <div className="flex items-center gap-2">
            <Link
              href="/screener"
              className="text-blue-600 font-semibold hover:underline flex items-center gap-1"
            >
              Scan All 500 NSE Equities <ArrowUpRight size={13} />
            </Link>
          </div>
        </div>

      </section>

      {/* 5. INTERACTIVE MODAL: Consolidated Rebalance & Hedge Execution Basket */}
      {isRebalanceModalOpen && (
        <div 
          onClick={() => setIsRebalanceModalOpen(false)}
          className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4 cursor-pointer"
        >
          <div 
            onClick={(e) => e.stopPropagation()}
            className="bg-white border border-slate-200 rounded-xl shadow-2xl max-w-xl w-full p-6 space-y-4 animate-scale-in cursor-default"
          >
            <div className="flex items-center justify-between pb-3 border-b border-slate-200">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded bg-blue-50 text-blue-600 flex items-center justify-center font-bold">
                  <Zap size={18} />
                </div>
                <div>
                  <h3 className="text-base font-bold text-slate-900">Consolidated Rebalance Basket</h3>
                  <p className="text-xs text-slate-500">Zero-Tax Capital Inflow + F&O Tail Hedge Deployment</p>
                </div>
              </div>
              <button
                onClick={() => setIsRebalanceModalOpen(false)}
                className="p-1 rounded text-slate-400 hover:text-slate-600 hover:bg-slate-100"
              >
                <X size={18} />
              </button>
            </div>

            {/* Order Items */}
            <div className="space-y-2 font-mono text-xs">
              <div className="text-[11px] font-bold text-slate-400 uppercase tracking-wider font-sans">
                Leg 1: Equity Fresh Inflow (0% Realized STCG)
              </div>
              <div className="p-3 bg-slate-50 rounded-lg border border-slate-200 space-y-1.5">
                <div className="flex justify-between items-center">
                  <span className="font-semibold text-slate-800">BUY 10 RELIANCE (CNC / Equity)</span>
                  <span className="text-slate-900">@ ₹2,985.40 = ₹29,854.00</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="font-semibold text-slate-800">BUY 16 ICICIBANK (CNC / Equity)</span>
                  <span className="text-slate-900">@ ₹1,245.00 = ₹19,920.00</span>
                </div>
              </div>

              <div className="text-[11px] font-bold text-slate-400 uppercase tracking-wider font-sans pt-1">
                Leg 2: F&O Tail Hedge Collar (26-SEP Expiry)
              </div>
              <div className="p-3 bg-slate-50 rounded-lg border border-slate-200 space-y-1.5">
                <div className="flex justify-between items-center">
                  <span className="text-red-700 font-semibold">BUY 2 Lots NIFTY 24,200 PE</span>
                  <span className="text-slate-900">@ ₹48.50 = ₹2,425.00</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-emerald-700 font-semibold">SELL 2 Lots NIFTY 25,400 CE</span>
                  <span className="text-slate-900">@ ₹46.20 = ₹2,310.00</span>
                </div>
              </div>

              <div className="p-3 bg-blue-50 rounded-lg border border-blue-200 space-y-1 text-slate-800">
                <div className="flex justify-between font-bold">
                  <span>Total Capital Outlay:</span>
                  <span className="text-blue-700">₹50,004.00</span>
                </div>
                <div className="flex justify-between text-[11px] text-slate-600">
                  <span>Estimated Capital Gains Tax:</span>
                  <span className="text-emerald-700 font-semibold">₹0.00 (Zero STCG)</span>
                </div>
                <div className="flex justify-between text-[11px] text-slate-600">
                  <span>Fyers Direct Execution Latency:</span>
                  <span>~3ms FIX Gateway</span>
                </div>
              </div>
            </div>

            {/* Modal Actions */}
            <div className="pt-2 flex items-center justify-end gap-3">
              <button
                onClick={() => setIsRebalanceModalOpen(false)}
                className="px-4 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-100 rounded-md border border-slate-300"
              >
                Cancel
              </button>
              <button
                onClick={handleExecuteBasket}
                disabled={isExecutingBasket || basketExecuted}
                className={`px-5 py-2 text-xs font-semibold text-white rounded-md shadow-sm transition flex items-center gap-2 ${
                  basketExecuted
                    ? "bg-emerald-600"
                    : "bg-blue-600 hover:bg-blue-700"
                }`}
              >
                {isExecutingBasket && <RefreshCw size={14} className="animate-spin" />}
                {basketExecuted && <CheckCircle2 size={14} />}
                <span>
                  {basketExecuted
                    ? "Basket Successfully Dispatched!"
                    : isExecutingBasket
                    ? "Routing Orders via Fyers..."
                    : "Confirm & Transmit Orders"}
                </span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 6. INTERACTIVE MODAL: 9-Point Piotroski Forensic Breakdown */}
      {selectedForensicHolding && (
        <div 
          onClick={() => setSelectedForensicHolding(null)}
          className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4 cursor-pointer"
        >
          <div 
            onClick={(e) => e.stopPropagation()}
            className="bg-white border border-slate-200 rounded-xl shadow-2xl max-w-lg w-full p-6 space-y-4 cursor-default"
          >
            <div className="flex items-center justify-between pb-3 border-b border-slate-200">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded bg-emerald-50 text-emerald-700 flex items-center justify-center font-bold font-mono">
                  {selectedForensicHolding.piotroski}/9
                </div>
                <div>
                  <h3 className="text-base font-bold text-slate-900">
                    {selectedForensicHolding.symbol} — Forensic Health Matrix
                  </h3>
                  <p className="text-xs text-slate-500">9-Point Piotroski F-Score Decomposition</p>
                </div>
              </div>
              <button
                onClick={() => setSelectedForensicHolding(null)}
                className="p-1 rounded text-slate-400 hover:text-slate-600 hover:bg-slate-100"
              >
                <X size={18} />
              </button>
            </div>

            <div className="space-y-2 text-xs font-mono">
              <div className="text-[11px] font-bold text-slate-400 uppercase tracking-wider font-sans">
                Profitability & Cash Generation (4 Points)
              </div>
              <div className="p-2.5 bg-slate-50 rounded border border-slate-200 space-y-1">
                <div className="flex justify-between">
                  <span>Return on Assets (ROA &gt; 0):</span>
                  <span className="text-emerald-700 font-bold">PASS (+1)</span>
                </div>
                <div className="flex justify-between">
                  <span>Operating Cash Flow (CFO &gt; 0):</span>
                  <span className="text-emerald-700 font-bold">PASS (+1)</span>
                </div>
                <div className="flex justify-between">
                  <span>Accruals Quality (CFO &gt; Net Income):</span>
                  <span className="text-emerald-700 font-bold">PASS (+1)</span>
                </div>
                <div className="flex justify-between">
                  <span>Δ ROA (YoY Expansion):</span>
                  <span className="text-emerald-700 font-bold">PASS (+1)</span>
                </div>
              </div>

              <div className="text-[11px] font-bold text-slate-400 uppercase tracking-wider font-sans pt-1">
                Leverage, Liquidity & Solvency (3 Points)
              </div>
              <div className="p-2.5 bg-slate-50 rounded border border-slate-200 space-y-1">
                <div className="flex justify-between">
                  <span>Δ Long-term Debt Ratio (Decreased):</span>
                  <span className="text-emerald-700 font-bold">PASS (+1)</span>
                </div>
                <div className="flex justify-between">
                  <span>Δ Current Ratio (Higher Liquidity):</span>
                  <span className="text-emerald-700 font-bold">PASS (+1)</span>
                </div>
                <div className="flex justify-between">
                  <span>Zero Equity Dilution (No Fresh Shares):</span>
                  <span className="text-emerald-700 font-bold">PASS (+1)</span>
                </div>
              </div>

              <div className="text-[11px] font-bold text-slate-400 uppercase tracking-wider font-sans pt-1">
                Operating Efficiency (2 Points)
              </div>
              <div className="p-2.5 bg-slate-50 rounded border border-slate-200 space-y-1">
                <div className="flex justify-between">
                  <span>Δ Gross Margin (Pricing Power):</span>
                  <span className="text-emerald-700 font-bold">PASS (+1)</span>
                </div>
                <div className="flex justify-between">
                  <span>Δ Asset Turnover (Operational Speed):</span>
                  <span className="text-slate-500 font-medium">NEUTRAL (0)</span>
                </div>
              </div>
            </div>

            <div className="pt-2 flex items-center justify-between">
              <span className="text-xs font-semibold text-emerald-700 bg-emerald-50 px-2.5 py-1 rounded border border-emerald-200">
                Classification: High Quality Institutional Compounder
              </span>
              <Link
                href={`/analyse/${selectedForensicHolding.symbol}`}
                className="px-3.5 py-1.5 text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 rounded-md"
              >
                View Full Audit
              </Link>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
