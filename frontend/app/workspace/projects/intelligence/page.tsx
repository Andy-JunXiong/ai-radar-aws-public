"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import AppContainer from "@/components/AppContainer";
import PageHeader from "@/components/PageHeader";
import RequireAdminAuth from "@/components/RequireAdminAuth";
import { adminFetch } from "@/lib/adminAuth";
import { apiUrl } from "@/lib/api";

type ProjectItem = {
  project_id: string;
  name?: string;
  description?: string;
  status?: string;
  repo?: string;
  current_state?: string;
  roadmap?: string;
  topics?: string[];
};

type SnapshotAnchor = {
  kind?: string;
  path?: string;
  required?: boolean;
  content_mode?: string;
  found?: boolean;
  error?: string;
  excerpt?: string;
  html_url?: string;
  development_sections?: Partial<Record<DevelopmentSectionKey, string>>;
  development_sections_truncated?: DevelopmentSectionKey[];
  source_last_updated?: string;
};

type DevelopmentStateKey = "completed" | "in_progress" | "blocked" | "next_up";
type DevelopmentSectionKey = DevelopmentStateKey | "active_plan";

type DevelopmentRealityEntry = {
  value: string;
  path: string;
  truncated: boolean;
  sourceLastUpdated: string;
};

type SnapshotCommit = {
  sha?: string;
  message?: string;
  committed_at?: string;
  html_url?: string;
};

type SnapshotFile = {
  path?: string;
  previous_path?: string;
  status?: string;
  additions?: number;
  deletions?: number;
  changes?: number;
  html_url?: string;
};

type ProjectRepoSnapshot = {
  schema_version?: number;
  status?: string;
  repo?: string;
  scanned_at?: string;
  message?: string;
  summary?: string;
  readme_found?: boolean;
  readme_path?: string;
  roadmap_found?: boolean;
  roadmap_path?: string;
  architecture_hints?: string[];
  keywords?: string[];
  manifests?: Array<{ path?: string }>;
  recent_commits?: SnapshotCommit[];
  anchors?: SnapshotAnchor[];
  discovery?: {
    mode?: string;
    config_status?: string;
    config_errors?: Array<{ path?: string; message?: string }>;
  };
  observation?: {
    head?: { sha?: string; branch?: string; committed_at?: string; scanned_at?: string } | null;
    baseline?: { sha?: string; branch?: string; committed_at?: string; scanned_at?: string } | null;
  };
  interpretation?: {
    method?: string;
    summary?: string;
    architecture_hints?: string[];
    keywords?: string[];
  };
  delta?: {
    status?: string;
    from_sha?: string;
    to_sha?: string;
    total_commits?: number;
    commits?: SnapshotCommit[];
    files?: SnapshotFile[];
    truncated?: boolean;
    message?: string;
  };
  refresh?: {
    last_attempted_at?: string;
    last_attempt_status?: string;
    last_succeeded_at?: string;
    last_failure?: { at?: string; message?: string } | null;
  };
};

type ProjectIntelligenceResponse = {
  project?: ProjectItem;
  repo_snapshot?: ProjectRepoSnapshot;
  detail?: string;
};

function clean(value?: string) {
  return (value || "").trim();
}

function shortSha(value?: string) {
  const normalized = clean(value);
  return normalized ? normalized.slice(0, 8) : "unavailable";
}

function formatDate(value?: string) {
  const normalized = clean(value);
  if (!normalized) return "not recorded";
  const parsed = new Date(normalized);
  return Number.isNaN(parsed.getTime()) ? normalized : parsed.toLocaleString();
}

function snapshotStatusLabel(value?: string) {
  switch (clean(value).toLowerCase()) {
    case "fresh":
      return "Fresh";
    case "partial":
      return "Partial";
    case "stale":
      return "Stale";
    case "failed":
      return "Failed";
    case "not_connected":
      return "Not connected";
    case "missing":
      return "Missing";
    default:
      return "Unavailable";
  }
}

function projectStatusLabel(value?: string) {
  return clean(value).replaceAll("_", " ") || "planning";
}

