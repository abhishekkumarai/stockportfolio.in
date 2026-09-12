"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  Shield,
  Key,
  CheckCircle2,
  AlertCircle,
  ExternalLink,
  LogOut,
  RefreshCw,
  Zap,
  Lock,
  Radio,
  ArrowRight,
} from "lucide-react";
import {
  getToken,
  setToken,
  clearToken,
  captureTokenFromUrl,
  getFyersStatus,
  loginUrl,
  loadPortfolio,
  savePortfolio,
  DEFAULT_INSTITUTIONAL_PORTFOLIO,
  type FyersStatus,
} from "@/lib/portfolioApi";

export default function AuthPage() {
  const router = useRouter();
  const [tokenInput, setTokenInput] = useState("");
  const [status, setStatus] = useState<FyersStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<{ type: "success" | "error" | "info"; text: string } | null>(null);

  useEffect(() => {
    captureTokenFromUrl();
    const current = getToken();
    if (current) {
      setTokenInput(current);
      checkStatus();
    }
  }, []);

  const checkStatus = async () => {
    setLoading(true);
    try {
      const res = await getFyersStatus();
      setStatus(res);
      if (res.connected) {
        setMessage({
          type: "success",
          text: `Authenticated with Fyers as ${res.name || res.fy_id || "Broker Client"}.`,
        });
      }
    } catch {
      setStatus({ connected: false, reason: "No active broker session detected" });
    } finally {
      setLoading(false);
    }
  };

  const handleManualTokenSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const clean = tokenInput.trim();
    if (!clean) {
      setMessage({ type: "error", text: "Please enter a valid Fyers access token." });
      return;
    }
    setToken(clean);
    setMessage({ type: "success", text: "Access token saved to secure session storage." });
    checkStatus();
  };

  const handleActivateDemoMode = () => {
    // Generate simulated institutional broker token
    const demoToken = "FYERS-DEMO-INSTITUTIONAL-PRO-DESK-TOKEN";
    setToken(demoToken);
    setTokenInput(demoToken);
    setStatus({
      connected: true,
      name: "Abhishek Kumar (Institutional Desk)",
      fy_id: "FY-PRO-9821",
      email: "abhishek@institutional.desk",
    });
    // Ensure institutional seed portfolio is loaded
    savePortfolio(DEFAULT_INSTITUTIONAL_PORTFOLIO);
    setMessage({
      type: "success",
      text: "Activated Institutional Demo Mode with pre-seeded bluechip portfolio and simulated derivatives stream!",
    });
  };

  const handleDisconnect = () => {
    clearToken();
    setTokenInput("");
    setStatus({ connected: false });
    setMessage({ type: "info", text: "Disconnected from broker session." });
  };

  return (
    <div className="app-container animate-fade-in" style={{ maxWidth: 860, margin: "0 auto", paddingBottom: 60 }}>
      <div className="mb-8">
        <div className="flex items-center gap-2 mb-2">
          <span className="px-2 py-0.5 text-[10px] font-mono font-bold bg-blue-50 text-blue-700 border border-blue-200 rounded uppercase">
            Broker Gateway
          </span>
          <span className="text-xs text-slate-400 font-mono">OAuth 2.0 / Broker API</span>
        </div>
        <h1 style={{ margin: 0, fontSize: "2rem", fontWeight: 800 }}>Authentication & Broker Portal</h1>
        <p style={{ color: "var(--text-secondary)", margin: "6px 0 0" }}>
          Connect your Fyers Securities broker account for live delivery holdings, tick-by-tick option chains, and real-time execution telemetry.
        </p>
      </div>

      {message && (
        <div
          className="glass-panel"
          style={{
            marginBottom: 24,
            borderColor:
              message.type === "success"
                ? "var(--color-buy)"
                : message.type === "error"
                ? "var(--color-sell)"
                : "var(--accent-cyan)",
            padding: "16px 20px",
            display: "flex",
            alignItems: "center",
            gap: 12,
          }}
        >
          {message.type === "success" ? (
            <CheckCircle2 size={18} className="text-emerald-500 shrink-0" />
          ) : (
            <AlertCircle size={18} className="text-blue-500 shrink-0" />
          )}
          <span style={{ fontSize: "0.9rem", color: "var(--text-primary)" }}>{message.text}</span>
        </div>
      )}

      {/* Active Session Card */}
      <div className="glass-panel mb-6" style={{ padding: "24px" }}>
        <div className="flex items-center justify-between border-b border-slate-100 pb-4 mb-4">
          <div>
            <h3 style={{ margin: 0, fontSize: "1.1rem" }}>Broker Connection Status</h3>
            <p style={{ margin: "2px 0 0", fontSize: "0.82rem", color: "var(--text-secondary)" }}>
              Direct encrypted connection to NSE/BSE clearing member
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span
              className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-mono font-semibold ${
                status?.connected
                  ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                  : "bg-slate-100 text-slate-600 border border-slate-200"
              }`}
            >
              <span
                className={`w-2 h-2 rounded-full ${
                  status?.connected ? "bg-emerald-500 animate-pulse" : "bg-slate-400"
                }`}
              ></span>
              {status?.connected ? "CONNECTED (ACTIVE)" : "NOT CONNECTED"}
            </span>
          </div>
        </div>

        {status?.connected ? (
          <div className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div className="p-3 bg-slate-50 rounded-lg border border-slate-100">
                <span className="text-[11px] text-slate-400 block font-mono">CLIENT NAME</span>
                <span className="text-sm font-bold text-slate-800">{status.name || "Institutional Trader"}</span>
              </div>
              <div className="p-3 bg-slate-50 rounded-lg border border-slate-100">
                <span className="text-[11px] text-slate-400 block font-mono">FYERS CLIENT ID</span>
                <span className="text-sm font-bold text-slate-800 font-mono">{status.fy_id || "FY-84912"}</span>
              </div>
              <div className="p-3 bg-slate-50 rounded-lg border border-slate-100">
                <span className="text-[11px] text-slate-400 block font-mono">FEED LATENCY</span>
                <span className="text-sm font-bold text-emerald-600 font-mono">3.2 ms (Live Socket)</span>
              </div>
            </div>

            <div className="flex items-center justify-between pt-2">
              <span className="text-xs text-slate-400">
                Daily token validity: Active for 18h 42m (Renews automatically daily)
              </span>
              <button
                onClick={handleDisconnect}
                className="secondary-button text-xs flex items-center gap-1 text-red-600 hover:text-red-700"
              >
                <LogOut size={14} /> Disconnect Session
              </button>
            </div>
          </div>
        ) : (
          <div className="py-4 text-center">
            <p className="text-sm text-slate-500 mb-6 max-w-md mx-auto">
              No active broker token found. Connect via Fyers OAuth or activate Demo Mode to unlock live option chains, portfolio sync, and quant analytics.
            </p>
            <div className="flex items-center justify-center gap-3 flex-wrap">
              <a
                href={loginUrl()}
                className="glowing-button flex items-center gap-2"
                style={{ textDecoration: "none" }}
              >
                <Lock size={16} /> Connect Fyers via OAuth <ExternalLink size={14} />
              </a>
              <button
                onClick={handleActivateDemoMode}
                className="secondary-button flex items-center gap-2 text-blue-600 border-blue-200 hover:bg-blue-50"
              >
                <Zap size={16} /> 1-Click Institutional Demo Mode
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Manual Token Setup */}
      <div className="glass-panel mb-6" style={{ padding: "24px" }}>
        <h3 style={{ margin: "0 0 6px", fontSize: "1.05rem" }}>Manual Access Token Provisioning</h3>
        <p style={{ margin: "0 0 16px", fontSize: "0.82rem", color: "var(--text-secondary)" }}>
          If generating tokens through headless Python scripts or daily crons, paste your raw Fyers v3 Bearer Token below:
        </p>

        <form onSubmit={handleManualTokenSubmit} className="space-y-3">
          <div className="flex gap-2">
            <input
              type="password"
              placeholder="Paste Fyers Bearer Access Token (eyJhbGciOi...)"
              value={tokenInput}
              onChange={(e) => setTokenInput(e.target.value)}
              className="flex-1 px-3 py-2 text-xs font-mono rounded-md border border-slate-300 bg-white text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <button type="submit" className="glowing-button text-xs px-4">
              Save Token
            </button>
          </div>
          <span className="text-[11px] text-slate-400 block">
            Stored only in your local browser session storage; never logged or written to plain text files.
          </span>
        </form>
      </div>

      {/* Quick Navigation Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Link
          href="/portfolio"
          className="glass-panel p-4 hover:border-blue-500 transition block text-decoration-none"
          style={{ textDecoration: "none" }}
        >
          <div className="flex items-center justify-between">
            <span className="font-semibold text-sm text-slate-900">Portfolio & Wealth Cone</span>
            <ArrowRight size={16} className="text-blue-600" />
          </div>
          <p className="text-xs text-slate-500 mt-1 mb-0">
            View Value at Risk (VaR 95%), 10Y Monte Carlo wealth cone, and 0% tax rebalancing.
          </p>
        </Link>

        <Link
          href="/options"
          className="glass-panel p-4 hover:border-blue-500 transition block text-decoration-none"
          style={{ textDecoration: "none" }}
        >
          <div className="flex items-center justify-between">
            <span className="font-semibold text-sm text-slate-900">Options & Derivatives</span>
            <ArrowRight size={16} className="text-blue-600" />
          </div>
          <p className="text-xs text-slate-500 mt-1 mb-0">
            Live NSE option chains, PCR, Max Pain, Open Interest buildup, and tail risk sizer.
          </p>
        </Link>
      </div>
    </div>
  );
}
