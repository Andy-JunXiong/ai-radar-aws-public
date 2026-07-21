"use client";

import Image from "next/image";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties, type ReactNode } from "react";
import { ArrowLeft, Database, FileText, FileUp, Radar, RefreshCcw, ShieldCheck, Sparkles } from "lucide-react";

import AppContainer from "@/components/AppContainer";
import VerificationGateNote from "@/components/VerificationGateNote";
import { API_BASE } from "@/lib/api";
import { adminFetch } from "@/lib/adminAuth";

const SIGNALS_CACHE_KEY = "ai-radar-signals-cache-v9";
const PDF_PREVIEW_PENDING_MESSAGE =
  "[PDF uploaded successfully. Text preview will be generated during analysis.]";

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
  article_fetch_error?: string;
};

type ClaimSourceSpan = {
  evidence_id?: string;
  source_id?: string;
  source_field?: string;
  char_start?: number;
  char_end?: number;
  match_type?: string;
  matched_token_count?: number;
  claim_token_coverage?: number;
};

type ClaimCheckItem = {
  claim_id?: string;
  claim_text?: string;
  claim_type?: string;
  source_field?: string;
  support_level?: string;
  evidence_refs?: string[];
  inference_distance?: string;
  risk_level?: string;
  verification_notes?: string[];
  recommended_rewrite?: string | null;
  source_span?: ClaimSourceSpan | null;
};

type VerificationMetadata = {
  verification_status?: string;
  confidence_score?: number;
  confidence_label?: string;
  uncertainty_boundaries?: string[];
  limitations?: string[];
  allowed_downstream_actions?: string[];
  blocked_downstream_actions?: string[];
  downgrade_reason?: string | null;
  claim_support_summary?: Record<string, number>;
  claim_results?: ClaimCheckItem[];
  evidence_quality?: {
    level?: string;
    score?: number;
    summary_provenance?: string;
    reason_codes?: string[];
  };
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
  workspace_file_name?: string;
  workspace_saved_at?: string;
  provider_used?: string | null;
  model_used?: string | null;
  generation_mode?: string | null;
  requested_provider?: string | null;
  fallback_used?: boolean;
  verification?: VerificationMetadata | null;
  policy_metadata?: {
    verification?: VerificationMetadata;
  } | null;
  evidence_pack?: Record<string, unknown>;
  analysis?: ManualAnalysis | null;
  files?: UploadedManualFile[];
};

type SessionDetailResponse = {
  message?: string;
  session?: ManualSessionDetail | null;
};

type ManualFilePreviewResponse = {
  preview_text?: string;
  preview_available?: boolean;
  message?: string;
};

type AnalyzeSessionResponse = {
  message?: string;
  analysis?: ManualAnalysis | null;
  provider_used?: string | null;
  fallback_used?: boolean;
};

type GenerateInsightResponse = {
  message?: string;
  status?: string;
  summary?: string;
  why_it_matters?: string;
  relevance_to_projects?: string | Record<string, unknown>;
  relevance_to_career?: string;
  synthesized_insight?: string;
  provider_used?: string | null;
  model_used?: string | null;
  generation_mode?: string | null;
  requested_provider?: string | null;
  verification?: VerificationMetadata | null;
  policy_metadata?: {
    verification?: VerificationMetadata;
  } | null;
  evidence_pack?: Record<string, unknown>;
};

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

function needsPdfPreviewHydration(file: UploadedManualFile): boolean {
  return (
    file.file_kind === "pdf" &&
    Boolean(file.stored_filename) &&
    (!file.preview_text || file.preview_text.trim() === PDF_PREVIEW_PENDING_MESSAGE)
  );
}

function invalidateSignalsListCache() {
  if (typeof window === "undefined") return;

  try {
    sessionStorage.removeItem(SIGNALS_CACHE_KEY);
  } catch {
    // ignore cache invalidation errors
  }
}