function discoveryLabel(snapshot?: ProjectRepoSnapshot | null) {
  if (snapshot?.discovery?.config_status === "invalid") return "Truth Map invalid";
  if (snapshot?.discovery?.mode === "configured") return "Configured Truth Map";
  return "Heuristic discovery";
}

function statusNoticeStyle(status?: string) {
  const normalized = clean(status).toLowerCase();
  if (normalized === "failed" || normalized === "missing" || normalized === "not_connected") {
    return { border: "1px solid var(--app-danger-border)", background: "var(--app-danger-bg)", color: "var(--app-danger-fg)" };
  }
  if (normalized === "partial" || normalized === "stale") {
    return { border: "1px solid var(--app-warning-border)", background: "var(--app-warning-bg)", color: "var(--app-warning-fg)" };
  }
  return { border: "1px solid var(--app-info-border)", background: "var(--app-info-bg)", color: "var(--app-info-fg)" };
}

const DEVELOPMENT_SECTION_LABELS: Array<{ key: DevelopmentStateKey; label: string }> = [
  { key: "completed", label: "Completed" },
  { key: "in_progress", label: "In progress" },
  { key: "blocked", label: "Blocked" },
  { key: "next_up", label: "Next up" },
];

const DEVELOPMENT_SOURCE_KINDS = new Set(["current_state", "development_plan", "roadmap"]);

function developmentRealityFromAnchors(anchors: SnapshotAnchor[]) {
  const result: Partial<Record<DevelopmentStateKey, DevelopmentRealityEntry>> = {};
  for (const anchor of anchors) {
    if (!anchor.found || !DEVELOPMENT_SOURCE_KINDS.has(clean(anchor.kind))) continue;
    for (const { key } of DEVELOPMENT_SECTION_LABELS) {
      const value = clean(anchor.development_sections?.[key]);
      if (!value || result[key]) continue;
      result[key] = {
        value,
        path: clean(anchor.path) || "Path unavailable",
        truncated: Boolean(anchor.development_sections_truncated?.includes(key)),
        sourceLastUpdated: clean(anchor.source_last_updated),
      };
    }
  }
  return result;
}

function activePlanFromAnchors(anchors: SnapshotAnchor[]): DevelopmentRealityEntry | undefined {
  for (const anchor of anchors) {
    if (!anchor.found || clean(anchor.kind) !== "development_plan") continue;
    const value = clean(anchor.development_sections?.active_plan);
    if (!value) continue;
    return {
      value,
      path: clean(anchor.path) || "Path unavailable",
      truncated: Boolean(anchor.development_sections_truncated?.includes("active_plan")),
      sourceLastUpdated: clean(anchor.source_last_updated),
    };
  }
  return undefined;
}

function cleanDevelopmentItem(value: string) {
  return value
    .replace(/^#{1,6}\s+/, "")
    .replace(/^\s*[-*+]\s+/, "")
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/__([^_]+)__/g, "$1")
    .replace(/\s+/g, " ")
    .trim();
}

function markdownTableItems(lines: string[]) {
  const tableLines = lines.filter((line) => line.startsWith("|") && line.includes("|", 1));
  const result: string[] = [];
  for (let index = 0; index < tableLines.length; index += 1) {
    const cells = tableLines[index]
      .replace(/^\|/, "")
      .replace(/\|$/, "")
      .split("|")
      .map((cell) => cleanDevelopmentItem(cell))
      .filter(Boolean);
    if (!cells.length) continue;
    const isSeparator = cells.every((cell) => /^:?-{3,}:?$/.test(cell.replace(/\s+/g, "")));
    if (isSeparator) continue;
    const nextLine = tableLines[index + 1] || "";
    const nextCells = nextLine
      .replace(/^\|/, "")
      .replace(/\|$/, "")
      .split("|")
      .map((cell) => cell.trim())
      .filter(Boolean);
    const nextIsSeparator = nextCells.length > 0 && nextCells.every((cell) => /^:?-{3,}:?$/.test(cell.replace(/\s+/g, "")));
    if (nextIsSeparator) continue;
    const item = cells.slice(0, 2).join(" — ");
    if (item && !result.includes(item)) result.push(item);
  }
  return result;
}

