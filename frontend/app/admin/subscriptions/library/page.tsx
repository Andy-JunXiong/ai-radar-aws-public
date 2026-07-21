"use client";

import Link from "next/link";
import { useEffect, useMemo, useState, type ReactNode } from "react";

import AppContainer from "@/components/AppContainer";
import PageHeader from "@/components/PageHeader";
import RequireAdminAuth from "@/components/RequireAdminAuth";
import SectionCard from "@/components/SectionCard";
import { apiUrl } from "@/lib/api";
import { adminFetch } from "@/lib/adminAuth";
import { buildBetaUserHeaders, getStoredBetaUserId, setStoredBetaUserId } from "@/lib/betaUser";

type SourceItem = {
  id: string;
  name: string;
  url: string;
  type: string;
  enabled: boolean;
  priority: string;
  tags: string[];
};

type SubscriptionSettings = {
  sources: SourceItem[];
};

type SubscriptionResponse = {
  settings?: SubscriptionSettings;
  scope?: string;
  status?: {
    local_path?: string;
    s3_bucket?: string;
    s3_key?: string;
    saved_source_count?: number;
    last_updated_epoch?: number | null;
  };
  runtime?: {
    date?: string;
    generated_at?: string;
    subscription_scope?: string;
    configured_source_count?: number | null;
    matched_subscription_source_count?: number | null;
    configured_active_source_count?: number | null;
    runtime_signal_sources?: string[];
  };
};

const DEFAULT_SUBSCRIPTION_USER_ID = "admin_default";

