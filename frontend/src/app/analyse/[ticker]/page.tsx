"use client";

import { AlertTriangle } from "lucide-react";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { apiUrl } from "@/lib/api";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler,
  ScriptableContext
} from "chart.js";
import { Line } from "react-chartjs-2";

// Register Chart.js components
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

interface NewsItem {
  title: string;
  link: string;
  source: string;
  time: string;
}

interface AnalysisData {
  symbol: string;
  name: string;
  price: number;
  change: number;
  change_pct: number;
  details: {
    day_high: number;
    day_low: number;
    volume: number;
    fifty_two_week_high: number;
    fifty_two_week_low: number;
    currency: string;
  };
  technicals: {
    rsi: number;
    rsi_desc: string;
    sma20: number;
    sma50: number;
    sma200: number;
    ema20: number;
    ema50: number;
    trend: string;
  };
  sentiment: {
    compound: number;
    pos: number;
    neg: number;
    neu: number;
    count: number;
    desc: string;
  };
  recommendation: {
    score: number;
    decision: string;
    interpretation: string;
  };
  chart_data: Array<{
    date: string;
    close: number;
    high: number;
    low: number;
    volume: number;
  }>;
  news: NewsItem[];
}

export default function AnalysePage({ params }: { params: Promise<{ ticker: string }> }) {
  const { ticker } = use(params);
  const [data, setData] = useState<AnalysisData | null>(null);
  const [timeframe, setTimeframe] = useState("month");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchAnalysis() {
      setLoading(true);
      setError(null);
      try {
        const response = await fetch(apiUrl(`/api/stocks/analyse?ticker=${encodeURIComponent(ticker)}&timeframe=${timeframe}`));
        if (!response.ok) {
          throw new Error(`Failed to load data for ${ticker}. Status: ${response.status}`);
        }
        const result = await response.json();
        setData(result);
      } catch (err: any) {
        console.error(err);
        setError(err.message || "An error occurred while fetching analysis.");
      } finally {
        setLoading(false);
      }
    }

    fetchAnalysis();
  }, [ticker, timeframe]);

  if (loading) {
    return (
      <div className="app-container loading-container">
        <div className="spinner"></div>
        <h3 style={{ fontWeight: 500, color: "var(--text-secondary)" }}>
          Analyzing {ticker.toUpperCase()}...
        </h3>
        <p style={{ fontSize: "0.9rem" }}>Scraping real-time news and calculating technical indicators</p>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="app-container" style={{ textAlign: "center", padding: "80px 20px" }}>
        <AlertTriangle size={32} strokeWidth={1.5} style={{ marginBottom: "20px" }} />
        <h2 style={{ marginBottom: "10px" }}>Analysis Failed</h2>
        <p style={{ maxWidth: "500px", margin: "0 auto 30px auto" }}>{error}</p>
        <Link href="/" className="glowing-button">
          ← Return to Dashboard
        </Link>
      </div>
    );
  }

  // Export chart data as CSV
  const handleExportCSV = () => {
    if (!data || !data.chart_data.length) return;
    
    const headers = ["Date", "High", "Low", "Close", "Volume"];
    const rows = data.chart_data.map(d => [
      d.date,
      d.high,
      d.low,
      d.close,
      d.volume
    ]);
    
    const csvContent = [headers.join(","), ...rows.map(e => e.join(","))].join("\n");
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.setAttribute("href", url);
    link.setAttribute("download", `${data.symbol.replace(/\.(NS|BO)$/i, "")}_price_history_${timeframe}.csv`);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  // Chart configuration
  const chartLabels = data.chart_data.map(d => d.date);
  const chartClosePrices = data.chart_data.map(d => d.close);

  const chartConfigData = {
    labels: chartLabels,
    datasets: [
      {
        label: "Closing Price",
        data: chartClosePrices,
        borderColor: "#2563eb",
        borderWidth: 2,
        pointBackgroundColor: "transparent",
        pointBorderColor: "transparent",
        pointHoverBackgroundColor: "#2563eb",
        pointHoverBorderColor: "#ffffff",
        pointHoverRadius: 5,
        fill: true,
        backgroundColor: (context: ScriptableContext<"line">) => {
          const ctx = context.chart.ctx;
          const gradient = ctx.createLinearGradient(0, 0, 0, context.chart.height);
          gradient.addColorStop(0, "rgba(37, 99, 235, 0.14)");
          gradient.addColorStop(1, "rgba(37, 99, 235, 0.0)");
          return gradient;
        },
        tension: 0.1,
      }
    ]
  };

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: "#ffffff",
        titleColor: "#0f172a",
        bodyColor: "#475569",
        titleFont: { family: "Inter", size: 12, weight: 600 as const },
        bodyFont: { family: "JetBrains Mono", size: 12 },
        borderColor: "#e2e8f0",
        borderWidth: 1,
        padding: 10,
        displayColors: false,
        callbacks: {
          label: (context: any) => `₹${Number(context.parsed.y).toLocaleString("en-IN", { minimumFractionDigits: 2 })}`
        }
      }
    },
    scales: {
      x: {
        grid: { display: false },
        ticks: {
          color: "#64748b",
          font: { family: "Inter", size: 10 },
          maxTicksLimit: 8
        }
      },
      y: {
        grid: { color: "#f1f5f9" },
        ticks: {
          color: "#64748b",
          font: { family: "JetBrains Mono", size: 10 },
          callback: (value: any) => `₹${Number(value).toLocaleString()}`
        }
      }
    }
  };

  // Classify recommendation class
  const recDecision = data.recommendation.decision.toLowerCase();
  let decisionClass = "hold";
  if (recDecision.includes("buy")) decisionClass = "buy";
  if (recDecision.includes("sell")) decisionClass = "sell";

  // Helper function to color news sentiment
  const getSentimentClass = (headline: string) => {
    // Basic local preview helper
    return "neutral";
  };

  return (
    <div className="app-container animate-fade-in">
      {/* Top Nav & Equity Switcher */}
      <div className="flex items-center justify-between flex-wrap gap-3 mb-6 pb-3 border-b border-slate-200">
        <div className="flex items-center gap-3">
          <Link href="/analyse" className="text-xs font-semibold text-blue-600 hover:underline flex items-center gap-1">
            ← All Equities
          </Link>
          <span className="text-slate-300">|</span>
          <Link href="/" className="text-xs font-semibold text-slate-500 hover:text-slate-800">
            Master Console
          </Link>
        </div>

        {/* Quick Stock Switcher Pills */}
        <div className="flex items-center gap-1.5 overflow-x-auto py-1">
          <span className="text-[11px] text-slate-400 font-medium mr-1">Switch Stock:</span>
          {["RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "TATAMOTORS", "LT", "ITC", "BHARTIARTL", "SBIN"].map((s) => {
            const isCurrent = ticker.toUpperCase().replace(/\.(NS|BO)$/i, "") === s;
            return (
              <Link
                key={s}
                href={`/analyse/${s}`}
                className={`px-2 py-0.5 text-xs font-mono rounded transition ${
                  isCurrent
                    ? "bg-blue-600 text-white font-bold"
                    : "bg-slate-100 hover:bg-slate-200 text-slate-700"
                }`}
              >
                {s}
              </Link>
            );
          })}
        </div>
      </div>

      {/* Stock Quote Header */}
      <section style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "20px", marginBottom: "40px" }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: "6px" }}>
            <h1 style={{ fontSize: "2.5rem", fontWeight: 800 }}>{data.symbol.replace(/\.(NS|BO)$/i, "")}</h1>
            <span style={{
              background: "rgba(255, 255, 255, 0.05)",
              border: "1px solid var(--border-subtle)",
              padding: "4px 8px",
              borderRadius: "6px",
              fontSize: "0.8rem",
              fontWeight: 600,
              color: "var(--accent-cyan)"
            }}>
              NSE/BSE Listed
            </span>
          </div>
          <p style={{ fontSize: "1.1rem", fontWeight: 500, color: "#fff" }}>{data.name}</p>
        </div>

        <div style={{ textAlign: "right" }}>
          <div style={{ fontSize: "2.4rem", fontWeight: 800, fontFamily: "var(--font-headings)" }}>
            ₹{data.price.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
          </div>
          <div style={{
            fontSize: "1.1rem",
            fontWeight: 600,
            color: data.change >= 0 ? "var(--color-buy)" : "var(--color-sell)",
            marginTop: "4px"
          }}>
            {data.change >= 0 ? "▲" : "▼"} {Math.abs(data.change).toFixed(2)} ({data.change_pct >= 0 ? "+" : ""}{data.change_pct.toFixed(2)}%)
          </div>
        </div>
      </section>

      {/* Main Signal Display */}
      <div className="glass-panel" style={{ padding: "30px", display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "30px", marginBottom: "40px", border: `1px solid ${decisionClass === 'buy' ? 'rgba(16, 185, 129, 0.25)' : decisionClass === 'sell' ? 'rgba(239, 68, 68, 0.25)' : 'rgba(245, 158, 11, 0.25)'}` }}>
        <div style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
          <div className="title" style={{ fontSize: "0.85rem", color: "var(--text-secondary)", letterSpacing: "1px", textTransform: "uppercase" }}>stockportfolio.in Recommendation</div>
          <div>
            <span className={`badge-recommendation ${decisionClass}`}>
              {data.recommendation.decision}
            </span>
          </div>
          <div style={{ fontSize: "0.95rem", lineHeight: 1.6, color: "var(--text-primary)" }}>
            {data.recommendation.interpretation}
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", justifyContent: "center", alignItems: "center", borderLeft: "1px solid var(--border-subtle)", padding: "0 20px" }}>
          <div style={{ position: "relative", width: "130px", height: "130px", display: "flex", alignItems: "center", justifyItems: "center", justifyContent: "center" }}>
            {/* Simple Circular gauge score display */}
            <div style={{
              position: "absolute",
              inset: 0,
              borderRadius: "50%",
              border: "6px solid rgba(255,255,255,0.03)",
              borderTopColor: "var(--accent-cyan)",
              transform: `rotate(${data.recommendation.score * 3.6}deg)`
            }}></div>
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", zIndex: 5 }}>
              <span style={{ fontSize: "2rem", fontWeight: 800, color: "#fff" }}>{data.recommendation.score}</span>
              <span style={{ fontSize: "0.7rem", color: "var(--text-secondary)", textTransform: "uppercase" }}>Score</span>
            </div>
          </div>
        </div>
      </div>

      {/* Grid of Chart + Technicals */}
      <div style={{
        display: "grid",
        gridTemplateColumns: "2fr 1fr",
        gap: "30px",
        marginBottom: "40px"
      }}>
        {/* Interactive Chart */}
        <div className="glass-panel" style={{ padding: "30px", minHeight: "380px", display: "flex", flexDirection: "column" }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', flexWrap: 'wrap', gap: '10px' }}>
            <h3 style={{ fontSize: "1.2rem", fontWeight: 600 }}>Price Movement</h3>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
              <button
                onClick={handleExportCSV}
                style={{
                  padding: '6px 12px',
                  borderRadius: '6px',
                  fontSize: '0.8rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  border: '1px solid var(--border-subtle)',
                  background: 'rgba(0, 240, 255, 0.05)',
                  color: 'var(--accent-cyan)',
                  transition: 'var(--transition-smooth)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px'
                }}
                onMouseEnter={(e) => e.currentTarget.style.background = 'rgba(0, 240, 255, 0.15)'}
                onMouseLeave={(e) => e.currentTarget.style.background = 'rgba(0, 240, 255, 0.05)'}
              >
                Export CSV
              </button>
              <div style={{ display: 'flex', gap: '6px' }}>
                {['day', 'week', 'month', 'year'].map((tf) => (
                  <button
                    key={tf}
                    onClick={() => setTimeframe(tf)}
                    style={{
                      padding: '6px 12px',
                      borderRadius: '6px',
                      fontSize: '0.8rem',
                      fontWeight: 600,
                      cursor: 'pointer',
                      border: '1px solid var(--border-subtle)',
                      background: timeframe === tf ? 'var(--accent-cyan)' : 'transparent',
                      color: timeframe === tf ? '#000' : 'var(--text-secondary)',
                      transition: 'var(--transition-smooth)'
                    }}
                  >
                    {tf === 'day' ? '1D' : tf === 'week' ? '1W' : tf === 'month' ? '1M' : '1Y'}
                  </button>
                ))}
              </div>
            </div>
          </div>
          <div style={{ flex: 1, position: "relative", height: "100%", minHeight: "260px" }}>
            <Line data={chartConfigData} options={chartOptions} />
          </div>
        </div>

        {/* Technical Summary */}
        <div className="glass-panel" style={{ padding: "30px", display: "flex", flexDirection: "column", gap: "20px" }}>
          <h3 style={{ fontSize: "1.2rem", fontWeight: 600, borderBottom: "1px solid var(--border-subtle)", paddingBottom: "10px" }}>Technical Snapshot</h3>
          
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>RSI (14)</span>
            <span style={{ fontWeight: 700, color: data.technicals.rsi > 70 ? "var(--color-sell)" : data.technicals.rsi < 30 ? "var(--color-buy)" : "#fff" }}>
              {data.technicals.rsi} <span style={{ fontSize: "0.75rem", fontWeight: 500, color: "var(--text-secondary)", marginLeft: "4px" }}>({data.technicals.rsi_desc})</span>
            </span>
          </div>

          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>Trend Bias</span>
            <span style={{ fontWeight: 700, color: data.technicals.trend === "Bullish" ? "var(--color-buy)" : "var(--color-sell)" }}>
              {data.technicals.trend}
            </span>
          </div>

          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>SMA (50)</span>
            <span style={{ fontWeight: 600 }}>₹{data.technicals.sma50}</span>
          </div>

          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>SMA (200)</span>
            <span style={{ fontWeight: 600 }}>₹{data.technicals.sma200}</span>
          </div>

          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>EMA (20)</span>
            <span style={{ fontWeight: 600 }}>₹{data.technicals.ema20}</span>
          </div>

          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>EMA (50)</span>
            <span style={{ fontWeight: 600 }}>₹{data.technicals.ema50}</span>
          </div>
        </div>
      </div>

      {/* Quote Details + Sentiment Metrics */}
      <div style={{
        display: "grid",
        gridTemplateColumns: "1fr 1fr",
        gap: "30px",
        marginBottom: "40px"
      }}>
        {/* Stock Details */}
        <div className="glass-panel" style={{ padding: "30px" }}>
          <h3 style={{ fontSize: "1.2rem", fontWeight: 600, borderBottom: "1px solid var(--border-subtle)", paddingBottom: "12px", marginBottom: "18px" }}>Market Details</h3>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "20px 30px" }}>
            <div>
              <div style={{ color: "var(--text-secondary)", fontSize: "0.8rem", textTransform: "uppercase" }}>Day High</div>
              <div style={{ fontSize: "1.2rem", fontWeight: 600, color: "#fff", marginTop: "4px" }}>₹{data.details.day_high}</div>
            </div>
            <div>
              <div style={{ color: "var(--text-secondary)", fontSize: "0.8rem", textTransform: "uppercase" }}>Day Low</div>
              <div style={{ fontSize: "1.2rem", fontWeight: 600, color: "#fff", marginTop: "4px" }}>₹{data.details.day_low}</div>
            </div>
            <div>
              <div style={{ color: "var(--text-secondary)", fontSize: "0.8rem", textTransform: "uppercase" }}>52W High</div>
              <div style={{ fontSize: "1.2rem", fontWeight: 600, color: "#fff", marginTop: "4px" }}>₹{data.details.fifty_two_week_high}</div>
            </div>
            <div>
              <div style={{ color: "var(--text-secondary)", fontSize: "0.8rem", textTransform: "uppercase" }}>52W Low</div>
              <div style={{ fontSize: "1.2rem", fontWeight: 600, color: "#fff", marginTop: "4px" }}>₹{data.details.fifty_two_week_low}</div>
            </div>
            <div>
              <div style={{ color: "var(--text-secondary)", fontSize: "0.8rem", textTransform: "uppercase" }}>Volume</div>
              <div style={{ fontSize: "1.2rem", fontWeight: 600, color: "#fff", marginTop: "4px" }}>{data.details.volume.toLocaleString("en-IN")}</div>
            </div>
            <div>
              <div style={{ color: "var(--text-secondary)", fontSize: "0.8rem", textTransform: "uppercase" }}>Currency</div>
              <div style={{ fontSize: "1.2rem", fontWeight: 600, color: "#fff", marginTop: "4px" }}>{data.details.currency}</div>
            </div>
          </div>
        </div>

        {/* Sentiment Analysis details */}
        <div className="glass-panel" style={{ padding: "30px", display: "flex", flexDirection: "column", gap: "18px" }}>
          <h3 style={{ fontSize: "1.2rem", fontWeight: 600, borderBottom: "1px solid var(--border-subtle)", paddingBottom: "12px", marginBottom: "5px" }}>News Sentiment Details</h3>
          
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>Compound Sentiment</span>
            <span style={{
              fontWeight: 700,
              fontSize: "1.1rem",
              color: data.sentiment.compound > 0.15 ? "var(--color-buy)" : data.sentiment.compound < -0.15 ? "var(--color-sell)" : "var(--color-hold)"
            }}>
              {data.sentiment.compound > 0 ? "+" : ""}{data.sentiment.compound}
            </span>
          </div>

          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>Overall Sentiment</span>
            <span style={{ fontWeight: 600 }}>{data.sentiment.desc}</span>
          </div>

          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>Articles Analyzed</span>
            <span style={{ fontWeight: 600 }}>{data.sentiment.count}</span>
          </div>

          {/* Sentiment bars breakdown */}
          <div style={{ display: "flex", flexDirection: "column", gap: "6px", marginTop: "5px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.8rem", color: "var(--text-secondary)" }}>
              <span>Positive: {(data.sentiment.pos * 100).toFixed(0)}%</span>
              <span>Neutral: {(data.sentiment.neu * 100).toFixed(0)}%</span>
              <span>Negative: {(data.sentiment.neg * 100).toFixed(0)}%</span>
            </div>
            <div style={{ height: "8px", borderRadius: "4px", overflow: "hidden", display: "flex", background: "rgba(255,255,255,0.05)" }}>
              <div style={{ width: `${data.sentiment.pos * 100}%`, background: "var(--color-buy)" }}></div>
              <div style={{ width: `${data.sentiment.neu * 100}%`, background: "var(--text-muted)" }}></div>
              <div style={{ width: `${data.sentiment.neg * 100}%`, background: "var(--color-sell)" }}></div>
            </div>
          </div>
        </div>
      </div>

      {/* Scraped News Feed section */}
      <section>
        <h3 style={{ fontSize: "1.4rem", fontWeight: 700, marginBottom: "20px", display: "flex", alignItems: "center", gap: "8px" }}>
          Online News Feed & Sentiment
        </h3>
        
        {data.news.length === 0 ? (
          <div className="glass-panel" style={{ padding: "30px", textAlign: "center", color: "var(--text-secondary)" }}>
            No recent news articles found for this ticker.
          </div>
        ) : (
          <div className="news-feed">
            {data.news.map((item, idx) => {
              // Estimate sentiment of individual title locally (since API returns compound of whole,
              // we can estimate using VADER scores or simple keywords for visualization,
              // or default to positive if contains gain/up/rise/profit, negative if crash/loss/fall)
              const lowerTitle = item.title.toLowerCase();
              let sentType: "positive" | "negative" | "neutral" = "neutral";
              let color = "var(--text-muted)";
              
              if (lowerTitle.includes("rise") || lowerTitle.includes("gain") || lowerTitle.includes("profit") || lowerTitle.includes("buy") || lowerTitle.includes("bullish") || lowerTitle.includes("upside") || lowerTitle.includes("partner") || lowerTitle.includes("surges")) {
                sentType = "positive";
                color = "var(--color-buy)";
              } else if (lowerTitle.includes("fall") || lowerTitle.includes("crash") || lowerTitle.includes("drop") || lowerTitle.includes("sell") || lowerTitle.includes("bearish") || lowerTitle.includes("concern") || lowerTitle.includes("loss") || lowerTitle.includes("low")) {
                sentType = "negative";
                color = "var(--color-sell)";
              }
              
              return (
                <div key={idx} className="glass-panel news-card" style={{ "--sentiment-color": color } as React.CSSProperties}>
                  <div className="news-header">
                    <span className="news-source">{item.source}</span>
                    <span className="news-time">{item.time}</span>
                  </div>
                  <a href={item.link} target="_blank" rel="noopener noreferrer" className="news-title">
                    <h4>{item.title}</h4>
                  </a>
                  <span className={`news-sentiment-badge ${sentType}`}>
                    {sentType.toUpperCase()}
                  </span>
                </div>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}
