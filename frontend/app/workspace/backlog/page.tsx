"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import AppContainer from "@/components/AppContainer";
import { API_BASE } from "@/lib/api";

type SavedItem = {
  id: string;
  signal_id?: string;
  title: string;
  summary: string;
  source: string;
  url?: string;
  published_at?: string;
  collected_at?: string;
  saved_reason?: string;
  status: string;
  topic?: string;
  importance_level?: string;
};

type SavedResponse = {
  items: SavedItem[];
  summary?: {
    count?: number;
    error?: string;
  };
};

function getErrorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}

function formatDate(dateStr?: string) {
  if (!dateStr) return "n/a";
  const d = new Date(dateStr);
  if (Number.isNaN(d.getTime())) return dateStr;
  return d.toLocaleDateString("en-AU", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

function resolveSignalId(item: SavedItem) {
  return item.signal_id || item.id;
}

export default function WorkspaceBacklogPage() {
  const router = useRouter();

  const [data, setData] = useState<SavedResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [openingId, setOpeningId] = useState("");

  useEffect(() => {
    let cancelled = false;

    const run = async () => {
      try {
        setLoading(true);
        setError("");

        const res = await fetch(`${API_BASE}/saved`);

        if (!res.ok) {
          throw new Error(`Failed to fetch backlog: ${res.status}`);
        }

        const json = (await res.json()) as SavedResponse;
        if (!cancelled) setData(json);
      } catch (err: unknown) {
        if (!cancelled) setError(getErrorMessage(err, "Failed to load saved backlog."));
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    void run();

    return () => {
      cancelled = true;
    };
  }, []);

  const items = useMemo(() => data?.items ?? [], [data]);
  const count = data?.summary?.count ?? items.length;

  const stats = useMemo(
    () => ({
      count,
      withReason: items.filter((x) => !!x.saved_reason).length,
      withTopic: items.filter((x) => !!x.topic).length,
    }),
    [items, count],
  );

  const handleStartReflection = (item: SavedItem) => {
    const signalId = resolveSignalId(item);
    if (!signalId) return;

    setOpeningId(signalId);
    router.push(`/signals/detail?id=${encodeURIComponent(signalId)}&from=backlog`);
  };

  return (
    <AppContainer style={{ paddingTop: "24px" }}>
      <div style={headerPanelStyle}>
        <div>
          <div style={eyebrowStyle}>Workspace</div>
          <h1 style={pageTitleStyle}>Saved Backlog</h1>
          <p style={descriptionStyle}>Review saved signals before turning them into completion notes or project memory.</p>
        </div>
        <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
          <Link href="/workspace" style={primaryButtonStyle}>
            Back to Workspace
          </Link>
          <Link href="/signals" style={secondaryButtonStyle}>
            Signal Records
          </Link>
        </div>
      </div>

      <section style={panelStyle}>
        <div style={sectionHeaderStyle}>
          <div>
            <div style={eyebrowStyle}>Backlog Overview</div>
            <h2 style={sectionTitleStyle}>Saved signal queue</h2>
          </div>
        </div>

        <div style={statGridStyle}>
          <StatCard label="Saved Signals" value={stats.count} subLabel="Current saved backlog" />
          <StatCard label="Tagged Topics" value={stats.withTopic} subLabel="Signals with topic labels" />
          <StatCard label="Saved Reasons" value={stats.withReason} subLabel="Signals with explicit save reasons" />
        </div>
      </section>

      <section style={panelStyle}>
        <div style={sectionHeaderStyle}>
          <div>
            <div style={eyebrowStyle}>Saved Signals</div>
            <h2 style={sectionTitleStyle}>{loading ? "Loading backlog" : `${items.length} item(s)`}</h2>
          </div>
        </div>

        {loading ? (
          <div style={stateCardStyle}>Loading saved backlog...</div>
        ) : error ? (
          <div style={errorCardStyle}>{error}</div>
        ) : items.length === 0 ? (
          <div style={stateCardStyle}>No saved signals yet.</div>
        ) : (
          <div style={{ display: "grid", gap: "16px" }}>
            {items.map((item) => {
              const signalId = resolveSignalId(item);

              return (
                <article key={signalId} style={recordCardStyle}>
                  <div style={recordHeaderStyle}>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <h3 style={recordTitleStyle}>{item.title || "Untitled signal"}</h3>
                      {item.summary ? <p style={recordSummaryStyle}>{item.summary}</p> : null}
                    </div>

                    {item.topic ? <span style={topicPillStyle}>{item.topic}</span> : null}
                  </div>

                  <div style={metadataRowStyle}>
                    <span>Source: {item.source || "n/a"}</span>
                    <span>Published: {formatDate(item.published_at)}</span>
                    <span>First Seen: {formatDate(item.collected_at)}</span>
                  </div>

                  {item.saved_reason ? (
                    <div style={noteBlockStyle}>
                      <div style={blockLabelStyle}>Saved Reason</div>
                      <div style={blockTextStyle}>{item.saved_reason}</div>
                    </div>
                  ) : null}

                  <div style={actionRowStyle}>
                    <button
                      onClick={() => handleStartReflection(item)}
                      disabled={!signalId || openingId === signalId}
                      style={{
                        ...secondaryButtonStyle,
                        cursor: !signalId || openingId === signalId ? "not-allowed" : "pointer",
                        opacity: !signalId || openingId === signalId ? 0.7 : 1,
                      }}
                    >
                      {openingId === signalId ? "Opening..." : "Start Completion Note"}
                    </button>

                    {item.url ? (
                      <a href={item.url} target="_blank" rel="noreferrer" style={secondaryButtonStyle}>
                        Open Source
                      </a>
                    ) : null}
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </section>
    </AppContainer>
  );
}

function StatCard({
  label,
  value,
  subLabel,
}: {
  label: string;
  value: number | string;
  subLabel?: string;
}) {
  return (
    <div style={statCardStyle}>
      <div style={statLabelStyle}>{label}</div>
      <div style={statValueStyle}>{value}</div>
      {subLabel ? <div style={statSubLabelStyle}>{subLabel}</div> : null}
    </div>
  );
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

const panelStyle = {
  border: "1px solid #e5e7eb",
  borderRadius: "20px",
  background: "#ffffff",
  padding: "18px",
  marginBottom: "20px",
  boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
} as const;

const sectionHeaderStyle = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  gap: "12px",
  flexWrap: "wrap" as const,
  marginBottom: "14px",
} as const;

const statGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
  gap: "12px",
} as const;

const statCardStyle = {
  border: "1px solid #e5e7eb",
  borderRadius: "18px",
  padding: "18px",
  background: "#ffffff",
  boxShadow: "0 4px 14px rgba(15, 23, 42, 0.04)",
} as const;

const recordCardStyle = {
  border: "1px solid #e5e7eb",
  borderRadius: "18px",
  padding: "18px",
  background: "#ffffff",
  boxShadow: "0 4px 14px rgba(15, 23, 42, 0.04)",
} as const;

const stateCardStyle = {
  border: "1px solid #e5e7eb",
  borderRadius: "18px",
  padding: "20px",
  background: "#ffffff",
  color: "#6b7280",
  boxShadow: "0 4px 14px rgba(15, 23, 42, 0.04)",
} as const;

const errorCardStyle = {
  ...stateCardStyle,
  border: "1px solid #fecaca",
  color: "#991b1b",
} as const;

const recordHeaderStyle = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "flex-start",
  gap: "12px",
  flexWrap: "wrap" as const,
} as const;

const actionRowStyle = {
  marginTop: "16px",
  display: "flex",
  gap: "10px",
  flexWrap: "wrap" as const,
} as const;

const metadataRowStyle = {
  marginTop: "12px",
  fontSize: "13px",
  color: "#6b7280",
  display: "flex",
  flexWrap: "wrap" as const,
  gap: "14px",
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

const sectionTitleStyle = {
  margin: "4px 0 0",
  color: "#111827",
  fontSize: "16px",
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

const recordTitleStyle = {
  margin: 0,
  color: "#111827",
  fontSize: "18px",
  fontWeight: 500,
  lineHeight: 1.35,
} as const;

const recordSummaryStyle = {
  margin: "10px 0 0",
  color: "#374151",
  fontSize: "14px",
  lineHeight: 1.7,
  whiteSpace: "pre-wrap" as const,
} as const;

const noteBlockStyle = {
  marginTop: "14px",
  border: "1px solid #e5e7eb",
  background: "#ffffff",
  borderRadius: "8px",
  padding: "12px 14px",
} as const;

const blockLabelStyle = {
  fontSize: "12px",
  textTransform: "uppercase" as const,
  letterSpacing: "0.4px",
  color: "#6b7280",
  marginBottom: "4px",
  fontWeight: 700,
} as const;

const blockTextStyle = {
  color: "#374151",
  fontSize: "14px",
  lineHeight: 1.7,
} as const;

const statLabelStyle = {
  color: "#374151",
  fontSize: "13px",
  marginBottom: "8px",
} as const;

const statValueStyle = {
  color: "#111827",
  fontSize: "30px",
  fontWeight: 700,
  lineHeight: 1,
} as const;

const statSubLabelStyle = {
  color: "#9ca3af",
  fontSize: "12px",
  marginTop: "8px",
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

const topicPillStyle = {
  border: "1px solid #e5e7eb",
  borderRadius: "999px",
  background: "#ffffff",
  color: "#374151",
  padding: "6px 10px",
  fontSize: "12px",
  fontWeight: 600,
  whiteSpace: "nowrap" as const,
} as const;
