import type { Metadata } from "next";
import { Suspense } from "react";
import MemoView from "./MemoView";

export const metadata: Metadata = {
  title: "AI Memo | stockportfolio.in",
  description: "An LLM-written monthly memo over your portfolio's computed metrics.",
};

export default function PortfolioMemoPage() {
  return (
    <Suspense
      fallback={
        <div className="loading-container">
          <div className="spinner" />
        </div>
      }
    >
      <MemoView />
    </Suspense>
  );
}
