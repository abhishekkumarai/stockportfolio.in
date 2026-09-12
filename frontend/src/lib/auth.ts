import { apiUrl } from "./api";
import { setAccountKey, clearAccountKey } from "./http";

export interface User {
  id: number;
  email: string;
  display_name: string;
  created_at: string | null;
}

export interface AuthResponse {
  token: string;
  user: User;
  message: string;
}

export const TOKEN_STORAGE_KEY = "stockportfolio_token";
export const USER_STORAGE_KEY = "stockportfolio_user";
export const COOKIE_NAME = "stockportfolio_token";

// Cookie management helpers for Next.js SSR / Middleware compatibility
export function setAuthCookie(token: string, days: number = 30): void {
  if (typeof document === "undefined") return;
  const maxAge = days * 24 * 60 * 60;
  document.cookie = `${COOKIE_NAME}=${encodeURIComponent(
    token
  )}; path=/; max-age=${maxAge}; SameSite=Lax`;
}

export function removeAuthCookie(): void {
  if (typeof document === "undefined") return;
  document.cookie = `${COOKIE_NAME}=; path=/; max-age=0; SameSite=Lax`;
}

export function getAuthCookie(): string | null {
  if (typeof document === "undefined") return null;
  const nameEQ = `${COOKIE_NAME}=`;
  const ca = document.cookie.split(";");
  for (let i = 0; i < ca.length; i++) {
    let c = ca[i].trim();
    if (c.indexOf(nameEQ) === 0) {
      return decodeURIComponent(c.substring(nameEQ.length));
    }
  }
  return null;
}

export function getAuthToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    const fromLocal = window.localStorage.getItem(TOKEN_STORAGE_KEY);
    if (fromLocal) return fromLocal;
  } catch {
    // localStorage might be blocked or unavailable
  }
  return getAuthCookie();
}

export function getAuthUser(): User | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(USER_STORAGE_KEY);
    if (raw) {
      return JSON.parse(raw) as User;
    }
  } catch {
    // parse error or storage blocked
  }
  return null;
}

export function isAuthenticated(): boolean {
  return Boolean(getAuthToken());
}

export function saveSession(token: string, user: User): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(TOKEN_STORAGE_KEY, token);
    window.localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(user));
  } catch {
    // storage fallback
  }
  setAccountKey(token);
  setAuthCookie(token);
  window.dispatchEvent(new Event("auth-changed"));
}

export function clearSession(): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(TOKEN_STORAGE_KEY);
    window.localStorage.removeItem(USER_STORAGE_KEY);
  } catch {
    // ignore
  }
  clearAccountKey();
  removeAuthCookie();
  window.dispatchEvent(new Event("auth-changed"));
}

export async function signin(email: string, password: string): Promise<AuthResponse> {
  const res = await fetch(apiUrl("/api/auth/signin"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });

  if (!res.ok) {
    let message = `Sign in failed (${res.status})`;
    try {
      const err = await res.json();
      if (err?.detail) message = typeof err.detail === "string" ? err.detail : JSON.stringify(err.detail);
    } catch {
      // fallback
    }
    throw new Error(message);
  }

  const data: AuthResponse = await res.json();
  saveSession(data.token, data.user);
  return data;
}

export async function signup(
  email: string,
  password: string,
  displayName?: string
): Promise<AuthResponse> {
  const res = await fetch(apiUrl("/api/auth/signup"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      email,
      password,
      display_name: displayName || undefined,
    }),
  });

  if (!res.ok) {
    let message = `Registration failed (${res.status})`;
    try {
      const err = await res.json();
      if (err?.detail) message = typeof err.detail === "string" ? err.detail : JSON.stringify(err.detail);
    } catch {
      // fallback
    }
    throw new Error(message);
  }

  const data: AuthResponse = await res.json();
  saveSession(data.token, data.user);
  return data;
}

export async function logout(): Promise<void> {
  const token = getAuthToken();
  if (token) {
    try {
      await fetch(apiUrl("/api/auth/logout"), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
          "X-Account-Key": token,
        },
      });
    } catch (err) {
      console.warn("Backend logout notification failed:", err);
    }
  }
  clearSession();
}

export async function fetchCurrentUser(): Promise<User | null> {
  const token = getAuthToken();
  if (!token) return null;

  try {
    const res = await fetch(apiUrl("/api/auth/me"), {
      headers: {
        Authorization: `Bearer ${token}`,
        "X-Account-Key": token,
      },
    });
    if (!res.ok) {
      if (res.status === 401) {
        clearSession();
      }
      return null;
    }
    const data = await res.json();
    if (data?.user) {
      if (typeof window !== "undefined") {
        window.localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(data.user));
      }
      return data.user as User;
    }
  } catch (err) {
    console.warn("Error fetching current user profile:", err);
  }
  return getAuthUser();
}
