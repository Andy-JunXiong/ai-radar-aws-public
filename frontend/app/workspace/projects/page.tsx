"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";

import AppContainer from "@/components/AppContainer";
import PageHeader from "@/components/PageHeader";
import { apiUrl } from "@/lib/api";
import { adminFetch } from "@/lib/adminAuth";

type ProjectItem = {
  project_id: string;
  name?: string;
  description?: string;
  status?: string;
  repo?: string;
  enabled?: boolean;
  current_state?: string;
  roadmap?: string;
  topics?: string[];
};

type GithubIssue = {
  number?: number;
  title?: string;
  html_url?: string;
  state?: string;
  labels?: string[];
};

type GithubDocument = {
  path?: string;
  html_url?: string;
  content?: string;
  sha?: string;
};

type GithubContext = {
  status?: string;
  repo?: string;
  repository?: {
    full_name?: string;
    description?: string;
    default_branch?: string;
    html_url?: string;
    open_issues_count?: number;
    updated_at?: string;
  } | null;
  readme?: GithubDocument | null;
  roadmap?: GithubDocument | null;
  issues?: GithubIssue[];
  message?: string;
};

type ProjectImprovementItem = {
  signal_id?: string;
  signal_title?: string;
  signal_summary?: string;
  takeaway?: string;
  why_it_matters?: string;
  fit_reason?: string;
  benefits?: string;
  final_reflection?: string;
  status?: string;
  suggested_stage?: string;
  roadmap_update_suggestion?: string;
  score?: number;
  should_apply?: boolean;
  saved_at?: string;
  confirmed_at?: string;
};

type WorkspaceViewRow = {
  project: ProjectItem;
  improvement_count?: number;
  confirmed_count?: number;
  latest_improvement?: ProjectImprovementItem | null;
};

type WorkspaceViewResponse = {
  items?: WorkspaceViewRow[];
};

type ProjectContextResponse = {
  project?: ProjectItem;
  github?: GithubContext;
  cache?: {
    repo?: string;
    fetched_at?: string;
  };
};

type ProjectImprovementsResponse = {
  items?: ProjectImprovementItem[];
  updated_at?: string;
};

function truncateText(value?: string, limit = 1400): string {
  const text = (value || "").trim();
  if (!text) return "";
  if (text.length <= limit) return text;
  return `${text.slice(0, limit)}\n\n...`;
}

function readableStatus(value?: string) {
  const normalized = (value || "").trim().toLowerCase();
  switch (normalized) {
    case "active":
      return "Active";
    case "on_hold":
      return "On Hold";
    case "completed":
      return "Completed";
    case "archived":
      return "Archived";
    case "planning":
    default:
      return "Planning";
  }
}

function renderGithubStatusChip(status?: string) {
  switch ((status || "").trim()) {
    case "loaded":
      return "loaded";
    case "rate_limited":
      return "rate limited";
    case "missing_roadmap":
      return "missing roadmap";
    case "unreachable":
      return "not reachable";
    case "no_repo":
    default:
      return "not connected";
  }
}

function formatScore(value?: number) {
  if (typeof value !== "number" || Number.isNaN(value)) return "n/a";
  return `${Math.max(0, Math.min(100, Math.round(value)))}/100`;
}