function formatDateTime(value?: string) {
  if (!value) return "Unknown time";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

function stripUncertainText(value: unknown): unknown {
  if (typeof value === "string") {
    return value.replace(/^\s*uncertain:\s*/i, "");
  }
  if (Array.isArray(value)) {
    return value.map((item) => stripUncertainText(item));
  }
  if (typeof value === "object" && value !== null) {
    const next: Record<string, unknown> = {};
    for (const [key, nestedValue] of Object.entries(value)) {
      next[key] = stripUncertainText(nestedValue);
    }
    return next;
  }
  return value;
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
  value?: ManualSessionDetail["source_stated_confidence"]
): string {
  if (!value) return "";
  if (typeof value === "string") return value.trim();
  return String(value.raw_text || value.normalized_label || "").trim();
}

function numberFromUnknown(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function findEvidenceContent(evidencePack: Record<string, unknown> | undefined, sourceSpan?: ClaimSourceSpan | null): string {
  if (!evidencePack || !sourceSpan?.evidence_id) return "";
  const evidenceItems = evidencePack.evidence_items;
  if (!Array.isArray(evidenceItems)) return "";

  const matchedItem = evidenceItems.find((item) => {
    if (!item || typeof item !== "object") return false;
    return String((item as Record<string, unknown>).evidence_id || "") === sourceSpan.evidence_id;
  });
  if (!matchedItem || typeof matchedItem !== "object") return "";

  const content = (matchedItem as Record<string, unknown>).content;
  return typeof content === "string" ? content : "";
}

function getClaimSourceExcerpt(
  claim: ClaimCheckItem,
  evidencePack: Record<string, unknown> | undefined
): { excerpt: string; location: string; matchDetails: string } | null {
  const sourceSpan = claim.source_span;
  if (!sourceSpan) return null;

  const content = findEvidenceContent(evidencePack, sourceSpan);
  const start = numberFromUnknown(sourceSpan.char_start);
  const end = numberFromUnknown(sourceSpan.char_end);
  if (!content || start === null || end === null || end <= start) return null;

  const safeStart = Math.max(0, Math.min(start, content.length));
  const safeEnd = Math.max(safeStart, Math.min(end, content.length));
  const excerpt = content.slice(safeStart, safeEnd).trim();
  if (!excerpt) return null;

  const locationParts = [
    sourceSpan.evidence_id ? `Evidence ${sourceSpan.evidence_id}` : "",
    sourceSpan.source_field ? formatCompactLabel(sourceSpan.source_field) : "",
    `chars ${safeStart}-${safeEnd}`,
  ].filter(Boolean);
  const detailParts = [
    sourceSpan.match_type ? formatCompactLabel(sourceSpan.match_type) : "",
    typeof sourceSpan.matched_token_count === "number" ? `${sourceSpan.matched_token_count} matched tokens` : "",
    typeof sourceSpan.claim_token_coverage === "number"
      ? `${Math.round(sourceSpan.claim_token_coverage * 100)}% claim coverage`
      : "",
  ].filter(Boolean);

  return {
    excerpt,
    location: locationParts.join(" · "),
    matchDetails: detailParts.join(" · "),
  };
}

function formatClaimSupportSummary(summary?: Record<string, number>): string {
  const entries = Object.entries(summary || {}).filter(([, count]) => count > 0);
  return entries
    .map(([supportLevel, count]) => `${formatCompactLabel(supportLevel)}: ${count}`)
    .join(" | ");
}

function formatSummaryProvenance(value?: string): string {
  switch (String(value || "").toLowerCase()) {
    case "manual_user_written":
      return "Manual user written";
    case "manual_upload_summary":
      return "Manual upload summary";
    case "llm_generated":
      return "LLM generated";
    case "unknown":
    case "":
      return "Unknown";
    default:
      return formatCompactLabel(value);
  }
}

function formatEvidenceReason(value?: string): string {
  switch (String(value || "").toLowerCase()) {
    case "manual_user_written":
      return "The summary comes from user-provided manual context.";
    case "source_url_present":
      return "The source has a traceable URL.";
    case "missing_summary":
      return "The source summary is missing.";
    default:
      return formatCompactLabel(value);
  }
}

function getClaimSupportRank(value?: string): number {
  switch (String(value || "").toLowerCase()) {
    case "contradicted":
      return 0;
    case "unsupported":
      return 1;
    case "inferred":
      return 2;
    case "partially_supported":
      return 3;
    case "directly_supported":
      return 4;
    default:
      return 5;
  }
}

function getReviewPriority({
  verificationStatus,
  blockedActions,
  supportSummary,
}: {
  verificationStatus?: string;
  blockedActions: string[];
  supportSummary: Record<string, number>;
}): { label: string; color: string; background: string; border: string } {
  const status = String(verificationStatus || "").toLowerCase();
  const unsupported = (supportSummary.unsupported || 0) + (supportSummary.contradicted || 0);
  const inferred = supportSummary.inferred || 0;
  const blocksAction =
    blockedActions.includes("low_risk_action_candidate") ||
    blockedActions.includes("strong_recommendation");

  if (status === "unsupported" || status === "contradicted" || unsupported > 0) {
    return { label: "Do Not Act", color: "var(--app-danger-fg)", background: "var(--app-danger-bg)", border: "1px solid var(--app-danger-border)" };
  }
  if (status === "not_verifiable" || status === "weakly_supported" || inferred > 0) {
    return { label: "Review Required", color: "var(--app-warning-fg)", background: "var(--app-warning-bg)", border: "1px solid var(--app-warning-border)" };
  }
  if (status === "partially_verified" || blocksAction) {
    return { label: "Review Before Action", color: "var(--app-warning-fg)", background: "var(--app-warning-bg)", border: "1px solid var(--app-warning-border)" };
  }
  if (status === "verified") {
    return { label: "Ready For Low-Risk Review", color: "var(--app-success-fg)", background: "var(--app-success-bg)", border: "1px solid var(--app-success-border)" };
  }
  return { label: "Review Unknown", color: "var(--app-text-muted)", background: "var(--app-surface-muted-bg)", border: "1px solid var(--app-surface-border)" };
}

function verificationColor(status?: string): { background: string; border: string; color: string } {
  switch (String(status || "").toLowerCase()) {
    case "unsupported":
    case "contradicted":
      return { background: "var(--app-danger-bg)", border: "1px solid var(--app-danger-border)", color: "var(--app-danger-fg)" };
    case "inferred":
    case "weakly_supported":
    case "not_verifiable":
      return { background: "var(--app-warning-bg)", border: "1px solid var(--app-warning-border)", color: "var(--app-warning-fg)" };
    case "partially_supported":
    case "partially_verified":
      return { background: "var(--app-warning-bg)", border: "1px solid var(--app-warning-border)", color: "var(--app-warning-fg)" };
    case "directly_supported":
    case "verified":
      return { background: "var(--app-success-bg)", border: "1px solid var(--app-success-border)", color: "var(--app-success-fg)" };
    default:
      return { background: "var(--app-surface-muted-bg)", border: "1px solid var(--app-surface-border)", color: "var(--app-text-muted)" };
  }
}

function isProjectRelevanceClaim(claim: ClaimCheckItem): boolean {
  const fields = [claim.source_field, claim.claim_type].map((value) => String(value || "").trim().toLowerCase());
  return fields.some((value) => value === "relevance_to_projects" || value === "relevance to projects");
}

function getClaimDisplayStyle(claim: ClaimCheckItem): { background: string; border: string; color: string } {
  if (isProjectRelevanceClaim(claim)) {
    return { background: "var(--app-info-bg)", border: "1px solid var(--app-info-border)", color: "var(--app-info-fg)" };
  }
  return verificationColor(claim.support_level);
}

function getClaimDisplayTypeLabel(claim: ClaimCheckItem): string {
  return isProjectRelevanceClaim(claim) ? "Project relevance judgment" : formatCompactLabel(claim.claim_type);
}

function getClaimDisplaySupportLabel(claim: ClaimCheckItem): string {
  return isProjectRelevanceClaim(claim) ? "Internal judgment" : formatCompactLabel(claim.support_level);
}

export default function ManualSessionDetailClient() {
  const searchParams = useSearchParams();
  const sessionId = (searchParams.get("id") || "").trim();

  const [session, setSession] = useState<ManualSessionDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [insightGenerating, setInsightGenerating] = useState(false);
  const [insightGeneratingModel, setInsightGeneratingModel] = useState<"chatgpt" | "claude" | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [manualFileUrls, setManualFileUrls] = useState<Record<string, string>>({});
  const [manualFilePreviewOverrides, setManualFilePreviewOverrides] = useState<Record<string, string>>({});
  const [expandedTextPreviewIds, setExpandedTextPreviewIds] = useState<Record<string, boolean>>({});
  const [lightboxIndex, setLightboxIndex] = useState<number | null>(null);
  const [relatedReflections, setRelatedReflections] = useState<RelatedReflection[]>([]);
  const [relatedReflectionTopics, setRelatedReflectionTopics] = useState<string[]>([]);
  const [relatedReflectionsLoading, setRelatedReflectionsLoading] = useState(false);

  const manualFileUrlsRef = useRef<Record<string, string>>({});
  const analysisSectionRef = useRef<HTMLDivElement | null>(null);

  const uploadedFiles = useMemo(() => (Array.isArray(session?.files) ? session.files : []), [session]);
  const sessionAnalysis = session?.analysis || null;
  const availableInSignals = Boolean(sessionAnalysis);
  const hasGenerationMetadata = Boolean(
    session?.provider_used ||
      session?.model_used ||
      session?.generation_mode ||
      session?.requested_provider
  );
  const providerLabel = session?.provider_used || "Not generated";
  const modelLabel = session?.model_used || "Model not recorded";
  const generationModeLabel = formatCompactLabel(session?.generation_mode || "unknown");
  const requestedProviderLabel = session?.requested_provider
    ? formatCompactLabel(session.requested_provider)
    : "";
  const latestGenerationRouteText = hasGenerationMetadata
    ? `Latest generation route: ${providerLabel}${session?.model_used ? ` / ${session.model_used}` : ""} / ${generationModeLabel}${requestedProviderLabel ? ` / Requested ${requestedProviderLabel}` : ""}.`
    : "Generation route metadata is not saved yet. Generate Insight or Generate with Claude to attach provider and model details.";
  const syncStatusLabel = availableInSignals
    ? "Synced to Signals"
    : "Not yet in Signals";
  const workspaceRecordFileName = session?.workspace_file_name || "";
  const hasWorkspaceRecord = Boolean(session?.workspace_saved && workspaceRecordFileName);
  const workspaceRecordHref = hasWorkspaceRecord
    ? `/workspace/detail?file_name=${encodeURIComponent(workspaceRecordFileName)}`
    : "";
  const workspaceLinkMissing = Boolean(session?.workspace_saved && !workspaceRecordFileName);
  const workspaceStatusLabel = hasWorkspaceRecord
    ? "Saved to Workspace"
    : session?.workspace_saved
      ? "Repair Workspace Link"
      : "Not completed";
  const handoffStage = hasWorkspaceRecord
    ? {
        label: "Workspace Done",
        body: "This manual-derived intelligence already has a durable Workspace record.",
        tone: "done" as const,
      }
    : availableInSignals
      ? {
          label: "Ready For Signal Review",
          body: "Structured insight exists. Review Signal Detail before Workspace completion or Project Takeaway routing.",
          tone: "ready" as const,
        }
      : uploadedFiles.length > 0
        ? {
            label: "Needs Insight",
            body: "Uploaded material exists, but structured insight has not been generated yet.",
            tone: "warning" as const,
          }
        : {
            label: "Pending Analysis",
            body: "This session needs upload/session detail review before it can enter the signal workflow.",
            tone: "pending" as const,
          };
  const manualFlowSteps = [
    {
      label: "Uploaded",
      value: uploadedFiles.length > 0 ? `${uploadedFiles.length} file${uploadedFiles.length === 1 ? "" : "s"}` : "No files",
      tone: uploadedFiles.length > 0 ? "done" : "pending",
    },
    {
      label: "Insight",
      value: availableInSignals ? "Structured insight ready" : "Needs analysis",
      tone: availableInSignals ? "done" : "pending",
    },
    {
      label: "Signals",
      value: syncStatusLabel,
      tone: availableInSignals ? "done" : "pending",
    },
    {
      label: "Workspace",
      value: workspaceStatusLabel,
      tone: hasWorkspaceRecord ? "done" : "pending",
    },
  ];
  const manualCompletionAuditItems = [
    {
      label: "Upload",
      value: uploadedFiles.length > 0 ? "Ready" : "Missing files",
    },
    {
      label: "Insight",
      value: availableInSignals ? "Generated" : "Needs generation",
    },
    {
      label: "Signal Detail",
      value: availableInSignals ? "Review Evidence Note" : "Unavailable",
    },
    {
      label: "Workspace",
      value: hasWorkspaceRecord ? "Saved" : workspaceLinkMissing ? "Saved, link missing" : "Not saved",
    },
    {
      label: "Durable Link",
      value: hasWorkspaceRecord ? "Openable" : workspaceLinkMissing ? "Needs repair" : "Not ready",
    },
  ];
  const manualIntentSummary = [
    session?.upload_reason ? `Reason: ${session.upload_reason}` : null,
    session?.intended_use ? `Use: ${session.intended_use}` : null,
    session?.cognitive_layer ? `Layer: ${formatCompactLabel(session.cognitive_layer)}` : null,
  ].filter((item): item is string => Boolean(item));
  const sourceStatedConfidenceText = getSourceStatedConfidenceText(
    session?.source_stated_confidence
  );
  const sourceLimitsSummary = session?.source_stated_limits_not_applicable
    ? "Not applicable"
    : session?.source_stated_limits || "";
  const hasSourceLimitsMetadata =
    Boolean(sourceLimitsSummary) ||
    Boolean(sourceStatedConfidenceText) ||
    Boolean(session?.source_stated_limits_status);
  const manualCompletionGaps = [
    uploadedFiles.length === 0 ? "Add source files or text before trusting the session." : null,
    !availableInSignals ? "Generate structured insight so the manual session appears as a Signal Detail object." : null,
    availableInSignals && !hasWorkspaceRecord
      ? "Open Signal Detail, review the Evidence Note, then complete the manual-derived signal into Workspace when it should become durable."
      : null,
    session?.workspace_saved && !workspaceRecordFileName
      ? "Workspace saved flag exists, but no workspace file name is recorded."
      : null,
  ].filter((gap): gap is string => Boolean(gap));
  const manualCompletionReady = uploadedFiles.length > 0 && availableInSignals && hasWorkspaceRecord;
  const manualCompletionRouteLabel = hasWorkspaceRecord
    ? "Workspace record is durable"
    : workspaceLinkMissing
      ? "Workspace completion is flagged, but the durable record link is missing"
    : availableInSignals
      ? "Signal Detail review is the next required route"
      : uploadedFiles.length > 0
        ? "Insight generation is the next required route"
        : "Source capture is the next required route";
  const nextActionState = hasWorkspaceRecord
    ? {
        label: "Review Workspace Record",
        body: "This manual session has already been completed into Workspace. Use the Workspace record as the durable review artifact.",
        tone: "done" as const,
      }
    : workspaceLinkMissing
      ? {
          label: "Repair Workspace Link",
          body: "Workspace completion is marked, but no Workspace file name is recorded. Treat this as incomplete until the durable record link is restored.",
          tone: "pending" as const,
        }
    : availableInSignals
      ? {
          label: "Complete From Signal Detail",
          body: "The structured insight is ready. Open the manual-derived signal, review the Evidence Note and completion note, then complete it into Workspace when it should become durable.",
          tone: "ready" as const,
        }
      : {
          label: "Generate Insight",
          body: "This upload still needs structured analysis before it can move into Signals, Project Takeaway review, or Workspace.",
          tone: "pending" as const,
        };
  const manualInsightMissing =
    !sessionAnalysis ||
    !(
      String(sessionAnalysis.why_it_matters || "").trim() ||
      String(sessionAnalysis.relevance_to_projects || "").trim() ||
      String(sessionAnalysis.relevance_to_career || "").trim() ||
      String(sessionAnalysis.synthesized_insight || "").trim()
    );

  const imageFiles = useMemo(
    () => uploadedFiles.filter((file) => file.file_kind === "image"),
    [uploadedFiles]
  );
  const textLikeFiles = useMemo(
    () => uploadedFiles.filter((file) => file.file_kind === "text" || file.file_kind === "pdf"),
    [uploadedFiles]
  );
  const filesNeedingPreviewHydration = useMemo(
    () => textLikeFiles.filter((file) => needsPdfPreviewHydration(file)),
    [textLikeFiles]
  );
  const sessionType = useMemo(() => {
    if (uploadedFiles.length === 0) return "";
    const kinds = Array.from(new Set(uploadedFiles.map((file) => file.file_kind)));
    if (kinds.length === 1 && kinds[0] === "image") return "image";
    if (kinds.every((kind) => kind === "text" || kind === "pdf")) return "text";
    return "mixed";
  }, [uploadedFiles]);
  const primaryActionGuidance = manualInsightMissing
    ? `Use Generate Insight to fill the missing structured insight sections for this ${sessionType === "image"
        ? "image"
        : sessionType === "text"
          ? "text / PDF"
          : sessionType === "mixed"
            ? "mixed"
            : "manual"} session.`
    : "Use Generate Insight or Generate with Claude only when you want to refresh the structured insight.";
  const analyzeSessionGuidance = availableInSignals
    ? "Legacy Analyze Session is hidden after this session enters Signals. Refresh through Generate Insight so Manual Detail and Signal Detail stay aligned."
    : "Legacy Analyze Session only creates the first saved analysis record. Prefer Generate Insight unless you specifically need that older initialization path.";
  const currentLightboxFile =
    lightboxIndex !== null && imageFiles[lightboxIndex] ? imageFiles[lightboxIndex] : null;

  const focusAnalysisSection = useCallback(() => {
    window.requestAnimationFrame(() => {
      analysisSectionRef.current?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    });
  }, []);

  const getManualFileUrl = useCallback(
    (storedFilename?: string) => (storedFilename ? manualFileUrls[storedFilename] || "" : ""),
    [manualFileUrls]
  );

  const getPreviewText = useCallback(
    (file: UploadedManualFile) => {
      const previewText = manualFilePreviewOverrides[file.stored_filename] || file.preview_text || "";
      return previewText.trim() === PDF_PREVIEW_PENDING_MESSAGE ? "" : previewText;
    },
    [manualFilePreviewOverrides]
  );

  const toggleTextPreview = (storedFilename: string) => {
    setExpandedTextPreviewIds((current) => ({
      ...current,
      [storedFilename]: !current[storedFilename],
    }));
  };

  const fetchSessionDetail = useCallback(async () => {
    if (!sessionId) {
      throw new Error("Missing session id.");
    }

    const response = await adminFetch(`${API_BASE}/manual/session/${encodeURIComponent(sessionId)}`, {
      cache: "no-store",
    });
    const data = (await response.json().catch(() => null)) as SessionDetailResponse | null;

    if (!response.ok || !data?.session) {
      if (response.status === 401 || response.status === 403) {
        throw new Error("Admin login is required before loading manual session detail.");
      }
      throw new Error(data?.message || "Failed to load manual session.");
    }

    return data.session;
  }, [sessionId]);

  useEffect(() => {
    let cancelled = false;

    async function loadSession() {
      if (!sessionId) {
        setError("Missing manual session id.");
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        setError("");
        const nextSession = await fetchSessionDetail();
        if (cancelled) return;
        setSession(nextSession);
        setMessage(
          nextSession.analysis
            ? "Manual session loaded with saved analysis."
            : "Manual session loaded. No saved analysis yet."
        );
      } catch (loadError) {
        if (!cancelled) {
          setError(getErrorMessage(loadError, "Failed to load manual session."));
          setSession(null);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void loadSession();

    return () => {
      cancelled = true;
    };
  }, [fetchSessionDetail, sessionId]);

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
      for (const file of uploadedFiles) {
        const storedFilename = file.stored_filename;
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
  }, [uploadedFiles]);

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
          if (cancelled || !previewText || previewText.trim() === PDF_PREVIEW_PENDING_MESSAGE) continue;

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
    let cancelled = false;
    const controller = new AbortController();

    async function loadRelatedReflections() {
      if (!sessionId || !sessionAnalysis) {
        setRelatedReflections([]);
        setRelatedReflectionTopics([]);
        return;
      }

      setRelatedReflectionsLoading(true);
      try {
        const response = await fetch(
          `${API_BASE}/signals/manual_${encodeURIComponent(sessionId)}/related-reflections?limit=3`,
          {
            cache: "no-store",
            signal: controller.signal,
          }
        );

        if (!response.ok) {
          throw new Error("Failed to load related reflections.");
        }

        const data = (await response.json()) as RelatedReflectionsResponse;
        if (cancelled) return;
        setRelatedReflections(Array.isArray(data.reflections) ? data.reflections : []);
        setRelatedReflectionTopics(Array.isArray(data.signal_topics) ? data.signal_topics : []);
      } catch (loadError) {
        if (loadError instanceof Error && loadError.name === "AbortError") {
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
  }, [sessionAnalysis, sessionId]);

  useEffect(() => {
    if (!sessionId) return;

    let cancelled = false;

    const refreshCurrentSession = async () => {
      try {
        const refreshedSession = await fetchSessionDetail();
        if (cancelled) return;
        setSession(refreshedSession);
      } catch {
        return;
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
  }, [fetchSessionDetail, sessionId]);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (lightboxIndex === null) return;
      if (event.key === "Escape") setLightboxIndex(null);
      if (event.key === "ArrowLeft") {
        setLightboxIndex((current) => {
          if (current === null) return 0;
          return current === 0 ? imageFiles.length - 1 : current - 1;
        });
      }
      if (event.key === "ArrowRight") {
        setLightboxIndex((current) => {
          if (current === null) return 0;
          return current === imageFiles.length - 1 ? 0 : current + 1;
        });
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [imageFiles.length, lightboxIndex]);

  const handleAnalyzeSession = async () => {
    if (!sessionId || uploadedFiles.length === 0) {
      setError("No uploaded files available for analysis.");
      return;
    }

    if (sessionType === "mixed") {
      setError(
        "Mixed session analysis is not supported yet. Please upload either all images or all text/PDF files in one session."
      );
      return;
    }

    try {
      setAnalysisLoading(true);
      setError("");
      setMessage("Analyzing session... this may take a little while.");

      const response = await adminFetch(`${API_BASE}/manual/analyze-session`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          session_id: sessionId,
          files: uploadedFiles.map((file) => ({
            stored_filename: file.stored_filename,
            original_filename: file.original_filename,
            file_kind: file.file_kind,
          })),
        }),
      });

      const data = (await response.json().catch(() => null)) as AnalyzeSessionResponse | null;
      if (!response.ok || !data?.analysis) {
        throw new Error(data?.message || "Session analysis failed.");
      }

      const refreshedSession = await fetchSessionDetail();
      setSession(refreshedSession);
      setMessage(data.message || "Session analysis generated successfully.");
      focusAnalysisSection();
    } catch (analyzeError) {
      const nextError = getErrorMessage(analyzeError, "Session analysis failed.");
      if (
        nextError.includes("overloaded_error") ||
        nextError.includes("Overloaded") ||
        nextError.includes("529")
      ) {
        setError("Analysis provider is temporarily overloaded. Please wait a moment and try again.");
      } else {
        setError(nextError);
      }
    } finally {
      setAnalysisLoading(false);
    }
  };

  const handleGenerateInsight = async (selectedModel: "chatgpt" | "claude") => {
    if (!sessionId || insightGenerating) return;

    try {
      setInsightGenerating(true);
      setInsightGeneratingModel(selectedModel);
      setError("");
      setMessage("");

      const response = await adminFetch(`${API_BASE}/signals/generate-insight`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          signal_id: `manual_${sessionId}`,
          selected_model: selectedModel,
        }),
      });

      const data = (await response.json().catch(() => null)) as GenerateInsightResponse | null;
      if (!response.ok) {
        const detail =
          (data as { detail?: string } | null)?.detail ||
          data?.message ||
          "Failed to generate insight.";
        throw new Error(detail);
      }

      const refreshedSession = await fetchSessionDetail();
      setSession(refreshedSession);
      invalidateSignalsListCache();
      setMessage(
        data?.generation_mode === "fallback"
          ? `Insight generation fell back from ${data?.requested_provider || selectedModel}.`
          : `Insight generated successfully via ${data?.provider_used || selectedModel}${data?.model_used ? ` (${data.model_used})` : ""}.`
      );
      focusAnalysisSection();
    } catch (generationError) {
      setError(getErrorMessage(generationError, "Failed to generate insight."));
    } finally {
      setInsightGenerating(false);
      setInsightGeneratingModel(null);
    }
  };

  if (loading) {
    return (
      <AppContainer>
        <div style={{ padding: "28px 0", color: "var(--app-text-subtle)", fontSize: "15px" }}>
          Loading manual session detail...
        </div>
      </AppContainer>
    );
  }

  if (!session) {
    return (
      <AppContainer>
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: "16px",
            padding: "28px 0",
          }}
        >
          <Link href="/manual" style={{ color: "#1d4ed8", textDecoration: "none", fontWeight: 600 }}>
            Back to Manual Upload
          </Link>
          <div style={{ fontSize: "15px", color: "#b91c1c" }}>
            {error || "Manual session not found."}
          </div>
        </div>
      </AppContainer>
    );
  }

  return (
    <>
      <AppContainer style={manualDetailShellStyle}>
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: "20px",
            paddingBottom: "40px",
          }}
        >
          <section style={manualDetailHeroStyle}>
            <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
              <Link href="/manual" style={primaryNavLinkStyle}>
                <ArrowLeft size={15} strokeWidth={2.4} />
                Manual Intake
              </Link>
              <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
                <span style={topicBadgeStyle}>
                  <FileText size={14} strokeWidth={2.4} />
                  Manual Session
                </span>
                <span
                  style={{
                    ...statusBadgeStyle,
                    background: session.analysis_status === "completed" ? "var(--app-warning-bg)" : "var(--app-surface-muted-bg)",
                    color: session.analysis_status === "completed" ? "var(--app-warning-fg)" : "var(--app-text-muted)",
                    border:
                      session.analysis_status === "completed"
                        ? "1px solid var(--app-warning-border)"
                        : "1px solid var(--app-surface-border)",
                  }}
                >
                  {session.analysis_status === "completed" ? "Insight available" : "Needs analysis"}
                </span>
              </div>
              <div style={detailTitleStyle}>
                {session.title || "Untitled Manual Session"}
              </div>
              <div
                style={{
                  display: "flex",
                  gap: "16px",
                  flexWrap: "wrap",
                  fontSize: "14px",
                  color: "var(--app-text-muted)",
                }}
              >
                <span>Created: {formatDateTime(session.created_at)}</span>
                <span>Updated: {formatDateTime(session.updated_at)}</span>
                <span>Files: {uploadedFiles.length}</span>
              </div>

              {(session.upload_reason || session.intended_use || session.cognitive_layer) && (
                <div
                  style={{
                    display: "flex",
                    gap: "8px",
                    flexWrap: "wrap",
                    fontSize: "13px",
                    color: "var(--app-text-muted)",
                  }}
                >
                  {session.upload_reason ? <span style={smallChipStyle}>Reason: {session.upload_reason}</span> : null}
                  {session.intended_use ? <span style={smallChipStyle}>Use: {session.intended_use}</span> : null}
                  <span style={smallChipStyle}>Layer: {formatCompactLabel(session.cognitive_layer || "unclassified")}</span>
                </div>
              )}

              {hasSourceLimitsMetadata ? (
                <div
                  style={{
                    display: "flex",
                    gap: "8px",
                    flexWrap: "wrap",
                    fontSize: "13px",
                    color: "var(--app-text-muted)",
                  }}
                >
                  <span style={smallChipStyle}>
                    Source limits: {sourceLimitsSummary || "Captured status only"}
                  </span>
                  {sourceStatedConfidenceText ? (
                    <span style={smallChipStyle}>
                      Source confidence: {sourceStatedConfidenceText}
                    </span>
                  ) : null}
                </div>
              ) : null}

              <div
                style={{
                  marginTop: "4px",
                  fontSize: "14px",
                  color: "var(--app-text-muted)",
                  lineHeight: "1.7",
                }}
              >
                {availableInSignals
                  ? "Analyzed = insight is ready for this manual session and can now be reviewed, regenerated, or opened in Signals."
                  : "Pending = this manual session still needs analysis before its insight sections are ready."}
              </div>

              <div style={manualDetailStatusGridStyle}>
                <div style={sessionStatusItemStyle}>
                  <span style={sessionStatusLabelStyle}>
                    <Radar size={13} strokeWidth={2.4} />
                    Signals Sync
                  </span>
                  <strong>{syncStatusLabel}</strong>
                </div>
                <div style={sessionStatusItemStyle}>
                  <span style={sessionStatusLabelStyle}>
                    <Sparkles size={13} strokeWidth={2.4} />
                    Provider
                  </span>
                  <strong>{providerLabel}</strong>
                </div>
                <div style={sessionStatusItemStyle}>
                  <span style={sessionStatusLabelStyle}>
                    <ShieldCheck size={13} strokeWidth={2.4} />
                    Model
                  </span>
                  <strong>{modelLabel}</strong>
                </div>
                <div style={sessionStatusItemStyle}>
                  <span style={sessionStatusLabelStyle}>
                    <RefreshCcw size={13} strokeWidth={2.4} />
                    Generation
                  </span>
                  <strong>
                    {generationModeLabel}
                    {requestedProviderLabel ? ` / Requested ${requestedProviderLabel}` : ""}
                  </strong>
                </div>
              </div>

              {session?.generation_mode === "fallback" ? (
                <div
                  style={{
                    marginTop: "2px",
                    padding: "10px 12px",
                    borderRadius: "8px",
                    border: "1px solid var(--app-warning-border)",
                    background: "var(--app-warning-bg)",
                    color: "var(--app-warning-fg)",
                    fontSize: "13px",
                    lineHeight: 1.6,
                  }}
                >
                  This session currently shows fallback output. Regenerate with ChatGPT or Claude when you want a stronger model pass.
                </div>
              ) : hasGenerationMetadata ? (
                <div
                  style={{
                    marginTop: "2px",
                    padding: "10px 12px",
                    borderRadius: "8px",
                    border: "1px solid var(--app-success-border)",
                    background: "var(--app-success-bg)",
                    color: "var(--app-success-fg)",
                    fontSize: "13px",
                    lineHeight: 1.6,
                  }}
                >
                  Latest generation metadata is saved on this manual session and will be used when opening it in Signals.
                </div>
              ) : null}

              <div style={manualHandoffDashboardStyle}>
                <div
                  style={{
                    ...manualNextActionPanelStyle,
                    ...(nextActionState.tone === "done" ? manualNextActionDoneStyle : {}),
                  }}
                >
                  <span style={manualFlowLabelStyle}>Next Action</span>
                  <strong>{nextActionState.label}</strong>
                  <span>{nextActionState.body}</span>
                  <div style={manualNextActionLinksStyle}>
                    {hasWorkspaceRecord ? (
                      <Link href={workspaceRecordHref} style={manualFlowLinkStyle}>
                        Open Workspace Record
                      </Link>
                    ) : workspaceLinkMissing ? (
                      <Link
                        href={`/signals/detail?id=${encodeURIComponent(`manual_${session.session_id}`)}`}
                        style={manualNextActionPrimaryLinkStyle}
                      >
                        Repair From Signal Detail
                      </Link>
                    ) : availableInSignals ? (
                      <Link
                        href={`/signals/detail?id=${encodeURIComponent(`manual_${session.session_id}`)}`}
                        style={manualNextActionPrimaryLinkStyle}
                      >
                        Open in Signals
                      </Link>
                    ) : null}
                  </div>
                </div>

                <div
                  style={{
                    ...manualHandoffPanelStyle,
                    ...(handoffStage.tone === "done"
                      ? manualHandoffDoneStyle
                      : handoffStage.tone === "ready"
                        ? manualHandoffReadyStyle
                        : handoffStage.tone === "warning"
                          ? manualHandoffWarningStyle
                          : {}),
                  }}
                >
                  <div style={manualHandoffHeaderStyle}>
                    <div>
                      <span style={manualFlowLabelStyle}>Handoff Readiness</span>
                      <strong>{handoffStage.label}</strong>
                    </div>
                    <span style={manualHandoffChipStyle}>{syncStatusLabel}</span>
                  </div>
                  <span>{handoffStage.body}</span>
                  <div style={manualHandoffGridStyle}>
                    <div style={manualHandoffItemStyle}>
                      <span style={manualFlowLabelStyle}>
                        <FileUp size={12} strokeWidth={2.4} />
                        Source
                      </span>
                      <strong>{uploadedFiles.length > 0 ? `${uploadedFiles.length} file${uploadedFiles.length === 1 ? "" : "s"}` : "No files"}</strong>
                    </div>
                    <div style={manualHandoffItemStyle}>
                      <span style={manualFlowLabelStyle}>Signal Review</span>
                      <strong>{availableInSignals ? "Available" : "Needs insight"}</strong>
                    </div>
                    <div style={manualHandoffItemStyle}>
                      <span style={manualFlowLabelStyle}>
                        <Database size={12} strokeWidth={2.4} />
                        Workspace
                      </span>
                      <strong>{workspaceStatusLabel}</strong>
                    </div>
                  </div>
                </div>
              </div>

              <div style={manualFlowPanelStyle}>
                <div style={eyebrowStyle}>Review Flow</div>
                <div style={manualFlowGridStyle}>
                  {manualFlowSteps.map((step) => (
                    <div
                      key={step.label}
                      style={{
                        ...manualFlowStepStyle,
                        ...(step.tone === "done" ? manualFlowStepDoneStyle : {}),
                      }}
                    >
                      <span style={manualFlowLabelStyle}>{step.label}</span>
                      <strong>{step.value}</strong>
                    </div>
                  ))}
                </div>
                <div style={manualFlowNoteStyle}>
                  {hasWorkspaceRecord ? (
                    <>
                      <span>
                        Workspace saved{session.workspace_saved_at ? `: ${formatDateTime(session.workspace_saved_at)}` : ""}.
                      </span>
                      <Link href={workspaceRecordHref} style={manualFlowLinkStyle}>
                        Open Workspace Record
                      </Link>
                    </>
                  ) : availableInSignals ? (
                    "Complete this manual-derived signal from Signal Detail when the insight is ready to preserve as a Workspace record."
                  ) : (
                    "Generate or analyze this session first; then review it in Signals before completing it into Workspace."
                  )}
                </div>
                <div
                  style={{
                    marginTop: "12px",
                    border: "1px solid var(--app-surface-border)",
                    borderRadius: "8px",
                    background: "var(--app-surface-bg)",
                    padding: "12px",
                    display: "grid",
                    gap: "10px",
                  }}
                >
                  <div style={eyebrowStyle}>Completion Audit</div>
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 145px), 1fr))", gap: "8px" }}>
                    {manualCompletionAuditItems.map((item) => (
                      <div key={item.label} style={{ border: "1px solid var(--app-surface-border)", borderRadius: "8px", padding: "9px 10px", background: "var(--app-surface-muted-bg)" }}>
                        <span style={manualFlowLabelStyle}>{item.label}</span>
                        <strong style={{ display: "block", marginTop: "4px", color: "var(--app-text-strong)" }}>{item.value}</strong>
                      </div>
                    ))}
                  </div>
                  <div style={{ color: "#4b5563", fontSize: "13px", lineHeight: 1.6 }}>
                    Use this audit to confirm the manual-derived signal has a clear source, generated insight, Signal Detail review path, and durable Workspace state.
                  </div>
                  <div style={manualIntentSummaryStyle}>
                    <span style={manualFlowLabelStyle}>Manual Intent</span>
                    <strong>{manualIntentSummary.length ? manualIntentSummary.join(" / ") : "Not captured"}</strong>
                    <span>
                      This intent should travel with the manual-derived signal so review can distinguish upload purpose from evidence quality.
                    </span>
                  </div>
                  <div style={manualCompletionDecisionStyle(manualCompletionReady ? "done" : "open")}>
                    <div style={{ display: "grid", gap: "6px", minWidth: "150px" }}>
                      <span style={manualFlowLabelStyle}>Completion Gate</span>
                      <strong>{manualCompletionReady ? "Complete" : "Still Open"}</strong>
                    </div>
                    <div style={manualCompletionDecisionBodyStyle}>
                      <span>{manualCompletionRouteLabel}</span>
                      {manualCompletionGaps.length ? (
                        manualCompletionGaps.map((gap) => <span key={gap}>{gap}</span>)
                      ) : (
                        <span>No remaining completion gaps are visible for this manual session.</span>
                      )}
                    </div>
                  </div>
                  <div style={manualCompletionRouteStyle}>
                    <span>Route:</span>
                    {hasWorkspaceRecord ? (
                      <Link href={workspaceRecordHref} style={manualFlowLinkStyle}>
                        Open Workspace Record
                      </Link>
                    ) : availableInSignals ? (
                      <Link
                        href={`/signals/detail?id=${encodeURIComponent(`manual_${session.session_id}`)}`}
                        style={manualNextActionPrimaryLinkStyle}
                      >
                        Open Signal Detail
                      </Link>
                    ) : (
                      <button
                        type="button"
                        onClick={() => void handleGenerateInsight("chatgpt")}
                        disabled={analysisLoading || insightGenerating}
                        style={analysisLoading || insightGenerating ? disabledActionButtonStyle : auditActionButtonStyle}
                      >
                        Generate Insight
                      </button>
                    )}
                  </div>
                </div>
              </div>

              <div
                style={{
                  marginTop: "18px",
                  display: "flex",
                  gap: "10px",
                  flexWrap: "wrap",
                }}
              >
                <button
                  onClick={() => void handleGenerateInsight("chatgpt")}
                  disabled={analysisLoading || insightGenerating}
                  title="Generate or regenerate this session insight with ChatGPT."
                  style={{
                    ...primaryActionButtonStyle,
                    border: "1px solid var(--app-primary-action-border)",
                    background:
                      analysisLoading || insightGenerating
                        ? "var(--app-surface-muted-bg)"
                        : "var(--app-primary-action-bg)",
                    cursor:
                      analysisLoading || insightGenerating
                        ? "not-allowed"
                        : "pointer",
                    color: analysisLoading || insightGenerating ? "var(--app-text-subtle)" : "var(--app-primary-action-fg)",
                  }}
                >
                  <Sparkles size={15} strokeWidth={2.4} />
                  {insightGenerating && insightGeneratingModel === "chatgpt"
                    ? "Generating..."
                    : "Generate Insight"}
                </button>

                <button
                  onClick={() => void handleGenerateInsight("claude")}
                  disabled={analysisLoading || insightGenerating}
                  title="Generate or regenerate this session insight with Claude."
                  style={{
                    ...secondaryActionButtonStyle,
                    background:
                      analysisLoading || insightGenerating
                        ? "var(--app-surface-muted-bg)"
                        : "var(--app-secondary-action-bg)",
                    cursor:
                      analysisLoading || insightGenerating
                        ? "not-allowed"
                        : "pointer",
                    color: "var(--app-secondary-action-fg)",
                  }}
                >
                  <Sparkles size={15} strokeWidth={2.4} />
                  {insightGenerating && insightGeneratingModel === "claude"
                    ? "Generating..."
                    : "Generate with Claude"}
                </button>

                <button
                  onClick={() => {
                    void fetchSessionDetail()
                      .then((nextSession) => {
                        setSession(nextSession);
                        setMessage("Manual session refreshed.");
                        setError("");
                      })
                      .catch((refreshError) => {
                        setError(getErrorMessage(refreshError, "Failed to refresh manual session."));
                      });
                  }}
                  disabled={analysisLoading || insightGenerating}
                  style={{
                    ...secondaryActionButtonStyle,
                    background: analysisLoading || insightGenerating ? "var(--app-surface-muted-bg)" : "var(--app-secondary-action-bg)",
                    color: "var(--app-secondary-action-fg)",
                    cursor: analysisLoading || insightGenerating ? "not-allowed" : "pointer",
                  }}
                >
                  <RefreshCcw size={15} strokeWidth={2.4} />
                  Refresh Session
                </button>

                {availableInSignals && (
                  <Link
                    href={`/signals/detail?id=${encodeURIComponent(`manual_${session.session_id}`)}`}
                    style={{
                      ...secondaryActionLinkStyle,
                      background: "var(--app-secondary-action-bg)",
                      color: "var(--app-secondary-action-fg)",
                    }}
                  >
                    <Radar size={15} strokeWidth={2.4} />
                    Open in Signals
                  </Link>
                )}
              </div>

              <div style={generationRouteNoticeStyle}>
                <span style={sessionStatusLabelStyle}>Generation Route</span>
                <strong>{latestGenerationRouteText}</strong>
              </div>

              {!availableInSignals && (
                <details style={legacyAnalyzeDetailsStyle}>
                  <summary style={legacyAnalyzeSummaryStyle}>Legacy analysis fallback</summary>
                  <div style={legacyAnalyzeBodyStyle}>
                    <span>
                      Use this only if Generate Insight cannot create the first analysis record for this session.
                    </span>
                    <button
                      onClick={handleAnalyzeSession}
                      disabled={analysisLoading || insightGenerating || uploadedFiles.length === 0}
                      style={{
                        ...secondaryActionButtonStyle,
                        background:
                          analysisLoading || insightGenerating || uploadedFiles.length === 0
                            ? "var(--app-surface-muted-bg)"
                            : "var(--app-secondary-action-bg)",
                        cursor:
                          analysisLoading || insightGenerating || uploadedFiles.length === 0
                            ? "not-allowed"
                            : "pointer",
                        color: "var(--app-secondary-action-fg)",
                      }}
                    >
                      {analysisLoading ? "Analyzing..." : "Run Legacy Analyze"}
                    </button>
                  </div>
                </details>
              )}

              <div
                style={{
                  marginTop: "12px",
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 240px), 1fr))",
                  gap: "10px",
                }}
              >
                <div style={actionGuidanceCardStyle}>
                  <span style={sessionStatusLabelStyle}>Primary Action</span>
                  <strong>{primaryActionGuidance}</strong>
                </div>
                <div style={actionGuidanceCardStyle}>
                  <span style={sessionStatusLabelStyle}>Analyze Session Role</span>
                  <strong>{analyzeSessionGuidance}</strong>
                </div>
              </div>
            </div>
          </section>

          {(message || error) && (
            <div
              style={{
                borderRadius: "8px",
                border: `1px solid ${error ? "var(--app-danger-border)" : "var(--app-info-border)"}`,
                background: error ? "var(--app-danger-bg)" : "var(--app-info-bg)",
                color: error ? "var(--app-danger-fg)" : "var(--app-info-fg)",
                padding: "14px 16px",
                fontSize: "14px",
                lineHeight: 1.6,
              }}
            >
              {error || message}
            </div>
          )}

          <div style={sectionCardStyle}>
            <div style={eyebrowStyle}>Files</div>
            <div style={{ marginTop: "12px", display: "flex", flexDirection: "column", gap: "12px" }}>
              {uploadedFiles.length === 0 ? (
                <div style={{ fontSize: "14px", color: "var(--app-text-subtle)" }}>No file metadata found.</div>
              ) : (
                uploadedFiles.map((file) => (
                  <div
                    key={file.stored_filename}
                    style={{
                      border: "1px solid var(--app-surface-border)",
                      borderRadius: "8px",
                      padding: "14px",
                      background: "var(--app-surface-muted-bg)",
                      display: "flex",
                      justifyContent: "space-between",
                      gap: "12px",
                      flexWrap: "wrap",
                      alignItems: "center",
                    }}
                  >
                    <div>
                      <div style={{ fontSize: "14px", fontWeight: 600, color: "var(--app-text-strong)" }}>
                        {file.original_filename}
                      </div>
                      <div style={{ marginTop: "4px", fontSize: "13px", color: "var(--app-text-subtle)" }}>
                        type: {file.file_kind}
                      </div>
                    </div>
                    {getManualFileUrl(file.stored_filename) ? (
                      <a
                        href={getManualFileUrl(file.stored_filename)}
                        target="_blank"
                        rel="noreferrer"
                        style={secondaryActionLinkStyle}
                      >
                        Open File
                      </a>
                    ) : (
                      <span style={{ fontSize: "14px", color: "var(--app-text-subtle)" }}>Preparing file...</span>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>

          {imageFiles.length > 0 && (
            <div style={sectionCardStyle}>
              <div style={eyebrowStyle}>Image Preview</div>
              <div
                style={{
                  marginTop: "12px",
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
                      borderRadius: "8px",
                      padding: "10px",
                      background: "var(--app-surface-muted-bg)",
                    }}
                  >
                    <button
                      onClick={() => setLightboxIndex(index)}
                      style={{
                        border: "none",
                        background: "transparent",
                        padding: 0,
                        cursor: "pointer",
                        width: "100%",
                        textAlign: "left",
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
                            height: "240px",
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
                            height: "240px",
                            borderRadius: "8px",
                            border: "1px solid var(--app-surface-border)",
                            background: "var(--app-surface-muted-bg)",
                            color: "var(--app-text-subtle)",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            fontSize: "13px",
                          }}
                        >
                          Preparing preview...
                        </div>
                      )}
                    </button>
                    <div style={{ marginTop: "10px", fontSize: "13px", color: "var(--app-text-muted)", lineHeight: 1.6 }}>
                      {file.original_filename}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {textLikeFiles.length > 0 && (
            <div style={sectionCardStyle}>
              <div style={eyebrowStyle}>Text / PDF Preview</div>
              <div style={{ marginTop: "12px", display: "flex", flexDirection: "column", gap: "16px" }}>
                {textLikeFiles.map((file) => {
                  const previewText = getPreviewText(file);
                  const pdfUrl = file.file_kind === "pdf" ? getManualFileUrl(file.stored_filename) : "";
                  const canExpandPreview = Boolean(previewText) && file.file_kind !== "pdf";

                  return (
                    <div
                      key={file.stored_filename}
                      style={{
                        border: "1px solid var(--app-surface-border)",
                        borderRadius: "8px",
                        padding: "14px",
                        background: "var(--app-surface-muted-bg)",
                      }}
                    >
                      <div style={{ fontSize: "13px", fontWeight: 700, marginBottom: "8px", color: "var(--app-text-strong)" }}>
                        {file.original_filename}
                      </div>
                      {file.article_fetch_status && (
                        <div
                          style={{
                            marginBottom: "10px",
                            display: "inline-flex",
                            alignItems: "center",
                            borderRadius: "999px",
                            border:
                              file.article_fetch_status === "fetched"
                                ? "1px solid var(--app-success-border)"
                                : "1px solid var(--app-danger-border)",
                            background:
                              file.article_fetch_status === "fetched" ? "var(--app-success-bg)" : "var(--app-danger-bg)",
                            color: file.article_fetch_status === "fetched" ? "var(--app-success-fg)" : "var(--app-danger-fg)",
                            padding: "4px 10px",
                            fontSize: "12px",
                            fontWeight: 700,
                          }}
                        >
                          Article fetch: {file.article_fetch_status}
                        </div>
                      )}
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
                                  background: "var(--app-surface-muted-bg)",
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
                              fontSize: "14px",
                              color: "var(--app-text-muted)",
                              lineHeight: 1.7,
                              whiteSpace: "pre-wrap",
                            }}
                          >
                            {previewText}
                          </div>
                        ) : (
                          <div
                            style={{
                              border: "1px dashed var(--app-surface-strong-border)",
                              borderRadius: "8px",
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
                        <div style={{ fontSize: "14px", color: "var(--app-text-muted)", lineHeight: 1.7 }}>
                          (No preview available. Full text will be analyzed in backend.)
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          <div ref={analysisSectionRef} style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
            <div style={sectionCardStyle}>
              <div style={eyebrowStyle}>Analysis Status</div>
              <div style={{ marginTop: "10px", fontSize: "15px", color: "var(--app-text-muted)", lineHeight: 1.7 }}>
                {availableInSignals
                  ? "Analysis completed and this manual session is now available in Signals. Use Generate Insight or Generate with Claude when you want to refresh the structured insight."
                  : "This session does not have saved analysis yet. Use Generate Insight to create the first structured result; the legacy analysis fallback is available only if the primary path cannot initialize the record."}
              </div>
            </div>

            <ManualVerificationPanel session={session} />

            <AnalysisCard title="Summary" content={sessionAnalysis?.summary} />
            <AnalysisCard title="Why It Matters" content={sessionAnalysis?.why_it_matters} />
            <AnalysisCard title="Relevance To Projects" content={sessionAnalysis?.relevance_to_projects} />
            <AnalysisCard title="Relevance To Career" content={sessionAnalysis?.relevance_to_career} />
            <AnalysisCard title="Synthesized Insight" content={sessionAnalysis?.synthesized_insight} />

            <div style={sectionCardStyle}>
              <div style={eyebrowStyle}>Related Deep Reflections</div>

              {relatedReflectionTopics.length > 0 && (
                <div style={{ marginTop: "10px", fontSize: "14px", color: "var(--app-text-muted)" }}>
                  Matching topics: {relatedReflectionTopics.join(", ")}
                </div>
              )}

              <div style={{ marginTop: "12px" }}>
                {relatedReflectionsLoading ? (
                  <div style={{ fontSize: "14px", color: "var(--app-text-subtle)" }}>Loading related deep reflections...</div>
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
                          borderRadius: "8px",
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
                            href={`/reflections/detail?id=${encodeURIComponent(item.id || "")}`}
                            style={{
                              color: "var(--app-info-fg)",
                              textDecoration: "none",
                              fontWeight: 700,
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
                                background: "var(--app-chip-bg)",
                                color: "var(--app-chip-fg)",
                                border: "1px solid var(--app-chip-border)",
                                fontSize: "12px",
                                fontWeight: 600,
                              }}
                            >
                              Match {item.match_score}
                            </span>
                          )}
                        </div>
                        <div style={{ fontSize: "13px", color: "var(--app-text-subtle)", lineHeight: 1.7 }}>
                          Source: {item.source || "unknown"} · Updated:{" "}
                          {item.timestamp ? new Date(item.timestamp).toLocaleString() : "Unknown"}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </AppContainer>

      {currentLightboxFile && (
        <div
          onClick={() => setLightboxIndex(null)}
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
            onClick={(event) => event.stopPropagation()}
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
              onClick={() =>
                setLightboxIndex((current) =>
                  current === null || current === 0 ? imageFiles.length - 1 : current - 1
                )
              }
              style={lightboxButtonStyle}
            >
              Prev
            </button>

            <div
              style={{
                background: "#111",
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
                    background: "#1f2937",
                    color: "#e5e7eb",
                    fontSize: "14px",
                  }}
                >
                  Preparing preview...
                </div>
              )}
              <div
                style={{
                  marginTop: "12px",
                  color: "#fff",
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
              onClick={() =>
                setLightboxIndex((current) =>
                  current === null || current === imageFiles.length - 1 ? 0 : current + 1
                )
              }
              style={lightboxButtonStyle}
            >
              Next
            </button>

            <button
              onClick={() => setLightboxIndex(null)}
              style={{
                position: "absolute",
                top: "-10px",
                right: "-4px",
                border: "none",
                background: "rgba(255,255,255,0.18)",
                color: "#fff",
                minWidth: "72px",
                height: "42px",
                padding: "0 14px",
                borderRadius: "999px",
                fontSize: "14px",
                fontWeight: 700,
                cursor: "pointer",
              }}
            >
              Close
            </button>
          </div>
        </div>
      )}
    </>
  );
}

const manualDetailShellStyle = {
  maxWidth: "1360px",
  paddingTop: "28px",
  "--app-text-strong": "#f8fafc",
  "--app-text-muted": "#b8c7da",
  "--app-text-subtle": "#8fa4bd",
  "--app-primary-action-bg": "rgba(59, 130, 246, 0.18)",
  "--app-primary-action-fg": "#dbeafe",
  "--app-primary-action-border": "rgba(147, 197, 253, 0.36)",
  "--app-secondary-action-bg": "rgba(15, 23, 42, 0.72)",
  "--app-secondary-action-fg": "#f8fafc",
  "--app-secondary-action-border": "rgba(148, 163, 184, 0.3)",
  "--app-ghost-action-bg": "rgba(30, 41, 59, 0.72)",
  "--app-ghost-action-fg": "#cbd5e1",
  "--app-ghost-action-border": "rgba(148, 163, 184, 0.24)",
  "--app-input-bg": "rgba(15, 23, 42, 0.72)",
  "--app-input-fg": "#f8fafc",
  "--app-input-border": "rgba(148, 163, 184, 0.34)",
  "--app-chip-bg": "rgba(59, 130, 246, 0.14)",
  "--app-chip-fg": "#dbeafe",
  "--app-chip-border": "rgba(147, 197, 253, 0.26)",
  "--app-tag-bg": "rgba(99, 102, 241, 0.2)",
  "--app-tag-fg": "#c7d2fe",
  "--app-info-bg": "rgba(59, 130, 246, 0.14)",
  "--app-info-fg": "#dbeafe",
  "--app-info-border": "rgba(147, 197, 253, 0.28)",
  "--app-warning-bg": "rgba(245, 158, 11, 0.14)",
  "--app-warning-fg": "#fde68a",
  "--app-warning-border": "rgba(245, 158, 11, 0.34)",
  "--app-danger-bg": "rgba(244, 63, 94, 0.14)",
  "--app-danger-fg": "#fecdd3",
  "--app-danger-border": "rgba(244, 63, 94, 0.32)",
  "--app-success-bg": "rgba(34, 197, 94, 0.14)",
  "--app-success-fg": "#bbf7d0",
  "--app-success-border": "rgba(34, 197, 94, 0.32)",
  "--app-surface-bg": "rgba(15, 23, 42, 0.76)",
  "--app-surface-muted-bg": "rgba(15, 23, 42, 0.56)",
  "--app-surface-soft-bg": "rgba(30, 41, 59, 0.58)",
  "--app-surface-border": "rgba(148, 163, 184, 0.24)",
  "--app-surface-strong-border": "rgba(147, 197, 253, 0.28)",
  "--app-surface-shadow": "0 18px 44px rgba(0, 0, 0, 0.22)",
} as CSSProperties;

const manualDetailHeroStyle: CSSProperties = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-bg)",
  padding: "clamp(22px, 3vw, 34px)",
  boxShadow: "var(--app-surface-shadow)",
};

const manualDetailStatusGridStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 190px), 1fr))",
  gap: "10px",
  marginTop: "6px",
};

const sectionCardStyle: CSSProperties = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  padding: "22px",
  background: "var(--app-surface-bg)",
  boxShadow: "var(--app-surface-shadow)",
};

const primaryNavLinkStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: "7px",
  width: "fit-content",
  padding: "7px 12px",
  borderRadius: "8px",
  border: "1px solid var(--app-primary-action-border)",
  background: "var(--app-primary-action-bg)",
  color: "var(--app-primary-action-fg)",
  textDecoration: "none",
  fontSize: "13px",
  fontWeight: 700,
};

const detailTitleStyle: CSSProperties = {
  fontSize: "clamp(28px, 4.5vw, 46px)",
  lineHeight: 1.04,
  fontWeight: 850,
  color: "var(--app-text-strong)",
  letterSpacing: 0,
  maxWidth: "980px",
};

const primaryActionButtonStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: "7px",
  padding: "7px 12px",
  borderRadius: "8px",
  fontSize: "13px",
  fontWeight: 700,
};

const secondaryActionButtonStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: "7px",
  padding: "7px 12px",
  borderRadius: "8px",
  border: "1px solid var(--app-secondary-action-border)",
  background: "var(--app-secondary-action-bg)",
  color: "var(--app-secondary-action-fg)",
  fontSize: "13px",
  fontWeight: 700,
};

