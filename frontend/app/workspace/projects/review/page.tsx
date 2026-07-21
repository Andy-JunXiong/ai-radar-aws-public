"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Sparkles } from "lucide-react";

import AppContainer from "@/components/AppContainer";
import RequireAdminAuth from "@/components/RequireAdminAuth";
import VerificationGateNote from "@/components/VerificationGateNote";
import VerifiedInsightObjectPanel, { type VerifiedInsightObjectRow } from "@/components/VerifiedInsightObjectPanel";
import { apiUrl } from "@/lib/api";
import { adminFetch } from "@/lib/adminAuth";
import { adminFetchWithTimeout, isAbortError } from "@/lib/requestTimeout";

type EligibilityDecision = {
  allowed?: boolean;
  reason?: string;
};

type ActionEligibilitySummary = {
  project_takeaway_candidate?: EligibilityDecision;
  watch_only?: EligibilityDecision;
  low_risk_action_candidate?: EligibilityDecision;
  signals?: {
    verification_status?: string;
    unsupported_or_contradicted_claim_count?: number;
    inferred_claim_count?: number;
    allowed_downstream_actions?: string[];
    blocked_downstream_actions?: string[];
  };
};

type ModelProvenance = {
  provider?: string;
  model_id?: string;
  route_key?: string;
  task_type?: string;
  deterministic_fingerprint?: string;
  provenance_schema_version?: number;
  provenance_completeness?: string;
};

type ReasoningCounterCheckDraft = {
  answer?: string;
  summary?: string;
  opposite_or_incompatible_conclusion?: string;
  evidence_used?: string[];
  missing_evidence?: string[];
  reviewer_next_step?: string;
  boundary?: string;
  comparison_mode?: string;
  source_provider?: string;
  source_model_id?: string;
  preferred_counter_provider?: string;
  countercheck_provider?: string;
  provider_selection_note?: string;
  produced_by_model?: ModelProvenance | null;
};

type ReasoningCounterCheckResponse = {
  draft?: ReasoningCounterCheckDraft;
  item?: ProjectTakeawayCandidate;
  persisted?: boolean;
  detail?: string;
};

type DeepProjectMatchReviewMetadata = {
  required?: boolean;
  status?: string;
  posture?: string;
  reason?: string;
  matched_projects?: string[];
  relevant_modules?: string[];
  match_type?: string;
  evidence_boundary?: string;
  downstream_posture?: string;
  review_note?: string;
  review_note_effect?: string;
  generated_analysis?: {
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
    source_read_targets?: Array<{
      target_type?: string;
      url?: string;
      path?: string;
      section_hint?: string;
      question?: string;
    }>;
    evidence_basis?: string;
    verification_effect?: string;
    allowed_downstream_effect?: string;
  } | null;
  generated_analysis_layers?: Array<NonNullable<DeepProjectMatchReviewMetadata["generated_analysis"]>>;
  checklist?: Array<{
    key?: string;
    label?: string;
    value?: string;
    status?: string;
  }>;
  source?: string;
};

type ProjectTakeawayCandidate = {
  project_id?: string;
  project_name?: string;
  signal_id?: string;
  signal_title?: string;
  signal_summary?: string;
  takeaway?: string;
  why_it_matters?: string;
  fit_reason?: string;
  benefits?: string;
  final_reflection?: string;
  status?: string;
  score?: number;
  suggested_stage?: string;
  saved_at?: string;
  reviewed_at?: string;
  confirmed_at?: string;
  rejected_at?: string;
  dismissed_at?: string;
  watched_at?: string;
  action_created_at?: string;
  action_completed_at?: string;
  review_outcome?: string;
  rejection_reason?: string;
  dismissal_reason?: string;
  watch_reason?: string;
  watch_review_date?: string;
  watch_success_criteria?: string;
  watch_status?: string;
  watch_last_reviewed_at?: string;
  watch_followup_result?: string;
  watch_review_note?: string;
  watch_evidence_update?: string;
  watch_next_review_date?: string;
  watch_followup_count?: number;
  action_reason?: string;
  action_expected_outcome?: string;
  action_due_date?: string;
  action_review_date?: string;
  action_completion_note?: string;
  action_completion_result?: string;
  action_completion_evidence_update?: string;
  action_next_review_date?: string;
  action_state?: string;
  action_eligibility?: ActionEligibilitySummary;
  source_type?: string;
  manual_session_id?: string;
  is_manual_source?: boolean;
  upload_reason?: string;
  intended_use?: string;
  cognitive_layer?: string;
  verification_metadata?: {
    review_priority?: string;
    confidence_label?: string;
    confidence_score?: number;
    verification_status?: string;
    claim_support_summary?: Record<string, number>;
    allowed_downstream_actions?: string[];
    blocked_downstream_actions?: string[];
    produced_by_model?: ModelProvenance | null;
    verified_insight?: {
      signal_id?: string;
      status?: string;
      produced_by_model?: ModelProvenance | null;
      claims?: {
        support_summary?: Record<string, number>;
      };
      action_policy?: {
        allowed?: string[];
        blocked?: string[];
      };
    } | null;
    manual_project_takeaway_override?: boolean;
    verification_required?: boolean;
    manual_override_note?: string;
    candidate_requested_from?: string;
    confirmed_final_takeaway?: boolean;
    final_takeaway_id?: string;
    review_bundle_snapshot_id?: string;
    source_type?: string;
    manual_session_id?: string;
    is_manual_source?: boolean;
    upload_reason?: string;
    intended_use?: string;
    cognitive_layer?: string;
    knowledge_convergence?: boolean;
    convergence_brief_id?: string;
    deep_project_match_review?: DeepProjectMatchReviewMetadata | null;
    supply_read?: string;
    demand_read?: string;
    why_paired?: string;
    review_boundary?: string;
    quality?: {
      score?: number;
      label?: string;
      reason?: string;
      recommendation?: string;
      factors?: Record<string, number>;
    };
    review_readiness?: {
      status?: string;
      label?: string;
      reason?: string;
      source_count?: number;
      shared_topic_count?: number;
      matched_project_count?: number;
    };
    evidence_profile?: {
      source_count?: number;
      shared_topic_count?: number;
      strategic_topic_overlap_count?: number;
      agent_watch_score?: number;
      friction_score?: number;
      quality_score?: number;
      quality_label?: string;
      quality_reason?: string;
      support_note?: string;
    };
    project_relevance?: {
      matched_projects?: Array<{
        project_id?: string;
        project_name?: string;
        matched_topics?: string[];
        reason?: string;
      }>;
      match_count?: number;
    };
  };
  candidate_source?: string;
  produced_by_model?: ModelProvenance | null;
  reasoning_counter_check_draft?: ReasoningCounterCheckDraft | null;
  reasoning_counter_check_saved_at?: string;
  reasoning_counter_check_effect?: string;
};

type ProjectReviewRecord = {
  id?: string;
  project_id?: string;
  project_name?: string;
  signal_id?: string;
  signal_title?: string;
  outcome?: string;
  reason?: string;
  source_status?: string;
  candidate_source?: string;
  produced_by_model?: ModelProvenance | null;
  manual_project_takeaway_override?: boolean;
  manual_override_note?: string;
  source_type?: string;
  manual_session_id?: string;
  is_manual_source?: boolean;
  upload_reason?: string;
  intended_use?: string;
  cognitive_layer?: string;
  verification_status?: string;
  claim_support_summary?: Record<string, number>;
  unsupported_claim_count?: number;
  inferred_claim_count?: number;
  allowed_downstream_actions?: string[];
  blocked_downstream_actions?: string[];
  action_eligibility?: ActionEligibilitySummary;
  confidence_score?: number | null;
  confidence_label?: string;
  reviewed_at?: string;
  updated_at?: string;
};

type ProjectReviewSummary = {
  total_records?: number;
  outcome_counts?: Record<string, number>;
  project_counts?: Record<string, number>;
  source_type_counts?: Record<string, number>;
  latest_reviewed_at?: string;
  actionable_count?: number;
  watch_count?: number;
  rejected_or_dismissed_count?: number;
  verification_status_counts?: Record<string, number>;
  blocked_action_counts?: Record<string, number>;
  confidence_label_counts?: Record<string, number>;
  unsupported_claim_count?: number;
  inferred_claim_count?: number;
  low_confidence_count?: number;
  records_with_blocked_actions?: number;
  records_with_action_blocked?: number;
  action_outcomes_with_blocked_gate?: number;
  manual_overrides_with_blocked_action?: number;
  watch_outcomes_with_action_blocked?: number;
  gate_conflict_record_count?: number;
  blocked_action_rate?: number;
  manual_record_count?: number;
  manual_record_rate?: number;
  manual_outcome_counts?: Record<string, number>;
  manual_actionable_count?: number;
  manual_watch_count?: number;
};

type ProjectCalibrationSummary = {
  total_events?: number;
  event_counts?: Record<string, number>;
  outcome_counts?: Record<string, number>;
  source_type_counts?: Record<string, number>;
  latest_event_at?: string;
  actionable_event_count?: number;
  watch_event_count?: number;
  rejected_or_dismissed_event_count?: number;
  candidate_review_event_count?: number;
  candidate_to_actionable_rate?: number;
  takeaway_rejection_rate?: number;
  watch_review_completion_rate?: number;
  watch_reviewed_event_count?: number;
  verification_status_counts?: Record<string, number>;
  blocked_action_counts?: Record<string, number>;
  confidence_label_counts?: Record<string, number>;
  unsupported_claim_count?: number;
  inferred_claim_count?: number;
  low_confidence_event_count?: number;
  events_with_blocked_actions?: number;
  events_with_action_blocked?: number;
  action_events_with_blocked_gate?: number;
  manual_overrides_with_blocked_action?: number;
  watch_events_with_action_blocked?: number;
  gate_conflict_event_count?: number;
  blocked_action_rate?: number;
  manual_event_count?: number;
  manual_event_rate?: number;
  manual_event_counts?: Record<string, number>;
  manual_outcome_counts?: Record<string, number>;
  manual_actionable_event_count?: number;
  manual_watch_event_count?: number;
};

type ReviewView = "pending" | "closed" | "watch" | "action" | "records";
type ReviewDisplayMode = "original" | "simplified";
type CandidateQualityFilter = "all" | "manual_source" | "manual_override" | "knowledge_convergence" | "knowledge_missing_project_fit";
type RecordOutcomeFilter = "all" | "confirmed" | "watch" | "action" | "action_completed" | "rejected" | "dismissed";
type RecordQualityFilter =
  | "all"
  | "manual_override"
  | "gate_conflicts"
  | "action_blocked"
  | "watch_action_blocked"
  | "low_confidence"
  | "blocked_actions"
  | "unsupported_claims"
  | "inferred_claims";
type RecordSortOrder = "newest" | "oldest";

type CandidatesResponse = {
  items?: ProjectTakeawayCandidate[];
  detail?: string;
};

type ConfirmResponse = {
  item?: ProjectTakeawayCandidate;
  detail?: string;
};

type ReviewRecordsResponse = {
  items?: ProjectReviewRecord[];
  detail?: string;
};

type ReviewSummaryResponse = {
  summary?: ProjectReviewSummary;
  detail?: string;
};

type CalibrationSummaryResponse = {
  summary?: ProjectCalibrationSummary;
  detail?: string;
};

type LearningProfileCount = {
  key?: string;
  count?: number;
};

type LearningProfileSignals = {
  actionable_count?: number;
  watch_count?: number;
  caution_count?: number;
  blocked_action_context_count?: number;
  manual_source_context_count?: number;
  gate_conflict_context_count?: number;
  has_actionable_memory?: boolean;
  has_watch_memory?: boolean;
  has_caution_memory?: boolean;
  has_gate_risk?: boolean;
  has_manual_source_learning?: boolean;
};

type ProjectLearningProfile = {
  schema_version?: number;
  profile_type?: string;
  scope?: {
    project_id?: string;
    recent_limit?: number;
  };
  context_role?: string;
  evidence_boundary?: string;
  review_summary?: ProjectReviewSummary;
  calibration_summary?: ProjectCalibrationSummary;
  learning_signals?: LearningProfileSignals;
  outcome_profile?: {
    top_review_outcomes?: LearningProfileCount[];
    top_calibration_outcomes?: LearningProfileCount[];
  };
  risk_profile?: {
    top_blocked_actions?: LearningProfileCount[];
    verification_status_mix?: LearningProfileCount[];
    calibration_verification_status_mix?: LearningProfileCount[];
    blocked_action_rate?: number;
    unsupported_claim_count?: number;
    inferred_claim_count?: number;
  };
  source_profile?: {
    review_source_type_mix?: LearningProfileCount[];
    calibration_source_type_mix?: LearningProfileCount[];
    manual_record_count?: number;
    manual_event_count?: number;
  };
  recent_review_records?: ProjectReviewRecord[];
  recent_calibration_events?: Array<{
    id?: string;
    project_id?: string;
    signal_id?: string;
    event_type?: string;
    outcome?: string;
    source_type?: string;
    verification_status?: string;
    blocked_downstream_actions?: string[];
    review_record_id?: string;
    created_at?: string;
    updated_at?: string;
  }>;
  next_focus?: string[];
  message?: string;
  detail?: string;
};

type ReviewAction = "rejected" | "dismissed" | "watch" | "action";

type ReviewMetadata = {
  watch_review_date?: string;
  watch_success_criteria?: string;
  watch_status?: string;
  action_expected_outcome?: string;
  action_due_date?: string;
  action_review_date?: string;
  followup_result?: string;
  evidence_update?: string;
  next_review_date?: string;
};

type ManualOverrideCalibration = {
  total: number;
  outcomeCounts: Record<string, number>;
  actionableCount: number;
  watchCount: number;
  rejectedOrDismissedCount: number;
  riskCount: number;
  blockedActionCount: number;
  actionCompletedCount: number;
  actionableRate: number;
  rejectionRate: number;
  latestReviewedAt: string;
};

type ReviewLoopFollowupSummary = {
  watchDueCount: number;
  watchMissingPlanCount: number;
  actionDueCount: number;
  actionMissingPlanCount: number;
  actionCompletedCount: number;
  learningRecordCount: number;
  calibrationEventCount: number;
  gateConflictCount: number;
  manualLearningCount: number;
  nextFocus: string;
};

function formatScore(value?: number) {
  if (typeof value !== "number" || Number.isNaN(value)) return "n/a";
  return `${Math.max(0, Math.min(100, Math.round(value)))}/100`;
}

function formatLabel(value?: string) {
  return (value || "")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase())
    .trim();
}

function todayDateKey() {
  return new Date().toISOString().slice(0, 10);
}

function isDateDue(value?: string) {
  const dateKey = (value || "").trim().slice(0, 10);
  return Boolean(dateKey && dateKey <= todayDateKey());
}

function candidateKey(projectId?: string, signalId?: string) {
  return `${projectId || ""}:${signalId || ""}`;
}

function resolveModelProvenance(...candidates: Array<ModelProvenance | null | undefined>): ModelProvenance {
  return candidates.find((candidate) => candidate && typeof candidate === "object") || {
    provenance_schema_version: 0,
    provenance_completeness: "legacy",
  };
}

function formatModelProvenanceChip(provenance: ModelProvenance): string {
  if (provenance.provenance_schema_version !== 1) {
    return "Model: legacy/v0";
  }
  const provider = provenance.provider || "provider unknown";
  const model = provenance.model_id || "model unknown";
  const fingerprint = provenance.deterministic_fingerprint
    ? ` fp ${provenance.deterministic_fingerprint.slice(0, 8)}`
    : "";
  return `Model: ${provider} / ${model}${fingerprint}`;
}

function buildKnowledgeQualityLabel(verification: NonNullable<ProjectTakeawayCandidate["verification_metadata"]>) {
  const score = verification.quality?.score ?? verification.evidence_profile?.quality_score;
  const label = verification.quality?.label || verification.evidence_profile?.quality_label || "Knowledge fit quality";
  const reason = verification.quality?.reason || verification.evidence_profile?.quality_reason || "";
  const recommendation = verification.quality?.recommendation || "";
  return {
    score: typeof score === "number" ? score : null,
    label,
    reason,
    recommendation,
  };
}

function buildKnowledgeQualityFactorRows(verification: NonNullable<ProjectTakeawayCandidate["verification_metadata"]>) {
  const backendFactors = verification.quality?.factors || {};
  const sourceCount = verification.evidence_profile?.source_count ?? verification.review_readiness?.source_count ?? 0;
  const sharedTopicCount = verification.evidence_profile?.shared_topic_count ?? verification.review_readiness?.shared_topic_count ?? 0;
  const projectCount = verification.project_relevance?.match_count ?? verification.review_readiness?.matched_project_count ?? 0;
  const strategicOverlap = verification.evidence_profile?.strategic_topic_overlap_count ?? 0;
  const agentScore = verification.evidence_profile?.agent_watch_score ?? 0;
  const frictionScore = verification.evidence_profile?.friction_score ?? 0;
  let penalty = 0;
  if (sourceCount < 2) penalty += 14;
  if (sharedTopicCount === 0) penalty += 16;
  if (projectCount === 0) penalty += 12;
  if (agentScore < 0.35 || frictionScore < 0.35) penalty += 8;
  const fallbackFactors = {
    evidence_score: Math.min(34, sourceCount * 10 + sharedTopicCount * 7),
    fit_score: Math.min(38, projectCount * 12),
    strategy_score: Math.min(12, strategicOverlap * 4),
    signal_score: Math.min(20, Math.round(((agentScore + frictionScore) / 2) * 20)),
    penalty,
  };
  const factors = typeof backendFactors.evidence_score === "number" ? backendFactors : fallbackFactors;
  return [
    { label: "Evidence", value: factors.evidence_score },
    { label: "Fit", value: factors.fit_score },
    { label: "Strategy", value: factors.strategy_score },
    { label: "Signal", value: factors.signal_score },
    { label: "Penalty", value: factors.penalty },
  ].filter((row) => typeof row.value === "number");
}

function buildKnowledgeReviewPath(verification: NonNullable<ProjectTakeawayCandidate["verification_metadata"]>) {
  const score = verification.quality?.score ?? verification.evidence_profile?.quality_score ?? 0;
  const projectCount = verification.project_relevance?.match_count ?? verification.review_readiness?.matched_project_count ?? 0;
  const actionBlocked = verification.blocked_downstream_actions?.includes("low_risk_action_candidate");
  if (score >= 70 && projectCount > 0) {
    return {
      label: "Strong Fit",
      body: "Prioritize Confirm review after checking the linked supply and demand sources. Action remains separate from this fit decision.",
    };
  }
  if (score >= 70) {
    return {
      label: "Strong Evidence / Missing Project Fit",
      body: "Keep this in Knowledge or Watch until the project fit is clearer; strong convergence alone is not a project takeaway.",
    };
  }
  if (score >= 45) {
    return {
      label: "Review Caution",
      body: "Use Watch when the pair is directionally useful, or Confirm only if project fit is explicit in the linked evidence.",
    };
  }
  return {
    label: actionBlocked ? "Thin Fit / Action Blocked" : "Thin Fit",
    body: "Prefer Watch or Reject. Do not use this as action evidence unless a human override documents the accepted risk.",
  };
}

function buildKnowledgeRationaleRows(verification: NonNullable<ProjectTakeawayCandidate["verification_metadata"]>) {
  return [
    { label: "Supply read", value: verification.supply_read },
    { label: "Demand read", value: verification.demand_read },
    { label: "Why paired", value: verification.why_paired },
    { label: "Review boundary", value: verification.review_boundary },
  ].filter((row) => String(row.value || "").trim());
}

function formatClaimSupport(summary?: Record<string, number>) {
  if (!summary) return "";
  return Object.entries(summary)
    .filter(([, count]) => typeof count === "number" && count > 0)
    .map(([key, count]) => `${formatLabel(key)} ${count}`)
    .join(", ");
}

function getSupportCount(summary: Record<string, number> | undefined, keys: string[]) {
  if (!summary) return 0;
  return keys.reduce((total, key) => total + (typeof summary[key] === "number" ? summary[key] : 0), 0);
}

function includesAnyTerm(text: string, terms: string[]) {
  return terms.some((term) => text.includes(term));
}

function buildCandidateFramingRawText(item: ProjectTakeawayCandidate) {
  const verification = item.verification_metadata || {};
  const values = [
    item.signal_title,
    item.signal_summary,
    item.takeaway,
    item.why_it_matters,
    item.fit_reason,
    item.benefits,
    item.final_reflection,
    item.candidate_source,
    verification.review_boundary,
    verification.why_paired,
    verification.supply_read,
    verification.demand_read,
    verification.deep_project_match_review?.review_note,
    verification.deep_project_match_review?.generated_analysis?.narrative_summary,
    verification.deep_project_match_review?.generated_analysis?.architecture_comparison,
    verification.deep_project_match_review?.generated_analysis?.beware,
    verification.deep_project_match_review?.generated_analysis?.evidence_boundary,
  ];
  return values
    .filter((value): value is string => Boolean(value && String(value).trim()))
    .join("\n");
}

function buildCandidateFramingText(item: ProjectTakeawayCandidate) {
  return buildCandidateFramingRawText(item).toLowerCase();
}

function normalizedUnique(values: string[]) {
  const seen = new Set<string>();
  const result: string[] = [];
  values.forEach((value) => {
    const normalized = value.replace(/\s+/g, " ").trim();
    const key = normalized.toLowerCase();
    if (!normalized || seen.has(key)) return;
    seen.add(key);
    result.push(normalized);
  });
  return result;
}

function extractProjectLikeLabelsFromText(text: string) {
  const labels: string[] = [];
  const forPattern =
    /\bFor\s+([A-Z][A-Za-z0-9_ -]{1,80}?)(?=,|\s+(?:this|the|it|there|those|a|an|is|are|can|could|may|might|should|would|needs?|suggests?|maps?|supports?)|:|;|\.)/g;
  let match = forPattern.exec(text);
  while (match) {
    labels.push(match[1]);
    match = forPattern.exec(text);
  }
  return normalizedUnique(labels);
}

function getApplicationMappingLabels(item: ProjectTakeawayCandidate) {
  const verification = item.verification_metadata || {};
  const matchedProjects = verification.project_relevance?.matched_projects || [];
  const projectNames = matchedProjects
    .map((project) => project.project_name || project.project_id || "")
    .filter(Boolean);
  const deepMatchProjects = verification.deep_project_match_review?.matched_projects || [];
  return normalizedUnique([
    item.project_name || "",
    ...projectNames,
    ...deepMatchProjects,
    ...extractProjectLikeLabelsFromText(buildCandidateFramingRawText(item)),
  ]);
}

function sentenceHasApplicationLanguage(sentence: string) {
  const text = sentence.toLowerCase();
  return includesAnyTerm(text, [
    "could",
    "may",
    "might",
    "should",
    "would",
    "support",
    "supports",
    "relevant",
    "apply",
    "applies",
    "application",
    "maps",
    "mapped",
    "embedded",
    "retrieved",
    "evolve",
    "suggests",
    "needs to",
    "useful example",
  ]);
}

function buildApplicationMappingLoad(item: ProjectTakeawayCandidate) {
  const rawText = buildCandidateFramingRawText(item);
  const sentences = rawText
    .split(/(?<=[.!?])\s+|;\s+|\n+/)
    .map((sentence) => sentence.trim())
    .filter(Boolean);
  const labels = getApplicationMappingLabels(item);
  const matchedLabels = labels.filter((label) => {
    const labelLower = label.toLowerCase();
    return sentences.some((sentence) => sentence.toLowerCase().includes(labelLower) && sentenceHasApplicationLanguage(sentence));
  });
  const fallbackLabels = matchedLabels.length ? matchedLabels : labels;
  const count = matchedLabels.length;

  if (count > 1) {
    return {
      count,
      labels: matchedLabels,
      summary: `${count} possible application-mapping leap(s) detected: ${matchedLabels.join(", ")}. Review each project mapping separately; the packet may support one mapping without supporting the others.`,
    };
  }
  if (count === 1) {
    return {
      count,
      labels: matchedLabels,
      summary: `1 possible application-mapping leap detected: ${matchedLabels[0]}. Check whether the packet supports this project mapping as stated.`,
    };
  }
  if (fallbackLabels.length > 1) {
    return {
      count: fallbackLabels.length,
      labels: fallbackLabels,
      summary: `${fallbackLabels.length} project reference(s) detected without clear application-language triggers: ${fallbackLabels.join(", ")}. Check whether the candidate is bundling several project mappings into one conclusion.`,
    };
  }
  return {
    count: 0,
    labels: fallbackLabels,
    summary: "No separate application-mapping leap was detected by the lightweight reviewer heuristic.",
  };
}

function buildFramingChecklist(item: ProjectTakeawayCandidate) {
  const verification = item.verification_metadata || {};
  const text = buildCandidateFramingText(item);
  const checklist: Array<{ label: string; body: string }> = [];
  const producer =
    item.produced_by_model ||
    verification.produced_by_model ||
    verification.verified_insight?.produced_by_model ||
    null;
  const provenanceVersion = producer?.provenance_schema_version;

  if (
    includesAnyTerm(text, [
      "benchmark",
      "faster",
      "slower",
      "token",
      "tokens",
      "tool call",
      "tool calls",
      "efficiency",
      "latency",
      "cost",
      "x fewer",
      "x faster",
      "% faster",
      "% fewer",
    ])
  ) {
    checklist.push({
      label: "Benchmark caveat",
      body: "Check baseline, task type, repo/sample count, model/version, run count, and whether the result is independent or author-reported.",
    });
  }

  if (
    includesAnyTerm(text, [
      "diagram",
      "architecture graph",
      "graph",
      "svg",
      "mermaid",
      "d2",
      "renderer",
      "generated artifact",
      "tool output",
      "visualization",
    ])
  ) {
    checklist.push({
      label: "Artifact vs evidence",
      body: "Generated diagrams, graphs, and tool outputs can be useful artifacts, but they do not by themselves verify the underlying claim.",
    });
  }

  if (
    includesAnyTerm(text, [
      "supports",
      "supported",
      "backend",
      "backends",
      "database",
      "databases",
      "sqlite",
      "neo4j",
      "arango",
      "memgraph",
      "language",
      "languages",
      "integrations",
      "capability list",
    ])
  ) {
    checklist.push({
      label: "Capability-list precision",
      body: "Check the exact capability list against primary-source docs or source code before treating a precise table as reliable.",
    });
  }

  if (
    includesAnyTerm(text, [
      "standalone",
      "independent tool",
      "platform",
      "product",
      "production-ready",
      "agent skill",
      "plugin",
      "helper",
      "demo",
      "example",
    ])
  ) {
    checklist.push({
      label: "Scope wording",
      body: "Compare the candidate wording with the source wording; do not let a helper, skill, demo, or example become a broader product claim.",
    });
  }

  if (!producer || provenanceVersion === undefined || provenanceVersion === null || provenanceVersion < 1) {
    checklist.push({
      label: "Producer provenance",
      body: "Check whether source model provenance is legacy, incomplete, or missing; judge-vs-producer separation may not hold from this candidate alone.",
    });
  }

  if (!checklist.length) {
    checklist.push({
      label: "No keyword-triggered framing warning",
      body: "No benchmark, artifact, capability-list, scope, or provenance keyword was detected. Reviewer judgment still owns the final framing check.",
    });
  }

  return checklist;
}

function buildPacketIntegrityChecks(item: ProjectTakeawayCandidate) {
  const verification = item.verification_metadata || {};
  const candidateSignalId = String(item.signal_id || "").trim();
  const embeddedSignalId = String(verification.verified_insight?.signal_id || "").trim();
  const checks: Array<{ label: string; body: string }> = [];

  if (candidateSignalId && embeddedSignalId && candidateSignalId !== embeddedSignalId) {
    checks.push({
      label: "Signal mismatch",
      body: `Candidate signal_id (${candidateSignalId}) differs from embedded verified_insight.signal_id (${embeddedSignalId}); inspect whether the evidence packet is stale, misattached, or referring to the wrong signal before relying on it.`,
    });
  }

  return checks;
}

function buildReasoningAssessmentAdvisory({
  item,
  actionEligibility,
  claimSupport,
}: {
  item: ProjectTakeawayCandidate;
  actionEligibility: ActionEligibilitySummary | null;
  claimSupport: string;
}) {
  const verification = item.verification_metadata || {};
  const supportSummary =
    verification.claim_support_summary ||
    verification.verified_insight?.claims?.support_summary ||
    {};
  const directCount = getSupportCount(supportSummary, ["direct", "supported", "fully_supported"]);
  const partialCount = getSupportCount(supportSummary, ["partial", "partially_supported"]);
  const inferredCount = getSupportCount(supportSummary, ["inferred"]);
  const unsupportedCount = getSupportCount(supportSummary, ["unsupported", "contradicted"]);
  const blockedActions =
    actionEligibility?.signals?.blocked_downstream_actions ||
    verification.blocked_downstream_actions ||
    verification.verified_insight?.action_policy?.blocked ||
    [];
  const hasRiskyComposition = unsupportedCount > 0 || inferredCount > 0 || partialCount > 0 || blockedActions.length > 0;
  const hasExplicitWarrant = Boolean(
    item.fit_reason ||
      item.why_it_matters ||
      verification.why_paired ||
      verification.review_boundary ||
      verification.deep_project_match_review?.review_note
  );
  const sourceLabel = getCandidateSourceLabel(item);
  const warrantSource =
    item.fit_reason ||
    item.why_it_matters ||
    verification.why_paired ||
    verification.deep_project_match_review?.review_note ||
    verification.review_boundary ||
    "";
  const originalInsight =
    item.takeaway ||
    item.final_reflection ||
    item.why_it_matters ||
    item.fit_reason ||
    "No original candidate insight recorded; inspect the candidate source before deciding.";

  const label = unsupportedCount > 0
    ? "Composition risk"
    : hasRiskyComposition
      ? "Check warrant before decision"
      : "Review-ready prompt";
  const tone: "good" | "watch" | "neutral" = unsupportedCount > 0 || blockedActions.length > 0
    ? "watch"
    : hasRiskyComposition || !hasExplicitWarrant
      ? "neutral"
      : "good";
  const summary = unsupportedCount > 0
    ? "The recorded packet contains unsupported or contradicted claim risk; do not let a polished takeaway outrun the evidence."
    : hasRiskyComposition
      ? "The recorded packet includes partial, inferred, or blocked-action context; check the reasoning bridge before deciding."
      : "No obvious claim-composition risk is recorded, but reviewer judgment still owns the final decision.";
  const supportFallback = [
    directCount ? `direct ${directCount}` : "",
    partialCount ? `partial ${partialCount}` : "",
    inferredCount ? `inferred ${inferredCount}` : "",
    unsupportedCount ? `unsupported/contradicted ${unsupportedCount}` : "",
  ].filter(Boolean).join(", ");
  const loadBearing = claimSupport || supportFallback || "No claim support summary recorded; inspect the source note before treating the takeaway as durable.";
  const packetIntegrityChecks = buildPacketIntegrityChecks(item);
  const hasPacketIntegrityWarning = packetIntegrityChecks.length > 0;
  const applicationMappingLoad = buildApplicationMappingLoad(item);
  const extraInferenceLoadParts = [
    partialCount ? `${partialCount} partially supported claim(s) need reviewer judgment before they can support the full takeaway.` : "",
    inferredCount ? `${inferredCount} inferred claim(s) may support only a weaker or Watch-level conclusion.` : "",
    unsupportedCount ? `${unsupportedCount} unsupported or contradicted claim(s) can break the composed conclusion even when other claims are supported.` : "",
    blockedActions.length ? `Blocked downstream action(s): ${formatActionList(blockedActions)}. Do not let a review-ready wording imply Action eligibility.` : "",
  ].filter(Boolean).join(" ");

  return {
    label,
    tone,
    summary,
    originalInsight,
    loadBearing,
    compositionBridge: {
      label: hasPacketIntegrityWarning ? "Integrity-first review required" : "Packet facts -> candidate takeaway",
      conclusion: originalInsight,
      isIntegrityBlocked: hasPacketIntegrityWarning,
      inferenceLoad: extraInferenceLoadParts || "No claim-level extra inference load is recorded; still confirm the candidate takeaway does not outrun the packet facts.",
      reviewerQuestion: hasPacketIntegrityWarning
        ? "First resolve whether the packet refers to the right signal. Then ask whether the packet facts support this composed conclusion as stated, or only a weaker, Watch-only, or no-takeaway conclusion."
        : "Do the packet facts support this composed conclusion as stated, or only a weaker, Watch-only, or no-takeaway conclusion?",
      applicationMappingLoad,
    },
    warrant: hasExplicitWarrant
      ? `${sourceLabel} warrant to inspect: ${warrantSource.trim()}`
      : "No explicit warrant recorded; reviewer should state why this evidence supports the takeaway before Confirm or Action.",
    counterCheck: blockedActions.length > 0
      ? `Counter-check: not system-adjudicated. Reviewer answer needed: Yes / No / Unclear on whether the same evidence supports an opposite or incompatible conclusion, or only Watch while ${formatActionList(blockedActions)} stays blocked.`
      : "Counter-check: not system-adjudicated. Reviewer answer needed: Yes / No / Unclear on whether the same evidence supports an opposite conclusion, incompatible conclusion, weaker conclusion, Watch posture, or no project takeaway.",
    boundary: "Reviewer advisory only: does not change verification_status, Project Takeaway gate, blocked_downstream_actions, or Action eligibility.",
    framingChecklist: buildFramingChecklist(item),
    packetIntegrityChecks,
  };
}

function isManualOverrideCandidate(item: ProjectTakeawayCandidate) {
  const verification = item.verification_metadata || {};
  return Boolean(
    verification.manual_project_takeaway_override ||
      item.candidate_source === "manual_project_takeaway_override"
  );
}

function isKnowledgeConvergenceCandidate(item: ProjectTakeawayCandidate) {
  const verification = item.verification_metadata || {};
  return Boolean(
    verification.knowledge_convergence ||
      item.candidate_source === "knowledge_convergence"
  );
}

function isConfirmedFinalTakeawayHandoff(item: ProjectTakeawayCandidate) {
  const verification = item.verification_metadata || {};
  return Boolean(
    verification.confirmed_final_takeaway ||
      verification.candidate_requested_from === "confirmed_final_takeaway" ||
      item.candidate_source === "confirmed_final_takeaway"
  );
}

function getKnowledgeProjectMatchCount(item: ProjectTakeawayCandidate) {
  const verification = item.verification_metadata || {};
  return verification.project_relevance?.match_count ?? verification.review_readiness?.matched_project_count ?? 0;
}

function isKnowledgeMissingProjectFitCandidate(item: ProjectTakeawayCandidate) {
  return isKnowledgeConvergenceCandidate(item) && getKnowledgeProjectMatchCount(item) === 0;
}

function isManualSourceCandidate(item: ProjectTakeawayCandidate) {
  const verification = item.verification_metadata || {};
  const signalId = String(item.signal_id || "").toLowerCase();
  return Boolean(
    item.is_manual_source ||
      verification.is_manual_source ||
      item.manual_session_id ||
      verification.manual_session_id ||
      item.upload_reason ||
      verification.upload_reason ||
      item.intended_use ||
      verification.intended_use ||
      signalId.startsWith("manual_") ||
      item.source_type === "manual_upload" ||
      verification.source_type === "manual_upload" ||
      item.candidate_source === "manual_project_takeaway_override"
  );
}

function getCandidateManualSessionId(item: ProjectTakeawayCandidate) {
  const verification = item.verification_metadata || {};
  if (item.manual_session_id) return item.manual_session_id;
  if (verification.manual_session_id) return verification.manual_session_id;
  const signalId = item.signal_id || "";
  if (signalId.startsWith("manual_")) return signalId.slice("manual_".length);
  return "";
}

function getCandidateSourceLabel(item: ProjectTakeawayCandidate) {
  if (isManualOverrideCandidate(item)) return "Manual Override";
  if (isManualSourceCandidate(item)) return "Manual Upload";
  if (isKnowledgeConvergenceCandidate(item)) return "Knowledge Convergence";
  return "Verified Signal";
}

function buildCandidateNextStep({
  item,
  activeView,
  actionEligibility,
  actionBlocked,
}: {
  item: ProjectTakeawayCandidate;
  activeView: ReviewView;
  actionEligibility: ActionEligibilitySummary | null;
  actionBlocked: boolean;
}) {
  const status = (item.status || "").toLowerCase();
  if (activeView === "watch" || status === "watch") {
    return {
      title: "Watch Follow-up",
      body: item.watch_review_date
        ? `Review again on ${item.watch_review_date}; keep the success criteria close to the original gate reason.`
        : "Set a review date and success criteria so this does not become passive backlog.",
    };
  }
  if (activeView === "action" || status === "action") {
    return {
      title: "Action Follow-up",
      body: item.action_due_date
        ? `Track delivery by ${item.action_due_date}, then complete it with an outcome note.`
        : "Add owner/date/expected outcome before treating this as operational work.",
    };
  }
  if (status === "confirmed") {
    return {
      title: "Confirmed Takeaway",
      body: "Open Fit Detail to inspect the saved project improvement and keep the review record as calibration context.",
    };
  }
  if (status === "rejected" || status === "dismissed") {
    return {
      title: "Closed Review",
      body: "This candidate is no longer active; use Records if the reason should inform future calibration.",
    };
  }
  if (isManualOverrideCandidate(item)) {
    return {
      title: "Override Review",
      body: "Check the original signal and gate note first; choose Watch when value is plausible but evidence is still thin.",
    };
  }
  if (isManualSourceCandidate(item)) {
    return {
      title: "Manual Source Review",
      body: "Confirm the manual upload intent, evidence note, and completion route before moving this into Project Takeaways.",
    };
  }
  if (isKnowledgeConvergenceCandidate(item)) {
    return {
      title: "Knowledge Fit Review",
      body: actionBlocked
        ? "Review the supply/demand fit, then Watch, Confirm, or Reject. Low-risk Action stays blocked unless a human override accepts the evidence risk."
        : "Review the supply/demand fit before confirming. This is convergence context, not a raw Signal Detail object.",
    };
  }
  if (actionBlocked) {
    return {
      title: "Recommended Next Step",
      body: actionEligibility?.watch_only?.reason || "Action is blocked by verification; Watch or Reject is safer than immediate action.",
    };
  }
  return {
    title: "Review Decision",
    body: "Confirm strong project fit, Watch uncertain value, Action only with a clear owner/date, or Reject weak fit.",
  };
}