export default function ProjectTakeawaysPage() {
  const searchParams = useSearchParams();
  const requestedProjectId = (searchParams.get("project_id") || "").trim();
  const [rows, setRows] = useState<WorkspaceViewRow[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState("");
  const [project, setProject] = useState<ProjectItem | null>(null);
  const [github, setGithub] = useState<GithubContext | null>(null);
  const [cacheInfo, setCacheInfo] = useState<{ repo?: string; fetched_at?: string } | null>(null);
  const [improvements, setImprovements] = useState<ProjectImprovementItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [githubRefreshing, setGithubRefreshing] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [actionMessage, setActionMessage] = useState("");
  const [actionMessageBySignalId, setActionMessageBySignalId] = useState<Record<string, string>>({});
  const [actionErrorBySignalId, setActionErrorBySignalId] = useState<Record<string, string>>({});
  const [confirmingSignalId, setConfirmingSignalId] = useState("");
  const [openDocument, setOpenDocument] = useState<null | "readme" | "roadmap">(null);

  useEffect(() => {
    async function loadWorkspaceProjects() {
      setLoading(true);
      setErrorMessage("");
      try {
        const response = await fetch(apiUrl("/projects/workspace-view"), { cache: "no-store" });
        const data = (await response.json().catch(() => null)) as WorkspaceViewResponse | null;
        const items = data?.items ?? [];
        setRows(items);
        const requestedProject = items.find((item) => item.project.project_id === requestedProjectId);
        const fallbackProjectId = items[0]?.project?.project_id || "";
        const nextProjectId = requestedProject?.project.project_id || fallbackProjectId;
        if (nextProjectId) {
          setSelectedProjectId((current) => requestedProject?.project.project_id || current || nextProjectId);
        }
      } catch (error) {
        setRows([]);
        setErrorMessage(error instanceof Error ? error.message : "Failed to load project workspace view.");
      } finally {
        setLoading(false);
      }
    }

    void loadWorkspaceProjects();
  }, [requestedProjectId]);

  useEffect(() => {
    if (!selectedProjectId) return;

    const controller = new AbortController();
    let detailLoaded = false;

    async function refreshGithubContextInBackground() {
      setGithubRefreshing(true);
      try {
        const refreshResponse = await adminFetch(
          apiUrl(`/projects/${encodeURIComponent(selectedProjectId)}/github-context/refresh`),
          {
            method: "POST",
            cache: "no-store",
            signal: controller.signal,
          }
        );

        const refreshData = (await refreshResponse.json().catch(() => null)) as ProjectContextResponse | null;
        if (!refreshResponse.ok || controller.signal.aborted) return;

        setProject(refreshData?.project || null);
        setGithub(refreshData?.github || null);
        setCacheInfo(refreshData?.cache || null);
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") return;
      } finally {
        if (!controller.signal.aborted) setGithubRefreshing(false);
      }
    }

    async function loadProjectDetail() {
      setDetailLoading(true);
      setGithubRefreshing(false);
      setErrorMessage("");
      try {
        const [contextResponse, improvementsResponse] = await Promise.all([
          fetch(apiUrl(`/projects/${encodeURIComponent(selectedProjectId)}/github-context`), {
            cache: "no-store",
            signal: controller.signal,
          }),
          fetch(apiUrl(`/projects/${encodeURIComponent(selectedProjectId)}/improvements`), {
            cache: "no-store",
            signal: controller.signal,
          }),
        ]);

        const contextData = (await contextResponse.json().catch(() => null)) as ProjectContextResponse | null;
        const improvementsData = (await improvementsResponse.json().catch(() => null)) as ProjectImprovementsResponse | null;

        if (!contextResponse.ok) {
          throw new Error("Failed to load project context.");
        }
        if (!improvementsResponse.ok) {
          throw new Error("Failed to load project improvements.");
        }

        setProject(contextData?.project || null);
        setGithub(contextData?.github || null);
        setCacheInfo(contextData?.cache || null);
        setImprovements(improvementsData?.items || []);
        detailLoaded = true;
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setProject(null);
        setGithub(null);
        setCacheInfo(null);
        setImprovements([]);
        setErrorMessage(error instanceof Error ? error.message : "Failed to load project detail.");
      } finally {
        if (!controller.signal.aborted) setDetailLoading(false);
      }

      if (detailLoaded && !controller.signal.aborted) {
        void refreshGithubContextInBackground();
      }
    }

    void loadProjectDetail();

    return () => controller.abort();
  }, [selectedProjectId]);

  const selectedRow = useMemo(
    () => rows.find((row) => row.project.project_id === selectedProjectId) || null,
    [rows, selectedProjectId]
  );

  async function handleConfirm(item: ProjectImprovementItem) {
    if (!selectedProjectId || !item.signal_id) return;
    const signalId = item.signal_id;

    setConfirmingSignalId(signalId);
    setErrorMessage("");
    setActionMessage("");
    setActionMessageBySignalId((current) => ({ ...current, [signalId]: "" }));
    setActionErrorBySignalId((current) => ({ ...current, [signalId]: "" }));

    try {
      const response = await adminFetch(
        apiUrl(`/projects/${encodeURIComponent(selectedProjectId)}/improvements/${encodeURIComponent(signalId)}/confirm`),
        { method: "POST" }
      );
      const data = (await response.json().catch(() => null)) as { item?: ProjectImprovementItem; detail?: string } | null;
      if (!response.ok) {
        throw new Error(data?.detail || `Failed to confirm project improvement (${response.status})`);
      }

      setImprovements((current) =>
        current.map((row) =>
          row.signal_id === item.signal_id
            ? { ...row, ...(data?.item || {}), status: "confirmed" }
            : row
        )
      );
      setRows((current) =>
        current.map((row) =>
          row.project.project_id === selectedProjectId
            ? {
                ...row,
                confirmed_count: (row.confirmed_count || 0) + (item.status === "confirmed" ? 0 : 1),
              }
            : row
        )
      );
      const message = `${item.signal_title || "Project takeaway"} confirmed for ${project?.name || selectedProjectId}.`;
      setActionMessage(message);
      setActionMessageBySignalId((current) => ({ ...current, [signalId]: message }));
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to confirm this improvement.";
      setErrorMessage(message);
      setActionErrorBySignalId((current) => ({ ...current, [signalId]: message }));
    } finally {
      setConfirmingSignalId("");
    }
  }

  const readmeText = (github?.readme?.content || "").trim();
  const roadmapText = (github?.roadmap?.content || "").trim();
  const fullReadmeText = github?.readme?.content || "";
  const fullRoadmapText = github?.roadmap?.content || "";

  return (
    <AppContainer>
      <PageHeader
        title="Project Takeaways"
        description="This is the working page for each project: review the saved project context, inspect GitHub context, and decide which completed signals should become confirmed improvements."
      />

        <div style={toolbarStyle}>
          <div style={{ display: "flex", gap: "12px", flexWrap: "wrap", alignItems: "center" }}>
            <Link href="/workspace" style={toolbarLinkStyle}>
              Back to Workspace
            </Link>
            <Link href="/workspace/projects/review" style={toolbarPrimaryLinkStyle}>
              Review Inbox
            </Link>
            <Link href="/workspace/projects/trajectory" style={toolbarPrimaryLinkStyle}>
              Trajectory Timeline
            </Link>
            <Link href="/admin/projects" style={toolbarPrimaryLinkStyle}>
              Add or Manage Projects
            </Link>
          </div>
        </div>

        {loading ? (
          <div style={{ color: "#6b7280" }}>Loading project workspace...</div>
        ) : rows.length === 0 ? (
          <div style={emptyCardStyle}>No projects are listed yet. Add one in Admin Project Intake first.</div>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "280px 1fr", gap: "20px", alignItems: "start" }}>
            <aside style={sidebarStyle}>
              <div style={sidebarTitleStyle}>Projects</div>
              <div style={{ display: "grid", gap: "10px" }}>
                {rows.map((row) => {
                  const active = row.project.project_id === selectedProjectId;
                  return (
                    <button
                      key={row.project.project_id}
                      onClick={() => setSelectedProjectId(row.project.project_id)}
                      style={{
                        textAlign: "left",
                        padding: "12px 14px",
                        borderRadius: "12px",
                        border: active ? "1px solid #111827" : "1px solid #e5e7eb",
                        background: active ? "#111827" : "#ffffff",
                        color: active ? "#ffffff" : "#111827",
                        cursor: "pointer",
                      }}
                    >
                      <div style={{ fontSize: "15px", fontWeight: 700 }}>{row.project.name || row.project.project_id}</div>
                      <div style={{ marginTop: "8px", display: "flex", gap: "8px", flexWrap: "wrap" }}>
                        <span style={{ ...chipStyle, background: active ? "#1f2937" : "#ffffff", color: active ? "#ffffff" : "#374151" }}>
                          {row.improvement_count || 0} improvements
                        </span>
                        <span style={{ ...chipStyle, background: active ? "#1f2937" : "#ffffff", color: active ? "#ffffff" : "#374151" }}>
                          {row.confirmed_count || 0} confirmed
                        </span>
                      </div>
                    </button>
                  );
                })}
              </div>
            </aside>

            <div style={{ display: "grid", gap: "18px" }}>
              <section style={panelStyle}>
                <div style={sidebarTitleStyle}>Project Workspace View</div>
                <div style={{ fontSize: "28px", fontWeight: 800, color: "#111827" }}>
                  {project?.name || selectedRow?.project.name || selectedProjectId}
                </div>
                {project?.description ? (
                  <div style={{ marginTop: "10px", fontSize: "14px", lineHeight: "1.75", color: "#4b5563" }}>
                    {project.description}
                  </div>
                ) : null}
                <div style={{ marginTop: "14px", display: "flex", gap: "10px", flexWrap: "wrap" }}>
                  <span style={chipStyle}>Status: {readableStatus(project?.status)}</span>
                  <span style={chipStyle}>GitHub: {renderGithubStatusChip(github?.status)}</span>
                  <span style={chipStyle}>{improvements.length} improvement item(s)</span>
                  {cacheInfo?.fetched_at ? <span style={chipStyle}>Cached: {cacheInfo.fetched_at}</span> : null}
                  {githubRefreshing ? <span style={chipStyle}>Refreshing GitHub context...</span> : null}
                </div>
                <div style={{ marginTop: "14px", display: "flex", gap: "12px", flexWrap: "wrap" }}>
                  {selectedProjectId ? (
                    <Link href={`/workspace/projects?project_id=${encodeURIComponent(selectedProjectId)}`} style={inlineLinkStyle}>
                      Open Full Project Detail
                    </Link>
                  ) : null}
                  <Link href="/admin/projects" style={inlineLinkStyle}>
                    Edit Project Configuration
                  </Link>
                </div>
              </section>

              {detailLoading ? <div style={{ color: "#6b7280" }}>Loading selected project detail...</div> : null}
              {errorMessage ? <div style={errorCardStyle}>{errorMessage}</div> : null}
              {actionMessage ? <div style={successCardStyle}>{actionMessage}</div> : null}

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "18px", alignItems: "start" }}>
                <section style={pairedPanelStyle}>
                  <div style={sectionTitleStyle}>Current Project Situation</div>
                  {project?.current_state?.trim() ? (
                    <pre style={preStyle}>{truncateText(project.current_state, 1800)}</pre>
                  ) : (
                    <div style={emptyTextStyle}>No manual project situation has been saved yet.</div>
                  )}
                </section>

                <section style={pairedPanelStyle}>
                  <div style={sectionTitleStyle}>Manual Roadmap</div>
                  {project?.roadmap?.trim() ? (
                    <pre style={preStyle}>{truncateText(project.roadmap, 1800)}</pre>
                  ) : (
                    <div style={emptyTextStyle}>No manual roadmap has been saved yet.</div>
                  )}
                </section>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "18px", alignItems: "start" }}>
                <section style={pairedPanelStyle}>
                  <div style={sectionTitleStyle}>README</div>
                  {readmeText ? (
                    <>
                      <div style={documentMetaStyle}>{github?.readme?.path || "README"}</div>
                      <pre style={scrollingPreStyle}>{readmeText}</pre>
                      <div style={documentActionsRowStyle}>
                        <button type="button" onClick={() => setOpenDocument("readme")} style={secondaryButtonStyle}>
                          View Full README
                        </button>
                      </div>
                    </>
                  ) : (
                    <div style={emptyTextStyle}>No README content available yet.</div>
                  )}
                </section>

                <section style={pairedPanelStyle}>
                  <div style={sectionTitleStyle}>Roadmap From GitHub</div>
                  {roadmapText ? (
                    <>
                      <div style={documentMetaStyle}>{github?.roadmap?.path || "Roadmap"}</div>
                      <pre style={scrollingPreStyle}>{roadmapText}</pre>
                      <div style={documentActionsRowStyle}>
                        <button type="button" onClick={() => setOpenDocument("roadmap")} style={secondaryButtonStyle}>
                          View Full Roadmap
                        </button>
                      </div>
                    </>
                  ) : (
                    <div style={emptyTextStyle}>
                      We did not find a roadmap file in this repository yet. If you want GitHub roadmap content here,
                      add `ROADMAP.md` or `docs/roadmap.md`.
                    </div>
                  )}
                </section>
              </div>

              <section style={panelStyle}>
                <div style={sectionTitleStyle}>Improvement List</div>
                <div style={{ marginTop: "8px", fontSize: "14px", color: "#64748b", lineHeight: "1.7" }}>
                  Each item below belongs only to this project. Review the signal fit, score, benefits, and roadmap placement,
                  then confirm the item when you want it to become an accepted project improvement.
                </div>

                {improvements.length === 0 ? (
                  <div style={{ marginTop: "16px", color: "#6b7280" }}>
                    No completed signal has been added to this project yet.
                  </div>
                ) : (
                  <div style={{ display: "grid", gap: "12px", marginTop: "16px" }}>
                    {improvements.map((item, index) => (
                      <div key={`${item.signal_id || "signal"}-${index}`} style={issueCardStyle}>
                        <div style={{ display: "flex", justifyContent: "space-between", gap: "16px", alignItems: "start" }}>
                          <div>
                            <div style={{ fontSize: "16px", fontWeight: 700, color: "#111827" }}>
                              {item.signal_title || "Untitled signal"}
                            </div>
                            {item.signal_summary ? (
                              <div style={{ marginTop: "8px", fontSize: "14px", lineHeight: "1.7", color: "#4b5563" }}>
                                {item.signal_summary}
                              </div>
                            ) : null}
                          </div>
                          <div style={{ fontSize: "22px", fontWeight: 800, color: "#111827", whiteSpace: "nowrap" }}>
                            {formatScore(item.score)}
                          </div>
                        </div>

                        <div style={{ marginTop: "10px", display: "flex", gap: "8px", flexWrap: "wrap" }}>
                          {item.status ? <span style={chipStyle}>{item.status}</span> : null}
                          {item.suggested_stage ? <span style={chipStyle}>Stage: {item.suggested_stage}</span> : null}
                          <span style={chipStyle}>{item.should_apply === false ? "low fit" : "candidate fit"}</span>
                        </div>

                        {item.takeaway ? (
                          <div style={{ marginTop: "12px", fontSize: "14px", lineHeight: "1.7", color: "#374151" }}>
                            {truncateText(item.takeaway, 260)}
                          </div>
                        ) : null}

                        <div style={{ marginTop: "14px", display: "flex", gap: "12px", flexWrap: "wrap" }}>
                          {item.signal_id ? (
                            <Link
                              href={`/workspace/projects/improvement-detail?project_id=${encodeURIComponent(selectedProjectId)}&signal_id=${encodeURIComponent(item.signal_id)}`}
                              style={secondaryLinkStyle}
                            >
                              {item.status === "confirmed" ? "Open Confirmed Improvement" : "Open Fit Detail"}
                            </Link>
                          ) : null}
                          {item.status !== "confirmed" && item.signal_id ? (
                            <button
                              type="button"
                              onClick={() => void handleConfirm(item)}
                              disabled={confirmingSignalId === item.signal_id}
                              style={primaryButtonStyle}
                            >
                              {confirmingSignalId === item.signal_id ? "Confirming..." : "Confirm"}
                            </button>
                          ) : null}
                        </div>
                        {item.signal_id && actionMessageBySignalId[item.signal_id] ? (
                          <div style={inlineSuccessStyle}>{actionMessageBySignalId[item.signal_id]}</div>
                        ) : null}
                        {item.signal_id && actionErrorBySignalId[item.signal_id] ? (
                          <div style={inlineErrorStyle}>{actionErrorBySignalId[item.signal_id]}</div>
                        ) : null}
                      </div>
                    ))}
                  </div>
                )}
              </section>
            </div>
          </div>
        )}

        {openDocument ? (
          <div style={modalOverlayStyle} onClick={() => setOpenDocument(null)}>
            <div style={modalCardStyle} onClick={(event) => event.stopPropagation()}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "16px" }}>
                <div>
                  <div style={sectionTitleStyle}>
                    {openDocument === "readme" ? "Full README" : "Full Roadmap"}
                  </div>
                  <div style={{ marginTop: "6px", fontSize: "13px", color: "#6b7280" }}>
                    {openDocument === "readme"
                      ? github?.readme?.path || "README"
                      : github?.roadmap?.path || "Roadmap"}
                  </div>
                </div>
                <button type="button" onClick={() => setOpenDocument(null)} style={secondaryButtonStyle}>
                  Close
                </button>
              </div>

              <pre style={{ ...preStyle, marginTop: "16px", maxHeight: "70vh" }}>
                {openDocument === "readme" ? fullReadmeText : fullRoadmapText}
              </pre>
            </div>
          </div>
        ) : null}

    </AppContainer>
  );
}