const secondaryActionLinkStyle: CSSProperties = {
  ...secondaryActionButtonStyle,
  textDecoration: "none",
};

const eyebrowStyle: CSSProperties = {
  fontSize: "12px",
  color: "var(--app-text-subtle)",
  textTransform: "uppercase",
  letterSpacing: 0,
  fontWeight: 700,
};

const topicBadgeStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: "6px",
  padding: "6px 12px",
  borderRadius: "999px",
  background: "var(--app-tag-bg)",
  color: "var(--app-tag-fg)",
  border: "1px solid var(--app-chip-border)",
  fontSize: "13px",
  fontWeight: 600,
};

const statusBadgeStyle: CSSProperties = {
  padding: "6px 12px",
  borderRadius: "999px",
  fontSize: "13px",
  fontWeight: 600,
};

const smallChipStyle: CSSProperties = {
  padding: "4px 8px",
  borderRadius: "999px",
  border: "1px solid var(--app-chip-border)",
  background: "var(--app-chip-bg)",
  color: "var(--app-chip-fg)",
};

const sessionStatusItemStyle: CSSProperties = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  padding: "10px 12px",
  display: "flex",
  flexDirection: "column",
  gap: "4px",
  minWidth: 0,
};

const sessionStatusLabelStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: "6px",
  fontSize: "11px",
  color: "var(--app-text-subtle)",
  fontWeight: 700,
  textTransform: "uppercase",
  letterSpacing: 0,
};

