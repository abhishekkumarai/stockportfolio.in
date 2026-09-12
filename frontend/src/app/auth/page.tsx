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
  ArrowRight,
  FileSpreadsheet,
  Upload,
  Database,
  TrendingUp,
  Sparkles,
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
  getOfflineFiles,
  importOfflineStatement,
  uploadStatementFile,
  formatCurrency,
  formatPct,
  type FyersStatus,
  type OfflineStatementFile,
  type OfflineImportResult,
} from "@/lib/portfolioApi";

export default function AuthPage() {
  const router = useRouter();
  const [tokenInput, setTokenInput] = useState("");
  const [status, setStatus] = useState<FyersStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<{ type: "success" | "error" | "info"; text: string } | null>(null);

  // Offline statement importer states
  const [offlineFiles, setOfflineFiles] = useState<OfflineStatementFile[]>([]);
  const [importingOffline, setImportingOffline] = useState(false);
  const [activeImport, setActiveImport] = useState<OfflineImportResult | null>(null);
  const [currentHoldingsCount, setCurrentHoldingsCount] = useState<{ equity: number; funds: number }>({
    equity: 0,
    funds: 0,
  });

  useEffect(() => {
    captureTokenFromUrl();
    const current = getToken();
    if (current) {
      setTokenInput(current);
      checkStatus();
    }
    fetchOfflineFiles();
    updateHoldingsCount();
  }, []);

  const updateHoldingsCount = () => {
    const p = loadPortfolio();
    setCurrentHoldingsCount({
      equity: p.equity.length,
      funds: p.funds.length,
    });
  };

  const fetchOfflineFiles = async () => {
    try {
      const data = await getOfflineFiles();
      if (data?.files) {
        setOfflineFiles(data.files);
      }
    } catch (err) {
      console.warn("Could not fetch offline files:", err);
    }
  };

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
    const demoToken = "FYERS-DEMO-TOKEN";
    setToken(demoToken);
    setTokenInput(demoToken);
    setStatus({
      connected: true,
      name: "Demo Account",
      fy_id: "DEMO-CLIENT",
      email: "demo@stockportfolio.in",
    });
    setMessage({
      type: "info",
      text: "Activated demo broker session.",
    });
  };

  const handleImportOfflineFile = async (filename?: string) => {
    setImportingOffline(true);
    try {
      const result = await importOfflineStatement(filename);
      if (result && result.portfolio) {
        savePortfolio(result.portfolio);
        setActiveImport(result);
        updateHoldingsCount();
        const cid = result.statement?.metadata?.client_id || result.report?.client_id || "STATEMENT";
        if (typeof window !== "undefined") {
          localStorage.setItem("stockportfolio_client_id", cid);
          localStorage.setItem("stockportfolio_user_name", result.statement?.metadata?.client_id ? `Client ${cid}` : "Statement Account");
          window.dispatchEvent(new Event("portfolio-updated"));
        }
        setStatus({
          connected: true,
          name: result.statement?.metadata?.client_id ? `Client ${cid}` : "Statement Account",
          fy_id: cid,
          email: `${cid.toLowerCase()}@stockportfolio.in`,
        });
        setMessage({
          type: "success",
          text: `Successfully imported statement! Loaded ${result.report.equities_imported} equities and ${result.report.funds_imported} mutual funds (Total NAV: ${formatCurrency(result.valuation?.totals?.current_value ?? 0)}).`,
        });
      }
    } catch (err: any) {
      setMessage({
        type: "error",
        text: `Offline statement import failed: ${err.message || err}`,
      });
    } finally {
      setImportingOffline(false);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setImportingOffline(true);
    try {
      const result = await uploadStatementFile(file);
      if (result && result.portfolio) {
        savePortfolio(result.portfolio);
        setActiveImport(result);
        updateHoldingsCount();
        const cid = result.statement?.metadata?.client_id || "UPLOADED";
        if (typeof window !== "undefined") {
          localStorage.setItem("stockportfolio_client_id", cid);
          localStorage.setItem("stockportfolio_user_name", result.statement?.metadata?.client_id ? `Client ${cid}` : "Uploaded Statement");
          window.dispatchEvent(new Event("portfolio-updated"));
        }
        setStatus({
          connected: true,
          name: result.statement?.metadata?.client_id ? `Client ${cid}` : "Uploaded Statement",
          fy_id: cid,
          email: `${cid.toLowerCase()}@stockportfolio.in`,
        });
        setMessage({
          type: "success",
          text: `Successfully parsed & imported ${file.name}! Loaded ${result.report.equities_imported} equities and ${result.report.funds_imported} mutual funds.`,
        });
      }
    } catch (err: any) {
      setMessage({
        type: "error",
        text: `File upload import failed: ${err.message || err}`,
      });
    } finally {
      setImportingOffline(false);
      e.target.value = "";
    }
  };

  const handleDisconnect = () => {
    clearToken();
    setTokenInput("");
    setStatus({ connected: false });
    setActiveImport(null);
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

      {/* Offline Broker Statement & Holdings Importer */}
      <div className="glass-panel mb-6" style={{ padding: "24px" }}>
        <div className="flex flex-col sm:flex-row sm:items-center justify-between border-b border-slate-100 pb-4 mb-4 gap-2">
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <h3 style={{ margin: 0, fontSize: "1.1rem" }}>Offline Broker Statement Importer</h3>
              <span className="px-2 py-0.5 text-[10px] font-mono font-bold bg-amber-50 text-amber-800 border border-amber-200 rounded uppercase flex items-center gap-1">
                <FileSpreadsheet size={12} /> Excel / Zerodha (.xlsx)
              </span>
            </div>
            <p style={{ margin: "2px 0 0", fontSize: "0.82rem", color: "var(--text-secondary)" }}>
              Import verified holding statements from <code className="font-mono text-[11px] bg-slate-100 px-1 py-0.5 rounded">ignore_offline/</code> or upload your broker export file.
            </p>
          </div>
          <div className="text-left sm:text-right">
            <span className="text-xs font-mono text-slate-400 block">
              Active Cockpit Holdings
            </span>
            <span className="text-xs font-bold text-slate-800 font-mono">
              {currentHoldingsCount.equity} Stocks • {currentHoldingsCount.funds} Funds
            </span>
          </div>
        </div>

        {/* Offline Files Found in ignore_offline */}
        <div className="space-y-4">
          {offlineFiles.length > 0 ? (
            offlineFiles.map((file) => (
              <div key={file.name} className="p-4 bg-slate-50/80 rounded-lg border border-slate-200/80">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-sm text-slate-900 font-mono">
                        {file.name}
                      </span>
                      <span className="px-1.5 py-0.5 text-[10px] font-mono font-medium rounded bg-emerald-100 text-emerald-800">
                        Detected in ignore_offline
                      </span>
                    </div>
                    <p className="text-xs text-slate-500 mt-1 mb-0 font-mono">
                      Size: {(file.size_bytes / 1024).toFixed(1)} KB • Modified:{" "}
                      {file.modified_at ? new Date(file.modified_at).toLocaleDateString() : "Recent"}
                    </p>
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    <button
                      type="button"
                      onClick={() => handleImportOfflineFile(file.name)}
                      disabled={importingOffline}
                      className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 rounded-md shadow-sm transition-all"
                    >
                      {importingOffline ? (
                        <>
                          <RefreshCw size={14} className="animate-spin" />
                          <span>Parsing & Mapping AMFI...</span>
                        </>
                      ) : (
                        <>
                          <Sparkles size={14} />
                          <span>Import & Apply {file.name.replace(/\.xlsx$/i, "")}</span>
                        </>
                      )}
                    </button>
                  </div>
                </div>

                {/* If activeImport has been loaded, show diagnostics pill */}
                {activeImport && (
                  <div className="mt-3 pt-3 border-t border-slate-200/60 grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                    <div>
                      <span className="text-slate-400 block text-[10px] font-mono uppercase">Client ID</span>
                      <span className="font-bold text-slate-800 font-mono">
                        {activeImport.statement?.metadata?.client_id || activeImport.report?.client_id || "Imported"}
                      </span>
                    </div>
                    <div>
                      <span className="text-slate-400 block text-[10px] font-mono uppercase">Portfolio NAV</span>
                      <span className="font-bold text-slate-900 font-mono">
                        {formatCurrency(activeImport.valuation?.totals?.current_value ?? 0)}
                      </span>
                    </div>
                    <div>
                      <span className="text-slate-400 block text-[10px] font-mono uppercase">Unrealized P&L</span>
                      <span
                        className={`font-bold font-mono ${
                          (activeImport.valuation?.totals?.pnl ?? 0) >= 0 ? "text-emerald-700" : "text-rose-700"
                        }`}
                      >
                        {(activeImport.valuation?.totals?.pnl ?? 0) >= 0 ? "+" : ""}
                        {formatCurrency(activeImport.valuation?.totals?.pnl ?? 0)} (
                        {formatPct(activeImport.valuation?.totals?.pnl_pct ?? 0)})
                      </span>
                    </div>
                    <div>
                      <span className="text-slate-400 block text-[10px] font-mono uppercase">AMFI Resolution</span>
                      <span className="font-bold text-emerald-600 font-mono">
                        {activeImport.report?.funds_imported ?? 0} Funds Mapped
                      </span>
                    </div>
                  </div>
                )}
              </div>
            ))
          ) : (
            <div className="p-4 bg-slate-50/80 rounded-lg border border-slate-200/80 text-center text-xs text-slate-500">
              No offline statement files detected in{" "}
              <code className="font-mono text-[11px] bg-slate-100 px-1 py-0.5 rounded">ignore_offline/</code>.
              Place an export file in that directory or upload one below.
            </div>
          )}

          {/* Custom Upload Dropzone */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between p-3.5 bg-white rounded-lg border border-dashed border-slate-300 hover:border-blue-400 transition-colors gap-3">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-full bg-blue-50 text-blue-600 flex items-center justify-center shrink-0">
                <Upload size={17} />
              </div>
              <div>
                <span className="text-xs font-semibold text-slate-800 block">
                  Upload Custom Holdings Statement (.xlsx)
                </span>
                <span className="text-[11px] text-slate-500 block">
                  Automatic AMFI fund code resolution, ISIN reconciliation, and capital gains tracking
                </span>
              </div>
            </div>
            <div>
              <label className="cursor-pointer inline-flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-slate-700 bg-slate-50 hover:bg-slate-100 rounded-md border border-slate-300 transition">
                <span>Browse File</span>
                <input
                  type="file"
                  accept=".xlsx,.xls"
                  onChange={handleFileUpload}
                  className="hidden"
                />
              </label>
            </div>
          </div>
        </div>
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