function buildCandidateDecisionOptions({
  item,
  actionEligibility,
  actionBlocked,
  projectTakeawayBlocked,
}: {
  item: ProjectTakeawayCandidate;
  actionEligibility: ActionEligibilitySummary | null;
  actionBlocked: boolean;
  projectTakeawayBlocked: boolean;
}) {
  const verification = item.verification_metadata || {};
  const options = [
    {
      label: "Confirm",
      value: projectTakeawayBlocked
        ? "Blocked unless override note and expected outcome justify the risk."
        : isKnowledgeConvergenceCandidate(item)
          ? "Use when supply/demand fit and project match are explicit."
          : "Use when project fit is durable and evidence is strong enough.",
    },
    {
      label: "Watch",
      value:
        actionEligibility?.watch_only?.reason ||
        "Use when the signal is directionally useful but timing or evidence is still thin.",
    },
    {
      label: "Reject",
      value: "Use when project fit is weak, generic, stale, or not worth future review.",
    },
  ];

  if (actionBlocked || verification.blocked_downstream_actions?.includes("low_risk_action_candidate")) {
    options.push({
      label: "Action",
      value: "Blocked for ordinary flow; only use Override Action with explicit risk acceptance and dates.",
    });
  } else {
    options.push({
      label: "Action",
      value: "Use only with a concrete owner/date/expected outcome.",
    });
  }

  return options;
}

function buildCandidateDecisionShortcut({
  item,
  actionEligibility,
  actionBlocked,
  projectTakeawayBlocked,
}: {
  item: ProjectTakeawayCandidate;
  actionEligibility: ActionEligibilitySummary | null;
  actionBlocked: boolean;
  projectTakeawayBlocked: boolean;
}) {
  const verification = item.verification_metadata || {};
  const score = typeof item.score === "number" ? item.score : 0;

  if (projectTakeawayBlocked) {
    return {
      label: "Watch or Reject",
      tone: "watch" as const,
      reason: actionEligibility?.project_takeaway_candidate?.reason || "Project Takeaway gate is blocked.",
      primary: "Use Watch when the signal may become useful; Reject when project fit is weak.",
      secondary: "Confirm requires the explicit override path with a reviewer note and expected outcome.",
    };
  }

  if (isKnowledgeConvergenceCandidate(item)) {
    const qualityScore =
      verification.quality?.score ?? verification.evidence_profile?.quality_score ?? score;
    const projectCount =
      verification.project_relevance?.match_count ??
      verification.review_readiness?.matched_project_count ??
      0;
    if (typeof qualityScore === "number" && qualityScore >= 70 && projectCount > 0) {
      return {
        label: "Confirm Fit",
        tone: "good" as const,
        reason: "Knowledge convergence has strong enough fit for human project-fit review.",
        primary: "Check the linked supply/demand rationale, then confirm if it is durable for the project.",
        secondary: actionBlocked
          ? "Action remains blocked unless an override accepts the evidence risk."
          : "Keep Action separate unless there is a concrete owner/date.",
      };
    }
    return {
      label: "Watch First",
      tone: "watch" as const,
      reason: "Knowledge convergence is useful context, but fit still needs human judgment.",
      primary: "Use Watch when directionally useful; Reject generic or low-fit pairings.",
      secondary: "Confirm only when project fit is explicit in the evidence.",
    };
  }

  if (isManualSourceCandidate(item) && !isManualOverrideCandidate(item)) {
    return {
      label: "Review Manual Route",
      tone: "watch" as const,
      reason: "Manual uploads need intent and Signal Detail evidence checked before becoming durable takeaways.",
      primary: "Open the manual session or Signal Detail, then Confirm only if the completion path is clear.",
      secondary: "Use Watch for promising manual context that is not ready for Workspace or Project Takeaway.",
    };
  }

  if (actionBlocked) {
    return {
      label: "Watch Safer",
      tone: "watch" as const,
      reason: actionEligibility?.low_risk_action_candidate?.reason || "Action is blocked by verification.",
      primary: "Choose Watch or Reject before considering any override.",
      secondary: "Action is not available in the ordinary flow.",
    };
  }

  if (score >= 70) {
    return {
      label: "Confirm Candidate",
      tone: "good" as const,
      reason: "Score and gate state are strong enough for a focused confirm review.",
      primary: "Confirm when the project fit is durable and evidence is specific.",
      secondary: "Use Action only when owner/date/expected outcome are already concrete.",
    };
  }

  return {
    label: "Triage",
    tone: "neutral" as const,
    reason: "No strong automatic path is visible from the current candidate metadata.",
    primary: "Confirm strong fit, Watch partial value, Reject weak fit.",
    secondary: "Keep Action for concrete owner/date work only.",
  };
}

function buildSimplifiedCandidateSnapshot({
  item,
  actionEligibility,
  claimSupport,
  sourceLabel,
  actionBlocked,
  projectTakeawayBlocked,
}: {
  item: ProjectTakeawayCandidate;
  actionEligibility: ActionEligibilitySummary | null;
  claimSupport: string;
  sourceLabel: string;
  actionBlocked: boolean;
  projectTakeawayBlocked: boolean;
}) {
  const verification = item.verification_metadata || {};
  const status =
    actionEligibility?.signals?.verification_status ||
    verification.verification_status ||
    verification.verified_insight?.status ||
    "";
  const confidence = formatConfidence(verification.confidence_label, verification.confidence_score);
  const blockedActions =
    actionEligibility?.signals?.blocked_downstream_actions ||
    verification.blocked_downstream_actions ||
    [];
  const qualityScore =
    verification.quality?.score ?? verification.evidence_profile?.quality_score ?? null;
  const projectCount = getKnowledgeProjectMatchCount(item);
  const gateReason =
    actionEligibility?.project_takeaway_candidate?.reason ||
    actionEligibility?.low_risk_action_candidate?.reason ||
    "No gate reason recorded.";

  return [
    {
      label: "Decision Route",
      value: projectTakeawayBlocked
        ? "Watch or Reject"
        : actionBlocked
          ? "Watch before Action"
          : isKnowledgeConvergenceCandidate(item)
            ? "Project-fit review"
            : "Review ready",
      detail: projectTakeawayBlocked
        ? "Confirm needs explicit override context."
        : actionBlocked
          ? "Ordinary Action is blocked; keep review conservative."
          : "Ordinary review actions are available.",
    },
    {
      label: "Evidence",
      value: claimSupport || formatLabel(status) || "Not recorded",
      detail: confidence !== "n/a" ? `Confidence: ${confidence}` : "Confidence not recorded.",
    },
    {
      label: "Gate",
      value: projectTakeawayBlocked
        ? "Confirm blocked"
        : actionBlocked
          ? "Action blocked"
          : "Gate clear",
      detail: gateReason,
    },
    {
      label: "Source",
      value: sourceLabel,
      detail: isKnowledgeConvergenceCandidate(item)
        ? `Quality ${typeof qualityScore === "number" ? qualityScore.toFixed(0) : "n/a"} / Projects ${projectCount}`
        : blockedActions.length
          ? `Blocked: ${formatActionList(blockedActions)}`
          : `Score: ${formatScore(item.score)}`,
    },
  ];
}

function buildWorkbenchDecisionLine({
  pendingCount,
  watchCount,
  actionCount,
  actionBlockedCount,
  manualCount,
  knowledgeCount,
}: {
  pendingCount: number;
  watchCount: number;
  actionCount: number;
  actionBlockedCount: number;
  manualCount: number;
  knowledgeCount: number;
}) {
  if (pendingCount === 0 && watchCount === 0 && actionCount === 0) {
    return "No active review work is waiting. Use Records for calibration or create a new candidate from Signal Detail.";
  }
  if (knowledgeCount > 0) {
    return `${knowledgeCount} Knowledge Convergence item(s) need supply/demand project-fit review; keep Action blocked unless a human override accepts the evidence risk.`;
  }
  if (actionBlockedCount > 0) {
    return `${actionBlockedCount} pending item(s) have Action blocked by verification; route them to Watch, Reject, or manual override only after evidence review.`;
  }
  if (manualCount > 0) {
    return `${manualCount} manual-source item(s) need intent and completion-route review before becoming durable project judgment.`;
  }
  if (actionCount > 0) {
    return `${actionCount} action item(s) need completion notes so they can become calibration evidence.`;
  }
  if (watchCount > 0) {
    return `${watchCount} watch item(s) need dated follow-up and success criteria.`;
  }
  return "Pending candidates are ready for human project-fit review.";
}

function getActiveQueueGuide(activeView: ReviewView) {
  if (activeView === "watch") {
    return {
      title: "Watch Queue",
      body: "Use this queue for valuable but still uncertain takeaways. Every item should have a review date and success criteria before it is trusted as project direction.",
    };
  }
  if (activeView === "action") {
    return {
      title: "Action Queue",
      body: "Use this queue only when the next step is concrete. Due date, review date, expected outcome, and completion note turn the action into calibration data.",
    };
  }
  if (activeView === "records") {
    return {
      title: "Review Records",
      body: "Records are the calibration layer: they explain which review decisions became takeaways, watch items, actions, rejections, or later learning signals.",
    };
  }
  if (activeView === "closed") {
    return {
      title: "Closed Reviews",
      body: "Closed items preserve prior decisions. Use Fit Detail for confirmed takeaways and Records when the reason should inform future thresholds.",
    };
  }
  return {
    title: "Pending Review",
    body: "Start here for candidate triage. Confirm durable project fit, Watch partial evidence, Action only with a concrete owner/date, or Reject weak fit.",
  };
}

function isSignalDetailLinkable(signalId?: string, candidateSource?: string) {
  const normalizedSignalId = String(signalId || "").toLowerCase();
  const normalizedSource = String(candidateSource || "").toLowerCase();
  if (!normalizedSignalId) return false;
  if (normalizedSignalId.startsWith("knowledge-convergence-")) return false;
  if (normalizedSource === "knowledge_convergence") return false;
  return true;
}

function getOutcomeChipStyle(value?: string) {
  const status = (value || "").toLowerCase();
  if (status === "confirmed") {
    return { ...outcomeChipBaseStyle, border: "1px solid #bbf7d0", background: "#f0fdf4", color: "#166534" } as const;
  }
  if (status === "action") {
    return { ...outcomeChipBaseStyle, border: "1px solid #86efac", background: "#dcfce7", color: "#15803d" } as const;
  }
  if (status === "action_completed") {
    return { ...outcomeChipBaseStyle, border: "1px solid #a7f3d0", background: "#ecfdf5", color: "#047857" } as const;
  }
  if (status === "watch") {
    return { ...outcomeChipBaseStyle, border: "1px solid #bae6fd", background: "#f0f9ff", color: "#0369a1" } as const;
  }
  if (status === "rejected") {
    return { ...outcomeChipBaseStyle, border: "1px solid #fecaca", background: "#fff1f2", color: "#be123c" } as const;
  }
  if (status === "dismissed") {
    return { ...outcomeChipBaseStyle, border: "1px solid #e5e7eb", background: "#f9fafb", color: "#4b5563" } as const;
  }
  return outcomeChipBaseStyle;
}

function getItemReviewDisplayOutcome(item: ProjectTakeawayCandidate) {
  const status = (item.status || "").toLowerCase();
  if (status === "action_completed" || item.action_completed_at || item.action_state === "completed") {
    return "action_completed";
  }
  return item.review_outcome || item.status;
}

function getOutcomeChipButtonStyle(value?: string) {
  return {
    ...getOutcomeChipStyle(value),
    cursor: "pointer",
  } as const;
}

function truncateText(value?: string, limit = 420) {
  const text = (value || "").trim();
  if (!text) return "";
  if (text.length <= limit) return text;
  return `${text.slice(0, limit).trim()}...`;
}

function formatRate(value?: number) {
  if (typeof value !== "number" || Number.isNaN(value)) return "0%";
  return `${Math.round(value * 100)}%`;
}

function countValue(counts: Record<string, number> | undefined, key: string) {
  return counts?.[key] || 0;
}

function formatActionList(values?: string[]) {
  if (!values || values.length === 0) return "None";
  return values.map(formatLabel).join(", ");
}

function safeCount(value?: number) {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

function buildProjectTakeawayGateReason({
  blocked,
  status,
  unsupportedCount,
  blockedActions,
  recorded = false,
}: {
  blocked: boolean;
  status: string;
  unsupportedCount: number;
  blockedActions: string[];
  recorded?: boolean;
}) {
  if (blockedActions.includes("project_takeaway_candidate")) {
    return recorded
      ? "Verification explicitly blocked Project Takeaway creation for this record."
      : "Verification explicitly blocks Project Takeaway creation for this insight.";
  }
  if (unsupportedCount > 0) {
    return `${unsupportedCount} unsupported or contradicted claim(s) ${recorded ? "blocked" : "block"} Project Takeaway creation.`;
  }
  if (status === "unsupported" || status === "contradicted") {
    return recorded
      ? "Verification status blocked Project Takeaway creation because the core claim was unsupported or contradicted."
      : "Verification status blocks Project Takeaway creation because the core claim is unsupported or contradicted.";
  }
  if (status === "not_verifiable") {
    return recorded
      ? "Project Takeaway creation was blocked because the source evidence was not traceable enough."
      : "Project Takeaway creation is blocked because the source evidence is not traceable enough.";
  }
  if (blocked) {
    return recorded
      ? "Project Takeaway creation was blocked by verification quality."
      : "Project Takeaway creation is blocked by verification quality.";
  }
  return recorded
    ? "Project Takeaway review was allowed under the recorded verification state."
    : "Project Takeaway review is allowed.";
}

function buildWatchGateReason({
  allowed,
  status,
  inferredCount,
  blockedActions,
  recorded = false,
}: {
  allowed: boolean;
  status: string;
  inferredCount: number;
  blockedActions: string[];
  recorded?: boolean;
}) {
  if (allowed && blockedActions.includes("watch_only")) {
    return recorded
      ? "Watch was allowed, but the metadata also contained a watch block needing reviewer attention."
      : "Watch is allowed, but the metadata also contains a watch block that needs reviewer attention.";
  }
  if (allowed && status === "weakly_supported") {
    return recorded
      ? "Watch was the safer downstream path because evidence was weak but still worth monitoring."
      : "Watch is the safer downstream path because evidence is weak but still worth monitoring.";
  }
  if (allowed && inferredCount > 0) {
    return recorded
      ? `Watch was suggested while ${inferredCount} inferred claim(s) waited for stronger evidence.`
      : `Watch is suggested while ${inferredCount} inferred claim(s) wait for stronger evidence.`;
  }
  if (allowed) {
    return recorded
      ? "Watch was the safer recorded downstream path for limited or partial evidence."
      : "Watch is the safer downstream path for limited or partial evidence.";
  }
  return recorded
    ? "Watch was not explicitly supported by the recorded verification metadata."
    : "Watch is not explicitly supported by the current verification metadata.";
}

function buildLowRiskActionGateReason({
  blocked,
  status,
  unsupportedCount,
  inferredCount,
  blockedActions,
  recorded = false,
}: {
  blocked: boolean;
  status: string;
  unsupportedCount: number;
  inferredCount: number;
  blockedActions: string[];
  recorded?: boolean;
}) {
  if (blockedActions.includes("low_risk_action_candidate")) {
    return recorded
      ? "Verification explicitly blocked low-risk Action; this record was not action-ready."
      : "Verification explicitly blocks low-risk Action; this insight is not action-ready.";
  }
  if (blockedActions.includes("strong_recommendation")) {
    return recorded
      ? "Verification blocked strong recommendations, so low-risk Action needed reviewer caution."
      : "Verification blocks strong recommendations, so low-risk Action needs reviewer caution.";
  }
  if (unsupportedCount > 0) {
    return `${unsupportedCount} unsupported or contradicted claim(s) ${recorded ? "blocked" : "block"} low-risk Action.`;
  }
  if (status === "unsupported" || status === "contradicted") {
    return recorded
      ? "Low-risk Action was blocked because the core claim was unsupported or contradicted."
      : "Low-risk Action is blocked because the core claim is unsupported or contradicted.";
  }
  if (status === "not_verifiable") {
    return recorded
      ? "Low-risk Action was blocked because the source evidence was not traceable enough."
      : "Low-risk Action is blocked because the source evidence is not traceable enough.";
  }
  if (status === "weakly_supported") {
    return recorded
      ? "Low-risk Action was blocked until weak evidence was upgraded or independently confirmed."
      : "Low-risk Action is blocked until weak evidence is upgraded or independently confirmed.";
  }
  if (blocked) {
    return recorded
      ? "Verification quality supported review or watch, but not action."
      : "Verification quality supports review or watch, but not action.";
  }
  if (inferredCount > 0 || status === "partially_verified") {
    return recorded
      ? "Action required reviewer confirmation of inferred or partial claim context."
      : "Action is available only after reviewer confirms the inferred or partial claim context.";
  }
  return recorded ? "Verification did not block low-risk action." : "Verification does not block low-risk action.";
}

function getCandidateActionEligibility(item: ProjectTakeawayCandidate): ActionEligibilitySummary | null {
  if (item.action_eligibility) return normalizeKnowledgeActionEligibility(item, item.action_eligibility);

  const verification = item.verification_metadata || {};
  const verifiedInsight = verification.verified_insight || null;
  const status = (verification.verification_status || verifiedInsight?.status || "").toLowerCase();
  const supportSummary = verification.claim_support_summary || verifiedInsight?.claims?.support_summary || {};
  const allowedActions = verification.allowed_downstream_actions || verifiedInsight?.action_policy?.allowed || [];
  const blockedActions = verification.blocked_downstream_actions || verifiedInsight?.action_policy?.blocked || [];
  const unsupportedCount = safeCount(supportSummary.unsupported) + safeCount(supportSummary.contradicted);
  const inferredCount = safeCount(supportSummary.inferred);

  if (!status && allowedActions.length === 0 && blockedActions.length === 0 && Object.keys(supportSummary).length === 0) {
    return null;
  }

  const projectBlocked =
    blockedActions.includes("project_takeaway_candidate") ||
    ["unsupported", "contradicted", "not_verifiable"].includes(status) ||
    unsupportedCount > 0;
  const actionBlocked =
    blockedActions.includes("low_risk_action_candidate") ||
    ["unsupported", "contradicted", "not_verifiable", "weakly_supported"].includes(status) ||
    unsupportedCount > 0;
  const watchAllowed =
    allowedActions.includes("watch_only") ||
    allowedActions.includes("project_takeaway_candidate") ||
    ["partially_verified", "verified", "verified_with_limitations", "weakly_supported"].includes(status);

  return normalizeKnowledgeActionEligibility(item, {
    project_takeaway_candidate: {
      allowed: !projectBlocked,
      reason: buildProjectTakeawayGateReason({
        blocked: projectBlocked,
        status,
        unsupportedCount,
        blockedActions,
      }),
    },
    watch_only: {
      allowed: watchAllowed,
      reason: buildWatchGateReason({
        allowed: watchAllowed,
        status,
        inferredCount,
        blockedActions,
      }),
    },
    low_risk_action_candidate: {
      allowed: !actionBlocked,
      reason: buildLowRiskActionGateReason({
        blocked: actionBlocked,
        status,
        unsupportedCount,
        inferredCount,
        blockedActions,
      }),
    },
    signals: {
      verification_status: status,
      unsupported_or_contradicted_claim_count: unsupportedCount,
      inferred_claim_count: inferredCount,
      allowed_downstream_actions: allowedActions,
      blocked_downstream_actions: blockedActions,
    },
  });
}

function gateValue(decision?: EligibilityDecision) {
  if (!decision) return "Not recorded";
  return decision.allowed === false ? "Blocked" : "Allowed";
}

function gateTone(decision?: EligibilityDecision): VerifiedInsightObjectRow["tone"] {
  if (!decision) return "neutral";
  return decision.allowed === false ? "bad" : "good";
}

function verificationObjectTone(status: string, blockedActions: string[]): VerifiedInsightObjectRow["tone"] {
  if (blockedActions.includes("low_risk_action_candidate") || ["unsupported", "contradicted", "not_verifiable"].includes(status)) {
    return "bad";
  }
  if (["partially_verified", "weakly_supported", "needs_review"].includes(status)) return "watch";
  if (["verified", "verified_with_limitations", "supported"].includes(status)) return "good";
  return "neutral";
}

function buildVerifiedInsightObjectRows(
  verification: NonNullable<ProjectTakeawayCandidate["verification_metadata"]>,
  actionEligibility: ActionEligibilitySummary | null
): VerifiedInsightObjectRow[] {
  const verifiedInsight = verification.verified_insight || null;
  const supportSummary = verification.claim_support_summary || verifiedInsight?.claims?.support_summary || {};
  const blockedActions =
    actionEligibility?.signals?.blocked_downstream_actions ||
    verification.blocked_downstream_actions ||
    verifiedInsight?.action_policy?.blocked ||
    [];
  const status = (
    actionEligibility?.signals?.verification_status ||
    verification.verification_status ||
    verifiedInsight?.status ||
    ""
  ).toLowerCase();
  const claimCount = Object.values(supportSummary).reduce((total, count) => total + safeCount(count), 0);
  const unsupportedCount = safeCount(supportSummary.unsupported) + safeCount(supportSummary.contradicted);
  const projectTakeawayGate = actionEligibility?.project_takeaway_candidate;
  const actionGate = actionEligibility?.low_risk_action_candidate;

  return [
    {
      label: "Verification",
      value: formatLabel(status) || "Not recorded",
      detail: "Existing verification_status or verified_insight.status.",
      tone: verificationObjectTone(status, blockedActions),
    },
    {
      label: "Confidence",
      value: formatConfidence(verification.confidence_label, verification.confidence_score),
      detail: "Confidence metadata is descriptive, not a gate override.",
      tone: verification.confidence_label?.toLowerCase() === "low" ? "watch" : "neutral",
    },
    {
      label: "Claims",
      value: claimCount > 0 ? `${claimCount} checked` : "Not checked",
      detail: formatClaimSupport(supportSummary) || "No claim-support summary is attached.",
      tone: unsupportedCount > 0 ? "bad" : claimCount > 0 ? "good" : "neutral",
    },
    {
      label: "Project Takeaway",
      value: gateValue(projectTakeawayGate),
      detail: projectTakeawayGate?.reason || "No Project Takeaway gate reason recorded.",
      tone: gateTone(projectTakeawayGate),
    },
    {
      label: "Low-risk Action",
      value: gateValue(actionGate),
      detail: actionGate?.reason || "No Action gate reason recorded.",
      tone: gateTone(actionGate),
    },
  ];
}

function hasVerifiedInsightObjectSurface(
  verification: NonNullable<ProjectTakeawayCandidate["verification_metadata"]>,
  actionEligibility: ActionEligibilitySummary | null
) {
  return Boolean(
    verification.verified_insight ||
      verification.verification_status ||
      verification.confidence_label ||
      verification.claim_support_summary ||
      verification.allowed_downstream_actions?.length ||
      verification.blocked_downstream_actions?.length ||
      actionEligibility
  );
}

function buildRecordVerifiedInsightObjectRows(
  record: ProjectReviewRecord,
  actionEligibility: ActionEligibilitySummary | null
): VerifiedInsightObjectRow[] {
  const supportSummary = record.claim_support_summary || {};
  const status = (actionEligibility?.signals?.verification_status || record.verification_status || "").toLowerCase();
  const blockedActions = actionEligibility?.signals?.blocked_downstream_actions || record.blocked_downstream_actions || [];
  const claimCount =
    Object.values(supportSummary).reduce((total, count) => total + safeCount(count), 0) ||
    safeCount(record.unsupported_claim_count) +
      safeCount(record.inferred_claim_count);
  const unsupportedCount =
    safeCount(record.unsupported_claim_count) ||
    safeCount(supportSummary.unsupported) + safeCount(supportSummary.contradicted);
  const actionGate = actionEligibility?.low_risk_action_candidate;

  return [
    {
      label: "Outcome",
      value: formatLabel(record.outcome) || "Not recorded",
      detail: "Recorded Project Review outcome; this is review history, not a new gate.",
      tone: ["confirmed", "action", "action_completed"].includes((record.outcome || "").toLowerCase())
        ? "good"
        : (record.outcome || "").toLowerCase() === "watch"
          ? "watch"
          : ["rejected", "dismissed"].includes((record.outcome || "").toLowerCase())
            ? "bad"
            : "neutral",
    },
    {
      label: "Verification",
      value: formatLabel(status) || "Not recorded",
      detail: "Recorded verification_status from the review event.",
      tone: verificationObjectTone(status, blockedActions),
    },
    {
      label: "Confidence",
      value: formatConfidence(record.confidence_label, record.confidence_score),
      detail: "Confidence metadata is preserved as review context only.",
      tone: record.confidence_label?.toLowerCase() === "low" ? "watch" : "neutral",
    },
    {
      label: "Claims",
      value: claimCount > 0 ? `${claimCount} recorded` : "Not recorded",
      detail: formatClaimSupport(supportSummary) || `Unsupported ${record.unsupported_claim_count || 0}, inferred ${record.inferred_claim_count || 0}.`,
      tone: unsupportedCount > 0 ? "bad" : claimCount > 0 ? "good" : "neutral",
    },
    {
      label: "Low-risk Action",
      value: gateValue(actionGate),
      detail: actionGate?.reason || "No Action gate reason recorded.",
      tone: gateTone(actionGate),
    },
  ];
}

function hasRecordVerifiedInsightObjectSurface(record: ProjectReviewRecord, actionEligibility: ActionEligibilitySummary | null) {
  return Boolean(
    record.outcome ||
      record.verification_status ||
      record.confidence_label ||
      record.claim_support_summary ||
      record.blocked_downstream_actions?.length ||
      actionEligibility
  );
}

function normalizeKnowledgeActionEligibility(
  item: ProjectTakeawayCandidate,
  actionEligibility: ActionEligibilitySummary
): ActionEligibilitySummary {
  if (!isKnowledgeConvergenceCandidate(item)) return actionEligibility;
  const verification = item.verification_metadata || {};
  const blockedActions = Array.from(
    new Set([
      ...(actionEligibility.signals?.blocked_downstream_actions || []),
      ...(verification.blocked_downstream_actions || []),
      "low_risk_action_candidate",
      "strong_recommendation",
    ])
  );
  return {
    ...actionEligibility,
    low_risk_action_candidate: {
      allowed: false,
      reason:
        actionEligibility.low_risk_action_candidate?.reason?.includes("Knowledge convergence")
          ? actionEligibility.low_risk_action_candidate.reason
          : "Knowledge convergence is review context only; low-risk Action requires explicit human override.",
    },
    signals: {
      ...(actionEligibility.signals || {}),
      verification_status:
        actionEligibility.signals?.verification_status ||
        verification.verification_status ||
        "knowledge_convergence_review_candidate",
      allowed_downstream_actions:
        actionEligibility.signals?.allowed_downstream_actions ||
        verification.allowed_downstream_actions ||
        ["project_takeaway_candidate"],
      blocked_downstream_actions: blockedActions,
    },
  };
}

function getRecordActionEligibility(record: ProjectReviewRecord): ActionEligibilitySummary | null {
  if (record.action_eligibility) return record.action_eligibility;

  const status = (record.verification_status || "").toLowerCase();
  const blockedActions = record.blocked_downstream_actions || [];
  const allowedActions = record.allowed_downstream_actions || [];
  const supportSummary = record.claim_support_summary || {};
  const unsupportedCount = safeCount(record.unsupported_claim_count) || safeCount(supportSummary.unsupported) + safeCount(supportSummary.contradicted);
  const inferredCount = safeCount(record.inferred_claim_count) || safeCount(supportSummary.inferred);

  if (!status && blockedActions.length === 0 && allowedActions.length === 0 && unsupportedCount === 0 && inferredCount === 0) {
    return null;
  }

  const projectBlocked =
    blockedActions.includes("project_takeaway_candidate") ||
    ["unsupported", "contradicted", "not_verifiable"].includes(status) ||
    unsupportedCount > 0;
  const actionBlocked =
    blockedActions.includes("low_risk_action_candidate") ||
    ["unsupported", "contradicted", "not_verifiable", "weakly_supported"].includes(status) ||
    unsupportedCount > 0;
  const watchAllowed =
    allowedActions.includes("watch_only") ||
    allowedActions.includes("project_takeaway_candidate") ||
    ["partially_verified", "verified", "verified_with_limitations", "weakly_supported"].includes(status);

  return {
    project_takeaway_candidate: {
      allowed: !projectBlocked,
      reason: buildProjectTakeawayGateReason({
        blocked: projectBlocked,
        status,
        unsupportedCount,
        blockedActions,
        recorded: true,
      }),
    },
    watch_only: {
      allowed: watchAllowed,
      reason: buildWatchGateReason({
        allowed: watchAllowed,
        status,
        inferredCount,
        blockedActions,
        recorded: true,
      }),
    },
    low_risk_action_candidate: {
      allowed: !actionBlocked,
      reason: buildLowRiskActionGateReason({
        blocked: actionBlocked,
        status,
        unsupportedCount,
        inferredCount,
        blockedActions,
        recorded: true,
      }),
    },
    signals: {
      verification_status: status,
      unsupported_or_contradicted_claim_count: unsupportedCount,
      inferred_claim_count: inferredCount,
      allowed_downstream_actions: allowedActions,
      blocked_downstream_actions: blockedActions,
    },
  };
}

function isRecordActionBlocked(record: ProjectReviewRecord) {
  const actionEligibility = getRecordActionEligibility(record);
  if (actionEligibility?.low_risk_action_candidate?.allowed === false) return true;
  return (record.blocked_downstream_actions || []).includes("low_risk_action_candidate");
}

function isActionOutcome(record: ProjectReviewRecord) {
  return ["action", "action_completed"].includes((record.outcome || "").toLowerCase());
}

function hasRecordGateConflict(record: ProjectReviewRecord) {
  return isRecordActionBlocked(record) && (isActionOutcome(record) || Boolean(record.manual_project_takeaway_override));
}

function hasWatchWithActionBlocked(record: ProjectReviewRecord) {
  return isRecordActionBlocked(record) && (record.outcome || "").toLowerCase() === "watch";
}

function formatConfidence(label?: string, score?: number | null) {
  const cleanLabel = label ? formatLabel(label) : "";
  if (typeof score === "number" && !Number.isNaN(score)) {
    return cleanLabel ? `${cleanLabel} (${score.toFixed(2)})` : score.toFixed(2);
  }
  return cleanLabel || "n/a";
}

function topCountLabel(counts?: Record<string, number>, fallback = "None") {
  const top = Object.entries(counts || {})
    .filter(([, count]) => count > 0)
    .sort((left, right) => right[1] - left[1])[0];
  return top ? `${formatLabel(top[0])} (${top[1]})` : fallback;
}

function normalizeRecordText(value?: string) {
  return (value || "").trim().toLowerCase();
}

function isManualReviewRecord(record: ProjectReviewRecord) {
  const sourceType = normalizeRecordText(record.source_type);
  const sourceStatus = normalizeRecordText(record.source_status);
  const candidateSource = normalizeRecordText(record.candidate_source);
  const signalId = normalizeRecordText(record.signal_id);
  const signalTitle = normalizeRecordText(record.signal_title);

  return Boolean(
    record.is_manual_source ||
      record.manual_session_id ||
      sourceType === "manual" ||
      sourceType === "manual_upload" ||
      sourceType === "manual upload" ||
      sourceStatus === "manual" ||
      candidateSource.includes("manual") ||
      signalId.startsWith("manual_") ||
      signalId.startsWith("manual-") ||
      signalTitle.startsWith("manual session"),
  );
}

function getManualSessionLabel(record: ProjectReviewRecord) {
  if (record.manual_session_id) return record.manual_session_id;

  const signalTitle = record.signal_title || "";
  const sessionTitleMatch = signalTitle.match(/manual session\s*\(([^)]+)\)/i);
  if (sessionTitleMatch?.[1]) return sessionTitleMatch[1];

  const signalId = record.signal_id || "";
  if (/^manual[-_]/i.test(signalId)) return signalId;

  return "";
}

function formatRecordSource(record: ProjectReviewRecord) {
  if (isManualReviewRecord(record)) {
    const manualSession = getManualSessionLabel(record);
    return manualSession ? `Manual Upload (${manualSession})` : "Manual Upload";
  }
  if (record.source_type && normalizeRecordText(record.source_type) !== "signal") return formatLabel(record.source_type);
  return "Collected Signal";
}

function buildReviewOpsInterpretation(summary: ProjectReviewSummary) {
  const total = summary.total_records || 0;
  if (total === 0) {
    return {
      achieved: "No review records exist yet.",
      gap: "Review quality cannot be interpreted until at least one decision is recorded.",
      next: "Create or review Project Takeaway candidates to start building a review-quality baseline.",
    };
  }

  const blockedRate = formatRate(summary.blocked_action_rate);
  const dominantBlockedAction = topCountLabel(summary.blocked_action_counts);
  const dominantVerificationStatus = topCountLabel(summary.verification_status_counts, "Unknown");
  const manualSourceLine = (summary.manual_record_count || 0) > 0
    ? `Manual uploads contributed ${summary.manual_record_count} review record(s), with ${summary.manual_watch_count || 0} watch item(s) and ${summary.manual_actionable_count || 0} actionable outcome(s).`
    : "No manual-upload review records are visible yet.";
  const riskSignals = [];
  if ((summary.low_confidence_count || 0) > 0) riskSignals.push(`${summary.low_confidence_count} low-confidence record(s)`);
  if ((summary.unsupported_claim_count || 0) > 0) riskSignals.push(`${summary.unsupported_claim_count} unsupported claim(s)`);
  if ((summary.inferred_claim_count || 0) > 0) riskSignals.push(`${summary.inferred_claim_count} inferred claim(s)`);
  if ((summary.records_with_blocked_actions || 0) > 0) riskSignals.push(`${summary.records_with_blocked_actions} record(s) with blocked actions`);
  if ((summary.gate_conflict_record_count || 0) > 0) riskSignals.push(`${summary.gate_conflict_record_count} action gate conflict(s)`);

  return {
    achieved: `${summary.actionable_count || 0} of ${total} review record(s) became actionable, with ${summary.watch_count || 0} watch item(s) preserved for later review.`,
    gap: riskSignals.length
      ? `Current review risk is concentrated in ${riskSignals.join(", ")}. Dominant verification status: ${dominantVerificationStatus}. Blocked action rate: ${blockedRate}.`
      : `No verification risk signals are currently visible in review records. Dominant verification status: ${dominantVerificationStatus}. ${manualSourceLine}`,
    next: (summary.gate_conflict_record_count || 0) > 0
      ? "Review gate conflicts before treating overridden or actioned records as calibration-positive examples."
      : (summary.records_with_blocked_actions || 0) > 0
        ? `Inspect blocked action mix, especially ${dominantBlockedAction}, before promoting more records into action.`
      : "Continue monitoring whether future watch/action decisions introduce blocked action or low-confidence patterns.",
  };
}

function buildCalibrationOpsInterpretation(summary: ProjectCalibrationSummary) {
  const total = summary.total_events || 0;
  if (total === 0) {
    return {
      achieved: "No calibration events exist yet.",
      gap: "Learning signals are unavailable until review outcomes emit calibration events.",
      next: "Process more candidate reviews so calibration can compare review outcomes against verification quality.",
    };
  }

  const dominantBlockedAction = topCountLabel(summary.blocked_action_counts);
  const dominantVerificationStatus = topCountLabel(summary.verification_status_counts, "Unknown");
  const blockedRate = formatRate(summary.blocked_action_rate);
  const manualSourceLine = (summary.manual_event_count || 0) > 0
    ? `Manual uploads contributed ${summary.manual_event_count} calibration event(s), including ${summary.manual_watch_event_count || 0} watch event(s) and ${summary.manual_actionable_event_count || 0} actionable event(s).`
    : "No manual-upload calibration events are visible yet.";
  const riskSignals = [];
  if ((summary.low_confidence_event_count || 0) > 0) riskSignals.push(`${summary.low_confidence_event_count} low-confidence event(s)`);
  if ((summary.unsupported_claim_count || 0) > 0) riskSignals.push(`${summary.unsupported_claim_count} unsupported claim(s)`);
  if ((summary.inferred_claim_count || 0) > 0) riskSignals.push(`${summary.inferred_claim_count} inferred claim(s)`);
  if ((summary.events_with_blocked_actions || 0) > 0) riskSignals.push(`${summary.events_with_blocked_actions} event(s) with blocked actions`);
  if ((summary.gate_conflict_event_count || 0) > 0) riskSignals.push(`${summary.gate_conflict_event_count} action gate conflict event(s)`);

  return {
    achieved: `${summary.candidate_review_event_count || 0} candidate review event(s) have produced an actionable rate of ${formatRate(summary.candidate_to_actionable_rate)}.`,
    gap: riskSignals.length
      ? `Calibration risk is currently shaped by ${riskSignals.join(", ")}. Dominant verification status: ${dominantVerificationStatus}. Blocked event rate: ${blockedRate}.`
      : `Calibration events do not currently show verification-risk pressure. Dominant verification status: ${dominantVerificationStatus}. ${manualSourceLine}`,
    next: (summary.gate_conflict_event_count || 0) > 0
      ? "Compare gate-conflict events with their ReviewRecords before using them as positive learning examples."
      : (summary.events_with_blocked_actions || 0) > 0
        ? `Use the blocked action mix, especially ${dominantBlockedAction}, to tune watch/action thresholds and review prompts.`
      : "Keep collecting calibration events so acceptance/rejection patterns can be compared against evidence quality.",
  };
}

