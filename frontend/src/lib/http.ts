import { apiUrl } from "./api";
import { getToken } from "./portfolioApi";

// Every route added after Phase 5 shares the same two headers and the same
// error contract, so the plumbing lives here rather than being copied into
// each of the five domain clients.

const ACCOUNT_KEY = "stockportfolio.account_key";

/** The opaque account key from `POST /api/accounts`, shown exactly once. */
export function getAccountKey(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(ACCOUNT_KEY);
}

export function setAccountKey(key: string): void {
  window.localStorage.setItem(ACCOUNT_KEY, key);
}

export function clearAccountKey(): void {
  window.localStorage.removeItem(ACCOUNT_KEY);
}

function headers(withBody: boolean, withAccount: boolean): HeadersInit {
  const result: Record<string, string> = {};
  if (withBody) result["Content-Type"] = "application/json";

  const token = getToken();
  if (token) result["X-Fyers-Token"] = token;

  if (withAccount) {
    const key = getAccountKey();
    if (key) result["X-Account-Key"] = key;
  }
  return result;
}

/** FastAPI puts the message in `detail`, which is sometimes an object. */
export async function handle<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      if (typeof body?.detail === "string") {
        detail = body.detail;
      } else if (body?.detail && typeof body.detail === "object") {
        detail = body.detail.reason ?? JSON.stringify(body.detail);
      }
    } catch {
      // A non-JSON body (a gateway timeout page, usually) keeps the status text.
    }
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}

export async function getJson<T>(
  path: string,
  options: { signal?: AbortSignal; account?: boolean } = {}
): Promise<T> {
  const response = await fetch(apiUrl(path), {
    headers: headers(false, options.account ?? false),
    signal: options.signal,
  });
  return handle<T>(response);
}

export async function postJson<T>(
  path: string,
  body: unknown,
  options: { signal?: AbortSignal; account?: boolean } = {}
): Promise<T> {
  const response = await fetch(apiUrl(path), {
    method: "POST",
    headers: headers(true, options.account ?? false),
    body: JSON.stringify(body),
    signal: options.signal,
  });
  return handle<T>(response);
}

/** Query string from a sparse filter object; unset values are dropped. */
export function queryString(params: Record<string, unknown>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    if (Array.isArray(value)) {
      value.forEach((entry) => search.append(key, String(entry)));
    } else {
      search.append(key, String(value));
    }
  }
  const encoded = search.toString();
  return encoded ? `?${encoded}` : "";
}
