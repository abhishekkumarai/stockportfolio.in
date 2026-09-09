import type { Metadata } from "next";
import RecommendationsConsole from "./RecommendationsConsole";

export const metadata: Metadata = {
  title: "Buy & Sell Recommendations | stockportfolio.in",
  description:
    "Ranked buy candidates from the NSE universe and sell calls on your own holdings, each with the evidence behind the score and the tax on the exit.",
};

export default function RecommendationsPage() {
  return <RecommendationsConsole />;
}
