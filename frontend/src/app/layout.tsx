import type { Metadata } from "next";
import { Analytics } from "@vercel/analytics/next";
import AppShell from "@/components/AppShell";
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
        <AppShell>{children}</AppShell>
        {process.env.VERCEL && <Analytics />}
      </body>
    </html>
  );
}
