"use client";

import Link from "next/link";
import {
  Menu,
  X,
  Bot,
  Calculator,
  Compass,
  FlaskConical,
  Landmark,
  LayoutDashboard,
  Radio,
  Microscope,
  Newspaper,
  NotebookPen,
  PenLine,
  Radar,
  Scale,
  Search,
  ShieldAlert,
  Target,
  TrendingDown,
  Zap,
} from "lucide-react";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { getFyersStatus, getToken, loginUrl, type FyersStatus } from "@/lib/portfolioApi";

/** Exactly one nav item is current: the href has to match the tab as well.
 *
 * `/portfolio` (no tab) is the dashboard link, so it stays highlighted while
 * the page's own default tab is showing rather than going dark until the user
 * clicks a tab. Hash-only links (`/#claude-mcp`) never count as current.
 */
function isCurrent(href: string, pathname: string, search: string): boolean {
  if (href.includes("#")) return false;

  const [path, query = ""] = href.split("?");
  if (path !== pathname) return false;

  const currentTab = new URLSearchParams(search).get("tab");
  const itemTab = new URLSearchParams(query).get("tab");
  if (itemTab === null) return currentTab === null;
  return itemTab === currentTab;
}

export default function Sidebar() {
  const pathname = usePathname();
  const [fyersStatus, setFyersStatus] = useState<FyersStatus | null>(null);
  const [mobileOpen, setMobileOpen] = useState(false);
  // Seven of these links point at /portfolio with a different ?tab=, so
  // pathname alone cannot tell them apart - it marked all seven active at
  // once. The query string is tracked here rather than with
  // `useSearchParams`, which would opt every prerendered page out of static
  // HTML for the sake of one highlight.
  const [search, setSearch] = useState("");
  const navRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const sync = () => setSearch(window.location.search);
    sync();
    // Back/forward changes the tab without changing the pathname.
    window.addEventListener("popstate", sync);
    return () => window.removeEventListener("popstate", sync);
  }, [pathname]);

  // Land with the current section in view: on a short window barely a third
  // of the nav fits, and the item you are on is usually not in that third.
  //
  // The nav's own scrollTop is set rather than calling scrollIntoView, which
  // also scrolls every scrollable ancestor - including the window, which would
  // jump the page the user is reading.
  useEffect(() => {
    const nav = navRef.current;
    if (!nav) return;
    let cancelled = false;

    const bringActiveIntoView = () => {
      if (cancelled) return;
      const active = nav.querySelector<HTMLElement>(".sidebar-nav-item.active");
      if (!active) return;
      const navBox = nav.getBoundingClientRect();
      const itemBox = active.getBoundingClientRect();
      if (itemBox.top >= navBox.top && itemBox.bottom <= navBox.bottom) return;
      nav.scrollTop += itemBox.top - navBox.top - (navBox.height - itemBox.height) / 2;
    };

    // Measured more than once on purpose. The first frame lands before Inter
    // and Outfit have swapped in, and the font swap changes every row's
    // height - a single early measurement decides the item is visible, and
    // then it is not.
    const frame = requestAnimationFrame(bringActiveIntoView);
    const timers = [
      window.setTimeout(bringActiveIntoView, 120),
      window.setTimeout(bringActiveIntoView, 500),
    ];
    return () => {
      cancelled = true;
      cancelAnimationFrame(frame);
      timers.forEach(clearTimeout);
    };
  }, [pathname, search]);

  // The shell contract, asserted where it can be seen. The previous layout
  // failed silently - `position: sticky` stops sticking as soon as an ancestor
  // becomes a scroll container, and nothing anywhere said so; the sidebar just
  // scrolled off the top of long pages. This makes that class of regression
  // loud in development and costs nothing in production.
  useEffect(() => {
    if (process.env.NODE_ENV === "production") return;
    const el = navRef.current?.closest(".app-sidebar");
    if (!el) return;
    const { position } = window.getComputedStyle(el);
    const height = Math.round(el.getBoundingClientRect().height);
    if (position !== "fixed") {
      console.error(
        `[shell] .app-sidebar must stay position: fixed (it is "${position}"). ` +
          "See the APP SHELL contract in globals.css - a non-fixed sidebar " +
          "scrolls away on long pages."
      );
    } else if (Math.abs(height - window.innerHeight) > 2) {
      console.error(
        `[shell] .app-sidebar is ${height}px tall but the viewport is ` +
          `${window.innerHeight}px. Something is overriding inset-block: 0.`
      );
    }
  }, [pathname]);

  useEffect(() => {
    if (typeof window === "undefined" || !getToken()) return;
    const controller = new AbortController();
    getFyersStatus(controller.signal)
      .then(setFyersStatus)
      .catch(() => setFyersStatus(null));
    return () => controller.abort();
  }, [pathname]);

  const navSections = [
    {
      title: "PORTFOLIO INTELLIGENCE",
      items: [
        {
          label: "Dashboard & Health",
          href: "/portfolio",
          icon: LayoutDashboard,
          badge: "Live",
          badgeTone: "var(--accent-cyan)",
        },
        {
          label: "Danger & Growth Radar",
          href: "/portfolio?tab=overview",
          icon: ShieldAlert,
          badge: "Quant",
          badgeTone: "var(--color-sell)",
        },
        {
          label: "Crash Stress Simulator",
          href: "/portfolio?tab=stress",
          icon: Zap,
        },
        {
          label: "Tax-Aware Rebalancer",
          href: "/portfolio?tab=rebalance",
          icon: Scale,
          badge: "Zero Tax",
          badgeTone: "var(--accent-cyan)",
        },
        {
          label: "Holdings News Catalysts",
          href: "/portfolio?tab=news",
          icon: Newspaper,
        },
        {
          label: "AI Monthly Memo",
          href: "/portfolio?tab=memo",
          icon: PenLine,
          badge: "Narrated",
          badgeTone: "var(--accent-purple)",
        },
      ],
    },
    {
      title: "RESEARCH & DISCOVERY",
      items: [
        {
          label: "Live Market Pulse",
          href: "/pulse",
          icon: Radio,
          badge: "Live",
          badgeTone: "var(--color-buy)",
        },
        {
          label: "Buy & Sell Calls",
          href: "/recommendations",
          icon: Target,
          badge: "Ranked",
          badgeTone: "var(--color-buy)",
        },
        {
          label: "NSE Universe Screener",
          href: "/screener",
          icon: Search,
          badge: "500",
          badgeTone: "var(--accent-cyan)",
        },
        {
          label: "Stock Deep-Dive",
          href: "/analyse/RELIANCE",
          icon: Microscope,
        },
        {
          label: "Mutual Funds Explorer",
          href: "/funds",
          icon: Landmark,
        },
      ],
    },
    {
      title: "QUANT & DERIVATIVES",
      items: [
        {
          label: "India Macro Radar",
          href: "/macro",
          icon: Compass,
          badge: "Macro",
          badgeTone: "var(--accent-cyan)",
        },
        {
          label: "Quant Lab",
          href: "/quant",
          icon: Calculator,
          badge: "HRP",
          badgeTone: "var(--accent-purple)",
        },
        {
          label: "Option Chain & Hedging",
          href: "/options",
          icon: Radar,
          badge: "Fyers",
          badgeTone: "var(--accent-cyan)",
        },
      ],
    },
    {
      title: "LAB & AGENT TOOLS",
      items: [
        {
          label: "Strategy Lab (v2)",
          href: "/lab",
          icon: FlaskConical,
          badge: "Walk-fwd",
          badgeTone: "var(--color-buy)",
        },
        {
          label: "Classic Backtester",
          href: "/backtest",
          icon: TrendingDown,
        },
        {
          label: "Paper Trading Ledger",
          href: "/paper",
          icon: NotebookPen,
          badge: "Simulated",
          badgeTone: "var(--color-hold)",
        },
        {
          label: "Claude Code MCP",
          href: "/#claude-mcp",
          icon: Bot,
          badge: "MCP",
          badgeTone: "var(--accent-purple)",
        },
      ],
    },
  ];

  return (
    <>
      {/* Mobile hamburger toggle button */}
      <button
        className="mobile-sidebar-toggle"
        onClick={() => setMobileOpen(!mobileOpen)}
        aria-label="Toggle Sidebar Navigation"
      >
        {mobileOpen ? <X size={18} strokeWidth={1.5} /> : <Menu size={18} strokeWidth={1.5} />}
      </button>

      {/* Backdrop overlay for mobile drawer */}
      {mobileOpen && (
        <div className="sidebar-backdrop" onClick={() => setMobileOpen(false)} />
      )}

      {/* Main Left-Side Navbar */}
      <aside className={`app-sidebar ${mobileOpen ? "sidebar-mobile-open" : ""}`}>
        {/* Top Brand Header */}
        <div className="sidebar-brand">
          <Link href="/" className="sidebar-brand-link" onClick={() => setMobileOpen(false)}>
            <div className="sidebar-logo-pulse" />
            <div className="sidebar-logo-text">
              stock<span className="logo-accent">portfolio</span>
              <span className="logo-tld">.in</span>
            </div>
          </Link>
        </div>

        {/* Live Broker & Market Status Bar */}
        <div className="sidebar-status-card">
          <div className="status-indicator-row">
            <span className="status-dot" />
            <span className="status-title">NSE / BSE Market Feed</span>
          </div>
          {fyersStatus?.connected ? (
            <div className="broker-connected-pill">
              <span className="broker-dot connected" />
              <span>Fyers Connected ({fyersStatus.fy_id})</span>
            </div>
          ) : (
            <a href={loginUrl()} className="broker-connect-pill">
              <span>+ Connect Fyers Broker</span>
            </a>
          )}
        </div>

        {/* Navigation Sections & Links */}
        <div className="sidebar-scrollable-nav" ref={navRef}>
          {navSections.map((section, sIdx) => (
            <div key={sIdx} className="sidebar-nav-group">
              <div className="sidebar-section-title">{section.title}</div>
              <ul className="sidebar-nav-list">
                {section.items.map((item, iIdx) => {
                  const isActive = isCurrent(item.href, pathname, search);
                  return (
                    <li key={iIdx}>
                      <Link
                        href={item.href}
                        className={`sidebar-nav-item ${isActive ? "active" : ""}`}
                        onClick={() => {
                          setMobileOpen(false);
                          setSearch(item.href.includes("?") ? `?${item.href.split("?")[1]}` : "");
                        }}
                      >
                        <item.icon className="sidebar-item-icon" size={16} strokeWidth={1.5} aria-hidden />
                        <span className="sidebar-item-label">{item.label}</span>
                        {item.badge && (
                          <span
                            className="sidebar-item-badge"
                            style={{
                              borderColor: item.badgeTone,
                              color: item.badgeTone,
                            }}
                          >
                            {item.badge}
                          </span>
                        )}
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </div>

        {/* Bottom Utility Profile / Actions */}
        <div className="sidebar-footer">
          <div className="sidebar-footer-card">
            <div className="sidebar-footer-title">Institutional Quant Suite</div>
            <div className="sidebar-footer-sub">v2.4 · 100% Stateless & Private</div>
          </div>
        </div>
      </aside>
    </>
  );
}
