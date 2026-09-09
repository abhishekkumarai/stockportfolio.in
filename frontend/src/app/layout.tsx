import type { Metadata } from "next";
import { Analytics } from "@vercel/analytics/next";
import Sidebar from "@/components/Sidebar";
import TopBar from "@/components/TopBar";
import "./globals.css";

export const metadata: Metadata = {
  title: "stockportfolio.in | Institutional Quant Alpha & Portfolio Intelligence Terminal",
  description:
    "Institutional quant risk, Danger vs Growth radar, tax-aware rebalancing, Piotroski forensics, walk-forward ML alpha factor matrix, and macro transmission radar for Indian equities.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="bg-slate-50 font-sans text-slate-900 antialiased">
        <div className="app-layout-container">
          {/* Left-Side Fixed Enterprise Navigation Rail */}
          <Sidebar />

          {/* Right Main Viewport */}
          <div className="app-main-viewport bg-slate-50">
            {/* Top Real-Time Ticker & Command Bar */}
            <TopBar />

            {/* Main Content Viewport */}
            <main className="viewport-main-content">{children}</main>

            {/* Institutional Compact Footer */}
            <footer className="compact-footer">
              <div className="compact-footer-content">
                <span className="font-medium text-slate-600">
                  © 2026 stockportfolio.in · Institutional Portfolio Intelligence & Quant Alpha Console
                </span>
                <span className="footer-disclaimer font-mono text-[11px] text-slate-500">
                  NSE/BSE End-of-Day & Live indicative telemetry. Not SEBI registered investment advice.
                </span>
              </div>
            </footer>
          </div>
        </div>
        <Analytics />
      </body>
    </html>
  );
}
