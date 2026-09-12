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
  Menu,
  X,
  LogIn,
  LogOut,
} from "lucide-react";
import { getFyersStatus, getToken, loadPortfolio, type FyersStatus } from "@/lib/portfolioApi";
import { getAuthUser, isAuthenticated, logout as doLogout, type User } from "@/lib/auth";

interface SidebarProps {
  onNavigate?: () => void;
  onClose?: () => void;
  onToggleCollapse?: () => void;
}

export default function Sidebar({ onNavigate, onClose, onToggleCollapse }: SidebarProps = {}) {
  const pathname = usePathname();
  const [fyersStatus, setFyersStatus] = useState<FyersStatus | null>(null);
  const [search, setSearch] = useState("");
  const [profileName, setProfileName] = useState("Portfolio Account");
  const [profileSubtitle, setProfileSubtitle] = useState("Offline / Disconnected");
  const [initials, setInitials] = useState("PA");

  useEffect(() => {
    const sync = () => setSearch(window.location.search);
    sync();
    window.addEventListener("popstate", sync);
    return () => window.removeEventListener("popstate", sync);
  }, [pathname]);

  const [isAuthed, setIsAuthed] = useState(false);

  useEffect(() => {
    const updateProfile = () => {
      try {
        const authed = isAuthenticated();
        setIsAuthed(authed);
        const authUser = getAuthUser();
        const p = loadPortfolio();
        const total = (p.equity?.length || 0) + (p.funds?.length || 0);
        const cid = typeof window !== "undefined" ? localStorage.getItem("stockportfolio_client_id") : null;
        const storedName = typeof window !== "undefined" ? localStorage.getItem("stockportfolio_user_name") : null;

        let displayName = "Portfolio Account";
        if (authUser?.display_name) {
          displayName = authUser.display_name;
        } else if (authUser?.email) {
          displayName = authUser.email.split("@")[0];
        } else if (fyersStatus?.name) {
          displayName = fyersStatus.name;
        } else if (storedName) {
          displayName = storedName;
        } else if (fyersStatus?.connected && fyersStatus.fy_id) {
          displayName = fyersStatus.fy_id;
        } else if (cid) {
          displayName = `Account ${cid}`;
        }
        setProfileName(displayName);

        const parts = displayName.trim().split(/\s+/);
        if (parts.length >= 2) {
          setInitials(`${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase());
        } else {
          setInitials(displayName.slice(0, 2).toUpperCase() || "PA");
        }

        if (authUser?.email) {
          setProfileSubtitle(total > 0 ? `${authUser.email} · ${total} Assets` : authUser.email);
        } else if (cid && total > 0) {
          setProfileSubtitle(`${cid} • ${total} Holdings`);
        } else if (fyersStatus?.fy_id) {
          setProfileSubtitle(`${fyersStatus.fy_id}${total > 0 ? ` • ${total} Holdings` : ""}`);
        } else if (total > 0) {
          setProfileSubtitle(`${total} Holdings`);
        } else if (fyersStatus?.connected) {
          setProfileSubtitle("Active Broker Session");
        } else {
          setProfileSubtitle("Not Authenticated");
        }
      } catch {
        // fallback
      }
    };

    updateProfile();
    window.addEventListener("portfolio-updated", updateProfile);
    window.addEventListener("auth-changed", updateProfile);
    return () => {
      window.removeEventListener("portfolio-updated", updateProfile);
      window.removeEventListener("auth-changed", updateProfile);
    };
  }, [fyersStatus, pathname]);

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
    <aside className="w-60 shrink-0 border-r border-slate-200 bg-white flex flex-col justify-between select-none min-h-full h-full z-40">
      {/* Top: StockPortfolio Banner & Hamburger Toggle */}
      <div className="h-14 px-3.5 border-b border-slate-200 flex items-center justify-between shrink-0 bg-white">
        <Link href="/" onClick={() => handleNav("/")} className="flex items-center gap-2 text-decoration-none min-w-0">
          <div className="w-7 h-7 rounded bg-blue-600 flex items-center justify-center text-white font-bold text-xs shadow-sm shrink-0">
            SP
          </div>
          <div className="flex flex-col leading-tight min-w-0">
            <span className="font-bold text-slate-900 text-sm tracking-tight font-sans truncate">
              StockPortfolio<span className="text-blue-600">.in</span>
            </span>
            <span className="text-[9px] font-mono text-slate-400 uppercase tracking-wider font-semibold">
              Enterprise Cockpit
            </span>
          </div>
        </Link>
        <button
          type="button"
          onClick={onToggleCollapse || onClose}
          className="p-1.5 rounded-md text-slate-500 hover:text-slate-900 hover:bg-slate-100 transition-colors shrink-0 -mr-1"
          aria-label="Toggle navigation menu"
          title="Toggle Navigation Menu"
        >
          <Menu size={18} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto py-3">

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

      {/* Bottom: User Profile Section */}
      <div className="p-3 border-t border-slate-200 bg-slate-50/90 shrink-0">
        {isAuthed ? (
          <div className="flex items-center justify-between gap-1">
            <Link
              href="/auth"
              onClick={() => handleNav("/auth")}
              className="flex items-center gap-2.5 p-1.5 -m-0.5 rounded-lg hover:bg-slate-100 transition group text-decoration-none min-w-0 flex-1"
              title="View Account Profile & Session Details"
            >
              <div className="w-8 h-8 rounded-full bg-slate-900 text-white font-semibold text-xs flex items-center justify-center border border-slate-200 group-hover:ring-2 group-hover:ring-blue-600/40 shrink-0 transition-all">
                {initials}
              </div>
              <div className="flex flex-col text-left min-w-0 flex-1 leading-tight">
                <div className="flex items-center gap-1.5">
                  <span className="text-xs font-semibold text-slate-900 truncate group-hover:text-blue-600 transition-colors">
                    {profileName}
                  </span>
                  <span
                    className={`w-2 h-2 rounded-full shrink-0 ${
                      fyersStatus?.connected
                        ? "bg-emerald-500 animate-pulse"
                        : "bg-emerald-500"
                    }`}
                    title={fyersStatus?.connected ? "Broker Connected" : "Authenticated"}
                  />
                </div>
                <span className="text-[10px] text-slate-400 font-mono truncate">
                  {profileSubtitle}
                </span>
              </div>
            </Link>
            <button
              onClick={async (e) => {
                e.preventDefault();
                e.stopPropagation();
                await doLogout();
              }}
              className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors cursor-pointer shrink-0"
              title="Log Out Session"
            >
              <LogOut size={15} />
            </button>
          </div>
        ) : (
          <Link
            href="/auth"
            onClick={() => handleNav("/auth")}
            className="flex items-center justify-center gap-2 w-full py-2 px-3 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold rounded-lg shadow-xs transition-colors text-decoration-none"
          >
            <LogIn size={14} />
            <span>Sign In to Terminal</span>
          </Link>
        )}
      </div>
    </aside>
  );
}
