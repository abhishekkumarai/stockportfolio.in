"use client";

export default function SampleDataNotice({ text }: { text: string }) {
  return (
    <div
      style={{
        border: "1px solid var(--color-hold)",
        borderRadius: 8,
        padding: "10px 14px",
        marginBottom: 16,
        fontSize: "0.82rem",
      }}
    >
      <strong style={{ color: "var(--color-hold)" }}>Sample data.</strong>{" "}
      <span style={{ color: "var(--text-secondary)" }}>{text}</span>
    </div>
  );
}
