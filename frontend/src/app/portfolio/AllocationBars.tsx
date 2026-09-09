"use client";

import { formatCurrency, type AllocationSlice } from "@/lib/portfolioApi";

// A categorical ramp rather than one hue per slice: allocation charts are read
// by comparing widths, so the colours only need to separate adjacent bars.
// Institutional categorical color ramp for allocation distribution
const PALETTE = ["#2563eb", "#059669", "#d97706", "#7c3aed", "#0891b2", "#dc2626", "#4f46e5", "#0284c7"];

export default function AllocationBars({
  allocation,
}: {
  allocation: {
    asset_class: AllocationSlice[];
    sector: AllocationSlice[];
    cap: AllocationSlice[];
    fund_category: AllocationSlice[];
  };
}) {
  const groups = [
    { title: "Asset class", slices: allocation.asset_class },
    { title: "Sector", slices: allocation.sector },
    { title: "Market cap", slices: allocation.cap },
    { title: "Fund category", slices: allocation.fund_category },
  ].filter((group) => group.slices.length > 0);

  if (groups.length === 0) return null;

  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: 16 }}>
      {groups.map((group) => (
        <div className="glass-panel" key={group.title} style={{ padding: "18px 20px" }}>
          <h3 style={{ marginTop: 0, marginBottom: 16, fontSize: "1rem" }}>{group.title}</h3>
          {group.slices.map((slice, index) => (
            <div key={slice.label} style={{ marginBottom: 12 }}>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.85rem", marginBottom: 4 }}>
                <span style={{ color: "var(--text-secondary)" }}>{slice.label}</span>
                <span style={{ color: "var(--text-muted)" }}>
                  {formatCurrency(slice.value)}
                  {slice.weight_pct !== null && ` · ${slice.weight_pct.toFixed(1)}%`}
                </span>
              </div>
              <div style={{ height: 6, borderRadius: 3, background: "var(--bg-secondary)", overflow: "hidden" }}>
                <div
                  style={{
                    height: "100%",
                    width: `${slice.weight_pct ?? 0}%`,
                    background: PALETTE[index % PALETTE.length],
                    transition: "var(--transition-smooth)",
                  }}
                />
              </div>
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}
