import { Suspense } from "react";
import type { Metadata } from "next";
import FundSearch from "./FundSearch";

export const metadata: Metadata = {
  title: "Mutual Funds | stockportfolio.in",
  description:
    "Search Indian mutual funds and analyse NAV history, trailing returns, rolling returns and risk metrics.",
};

// FundSearch reads the query string via useSearchParams, which forces client-side
// rendering up to the nearest Suspense boundary. Keeping that boundary here lets
// the page shell prerender instead of the whole route going dynamic.
export default function FundsPage() {
  return (
    <Suspense
      fallback={
        <div className="app-container loading-container">
          <div className="spinner"></div>
        </div>
      }
    >
      <FundSearch />
    </Suspense>
  );
}
