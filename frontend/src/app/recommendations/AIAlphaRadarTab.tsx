"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Activity,
  ArrowUpRight,
  ExternalLink,
  Info,
  RefreshCw,
  Sparkles,
  Zap,
} from "lucide-react";
import {
  getMLRankings,
  type MLRankingsResponse,
  type RankedStockItem,
} from "@/lib/mlApi";

export default function AIAlphaRadarTab() {
  const [data, setData] = useState<MLRankingsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedDecile, setSelectedDecile] = useState<number>(10);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getMLRankings("NIFTY50");
      setData(res);
      if (!res.available) {
        setError(res.reason || "ML alpha rankings temporarily unavailable.");
      }
    } catch (err: any) {
      setError(err?.message || "Failed to load ML alpha model.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const metrics = data?.model_metrics;
  const rankings = data?.rankings || [];
  const decilePicks = rankings.filter((r) => r.decile === selectedDecile);
  const topPicks = rankings.filter((r) => r.decile === 10);

  return (
    <div className="space-y-6 pt-2 font-sans text-slate-900">
      {/* 1. Model Verification & Integrity Banner */}
      <div className="rounded-lg bg-white border border-slate-200 p-4 sm:p-5 flex flex-col md:flex-row md:items-center justify-between gap-4 shadow-[0_1px_2px_0_rgba(15,23,42,0.04)]">
        <div>
          <div className="flex items-center gap-2">
            <span className="p-1 rounded bg-blue-50 text-blue-700 border border-blue-200">
              <Sparkles size={15} />
            </span>
            <span className="font-bold text-slate-900 text-sm">
              L2 Ridge Ranker · Purged Walk-Forward CV
            </span>
            <span className="px-2 py-0.5 rounded text-[11px] font-mono font-bold bg-emerald-50 text-emerald-800 border border-emerald-200">
              Zero-Leakage
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Trained on forward 10-day excess returns vs NIFTY 50 with 5-day post-test embargo against naive baselines.
          </p>
        </div>

        <div className="flex items-center gap-4 font-mono text-xs shrink-0">
          <div className="text-right">
            <span className="text-[11px] text-slate-500 block">Out-of-Sample Rank IC</span>
            <span className="text-sm font-bold text-emerald-700">
              {metrics ? `+${metrics.rank_ic_mean.toFixed(3)}` : "—"}
            </span>
          </div>

          <div className="text-right">
            <span className="text-[11px] text-slate-500 block">Information Ratio (IR)</span>
            <span className="text-sm font-bold text-slate-900">
              {metrics ? metrics.information_ratio.toFixed(2) : "—"}
            </span>
          </div>

          <button
            onClick={() => loadData()}
            disabled={loading}
            className="p-2 rounded-md bg-white text-slate-700 hover:bg-slate-50 border border-slate-200 shadow-sm transition-colors disabled:opacity-50"
            title="Refresh ML Rankings"
          >
            <RefreshCw size={14} className={loading ? "animate-spin text-blue-600" : ""} />
          </button>
        </div>
      </div>

      {error && !data?.available && (
        <div className="p-4 rounded-lg bg-amber-50 border border-amber-200 text-amber-900 text-sm flex items-start gap-3">
          <Info size={16} className="text-amber-600 shrink-0 mt-0.5" />
          <div className="text-xs">
            <span className="font-bold block">Model Notice</span>
            {error}
          </div>
        </div>
      )}

      {/* 2. Decile 10 Highlight Cards: Institutional Strong Buys */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-800 flex items-center gap-2">
            <Zap size={14} className="text-amber-600" />
            Decile 10 Alpha Leaders (Institutional "Strong Buy")
          </h3>
          <span className="text-xs font-mono text-slate-500">
            Top 10% Cross-Sectional Alpha Ranks
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {topPicks.map((stock) => (
            <div
              key={stock.symbol}
              className="rounded-lg bg-white border border-slate-200 p-4 space-y-3 relative overflow-hidden shadow-[0_1px_2px_0_rgba(15,23,42,0.04)]"
            >
              <div className="flex items-start justify-between gap-2">
                <div>
                  <div className="flex items-center gap-2">
                    <Link
                      href={`/analyse/${stock.symbol}`}
                      className="text-base font-bold text-slate-900 hover:text-blue-600 flex items-center gap-1 group"
                    >
                      {stock.name}
                      <ExternalLink size={12} className="opacity-0 group-hover:opacity-100 transition-opacity" />
                    </Link>
                    <span className="px-1.5 py-0.5 rounded text-[10px] font-mono font-bold bg-slate-100 text-slate-700">
                      {stock.symbol}
                    </span>
                  </div>
                  <span className="text-xs text-slate-500">{stock.sector || "Large Cap"}</span>
                </div>

                <span className="px-2.5 py-0.5 rounded-full text-xs font-mono font-bold bg-emerald-50 text-emerald-800 border border-emerald-200">
                  DECILE {stock.decile}
                </span>
              </div>

              {/* Driver Pills */}
              <div className="flex flex-wrap gap-1.5 pt-1">
                {stock.driver_pills.map((pill, idx) => (
                  <span
                    key={idx}
                    className="px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-blue-50 text-blue-700 border border-blue-200"
                  >
                    {pill}
                  </span>
                ))}
              </div>

              {/* Trade Execution Bracket */}
              <div className="rounded-md bg-slate-50 border border-slate-200 p-3 grid grid-cols-3 gap-2 text-center font-mono text-xs">
                <div>
                  <span className="text-[10px] text-slate-500 block uppercase font-semibold">Entry</span>
                  <span className="text-slate-900 font-bold">₹{stock.trade.entry_price}</span>
                </div>
                <div>
                  <span className="text-[10px] text-emerald-700 block uppercase font-semibold">
                    Target (+2.0σ)
                  </span>
                  <span className="text-emerald-700 font-bold">
                    ₹{stock.trade.target_price}
                    <span className="text-[10px] block font-normal">+{stock.trade.target_pct}%</span>
                  </span>
                </div>
                <div>
                  <span className="text-[10px] text-red-700 block uppercase font-semibold">
                    Stop (-1.5σ)
                  </span>
                  <span className="text-red-700 font-bold">
                    ₹{stock.trade.stop_loss}
                    <span className="text-[10px] block font-normal">-{stock.trade.stop_loss_pct}%</span>
                  </span>
                </div>
              </div>

              {/* Tax & R/R Note */}
              <div className="flex items-center justify-between text-[11px] text-slate-500 pt-1 border-t border-slate-100 font-mono">
                <span>R/R: <strong className="text-slate-800">{stock.trade.risk_reward_ratio}:1</strong></span>
                <span className="text-slate-500">STCG 20% | LTCG 12.5%</span>
              </div>
            </div>
          ))}

          {topPicks.length === 0 && !loading && (
            <div className="col-span-2 py-8 text-center text-slate-400 text-xs font-sans">
              No Decile 10 candidates found in current scan.
            </div>
          )}
        </div>
      </div>

      {/* 3. Decile Filter Bar & Full Table */}
      <div className="space-y-3 pt-2">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-200 pb-3">
          <span className="text-xs font-mono uppercase tracking-wider text-slate-500 font-semibold">
            Cross-Sectional Decile Filter
          </span>

          <div className="flex items-center gap-1 overflow-x-auto text-xs font-mono">
            {[10, 9, 8, 7, 6, 5, 4, 3, 2, 1].map((d) => (
              <button
                key={d}
                onClick={() => setSelectedDecile(d)}
                className={`px-2.5 py-1 rounded transition-colors font-bold ${
                  selectedDecile === d
                    ? d >= 9
                      ? "bg-emerald-600 text-white shadow-sm"
                      : d >= 4
                      ? "bg-blue-600 text-white shadow-sm"
                      : "bg-red-600 text-white shadow-sm"
                    : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                }`}
              >
                D{d}
              </button>
            ))}
          </div>
        </div>

        <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white shadow-[0_1px_2px_0_rgba(15,23,42,0.04)]">
          <table className="w-full text-left text-xs font-mono">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50/75 text-slate-500 uppercase tracking-wider text-[10px]">
                <th className="py-2.5 px-3 font-semibold">Decile</th>
                <th className="py-2.5 px-3 font-sans font-semibold">Stock</th>
                <th className="py-2.5 px-3 font-semibold">Price</th>
                <th className="py-2.5 px-3 font-semibold">Target (+2σ)</th>
                <th className="py-2.5 px-3 font-semibold">Stop (-1.5σ)</th>
                <th className="py-2.5 px-3 font-semibold">Alpha Score</th>
                <th className="py-2.5 px-3 text-right font-semibold">Rating</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {decilePicks.map((s) => (
                <tr key={s.symbol} className="hover:bg-slate-50/80 transition-colors">
                  <td className="py-3 px-3 font-bold text-slate-900">D{s.decile}</td>
                  <td className="py-3 px-3">
                    <Link
                      href={`/analyse/${s.symbol}`}
                      className="font-sans font-bold text-slate-900 hover:text-blue-600"
                    >
                      {s.name} <span className="text-slate-500 font-mono text-[11px]">({s.symbol})</span>
                    </Link>
                  </td>
                  <td className="py-3 px-3 text-slate-900 font-semibold">₹{s.trade.entry_price}</td>
                  <td className="py-3 px-3 text-emerald-700 font-bold">₹{s.trade.target_price}</td>
                  <td className="py-3 px-3 text-red-700 font-bold">₹{s.trade.stop_loss}</td>
                  <td className="py-3 px-3 font-bold text-slate-800">{s.alpha_score.toFixed(4)}</td>
                  <td className="py-3 px-3 text-right">
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-bold border ${
                        s.rating === "STRONG_BUY"
                          ? "bg-emerald-50 text-emerald-800 border-emerald-200"
                          : s.rating === "BUY"
                          ? "bg-blue-50 text-blue-800 border-blue-200"
                          : s.rating === "HOLD"
                          ? "bg-slate-100 text-slate-800 border-slate-200"
                          : "bg-red-50 text-red-800 border-red-200"
                      }`}
                    >
                      {s.rating.replace(/_/g, " ")}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
