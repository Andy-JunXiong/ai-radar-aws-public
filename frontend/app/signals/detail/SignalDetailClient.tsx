"use client";

import Image from "next/image";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { type ChangeEvent, useEffect, useMemo, useRef, useState } from "react";
import { Copy, Maximize2, Minimize2, Star } from "lucide-react";
import SignalDecisionFlow from "@/components/SignalDecisionFlow";
import VerificationGateNote from "@/components/VerificationGateNote";
import VerifiedInsightObjectPanel, { type VerifiedInsightObjectRow } from "@/components/VerifiedInsightObjectPanel";
import { API_BASE } from "@/lib/api";
import {
  adminFetch,
  buildAdminAuthHeaders,
} from "@/lib/adminAuth";

const SIGNALS_CACHE_KEY = "ai-radar-signals-cache-v9";
const STATUS_UPDATE_TIMEOUT_MS = 8_000;
const STATUS_REFRESH_TIMEOUT_MS = 5_000;
const PDF_PREVIEW_PENDING_MESSAGE =
  "[PDF uploaded successfully. Text preview will be generated during analysis.]";

const withTimeout = async <T,>(promise: Promise<T>, timeoutMs: number, message: string): Promise<T> => {
  let timeoutId: number | null = null;

  try {
    return await Promise.race([
      promise,
      new Promise<T>((_, reject) => {
        timeoutId = window.setTimeout(() => reject(new Error(message)), timeoutMs);
      }),
    ]);
  } finally {
    if (timeoutId !== null) {
      window.clearTimeout(timeoutId);
    }
  }
};

type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  provider_used?: string;
  model_used?: string;
  fallback_used?: boolean;
};

type ModelKey = "claude" | "chatgpt" | "perplexity";
type UiTab = "Claude" | "ChatGPT" | "Perplexity";
type ConversationIntent = "artifact" | "discussion";
type VisualStyle = "architecture" | "infographic" | "concept_map" | "editorial";
type StructuredValue = string | number | boolean | null | undefined | StructuredValue[] | { [key: string]: StructuredValue };

const RECENT_DISCUSSION_CONTEXT_LIMIT = 4;

type ModelProvenance = {
  provider?: string;
  model_id?: string;
  model_version?: string;
  task_type?: string;
  route_key?: string;
  router_source?: string;
  prompt_template_id?: string;
  prompt_template_version?: string;
  deterministic_fingerprint?: string;
  generated_at?: string;
  provenance_schema_version?: number;
  provenance_completeness?: string;
};

type DecisionTraceEvent = {
  event_type?: string;
  actor?: string;
  timestamp?: string;
  status_before?: string;
  status_after?: string;
  route?: string;
  support?: {
    saved_reason?: string | null;
    verification_status?: string | null;
    blocked_downstream_actions?: string[];
    allowed_downstream_actions?: string[];
    claim_support_summary?: Record<string, number>;
    evidence_level?: string | null;
    evidence_pack_id?: string | null;
  };
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
  presentation_fidelity?: {
    limits_state?: string;
    reason_codes?: string[];
    source_stated_limits_count?: number;
    source_stated_confidence_present?: boolean;
  } | null;
};

type FeedbackReasonSlot = "stale_input" | "not_me" | "reasoning_gap" | "blind_spot";

type ClaimFeedbackDraft = {
  open: boolean;
  reasonSlot: FeedbackReasonSlot;
  note: string;
  submitting: boolean;
  submitted: boolean;
  message: string;
  error: string;
};

type SignalReviewFeedbackRecord = {
  id?: string;
  claim_id?: string;
  reason_slot?: string;
  note?: string;
  created_at?: string;
  relationship_annotation?: RelationshipAnnotation | null;
};

type RelationshipAnnotation = {
  relation_type?: string;
  grounding_source?: string;
  derivation_mechanism?: string;
  support_posture?: string;
  review_reason_codes?: string[];
  source_refs?: string[];
  rationale?: string;
  classified_by?: string;
};

type ReviewBundleSnapshot = {
  snapshot_id?: string;
  signal_id?: string;
  content_hash?: string;
  created_at?: string;
  used_by?: string;
  source_kind?: string;
  source_text?: string;
  metadata?: {
    external_synthesis_quality?: ExternalSynthesisQualityAssessment;
  };
};

type FinalTakeawayArtifact = {
  final_takeaway_id?: string;
  signal_id?: string;
  status?: string;
  confirmed_text?: string;
  review_bundle_snapshot_id?: string;
  review_bundle_content_hash?: string;
  confirmed_by?: string;
  confirmed_at?: string;
};

type ExternalSynthesisSource = {
  external_synthesis_source_id?: string;
  signal_id?: string;
  source_kind?: string;
  source_file?: string;
  content_type?: string;
  source_text?: string;
  source_text_length?: number;
  original_content_hash?: string;
  normalized_content_hash?: string;
  evidence_boundary?: string;
  used_by?: string;
  created_at?: string;
  metadata?: {
    external_synthesis_quality?: ExternalSynthesisQualityAssessment;
  };
};

type ExternalSynthesisQualityFlag = {
  code: string;
  label: string;
  detail: string;
};

type ExternalSynthesisQualityAssessment = {
  schema_version: 1;
  status: "clean" | "warning" | "not_checked" | "not_attached";
  summary: string;
  flags: ExternalSynthesisQualityFlag[];
  effect: "non_blocking_review_context_warning";
  evidence_boundary: "review_context_not_verified_evidence";
  review_context_only: true;
  not_verified_evidence: true;
  checked_at?: string;
  checked_text_length: number;
  source_file: string;
  source_kind: string;
  topic_terms_checked: string[];
  topic_hit_count: number;
};

const FEEDBACK_REASON_OPTIONS: Array<{ value: FeedbackReasonSlot; label: string }> = [
  { value: "stale_input", label: "Stale input" },
  { value: "not_me", label: "Not me" },
  { value: "reasoning_gap", label: "Reasoning gap" },
  { value: "blind_spot", label: "My blind spot" },
];

type DeepProjectMatchChecklistItem = {
  key: string;
  label: string;
  value: string;
  status: "ok" | "watch" | "risk";
};

type DeepProjectMatchReview = {
  required: boolean;
  status: "not_project_related" | "not_required" | "needed";
  posture: "Knowledge" | "Watch" | "Review";
  reason: string;
  matchedProjects: string[];
  relevantModules: string[];
  matchType: "direct" | "analogous" | "reference_only" | "weak";
  evidenceBoundary: "source_supported" | "internal_judgment" | "unsupported";
  downstreamPosture: string;
  checklist: DeepProjectMatchChecklistItem[];
  suggestedReviewNote: string;
};

type DeepProjectMatchGeneratedAnalysis = {
  analysis_type?: string;
  reference_frame_version?: string;
  reference_frame_source_hint?: string;
  source_depth_tier?: string;
  analysis_mode?: string;
  hypothesis_status?: string;
  differentiated_insight_status?: string;
  narrative_summary?: string;
  signal_side_fact?: string;
  ai_radar_side_fact?: string;
  suspected_differentiated_insight?: string;
  concrete_relevance?: string;
  architecture_comparison?: string;
  borrow?: string;
  beware?: string;
  evidence_boundary?: string;
  decision_posture?: string;
  review_note?: string;
  review_note_effect?: string;
  needs_source_read?: boolean;
  source_claim_reading?: {
    source_read_depth?: string;
    source_claim_reliability?: string;
    summary?: string;
    claims?: Array<{
      source_claim?: string;
      source_assertion_type?: string;
      evidence_locator?: string;
      honesty_signals?: string[];
      inflation_signals?: string[];
      can_support_differentiated_insight?: boolean;
      limitation?: string;
    }>;
  };
  source_read_targets?: Array<{
    target_type?: string;
    url?: string;
    path?: string;
    section_hint?: string;
    question?: string;
  }>;
  evidence_basis?: string;
  structured_checklist?: Array<{
    label?: string;
    value?: string;
    status?: "ok" | "watch" | "risk" | string;
  }>;
  limitations?: string[];
  verification_effect?: string;
  allowed_downstream_effect?: string;
  provider_used?: string;
  model_used?: string;
  route_task_type?: string;
};

type InsightLike = {
  id?: string;
  signal_id?: string;
  title?: string;
  signal_title?: string;
  summary?: string;
  signal_summary?: string;
  source?: string;
  published_at?: string | null;
  collected_at?: string | null;
  status?: string;
  saved_reason?: string | null;
  starred?: boolean;
  starred_at?: string | null;
  url?: string | null;
  link?: string | null;
  source_url?: string | null;
  source_excerpt?: string;
  source_excerpt_length?: number | null;
  source_stated_limits?: StructuredValue;
  source_stated_confidence?: StructuredValue;
  source_stated_limits_not_applicable?: boolean;
  source_stated_limits_status?: string;

  topic?: string;
  insight_status?: string;
  insight_status_label?: string;
  processing_bucket?: string;

  why_it_matters?: StructuredValue;
  relevance_to_projects?: StructuredValue;
  relevance_to_career?: StructuredValue;
  synthesized_insight?: StructuredValue;
  insight?: StructuredValue;
  strategy?: StructuredValue;
  is_manual?: boolean;
  manual_session_id?: string;
  upload_reason?: string;
  intended_use?: string;
  cognitive_layer?: string;
  analysis_status?: string;
  workspace_saved?: boolean;
  workspace_file_name?: string;
  workspace_saved_at?: string;
  subscription_score_percent?: number | null;
  subscription_topic_priority?: string;
  subscription_project_links?: Array<{
    project_id?: string;
    topic_keywords?: string[];
    matched_keywords?: string[];
  }>;
  projects?: string[];
  project_links?: Array<{
    project_id?: string;
    name?: string;
    status?: string;
    score?: number;
  }>;
  auto_action_hint?: string;
  provider_used?: string;
  model_used?: string;
  produced_by_model?: ModelProvenance | null;
  generation_mode?: string;
  requested_provider?: string;
  verification?: {
    verified_insight?: {
      id?: string;
      status?: string;
      evidence?: {
        level?: string;
        score?: number;
        pack_id?: string | null;
        summary_provenance?: string;
        reason_codes?: string[];
      };
      claims?: {
        count?: number;
        support_summary?: Record<string, number>;
        unsupported_or_contradicted_count?: number;
        inferred_count?: number;
        items?: ClaimCheckItem[];
      };
      confidence?: {
        score?: number | null;
        label?: string | null;
        reason?: string[];
      };
      action_policy?: {
        allowed?: string[];
        blocked?: string[];
      };
      downgrade?: {
        applied?: boolean;
        reason?: string | null;
      };
      limitations?: string[];
      produced_by_model?: ModelProvenance | null;
    };
    produced_by_model?: ModelProvenance | null;
    evidence_quality?: {
      level?: string;
      score?: number;
      notes?: string[];
      is_thin_signal?: boolean;
      summary_provenance?: string;
      summary_weight_applied?: number;
      reason_codes?: string[];
    };
    low_evidence_gate?: {
      output_mode?: string;
      max_confidence?: number;
      decision_card_allowed?: boolean | string;
      required_uncertainty_notes?: string[];
    };
    verification_status?: string;
    allowed_downstream_actions?: string[];
    blocked_downstream_actions?: string[];
    confidence_score?: number;
    confidence_label?: string;
    uncertainty_boundaries?: string[];
    limitations?: string[];
    downgrade_reason?: string | null;
    claim_support_summary?: Record<string, number>;
    claim_results?: ClaimCheckItem[];
  };
  policy_metadata?: {
    notes?: string[];
    verification?: InsightLike["verification"];
  };
  evidence_pack?: Record<string, unknown>;
  decision_trace?: DecisionTraceEvent[];
  files?: Array<{
    original_filename?: string;
    stored_filename?: string;
    file_kind?: string;
    preview_text?: string;
    message?: string;
  }>;
  file_count?: number;
  file_types?: string[];
};

type ManualSessionLike = {
  session_id?: string;
  title?: string;
  created_at?: string;
  updated_at?: string;
  status?: string;
  saved_reason?: string | null;
  analysis_status?: string;
  completion_saved?: boolean;
  workspace_saved?: boolean;
  topic?: string;
  summary?: string;
  provider_used?: string;
  model_used?: string;
  generation_mode?: string;
  requested_provider?: string;
  produced_by_model?: ModelProvenance | null;
  verification?: InsightLike["verification"];
  policy_metadata?: InsightLike["policy_metadata"];
  evidence_pack?: Record<string, unknown>;
  why_it_matters?: StructuredValue;
  relevance_to_projects?: StructuredValue;
  relevance_to_career?: StructuredValue;
  synthesized_insight?: StructuredValue;
  subscription_project_links?: Array<{
    project_id?: string;
    topic_keywords?: string[];
    matched_keywords?: string[];
  }>;
  analysis?: {
    summary?: StructuredValue;
    why_it_matters?: StructuredValue;
    relevance_to_projects?: StructuredValue;
    relevance_to_career?: StructuredValue;
    synthesized_insight?: StructuredValue;
    topic?: string;
  } | null;
  is_manual?: boolean;
  upload_reason?: string;
  intended_use?: string;
  cognitive_layer?: string;
  files?: Array<{
    original_filename?: string;
    stored_filename?: string;
    file_kind?: string;
    preview_text?: string;
    message?: string;
  }>;
  file_count?: number;
  file_types?: string[];
};

type ManualSessionsResponse = {
  sessions?: ManualSessionLike[];
  items?: ManualSessionLike[];
};

type ManualSessionDetailResponse = {
  session?: ManualSessionLike | null;
};

type ManualFilePreviewResponse = {
  preview_text?: string;
  preview_available?: boolean;
  message?: string;
};

type SignalDetailResponse = InsightLike;

type LifecycleProbeStep = {
  step_id?: string;
  label?: string;
  state?: string;
  provenance?: "direct" | "derived" | "inferred" | "missing" | string;
  source?: string;
  timestamp?: string;
  actor?: string;
  detail?: string;
  support?: Record<string, unknown>;
  gaps?: string[];
};

type SignalLifecycleProbe = {
  adapter?: string;
  contract_version?: string;
  authoritative?: boolean;
  signal_id?: string;
  title?: string;
  status?: string;
  steps?: LifecycleProbeStep[];
  gap_report?: {
    direct_fields?: string[];
    service_outputs_not_persisted?: string[];
    architecture_gaps?: string[];
  };
  project_context?: {
    review_records_count?: number;
    calibration_events_count?: number;
  };
  detail?: string;
  message?: string;
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
  total_count?: number;
  reflections?: RelatedReflection[];
  signal_topics?: string[];
};

type ProjectTakeawayCandidate = {
  signal_id?: string;
  signal_refs?: string[];
  project_id?: string;
  project_name?: string;
  status?: string;
  review_outcome?: string;
  watch_status?: string;
  action_completed_at?: string;
  candidate_source?: string;
  verification_metadata?: {
    confirmed_final_takeaway?: boolean;
    candidate_requested_from?: string;
    final_takeaway_id?: string;
    review_bundle_snapshot_id?: string;
    source_signal_id?: string;
    signal_id?: string;
  };
};

type ProjectTakeawayCandidatesResponse = {
  items?: ProjectTakeawayCandidate[];
};

type ReviewBundleSnapshotsResponse = {
  items?: ReviewBundleSnapshot[];
};

type FinalTakeawaysResponse = {
  items?: FinalTakeawayArtifact[];
};

type ExternalSynthesisSourcesResponse = {
  items?: ExternalSynthesisSource[];
};

type GenerateInsightResponse = {
  detail?: string;
  message?: string;
  signal_id?: string;
  id?: string;
  is_manual?: boolean;
  manual_session_id?: string;
  upload_reason?: string;
  intended_use?: string;
  cognitive_layer?: string;
  analysis_status?: string;
  insight_status?: string;
  insight_status_label?: string;
  workspace_saved?: boolean;
  workspace_file_name?: string;
  workspace_saved_at?: string;
  file_count?: number;
  file_types?: string[];
  files?: InsightLike["files"];
  status?: string;
  summary?: string;
  why_it_matters?: string;
  relevance_to_projects?: string;
  relevance_to_career?: string;
  synthesized_insight?: string;
  provider_used?: string;
  model_used?: string;
  produced_by_model?: ModelProvenance | null;
  generation_mode?: string;
  requested_provider?: string;
  verification?: InsightLike["verification"];
  policy_metadata?: InsightLike["policy_metadata"];
  evidence_pack?: InsightLike["evidence_pack"];
};

type DeepMatchAnalysisResponse = {
  detail?: string;
  message?: string;
  signal_id?: string;
  generated_at?: string;
  analysis?: DeepProjectMatchGeneratedAnalysis;
  verification_effect?: string;
  allowed_downstream_effect?: string;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function needsPdfPreviewHydration(file: NonNullable<InsightLike["files"]>[number]): boolean {
  return (
    file.file_kind === "pdf" &&
    Boolean(file.stored_filename) &&
    (!file.preview_text || file.preview_text.trim() === PDF_PREVIEW_PENDING_MESSAGE)
  );
}

function getErrorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}

function inferExternalSynthesisKind(fileName: string) {
  const lower = fileName.toLowerCase();
  if (lower.endsWith(".html") || lower.endsWith(".htm")) return "external_html";
  if (lower.endsWith(".md") || lower.endsWith(".markdown")) return "external_markdown";
  if (lower.endsWith(".txt")) return "external_plaintext";
  return "paste";
}

async function readApiResponse(res: Response): Promise<Record<string, unknown>> {
  const text = await res.text();
  if (!text) return {};

  try {
    const parsed = JSON.parse(text);
    return isRecord(parsed) ? parsed : {};
  } catch {
    return { message: text };
  }
}

function buildJsonAdminHeaders(): HeadersInit {
  return {
    "Content-Type": "application/json",
    ...buildAdminAuthHeaders(),
  };
}

function buildDefaultClaimFeedbackDraft(overrides: Partial<ClaimFeedbackDraft> = {}): ClaimFeedbackDraft {
  return {
    open: false,
    reasonSlot: "reasoning_gap",
    note: "",
    submitting: false,
    submitted: false,
    message: "",
    error: "",
    ...overrides,
  };
}

function projectCandidateMatchesSignal(item: ProjectTakeawayCandidate, signalId: string): boolean {
  const normalizedSignalId = String(signalId || "").trim();
  if (!normalizedSignalId) return false;
  const verification = item.verification_metadata || {};
  const signalRefs = Array.isArray(item.signal_refs) ? item.signal_refs : [];
  return (
    String(item.signal_id || "").trim() === normalizedSignalId ||
    String(verification.signal_id || "").trim() === normalizedSignalId ||
    String(verification.source_signal_id || "").trim() === normalizedSignalId ||
    signalRefs.some((ref) => String(ref || "").trim() === normalizedSignalId)
  );
}

function projectCandidateMatchesFinalTakeaway(
  item: ProjectTakeawayCandidate,
  signalId: string,
  finalTakeawayId = ""
): boolean {
  const verification = item.verification_metadata || {};
  const normalizedFinalTakeawayId = String(finalTakeawayId || "").trim();
  if (
    normalizedFinalTakeawayId &&
    String(verification.final_takeaway_id || "").trim() === normalizedFinalTakeawayId
  ) {
    return true;
  }
  if (!projectCandidateMatchesSignal(item, signalId)) return false;
  return (
    Boolean(verification.confirmed_final_takeaway) ||
    String(verification.candidate_requested_from || "").trim() === "confirmed_final_takeaway" ||
    String(item.candidate_source || "").trim() === "confirmed_final_takeaway"
  );
}

function getClaimFeedbackKey(claim: ClaimCheckItem, index: number): string {
  return claim.claim_id || `${claim.claim_type || "claim"}-${index}`;
}

function getClaimFeedbackRecordId(claim: ClaimCheckItem, index: number): string {
  return claim.claim_id || `claim-${index + 1}`;
}

function parseOptionalDate(value?: string | null): Date | null {
  const text = String(value || "").trim();
  if (!text) return null;
  const date = new Date(text);
  return Number.isNaN(date.getTime()) ? null : date;
}

function buildSignalInputProvenanceSnapshot(signal: InsightLike | null): Record<string, unknown> {
  const capturedAt = new Date();
  const publishedAt = signal?.published_at || "";
  const collectedAt = signal?.collected_at || "";
  const timestampText = publishedAt || collectedAt;
  const timestamp = parseOptionalDate(timestampText);
  const staleFlags: string[] = [];
  if (timestampText && !timestamp) {
    staleFlags.push("signal_timestamp_invalid");
  } else if (timestamp && capturedAt.getTime() - timestamp.getTime() > 30 * 24 * 60 * 60 * 1000) {
    staleFlags.push("signal_timestamp_stale");
  }

  const sourceExcerptLength =
    typeof signal?.source_excerpt_length === "number"
      ? signal.source_excerpt_length
      : typeof signal?.source_excerpt === "string"
        ? signal.source_excerpt.length
        : 0;

  return {
    schema_version: 1,
    captured_at: capturedAt.toISOString(),
    signal: {
      published_at: publishedAt,
      collected_at: collectedAt,
      source_excerpt_length: Math.max(0, sourceExcerptLength || 0),
    },
    user_context: {
      context_scope: "signal_detail_claim_review",
      captured_at: "",
    },
    project_context: {
      repo_snapshot_scanned_at: "",
      repo_snapshot_status: "",
    },
    project_context_cache: {
      fetched_at: "",
      ttl_hours: 12,
    },
    freshness: {
      stale_flags: staleFlags,
      freshness_penalty: Math.min(0.4, staleFlags.length * 0.1),
      summary: staleFlags.length ? `Stale input detected: ${staleFlags.join(", ")}.` : "No stale signal timestamp detected.",
    },
  };
}

