import type { Metadata } from "next";
import { Suspense } from "react";
import RebalanceView from "./RebalanceView";

export const metadata: Metadata = {
  title: "Tax Rebalance | stockportfolio.in",
  description: "A tax-aware rebalance order sheet optimized around STCG, LTCG, and zero-tax cash inflow routing.",
};

export default function PortfolioRebalancePage() {
  return (
    <Suspense
      fallback={
        <div className="loading-container">
          <div className="spinner" />
        </div>
      }
    >
      <RebalanceView />
    </Suspense>
  );
}