const toolbarLinkStyle = {
  textDecoration: "none",
  color: "#111827",
  fontSize: "14px",
  fontWeight: 800,
  border: "1px solid #d1d5db",
  borderRadius: "8px",
  background: "#ffffff",
  padding: "10px 14px",
} as const;

const toolbarPrimaryLinkStyle = {
  ...toolbarLinkStyle,
  border: "1px solid #111827",
  background: "#111827",
  color: "#ffffff",
} as const;

const toolbarStyle = {
  marginBottom: "20px",
  border: "1px solid #e5e7eb",
  borderRadius: "20px",
  background: "#ffffff",
  padding: "16px 18px",
  boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
} as const;

const inlineLinkStyle = {
  textDecoration: "none",
  color: "#111827",
  fontSize: "14px",
  fontWeight: 700,
} as const;

const sidebarStyle = {
  border: "1px solid #e5e7eb",
  borderRadius: "16px",
  background: "#fff",
  padding: "14px",
} as const;

const panelStyle = {
  border: "1px solid #e5e7eb",
  borderRadius: "16px",
  background: "#fff",
  padding: "20px",
  boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
} as const;

const pairedPanelStyle = {
  ...panelStyle,
  minHeight: "220px",
} as const;

const sidebarTitleStyle = {
  fontSize: "13px",
  color: "#6b7280",
  marginBottom: "10px",
  textTransform: "uppercase" as const,
  letterSpacing: "0.4px",
} as const;

