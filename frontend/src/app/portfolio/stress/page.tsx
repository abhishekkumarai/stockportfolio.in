import type { Metadata } from "next";
import { Suspense } from "react";
import StressView from "./StressView";

export const metadata: Metadata = {
  title: "Crash Simulator | stockportfolio.in",
  description: "Simulate how your portfolio would perform in major historical market crashes.",
};

export default function PortfolioStressPage() {
  return (
    <Suspense
      fallback={
        <div className="loading-container">
          <div className="spinner" />
        </div>
      }
    >
      <StressView />
    </Suspense>
  );
}
