"use client";

import Image from "next/image";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { Database, FileText, FileUp, Radar, ShieldCheck, UploadCloud } from "lucide-react";
import AppContainer from "@/components/AppContainer";
import RequireAdminAuth from "@/components/RequireAdminAuth";
import VerificationGateNote from "@/components/VerificationGateNote";
import { API_BASE } from "@/lib/api";
import { adminFetch, getStoredAdminToken } from "@/lib/adminAuth";

type ManualAnalysis = {
  summary?: string;
  why_it_matters?: string;
  relevance_to_projects?: string | Record<string, unknown>;
  relevance_to_career?: string;
  synthesized_insight?: string;
};

type UploadedManualFile = {
  original_filename: string;
  stored_filename: string;
  file_kind: string;
  preview_text?: string;
  message?: string;
  source_url?: string;
  fetched_url?: string;
  article_fetch_status?: "fetched" | "failed" | "skipped" | string;
  article_title?: string;
  article_excerpt?: string;
  article_text_char_count?: number;
  article_fetch_error?: string;
};

type VerificationMetadata = {
  verification_status?: string;
  confidence_score?: number;
  confidence_label?: string;
  allowed_downstream_actions?: string[];
  blocked_downstream_actions?: string[];
  claim_support_summary?: Record<string, number>;
};

type ReviewPriorityFilter =
  | "all"
  | "do_not_act"
  | "review_required"
  | "review_before_action"
  | "ready_for_low_risk_review"
  | "unknown";

type WorkspaceStatusFilter = "all" | "workspace_saved" | "not_in_workspace";
type ManualHandoffFilter = "all" | "workspace_done" | "ready_for_signal_review" | "needs_insight" | "pending_analysis";

type ManualSessionSummary = {
  session_id: string;
  title?: string;
  created_at?: string;
  updated_at?: string;
  upload_reason?: string;
  intended_use?: string;
  cognitive_layer?: string;
  source_stated_limits?: string;
  source_stated_confidence?: {
    raw_text?: string;
    normalized_label?: string | null;
  } | string | null;
  source_stated_limits_not_applicable?: boolean;
  source_stated_limits_status?: string;
  file_count?: number;
  file_types?: string[];
  analysis_status?: string;
  workspace_saved?: boolean;
  completion_saved?: boolean;
  workspace_file_name?: string;
  workspace_saved_at?: string;
  verification?: VerificationMetadata | null;
  policy_metadata?: {
    verification?: VerificationMetadata | null;
  } | null;
  files?: UploadedManualFile[];
};

type ManualSessionDetail = {
  session_id: string;
  title?: string;
  created_at?: string;
  updated_at?: string;
  upload_reason?: string;
  intended_use?: string;
  cognitive_layer?: string;
  source_stated_limits?: string;
  source_stated_confidence?: {
    raw_text?: string;
    normalized_label?: string | null;
  } | string | null;
  source_stated_limits_not_applicable?: boolean;
  source_stated_limits_status?: string;
  analysis_status?: string;
  workspace_saved?: boolean;
  completion_saved?: boolean;
  workspace_file_name?: string;
  workspace_saved_at?: string;
  verification?: VerificationMetadata | null;
  policy_metadata?: {
    verification?: VerificationMetadata | null;
  } | null;
  analysis?: ManualAnalysis | null;
  files?: UploadedManualFile[];
};

type SessionListResponse = {
  message?: string;
  sessions?: ManualSessionSummary[];
  detail?: string;
};

type SessionDetailResponse = {
  message?: string;
  session?: ManualSessionDetail | null;
};

type UploadResponse = {
  message?: string;
  session_id?: string | null;
  files?: UploadedManualFile[];
};

type AnalyzeSessionResponse = {
  message?: string;
  analysis?: ManualAnalysis | null;
  provider_used?: string | null;
  fallback_used?: boolean;
  workspace_saved?: boolean;
  workspace_file_name?: string | null;
};

type ManualFilePreviewResponse = {
  preview_text?: string;
  preview_available?: boolean;
  message?: string;
};

const PDF_PREVIEW_PENDING_MESSAGE =
  "[PDF uploaded successfully. Text preview will be generated during analysis.]";

function hasPendingPdfPreview(files: UploadedManualFile[]): boolean {
  return files.some(
    (file) =>
      file.file_kind === "pdf" &&
      (!file.preview_text || file.preview_text.trim() === PDF_PREVIEW_PENDING_MESSAGE)
  );
}

function needsPdfPreviewHydration(file: UploadedManualFile): boolean {
  return (
    file.file_kind === "pdf" &&
    Boolean(file.stored_filename) &&
    (!file.preview_text || file.preview_text.trim() === PDF_PREVIEW_PENDING_MESSAGE)
  );
}

type RelatedReflection = {
  id?: string;
  title?: string;
  source?: string;
  tags?: string[];
  timestamp?: string;
  match_score?: number;
  matched_topics?: string[];
  matched_terms?: string[];
};

type RelatedReflectionsResponse = {
  reflections?: RelatedReflection[];
  signal_topics?: string[];
};

type AnalysisValue =
  | string
  | number
  | boolean
  | null
  | undefined
  | AnalysisValue[]
  | { [key: string]: unknown };

function getErrorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}

function formatCompactLabel(value?: string): string {
  const normalized = String(value || "").trim();
  if (!normalized) return "Unknown";
  switch (normalized) {
    case "relevance_to_projects_requires_contextual_review":
      return "Project relevance requires contextual review";
    case "relevance_to_career_requires_contextual_review":
      return "Career relevance requires contextual review";
    default:
      return normalized
        .replace(/_/g, " ")
        .replace(/\b\w/g, (char) => char.toUpperCase());
  }
}

function getSourceStatedConfidenceText(
  value?: ManualSessionSummary["source_stated_confidence"]
): string {
  if (!value) return "";
  if (typeof value === "string") return value.trim();
  return String(value.raw_text || value.normalized_label || "").trim();
}

function getReviewPriority({
  verificationStatus,
  blockedActions,
  supportSummary,
}: {
  verificationStatus?: string;
  blockedActions: string[];
  supportSummary: Record<string, number>;
}): { key: ReviewPriorityFilter; label: string; color: string; background: string; border: string } {
  const status = String(verificationStatus || "").toLowerCase();
  const unsupported = (supportSummary.unsupported || 0) + (supportSummary.contradicted || 0);
  const inferred = supportSummary.inferred || 0;
  const blocksAction =
    blockedActions.includes("low_risk_action_candidate") ||
    blockedActions.includes("strong_recommendation");

  if (status === "unsupported" || status === "contradicted" || unsupported > 0) {
    return { key: "do_not_act", label: "Do Not Act", color: "var(--app-danger-fg)", background: "var(--app-danger-bg)", border: "1px solid var(--app-danger-border)" };
  }
  if (status === "not_verifiable" || status === "weakly_supported" || inferred > 0) {
    return { key: "review_required", label: "Review Required", color: "var(--app-warning-fg)", background: "var(--app-warning-bg)", border: "1px solid var(--app-warning-border)" };
  }
  if (status === "partially_verified" || blocksAction) {
    return { key: "review_before_action", label: "Review Before Action", color: "var(--app-warning-fg)", background: "var(--app-warning-bg)", border: "1px solid var(--app-warning-border)" };
  }
  if (status === "verified") {
    return { key: "ready_for_low_risk_review", label: "Ready For Low-Risk Review", color: "var(--app-success-fg)", background: "var(--app-success-bg)", border: "1px solid var(--app-success-border)" };
  }
  return { key: "unknown", label: "Review Unknown", color: "var(--app-text-muted)", background: "var(--app-chip-bg)", border: "1px solid var(--app-chip-border)" };
}

function getSessionVerification(session: ManualSessionSummary | ManualSessionDetail): VerificationMetadata | null {
  return session.verification || session.policy_metadata?.verification || null;
}

function getSessionReviewPriority(session: ManualSessionSummary | ManualSessionDetail) {
  const verification = getSessionVerification(session);
  if (!verification) return null;

  return getReviewPriority({
    verificationStatus: verification.verification_status,
    blockedActions: verification.blocked_downstream_actions || [],
    supportSummary: verification.claim_support_summary || {},
  });
}

function getManualSessionNextAction(session: ManualSessionSummary | ManualSessionDetail): {
  label: string;
  detail: string;
  tone: "done" | "ready" | "pending";
} {
  if (session.workspace_saved) {
    return {
      label: "Review Workspace record",
      detail: "This manual-derived intelligence has already been preserved as a Workspace record.",
      tone: "done",
    };
  }

  if (session.analysis_status === "completed") {
    return {
      label: "Manual Completion Route",
      detail: "Open the manual-derived signal. The right sidebar shows Manual Completion Route, completion note, and Complete Signal before saving to Workspace.",
      tone: "ready",
    };
  }

  return {
    label: "Generate insight",
    detail: "This upload still needs analysis before it can become a reviewed signal or Workspace record.",
    tone: "pending",
  };
}

function getManualSessionHandoffStage(session: ManualSessionSummary | ManualSessionDetail): {
  key: Exclude<ManualHandoffFilter, "all">;
  label: string;
  detail: string;
  tone: "done" | "ready" | "warning" | "pending";
} {
  if (session.workspace_saved) {
    return {
      key: "workspace_done",
      label: "Workspace Done",
      detail: "This manual-derived intelligence already has a durable Workspace record.",
      tone: "done",
    };
  }

  if (session.analysis_status === "completed") {
    return {
      key: "ready_for_signal_review",
      label: "Ready For Signal Review",
      detail: "Insight exists; review the manual-derived Signal Detail before saving to Workspace or routing into Project Takeaways.",
      tone: "ready",
    };
  }

  const summaryFileCount = "file_count" in session ? session.file_count || 0 : 0;
  const hasFiles = Array.isArray(session.files) ? session.files.length > 0 : summaryFileCount > 0;
  if (hasFiles) {
    return {
      key: "needs_insight",
      label: "Needs Insight",
      detail: "Uploaded material exists, but structured insight has not been generated yet.",
      tone: "warning",
    };
  }

  return {
    key: "pending_analysis",
    label: "Pending Analysis",
    detail: "This session needs upload/session detail review before it can enter the signal workflow.",
    tone: "pending",
  };
}

function buildManualHandoffFocus(counts: Record<ManualHandoffFilter, number>) {
  if (counts.ready_for_signal_review > 0) {
    return `${counts.ready_for_signal_review} session(s) are ready for Signal Detail review before Workspace completion or Project Takeaway routing.`;
  }
  if (counts.needs_insight > 0) {
    return `${counts.needs_insight} uploaded session(s) have files but still need generated insight.`;
  }
  if (counts.pending_analysis > 0) {
    return `${counts.pending_analysis} session(s) need session-detail review before entering the signal workflow.`;
  }
  if (counts.workspace_done > 0) {
    return "All visible manual sessions are already durable in Workspace.";
  }
  return "No manual handoff queue is waiting in this view.";
}

function applyLoadedSessionDetail(
  session: ManualSessionDetail,
  setCurrentSessionId: (value: string | null) => void,
  setUploadedFiles: (value: UploadedManualFile[]) => void,
  setSessionAnalysis: (value: ManualAnalysis | null) => void,
  setAvailableInSignals: (value: boolean) => void,
  setAnalysisMessage: (value: string) => void,
  successMessage?: string
) {
  setCurrentSessionId(session.session_id || null);
  setUploadedFiles(Array.isArray(session.files) ? session.files : []);
  setSessionAnalysis(session.analysis || null);
  setAvailableInSignals(Boolean(session.analysis));
  setAnalysisMessage(
    successMessage ||
      (session.analysis
        ? "Loaded saved analysis from manual session."
        : "Manual session loaded. No saved analysis yet.")
  );
}

