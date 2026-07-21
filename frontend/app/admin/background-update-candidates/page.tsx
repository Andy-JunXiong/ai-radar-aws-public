"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import Link from "next/link";

import AppContainer from "@/components/AppContainer";
import PageHeader from "@/components/PageHeader";
import RequireAdminAuth from "@/components/RequireAdminAuth";
import SectionCard from "@/components/SectionCard";
import { apiUrl } from "@/lib/api";
import { adminFetch } from "@/lib/adminAuth";

type BackgroundUpdateCandidate = {
  id?: string;
  candidate_status?: string;
  candidate_scope?: string;
  candidate_type?: string;
  suggested_review_focus?: string;
  source_feedback_id?: string;
  source_signal_id?: string;
  source_insight_id?: string;
  source_claim_id?: string;
  source_claim_text_snapshot?: string;
  reason_slot?: string;
  distortion_tags?: string[];
  note_snapshot?: string;
  feedback_created_at?: string;
  verification_snapshot_summary?: {
    verification_status?: string;
    confidence_label?: string;
    blocked_downstream_actions?: string[];
  };
  input_freshness_summary?: {
    summary?: string;
    stale_flags?: string[];
    freshness_penalty?: number;
  };
  downstream_effect?: string;
  evidence_boundary?: string;
  review_boundary?: Record<string, boolean>;
  latest_decision?: {
    id?: string;
    decision?: string;
    note?: string;
    created_by?: string;
    created_at?: string;
    downstream_effect?: string;
    evidence_boundary?: string;
  } | null;
};

type CandidateQueueResponse = {
  queue_type?: string;
  candidate_status?: string;
  evidence_boundary?: string;
  allowed_reason_slots?: string[];
  records?: BackgroundUpdateCandidate[];
  count?: number;
  message?: string;
};

type SignalReviewFeedbackRecord = {
  id?: string;
  signal_id?: string;
  insight_id?: string;
  claim_id?: string;
  claim_text_snapshot?: string;
  reason_slot?: string;
  distortion_tags?: string[];
  note?: string;
  verification_snapshot?: Record<string, unknown>;
  input_provenance_snapshot?: Record<string, unknown>;
  created_at?: string;
  updated_at?: string;
};

type SignalReviewFeedbackResponse = {
  records?: SignalReviewFeedbackRecord[];
  count?: number;
};

const DEFAULT_LIMIT = 25;