function formatDateTime(value?: string | null) {
  if (!value) return "N/A";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

function normalizeStatus(status?: string) {
  const value = (status || "pending").toLowerCase();
  if (value === "saved" || value === "analyzed" || value === "completed" || value === "rejected") {
    return value;
  }
  return "pending";
}

function getStatusStyle(status?: string) {
  switch (normalizeStatus(status)) {
    case "analyzed":
      return {
        background: "var(--app-info-bg)",
        color: "var(--app-info-fg)",
        border: "1px solid var(--app-info-border)",
      };
    case "completed":
      return {
        background: "var(--app-success-bg)",
        color: "var(--app-success-fg)",
        border: "1px solid var(--app-success-border)",
      };
    case "rejected":
      return {
        background: "var(--app-danger-bg)",
        color: "var(--app-danger-fg)",
        border: "1px solid var(--app-danger-border)",
      };
    case "saved":
      return {
        background: "var(--app-warning-bg)",
        color: "var(--app-warning-fg)",
        border: "1px solid var(--app-warning-border)",
      };
    default:
      return {
        background: "var(--app-chip-bg)",
        color: "var(--app-chip-fg)",
        border: "1px solid var(--app-chip-border)",
      };
  }
}

function getStatusLabel(status?: string) {
  switch (normalizeStatus(status)) {
    case "saved":
      return "Saved";
    case "analyzed":
      return "Analyzed";
    case "completed":
      return "Completed";
    case "rejected":
      return "Rejected";
    default:
      return "Pending";
  }
}

function syncSignalsListCacheStatus(signalId: string, nextStatus: string) {
  if (typeof window === "undefined") return;

  try {
    const raw = sessionStorage.getItem(SIGNALS_CACHE_KEY);
    if (!raw) return;

    const parsed = JSON.parse(raw);
    const payload = parsed?.payload;
    if (!payload || !Array.isArray(payload.signals) || !Array.isArray(payload.manualSignals)) return;

    const normalized = normalizeStatus(nextStatus);
    const updateOne = (item: Record<string, unknown>) => {
      const itemId = String(item.signal_id || item.id || "");
      if (itemId !== signalId) return item;
      return {
        ...item,
        status: normalized,
      };
    };

    const nextSignals = payload.signals.map(updateOne);
    const nextManualSignals = payload.manualSignals.map(updateOne);

    const buildCounts = (items: Array<Record<string, unknown>>) => {
      const counts = { all: items.length, pending: 0, saved: 0, analyzed: 0, completed: 0, rejected: 0 };
      for (const item of items) {
        const status = normalizeStatus(String(item.status || "pending"));
        counts[status] += 1;
      }
      return counts;
    };

    const mergedCounts = buildCounts([...nextSignals, ...nextManualSignals]);
    sessionStorage.setItem(
      SIGNALS_CACHE_KEY,
      JSON.stringify({
        ...parsed,
        timestamp: Date.now(),
        payload: {
          ...payload,
          signals: nextSignals,
          manualSignals: nextManualSignals,
          counts: mergedCounts,
        },
      })
    );
  } catch {
    // ignore cache sync errors
  }
}

function syncSignalsListCacheStar(signalId: string, starred: boolean, starredAt?: string | null) {
  if (typeof window === "undefined") return;

  try {
    const raw = sessionStorage.getItem(SIGNALS_CACHE_KEY);
    if (!raw) return;

    const parsed = JSON.parse(raw);
    const payload = parsed?.payload;
    if (!payload || !Array.isArray(payload.signals) || !Array.isArray(payload.manualSignals)) return;

    const updateOne = (item: Record<string, unknown>) => {
      const itemId = String(item.signal_id || item.id || "");
      if (itemId !== signalId) return item;
      return {
        ...item,
        starred,
        starred_at: starred ? starredAt || item.starred_at || new Date().toISOString() : null,
      };
    };

    sessionStorage.setItem(
      SIGNALS_CACHE_KEY,
      JSON.stringify({
        ...parsed,
        timestamp: Date.now(),
        payload: {
          ...payload,
          signals: payload.signals.map(updateOne),
          manualSignals: payload.manualSignals.map(updateOne),
        },
      })
    );
  } catch {
    // ignore cache sync errors
  }
}

function invalidateSignalsListCache() {
  if (typeof window === "undefined") return;

  try {
    sessionStorage.removeItem(SIGNALS_CACHE_KEY);
  } catch {
    // ignore cache invalidation errors
  }
}

function findCachedSignalDetail(signalId: string): InsightLike | null {
  if (typeof window === "undefined" || !signalId) return null;

  try {
    const raw = sessionStorage.getItem(SIGNALS_CACHE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    const payload = parsed?.payload;
    const candidates = [
      ...(Array.isArray(payload?.signals) ? payload.signals : []),
      ...(Array.isArray(payload?.manualSignals) ? payload.manualSignals : []),
    ] as InsightLike[];

    return candidates.find((item) => {
      const itemId = String(item.signal_id || item.id || "");
      return itemId === signalId;
    }) || null;
  } catch {
    return null;
  }
}

function safeText(value: StructuredValue, fallback = "") {
  if (value === null || value === undefined) return fallback;
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return fallback;
  }
}

function normalizedDisplayText(value: StructuredValue, fallback = "") {
  return safeText(stripUncertainPrefix(value), fallback);
}

function formatEvidenceReason(code: string): string {
  switch (code) {
    case "missing_title":
      return "Title metadata is missing.";
    case "missing_summary":
      return "No summary text was available.";
    case "short_summary":
      return "The available summary is very short.";
    case "llm_generated_summary_downweighted":
      return "The summary appears to be LLM-generated, so it was downweighted.";
    case "unknown_summary_provenance_downweighted":
      return "The summary source is unknown, so it was downweighted.";
    case "collector_summary_slightly_downweighted":
      return "The summary comes from collector-level extraction, so it was slightly downweighted.";
    case "source_excerpt_summary":
      return "The summary looks like a direct source excerpt.";
    case "manual_summary_context":
      return "The summary comes from user-provided manual context.";
    case "high_source_reliability":
      return "The source type is currently treated as high reliability.";
    case "medium_source_reliability":
      return "The source type is currently treated as medium reliability.";
    case "unknown_source_reliability":
      return "The source reliability is unknown.";
    case "has_source_url":
      return "A source URL is present.";
    case "missing_source_url":
      return "No source URL was available.";
    case "thin_signal_penalty_applied":
      return "A thin-signal penalty was applied because the available evidence is limited.";
    default:
      return code.replace(/_/g, " ");
  }
}

function formatSummaryProvenance(value?: string): string {
  switch (String(value || "").toLowerCase()) {
    case "source_excerpt":
      return "Source excerpt";
    case "collector_extracted":
      return "Collector extracted";
    case "llm_generated":
      return "LLM generated";
    case "manual_user_written":
      return "Manual user written";
    default:
      return "Unknown";
  }
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
      break;
  }
  return normalized
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function relationshipReviewRequired(annotation?: RelationshipAnnotation | null): boolean {
  const posture = String(annotation?.support_posture || "").toLowerCase();
  return posture === "proposed" || posture === "needs_review";
}

function getRelationshipAnnotationStyle(annotation?: RelationshipAnnotation | null): { background: string; border: string; color: string } {
  if (relationshipReviewRequired(annotation)) {
    return { background: "var(--app-warning-bg)", border: "1px solid var(--app-warning-border)", color: "var(--app-warning-fg)" };
  }
  switch (String(annotation?.support_posture || "").toLowerCase()) {
    case "confirmed":
      return { background: "var(--app-success-bg)", border: "1px solid var(--app-success-border)", color: "var(--app-success-fg)" };
    case "rejected":
      return { background: "var(--app-danger-bg)", border: "1px solid var(--app-danger-border)", color: "var(--app-danger-fg)" };
    default:
      return { background: "var(--app-surface-muted-bg)", border: "1px solid var(--app-surface-border)", color: "var(--app-text-muted)" };
  }
}

function hasRelationshipAnnotation(annotation?: RelationshipAnnotation | null): annotation is RelationshipAnnotation {
  return Boolean(annotation && typeof annotation === "object" && annotation.relation_type);
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

function resolveModelProvenance(...candidates: Array<ModelProvenance | null | undefined>): ModelProvenance {
  return candidates.find((candidate) => candidate && typeof candidate === "object") || {
    provenance_schema_version: 0,
    provenance_completeness: "legacy",
  };
}

function formatModelProvenance(provenance: ModelProvenance): string {
  if (provenance.provenance_schema_version !== 1) {
    return "Legacy/v0 provenance";
  }
  const provider = provenance.provider || "provider unknown";
  const model = provenance.model_id || "model unknown";
  const route = provenance.route_key || provenance.task_type || "route unknown";
  const fingerprint = provenance.deterministic_fingerprint
    ? ` | fp ${provenance.deterministic_fingerprint.slice(0, 8)}`
    : "";
  return `${provider} / ${model} / ${route}${fingerprint}`;
}

function formatClaimSupportSummary(summary: Record<string, number>): string {
  const entries = Object.entries(summary).filter(([, count]) => count > 0);
  if (entries.length === 0) return "";
  return entries
    .map(([supportLevel, count]) => `${formatCompactLabel(supportLevel)}: ${count}`)
    .join(" | ");
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

function getClaimSupportStyle(value?: string): { background: string; border: string; color: string } {
  switch (String(value || "").toLowerCase()) {
    case "contradicted":
    case "unsupported":
      return { background: "var(--app-danger-bg)", border: "1px solid var(--app-danger-border)", color: "var(--app-danger-fg)" };
    case "inferred":
      return { background: "var(--app-warning-bg)", border: "1px solid var(--app-warning-border)", color: "var(--app-warning-fg)" };
    case "partially_supported":
      return { background: "var(--app-warning-bg)", border: "1px solid var(--app-warning-border)", color: "var(--app-warning-fg)" };
    case "directly_supported":
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
  return getClaimSupportStyle(claim.support_level);
}

function getClaimDisplayTypeLabel(claim: ClaimCheckItem): string {
  return isProjectRelevanceClaim(claim) ? "Project relevance judgment" : formatCompactLabel(claim.claim_type);
}

function getClaimDisplaySupportLabel(claim: ClaimCheckItem): string {
  return isProjectRelevanceClaim(claim) ? "Internal judgment" : formatCompactLabel(claim.support_level);
}

function getPresentationFidelityStyle(state?: string): { background: string; border: string; color: string } {
  switch (String(state || "").toLowerCase()) {
    case "limits_present_and_exceeded":
      return { background: "var(--app-danger-bg)", border: "1px solid var(--app-danger-border)", color: "var(--app-danger-fg)" };
    case "limits_present_and_preserved":
      return { background: "var(--app-success-bg)", border: "1px solid var(--app-success-border)", color: "var(--app-success-fg)" };
    case "limits_absent_unknown":
      return { background: "var(--app-warning-bg)", border: "1px solid var(--app-warning-border)", color: "var(--app-warning-fg)" };
    case "limits_not_applicable":
      return { background: "var(--app-surface-muted-bg)", border: "1px solid var(--app-surface-border)", color: "var(--app-text-muted)" };
    default:
      return { background: "var(--app-surface-bg)", border: "1px solid var(--app-surface-border)", color: "var(--app-text-muted)" };
  }
}

function getPresentationFidelityLabel(state?: string): string {
  switch (String(state || "").toLowerCase()) {
    case "limits_present_and_exceeded":
      return "Source limit exceeded";
    case "limits_present_and_preserved":
      return "Source limits preserved";
    case "limits_absent_unknown":
      return "Source limits coverage gap";
    case "limits_not_applicable":
      return "Source limits not applicable";
    default:
      return "Presentation fidelity unknown";
  }
}

function getPresentationFidelityDetail(state?: string): string {
  switch (String(state || "").toLowerCase()) {
    case "limits_present_and_exceeded":
      return "Claim wording appears stronger than the recorded source-stated limits.";
    case "limits_present_and_preserved":
      return "Claim wording stays within the recorded source-stated limits.";
    case "limits_absent_unknown":
      return "No source-stated limits metadata was recorded. This is a coverage gap, not a fidelity failure.";
    case "limits_not_applicable":
      return "This evidence item explicitly marked source-stated limits as not applicable.";
    default:
      return "No presentation-fidelity state is available for this claim.";
  }
}

function shouldShowPresentationFidelityDetail(state?: string): boolean {
  return ["limits_present_and_exceeded", "limits_absent_unknown"].includes(String(state || "").toLowerCase());
}

type PresentationFidelitySummary = {
  total: number;
  exceeded: number;
  preserved: number;
  absentUnknown: number;
  notApplicable: number;
};

function getPresentationFidelitySummary(claims: ClaimCheckItem[]): PresentationFidelitySummary {
  const counts = {
    total: 0,
    exceeded: 0,
    preserved: 0,
    absentUnknown: 0,
    notApplicable: 0,
  };

  for (const claim of claims) {
    const state = String(claim.presentation_fidelity?.limits_state || "").toLowerCase();
    if (!state) continue;
    counts.total += 1;
    if (state === "limits_present_and_exceeded") counts.exceeded += 1;
    if (state === "limits_present_and_preserved") counts.preserved += 1;
    if (state === "limits_absent_unknown") counts.absentUnknown += 1;
    if (state === "limits_not_applicable") counts.notApplicable += 1;
  }

  return counts;
}

function getSourceLimitsRecordStyle(status?: string): { background: string; border: string; color: string } {
  const normalized = String(status || "").toLowerCase();
  if (normalized === "limits_present") {
    return { background: "var(--app-success-bg)", border: "1px solid var(--app-success-border)", color: "var(--app-success-fg)" };
  }
  if (normalized === "limits_not_applicable") {
    return { background: "var(--app-surface-muted-bg)", border: "1px solid var(--app-surface-border)", color: "var(--app-text-muted)" };
  }
  return { background: "var(--app-warning-bg)", border: "1px solid var(--app-warning-border)", color: "var(--app-warning-fg)" };
}

function getSourceLimitsRecordLabel(status?: string): string {
  switch (String(status || "").toLowerCase()) {
    case "limits_present":
      return "Source limits recorded";
    case "limits_not_applicable":
      return "Source limits not applicable";
    case "limits_absent_unknown":
      return "Source limits not recorded";
    default:
      return "Source limits not recorded";
  }
}

function getSourceLimitsRecordDetail(status?: string): string {
  switch (String(status || "").toLowerCase()) {
    case "limits_present":
      return "Recorded source-side caveats are available for presentation-fidelity checks.";
    case "limits_not_applicable":
      return "The source was explicitly marked as not needing source-stated limits.";
    case "limits_absent_unknown":
      return "No source-stated limits metadata was recorded. This is a coverage gap, not a source-quality failure.";
    default:
      return "No source-stated limits metadata was recorded. This is a coverage gap, not a source-quality failure.";
  }
}

function getSourceLimitsRecord(
  insight: InsightLike | null,
  summary: PresentationFidelitySummary
) {
  const rawStatus = String(insight?.source_stated_limits_status || "").trim().toLowerCase();
  const text = normalizedDisplayText(insight?.source_stated_limits, "");
  const confidence = normalizedDisplayText(insight?.source_stated_confidence, "");
  const status =
    rawStatus ||
    (insight?.source_stated_limits_not_applicable
      ? "limits_not_applicable"
      : text
        ? "limits_present"
        : "limits_absent_unknown");
  const style = getSourceLimitsRecordStyle(status);

  return {
    status,
    label: getSourceLimitsRecordLabel(status),
    detail: getSourceLimitsRecordDetail(status),
    text,
    confidence,
    style,
    shouldShow:
      Boolean(text || confidence || insight?.source_stated_limits_not_applicable) ||
      summary.total > 0,
  };
}

function buildProjectReviewVerifiedInsightFallback({
  existing,
  signalId,
  verificationStatus,
  evidenceLevel,
  evidenceQuality,
  claimResults,
  claimSupportSummary,
  confidenceScore,
  confidenceLabel,
  allowedActions,
  blockedActions,
  downgradeReason,
  limitations,
  producedByModel,
}: {
  existing?: NonNullable<InsightLike["verification"]>["verified_insight"];
  signalId: string;
  verificationStatus?: string;
  evidenceLevel?: string;
  evidenceQuality?: InsightLike["verification"] extends infer Verification
    ? Verification extends { evidence_quality?: infer EvidenceQuality }
      ? EvidenceQuality
      : never
    : never;
  claimResults: ClaimCheckItem[];
  claimSupportSummary: Record<string, number>;
  confidenceScore?: number | null;
  confidenceLabel?: string | null;
  allowedActions: string[];
  blockedActions: string[];
  downgradeReason?: string | null;
  limitations: string[];
  producedByModel?: ModelProvenance | null;
}) {
  if (existing) return existing;
  if (claimResults.length === 0) return null;

  const normalizedStatus = verificationStatus || "unknown";
  const unsupportedOrContradictedCount = claimResults.filter((claim) =>
    ["unsupported", "contradicted"].includes(String(claim.support_level || "").toLowerCase())
  ).length;
  const inferredCount = claimResults.filter(
    (claim) => String(claim.support_level || "").toLowerCase() === "inferred"
  ).length;

  return {
    id: "",
    signal_id: signalId,
    schema_version: 1,
    version: "v1",
    generation_mode: "project_review_metadata_fallback",
    status: normalizedStatus,
    evidence: {
      level: evidenceLevel || evidenceQuality?.level || "unknown",
      score: evidenceQuality?.score,
      pack_id: null,
      summary_provenance: evidenceQuality?.summary_provenance,
      reason_codes: evidenceQuality?.reason_codes || [],
    },
    claims: {
      count: claimResults.length,
      support_summary: claimSupportSummary,
      unsupported_or_contradicted_count: unsupportedOrContradictedCount,
      inferred_count: inferredCount,
      items: claimResults,
    },
    confidence: {
      score: typeof confidenceScore === "number" ? confidenceScore : null,
      label: confidenceLabel || null,
      reason: [],
    },
    action_policy: {
      allowed: allowedActions,
      blocked: blockedActions,
    },
    downgrade: {
      applied: Boolean(downgradeReason),
      reason: downgradeReason || null,
    },
    limitations,
    produced_by_model: producedByModel?.provenance_schema_version === 1 ? producedByModel : null,
  };
}

function uniqueCleanValues(values: Array<string | undefined | null>): string[] {
  const seen = new Set<string>();
  const result: string[] = [];
  for (const raw of values) {
    const value = String(raw || "").trim();
    if (!value || seen.has(value.toLowerCase())) continue;
    seen.add(value.toLowerCase());
    result.push(value);
  }
  return result;
}

function extractMatchedProjectNames(signal: InsightLike | null, projectText: string): string[] {
  const linkNames = (signal?.project_links || []).map((item) => item.name || item.project_id);
  const subscriptionNames = (signal?.subscription_project_links || []).map((item) => item.project_id);
  const directNames = Array.isArray(signal?.projects) ? signal.projects : [];
  const detectedNames: string[] = [];
  const lower = projectText.toLowerCase();
  [
    ["AI Radar", ["ai radar", "strategic intelligence", "project takeaway", "review loop"]],
    ["Trajectory Memory", ["trajectory memory", "trajectory"]],
    ["GLAP", ["glap", "supply chain", "logistics"]],
    ["AI Cognitive OS", ["cognitive os", "cognition", "reflection"]],
  ].forEach(([name, terms]) => {
    if ((terms as string[]).some((term) => lower.includes(term))) detectedNames.push(name as string);
  });
  return uniqueCleanValues([...linkNames, ...directNames, ...subscriptionNames, ...detectedNames])
    .map((value) => (value === "ai_radar" ? "AI Radar" : value));
}

function inferRelevantModules(text: string): string[] {
  const lower = text.toLowerCase();
  const modules: Array<[string, string[]]> = [
    ["Project Takeaway Review Loop", ["project takeaway", "review loop", "decision -> review", "decision review", "review inbox"]],
    ["Reflection Index", ["reflection", "reflections", "cognitive layer"]],
    ["Trajectory / Learning History", ["trajectory", "learning loop", "calibration", "reviewrecord", "review record"]],
    ["Knowledge / Strategic Synthesis", ["knowledge", "strategic synthesis", "strategic intelligence", "convergence"]],
    ["Agent Watch", ["agent watch", "coding agent", "claude code", "codex", "agent memory"]],
    ["Skill / Harness Management", ["skill", "skills", "harness", "prompt registry", "agent protocol"]],
    ["Verification / Evidence Gates", ["verification", "evidence", "claim", "unsupported", "blocked_downstream_actions"]],
  ];
  return modules
    .filter(([, terms]) => terms.some((term) => lower.includes(term)))
    .map(([label]) => label);
}

function compactDisplayText(value: string, maxLength = 360): string {
  const text = value.replace(/\s+/g, " ").trim();
  if (text.length <= maxLength) return text;
  return `${text.slice(0, maxLength - 3).trim()}...`;
}

const AI_RADAR_MODULE_RELEVANCE: Record<string, string> = {
  "Project Takeaway Review Loop":
    "AI Radar turns signals into project takeaway candidates, then requires human Review before Confirm, Watch, Reject, or Action.",
  "Reflection Index":
    "AI Radar uses reflections as cognitive context, but keeps them separate from external factual evidence.",
  "Trajectory / Learning History":
    "AI Radar records ReviewRecord and CalibrationEvent history so later judgments can learn from prior decisions.",
  "Knowledge / Strategic Synthesis":
    "AI Radar pairs signals into Knowledge / Strategic Synthesis context before deciding whether a project review is justified.",
  "Agent Watch":
    "AI Radar tracks agent ecosystem movements as supply-side signals that may inform project direction.",
  "Skill / Harness Management":
    "AI Radar treats agent skills, prompt registry, and harness discipline as governed development-time capabilities.",
  "Verification / Evidence Gates":
    "AI Radar blocks low-risk Action and strong recommendations when claim support or source evidence is thin.",
};

function buildAiRadarSpecificRelation({
  projectText,
  strategicText,
  relevantModules,
  matchType,
}: {
  projectText: string;
  strategicText: string;
  relevantModules: string[];
  matchType: DeepProjectMatchReview["matchType"];
}): string {
  const projectExcerpt = compactDisplayText(projectText, 420);
  const strategicExcerpt = compactDisplayText(strategicText, 260);
  const moduleReasons = relevantModules
    .map((moduleName) => AI_RADAR_MODULE_RELEVANCE[moduleName])
    .filter(Boolean)
    .slice(0, 3);
  const sourceText = projectExcerpt || strategicExcerpt;
  const relationParts: string[] = [];

  if (sourceText) {
    relationParts.push(`Project relevance text: ${sourceText}`);
  }
  if (moduleReasons.length > 0) {
    relationParts.push(`Concrete AI Radar comparison: ${moduleReasons.join(" ")}`);
  }
  relationParts.push(
    matchType === "analogous"
      ? "Review question: is this only an analogy to AI Radar's loop, or does it reveal a design pattern AI Radar should adopt or avoid?"
      : "Review question: which exact AI Radar module would change if this signal is accepted?"
  );

  return relationParts.join(" ");
}

function buildDeepProjectMatchReview({
  signal,
  projectText,
  strategicText,
  claimResults,
  evidenceLevel,
  blockedActions,
}: {
  signal: InsightLike | null;
  projectText: string;
  strategicText: string;
  claimResults: ClaimCheckItem[];
  evidenceLevel: string;
  blockedActions: string[];
}): DeepProjectMatchReview {
  const combinedText = `${projectText}\n${strategicText}`;
  const matchedProjects = extractMatchedProjectNames(signal, combinedText);
  const hasProjectText = Boolean(projectText.trim() || strategicText.trim() || matchedProjects.length > 0);
  const projectClaims = claimResults.filter(isProjectRelevanceClaim);
  const hasProjectRelevanceJudgment = projectClaims.length > 0;
  const unsupportedProjectJudgment = projectClaims.some((claim) =>
    ["unsupported", "contradicted"].includes(String(claim.support_level || "").toLowerCase())
  );
  const inferredProjectJudgment = projectClaims.some((claim) =>
    String(claim.support_level || "").toLowerCase() === "inferred"
  );
  const projectJudgmentWithoutSourceRefs = projectClaims.some(
    (claim) => !Array.isArray(claim.evidence_refs) || claim.evidence_refs.length === 0
  );
  const thinEvidence = ["thin", "insufficient", "weak"].includes(String(evidenceLevel || "").toLowerCase());
  const actionBlocked = blockedActions.includes("low_risk_action_candidate") ||
    blockedActions.includes("strong_recommendation");

  if (!hasProjectText) {
    return {
      required: false,
      status: "not_project_related",
      posture: "Knowledge",
      reason: "No project relevance text or matched project is present.",
      matchedProjects: [],
      relevantModules: [],
      matchType: "weak",
      evidenceBoundary: "unsupported",
      downstreamPosture: "Keep as ordinary signal context.",
      checklist: [],
      suggestedReviewNote: "",
    };
  }

  const required = hasProjectRelevanceJudgment || thinEvidence || unsupportedProjectJudgment || inferredProjectJudgment || actionBlocked;
  const evidenceBoundary: DeepProjectMatchReview["evidenceBoundary"] = unsupportedProjectJudgment || projectJudgmentWithoutSourceRefs
    ? "internal_judgment"
    : inferredProjectJudgment || thinEvidence
      ? "internal_judgment"
      : "source_supported";
  const relevantModules = inferRelevantModules(combinedText);
  const matchType: DeepProjectMatchReview["matchType"] =
    relevantModules.some((moduleName) => moduleName.includes("Review Loop") || moduleName.includes("Trajectory"))
      ? "analogous"
      : relevantModules.length > 0
        ? "reference_only"
        : "weak";
  const posture: DeepProjectMatchReview["posture"] = !required ? "Review" : actionBlocked || thinEvidence ? "Watch" : "Review";
  const downstreamPosture =
    posture === "Watch"
      ? "Use Watch or Review Inbox; keep low-risk Action blocked until a human deep match review confirms project fit."
      : "Project Review can proceed, but Confirm still requires human review of project fit and evidence boundaries.";
  const reason = required
    ? "Project relevance is present, but the current support is internal, inferred, thin, or action-limited."
    : "Project relevance and evidence look strong enough for normal Project Review.";
  const matchedProjectText = matchedProjects.length ? matchedProjects.join(", ") : "Unspecified project fit";
  const moduleText = relevantModules.length ? relevantModules.join(", ") : "No module identified yet";
  const aiRadarSpecificRelation = buildAiRadarSpecificRelation({
    projectText,
    strategicText,
    relevantModules,
    matchType,
  });
  const suggestedReviewNote = required
    ? `Deep match required: ${compactDisplayText(aiRadarSpecificRelation, 520)}`
    : `Project match looks reviewable for ${matchedProjectText}; confirm only after checking source evidence and module fit.`;

  return {
    required,
    status: required ? "needed" : "not_required",
    posture,
    reason,
    matchedProjects,
    relevantModules,
    matchType,
    evidenceBoundary,
    downstreamPosture,
    suggestedReviewNote,
    checklist: [
      {
        key: "matched_project",
        label: "Matched project",
        value: matchedProjectText,
        status: matchedProjects.length ? "ok" : "watch",
      },
      {
        key: "relevant_module",
        label: "Relevant module",
        value: moduleText,
        status: relevantModules.length ? "ok" : "watch",
      },
      {
        key: "signal_side_fact",
        label: "Signal-side fact",
        value: normalizedDisplayText(signal?.summary || signal?.signal_summary || signal?.title || "External signal needs source review."),
        status: "watch",
      },
      {
        key: "ai_radar_side_fact",
        label: "AI Radar-side fact",
        value: aiRadarSpecificRelation,
        status: relevantModules.length ? "ok" : "risk",
      },
      {
        key: "match_type",
        label: "Match type",
        value: formatCompactLabel(matchType),
        status: matchType === "weak" ? "risk" : "watch",
      },
      {
        key: "evidence_boundary",
        label: "Evidence boundary",
        value: formatCompactLabel(evidenceBoundary),
        status: evidenceBoundary === "source_supported" ? "ok" : "watch",
      },
      {
        key: "downstream_posture",
        label: "Downstream posture",
        value: downstreamPosture,
        status: posture === "Watch" ? "watch" : "ok",
      },
    ],
  };
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
  const blocksAction = blockedActions.includes("low_risk_action_candidate") ||
    blockedActions.includes("strong_recommendation");

  if (status === "unsupported" || status === "contradicted" || unsupported > 0) {
    return { label: "Do Not Act", color: "#b91c1c", background: "#fef2f2", border: "1px solid #fecaca" };
  }
  if (status === "not_verifiable" || status === "weakly_supported" || inferred > 0) {
    return { label: "Review Required", color: "#92400e", background: "#fffbeb", border: "1px solid #fde68a" };
  }
  if (status === "partially_verified" || blocksAction) {
    return { label: "Review Before Action", color: "#c2410c", background: "#fff7ed", border: "1px solid #fed7aa" };
  }
  if (status === "verified") {
    return { label: "Ready For Low-Risk Review", color: "#166534", background: "#ecfdf5", border: "1px solid #bbf7d0" };
  }
  return { label: "Review Unknown", color: "#374151", background: "#f9fafb", border: "1px solid #e5e7eb" };
}

function getReviewPriorityExplanation({
  verificationStatus,
  blockedActions,
  supportSummary,
}: {
  verificationStatus?: string;
  blockedActions: string[];
  supportSummary: Record<string, number>;
}): string {
  const status = String(verificationStatus || "").toLowerCase();
  const unsupported = supportSummary.unsupported || 0;
  const contradicted = supportSummary.contradicted || 0;
  const inferred = supportSummary.inferred || 0;
  const partiallySupported = supportSummary.partially_supported || 0;

  if (status === "unsupported" || status === "contradicted" || unsupported > 0 || contradicted > 0) {
    return `Do not turn this into action yet: ${unsupported + contradicted} claim(s) are unsupported or contradicted by the attached evidence.`;
  }
  if (status === "not_verifiable") {
    return "Keep this as observation or watch-only: the source material is not traceable enough for project action.";
  }
  if (status === "weakly_supported" || inferred > 0) {
    return `Review before using this: ${inferred} claim(s) rely on inference rather than direct support.`;
  }
  if (status === "partially_verified" || partiallySupported > 0) {
    return "Use carefully: some claims are supported, but the insight still needs human review before stronger action.";
  }
  if (blockedActions.includes("low_risk_action_candidate") || blockedActions.includes("strong_recommendation")) {
    return "Verification allows reading, but blocks stronger downstream action until the claim checks improve.";
  }
  if (status === "verified") {
    return "Verification supports low-risk review. Human judgment is still needed before changing project direction.";
  }
  return "Verification metadata is incomplete, so treat this as review-only until the insight is regenerated or checked.";
}

function getProjectTakeawayGateMessage({
  allowed,
  blocked,
  reviewPriorityLabel,
  hasProjectText,
  candidateCreated,
  unsupportedCount,
  verificationStatus,
  blockedActions,
}: {
  allowed: boolean;
  blocked: boolean;
  reviewPriorityLabel: string;
  hasProjectText: boolean;
  candidateCreated: boolean;
  unsupportedCount: number;
  verificationStatus?: string;
  blockedActions: string[];
}): string {
  const status = String(verificationStatus || "").toLowerCase();
  if (candidateCreated) {
    return "Created: this signal already has a Project Takeaway candidate. Continue from the Review Inbox.";
  }
  if (blocked) {
    if (blockedActions.includes("project_takeaway_candidate")) {
      return "Blocked: verification explicitly blocks Project Takeaway creation for this insight.";
    }
    if (unsupportedCount > 0) {
      return `Blocked: ${unsupportedCount} unsupported or contradicted claim(s) prevent this from becoming a Project Takeaway candidate.`;
    }
    if (status === "unsupported" || status === "contradicted") {
      return "Blocked: the core claim is unsupported or contradicted by the attached evidence.";
    }
    if (status === "not_verifiable") {
      return "Blocked: the source evidence is not traceable enough for Project Takeaway review.";
    }
    return "Blocked: verification policy does not allow this insight to become a Project Takeaway candidate.";
  }
  if (reviewPriorityLabel === "Do Not Act") {
    if (unsupportedCount > 0) {
      return `Blocked: review priority is Do Not Act because ${unsupportedCount} claim(s) are unsupported or contradicted.`;
    }
    if (status === "unsupported" || status === "contradicted") {
      return "Blocked: review priority is Do Not Act because the verified insight is unsupported or contradicted.";
    }
    return "Blocked: review priority is Do Not Act, so this should remain out of the project review queue.";
  }
  if (!allowed) {
    if (status === "weakly_supported") {
      return "Waiting: evidence is weak, so this should stay in review or watch before Project Takeaway handoff.";
    }
    if (blockedActions.includes("low_risk_action_candidate")) {
      return "Waiting: low-risk Action is blocked; review the gate reason before Project Takeaway handoff.";
    }
    return "Waiting: verification has not explicitly allowed Project Takeaway candidate creation.";
  }
  if (!hasProjectText) {
    return "Waiting: project relevance or strategic takeaway text is missing.";
  }
  return "Ready: verification allows a Project Takeaway candidate, and the insight has project-relevant text.";
}

function buildProjectTakeawayManualOverrideReason({
  allowed,
  blocked,
  reviewPriorityLabel,
  unsupportedCount,
  verificationStatus,
  blockedActions,
}: {
  allowed: boolean;
  blocked: boolean;
  reviewPriorityLabel: string;
  unsupportedCount: number;
  verificationStatus?: string;
  blockedActions: string[];
}) {
  const status = String(verificationStatus || "").toLowerCase();
  const reasons: string[] = [];
  if (blockedActions.includes("project_takeaway_candidate")) {
    reasons.push("verification explicitly blocks Project Takeaway candidate creation");
  } else if (blocked) {
    reasons.push("verification blocks Project Takeaway candidate creation");
  }
  if (!allowed) reasons.push("verification has not allowed Project Takeaway candidate creation");
  if (reviewPriorityLabel === "Do Not Act") reasons.push("review priority is Do Not Act");
  if (unsupportedCount > 0) reasons.push(`${unsupportedCount} unsupported or contradicted claim(s) exist`);
  if (status === "not_verifiable") reasons.push("source evidence is not traceable enough");
  if (status === "weakly_supported") reasons.push("evidence is weak and needs review or watch first");
  return reasons.join("; ") || "manual reviewer selected this despite a conservative gate";
}

function getVerificationDecisionSummary({
  verificationStatus,
  evidenceLevel,
  supportSummary,
  allowedActions,
  blockedActions,
  downgradeReason,
}: {
  verificationStatus?: string;
  evidenceLevel?: string;
  supportSummary: Record<string, number>;
  allowedActions: string[];
  blockedActions: string[];
  downgradeReason?: string | null;
}) {
  const unsupported = (supportSummary.unsupported || 0) + (supportSummary.contradicted || 0);
  const inferred = supportSummary.inferred || 0;
  const partiallySupported = supportSummary.partially_supported || 0;
  const directlySupported = supportSummary.directly_supported || 0;
  const status = String(verificationStatus || "").toLowerCase();
  const readableStatus = formatCompactLabel(status || "unknown");

  const usable = allowedActions.length
    ? `Allowed uses: ${allowedActions.map(formatCompactLabel).join(", ")}.`
    : "No downstream use has been explicitly allowed yet.";

  const blocked = blockedActions.length
    ? `Blocked uses: ${blockedActions.map(formatCompactLabel).join(", ")}.`
    : "No downstream actions are currently blocked by verification.";

  const focus =
    unsupported > 0
      ? `Resolve or rewrite ${unsupported} unsupported/contradicted claim(s) before action.`
      : inferred > 0
        ? `Review ${inferred} inferred claim(s) and look for direct evidence before stronger action.`
        : partiallySupported > 0
          ? `Review partially supported claims before treating this as a strong recommendation.`
          : blockedActions.length > 0
            ? "Review the blocked action policy before moving this into action-oriented workflows."
            : "Human review can focus on project relevance rather than basic claim support.";

  return {
    headline: `Status: ${readableStatus}. Evidence level: ${formatCompactLabel(evidenceLevel || "unknown")}.`,
    usable,
    blocked,
    focus,
    supportLine: `${directlySupported} directly supported, ${partiallySupported} partially supported, ${inferred} inferred, ${unsupported} unsupported/contradicted.`,
    downgradeLine: downgradeReason
      ? `Downgrade reason: ${formatCompactLabel(downgradeReason)}.`
      : "No explicit downgrade reason is attached.",
  };
}

function getClaimSupportRows(summary: Record<string, number>) {
  return [
    { key: "directly_supported", label: "Direct", tone: "good" },
    { key: "partially_supported", label: "Partial", tone: "watch" },
    { key: "inferred", label: "Inferred", tone: "watch" },
    { key: "unsupported", label: "Unsupported", tone: "bad" },
    { key: "contradicted", label: "Contradicted", tone: "bad" },
  ].map((item) => ({
    ...item,
    count: summary[item.key] || 0,
  }));
}

function getClaimCoverageSnapshot(claims: ClaimCheckItem[]) {
  const total = claims.length;
  const withEvidenceRefs = claims.filter(
    (claim) => Array.isArray(claim.evidence_refs) && claim.evidence_refs.length > 0
  ).length;
  const withSourceSpan = claims.filter((claim) => Boolean(claim.source_span)).length;
  const formatCoverage = (count: number) =>
    total > 0 ? `${count}/${total} (${Math.round((count / total) * 100)}%)` : "N/A";

  return {
    total,
    withEvidenceRefs,
    withSourceSpan,
    evidenceRefCoverage: formatCoverage(withEvidenceRefs),
    sourceSpanCoverage: formatCoverage(withSourceSpan),
  };
}

function getGateSnapshotRows(allowedActions: string[], blockedActions: string[]) {
  return [
    { action: "project_takeaway_candidate", label: "Project Takeaway" },
    { action: "watch_only", label: "Watch" },
    { action: "low_risk_action_candidate", label: "Low-risk Action" },
  ].map((item) => {
    const allowed = allowedActions.includes(item.action);
    const blocked = blockedActions.includes(item.action);
    const tone: VerifiedInsightObjectRow["tone"] = allowed ? "good" : blocked ? "bad" : "neutral";
    return {
      ...item,
      status: allowed ? "Allowed" : blocked ? "Blocked" : "Not recorded",
      detail: allowed
        ? "Listed in allowed_downstream_actions."
        : blocked
          ? "Listed in blocked_downstream_actions."
          : "Not present in the current gate metadata.",
      tone,
    };
  });
}

function getVerificationObjectTone(verificationStatus?: string, blockedActions: string[] = []): VerifiedInsightObjectRow["tone"] {
  const status = String(verificationStatus || "").toLowerCase();
  if (blockedActions.includes("low_risk_action_candidate") || status.includes("unsupported")) return "bad";
  if (status.includes("partial") || status.includes("review") || status.includes("needs")) return "watch";
  if (status.includes("verified") || status.includes("supported")) return "good";
  return "neutral";
}

function getClaimSupportDecisionLine(summary: Record<string, number>, blockedActions: string[]) {
  const unsupported = (summary.unsupported || 0) + (summary.contradicted || 0);
  const inferred = summary.inferred || 0;
  const partial = summary.partially_supported || 0;
  const direct = summary.directly_supported || 0;

  if (unsupported > 0) {
    return `Decision posture: do not create action-oriented output until ${unsupported} unsupported or contradicted claim(s) are resolved.`;
  }
  if (blockedActions.includes("low_risk_action_candidate") || blockedActions.includes("strong_recommendation")) {
    return "Decision posture: review or Watch is acceptable, but low-risk Action remains blocked by verification.";
  }
  if (inferred > 0) {
    return `Decision posture: Watch or cautious review; ${inferred} inferred claim(s) still need direct evidence before stronger use.`;
  }
  if (partial > 0) {
    return `Decision posture: partial support is present; confirm the important claims before using this as a strong recommendation.`;
  }
  if (direct > 0) {
    return "Decision posture: evidence support is clean enough for project-fit review, subject to human judgment.";
  }
  return "Decision posture: no claim-support counts are available; treat this as review-only until regenerated or checked.";
}

function getInsightFallbackText(
  signal: InsightLike | null,
  field:
    | "why_it_matters"
    | "relevance_to_projects"
    | "relevance_to_career"
    | "synthesized_insight"
) {
  const status = signal?.insight_status;

  if (status === "manual_candidate") {
    switch (field) {
      case "why_it_matters":
        return "Insight was not auto-generated for this signal. This article is available for manual insight generation.";
      case "relevance_to_projects":
        return "Project relevance was not auto-generated for this signal. You can generate it manually if this article looks important.";
      case "relevance_to_career":
        return "Career relevance was not auto-generated for this signal. You can request an on-demand insight if needed.";
      case "synthesized_insight":
        return "Strategic takeaway was not auto-generated for this signal. This article is currently in the manual-candidate tier.";
      default:
        return "Insight is available on demand for this signal.";
    }
  }

  if (status === "archived_only") {
    switch (field) {
      case "why_it_matters":
        return "This signal was archived without AI insight generation because it ranked lower in the current radar run.";
      case "relevance_to_projects":
        return "This lower-priority signal was stored for timeline completeness, but project relevance was not generated.";
      case "relevance_to_career":
        return "This lower-priority signal was not analyzed for career relevance in the automatic insight pass.";
      case "synthesized_insight":
        return "No strategic takeaway was generated because this signal was placed in the archive-only tier.";
      default:
        return "This signal was archived without automatic AI insight generation.";
    }
  }

  if (status === "auto_generated") {
    return "Insight field is temporarily unavailable.";
  }

  return "Insight not available yet.";
}

function getInsightProcessingExplanation(status?: string) {
  if (status === "auto_generated") {
    return "This signal was selected by the daily pipeline for automatic insight generation.";
  }

  if (status === "manual_completed") {
    return "This manual-upload-derived signal already has structured insight content. Regenerate only when the uploaded context or intended use has changed.";
  }

  if (status === "manual_pending") {
    return "This manual-upload-derived signal is available in Signals, but its structured insight sections still need generation from Manual Detail or Signal Detail.";
  }

  if (status === "manual_candidate") {
    return "This signal was collected and kept as worth reviewing, but it was not selected for the automatic insight pass. Use Generate Insight or Generate with Claude if you want a full analysis.";
  }

  if (status === "archived_only") {
    return "This signal was stored for timeline completeness but ranked below the current threshold for automatic or on-demand insight work.";
  }

  return "Insight processing status is not available for this signal.";
}

function getProcessingBadgeStyle(status?: string) {
  if (status === "auto_generated") {
    return {
      background: "var(--app-success-bg)",
      color: "var(--app-success-fg)",
      border: "1px solid var(--app-success-border)",
    };
  }

  if (status === "manual_completed") {
    return {
      background: "var(--app-success-bg)",
      color: "var(--app-success-fg)",
      border: "1px solid var(--app-success-border)",
    };
  }

  if (status === "manual_pending") {
    return {
      background: "var(--app-warning-bg)",
      color: "var(--app-warning-fg)",
      border: "1px solid var(--app-warning-border)",
    };
  }

  if (status === "manual_candidate") {
    return {
      background: "var(--app-warning-bg)",
      color: "var(--app-warning-fg)",
      border: "1px solid var(--app-warning-border)",
    };
  }

  return {
    background: "var(--app-chip-bg)",
    color: "var(--app-chip-fg)",
    border: "1px solid var(--app-chip-border)",
  };
}

function coalesceStructuredValue<T extends StructuredValue>(...values: T[]): T | "" {
  for (const value of values) {
    if (value === null || value === undefined) continue;
    if (typeof value === "string" && value.trim() === "") continue;
    if (Array.isArray(value) && value.length === 0) continue;
    return value;
  }
  return "";
}

function stripUncertainPrefix(value: StructuredValue): StructuredValue {
  if (typeof value === "string") {
    return value.replace(/^\s*uncertain:\s*/i, "");
  }
  if (Array.isArray(value)) {
    return value.map((item) => stripUncertainPrefix(item)) as StructuredValue;
  }
  if (isRecord(value)) {
    const next: Record<string, StructuredValue> = {};
    for (const [key, nested] of Object.entries(value)) {
      next[key] = stripUncertainPrefix(nested as StructuredValue);
    }
    return next;
  }
  return value;
}

function buildManualInsight(session: ManualSessionLike, requestedId: string): InsightLike {
  const analysis = session.analysis || {};
  const summaryValue = coalesceStructuredValue(
    session.summary,
    analysis.summary,
    "Manual uploaded session"
  );
  const manualSummary =
    typeof summaryValue === "string" ? summaryValue.trim() || "Manual uploaded session" : "Manual uploaded session";

  const resolvedStatus =
    session.status ||
    (session.completion_saved
      ? "completed"
      : session.analysis_status === "completed"
        ? "analyzed"
        : "pending");

  const whyItMatters = coalesceStructuredValue(
    session.why_it_matters,
    analysis.why_it_matters
  );
  const relevanceToProjects = coalesceStructuredValue(
    session.relevance_to_projects,
    analysis.relevance_to_projects
  );
  const relevanceToCareer = coalesceStructuredValue(
    session.relevance_to_career,
    analysis.relevance_to_career
  );
  const synthesizedInsight = coalesceStructuredValue(
    session.synthesized_insight,
    analysis.synthesized_insight
  );

  return {
    id: session.session_id || requestedId,
    signal_id: session.session_id || requestedId,
    title: session.title || "Manual Session",
    signal_title: session.title || "Manual Session",
    summary: typeof stripUncertainPrefix(manualSummary) === "string" ? String(stripUncertainPrefix(manualSummary)) : manualSummary,
    signal_summary: typeof stripUncertainPrefix(manualSummary) === "string" ? String(stripUncertainPrefix(manualSummary)) : manualSummary,
    topic: session.topic || analysis.topic || "Manual Upload",
    insight_status:
      session.analysis_status === "completed" ? "manual_completed" : "manual_pending",
    insight_status_label:
      session.analysis_status === "completed"
        ? "Manual session analyzed"
        : "Manual session pending",
    status: resolvedStatus,
    saved_reason: session.saved_reason || null,
    published_at: session.created_at,
    collected_at: session.created_at,
    why_it_matters: stripUncertainPrefix(whyItMatters),
    relevance_to_projects: stripUncertainPrefix(relevanceToProjects),
    relevance_to_career: stripUncertainPrefix(relevanceToCareer),
    synthesized_insight: stripUncertainPrefix(synthesizedInsight),
    insight: stripUncertainPrefix(whyItMatters),
    strategy: stripUncertainPrefix(synthesizedInsight),
    is_manual: true,
    upload_reason: session.upload_reason || "",
    intended_use: session.intended_use || "",
    cognitive_layer: session.cognitive_layer || "unclassified",
    provider_used: session.provider_used,
    model_used: session.model_used,
    generation_mode: session.generation_mode,
    requested_provider: session.requested_provider,
    verification: session.verification,
    policy_metadata: session.policy_metadata,
    evidence_pack: session.evidence_pack,
    subscription_project_links: session.subscription_project_links || [],
    files: Array.isArray(session.files) ? session.files : [],
    file_count: session.file_count,
    file_types: session.file_types,
  };
}

function renderStructuredValue(value: StructuredValue): React.ReactNode {
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
          <div key={index}>{renderStructuredValue(item)}</div>
        ))}
      </div>
    );
  }

  if (isRecord(value)) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
        {Object.entries(value).map(([key, val]) => (
          <div
            key={key}
            style={{
              border: "1px solid #ececec",
              borderRadius: "8px",
              padding: "12px",
              background: "var(--app-surface-muted-bg)",
            }}
          >
            <div
              style={{
                fontSize: "12px",
                fontWeight: 700,
                color: "var(--app-text-subtle)",
                marginBottom: "6px",
                textTransform: "uppercase",
                letterSpacing: 0,
              }}
            >
              {key}
            </div>
            <div style={{ lineHeight: 1.7, color: "var(--app-text-muted)", fontSize: "14px" }}>
              {renderStructuredValue(val)}
            </div>
          </div>
        ))}
      </div>
    );
  }

  return <span>{String(value)}</span>;
}

function InsightSection({
  label,
  value,
  fallback,
}: {
  label: string;
  value: StructuredValue;
  fallback?: string;
}) {
  const isEmpty =
    value === null ||
    value === undefined ||
    value === "" ||
    (Array.isArray(value) && value.length === 0);

  return (
    <div
      style={{
        border: "1px solid var(--app-surface-border)",
        borderRadius: "8px",
        padding: "18px",
        background: "var(--app-surface-bg)",
        marginBottom: "16px",
        boxShadow: "var(--app-surface-shadow)",
      }}
    >
      <div
        style={{
          fontSize: "12px",
          fontWeight: 700,
          color: "var(--app-text-subtle)",
          marginBottom: "8px",
          textTransform: "uppercase",
          letterSpacing: 0,
        }}
      >
        {label}
      </div>

      <div style={{ fontSize: "15px", lineHeight: 1.7, color: "var(--app-text-strong)" }}>
        {isEmpty ? <span>{fallback || "No content available yet."}</span> : renderStructuredValue(value)}
      </div>
    </div>
  );
}

function ChatWindow({
  messages,
  loading,
  expectedProvider,
  expanded,
}: {
  messages: ChatMessage[];
  loading: boolean;
  expectedProvider?: string;
  expanded: boolean;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const endRef = useRef<HTMLDivElement | null>(null);
  const [copiedMessageKey, setCopiedMessageKey] = useState<string | null>(null);
  const [copyFailedMessageKey, setCopyFailedMessageKey] = useState<string | null>(null);

  async function copyMessage(messageKey: string, content: string) {
    try {
      await navigator.clipboard.writeText(content);
      setCopiedMessageKey(messageKey);
      setCopyFailedMessageKey(null);
      window.setTimeout(() => {
        setCopiedMessageKey((current) => (current === messageKey ? null : current));
      }, 1800);
    } catch {
      setCopiedMessageKey(null);
      setCopyFailedMessageKey(messageKey);
      window.setTimeout(() => {
        setCopyFailedMessageKey((current) => (current === messageKey ? null : current));
      }, 2400);
    }
  }

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    container.scrollTo({
      top: container.scrollHeight,
      behavior: "smooth",
    });
  }, [messages, loading]);

  return (
    <div
      ref={containerRef}
      style={{
        border: "1px solid var(--app-surface-border)",
        borderRadius: "8px",
        background: "var(--app-surface-muted-bg)",
        height: expanded ? "min(72vh, 760px)" : "clamp(420px, 52vh, 680px)",
        overflowY: "auto",
        padding: "12px",
      }}
    >
      {messages.length === 0 ? (
        <div style={{ color: "var(--app-text-subtle)", fontSize: "14px" }}>
          No conversation yet.
        </div>
      ) : (
        messages.map((msg, index) => {
          const messageKey = `${msg.role}-${index}`;
          const copyState =
            copiedMessageKey === messageKey
              ? "copied"
              : copyFailedMessageKey === messageKey
                ? "failed"
                : "idle";
          const hasRouteInfo =
            msg.role === "assistant" &&
            (msg.provider_used || msg.model_used || typeof msg.fallback_used === "boolean");
          const providerMismatch =
            msg.role === "assistant" &&
            expectedProvider &&
            msg.provider_used &&
            msg.provider_used !== expectedProvider;

          return (
            <div
              key={messageKey}
              style={{
                display: "flex",
                justifyContent: msg.role === "user" ? "flex-end" : "flex-start",
                marginBottom: "10px",
              }}
            >
              <div
                style={{
                  maxWidth: "92%",
                  whiteSpace: "pre-wrap",
                  lineHeight: 1.6,
                  fontSize: "14px",
                  padding: "10px 12px",
                  borderRadius: "12px",
                  background:
                    msg.role === "user"
                      ? "var(--app-primary-action-bg)"
                      : "var(--app-surface-bg)",
                  color:
                    msg.role === "user"
                      ? "var(--app-primary-action-fg)"
                      : "var(--app-text-strong)",
                  border:
                    msg.role === "user"
                      ? "1px solid var(--app-primary-action-border)"
                      : "1px solid var(--app-surface-border)",
                }}
              >
                <div style={{ whiteSpace: "pre-wrap" }}>{msg.content}</div>
                {hasRouteInfo ? (
                  <div
                    style={{
                      marginTop: "8px",
                      paddingTop: "8px",
                      borderTop:
                        msg.role === "user"
                          ? "1px solid rgba(255,255,255,0.18)"
                          : "1px solid var(--app-surface-border)",
                      fontSize: "11px",
                      lineHeight: 1.5,
                      color:
                        msg.role === "user"
                          ? "rgba(255,255,255,0.82)"
                          : "var(--app-text-subtle)",
                    }}
                  >
                    {`Actual route: ${msg.provider_used || "unknown"}${msg.model_used ? ` / ${msg.model_used}` : ""}${msg.fallback_used ? " / fallback used" : ""}`}
                    {providerMismatch ? (
                      <div style={{ color: "#b45309", marginTop: "4px", fontWeight: 700 }}>
                        {`Warning: selected tab expected ${expectedProvider}, but this reply used ${msg.provider_used}.`}
                      </div>
                    ) : null}
                  </div>
                ) : null}
                <div
                  style={{
                    display: "flex",
                    justifyContent: "flex-end",
                    marginTop: "8px",
                  }}
                >
                  <button
                    type="button"
                    onClick={() => void copyMessage(messageKey, msg.content)}
                    aria-label="Copy this discussion message"
                    title="Copy message"
                    style={{
                      ...discussionCopyButtonStyle,
                      ...(msg.role === "user" ? discussionCopyButtonOnPrimaryStyle : {}),
                    }}
                  >
                    <Copy size={13} strokeWidth={2.3} />
                    {copyState === "copied" ? "Copied" : copyState === "failed" ? "Copy failed" : "Copy"}
                  </button>
                </div>
              </div>
            </div>
          );
        })
      )}

      {loading && (
        <div style={{ color: "var(--app-text-subtle)", fontSize: "14px", marginTop: "8px" }}>
          Thinking...
        </div>
      )}

      <div ref={endRef} />
    </div>
  );
}