const sectionTitleStyle = {
  fontSize: "22px",
  lineHeight: "1.2",
  fontWeight: 700,
  color: "#111827",
} as const;

const chipStyle = {
  display: "inline-flex",
  alignItems: "center",
  padding: "5px 10px",
  borderRadius: "999px",
  border: "1px solid #d1d5db",
  background: "#ffffff",
  fontSize: "12px",
  color: "#374151",
  fontWeight: 600,
} as const;

const preStyle = {
  marginTop: "10px",
  padding: "16px",
  borderRadius: "12px",
  background: "#f8fafc",
  border: "1px solid #eef2f7",
  whiteSpace: "pre-wrap" as const,
  fontSize: "13px",
  lineHeight: "1.7",
  color: "#334155",
  overflowX: "auto" as const,
} as const;

const scrollingPreStyle = {
  ...preStyle,
  height: "400px",
  overflowY: "auto" as const,
} as const;

const documentActionsRowStyle = {
  display: "flex",
  justifyContent: "flex-end",
  marginTop: "12px",
} as const;

const documentMetaStyle = {
  marginTop: "10px",
  fontSize: "12px",
  color: "#6b7280",
  textTransform: "uppercase" as const,
  letterSpacing: "0.4px",
} as const;

const emptyTextStyle = {
  marginTop: "12px",
  color: "#6b7280",
  fontSize: "14px",
  lineHeight: "1.7",
} as const;

