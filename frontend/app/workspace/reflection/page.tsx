"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import AppContainer from "@/components/AppContainer";
import { fetchWorkspaceHistoryCached, getWorkspaceHistoryCachedSnapshot } from "@/lib/workspaceHistory";

type WorkspaceItem = {
  file_name: string;
  saved_at?: string;
  source_type?: string;
  content_type?: string;
  signal_id?: string;
  signal_title?: string;
  signal_summary?: string;
  reflection?: string;
  user_reflection?: string;
  saved_reflection?: string;
  final_reflection?: string;
};

function parseReflection(item: WorkspaceItem): string {
  const candidates = [
    item.reflection,
    item.user_reflection,
    item.saved_reflection,
    item.final_reflection,
  ];

  for (const value of candidates) {
    if (!value) continue;

    const trimmed = value.trim();
    if (!trimmed) continue;

    try {
      const parsed = JSON.parse(trimmed);

      if (typeof parsed === "string") {
        return parsed.trim();
      }

      if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
        const preferredKeys = [
          "reflection",
          "user_reflection",
          "saved_reflection",
          "final_reflection",
          "content",
          "text",
          "summary",
          "value",
        ];

        for (const key of preferredKeys) {
          const val = (parsed as Record<string, unknown>)[key];
          if (typeof val === "string" && val.trim()) {
            return val.trim();
          }
        }

        const merged = Object.values(parsed as Record<string, unknown>)
          .map((val) => {
            if (typeof val === "string") return val.trim();
            return "";
          })
          .filter(Boolean)
          .join("\n");

        if (merged) return merged;
      }
    } catch {
      return trimmed;
    }

    return trimmed;
  }

  return "";
}

