import type { Metadata } from "next";
import { Suspense } from "react";
import NewsView from "./NewsView";

export const metadata: Metadata = {
  title: "Catalysts & News | stockportfolio.in",
  description: "News and corporate filings filtered strictly for the stocks and mutual funds you hold.",
};

export default function PortfolioNewsPage() {
  return (
    <Suspense
      fallback={
        <div className="loading-container">
          <div className="spinner" />
        </div>
      }
    >
      <NewsView />
    </Suspense>
  );
}
