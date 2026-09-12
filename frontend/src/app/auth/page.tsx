"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import {
  Shield,
  Key,
  CheckCircle2,
  AlertCircle,
  LogOut,
  Zap,
  Lock,
  Mail,
  User as UserIcon,
  ArrowRight,
  FileSpreadsheet,
  Upload,
  Database,
  TrendingUp,
  Sparkles,
  LogIn,
  UserPlus,
  RefreshCw,
} from "lucide-react";
import {
  signin,
  signup,
  logout,
  getAuthToken,
  getAuthUser,
  isAuthenticated,
  type User,
} from "@/lib/auth";
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
  type FyersStatus,
  type OfflineStatementFile,
  type OfflineImportResult,
} from "@/lib/portfolioApi";

function AuthContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const redirectTarget = searchParams.get("redirect") || "/";

  // Auth Mode: "signin" | "signup"
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [authUser, setAuthUser] = useState<User | null>(null);
  const [authLoading, setAuthLoading] = useState(false);

  // Form Inputs
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");

  // Fyers broker token input & state
  const [tokenInput, setTokenInput] = useState("");
  const [status, setStatus] = useState<FyersStatus | null>(null);
  const [loadingBroker, setLoadingBroker] = useState(false);
  const [message, setMessage] = useState<{
    type: "success" | "error" | "info";
    text: string;
  } | null>(null);

  // Offline statement importer states
  const [offlineFiles, setOfflineFiles] = useState<OfflineStatementFile[]>([]);
  const [importingOffline, setImportingOffline] = useState(false);
  const [activeImport, setActiveImport] = useState<OfflineImportResult | null>(null);
  const [currentHoldingsCount, setCurrentHoldingsCount] = useState<{
    equity: number;
    funds: number;
  }>({
    equity: 0,
    funds: 0,
  });

  useEffect(() => {
    // Check existing auth state
    const user = getAuthUser();
    const authed = isAuthenticated();
    if (authed && user) {
      setAuthUser(user);
    }

    // Broker checks
    captureTokenFromUrl();
    const currentBrokerToken = getToken();
    if (currentBrokerToken) {
      setTokenInput(currentBrokerToken);
      checkBrokerStatus();
    }
    fetchOfflineFiles();
    updateHoldingsCount();
  }, []);

  const updateHoldingsCount = () => {
    const p = loadPortfolio();
    setCurrentHoldingsCount({
      equity: p.equity?.length || 0,
      funds: p.funds?.length || 0,
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

  const checkBrokerStatus = async () => {
    setLoadingBroker(true);
    try {
      const res = await getFyersStatus();
      setStatus(res);
    } catch {
      setStatus({ connected: false, reason: "No active broker session detected" });
    } finally {
      setLoadingBroker(false);
    }
  };

  // ----------------------------------------------------
  // Primary Account Auth Handlers (Sign In / Sign Up / Logout)
  // ----------------------------------------------------
  const handleSignIn = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim() || !password) {
      setMessage({ type: "error", text: "Please provide both email and password." });
      return;
    }
    setAuthLoading(true);
    setMessage(null);
    try {
      const resp = await signin(email.trim(), password);
      setAuthUser(resp.user);
      setMessage({
        type: "success",
        text: `Welcome back, ${resp.user.display_name || resp.user.email}! Redirecting...`,
      });
      setTimeout(() => {
        router.push(redirectTarget);
      }, 700);
    } catch (err: any) {
      setMessage({
        type: "error",
        text: err.message || "Failed to sign in. Please check your credentials.",
      });
    } finally {
      setAuthLoading(false);
    }
  };

  const handleSignUp = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim() || !password) {
      setMessage({ type: "error", text: "Please provide both email and password." });
      return;
    }
    if (password.length < 6) {
      setMessage({ type: "error", text: "Password must be at least 6 characters long." });
      return;
    }
    setAuthLoading(true);
    setMessage(null);
    try {
      const resp = await signup(email.trim(), password, displayName.trim() || undefined);
      setAuthUser(resp.user);
      setMessage({
        type: "success",
        text: `Account created successfully! Welcome to StockPortfolio.in, ${
          resp.user.display_name || resp.user.email
        }.`,
      });
      setTimeout(() => {
        router.push(redirectTarget);
      }, 800);
    } catch (err: any) {
      setMessage({
        type: "error",
        text: err.message || "Account registration failed. Please try again.",
      });
    } finally {
      setAuthLoading(false);
    }
  };

  const handleLogout = async () => {
    setAuthLoading(true);
    try {
      await logout();
      setAuthUser(null);
      setMessage({ type: "info", text: "You have been logged out of your account." });
    } catch (err: any) {
      setMessage({ type: "error", text: `Logout error: ${err.message || err}` });
    } finally {
      setAuthLoading(false);
    }
  };

  // Demo user quick login
  const handleQuickDemoAuth = async () => {
    setAuthLoading(true);
    setMessage(null);
    try {
      // First try signing in with demo account
      try {
        const resp = await signin("trader@stockportfolio.in", "demopassword123");
        setAuthUser(resp.user);
        setMessage({
          type: "success",
          text: "Demo session loaded successfully! Redirecting...",
        });
        setTimeout(() => router.push(redirectTarget), 600);
        return;
      } catch {
        // If not created yet, create it
        const resp = await signup(
          "trader@stockportfolio.in",
          "demopassword123",
          "Institutional Demo Desk"
        );
        setAuthUser(resp.user);
        setMessage({
          type: "success",
          text: "Created demo account & logged in! Redirecting...",
        });
        setTimeout(() => router.push(redirectTarget), 600);
      }
    } catch (err: any) {
      setMessage({ type: "error", text: `Demo auth failed: ${err.message || err}` });
    } finally {
      setAuthLoading(false);
    }
  };

  // ----------------------------------------------------
  // Broker & Offline Statement Handlers
  // ----------------------------------------------------
  const handleManualTokenSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const clean = tokenInput.trim();
    if (!clean) {
      setMessage({ type: "error", text: "Please enter a valid Fyers access token." });
      return;
    }
    setToken(clean);
    setMessage({ type: "success", text: "Broker access token saved." });
    checkBrokerStatus();
  };

  const handleImportOfflineFile = async (filename?: string) => {
    setImportingOffline(true);
    try {
      const result = await importOfflineStatement(filename);
      if (result && result.portfolio) {
        savePortfolio(result.portfolio);
        setActiveImport(result);
        updateHoldingsCount();
        const cid =
          result.statement?.metadata?.client_id || result.report?.client_id || "STATEMENT";
        if (typeof window !== "undefined") {
          localStorage.setItem("stockportfolio_client_id", cid);
          localStorage.setItem(
            "stockportfolio_user_name",
            result.statement?.metadata?.client_id ? `Client ${cid}` : "Statement Account"
          );
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
          text: `Successfully imported statement! Loaded ${result.report.equities_imported} equities and ${
            result.report.funds_imported
          } mutual funds (Total NAV: ${formatCurrency(
            result.valuation?.totals?.current_value ?? 0
          )}).`,
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
          localStorage.setItem(
            "stockportfolio_user_name",
            result.statement?.metadata?.client_id ? `Client ${cid}` : "Uploaded Statement"
          );
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

  const handleDisconnectBroker = () => {
    clearToken();
    setTokenInput("");
    setStatus({ connected: false });
    setActiveImport(null);
    setMessage({ type: "info", text: "Disconnected from broker session." });
  };

  return (
    <div
      className="app-container animate-fade-in"
      style={{ maxWidth: 880, margin: "0 auto", padding: "28px 20px 60px" }}
    >
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center gap-2 mb-2">
          <span className="px-2.5 py-0.5 text-[10px] font-mono font-bold bg-indigo-50 text-indigo-700 border border-indigo-200 rounded uppercase">
            Security & Identity Gate
          </span>
          <span className="text-xs text-slate-400 font-mono">
            Encrypted Session · PBKDF2 Hashing
          </span>
        </div>
        <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
          Authentication & Access Portal
        </h1>
        <p className="text-sm text-slate-500 mt-1">
          Sign in or create your institutional account to access quant engines, live portfolio radar,
          and factor backtesting.
        </p>
      </div>

      {/* Global Status Message */}
      {message && (
        <div
          className="glass-panel mb-6 p-4 rounded-xl border flex items-center gap-3 transition-all"
          style={{
            borderColor:
              message.type === "success"
                ? "var(--color-buy, #10b981)"
                : message.type === "error"
                ? "var(--color-sell, #ef4444)"
                : "#3b82f6",
            backgroundColor:
              message.type === "success"
                ? "rgba(16, 185, 129, 0.05)"
                : message.type === "error"
                ? "rgba(239, 68, 68, 0.05)"
                : "rgba(59, 130, 246, 0.05)",
          }}
        >
          {message.type === "success" ? (
            <CheckCircle2 size={18} className="text-emerald-500 shrink-0" />
          ) : message.type === "error" ? (
            <AlertCircle size={18} className="text-rose-500 shrink-0" />
          ) : (
            <AlertCircle size={18} className="text-blue-500 shrink-0" />
          )}
          <span className="text-sm font-medium text-slate-800">{message.text}</span>
        </div>
      )}

      {/* ==================================================== */}
      {/* 1. PRIMARY USER ACCOUNT CARD (SIGN IN / SIGN UP / LOGOUT) */}
      {/* ==================================================== */}
      {authUser ? (
        // Authenticated State View
        <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-xs mb-8">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-100 pb-5">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-full bg-slate-900 text-white font-bold text-base flex items-center justify-center border-2 border-slate-100 shadow-xs">
                {authUser.display_name
                  ? authUser.display_name.slice(0, 2).toUpperCase()
                  : authUser.email.slice(0, 2).toUpperCase()}
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-lg font-bold text-slate-900 leading-none">
                    {authUser.display_name || "Institutional User"}
                  </h2>
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-mono font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                    Authenticated
                  </span>
                </div>
                <p className="text-xs text-slate-500 font-mono mt-1">{authUser.email}</p>
              </div>
            </div>

            <button
              onClick={handleLogout}
              disabled={authLoading}
              className="inline-flex items-center justify-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold text-rose-600 bg-rose-50 hover:bg-rose-100 border border-rose-200 transition-colors cursor-pointer"
            >
              <LogOut size={14} />
              <span>{authLoading ? "Logging out..." : "Log Out Session"}</span>
            </button>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-5">
            <div className="p-3.5 bg-slate-50 rounded-lg border border-slate-100">
              <span className="text-[11px] text-slate-400 block font-mono">ACCOUNT ID</span>
              <span className="text-sm font-bold text-slate-800 font-mono">
                USR-{String(authUser.id).padStart(5, "0")}
              </span>
            </div>
            <div className="p-3.5 bg-slate-50 rounded-lg border border-slate-100">
              <span className="text-[11px] text-slate-400 block font-mono">SESSION ROLE</span>
              <span className="text-sm font-bold text-indigo-600 font-mono">
                Quant Desk Trader
              </span>
            </div>
            <div className="p-3.5 bg-slate-50 rounded-lg border border-slate-100">
              <span className="text-[11px] text-slate-400 block font-mono">HOLDINGS IN VAULT</span>
              <span className="text-sm font-bold text-slate-800 font-mono">
                {currentHoldingsCount.equity} Equities · {currentHoldingsCount.funds} Funds
              </span>
            </div>
          </div>

          <div className="mt-5 pt-4 border-t border-slate-100 flex flex-wrap items-center justify-between gap-3">
            <span className="text-xs text-slate-400 font-mono">
              All quantitative routes and screening features are unlocked for this session.
            </span>
            <Link
              href="/"
              className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-semibold shadow-xs transition-colors"
            >
              <span>Go to Quant Dashboard</span>
              <ArrowRight size={14} />
            </Link>
          </div>
        </div>
      ) : (
        // Unauthenticated Tabs: Sign In / Create Account
        <div className="bg-white border border-slate-200 rounded-xl shadow-xs overflow-hidden mb-8">
          {/* Tabs */}
          <div className="flex border-b border-slate-200 bg-slate-50/70 p-1">
            <button
              onClick={() => {
                setMode("signin");
                setMessage(null);
              }}
              className={`flex-1 py-3 px-4 text-xs font-semibold rounded-lg flex items-center justify-center gap-2 transition-all cursor-pointer ${
                mode === "signin"
                  ? "bg-white text-blue-600 shadow-xs border border-slate-200/60"
                  : "text-slate-500 hover:text-slate-900"
              }`}
            >
              <LogIn size={15} />
              <span>Sign In</span>
            </button>
            <button
              onClick={() => {
                setMode("signup");
                setMessage(null);
              }}
              className={`flex-1 py-3 px-4 text-xs font-semibold rounded-lg flex items-center justify-center gap-2 transition-all cursor-pointer ${
                mode === "signup"
                  ? "bg-white text-blue-600 shadow-xs border border-slate-200/60"
                  : "text-slate-500 hover:text-slate-900"
              }`}
            >
              <UserPlus size={15} />
              <span>Create Account</span>
            </button>
          </div>

          <div className="p-6">
            {mode === "signin" ? (
              <form onSubmit={handleSignIn} className="space-y-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                    Email Address
                  </label>
                  <div className="relative">
                    <Mail
                      size={16}
                      className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
                    />
                    <input
                      type="email"
                      required
                      placeholder="trader@stockportfolio.in"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      className="w-full pl-9 pr-3 py-2 bg-white border border-slate-200 rounded-lg text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 font-mono"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                    Password
                  </label>
                  <div className="relative">
                    <Lock
                      size={16}
                      className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
                    />
                    <input
                      type="password"
                      required
                      placeholder="••••••••••••"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      className="w-full pl-9 pr-3 py-2 bg-white border border-slate-200 rounded-lg text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 font-mono"
                    />
                  </div>
                </div>

                <div className="flex items-center justify-between pt-2">
                  <button
                    type="button"
                    onClick={handleQuickDemoAuth}
                    disabled={authLoading}
                    className="text-xs text-indigo-600 hover:text-indigo-800 font-medium hover:underline cursor-pointer flex items-center gap-1"
                  >
                    <Sparkles size={13} />
                    <span>Quick Demo Login</span>
                  </button>

                  <button
                    type="submit"
                    disabled={authLoading}
                    className="inline-flex items-center gap-2 px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-semibold shadow-xs transition-colors cursor-pointer"
                  >
                    {authLoading ? (
                      <RefreshCw size={14} className="animate-spin" />
                    ) : (
                      <LogIn size={14} />
                    )}
                    <span>{authLoading ? "Authenticating..." : "Sign In to Terminal"}</span>
                  </button>
                </div>
              </form>
            ) : (
              <form onSubmit={handleSignUp} className="space-y-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                    Full Name / Desk Title (Optional)
                  </label>
                  <div className="relative">
                    <UserIcon
                      size={16}
                      className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
                    />
                    <input
                      type="text"
                      placeholder="e.g. Abhishek Kumar"
                      value={displayName}
                      onChange={(e) => setDisplayName(e.target.value)}
                      className="w-full pl-9 pr-3 py-2 bg-white border border-slate-200 rounded-lg text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                    Email Address
                  </label>
                  <div className="relative">
                    <Mail
                      size={16}
                      className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
                    />
                    <input
                      type="email"
                      required
                      placeholder="trader@stockportfolio.in"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      className="w-full pl-9 pr-3 py-2 bg-white border border-slate-200 rounded-lg text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 font-mono"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                    Password (min 6 characters)
                  </label>
                  <div className="relative">
                    <Lock
                      size={16}
                      className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
                    />
                    <input
                      type="password"
                      required
                      minLength={6}
                      placeholder="••••••••••••"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      className="w-full pl-9 pr-3 py-2 bg-white border border-slate-200 rounded-lg text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 font-mono"
                    />
                  </div>
                </div>

                <div className="flex items-center justify-between pt-2">
                  <button
                    type="button"
                    onClick={handleQuickDemoAuth}
                    disabled={authLoading}
                    className="text-xs text-indigo-600 hover:text-indigo-800 font-medium hover:underline cursor-pointer flex items-center gap-1"
                  >
                    <Sparkles size={13} />
                    <span>Quick Demo Setup</span>
                  </button>

                  <button
                    type="submit"
                    disabled={authLoading}
                    className="inline-flex items-center gap-2 px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-semibold shadow-xs transition-colors cursor-pointer"
                  >
                    {authLoading ? (
                      <RefreshCw size={14} className="animate-spin" />
                    ) : (
                      <UserPlus size={14} />
                    )}
                    <span>{authLoading ? "Creating Account..." : "Create Free Account"}</span>
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}

      {/* ==================================================== */}
      {/* 2. BROKER CONNECTION & OFFLINE STATEMENTS */}
      {/* ==================================================== */}
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h2 className="text-base font-bold text-slate-800">
            Portfolio Data Feeds & Statement Ingestion
          </h2>
          <p className="text-xs text-slate-500">
            Link your live Fyers broker session or load verified CAMS/Zerodha statement records.
          </p>
        </div>
      </div>

      {/* Fyers Broker Status & Token */}
      <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-xs mb-6">
        <div className="flex items-center justify-between border-b border-slate-100 pb-4 mb-4">
          <div>
            <h3 className="text-sm font-bold text-slate-800">Broker Gateway Connection (Fyers)</h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Encrypted feed for live delivery holdings & option chain data.
            </p>
          </div>
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
            />
            {status?.connected ? "CONNECTED (ACTIVE)" : "NOT CONNECTED"}
          </span>
        </div>

        {status?.connected ? (
          <div className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div className="p-3 bg-slate-50 rounded-lg border border-slate-100">
                <span className="text-[10px] text-slate-400 block font-mono">ACCOUNT HOLDER</span>
                <span className="text-xs font-bold text-slate-800 truncate block">
                  {status.name || "Broker Account"}
                </span>
              </div>
              <div className="p-3 bg-slate-50 rounded-lg border border-slate-100">
                <span className="text-[10px] text-slate-400 block font-mono">FYERS CLIENT ID</span>
                <span className="text-xs font-bold text-slate-800 font-mono">
                  {status.fy_id || "FY-CONNECTED"}
                </span>
              </div>
              <div className="p-3 bg-slate-50 rounded-lg border border-slate-100">
                <span className="text-[10px] text-slate-400 block font-mono">FEED STATUS</span>
                <span className="text-xs font-bold text-emerald-600 font-mono">
                  Live Socket Ready
                </span>
              </div>
            </div>

            <div className="flex items-center justify-between pt-2">
              <span className="text-[11px] text-slate-400 font-mono">
                Access token saved in secure session memory.
              </span>
              <button
                onClick={handleDisconnectBroker}
                className="px-3 py-1.5 text-xs text-rose-600 hover:bg-rose-50 rounded-md font-medium transition cursor-pointer"
              >
                Disconnect Broker
              </button>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="flex flex-col sm:flex-row gap-3">
              <a
                href={loginUrl()}
                className="flex-1 inline-flex items-center justify-center gap-2 py-2.5 px-4 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-semibold transition cursor-pointer text-decoration-none"
              >
                <Zap size={14} />
                <span>Authorize with Fyers OAuth</span>
              </a>
            </div>

            <form onSubmit={handleManualTokenSubmit} className="pt-2">
              <label className="block text-xs font-medium text-slate-600 mb-1">
                Or Paste Access Token Manually:
              </label>
              <div className="flex gap-2">
                <input
                  type="password"
                  placeholder="eyJhbGciOi..."
                  value={tokenInput}
                  onChange={(e) => setTokenInput(e.target.value)}
                  className="flex-1 px-3 py-1.5 text-xs font-mono bg-slate-50 border border-slate-200 rounded-lg text-slate-800 focus:outline-none focus:border-blue-500"
                />
                <button
                  type="submit"
                  disabled={loadingBroker}
                  className="px-4 py-1.5 bg-slate-800 hover:bg-slate-900 text-white text-xs font-medium rounded-lg transition cursor-pointer"
                >
                  Save
                </button>
              </div>
            </form>
          </div>
        )}
      </div>

      {/* Offline Statements Section */}
      <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-xs">
        <div className="flex items-center justify-between border-b border-slate-100 pb-4 mb-4">
          <div>
            <h3 className="text-sm font-bold text-slate-800 flex items-center gap-2">
              <FileSpreadsheet size={16} className="text-emerald-600" />
              <span>Offline Statement Ingestion</span>
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Directly parse CAS PDF/Excel, Zerodha tradebooks, or server statement archives.
            </p>
          </div>
          <label className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-emerald-50 hover:bg-emerald-100 text-emerald-700 border border-emerald-200 rounded-lg text-xs font-semibold cursor-pointer transition">
            <Upload size={13} />
            <span>Upload File</span>
            <input
              type="file"
              accept=".xlsx,.xls,.csv,.pdf"
              onChange={handleFileUpload}
              disabled={importingOffline}
              className="hidden"
            />
          </label>
        </div>

        {offlineFiles.length > 0 && (
          <div className="space-y-2">
            <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider block font-mono">
              Available Offline Archive Files:
            </span>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
              {offlineFiles.map((file) => (
                <div
                  key={file.name}
                  className="p-3 bg-slate-50 border border-slate-100 rounded-lg flex items-center justify-between gap-3 hover:border-slate-300 transition"
                >
                  <div className="min-w-0 flex-1">
                    <span className="text-xs font-semibold text-slate-800 truncate block">
                      {file.name}
                    </span>
                    <span className="text-[10px] text-slate-400 font-mono">
                      {(file.size_bytes / 1024).toFixed(1)} KB
                    </span>
                  </div>
                  <button
                    onClick={() => handleImportOfflineFile(file.name)}
                    disabled={importingOffline}
                    className="px-2.5 py-1 text-xs font-semibold bg-blue-50 text-blue-600 hover:bg-blue-100 rounded-md border border-blue-200 transition cursor-pointer"
                  >
                    {importingOffline ? "Parsing..." : "Import"}
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default function AuthPage() {
  return (
    <Suspense
      fallback={
        <div className="flex h-screen items-center justify-center bg-slate-50 text-slate-600 font-mono text-xs">
          Loading Security Gate...
        </div>
      }
    >
      <AuthContent />
    </Suspense>
  );
}