function compactDevelopmentItems(value: string) {
  const lines = value.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
  const headings = lines.filter((line) => /^#{1,6}\s+/.test(line));
  const bullets = lines.filter((line) => /^[-*+]\s+/.test(line));
  const tableItems = markdownTableItems(lines);
  const candidates = headings.length ? headings : bullets.length ? bullets : tableItems.length ? tableItems : lines;
  const items: string[] = [];
  for (const candidate of candidates) {
    const cleaned = cleanDevelopmentItem(candidate);
    if (!cleaned || items.includes(cleaned)) continue;
    items.push(cleaned);
    if (items.length === 5) break;
  }
  return items;
}

export default function ProjectUnderstandingPreviewPage() {
  const searchParams = useSearchParams();
  const projectId = clean(searchParams.get("project_id") || "");
  const [project, setProject] = useState<ProjectItem | null>(null);
  const [snapshot, setSnapshot] = useState<ProjectRepoSnapshot | null>(null);
  const [loading, setLoading] = useState(Boolean(projectId));
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    if (!projectId) {
      setProject(null);
      setSnapshot(null);
      setLoading(false);
      setErrorMessage("Select a project from Admin Projects before opening Project Understanding.");
      return;
    }

    const controller = new AbortController();

    async function loadProjectIntelligence() {
      setLoading(true);
      setErrorMessage("");
      try {
        const response = await adminFetch(apiUrl(`/projects/${encodeURIComponent(projectId)}/repo-snapshot`), {
          cache: "no-store",
          signal: controller.signal,
        });
        const data = (await response.json().catch(() => null)) as ProjectIntelligenceResponse | null;
        if (!response.ok) {
          throw new Error(data?.detail || `Failed to load project understanding (${response.status}).`);
        }
        if (!controller.signal.aborted) {
          setProject(data?.project || null);
          setSnapshot(data?.repo_snapshot || null);
        }
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") return;
        if (!controller.signal.aborted) {
          setProject(null);
          setSnapshot(null);
          setErrorMessage(error instanceof Error ? error.message : "Failed to load project understanding.");
        }
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }

    void loadProjectIntelligence();
    return () => controller.abort();
  }, [projectId]);

  const summary = clean(snapshot?.interpretation?.summary) || clean(snapshot?.summary) || clean(project?.description);
  const architectureHints = snapshot?.interpretation?.architecture_hints?.length
    ? snapshot.interpretation.architecture_hints
    : snapshot?.architecture_hints || [];
  const keywords = snapshot?.interpretation?.keywords?.length
    ? snapshot.interpretation.keywords
    : snapshot?.keywords || [];
  const anchors = snapshot?.anchors || [];
  const foundAnchors = anchors.filter((anchor) => anchor.found).length;
  const developmentAnchors = anchors.filter((anchor) => DEVELOPMENT_SOURCE_KINDS.has(clean(anchor.kind)));
  const developmentReality = developmentRealityFromAnchors(developmentAnchors);
  const activePlan = activePlanFromAnchors(developmentAnchors);
  const reportedDevelopmentSections = DEVELOPMENT_SECTION_LABELS.filter(({ key }) => developmentReality[key]).length;
  const hasCurrentStateAnchor = developmentAnchors.some((anchor) => clean(anchor.kind) === "current_state");
  const hasDevelopmentPlanAnchor = developmentAnchors.some((anchor) => clean(anchor.kind) === "development_plan");
  const deltaCommits = snapshot?.delta?.commits || [];
  const deltaFiles = snapshot?.delta?.files || [];
  const returnHref = projectId
    ? `/workspace/projects?project_id=${encodeURIComponent(projectId)}`
    : "/workspace/projects";
  const title = useMemo(() => clean(project?.name) || clean(project?.project_id) || "Project Understanding", [project]);

  return (
    <AppContainer>
      <RequireAdminAuth>
        <PageHeader
          title={title}
          description="A read-only preview of saved project context and the latest bounded repository snapshot."
          size="compact"
          marginBottom="18px"
        />

        <div style={toolbarStyle}>
          <Link href={returnHref} style={primaryLinkStyle}>Back to Project Takeaways</Link>
          <Link href="/workspace/projects/changes" style={secondaryLinkStyle}>Review Project Changes</Link>
          <Link href="/admin/projects" style={secondaryLinkStyle}>Manage Projects</Link>
          <span style={toolbarNoteStyle}>Cached snapshot · page loads never refresh GitHub</span>
        </div>

        {loading ? <div style={emptyStyle}>Loading cached project understanding...</div> : null}
        {errorMessage ? <div style={errorStyle}>{errorMessage}</div> : null}

        {!loading && !errorMessage && project ? (
          <div style={{ display: "grid", gap: "16px" }}>
            <section style={panelStyle}>
              <div style={sectionEyebrowStyle}>Project identity</div>
              <div style={chipRowStyle}>
                <span style={chipStyle}>{projectStatusLabel(project.status)}</span>
                <span style={chipStyle}>{project.project_id}</span>
                {(project.topics || []).map((topic) => <span key={topic} style={chipStyle}>{topic}</span>)}
              </div>
              <div style={summaryStyle}>{summary || "No project description or repository summary is available."}</div>
            </section>

            <section style={{ ...statusPanelStyle, ...statusNoticeStyle(snapshot?.status) }}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: "12px", flexWrap: "wrap" }}>
                <strong>Snapshot {snapshotStatusLabel(snapshot?.status)}</strong>
                <span>scanned {formatDate(snapshot?.scanned_at)}</span>
              </div>
              <div>{snapshot?.message || "No snapshot status message is available."}</div>
            </section>

            {snapshot?.refresh?.last_attempt_status === "failed" ? (
              <section style={{ ...statusPanelStyle, borderColor: "#f59e0b", background: "#fffbeb", color: "#92400e" }}>
                <strong>Latest Light Snapshot refresh failed</strong>
                <div>
                  Attempted {formatDate(snapshot.refresh.last_attempted_at)}. {snapshot.refresh.last_failure?.message || "No failure detail was recorded."}
                </div>
                <div>Showing the last successful snapshot from {formatDate(snapshot.refresh.last_succeeded_at || snapshot.scanned_at)}.</div>
              </section>
            ) : null}

            <div style={twoColumnStyle}>
              <section style={panelStyle}>
                <div style={sectionEyebrowStyle}>Observation</div>
                <h2 style={sectionTitleStyle}>Repository state</h2>
                <div style={chipRowStyle}>
                  <span style={chipStyle}>{snapshot?.repo || project.repo || "No repository"}</span>
                  <span style={chipStyle}>snapshot v{snapshot?.schema_version || "?"}</span>
                  <span style={chipStyle}>{discoveryLabel(snapshot)}</span>
                  <span style={chipStyle}>head {shortSha(snapshot?.observation?.head?.sha)}</span>
                  <span style={chipStyle}>baseline {shortSha(snapshot?.observation?.baseline?.sha)}</span>
                  <span style={chipStyle}>delta {snapshot?.delta?.status || "unavailable"}</span>
                </div>
                <div style={coverageGridStyle}>
                  <CoverageItem label="README" value={snapshot?.readme_found ? snapshot.readme_path || "found" : "missing"} />
                  <CoverageItem label="Roadmap" value={snapshot?.roadmap_found ? snapshot.roadmap_path || "found" : "missing"} />
                  <CoverageItem label="Manifests" value={String(snapshot?.manifests?.length || 0)} />
                  <CoverageItem label="Recent commits" value={String(snapshot?.recent_commits?.length || 0)} />
                  <CoverageItem label="Truth anchors" value={anchors.length ? `${foundAnchors}/${anchors.length} found` : "not configured"} />
                  <CoverageItem label="Branch" value={snapshot?.observation?.head?.branch || "unavailable"} />
                </div>
              </section>

              <section style={panelStyle}>
                <div style={sectionEyebrowStyle}>Deterministic interpretation</div>
                <h2 style={sectionTitleStyle}>Project shape</h2>
                <p style={bodyTextStyle}>{summary || "No deterministic summary is available."}</p>
                <div style={labelStyle}>Architecture hints</div>
                <div style={chipRowStyle}>
                  {architectureHints.length
                    ? architectureHints.map((hint) => <span key={hint} style={chipStyle}>{hint}</span>)
                    : <span style={mutedTextStyle}>No architecture hints observed.</span>}
                </div>
                {keywords.length ? (
                  <>
                    <div style={labelStyle}>Context keywords</div>
                    <div style={chipRowStyle}>{keywords.slice(0, 12).map((keyword) => <span key={keyword} style={chipStyle}>{keyword}</span>)}</div>
                  </>
                ) : null}
              </section>
            </div>

            <section style={panelStyle}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: "12px", flexWrap: "wrap", alignItems: "start" }}>
                <div style={{ display: "grid", gap: "7px" }}>
                  <div style={sectionEyebrowStyle}>Source-reported development reality</div>
                  <h2 style={sectionTitleStyle}>What is developed, active, blocked, and next</h2>
                </div>
                <span style={chipStyle}>snapshot {formatDate(snapshot?.scanned_at)}</span>
              </div>
              <p style={bodyTextStyle}>
                These states come only from configured repository status sources. Commit counts and unchanged deltas do not determine development state.
              </p>

              {!hasCurrentStateAnchor || !hasDevelopmentPlanAnchor ? (
                <div style={developmentSetupStyle}>
                  <strong>Development source coverage is incomplete.</strong>
                  <span>
                    In Manage Projects, configure excerpt anchors with kind <code>current_state</code> and <code>development_plan</code>, save changes, then refresh the light snapshot.
                  </span>
                  <Link href="/admin/projects" style={inlineLinkStyle}>Manage project sources</Link>
                </div>
              ) : null}

              {developmentAnchors.length > 0 && reportedDevelopmentSections === 0 ? (
                <div style={developmentUnknownStyle}>
                  Configured development sources were observed, but they did not report recognized Completed, In Progress, Blocked, or Next Up Markdown sections.
                </div>
              ) : null}

              <div style={developmentGridStyle}>
                {DEVELOPMENT_SECTION_LABELS.map(({ key, label }) => (
                  <DevelopmentRealityCard key={key} label={label} entry={developmentReality[key]} />
                ))}
              </div>

              <div style={activePlanStyle}>
                <div style={labelStyle}>Active plan</div>
                {activePlan ? (
                  <DevelopmentRealityContent entry={activePlan} />
                ) : (
                  <div style={mutedTextStyle}>Unknown — the configured development plan did not report a recognized Active Plan or Current P0 Track section.</div>
                )}
              </div>
            </section>

            <section style={panelStyle}>
              <div style={sectionEyebrowStyle}>Operator-owned project context</div>
              <h2 style={sectionTitleStyle}>Saved situation and roadmap</h2>
              <p style={bodyTextStyle}>Operator notes are shown separately and do not overwrite repository observations.</p>
              <div style={twoColumnStyle}>
                <ContextBlock label="Current project situation" value={project.current_state} empty="No current situation has been saved." />
                <ContextBlock label="Manual roadmap" value={project.roadmap} empty="No manual roadmap has been saved." />
              </div>
            </section>

            <section style={panelStyle}>
              <div style={sectionEyebrowStyle}>Observed repository delta</div>
              <div style={{ display: "flex", justifyContent: "space-between", gap: "12px", flexWrap: "wrap", alignItems: "center" }}>
                <h2 style={sectionTitleStyle}>Changes since baseline</h2>
                <span style={chipStyle}>{shortSha(snapshot?.delta?.from_sha)} → {shortSha(snapshot?.delta?.to_sha)}</span>
              </div>
              <p style={bodyTextStyle}>{snapshot?.delta?.message || "No bounded delta is available."}</p>
              {snapshot?.delta?.status === "changed" ? (
                <div style={deltaGridStyle}>
                  <DeltaList title={`Commits (${snapshot.delta.total_commits ?? deltaCommits.length})`} items={deltaCommits.map((commit) => `${shortSha(commit.sha)} · ${clean(commit.message) || "Message unavailable"}`)} />
                  <DeltaList title={`Files (${deltaFiles.length})`} items={deltaFiles.map((file) => `${clean(file.status) || "changed"} · ${clean(file.path) || "Path unavailable"}${typeof file.changes === "number" ? ` · ${file.changes} lines` : ""}`)} />
                </div>
              ) : null}
              {snapshot?.delta?.truncated ? <div style={warningTextStyle}>The cached delta is bounded; additional changes were omitted.</div> : null}
            </section>

            {anchors.length ? (
              <section style={panelStyle}>
                <div style={sectionEyebrowStyle}>Configured source coverage</div>
                <h2 style={sectionTitleStyle}>Truth Map anchors</h2>
                <div style={{ display: "grid", gap: "8px" }}>
                  {anchors.map((anchor, index) => (
                    <div key={`${anchor.path || "anchor"}-${index}`} style={anchorRowStyle}>
                      <strong>{anchor.kind || "anchor"}</strong>
                      <span>{anchor.path || "Path unavailable"}</span>
                      <span style={chipStyle}>{anchor.required ? "required" : "optional"}</span>
                      <span style={chipStyle}>{anchor.found ? "found" : anchor.error || "missing"}</span>
                    </div>
                  ))}
                </div>
              </section>
            ) : null}

            <section style={boundaryStyle}>
              <strong>Evidence boundary</strong>
              <span>Repository context is project review context only. It does not verify external claims or unlock downstream actions.</span>
            </section>
          </div>
        ) : null}
      </RequireAdminAuth>
    </AppContainer>
  );
}

