"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, useEffect, useRef } from "react";
import { Search, Bell, TrendingUp, TrendingDown, Menu, X } from "lucide-react";
import { apiUrl } from "@/lib/api";
import { getMacroOverview, type MacroOverview } from "@/lib/macroApi";

interface TickerSuggestion {
  symbol: string;
  name: string;
  exchange: string;
}

interface TopBarProps {
  onToggleSidebar?: () => void;
  isSidebarOpen?: boolean;
  isDesktopSidebarOpen?: boolean;
}

export default function TopBar({
  onToggleSidebar,
  isSidebarOpen,
  isDesktopSidebarOpen = true,
}: TopBarProps = {}) {
  const router = useRouter();
  const [searchQuery, setSearchQuery] = useState("");
  const [suggestions, setSuggestions] = useState<TickerSuggestion[]>([]);
  const [showDropdown, setShowDropdown] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);
  const [indices, setIndices] = useState<MacroOverview["indices"] | null>(null);
  const [vix, setVix] = useState<MacroOverview["vix"] | null>(null);

  // Real index/VIX ticks from the macro snapshot (15-min TTL cache server-side)
  useEffect(() => {
    let cancelled = false;
    getMacroOverview()
      .then((data) => {
        if (cancelled || !data.available) return;
        setIndices(data.indices ?? null);
        setVix(data.vix ?? null);
      })
      .catch((err) => console.error("Error fetching macro overview:", err));
    return () => {
      cancelled = true;
    };
  }, []);

  // Keyboard shortcut listener for Cmd+K / Ctrl+K and Escape
  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && (event.key === "k" || event.key === "K")) {
        event.preventDefault();
        searchInputRef.current?.focus();
        searchInputRef.current?.select();
      } else if (event.key === "Escape") {
        setShowDropdown(false);
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  // Close dropdown on outside click
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setShowDropdown(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Fetch search suggestions
  useEffect(() => {
    if (searchQuery.trim().length === 0) {
      setSuggestions([]);
      setShowDropdown(false);
      return;
    }

    const timer = setTimeout(async () => {
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
      }
    }, 200);

    return () => clearTimeout(timer);
  }, [searchQuery]);

  const handleSelectTicker = (symbol: string) => {
    const cleanSymbol = symbol.replace(/\.(NS|BO)$/i, "");
    router.push(`/analyse/${cleanSymbol}`);
    setShowDropdown(false);
    setSearchQuery("");
  };

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const clean = searchQuery.trim().toUpperCase();
    if (!clean) return;
    if (suggestions.length > 0) {
      handleSelectTicker(suggestions[0].symbol);
    } else {
      router.push(`/analyse/${clean}`);
    }
    setShowDropdown(false);
    setSearchQuery("");
  };

  return (
    <header className="w-full max-w-full h-14 sticky top-0 z-40 bg-white border-b border-slate-200 px-3 sm:px-4 flex items-center justify-between select-none shadow-[0_1px_2px_0_rgba(15,23,42,0.03)] gap-2 sm:gap-4">
      {/* Left Section: Sidebar Toggle (when collapsed / mobile) & Market Telemetry */}
      <div className="flex items-center gap-2 sm:gap-3 shrink-0">
        <button
          type="button"
          onClick={onToggleSidebar}
          className={`p-1.5 -ml-1 text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded-md transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 ${
            isDesktopSidebarOpen ? "lg:hidden" : "flex"
          }`}
          aria-label="Toggle navigation menu"
          title="Toggle Navigation Menu"
        >
          <Menu size={20} />
        </button>

        {/* Market Telemetry Chips — real data from /api/macro, hidden until available */}
        <div className="flex items-center gap-1.5 sm:gap-2 text-xs font-mono">
          <TickerChip
            className="flex"
            label="NIFTY 50"
            value={indices?.nifty50?.current}
            changePct={indices?.nifty50?.change_pct}
          />
          <TickerChip
            className="hidden xl:flex"
            label="SENSEX"
            value={indices?.sensex?.current}
            changePct={indices?.sensex?.change_pct}
          />
          <TickerChip
            className="hidden 2xl:flex"
            label="INDIA VIX"
            value={vix?.current}
            changePct={vix?.change_pct}
          />
        </div>
      </div>

      {/* Center Section: Universal Search */}
      <div className="flex-1 min-w-[120px] max-w-md relative" ref={dropdownRef}>
        <form onSubmit={handleSearchSubmit} className="relative flex items-center w-full">
          <Search size={14} className="absolute left-3 text-slate-400 pointer-events-none" />
          <input
            ref={searchInputRef}
            type="text"
            placeholder="Search equities, F&O, funds... (Cmd+K)"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full h-8 sm:h-9 pl-8 sm:pl-9 pr-10 text-xs font-sans bg-slate-50 focus:bg-white text-slate-900 placeholder-slate-400 rounded-md border border-slate-200 focus:border-blue-600 focus:outline-none focus:ring-1 focus:ring-blue-600 transition-all"
          />
          <div className="hidden sm:flex absolute right-2 items-center px-1.5 py-0.5 rounded border border-slate-200 bg-white text-[10px] font-mono text-slate-400 shadow-2xs pointer-events-none">
            ⌘K
          </div>
        </form>

        {/* Dropdown Suggestions */}
        {showDropdown && suggestions.length > 0 && (
          <div className="absolute left-0 right-0 top-full mt-1 bg-white border border-slate-200 rounded-lg shadow-xl overflow-hidden z-50 divide-y divide-slate-100 max-h-72 overflow-y-auto">
            {suggestions.map((item) => (
              <div
                key={item.symbol}
                onClick={() => handleSelectTicker(item.symbol)}
                className="px-4 py-2.5 hover:bg-slate-50 cursor-pointer flex items-center justify-between text-xs transition"
              >
                <div className="flex items-center gap-2">
                  <span className="font-mono font-bold text-slate-900">{item.symbol}</span>
                  <span className="text-slate-500 truncate max-w-xs">{item.name}</span>
                </div>
                <span className="font-mono text-[10px] text-blue-600 uppercase font-semibold">
                  {item.exchange}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Right Section: Notifications & Account */}
      <div className="flex items-center gap-2 sm:gap-3 shrink-0">
        {/* Notifications — no notification source is wired yet, so no unread badge */}
        <button
          type="button"
          aria-label="Notifications (none yet)"
          title="Notifications are not yet available"
          disabled
          className="relative p-1.5 text-slate-300 rounded-md shrink-0 cursor-not-allowed"
        >
          <Bell size={17} />
        </button>

        {/* Account / Broker Quick Link (visible on wide displays, profile is in sidebar bottom) */}
        <Link
          href="/auth"
          className="hidden 2xl:flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-mono bg-slate-50 hover:bg-slate-100 text-slate-700 border border-slate-200 transition group text-decoration-none shrink-0"
          title="Sign in / manage account"
        >
          <span className="text-[11px] font-semibold text-slate-800 group-hover:text-blue-600 transition">Account</span>
          <span className="text-[10px] text-slate-400">↗</span>
        </Link>
      </div>
    </header>
  );
}

function TickerChip({
  className,
  label,
  value,
  changePct,
}: {
  className: string;
  label: string;
  value: number | null | undefined;
  changePct: number | null | undefined;
}) {
  // Nothing fetched yet, or the upstream feed was unavailable — omit rather than fabricate.
  if (value == null || changePct == null) return null;
  const isUp = changePct >= 0;
  return (
    <div className={`${className} items-center gap-1 sm:gap-1.5 px-2 py-1 bg-slate-50 rounded border border-slate-200 shrink-0`}>
      <span className="text-slate-500 text-[10px] sm:text-[11px] font-sans font-medium">{label}</span>
      <span className="font-semibold text-slate-900 text-[11px]">
        {value.toLocaleString("en-IN", { maximumFractionDigits: 2 })}
      </span>
      <span
        className={`font-semibold text-[10px] px-1 rounded flex items-center ${
          isUp ? "text-emerald-700 bg-emerald-50" : "text-red-700 bg-red-50"
        }`}
      >
        {isUp ? <TrendingUp size={9} className="mr-0.5" /> : <TrendingDown size={9} className="mr-0.5" />}
        {isUp ? "+" : ""}
        {changePct.toFixed(2)}%
      </span>
    </div>
  );
}
