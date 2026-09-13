import type { Metadata } from "next";
import { Suspense } from "react";
import HoldingsView from "./HoldingsView";

export const metadata: Metadata = {
  title: "Holdings | stockportfolio.in",
  description:
    "Track your Indian equity and mutual fund holdings in one place, with live valuations, profit and loss, and allocation breakdowns.",
};

export default function PortfolioHoldingsPage() {
  return (
    <Suspense
      fallback={
        <div className="loading-container">
          <div className="spinner" />
        </div>
      }
    >
      <HoldingsView />
    </Suspense>
  );
}
