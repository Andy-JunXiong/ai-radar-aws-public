"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import AppContainer from "@/components/AppContainer";
import VerificationGateNote from "@/components/VerificationGateNote";
import VerifiedInsightObjectPanel, { type VerifiedInsightObjectRow } from "@/components/VerifiedInsightObjectPanel";
import { apiUrl } from "@/lib/api";
import { adminFetchWithTimeout, isAbortError } from "@/lib/requestTimeout";

type ProjectTrajectoryApiEvent = {
  id?: string;
  event_kind?: "review" | "calibration";
  timestamp?: string;
  project_id?: string;
  project_name?: string;
  signal_id?: string;
  signal_title?: string;
  outcome?: string;
  reason?: string;
  followup_result?: string;
  review_note?: string;
  evidence_update?: string;
  next_review_date?: string;
  expected_outcome?: string;
  source_type?: string;
  manual_session_id?: string;
  is_manual_source?: boolean;
  upload_reason?: string;
  intended_use?: string;
  cognitive_layer?: string;
  verification_status?: string;
  unsupported_claim_count?: number;
  inferred_claim_count?: number;
  blocked_downstream_actions?: string[];
  confidence_label?: string;
  confidence_score?: number | null;
  risk_level?: string;
  trajectory_signal_type?: string;
};

type TrajectoryEventsResponse = {
  items?: ProjectTrajectoryApiEvent[];
  summary?: {
    total_events?: number;
    manual_count?: number;
    risk_count?: number;
    latest_timestamp?: string;
    risk_mix?: Record<string, number>;
    signal_type_mix?: Record<string, number>;
    event_kind_mix?: Record<string, number>;
    source_type_mix?: Record<string, number>;
    manual_intent_summary?: ManualIntentSummary;
    project_mix?: Array<{
      project_id?: string;
      project_name?: string;
      event_count?: number;
      manual_count?: number;
      risk_count?: number;
      watch_count?: number;
      action_count?: number;
      latest_timestamp?: string;
    }>;
  };
  detail?: string;
};

type CountItem = {
  value?: string;
  count?: number;
};

type ManualIntentSummary = {
  upload_reason_mix?: CountItem[];
  intended_use_mix?: CountItem[];
  cognitive_layer_mix?: CountItem[];
};

type TimelineEvent = {
  id: string;
  kind: "review" | "calibration";
  timestamp: string;
  title: string;
  projectKey: string;
  projectLabel: string;
  signalId: string;
  outcome: string;
  sourceLabel: string;
  isManual: boolean;
  verificationStatus: string;
  confidence: string;
  unsupportedCount: number;
  inferredCount: number;
  blockedCount: number;
  blockedDownstreamActions: string[];
  riskLevel: string;
  trajectorySignalType: string;
  reason?: string;
  followupResult?: string;
  reviewNote?: string;
  evidenceUpdate?: string;
  nextReviewDate?: string;
  expectedOutcome?: string;
  uploadReason?: string;
  intendedUse?: string;
  cognitiveLayer?: string;
  auditEventCount: number;
  auditEventLabels: string[];
};

type TimelineFilter = "all" | "manual" | "risk" | "watch" | "action" | "review" | "calibration";
type TimeWindowFilter = "all" | "7d" | "30d" | "90d";
type TimelineStage = "review" | "watch" | "action" | "completed" | "rejected" | "calibration";

type ProjectSummary = {
  projectKey: string;
  projectLabel: string;
  totalCount: number;
  manualCount: number;
  riskCount: number;
  watchCount: number;
  actionCount: number;
  latestTimestamp: string;
};

function formatLabel(value?: string) {
  return (value || "")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase())
    .trim();
}

function formatConfidence(label?: string, score?: number | null) {
  const cleanLabel = label ? formatLabel(label) : "";
  if (typeof score === "number" && !Number.isNaN(score)) {
    return cleanLabel ? `${cleanLabel} (${score.toFixed(2)})` : score.toFixed(2);
  }
  return cleanLabel || "n/a";
}

function formatDateTime(value?: string) {
  if (!value) return "n/a";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString();
}

function formatSourceLabel(isManual: boolean, sourceType?: string, manualSessionId?: string) {
  if (isManual || sourceType === "manual_upload") {
    return manualSessionId ? `Manual Upload (${manualSessionId})` : "Manual Upload";
  }
  return sourceType ? formatLabel(sourceType) : "Collected Signal";
}

function trajectoryToneFromOutcome(outcome?: string): VerifiedInsightObjectRow["tone"] {
  const normalized = (outcome || "").toLowerCase();
  if (["confirmed", "action", "action_completed"].includes(normalized)) return "good";
  if (normalized === "watch") return "watch";
  if (["rejected", "dismissed"].includes(normalized)) return "bad";
  return "neutral";
}

function trajectoryToneFromVerification(status?: string, blockedActions: string[] = []): VerifiedInsightObjectRow["tone"] {
  const normalized = (status || "").toLowerCase();
  if (blockedActions.includes("low_risk_action_candidate") || ["unsupported", "contradicted", "not_verifiable"].includes(normalized)) {
    return "bad";
  }
  if (["partially_verified", "weakly_supported", "needs_review"].includes(normalized)) return "watch";
  if (["verified", "verified_with_limitations", "supported"].includes(normalized)) return "good";
  return "neutral";
}

function buildTrajectoryVerifiedInsightObjectRows(event: TimelineEvent): VerifiedInsightObjectRow[] {
  const actionBlocked = event.blockedDownstreamActions.includes("low_risk_action_candidate");
  const claimCount = event.unsupportedCount + event.inferredCount;
  return [
    {
      label: "Outcome",
      value: formatLabel(event.outcome) || "Not recorded",
      detail: "Recorded trajectory outcome from the review or calibration event.",
      tone: trajectoryToneFromOutcome(event.outcome),
    },
    {
      label: "Verification",
      value: formatLabel(event.verificationStatus) || "Unknown",
      detail: "Verification state captured with the timeline event.",
      tone: trajectoryToneFromVerification(event.verificationStatus, event.blockedDownstreamActions),
    },
    {
      label: "Confidence",
      value: event.confidence || "n/a",
      detail: "Confidence is preserved as event context only.",
      tone: event.confidence.toLowerCase().includes("low") ? "watch" : "neutral",
    },
    {
      label: "Claims",
      value: claimCount > 0 ? `${claimCount} risk flag(s)` : "No visible risk",
      detail: `Unsupported ${event.unsupportedCount}, inferred ${event.inferredCount}.`,
      tone: event.unsupportedCount > 0 ? "bad" : event.inferredCount > 0 ? "watch" : "neutral",
    },
    {
      label: "Low-risk Action",
      value: actionBlocked ? "Blocked" : "Not blocked",
      detail: actionBlocked
        ? "low_risk_action_candidate is recorded in blocked_downstream_actions."
        : "No low-risk Action block is visible on this event.",
      tone: actionBlocked ? "bad" : "neutral",
    },
  ];
}