function buildGateComparison(recordSummary: ProjectReviewSummary, calibrationSummary: ProjectCalibrationSummary) {
  const recordConflicts = recordSummary.gate_conflict_record_count || 0;
  const calibrationConflicts = calibrationSummary.gate_conflict_event_count || 0;
  const conflictDelta = calibrationConflicts - recordConflicts;
  const recordActionBlocked = recordSummary.records_with_action_blocked || 0;
  const calibrationActionBlocked = calibrationSummary.events_with_action_blocked || 0;
  const recordWatchBlocked = recordSummary.watch_outcomes_with_action_blocked || 0;
  const calibrationWatchBlocked = calibrationSummary.watch_events_with_action_blocked || 0;
  const recordActionConflict = recordSummary.action_outcomes_with_blocked_gate || 0;
  const calibrationActionConflict = calibrationSummary.action_events_with_blocked_gate || 0;
  const recordOverrideConflict = recordSummary.manual_overrides_with_blocked_action || 0;
  const calibrationOverrideConflict = calibrationSummary.manual_overrides_with_blocked_action || 0;

  const alignment =
    conflictDelta === 0
      ? "Aligned"
      : conflictDelta > 0
        ? "Calibration has extra conflicts"
        : "Records have extra conflicts";
  const next =
    conflictDelta === 0
      ? "Use the matching conflict counts as a stable review-quality baseline."
      : conflictDelta > 0
        ? "Inspect calibration event duplication or backfilled review-record-created events before treating the learning signal as final."
        : "Inspect missing or stale calibration events before using ReviewRecords as the only source of learning truth.";

  return {
    alignment,
    next,
    recordConflicts,
    calibrationConflicts,
    conflictDelta,
    recordActionBlocked,
    calibrationActionBlocked,
    recordWatchBlocked,
    calibrationWatchBlocked,
    recordActionConflict,
    calibrationActionConflict,
    recordOverrideConflict,
    calibrationOverrideConflict,
  };
}

function buildReviewCalibrationActions(
  recordSummary: ProjectReviewSummary,
  calibrationSummary?: ProjectCalibrationSummary | null,
) {
  const actions = [];
  const gateConflicts =
    (recordSummary.gate_conflict_record_count || 0) + (calibrationSummary?.gate_conflict_event_count || 0);
  const actionBlocked =
    (recordSummary.records_with_action_blocked || 0) + (calibrationSummary?.events_with_action_blocked || 0);
  const watchBlocked =
    (recordSummary.watch_outcomes_with_action_blocked || 0) + (calibrationSummary?.watch_events_with_action_blocked || 0);
  const manualRoute =
    (recordSummary.manual_record_count || 0) + (calibrationSummary?.manual_event_count || 0);

  if (gateConflicts > 0) {
    actions.push({
      label: "Inspect Gate Conflicts",
      detail: `${gateConflicts} record/calibration conflict(s) need review before they become learning examples.`,
    });
  }
  if (actionBlocked > 0) {
    actions.push({
      label: "Audit Action Blocks",
      detail: `${actionBlocked} blocked action signal(s) should stay out of ordinary Action until evidence improves.`,
    });
  }
  if (watchBlocked > 0) {
    actions.push({
      label: "Promote Watch Discipline",
      detail: `${watchBlocked} Watch item(s) have blocked downstream action, so Watch is the intended safe holding state.`,
    });
  }
  if (manualRoute > 0) {
    actions.push({
      label: "Check Manual Route",
      detail: `${manualRoute} manual item(s) should retain explicit source intent and completion audit context.`,
    });
  }

  return actions.length
    ? actions
    : [
        {
          label: "Continue Baseline",
          detail: "No visible gate conflicts or manual-route pressure; keep using the current review thresholds.",
        },
      ];
}

function buildManualSourceLearningSummary(
  recordSummary: ProjectReviewSummary,
  calibrationSummary?: ProjectCalibrationSummary | null,
) {
  const manualRecords = recordSummary.manual_record_count || 0;
  const manualEvents = calibrationSummary?.manual_event_count || 0;
  const manualWatch = (recordSummary.manual_watch_count || 0) + (calibrationSummary?.manual_watch_event_count || 0);
  const manualActionable =
    (recordSummary.manual_actionable_count || 0) + (calibrationSummary?.manual_actionable_event_count || 0);
  const manualTotal = manualRecords + manualEvents;
  const gateConflicts =
    (recordSummary.gate_conflict_record_count || 0) + (calibrationSummary?.gate_conflict_event_count || 0);
  const actionBlocked =
    (recordSummary.records_with_action_blocked || 0) + (calibrationSummary?.events_with_action_blocked || 0);

  if (manualTotal === 0) {
    return {
      hasManualLearning: false,
      achieved: "No manual-upload review learning has been recorded yet.",
      gap: "Manual material is not contributing to review calibration in this scope.",
      next: "Complete a manual-upload-derived review to start comparing human-selected material with collected signals.",
      manualRecords,
      manualEvents,
      manualWatch,
      manualActionable,
    };
  }

  const achieved =
    manualEvents > 0
      ? `${manualRecords} manual review record(s) and ${manualEvents} calibration event(s) are now visible in the learning loop.`
      : `${manualRecords} manual review record(s) exist; calibration events have not caught up yet.`;
  const gap =
    gateConflicts > 0 || actionBlocked > 0
      ? `${gateConflicts} gate conflict(s) and ${actionBlocked} action-blocked signal(s) still need review discipline.`
      : "No visible gate-conflict pressure is attached to the current manual-source learning.";
  const next =
    manualActionable > 0
      ? "Compare manual actionable outcomes with ordinary signal outcomes before treating them as reusable project patterns."
      : manualWatch > 0
        ? "Keep manual Watch outcomes under observation until evidence quality supports a stronger route."
        : "Use the next manual review decision to test whether this material should become Watch, Action, or a rejected learning example.";

  return {
    hasManualLearning: true,
    achieved,
    gap,
    next,
    manualRecords,
    manualEvents,
    manualWatch,
    manualActionable,
  };
}

function buildKnowledgeOperatingSummary(items: ProjectTakeawayCandidate[]) {
  const knowledgeItems = items.filter(isKnowledgeConvergenceCandidate);
  const strongFitCount = knowledgeItems.filter((item) => {
    const verification = item.verification_metadata || {};
    const score = verification.quality?.score ?? verification.evidence_profile?.quality_score ?? 0;
    const projectCount = getKnowledgeProjectMatchCount(item);
    return score >= 70 && projectCount > 0;
  }).length;
  const actionBlockedCount = knowledgeItems.filter((item) => {
    const eligibility = getCandidateActionEligibility(item);
    return eligibility?.low_risk_action_candidate?.allowed === false;
  }).length;
  const watchReadyCount = knowledgeItems.filter((item) => {
    const eligibility = getCandidateActionEligibility(item);
    return eligibility?.watch_only?.allowed !== false;
  }).length;
  const missingProjectFitCount = knowledgeItems.filter(isKnowledgeMissingProjectFitCandidate).length;

  const posture =
    knowledgeItems.length === 0
      ? "No pending Knowledge Fit review"
      : actionBlockedCount > 0
        ? "Watch-first posture"
        : strongFitCount > 0
          ? "Confirm-review candidates available"
          : "Evidence-fit triage";
  const next =
    knowledgeItems.length === 0
      ? "Keep Knowledge Fit available, but spend review time on records/calibration pressure first."
      : actionBlockedCount > 0
        ? "Open the Knowledge Fit queue and keep action-blocked convergence items in Watch unless a human override is justified."
        : strongFitCount > 0
          ? "Review the strongest fit candidates for Confirm after checking linked supply and demand evidence."
          : "Use Watch or Reject until project match and evidence quality become explicit.";

  return {
    total: knowledgeItems.length,
    strongFitCount,
    actionBlockedCount,
    watchReadyCount,
    missingProjectFitCount,
    posture,
    next,
  };
}

function buildMetricsOperatingSummary(
  recordSummary: ProjectReviewSummary,
  calibrationSummary?: ProjectCalibrationSummary | null,
) {
  const recordCount = recordSummary.total_records || 0;
  const calibrationCount = calibrationSummary?.total_events || 0;
  const latest = calibrationSummary?.latest_event_at || recordSummary.latest_reviewed_at || "n/a";
  const needsCalibrationRun = calibrationCount === 0 || calibrationCount < recordCount;
  const posture =
    calibrationCount === 0
      ? "Waiting for calibration data"
      : needsCalibrationRun
        ? "Check calibration freshness"
        : "Calibration data aligned";
  const next =
    calibrationCount === 0
      ? "After the next pipeline run, confirm Admin Metrics shows production-backed artifacts before interpreting trend quality."
      : needsCalibrationRun
        ? "Open Admin Metrics and compare the latest production artifact time against the newest review record."
        : "Use Admin Metrics as the production source for follow-up calibration checks.";

  return {
    recordCount,
    calibrationCount,
    latest,
    posture,
    next,
  };
}

function buildReviewLoopFollowupSummary({
  watchItems,
  actionItems,
  closedItems,
  recordSummary,
  calibrationSummary,
}: {
  watchItems: ProjectTakeawayCandidate[];
  actionItems: ProjectTakeawayCandidate[];
  closedItems: ProjectTakeawayCandidate[];
  recordSummary?: ProjectReviewSummary | null;
  calibrationSummary?: ProjectCalibrationSummary | null;
}): ReviewLoopFollowupSummary {
  const watchDueCount = watchItems.filter((item) => isDateDue(item.watch_review_date)).length;
  const watchMissingPlanCount = watchItems.filter(
    (item) => !item.watch_review_date || !item.watch_success_criteria || !item.watch_status,
  ).length;
  const actionDueCount = actionItems.filter((item) => isDateDue(item.action_due_date || item.action_review_date)).length;
  const actionMissingPlanCount = actionItems.filter(
    (item) => !item.action_due_date || !item.action_review_date || !item.action_expected_outcome,
  ).length;
  const actionCompletedCount =
    closedItems.filter((item) => (item.status || "").toLowerCase() === "action_completed").length ||
    countValue(recordSummary?.outcome_counts, "action_completed");
  const learningRecordCount = recordSummary?.total_records || 0;
  const calibrationEventCount = calibrationSummary?.total_events || 0;
  const gateConflictCount =
    (recordSummary?.gate_conflict_record_count || 0) + (calibrationSummary?.gate_conflict_event_count || 0);
  const manualLearningCount =
    (recordSummary?.manual_record_count || 0) + (calibrationSummary?.manual_event_count || 0);

  let nextFocus = "Review pending candidates; use Watch for partial evidence and Action only for concrete dated work.";
  if (watchDueCount > 0) {
    nextFocus = "Review due Watch items first; either promote, reject, or reset the watch criteria.";
  } else if (watchMissingPlanCount > 0) {
    nextFocus = "Clean up Watch items without review dates, status, or success criteria.";
  } else if (actionDueCount > 0) {
    nextFocus = "Check due Action items and complete them only with an outcome note.";
  } else if (actionMissingPlanCount > 0) {
    nextFocus = "Fill Action due dates, review dates, and expected outcomes before treating them as operational work.";
  } else if (gateConflictCount > 0) {
    nextFocus = "Inspect gate conflicts in Records before creating more override-driven outcomes.";
  } else if (learningRecordCount || calibrationEventCount) {
    nextFocus = "Use Records to compare outcomes against calibration before adding more process.";
  }

  return {
    watchDueCount,
    watchMissingPlanCount,
    actionDueCount,
    actionMissingPlanCount,
    actionCompletedCount,
    learningRecordCount,
    calibrationEventCount,
    gateConflictCount,
    manualLearningCount,
    nextFocus,
  };
}

function formatLearningProfileTopCount(items?: LearningProfileCount[]) {
  const first = (items || []).find((item) => item.key && (item.count || 0) > 0);
  if (!first) return "None";
  return `${formatLabel(first.key)} ${first.count || 0}`;
}

function buildLearningProfilePosture(profile?: ProjectLearningProfile | null) {
  const signals = profile?.learning_signals || {};
  const focus = (profile?.next_focus || []).find((item) => item.trim()) || "";

  if (!profile) {
    return {
      label: "Waiting for profile",
      body: "Review Inbox can still be used while learning context loads.",
      focus: "Load ReviewRecords and calibration history before interpreting project learning posture.",
    };
  }
  if (signals.has_gate_risk) {
    return {
      label: "Gate Risk Visible",
      body: "Review blocked-action and gate-conflict memory before treating past outcomes as low-risk action context.",
      focus,
    };
  }
  if (signals.has_watch_memory) {
    return {
      label: "Watch Memory Active",
      body: "Watch outcomes are available as learning memory, but they still need follow-up evidence before promotion.",
      focus,
    };
  }
  if (signals.has_actionable_memory) {
    return {
      label: "Actionable Memory Present",
      body: "Confirmed and action outcomes exist; use them as project learning context, not automatic external evidence.",
      focus,
    };
  }
  return {
    label: "Learning Context Building",
    body: "The profile is read-only and becomes more useful as ReviewRecords and calibration events accumulate.",
    focus,
  };
}

function buildRecordCardSummary(record: ProjectReviewRecord) {
  const riskParts = [];
  if ((record.unsupported_claim_count || 0) > 0) riskParts.push(`${record.unsupported_claim_count} unsupported`);
  if ((record.inferred_claim_count || 0) > 0) riskParts.push(`${record.inferred_claim_count} inferred`);
  if (Array.isArray(record.blocked_downstream_actions) && record.blocked_downstream_actions.length > 0) {
    riskParts.push(`${record.blocked_downstream_actions.length} blocked action(s)`);
  }

  const verification = record.verification_status ? formatLabel(record.verification_status) : "No verification status";
  const confidence = formatConfidence(record.confidence_label, record.confidence_score);
  const risk = riskParts.length ? riskParts.join(", ") : "no visible claim/action risk";
  const source = record.manual_project_takeaway_override
    ? "Manual override"
    : isManualReviewRecord(record) ? "Manual upload" : "Collected signal";
  const reason = record.reason ? truncateText(record.reason, 140) : "No review reason recorded";
  const overrideNote = record.manual_project_takeaway_override && record.manual_override_note
    ? ` Override note: ${truncateText(record.manual_override_note, 120)}`
    : "";

  return `${source} / ${verification} / Confidence: ${confidence} / Risk: ${risk}. ${reason}${overrideNote}`;
}

function isActionReviewRecord(record: ProjectReviewRecord) {
  const outcome = (record.outcome || "").toLowerCase();
  return outcome.includes("action") || outcome === "confirmed";
}

function isWatchReviewRecord(record: ProjectReviewRecord) {
  return (record.outcome || "").toLowerCase().includes("watch");
}

function hasReviewRecordRisk(record: ProjectReviewRecord) {
  return (
    (record.unsupported_claim_count || 0) > 0 ||
    (record.inferred_claim_count || 0) > 0 ||
    (Array.isArray(record.blocked_downstream_actions) && record.blocked_downstream_actions.length > 0) ||
    (record.confidence_label || "").toLowerCase() === "low" ||
    ["not_verifiable", "weakly_supported", "partially_verified"].includes((record.verification_status || "").toLowerCase())
  );
}

function buildRecordImportance(record: ProjectReviewRecord) {
  if (record.manual_project_takeaway_override) {
    return "Human override changed the normal gate, so this record should stay visible when reviewing judgment quality.";
  }
  if (isActionReviewRecord(record)) {
    return "This record created or completed an action path, so it is part of the project's execution history.";
  }
  if (isWatchReviewRecord(record)) {
    return "This record preserved a watch decision, so it is useful for later review without forcing premature action.";
  }
  if (hasReviewRecordRisk(record)) {
    return "This record carries verification risk and should not be treated as clean evidence without review.";
  }
  return "This record captures a completed project-review judgment and contributes to the review-quality baseline.";
}

function buildManualOverrideCalibration(records: ProjectReviewRecord[]): ManualOverrideCalibration {
  const manualRecords = records.filter((record) => record.manual_project_takeaway_override);
  const outcomeCounts = manualRecords.reduce<Record<string, number>>((counts, record) => {
    const outcome = (record.outcome || "unknown").toLowerCase();
    counts[outcome] = (counts[outcome] || 0) + 1;
    return counts;
  }, {});
  const total = manualRecords.length;
  const actionableCount =
    countValue(outcomeCounts, "confirmed") +
    countValue(outcomeCounts, "action") +
    countValue(outcomeCounts, "action_completed");
  const rejectedOrDismissedCount = countValue(outcomeCounts, "rejected") + countValue(outcomeCounts, "dismissed");
  const latestReviewedAt = manualRecords
    .map((record) => record.reviewed_at || record.updated_at || "")
    .filter(Boolean)
    .sort((left, right) => right.localeCompare(left))[0] || "";

  return {
    total,
    outcomeCounts,
    actionableCount,
    watchCount: countValue(outcomeCounts, "watch"),
    rejectedOrDismissedCount,
    riskCount: manualRecords.filter(hasReviewRecordRisk).length,
    blockedActionCount: manualRecords.filter((record) =>
      Array.isArray(record.blocked_downstream_actions) && record.blocked_downstream_actions.length > 0
    ).length,
    actionCompletedCount: countValue(outcomeCounts, "action_completed"),
    actionableRate: total > 0 ? actionableCount / total : 0,
    rejectionRate: total > 0 ? rejectedOrDismissedCount / total : 0,
    latestReviewedAt,
  };
}

function buildManualOverrideCalibrationInterpretation(summary: ManualOverrideCalibration) {
  if (summary.total === 0) {
    return {
      achieved: "No manual override review records exist yet.",
      gap: "The system cannot learn whether human gate-bypasses are useful until overrides receive review outcomes.",
      next: "When a blocked candidate is manually promoted, finish it through Confirm, Watch, Action, Reject, or Dismiss so it becomes calibration data.",
    };
  }

  const completionLine = summary.actionCompletedCount > 0
    ? `${summary.actionCompletedCount} override-backed action(s) have been completed, which is the strongest evidence that bypassing the original gate produced value.`
    : "No override-backed action has been completed yet, so the calibration signal is still mostly intent rather than proven outcome.";
  const riskLine = summary.riskCount > 0
    ? `${summary.riskCount} override record(s) still carry verification risk, including ${summary.blockedActionCount} with blocked downstream actions.`
    : "No visible verification-risk flags are attached to current manual override records.";
  const nextLine = summary.rejectedOrDismissedCount >= summary.actionableCount && summary.rejectedOrDismissedCount > 0
    ? "Tighten the manual override threshold before creating more action paths; rejection/dismissal is currently matching or exceeding actionable outcomes."
    : "Keep using Watch for uncertain overrides, and compare completed actions against the original gate reason before trusting future bypasses.";

  return {
    achieved: `${summary.actionableCount} of ${summary.total} manual override record(s) became actionable, with ${summary.watchCount} held as watch items. ${completionLine}`,
    gap: `${riskLine} Current override actionable rate is ${formatRate(summary.actionableRate)} and rejection/dismissal rate is ${formatRate(summary.rejectionRate)}.`,
    next: nextLine,
  };
}

function buildManualOverrideOutcomeInterpretation(record: ProjectReviewRecord) {
  const outcome = (record.outcome || "").toLowerCase();

  if (outcome === "confirmed") {
    return "The reviewer overrode the gate and promoted this into project knowledge. Revisit this later to check whether the override produced durable value.";
  }
  if (outcome === "watch") {
    return "The reviewer preserved the override as observation rather than action. This is the safest outcome when value is plausible but evidence is not strong enough yet.";
  }
  if (outcome === "action") {
    return "The reviewer turned an override into an action path. This should be checked against due date, expected outcome, and later completion evidence.";
  }
  if (outcome === "action_completed") {
    return "The override-backed action has been completed. Use the completion note to judge whether bypassing the original gate was justified.";
  }
  if (outcome === "rejected") {
    return "The reviewer rejected the override after review. This is useful calibration: the system gate may have been right to block it.";
  }
  if (outcome === "dismissed") {
    return "The reviewer dismissed the override without treating it as a strong project signal. Keep this as low-cost calibration rather than project evidence.";
  }

  return "This manual override has a recorded review outcome. Compare the outcome with the original gate reason before using it as evidence.";
}

function buildRecordSourceContext(record: ProjectReviewRecord) {
  if (isManualReviewRecord(record)) {
    const contextParts = [
      record.upload_reason ? `Reason: ${record.upload_reason}` : "",
      record.intended_use ? `Use: ${record.intended_use}` : "",
      record.cognitive_layer ? `Layer: ${formatLabel(record.cognitive_layer)}` : "",
    ].filter(Boolean);
    return contextParts.length > 0
      ? contextParts.join(" / ")
      : "Manual-upload-derived record with no additional intent metadata.";
  }
  return `${formatRecordSource(record)} / Verification: ${record.verification_status ? formatLabel(record.verification_status) : "n/a"} / Confidence: ${formatConfidence(record.confidence_label, record.confidence_score)}`;
}

function buildRecordLearningSignal(record: ProjectReviewRecord) {
  const outcome = (record.outcome || "").toLowerCase();
  if (record.manual_project_takeaway_override) {
    return "Learning signal: compare this override against the gate reason before weakening future blockers.";
  }
  if (isRecordActionBlocked(record) && outcome.includes("watch")) {
    return "Learning signal: Watch preserved a blocked-action candidate without promoting it too early.";
  }
  if (isRecordActionBlocked(record) && outcome.includes("action")) {
    return "Learning signal: action moved ahead despite blocked-action context; review the outcome carefully.";
  }
  if ((record.unsupported_claim_count || 0) > 0) {
    return "Learning signal: unsupported claims reached review; future prompts should surface evidence gaps earlier.";
  }
  if (outcome.includes("action") || outcome === "confirmed") {
    return "Learning signal: this became actionable project memory and can calibrate future fit confidence.";
  }
  if (outcome.includes("rejected") || outcome.includes("dismissed")) {
    return "Learning signal: this rejection helps tune project-match and review-readiness thresholds.";
  }
  return "Learning signal: keep this review record as judgment context for future project-fit decisions.";
}

function SummaryMetric({ label, value }: { label: string; value: string | number }) {
  return (
    <div style={summaryItemStyle}>
      <span style={summaryLabelStyle}>{label}</span>
      <strong style={summaryValueStyle}>{value}</strong>
    </div>
  );
}

function OpsInterpretation({
  title,
  interpretation,
}: {
  title: string;
  interpretation: { achieved: string; gap: string; next: string };
}) {
  return (
    <div style={opsInterpretationStyle}>
      <span style={summaryLabelStyle}>{title}</span>
      <div style={opsInterpretationGridStyle}>
        <div style={opsInterpretationItemStyle}>
          <span style={detailLabelStyle}>Achieved</span>
          <strong>{interpretation.achieved}</strong>
        </div>
        <div style={opsInterpretationItemStyle}>
          <span style={detailLabelStyle}>Gaps</span>
          <strong>{interpretation.gap}</strong>
        </div>
        <div style={opsInterpretationItemStyle}>
          <span style={detailLabelStyle}>Next Focus</span>
          <strong>{interpretation.next}</strong>
        </div>
      </div>
    </div>
  );
}

function GateComparisonReadout({
  recordSummary,
  calibrationSummary,
  onShowActionBlocked,
  onShowGateConflicts,
  onShowManualOverrides,
  onShowWatchActionBlocked,
}: {
  recordSummary: ProjectReviewSummary;
  calibrationSummary: ProjectCalibrationSummary;
  onShowActionBlocked: () => void;
  onShowGateConflicts: () => void;
  onShowManualOverrides: () => void;
  onShowWatchActionBlocked: () => void;
}) {
  const comparison = buildGateComparison(recordSummary, calibrationSummary);

  return (
    <section style={gateComparisonBandStyle}>
      <div style={gateComparisonHeaderStyle}>
        <div>
          <span style={summaryLabelStyle}>Review vs Calibration</span>
          <strong style={summaryValueStyle}>Gate Conflict Alignment</strong>
        </div>
        <span style={comparison.conflictDelta === 0 ? gateAlignedChipStyle : gateMismatchChipStyle}>
          {comparison.alignment}
        </span>
      </div>
      <div style={gateComparisonGridStyle}>
        <div style={gateComparisonColumnStyle}>
          <span style={detailLabelStyle}>Review Records</span>
          <strong style={gateComparisonValueStyle}>{comparison.recordConflicts} conflict record(s)</strong>
          <span style={gateComparisonTextStyle}>
            Action blocked: {comparison.recordActionBlocked} / Watch kept safe: {comparison.recordWatchBlocked}
          </span>
          <span style={gateComparisonTextStyle}>
            Action conflict: {comparison.recordActionConflict} / Override conflict: {comparison.recordOverrideConflict}
          </span>
        </div>
        <div style={gateComparisonColumnStyle}>
          <span style={detailLabelStyle}>Calibration Events</span>
          <strong style={gateComparisonValueStyle}>{comparison.calibrationConflicts} conflict event(s)</strong>
          <span style={gateComparisonTextStyle}>
            Action blocked: {comparison.calibrationActionBlocked} / Watch kept safe: {comparison.calibrationWatchBlocked}
          </span>
          <span style={gateComparisonTextStyle}>
            Action conflict: {comparison.calibrationActionConflict} / Override conflict: {comparison.calibrationOverrideConflict}
          </span>
        </div>
        <div style={gateComparisonColumnStyle}>
          <span style={detailLabelStyle}>Delta</span>
          <strong style={gateComparisonValueStyle}>{comparison.conflictDelta > 0 ? "+" : ""}{comparison.conflictDelta}</strong>
          <span style={gateComparisonTextStyle}>{comparison.next}</span>
        </div>
      </div>
      <div style={gateComparisonActionRowStyle}>
        <button type="button" onClick={onShowGateConflicts} style={gateComparisonButtonStyle}>
          Show Gate Conflicts
        </button>
        <button type="button" onClick={onShowActionBlocked} style={gateComparisonButtonStyle}>
          Show Action Blocked
        </button>
        <button type="button" onClick={onShowWatchActionBlocked} style={gateComparisonButtonStyle}>
          Show Watch Kept Safe
        </button>
        <button type="button" onClick={onShowManualOverrides} style={gateComparisonButtonStyle}>
          Show Manual Overrides
        </button>
      </div>
    </section>
  );
}

const recordOutcomeFilters: Array<{ label: string; value: RecordOutcomeFilter }> = [
  { label: "All", value: "all" },
  { label: "Confirmed", value: "confirmed" },
  { label: "Watch", value: "watch" },
  { label: "Action", value: "action" },
  { label: "Completed", value: "action_completed" },
  { label: "Rejected", value: "rejected" },
  { label: "Dismissed", value: "dismissed" },
];

const recordQualityFilters: Array<{ label: string; value: RecordQualityFilter }> = [
  { label: "All Quality", value: "all" },
  { label: "Manual Overrides", value: "manual_override" },
  { label: "Gate Conflicts", value: "gate_conflicts" },
  { label: "Action Blocked", value: "action_blocked" },
  { label: "Watch Kept Safe", value: "watch_action_blocked" },
  { label: "Low Confidence", value: "low_confidence" },
  { label: "Blocked Actions", value: "blocked_actions" },
  { label: "Unsupported Claims", value: "unsupported_claims" },
  { label: "Inferred Claims", value: "inferred_claims" },
];

function missingReviewMetadata(action: ReviewAction, metadata: ReviewMetadata) {
  if (action === "watch") {
    const missing = [];
    if (!metadata.watch_review_date?.trim()) missing.push("Watch review date");
    if (!metadata.watch_status?.trim()) missing.push("Watch status");
    if (!metadata.watch_success_criteria?.trim()) missing.push("Watch success criteria");
    return missing;
  }

  if (action === "action") {
    const missing = [];
    if (!metadata.action_due_date?.trim()) missing.push("Action due date");
    if (!metadata.action_review_date?.trim()) missing.push("Action review date");
    if (!metadata.action_expected_outcome?.trim()) missing.push("Expected outcome");
    return missing;
  }

  return [];
}

