"use client";

import { usePortfolioContext } from "./PortfolioContext";
import SampleDataNotice from "./SampleDataNotice";

export default function AnalysisGate({ children }: { children: React.ReactNode }) {
  const { loading, danger, analysisIsSample, isEmpty } = usePortfolioContext();

  if (loading && !danger) {
    return (
      <div className="glass-panel" style={{ textAlign: "center", padding: "32px 16px", marginBottom: 24 }}>
        <div className="spinner" style={{ margin: "0 auto 12px" }} />
        <p style={{ color: "var(--text-secondary)", margin: 0 }}>Evaluating Danger Matrix & Expected Growth...</p>
      </div>
    );
  }

  return (
    <>
      {analysisIsSample && !isEmpty && (
        <SampleDataNotice text="The full risk/growth analysis couldn't be computed for your holdings, so the numbers below are an illustrative example instead of your real data." />
      )}
      {children}
    </>
  );
}
