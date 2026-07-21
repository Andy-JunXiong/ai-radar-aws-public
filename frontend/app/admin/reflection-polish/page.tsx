"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import Link from "next/link";

import AppContainer from "@/components/AppContainer";
import PageHeader from "@/components/PageHeader";
import RequireAdminAuth from "@/components/RequireAdminAuth";
import SectionCard from "@/components/SectionCard";
import { apiUrl } from "@/lib/api";
import { adminFetch } from "@/lib/adminAuth";

type PairSummary = {
  id?: string;
  created_at?: string;
  status?: string;
  review_outcome?: string | null;
  review_id?: string;
  signal_id?: string | null;
};

type ReflectionPolishPair = {
  id?: string;
  created_at?: string;
  status?: string;
  context?: {
    signal_id?: string | null;
    signal_title?: string | null;
    signal_summary?: string | null;
    why_it_matters?: string | null;
    relevance_to_projects?: string | null;
    relevance_to_career?: string | null;
    synthesized_insight?: string | null;
  };
  draft?: {
    original_text?: string;
    content_fingerprint?: string;
  };
  polish?: {
    polished_text?: string;
    content_fingerprint?: string;
    provider_used?: string;
    fallback_used?: boolean;
    policy_metadata?: Record<string, unknown>;
    execution?: Record<string, unknown>;
  };
  baseline_eligibility?: {
    eligible?: boolean;
    reason?: string;
  };
};

type ReflectionPolishReview = {
  id?: string;
  pair_id?: string;
  reviewed_at?: string;
  reviewer?: {
    type?: string;
    id?: string;
  };
  outcome?: ReviewOutcome;
  reviewer_note?: string;
  dimension_results?: Record<ReviewDimension, DimensionResult>;
  final_reflection_text?: string;
};

type PairDetail = {
  pair?: ReflectionPolishPair;
  review?: ReflectionPolishReview | null;
  index_entry?: PairSummary | null;
};

type ReviewOutcome = "approved" | "needs_revision" | "rejected";
type DimensionResult = "pass" | "fail" | "uncertain";
type ReviewDimension =
  | "meaning_preservation"
  | "user_voice_preservation"
  | "clarity_and_structure_gain"
  | "context_grounding"
  | "no_new_claims"
  | "non_generic_specificity";

const REVIEW_DIMENSIONS: { id: ReviewDimension; label: string }[] = [
  { id: "meaning_preservation", label: "Meaning preservation" },
  { id: "user_voice_preservation", label: "User voice" },
  { id: "clarity_and_structure_gain", label: "Clarity gain" },
  { id: "context_grounding", label: "Context grounding" },
  { id: "no_new_claims", label: "No new claims" },
  { id: "non_generic_specificity", label: "Specificity" },
];

const DEFAULT_DIMENSIONS: Record<ReviewDimension, DimensionResult> = {
  meaning_preservation: "pass",
  user_voice_preservation: "pass",
  clarity_and_structure_gain: "pass",
  context_grounding: "pass",
  no_new_claims: "pass",
  non_generic_specificity: "pass",
};

