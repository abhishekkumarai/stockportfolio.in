"use client";

import { useEffect, useState } from "react";
import { aiStatus, monthlyReport, type AiReport, type AiStatus } from "@/lib/aiApi";
import type { StoredPortfolio } from "@/lib/portfolioApi";

// The narrator is strictly a narrator: the backend regenerates the same
// deterministic analysis this dashboard already shows, hands it to the model,
// and then checks every figure in the prose against that data. This component
// surfaces the result of that check rather than hiding it.

export default function AiMemo({ portfolio }: { portfolio: StoredPortfolio }) {
  const [status, setStatus] = useState<AiStatus | null>(null);
  const [report, setReport] = useState<AiReport | null>(null);
  const [effort, setEffort] = useState("high");
  const [includeNews, setIncludeNews] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    aiStatus(controller.signal)
      .then(setStatus)
      .catch(() => setStatus(null));
    return () => controller.abort();
  }, []);

  const isEmpty = portfolio.equity.length === 0 && portfolio.funds.length === 0;

  const generate = async () => {
    setLoading(true);
    setError(null);
    try {
      setReport(await monthlyReport(portfolio, { includeNews, effort }));
    } catch (err) {
      setError((err as Error).message);
      setReport(null);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div style={{ display: "flex", gap: 14, flexWrap: "wrap", alignItems: "flex-end", marginBottom: 16 }}>
        <label>
          <span
            style={{
              display: "block",
              color: "var(--text-muted)",
              fontSize: "0.72rem",
              textTransform: "uppercase",
              letterSpacing: "0.05em",
              marginBottom: 6,
            }}
          >
            Reasoning effort
          </span>
          <select
            value={effort}
            onChange={(event) => setEffort(event.target.value)}
            style={{
              background: "var(--bg-secondary)",
              border: "1px solid var(--border-subtle)",
              borderRadius: 8,
              color: "var(--text-primary)",
              padding: "8px 10px",
              fontSize: "0.9rem",
            }}
          >
            <option value="low">Low — quick summary</option>
            <option value="medium">Medium</option>
            <option value="high">High (default)</option>
            <option value="xhigh">Extra high</option>
            <option value="max">Maximum</option>
          </select>
        </label>

        <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: "0.85rem", paddingBottom: 8 }}>
          <input
            type="checkbox"
            checked={includeNews}
            onChange={(event) => setIncludeNews(event.target.checked)}
          />
          Include the news digest
        </label>

        <button
          className="glowing-button"
          onClick={generate}
          disabled={loading || isEmpty || status?.configured === false}
          style={{ padding: "8px 18px", fontSize: "0.85rem" }}
        >
          {loading ? "Writing the memo…" : "Generate monthly memo"}
        </button>
      </div>

      {status && !status.configured && (
        <div className="glass-panel" style={{ borderColor: "var(--color-hold)", marginBottom: 16, padding: "16px 20px" }}>
          <strong style={{ color: "var(--color-hold)" }}>The AI layer is not configured</strong>
          <p style={{ margin: "6px 0 0", color: "var(--text-secondary)", fontSize: "0.88rem" }}>{status.note}</p>
        </div>
      )}

      {isEmpty && (
        <p style={{ color: "var(--text-muted)" }}>
          Add holdings first — the memo is written over your computed metrics, so there is nothing
          to narrate yet.
        </p>
      )}

      {error && (
        <div className="glass-panel" style={{ borderColor: "var(--color-sell)", marginBottom: 16, padding: "14px 18px" }}>
          <p style={{ margin: 0, color: "var(--color-sell)" }}>{error}</p>
        </div>
      )}

      {loading && (
        <div className="loading-container">
          <div className="spinner" />
        </div>
      )}

      {report && !report.available && (
        <p style={{ color: "var(--color-hold)" }}>{report.reason}</p>
      )}

      {report?.available && report.report_markdown && (
        <>
          <div
            className="glass-panel"
            style={{
              borderColor:
                report.unsupported_figures && report.unsupported_figures.length > 0
                  ? "var(--color-hold)"
                  : "var(--color-buy)",
              marginBottom: 16,
              padding: "16px 20px",
            }}
          >
            <p style={{ margin: 0, color: "var(--text-secondary)", fontSize: "0.88rem" }}>
              {report.verification}
            </p>
            {report.unsupported_figures && report.unsupported_figures.length > 0 && (
              <p style={{ margin: "6px 0 0", color: "var(--color-hold)", fontSize: "0.82rem" }}>
                Unverified: {report.unsupported_figures.slice(0, 12).join(", ")}
              </p>
            )}
            <p style={{ margin: "8px 0 0", color: "var(--text-muted)", fontSize: "0.78rem" }}>
              {report.period} · generated {report.as_of?.slice(0, 10)} · {report.model} at {report.effort} effort
            </p>
          </div>

          <article style={{ lineHeight: 1.65, color: "var(--text-secondary)", padding: "24px 28px", background: "#ffffff", borderRadius: 8, border: "1px solid var(--border-subtle)", boxShadow: "0 1px 2px 0 rgba(15, 23, 42, 0.04)" }}>
            <Markdown source={report.report_markdown} />
          </article>
        </>
      )}
    </div>
  );
}

