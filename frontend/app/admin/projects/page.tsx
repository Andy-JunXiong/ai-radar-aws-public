"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import AppContainer from "@/components/AppContainer";
import PageHeader from "@/components/PageHeader";
import RequireAdminAuth from "@/components/RequireAdminAuth";
import { apiUrl } from "@/lib/api";
import { adminFetch } from "@/lib/adminAuth";

type ProjectRegistryItem = {
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

type ProjectRegistryResponse = {
  items?: ProjectRegistryItem[];
};

type ProjectRepoSnapshot = {
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
  top_level_tree?: Array<{ name?: string; path?: string; type?: string }>;
  recent_commits?: Array<{ sha?: string; message?: string; committed_at?: string }>;
  manifests?: Array<{ path?: string }>;
};

type ProjectRepoSnapshotResponse = {
  repo_snapshot?: ProjectRepoSnapshot;
};

const STATUS_OPTIONS = [
  { value: "planning", label: "Planning" },
  { value: "active", label: "Active" },
  { value: "on_hold", label: "On Hold" },
  { value: "completed", label: "Completed" },
  { value: "archived", label: "Archived" },
];

const TOPIC_OPTIONS = [
  "AI Intelligence",
  "Agent Systems",
  "Knowledge Systems",
  "Decision Intelligence",
  "Market Intelligence",
  "Real Estate",
  "Operations",
  "Infrastructure",
];

const EMPTY_FORM = {
  project_id: "",
  name: "",
  description: "",
  status: "planning",
  repo: "",
  enabled: true,
  current_state: "",
  roadmap: "",
  topics: [] as string[],
  customTopics: "",
};

function normalizeStatus(value?: string): string {
  const raw = (value || "").trim().toLowerCase();
  return STATUS_OPTIONS.some((option) => option.value === raw) ? raw : "planning";
}

export default function AdminProjectIntakePage() {
  const [projects, setProjects] = useState<ProjectRegistryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [message, setMessage] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [form, setForm] = useState(EMPTY_FORM);
  const [selectedProjectId, setSelectedProjectId] = useState("");
  const [repoSnapshot, setRepoSnapshot] = useState<ProjectRepoSnapshot | null>(null);
  const [snapshotLoading, setSnapshotLoading] = useState(false);
  const [snapshotRefreshing, setSnapshotRefreshing] = useState(false);

  async function fetchNextProjectId() {
    const response = await fetch(apiUrl("/projects/next-id"), { cache: "no-store" });
    const data = (await response.json().catch(() => null)) as { project_id?: string } | null;
    return data?.project_id || "";
  }

  async function loadProjects() {
    setLoading(true);
    try {
      const response = await fetch(apiUrl("/projects"), { cache: "no-store" });
      const data = (await response.json().catch(() => null)) as ProjectRegistryResponse | null;
      setProjects(data?.items ?? []);
    } catch (error) {
      console.error("Failed to load projects:", error);
      setProjects([]);
    } finally {
      setLoading(false);
    }
  }

  async function loadRepoSnapshot(projectId: string) {
    const normalizedProjectId = projectId.trim();
    if (!normalizedProjectId) {
      setRepoSnapshot(null);
      return;
    }

    setSnapshotLoading(true);
    try {
      const response = await fetch(apiUrl(`/projects/${encodeURIComponent(normalizedProjectId)}/repo-snapshot`), {
        cache: "no-store",
      });
      const data = (await response.json().catch(() => null)) as ProjectRepoSnapshotResponse | null;
      setRepoSnapshot(data?.repo_snapshot || null);
    } catch (error) {
      console.error("Failed to load repo snapshot:", error);
      setRepoSnapshot({
        status: "failed",
        message: "Repo snapshot could not be loaded.",
      });
    } finally {
      setSnapshotLoading(false);
    }
  }

  async function resetForNewProject() {
    const nextId = await fetchNextProjectId().catch(() => "");
    setSelectedProjectId("");
    setForm({
      ...EMPTY_FORM,
      project_id: nextId,
    });
    setMessage("");
    setErrorMessage("");
    setRepoSnapshot(null);
  }

  useEffect(() => {
    if (!selectedProjectId) {
      setRepoSnapshot(null);
      return;
    }
    void loadRepoSnapshot(selectedProjectId);
  }, [selectedProjectId]);

  useEffect(() => {
    void loadProjects();
    void resetForNewProject();
  }, []);

  function hydrateForm(project: ProjectRegistryItem) {
    const topics = Array.isArray(project.topics) ? project.topics : [];
    const presetTopics = topics.filter((topic) => TOPIC_OPTIONS.includes(topic));
    const customTopics = topics.filter((topic) => !TOPIC_OPTIONS.includes(topic)).join(", ");

    setSelectedProjectId(project.project_id || "");
    setForm({
      project_id: project.project_id || "",
      name: project.name || "",
      description: project.description || "",
      status: normalizeStatus(project.status),
      repo: project.repo || "",
      enabled: project.enabled !== false,
      current_state: project.current_state || "",
      roadmap: project.roadmap || "",
      topics: presetTopics,
      customTopics,
    });
    setMessage("");
    setErrorMessage("");
  }

  const allTopics = useMemo(() => {
    const customTopics = form.customTopics
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);

    return Array.from(new Set([...form.topics, ...customTopics]));
  }, [form.customTopics, form.topics]);

  async function handleSave() {
    if (!form.name.trim()) {
      setErrorMessage("Project name is required.");
      setMessage("");
      return;
    }

    setSaving(true);
    setMessage("");
    setErrorMessage("");

    try {
      const response = await adminFetch(apiUrl("/projects"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project_id: form.project_id.trim(),
          name: form.name.trim(),
          description: form.description.trim(),
          status: normalizeStatus(form.status),
          repo: form.repo.trim(),
          enabled: form.enabled,
          current_state: form.current_state.trim(),
          roadmap: form.roadmap.trim(),
          topics: allTopics,
        }),
      });

      const data = (await response.json().catch(() => null)) as {
        detail?: string;
        message?: string;
        item?: ProjectRegistryItem;
        repo_snapshot?: ProjectRepoSnapshot;
      } | null;
      if (!response.ok) {
        throw new Error(data?.detail || data?.message || `Failed to save project (${response.status})`);
      }

      const savedProject = data?.item;
      if (savedProject?.project_id) {
        setSelectedProjectId(savedProject.project_id);
        hydrateForm(savedProject);
      }
      setRepoSnapshot(data?.repo_snapshot || null);

      setMessage("Project saved successfully.");
      await loadProjects();
    } catch (error) {
      console.error("Failed to save project:", error);
      setErrorMessage(error instanceof Error ? error.message : "Failed to save project.");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!selectedProjectId) return;

    setDeleting(true);
    setMessage("");
    setErrorMessage("");

    try {
      const response = await adminFetch(apiUrl(`/projects/${encodeURIComponent(selectedProjectId)}`), {
        method: "DELETE",
      });

      const data = (await response.json().catch(() => null)) as { detail?: string; message?: string } | null;
      if (!response.ok) {
        throw new Error(data?.detail || data?.message || `Failed to delete project (${response.status})`);
      }

      setMessage("Project deleted.");
      await loadProjects();
      await resetForNewProject();
    } catch (error) {
      console.error("Failed to delete project:", error);
      setErrorMessage(error instanceof Error ? error.message : "Failed to delete project.");
    } finally {
      setDeleting(false);
    }
  }

  async function handleRefreshSnapshot() {
    const projectId = selectedProjectId || form.project_id.trim();
    if (!projectId) return;

    setSnapshotRefreshing(true);
    setErrorMessage("");
    try {
      const response = await adminFetch(apiUrl(`/projects/${encodeURIComponent(projectId)}/repo-snapshot/refresh`), {
        method: "POST",
        cache: "no-store",
      });
      const data = (await response.json().catch(() => null)) as
        | (ProjectRepoSnapshotResponse & { detail?: string; message?: string })
        | null;
      if (!response.ok) {
        throw new Error(data?.detail || data?.message || `Failed to refresh repo snapshot (${response.status})`);
      }
      setRepoSnapshot(data?.repo_snapshot || null);
      setMessage("Repo snapshot refreshed.");
    } catch (error) {
      console.error("Failed to refresh repo snapshot:", error);
      setErrorMessage(error instanceof Error ? error.message : "Failed to refresh repo snapshot.");
    } finally {
      setSnapshotRefreshing(false);
    }
  }

  function toggleTopic(topic: string) {
    setForm((prev) => ({
      ...prev,
      topics: prev.topics.includes(topic)
        ? prev.topics.filter((item) => item !== topic)
        : [...prev.topics, topic],
    }));
  }

  return (
    <AppContainer>
      <RequireAdminAuth>
        <PageHeader
          title="Project Intake"
          description="Add projects here, maintain project status and roadmap, and connect GitHub only when you are ready. Workspace pages will read from this admin-managed list."
        />

        <div style={toolbarRowStyle}>
          <Link href="/workspace/projects" style={toolbarPrimaryLinkStyle}>
            Back to Project Takeaways
          </Link>
          <Link href="/admin" style={toolbarSecondaryLinkStyle}>
            Back to Admin
          </Link>
        </div>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "320px 1fr",
            gap: "20px",
            alignItems: "start",
          }}
        >
          <section style={panelStyle}>
            <div style={sectionTitleStyle}>Project List</div>
            <div style={{ marginTop: "10px", fontSize: "14px", color: "#64748b", lineHeight: "1.7" }}>
              Select a project to edit it, or create a new project with an automatically generated project ID.
            </div>

            <button onClick={() => void resetForNewProject()} style={{ ...secondaryButtonStyle, marginTop: "14px" }}>
              Add New Project
            </button>

            <div style={{ display: "grid", gap: "10px", marginTop: "14px" }}>
              {loading ? (
                <div style={{ color: "#6b7280" }}>Loading projects...</div>
              ) : (
                projects.map((project) => (
                  <button
                    key={project.project_id}
                    onClick={() => hydrateForm(project)}
                    style={{
                      textAlign: "left",
                      padding: "12px 14px",
                      borderRadius: "12px",
                      border:
                        selectedProjectId === project.project_id ? "1px solid #111827" : "1px solid #e5e7eb",
                      background: "#ffffff",
                      cursor: "pointer",
                    }}
                  >
                    <div style={{ fontSize: "15px", fontWeight: 700, color: "#111827" }}>
                      {project.name || project.project_id}
                    </div>
                    <div style={{ marginTop: "6px", display: "flex", gap: "8px", flexWrap: "wrap" }}>
                      <span style={chipStyle}>{readableStatus(project.status)}</span>
                      <span style={chipStyle}>{project.enabled === false ? "hidden" : "listed"}</span>
                      {project.repo ? <span style={chipStyle}>repo linked</span> : null}
                    </div>
                  </button>
                ))
              )}
            </div>
          </section>

          <section style={panelStyle}>
            <div style={sectionTitleStyle}>Project Configuration</div>
            <div style={{ marginTop: "8px", fontSize: "14px", color: "#64748b", lineHeight: "1.7" }}>
              `Open Project Intelligence` means opening the next page that reads your saved project context and,
              if a GitHub repo is connected, loads README, roadmap, and issues from GitHub.
            </div>

            <div style={{ marginTop: "12px", display: "grid", gap: "14px" }}>
              <Field label="Project ID">
                <input value={form.project_id} readOnly style={{ ...inputStyle, background: "#f8fafc", color: "#64748b" }} />
              </Field>

              <div style={{ display: "grid", gridTemplateColumns: "1.5fr 0.8fr", gap: "14px" }}>
                <Field label="Project Name">
                  <input value={form.name} onChange={(e) => setForm((prev) => ({ ...prev, name: e.target.value }))} style={inputStyle} placeholder="AI Radar" />
                </Field>

                <Field label="Status">
                  <select value={form.status} onChange={(e) => setForm((prev) => ({ ...prev, status: e.target.value }))} style={inputStyle}>
                    {STATUS_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </Field>
              </div>

              <Field label="Description">
                <textarea value={form.description} onChange={(e) => setForm((prev) => ({ ...prev, description: e.target.value }))} style={textareaStyle} placeholder="What this project is about" />
              </Field>

              <Field label="Current Project Situation">
                <textarea value={form.current_state} onChange={(e) => setForm((prev) => ({ ...prev, current_state: e.target.value }))} style={textareaStyle} placeholder="Current state, blockers, priorities, implementation situation..." />
              </Field>

              <Field label="Manual Roadmap">
                <textarea value={form.roadmap} onChange={(e) => setForm((prev) => ({ ...prev, roadmap: e.target.value }))} style={{ ...textareaStyle, minHeight: "160px" }} placeholder="Roadmap, phases, upcoming milestones..." />
              </Field>

              <Field label="GitHub Repo">
                <input value={form.repo} onChange={(e) => setForm((prev) => ({ ...prev, repo: e.target.value }))} style={inputStyle} placeholder="owner/repo or https://github.com/owner/repo" />
              </Field>

              <section style={snapshotPanelStyle}>
                <div style={{ display: "flex", justifyContent: "space-between", gap: "12px", flexWrap: "wrap" }}>
                  <div>
                    <div style={smallTitleStyle}>Repo Snapshot</div>
                    <div style={{ marginTop: "6px", display: "flex", gap: "8px", flexWrap: "wrap" }}>
                      <span style={chipStyle}>{snapshotLoading ? "loading" : readableSnapshotStatus(repoSnapshot?.status)}</span>
                      {repoSnapshot?.repo ? <span style={chipStyle}>{repoSnapshot.repo}</span> : null}
                      {repoSnapshot?.scanned_at ? <span style={chipStyle}>scanned {formatCompactDate(repoSnapshot.scanned_at)}</span> : null}
                    </div>
                  </div>
                  <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", alignItems: "start" }}>
                    <button
                      type="button"
                      onClick={() => void handleRefreshSnapshot()}
                      disabled={!form.project_id.trim() || snapshotRefreshing}
                      style={secondaryButtonStyle}
                    >
                      {snapshotRefreshing ? "Refreshing..." : "Refresh Light Snapshot"}
                    </button>
                    <button type="button" disabled style={{ ...secondaryButtonStyle, color: "#94a3b8", cursor: "not-allowed" }}>
                      Run Deep Scan
                    </button>
                  </div>
                </div>

                {repoSnapshot?.message ? <div style={snapshotMessageStyle}>{repoSnapshot.message}</div> : null}

                {repoSnapshot?.summary ? <div style={snapshotSummaryStyle}>{repoSnapshot.summary}</div> : null}

                <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                  <span style={chipStyle}>README {repoSnapshot?.readme_found ? repoSnapshot.readme_path || "found" : "missing"}</span>
                  <span style={chipStyle}>Roadmap {repoSnapshot?.roadmap_found ? repoSnapshot.roadmap_path || "found" : "missing"}</span>
                  <span style={chipStyle}>Manifests {repoSnapshot?.manifests?.length || 0}</span>
                  <span style={chipStyle}>Recent commits {repoSnapshot?.recent_commits?.length || 0}</span>
                </div>

                {repoSnapshot?.architecture_hints?.length ? (
                  <div style={snapshotListStyle}>
                    {repoSnapshot.architecture_hints.map((hint) => (
                      <span key={hint} style={chipStyle}>
                        {hint}
                      </span>
                    ))}
                  </div>
                ) : null}
              </section>

              <Field label="Focus Tags">
                <div style={{ display: "grid", gap: "10px" }}>
                  <div style={{ fontSize: "13px", color: "#64748b" }}>
                    These tags help explain what the project is about and make project grouping clearer in workspace pages.
                  </div>
                  <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                    {TOPIC_OPTIONS.map((topic) => {
                      const active = form.topics.includes(topic);
                      return (
                        <button
                          key={topic}
                          type="button"
                          onClick={() => toggleTopic(topic)}
                          style={{
                            ...chipButtonStyle,
                            background: active ? "#111827" : "#ffffff",
                            color: active ? "#ffffff" : "#374151",
                            border: active ? "1px solid #111827" : "1px solid #d1d5db",
                          }}
                        >
                          {topic}
                        </button>
                      );
                    })}
                  </div>
                  <input
                    value={form.customTopics}
                    onChange={(e) => setForm((prev) => ({ ...prev, customTopics: e.target.value }))}
                    style={inputStyle}
                    placeholder="Optional custom tags, comma-separated"
                  />
                </div>
              </Field>

              <label style={{ display: "flex", gap: "10px", alignItems: "center", fontSize: "14px", color: "#374151" }}>
                <input type="checkbox" checked={form.enabled} onChange={(e) => setForm((prev) => ({ ...prev, enabled: e.target.checked }))} />
                Include this project in Workspace Project Takeaways
              </label>

              <div style={{ display: "flex", gap: "10px", flexWrap: "wrap", alignItems: "center" }}>
                <button onClick={() => void handleSave()} disabled={saving} style={primaryButtonStyle}>
                  {saving ? "Saving..." : "Save Project"}
                </button>

                {selectedProjectId ? (
                  <button onClick={() => void handleDelete()} disabled={deleting} style={dangerButtonStyle}>
                    {deleting ? "Deleting..." : "Delete Project"}
                  </button>
                ) : null}

                {form.project_id.trim() ? (
                  <Link href={`/workspace/projects?project_id=${encodeURIComponent(form.project_id.trim())}`} style={secondaryLinkStyle}>
                    Open Project Intelligence
                  </Link>
                ) : null}
              </div>

              {message ? <div style={successNoticeStyle}>{message}</div> : null}
              {errorMessage ? <div style={errorNoticeStyle}>{errorMessage}</div> : null}
            </div>
          </section>
        </div>
      </RequireAdminAuth>
    </AppContainer>
  );
}

