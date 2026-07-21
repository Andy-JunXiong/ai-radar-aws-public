import type { CSSProperties } from "react";

export type VerifiedInsightObjectTone = "good" | "watch" | "bad" | "neutral";

export type VerifiedInsightObjectRow = {
  label: string;
  value: string;
  detail: string;
  tone: VerifiedInsightObjectTone;
};

type VerifiedInsightObjectPanelProps = {
  rows: VerifiedInsightObjectRow[];
  subtitle: string;
  objectId?: string;
  badge?: string;
  headline?: string;
  style?: CSSProperties;
};

function toneStyle(tone: VerifiedInsightObjectTone) {
  if (tone === "good") {
    return {
      border: "1px solid var(--app-success-border)",
      background: "var(--app-success-bg)",
      color: "var(--app-success-fg)",
    };
  }
  if (tone === "bad") {
    return {
      border: "1px solid var(--app-danger-border)",
      background: "var(--app-danger-bg)",
      color: "var(--app-danger-fg)",
    };
  }
  if (tone === "watch") {
    return {
      border: "1px solid var(--app-warning-border)",
      background: "var(--app-warning-bg)",
      color: "var(--app-warning-fg)",
    };
  }
  return {
    border: "1px solid var(--app-surface-border)",
    background: "var(--app-surface-bg)",
    color: "var(--app-text-muted)",
  };
}

export default function VerifiedInsightObjectPanel({
  rows,
  subtitle,
  objectId,
  badge = "Read-only",
  headline = "Verified Insight Object",
  style,
}: VerifiedInsightObjectPanelProps) {
  return (
    <div
      style={{
        border: "1px solid var(--app-info-border)",
        borderRadius: "8px",
        background: "var(--app-info-bg)",
        padding: "14px",
        display: "grid",
        gap: "10px",
        ...style,
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          gap: "12px",
          alignItems: "flex-start",
          flexWrap: "wrap",
        }}
      >
        <div>
          <div
            style={{
              color: "var(--app-info-fg)",
              fontSize: "12px",
              fontWeight: 800,
              textTransform: "uppercase",
              letterSpacing: 0,
            }}
          >
            {headline}
          </div>
          <div style={{ color: "var(--app-text-muted)", fontSize: "13px", lineHeight: 1.55, marginTop: "5px" }}>
            {subtitle}
          </div>
        </div>
        <div style={{ display: "flex", gap: "8px", alignItems: "center", flexWrap: "wrap" }}>
          {objectId ? (
            <div style={{ color: "var(--app-text-subtle)", fontSize: "12px", fontWeight: 700 }}>
              ID: {objectId}
            </div>
          ) : null}
          <div
            style={{
              border: "1px solid var(--app-info-border)",
              borderRadius: "999px",
              background: "var(--app-surface-bg)",
              color: "var(--app-info-fg)",
              padding: "5px 9px",
              fontSize: "11px",
              fontWeight: 850,
              textTransform: "uppercase",
              letterSpacing: 0,
            }}
          >
            {badge}
          </div>
        </div>
      </div>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))",
          gap: "8px",
        }}
      >
        {rows.map((row) => {
          const colors = toneStyle(row.tone);
          return (
            <div
              key={row.label}
              style={{
                border: colors.border,
                borderRadius: "8px",
                background: colors.background,
                color: colors.color,
                padding: "10px",
                minHeight: "98px",
                display: "grid",
                gap: "5px",
                fontSize: "12px",
                lineHeight: 1.45,
              }}
            >
              <div style={{ color: "var(--app-text-strong)", fontSize: "12px", fontWeight: 800 }}>
                {row.label}
              </div>
              <div style={{ color: colors.color, fontSize: "16px", fontWeight: 850 }}>
                {row.value}
              </div>
              <div style={{ color: "var(--app-text-subtle)", fontSize: "11px", lineHeight: 1.45 }}>
                {row.detail}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
