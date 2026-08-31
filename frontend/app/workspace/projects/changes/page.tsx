"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import AppContainer from "@/components/AppContainer";
import PageHeader from "@/components/PageHeader";
import RequireAdminAuth from "@/components/RequireAdminAuth";
import { adminFetch } from "@/lib/adminAuth";
import { apiUrl } from "@/lib/api";

type ReviewState = "needs_attention" | "changed" | "baseline" | "unchanged";
type ReviewFilter = "all" | ReviewState;

type ProjectChangeItem = {
  project_id: string;
  project_name?: string;
  repo?: string;
  snapshot_status?: string;
  scanned_at?: string;
  snapshot_message?: string;
  delta_status?: string;
  from_sha?: string;
  to_sha?: string;
  commit_count?: number;
  file_count?: number;
  delta_truncated?: boolean;
  review_state?: ReviewState;
  review_reason?: string;
  last_attempted_at?: string;
  last_attempt_status?: string;
  last_succeeded_at?: string;
  last_failure_message?: string;
};

type ProjectChangeResponse = {
  generated_at?: string;
  summary?: {
    total?: number;
    needs_attention?: number;
    changed?: number;
    baseline?: number;
    unchanged?: number;
    failed?: number;
    stale?: number;
    partial?: number;
    missing?: number;
  };
  items?: ProjectChangeItem[];
  detail?: string;
};

const FILTERS: Array<{ key: ReviewFilter; label: string }> = [
  { key: "all", label: "All" },
  { key: "needs_attention", label: "Needs attention" },
  { key: "changed", label: "Changed" },
  { key: "baseline", label: "Baseline" },
  { key: "unchanged", label: "Unchanged" },
];

function clean(value: unknown): string {
  return String(value || "").trim();
}

function formatDate(value?: string): string {
  const text = clean(value);
  if (!text) return "not recorded";
  const parsed = new Date(text);
  if (Number.isNaN(parsed.getTime())) return text;
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(parsed);
}

function shortSha(value?: string): string {
  const text = clean(value);
  return text ? text.slice(0, 8) : "unavailable";
}

function reviewStateLabel(value?: ReviewState): string {
  switch (value) {
    case "needs_attention":
      return "Needs attention";
    case "changed":
      return "Changed";
    case "baseline":
      return "Initial baseline";
    case "unchanged":
      return "Unchanged";
    default:
      return "Needs attention";
  }
}

function countForFilter(response: ProjectChangeResponse | null, filter: ReviewFilter): number {
  const summary = response?.summary;
  if (filter === "all") return summary?.total || 0;
  return summary?.[filter] || 0;
}