const manualFlowPanelStyle: CSSProperties = {
  marginTop: "4px",
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  padding: "14px",
};

const manualHandoffDashboardStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 300px), 1fr))",
  gap: "12px",
  alignItems: "stretch",
};

const manualFlowGridStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 150px), 1fr))",
  gap: "8px",
  marginTop: "10px",
};

const manualFlowStepStyle: CSSProperties = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-bg)",
  padding: "10px 12px",
  display: "flex",
  flexDirection: "column",
  gap: "5px",
  color: "var(--app-text-muted)",
};

const manualFlowStepDoneStyle: CSSProperties = {
  border: "1px solid var(--app-success-border)",
  background: "var(--app-success-bg)",
  color: "var(--app-success-fg)",
};

const manualFlowLabelStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: "5px",
  fontSize: "11px",
  color: "var(--app-text-subtle)",
  fontWeight: 700,
  textTransform: "uppercase",
  letterSpacing: 0,
};

const manualFlowNoteStyle: CSSProperties = {
  marginTop: "10px",
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  gap: "10px",
  flexWrap: "wrap",
  fontSize: "13px",
  lineHeight: 1.6,
  color: "var(--app-text-muted)",
};

const manualFlowLinkStyle: CSSProperties = {
  border: "1px solid var(--app-secondary-action-border)",
  borderRadius: "8px",
  background: "var(--app-secondary-action-bg)",
  color: "var(--app-secondary-action-fg)",
  padding: "7px 10px",
  fontSize: "13px",
  fontWeight: 700,
  textDecoration: "none",
};

