"use client";

import Link from "next/link";
import { usePortfolioContext } from "./PortfolioContext";

export default function EmptyPortfolioNotice() {
  const { isEmpty } = usePortfolioContext();
  if (!isEmpty) return null;

  return (
    <div
      className="glass-panel"
      style={{ borderColor: "var(--color-hold)", marginBottom: 20, padding: "12px 16px", fontSize: "0.85rem" }}
    >
      <strong style={{ color: "var(--color-hold)" }}>No holdings loaded.</strong>{" "}
      <span style={{ color: "var(--text-secondary)" }}>
        Add or import your portfolio on the{" "}
        <Link href="/portfolio/holdings" style={{ color: "var(--accent-cyan)", fontWeight: 600 }}>
          Holdings
        </Link>{" "}
        page to see real numbers here.
      </span>
    </div>
  );
}