export default function ProjectTakeawayReviewPage() {
  const searchParams = useSearchParams();
  const focusedSignalId = (searchParams.get("signal_id") || "").trim();
  const initialViewParam = (searchParams.get("view") || "").trim();
  const [items, setItems] = useState<ProjectTakeawayCandidate[]>([]);
  const [loading, setLoading] = useState(true);
  const [recordsLoading, setRecordsLoading] = useState(false);
  const [telemetryLoading, setTelemetryLoading] = useState(false);
  const [recordsLoaded, setRecordsLoaded] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [activeView, setActiveView] = useState<ReviewView>(initialViewParam === "records" ? "records" : "pending");
  const [reviewDisplayMode, setReviewDisplayMode] = useState<ReviewDisplayMode>("original");
  const [records, setRecords] = useState<ProjectReviewRecord[]>([]);
  const [recordSummary, setRecordSummary] = useState<ProjectReviewSummary | null>(null);
  const [calibrationSummary, setCalibrationSummary] = useState<ProjectCalibrationSummary | null>(null);
  const [learningProfile, setLearningProfile] = useState<ProjectLearningProfile | null>(null);
  const [learningProfileLoading, setLearningProfileLoading] = useState(false);
  const [learningProfileError, setLearningProfileError] = useState("");
  const [candidateQualityFilter, setCandidateQualityFilter] = useState<CandidateQualityFilter>("all");
  const [recordOutcomeFilter, setRecordOutcomeFilter] = useState<RecordOutcomeFilter>("all");
  const [recordQualityFilter, setRecordQualityFilter] = useState<RecordQualityFilter>("all");
  const [recordProjectFilter, setRecordProjectFilter] = useState("all");
  const [recordSearch, setRecordSearch] = useState("");
  const [recordSortOrder, setRecordSortOrder] = useState<RecordSortOrder>("newest");
  const recordsFilterRef = useRef<HTMLElement | null>(null);
  const [recordsLastLoadedAt, setRecordsLastLoadedAt] = useState("");
  const [loadStatus, setLoadStatus] = useState("");
  const [confirmingKey, setConfirmingKey] = useState("");
  const [closingKey, setClosingKey] = useState("");
  const [completingActionKey, setCompletingActionKey] = useState("");
  const [reviewingWatchKey, setReviewingWatchKey] = useState("");
  const [followupMessageByKey, setFollowupMessageByKey] = useState<Record<string, string>>({});
  const [reasonByKey, setReasonByKey] = useState<Record<string, string>>({});
  const [metadataByKey, setMetadataByKey] = useState<Record<string, ReviewMetadata>>({});
  const [overrideErrorByKey, setOverrideErrorByKey] = useState<Record<string, string>>({});
  const [completionNoteByKey, setCompletionNoteByKey] = useState<Record<string, string>>({});
  const [counterCheckDraftByKey, setCounterCheckDraftByKey] = useState<Record<string, ReasoningCounterCheckDraft>>({});
  const [counterCheckLoadingKey, setCounterCheckLoadingKey] = useState("");
  const [counterCheckErrorByKey, setCounterCheckErrorByKey] = useState<Record<string, string>>({});
  const [confirmedItem, setConfirmedItem] = useState<ProjectTakeawayCandidate | null>(null);
  const [closedItem, setClosedItem] = useState<ProjectTakeawayCandidate | null>(null);

  const loadCandidates = useCallback(async (options?: { keepExistingOnError?: boolean }) => {
    setLoading(true);
    setErrorMessage("");
    setLoadStatus("Loading Review Inbox candidates...");

    try {
      const response = await adminFetchWithTimeout(apiUrl("/projects/takeaway-candidates?include_confirmed=true&include_closed=true"), { cache: "no-store" });
      const data = (await response.json().catch(() => null)) as CandidatesResponse | null;
      if (!response.ok) {
        throw new Error(data?.detail || `Failed to load project takeaway candidates (${response.status})`);
      }

      const nextItems = data?.items || [];
      setItems(nextItems);
      setCounterCheckDraftByKey(
        nextItems.reduce<Record<string, ReasoningCounterCheckDraft>>((drafts, item) => {
          if (item.reasoning_counter_check_draft) {
            drafts[candidateKey(item.project_id, item.signal_id)] = item.reasoning_counter_check_draft;
          }
          return drafts;
        }, {})
      );
    } catch (error) {
      if (!options?.keepExistingOnError) {
        setItems([]);
      }
      setErrorMessage(isAbortError(error)
        ? "Project takeaway candidates request timed out after 8 seconds. Confirm the backend is running, then use Refresh or reload this page."
        : error instanceof Error ? error.message : "Failed to load project takeaway candidates.");
    } finally {
      setLoading(false);
      setLoadStatus("");
    }
  }, []);

  const loadReviewRecords = useCallback(async (options?: { keepExistingOnError?: boolean; clearVisibleError?: boolean }) => {
    setRecordsLoading(true);
    setLoadStatus(records.length > 0 ? "Refreshing Review Records and calibration summaries..." : "Loading Review Records and calibration summaries...");
    if (options?.clearVisibleError) {
      setErrorMessage("");
    }

    try {
      const [recordsResponse, summaryResponse] = await Promise.all([
        adminFetchWithTimeout(apiUrl("/projects/review-records"), { cache: "no-store" }),
        adminFetchWithTimeout(apiUrl("/projects/review-records/summary"), { cache: "no-store" }),
      ]);
      const recordsData = (await recordsResponse.json().catch(() => null)) as ReviewRecordsResponse | null;
      const summaryData = (await summaryResponse.json().catch(() => null)) as ReviewSummaryResponse | null;
      if (!recordsResponse.ok) {
        throw new Error(recordsData?.detail || `Failed to load project review records (${recordsResponse.status})`);
      }
      if (!summaryResponse.ok) {
        throw new Error(summaryData?.detail || `Failed to load project review summary (${summaryResponse.status})`);
      }

      setRecords(recordsData?.items || []);
      setRecordSummary(summaryData?.summary || null);
      setRecordsLoaded(true);
      setRecordsLastLoadedAt(new Date().toLocaleTimeString());

      const calibrationResponse = await adminFetchWithTimeout(apiUrl("/projects/calibration-events/summary"), { cache: "no-store" });
      const calibrationData = (await calibrationResponse.json().catch(() => null)) as CalibrationSummaryResponse | null;
      setCalibrationSummary(calibrationResponse.ok ? calibrationData?.summary || null : null);
    } catch (error) {
      setRecordsLoaded(false);
      if (!options?.keepExistingOnError) {
        setRecords([]);
        setRecordSummary(null);
        setCalibrationSummary(null);
      }
      setErrorMessage(isAbortError(error)
        ? "Review records request timed out after 8 seconds. Confirm the backend is running, then use Refresh or reload this page."
        : error instanceof Error ? error.message : "Failed to load project review records.");
    } finally {
      setRecordsLoading(false);
      setLoadStatus("");
    }
  }, [records.length]);

  const loadReviewTelemetry = useCallback(async () => {
    setTelemetryLoading(true);
    setLearningProfileLoading(true);
    setLearningProfileError("");
    try {
      const [summaryResponse, calibrationResponse, learningProfileResponse] = await Promise.all([
        adminFetchWithTimeout(apiUrl("/projects/review-records/summary"), { cache: "no-store" }),
        adminFetchWithTimeout(apiUrl("/projects/calibration-events/summary"), { cache: "no-store" }),
        adminFetchWithTimeout(apiUrl("/projects/learning-profile?recent_limit=3"), { cache: "no-store" }),
      ]);
      const summaryData = (await summaryResponse.json().catch(() => null)) as ReviewSummaryResponse | null;
      const calibrationData = (await calibrationResponse.json().catch(() => null)) as CalibrationSummaryResponse | null;
      const learningProfileData = (await learningProfileResponse.json().catch(() => null)) as ProjectLearningProfile | null;
      if (summaryResponse.ok) {
        setRecordSummary(summaryData?.summary || null);
      }
      if (calibrationResponse.ok) {
        setCalibrationSummary(calibrationData?.summary || null);
      }
      if (learningProfileResponse.ok) {
        setLearningProfile(learningProfileData || null);
      } else {
        setLearningProfileError(learningProfileData?.detail || `Learning profile unavailable (${learningProfileResponse.status})`);
      }
    } catch {
      setLearningProfileError("Learning profile unavailable while Review Inbox continues to load.");
      // Telemetry is supportive; candidate loading remains the primary page path.
    } finally {
      setTelemetryLoading(false);
      setLearningProfileLoading(false);
    }
  }, []);

  const pendingItems = items.filter((item) => (item.status || "").toLowerCase() === "candidate");
  const closedItems = items.filter((item) => (item.status || "").toLowerCase() !== "candidate");
  const watchItems = items.filter((item) => (item.status || "").toLowerCase() === "watch");
  const actionItems = items.filter((item) => (item.status || "").toLowerCase() === "action");
  const candidateSourceItems =
    activeView === "pending"
      ? pendingItems
      : activeView === "watch"
        ? watchItems
        : activeView === "action"
          ? actionItems
          : activeView === "closed"
            ? closedItems
            : [];
  const manualOverrideCandidateCount = candidateSourceItems.filter(isManualOverrideCandidate).length;
  const knowledgeConvergenceCandidateCount = candidateSourceItems.filter(isKnowledgeConvergenceCandidate).length;
  const knowledgeMissingProjectFitCandidateCount = candidateSourceItems.filter(isKnowledgeMissingProjectFitCandidate).length;
  const manualSourceCandidateCount = candidateSourceItems.filter(isManualSourceCandidate).length;
  const pendingActionBlockedCount = pendingItems.filter((item) => {
    const eligibility = getCandidateActionEligibility(item);
    return Boolean(eligibility?.low_risk_action_candidate?.allowed === false && !isManualOverrideCandidate(item));
  }).length;
  const pendingWatchSuggestedCount = pendingItems.filter((item) => {
    const eligibility = getCandidateActionEligibility(item);
    return Boolean(eligibility?.watch_only?.allowed !== false);
  }).length;
  const workbenchDecisionLine = buildWorkbenchDecisionLine({
    pendingCount: pendingItems.length,
    watchCount: watchItems.length,
    actionCount: actionItems.length,
    actionBlockedCount: pendingActionBlockedCount,
    manualCount: manualSourceCandidateCount,
    knowledgeCount: knowledgeConvergenceCandidateCount,
  });
  const activeQueueGuide = getActiveQueueGuide(activeView);
  const reviewedItemCount = closedItems.filter((item) =>
    ["confirmed", "rejected", "dismissed", "watch", "action", "action_completed"].includes((item.status || "").toLowerCase())
  ).length;
  const recordsTabCount = records.length || reviewedItemCount;
  const candidateTabCount = (count: number) => (loading && items.length === 0 ? "..." : String(count));
  const recordsTabCountLabel = recordsLoaded || !loading ? String(recordsTabCount) : "...";
  const normalizedRecordSearch = recordSearch.trim().toLowerCase();
  const recordMatchesQuality = (record: ProjectReviewRecord) => {
    if (recordQualityFilter === "all") return true;
    if (recordQualityFilter === "manual_override") {
      return Boolean(record.manual_project_takeaway_override);
    }
    if (recordQualityFilter === "gate_conflicts") {
      return hasRecordGateConflict(record);
    }
    if (recordQualityFilter === "action_blocked") {
      return isRecordActionBlocked(record);
    }
    if (recordQualityFilter === "watch_action_blocked") {
      return hasWatchWithActionBlocked(record);
    }
    if (recordQualityFilter === "low_confidence") {
      return (record.confidence_label || "").toLowerCase() === "low";
    }
    if (recordQualityFilter === "blocked_actions") {
      return Array.isArray(record.blocked_downstream_actions) && record.blocked_downstream_actions.length > 0;
    }
    if (recordQualityFilter === "unsupported_claims") {
      return (record.unsupported_claim_count || 0) > 0;
    }
    if (recordQualityFilter === "inferred_claims") {
      return (record.inferred_claim_count || 0) > 0;
    }
    return true;
  };
  const recordMatchesSearch = (record: ProjectReviewRecord) => {
    if (!normalizedRecordSearch) return true;
    return [
      record.project_name,
      record.project_id,
      record.signal_title,
      record.signal_id,
      record.reason,
      formatRecordSource(record),
      record.source_status,
      record.source_type,
      record.candidate_source,
      record.manual_session_id,
      record.manual_project_takeaway_override ? "manual override reviewer override human selected" : "",
      record.manual_override_note,
      record.verification_status,
      formatClaimSupport(record.claim_support_summary),
      formatActionList(record.blocked_downstream_actions),
      record.confidence_label,
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase()
      .includes(normalizedRecordSearch);
  };
  const recordsMatchingSearch = records.filter(recordMatchesSearch);
  const recordsMatchingProjectAndSearch = recordsMatchingSearch.filter(
    (record) =>
      (recordProjectFilter === "all" || (record.project_id || "") === recordProjectFilter) &&
      recordMatchesQuality(record)
  );
  const recordsMatchingOutcomeAndSearch = recordsMatchingSearch.filter(
    (record) =>
      (recordOutcomeFilter === "all" || (record.outcome || "").toLowerCase() === recordOutcomeFilter) &&
      recordMatchesQuality(record)
  );
  const recordsMatchingProjectOutcomeAndSearch = recordsMatchingSearch.filter((record) => {
    const outcomeMatches = recordOutcomeFilter === "all" || (record.outcome || "").toLowerCase() === recordOutcomeFilter;
    const projectMatches = recordProjectFilter === "all" || (record.project_id || "") === recordProjectFilter;
    return outcomeMatches && projectMatches;
  });
  const dynamicOutcomeCounts = recordsMatchingProjectAndSearch.reduce<Record<string, number>>((counts, record) => {
    const outcome = (record.outcome || "unknown").toLowerCase();
    counts[outcome] = (counts[outcome] || 0) + 1;
    return counts;
  }, {});
  const dynamicProjectCounts = recordsMatchingOutcomeAndSearch.reduce<Record<string, number>>((counts, record) => {
    const projectId = record.project_id || "unknown";
    counts[projectId] = (counts[projectId] || 0) + 1;
    return counts;
  }, {});
  const projectLabelById = records.reduce<Record<string, string>>((labels, record) => {
    const projectId = record.project_id || "unknown";
    labels[projectId] = record.project_name || formatLabel(projectId);
    return labels;
  }, {});
  const recordProjectFilters = [
    { label: "All Projects", value: "all", count: recordsMatchingOutcomeAndSearch.length },
    ...Object.entries(dynamicProjectCounts)
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([projectId, count]) => ({ label: projectLabelById[projectId] || formatLabel(projectId), value: projectId, count })),
  ];
  const selectedProjectLabel =
    recordProjectFilter === "all" ? "All Projects" : projectLabelById[recordProjectFilter] || formatLabel(recordProjectFilter);
  const selectedOutcomeLabel =
    recordOutcomeFilter === "all" ? "All Outcomes" : recordOutcomeFilters.find((filter) => filter.value === recordOutcomeFilter)?.label || formatLabel(recordOutcomeFilter);
  const selectedQualityLabel =
    recordQualityFilter === "all" ? "All Quality" : recordQualityFilters.find((filter) => filter.value === recordQualityFilter)?.label || formatLabel(recordQualityFilter);
  const hasActiveRecordFilters =
    recordProjectFilter !== "all" ||
    recordOutcomeFilter !== "all" ||
    recordQualityFilter !== "all" ||
    recordSearch.trim().length > 0 ||
    recordSortOrder !== "newest";
  const qualityFilterCount = (filterValue: RecordQualityFilter) =>
    recordsMatchingProjectOutcomeAndSearch.filter((record) => {
      if (filterValue === "all") return true;
      if (filterValue === "manual_override") return Boolean(record.manual_project_takeaway_override);
      if (filterValue === "gate_conflicts") return hasRecordGateConflict(record);
      if (filterValue === "action_blocked") return isRecordActionBlocked(record);
      if (filterValue === "watch_action_blocked") return hasWatchWithActionBlocked(record);
      if (filterValue === "low_confidence") return (record.confidence_label || "").toLowerCase() === "low";
      if (filterValue === "blocked_actions") return Array.isArray(record.blocked_downstream_actions) && record.blocked_downstream_actions.length > 0;
      if (filterValue === "unsupported_claims") return (record.unsupported_claim_count || 0) > 0;
      if (filterValue === "inferred_claims") return (record.inferred_claim_count || 0) > 0;
      return true;
    }).length;
  const filterSummaryText = `${selectedProjectLabel} / ${selectedOutcomeLabel} / ${selectedQualityLabel} / ${recordSortOrder === "newest" ? "Newest first" : "Oldest first"}${recordSearch.trim() ? ` / Search: ${recordSearch.trim()}` : ""}`;
  function resetRecordFilters() {
    setRecordProjectFilter("all");
    setRecordOutcomeFilter("all");
    setRecordQualityFilter("all");
    setRecordSortOrder("newest");
    setRecordSearch("");
  }
  function focusRecordQuality(filter: RecordQualityFilter) {
    setRecordProjectFilter("all");
    setRecordOutcomeFilter("all");
    setRecordQualityFilter(filter);
    setRecordSortOrder("newest");
    setRecordSearch("");
    window.requestAnimationFrame(() => {
      recordsFilterRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }
  const manualOverrideCalibration = buildManualOverrideCalibration(records);
  const calibrationFocusSummary: ProjectReviewSummary = recordSummary || { total_records: records.length };
  const reviewCalibrationActions = buildReviewCalibrationActions(calibrationFocusSummary, calibrationSummary);
  const manualSourceLearningSummary = buildManualSourceLearningSummary(calibrationFocusSummary, calibrationSummary);
  const knowledgeOperatingSummary = buildKnowledgeOperatingSummary(pendingItems);
  const metricsOperatingSummary = buildMetricsOperatingSummary(calibrationFocusSummary, calibrationSummary);
  const reviewLoopFollowupSummary = buildReviewLoopFollowupSummary({
    watchItems,
    actionItems,
    closedItems,
    recordSummary,
    calibrationSummary,
  });
  const learningProfilePosture = buildLearningProfilePosture(learningProfile);
  const learningSignals = learningProfile?.learning_signals || {};
  const learningReviewSummary = learningProfile?.review_summary || recordSummary || {};
  const learningCalibrationSummary = learningProfile?.calibration_summary || calibrationSummary || {};
  const topBlockedAction = formatLearningProfileTopCount(learningProfile?.risk_profile?.top_blocked_actions);
  const topReviewOutcome = formatLearningProfileTopCount(learningProfile?.outcome_profile?.top_review_outcomes);
  const learningBoundary =
    learningProfile?.evidence_boundary === "review_and_calibration_history_not_external_claim_evidence"
      ? "Review/calibration history, not external claim evidence"
      : learningProfile?.evidence_boundary || "Read-only learning context";
  const visibleRecords = records
    .filter((record) => {
      const outcomeMatches = recordOutcomeFilter === "all" || (record.outcome || "").toLowerCase() === recordOutcomeFilter;
      if (!outcomeMatches) return false;
      const projectMatches = recordProjectFilter === "all" || (record.project_id || "") === recordProjectFilter;
      if (!projectMatches) return false;
      if (!recordMatchesQuality(record)) return false;
      return recordMatchesSearch(record);
    })
    .sort((left, right) => {
      const leftTime = left.reviewed_at || left.updated_at || "";
      const rightTime = right.reviewed_at || right.updated_at || "";
      return recordSortOrder === "newest" ? rightTime.localeCompare(leftTime) : leftTime.localeCompare(rightTime);
    });
  const visibleItems =
    (activeView === "pending"
      ? pendingItems
      : activeView === "watch"
        ? watchItems
        : activeView === "action"
          ? actionItems
          : closedItems
    ).filter((item) => {
      if (focusedSignalId && (item.signal_id || "") !== focusedSignalId) return false;
      if (activeView === "records" || candidateQualityFilter === "all") return true;
      if (candidateQualityFilter === "manual_source") return isManualSourceCandidate(item);
      if (candidateQualityFilter === "manual_override") return isManualOverrideCandidate(item);
      if (candidateQualityFilter === "knowledge_convergence") return isKnowledgeConvergenceCandidate(item);
      if (candidateQualityFilter === "knowledge_missing_project_fit") return isKnowledgeMissingProjectFitCandidate(item);
      return true;
    });
  const focusedPendingCount = focusedSignalId
    ? pendingItems.filter((item) => (item.signal_id || "") === focusedSignalId).length
    : 0;
  const focusedClosedCount = focusedSignalId
    ? closedItems.filter((item) => (item.signal_id || "") === focusedSignalId).length
    : 0;
  const focusedWatchCount = focusedSignalId
    ? watchItems.filter((item) => (item.signal_id || "") === focusedSignalId).length
    : 0;
  const focusedActionCount = focusedSignalId
    ? actionItems.filter((item) => (item.signal_id || "") === focusedSignalId).length
    : 0;
  const focusedCandidateTotal = focusedPendingCount + focusedClosedCount;
  const focusedCurrentViewCount =
    activeView === "pending"
      ? focusedPendingCount
      : activeView === "watch"
        ? focusedWatchCount
        : activeView === "action"
          ? focusedActionCount
          : activeView === "closed"
            ? focusedClosedCount
            : 0;

  useEffect(() => {
    if (!focusedSignalId || loading || activeView === "records") return;
    if (focusedCandidateTotal === 0 || focusedCurrentViewCount > 0) return;

    if (focusedPendingCount > 0) {
      setActiveView("pending");
      return;
    }
    if (focusedWatchCount > 0) {
      setActiveView("watch");
      return;
    }
    if (focusedActionCount > 0) {
      setActiveView("action");
      return;
    }
    if (focusedClosedCount > 0) {
      setActiveView("closed");
    }
  }, [
    activeView,
    focusedActionCount,
    focusedCandidateTotal,
    focusedClosedCount,
    focusedCurrentViewCount,
    focusedPendingCount,
    focusedSignalId,
    focusedWatchCount,
    loading,
  ]);

  useEffect(() => {
    void loadCandidates();
    void loadReviewTelemetry();
  }, [loadCandidates, loadReviewTelemetry]);

  useEffect(() => {
    if (activeView === "records" && !recordsLoaded) {
      void loadReviewRecords({ clearVisibleError: true });
    }
  }, [activeView, loadReviewRecords, recordsLoaded]);

  async function handleGenerateCounterCheck(
    item: ProjectTakeawayCandidate,
    advisory: ReturnType<typeof buildReasoningAssessmentAdvisory>,
    actionEligibility: ActionEligibilitySummary | null,
    claimSupport: string,
    sourceModelProvenance: ModelProvenance,
    key: string
  ) {
    setCounterCheckLoadingKey(key);
    setCounterCheckErrorByKey((current) => {
      const next = { ...current };
      delete next[key];
      return next;
    });

    try {
      const response = await adminFetch(
        apiUrl("/projects/reasoning-counter-check"),
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            project_id: item.project_id || "",
            project_name: item.project_name || "",
            signal_id: item.signal_id || "",
            signal_title: item.signal_title || "",
            signal_summary: item.signal_summary || "",
            takeaway: item.takeaway || "",
            why_it_matters: item.why_it_matters || "",
            fit_reason: item.fit_reason || "",
            benefits: item.benefits || "",
            final_reflection: item.final_reflection || "",
            claim_support: claimSupport,
            warrant: advisory.warrant,
            counter_check_prompt: advisory.counterCheck,
            boundary: advisory.boundary,
            source_model_provenance: sourceModelProvenance,
            verification_metadata: item.verification_metadata || {},
            action_eligibility: actionEligibility || item.action_eligibility || {},
          }),
        }
      );
      const data = (await response.json().catch(() => null)) as ReasoningCounterCheckResponse | null;
      if (!response.ok) {
        throw new Error(data?.detail || `Failed to generate counter-check draft (${response.status})`);
      }
      if (!data?.draft) {
        throw new Error("Counter-check draft response was empty.");
      }
      setCounterCheckDraftByKey((current) => ({
        ...current,
        [key]: data.draft as ReasoningCounterCheckDraft,
      }));
      if (data.item) {
        setItems((current) =>
          current.map((candidate) =>
            candidate.project_id === data.item?.project_id && candidate.signal_id === data.item?.signal_id
              ? { ...candidate, ...data.item }
              : candidate
          )
        );
      }
    } catch (error) {
      setCounterCheckErrorByKey((current) => ({
        ...current,
        [key]: error instanceof Error ? error.message : "Failed to generate counter-check draft.",
      }));
    } finally {
      setCounterCheckLoadingKey("");
    }
  }

  async function handleConfirm(item: ProjectTakeawayCandidate) {
    if (!item.project_id || !item.signal_id) return;

    const key = `${item.project_id}:${item.signal_id}`;
    setConfirmingKey(key);
    setErrorMessage("");
    setConfirmedItem(null);
    setClosedItem(null);

    try {
      const response = await adminFetch(
        apiUrl(`/projects/${encodeURIComponent(item.project_id)}/improvements/${encodeURIComponent(item.signal_id)}/confirm`),
        { method: "POST" }
      );
      const data = (await response.json().catch(() => null)) as ConfirmResponse | null;
      if (!response.ok) {
        throw new Error(data?.detail || `Failed to confirm candidate (${response.status})`);
      }

      setItems((current) =>
        current.map((candidate) =>
          candidate.project_id === item.project_id && candidate.signal_id === item.signal_id
            ? { ...candidate, ...(data?.item || {}), status: "confirmed" }
            : candidate
        )
      );
      setConfirmedItem({ ...item, ...(data?.item || {}), status: "confirmed" });
      void loadReviewRecords();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to confirm this candidate.");
    } finally {
      setConfirmingKey("");
    }
  }

  async function handleOverrideConfirm(item: ProjectTakeawayCandidate) {
    if (!item.project_id || !item.signal_id) return;

    const key = `${item.project_id}:${item.signal_id}`;
    const metadata = metadataByKey[key] || {};
    const overrideNote = (reasonByKey[key] || "").trim();
    const expectedOutcome = (metadata.action_expected_outcome || "").trim();
    if (!overrideNote || !expectedOutcome) {
      setOverrideErrorByKey((current) => ({
        ...current,
        [key]: "Override Confirm requires a manual override note and expected outcome.",
      }));
      setConfirmedItem(null);
      setClosedItem(null);
      return;
    }

    setConfirmingKey(`${key}:override`);
    setErrorMessage("");
    setOverrideErrorByKey((current) => {
      const next = { ...current };
      delete next[key];
      return next;
    });
    setConfirmedItem(null);
    setClosedItem(null);

    try {
      const response = await adminFetch(
        apiUrl(`/projects/${encodeURIComponent(item.project_id)}/improvements/${encodeURIComponent(item.signal_id)}/override-confirm`),
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            reason: overrideNote,
            expected_outcome: expectedOutcome,
          }),
        }
      );
      const data = (await response.json().catch(() => null)) as ConfirmResponse | null;
      if (!response.ok) {
        throw new Error(data?.detail || `Failed to override-confirm candidate (${response.status})`);
      }

      setItems((current) =>
        current.map((candidate) =>
          candidate.project_id === item.project_id && candidate.signal_id === item.signal_id
            ? { ...candidate, ...(data?.item || {}), status: "confirmed" }
            : candidate
        )
      );
      setReasonByKey((current) => {
        const next = { ...current };
        delete next[key];
        return next;
      });
      setMetadataByKey((current) => {
        const next = { ...current };
        delete next[key];
        return next;
      });
      setConfirmedItem({ ...item, ...(data?.item || {}), status: "confirmed" });
      void loadReviewRecords();
    } catch (error) {
      setOverrideErrorByKey((current) => ({
        ...current,
        [key]: error instanceof Error ? error.message : "Failed to override-confirm this candidate.",
      }));
    } finally {
      setConfirmingKey("");
    }
  }

  async function handleCloseCandidate(item: ProjectTakeawayCandidate, action: ReviewAction) {
    if (!item.project_id || !item.signal_id) return;

    const key = `${item.project_id}:${item.signal_id}`;
    const metadata = metadataByKey[key] || {};
    const missingFields = missingReviewMetadata(action, metadata);
    if (missingFields.length > 0) {
      setErrorMessage(`${action === "watch" ? "Watch" : "Action"} details required: ${missingFields.join(", ")}.`);
      setConfirmedItem(null);
      setClosedItem(null);
      return;
    }

    setClosingKey(`${key}:${action}`);
    setErrorMessage("");
    setConfirmedItem(null);
    setClosedItem(null);

    try {
      const response = await adminFetch(
        apiUrl(`/projects/${encodeURIComponent(item.project_id)}/improvements/${encodeURIComponent(item.signal_id)}/${action === "rejected" ? "reject" : action === "dismissed" ? "dismiss" : action}`),
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            reason: reasonByKey[key] || "",
            review_date: action === "watch" ? metadata.watch_review_date || "" : metadata.action_review_date || "",
            success_criteria: metadata.watch_success_criteria || "",
            watch_status: metadata.watch_status || "",
            expected_outcome: metadata.action_expected_outcome || "",
            due_date: metadata.action_due_date || "",
          }),
        }
      );
      const data = (await response.json().catch(() => null)) as ConfirmResponse | null;
      if (!response.ok) {
        throw new Error(data?.detail || `Failed to ${action === "rejected" ? "reject" : action === "dismissed" ? "dismiss" : action} candidate (${response.status})`);
      }

      setItems((current) =>
        current.map((candidate) =>
          candidate.project_id === item.project_id && candidate.signal_id === item.signal_id
            ? { ...candidate, ...(data?.item || {}), status: action }
            : candidate
        )
      );
      setReasonByKey((current) => {
        const next = { ...current };
        delete next[key];
        return next;
      });
      setMetadataByKey((current) => {
        const next = { ...current };
        delete next[key];
        return next;
      });
      setClosedItem({ ...item, ...(data?.item || {}), status: action });
      void loadReviewRecords();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : `Failed to ${action === "rejected" ? "reject" : action === "dismissed" ? "dismiss" : action} this candidate.`);
    } finally {
      setClosingKey("");
    }
  }

  async function handleOverrideAction(item: ProjectTakeawayCandidate) {
    if (!item.project_id || !item.signal_id) return;

    const key = `${item.project_id}:${item.signal_id}`;
    const metadata = metadataByKey[key] || {};
    const overrideNote = (reasonByKey[key] || "").trim();
    const expectedOutcome = (metadata.action_expected_outcome || "").trim();
    const dueDate = (metadata.action_due_date || "").trim();
    const reviewDate = (metadata.action_review_date || "").trim();
    if (!overrideNote || !expectedOutcome || !dueDate || !reviewDate) {
      setOverrideErrorByKey((current) => ({
        ...current,
        [key]: "Override Action requires a manual override note, expected outcome, due date, and review date.",
      }));
      setConfirmedItem(null);
      setClosedItem(null);
      return;
    }

    setClosingKey(`${key}:override-action`);
    setErrorMessage("");
    setOverrideErrorByKey((current) => {
      const next = { ...current };
      delete next[key];
      return next;
    });
    setConfirmedItem(null);
    setClosedItem(null);

    try {
      const response = await adminFetch(
        apiUrl(`/projects/${encodeURIComponent(item.project_id)}/improvements/${encodeURIComponent(item.signal_id)}/override-action`),
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            reason: overrideNote,
            expected_outcome: expectedOutcome,
            due_date: dueDate,
            review_date: reviewDate,
          }),
        }
      );
      const data = (await response.json().catch(() => null)) as ConfirmResponse | null;
      if (!response.ok) {
        throw new Error(data?.detail || `Failed to override-action candidate (${response.status})`);
      }

      setItems((current) =>
        current.map((candidate) =>
          candidate.project_id === item.project_id && candidate.signal_id === item.signal_id
            ? { ...candidate, ...(data?.item || {}), status: "action" }
            : candidate
        )
      );
      setReasonByKey((current) => {
        const next = { ...current };
        delete next[key];
        return next;
      });
      setMetadataByKey((current) => {
        const next = { ...current };
        delete next[key];
        return next;
      });
      setClosedItem({ ...item, ...(data?.item || {}), status: "action" });
      void loadReviewRecords();
    } catch (error) {
      setOverrideErrorByKey((current) => ({
        ...current,
        [key]: error instanceof Error ? error.message : "Failed to override-action this candidate.",
      }));
    } finally {
      setClosingKey("");
    }
  }

  async function handleCompleteAction(item: ProjectTakeawayCandidate) {
    if (!item.project_id || !item.signal_id) return;

    const key = `${item.project_id}:${item.signal_id}`;
    const metadata = metadataByKey[key] || {};
    setCompletingActionKey(key);
    setErrorMessage("");
    setConfirmedItem(null);
    setClosedItem(null);

    try {
      const response = await adminFetch(
        apiUrl(`/projects/${encodeURIComponent(item.project_id)}/improvements/${encodeURIComponent(item.signal_id)}/complete-action`),
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            reason: completionNoteByKey[key] || "",
            followup_result: metadata.followup_result || "",
            evidence_update: metadata.evidence_update || "",
            next_review_date: metadata.next_review_date || "",
          }),
        }
      );
      const data = (await response.json().catch(() => null)) as ConfirmResponse | null;
      if (!response.ok) {
        throw new Error(data?.detail || `Failed to complete action (${response.status})`);
      }

      setItems((current) =>
        current.map((candidate) =>
          candidate.project_id === item.project_id && candidate.signal_id === item.signal_id
            ? { ...candidate, ...(data?.item || {}), status: "action_completed" }
            : candidate
        )
      );
      setCompletionNoteByKey((current) => {
        const next = { ...current };
        delete next[key];
        return next;
      });
      setMetadataByKey((current) => {
        const next = { ...current };
        delete next[key];
        return next;
      });
      setClosedItem({ ...item, ...(data?.item || {}), status: "action_completed" });
      setActiveView("closed");
      void loadReviewRecords();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to complete this action.");
    } finally {
      setCompletingActionKey("");
    }
  }

  async function handleReviewWatch(item: ProjectTakeawayCandidate) {
    if (!item.project_id || !item.signal_id) return;

    const key = `${item.project_id}:${item.signal_id}`;
    const metadata = metadataByKey[key] || {};
    const followupResult = (metadata.followup_result || "").trim();
    if (!followupResult) {
      setErrorMessage("Watch follow-up result is required.");
      setConfirmedItem(null);
      setClosedItem(null);
      return;
    }

    setReviewingWatchKey(key);
    setErrorMessage("");
    setFollowupMessageByKey((current) => {
      const next = { ...current };
      delete next[key];
      return next;
    });
    setConfirmedItem(null);
    setClosedItem(null);

    try {
      const response = await adminFetch(
        apiUrl(`/projects/${encodeURIComponent(item.project_id)}/improvements/${encodeURIComponent(item.signal_id)}/review-watch`),
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            reason: reasonByKey[key] || "",
            followup_result: followupResult,
            evidence_update: metadata.evidence_update || "",
            next_review_date: metadata.next_review_date || "",
          }),
        }
      );
      const data = (await response.json().catch(() => null)) as ConfirmResponse | null;
      if (!response.ok) {
        throw new Error(data?.detail || `Failed to review watch item (${response.status})`);
      }

      setItems((current) =>
        current.map((candidate) =>
          candidate.project_id === item.project_id && candidate.signal_id === item.signal_id
            ? { ...candidate, ...(data?.item || {}), status: "watch" }
            : candidate
        )
      );
      setReasonByKey((current) => {
        const next = { ...current };
        delete next[key];
        return next;
      });
      setMetadataByKey((current) => {
        const next = { ...current };
        delete next[key];
        return next;
      });
      setClosedItem({ ...item, ...(data?.item || {}), status: "watch" });
      setFollowupMessageByKey((current) => ({
        ...current,
        [key]: "Follow-up added. Item remains in Watch until you convert it to Action, reject it, or close it later.",
      }));
      void loadReviewTelemetry();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to review this watch item.");
    } finally {
      setReviewingWatchKey("");
    }
  }

  return (
    <AppContainer style={{ paddingTop: "24px" }}>
      <RequireAdminAuth>
        <div style={compactHeaderStyle}>
          <div style={{ minWidth: 0 }}>
            <div style={summaryLabelStyle}>Workspace Review</div>
            <h1 style={compactTitleStyle}>Project Takeaway Review Inbox</h1>
            <p style={compactDescriptionStyle}>
              Review verified signal takeaways before they become confirmed project improvements.
            </p>
          </div>
          <div style={compactHeaderActionsStyle}>
            <Link href="/workspace/projects" style={primaryToolbarLinkStyle}>
              Back to Project Takeaways
            </Link>
            <Link href="/workspace" style={toolbarLinkStyle}>
              Back to Workspace
            </Link>
            <Link href="/workspace/projects/trajectory" style={toolbarLinkStyle}>
              Trajectory Timeline
            </Link>
          </div>
        </div>

        <section style={displayModePanelStyle}>
          <div>
            <span style={summaryLabelStyle}>Page Mode</span>
            <strong style={displayModeTitleStyle}>
              {reviewDisplayMode === "original" ? "Original full-detail view" : "Simplified comparison view"}
            </strong>
            <p style={displayModeCopyStyle}>
              Original keeps the full audit surface. Simplified reduces pending candidate cards to recommendation, reason, next step, and shared actions while preserving diagnostics in disclosure.
            </p>
          </div>
          <div style={displayModeToggleStyle} aria-label="Review page display mode">
            <button
              type="button"
              onClick={() => setReviewDisplayMode("original")}
              style={reviewDisplayMode === "original" ? activeDisplayModeButtonStyle : displayModeButtonStyle}
            >
              Original
            </button>
            <button
              type="button"
              onClick={() => setReviewDisplayMode("simplified")}
              style={reviewDisplayMode === "simplified" ? activeDisplayModeButtonStyle : displayModeButtonStyle}
            >
              Simplified
            </button>
          </div>
        </section>

        <section style={reviewLoopFollowupStyle}>
          <div style={reviewWorkbenchHeaderStyle}>
            <div>
              <span style={summaryLabelStyle}>Review Loop Follow-up</span>
              <h2 style={reviewWorkbenchTitleStyle}>Watch, Action, and calibration queue</h2>
              <p style={reviewWorkbenchCopyStyle}>
                {reviewLoopFollowupSummary.nextFocus}
              </p>
            </div>
            {telemetryLoading ? <span style={refreshingNoticeStyle}>Loading learning summary...</span> : null}
          </div>
          <div style={reviewWorkbenchGridStyle}>
            <button type="button" onClick={() => setActiveView("watch")} style={reviewWorkbenchMetricButtonStyle}>
              <span style={summaryLabelStyle}>Watch Due</span>
              <strong>{candidateTabCount(reviewLoopFollowupSummary.watchDueCount)}</strong>
              <span>Review dates due now or earlier.</span>
            </button>
            <button type="button" onClick={() => setActiveView("watch")} style={reviewWorkbenchMetricButtonStyle}>
              <span style={summaryLabelStyle}>Watch Missing Plan</span>
              <strong>{candidateTabCount(reviewLoopFollowupSummary.watchMissingPlanCount)}</strong>
              <span>Missing review date, status, or success criteria.</span>
            </button>
            <button type="button" onClick={() => setActiveView("action")} style={reviewWorkbenchMetricButtonStyle}>
              <span style={summaryLabelStyle}>Action Due</span>
              <strong>{candidateTabCount(reviewLoopFollowupSummary.actionDueCount)}</strong>
              <span>Due or review date needs attention.</span>
            </button>
            <button type="button" onClick={() => setActiveView("action")} style={reviewWorkbenchMetricButtonStyle}>
              <span style={summaryLabelStyle}>Action Missing Plan</span>
              <strong>{candidateTabCount(reviewLoopFollowupSummary.actionMissingPlanCount)}</strong>
              <span>Missing due date, review date, or expected outcome.</span>
            </button>
            <button type="button" onClick={() => setActiveView("records")} style={reviewWorkbenchMetricButtonStyle}>
              <span style={summaryLabelStyle}>Learning Memory</span>
              <strong>{reviewLoopFollowupSummary.learningRecordCount}</strong>
              <span>{reviewLoopFollowupSummary.calibrationEventCount} calibration events / {reviewLoopFollowupSummary.manualLearningCount} manual signals.</span>
            </button>
          </div>
          <div style={activeQueueGuideStyle}>
            <span style={summaryLabelStyle}>Calibration Signal</span>
            <strong>
              {reviewLoopFollowupSummary.gateConflictCount > 0
                ? `${reviewLoopFollowupSummary.gateConflictCount} gate conflict(s) need review before more override-driven action.`
                : `${reviewLoopFollowupSummary.actionCompletedCount} action completion(s) are available as learning memory.`}
            </strong>
          </div>
        </section>

        <section style={projectLearningProfileStyle}>
          <div style={reviewWorkbenchHeaderStyle}>
            <div>
              <span style={summaryLabelStyle}>Project Learning Profile</span>
              <h2 style={reviewWorkbenchTitleStyle}>{learningProfilePosture.label}</h2>
              <p style={reviewWorkbenchCopyStyle}>{learningProfilePosture.body}</p>
            </div>
            {learningProfileLoading ? <span style={refreshingNoticeStyle}>Loading learning profile...</span> : null}
          </div>
          <div style={projectLearningProfileGridStyle}>
            <div style={projectLearningProfileMetricStyle}>
              <span style={summaryLabelStyle}>Review Records</span>
              <strong>{learningReviewSummary.total_records || 0}</strong>
              <span>Top outcome: {topReviewOutcome}</span>
            </div>
            <div style={projectLearningProfileMetricStyle}>
              <span style={summaryLabelStyle}>Calibration Events</span>
              <strong>{learningCalibrationSummary.total_events || 0}</strong>
              <span>Latest: {learningCalibrationSummary.latest_event_at || learningReviewSummary.latest_reviewed_at || "n/a"}</span>
            </div>
            <div style={projectLearningProfileMetricStyle}>
              <span style={summaryLabelStyle}>Actionable Memory</span>
              <strong>{safeCount(learningSignals.actionable_count)}</strong>
              <span>Confirmed / Action outcomes remain learning context.</span>
            </div>
            <div style={projectLearningProfileMetricStyle}>
              <span style={summaryLabelStyle}>Watch Memory</span>
              <strong>{safeCount(learningSignals.watch_count)}</strong>
              <span>Follow-up evidence decides whether to promote.</span>
            </div>
            <div style={projectLearningProfileMetricStyle}>
              <span style={summaryLabelStyle}>Gate Risk</span>
              <strong>{safeCount(learningSignals.blocked_action_context_count) + safeCount(learningSignals.gate_conflict_context_count)}</strong>
              <span>Top blocked action: {topBlockedAction}</span>
            </div>
            <div style={projectLearningProfileMetricStyle}>
              <span style={summaryLabelStyle}>Manual Source Learning</span>
              <strong>{safeCount(learningSignals.manual_source_context_count)}</strong>
              <span>Manual material keeps separate provenance.</span>
            </div>
          </div>
          <div style={projectLearningProfileBoundaryStyle}>
            <div>
              <span style={summaryLabelStyle}>Evidence Boundary</span>
              <strong>{learningBoundary}</strong>
            </div>
            <div>
              <span style={summaryLabelStyle}>Next Focus</span>
              <strong>{learningProfilePosture.focus || "Keep using Review Inbox decisions to build project learning memory."}</strong>
            </div>
          </div>
          {learningProfileError ? <div style={projectLearningProfileErrorStyle}>{learningProfileError}</div> : null}
        </section>

        <div style={tabListStyle}>
          <button
            type="button"
            onClick={() => setActiveView("pending")}
            style={activeView === "pending" ? activeTabStyle : tabButtonStyle}
          >
            Pending ({candidateTabCount(pendingItems.length)})
          </button>
          <button
            type="button"
            onClick={() => setActiveView("closed")}
            style={activeView === "closed" ? activeTabStyle : tabButtonStyle}
          >
            Closed ({candidateTabCount(closedItems.length)})
          </button>
          <button
            type="button"
            onClick={() => setActiveView("watch")}
            style={activeView === "watch" ? activeTabStyle : tabButtonStyle}
          >
            Watch ({candidateTabCount(watchItems.length)})
          </button>
          <button
            type="button"
            onClick={() => setActiveView("action")}
            style={activeView === "action" ? activeTabStyle : tabButtonStyle}
          >
            Action ({candidateTabCount(actionItems.length)})
          </button>
          <button
            type="button"
            onClick={() => setActiveView("records")}
            style={activeView === "records" ? activeTabStyle : tabButtonStyle}
          >
            Records ({recordsTabCountLabel})
          </button>
        </div>

        <section style={reviewWorkbenchStyle}>
          <div style={reviewWorkbenchHeaderStyle}>
            <div>
              <div style={summaryLabelStyle}>Review Workbench</div>
              <h2 style={reviewWorkbenchTitleStyle}>Next best review move</h2>
              <p style={reviewWorkbenchCopyStyle}>{workbenchDecisionLine}</p>
            </div>
          </div>
          <div style={reviewWorkbenchGridStyle}>
            <button
              type="button"
              onClick={() => {
                setActiveView("pending");
                setCandidateQualityFilter("all");
              }}
              style={reviewWorkbenchMetricButtonStyle}
            >
              <span style={summaryLabelStyle}>Pending Queue</span>
              <strong>{candidateTabCount(pendingItems.length)}</strong>
              <span>Human project-fit decisions waiting.</span>
            </button>
            <button
              type="button"
              onClick={() => {
                setActiveView("pending");
                setCandidateQualityFilter("all");
              }}
              style={reviewWorkbenchMetricButtonStyle}
            >
              <span style={summaryLabelStyle}>Action Blocked</span>
              <strong>{candidateTabCount(pendingActionBlockedCount)}</strong>
              <span>Use Watch / Reject unless evidence improves. Action completed remains lifecycle state, not review outcome.</span>
            </button>
            <button
              type="button"
              onClick={() => {
                setActiveView("pending");
                setCandidateQualityFilter("manual_source");
              }}
              style={reviewWorkbenchMetricButtonStyle}
            >
              <span style={summaryLabelStyle}>Manual Source</span>
              <strong>{candidateTabCount(manualSourceCandidateCount)}</strong>
              <span>Check upload intent and completion route.</span>
            </button>
            <button
              type="button"
              onClick={() => {
                setActiveView("pending");
                setCandidateQualityFilter("knowledge_convergence");
              }}
              style={reviewWorkbenchMetricButtonStyle}
            >
              <span style={summaryLabelStyle}>Knowledge Fit</span>
              <strong>{candidateTabCount(knowledgeConvergenceCandidateCount)}</strong>
              <span>Review supply/demand fit before action.</span>
            </button>
            <button
              type="button"
              onClick={() => setActiveView("watch")}
              style={reviewWorkbenchMetricButtonStyle}
            >
              <span style={summaryLabelStyle}>Watch Viable</span>
              <strong>{candidateTabCount(pendingWatchSuggestedCount)}</strong>
              <span>Safer path for partial evidence.</span>
            </button>
          </div>
          <div style={activeQueueGuideStyle}>
            <span style={summaryLabelStyle}>{activeQueueGuide.title}</span>
            <strong>{activeQueueGuide.body}</strong>
          </div>
        </section>

        {loadStatus ? <div style={infoCardStyle}>{loadStatus}</div> : null}
        {errorMessage ? <div style={errorCardStyle}>{errorMessage}</div> : null}
        {focusedSignalId && activeView !== "records" ? (
          <section style={focusedSignalPanelStyle}>
            <div>
              <div style={summaryLabelStyle}>Focused Signal Review</div>
              <div style={{ color: "var(--app-text-muted)", fontSize: "13px", lineHeight: 1.6, marginTop: "4px" }}>
                Showing candidates for <strong>{focusedSignalId}</strong>. This tab has {visibleItems.length} matching item(s); all review states have {focusedCandidateTotal} matching item(s).
              </div>
            </div>
            <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
              <button
                type="button"
                onClick={() => setActiveView("pending")}
                style={activeView === "pending" ? activeFilterButtonStyle : filterButtonStyle}
              >
                Pending ({focusedPendingCount})
              </button>
              <button
                type="button"
                onClick={() => setActiveView("closed")}
                style={activeView === "closed" ? activeFilterButtonStyle : filterButtonStyle}
              >
                Closed ({focusedClosedCount})
              </button>
              <button
                type="button"
                onClick={() => setActiveView("watch")}
                style={activeView === "watch" ? activeFilterButtonStyle : filterButtonStyle}
              >
                Watch ({focusedWatchCount})
              </button>
              <button
                type="button"
                onClick={() => setActiveView("action")}
                style={activeView === "action" ? activeFilterButtonStyle : filterButtonStyle}
              >
                Action ({focusedActionCount})
              </button>
            </div>
            <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
              <Link href={`/signals/detail?id=${encodeURIComponent(focusedSignalId)}`} style={secondaryLinkStyle}>
                Back to Signal
              </Link>
              <Link href="/workspace/projects/review" style={secondaryLinkStyle}>
                Show All Review Inbox
              </Link>
            </div>
          </section>
        ) : null}
        {activeView !== "records" ? (
          <section style={candidateFilterPanelStyle}>
            <div>
              <div style={summaryLabelStyle}>Candidate Focus</div>
              <div style={{ color: "var(--app-text-muted)", fontSize: "13px", lineHeight: 1.6, marginTop: "4px" }}>
                Manual overrides bypassed the normal gate; Knowledge Convergence candidates came from supply/demand synthesis and still need human review.
              </div>
            </div>
            <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
              <button
                type="button"
                onClick={() => setCandidateQualityFilter("all")}
                style={candidateQualityFilter === "all" ? activeFilterButtonStyle : filterButtonStyle}
              >
                All Candidates ({candidateSourceItems.length})
              </button>
              <button
                type="button"
                onClick={() => setCandidateQualityFilter("manual_override")}
                style={candidateQualityFilter === "manual_override" ? activeFilterButtonStyle : filterButtonStyle}
              >
                Manual Overrides ({manualOverrideCandidateCount})
              </button>
              <button
                type="button"
                onClick={() => setCandidateQualityFilter("manual_source")}
                style={candidateQualityFilter === "manual_source" ? activeFilterButtonStyle : filterButtonStyle}
              >
                Manual Source ({manualSourceCandidateCount})
              </button>
              <button
                type="button"
                onClick={() => setCandidateQualityFilter("knowledge_convergence")}
                style={candidateQualityFilter === "knowledge_convergence" ? activeFilterButtonStyle : filterButtonStyle}
              >
                Knowledge Convergence ({knowledgeConvergenceCandidateCount})
              </button>
              <button
                type="button"
                onClick={() => setCandidateQualityFilter("knowledge_missing_project_fit")}
                style={candidateQualityFilter === "knowledge_missing_project_fit" ? activeFilterButtonStyle : filterButtonStyle}
              >
                Missing Project Fit ({knowledgeMissingProjectFitCandidateCount})
              </button>
            </div>
          </section>
        ) : null}
        {confirmedItem ? (
          <div style={successCardStyle}>
            <div style={{ fontWeight: 800, color: "#166534" }}>
              Project takeaway confirmed.
            </div>
            <div style={{ marginTop: "6px", color: "#14532d", fontSize: "14px", lineHeight: "1.6" }}>
              It is now in Project Takeaways under {confirmedItem.project_name || confirmedItem.project_id || "the selected project"}.
            </div>
            <div style={{ marginTop: "10px", display: "flex", gap: "10px", flexWrap: "wrap" }}>
              <Link href="/workspace/projects" style={successLinkStyle}>
                Open Project Takeaways
              </Link>
              {confirmedItem.project_id && confirmedItem.signal_id ? (
                <Link
                  href={`/workspace/projects/improvement-detail?project_id=${encodeURIComponent(confirmedItem.project_id)}&signal_id=${encodeURIComponent(confirmedItem.signal_id)}`}
                  style={successLinkStyle}
                >
                  Open Confirmed Improvement
                </Link>
              ) : null}
            </div>
          </div>
        ) : null}
        {closedItem ? (
          <div style={noticeCardStyle}>
            <div style={{ fontWeight: 800, color: "#374151" }}>
              Project takeaway candidate {closedItem.status === "action_completed" ? "completed as action" : closedItem.status === "action" ? "added to action" : closedItem.status === "watch" ? "added to watch" : closedItem.status === "dismissed" ? "dismissed" : "rejected"}.
            </div>
            <div style={{ marginTop: "6px", color: "#4b5563", fontSize: "14px", lineHeight: "1.6" }}>
              It has been removed from the active review inbox.
            </div>
          </div>
        ) : null}

        {activeView === "records" ? (
          <section style={reviewCalibrationPlanStyle}>
            <div style={operatingSurfaceHeaderStyle}>
              <div>
                <span style={summaryLabelStyle}>Review Quality Operating Surface</span>
                <strong style={operatingSurfaceTitleStyle}>Records, Knowledge Fit, and Metrics Calibration</strong>
              </div>
              <Link href="/admin/metrics" style={secondaryLinkStyle}>
                Open Admin Metrics
              </Link>
            </div>
            <div style={operatingSurfaceGridStyle}>
              <div style={operatingSurfaceCardStyle}>
                <span style={summaryLabelStyle}>Review Records</span>
                <strong>{reviewCalibrationActions[0]?.label || "Continue Baseline"}</strong>
                <span>{reviewCalibrationActions[0]?.detail || "Keep collecting review records as the calibration baseline."}</span>
                <div style={operatingSurfaceMetricRowStyle}>
                  <span>Blocked rate {formatRate(calibrationFocusSummary.blocked_action_rate)}</span>
                  <span>Gate conflicts {calibrationFocusSummary.gate_conflict_record_count || 0}</span>
                </div>
                <div style={gateComparisonActionRowStyle}>
                  <button type="button" onClick={() => focusRecordQuality("gate_conflicts")} style={gateComparisonButtonStyle}>
                    Gate Conflicts
                  </button>
                  <button type="button" onClick={() => focusRecordQuality("action_blocked")} style={gateComparisonButtonStyle}>
                    Action Blocks
                  </button>
                </div>
              </div>
              <div style={operatingSurfaceCardStyle}>
                <span style={summaryLabelStyle}>Knowledge Fit</span>
                <strong>{knowledgeOperatingSummary.posture}</strong>
                <span>{knowledgeOperatingSummary.next}</span>
                <div style={operatingSurfaceMetricRowStyle}>
                  <span>Pending {knowledgeOperatingSummary.total}</span>
                  <span>Strong fit {knowledgeOperatingSummary.strongFitCount}</span>
                  <span>Missing project fit {knowledgeOperatingSummary.missingProjectFitCount}</span>
                  <span>Watch-ready {knowledgeOperatingSummary.watchReadyCount}</span>
                  <span>Action blocked {knowledgeOperatingSummary.actionBlockedCount}</span>
                </div>
                <div style={gateComparisonActionRowStyle}>
                  <button
                    type="button"
                    onClick={() => {
                      setActiveView("pending");
                      setCandidateQualityFilter(
                        knowledgeOperatingSummary.missingProjectFitCount > 0
                          ? "knowledge_missing_project_fit"
                          : "knowledge_convergence"
                      );
                    }}
                    style={gateComparisonButtonStyle}
                  >
                    Review Knowledge Fit
                  </button>
                  <Link href="/knowledge" style={secondaryLinkStyle}>
                    Open Knowledge
                  </Link>
                </div>
              </div>
              <div style={operatingSurfaceCardStyle}>
                <span style={summaryLabelStyle}>Metrics Calibration</span>
                <strong>{metricsOperatingSummary.posture}</strong>
                <span>{metricsOperatingSummary.next}</span>
                <div style={operatingSurfaceMetricRowStyle}>
                  <span>Records {metricsOperatingSummary.recordCount}</span>
                  <span>Calibration events {metricsOperatingSummary.calibrationCount}</span>
                  <span>Latest {metricsOperatingSummary.latest}</span>
                </div>
                <Link href="/admin/metrics" style={secondaryLinkStyle}>
                  Check Metrics Status
                </Link>
              </div>
            </div>
            <span style={summaryLabelStyle}>Records Calibration Focus</span>
            <div style={reviewCalibrationActionGridStyle}>
              {reviewCalibrationActions.map((action) => (
                <div key={action.label} style={reviewCalibrationActionStyle}>
                  <strong>{action.label}</strong>
                  <span>{action.detail}</span>
                </div>
              ))}
            </div>
          </section>
        ) : null}

        {activeView === "records" ? (
          recordsLoading && records.length === 0 ? (
            <div style={{ color: "var(--app-text-muted)" }}>Loading project review records...</div>
          ) : (
            <div style={{ display: "grid", gap: "14px" }}>
              {recordsLoading ? (
                <div style={refreshingNoticeStyle}>
                  Refreshing records and calibration summaries while keeping the current list visible.
                </div>
              ) : null}
              <section style={summaryBandStyle}>
                <div style={summaryMetricRowStyle}>
                  <SummaryMetric label="Total" value={calibrationFocusSummary.total_records || 0} />
                  <SummaryMetric label="Actionable" value={calibrationFocusSummary.actionable_count || 0} />
                  <SummaryMetric label="Watch" value={calibrationFocusSummary.watch_count || 0} />
                  <SummaryMetric label="Low Confidence" value={calibrationFocusSummary.low_confidence_count || 0} />
                  <SummaryMetric label="Blocked Rate" value={formatRate(calibrationFocusSummary.blocked_action_rate)} />
                  <SummaryMetric label="Gate Conflicts" value={calibrationFocusSummary.gate_conflict_record_count || 0} />
                  <SummaryMetric label="Latest" value={calibrationFocusSummary.latest_reviewed_at || "n/a"} />
                </div>
                <OpsInterpretation
                  title="Review Ops Interpretation"
                  interpretation={buildReviewOpsInterpretation(calibrationFocusSummary)}
                />
                {manualSourceLearningSummary.hasManualLearning ? (
                  <div style={manualSourceLearningStyle}>
                    <div style={operatingSurfaceHeaderStyle}>
                      <div>
                        <span style={summaryLabelStyle}>Manual Source Learning</span>
                        <strong style={operatingSurfaceTitleStyle}>
                          User-selected material is now part of the review/calibration loop.
                        </strong>
                      </div>
                      <div style={operatingSurfaceMetricRowStyle}>
                        <span>Records {manualSourceLearningSummary.manualRecords}</span>
                        <span>Events {manualSourceLearningSummary.manualEvents}</span>
                        <span>Watch {manualSourceLearningSummary.manualWatch}</span>
                        <span>Actionable {manualSourceLearningSummary.manualActionable}</span>
                      </div>
                    </div>
                    <div style={reviewCalibrationActionGridStyle}>
                      <div style={reviewCalibrationActionStyle}>
                        <span style={summaryLabelStyle}>Achieved</span>
                        <strong>{manualSourceLearningSummary.achieved}</strong>
                      </div>
                      <div style={reviewCalibrationActionStyle}>
                        <span style={summaryLabelStyle}>Gap</span>
                        <strong>{manualSourceLearningSummary.gap}</strong>
                      </div>
                      <div style={reviewCalibrationActionStyle}>
                        <span style={summaryLabelStyle}>Next Focus</span>
                        <strong>{manualSourceLearningSummary.next}</strong>
                      </div>
                    </div>
                  </div>
                ) : null}
                <div style={reviewCalibrationPlanStyle}>
                  <span style={summaryLabelStyle}>Calibration Focus</span>
                  <div style={reviewCalibrationActionGridStyle}>
                    {reviewCalibrationActions.map((action) => (
                      <div key={action.label} style={reviewCalibrationActionStyle}>
                        <strong>{action.label}</strong>
                        <span>{action.detail}</span>
                      </div>
                    ))}
                  </div>
                </div>
                {recordSummary ? (
                  <details style={summaryDetailsStyle}>
                    <summary style={summaryDetailsSummaryStyle}>Review Details</summary>
                    <div style={summaryBreakdownStyle}>
                      <span style={summaryLabelStyle}>Outcome Mix</span>
                      <div style={summaryChipRowStyle}>
                        <span style={summaryMiniChipStyle}>Confirmed {countValue(recordSummary.outcome_counts, "confirmed")}</span>
                        <span style={summaryMiniChipStyle}>Watch {countValue(recordSummary.outcome_counts, "watch")}</span>
                        <span style={summaryMiniChipStyle}>Action {countValue(recordSummary.outcome_counts, "action")}</span>
                        <span style={summaryMiniChipStyle}>Completed {countValue(recordSummary.outcome_counts, "action_completed")}</span>
                        <span style={summaryMiniChipStyle}>Rejected {countValue(recordSummary.outcome_counts, "rejected")}</span>
                        <span style={summaryMiniChipStyle}>Dismissed {countValue(recordSummary.outcome_counts, "dismissed")}</span>
                      </div>
                    </div>
                    <div style={summaryBreakdownStyle}>
                      <span style={summaryLabelStyle}>Verification Quality</span>
                      <div style={summaryChipRowStyle}>
                        <span style={summaryMiniChipStyle}>Verified {countValue(recordSummary.verification_status_counts, "verified")}</span>
                        <span style={summaryMiniChipStyle}>Partial {countValue(recordSummary.verification_status_counts, "partially_verified")}</span>
                        <span style={summaryMiniChipStyle}>Weak {countValue(recordSummary.verification_status_counts, "weakly_supported")}</span>
                        <span style={summaryMiniChipStyle}>Unsupported Claims {recordSummary.unsupported_claim_count || 0}</span>
                        <span style={summaryMiniChipStyle}>Inferred Claims {recordSummary.inferred_claim_count || 0}</span>
                        <span style={summaryMiniChipStyle}>Blocked Records {recordSummary.records_with_blocked_actions || 0}</span>
                        <span style={summaryMiniChipStyle}>Action Blocked {recordSummary.records_with_action_blocked || 0}</span>
                        <span style={summaryMiniChipStyle}>Gate Conflicts {recordSummary.gate_conflict_record_count || 0}</span>
                        <span style={summaryMiniChipStyle}>Watch With Action Blocked {recordSummary.watch_outcomes_with_action_blocked || 0}</span>
                      </div>
                    </div>
                    <div style={summaryBreakdownStyle}>
                      <span style={summaryLabelStyle}>Action Gate Outcomes</span>
                      <div style={summaryChipRowStyle}>
                        <span style={summaryMiniChipStyle}>Action Outcomes Blocked {recordSummary.action_outcomes_with_blocked_gate || 0}</span>
                        <span style={summaryMiniChipStyle}>Override Blocked Action {recordSummary.manual_overrides_with_blocked_action || 0}</span>
                        <span style={summaryMiniChipStyle}>Gate Conflict Records {recordSummary.gate_conflict_record_count || 0}</span>
                      </div>
                    </div>
                    <div style={summaryBreakdownStyle}>
                      <span style={summaryLabelStyle}>Source Mix</span>
                      <div style={summaryChipRowStyle}>
                        <span style={summaryMiniChipStyle}>Signals {countValue(recordSummary.source_type_counts, "signal")}</span>
                        <span style={summaryMiniChipStyle}>Manual Uploads {recordSummary.manual_record_count || 0}</span>
                        <span style={summaryMiniChipStyle}>Manual Watch {recordSummary.manual_watch_count || 0}</span>
                        <span style={summaryMiniChipStyle}>Manual Actionable {recordSummary.manual_actionable_count || 0}</span>
                      </div>
                    </div>
                    {recordSummary.blocked_action_counts && Object.keys(recordSummary.blocked_action_counts).length > 0 ? (
                      <div style={summaryBreakdownStyle}>
                        <span style={summaryLabelStyle}>Blocked Action Mix</span>
                        <div style={summaryChipRowStyle}>
                          {Object.entries(recordSummary.blocked_action_counts).map(([action, count]) => (
                            <span key={action} style={summaryMiniChipStyle}>
                              {formatLabel(action)} {count}
                            </span>
                          ))}
                        </div>
                      </div>
                    ) : null}
                  </details>
                ) : null}
              </section>
              {calibrationSummary ? (
                <details style={calibrationBandStyle}>
                  <summary style={summaryDetailsSummaryStyle}>
                    Calibration: {calibrationSummary.total_events || 0} events / {formatRate(calibrationSummary.candidate_to_actionable_rate)} actionable rate / {calibrationSummary.manual_event_count || 0} manual / {calibrationSummary.gate_conflict_event_count || 0} gate conflicts
                  </summary>
                  <div style={summaryMetricRowStyle}>
                    <SummaryMetric label="Calibration Events" value={calibrationSummary.total_events || 0} />
                    <SummaryMetric label="Actionable Events" value={calibrationSummary.actionable_event_count || 0} />
                    <SummaryMetric label="Candidate Reviews" value={calibrationSummary.candidate_review_event_count || 0} />
                    <SummaryMetric label="Actionable Rate" value={formatRate(calibrationSummary.candidate_to_actionable_rate)} />
                    <SummaryMetric label="Rejection Rate" value={formatRate(calibrationSummary.takeaway_rejection_rate)} />
                    <SummaryMetric label="Low Confidence Events" value={calibrationSummary.low_confidence_event_count || 0} />
                    <SummaryMetric label="Blocked Event Rate" value={formatRate(calibrationSummary.blocked_action_rate)} />
                    <SummaryMetric label="Gate Conflicts" value={calibrationSummary.gate_conflict_event_count || 0} />
                    <SummaryMetric label="Unsupported Claims" value={calibrationSummary.unsupported_claim_count || 0} />
                    <SummaryMetric label="Inferred Claims" value={calibrationSummary.inferred_claim_count || 0} />
                    <SummaryMetric label="Latest Event" value={calibrationSummary.latest_event_at || "n/a"} />
                  </div>
                  <div style={summaryBreakdownStyle}>
                    <span style={summaryLabelStyle}>Event Mix</span>
                    <div style={summaryChipRowStyle}>
                      <span style={summaryMiniChipStyle}>Accepted {countValue(calibrationSummary.event_counts, "takeaway_accepted")}</span>
                      <span style={summaryMiniChipStyle}>Watch Created {countValue(calibrationSummary.event_counts, "watch_item_created")}</span>
                      <span style={summaryMiniChipStyle}>Action Created {countValue(calibrationSummary.event_counts, "action_item_created")}</span>
                      <span style={summaryMiniChipStyle}>Action Completed {countValue(calibrationSummary.event_counts, "action_item_completed")}</span>
                      <span style={summaryMiniChipStyle}>Rejected {countValue(calibrationSummary.event_counts, "takeaway_rejected")}</span>
                      <span style={summaryMiniChipStyle}>Dismissed {countValue(calibrationSummary.event_counts, "takeaway_dismissed")}</span>
                    </div>
                  </div>
                  <div style={summaryBreakdownStyle}>
                    <span style={summaryLabelStyle}>Verification Learning</span>
                    <div style={summaryChipRowStyle}>
                      <span style={summaryMiniChipStyle}>Verified {countValue(calibrationSummary.verification_status_counts, "verified")}</span>
                      <span style={summaryMiniChipStyle}>Partial {countValue(calibrationSummary.verification_status_counts, "partially_verified")}</span>
                      <span style={summaryMiniChipStyle}>Weak {countValue(calibrationSummary.verification_status_counts, "weakly_supported")}</span>
                      <span style={summaryMiniChipStyle}>Low Confidence {calibrationSummary.low_confidence_event_count || 0}</span>
                      <span style={summaryMiniChipStyle}>Blocked Events {calibrationSummary.events_with_blocked_actions || 0}</span>
                      <span style={summaryMiniChipStyle}>Action Blocked {calibrationSummary.events_with_action_blocked || 0}</span>
                      <span style={summaryMiniChipStyle}>Gate Conflicts {calibrationSummary.gate_conflict_event_count || 0}</span>
                    </div>
                  </div>
                  <div style={summaryBreakdownStyle}>
                    <span style={summaryLabelStyle}>Calibration Gate Outcomes</span>
                    <div style={summaryChipRowStyle}>
                      <span style={summaryMiniChipStyle}>Watch With Action Blocked {calibrationSummary.watch_events_with_action_blocked || 0}</span>
                      <span style={summaryMiniChipStyle}>Action Events Blocked {calibrationSummary.action_events_with_blocked_gate || 0}</span>
                      <span style={summaryMiniChipStyle}>Override Blocked Action {calibrationSummary.manual_overrides_with_blocked_action || 0}</span>
                      <span style={summaryMiniChipStyle}>Gate Conflict Events {calibrationSummary.gate_conflict_event_count || 0}</span>
                    </div>
                  </div>
                  <div style={summaryBreakdownStyle}>
                    <span style={summaryLabelStyle}>Source Learning</span>
                    <div style={summaryChipRowStyle}>
                      <span style={summaryMiniChipStyle}>Signals {countValue(calibrationSummary.source_type_counts, "signal")}</span>
                      <span style={summaryMiniChipStyle}>Manual Uploads {calibrationSummary.manual_event_count || 0}</span>
                      <span style={summaryMiniChipStyle}>Manual Watch {calibrationSummary.manual_watch_event_count || 0}</span>
                      <span style={summaryMiniChipStyle}>Manual Actionable {calibrationSummary.manual_actionable_event_count || 0}</span>
                    </div>
                  </div>
                  {calibrationSummary.blocked_action_counts && Object.keys(calibrationSummary.blocked_action_counts).length > 0 ? (
                    <div style={summaryBreakdownStyle}>
                      <span style={summaryLabelStyle}>Calibration Blocked Action Mix</span>
                      <div style={summaryChipRowStyle}>
                        {Object.entries(calibrationSummary.blocked_action_counts).map(([action, count]) => (
                          <span key={action} style={summaryMiniChipStyle}>
                            {formatLabel(action)} {count}
                          </span>
                        ))}
                      </div>
                    </div>
                  ) : null}
                  <OpsInterpretation
                    title="Calibration Ops Interpretation"
                    interpretation={buildCalibrationOpsInterpretation(calibrationSummary)}
                  />
                </details>
              ) : null}
              {recordSummary && calibrationSummary ? (
                <details style={advancedReviewDetailsStyle}>
                  <summary style={summaryDetailsSummaryStyle}>
                    Advanced gate alignment: {recordSummary.gate_conflict_record_count || 0} record conflict(s) / {calibrationSummary.gate_conflict_event_count || 0} calibration conflict(s)
                  </summary>
                  <div style={{ marginTop: "12px" }}>
                    <GateComparisonReadout
                      recordSummary={recordSummary}
                      calibrationSummary={calibrationSummary}
                      onShowActionBlocked={() => focusRecordQuality("action_blocked")}
                      onShowGateConflicts={() => focusRecordQuality("gate_conflicts")}
                      onShowManualOverrides={() => focusRecordQuality("manual_override")}
                      onShowWatchActionBlocked={() => focusRecordQuality("watch_action_blocked")}
                    />
                  </div>
                </details>
              ) : null}
              <details style={manualOverrideCalibrationBandStyle}>
                <summary style={summaryDetailsSummaryStyle}>
                  Manual override calibration: {manualOverrideCalibration.total} override record{manualOverrideCalibration.total === 1 ? "" : "s"}
                </summary>
                <div style={{ ...manualOverrideCalibrationHeaderStyle, marginTop: "12px" }}>
                  <button
                    type="button"
                    onClick={() => {
                      setRecordQualityFilter("manual_override");
                      setRecordOutcomeFilter("all");
                    }}
                    style={recordQualityFilter === "manual_override" ? activeFilterButtonStyle : filterButtonStyle}
                  >
                    Show Manual Overrides
                  </button>
                </div>
                <div style={summaryMetricRowStyle}>
                  <SummaryMetric label="Overrides" value={manualOverrideCalibration.total} />
                  <SummaryMetric label="Actionable" value={manualOverrideCalibration.actionableCount} />
                  <SummaryMetric label="Watch" value={manualOverrideCalibration.watchCount} />
                  <SummaryMetric label="Rejected / Dismissed" value={manualOverrideCalibration.rejectedOrDismissedCount} />
                  <SummaryMetric label="Actionable Rate" value={formatRate(manualOverrideCalibration.actionableRate)} />
                  <SummaryMetric label="Rejection Rate" value={formatRate(manualOverrideCalibration.rejectionRate)} />
                  <SummaryMetric label="Risk Records" value={manualOverrideCalibration.riskCount} />
                  <SummaryMetric label="Completed Actions" value={manualOverrideCalibration.actionCompletedCount} />
                  <SummaryMetric label="Latest Override" value={manualOverrideCalibration.latestReviewedAt || "n/a"} />
                </div>
                <div style={summaryBreakdownStyle}>
                  <span style={summaryLabelStyle}>Override Outcome Mix</span>
                  <div style={summaryChipRowStyle}>
                    <span style={summaryMiniChipStyle}>Confirmed {countValue(manualOverrideCalibration.outcomeCounts, "confirmed")}</span>
                    <span style={summaryMiniChipStyle}>Watch {countValue(manualOverrideCalibration.outcomeCounts, "watch")}</span>
                    <span style={summaryMiniChipStyle}>Action {countValue(manualOverrideCalibration.outcomeCounts, "action")}</span>
                    <span style={summaryMiniChipStyle}>Completed {countValue(manualOverrideCalibration.outcomeCounts, "action_completed")}</span>
                    <span style={summaryMiniChipStyle}>Rejected {countValue(manualOverrideCalibration.outcomeCounts, "rejected")}</span>
                    <span style={summaryMiniChipStyle}>Dismissed {countValue(manualOverrideCalibration.outcomeCounts, "dismissed")}</span>
                  </div>
                </div>
                <OpsInterpretation
                  title="Override Calibration Readout"
                  interpretation={buildManualOverrideCalibrationInterpretation(manualOverrideCalibration)}
                />
              </details>
              <section ref={recordsFilterRef} style={recordFilterPanelStyle}>
                <div style={recordFilterTopRowStyle}>
                  <div style={recordFilterTitleStyle}>
                    <span style={summaryLabelStyle}>Record Filter</span>
                    <strong style={summaryValueStyle}>{visibleRecords.length} shown</strong>
                    {recordsLastLoadedAt ? <span style={recordFilterHintStyle}>Updated {recordsLastLoadedAt}</span> : null}
                  </div>
                  <div style={recordFilterTopActionsStyle}>
                    <div style={recordFilterInlineGroupStyle}>
                      <span style={summaryLabelStyle}>Sort</span>
                      <div style={recordFilterButtonRowStyle}>
                        <button
                          type="button"
                          onClick={() => setRecordSortOrder("newest")}
                          style={recordSortOrder === "newest" ? activeFilterButtonStyle : filterButtonStyle}
                        >
                          Newest
                        </button>
                        <button
                          type="button"
                          onClick={() => setRecordSortOrder("oldest")}
                          style={recordSortOrder === "oldest" ? activeFilterButtonStyle : filterButtonStyle}
                        >
                          Oldest
                        </button>
                      </div>
                    </div>
                    <div style={recordFilterInlineGroupStyle}>
                      <span style={summaryLabelStyle}>Actions</span>
                      <div style={recordFilterActionRowStyle}>
                        <button
                          type="button"
                          onClick={() => void loadReviewRecords({ clearVisibleError: true, keepExistingOnError: true })}
                          disabled={recordsLoading}
                          style={resetFilterButtonStyle}
                        >
                          {recordsLoading ? "Refreshing..." : "Refresh"}
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            setRecordOutcomeFilter("all");
                            setRecordQualityFilter("all");
                            setRecordProjectFilter("all");
                            setRecordSearch("");
                            setRecordSortOrder("newest");
                          }}
                          style={resetFilterButtonStyle}
                        >
                          Reset
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
                <div style={recordFilterBoxStyle}>
                  <span style={summaryLabelStyle}>Current View</span>
                  <div style={recordFilterSummaryStyle}>{filterSummaryText}</div>
                  <div style={recordFilterHintStyle}>
                    Filter counts update with the current search and selected filters.
                  </div>
                </div>
                <div style={recordFilterBoxStyle}>
                  <span style={summaryLabelStyle}>Search</span>
                  <input
                    type="search"
                    value={recordSearch}
                    onChange={(event) => setRecordSearch(event.target.value)}
                    placeholder="Search project, signal, reason, or status"
                    style={recordSearchInputStyle}
                  />
                </div>
                <div style={recordFilterBoxStyle}>
                  <span style={summaryLabelStyle}>Projects</span>
                  <div style={recordFilterButtonRowStyle}>
                    {recordProjectFilters.map((filter) => (
                      <button
                        key={filter.value}
                        type="button"
                        onClick={() => setRecordProjectFilter(filter.value)}
                        style={recordProjectFilter === filter.value ? activeFilterButtonStyle : filterButtonStyle}
                      >
                        {filter.label} ({filter.count})
                      </button>
                    ))}
                  </div>
                </div>
                <div style={recordFilterBoxStyle}>
                  <span style={summaryLabelStyle}>Outcomes</span>
                  <div style={recordFilterButtonRowStyle}>
                    {recordOutcomeFilters.map((filter) => (
                      <button
                        key={filter.value}
                        type="button"
                        onClick={() => setRecordOutcomeFilter(filter.value)}
                        style={recordOutcomeFilter === filter.value ? activeFilterButtonStyle : filterButtonStyle}
                      >
                        {filter.label} ({filter.value === "all" ? recordsMatchingProjectAndSearch.length : countValue(dynamicOutcomeCounts, filter.value)})
                      </button>
                    ))}
                  </div>
                </div>
                <div style={recordFilterBoxStyle}>
                  <span style={summaryLabelStyle}>Quality</span>
                  <div style={recordFilterButtonRowStyle}>
                    {recordQualityFilters.map((filter) => (
                      <button
                        key={filter.value}
                        type="button"
                        onClick={() => setRecordQualityFilter(filter.value)}
                        style={recordQualityFilter === filter.value ? activeFilterButtonStyle : filterButtonStyle}
                      >
                        {filter.label} ({qualityFilterCount(filter.value)})
                      </button>
                    ))}
                  </div>
                </div>
              </section>
              {visibleRecords.length === 0 ? (
                <div style={emptyCardStyle}>
                  <strong style={emptyTitleStyle}>
                    {records.length === 0 ? "No review records yet" : "No records match this view"}
                  </strong>
                  <p style={emptyDescriptionStyle}>
                    {records.length === 0
                      ? "Review records are created when Project Takeaway candidates are confirmed, watched, acted on, rejected, dismissed, or completed."
                      : `Current view: ${filterSummaryText}. Try broadening the project, outcome, quality, or search filters.`}
                  </p>
                  <div style={recordFilterActionRowStyle}>
                    {hasActiveRecordFilters ? (
                      <button type="button" onClick={resetRecordFilters} style={filterButtonStyle}>
                        Reset Filters
                      </button>
                    ) : null}
                    <Link href="/workspace/projects/review" style={secondaryLinkStyle}>
                      Review Inbox
                    </Link>
                    <Link href="/workspace/projects" style={secondaryLinkStyle}>
                      Project Takeaways
                    </Link>
                  </div>
                </div>
              ) : null}
              {visibleRecords.map((record, index) => (
                (() => {
                  const recordEligibility = getRecordActionEligibility(record);
                  const recordActionGate = recordEligibility?.low_risk_action_candidate;
                  const recordVerifiedInsightObjectRows = buildRecordVerifiedInsightObjectRows(record, recordEligibility);
                  const showRecordVerifiedInsightObject = hasRecordVerifiedInsightObjectSurface(record, recordEligibility);
                  return (
                    <section
                      key={record.id || index}
                      style={record.manual_project_takeaway_override ? manualOverrideRecordCardStyle : candidateCardStyle}
                    >
                  <div style={{ display: "flex", justifyContent: "space-between", gap: "18px", alignItems: "start" }}>
                    <div>
                      <button
                        type="button"
                        onClick={() => setRecordProjectFilter(record.project_id || "all")}
                        title="Filter records by this project"
                        style={projectFilterLinkStyle}
                      >
                        {record.project_name || record.project_id || "Unknown project"}
                      </button>
                      <div style={candidateTitleStyle}>
                        {record.signal_title || record.signal_id || "Untitled review record"}
                      </div>
                    </div>
                    {record.outcome ? (
                      <button
                        type="button"
                        onClick={() => setRecordOutcomeFilter((record.outcome || "all") as RecordOutcomeFilter)}
                        title="Filter records by this outcome"
                        style={getOutcomeChipButtonStyle(record.outcome)}
                      >
                        {formatLabel(record.outcome)}
                      </button>
                    ) : null}
                  </div>

                  <div style={recordSummaryLineStyle}>
                    {buildRecordCardSummary(record)}
                  </div>
                  <div style={recordLearningSignalStyle}>
                    {buildRecordLearningSignal(record)}
                  </div>

                  {showRecordVerifiedInsightObject ? (
                    <VerifiedInsightObjectPanel
                      rows={recordVerifiedInsightObjectRows}
                      subtitle="Recorded verification boundary for this Project Review decision. It preserves review context but does not reopen gates or change action eligibility."
                      style={{ marginTop: "12px" }}
                    />
                  ) : null}

                  {recordEligibility ? (
                    <div style={recordEligibilityPanelStyle}>
                      <div style={actionEligibilityHeaderStyle}>
                        <span style={detailLabelStyle}>Recorded Gate</span>
                        <strong>
                          {recordActionGate?.allowed === false
                            ? record.manual_project_takeaway_override
                              ? "Override carried blocked action context"
                              : "Action was blocked"
                            : "Action was eligible after review"}
                        </strong>
                      </div>
                      <VerificationGateNote
                        verification={{
                          verification_status: recordEligibility.signals?.verification_status || record.verification_status || "",
                          allowed_downstream_actions: recordEligibility.signals?.allowed_downstream_actions || record.allowed_downstream_actions || [],
                          blocked_downstream_actions: recordEligibility.signals?.blocked_downstream_actions || record.blocked_downstream_actions || [],
                          claim_support_summary: {
                            unsupported: recordEligibility.signals?.unsupported_or_contradicted_claim_count ?? record.unsupported_claim_count ?? 0,
                            inferred: recordEligibility.signals?.inferred_claim_count ?? record.inferred_claim_count ?? 0,
                          },
                        }}
                        accentColor={recordActionGate?.allowed === false ? "#b91c1c" : "#9ca3af"}
                        background="#fff"
                        style={{ marginTop: "10px" }}
                      />
                      <div style={actionEligibilityGridStyle}>
                        <div style={detailItemStyle}>
                          <span style={detailLabelStyle}>Project Takeaway</span>
                          <strong>{recordEligibility.project_takeaway_candidate?.allowed === false ? "Blocked" : "Allowed"}</strong>
                          <span>{recordEligibility.project_takeaway_candidate?.reason || "No Project Takeaway gate reason recorded."}</span>
                        </div>
                        <div style={detailItemStyle}>
                          <span style={detailLabelStyle}>Watch</span>
                          <strong>{recordEligibility.watch_only?.allowed === false ? "Not suggested" : "Suggested"}</strong>
                          <span>{recordEligibility.watch_only?.reason || "No Watch gate reason recorded."}</span>
                        </div>
                        <div style={detailItemStyle}>
                          <span style={detailLabelStyle}>Action</span>
                          <strong>{recordActionGate?.allowed === false ? "Blocked" : "Allowed"}</strong>
                          <span>{recordActionGate?.reason || "No Action gate reason recorded."}</span>
                        </div>
                      </div>
                      <div style={actionEligibilitySignalStyle}>
                        Status: {formatLabel(recordEligibility.signals?.verification_status) || "n/a"} / Unsupported or contradicted:{" "}
                        {recordEligibility.signals?.unsupported_or_contradicted_claim_count ?? 0} / Inferred:{" "}
                        {recordEligibility.signals?.inferred_claim_count ?? 0} / Blocked actions:{" "}
                        {formatActionList(recordEligibility.signals?.blocked_downstream_actions)}
                      </div>
                    </div>
                  ) : null}

                  {record.manual_project_takeaway_override ? (
                    <div style={manualOverrideOutcomeStyle}>
                      <span style={detailLabelStyle}>Override Outcome</span>
                      <strong>{buildManualOverrideOutcomeInterpretation(record)}</strong>
                    </div>
                  ) : null}

                  <div style={recordContextGridStyle}>
                    <div style={recordContextCardStyle}>
                      <span style={detailLabelStyle}>Why This Matters</span>
                      <strong>{buildRecordImportance(record)}</strong>
                    </div>
                    <div style={recordContextCardStyle}>
                      <span style={detailLabelStyle}>Source Context</span>
                      <strong>{buildRecordSourceContext(record)}</strong>
                    </div>
                  </div>

                  <details style={recordDetailsStyle}>
                    <summary style={summaryDetailsSummaryStyle}>Record Details</summary>
                    <div style={recordMetaGridStyle}>
                      <div style={recordMetaItemStyle}>
                        <span style={detailLabelStyle}>Reason</span>
                        <strong>{record.reason || "Not provided"}</strong>
                      </div>
                      <div style={recordMetaItemStyle}>
                        <span style={detailLabelStyle}>Source</span>
                        <strong>{formatRecordSource(record)}</strong>
                      </div>
                      {record.manual_project_takeaway_override ? (
                        <div style={recordMetaItemStyle}>
                          <span style={detailLabelStyle}>Manual Override</span>
                          <strong>{record.manual_override_note || "Reviewer manually selected this candidate."}</strong>
                        </div>
                      ) : null}
                      {record.is_manual_source || record.upload_reason || record.intended_use ? (
                        <div style={recordMetaItemStyle}>
                          <span style={detailLabelStyle}>Manual Intent</span>
                          <strong>
                            {record.upload_reason || record.intended_use
                              ? [record.upload_reason, record.intended_use].filter(Boolean).join(" / ")
                              : "Not captured"}
                          </strong>
                        </div>
                      ) : null}
                      {record.is_manual_source || record.cognitive_layer ? (
                        <div style={recordMetaItemStyle}>
                          <span style={detailLabelStyle}>Cognitive Layer</span>
                          <strong>{formatLabel(record.cognitive_layer || "unclassified")}</strong>
                        </div>
                      ) : null}
                      <div style={recordMetaItemStyle}>
                        <span style={detailLabelStyle}>Verification</span>
                        <strong>{record.verification_status ? formatLabel(record.verification_status) : "n/a"}</strong>
                      </div>
                      <div style={recordMetaItemStyle}>
                        <span style={detailLabelStyle}>Confidence</span>
                        <strong>{formatConfidence(record.confidence_label, record.confidence_score)}</strong>
                      </div>
                      <div style={recordMetaItemStyle}>
                        <span style={detailLabelStyle}>Claim Risk</span>
                        <strong>
                          Unsupported {record.unsupported_claim_count || 0} / Inferred {record.inferred_claim_count || 0}
                        </strong>
                      </div>
                      <div style={recordMetaItemStyle}>
                        <span style={detailLabelStyle}>Blocked Actions</span>
                        <strong>{formatActionList(record.blocked_downstream_actions)}</strong>
                      </div>
                      <div style={recordMetaItemStyle}>
                        <span style={detailLabelStyle}>Reviewed</span>
                        <strong>{record.reviewed_at || record.updated_at || "n/a"}</strong>
                      </div>
                    </div>

                    {record.claim_support_summary && Object.keys(record.claim_support_summary).length > 0 ? (
                      <div style={recordVerificationChipRowStyle}>
                        <span style={recordVerificationLabelStyle}>Claim Support</span>
                        {Object.entries(record.claim_support_summary)
                          .filter(([, count]) => count > 0)
                          .map(([supportLevel, count]) => (
                            <span key={supportLevel} style={recordVerificationChipStyle}>
                              {formatLabel(supportLevel)} {count}
                            </span>
                          ))}
                      </div>
                    ) : null}
                  </details>

                  <div style={{ display: "none" }}>
                    <strong>Review record:</strong>
                    {record.reason ? <span> · {record.reason}</span> : null}
                    <span> · {formatRecordSource(record)}</span>
                    {record.verification_status ? <span> · {formatLabel(record.verification_status)}</span> : null}
                    {record.reviewed_at || record.updated_at ? <span> · {record.reviewed_at || record.updated_at}</span> : null}
                  </div>

                  <div style={{ marginTop: "14px", display: "flex", gap: "10px", flexWrap: "wrap" }}>
                    {record.id ? (
                      <Link
                        href={`/workspace/projects/review/record?id=${encodeURIComponent(record.id)}`}
                        style={secondaryLinkStyle}
                      >
                        Open Record Detail
                      </Link>
                    ) : null}
                    {isSignalDetailLinkable(record.signal_id, record.candidate_source) ? (
                      <Link
                        href={`/signals/detail?id=${encodeURIComponent(record.signal_id || "")}&review_signal_id=${encodeURIComponent(record.signal_id || "")}`}
                        style={secondaryLinkStyle}
                      >
                        {focusedSignalId ? "Back to Focused Signal" : "Open Signal Detail"}
                      </Link>
                    ) : null}
                    {record.project_id && record.signal_id ? (
                      <Link
                        href={`/workspace/projects/improvement-detail?project_id=${encodeURIComponent(record.project_id)}&signal_id=${encodeURIComponent(record.signal_id)}`}
                        style={secondaryLinkStyle}
                      >
                        Open Fit Detail
                      </Link>
                    ) : null}
                  </div>
                </section>
                  );
                })()
              ))}
            </div>
          )
        ) : loading && items.length === 0 ? (
          <div style={emptyCardStyle}>
            <div>Loading Review Inbox candidates from /projects/takeaway-candidates...</div>
            <div style={{ marginTop: "12px" }}>
              <button type="button" onClick={() => void loadCandidates()} style={secondaryButtonStyle}>
                Retry Candidates
              </button>
            </div>
          </div>
        ) : visibleItems.length === 0 ? (
          <div style={emptyCardStyle}>
            {focusedSignalId
              ? `No Review Inbox candidate for ${focusedSignalId} appears in the current tab. Check Pending, Closed, Watch, or Action, or show the full Review Inbox.`
              : candidateQualityFilter === "manual_override"
              ? "No manual override candidates match this view. Switch back to All Candidates to see the full queue."
              : candidateQualityFilter === "knowledge_missing_project_fit"
                ? "No Knowledge Convergence candidates are missing project fit in this view. Use Knowledge Convergence for the full synthesis queue."
              : candidateQualityFilter === "knowledge_convergence"
                ? "No Knowledge Convergence candidates match this view. Send a ready brief from Knowledge or switch back to All Candidates."
              : activeView === "pending"
                ? "No project takeaway candidates are waiting for review. Create one from a verified signal Evidence Note."
              : activeView === "watch"
                ? "No project takeaway candidates are on the watch list yet."
                : activeView === "action"
                  ? "No project takeaway candidates are marked for action yet."
                  : "No reviewed project takeaway candidates yet."}
          </div>
        ) : (
          <div style={{ display: "grid", gap: "14px" }}>
            {loading && items.length > 0 ? (
              <div style={refreshingNoticeStyle}>
                Refreshing Review Inbox candidates while keeping the current queue visible.
              </div>
            ) : null}
            {visibleItems.map((item, index) => {
              const key = candidateKey(item.project_id || "project", item.signal_id || String(index));
              const verification = item.verification_metadata || {};
              const candidateModelProvenance = resolveModelProvenance(
                item.produced_by_model,
                verification.produced_by_model,
                verification.verified_insight?.produced_by_model
              );
              const manualOverrideCandidate = isManualOverrideCandidate(item);
              const knowledgeConvergenceCandidate = isKnowledgeConvergenceCandidate(item);
              const knowledgeRationaleRows = buildKnowledgeRationaleRows(verification);
              const knowledgeQualityFactorRows = buildKnowledgeQualityFactorRows(verification);
              const knowledgeReviewPath = buildKnowledgeReviewPath(verification);
              const deepProjectMatchReview = verification.deep_project_match_review || null;
              const showDeepProjectMatchReview = Boolean(
                deepProjectMatchReview?.required || deepProjectMatchReview?.review_note
              );
              const claimSupport = formatClaimSupport(verification.claim_support_summary);
              const rejectActionKey = `${key}:rejected`;
              const dismissActionKey = `${key}:dismissed`;
              const watchActionKey = `${key}:watch`;
              const actionActionKey = `${key}:action`;
              const normalizedStatus = (item.status || "").toLowerCase();
              const actionEligibility = getCandidateActionEligibility(item);
              const verifiedInsightObjectRows = buildVerifiedInsightObjectRows(verification, actionEligibility);
              const showVerifiedInsightObject = hasVerifiedInsightObjectSurface(verification, actionEligibility);
              const projectTakeawayGate = actionEligibility?.project_takeaway_candidate;
              const projectTakeawayBlockedForCandidate = Boolean(projectTakeawayGate && projectTakeawayGate.allowed === false);
              const actionGate = actionEligibility?.low_risk_action_candidate;
              const actionBlockedForCandidate = Boolean(actionGate && actionGate.allowed === false);
              const candidateNextStep = buildCandidateNextStep({
                item,
                activeView,
                actionEligibility,
                actionBlocked: actionBlockedForCandidate,
              });
              const candidateDecisionOptions = buildCandidateDecisionOptions({
                item,
                actionEligibility,
                actionBlocked: actionBlockedForCandidate,
                projectTakeawayBlocked: projectTakeawayBlockedForCandidate,
              });
              const candidateDecisionShortcut = buildCandidateDecisionShortcut({
                item,
                actionEligibility,
                actionBlocked: actionBlockedForCandidate,
                projectTakeawayBlocked: projectTakeawayBlockedForCandidate,
              });
              const confirmedFinalTakeawayHandoff = isConfirmedFinalTakeawayHandoff(item);
              const candidateManualSessionId = getCandidateManualSessionId(item);
              const candidateSourceLabel = getCandidateSourceLabel(item);
              const candidateUploadReason = item.upload_reason || verification.upload_reason || "";
              const candidateIntendedUse = item.intended_use || verification.intended_use || "";
              const candidateCognitiveLayer = item.cognitive_layer || verification.cognitive_layer || "";
              const candidateSimplifiedSnapshot = buildSimplifiedCandidateSnapshot({
                item,
                actionEligibility,
                claimSupport,
                sourceLabel: candidateSourceLabel,
                actionBlocked: actionBlockedForCandidate,
                projectTakeawayBlocked: projectTakeawayBlockedForCandidate,
              });
              const reasoningAssessmentAdvisory = buildReasoningAssessmentAdvisory({
                item,
                actionEligibility,
                claimSupport,
              });
              const counterCheckDraft = counterCheckDraftByKey[key];
              const counterCheckError = counterCheckErrorByKey[key] || "";
              const counterCheckLoading = counterCheckLoadingKey === key;
              const reviewReason =
                item.rejection_reason ||
                item.dismissal_reason ||
                item.watch_reason ||
                item.action_reason ||
                "";
              const actionCompletionNote = item.action_completion_note || "";
              const currentMetadata = metadataByKey[key] || {};
              const overrideError = overrideErrorByKey[key] || "";
              const followupMessage = followupMessageByKey[key] || "";
              const watchFollowupReady = Boolean((currentMetadata.followup_result || "").trim());
              const sharedOverrideNote = (reasonByKey[key] || "").trim();
              const sharedExpectedOutcome = (currentMetadata.action_expected_outcome || "").trim();
              const overrideConfirmReady = Boolean(sharedOverrideNote && sharedExpectedOutcome);
              const overrideActionReady = Boolean(
                sharedOverrideNote &&
                  sharedExpectedOutcome &&
                  (currentMetadata.action_due_date || "").trim() &&
                  (currentMetadata.action_review_date || "").trim()
              );
              const reviewedAt =
                item.reviewed_at ||
                item.confirmed_at ||
                item.rejected_at ||
                item.dismissed_at ||
                item.watched_at ||
                item.action_created_at ||
                item.action_completed_at ||
                item.saved_at ||
                "";
              const simplifiedCandidateMode = reviewDisplayMode === "simplified" && activeView === "pending";

              return (
                <section
                  key={key}
                  style={manualOverrideCandidate ? manualOverrideCandidateCardStyle : candidateCardStyle}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", gap: "18px", alignItems: "start" }}>
                    <div>
                      <div style={metaStyle}>{item.project_name || item.project_id || "Unknown project"}</div>
                      <div style={candidateTitleStyle}>
                        {item.signal_title || "Untitled signal"}
                      </div>
                    </div>
                    <div style={scoreChipStyle}>
                      Score: {formatScore(item.score)}
                    </div>
                  </div>

                  <div style={{ marginTop: "12px", display: "flex", gap: "8px", flexWrap: "wrap" }}>
                    {item.status ? <span style={chipStyle}>{formatLabel(item.status)}</span> : null}
                    {manualOverrideCandidate ? <span style={manualOverrideChipStyle}>Manual Override</span> : null}
                    {confirmedFinalTakeawayHandoff ? (
                      <span
                        style={finalTakeawayHandoffChipStyle}
                        title="This candidate came from Send Final Takeaway to Review. It still follows the normal Project Review gate."
                      >
                        Final Takeaway Handoff
                      </span>
                    ) : null}
                    {knowledgeConvergenceCandidate ? <span style={knowledgeConvergenceChipStyle}>Knowledge Convergence</span> : null}
                    {verification.review_priority ? <span style={chipStyle}>Review: {verification.review_priority}</span> : null}
                    {verification.verification_status ? <span style={chipStyle}>{formatLabel(verification.verification_status)}</span> : null}
                    {verification.confidence_label ? (
                      <span style={chipStyle}>
                        Confidence: {formatLabel(verification.confidence_label)}
                        {typeof verification.confidence_score === "number" ? ` (${verification.confidence_score.toFixed(2)})` : ""}
                      </span>
                    ) : null}
                    <span style={chipStyle}>{formatModelProvenanceChip(candidateModelProvenance)}</span>
                    {item.suggested_stage ? <span style={chipStyle}>Stage: {item.suggested_stage}</span> : null}
                  </div>

                  {claimSupport ? (
                    <div style={{ marginTop: "10px", fontSize: "13px", color: "var(--app-text-muted)", display: simplifiedCandidateMode ? "none" : "block" }}>
                      Claim support: {claimSupport}
                    </div>
                  ) : null}

                  {showVerifiedInsightObject ? (
                    <VerifiedInsightObjectPanel
                      rows={verifiedInsightObjectRows}
                      subtitle="Existing verification metadata projected for Project Review. This panel does not change gates, create evidence, or unlock Action."
                      style={{ marginTop: "12px" }}
                    />
                  ) : null}

                  {activeView === "pending" ? (
                    <div style={reasoningAssessmentAdvisoryStyle(reasoningAssessmentAdvisory.tone)}>
                      <div style={reasoningAssessmentHeaderStyle}>
                        <div>
                          <span style={detailLabelStyle}>Reasoning Assessment Advisory</span>
                          <strong>{reasoningAssessmentAdvisory.label}</strong>
                        </div>
                        <span style={reasoningAssessmentChipStyle(reasoningAssessmentAdvisory.tone)}>
                          ADR-0015 reviewer-only
                        </span>
                      </div>
                      <p style={reasoningAssessmentSummaryStyle}>{reasoningAssessmentAdvisory.summary}</p>
                      <div style={reasoningAssessmentGridStyle}>
                        <div style={reasoningAssessmentItemStyle}>
                          <span style={detailLabelStyle}>Load-bearing packet</span>
                          <strong style={reasoningAssessmentValueStyle}>{reasoningAssessmentAdvisory.loadBearing}</strong>
                        </div>
                        <div style={reasoningAssessmentItemStyle}>
                          <span style={detailLabelStyle}>Boundary</span>
                          <strong style={reasoningAssessmentValueStyle}>{reasoningAssessmentAdvisory.boundary}</strong>
                        </div>
                        <div style={reasoningAssessmentBridgeItemStyle}>
                          <div style={reasoningAssessmentBridgeTitleStyle}>
                            <span style={detailLabelStyle}>Composition Bridge</span>
                            <strong>{reasoningAssessmentAdvisory.compositionBridge.label}</strong>
                          </div>
                          <div style={reasoningAssessmentBridgeGridStyle}>
                            <div style={reasoningAssessmentBridgeColumnStyle}>
                              <span style={detailLabelStyle}>Composed conclusion</span>
                              {reasoningAssessmentAdvisory.compositionBridge.isIntegrityBlocked ? (
                                <details style={reasoningAssessmentCollapsedConclusionStyle}>
                                  <summary style={reasoningAssessmentCollapsedSummaryStyle}>
                                    Hidden until packet integrity is reviewed
                                  </summary>
                                  <span style={reasoningAssessmentUnverifiedPrefixStyle}>
                                    Unverified pending packet integrity review
                                  </span>
                                  <strong style={reasoningAssessmentDegradedConclusionStyle}>
                                    {reasoningAssessmentAdvisory.compositionBridge.conclusion}
                                  </strong>
                                </details>
                              ) : (
                                <strong style={reasoningAssessmentValueStyle}>
                                  {reasoningAssessmentAdvisory.compositionBridge.conclusion}
                                </strong>
                              )}
                            </div>
                            <div style={reasoningAssessmentBridgeColumnStyle}>
                              <span style={detailLabelStyle}>Extra inference load</span>
                              <strong style={reasoningAssessmentValueStyle}>
                                {reasoningAssessmentAdvisory.compositionBridge.inferenceLoad}
                              </strong>
                            </div>
                            <div style={reasoningAssessmentBridgeColumnStyle}>
                              <span style={detailLabelStyle}>Application Mapping Load</span>
                              <strong style={reasoningAssessmentValueStyle}>
                                {reasoningAssessmentAdvisory.compositionBridge.applicationMappingLoad.summary}
                              </strong>
                            </div>
                            <div style={reasoningAssessmentBridgeColumnStyle}>
                              <span style={detailLabelStyle}>Reviewer question</span>
                              <strong style={reasoningAssessmentValueStyle}>
                                {reasoningAssessmentAdvisory.compositionBridge.reviewerQuestion}
                              </strong>
                            </div>
                          </div>
                        </div>
                        {reasoningAssessmentAdvisory.packetIntegrityChecks.length ? (
                          <div style={reasoningAssessmentChecklistItemStyle}>
                            <div style={reasoningAssessmentBridgeTitleStyle}>
                              <span style={detailLabelStyle}>Packet Integrity Check</span>
                              <strong>Referential consistency warnings</strong>
                            </div>
                            <div style={reasoningAssessmentChecklistGridStyle}>
                              {reasoningAssessmentAdvisory.packetIntegrityChecks.map((check) => (
                                <div key={check.label} style={reasoningAssessmentIntegrityCardStyle}>
                                  <span style={detailLabelStyle}>{check.label}</span>
                                  <strong style={reasoningAssessmentValueStyle}>{check.body}</strong>
                                </div>
                              ))}
                            </div>
                          </div>
                        ) : null}
                        <div style={reasoningAssessmentChecklistItemStyle}>
                          <div style={reasoningAssessmentBridgeTitleStyle}>
                            <span style={detailLabelStyle}>Framing Checklist</span>
                            <strong>Claim-framing review prompts</strong>
                          </div>
                          <div style={reasoningAssessmentChecklistGridStyle}>
                            {reasoningAssessmentAdvisory.framingChecklist.map((check) => (
                              <div key={check.label} style={reasoningAssessmentChecklistCardStyle}>
                                <span style={detailLabelStyle}>{check.label}</span>
                                <strong style={reasoningAssessmentValueStyle}>{check.body}</strong>
                              </div>
                            ))}
                          </div>
                        </div>
                        <div style={reasoningAssessmentBridgeItemStyle}>
                          <div style={reasoningAssessmentBridgeHeaderStyle}>
                            <div style={reasoningAssessmentBridgeTitleStyle}>
                              <span style={detailLabelStyle}>Warrant + Counter-check</span>
                              <strong>Reasoning bridge review</strong>
                            </div>
                            <button
                              type="button"
                              onClick={() =>
                                void handleGenerateCounterCheck(
                                  item,
                                  reasoningAssessmentAdvisory,
                                  actionEligibility,
                                  claimSupport,
                                  candidateModelProvenance,
                                  key
                                )
                              }
                              disabled={counterCheckLoading}
                              style={counterCheckLoading ? reasoningAssessmentButtonDisabledStyle : reasoningAssessmentButtonStyle}
                            >
                              <Sparkles size={14} aria-hidden="true" />
                              {counterCheckLoading
                                ? "Generating..."
                                : counterCheckDraft
                                  ? "Regenerate Counter-Check"
                                  : "Generate Counter-Check"}
                            </button>
                          </div>
                          <div style={reasoningAssessmentBridgeGridStyle}>
                            <div style={reasoningAssessmentBridgeColumnStyle}>
                              <span style={detailLabelStyle}>Warrant</span>
                              <strong style={reasoningAssessmentValueStyle}>{reasoningAssessmentAdvisory.warrant}</strong>
                            </div>
                            <div style={reasoningAssessmentBridgeColumnStyle}>
                              <span style={detailLabelStyle}>Counter-check</span>
                              <strong style={reasoningAssessmentValueStyle}>{reasoningAssessmentAdvisory.counterCheck}</strong>
                            </div>
                          </div>
                          {counterCheckDraft ? (
                            <div style={reasoningAssessmentDraftStyle}>
                              <div style={reasoningAssessmentDraftHeaderStyle}>
                                <span style={detailLabelStyle}>LLM counter-check draft</span>
                                <strong style={reasoningAssessmentDraftChipStyle(counterCheckDraft.answer)}>
                                  Answer: {formatLabel(counterCheckDraft.answer || "unclear")}
                                </strong>
                              </div>
                              <div style={reasoningAssessmentDraftGridStyle}>
                                <span style={detailLabelStyle}>Model comparison</span>
                                <strong style={reasoningAssessmentValueStyle}>
                                  {formatLabel(counterCheckDraft.source_provider || "source unknown")}
                                  {counterCheckDraft.source_model_id ? ` / ${counterCheckDraft.source_model_id}` : ""} -&gt;{" "}
                                  {formatLabel(counterCheckDraft.countercheck_provider || counterCheckDraft.produced_by_model?.provider || "counter-check unknown")}
                                </strong>
                                <span>
                                  {formatLabel(counterCheckDraft.comparison_mode || "default route")}
                                  {counterCheckDraft.provider_selection_note ? `: ${counterCheckDraft.provider_selection_note}` : ""}
                                </span>
                              </div>
                              {counterCheckDraft.summary ? <span>{counterCheckDraft.summary}</span> : null}
                              <div style={reasoningAssessmentComparisonGridStyle}>
                                <div style={reasoningAssessmentComparisonColumnStyle}>
                                  <span style={detailLabelStyle}>Original insight / takeaway</span>
                                  <strong style={reasoningAssessmentValueStyle}>
                                    {reasoningAssessmentAdvisory.originalInsight}
                                  </strong>
                                </div>
                                <div style={reasoningAssessmentComparisonColumnStyle}>
                                  <span style={detailLabelStyle}>Counter-check alternative</span>
                                  <strong style={reasoningAssessmentValueStyle}>
                                    {counterCheckDraft.opposite_or_incompatible_conclusion || "No alternative conclusion returned."}
                                  </strong>
                                </div>
                              </div>
                              {counterCheckDraft.evidence_used?.length ? (
                                <div style={reasoningAssessmentDraftGridStyle}>
                                  <span style={detailLabelStyle}>Evidence used</span>
                                  <span>{counterCheckDraft.evidence_used.join("; ")}</span>
                                </div>
                              ) : null}
                              {counterCheckDraft.missing_evidence?.length ? (
                                <div style={reasoningAssessmentDraftGridStyle}>
                                  <span style={detailLabelStyle}>Missing evidence</span>
                                  <span>{counterCheckDraft.missing_evidence.join("; ")}</span>
                                </div>
                              ) : null}
                              {counterCheckDraft.reviewer_next_step ? (
                                <div style={reasoningAssessmentDraftGridStyle}>
                                  <span style={detailLabelStyle}>Reviewer next step</span>
                                  <strong style={reasoningAssessmentValueStyle}>{counterCheckDraft.reviewer_next_step}</strong>
                                </div>
                              ) : null}
                              <span style={reasoningAssessmentValueStyle}>
                                {counterCheckDraft.boundary || reasoningAssessmentAdvisory.boundary}
                              </span>
                            </div>
                          ) : null}
                          {counterCheckError ? <div style={reasoningAssessmentErrorStyle}>{counterCheckError}</div> : null}
                        </div>
                      </div>
                    </div>
                  ) : null}

                  {simplifiedCandidateMode ? (
                    <div style={simplifiedDecisionCardStyle(candidateDecisionShortcut.tone)}>
                      <div style={simplifiedDecisionHeaderStyle}>
                        <span style={detailLabelStyle}>Recommendation</span>
                        <strong>{candidateDecisionShortcut.label}</strong>
                      </div>
                      <div style={simplifiedDecisionBodyStyle}>
                        <span>{candidateDecisionShortcut.reason}</span>
                        <span>{candidateDecisionShortcut.primary}</span>
                        <span>{candidateDecisionShortcut.secondary}</span>
                        <strong>{candidateNextStep.title}</strong>
                        <span>{candidateNextStep.body}</span>
                      </div>
                      <div style={simplifiedDecisionSnapshotGridStyle}>
                        {candidateSimplifiedSnapshot.map((fact) => (
                          <div key={fact.label} style={simplifiedDecisionSnapshotCardStyle}>
                            <span style={detailLabelStyle}>{fact.label}</span>
                            <strong>{fact.value}</strong>
                            <span>{fact.detail}</span>
                          </div>
                        ))}
                      </div>
                      {isManualSourceCandidate(item) ? (
                        <div style={manualSourceRouteStyle}>
                          {candidateManualSessionId ? (
                            <Link
                              href={`/manual/detail?id=${encodeURIComponent(candidateManualSessionId)}`}
                              style={manualSourceRouteLinkStyle}
                            >
                              Open Manual Session
                            </Link>
                          ) : null}
                          {candidateUploadReason ? <span>Reason: {candidateUploadReason}</span> : null}
                          {candidateIntendedUse ? <span>Use: {candidateIntendedUse}</span> : null}
                          <span>Layer: {formatLabel(candidateCognitiveLayer || "unclassified")}</span>
                        </div>
                      ) : null}
                      <details style={simplifiedDiagnosticsDetailsStyle}>
                        <summary style={summaryDetailsSummaryStyle}>Diagnostics / original context</summary>
                        <div style={simplifiedDiagnosticsGridStyle}>
                          {candidateDecisionOptions.map((option) => (
                            <div key={option.label} style={detailItemStyle}>
                              <span style={detailLabelStyle}>{option.label}</span>
                              <strong>{option.value}</strong>
                            </div>
                          ))}
                          <div style={detailItemStyle}>
                            <span style={detailLabelStyle}>Source</span>
                            <strong>{candidateSourceLabel}</strong>
                          </div>
                          <div style={detailItemStyle}>
                            <span style={detailLabelStyle}>IDs</span>
                            <strong>{item.project_id || "Unknown project"}</strong>
                            <span>{item.signal_id || "Unknown signal"}</span>
                          </div>
                          <div style={detailItemStyle}>
                            <span style={detailLabelStyle}>Claim Support</span>
                            <strong>{claimSupport || "Not recorded"}</strong>
                          </div>
                          <div style={detailItemStyle}>
                            <span style={detailLabelStyle}>Project Takeaway</span>
                            <strong>{projectTakeawayGate?.allowed === false ? "Blocked" : "Allowed"}</strong>
                            <span>{projectTakeawayGate?.reason || "No Project Takeaway gate reason recorded."}</span>
                          </div>
                          <div style={detailItemStyle}>
                            <span style={detailLabelStyle}>Action</span>
                            <strong>{actionGate?.allowed === false ? "Blocked" : "Allowed"}</strong>
                            <span>{actionGate?.reason || "No Action gate reason recorded."}</span>
                          </div>
                        </div>
                        <div style={simplifiedDiagnosticsHintStyle}>
                          Switch to Original for the full Knowledge Context, Verification Gate, evidence notes, and decision option grids.
                        </div>
                      </details>
                    </div>
                  ) : (
                  <div style={candidateDecisionGuideStyle}>
                    <div style={candidateDecisionGuideHeaderStyle}>
                      <span style={detailLabelStyle}>Source</span>
                      <strong>{candidateSourceLabel}</strong>
                    </div>
                    <div style={candidateDecisionShortcutStyle(candidateDecisionShortcut.tone)}>
                      <div>
                        <span style={detailLabelStyle}>Decision Shortcut</span>
                        <strong>{candidateDecisionShortcut.label}</strong>
                      </div>
                      <div style={candidateDecisionShortcutBodyStyle}>
                        <span>{candidateDecisionShortcut.reason}</span>
                        <span>{candidateDecisionShortcut.primary}</span>
                        <span>{candidateDecisionShortcut.secondary}</span>
                      </div>
                    </div>
                    <span style={detailLabelStyle}>Next Step</span>
                    <div style={candidateDecisionGuideBodyStyle}>
                      <strong style={candidateNextStepTitleStyle}>{candidateNextStep.title}</strong>
                      <span style={candidateNextStepBodyStyle}>{candidateNextStep.body}</span>
                    </div>
                    <div style={candidateDecisionOptionGridStyle}>
                      {candidateDecisionOptions.map((option) => (
                        <div key={option.label} style={candidateDecisionOptionStyle}>
                          <span style={detailLabelStyle}>{option.label}</span>
                          <strong>{option.value}</strong>
                        </div>
                      ))}
                    </div>
                    {isManualSourceCandidate(item) ? (
                      <div style={manualSourceRouteStyle}>
                        {candidateManualSessionId ? (
                          <Link
                            href={`/manual/detail?id=${encodeURIComponent(candidateManualSessionId)}`}
                            style={manualSourceRouteLinkStyle}
                          >
                            Open Manual Session
                          </Link>
                        ) : null}
                        {candidateUploadReason ? <span>Reason: {candidateUploadReason}</span> : null}
                        {candidateIntendedUse ? <span>Use: {candidateIntendedUse}</span> : null}
                        <span>Layer: {formatLabel(candidateCognitiveLayer || "unclassified")}</span>
                      </div>
                    ) : null}
                  </div>
                  )}

                  {manualOverrideCandidate ? (
                    <div style={manualOverrideNoticeStyle}>
                      <strong>Manual override:</strong>{" "}
                      {verification.manual_override_note || "Reviewer manually selected this candidate despite the system gate."}
                    </div>
                  ) : null}

                  {showDeepProjectMatchReview ? (
                    <div style={deepProjectMatchReviewStyle}>
                      <div style={deepProjectMatchReviewHeaderStyle}>
                        <div>
                          <span style={detailLabelStyle}>Deep Project Match</span>
                          <strong>{deepProjectMatchReview?.posture || "Review required"}</strong>
                        </div>
                        <span style={deepProjectMatchReviewChipStyle}>
                          {formatLabel(deepProjectMatchReview?.evidence_boundary || "internal_judgment")}
                        </span>
                      </div>
                      {deepProjectMatchReview?.review_note ? (
                        <p style={deepProjectMatchReviewNoteStyle}>{deepProjectMatchReview.review_note}</p>
                      ) : null}
                      {deepProjectMatchReview?.generated_analysis?.narrative_summary ? (
                        <div style={deepProjectMatchGeneratedAnalysisStyle}>
                          <span style={detailLabelStyle}>Generated Analysis</span>
                          <strong>
                            {formatLabel(deepProjectMatchReview.generated_analysis.source_depth_tier || "metadata")} /{" "}
                            {formatLabel(deepProjectMatchReview.generated_analysis.hypothesis_status || deepProjectMatchReview.generated_analysis.differentiated_insight_status || "not_enough_metadata")}
                          </strong>
                          <p style={deepProjectMatchReviewNoteStyle}>
                            {deepProjectMatchReview.generated_analysis.narrative_summary}
                          </p>
                          {deepProjectMatchReview.generated_analysis.suspected_differentiated_insight ? (
                            <span>{deepProjectMatchReview.generated_analysis.suspected_differentiated_insight}</span>
                          ) : null}
                          {deepProjectMatchReview.generated_analysis.concrete_relevance ? (
                            <span>{deepProjectMatchReview.generated_analysis.concrete_relevance}</span>
                          ) : null}
                          {deepProjectMatchReview.generated_analysis.needs_source_read ? (
                            <span>
                              Needs source read:{" "}
                              {deepProjectMatchReview.generated_analysis.source_read_targets?.length
                                ? deepProjectMatchReview.generated_analysis.source_read_targets
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
                                : "Open original source before treating as source-grounded."}
                            </span>
                          ) : null}
                          <span>
                            Review note effect:{" "}
                            {formatLabel(deepProjectMatchReview.generated_analysis.review_note_effect || deepProjectMatchReview.review_note_effect || "review_context_only")}
                          </span>
                          <strong>
                            Verification effect: {deepProjectMatchReview.generated_analysis.verification_effect || "none"}
                          </strong>
                          {Array.isArray(deepProjectMatchReview.generated_analysis_layers) &&
                          deepProjectMatchReview.generated_analysis_layers.length > 1 ? (
                            <span>Analysis layers preserved: {deepProjectMatchReview.generated_analysis_layers.length}</span>
                          ) : null}
                        </div>
                      ) : null}
                      <div style={deepProjectMatchReviewGridStyle}>
                        <div style={detailItemStyle}>
                          <span style={detailLabelStyle}>Project</span>
                          <strong>
                            {deepProjectMatchReview?.matched_projects?.length
                              ? deepProjectMatchReview.matched_projects.join(", ")
                              : "Unspecified"}
                          </strong>
                        </div>
                        <div style={detailItemStyle}>
                          <span style={detailLabelStyle}>AI Radar Module</span>
                          <strong>
                            {deepProjectMatchReview?.relevant_modules?.length
                              ? deepProjectMatchReview.relevant_modules.join(", ")
                              : "Needs module match"}
                          </strong>
                        </div>
                        <div style={detailItemStyle}>
                          <span style={detailLabelStyle}>Match Type</span>
                          <strong>{formatLabel(deepProjectMatchReview?.match_type || "weak")}</strong>
                        </div>
                      </div>
                      {Array.isArray(deepProjectMatchReview?.checklist) && deepProjectMatchReview.checklist.length > 0 ? (
                        <details style={deepProjectMatchReviewDetailsStyle}>
                          <summary style={summaryDetailsSummaryStyle}>Structured checklist</summary>
                          <div style={deepProjectMatchReviewChecklistStyle}>
                            {deepProjectMatchReview.checklist.map((item, itemIndex) => (
                              <div key={item.key || `${item.label || "item"}-${itemIndex}`} style={detailItemStyle}>
                                <span style={detailLabelStyle}>{item.label || "Checklist item"}</span>
                                <strong>{item.value || "Not recorded"}</strong>
                                {item.status ? <span>{formatLabel(item.status)}</span> : null}
                              </div>
                            ))}
                          </div>
                        </details>
                      ) : null}
                    </div>
                  ) : null}

                  {manualOverrideCandidate && activeView === "pending" && !simplifiedCandidateMode ? (
                    <div style={manualOverrideReviewGuideStyle}>
                      <div style={detailItemStyle}>
                        <span style={detailLabelStyle}>Review Posture</span>
                        <strong>Confirm only after checking the original signal and claim evidence.</strong>
                      </div>
                      <div style={detailItemStyle}>
                        <span style={detailLabelStyle}>Safer Paths</span>
                        <strong>Use Watch for uncertain value, Action only with a clear owner/date, Reject if the override was too optimistic.</strong>
                      </div>
                    </div>
                  ) : null}

                  {activeView === "pending" && actionEligibility && !simplifiedCandidateMode ? (
                    <div style={actionEligibilityPanelStyle}>
                      <div style={actionEligibilityHeaderStyle}>
                        <span style={detailLabelStyle}>Verification Gate</span>
                        <strong>
                          {actionGate?.allowed === false
                            ? manualOverrideCandidate
                              ? "Action requires override judgment"
                              : "Action blocked"
                            : "Action available after review"}
                        </strong>
                      </div>
                      <VerificationGateNote
                        verification={{
                          verification_status: actionEligibility.signals?.verification_status || verification.verification_status || "",
                          verification_required: Boolean(verification.verification_required),
                          knowledge_convergence: Boolean(verification.knowledge_convergence),
                          manual_project_takeaway_override: Boolean(verification.manual_project_takeaway_override),
                          allowed_downstream_actions: actionEligibility.signals?.allowed_downstream_actions || verification.allowed_downstream_actions || [],
                          blocked_downstream_actions: actionEligibility.signals?.blocked_downstream_actions || verification.blocked_downstream_actions || [],
                          claim_support_summary: verification.claim_support_summary || {
                            unsupported: actionEligibility.signals?.unsupported_or_contradicted_claim_count || 0,
                            inferred: actionEligibility.signals?.inferred_claim_count || 0,
                          },
                        }}
                        style={{ marginTop: "10px" }}
                      />
                      <div style={actionEligibilityGridStyle}>
                        <div style={detailItemStyle}>
                          <span style={detailLabelStyle}>Project Takeaway</span>
                          <strong>{actionEligibility.project_takeaway_candidate?.allowed === false ? "Blocked" : "Allowed"}</strong>
                          <span>{actionEligibility.project_takeaway_candidate?.reason || "No Project Takeaway gate reason recorded."}</span>
                        </div>
                        <div style={detailItemStyle}>
                          <span style={detailLabelStyle}>Watch</span>
                          <strong>{actionEligibility.watch_only?.allowed === false ? "Not suggested" : "Suggested"}</strong>
                          <span>{actionEligibility.watch_only?.reason || "No Watch gate reason recorded."}</span>
                        </div>
                        <div style={detailItemStyle}>
                          <span style={detailLabelStyle}>Action</span>
                          <strong>{actionGate?.allowed === false ? "Blocked" : "Allowed"}</strong>
                          <span>{actionGate?.reason || "No Action gate reason recorded."}</span>
                        </div>
                      </div>
                      <div style={actionEligibilitySignalStyle}>
                        Status: {formatLabel(actionEligibility.signals?.verification_status) || "n/a"} / Unsupported or contradicted:{" "}
                        {actionEligibility.signals?.unsupported_or_contradicted_claim_count ?? 0} / Inferred:{" "}
                        {actionEligibility.signals?.inferred_claim_count ?? 0} / Blocked actions:{" "}
                        {formatActionList(actionEligibility.signals?.blocked_downstream_actions)}
                      </div>
                    </div>
                  ) : null}

                  {activeView === "pending" && (projectTakeawayBlockedForCandidate || actionBlockedForCandidate) ? (
                    <details open={projectTakeawayBlockedForCandidate || Boolean(overrideError)} style={metadataDetailsStyle}>
                      <summary style={summaryDetailsSummaryStyle}>Override Actions</summary>
                      <div style={metadataPanelStyle}>
                        <div style={metadataColumnStyle}>
                          <div style={metadataHeadingStyle}>Shared override note</div>
                          <textarea
                            value={reasonByKey[key] || ""}
                            onChange={(event) =>
                              setReasonByKey((current) => ({ ...current, [key]: event.target.value }))
                            }
                            placeholder="Used by Override Confirm and Override Action. Explain why a human reviewer accepts the verification risk."
                            rows={3}
                            style={metadataTextareaStyle}
                          />
                        </div>
                        <div style={metadataColumnStyle}>
                          <div style={metadataHeadingStyle}>Shared expected outcome</div>
                          <textarea
                            value={currentMetadata.action_expected_outcome || ""}
                            onChange={(event) =>
                              setMetadataByKey((current) => ({
                                ...current,
                                [key]: { ...(current[key] || {}), action_expected_outcome: event.target.value },
                              }))
                            }
                            placeholder="Used by Override Confirm and Override Action. State what value this override is expected to produce."
                            rows={3}
                            style={metadataTextareaStyle}
                          />
                          {actionBlockedForCandidate ? (
                            <>
                              <span style={metadataFieldLabelStyle}>Action due date (Override Action only)</span>
                              <input
                                type="date"
                                value={currentMetadata.action_due_date || ""}
                                onChange={(event) =>
                                  setMetadataByKey((current) => ({
                                    ...current,
                                    [key]: { ...(current[key] || {}), action_due_date: event.target.value },
                                  }))
                                }
                                style={metadataInputStyle}
                              />
                              <span style={metadataFieldLabelStyle}>Action review date (Override Action only)</span>
                              <input
                                type="date"
                                value={currentMetadata.action_review_date || ""}
                                onChange={(event) =>
                                  setMetadataByKey((current) => ({
                                    ...current,
                                    [key]: { ...(current[key] || {}), action_review_date: event.target.value },
                                  }))
                                }
                                style={metadataInputStyle}
                              />
                            </>
                          ) : null}
                        </div>
                        <div style={overrideConfirmWarningStyle}>
                          Override actions bypass the normal gate and write auditable review records. Use them only when a human reviewer accepts the verification risk.
                        </div>
                        <div style={overrideInlineHelpStyle}>
                          Override Confirm accepts this as a Project Takeaway. Override Action moves it into Action and also requires the two action dates.
                        </div>
                        {!overrideConfirmReady ? (
                          <div style={overrideInlineHelpStyle}>
                            Fill the shared override note and shared expected outcome before using Override Confirm.
                          </div>
                        ) : null}
                        {actionBlockedForCandidate && !overrideActionReady ? (
                          <div style={overrideInlineHelpStyle}>
                            Fill both shared fields plus the Action due date and Action review date before using Override Action.
                          </div>
                        ) : null}
                        {overrideError ? (
                          <div style={overrideInlineErrorStyle}>{overrideError}</div>
                        ) : null}
                        <div style={{ gridColumn: "1 / -1", display: "flex", gap: "10px", flexWrap: "wrap" }}>
                          {projectTakeawayBlockedForCandidate ? (
                            <button
                              type="button"
                              onClick={() => void handleOverrideConfirm(item)}
                              disabled={!overrideConfirmReady || confirmingKey === `${key}:override` || closingKey.startsWith(`${key}:`)}
                              title={!overrideConfirmReady ? "Fill the shared override note and shared expected outcome first." : undefined}
                              style={overrideConfirmReady ? dangerButtonStyle : disabledButtonStyle}
                            >
                              {confirmingKey === `${key}:override` ? "Override Confirming..." : "Override Confirm"}
                            </button>
                          ) : null}
                          {actionBlockedForCandidate ? (
                            <button
                              type="button"
                              onClick={() => void handleOverrideAction(item)}
                              disabled={!overrideActionReady || confirmingKey === key || closingKey.startsWith(`${key}:`)}
                              title={!overrideActionReady ? "Fill the shared fields and both action dates first." : undefined}
                              style={overrideActionReady ? dangerButtonStyle : disabledButtonStyle}
                            >
                              {closingKey === `${key}:override-action` ? "Override Actioning..." : "Override Action"}
                            </button>
                          ) : null}
                        </div>
                      </div>
                    </details>
                  ) : null}

                  {knowledgeConvergenceCandidate && !simplifiedCandidateMode ? (
                    <div style={knowledgeConvergencePanelStyle}>
                      <div style={knowledgeConvergenceHeaderStyle}>
                        <div>
                          <span style={detailLabelStyle}>Knowledge Context</span>
                          <strong>
                            {verification.review_readiness?.label || formatLabel(verification.review_readiness?.status) || "Human Review Required"}
                          </strong>
                        </div>
                        <span style={knowledgeConvergenceSourceStyle}>
                          {verification.convergence_brief_id || "knowledge convergence"}
                        </span>
                      </div>
                      <div style={knowledgeReviewPostureStyle}>
                        <div style={detailItemStyle}>
                          <span style={detailLabelStyle}>Review Posture</span>
                          <strong>Convergence review, not action evidence</strong>
                        </div>
                        <div style={detailItemStyle}>
                          <span style={detailLabelStyle}>Review Path</span>
                          <strong>{knowledgeReviewPath.label}</strong>
                          <span>{knowledgeReviewPath.body}</span>
                        </div>
                        <div style={detailItemStyle}>
                          <span style={detailLabelStyle}>Best Use</span>
                          <strong>Confirm project fit or move to Watch when evidence is still thin.</strong>
                        </div>
                        <div style={detailItemStyle}>
                          <span style={detailLabelStyle}>Action Boundary</span>
                          <strong>Low-risk Action stays blocked unless override context is explicit.</strong>
                        </div>
                      </div>
                      {verification.review_readiness?.reason ? (
                        <div style={knowledgeConvergenceBodyStyle}>{verification.review_readiness.reason}</div>
                      ) : null}
                      {knowledgeRationaleRows.length ? (
                        <div style={knowledgeRationaleGridStyle}>
                          {knowledgeRationaleRows.map((row) => (
                            <div key={row.label} style={knowledgeRationaleItemStyle}>
                              <span style={detailLabelStyle}>{row.label}</span>
                              <strong>{row.value}</strong>
                            </div>
                          ))}
                        </div>
                      ) : null}
                      {(() => {
                        const quality = buildKnowledgeQualityLabel(verification);
                        return (
                          <div style={knowledgeQualityPanelStyle}>
                            <div>
                              <span style={detailLabelStyle}>Fit Quality</span>
                              <strong>{quality.label}</strong>
                            </div>
                            {quality.score !== null ? <span style={knowledgeQualityScoreStyle}>{quality.score}/100</span> : null}
                            {quality.reason ? <div style={knowledgeConvergenceBodyStyle}>{quality.reason}</div> : null}
                            {quality.recommendation ? <div style={knowledgeQualityRecommendationStyle}>{quality.recommendation}</div> : null}
                            {knowledgeQualityFactorRows.length ? (
                              <div style={knowledgeFactorRowStyle}>
                                {knowledgeQualityFactorRows.map((factor) => (
                                  <span key={factor.label} style={knowledgeFactorChipStyle}>
                                    {factor.label}: {factor.value}
                                  </span>
                                ))}
                              </div>
                            ) : null}
                          </div>
                        );
                      })()}
                      <div style={knowledgeMetricGridStyle}>
                        <div style={knowledgeMetricStyle}>
                          <span style={detailLabelStyle}>Sources</span>
                          <strong style={knowledgeMetricValueStyle}>
                            {verification.evidence_profile?.source_count ?? verification.review_readiness?.source_count ?? 0}
                          </strong>
                        </div>
                        <div style={knowledgeMetricStyle}>
                          <span style={detailLabelStyle}>Shared Topics</span>
                          <strong style={knowledgeMetricValueStyle}>
                            {verification.evidence_profile?.shared_topic_count ?? verification.review_readiness?.shared_topic_count ?? 0}
                          </strong>
                        </div>
                        <div style={knowledgeMetricStyle}>
                          <span style={detailLabelStyle}>Project Matches</span>
                          <strong style={knowledgeMetricValueStyle}>
                            {verification.project_relevance?.match_count ?? verification.review_readiness?.matched_project_count ?? 0}
                          </strong>
                        </div>
                      </div>
                      {verification.project_relevance?.matched_projects?.length ? (
                        <div style={knowledgeProjectRowStyle}>
                          {verification.project_relevance.matched_projects.slice(0, 3).map((project) => (
                            <span key={project.project_id || project.project_name} style={knowledgeProjectPillStyle}>
                              {project.project_name || project.project_id || "Project"}
                              {project.matched_topics?.length ? ` / ${project.matched_topics.slice(0, 3).join(", ")}` : ""}
                            </span>
                          ))}
                        </div>
                      ) : null}
                      {verification.evidence_profile?.support_note ? (
                        <div style={knowledgeConvergenceBodyStyle}>{verification.evidence_profile.support_note}</div>
                      ) : null}
                      {verification.convergence_brief_id ? (
                        <div style={knowledgeRouteRowStyle}>
                          <Link
                            href={`/knowledge/detail?id=${encodeURIComponent(verification.convergence_brief_id)}`}
                            style={secondaryLinkStyle}
                          >
                            Open Knowledge Detail
                          </Link>
                        </div>
                      ) : null}
                    </div>
                  ) : null}

                  {item.takeaway && !simplifiedCandidateMode ? (
                    <div style={bodyTextStyle}>{truncateText(item.takeaway)}</div>
                  ) : item.signal_summary && !simplifiedCandidateMode ? (
                    <div style={bodyTextStyle}>{truncateText(item.signal_summary)}</div>
                  ) : null}

                  {item.fit_reason && !simplifiedCandidateMode ? (
                    <div style={mutedBlockStyle}>
                      <strong>Fit reason:</strong> {truncateText(item.fit_reason, 260)}
                    </div>
                  ) : null}

                  {activeView !== "pending" ? (
                    <div style={mutedBlockStyle}>
                      <strong>Review outcome:</strong>{" "}
                      <span style={getOutcomeChipStyle(getItemReviewDisplayOutcome(item))}>
                        {formatLabel(getItemReviewDisplayOutcome(item))}
                      </span>
                      {reviewReason ? <span> · {reviewReason}</span> : null}
                      {actionCompletionNote ? <span> · Completed: {actionCompletionNote}</span> : null}
                      {reviewedAt ? <span> · {reviewedAt}</span> : null}
                    </div>
                  ) : null}

                  {activeView === "watch" || (activeView === "closed" && normalizedStatus === "watch") ? (
                    <div style={{ marginTop: "12px" }}>
                      <div style={detailGridStyle}>
                        <div style={detailItemStyle}>
                          <span style={detailLabelStyle}>Watch Status</span>
                          <strong>{formatLabel(item.watch_status) || "Watching"}</strong>
                        </div>
                        <div style={detailItemStyle}>
                          <span style={detailLabelStyle}>Review Date</span>
                          <strong>{item.watch_review_date || "Not set"}</strong>
                        </div>
                        <div style={detailItemStyle}>
                          <span style={detailLabelStyle}>Success Criteria</span>
                          <strong>{item.watch_success_criteria || "Not set"}</strong>
                        </div>
                      </div>
                      {item.watch_last_reviewed_at || item.watch_followup_result || item.watch_review_note ? (
                        <div style={mutedBlockStyle}>
                          <strong>Latest watch observation:</strong>{" "}
                          {formatLabel(item.watch_followup_result) || "Reviewed"}
                          {item.watch_last_reviewed_at ? <span> / {item.watch_last_reviewed_at}</span> : null}
                          {item.watch_review_note ? <span> / {item.watch_review_note}</span> : null}
                        </div>
                      ) : null}
                      <div style={mutedBlockStyle}>
                        <strong>Watch follow-ups:</strong> {item.watch_followup_count || 0}
                        {item.watch_next_review_date ? <span> / Next review {item.watch_next_review_date}</span> : null}
                        <span> / This records observation; it does not close the Watch item.</span>
                      </div>
                      {followupMessage ? <div style={successNoticeStyle}>{followupMessage}</div> : null}
                      {activeView === "watch" ? (
                        <details style={metadataDetailsStyle}>
                          <summary style={summaryDetailsSummaryStyle}>Add Watch Follow-up</summary>
                          <div style={metadataPanelStyle}>
                            <div style={metadataColumnStyle}>
                              <div style={metadataHeadingStyle}>Follow-up result</div>
                              <input
                                type="text"
                                value={currentMetadata.followup_result || ""}
                                onChange={(event) =>
                                  setMetadataByKey((current) => ({
                                    ...current,
                                    [key]: { ...(current[key] || {}), followup_result: event.target.value },
                                  }))
                                }
                                placeholder="e.g. evidence_improved, still_uncertain, false_positive"
                                style={metadataInputStyle}
                              />
                              <textarea
                                value={reasonByKey[key] || ""}
                                onChange={(event) =>
                                  setReasonByKey((current) => ({ ...current, [key]: event.target.value }))
                                }
                                placeholder="What changed since this entered Watch?"
                                rows={2}
                                style={metadataTextareaStyle}
                              />
                            </div>
                            <div style={metadataColumnStyle}>
                              <div style={metadataHeadingStyle}>Evidence update</div>
                              <textarea
                                value={currentMetadata.evidence_update || ""}
                                onChange={(event) =>
                                  setMetadataByKey((current) => ({
                                    ...current,
                                    [key]: { ...(current[key] || {}), evidence_update: event.target.value },
                                  }))
                                }
                                placeholder="New evidence, missing evidence, or reason to keep watching"
                                rows={2}
                                style={metadataTextareaStyle}
                              />
                              <input
                                type="date"
                                value={currentMetadata.next_review_date || ""}
                                onChange={(event) =>
                                  setMetadataByKey((current) => ({
                                    ...current,
                                    [key]: { ...(current[key] || {}), next_review_date: event.target.value },
                                  }))
                                }
                                style={metadataInputStyle}
                              />
                            </div>
                          </div>
                        </details>
                      ) : null}
                    </div>
                  ) : null}

                  {activeView === "action" || ["action", "action_completed"].includes(normalizedStatus) && activeView === "closed" ? (
                    <div style={detailGridStyle}>
                      <div style={detailItemStyle}>
                        <span style={detailLabelStyle}>Expected Outcome</span>
                        <strong>{item.action_expected_outcome || "Not set"}</strong>
                      </div>
                      <div style={detailItemStyle}>
                        <span style={detailLabelStyle}>Due Date</span>
                        <strong>{item.action_due_date || "Not set"}</strong>
                      </div>
                      <div style={detailItemStyle}>
                        <span style={detailLabelStyle}>Review Date</span>
                        <strong>{item.action_review_date || "Not set"}</strong>
                      </div>
                    </div>
                  ) : null}

                  {activeView === "closed" && normalizedStatus === "action_completed" && (item.action_completion_result || item.action_completion_evidence_update || item.action_next_review_date) ? (
                    <div style={mutedBlockStyle}>
                      <strong>Action follow-up:</strong>{" "}
                      {formatLabel(item.action_completion_result) || "Completed"}
                      {item.action_completion_evidence_update ? <span> / {item.action_completion_evidence_update}</span> : null}
                      {item.action_next_review_date ? <span> / Next review {item.action_next_review_date}</span> : null}
                    </div>
                  ) : null}

                  {activeView === "action" ? (
                    <div style={{ marginTop: "14px" }}>
                      <label style={reasonLabelStyle} htmlFor={`completion-note-${index}`}>
                        Completion note
                      </label>
                      <textarea
                        id={`completion-note-${index}`}
                        value={completionNoteByKey[key] || ""}
                        onChange={(event) =>
                          setCompletionNoteByKey((current) => ({ ...current, [key]: event.target.value }))
                        }
                        placeholder="Optional note about what was completed"
                        rows={2}
                        style={reasonInputStyle}
                      />
                      <details style={metadataDetailsStyle}>
                        <summary style={summaryDetailsSummaryStyle}>Action Follow-up</summary>
                        <div style={metadataPanelStyle}>
                          <div style={metadataColumnStyle}>
                            <input
                              type="text"
                              value={currentMetadata.followup_result || ""}
                              onChange={(event) =>
                                setMetadataByKey((current) => ({
                                  ...current,
                                  [key]: { ...(current[key] || {}), followup_result: event.target.value },
                                }))
                              }
                              placeholder="e.g. expected_outcome_met, partial, missed"
                              style={metadataInputStyle}
                            />
                            <input
                              type="date"
                              value={currentMetadata.next_review_date || ""}
                              onChange={(event) =>
                                setMetadataByKey((current) => ({
                                  ...current,
                                  [key]: { ...(current[key] || {}), next_review_date: event.target.value },
                                }))
                              }
                              style={metadataInputStyle}
                            />
                          </div>
                          <div style={metadataColumnStyle}>
                            <textarea
                              value={currentMetadata.evidence_update || ""}
                              onChange={(event) =>
                                setMetadataByKey((current) => ({
                                  ...current,
                                  [key]: { ...(current[key] || {}), evidence_update: event.target.value },
                                }))
                              }
                              placeholder="What evidence shows whether the expected outcome happened?"
                              rows={3}
                              style={metadataTextareaStyle}
                            />
                          </div>
                        </div>
                      </details>
                    </div>
                  ) : null}

                  {activeView === "pending" ? (
                    <>
                      <div style={{ marginTop: "14px" }}>
                        <label style={reasonLabelStyle} htmlFor={`review-reason-${index}`}>
                          Review note
                        </label>
                        <textarea
                          id={`review-reason-${index}`}
                          value={reasonByKey[key] || ""}
                          onChange={(event) =>
                            setReasonByKey((current) => ({ ...current, [key]: event.target.value }))
                          }
                          placeholder="Optional reason for reject, dismiss, watch, or action"
                          rows={2}
                          style={reasonInputStyle}
                        />
                      </div>
                      <details style={metadataDetailsStyle}>
                        <summary style={summaryDetailsSummaryStyle}>Watch / Action Metadata</summary>
                        <div style={metadataPanelStyle}>
                          <div style={metadataColumnStyle}>
                            <div style={metadataHeadingStyle}>Watch</div>
                            <input
                              type="date"
                              value={currentMetadata.watch_review_date || ""}
                              onChange={(event) =>
                                setMetadataByKey((current) => ({
                                  ...current,
                                  [key]: { ...(current[key] || {}), watch_review_date: event.target.value },
                                }))
                              }
                              style={metadataInputStyle}
                            />
                            <input
                              type="text"
                              value={currentMetadata.watch_status || ""}
                              onChange={(event) =>
                                setMetadataByKey((current) => ({
                                  ...current,
                                  [key]: { ...(current[key] || {}), watch_status: event.target.value },
                                }))
                              }
                              placeholder="Status, e.g. watching"
                              style={metadataInputStyle}
                            />
                            <textarea
                              value={currentMetadata.watch_success_criteria || ""}
                              onChange={(event) =>
                                setMetadataByKey((current) => ({
                                  ...current,
                                  [key]: { ...(current[key] || {}), watch_success_criteria: event.target.value },
                                }))
                              }
                              placeholder="Success criteria to look for"
                              rows={2}
                              style={metadataTextareaStyle}
                            />
                          </div>
                          <div style={metadataColumnStyle}>
                            <div style={metadataHeadingStyle}>Action</div>
                            <input
                              type="date"
                              value={currentMetadata.action_due_date || ""}
                              onChange={(event) =>
                                setMetadataByKey((current) => ({
                                  ...current,
                                  [key]: { ...(current[key] || {}), action_due_date: event.target.value },
                                }))
                              }
                              style={metadataInputStyle}
                            />
                            <input
                              type="date"
                              value={currentMetadata.action_review_date || ""}
                              onChange={(event) =>
                                setMetadataByKey((current) => ({
                                  ...current,
                                  [key]: { ...(current[key] || {}), action_review_date: event.target.value },
                                }))
                              }
                              style={metadataInputStyle}
                            />
                            <textarea
                              value={currentMetadata.action_expected_outcome || ""}
                              onChange={(event) =>
                                setMetadataByKey((current) => ({
                                  ...current,
                                  [key]: { ...(current[key] || {}), action_expected_outcome: event.target.value },
                                }))
                              }
                              placeholder="Expected outcome after action"
                              rows={2}
                              style={metadataTextareaStyle}
                            />
                          </div>
                        </div>
                      </details>
                    </>
                  ) : null}

                  <div style={{ marginTop: "14px", display: "flex", gap: "10px", flexWrap: "wrap" }}>
                    {item.project_id && item.signal_id ? (
                      <Link
                        href={`/workspace/projects/improvement-detail?project_id=${encodeURIComponent(item.project_id)}&signal_id=${encodeURIComponent(item.signal_id)}`}
                        style={secondaryLinkStyle}
                      >
                        Open Fit Detail
                      </Link>
                    ) : null}
                    {isSignalDetailLinkable(item.signal_id, item.candidate_source) ? (
                      <Link
                        href={`/signals/detail?id=${encodeURIComponent(item.signal_id || "")}&review_signal_id=${encodeURIComponent(item.signal_id || "")}`}
                        style={secondaryLinkStyle}
                      >
                        {focusedSignalId ? "Back to Focused Signal" : "Open Signal Detail"}
                      </Link>
                    ) : null}
                    {!isSignalDetailLinkable(item.signal_id, item.candidate_source) && isKnowledgeConvergenceCandidate(item) ? (
                      <span style={candidateSourceHintStyle}>
                        Knowledge candidate: use Fit Detail instead of Signal Detail.
                      </span>
                    ) : null}
                    {activeView === "pending" && item.project_id && item.signal_id && !projectTakeawayBlockedForCandidate ? (
                      <button
                        type="button"
                        onClick={() => void handleConfirm(item)}
                        disabled={confirmingKey === key || closingKey.startsWith(`${key}:`)}
                        style={primaryButtonStyle}
                      >
                        {confirmingKey === key
                          ? "Confirming..."
                          : manualOverrideCandidate
                            ? "Confirm Override"
                            : "Confirm Project Takeaway"}
                      </button>
                    ) : null}
                    {activeView === "pending" && item.project_id && item.signal_id ? (
                      <button
                        type="button"
                        onClick={() => void handleCloseCandidate(item, "action")}
                        disabled={actionBlockedForCandidate || confirmingKey === key || closingKey.startsWith(`${key}:`)}
                        style={actionBlockedForCandidate ? disabledButtonStyle : actionButtonStyle}
                        title={actionBlockedForCandidate ? actionGate?.reason || "Verification blocks action creation." : undefined}
                      >
                        {closingKey === actionActionKey
                          ? "Adding Action..."
                          : actionBlockedForCandidate
                            ? "Action Blocked"
                            : manualOverrideCandidate ? "Action Override" : "Action"}
                      </button>
                    ) : null}
                    {activeView === "pending" && item.project_id && item.signal_id ? (
                      <button
                        type="button"
                        onClick={() => void handleCloseCandidate(item, "watch")}
                        disabled={confirmingKey === key || closingKey.startsWith(`${key}:`)}
                        style={watchButtonStyle}
                      >
                        {closingKey === watchActionKey ? "Watching..." : manualOverrideCandidate ? "Watch Override" : "Watch"}
                      </button>
                    ) : null}
                    {activeView === "pending" && item.project_id && item.signal_id ? (
                      <button
                        type="button"
                        onClick={() => void handleCloseCandidate(item, "rejected")}
                        disabled={confirmingKey === key || closingKey.startsWith(`${key}:`)}
                        style={dangerButtonStyle}
                      >
                        {closingKey === rejectActionKey ? "Rejecting..." : "Reject"}
                      </button>
                    ) : null}
                    {activeView === "pending" && item.project_id && item.signal_id ? (
                      <button
                        type="button"
                        onClick={() => void handleCloseCandidate(item, "dismissed")}
                        disabled={confirmingKey === key || closingKey.startsWith(`${key}:`)}
                        style={secondaryButtonStyle}
                      >
                        {closingKey === dismissActionKey ? "Dismissing..." : "Dismiss"}
                      </button>
                    ) : null}
                    {activeView === "closed" && normalizedStatus === "confirmed" && item.project_id && item.signal_id ? (
                      <Link
                        href={`/workspace/projects/improvement-detail?project_id=${encodeURIComponent(item.project_id)}&signal_id=${encodeURIComponent(item.signal_id)}`}
                        style={successLinkStyle}
                      >
                        Open Confirmed Improvement
                      </Link>
                    ) : null}
                    {activeView === "action" && item.project_id && item.signal_id ? (
                      <button
                        type="button"
                        onClick={() => void handleCompleteAction(item)}
                        disabled={completingActionKey === key}
                        style={actionButtonStyle}
                      >
                        {completingActionKey === key ? "Completing..." : "Complete Action"}
                      </button>
                    ) : null}
                    {activeView === "watch" && item.project_id && item.signal_id ? (
                      <Link href="/workspace/projects/trajectory" style={secondaryLinkStyle}>
                        Open Trajectory
                      </Link>
                    ) : null}
                    {activeView === "watch" && item.project_id && item.signal_id ? (
                      <button
                        type="button"
                        onClick={() => void handleReviewWatch(item)}
                        disabled={reviewingWatchKey === key || !watchFollowupReady}
                        style={watchFollowupReady ? watchButtonStyle : disabledButtonStyle}
                        title={!watchFollowupReady ? "Fill Follow-up Result before recording." : undefined}
                      >
                        {reviewingWatchKey === key ? "Adding..." : watchFollowupReady ? "Add Watch Follow-up" : "Fill Follow-up Result"}
                      </button>
                    ) : null}
                  </div>
                </section>
              );
            })}
          </div>
        )}
      </RequireAdminAuth>
    </AppContainer>
  );
}