const issueCardStyle = {
  border: "1px solid #e5e7eb",
  borderRadius: "14px",
  padding: "16px",
  background: "#fafafa",
} as const;

const emptyCardStyle = {
  border: "1px solid #e5e7eb",
  borderRadius: "16px",
  padding: "20px",
  background: "#fff",
} as const;

const errorCardStyle = {
  border: "1px solid #fecaca",
  borderRadius: "16px",
  padding: "14px 16px",
  background: "#fff1f2",
  color: "#be123c",
} as const;

const successCardStyle = {
  border: "1px solid #bbf7d0",
  borderRadius: "16px",
  padding: "14px 16px",
  background: "#f0fdf4",
  color: "#166534",
  fontWeight: 700,
} as const;

const inlineSuccessStyle = {
  marginTop: "12px",
  border: "1px solid #bbf7d0",
  borderRadius: "10px",
  padding: "10px 12px",
  background: "#f0fdf4",
  color: "#166534",
  fontSize: "13px",
  fontWeight: 700,
} as const;

const inlineErrorStyle = {
  marginTop: "12px",
  border: "1px solid #fecaca",
  borderRadius: "10px",
  padding: "10px 12px",
  background: "#fff1f2",
  color: "#be123c",
  fontSize: "13px",
  fontWeight: 700,
} as const;

