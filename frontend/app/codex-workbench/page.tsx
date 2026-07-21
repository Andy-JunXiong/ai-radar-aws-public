"use client";

import Link from "next/link";
import type { CSSProperties } from "react";
import { useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
  Bot,
  CheckCircle2,
  Clock3,
  ClipboardCheck,
  Copy,
  ExternalLink,
  FileCode2,
  Filter,
  GitBranch,
  GitPullRequest,
  ListChecks,
  Save,
  ShieldCheck,
  TerminalSquare,
  Trash2,
} from "lucide-react";
import AppContainer from "@/components/AppContainer";
import PageHeader from "@/components/PageHeader";
import { API_BASE } from "@/lib/api";
import { adminFetch } from "@/lib/adminAuth";

const DEFAULT_REPO = "Andy-JunXiong/ai-radar-aws";
const DEFAULT_BRANCH = "main";
const STORAGE_KEY = "ai-radar-codex-workbench-drafts";
const MAX_SAVED_DRAFTS = 12;

const requestTypeOptions = [
  { value: "bug", label: "Bug" },
  { value: "feature", label: "Feature" },
  { value: "review", label: "Review" },
  { value: "ops", label: "Ops" },
] as const;

const priorityOptions = [
  { value: "normal", label: "Normal" },
  { value: "high", label: "High" },
  { value: "low", label: "Low" },
] as const;

type RequestType = (typeof requestTypeOptions)[number]["value"];
type DraftPriority = (typeof priorityOptions)[number]["value"];
type DraftFilter = RequestType | "all";
type PriorityFilter = DraftPriority | "all";
type DraftStatus = "open" | "done";
type StatusFilter = DraftStatus | "all";
type DraftQualityStatus = "ready" | "warning";
type DraftLoadState = "loading" | "ready" | "failed";
type DraftStorage = {
  backend?: string;
  s3_bucket?: string;
  s3_key?: string;
  local_path?: string;
};

type SavedDraft = {
  id: string;
  repo: string;
  branch: string;
  requestType?: RequestType;
  priority?: DraftPriority;
  surface?: string;
  task: string;
  savedAt: string;
  status?: DraftStatus;
};

function normalizeSavedDraft(value: unknown): SavedDraft | null {
  if (!value || typeof value !== "object") return null;
  const item = value as Partial<SavedDraft>;
  if (typeof item.id !== "string" || typeof item.task !== "string" || !item.task.trim()) return null;
  return {
    id: item.id,
    repo: typeof item.repo === "string" && item.repo.trim() ? item.repo : DEFAULT_REPO,
    branch: typeof item.branch === "string" && item.branch.trim() ? item.branch : DEFAULT_BRANCH,
    requestType: requestTypeOptions.some((option) => option.value === item.requestType) ? item.requestType : "bug",
    priority: priorityOptions.some((option) => option.value === item.priority) ? item.priority : "normal",
    surface: typeof item.surface === "string" ? item.surface : "",
    task: item.task,
    savedAt: typeof item.savedAt === "string" && item.savedAt.trim() ? item.savedAt : new Date().toISOString(),
    status: item.status === "done" ? "done" : "open",
  };
}

function mergeDrafts(drafts: SavedDraft[]) {
  const seen = new Set<string>();
  const result: SavedDraft[] = [];
  for (const draft of drafts) {
    if (seen.has(draft.id)) continue;
    seen.add(draft.id);
    result.push(draft);
  }
  return result;
}

function loadLegacySavedDrafts() {
  if (typeof window === "undefined") return [];
  try {
    const rawValue = window.localStorage.getItem(STORAGE_KEY);
    if (!rawValue) return [];
    const parsedValue = JSON.parse(rawValue) as SavedDraft[];
    if (!Array.isArray(parsedValue)) return [];
    return parsedValue
      .map((item) => normalizeSavedDraft(item))
      .filter((item): item is SavedDraft => Boolean(item))
      .slice(0, MAX_SAVED_DRAFTS);
  } catch {
    return [];
  }
}

function clearLegacySavedDrafts() {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(STORAGE_KEY);
}

async function readDraftsFromBackend() {
  const response = await adminFetch(`${API_BASE}/dev-inbox/drafts`, {
    cache: "no-store",
  });
  if (!response.ok) throw new Error(`Draft load failed: ${response.status}`);
  const data = (await response.json()) as { drafts?: unknown[]; storage?: DraftStorage };
  const drafts = (data.drafts || [])
    .map((item) => normalizeSavedDraft(item))
    .filter((item): item is SavedDraft => Boolean(item));
  return { drafts, storage: data.storage || {} };
}

async function saveDraftToBackend(draft: SavedDraft) {
  const response = await adminFetch(`${API_BASE}/dev-inbox/drafts`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(draft),
  });
  if (!response.ok) throw new Error(`Draft save failed: ${response.status}`);
  const data = (await response.json()) as { draft?: unknown; storage?: DraftStorage };
  const savedDraft = normalizeSavedDraft(data.draft);
  if (!savedDraft) throw new Error("Draft save returned an invalid draft.");
  return { draft: savedDraft, storage: data.storage || {} };
}

function describeDraftStorage(storage: DraftStorage) {
  if (storage.backend === "s3") {
    return `S3-backed draft store ready: ${storage.s3_key || "dev-inbox/drafts/index.json"}.`;
  }
  if (storage.backend === "local_file") {
    return "Local backend file draft store ready.";
  }
  return "Backend draft store ready.";
}

const modeCards = [
  {
    title: "Codex Cloud",
    status: "Account session",
    detail: "Use your OpenAI Codex account and connected GitHub repo for hosted tasks.",
    icon: Bot,
    action: "Open Codex",
    href: "https://chatgpt.com/codex",
  },
  {
    title: "Local Codex",
    status: "VS Code parity",
    detail: "Keep the same repo-local AGENTS.md and working-tree approval rhythm.",
    icon: TerminalSquare,
    action: "Local workflow",
    href: "#task-draft",
  },
  {
    title: "GitHub PR Loop",
    status: "Review first",
    detail: "Let Codex work on a branch, then use PR checks before merge or deploy.",
    icon: GitPullRequest,
    action: "Open GitHub",
    href: "https://github.com/Andy-JunXiong/ai-radar-aws",
  },
];

const guardrails = [
  "No OpenAI passwords or long-lived keys in the browser.",
  "No direct push to main from this page.",
  "No deployment without an explicit human command.",
  "PR, test, and review status stay visible before merge.",
];

