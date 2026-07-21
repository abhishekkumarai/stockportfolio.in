// NEXT_PUBLIC_* values are inlined at build time, so an unset variable in a
// production build would silently ship "localhost" to every visitor's browser.
// Failing the build instead turns that into a loud, early error.
const configured = process.env.NEXT_PUBLIC_API_URL;

if (!configured && process.env.NODE_ENV === "production") {
  throw new Error(
    "NEXT_PUBLIC_API_URL is not set. Configure it in the Vercel project " +
      "settings for both Production and Preview, then redeploy."
  );
}

export const API_BASE = configured ?? "http://127.0.0.1:8001";

export const apiUrl = (path: string) =>
  `${API_BASE}${path.startsWith("/") ? path : `/${path}`}`;