const primaryButtonStyle = {
  padding: "10px 14px",
  borderRadius: "10px",
  border: "1px solid #111827",
  background: "#111827",
  color: "#ffffff",
  cursor: "pointer",
  fontWeight: 700,
} as const;

const secondaryButtonStyle = {
  padding: "10px 14px",
  borderRadius: "10px",
  border: "1px solid #d1d5db",
  background: "#ffffff",
  color: "#111827",
  cursor: "pointer",
  fontWeight: 600,
} as const;

const secondaryLinkStyle = {
  padding: "10px 14px",
  borderRadius: "10px",
  border: "1px solid #d1d5db",
  background: "#ffffff",
  color: "#111827",
  textDecoration: "none",
  fontWeight: 600,
} as const;

const modalOverlayStyle = {
  position: "fixed",
  inset: 0,
  background: "rgba(15, 23, 42, 0.5)",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  padding: "24px",
  zIndex: 120,
} as const;

const modalCardStyle = {
  width: "min(1100px, 100%)",
  maxHeight: "85vh",
  overflow: "auto",
  borderRadius: "20px",
  background: "#ffffff",
  border: "1px solid #e5e7eb",
  boxShadow: "0 24px 48px rgba(15, 23, 42, 0.18)",
  padding: "22px",
} as const;