export default function BackgroundUpdateCandidatesPage() {
  const [signalId, setSignalId] = useState("");
  const [reasonSlot, setReasonSlot] = useState("");
  const [limit, setLimit] = useState(DEFAULT_LIMIT);
  const [queue, setQueue] = useState<CandidateQueueResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [decisionInFlight, setDecisionInFlight] = useState<Record<string, string>>({});

  const candidates = queue?.records || [];
  const querySummary = useMemo(() => {
    const parts = [
      signalId.trim() ? `signal_id=${signalId.trim()}` : "all signals",
      reasonSlot || "not_me + blind_spot",
      `limit=${limit}`,
    ];
    return parts.join(" / ");
  }, [limit, reasonSlot, signalId]);

  async function loadQueue() {
    setLoading(true);
    setError("");

    const params = new URLSearchParams();
    if (signalId.trim()) params.set("signal_id", signalId.trim());
    if (reasonSlot) params.set("reason_slot", reasonSlot);
    params.set("limit", String(limit));

    try {
      const response = await adminFetch(
        apiUrl(`/signal-review-feedback/background-update-candidates?${params.toString()}`),
        { cache: "no-store" },
      );
      if (!response.ok) {
        if (response.status === 404) {
          const fallbackQueue = await loadQueueFromFeedbackRecords(params);
          setQueue(fallbackQueue);
          return;
        }
        throw new Error(`Background update candidate queue failed with HTTP ${response.status}`);
      }
      setQueue((await response.json()) as CandidateQueueResponse);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Background update candidate queue could not load.");
      setQueue(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadQueue();
    // Initial load should use the default query only.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void loadQueue();
  }

  async function recordCandidateDecision(candidate: BackgroundUpdateCandidate, decision: "confirmed" | "dismissed") {
    const candidateId = candidate.id || "";
    if (!candidateId) {
      setError("Candidate decision could not be recorded because the candidate ID is missing.");
      return;
    }

    setDecisionInFlight((current) => ({ ...current, [candidateId]: decision }));
    setError("");

    try {
      const response = await adminFetch(
        apiUrl(`/signal-review-feedback/background-update-candidates/${encodeURIComponent(candidateId)}/decision`),
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            decision,
            note:
              decision === "confirmed"
                ? "Confirmed for future background-context review; no active context mutation performed."
                : "Dismissed from the background update candidate queue; no active context mutation performed.",
          }),
        },
      );
      if (!response.ok) {
        throw new Error(`Candidate decision failed with HTTP ${response.status}`);
      }
      await loadQueue();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Candidate decision could not be recorded.");
    } finally {
      setDecisionInFlight((current) => {
        const next = { ...current };
        delete next[candidateId];
        return next;
      });
    }
  }

  return (
    <AppContainer>
      <RequireAdminAuth>
        <PageHeader
          title="Background Update Queue"
          description="Inactive candidates from Signal claim feedback. This page does not apply background updates or change verification gates."
          size="compact"
        />

        <SectionCard title="Boundary">
          <div style={boundaryGridStyle}>
            <BoundaryCard label="Queue" value={formatQueueType(queue?.queue_type)} />
            <BoundaryCard label="Status" value={formatMachineLabel(queue?.candidate_status || "inactive_review_only")} />
            <BoundaryCard label="Evidence Boundary" value={formatEvidenceBoundary(queue?.evidence_boundary)} />
            <BoundaryCard label="Reason Slots" value={formatReasonSlots(queue?.allowed_reason_slots || ["not_me", "blind_spot"])} />
            <BoundaryCard label="Candidates" value={String(queue?.count ?? candidates.length)} />
          </div>
          {queue?.message ? <div style={queueMessageStyle}>{queue.message}</div> : null}
        </SectionCard>

        <SectionCard title="Query">
          <form onSubmit={handleSubmit} style={queryFormStyle}>
            <label style={fieldStyle}>
              <span style={fieldLabelStyle}>Signal ID</span>
              <input
                value={signalId}
                onChange={(event) => setSignalId(event.target.value)}
                placeholder="optional"
                style={inputStyle}
              />
            </label>
            <label style={fieldStyle}>
              <span style={fieldLabelStyle}>Reason Slot</span>
              <select value={reasonSlot} onChange={(event) => setReasonSlot(event.target.value)} style={inputStyle}>
                <option value="">not_me + blind_spot</option>
                <option value="not_me">not_me</option>
                <option value="blind_spot">blind_spot</option>
              </select>
            </label>
            <label style={fieldStyle}>
              <span style={fieldLabelStyle}>Limit</span>
              <input
                type="number"
                min={1}
                max={100}
                value={limit}
                onChange={(event) => setLimit(Math.max(1, Math.min(100, Number(event.target.value) || DEFAULT_LIMIT)))}
                style={inputStyle}
              />
            </label>
            <button type="submit" style={primaryButtonStyle} disabled={loading}>
              {loading ? "Loading" : "Load Queue"}
            </button>
          </form>
          <div style={querySummaryStyle}>{querySummary}</div>
        </SectionCard>

        <SectionCard title="Candidate Queue">
          {error ? <div style={errorStyle}>{error}</div> : null}
          {loading ? <div style={mutedStyle}>Loading background update candidates...</div> : null}
          {!loading && !error && candidates.length === 0 ? (
            <div style={emptyStyle}>No inactive background update candidates matched this query.</div>
          ) : null}
          <div style={candidateListStyle}>
            {candidates.map((candidate, index) => (
              <article key={candidate.id || `${candidate.source_feedback_id || "candidate"}-${index}`} style={candidateCardStyle}>
                <div style={candidateHeaderStyle}>
                  <div>
                    <div style={eyebrowStyle}>{formatReasonSlot(candidate.reason_slot)} candidate</div>
                    <h2 style={candidateTitleStyle}>{formatMachineLabel(candidate.candidate_type || "background update candidate")}</h2>
                  </div>
                  <span style={statusBadgeStyle}>{formatMachineLabel(candidate.candidate_status || "inactive")}</span>
                </div>

                <p style={focusStyle}>{candidate.suggested_review_focus || "Review this candidate before any future background update."}</p>

                {candidate.note_snapshot ? (
                  <div style={noteStyle}>
                    <strong>Feedback note:</strong> {candidate.note_snapshot}
                  </div>
                ) : null}

                {candidate.source_claim_text_snapshot ? (
                  <div style={claimStyle}>{candidate.source_claim_text_snapshot}</div>
                ) : null}

                <div style={metaGridStyle}>
                  <Meta label="Signal" value={candidate.source_signal_id || "unknown"} />
                  <Meta label="Claim" value={candidate.source_claim_id || "unknown"} />
                  <Meta label="Feedback" value={candidate.source_feedback_id || "unknown"} />
                  <Meta label="Verification" value={candidate.verification_snapshot_summary?.verification_status || "unknown"} />
                  <Meta label="Confidence" value={candidate.verification_snapshot_summary?.confidence_label || "unknown"} />
                  <Meta label="Downstream Effect" value={formatMachineLabel(candidate.downstream_effect || "candidate_only")} />
                </div>

                {candidate.input_freshness_summary?.summary || candidate.input_freshness_summary?.stale_flags?.length ? (
                  <div style={freshnessStyle}>
                    <strong>Input freshness:</strong>{" "}
                    {candidate.input_freshness_summary.summary || "No freshness summary."}
                    {candidate.input_freshness_summary.stale_flags?.length ? (
                      <div style={chipRowStyle}>
                        {candidate.input_freshness_summary.stale_flags.map((flag) => (
                          <span key={flag} style={chipStyle}>{flag}</span>
                        ))}
                      </div>
                    ) : null}
                  </div>
                ) : null}

                {candidate.verification_snapshot_summary?.blocked_downstream_actions?.length ? (
                  <div style={chipRowStyle}>
                    {candidate.verification_snapshot_summary.blocked_downstream_actions.map((action) => (
                      <span key={action} style={chipStyle}>{action}</span>
                    ))}
                  </div>
                ) : null}

                <div style={boundaryListStyle}>
                  <BoundaryFlag label="Requires confirmation" value={candidate.review_boundary?.requires_explicit_confirmation} />
                  <BoundaryFlag label="Mutates context" value={candidate.review_boundary?.mutates_context} />
                  <BoundaryFlag label="Mutates verification" value={candidate.review_boundary?.mutates_verification_status} />
                  <BoundaryFlag label="Mutates action gate" value={candidate.review_boundary?.mutates_action_gate} />
                  <BoundaryFlag label="External claim evidence" value={candidate.review_boundary?.external_claim_evidence} />
                </div>

                <DecisionLedger decision={candidate.latest_decision} />

                <div style={linkRowStyle}>
                  {candidate.source_signal_id ? (
                    <Link href={`/signals/detail?id=${encodeURIComponent(candidate.source_signal_id)}`} style={secondaryLinkStyle}>
                      Open Signal
                    </Link>
                  ) : null}
                  <button
                    type="button"
                    style={primaryButtonStyle}
                    disabled={!!decisionInFlight[candidate.id || ""]}
                    onClick={() => void recordCandidateDecision(candidate, "confirmed")}
                  >
                    {decisionInFlight[candidate.id || ""] === "confirmed" ? "Confirming" : "Confirm"}
                  </button>
                  <button
                    type="button"
                    style={secondaryButtonStyle}
                    disabled={!!decisionInFlight[candidate.id || ""]}
                    onClick={() => void recordCandidateDecision(candidate, "dismissed")}
                  >
                    {decisionInFlight[candidate.id || ""] === "dismissed" ? "Dismissing" : "Dismiss"}
                  </button>
                </div>
              </article>
            ))}
          </div>
        </SectionCard>
      </RequireAdminAuth>
    </AppContainer>
  );
}

