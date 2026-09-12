"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, useEffect, useRef } from "react";
import { Search, Bell, TrendingUp, TrendingDown, Menu, X } from "lucide-react";
import { apiUrl } from "@/lib/api";

interface TickerSuggestion {
  symbol: string;
  name: string;
  exchange: string;
}

interface TopBarProps {
  onToggleSidebar?: () => void;
  isSidebarOpen?: boolean;
}

export default function TopBar({ onToggleSidebar, isSidebarOpen }: TopBarProps = {}) {
  const router = useRouter();
  const [searchQuery, setSearchQuery] = useState("");
  const [suggestions, setSuggestions] = useState<TickerSuggestion[]>([]);
  const [showDropdown, setShowDropdown] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);

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
    <header className="w-full max-w-full h-14 sticky top-0 z-50 bg-white border-b border-slate-200 px-4 flex items-center justify-between overflow-hidden select-none shadow-[0_1px_2px_0_rgba(15,23,42,0.03)]">
      {/* Left Section: Hamburger Menu, Logo & Live Benchmarks */}
      <div className="flex items-center gap-2 sm:gap-3 shrink-0 min-w-0">
        <button
          type="button"
          onClick={onToggleSidebar}
          className="p-1.5 -ml-1 text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded-md transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500"
          aria-label="Toggle navigation menu"
          title="Toggle Navigation Menu"
        >
          <Menu size={20} />
        </button>

        <Link href="/" className="flex items-center gap-2 text-decoration-none">
          <div className="w-8 h-8 rounded bg-blue-600 flex items-center justify-center text-white font-bold text-sm shadow-sm">
            SP
          </div>
          <div className="flex flex-col leading-tight">
            <div className="flex items-center gap-1.5">
              <span className="font-bold text-slate-900 text-[15px] tracking-tight font-sans">
                StockPortfolio<span className="text-blue-600">.in</span>
              </span>
              <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded bg-blue-50 text-blue-700 border border-blue-200 tracking-wider uppercase font-mono">
                Enterprise Cockpit
              </span>
            </div>
          </div>
        </Link>

        <div className="h-5 w-[1px] bg-slate-200 mx-1 hidden sm:block"></div>

        {/* Live Benchmarks */}
        <div className="hidden md:flex items-center gap-2 text-xs font-mono">
          <div className="flex items-center gap-1.5 px-2 py-1 bg-slate-50 rounded border border-slate-200 shrink-0">
            <span className="text-slate-500 text-[11px] font-sans font-medium">NIFTY 50</span>
            <span className="font-semibold text-slate-900">24,852.15</span>
            <span className="text-emerald-700 font-semibold text-[10.5px] bg-emerald-50 px-1 rounded flex items-center">
              <TrendingUp size={10} className="mr-0.5" /> +0.58%
            </span>
          </div>

          <div className="flex items-center gap-1.5 px-2 py-1 bg-slate-50 rounded border border-slate-200 shrink-0">
            <span className="text-slate-500 text-[11px] font-sans font-medium">SENSEX</span>
            <span className="font-semibold text-slate-900">81,332.70</span>
            <span className="text-emerald-700 font-semibold text-[10.5px] bg-emerald-50 px-1 rounded flex items-center">
              <TrendingUp size={10} className="mr-0.5" /> +0.51%
            </span>
          </div>

          <div className="flex items-center gap-1.5 px-2 py-1 bg-slate-50 rounded border border-slate-200 shrink-0">
            <span className="text-slate-500 text-[11px] font-sans font-medium">INDIA VIX</span>
            <span className="font-semibold text-slate-900">13.45</span>
            <span className="text-emerald-700 font-semibold text-[10.5px] bg-emerald-50 px-1 rounded flex items-center">
              <TrendingDown size={10} className="mr-0.5" /> -4.41%
            </span>
          </div>

          <div className="hidden xl:flex items-center gap-2 shrink-0">
            <div className="flex items-center gap-1.5 px-2 py-1 bg-slate-50 rounded border border-slate-200 shrink-0">
              <span className="text-slate-500 text-[11px] font-sans font-medium">BRENT</span>
              <span className="font-semibold text-slate-900">$74.80</span>
              <span className="text-emerald-700 text-[10px] font-semibold">+0.4%</span>
            </div>
            <div className="flex items-center gap-1.5 px-2 py-1 bg-slate-50 rounded border border-slate-200 shrink-0">
              <span className="text-slate-500 text-[11px] font-sans font-medium">USD/INR</span>
              <span className="font-semibold text-slate-900">₹83.94</span>
              <span className="text-slate-500 text-[10px]">-0.05%</span>
            </div>
          </div>
        </div>
      </div>

      {/* Center Section: Universal Search */}
      <div className="min-w-0 flex-1 max-w-md mx-4 hidden md:block" ref={dropdownRef}>
        <form onSubmit={handleSearchSubmit} className="relative flex items-center">
          <Search size={15} className="absolute left-3 text-slate-400" />
          <input
            ref={searchInputRef}
            type="text"
            placeholder="Search 500+ Indian equities, F&O contracts, AMFI funds... (Cmd+K)"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full h-9 pl-9 pr-12 text-xs font-sans bg-slate-50 focus:bg-white text-slate-900 placeholder-slate-400 rounded-md border border-slate-300 focus:border-blue-600 focus:outline-none focus:ring-1 focus:ring-blue-600 transition-all"
          />
          <div className="absolute right-2.5 flex items-center gap-0.5 px-1.5 py-0.5 rounded border border-slate-200 bg-white text-[10px] font-mono text-slate-400 shadow-2xs">
            ⌘K
          </div>
        </form>

        {/* Dropdown Suggestions */}
        {showDropdown && suggestions.length > 0 && (
          <div className="absolute left-0 right-0 mt-1 bg-white border border-slate-200 rounded-lg shadow-xl overflow-hidden z-50 divide-y divide-slate-100 max-h-72 overflow-y-auto">
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

      {/* Right Section: Socket Status & User Profile */}
      <div className="flex items-center gap-3">
        {/* Live WebSocket status */}
        <div className="flex items-center gap-1.5 px-2.5 py-1 bg-emerald-50 border border-emerald-200 rounded-full text-xs font-mono text-emerald-700">
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
          <span className="font-medium text-[11px]">WebSocket Live 3ms</span>
        </div>

        {/* Notifications */}
        <button
          aria-label="Notifications"
          className="relative p-1.5 text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded-md transition-colors"
        >
          <Bell size={18} />
          <span className="absolute top-1 right-1 w-2 h-2 bg-red-600 rounded-full ring-2 ring-white"></span>
        </button>

        <div className="h-5 w-[1px] bg-slate-200 hidden sm:block"></div>

        {/* User Profile */}
        <div className="flex items-center gap-2.5 pl-1 cursor-pointer group">
          <div className="w-7 h-7 rounded-full bg-slate-800 text-white font-semibold text-xs flex items-center justify-center border border-slate-200 group-hover:ring-2 group-hover:ring-blue-600/40 transition-all">
            AK
          </div>
          <div className="hidden lg:flex flex-col text-left leading-none">
            <span className="text-xs font-semibold text-slate-900 group-hover:text-blue-600 transition-colors">
              Abhishek Kumar
            </span>
            <span className="text-[10px] text-slate-400 mt-0.5 font-mono">Institutional Pro Desk</span>
          </div>
        </div>
      </div>
    </header>
  );
}
