"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import AppContainer from "@/components/AppContainer";
import PageHeader from "@/components/PageHeader";
import RequireAdminAuth from "@/components/RequireAdminAuth";
import VerificationGateNote from "@/components/VerificationGateNote";
import { apiUrl } from "@/lib/api";
import { adminFetch } from "@/lib/adminAuth";

type ProjectItem = {
  project_id?: string;
  name?: string;
  description?: string;
  status?: string;
};

type ProjectImprovementItem = {
  signal_id?: string;
  project_id?: string;
  signal_title?: string;
  signal_summary?: string;
  takeaway?: string;
  source_takeaway?: string;
  why_it_matters?: string;
  fit_reason?: string;
  benefits?: string;
  final_reflection?: string;
  status?: string;
  suggested_stage?: string;
  readme_update_suggestion?: string;
  roadmap_update_suggestion?: string;
  score?: number;
  should_apply?: boolean;
  saved_at?: string;
  confirmed_at?: string;
  verification_metadata?: {
    review_priority?: string;
    verification_status?: string;
    confidence_label?: string;
    confidence_score?: number;
    allowed_downstream_actions?: string[];
    blocked_downstream_actions?: string[];
    claim_support_summary?: Record<string, number>;
    manual_project_takeaway_override?: boolean;
    manual_override_note?: string;
    manual_override_expected_outcome?: string;
  };
};

type DetailResponse = {
  project?: ProjectItem;
  item?: ProjectImprovementItem;
  detail?: string;
};

type ConfirmResponse = {
  item?: ProjectImprovementItem;
  detail?: string;
};

function formatScore(value?: number) {
  if (typeof value !== "number" || Number.isNaN(value)) return "n/a";
  return `${Math.max(0, Math.min(100, Math.round(value)))}/100`;
}