const taskTemplateOptions = [
  {
    label: "UI bug",
    requestType: "bug",
    priority: "high",
    surface: "/signals/detail",
    task: "Fix a focused UI bug and validate the affected route in both Navy and Light.",
  },
  {
    label: "Visual polish",
    requestType: "feature",
    priority: "normal",
    surface: "/architecture/signal-lifecycle-demo",
    task: "Improve one frontend visual surface without changing workflow semantics or backend behavior.",
  },
  {
    label: "Backend gate review",
    requestType: "review",
    priority: "high",
    surface: "backend verification gate",
    task: "Review a small backend service change for verification-gate regressions and preserve downstream action gates.",
  },
  {
    label: "Ops read-only",
    requestType: "ops",
    priority: "high",
    surface: "deployment or runtime status",
    task: "Inspect the reported operational issue with read-only checks and recommend the safest next command.",
  },
  {
    label: "Current diff review",
    requestType: "review",
    priority: "normal",
    surface: "current working tree",
    task: "Summarize current diff and recommend the safest next validation command without committing or pushing.",
  },
] as const satisfies ReadonlyArray<{
  label: string;
  requestType: RequestType;
  priority: DraftPriority;
  surface: string;
  task: string;
}>;

export default function CodexWorkbenchPage() {
  const [repo, setRepo] = useState(DEFAULT_REPO);
  const [branch, setBranch] = useState(DEFAULT_BRANCH);
  const [requestType, setRequestType] = useState<RequestType>("bug");
  const [priority, setPriority] = useState<DraftPriority>("normal");
  const [surface, setSurface] = useState<string>("/signals/detail");
  const [task, setTask] = useState<string>(taskTemplateOptions[0].task);
  const [draftTypeFilter, setDraftTypeFilter] = useState<DraftFilter>("all");
  const [draftPriorityFilter, setDraftPriorityFilter] = useState<PriorityFilter>("all");
  const [draftStatusFilter, setDraftStatusFilter] = useState<StatusFilter>("all");
  const [copyState, setCopyState] = useState<"idle" | "copied" | "failed">("idle");
  const [copyHandoffState, setCopyHandoffState] = useState<"idle" | "copied" | "failed">("idle");
  const [savedDraftCopyState, setSavedDraftCopyState] = useState<Record<string, "copied" | "failed">>({});
  const [saveState, setSaveState] = useState<"idle" | "saved" | "failed">("idle");
  const [draftLoadState, setDraftLoadState] = useState<DraftLoadState>("loading");
  const [draftStoreMessage, setDraftStoreMessage] = useState("Loading backend drafts.");
  const [savedDrafts, setSavedDrafts] = useState<SavedDraft[]>([]);

  useEffect(() => {
    let cancelled = false;

    async function loadDrafts() {
      try {
        const backendResult = await readDraftsFromBackend();
        const legacyDrafts = loadLegacySavedDrafts();
        const migratedDrafts: SavedDraft[] = [];
        let latestStorage = backendResult.storage;

        for (const draft of legacyDrafts) {
          const migrated = await saveDraftToBackend(draft);
          migratedDrafts.push(migrated.draft);
          latestStorage = migrated.storage;
        }

        if (legacyDrafts.length) {
          clearLegacySavedDrafts();
        }

        if (cancelled) return;
        const nextDrafts = mergeDrafts([...migratedDrafts, ...backendResult.drafts]).slice(0, MAX_SAVED_DRAFTS);
        setSavedDrafts(nextDrafts);
        setDraftLoadState("ready");
        setDraftStoreMessage(
          legacyDrafts.length
            ? `${describeDraftStorage(latestStorage)} Migrated ${legacyDrafts.length} browser draft(s).`
            : describeDraftStorage(latestStorage)
        );
      } catch {
        if (cancelled) return;
        const legacyDrafts = loadLegacySavedDrafts();
        setSavedDrafts(legacyDrafts);
        setDraftLoadState("failed");
        setDraftStoreMessage(
          legacyDrafts.length
            ? "Backend draft store is unavailable. Showing browser legacy drafts only."
            : "Backend draft store is unavailable."
        );
      }
    }

    void loadDrafts();

    return () => {
      cancelled = true;
    };
  }, []);

  const taskDraft = useMemo(
    () =>
      [
        "Mode: Development",
        `Repo: ${repo.trim() || DEFAULT_REPO}`,
        `Branch/base: ${branch.trim() || DEFAULT_BRANCH}`,
        `Request type: ${requestType}`,
        `Priority: ${priority}`,
        `Affected surface: ${surface.trim() || "not specified"}`,
        "",
        "Task:",
        task.trim() || "Describe the smallest safe development slice.",
        "",
        "AI Radar boundaries:",
        "- Follow AGENTS.md and the closest repo instructions.",
        "- Keep the patch narrow and preserve verification / Project Takeaway gates.",
        "- Do not commit, push, open PRs, or deploy unless explicitly asked.",
        "- Report files changed, validation run, and manual testing still needed.",
      ].join("\n"),
    [branch, priority, repo, requestType, surface, task]
  );

  const localHandoffDraft = useMemo(
    () =>
      buildLocalCodexHandoff({
        repo: repo.trim() || DEFAULT_REPO,
        branch: branch.trim() || DEFAULT_BRANCH,
        requestType,
        priority,
        surface: surface.trim(),
        task: task.trim(),
      }),
    [branch, priority, repo, requestType, surface, task]
  );

  const draftQualityChecks = useMemo(
    () =>
      buildDraftQualityChecks({
        requestType,
        priority,
        surface: surface.trim(),
        task: task.trim(),
      }),
    [priority, requestType, surface, task]
  );

  const qualityWarningCount = draftQualityChecks.filter((check) => check.status === "warning").length;

  const filteredSavedDrafts = useMemo(
    () =>
      savedDrafts.filter((draft) => {
        const typeMatch = draftTypeFilter === "all" || (draft.requestType || "bug") === draftTypeFilter;
        const priorityMatch = draftPriorityFilter === "all" || (draft.priority || "normal") === draftPriorityFilter;
        const statusMatch = draftStatusFilter === "all" || (draft.status || "open") === draftStatusFilter;
        return typeMatch && priorityMatch && statusMatch;
      }),
    [draftPriorityFilter, draftStatusFilter, draftTypeFilter, savedDrafts]
  );

  const githubLinks = useMemo(
    () => buildGithubLinks(repo.trim() || DEFAULT_REPO, branch.trim() || DEFAULT_BRANCH),
    [branch, repo]
  );

  function applyTemplate(template: (typeof taskTemplateOptions)[number]) {
    setRequestType(template.requestType);
    setPriority(template.priority);
    setSurface(template.surface);
    setTask(template.task);
    setCopyState("idle");
    setCopyHandoffState("idle");
    setSaveState("idle");
  }

  async function copyTaskDraft() {
    try {
      await navigator.clipboard.writeText(taskDraft);
      setCopyState("copied");
    } catch {
      setCopyState("failed");
    }
  }

  async function copyLocalHandoff() {
    try {
      await navigator.clipboard.writeText(localHandoffDraft);
      setCopyHandoffState("copied");
    } catch {
      setCopyHandoffState("failed");
    }
  }

  async function copySavedDraftHandoff(draft: SavedDraft) {
    const handoff = buildLocalCodexHandoff({
      repo: draft.repo || DEFAULT_REPO,
      branch: draft.branch || DEFAULT_BRANCH,
      requestType: draft.requestType || "bug",
      priority: draft.priority || "normal",
      surface: draft.surface || "",
      task: draft.task || "",
    });

    try {
      await navigator.clipboard.writeText(handoff);
      setSavedDraftCopyState((current) => ({ ...current, [draft.id]: "copied" }));
    } catch {
      setSavedDraftCopyState((current) => ({ ...current, [draft.id]: "failed" }));
    }
  }

  async function saveCurrentDraft() {
    const normalizedTask = task.trim();
    if (!normalizedTask) return;

    try {
      const nextDraft: SavedDraft = {
        id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        repo: repo.trim() || DEFAULT_REPO,
        branch: branch.trim() || DEFAULT_BRANCH,
        requestType,
        priority,
        surface: surface.trim(),
        task: normalizedTask,
        savedAt: new Date().toISOString(),
        status: "open",
      };
      const saved = await saveDraftToBackend(nextDraft);
      setSavedDrafts(mergeDrafts([saved.draft, ...savedDrafts]).slice(0, MAX_SAVED_DRAFTS));
      setDraftLoadState("ready");
      setDraftStoreMessage(describeDraftStorage(saved.storage));
      setSaveState("saved");
    } catch {
      setSaveState("failed");
      setDraftLoadState("failed");
      setDraftStoreMessage("Backend draft save failed. Check the local backend and admin session.");
    }
  }

  function restoreDraft(draft: SavedDraft) {
    setRepo(draft.repo || DEFAULT_REPO);
    setBranch(draft.branch || DEFAULT_BRANCH);
    setRequestType(draft.requestType || "bug");
    setPriority(draft.priority || "normal");
    setSurface(draft.surface || "");
    setTask(draft.task || "");
    setCopyState("idle");
    setCopyHandoffState("idle");
    setSavedDraftCopyState({});
    setSaveState("idle");
  }

  async function deleteDraft(draftId: string) {
    try {
      const response = await adminFetch(`${API_BASE}/dev-inbox/drafts/${encodeURIComponent(draftId)}`, {
        method: "DELETE",
      });
      if (!response.ok) throw new Error(`Draft delete failed: ${response.status}`);
      setSavedDrafts(savedDrafts.filter((draft) => draft.id !== draftId));
      setSavedDraftCopyState((current) => {
        const remaining = { ...current };
        delete remaining[draftId];
        return remaining;
      });
      setDraftLoadState("ready");
      const data = (await response.json()) as { storage?: DraftStorage };
      setDraftStoreMessage(describeDraftStorage(data.storage || {}));
    } catch {
      setSaveState("failed");
      setDraftLoadState("failed");
      setDraftStoreMessage("Backend draft delete failed. Check the local backend and admin session.");
    }
  }

  async function toggleDraftStatus(draftId: string) {
    const currentDraft = savedDrafts.find((draft) => draft.id === draftId);
    const nextStatus: DraftStatus = (currentDraft?.status || "open") === "open" ? "done" : "open";

    try {
      const response = await adminFetch(`${API_BASE}/dev-inbox/drafts/${encodeURIComponent(draftId)}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: nextStatus }),
      });
      if (!response.ok) throw new Error(`Draft update failed: ${response.status}`);
      const data = (await response.json()) as { draft?: unknown; storage?: DraftStorage };
      const updatedDraft = normalizeSavedDraft(data.draft);
      if (!updatedDraft) throw new Error("Draft update returned an invalid draft.");
      setSavedDrafts(savedDrafts.map((draft) => (draft.id === draftId ? updatedDraft : draft)));
      setDraftLoadState("ready");
      setDraftStoreMessage(describeDraftStorage(data.storage || {}));
    } catch {
      setSaveState("failed");
      setDraftLoadState("failed");
      setDraftStoreMessage("Backend draft status update failed. Check the local backend and admin session.");
    }
  }

  return (
    <AppContainer style={pageShellStyle}>
      <PageHeader
        title="Dev Inbox"
        description="Capture AI Radar bugs, improvements, and coding-agent handoffs without turning the product into an IDE."
      />

      <section style={heroPanelStyle}>
        <div style={heroCopyStyle}>
          <div style={eyebrowStyle}>
            <FileCode2 size={16} strokeWidth={2.3} />
            Development intake
          </div>
          <h2 style={heroTitleStyle}>Keep the issue capture close to the product.</h2>
          <p style={heroTextStyle}>
            Use AI Radar to capture bugs, improvements, and clean handoff drafts. Keep real code execution in local
            Codex, VS Code, Codex Cloud, GitHub, and CI.
          </p>
          <div style={heroActionRowStyle}>
            <a href="https://chatgpt.com/codex" target="_blank" rel="noreferrer" style={primaryActionStyle}>
              <Bot size={16} strokeWidth={2.3} />
              Open Codex Cloud
              <ExternalLink size={14} strokeWidth={2.4} />
            </a>
            <Link href="/admin/projects" style={secondaryActionStyle}>
              <GitBranch size={16} strokeWidth={2.3} />
              Project registry
            </Link>
          </div>
        </div>

        <div style={readinessPanelStyle}>
          <div style={readinessHeaderStyle}>Connection boundary</div>
          <div style={readinessGridStyle}>
            <Metric label="OpenAI auth" value="External" />
            <Metric label="GitHub writes" value="PR only" />
            <Metric label="AI Radar secrets" value="None" />
            <Metric label="Deploy path" value="Manual" />
          </div>
        </div>
      </section>

      <section style={sectionStyle}>
        <div style={sectionHeaderStyle}>
          <div>
            <div style={sectionEyebrowStyle}>Access modes</div>
            <h2 style={sectionTitleStyle}>Choose the execution surface</h2>
          </div>
          <span style={countChipStyle}>backend draft store</span>
        </div>

        <div style={modeGridStyle}>
          {modeCards.map((card) => {
            const Icon = card.icon;
            const isExternal = card.href.startsWith("http");
            const content = (
              <article style={modeCardStyle}>
                <div style={modeTopRowStyle}>
                  <span style={iconShellStyle}>
                    <Icon size={18} strokeWidth={2.3} />
                  </span>
                  <span style={chipStyle}>{card.status}</span>
                </div>
                <h3 style={cardTitleStyle}>{card.title}</h3>
                <p style={cardTextStyle}>{card.detail}</p>
                <span style={cardActionStyle}>
                  {card.action}
                  {isExternal ? <ExternalLink size={14} strokeWidth={2.4} /> : null}
                </span>
              </article>
            );

            return isExternal ? (
              <a key={card.title} href={card.href} target="_blank" rel="noreferrer" style={cardLinkStyle}>
                {content}
              </a>
            ) : (
              <Link key={card.title} href={card.href} style={cardLinkStyle}>
                {content}
              </Link>
            );
          })}
        </div>
      </section>

      <section style={sectionStyle}>
        <div style={sectionHeaderStyle}>
          <div>
            <div style={sectionEyebrowStyle}>GitHub read-only loop</div>
            <h2 style={sectionTitleStyle}>Check PR and CI status outside the prompt</h2>
          </div>
          <span style={countChipStyle}>links only</span>
        </div>
        <div style={githubLoopGridStyle}>
          <a href={githubLinks.repo} target="_blank" rel="noreferrer" style={githubLoopLinkStyle}>
            <FileCode2 size={17} strokeWidth={2.3} />
            Repo
            <ExternalLink size={13} strokeWidth={2.4} />
          </a>
          <a href={githubLinks.branch} target="_blank" rel="noreferrer" style={githubLoopLinkStyle}>
            <GitBranch size={17} strokeWidth={2.3} />
            Branch
            <ExternalLink size={13} strokeWidth={2.4} />
          </a>
          <a href={githubLinks.pulls} target="_blank" rel="noreferrer" style={githubLoopLinkStyle}>
            <GitPullRequest size={17} strokeWidth={2.3} />
            Pull requests
            <ExternalLink size={13} strokeWidth={2.4} />
          </a>
          <a href={githubLinks.actions} target="_blank" rel="noreferrer" style={githubLoopLinkStyle}>
            <ListChecks size={17} strokeWidth={2.3} />
            Actions
            <ExternalLink size={13} strokeWidth={2.4} />
          </a>
        </div>
        <p style={readOnlyNoteStyle}>
          This panel derives links from the repo and branch fields only. It does not call GitHub APIs, create PRs,
          change branches, or read private credentials.
        </p>
      </section>

      <section id="task-draft" style={taskLayoutStyle}>
        <div style={sectionStyle}>
          <div style={sectionHeaderStyle}>
            <div>
              <div style={sectionEyebrowStyle}>Task draft</div>
              <h2 style={sectionTitleStyle}>Prepare the next development handoff</h2>
            </div>
            <div style={actionClusterStyle}>
              <button type="button" onClick={() => void saveCurrentDraft()} style={secondaryButtonStyle}>
                <Save size={15} strokeWidth={2.4} />
                {saveState === "saved" ? "Saved" : saveState === "failed" ? "Save failed" : "Save draft"}
              </button>
              <button type="button" onClick={() => void copyTaskDraft()} style={secondaryButtonStyle}>
                <Copy size={15} strokeWidth={2.4} />
                {copyState === "copied" ? "Copied" : copyState === "failed" ? "Copy failed" : "Copy draft"}
              </button>
              <button type="button" onClick={() => void copyLocalHandoff()} style={primaryCompactButtonStyle}>
                <TerminalSquare size={15} strokeWidth={2.4} />
                {copyHandoffState === "copied"
                  ? "Handoff copied"
                  : copyHandoffState === "failed"
                    ? "Handoff failed"
                    : "Copy local handoff"}
              </button>
            </div>
          </div>

          <div style={formGridStyle}>
            <Field label="GitHub repo">
              <input value={repo} onChange={(event) => setRepo(event.target.value)} style={inputStyle} />
            </Field>
            <Field label="Branch / base">
              <input value={branch} onChange={(event) => setBranch(event.target.value)} style={inputStyle} />
            </Field>
            <Field label="Request type">
              <select
                value={requestType}
                onChange={(event) => setRequestType(event.target.value as RequestType)}
                style={inputStyle}
              >
                {requestTypeOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Priority">
              <select
                value={priority}
                onChange={(event) => setPriority(event.target.value as DraftPriority)}
                style={inputStyle}
              >
                {priorityOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </Field>
            <div style={wideFieldStyle}>
              <Field label="Affected surface">
                <input
                  value={surface}
                  onChange={(event) => setSurface(event.target.value)}
                  placeholder="/signals/detail, manual upload, admin metrics..."
                  style={inputStyle}
                />
              </Field>
            </div>
            <div style={wideFieldStyle}>
              <Field label="Development request">
                <textarea value={task} onChange={(event) => setTask(event.target.value)} style={textareaStyle} />
              </Field>
            </div>
          </div>

          <div style={templateRowStyle}>
            {taskTemplateOptions.map((template) => (
              <button key={template.label} type="button" onClick={() => applyTemplate(template)} style={templateButtonStyle}>
                {template.label}
              </button>
            ))}
          </div>

          <div style={qualityGateStyle}>
            <div style={qualityGateHeaderStyle}>
              <div>
                <div style={sectionEyebrowStyle}>Draft quality gate</div>
                <h3 style={qualityTitleStyle}>
                  {qualityWarningCount ? `${qualityWarningCount} item(s) need attention` : "Ready to hand off"}
                </h3>
              </div>
              <span style={qualityBadgeStyle(qualityWarningCount ? "warning" : "ready")}>
                {qualityWarningCount ? "Review first" : "Ready"}
              </span>
            </div>
            <div style={qualityCheckGridStyle}>
              {draftQualityChecks.map((check) => {
                const Icon = check.status === "ready" ? CheckCircle2 : AlertCircle;
                return (
                  <div key={check.label} style={qualityCheckStyle(check.status)}>
                    <Icon size={16} strokeWidth={2.4} />
                    <span>
                      <strong style={qualityCheckLabelStyle}>{check.label}</strong>
                      <small style={qualityCheckDetailStyle}>{check.detail}</small>
                    </span>
                  </div>
                );
              })}
            </div>
          </div>

          <pre style={draftStyle}>{taskDraft}</pre>
          <div style={handoffPreviewStyle}>
            <div style={sectionEyebrowStyle}>Local Codex handoff preview</div>
            <pre style={handoffDraftStyle}>{localHandoffDraft}</pre>
          </div>
        </div>

        <aside style={sectionStyle}>
          <div style={sectionEyebrowStyle}>Dev Inbox</div>
          <h2 style={sectionTitleStyle}>Saved bugs and development ideas</h2>
          <div style={filterPanelStyle}>
            <span style={filterLabelStyle}>
              <Filter size={14} strokeWidth={2.4} />
              Filter
            </span>
            <select
              value={draftTypeFilter}
              onChange={(event) => setDraftTypeFilter(event.target.value as DraftFilter)}
              style={smallSelectStyle}
            >
              <option value="all">All types</option>
              {requestTypeOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            <select
              value={draftPriorityFilter}
              onChange={(event) => setDraftPriorityFilter(event.target.value as PriorityFilter)}
              style={smallSelectStyle}
            >
              <option value="all">All priorities</option>
              {priorityOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            <select
              value={draftStatusFilter}
              onChange={(event) => setDraftStatusFilter(event.target.value as StatusFilter)}
              style={smallSelectStyle}
            >
              <option value="all">All statuses</option>
              <option value="open">Open</option>
              <option value="done">Done</option>
            </select>
            <span style={filterCountStyle}>
              {filteredSavedDrafts.length}/{savedDrafts.length}
            </span>
          </div>
          <div style={draftStoreNoticeStyle(draftLoadState)}>
            {draftStoreMessage}
          </div>
          <div style={draftListStyle}>
            {filteredSavedDrafts.length ? (
              filteredSavedDrafts.map((draft) => (
                <article key={draft.id} style={savedDraftCardStyle}>
                  <button type="button" onClick={() => restoreDraft(draft)} style={savedDraftMainButtonStyle}>
                    <span style={savedDraftTitleStyle}>{summarizeDraft(draft.task)}</span>
                    <span style={savedDraftChipRowStyle}>
                      <span style={savedDraftChipStyle}>{draft.requestType || "bug"}</span>
                      <span style={savedDraftChipStyle}>{draft.priority || "normal"}</span>
                      <span style={savedDraftStatusChipStyle(draft.status || "open")}>
                        {(draft.status || "open") === "done" ? "done" : "open"}
                      </span>
                      {draft.surface ? <span style={savedDraftChipStyle}>{draft.surface}</span> : null}
                    </span>
                    <span style={savedDraftMetaStyle}>
                      <Clock3 size={13} strokeWidth={2.4} />
                      {formatSavedAt(draft.savedAt)}
                    </span>
                    <span style={savedDraftRepoStyle}>
                      {draft.repo} / {draft.branch}
                    </span>
                  </button>
                  <div style={savedDraftActionStackStyle}>
                    <button
                      type="button"
                      onClick={() => void toggleDraftStatus(draft.id)}
                      style={savedDraftStatusButtonStyle(draft.status || "open")}
                    >
                      <CheckCircle2 size={14} strokeWidth={2.4} />
                      {(draft.status || "open") === "done" ? "Reopen" : "Mark done"}
                    </button>
                    <button type="button" onClick={() => void copySavedDraftHandoff(draft)} style={savedDraftCopyButtonStyle}>
                      <Copy size={14} strokeWidth={2.4} />
                      {savedDraftCopyState[draft.id] === "copied"
                        ? "Copied"
                        : savedDraftCopyState[draft.id] === "failed"
                          ? "Failed"
                          : "Handoff"}
                    </button>
                    <button type="button" onClick={() => void deleteDraft(draft.id)} style={deleteDraftButtonStyle}>
                      <Trash2 size={14} strokeWidth={2.4} />
                    </button>
                  </div>
                </article>
              ))
            ) : savedDrafts.length ? (
              <div style={emptyDraftStateStyle}>No saved drafts match the current filters.</div>
            ) : (
              <div style={emptyDraftStateStyle}>
                Save UI bugs, product ideas, or review tasks here before sending them to local Codex or Codex Cloud.
              </div>
            )}
          </div>

          <div style={asideDividerStyle} />

          <div style={sectionEyebrowStyle}>Guardrails</div>
          <h2 style={sectionTitleStyle}>Keep the control plane outside the prompt</h2>
          <div style={guardrailListStyle}>
            {guardrails.map((item) => (
              <div key={item} style={guardrailItemStyle}>
                <CheckCircle2 size={16} strokeWidth={2.4} />
                <span>{item}</span>
              </div>
            ))}
          </div>

          <div style={boundaryNoticeStyle}>
            <div style={noticeLabelStyle}>
              <ShieldCheck size={15} strokeWidth={2.4} />
              Human approval boundary
            </div>
            <p style={noticeTextStyle}>
              This page can stage development intent. Merge, push, PR creation, and deployment stay explicit actions.
            </p>
          </div>

          <Link href="/workspace/projects/review" style={wideSecondaryActionStyle}>
            <ClipboardCheck size={16} strokeWidth={2.3} />
            Review Inbox
          </Link>
        </aside>
      </section>
    </AppContainer>
  );
}

function summarizeDraft(value: string) {
  const normalized = value.replace(/\s+/g, " ").trim();
  if (!normalized) return "Untitled draft";
  return normalized.length > 88 ? `${normalized.slice(0, 85)}...` : normalized;
}

function formatSavedAt(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Saved";
  return date.toLocaleString();
}

function buildLocalCodexHandoff({
  repo,
  branch,
  requestType,
  priority,
  surface,
  task,
}: {
  repo: string;
  branch: string;
  requestType: RequestType;
  priority: DraftPriority;
  surface: string;
  task: string;
}) {
  const normalizedSurface = surface || "not specified";
  const routeCheck =
    surface.startsWith("/")
      ? `curl.exe -L -sS -o NUL -w "%{http_code} %{time_total}\\n" "http://127.0.0.1:3000${surface}"`
      : "Open the affected surface manually and verify the visible behavior.";

  const validation =
    requestType === "ops"
      ? [
          "Run only read-only checks unless the user explicitly approves a write action.",
          "Do not deploy or change AWS resources from this handoff.",
          "Report the observed status and the safest next command.",
        ]
      : [
          "Run targeted lint for touched frontend/backend files.",
          "Run `npm.cmd run build` if frontend files changed.",
          "Run `npm.cmd run test:guidance` if visible workflow language or Operator Guidance changed.",
          "Run `git diff --check` before handoff.",
          `Route/manual check: ${routeCheck}`,
        ];

  return [
    "Mode: Development",
    `Scope: ${normalizedSurface}`,
    `Repo: ${repo}`,
    `Branch/base: ${branch}`,
    `Request type: ${requestType}`,
    `Priority: ${priority}`,
    "",
    "Task:",
    task || "Describe the smallest safe development slice.",
    "",
    "Implementation boundaries:",
    "- Keep the patch narrow and inspect only the directly related files.",
    "- Preserve AGENTS.md boundaries, verification gates, and Project Takeaway action gates.",
    "- Do not commit, push, open PRs, deploy, or run AWS write commands unless explicitly asked.",
    "- Do not add secrets, tokens, or long-lived credentials.",
    "",
    "Validation plan:",
    ...validation.map((item) => `- ${item}`),
    "",
    "Manual verification:",
    `- Open ${normalizedSurface} after the change.`,
    "- Reproduce the reported issue or intended workflow.",
    "- Confirm the visible result matches the requested behavior in both Navy and Light if the change is visual.",
    "",
    "Handoff requirements:",
    "- Report files changed.",
    "- Separate Codex-run validation from user/manual validation.",
    "- State any remaining manual test gaps.",
  ].join("\n");
}

function buildDraftQualityChecks({
  requestType,
  priority,
  surface,
  task,
}: {
  requestType: RequestType;
  priority: DraftPriority;
  surface: string;
  task: string;
}) {
  const normalizedTask = task.replace(/\s+/g, " ").trim();
  const normalizedSurface = surface.trim();
  const isRouteSurface = normalizedSurface.startsWith("/");
  const isVisualOrBug = requestType === "bug" || normalizedTask.toLowerCase().includes("visual");

  return [
    {
      label: "Scope",
      status: normalizedSurface && normalizedSurface !== "not specified" ? "ready" : "warning",
      detail: normalizedSurface
        ? "Affected surface is present."
        : "Add a route, module, or file family before copying the handoff.",
    },
    {
      label: "Task specificity",
      status: normalizedTask.length >= 32 ? "ready" : "warning",
      detail:
        normalizedTask.length >= 32
          ? "Request has enough detail for a narrow first pass."
          : "Describe the smallest visible bug, change, or review question.",
    },
    {
      label: "Manual check",
      status: !isVisualOrBug || isRouteSurface ? "ready" : "warning",
      detail:
        !isVisualOrBug || isRouteSurface
          ? "Manual verification can be routed from the handoff."
          : "For visual or bug work, prefer a concrete route such as /signals/detail.",
    },
    {
      label: "Priority fit",
      status: requestType !== "ops" || priority === "high" ? "ready" : "warning",
      detail:
        requestType !== "ops" || priority === "high"
          ? "Priority is consistent with the selected request type."
          : "Ops checks are usually high priority until classified.",
    },
  ] satisfies Array<{ label: string; status: DraftQualityStatus; detail: string }>;
}

function buildGithubLinks(repo: string, branch: string) {
  const repoSlug = normalizeRepoSlug(repo) || DEFAULT_REPO;
  const branchSlug = encodeURIComponent(branch || DEFAULT_BRANCH);
  const baseUrl = `https://github.com/${repoSlug}`;

  return {
    repo: baseUrl,
    branch: `${baseUrl}/tree/${branchSlug}`,
    pulls: `${baseUrl}/pulls`,
    actions: `${baseUrl}/actions`,
  };
}

function normalizeRepoSlug(value: string) {
  return value
    .trim()
    .replace(/^https?:\/\/github\.com\//i, "")
    .replace(/^git@github\.com:/i, "")
    .replace(/\.git$/i, "")
    .replace(/^\/+|\/+$/g, "");
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div style={metricStyle}>
      <span style={metricLabelStyle}>{label}</span>
      <strong style={metricValueStyle}>{value}</strong>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label style={fieldStyle}>
      <span style={fieldLabelStyle}>{label}</span>
      {children}
    </label>
  );
}

const pageShellStyle: CSSProperties = {
  maxWidth: "1360px",
};

const heroPanelStyle: CSSProperties = {
  border: "1px solid var(--app-surface-strong-border)",
  borderRadius: "8px",
  background: "var(--app-surface-bg)",
  padding: "clamp(22px, 3vw, 34px)",
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 360px), 1fr))",
  gap: "22px",
  alignItems: "stretch",
  marginBottom: "22px",
  boxShadow: "var(--app-surface-shadow)",
};