function BoundaryCard({ label, value }: { label: string; value: string }) {
  return (
    <div style={boundaryCardStyle}>
      <div style={eyebrowStyle}>{label}</div>
      <div style={boundaryValueStyle} title={value}>{value}</div>
    </div>
  );
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div style={metaItemStyle}>
      <span style={metaLabelStyle}>{label}</span>
      <strong style={metaValueStyle}>{value}</strong>
    </div>
  );
}

function BoundaryFlag({ label, value }: { label: string; value?: boolean }) {
  return (
    <div style={flagStyle}>
      <span>{label}</span>
      <strong>{value ? "yes" : "no"}</strong>
    </div>
  );
}

function DecisionLedger({ decision }: { decision?: BackgroundUpdateCandidate["latest_decision"] }) {
  if (!decision) {
    return (
      <div style={decisionLedgerStyle}>
        <strong>No decision recorded</strong>
        <span>Confirm or dismiss records a ledger decision only. It does not apply a background update.</span>
      </div>
    );
  }

  return (
    <div style={decisionLedgerStyle}>
      <strong>Latest decision: {formatMachineLabel(decision.decision || "unknown")}</strong>
      <span>
        {decision.created_at || "unknown time"} / {formatMachineLabel(decision.downstream_effect || "decision_record_only")}
      </span>
      {decision.note ? <span>{decision.note}</span> : null}
    </div>
  );
}