const manualNextActionPanelStyle: CSSProperties = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-bg)",
  color: "var(--app-text-muted)",
  padding: "12px 14px",
  display: "grid",
  gap: "6px",
  fontSize: "13px",
  lineHeight: 1.6,
};

const manualNextActionDoneStyle: CSSProperties = {
  border: "1px solid var(--app-success-border)",
  background: "var(--app-success-bg)",
  color: "var(--app-success-fg)",
};

const manualNextActionLinksStyle: CSSProperties = {
  display: "flex",
  gap: "8px",
  flexWrap: "wrap",
  marginTop: "2px",
};

const manualNextActionPrimaryLinkStyle: CSSProperties = {
  border: "1px solid var(--app-primary-action-border)",
  borderRadius: "8px",
  background: "var(--app-primary-action-bg)",
  color: "var(--app-primary-action-fg)",
  padding: "7px 10px",
  fontSize: "13px",
  fontWeight: 700,
  textDecoration: "none",
};

const manualCompletionDecisionStyle = (tone: "done" | "open"): CSSProperties => ({
  border: `1px solid ${tone === "done" ? "var(--app-success-border)" : "var(--app-warning-border)"}`,
  borderRadius: "8px",
  background: tone === "done" ? "var(--app-success-bg)" : "var(--app-warning-bg)",
  color: tone === "done" ? "var(--app-success-fg)" : "var(--app-warning-fg)",
  padding: "10px 12px",
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 220px), 1fr))",
  gap: "10px",
  fontSize: "13px",
  lineHeight: 1.55,
});