const toolbarStyle = {
  marginBottom: "20px",
  display: "flex",
  gap: "12px",
  flexWrap: "wrap" as const,
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-bg)",
  padding: "16px 18px",
  boxShadow: "var(--app-surface-shadow)",
} as const;

const compactHeaderStyle = {
  ...toolbarStyle,
  alignItems: "center",
  justifyContent: "space-between",
} as const;

const compactHeaderActionsStyle = {
  display: "flex",
  gap: "12px",
  flexWrap: "wrap" as const,
  alignItems: "center",
} as const;

const compactTitleStyle = {
  margin: "4px 0 0",
  color: "var(--app-text-strong)",
  fontSize: "18px",
  fontWeight: 600,
  lineHeight: 1.35,
} as const;

const compactDescriptionStyle = {
  margin: "6px 0 0",
  color: "var(--app-text-muted)",
  fontSize: "13px",
  lineHeight: 1.5,
} as const;

const primaryToolbarLinkStyle = {
  border: "1px solid var(--app-primary-action-border)",
  borderRadius: "8px",
  color: "var(--app-primary-action-fg)",
  background: "var(--app-primary-action-bg)",
  padding: "10px 14px",
  fontSize: "14px",
  fontWeight: 700,
  textDecoration: "none",
} as const;

const toolbarLinkStyle = {
  textDecoration: "none",
  color: "var(--app-secondary-action-fg)",
  fontSize: "14px",
  fontWeight: 700,
  border: "1px solid var(--app-secondary-action-border)",
  borderRadius: "8px",
  background: "var(--app-secondary-action-bg)",
  padding: "10px 14px",
} as const;

const displayModePanelStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-bg)",
  padding: "14px",
  display: "flex",
  justifyContent: "space-between",
  gap: "14px",
  alignItems: "center",
  flexWrap: "wrap" as const,
  marginBottom: "14px",
  boxShadow: "var(--app-surface-shadow)",
} as const;

const displayModeTitleStyle = {
  display: "block",
  marginTop: "4px",
  color: "var(--app-text-strong)",
  fontSize: "15px",
  lineHeight: 1.35,
} as const;

const displayModeCopyStyle = {
  margin: "5px 0 0",
  color: "var(--app-text-muted)",
  fontSize: "13px",
  lineHeight: 1.5,
  maxWidth: "760px",
} as const;

const displayModeToggleStyle = {
  display: "inline-flex",
  gap: "4px",
  border: "1px solid var(--app-surface-border)",
  borderRadius: "999px",
  background: "var(--app-surface-muted-bg)",
  padding: "4px",
} as const;

const displayModeButtonStyle = {
  border: "1px solid transparent",
  borderRadius: "999px",
  background: "transparent",
  color: "var(--app-text-muted)",
  padding: "8px 12px",
  fontSize: "13px",
  fontWeight: 850,
  cursor: "pointer",
} as const;

const activeDisplayModeButtonStyle = {
  ...displayModeButtonStyle,
  border: "1px solid var(--app-primary-action-border)",
  background: "var(--app-primary-action-bg)",
  color: "var(--app-primary-action-fg)",
} as const;

const candidateCardStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-bg)",
  padding: "18px",
  boxShadow: "var(--app-surface-shadow)",
} as const;

const focusedSignalPanelStyle = {
  ...candidateCardStyle,
  border: "1px solid var(--app-info-border)",
  background: "var(--app-info-bg)",
  display: "flex",
  justifyContent: "space-between",
  gap: "12px",
  alignItems: "center",
  flexWrap: "wrap",
} as const;

const manualOverrideCandidateCardStyle = {
  ...candidateCardStyle,
  border: "1px solid var(--app-warning-border)",
  background: "var(--app-warning-bg)",
} as const;

const manualOverrideRecordCardStyle = {
  ...candidateCardStyle,
  border: "1px solid var(--app-warning-border)",
  background: "var(--app-warning-bg)",
} as const;

const candidateTitleStyle = {
  marginTop: "6px",
  fontSize: "18px",
  fontWeight: 500,
  color: "var(--app-text-strong)",
  lineHeight: 1.35,
} as const;

const candidateSourceHintStyle = {
  display: "inline-flex",
  alignItems: "center",
  border: "1px solid var(--app-info-border)",
  borderRadius: "8px",
  background: "var(--app-info-bg)",
  color: "var(--app-info-fg)",
  padding: "7px 10px",
  fontSize: "13px",
  fontWeight: 700,
} as const;

const scoreChipStyle = {
  display: "inline-flex",
  alignItems: "center",
  whiteSpace: "nowrap" as const,
  border: "1px solid var(--app-surface-border)",
  borderRadius: "999px",
  background: "var(--app-surface-muted-bg)",
  color: "var(--app-text-strong)",
  padding: "6px 10px",
  fontSize: "12px",
  fontWeight: 700,
} as const;

const candidateFilterPanelStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-bg)",
  padding: "14px",
  marginBottom: "14px",
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  gap: "12px",
  flexWrap: "wrap" as const,
} as const;

const reviewWorkbenchStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-bg)",
  padding: "14px",
  marginBottom: "14px",
  boxShadow: "var(--app-surface-shadow)",
} as const;

const reviewLoopFollowupStyle = {
  ...reviewWorkbenchStyle,
  border: "1px solid var(--app-surface-strong-border)",
  background: "var(--app-surface-bg)",
} as const;

const projectLearningProfileStyle = {
  ...reviewWorkbenchStyle,
  border: "1px solid var(--app-success-border)",
  background: "var(--app-surface-bg)",
} as const;

const reviewWorkbenchHeaderStyle = {
  display: "flex",
  alignItems: "flex-start",
  justifyContent: "space-between",
  gap: "12px",
  flexWrap: "wrap" as const,
} as const;

const reviewWorkbenchTitleStyle = {
  margin: "4px 0 0",
  color: "var(--app-text-strong)",
  fontSize: "16px",
  fontWeight: 800,
  lineHeight: 1.35,
} as const;

const reviewWorkbenchCopyStyle = {
  margin: "6px 0 0",
  color: "var(--app-text-muted)",
  fontSize: "13px",
  lineHeight: 1.55,
  maxWidth: "760px",
} as const;

const reviewWorkbenchGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))",
  gap: "10px",
  marginTop: "12px",
} as const;

const reviewWorkbenchMetricButtonStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  padding: "11px",
  textAlign: "left" as const,
  display: "grid",
  gap: "6px",
  color: "var(--app-text-muted)",
  cursor: "pointer",
  minHeight: "104px",
  minWidth: 0,
  overflowWrap: "anywhere" as const,
} as const;

const projectLearningProfileGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
  gap: "10px",
  marginTop: "12px",
} as const;

const projectLearningProfileMetricStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  padding: "11px",
  display: "grid",
  gap: "6px",
  color: "var(--app-text-muted)",
  minHeight: "104px",
  fontSize: "13px",
  lineHeight: 1.45,
  minWidth: 0,
  overflowWrap: "anywhere" as const,
} as const;

const projectLearningProfileBoundaryStyle = {
  marginTop: "12px",
  border: "1px solid var(--app-success-border)",
  borderRadius: "8px",
  background: "var(--app-success-bg)",
  padding: "10px 12px",
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
  gap: "10px",
  color: "var(--app-success-fg)",
  fontSize: "13px",
  lineHeight: 1.5,
  overflowWrap: "anywhere" as const,
} as const;

const projectLearningProfileErrorStyle = {
  marginTop: "10px",
  border: "1px solid var(--app-warning-border)",
  borderRadius: "8px",
  background: "var(--app-warning-bg)",
  color: "var(--app-warning-fg)",
  padding: "10px 12px",
  fontSize: "13px",
  fontWeight: 700,
  lineHeight: 1.5,
} as const;

const activeQueueGuideStyle = {
  marginTop: "12px",
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  padding: "10px 12px",
  display: "grid",
  gap: "5px",
  color: "var(--app-text-muted)",
  fontSize: "13px",
  lineHeight: 1.5,
  overflowWrap: "anywhere" as const,
} as const;

const refreshingNoticeStyle = {
  border: "1px solid var(--app-info-border)",
  borderRadius: "8px",
  background: "var(--app-info-bg)",
  color: "var(--app-info-fg)",
  padding: "10px 12px",
  fontSize: "13px",
  fontWeight: 700,
} as const;

const successNoticeStyle = {
  marginTop: "10px",
  border: "1px solid var(--app-success-border)",
  borderRadius: "8px",
  background: "var(--app-success-bg)",
  color: "var(--app-success-fg)",
  padding: "10px 12px",
  fontSize: "13px",
  fontWeight: 700,
  lineHeight: 1.5,
} as const;

const advancedReviewDetailsStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  padding: "12px 14px",
} as const;

const candidateDecisionGuideStyle = {
  marginTop: "12px",
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  padding: "12px",
  display: "grid",
  gap: "8px",
} as const;

const candidateDecisionGuideHeaderStyle = {
  display: "flex",
  justifyContent: "space-between",
  gap: "10px",
  alignItems: "center",
  flexWrap: "wrap" as const,
} as const;

const candidateDecisionGuideBodyStyle = {
  display: "grid",
  gap: "6px",
  borderLeft: "3px solid var(--app-info-border)",
  background: "var(--app-surface-soft-bg)",
  borderRadius: "8px",
  padding: "10px 12px",
} as const;

const candidateDecisionShortcutStyle = (tone: "good" | "watch" | "neutral") =>
  ({
    display: "grid",
    gridTemplateColumns: "minmax(150px, 0.55fr) minmax(220px, 1fr)",
    gap: "10px",
    border: `1px solid ${tone === "good" ? "var(--app-success-border)" : tone === "watch" ? "var(--app-warning-border)" : "var(--app-info-border)"}`,
    borderRadius: "8px",
    background: tone === "good" ? "var(--app-success-bg)" : tone === "watch" ? "var(--app-warning-bg)" : "var(--app-info-bg)",
    color: tone === "good" ? "var(--app-success-fg)" : tone === "watch" ? "var(--app-warning-fg)" : "var(--app-info-fg)",
    padding: "10px 12px",
  }) as const;

const candidateDecisionShortcutBodyStyle = {
  display: "grid",
  gap: "4px",
  color: "var(--app-text-muted)",
  fontSize: "12px",
  fontWeight: 700,
  lineHeight: 1.45,
} as const;

const candidateNextStepTitleStyle = {
  color: "var(--app-info-fg)",
  fontSize: "14px",
  fontWeight: 900,
  lineHeight: 1.35,
} as const;

const candidateNextStepBodyStyle = {
  color: "var(--app-text-muted)",
  fontSize: "13px",
  fontWeight: 650,
  lineHeight: 1.55,
} as const;

const candidateDecisionOptionGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))",
  gap: "8px",
} as const;

const candidateDecisionOptionStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-bg)",
  padding: "9px 10px",
  display: "grid",
  gap: "5px",
  color: "var(--app-text-muted)",
  fontSize: "12px",
  lineHeight: 1.45,
} as const;