/**
 * A deliberately small Markdown renderer.
 *
 * The memo is generated by our own backend from a fixed prompt and uses only
 * headings, bold, lists and paragraphs, so pulling in a full parser (and its
 * sanitiser) to render it would be more dependency than the job needs. No HTML
 * is interpreted — every character is rendered as text.
 */
function Markdown({ source }: { source: string }) {
  const blocks: React.ReactNode[] = [];
  const lines = source.split("\n");
  let list: string[] = [];

  const flushList = (key: string) => {
    if (list.length === 0) return;
    blocks.push(
      <ul key={key} style={{ paddingLeft: 20, marginBottom: 14 }}>
        {list.map((item, index) => (
          <li key={index} style={{ marginBottom: 6 }}>
            <Inline text={item} />
          </li>
        ))}
      </ul>
    );
    list = [];
  };

  lines.forEach((raw, index) => {
    const line = raw.trimEnd();
    const bullet = line.match(/^\s*[-*]\s+(.*)$/);
    if (bullet) {
      list.push(bullet[1]);
      return;
    }
    flushList(`list-${index}`);

    if (!line.trim()) return;

    const heading = line.match(/^(#{1,4})\s+(.*)$/);
    if (heading) {
      const level = heading[1].length;
      const sizes = ["1.4rem", "1.2rem", "1.05rem", "0.95rem"];
      blocks.push(
        <div
          key={index}
          style={{
            fontFamily: "var(--font-headings)",
            fontSize: sizes[level - 1],
            fontWeight: 600,
            color: "var(--text-primary)",
            margin: level === 1 ? "20px 0 10px" : "16px 0 8px",
          }}
        >
          <Inline text={heading[2]} />
        </div>
      );
      return;
    }

    blocks.push(
      <p key={index} style={{ marginBottom: 12 }}>
        <Inline text={line} />
      </p>
    );
  });

  flushList("list-final");
  return <>{blocks}</>;
}

/** Bold and inline code only; everything else stays literal text. */
function Inline({ text }: { text: string }) {
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g);
  return (
    <>
      {parts.map((part, index) => {
        if (part.startsWith("**") && part.endsWith("**")) {
          return (
            <strong key={index} style={{ color: "var(--text-primary)" }}>
              {part.slice(2, -2)}
            </strong>
          );
        }
        if (part.startsWith("`") && part.endsWith("`") && part.length > 1) {
          return (
            <code key={index} style={{ color: "var(--accent-cyan)", fontSize: "0.9em" }}>
              {part.slice(1, -1)}
            </code>
          );
        }
        return <span key={index}>{part}</span>;
      })}
    </>
  );
}