function CoverageItem({ label, value }: { label: string; value: string }) {
  return <div style={coverageItemStyle}><span style={metricLabelStyle}>{label}</span><strong>{value}</strong></div>;
}

function ContextBlock({ label, value, empty }: { label: string; value?: string; empty: string }) {
  return <div style={contextBlockStyle}><div style={labelStyle}>{label}</div><div style={bodyTextStyle}>{clean(value) || empty}</div></div>;
}

function DevelopmentRealityCard({ label, entry }: { label: string; entry?: DevelopmentRealityEntry }) {
  return (
    <div style={developmentCardStyle}>
      <div style={labelStyle}>{label}</div>
      {entry ? (
        <DevelopmentRealityContent entry={entry} />
      ) : (
        <div style={mutedTextStyle}>Unknown — no configured source reported this state.</div>
      )}
    </div>
  );
}

function DevelopmentRealityContent({ entry }: { entry: DevelopmentRealityEntry }) {
  const items = compactDevelopmentItems(entry.value);
  return (
    <>
      <ul style={developmentSummaryListStyle}>
        {items.map((item) => <li key={item}>{item}</li>)}
      </ul>
      <details style={developmentDetailsStyle}>
        <summary style={developmentSummaryStyle}>View source details</summary>
        <div style={developmentRawDetailStyle}>{entry.value}</div>
      </details>
      <div style={developmentSourceStyle}>
        Repository source · {entry.path}
        {entry.sourceLastUpdated ? ` · source updated ${entry.sourceLastUpdated}` : " · source update not reported"}
        {entry.truncated ? " · bounded excerpt" : ""}
      </div>
    </>
  );
}