export default function ReflectionPolishAdminPage() {
  const [pairs, setPairs] = useState<PairSummary[]>([]);
  const [selectedPairId, setSelectedPairId] = useState("");
  const [detail, setDetail] = useState<PairDetail | null>(null);
  const [loadingList, setLoadingList] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [submittingReview, setSubmittingReview] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [outcome, setOutcome] = useState<ReviewOutcome>("approved");
  const [dimensionResults, setDimensionResults] = useState<Record<ReviewDimension, DimensionResult>>(DEFAULT_DIMENSIONS);
  const [reviewerNote, setReviewerNote] = useState("");
  const [finalReflectionText, setFinalReflectionText] = useState("");

  const selectedPair = detail?.pair;
  const existingReview = detail?.review || null;
  const passCount = useMemo(
    () => REVIEW_DIMENSIONS.filter((dimension) => dimensionResults[dimension.id] === "pass").length,
    [dimensionResults],
  );
  const hasFailedDimension = useMemo(
    () => REVIEW_DIMENSIONS.some((dimension) => dimensionResults[dimension.id] === "fail"),
    [dimensionResults],
  );

  async function loadPairs(preferredPairId?: string) {
    setLoadingList(true);
    setError("");
    try {
      const response = await adminFetch(apiUrl("/reflection-polish/pairs?limit=50"), { cache: "no-store" });
      if (!response.ok) throw new Error(`Reflection polish pair list failed with HTTP ${response.status}`);
      const payload = await response.json();
      const loadedPairs = Array.isArray(payload?.record?.pairs) ? payload.record.pairs : [];
      setPairs(loadedPairs);
      const nextPairId = preferredPairId || selectedPairId || loadedPairs[0]?.id || "";
      setSelectedPairId(nextPairId);
      if (nextPairId) {
        await loadPairDetail(nextPairId);
      } else {
        setDetail(null);
      }
    } catch (err) {
      setPairs([]);
      setDetail(null);
      setError(err instanceof Error ? err.message : "Reflection polish pairs could not be loaded.");
    } finally {
      setLoadingList(false);
    }
  }

  async function loadPairDetail(pairId: string) {
    if (!pairId) {
      setDetail(null);
      return;
    }
    setLoadingDetail(true);
    setError("");
    try {
      const response = await adminFetch(apiUrl(`/reflection-polish/pairs/${encodeURIComponent(pairId)}`), {
        cache: "no-store",
      });
      if (!response.ok) throw new Error(`Reflection polish pair detail failed with HTTP ${response.status}`);
      const payload = await response.json();
      const nextDetail = payload?.record || null;
      setDetail(nextDetail);
      const review = nextDetail?.review || null;
      if (review) {
        setOutcome((review.outcome || "approved") as ReviewOutcome);
        setDimensionResults({ ...DEFAULT_DIMENSIONS, ...(review.dimension_results || {}) });
        setReviewerNote(review.reviewer_note || "");
        setFinalReflectionText(review.final_reflection_text || "");
      } else {
        setOutcome("approved");
        setDimensionResults(DEFAULT_DIMENSIONS);
        setReviewerNote("");
        setFinalReflectionText(nextDetail?.pair?.polish?.polished_text || "");
      }
    } catch (err) {
      setDetail(null);
      setError(err instanceof Error ? err.message : "Reflection polish pair detail could not be loaded.");
    } finally {
      setLoadingDetail(false);
    }
  }

  useEffect(() => {
    void loadPairs();
    // Initial load only.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function selectPair(pairId: string) {
    setSelectedPairId(pairId);
    setNotice("");
    void loadPairDetail(pairId);
  }

  function setDimensionResult(dimension: ReviewDimension, value: DimensionResult) {
    setDimensionResults((current) => ({ ...current, [dimension]: value }));
  }

  async function submitReview(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedPairId) {
      setError("Select a reflection polish pair before recording review.");
      return;
    }
    setSubmittingReview(true);
    setError("");
    setNotice("");

    try {
      const response = await adminFetch(apiUrl(`/reflection-polish/pairs/${encodeURIComponent(selectedPairId)}/review`), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          outcome,
          dimension_results: dimensionResults,
          reviewer_note: reviewerNote,
          final_reflection_text: finalReflectionText,
        }),
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload?.detail || `Reflection polish review failed with HTTP ${response.status}`);
      }
      const payload = await response.json();
      const savedRecord = payload?.record || {};
      const savedOutcome = (savedRecord.outcome || outcome) as ReviewOutcome;
      const savedReviewId = String(savedRecord.review_id || "");
      const savedPairId = String(savedRecord.pair_id || selectedPairId);
      setNotice(`Review recorded: ${formatLabel(savedOutcome)}.`);
      setPairs((current) =>
        current.map((pair) =>
          pair.id === selectedPairId
            ? {
                ...pair,
                review_outcome: savedOutcome,
                review_id: savedReviewId,
              }
            : pair,
        ),
      );
      setDetail((current) =>
        current
          ? {
              ...current,
              review: {
                id: savedReviewId,
                pair_id: savedPairId,
                outcome: savedOutcome,
                reviewer_note: reviewerNote,
                dimension_results: dimensionResults,
                final_reflection_text: finalReflectionText,
              },
              index_entry: current.index_entry
                ? {
                    ...current.index_entry,
                    review_outcome: savedOutcome,
                    review_id: savedReviewId,
                  }
                : current.index_entry,
            }
          : current,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Reflection polish review could not be recorded.");
    } finally {
      setSubmittingReview(false);
    }
  }

  return (
    <AppContainer>
      <RequireAdminAuth>
        <PageHeader
          title="Reflection Polish Review"
          description="Review persisted before/after reflection polish pairs. This page records human judgment only and does not save final reflections or create evidence."
          size="compact"
        />

        <SectionCard title="Boundary">
          <div style={boundaryGridStyle}>
            <BoundaryCard label="Pairs" value={String(pairs.length)} />
            <BoundaryCard label="Selected" value={selectedPairId || "none"} />
            <BoundaryCard label="Review" value={existingReview?.outcome ? formatLabel(existingReview.outcome) : "not recorded"} />
            <BoundaryCard label="Baseline" value={selectedPair?.baseline_eligibility?.eligible ? "eligible" : "human review required"} />
          </div>
        </SectionCard>

        <div style={layoutStyle}>
          <SectionCard title="Pairs">
            {loadingList ? <div style={mutedStyle}>Loading reflection polish pairs...</div> : null}
            {!loadingList && pairs.length === 0 ? (
              <div style={emptyStyle}>No persisted reflection polish pairs yet.</div>
            ) : null}
            <div style={pairListStyle}>
              {pairs.map((pair) => (
                <button
                  key={pair.id || pair.created_at}
                  type="button"
                  style={pair.id === selectedPairId ? selectedPairButtonStyle : pairButtonStyle}
                  onClick={() => selectPair(pair.id || "")}
                >
                  <span style={pairIdStyle}>{pair.id || "unknown pair"}</span>
                  <span style={pairMetaStyle}>
                    {pair.created_at || "unknown time"} / {formatLabel(pair.review_outcome || "pending_review")}
                  </span>
                  {pair.signal_id ? <span style={pairMetaStyle}>signal: {pair.signal_id}</span> : null}
                </button>
              ))}
            </div>
          </SectionCard>

          <SectionCard title="Pair Detail">
            {error ? <div style={errorStyle}>{error}</div> : null}
            {notice ? <div style={noticeStyle}>{notice}</div> : null}
            {loadingDetail ? <div style={mutedStyle}>Loading selected pair...</div> : null}
            {!loadingDetail && selectedPair ? (
              <div style={detailGridStyle}>
                <div style={contextStyle}>
                  <div style={eyebrowStyle}>Context</div>
                  <h2 style={detailTitleStyle}>{selectedPair.context?.signal_title || "Untitled reflection context"}</h2>
                  <div style={metaGridStyle}>
                    <Meta label="Pair" value={selectedPair.id || "unknown"} />
                    <Meta label="Status" value={formatLabel(selectedPair.status || "generated")} />
                    <Meta label="Provider" value={selectedPair.polish?.provider_used || "unknown"} />
                    <Meta label="Fallback" value={selectedPair.polish?.fallback_used ? "yes" : "no"} />
                  </div>
                  {selectedPair.context?.signal_summary ? <p style={contextTextStyle}>{selectedPair.context.signal_summary}</p> : null}
                </div>

                <div style={compareGridStyle}>
                  <TextPanel title="Original Draft" text={selectedPair.draft?.original_text || ""} />
                  <TextPanel title="Polished Output" text={selectedPair.polish?.polished_text || ""} />
                </div>

                <form onSubmit={submitReview} style={reviewFormStyle}>
                  <div style={reviewHeaderStyle}>
                    <div>
                      <div style={eyebrowStyle}>Human Review</div>
                      <h2 style={detailTitleStyle}>{existingReview ? "Review recorded" : "Record review"}</h2>
                    </div>
                    <span style={statusBadgeStyle}>{passCount}/6 pass</span>
                  </div>

                  <label style={fieldStyle}>
                    <span style={fieldLabelStyle}>Outcome</span>
                    <select value={outcome} onChange={(event) => setOutcome(event.target.value as ReviewOutcome)} style={inputStyle}>
                      <option value="approved">Approved</option>
                      <option value="needs_revision">Needs revision</option>
                      <option value="rejected">Rejected</option>
                    </select>
                  </label>

                  <div style={dimensionGridStyle}>
                    {REVIEW_DIMENSIONS.map((dimension) => (
                      <label key={dimension.id} style={fieldStyle}>
                        <span style={fieldLabelStyle}>{dimension.label}</span>
                        <select
                          value={dimensionResults[dimension.id]}
                          onChange={(event) => setDimensionResult(dimension.id, event.target.value as DimensionResult)}
                          style={inputStyle}
                        >
                          <option value="pass">Pass</option>
                          <option value="uncertain">Uncertain</option>
                          <option value="fail">Fail</option>
                        </select>
                      </label>
                    ))}
                  </div>

                  <label style={fieldStyle}>
                    <span style={fieldLabelStyle}>Reviewer Note</span>
                    <textarea
                      value={reviewerNote}
                      onChange={(event) => setReviewerNote(event.target.value)}
                      placeholder="Required for needs_revision or rejected; recommended for approved."
                      style={textareaStyle}
                    />
                  </label>

                  <label style={fieldStyle}>
                    <span style={fieldLabelStyle}>Final Reflection Text</span>
                    <textarea
                      value={finalReflectionText}
                      onChange={(event) => setFinalReflectionText(event.target.value)}
                      placeholder="Required when outcome is approved."
                      style={largeTextareaStyle}
                    />
                  </label>

                  {hasFailedDimension && outcome === "approved" ? (
                    <div style={warningStyle}>Approved reviews cannot include failed dimensions.</div>
                  ) : null}

                  <div style={actionRowStyle}>
                    <button type="submit" style={primaryButtonStyle} disabled={submittingReview}>
                      {submittingReview ? "Recording" : "Record Review"}
                    </button>
                    <Link href="/admin" style={secondaryLinkStyle}>Back to Admin</Link>
                  </div>
                  {notice ? <div aria-live="polite" style={inlineNoticeStyle}>{notice}</div> : null}
                </form>
              </div>
            ) : null}
          </SectionCard>
        </div>
      </RequireAdminAuth>
    </AppContainer>
  );
}