function toTimelineEvent(event: ProjectTrajectoryApiEvent): TimelineEvent {
  const isManual = Boolean(event.is_manual_source) || event.source_type === "manual_upload";
  const eventKind = event.event_kind === "calibration" ? "calibration" : "review";
  return {
    id: event.id || `${eventKind}:${event.project_id || "project"}:${event.signal_id || "signal"}:${event.outcome || "event"}`,
    kind: eventKind,
    timestamp: event.timestamp || "",
    title: event.signal_title || event.signal_id || (eventKind === "calibration" ? "Untitled calibration event" : "Untitled review record"),
    projectKey: event.project_id || "unknown",
    projectLabel: event.project_name || event.project_id || "Unknown project",
    signalId: event.signal_id || "",
    outcome: event.outcome || (eventKind === "calibration" ? "calibration_event" : "review_recorded"),
    sourceLabel: formatSourceLabel(isManual, event.source_type, event.manual_session_id),
    isManual,
    verificationStatus: event.verification_status || "unknown",
    confidence: formatConfidence(event.confidence_label, event.confidence_score),
    unsupportedCount: event.unsupported_claim_count || 0,
    inferredCount: event.inferred_claim_count || 0,
    blockedCount: Array.isArray(event.blocked_downstream_actions) ? event.blocked_downstream_actions.length : 0,
    blockedDownstreamActions: Array.isArray(event.blocked_downstream_actions) ? event.blocked_downstream_actions : [],
    riskLevel: event.risk_level || "low",
    trajectorySignalType: event.trajectory_signal_type || (eventKind === "calibration" ? "calibration_learning" : "review_decision"),
    reason: event.reason,
    followupResult: event.followup_result || "",
    reviewNote: event.review_note || "",
    evidenceUpdate: event.evidence_update || "",
    nextReviewDate: event.next_review_date || "",
    expectedOutcome: event.expected_outcome || "",
    uploadReason: event.upload_reason || "",
    intendedUse: event.intended_use || "",
    cognitiveLayer: event.cognitive_layer || "unclassified",
    auditEventCount: 0,
    auditEventLabels: [],
  };
}

function auditFoldKey(event: TimelineEvent) {
  return [event.projectKey, event.signalId, event.timestamp].join("::");
}

function isFoldableAuditCalibration(event: TimelineEvent) {
  const outcome = event.outcome.toLowerCase();
  return event.kind === "calibration" && (outcome === "takeaway_accepted" || outcome === "review_record_created");
}

function foldAuditCalibrationEvents(events: TimelineEvent[]) {
  const reviewByKey = new Map<string, TimelineEvent>();
  const foldedReviews = events.map((event) => {
    if (event.kind !== "review") return event;
    const cloned = { ...event, auditEventCount: 0, auditEventLabels: [] as string[] };
    reviewByKey.set(auditFoldKey(cloned), cloned);
    return cloned;
  });

  return foldedReviews.filter((event) => {
    if (!isFoldableAuditCalibration(event)) return true;

    const review = reviewByKey.get(auditFoldKey(event));
    if (!review) return true;

    review.auditEventCount += 1;
    review.auditEventLabels = [...review.auditEventLabels, event.outcome];
    return false;
  });
}

function hasRisk(event: TimelineEvent) {
  return event.riskLevel !== "low";
}

function isWatchEvent(event: TimelineEvent) {
  return event.outcome.toLowerCase().includes("watch");
}

function isActionEvent(event: TimelineEvent) {
  const outcome = event.outcome.toLowerCase();
  return outcome.includes("action") || outcome === "confirmed";
}

function getTrajectoryStage(event: TimelineEvent): TimelineStage {
  const outcome = event.outcome.toLowerCase();
  if (event.kind === "calibration") return "calibration";
  if (outcome === "action_completed") return "completed";
  if (outcome === "confirmed" && hasRisk(event)) return "review";
  if (outcome.includes("action") || outcome === "confirmed") return "action";
  if (outcome.includes("watch")) return "watch";
  if (outcome === "rejected" || outcome === "dismissed") return "rejected";
  return "review";
}

function buildStageSummary(events: TimelineEvent[]) {
  return events.reduce<Record<TimelineStage, number>>(
    (summary, event) => {
      const stage = getTrajectoryStage(event);
      summary[stage] += 1;
      return summary;
    },
    {
      review: 0,
      watch: 0,
      action: 0,
      completed: 0,
      rejected: 0,
      calibration: 0,
    }
  );
}

function buildTrajectoryConversionInsight(events: TimelineEvent[]) {
  if (!events.length) return "No reviewed judgment flow is visible in this scope yet.";
  const stageSummary = buildStageSummary(events);
  const commitmentCount = stageSummary.action + stageSummary.completed;
  const learningCount = stageSummary.calibration + stageSummary.completed;
  const watchPressure = stageSummary.watch;
  if (commitmentCount > 0) {
    return `${commitmentCount} event(s) have become confirmed/action commitments; ${learningCount} event(s) already feed completion or calibration learning.`;
  }
  if (watchPressure > 0) {
    return `${watchPressure} event(s) are still in Watch, so this trajectory is accumulating evidence before stronger commitment.`;
  }
  if (stageSummary.rejected > 0) {
    return `${stageSummary.rejected} event(s) were rejected or dismissed, which is useful calibration against noisy project-fit signals.`;
  }
  return "This scope is mostly pending review memory; use Review Inbox outcomes to create clearer trajectory movement.";
}

function buildStageFlowDecision(stageSummary: Record<TimelineStage, number>) {
  if (stageSummary.action + stageSummary.completed > 0) {
    return "Follow action and completion outcomes first; they are the strongest trajectory commitments.";
  }
  if (stageSummary.watch > 0) {
    return "Watch is the active pressure. Revisit review dates and promote only after evidence or project fit improves.";
  }
  if (stageSummary.review > 0) {
    return "Review memory exists, but it has not yet become Watch, Action, Rejection, or Calibration movement.";
  }
  if (stageSummary.rejected > 0) {
    return "Rejected/dismissed outcomes are useful calibration; compare them against noisy project-fit sources.";
  }
  if (stageSummary.calibration > 0) {
    return "Calibration is visible without active commitments in this scope.";
  }
  return "No stage pressure is visible in this scope.";
}

function buildStageExplanation(event: TimelineEvent) {
  const stage = getTrajectoryStage(event);
  if (stage === "calibration") {
    return "Calibration stage because this event records system learning about a prior review outcome, not a new candidate decision.";
  }
  if (stage === "completed") {
    return "Completed stage because the action lifecycle has a completion outcome, so this event contributes execution learning back into the trajectory.";
  }
  if (stage === "action") {
    return "Action stage because the review outcome created a confirmed or action-oriented commitment; use the gate note to confirm whether that path was ordinary or override-based.";
  }
  if (event.outcome.toLowerCase() === "confirmed" && hasRisk(event)) {
    return "Review stage because this confirmed manual judgment still carries verification-risk gates; treat it as review memory until the blocked actions are resolved or explicitly justified.";
  }
  if (stage === "watch") {
    return "Watch stage because the reviewer kept the item visible while waiting for stronger evidence, timing, or project-fit confirmation.";
  }
  if (stage === "rejected") {
    return "Rejected stage because the reviewer dismissed or rejected this candidate, which helps calibrate noisy or weak project-fit signals.";
  }
  return "Review stage because this event is still best read as judgment memory rather than watch, action, completion, rejection, or calibration.";
}

function buildEventImportance(event: TimelineEvent) {
  if (isActionEvent(event) && hasRisk(event)) {
    return "This confirmed review carries verification risk, so it should inform project memory without becoming ordinary Action evidence yet.";
  }
  if (isActionEvent(event)) {
    return "This event represents an action commitment or confirmed project takeaway, so it is part of the system's execution memory.";
  }
  if (isWatchEvent(event)) {
    return "This event keeps the signal under observation before it becomes a stronger project commitment.";
  }
  if (hasRisk(event)) {
    return "This event carries verification risk, so it should be reviewed before it influences project direction.";
  }
  if (event.kind === "calibration") {
    return "This event records learning from prior review behavior and helps calibrate future judgment quality.";
  }
  return "This event records a reviewed judgment that can contribute to the project's lightweight trajectory seed.";
}

function buildSourceContext(event: TimelineEvent) {
  if (event.isManual) {
    const contextParts = [
      event.uploadReason ? `Reason: ${event.uploadReason}` : "",
      event.intendedUse ? `Use: ${event.intendedUse}` : "",
      event.cognitiveLayer ? `Layer: ${formatLabel(event.cognitiveLayer)}` : "",
    ].filter(Boolean);
    return contextParts.length > 0
      ? contextParts.join(" / ")
      : "Manual-upload-derived event with no additional intent metadata.";
  }
  return `Collected signal / Verification: ${formatLabel(event.verificationStatus)} / Confidence: ${event.confidence}`;
}

