import type { Metadata } from "next";
import ScreenerConsole from "./ScreenerConsole";

export const metadata: Metadata = {
  title: "NSE Screener | stockportfolio.in",
  description:
    "Rank the NSE universe on the same technical and fundamental model your holdings are scored on, with every score's evidence attached.",
};

export default function ScreenerPage() {
  return <ScreenerConsole />;
}