export default function ProjectChangeReviewPage() {
  const [payload, setPayload] = useState<ProjectChangeResponse | null>(null);
  const [filter, setFilter] = useState<ReviewFilter>("all");
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    const controller = new AbortController();

    async function loadProjectChanges() {
      setLoading(true);
      setErrorMessage("");
      try {
        const response = await adminFetch(apiUrl("/projects/repo-snapshot-changes"), {
          cache: "no-store",
          signal: controller.signal,
        });
        const data = (await response.json().catch(() => null)) as ProjectChangeResponse | null;
        if (!response.ok) {
          throw new Error(data?.detail || `Failed to load Project Change Review (${response.status}).`);
        }
        if (!controller.signal.aborted) setPayload(data || { items: [] });
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") return;
        if (!controller.signal.aborted) {
          setPayload(null);
          setErrorMessage(error instanceof Error ? error.message : "Failed to load Project Change Review.");
        }
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }

    void loadProjectChanges();
    return () => controller.abort();
  }, []);

  const items = useMemo(() => payload?.items || [], [payload?.items]);
  const visibleItems = useMemo(
    () => (filter === "all" ? items : items.filter((item) => item.review_state === filter)),
    [filter, items],
  );

  return (
    <AppContainer>
      <RequireAdminAuth>
        <PageHeader
          title="Project Change Review"
          description="A read-only cross-project view of cached Snapshot health and repository delta."
          size="compact"
          marginBottom="18px"
        />

        <div style={toolbarStyle}>
          <Link href="/workspace/projects" style={primaryLinkStyle}>Back to Project Takeaways</Link>
          <Link href="/admin/projects" style={secondaryLinkStyle}>Manage Projects</Link>
          <span style={toolbarNoteStyle}>Cached snapshots only · page loads never refresh GitHub</span>
        </div>

        {loading ? <div style={emptyStyle}>Loading cached project changes...</div> : null}
        {errorMessage ? <div style={errorStyle}>{errorMessage}</div> : null}

        {!loading && !errorMessage ? (
          <div style={{ display: "grid", gap: "16px" }}>
            <section style={summaryPanelStyle}>
              <div>
                <div style={eyebrowStyle}>Cross-project observation</div>
                <h2 style={sectionTitleStyle}>What changed and what needs attention</h2>
                <p style={bodyStyle}>
                  Snapshot health and repository delta stay separate. A failed or unavailable observation is never presented as an unchanged project.
                </p>
              </div>
              <div style={summaryGridStyle}>
                <SummaryMetric label="Active connected" value={payload?.summary?.total || 0} />
                <SummaryMetric label="Needs attention" value={payload?.summary?.needs_attention || 0} tone="warning" />
                <SummaryMetric label="Changed" value={payload?.summary?.changed || 0} tone="info" />
                <SummaryMetric label="Unchanged" value={payload?.summary?.unchanged || 0} />
                <SummaryMetric label="Baseline" value={payload?.summary?.baseline || 0} />
              </div>
              <div style={metaRowStyle}>
                <span>projection generated {formatDate(payload?.generated_at)}</span>
                <span>failed {payload?.summary?.failed || 0}</span>
                <span>stale {payload?.summary?.stale || 0}</span>
                <span>partial {payload?.summary?.partial || 0}</span>
                <span>missing {payload?.summary?.missing || 0}</span>
              </div>
            </section>

            <section style={filterPanelStyle} aria-label="Project change filters">
              {FILTERS.map(({ key, label }) => {
                const active = filter === key;
                return (
                  <button
                    key={key}
                    type="button"
                    onClick={() => setFilter(key)}
                    aria-pressed={active}
                    style={{
                      ...filterButtonStyle,
                      background: active ? "var(--app-primary-action-bg)" : "var(--app-secondary-action-bg)",
                      color: active ? "var(--app-primary-action-fg)" : "var(--app-secondary-action-fg)",
                      borderColor: active ? "var(--app-primary-action-border)" : "var(--app-secondary-action-border)",
                    }}
                  >
                    {label} ({countForFilter(payload, key)})
                  </button>
                );
              })}
            </section>

            {items.length === 0 ? (
              <div style={emptyStyle}>No active connected projects have cached Snapshot review context.</div>
            ) : visibleItems.length === 0 ? (
              <div style={emptyStyle}>No projects match the selected {reviewStateLabel(filter as ReviewState).toLowerCase()} filter.</div>
            ) : (
              <section style={cardGridStyle}>
                {visibleItems.map((item) => <ProjectChangeCard key={item.project_id} item={item} />)}
              </section>
            )}

            <section style={boundaryStyle}>
              <strong>Review boundary</strong>
              <span>
                Repository change is project review context only. It does not verify claims, infer development progress, run Deep Scan, or unlock downstream actions.
              </span>
            </section>
          </div>
        ) : null}
      </RequireAdminAuth>
    </AppContainer>
  );
}

function SummaryMetric({ label, value, tone = "neutral" }: { label: string; value: number; tone?: "neutral" | "warning" | "info" }) {
  const toneStyle = tone === "warning"
    ? { borderColor: "var(--app-warning-border)", background: "var(--app-warning-bg)", color: "var(--app-warning-fg)" }
    : tone === "info"
      ? { borderColor: "var(--app-info-border)", background: "var(--app-info-bg)", color: "var(--app-info-fg)" }
      : {};
  return <div style={{ ...metricStyle, ...toneStyle }}><strong style={metricValueStyle}>{value}</strong><span>{label}</span></div>;
}