function formatLabel(value?: string) {
  return (value || "unknown")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function formatDate(value?: string) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

function TextBlock({ title, value, fallback }: { title: string; value?: string; fallback?: string }) {
  return (
    <section style={sectionStyle}>
      <div style={sectionTitleStyle}>{title}</div>
      <div style={bodyTextStyle}>{value?.trim() || fallback || "Not available."}</div>
    </section>
  );
}

export default function ProjectImprovementDetailPage() {
  const searchParams = useSearchParams();
  const projectId = searchParams.get("project_id") || "";
  const signalId = searchParams.get("signal_id") || "";

  const [project, setProject] = useState<ProjectItem | null>(null);
  const [improvement, setImprovement] = useState<ProjectImprovementItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState("");
  const [confirming, setConfirming] = useState(false);
  const [overrideConfirming, setOverrideConfirming] = useState(false);
  const [overrideNote, setOverrideNote] = useState("");
  const [overrideExpectedOutcome, setOverrideExpectedOutcome] = useState("");
  const [actionMessage, setActionMessage] = useState("");

  useEffect(() => {
    const controller = new AbortController();

    async function loadDetail() {
      setLoading(true);
      setErrorMessage("");
      try {
        const response = await fetch(
          apiUrl(`/projects/${encodeURIComponent(projectId)}/improvements/${encodeURIComponent(signalId)}`),
          { cache: "no-store", signal: controller.signal }
        );
        const data = (await response.json().catch(() => null)) as DetailResponse | null;
        if (!response.ok) {
          throw new Error(data?.detail || `Failed to load improvement detail (${response.status})`);
        }
        setProject(data?.project || null);
        setImprovement(data?.item || null);
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setProject(null);
        setImprovement(null);
        setErrorMessage(error instanceof Error ? error.message : "Failed to load improvement detail.");
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }

    void loadDetail();
    return () => controller.abort();
  }, [projectId, signalId]);

  async function handleConfirm() {
    if (!improvement?.signal_id) return;

    setConfirming(true);
    setErrorMessage("");
    setActionMessage("");

    try {
      const response = await adminFetch(
        apiUrl(`/projects/${encodeURIComponent(projectId)}/improvements/${encodeURIComponent(improvement.signal_id)}/confirm`),
        { method: "POST" }
      );
      const data = (await response.json().catch(() => null)) as ConfirmResponse | null;
      if (!response.ok) {
        throw new Error(data?.detail || `Failed to confirm improvement (${response.status})`);
      }

      setImprovement((current) => ({ ...(current || {}), ...(data?.item || {}), status: "confirmed" }));
      setActionMessage("Confirmed. This improvement is now accepted for this project.");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to confirm improvement.");
    } finally {
      setConfirming(false);
    }
  }

  async function handleOverrideConfirm() {
    if (!improvement?.signal_id) return;
    const note = overrideNote.trim();
    const expectedOutcome = overrideExpectedOutcome.trim();
    if (!note || !expectedOutcome) {
      setErrorMessage("Override Confirm requires a manual override note and expected outcome.");
      return;
    }

    setOverrideConfirming(true);
    setErrorMessage("");
    setActionMessage("");

    try {
      const response = await adminFetch(
        apiUrl(`/projects/${encodeURIComponent(projectId)}/improvements/${encodeURIComponent(improvement.signal_id)}/override-confirm`),
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            reason: note,
            expected_outcome: expectedOutcome,
          }),
        }
      );
      const data = (await response.json().catch(() => null)) as ConfirmResponse | null;
      if (!response.ok) {
        throw new Error(data?.detail || `Failed to override-confirm improvement (${response.status})`);
      }

      setImprovement((current) => ({ ...(current || {}), ...(data?.item || {}), status: "confirmed" }));
      setOverrideNote("");
      setOverrideExpectedOutcome("");
      setActionMessage("Override confirmed. This decision was recorded with an audit note and expected outcome.");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to override-confirm improvement.");
    } finally {
      setOverrideConfirming(false);
    }
  }

  const verification = improvement?.verification_metadata || {};
  const normalizedStatus = (improvement?.status || "").toLowerCase();
  const reviewClosedStatuses = new Set(["confirmed", "action", "action_completed", "watch", "rejected", "dismissed"]);
  const canReviewProjectTakeaway = !reviewClosedStatuses.has(normalizedStatus);
  const blockedActions = verification.blocked_downstream_actions || [];
  const claimSupport = verification.claim_support_summary || {};
  const unsupportedOrContradictedCount =
    Number(claimSupport.unsupported || 0) + Number(claimSupport.contradicted || 0);
  const verificationStatus = (verification.verification_status || "").toLowerCase();
  const projectTakeawayBlocked =
    blockedActions.includes("project_takeaway_candidate") ||
    ["unsupported", "contradicted", "not_verifiable"].includes(verificationStatus) ||
    unsupportedOrContradictedCount > 0;

  return (
    <AppContainer>
      <RequireAdminAuth>
        <PageHeader
          title="Project Improvement Detail"
          description="Review the project fit, evidence status, and suggested project takeaway before or after confirmation."
        />

        <div style={toolbarStyle}>
          <Link href="/workspace/projects" style={primaryNavLinkStyle}>
            Back to Project Takeaways
          </Link>
          <Link href="/workspace/projects/review" style={navLinkStyle}>
            Review Inbox
          </Link>
          <Link href={`/signals/detail?id=${encodeURIComponent(signalId)}`} style={navLinkStyle}>
            Open Signal
          </Link>
        </div>

        {loading ? <div style={{ color: "#6b7280" }}>Loading improvement detail...</div> : null}
        {errorMessage ? <div style={errorStyle}>{errorMessage}</div> : null}
        {actionMessage ? <div style={successStyle}>{actionMessage}</div> : null}

        {!loading && improvement ? (
          <div style={{ display: "grid", gap: "16px" }}>
            <section style={heroStyle}>
              <div>
                <div style={metaStyle}>{project?.name || improvement.project_id || projectId}</div>
                <h2 style={{ margin: "6px 0 0", fontSize: "28px", lineHeight: "1.2", color: "#111827" }}>
                  {improvement.signal_title || "Untitled signal"}
                </h2>
              </div>
              <div style={{ fontSize: "30px", fontWeight: 900, color: "#111827", whiteSpace: "nowrap" }}>
                {formatScore(improvement.score)}
              </div>
            </section>

            <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
              <span style={chipStyle}>Status: {formatLabel(improvement.status)}</span>
              {improvement.suggested_stage ? <span style={chipStyle}>Stage: {improvement.suggested_stage}</span> : null}
              {verification.review_priority ? <span style={chipStyle}>Review: {verification.review_priority}</span> : null}
              {verification.confidence_label ? (
                <span style={chipStyle}>
                  Confidence: {formatLabel(verification.confidence_label)}
                  {typeof verification.confidence_score === "number" ? ` (${verification.confidence_score.toFixed(2)})` : ""}
                </span>
              ) : null}
              {improvement.saved_at ? <span style={chipStyle}>Saved: {formatDate(improvement.saved_at)}</span> : null}
              {improvement.confirmed_at ? <span style={chipStyle}>Confirmed: {formatDate(improvement.confirmed_at)}</span> : null}
            </div>

            <VerificationGateNote
              verification={{
                verification_status: verification.verification_status || "",
                allowed_downstream_actions: verification.allowed_downstream_actions || [],
                blocked_downstream_actions: verification.blocked_downstream_actions || [],
                claim_support_summary: verification.claim_support_summary || {},
              }}
            />

            {canReviewProjectTakeaway ? (
              <div style={actionPanelStyle}>
                {!projectTakeawayBlocked ? (
                  <button
                    type="button"
                    onClick={() => void handleConfirm()}
                    disabled={confirming}
                    style={primaryButtonStyle}
                  >
                    {confirming ? "Confirming..." : "Confirm Project Takeaway"}
                  </button>
                ) : null}
                {projectTakeawayBlocked ? (
                  <details style={overrideDetailsStyle}>
                    <summary style={overrideSummaryStyle}>Override Confirm</summary>
                    <div style={overridePanelStyle}>
                      <div style={overrideWarningStyle}>
                        Use this only when a human reviewer accepts the verification risk. The note and expected outcome are saved for later calibration.
                      </div>
                      <label style={fieldLabelStyle}>
                        Manual override note
                        <textarea
                          value={overrideNote}
                          onChange={(event) => setOverrideNote(event.target.value)}
                          rows={3}
                          placeholder="Explain why this should be confirmed despite the gate"
                          style={textareaStyle}
                        />
                      </label>
                      <label style={fieldLabelStyle}>
                        Expected outcome
                        <textarea
                          value={overrideExpectedOutcome}
                          onChange={(event) => setOverrideExpectedOutcome(event.target.value)}
                          rows={3}
                          placeholder="State the expected project value so the override can be reviewed later"
                          style={textareaStyle}
                        />
                      </label>
                      <button
                        type="button"
                        onClick={() => void handleOverrideConfirm()}
                        disabled={overrideConfirming}
                        style={dangerButtonStyle}
                      >
                        {overrideConfirming ? "Override Confirming..." : "Override Confirm"}
                      </button>
                    </div>
                  </details>
                ) : null}
              </div>
            ) : null}

            <TextBlock title="Signal Summary" value={improvement.signal_summary} />
            <TextBlock title="Project Takeaway" value={improvement.takeaway || improvement.source_takeaway} />
            <TextBlock title="Fit Reason" value={improvement.fit_reason} />
            <TextBlock title="Benefits" value={improvement.benefits} />
            <TextBlock title="Roadmap Update Suggestion" value={improvement.roadmap_update_suggestion} />
            <TextBlock title="README Update Suggestion" value={improvement.readme_update_suggestion} />
            <TextBlock title="Final Reflection" value={improvement.final_reflection} fallback="No completion note was attached." />
          </div>
        ) : null}
      </RequireAdminAuth>
    </AppContainer>
  );
}