const manualIntentSummaryStyle: CSSProperties = {
  border: "1px solid var(--app-info-border)",
  borderRadius: "8px",
  background: "var(--app-surface-bg)",
  padding: "12px",
  display: "grid",
  gap: "5px",
  color: "var(--app-text-muted)",
  fontSize: "13px",
  lineHeight: 1.55,
};

const manualCompletionDecisionBodyStyle: CSSProperties = {
  display: "grid",
  gap: "4px",
  color: "var(--app-text-muted)",
  fontWeight: 650,
};

const manualCompletionRouteStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: "8px",
  flexWrap: "wrap",
  color: "var(--app-text-muted)",
  fontSize: "13px",
  fontWeight: 700,
};

const auditActionButtonStyle: CSSProperties = {
  border: "1px solid var(--app-primary-action-border)",
  borderRadius: "8px",
  background: "var(--app-primary-action-bg)",
  color: "var(--app-primary-action-fg)",
  padding: "7px 10px",
  fontSize: "13px",
  fontWeight: 700,
  cursor: "pointer",
};

const disabledActionButtonStyle: CSSProperties = {
  ...auditActionButtonStyle,
  border: "1px solid var(--app-surface-border)",
  background: "var(--app-surface-muted-bg)",
  color: "var(--app-text-subtle)",
  cursor: "not-allowed",
};

