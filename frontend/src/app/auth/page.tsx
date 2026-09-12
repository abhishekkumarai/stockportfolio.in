"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import {
  Shield,
  CheckCircle2,
  AlertCircle,
  LogOut,
  Lock,
  Mail,
  User as UserIcon,
  ArrowRight,
  Sparkles,
  LogIn,
  UserPlus,
  RefreshCw,
  Activity,
} from "lucide-react";
import {
  signin,
  signup,
  logout,
  getAuthUser,
  isAuthenticated,
  type User,
} from "@/lib/auth";

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

  const [message, setMessage] = useState<{
    type: "success" | "error" | "info";
    text: string;
  } | null>(null);

  useEffect(() => {
    const user = getAuthUser();
    const authed = isAuthenticated();
    if (authed && user) {
      setAuthUser(user);
    }
  }, []);

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
      }, 600);
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
      }, 700);
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
      setMessage({ type: "info", text: "You have been logged out of your session." });
    } catch (err: any) {
      setMessage({ type: "error", text: `Logout error: ${err.message || err}` });
    } finally {
      setAuthLoading(false);
    }
  };

  const handleQuickDemoAuth = async () => {
    setAuthLoading(true);
    setMessage(null);
    try {
      try {
        const resp = await signin("trader@stockportfolio.in", "demopassword123");
        setAuthUser(resp.user);
        setMessage({
          type: "success",
          text: "Demo session loaded successfully! Redirecting...",
        });
        setTimeout(() => router.push(redirectTarget), 500);
        return;
      } catch {
        const resp = await signup(
          "trader@stockportfolio.in",
          "demopassword123",
          "Institutional Demo Desk"
        );
        setAuthUser(resp.user);
        setMessage({
          type: "success",
          text: "Demo account activated! Redirecting...",
        });
        setTimeout(() => router.push(redirectTarget), 500);
      }
    } catch (err: any) {
      setMessage({ type: "error", text: `Demo auth failed: ${err.message || err}` });
    } finally {
      setAuthLoading(false);
    }
  };

  return (
    <div className="min-h-screen w-full bg-slate-950 text-slate-100 flex flex-col justify-between relative overflow-x-hidden selection:bg-blue-600 selection:text-white">
      {/* Background Ambient Glows & Grid */}
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_80%_80%_at_50%_-20%,rgba(59,130,246,0.15),rgba(255,255,255,0))] pointer-events-none" />
      <div className="absolute top-1/3 left-1/4 w-96 h-96 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute bottom-1/3 right-1/4 w-96 h-96 bg-emerald-500/10 rounded-full blur-3xl pointer-events-none" />

      {/* Top Brand Bar */}
      <header className="w-full max-w-6xl mx-auto px-6 py-6 flex items-center justify-between z-10">
        <Link href="/" className="flex items-center gap-3 group text-decoration-none">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-600 flex items-center justify-center font-black text-sm text-white shadow-lg shadow-blue-500/20 border border-blue-400/30">
            SP
          </div>
          <div className="flex flex-col">
            <div className="flex items-center gap-1">
              <span className="font-extrabold text-base tracking-tight text-white group-hover:text-blue-400 transition-colors">
                StockPortfolio
              </span>
              <span className="text-blue-500 font-bold text-base">.in</span>
            </div>
            <span className="text-[10px] text-slate-400 font-mono tracking-wider uppercase">
              Enterprise Cockpit
            </span>
          </div>
        </Link>

        <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-slate-900/80 border border-slate-800 text-[11px] font-mono text-slate-400">
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
          <span>NSE Gateway Operational</span>
        </div>
      </header>

      {/* Main Centered Authentication Container */}
      <main className="w-full max-w-md mx-auto px-4 py-8 z-10 flex-1 flex flex-col justify-center">
        {/* Global Alert Message */}
        {message && (
          <div
            className={`mb-6 p-4 rounded-xl border flex items-center gap-3 backdrop-blur-md transition-all animate-fade-in ${
              message.type === "success"
                ? "bg-emerald-950/40 border-emerald-500/40 text-emerald-300"
                : message.type === "error"
                ? "bg-rose-950/40 border-rose-500/40 text-rose-300"
                : "bg-blue-950/40 border-blue-500/40 text-blue-300"
            }`}
          >
            {message.type === "success" ? (
              <CheckCircle2 size={18} className="text-emerald-400 shrink-0" />
            ) : message.type === "error" ? (
              <AlertCircle size={18} className="text-rose-400 shrink-0" />
            ) : (
              <Activity size={18} className="text-blue-400 shrink-0" />
            )}
            <span className="text-xs font-medium leading-relaxed">{message.text}</span>
          </div>
        )}

        {authUser ? (
          // ==========================================
          // Authenticated State View (Clean Profile & Logout)
          // ==========================================
          <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-7 shadow-2xl backdrop-blur-xl">
            <div className="flex items-center justify-between border-b border-slate-800 pb-5 mb-5">
              <div className="flex items-center gap-3.5">
                <div className="w-12 h-12 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-600 text-white font-bold text-base flex items-center justify-center border border-blue-400/30 shadow-md">
                  {authUser.display_name
                    ? authUser.display_name.slice(0, 2).toUpperCase()
                    : authUser.email.slice(0, 2).toUpperCase()}
                </div>
                <div className="min-w-0">
                  <h2
                    className="text-base font-bold text-white truncate"
                    style={{ color: "#ffffff" }}
                  >
                    {authUser.display_name || "Institutional Trader"}
                  </h2>
                  <p className="text-xs text-slate-400 font-mono truncate">{authUser.email}</p>
                </div>
              </div>

              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-mono font-semibold bg-emerald-950/60 text-emerald-400 border border-emerald-800/60 shrink-0">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                Active
              </span>
            </div>

            <div className="grid grid-cols-2 gap-3 mb-6 font-mono">
              <div className="p-3 bg-slate-950/60 rounded-xl border border-slate-800/80">
                <span className="text-[10px] text-slate-500 uppercase block">Account ID</span>
                <span className="text-xs font-bold text-slate-200 mt-0.5 block">
                  USR-{String(authUser.id).padStart(5, "0")}
                </span>
              </div>
              <div className="p-3 bg-slate-950/60 rounded-xl border border-slate-800/80">
                <span className="text-[10px] text-slate-500 uppercase block">Desk Role</span>
                <span className="text-xs font-bold text-indigo-400 mt-0.5 block">
                  Quant Trader
                </span>
              </div>
            </div>

            <div className="space-y-3">
              <Link
                href={redirectTarget}
                className="w-full py-2.5 px-4 bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold rounded-xl shadow-lg shadow-blue-600/25 flex items-center justify-center gap-2 transition-all text-decoration-none"
              >
                <span>Enter Quant Terminal</span>
                <ArrowRight size={14} />
              </Link>

              <button
                onClick={handleLogout}
                disabled={authLoading}
                className="w-full py-2.5 px-4 bg-slate-800/80 hover:bg-rose-950/40 text-slate-300 hover:text-rose-300 hover:border-rose-800/50 border border-slate-700/60 rounded-xl text-xs font-semibold flex items-center justify-center gap-2 transition-all cursor-pointer"
              >
                <LogOut size={14} />
                <span>{authLoading ? "Logging Out..." : "Log Out Session"}</span>
              </button>
            </div>
          </div>
        ) : (
          // ==========================================
          // Unauthenticated Form (Sign In / Create Account)
          // ==========================================
          <div className="bg-slate-900/90 border border-slate-800 rounded-2xl shadow-2xl backdrop-blur-xl overflow-hidden">
            {/* Header Tabs */}
            <div className="flex border-b border-slate-800/80 bg-slate-950/40 p-1.5">
              <button
                onClick={() => {
                  setMode("signin");
                  setMessage(null);
                }}
                className={`flex-1 py-2.5 px-4 text-xs font-semibold rounded-xl flex items-center justify-center gap-2 transition-all cursor-pointer ${
                  mode === "signin"
                    ? "bg-slate-800 text-white shadow-sm border border-slate-700/80"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                <LogIn size={14} />
                <span>Sign In</span>
              </button>
              <button
                onClick={() => {
                  setMode("signup");
                  setMessage(null);
                }}
                className={`flex-1 py-2.5 px-4 text-xs font-semibold rounded-xl flex items-center justify-center gap-2 transition-all cursor-pointer ${
                  mode === "signup"
                    ? "bg-slate-800 text-white shadow-sm border border-slate-700/80"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                <UserPlus size={14} />
                <span>Create Account</span>
              </button>
            </div>

            <div className="p-6 sm:p-7">
              {mode === "signin" ? (
                <form onSubmit={handleSignIn} className="space-y-4">
                  <div>
                    <label className="block text-xs font-medium text-slate-300 mb-1.5 font-mono">
                      Email Address
                    </label>
                    <div className="relative">
                      <Mail
                        size={16}
                        className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-500"
                      />
                      <input
                        type="email"
                        required
                        placeholder="trader@stockportfolio.in"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        className="w-full pl-10 pr-3.5 py-2.5 bg-slate-950 border border-slate-800 rounded-xl text-xs text-white placeholder:text-slate-600 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 font-mono transition-all"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-medium text-slate-300 mb-1.5 font-mono">
                      Password
                    </label>
                    <div className="relative">
                      <Lock
                        size={16}
                        className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-500"
                      />
                      <input
                        type="password"
                        required
                        placeholder="••••••••••••"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        className="w-full pl-10 pr-3.5 py-2.5 bg-slate-950 border border-slate-800 rounded-xl text-xs text-white placeholder:text-slate-600 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 font-mono transition-all"
                      />
                    </div>
                  </div>

                  <button
                    type="submit"
                    disabled={authLoading}
                    className="w-full py-2.5 px-4 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-semibold shadow-lg shadow-blue-600/25 flex items-center justify-center gap-2 transition-all cursor-pointer mt-2"
                  >
                    {authLoading ? (
                      <RefreshCw size={14} className="animate-spin" />
                    ) : (
                      <LogIn size={14} />
                    )}
                    <span>{authLoading ? "Verifying..." : "Sign In to Terminal"}</span>
                  </button>

                  <div className="pt-3 border-t border-slate-800/80 flex items-center justify-between">
                    <span className="text-[11px] text-slate-500 font-mono">Demo Evaluation:</span>
                    <button
                      type="button"
                      onClick={handleQuickDemoAuth}
                      disabled={authLoading}
                      className="text-xs text-indigo-400 hover:text-indigo-300 font-medium cursor-pointer flex items-center gap-1.5 transition-colors"
                    >
                      <Sparkles size={13} />
                      <span>Instant Demo Access</span>
                    </button>
                  </div>
                </form>
              ) : (
                <form onSubmit={handleSignUp} className="space-y-4">
                  <div>
                    <label className="block text-xs font-medium text-slate-300 mb-1.5 font-mono">
                      Full Name / Desk Identifier (Optional)
                    </label>
                    <div className="relative">
                      <UserIcon
                        size={16}
                        className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-500"
                      />
                      <input
                        type="text"
                        placeholder="e.g. Abhishek Kumar"
                        value={displayName}
                        onChange={(e) => setDisplayName(e.target.value)}
                        className="w-full pl-10 pr-3.5 py-2.5 bg-slate-950 border border-slate-800 rounded-xl text-xs text-white placeholder:text-slate-600 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-medium text-slate-300 mb-1.5 font-mono">
                      Email Address
                    </label>
                    <div className="relative">
                      <Mail
                        size={16}
                        className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-500"
                      />
                      <input
                        type="email"
                        required
                        placeholder="trader@stockportfolio.in"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        className="w-full pl-10 pr-3.5 py-2.5 bg-slate-950 border border-slate-800 rounded-xl text-xs text-white placeholder:text-slate-600 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 font-mono transition-all"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-medium text-slate-300 mb-1.5 font-mono">
                      Password (min 6 characters)
                    </label>
                    <div className="relative">
                      <Lock
                        size={16}
                        className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-500"
                      />
                      <input
                        type="password"
                        required
                        minLength={6}
                        placeholder="••••••••••••"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        className="w-full pl-10 pr-3.5 py-2.5 bg-slate-950 border border-slate-800 rounded-xl text-xs text-white placeholder:text-slate-600 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 font-mono transition-all"
                      />
                    </div>
                  </div>

                  <button
                    type="submit"
                    disabled={authLoading}
                    className="w-full py-2.5 px-4 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-semibold shadow-lg shadow-blue-600/25 flex items-center justify-center gap-2 transition-all cursor-pointer mt-2"
                  >
                    {authLoading ? (
                      <RefreshCw size={14} className="animate-spin" />
                    ) : (
                      <UserPlus size={14} />
                    )}
                    <span>{authLoading ? "Creating..." : "Create Account & Enter"}</span>
                  </button>

                  <div className="pt-3 border-t border-slate-800/80 flex items-center justify-between">
                    <span className="text-[11px] text-slate-500 font-mono">Quick Access:</span>
                    <button
                      type="button"
                      onClick={handleQuickDemoAuth}
                      disabled={authLoading}
                      className="text-xs text-indigo-400 hover:text-indigo-300 font-medium cursor-pointer flex items-center gap-1.5 transition-colors"
                    >
                      <Sparkles size={13} />
                      <span>Instant Demo Setup</span>
                    </button>
                  </div>
                </form>
              )}
            </div>
          </div>
        )}
      </main>

      {/* Institutional Footer */}
      <footer className="w-full max-w-6xl mx-auto px-6 py-6 text-center z-10">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-2 text-[11px] font-mono text-slate-500">
          <div className="flex items-center gap-2">
            <Shield size={13} className="text-slate-400" />
            <span>PBKDF2-HMAC-SHA256 Encryption · Enterprise Identity Isolation</span>
          </div>
          <span>© 2026 StockPortfolio.in</span>
        </div>
      </footer>
    </div>
  );
}

export default function AuthPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen w-full bg-slate-950 text-slate-400 font-mono text-xs flex items-center justify-center">
          Loading Security Gate...
        </div>
      }
    >
      <AuthContent />
    </Suspense>
  );
}
