import type { Metadata } from "next";
import PaperConsole from "./PaperConsole";

export const metadata: Metadata = {
  title: "Paper Trading | stockportfolio.in",
  description:
    "A persisted paper-trading ledger with a full signal audit trail, benchmarked against the backtest that justified the strategy. Simulated only — no broker order API.",
};

export default function PaperPage() {
  return <PaperConsole />;
}