const legacyAnalyzeDetailsStyle: CSSProperties = {
  marginTop: "12px",
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  color: "var(--app-text-muted)",
  padding: "10px 12px",
};

const legacyAnalyzeSummaryStyle: CSSProperties = {
  cursor: "pointer",
  color: "var(--app-text-muted)",
  fontSize: "13px",
  fontWeight: 800,
};

const legacyAnalyzeBodyStyle: CSSProperties = {
  marginTop: "10px",
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  gap: "10px",
  flexWrap: "wrap",
  fontSize: "13px",
  lineHeight: 1.55,
};

const manualHandoffPanelStyle: CSSProperties = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-bg)",
  color: "var(--app-text-muted)",
  padding: "12px 14px",
  display: "grid",
  gap: "10px",
  fontSize: "13px",
  lineHeight: 1.6,
};

const manualHandoffDoneStyle: CSSProperties = {
  border: "1px solid var(--app-success-border)",
  background: "var(--app-success-bg)",
  color: "var(--app-success-fg)",
};

const manualHandoffReadyStyle: CSSProperties = {
  border: "1px solid var(--app-info-border)",
  background: "var(--app-info-bg)",
  color: "var(--app-info-fg)",
};

const manualHandoffWarningStyle: CSSProperties = {
  border: "1px solid var(--app-warning-border)",
  background: "var(--app-warning-bg)",
  color: "var(--app-warning-fg)",
};

const manualHandoffHeaderStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  gap: "10px",
  alignItems: "flex-start",
  flexWrap: "wrap",
};

const manualHandoffChipStyle: CSSProperties = {
  border: "1px solid var(--app-chip-border)",
  borderRadius: "999px",
  background: "var(--app-chip-bg)",
  color: "var(--app-chip-fg)",
  padding: "4px 8px",
  fontSize: "11px",
  fontWeight: 800,
};

const manualHandoffGridStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 145px), 1fr))",
  gap: "8px",
};

const manualHandoffItemStyle: CSSProperties = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-bg)",
  padding: "9px 10px",
  display: "grid",
  gap: "4px",
};

const actionGuidanceCardStyle: CSSProperties = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-bg)",
  color: "var(--app-text-muted)",
  padding: "10px 12px",
  display: "grid",
  gap: "6px",
  fontSize: "13px",
  lineHeight: 1.55,
};

const generationRouteNoticeStyle: CSSProperties = {
  marginTop: "12px",
  border: "1px solid var(--app-info-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  color: "var(--app-info-fg)",
  padding: "10px 12px",
  display: "grid",
  gap: "5px",
  fontSize: "13px",
  lineHeight: 1.55,
};

const lightboxButtonStyle: CSSProperties = {
  border: "none",
  background: "rgba(255,255,255,0.18)",
  color: "#fff",
  minWidth: "64px",
  height: "48px",
  padding: "0 14px",
  borderRadius: "999px",
  fontSize: "14px",
  fontWeight: 700,
  cursor: "pointer",
  flexShrink: 0,
};

