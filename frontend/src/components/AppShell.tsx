"use client";

import { useState, useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import Sidebar from "./Sidebar";
import TopBar from "./TopBar";
import { isAuthenticated } from "@/lib/auth";

export default function AppShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [desktopSidebarOpen, setDesktopSidebarOpen] = useState(true);
  const [mobileDrawerOpen, setMobileDrawerOpen] = useState(false);
  const [authChecked, setAuthChecked] = useState(false);
  const [authed, setAuthed] = useState(false);

  // Synchronize client-side auth state
  useEffect(() => {
    const checkAuth = () => {
      const auth = isAuthenticated();
      setAuthed(auth);
      setAuthChecked(true);

      if (!auth && pathname !== "/auth") {
        const dest = pathname !== "/" ? `/auth?redirect=${encodeURIComponent(pathname)}` : "/auth";
        router.replace(dest);
      }
    };

    checkAuth();

    const handleAuthChange = () => checkAuth();
    window.addEventListener("auth-changed", handleAuthChange);
    window.addEventListener("storage", handleAuthChange);

    return () => {
      window.removeEventListener("auth-changed", handleAuthChange);
      window.removeEventListener("storage", handleAuthChange);
    };
  }, [pathname, router]);

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

  // Prevent flash of protected content while evaluating authentication
  if (!authChecked && pathname !== "/auth") {
    return (
      <div className="flex h-screen w-screen items-center justify-center bg-slate-950 text-slate-100 font-mono">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-emerald-500 border-t-transparent" />
          <span className="text-xs uppercase tracking-widest text-slate-400">
            Verifying Session Credentials...
          </span>
        </div>
      </div>
    );
  }

  // If unauthenticated and not on /auth yet, show spinner while redirect takes effect
  if (!authed && pathname !== "/auth") {
    return (
      <div className="flex h-screen w-screen items-center justify-center bg-slate-950 text-slate-100 font-mono">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-indigo-500 border-t-transparent" />
          <span className="text-xs uppercase tracking-widest text-slate-400">
            Redirecting to Authentication...
          </span>
        </div>
      </div>
    );
  }

  // Full-screen dedicated view for authentication page (no sidebar, no topbar, no dashboard footer)
  if (pathname === "/auth") {
    return <div className="w-full min-h-screen bg-slate-950">{children}</div>;
  }

  return (
    <div className="flex w-full max-w-full min-h-screen overflow-x-hidden">
      {/* Desktop Fixed Enterprise Navigation Rail */}
      <div
        className={`hidden lg:block shrink-0 transition-[width] duration-200 ease-in-out h-screen sticky top-0 ${
          desktopSidebarOpen ? "w-60" : "w-0 overflow-hidden"
        }`}
      >
        <Sidebar onToggleCollapse={handleToggleSidebar} />
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
              onToggleCollapse={() => setMobileDrawerOpen(false)}
            />
          </div>
        </div>
      )}

      {/* Right Main Viewport */}
      <div className="flex-1 min-w-0 w-full max-w-full flex flex-col min-h-screen overflow-x-hidden bg-slate-50">
        {/* Top Real-Time Command Bar */}
        <TopBar
          onToggleSidebar={handleToggleSidebar}
          isSidebarOpen={mobileDrawerOpen || desktopSidebarOpen}
          isDesktopSidebarOpen={desktopSidebarOpen}
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