export default function ReflectionPage() {
  const [items, setItems] = useState<WorkspaceItem[]>(() => getWorkspaceHistoryCachedSnapshot() as WorkspaceItem[]);
  const [loading, setLoading] = useState(() => getWorkspaceHistoryCachedSnapshot().length === 0);

  useEffect(() => {
    fetchWorkspaceHistoryCached()
      .then((data) => {
        setItems(Array.isArray(data) ? (data as WorkspaceItem[]) : []);
      })
      .catch((error) => {
        console.error("Failed to load workspace history:", error);
        setItems([]);
      })
      .finally(() => {
        setLoading(false);
      });
  }, []);

  const reflectionRows = useMemo(() => {
    const rows: Array<{
      signalTitle: string;
      signalSummary: string;
      reflectionText: string;
      fileName: string;
      signalId?: string;
      savedAt?: string;
    }> = [];

    for (const item of items) {
      const isSavedSignalReflection =
        item.source_type === "signal" &&
        (!item.content_type || item.content_type === "signal");

      if (!isSavedSignalReflection) continue;

      const reflectionText = parseReflection(item);

      if (!reflectionText) continue;

      rows.push({
        signalTitle: item.signal_title || "Untitled signal",
        signalSummary: item.signal_summary || "",
        reflectionText,
        fileName: item.file_name,
        signalId: item.signal_id,
        savedAt: item.saved_at,
      });
    }

    return rows.sort((a, b) => {
      const aTime = a.savedAt ? new Date(a.savedAt).getTime() : 0;
      const bTime = b.savedAt ? new Date(b.savedAt).getTime() : 0;
      return bTime - aTime;
    });
  }, [items]);

  return (
    <AppContainer style={{ paddingTop: "24px" }}>
      <div style={headerPanelStyle}>
        <div>
          <div style={eyebrowStyle}>Workspace</div>
          <h1 style={pageTitleStyle}>Signal Completion Notes</h1>
          <p style={descriptionStyle}>Browse final notes saved when signals are completed into Workspace.</p>
        </div>
        <Link href="/workspace" style={primaryButtonStyle}>
          Back to Workspace
        </Link>
      </div>

      <div style={{ display: "none" }}>
        <Link
          href="/workspace"
          style={{
            textDecoration: "none",
            color: "#374151",
            fontSize: "14px",
            fontWeight: 600,
          }}
        >
          Back to Workspace
        </Link>
      </div>

      {loading ? (
        <div
          style={{
            padding: "20px",
            border: "1px solid #e5e7eb",
            borderRadius: "18px",
            background: "#fff",
            color: "#6b7280",
            boxShadow: "0 4px 14px rgba(15, 23, 42, 0.04)",
          }}
        >
          Loading signal completion notes from workspace history...
        </div>
      ) : reflectionRows.length === 0 ? (
        <div
          style={{
            padding: "20px",
            border: "1px solid #e5e7eb",
            borderRadius: "18px",
            background: "#fff",
            boxShadow: "0 4px 14px rgba(15, 23, 42, 0.04)",
          }}
        >
          No signal completion notes found yet.
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
          <div
            style={{
              fontSize: "14px",
              color: "#6b7280",
            }}
          >
            {formatSignalCount(reflectionRows.length)} with <strong>completion notes</strong>
          </div>

          {reflectionRows.map((row, index) => (
            <div
              key={`${row.fileName}-${index}`}
              style={{
                border: "1px solid #e5e7eb",
                borderRadius: "18px",
                padding: "18px",
                background: "#fff",
                boxShadow: "0 4px 14px rgba(15, 23, 42, 0.04)",
              }}
            >
              <div
                style={{
                  fontSize: "12px",
                  color: "#6b7280",
                  marginBottom: "8px",
                  textTransform: "uppercase",
                  letterSpacing: "0.4px",
                }}
              >
                {row.savedAt || "No timestamp"}
              </div>

              <h2
                style={{
                  marginTop: 0,
                  marginBottom: "10px",
                  fontSize: "18px",
                  fontWeight: 500,
                  lineHeight: "1.35",
                  color: "#111827",
                }}
              >
                {row.signalTitle}
              </h2>

              {row.signalSummary ? (
                <div
                  style={{
                    marginBottom: "14px",
                    fontSize: "14px",
                    lineHeight: "1.7",
                    color: "#4b5563",
                  }}
                >
                  {row.signalSummary}
                </div>
              ) : null}

              <div
                style={{
                  padding: "14px 16px",
                  borderRadius: "8px",
                  background: "#ffffff",
                  border: "1px solid #e5e7eb",
                }}
              >
                <div
                  style={{
                    fontSize: "12px",
                    fontWeight: 700,
                    marginBottom: "8px",
                    textTransform: "uppercase",
                    letterSpacing: "0.4px",
                    color: "#6b7280",
                  }}
                >
                  Completion Note
                </div>

                <div
                  style={{
                    fontSize: "14px",
                    lineHeight: "1.8",
                    color: "#374151",
                    whiteSpace: "pre-wrap",
                  }}
                >
                  {row.reflectionText}
                </div>
              </div>

              <div style={{ marginTop: "16px" }}>
                <Link
                  href={`/workspace/detail?file_name=${encodeURIComponent(row.fileName)}`}
                  style={secondaryButtonStyle}
                >
                  View full workspace record -&gt;
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </AppContainer>
  );
}

function formatSignalCount(count: number) {
  return `${count} signal${count === 1 ? "" : "s"}`;
}

const headerPanelStyle = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  gap: "18px",
  flexWrap: "wrap" as const,
  border: "1px solid #e5e7eb",
  borderRadius: "20px",
  background: "#ffffff",
  padding: "18px",
  marginBottom: "20px",
  boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
} as const;

const eyebrowStyle = {
  color: "#6b7280",
  fontSize: "12px",
  fontWeight: 700,
  textTransform: "uppercase" as const,
  letterSpacing: "0.4px",
} as const;

const pageTitleStyle = {
  margin: "4px 0 0",
  color: "#111827",
  fontSize: "18px",
  fontWeight: 600,
  lineHeight: 1.35,
} as const;

const descriptionStyle = {
  margin: "6px 0 0",
  color: "#6b7280",
  fontSize: "13px",
  lineHeight: 1.5,
  maxWidth: "760px",
} as const;

const primaryButtonStyle = {
  display: "inline-flex",
  alignItems: "center",
  border: "1px solid #111827",
  borderRadius: "10px",
  background: "#111827",
  color: "#ffffff",
  padding: "7px 12px",
  textDecoration: "none",
  fontSize: "13px",
  fontWeight: 600,
} as const;

const secondaryButtonStyle = {
  display: "inline-flex",
  alignItems: "center",
  border: "1px solid #d1d5db",
  borderRadius: "10px",
  background: "#ffffff",
  color: "#111827",
  padding: "7px 12px",
  textDecoration: "none",
  fontSize: "13px",
  fontWeight: 600,
} as const;