const reasoningAssessmentAdvisoryStyle = (tone: "good" | "watch" | "neutral") =>
  ({
    marginTop: "12px",
    border: `1px solid ${tone === "good" ? "var(--app-success-border)" : tone === "watch" ? "var(--app-warning-border)" : "var(--app-info-border)"}`,
    borderRadius: "8px",
    background: tone === "good" ? "var(--app-success-bg)" : tone === "watch" ? "var(--app-warning-bg)" : "var(--app-info-bg)",
    color: tone === "good" ? "var(--app-success-fg)" : tone === "watch" ? "var(--app-warning-fg)" : "var(--app-info-fg)",
    padding: "12px",
    display: "grid",
    gap: "10px",
  }) as const;

const reasoningAssessmentHeaderStyle = {
  display: "flex",
  justifyContent: "space-between",
  gap: "10px",
  alignItems: "start",
  flexWrap: "wrap" as const,
} as const;

const reasoningAssessmentChipStyle = (tone: "good" | "watch" | "neutral") =>
  ({
    border: `1px solid ${tone === "good" ? "var(--app-success-border)" : tone === "watch" ? "var(--app-warning-border)" : "var(--app-info-border)"}`,
    borderRadius: "999px",
    background: "var(--app-surface-bg)",
    padding: "4px 8px",
    fontSize: "11px",
    fontWeight: 900,
    whiteSpace: "nowrap" as const,
  }) as const;

const reasoningAssessmentSummaryStyle = {
  margin: 0,
  color: "var(--app-text-muted)",
  fontSize: "13px",
  lineHeight: 1.5,
  fontWeight: 650,
} as const;

const reasoningAssessmentGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 520px), 1fr))",
  gap: "10px",
} as const;

const reasoningAssessmentItemStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-bg)",
  padding: "9px 10px",
  display: "grid",
  gap: "5px",
  color: "var(--app-text-muted)",
  fontSize: "12px",
  lineHeight: 1.45,
} as const;

const reasoningAssessmentValueStyle = {
  whiteSpace: "pre-wrap" as const,
  overflowWrap: "anywhere" as const,
  color: "var(--app-text-strong)",
  fontSize: "12px",
  lineHeight: 1.5,
} as const;

const reasoningAssessmentCollapsedConclusionStyle = {
  border: "1px dashed var(--app-warning-border)",
  borderRadius: "8px",
  background: "var(--app-warning-bg)",
  padding: "8px",
  display: "grid",
  gap: "8px",
} as const;

const reasoningAssessmentCollapsedSummaryStyle = {
  cursor: "pointer",
  color: "var(--app-warning-fg)",
  fontSize: "12px",
  fontWeight: 900,
  lineHeight: 1.45,
} as const;

const reasoningAssessmentUnverifiedPrefixStyle = {
  border: "1px solid var(--app-warning-border)",
  borderRadius: "999px",
  color: "var(--app-warning-fg)",
  background: "var(--app-surface-bg)",
  padding: "4px 8px",
  width: "fit-content",
  fontSize: "11px",
  fontWeight: 900,
  textTransform: "uppercase" as const,
} as const;

const reasoningAssessmentDegradedConclusionStyle = {
  ...reasoningAssessmentValueStyle,
  color: "var(--app-text-muted)",
  opacity: 0.78,
} as const;

const reasoningAssessmentBridgeItemStyle = {
  ...reasoningAssessmentItemStyle,
  gridColumn: "1 / -1",
  gap: "10px",
} as const;

const reasoningAssessmentChecklistItemStyle = {
  ...reasoningAssessmentItemStyle,
  gridColumn: "1 / -1",
  gap: "10px",
} as const;

const reasoningAssessmentChecklistGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 240px), 1fr))",
  gap: "8px",
} as const;

const reasoningAssessmentChecklistCardStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  padding: "8px 9px",
  display: "grid",
  gap: "5px",
  minWidth: 0,
} as const;

const reasoningAssessmentIntegrityCardStyle = {
  ...reasoningAssessmentChecklistCardStyle,
  border: "1px solid var(--app-warning-border)",
  background: "var(--app-warning-bg)",
} as const;

const reasoningAssessmentBridgeHeaderStyle = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "start",
  gap: "10px",
  flexWrap: "wrap" as const,
} as const;

const reasoningAssessmentBridgeTitleStyle = {
  display: "grid",
  gap: "4px",
  minWidth: 0,
} as const;

const reasoningAssessmentBridgeGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 280px), 1fr))",
  gap: "10px",
} as const;

const reasoningAssessmentBridgeColumnStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  padding: "9px",
  display: "grid",
  gap: "5px",
  minWidth: 0,
} as const;

const reasoningAssessmentButtonStyle = {
  border: "1px solid var(--app-primary-action-border)",
  borderRadius: "8px",
  background: "var(--app-primary-action-bg)",
  color: "var(--app-primary-action-fg)",
  padding: "7px 10px",
  fontSize: "12px",
  fontWeight: 900,
  cursor: "pointer",
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  gap: "6px",
  whiteSpace: "nowrap" as const,
} as const;

const reasoningAssessmentButtonDisabledStyle = {
  ...reasoningAssessmentButtonStyle,
  border: "1px solid var(--app-surface-border)",
  background: "var(--app-surface-muted-bg)",
  color: "var(--app-text-subtle)",
  cursor: "wait",
} as const;

const reasoningAssessmentDraftStyle = {
  border: "1px solid var(--app-info-border)",
  borderRadius: "8px",
  background: "var(--app-info-bg)",
  color: "var(--app-info-fg)",
  padding: "10px",
  display: "grid",
  gap: "7px",
  fontSize: "12px",
  lineHeight: 1.5,
} as const;

const reasoningAssessmentDraftHeaderStyle = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  gap: "8px",
  flexWrap: "wrap" as const,
} as const;

const reasoningAssessmentDraftGridStyle = {
  display: "grid",
  gap: "3px",
  minWidth: 0,
} as const;

const reasoningAssessmentComparisonGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 320px), 1fr))",
  gap: "8px",
} as const;

const reasoningAssessmentComparisonColumnStyle = {
  border: "1px solid var(--app-info-border)",
  borderRadius: "8px",
  background: "var(--app-surface-bg)",
  padding: "9px",
  display: "grid",
  gap: "5px",
  minWidth: 0,
} as const;

const reasoningAssessmentDraftChipStyle = (answer?: string) => {
  const normalized = (answer || "").toLowerCase();
  return {
    border: `1px solid ${
      normalized === "yes"
        ? "var(--app-warning-border)"
        : normalized === "no"
          ? "var(--app-success-border)"
          : "var(--app-info-border)"
    }`,
    borderRadius: "999px",
    background: "var(--app-surface-bg)",
    color: "var(--app-text-strong)",
    padding: "4px 8px",
    fontSize: "11px",
    fontWeight: 900,
    whiteSpace: "nowrap" as const,
  } as const;
};

const reasoningAssessmentErrorStyle = {
  border: "1px solid var(--app-danger-border)",
  borderRadius: "8px",
  background: "var(--app-danger-bg)",
  color: "var(--app-danger-fg)",
  padding: "8px 9px",
  fontSize: "12px",
  fontWeight: 750,
  lineHeight: 1.45,
} as const;

const simplifiedDecisionCardStyle = (tone: "good" | "watch" | "neutral") =>
  ({
    marginTop: "12px",
    border: `1px solid ${tone === "good" ? "var(--app-success-border)" : tone === "watch" ? "var(--app-warning-border)" : "var(--app-info-border)"}`,
    borderRadius: "8px",
    background: tone === "good" ? "var(--app-success-bg)" : tone === "watch" ? "var(--app-warning-bg)" : "var(--app-info-bg)",
    padding: "14px",
    display: "grid",
    gap: "10px",
  }) as const;

const simplifiedDecisionHeaderStyle = {
  display: "grid",
  gap: "4px",
  color: "var(--app-text-strong)",
} as const;

const simplifiedDecisionBodyStyle = {
  display: "grid",
  gap: "6px",
  color: "var(--app-text-muted)",
  fontSize: "13px",
  lineHeight: 1.55,
  fontWeight: 650,
} as const;

const simplifiedDecisionSnapshotGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))",
  gap: "8px",
} as const;

const simplifiedDecisionSnapshotCardStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-bg)",
  padding: "10px 12px",
  display: "grid",
  gap: "5px",
  color: "var(--app-text-muted)",
  fontSize: "12px",
  lineHeight: "1.45",
  minWidth: 0,
  overflowWrap: "anywhere" as const,
} as const;

const simplifiedDiagnosticsDetailsStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-bg)",
  padding: "10px 12px",
} as const;

const simplifiedDiagnosticsGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
  gap: "8px",
  marginTop: "10px",
} as const;

const simplifiedDiagnosticsHintStyle = {
  marginTop: "10px",
  color: "var(--app-text-subtle)",
  fontSize: "12px",
  lineHeight: 1.5,
  fontWeight: 700,
} as const;

const manualSourceRouteStyle = {
  display: "flex",
  gap: "8px",
  flexWrap: "wrap" as const,
  alignItems: "center",
  color: "var(--app-text-muted)",
  fontSize: "12px",
  fontWeight: 700,
} as const;

const manualSourceRouteLinkStyle = {
  border: "1px solid var(--app-info-border)",
  borderRadius: "8px",
  background: "var(--app-info-bg)",
  color: "var(--app-info-fg)",
  padding: "6px 8px",
  textDecoration: "none",
  fontSize: "12px",
  fontWeight: 800,
} as const;

const manualOverrideChipStyle = {
  border: "1px solid var(--app-warning-border)",
  borderRadius: "999px",
  background: "var(--app-warning-bg)",
  color: "var(--app-warning-fg)",
  padding: "5px 8px",
  fontSize: "12px",
  fontWeight: 800,
} as const;

const finalTakeawayHandoffChipStyle = {
  border: "1px solid var(--app-success-border)",
  borderRadius: "999px",
  background: "var(--app-success-bg)",
  color: "var(--app-success-fg)",
  padding: "5px 8px",
  fontSize: "12px",
  fontWeight: 800,
} as const;

const knowledgeConvergenceChipStyle = {
  border: "1px solid var(--app-info-border)",
  borderRadius: "999px",
  background: "var(--app-info-bg)",
  color: "var(--app-info-fg)",
  padding: "5px 8px",
  fontSize: "12px",
  fontWeight: 800,
} as const;

const knowledgeConvergencePanelStyle = {
  marginTop: "12px",
  border: "1px solid var(--app-info-border)",
  borderRadius: "8px",
  background: "var(--app-info-bg)",
  padding: "12px",
} as const;

const knowledgeConvergenceHeaderStyle = {
  display: "flex",
  justifyContent: "space-between",
  gap: "12px",
  alignItems: "flex-start",
  flexWrap: "wrap",
} as const;

const knowledgeConvergenceSourceStyle = {
  color: "var(--app-info-fg)",
  fontSize: "12px",
  fontWeight: 800,
  overflowWrap: "anywhere" as const,
  textAlign: "right" as const,
} as const;

const knowledgeConvergenceBodyStyle = {
  marginTop: "8px",
  color: "var(--app-text-muted)",
  fontSize: "13px",
  lineHeight: 1.55,
} as const;

const knowledgeReviewPostureStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))",
  gap: "8px",
  marginTop: "10px",
} as const;

const knowledgeRationaleGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
  gap: "8px",
  marginTop: "10px",
} as const;

const knowledgeRationaleItemStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-bg)",
  padding: "10px",
  display: "grid",
  gap: "6px",
  color: "var(--app-text-muted)",
  fontSize: "13px",
  lineHeight: 1.45,
} as const;

const knowledgeQualityPanelStyle = {
  marginTop: "10px",
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-bg)",
  padding: "10px",
  display: "grid",
  gridTemplateColumns: "minmax(0, 1fr) auto",
  gap: "8px",
  alignItems: "start",
} as const;

const knowledgeQualityScoreStyle = {
  border: "1px solid var(--app-info-border)",
  borderRadius: "999px",
  background: "var(--app-info-bg)",
  color: "var(--app-info-fg)",
  padding: "5px 8px",
  fontSize: "12px",
  fontWeight: 900,
} as const;

const knowledgeQualityRecommendationStyle = {
  ...knowledgeConvergenceBodyStyle,
  gridColumn: "1 / -1",
  color: "var(--app-info-fg)",
  fontWeight: 800,
} as const;

const knowledgeFactorRowStyle = {
  gridColumn: "1 / -1",
  display: "flex",
  gap: "8px",
  flexWrap: "wrap" as const,
  marginTop: "4px",
} as const;

const knowledgeFactorChipStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "999px",
  background: "var(--app-surface-bg)",
  color: "var(--app-text-muted)",
  padding: "5px 8px",
  fontSize: "12px",
  fontWeight: 800,
} as const;

const knowledgeMetricGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))",
  gap: "8px",
  marginTop: "10px",
} as const;

const knowledgeMetricStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-bg)",
  padding: "10px",
  display: "grid",
  gap: "6px",
  alignContent: "start",
} as const;

const knowledgeMetricValueStyle = {
  display: "block",
  color: "var(--app-text-strong)",
  fontSize: "18px",
  lineHeight: 1.2,
} as const;

const knowledgeProjectRowStyle = {
  display: "flex",
  gap: "8px",
  flexWrap: "wrap",
  marginTop: "10px",
} as const;

const knowledgeProjectPillStyle = {
  border: "1px solid var(--app-success-border)",
  borderRadius: "999px",
  background: "var(--app-success-bg)",
  color: "var(--app-success-fg)",
  padding: "6px 9px",
  fontSize: "12px",
  fontWeight: 800,
  overflowWrap: "anywhere" as const,
} as const;

const knowledgeRouteRowStyle = {
  display: "flex",
  gap: "8px",
  flexWrap: "wrap",
  marginTop: "12px",
} as const;

const manualOverrideNoticeStyle = {
  marginTop: "10px",
  border: "1px solid var(--app-warning-border)",
  borderRadius: "8px",
  background: "var(--app-warning-bg)",
  color: "var(--app-warning-fg)",
  padding: "10px 12px",
  fontSize: "13px",
  lineHeight: 1.55,
} as const;

const deepProjectMatchReviewStyle = {
  marginTop: "10px",
  border: "1px solid var(--app-info-border)",
  borderRadius: "8px",
  background: "var(--app-info-bg)",
  color: "var(--app-info-fg)",
  padding: "12px",
  display: "grid",
  gap: "10px",
  fontSize: "13px",
  lineHeight: 1.55,
} as const;

const deepProjectMatchReviewHeaderStyle = {
  display: "flex",
  justifyContent: "space-between",
  gap: "12px",
  alignItems: "flex-start",
  flexWrap: "wrap" as const,
} as const;

const deepProjectMatchReviewChipStyle = {
  border: "1px solid var(--app-info-border)",
  borderRadius: "999px",
  background: "var(--app-surface-bg)",
  color: "var(--app-info-fg)",
  padding: "5px 8px",
  fontSize: "12px",
  fontWeight: 800,
  whiteSpace: "nowrap" as const,
} as const;

const deepProjectMatchReviewNoteStyle = {
  margin: 0,
  color: "var(--app-info-fg)",
} as const;

const deepProjectMatchGeneratedAnalysisStyle = {
  border: "1px solid var(--app-info-border)",
  borderRadius: "8px",
  background: "var(--app-surface-bg)",
  padding: "10px",
  display: "grid",
  gap: "6px",
  color: "var(--app-text-muted)",
} as const;

const deepProjectMatchReviewGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
  gap: "8px",
} as const;

const deepProjectMatchReviewDetailsStyle = {
  borderTop: "1px solid var(--app-info-border)",
  paddingTop: "8px",
} as const;

const deepProjectMatchReviewChecklistStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
  gap: "8px",
  marginTop: "8px",
} as const;

const manualOverrideOutcomeStyle = {
  marginTop: "10px",
  border: "1px solid var(--app-warning-border)",
  borderRadius: "8px",
  background: "var(--app-warning-bg)",
  color: "var(--app-warning-fg)",
  padding: "10px 12px",
  display: "grid",
  gap: "5px",
  fontSize: "13px",
  lineHeight: 1.55,
} as const;

const manualOverrideReviewGuideStyle = {
  marginTop: "10px",
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
  gap: "10px",
} as const;

const manualOverrideCalibrationBandStyle = {
  display: "grid",
  gap: "14px",
  border: "1px solid var(--app-warning-border)",
  borderRadius: "8px",
  background: "var(--app-warning-bg)",
  padding: "16px",
  boxShadow: "var(--app-surface-shadow)",
} as const;

const manualOverrideCalibrationHeaderStyle = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  gap: "12px",
  flexWrap: "wrap" as const,
} as const;

const summaryBandStyle = {
  display: "grid",
  gap: "16px",
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-bg)",
  padding: "16px",
  boxShadow: "var(--app-surface-shadow)",
} as const;

const calibrationBandStyle = {
  ...summaryBandStyle,
  border: "1px solid var(--app-surface-border)",
  background: "var(--app-surface-bg)",
} as const;

const gateComparisonBandStyle = {
  display: "grid",
  gap: "12px",
  border: "1px solid var(--app-info-border)",
  borderRadius: "8px",
  background: "var(--app-info-bg)",
  padding: "14px",
} as const;

const gateComparisonHeaderStyle = {
  display: "flex",
  justifyContent: "space-between",
  gap: "12px",
  alignItems: "center",
  flexWrap: "wrap" as const,
} as const;

const gateComparisonGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))",
  gap: "10px",
} as const;

const gateComparisonColumnStyle = {
  display: "grid",
  gap: "7px",
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-bg)",
  color: "var(--app-text-muted)",
  padding: "10px 12px",
  minWidth: 0,
} as const;

const reviewCalibrationPlanStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  padding: "14px",
  display: "grid",
  gap: "10px",
} as const;

const manualSourceLearningStyle = {
  ...reviewCalibrationPlanStyle,
  border: "1px solid var(--app-success-border)",
  background: "var(--app-success-bg)",
} as const;

const operatingSurfaceHeaderStyle = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  gap: "12px",
  flexWrap: "wrap" as const,
} as const;

const operatingSurfaceTitleStyle = {
  display: "block",
  marginTop: "4px",
  color: "var(--app-text-strong)",
  fontSize: "15px",
  lineHeight: "1.35",
} as const;

const operatingSurfaceGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
  gap: "10px",
} as const;

const operatingSurfaceCardStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-bg)",
  padding: "12px",
  display: "grid",
  gap: "8px",
  color: "var(--app-text-muted)",
  fontSize: "13px",
  lineHeight: 1.5,
  minWidth: 0,
} as const;

const operatingSurfaceMetricRowStyle = {
  display: "flex",
  gap: "7px",
  flexWrap: "wrap" as const,
  color: "var(--app-text-subtle)",
  fontSize: "12px",
  fontWeight: 800,
} as const;

const reviewCalibrationActionGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
  gap: "10px",
} as const;

const reviewCalibrationActionStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-bg)",
  padding: "10px 12px",
  display: "grid",
  gap: "5px",
  color: "var(--app-text-muted)",
  fontSize: "13px",
  lineHeight: 1.5,
} as const;

const gateComparisonValueStyle = {
  color: "var(--app-text-strong)",
  fontSize: "15px",
  fontWeight: 900,
  lineHeight: "1.35",
  overflowWrap: "anywhere" as const,
} as const;

const gateComparisonTextStyle = {
  color: "var(--app-text-muted)",
  fontSize: "12px",
  lineHeight: "1.5",
} as const;

const gateComparisonActionRowStyle = {
  display: "flex",
  gap: "8px",
  flexWrap: "wrap" as const,
} as const;

const gateComparisonButtonStyle = {
  border: "1px solid var(--app-info-border)",
  borderRadius: "8px",
  background: "var(--app-info-bg)",
  color: "var(--app-info-fg)",
  padding: "7px 10px",
  fontSize: "12px",
  fontWeight: 900,
  cursor: "pointer",
} as const;

const gateAlignedChipStyle = {
  border: "1px solid var(--app-success-border)",
  borderRadius: "999px",
  background: "var(--app-success-bg)",
  color: "var(--app-success-fg)",
  padding: "6px 10px",
  fontSize: "12px",
  fontWeight: 900,
} as const;

const gateMismatchChipStyle = {
  border: "1px solid var(--app-warning-border)",
  borderRadius: "999px",
  background: "var(--app-warning-bg)",
  color: "var(--app-warning-fg)",
  padding: "6px 10px",
  fontSize: "12px",
  fontWeight: 900,
} as const;

const summaryMetricRowStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(145px, 1fr))",
  gap: "10px",
  alignItems: "start",
} as const;

const summaryItemStyle = {
  display: "grid",
  gap: "6px",
  color: "var(--app-text-muted)",
  fontSize: "15px",
  minWidth: 0,
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-bg)",
  padding: "10px 12px",
} as const;

const summaryValueStyle = {
  color: "var(--app-text-strong)",
  fontSize: "15px",
  fontWeight: 800,
  lineHeight: "1.35",
  overflowWrap: "anywhere" as const,
  wordBreak: "break-word" as const,
} as const;

const summaryBreakdownStyle = {
  gridColumn: "1 / -1",
  display: "grid",
  gap: "10px",
  color: "var(--app-text-strong)",
  paddingTop: "2px",
} as const;

const summaryDetailsStyle = {
  gridColumn: "1 / -1",
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-bg)",
  padding: "10px 12px",
} as const;

const summaryDetailsSummaryStyle = {
  color: "var(--app-text-strong)",
  fontSize: "13px",
  fontWeight: 900,
  cursor: "pointer",
  lineHeight: "1.45",
} as const;

const summaryChipRowStyle = {
  display: "flex",
  gap: "8px",
  flexWrap: "wrap" as const,
} as const;

const summaryMiniChipStyle = {
  display: "inline-flex",
  alignItems: "center",
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  color: "var(--app-text-strong)",
  padding: "6px 10px",
  fontSize: "12px",
  fontWeight: 800,
} as const;

const opsInterpretationStyle = {
  gridColumn: "1 / -1",
  display: "grid",
  gap: "10px",
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-bg)",
  padding: "12px",
} as const;

const opsInterpretationGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
  gap: "10px",
} as const;

const opsInterpretationItemStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  color: "var(--app-text-muted)",
  padding: "10px 12px",
  display: "grid",
  gap: "6px",
  fontSize: "13px",
  lineHeight: "1.55",
} as const;

const summaryLabelStyle = {
  color: "var(--app-text-subtle)",
  fontSize: "12px",
  fontWeight: 800,
  textTransform: "uppercase" as const,
  letterSpacing: 0,
} as const;

const recordFilterPanelStyle = {
  border: "1px solid #e5e7eb",
  borderRadius: "20px",
  background: "#ffffff",
  padding: "16px 18px",
  display: "grid",
  gap: "14px",
  boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
} as const;

const recordFilterTopRowStyle = {
  display: "flex",
  justifyContent: "space-between",
  gap: "16px",
  alignItems: "start",
  flexWrap: "wrap" as const,
  color: "#111827",
  fontSize: "13px",
} as const;

const recordFilterTopActionsStyle = {
  display: "flex",
  gap: "16px",
  alignItems: "start",
  flexWrap: "wrap" as const,
  justifyContent: "flex-end",
} as const;

const recordFilterTitleStyle = {
  display: "grid",
  gap: "4px",
  minWidth: "150px",
} as const;

const recordFilterInlineGroupStyle = {
  display: "grid",
  gap: "8px",
  minWidth: "150px",
} as const;

const recordFilterActionRowStyle = {
  display: "flex",
  gap: "8px",
  flexWrap: "wrap" as const,
  alignSelf: "end",
} as const;

const recordFilterBoxStyle = {
  border: "1px solid #e5e7eb",
  borderRadius: "8px",
  background: "#ffffff",
  padding: "12px",
  display: "grid",
  gap: "10px",
} as const;

const recordFilterHintStyle = {
  color: "#6b7280",
  fontSize: "12px",
  fontWeight: 700,
} as const;

const recordFilterSummaryStyle = {
  border: "1px solid #e5e7eb",
  borderRadius: "8px",
  background: "#ffffff",
  color: "#374151",
  padding: "8px 10px",
  fontSize: "13px",
  fontWeight: 700,
  lineHeight: "1.45",
} as const;

const recordFilterButtonRowStyle = {
  display: "flex",
  gap: "8px",
  flexWrap: "wrap" as const,
} as const;

const recordSearchInputStyle = {
  width: "100%",
  border: "1px solid #d1d5db",
  borderRadius: "8px",
  background: "#ffffff",
  color: "#111827",
  padding: "10px 12px",
  fontSize: "14px",
  boxSizing: "border-box" as const,
} as const;

const filterButtonStyle = {
  border: "1px solid #d1d5db",
  borderRadius: "999px",
  background: "#ffffff",
  color: "#374151",
  padding: "7px 10px",
  fontSize: "12px",
  fontWeight: 800,
  cursor: "pointer",
} as const;

const activeFilterButtonStyle = {
  ...filterButtonStyle,
  border: "1px solid #111827",
  background: "#111827",
  color: "#ffffff",
} as const;

const resetFilterButtonStyle = {
  border: "1px solid #d1d5db",
  borderRadius: "8px",
  background: "#ffffff",
  color: "#374151",
  padding: "6px 9px",
  fontSize: "12px",
  fontWeight: 800,
  cursor: "pointer",
} as const;

const tabListStyle = {
  display: "flex",
  gap: "8px",
  marginBottom: "18px",
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-bg)",
  padding: "12px",
  flexWrap: "wrap" as const,
  boxShadow: "var(--app-surface-shadow)",
} as const;

const tabButtonStyle = {
  padding: "9px 12px",
  border: "1px solid var(--app-secondary-action-border)",
  borderRadius: "999px",
  background: "var(--app-secondary-action-bg)",
  color: "var(--app-secondary-action-fg)",
  cursor: "pointer",
  fontWeight: 800,
} as const;

const activeTabStyle = {
  ...tabButtonStyle,
  color: "var(--app-primary-action-fg)",
  border: "1px solid var(--app-primary-action-border)",
  background: "var(--app-primary-action-bg)",
} as const;

const emptyCardStyle = {
  border: "1px solid #e5e7eb",
  borderRadius: "14px",
  padding: "20px",
  background: "#ffffff",
  color: "#4b5563",
  display: "grid",
  gap: "10px",
} as const;

const emptyTitleStyle = {
  color: "#111827",
  fontSize: "15px",
  fontWeight: 800,
  lineHeight: "1.4",
} as const;

const emptyDescriptionStyle = {
  margin: 0,
  color: "#4b5563",
  fontSize: "13px",
  lineHeight: "1.6",
} as const;

const errorCardStyle = {
  border: "1px solid #fecaca",
  borderRadius: "14px",
  padding: "14px 16px",
  background: "#fff1f2",
  color: "#be123c",
  marginBottom: "16px",
} as const;

const infoCardStyle = {
  border: "1px solid #bfdbfe",
  borderRadius: "14px",
  padding: "14px 16px",
  background: "#eff6ff",
  color: "#1e3a8a",
  marginBottom: "16px",
} as const;

const successCardStyle = {
  border: "1px solid #bbf7d0",
  borderRadius: "14px",
  padding: "14px 16px",
  background: "#f0fdf4",
  marginBottom: "16px",
} as const;

const noticeCardStyle = {
  border: "1px solid #d1d5db",
  borderRadius: "8px",
  padding: "14px 16px",
  background: "#f9fafb",
  marginBottom: "16px",
} as const;

const successLinkStyle = {
  color: "var(--app-success-fg)",
  fontSize: "14px",
  fontWeight: 800,
  textDecoration: "none",
} as const;

const metaStyle = {
  fontSize: "12px",
  color: "var(--app-text-subtle)",
  textTransform: "uppercase" as const,
  letterSpacing: "0.4px",
  fontWeight: 700,
} as const;

const projectFilterLinkStyle = {
  ...metaStyle,
  border: "0",
  background: "transparent",
  padding: "0",
  cursor: "pointer",
  textAlign: "left" as const,
} as const;

const chipStyle = {
  display: "inline-flex",
  alignItems: "center",
  padding: "5px 10px",
  borderRadius: "999px",
  border: "1px solid var(--app-surface-border)",
  background: "var(--app-surface-muted-bg)",
  fontSize: "12px",
  color: "var(--app-text-strong)",
  fontWeight: 600,
} as const;

const outcomeChipBaseStyle = {
  display: "inline-flex",
  alignItems: "center",
  padding: "3px 8px",
  borderRadius: "999px",
  border: "1px solid var(--app-surface-border)",
  background: "var(--app-surface-muted-bg)",
  fontSize: "12px",
  color: "var(--app-text-strong)",
  fontWeight: 800,
} as const;

const bodyTextStyle = {
  marginTop: "12px",
  fontSize: "14px",
  lineHeight: "1.7",
  color: "var(--app-text-muted)",
} as const;

const mutedBlockStyle = {
  marginTop: "12px",
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  padding: "10px 12px",
  fontSize: "13px",
  lineHeight: "1.6",
  color: "var(--app-text-muted)",
} as const;

const actionEligibilityPanelStyle = {
  marginTop: "12px",
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  padding: "12px",
  display: "grid",
  gap: "10px",
} as const;

const actionEligibilityHeaderStyle = {
  display: "flex",
  justifyContent: "space-between",
  gap: "12px",
  alignItems: "center",
  flexWrap: "wrap" as const,
  color: "var(--app-text-strong)",
  fontSize: "13px",
} as const;

const actionEligibilityGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))",
  gap: "10px",
} as const;

const actionEligibilitySignalStyle = {
  borderTop: "1px solid var(--app-surface-border)",
  paddingTop: "8px",
  color: "var(--app-text-subtle)",
  fontSize: "12px",
  fontWeight: 700,
  lineHeight: "1.5",
} as const;

const recordEligibilityPanelStyle = {
  ...actionEligibilityPanelStyle,
  border: "1px solid var(--app-surface-border)",
  background: "var(--app-surface-muted-bg)",
} as const;

const detailGridStyle = {
  marginTop: "12px",
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
  gap: "10px",
} as const;

const detailItemStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  padding: "10px 12px",
  background: "var(--app-surface-bg)",
  display: "grid",
  gap: "5px",
  color: "var(--app-text-strong)",
  fontSize: "13px",
  lineHeight: "1.45",
} as const;

const detailLabelStyle = {
  display: "block",
  color: "var(--app-text-subtle)",
  fontSize: "11px",
  fontWeight: 800,
  textTransform: "uppercase" as const,
  letterSpacing: 0,
  marginBottom: "4px",
} as const;

const recordMetaGridStyle = {
  marginTop: "14px",
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
  gap: "10px",
} as const;

const recordSummaryLineStyle = {
  marginTop: "12px",
  border: "1px solid #e5e7eb",
  borderRadius: "8px",
  background: "#ffffff",
  color: "#374151",
  padding: "10px 12px",
  fontSize: "13px",
  fontWeight: 600,
  lineHeight: "1.55",
} as const;

const recordLearningSignalStyle = {
  marginTop: "8px",
  border: "1px solid #bbf7d0",
  borderLeft: "3px solid #10b981",
  borderRadius: "8px",
  background: "#ecfdf5",
  color: "#065f46",
  padding: "10px 12px",
  fontSize: "13px",
  fontWeight: 800,
  lineHeight: "1.5",
} as const;

const recordContextGridStyle = {
  marginTop: "10px",
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
  gap: "10px",
} as const;

const recordContextCardStyle = {
  border: "1px solid #e5e7eb",
  borderRadius: "8px",
  background: "#ffffff",
  color: "#374151",
  padding: "10px 12px",
  display: "grid",
  gap: "6px",
  fontSize: "13px",
  lineHeight: "1.55",
} as const;

const recordDetailsStyle = {
  marginTop: "10px",
  border: "1px solid #e5e7eb",
  borderRadius: "8px",
  background: "#ffffff",
  padding: "10px 12px",
} as const;

const recordMetaItemStyle = {
  border: "1px solid #e5e7eb",
  borderRadius: "8px",
  background: "#ffffff",
  color: "#374151",
  padding: "10px 12px",
  display: "grid",
  gap: "5px",
  fontSize: "13px",
  lineHeight: "1.45",
  minWidth: 0,
  overflowWrap: "anywhere" as const,
} as const;

const recordVerificationChipRowStyle = {
  marginTop: "12px",
  display: "flex",
  gap: "8px",
  flexWrap: "wrap" as const,
  alignItems: "center",
  border: "1px solid #e5e7eb",
  borderRadius: "8px",
  background: "#ffffff",
  padding: "10px 12px",
} as const;

const recordVerificationLabelStyle = {
  color: "#6b7280",
  fontSize: "12px",
  fontWeight: 900,
  textTransform: "uppercase" as const,
  letterSpacing: "0.4px",
} as const;

const recordVerificationChipStyle = {
  display: "inline-flex",
  alignItems: "center",
  border: "1px solid #d1d5db",
  borderRadius: "999px",
  background: "#ffffff",
  color: "#374151",
  padding: "5px 9px",
  fontSize: "12px",
  fontWeight: 800,
} as const;

const reasonLabelStyle = {
  display: "block",
  marginBottom: "6px",
  fontSize: "12px",
  color: "#6b7280",
  fontWeight: 700,
  textTransform: "uppercase" as const,
  letterSpacing: "0.4px",
} as const;

const reasonInputStyle = {
  width: "100%",
  minHeight: "64px",
  resize: "vertical" as const,
  border: "1px solid #d1d5db",
  borderRadius: "8px",
  padding: "10px 12px",
  fontSize: "14px",
  lineHeight: "1.5",
  color: "#111827",
  background: "#ffffff",
  boxSizing: "border-box" as const,
} as const;

const metadataPanelStyle = {
  marginTop: "10px",
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
  gap: "12px",
} as const;

const metadataDetailsStyle = {
  marginTop: "12px",
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-bg)",
  padding: "10px 12px",
} as const;

const metadataColumnStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  padding: "12px",
  background: "var(--app-surface-muted-bg)",
  display: "grid",
  gap: "8px",
} as const;

const metadataHeadingStyle = {
  fontSize: "12px",
  color: "var(--app-text-strong)",
  fontWeight: 800,
  textTransform: "uppercase" as const,
  letterSpacing: "0.4px",
} as const;

const metadataFieldLabelStyle = {
  color: "var(--app-text-subtle)",
  fontSize: "12px",
  fontWeight: 800,
} as const;

const metadataInputStyle = {
  width: "100%",
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  padding: "9px 10px",
  fontSize: "13px",
  color: "var(--app-text-strong)",
  background: "var(--app-surface-bg)",
  boxSizing: "border-box" as const,
} as const;

const metadataTextareaStyle = {
  ...metadataInputStyle,
  minHeight: "58px",
  resize: "vertical" as const,
  lineHeight: "1.45",
} as const;

const overrideConfirmWarningStyle = {
  gridColumn: "1 / -1",
  border: "1px solid var(--app-danger-border)",
  borderRadius: "8px",
  background: "var(--app-danger-bg)",
  color: "var(--app-danger-fg)",
  padding: "10px 12px",
  fontSize: "13px",
  fontWeight: 800,
  lineHeight: "1.45",
} as const;

const overrideInlineErrorStyle = {
  gridColumn: "1 / -1",
  border: "1px solid var(--app-danger-border)",
  borderRadius: "8px",
  background: "var(--app-danger-bg)",
  color: "var(--app-danger-fg)",
  padding: "10px 12px",
  fontSize: "13px",
  fontWeight: 800,
} as const;

const overrideInlineHelpStyle = {
  gridColumn: "1 / -1",
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  color: "var(--app-text-muted)",
  padding: "10px 12px",
  fontSize: "13px",
  fontWeight: 700,
  lineHeight: "1.45",
} as const;

const primaryButtonStyle = {
  padding: "7px 12px",
  borderRadius: "8px",
  border: "1px solid var(--app-primary-action-border)",
  background: "var(--app-primary-action-bg)",
  color: "var(--app-primary-action-fg)",
  cursor: "pointer",
  fontSize: "13px",
  fontWeight: 600,
} as const;

const secondaryLinkStyle = {
  padding: "7px 12px",
  borderRadius: "8px",
  border: "1px solid var(--app-secondary-action-border)",
  background: "var(--app-secondary-action-bg)",
  color: "var(--app-secondary-action-fg)",
  textDecoration: "none",
  fontSize: "13px",
  fontWeight: 600,
} as const;

const secondaryButtonStyle = {
  padding: "7px 12px",
  borderRadius: "8px",
  border: "1px solid var(--app-secondary-action-border)",
  background: "var(--app-secondary-action-bg)",
  color: "var(--app-secondary-action-fg)",
  cursor: "pointer",
  fontSize: "13px",
  fontWeight: 600,
} as const;

const dangerButtonStyle = {
  padding: "7px 12px",
  borderRadius: "8px",
  border: "1px solid var(--app-danger-border)",
  background: "var(--app-danger-bg)",
  color: "var(--app-danger-fg)",
  cursor: "pointer",
  fontSize: "13px",
  fontWeight: 600,
} as const;

const watchButtonStyle = {
  ...secondaryButtonStyle,
  border: "1px solid var(--app-secondary-action-border)",
  background: "var(--app-secondary-action-bg)",
  color: "var(--app-secondary-action-fg)",
  cursor: "pointer",
} as const;

const actionButtonStyle = {
  ...secondaryButtonStyle,
  border: "1px solid var(--app-secondary-action-border)",
  background: "var(--app-secondary-action-bg)",
  color: "var(--app-secondary-action-fg)",
  cursor: "pointer",
} as const;

const disabledButtonStyle = {
  ...secondaryButtonStyle,
  border: "1px solid var(--app-surface-border)",
  background: "var(--app-surface-muted-bg)",
  color: "var(--app-text-subtle)",
  cursor: "not-allowed",
} as const;
