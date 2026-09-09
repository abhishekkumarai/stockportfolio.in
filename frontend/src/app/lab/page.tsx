import type { Metadata } from "next";
import StrategyLab from "./StrategyLab";

export const metadata: Metadata = {
  title: "Strategy Lab | stockportfolio.in",
  description:
    "Event-driven backtesting with next-bar-open fills, realistic costs, walk-forward optimisation and Monte Carlo permutation testing.",
};

export default function LabPage() {
  return <StrategyLab />;
}