function BoundaryCard({ label, value }: { label: string; value: string }) {
  return (
    <div style={boundaryCardStyle}>
      <div style={eyebrowStyle}>{label}</div>
      <div style={boundaryValueStyle}>{value}</div>
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

function TextPanel({ title, text }: { title: string; text: string }) {
  return (
    <div style={textPanelStyle}>
      <div style={eyebrowStyle}>{title}</div>
      <div style={textBodyStyle}>{text || "No text recorded."}</div>
    </div>
  );
}

function formatLabel(value: string) {
  return value.replace(/_/g, " ");
}

const boundaryGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
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
  fontWeight: 850,
  color: "var(--app-text-strong)",
  lineHeight: 1.35,
  overflowWrap: "anywhere",
} as const;

const layoutStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 320px), 1fr))",
  gap: "16px",
  alignItems: "start",
} as const;

const pairListStyle = {
  display: "grid",
  gap: "8px",
} as const;

const pairButtonStyle = {
  width: "100%",
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  padding: "12px",
  background: "var(--app-surface-bg)",
  color: "var(--app-text-strong)",
  textAlign: "left",
  display: "grid",
  gap: "5px",
  cursor: "pointer",
} as const;

const selectedPairButtonStyle = {
  ...pairButtonStyle,
  border: "1px solid var(--app-info-border)",
  background: "var(--app-info-bg)",
} as const;

