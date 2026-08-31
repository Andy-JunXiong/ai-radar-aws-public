"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import AppContainer from "@/components/AppContainer";
import PageHeader from "@/components/PageHeader";
import RequireAdminAuth from "@/components/RequireAdminAuth";
import { apiUrl } from "@/lib/api";
import { adminFetch } from "@/lib/adminAuth";

type TruthMapAnchor = {
  kind: string;
  path: string;
  required: boolean;
  content_mode: "excerpt" | "metadata_only";
  max_chars?: number;
};

type ProjectTruthMap = {
  schema_version: 1;
  anchors: TruthMapAnchor[];
};

type ProjectMetadata = {
  [key: string]: unknown;
  repo_context?: {
    [key: string]: unknown;
    truth_map?: ProjectTruthMap | null;
  };
};

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
  metadata?: ProjectMetadata;
};

type ProjectRegistryResponse = {
  items?: ProjectRegistryItem[];
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
  top_level_tree?: Array<{ name?: string; path?: string; type?: string }>;
  recent_commits?: Array<{ sha?: string; message?: string; committed_at?: string }>;
  manifests?: Array<{ path?: string }>;
  anchors?: Array<{
    kind?: string;
    path?: string;
    required?: boolean;
    content_mode?: string;
    found?: boolean;
    error?: string;
  }>;
  discovery?: {
    mode?: string;
    config_status?: string;
    config_errors?: Array<{ path?: string; code?: string; message?: string }>;
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
    status?: "initial" | "unchanged" | "changed" | "unavailable" | string;
    from_sha?: string;
    to_sha?: string;
    total_commits?: number;
    commits?: Array<{ sha?: string; message?: string; committed_at?: string; html_url?: string }>;
    files?: Array<{
      path?: string;
      previous_path?: string;
      status?: string;
      additions?: number;
      deletions?: number;
      changes?: number;
      html_url?: string;
    }>;
    truncated?: boolean;
    message?: string;
    html_url?: string;
  };
  refresh?: {
    last_attempted_at?: string;
    last_attempt_status?: string;
    last_succeeded_at?: string;
    last_failure?: { at?: string; message?: string } | null;
  };
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
  truthMapEnabled: false,
  truthMapAnchors: [] as TruthMapAnchor[],
};

type ApiErrorDetail =
  | string
  | {
      code?: string;
      errors?: Array<{ path?: string; code?: string; message?: string }>;
    };

function createDefaultTruthMapAnchor(): TruthMapAnchor {
  return {
    kind: "readme",
    path: "README.md",
    required: false,
    content_mode: "excerpt",
    max_chars: 1600,
  };
}

function projectTruthMap(project: ProjectRegistryItem): ProjectTruthMap | null {
  const truthMap = project.metadata?.repo_context?.truth_map;
  if (!truthMap || truthMap.schema_version !== 1 || !Array.isArray(truthMap.anchors)) return null;
  return truthMap;
}

