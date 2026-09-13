"use client";

import EmptyPortfolioNotice from "../EmptyPortfolioNotice";
import { usePortfolioContext } from "../PortfolioContext";
import AiMemo from "../AiMemo";

export default function MemoView() {
  const { portfolio } = usePortfolioContext();

  return (
    <div>
      <div style={{ marginBottom: 20 }}>
        <h1 style={{ margin: 0, fontSize: "1.6rem" }}>AI Memo</h1>
        <p style={{ color: "var(--text-secondary)", margin: "6px 0 0" }}>
          An LLM-written monthly memo over your portfolio&apos;s computed metrics.
        </p>
      </div>

      <EmptyPortfolioNotice />

      <div style={{ marginBottom: 16 }}>
        <h3 style={{ fontSize: "1.05rem", margin: 0 }}>Monthly Portfolio Memo</h3>
        <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", margin: "4px 0 0" }}>
          An LLM writing over the numbers on this page — never inventing a metric, and every
          figure checked back against the computed data before it is shown.
        </p>
      </div>
      <AiMemo portfolio={portfolio} />
    </div>
  );
}