function renderAnalysisContent(value: unknown): ReactNode {
  const normalizedValue = stripUncertainText(value);

  if (normalizedValue === null || normalizedValue === undefined || normalizedValue === "") {
    return <span style={{ color: "var(--app-text-subtle)" }}>No content available yet.</span>;
  }

  if (typeof normalizedValue === "string" || typeof normalizedValue === "number") {
    return <span style={{ whiteSpace: "pre-wrap" }}>{String(normalizedValue)}</span>;
  }

  if (Array.isArray(normalizedValue)) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
        {normalizedValue.map((item, index) => (
          <div
            key={index}
            style={{
              border: "1px solid var(--app-surface-border)",
              borderRadius: "8px",
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

  if (typeof normalizedValue === "object" && normalizedValue !== null) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
        {Object.entries(normalizedValue).map(([key, nestedValue]) => (
          <div
            key={key}
            style={{
              border: "1px solid var(--app-surface-border)",
              borderRadius: "8px",
              padding: "12px",
              background: "var(--app-surface-muted-bg)",
            }}
          >
            <div
              style={{
                fontSize: "13px",
                fontWeight: 600,
                marginBottom: "6px",
                color: "var(--app-text-subtle)",
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
              {renderAnalysisContent(nestedValue)}
            </div>
          </div>
        ))}
      </div>
    );
  }

  return <span>{String(normalizedValue)}</span>;
}

function ManualVerificationPanel({ session }: { session: ManualSessionDetail }) {
  const verification = session.verification || session.policy_metadata?.verification;
  const evidenceQuality = verification?.evidence_quality;
  const evidenceLevel = String(evidenceQuality?.level || "").toLowerCase();
  const hasEvidenceQuality = Boolean(evidenceQuality);
  const hasEvidencePack = Boolean(session.evidence_pack);
  const showEvidenceNote = hasEvidenceQuality || hasEvidencePack || Boolean(verification);

  if (!showEvidenceNote) {
    return null;
  }

  const isLowEvidence = evidenceLevel === "insufficient" || evidenceLevel === "thin";
  const toneColor = isLowEvidence || !hasEvidenceQuality ? "var(--app-warning-fg)" : "var(--app-success-fg)";
  const headingColor = toneColor;
  const borderColor = isLowEvidence || !hasEvidenceQuality ? "var(--app-warning-border)" : "var(--app-success-border)";
  const backgroundColor = isLowEvidence || !hasEvidenceQuality ? "var(--app-warning-bg)" : "var(--app-success-bg)";
  const claimResults = verification?.claim_results || [];
  const sortedClaimResults = [...claimResults].sort(
    (left, right) => getClaimSupportRank(left.support_level) - getClaimSupportRank(right.support_level)
  );
  const claimSupportSummary = verification?.claim_support_summary || {};
  const verificationLimitations = verification?.limitations || [];
  const evidenceReasonCodes = evidenceQuality?.reason_codes || [];
  const allowedDownstreamActions = verification?.allowed_downstream_actions || [];
  const blockedDownstreamActions = verification?.blocked_downstream_actions || [];
  const reviewPriority = getReviewPriority({
    verificationStatus: verification?.verification_status,
    blockedActions: blockedDownstreamActions,
    supportSummary: claimSupportSummary,
  });
  const supportSummaryText = formatClaimSupportSummary(claimSupportSummary);

  return (
    <div
      style={{
        border: `1px solid ${borderColor}`,
        borderRadius: "8px",
        padding: "18px",
        background: backgroundColor,
      }}
    >
      <div style={{ ...eyebrowStyle, color: headingColor }}>Evidence Note</div>
      <div style={{ color: headingColor, fontSize: "14px", lineHeight: 1.6, marginTop: "10px" }}>
        {hasEvidenceQuality
          ? isLowEvidence
            ? `This insight is based on ${evidenceLevel === "insufficient" ? "insufficient" : "thin"} evidence, so it should be read as a cautious interpretation rather than a strong conclusion.`
            : `Evidence quality is ${evidenceLevel || "available"}, so this insight has a traceable evidence summary attached.`
          : "An evidence pack is attached to this insight, but evidence-quality scoring is not available on this saved record yet. Regenerate the insight to compute score, source, and reason metadata."}
      </div>
      <div style={{ color: toneColor, fontSize: "13px", lineHeight: 1.6, marginTop: "8px" }}>
        Score: {typeof evidenceQuality?.score === "number" ? evidenceQuality.score.toFixed(2) : "N/A"} | Summary source:{" "}
        {formatSummaryProvenance(evidenceQuality?.summary_provenance)}
      </div>
      {(verification?.verification_status || verification?.confidence_label || typeof verification?.confidence_score === "number") && (
        <div style={{ color: toneColor, fontSize: "13px", lineHeight: 1.6, marginTop: "8px" }}>
          Verification: {formatCompactLabel(verification?.verification_status)}
          {verification?.confidence_label ? ` | Confidence: ${formatCompactLabel(verification.confidence_label)}` : ""}
          {typeof verification?.confidence_score === "number" ? ` (${verification.confidence_score.toFixed(2)})` : ""}
        </div>
      )}
      <div
        style={{
          display: "inline-flex",
          alignItems: "center",
          marginTop: "10px",
          padding: "6px 10px",
          borderRadius: "999px",
          border: reviewPriority.border,
          background: reviewPriority.background,
          color: reviewPriority.color,
          fontSize: "12px",
          fontWeight: 700,
          textTransform: "uppercase",
          letterSpacing: 0,
        }}
      >
        Review Priority: {reviewPriority.label}
      </div>
      {verification ? (
        <VerificationGateNote
          verification={verification}
          accentColor={reviewPriority.color}
          background="var(--app-surface-bg)"
          style={{ marginTop: "10px" }}
        />
      ) : null}
      {supportSummaryText && (
        <div style={{ color: toneColor, fontSize: "13px", lineHeight: 1.6, marginTop: "8px" }}>
          Claim support: {supportSummaryText}
        </div>
      )}
      {evidenceReasonCodes.length > 0 && (
        <div style={{ color: toneColor, fontSize: "13px", lineHeight: 1.6, marginTop: "8px" }}>
          Why: {formatEvidenceReason(evidenceReasonCodes[0])}
        </div>
      )}
      {(verification?.downgrade_reason || verificationLimitations.length > 0) && (
        <div style={{ color: toneColor, fontSize: "13px", lineHeight: 1.6, marginTop: "8px" }}>
          {verification?.downgrade_reason ? `Downgrade: ${formatCompactLabel(verification.downgrade_reason)}.` : null}
          {verificationLimitations.length > 0 ? ` Limitation: ${formatCompactLabel(verificationLimitations[0])}.` : null}
        </div>
      )}
      {(allowedDownstreamActions.length > 0 || blockedDownstreamActions.length > 0) && (
        <div
          style={{
            marginTop: "12px",
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 220px), 1fr))",
            gap: "10px",
          }}
        >
          <ActionGateBox
            label="Allowed"
            borderColor="var(--app-success-border)"
            titleColor="var(--app-success-fg)"
            textColor="var(--app-success-fg)"
            actions={allowedDownstreamActions}
          />
          <ActionGateBox
            label="Blocked"
            borderColor="var(--app-danger-border)"
            titleColor="var(--app-danger-fg)"
            textColor="var(--app-danger-fg)"
            actions={blockedDownstreamActions}
          />
        </div>
      )}
      {sortedClaimResults.length > 0 && (
        <div
          style={{
            marginTop: "14px",
            paddingTop: "12px",
            borderTop: `1px solid ${borderColor}`,
          }}
        >
          <div style={{ ...eyebrowStyle, color: toneColor, marginBottom: "8px" }}>Claim Checks</div>
          <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
            {sortedClaimResults.slice(0, 5).map((claim, index) => {
              const supportStyle = getClaimDisplayStyle(claim);
              const isProjectRelevance = isProjectRelevanceClaim(claim);
              const sourceExcerpt = getClaimSourceExcerpt(claim, session.evidence_pack);
              return (
                <div
                  key={claim.claim_id || `${claim.claim_text}-${index}`}
                  style={{
                    border: supportStyle.border,
                    borderRadius: "8px",
                    padding: "10px 12px",
                    background: supportStyle.background,
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      gap: "8px",
                      flexWrap: "wrap",
                      alignItems: "center",
                      marginBottom: "6px",
                    }}
                  >
                    <span style={{ fontSize: "12px", fontWeight: 700, color: "var(--app-text-strong)" }}>
                      {getClaimDisplayTypeLabel(claim)}
                    </span>
                    <span style={{ fontSize: "12px", color: supportStyle.color, fontWeight: 700 }}>
                      {getClaimDisplaySupportLabel(claim)}
                    </span>
                    <span style={{ fontSize: "12px", color: "var(--app-text-subtle)" }}>
                      {formatCompactLabel(claim.source_field)}
                    </span>
                    <span style={{ fontSize: "12px", color: "var(--app-text-subtle)" }}>
                      Evidence refs: {Array.isArray(claim.evidence_refs) ? claim.evidence_refs.length : 0}
                    </span>
                  </div>
                  <div style={{ color: "var(--app-text-muted)", fontSize: "13px", lineHeight: 1.55 }}>
                    {claim.claim_text || "Claim text unavailable."}
                  </div>
                  {Array.isArray(claim.verification_notes) && claim.verification_notes.length > 0 && (
                    <div style={{ color: "var(--app-text-subtle)", fontSize: "12px", lineHeight: 1.5, marginTop: "6px" }}>
                      Note: {formatCompactLabel(claim.verification_notes[0])}
                    </div>
                  )}
                  {isProjectRelevance ? (
                    <div style={{ color: "var(--app-info-fg)", fontSize: "12px", lineHeight: 1.5, marginTop: "6px" }}>
                      Boundary: project-fit interpretation, not an external factual claim. Evidence refs still show whether the source text directly supports the analogy.
                    </div>
                  ) : null}
                  {sourceExcerpt ? (
                    <details style={{ marginTop: "8px" }}>
                      <summary
                        style={{
                          cursor: "pointer",
                          color: supportStyle.color,
                          fontSize: "12px",
                          fontWeight: 700,
                        }}
                      >
                        Source span
                      </summary>
                      <div
                        style={{
                          marginTop: "6px",
                          borderLeft: `3px solid ${supportStyle.color}`,
                          paddingLeft: "10px",
                        }}
                      >
                        <div style={{ color: "var(--app-text-subtle)", fontSize: "12px", lineHeight: 1.45 }}>
                          {sourceExcerpt.location}
                          {sourceExcerpt.matchDetails ? ` · ${sourceExcerpt.matchDetails}` : ""}
                        </div>
                        <blockquote
                          style={{
                            margin: "6px 0 0",
                            color: "var(--app-text-strong)",
                            fontSize: "12px",
                            lineHeight: 1.55,
                            whiteSpace: "pre-wrap",
                          }}
                        >
                          {sourceExcerpt.excerpt}
                        </blockquote>
                      </div>
                    </details>
                  ) : null}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

function ActionGateBox({
  label,
  borderColor,
  titleColor,
  textColor,
  actions,
}: {
  label: string;
  borderColor: string;
  titleColor: string;
  textColor: string;
  actions: string[];
}) {
  return (
    <div
      style={{
        border: `1px solid ${borderColor}`,
        borderRadius: "8px",
        padding: "10px 12px",
        background: "var(--app-surface-bg)",
      }}
    >
      <div style={{ color: titleColor, fontSize: "12px", fontWeight: 700, marginBottom: "6px", textTransform: "uppercase" }}>
        {label}
      </div>
      <div style={{ color: textColor, fontSize: "13px", lineHeight: 1.6 }}>
        {actions.length > 0 ? actions.map(formatCompactLabel).join(", ") : "None"}
      </div>
    </div>
  );
}

function AnalysisCard({ title, content }: { title: string; content?: AnalysisValue }) {
  return (
    <div style={sectionCardStyle}>
      <div style={eyebrowStyle}>{title}</div>
      <div style={{ marginTop: "10px", lineHeight: "1.7" }}>{renderAnalysisContent(content)}</div>
    </div>
  );
}