function readableStatus(value?: string) {
  return STATUS_OPTIONS.find((option) => option.value === normalizeStatus(value))?.label || "Planning";
}

function readableSnapshotStatus(value?: string) {
  switch ((value || "").trim()) {
    case "fresh":
      return "fresh";
    case "stale":
      return "stale";
    case "partial":
      return "partial";
    case "failed":
      return "failed";
    case "not_connected":
      return "not connected";
    default:
      return "missing";
  }
}

function formatCompactDate(value?: string) {
  if (!value) return "";
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label style={{ display: "grid", gap: "8px" }}>
      <span style={{ fontSize: "13px", fontWeight: 700, color: "#374151" }}>{label}</span>
      {children}
    </label>
  );
}

const panelStyle = {
  border: "1px solid #e5e7eb",
  borderRadius: "16px",
  background: "#fff",
  padding: "20px",
  boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
} as const;

const sectionTitleStyle = {
  fontSize: "22px",
  lineHeight: "1.2",
  fontWeight: 700,
  color: "#111827",
} as const;

const smallTitleStyle = {
  fontSize: "13px",
  fontWeight: 800,
  color: "#475569",
  textTransform: "uppercase" as const,
  letterSpacing: 0,
} as const;

const snapshotPanelStyle = {
  border: "1px solid #e5e7eb",
  borderRadius: "14px",
  background: "#f8fafc",
  padding: "14px",
  display: "grid",
  gap: "12px",
} as const;