function apiErrorMessage(detail: ApiErrorDetail | undefined, fallback: string): string {
  if (typeof detail === "string" && detail.trim()) return detail;
  if (detail && typeof detail === "object" && Array.isArray(detail.errors) && detail.errors.length) {
    const first = detail.errors[0];
    return [first.path, first.message].filter(Boolean).join(": ") || fallback;
  }
  return fallback;
}

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
  const [newProjectLoading, setNewProjectLoading] = useState(false);
  const newProjectRequestRef = useRef(0);
  const projectConfigurationRef = useRef<HTMLElement | null>(null);
  const projectNameRef = useRef<HTMLInputElement | null>(null);

  const fetchNextProjectId = useCallback(async () => {
    const response = await fetch(apiUrl("/projects/next-id"), { cache: "no-store" });
    const data = (await response.json().catch(() => null)) as { project_id?: string } | null;
    return data?.project_id || "";
  }, []);

  const loadProjects = useCallback(async () => {
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
  }, []);

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

  const resetForNewProject = useCallback(async ({ focus = true }: { focus?: boolean } = {}) => {
    const requestId = newProjectRequestRef.current + 1;
    newProjectRequestRef.current = requestId;
    setSelectedProjectId("");
    setForm(EMPTY_FORM);
    setMessage("");
    setErrorMessage("");
    setRepoSnapshot(null);
    setNewProjectLoading(true);

    if (focus) {
      requestAnimationFrame(() => {
        projectConfigurationRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
        projectNameRef.current?.focus({ preventScroll: true });
      });
    }

    const nextId = await fetchNextProjectId().catch(() => "");
    if (newProjectRequestRef.current !== requestId) return;

    setForm((previous) => ({
      ...previous,
      project_id: nextId,
    }));
    setNewProjectLoading(false);
  }, [fetchNextProjectId]);

  useEffect(() => {
    if (!selectedProjectId) {
      setRepoSnapshot(null);
      return;
    }
    void loadRepoSnapshot(selectedProjectId);
  }, [selectedProjectId]);

  useEffect(() => {
    void loadProjects();
    void resetForNewProject({ focus: false });
  }, [loadProjects, resetForNewProject]);

  function hydrateForm(project: ProjectRegistryItem) {
    newProjectRequestRef.current += 1;
    setNewProjectLoading(false);
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
      truthMapEnabled: Boolean(projectTruthMap(project)),
      truthMapAnchors: projectTruthMap(project)?.anchors.map((anchor) => ({ ...anchor })) || [],
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
    if (form.truthMapEnabled && !form.truthMapAnchors.length) {
      setErrorMessage("Add at least one Truth Map anchor, or turn configured Truth Map off.");
      setMessage("");
      return;
    }
    if (
      form.truthMapEnabled &&
      form.truthMapAnchors.some((anchor) => !anchor.kind.trim() || !anchor.path.trim())
    ) {
      setErrorMessage("Every Truth Map anchor needs both a kind and a repository-relative file path.");
      setMessage("");
      return;
    }

    const wasEditing = Boolean(selectedProjectId);
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
          metadata: {
            repo_context: {
              truth_map: form.truthMapEnabled
                ? {
                    schema_version: 1,
                    anchors: form.truthMapAnchors.map((anchor) => ({
                      ...anchor,
                      kind: anchor.kind.trim(),
                      path: anchor.path.trim(),
                    })),
                  }
                : null,
            },
          },
        }),
      });

      const data = (await response.json().catch(() => null)) as {
        detail?: ApiErrorDetail;
        message?: string;
        item?: ProjectRegistryItem;
        repo_snapshot?: ProjectRepoSnapshot;
      } | null;
      if (!response.ok) {
        throw new Error(
          apiErrorMessage(data?.detail, data?.message || `Failed to save project (${response.status})`),
        );
      }

      const savedProject = data?.item;
      if (savedProject?.project_id) {
        setSelectedProjectId(savedProject.project_id);
        hydrateForm(savedProject);
      }
      setRepoSnapshot(data?.repo_snapshot || null);

      setMessage(wasEditing ? "Project changes saved successfully." : "Project created successfully.");
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
    if (!selectedProjectId) {
      setMessage("");
      setErrorMessage("Create the project before refreshing its repo snapshot.");
      return;
    }

    const projectId = selectedProjectId;

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
      console.warn("Failed to refresh repo snapshot:", error);
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

  function setTruthMapEnabled(enabled: boolean) {
    setForm((previous) => ({
      ...previous,
      truthMapEnabled: enabled,
      truthMapAnchors:
        enabled && !previous.truthMapAnchors.length
          ? [createDefaultTruthMapAnchor()]
          : previous.truthMapAnchors,
    }));
  }

  function addTruthMapAnchor() {
    setForm((previous) => ({
      ...previous,
      truthMapAnchors: [
        ...previous.truthMapAnchors,
        {
          kind: "roadmap",
          path: "ROADMAP.md",
          required: false,
          content_mode: "excerpt",
          max_chars: 1600,
        },
      ],
    }));
  }

  function updateTruthMapAnchor(index: number, updates: Partial<TruthMapAnchor>) {
    setForm((previous) => ({
      ...previous,
      truthMapAnchors: previous.truthMapAnchors.map((anchor, anchorIndex) => {
        if (anchorIndex !== index) return anchor;
        const next = { ...anchor, ...updates };
        if (next.content_mode === "metadata_only") delete next.max_chars;
        if (next.content_mode === "excerpt" && next.max_chars === undefined) next.max_chars = 1600;
        return next;
      }),
    }));
  }

  function removeTruthMapAnchor(index: number) {
    setForm((previous) => ({
      ...previous,
      truthMapAnchors: previous.truthMapAnchors.filter((_, anchorIndex) => anchorIndex !== index),
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
                      {projectTruthMap(project) ? <span style={chipStyle}>truth map</span> : null}
                    </div>
                  </button>
                ))
              )}
            </div>
          </section>

          <section ref={projectConfigurationRef} style={panelStyle}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: "12px", alignItems: "start", flexWrap: "wrap" }}>
              <div>
                <div style={sectionTitleStyle}>{selectedProjectId ? "Edit Project" : "Create New Project"}</div>
                {!selectedProjectId ? (
                  <div style={{ marginTop: "8px", fontSize: "13px", color: "#0369a1", lineHeight: "1.6" }}>
                    {newProjectLoading
                      ? "Preparing a new project ID..."
                      : "New project form is ready. Enter a project name, then select Create Project."}
                  </div>
                ) : null}
              </div>
              <button
                type="button"
                onClick={() => void handleSave()}
                disabled={saving || newProjectLoading}
                style={primaryButtonStyle}
              >
                {saving
                  ? selectedProjectId
                    ? "Saving..."
                    : "Creating..."
                  : selectedProjectId
                    ? "Save Changes"
                    : "Create Project"}
              </button>
            </div>
            <div style={{ marginTop: "8px", fontSize: "14px", color: "#64748b", lineHeight: "1.7" }}>
              `Open Project Understanding` means opening the next page that reads your saved project context and,
              if a GitHub repo is connected, loads README, roadmap, and issues from GitHub.
            </div>

            {message ? <div style={{ ...successNoticeStyle, marginTop: "12px" }}>{message}</div> : null}
            {errorMessage ? <div style={{ ...errorNoticeStyle, marginTop: "12px" }}>{errorMessage}</div> : null}

            <div style={{ marginTop: "12px", display: "grid", gap: "14px" }}>
              <Field label="Project ID">
                <input
                  value={form.project_id}
                  readOnly
                  style={{ ...inputStyle, background: "#f8fafc", color: "#64748b" }}
                  placeholder={newProjectLoading ? "Generating..." : "Generated automatically"}
                />
              </Field>

              <div style={{ display: "grid", gridTemplateColumns: "1.5fr 0.8fr", gap: "14px" }}>
                <Field label="Project Name">
                  <input
                    ref={projectNameRef}
                    value={form.name}
                    onChange={(e) => setForm((prev) => ({ ...prev, name: e.target.value }))}
                    style={inputStyle}
                    placeholder="Enter a project name"
                  />
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

              <section style={truthMapPanelStyle}>
                <div style={{ display: "flex", justifyContent: "space-between", gap: "12px", flexWrap: "wrap" }}>
                  <div>
                    <div style={smallTitleStyle}>Repository Truth Map</div>
                    <div style={{ marginTop: "6px", fontSize: "13px", color: "#64748b", lineHeight: 1.6 }}>
                      Declare the exact repository files AI Radar should read as project context. This does not verify
                      their claims or change Project Takeaway eligibility.
                    </div>
                  </div>
                  <label style={{ display: "flex", gap: "8px", alignItems: "center", fontSize: "13px", color: "#374151" }}>
                    <input
                      type="checkbox"
                      checked={form.truthMapEnabled}
                      onChange={(event) => setTruthMapEnabled(event.target.checked)}
                    />
                    Use configured Truth Map
                  </label>
                </div>

                <div style={truthMapWorkflowNoteStyle}>
                  Save Changes stores this configuration. Refresh Light Snapshot then reads the saved anchors; refresh
                  does not require another save afterward.
                </div>

                <div style={{ fontSize: "12px", color: "var(--app-text-muted)", lineHeight: 1.6 }}>
                  Development Reality reads excerpt anchors named <code>current_state</code> and <code>development_plan</code>.
                  Use the exact repository files that own current execution status and the active plan.
                </div>

                {form.truthMapEnabled ? (
                  <div style={{ display: "grid", gap: "10px" }}>
                    {form.truthMapAnchors.map((anchor, index) => (
                      <div key={index} style={truthMapAnchorStyle}>
                        <div style={{ display: "flex", justifyContent: "space-between", gap: "10px", alignItems: "center" }}>
                          <strong style={{ fontSize: "13px", color: "#111827" }}>Anchor {index + 1}</strong>
                          <button
                            type="button"
                            onClick={() => removeTruthMapAnchor(index)}
                            style={compactDangerButtonStyle}
                          >
                            Remove
                          </button>
                        </div>
                        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "10px" }}>
                          <Field label="Kind">
                            <input
                              value={anchor.kind}
                              onChange={(event) => updateTruthMapAnchor(index, { kind: event.target.value })}
                              style={inputStyle}
                              placeholder="product_spec"
                            />
                          </Field>
                          <Field label="Repository-relative file path">
                            <input
                              value={anchor.path}
                              onChange={(event) => updateTruthMapAnchor(index, { path: event.target.value })}
                              style={inputStyle}
                              placeholder="docs/product.md"
                            />
                          </Field>
                        </div>
                        <div style={{ display: "flex", gap: "12px", flexWrap: "wrap", alignItems: "end" }}>
                          <Field label="Content mode">
                            <select
                              value={anchor.content_mode}
                              onChange={(event) =>
                                updateTruthMapAnchor(index, {
                                  content_mode: event.target.value as TruthMapAnchor["content_mode"],
                                })
                              }
                              style={{ ...inputStyle, minWidth: "160px" }}
                            >
                              <option value="excerpt">Bounded excerpt</option>
                              <option value="metadata_only">Metadata only</option>
                            </select>
                          </Field>
                          {anchor.content_mode === "excerpt" ? (
                            <Field label="Excerpt characters">
                              <input
                                type="number"
                                min={400}
                                max={4000}
                                value={anchor.max_chars || 1600}
                                onChange={(event) =>
                                  updateTruthMapAnchor(index, { max_chars: Number(event.target.value) })
                                }
                                style={{ ...inputStyle, width: "150px" }}
                              />
                            </Field>
                          ) : null}
                          <label style={{ display: "flex", gap: "8px", alignItems: "center", minHeight: "43px", fontSize: "13px", color: "#374151" }}>
                            <input
                              type="checkbox"
                              checked={anchor.required}
                              onChange={(event) => updateTruthMapAnchor(index, { required: event.target.checked })}
                            />
                            Required anchor
                          </label>
                        </div>
                      </div>
                    ))}
                    <button type="button" onClick={addTruthMapAnchor} style={{ ...secondaryButtonStyle, justifySelf: "start" }}>
                      Add Truth Anchor
                    </button>
                  </div>
                ) : (
                  <div style={{ fontSize: "13px", color: "#64748b" }}>
                    Heuristic discovery remains active until a Truth Map is enabled and saved.
                  </div>
                )}
              </section>

              <section style={snapshotPanelStyle}>
                <div style={{ display: "flex", justifyContent: "space-between", gap: "12px", flexWrap: "wrap" }}>
                  <div>
                    <div style={smallTitleStyle}>Repo Snapshot</div>
                    <div style={{ marginTop: "6px", display: "flex", gap: "8px", flexWrap: "wrap" }}>
                      <span style={chipStyle}>
                        {!selectedProjectId
                          ? "save project first"
                          : snapshotLoading
                            ? "loading"
                            : readableSnapshotStatus(repoSnapshot?.status)}
                      </span>
                      {repoSnapshot?.repo ? <span style={chipStyle}>{repoSnapshot.repo}</span> : null}
                      {repoSnapshot?.scanned_at ? <span style={chipStyle}>scanned {formatCompactDate(repoSnapshot.scanned_at)}</span> : null}
                      {repoSnapshot?.discovery ? (
                        <span style={chipStyle}>{readableDiscoveryStatus(repoSnapshot.discovery)}</span>
                      ) : null}
                      {repoSnapshot?.schema_version === 2 ? <span style={chipStyle}>snapshot v2</span> : null}
                      {repoSnapshot?.observation?.head?.sha ? (
                        <span style={chipStyle}>head {shortSha(repoSnapshot.observation.head.sha)}</span>
                      ) : null}
                      {repoSnapshot?.observation?.baseline?.sha ? (
                        <span style={chipStyle}>baseline {shortSha(repoSnapshot.observation.baseline.sha)}</span>
                      ) : null}
                      {repoSnapshot?.delta?.status ? <span style={chipStyle}>delta {repoSnapshot.delta.status}</span> : null}
                    </div>
                  </div>
                  <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", alignItems: "start" }}>
                    <button
                      type="button"
                      onClick={() => void handleRefreshSnapshot()}
                      disabled={!selectedProjectId || snapshotRefreshing}
                      style={secondaryButtonStyle}
                    >
                      {snapshotRefreshing
                        ? "Refreshing..."
                        : selectedProjectId
                          ? "Refresh Light Snapshot"
                          : "Save Project Before Refresh"}
                    </button>
                    <button type="button" disabled style={{ ...secondaryButtonStyle, color: "#94a3b8", cursor: "not-allowed" }}>
                      Run Deep Scan
                    </button>
                  </div>
                </div>

                {repoSnapshot?.message ? <div style={snapshotMessageStyle}>{repoSnapshot.message}</div> : null}

                {repoSnapshot?.refresh?.last_attempt_status === "failed" ? (
                  <div style={snapshotConfigErrorStyle}>
                    Latest Light Snapshot refresh failed {repoSnapshot.refresh.last_attempted_at ? `at ${formatCompactDate(repoSnapshot.refresh.last_attempted_at)}` : ""}.
                    {repoSnapshot.refresh.last_failure?.message ? ` ${repoSnapshot.refresh.last_failure.message}` : ""}
                    {repoSnapshot.refresh.last_succeeded_at ? ` Last successful snapshot: ${formatCompactDate(repoSnapshot.refresh.last_succeeded_at)}.` : ""}
                  </div>
                ) : null}

                {repoSnapshot?.discovery?.config_status === "invalid" ? (
                  <div style={snapshotConfigErrorStyle}>
                    {repoSnapshot.discovery.config_errors?.[0]?.path || "Truth Map"}: {repoSnapshot.discovery.config_errors?.[0]?.message || "Configuration is invalid."}
                  </div>
                ) : null}

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

                {repoSnapshot?.delta ? (
                  <div style={snapshotDeltaStyle}>
                    <div style={{ display: "flex", justifyContent: "space-between", gap: "8px", flexWrap: "wrap" }}>
                      <span style={{ fontSize: "13px", fontWeight: 800, color: "var(--app-text-strong)" }}>Observed repository delta</span>
                      {repoSnapshot.delta.from_sha || repoSnapshot.delta.to_sha ? (
                        <span style={{ fontSize: "12px", color: "var(--app-text-subtle)" }}>
                          {shortSha(repoSnapshot.delta.from_sha)} → {shortSha(repoSnapshot.delta.to_sha)}
                        </span>
                      ) : null}
                    </div>
                    {repoSnapshot.delta.message ? (
                      <div style={{ fontSize: "12px", color: "var(--app-text-muted)", lineHeight: 1.6 }}>{repoSnapshot.delta.message}</div>
                    ) : null}
                    {repoSnapshot.delta.status === "changed" && repoSnapshot.delta.commits?.length ? (
                      <div style={{ display: "grid", gap: "6px" }}>
                        <div style={snapshotDeltaLabelStyle}>
                          Commits ({repoSnapshot.delta.total_commits ?? repoSnapshot.delta.commits.length})
                        </div>
                        {repoSnapshot.delta.commits.map((commit, index) => (
                          <div key={`${commit.sha || "commit"}-${index}`} style={snapshotDeltaRowStyle}>
                            <span style={{ fontWeight: 700 }}>{shortSha(commit.sha)}</span>
                            <span>{commit.message || "Commit message unavailable"}</span>
                          </div>
                        ))}
                      </div>
                    ) : null}
                    {repoSnapshot.delta.status === "changed" && repoSnapshot.delta.files?.length ? (
                      <div style={{ display: "grid", gap: "6px" }}>
                        <div style={snapshotDeltaLabelStyle}>Files ({repoSnapshot.delta.files.length})</div>
                        {repoSnapshot.delta.files.map((file, index) => (
                          <div key={`${file.path || "file"}-${index}`} style={snapshotDeltaRowStyle}>
                            <span style={{ fontWeight: 700 }}>{file.status || "changed"}</span>
                            <span>{file.path || "Path unavailable"}</span>
                            {typeof file.changes === "number" ? <span>{file.changes} lines</span> : null}
                          </div>
                        ))}
                      </div>
                    ) : null}
                    {repoSnapshot.delta.truncated ? (
                      <div style={{ fontSize: "12px", color: "var(--app-warning-fg)" }}>Delta display is bounded; additional changes were omitted.</div>
                    ) : null}
                  </div>
                ) : null}

                {repoSnapshot?.anchors?.length ? (
                  <div style={{ display: "grid", gap: "8px" }}>
                    <div style={{ fontSize: "13px", fontWeight: 800, color: "#475569" }}>Observed truth anchors</div>
                    {repoSnapshot.anchors.map((anchor, index) => (
                      <div key={`${anchor.path || "anchor"}-${index}`} style={snapshotAnchorRowStyle}>
                        <span style={{ fontWeight: 700 }}>{anchor.kind || "anchor"}</span>
                        <span style={{ color: "#64748b" }}>{anchor.path || "path unavailable"}</span>
                        <span style={chipStyle}>{anchor.required ? "required" : "optional"}</span>
                        <span style={chipStyle}>{anchor.found ? "found" : anchor.error || "missing"}</span>
                      </div>
                    ))}
                  </div>
                ) : null}

                <div style={{ fontSize: "12px", color: "#64748b", lineHeight: 1.6 }}>
                  Repo Snapshot is project review context only. It does not verify external claims or unlock downstream actions.
                </div>
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
                <button onClick={() => void handleSave()} disabled={saving || newProjectLoading} style={primaryButtonStyle}>
                  {saving
                    ? selectedProjectId
                      ? "Saving..."
                      : "Creating..."
                    : selectedProjectId
                      ? "Save Changes"
                      : "Create Project"}
                </button>

                {selectedProjectId ? (
                  <button onClick={() => void handleDelete()} disabled={deleting} style={dangerButtonStyle}>
                    {deleting ? "Deleting..." : "Delete Project"}
                  </button>
                ) : null}

                {selectedProjectId ? (
                  <Link href={`/workspace/projects/intelligence?project_id=${encodeURIComponent(selectedProjectId)}`} style={secondaryLinkStyle}>
                    Open Project Understanding
                  </Link>
                ) : null}
              </div>

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