function buildManualTrajectoryContribution(events: TimelineEvent[]) {
  const manualEvents = events.filter((event) => event.isManual);
  const manualWatch = manualEvents.filter(isWatchEvent).length;
  const manualAction = manualEvents.filter(isActionEvent).length;
  const manualRisk = manualEvents.filter(hasRisk).length;
  const manualCalibration = manualEvents.filter((event) => event.kind === "calibration").length;

  if (manualEvents.length === 0) {
    return {
      hasManualContribution: false,
      achieved: "No manual-source trajectory events are visible in this scope.",
      gap: "Trajectory movement is currently based on ordinary collected signals only.",
      next: "Complete a manual-upload review when user-selected material should influence the judgment timeline.",
      manualEvents: 0,
      manualWatch,
      manualAction,
      manualRisk,
      manualCalibration,
    };
  }

  const achieved = `${manualEvents.length} manual-source event(s) are shaping this trajectory view, including ${manualCalibration} calibration event(s).`;
  const gap =
    manualRisk > 0
      ? `${manualRisk} manual-source event(s) still carry verification risk and should remain visible during follow-up.`
      : "Manual-source events have no visible verification-risk pressure in this scope.";
  const next =
    manualAction > 0
      ? "Compare manual Action outcomes against collected-signal Action outcomes before reusing them as project patterns."
      : manualWatch > 0
        ? "Watch manual-source outcomes until evidence quality supports a stronger action route."
        : "Use the next review decision to decide whether manual-source learning should become Watch, Action, or calibration-only memory.";

  return {
    hasManualContribution: true,
    achieved,
    gap,
    next,
    manualEvents: manualEvents.length,
    manualWatch,
    manualAction,
    manualRisk,
    manualCalibration,
  };
}

function buildManualEventContribution(event: TimelineEvent) {
  if (event.kind === "calibration") {
    return "This manual-source event is calibration memory: it helps compare user-selected material against future review behavior.";
  }
  if (isActionEvent(event) && hasRisk(event)) {
    return "This manual-source review was confirmed with verification risk still visible, so it should remain review memory unless an explicit override rationale makes it reusable.";
  }
  if (isActionEvent(event)) {
    return "This manual-source review created action pressure, so it should be compared with collected-signal actions before becoming a reusable pattern.";
  }
  if (isWatchEvent(event)) {
    return "This manual-source review is being held in Watch, which keeps user-selected material visible without bypassing evidence gates.";
  }
  if (hasRisk(event)) {
    return "This manual-source review carries verification risk, so it should inform judgment without becoming automatic action.";
  }
  return "This manual-source review adds human-selected context to the trajectory seed while staying inside the ordinary review path.";
}

function timeWindowDays(value: TimeWindowFilter) {
  if (value === "7d") return 7;
  if (value === "30d") return 30;
  if (value === "90d") return 90;
  return null;
}

function filterByTimeWindow(events: TimelineEvent[], window: TimeWindowFilter) {
  const days = timeWindowDays(window);
  if (!days) return events;
  const cutoff = Date.now() - days * 24 * 60 * 60 * 1000;
  return events.filter((event) => {
    const timestamp = new Date(event.timestamp).getTime();
    return !Number.isNaN(timestamp) && timestamp >= cutoff;
  });
}

function buildOpsSummary(events: TimelineEvent[]) {
  if (events.length === 0) {
    return {
      achieved: "No trajectory seed events exist yet.",
      gap: "AI Radar cannot show judgment movement until review or calibration events are created.",
      next: "Review Project Takeaway candidates to start producing trajectory seed data.",
    };
  }

  const manualCount = events.filter((event) => event.isManual).length;
  const riskCount = events.filter(hasRisk).length;
  const latest = events[0];
  return {
    achieved: `${events.length} judgment event(s) are available, including ${manualCount} manual-upload-derived event(s). Latest event: ${formatLabel(latest.outcome)}.`,
    gap: riskCount > 0
      ? `${riskCount} event(s) carry verification risk through unsupported claims, inferred claims, blocked actions, or low confidence.`
      : "No visible verification-risk pressure appears in the current trajectory seed.",
    next: manualCount > 0
      ? "Compare manual-upload outcomes against collected-signal outcomes before turning this into heavier memory modeling."
      : "Add manual-upload review outcomes when user-selected material needs to become part of the judgment history.",
  };
}

function buildTrajectoryTrendLine(events: TimelineEvent[]) {
  if (events.length === 0) return "No events in this scope yet.";
  const manual = events.filter((event) => event.isManual).length;
  const risk = events.filter(hasRisk).length;
  const watch = events.filter(isWatchEvent).length;
  const action = events.filter(isActionEvent).length;
  const dominant = [
    { label: "manual source", count: manual },
    { label: "verification risk", count: risk },
    { label: "watch follow-up", count: watch },
    { label: "action pressure", count: action },
  ].sort((left, right) => right.count - left.count)[0];
  return `Current trajectory pressure: ${dominant.count} ${dominant.label} event(s) out of ${events.length}. Manual ${manual}, risk ${risk}, watch ${watch}, action ${action}.`;
}

function buildProjectSummaries(events: TimelineEvent[]): ProjectSummary[] {
  const summaries = new Map<string, ProjectSummary>();
  for (const event of events) {
    const existing = summaries.get(event.projectKey) || {
      projectKey: event.projectKey,
      projectLabel: event.projectLabel,
      totalCount: 0,
      manualCount: 0,
      riskCount: 0,
      watchCount: 0,
      actionCount: 0,
      latestTimestamp: event.timestamp,
    };
    existing.totalCount += 1;
    if (event.isManual) existing.manualCount += 1;
    if (hasRisk(event)) existing.riskCount += 1;
    if (event.outcome.toLowerCase().includes("watch")) existing.watchCount += 1;
    if (event.outcome.toLowerCase().includes("action") || event.outcome.toLowerCase() === "confirmed") {
      existing.actionCount += 1;
    }
    if (new Date(event.timestamp).getTime() > new Date(existing.latestTimestamp).getTime()) {
      existing.latestTimestamp = event.timestamp;
      existing.projectLabel = event.projectLabel;
    }
    summaries.set(event.projectKey, existing);
  }
  return Array.from(summaries.values()).sort((left, right) => {
    if (right.totalCount !== left.totalCount) return right.totalCount - left.totalCount;
    return new Date(right.latestTimestamp).getTime() - new Date(left.latestTimestamp).getTime();
  });
}

function countBy(events: TimelineEvent[], getKey: (event: TimelineEvent) => string) {
  return events.reduce<Record<string, number>>((counts, event) => {
    const key = getKey(event) || "unknown";
    counts[key] = (counts[key] || 0) + 1;
    return counts;
  }, {});
}

function topCountItems(counts: Record<string, number>, limit = 5): CountItem[] {
  return Object.entries(counts)
    .sort((left, right) => {
      if (right[1] !== left[1]) return right[1] - left[1];
      return right[0].localeCompare(left[0]);
    })
    .slice(0, limit)
    .map(([value, count]) => ({ value, count }));
}

function buildManualIntentSummary(events: TimelineEvent[]): ManualIntentSummary {
  const manualEvents = events.filter((event) => event.isManual);
  return {
    upload_reason_mix: topCountItems(countBy(manualEvents, (event) => event.uploadReason || "unknown")),
    intended_use_mix: topCountItems(countBy(manualEvents, (event) => event.intendedUse || "unknown")),
    cognitive_layer_mix: topCountItems(countBy(manualEvents, (event) => event.cognitiveLayer || "unclassified")),
  };
}