export default function SubscriptionLibraryPage() {
  const [userId, setUserId] = useState(DEFAULT_SUBSCRIPTION_USER_ID);
  const [scope, setScope] = useState(DEFAULT_SUBSCRIPTION_USER_ID);
  const [sources, setSources] = useState<SourceItem[]>([]);
  const [activeCategory, setActiveCategory] = useState("all");
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState("");
  const [status, setStatus] = useState<SubscriptionResponse["status"] | null>(null);
  const [runtime, setRuntime] = useState<SubscriptionResponse["runtime"] | null>(null);

  function formatStatusTime(epoch?: number | null) {
    if (!epoch) return "Not saved yet";
    try {
      return new Date(epoch * 1000).toLocaleString();
    } catch {
      return "Not saved yet";
    }
  }

  async function loadLibrary(stored: string) {
    setLoading(true);
    setErrorMessage("");

    try {
      const response = await adminFetch(apiUrl("/settings/subscriptions"), {
        headers: {
          ...buildBetaUserHeaders(stored),
        },
        cache: "no-store",
      });
      if (!response.ok) {
        throw new Error(`Failed to load subscriptions (${response.status})`);
      }
      const data = (await response.json()) as SubscriptionResponse;
      setScope(data.scope || stored);
      setSources(Array.isArray(data.settings?.sources) ? data.settings?.sources : []);
      setStatus(data.status || null);
      setRuntime(data.runtime || null);
    } catch (error) {
      console.error(error);
      setSources([]);
      setStatus(null);
      setRuntime(null);
      setErrorMessage("We could not load this subscription library right now. Please refresh and try again.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const stored = getStoredBetaUserId().trim() || DEFAULT_SUBSCRIPTION_USER_ID;
    setUserId(stored);
    setStoredBetaUserId(stored);
    void loadLibrary(stored);
  }, []);

  const stats = useMemo(() => {
    const active = sources.filter((item) => item.enabled).length;
    const paused = sources.filter((item) => !item.enabled).length;
    const highPriority = sources.filter((item) => item.priority === "high").length;
    const types = Array.from(new Set(sources.map((item) => item.type).filter(Boolean)));
    return {
      total: sources.length,
      active,
      paused,
      highPriority,
      typeCount: types.length,
    };
  }, [sources]);

  const categoryItems = useMemo(() => {
    const counts = new Map<string, number>();
    for (const source of sources) {
      const key = (source.type || "custom_url").toLowerCase();
      counts.set(key, (counts.get(key) || 0) + 1);
    }

    const items = [
      { key: "all", label: "All Sources", count: sources.length },
      ...Array.from(counts.entries()).map(([key, count]) => ({
        key,
        label: typeLabel(key),
        count,
      })),
    ];

    return items;
  }, [sources]);

  const filteredSources = useMemo(() => {
    if (activeCategory === "all") return sources;
    return sources.filter((source) => (source.type || "custom_url").toLowerCase() === activeCategory);
  }, [activeCategory, sources]);

  const configuredActiveSourceCount =
    runtime?.configured_active_source_count ?? stats.active;

  return (
    <AppContainer>
      <RequireAdminAuth>
        <PageHeader
          title="My Subscriptions"
          description="Review the sources currently subscribed under this admin scope. This page is the clean read view for Source Library only."
          size="compact"
        />

        <div style={toolbarRowStyle}>
          <Link href="/admin" style={toolbarPrimaryLinkStyle}>
            Back to Admin
          </Link>
          <Link href="/admin/subscriptions" style={toolbarSecondaryLinkStyle}>
            Open Subscription Settings
          </Link>
          <button
            onClick={() => void loadLibrary(userId || DEFAULT_SUBSCRIPTION_USER_ID)}
            disabled={loading}
            style={toolbarButtonStyle}
          >
            {loading ? "Refreshing..." : "Refresh Library"}
          </button>
        </div>

        <SectionCard title="Subscription Snapshot">
          <div style={{ display: "grid", gap: "14px" }}>
            <div style={{ fontSize: "13px", color: "var(--app-text-muted)" }}>
              Current scope: <strong style={{ color: "#111827" }}>{scope}</strong> · user id:{" "}
              <strong style={{ color: "#111827" }}>{userId}</strong>
            </div>
            <div style={infoStateStyle}>
              This page only shows sources saved in <strong>Source Library</strong>. It does not include manual uploads,
              manual notes, or manually saved signals from the signal workflow.
            </div>
            <div style={runtimeStatusPanelStyle}>
              <div style={{ fontSize: "14px", fontWeight: 800, color: "var(--app-text-strong)" }}>Library Runtime Status</div>
              <div style={runtimeStatusGridStyle}>
                <StatMini label="Saved sources" value={status?.saved_source_count ?? sources.length} />
                <StatMini label="Last saved" value={formatStatusTime(status?.last_updated_epoch)} />
                <StatMini label="S3 bucket" value={status?.s3_bucket || "Not configured"} />
              </div>
              <div style={runtimeStatusPathStyle}>
                <strong>S3 key:</strong> {status?.s3_key || "Unavailable"}
              </div>
            </div>
            <div style={runtimeStatusPanelStyle}>
              <div style={{ fontSize: "14px", fontWeight: 800, color: "var(--app-text-strong)" }}>Daily Runtime Snapshot</div>
              <div style={runtimeStatusGridStyle}>
                <StatMini label="Last run date" value={runtime?.date || "Unavailable"} />
                <StatMini label="Configured active" value={configuredActiveSourceCount} />
                <StatMini
                  label="Matched sources"
                  value={runtime?.matched_subscription_source_count ?? "Unavailable"}
                />
              </div>
              <div style={runtimeStatusPathStyle}>
                <strong>Runtime sources:</strong>{" "}
                {runtime?.runtime_signal_sources?.length
                  ? runtime.runtime_signal_sources.join(", ")
                  : "No runtime source list available yet."}
              </div>
            </div>
            <div style={statsGridStyle}>
              <StatCard label="Total Sources" value={stats.total} />
              <StatCard label="Active" value={stats.active} />
              <StatCard label="Paused" value={stats.paused} />
              <StatCard label="High Priority" value={stats.highPriority} />
              <StatCard label="Source Types" value={stats.typeCount} />
            </div>
          </div>
        </SectionCard>

        <SectionCard title="Subscribed Sources">
          {loading ? (
            <div style={emptyStateStyle}>Loading your subscription library...</div>
          ) : errorMessage ? (
            <div style={errorStateStyle}>{errorMessage}</div>
          ) : sources.length === 0 ? (
            <div style={emptyStateStyle}>
              No subscribed sources yet. Open Subscription Settings to add starter collections or bring in a source with AI Source Assistant.
            </div>
          ) : (
            <div style={libraryLayoutStyle}>
              <div style={categorySidebarStyle}>
                <div style={{ fontSize: "12px", fontWeight: 800, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.08em" }}>
                  Categories
                </div>
                <div style={{ display: "grid", gap: "10px", marginTop: "12px" }}>
                  {categoryItems.map((item) => (
                    <button
                      key={item.key}
                      onClick={() => setActiveCategory(item.key)}
                      style={item.key === activeCategory ? activeCategoryButtonStyle : categoryButtonStyle}
                    >
                      <span>{item.label}</span>
                      <span>{item.count}</span>
                    </button>
                  ))}
                </div>
              </div>
              <div style={{ display: "grid", gap: "14px" }}>
                {filteredSources.length === 0 ? (
                  <div style={emptyStateStyle}>No saved sources match this category yet.</div>
                ) : (
                  filteredSources.map((source) => (
                    <div key={source.id} style={sourceCardStyle}>
                      <div style={{ display: "grid", gap: "10px" }}>
                        <div
                          style={{
                            display: "flex",
                            justifyContent: "space-between",
                            gap: "12px",
                            alignItems: "flex-start",
                            flexWrap: "wrap",
                          }}
                        >
                          <div style={{ display: "grid", gap: "4px" }}>
                            <div style={{ fontSize: "18px", fontWeight: 800, color: "var(--app-text-strong)" }}>
                              {source.name || "Untitled source"}
                            </div>
                            <a href={source.url} target="_blank" rel="noreferrer" style={sourceUrlStyle}>
                              {source.url}
                            </a>
                          </div>
                          <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                            <TagChip>{source.enabled ? "active" : "paused"}</TagChip>
                            <TagChip>{typeLabel(source.type || "custom_url")}</TagChip>
                            <TagChip>{source.priority || "normal"}</TagChip>
                          </div>
                        </div>
                        <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                          {(Array.isArray(source.tags) ? source.tags : []).length ? (
                            source.tags.map((tag) => <TagChip key={`${source.id}-${tag}`}>{tag}</TagChip>)
                          ) : (
                            <span style={{ fontSize: "13px", color: "var(--app-text-subtle)" }}>No tags set yet.</span>
                          )}
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}
        </SectionCard>
      </RequireAdminAuth>
    </AppContainer>
  );
}

function typeLabel(type: string) {
  const value = (type || "custom_url").toLowerCase();
  if (value === "official_blog") return "Official Blog";
  if (value === "custom_url") return "Custom URL";
  if (value === "rss") return "RSS";
  if (value === "research") return "Research";
  if (value === "newsletter") return "Newsletter";
  return value;
}

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <div style={statCardStyle}>
      <div
        style={{
          fontSize: "12px",
          fontWeight: 700,
          color: "var(--app-text-muted)",
          textTransform: "uppercase",
          letterSpacing: 0,
        }}
      >
        {label}
      </div>
      <div style={{ marginTop: "10px", fontSize: "30px", fontWeight: 850, color: "var(--app-text-strong)", letterSpacing: 0 }}>
        {value}
      </div>
    </div>
  );
}

function StatMini({ label, value }: { label: string; value: string | number }) {
  return (
    <div style={runtimeStatCardStyle}>
      <div style={runtimeStatLabelStyle}>{label}</div>
      <div style={runtimeStatValueStyle}>{value}</div>
    </div>
  );
}

function TagChip({ children }: { children: ReactNode }) {
  return <span style={tagChipStyle}>{children}</span>;
}

const toolbarRowStyle = {
  marginBottom: "20px",
  display: "flex",
  gap: "12px",
  flexWrap: "wrap" as const,
  alignItems: "center",
} as const;

const toolbarPrimaryLinkStyle = {
  textDecoration: "none",
  color: "var(--app-secondary-action-fg)",
  fontSize: "14px",
  fontWeight: 700,
  border: "1px solid var(--app-secondary-action-border)",
  borderRadius: "8px",
  padding: "10px 14px",
  background: "var(--app-secondary-action-bg)",
} as const;

const toolbarSecondaryLinkStyle = {
  ...toolbarPrimaryLinkStyle,
  textDecoration: "none",
} as const;

const toolbarButtonStyle = {
  border: "1px solid var(--app-secondary-action-border)",
  borderRadius: "8px",
  background: "var(--app-secondary-action-bg)",
  color: "var(--app-secondary-action-fg)",
  padding: "10px 14px",
  fontSize: "14px",
  fontWeight: 700,
  cursor: "pointer",
} as const;

const libraryLayoutStyle = {
  display: "grid",
  gridTemplateColumns: "260px minmax(0, 1fr)",
  gap: "18px",
  alignItems: "start",
} as const;

const categorySidebarStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  padding: "16px",
} as const;

const categoryButtonStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-bg)",
  color: "var(--app-text-muted)",
  padding: "12px 14px",
  fontSize: "14px",
  fontWeight: 700,
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  cursor: "pointer",
} as const;

const activeCategoryButtonStyle = {
  ...categoryButtonStyle,
  border: "1px solid var(--app-primary-action-border)",
  background: "var(--app-primary-action-bg)",
  color: "var(--app-primary-action-fg)",
} as const;

const statsGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
  gap: "12px",
} as const;

const statCardStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  padding: "16px",
} as const;

const sourceCardStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  padding: "16px",
} as const;

