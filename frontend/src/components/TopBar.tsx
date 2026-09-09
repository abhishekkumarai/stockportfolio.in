"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, useEffect } from "react";
import { Search, Zap, Scale, Bell, CheckCircle2, TrendingUp, TrendingDown } from "lucide-react";
import { getToken } from "@/lib/portfolioApi";

export default function TopBar() {
  const router = useRouter();
  const [searchQuery, setSearchQuery] = useState("");
  const [isBrokerConnected, setIsBrokerConnected] = useState(false);

  useEffect(() => {
    if (typeof window !== "undefined") {
      setIsBrokerConnected(Boolean(getToken()));
    }
  }, []);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    const clean = searchQuery.trim().toUpperCase();
    if (!clean) return;
    router.push(`/analyse/${clean}`);
    setSearchQuery("");
  };

  return (
    <header className="sticky top-0 z-50 flex h-14 w-full items-center justify-between border-b border-slate-200 bg-white px-5 shadow-[0_1px_2px_0_rgba(15,23,42,0.03)]">
      {/* Left: Real-time Market Ticker Strip */}
      <div className="flex items-center gap-3 overflow-x-auto py-1 scrollbar-none">
        <div className="flex items-center gap-1.5 border-r border-slate-200 pr-3">
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75"></span>
            <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-600"></span>
          </span>
          <span className="font-mono text-[10px] font-bold uppercase tracking-wider text-slate-500">
            NSE LIVE
          </span>
        </div>

        {/* Ticker Badges */}
        <div className="flex items-center gap-2 text-xs">
          {/* NIFTY 50 */}
          <div className="flex items-center gap-1.5 rounded-full border border-emerald-200 bg-emerald-50/70 px-2.5 py-0.5 font-mono text-[11px] font-medium text-emerald-800">
            <span className="font-semibold text-slate-700">NIFTY 50</span>
            <span className="font-bold">24,850.30</span>
            <span className="flex items-center text-[10px] font-semibold text-emerald-600">
              <TrendingUp size={11} className="mr-0.5 inline" /> +0.42%
            </span>
          </div>

          {/* SENSEX */}
          <div className="flex items-center gap-1.5 rounded-full border border-emerald-200 bg-emerald-50/70 px-2.5 py-0.5 font-mono text-[11px] font-medium text-emerald-800">
            <span className="font-semibold text-slate-700">SENSEX</span>
            <span className="font-bold">81,320.15</span>
            <span className="flex items-center text-[10px] font-semibold text-emerald-600">
              <TrendingUp size={11} className="mr-0.5 inline" /> +0.38%
            </span>
          </div>

          {/* INDIA VIX */}
          <div className="flex items-center gap-1.5 rounded-full border border-emerald-200 bg-emerald-50/70 px-2.5 py-0.5 font-mono text-[11px] font-medium text-emerald-800">
            <span className="font-semibold text-slate-700">INDIA VIX</span>
            <span className="font-bold">13.45</span>
            <span className="flex items-center text-[10px] font-semibold text-emerald-600">
              <TrendingDown size={11} className="mr-0.5 inline" /> -2.10%
            </span>
          </div>

          {/* BRENT CRUDE */}
          <div className="flex items-center gap-1.5 rounded-full border border-slate-200 bg-slate-50 px-2.5 py-0.5 font-mono text-[11px] font-medium text-slate-700">
            <span className="font-semibold text-slate-500">BRENT</span>
            <span className="font-bold text-slate-900">$74.20</span>
            <span className="text-[10px] font-semibold text-emerald-600">-1.15%</span>
          </div>

          {/* USD/INR */}
          <div className="hidden items-center gap-1.5 rounded-full border border-slate-200 bg-slate-50 px-2.5 py-0.5 font-mono text-[11px] font-medium text-slate-700 lg:flex">
            <span className="font-semibold text-slate-500">USD/INR</span>
            <span className="font-bold text-slate-900">₹83.92</span>
            <span className="text-[10px] font-semibold text-slate-500">+0.04%</span>
          </div>
        </div>
      </div>

      {/* Right: Search & Actions */}
      <div className="flex items-center gap-3">
        {/* Ticker Search Box */}
        <form onSubmit={handleSearch} className="relative hidden md:block">
          <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            placeholder="Search symbol (e.g. RELIANCE, TCS)..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="h-8 w-56 rounded-md border border-slate-200 bg-slate-50 pl-8 pr-11 text-xs text-slate-900 placeholder-slate-400 transition-all focus:border-blue-600 focus:bg-white focus:outline-none focus:ring-1 focus:ring-blue-600"
          />
          <kbd className="absolute right-2 top-1/2 -translate-y-1/2 rounded border border-slate-200 bg-white px-1.5 py-0.5 font-mono text-[9px] font-semibold text-slate-400 shadow-sm">
            ↵
          </kbd>
        </form>

        {/* Fyers Broker Status */}
        <div className="flex items-center gap-1.5 rounded-md border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs">
          <span
            className={`h-2 w-2 rounded-full ${isBrokerConnected ? "bg-emerald-500" : "bg-amber-500"}`}
          />
          <span className="hidden font-mono text-[11px] font-medium text-slate-600 sm:inline">
            {isBrokerConnected ? "Fyers: Connected" : "Fyers: Guest Mode"}
          </span>
        </div>

        {/* Quick CTA */}
        <Link
          href="/portfolio?tab=rebalance"
          className="flex h-8 items-center gap-1.5 rounded-md bg-blue-600 px-3 text-xs font-semibold text-white shadow-sm transition hover:bg-blue-700"
        >
          <Scale size={13} strokeWidth={2} />
          <span className="hidden sm:inline">Rebalance</span>
        </Link>
      </div>
    </header>
  );
}