function formatIntentMix(items?: CountItem[]) {
  const visible = (items || []).filter((item) => item.value);
  if (!visible.length) return "No manual intent metadata in this scope.";
  return visible
    .map((item) => `${formatLabel(item.value)} ${item.count || 0}`)
    .join(" / ");
}

function SummaryMetric({ label, value }: { label: string; value: string | number }) {
  return (
    <div style={summaryItemStyle}>
      <span style={metricLabelStyle}>{label}</span>
      <strong style={summaryValueStyle}>{value}</strong>
    </div>
  );
}

function EmptyStateCard({
  title,
  description,
  primaryHref,
  primaryLabel,
  secondaryHref,
  secondaryLabel,
}: {
  title: string;
  description: string;
  primaryHref?: string;
  primaryLabel?: string;
  secondaryHref?: string;
  secondaryLabel?: string;
}) {
  return (
    <div style={emptyCardStyle}>
      <strong style={emptyTitleStyle}>{title}</strong>
      <p style={emptyDescriptionStyle}>{description}</p>
      {primaryHref || secondaryHref ? (
        <div style={linkRowStyle}>
          {primaryHref && primaryLabel ? (
            <Link href={primaryHref} style={primaryToolbarLinkStyle}>
              {primaryLabel}
            </Link>
          ) : null}
          {secondaryHref && secondaryLabel ? (
            <Link href={secondaryHref} style={secondaryLinkStyle}>
              {secondaryLabel}
            </Link>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

export default function ProjectTrajectoryPage() {
  const searchParams = useSearchParams();
  const initialProjectId = (searchParams.get("project_id") || "").trim();
  const initialSignalId = (searchParams.get("signal_id") || "").trim();
  const [trajectoryApiEvents, setTrajectoryApiEvents] = useState<ProjectTrajectoryApiEvent[]>([]);
  const [timeWindowFilter, setTimeWindowFilter] = useState<TimeWindowFilter>("all");
  const [timelineFilter, setTimelineFilter] = useState<TimelineFilter>("all");
  const [projectFilter, setProjectFilter] = useState(initialProjectId || "all");
  const [signalFilter, setSignalFilter] = useState(initialSignalId);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState("");
  const [loadStatus, setLoadStatus] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function loadTimeline() {
      setLoading(true);
      setErrorMessage("");
      setLoadStatus("Requesting /projects/trajectory-events from the local API...");
      try {
        const response = await adminFetchWithTimeout(apiUrl("/projects/trajectory-events"), {
          cache: "no-store",
        });
        const data = (await response.json().catch(() => null)) as TrajectoryEventsResponse | null;

        if (!response.ok) {
          if (response.status === 401 || response.status === 403) {
            throw new Error("Admin access is required. Please open the admin login, then return to this page.");
          }
          throw new Error(data?.detail || `Failed to load trajectory events (${response.status}). Confirm the backend is running with the latest route code.`);
        }

        if (!cancelled) {
          setTrajectoryApiEvents(Array.isArray(data?.items) ? data.items : []);
        }
      } catch (error) {
        if (!cancelled) {
          setTrajectoryApiEvents([]);
          const message = isAbortError(error)
            ? "Trajectory request timed out after 8 seconds. Confirm the backend is running and restart it if this route was just added."
            : error instanceof Error
              ? error.message
              : "Failed to load trajectory timeline.";
          setErrorMessage(message);
        }
      } finally {
        if (!cancelled) setLoadStatus("");
        if (!cancelled) setLoading(false);
      }
    }

    void loadTimeline();
    return () => {
      cancelled = true;
    };
  }, []);

  const timelineEvents = useMemo(() => {
    return trajectoryApiEvents
      .map(toTimelineEvent)
      .filter((event) => event.timestamp)
      .sort((left, right) => new Date(right.timestamp).getTime() - new Date(left.timestamp).getTime());
  }, [trajectoryApiEvents]);

  const foldedTimelineEvents = useMemo(() => foldAuditCalibrationEvents(timelineEvents), [timelineEvents]);
  const timeFilteredEvents = useMemo(() => filterByTimeWindow(timelineEvents, timeWindowFilter), [timelineEvents, timeWindowFilter]);
  const foldedTimeFilteredEvents = useMemo(() => foldAuditCalibrationEvents(timeFilteredEvents), [timeFilteredEvents]);
  const projectSummaries = useMemo(() => buildProjectSummaries(foldedTimeFilteredEvents), [foldedTimeFilteredEvents]);
  const projectFilteredEvents = useMemo(() => {
    return timeFilteredEvents.filter((event) => {
      if (projectFilter !== "all" && event.projectKey !== projectFilter) return false;
      if (signalFilter && event.signalId !== signalFilter) return false;
      return true;
    });
  }, [timeFilteredEvents, projectFilter, signalFilter]);
  const foldedProjectFilteredEvents = useMemo(() => foldAuditCalibrationEvents(projectFilteredEvents), [projectFilteredEvents]);
  const projectScopedSummary = useMemo(() => buildOpsSummary(foldedProjectFilteredEvents), [foldedProjectFilteredEvents]);
  const opsSummary = useMemo(() => buildOpsSummary(foldedTimelineEvents), [foldedTimelineEvents]);
  const activeOpsSummary = projectFilter === "all" ? opsSummary : projectScopedSummary;
  const manualCount = foldedProjectFilteredEvents.filter((event) => event.isManual).length;
  const riskCount = foldedProjectFilteredEvents.filter(hasRisk).length;
  const watchCount = foldedProjectFilteredEvents.filter(isWatchEvent).length;
  const actionCount = foldedProjectFilteredEvents.filter(isActionEvent).length;
  const displayRiskMix = countBy(foldedProjectFilteredEvents, (event) => event.riskLevel);
  const displaySignalTypeMix = countBy(foldedProjectFilteredEvents, (event) => event.trajectorySignalType);
  const manualIntentSummary = buildManualIntentSummary(foldedProjectFilteredEvents);
  const visibleEvents = useMemo(() => {
    if (timelineFilter === "calibration") return projectFilteredEvents.filter((event) => event.kind === "calibration");
    if (timelineFilter === "manual") return foldedProjectFilteredEvents.filter((event) => event.isManual);
    if (timelineFilter === "risk") return foldedProjectFilteredEvents.filter(hasRisk);
    if (timelineFilter === "watch") return foldedProjectFilteredEvents.filter(isWatchEvent);
    if (timelineFilter === "action") return foldedProjectFilteredEvents.filter(isActionEvent);
    if (timelineFilter === "review") return foldedProjectFilteredEvents.filter((event) => event.kind === "review");
    return foldedProjectFilteredEvents;
  }, [foldedProjectFilteredEvents, projectFilteredEvents, timelineFilter]);
  const filterOptions: Array<{ value: TimelineFilter; label: string; count: number }> = [
    { value: "all", label: "All", count: foldedProjectFilteredEvents.length },
    { value: "manual", label: "Manual", count: manualCount },
    { value: "risk", label: "Risk", count: riskCount },
    { value: "watch", label: "Watch", count: watchCount },
    { value: "action", label: "Action", count: actionCount },
    { value: "review", label: "Review", count: foldedProjectFilteredEvents.filter((event) => event.kind === "review").length },
    { value: "calibration", label: "Calibration", count: projectFilteredEvents.filter((event) => event.kind === "calibration").length },
  ];
  const timeWindowOptions: Array<{ value: TimeWindowFilter; label: string; count: number }> = [
    { value: "all", label: "All Time", count: foldedTimelineEvents.length },
    { value: "7d", label: "7d", count: foldAuditCalibrationEvents(filterByTimeWindow(timelineEvents, "7d")).length },
    { value: "30d", label: "30d", count: foldAuditCalibrationEvents(filterByTimeWindow(timelineEvents, "30d")).length },
    { value: "90d", label: "90d", count: foldAuditCalibrationEvents(filterByTimeWindow(timelineEvents, "90d")).length },
  ];
  const activeProjectLabel = projectFilter === "all"
    ? "All projects"
    : projectSummaries.find((project) => project.projectKey === projectFilter)?.projectLabel || projectFilter;
  const activeSignalLabel = signalFilter || "All signals";
  const activeWindowLabel = timeWindowOptions.find((option) => option.value === timeWindowFilter)?.label || "All Time";
  const activeEventLabel = filterOptions.find((option) => option.value === timelineFilter)?.label || "All";
  const trajectoryTrendLine = buildTrajectoryTrendLine(foldedProjectFilteredEvents);
  const manualTrajectoryContribution = buildManualTrajectoryContribution(foldedProjectFilteredEvents);
  const stageSummary = useMemo(() => buildStageSummary(foldedProjectFilteredEvents), [foldedProjectFilteredEvents]);
  const conversionInsight = useMemo(() => buildTrajectoryConversionInsight(foldedProjectFilteredEvents), [foldedProjectFilteredEvents]);
  const stageFlowDecision = useMemo(() => buildStageFlowDecision(stageSummary), [stageSummary]);

  return (
    <AppContainer style={{ paddingTop: "24px" }}>
      <div style={compactHeaderStyle}>
        <div style={{ minWidth: 0 }}>
          <div style={summaryLabelStyle}>Workspace Review</div>
          <h1 style={compactTitleStyle}>Trajectory Timeline</h1>
          <p style={compactDescriptionStyle}>
            Read-only judgment-event timeline built from Review Records and Calibration Events.
          </p>
        </div>
        <div style={compactHeaderActionsStyle}>
          <Link href="/workspace/projects" style={primaryToolbarLinkStyle}>
            Back to Project Takeaways
          </Link>
          <Link href="/workspace/projects/review" style={toolbarLinkStyle}>
            Review Inbox
          </Link>
        </div>
      </div>

      {loadStatus ? <div style={infoCardStyle}>{loadStatus}</div> : null}
      {errorMessage ? (
        <div style={errorCardStyle}>
          <strong style={emptyTitleStyle}>Trajectory events could not load.</strong>
          <p style={emptyDescriptionStyle}>{errorMessage}</p>
          <div style={linkRowStyle}>
            <Link href="/admin" style={primaryToolbarLinkStyle}>
              Open Admin
            </Link>
            <Link href="/workspace/projects/review" style={secondaryLinkStyle}>
              Review Inbox
            </Link>
          </div>
        </div>
      ) : null}

      {loading ? (
        <EmptyStateCard
          title="Loading trajectory events"
          description="Requesting /projects/trajectory-events from the local API."
        />
      ) : (
        <div style={pageGridStyle}>
            <section style={summaryBandStyle}>
              <div style={sectionTitleStyle}>Timeline Summary</div>
              <div style={summaryMetricRowStyle}>
                <SummaryMetric label="Events" value={projectFilteredEvents.length} />
                <SummaryMetric label="Manual Source" value={manualCount} />
                <SummaryMetric label="Watch" value={watchCount} />
                <SummaryMetric label="Action" value={actionCount} />
                <SummaryMetric label="Risk Signals" value={riskCount} />
              </div>
              <div style={opsInterpretationStyle}>
                <div style={opsInterpretationItemStyle}>
                  <span style={summaryLabelStyle}>Achieved</span>
                  <strong>{activeOpsSummary.achieved}</strong>
                </div>
                <div style={opsInterpretationItemStyle}>
                  <span style={summaryLabelStyle}>Gaps</span>
                  <strong>{activeOpsSummary.gap}</strong>
                </div>
                <div style={opsInterpretationItemStyle}>
                  <span style={summaryLabelStyle}>Next Focus</span>
                  <strong>{activeOpsSummary.next}</strong>
                </div>
              </div>
              {manualTrajectoryContribution.hasManualContribution ? (
                <div style={manualContributionPanelStyle}>
                  <div style={manualContributionHeaderStyle}>
                    <div>
                      <span style={summaryLabelStyle}>Manual Source Contribution</span>
                      <strong style={manualContributionTitleStyle}>
                        User-selected material is contributing to trajectory movement.
                      </strong>
                    </div>
                    <div style={manualContributionMetricRowStyle}>
                      <span>Events {manualTrajectoryContribution.manualEvents}</span>
                      <span>Calibration {manualTrajectoryContribution.manualCalibration}</span>
                      <span>Watch {manualTrajectoryContribution.manualWatch}</span>
                      <span>Action {manualTrajectoryContribution.manualAction}</span>
                      <span>Risk {manualTrajectoryContribution.manualRisk}</span>
                    </div>
                  </div>
                  <div style={manualContributionGridStyle}>
                    <div style={manualContributionCardStyle}>
                      <span style={summaryLabelStyle}>Achieved</span>
                      <strong>{manualTrajectoryContribution.achieved}</strong>
                    </div>
                    <div style={manualContributionCardStyle}>
                      <span style={summaryLabelStyle}>Gap</span>
                      <strong>{manualTrajectoryContribution.gap}</strong>
                    </div>
                    <div style={manualContributionCardStyle}>
                      <span style={summaryLabelStyle}>Next Focus</span>
                      <strong>{manualTrajectoryContribution.next}</strong>
                    </div>
                  </div>
                  <div style={manualContributionGridStyle}>
                    <div style={manualContributionCardStyle}>
                      <span style={summaryLabelStyle}>Upload Reason Mix</span>
                      <strong>{formatIntentMix(manualIntentSummary.upload_reason_mix)}</strong>
                    </div>
                    <div style={manualContributionCardStyle}>
                      <span style={summaryLabelStyle}>Intended Use Mix</span>
                      <strong>{formatIntentMix(manualIntentSummary.intended_use_mix)}</strong>
                    </div>
                    <div style={manualContributionCardStyle}>
                      <span style={summaryLabelStyle}>Cognitive Layer Mix</span>
                      <strong>{formatIntentMix(manualIntentSummary.cognitive_layer_mix)}</strong>
                    </div>
                  </div>
                </div>
              ) : null}
              <div style={stageFlowStyle}>
                {[
                  { key: "review" as const, label: "Review" },
                  { key: "watch" as const, label: "Watch" },
                  { key: "action" as const, label: "Action" },
                  { key: "completed" as const, label: "Completed" },
                  { key: "rejected" as const, label: "Rejected" },
                  { key: "calibration" as const, label: "Calibration" },
                ].map((stage) => (
                  <div key={stage.key} style={stageFlowItemStyle}>
                    <span style={summaryLabelStyle}>{stage.label}</span>
                    <strong>{stageSummary[stage.key]}</strong>
                  </div>
                ))}
                <div style={stageFlowInsightStyle}>
                  <span style={summaryLabelStyle}>Trajectory Movement</span>
                  <strong>{conversionInsight}</strong>
                </div>
                <div style={stageFlowInsightStyle}>
                  <span style={summaryLabelStyle}>Next Stage Focus</span>
                  <strong>{stageFlowDecision}</strong>
                </div>
              </div>
              <div style={trendLineStyle}>{trajectoryTrendLine}</div>
              <div style={trajectoryBoundaryStyle}>
                <span style={summaryLabelStyle}>Trajectory Boundary</span>
                <strong>
                  This page is a lightweight trajectory seed over reviewed judgments. Raw signals and deep reflections
                  should only influence it after explicit review, watch, action, calibration, or user-marked judgment.
                </strong>
              </div>
            </section>

            <section style={filterPanelStyle}>
              <div>
                <div style={sectionTitleStyle}>Filters</div>
                <p style={sectionDescriptionStyle}>Review judgment events by project, time window, event type, and risk mix.</p>
              </div>
              <div style={scopeSummaryStyle}>
                Current view: {activeWindowLabel} / {activeProjectLabel} / {activeSignalLabel} / {activeEventLabel} events / {visibleEvents.length} shown
              </div>
              <details style={mixDetailsStyle}>
                <summary style={mixSummaryStyle}>Risk Mix / Signal Type Mix</summary>
                <div style={mixGridStyle}>
                  <div style={mixGroupStyle}>
                    <span style={summaryLabelStyle}>Risk Mix</span>
                    <div style={chipRowStyle}>
                      {["low", "medium", "high"].map((riskLevel) => (
                        <span key={riskLevel} style={riskLevel === "high" ? riskChipStyle : chipStyle}>
                          {formatLabel(riskLevel)} {displayRiskMix[riskLevel] || 0}
                        </span>
                      ))}
                    </div>
                  </div>
                  <div style={mixGroupStyle}>
                    <span style={summaryLabelStyle}>Signal Type Mix</span>
                    <div style={chipRowStyle}>
                      {["manual_judgment", "verification_risk", "calibration_learning", "review_decision"].map((signalType) => (
                        <span key={signalType} style={signalType === "verification_risk" ? riskChipStyle : chipStyle}>
                          {formatLabel(signalType)} {displaySignalTypeMix[signalType] || 0}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              </details>
              {projectSummaries.length > 0 ? (
                <div style={projectSummaryGridStyle}>
                  {projectSummaries.slice(0, 6).map((project) => (
                    <button
                      key={project.projectKey}
                      type="button"
                      onClick={() => setProjectFilter(project.projectKey)}
                      style={projectFilter === project.projectKey ? activeProjectSummaryCardStyle : projectSummaryCardStyle}
                      title="Filter timeline by this project"
                    >
                      <span style={summaryLabelStyle}>{project.projectLabel}</span>
                      <strong style={projectSummaryValueStyle}>{project.totalCount} event(s)</strong>
                      <span style={projectSummaryMetaStyle}>
                        Manual {project.manualCount} / Risk {project.riskCount} / Watch {project.watchCount} / Action {project.actionCount}
                      </span>
                    </button>
                  ))}
                </div>
              ) : null}
              {projectFilter !== "all" ? (
                <div style={activeProjectNoticeStyle}>
                  Project filter active: {projectSummaries.find((project) => project.projectKey === projectFilter)?.projectLabel || projectFilter}
                  <button type="button" onClick={() => setProjectFilter("all")} style={clearProjectFilterButtonStyle}>
                    Clear
                  </button>
                </div>
              ) : null}
              {signalFilter ? (
                <div style={activeProjectNoticeStyle}>
                  Signal filter active: {signalFilter}
                  <button type="button" onClick={() => setSignalFilter("")} style={clearProjectFilterButtonStyle}>
                    Clear
                  </button>
                </div>
              ) : null}
              <div style={filterGroupStyle}>
                <span style={filterGroupLabelStyle}>Time Window</span>
                <div style={filterRowStyle}>
                  {timeWindowOptions.map((option) => (
                    <button
                      key={option.value}
                      type="button"
                      onClick={() => setTimeWindowFilter(option.value)}
                      style={timeWindowFilter === option.value ? activeFilterButtonStyle : filterButtonStyle}
                    >
                      {option.label} ({option.count})
                    </button>
                  ))}
                </div>
              </div>
              <div style={filterGroupStyle}>
                <span style={filterGroupLabelStyle}>Event Type</span>
                <div style={filterRowStyle}>
                  {filterOptions.map((option) => (
                    <button
                      key={option.value}
                      type="button"
                      onClick={() => setTimelineFilter(option.value)}
                      style={timelineFilter === option.value ? activeFilterButtonStyle : filterButtonStyle}
                    >
                      {option.label} ({option.count})
                    </button>
                  ))}
                </div>
              </div>
            </section>

            {timelineEvents.length === 0 ? (
              <EmptyStateCard
                title="No trajectory seed events yet"
                description="Trajectory events are created after Project Takeaway reviews or calibration events. Start in the Review Inbox to produce the first judgment events."
                primaryHref="/workspace/projects/review"
                primaryLabel="Open Review Inbox"
                secondaryHref="/workspace/projects"
                secondaryLabel="Project Takeaways"
              />
            ) : timeFilteredEvents.length === 0 ? (
              <EmptyStateCard
                title="No events in this time window"
                description="The current project has trajectory events, but none fall inside the selected time range. Switch back to All Time to inspect the full judgment history."
                secondaryHref="/workspace/projects/review"
                secondaryLabel="Review Inbox"
              />
            ) : visibleEvents.length === 0 ? (
              <EmptyStateCard
                title="No events match this filter"
                description="The selected project and time window have trajectory events, but none match this event type. Try All, Manual, Risk, Watch, or Action depending on the review question."
                secondaryHref="/workspace/projects/review"
                secondaryLabel="Review Inbox"
              />
            ) : (
              <section style={timelinePanelStyle}>
                {visibleEvents.slice(0, 80).map((event) => (
                  <article key={`${event.kind}:${event.id}`} style={timelineItemStyle}>
                    <div style={timelineRailStyle}>
                      <span style={event.kind === "review" ? reviewDotStyle : calibrationDotStyle} />
                    </div>
                    <div style={timelineContentStyle}>
                      <div style={timelineHeaderStyle}>
                        <div>
                          <span style={metaStyle}>{formatDateTime(event.timestamp)} / {formatLabel(event.kind)}</span>
                          <h2 style={itemTitleStyle}>{event.title}</h2>
                        </div>
                        <span style={event.isManual ? manualChipStyle : chipStyle}>{event.sourceLabel}</span>
                      </div>
                      <div style={itemSummaryStyle}>
                        {event.projectLabel} / {formatLabel(event.outcome)} / {formatLabel(event.trajectorySignalType)} / Verification: {formatLabel(event.verificationStatus)} / Confidence: {event.confidence}
                      </div>
                      <div style={chipRowStyle}>
                        <span style={hasRisk(event) ? riskChipStyle : chipStyle}>Risk {formatLabel(event.riskLevel)}</span>
                        <span style={chipStyle}>Stage {formatLabel(getTrajectoryStage(event))}</span>
                        <span style={chipStyle}>{formatLabel(event.trajectorySignalType)}</span>
                        {event.isManual ? <span style={chipStyle}>Layer {formatLabel(event.cognitiveLayer)}</span> : null}
                        {event.auditEventCount > 0 ? <span style={chipStyle}>Audit Events {event.auditEventCount}</span> : null}
                        <span style={chipStyle}>Unsupported {event.unsupportedCount}</span>
                        <span style={chipStyle}>Inferred {event.inferredCount}</span>
                        <span style={chipStyle}>Blocked {event.blockedCount}</span>
                      </div>
                      <VerifiedInsightObjectPanel
                        rows={buildTrajectoryVerifiedInsightObjectRows(event)}
                        subtitle="Recorded verification boundary for this trajectory event. It preserves review history but does not reopen gates, create evidence, or change action eligibility."
                        style={{ marginTop: "10px" }}
                      />
                      <VerificationGateNote
                        verification={{
                          verification_status: event.verificationStatus === "unknown" ? "" : event.verificationStatus,
                          blocked_downstream_actions: event.blockedDownstreamActions,
                          claim_support_summary: {
                            unsupported: event.unsupportedCount,
                            inferred: event.inferredCount,
                          },
                        }}
                        accentColor={hasRisk(event) ? "var(--app-danger-border)" : "var(--app-surface-strong-border)"}
                        style={{ marginTop: "10px" }}
                      />
                      <div style={eventContextGridStyle}>
                        <div style={eventContextCardStyle}>
                          <span style={summaryLabelStyle}>Why This Matters</span>
                          <strong>{buildEventImportance(event)}</strong>
                        </div>
                        <div style={eventContextCardStyle}>
                          <span style={summaryLabelStyle}>Source Context</span>
                          <strong>{buildSourceContext(event)}</strong>
                        </div>
                        {event.isManual ? (
                          <div style={manualEventContributionCardStyle}>
                            <span style={summaryLabelStyle}>Manual Contribution</span>
                            <strong>{buildManualEventContribution(event)}</strong>
                          </div>
                        ) : null}
                        <div style={stageExplanationCardStyle}>
                          <span style={summaryLabelStyle}>Stage Explanation</span>
                          <strong>{buildStageExplanation(event)}</strong>
                        </div>
                        {event.auditEventCount > 0 ? (
                          <div style={auditFoldCardStyle}>
                            <span style={summaryLabelStyle}>Audit / Calibration Folded</span>
                            <strong>
                              {event.auditEventCount} audit event(s) are folded into this review:
                              {" "}
                              {event.auditEventLabels.map(formatLabel).join(" / ")}
                            </strong>
                          </div>
                        ) : null}
                      </div>
                      {event.isManual && (event.uploadReason || event.intendedUse) ? (
                        <p style={reasonStyle}>
                          {[event.uploadReason ? `Reason: ${event.uploadReason}` : "", event.intendedUse ? `Use: ${event.intendedUse}` : ""]
                            .filter(Boolean)
                            .join(" / ")}
                        </p>
                      ) : null}
                      {event.followupResult || event.reviewNote || event.evidenceUpdate || event.nextReviewDate || event.expectedOutcome ? (
                        <p style={reasonStyle}>
                          {[
                            event.followupResult ? `Follow-up: ${formatLabel(event.followupResult)}` : "",
                            event.expectedOutcome ? `Expected: ${event.expectedOutcome}` : "",
                            event.reviewNote ? `Note: ${event.reviewNote}` : "",
                            event.evidenceUpdate ? `Evidence: ${event.evidenceUpdate}` : "",
                            event.nextReviewDate ? `Next review: ${event.nextReviewDate}` : "",
                          ]
                            .filter(Boolean)
                            .join(" / ")}
                        </p>
                      ) : null}
                      {event.reason ? <p style={reasonStyle}>{event.reason}</p> : null}
                      <div style={linkRowStyle}>
                        {event.kind === "review" && event.id ? (
                          <Link href={`/workspace/projects/review/record?id=${encodeURIComponent(event.id)}`} style={secondaryLinkStyle}>
                            Open Review Record
                          </Link>
                        ) : null}
                        {event.signalId ? (
                          <Link href={`/signals/detail?id=${encodeURIComponent(event.signalId)}`} style={secondaryLinkStyle}>
                            Open Signal
                          </Link>
                        ) : null}
                        {event.signalId && event.projectLabel !== "Unknown project" ? (
                          <Link href={`/workspace/projects/review?signal_id=${encodeURIComponent(event.signalId)}&view=records`} style={secondaryLinkStyle}>
                            Open Review Inbox
                          </Link>
                        ) : null}
                      </div>
                    </div>
                  </article>
                ))}
              </section>
            )}
        </div>
      )}
    </AppContainer>
  );
}

const toolbarStyle = {
  marginBottom: "20px",
  display: "flex",
  gap: "12px",
  flexWrap: "wrap" as const,
  border: "1px solid var(--app-surface-border)",
  borderRadius: "20px",
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
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  color: "var(--app-text-strong)",
  background: "var(--app-secondary-action-bg)",
  padding: "10px 14px",
  fontSize: "14px",
  fontWeight: 700,
  textDecoration: "none",
} as const;

const pageGridStyle = {
  display: "grid",
  gap: "16px",
} as const;

const summaryBandStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "20px",
  background: "var(--app-surface-bg)",
  padding: "18px",
  display: "grid",
  gap: "14px",
  boxShadow: "var(--app-surface-shadow)",
} as const;

const filterPanelStyle = {
  ...summaryBandStyle,
  gap: "18px",
} as const;

const sectionTitleStyle = {
  color: "var(--app-text-strong)",
  fontSize: "14px",
  fontWeight: 700,
  textTransform: "uppercase" as const,
} as const;

const sectionDescriptionStyle = {
  margin: "8px 0 0",
  color: "var(--app-text-muted)",
  fontSize: "13px",
  lineHeight: 1.5,
} as const;

const summaryMetricRowStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
  gap: "12px",
} as const;

const summaryItemStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "18px",
  background: "var(--app-surface-muted-bg)",
  padding: "18px",
  display: "grid",
  gap: "10px",
  minHeight: "86px",
} as const;

const metricLabelStyle = {
  color: "var(--app-text-muted)",
  fontSize: "13px",
  fontWeight: 500,
} as const;

const summaryLabelStyle = {
  color: "var(--app-text-subtle)",
  fontSize: "12px",
  fontWeight: 700,
  textTransform: "uppercase" as const,
} as const;

const summaryValueStyle = {
  color: "var(--app-text-strong)",
  fontSize: "30px",
  fontWeight: 800,
  lineHeight: 1,
  overflowWrap: "anywhere" as const,
} as const;

const opsInterpretationStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
  gap: "10px",
} as const;

const opsInterpretationItemStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  color: "var(--app-text-muted)",
  padding: "12px",
  display: "grid",
  gap: "6px",
  fontSize: "13px",
  lineHeight: "1.55",
} as const;

const stageFlowStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))",
  gap: "10px",
} as const;

const stageFlowItemStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  color: "var(--app-text-strong)",
  padding: "12px",
  display: "grid",
  gap: "6px",
} as const;

const stageFlowInsightStyle = {
  ...stageFlowItemStyle,
  gridColumn: "1 / -1",
  color: "var(--app-info-fg)",
  background: "var(--app-info-bg)",
  border: "1px solid var(--app-info-border)",
} as const;

const trendLineStyle = {
  border: "1px solid var(--app-info-border)",
  borderRadius: "8px",
  background: "var(--app-info-bg)",
  color: "var(--app-info-fg)",
  padding: "10px 12px",
  fontSize: "13px",
  fontWeight: 800,
  lineHeight: "1.5",
} as const;

const trajectoryBoundaryStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  color: "var(--app-text-muted)",
  padding: "10px 12px",
  display: "grid",
  gap: "5px",
  fontSize: "13px",
  lineHeight: "1.5",
} as const;

const scopeSummaryStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  color: "var(--app-text-muted)",
  padding: "10px 12px",
  fontSize: "13px",
  fontWeight: 700,
} as const;

const mixDetailsStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  padding: "10px 12px",
} as const;

const mixSummaryStyle = {
  color: "var(--app-text-muted)",
  fontSize: "13px",
  fontWeight: 700,
  cursor: "pointer",
  lineHeight: "1.45",
} as const;

