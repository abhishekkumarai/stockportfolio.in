"use client";

import { useEffect, useState } from "react";
import { getPortfolioNews, type NewsArticle } from "@/lib/portfolioApi";
import EmptyPortfolioNotice from "../EmptyPortfolioNotice";
import { usePortfolioContext } from "../PortfolioContext";
import SampleDataNotice from "../SampleDataNotice";

const SAMPLE_CATALYSTS_NEWS: NewsArticle[] = [
  {
    symbol: "RELIANCE",
    title: "Reliance Retail & Jio Platforms demerger structuring gets in-principle clearance for FY26 listing",
    url: "https://economictimes.indiatimes.com",
    source: "Economic Times",
    published_at: "2 hours ago",
    tag: "Corporate Action",
    impact: "BULLISH",
    impact_label: "+0.64α Bullish",
    sentiment_score: 0.82,
  },
  {
    symbol: "TCS",
    title: "TCS signs $1.2B multi-year cloud modernisation and sovereign AI transformation deal with European consortium",
    url: "https://www.bseindia.com",
    source: "BSE Corporate Announcement",
    published_at: "4 hours ago",
    tag: "Order Win",
    impact: "BULLISH",
    impact_label: "+0.45α Bullish",
    sentiment_score: 0.76,
  },
  {
    symbol: "HDFCBANK",
    title: "HDFC Bank reports 16.4% YoY net credit expansion with NIM stabilizing at 3.65% post-merger integration",
    url: "https://www.nseindia.com",
    source: "NSE Disclosures",
    published_at: "6 hours ago",
    tag: "Earnings Catalyst",
    impact: "BULLISH",
    impact_label: "+0.38α Bullish",
    sentiment_score: 0.69,
  },
  {
    symbol: "INFY",
    title: "Infosys expands generative AI enterprise suite 'Topaz' with 240+ global enterprise production deployments",
    url: "https://moneycontrol.com",
    source: "Moneycontrol",
    published_at: "9 hours ago",
    tag: "AI Tech",
    impact: "BULLISH",
    impact_label: "+0.29α Bullish",
    sentiment_score: 0.65,
  },
  {
    symbol: "ICICIBANK",
    title: "ICICI Bank domestic loan book advances 18.2% YoY; Net NPA drops to 0.42% in pristine asset quality cycle",
    url: "https://livemint.com",
    source: "Livemint",
    published_at: "12 hours ago",
    tag: "Credit Catalyst",
    impact: "BULLISH",
    impact_label: "+0.41α Bullish",
    sentiment_score: 0.74,
  },
];

export default function NewsView() {
  const { portfolio } = usePortfolioContext();
  const [newsArticles, setNewsArticles] = useState<NewsArticle[]>(SAMPLE_CATALYSTS_NEWS);
  const [newsIsSample, setNewsIsSample] = useState(true);
  const [newsLoading, setNewsLoading] = useState(false);

  const fetchNews = async () => {
    setNewsLoading(true);
    try {
      if (!portfolio.equity.length) {
        setNewsArticles(SAMPLE_CATALYSTS_NEWS);
        setNewsIsSample(true);
        return;
      }
      const res = await getPortfolioNews(portfolio.equity);
      const gotRealNews = Boolean(res?.articles?.length);
      setNewsArticles(gotRealNews ? res.articles : SAMPLE_CATALYSTS_NEWS);
      setNewsIsSample(!gotRealNews);
    } catch (err) {
      console.error("News fetch failed", err);
      setNewsArticles(SAMPLE_CATALYSTS_NEWS);
      setNewsIsSample(true);
    } finally {
      setNewsLoading(false);
    }
  };

  useEffect(() => {
    fetchNews();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div>
      <div style={{ marginBottom: 20 }}>
        <h1 style={{ margin: 0, fontSize: "1.6rem" }}>Catalysts &amp; News</h1>
        <p style={{ color: "var(--text-secondary)", margin: "6px 0 0" }}>
          News and corporate filings filtered strictly for the stocks you hold.
        </p>
      </div>

      <EmptyPortfolioNotice />

      {newsIsSample && <SampleDataNotice text="No real news could be fetched for your holdings — the headlines below are fabricated examples, not real articles." />}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <div>
          <h3 style={{ fontSize: "1.05rem", margin: 0 }}>Holdings News & Corporate Filings</h3>
          <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", margin: "4px 0 0" }}>
            Filtered strictly for the stocks you hold (Zero generic market noise).
          </p>
        </div>
        <button className="secondary-button" onClick={fetchNews} disabled={newsLoading}>
          {newsLoading ? "Refreshing..." : "Refresh News"}
        </button>
      </div>

      {newsArticles.length === 0 ? (
        <div style={{ textAlign: "center", padding: "24px 0", color: "var(--text-muted)" }}>
          {newsLoading ? "Fetching disclosures..." : "No adverse news or filings detected for your holdings."}
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {newsArticles.map((art, idx) => (
            <div key={idx} className="glass-panel" style={{ padding: "14px 18px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                  <span style={{ fontSize: "0.75rem", fontWeight: 700, padding: "2px 8px", borderRadius: 4, background: "#f1f5f9", color: "#0f172a", border: "1px solid var(--border-subtle)", fontFamily: "var(--font-mono)" }}>
                    {art.symbol}
                  </span>
                  <span style={{ fontSize: "0.75rem", color: "#2563eb", background: "#eff6ff", border: "1px solid #bfdbfe", padding: "1px 6px", borderRadius: 4, fontWeight: 500 }}>
                    {art.tag}
                  </span>
                </div>
                <span style={{ fontSize: "0.8rem", fontWeight: 600, color: "var(--text-secondary)" }}>{art.impact_label}</span>
              </div>
              <a
                href={art.url}
                target="_blank"
                rel="noopener noreferrer"
                style={{ color: "var(--text-primary)", fontWeight: 600, fontSize: "0.92rem", textDecoration: "none" }}
              >
                {art.title} ↗
              </a>
              <div style={{ color: "var(--text-muted)", fontSize: "0.75rem", marginTop: 4 }}>
                {art.source} · {art.published_at}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
