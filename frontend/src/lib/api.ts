// NEXT_PUBLIC_* values are inlined at build time, so an unset variable in a
// production build would silently ship "localhost" to every visitor's browser.
// Failing the build instead turns that into a loud, early error.
const configured = process.env.NEXT_PUBLIC_API_URL?.trim();

if (process.env.NODE_ENV === "production") {
  if (!configured) {
    throw new Error(
      "NEXT_PUBLIC_API_URL is not set. Configure it in the Vercel project " +
        "settings for both Production and Preview, then redeploy."
    );
  }
  // A scheme-less value like "www.example.com" is not an absolute URL: the
  // browser resolves it against the current page, silently turning every API
  // call into a 404 on the frontend's own domain. That shipped to production
  // once, and the only symptom was an empty page.
  if (!/^https?:\/\//.test(configured)) {
    throw new Error(
      `NEXT_PUBLIC_API_URL must start with http:// or https:// — got "${configured}". ` +
        "Without a scheme the browser treats it as a relative path, not the backend."
    );
  }
}

// A trailing slash would produce a double slash once a path is appended.
export const API_BASE = (configured ?? "http://127.0.0.1:8001").replace(/\/+$/, "");

export const apiUrl = (path: string) =>
  `${API_BASE}${path.startsWith("/") ? path : `/${path}`}`;