export default function ManualPage() {
  const [selectedFiles, setSelectedFiles] = useState<FileList | null>(null);
  const [uploadMessage, setUploadMessage] = useState("");
  const [loading, setLoading] = useState(false);

  const [uploadedFiles, setUploadedFiles] = useState<UploadedManualFile[]>([]);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [analysisMessage, setAnalysisMessage] = useState("");
  const [sessionAnalysis, setSessionAnalysis] = useState<ManualAnalysis | null>(null);
  const [relatedReflections, setRelatedReflections] = useState<RelatedReflection[]>([]);
  const [relatedReflectionTopics, setRelatedReflectionTopics] = useState<string[]>([]);
  const [relatedReflectionsLoading, setRelatedReflectionsLoading] = useState(false);

  const [availableInSignals, setAvailableInSignals] = useState(false);

  const [lightboxIndex, setLightboxIndex] = useState<number | null>(null);

  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [sourceLink, setSourceLink] = useState("");
  const [uploadReason, setUploadReason] = useState("");
  const [intendedUse, setIntendedUse] = useState("");
  const [cognitiveLayer, setCognitiveLayer] = useState("unclassified");
  const [sourceStatedLimits, setSourceStatedLimits] = useState("");
  const [sourceStatedConfidence, setSourceStatedConfidence] = useState("");
  const [sourceStatedLimitsNotApplicable, setSourceStatedLimitsNotApplicable] = useState(false);

  const [savedSessions, setSavedSessions] = useState<ManualSessionSummary[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(false);
  const [sessionsMessage, setSessionsMessage] = useState("");
  const [expandedSessionId, setExpandedSessionId] = useState<string | null>(null);
  const [selectedSessionReviewPriority, setSelectedSessionReviewPriority] =
    useState<ReviewPriorityFilter>("all");
  const [selectedWorkspaceStatus, setSelectedWorkspaceStatus] =
    useState<WorkspaceStatusFilter>("all");
  const [selectedHandoffStage, setSelectedHandoffStage] =
    useState<ManualHandoffFilter>("all");
  const [manualFileUrls, setManualFileUrls] = useState<Record<string, string>>({});
  const [manualFilePreviewOverrides, setManualFilePreviewOverrides] = useState<Record<string, string>>({});
  const [expandedTextPreviewIds, setExpandedTextPreviewIds] = useState<Record<string, boolean>>({});

  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const manualFileUrlsRef = useRef<Record<string, string>>({});
  const analysisSectionRef = useRef<HTMLDivElement | null>(null);

  const imageFiles = useMemo(
    () => uploadedFiles.filter((file) => file.file_kind === "image"),
    [uploadedFiles]
  );

  const textLikeFiles = useMemo(
    () => uploadedFiles.filter((file) => file.file_kind === "text" || file.file_kind === "pdf"),
    [uploadedFiles]
  );

  const sessionType = useMemo(() => {
    if (uploadedFiles.length === 0) return "";
    const kinds = Array.from(new Set(uploadedFiles.map((f) => f.file_kind)));
    if (kinds.length === 1 && kinds[0] === "image") return "image";
    if (kinds.every((k) => k === "text" || k === "pdf")) return "text";
    return "mixed";
  }, [uploadedFiles]);

  const currentLightboxFile =
    lightboxIndex !== null && imageFiles[lightboxIndex] ? imageFiles[lightboxIndex] : null;
  const expandedSession = useMemo(
    () => savedSessions.find((session) => session.session_id === expandedSessionId) || null,
    [expandedSessionId, savedSessions]
  );
  const visibleSavedSessions = useMemo(() => {
    return savedSessions.filter((session) => {
      const reviewPriority = getSessionReviewPriority(session);
      const matchesReviewPriority =
        selectedSessionReviewPriority === "all"
          ? true
          : selectedSessionReviewPriority === "unknown"
            ? !reviewPriority
            : reviewPriority?.key === selectedSessionReviewPriority;
      const matchesWorkspaceStatus =
        selectedWorkspaceStatus === "all"
          ? true
          : selectedWorkspaceStatus === "workspace_saved"
            ? Boolean(session.workspace_saved)
            : !session.workspace_saved;
      const handoffStage = getManualSessionHandoffStage(session);
      const matchesHandoffStage =
        selectedHandoffStage === "all"
          ? true
          : handoffStage.key === selectedHandoffStage;
      return matchesReviewPriority && matchesWorkspaceStatus && matchesHandoffStage;
    });
  }, [savedSessions, selectedHandoffStage, selectedSessionReviewPriority, selectedWorkspaceStatus]);
  const sessionReviewPriorityCounts = useMemo(() => {
    const counts: Record<ReviewPriorityFilter, number> = {
      all: savedSessions.length,
      do_not_act: 0,
      review_required: 0,
      review_before_action: 0,
      ready_for_low_risk_review: 0,
      unknown: 0,
    };

    for (const session of savedSessions) {
      const reviewPriority = getSessionReviewPriority(session);
      counts[reviewPriority?.key || "unknown"] += 1;
    }

    return counts;
  }, [savedSessions]);
  const workspaceStatusCounts = useMemo(() => {
    const savedCount = savedSessions.filter((session) => session.workspace_saved).length;
    const analyzedNotInWorkspace = savedSessions.filter(
      (session) => session.analysis_status === "completed" && !session.workspace_saved
    ).length;
    const needsAnalysis = savedSessions.filter((session) => session.analysis_status !== "completed").length;
    return {
      all: savedSessions.length,
      workspace_saved: savedCount,
      not_in_workspace: savedSessions.length - savedCount,
      analyzed_not_in_workspace: analyzedNotInWorkspace,
      needs_analysis: needsAnalysis,
    };
  }, [savedSessions]);
  const handoffStageCounts = useMemo(() => {
    const counts: Record<ManualHandoffFilter, number> = {
      all: savedSessions.length,
      workspace_done: 0,
      ready_for_signal_review: 0,
      needs_insight: 0,
      pending_analysis: 0,
    };

    for (const session of savedSessions) {
      counts[getManualSessionHandoffStage(session).key] += 1;
    }

    return counts;
  }, [savedSessions]);
  const requiredManualFiles = useMemo(() => {
    const unique = new Set<string>();
    for (const file of uploadedFiles) {
      if (file.stored_filename) unique.add(file.stored_filename);
    }
    for (const file of expandedSession?.files || []) {
      if (file.stored_filename) unique.add(file.stored_filename);
    }
    return Array.from(unique);
  }, [expandedSession, uploadedFiles]);
  const filesNeedingPreviewHydration = useMemo(() => {
    const byStoredFilename = new Map<string, UploadedManualFile>();
    for (const file of uploadedFiles) {
      if (needsPdfPreviewHydration(file)) byStoredFilename.set(file.stored_filename, file);
    }
    for (const file of expandedSession?.files || []) {
      if (needsPdfPreviewHydration(file)) byStoredFilename.set(file.stored_filename, file);
    }
    return Array.from(byStoredFilename.values());
  }, [expandedSession, uploadedFiles]);

  const getPreviewText = (file: UploadedManualFile) => {
    const previewText = manualFilePreviewOverrides[file.stored_filename] || file.preview_text || "";
    return previewText.trim() === PDF_PREVIEW_PENDING_MESSAGE ? "" : previewText;
  };

  const openLightbox = (index: number) => {
    setLightboxIndex(index);
  };

  const focusAnalysisSection = useCallback(() => {
    window.requestAnimationFrame(() => {
      analysisSectionRef.current?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    });
  }, []);

  const closeLightbox = useCallback(() => {
    setLightboxIndex(null);
  }, []);

  const showPrevImage = useCallback(() => {
    if (lightboxIndex === null || imageFiles.length === 0) return;
    setLightboxIndex((prev) => {
      if (prev === null) return 0;
      return prev === 0 ? imageFiles.length - 1 : prev - 1;
    });
  }, [imageFiles.length, lightboxIndex]);

  const showNextImage = useCallback(() => {
    if (lightboxIndex === null || imageFiles.length === 0) return;
    setLightboxIndex((prev) => {
      if (prev === null) return 0;
      return prev === imageFiles.length - 1 ? 0 : prev + 1;
    });
  }, [imageFiles.length, lightboxIndex]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (lightboxIndex === null) return;

      if (e.key === "Escape") closeLightbox();
      if (e.key === "ArrowLeft") showPrevImage();
      if (e.key === "ArrowRight") showNextImage();
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [closeLightbox, lightboxIndex, showNextImage, showPrevImage]);

  useEffect(() => {
    return () => {
      for (const url of Object.values(manualFileUrlsRef.current)) {
        URL.revokeObjectURL(url);
      }
      manualFileUrlsRef.current = {};
    };
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function hydrateManualFileUrls() {
      for (const storedFilename of requiredManualFiles) {
        if (!storedFilename || manualFileUrlsRef.current[storedFilename]) continue;

        try {
          const response = await adminFetch(
            `${API_BASE}/manual/file/${encodeURIComponent(storedFilename)}`,
            {
              cache: "force-cache",
            }
          );
          if (!response.ok) continue;

          const blob = await response.blob();
          if (cancelled) continue;

          const objectUrl = URL.createObjectURL(blob);
          manualFileUrlsRef.current[storedFilename] = objectUrl;
          setManualFileUrls((current) => ({
            ...current,
            [storedFilename]: objectUrl,
          }));
        } catch {
          continue;
        }
      }
    }

    void hydrateManualFileUrls();

    return () => {
      cancelled = true;
    };
  }, [requiredManualFiles]);

  useEffect(() => {
    if (filesNeedingPreviewHydration.length === 0) return;

    let cancelled = false;

    async function hydrateManualFilePreviews() {
      for (const file of filesNeedingPreviewHydration) {
        const storedFilename = file.stored_filename;
        if (!storedFilename || manualFilePreviewOverrides[storedFilename]) continue;

        try {
          const response = await adminFetch(
            `${API_BASE}/manual/file-preview/${encodeURIComponent(storedFilename)}`,
            {
              cache: "no-store",
            }
          );
          if (!response.ok) continue;

          const data = (await response.json().catch(() => null)) as ManualFilePreviewResponse | null;
          const previewText = data?.preview_text || "";
          if (cancelled || !previewText || previewText === PDF_PREVIEW_PENDING_MESSAGE) continue;

          setManualFilePreviewOverrides((current) => ({
            ...current,
            [storedFilename]: previewText,
          }));
        } catch {
          continue;
        }
      }
    }

    void hydrateManualFilePreviews();

    return () => {
      cancelled = true;
    };
  }, [filesNeedingPreviewHydration, manualFilePreviewOverrides]);

  useEffect(() => {
    loadSavedSessions();
  }, []);

  useEffect(() => {
    let cancelled = false;
    const controller = new AbortController();

    async function loadRelatedReflections() {
      if (!currentSessionId || !sessionAnalysis) {
        setRelatedReflections([]);
        setRelatedReflectionTopics([]);
        return;
      }

      setRelatedReflectionsLoading(true);
      try {
        const res = await fetch(
          `${API_BASE}/signals/manual_${encodeURIComponent(currentSessionId)}/related-reflections?limit=3`,
          {
            cache: "no-store",
            signal: controller.signal,
          }
        );
        if (!res.ok) {
          throw new Error("Failed to load related reflections.");
        }

        const data = (await res.json()) as RelatedReflectionsResponse;
        if (!cancelled) {
          setRelatedReflections(Array.isArray(data.reflections) ? data.reflections : []);
          setRelatedReflectionTopics(Array.isArray(data.signal_topics) ? data.signal_topics : []);
        }
      } catch (error) {
        if (error instanceof Error && error.name === "AbortError") {
          return;
        }
        if (!cancelled) {
          setRelatedReflections([]);
          setRelatedReflectionTopics([]);
        }
      } finally {
        if (!cancelled) {
          setRelatedReflectionsLoading(false);
        }
      }
    }

    void loadRelatedReflections();

    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [currentSessionId, sessionAnalysis]);

  const loadSavedSessions = async () => {
    if (!getStoredAdminToken()) {
      setSavedSessions([]);
      setSessionsMessage("Admin login is required before loading saved manual sessions.");
      return;
    }

    try {
      setSessionsLoading(true);
      setSessionsMessage("");

      const res = await adminFetch(`${API_BASE}/manual/sessions`, {
        cache: "no-store",
      });

      const data = (await res.json().catch(() => null)) as SessionListResponse | null;

      if (!res.ok) {
        if (res.status === 401 || res.status === 403) {
          throw new Error("Admin login is required before loading saved manual sessions.");
        }
        throw new Error(data?.message || data?.detail || `Failed to load sessions: ${res.status}`);
      }

      const sessions = Array.isArray(data?.sessions) ? data.sessions : [];
      setSavedSessions(sessions);
      setSessionsMessage(data?.message || "");
    } catch (error: unknown) {
      console.error("Failed to load manual sessions:", error);
      setSavedSessions([]);
      setSessionsMessage(getErrorMessage(error, "Failed to load manual sessions."));
    } finally {
      setSessionsLoading(false);
    }
  };

  const fetchSessionDetail = useCallback(async (sessionId: string) => {
    const res = await adminFetch(`${API_BASE}/manual/session/${encodeURIComponent(sessionId)}`, {
      cache: "no-store",
    });

    const data = (await res.json().catch(() => null)) as SessionDetailResponse | null;

    if (!res.ok) {
      if (res.status === 401 || res.status === 403) {
        throw new Error("Admin login is required before loading manual session detail.");
      }
      throw new Error(data?.message || `Failed to load session detail: ${res.status}`);
    }

    const session: ManualSessionDetail | null = data?.session || null;
    if (!session) {
      throw new Error(data?.message || "Session not found.");
    }

    return session;
  }, []);

  useEffect(() => {
    if (!currentSessionId) return;

    let cancelled = false;

    const refreshCurrentSession = async () => {
      try {
        const res = await adminFetch(`${API_BASE}/manual/session/${encodeURIComponent(currentSessionId)}`, {
          cache: "no-store",
        });

        const data = (await res.json().catch(() => null)) as SessionDetailResponse | null;
        if (!res.ok || !data?.session || cancelled) {
          return;
        }

        applyLoadedSessionDetail(
          data.session,
          setCurrentSessionId,
          setUploadedFiles,
          setSessionAnalysis,
          setAvailableInSignals,
          setAnalysisMessage,
          data.session.analysis
            ? "Manual session detail refreshed with latest analysis."
            : "Manual session refreshed."
        );
      } catch {
        // Ignore background refresh errors and keep the current page state.
      }
    };

    const handleVisibilityOrFocus = () => {
      if (document.visibilityState === "visible") {
        void refreshCurrentSession();
      }
    };

    window.addEventListener("focus", handleVisibilityOrFocus);
    document.addEventListener("visibilitychange", handleVisibilityOrFocus);

    return () => {
      cancelled = true;
      window.removeEventListener("focus", handleVisibilityOrFocus);
      document.removeEventListener("visibilitychange", handleVisibilityOrFocus);
    };
  }, [currentSessionId]);

  useEffect(() => {
    if (!currentSessionId || !hasPendingPdfPreview(uploadedFiles)) return;

    let cancelled = false;

    const refreshPendingPdfPreview = async () => {
      try {
        const session = await fetchSessionDetail(currentSessionId);
        if (cancelled) return;
        applyLoadedSessionDetail(
          session,
          setCurrentSessionId,
          setUploadedFiles,
          setSessionAnalysis,
          setAvailableInSignals,
          setAnalysisMessage,
          session.analysis
            ? "Manual session refreshed with extracted PDF preview."
            : "Manual session refreshed with latest PDF preview."
        );
      } catch {
        // Keep the current upload state if detail refresh fails.
      }
    };

    void refreshPendingPdfPreview();

    return () => {
      cancelled = true;
    };
  }, [currentSessionId, fetchSessionDetail, uploadedFiles]);

  const formatDateTime = (value?: string) => {
    if (!value) return "Unknown time";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return date.toLocaleString();
  };

  const resetSessionState = () => {
    setUploadMessage("");
    setAnalysisMessage("");
    setSessionAnalysis(null);
    setRelatedReflections([]);
    setRelatedReflectionTopics([]);
    setAvailableInSignals(false);
    setUploadedFiles([]);
    setLightboxIndex(null);
    setCurrentSessionId(null);
  };

  const getManualFileUrl = (storedFilename?: string) =>
    (storedFilename ? manualFileUrls[storedFilename] : "") || "";

  const toggleTextPreview = (storedFilename: string) => {
    setExpandedTextPreviewIds((current) => ({
      ...current,
      [storedFilename]: !current[storedFilename],
    }));
  };

  const handleUpload = async () => {
    const trimmedSourceLink = sourceLink.trim();
    const hasSelectedFiles = Boolean(selectedFiles && selectedFiles.length > 0);
    if (!hasSelectedFiles && !trimmedSourceLink) {
      setUploadMessage("Please choose at least one file or add one source link first.");
      return;
    }
    let normalizedSourceLink = "";
    if (trimmedSourceLink) {
      try {
        normalizedSourceLink = new URL(trimmedSourceLink).toString();
      } catch {
        setUploadMessage("Please enter a valid source link, including https:// or http://.");
        return;
      }
      const selectedImageFiles = selectedFiles
        ? Array.from(selectedFiles).filter((file) => /\.(png|jpe?g|webp)$/i.test(file.name))
        : [];
      if (selectedImageFiles.length > 0) {
        setUploadMessage("Source links can be combined with text/PDF files, but not image files yet.");
        return;
      }
    }
    if (!getStoredAdminToken()) {
      setUploadMessage("Admin login is required before uploading manual files.");
      return;
    }

    try {
      setLoading(true);
      resetSessionState();

      const formData = new FormData();

      if (selectedFiles) {
        for (let i = 0; i < selectedFiles.length; i++) {
          formData.append("files", selectedFiles[i]);
        }
      }

      if (normalizedSourceLink) {
        const linkSourceText = [
          "# Manual Link Source",
          "",
          `Source URL: ${normalizedSourceLink}`,
          uploadReason.trim() ? `Upload reason: ${uploadReason.trim()}` : "",
          intendedUse.trim() ? `Intended use: ${intendedUse.trim()}` : "",
          `Cognitive layer: ${cognitiveLayer}`,
          "",
          "Note: AI Radar will attempt to fetch public article text from this link for manual analysis. If fetching fails, the URL and reviewer intent are still preserved.",
        ]
          .filter(Boolean)
          .join("\n");
        formData.append(
          "files",
          new File([linkSourceText], "manual-link-source.md", {
            type: "text/markdown",
          }),
        );
      }
      formData.append("upload_reason", uploadReason.trim());
      formData.append("intended_use", intendedUse.trim());
      formData.append("cognitive_layer", cognitiveLayer);
      if (sourceStatedLimitsNotApplicable) {
        formData.append("source_stated_limits_not_applicable", "true");
      } else {
        formData.append("source_stated_limits", sourceStatedLimits.trim());
        formData.append("source_stated_confidence", sourceStatedConfidence.trim());
      }

      const res = await adminFetch(`${API_BASE}/manual/upload`, {
        method: "POST",
        body: formData,
      });

      const data = (await res.json().catch(() => null)) as UploadResponse | null;

      if (!res.ok) {
        throw new Error(data?.message || `Upload failed: ${res.status}`);
      }

      const files: UploadedManualFile[] = Array.isArray(data?.files) ? data.files : [];
      setUploadedFiles(files);
      setCurrentSessionId(data?.session_id || null);
      setUploadMessage(data?.message || "Files uploaded successfully.");
      void loadSavedSessions();
    } catch (error: unknown) {
      console.error("Upload failed:", error);
      setUploadMessage(getErrorMessage(error, "Upload failed."));
      setUploadedFiles([]);
      setCurrentSessionId(null);
    } finally {
      setLoading(false);
    }
  };

  const handleAnalyzeSession = async () => {
    if (uploadedFiles.length === 0) {
      setAnalysisMessage("No uploaded files available for analysis.");
      return;
    }

    if (sessionType === "mixed") {
      setAnalysisMessage(
        "Mixed session analysis is not supported yet. Please upload either all images or all text/PDF files in one session."
      );
      return;
    }

    try {
      setAnalysisLoading(true);
      setAnalysisMessage("Analyzing session... this may take a little while.");
      setAvailableInSignals(false);
      setSessionAnalysis(null);
      if (currentSessionId) {
        setExpandedSessionId(currentSessionId);
      }

      const res = await adminFetch(`${API_BASE}/manual/analyze-session`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          session_id: currentSessionId,
          files: uploadedFiles.map((file) => ({
            stored_filename: file.stored_filename,
            original_filename: file.original_filename,
            file_kind: file.file_kind,
          })),
        }),
      });

      const data = (await res.json().catch(() => null)) as AnalyzeSessionResponse | null;

      if (!res.ok) {
        throw new Error(data?.message || `Session analysis failed: ${res.status}`);
      }

      if (!data?.analysis) {
        throw new Error(data?.message || "No analysis returned from backend.");
      }

      setAnalysisMessage(data?.message || "Session analysis generated successfully.");
      setSessionAnalysis(data.analysis);
      setAvailableInSignals(true);
      await loadSavedSessions();
      if (currentSessionId) {
        try {
          const refreshedSession = await fetchSessionDetail(currentSessionId);
          applyLoadedSessionDetail(
            refreshedSession,
            setCurrentSessionId,
            setUploadedFiles,
            setSessionAnalysis,
            setAvailableInSignals,
            setAnalysisMessage,
            data?.message || "Session analysis generated successfully."
          );
        } catch {
          // Keep the immediate analysis result even if the follow-up refresh misses.
        }
      }
      focusAnalysisSection();
    } catch (error: unknown) {
      console.error("Session analysis failed:", error);

      const message = getErrorMessage(error, "Session analysis failed.");
      if (
        message.includes("overloaded_error") ||
        message.includes("Overloaded") ||
        message.includes("529")
      ) {
        setAnalysisMessage(
          "Analysis provider is temporarily overloaded. Please wait a moment and try again."
        );
      } else {
        setAnalysisMessage(message);
      }

      setSessionAnalysis(null);
    } finally {
      setAnalysisLoading(false);
    }
  };

  const handleClearSession = () => {
    setSelectedFiles(null);
    setSourceLink("");
    setUploadReason("");
    setIntendedUse("");
    setCognitiveLayer("unclassified");
    resetSessionState();
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  return (
    <>
      <AppContainer style={manualShellStyle}>
        <RequireAdminAuth>
        <ManualHero
          selectedFileCount={selectedFiles?.length || 0}
          uploadedFileCount={uploadedFiles.length}
          savedSessionCount={savedSessions.length}
          readyForReviewCount={handoffStageCounts.ready_for_signal_review}
          workspaceCount={workspaceStatusCounts.workspace_saved}
        />

        <section style={manualPanelStyle}>
          <div style={manualPanelHeaderStyle}>
            <div>
              <div style={manualPanelEyebrowStyle}>Source capture</div>
              <h2 style={manualPanelTitleStyle}>Upload or fetch source material</h2>
              <p style={manualPanelDescriptionStyle}>
                Add files or a source link, preserve why it matters, then generate an analysis before sending useful material into Signals.
              </p>
            </div>
            <div style={manualPanelBadgeStyle}>
              {currentSessionId ? "Session active" : "Ready for intake"}
            </div>
          </div>

          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept=".txt,.md,.json,.pdf,.png,.jpg,.jpeg,.webp"
            onChange={(e) => {
              setSelectedFiles(e.target.files);
            }}
          />

          {selectedFiles && selectedFiles.length > 0 && (
            <div style={{ marginTop: "12px", fontSize: "14px", color: "var(--app-text-muted)" }}>
              Selected {selectedFiles.length} file(s):
              <ul style={{ marginTop: "8px", paddingLeft: "18px" }}>
                {Array.from(selectedFiles).map((file, idx) => (
                  <li key={`${file.name}-${idx}`}>{file.name}</li>
                ))}
              </ul>
            </div>
          )}

          <label
            style={{ ...manualFieldLabelStyle, marginTop: "16px" }}
          >
            Source link
            <input
              type="url"
              value={sourceLink}
              onChange={(event) => setSourceLink(event.target.value)}
              placeholder="https://example.com/article-or-video"
              style={manualInputStyle}
            />
            <span style={manualHelperTextStyle}>
              Optional first-class source for a link-only manual session. AI Radar will attempt to fetch public article text, then preserve the URL and intent either way.
            </span>
          </label>

          {sourceLink.trim() ? (
            <div style={{ marginTop: "10px", fontSize: "13px", color: "var(--app-text-muted)" }}>
              Link will be uploaded as a text source. Public article text will be fetched when available.
            </div>
          ) : null}

          <div
            style={{
              marginTop: "16px",
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 220px), 1fr))",
              gap: "12px",
            }}
          >
            <label style={manualFieldLabelStyle}>
              Upload reason
              <input
                value={uploadReason}
                onChange={(event) => setUploadReason(event.target.value)}
                placeholder="Why this material matters now"
                style={manualInputStyle}
              />
            </label>

            <label style={manualFieldLabelStyle}>
              Intended use
              <input
                value={intendedUse}
                onChange={(event) => setIntendedUse(event.target.value)}
                placeholder="Review, project input, reference, decision prep"
                style={manualInputStyle}
              />
            </label>

            <label style={manualFieldLabelStyle}>
              Cognitive layer
              <select
                value={cognitiveLayer}
                onChange={(event) => setCognitiveLayer(event.target.value)}
                style={manualInputStyle}
              >
                <option value="unclassified">Unclassified - decide later</option>
                <option value="L1">L1 - infrastructure / reusable skill material</option>
                <option value="L2">L2 - reusable structure / project judgment</option>
                <option value="L3">L3 - personal reasoning / judgment trajectory</option>
              </select>
              <span style={manualHelperTextStyle}>
                Optional marker for why this upload matters: tool/process material, reusable project thinking, or deeper personal reasoning.
              </span>
            </label>
          </div>

          <div
            style={{
              marginTop: "16px",
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 280px), 1fr))",
              gap: "12px",
            }}
          >
            <label style={manualFieldLabelStyle}>
              Source-stated limits
              <textarea
                value={sourceStatedLimits}
                onChange={(event) => setSourceStatedLimits(event.target.value)}
                placeholder="Limits, caveats, scope boundaries, or known failure modes stated by the source"
                disabled={sourceStatedLimitsNotApplicable}
                style={{
                  ...manualInputStyle,
                  minHeight: "92px",
                  resize: "vertical",
                  opacity: sourceStatedLimitsNotApplicable ? 0.65 : 1,
                }}
              />
            </label>

            <label style={manualFieldLabelStyle}>
              Source-stated confidence
              <textarea
                value={sourceStatedConfidence}
                onChange={(event) => setSourceStatedConfidence(event.target.value)}
                placeholder="Confidence wording from the source, if it states one"
                disabled={sourceStatedLimitsNotApplicable}
                style={{
                  ...manualInputStyle,
                  minHeight: "92px",
                  resize: "vertical",
                  opacity: sourceStatedLimitsNotApplicable ? 0.65 : 1,
                }}
              />
            </label>
          </div>

          <label
            style={{
              ...manualHelperTextStyle,
              marginTop: "10px",
              display: "flex",
              alignItems: "center",
              gap: "8px",
              fontSize: "13px",
            }}
          >
            <input
              type="checkbox"
              checked={sourceStatedLimitsNotApplicable}
              onChange={(event) => setSourceStatedLimitsNotApplicable(event.target.checked)}
            />
            This source has no applicable self-stated limits or confidence boundary.
          </label>

          <div
            style={{
              marginTop: "16px",
              display: "flex",
              gap: "12px",
              flexWrap: "wrap",
            }}
          >
            <button
              onClick={handleUpload}
              disabled={loading}
              style={{
                padding: "10px 16px",
                borderRadius: "8px",
                border: loading
                  ? "1px solid var(--app-surface-border)"
                  : "1px solid var(--app-primary-action-border)",
                background: loading ? "var(--app-surface-soft-bg)" : "var(--app-primary-action-bg)",
                color: loading ? "var(--app-text-subtle)" : "var(--app-primary-action-fg)",
                cursor: loading ? "not-allowed" : "pointer",
                fontWeight: 700,
              }}
            >
              {loading ? "Uploading..." : "Upload Source"}
            </button>

            {!availableInSignals ? (
              <button
                onClick={handleAnalyzeSession}
                disabled={analysisLoading || uploadedFiles.length === 0}
                style={{
                  padding: "10px 16px",
                  borderRadius: "8px",
                  border: "1px solid var(--app-secondary-action-border)",
                  background:
                    analysisLoading || uploadedFiles.length === 0
                      ? "var(--app-surface-soft-bg)"
                      : "var(--app-secondary-action-bg)",
                  color:
                    analysisLoading || uploadedFiles.length === 0
                      ? "var(--app-text-subtle)"
                      : "var(--app-secondary-action-fg)",
                  cursor: analysisLoading || uploadedFiles.length === 0 ? "not-allowed" : "pointer",
                  fontWeight: 700,
                }}
              >
                {analysisLoading ? "Analyzing..." : "Analyze Session"}
              </button>
            ) : currentSessionId ? (
              <>
                <Link
                  href={`/signals/detail?id=${encodeURIComponent(`manual_${currentSessionId}`)}`}
                  style={{
                    padding: "10px 16px",
                    borderRadius: "8px",
                    border: "1px solid var(--app-primary-action-border)",
                    background: "var(--app-primary-action-bg)",
                    color: "var(--app-primary-action-fg)",
                    textDecoration: "none",
                    fontSize: "14px",
                    fontWeight: 700,
                    display: "inline-flex",
                    alignItems: "center",
                  }}
                >
                  Open in Signals
                </Link>
                <Link
                  href={`/manual/detail?id=${encodeURIComponent(currentSessionId)}`}
                  style={{
                    padding: "10px 16px",
                    borderRadius: "8px",
                    border: "1px solid var(--app-info-border)",
                    background: "var(--app-info-bg)",
                    color: "var(--app-info-fg)",
                    textDecoration: "none",
                    fontSize: "14px",
                    fontWeight: 700,
                    display: "inline-flex",
                    alignItems: "center",
                  }}
                >
                  Open Session Detail
                </Link>
              </>
            ) : null}

              <button
                onClick={handleClearSession}
                disabled={loading || analysisLoading}
                style={{
                  padding: "10px 16px",
                  borderRadius: "8px",
                  border: "1px solid var(--app-secondary-action-border)",
                  background:
                    loading || analysisLoading
                      ? "var(--app-surface-soft-bg)"
                      : "var(--app-secondary-action-bg)",
                  color:
                    loading || analysisLoading
                      ? "var(--app-text-subtle)"
                      : "var(--app-secondary-action-fg)",
                  cursor: loading || analysisLoading ? "not-allowed" : "pointer",
                  fontWeight: 700,
                }}
              >
                Clear
              </button>

            <Link
              href="/signals?source=manual"
              style={{
                padding: "10px 16px",
                borderRadius: "8px",
                border: "1px solid var(--app-secondary-action-border)",
                background: "var(--app-secondary-action-bg)",
                textDecoration: "none",
                color: "var(--app-secondary-action-fg)",
                fontSize: "14px",
                fontWeight: 700,
                display: "inline-flex",
                alignItems: "center",
              }}
            >
              View Signal Records -&gt;
            </Link>
          </div>

          {currentSessionId && (
            <div style={{ marginTop: "14px", fontSize: "13px", color: "var(--app-text-subtle)" }}>
              Current session ID: <strong>{currentSessionId}</strong>
            </div>
          )}

          {uploadedFiles.length > 0 && (
            <div style={{ marginTop: "14px", fontSize: "13px", color: "var(--app-text-subtle)" }}>
              Session type:{" "}
              <strong>
                {sessionType === "image"
                  ? "Image Session"
                  : sessionType === "text"
                    ? "Text / PDF Session"
                    : sessionType === "mixed"
                      ? "Mixed Session"
                      : "Unknown"}
              </strong>
            </div>
          )}

          {uploadMessage && (
            <div style={{ marginTop: "14px", fontSize: "14px", color: "var(--app-text-muted)" }}>
              {uploadMessage}
            </div>
          )}

          {analysisMessage && (
            <div style={{ marginTop: "10px", fontSize: "14px", color: "var(--app-text-muted)" }}>
              {analysisMessage}
            </div>
          )}
        </section>

        {uploadedFiles.length > 0 && (
          <div
            style={manualNestedPanelStyle}
          >
            <div
              style={{
                fontSize: "13px",
                color: "var(--app-text-subtle)",
                marginBottom: "12px",
                textTransform: "uppercase",
                letterSpacing: 0,
              }}
            >
              Uploaded session files
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
              {uploadedFiles.map((file) => (
                <div
                  key={file.stored_filename}
                  style={manualNestedCardStyle}
                >
                  <div style={{ fontSize: "14px", fontWeight: 600 }}>{file.original_filename}</div>
                  <div style={{ ...manualMutedMetaStyle, marginTop: "4px" }}>
                    type: {file.file_kind}
                  </div>
                  {file.article_fetch_status && (
                    <div
                      style={{
                        marginTop: "8px",
                        display: "inline-flex",
                        alignItems: "center",
                        borderRadius: "999px",
                        border:
                          file.article_fetch_status === "fetched"
                            ? "1px solid var(--app-success-border)"
                            : "1px solid var(--app-danger-border)",
                        background:
                          file.article_fetch_status === "fetched"
                            ? "var(--app-success-bg)"
                            : "var(--app-danger-bg)",
                        color:
                          file.article_fetch_status === "fetched"
                            ? "var(--app-success-fg)"
                            : "var(--app-danger-fg)",
                        padding: "4px 10px",
                        fontSize: "12px",
                        fontWeight: 700,
                      }}
                    >
                      Article fetch: {file.article_fetch_status}
                    </div>
                  )}
                  {file.article_title && (
                    <div style={{ ...manualMutedMetaStyle, marginTop: "6px" }}>
                      {file.article_title}
                    </div>
                  )}
                  {file.article_fetch_error && (
                    <div style={{ fontSize: "12px", color: "var(--app-danger-fg)", marginTop: "6px" }}>
                      {file.article_fetch_error}
                    </div>
                  )}
                  {file.message && (
                    <div style={{ ...manualMutedMetaStyle, marginTop: "4px" }}>
                      {file.message}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {imageFiles.length > 0 && (
          <div
            style={manualNestedPanelStyle}
          >
            <div
              style={{
                fontSize: "13px",
                color: "var(--app-text-subtle)",
                marginBottom: "12px",
                textTransform: "uppercase",
                letterSpacing: 0,
              }}
            >
              Image session preview
            </div>

            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 220px), 1fr))",
                gap: "16px",
              }}
            >
              {imageFiles.map((file, index) => (
                <div
                  key={file.stored_filename}
                  style={{
                    border: "1px solid var(--app-surface-border)",
                    borderRadius: "10px",
                    padding: "10px",
                    background: "var(--app-surface-muted-bg)",
                    minHeight: "340px",
                    display: "flex",
                    flexDirection: "column",
                  }}
                >
                  <button
                    onClick={() => openLightbox(index)}
                    style={{
                      border: "none",
                      background: "transparent",
                      padding: 0,
                      cursor: "pointer",
                      textAlign: "left",
                      display: "block",
                    }}
                  >
                    {getManualFileUrl(file.stored_filename) ? (
                      <Image
                        src={getManualFileUrl(file.stored_filename)}
                        alt={file.original_filename}
                        width={1200}
                        height={780}
                        unoptimized
                        style={{
                          width: "100%",
                          height: "260px",
                          objectFit: "cover",
                          borderRadius: "8px",
                          border: "1px solid var(--app-surface-border)",
                          display: "block",
                        }}
                      />
                    ) : (
                      <div
                        style={{
                          width: "100%",
                          height: "260px",
                          borderRadius: "8px",
                          border: "1px solid var(--app-surface-border)",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          background: "var(--app-surface-soft-bg)",
                          color: "var(--app-text-subtle)",
                          fontSize: "13px",
                        }}
                      >
                        Preparing preview...
                      </div>
                    )}
                  </button>

                  <div
                    style={{
                      marginTop: "10px",
                      fontSize: "12px",
                      color: "var(--app-text-muted)",
                      wordBreak: "break-word",
                      lineHeight: "1.6",
                      flex: 1,
                    }}
                    title={file.original_filename}
                  >
                    {file.original_filename}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {textLikeFiles.length > 0 && (
          <div
            style={manualNestedPanelStyle}
          >
            <div
              style={{
                fontSize: "13px",
                color: "var(--app-text-subtle)",
                marginBottom: "12px",
                textTransform: "uppercase",
                letterSpacing: 0,
              }}
            >
              Text / PDF session preview
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
              {textLikeFiles.map((file) => {
                const previewText = getPreviewText(file);
                const pdfUrl = file.file_kind === "pdf" ? getManualFileUrl(file.stored_filename) : "";
                const canExpandPreview = Boolean(previewText) && file.file_kind !== "pdf";
                return (
                  <div
                    key={file.stored_filename}
                    style={{
                      border: "1px solid var(--app-surface-border)",
                      borderRadius: "10px",
                      padding: "14px",
                      background: "var(--app-surface-muted-bg)",
                    }}
                  >
                    <div style={{ fontSize: "13px", fontWeight: 600, marginBottom: "8px" }}>
                      {file.original_filename}
                    </div>
                    {(canExpandPreview || file.file_kind === "pdf") && (
                      <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", marginBottom: "10px" }}>
                        {canExpandPreview && (
                          <button
                            type="button"
                            onClick={() => toggleTextPreview(file.stored_filename)}
                            style={{
                              border: "1px solid var(--app-secondary-action-border)",
                              borderRadius: "8px",
                              background: "var(--app-secondary-action-bg)",
                              color: "var(--app-secondary-action-fg)",
                              padding: "7px 10px",
                              fontSize: "13px",
                              fontWeight: 700,
                              cursor: "pointer",
                            }}
                          >
                            {expandedTextPreviewIds[file.stored_filename] ? "Collapse preview" : "Expand preview"}
                          </button>
                        )}
                        {file.file_kind === "pdf" && (
                          pdfUrl ? (
                            <a
                              href={pdfUrl}
                              target="_blank"
                              rel="noreferrer"
                              style={{
                                border: "1px solid var(--app-primary-action-border)",
                                borderRadius: "8px",
                                background: "var(--app-primary-action-bg)",
                                color: "var(--app-primary-action-fg)",
                                padding: "7px 10px",
                                fontSize: "13px",
                                fontWeight: 700,
                                textDecoration: "none",
                              }}
                            >
                              Open PDF
                            </a>
                          ) : (
                            <button
                              type="button"
                              disabled
                              style={{
                                border: "1px solid var(--app-surface-border)",
                                borderRadius: "8px",
                                background: "var(--app-surface-soft-bg)",
                                color: "var(--app-text-subtle)",
                                padding: "7px 10px",
                                fontSize: "13px",
                                fontWeight: 700,
                                cursor: "not-allowed",
                              }}
                            >
                              Preparing PDF
                            </button>
                          )
                        )}
                      </div>
                    )}
                    {file.file_kind === "pdf" ? null : previewText ? (
                      expandedTextPreviewIds[file.stored_filename] ? (
                        <div
                          style={{
                            whiteSpace: "pre-wrap",
                            lineHeight: "1.7",
                            fontSize: "14px",
                            color: "var(--app-text-muted)",
                          }}
                        >
                          {previewText}
                        </div>
                      ) : (
                        <div
                          style={{
                            border: "1px dashed var(--app-surface-strong-border)",
                            borderRadius: "10px",
                            background: "var(--app-surface-bg)",
                            color: "var(--app-text-subtle)",
                            padding: "12px",
                            fontSize: "13px",
                            lineHeight: 1.6,
                          }}
                        >
                          Preview hidden. Full text is still used during analysis.
                        </div>
                      )
                    ) : (
                      <div style={{ lineHeight: "1.7", fontSize: "14px", color: "var(--app-text-muted)" }}>
                        (No preview available. Full text will be analyzed in backend.)
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {sessionAnalysis && (
          <div
            ref={analysisSectionRef}
            style={{
              display: "flex",
              flexDirection: "column",
              gap: "16px",
              marginBottom: "20px",
            }}
          >
            <div
              style={{ ...manualNestedPanelStyle, marginBottom: 0 }}
            >
              <div
                style={{
                  display: "flex",
                  gap: "12px",
                  alignItems: "center",
                  flexWrap: "wrap",
                }}
              >
                <div
                  style={{
                    fontSize: "14px",
                    color: availableInSignals ? "var(--app-success-fg)" : "var(--app-text-muted)",
                    fontWeight: 600,
                  }}
                >
                  {availableInSignals
                    ? "Analysis completed and sent to Signals. Save a signal completion note there when you want it to enter Workspace."
                    : "Analysis completed."}
                </div>
              </div>

              {availableInSignals && currentSessionId && (
                <div
                  style={{
                    marginTop: "16px",
                    padding: "14px 16px",
                    borderRadius: "10px",
                    border: "1px solid var(--app-success-border)",
                    background: "var(--app-success-bg)",
                  }}
                >
                  <div
                    style={{
                      fontSize: "14px",
                      fontWeight: 600,
                      color: "var(--app-success-fg)",
                      marginBottom: "8px",
                    }}
                  >
                    This manual session is now available in Signals.
                  </div>

                  <Link
                    href={`/signals/detail?id=${encodeURIComponent(`manual_${currentSessionId}`)}`}
                    style={{
                      textDecoration: "none",
                      fontSize: "14px",
                      fontWeight: 600,
                      color: "var(--app-info-fg)",
                    }}
                  >
                    Open in Signals
                  </Link>
                </div>
              )}
            </div>

            <AnalysisCard title="Summary" content={sessionAnalysis.summary} />
            <AnalysisCard title="Why it matters" content={sessionAnalysis.why_it_matters} />
            <AnalysisCard
              title="Relevance to projects"
              content={sessionAnalysis.relevance_to_projects}
            />
            <AnalysisCard
              title="Relevance to career"
              content={sessionAnalysis.relevance_to_career}
            />
            <AnalysisCard
              title="Synthesized insight"
              content={sessionAnalysis.synthesized_insight}
            />

            <div
              style={{ ...manualNestedPanelStyle, marginBottom: 0 }}
            >
              <div
                style={{
                  fontSize: "13px",
                  color: "var(--app-text-subtle)",
                  marginBottom: "10px",
                  textTransform: "uppercase",
                  letterSpacing: 0,
                }}
              >
                Related Deep Reflections
              </div>

              {relatedReflectionTopics.length > 0 && (
                <div style={{ fontSize: "14px", color: "var(--app-text-subtle)", marginBottom: "12px" }}>
                  Matching topics: {relatedReflectionTopics.join(", ")}
                </div>
              )}

              {relatedReflectionsLoading ? (
                <div style={{ fontSize: "14px", color: "var(--app-text-subtle)" }}>
                  Loading related deep reflections...
                </div>
              ) : relatedReflections.length === 0 ? (
                <div style={{ fontSize: "14px", color: "var(--app-text-subtle)" }}>
                  No closely related deep reflections found for this manual session yet.
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                  {relatedReflections.map((item) => (
                    <div
                      key={item.id || item.title}
                      style={{
                        border: "1px solid var(--app-surface-border)",
                        borderRadius: "12px",
                        padding: "14px",
                        background: "var(--app-surface-muted-bg)",
                      }}
                    >
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          gap: "12px",
                          flexWrap: "wrap",
                          marginBottom: "8px",
                        }}
                      >
                        <Link
                          href={`/reflections/${encodeURIComponent(item.id || "")}`}
                          style={{
                            fontSize: "15px",
                            fontWeight: 700,
                            color: "var(--app-text-strong)",
                            textDecoration: "none",
                            lineHeight: 1.4,
                          }}
                        >
                          {item.title || item.id || "Untitled deep reflection"}
                        </Link>

                        {item.match_score !== undefined && (
                          <span
                            style={{
                              borderRadius: "999px",
                              padding: "4px 10px",
                              background: "var(--app-info-bg)",
                              color: "var(--app-info-fg)",
                              border: "1px solid var(--app-info-border)",
                              fontSize: "12px",
                              fontWeight: 600,
                              whiteSpace: "nowrap",
                            }}
                          >
                            Match {item.match_score}
                          </span>
                        )}
                      </div>

                      <div
                        style={{
                          fontSize: "13px",
                          color: "var(--app-text-subtle)",
                          display: "flex",
                          gap: "12px",
                          flexWrap: "wrap",
                          marginBottom: "8px",
                        }}
                      >
                        <span>Source: {item.source || "unknown"}</span>
                        <span>
                          Updated: {item.timestamp ? new Date(item.timestamp).toLocaleString() : "Unknown"}
                        </span>
                      </div>

                      {(item.matched_topics || []).length > 0 && (
                        <div style={{ fontSize: "13px", color: "var(--app-text-muted)", marginBottom: "6px" }}>
                          Matched topics: {(item.matched_topics || []).join(", ")}
                        </div>
                      )}

                      {(item.matched_terms || []).length > 0 && (
                        <div style={{ fontSize: "13px", color: "var(--app-text-muted)", marginBottom: "6px" }}>
                          Matched terms: {(item.matched_terms || []).join(", ")}
                        </div>
                      )}

                      {(item.tags || []).length > 0 && (
                        <div
                          style={{
                            display: "flex",
                            gap: "8px",
                            flexWrap: "wrap",
                            marginTop: "10px",
                          }}
                        >
                          {(item.tags || []).map((tag) => (
                            <span
                              key={`${item.id || item.title}-${tag}`}
                              style={{
                                borderRadius: "999px",
                                padding: "4px 10px",
                                background: "var(--app-chip-bg)",
                                color: "var(--app-chip-fg)",
                                fontSize: "12px",
                                border: "1px solid var(--app-chip-border)",
                              }}
                            >
                              {tag}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        <section style={{ ...manualPanelStyle, marginBottom: "32px" }}>
          <div style={manualPanelHeaderStyle}>
            <div>
              <div style={manualPanelEyebrowStyle}>Manual queue</div>
              <h2 style={manualPanelTitleStyle}>Saved manual sessions</h2>
              <p style={manualPanelDescriptionStyle}>
                Review intake history, see which sessions need analysis, and continue completed material into Signals or Workspace.
              </p>
            </div>

            <button
              onClick={loadSavedSessions}
              disabled={sessionsLoading}
              style={{
                padding: "10px 16px",
                borderRadius: "8px",
                border: "1px solid var(--app-secondary-action-border)",
                background: sessionsLoading ? "var(--app-surface-soft-bg)" : "var(--app-secondary-action-bg)",
                color: sessionsLoading ? "var(--app-text-subtle)" : "var(--app-secondary-action-fg)",
                cursor: sessionsLoading ? "not-allowed" : "pointer",
                fontWeight: 700,
              }}
            >
              {sessionsLoading ? "Refreshing..." : "Refresh Sessions"}
            </button>
          </div>

          {sessionsMessage && (
            <div style={{ marginBottom: "14px", fontSize: "13px", color: "var(--app-text-subtle)" }}>
              {sessionsMessage}
            </div>
          )}

          {savedSessions.length > 0 && (
            <div style={{ marginBottom: "14px", display: "grid", gap: "8px" }}>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 150px), 1fr))",
                  gap: "8px",
                }}
              >
                <ManualSessionSummaryCard label="Total Sessions" value={workspaceStatusCounts.all} />
                <ManualSessionSummaryCard label="In Workspace" value={workspaceStatusCounts.workspace_saved} />
                <ManualSessionSummaryCard
                  label="Ready To Complete"
                  value={workspaceStatusCounts.analyzed_not_in_workspace}
                />
                <ManualSessionSummaryCard label="Needs Analysis" value={workspaceStatusCounts.needs_analysis} />
              </div>
              <ManualHandoffWorkbench
                counts={handoffStageCounts}
                selected={selectedHandoffStage}
                onSelect={(stage) => setSelectedHandoffStage(stage)}
              />
              <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                <ManualSessionFilterButton
                  label="All Review"
                  count={sessionReviewPriorityCounts.all}
                  active={selectedSessionReviewPriority === "all"}
                  onClick={() => setSelectedSessionReviewPriority("all")}
                />
                <ManualSessionFilterButton
                  label="Do Not Act"
                  count={sessionReviewPriorityCounts.do_not_act}
                  active={selectedSessionReviewPriority === "do_not_act"}
                  onClick={() => setSelectedSessionReviewPriority("do_not_act")}
                />
                <ManualSessionFilterButton
                  label="Review Required"
                  count={sessionReviewPriorityCounts.review_required}
                  active={selectedSessionReviewPriority === "review_required"}
                  onClick={() => setSelectedSessionReviewPriority("review_required")}
                />
                <ManualSessionFilterButton
                  label="Review Before Action"
                  count={sessionReviewPriorityCounts.review_before_action}
                  active={selectedSessionReviewPriority === "review_before_action"}
                  onClick={() => setSelectedSessionReviewPriority("review_before_action")}
                />
                <ManualSessionFilterButton
                  label="Low-Risk Review"
                  count={sessionReviewPriorityCounts.ready_for_low_risk_review}
                  active={selectedSessionReviewPriority === "ready_for_low_risk_review"}
                  onClick={() => setSelectedSessionReviewPriority("ready_for_low_risk_review")}
                />
                <ManualSessionFilterButton
                  label="Unknown"
                  count={sessionReviewPriorityCounts.unknown}
                  active={selectedSessionReviewPriority === "unknown"}
                  onClick={() => setSelectedSessionReviewPriority("unknown")}
                />
              </div>
              <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                <ManualSessionFilterButton
                  label="All Workspace"
                  count={workspaceStatusCounts.all}
                  active={selectedWorkspaceStatus === "all"}
                  onClick={() => setSelectedWorkspaceStatus("all")}
                />
                <ManualSessionFilterButton
                  label="In Workspace"
                  count={workspaceStatusCounts.workspace_saved}
                  active={selectedWorkspaceStatus === "workspace_saved"}
                  onClick={() => setSelectedWorkspaceStatus("workspace_saved")}
                />
                <ManualSessionFilterButton
                  label="Not in Workspace"
                  count={workspaceStatusCounts.not_in_workspace}
                  active={selectedWorkspaceStatus === "not_in_workspace"}
                  onClick={() => setSelectedWorkspaceStatus("not_in_workspace")}
                />
              </div>
              <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                <ManualSessionFilterButton
                  label="All Handoff"
                  count={handoffStageCounts.all}
                  active={selectedHandoffStage === "all"}
                  onClick={() => setSelectedHandoffStage("all")}
                />
                <ManualSessionFilterButton
                  label="Workspace Done"
                  count={handoffStageCounts.workspace_done}
                  active={selectedHandoffStage === "workspace_done"}
                  onClick={() => setSelectedHandoffStage("workspace_done")}
                />
                <ManualSessionFilterButton
                  label="Ready For Signal Review"
                  count={handoffStageCounts.ready_for_signal_review}
                  active={selectedHandoffStage === "ready_for_signal_review"}
                  onClick={() => setSelectedHandoffStage("ready_for_signal_review")}
                />
                <ManualSessionFilterButton
                  label="Needs Insight"
                  count={handoffStageCounts.needs_insight}
                  active={selectedHandoffStage === "needs_insight"}
                  onClick={() => setSelectedHandoffStage("needs_insight")}
                />
                <ManualSessionFilterButton
                  label="Pending Analysis"
                  count={handoffStageCounts.pending_analysis}
                  active={selectedHandoffStage === "pending_analysis"}
                  onClick={() => setSelectedHandoffStage("pending_analysis")}
                />
              </div>
            </div>
          )}

          {savedSessions.length === 0 ? (
            <ManualSessionsStateCard
              title={sessionsMessage.includes("Admin login") ? "Admin login required" : "No saved manual sessions yet"}
              description={
                sessionsMessage.includes("Admin login")
                  ? "Saved manual sessions are not requested until an admin token is available. Open Admin, log in, then refresh this list."
                  : "Upload files above to create a manual session. After upload or analysis, it will appear here for review and Signal handoff."
              }
              primaryHref={sessionsMessage.includes("Admin login") ? "/admin" : undefined}
              primaryLabel={sessionsMessage.includes("Admin login") ? "Open Admin" : undefined}
            />
          ) : visibleSavedSessions.length === 0 ? (
            <ManualSessionsStateCard
              title="No sessions match these filters"
              description="Saved sessions exist, but none match the selected review-priority, Workspace, and handoff filters. Reset the filters to see the full manual-session history."
              actionLabel="Show All Sessions"
              onAction={() => {
                setSelectedSessionReviewPriority("all");
                setSelectedWorkspaceStatus("all");
                setSelectedHandoffStage("all");
              }}
            />
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
              {visibleSavedSessions.map((session) => {
                const isExpanded = expandedSessionId === session.session_id;
                const isCurrent = currentSessionId === session.session_id;
                const verification = getSessionVerification(session);
                const reviewPriority = getSessionReviewPriority(session);
                const hasWorkspaceRecord = Boolean(session.workspace_saved && session.workspace_file_name);
                const workspaceRecordHref = hasWorkspaceRecord
                  ? `/workspace/detail?file_name=${encodeURIComponent(session.workspace_file_name || "")}`
                  : "";
                const manualSignalHref = `/signals/detail?id=${encodeURIComponent(`manual_${session.session_id}`)}`;
                const nextAction = getManualSessionNextAction(session);
                const handoffStage = getManualSessionHandoffStage(session);
                const sourceStatedConfidenceText = getSourceStatedConfidenceText(
                  session.source_stated_confidence
                );
                const hasSourceLimitsMetadata =
                  Boolean(session.source_stated_limits) ||
                  Boolean(sourceStatedConfidenceText) ||
                  Boolean(session.source_stated_limits_not_applicable) ||
                  Boolean(session.source_stated_limits_status);

                return (
                  <div
                    key={session.session_id}
                    style={{
                      border: "1px solid var(--app-surface-border)",
                      borderRadius: "12px",
                      padding: "16px",
                      background: isCurrent ? "var(--app-info-bg)" : "var(--app-surface-muted-bg)",
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "flex-start",
                        gap: "14px",
                        flexWrap: "wrap",
                      }}
                    >
                      <div
                        style={{
                          fontSize: "15px",
                          fontWeight: 700,
                          color: "var(--app-text-strong)",
                          minWidth: "220px",
                          paddingTop: "4px",
                        }}
                      >
                        {session.title || "Untitled Manual Session"}
                      </div>

                      <div
                        style={{
                          display: "flex",
                          gap: "10px",
                          flexWrap: "wrap",
                          alignItems: "flex-start",
                          justifyContent: "flex-end",
                        }}
                      >
                        {!session.workspace_saved && session.analysis_status !== "completed" ? (
                          <Link
                            href={`/manual/detail?id=${encodeURIComponent(session.session_id)}`}
                            style={{
                              padding: "10px 14px",
                              borderRadius: "8px",
                              border: "1px solid var(--app-primary-action-border)",
                              background: "var(--app-primary-action-bg)",
                              color: "var(--app-primary-action-fg)",
                              textDecoration: "none",
                              fontWeight: 700,
                            }}
                          >
                            Generate Insight
                          </Link>
                        ) : null}

                        {session.analysis_status === "completed" && !session.workspace_saved ? (
                          <Link
                            href={manualSignalHref}
                            style={{
                              padding: "10px 14px",
                              borderRadius: "8px",
                              border: "1px solid var(--app-primary-action-border)",
                              background: "var(--app-primary-action-bg)",
                              color: "var(--app-primary-action-fg)",
                              textDecoration: "none",
                              fontWeight: 700,
                            }}
                          >
                            Open in Signals
                          </Link>
                        ) : null}

                        {hasWorkspaceRecord ? (
                          <Link
                            href={workspaceRecordHref}
                            style={{
                              padding: "10px 14px",
                              borderRadius: "8px",
                              border: "1px solid var(--app-success-border)",
                              background: "var(--app-success-bg)",
                              color: "var(--app-success-fg)",
                              textDecoration: "none",
                              fontWeight: 700,
                            }}
                          >
                            Open Workspace Record
                          </Link>
                        ) : null}

                        <button
                          onClick={() =>
                            setExpandedSessionId(isExpanded ? null : session.session_id)
                          }
                          style={{
                            padding: "10px 14px",
                            borderRadius: "8px",
                            border: "1px solid var(--app-secondary-action-border)",
                            background: "var(--app-secondary-action-bg)",
                            color: "var(--app-secondary-action-fg)",
                            cursor: "pointer",
                            fontWeight: 700,
                          }}
                        >
                          {isExpanded ? "Hide Files" : "View Files"}
                        </button>

                        <Link
                          href={`/manual/detail?id=${encodeURIComponent(session.session_id)}`}
                          style={{
                            padding: "10px 14px",
                            borderRadius: "8px",
                            border: "1px solid var(--app-info-border)",
                            background: "var(--app-info-bg)",
                            color: "var(--app-info-fg)",
                            textDecoration: "none",
                            fontWeight: 600,
                          }}
                        >
                          Open Session Detail
                        </Link>
                      </div>
                    </div>

                    <div>
                        <div
                          style={{
                            marginTop: "10px",
                            border:
                              nextAction.tone === "done"
                                ? "1px solid var(--app-success-border)"
                                : "1px solid var(--app-info-border)",
                            borderRadius: "10px",
                            background:
                              nextAction.tone === "done"
                                ? "var(--app-success-bg)"
                                : "var(--app-info-bg)",
                            padding: "10px 12px",
                            display: "grid",
                            gap: "5px",
                          }}
                        >
                          <span
                            style={{
                              fontSize: "11px",
                              color:
                                nextAction.tone === "done"
                                  ? "var(--app-success-fg)"
                                  : "var(--app-info-fg)",
                              fontWeight: 800,
                              letterSpacing: 0,
                              textTransform: "uppercase",
                            }}
                          >
                            Next Action
                          </span>
                          <strong
                            style={{
                              color:
                                nextAction.tone === "done"
                                  ? "var(--app-success-fg)"
                                  : "var(--app-text-strong)",
                            }}
                          >
                            {nextAction.label}
                          </strong>
                          <span style={{ color: "var(--app-text-muted)", fontSize: "13px", lineHeight: 1.55 }}>
                            {nextAction.detail}
                          </span>
                        </div>

                        <div
                          style={{
                            marginTop: "8px",
                            display: "flex",
                            gap: "10px",
                            flexWrap: "wrap",
                            fontSize: "13px",
                            color: "var(--app-text-subtle)",
                          }}
                        >
                          <span>{formatDateTime(session.created_at)}</span>
                          <span>•</span>
                          <span>{session.file_count || 0} files</span>
                          <span>•</span>
                          <span>
                            {(session.file_types || []).length > 0
                              ? (session.file_types || []).join(" / ")
                              : "unknown"}
                          </span>
                        </div>

                        <div
                          style={{
                            marginTop: "8px",
                            display: "flex",
                            gap: "10px",
                            flexWrap: "wrap",
                            fontSize: "13px",
                          }}
                        >
                          <span
                            style={{
                              padding: "4px 8px",
                              borderRadius: "999px",
                              background: "var(--app-chip-bg)",
                              color: "var(--app-chip-fg)",
                            }}
                          >
                            Analysis: {session.analysis_status || "not_started"}
                          </span>

                          <span
                            style={{
                              padding: "4px 8px",
                              borderRadius: "999px",
                              background:
                                session.analysis_status === "completed"
                                  ? "var(--app-info-bg)"
                                  : "var(--app-chip-bg)",
                              color:
                                session.analysis_status === "completed"
                                  ? "var(--app-info-fg)"
                                  : "var(--app-chip-fg)",
                            }}
                          >
                            {session.analysis_status === "completed"
                              ? "Available in Signals"
                              : "Not analyzed yet"}
                          </span>

                          {isCurrent && (
                            <span
                              style={{
                                padding: "4px 8px",
                                borderRadius: "999px",
                                background: "var(--app-info-bg)",
                                color: "var(--app-info-fg)",
                              }}
                            >
                              Current session
                            </span>
                          )}

                          {reviewPriority && (
                            <span
                              style={{
                                padding: "4px 8px",
                                borderRadius: "999px",
                                background: reviewPriority.background,
                                color: reviewPriority.color,
                                border: reviewPriority.border,
                                fontWeight: 700,
                              }}
                            >
                              {reviewPriority.label}
                            </span>
                          )}

                          <span
                            style={{
                              padding: "4px 8px",
                              borderRadius: "999px",
                              background:
                                handoffStage.tone === "done"
                                  ? "var(--app-success-bg)"
                                  : handoffStage.tone === "ready"
                                    ? "var(--app-info-bg)"
                                    : handoffStage.tone === "warning"
                                      ? "var(--app-warning-bg)"
                                      : "var(--app-chip-bg)",
                              color:
                                handoffStage.tone === "done"
                                  ? "var(--app-success-fg)"
                                  : handoffStage.tone === "ready"
                                    ? "var(--app-info-fg)"
                                    : handoffStage.tone === "warning"
                                      ? "var(--app-warning-fg)"
                                      : "var(--app-chip-fg)",
                              border:
                                handoffStage.tone === "done"
                                  ? "1px solid var(--app-success-border)"
                                  : handoffStage.tone === "ready"
                                    ? "1px solid var(--app-info-border)"
                                    : handoffStage.tone === "warning"
                                      ? "1px solid var(--app-warning-border)"
                                      : "1px solid var(--app-chip-border)",
                              fontWeight: 700,
                            }}
                            title={handoffStage.detail}
                          >
                            {handoffStage.label}
                          </span>

                          <span
                            style={{
                              padding: "4px 8px",
                              borderRadius: "999px",
                              background: session.workspace_saved
                                ? "var(--app-success-bg)"
                                : "var(--app-chip-bg)",
                              color: session.workspace_saved
                                ? "var(--app-success-fg)"
                                : "var(--app-chip-fg)",
                              border: session.workspace_saved
                                ? "1px solid var(--app-success-border)"
                                : "1px solid var(--app-chip-border)",
                              fontWeight: session.workspace_saved ? 700 : 500,
                            }}
                          >
                            {session.workspace_saved ? "Workspace saved" : "Not in Workspace"}
                          </span>
                        </div>

                        {session.workspace_saved ? (
                          <div
                            style={{
                              marginTop: "8px",
                              fontSize: "13px",
                              lineHeight: 1.6,
                              color: "var(--app-success-fg)",
                            }}
                          >
                            Completed into Workspace
                            {session.workspace_saved_at ? `: ${formatDateTime(session.workspace_saved_at)}` : ""}.
                          </div>
                        ) : session.analysis_status === "completed" ? (
                          <div
                            style={{
                              marginTop: "8px",
                              fontSize: "13px",
                              lineHeight: 1.6,
                              color: "var(--app-text-subtle)",
                            }}
                          >
                            Insight is ready; open Signal Detail to review Evidence Note, Project Takeaway Gate, and the right-side Manual Completion Route before Workspace completion.
                          </div>
                        ) : null}

                        {(session.upload_reason || session.intended_use || session.cognitive_layer) && (
                          <div
                            style={{
                              marginTop: "8px",
                              fontSize: "13px",
                              lineHeight: 1.6,
                              color: "var(--app-text-muted)",
                            }}
                          >
                            {session.upload_reason ? <div>Reason: {session.upload_reason}</div> : null}
                            {session.intended_use ? <div>Use: {session.intended_use}</div> : null}
                            <div>Layer: {formatCompactLabel(session.cognitive_layer || "unclassified")}</div>
                          </div>
                        )}

                        {hasSourceLimitsMetadata ? (
                          <div
                            style={{
                              marginTop: "8px",
                              fontSize: "13px",
                              lineHeight: 1.6,
                              color: "var(--app-text-muted)",
                            }}
                          >
                            <div>
                              Source limits:{" "}
                              {session.source_stated_limits_not_applicable
                                ? "Not applicable"
                                : session.source_stated_limits || "Captured status only"}
                            </div>
                            {sourceStatedConfidenceText ? (
                              <div>Source confidence: {sourceStatedConfidenceText}</div>
                            ) : null}
                          </div>
                        ) : null}

                        {verification && (
                          <div
                            style={{
                              marginTop: "8px",
                              fontSize: "13px",
                              lineHeight: 1.6,
                              color: "var(--app-text-subtle)",
                            }}
                          >
                            Verification: {formatCompactLabel(verification.verification_status)}
                            {verification.confidence_label
                              ? ` | Confidence: ${formatCompactLabel(verification.confidence_label)}`
                              : ""}
                            {typeof verification.confidence_score === "number"
                              ? ` (${verification.confidence_score.toFixed(2)})`
                              : ""}
                          </div>
                        )}

                        {verification ? (
                          <VerificationGateNote
                            verification={verification}
                            accentColor={reviewPriority?.color}
                            style={{ marginTop: "8px" }}
                          />
                        ) : null}
                    </div>

                    {isExpanded && (
                      <div
                        style={{
                          marginTop: "14px",
                          borderTop: "1px solid var(--app-surface-border)",
                          paddingTop: "14px",
                          display: "flex",
                          flexDirection: "column",
                          gap: "10px",
                        }}
                      >
                        {(session.files || []).length === 0 ? (
                          <div style={{ fontSize: "13px", color: "var(--app-text-subtle)" }}>
                            No file metadata found.
                          </div>
                        ) : (
                          session.files?.map((file) => (
                            <div
                              key={`${session.session_id}-${file.stored_filename}`}
                              style={{
                                border: "1px solid var(--app-surface-border)",
                                borderRadius: "10px",
                                padding: "12px",
                                background: "var(--app-surface-bg)",
                                display: "flex",
                                justifyContent: "space-between",
                                gap: "12px",
                                flexWrap: "wrap",
                                alignItems: "center",
                              }}
                            >
                              <div>
                                <div style={{ fontSize: "14px", fontWeight: 600 }}>
                                  {file.original_filename}
                                </div>
                                <div style={{ marginTop: "4px", fontSize: "12px", color: "var(--app-text-subtle)" }}>
                                  type: {file.file_kind}
                                </div>
                              </div>

                              {getManualFileUrl(file.stored_filename) ? (
                                <a
                                  href={getManualFileUrl(file.stored_filename)}
                                  download={file.original_filename}
                                  target="_blank"
                                  rel="noreferrer"
                                  style={{
                                    textDecoration: "none",
                                    fontSize: "14px",
                                    fontWeight: 600,
                                    color: "var(--app-info-fg)",
                                  }}
                                >
                                  Open File
                                </a>
                              ) : (
                                <span
                                  style={{
                                    fontSize: "14px",
                                    fontWeight: 600,
                                    color: "var(--app-text-subtle)",
                                  }}
                                >
                                  Preparing file...
                                </span>
                              )}
                            </div>
                          ))
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </section>
        </RequireAdminAuth>
      </AppContainer>

      {currentLightboxFile && (
        <div
          onClick={closeLightbox}
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.78)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 9999,
            padding: "32px",
          }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              position: "relative",
              maxWidth: "92vw",
              maxHeight: "90vh",
              width: "100%",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: "16px",
            }}
          >
            <button
              onClick={showPrevImage}
              style={{
                border: "none",
                background: "rgba(255,255,255,0.18)",
                color: "white",
                width: "48px",
                height: "48px",
                borderRadius: "999px",
                fontSize: "24px",
                cursor: "pointer",
                flexShrink: 0,
              }}
            >
              鈥?
            </button>

            <div
              style={{
                background: "black",
                borderRadius: "12px",
                padding: "16px",
                maxWidth: "80vw",
                maxHeight: "86vh",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                boxShadow: "0 10px 30px rgba(0,0,0,0.35)",
              }}
            >
              {getManualFileUrl(currentLightboxFile.stored_filename) ? (
                <Image
                  src={getManualFileUrl(currentLightboxFile.stored_filename)}
                  alt={currentLightboxFile.original_filename}
                  width={1600}
                  height={1200}
                  unoptimized
                  style={{
                    maxWidth: "78vw",
                    maxHeight: "72vh",
                    width: "auto",
                    height: "auto",
                    borderRadius: "10px",
                    display: "block",
                  }}
                />
              ) : (
                <div
                  style={{
                    width: "78vw",
                    maxWidth: "960px",
                    height: "60vh",
                    maxHeight: "720px",
                    borderRadius: "10px",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    background: "black",
                    color: "white",
                    fontSize: "14px",
                  }}
                >
                  Preparing preview...
                </div>
              )}

              <div
                style={{
                  marginTop: "12px",
                  color: "white",
                  fontSize: "14px",
                  lineHeight: "1.6",
                  textAlign: "center",
                  wordBreak: "break-word",
                  maxWidth: "72vw",
                }}
              >
                {currentLightboxFile.original_filename}
              </div>
            </div>

            <button
              onClick={showNextImage}
              style={{
                border: "none",
                background: "rgba(255,255,255,0.18)",
                color: "white",
                width: "48px",
                height: "48px",
                borderRadius: "999px",
                fontSize: "24px",
                cursor: "pointer",
                flexShrink: 0,
              }}
            >
              鈥?
            </button>

            <button
              onClick={closeLightbox}
              style={{
                position: "absolute",
                top: "-10px",
                right: "-4px",
                border: "none",
                background: "rgba(255,255,255,0.18)",
                color: "white",
                width: "42px",
                height: "42px",
                borderRadius: "999px",
                fontSize: "22px",
                cursor: "pointer",
              }}
            >
              脳
            </button>
          </div>
        </div>
      )}
    </>
  );
}

function ManualHero({
  selectedFileCount,
  uploadedFileCount,
  savedSessionCount,
  readyForReviewCount,
  workspaceCount,
}: {
  selectedFileCount: number;
  uploadedFileCount: number;
  savedSessionCount: number;
  readyForReviewCount: number;
  workspaceCount: number;
}) {
  const metrics = [
    {
      label: "Selected",
      value: selectedFileCount,
      detail: "Files staged now",
      icon: FileUp,
      color: "var(--app-info-fg)",
    },
    {
      label: "Uploaded",
      value: uploadedFileCount,
      detail: "Current session",
      icon: UploadCloud,
      color: "var(--app-success-fg)",
    },
    {
      label: "Saved",
      value: savedSessionCount,
      detail: "Manual sessions",
      icon: Database,
      color: "var(--app-warning-fg)",
    },
    {
      label: "Review",
      value: readyForReviewCount,
      detail: "Ready for Signals",
      icon: ShieldCheck,
      color: "var(--app-info-fg)",
    },
  ];

  return (
    <section style={manualHeroStyle}>
      <div style={manualHeroCopyStyle}>
        <div style={manualEyebrowStyle}>
          <FileText size={16} strokeWidth={2.2} />
          Manual Intake
        </div>
        <h1 style={manualHeroTitleStyle}>Turn source material into reviewable signals.</h1>
        <p style={manualHeroDescriptionStyle}>
          Capture PDFs, notes, screenshots, and source links with their intent preserved. AI Radar keeps the raw source separate from interpretation before it moves into Signal review or Workspace.
        </p>
        <div style={manualQuickActionRowStyle}>
          <Link href="/signals?source=manual" style={manualPrimaryActionStyle}>
            <Radar size={16} strokeWidth={2.3} />
            Manual Signals
          </Link>
          <Link href="/workspace" style={manualSecondaryActionStyle}>
            <Database size={16} strokeWidth={2.3} />
            Workspace
          </Link>
        </div>
      </div>

      <div style={manualHeroPanelStyle}>
        <div style={manualHeroPanelHeaderStyle}>
          <span>Current intake state</span>
          <strong>{workspaceCount}</strong>
        </div>
        <div style={manualHeroMetricGridStyle}>
          {metrics.map((metric) => {
            const Icon = metric.icon;
            return (
              <div key={metric.label} style={manualHeroMetricStyle}>
                <div style={{ ...manualHeroMetricIconStyle, color: metric.color }}>
                  <Icon size={18} strokeWidth={2.3} />
                </div>
                <strong style={manualHeroMetricValueStyle}>{metric.value}</strong>
                <span style={manualHeroMetricLabelStyle}>{metric.label}</span>
                <span style={manualHeroMetricDetailStyle}>{metric.detail}</span>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}

const manualShellStyle: CSSProperties = {
  maxWidth: "1360px",
  paddingTop: "28px",
};

const manualHeroStyle: CSSProperties = {
  border: "1px solid var(--app-surface-strong-border)",
  borderRadius: "8px",
  background: "var(--app-surface-bg)",
  padding: "clamp(22px, 3vw, 34px)",
  marginBottom: "22px",
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 420px), 1fr))",
  gap: "24px",
  alignItems: "stretch",
};

const manualHeroCopyStyle: CSSProperties = {
  minWidth: 0,
  display: "flex",
  flexDirection: "column",
  justifyContent: "center",
};

const manualEyebrowStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: "8px",
  width: "fit-content",
  color: "var(--app-text-subtle)",
  fontSize: "12px",
  fontWeight: 800,
  letterSpacing: 0,
  textTransform: "uppercase",
};

const manualHeroTitleStyle: CSSProperties = {
  margin: "12px 0 0",
  color: "var(--app-text-strong)",
  fontSize: "clamp(32px, 5vw, 58px)",
  lineHeight: 0.96,
  fontWeight: 850,
  letterSpacing: 0,
  maxWidth: "820px",
};

const manualHeroDescriptionStyle: CSSProperties = {
  margin: "18px 0 0",
  color: "var(--app-text-muted)",
  fontSize: "16px",
  lineHeight: 1.7,
  maxWidth: "780px",
};

const manualQuickActionRowStyle: CSSProperties = {
  marginTop: "22px",
  display: "flex",
  gap: "10px",
  flexWrap: "wrap",
};

const manualPrimaryActionStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: "8px",
  border: "1px solid var(--app-primary-action-border)",
  borderRadius: "8px",
  background: "var(--app-primary-action-bg)",
  color: "var(--app-primary-action-fg)",
  padding: "10px 13px",
  fontSize: "14px",
  fontWeight: 800,
  textDecoration: "none",
};

const manualSecondaryActionStyle: CSSProperties = {
  ...manualPrimaryActionStyle,
  border: "1px solid var(--app-secondary-action-border)",
  background: "var(--app-secondary-action-bg)",
  color: "var(--app-secondary-action-fg)",
};

const manualHeroPanelStyle: CSSProperties = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-soft-bg)",
  padding: "14px",
  display: "grid",
  gap: "12px",
  boxShadow: "var(--app-surface-shadow)",
};

const manualHeroPanelHeaderStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  gap: "12px",
  color: "var(--app-text-subtle)",
  fontSize: "12px",
  fontWeight: 800,
  textTransform: "uppercase",
  letterSpacing: 0,
};

const manualHeroMetricGridStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
  gap: "10px",
};

const manualHeroMetricStyle: CSSProperties = {
  minHeight: "126px",
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-bg)",
  padding: "12px",
  display: "grid",
  alignContent: "space-between",
};

const manualHeroMetricIconStyle: CSSProperties = {
  width: "30px",
  height: "30px",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
};

const manualHeroMetricValueStyle: CSSProperties = {
  color: "var(--app-text-strong)",
  fontSize: "28px",
  lineHeight: 1,
  fontWeight: 850,
};

const manualHeroMetricLabelStyle: CSSProperties = {
  color: "var(--app-text-muted)",
  fontSize: "13px",
  fontWeight: 800,
};

const manualHeroMetricDetailStyle: CSSProperties = {
  color: "var(--app-text-subtle)",
  fontSize: "12px",
  lineHeight: 1.35,
};

const manualPanelStyle: CSSProperties = {
  border: "1px solid var(--app-surface-strong-border)",
  borderRadius: "8px",
  padding: "20px",
  background: "var(--app-surface-bg)",
  marginBottom: "20px",
  boxShadow: "var(--app-surface-shadow)",
};

const manualPanelHeaderStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "flex-start",
  gap: "14px",
  flexWrap: "wrap",
  marginBottom: "16px",
};

const manualPanelEyebrowStyle: CSSProperties = {
  color: "var(--app-text-subtle)",
  fontSize: "12px",
  fontWeight: 850,
  letterSpacing: 0,
  textTransform: "uppercase",
};

const manualPanelTitleStyle: CSSProperties = {
  margin: "5px 0 0",
  color: "var(--app-text-strong)",
  fontSize: "22px",
  lineHeight: 1.15,
  fontWeight: 850,
  letterSpacing: 0,
};

const manualPanelDescriptionStyle: CSSProperties = {
  margin: "7px 0 0",
  color: "var(--app-text-muted)",
  fontSize: "14px",
  lineHeight: 1.6,
  maxWidth: "760px",
};

const manualPanelBadgeStyle: CSSProperties = {
  border: "1px solid var(--app-chip-border)",
  borderRadius: "999px",
  background: "var(--app-chip-bg)",
  color: "var(--app-chip-fg)",
  padding: "7px 10px",
  fontSize: "12px",
  fontWeight: 800,
  whiteSpace: "nowrap",
};

const manualFieldLabelStyle: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: "6px",
  color: "var(--app-text-muted)",
  fontSize: "13px",
};

const manualInputStyle: CSSProperties = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  color: "var(--app-text-strong)",
  padding: "10px 12px",
  fontSize: "14px",
};

const manualHelperTextStyle: CSSProperties = {
  color: "var(--app-text-subtle)",
  lineHeight: 1.45,
};

const manualNestedPanelStyle: CSSProperties = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "16px",
  padding: "20px",
  background: "var(--app-surface-bg)",
  marginBottom: "20px",
  boxShadow: "var(--app-surface-shadow)",
};

const manualNestedCardStyle: CSSProperties = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "10px",
  padding: "12px",
  background: "var(--app-surface-muted-bg)",
};

const manualMutedMetaStyle: CSSProperties = {
  color: "var(--app-text-subtle)",
  fontSize: "12px",
  lineHeight: 1.45,
};

function renderAnalysisContent(value: unknown): React.ReactNode {
  if (value === null || value === undefined || value === "") {
    return <span style={{ color: "var(--app-text-subtle)" }}>No content available yet.</span>;
  }

  if (typeof value === "string" || typeof value === "number") {
    return <span style={{ whiteSpace: "pre-wrap" }}>{String(value)}</span>;
  }

  if (Array.isArray(value)) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
        {value.map((item, index) => (
          <div
            key={index}
            style={{
              border: "1px solid var(--app-surface-border)",
              borderRadius: "10px",
              padding: "12px",
              background: "var(--app-surface-muted-bg)",
            }}
          >
            {renderAnalysisContent(item)}
          </div>
        ))}
      </div>
    );
  }

  if (typeof value === "object" && value !== null) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
        {Object.entries(value).map(([key, val]) => (
          <div
            key={key}
            style={{
              border: "1px solid var(--app-surface-border)",
              borderRadius: "10px",
              padding: "12px",
              background: "var(--app-surface-muted-bg)",
            }}
          >
            <div
              style={{
                fontSize: "13px",
                fontWeight: 600,
                marginBottom: "6px",
                color: "var(--app-text-strong)",
              }}
            >
              {key}
            </div>

            <div
              style={{
                fontSize: "14px",
                lineHeight: "1.7",
                color: "var(--app-text-muted)",
                whiteSpace: "pre-wrap",
              }}
            >
              {renderAnalysisContent(val)}
            </div>
          </div>
        ))}
      </div>
    );
  }

  return <span>{String(value)}</span>;
}

function ManualSessionFilterButton({
  label,
  count,
  active,
  onClick,
}: {
  label: string;
  count: number;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      style={{
        border: active
          ? "1px solid var(--app-primary-action-border)"
          : "1px solid var(--app-secondary-action-border)",
        background: active ? "var(--app-primary-action-bg)" : "var(--app-secondary-action-bg)",
        color: active ? "var(--app-primary-action-fg)" : "var(--app-secondary-action-fg)",
        borderRadius: "999px",
        padding: "7px 10px",
        cursor: "pointer",
        fontSize: "12px",
        fontWeight: 700,
      }}
    >
      {label} ({count})
    </button>
  );
}

function ManualSessionSummaryCard({
  label,
  value,
}: {
  label: string;
  value: number;
}) {
  return (
    <div
      style={{
        border: "1px solid var(--app-surface-border)",
        borderRadius: "8px",
        background: "var(--app-surface-muted-bg)",
        padding: "10px 12px",
        display: "grid",
        gap: "4px",
      }}
    >
      <span
        style={{
          color: "var(--app-text-subtle)",
          fontSize: "11px",
          fontWeight: 700,
          letterSpacing: 0,
          textTransform: "uppercase",
        }}
      >
        {label}
      </span>
      <strong style={{ color: "var(--app-text-strong)", fontSize: "20px", lineHeight: 1.1 }}>{value}</strong>
    </div>
  );
}

function ManualHandoffWorkbench({
  counts,
  selected,
  onSelect,
}: {
  counts: Record<ManualHandoffFilter, number>;
  selected: ManualHandoffFilter;
  onSelect: (stage: ManualHandoffFilter) => void;
}) {
  const cards: Array<{
    key: ManualHandoffFilter;
    label: string;
    detail: string;
    value: number;
  }> = [
    {
      key: "workspace_done",
      label: "Workspace Done",
      detail: "Already durable; use Workspace as the source of truth.",
      value: counts.workspace_done,
    },
    {
      key: "ready_for_signal_review",
      label: "Ready For Signal Review",
      detail: "Insight exists; review Signal Detail before Workspace or Project Takeaway routing.",
      value: counts.ready_for_signal_review,
    },
    {
      key: "needs_insight",
      label: "Needs Insight",
      detail: "Uploaded material exists but needs structured insight generation.",
      value: counts.needs_insight,
    },
    {
      key: "pending_analysis",
      label: "Pending Analysis",
      detail: "Session detail should be checked before entering the signal workflow.",
      value: counts.pending_analysis,
    },
  ];

  return (
    <div
      style={{
        border: "1px solid var(--app-surface-border)",
        borderRadius: "8px",
        background: "var(--app-surface-muted-bg)",
        padding: "12px",
        display: "grid",
        gap: "10px",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", gap: "10px", flexWrap: "wrap" }}>
        <div>
          <span
            style={{
              color: "var(--app-text-subtle)",
              fontSize: "11px",
              fontWeight: 800,
              letterSpacing: 0,
              textTransform: "uppercase",
            }}
          >
            Manual Handoff Readiness
          </span>
          <div style={{ marginTop: "4px", color: "var(--app-text-muted)", fontSize: "13px", lineHeight: 1.5 }}>
            Move from uploaded material to Signal review, Project Takeaway judgment, or Workspace completion.
          </div>
          <div style={{ marginTop: "6px", color: "var(--app-text-strong)", fontSize: "13px", lineHeight: 1.5, fontWeight: 700 }}>
            {buildManualHandoffFocus(counts)}
          </div>
        </div>
        <button
          type="button"
          onClick={() => onSelect("all")}
          style={{
            border:
              selected === "all"
                ? "1px solid var(--app-primary-action-border)"
                : "1px solid var(--app-secondary-action-border)",
            borderRadius: "8px",
            background:
              selected === "all"
                ? "var(--app-primary-action-bg)"
                : "var(--app-secondary-action-bg)",
            color:
              selected === "all"
                ? "var(--app-primary-action-fg)"
                : "var(--app-secondary-action-fg)",
            padding: "8px 10px",
            fontSize: "12px",
            fontWeight: 800,
            cursor: "pointer",
            height: "fit-content",
          }}
        >
          All Handoff ({counts.all})
        </button>
      </div>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 180px), 1fr))",
          gap: "8px",
        }}
      >
        {cards.map((card) => (
          <button
            key={card.key}
            type="button"
            onClick={() => onSelect(card.key)}
            style={{
              textAlign: "left",
              border:
                selected === card.key
                  ? "1px solid var(--app-primary-action-border)"
                  : "1px solid var(--app-surface-border)",
              borderRadius: "8px",
              background: "var(--app-surface-bg)",
              padding: "10px 12px",
              cursor: "pointer",
              display: "grid",
              gap: "6px",
            }}
          >
            <span style={{ color: "var(--app-text-subtle)", fontSize: "11px", fontWeight: 800, textTransform: "uppercase" }}>
              {card.label}
            </span>
            <strong style={{ color: "var(--app-text-strong)", fontSize: "20px", lineHeight: 1 }}>{card.value}</strong>
            <span style={{ color: "var(--app-text-muted)", fontSize: "12px", lineHeight: 1.45 }}>{card.detail}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

function ManualSessionsStateCard({
  title,
  description,
  primaryHref,
  primaryLabel,
  actionLabel,
  onAction,
}: {
  title: string;
  description: string;
  primaryHref?: string;
  primaryLabel?: string;
  actionLabel?: string;
  onAction?: () => void;
}) {
  return (
    <div
      style={{
        border: "1px solid var(--app-surface-border)",
        borderRadius: "8px",
        background: "var(--app-surface-muted-bg)",
        color: "var(--app-text-muted)",
        padding: "16px",
        display: "grid",
        gap: "10px",
        fontSize: "13px",
        lineHeight: 1.6,
      }}
    >
      <strong style={{ color: "var(--app-text-strong)", fontSize: "15px" }}>{title}</strong>
      <p style={{ margin: 0 }}>{description}</p>
      {primaryHref && primaryLabel ? (
        <Link
          href={primaryHref}
          style={{
            width: "fit-content",
            border: "1px solid var(--app-primary-action-border)",
            borderRadius: "8px",
            background: "var(--app-primary-action-bg)",
            color: "var(--app-primary-action-fg)",
            padding: "8px 10px",
            fontSize: "13px",
            fontWeight: 700,
            textDecoration: "none",
          }}
        >
          {primaryLabel}
        </Link>
      ) : null}
      {actionLabel && onAction ? (
        <button
          type="button"
          onClick={onAction}
          style={{
            width: "fit-content",
            border: "1px solid var(--app-secondary-action-border)",
            borderRadius: "8px",
            background: "var(--app-secondary-action-bg)",
            color: "var(--app-secondary-action-fg)",
            padding: "8px 10px",
            fontSize: "13px",
            fontWeight: 700,
            cursor: "pointer",
          }}
        >
          {actionLabel}
        </button>
      ) : null}
    </div>
  );
}

function AnalysisCard({
  title,
  content,
}: {
  title: string;
  content?: AnalysisValue;
}) {
  return (
    <div
      style={{
        border: "1px solid var(--app-surface-border)",
        borderRadius: "12px",
        padding: "20px",
        background: "var(--app-surface-bg)",
      }}
    >
      <div
        style={{
          fontSize: "13px",
          color: "var(--app-text-subtle)",
          marginBottom: "8px",
          textTransform: "uppercase",
          letterSpacing: 0,
        }}
      >
        {title}
      </div>

      <div style={{ lineHeight: "1.7" }}>
        {renderAnalysisContent(content)}
      </div>
    </div>
  );
}