function readableDiscoveryStatus(discovery: NonNullable<ProjectRepoSnapshot["discovery"]>) {
  if (discovery.config_status === "invalid") return "truth map invalid";
  if (discovery.mode === "configured") return "configured truth map";
  return "heuristic discovery";
}

function formatCompactDate(value?: string) {
  if (!value) return "";
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

function shortSha(value?: string) {
  const normalized = (value || "").trim();
  return normalized ? normalized.slice(0, 8) : "—";
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

const truthMapPanelStyle = {
  border: "1px solid #dbeafe",
  borderRadius: "14px",
  background: "#f8fafc",
  padding: "14px",
  display: "grid",
  gap: "12px",
} as const;

const truthMapWorkflowNoteStyle = {
  border: "1px solid #bfdbfe",
  borderRadius: "10px",
  background: "#eff6ff",
  padding: "10px 12px",
  color: "#1e3a8a",
  fontSize: "12px",
  lineHeight: 1.6,
} as const;

const truthMapAnchorStyle = {
  border: "1px solid #e5e7eb",
  borderRadius: "10px",
  background: "#ffffff",
  padding: "12px",
  display: "grid",
  gap: "10px",
} as const;

const compactDangerButtonStyle = {
  border: "0",
  background: "transparent",
  color: "#b91c1c",
  cursor: "pointer",
  fontSize: "12px",
  fontWeight: 700,
} as const;

const snapshotConfigErrorStyle = {
  border: "1px solid var(--app-danger-border)",
  borderRadius: "10px",
  background: "var(--app-danger-bg)",
  color: "var(--app-danger-fg)",
  padding: "10px 12px",
  fontSize: "12px",
  lineHeight: 1.6,
} as const;

const snapshotAnchorRowStyle = {
  display: "flex",
  gap: "8px",
  flexWrap: "wrap" as const,
  alignItems: "center",
  borderTop: "1px solid #e5e7eb",
  paddingTop: "8px",
  fontSize: "12px",
  color: "#111827",
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

const snapshotDeltaStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "12px",
  background: "var(--app-surface-muted-bg)",
  padding: "12px",
  display: "grid",
  gap: "10px",
} as const;

const snapshotDeltaLabelStyle = {
  fontSize: "12px",
  fontWeight: 800,
  color: "var(--app-text-subtle)",
  textTransform: "uppercase" as const,
} as const;

const snapshotDeltaRowStyle = {
  display: "flex",
  gap: "8px",
  flexWrap: "wrap" as const,
  alignItems: "center",
  borderTop: "1px solid var(--app-surface-border)",
  paddingTop: "6px",
  fontSize: "12px",
  color: "var(--app-text-muted)",
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
  border: "1px solid var(--app-success-border)",
  background: "var(--app-success-bg)",
  color: "var(--app-success-fg)",
  borderRadius: "12px",
  padding: "12px 14px",
  fontSize: "13px",
  fontWeight: 700,
} as const;

const errorNoticeStyle = {
  border: "1px solid var(--app-danger-border)",
  background: "var(--app-danger-bg)",
  color: "var(--app-danger-fg)",
  borderRadius: "12px",
  padding: "12px 14px",
  fontSize: "13px",
  fontWeight: 700,
} as const;
