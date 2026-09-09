import type { Metadata } from "next";
import OptionsConsole from "./OptionsConsole";

export const metadata: Metadata = {
  title: "Option Chain & Hedging | stockportfolio.in",
  description:
    "Live NSE option chain analytics — PCR, max pain, OI walls and build-up — plus an index put or collar sized to cap your portfolio drawdown.",
};

export default function OptionsPage() {
  return <OptionsConsole />;
}
