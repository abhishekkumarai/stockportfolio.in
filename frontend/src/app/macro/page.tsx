"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Activity,
  ArrowDownRight,
  ArrowUpRight,
  Compass,
  DollarSign,
  Droplets,
  Flame,
  Globe,
  Info,
  Layers,
  RefreshCw,
  TrendingDown,
  TrendingUp,
} from "lucide-react";
import {
  getMacroOverview,
  type MacroOverview,
  type SectorRotationItem,
} from "@/lib/macroApi";

export default function MacroPage() {
  const [data, setData] = useState<MacroOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sectorFilter, setSectorFilter] = useState<string>("ALL");

  const loadData = async (refresh: boolean = false) => {
    setLoading(true);
    setError(null);
    try {
      const res = await getMacroOverview();
      setData(res);
      if (!res.available) {
        setError(res.reason || "Macro feed temporarily unavailable.");
      }
    } catch (err: any) {
      setError(err?.message || "Failed to load macro intelligence.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const regime = data?.regime;
  const crude = data?.crude;
  const currency = data?.currency;
  const vix = data?.vix;
  const us10y = data?.us10y;
  const gold = data?.gold;

  const sectors = (data?.sector_rotation || []).filter((s) => {
    if (sectorFilter === "ALL") return true;
    return s.status === sectorFilter;
  });

  return (
    <div className="mx-auto max-w-[1400px] p-6 space-y-6 font-sans text-slate-900 animate-fade-in">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-200 pb-5">
        <div>
          <div className="flex items-center gap-2">
            <span className="p-1.5 rounded-lg bg-blue-50 text-blue-700 border border-blue-200">
              <Compass size={18} strokeWidth={2} />
            </span>
            <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-slate-900">
              India Macro &amp; Inter-Market Radar
            </h1>
          </div>
          <p className="text-xs sm:text-sm text-slate-500 mt-1">
            Global commodity currents, Rupee velocity, and NIFTY sectoral relative rotation
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => loadData(true)}
            disabled={loading}
            className="flex items-center gap-2 px-3.5 py-1.5 text-xs font-semibold rounded-md bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 shadow-sm transition-colors disabled:opacity-50"
          >
            <RefreshCw size={13} className={loading ? "animate-spin text-blue-600" : ""} />
            Sync Feeds
          </button>
          <div className="px-3 py-1 text-xs font-mono rounded-full bg-emerald-50 text-emerald-800 border border-emerald-200 flex items-center gap-1.5 font-semibold">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-600 animate-pulse" />
            100% Free Data
          </div>
        </div>
      </div>

      {error && !data?.available && (
        <div className="p-4 rounded-lg bg-amber-50 border border-amber-200 text-amber-900 text-sm flex items-start gap-3">
          <Info size={18} className="text-amber-600 shrink-0 mt-0.5" />
          <div>
            <div className="font-semibold">Macro Upstream Notice</div>
            <div className="text-xs text-amber-700 mt-0.5">{error}</div>
          </div>
        </div>
      )}

      {/* 1. Macro Health Matrix & Regime Banner */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Main Regime Card */}
        <div className="lg:col-span-2 rounded-lg bg-white border border-slate-200 p-5 sm:p-6 shadow-[0_1px_2px_0_rgba(15,23,42,0.04)] flex flex-col justify-between space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono uppercase tracking-wider text-slate-500 font-semibold">
              Composite Macro Regime
            </span>
            {regime && (
              <span
                className={`px-3 py-0.5 rounded-full text-xs font-mono font-bold border ${
                  regime.posture === "OVERWEIGHT_CYCLICALS"
                    ? "bg-emerald-50 text-emerald-800 border-emerald-200"
                    : regime.posture === "CAPITAL_PRESERVATION"
                    ? "bg-red-50 text-red-800 border-red-200"
                    : regime.posture === "DEFENSIVE_TILT"
                    ? "bg-amber-50 text-amber-800 border-amber-200"
                    : "bg-blue-50 text-blue-800 border-blue-200"
                }`}
              >
                {regime.posture.replace(/_/g, " ")}
              </span>
            )}
          </div>

          <div>
            <h2 className="text-2xl font-bold tracking-tight text-slate-900">
              {regime?.title || "Evaluating Macro Signals..."}
            </h2>
            <p className="text-xs sm:text-sm text-slate-600 mt-2 leading-relaxed">
              {regime?.narrative || "Aggregating global yields, Brent crude, and currency trajectories..."}
            </p>
          </div>

          {regime && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-4 border-t border-slate-100 text-xs">
              <div className="rounded-lg bg-emerald-50/50 border border-emerald-200 p-3">
                <div className="text-emerald-800 font-bold mb-1 flex items-center gap-1.5">
                  <TrendingUp size={14} /> Favored Transmission
                </div>
                <div className="text-slate-700 font-medium">
                  {regime.favored_sectors.join(" · ")}
                </div>
              </div>

              <div className="rounded-lg bg-red-50/50 border border-red-200 p-3">
                <div className="text-red-800 font-bold mb-1 flex items-center gap-1.5">
                  <TrendingDown size={14} /> Vulnerable / Underweight
                </div>
                <div className="text-slate-700 font-medium">
                  {regime.unfavored_sectors.join(" · ")}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Live Gauges Summary Card */}
        <div className="rounded-lg bg-white border border-slate-200 p-5 sm:p-6 shadow-[0_1px_2px_0_rgba(15,23,42,0.04)] flex flex-col justify-between space-y-4">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <span className="text-xs font-mono uppercase tracking-wider text-slate-500 font-semibold">
              Systemic Risk Gauges
            </span>
            <span className="w-2 h-2 rounded-full bg-emerald-600 animate-pulse" />
          </div>

          <div className="space-y-2.5 font-mono text-xs">
            {/* VIX */}
            <div className="flex items-center justify-between p-2.5 rounded-lg bg-slate-50 border border-slate-200">
              <div>
                <span className="text-[11px] text-slate-500 block font-sans">India VIX</span>
                <span className="text-base font-bold text-slate-900">
                  {vix?.current ? vix.current.toFixed(2) : "—"}
                </span>
              </div>
              <span
                className={`text-[10px] font-bold px-2 py-0.5 rounded border ${
                  (vix?.current || 0) < 15
                    ? "bg-emerald-50 text-emerald-800 border-emerald-200"
                    : (vix?.current || 0) < 18
                    ? "bg-amber-50 text-amber-800 border-amber-200"
                    : "bg-red-50 text-red-800 border-red-200"
                }`}
              >
                {(vix?.current || 0) < 15 ? "Low Risk" : (vix?.current || 0) < 18 ? "Moderate" : "High Risk"}
              </span>
            </div>

            {/* US 10Y Yield */}
            <div className="flex items-center justify-between p-2.5 rounded-lg bg-slate-50 border border-slate-200">
              <div>
                <span className="text-[11px] text-slate-500 block font-sans">US 10Y Yield (^TNX)</span>
                <span className="text-base font-bold text-slate-900">
                  {us10y?.yield_pct ? `${us10y.yield_pct.toFixed(2)}%` : "—"}
                </span>
              </div>
              <span className="text-[11px] text-slate-500 font-medium">Capital Cost</span>
            </div>

            {/* Safe-Haven Gold */}
            <div className="flex items-center justify-between p-2.5 rounded-lg bg-slate-50 border border-slate-200">
              <div>
                <span className="text-[11px] text-slate-500 block font-sans">Gold (COMEX $/oz)</span>
                <span className="text-base font-bold text-amber-800">
                  {gold?.current_price ? `$${gold.current_price.toLocaleString()}` : "—"}
                </span>
              </div>
              <span className="text-[11px] text-slate-500 font-medium">
                {gold?.change_5d_pct ? `${gold.change_5d_pct > 0 ? "+" : ""}${gold.change_5d_pct.toFixed(1)}% / 5d` : "Safe Haven"}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* 2. Key Transmission Channels: Crude & USD/INR */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {/* Crude Pressure Index */}
        <div className="rounded-lg bg-white border border-slate-200 p-5 sm:p-6 space-y-3 shadow-[0_1px_2px_0_rgba(15,23,42,0.04)]">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="p-1 rounded-md bg-amber-50 text-amber-700 border border-amber-200">
                <Droplets size={16} />
              </span>
              <span className="font-bold text-sm text-slate-900">Crude Pressure Index</span>
            </div>
            <span
              className={`text-xs font-mono px-2 py-0.5 rounded font-bold border ${
                crude?.pressure_level === "BENIGN"
                  ? "bg-emerald-50 text-emerald-800 border-emerald-200"
                  : crude?.pressure_level === "ELEVATED"
                  ? "bg-red-50 text-red-800 border-red-200"
                  : "bg-amber-50 text-amber-800 border-amber-200"
              }`}
            >
              {crude?.pressure_level || "MODERATE"}
            </span>
          </div>

          <div className="flex items-baseline gap-3 pt-1">
            <span className="text-3xl font-mono font-bold text-slate-900">
              {crude?.current_price ? `$${crude.current_price.toFixed(2)}` : "—"}
            </span>
            <span className="text-xs font-mono text-slate-500">Brent Continuous (BZ=F)</span>
          </div>

          <div className="grid grid-cols-2 gap-2 text-xs font-mono pt-1">
            <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200">
              <span className="text-slate-500 block text-[10px] uppercase font-bold">5-Day Momentum</span>
              <span className={(crude?.change_5d_pct || 0) >= 0 ? "text-red-700 font-bold" : "text-emerald-700 font-bold"}>
                {(crude?.change_5d_pct || 0) > 0 ? "+" : ""}
                {crude?.change_5d_pct?.toFixed(1)}%
              </span>
            </div>
            <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200">
              <span className="text-slate-500 block text-[10px] uppercase font-bold">20-Day Velocity</span>
              <span className={(crude?.change_20d_pct || 0) >= 0 ? "text-red-700 font-bold" : "text-emerald-700 font-bold"}>
                {(crude?.change_20d_pct || 0) > 0 ? "+" : ""}
                {crude?.change_20d_pct?.toFixed(1)}%
              </span>
            </div>
          </div>

          <p className="text-xs text-slate-600 pt-1 leading-relaxed">
            {crude?.impact_assessment || "Analyzing crude oil transmission to Indian current account and corporate input costs..."}
          </p>
        </div>

        {/* Currency Velocity / USD-INR */}
        <div className="rounded-lg bg-white border border-slate-200 p-5 sm:p-6 space-y-3 shadow-[0_1px_2px_0_rgba(15,23,42,0.04)]">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="p-1 rounded-md bg-blue-50 text-blue-700 border border-blue-200">
                <DollarSign size={16} />
              </span>
              <span className="font-bold text-sm text-slate-900">USD / INR Velocity</span>
            </div>
            <span
              className={`text-xs font-mono px-2 py-0.5 rounded font-bold border ${
                currency?.stance === "TAILWIND_FOR_EXPORTS"
                  ? "bg-emerald-50 text-emerald-800 border-emerald-200"
                  : currency?.stance === "HEADWIND_FOR_EXPORTS"
                  ? "bg-red-50 text-red-800 border-red-200"
                  : "bg-slate-100 text-slate-800 border-slate-200"
              }`}
            >
              {currency?.stance?.replace(/_/g, " ") || "STABLE"}
            </span>
          </div>

          <div className="flex items-baseline gap-3 pt-1">
            <span className="text-3xl font-mono font-bold text-slate-900">
              {currency?.current_rate ? `₹${currency.current_rate.toFixed(2)}` : "—"}
            </span>
            <span className="text-xs font-mono text-slate-500">INR=X Spot</span>
          </div>

          <div className="grid grid-cols-2 gap-2 text-xs font-mono pt-1">
            <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200">
              <span className="text-slate-500 block text-[10px] uppercase font-bold">5-Day Change</span>
              <span className="text-slate-800 font-bold">
                {(currency?.change_5d_pct || 0) > 0 ? "+" : ""}
                {currency?.change_5d_pct?.toFixed(2)}%
              </span>
            </div>
            <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200">
              <span className="text-slate-500 block text-[10px] uppercase font-bold">20-Day Trajectory</span>
              <span className="text-slate-800 font-bold">
                {(currency?.change_20d_pct || 0) > 0 ? "+" : ""}
                {currency?.change_20d_pct?.toFixed(2)}%
              </span>
            </div>
          </div>

          <p className="text-xs text-slate-600 pt-1 leading-relaxed">
            {currency?.impact_assessment || "Evaluating foreign exchange translation effects across IT, Pharma, and domestic importers..."}
          </p>
        </div>
      </div>

      {/* 3. NIFTY Sector Relative Rotation Matrix */}
      <div className="rounded-lg bg-white border border-slate-200 p-5 sm:p-6 space-y-4 shadow-[0_1px_2px_0_rgba(15,23,42,0.04)]">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-200 pb-4">
          <div>
            <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
              <Layers size={18} className="text-blue-600" />
              NIFTY Sector Relative Momentum Matrix
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Benchmark-relative excess return: 1-Month (21d) and 3-Month (63d) vs NIFTY 50
            </p>
          </div>

          {/* Filter Pills */}
          <div className="flex items-center gap-1.5 overflow-x-auto text-xs font-mono">
            {["ALL", "LEADERSHIP", "IMPROVING", "WEAKENING", "LAGGING"].map((f) => (
              <button
                key={f}
                onClick={() => setSectorFilter(f)}
                className={`px-3 py-1 rounded-md transition-colors font-bold ${
                  sectorFilter === f
                    ? "bg-blue-600 text-white shadow-sm"
                    : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                }`}
              >
                {f}
              </button>
            ))}
          </div>
        </div>

        {/* Sectors Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50/75 text-slate-500 uppercase tracking-wider text-[10px]">
                <th className="py-2.5 px-3 font-semibold">Rank</th>
                <th className="py-2.5 px-3 font-sans font-semibold">Sector</th>
                <th className="py-2.5 px-3 font-semibold">Price</th>
                <th className="py-2.5 px-3 font-semibold">1M Rel vs NIFTY</th>
                <th className="py-2.5 px-3 font-semibold">3M Rel vs NIFTY</th>
                <th className="py-2.5 px-3 font-semibold">Score</th>
                <th className="py-2.5 px-3 text-right font-semibold">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {sectors.map((s) => (
                <tr key={s.sector_key} className="hover:bg-slate-50/80 transition-colors">
                  <td className="py-3 px-3 text-slate-500">#{s.rank}</td>
                  <td className="py-3 px-3 font-sans font-bold text-slate-900">
                    {s.name}
                  </td>
                  <td className="py-3 px-3 text-slate-800 font-semibold">
                    ₹{s.current_price.toLocaleString()}
                  </td>
                  <td className="py-3 px-3">
                    <span className={s.relative_1m_pct >= 0 ? "text-emerald-700 font-bold" : "text-red-700 font-bold"}>
                      {s.relative_1m_pct >= 0 ? "+" : ""}
                      {s.relative_1m_pct.toFixed(2)}%
                    </span>
                  </td>
                  <td className="py-3 px-3">
                    <span className={s.relative_3m_pct >= 0 ? "text-emerald-700 font-bold" : "text-red-700 font-bold"}>
                      {s.relative_3m_pct >= 0 ? "+" : ""}
                      {s.relative_3m_pct.toFixed(2)}%
                    </span>
                  </td>
                  <td className="py-3 px-3 font-bold text-slate-900">
                    {s.momentum_score > 0 ? "+" : ""}
                    {s.momentum_score.toFixed(2)}
                  </td>
                  <td className="py-3 px-3 text-right">
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-bold border ${
                        s.status === "LEADERSHIP"
                          ? "bg-emerald-50 text-emerald-800 border-emerald-200"
                          : s.status === "IMPROVING"
                          ? "bg-blue-50 text-blue-800 border-blue-200"
                          : s.status === "WEAKENING"
                          ? "bg-amber-50 text-amber-800 border-amber-200"
                          : "bg-red-50 text-red-800 border-red-200"
                      }`}
                    >
                      {s.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {sectors.length === 0 && (
            <div className="py-8 text-center text-slate-400 text-xs font-sans">
              No sectors match filter '{sectorFilter}'.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