const snapshotMessageStyle = {
  fontSize: "13px",
  lineHeight: 1.6,
  color: "#475569",
} as const;

const snapshotSummaryStyle = {
  border: "1px solid #e5e7eb",
  borderRadius: "12px",
  background: "#ffffff",
  padding: "12px",
  fontSize: "14px",
  lineHeight: 1.65,
  color: "#111827",
} as const;

const snapshotListStyle = {
  display: "flex",
  gap: "8px",
  flexWrap: "wrap" as const,
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

const chipButtonStyle = {
  display: "inline-flex",
  alignItems: "center",
  padding: "7px 11px",
  borderRadius: "999px",
  fontSize: "12px",
  fontWeight: 700,
  cursor: "pointer",
} as const;

const inputStyle = {
  border: "1px solid #d1d5db",
  borderRadius: "12px",
  padding: "12px 14px",
  fontSize: "14px",
  color: "#111827",
} as const;

const textareaStyle = {
  width: "100%",
  minHeight: "120px",
  border: "1px solid #d1d5db",
  borderRadius: "16px",
  padding: "14px 16px",
  fontSize: "14px",
  lineHeight: 1.7,
  color: "#111827",
  resize: "vertical" as const,
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

const dangerButtonStyle = {
  padding: "10px 14px",
  borderRadius: "10px",
  border: "1px solid #ef4444",
  background: "#ffffff",
  color: "#b91c1c",
  cursor: "pointer",
  fontWeight: 700,
} as const;

const secondaryButtonStyle = {
  padding: "10px 14px",
  borderRadius: "10px",
  border: "1px solid #d1d5db",
  background: "#ffffff",
  cursor: "pointer",
  fontWeight: 600,
} as const;

const secondaryLinkStyle = {
  padding: "10px 14px",
  borderRadius: "10px",
  border: "1px solid #d1d5db",
  color: "#111827",
  textDecoration: "none",
  fontWeight: 600,
} as const;

const toolbarRowStyle = {
  marginBottom: "20px",
  display: "flex",
  gap: "12px",
  flexWrap: "wrap" as const,
  alignItems: "center",
  border: "1px solid #e5e7eb",
  borderRadius: "20px",
  background: "#ffffff",
  padding: "16px 18px",
  boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
} as const;

const toolbarPrimaryLinkStyle = {
  textDecoration: "none",
  color: "#ffffff",
  fontSize: "14px",
  fontWeight: 800,
  border: "1px solid #111827",
  borderRadius: "8px",
  padding: "10px 14px",
  background: "#111827",
} as const;

const toolbarSecondaryLinkStyle = {
  textDecoration: "none",
  color: "#111827",
  fontSize: "14px",
  fontWeight: 800,
  border: "1px solid #d1d5db",
  borderRadius: "8px",
  padding: "10px 14px",
  background: "#ffffff",
} as const;

const successNoticeStyle = {
  border: "1px solid #bbf7d0",
  background: "#ecfdf3",
  color: "#166534",
  borderRadius: "12px",
  padding: "12px 14px",
  fontSize: "13px",
} as const;

const errorNoticeStyle = {
  border: "1px solid #fecaca",
  background: "#fff1f2",
  color: "#be123c",
  borderRadius: "12px",
  padding: "12px 14px",
  fontSize: "13px",
} as const;
