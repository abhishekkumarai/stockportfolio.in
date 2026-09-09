import type { Metadata } from "next";
import { Suspense } from "react";
import PortfolioDashboard from "./PortfolioDashboard";

export const metadata: Metadata = {
  title: "My Portfolio | stockportfolio.in",
  description:
    "Track your Indian equity and mutual fund holdings in one place, with live valuations, profit and loss, and allocation breakdowns.",
};

export default function PortfolioPage() {
  return (
    <Suspense
      fallback={
        <div className="app-container">
          <div className="loading-container">
            <div className="spinner" />
          </div>
        </div>
      }
    >
      <PortfolioDashboard />
    </Suspense>
  );
}
