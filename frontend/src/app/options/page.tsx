import type { Metadata } from "next";
import OptionsConsole from "./OptionsConsole";

export const metadata: Metadata = {
  title: "Options Chain & OI | stockportfolio.in",
  description: "Live NSE option chain analytics — PCR, max pain, OI walls and build-up.",
};

export default function OptionsPage() {
  return <OptionsConsole />;
}
