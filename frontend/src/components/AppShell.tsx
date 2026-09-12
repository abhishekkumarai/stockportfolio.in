"use client";

import { useState, useEffect } from "react";
import Sidebar from "./Sidebar";
import TopBar from "./TopBar";

export default function AppShell({ children }: { children: React.ReactNode }) {
  const [desktopSidebarOpen, setDesktopSidebarOpen] = useState(true);
  const [mobileDrawerOpen, setMobileDrawerOpen] = useState(false);

  // Close mobile drawer on Escape key
  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setMobileDrawerOpen(false);
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  const handleToggleSidebar = () => {
    if (typeof window !== "undefined" && window.innerWidth < 1024) {
      setMobileDrawerOpen((prev) => !prev);
    } else {
      setDesktopSidebarOpen((prev) => !prev);
    }
  };

  return (
    <div className="flex w-full max-w-full min-h-screen overflow-x-hidden">
      {/* Desktop Fixed Enterprise Navigation Rail */}
      <div
        className={`hidden lg:block shrink-0 transition-[width] duration-200 ease-in-out ${
          desktopSidebarOpen ? "w-56" : "w-0 overflow-hidden"
        }`}
      >
        <Sidebar />
      </div>

      {/* Mobile Drawer Overlay */}
      {mobileDrawerOpen && (
        <div
          onClick={() => setMobileDrawerOpen(false)}
          className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-xs lg:hidden transition-opacity flex cursor-pointer"
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="w-64 max-w-[85vw] h-full bg-white shadow-2xl relative flex flex-col cursor-default"
          >
            <Sidebar
              onNavigate={() => setMobileDrawerOpen(false)}
              onClose={() => setMobileDrawerOpen(false)}
            />
          </div>
        </div>
      )}

      {/* Right Main Viewport */}
      <div className="flex-1 min-w-0 w-full max-w-full flex flex-col min-h-screen overflow-x-hidden bg-slate-50">
        {/* Top Real-Time Command Bar with Hamburger button */}
        <TopBar
          onToggleSidebar={handleToggleSidebar}
          isSidebarOpen={mobileDrawerOpen || desktopSidebarOpen}
        />

        {/* Main Content Viewport */}
        <main className="flex-1 min-w-0 w-full max-w-full overflow-x-hidden">
          {children}
        </main>

        {/* Institutional Compact Footer */}
        <footer className="w-full border-t border-slate-200 bg-white py-3 px-6 text-xs text-slate-500 flex flex-col sm:flex-row items-center justify-between gap-2 font-mono">
          <span>
            © 2026 StockPortfolio.in · Institutional Decision Support & Quantitative Execution Desk
          </span>
          <span className="text-[11px] text-slate-400">
            NSE/BSE End-of-Day & Live Indicative Telemetry. Not SEBI Registered Investment Advice.
          </span>
        </footer>
      </div>
    </div>
  );
}