function ProjectChangeCard({ item }: { item: ProjectChangeItem }) {
  const state = item.review_state || "needs_attention";
  const stateStyle = state === "needs_attention"
    ? { borderColor: "var(--app-warning-border)", background: "var(--app-warning-bg)", color: "var(--app-warning-fg)" }
    : state === "changed"
      ? { borderColor: "var(--app-info-border)", background: "var(--app-info-bg)", color: "var(--app-info-fg)" }
      : {};
  return (
    <article style={cardStyle}>
      <div style={cardHeaderStyle}>
        <div>
          <div style={eyebrowStyle}>{item.repo || "Repository unavailable"}</div>
          <h2 style={cardTitleStyle}>{item.project_name || item.project_id}</h2>
        </div>
        <span style={{ ...stateChipStyle, ...stateStyle }}>{reviewStateLabel(state)}</span>
      </div>

      <div style={chipRowStyle}>
        <span style={chipStyle}>snapshot {item.snapshot_status || "missing"}</span>
        <span style={chipStyle}>delta {item.delta_status || "unavailable"}</span>
        <span style={chipStyle}>scanned {formatDate(item.scanned_at)}</span>
      </div>

      <div style={reasonStyle}>{item.review_reason || "No review reason was recorded."}</div>

      <div style={factGridStyle}>
        <Fact label="From" value={shortSha(item.from_sha)} />
        <Fact label="To" value={shortSha(item.to_sha)} />
        <Fact label="Commits" value={String(item.commit_count || 0)} />
        <Fact label="Files" value={String(item.file_count || 0)} />
      </div>

      {item.last_attempt_status === "failed" ? (
        <div style={failureStyle}>
          Latest refresh failed {formatDate(item.last_attempted_at)}. Last usable snapshot: {formatDate(item.last_succeeded_at)}.
        </div>
      ) : null}
      {item.delta_truncated ? <div style={truncatedStyle}>The cached delta is bounded; additional changes were omitted.</div> : null}

      <div style={cardActionsStyle}>
        <Link
          href={`/workspace/projects/intelligence?project_id=${encodeURIComponent(item.project_id)}`}
          style={secondaryLinkStyle}
        >
          Open Project Understanding
        </Link>
      </div>
    </article>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return <div style={factStyle}><span style={factLabelStyle}>{label}</span><strong>{value}</strong></div>;
}

const toolbarStyle = { display: "flex", gap: "10px", flexWrap: "wrap" as const, alignItems: "center", padding: "14px", borderRadius: "16px", border: "1px solid var(--app-surface-border)", background: "var(--app-surface-bg)", boxShadow: "var(--app-surface-shadow)", marginBottom: "16px" } as const;
const primaryLinkStyle = { display: "inline-flex", padding: "10px 14px", borderRadius: "10px", background: "var(--app-primary-action-bg)", color: "var(--app-primary-action-fg)", border: "1px solid var(--app-primary-action-border)", textDecoration: "none", fontWeight: 800 } as const;
const secondaryLinkStyle = { display: "inline-flex", padding: "9px 12px", borderRadius: "9px", background: "var(--app-secondary-action-bg)", color: "var(--app-secondary-action-fg)", border: "1px solid var(--app-secondary-action-border)", textDecoration: "none", fontWeight: 750, fontSize: "13px" } as const;
const toolbarNoteStyle = { marginLeft: "auto", color: "var(--app-text-subtle)", fontSize: "12px", fontWeight: 700 } as const;
const summaryPanelStyle = { padding: "18px", borderRadius: "16px", border: "1px solid var(--app-surface-border)", background: "var(--app-surface-bg)", boxShadow: "var(--app-surface-shadow)", display: "grid", gap: "14px" } as const;
const summaryGridStyle = { display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))", gap: "8px" } as const;
const metricStyle = { padding: "11px 12px", borderRadius: "10px", border: "1px solid var(--app-surface-border)", background: "var(--app-surface-muted-bg)", color: "var(--app-text-muted)", display: "grid", gap: "3px", fontSize: "12px" } as const;
const metricValueStyle = { color: "inherit", fontSize: "22px", lineHeight: 1 } as const;
const metaRowStyle = { display: "flex", gap: "12px", flexWrap: "wrap" as const, color: "var(--app-text-subtle)", fontSize: "12px", fontWeight: 650 } as const;
const filterPanelStyle = { display: "flex", gap: "8px", flexWrap: "wrap" as const, padding: "12px", borderRadius: "14px", border: "1px solid var(--app-surface-border)", background: "var(--app-surface-bg)" } as const;
const filterButtonStyle = { padding: "8px 11px", borderRadius: "999px", border: "1px solid", fontSize: "12px", fontWeight: 800, cursor: "pointer" } as const;
const cardGridStyle = { display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 360px), 1fr))", gap: "12px", alignItems: "start" } as const;
const cardStyle = { padding: "16px", borderRadius: "12px", border: "1px solid var(--app-surface-border)", background: "var(--app-surface-bg)", display: "grid", gap: "12px" } as const;
const cardHeaderStyle = { display: "flex", justifyContent: "space-between", gap: "12px", flexWrap: "wrap" as const, alignItems: "start" } as const;
const cardTitleStyle = { margin: "4px 0 0", color: "var(--app-text-strong)", fontSize: "18px", lineHeight: 1.3 } as const;
const stateChipStyle = { display: "inline-flex", padding: "5px 9px", borderRadius: "999px", border: "1px solid var(--app-chip-border)", background: "var(--app-chip-bg)", color: "var(--app-chip-fg)", fontSize: "12px", fontWeight: 850 } as const;
const chipRowStyle = { display: "flex", gap: "7px", flexWrap: "wrap" as const } as const;
const chipStyle = { display: "inline-flex", padding: "5px 8px", borderRadius: "999px", border: "1px solid var(--app-chip-border)", background: "var(--app-chip-bg)", color: "var(--app-chip-fg)", fontSize: "11px", fontWeight: 700 } as const;
const factGridStyle = { display: "grid", gridTemplateColumns: "repeat(4, minmax(0, 1fr))", gap: "7px" } as const;
const factStyle = { padding: "9px", borderRadius: "8px", border: "1px solid var(--app-surface-border)", background: "var(--app-surface-muted-bg)", color: "var(--app-text-strong)", display: "grid", gap: "3px", minWidth: 0, fontSize: "12px" } as const;
const factLabelStyle = { color: "var(--app-text-subtle)", fontSize: "10px", fontWeight: 850, textTransform: "uppercase" as const } as const;
const eyebrowStyle = { color: "var(--app-text-subtle)", fontSize: "11px", fontWeight: 850, textTransform: "uppercase" as const, letterSpacing: ".035em", overflowWrap: "anywhere" as const } as const;
const sectionTitleStyle = { margin: "4px 0 0", color: "var(--app-text-strong)", fontSize: "20px", lineHeight: 1.3 } as const;
const bodyStyle = { margin: "8px 0 0", color: "var(--app-text-muted)", fontSize: "13px", lineHeight: 1.65 } as const;
const reasonStyle = { color: "var(--app-text-muted)", fontSize: "13px", lineHeight: 1.6 } as const;
const failureStyle = { padding: "10px 11px", borderRadius: "9px", border: "1px solid var(--app-warning-border)", background: "var(--app-warning-bg)", color: "var(--app-warning-fg)", fontSize: "12px", lineHeight: 1.55 } as const;
const truncatedStyle = { color: "var(--app-warning-fg)", fontSize: "11px", fontWeight: 750 } as const;
const cardActionsStyle = { display: "flex", gap: "8px", flexWrap: "wrap" as const, paddingTop: "2px" } as const;
const boundaryStyle = { padding: "14px 16px", borderRadius: "12px", border: "1px solid var(--app-info-border)", background: "var(--app-info-bg)", color: "var(--app-info-fg)", display: "grid", gap: "5px", fontSize: "13px", lineHeight: 1.6 } as const;
const emptyStyle = { padding: "22px", borderRadius: "14px", border: "1px solid var(--app-surface-border)", background: "var(--app-surface-muted-bg)", color: "var(--app-text-muted)" } as const;
const errorStyle = { padding: "14px 16px", borderRadius: "12px", border: "1px solid var(--app-danger-border)", background: "var(--app-danger-bg)", color: "var(--app-danger-fg)" } as const;
