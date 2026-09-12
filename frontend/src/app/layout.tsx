import type { Metadata } from "next";
import { Analytics } from "@vercel/analytics/next";
import Sidebar from "@/components/Sidebar";
import TopBar from "@/components/TopBar";
import "./globals.css";

export const metadata: Metadata = {
  title: "StockPortfolio.in | Institutional Quant Alpha & Portfolio Intelligence Terminal",
  description:
    "Institutional quant risk, Danger vs Growth radar, tax-aware rebalancing, Piotroski forensics, walk-forward ML alpha factor matrix, and macro transmission radar for Indian equities.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="overflow-x-hidden">
      <body className="bg-slate-50 font-sans text-slate-900 antialiased overflow-x-hidden min-h-screen w-full max-w-full">
        <div className="flex w-full max-w-full min-h-screen overflow-x-hidden">
          {/* Left-Side Fixed Enterprise Navigation Rail */}
          <div className="hidden lg:block shrink-0">
            <Sidebar />
          </div>

          {/* Right Main Viewport */}
          <div className="flex-1 min-w-0 w-full max-w-full flex flex-col min-h-screen overflow-x-hidden bg-slate-50">
            {/* Top Real-Time Command Bar */}
            <TopBar />

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
        {process.env.VERCEL && <Analytics />}
      </body>
    </html>
  );
}
