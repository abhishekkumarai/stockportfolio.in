import type { Metadata } from "next";
import QuantConsole from "./QuantConsole";

export const metadata: Metadata = {
  title: "Quant Lab | stockportfolio.in",
  description:
    "Hierarchical risk parity and mean-variance target weights, factor exposure regression, market regime detection, and a tax-aware rebalancing sheet.",
};

export default function QuantPage() {
  return <QuantConsole />;
}