const heroCopyStyle: CSSProperties = {
  minWidth: 0,
};

const eyebrowStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: "8px",
  color: "var(--app-text-subtle)",
  fontSize: "12px",
  fontWeight: 850,
  letterSpacing: 0,
  textTransform: "uppercase",
};

const heroTitleStyle: CSSProperties = {
  margin: "12px 0 0",
  color: "var(--app-text-strong)",
  fontSize: "clamp(28px, 4vw, 46px)",
  lineHeight: 1.05,
  fontWeight: 850,
  letterSpacing: 0,
  maxWidth: "840px",
};

const heroTextStyle: CSSProperties = {
  margin: "16px 0 0",
  color: "var(--app-text-muted)",
  fontSize: "15px",
  lineHeight: 1.75,
  maxWidth: "820px",
};

const heroActionRowStyle: CSSProperties = {
  marginTop: "22px",
  display: "flex",
  gap: "10px",
  flexWrap: "wrap",
};

const primaryActionStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  gap: "8px",
  border: "1px solid var(--app-primary-action-border)",
  borderRadius: "8px",
  background: "var(--app-primary-action-bg)",
  color: "var(--app-primary-action-fg)",
  padding: "10px 13px",
  textDecoration: "none",
  fontSize: "14px",
  fontWeight: 800,
};

