"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Activity,
  ArrowUpRight,
  ExternalLink,
  Flame,
  Info,
  Radio,
  RefreshCw,
  TrendingUp,
} from "lucide-react";
import {
  getMarketPulse,
  type BreakoutCandidate,
  type MarketBreadth,
  type MarketPulseResponse,
  type VolumeShocker,
} from "@/lib/pulseApi";

export default function MarketPulsePage() {
  const [data, setData] = useState<MarketPulseResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [universe, setUniverse] = useState<string>("NIFTY50");
  const [activeTab, setActiveTab] = useState<"SHOCKERS" | "BREAKOUTS">("SHOCKERS");

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getMarketPulse(universe);
      setData(res);
      if (!res.available) {
        setError(res.reason || "Market pulse data temporarily unavailable.");
      }
    } catch (err: any) {
      setError(err?.message || "Failed to load live market pulse.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [universe]);

  const breadth: MarketBreadth | undefined = data?.breadth;
  const shockers: VolumeShocker[] = data?.volume_shockers || [];
  const breakouts: BreakoutCandidate[] = data?.breakouts || [];

  return (
    <div className="mx-auto max-w-[1400px] p-6 space-y-6 font-sans text-slate-900 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-200 pb-5">
        <div>
          <div className="flex items-center gap-2">
            <span className="p-1.5 rounded-lg bg-emerald-50 text-emerald-700 border border-emerald-200">
              <Radio size={18} strokeWidth={2} />
            </span>
            <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-slate-900">
              Live NSE Market Pulse &amp; Breakouts
            </h1>
          </div>
          <p className="text-xs sm:text-sm text-slate-500 mt-1">
            Real-time market breadth, institutional volume shockers, and 52-week high breakout radar
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* Universe selector */}
          <div className="flex items-center rounded-md bg-slate-100 border border-slate-200 p-0.5 text-xs font-mono">
            {["NIFTY50", "NIFTY500"].map((u) => (
              <button
                key={u}
                onClick={() => setUniverse(u)}
                className={`px-3 py-1 rounded transition-colors ${
                  universe === u ? "bg-white text-blue-700 font-bold shadow-sm" : "text-slate-600 hover:text-slate-900"
                }`}
              >
                {u}
              </button>
            ))}
          </div>

          <button
            onClick={() => loadData()}
            disabled={loading}
            className="flex items-center gap-2 px-3.5 py-1.5 text-xs font-semibold rounded-md bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 shadow-sm transition-colors disabled:opacity-50"
          >
            <RefreshCw size={13} className={loading ? "animate-spin text-blue-600" : ""} />
            Scan
          </button>
        </div>
      </div>

      {error && !data?.available && (
        <div className="p-4 rounded-lg bg-amber-50 border border-amber-200 text-amber-900 text-sm flex items-start gap-3">
          <Info size={18} className="text-amber-600 shrink-0 mt-0.5" />
          <div>
            <div className="font-semibold">Scanner Notice</div>
            <div className="text-xs text-amber-700 mt-0.5">{error}</div>
          </div>
        </div>
      )}

      {/* 1. Advance / Decline Breadth Gauge */}
      {breadth && (
        <div className="rounded-lg bg-white border border-slate-200 p-5 sm:p-6 space-y-4 shadow-[0_1px_2px_0_rgba(15,23,42,0.04)]">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <span className="text-xs font-mono uppercase tracking-wider text-slate-500 font-semibold">
                NSE Market Breadth ({universe})
              </span>
              <div className="text-lg font-bold text-slate-900 mt-1 flex items-center gap-2 font-mono">
                <span className="text-emerald-700">{breadth.advances} Advances</span>
                <span className="text-slate-300">/</span>
                <span className="text-red-700">{breadth.declines} Declines</span>
                {breadth.unchanged > 0 && (
                  <>
                    <span className="text-slate-300">/</span>
                    <span className="text-slate-500">{breadth.unchanged} Unchanged</span>
                  </>
                )}
              </div>
            </div>

            <div className="flex items-center gap-2 font-mono text-xs">
              <span className="px-3 py-1 rounded-md bg-slate-50 border border-slate-200 text-slate-700">
                Ratio: <strong className="text-slate-900">{breadth.breadth_ratio.toFixed(2)}x</strong>
              </span>
              <span
                className={`px-3 py-1 rounded-md font-bold border ${
                  breadth.sentiment === "BULLISH_EXPANSION"
                    ? "bg-emerald-50 text-emerald-800 border-emerald-200"
                    : breadth.sentiment === "BEARISH_DIVERGENCE"
                    ? "bg-red-50 text-red-800 border-red-200"
                    : "bg-slate-100 text-slate-700 border-slate-200"
                }`}
              >
                {breadth.sentiment.replace(/_/g, " ")}
              </span>
            </div>
          </div>

          {/* Breadth Bar Visual */}
          <div className="space-y-1.5 font-mono text-xs">
            <div className="w-full h-3 rounded-full bg-red-100 overflow-hidden flex">
              <div
                className="h-full bg-emerald-600 transition-all duration-500"
                style={{ width: `${breadth.advance_pct}%` }}
              />
            </div>
            <div className="flex justify-between text-[11px] font-semibold">
              <span className="text-emerald-700">{breadth.advance_pct.toFixed(1)}% Advancing</span>
              <span className="text-red-700">{(100 - breadth.advance_pct).toFixed(1)}% Declining</span>
            </div>
          </div>

          <p className="text-xs text-slate-600 border-t border-slate-100 pt-3">
            {breadth.description}
          </p>
        </div>
      )}

      {/* 2. Scanner Tabs: Volume Shockers vs 52W Breakouts */}
      <div className="rounded-lg bg-white border border-slate-200 p-5 sm:p-6 space-y-5 shadow-[0_1px_2px_0_rgba(15,23,42,0.04)]">
        <div className="flex items-center justify-between border-b border-slate-200 pb-3">
          <div className="flex items-center gap-4">
            <button
              onClick={() => setActiveTab("SHOCKERS")}
              className={`flex items-center gap-2 pb-2 text-xs font-bold uppercase tracking-wider border-b-2 transition-all ${
                activeTab === "SHOCKERS"
                  ? "border-emerald-600 text-emerald-700"
                  : "border-transparent text-slate-500 hover:text-slate-900"
              }`}
            >
              <Flame size={15} className={activeTab === "SHOCKERS" ? "text-emerald-600" : ""} />
              Volume Shockers ({shockers.length})
            </button>

            <button
              onClick={() => setActiveTab("BREAKOUTS")}
              className={`flex items-center gap-2 pb-2 text-xs font-bold uppercase tracking-wider border-b-2 transition-all ${
                activeTab === "BREAKOUTS"
                  ? "border-blue-600 text-blue-700"
                  : "border-transparent text-slate-500 hover:text-slate-900"
              }`}
            >
              <TrendingUp size={15} className={activeTab === "BREAKOUTS" ? "text-blue-600" : ""} />
              52-Week Breakout Radar ({breakouts.length})
            </button>
          </div>

          <span className="text-xs font-mono text-slate-500 hidden sm:inline">
            Scanned {data?.scanned_symbols || 0} equities
          </span>
        </div>

        {/* Tab 1: Volume Shockers */}
        {activeTab === "SHOCKERS" && (
          <div className="space-y-3">
            <div className="text-xs text-slate-500">
              Institutional accumulation footprint: Volume surge $\ge 2.0\times$ 20-day average volume on positive daily returns.
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs font-mono">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50/75 text-slate-500 uppercase tracking-wider text-[10px]">
                    <th className="py-2.5 px-3 font-sans font-semibold">Stock</th>
                    <th className="py-2.5 px-3 font-semibold">Price</th>
                    <th className="py-2.5 px-3 font-semibold">1D Return</th>
                    <th className="py-2.5 px-3 font-semibold">Surge Ratio</th>
                    <th className="py-2.5 px-3 font-semibold">Today Volume</th>
                    <th className="py-2.5 px-3 font-semibold">20D Avg Vol</th>
                    <th className="py-2.5 px-3 text-right font-semibold">Tag</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {shockers.map((s) => (
                    <tr key={s.symbol} className="hover:bg-slate-50/80 transition-colors">
                      <td className="py-3 px-3">
                        <Link
                          href={`/analyse/${s.symbol}`}
                          className="font-sans font-medium text-slate-900 hover:text-blue-600 flex items-center gap-1.5 group"
                        >
                          {s.name}
                          <span className="text-slate-500 font-mono text-[11px] group-hover:text-blue-600">
                            ({s.symbol})
                          </span>
                          <ExternalLink size={11} className="opacity-0 group-hover:opacity-100 transition-opacity" />
                        </Link>
                      </td>
                      <td className="py-3 px-3 text-slate-900 font-semibold">
                        ₹{s.current_price.toLocaleString()}
                      </td>
                      <td className="py-3 px-3 text-emerald-700 font-bold">
                        +{s.change_pct.toFixed(2)}%
                      </td>
                      <td className="py-3 px-3">
                        <span className="text-amber-700 font-bold bg-amber-50 px-2 py-0.5 rounded border border-amber-200">
                          {s.volume_surge_ratio.toFixed(2)}x
                        </span>
                      </td>
                      <td className="py-3 px-3 text-slate-600">
                        {s.volume.toLocaleString()}
                      </td>
                      <td className="py-3 px-3 text-slate-500">
                        {s.sma20_volume.toLocaleString()}
                      </td>
                      <td className="py-3 px-3 text-right">
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-bold border ${
                            s.tag === "INSTITUTIONAL_ACCUMULATION"
                              ? "bg-amber-50 text-amber-800 border-amber-200"
                              : "bg-emerald-50 text-emerald-800 border-emerald-200"
                          }`}
                        >
                          {s.tag.replace(/_/g, " ")}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              {shockers.length === 0 && (
                <div className="py-12 text-center text-slate-400 text-xs font-sans">
                  No stocks in {universe} meet the $2.0\times$ volume surge threshold today.
                </div>
              )}
            </div>
          </div>
        )}

        {/* Tab 2: 52-Week Breakouts */}
        {activeTab === "BREAKOUTS" && (
          <div className="space-y-3">
            <div className="text-xs text-slate-500">
              Stocks within 2% of or breaking out above their 52-week high, tagged with Volatility Contraction Pattern (VCP) consolidation status.
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs font-mono">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50/75 text-slate-500 uppercase tracking-wider text-[10px]">
                    <th className="py-2.5 px-3 font-sans font-semibold">Stock</th>
                    <th className="py-2.5 px-3 font-semibold">Price</th>
                    <th className="py-2.5 px-3 font-semibold">52W High</th>
                    <th className="py-2.5 px-3 font-semibold">Distance</th>
                    <th className="py-2.5 px-3 font-semibold">1D Change</th>
                    <th className="py-2.5 px-3 font-semibold">VCP Setup</th>
                    <th className="py-2.5 px-3 text-right font-semibold">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {breakouts.map((b) => (
                    <tr key={b.symbol} className="hover:bg-slate-50/80 transition-colors">
                      <td className="py-3 px-3">
                        <Link
                          href={`/analyse/${b.symbol}`}
                          className="font-sans font-medium text-slate-900 hover:text-blue-600 flex items-center gap-1.5 group"
                        >
                          {b.name}
                          <span className="text-slate-500 font-mono text-[11px] group-hover:text-blue-600">
                            ({b.symbol})
                          </span>
                          <ExternalLink size={11} className="opacity-0 group-hover:opacity-100 transition-opacity" />
                        </Link>
                      </td>
                      <td className="py-3 px-3 text-slate-900 font-semibold">
                        ₹{b.current_price.toLocaleString()}
                      </td>
                      <td className="py-3 px-3 text-slate-600">
                        ₹{b.high_52w.toLocaleString()}
                      </td>
                      <td className="py-3 px-3">
                        <span className={b.distance_pct >= 0 ? "text-emerald-700 font-bold" : "text-slate-700 font-semibold"}>
                          {b.distance_pct >= 0 ? "+" : ""}
                          {b.distance_pct.toFixed(2)}%
                        </span>
                      </td>
                      <td className="py-3 px-3">
                        <span className={b.change_pct >= 0 ? "text-emerald-700 font-bold" : "text-red-700 font-bold"}>
                          {b.change_pct >= 0 ? "+" : ""}
                          {b.change_pct.toFixed(2)}%
                        </span>
                      </td>
                      <td className="py-3 px-3">
                        {b.vcp_contracted ? (
                          <span className="px-2 py-0.5 rounded text-[10px] bg-blue-50 text-blue-700 border border-blue-200 font-bold">
                            TIGHT BASE
                          </span>
                        ) : (
                          <span className="text-slate-400 text-[11px]">—</span>
                        )}
                      </td>
                      <td className="py-3 px-3 text-right">
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-bold border ${
                            b.status.includes("NEW") || b.status.includes("BREAKOUT")
                              ? "bg-emerald-50 text-emerald-800 border-emerald-200"
                              : "bg-blue-50 text-blue-800 border-blue-200"
                          }`}
                        >
                          {b.status.replace(/_/g, " ")}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              {breakouts.length === 0 && (
                <div className="py-12 text-center text-slate-400 text-xs font-sans">
                  No stocks in {universe} currently trading within 2% of their 52-week high.
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