const pairIdStyle = {
  fontSize: "13px",
  fontWeight: 850,
  overflowWrap: "anywhere",
} as const;

const pairMetaStyle = {
  fontSize: "12px",
  color: "var(--app-text-muted)",
  lineHeight: 1.35,
} as const;

const detailGridStyle = {
  display: "grid",
  gap: "14px",
} as const;

const contextStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  padding: "14px",
  background: "var(--app-surface-muted-bg)",
} as const;

const compareGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
  gap: "12px",
} as const;

const textPanelStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  padding: "14px",
  background: "var(--app-surface-bg)",
  minHeight: "180px",
} as const;

const textBodyStyle = {
  marginTop: "10px",
  color: "var(--app-text-strong)",
  fontSize: "14px",
  lineHeight: 1.65,
  whiteSpace: "pre-wrap",
} as const;

const reviewFormStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  padding: "14px",
  background: "var(--app-surface-soft-bg)",
  display: "grid",
  gap: "12px",
} as const;

const reviewHeaderStyle = {
  display: "flex",
  justifyContent: "space-between",
  gap: "12px",
  alignItems: "flex-start",
} as const;

const dimensionGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))",
  gap: "10px",
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

const textareaStyle = {
  ...inputStyle,
  minHeight: "84px",
  resize: "vertical",
} as const;