async function loadQueueFromFeedbackRecords(params: URLSearchParams): Promise<CandidateQueueResponse> {
  const fallbackParams = new URLSearchParams();
  const signalId = params.get("signal_id");
  const reasonSlot = params.get("reason_slot");
  const limit = Number(params.get("limit") || DEFAULT_LIMIT);
  if (signalId) fallbackParams.set("signal_id", signalId);
  if (reasonSlot) fallbackParams.set("reason_slot", reasonSlot);

  const response = await adminFetch(
    apiUrl(`/signal-review-feedback?${fallbackParams.toString()}`),
    { cache: "no-store" },
  );
  if (!response.ok) {
    throw new Error(`Background update candidate queue failed with HTTP 404 and feedback fallback failed with HTTP ${response.status}`);
  }

  const payload = (await response.json()) as SignalReviewFeedbackResponse;
  const records = Array.isArray(payload.records) ? payload.records : [];
  const candidates = records
    .map(buildCandidateFromFeedbackRecord)
    .filter((candidate): candidate is BackgroundUpdateCandidate => !!candidate)
    .slice(0, Math.max(1, Math.min(100, Number.isFinite(limit) ? limit : DEFAULT_LIMIT)));

  return {
    queue_type: "background_update_candidate_queue",
    candidate_status: "inactive_review_only",
    evidence_boundary: "not_external_claim_evidence",
    allowed_reason_slots: ["not_me", "blind_spot"],
    records: candidates,
    count: candidates.length,
    message: "Using feedback-list fallback because the backend queue endpoint is not loaded in the current API process.",
  };
}

function buildCandidateFromFeedbackRecord(record: SignalReviewFeedbackRecord): BackgroundUpdateCandidate | null {
  const reasonSlot = String(record.reason_slot || "").trim().toLowerCase();
  if (reasonSlot !== "not_me" && reasonSlot !== "blind_spot") return null;

  const verificationSnapshot = isRecord(record.verification_snapshot) ? record.verification_snapshot : {};
  const inputProvenance = isRecord(record.input_provenance_snapshot) ? record.input_provenance_snapshot : {};
  const freshness = isRecord(inputProvenance.freshness) ? inputProvenance.freshness : {};

  return {
    id: `buc_${String(record.id || "").replace(/^srf_/, "")}`,
    candidate_status: "inactive_review_only",
    candidate_scope: "user_or_system_understanding_context",
    candidate_type: reasonSlot === "not_me" ? "user_context_alignment" : "user_attention_calibration",
    suggested_review_focus:
      reasonSlot === "not_me"
        ? "Review whether AI Radar's understanding of the user's priorities or project context is stale or mismatched."
        : "Review whether this feedback should become user-confirmed attention or interpretation context.",
    source_feedback_id: record.id || "",
    source_signal_id: record.signal_id || "",
    source_insight_id: record.insight_id || "",
    source_claim_id: record.claim_id || "",
    source_claim_text_snapshot: record.claim_text_snapshot || "",
    reason_slot: reasonSlot,
    distortion_tags: Array.isArray(record.distortion_tags) ? record.distortion_tags : [],
    note_snapshot: record.note || "",
    feedback_created_at: record.created_at || "",
    verification_snapshot_summary: {
      verification_status: safeString(verificationSnapshot.verification_status),
      confidence_label: safeString(verificationSnapshot.confidence_label),
      blocked_downstream_actions: cleanStringList(verificationSnapshot.blocked_downstream_actions),
    },
    input_freshness_summary: {
      summary: safeString(freshness.summary),
      stale_flags: cleanStringList(freshness.stale_flags),
      freshness_penalty: typeof freshness.freshness_penalty === "number" ? freshness.freshness_penalty : 0,
    },
    downstream_effect: "candidate_only",
    evidence_boundary: "not_external_claim_evidence",
    review_boundary: {
      requires_explicit_confirmation: true,
      mutates_context: false,
      mutates_verification_status: false,
      mutates_project_takeaway_gate: false,
      mutates_action_gate: false,
      external_claim_evidence: false,
    },
    latest_decision: null,
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === "object" && !Array.isArray(value);
}

function safeString(value: unknown): string {
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return "";
}

function cleanStringList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.map(safeString).filter(Boolean);
}

