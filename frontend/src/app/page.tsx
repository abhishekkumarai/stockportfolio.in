"use client";

import { useState, useEffect, useRef, useMemo } from "react";
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
  SlidersHorizontal,
  Layers,
  Sparkles,
} from "lucide-react";
import { apiUrl } from "@/lib/api";
import {
  loadPortfolio,
  analysePortfolio,
  StoredPortfolio,
  FullAnalysisResponse,
  formatCurrency,
  formatPct,
} from "@/lib/portfolioApi";

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
  varContrib: string | null;
  piotroski: number | null;
  piotroskiLabel: string | null;
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

  // Keyboard shortcut listener to dismiss modals on Escape
  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setIsRebalanceModalOpen(false);
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  // Dynamic Portfolio State from persistent storage & backend analysis
  const [portfolio, setPortfolio] = useState<StoredPortfolio>({ equity: [], funds: [], cash: 0 });
  const [analysis, setAnalysis] = useState<FullAnalysisResponse | null>(null);
  const [isPortfolioLoading, setIsPortfolioLoading] = useState(true);
  const [portfolioError, setPortfolioError] = useState<string | null>(null);

  const refreshPortfolio = async () => {
    try {
      const p = loadPortfolio();
      setPortfolio(p);
      if (p.equity.length > 0 || p.funds.length > 0) {
        setIsPortfolioLoading(true);
        const res = await analysePortfolio(p.equity, p.funds, p.cash);
        setAnalysis(res);
        setPortfolioError(null);
      } else {
        setAnalysis(null);
        setPortfolioError(null);
      }
    } catch (err) {
      console.error("Failed to load or analyse portfolio:", err);
      setPortfolioError(
        err instanceof Error ? err.message : "Could not analyse your portfolio. Please try again."
      );
    } finally {
      setIsPortfolioLoading(false);
    }
  };

  useEffect(() => {
    refreshPortfolio();

    const handlePortfolioUpdated = () => {
      refreshPortfolio();
    };

    window.addEventListener("portfolio-updated", handlePortfolioUpdated);
    window.addEventListener("storage", handlePortfolioUpdated);

    return () => {
      window.removeEventListener("portfolio-updated", handlePortfolioUpdated);
      window.removeEventListener("storage", handlePortfolioUpdated);
    };
  }, []);

  // Map dynamic portfolio data to HoldingItem structure
  const holdings: HoldingItem[] = useMemo(() => {
    if (analysis?.valuation?.holdings && analysis.valuation.holdings.length > 0) {
      return analysis.valuation.holdings.map((h) => {
        const pnl = h.pnl ?? (h.current_value !== null ? h.current_value - h.invested : 0);
        const pnlPct = h.pnl_pct ?? (h.invested > 0 ? (pnl / h.invested) * 100 : 0);
        const ltp = h.price ?? (h.quantity > 0 ? (h.current_value ?? h.invested) / h.quantity : h.avg_cost);
        const totalVal = h.current_value ?? h.quantity * ltp;
        const weight = h.weight_pct !== null ? Number(h.weight_pct.toFixed(1)) : 0;
        return {
          symbol: h.key,
          name: h.name || h.key,
          sector: h.sector || (h.kind === "fund" ? "Mutual Fund" : "Equity"),
          weight,
          qty: h.quantity,
          avgBuy: h.avg_cost,
          ltp,
          totalValue: totalVal,
          unrealizedPnL: pnl,
          unrealizedPnLPct: Number(pnlPct.toFixed(2)),
          varContrib: null,
          piotroski: null,
          piotroskiLabel: null,
          catalyst:
            h.warnings && h.warnings.length > 0
              ? h.warnings[0]
              : h.kind === "fund"
              ? "Direct Growth NAV"
              : "Active Core Holding",
          lockWarning: h.warnings?.find(
            (w) =>
              w.toLowerCase().includes("lock") ||
              w.toLowerCase().includes("tax") ||
              w.toLowerCase().includes("ltcg")
          ),
        };
      });
    }

    if (portfolio.equity.length > 0 || portfolio.funds.length > 0) {
      const eqItems: HoldingItem[] = portfolio.equity.map((eq) => ({
        symbol: eq.symbol,
        name: eq.symbol,
        sector: "Equity",
        weight: 0,
        qty: eq.quantity,
        avgBuy: eq.avg_cost,
        ltp: eq.avg_cost,
        totalValue: eq.quantity * eq.avg_cost,
        unrealizedPnL: 0,
        unrealizedPnLPct: 0,
        varContrib: null,
        piotroski: null,
        piotroskiLabel: null,
        catalyst: "Imported Holding",
      }));
      const mfItems: HoldingItem[] = portfolio.funds.map((mf) => ({
        symbol: `MF-${mf.scheme_code}`,
        name: `Scheme ${mf.scheme_code}`,
        sector: "Mutual Fund",
        weight: 0,
        qty: mf.units,
        avgBuy: mf.avg_nav,
        ltp: mf.avg_nav,
        totalValue: mf.units * mf.avg_nav,
        unrealizedPnL: 0,
        unrealizedPnLPct: 0,
        varContrib: null,
        piotroski: null,
        piotroskiLabel: null,
        catalyst: "SIP Direct Scheme",
      }));
      const combined = [...eqItems, ...mfItems];
      const sumVal = combined.reduce((acc, c) => acc + c.totalValue, 0);
      if (sumVal > 0) {
        combined.forEach((c) => {
          c.weight = Number(((c.totalValue / sumVal) * 100).toFixed(1));
        });
      }
      return combined;
    }

    return [];
  }, [analysis, portfolio]);

  // Derived Totals
  const totalCurrentValue =
    analysis?.valuation?.totals?.current_value ??
    holdings.reduce((sum, h) => sum + h.totalValue, 0) + (portfolio.cash || 0);

  const totalInvested =
    analysis?.valuation?.totals?.invested ??
    holdings.reduce((sum, h) => sum + h.qty * h.avgBuy, 0);

  const totalPnL =
    analysis?.valuation?.totals?.pnl ?? totalCurrentValue - totalInvested;

  const totalPnLPct =
    analysis?.valuation?.totals?.pnl_pct ??
    (totalInvested > 0 ? (totalPnL / totalInvested) * 100 : 0);

  // Available unique sectors
  const availableSectors = useMemo(() => {
    return Array.from(new Set(holdings.map((h) => h.sector).filter(Boolean)));
  }, [holdings]);

  // Filtered holdings
  const filteredHoldings = holdings.filter((item) => {
    const matchesSector = selectedSector === "all" || item.sector === selectedSector;
    const matchesSearch =
      item.symbol.toLowerCase().includes(tableSearch.toLowerCase()) ||
      item.name.toLowerCase().includes(tableSearch.toLowerCase());
    return matchesSector && matchesSearch;
  });

  // Table density state
  const [isCompactDensity, setIsCompactDensity] = useState(false);

  // Top Alpha Picks (Decile 10) Dataset
  const alphaPicks = [
    {
      symbol: "TRENT",
      name: "Trent Ltd",
      sector: "Retail & Consumption",
      decile: "Decile 10",
      expectedAlpha: "+4.62%",
      momentumScore: 99,
      piotroski: 8,
      peRatio: 112.4,
      rocePct: 28.4,
      catalyst: "Zudio Tier-2/3 Rapid Store Rollout",
      sentiment: "Strong Bullish",
    },
    {
      symbol: "BEL",
      name: "Bharat Electronics Ltd",
      sector: "Defense & Aerospace",
      decile: "Decile 10",
      expectedAlpha: "+4.18%",
      momentumScore: 96,
      piotroski: 9,
      peRatio: 42.5,
      rocePct: 31.2,
      catalyst: "Indigenous Defense Capex Supercycle",
      sentiment: "Strong Bullish",
    },
    {
      symbol: "DIXON",
      name: "Dixon Technologies",
      sector: "Electronics EMS",
      decile: "Decile 10",
      expectedAlpha: "+3.95%",
      momentumScore: 94,
      piotroski: 8,
      peRatio: 88.2,
      rocePct: 26.5,
      catalyst: "Smartphone PLI & Display Component Localization",
      sentiment: "Bullish",
    },
    {
      symbol: "PERSISTENT",
      name: "Persistent Systems",
      sector: "IT & Software",
      decile: "Decile 10",
      expectedAlpha: "+3.82%",
      momentumScore: 92,
      piotroski: 8,
      peRatio: 54.0,
      rocePct: 25.1,
      catalyst: "Generative AI Enterprise Spend & Cloud Modernization",
      sentiment: "Bullish",
    },
    {
      symbol: "POLYCAB",
      name: "Polycab India Ltd",
      sector: "Industrials & Cables",
      decile: "Decile 10",
      expectedAlpha: "+3.65%",
      momentumScore: 91,
      piotroski: 9,
      peRatio: 46.8,
      rocePct: 29.8,
      catalyst: "Grid Modernization & Renewable Power T&D Boom",
      sentiment: "Strong Bullish",
    },
    {
      symbol: "SUZLON",
      name: "Suzlon Energy Ltd",
      sector: "Energy & Power",
      decile: "Decile 10",
      expectedAlpha: "+3.45%",
      momentumScore: 89,
      piotroski: 7,
      peRatio: 58.4,
      rocePct: 24.2,
      catalyst: "Record 5.4GW Wind Energy Order Book",
      sentiment: "Bullish",
    },
  ];

  // Option Chain Matrix Dataset (ATM 24,850)
  const optionChain = [
    {
      strike: 24500,
      tag: "Put Wall Support (1.85 Cr OI)",
      callOi: "22.4L",
      callOiChg: "-1.2L",
      callIv: "12.5%",
      callLtp: 395.2,
      putLtp: 28.5,
      putIv: "14.8%",
      putOiChg: "+38.2L",
      putOi: "185.2L",
      isPutWall: true,
    },
    {
      strike: 24600,
      tag: "",
      callOi: "34.2L",
      callOiChg: "+2.1L",
      callIv: "12.8%",
      callLtp: 312.4,
      putLtp: 42.1,
      putIv: "14.1%",
      putOiChg: "+14.5L",
      putOi: "88.5L",
    },
    {
      strike: 24700,
      tag: "",
      callOi: "45.6L",
      callOiChg: "+5.4L",
      callIv: "13.0%",
      callLtp: 228.8,
      putLtp: 64.5,
      putIv: "13.8%",
      putOiChg: "+18.2L",
      putOi: "102.3L",
    },
    {
      strike: 24800,
      tag: "Max Pain Strike",
      callOi: "62.8L",
      callOiChg: "+14.2L",
      callIv: "13.2%",
      callLtp: 152.6,
      putLtp: 96.2,
      putIv: "13.5%",
      putOiChg: "+22.4L",
      putOi: "145.2L",
      isMaxPain: true,
    },
    {
      strike: 24850,
      tag: "ATM Straddle Pivot",
      callOi: "78.4L",
      callOiChg: "+22.1L",
      callIv: "13.4%",
      callLtp: 118.5,
      putLtp: 119.8,
      putIv: "13.4%",
      putOiChg: "+24.5L",
      putOi: "138.9L",
      isAtm: true,
    },
    {
      strike: 24900,
      tag: "",
      callOi: "95.1L",
      callOiChg: "+31.4L",
      callIv: "13.6%",
      callLtp: 88.2,
      putLtp: 148.4,
      putIv: "13.2%",
      putOiChg: "-6.4L",
      putOi: "115.4L",
    },
    {
      strike: 25000,
      tag: "Call Wall Resistance / Collar Leg",
      callOi: "142.5L",
      callOiChg: "+48.2L",
      callIv: "14.1%",
      callLtp: 46.2,
      putLtp: 215.1,
      putIv: "13.0%",
      putOiChg: "-12.1L",
      putOi: "72.1L",
      isCallWall: true,
    },
    {
      strike: 25100,
      tag: "",
      callOi: "88.2L",
      callOiChg: "+16.5L",
      callIv: "14.5%",
      callLtp: 24.1,
      putLtp: 298.0,
      putIv: "12.9%",
      putOiChg: "-8.5L",
      putOi: "41.6L",
    },
  ];

  // Strategy Backtest Logs Dataset
  const backtestLogs = [
    {
      strategy: "Dual-Factor Alpha (Momentum + Piotroski)",
      benchmark: "Nifty 500 TRI",
      isSharpe: 2.38,
      oosSharpe: 1.94,
      sampleRatio: "0.82",
      maxDrawdown: "-6.4%",
      winRate: "64.2%",
      annualizedReturn: "+28.6%",
      rebalanceFreq: "Monthly",
      status: "Active Production",
    },
    {
      strategy: "Hierarchical Risk Parity (HRP Min-VaR)",
      benchmark: "Nifty 50 Equal Weight",
      isSharpe: 2.12,
      oosSharpe: 1.88,
      sampleRatio: "0.89",
      maxDrawdown: "-4.8%",
      winRate: "59.8%",
      annualizedReturn: "+19.4%",
      rebalanceFreq: "Quarterly",
      status: "Active Production",
    },
    {
      strategy: "Volatility-Adjusted Tail Collar (Systematic Hedge)",
      benchmark: "Cash + Nifty Put",
      isSharpe: 1.62,
      oosSharpe: 1.58,
      sampleRatio: "0.98",
      maxDrawdown: "-3.2%",
      winRate: "71.4%",
      annualizedReturn: "+13.8%",
      rebalanceFreq: "Expiry-Cycle",
      status: "Active Hedge",
    },
    {
      strategy: "RSI Mean Reversion + Bollinger Band Bounce",
      benchmark: "Nifty Bank",
      isSharpe: 1.76,
      oosSharpe: 1.34,
      sampleRatio: "0.76",
      maxDrawdown: "-11.2%",
      winRate: "52.1%",
      annualizedReturn: "+15.2%",
      rebalanceFreq: "Weekly",
      status: "Paper Trading",
    },
  ];

  // Filtered alpha picks
  const filteredAlphaPicks = alphaPicks.filter((item) => {
    const matchesSector = selectedSector === "all" || item.sector.toLowerCase().includes(selectedSector.toLowerCase().split(" ")[0]);
    const matchesSearch =
      item.symbol.toLowerCase().includes(tableSearch.toLowerCase()) ||
      item.name.toLowerCase().includes(tableSearch.toLowerCase());
    return matchesSector && matchesSearch;
  });

  // Export CSV Handler
  const handleExportCSV = () => {
    let csvContent = "data:text/csv;charset=utf-8,";
    if (activeTableTab === "holdings") {
      csvContent += "Symbol,Name,Sector,Weight(%),Qty,Avg Buy,LTP,Total Value,Unrealized PnL,VaR,Piotroski,Catalyst\n";
      filteredHoldings.forEach((h) => {
        csvContent += `"${h.symbol}","${h.name}","${h.sector}",${h.weight},${h.qty},${h.avgBuy},${h.ltp},${h.totalValue},${h.unrealizedPnL},"${h.varContrib ?? "N/A"}","${h.piotroski != null ? `${h.piotroski}/9` : "N/A"}","${h.catalyst}"\n`;
      });
    } else if (activeTableTab === "alpha") {
      csvContent += "Symbol,Name,Sector,Decile,Expected Alpha,Momentum,Piotroski,PE,ROCE,Catalyst\n";
      filteredAlphaPicks.forEach((a) => {
        csvContent += `"${a.symbol}","${a.name}","${a.sector}","${a.decile}","${a.expectedAlpha}",${a.momentumScore},"${a.piotroski}/9",${a.peRatio},${a.rocePct},"${a.catalyst}"\n`;
      });
    } else if (activeTableTab === "options") {
      csvContent += "Call OI,Call Chg,Call IV,Call LTP,Strike,Put LTP,Put IV,Put Chg,Put OI\n";
      optionChain.forEach((o) => {
        csvContent += `"${o.callOi}","${o.callOiChg}","${o.callIv}",${o.callLtp},${o.strike},${o.putLtp},"${o.putIv}","${o.putOiChg}","${o.putOi}"\n`;
      });
    } else {
      csvContent += "Strategy,Benchmark,IS Sharpe,OOS Sharpe,Sample Ratio,Max DD,Win Rate,CAGR,Status\n";
      backtestLogs.forEach((b) => {
        csvContent += `"${b.strategy}","${b.benchmark}",${b.isSharpe},${b.oosSharpe},"${b.sampleRatio}","${b.maxDrawdown}","${b.winRate}","${b.annualizedReturn}","${b.status}"\n`;
      });
    }
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `stockportfolio_${activeTableTab}_${new Date().toISOString().slice(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="w-full max-w-full overflow-x-hidden p-4 sm:p-6 space-y-6">

      {portfolioError && (
        <div className="flex items-center gap-2 px-4 py-2.5 rounded-lg border border-red-200 bg-red-50 text-red-800 text-xs">
          <AlertTriangle size={15} className="shrink-0" />
          <span>{portfolioError}</span>
          <button
            onClick={refreshPortfolio}
            className="ml-auto font-semibold underline hover:no-underline"
          >
            Retry
          </button>
        </div>
      )}

      {/* 1. TOP TITLE BANNER & INSTITUTIONAL DISPATCH ACTIONS */}
      <div className="flex flex-col xl:flex-row xl:items-center justify-between gap-4 pb-6 border-b border-slate-200 mb-2">
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
        <div className="flex flex-wrap items-center gap-2 sm:gap-2.5">
          <button
            onClick={() => router.push("/portfolio/holdings")}
            className="inline-flex items-center gap-1.5 px-3 py-2 text-xs font-medium text-slate-800 bg-white hover:bg-slate-50 rounded-md border border-slate-300 shadow-sm transition-all"
            title="Connect your broker or import a statement on the Portfolio page"
          >
            <RefreshCw size={14} className="text-slate-500" />
            <span>Import / Sync Broker Holdings</span>
          </button>
          <button
            onClick={handleExportCSV}
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
                Portfolio NAV & Valuation
              </span>
              <PieChart size={16} className="text-slate-400" />
            </div>
            <div className="text-2xl font-bold font-mono text-slate-900 tracking-tight tabular-nums">
              {formatCurrency(totalCurrentValue)}
            </div>
            <div className="mt-1.5 flex items-center gap-1.5">
              <span className={`text-xs font-mono font-semibold px-2 py-0.5 rounded border tabular-nums flex items-center gap-1 ${
                totalPnL >= 0
                  ? "text-emerald-700 bg-emerald-50 border-emerald-200"
                  : "text-red-700 bg-red-50 border-red-200"
              }`}>
                {totalPnL >= 0 ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
                {totalPnL >= 0 ? "+" : ""}{formatCurrency(totalPnL)} ({formatPct(totalPnLPct)}) Total
              </span>
            </div>
          </div>
          <div className="mt-3.5 pt-2.5 border-t border-slate-100 text-[11px] font-mono text-slate-500 space-y-1">
            <div className="flex justify-between">
              <span>Invested Capital:</span>
              <span className="font-semibold text-slate-800">{formatCurrency(totalInvested)}</span>
            </div>
            <div className="flex justify-between items-center text-[10.5px]">
              <span>Cash Buffer: <strong className="text-slate-800 font-semibold">{formatCurrency(portfolio.cash || 0)}</strong></span>
              <span className="px-1.5 py-0.2 rounded bg-slate-100 text-slate-700 font-semibold">{holdings.length} Positions</span>
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
            <div className="text-2xl font-bold font-mono text-slate-400 tracking-tight tabular-nums">
              See Tax Rebalance
            </div>
            <div className="mt-1.5 flex items-center gap-1.5">
              <span className="text-xs font-mono font-medium text-slate-500 bg-slate-50 px-2 py-0.5 rounded border border-slate-200">
                Computed on the Tax Rebalance page
              </span>
            </div>
          </div>
          <div className="mt-3.5 pt-2.5 border-t border-slate-100 text-[11px] font-mono text-slate-500 space-y-1">
            <div className="flex justify-between items-center">
              <span>LTCG Protected Positions:</span>
              <span className="text-amber-700 font-semibold text-[10px] bg-amber-50 px-1.5 py-0.2 rounded border border-amber-200">
                {holdings.filter((h) => h.lockWarning).length} Locked
              </span>
            </div>
            <Link href="/portfolio/rebalance" className="text-[10.5px] text-blue-600 hover:underline">
              Open tax-aware rebalance →
            </Link>
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
            <div className="text-2xl font-bold font-mono text-slate-400 tracking-tight tabular-nums">
              See Tail Risk Sizer
            </div>
            <div className="mt-1.5 flex items-center gap-1.5">
              <span className="text-xs font-mono font-medium text-slate-500 bg-slate-50 px-2 py-0.5 rounded border border-slate-200">
                Computed on the Options page
              </span>
            </div>
          </div>
          <div className="mt-3.5 pt-2.5 border-t border-slate-100 text-[11px] font-mono text-slate-500 space-y-1">
            <div className="flex justify-between items-center">
              <span>Portfolio NAV base:</span>
              <span className="font-semibold text-slate-800">{formatCurrency(totalCurrentValue)}</span>
            </div>
            <Link href="/options/tail-risk" className="text-[10.5px] text-blue-600 hover:underline">
              Open tail risk sizer →
            </Link>
          </div>
        </div>

        {/* Card 4: Quantitative ML Alpha & Risk */}
        <div className="bg-white border border-slate-200 rounded-lg p-4 shadow-[0_1px_2px_0_rgba(15,23,42,0.04)] flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-[10.5px] font-mono font-semibold uppercase text-slate-500 tracking-wider">
                Portfolio Risk (VaR &amp; Beta)
              </span>
              <Activity size={16} className="text-blue-600" />
            </div>
            <div className="text-2xl font-bold font-mono text-slate-900 tracking-tight tabular-nums">
              {analysis?.danger?.metrics?.monthly_var_95_pct
                ? `${(analysis.danger.metrics.monthly_var_95_pct / 4).toFixed(2)}% VaR`
                : "— VaR"}
            </div>
            <div className="mt-1.5 flex items-center gap-1.5">
              <span className="text-xs font-mono font-semibold text-blue-700 bg-blue-50 px-2 py-0.5 rounded border border-blue-200">
                {analysis?.danger?.metrics?.portfolio_beta
                  ? `Beta: ${analysis.danger.metrics.portfolio_beta.toFixed(2)} vs NIFTY`
                  : "Add holdings for beta"}
              </span>
            </div>
          </div>
          <div className="mt-3.5 pt-2.5 border-t border-slate-100 text-[11px] font-mono text-slate-500 space-y-1">
            <div className="flex justify-between">
              <span>Hist VaR (95%, 1D):</span>
              <span className="font-semibold text-slate-800">
                {analysis?.danger?.metrics?.monthly_var_95_pct
                  ? `${(analysis.danger.metrics.monthly_var_95_pct / 4).toFixed(2)}% (${formatCurrency(totalCurrentValue * (analysis.danger.metrics.monthly_var_95_pct / 400))})`
                  : "Not yet computed"}
              </span>
            </div>
            <Link href="/recommendations" className="text-[10.5px] text-blue-600 hover:underline">
              View ML alpha rankings →
            </Link>
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
                <div className="flex items-center gap-2">
                  <h2 className="text-sm font-bold text-slate-900">Multi-Model Visual Analytics Console</h2>
                  <span
                    className="text-[9px] font-mono uppercase px-1.5 py-0.5 rounded bg-amber-50 text-amber-700 border border-amber-200"
                    title="This chart illustrates a fixed growth-rate assumption, not a Monte Carlo simulation run against your actual holdings"
                  >
                    Illustrative
                  </span>
                </div>
                <p className="text-[11px] text-slate-500">Illustrative 10-year compounding projection at an assumed CAGR — not a simulation of your actual holdings</p>
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
                      <span className="text-slate-600 text-[11px]">95th %ile (Bull): <strong className="text-slate-900 font-semibold">{totalCurrentValue > 0 ? formatCurrency(totalCurrentValue * 6.0) : "₹0"}</strong></span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <span className="w-3 h-0.5 bg-blue-600 rounded-full"></span>
                      <span className="text-slate-600 text-[11px]">50th %ile (Median): <strong className="text-slate-900 font-semibold">{totalCurrentValue > 0 ? formatCurrency(totalCurrentValue * 3.8) : "₹0"}</strong></span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <span className="w-3 h-0.5 bg-red-600 rounded-full"></span>
                      <span className="text-slate-600 text-[11px]">5th %ile (Bear): <strong className="text-slate-900 font-semibold">{totalCurrentValue > 0 ? formatCurrency(totalCurrentValue * 2.4) : "₹0"}</strong></span>
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
                    <text x="35" y="184" textAnchor="end" fontSize="9" fill="#94A3B8" fontFamily="JetBrains Mono">{totalCurrentValue > 0 ? formatCurrency(totalCurrentValue) : "₹0"}</text>

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
                    <text x="582" y="72" textAnchor="middle" fontSize="9.5" fill="#FFFFFF" fontFamily="JetBrains Mono" fontWeight="700">{totalCurrentValue > 0 ? formatCurrency(totalCurrentValue * 3.8) + " Med" : "₹0 Med"}</text>

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
                  <div>Downside Floor: <strong className="text-slate-800 font-semibold">{totalCurrentValue > 0 ? formatCurrency(totalCurrentValue * 2.4) : "₹0"}</strong></div>
                </div>
              </div>
            )}

            {/* TAB 2: Strategy Lab v2 Walk-Forward Metrics */}
            {activeVisualTab === "lab" && (
              <div className="mt-4 bg-slate-50 rounded-lg border border-slate-200 p-4 space-y-3 font-mono text-xs">
                <div className="flex items-center justify-between pb-2 border-b border-slate-200 gap-2">
                  <span className="font-semibold text-slate-800">Sample Walk-Forward Output</span>
                  <span className="text-amber-700 bg-amber-50 px-2 py-0.5 rounded border border-amber-200 font-bold">
                    Illustrative — run your own in Strategy Lab
                  </span>
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
                <div className="flex items-center justify-between pb-2 border-b border-slate-200 gap-2">
                  <span className="font-semibold text-slate-800">Sample OI Wall Layout</span>
                  <span className="text-amber-700 bg-amber-50 px-2 py-0.5 rounded border border-amber-200 font-bold">
                    Illustrative — see live chain on Options
                  </span>
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
            {/* Mini Footer Metrics */}
            <div className="mt-4 pt-3 border-t border-slate-200 grid grid-cols-3 gap-2 text-center text-xs font-mono">
              <div className="p-2 bg-slate-50 rounded border border-slate-200">
                <span className="text-[10px] text-slate-400 block uppercase">Expected Volatility</span>
                <span className="text-xs font-bold text-slate-900">
                  {analysis?.growth?.pillars?.expected_volatility_pct != null
                    ? `${analysis.growth.pillars.expected_volatility_pct.toFixed(1)}%`
                    : "—"}
                </span>
              </div>
              <div className="p-2 bg-slate-50 rounded border border-slate-200">
                <span className="text-[10px] text-slate-400 block uppercase">Monthly CVaR (95%)</span>
                <span className="text-xs font-bold text-red-600">
                  {analysis?.danger?.metrics?.monthly_cvar_95_pct != null
                    ? `${analysis.danger.metrics.monthly_cvar_95_pct.toFixed(2)}%`
                    : "—"}
                </span>
              </div>
              <div className="p-2 bg-slate-50 rounded border border-slate-200">
                <span className="text-[10px] text-slate-400 block uppercase">Projected CAGR</span>
                <span className="text-xs font-bold text-emerald-600">
                  {analysis?.growth?.pillars?.projected_cagr_pct != null
                    ? `${analysis.growth.pillars.projected_cagr_pct.toFixed(1)}%`
                    : "—"}
                </span>
              </div>
            </div>
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
              <span className="text-[10px] font-mono font-semibold px-2 py-0.5 rounded bg-slate-100 text-slate-500 border border-slate-200">
                Preview
              </span>
            </div>

            {/* Zero-Tax Fresh Capital Allocator — real computation lives on /portfolio/rebalance */}
            {holdings.length === 0 ? (
              <div className="mt-3.5 p-4 rounded-lg border border-slate-200 bg-slate-50 text-center space-y-2">
                <div className="text-xs font-semibold text-slate-800">No Active Positions to Rebalance</div>
                <p className="text-[11px] text-slate-500">
                  Connect your broker or import a statement on the Portfolio page to compute zero-tax fresh capital inflows.
                </p>
                <Link
                  href="/portfolio/holdings"
                  className="inline-flex items-center gap-1 px-3 py-1.5 bg-blue-600 text-white rounded text-xs font-semibold hover:bg-blue-700 transition"
                >
                  <span>Go to Portfolio</span>
                  <ChevronRight size={13} />
                </Link>
              </div>
            ) : (
              <div className="mt-3.5 p-3 rounded-lg border border-blue-200 bg-blue-50/60 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-slate-900 flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-blue-600"></span>
                    Zero-Tax Fresh Capital Inflow
                  </span>
                </div>
                <p className="text-[11px] text-slate-600">
                  The exact per-holding allocation for new cash is computed on the Tax Rebalance page, using your
                  live valuation and the tax-aware rebalance engine.
                </p>
                <Link href="/portfolio/rebalance" className="text-[11px] text-blue-600 hover:underline font-semibold">
                  Compute allocation →
                </Link>
              </div>
            )}

            {/* Amber 30-Day LTCG Proximity Gate Warning */}
            {holdings.filter((h) => h.lockWarning).length > 0 ? (
              <div className="mt-3 p-3 rounded-lg border border-amber-200 bg-amber-50/70 text-xs text-amber-950 space-y-1.5">
                <div className="flex items-center gap-1.5 font-semibold text-amber-900">
                  <Lock size={14} className="text-amber-700" />
                  <span>30-Day LTCG Proximity Gate Alert</span>
                </div>
                <p className="text-[11px] leading-relaxed text-amber-900">
                  <strong>{holdings.filter((h) => h.lockWarning).map((h) => h.symbol).join(", ")}</strong> positions are within proximity of the 12-month holding mark. Selling now triggers 20% STCG; holding unlocks 12.5% LTCG.
                </p>
                <div className="font-mono text-[10.5px] text-amber-800 font-semibold">
                  Protected from rebalance trims to optimize capital gains tax.
                </div>
              </div>
            ) : (
              <div className="mt-3 p-3 rounded-lg border border-slate-200 bg-slate-50 text-xs text-slate-600 space-y-1">
                <div className="flex items-center gap-1.5 font-semibold text-slate-800">
                  <Lock size={14} className="text-slate-500" />
                  <span>30-Day LTCG Proximity Gate Alert</span>
                </div>
                <p className="text-[11px] text-slate-500">
                  {holdings.length > 0
                    ? "All active positions are clear of the 30-day LTCG threshold window."
                    : "No positions loaded to check for LTCG proximity."}
                </p>
              </div>
            )}

            {/* Collar Sizer — real computation lives on /options/tail-risk */}
            <div className="mt-3 p-3 rounded-lg border border-slate-200 bg-slate-50 space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="font-semibold text-slate-800 flex items-center gap-1">
                  <Shield size={14} className="text-blue-600" />
                  Protective Collar Sizer
                </span>
              </div>
              <p className="text-[11px] text-slate-500">
                Strike selection and net debit/credit are computed against the live options chain on the Tail Risk
                Sizer page.
              </p>
              <Link href="/options/tail-risk" className="text-[11px] text-blue-600 hover:underline font-semibold">
                Size a hedge →
              </Link>
            </div>
          </div>

          {/* Primary Action Button */}
          <div>
            <button
              onClick={() => setIsRebalanceModalOpen(true)}
              className="w-full py-2.5 px-4 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold rounded-md shadow-sm flex items-center justify-center gap-2 transition-all active:scale-[0.99]"
            >
              <Zap size={15} />
              <span>Preview Rebalance & Hedge Basket</span>
            </button>
            <div className="mt-1.5 text-center text-[10px] text-slate-400 font-mono">
              This preview does not place a real order — orders are not yet supported
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
              {availableSectors.length > 0 ? (
                availableSectors.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))
              ) : (
                <>
                  <option value="Energy & Telecom">Energy & Telecom</option>
                  <option value="Banking & NBFC">Banking & NBFC</option>
                  <option value="IT & Software">IT & Software</option>
                  <option value="Retail & Consumption">Retail & Consumption</option>
                </>
              )}
            </select>

            {/* Density Button */}
            <button
              onClick={() => setIsCompactDensity(!isCompactDensity)}
              className={`h-8 px-2.5 bg-white hover:bg-slate-50 text-xs rounded border transition-colors inline-flex items-center gap-1.5 ${
                isCompactDensity ? "border-blue-500 text-blue-700 bg-blue-50/50 font-semibold" : "border-slate-300 text-slate-700"
              }`}
              title="Toggle Row Padding Density"
            >
              <SlidersHorizontal size={14} className={isCompactDensity ? "text-blue-600" : "text-slate-500"} />
              <span>Density</span>
              {isCompactDensity && <span className="text-[10px] font-bold text-blue-600 font-mono">(Compact)</span>}
            </button>

            {/* Export CSV Button */}
            <button
              onClick={handleExportCSV}
              className="h-8 px-2.5 bg-white hover:bg-slate-50 text-slate-700 text-xs rounded border border-slate-300 inline-flex items-center gap-1.5 transition-colors"
              title="Export Current Table as CSV"
            >
              <Download size={14} className="text-slate-500" />
              <span>Export CSV</span>
            </button>
          </div>
        </div>

        {/* ============================================================ */}
        {/* TAB 1: ACTIVE PORTFOLIO HOLDINGS & FORENSICS                 */}
        {/* ============================================================ */}
        {activeTableTab === "holdings" && (
          <>
            {holdings.length === 0 ? (
              <div className="py-16 px-4 text-center">
                <div className="w-12 h-12 rounded-full bg-blue-50 text-blue-600 flex items-center justify-center mx-auto mb-3">
                  <Layers size={24} />
                </div>
                <h3 className="text-sm font-bold text-slate-900">No Portfolio Holdings Loaded</h3>
                <p className="text-xs text-slate-500 max-w-md mx-auto mt-1 mb-4">
                  Your institutional terminal currently has 0 active positions. Connect with Fyers or import an offline portfolio statement (.xlsx) in User Profile &amp; Auth to inspect live forensics, tax optimization, and wealth projections.
                </p>
                <Link
                  href="/auth"
                  className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold rounded-md shadow-xs transition"
                >
                  <span>Import Portfolio / Connect Broker</span>
                  <ChevronRight size={14} />
                </Link>
              </div>
            ) : filteredHoldings.length === 0 ? (
              <div className="py-12 px-4 text-center text-xs text-slate-500">
                No positions match your current search / sector filter criteria.
              </div>
            ) : (
              <>
                {/* DESKTOP VIEW */}
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
                          <td className={`${isCompactDensity ? "py-1.5 px-4" : "py-3 px-4"}`}>
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
                          <td className={`${isCompactDensity ? "py-1.5 px-3" : "py-3 px-3"}`}>
                            <div className="flex items-center gap-2">
                              <span className="font-mono font-bold text-slate-900 tabular-nums w-10">
                                {item.weight}%
                              </span>
                              <div className="w-16 h-1.5 bg-slate-200 rounded-full overflow-hidden">
                                <div className="h-full bg-blue-600 rounded-full" style={{ width: `${Math.min(100, item.weight * 5)}%` }}></div>
                              </div>
                            </div>
                          </td>

                          <td className={`${isCompactDensity ? "py-1.5 px-3" : "py-3 px-3"} text-right font-mono font-medium text-slate-800 tabular-nums`}>
                            {item.qty}
                          </td>
                          <td className={`${isCompactDensity ? "py-1.5 px-3" : "py-3 px-3"} text-right font-mono text-slate-500 tabular-nums`}>
                            ₹{item.avgBuy.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                          </td>
                          <td className={`${isCompactDensity ? "py-1.5 px-3" : "py-3 px-3"} text-right font-mono font-semibold text-slate-900 tabular-nums`}>
                            ₹{item.ltp.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                          </td>
                          <td className={`${isCompactDensity ? "py-1.5 px-3" : "py-3 px-3"} text-right font-mono font-bold text-slate-900 tabular-nums`}>
                            ₹{item.totalValue.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                          </td>

                          {/* Unrealized P&L */}
                          <td className={`${isCompactDensity ? "py-1.5 px-3" : "py-3 px-3"} text-right font-mono tabular-nums`}>
                            <div className={`font-bold ${item.unrealizedPnL >= 0 ? "text-emerald-600" : "text-red-600"}`}>
                              {item.unrealizedPnL >= 0 ? "+" : ""}₹{item.unrealizedPnL.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                            </div>
                            <div className={`text-[10px] font-semibold ${item.unrealizedPnL >= 0 ? "text-emerald-600" : "text-red-600"}`}>
                              ({item.unrealizedPnL >= 0 ? "+" : ""}{item.unrealizedPnLPct}%)
                            </div>
                          </td>

                          {/* VaR Contrib */}
                          <td className={`${isCompactDensity ? "py-1.5 px-3" : "py-3 px-3"} text-center`}>
                            <span className="font-mono text-xs font-semibold px-1.5 py-0.5 rounded bg-slate-100 text-slate-500 border border-slate-200">
                              {item.varContrib ?? "—"}
                            </span>
                          </td>

                          {/* Fundamentals link — Piotroski/fundamentals scoring isn't computed on this page */}
                          <td className={`${isCompactDensity ? "py-1.5 px-3" : "py-3 px-3"} text-center`}>
                            <Link
                              href={`/analyse/${item.symbol}`}
                              className="font-mono text-[11px] text-slate-400 hover:text-blue-600 underline"
                              title="View this holding's full fundamentals scorecard"
                            >
                              View fundamentals
                            </Link>
                          </td>

                          {/* Catalyst / Signal Tag */}
                          <td className={`${isCompactDensity ? "py-1.5 px-3" : "py-3 px-3"} text-center`}>
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
                          <td className={`${isCompactDensity ? "py-1.5 px-4" : "py-3 px-4"} text-center`}>
                            <div className="flex items-center justify-center gap-1.5">
                              {item.lockWarning ? (
                                <button
                                  disabled
                                  title={`${item.symbol} is protected from rebalance trims: ${item.lockWarning}`}
                                  className="px-2 py-1 bg-amber-50 text-amber-800 border border-amber-300 rounded text-[11px] font-semibold cursor-not-allowed"
                                >
                                  Locked
                                </button>
                              ) : (
                                <button
                                  onClick={() => setIsRebalanceModalOpen(true)}
                                  className="px-2 py-1 bg-blue-50 text-blue-700 hover:bg-blue-100 border border-blue-200 rounded text-[11px] font-semibold transition"
                                >
                                  Rebalance
                                </button>
                              )}
                              <Link
                                href={`/analyse/${item.symbol}`}
                                className="px-2.5 py-1 text-[11px] font-semibold text-slate-600 hover:text-slate-900 hover:bg-slate-100 border border-slate-300 rounded transition"
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

                {/* MOBILE VIEW */}
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
                          <span className={`font-mono text-[10px] font-semibold ml-1 ${item.unrealizedPnL >= 0 ? "text-emerald-600" : "text-red-600"}`}>
                            {item.unrealizedPnL >= 0 ? "+" : ""}{item.unrealizedPnLPct}%
                          </span>
                        </div>
                      </div>

                      <div className="flex items-center justify-between text-[11px] font-mono text-slate-500">
                        <span>{item.qty} Qty @ Avg ₹{item.avgBuy}</span>
                        <span className={`font-bold ${item.unrealizedPnL >= 0 ? "text-emerald-600" : "text-red-600"}`}>
                          {item.unrealizedPnL >= 0 ? "+" : ""}₹{item.unrealizedPnL.toLocaleString("en-IN")}
                        </span>
                      </div>

                      <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-[10px]">
                        <span className="text-slate-400 font-mono">Fundamentals: view Deep Dive</span>
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
              </>
            )}
          </>
        )}

        {/* ============================================================ */}
        {/* TAB 2: NSE 500 TOP ALPHA PICKS (DECILE 10)                   */}
        {/* ============================================================ */}
        {activeTableTab === "alpha" && (
          <>
            <div className="mx-4 mt-3 flex items-center gap-2 text-[11px] font-mono px-3 py-2 rounded border border-amber-200 bg-amber-50 text-amber-800">
              <span className="font-bold uppercase">Sample data</span>
              <span>—</span>
              <span>
                these six names illustrate the layout only. For real, ranked picks see the{" "}
                <Link href="/recommendations" className="underline font-semibold">
                  Ranked Alpha Board
                </Link>
                .
              </span>
            </div>
            {/* DESKTOP VIEW */}
            <div className="hidden md:block overflow-x-auto w-full min-w-0">
              <table className="w-full min-w-[960px] text-left text-xs border-collapse">
                <thead>
                  <tr className="bg-slate-50 border-b border-slate-200 text-[10.5px] font-mono font-semibold uppercase text-slate-500 tracking-wider">
                    <th className="py-2.5 px-4 font-mono">TICKER & ASSET</th>
                    <th className="py-2.5 px-3 font-mono text-center">FACTOR DECILE</th>
                    <th className="py-2.5 px-3 font-mono text-center">MOMENTUM (12M-1M)</th>
                    <th className="py-2.5 px-3 font-mono text-center">PIOTROSKI</th>
                    <th className="py-2.5 px-3 font-mono text-right">P/E & ROCE %</th>
                    <th className="py-2.5 px-3 font-mono text-center">EXPECTED ALPHA</th>
                    <th className="py-2.5 px-3 font-mono">CATALYST / THESIS</th>
                    <th className="py-2.5 px-4 font-mono text-center">QUICK ACTION</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 font-sans">
                  {filteredAlphaPicks.map((pick) => (
                    <tr key={pick.symbol} className="hover:bg-slate-50/80 transition-colors group">
                      <td className={`${isCompactDensity ? "py-1.5 px-4" : "py-3 px-4"}`}>
                        <div className="flex items-center gap-2.5">
                          <div className="w-7 h-7 rounded bg-emerald-50 text-emerald-700 border border-emerald-200 flex items-center justify-center font-mono font-bold text-xs">
                            {pick.symbol.slice(0, 2)}
                          </div>
                          <div>
                            <div className="font-bold text-slate-900 font-mono flex items-center gap-1.5">
                              <span>{pick.symbol}</span>
                              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                            </div>
                            <div className="text-[11px] text-slate-400">
                              {pick.name} • <span className="text-slate-600 font-medium">{pick.sector}</span>
                            </div>
                          </div>
                        </div>
                      </td>

                      <td className={`${isCompactDensity ? "py-1.5 px-3" : "py-3 px-3"} text-center`}>
                        <span className="px-2 py-0.5 rounded-full text-xs font-mono font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
                          {pick.decile}
                        </span>
                      </td>

                      <td className={`${isCompactDensity ? "py-1.5 px-3" : "py-3 px-3"} text-center font-mono font-bold text-slate-800`}>
                        <span className="text-blue-600">{pick.momentumScore}</span>
                        <span className="text-[10px] text-slate-400 font-normal"> / 100</span>
                      </td>

                      <td className={`${isCompactDensity ? "py-1.5 px-3" : "py-3 px-3"} text-center`}>
                        <span className="inline-flex items-center gap-1 font-mono text-xs font-semibold px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
                          {pick.piotroski}/9 Strong
                        </span>
                      </td>

                      <td className={`${isCompactDensity ? "py-1.5 px-3" : "py-3 px-3"} text-right font-mono tabular-nums`}>
                        <div className="text-slate-800 font-semibold">{pick.peRatio}x P/E</div>
                        <div className="text-[10px] text-emerald-600 font-semibold">{pick.rocePct}% ROCE</div>
                      </td>

                      <td className={`${isCompactDensity ? "py-1.5 px-3" : "py-3 px-3"} text-center`}>
                        <span className="inline-flex items-center gap-1 font-mono text-xs font-bold px-2 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200">
                          {pick.expectedAlpha}
                        </span>
                      </td>

                      <td className={`${isCompactDensity ? "py-1.5 px-3" : "py-3 px-3"} text-slate-700 text-xs`}>
                        <div className="font-medium text-slate-800">{pick.catalyst}</div>
                        <div className="text-[10px] text-slate-400 font-mono">Consensus: {pick.sentiment}</div>
                      </td>

                      <td className={`${isCompactDensity ? "py-1.5 px-4" : "py-3 px-4"} text-center`}>
                        <div className="flex items-center justify-center gap-1.5">
                          <Link
                            href={`/analyse/${pick.symbol}`}
                            className="px-2.5 py-1 text-[11px] font-semibold text-slate-600 hover:text-slate-900 hover:bg-slate-100 border border-slate-300 rounded transition"
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

            {/* MOBILE VIEW */}
            <div className="block md:hidden p-3 space-y-2.5">
              {filteredAlphaPicks.map((pick) => (
                <div key={pick.symbol} className="bg-white border border-slate-200 rounded-lg p-3 shadow-xs space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="font-mono font-bold text-sm text-slate-900">{pick.symbol}</span>
                      <span className="bg-emerald-50 text-emerald-700 text-[10px] font-mono font-bold px-1.5 py-0.5 rounded border border-emerald-200">
                        {pick.decile} ({pick.expectedAlpha})
                      </span>
                    </div>
                    <span className="font-mono text-xs font-semibold text-blue-600">
                      Mom: {pick.momentumScore}/100
                    </span>
                  </div>
                  <div className="text-xs text-slate-600">{pick.catalyst}</div>
                  <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-[11px] font-mono">
                    <span className="text-slate-500">{pick.peRatio}x P/E • {pick.rocePct}% ROCE</span>
                    <Link href={`/analyse/${pick.symbol}`} className="text-blue-600 font-semibold flex items-center gap-0.5">
                      Deep Dive <ChevronRight size={12} />
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          </>
        )}

        {/* ============================================================ */}
        {/* TAB 3: OPTION CHAIN MATRIX (ATM 24,850)                      */}
        {/* ============================================================ */}
        {activeTableTab === "options" && (
          <>
            <div className="mx-4 mt-3 flex items-center gap-2 text-[11px] font-mono px-3 py-2 rounded border border-amber-200 bg-amber-50 text-amber-800">
              <span className="font-bold uppercase">Sample data</span>
              <span>—</span>
              <span>
                illustrative layout only. For the live chain from your broker see{" "}
                <Link href="/options" className="underline font-semibold">
                  Options Chain &amp; OI
                </Link>
                .
              </span>
            </div>
            {/* DESKTOP VIEW */}
            <div className="hidden md:block overflow-x-auto w-full min-w-0">
              <table className="w-full min-w-[960px] text-center text-xs border-collapse">
                <thead>
                  <tr className="bg-slate-50 border-b border-slate-200 text-[10.5px] font-mono font-semibold uppercase text-slate-500 tracking-wider">
                    <th colSpan={4} className="py-2 px-3 text-center bg-blue-50/40 text-blue-900 border-r border-slate-200">
                      CALL OPTIONS (CE)
                    </th>
                    <th className="py-2 px-4 text-center bg-slate-100 text-slate-900 font-bold border-r border-slate-200">
                      STRIKE
                    </th>
                    <th colSpan={4} className="py-2 px-3 text-center bg-emerald-50/40 text-emerald-900">
                      PUT OPTIONS (PE)
                    </th>
                  </tr>
                  <tr className="bg-slate-50/80 border-b border-slate-200 text-[10px] font-mono text-slate-500">
                    <th className="py-1.5 px-3 text-right">CALL OI</th>
                    <th className="py-1.5 px-2 text-right">CHG</th>
                    <th className="py-1.5 px-2 text-right">IV %</th>
                    <th className="py-1.5 px-3 text-right border-r border-slate-200 font-semibold text-slate-700">CALL LTP (₹)</th>
                    <th className="py-1.5 px-4 text-center bg-slate-100 font-bold text-slate-800 border-r border-slate-200">STRIKE (NIFTY)</th>
                    <th className="py-1.5 px-3 text-left font-semibold text-slate-700">PUT LTP (₹)</th>
                    <th className="py-1.5 px-2 text-left">IV %</th>
                    <th className="py-1.5 px-2 text-left">CHG</th>
                    <th className="py-1.5 px-3 text-left">PUT OI</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 font-mono text-xs">
                  {optionChain.map((row) => (
                    <tr
                      key={row.strike}
                      className={`hover:bg-slate-50/80 transition-colors ${
                        row.isAtm ? "bg-blue-50/60 font-semibold" : row.isMaxPain ? "bg-amber-50/40" : ""
                      }`}
                    >
                      <td className={`${isCompactDensity ? "py-1 px-3" : "py-2.5 px-3"} text-right font-medium text-slate-800`}>
                        {row.callOi}
                      </td>
                      <td className={`${isCompactDensity ? "py-1 px-2" : "py-2.5 px-2"} text-right text-[11px] ${row.callOiChg.startsWith("+") ? "text-emerald-600 font-semibold" : "text-slate-400"}`}>
                        {row.callOiChg}
                      </td>
                      <td className={`${isCompactDensity ? "py-1 px-2" : "py-2.5 px-2"} text-right text-slate-500 text-[11px]`}>
                        {row.callIv}
                      </td>
                      <td className={`${isCompactDensity ? "py-1 px-3" : "py-2.5 px-3"} text-right font-bold text-slate-900 border-r border-slate-200 tabular-nums`}>
                        ₹{row.callLtp.toFixed(2)}
                      </td>

                      {/* STRIKE PRICE CENTER CELL */}
                      <td className={`${isCompactDensity ? "py-1 px-4" : "py-2.5 px-4"} text-center font-bold border-r border-slate-200 ${
                        row.isAtm
                          ? "bg-blue-600 text-white shadow-xs"
                          : row.isMaxPain
                          ? "bg-amber-100 text-amber-900"
                          : row.isCallWall
                          ? "bg-red-50 text-red-700"
                          : row.isPutWall
                          ? "bg-emerald-50 text-emerald-700"
                          : "bg-slate-100 text-slate-900"
                      }`}>
                        <div className="flex items-center justify-center gap-1.5">
                          <span>{row.strike}</span>
                          {row.isAtm && <span className="text-[9px] uppercase px-1 py-0.2 bg-white text-blue-700 rounded font-sans font-bold">ATM</span>}
                          {row.isMaxPain && <span className="text-[9px] uppercase px-1 py-0.2 bg-amber-200 text-amber-900 rounded font-sans font-bold">Pain</span>}
                          {row.isCallWall && <span className="text-[9px] uppercase px-1 py-0.2 bg-red-100 text-red-800 rounded font-sans font-bold">Wall</span>}
                          {row.isPutWall && <span className="text-[9px] uppercase px-1 py-0.2 bg-emerald-100 text-emerald-800 rounded font-sans font-bold">Support</span>}
                        </div>
                      </td>

                      <td className={`${isCompactDensity ? "py-1 px-3" : "py-2.5 px-3"} text-left font-bold text-slate-900 tabular-nums`}>
                        ₹{row.putLtp.toFixed(2)}
                      </td>
                      <td className={`${isCompactDensity ? "py-1 px-2" : "py-2.5 px-2"} text-left text-slate-500 text-[11px]`}>
                        {row.putIv}
                      </td>
                      <td className={`${isCompactDensity ? "py-1 px-2" : "py-2.5 px-2"} text-left text-[11px] ${row.putOiChg.startsWith("+") ? "text-emerald-600 font-semibold" : "text-slate-400"}`}>
                        {row.putOiChg}
                      </td>
                      <td className={`${isCompactDensity ? "py-1 px-3" : "py-2.5 px-3"} text-left font-medium text-slate-800`}>
                        {row.putOi}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* MOBILE VIEW */}
            <div className="block md:hidden p-3 space-y-2 font-mono">
              {optionChain.map((row) => (
                <div
                  key={row.strike}
                  className={`p-2.5 rounded-lg border text-xs space-y-1.5 ${
                    row.isAtm
                      ? "bg-blue-50 border-blue-300"
                      : row.isMaxPain
                      ? "bg-amber-50 border-amber-300"
                      : "bg-white border-slate-200"
                  }`}
                >
                  <div className="flex items-center justify-between font-bold text-slate-900">
                    <span className="flex items-center gap-1.5">
                      Strike {row.strike}
                      {row.isAtm && <span className="px-1.5 py-0.2 bg-blue-600 text-white text-[9px] rounded">ATM</span>}
                    </span>
                    <span className="text-[11px] text-slate-500 font-sans">{row.tag || "NIFTY 26-SEP"}</span>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-[11px]">
                    <div className="bg-white/80 p-1.5 rounded border border-slate-200">
                      <div className="text-[9px] text-slate-400 uppercase">CALL LTP</div>
                      <div className="font-bold text-slate-900">₹{row.callLtp} ({row.callOi})</div>
                    </div>
                    <div className="bg-white/80 p-1.5 rounded border border-slate-200 text-right">
                      <div className="text-[9px] text-slate-400 uppercase">PUT LTP</div>
                      <div className="font-bold text-slate-900">₹{row.putLtp} ({row.putOi})</div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </>
        )}

        {/* ============================================================ */}
        {/* TAB 4: STRATEGY BACKTEST LOGS                                */}
        {/* ============================================================ */}
        {activeTableTab === "backtest" && (
          <>
            <div className="mx-4 mt-3 flex items-center gap-2 text-[11px] font-mono px-3 py-2 rounded border border-amber-200 bg-amber-50 text-amber-800">
              <span className="font-bold uppercase">Sample data</span>
              <span>—</span>
              <span>
                illustrative layout only. Run a real backtest in{" "}
                <Link href="/lab" className="underline font-semibold">
                  Strategy Lab
                </Link>{" "}
                or{" "}
                <Link href="/backtest" className="underline font-semibold">
                  Strategy Backtest (v1)
                </Link>
                .
              </span>
            </div>
            {/* DESKTOP VIEW */}
            <div className="hidden md:block overflow-x-auto w-full min-w-0">
              <table className="w-full min-w-[960px] text-left text-xs border-collapse">
                <thead>
                  <tr className="bg-slate-50 border-b border-slate-200 text-[10.5px] font-mono font-semibold uppercase text-slate-500 tracking-wider">
                    <th className="py-2.5 px-4 font-mono">STRATEGY MODEL</th>
                    <th className="py-2.5 px-3 font-mono">BENCHMARK</th>
                    <th className="py-2.5 px-3 font-mono text-center">IS SHARPE</th>
                    <th className="py-2.5 px-3 font-mono text-center">OOS SHARPE</th>
                    <th className="py-2.5 px-3 font-mono text-center">IS/OOS RATIO</th>
                    <th className="py-2.5 px-3 font-mono text-center">MAX DRAWDOWN</th>
                    <th className="py-2.5 px-3 font-mono text-center">WIN RATE</th>
                    <th className="py-2.5 px-3 font-mono text-right">CAGR %</th>
                    <th className="py-2.5 px-4 font-mono text-center">STATUS</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 font-sans">
                  {backtestLogs.map((log) => (
                    <tr key={log.strategy} className="hover:bg-slate-50/80 transition-colors group">
                      <td className={`${isCompactDensity ? "py-1.5 px-4" : "py-3 px-4"}`}>
                        <div className="font-bold text-slate-900">{log.strategy}</div>
                        <div className="text-[11px] text-slate-400 font-mono">Walk-forward folds: 5 Folds • {log.rebalanceFreq}</div>
                      </td>

                      <td className={`${isCompactDensity ? "py-1.5 px-3" : "py-3 px-3"} font-mono text-slate-600 text-[11px]`}>
                        {log.benchmark}
                      </td>

                      <td className={`${isCompactDensity ? "py-1.5 px-3" : "py-3 px-3"} text-center font-mono font-bold text-slate-800`}>
                        {log.isSharpe}
                      </td>

                      <td className={`${isCompactDensity ? "py-1.5 px-3" : "py-3 px-3"} text-center font-mono font-bold text-blue-600`}>
                        {log.oosSharpe}
                      </td>

                      <td className={`${isCompactDensity ? "py-1.5 px-3" : "py-3 px-3"} text-center`}>
                        <span className="px-2 py-0.5 rounded font-mono text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                          {log.sampleRatio}
                        </span>
                      </td>

                      <td className={`${isCompactDensity ? "py-1.5 px-3" : "py-3 px-3"} text-center font-mono font-bold text-red-600`}>
                        {log.maxDrawdown}
                      </td>

                      <td className={`${isCompactDensity ? "py-1.5 px-3" : "py-3 px-3"} text-center font-mono font-semibold text-slate-800`}>
                        {log.winRate}
                      </td>

                      <td className={`${isCompactDensity ? "py-1.5 px-3" : "py-3 px-3"} text-right font-mono font-bold text-emerald-600 text-sm`}>
                        {log.annualizedReturn}
                      </td>

                      <td className={`${isCompactDensity ? "py-1.5 px-4" : "py-3 px-4"} text-center`}>
                        <span className={`px-2.5 py-1 rounded text-[11px] font-mono font-semibold border ${
                          log.status === "Active Production"
                            ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                            : log.status === "Active Hedge"
                            ? "bg-blue-50 text-blue-700 border-blue-200"
                            : "bg-amber-50 text-amber-700 border-amber-200"
                        }`}>
                          {log.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* MOBILE VIEW */}
            <div className="block md:hidden p-3 space-y-2.5">
              {backtestLogs.map((log) => (
                <div key={log.strategy} className="bg-white border border-slate-200 rounded-lg p-3 shadow-xs space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-xs text-slate-900">{log.strategy}</span>
                    <span className="text-[10px] font-mono font-bold px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200">
                      {log.annualizedReturn}
                    </span>
                  </div>
                  <div className="grid grid-cols-3 gap-2 font-mono text-[10px] text-center">
                    <div className="p-1.5 rounded bg-slate-50 border border-slate-200">
                      <div className="text-slate-400">OOS SHARPE</div>
                      <div className="font-bold text-blue-600 text-xs">{log.oosSharpe}</div>
                    </div>
                    <div className="p-1.5 rounded bg-slate-50 border border-slate-200">
                      <div className="text-slate-400">MAX DD</div>
                      <div className="font-bold text-red-600 text-xs">{log.maxDrawdown}</div>
                    </div>
                    <div className="p-1.5 rounded bg-slate-50 border border-slate-200">
                      <div className="text-slate-400">WIN RATE</div>
                      <div className="font-bold text-slate-800 text-xs">{log.winRate}</div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </>
        )}

        {/* ============================================================ */}
        {/* STICKY TABLE SUMMARY & PAGINATION FOOTER (Master Spec)        */}
        {/* ============================================================ */}
        <div className="px-5 py-3 border-t border-slate-200 bg-slate-50/80 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs font-mono">
          <div className="flex flex-wrap items-center gap-4 text-slate-600">
            {activeTableTab === "holdings" && (
              <>
                <div>
                  <span>Valuation In View: </span>
                  <strong className="text-slate-900 font-bold tabular-nums">{formatCurrency(totalCurrentValue)}</strong>
                </div>
                <div className="h-4 w-[1px] bg-slate-200 hidden sm:block"></div>
                <div>
                  <span>Agg. Unrealized Gain: </span>
                  <strong className={`font-bold tabular-nums ${totalPnL >= 0 ? "text-emerald-600" : "text-red-600"}`}>
                    {totalPnL >= 0 ? "+" : ""}{formatCurrency(totalPnL)} ({formatPct(totalPnLPct)})
                  </strong>
                </div>
              </>
            )}

            {activeTableTab === "alpha" && (
              <div className="text-amber-700">Sample data — not a live evaluation</div>
            )}

            {activeTableTab === "options" && (
              <div className="text-amber-700">Sample data — see the live chain on Options</div>
            )}

            {activeTableTab === "backtest" && (
              <div className="text-amber-700">Sample data — run a real backtest in Strategy Lab</div>
            )}
          </div>

          {/* Result count — all rows for the active tab are rendered above, no pagination */}
          <div className="flex items-center gap-2">
            <span className="text-[11px] text-slate-500 font-mono">
              {activeTableTab === "holdings" && `Showing ${filteredHoldings.length} of ${holdings.length} Positions`}
              {activeTableTab === "alpha" && `Showing ${filteredAlphaPicks.length} Sample Picks`}
              {activeTableTab === "options" && `Showing ${optionChain.length} Sample Strikes`}
              {activeTableTab === "backtest" && `Showing ${backtestLogs.length} Sample Models`}
            </span>
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
                  <p className="text-xs text-slate-500">Illustrative preview only — order execution is not yet supported</p>
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
            {holdings.length === 0 ? (
              <div className="py-8 px-4 text-center space-y-2">
                <div className="text-xs font-semibold text-slate-800">No Positions to Rebalance</div>
                <p className="text-xs text-slate-500">
                  Please import a portfolio statement (.xlsx) or sync your Fyers broker account to generate orders.
                </p>
                <div className="pt-2">
                  <button
                    onClick={() => {
                      setIsRebalanceModalOpen(false);
                      router.push("/portfolio/holdings");
                    }}
                    className="px-4 py-2 bg-blue-600 text-white text-xs font-semibold rounded-md hover:bg-blue-700"
                  >
                    Go to Portfolio
                  </button>
                </div>
              </div>
            ) : (
              <div className="space-y-3 text-xs text-slate-600">
                <p>
                  This basket would combine a zero-tax capital allocation across your holdings with an F&amp;O tail
                  hedge. Both legs are computed live — with real prices and tax impact — on their dedicated pages
                  rather than duplicated here:
                </p>
                <div className="space-y-2">
                  <Link
                    href="/portfolio/rebalance"
                    onClick={() => setIsRebalanceModalOpen(false)}
                    className="block p-3 bg-slate-50 rounded-lg border border-slate-200 hover:border-blue-300 transition"
                  >
                    <div className="font-semibold text-slate-800">Leg 1: Tax-Aware Capital Allocation →</div>
                    <div className="text-[11px] text-slate-500">Open the Tax Rebalance page for a real order sheet</div>
                  </Link>
                  <Link
                    href="/options/tail-risk"
                    onClick={() => setIsRebalanceModalOpen(false)}
                    className="block p-3 bg-slate-50 rounded-lg border border-slate-200 hover:border-blue-300 transition"
                  >
                    <div className="font-semibold text-slate-800">Leg 2: F&amp;O Tail Hedge →</div>
                    <div className="text-[11px] text-slate-500">Open the Tail Risk Sizer for real strikes and pricing</div>
                  </Link>
                </div>
                <p className="text-[11px] text-amber-700 bg-amber-50 border border-amber-200 rounded p-2">
                  Order execution isn&apos;t supported by this app yet — any order still has to be placed with your
                  broker directly.
                </p>
              </div>
            )}

            {/* Modal Actions */}
            <div className="pt-2 flex items-center justify-end gap-3">
              <button
                onClick={() => setIsRebalanceModalOpen(false)}
                className="px-4 py-2 text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 rounded-md shadow-sm"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 6. STATUS FOOTER */}
      <footer className="mt-8 pt-4 border-t border-slate-200 flex flex-col md:flex-row items-center justify-between gap-3 text-[11px] font-mono text-slate-500">
        <div className="flex flex-wrap items-center gap-2.5">
          <span className="flex items-center gap-1.5">
            <span className={`w-2 h-2 rounded-full ${portfolioError ? "bg-red-500" : "bg-emerald-500"}`}></span>
            Portfolio Data: <strong className={portfolioError ? "text-red-700" : "text-emerald-700 font-semibold"}>
              {portfolioError ? "Error" : isPortfolioLoading ? "Loading" : "Loaded"}
            </strong>
          </span>
          <span>•</span>
          <span>Tax Rules: <strong className="text-slate-800 font-medium">Budget 2024-25 STT/LTCG</strong></span>
        </div>
      </footer>

    </div>
  );
}
