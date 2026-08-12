import type { Metadata } from "next";
import Link from "next/link";
import { Analytics } from "@vercel/analytics/next";
import "./globals.css";

export const metadata: Metadata = {
  title: "stockportfolio.in | Indian Stock Sentiment & Backtesting",
  description: "Analyze Indian listed stocks (NSE & BSE) using technical indicators, online news sentiment scraping, and run advanced strategy backtesting.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        <header className="app-header">
          <Link href="/" style={{ textDecoration: 'none' }}>
            <div className="app-logo">
              stock<span>portfolio.in</span>
            </div>
          </Link>
          <nav className="nav-links">
            <Link href="/" className="nav-link">
              Dashboard
            </Link>
            <Link href="/backtest" className="nav-link">
              Backtest Strategy
            </Link>
          </nav>
        </header>
        <main style={{ minHeight: 'calc(100vh - 70px)' }}>
          {children}
        </main>
        <Analytics />
      </body>
    </html>
  );
}