const mixGridStyle = {
  marginTop: "12px",
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
  gap: "10px",
} as const;

const mixGroupStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-bg)",
  padding: "10px 12px",
  display: "grid",
  gap: "8px",
} as const;

const projectSummaryGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))",
  gap: "10px",
} as const;

const projectSummaryCardStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  color: "var(--app-text-muted)",
  padding: "12px",
  display: "grid",
  gap: "7px",
  textAlign: "left" as const,
  cursor: "pointer",
} as const;

const activeProjectSummaryCardStyle = {
  ...projectSummaryCardStyle,
  border: "1px solid var(--app-info-border)",
  background: "var(--app-info-bg)",
} as const;

const projectSummaryValueStyle = {
  color: "var(--app-text-strong)",
  fontSize: "18px",
  fontWeight: 800,
} as const;

const projectSummaryMetaStyle = {
  color: "var(--app-text-muted)",
  fontSize: "12px",
  fontWeight: 600,
  lineHeight: "1.5",
} as const;

const activeProjectNoticeStyle = {
  border: "1px solid var(--app-info-border)",
  borderRadius: "8px",
  background: "var(--app-info-bg)",
  color: "var(--app-info-fg)",
  padding: "10px 12px",
  display: "flex",
  gap: "10px",
  justifyContent: "space-between",
  alignItems: "center",
  flexWrap: "wrap" as const,
  fontSize: "13px",
  fontWeight: 800,
} as const;