const toolbarStyle = {
  marginBottom: "20px",
  display: "flex",
  gap: "12px",
  flexWrap: "wrap" as const,
  border: "1px solid #e5e7eb",
  borderRadius: "20px",
  background: "#ffffff",
  padding: "16px 18px",
  boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
} as const;

const navLinkStyle = {
  textDecoration: "none",
  color: "#111827",
  fontSize: "14px",
  fontWeight: 800,
  border: "1px solid #d1d5db",
  borderRadius: "8px",
  background: "#ffffff",
  padding: "10px 14px",
} as const;

const primaryNavLinkStyle = {
  ...navLinkStyle,
  border: "1px solid #111827",
  background: "#111827",
  color: "#ffffff",
} as const;

const heroStyle = {
  border: "1px solid #e5e7eb",
  borderRadius: "20px",
  background: "#ffffff",
  padding: "18px",
  display: "flex",
  justifyContent: "space-between",
  gap: "18px",
  alignItems: "start",
  boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
} as const;

const sectionStyle = {
  border: "1px solid #e5e7eb",
  borderRadius: "8px",
  background: "#ffffff",
  padding: "16px",
} as const;

const actionPanelStyle = {
  border: "1px solid #e5e7eb",
  borderRadius: "20px",
  background: "#ffffff",
  padding: "16px 18px",
  boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
  display: "grid",
  gap: "12px",
} as const;