const secondaryActionStyle: CSSProperties = {
  ...primaryActionStyle,
  border: "1px solid var(--app-secondary-action-border)",
  background: "var(--app-secondary-action-bg)",
  color: "var(--app-secondary-action-fg)",
};

const readinessPanelStyle: CSSProperties = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  padding: "16px",
  display: "grid",
  alignContent: "center",
  gap: "12px",
};

const readinessHeaderStyle: CSSProperties = {
  color: "var(--app-text-subtle)",
  fontSize: "12px",
  fontWeight: 850,
  letterSpacing: 0,
  textTransform: "uppercase",
};

const readinessGridStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
  gap: "10px",
};

const metricStyle: CSSProperties = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-bg)",
  padding: "12px",
  minHeight: "78px",
};

const metricLabelStyle: CSSProperties = {
  display: "block",
  color: "var(--app-text-subtle)",
  fontSize: "11px",
  fontWeight: 850,
  letterSpacing: 0,
  textTransform: "uppercase",
};

const metricValueStyle: CSSProperties = {
  display: "block",
  marginTop: "8px",
  color: "var(--app-text-strong)",
  fontSize: "18px",
  lineHeight: 1.2,
};

const sectionStyle: CSSProperties = {
  border: "1px solid var(--app-surface-strong-border)",
  borderRadius: "8px",
  background: "var(--app-surface-bg)",
  padding: "20px",
  boxShadow: "var(--app-surface-shadow)",
};

const sectionHeaderStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "flex-start",
  gap: "14px",
  flexWrap: "wrap",
  marginBottom: "16px",
};

const actionClusterStyle: CSSProperties = {
  display: "flex",
  gap: "8px",
  flexWrap: "wrap",
  justifyContent: "flex-end",
};

const sectionEyebrowStyle: CSSProperties = {
  color: "var(--app-text-subtle)",
  fontSize: "12px",
  fontWeight: 850,
  letterSpacing: 0,
  textTransform: "uppercase",
};

const sectionTitleStyle: CSSProperties = {
  margin: "5px 0 0",
  color: "var(--app-text-strong)",
  fontSize: "22px",
  lineHeight: 1.15,
  fontWeight: 850,
  letterSpacing: 0,
};

const countChipStyle: CSSProperties = {
  border: "1px solid var(--app-chip-border)",
  borderRadius: "999px",
  background: "var(--app-chip-bg)",
  color: "var(--app-chip-fg)",
  padding: "7px 10px",
  fontSize: "12px",
  fontWeight: 800,
};

const modeGridStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 260px), 1fr))",
  gap: "14px",
};

const cardLinkStyle: CSSProperties = {
  display: "flex",
  textDecoration: "none",
  color: "inherit",
};

const modeCardStyle: CSSProperties = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  padding: "18px",
  minHeight: "210px",
  width: "100%",
  boxSizing: "border-box",
  display: "flex",
  flexDirection: "column",
};

const modeTopRowStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  gap: "10px",
};

const iconShellStyle: CSSProperties = {
  width: "34px",
  height: "34px",
  borderRadius: "8px",
  border: "1px solid var(--app-surface-border)",
  background: "var(--app-surface-bg)",
  color: "var(--app-text-muted)",
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  flexShrink: 0,
};

const chipStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  border: "1px solid var(--app-chip-border)",
  borderRadius: "999px",
  background: "var(--app-chip-bg)",
  color: "var(--app-chip-fg)",
  padding: "5px 10px",
  fontSize: "12px",
  fontWeight: 700,
  whiteSpace: "nowrap",
};

const cardTitleStyle: CSSProperties = {
  margin: "14px 0 9px",
  color: "var(--app-text-strong)",
  fontSize: "19px",
  lineHeight: 1.3,
  fontWeight: 850,
  letterSpacing: 0,
};

const cardTextStyle: CSSProperties = {
  margin: 0,
  color: "var(--app-text-muted)",
  fontSize: "14px",
  lineHeight: 1.7,
};

const cardActionStyle: CSSProperties = {
  marginTop: "auto",
  display: "inline-flex",
  alignItems: "center",
  gap: "7px",
  color: "var(--app-text-strong)",
  fontSize: "13px",
  fontWeight: 800,
};

const githubLoopGridStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 180px), 1fr))",
  gap: "10px",
};

const githubLoopLinkStyle: CSSProperties = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  color: "var(--app-text-strong)",
  minHeight: "54px",
  padding: "12px",
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  gap: "8px",
  textDecoration: "none",
  fontSize: "13px",
  fontWeight: 850,
};

const readOnlyNoteStyle: CSSProperties = {
  margin: "12px 0 0",
  color: "var(--app-text-muted)",
  fontSize: "13px",
  lineHeight: 1.65,
};

const taskLayoutStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 360px), 1fr))",
  gap: "18px",
  alignItems: "start",
  marginTop: "22px",
};

const secondaryButtonStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  gap: "8px",
  border: "1px solid var(--app-secondary-action-border)",
  borderRadius: "8px",
  background: "var(--app-secondary-action-bg)",
  color: "var(--app-secondary-action-fg)",
  padding: "9px 12px",
  fontSize: "13px",
  fontWeight: 800,
  cursor: "pointer",
};

const primaryCompactButtonStyle: CSSProperties = {
  ...secondaryButtonStyle,
  border: "1px solid var(--app-primary-action-border)",
  background: "var(--app-primary-action-bg)",
  color: "var(--app-primary-action-fg)",
};

const formGridStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 260px), 1fr))",
  gap: "14px",
};

const wideFieldStyle: CSSProperties = {
  gridColumn: "1 / -1",
};

const fieldStyle: CSSProperties = {
  display: "grid",
  gap: "8px",
};

const fieldLabelStyle: CSSProperties = {
  color: "var(--app-text-subtle)",
  fontSize: "12px",
  fontWeight: 850,
  letterSpacing: 0,
  textTransform: "uppercase",
};

const inputStyle: CSSProperties = {
  border: "1px solid var(--app-input-border)",
  borderRadius: "8px",
  background: "var(--app-input-bg)",
  color: "var(--app-input-fg)",
  padding: "12px 13px",
  fontSize: "14px",
  fontWeight: 650,
  minWidth: 0,
};

const textareaStyle: CSSProperties = {
  ...inputStyle,
  minHeight: "116px",
  lineHeight: 1.65,
  resize: "vertical",
};

const templateRowStyle: CSSProperties = {
  display: "flex",
  flexWrap: "wrap",
  gap: "8px",
  marginTop: "14px",
};

const templateButtonStyle: CSSProperties = {
  border: "1px solid var(--app-chip-border)",
  borderRadius: "999px",
  background: "var(--app-chip-bg)",
  color: "var(--app-chip-fg)",
  padding: "7px 10px",
  fontSize: "12px",
  fontWeight: 750,
  cursor: "pointer",
};

const qualityGateStyle: CSSProperties = {
  marginTop: "16px",
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  padding: "14px",
};

const qualityGateHeaderStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "flex-start",
  gap: "12px",
  flexWrap: "wrap",
};

const qualityTitleStyle: CSSProperties = {
  margin: "4px 0 0",
  color: "var(--app-text-strong)",
  fontSize: "16px",
  lineHeight: 1.25,
  fontWeight: 850,
};

const qualityBadgeStyle = (status: DraftQualityStatus): CSSProperties => ({
  border: status === "ready" ? "1px solid var(--app-success-border)" : "1px solid var(--app-warning-border)",
  borderRadius: "999px",
  background: status === "ready" ? "var(--app-success-bg)" : "var(--app-warning-bg)",
  color: status === "ready" ? "var(--app-success-fg)" : "var(--app-warning-fg)",
  padding: "6px 9px",
  fontSize: "12px",
  fontWeight: 850,
});

const qualityCheckGridStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 220px), 1fr))",
  gap: "10px",
  marginTop: "12px",
};

const qualityCheckStyle = (status: DraftQualityStatus): CSSProperties => ({
  border: status === "ready" ? "1px solid var(--app-success-border)" : "1px solid var(--app-warning-border)",
  borderRadius: "8px",
  background: status === "ready" ? "var(--app-success-bg)" : "var(--app-warning-bg)",
  color: status === "ready" ? "var(--app-success-fg)" : "var(--app-warning-fg)",
  padding: "10px",
  display: "flex",
  alignItems: "flex-start",
  gap: "8px",
  fontSize: "12px",
  lineHeight: 1.45,
});

const qualityCheckLabelStyle: CSSProperties = {
  display: "block",
};

const qualityCheckDetailStyle: CSSProperties = {
  display: "block",
  marginTop: "4px",
  fontSize: "11px",
  lineHeight: 1.45,
};

const filterPanelStyle: CSSProperties = {
  marginTop: "14px",
  display: "flex",
  alignItems: "center",
  gap: "8px",
  flexWrap: "wrap",
};

const filterLabelStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: "6px",
  color: "var(--app-text-subtle)",
  fontSize: "12px",
  fontWeight: 850,
  textTransform: "uppercase",
};