function formatQueueType(value?: string) {
  if (value === "background_update_candidate_queue" || !value) return "Candidate queue";
  return formatMachineLabel(value);
}

function formatEvidenceBoundary(value?: string) {
  if (value === "not_external_claim_evidence" || !value) return "Not external evidence";
  return formatMachineLabel(value);
}

function formatReasonSlots(values: string[]) {
  return values.map(formatReasonSlot).join(", ");
}

function formatReasonSlot(value?: string) {
  if (value === "not_me") return "not me";
  if (value === "blind_spot") return "blind spot";
  return formatMachineLabel(value || "reason");
}

function formatMachineLabel(value: string) {
  return value.replace(/_/g, " ");
}

const boundaryGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))",
  gap: "12px",
} as const;

const boundaryCardStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  padding: "14px",
  background: "var(--app-surface-muted-bg)",
} as const;

const boundaryValueStyle = {
  marginTop: "7px",
  fontSize: "15px",
  fontWeight: 800,
  color: "var(--app-text-strong)",
  lineHeight: 1.35,
  overflowWrap: "normal",
} as const;

const queueMessageStyle = {
  marginTop: "12px",
  border: "1px solid var(--app-info-border)",
  borderRadius: "8px",
  padding: "9px 10px",
  background: "var(--app-info-bg)",
  color: "var(--app-info-fg)",
  fontSize: "12px",
  lineHeight: 1.45,
} as const;

const queryFormStyle = {
  display: "grid",
  gridTemplateColumns: "minmax(220px, 1.4fr) minmax(180px, 1fr) minmax(110px, 0.5fr) auto",
  alignItems: "end",
  gap: "12px",
} as const;

const fieldStyle = {
  display: "grid",
  gap: "6px",
} as const;

const fieldLabelStyle = {
  fontSize: "12px",
  fontWeight: 800,
  color: "var(--app-text-muted)",
} as const;

const inputStyle = {
  width: "100%",
  border: "1px solid var(--app-input-border)",
  borderRadius: "8px",
  padding: "10px 12px",
  fontSize: "14px",
  background: "var(--app-input-bg)",
  color: "var(--app-text-strong)",
} as const;

const primaryButtonStyle = {
  width: "fit-content",
  minWidth: "118px",
  border: "1px solid var(--app-info-border)",
  borderRadius: "8px",
  padding: "10px 14px",
  background: "var(--app-info-bg)",
  color: "var(--app-info-fg)",
  fontSize: "14px",
  fontWeight: 800,
  cursor: "pointer",
} as const;

const secondaryButtonStyle = {
  width: "fit-content",
  minWidth: "98px",
  border: "1px solid var(--app-surface-strong-border)",
  borderRadius: "8px",
  padding: "10px 14px",
  background: "var(--app-surface-bg)",
  color: "var(--app-text-strong)",
  fontSize: "14px",
  fontWeight: 800,
  cursor: "pointer",
} as const;

const querySummaryStyle = {
  marginTop: "10px",
  color: "var(--app-text-muted)",
  fontSize: "13px",
} as const;

const candidateListStyle = {
  display: "grid",
  gap: "12px",
} as const;

const candidateCardStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  padding: "16px",
  background: "var(--app-surface-bg)",
  display: "grid",
  gap: "12px",
} as const;

const candidateHeaderStyle = {
  display: "flex",
  justifyContent: "space-between",
  gap: "12px",
  alignItems: "flex-start",
} as const;

