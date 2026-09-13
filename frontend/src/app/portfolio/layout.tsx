"use client";

import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import {
  EMPTY_PORTFOLIO,
  StoredPortfolio,
  analysePortfolio,
  captureTokenFromUrl,
  getFyersHoldings,
  getFyersStatus,
  getToken,
  loadPortfolio,
  savePortfolio,
  uploadStatementFile,
  valuePortfolio,
  type DangerAnalysis,
  type FyersStatus,
  type GrowthAnalysis,
  type PortfolioValuation,
} from "@/lib/portfolioApi";
import {
  FALLBACK_DANGER,
  FALLBACK_GROWTH,
  PortfolioContext,
  type PortfolioContextValue,
} from "./PortfolioContext";

const LEGACY_TAB_ROUTES: Record<string, string> = {
  overview: "/portfolio",
  stress: "/portfolio/stress",
  rebalance: "/portfolio/rebalance",
  news: "/portfolio/news",
  catalysts: "/portfolio/news",
  memo: "/portfolio/memo",
};

function LegacyTabRedirect() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (pathname !== "/portfolio") return;
    const rawTab = searchParams.get("tab");
    if (!rawTab) return;
    const target = LEGACY_TAB_ROUTES[rawTab];
    if (target && target !== "/portfolio") {
      router.replace(target);
    }
  }, [searchParams, pathname, router]);

  return null;
}

export default function PortfolioLayout({ children }: { children: React.ReactNode }) {
  const [portfolio, setPortfolio] = useState<StoredPortfolio>(EMPTY_PORTFOLIO);
  const [hydrated, setHydrated] = useState(false);
  const [valuation, setValuation] = useState<PortfolioValuation | null>(null);
  const [danger, setDanger] = useState<DangerAnalysis | null>(null);
  const [growth, setGrowth] = useState<GrowthAnalysis | null>(null);
  const [analysisIsSample, setAnalysisIsSample] = useState(false);
  const [status, setStatus] = useState<FyersStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [importing, setImporting] = useState(false);
  const [uploadingStatement, setUploadingStatement] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const statementFileInputRef = useRef<HTMLInputElement>(null);

  // localStorage is only readable on the client, so the first render must not
  // depend on it or the server and client markup disagree.
  useEffect(() => {
    captureTokenFromUrl();
    setPortfolio(loadPortfolio());
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (hydrated) savePortfolio(portfolio);
  }, [portfolio, hydrated]);

  useEffect(() => {
    if (!hydrated || !getToken()) return;
    const controller = new AbortController();
    getFyersStatus(controller.signal)
      .then(setStatus)
      .catch(() => setStatus(null));
    return () => controller.abort();
  }, [hydrated]);

  const isEmpty = portfolio.equity.length === 0 && portfolio.funds.length === 0;

  const refresh = useCallback(
    async (signal?: AbortSignal) => {
      if (isEmpty) {
        setValuation(null);
        setDanger(null);
        setGrowth(null);
        setAnalysisIsSample(false);
        return;
      }
      setLoading(true);
      setError(null);
      try {
        const fullAnalysis = await analysePortfolio(
          portfolio.equity,
          portfolio.funds,
          portfolio.cash,
          signal
        );
        setValuation(fullAnalysis.valuation);
        setDanger(fullAnalysis.danger);
        setGrowth(fullAnalysis.growth);
        setAnalysisIsSample(false);
      } catch (err) {
        if ((err as Error).name !== "AbortError") {
          // Fallback to basic valuation if full analysis fails
          try {
            const val = await valuePortfolio(portfolio.equity, portfolio.funds, portfolio.cash, signal);
            setValuation(val);
            setDanger(FALLBACK_DANGER);
            setGrowth(FALLBACK_GROWTH);
            setAnalysisIsSample(true);
          } catch (fallbackErr) {
            setDanger(FALLBACK_DANGER);
            setGrowth(FALLBACK_GROWTH);
            setAnalysisIsSample(true);
            setError((fallbackErr as Error).message);
          }
        }
      } finally {
        setLoading(false);
      }
    },
    [portfolio, isEmpty]
  );

  useEffect(() => {
    if (!hydrated) return;
    const controller = new AbortController();
    refresh(controller.signal);
    return () => controller.abort();
  }, [hydrated, refresh]);

  const importHoldings = async () => {
    setImporting(true);
    setError(null);
    setNotice(null);
    try {
      const response = await getFyersHoldings();
      if (response.count === 0) {
        setNotice("Fyers returned no delivery holdings for this account.");
        return;
      }
      // Replace rather than append: re-importing must not double every
      // position. Manually added funds are untouched.
      setPortfolio((current) => ({
        ...current,
        equity: response.holdings.map((holding) => ({
          symbol: holding.symbol,
          quantity: holding.quantity,
          avg_cost: holding.avg_cost,
          buy_date: null,
        })),
      }));
      setNotice(
        `Imported ${response.count} holding${response.count === 1 ? "" : "s"}. ` +
          "Fyers does not supply purchase dates — add them below to unlock holding-period returns."
      );
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setImporting(false);
    }
  };

  const handleStatementFile = async (file: File) => {
    setUploadingStatement(true);
    setError(null);
    setNotice(null);
    try {
      const result = await uploadStatementFile(file);
      setPortfolio(result.portfolio);
      const { equities_imported, funds_imported, unresolved_funds } = result.report;
      let message = `Imported ${equities_imported} equity holding${equities_imported === 1 ? "" : "s"} and ${funds_imported} fund holding${funds_imported === 1 ? "" : "s"} from the statement.`;
      if (unresolved_funds.length > 0) {
        message += ` ${unresolved_funds.length} fund row${unresolved_funds.length === 1 ? "" : "s"} could not be matched to a known scheme.`;
      }
      setNotice(message);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setUploadingStatement(false);
    }
  };

  const removeRow = (kind: "equity" | "fund", key: string) => {
    setPortfolio((current) =>
      kind === "equity"
        ? { ...current, equity: current.equity.filter((h) => h.symbol !== key) }
        : { ...current, funds: current.funds.filter((f) => String(f.scheme_code) !== key) }
    );
  };

  const staleCount = useMemo(
    () => valuation?.holdings.filter((h) => h.price_source === "yfinance").length ?? 0,
    [valuation]
  );

  const contextValue: PortfolioContextValue = {
    portfolio,
    hydrated,
    valuation,
    danger,
    growth,
    analysisIsSample,
    status,
    loading,
    importing,
    uploadingStatement,
    error,
    notice,
    isEmpty,
    staleCount,
    refresh,
    importHoldings,
    handleStatementFile,
    removeRow,
    setPortfolio,
    setStatus,
    setNotice,
    setError,
    statementFileInputRef,
  };

  if (!hydrated) {
    return (
      <div className="app-container">
        <div className="loading-container">
          <div className="spinner" />
        </div>
      </div>
    );
  }

  return (
    <PortfolioContext.Provider value={contextValue}>
      <Suspense fallback={null}>
        <LegacyTabRedirect />
      </Suspense>
      <div className="app-container animate-fade-in">{children}</div>
    </PortfolioContext.Provider>
  );
}