const smallSelectStyle: CSSProperties = {
  border: "1px solid var(--app-input-border)",
  borderRadius: "8px",
  background: "var(--app-input-bg)",
  color: "var(--app-input-fg)",
  padding: "8px 9px",
  fontSize: "12px",
  fontWeight: 750,
  minWidth: "130px",
};

const filterCountStyle: CSSProperties = {
  border: "1px solid var(--app-chip-border)",
  borderRadius: "999px",
  background: "var(--app-chip-bg)",
  color: "var(--app-chip-fg)",
  padding: "6px 9px",
  fontSize: "12px",
  fontWeight: 850,
};

const draftStoreNoticeStyle = (state: DraftLoadState): CSSProperties => ({
  marginTop: "12px",
  border: state === "failed" ? "1px solid var(--app-warning-border)" : "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: state === "failed" ? "var(--app-warning-bg)" : "var(--app-surface-muted-bg)",
  color: state === "failed" ? "var(--app-warning-fg)" : "var(--app-text-muted)",
  padding: "10px 12px",
  fontSize: "12px",
  lineHeight: 1.5,
  fontWeight: 750,
});

const draftStyle: CSSProperties = {
  margin: "16px 0 0",
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  color: "var(--app-text-muted)",
  padding: "14px",
  overflowX: "auto",
  whiteSpace: "pre-wrap",
  wordBreak: "break-word",
  fontSize: "13px",
  lineHeight: 1.65,
};

const handoffPreviewStyle: CSSProperties = {
  marginTop: "14px",
  border: "1px solid var(--app-info-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  padding: "13px",
};

const handoffDraftStyle: CSSProperties = {
  ...draftStyle,
  margin: "10px 0 0",
  background: "var(--app-surface-bg)",
};

const guardrailListStyle: CSSProperties = {
  display: "grid",
  gap: "10px",
  marginTop: "16px",
};

const draftListStyle: CSSProperties = {
  display: "grid",
  gap: "10px",
  marginTop: "16px",
};

const savedDraftCardStyle: CSSProperties = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  display: "grid",
  gridTemplateColumns: "minmax(0, 1fr) auto",
  gap: "8px",
  alignItems: "stretch",
  padding: "10px",
};

const savedDraftMainButtonStyle: CSSProperties = {
  border: 0,
  background: "transparent",
  color: "inherit",
  padding: 0,
  textAlign: "left",
  cursor: "pointer",
  display: "grid",
  gap: "7px",
  minWidth: 0,
};

const savedDraftTitleStyle: CSSProperties = {
  color: "var(--app-text-strong)",
  fontSize: "13px",
  lineHeight: 1.45,
  fontWeight: 800,
};

const savedDraftChipRowStyle: CSSProperties = {
  display: "flex",
  flexWrap: "wrap",
  gap: "6px",
};

const savedDraftChipStyle: CSSProperties = {
  border: "1px solid var(--app-chip-border)",
  borderRadius: "999px",
  background: "var(--app-chip-bg)",
  color: "var(--app-chip-fg)",
  padding: "3px 7px",
  fontSize: "10px",
  lineHeight: 1.2,
  fontWeight: 800,
  maxWidth: "100%",
  overflowWrap: "anywhere",
};

const savedDraftStatusChipStyle = (status: DraftStatus): CSSProperties => ({
  border: status === "done" ? "1px solid var(--app-success-border)" : "1px solid var(--app-warning-border)",
  borderRadius: "999px",
  background: status === "done" ? "var(--app-success-bg)" : "var(--app-warning-bg)",
  color: status === "done" ? "var(--app-success-fg)" : "var(--app-warning-fg)",
  padding: "3px 7px",
  fontSize: "10px",
  lineHeight: 1.2,
  fontWeight: 850,
});

const savedDraftMetaStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: "6px",
  color: "var(--app-text-subtle)",
  fontSize: "11px",
  fontWeight: 750,
};

const savedDraftRepoStyle: CSSProperties = {
  color: "var(--app-text-muted)",
  fontSize: "11px",
  lineHeight: 1.4,
  wordBreak: "break-word",
};

const savedDraftActionStackStyle: CSSProperties = {
  display: "grid",
  gap: "8px",
  alignContent: "start",
};

const savedDraftCopyButtonStyle: CSSProperties = {
  border: "1px solid var(--app-secondary-action-border)",
  borderRadius: "8px",
  background: "var(--app-secondary-action-bg)",
  color: "var(--app-secondary-action-fg)",
  minHeight: "34px",
  padding: "8px 9px",
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  gap: "6px",
  cursor: "pointer",
  fontSize: "11px",
  fontWeight: 800,
  whiteSpace: "nowrap",
};

const savedDraftStatusButtonStyle = (status: DraftStatus): CSSProperties => ({
  border: status === "done" ? "1px solid var(--app-success-border)" : "1px solid var(--app-secondary-action-border)",
  borderRadius: "8px",
  background: status === "done" ? "var(--app-success-bg)" : "var(--app-secondary-action-bg)",
  color: status === "done" ? "var(--app-success-fg)" : "var(--app-secondary-action-fg)",
  minHeight: "34px",
  padding: "8px 9px",
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  gap: "6px",
  cursor: "pointer",
  fontSize: "11px",
  fontWeight: 800,
  whiteSpace: "nowrap",
});

const deleteDraftButtonStyle: CSSProperties = {
  border: "1px solid var(--app-danger-border)",
  borderRadius: "8px",
  background: "var(--app-danger-bg)",
  color: "var(--app-danger-fg)",
  width: "34px",
  minHeight: "34px",
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  cursor: "pointer",
};

const emptyDraftStateStyle: CSSProperties = {
  border: "1px dashed var(--app-surface-border)",
  borderRadius: "8px",
  color: "var(--app-text-muted)",
  padding: "13px",
  fontSize: "13px",
  lineHeight: 1.65,
};

const asideDividerStyle: CSSProperties = {
  height: "1px",
  background: "var(--app-surface-border)",
  margin: "18px 0",
};

const guardrailItemStyle: CSSProperties = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  color: "var(--app-text-muted)",
  padding: "11px 12px",
  display: "flex",
  alignItems: "flex-start",
  gap: "9px",
  fontSize: "13px",
  lineHeight: 1.55,
};

const boundaryNoticeStyle: CSSProperties = {
  marginTop: "16px",
  border: "1px solid var(--app-warning-border)",
  borderRadius: "8px",
  background: "var(--app-warning-bg)",
  color: "var(--app-warning-fg)",
  padding: "13px",
};

const noticeLabelStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: "7px",
  fontSize: "12px",
  fontWeight: 850,
  letterSpacing: 0,
  textTransform: "uppercase",
};

const noticeTextStyle: CSSProperties = {
  margin: "8px 0 0",
  fontSize: "13px",
  lineHeight: 1.65,
};

const wideSecondaryActionStyle: CSSProperties = {
  ...secondaryActionStyle,
  width: "100%",
  marginTop: "16px",
};