const sourceUrlStyle = {
  color: "var(--app-info-fg)",
  textDecoration: "none",
  fontSize: "14px",
  fontWeight: 650,
  lineHeight: 1.7,
  wordBreak: "break-all" as const,
} as const;

const tagChipStyle = {
  display: "inline-flex",
  alignItems: "center",
  gap: "6px",
  padding: "6px 10px",
  borderRadius: "999px",
  border: "1px solid var(--app-chip-border)",
  background: "var(--app-chip-bg)",
  color: "var(--app-chip-fg)",
  fontSize: "12px",
  fontWeight: 700,
} as const;

const emptyStateStyle = {
  border: "1px dashed var(--app-surface-border)",
  borderRadius: "8px",
  padding: "16px",
  color: "var(--app-text-muted)",
  background: "var(--app-surface-muted-bg)",
  fontSize: "14px",
} as const;

const errorStateStyle = {
  border: "1px solid var(--app-danger-border)",
  borderRadius: "8px",
  padding: "16px",
  color: "var(--app-danger-fg)",
  background: "var(--app-danger-bg)",
  fontSize: "14px",
} as const;

const infoStateStyle = {
  border: "1px solid var(--app-info-border)",
  borderRadius: "8px",
  padding: "14px 16px",
  color: "var(--app-info-fg)",
  background: "var(--app-info-bg)",
  fontSize: "14px",
  lineHeight: 1.7,
} as const;

const runtimeStatusPanelStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  padding: "14px 16px",
  display: "grid",
  gap: "12px",
} as const;

const runtimeStatusGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
  gap: "10px",
} as const;

const runtimeStatCardStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-bg)",
  padding: "12px",
  display: "grid",
  gap: "4px",
} as const;

const runtimeStatLabelStyle = {
  fontSize: "12px",
  color: "var(--app-text-muted)",
  fontWeight: 700,
} as const;

const runtimeStatValueStyle = {
  fontSize: "14px",
  color: "var(--app-text-strong)",
  fontWeight: 700,
  lineHeight: 1.5,
  wordBreak: "break-word" as const,
} as const;

const runtimeStatusPathStyle = {
  fontSize: "12px",
  color: "var(--app-text-subtle)",
  lineHeight: 1.7,
  wordBreak: "break-all" as const,
} as const;