export default function SignalDetailClient() {
  const searchParams = useSearchParams();
  const id = decodeURIComponent(searchParams.get("id") || "");
  const reviewFocusId = decodeURIComponent(searchParams.get("review_signal_id") || "");

  const [insight, setInsight] = useState<InsightLike | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailRefreshing, setDetailRefreshing] = useState(false);
  const [relatedReflections, setRelatedReflections] = useState<RelatedReflection[]>([]);
  const [relatedReflectionTopics, setRelatedReflectionTopics] = useState<string[]>([]);
  const [relatedReflectionsLoading, setRelatedReflectionsLoading] = useState(false);
  const [lifecycleProbe, setLifecycleProbe] = useState<SignalLifecycleProbe | null>(null);
  const [lifecycleProbeLoading, setLifecycleProbeLoading] = useState(false);
  const [lifecycleProbeError, setLifecycleProbeError] = useState("");

  const [localStatus, setLocalStatus] = useState<string>("pending");
  const [statusUpdating, setStatusUpdating] = useState(false);
  const [starUpdating, setStarUpdating] = useState(false);
  const [statusMessage, setStatusMessage] = useState("");
  const [statusError, setStatusError] = useState("");
  const [decisionEditingUnlocked, setDecisionEditingUnlocked] = useState(false);
  const [decisionLockActive, setDecisionLockActive] = useState(false);
  const [insightGenerating, setInsightGenerating] = useState(false);
  const [insightGeneratingModel, setInsightGeneratingModel] = useState<"chatgpt" | "claude" | null>(null);
  const [showSaveReason, setShowSaveReason] = useState(false);
  const [selectedSaveReasons, setSelectedSaveReasons] = useState<string[]>(["Industry Trend"]);
  const [customSaveReason, setCustomSaveReason] = useState("");

  const [reflection, setReflection] = useState("");
  const [isGeneratingDraft, setIsGeneratingDraft] = useState(false);
  const [draftError, setDraftError] = useState("");
  const [isPolishing, setIsPolishing] = useState(false);
  const [reflectionPolishPairId, setReflectionPolishPairId] = useState("");
  const [visualStyle, setVisualStyle] = useState<VisualStyle>("architecture");
  const [visualDirection, setVisualDirection] = useState("");
  const [visualGenerating, setVisualGenerating] = useState(false);
  const [visualError, setVisualError] = useState("");
  const [generatedVisualUrl, setGeneratedVisualUrl] = useState("");
  const [generatedVisualFileName, setGeneratedVisualFileName] = useState("");

  const [saveMessage, setSaveMessage] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [isCompleting, setIsCompleting] = useState(false);
  const [reviewBundleText, setReviewBundleText] = useState("");
  const [reviewBundleSnapshot, setReviewBundleSnapshot] = useState<ReviewBundleSnapshot | null>(null);
  const [reviewBundleSaving, setReviewBundleSaving] = useState(false);
  const [reviewBundleMessage, setReviewBundleMessage] = useState("");
  const [reviewBundleError, setReviewBundleError] = useState("");
  const [externalSynthesisText, setExternalSynthesisText] = useState("");
  const [externalSynthesisFileName, setExternalSynthesisFileName] = useState("");
  const [externalSynthesisSource, setExternalSynthesisSource] = useState<ExternalSynthesisSource | null>(null);
  const [externalSynthesisSaving, setExternalSynthesisSaving] = useState(false);
  const [externalSynthesisMessage, setExternalSynthesisMessage] = useState("");
  const [externalSynthesisError, setExternalSynthesisError] = useState("");
  const [finalTakeawayText, setFinalTakeawayText] = useState("");
  const [finalTakeawayConfirming, setFinalTakeawayConfirming] = useState(false);
  const [confirmedFinalTakeaway, setConfirmedFinalTakeaway] = useState<FinalTakeawayArtifact | null>(null);
  const [finalTakeawayMessage, setFinalTakeawayMessage] = useState("");
  const [finalTakeawayError, setFinalTakeawayError] = useState("");
  const [completionReviewConfirmed, setCompletionReviewConfirmed] = useState(false);
  const [projectCandidateCreating, setProjectCandidateCreating] = useState(false);
  const [projectCandidateCreated, setProjectCandidateCreated] = useState(false);
  const [projectCandidateItems, setProjectCandidateItems] = useState<ProjectTakeawayCandidate[]>([]);
  const [projectCandidateMessage, setProjectCandidateMessage] = useState("");
  const [projectCandidateError, setProjectCandidateError] = useState("");
  const [projectTakeawayOverrideConfirmed, setProjectTakeawayOverrideConfirmed] = useState(false);
  const [deepProjectMatchReviewNote, setDeepProjectMatchReviewNote] = useState("");
  const [deepProjectMatchAnalysis, setDeepProjectMatchAnalysis] = useState<DeepProjectMatchGeneratedAnalysis | null>(null);
  const [deepProjectMatchAnalysisLayers, setDeepProjectMatchAnalysisLayers] = useState<DeepProjectMatchGeneratedAnalysis[]>([]);
  const [deepProjectMatchAnalysisLoading, setDeepProjectMatchAnalysisLoading] = useState(false);
  const [deepProjectMatchAnalysisError, setDeepProjectMatchAnalysisError] = useState("");
  const [claimFeedbackDrafts, setClaimFeedbackDrafts] = useState<Record<string, ClaimFeedbackDraft>>({});
  const [claimFeedbackRecords, setClaimFeedbackRecords] = useState<SignalReviewFeedbackRecord[]>([]);
  const [claimFeedbackLoading, setClaimFeedbackLoading] = useState(false);
  const [claimFeedbackError, setClaimFeedbackError] = useState("");

  const [activeTab, setActiveTab] = useState<UiTab>("ChatGPT");
  const [discussionExpanded, setDiscussionExpanded] = useState(false);

  const [claudeInput, setClaudeInput] = useState("");
  const [claudeLoading, setClaudeLoading] = useState(false);
  const [claudeMessages, setClaudeMessages] = useState<ChatMessage[]>([]);

  const [chatgptInput, setChatgptInput] = useState("");
  const [chatgptLoading, setChatgptLoading] = useState(false);
  const [chatgptMessages, setChatgptMessages] = useState<ChatMessage[]>([]);

  const [perplexityInput, setPerplexityInput] = useState("");
  const [perplexityLoading, setPerplexityLoading] = useState(false);
  const [perplexityMessages, setPerplexityMessages] = useState<ChatMessage[]>([]);
  const [manualFileUrls, setManualFileUrls] = useState<Record<string, string>>({});
  const [manualFilePreviewOverrides, setManualFilePreviewOverrides] = useState<Record<string, string>>({});
  const [manualLightboxIndex, setManualLightboxIndex] = useState<number | null>(null);
  const [expandedManualTextPreviewIds, setExpandedManualTextPreviewIds] = useState<Record<string, boolean>>({});
  const manualFileUrlsRef = useRef<Record<string, string>>({});
  const manualFiles = useMemo(
    () => (Array.isArray(insight?.files) ? insight.files : []),
    [insight]
  );
  const manualImageFiles = useMemo(
    () => manualFiles.filter((file) => file.file_kind === "image"),
    [manualFiles]
  );
  const manualTextLikeFiles = useMemo(
    () => manualFiles.filter((file) => file.file_kind === "text" || file.file_kind === "pdf"),
    [manualFiles]
  );
  const filesNeedingManualPreviewHydration = useMemo(
    () => manualTextLikeFiles.filter((file) => needsPdfPreviewHydration(file)),
    [manualTextLikeFiles]
  );
  const currentManualLightboxFile =
    manualLightboxIndex !== null && manualImageFiles[manualLightboxIndex]
      ? manualImageFiles[manualLightboxIndex]
      : null;

  useEffect(() => {
    if (!insight) return;
    const adminHeaders = buildAdminAuthHeaders();
    if (Object.keys(adminHeaders as Record<string, string>).length === 0) return;

    let cancelled = false;
    const controller = new AbortController();
    const signalId = insight.signal_id || insight.id || String(id);

    async function loadClaimFeedbackRecords() {
      setClaimFeedbackLoading(true);
      setClaimFeedbackError("");
      try {
        const params = new URLSearchParams({ signal_id: signalId });
        const res = await adminFetch(`${API_BASE}/signal-review-feedback?${params.toString()}`, {
          cache: "no-store",
          signal: controller.signal,
        });
        const data = await readApiResponse(res);
        if (!res.ok) {
          throw new Error(String(data.detail || data.message || `Failed to load feedback records. HTTP ${res.status}`));
        }
        const records = Array.isArray(data.records)
          ? data.records.filter(isRecord).map((record) => ({
              id: String(record.id || ""),
              claim_id: String(record.claim_id || ""),
              reason_slot: String(record.reason_slot || ""),
              note: String(record.note || ""),
              created_at: String(record.created_at || ""),
            }))
          : [];
        if (!cancelled) {
          setClaimFeedbackRecords(records);
        }
      } catch (error: unknown) {
        if (error instanceof DOMException && error.name === "AbortError") return;
        if (!cancelled) {
          setClaimFeedbackError(getErrorMessage(error, "Failed to load feedback records."));
        }
      } finally {
        if (!cancelled) {
          setClaimFeedbackLoading(false);
        }
      }
    }

    void loadClaimFeedbackRecords();

    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [id, insight?.id, insight?.signal_id]);

  const getManualPreviewText = (file: NonNullable<InsightLike["files"]>[number]) => {
    const storedFilename = file.stored_filename || "";
    const previewText = manualFilePreviewOverrides[storedFilename] || file.preview_text || "";
    return previewText.trim() === PDF_PREVIEW_PENDING_MESSAGE ? "" : previewText;
  };

  const toggleManualTextPreview = (fileKey: string) => {
    setExpandedManualTextPreviewIds((current) => ({
      ...current,
      [fileKey]: !current[fileKey],
    }));
  };

  const refreshSignalStatus = async () => {
    const res = await withTimeout(
      fetch(`${API_BASE}/signals/${encodeURIComponent(id)}`),
      STATUS_REFRESH_TIMEOUT_MS,
      "Signal detail refresh timed out."
    );
    if (!res.ok) {
      throw new Error("Failed to refresh signal detail.");
    }
    const data = (await res.json()) as SignalDetailResponse;
    setInsight((prev) => (prev ? { ...prev, ...data } : data));
    setLocalStatus(normalizeStatus(data?.status));
    return data;
  };

  useEffect(() => {
    let cancelled = false;
    const signalController = new AbortController();
    const cachedSignal = findCachedSignalDetail(id);
    if (cachedSignal) {
      window.queueMicrotask(() => {
        if (cancelled) return;
        setInsight(cachedSignal);
        setLocalStatus(normalizeStatus(cachedSignal.status));
        setLoading(false);
        setDetailRefreshing(true);
      });
    }

    async function loadSignal() {
      if (!cachedSignal) {
        setLoading(true);
      } else {
        setDetailRefreshing(true);
      }

      try {
    // First path: standard signal detail.
        const res = await fetch(`${API_BASE}/signals/${encodeURIComponent(id)}`, {
          signal: signalController.signal,
        });

        if (res.ok) {
          const data = (await res.json()) as SignalDetailResponse;
          if (!cancelled) {
            setInsight(data);
            setLocalStatus(normalizeStatus(data?.status));
            setDetailRefreshing(false);
          }
          return;
        }

      // Second path: try the manual session fallback.
        console.log("signal not found, trying manual session fallback");

        const normalizedManualId =
          typeof id === "string" && id.startsWith("manual_") ? id.slice("manual_".length) : id;

        const enrichedManualSignalRes = await fetch(
          `${API_BASE}/signals/${encodeURIComponent(`manual_${normalizedManualId}`)}`,
          {
            headers: buildAdminAuthHeaders(),
            signal: signalController.signal,
          }
        );

        if (enrichedManualSignalRes.ok) {
          const manualSignalData = (await enrichedManualSignalRes.json()) as SignalDetailResponse;
          if (!cancelled) {
            setInsight(manualSignalData);
            setLocalStatus(normalizeStatus(manualSignalData?.status));
            setDetailRefreshing(false);
          }
          return;
        }

        const manualDetailRes = await fetch(
          `${API_BASE}/manual/session/${encodeURIComponent(normalizedManualId)}`,
          {
            headers: buildAdminAuthHeaders(),
            signal: signalController.signal,
          }
        );

        if (manualDetailRes.ok) {
          const manualDetailData = (await manualDetailRes.json()) as ManualSessionDetailResponse;
          if (manualDetailData.session) {
            const manualInsight = buildManualInsight(manualDetailData.session, id);
            if (!cancelled) {
              setInsight(manualInsight);
              setLocalStatus(normalizeStatus(manualInsight.status));
              setDetailRefreshing(false);
            }
            return;
          }
        }

        const manualRes = await fetch(`${API_BASE}/manual/sessions`, {
          headers: buildAdminAuthHeaders(),
          signal: signalController.signal,
        });

        if (!manualRes.ok) {
          throw new Error("manual session fetch failed");
        }

        const manualData = (await manualRes.json()) as ManualSessionsResponse | ManualSessionLike[];

        const sessions = Array.isArray(manualData)
          ? manualData
          : manualData.sessions || manualData.items || [];

        const matched = sessions.find(
          (s: ManualSessionLike) =>
            s.session_id === id || s.session_id === normalizedManualId
        );

        if (matched) {
          const manualInsight = buildManualInsight(matched as ManualSessionLike, id);

          if (!cancelled) {
            setInsight(manualInsight);
            setLocalStatus(normalizeStatus(manualInsight.status));
            setDetailRefreshing(false);
          }

          return;
        }

        throw new Error("Signal not found");
      } catch (err) {
        if (err instanceof Error && err.name === "AbortError") {
          return;
        }
        if (!cancelled) {
          setInsight(null);
          setDetailRefreshing(false);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
          setDetailRefreshing(false);
        }
      }
    }

    loadSignal();

    return () => {
      cancelled = true;
      signalController.abort();
    };
  }, [id]);

  useEffect(() => {
    if (!insight) return;

    const signalId = insight.signal_id || insight.id || String(id);
    if (!signalId) return;

    let cancelled = false;
    const controller = new AbortController();

    async function loadExistingFinalTakeawayArtifacts() {
      try {
        const synthesisRes = await adminFetch(
          `${API_BASE}/final-takeaways/external-synthesis-sources?signal_id=${encodeURIComponent(signalId)}`,
          { signal: controller.signal }
        );
        if (synthesisRes.ok) {
          const synthesisData = (await synthesisRes.json().catch(() => null)) as ExternalSynthesisSourcesResponse | null;
          const latestSynthesis = (synthesisData?.items || [])[0] || null;
          if (latestSynthesis?.external_synthesis_source_id) {
            const synthesisDetailRes = await adminFetch(
              `${API_BASE}/final-takeaways/external-synthesis-sources/${encodeURIComponent(latestSynthesis.external_synthesis_source_id)}`,
              { signal: controller.signal }
            );
            const synthesisDetail = synthesisDetailRes.ok
              ? ((await synthesisDetailRes.json().catch(() => null)) as { source?: ExternalSynthesisSource } | null)
              : null;
            const source = synthesisDetail?.source || latestSynthesis;
            if (!cancelled) {
              setExternalSynthesisSource(source);
              setExternalSynthesisText(source.source_text || "");
              setExternalSynthesisFileName(source.source_file || "");
            }
          }
        }

        const snapshotsRes = await adminFetch(
          `${API_BASE}/final-takeaways/review-bundle-snapshots?signal_id=${encodeURIComponent(signalId)}`,
          { signal: controller.signal }
        );
        if (snapshotsRes.ok) {
          const snapshotData = (await snapshotsRes.json().catch(() => null)) as ReviewBundleSnapshotsResponse | null;
          const latestSnapshot = (snapshotData?.items || [])[0] || null;
          if (latestSnapshot?.snapshot_id) {
            const snapshotDetailRes = await adminFetch(
              `${API_BASE}/final-takeaways/review-bundle-snapshots/${encodeURIComponent(latestSnapshot.snapshot_id)}`,
              { signal: controller.signal }
            );
            const snapshotDetail = snapshotDetailRes.ok
              ? ((await snapshotDetailRes.json().catch(() => null)) as { snapshot?: ReviewBundleSnapshot } | null)
              : null;
            const snapshot = snapshotDetail?.snapshot || latestSnapshot;
            if (!cancelled) {
              setReviewBundleSnapshot(snapshot);
              if (snapshot.source_text) {
                setReviewBundleText(snapshot.source_text);
              }
            }
          }
        }

        const finalTakeawaysRes = await adminFetch(
          `${API_BASE}/final-takeaways?signal_id=${encodeURIComponent(signalId)}`,
          { signal: controller.signal }
        );
        if (!finalTakeawaysRes.ok) return;

        const finalTakeawaysData = (await finalTakeawaysRes.json().catch(() => null)) as FinalTakeawaysResponse | null;
        const latestFinalTakeaway = (finalTakeawaysData?.items || [])[0] || null;
        if (!latestFinalTakeaway?.final_takeaway_id) {
          if (!cancelled) {
            setConfirmedFinalTakeaway(null);
          }
          return;
        }

        const detailRes = await adminFetch(
          `${API_BASE}/final-takeaways/${encodeURIComponent(latestFinalTakeaway.final_takeaway_id)}`,
          { signal: controller.signal }
        );
        if (!detailRes.ok) return;

        const detailData = (await detailRes.json().catch(() => null)) as { final_takeaway?: FinalTakeawayArtifact } | null;
        const finalTakeaway = detailData?.final_takeaway || latestFinalTakeaway;
        if (cancelled || !finalTakeaway?.final_takeaway_id) return;

        setConfirmedFinalTakeaway(finalTakeaway);
        setFinalTakeawayText(finalTakeaway.confirmed_text || "");
        if (finalTakeaway.review_bundle_snapshot_id) {
          setReviewBundleSnapshot((current) => ({
            snapshot_id: finalTakeaway.review_bundle_snapshot_id,
            signal_id: finalTakeaway.signal_id || signalId,
            content_hash: finalTakeaway.review_bundle_content_hash || current?.content_hash || "",
            created_at: current?.created_at || finalTakeaway.confirmed_at || "",
            used_by: current?.used_by || "confirmed_final_takeaway",
            source_kind: current?.source_kind || "external_md",
            source_text: current?.source_text || "",
          }));
        }
      } catch (error) {
        if (error instanceof Error && error.name === "AbortError") return;
      }
    }

    void loadExistingFinalTakeawayArtifacts();

    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [id, insight]);

  useEffect(() => {
    if (!insight) return;

    const signalId = insight.signal_id || insight.id || String(id);
    if (!signalId) return;

    let cancelled = false;
    const controller = new AbortController();

    async function loadExistingProjectCandidate() {
      try {
        const res = await adminFetch(`${API_BASE}/projects/takeaway-candidates?include_confirmed=true&include_closed=true`, {
          signal: controller.signal,
        });
        if (!res.ok) return;

        const data = (await res.json().catch(() => null)) as ProjectTakeawayCandidatesResponse | null;
        const matches = (data?.items || []).filter((item) => projectCandidateMatchesSignal(item, signalId));
        const finalTakeawayMatches = matches.filter((item) =>
          projectCandidateMatchesFinalTakeaway(item, signalId, confirmedFinalTakeaway?.final_takeaway_id || "")
        );
        if (!cancelled && matches.length > 0) {
          setProjectCandidateItems(finalTakeawayMatches.length > 0 ? finalTakeawayMatches : matches);
          setProjectCandidateCreated(true);
          setProjectCandidateMessage(
            finalTakeawayMatches.length > 0
              ? "Confirmed Final Takeaway has already been sent to Project Review."
              : "Project takeaway candidate already exists. Open the Review Inbox or Project Takeaways to review it."
          );
        } else if (!cancelled) {
          setProjectCandidateItems([]);
          setProjectCandidateCreated(false);
        }
      } catch (error) {
        if (error instanceof Error && error.name === "AbortError") return;
      }
    }

    void loadExistingProjectCandidate();

    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [id, insight, confirmedFinalTakeaway?.final_takeaway_id]);

  useEffect(() => {
    if (!insight) {
      setLifecycleProbe(null);
      setLifecycleProbeError("");
      setLifecycleProbeLoading(false);
      return;
    }

    const signalId = insight.signal_id || insight.id || String(id);
    if (!signalId) return;

    let cancelled = false;
    const controller = new AbortController();

    async function loadLifecycleProbe() {
      setLifecycleProbeLoading(true);
      setLifecycleProbeError("");

      try {
        const res = await adminFetch(`${API_BASE}/signals/${encodeURIComponent(signalId)}/lifecycle-probe`, {
          signal: controller.signal,
        });
        const data = (await res.json().catch(() => null)) as SignalLifecycleProbe | { detail?: string; message?: string } | null;

        if (!res.ok) {
          const message = data?.detail || data?.message || `Lifecycle probe failed (${res.status})`;
          throw new Error(message);
        }

        if (!cancelled) {
          setLifecycleProbe(data as SignalLifecycleProbe);
        }
      } catch (error) {
        if (error instanceof Error && error.name === "AbortError") return;
        if (!cancelled) {
          setLifecycleProbe(null);
          setLifecycleProbeError(error instanceof Error ? error.message : "Lifecycle probe failed.");
        }
      } finally {
        if (!cancelled) {
          setLifecycleProbeLoading(false);
        }
      }
    }

    void loadLifecycleProbe();

    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [id, insight]);

  useEffect(() => {
    const savedReflection = localStorage.getItem(`reflection-${id}`);
    if (savedReflection) setReflection(savedReflection);

    const savedClaudeMessages = localStorage.getItem(`claudeMessages-${id}`);
    if (savedClaudeMessages) setClaudeMessages(JSON.parse(savedClaudeMessages));

    const savedChatgptMessages = localStorage.getItem(`chatgptMessages-${id}`);
    if (savedChatgptMessages) setChatgptMessages(JSON.parse(savedChatgptMessages));

    const savedPerplexityMessages = localStorage.getItem(`perplexityMessages-${id}`);
    if (savedPerplexityMessages) setPerplexityMessages(JSON.parse(savedPerplexityMessages));
  }, [id]);

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
    const chatController = new AbortController();

    async function loadPersistedChats() {
      try {
        const res = await fetch(
          `${API_BASE}/workspace_chat_history/${encodeURIComponent(String(id))}`,
          {
            headers: buildAdminAuthHeaders(),
            signal: chatController.signal,
          }
        );
        if (!res.ok) return;

        const data = await res.json();
        const models = data?.models || {};

        if (cancelled) return;

        if (Array.isArray(models.claude?.messages) && models.claude.messages.length > 0) {
          setClaudeMessages(models.claude.messages);
        }
        if (Array.isArray(models.chatgpt?.messages) && models.chatgpt.messages.length > 0) {
          setChatgptMessages(models.chatgpt.messages);
        }
        if (Array.isArray(models.perplexity?.messages) && models.perplexity.messages.length > 0) {
          setPerplexityMessages(models.perplexity.messages);
        }
      } catch (error) {
        if (error instanceof Error && error.name === "AbortError") {
          return;
        }
      }
    }

    loadPersistedChats();

    return () => {
      cancelled = true;
      chatController.abort();
    };
  }, [id]);

  useEffect(() => {
    let cancelled = false;

    async function hydrateManualFileUrls() {
      for (const file of manualFiles) {
        const storedFilename = file.stored_filename || "";
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

    if (manualFiles.length > 0) {
      void hydrateManualFileUrls();
    }

    return () => {
      cancelled = true;
    };
  }, [manualFiles]);

  useEffect(() => {
    if (filesNeedingManualPreviewHydration.length === 0) return;

    let cancelled = false;

    async function hydrateManualFilePreviews() {
      for (const file of filesNeedingManualPreviewHydration) {
        const storedFilename = file.stored_filename || "";
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
  }, [filesNeedingManualPreviewHydration, manualFilePreviewOverrides]);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (manualLightboxIndex === null || manualImageFiles.length === 0) return;
      if (event.key === "Escape") setManualLightboxIndex(null);
      if (event.key === "ArrowLeft") {
        setManualLightboxIndex((current) => {
          if (current === null) return 0;
          return current === 0 ? manualImageFiles.length - 1 : current - 1;
        });
      }
      if (event.key === "ArrowRight") {
        setManualLightboxIndex((current) => {
          if (current === null) return 0;
          return current === manualImageFiles.length - 1 ? 0 : current + 1;
        });
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [manualImageFiles.length, manualLightboxIndex]);

  useEffect(() => {
    setGeneratedVisualUrl("");
    setGeneratedVisualFileName("");
    setVisualError("");
    setVisualDirection("");
    setVisualStyle("architecture");
  }, [id]);

  useEffect(() => {
    localStorage.setItem(`reflection-${id}`, reflection);
  }, [id, reflection]);

  useEffect(() => {
    localStorage.setItem(`claudeMessages-${id}`, JSON.stringify(claudeMessages));
  }, [id, claudeMessages]);

  useEffect(() => {
    localStorage.setItem(`chatgptMessages-${id}`, JSON.stringify(chatgptMessages));
  }, [id, chatgptMessages]);

  useEffect(() => {
    localStorage.setItem(`perplexityMessages-${id}`, JSON.stringify(perplexityMessages));
  }, [id, perplexityMessages]);

  useEffect(() => {
    let cancelled = false;
    const controller = new AbortController();

    async function loadRelatedReflections() {
      if (!insight) {
        setRelatedReflections([]);
        setRelatedReflectionTopics([]);
        return;
      }

      setRelatedReflectionsLoading(true);
      try {
        const res = await fetch(
          `${API_BASE}/signals/${encodeURIComponent(id)}/related-reflections?limit=3`,
          { signal: controller.signal }
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
  }, [id, insight]);

  const displayTitle = insight?.signal_title || insight?.title || "Untitled signal";
  const displaySummary = insight?.signal_summary || insight?.summary || "No summary available.";
  const displayTopic = insight?.topic || "General AI";
  const displayInsightStatus = insight?.insight_status || "unknown";
  const displayInsightStatusLabel = insight?.insight_status_label || "Status unknown";
  const displayInsightProcessingExplanation = getInsightProcessingExplanation(displayInsightStatus);
  const isStarred = Boolean(insight?.starred);
  const isManualInsight =
    !!insight?.is_manual ||
    displayInsightStatus === "manual_completed" ||
    displayInsightStatus === "manual_pending" ||
    insight?.source === "manual";
  const manualIntentItems = [
    insight?.upload_reason ? { label: "Upload reason", value: insight.upload_reason } : null,
    insight?.intended_use ? { label: "Intended use", value: insight.intended_use } : null,
    insight?.cognitive_layer
      ? { label: "Cognitive layer", value: formatCompactLabel(insight.cognitive_layer) }
      : null,
  ].filter((item): item is { label: string; value: string } => Boolean(item));

  const displayWhyItMatters =
    insight?.why_it_matters ||
    insight?.insight ||
    getInsightFallbackText(insight, "why_it_matters");

  const displayProjectRelevance =
    insight?.relevance_to_projects ||
    getInsightFallbackText(insight, "relevance_to_projects");

  const displayCareerRelevance =
    insight?.relevance_to_career ||
    getInsightFallbackText(insight, "relevance_to_career");

  const displayStrategicTakeaway =
    insight?.synthesized_insight ||
    insight?.strategy ||
    getInsightFallbackText(insight, "synthesized_insight");

  const cleanedDisplaySummary = normalizedDisplayText(displaySummary, "No summary available.");
  const cleanedWhyItMatters = normalizedDisplayText(displayWhyItMatters);
  const cleanedProjectRelevance = normalizedDisplayText(displayProjectRelevance);
  const cleanedCareerRelevance = normalizedDisplayText(displayCareerRelevance);
  const cleanedStrategicTakeaway = normalizedDisplayText(displayStrategicTakeaway);
  const finalTakeawaySignalId = insight?.signal_id || insight?.id || String(id);
  const hasGeneratedInsightContent = Boolean(
    insight?.why_it_matters ||
      insight?.insight ||
      insight?.relevance_to_projects ||
      insight?.relevance_to_career ||
      insight?.synthesized_insight ||
      insight?.strategy
  );
  const verifiedInsight =
    insight?.verification?.verified_insight ||
    insight?.policy_metadata?.verification?.verified_insight;
  const producedByModel = resolveModelProvenance(
    insight?.produced_by_model,
    insight?.verification?.produced_by_model,
    verifiedInsight?.produced_by_model,
    insight?.policy_metadata?.verification?.produced_by_model,
    insight?.policy_metadata?.verification?.verified_insight?.produced_by_model
  );
  const modelProvenanceLine = formatModelProvenance(producedByModel);
  const evidenceQuality =
    insight?.verification?.evidence_quality ||
    insight?.policy_metadata?.verification?.evidence_quality;
  const evidenceLevel = String(verifiedInsight?.evidence?.level || evidenceQuality?.level || "").toLowerCase();
  const hasEvidencePack = Boolean(insight?.evidence_pack);
  const hasEvidenceQuality = Boolean(evidenceQuality || verifiedInsight?.evidence);
  const isLowEvidence = evidenceLevel === "insufficient" || evidenceLevel === "thin";
  const lowEvidenceNotes =
    insight?.verification?.uncertainty_boundaries?.filter(Boolean) ||
    insight?.policy_metadata?.verification?.uncertainty_boundaries?.filter(Boolean) ||
    [];
  const evidenceReasonCodes = verifiedInsight?.evidence?.reason_codes || evidenceQuality?.reason_codes || [];
  const claimResults =
    verifiedInsight?.claims?.items ||
    insight?.verification?.claim_results ||
    insight?.policy_metadata?.verification?.claim_results ||
    [];
  const sortedClaimResults = [...claimResults].sort(
    (left, right) =>
      getClaimSupportRank(left.support_level) - getClaimSupportRank(right.support_level)
  );
  const claimSupportSummary =
    verifiedInsight?.claims?.support_summary ||
    insight?.verification?.claim_support_summary ||
    insight?.policy_metadata?.verification?.claim_support_summary ||
    {};
  const verificationLimitations =
    verifiedInsight?.limitations ||
    insight?.verification?.limitations ||
    insight?.policy_metadata?.verification?.limitations ||
    [];
  const downgradeReason =
    verifiedInsight?.downgrade?.reason ||
    insight?.verification?.downgrade_reason ||
    insight?.policy_metadata?.verification?.downgrade_reason;
  const verificationStatus =
    verifiedInsight?.status ||
    insight?.verification?.verification_status ||
    insight?.policy_metadata?.verification?.verification_status;
  const confidenceScore =
    verifiedInsight?.confidence?.score ??
    insight?.verification?.confidence_score ??
    insight?.policy_metadata?.verification?.confidence_score;
  const confidenceLabel =
    verifiedInsight?.confidence?.label ||
    insight?.verification?.confidence_label ||
    insight?.policy_metadata?.verification?.confidence_label;
  const allowedDownstreamActions =
    verifiedInsight?.action_policy?.allowed ||
    insight?.verification?.allowed_downstream_actions ||
    insight?.policy_metadata?.verification?.allowed_downstream_actions ||
    [];
  const blockedDownstreamActions =
    verifiedInsight?.action_policy?.blocked ||
    insight?.verification?.blocked_downstream_actions ||
    insight?.policy_metadata?.verification?.blocked_downstream_actions ||
    [];
  const projectReviewVerifiedInsight = buildProjectReviewVerifiedInsightFallback({
    existing: verifiedInsight,
    signalId: finalTakeawaySignalId,
    verificationStatus,
    evidenceLevel,
    evidenceQuality,
    claimResults,
    claimSupportSummary,
    confidenceScore,
    confidenceLabel,
    allowedActions: allowedDownstreamActions,
    blockedActions: blockedDownstreamActions,
    downgradeReason,
    limitations: verificationLimitations,
    producedByModel,
  });
  const reviewPriority = getReviewPriority({
    verificationStatus,
    blockedActions: blockedDownstreamActions,
    supportSummary: claimSupportSummary,
  });
  const reviewPriorityExplanation = getReviewPriorityExplanation({
    verificationStatus,
    blockedActions: blockedDownstreamActions,
    supportSummary: claimSupportSummary,
  });
  const verificationDecisionSummary = getVerificationDecisionSummary({
    verificationStatus,
    evidenceLevel,
    supportSummary: claimSupportSummary,
    allowedActions: allowedDownstreamActions,
    blockedActions: blockedDownstreamActions,
    downgradeReason: downgradeReason || null,
  });
  const claimSupportRows = getClaimSupportRows(claimSupportSummary);
  const claimCoverageSnapshot = getClaimCoverageSnapshot(claimResults);
  const presentationFidelitySummary = getPresentationFidelitySummary(claimResults);
  const sourceLimitsRecord = getSourceLimitsRecord(insight, presentationFidelitySummary);
  const gateSnapshotRows = getGateSnapshotRows(allowedDownstreamActions, blockedDownstreamActions);
  const completionRequiresVerificationReview = blockedDownstreamActions.some((action) =>
    ["strong_recommendation", "decision_card", "low_risk_action_candidate"].includes(action)
  );
  const completionGateMessage =
    "Verification blocks action-oriented outputs for this insight. Review the claim checks before completing it into Workspace.";
  const hasCompletionNote = Boolean(reflection.trim());
  const externalSynthesisSavedText = (externalSynthesisSource?.source_text || "").trim();
  const externalSynthesisPreviewText =
    externalSynthesisSavedText.length > 420
      ? `${externalSynthesisSavedText.slice(0, 420).trim()}...`
      : externalSynthesisSavedText;
  const externalSynthesisDraftText = externalSynthesisText.trim();
  const externalSynthesisLineItems = externalSynthesisDraftText
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  const externalSynthesisSentenceCount = (externalSynthesisDraftText.match(/[.!?。！？](\s|$)/g) || []).length;
  const externalSynthesisDependencyLineCount = externalSynthesisLineItems.filter((line) =>
    /^[a-z0-9_.-]+\s*(==|>=|<=|~=|>|<|=)\s*[^,\s]+/i.test(line)
  ).length;
  const externalSynthesisConfigLineCount = externalSynthesisLineItems.filter((line) =>
    /^[a-z0-9_.-]+\s*[:=]\s*\S+/i.test(line)
  ).length;
  const externalSynthesisFileNameLower = externalSynthesisFileName.toLowerCase();
  const externalSynthesisLooksLikeDependencyFile =
    /(^|[\\/])(requirements|package-lock|yarn|poetry|pipfile|composer|gemfile)(\..*)?$/i.test(externalSynthesisFileNameLower) ||
    externalSynthesisDependencyLineCount >= Math.max(2, Math.ceil(externalSynthesisLineItems.length * 0.6));
  const externalSynthesisLooksLikeConfig =
    /\.(json|ya?ml|toml|ini|env|lock|log)$/i.test(externalSynthesisFileNameLower) ||
    externalSynthesisConfigLineCount >= Math.max(3, Math.ceil(externalSynthesisLineItems.length * 0.55));
  const externalSynthesisLooksTooShort =
    Boolean(externalSynthesisDraftText) &&
    externalSynthesisDraftText.length < 180 &&
    externalSynthesisSentenceCount < 2;
  const externalSynthesisDraftTextLower = externalSynthesisDraftText.toLowerCase();
  const externalSynthesisUiChromePhrases = [
    "claude is ai and can make mistakes",
    "new chat",
    "customize",
    "recents",
    "all chats",
    "projects",
    "artifacts",
    "share",
    "content",
    "search",
  ];
  const externalSynthesisUiChromeHitCount = externalSynthesisUiChromePhrases.filter((phrase) =>
    externalSynthesisDraftTextLower.includes(phrase)
  ).length;
  const externalSynthesisLooksLikeUiDump =
    externalSynthesisUiChromeHitCount >= 4 ||
    (externalSynthesisFileNameLower.endsWith(".html") && externalSynthesisUiChromeHitCount >= 2);
  const externalSynthesisMojibakeCount = (externalSynthesisDraftText.match(/[\ufffd]/g) || []).length;
  const externalSynthesisLooksEncodingDamaged =
    externalSynthesisMojibakeCount >= 3 ||
    externalSynthesisDraftTextLower.includes("mojibake");
  const externalSynthesisTopicStopWords = [
    "with",
    "from",
    "that",
    "this",
    "into",
    "built",
    "first",
    "using",
    "what",
    "when",
    "where",
    "signal",
    "signals",
    "intelligence",
    "evidence",
  ];
  const externalSynthesisTopicTerms = Array.from(
    new Set((`${displayTitle} ${cleanedDisplaySummary}`.toLowerCase().match(/[a-z0-9][a-z0-9_-]{3,}/g) || []))
  )
    .filter((term) => !externalSynthesisTopicStopWords.includes(term))
    .slice(0, 24);
  const externalSynthesisTopicHitCount = externalSynthesisTopicTerms.filter((term) =>
    externalSynthesisDraftTextLower.includes(term)
  ).length;
  const externalSynthesisLooksOffTopic =
    externalSynthesisDraftText.length > 900 &&
    externalSynthesisTopicTerms.length >= 4 &&
    externalSynthesisTopicHitCount <= Math.max(1, Math.floor(externalSynthesisTopicTerms.length * 0.1));
  const externalSynthesisQualityFlags = [
    externalSynthesisLooksLikeUiDump
      ? {
          code: "chat_export_ui_dump",
          label: "Chat export / UI dump",
          detail:
            "This source looks like a chat export or captured app UI, not focused synthesis for this signal.",
        }
      : null,
    externalSynthesisLooksEncodingDamaged
      ? {
          code: "encoding_damaged_text",
          label: "Encoding-damaged text",
          detail: "This source appears to contain encoding damage or mojibake.",
        }
      : null,
    externalSynthesisLooksOffTopic
      ? {
          code: "weak_topical_overlap",
          label: "Weak topical overlap",
          detail: "This source has weak topical overlap with the current signal.",
        }
      : null,
    externalSynthesisLooksLikeDependencyFile
      ? {
          code: "dependency_or_package_text",
          label: "Dependency/package text",
          detail: "This source looks like dependency text, not long-form synthesis.",
        }
      : null,
    externalSynthesisLooksLikeConfig
      ? {
          code: "config_or_log_text",
          label: "Config/log text",
          detail: "This source looks like config or log text, not long-form synthesis.",
        }
      : null,
    externalSynthesisLooksTooShort
      ? {
          code: "short_source_text",
          label: "Short source text",
          detail: "This source is short for long-form synthesis.",
        }
      : null,
  ].filter(Boolean) as ExternalSynthesisQualityFlag[];
  const externalSynthesisQualitySummary = externalSynthesisQualityFlags.length
    ? `${externalSynthesisQualityFlags[0].detail} Save anyway only if it is intentional review context.`
    : externalSynthesisDraftText
      ? "No source-shape warning detected for this External Synthesis Source."
      : "No External Synthesis Source text available for quality assessment.";
  const externalSynthesisQualityAssessmentBase: ExternalSynthesisQualityAssessment = {
    schema_version: 1,
    status: externalSynthesisDraftText ? (externalSynthesisQualityFlags.length ? "warning" : "clean") : "not_attached",
    summary: externalSynthesisQualitySummary,
    flags: externalSynthesisQualityFlags,
    effect: "non_blocking_review_context_warning",
    evidence_boundary: "review_context_not_verified_evidence",
    review_context_only: true,
    not_verified_evidence: true,
    checked_text_length: externalSynthesisDraftText.length,
    source_file: externalSynthesisFileName,
    source_kind: inferExternalSynthesisKind(externalSynthesisFileName),
    topic_terms_checked: externalSynthesisTopicTerms,
    topic_hit_count: externalSynthesisTopicHitCount,
  };
  const buildExternalSynthesisQualityAssessment = (): ExternalSynthesisQualityAssessment => ({
    ...externalSynthesisQualityAssessmentBase,
    checked_at: new Date().toISOString(),
  });
  const externalSynthesisContentWarning =
    externalSynthesisQualityAssessmentBase.status === "warning" ? externalSynthesisQualityAssessmentBase.summary : "";
  const savedExternalSynthesisSource = externalSynthesisSource?.external_synthesis_source_id
    ? externalSynthesisSource
    : null;
  const hasSavedExternalSynthesisSource = Boolean(savedExternalSynthesisSource);
  const savedExternalSynthesisQuality =
    savedExternalSynthesisSource?.metadata?.external_synthesis_quality || externalSynthesisQualityAssessmentBase;
  const reviewBundleSnapshotQuality = reviewBundleSnapshot?.metadata?.external_synthesis_quality;
  const externalSynthesisSavedMatchesDraft =
    Boolean(savedExternalSynthesisSource) &&
    externalSynthesisDraftText === (savedExternalSynthesisSource?.source_text || "").trim() &&
    (!externalSynthesisFileName || externalSynthesisFileName === (savedExternalSynthesisSource?.source_file || ""));
  const hasUnsavedExternalSynthesisDraft =
    Boolean(externalSynthesisDraftText) && !externalSynthesisSavedMatchesDraft;
  const externalSynthesisArchivedInBundleOnly =
    !hasSavedExternalSynthesisSource && Boolean(confirmedFinalTakeaway || reviewBundleSnapshot?.snapshot_id);
  const signalCompleted = normalizeStatus(localStatus) === "completed";
  const finalTakeawayPrerequisiteMessage = !signalCompleted
    ? "Complete Signal before generating a Final Takeaway Review Bundle."
    : hasUnsavedExternalSynthesisDraft
      ? "Save or clear the External Synthesis Source before generating a Review Bundle."
      : "";
  const finalTakeawayPrerequisitesMet = !finalTakeawayPrerequisiteMessage;
  const saveMessageIsError = /failed|cannot reach|error/i.test(saveMessage);
  const projectTakeawayBlocked = blockedDownstreamActions.includes("project_takeaway_candidate");
  const projectTakeawayAllowed = allowedDownstreamActions.includes("project_takeaway_candidate");
  const projectTakeawayReviewBlocked = reviewPriority.label === "Do Not Act";
  const hasProjectTakeawayText = Boolean(cleanedProjectRelevance.trim() || cleanedStrategicTakeaway.trim());
  const unsupportedProjectClaimCount =
    (claimSupportSummary.unsupported || 0) + (claimSupportSummary.contradicted || 0);
  const projectTakeawayGateMessage = getProjectTakeawayGateMessage({
    allowed: projectTakeawayAllowed,
    blocked: projectTakeawayBlocked,
    reviewPriorityLabel: reviewPriority.label,
    hasProjectText: hasProjectTakeawayText,
    candidateCreated: projectCandidateCreated,
    unsupportedCount: unsupportedProjectClaimCount,
    verificationStatus,
    blockedActions: blockedDownstreamActions,
  });
  const projectTakeawaySnapshot = gateSnapshotRows.find((row) => row.action === "project_takeaway_candidate");
  const lowRiskActionSnapshot = gateSnapshotRows.find((row) => row.action === "low_risk_action_candidate");
  const verifiedInsightClaimCount =
    claimResults.length ||
    verifiedInsight?.claims?.count ||
    Object.values(claimSupportSummary).reduce((total, count) => total + (Number.isFinite(count) ? count : 0), 0);
  const verifiedInsightObjectRows: VerifiedInsightObjectRow[] = [
    {
      label: "Verification",
      value: formatCompactLabel(verificationStatus),
      detail: "Current verified_insight.status or verification_status.",
      tone: getVerificationObjectTone(verificationStatus, blockedDownstreamActions),
    },
    {
      label: "Evidence",
      value: formatCompactLabel(evidenceLevel || "unknown"),
      detail:
        typeof confidenceScore === "number"
          ? `${formatCompactLabel(confidenceLabel)} confidence (${confidenceScore.toFixed(2)}).`
          : `${formatCompactLabel(confidenceLabel)} confidence.`,
      tone: isLowEvidence ? "watch" : hasEvidenceQuality ? "good" : "neutral",
    },
    {
      label: "Claims",
      value: verifiedInsightClaimCount > 0 ? `${verifiedInsightClaimCount} checked` : "Not checked",
      detail: formatClaimSupportSummary(claimSupportSummary) || "No claim-support summary is attached.",
      tone: unsupportedProjectClaimCount > 0 ? "bad" : verifiedInsightClaimCount > 0 ? "good" : "neutral",
    },
    {
      label: "Project Takeaway",
      value: projectTakeawaySnapshot?.status || "Not recorded",
      detail: projectTakeawayGateMessage,
      tone: projectTakeawaySnapshot?.tone || "neutral",
    },
    {
      label: "Low-risk Action",
      value: lowRiskActionSnapshot?.status || "Not recorded",
      detail: lowRiskActionSnapshot?.detail || "Not present in the current gate metadata.",
      tone: lowRiskActionSnapshot?.tone || "neutral",
    },
  ];
  const showVerificationObjectSurface = Boolean(
    verifiedInsight ||
      verificationStatus ||
      hasEvidenceQuality ||
      hasEvidencePack ||
      allowedDownstreamActions.length ||
      blockedDownstreamActions.length ||
      claimResults.length
  );
  const canCreateProjectTakeawayCandidate =
    projectTakeawayAllowed &&
    !projectTakeawayBlocked &&
    !projectTakeawayReviewBlocked &&
    hasProjectTakeawayText &&
    !projectCandidateCreated;
  const projectTakeawayManualOverrideNeeded =
    hasProjectTakeawayText &&
    !projectCandidateCreated &&
    !canCreateProjectTakeawayCandidate;
  const projectTakeawayManualOverrideReason = buildProjectTakeawayManualOverrideReason({
    allowed: projectTakeawayAllowed,
    blocked: projectTakeawayBlocked,
    reviewPriorityLabel: reviewPriority.label,
    unsupportedCount: unsupportedProjectClaimCount,
    verificationStatus,
    blockedActions: blockedDownstreamActions,
  });
  const deepProjectMatchReview = buildDeepProjectMatchReview({
    signal: insight,
    projectText: cleanedProjectRelevance,
    strategicText: cleanedStrategicTakeaway,
    claimResults,
    evidenceLevel,
    blockedActions: blockedDownstreamActions,
  });
  const showDeepProjectMatchReview =
    deepProjectMatchReview.status !== "not_project_related" && deepProjectMatchReview.required;
  const deepProjectMatchReviewNoteValue =
    deepProjectMatchReviewNote.trim() || deepProjectMatchReview.suggestedReviewNote;
  const deepProjectMatchReviewMetadata = showDeepProjectMatchReview
    ? {
        required: deepProjectMatchReview.required,
        status: deepProjectMatchReview.status,
        posture: deepProjectMatchReview.posture,
        reason: deepProjectMatchReview.reason,
        matched_projects: deepProjectMatchReview.matchedProjects,
        relevant_modules: deepProjectMatchReview.relevantModules,
        match_type: deepProjectMatchReview.matchType,
        evidence_boundary: deepProjectMatchReview.evidenceBoundary,
        downstream_posture: deepProjectMatchReview.downstreamPosture,
        checklist: deepProjectMatchReview.checklist,
        generated_analysis: deepProjectMatchAnalysis,
        generated_analysis_layers: deepProjectMatchAnalysisLayers,
        review_note: deepProjectMatchReviewNoteValue,
        review_note_effect: "review_context_only",
        source: "signal_detail",
      }
    : null;

  const buildVerificationMetadata = (extra: Record<string, unknown> = {}) => ({
    verified_insight: projectReviewVerifiedInsight,
    produced_by_model: producedByModel.provenance_schema_version === 1 ? producedByModel : null,
    verification_status: verificationStatus || null,
    confidence_label: confidenceLabel || null,
    confidence_score: typeof confidenceScore === "number" ? confidenceScore : null,
    review_priority: reviewPriority.label,
    blocked_downstream_actions: blockedDownstreamActions,
    allowed_downstream_actions: allowedDownstreamActions,
    claim_support_summary: claimSupportSummary,
    downgrade_reason: downgradeReason || null,
    limitations: verificationLimitations,
    deep_project_match_review: deepProjectMatchReviewMetadata,
    ...extra,
  });

  const handleExternalSynthesisFileChange = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    const lowerName = file.name.toLowerCase();
    const supported = lowerName.endsWith(".md") || lowerName.endsWith(".markdown") || lowerName.endsWith(".txt") || lowerName.endsWith(".html") || lowerName.endsWith(".htm");
    if (!supported) {
      setExternalSynthesisError("Use a .md, .txt, or .html external synthesis file.");
      return;
    }

    try {
      const text = await file.text();
      setExternalSynthesisText(text);
      setExternalSynthesisFileName(file.name);
      setExternalSynthesisSource(null);
      setExternalSynthesisError("");
      setExternalSynthesisMessage("External synthesis file loaded. Review it, then save source.");
    } catch (error: unknown) {
      setExternalSynthesisError(getErrorMessage(error, "Failed to read external synthesis file."));
    } finally {
      event.target.value = "";
    }
  };

  const handleSaveExternalSynthesisSource = async () => {
    const sourceText = externalSynthesisText.trim();
    if (!sourceText) {
      setExternalSynthesisError("Paste or upload external synthesis text before saving.");
      setExternalSynthesisMessage("");
      return;
    }

    setExternalSynthesisSaving(true);
    setExternalSynthesisError("");
    setExternalSynthesisMessage("");

    try {
      const res = await adminFetch(`${API_BASE}/final-takeaways/external-synthesis-sources`, {
        method: "POST",
        headers: buildJsonAdminHeaders(),
        body: JSON.stringify({
          signal_id: finalTakeawaySignalId,
          source_text: sourceText,
          source_file: externalSynthesisFileName,
          source_kind: inferExternalSynthesisKind(externalSynthesisFileName),
          content_type: "",
          created_by: "Andy",
          metadata: {
            source_surface: "signal_detail_final_takeaway",
            review_context_only: true,
            not_verified_evidence: true,
            external_synthesis_quality: buildExternalSynthesisQualityAssessment(),
          },
        }),
      });
      const data = (await readApiResponse(res)) as { source?: ExternalSynthesisSource; detail?: string; message?: string };
      if (!res.ok || !data.source) {
        throw new Error(String(data.detail || data.message || `Failed to save External Synthesis Source. HTTP ${res.status}`));
      }
      setExternalSynthesisSource(data.source);
      setExternalSynthesisText(data.source.source_text || sourceText);
      setExternalSynthesisFileName(data.source.source_file || externalSynthesisFileName);
      setExternalSynthesisMessage(`External Synthesis Source saved: ${data.source.external_synthesis_source_id || "saved"}.`);
    } catch (error: unknown) {
      setExternalSynthesisError(getErrorMessage(error, "Failed to save External Synthesis Source."));
    } finally {
      setExternalSynthesisSaving(false);
    }
  };

  const buildReviewBundleDraft = () => {
    const verificationSnapshot = buildVerificationMetadata({
      final_takeaway_review_bundle_source: "signal_detail",
      external_synthesis_source_id: externalSynthesisSource?.external_synthesis_source_id || null,
      external_synthesis_boundary: externalSynthesisSource?.evidence_boundary || null,
    });
    const externalSynthesisBlock = externalSynthesisSource?.external_synthesis_source_id
      ? [
          "## External Synthesis Source",
          `- source_id: ${externalSynthesisSource.external_synthesis_source_id}`,
          `- source_file: ${externalSynthesisSource.source_file || "paste"}`,
          `- source_kind: ${externalSynthesisSource.source_kind || "external_synthesis"}`,
          `- normalized_hash: ${externalSynthesisSource.normalized_content_hash || "unknown"}`,
          `- evidence_boundary: ${externalSynthesisSource.evidence_boundary || "review_context_not_verified_evidence"}`,
          "",
          externalSynthesisSource.source_text || externalSynthesisText.trim(),
        ]
      : [
          "## External Synthesis Source",
          "No external synthesis source attached. Paste or upload one before snapshot if this Final Takeaway depends on long-form external review.",
        ];
    const discussionSummary = [
      `Claude messages: ${claudeMessages.length}`,
      `ChatGPT messages: ${chatgptMessages.length}`,
      `Perplexity messages: ${perplexityMessages.length}`,
    ].join("\n");
    return [
      "# Final Takeaway Review Bundle",
      "",
      "## Source Signal",
      `- signal_id: ${finalTakeawaySignalId}`,
      `- signal_title: ${displayTitle}`,
      "",
      "## Completion Note Draft",
      reflection.trim() || "Not written yet.",
      "",
      "## AI Radar Discussion Summary",
      discussionSummary,
      "",
      "## Claude Client Review",
      "External Claude client review not attached in this draft.",
      "",
      "## Codex Review",
      "Codex repo-grounded review not attached in this draft.",
      "",
      ...externalSynthesisBlock,
      "",
      "## Andy Synthesis",
      finalTakeawayText.trim() || reflection.trim() || "Not confirmed yet.",
      "",
      "## Structured Insight",
      `### Signal Summary\n${cleanedDisplaySummary}`,
      `### Why It Matters\n${cleanedWhyItMatters || "Missing."}`,
      `### Relevance To Projects\n${cleanedProjectRelevance || "Missing."}`,
      `### Relevance To Career\n${cleanedCareerRelevance || "Missing."}`,
      `### Strategic Takeaway\n${cleanedStrategicTakeaway || "Missing."}`,
      "",
      "## Deep Project Match Context",
      `- required: ${String(deepProjectMatchReview.required)}`,
      `- status: ${deepProjectMatchReview.status}`,
      `- posture: ${deepProjectMatchReview.posture}`,
      `- match_type: ${deepProjectMatchReview.matchType}`,
      `- evidence_boundary: ${deepProjectMatchReview.evidenceBoundary}`,
      `- generated_analysis_attached: ${deepProjectMatchAnalysis ? "yes" : "no"}`,
      "",
      deepProjectMatchReviewNoteValue || deepProjectMatchReview.reason || "No deep match review note.",
      "",
      "## Verification Snapshot",
      "```json",
      JSON.stringify(verificationSnapshot, null, 2),
      "```",
      "",
      "## Confirmation",
      "- confirmed_by: Andy",
      "- confirmed_at: pending",
      "- decision: pending",
    ].join("\n");
  };

  const handleGenerateReviewBundleDraft = () => {
    if (!finalTakeawayPrerequisitesMet) {
      setReviewBundleError(finalTakeawayPrerequisiteMessage);
      setReviewBundleMessage("");
      return;
    }
    setReviewBundleText(buildReviewBundleDraft());
    setReviewBundleError("");
    setReviewBundleMessage("Review Bundle draft generated. Review or edit it, then create an immutable snapshot.");
    if (!finalTakeawayText.trim() && reflection.trim()) {
      setFinalTakeawayText(reflection.trim());
    }
  };

  const handleCreateReviewBundleSnapshot = async () => {
    if (!finalTakeawayPrerequisitesMet) {
      setReviewBundleError(finalTakeawayPrerequisiteMessage);
      setReviewBundleMessage("");
      return;
    }
    const sourceText = reviewBundleText.trim();
    if (!sourceText) {
      setReviewBundleError("Generate or paste a Review Bundle markdown draft first.");
      setReviewBundleMessage("");
      return;
    }

    setReviewBundleSaving(true);
    setReviewBundleError("");
    setReviewBundleMessage("");
    setFinalTakeawayError("");

    try {
      const res = await adminFetch(`${API_BASE}/final-takeaways/review-bundle-snapshots`, {
        method: "POST",
        headers: buildJsonAdminHeaders(),
        body: JSON.stringify({
          signal_id: finalTakeawaySignalId,
          source_text: sourceText,
          source_kind: "signal_detail_generated_md",
          snapshot_reason: "final_takeaway_review_bundle",
          used_by: "confirmed_final_takeaway",
          created_by: "Andy",
          conversation_refs: [
            {
              source: "ai_radar_discussion",
              signal_id: finalTakeawaySignalId,
              claude_message_count: claudeMessages.length,
              chatgpt_message_count: chatgptMessages.length,
              perplexity_message_count: perplexityMessages.length,
            },
          ],
          metadata: {
            has_generated_insight_content: hasGeneratedInsightContent,
            has_deep_project_match_analysis: Boolean(deepProjectMatchAnalysis),
            external_synthesis_source_id: externalSynthesisSource?.external_synthesis_source_id || "",
            external_synthesis_content_hash: externalSynthesisSource?.normalized_content_hash || "",
            external_synthesis_evidence_boundary: externalSynthesisSource?.evidence_boundary || "",
            external_synthesis_quality: buildExternalSynthesisQualityAssessment(),
            verification_status: verificationStatus || "",
            review_priority: reviewPriority.label,
          },
        }),
      });
      const data = (await readApiResponse(res)) as { snapshot?: ReviewBundleSnapshot; detail?: string; message?: string };
      if (!res.ok || !data.snapshot) {
        throw new Error(String(data.detail || data.message || `Failed to create Review Bundle snapshot. HTTP ${res.status}`));
      }
      setReviewBundleSnapshot(data.snapshot);
      setReviewBundleMessage(`Immutable Review Bundle snapshot created: ${data.snapshot.snapshot_id || "saved"}.`);
    } catch (error: unknown) {
      setReviewBundleError(getErrorMessage(error, "Failed to create Review Bundle snapshot."));
    } finally {
      setReviewBundleSaving(false);
    }
  };

  const handleConfirmFinalTakeaway = async () => {
    const confirmedText = finalTakeawayText.trim() || reflection.trim();
    if (!finalTakeawayPrerequisitesMet) {
      setFinalTakeawayError(finalTakeawayPrerequisiteMessage);
      setFinalTakeawayMessage("");
      return;
    }
    if (!reviewBundleSnapshot?.snapshot_id) {
      setFinalTakeawayError("Create a Review Bundle snapshot before confirming the Final Takeaway.");
      setFinalTakeawayMessage("");
      return;
    }
    if (!confirmedText) {
      setFinalTakeawayError("Write a Final Takeaway or Completion Note before confirming.");
      setFinalTakeawayMessage("");
      return;
    }

    setFinalTakeawayConfirming(true);
    setFinalTakeawayError("");
    setFinalTakeawayMessage("");

    try {
      const res = await adminFetch(`${API_BASE}/final-takeaways/confirm`, {
        method: "POST",
        headers: buildJsonAdminHeaders(),
        body: JSON.stringify({
          signal_id: finalTakeawaySignalId,
          confirmed_text: confirmedText,
          review_bundle_snapshot_id: reviewBundleSnapshot.snapshot_id,
          source_completion_note: reflection,
          confirmed_by: "Andy",
          source_signal_id: finalTakeawaySignalId,
          provenance: {
            source: "signal_detail",
            completion_note_used: Boolean(reflection.trim()),
            has_generated_insight_content: hasGeneratedInsightContent,
            has_deep_project_match_analysis: Boolean(deepProjectMatchAnalysis),
            review_bundle_content_hash: reviewBundleSnapshot.content_hash || "",
          },
        }),
      });
      const data = (await readApiResponse(res)) as { final_takeaway?: FinalTakeawayArtifact; detail?: string; message?: string };
      if (!res.ok || !data.final_takeaway) {
        throw new Error(String(data.detail || data.message || `Failed to confirm Final Takeaway. HTTP ${res.status}`));
      }
      setConfirmedFinalTakeaway(data.final_takeaway);
      setFinalTakeawayText(data.final_takeaway.confirmed_text || confirmedText);
      setFinalTakeawayMessage(`Final Takeaway confirmed: ${data.final_takeaway.final_takeaway_id || "saved"}.`);
    } catch (error: unknown) {
      setFinalTakeawayError(getErrorMessage(error, "Failed to confirm Final Takeaway."));
    } finally {
      setFinalTakeawayConfirming(false);
    }
  };

  const updateClaimFeedbackDraft = (key: string, patch: Partial<ClaimFeedbackDraft>) => {
    setClaimFeedbackDrafts((current) => ({
      ...current,
      [key]: buildDefaultClaimFeedbackDraft({
        ...(current[key] || {}),
        ...patch,
      }),
    }));
  };

  const handleSubmitClaimFeedback = async (claim: ClaimCheckItem, claimIndex: number) => {
    const key = getClaimFeedbackKey(claim, claimIndex);
    const claimRecordId = getClaimFeedbackRecordId(claim, claimIndex);
    const draft = claimFeedbackDrafts[key] || buildDefaultClaimFeedbackDraft({ open: true });
    const note = draft.note.trim();

    if (!insight) {
      updateClaimFeedbackDraft(key, { open: true, error: "Signal detail is still loading.", message: "" });
      return;
    }
    if (!note) {
      updateClaimFeedbackDraft(key, { open: true, error: "Add a short note before recording feedback.", message: "" });
      return;
    }

    updateClaimFeedbackDraft(key, { submitting: true, error: "", message: "" });

    try {
      const res = await adminFetch(`${API_BASE}/signal-review-feedback`, {
        method: "POST",
        headers: buildJsonAdminHeaders(),
        body: JSON.stringify({
          signal_id: insight.signal_id || insight.id || String(id),
          insight_id: verifiedInsight?.id || insight.id || "",
          content_fingerprint: producedByModel.deterministic_fingerprint || "",
          claim_id: claimRecordId,
          claim_text_snapshot: normalizedDisplayText(claim.claim_text, "Claim text unavailable."),
          claim_source_field: claim.source_field || claim.claim_type || "",
          reason_slot: draft.reasonSlot,
          distortion_tags: [],
          note,
          verification_snapshot: buildVerificationMetadata({
            feedback_capture_source: "signal_detail_claim_checks",
            feedback_claim_id: claimRecordId,
            feedback_claim_support_level: claim.support_level || null,
          }),
          input_provenance_snapshot: buildSignalInputProvenanceSnapshot(insight),
        }),
      });

      const data = await readApiResponse(res);
      if (!res.ok) {
        throw new Error(String(data.detail || data.message || `Failed to record feedback. HTTP ${res.status}`));
      }

      const savedRecord = isRecord(data.record)
        ? {
            id: String(data.record.id || ""),
            claim_id: String(data.record.claim_id || claimRecordId),
            reason_slot: String(data.record.reason_slot || draft.reasonSlot),
            note: String(data.record.note || note),
            created_at: String(data.record.created_at || ""),
          }
        : null;
      if (savedRecord) {
        setClaimFeedbackRecords((current) => [
          savedRecord,
          ...current.filter((record) => record.id !== savedRecord.id),
        ]);
      }
      updateClaimFeedbackDraft(key, {
        open: false,
        submitting: false,
        submitted: true,
        message: "Feedback recorded.",
        error: "",
      });
    } catch (error: unknown) {
      updateClaimFeedbackDraft(key, {
        submitting: false,
        submitted: false,
        message: "",
        error: getErrorMessage(error, "Failed to record feedback."),
      });
    }
  };

  const manualInsightMissing =
    isManualInsight &&
    !String(insight?.why_it_matters || insight?.insight || "").trim() &&
    !String(insight?.relevance_to_projects || "").trim() &&
    !String(insight?.relevance_to_career || "").trim() &&
    !String(insight?.synthesized_insight || insight?.strategy || "").trim();
  const manualSessionSourceNote = isManualInsight && insight?.manual_session_id
    ? `Derived from Manual Session ${insight.manual_session_id}. Open the manual session when you need uploaded files, upload intent, or first-analysis context.`
    : "";
  const manualGenerationNote = isManualInsight
    ? insight?.generation_mode === "fallback"
      ? "Current generation mode is fallback. Regenerate from Signal Detail or Manual Detail for a stronger model pass."
      : insight?.provider_used || insight?.model_used
        ? `Latest manual insight route: ${insight.provider_used || "provider unknown"}${insight.model_used ? ` / ${insight.model_used}` : ""}.`
        : "Generation route metadata is not saved on this manual signal yet. Regenerate the insight to attach provider/model metadata."
    : "";
  const workspaceRecordFileName = insight?.workspace_file_name || "";
  const hasWorkspaceRecord = Boolean(insight?.workspace_saved && workspaceRecordFileName);
  const workspaceRecordHref = hasWorkspaceRecord
    ? `/workspace/detail?file_name=${encodeURIComponent(workspaceRecordFileName)}`
    : "";
  const reviewInboxHref = `/workspace/projects/review?signal_id=${encodeURIComponent(reviewFocusId || insight?.signal_id || insight?.id || String(id))}`;
  const manualProjectTakeawayHandoff = isManualInsight
    ? hasWorkspaceRecord
      ? "Workspace record saved. Use the record as the durable artifact; create new Project Takeaway review only if a fresh project decision is still needed."
      : canCreateProjectTakeawayCandidate
        ? "Ready for Project Review after Andy confirms a Final Takeaway. Use the Final Takeaway Confirmation panel as the handoff entry."
        : projectTakeawayManualOverrideNeeded
          ? `Final Takeaway handoff needs explicit override before Project Review: ${projectTakeawayManualOverrideReason}.`
          : manualInsightMissing
            ? "Generate the missing insight sections before routing this manual upload into Project Takeaway review."
            : "Keep as observation for now. Final Takeaway handoff needs project-relevant text and gate review."
    : "";
  const manualSignalNextAction = isManualInsight
    ? hasWorkspaceRecord
      ? "Next action: review the saved Workspace record as the durable artifact for this manual-derived intelligence."
      : manualInsightMissing
        ? "Next action: generate the missing insight sections before completing this manual-derived signal."
        : "Next action: review the Evidence Note and completion note, then use Complete Signal when this should become a Workspace record."
    : "";
  const manualSignalHandoffStage = isManualInsight
    ? hasWorkspaceRecord
      ? {
          label: "Workspace Done",
          tone: "done",
          body: "This manual upload already has a durable Workspace record. Use the record as the canonical artifact.",
        }
      : manualInsightMissing
        ? {
            label: "Needs Insight",
            tone: "warning",
            body: "Structured insight sections are missing. Generate insight before review, Project Takeaway routing, or Workspace completion.",
          }
        : canCreateProjectTakeawayCandidate
          ? {
              label: "Ready For Signal Review",
              tone: "ready",
              body: "Structured insight exists; review the Evidence Note, completion note, and Project Takeaway Gate before Workspace completion or Project Takeaway routing.",
            }
          : projectTakeawayManualOverrideNeeded
            ? {
                label: "Review Before Handoff",
                tone: "warning",
                body: "The conservative gate wants human review before Project Takeaway routing. Complete to Workspace only after reviewing the claim checks.",
              }
            : {
                label: "Signal Review",
                tone: "neutral",
                body: "Review the Evidence Note and completion note before deciding whether this should become a durable Workspace artifact.",
              }
    : null;

  const displayUrl = insight?.url || insight?.link || insight?.source_url || "";

  const statusLabel = useMemo(() => getStatusLabel(localStatus), [localStatus]);
  const normalizedLocalStatus = normalizeStatus(localStatus);
  const decisionLockKind =
    normalizedLocalStatus === "rejected" || normalizedLocalStatus === "saved" || (normalizedLocalStatus === "analyzed" && decisionLockActive)
      ? normalizedLocalStatus
      : "";
  const decisionLockLabel =
    decisionLockKind === "saved"
      ? "saved"
      : decisionLockKind === "analyzed"
        ? "processed"
        : decisionLockKind === "rejected"
          ? "rejected"
          : "";
  const isRejectedLocked = !!decisionLockKind && !decisionEditingUnlocked;
  const actionDisabledReason = isRejectedLocked
    ? `This signal is ${decisionLockLabel}. Confirm Enable Editing before making changes.`
    : "";
  const finalTakeawayArtifactLocked = Boolean(confirmedFinalTakeaway?.final_takeaway_id);
  const completionNoteLocked = isRejectedLocked || signalCompleted || finalTakeawayArtifactLocked;
  const completionNoteDisabledReason = finalTakeawayArtifactLocked
    ? "A Final Takeaway artifact is already confirmed. Use the Final Takeaway handoff path instead of editing or completing the Completion Note."
    : signalCompleted
    ? "This signal is completed. Completion Note editing is locked."
    : actionDisabledReason;
  const canClickFinalTakeawayHandoff =
    Boolean(confirmedFinalTakeaway?.final_takeaway_id) &&
    (canCreateProjectTakeawayCandidate || projectTakeawayManualOverrideNeeded) &&
    (!projectTakeawayManualOverrideNeeded || projectTakeawayOverrideConfirmed) &&
    !projectCandidateCreated &&
    !projectCandidateCreating &&
    !isRejectedLocked &&
    signalCompleted;

  useEffect(() => {
    const normalized = normalizeStatus(localStatus);
    if (normalized !== "rejected" && normalized !== "saved" && normalized !== "analyzed") {
      setDecisionEditingUnlocked(false);
      setDecisionLockActive(false);
    }
  }, [localStatus]);

  const buildWorkspacePayload = (
    model: string,
    message: string,
    reflectionOverride?: string,
    conversationIntent: ConversationIntent = "artifact",
    recentMessages: ChatMessage[] = []
  ) => ({
    model,
    message,
    conversation_intent: conversationIntent,
    recent_messages: recentMessages.map((item) => ({
      role: item.role,
      content: item.content,
    })),
    signal_title: displayTitle,
    signal_summary: cleanedDisplaySummary,
    why_it_matters: cleanedWhyItMatters,
    relevance_to_projects: cleanedProjectRelevance,
    relevance_to_career: cleanedCareerRelevance,
    synthesized_insight: cleanedStrategicTakeaway,
    reflection: reflectionOverride ?? reflection,
  });

  const buildVisualPayload = () => ({
    signal_id: insight?.signal_id || insight?.id || String(id),
    signal_title: displayTitle,
    signal_summary: cleanedDisplaySummary,
    why_it_matters: cleanedWhyItMatters,
    relevance_to_projects: cleanedProjectRelevance,
    relevance_to_career: cleanedCareerRelevance,
    synthesized_insight: cleanedStrategicTakeaway,
    reflection,
    visual_style: visualStyle,
    visual_direction: visualDirection.trim() || null,
  });

  const buildChatHistoryPayload = (model: ModelKey, messages: ChatMessage[]) => ({
    model,
    signal_id: insight?.signal_id || insight?.id || String(id),
    signal_title: displayTitle,
    signal_summary: cleanedDisplaySummary,
    why_it_matters: cleanedWhyItMatters,
    relevance_to_projects: cleanedProjectRelevance,
    relevance_to_career: cleanedCareerRelevance,
    synthesized_insight: cleanedStrategicTakeaway,
    reflection,
    messages,
  });

  const persistChatHistory = async (model: ModelKey, messages: ChatMessage[]) => {
    try {
      await adminFetch(`${API_BASE}/workspace_chat_history`, {
        method: "POST",
        headers: buildJsonAdminHeaders(),
        body: JSON.stringify(buildChatHistoryPayload(model, messages)),
      });
    } catch (error) {
      console.error(`Failed to persist ${model} chat history:`, error);
    }
  };

  const deletePersistedChatHistory = async (model: ModelKey) => {
    try {
      await adminFetch(
        `${API_BASE}/workspace_chat_history/${encodeURIComponent(String(id))}?model=${encodeURIComponent(model)}`,
        {
          method: "DELETE",
        }
      );
    } catch (error) {
      console.error(`Failed to delete ${model} chat history:`, error);
    }
  };

  const getResolvedSaveReason = () => {
    const reasons = selectedSaveReasons
      .filter((reason) => reason !== "Other")
      .map((reason) => reason.trim())
      .filter(Boolean);
    const customReason = customSaveReason.trim();

    if (selectedSaveReasons.includes("Other") && customReason) {
      reasons.push(customReason);
    }

    return reasons.join("; ");
  };

  const toggleSaveReason = (reason: string) => {
    setSelectedSaveReasons((current) => {
      if (current.includes(reason)) {
        return current.filter((item) => item !== reason);
      }
      return [...current, reason];
    });
  };

  const getStatusSuccessMessage = (nextStatus: string, savedReason?: string | null) => {
    const normalized = normalizeStatus(nextStatus);

    if (normalized === "rejected") {
      return "Rejected. Other actions are now locked until you enable editing.";
    }

    if (normalized === "analyzed") {
      return "Marked processed. Other actions are now locked until you enable editing.";
    }

    if (normalized === "saved") {
      return savedReason
        ? `Saved for later. Reason: ${savedReason}. Other actions are now locked until you enable editing.`
        : "Saved for later. Other actions are now locked until you enable editing.";
    }

    return `Status updated to ${getStatusLabel(nextStatus)}.`;
  };

  const persistStatus = async (newStatus: string, savedReason?: string | null) => {
    if (!insight || statusUpdating) return;
    if (isRejectedLocked) {
      setStatusError("Confirm Enable Editing before changing this signal.");
      return;
    }

    const previousStatus = localStatus;
    const previousSavedReason = insight.saved_reason || null;
    const normalizedNextStatus = normalizeStatus(newStatus);
    const finalSavedReason = normalizedNextStatus === "saved" ? savedReason || null : null;

    if (normalizeStatus(previousStatus) === normalizedNextStatus && !!decisionLockKind) {
      setDecisionEditingUnlocked(false);
      setDecisionLockActive(normalizedNextStatus === "analyzed");
      setStatusError("");
      setStatusMessage(getStatusSuccessMessage(newStatus, finalSavedReason));
      setInsight((prev) =>
        prev
          ? {
              ...prev,
              status: normalizedNextStatus,
              saved_reason: finalSavedReason,
            }
          : prev
      );
      return;
    }

    setStatusUpdating(true);
    setStatusMessage(`Updating status to ${getStatusLabel(newStatus)}...`);
    setStatusError("");
    setLocalStatus(normalizedNextStatus);
    setInsight((prev) =>
      prev
        ? {
            ...prev,
            status: normalizedNextStatus,
            saved_reason: finalSavedReason,
          }
        : prev
    );

    try {
      const res = await withTimeout(
        adminFetch(`${API_BASE}/signals/update-status`, {
          method: "POST",
          headers: buildJsonAdminHeaders(),
          body: JSON.stringify({
            signal_id: insight.signal_id || insight.id || String(id),
            title: displayTitle,
            source: insight.source || "",
            published_at: insight.published_at || "",
            collected_at: insight.collected_at || "",
            status: newStatus,
            saved_reason: finalSavedReason,
          }),
        }),
        STATUS_UPDATE_TIMEOUT_MS,
        "Status update timed out."
      );

      if (!res.ok) {
        const text = await res.text();
        console.error("Failed to persist status:", res.status, text);
        setLocalStatus(previousStatus);
        setInsight((prev) =>
          prev
            ? {
                ...prev,
                status: previousStatus,
                saved_reason: previousSavedReason,
              }
            : prev
        );
        setStatusError(`Failed to update status (${res.status}).`);
        return;
      }

      if (normalizedNextStatus === "rejected" || normalizedNextStatus === "saved" || normalizedNextStatus === "analyzed") {
        setDecisionEditingUnlocked(false);
        setDecisionLockActive(normalizedNextStatus === "analyzed");
      }
      syncSignalsListCacheStatus(insight.signal_id || insight.id || String(id), normalizedNextStatus);
      invalidateSignalsListCache();

      try {
        const refreshed = await refreshSignalStatus();
        setLocalStatus(normalizeStatus(refreshed?.status || normalizedNextStatus));
      } catch (refreshError) {
        console.warn("Status updated but detail refresh failed:", refreshError);
      }

      setStatusMessage(getStatusSuccessMessage(newStatus, finalSavedReason));
    } catch (err) {
      const isTimeoutError = err instanceof Error && err.message === "Status update timed out.";
      if (isTimeoutError) {
        if (normalizedNextStatus === "rejected" || normalizedNextStatus === "saved" || normalizedNextStatus === "analyzed") {
          setDecisionEditingUnlocked(false);
          setDecisionLockActive(normalizedNextStatus === "analyzed");
        }
        syncSignalsListCacheStatus(insight.signal_id || insight.id || String(id), normalizedNextStatus);
        invalidateSignalsListCache();
        setStatusMessage(
          normalizedNextStatus === "saved"
            ? `Saved locally${finalSavedReason ? `: ${finalSavedReason}` : ""}. Backend confirmation timed out; refresh this signal to confirm it persisted.`
            : `${getStatusLabel(newStatus)} locally. Backend confirmation timed out; refresh this signal to confirm it persisted.`
        );
        setStatusError("The status request timed out instead of completing cleanly.");
        return;
      }
      console.error("Failed to persist status:", err);
      setLocalStatus(previousStatus);
      setInsight((prev) =>
        prev
          ? {
              ...prev,
              status: previousStatus,
              saved_reason: previousSavedReason,
            }
          : prev
      );
      setStatusError("Failed to update status.");
    } finally {
      setStatusUpdating(false);
    }
  };

  const persistStar = async (nextStarred: boolean) => {
    if (!insight || starUpdating) return;

    const signalId = insight.signal_id || insight.id || String(id);
    const previousStarred = Boolean(insight.starred);
    const previousStarredAt = insight.starred_at || null;
    const optimisticStarredAt = nextStarred ? new Date().toISOString() : null;

    setStarUpdating(true);
    setStatusMessage(nextStarred ? "Starring signal..." : "Removing star...");
    setStatusError("");
    setInsight((prev) =>
      prev
        ? {
            ...prev,
            starred: nextStarred,
            starred_at: optimisticStarredAt,
          }
        : prev
    );
    syncSignalsListCacheStar(signalId, nextStarred, optimisticStarredAt);

    try {
      const res = await withTimeout(
        adminFetch(`${API_BASE}/signals/update-star`, {
          method: "POST",
          headers: buildJsonAdminHeaders(),
          body: JSON.stringify({
            signal_id: signalId,
            title: displayTitle,
            source: insight.source || "",
            published_at: insight.published_at || "",
            collected_at: insight.collected_at || "",
            starred: nextStarred,
          }),
        }),
        STATUS_UPDATE_TIMEOUT_MS,
        "Star update timed out."
      );

      if (!res.ok) {
        const text = await res.text();
        console.error("Failed to persist star:", res.status, text);
        setInsight((prev) =>
          prev
            ? {
                ...prev,
                starred: previousStarred,
                starred_at: previousStarredAt,
              }
            : prev
        );
        syncSignalsListCacheStar(signalId, previousStarred, previousStarredAt);
        setStatusError(`Failed to update star (${res.status}).`);
        return;
      }

      const data = (await res.json()) as { starred?: boolean; starred_at?: string | null };
      const persistedStarred = Boolean(data.starred);
      const persistedStarredAt = data.starred_at || null;
      setInsight((prev) =>
        prev
          ? {
              ...prev,
              starred: persistedStarred,
              starred_at: persistedStarredAt,
            }
          : prev
      );
      syncSignalsListCacheStar(signalId, persistedStarred, persistedStarredAt);
      setStatusMessage(persistedStarred ? "Starred for quick return." : "Star removed.");
    } catch (err) {
      const isTimeoutError = err instanceof Error && err.message === "Star update timed out.";
      if (isTimeoutError) {
        setStatusMessage(
          nextStarred
            ? "Starred locally. Backend confirmation timed out; refresh this signal to confirm it persisted."
            : "Star removed locally. Backend confirmation timed out; refresh this signal to confirm it persisted."
        );
        setStatusError("The star request timed out instead of completing cleanly.");
        return;
      }
      console.error("Failed to persist star:", err);
      setInsight((prev) =>
        prev
          ? {
              ...prev,
              starred: previousStarred,
              starred_at: previousStarredAt,
            }
          : prev
      );
      syncSignalsListCacheStar(signalId, previousStarred, previousStarredAt);
      setStatusError("Failed to update star.");
    } finally {
      setStarUpdating(false);
    }
  };

  const handleGenerateInsight = async (selectedModel: "chatgpt" | "claude" = "chatgpt") => {
    if (!insight || insightGenerating) return;
    if (isRejectedLocked) {
      setStatusError("Confirm Enable Editing before regenerating this signal.");
      return;
    }

    setInsightGenerating(true);
    setInsightGeneratingModel(selectedModel);
    setStatusMessage("");
    setStatusError("");

    try {
      const res = await adminFetch(`${API_BASE}/signals/generate-insight`, {
        method: "POST",
        headers: buildJsonAdminHeaders(),
        body: JSON.stringify({
          signal_id: insight.signal_id || insight.id || String(id),
          selected_model: selectedModel,
        }),
      });

      const data = (await readApiResponse(res)) as GenerateInsightResponse;

      if (!res.ok) {
        throw new Error(String(data.detail || data.message || "Failed to generate insight"));
      }

      setInsight((prev) =>
        prev
          ? {
              ...prev,
              signal_summary: data.summary || prev.signal_summary || prev.summary || "",
              summary: data.summary || prev.summary || prev.signal_summary || "",
              status: data.status || "analyzed",
              why_it_matters: data.why_it_matters || "",
              relevance_to_projects: data.relevance_to_projects || "",
              relevance_to_career: data.relevance_to_career || "",
              synthesized_insight: data.synthesized_insight || "",
              insight: data.why_it_matters || "",
              strategy: data.synthesized_insight || "",
              provider_used: data.provider_used || selectedModel,
              model_used: data.model_used || "",
              produced_by_model: data.produced_by_model || prev.produced_by_model,
              generation_mode: data.generation_mode || "llm",
              requested_provider: data.requested_provider || selectedModel,
              is_manual: typeof data.is_manual === "boolean" ? data.is_manual : prev.is_manual,
              manual_session_id: data.manual_session_id || prev.manual_session_id,
              upload_reason: data.upload_reason || prev.upload_reason || "",
              intended_use: data.intended_use || prev.intended_use || "",
              cognitive_layer: data.cognitive_layer || prev.cognitive_layer || "unclassified",
              analysis_status: data.analysis_status || prev.analysis_status,
              insight_status: data.insight_status || prev.insight_status,
              insight_status_label: data.insight_status_label || prev.insight_status_label,
              workspace_saved: typeof data.workspace_saved === "boolean" ? data.workspace_saved : prev.workspace_saved,
              workspace_file_name: data.workspace_file_name || prev.workspace_file_name,
              workspace_saved_at: data.workspace_saved_at || prev.workspace_saved_at,
              file_count: typeof data.file_count === "number" ? data.file_count : prev.file_count,
              file_types: Array.isArray(data.file_types) ? data.file_types : prev.file_types,
              files: Array.isArray(data.files) ? data.files : prev.files,
              verification: data.verification || prev.verification,
              policy_metadata: data.policy_metadata || prev.policy_metadata,
              evidence_pack: data.evidence_pack || prev.evidence_pack,
            }
          : prev
      );

      setLocalStatus(normalizeStatus(data.status || "analyzed"));
      setDecisionEditingUnlocked(false);
      setDecisionLockActive(false);
      invalidateSignalsListCache();
      setStatusMessage(
        data.generation_mode === "fallback"
          ? `Insight generation did not produce a strong enough model result, so a fallback template was saved instead. Requested: ${data.requested_provider || selectedModel}.${Array.isArray(data.policy_metadata?.notes) && data.policy_metadata.notes.length ? ` ${data.policy_metadata.notes[data.policy_metadata.notes.length - 1]}` : ""}`
          : `Insight generated successfully via ${data.provider_used || selectedModel}${data.model_used ? ` (${data.model_used})` : ""}.`
      );
    } catch (error: unknown) {
      console.error("Generate insight failed:", error);
      setStatusError(getErrorMessage(error, "Failed to generate insight"));
    } finally {
      setInsightGenerating(false);
      setInsightGeneratingModel(null);
    }
  };

  const handleGenerateDeepProjectMatchAnalysis = async () => {
    if (!insight || deepProjectMatchAnalysisLoading) return;

    setDeepProjectMatchAnalysisLoading(true);
    setDeepProjectMatchAnalysisError("");
    setStatusMessage("");

    try {
      const res = await adminFetch(`${API_BASE}/signals/actions/deep-match-analysis`, {
        method: "POST",
        headers: buildJsonAdminHeaders(),
        body: JSON.stringify({
          signal_id: insight.signal_id || insight.id || String(id),
          selected_model: "chatgpt",
          signal_snapshot: insight,
          source_depth_tier: "metadata",
          deep_match_review: {
            required: deepProjectMatchReview.required,
            status: deepProjectMatchReview.status,
            posture: deepProjectMatchReview.posture,
            reason: deepProjectMatchReview.reason,
            matched_projects: deepProjectMatchReview.matchedProjects,
            relevant_modules: deepProjectMatchReview.relevantModules,
            match_type: deepProjectMatchReview.matchType,
            evidence_boundary: deepProjectMatchReview.evidenceBoundary,
            downstream_posture: deepProjectMatchReview.downstreamPosture,
            checklist: deepProjectMatchReview.checklist,
            review_note: deepProjectMatchReviewNoteValue,
          },
        }),
      });
      const data = (await readApiResponse(res)) as DeepMatchAnalysisResponse;
      if (!res.ok) {
        throw new Error(String(data.detail || data.message || "Failed to generate Deep Match Analysis"));
      }

      const generated = data.analysis || null;
      setDeepProjectMatchAnalysis(generated);
      if (generated) {
        setDeepProjectMatchAnalysisLayers((current) => [...current, generated]);
      }
      if (generated?.review_note) {
        setDeepProjectMatchReviewNote(generated.review_note);
      }
      setStatusMessage("Deep Match Analysis generated as review context. Verification status and Action gates are unchanged.");
    } catch (error: unknown) {
      console.error("Generate Deep Match Analysis failed:", error);
      setDeepProjectMatchAnalysisError(getErrorMessage(error, "Failed to generate Deep Match Analysis"));
    } finally {
      setDeepProjectMatchAnalysisLoading(false);
    }
  };

  const generateReflectionDraft = async (force = false) => {
    if (!insight) return;
    if (isRejectedLocked) {
      setSaveMessage("Confirm Enable Editing before generating a completion note for this signal.");
      return;
    }
    if (!force && reflection.trim()) return;

    setIsGeneratingDraft(true);
    setDraftError("");
    setSaveMessage("");

    const prompt = `
Write a first-person reflection draft for me.

Requirements:
- 140 to 220 words
- first-person voice
- practical and thoughtful
- connect this signal to my work, projects, career direction, and skills
- do not use bullet points
- plain text only

Signal title:
${displayTitle}

Signal summary:
${cleanedDisplaySummary}

Why it matters:
${cleanedWhyItMatters}

Relevance to projects:
${cleanedProjectRelevance}

Relevance to career:
${cleanedCareerRelevance}

Strategic takeaway:
${cleanedStrategicTakeaway}

Please generate a reflection draft that feels personal and specific, not generic.
`.trim();

    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), 30000);

    try {
      const res = await adminFetch(`${API_BASE}/workspace_chat`, {
        method: "POST",
        headers: buildJsonAdminHeaders(),
        signal: controller.signal,
        body: JSON.stringify(buildWorkspacePayload("chatgpt", prompt, "", "artifact")),
      });

      const data = await readApiResponse(res);
      if (!res.ok) {
        throw new Error(String(data.detail || data.message || `Draft generation failed. HTTP ${res.status}`));
      }

      const reply = String(data.reply || data.error || "").trim();

      if (!reply) {
        setDraftError("Draft generation returned no content.");
        return;
      }

      setReflection(normalizedDisplayText(reply));
      setReflectionPolishPairId("");
      setSaveMessage("Draft generated. Review it, then complete the signal.");
    } catch (error: unknown) {
      const message =
        error instanceof DOMException && error.name === "AbortError"
          ? "Draft generation timed out. Type a completion note manually or try Generate Draft again."
          : getErrorMessage(error, "Failed to generate reflection draft.");
      setDraftError(message);
    } finally {
      window.clearTimeout(timeoutId);
      setIsGeneratingDraft(false);
    }
  };

  const handleSaveReflection = async () => {
    if (isRejectedLocked) {
      setSaveMessage("Confirm Enable Editing before saving a completion note for this signal.");
      return;
    }
    if (!reflection.trim()) {
      setSaveMessage("Completion note is empty.");
      return;
    }

    setIsSaving(true);
    setSaveMessage("");

    try {
      localStorage.setItem(`reflection-${id}`, reflection);
      setSaveMessage("Completion note draft saved. Complete Signal when you're ready to send it to Workspace.");
    } catch (error) {
      console.error("Save completion note draft failed:", error);
      setSaveMessage("Failed to save completion note draft.");
    } finally {
      setIsSaving(false);
    }
  };

  const handleCompleteSignal = async () => {
    if (!insight) return;
    if (isRejectedLocked) {
      setSaveMessage("Confirm Enable Editing before completing this signal.");
      return;
    }
    if (confirmedFinalTakeaway?.final_takeaway_id) {
      setSaveMessage("Final Takeaway is already confirmed. Use Send Final Takeaway to Review instead of Complete Signal.");
      return;
    }
    if (isGeneratingDraft) {
      setSaveMessage("Draft generation is still running. Wait for it to finish, or type a completion note manually.");
      return;
    }
    if (!hasCompletionNote) {
      setSaveMessage("Please write or generate a completion note first.");
      return;
    }
    if (completionRequiresVerificationReview && !completionReviewConfirmed) {
      setSaveMessage("Confirm the verification review checkbox before completing this signal into Workspace.");
      return;
    }

    setIsCompleting(true);
    setSaveMessage("");

    try {
      let selectedModel = "";
      let userInput = "";
      let aiResponse = "";

      if (activeTab === "Claude") {
        selectedModel = "claude";
        const lastUser = [...claudeMessages].reverse().find((m) => m.role === "user");
        const lastAssistant = [...claudeMessages].reverse().find((m) => m.role === "assistant");
        userInput = lastUser?.content || claudeInput || "";
        aiResponse = lastAssistant?.content || "";
      } else if (activeTab === "ChatGPT") {
        selectedModel = "chatgpt";
        const lastUser = [...chatgptMessages].reverse().find((m) => m.role === "user");
        const lastAssistant = [...chatgptMessages].reverse().find((m) => m.role === "assistant");
        userInput = lastUser?.content || chatgptInput || "";
        aiResponse = lastAssistant?.content || "";
      } else if (activeTab === "Perplexity") {
        selectedModel = "perplexity";
        const lastUser = [...perplexityMessages].reverse().find((m) => m.role === "user");
        const lastAssistant = [...perplexityMessages].reverse().find((m) => m.role === "assistant");
        userInput = lastUser?.content || perplexityInput || "";
        aiResponse = lastAssistant?.content || "";
      }

      const res = await adminFetch(`${API_BASE}/signals/complete`, {
        method: "POST",
        headers: buildJsonAdminHeaders(),
          body: JSON.stringify({
            signal_id: insight?.signal_id || insight?.id || String(id),
            signal_title: displayTitle,
            topic: insight?.topic || "",
            selected_model: selectedModel,
          user_input: userInput,
          ai_response: aiResponse,
          final_reflection: reflection,
          signal_summary: cleanedDisplaySummary,
            why_it_matters: cleanedWhyItMatters,
            relevance_to_projects: cleanedProjectRelevance,
            relevance_to_career: cleanedCareerRelevance,
            synthesized_insight: cleanedStrategicTakeaway,
            verification_metadata: buildVerificationMetadata({
              completed_with_blocked_actions: completionRequiresVerificationReview,
            }),
            subscription_project_links: insight?.subscription_project_links || [],
          }),
        });

      const data = await readApiResponse(res);
      if (!res.ok) {
        throw new Error(String(data.detail || data.message || `Failed to complete signal. HTTP ${res.status}`));
      }

      const completedWorkspaceFileName =
        typeof data?.workspace_file_name === "string" ? data.workspace_file_name : "";
      const completedWorkspaceSavedAt =
        typeof data?.workspace_saved_at === "string" ? data.workspace_saved_at : "";

      setLocalStatus("completed");
      setInsight((prev) =>
        prev
          ? {
              ...prev,
              status: "completed",
              workspace_saved: true,
              workspace_file_name: completedWorkspaceFileName || prev.workspace_file_name,
              workspace_saved_at: completedWorkspaceSavedAt || prev.workspace_saved_at,
            }
          : prev
      );
      syncSignalsListCacheStatus(insight?.signal_id || insight?.id || String(id), "completed");
      try {
        await refreshSignalStatus();
      } catch {
        // Keep optimistic completed state if the follow-up refresh is temporarily unavailable.
      }
      setSaveMessage(
        completedWorkspaceFileName
          ? "Signal completed and sent to Workspace. The workspace record is now available from this page."
          : "Signal completed and sent to Workspace."
      );
    } catch (error: unknown) {
      const message =
        error instanceof TypeError
          ? `Cannot reach AI Radar API at ${API_BASE || "the configured API URL"}. Check that the local backend is running and refresh this page.`
          : getErrorMessage(error, "Failed to complete signal.");
      setSaveMessage(message);
    } finally {
      setIsCompleting(false);
    }
  };

  const handleSendFinalTakeawayToReview = async () => {
    if (!insight || projectCandidateCreating) return;

    setProjectCandidateMessage("");
    setProjectCandidateError("");

    const finalTakeawayId = confirmedFinalTakeaway?.final_takeaway_id || "";
    if (!finalTakeawayId) {
      setProjectCandidateError("Confirm the Final Takeaway before sending it to Project Review.");
      return;
    }
    if (isRejectedLocked) {
      setProjectCandidateError("Confirm Enable Editing before sending this Final Takeaway to Project Review.");
      return;
    }
    if (!hasProjectTakeawayText) {
      setProjectCandidateError("Add or generate project relevance before sending this Final Takeaway to Project Review.");
      return;
    }
    if (!signalCompleted) {
      setProjectCandidateError("Complete Signal before sending this Final Takeaway to Project Review.");
      return;
    }

    const manualOverride = !canCreateProjectTakeawayCandidate;
    if (manualOverride && !projectTakeawayOverrideConfirmed) {
      setProjectCandidateError("Confirm the Final Takeaway override checkbox before sending this Final Takeaway to Project Review.");
      return;
    }

    setProjectCandidateCreating(true);

    try {
      const confirmedText = confirmedFinalTakeaway?.confirmed_text || finalTakeawayText || reflection;
      const res = await adminFetch(`${API_BASE}/projects/takeaway-candidates/from-final-takeaway`, {
        method: "POST",
        headers: buildJsonAdminHeaders(),
        body: JSON.stringify({
          final_takeaway_id: finalTakeawayId,
          signal_id: finalTakeawaySignalId,
          signal_title: displayTitle,
          signal_summary: cleanedDisplaySummary,
          why_it_matters: cleanedWhyItMatters,
          relevance_to_projects: cleanedProjectRelevance,
          synthesized_insight: confirmedText || cleanedStrategicTakeaway,
          final_reflection: confirmedText || reflection,
          subscription_project_links: insight.subscription_project_links || [],
          verification_metadata: buildVerificationMetadata({
            candidate_requested_from: "confirmed_final_takeaway",
            confirmed_final_takeaway: true,
            final_takeaway_id: finalTakeawayId,
            review_bundle_snapshot_id:
              confirmedFinalTakeaway?.review_bundle_snapshot_id || reviewBundleSnapshot?.snapshot_id || "",
            review_bundle_content_hash:
              confirmedFinalTakeaway?.review_bundle_content_hash || reviewBundleSnapshot?.content_hash || "",
            final_takeaway_confirmed_at: confirmedFinalTakeaway?.confirmed_at || "",
            upload_reason: insight.upload_reason || "",
            intended_use: insight.intended_use || "",
            cognitive_layer: insight.cognitive_layer || "unclassified",
            manual_project_takeaway_override: manualOverride,
            manual_override_note: manualOverride ? projectTakeawayManualOverrideReason : "",
          }),
        }),
      });

      const data = await res.json().catch(() => null);
      if (!res.ok) {
        throw new Error(data?.detail || data?.message || "Failed to send Final Takeaway to Project Review.");
      }

      const createdCount = typeof data?.created_count === "number" ? data.created_count : 0;
      if (createdCount > 0) {
        setProjectCandidateCreated(true);
      }
      setProjectCandidateMessage(
        createdCount > 0
          ? manualOverride
            ? `Confirmed Final Takeaway sent to Project Review with explicit override for ${createdCount} project(s). Open the Review Inbox and review it before acting.`
            : `Confirmed Final Takeaway sent to Project Review for ${createdCount} project(s).`
          : "No linked project matched this Final Takeaway, so no candidate was created."
      );
    } catch (error: unknown) {
      console.error("Send Final Takeaway to Project Review failed:", error);
      setProjectCandidateError(getErrorMessage(error, "Failed to send Final Takeaway to Project Review."));
    } finally {
      setProjectCandidateCreating(false);
    }
  };

  const polishReflection = async () => {
    if (isRejectedLocked) {
      setSaveMessage("Confirm Enable Editing before polishing a completion note for this signal.");
      return;
    }
    if (!reflection.trim()) {
      setSaveMessage("Please write or generate a completion note first.");
      return;
    }

    setIsPolishing(true);
    setSaveMessage("");
    setReflectionPolishPairId("");

    try {
      const res = await adminFetch(`${API_BASE}/polish_reflection`, {
        method: "POST",
        headers: buildJsonAdminHeaders(),
        body: JSON.stringify({
          text: reflection,
          persist_pair: true,
          signal_id: insight?.signal_id || insight?.id || String(id),
          signal_title: displayTitle,
          signal_summary: cleanedDisplaySummary,
          why_it_matters: cleanedWhyItMatters,
          relevance_to_projects: cleanedProjectRelevance,
          relevance_to_career: cleanedCareerRelevance,
          synthesized_insight: cleanedStrategicTakeaway,
        }),
      });

      const data = await readApiResponse(res);
      if (!res.ok) {
        throw new Error(String(data.detail || data.message || `AI Polish failed. HTTP ${res.status}`));
      }
      const reply = String(data.polished_text || data.error || "").trim();
      const pairId = String(data.reflection_polish_pair_id || "").trim();

      if (!reply) {
        setSaveMessage("AI Polish returned no content.");
        return;
      }

      setReflection(normalizedDisplayText(reply));
      if (pairId) {
        setReflectionPolishPairId(pairId);
        setSaveMessage(`Completion note polished. Review pair recorded: ${pairId}.`);
      } else {
        setSaveMessage("Completion note polished. Review pair was not recorded.");
      }
    } catch (error) {
      console.error("AI polish failed:", error);
      setSaveMessage(getErrorMessage(error, "AI Polish failed."));
    } finally {
      setIsPolishing(false);
    }
  };

  const handleGenerateVisual = async () => {
    if (!insight || visualGenerating) return;
    if (isRejectedLocked) {
      setVisualError("Confirm Enable Editing before generating visuals for this signal.");
      return;
    }

    setVisualGenerating(true);
    setVisualError("");

    try {
      const res = await adminFetch(`${API_BASE}/workspace_generate_visual`, {
        method: "POST",
        headers: buildJsonAdminHeaders(),
        body: JSON.stringify(buildVisualPayload()),
      });

      const data = await res.json();

      if (!res.ok || !data?.image_url) {
        throw new Error(data?.message || "Failed to generate GPT-5.5 visual.");
      }

      setGeneratedVisualUrl(`${API_BASE}${data.image_url}`);
      setGeneratedVisualFileName(data.image_file_name || "");
    } catch (err) {
      console.error("GPT-5.5 visual generation failed:", err);
      setVisualError(err instanceof Error ? err.message : "Failed to generate GPT-5.5 visual.");
    } finally {
      setVisualGenerating(false);
    }
  };

  const sendToModel = async (model: ModelKey) => {
    const isClaude = model === "claude";
    const isChatGPT = model === "chatgpt";
    const isPerplexity = model === "perplexity";

    const input = isClaude ? claudeInput : isChatGPT ? chatgptInput : perplexityInput;
    if (!input.trim()) return;

    const userMessage = input.trim();
    const existingMessages = isClaude
      ? claudeMessages
      : isChatGPT
        ? chatgptMessages
        : perplexityMessages;
    const optimisticMessages: ChatMessage[] = [
      ...existingMessages,
      { role: "user", content: userMessage },
    ];

    if (isClaude) {
      setClaudeMessages(optimisticMessages);
      setClaudeInput("");
      setClaudeLoading(true);
    } else if (isChatGPT) {
      setChatgptMessages(optimisticMessages);
      setChatgptInput("");
      setChatgptLoading(true);
    } else {
      setPerplexityMessages(optimisticMessages);
      setPerplexityInput("");
      setPerplexityLoading(true);
    }

    try {
      const recentDiscussionContext =
        isClaude ? existingMessages.slice(-RECENT_DISCUSSION_CONTEXT_LIMIT) : [];
      const res = await adminFetch(`${API_BASE}/workspace_chat`, {
        method: "POST",
        headers: buildJsonAdminHeaders(),
        body: JSON.stringify(buildWorkspacePayload(model, userMessage, undefined, "discussion", recentDiscussionContext)),
      });

      const data = await res.json();
      const assistantReply = data.reply || data.error || "No response returned.";
      const nextMessages: ChatMessage[] = [
        ...optimisticMessages,
        {
          role: "assistant",
          content: assistantReply,
          provider_used: data.provider_used,
          model_used: data.model_used,
          fallback_used: typeof data.fallback_used === "boolean" ? data.fallback_used : undefined,
        },
      ];

      if (isClaude) {
        setClaudeMessages(nextMessages);
      } else if (isChatGPT) {
        setChatgptMessages(nextMessages);
      } else {
        setPerplexityMessages(nextMessages);
      }
      await persistChatHistory(model, nextMessages);
    } catch (error) {
      console.error(`${model} workspace chat failed:`, error);

      const fallback = `${model} workspace chat failed.`;
      const nextMessages: ChatMessage[] = [
        ...optimisticMessages,
        { role: "assistant", content: fallback },
      ];
      if (isClaude) {
        setClaudeMessages(nextMessages);
      } else if (isChatGPT) {
        setChatgptMessages(nextMessages);
      } else {
        setPerplexityMessages(nextMessages);
      }
      await persistChatHistory(model, nextMessages);
    } finally {
      if (isClaude) setClaudeLoading(false);
      if (isChatGPT) setChatgptLoading(false);
      if (isPerplexity) setPerplexityLoading(false);
    }
  };

  const clearChat = (tab: UiTab) => {
    if (tab === "Claude") {
      setClaudeMessages([]);
      localStorage.removeItem(`claudeMessages-${id}`);
      void deletePersistedChatHistory("claude");
    } else if (tab === "ChatGPT") {
      setChatgptMessages([]);
      localStorage.removeItem(`chatgptMessages-${id}`);
      void deletePersistedChatHistory("chatgpt");
    } else {
      setPerplexityMessages([]);
      localStorage.removeItem(`perplexityMessages-${id}`);
      void deletePersistedChatHistory("perplexity");
    }
  };

  if (loading) {
    return (
      <main style={detailPageShellStyle}>
        <div style={detailToolbarStyle}>
          <Link href="/signals" style={primaryNavLinkStyle}>
            <span style={{ fontSize: "14px" }}>Back to Signal Records</span>
          </Link>
          {reviewFocusId ? (
            <Link href={`/workspace/projects/review?signal_id=${encodeURIComponent(reviewFocusId)}`} style={secondaryNavLinkStyle}>
              Back to Focused Review
            </Link>
          ) : null}
        </div>
        <div style={{ ...detailPanelStyle, color: "#6b7280" }}>
          Loading signal detail and review context...
        </div>
      </main>
    );
  }

  if (!insight) {
    return (
      <main style={detailPageShellStyle}>
        <Link href="/signals">← Back to Signals</Link>
        <div style={{ ...detailPanelStyle, marginTop: "20px" }}>Signal detail not found.</div>
      </main>
    );
  }

  const currentMessages =
    activeTab === "Claude"
      ? claudeMessages
      : activeTab === "ChatGPT"
        ? chatgptMessages
        : perplexityMessages;

  const currentLoading =
    activeTab === "Claude"
      ? claudeLoading
      : activeTab === "ChatGPT"
        ? chatgptLoading
        : perplexityLoading;

  const currentInput =
    activeTab === "Claude"
      ? claudeInput
      : activeTab === "ChatGPT"
        ? chatgptInput
        : perplexityInput;
  const currentExpectedProvider =
    activeTab === "Claude"
      ? "anthropic"
      : activeTab === "ChatGPT"
        ? "openai"
        : "perplexity";
  const signalActionDisabled = statusUpdating || insightGenerating || isRejectedLocked;

  return (
    <>
    <main style={detailPageShellStyle}>
      <div style={detailToolbarStyle}>
        <div style={detailToolbarLeftStyle}>
          <Link
            href="/signals"
            style={primaryNavLinkStyle}
          >
            <span style={{ fontSize: "14px" }}>Back to Signal Records</span>
          </Link>
          {isManualInsight && insight.manual_session_id ? (
            <Link
              href={`/manual/detail?id=${encodeURIComponent(insight.manual_session_id)}`}
              style={secondaryNavLinkStyle}
            >
              Open Manual Session
            </Link>
          ) : null}
          <Link href={reviewInboxHref} style={secondaryNavLinkStyle}>
            Project Review Inbox
          </Link>
        </div>
      </div>
      {detailRefreshing ? (
        <div style={detailRefreshingNoticeStyle}>
          Showing cached signal context while refreshing the latest detail.
        </div>
      ) : null}

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "minmax(0, 1.2fr) minmax(360px, 0.8fr)",
          gap: "24px",
          alignItems: "start",
        }}
      >
        <div>
          <div
            style={{
              ...detailPanelStyle,
              padding: "20px",
              marginBottom: "20px",
            }}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "flex-start",
                gap: "12px",
                marginBottom: "8px",
                flexWrap: "wrap",
              }}
            >
              <div
                style={{
                  fontSize: "12px",
                  color: "var(--app-text-subtle)",
                  textTransform: "uppercase",
                  letterSpacing: 0,
                  fontWeight: 700,
                }}
              >
                Signal
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <div
                  style={{
                    ...getStatusStyle(localStatus),
                    borderRadius: "999px",
                    padding: "6px 10px",
                    fontSize: "12px",
                    whiteSpace: "nowrap",
                  }}
                >
                  {statusLabel}
                </div>
                <button
                  type="button"
                  onClick={() => void persistStar(!isStarred)}
                  disabled={starUpdating}
                  title={isStarred ? "Remove star" : "Star signal"}
                  aria-label={isStarred ? "Remove star from signal" : "Star signal"}
                  aria-pressed={isStarred}
                  style={{
                    width: "34px",
                    height: "34px",
                    borderRadius: "8px",
                    border: isStarred ? "1px solid var(--app-warning-border)" : "1px solid var(--app-secondary-action-border)",
                    background: isStarred ? "var(--app-warning-bg)" : "var(--app-secondary-action-bg)",
                    color: isStarred ? "var(--app-warning-fg)" : "var(--app-secondary-action-fg)",
                    cursor: starUpdating ? "not-allowed" : "pointer",
                    opacity: starUpdating ? 0.7 : 1,
                    display: "inline-flex",
                    alignItems: "center",
                    justifyContent: "center",
                  }}
                >
                  <Star size={17} fill={isStarred ? "currentColor" : "none"} aria-hidden="true" />
                </button>
              </div>
            </div>

            <h1
              style={{
                fontSize: "28px",
                fontWeight: 700,
                marginBottom: "10px",
                lineHeight: 1.35,
              }}
            >
              {displayTitle}
            </h1>

            <div
              style={{
                display: "flex",
                gap: "8px",
                flexWrap: "wrap",
                marginTop: "10px",
                marginBottom: "6px",
              }}
            >
              <span
                style={{
                  padding: "4px 10px",
                  borderRadius: "999px",
                  background: "var(--app-tag-bg)",
                  color: "var(--app-tag-fg)",
                  border: "1px solid var(--app-chip-border)",
                  fontSize: "12px",
                  fontWeight: 600,
                }}
              >
                Topic: {displayTopic}
              </span>

              <span
                style={{
                  padding: "4px 10px",
                  borderRadius: "999px",
                  fontSize: "12px",
                  fontWeight: 600,
                  ...getProcessingBadgeStyle(displayInsightStatus),
                }}
              >
                {displayInsightStatusLabel}
              </span>
            </div>

            <div
              style={{
                marginTop: "12px",
                fontSize: "13px",
                color: "var(--app-text-muted)",
                display: "flex",
                flexWrap: "wrap",
                gap: "14px",
              }}
            >
              <span>Source: {insight.source || "Unknown"}</span>
              <span>Published: {formatDateTime(insight.published_at)}</span>
              <span>Collected: {formatDateTime(insight.collected_at)}</span>
            </div>

            {isManualInsight ? (
              <div
                style={{
                  marginTop: "12px",
                  border: "1px solid var(--app-info-border)",
                  background: "var(--app-info-bg)",
                  borderRadius: "8px",
                  padding: "12px 14px",
                }}
              >
                <div
                  style={{
                    fontSize: "12px",
                    fontWeight: 800,
                    color: "var(--app-info-fg)",
                    textTransform: "uppercase",
                    letterSpacing: 0,
                    marginBottom: "8px",
                  }}
                >
                  Manual Intent
                </div>
                {manualIntentItems.length > 0 ? (
                  <div style={{ display: "grid", gap: "6px" }}>
                    {manualIntentItems.map((item) => (
                      <div key={item.label} style={{ color: "var(--app-text-muted)", fontSize: "13px", lineHeight: 1.5 }}>
                        <strong>{item.label}:</strong> {item.value}
                      </div>
                    ))}
                  </div>
                ) : (
                  <div style={{ color: "var(--app-text-muted)", fontSize: "13px", lineHeight: 1.5 }}>
                    No upload intent metadata is attached to this manual signal.
                  </div>
                )}
              </div>
            ) : null}

            <div
              style={{
                marginTop: "14px",
                fontSize: "14px",
                color: "var(--app-text-muted)",
                lineHeight: "1.7",
              }}
            >
              {normalizeStatus(localStatus) === "pending" &&
                "Pending = waiting to be processed."}
              {normalizeStatus(localStatus) === "saved" &&
                "Saved = valuable, partially reviewed, and should be revisited later."}
              {normalizeStatus(localStatus) === "analyzed" &&
                "Analyzed = insight is ready, but it has not been finalized into Workspace yet."}
              {normalizeStatus(localStatus) === "completed" &&
                "Completed = reflection is finalized and this signal has been submitted to Workspace."}
              {normalizeStatus(localStatus) === "rejected" &&
                "Rejected = reviewed, but not valuable enough to continue."}
            </div>

            {decisionLockKind ? (
              <div
                style={{
                  marginTop: "12px",
                  border: decisionEditingUnlocked
                    ? "1px solid var(--app-warning-border)"
                    : "1px solid var(--app-danger-border)",
                  background: decisionEditingUnlocked ? "var(--app-warning-bg)" : "var(--app-danger-bg)",
                  color: decisionEditingUnlocked ? "var(--app-warning-fg)" : "var(--app-danger-fg)",
                  borderRadius: "8px",
                  padding: "12px 14px",
                  fontSize: "13px",
                  lineHeight: 1.6,
                }}
              >
                <strong>
                  {decisionEditingUnlocked ? "Editing is temporarily enabled." : `${getStatusLabel(localStatus)} signal is locked.`}
                </strong>{" "}
                {decisionEditingUnlocked
                  ? "You can modify this signal in this session. Change status if it should re-enter the workflow."
                  : "Generate, status, completion, and workspace actions stay disabled until you confirm editing."}
                {!decisionEditingUnlocked ? (
                  <div style={{ marginTop: "10px" }}>
                    <button
                      onClick={() => {
                        const confirmed = window.confirm(
                          "Enable editing for this signal? This does not change status by itself."
                        );
                        if (confirmed) {
                          setDecisionEditingUnlocked(true);
                          setStatusMessage("Editing enabled. Change status if this signal should re-enter the workflow.");
                          setStatusError("");
                        }
                      }}
                      style={{
                        ...detailActionDangerStyle,
                        padding: "8px 12px",
                        fontWeight: 800,
                        cursor: "pointer",
                      }}
                    >
                      Enable Editing
                    </button>
                  </div>
                ) : null}
              </div>
            ) : null}

            {normalizeStatus(localStatus) === "saved" && insight?.saved_reason && (
              <div
                style={{
                  marginTop: "10px",
                  fontSize: "13px",
                  color: "var(--app-tag-fg)",
                }}
              >
                <strong>Saved reason:</strong> {insight.saved_reason}
              </div>
            )}

            <SignalDecisionFlow
              status={localStatus}
              source={insight.source}
              publishedAt={insight.published_at}
              savedReason={insight.saved_reason}
              hasInsight={hasGeneratedInsightContent}
              workspaceSaved={insight.workspace_saved}
              modelUsed={insight.model_used}
              generationMode={insight.generation_mode}
              verification={insight.verification || insight.policy_metadata?.verification}
              decisionTrace={insight.decision_trace || []}
              projectCandidates={projectCandidateItems.map((item) => ({
                projectId: item.project_id,
                projectName: item.project_name,
                status: item.status,
                reviewOutcome: item.review_outcome,
                watchStatus: item.watch_status,
                actionCompletedAt: item.action_completed_at,
              }))}
              lifecycleProbe={lifecycleProbe}
              lifecycleProbeLoading={lifecycleProbeLoading}
              lifecycleProbeError={lifecycleProbeError}
            />

            {statusMessage && (
              <div
                style={{
                  marginTop: "12px",
                  border: statusMessage.startsWith("Updating")
                    ? "1px solid var(--app-info-border)"
                    : "1px solid var(--app-success-border)",
                  background: statusMessage.startsWith("Updating")
                    ? "var(--app-info-bg)"
                    : "var(--app-success-bg)",
                  borderRadius: "8px",
                  padding: "10px 12px",
                  fontSize: "14px",
                  color: statusMessage.startsWith("Updating")
                    ? "var(--app-info-fg)"
                    : "var(--app-success-fg)",
                  fontWeight: 600,
                }}
              >
                {statusMessage}
              </div>
            )}

            {statusError && (
              <div
                style={{
                  marginTop: "12px",
                  fontSize: "14px",
                  color: "var(--app-danger-fg)",
                }}
              >
                {statusError}
              </div>
            )}

            {insight?.generation_mode === "fallback" && !statusError ? (
              <div
                style={{
                  marginTop: "12px",
                  fontSize: "13px",
                  color: "var(--app-warning-fg)",
                  background: "var(--app-warning-bg)",
                  border: "1px solid var(--app-warning-border)",
                  borderRadius: "8px",
                  padding: "10px 12px",
                  lineHeight: 1.6,
                }}
              >
                This insight is currently fallback output, not a strong model-generated pass. Try regenerating with Claude after backend update/restart if you want a deeper result.
              </div>
            ) : null}

            <div
              style={{
                marginTop: "12px",
                fontSize: "13px",
                color:
                  displayInsightStatus === "manual_candidate" || displayInsightStatus === "manual_pending"
                    ? "var(--app-warning-fg)"
                    : displayInsightStatus === "manual_completed"
                      ? "var(--app-success-fg)"
                      : "var(--app-text-muted)",
                background:
                  displayInsightStatus === "manual_candidate" || displayInsightStatus === "manual_pending"
                    ? "var(--app-warning-bg)"
                    : displayInsightStatus === "manual_completed"
                      ? "var(--app-success-bg)"
                      : "var(--app-surface-muted-bg)",
                border:
                  displayInsightStatus === "manual_candidate" || displayInsightStatus === "manual_pending"
                    ? "1px solid var(--app-warning-border)"
                    : displayInsightStatus === "manual_completed"
                      ? "1px solid var(--app-success-border)"
                      : "1px solid var(--app-surface-border)",
                borderRadius: "8px",
                padding: "10px 12px",
                lineHeight: 1.6,
              }}
            >
              <strong>Insight processing:</strong> {displayInsightProcessingExplanation}
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
                disabled={signalActionDisabled}
                title={
                  actionDisabledReason ||
                  (isManualInsight
                    ? manualInsightMissing
                      ? "This manual session is missing insight content, so you can generate it here with ChatGPT by default."
                      : "Regenerate this manual session insight with ChatGPT."
                    : undefined)
                }
                style={{
                  ...detailActionPrimaryStyle,
                  ...(signalActionDisabled ? detailActionDisabledStyle : {}),
                  cursor: signalActionDisabled ? "not-allowed" : "pointer",
                }}
              >
                {insightGenerating && insightGeneratingModel === "chatgpt"
                  ? "Generating..."
                  : "Generate Insight"}
              </button>

              <button
                onClick={() => void handleGenerateInsight("claude")}
                disabled={signalActionDisabled}
                title={
                  actionDisabledReason ||
                  (isManualInsight
                    ? manualInsightMissing
                      ? "Use Claude for a higher-cost deeper pass on this manual session."
                      : "Regenerate this manual session insight with Claude."
                    : "Use Claude for a higher-cost deeper pass.")
                }
                style={{
                  ...detailActionSecondaryStyle,
                  ...(signalActionDisabled ? detailActionDisabledStyle : {}),
                  cursor: signalActionDisabled ? "not-allowed" : "pointer",
                }}
              >
                {insightGenerating && insightGeneratingModel === "claude"
                  ? "Generating..."
                  : "Generate with Claude"}
              </button>

              <button
                onClick={() => persistStatus("analyzed")}
                disabled={signalActionDisabled}
                style={{
                  ...detailActionSecondaryStyle,
                  ...(signalActionDisabled ? detailActionDisabledStyle : {}),
                  cursor: signalActionDisabled ? "not-allowed" : "pointer",
                }}
              >
                Mark Processed
              </button>

              <button
                onClick={() => setShowSaveReason((prev) => !prev)}
                disabled={signalActionDisabled}
                style={{
                  ...detailActionSecondaryStyle,
                  ...(signalActionDisabled ? detailActionDisabledStyle : {}),
                  cursor: signalActionDisabled ? "not-allowed" : "pointer",
                }}
              >
                Save for Later
              </button>

              <button
                onClick={() => persistStatus("rejected")}
                disabled={signalActionDisabled}
                style={{
                  ...detailActionDangerStyle,
                  ...(signalActionDisabled ? detailActionDisabledStyle : {}),
                  cursor: signalActionDisabled ? "not-allowed" : "pointer",
                }}
              >
                Reject
              </button>

              {displayUrl ? (
                <a
                  href={displayUrl}
                  target="_blank"
                  rel="noreferrer"
                  style={{
                    ...detailActionLinkStyle,
                  }}
                >
                  Open Source
                </a>
              ) : null}
            </div>

            {isManualInsight ? (
              <div
                style={{
                  ...manualSignalHandoffPanelStyle,
                  ...(manualSignalHandoffStage?.tone === "done"
                    ? manualSignalHandoffDoneStyle
                    : manualSignalHandoffStage?.tone === "ready"
                      ? manualSignalHandoffReadyStyle
                      : manualSignalHandoffStage?.tone === "warning"
                        ? manualSignalHandoffWarningStyle
                        : {}),
                }}
              >
                <div style={manualSignalHandoffHeaderStyle}>
                  <div>
                    <span style={manualSourceContextLabelStyle}>Manual Signal Handoff</span>
                    <strong>{manualSignalHandoffStage?.label || "Signal Review"}</strong>
                  </div>
                  <span style={manualSignalHandoffChipStyle}>
                    {displayInsightStatusLabel}
                  </span>
                </div>
                <div>{manualSignalHandoffStage?.body}</div>

                <div style={manualSignalHandoffGridStyle}>
                  <div style={manualSignalHandoffItemStyle}>
                    <span style={manualSourceContextLabelStyle}>Manual Session</span>
                    <strong>{insight.manual_session_id ? "Linked" : "Missing link"}</strong>
                  </div>
                  <div style={manualSignalHandoffItemStyle}>
                    <span style={manualSourceContextLabelStyle}>Signal Review</span>
                    <strong>{manualInsightMissing ? "Needs insight" : "Insight ready"}</strong>
                  </div>
                  <div style={manualSignalHandoffItemStyle}>
                    <span style={manualSourceContextLabelStyle}>Workspace</span>
                    <strong>{hasWorkspaceRecord ? "Saved" : "Not saved"}</strong>
                  </div>
                  <div style={manualSignalHandoffItemStyle}>
                    <span style={manualSourceContextLabelStyle}>Project Gate</span>
                    <strong>
                      {projectCandidateCreated
                        ? "Candidate created"
                        : canCreateProjectTakeawayCandidate
                          ? "Candidate ready"
                          : projectTakeawayManualOverrideNeeded
                            ? "Override review"
                            : "Observation first"}
                    </strong>
                  </div>
                </div>

                <VerificationGateNote
                  verification={{
                    verification_status: verificationStatus,
                    allowed_downstream_actions: allowedDownstreamActions,
                    blocked_downstream_actions: blockedDownstreamActions,
                    claim_support_summary: claimSupportSummary,
                  }}
                  style={{ marginTop: "0" }}
                />

                <div style={manualNextActionStyle}>{manualSignalNextAction}</div>

                {(insight?.upload_reason || insight?.intended_use || insight?.cognitive_layer) && (
                  <div style={{ marginTop: "10px", display: "flex", gap: "8px", flexWrap: "wrap", color: "#374151" }}>
                    {insight.upload_reason ? <span style={manualMetadataChipStyle}>Reason: {insight.upload_reason}</span> : null}
                    {insight.intended_use ? <span style={manualMetadataChipStyle}>Use: {insight.intended_use}</span> : null}
                    <span style={manualMetadataChipStyle}>Layer: {formatCompactLabel(insight.cognitive_layer || "unclassified")}</span>
                  </div>
                )}

                <div style={manualSignalHandoffActionsStyle}>
                  {insight.manual_session_id ? (
                    <Link
                      href={`/manual/detail?id=${encodeURIComponent(insight.manual_session_id)}`}
                      style={manualSignalHandoffPrimaryLinkStyle}
                    >
                      Open Manual Session
                    </Link>
                  ) : null}
                  {hasWorkspaceRecord ? (
                    <Link href={workspaceRecordHref} style={manualWorkspaceLinkStyle}>
                      Open Workspace Record
                    </Link>
                  ) : null}
                  <Link href={reviewInboxHref} style={manualWorkspaceLinkStyle}>
                    Open Review Inbox
                  </Link>
                </div>

                {(manualSessionSourceNote || manualGenerationNote) && (
                  <div style={manualSourceContextGridStyle}>
                    {manualSessionSourceNote ? (
                      <div style={manualSourceContextCardStyle}>
                        <span style={manualSourceContextLabelStyle}>Manual Session Link</span>
                        <strong>{manualSessionSourceNote}</strong>
                      </div>
                    ) : null}
                    {manualGenerationNote ? (
                      <div style={manualSourceContextCardStyle}>
                        <span style={manualSourceContextLabelStyle}>Generation Context</span>
                        <strong>{manualGenerationNote}</strong>
                      </div>
                    ) : null}
                  </div>
                )}
                {manualProjectTakeawayHandoff ? (
                  <div style={manualHandoffPanelStyle}>
                    <span style={manualSourceContextLabelStyle}>Project Takeaway Handoff</span>
                    <strong>{manualProjectTakeawayHandoff}</strong>
                    <div style={manualHandoffMetaStyle}>
                      <span>Gate: {projectTakeawayGateMessage}</span>
                      {insight.upload_reason ? <span>Reason: {insight.upload_reason}</span> : null}
                      {insight.intended_use ? <span>Use: {insight.intended_use}</span> : null}
                      <span>Layer: {formatCompactLabel(insight.cognitive_layer || "unclassified")}</span>
                    </div>
                  </div>
                ) : null}
                {hasWorkspaceRecord ? (
                  <div style={manualWorkspaceSavedStyle}>
                    <span>
                      Workspace saved{insight?.workspace_saved_at ? `: ${formatDateTime(insight.workspace_saved_at)}` : ""}.
                    </span>
                    <Link href={workspaceRecordHref} style={manualWorkspaceLinkStyle}>
                      Open Workspace Record
                    </Link>
                  </div>
                ) : null}
              </div>
            ) : null}

              {showSaveReason && (
                <div
                  style={{
                  marginTop: "16px",
                  border: "1px solid #e5e7eb",
                  background: "#ffffff",
                  borderRadius: "8px",
                  padding: "16px",
                }}
              >
                <div
                  style={{
                    fontSize: "13px",
                    fontWeight: 700,
                    color: "#6b7280",
                    marginBottom: "12px",
                    textTransform: "uppercase",
                    letterSpacing: "0.4px",
                  }}
                >
                  Save reason
                </div>

                <div
                  style={{
                    display: "flex",
                    flexWrap: "wrap",
                    gap: "12px",
                    marginBottom: "12px",
                  }}
                >
                  {["Industry Trend", "AI Radar", "GLAP", "AI Cognitive", "Career", "Other"].map(
                    (reason) => (
                      <label
                        key={reason}
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: "8px",
                          fontSize: "14px",
                          color: "#333",
                        }}
                      >
                        <input
                          type="checkbox"
                          name="save-reason"
                          value={reason}
                          checked={selectedSaveReasons.includes(reason)}
                          disabled={isRejectedLocked}
                          onChange={() => toggleSaveReason(reason)}
                        />
                        {reason}
                      </label>
                    )
                  )}
                </div>

                {selectedSaveReasons.includes("Other") && (
                  <textarea
                    value={customSaveReason}
                    onChange={(e) => setCustomSaveReason(e.target.value)}
                    readOnly={isRejectedLocked}
                    placeholder="Write your reason."
                    style={{
                      width: "100%",
                      minHeight: "90px",
                      padding: "10px",
                      borderRadius: "8px",
                      border: "1px solid #d1d5db",
                      fontFamily: "Arial",
                      fontSize: "14px",
                      resize: "vertical",
                      boxSizing: "border-box",
                      marginBottom: "12px",
                    }}
                  />
                )}

                <div
                  style={{
                    display: "flex",
                    gap: "10px",
                    flexWrap: "wrap",
                  }}
                >
                  <button
                    onClick={async () => {
                      const reason = getResolvedSaveReason();

                      if (!reason) {
                        setStatusError("Please select at least one save reason. If you choose Other, write the custom reason.");
                        return;
                      }

                      setShowSaveReason(false);
                      await persistStatus("saved", reason);
                    }}
                    disabled={statusUpdating || isRejectedLocked}
                    style={{
                      ...detailActionPrimaryStyle,
                      background: statusUpdating || isRejectedLocked ? "#f3f4f6" : "#111827",
                      cursor: statusUpdating || isRejectedLocked ? "not-allowed" : "pointer",
                      color: statusUpdating || isRejectedLocked ? "#6b7280" : "#ffffff",
                    }}
                  >
                    Confirm Save
                  </button>

                  <button
                    onClick={() => {
                      setShowSaveReason(false);
                      setCustomSaveReason("");
                      setStatusError("");
                    }}
                    style={detailActionSecondaryStyle}
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}
          </div>

          {showVerificationObjectSurface && (
            <div
              style={{
                border: "1px solid #e5e7eb",
                borderRadius: "8px",
                padding: "18px",
                background: "#ffffff",
                marginBottom: "16px",
                boxShadow: "0 4px 14px rgba(15, 23, 42, 0.04)",
              }}
            >
              <VerifiedInsightObjectPanel
                rows={verifiedInsightObjectRows}
                objectId={verifiedInsight?.id}
                subtitle="Read-only product view of the current verification metadata. It explains downstream eligibility but does not change gates, create evidence, or unlock actions."
                style={{ marginBottom: "14px" }}
              />
              <div
                style={{
                  fontSize: "12px",
                  fontWeight: 700,
                  color: "#6b7280",
                  marginBottom: "6px",
                  textTransform: "uppercase",
                  letterSpacing: "0.5px",
                }}
              >
                Evidence Note
              </div>
              <div style={{ color: "#374151", fontSize: "14px", lineHeight: 1.6 }}>
                {hasEvidenceQuality
                  ? isLowEvidence
                    ? `This insight is based on ${evidenceLevel === "insufficient" ? "insufficient" : "thin"} evidence, so it should be read as a cautious interpretation rather than a strong conclusion.`
                    : `Evidence quality is ${evidenceLevel || "available"}, so this insight has a traceable evidence summary attached.`
                  : hasEvidencePack
                    ? "An evidence pack is attached to this insight, but evidence-quality scoring is not available on this saved record yet. Regenerate the insight to compute score, source, and reason metadata."
                    : "Verification metadata is attached to this saved record, but evidence-quality scoring is not available yet. Treat the object as a read-only gate snapshot until regenerated or reviewed."}
              </div>
              <div style={{ color: "#6b7280", fontSize: "13px", lineHeight: 1.6, marginTop: "8px" }}>
                Score: {typeof evidenceQuality?.score === "number" ? evidenceQuality.score.toFixed(2) : "N/A"} | Summary source: {formatSummaryProvenance(evidenceQuality?.summary_provenance)}
              </div>
              {(verificationStatus || confidenceLabel || typeof confidenceScore === "number") && (
                <div style={{ color: "#6b7280", fontSize: "13px", lineHeight: 1.6, marginTop: "8px" }}>
                  Verification: {formatCompactLabel(verificationStatus)}
                  {confidenceLabel ? ` | Confidence: ${formatCompactLabel(confidenceLabel)}` : ""}
                  {typeof confidenceScore === "number" ? ` (${confidenceScore.toFixed(2)})` : ""}
                </div>
              )}
              {hasGeneratedInsightContent ? (
                <div style={{ color: "#6b7280", fontSize: "13px", lineHeight: 1.6, marginTop: "8px" }}>
                  Model provenance: {modelProvenanceLine}
                </div>
              ) : null}
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
              <div style={{ color: "var(--app-text-muted)", fontSize: "13px", lineHeight: 1.6, marginTop: "8px" }}>
                {reviewPriorityExplanation}
              </div>
              <VerificationGateNote
                verification={{
                  verification_status: verificationStatus,
                  allowed_downstream_actions: allowedDownstreamActions,
                  blocked_downstream_actions: blockedDownstreamActions,
                  claim_support_summary: claimSupportSummary,
                }}
                accentColor={reviewPriority.color}
                style={{ marginTop: "10px" }}
              />
              <details
                style={{
                  marginTop: "12px",
                  border: "1px solid var(--app-surface-border)",
                  borderRadius: "8px",
                  background: "var(--app-surface-bg)",
                  padding: "12px",
                }}
              >
                <summary style={{ color: "var(--app-text-strong)", fontSize: "14px", fontWeight: 800, cursor: "pointer" }}>
                  Verification Details
                </summary>
                <div style={{ color: "var(--app-text-muted)", fontSize: "13px", lineHeight: 1.6 }}>
                  {verificationDecisionSummary.headline}
                </div>
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))",
                    gap: "8px",
                  }}
                >
                  <div style={{ color: "var(--app-success-fg)", fontSize: "13px", lineHeight: 1.55 }}>
                    <strong>Usable:</strong> {verificationDecisionSummary.usable}
                  </div>
                  <div style={{ color: "var(--app-danger-fg)", fontSize: "13px", lineHeight: 1.55 }}>
                    <strong>Blocked:</strong> {verificationDecisionSummary.blocked}
                  </div>
                  <div style={{ color: "var(--app-warning-fg)", fontSize: "13px", lineHeight: 1.55 }}>
                    <strong>Next review:</strong> {verificationDecisionSummary.focus}
                  </div>
                </div>
                <div style={{ color: "var(--app-text-muted)", fontSize: "12px", lineHeight: 1.5 }}>
                  {verificationDecisionSummary.supportLine} {verificationDecisionSummary.downgradeLine}
                </div>
                <div style={{ color: "var(--app-text-strong)", fontSize: "13px", lineHeight: 1.6, fontWeight: 800 }}>
                  {getClaimSupportDecisionLine(claimSupportSummary, blockedDownstreamActions)}
                </div>
                <div style={{ marginTop: "12px" }}>
                  <div
                    style={{
                      color: "var(--app-text-muted)",
                      fontSize: "12px",
                      fontWeight: 700,
                      textTransform: "uppercase",
                      letterSpacing: 0,
                      marginBottom: "8px",
                    }}
                  >
                    Gate Snapshot
                  </div>
                  <div style={{ color: "var(--app-text-muted)", fontSize: "12px", lineHeight: 1.5, marginBottom: "8px" }}>
                    Read-only projection of current allowed_downstream_actions and blocked_downstream_actions. This display does not change verification status or unlock actions.
                  </div>
                  <div
                    style={{
                      display: "grid",
                      gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
                      gap: "8px",
                    }}
                  >
                    {gateSnapshotRows.map((row) => {
                      const toneStyle =
                        row.tone === "good"
                          ? { border: "1px solid var(--app-success-border)", background: "var(--app-success-bg)", color: "var(--app-success-fg)" }
                          : row.tone === "bad"
                            ? { border: "1px solid var(--app-danger-border)", background: "var(--app-danger-bg)", color: "var(--app-danger-fg)" }
                            : { border: "1px solid var(--app-surface-border)", background: "var(--app-surface-muted-bg)", color: "var(--app-text-muted)" };
                      return (
                        <div
                          key={row.action}
                          style={{
                            border: toneStyle.border,
                            borderRadius: "10px",
                            background: toneStyle.background,
                            padding: "9px 10px",
                          }}
                        >
                          <div style={{ color: "var(--app-text-strong)", fontSize: "12px", fontWeight: 800 }}>
                            {row.label}
                          </div>
                          <div style={{ color: toneStyle.color, fontSize: "13px", fontWeight: 800, marginTop: "4px" }}>
                            {row.status}
                          </div>
                          <div style={{ color: "var(--app-text-subtle)", fontSize: "11px", lineHeight: 1.45, marginTop: "4px" }}>
                            {row.detail}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              {(formatClaimSupportSummary(claimSupportSummary) || claimCoverageSnapshot.total > 0) && (
                <div style={{ marginTop: "12px" }}>
                  <div
                    style={{
                      color: isLowEvidence || !hasEvidenceQuality ? "var(--app-warning-fg)" : "var(--app-success-fg)",
                      fontSize: "12px",
                      fontWeight: 700,
                      textTransform: "uppercase",
                      letterSpacing: 0,
                      marginBottom: "8px",
                    }}
                  >
                    Evidence Grounding
                  </div>
                  <div style={{ color: "var(--app-text-muted)", fontSize: "12px", lineHeight: 1.5, marginBottom: "8px" }}>
                    Claim grounding counts and coverage are read-time counts only; no threshold label or source reliability score is inferred here.
                  </div>
                  {sourceLimitsRecord.shouldShow ? (
                    <div
                      style={{
                        border: sourceLimitsRecord.style.border,
                        borderRadius: "10px",
                        background: sourceLimitsRecord.style.background,
                        padding: "10px 12px",
                        marginBottom: "10px",
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
                        <span style={{ color: sourceLimitsRecord.style.color, fontSize: "12px", fontWeight: 850 }}>
                          Source Limits Record
                        </span>
                        <span style={{ color: sourceLimitsRecord.style.color, fontSize: "12px", fontWeight: 800 }}>
                          {sourceLimitsRecord.label}
                        </span>
                        {sourceLimitsRecord.confidence ? (
                          <span style={{ color: "var(--app-text-muted)", fontSize: "12px", fontWeight: 700 }}>
                            Confidence: {sourceLimitsRecord.confidence}
                          </span>
                        ) : null}
                      </div>
                      <div style={{ color: "var(--app-text-strong)", fontSize: "12px", lineHeight: 1.5 }}>
                        {sourceLimitsRecord.detail}
                      </div>
                      {sourceLimitsRecord.text ? (
                        <div
                          style={{
                            borderLeft: `3px solid ${sourceLimitsRecord.style.color}`,
                            color: "var(--app-text-muted)",
                            fontSize: "12px",
                            lineHeight: 1.5,
                            marginTop: "7px",
                            paddingLeft: "9px",
                          }}
                        >
                          {sourceLimitsRecord.text}
                        </div>
                      ) : null}
                      {presentationFidelitySummary.total > 0 ? (
                        <div style={{ color: "var(--app-text-subtle)", fontSize: "11px", lineHeight: 1.45, marginTop: "7px" }}>
                          Claim presentation states: {presentationFidelitySummary.exceeded} exceeded, {presentationFidelitySummary.preserved} preserved, {presentationFidelitySummary.absentUnknown} coverage gaps, {presentationFidelitySummary.notApplicable} not applicable.
                        </div>
                      ) : null}
                    </div>
                  ) : null}
                  <div
                    style={{
                      display: "grid",
                      gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))",
                      gap: "8px",
                    }}
                  >
                    {claimSupportRows.map((row) => {
                      const toneStyle =
                        row.tone === "good"
                          ? { border: "1px solid var(--app-success-border)", background: "var(--app-success-bg)", color: "var(--app-success-fg)" }
                          : row.tone === "bad"
                            ? { border: "1px solid var(--app-danger-border)", background: "var(--app-danger-bg)", color: "var(--app-danger-fg)" }
                            : { border: "1px solid var(--app-warning-border)", background: "var(--app-warning-bg)", color: "var(--app-warning-fg)" };
                      return (
                        <div
                          key={row.key}
                          style={{
                            border: toneStyle.border,
                            borderRadius: "10px",
                            background: toneStyle.background,
                            padding: "9px 10px",
                          }}
                        >
                          <div style={{ color: toneStyle.color, fontSize: "12px", fontWeight: 800 }}>
                            {row.label}
                          </div>
                          <div style={{ color: toneStyle.color, fontSize: "20px", fontWeight: 850, marginTop: "4px" }}>
                            {row.count}
                          </div>
                        </div>
                      );
                    })}
                    <div
                      style={{
                        border: "1px solid var(--app-surface-border)",
                        borderRadius: "10px",
                        background: "var(--app-surface-muted-bg)",
                        padding: "9px 10px",
                      }}
                    >
                      <div style={{ color: "var(--app-text-muted)", fontSize: "12px", fontWeight: 800 }}>
                        Evidence refs
                      </div>
                      <div style={{ color: "var(--app-text-muted)", fontSize: "16px", fontWeight: 850, marginTop: "4px" }}>
                        {claimCoverageSnapshot.evidenceRefCoverage}
                      </div>
                    </div>
                    <div
                      style={{
                        border: "1px solid var(--app-surface-border)",
                        borderRadius: "10px",
                        background: "var(--app-surface-muted-bg)",
                        padding: "9px 10px",
                      }}
                    >
                      <div style={{ color: "var(--app-text-muted)", fontSize: "12px", fontWeight: 800 }}>
                        Source spans
                      </div>
                      <div style={{ color: "var(--app-text-muted)", fontSize: "16px", fontWeight: 850, marginTop: "4px" }}>
                        {claimCoverageSnapshot.sourceSpanCoverage}
                      </div>
                    </div>
                    {presentationFidelitySummary.total > 0 ? (
                      <>
                        <div
                          style={{
                            border: "1px solid var(--app-danger-border)",
                            borderRadius: "10px",
                            background: "var(--app-danger-bg)",
                            padding: "9px 10px",
                          }}
                        >
                          <div style={{ color: "var(--app-danger-fg)", fontSize: "12px", fontWeight: 800 }}>
                            Source limit exceeded
                          </div>
                          <div style={{ color: "var(--app-danger-fg)", fontSize: "16px", fontWeight: 850, marginTop: "4px" }}>
                            {presentationFidelitySummary.exceeded}/{presentationFidelitySummary.total}
                          </div>
                        </div>
                        <div
                          style={{
                            border: "1px solid var(--app-warning-border)",
                            borderRadius: "10px",
                            background: "var(--app-warning-bg)",
                            padding: "9px 10px",
                          }}
                        >
                          <div style={{ color: "var(--app-warning-fg)", fontSize: "12px", fontWeight: 800 }}>
                            Source limits coverage gap
                          </div>
                          <div style={{ color: "var(--app-warning-fg)", fontSize: "16px", fontWeight: 850, marginTop: "4px" }}>
                            {presentationFidelitySummary.absentUnknown}/{presentationFidelitySummary.total}
                          </div>
                        </div>
                        <div
                          style={{
                            border: "1px solid var(--app-success-border)",
                            borderRadius: "10px",
                            background: "var(--app-success-bg)",
                            padding: "9px 10px",
                          }}
                        >
                          <div style={{ color: "var(--app-success-fg)", fontSize: "12px", fontWeight: 800 }}>
                            Source limits preserved
                          </div>
                          <div style={{ color: "var(--app-success-fg)", fontSize: "16px", fontWeight: 850, marginTop: "4px" }}>
                            {presentationFidelitySummary.preserved}/{presentationFidelitySummary.total}
                          </div>
                        </div>
                        <div
                          style={{
                            border: "1px solid var(--app-surface-border)",
                            borderRadius: "10px",
                            background: "var(--app-surface-muted-bg)",
                            padding: "9px 10px",
                          }}
                        >
                          <div style={{ color: "var(--app-text-muted)", fontSize: "12px", fontWeight: 800 }}>
                            Source limits not applicable
                          </div>
                          <div style={{ color: "var(--app-text-muted)", fontSize: "16px", fontWeight: 850, marginTop: "4px" }}>
                            {presentationFidelitySummary.notApplicable}/{presentationFidelitySummary.total}
                          </div>
                        </div>
                      </>
                    ) : null}
                  </div>
                  {presentationFidelitySummary.total > 0 ? (
                    <div style={{ color: "var(--app-text-subtle)", fontSize: "12px", lineHeight: 1.5, marginTop: "8px" }}>
                      Presentation fidelity is read-only. Coverage gap means no source-stated limits metadata was recorded; it is not a claim that the source stripped a caveat.
                    </div>
                  ) : null}
                </div>
              )}
              {evidenceReasonCodes.length > 0 && (
                <div style={{ color: isLowEvidence || !hasEvidenceQuality ? "var(--app-warning-fg)" : "var(--app-success-fg)", fontSize: "13px", lineHeight: 1.6, marginTop: "8px" }}>
                  Why: {formatEvidenceReason(evidenceReasonCodes[0])}
                </div>
              )}
              {lowEvidenceNotes.length > 0 && (
                <div style={{ color: isLowEvidence || !hasEvidenceQuality ? "var(--app-warning-fg)" : "var(--app-success-fg)", fontSize: "13px", lineHeight: 1.6, marginTop: "8px" }}>
                  {lowEvidenceNotes[0]}
                </div>
              )}
              {(downgradeReason || verificationLimitations.length > 0) && (
                <div style={{ color: isLowEvidence || !hasEvidenceQuality ? "var(--app-warning-fg)" : "var(--app-success-fg)", fontSize: "13px", lineHeight: 1.6, marginTop: "8px" }}>
                  {downgradeReason ? `Downgrade: ${formatCompactLabel(downgradeReason)}.` : null}
                  {verificationLimitations.length > 0 ? ` Limitation: ${formatCompactLabel(verificationLimitations[0])}.` : null}
                </div>
              )}
              {(allowedDownstreamActions.length > 0 || blockedDownstreamActions.length > 0) && (
                <div
                  style={{
                    marginTop: "12px",
                    display: "grid",
                    gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
                    gap: "10px",
                  }}
                >
                  <div
                    style={{
                      border: "1px solid var(--app-success-border)",
                      borderRadius: "10px",
                      padding: "10px 12px",
                      background: "var(--app-success-bg)",
                    }}
                  >
                    <div style={{ color: "var(--app-success-fg)", fontSize: "12px", fontWeight: 700, marginBottom: "6px", textTransform: "uppercase", letterSpacing: 0 }}>
                      Allowed
                    </div>
                    <div style={{ color: "var(--app-success-fg)", fontSize: "13px", lineHeight: 1.6 }}>
                      {allowedDownstreamActions.length > 0
                        ? allowedDownstreamActions.map(formatCompactLabel).join(", ")
                        : "None"}
                    </div>
                  </div>
                  <div
                    style={{
                      border: "1px solid var(--app-danger-border)",
                      borderRadius: "10px",
                      padding: "10px 12px",
                      background: "var(--app-danger-bg)",
                    }}
                  >
                    <div style={{ color: "var(--app-danger-fg)", fontSize: "12px", fontWeight: 700, marginBottom: "6px", textTransform: "uppercase", letterSpacing: 0 }}>
                      Blocked
                    </div>
                    <div style={{ color: "var(--app-danger-fg)", fontSize: "13px", lineHeight: 1.6 }}>
                      {blockedDownstreamActions.length > 0
                        ? blockedDownstreamActions.map(formatCompactLabel).join(", ")
                        : "None"}
                    </div>
                  </div>
                </div>
              )}
              </details>
              <div
                style={{
                  marginTop: "12px",
                  paddingTop: "12px",
                  borderTop: `1px solid ${isLowEvidence || !hasEvidenceQuality ? "var(--app-warning-border)" : "var(--app-success-border)"}`,
                }}
              >
                <div style={{ color: isLowEvidence || !hasEvidenceQuality ? "var(--app-warning-fg)" : "var(--app-success-fg)", fontSize: "13px", lineHeight: 1.6 }}>
                  Project Takeaway Gate: {projectTakeawayGateMessage}
                </div>
                {showDeepProjectMatchReview ? (
                  <details
                    style={{
                      marginTop: "10px",
                      border: "1px solid var(--app-info-border)",
                      borderRadius: "8px",
                      background: "var(--app-info-bg)",
                      padding: "12px",
                    }}
                  >
                    <summary style={{ display: "flex", justifyContent: "space-between", gap: "12px", alignItems: "flex-start", cursor: "pointer" }}>
                      <div>
                        <div style={{ color: "var(--app-info-fg)", fontSize: "12px", fontWeight: 800, textTransform: "uppercase", letterSpacing: 0 }}>
                          Deep Project Match Review
                        </div>
                        <div style={{ marginTop: "4px", color: "var(--app-text-strong)", fontSize: "14px", fontWeight: 800 }}>
                          {deepProjectMatchReview.posture} - {formatCompactLabel(deepProjectMatchReview.matchType)}
                        </div>
                      </div>
                      <span
                        style={{
                          border: "1px solid var(--app-info-border)",
                          borderRadius: "999px",
                          color: "var(--app-info-fg)",
                          background: "var(--app-surface-muted-bg)",
                          padding: "4px 8px",
                          fontSize: "11px",
                          fontWeight: 800,
                          textTransform: "uppercase",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {formatCompactLabel(deepProjectMatchReview.evidenceBoundary)}
                      </span>
                    </summary>
                    <p style={{ margin: "8px 0 10px", color: "var(--app-text-muted)", fontSize: "13px", lineHeight: 1.55 }}>
                      {deepProjectMatchReview.reason}
                    </p>
                    <div style={{ display: "grid", gap: "8px" }}>
                      {deepProjectMatchReview.checklist.map((item) => (
                        <div
                          key={item.key}
                          style={{
                            border: "1px solid var(--app-surface-border)",
                            borderRadius: "8px",
                            background: "var(--app-surface-bg)",
                            padding: "8px 10px",
                          }}
                        >
                          <div
                            style={{
                              display: "flex",
                              justifyContent: "space-between",
                              gap: "8px",
                              alignItems: "center",
                            }}
                          >
                            <span style={{ color: "var(--app-text-subtle)", fontSize: "11px", fontWeight: 800, textTransform: "uppercase", letterSpacing: 0 }}>
                              {item.label}
                            </span>
                            <span
                              style={{
                                color: item.status === "risk" ? "var(--app-danger-fg)" : item.status === "watch" ? "var(--app-warning-fg)" : "var(--app-success-fg)",
                                fontSize: "11px",
                                fontWeight: 800,
                                textTransform: "uppercase",
                              }}
                            >
                              {item.status}
                            </span>
                          </div>
                          <div style={{ marginTop: "4px", color: "var(--app-text-strong)", fontSize: "13px", lineHeight: 1.45 }}>
                            {item.value}
                          </div>
                        </div>
                      ))}
                    </div>
                    <label
                      style={{
                        display: "block",
                        marginTop: "10px",
                        color: "var(--app-info-fg)",
                        fontSize: "12px",
                        fontWeight: 800,
                        textTransform: "uppercase",
                        letterSpacing: 0,
                      }}
                    >
                      Review note
                      <textarea
                        value={deepProjectMatchReviewNote || deepProjectMatchReview.suggestedReviewNote}
                        onChange={(event) => setDeepProjectMatchReviewNote(event.target.value)}
                        rows={7}
                        style={{
                          display: "block",
                          width: "100%",
                          boxSizing: "border-box",
                          marginTop: "6px",
                          border: "1px solid var(--app-input-border)",
                          borderRadius: "8px",
                          padding: "8px 10px",
                          color: "var(--app-input-fg)",
                          background: "var(--app-input-bg)",
                          fontSize: "13px",
                          lineHeight: 1.45,
                          minHeight: "140px",
                          resize: "vertical",
                        }}
                      />
                    </label>
                    <div style={{ marginTop: "8px", color: "var(--app-text-muted)", fontSize: "12px", lineHeight: 1.5 }}>
                      {deepProjectMatchReview.downstreamPosture}
                    </div>
                    <div style={{ marginTop: "10px", display: "flex", gap: "8px", flexWrap: "wrap", alignItems: "center" }}>
                      <button
                        type="button"
                        onClick={() => void handleGenerateDeepProjectMatchAnalysis()}
                        disabled={deepProjectMatchAnalysisLoading || isRejectedLocked}
                        style={{
                          ...detailActionPrimaryStyle,
                          padding: "7px 12px",
                          ...(deepProjectMatchAnalysisLoading || isRejectedLocked ? detailActionDisabledStyle : {}),
                          cursor: deepProjectMatchAnalysisLoading || isRejectedLocked ? "not-allowed" : "pointer",
                          fontSize: "13px",
                          fontWeight: 800,
                        }}
                      >
                        {deepProjectMatchAnalysisLoading ? "Generating..." : "Generate Deep Match Analysis"}
                      </button>
                      <span style={{ color: "var(--app-text-muted)", fontSize: "12px", lineHeight: 1.4 }}>
                        Optional review aid. Does not change verification or Action gates.
                      </span>
                    </div>
                    {deepProjectMatchAnalysisError ? (
                      <div
                        style={{
                          marginTop: "8px",
                          border: "1px solid var(--app-danger-border)",
                          borderRadius: "8px",
                          background: "var(--app-danger-bg)",
                          color: "var(--app-danger-fg)",
                          padding: "8px 10px",
                          fontSize: "12px",
                          lineHeight: 1.45,
                        }}
                      >
                        {deepProjectMatchAnalysisError}
                      </div>
                    ) : null}
                    {deepProjectMatchAnalysis ? (
                      <div
                        style={{
                          marginTop: "10px",
                          border: "1px solid var(--app-surface-border)",
                          borderRadius: "8px",
                          background: "var(--app-surface-bg)",
                          padding: "12px",
                          display: "grid",
                          gap: "10px",
                        }}
                      >
                        <div style={{ color: "var(--app-text-subtle)", fontSize: "12px", fontWeight: 800, textTransform: "uppercase", letterSpacing: 0 }}>
                          Generated Analysis
                        </div>
                        <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                          <span
                            style={{
                              border: "1px solid var(--app-warning-border)",
                              borderRadius: "999px",
                              background: "var(--app-warning-bg)",
                              color: "var(--app-warning-fg)",
                              padding: "4px 8px",
                              fontSize: "11px",
                              fontWeight: 800,
                              textTransform: "uppercase",
                            }}
                          >
                            {formatCompactLabel(deepProjectMatchAnalysis.source_depth_tier || "metadata")} tier
                          </span>
                          <span
                            style={{
                              border: "1px solid var(--app-warning-border)",
                              borderRadius: "999px",
                              background: "var(--app-warning-bg)",
                              color: "var(--app-warning-fg)",
                              padding: "4px 8px",
                              fontSize: "11px",
                              fontWeight: 800,
                              textTransform: "uppercase",
                            }}
                          >
                            {formatCompactLabel(deepProjectMatchAnalysis.hypothesis_status || deepProjectMatchAnalysis.differentiated_insight_status || "not_enough_metadata")}
                          </span>
                        </div>
                        {deepProjectMatchAnalysis.narrative_summary ? (
                          <p style={{ margin: 0, color: "var(--app-text-strong)", fontSize: "14px", lineHeight: 1.6 }}>
                            {deepProjectMatchAnalysis.narrative_summary}
                          </p>
                        ) : null}
                        {deepProjectMatchAnalysis.source_claim_reading ? (
                          <div
                            style={{
                              borderTop: "1px solid var(--app-surface-border)",
                              paddingTop: "8px",
                              display: "grid",
                              gap: "8px",
                            }}
                          >
                            <div style={{ color: "var(--app-text-subtle)", fontSize: "11px", fontWeight: 800, textTransform: "uppercase", letterSpacing: 0 }}>
                              Source claim reading
                            </div>
                            <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                              <span
                                style={{
                                  border: "1px solid var(--app-info-border)",
                                  borderRadius: "999px",
                                  background: "var(--app-info-bg)",
                                  color: "var(--app-info-fg)",
                                  padding: "3px 8px",
                                  fontSize: "11px",
                                  fontWeight: 800,
                                  textTransform: "uppercase",
                                }}
                              >
                                Read depth: {formatCompactLabel(deepProjectMatchAnalysis.source_claim_reading.source_read_depth || deepProjectMatchAnalysis.source_depth_tier || "metadata")}
                              </span>
                              <span
                                style={{
                                  border: "1px solid var(--app-chip-border)",
                                  borderRadius: "999px",
                                  background: "var(--app-chip-bg)",
                                  color: "var(--app-chip-fg)",
                                  padding: "3px 8px",
                                  fontSize: "11px",
                                  fontWeight: 800,
                                  textTransform: "uppercase",
                                }}
                              >
                                Reliability: {formatCompactLabel(deepProjectMatchAnalysis.source_claim_reading.source_claim_reliability || "unknown")}
                              </span>
                            </div>
                            {deepProjectMatchAnalysis.source_claim_reading.summary ? (
                              <div style={{ color: "var(--app-text-strong)", fontSize: "13px", lineHeight: 1.5 }}>
                                {deepProjectMatchAnalysis.source_claim_reading.summary}
                              </div>
                            ) : null}
                            {Array.isArray(deepProjectMatchAnalysis.source_claim_reading.claims) &&
                            deepProjectMatchAnalysis.source_claim_reading.claims.length > 0 ? (
                              <div style={{ display: "grid", gap: "8px" }}>
                                {deepProjectMatchAnalysis.source_claim_reading.claims.map((claim, claimIndex) => (
                                  <div
                                    key={`${claim.source_claim || "source-claim"}-${claimIndex}`}
                                    style={{
                                      border: "1px solid var(--app-surface-border)",
                                      borderRadius: "8px",
                                      padding: "8px 10px",
                                      background: "var(--app-surface-muted-bg)",
                                    }}
                                  >
                                    <div style={{ display: "flex", justifyContent: "space-between", gap: "8px", flexWrap: "wrap" }}>
                                      <span style={{ color: "var(--app-text-subtle)", fontSize: "11px", fontWeight: 800, textTransform: "uppercase", letterSpacing: 0 }}>
                                        Claim {claimIndex + 1}
                                      </span>
                                      <span style={{ color: "var(--app-info-fg)", fontSize: "11px", fontWeight: 800, textTransform: "uppercase", letterSpacing: 0 }}>
                                        {formatCompactLabel(claim.source_assertion_type || "unknown")}
                                      </span>
                                    </div>
                                    {claim.source_claim ? (
                                      <div style={{ marginTop: "4px", color: "var(--app-text-strong)", fontSize: "13px", lineHeight: 1.45 }}>
                                        {claim.source_claim}
                                      </div>
                                    ) : null}
                                    {claim.evidence_locator ? (
                                      <div style={{ marginTop: "4px", color: "var(--app-text-muted)", fontSize: "12px", lineHeight: 1.4 }}>
                                        Locator: {claim.evidence_locator}
                                      </div>
                                    ) : null}
                                    {claim.limitation ? (
                                      <div style={{ marginTop: "4px", color: "var(--app-warning-fg)", fontSize: "12px", lineHeight: 1.4 }}>
                                        Limitation: {claim.limitation}
                                      </div>
                                    ) : null}
                                  </div>
                                ))}
                              </div>
                            ) : (
                              <div style={{ color: "var(--app-text-subtle)", fontSize: "12px", lineHeight: 1.4 }}>
                                No source-side claim was typed at this depth. Metadata-tier output still needs source read before becoming source-grounded.
                              </div>
                            )}
                          </div>
                        ) : null}
                        <div style={{ display: "grid", gap: "8px" }}>
                          {[
                            ["Signal-side fact", deepProjectMatchAnalysis.signal_side_fact],
                            ["AI Radar-side fact", deepProjectMatchAnalysis.ai_radar_side_fact],
                            ["Suspected differentiated insight", deepProjectMatchAnalysis.suspected_differentiated_insight],
                            ["Concrete relevance", deepProjectMatchAnalysis.concrete_relevance],
                            ["Architecture comparison", deepProjectMatchAnalysis.architecture_comparison],
                            ["Borrow", deepProjectMatchAnalysis.borrow],
                            ["Beware", deepProjectMatchAnalysis.beware],
                            ["Evidence boundary", deepProjectMatchAnalysis.evidence_boundary],
                            ["Evidence basis", deepProjectMatchAnalysis.evidence_basis],
                            ["Review note effect", deepProjectMatchAnalysis.review_note_effect],
                            ["Decision posture", deepProjectMatchAnalysis.decision_posture],
                          ].map(([label, value]) =>
                            value ? (
                              <div key={label} style={{ borderTop: "1px solid var(--app-surface-border)", paddingTop: "8px" }}>
                                <div style={{ color: "var(--app-text-subtle)", fontSize: "11px", fontWeight: 800, textTransform: "uppercase", letterSpacing: 0 }}>
                                  {label}
                                </div>
                                <div style={{ marginTop: "3px", color: "var(--app-text-strong)", fontSize: "13px", lineHeight: 1.5 }}>
                                  {value}
                                </div>
                              </div>
                            ) : null
                          )}
                        </div>
                        {deepProjectMatchAnalysis.needs_source_read ? (
                          <div
                            style={{
                              borderTop: "1px solid var(--app-warning-border)",
                              paddingTop: "8px",
                              color: "var(--app-warning-fg)",
                              fontSize: "13px",
                              lineHeight: 1.5,
                            }}
                          >
                            <strong>Needs source read:</strong>{" "}
                            {Array.isArray(deepProjectMatchAnalysis.source_read_targets) &&
                            deepProjectMatchAnalysis.source_read_targets.length > 0
                              ? deepProjectMatchAnalysis.source_read_targets
                                  .map((target) =>
                                    [
                                      target.url,
                                      target.path,
                                      target.section_hint,
                                      target.question ? `Question: ${target.question}` : "",
                                    ]
                                      .filter(Boolean)
                                      .join(" / ")
                                  )
                                  .join("; ")
                              : "Open the original source before treating this as a source-grounded insight."}
                          </div>
                        ) : null}
                        {deepProjectMatchAnalysisLayers.length > 1 ? (
                          <div style={{ color: "var(--app-text-subtle)", fontSize: "12px", lineHeight: 1.4 }}>
                            Analysis layers preserved: {deepProjectMatchAnalysisLayers.length}. Latest layer shown above.
                          </div>
                        ) : null}
                        {Array.isArray(deepProjectMatchAnalysis.structured_checklist) &&
                        deepProjectMatchAnalysis.structured_checklist.length > 0 ? (
                          <details style={{ borderTop: "1px solid var(--app-surface-border)", paddingTop: "8px" }}>
                            <summary style={{ color: "var(--app-info-fg)", fontSize: "12px", fontWeight: 800, cursor: "pointer" }}>
                              Generated structured checklist
                            </summary>
                            <div style={{ display: "grid", gap: "8px", marginTop: "8px" }}>
                              {deepProjectMatchAnalysis.structured_checklist.map((item, itemIndex) => (
                                <div
                                  key={`${item.label || "item"}-${itemIndex}`}
                                  style={{
                                    border: "1px solid var(--app-surface-border)",
                                    borderRadius: "8px",
                                    background: "var(--app-surface-muted-bg)",
                                    padding: "8px 10px",
                                  }}
                                >
                                  <div style={{ display: "flex", justifyContent: "space-between", gap: "8px" }}>
                                    <span style={{ color: "var(--app-text-subtle)", fontSize: "11px", fontWeight: 800, textTransform: "uppercase", letterSpacing: 0 }}>
                                      {item.label || "Finding"}
                                    </span>
                                    <span style={{ color: item.status === "risk" ? "var(--app-danger-fg)" : item.status === "ok" ? "var(--app-success-fg)" : "var(--app-warning-fg)", fontSize: "11px", fontWeight: 800, textTransform: "uppercase", letterSpacing: 0 }}>
                                      {item.status || "watch"}
                                    </span>
                                  </div>
                                  <div style={{ marginTop: "4px", color: "var(--app-text-strong)", fontSize: "13px", lineHeight: 1.45 }}>
                                    {item.value || "Not recorded"}
                                  </div>
                                </div>
                              ))}
                            </div>
                          </details>
                        ) : null}
                      </div>
                    ) : null}
                  </details>
                ) : null}
                <div style={{ marginTop: "10px", display: "flex", gap: "10px", flexWrap: "wrap", alignItems: "center" }}>
                  <div style={{ color: "var(--app-text-muted)", fontSize: "12px", lineHeight: 1.5 }}>
                    Project Review handoff now starts from Final Takeaway Confirmation. Confirm the Final Takeaway below, then use Send Final Takeaway to Review.
                  </div>
                  <Link
                    href={reviewInboxHref}
                    style={{
                      ...detailActionLinkStyle,
                      fontSize: "13px",
                    }}
                  >
                    Open Review Inbox
                  </Link>
                </div>
                {projectTakeawayManualOverrideNeeded ? (
                  <div
                    style={{
                      marginTop: "8px",
                      border: "1px solid var(--app-warning-border)",
                      borderRadius: "8px",
                      background: "var(--app-warning-bg)",
                      color: "var(--app-warning-fg)",
                      padding: "10px 12px",
                      fontSize: "12px",
                      lineHeight: 1.5,
                    }}
                  >
                    <div>
                      Final Takeaway override available: this records why the system gate was bypassed before sending the Andy-confirmed Final Takeaway to Review Inbox.
                    </div>
                    <label
                      style={{
                        display: "flex",
                        alignItems: "flex-start",
                        gap: "8px",
                        marginTop: "8px",
                        fontWeight: 700,
                      }}
                    >
                      <input
                        type="checkbox"
                        checked={projectTakeawayOverrideConfirmed}
                        disabled={isRejectedLocked}
                        onChange={(event) => setProjectTakeawayOverrideConfirmed(event.target.checked)}
                        style={{ marginTop: "3px" }}
                      />
                      <span>
                        I understand the Project Takeaway gate is blocked and still want to send this confirmed Final Takeaway to Review Inbox for human review.
                      </span>
                    </label>
                  </div>
                ) : !canCreateProjectTakeawayCandidate && (
                  <div style={{ color: "var(--app-text-subtle)", fontSize: "12px", lineHeight: 1.5, marginTop: "8px" }}>
                    Project Review handoff requires all three checks: verification allows the handoff, review priority is not Do Not Act, and project-relevant text exists.
                  </div>
                )}
                {projectCandidateMessage ? (
                  <div style={{ color: "var(--app-success-fg)", fontSize: "13px", lineHeight: 1.5, marginTop: "8px" }}>
                    {projectCandidateMessage}
                  </div>
                ) : null}
                {projectCandidateError ? (
                  <div style={{ color: "var(--app-danger-fg)", fontSize: "13px", lineHeight: 1.5, marginTop: "8px" }}>
                    {projectCandidateError}
                  </div>
                ) : null}
              </div>
              {claimResults.length > 0 && (
                <details
                  style={{
                    marginTop: "14px",
                    paddingTop: "12px",
                    borderTop: `1px solid ${isLowEvidence || !hasEvidenceQuality ? "var(--app-warning-border)" : "var(--app-success-border)"}`,
                  }}
                >
                  <summary
                    style={{
                      fontSize: "12px",
                      fontWeight: 700,
                      color: isLowEvidence || !hasEvidenceQuality ? "var(--app-warning-fg)" : "var(--app-success-fg)",
                      marginBottom: "8px",
                      textTransform: "uppercase",
                      letterSpacing: 0,
                      cursor: "pointer",
                    }}
                  >
                    Claim Checks ({claimResults.length})
                  </summary>
                  <div style={{ color: "var(--app-text-muted)", fontSize: "12px", lineHeight: 1.5, marginBottom: "8px" }}>
                    Inferred means useful interpretation, not source-proven fact. Internal judgment means project-fit reasoning, not external evidence.
                  </div>
                  {claimFeedbackLoading ? (
                    <div style={{ color: "var(--app-text-subtle)", fontSize: "12px", lineHeight: 1.5, marginBottom: "8px" }}>
                      Loading recorded feedback...
                    </div>
                  ) : null}
                  {claimFeedbackError ? (
                    <div style={{ color: "var(--app-danger-fg)", fontSize: "12px", lineHeight: 1.5, marginBottom: "8px" }}>
                      {claimFeedbackError}
                    </div>
                  ) : null}
                  <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                    {sortedClaimResults.slice(0, 5).map((claim, index) => {
                      const supportStyle = getClaimDisplayStyle(claim);
                      const isProjectRelevance = isProjectRelevanceClaim(claim);
                      const sourceExcerpt = getClaimSourceExcerpt(claim, insight?.evidence_pack);
                      const presentationFidelity = claim.presentation_fidelity || null;
                      const presentationFidelityStyle = getPresentationFidelityStyle(presentationFidelity?.limits_state);
                      const showPresentationFidelityDetail = shouldShowPresentationFidelityDetail(presentationFidelity?.limits_state);
                      const feedbackKey = getClaimFeedbackKey(claim, index);
                      const claimRecordId = getClaimFeedbackRecordId(claim, index);
                      const feedbackDraft = claimFeedbackDrafts[feedbackKey] || buildDefaultClaimFeedbackDraft();
                      const recordedFeedback = claimFeedbackRecords.filter(
                        (record) => String(record.claim_id || "") === claimRecordId
                      );
                      return (
                        <div
                          key={claim.claim_id || `${claim.claim_text}-${index}`}
                          style={{
                            border: supportStyle.border,
                            borderRadius: "10px",
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
                          {presentationFidelity ? (
                            <span
                              style={{
                                display: "inline-flex",
                                alignItems: "center",
                                border: presentationFidelityStyle.border,
                                borderRadius: "999px",
                                background: presentationFidelityStyle.background,
                                color: presentationFidelityStyle.color,
                                padding: "3px 8px",
                                fontSize: "11px",
                                fontWeight: 800,
                              }}
                            >
                              {getPresentationFidelityLabel(presentationFidelity.limits_state)}
                            </span>
                          ) : null}
                        </div>
                        <div style={{ color: "var(--app-text-strong)", fontSize: "13px", lineHeight: 1.55 }}>
                          {normalizedDisplayText(claim.claim_text, "Claim text unavailable.")}
                        </div>
                        {presentationFidelity && showPresentationFidelityDetail ? (
                          <div
                            style={{
                              marginTop: "8px",
                              border: presentationFidelityStyle.border,
                              borderRadius: "8px",
                              background: presentationFidelityStyle.background,
                              padding: "8px 10px",
                            }}
                          >
                            <div style={{ color: presentationFidelityStyle.color, fontSize: "12px", fontWeight: 800, marginBottom: "4px" }}>
                              Presentation fidelity: {getPresentationFidelityLabel(presentationFidelity.limits_state)}
                            </div>
                            <div style={{ color: "var(--app-text-strong)", fontSize: "12px", lineHeight: 1.5 }}>
                              {getPresentationFidelityDetail(presentationFidelity.limits_state)}
                            </div>
                            <div style={{ color: "var(--app-text-subtle)", fontSize: "11px", lineHeight: 1.45, marginTop: "4px" }}>
                              Source limits: {typeof presentationFidelity.source_stated_limits_count === "number" ? presentationFidelity.source_stated_limits_count : 0}
                              {" | "}
                              Source confidence: {presentationFidelity.source_stated_confidence_present ? "recorded" : "not recorded"}
                              {Array.isArray(presentationFidelity.reason_codes) && presentationFidelity.reason_codes.length > 0
                                ? ` | Reasons: ${presentationFidelity.reason_codes.map(formatCompactLabel).join(", ")}`
                                : ""}
                            </div>
                          </div>
                        ) : null}
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
                        {recordedFeedback.length > 0 ? (
                          <div
                            style={{
                              marginTop: "10px",
                              border: "1px solid var(--app-info-border)",
                              background: "var(--app-info-bg)",
                              borderRadius: "8px",
                              padding: "8px 10px",
                            }}
                          >
                            <div style={{ color: "var(--app-info-fg)", fontSize: "12px", fontWeight: 800, marginBottom: "6px" }}>
                              Recorded feedback ({recordedFeedback.length})
                            </div>
                            <div style={{ display: "grid", gap: "6px" }}>
                              {recordedFeedback.slice(0, 3).map((record) => {
                                const annotation = hasRelationshipAnnotation(record.relationship_annotation)
                                  ? record.relationship_annotation
                                  : null;
                                const annotationStyle = getRelationshipAnnotationStyle(annotation);
                                return (
                                  <div
                                    key={record.id || `${record.claim_id}-${record.created_at}`}
                                    style={{ color: "var(--app-text-strong)", fontSize: "12px", lineHeight: 1.45 }}
                                  >
                                    <div>
                                      <strong>{formatCompactLabel(record.reason_slot)}:</strong> {record.note || "No note recorded."}
                                      {record.created_at ? (
                                        <span style={{ color: "var(--app-text-subtle)" }}> | {formatDateTime(record.created_at)}</span>
                                      ) : null}
                                    </div>
                                    {annotation ? (
                                      <div
                                        style={{
                                          marginTop: "6px",
                                          border: annotationStyle.border,
                                          borderRadius: "8px",
                                          background: annotationStyle.background,
                                          padding: "7px 8px",
                                        }}
                                      >
                                        <div
                                          style={{
                                            display: "flex",
                                            gap: "6px",
                                            flexWrap: "wrap",
                                            alignItems: "center",
                                            color: annotationStyle.color,
                                            fontSize: "11px",
                                            fontWeight: 800,
                                          }}
                                        >
                                          <span>Relationship Annotation</span>
                                          <span>{formatCompactLabel(annotation.relation_type)}</span>
                                          <span>{formatCompactLabel(annotation.support_posture)}</span>
                                          {relationshipReviewRequired(annotation) ? <span>Review Required</span> : null}
                                        </div>
                                        <div style={{ color: "var(--app-text-muted)", fontSize: "11px", lineHeight: 1.45, marginTop: "4px" }}>
                                          Grounding: {formatCompactLabel(annotation.grounding_source)}
                                          {" | "}
                                          Derivation: {formatCompactLabel(annotation.derivation_mechanism)}
                                          {" | "}
                                          Classified by: {formatCompactLabel(annotation.classified_by)}
                                        </div>
                                        {Array.isArray(annotation.review_reason_codes) && annotation.review_reason_codes.length > 0 ? (
                                          <div style={{ color: "var(--app-text-subtle)", fontSize: "11px", lineHeight: 1.45, marginTop: "4px" }}>
                                            Reasons: {annotation.review_reason_codes.map(formatCompactLabel).join(", ")}
                                          </div>
                                        ) : null}
                                        {annotation.rationale ? (
                                          <div style={{ color: "var(--app-text-strong)", fontSize: "11px", lineHeight: 1.45, marginTop: "4px" }}>
                                            {annotation.rationale}
                                          </div>
                                        ) : null}
                                        {Array.isArray(annotation.source_refs) && annotation.source_refs.length > 0 ? (
                                          <div style={{ color: "var(--app-text-subtle)", fontSize: "11px", lineHeight: 1.45, marginTop: "4px" }}>
                                            Source refs: {annotation.source_refs.slice(0, 3).join(", ")}
                                          </div>
                                        ) : null}
                                      </div>
                                    ) : null}
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                        ) : null}
                        <div style={{ marginTop: "10px" }}>
                          <button
                            type="button"
                            disabled={feedbackDraft.submitted}
                            onClick={() =>
                              updateClaimFeedbackDraft(feedbackKey, {
                                open: !feedbackDraft.open,
                                error: "",
                                message: feedbackDraft.message,
                              })
                            }
                            style={{
                              padding: "6px 10px",
                              borderRadius: "8px",
                              border: feedbackDraft.submitted
                                ? "1px solid var(--app-success-border)"
                                : "1px solid var(--app-secondary-action-border)",
                              background: feedbackDraft.submitted
                                ? "var(--app-success-bg)"
                                : "var(--app-secondary-action-bg)",
                              color: feedbackDraft.submitted
                                ? "var(--app-success-fg)"
                                : "var(--app-secondary-action-fg)",
                              fontSize: "12px",
                              fontWeight: 800,
                              cursor: feedbackDraft.submitted ? "default" : "pointer",
                              opacity: feedbackDraft.submitted ? 0.92 : 1,
                            }}
                          >
                            {feedbackDraft.submitted ? "Feedback recorded" : "Not right"}
                          </button>
                          {feedbackDraft.open && !feedbackDraft.submitted ? (
                            <form
                              onSubmit={(event) => {
                                event.preventDefault();
                                void handleSubmitClaimFeedback(claim, index);
                              }}
                              style={{
                                marginTop: "8px",
                                display: "grid",
                                gap: "8px",
                                gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
                                alignItems: "start",
                              }}
                            >
                              <label style={{ display: "grid", gap: "4px", fontSize: "12px", color: "var(--app-text-muted)" }}>
                                Reason
                                <select
                                  value={feedbackDraft.reasonSlot}
                                  onChange={(event) =>
                                    updateClaimFeedbackDraft(feedbackKey, {
                                      reasonSlot: event.target.value as FeedbackReasonSlot,
                                      submitted: false,
                                      message: "",
                                      error: "",
                                    })
                                  }
                                  disabled={feedbackDraft.submitting}
                                  style={{
                                    minHeight: "34px",
                                    borderRadius: "8px",
                                    border: "1px solid var(--app-input-border)",
                                    padding: "6px 8px",
                                    background: "var(--app-input-bg)",
                                    color: "var(--app-input-fg)",
                                    fontSize: "13px",
                                  }}
                                >
                                  {FEEDBACK_REASON_OPTIONS.map((option) => (
                                    <option key={option.value} value={option.value}>
                                      {option.label}
                                    </option>
                                  ))}
                                </select>
                              </label>
                              <label style={{ display: "grid", gap: "4px", fontSize: "12px", color: "var(--app-text-muted)" }}>
                                Note
                                <textarea
                                  value={feedbackDraft.note}
                                  onChange={(event) =>
                                    updateClaimFeedbackDraft(feedbackKey, {
                                      note: event.target.value,
                                      submitted: false,
                                      message: "",
                                      error: "",
                                    })
                                  }
                                  disabled={feedbackDraft.submitting}
                                  rows={2}
                                  placeholder="Where does this depart from your judgment?"
                                  style={{
                                    minHeight: "52px",
                                    resize: "vertical",
                                    borderRadius: "8px",
                                    border: "1px solid var(--app-input-border)",
                                    padding: "7px 8px",
                                    color: "var(--app-input-fg)",
                                    background: "var(--app-input-bg)",
                                    fontSize: "13px",
                                    lineHeight: 1.4,
                                  }}
                                />
                              </label>
                              <button
                                type="submit"
                                disabled={feedbackDraft.submitting}
                                style={{
                                  ...detailActionPrimaryStyle,
                                  minHeight: "34px",
                                  marginTop: "20px",
                                  padding: "7px 12px",
                                  ...(feedbackDraft.submitting ? detailActionDisabledStyle : {}),
                                  fontSize: "12px",
                                  fontWeight: 800,
                                  cursor: feedbackDraft.submitting ? "not-allowed" : "pointer",
                                  opacity: feedbackDraft.submitting ? 0.7 : 1,
                                }}
                              >
                                {feedbackDraft.submitting ? "Saving" : "Record"}
                              </button>
                              {(feedbackDraft.message || feedbackDraft.error) ? (
                                <div
                                  style={{
                                    gridColumn: "1 / -1",
                                    color: feedbackDraft.error ? "var(--app-danger-fg)" : "var(--app-success-fg)",
                                    fontSize: "12px",
                                    lineHeight: 1.45,
                                  }}
                                >
                                  {feedbackDraft.error || feedbackDraft.message}
                                </div>
                              ) : null}
                            </form>
                          ) : null}
                        </div>
                        </div>
                      );
                    })}
                  </div>
                </details>
              )}
            </div>
          )}

          <InsightSection
            label="Summary"
            value={stripUncertainPrefix(displaySummary)}
            fallback="No summary available yet."
          />

          {isManualInsight && manualImageFiles.length > 0 && (
            <div
              style={{
                border: "1px solid var(--app-surface-border)",
                borderRadius: "8px",
                padding: "18px",
                background: "var(--app-surface-bg)",
                marginBottom: "16px",
                boxShadow: "var(--app-surface-shadow)",
              }}
            >
              <div
                style={{
                  fontSize: "12px",
                  fontWeight: 700,
                  color: "var(--app-text-subtle)",
                  marginBottom: "8px",
                  textTransform: "uppercase",
                  letterSpacing: 0,
                }}
              >
                Image Preview
              </div>

              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
                  gap: "16px",
                }}
              >
                {manualImageFiles.map((file, index) => (
                  <div
                    key={file.stored_filename || `${file.original_filename}-${index}`}
                    style={{
                      border: "1px solid var(--app-surface-border)",
                      borderRadius: "8px",
                      padding: "10px",
                      background: "var(--app-surface-muted-bg)",
                    }}
                  >
                    <button
                      onClick={() => setManualLightboxIndex(index)}
                      style={{
                        border: "none",
                        background: "transparent",
                        padding: 0,
                        cursor: "pointer",
                        width: "100%",
                        textAlign: "left",
                      }}
                    >
                      {file.stored_filename && manualFileUrls[file.stored_filename] ? (
                        <Image
                          src={manualFileUrls[file.stored_filename]}
                          alt={file.original_filename || "Manual image"}
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
                      {file.original_filename || "Untitled image"}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {isManualInsight && manualTextLikeFiles.length > 0 && (
            <div
              style={{
                border: "1px solid var(--app-surface-border)",
                borderRadius: "8px",
                padding: "18px",
                background: "var(--app-surface-bg)",
                marginBottom: "16px",
                boxShadow: "var(--app-surface-shadow)",
              }}
            >
              <div
                style={{
                  fontSize: "12px",
                  fontWeight: 700,
                  color: "var(--app-text-subtle)",
                  marginBottom: "8px",
                  textTransform: "uppercase",
                  letterSpacing: 0,
                }}
              >
                Text / PDF Preview
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
                {manualTextLikeFiles.map((file) => {
                  const fileKey = file.stored_filename || file.original_filename || "manual-file";
                  const isExpanded = Boolean(expandedManualTextPreviewIds[fileKey]);
                  const previewText = getManualPreviewText(file);
                  const pdfUrl =
                    file.file_kind === "pdf" && file.stored_filename
                      ? manualFileUrls[file.stored_filename] || ""
                      : "";
                  const canExpandPreview = Boolean(previewText) && file.file_kind !== "pdf";

                  return (
                    <div
                      key={fileKey}
                      style={{
                        border: "1px solid var(--app-surface-border)",
                        borderRadius: "8px",
                        padding: "14px",
                        background: "var(--app-surface-muted-bg)",
                      }}
                    >
                      <div style={{ fontSize: "13px", fontWeight: 600, marginBottom: "8px", color: "var(--app-text-strong)" }}>
                        {file.original_filename || "Untitled file"}
                      </div>
                      {canExpandPreview || file.file_kind === "pdf" ? (
                        <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", marginBottom: "10px" }}>
                          {canExpandPreview ? (
                            <button
                              type="button"
                              onClick={() => toggleManualTextPreview(fileKey)}
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
                              {isExpanded ? "Collapse preview" : "Expand preview"}
                            </button>
                          ) : null}
                          {file.file_kind === "pdf" ? (
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
                          ) : null}
                        </div>
                      ) : null}
                      {file.file_kind === "pdf" ? null : previewText ? (
                        isExpanded ? (
                          <div style={{ fontSize: "14px", color: "var(--app-text-muted)", lineHeight: 1.7, whiteSpace: "pre-wrap" }}>
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

          <InsightSection
            label="Why It Matters"
              value={stripUncertainPrefix(insight?.why_it_matters || insight?.insight || "")}
            fallback={getInsightFallbackText(insight, "why_it_matters")}
          />

          <InsightSection
            label="Relevance to Projects"
              value={stripUncertainPrefix(insight?.relevance_to_projects || "")}
            fallback={getInsightFallbackText(insight, "relevance_to_projects")}
          />

          <InsightSection
            label="Relevance to Career"
              value={stripUncertainPrefix(insight?.relevance_to_career || "")}
            fallback={getInsightFallbackText(insight, "relevance_to_career")}
          />

          <InsightSection
            label="Strategic Takeaway"
              value={stripUncertainPrefix(insight?.synthesized_insight || insight?.strategy || "")}
            fallback={getInsightFallbackText(insight, "synthesized_insight")}
          />

          <div
            style={{
              border: "1px solid var(--app-surface-border)",
              borderRadius: "8px",
              padding: "18px",
              background: "var(--app-surface-bg)",
              marginBottom: "16px",
              boxShadow: "var(--app-surface-shadow)",
            }}
          >
            <div
              style={{
                fontSize: "12px",
                fontWeight: 700,
                color: "var(--app-text-subtle)",
                marginBottom: "8px",
                textTransform: "uppercase",
                letterSpacing: 0,
              }}
            >
              Related Deep Reflections
            </div>

            {relatedReflectionTopics.length > 0 && (
              <div
                style={{
                  fontSize: "13px",
                  color: "var(--app-text-muted)",
                  marginBottom: "14px",
                  lineHeight: 1.6,
                }}
              >
                Matching topics: {relatedReflectionTopics.join(", ")}
              </div>
            )}

            {relatedReflectionsLoading ? (
              <div style={{ fontSize: "14px", color: "var(--app-text-subtle)" }}>
                Loading related deep reflections...
              </div>
            ) : relatedReflections.length === 0 ? (
              <div style={{ fontSize: "14px", color: "var(--app-text-subtle)" }}>
                No closely related deep reflections found for this signal yet.
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
                        alignItems: "flex-start",
                        flexWrap: "wrap",
                        marginBottom: "8px",
                      }}
                    >
                      <Link
                        href={`/reflections/detail?id=${encodeURIComponent(item.id || "")}`}
                        style={{
                          fontSize: "16px",
                          fontWeight: 500,
                          color: "var(--app-info-fg)",
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
                            background: "var(--app-chip-bg)",
                            color: "var(--app-chip-fg)",
                            border: "1px solid var(--app-chip-border)",
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
                      <span>Updated: {formatDateTime(item.timestamp)}</span>
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

        <div>
          <div
            style={{
              position: "sticky",
              top: "148px",
              display: "flex",
              flexDirection: "column",
              gap: "16px",
            }}
          >
            <div
              style={{
                border: "1px solid var(--app-surface-border)",
                borderRadius: "8px",
                padding: "20px",
                background: "var(--app-surface-bg)",
              }}
            >
              <div style={discussionPanelHeaderStyle}>
                <div
                  style={{
                    fontSize: "12px",
                    color: "var(--app-text-subtle)",
                    textTransform: "uppercase",
                    letterSpacing: 0,
                    fontWeight: 700,
                  }}
                >
                  AI Discussion
                </div>
                <button
                  type="button"
                  onClick={() => setDiscussionExpanded((current) => !current)}
                  title={discussionExpanded ? "Collapse discussion" : "Expand discussion"}
                  aria-label={discussionExpanded ? "Collapse discussion" : "Expand discussion"}
                  style={discussionExpandButtonStyle}
                >
                  {discussionExpanded ? <Minimize2 size={14} strokeWidth={2.4} /> : <Maximize2 size={14} strokeWidth={2.4} />}
                  {discussionExpanded ? "Collapse" : "Expand"}
                </button>
              </div>
              <div style={{ fontSize: "13px", color: "var(--app-text-muted)", lineHeight: 1.5, marginBottom: "12px" }}>
                Discussion may challenge assumptions. It does not verify external facts or change action eligibility.
              </div>
              <div style={{ fontSize: "12px", color: "var(--app-text-subtle)", lineHeight: 1.5, marginBottom: "12px" }}>
                Claude uses recent discussion context for continuity; discussion history is not verified evidence.
              </div>

              <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", marginBottom: "14px" }}>
                {(["Claude", "ChatGPT", "Perplexity"] as UiTab[]).map((tab) => {
                  const active = activeTab === tab;
                  return (
                    <button
                      key={tab}
                      onClick={() => setActiveTab(tab)}
                      style={{
                        ...(active ? detailPillActiveStyle : detailPillStyle),
                        cursor: "pointer",
                      }}
                    >
                      {tab}
                    </button>
                  );
                })}
              </div>

              <details style={thinkingStyleDisclosureStyle}>
                <summary style={thinkingStyleSummaryStyle}>
                  <span>Thinking Style: Andy Default</span>
                  <span style={thinkingStyleModeStyle}>Claude discussion</span>
                </summary>
                <div style={thinkingStyleGridStyle}>
                  <div style={thinkingStyleItemStyle}>
                    <strong>Evidence grading</strong>
                    <span>Always on. Separate verified facts from inference and say when the answer is uncertain.</span>
                  </div>
                  <div style={thinkingStyleItemStyle}>
                    <strong>Tension axis</strong>
                    <span>Used only when a tradeoff or vague good/bad judgment needs sharper framing.</span>
                  </div>
                  <div style={thinkingStyleItemStyle}>
                    <strong>Valence check</strong>
                    <span>Used when a metric or fact looks positive on the surface but may flip under scrutiny.</span>
                  </div>
                  <div style={thinkingStyleItemStyle}>
                    <strong>Negative ROI gate</strong>
                    <span>Used for build, optimize, or upgrade decisions: can do is not the same as should do now.</span>
                  </div>
                </div>
                <div style={thinkingStyleExampleStyle}>
                  Without this style: technically possible. With it: technically possible, but first check whether it is worth doing in this context.
                </div>
              </details>

              <ChatWindow
                messages={currentMessages}
                loading={currentLoading}
                expectedProvider={currentExpectedProvider}
                expanded={discussionExpanded}
              />

              <textarea
                value={currentInput}
                onChange={(e) => {
                  const value = e.target.value;
                  if (activeTab === "Claude") setClaudeInput(value);
                  if (activeTab === "ChatGPT") setChatgptInput(value);
                  if (activeTab === "Perplexity") setPerplexityInput(value);
                }}
                placeholder={`Ask ${activeTab} about this signal...`}
                style={{
                  width: "100%",
                  minHeight: "90px",
                  resize: "vertical",
                  borderRadius: "8px",
                  border: "1px solid var(--app-input-border)",
                  background: "var(--app-input-bg)",
                  color: "var(--app-input-fg)",
                  padding: "12px",
                  fontFamily: "Arial",
                  fontSize: "14px",
                  lineHeight: 1.6,
                  boxSizing: "border-box",
                  marginTop: "14px",
                }}
              />

              <div
                style={{
                  display: "flex",
                  gap: "10px",
                  flexWrap: "wrap",
                  marginTop: "12px",
                }}
              >
                <button
                  onClick={() => {
                    if (activeTab === "Claude") sendToModel("claude");
                    if (activeTab === "ChatGPT") sendToModel("chatgpt");
                    if (activeTab === "Perplexity") sendToModel("perplexity");
                  }}
                  disabled={currentLoading}
                  style={{
                    ...detailActionPrimaryStyle,
                    ...(currentLoading ? detailActionDisabledStyle : {}),
                    cursor: currentLoading ? "not-allowed" : "pointer",
                  }}
                >
                  {currentLoading ? "Sending..." : `Send to ${activeTab}`}
                </button>

                <button
                  onClick={() => clearChat(activeTab)}
                  style={detailActionSecondaryStyle}
                >
                  Clear Chat
                </button>
              </div>
            </div>

            <div
              style={{
                border: "1px solid var(--app-surface-border)",
                borderRadius: "8px",
                padding: "20px",
                background: "var(--app-surface-bg)",
              }}
            >
              <div
                style={{
                  fontSize: "12px",
                  color: "var(--app-text-subtle)",
                  marginBottom: "8px",
                  textTransform: "uppercase",
                  letterSpacing: 0,
                  fontWeight: 700,
                }}
              >
                Signal Completion Notes
              </div>

              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  gap: "12px",
                  flexWrap: "wrap",
                  marginBottom: "12px",
                }}
              >
                <h2 style={{ margin: 0, fontSize: "20px" }}>
                  Completion Note
                </h2>
                {signalCompleted ? (
                  <div
                    style={{
                      padding: "6px 10px",
                      borderRadius: "999px",
                      border: "1px solid var(--app-success-border)",
                      background: "var(--app-success-bg)",
                      color: "var(--app-success-fg)",
                      fontSize: "12px",
                      fontWeight: 700,
                      whiteSpace: "nowrap",
                    }}
                  >
                    {hasWorkspaceRecord ? "Completed in Workspace" : "Completed"}
                  </div>
                ) : null}
              </div>

              <div
                style={{
                  marginBottom: "12px",
                  border: finalTakeawayArtifactLocked
                    ? "1px solid var(--app-success-border)"
                    : "1px solid var(--app-surface-border)",
                  borderRadius: "8px",
                  background: finalTakeawayArtifactLocked
                    ? "var(--app-success-bg)"
                    : "var(--app-ghost-action-bg)",
                  padding: "10px 12px",
                  color: finalTakeawayArtifactLocked
                    ? "var(--app-success-fg)"
                    : "var(--app-text-muted)",
                  fontSize: "13px",
                  lineHeight: 1.6,
                }}
              >
                {finalTakeawayArtifactLocked
                  ? "Completion Note is locked because a Final Takeaway artifact is already confirmed. Continue through Send Final Takeaway to Review; do not also Complete Signal into Workspace."
                  : "Completion Note is a Final Takeaway draft. Confirming a Final Takeaway requires an immutable Review Bundle snapshot and does not send anything to Project Review in this step."}
              </div>

              {isManualInsight ? (
                <div
                  style={{
                    ...manualCompletionGuideStyle,
                    ...(hasWorkspaceRecord
                      ? manualCompletionGuideDoneStyle
                      : completionRequiresVerificationReview
                        ? manualCompletionGuideWarningStyle
                        : {}),
                  }}
                >
                  <span style={manualSourceContextLabelStyle}>Manual Completion Route</span>
                  <strong>
                    {hasWorkspaceRecord
                      ? "Workspace record is already saved"
                      : completionRequiresVerificationReview
                        ? "Review claim checks before completion"
                        : hasCompletionNote
                          ? "Ready to complete when reviewed"
                          : "Draft or write a completion note"}
                  </strong>
                  <span>
                    {hasWorkspaceRecord
                      ? "Use the Workspace record for durable follow-up."
                      : completionRequiresVerificationReview
                        ? "Completion is allowed only after confirming the verification warning below."
                        : "Complete Signal creates the durable Workspace artifact for this manual-derived intelligence."}
                  </span>
                </div>
              ) : null}

              <textarea
                value={reflection}
                onChange={(e) => {
                  setReflection(e.target.value);
                  setReflectionPolishPairId("");
                }}
                placeholder="Your signal completion note will appear here..."
                readOnly={completionNoteLocked}
                style={{
                  width: "100%",
                  minHeight: "190px",
                  resize: "vertical",
                  borderRadius: "8px",
                  border: "1px solid var(--app-input-border)",
                  padding: "12px",
                  fontFamily: "Arial",
                  fontSize: "14px",
                  lineHeight: 1.6,
                  boxSizing: "border-box",
                  background: completionNoteLocked ? "var(--app-ghost-action-bg)" : "var(--app-input-bg)",
                  color: "var(--app-input-fg)",
                  cursor: completionNoteLocked ? "not-allowed" : "text",
                }}
              />

              {draftError && (
                <div style={{ marginTop: "10px", color: "var(--app-danger-fg)", fontSize: "13px" }}>
                  {draftError}
                </div>
              )}

              {saveMessage && (
                <div
                  style={{
                    marginTop: "10px",
                    color: saveMessageIsError ? "var(--app-danger-fg)" : "var(--app-success-fg)",
                    fontSize: "13px",
                  }}
                >
                  {saveMessage}
                </div>
              )}

              {reflectionPolishPairId ? (
                <div
                  style={{
                    marginTop: "8px",
                    display: "flex",
                    flexWrap: "wrap",
                    alignItems: "center",
                    gap: "8px",
                    color: "var(--app-text-muted)",
                    fontSize: "13px",
                  }}
                >
                  <span>Human review pair: {reflectionPolishPairId}</span>
                  <Link href="/admin/reflection-polish" style={inlineReviewLinkStyle}>
                    Open Reflection Polish Review
                  </Link>
                </div>
              ) : null}

              {completionRequiresVerificationReview && !signalCompleted && !finalTakeawayArtifactLocked && (
                <div
                  style={{
                    marginTop: "12px",
                    border: "1px solid var(--app-warning-border)",
                    background: "var(--app-warning-bg)",
                    color: "var(--app-warning-fg)",
                    borderRadius: "8px",
                    padding: "10px 12px",
                    fontSize: "13px",
                    lineHeight: 1.6,
                  }}
                >
                  <div>
                    {completionGateMessage} Review priority: {reviewPriority.label}.
                  </div>
                  <label
                    style={{
                      display: "flex",
                      alignItems: "flex-start",
                      gap: "8px",
                      marginTop: "8px",
                      fontWeight: 700,
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={completionReviewConfirmed}
                      disabled={isRejectedLocked}
                      onChange={(event) => setCompletionReviewConfirmed(event.target.checked)}
                      style={{ marginTop: "3px" }}
                    />
                    <span>I reviewed the claim checks and still want to complete this signal into Workspace.</span>
                  </label>
                </div>
              )}

              <div
                style={{
                  display: "flex",
                  gap: "10px",
                  flexWrap: "wrap",
                  marginTop: "14px",
                }}
              >
                <button
                  onClick={() => generateReflectionDraft(true)}
                  disabled={isGeneratingDraft || completionNoteLocked}
                  title={completionNoteDisabledReason || undefined}
                  style={{
                    ...detailActionSecondaryStyle,
                    ...(isGeneratingDraft || completionNoteLocked ? detailActionDisabledStyle : {}),
                    cursor: isGeneratingDraft || completionNoteLocked ? "not-allowed" : "pointer",
                    opacity: completionNoteLocked ? 0.65 : 1,
                  }}
                >
                  {isGeneratingDraft ? "Generating..." : "Generate Draft"}
                </button>

                <button
                  onClick={polishReflection}
                  disabled={isPolishing || completionNoteLocked}
                  title={completionNoteDisabledReason || undefined}
                  style={{
                    ...detailActionSecondaryStyle,
                    ...(isPolishing || completionNoteLocked ? detailActionDisabledStyle : {}),
                    cursor: isPolishing || completionNoteLocked ? "not-allowed" : "pointer",
                    opacity: completionNoteLocked ? 0.65 : 1,
                  }}
                >
                  {isPolishing ? "Polishing..." : "AI Polish"}
                </button>

                <button
                  onClick={handleSaveReflection}
                  disabled={isSaving || completionNoteLocked}
                  title={completionNoteDisabledReason || undefined}
                  style={{
                    ...detailActionPrimaryStyle,
                    ...(isSaving || completionNoteLocked ? detailActionDisabledStyle : {}),
                    cursor: isSaving || completionNoteLocked ? "not-allowed" : "pointer",
                    opacity: completionNoteLocked ? 0.65 : 1,
                  }}
                >
                  {isSaving ? "Saving..." : "Save Note"}
                </button>

                {finalTakeawayArtifactLocked ? (
                  <div
                    style={{
                      ...detailActionDisabledStyle,
                      borderRadius: "8px",
                      padding: "10px 12px",
                      fontSize: "13px",
                      fontWeight: 700,
                    }}
                    title={completionNoteDisabledReason}
                  >
                    Completion Note locked by confirmed Final Takeaway
                  </div>
                ) : !signalCompleted ? (
                  <button
                    onClick={handleCompleteSignal}
                    disabled={
                      isRejectedLocked ||
                      isCompleting ||
                      isGeneratingDraft ||
                      !hasCompletionNote ||
                      (completionRequiresVerificationReview && !completionReviewConfirmed)
                    }
                    style={{
                      ...detailActionPrimaryStyle,
                      border: completionRequiresVerificationReview
                        ? "1px solid var(--app-warning-border)"
                        : "1px solid var(--app-success-border)",
                      background:
                        isCompleting ||
                        isRejectedLocked ||
                        isGeneratingDraft ||
                        !hasCompletionNote ||
                        (completionRequiresVerificationReview && !completionReviewConfirmed)
                          ? "var(--app-ghost-action-bg)"
                          : completionRequiresVerificationReview
                            ? "var(--app-warning-bg)"
                            : "var(--app-success-bg)",
                      color:
                        isCompleting ||
                        isRejectedLocked ||
                        isGeneratingDraft ||
                        !hasCompletionNote ||
                        (completionRequiresVerificationReview && !completionReviewConfirmed)
                          ? "var(--app-text-subtle)"
                          : completionRequiresVerificationReview
                            ? "var(--app-warning-fg)"
                            : "var(--app-success-fg)",
                      cursor:
                        isCompleting ||
                        isRejectedLocked ||
                        isGeneratingDraft ||
                        !hasCompletionNote ||
                        (completionRequiresVerificationReview && !completionReviewConfirmed)
                          ? "not-allowed"
                          : "pointer",
                    }}
                    title={
                      !hasCompletionNote
                        ? "Write or generate a completion note first."
                        : isRejectedLocked
                          ? actionDisabledReason
                          : isGeneratingDraft
                          ? "Wait for draft generation to finish."
                          : undefined
                    }
                  >
                    {isCompleting ? "Completing..." : "Complete Signal"}
                  </button>
                ) : hasWorkspaceRecord ? (
                  <Link href={workspaceRecordHref} style={detailActionSecondaryStyle}>
                    Open Workspace Record
                  </Link>
                ) : null}
              </div>

              <div
                style={{
                  marginTop: "18px",
                  border: "1px solid var(--app-surface-border)",
                  borderRadius: "8px",
                  background: "var(--app-panel-bg)",
                  padding: "14px",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    gap: "12px",
                    flexWrap: "wrap",
                    alignItems: "flex-start",
                    marginBottom: "10px",
                  }}
                >
                  <div>
                    <div style={{ ...manualSourceContextLabelStyle, marginBottom: "4px" }}>
                      Final Takeaway Confirmation
                    </div>
                    <strong style={{ display: "block", color: "var(--app-text)", fontSize: "15px" }}>
                      Review Bundle snapshot to Andy Confirm
                    </strong>
                    <div style={{ color: "var(--app-text-muted)", fontSize: "13px", marginTop: "4px", lineHeight: 1.5 }}>
                      Confirming creates durable Final Takeaway artifacts only. After confirmation, send it to Project Review through the confirmed_final_takeaway provider.
                    </div>
                  </div>
                  {confirmedFinalTakeaway?.final_takeaway_id ? (
                    <span
                      style={{
                        border: "1px solid var(--app-success-border)",
                        background: "var(--app-success-bg)",
                        color: "var(--app-success-fg)",
                        borderRadius: "999px",
                        padding: "5px 9px",
                        fontSize: "12px",
                        fontWeight: 700,
                      }}
                    >
                      Confirmed
                    </span>
                  ) : reviewBundleSnapshot?.snapshot_id ? (
                    <span
                      style={{
                        border: "1px solid var(--app-info-border)",
                        background: "var(--app-info-bg)",
                        color: "var(--app-info-fg)",
                        borderRadius: "999px",
                        padding: "5px 9px",
                        fontSize: "12px",
                        fontWeight: 700,
                      }}
                    >
                      Snapshot Ready
                    </span>
                  ) : null}
                </div>

                <div style={{ display: "grid", gap: "10px" }}>
                  <div
                    style={{
                      display: "grid",
                      gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
                      gap: "8px",
                      color: "var(--app-text-muted)",
                      fontSize: "12px",
                    }}
                  >
                    <div>
                      <strong style={{ color: hasCompletionNote ? "var(--app-success-fg)" : "var(--app-warning-fg)" }}>
                        Completion note
                      </strong>
                      <div>{hasCompletionNote ? "Draft available" : "Missing"}</div>
                    </div>
                    <div>
                      <strong style={{ color: hasGeneratedInsightContent ? "var(--app-success-fg)" : "var(--app-warning-fg)" }}>
                        Structured insight
                      </strong>
                      <div>{hasGeneratedInsightContent ? "Available" : "Missing"}</div>
                    </div>
                    <div>
                      <strong style={{ color: deepProjectMatchAnalysis ? "var(--app-success-fg)" : "var(--app-warning-fg)" }}>
                        Deep match analysis
                      </strong>
                      <div>{deepProjectMatchAnalysis ? "Attached" : "Not generated"}</div>
                    </div>
                  </div>

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
                        <strong style={{ color: "var(--app-text)", fontSize: "13px" }}>External Synthesis Source</strong>
                        <div style={{ color: "var(--app-text-muted)", fontSize: "12px", lineHeight: 1.5, marginTop: "3px" }}>
                          Optional long-form review context from Codex, Claude, ChatGPT, or another tool. It feeds the Review Bundle as context, not verified evidence.
                        </div>
                      </div>
                      {hasSavedExternalSynthesisSource || externalSynthesisArchivedInBundleOnly ? (
                        <span
                          style={{
                            border: hasSavedExternalSynthesisSource
                              ? "1px solid var(--app-info-border)"
                              : "1px solid var(--app-warning-border)",
                            background: hasSavedExternalSynthesisSource
                              ? "var(--app-info-bg)"
                              : "var(--app-warning-bg)",
                            color: hasSavedExternalSynthesisSource
                              ? "var(--app-info-fg)"
                              : "var(--app-warning-fg)",
                            borderRadius: "999px",
                            padding: "5px 9px",
                            fontSize: "12px",
                            fontWeight: 700,
                            height: "fit-content",
                          }}
                        >
                          {hasSavedExternalSynthesisSource ? "Source saved" : "Bundled in snapshot"}
                        </span>
                      ) : null}
                    </div>

                    {externalSynthesisArchivedInBundleOnly ? (
                      <div
                        style={{
                          border: "1px solid var(--app-warning-border)",
                          background: "var(--app-warning-bg)",
                          color: "var(--app-warning-fg)",
                          borderRadius: "8px",
                          padding: "10px",
                          fontSize: "12px",
                          lineHeight: 1.55,
                        }}
                      >
                        No standalone External Synthesis Source was saved for this confirmed artifact. The Review Bundle
                        snapshot is restored below and remains the immutable source for this Final Takeaway.
                      </div>
                    ) : (
                      <textarea
                        value={externalSynthesisText}
                        onChange={(event) => {
                          setExternalSynthesisText(event.target.value);
                          setExternalSynthesisSource(null);
                        }}
                        placeholder="Paste external synthesis here, or upload .md / .txt / .html below..."
                        readOnly={isRejectedLocked || Boolean(confirmedFinalTakeaway)}
                        style={{
                          width: "100%",
                          minHeight: "95px",
                          resize: "vertical",
                          borderRadius: "8px",
                          border: "1px solid var(--app-input-border)",
                          padding: "10px",
                          fontFamily: "Arial",
                          fontSize: "13px",
                          lineHeight: 1.55,
                          boxSizing: "border-box",
                          background:
                            isRejectedLocked || Boolean(confirmedFinalTakeaway)
                              ? "var(--app-ghost-action-bg)"
                              : "var(--app-input-bg)",
                          color: "var(--app-input-fg)",
                        }}
                      />
                    )}

                    {!externalSynthesisArchivedInBundleOnly && externalSynthesisContentWarning ? (
                      <div
                        style={{
                          border: "1px solid var(--app-warning-border)",
                          background: "var(--app-warning-bg)",
                          color: "var(--app-warning-fg)",
                          borderRadius: "8px",
                          padding: "9px 10px",
                          fontSize: "12px",
                          lineHeight: 1.5,
                        }}
                      >
                        {externalSynthesisContentWarning}
                      </div>
                    ) : null}

                    {!externalSynthesisArchivedInBundleOnly ? (
                      <div style={{ display: "flex", gap: "10px", flexWrap: "wrap", alignItems: "center" }}>
                      <label
                        style={{
                          ...detailActionSecondaryStyle,
                          ...(isRejectedLocked || Boolean(confirmedFinalTakeaway) ? detailActionDisabledStyle : {}),
                          cursor: isRejectedLocked || Boolean(confirmedFinalTakeaway) ? "not-allowed" : "pointer",
                        }}
                      >
                        Upload .md/.txt/.html
                        <input
                          type="file"
                          accept=".md,.markdown,.txt,.html,.htm,text/markdown,text/plain,text/html"
                          onChange={handleExternalSynthesisFileChange}
                          disabled={isRejectedLocked || Boolean(confirmedFinalTakeaway)}
                          style={{ display: "none" }}
                        />
                      </label>
                      <button
                        type="button"
                        onClick={handleSaveExternalSynthesisSource}
                        disabled={isRejectedLocked || externalSynthesisSaving || !externalSynthesisText.trim() || Boolean(confirmedFinalTakeaway)}
                        style={{
                          ...detailActionSecondaryStyle,
                          ...(isRejectedLocked || externalSynthesisSaving || !externalSynthesisText.trim() || Boolean(confirmedFinalTakeaway)
                            ? detailActionDisabledStyle
                            : {}),
                        }}
                      >
                        {externalSynthesisSaving ? "Saving..." : "Save Source"}
                      </button>
                      {externalSynthesisFileName ? (
                        <span style={{ color: "var(--app-text-muted)", fontSize: "12px" }}>{externalSynthesisFileName}</span>
                      ) : null}
                      </div>
                    ) : null}

                    {savedExternalSynthesisSource ? (
                      <div
                        style={{
                          borderTop: "1px solid var(--app-surface-border)",
                          paddingTop: "10px",
                          display: "grid",
                          gap: "10px",
                        }}
                      >
                        <div
                          style={{
                            display: "grid",
                            gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))",
                            gap: "8px",
                          }}
                        >
                          {[
                            { label: "Source ID", value: savedExternalSynthesisSource.external_synthesis_source_id },
                            { label: "Input", value: savedExternalSynthesisSource.source_file || "paste" },
                            {
                              label: "Hash",
                              value: savedExternalSynthesisSource.normalized_content_hash
                                ? savedExternalSynthesisSource.normalized_content_hash.slice(0, 16)
                                : "unknown",
                            },
                            {
                              label: "Boundary",
                              value: savedExternalSynthesisSource.evidence_boundary || "review_context_not_verified_evidence",
                            },
                            {
                              label: "Quality",
                              value:
                                savedExternalSynthesisQuality.status === "warning"
                                  ? "warning recorded"
                                  : savedExternalSynthesisQuality.status === "clean"
                                    ? "clean"
                                    : "not checked",
                            },
                          ].map((item) => (
                            <div key={item.label} style={{ minWidth: 0 }}>
                              <div
                                style={{
                                  color: "var(--app-text-muted)",
                                  fontSize: "11px",
                                  fontWeight: 700,
                                  textTransform: "uppercase",
                                }}
                              >
                                {item.label}
                              </div>
                              <div
                                style={{
                                  color: "var(--app-text)",
                                  fontSize: "12px",
                                  fontWeight: 700,
                                  lineHeight: 1.45,
                                  overflowWrap: "anywhere",
                                }}
                              >
                                {item.value}
                              </div>
                            </div>
                          ))}
                        </div>

                        {externalSynthesisPreviewText ? (
                          <div style={{ display: "grid", gap: "4px" }}>
                            <div
                              style={{
                                color: "var(--app-text-muted)",
                                fontSize: "11px",
                                fontWeight: 700,
                                textTransform: "uppercase",
                              }}
                            >
                              Saved Preview
                            </div>
                            <div
                              style={{
                                color: "var(--app-text)",
                                fontSize: "12px",
                                lineHeight: 1.55,
                                maxHeight: "78px",
                                overflow: "auto",
                                overflowWrap: "break-word",
                              }}
                            >
                              {externalSynthesisPreviewText}
                            </div>
                          </div>
                        ) : null}
                        {savedExternalSynthesisQuality.status === "warning" ? (
                          <div
                            style={{
                              border: "1px solid var(--app-warning-border)",
                              background: "var(--app-warning-bg)",
                              color: "var(--app-warning-fg)",
                              borderRadius: "8px",
                              padding: "9px 10px",
                              fontSize: "12px",
                              lineHeight: 1.5,
                            }}
                          >
                            Source quality warning recorded in review metadata: {savedExternalSynthesisQuality.summary}
                          </div>
                        ) : null}
                      </div>
                    ) : null}
                    {!externalSynthesisArchivedInBundleOnly && externalSynthesisMessage ? (
                      <div style={{ color: "var(--app-success-fg)", fontSize: "13px" }}>{externalSynthesisMessage}</div>
                    ) : null}
                    {!externalSynthesisArchivedInBundleOnly && externalSynthesisError ? (
                      <div style={{ color: "var(--app-danger-fg)", fontSize: "13px" }}>{externalSynthesisError}</div>
                    ) : null}
                  </div>

                  <textarea
                    value={reviewBundleText}
                    onChange={(event) => setReviewBundleText(event.target.value)}
                    placeholder="Generate or paste a Final Takeaway Review Bundle markdown here..."
                    readOnly={isRejectedLocked || Boolean(confirmedFinalTakeaway)}
                    style={{
                      width: "100%",
                      minHeight: "150px",
                      resize: "vertical",
                      borderRadius: "8px",
                      border: "1px solid var(--app-input-border)",
                      padding: "10px",
                      fontFamily: "Arial",
                      fontSize: "13px",
                      lineHeight: 1.55,
                      boxSizing: "border-box",
                      background:
                        isRejectedLocked || Boolean(confirmedFinalTakeaway)
                          ? "var(--app-ghost-action-bg)"
                          : "var(--app-input-bg)",
                      color: "var(--app-input-fg)",
                    }}
                  />

                  <textarea
                    value={finalTakeawayText}
                    onChange={(event) => setFinalTakeawayText(event.target.value)}
                    placeholder="Andy-confirmed Final Takeaway text..."
                    readOnly={isRejectedLocked || Boolean(confirmedFinalTakeaway)}
                    style={{
                      width: "100%",
                      minHeight: "90px",
                      resize: "vertical",
                      borderRadius: "8px",
                      border: "1px solid var(--app-input-border)",
                      padding: "10px",
                      fontFamily: "Arial",
                      fontSize: "13px",
                      lineHeight: 1.55,
                      boxSizing: "border-box",
                      background:
                        isRejectedLocked || Boolean(confirmedFinalTakeaway)
                          ? "var(--app-ghost-action-bg)"
                          : "var(--app-input-bg)",
                      color: "var(--app-input-fg)",
                    }}
                  />

                  {!confirmedFinalTakeaway?.final_takeaway_id && finalTakeawayPrerequisiteMessage ? (
                    <div
                      style={{
                        border: "1px solid var(--app-warning-border)",
                        background: "var(--app-warning-bg)",
                        color: "var(--app-warning-fg)",
                        borderRadius: "8px",
                        padding: "10px 12px",
                        fontSize: "12px",
                        lineHeight: 1.5,
                      }}
                    >
                      {finalTakeawayPrerequisiteMessage}
                    </div>
                  ) : null}

                  <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
                    <button
                      type="button"
                      onClick={handleGenerateReviewBundleDraft}
                      disabled={isRejectedLocked || Boolean(confirmedFinalTakeaway) || !finalTakeawayPrerequisitesMet}
                      title={finalTakeawayPrerequisiteMessage || undefined}
                      style={{
                        ...detailActionSecondaryStyle,
                        ...(isRejectedLocked || Boolean(confirmedFinalTakeaway) || !finalTakeawayPrerequisitesMet ? detailActionDisabledStyle : {}),
                      }}
                    >
                      Generate Bundle Draft
                    </button>
                    <button
                      type="button"
                      onClick={handleCreateReviewBundleSnapshot}
                      disabled={isRejectedLocked || reviewBundleSaving || !reviewBundleText.trim() || Boolean(confirmedFinalTakeaway) || !finalTakeawayPrerequisitesMet}
                      title={finalTakeawayPrerequisiteMessage || undefined}
                      style={{
                        ...detailActionSecondaryStyle,
                        ...(isRejectedLocked || reviewBundleSaving || !reviewBundleText.trim() || Boolean(confirmedFinalTakeaway) || !finalTakeawayPrerequisitesMet
                          ? detailActionDisabledStyle
                          : {}),
                      }}
                    >
                      {reviewBundleSaving ? "Creating..." : "Create Snapshot"}
                    </button>
                    <button
                      type="button"
                      onClick={handleConfirmFinalTakeaway}
                      disabled={
                        isRejectedLocked ||
                        finalTakeawayConfirming ||
                        !reviewBundleSnapshot?.snapshot_id ||
                        !(finalTakeawayText.trim() || reflection.trim()) ||
                        Boolean(confirmedFinalTakeaway) ||
                        !finalTakeawayPrerequisitesMet
                      }
                      title={finalTakeawayPrerequisiteMessage || undefined}
                      style={{
                        ...detailActionPrimaryStyle,
                        ...(isRejectedLocked ||
                        finalTakeawayConfirming ||
                        !reviewBundleSnapshot?.snapshot_id ||
                        !(finalTakeawayText.trim() || reflection.trim()) ||
                        Boolean(confirmedFinalTakeaway) ||
                        !finalTakeawayPrerequisitesMet
                          ? detailActionDisabledStyle
                          : {}),
                      }}
                    >
                      {finalTakeawayConfirming ? "Confirming..." : "Confirm Final Takeaway"}
                    </button>
                    {confirmedFinalTakeaway?.final_takeaway_id ? (
                      <button
                        type="button"
                        onClick={handleSendFinalTakeawayToReview}
                        disabled={!canClickFinalTakeawayHandoff}
                        style={{
                          ...detailActionPrimaryStyle,
                          ...(!canClickFinalTakeawayHandoff ? detailActionDisabledStyle : {}),
                        }}
                        title={
                          projectCandidateCreated
                            ? "This signal already has a Project Takeaway candidate."
                            : projectTakeawayManualOverrideNeeded && !projectTakeawayOverrideConfirmed
                              ? "Confirm the Final Takeaway override checkbox in Project Takeaway Handoff first."
                              : !signalCompleted
                                ? "Complete Signal before sending this Final Takeaway to Review."
                              : !hasProjectTakeawayText
                                ? "Add or generate project relevance first."
                                : undefined
                        }
                      >
                        {projectCandidateCreating
                          ? "Sending..."
                          : projectCandidateCreated
                            ? "Sent to Review"
                            : "Send Final Takeaway to Review"}
                      </button>
                    ) : null}
                  </div>

                  {confirmedFinalTakeaway?.final_takeaway_id && projectTakeawayManualOverrideNeeded ? (
                    <div
                      style={{
                        border: "1px solid var(--app-warning-border)",
                        borderRadius: "8px",
                        background: "var(--app-warning-bg)",
                        color: "var(--app-warning-fg)",
                        padding: "10px 12px",
                        fontSize: "12px",
                        lineHeight: 1.5,
                      }}
                    >
                      The ordinary Project Takeaway gate is blocked. Confirm the Final Takeaway override checkbox in Project Takeaway Handoff before sending this Final Takeaway to Review.
                    </div>
                  ) : null}

                  {reviewBundleSnapshot?.snapshot_id ? (
                    <div style={{ color: "var(--app-text-muted)", fontSize: "12px", lineHeight: 1.5 }}>
                      Snapshot: <strong>{reviewBundleSnapshot.snapshot_id}</strong>
                      {reviewBundleSnapshot.content_hash ? ` / hash ${reviewBundleSnapshot.content_hash.slice(0, 12)}` : ""}
                      {reviewBundleSnapshotQuality?.status === "warning" ? (
                        <div style={{ color: "var(--app-warning-fg)", marginTop: "4px" }}>
                          Source quality warning recorded in snapshot metadata: {reviewBundleSnapshotQuality.summary}
                        </div>
                      ) : null}
                    </div>
                  ) : null}
                  {confirmedFinalTakeaway?.final_takeaway_id ? (
                    <div style={{ color: "var(--app-success-fg)", fontSize: "12px", lineHeight: 1.5 }}>
                      Final Takeaway: <strong>{confirmedFinalTakeaway.final_takeaway_id}</strong>
                      {confirmedFinalTakeaway.confirmed_at ? ` / confirmed ${confirmedFinalTakeaway.confirmed_at}` : ""}
                    </div>
                  ) : null}
                  {reviewBundleMessage ? (
                    <div style={{ color: "var(--app-success-fg)", fontSize: "13px" }}>{reviewBundleMessage}</div>
                  ) : null}
                  {reviewBundleError ? (
                    <div style={{ color: "var(--app-danger-fg)", fontSize: "13px" }}>{reviewBundleError}</div>
                  ) : null}
                  {finalTakeawayMessage ? (
                    <div style={{ color: "var(--app-success-fg)", fontSize: "13px" }}>{finalTakeawayMessage}</div>
                  ) : null}
                  {finalTakeawayError ? (
                    <div style={{ color: "var(--app-danger-fg)", fontSize: "13px" }}>{finalTakeawayError}</div>
                  ) : null}
                </div>
              </div>

              <div
                style={{
                  marginTop: "18px",
                  paddingTop: "18px",
                  borderTop: "1px solid var(--app-surface-border)",
                }}
              >
                <div
                  style={{
                    fontSize: "12px",
                    color: "var(--app-text-subtle)",
                    marginBottom: "8px",
                    textTransform: "uppercase",
                    letterSpacing: 0,
                    fontWeight: 700,
                  }}
                >
                  GPT-5.5 Visual
                </div>

                <div style={{ fontSize: "14px", color: "var(--app-text-muted)", lineHeight: 1.6, marginBottom: "12px" }}>
                  Generate a visual by combining the signal summary, why it matters, project relevance,
                  career relevance, strategic takeaway, and your reflection.
                </div>

                <label
                  style={{
                    display: "block",
                    fontSize: "13px",
                    fontWeight: 600,
                    color: "var(--app-text-muted)",
                    marginBottom: "8px",
                  }}
                >
                  Visual style
                </label>
                <select
                  value={visualStyle}
                  onChange={(e) => setVisualStyle(e.target.value as VisualStyle)}
                  style={{
                    width: "100%",
                    borderRadius: "8px",
                    border: "1px solid var(--app-input-border)",
                    padding: "10px 12px",
                    fontSize: "14px",
                    background: "var(--app-input-bg)",
                    color: "var(--app-input-fg)",
                    marginBottom: "12px",
                  }}
                >
                  <option value="architecture">Architecture Diagram</option>
                  <option value="infographic">Strategic Infographic</option>
                  <option value="concept_map">Concept Map</option>
                  <option value="editorial">Editorial Illustration</option>
                </select>

                <label
                  style={{
                    display: "block",
                    fontSize: "13px",
                    fontWeight: 600,
                    color: "var(--app-text-muted)",
                    marginBottom: "8px",
                  }}
                >
                  Extra direction
                </label>
                <textarea
                  value={visualDirection}
                  onChange={(e) => setVisualDirection(e.target.value)}
                  readOnly={isRejectedLocked}
                  placeholder="Optional: ask for a data-flow style diagram, a cleaner executive look, specific metaphors, color direction, etc."
                  style={{
                    width: "100%",
                    minHeight: "88px",
                    resize: "vertical",
                    borderRadius: "8px",
                    border: "1px solid var(--app-input-border)",
                    padding: "12px",
                    fontFamily: "Arial",
                    fontSize: "14px",
                    lineHeight: 1.5,
                    boxSizing: "border-box",
                    background: isRejectedLocked ? "var(--app-ghost-action-bg)" : "var(--app-input-bg)",
                    color: "var(--app-input-fg)",
                    cursor: isRejectedLocked ? "not-allowed" : "text",
                  }}
                />

                {visualError ? (
                  <div style={{ marginTop: "10px", color: "var(--app-danger-fg)", fontSize: "13px" }}>
                    {visualError}
                  </div>
                ) : null}

                <div style={{ display: "flex", gap: "10px", flexWrap: "wrap", marginTop: "12px" }}>
                  <button
                    onClick={handleGenerateVisual}
                    disabled={visualGenerating || isRejectedLocked}
                    title={actionDisabledReason || undefined}
                    style={{
                      ...detailActionPrimaryStyle,
                      ...(visualGenerating || isRejectedLocked ? detailActionDisabledStyle : {}),
                      cursor: visualGenerating || isRejectedLocked ? "not-allowed" : "pointer",
                    }}
                  >
                    {visualGenerating ? "Generating Visual..." : "Generate Visual with GPT-5.5"}
                  </button>

                  {generatedVisualUrl ? (
                    <a
                      href={generatedVisualUrl}
                      target="_blank"
                      rel="noreferrer"
                      style={detailActionLinkStyle}
                    >
                      Open Image
                    </a>
                  ) : null}
                </div>

                {generatedVisualUrl ? (
                  <div
                    style={{
                      marginTop: "14px",
                      border: "1px solid var(--app-surface-border)",
                      borderRadius: "8px",
                      overflow: "hidden",
                      background: "var(--app-surface-muted-bg)",
                    }}
                  >
                    <Image
                      src={generatedVisualUrl}
                      alt="GPT-5.5-generated visual"
                      width={1600}
                      height={1000}
                      unoptimized
                      style={{ display: "block", width: "100%", height: "auto" }}
                    />
                    {generatedVisualFileName ? (
                      <div
                        style={{
                          padding: "10px 12px",
                          fontSize: "12px",
                          color: "var(--app-text-subtle)",
                          borderTop: "1px solid var(--app-surface-border)",
                          background: "var(--app-surface-bg)",
                        }}
                      >
                        {generatedVisualFileName}
                      </div>
                    ) : null}
                  </div>
                ) : null}
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>
    {currentManualLightboxFile ? (
      <div
        onClick={() => setManualLightboxIndex(null)}
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
              setManualLightboxIndex((current) =>
                current === null || current === 0 ? manualImageFiles.length - 1 : current - 1
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
            {currentManualLightboxFile.stored_filename &&
            manualFileUrls[currentManualLightboxFile.stored_filename] ? (
              <Image
                src={manualFileUrls[currentManualLightboxFile.stored_filename]}
                alt={currentManualLightboxFile.original_filename || "Manual image"}
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
            ) : null}
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
              {currentManualLightboxFile.original_filename || "Untitled image"}
            </div>
          </div>
          <button
            onClick={() =>
              setManualLightboxIndex((current) =>
                current === null || current === manualImageFiles.length - 1 ? 0 : current + 1
              )
            }
            style={lightboxButtonStyle}
          >
            Next
          </button>
          <button
            onClick={() => setManualLightboxIndex(null)}
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
    ) : null}
    </>
  );
}

const lightboxButtonStyle: React.CSSProperties = {
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

const detailPageShellStyle = {
  paddingTop: "8px",
  fontFamily: "Arial",
  maxWidth: "1320px",
  margin: "0 auto",
  paddingLeft: "24px",
  paddingRight: "24px",
  paddingBottom: "40px",
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
  "--app-dock-bg": "rgba(15, 23, 42, 0.92)",
  "--app-dock-border": "rgba(148, 163, 184, 0.24)",
  "--app-dock-shadow": "0 12px 28px rgba(0, 0, 0, 0.22)",
} as React.CSSProperties;

const detailToolbarStyle: React.CSSProperties = {
  width: "100%",
  display: "flex",
  alignItems: "center",
  gap: "12px",
  flexWrap: "wrap",
  justifyContent: "space-between",
  border: "1px solid var(--app-dock-border)",
  borderRadius: "8px",
  padding: "10px 12px",
  marginBottom: "20px",
  position: "sticky",
  top: "68px",
  zIndex: 30,
  background: "var(--app-dock-bg)",
  backdropFilter: "blur(12px)",
  boxSizing: "border-box",
  boxShadow: "var(--app-dock-shadow)",
};

const detailToolbarLeftStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: "12px",
  flexWrap: "wrap",
  minWidth: 0,
};

const detailRefreshingNoticeStyle: React.CSSProperties = {
  border: "1px solid var(--app-info-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  color: "var(--app-text-muted)",
  padding: "10px 12px",
  fontSize: "13px",
  fontWeight: 700,
  marginBottom: "16px",
};

const primaryNavLinkStyle: React.CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  minHeight: "40px",
  padding: "0 16px",
  borderRadius: "8px",
  border: "1px solid var(--app-surface-border)",
  background: "var(--app-surface-muted-bg)",
  color: "var(--app-text-strong)",
  textDecoration: "none",
  fontSize: 0,
  fontWeight: 700,
};

const secondaryNavLinkStyle: React.CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  minHeight: "40px",
  padding: "0 16px",
  borderRadius: "8px",
  border: "1px solid var(--app-surface-border)",
  background: "var(--app-surface-muted-bg)",
  color: "var(--app-text-strong)",
  textDecoration: "none",
  fontSize: "14px",
  fontWeight: 700,
};

const detailPanelStyle: React.CSSProperties = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-bg)",
  boxShadow: "var(--app-surface-shadow)",
};

const detailActionPrimaryStyle: React.CSSProperties = {
  padding: "10px 16px",
  borderRadius: "8px",
  border: "1px solid var(--app-info-border)",
  background: "var(--app-info-bg)",
  color: "var(--app-info-fg)",
  fontSize: "13px",
  fontWeight: 700,
};

const detailActionSecondaryStyle: React.CSSProperties = {
  padding: "10px 16px",
  borderRadius: "8px",
  border: "1px solid var(--app-secondary-action-border)",
  background: "var(--app-secondary-action-bg)",
  color: "var(--app-secondary-action-fg)",
  cursor: "pointer",
  fontSize: "13px",
  fontWeight: 700,
};

const detailActionDangerStyle: React.CSSProperties = {
  ...detailActionSecondaryStyle,
  border: "1px solid var(--app-danger-border)",
  background: "var(--app-danger-bg)",
  color: "var(--app-danger-fg)",
};

const detailActionDisabledStyle: React.CSSProperties = {
  border: "1px solid var(--app-surface-border)",
  background: "var(--app-surface-muted-bg)",
  color: "var(--app-text-subtle)",
  boxShadow: "none",
  opacity: 0.78,
};

const detailActionLinkStyle: React.CSSProperties = {
  ...detailActionSecondaryStyle,
  display: "inline-flex",
  alignItems: "center",
  textDecoration: "none",
};

const inlineReviewLinkStyle: React.CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  border: "1px solid var(--app-info-border)",
  borderRadius: "8px",
  padding: "6px 9px",
  background: "var(--app-info-bg)",
  color: "var(--app-info-fg)",
  fontSize: "12px",
  fontWeight: 800,
  textDecoration: "none",
};

const discussionPanelHeaderStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  gap: "10px",
  marginBottom: "10px",
};

const discussionExpandButtonStyle: React.CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  gap: "6px",
  height: "30px",
  padding: "0 10px",
  borderRadius: "999px",
  border: "1px solid var(--app-secondary-action-border)",
  background: "var(--app-secondary-action-bg)",
  color: "var(--app-secondary-action-fg)",
  cursor: "pointer",
  fontSize: "12px",
  fontWeight: 700,
  lineHeight: 1,
  whiteSpace: "nowrap",
};

const discussionCopyButtonStyle: React.CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  gap: "5px",
  minWidth: "72px",
  height: "28px",
  padding: "0 9px",
  borderRadius: "999px",
  border: "1px solid var(--app-secondary-action-border)",
  background: "var(--app-secondary-action-bg)",
  color: "var(--app-secondary-action-fg)",
  cursor: "pointer",
  fontSize: "12px",
  fontWeight: 700,
  lineHeight: 1,
  whiteSpace: "nowrap",
};

const discussionCopyButtonOnPrimaryStyle: React.CSSProperties = {
  border: "1px solid rgba(255,255,255,0.28)",
  background: "rgba(255,255,255,0.12)",
  color: "var(--app-primary-action-fg)",
};

const detailPillStyle: React.CSSProperties = {
  padding: "7px 10px",
  borderRadius: "999px",
  border: "1px solid var(--app-secondary-action-border)",
  background: "var(--app-secondary-action-bg)",
  color: "var(--app-secondary-action-fg)",
  fontSize: "12px",
  fontWeight: 600,
};

const detailPillActiveStyle: React.CSSProperties = {
  ...detailPillStyle,
  border: "1px solid var(--app-primary-action-border)",
  background: "var(--app-primary-action-bg)",
  color: "var(--app-primary-action-fg)",
};

const thinkingStyleDisclosureStyle: React.CSSProperties = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  padding: "10px 12px",
  marginBottom: "14px",
};

const thinkingStyleSummaryStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  gap: "10px",
  cursor: "pointer",
  color: "var(--app-text-strong)",
  fontSize: "13px",
  fontWeight: 800,
};

const thinkingStyleModeStyle: React.CSSProperties = {
  border: "1px solid var(--app-chip-border)",
  borderRadius: "999px",
  background: "var(--app-chip-bg)",
  color: "var(--app-chip-fg)",
  padding: "3px 8px",
  fontSize: "11px",
  fontWeight: 700,
  whiteSpace: "nowrap",
};

const thinkingStyleGridStyle: React.CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))",
  gap: "8px",
  marginTop: "10px",
};

const thinkingStyleItemStyle: React.CSSProperties = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-bg)",
  padding: "9px 10px",
  display: "grid",
  gap: "4px",
  color: "var(--app-text-muted)",
  fontSize: "12px",
  lineHeight: 1.45,
};

const thinkingStyleExampleStyle: React.CSSProperties = {
  borderTop: "1px solid var(--app-surface-border)",
  marginTop: "10px",
  paddingTop: "10px",
  color: "var(--app-text-subtle)",
  fontSize: "12px",
  lineHeight: 1.5,
};

const manualMetadataChipStyle: React.CSSProperties = {
  padding: "4px 8px",
  borderRadius: "999px",
  border: "1px solid var(--app-chip-border)",
  background: "var(--app-chip-bg)",
  color: "var(--app-chip-fg)",
};

const manualSourceContextGridStyle: React.CSSProperties = {
  marginTop: "10px",
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
  gap: "10px",
};

const manualSourceContextCardStyle: React.CSSProperties = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  color: "var(--app-text-muted)",
  padding: "10px 12px",
  display: "grid",
  gap: "6px",
  fontSize: "13px",
  lineHeight: 1.55,
};

const manualSourceContextLabelStyle: React.CSSProperties = {
  color: "var(--app-text-subtle)",
  fontSize: "11px",
  fontWeight: 800,
  textTransform: "uppercase",
  letterSpacing: "0.4px",
};

const manualWorkspaceSavedStyle: React.CSSProperties = {
  marginTop: "10px",
  border: "1px solid var(--app-success-border)",
  borderRadius: "8px",
  background: "var(--app-success-bg)",
  color: "var(--app-success-fg)",
  padding: "10px 12px",
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  gap: "10px",
  flexWrap: "wrap",
  fontSize: "13px",
  fontWeight: 700,
};

const manualWorkspaceLinkStyle: React.CSSProperties = {
  border: "1px solid var(--app-success-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  color: "var(--app-success-fg)",
  padding: "6px 10px",
  textDecoration: "none",
  fontSize: "13px",
  fontWeight: 700,
};

const manualSignalHandoffPanelStyle: React.CSSProperties = {
  marginTop: "12px",
  padding: "14px",
  borderRadius: "12px",
  border: "1px solid var(--app-surface-border)",
  background: "var(--app-surface-muted-bg)",
  color: "var(--app-text-muted)",
  fontSize: "13px",
  lineHeight: 1.6,
  display: "grid",
  gap: "10px",
};

const manualSignalHandoffReadyStyle: React.CSSProperties = {
  border: "1px solid var(--app-info-border)",
  background: "var(--app-info-bg)",
  color: "var(--app-info-fg)",
};

const manualSignalHandoffWarningStyle: React.CSSProperties = {
  border: "1px solid var(--app-warning-border)",
  background: "var(--app-warning-bg)",
  color: "var(--app-warning-fg)",
};

const manualSignalHandoffDoneStyle: React.CSSProperties = {
  border: "1px solid var(--app-success-border)",
  background: "var(--app-success-bg)",
  color: "var(--app-success-fg)",
};

const manualSignalHandoffHeaderStyle: React.CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "flex-start",
  gap: "12px",
  flexWrap: "wrap",
};

const manualSignalHandoffChipStyle: React.CSSProperties = {
  border: "1px solid var(--app-chip-border)",
  borderRadius: "999px",
  background: "var(--app-chip-bg)",
  color: "var(--app-chip-fg)",
  padding: "4px 8px",
  fontSize: "11px",
  fontWeight: 800,
};

const manualSignalHandoffGridStyle: React.CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(135px, 1fr))",
  gap: "8px",
};

const manualSignalHandoffItemStyle: React.CSSProperties = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-bg)",
  padding: "9px 10px",
  display: "grid",
  gap: "4px",
};

const manualSignalHandoffActionsStyle: React.CSSProperties = {
  display: "flex",
  gap: "8px",
  flexWrap: "wrap",
};

const manualSignalHandoffPrimaryLinkStyle: React.CSSProperties = {
  border: "1px solid var(--app-info-border)",
  borderRadius: "8px",
  background: "var(--app-info-bg)",
  color: "var(--app-info-fg)",
  padding: "7px 10px",
  fontSize: "13px",
  fontWeight: 700,
  textDecoration: "none",
};

const manualNextActionStyle: React.CSSProperties = {
  marginTop: "10px",
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  color: "var(--app-text-strong)",
  padding: "9px 10px",
  fontSize: "13px",
  lineHeight: 1.55,
  fontWeight: 700,
};

const manualHandoffPanelStyle: React.CSSProperties = {
  marginTop: "10px",
  border: "1px solid var(--app-info-border)",
  borderRadius: "8px",
  background: "var(--app-info-bg)",
  color: "var(--app-info-fg)",
  padding: "10px 12px",
  display: "grid",
  gap: "7px",
  fontSize: "13px",
  lineHeight: 1.55,
};

const manualHandoffMetaStyle: React.CSSProperties = {
  display: "flex",
  gap: "8px",
  flexWrap: "wrap",
  color: "var(--app-text-muted)",
  fontSize: "12px",
  lineHeight: 1.5,
};

const manualCompletionGuideStyle: React.CSSProperties = {
  border: "1px solid var(--app-info-border)",
  borderRadius: "10px",
  background: "var(--app-info-bg)",
  color: "var(--app-info-fg)",
  padding: "10px 12px",
  display: "grid",
  gap: "5px",
  fontSize: "13px",
  lineHeight: 1.55,
  marginBottom: "12px",
};

const manualCompletionGuideWarningStyle: React.CSSProperties = {
  border: "1px solid var(--app-warning-border)",
  background: "var(--app-warning-bg)",
  color: "var(--app-warning-fg)",
};

const manualCompletionGuideDoneStyle: React.CSSProperties = {
  border: "1px solid var(--app-success-border)",
  background: "var(--app-success-bg)",
  color: "var(--app-success-fg)",
};