function DeltaList({ title, items }: { title: string; items: string[] }) {
  const visibleItems = items.slice(0, 6);
  const hiddenItems = items.slice(6);
  return (
    <div style={deltaListStyle}>
      <div style={labelStyle}>{title}</div>
      {visibleItems.length ? visibleItems.map((item, index) => <div key={`${item}-${index}`} style={deltaRowStyle}>{item}</div>) : <div style={mutedTextStyle}>No cached items.</div>}
      {hiddenItems.length ? (
        <details style={deltaDetailsStyle}>
          <summary style={deltaSummaryStyle}>View {hiddenItems.length} more</summary>
          <div style={deltaHiddenListStyle}>
            {hiddenItems.map((item, index) => <div key={`${item}-${index + visibleItems.length}`} style={deltaRowStyle}>{item}</div>)}
          </div>
        </details>
      ) : null}
    </div>
  );
}

const toolbarStyle = { display: "flex", gap: "10px", flexWrap: "wrap" as const, alignItems: "center", padding: "14px", borderRadius: "16px", border: "1px solid var(--app-surface-border)", background: "var(--app-surface-bg)", boxShadow: "var(--app-surface-shadow)", marginBottom: "16px" } as const;
const primaryLinkStyle = { display: "inline-flex", padding: "10px 14px", borderRadius: "10px", background: "var(--app-primary-action-bg)", color: "var(--app-primary-action-fg)", border: "1px solid var(--app-primary-action-border)", textDecoration: "none", fontWeight: 800 } as const;
const secondaryLinkStyle = { display: "inline-flex", padding: "10px 14px", borderRadius: "10px", background: "var(--app-secondary-action-bg)", color: "var(--app-secondary-action-fg)", border: "1px solid var(--app-secondary-action-border)", textDecoration: "none", fontWeight: 700 } as const;
const toolbarNoteStyle = { marginLeft: "auto", color: "var(--app-text-subtle)", fontSize: "12px", fontWeight: 700 } as const;
const panelStyle = { padding: "18px", borderRadius: "16px", border: "1px solid var(--app-surface-border)", background: "var(--app-surface-bg)", boxShadow: "var(--app-surface-shadow)", display: "grid", gap: "12px" } as const;
const statusPanelStyle = { padding: "12px 14px", borderRadius: "12px", display: "grid", gap: "6px", fontSize: "13px", lineHeight: 1.6 } as const;
const sectionEyebrowStyle = { color: "var(--app-text-subtle)", fontSize: "12px", fontWeight: 900, textTransform: "uppercase" as const, letterSpacing: ".04em" } as const;
const sectionTitleStyle = { margin: 0, color: "var(--app-text-strong)", fontSize: "19px", lineHeight: 1.25 } as const;
const summaryStyle = { padding: "14px", borderRadius: "12px", background: "var(--app-surface-muted-bg)", border: "1px solid var(--app-surface-border)", color: "var(--app-text-strong)", fontSize: "16px", lineHeight: 1.7, fontWeight: 650 } as const;
const twoColumnStyle = { display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: "16px" } as const;
const deltaGridStyle = { ...twoColumnStyle, alignItems: "start" } as const;
const chipRowStyle = { display: "flex", gap: "8px", flexWrap: "wrap" as const, alignItems: "center" } as const;
const chipStyle = { display: "inline-flex", alignItems: "center", padding: "5px 9px", borderRadius: "999px", border: "1px solid var(--app-chip-border)", background: "var(--app-chip-bg)", color: "var(--app-chip-fg)", fontSize: "12px", fontWeight: 700 } as const;
const coverageGridStyle = { display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: "8px" } as const;
const coverageItemStyle = { padding: "10px 12px", borderRadius: "10px", background: "var(--app-surface-muted-bg)", border: "1px solid var(--app-surface-border)", display: "grid", gap: "4px", color: "var(--app-text-strong)", fontSize: "13px" } as const;
const metricLabelStyle = { color: "var(--app-text-subtle)", fontSize: "11px", fontWeight: 800, textTransform: "uppercase" as const } as const;
const labelStyle = { color: "var(--app-text-subtle)", fontSize: "12px", fontWeight: 800, textTransform: "uppercase" as const, marginTop: "4px" } as const;
const bodyTextStyle = { margin: 0, color: "var(--app-text-muted)", fontSize: "14px", lineHeight: 1.7, whiteSpace: "pre-wrap" as const } as const;
const mutedTextStyle = { color: "var(--app-text-subtle)", fontSize: "13px", lineHeight: 1.6 } as const;
const contextBlockStyle = { padding: "12px", borderRadius: "12px", background: "var(--app-surface-muted-bg)", border: "1px solid var(--app-surface-border)", display: "grid", gap: "8px" } as const;
const developmentGridStyle = { display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 420px), 1fr))", gap: "10px", alignItems: "start" } as const;
const developmentCardStyle = { padding: "13px", borderRadius: "12px", background: "var(--app-surface-muted-bg)", border: "1px solid var(--app-surface-border)", display: "grid", gap: "8px", alignContent: "start" } as const;
const activePlanStyle = { padding: "13px", borderRadius: "12px", background: "var(--app-surface-muted-bg)", border: "1px solid var(--app-surface-border)", display: "grid", gap: "8px" } as const;
const developmentSummaryListStyle = { margin: 0, paddingLeft: "20px", display: "grid", gap: "6px", color: "var(--app-text-muted)", fontSize: "14px", lineHeight: 1.55 } as const;
const developmentDetailsStyle = { borderTop: "1px solid var(--app-surface-border)", paddingTop: "8px" } as const;
const developmentSummaryStyle = { cursor: "pointer", color: "var(--app-text-muted)", fontSize: "12px", fontWeight: 800 } as const;
const developmentRawDetailStyle = { marginTop: "10px", maxHeight: "320px", overflow: "auto", whiteSpace: "pre-wrap" as const, color: "var(--app-text-muted)", fontSize: "12px", lineHeight: 1.6 } as const;
const developmentSourceStyle = { paddingTop: "8px", borderTop: "1px solid var(--app-surface-border)", color: "var(--app-text-subtle)", fontSize: "11px", fontWeight: 700, lineHeight: 1.5 } as const;
const developmentSetupStyle = { padding: "12px 14px", borderRadius: "12px", border: "1px solid var(--app-warning-border)", background: "var(--app-warning-bg)", color: "var(--app-warning-fg)", display: "grid", gap: "6px", fontSize: "13px", lineHeight: 1.6 } as const;
const developmentUnknownStyle = { padding: "11px 13px", borderRadius: "10px", border: "1px solid var(--app-info-border)", background: "var(--app-info-bg)", color: "var(--app-info-fg)", fontSize: "13px", lineHeight: 1.6 } as const;
const inlineLinkStyle = { color: "inherit", fontWeight: 800, textDecoration: "underline", justifySelf: "start" } as const;
const deltaRowStyle = { borderTop: "1px solid var(--app-surface-border)", paddingTop: "7px", color: "var(--app-text-muted)", fontSize: "13px", lineHeight: 1.5 } as const;
const deltaListStyle = { ...contextBlockStyle, alignSelf: "start" } as const;
const deltaDetailsStyle = { borderTop: "1px solid var(--app-surface-border)", paddingTop: "8px" } as const;
const deltaSummaryStyle = { cursor: "pointer", color: "var(--app-text-muted)", fontSize: "12px", fontWeight: 800 } as const;
const deltaHiddenListStyle = { display: "grid", gap: "7px", marginTop: "8px" } as const;
const warningTextStyle = { color: "var(--app-warning-fg)", fontSize: "12px", fontWeight: 700 } as const;
const anchorRowStyle = { display: "flex", gap: "8px", flexWrap: "wrap" as const, alignItems: "center", paddingTop: "8px", borderTop: "1px solid var(--app-surface-border)", color: "var(--app-text-muted)", fontSize: "13px" } as const;
const boundaryStyle = { padding: "14px 16px", borderRadius: "12px", border: "1px solid var(--app-info-border)", background: "var(--app-info-bg)", color: "var(--app-info-fg)", display: "grid", gap: "5px", fontSize: "13px", lineHeight: 1.6 } as const;
const emptyStyle = { padding: "24px", borderRadius: "14px", border: "1px solid var(--app-surface-border)", background: "var(--app-surface-muted-bg)", color: "var(--app-text-muted)" } as const;
const errorStyle = { padding: "14px 16px", borderRadius: "12px", border: "1px solid var(--app-danger-border)", background: "var(--app-danger-bg)", color: "var(--app-danger-fg)" } as const;
