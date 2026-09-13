import type { Metadata } from "next";
import { Suspense } from "react";
import TailRiskSizerView from "./TailRiskSizerView";

export const metadata: Metadata = {
  title: "Tail Risk Sizer | stockportfolio.in",
  description: "Size the index put or collar that caps your portfolio's drawdown at a level you choose.",
};

export default function TailRiskSizerPage() {
  return (
    <Suspense
      fallback={
        <div className="loading-container">
          <div className="spinner" />
        </div>
      }
    >
      <TailRiskSizerView />
    </Suspense>
  );
}