const overrideDetailsStyle = {
  border: "1px solid #fecaca",
  borderRadius: "8px",
  background: "#fff7f7",
  padding: "10px 12px",
} as const;

const overrideSummaryStyle = {
  cursor: "pointer",
  color: "#991b1b",
  fontSize: "13px",
  fontWeight: 900,
} as const;

const overridePanelStyle = {
  marginTop: "10px",
  display: "grid",
  gap: "10px",
} as const;

const overrideWarningStyle = {
  border: "1px solid #fecaca",
  borderRadius: "8px",
  background: "#fff1f2",
  color: "#991b1b",
  padding: "10px 12px",
  fontSize: "13px",
  fontWeight: 800,
  lineHeight: "1.45",
} as const;

const fieldLabelStyle = {
  display: "grid",
  gap: "6px",
  color: "#374151",
  fontSize: "12px",
  fontWeight: 900,
  textTransform: "uppercase" as const,
  letterSpacing: "0.4px",
} as const;

const textareaStyle = {
  width: "100%",
  border: "1px solid #d1d5db",
  borderRadius: "8px",
  padding: "10px 12px",
  fontSize: "14px",
  lineHeight: "1.5",
  color: "#111827",
  background: "#ffffff",
  resize: "vertical" as const,
  boxSizing: "border-box" as const,
  fontWeight: 500,
  letterSpacing: "0",
  textTransform: "none" as const,
} as const;

const sectionTitleStyle = {
  fontSize: "13px",
  color: "#475569",
  fontWeight: 900,
  textTransform: "uppercase" as const,
  letterSpacing: "0.4px",
} as const;

const bodyTextStyle = {
  marginTop: "8px",
  whiteSpace: "pre-wrap" as const,
  fontSize: "14px",
  lineHeight: "1.75",
  color: "#334155",
} as const;

const metaStyle = {
  fontSize: "12px",
  color: "#64748b",
  fontWeight: 900,
  textTransform: "uppercase" as const,
  letterSpacing: "0.4px",
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
  fontWeight: 700,
} as const;

const primaryButtonStyle = {
  padding: "10px 14px",
  borderRadius: "10px",
  border: "1px solid #111827",
  background: "#111827",
  color: "#ffffff",
  cursor: "pointer",
  fontWeight: 800,
} as const;

const dangerButtonStyle = {
  padding: "10px 14px",
  borderRadius: "10px",
  border: "1px solid #fecaca",
  background: "#fff1f2",
  color: "#be123c",
  cursor: "pointer",
  fontWeight: 800,
} as const;

const errorStyle = {
  border: "1px solid #fecaca",
  borderRadius: "8px",
  padding: "14px 16px",
  background: "#fff1f2",
  color: "#be123c",
  marginBottom: "16px",
} as const;

const successStyle = {
  border: "1px solid #bbf7d0",
  borderRadius: "8px",
  padding: "14px 16px",
  background: "#f0fdf4",
  color: "#166534",
  marginBottom: "16px",
} as const;