const eyebrowStyle = {
  fontSize: "12px",
  fontWeight: 800,
  color: "var(--app-text-subtle)",
  textTransform: "uppercase",
  letterSpacing: 0,
} as const;

const candidateTitleStyle = {
  margin: "4px 0 0",
  fontSize: "20px",
  fontWeight: 850,
  color: "var(--app-text-strong)",
  letterSpacing: 0,
  lineHeight: 1.25,
} as const;

const statusBadgeStyle = {
  border: "1px solid var(--app-info-border)",
  borderRadius: "999px",
  padding: "5px 9px",
  background: "var(--app-info-bg)",
  color: "var(--app-info-fg)",
  fontSize: "12px",
  fontWeight: 800,
  whiteSpace: "nowrap",
} as const;

const focusStyle = {
  margin: 0,
  color: "var(--app-text-muted)",
  fontSize: "14px",
  lineHeight: 1.55,
} as const;

const noteStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  padding: "10px",
  background: "var(--app-surface-muted-bg)",
  color: "var(--app-text-muted)",
  fontSize: "13px",
  lineHeight: 1.55,
} as const;

const claimStyle = {
  borderLeft: "3px solid var(--app-warning-border)",
  padding: "8px 10px",
  background: "var(--app-warning-bg)",
  color: "var(--app-warning-fg)",
  fontSize: "13px",
  lineHeight: 1.55,
} as const;

const metaGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
  gap: "8px",
} as const;

const metaItemStyle = {
  display: "grid",
  gap: "4px",
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  padding: "10px",
  background: "var(--app-surface-soft-bg)",
} as const;

const metaLabelStyle = {
  color: "var(--app-text-subtle)",
  fontSize: "11px",
  fontWeight: 800,
  textTransform: "uppercase",
  letterSpacing: 0,
} as const;

const metaValueStyle = {
  color: "var(--app-text-strong)",
  fontSize: "13px",
  overflowWrap: "anywhere",
} as const;

const freshnessStyle = {
  color: "var(--app-text-muted)",
  fontSize: "13px",
  lineHeight: 1.55,
} as const;

const chipRowStyle = {
  display: "flex",
  flexWrap: "wrap",
  gap: "6px",
  marginTop: "8px",
} as const;

const chipStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "999px",
  padding: "4px 8px",
  background: "var(--app-surface-muted-bg)",
  color: "var(--app-text-muted)",
  fontSize: "12px",
  fontWeight: 700,
} as const;

const boundaryListStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
  gap: "8px",
} as const;

const decisionLedgerStyle = {
  border: "1px solid var(--app-info-border)",
  borderRadius: "8px",
  padding: "10px",
  background: "var(--app-info-bg)",
  color: "var(--app-info-fg)",
  fontSize: "13px",
  lineHeight: 1.5,
  display: "grid",
  gap: "4px",
} as const;

const flagStyle = {
  display: "flex",
  justifyContent: "space-between",
  gap: "8px",
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  padding: "8px 10px",
  background: "var(--app-surface-muted-bg)",
  color: "var(--app-text-muted)",
  fontSize: "12px",
} as const;

const linkRowStyle = {
  display: "flex",
  flexWrap: "wrap",
  gap: "8px",
} as const;

const secondaryLinkStyle = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  border: "1px solid var(--app-surface-strong-border)",
  borderRadius: "8px",
  padding: "8px 10px",
  color: "var(--app-text-strong)",
  background: "var(--app-surface-bg)",
  textDecoration: "none",
  fontSize: "13px",
  fontWeight: 800,
} as const;

const errorStyle = {
  border: "1px solid var(--app-danger-border)",
  borderRadius: "8px",
  padding: "10px",
  background: "var(--app-danger-bg)",
  color: "var(--app-danger-fg)",
  fontSize: "13px",
} as const;

const mutedStyle = {
  color: "var(--app-text-muted)",
  fontSize: "14px",
} as const;

const emptyStyle = {
  border: "1px dashed var(--app-surface-strong-border)",
  borderRadius: "8px",
  padding: "14px",
  color: "var(--app-text-muted)",
  background: "var(--app-surface-soft-bg)",
  fontSize: "14px",
} as const;
