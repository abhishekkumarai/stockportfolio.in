"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import {
  LayoutDashboard,
  TrendingUp,
  Scale,
  Newspaper,
  Filter,
  BarChart2,
  Award,
  Radio,
  Layers,
  Shield,
  GitFork,
  FlaskConical,
  FileText,
  X,
} from "lucide-react";
import { getFyersStatus, getToken, type FyersStatus } from "@/lib/portfolioApi";

interface SidebarProps {
  onNavigate?: () => void;
  onClose?: () => void;
}

export default function Sidebar({ onNavigate, onClose }: SidebarProps = {}) {
  const pathname = usePathname();
  const [fyersStatus, setFyersStatus] = useState<FyersStatus | null>(null);
  const [search, setSearch] = useState("");

  useEffect(() => {
    const sync = () => setSearch(window.location.search);
    sync();
    window.addEventListener("popstate", sync);
    return () => window.removeEventListener("popstate", sync);
  }, [pathname]);

  useEffect(() => {
    if (!getToken()) return;
    const controller = new AbortController();
    getFyersStatus(controller.signal)
      .then(setFyersStatus)
      .catch(() => setFyersStatus(null));
    return () => controller.abort();
  }, []);

  const isActive = (href: string) => {
    const [path, query = ""] = href.split("?");
    if (path !== pathname) return false;
    if (!query) {
      return search === "" || search === "?tab=all";
    }
    const hrefTab = new URLSearchParams(query).get("tab");
    const currentTab = new URLSearchParams(search).get("tab");
    return hrefTab === currentTab;
  };

  const handleNav = (href: string) => {
    const [, query = ""] = href.split("?");
    setSearch(query ? `?${query}` : "");
    if (onNavigate) {
      onNavigate();
    }
  };

  return (
    <aside className="w-56 shrink-0 border-r border-slate-200 bg-white flex flex-col justify-between select-none min-h-full h-full z-40">
      <div className="py-3">
        {/* Sidebar Workspace Header */}
        <div className="px-4 pb-3 mb-2 border-b border-slate-200 flex items-center justify-between">
          <div>
            <div className="text-[11px] font-bold text-slate-900 uppercase tracking-wider font-mono">
              Alpha Terminal v4.2
            </div>
            <div className="text-[11px] text-slate-400">Unified Institutional Desk</div>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
            {onClose && (
              <button
                type="button"
                onClick={onClose}
                className="p-1 rounded text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
                aria-label="Close sidebar navigation"
              >
                <X size={16} />
              </button>
            )}
          </div>
        </div>

        {/* Navigation Modules */}
        <div className="space-y-4 px-2">
          {/* Module 1: PORTFOLIO INTELLIGENCE */}
          <div>
            <div className="px-3 py-1 text-[10px] font-bold font-mono text-slate-400 uppercase tracking-wider">
              Portfolio Intelligence
            </div>
            <nav className="mt-1 space-y-0.5 text-xs">
              <Link
                href="/"
                onClick={() => handleNav("/")}
                className={`flex items-center justify-between px-3 py-2 rounded-r-md transition-colors ${
                  isActive("/")
                    ? "bg-blue-50 text-blue-600 font-semibold border-l-[3px] border-blue-600"
                    : "text-slate-600 hover:text-slate-900 hover:bg-slate-50"
                }`}
              >
                <div className="flex items-center gap-2.5">
                  <LayoutDashboard size={16} />
                  <span>Master Console</span>
                </div>
                <span className="text-[9px] font-mono uppercase px-1.5 py-0.5 rounded bg-blue-600 text-white font-bold">
                  Live
                </span>
              </Link>

              <Link
                href="/portfolio"
                onClick={() => handleNav("/portfolio")}
                className={`flex items-center justify-between px-3 py-2 rounded-md transition-colors ${
                  isActive("/portfolio")
                    ? "bg-blue-50 text-blue-600 font-semibold border-l-[3px] border-blue-600"
                    : "text-slate-600 hover:text-slate-900 hover:bg-slate-50"
                }`}
              >
                <div className="flex items-center gap-2.5">
                  <TrendingUp size={16} />
                  <span>Wealth Cone & VaR</span>
                </div>
              </Link>

              <Link
                href="/portfolio?tab=rebalance"
                onClick={() => handleNav("/portfolio?tab=rebalance")}
                className={`flex items-center justify-between px-3 py-2 rounded-md transition-colors ${
                  isActive("/portfolio?tab=rebalance")
                    ? "bg-blue-50 text-blue-600 font-semibold border-l-[3px] border-blue-600"
                    : "text-slate-600 hover:text-slate-900 hover:bg-slate-50"
                }`}
              >
                <div className="flex items-center gap-2.5">
                  <Scale size={16} />
                  <span>Tax Rebalance</span>
                </div>
                <span className="text-[9px] font-mono px-1 rounded bg-emerald-50 text-emerald-700 border border-emerald-200">
                  0% Tax
                </span>
              </Link>

              <Link
                href="/portfolio?tab=catalysts"
                onClick={() => handleNav("/portfolio?tab=catalysts")}
                className={`flex items-center justify-between px-3 py-2 rounded-md transition-colors ${
                  isActive("/portfolio?tab=catalysts")
                    ? "bg-blue-50 text-blue-600 font-semibold border-l-[3px] border-blue-600"
                    : "text-slate-600 hover:text-slate-900 hover:bg-slate-50"
                }`}
              >
                <div className="flex items-center gap-2.5">
                  <Newspaper size={16} />
                  <span>Catalysts & News</span>
                </div>
              </Link>
            </nav>
          </div>

          {/* Module 2: RESEARCH & DISCOVERY */}
          <div>
            <div className="px-3 py-1 text-[10px] font-bold font-mono text-slate-400 uppercase tracking-wider">
              Research & Discovery
            </div>
            <nav className="mt-1 space-y-0.5 text-xs">
              <Link
                href="/screener"
                onClick={() => handleNav("/screener")}
                className={`flex items-center justify-between px-3 py-2 rounded-md transition-colors ${
                  isActive("/screener")
                    ? "bg-blue-50 text-blue-600 font-semibold border-l-[3px] border-blue-600"
                    : "text-slate-600 hover:text-slate-900 hover:bg-slate-50"
                }`}
              >
                <div className="flex items-center gap-2.5">
                  <Filter size={16} />
                  <span>NSE Screener</span>
                </div>
                <span className="text-[9px] font-mono px-1 rounded bg-slate-100 text-slate-500 border border-slate-200">
                  500 EQ
                </span>
              </Link>

              <Link
                href="/analyse"
                onClick={() => handleNav("/analyse")}
                className={`flex items-center justify-between px-3 py-2 rounded-md transition-colors ${
                  pathname.startsWith("/analyse")
                    ? "bg-blue-50 text-blue-600 font-semibold border-l-[3px] border-blue-600"
                    : "text-slate-600 hover:text-slate-900 hover:bg-slate-50"
                }`}
              >
                <div className="flex items-center gap-2.5">
                  <BarChart2 size={16} />
                  <span>Equity Deep Dive</span>
                </div>
                <span className="text-[9px] font-mono text-slate-400">Piotroski</span>
              </Link>

              <Link
                href="/recommendations"
                onClick={() => handleNav("/recommendations")}
                className={`flex items-center justify-between px-3 py-2 rounded-md transition-colors ${
                  isActive("/recommendations")
                    ? "bg-blue-50 text-blue-600 font-semibold border-l-[3px] border-blue-600"
                    : "text-slate-600 hover:text-slate-900 hover:bg-slate-50"
                }`}
              >
                <div className="flex items-center gap-2.5">
                  <Award size={16} />
                  <span>Ranked Alpha Board</span>
                </div>
                <span className="text-[9px] font-mono px-1 rounded bg-blue-50 text-blue-700 border border-blue-200">
                  Ranked
                </span>
              </Link>

              <Link
                href="/pulse"
                onClick={() => handleNav("/pulse")}
                className={`flex items-center justify-between px-3 py-2 rounded-md transition-colors ${
                  isActive("/pulse")
                    ? "bg-blue-50 text-blue-600 font-semibold border-l-[3px] border-blue-600"
                    : "text-slate-600 hover:text-slate-900 hover:bg-slate-50"
                }`}
              >
                <div className="flex items-center gap-2.5">
                  <Radio size={16} />
                  <span>Market Pulse</span>
                </div>
              </Link>
            </nav>
          </div>

          {/* Module 3: QUANT & DERIVATIVES */}
          <div>
            <div className="px-3 py-1 text-[10px] font-bold font-mono text-slate-400 uppercase tracking-wider">
              Quant & Derivatives
            </div>
            <nav className="mt-1 space-y-0.5 text-xs">
              <Link
                href="/options"
                onClick={() => handleNav("/options")}
                className={`flex items-center justify-between px-3 py-2 rounded-md transition-colors ${
                  isActive("/options")
                    ? "bg-blue-50 text-blue-600 font-semibold border-l-[3px] border-blue-600"
                    : "text-slate-600 hover:text-slate-900 hover:bg-slate-50"
                }`}
              >
                <div className="flex items-center gap-2.5">
                  <Layers size={16} />
                  <span>Options Chain & OI</span>
                </div>
                <span className="text-[9px] font-mono px-1 rounded bg-emerald-50 text-emerald-700 border border-emerald-200">
                  Fyers
                </span>
              </Link>

              <Link
                href="/options?tab=sizer"
                onClick={() => handleNav("/options?tab=sizer")}
                className={`flex items-center justify-between px-3 py-2 rounded-md transition-colors ${
                  isActive("/options?tab=sizer")
                    ? "bg-blue-50 text-blue-600 font-semibold border-l-[3px] border-blue-600"
                    : "text-slate-600 hover:text-slate-900 hover:bg-slate-50"
                }`}
              >
                <div className="flex items-center gap-2.5">
                  <Shield size={16} />
                  <span>Tail Risk Sizer</span>
                </div>
              </Link>

              <Link
                href="/quant"
                onClick={() => handleNav("/quant")}
                className={`flex items-center justify-between px-3 py-2 rounded-md transition-colors ${
                  isActive("/quant")
                    ? "bg-blue-50 text-blue-600 font-semibold border-l-[3px] border-blue-600"
                    : "text-slate-600 hover:text-slate-900 hover:bg-slate-50"
                }`}
              >
                <div className="flex items-center gap-2.5">
                  <GitFork size={16} />
                  <span>Risk Parity (HRP)</span>
                </div>
              </Link>
            </nav>
          </div>

          {/* Module 4: LAB & AGENT TOOLS */}
          <div>
            <div className="px-3 py-1 text-[10px] font-bold font-mono text-slate-400 uppercase tracking-wider">
              Lab & Agent Tools
            </div>
            <nav className="mt-1 space-y-0.5 text-xs">
              <Link
                href="/lab"
                onClick={() => handleNav("/lab")}
                className={`flex items-center justify-between px-3 py-2 rounded-md transition-colors ${
                  isActive("/lab")
                    ? "bg-blue-50 text-blue-600 font-semibold border-l-[3px] border-blue-600"
                    : "text-slate-600 hover:text-slate-900 hover:bg-slate-50"
                }`}
              >
                <div className="flex items-center gap-2.5">
                  <FlaskConical size={16} />
                  <span>Strategy Lab (v2)</span>
                </div>
                <span className="text-[9px] font-mono px-1 rounded bg-blue-50 text-blue-700 border border-blue-200">
                  Walk-fwd
                </span>
              </Link>

              <Link
                href="/paper"
                onClick={() => handleNav("/paper")}
                className={`flex items-center justify-between px-3 py-2 rounded-md transition-colors ${
                  isActive("/paper")
                    ? "bg-blue-50 text-blue-600 font-semibold border-l-[3px] border-blue-600"
                    : "text-slate-600 hover:text-slate-900 hover:bg-slate-50"
                }`}
              >
                <div className="flex items-center gap-2.5">
                  <FileText size={16} />
                  <span>Paper Trading</span>
                </div>
                <span className="text-[9px] font-mono px-1 rounded bg-slate-100 text-slate-500 border border-slate-200">
                  Sim
                </span>
              </Link>
            </nav>
          </div>
        </div>
      </div>

      {/* Footer Broker Connection Status */}
      <Link
        href="/auth"
        onClick={() => handleNav("/auth")}
        className="p-3 border-t border-slate-200 bg-slate-50 text-xs block hover:bg-slate-100 transition group text-decoration-none"
      >
        <div className="flex items-center justify-between mb-1">
          <span className="text-[11px] font-medium text-slate-600 group-hover:text-blue-600 transition">Broker Auth Gateway</span>
          <span className="inline-flex items-center gap-1 text-[10px] font-mono text-emerald-700 font-semibold">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span> {fyersStatus?.connected ? "Live Active" : "Pro Desk Demo"}
          </span>
        </div>
        <div className="text-[10px] text-slate-400 font-mono truncate">
          {fyersStatus?.fy_id ? `ID: ${fyersStatus.fy_id}` : "Token: FYERS-NSE-PRO-8491"} ↗
        </div>
      </Link>
    </aside>
  );
}