const largeTextareaStyle = {
  ...inputStyle,
  minHeight: "140px",
  resize: "vertical",
  lineHeight: 1.55,
} as const;

const actionRowStyle = {
  display: "flex",
  flexWrap: "wrap",
  gap: "8px",
  alignItems: "center",
} as const;

const primaryButtonStyle = {
  border: "1px solid var(--app-info-border)",
  borderRadius: "8px",
  padding: "10px 14px",
  background: "var(--app-info-bg)",
  color: "var(--app-info-fg)",
  fontSize: "14px",
  fontWeight: 850,
  cursor: "pointer",
} as const;

const secondaryLinkStyle = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  border: "1px solid var(--app-surface-strong-border)",
  borderRadius: "8px",
  padding: "10px 14px",
  background: "var(--app-surface-bg)",
  color: "var(--app-text-strong)",
  fontSize: "14px",
  fontWeight: 800,
  textDecoration: "none",
} as const;

const metaGridStyle = {
  marginTop: "10px",
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
  gap: "8px",
} as const;

const metaItemStyle = {
  display: "grid",
  gap: "4px",
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  padding: "9px",
  background: "var(--app-surface-bg)",
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

const contextTextStyle = {
  margin: "12px 0 0",
  color: "var(--app-text-muted)",
  fontSize: "14px",
  lineHeight: 1.6,
} as const;

const eyebrowStyle = {
  fontSize: "12px",
  fontWeight: 800,
  color: "var(--app-text-subtle)",
  textTransform: "uppercase",
  letterSpacing: 0,
} as const;

const detailTitleStyle = {
  margin: "4px 0 0",
  color: "var(--app-text-strong)",
  fontSize: "20px",
  fontWeight: 850,
  lineHeight: 1.25,
} as const;

const statusBadgeStyle = {
  border: "1px solid var(--app-info-border)",
  borderRadius: "999px",
  padding: "5px 9px",
  background: "var(--app-info-bg)",
  color: "var(--app-info-fg)",
  fontSize: "12px",
  fontWeight: 850,
  whiteSpace: "nowrap",
} as const;

const mutedStyle = {
  color: "var(--app-text-muted)",
  fontSize: "14px",
} as const;

const emptyStyle = {
  border: "1px dashed var(--app-surface-strong-border)",
  borderRadius: "8px",
  padding: "14px",
  background: "var(--app-surface-soft-bg)",
  color: "var(--app-text-muted)",
  fontSize: "14px",
} as const;

const errorStyle = {
  border: "1px solid var(--app-danger-border)",
  borderRadius: "8px",
  padding: "10px",
  background: "var(--app-danger-bg)",
  color: "var(--app-danger-fg)",
  fontSize: "13px",
} as const;

const noticeStyle = {
  border: "1px solid var(--app-info-border)",
  borderRadius: "8px",
  padding: "10px",
  background: "var(--app-info-bg)",
  color: "var(--app-info-fg)",
  fontSize: "13px",
} as const;

const inlineNoticeStyle = {
  ...noticeStyle,
  marginTop: "-2px",
} as const;

const warningStyle = {
  border: "1px solid var(--app-warning-border)",
  borderRadius: "8px",
  padding: "10px",
  background: "var(--app-warning-bg)",
  color: "var(--app-warning-fg)",
  fontSize: "13px",
} as const;