const clearProjectFilterButtonStyle = {
  border: "1px solid var(--app-info-border)",
  borderRadius: "8px",
  background: "var(--app-secondary-action-bg)",
  color: "var(--app-info-fg)",
  padding: "6px 9px",
  fontSize: "12px",
  fontWeight: 700,
  cursor: "pointer",
} as const;

const filterGroupStyle = {
  display: "grid",
  gap: "8px",
} as const;

const filterGroupLabelStyle = {
  color: "var(--app-text-subtle)",
  fontSize: "12px",
  fontWeight: 700,
  textTransform: "uppercase" as const,
} as const;

const filterRowStyle = {
  display: "flex",
  gap: "8px",
  flexWrap: "wrap" as const,
} as const;

const filterButtonStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "999px",
  background: "var(--app-surface-muted-bg)",
  color: "var(--app-text-muted)",
  padding: "8px 10px",
  fontSize: "13px",
  fontWeight: 700,
  cursor: "pointer",
} as const;

const activeFilterButtonStyle = {
  ...filterButtonStyle,
  border: "1px solid var(--app-primary-action-border)",
  background: "var(--app-primary-action-bg)",
  color: "var(--app-primary-action-fg)",
} as const;

const timelinePanelStyle = {
  display: "grid",
  gap: "16px",
} as const;

const timelineItemStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "18px",
  background: "var(--app-surface-bg)",
  padding: "20px 18px",
  display: "grid",
  gridTemplateColumns: "1fr",
  gap: "0",
  boxShadow: "var(--app-surface-shadow)",
} as const;

const timelineRailStyle = {
  display: "none",
} as const;

const dotBaseStyle = {
  width: "12px",
  height: "12px",
  borderRadius: "999px",
  display: "inline-block",
} as const;

const reviewDotStyle = {
  ...dotBaseStyle,
  background: "var(--app-text-strong)",
} as const;

const calibrationDotStyle = {
  ...dotBaseStyle,
  background: "var(--app-info-fg)",
} as const;

const timelineContentStyle = {
  display: "grid",
  gap: "12px",
  minWidth: 0,
} as const;

const timelineHeaderStyle = {
  display: "flex",
  justifyContent: "space-between",
  gap: "12px",
  alignItems: "start",
  flexWrap: "wrap" as const,
} as const;

const metaStyle = {
  color: "var(--app-text-subtle)",
  fontSize: "12px",
  fontWeight: 600,
  textTransform: "uppercase" as const,
} as const;

const itemTitleStyle = {
  margin: "4px 0 0",
  color: "var(--app-text-strong)",
  fontSize: "18px",
  fontWeight: 400,
  lineHeight: "1.35",
} as const;

const itemSummaryStyle = {
  color: "var(--app-text-muted)",
  fontSize: "13px",
  lineHeight: "1.55",
  fontWeight: 500,
} as const;

const chipRowStyle = {
  display: "flex",
  gap: "8px",
  flexWrap: "wrap" as const,
} as const;

const chipStyle = {
  display: "inline-flex",
  alignItems: "center",
  border: "1px solid var(--app-chip-border)",
  borderRadius: "999px",
  background: "var(--app-chip-bg)",
  color: "var(--app-chip-fg)",
  padding: "5px 9px",
  fontSize: "12px",
  fontWeight: 600,
} as const;

const manualContributionPanelStyle = {
  border: "1px solid var(--app-success-border)",
  borderRadius: "12px",
  background: "var(--app-success-bg)",
  padding: "14px",
  display: "grid",
  gap: "10px",
} as const;

const manualContributionHeaderStyle = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  gap: "12px",
  flexWrap: "wrap" as const,
} as const;

const manualContributionTitleStyle = {
  display: "block",
  marginTop: "4px",
  color: "var(--app-success-fg)",
  fontSize: "15px",
  lineHeight: "1.35",
} as const;

const manualContributionMetricRowStyle = {
  display: "flex",
  gap: "7px",
  flexWrap: "wrap" as const,
  color: "var(--app-success-fg)",
  fontSize: "12px",
  fontWeight: 800,
} as const;

const manualContributionGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
  gap: "10px",
} as const;

const manualContributionCardStyle = {
  border: "1px solid var(--app-success-border)",
  borderRadius: "8px",
  background: "var(--app-surface-bg)",
  color: "var(--app-success-fg)",
  padding: "10px 12px",
  display: "grid",
  gap: "6px",
  fontSize: "13px",
  lineHeight: "1.55",
} as const;

const eventContextGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
  gap: "10px",
} as const;

const eventContextCardStyle = {
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

const stageExplanationCardStyle = {
  ...eventContextCardStyle,
  gridColumn: "1 / -1",
  border: "1px solid var(--app-info-border)",
  background: "var(--app-info-bg)",
  color: "var(--app-info-fg)",
} as const;

const auditFoldCardStyle = {
  ...eventContextCardStyle,
  gridColumn: "1 / -1",
  border: "1px solid var(--app-surface-border)",
  background: "var(--app-surface-muted-bg)",
  color: "var(--app-text-muted)",
} as const;

const manualEventContributionCardStyle = {
  ...eventContextCardStyle,
  border: "1px solid var(--app-success-border)",
  background: "var(--app-success-bg)",
  color: "var(--app-success-fg)",
} as const;

const manualChipStyle = {
  ...chipStyle,
  border: "1px solid var(--app-success-border)",
  background: "var(--app-success-bg)",
  color: "var(--app-success-fg)",
} as const;

const riskChipStyle = {
  ...chipStyle,
  border: "1px solid var(--app-danger-border)",
  background: "var(--app-danger-bg)",
  color: "var(--app-danger-fg)",
} as const;

const reasonStyle = {
  margin: 0,
  color: "var(--app-text-muted)",
  fontSize: "13px",
  lineHeight: "1.6",
} as const;

const linkRowStyle = {
  display: "flex",
  gap: "10px",
  flexWrap: "wrap" as const,
} as const;

const secondaryLinkStyle = {
  display: "inline-flex",
  alignItems: "center",
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-secondary-action-bg)",
  color: "var(--app-text-strong)",
  padding: "8px 10px",
  fontSize: "13px",
  fontWeight: 700,
  textDecoration: "none",
} as const;

const emptyCardStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  padding: "18px",
  background: "var(--app-surface-muted-bg)",
  color: "var(--app-text-muted)",
  display: "grid",
  gap: "10px",
} as const;

const emptyTitleStyle = {
  color: "var(--app-text-strong)",
  fontSize: "15px",
  fontWeight: 800,
  lineHeight: "1.4",
} as const;

const emptyDescriptionStyle = {
  margin: 0,
  color: "var(--app-text-muted)",
  fontSize: "13px",
  lineHeight: "1.6",
} as const;

const errorCardStyle = {
  border: "1px solid var(--app-danger-border)",
  borderRadius: "8px",
  padding: "14px 16px",
  background: "var(--app-danger-bg)",
  color: "var(--app-danger-fg)",
  marginBottom: "16px",
  display: "grid",
  gap: "10px",
} as const;

const infoCardStyle = {
  border: "1px solid var(--app-info-border)",
  borderRadius: "8px",
  padding: "14px 16px",
  background: "var(--app-info-bg)",
  color: "var(--app-info-fg)",
  marginBottom: "16px",
} as const;
