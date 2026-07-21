"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import AppContainer from "@/components/AppContainer";
import RequireAdminAuth from "@/components/RequireAdminAuth";
import VerificationGateNote from "@/components/VerificationGateNote";
import VerifiedInsightObjectPanel, { type VerifiedInsightObjectRow } from "@/components/VerifiedInsightObjectPanel";
import { apiUrl } from "@/lib/api";
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
  provenance_completeness?: string;
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
  created_at?: string;
};

type RelatedCalibrationEvent = {
  id?: string;
  event_type?: string;
  outcome?: string;
  source_status?: string;
  review_record_id?: string;
  is_current_review_record_event?: boolean;
  created_at?: string;
  updated_at?: string;
};

type AuditSummary = {
  event_count?: number;
  has_review_record_created?: boolean;
  has_outcome_event?: boolean;
  matching_review_record_event_count?: number;
};

type ReviewRecordResponse = {
  item?: ProjectReviewRecord;
  related_calibration_events?: RelatedCalibrationEvent[];
  audit_summary?: AuditSummary;
  detail?: string;
  message?: string;
};

function formatLabel(value?: string) {
  return (value || "")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase())
    .trim();
}

function formatDateTime(value?: string) {
  if (!value) return "n/a";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function formatConfidence(label?: string, score?: number | null) {
  const cleanLabel = label ? formatLabel(label) : "n/a";
  return typeof score === "number" ? `${cleanLabel} (${score.toFixed(2)})` : cleanLabel;
}

function formatActionList(values?: string[]) {
  if (!Array.isArray(values) || values.length === 0) return "None";
  return values.map(formatLabel).join(", ");
}

function formatEligibilityDecision(
  decision: EligibilityDecision | undefined,
  labels: { allowed: string; blocked: string }
) {
  if (!decision || typeof decision.allowed !== "boolean") return "Not recorded";
  return decision.allowed ? labels.allowed : labels.blocked;
}

function formatSource(record?: ProjectReviewRecord | null) {
  if (!record) return "Unknown source";
  if (record.is_manual_source || record.source_type === "manual_upload") {
    return record.manual_session_id ? `Manual Upload (${record.manual_session_id})` : "Manual Upload";
  }
  if (record.candidate_source === "knowledge_convergence") return "Knowledge Convergence";
  return "Collected Signal";
}

function formatModel(record?: ProjectReviewRecord | null) {
  const model = record?.produced_by_model;
  if (!model) return "Legacy / not recorded";
  return [model.provider, model.model_id, model.route_key, model.task_type, model.provenance_completeness]
    .filter(Boolean)
    .join(" / ");
}

function buildLearningBoundary(record?: ProjectReviewRecord | null) {
  if (!record) return "";
  if (record.manual_project_takeaway_override) {
    return "This record includes a human override. Treat it as auditable judgment memory, not automatic positive calibration.";
  }
  if ((record.blocked_downstream_actions || []).length > 0 || (record.unsupported_claim_count || 0) > 0) {
    return "This record carries gate or claim-support risk. Keep it visible before reusing it as project memory.";
  }
  if (record.outcome === "watch") {
    return "This record keeps the item under observation before stronger commitment.";
  }
  if (record.outcome === "action" || record.outcome === "confirmed") {
    return "This record is part of project commitment memory after review.";
  }
  return "This record preserves one human review decision for calibration and later project context.";
}

function buildDecisionSnapshot(record?: ProjectReviewRecord | null) {
  const outcome = record?.outcome || "";
  const blockedActionCount = Array.isArray(record?.blocked_downstream_actions) ? record.blocked_downstream_actions.length : 0;
  const unsupportedClaimCount = record?.unsupported_claim_count || 0;
  const actionAllowed = record?.action_eligibility?.low_risk_action_candidate?.allowed;
  const hasGateRisk = blockedActionCount > 0 || unsupportedClaimCount > 0 || actionAllowed === false;

  if (!record) {
    return {
      headline: "No review record loaded",
      reusePosture: "Not available",
      riskPosture: "No record context",
      nextStep: "Return to Review Records.",
    };
  }

  if (record.manual_project_takeaway_override) {
    return {
      headline: "Human override judgment",
      reusePosture: "Audit before reuse",
      riskPosture: "Gate risk may still be present",
      nextStep: "Read Review Boundary and the override note before using this as project memory.",
    };
  }

  if (outcome === "watch") {
    return {
      headline: "Watch decision",
      reusePosture: "Observation memory",
      riskPosture: hasGateRisk ? "Gate or claim risk visible" : "No recorded action block",
      nextStep: "Use Trajectory or Review Records to decide whether later evidence changes the posture.",
    };
  }

  if (outcome === "action" || outcome === "confirmed") {
    return {
      headline: hasGateRisk ? "Committed decision with visible risk" : "Committed review decision",
      reusePosture: hasGateRisk ? "Review boundary first" : "Reusable project memory",
      riskPosture: hasGateRisk ? "Do not treat as low-risk action without checking gates" : "No recorded gate block",
      nextStep: hasGateRisk ? "Start with Review Boundary before opening related surfaces." : "Open related surfaces if you need source or trajectory context.",
    };
  }

  if (outcome === "rejected" || outcome === "dismissed") {
    return {
      headline: "Closed review decision",
      reusePosture: "Calibration or caution memory",
      riskPosture: "Not reusable as a positive Project Takeaway",
      nextStep: "Use this to understand why the candidate was not accepted.",
    };
  }

  return {
    headline: "Review decision memory",
    reusePosture: hasGateRisk ? "Review boundary first" : "Inspect before reuse",
    riskPosture: hasGateRisk ? "Gate or claim risk visible" : "No recorded gate block",
    nextStep: "Use Review Boundary, Audit Trail, and related surfaces before drawing a new conclusion.",
  };
}

function safeCount(value?: number) {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

function gateDecisionValue(decision?: EligibilityDecision, blockedActions: string[] = []) {
  if (decision?.allowed === false || blockedActions.includes("low_risk_action_candidate")) return "Blocked";
  if (decision?.allowed === true) return "Allowed";
  return "Not recorded";
}

function gateDecisionTone(decision?: EligibilityDecision, blockedActions: string[] = []): VerifiedInsightObjectRow["tone"] {
  if (decision?.allowed === false || blockedActions.includes("low_risk_action_candidate")) return "bad";
  if (decision?.allowed === true) return "good";
  return "neutral";
}

function toneFromOutcome(outcome?: string): VerifiedInsightObjectRow["tone"] {
  const normalized = (outcome || "").toLowerCase();
  if (["confirmed", "action", "action_completed"].includes(normalized)) return "good";
  if (normalized === "watch") return "watch";
  if (["rejected", "dismissed"].includes(normalized)) return "bad";
  return "neutral";
}

function toneFromVerification(status?: string, blockedActions: string[] = []): VerifiedInsightObjectRow["tone"] {
  const normalized = (status || "").toLowerCase();
  if (blockedActions.includes("low_risk_action_candidate") || ["unsupported", "contradicted", "not_verifiable"].includes(normalized)) {
    return "bad";
  }
  if (["partially_verified", "weakly_supported", "needs_review"].includes(normalized)) return "watch";
  if (["verified", "verified_with_limitations", "supported"].includes(normalized)) return "good";
  return "neutral";
}

function formatClaimSupport(summary?: Record<string, number>) {
  if (!summary) return "";
  return Object.entries(summary)
    .filter(([, count]) => typeof count === "number" && count > 0)
    .map(([key, count]) => `${formatLabel(key)} ${count}`)
    .join(", ");
}

function buildVerifiedInsightObjectRows(
  record: ProjectReviewRecord,
  eligibility?: ActionEligibilitySummary
): VerifiedInsightObjectRow[] {
  const supportSummary = record.claim_support_summary || {};
  const blockedActions = eligibility?.signals?.blocked_downstream_actions || record.blocked_downstream_actions || [];
  const verificationStatus = eligibility?.signals?.verification_status || record.verification_status || "";
  const unsupportedCount =
    safeCount(eligibility?.signals?.unsupported_or_contradicted_claim_count) ||
    safeCount(record.unsupported_claim_count) ||
    safeCount(supportSummary.unsupported) + safeCount(supportSummary.contradicted);
  const inferredCount =
    safeCount(eligibility?.signals?.inferred_claim_count) ||
    safeCount(record.inferred_claim_count) ||
    safeCount(supportSummary.inferred);
  const claimCount = Object.values(supportSummary).reduce((total, count) => total + safeCount(count), 0) || unsupportedCount + inferredCount;
  const actionGate = eligibility?.low_risk_action_candidate;

  return [
    {
      label: "Outcome",
      value: formatLabel(record.outcome) || "Not recorded",
      detail: "Recorded Project Review outcome; this is judgment memory, not a new gate.",
      tone: toneFromOutcome(record.outcome),
    },
    {
      label: "Verification",
      value: formatLabel(verificationStatus) || "Not recorded",
      detail: "Recorded verification_status from the Review Record.",
      tone: toneFromVerification(verificationStatus, blockedActions),
    },
    {
      label: "Confidence",
      value: formatConfidence(record.confidence_label, record.confidence_score),
      detail: "Confidence is preserved as review context only.",
      tone: record.confidence_label?.toLowerCase() === "low" ? "watch" : "neutral",
    },
    {
      label: "Claims",
      value: claimCount > 0 ? `${claimCount} recorded` : "Not recorded",
      detail: formatClaimSupport(supportSummary) || `Unsupported ${unsupportedCount}, inferred ${inferredCount}.`,
      tone: unsupportedCount > 0 ? "bad" : inferredCount > 0 ? "watch" : claimCount > 0 ? "good" : "neutral",
    },
    {
      label: "Low-risk Action",
      value: gateDecisionValue(actionGate, blockedActions),
      detail: actionGate?.reason || "No low-risk Action gate reason is recorded on this detail view.",
      tone: gateDecisionTone(actionGate, blockedActions),
    },
  ];
}

function hasVerifiedInsightObject(record?: ProjectReviewRecord | null, eligibility?: ActionEligibilitySummary) {
  return Boolean(
    record &&
      (record.outcome ||
        record.verification_status ||
        record.confidence_label ||
        record.claim_support_summary ||
        record.blocked_downstream_actions?.length ||
        eligibility)
  );
}

function InfoItem({ label, value }: { label: string; value: string }) {
  return (
    <div style={infoItemStyle}>
      <span style={smallLabelStyle}>{label}</span>
      <strong>{value || "n/a"}</strong>
    </div>
  );
}

export default function ReviewRecordDetailPage() {
  const searchParams = useSearchParams();
  const recordId = searchParams.get("id") || "";
  const [record, setRecord] = useState<ProjectReviewRecord | null>(null);
  const [relatedEvents, setRelatedEvents] = useState<RelatedCalibrationEvent[]>([]);
  const [auditSummary, setAuditSummary] = useState<AuditSummary | null>(null);
  const [loading, setLoading] = useState(Boolean(recordId));
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    let cancelled = false;
    if (!recordId) {
      setLoading(false);
      setErrorMessage("Missing review record id.");
      return () => {
        cancelled = true;
      };
    }

    async function loadRecord() {
      setLoading(true);
      setErrorMessage("");
      try {
        const response = await adminFetchWithTimeout(apiUrl(`/projects/review-records/${encodeURIComponent(recordId)}`), {
          cache: "no-store",
        });
        const data = (await response.json().catch(() => null)) as ReviewRecordResponse | null;
        if (!response.ok) {
          throw new Error(data?.detail || `Failed to load review record (${response.status}).`);
        }
        if (!cancelled) {
          setRecord(data?.item || null);
          setRelatedEvents(Array.isArray(data?.related_calibration_events) ? data.related_calibration_events : []);
          setAuditSummary(data?.audit_summary || null);
        }
      } catch (error) {
        if (!cancelled) {
          setRecord(null);
          setRelatedEvents([]);
          setAuditSummary(null);
          setErrorMessage(
            isAbortError(error)
              ? "Review record request timed out after 8 seconds. Confirm the backend is running, then reload this page."
              : error instanceof Error
                ? error.message
                : "Failed to load review record."
          );
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void loadRecord();
    return () => {
      cancelled = true;
    };
  }, [recordId]);

  const eligibility = record?.action_eligibility;
  const actionGate = eligibility?.low_risk_action_candidate;
  const signalHref = record?.signal_id ? `/signals/detail?id=${encodeURIComponent(record.signal_id)}` : "";
  const fitHref = record?.project_id && record?.signal_id
    ? `/workspace/projects/improvement-detail?project_id=${encodeURIComponent(record.project_id)}&signal_id=${encodeURIComponent(record.signal_id)}`
    : "";
  const manualHref = record?.manual_session_id ? `/manual/detail?id=${encodeURIComponent(record.manual_session_id)}` : "";
  const trajectoryHref = `/workspace/projects/trajectory?project_id=${encodeURIComponent(record?.project_id || "")}&signal_id=${encodeURIComponent(record?.signal_id || "")}`;
  const claimSupportRows = useMemo(
    () => Object.entries(record?.claim_support_summary || {}).filter(([, count]) => Number(count) > 0),
    [record?.claim_support_summary]
  );
  const decisionSnapshot = useMemo(() => buildDecisionSnapshot(record), [record]);
  const verifiedInsightObjectRows = useMemo(
    () => (record ? buildVerifiedInsightObjectRows(record, eligibility) : []),
    [record, eligibility]
  );
  const showVerifiedInsightObject = hasVerifiedInsightObject(record, eligibility);

  return (
    <AppContainer style={{ paddingTop: "24px" }}>
      <RequireAdminAuth>
        <div style={headerStyle}>
          <div>
            <div style={smallLabelStyle}>Project Review</div>
            <h1 style={titleStyle}>Review Record Detail</h1>
            <p style={descriptionStyle}>
              Read-only view of one Project Takeaway review decision, its source context, and the gate state recorded at review time.
            </p>
          </div>
          <div style={linkRowStyle}>
            <Link href="/workspace/projects/review?view=records" style={primaryLinkStyle}>
              Review Records
            </Link>
            <Link href="/workspace/projects/trajectory" style={secondaryLinkStyle}>
              Trajectory
            </Link>
          </div>
        </div>

        {loading ? (
          <div style={emptyStyle}>Loading review record...</div>
        ) : errorMessage ? (
          <div style={errorStyle}>
            <strong>Review record could not load.</strong>
            <span>{errorMessage}</span>
          </div>
        ) : record ? (
          <div style={pageGridStyle}>
            <section style={summaryStyle}>
              <div style={summaryHeaderStyle}>
                <div>
                  <div style={smallLabelStyle}>{record.project_name || record.project_id || "Unknown project"}</div>
                  <h2 style={recordTitleStyle}>{record.signal_title || record.signal_id || record.id || "Untitled review record"}</h2>
                </div>
                <span style={outcomeChipStyle}>{formatLabel(record.outcome)}</span>
              </div>
              <p style={bodyTextStyle}>{record.reason || "No reviewer reason was recorded."}</p>
              <div style={metricGridStyle}>
                <InfoItem label="Record ID" value={record.id || "n/a"} />
                <InfoItem label="Reviewed" value={formatDateTime(record.reviewed_at || record.updated_at || record.created_at)} />
                <InfoItem label="Source" value={formatSource(record)} />
                <InfoItem label="Verification" value={formatLabel(record.verification_status) || "n/a"} />
                <InfoItem label="Confidence" value={formatConfidence(record.confidence_label, record.confidence_score)} />
                <InfoItem label="Model Provenance" value={formatModel(record)} />
              </div>
            </section>

            <section style={panelStyle}>
              <div style={sectionTitleStyle}>Decision Snapshot</div>
              <div style={snapshotHeroStyle}>
                <span style={smallLabelStyle}>Current judgment</span>
                <strong>{decisionSnapshot.headline}</strong>
                <span>{decisionSnapshot.nextStep}</span>
              </div>
              <div style={metricGridStyle}>
                <InfoItem label="Review Outcome" value={formatLabel(record.outcome) || "n/a"} />
                <InfoItem label="Reuse Posture" value={decisionSnapshot.reusePosture} />
                <InfoItem label="Risk Posture" value={decisionSnapshot.riskPosture} />
              </div>
            </section>

            {showVerifiedInsightObject ? (
              <section style={panelStyle}>
                <VerifiedInsightObjectPanel
                  rows={verifiedInsightObjectRows}
                  objectId={record.id}
                  subtitle="Recorded verification boundary for this Review Record detail. It preserves judgment history but does not reconfirm, reopen gates, create evidence, or change action eligibility."
                />
              </section>
            ) : null}

            <section style={panelStyle}>
              <div style={sectionTitleStyle}>Review Boundary</div>
              <div style={boundaryStyle}>{buildLearningBoundary(record)}</div>
              <VerificationGateNote
                verification={{
                  verification_status: eligibility?.signals?.verification_status || record.verification_status || "",
                  allowed_downstream_actions: eligibility?.signals?.allowed_downstream_actions || record.allowed_downstream_actions || [],
                  blocked_downstream_actions: eligibility?.signals?.blocked_downstream_actions || record.blocked_downstream_actions || [],
                  claim_support_summary: {
                    unsupported: eligibility?.signals?.unsupported_or_contradicted_claim_count ?? record.unsupported_claim_count ?? 0,
                    inferred: eligibility?.signals?.inferred_claim_count ?? record.inferred_claim_count ?? 0,
                  },
                }}
                accentColor={actionGate?.allowed === false ? "#b91c1c" : "#9ca3af"}
                background="#fff"
                style={{ marginTop: "12px" }}
              />
              <div style={metricGridStyle}>
                <InfoItem
                  label="Project Takeaway"
                  value={formatEligibilityDecision(eligibility?.project_takeaway_candidate, {
                    allowed: "Allowed / not blocked",
                    blocked: "Blocked",
                  })}
                />
                <InfoItem
                  label="Watch"
                  value={formatEligibilityDecision(eligibility?.watch_only, {
                    allowed: "Suggested / available",
                    blocked: "Not suggested",
                  })}
                />
                <InfoItem
                  label="Action"
                  value={formatEligibilityDecision(actionGate, {
                    allowed: "Allowed / not blocked",
                    blocked: "Blocked",
                  })}
                />
                <InfoItem label="Blocked Actions" value={formatActionList(record.blocked_downstream_actions)} />
              </div>
            </section>

            <section style={panelStyle}>
              <div style={sectionTitleStyle}>Audit Trail</div>
              <div style={metricGridStyle}>
                <InfoItem label="Related Events" value={String(auditSummary?.event_count ?? relatedEvents.length)} />
                <InfoItem
                  label="Review Record Event"
                  value={(auditSummary?.matching_review_record_event_count || 0) > 0 ? "Present" : "Not returned"}
                />
                <InfoItem label="Outcome Event" value={auditSummary?.has_outcome_event ? "Present" : "Not returned"} />
              </div>
              {relatedEvents.length ? (
                <div style={eventListStyle}>
                  {relatedEvents.map((event, index) => (
                    <div key={event.id || `${event.event_type || "event"}-${index}`} style={eventItemStyle}>
                      <div style={eventHeaderStyle}>
                        <div style={eventTitleStyle}>
                          <strong>{formatLabel(event.event_type) || "Calibration Event"}</strong>
                          {event.is_current_review_record_event ? (
                            <span style={currentEventChipStyle}>Current Review Record</span>
                          ) : null}
                        </div>
                        <span style={smallLabelStyle}>{formatDateTime(event.created_at || event.updated_at)}</span>
                      </div>
                      <div style={eventMetaStyle}>
                        <span>{formatLabel(event.outcome) || "No outcome"}</span>
                        <span>{formatLabel(event.source_status) || "No source status"}</span>
                        <span>{event.review_record_id ? `Review ${event.review_record_id}` : "No linked review id"}</span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div style={mutedTextStyle}>No related calibration events were returned.</div>
              )}
            </section>

            <section style={panelStyle}>
              <div style={sectionTitleStyle}>Source Context</div>
              <div style={metricGridStyle}>
                <InfoItem label="Project" value={record.project_id || "n/a"} />
                <InfoItem label="Signal" value={record.signal_id || "n/a"} />
                <InfoItem label="Candidate Source" value={formatLabel(record.candidate_source) || "n/a"} />
                <InfoItem label="Source Status" value={formatLabel(record.source_status) || "n/a"} />
                <InfoItem label="Manual Intent" value={[record.upload_reason, record.intended_use].filter(Boolean).join(" / ") || "Not captured"} />
                <InfoItem label="Cognitive Layer" value={formatLabel(record.cognitive_layer || "unclassified")} />
              </div>
              {record.manual_project_takeaway_override ? (
                <div style={overrideStyle}>
                  <span style={smallLabelStyle}>Manual Override</span>
                  <strong>{record.manual_override_note || "Reviewer manually selected this candidate despite the system gate."}</strong>
                </div>
              ) : null}
            </section>

            <section style={panelStyle}>
              <div style={sectionTitleStyle}>Claim Support</div>
              {claimSupportRows.length ? (
                <div style={chipRowStyle}>
                  {claimSupportRows.map(([label, count]) => (
                    <span key={label} style={chipStyle}>
                      {formatLabel(label)} {count}
                    </span>
                  ))}
                </div>
              ) : (
                <div style={mutedTextStyle}>No claim-support counts were recorded.</div>
              )}
            </section>

            <section style={panelStyle}>
              <div style={sectionTitleStyle}>Open Related Surfaces</div>
              <div style={linkRowStyle}>
                {signalHref ? <Link href={signalHref} style={secondaryLinkStyle}>Open Signal Detail</Link> : null}
                {fitHref ? <Link href={fitHref} style={secondaryLinkStyle}>Open Fit Detail</Link> : null}
                {manualHref ? <Link href={manualHref} style={secondaryLinkStyle}>Open Manual Session</Link> : null}
                <Link href={trajectoryHref} style={secondaryLinkStyle}>
                  Open Trajectory
                </Link>
              </div>
            </section>
          </div>
        ) : (
          <div style={emptyStyle}>No review record returned.</div>
        )}
      </RequireAdminAuth>
    </AppContainer>
  );
}

const headerStyle = {
  border: "1px solid #e5e7eb",
  borderRadius: "8px",
  background: "#ffffff",
  padding: "18px",
  display: "flex",
  justifyContent: "space-between",
  alignItems: "flex-start",
  gap: "16px",
  flexWrap: "wrap" as const,
  marginBottom: "16px",
} as const;

const titleStyle = { margin: "4px 0 0", color: "#111827", fontSize: "24px", lineHeight: 1.2 } as const;
const descriptionStyle = { margin: "8px 0 0", color: "#4b5563", fontSize: "14px", lineHeight: 1.6, maxWidth: "760px" } as const;
const pageGridStyle = { display: "grid", gap: "14px" } as const;
const summaryStyle = { border: "1px solid #e5e7eb", borderRadius: "8px", background: "#ffffff", padding: "18px", display: "grid", gap: "14px" } as const;
const panelStyle = { ...summaryStyle } as const;
const summaryHeaderStyle = { display: "flex", justifyContent: "space-between", gap: "14px", alignItems: "flex-start", flexWrap: "wrap" as const } as const;
const recordTitleStyle = { margin: "4px 0 0", color: "#111827", fontSize: "20px", lineHeight: 1.3 } as const;
const smallLabelStyle = { color: "#6b7280", fontSize: "12px", fontWeight: 800, textTransform: "uppercase" as const } as const;
const bodyTextStyle = { margin: 0, color: "#374151", fontSize: "14px", lineHeight: 1.7 } as const;
const sectionTitleStyle = { color: "#111827", fontSize: "14px", fontWeight: 800, textTransform: "uppercase" as const } as const;
const metricGridStyle = { display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "10px" } as const;
const infoItemStyle = { border: "1px solid #e5e7eb", borderRadius: "8px", background: "#f9fafb", padding: "12px", display: "grid", gap: "6px", color: "#111827", overflowWrap: "anywhere" as const } as const;
const outcomeChipStyle = { border: "1px solid #d1d5db", borderRadius: "999px", padding: "8px 12px", color: "#111827", background: "#f9fafb", fontSize: "13px", fontWeight: 800 } as const;
const snapshotHeroStyle = { border: "1px solid #d1d5db", borderRadius: "8px", background: "#f9fafb", padding: "14px", display: "grid", gap: "6px", color: "#374151", fontSize: "14px", lineHeight: 1.6 } as const;
const boundaryStyle = { border: "1px solid #dbeafe", borderRadius: "8px", background: "#eff6ff", color: "#1e3a8a", padding: "12px", fontSize: "14px", lineHeight: 1.6, fontWeight: 700 } as const;
const overrideStyle = { border: "1px solid #fbbf24", borderRadius: "8px", background: "#fffbeb", color: "#92400e", padding: "12px", display: "grid", gap: "6px", lineHeight: 1.6 } as const;
const chipRowStyle = { display: "flex", gap: "8px", flexWrap: "wrap" as const } as const;
const chipStyle = { border: "1px solid #e5e7eb", borderRadius: "999px", padding: "7px 10px", background: "#f9fafb", color: "#111827", fontSize: "13px", fontWeight: 700 } as const;
const mutedTextStyle = { color: "#6b7280", fontSize: "14px", lineHeight: 1.6 } as const;
const eventListStyle = { display: "grid", gap: "8px" } as const;
const eventItemStyle = { border: "1px solid #e5e7eb", borderRadius: "8px", background: "#fff", padding: "12px", display: "grid", gap: "8px" } as const;
const eventHeaderStyle = { display: "flex", justifyContent: "space-between", gap: "10px", flexWrap: "wrap" as const, color: "#111827", fontSize: "14px" } as const;
const eventTitleStyle = { display: "flex", gap: "8px", alignItems: "center", flexWrap: "wrap" as const } as const;
const currentEventChipStyle = { border: "1px solid #bfdbfe", borderRadius: "999px", background: "#eff6ff", color: "#1d4ed8", padding: "4px 8px", fontSize: "12px", fontWeight: 800 } as const;
const eventMetaStyle = { display: "flex", gap: "8px", flexWrap: "wrap" as const, color: "#4b5563", fontSize: "13px", lineHeight: 1.5 } as const;
const linkRowStyle = { display: "flex", gap: "10px", flexWrap: "wrap" as const, alignItems: "center" } as const;
const primaryLinkStyle = { border: "1px solid #111827", borderRadius: "8px", background: "#111827", color: "#fff", padding: "10px 13px", textDecoration: "none", fontWeight: 800, fontSize: "14px" } as const;
const secondaryLinkStyle = { border: "1px solid #d1d5db", borderRadius: "8px", background: "#fff", color: "#111827", padding: "10px 13px", textDecoration: "none", fontWeight: 800, fontSize: "14px" } as const;
const emptyStyle = { border: "1px dashed #d1d5db", borderRadius: "8px", background: "#f9fafb", color: "#4b5563", padding: "18px", fontSize: "14px" } as const;
const errorStyle = { border: "1px solid #fecaca", borderRadius: "8px", background: "#fef2f2", color: "#991b1b", padding: "16px", display: "grid", gap: "8px", fontSize: "14px" } as const;
