"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";

import AppContainer from "@/components/AppContainer";
import PageHeader from "@/components/PageHeader";
import RequireAdminAuth from "@/components/RequireAdminAuth";
import SectionCard from "@/components/SectionCard";
import { apiUrl } from "@/lib/api";
import { adminFetch } from "@/lib/adminAuth";
import { DecisionCard, LearningSummary, ReviewRecord, completeReview, fetchDecisionCards, fetchDueReviews, fetchLearningSummary } from "@/lib/decisions";

type ReflectionItem = {
  id: string;
  title?: string;
  timestamp?: string;
  source?: string;
  tags?: string[];
  depth?: string | null;
  duration_minutes?: number | null;
  self_correction_count?: number | null;
  github_url?: string;
};

type ReflectionListPayload = {
  schema_version?: string;
  last_updated?: string;
  total_count?: number;
  reflections?: ReflectionItem[];
};

type ReflectionAnalyticsPayload = {
  window_days?: number;
  total_reflections?: number;
  reflections_with_signal_matches?: number;
  reflections_with_manual_matches?: number;
  total_signal_matches?: number;
  total_manual_matches?: number;
  top_reflections?: Array<{
    id: string;
    title?: string;
    total_matches?: number;
    signal_matches?: number;
    manual_matches?: number;
  }>;
  top_relationship_tags?: Array<{
    tag: string;
    count: number;
  }>;
};

type ReflectionBackfillPreviewPayload = {
  total_candidates?: number;
  suggestions?: Array<{
    id: string;
    title?: string;
    missing_fields?: string[];
    suggested_thesis?: string;
    suggested_key_claims?: string[];
    suggested_final_takeaway?: string;
  }>;
};

type BackfillBatchResult = {
  requested_limit?: number;
  created_count?: number;
  drafts?: Array<{
    reflection_id?: string;
    file_path?: string;
  }>;
};

export default function ReflectionsPage() {
  const [payload, setPayload] = useState<ReflectionListPayload | null>(null);
  const [analytics, setAnalytics] = useState<ReflectionAnalyticsPayload | null>(null);
  const [backfillPreview, setBackfillPreview] = useState<ReflectionBackfillPreviewPayload | null>(null);
  const [backfillBatchResult, setBackfillBatchResult] = useState<BackfillBatchResult | null>(null);
  const [dueReviews, setDueReviews] = useState<ReviewRecord[]>([]);
  const [reviewDecisionCards, setReviewDecisionCards] = useState<DecisionCard[]>([]);
  const [learningSummary, setLearningSummary] = useState<LearningSummary | null>(null);
  const [activeReviewId, setActiveReviewId] = useState("");
  const [reviewOutcome, setReviewOutcome] = useState<"correct" | "partially_correct" | "wrong" | "unclear">("unclear");
  const [reviewWhatHappened, setReviewWhatHappened] = useState("");
  const [reviewNotes, setReviewNotes] = useState("");
  const [reviewConfidenceAdjustment, setReviewConfidenceAdjustment] = useState("0");
  const [reviewSubmitting, setReviewSubmitting] = useState(false);
  const [reviewMessage, setReviewMessage] = useState("");
  const [batchDraftLoading, setBatchDraftLoading] = useState(false);
  const [search, setSearch] = useState("");
  const [sourceFilter, setSourceFilter] = useState("all");
  const [windowFilter, setWindowFilter] = useState<"7" | "30" | "180" | "all">("30");
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    fetch(apiUrl("/reflection"))
      .then((res) => res.json())
      .then((data) => {
        setPayload(data);
        setErrorMessage("");
      })
      .catch(() => {
        setPayload({ reflections: [], total_count: 0 });
        setErrorMessage("Failed to load reflections right now.");
      });

  }, []);

  useEffect(() => {
    const daysParam = windowFilter === "all" ? "0" : windowFilter;
    fetch(apiUrl(`/reflection/analytics?days=${daysParam}&limit=5`))
      .then((res) => res.json())
      .then((data) => {
        setAnalytics(data);
      })
      .catch(() => {
        setAnalytics(null);
      });
  }, [windowFilter]);

  useEffect(() => {
    fetch(apiUrl("/reflection/backfill-preview?limit=5"))
      .then((res) => res.json())
      .then((data) => {
        setBackfillPreview(data);
      })
      .catch(() => {
        setBackfillPreview(null);
      });
  }, []);

  useEffect(() => {
    Promise.all([fetchDueReviews(), fetchDecisionCards()])
      .then(([reviews, cards]) => {
        setDueReviews(reviews.slice(0, 5));
        const cardMap = new Map(cards.map((card) => [card.id, card]));
        setReviewDecisionCards(
          reviews
            .map((review) => cardMap.get(review.decision_card_id || ""))
            .filter((item): item is DecisionCard => Boolean(item))
            .slice(0, 5),
        );
      })
      .catch(() => {
        setDueReviews([]);
        setReviewDecisionCards([]);
      });
  }, []);

  useEffect(() => {
    fetchLearningSummary()
      .then((summary) => setLearningSummary(summary))
      .catch(() => setLearningSummary(null));
  }, []);

  const reviewCardMap = useMemo(
    () => new Map(reviewDecisionCards.map((card) => [card.id, card])),
    [reviewDecisionCards],
  );

  const reflections = useMemo(() => {
    const items = Array.isArray(payload?.reflections) ? payload!.reflections! : [];
    const query = search.trim().toLowerCase();
    return items.filter((item) => {
      const sourceOk = sourceFilter === "all" || (item.source || "") === sourceFilter;
      if (!sourceOk) return false;
      if (!query) return true;
      const haystack = [item.title, item.id, ...(item.tags || [])].filter(Boolean).join(" ").toLowerCase();
      return haystack.includes(query);
    });
  }, [payload, search, sourceFilter]);

  const sources = useMemo(() => {
    const items = Array.isArray(payload?.reflections) ? payload!.reflections! : [];
    return Array.from(new Set(items.map((item) => (item.source || "").trim()).filter(Boolean))).sort((a, b) =>
      a.localeCompare(b),
    );
  }, [payload]);

  const createBatchDrafts = async () => {
    try {
      setBatchDraftLoading(true);
      const res = await adminFetch(apiUrl("/reflection/backfill-drafts/batch?limit=5"), {
        method: "POST",
      });
      if (!res.ok) {
        throw new Error("Failed to create batch drafts.");
      }
      const data = (await res.json()) as BackfillBatchResult;
      setBackfillBatchResult(data);
    } catch {
      setBackfillBatchResult(null);
    } finally {
      setBatchDraftLoading(false);
    }
  };

  const startReview = (review: ReviewRecord) => {
    setActiveReviewId(review.id);
    setReviewOutcome((review.outcome as "correct" | "partially_correct" | "wrong" | "unclear") || "unclear");
    setReviewWhatHappened(review.what_happened || "");
    setReviewNotes(review.notes || "");
    setReviewConfidenceAdjustment(String(review.confidence_adjustment ?? 0));
    setReviewMessage("");
  };

  const submitReview = async (reviewId: string) => {
    try {
      setReviewSubmitting(true);
      setReviewMessage("");
      await completeReview(reviewId, {
        outcome: reviewOutcome,
        what_happened: reviewWhatHappened,
        confidence_adjustment: Number(reviewConfidenceAdjustment) || 0,
        notes: reviewNotes,
      });

      const completed = dueReviews.find((item) => item.id === reviewId);
      setDueReviews((current) => current.filter((item) => item.id !== reviewId));
      if (completed?.decision_card_id) {
        setReviewDecisionCards((current) =>
          current.map((item) =>
            item.id === completed.decision_card_id
              ? {
                  ...item,
                  status: "reviewed",
                }
              : item,
          ),
        );
      }
      setActiveReviewId("");
      setReviewWhatHappened("");
      setReviewNotes("");
      setReviewConfidenceAdjustment("0");
      setReviewOutcome("unclear");
      setReviewMessage("Review completed successfully.");
      try {
        const summary = await fetchLearningSummary();
        setLearningSummary(summary);
      } catch {
        setLearningSummary(null);
      }
    } catch {
      setReviewMessage("Failed to complete review.");
    } finally {
      setReviewSubmitting(false);
    }
  };

  return (
    <AppContainer>
      <RequireAdminAuth>
        <PageHeader
          title="Reflection Center"
          description="Review completed signal decisions separately from long-form deep conversation reflections synced from GitHub."
        />

        <SectionCard title="Reflection Boundary">
          <div style={boundaryGridStyle}>
            <div style={boundaryItemStyle}>
              <strong>Cognition context</strong>
              <span>Deep reflections can explain how your thinking is evolving, but they are not factual evidence for external AI ecosystem claims.</span>
            </div>
            <div style={boundaryItemStyle}>
              <strong>Selective bridge</strong>
              <span>Use reflection matches as context for review questions, not as automatic Project Takeaway, action, or trajectory-memory events.</span>
            </div>
            <div style={boundaryItemStyle}>
              <strong>Concept skills</strong>
              <span>Concept-skill links should remain conditional and human-reviewed until repeated usage proves the schema is stable.</span>
            </div>
          </div>
        </SectionCard>

        <SectionCard title="Signal Reflection Review">
          <div style={sectionIntroStyle}>
            Use this queue to revisit signal-based decisions after time has passed. Mark what actually
            happened, whether the original judgment was correct, and how confidence should change.
            These reviews help calibrate future signal completion notes and decision cards.
          </div>
          <div style={{ marginBottom: "14px", fontSize: "14px", color: "var(--app-text-muted)" }}>
            Due reviews: <strong>{dueReviews.length}</strong>
          </div>
          {reviewMessage ? (
            <div style={{ marginBottom: "12px", fontSize: "14px", color: reviewMessage.startsWith("Failed") ? "#b91c1c" : "#166534" }}>
              {reviewMessage}
            </div>
          ) : null}
          {dueReviews.length ? (
            <div style={{ display: "grid", gap: "12px" }}>
              {dueReviews.map((review) => {
                const linkedCard = reviewCardMap.get(review.decision_card_id || "");
                const isActive = activeReviewId === review.id;

                return (
                  <div
                    key={review.id}
                    style={{
                      border: "1px solid var(--app-surface-border)",
                      borderRadius: "8px",
                      padding: "16px",
                      background: "var(--app-surface-bg)",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", gap: "12px", flexWrap: "wrap" }}>
                      <div>
                        <div style={{ fontWeight: 700, color: "var(--app-text-strong)" }}>
                          {linkedCard?.title || review.decision_card_id || review.id}
                        </div>
                        <div style={{ fontSize: "13px", color: "var(--app-text-muted)", marginTop: "4px" }}>
                          review due: {review.review_date ? new Date(review.review_date).toLocaleDateString() : "n/a"}
                        </div>
                      </div>
                      <button type="button" onClick={() => startReview(review)} style={secondaryLinkButtonStyle}>
                        {isActive ? "Editing Review" : "Complete Review"}
                      </button>
                    </div>

                    {linkedCard?.thesis ? (
                      <div style={{ marginTop: "12px", fontSize: "14px", color: "var(--app-text-strong)", lineHeight: 1.7 }}>
                        {linkedCard.thesis}
                      </div>
                    ) : null}

                    {linkedCard?.recommended_action ? (
                      <div style={{ marginTop: "10px", fontSize: "14px", color: "var(--app-text-muted)" }}>
                        <strong>Recommended action:</strong> {linkedCard.recommended_action}
                      </div>
                    ) : null}

                    {isActive ? (
                      <div
                        style={{
                          marginTop: "14px",
                          borderTop: "1px solid var(--app-surface-border)",
                          paddingTop: "14px",
                          display: "grid",
                          gap: "12px",
                        }}
                      >
                        <label style={formLabelStyle}>
                          Outcome
                          <select
                            value={reviewOutcome}
                            onChange={(event) =>
                              setReviewOutcome(event.target.value as "correct" | "partially_correct" | "wrong" | "unclear")
                            }
                            style={reviewInputStyle}
                          >
                            <option value="correct">correct</option>
                            <option value="partially_correct">partially_correct</option>
                            <option value="wrong">wrong</option>
                            <option value="unclear">unclear</option>
                          </select>
                        </label>

                        <label style={formLabelStyle}>
                          What changed since the decision
                          <textarea
                            value={reviewWhatHappened}
                            onChange={(event) => setReviewWhatHappened(event.target.value)}
                            rows={4}
                            style={{ ...reviewInputStyle, resize: "vertical" }}
                            placeholder="Summarize what actually happened after this decision."
                          />
                        </label>

                        <label style={formLabelStyle}>
                          Confidence adjustment
                          <input
                            type="number"
                            value={reviewConfidenceAdjustment}
                            onChange={(event) => setReviewConfidenceAdjustment(event.target.value)}
                            style={reviewInputStyle}
                          />
                        </label>

                        <label style={formLabelStyle}>
                          Notes
                          <textarea
                            value={reviewNotes}
                            onChange={(event) => setReviewNotes(event.target.value)}
                            rows={3}
                            style={{ ...reviewInputStyle, resize: "vertical" }}
                            placeholder="Optional follow-up notes."
                          />
                        </label>

                        <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
                          <button
                            type="button"
                            onClick={() => void submitReview(review.id)}
                            disabled={reviewSubmitting || !reviewWhatHappened.trim()}
                            style={secondaryLinkButtonStyle}
                          >
                            {reviewSubmitting ? "Saving..." : "Submit Review"}
                          </button>
                          <button
                            type="button"
                            onClick={() => setActiveReviewId("")}
                            disabled={reviewSubmitting}
                            style={secondaryGhostButtonStyle}
                          >
                            Cancel
                          </button>
                        </div>
                      </div>
                    ) : null}
                  </div>
                );
              })}
            </div>
          ) : (
            <div style={emptyStyle}>No due decision reviews yet.</div>
          )}
        </SectionCard>

        <SectionCard title="Signal Reflection Review Stats">
          <div style={sectionIntroStyle}>
            This summarizes completed signal reviews. It is not the GitHub deep reflection index; it is
            feedback on whether previous signal judgments held up over time.
          </div>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
              gap: "12px",
              marginBottom: "16px",
            }}
          >
            <div style={metricCardStyle}>
              <div style={metricLabelStyle}>Completed Reviews</div>
              <div style={metricValueStyle}>{learningSummary?.total_completed_reviews ?? 0}</div>
            </div>
            <div style={metricCardStyle}>
              <div style={metricLabelStyle}>Linked Cards Reviewed</div>
              <div style={metricValueStyle}>{learningSummary?.reviewed_with_linked_cards ?? 0}</div>
            </div>
            <div style={metricCardStyle}>
              <div style={metricLabelStyle}>Avg Confidence Adj.</div>
              <div style={metricValueStyle}>{learningSummary?.average_confidence_adjustment ?? 0}</div>
            </div>
          </div>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
              gap: "16px",
            }}
          >
            <div style={analyticsPanelStyle}>
              <div style={analyticsPanelTitleStyle}>Outcome Mix</div>
              <div style={{ display: "grid", gap: "8px" }}>
                {[
                  ["correct", learningSummary?.outcome_counts?.correct ?? 0],
                  ["partially_correct", learningSummary?.outcome_counts?.partially_correct ?? 0],
                  ["wrong", learningSummary?.outcome_counts?.wrong ?? 0],
                  ["unclear", learningSummary?.outcome_counts?.unclear ?? 0],
                ].map(([label, value]) => (
                  <div key={String(label)} style={analyticsRowStyle}>
                    <div style={{ color: "var(--app-text-muted)", fontSize: "14px" }}>{label}</div>
                    <div style={{ color: "var(--app-text-strong)", fontWeight: 700 }}>{value}</div>
                  </div>
                ))}
              </div>
            </div>

            <div style={analyticsPanelStyle}>
              <div style={analyticsPanelTitleStyle}>Confidence Calibration</div>
              {(learningSummary?.confidence_buckets || []).length ? (
                <div style={{ display: "grid", gap: "10px" }}>
                  {(learningSummary?.confidence_buckets || []).map((bucket) => (
                    <div key={bucket.label} style={analyticsRowStyle}>
                      <div>
                        <div style={{ color: "var(--app-text-strong)", fontWeight: 700 }}>{bucket.label}</div>
                        <div style={{ color: "var(--app-text-muted)", fontSize: "13px" }}>
                          total {bucket.total} 路 correct {bucket.correct} 路 partial {bucket.partially_correct}
                        </div>
                      </div>
                      <div style={{ color: "var(--app-text-muted)", fontSize: "13px" }}>
                        wrong {bucket.wrong} 路 unclear {bucket.unclear}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div style={emptyStyle}>No calibration data yet.</div>
              )}
            </div>
          </div>
        </SectionCard>

        <div style={sectionHeaderStyle}>
          <div style={sectionEyebrowStyle}>Deep Reflections</div>
          <h2 style={sectionTitleStyle}>Deep Conversation Reflection Index</h2>
          <div style={sectionDescriptionStyle}>
            These records are synced from your configured GitHub deep reflection source. They are separate from signal completion notes and signal review calibration.
          </div>
        </div>

        <SectionCard title="Deep Reflection Match Analytics">
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
              gap: "12px",
              marginBottom: "16px",
            }}
          >
            <div style={metricCardStyle}>
              <div style={metricLabelStyle}>Window</div>
              <select
                value={windowFilter}
                onChange={(event) => setWindowFilter(event.target.value as "7" | "30" | "180" | "all")}
                style={windowSelectStyle}
              >
                <option value="7">7d</option>
                <option value="30">30d</option>
                <option value="180">180d</option>
                <option value="all">All</option>
              </select>
            </div>
            <div style={metricCardStyle}>
              <div style={metricLabelStyle}>Signal Matches</div>
              <div style={metricValueStyle}>{analytics?.total_signal_matches ?? 0}</div>
            </div>
            <div style={metricCardStyle}>
              <div style={metricLabelStyle}>Manual Matches</div>
              <div style={metricValueStyle}>{analytics?.total_manual_matches ?? 0}</div>
            </div>
            <div style={metricCardStyle}>
              <div style={metricLabelStyle}>Deep Reflections Hit By Signals</div>
              <div style={metricValueStyle}>{analytics?.reflections_with_signal_matches ?? 0}</div>
            </div>
            <div style={metricCardStyle}>
              <div style={metricLabelStyle}>Deep Reflections Hit By Manual</div>
              <div style={metricValueStyle}>{analytics?.reflections_with_manual_matches ?? 0}</div>
            </div>
          </div>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
              gap: "16px",
            }}
          >
            <div style={analyticsPanelStyle}>
              <div style={analyticsPanelTitleStyle}>Top Deep Reflections</div>
              {(analytics?.top_reflections || []).length ? (
                <div style={{ display: "grid", gap: "10px" }}>
                  {(analytics?.top_reflections || []).map((item) => (
                    <div key={item.id} style={analyticsRowStyle}>
                      <div>
                        <div style={{ fontWeight: 700, color: "var(--app-text-strong)" }}>
                          {item.title || item.id}
                        </div>
                        <div style={{ fontSize: "13px", color: "var(--app-text-muted)" }}>
                          {item.total_matches ?? 0} total · {item.signal_matches ?? 0} signal · {item.manual_matches ?? 0} manual
                        </div>
                      </div>
                      <Link href={`/reflections/detail?id=${encodeURIComponent(item.id)}`} style={miniLinkStyle}>
                        Open detail
                      </Link>
                    </div>
                  ))}
                </div>
              ) : (
                <div style={emptyStyle}>No relationship activity yet.</div>
              )}
            </div>

            <div style={analyticsPanelStyle}>
              <div style={analyticsPanelTitleStyle}>Top Relationship Tags</div>
              {(analytics?.top_relationship_tags || []).length ? (
                <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                  {(analytics?.top_relationship_tags || []).map((item) => (
                    <span key={item.tag} style={tagStyle}>
                      #{item.tag} ({item.count})
                    </span>
                  ))}
                </div>
              ) : (
                <div style={emptyStyle}>No repeated tags yet.</div>
              )}
            </div>
          </div>
        </SectionCard>

        <SectionCard title="Advanced Maintenance">
          <details>
            <summary style={{ cursor: "pointer", fontWeight: 800, color: "var(--app-text-strong)" }}>
              Deep Reflection Structure Backfill
            </summary>
            <div style={{ marginTop: "14px", color: "var(--app-text-muted)", fontSize: "14px", lineHeight: 1.7 }}>
              Maintenance-only tool for finding deep reflections that are missing structured fields such as thesis,
              key claims, or final takeaway.
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", gap: "12px", flexWrap: "wrap", marginTop: "14px", marginBottom: "14px" }}>
              <div style={{ fontSize: "14px", color: "var(--app-text-muted)" }}>
                Candidate deep reflections missing structured reasoning fields:{" "}
                <strong>{backfillPreview?.total_candidates ?? 0}</strong>
              </div>
              <button type="button" onClick={createBatchDrafts} disabled={batchDraftLoading} style={secondaryLinkButtonStyle}>
                {batchDraftLoading ? "Creating..." : "Create Structure Drafts"}
              </button>
            </div>

          {backfillBatchResult?.created_count ? (
            <div style={{ ...analyticsPanelStyle, marginBottom: "14px" }}>
              <div style={analyticsPanelTitleStyle}>
                Draft files created: {backfillBatchResult.created_count}
              </div>
              <div style={{ display: "grid", gap: "8px" }}>
                {(backfillBatchResult.drafts || []).map((item, index) => (
                  <div key={`${item.reflection_id || "draft"}-${index}`} style={{ fontSize: "13px", color: "var(--app-text-muted)" }}>
                    <strong>{item.reflection_id || "unknown"}</strong>: {item.file_path || "no path"}
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          {(backfillPreview?.suggestions || []).length ? (
            <div style={{ display: "grid", gap: "12px" }}>
              {(backfillPreview?.suggestions || []).map((item) => (
                <div key={item.id} style={analyticsPanelStyle}>
                  <div style={{ display: "flex", justifyContent: "space-between", gap: "12px", flexWrap: "wrap" }}>
                    <div>
                      <div style={{ fontWeight: 800, color: "var(--app-text-strong)" }}>{item.title || item.id}</div>
                      <div style={{ fontSize: "13px", color: "var(--app-text-muted)" }}>
                        Missing: {(item.missing_fields || []).join(", ")}
                      </div>
                    </div>
                    <Link href={`/reflections/detail?id=${encodeURIComponent(item.id)}`} style={miniLinkStyle}>
                      Open detail
                    </Link>
                  </div>
                  {item.suggested_thesis ? (
                    <div style={{ fontSize: "14px", color: "var(--app-text-muted)", lineHeight: 1.6 }}>
                      <strong>Suggested thesis:</strong> {item.suggested_thesis}
                    </div>
                  ) : null}
                  {(item.suggested_key_claims || []).length ? (
                    <div style={{ fontSize: "14px", color: "var(--app-text-muted)", lineHeight: 1.6 }}>
                      <strong>Suggested claims:</strong> {(item.suggested_key_claims || []).join(" | ")}
                    </div>
                  ) : null}
                  {item.suggested_final_takeaway ? (
                    <div style={{ fontSize: "14px", color: "var(--app-text-muted)", lineHeight: 1.6 }}>
                      <strong>Suggested takeaway:</strong> {item.suggested_final_takeaway}
                    </div>
                  ) : null}
                </div>
              ))}
            </div>
          ) : (
            <div style={emptyStyle}>
              No immediate structure backfill candidates found, or preview data is unavailable.
            </div>
          )}
          </details>
        </SectionCard>

        <SectionCard title="Deep Reflection Index">
          {errorMessage ? <div style={errorStyle}>{errorMessage}</div> : null}
          <div style={toolbarStyle}>
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search title, id, or tags"
              style={inputStyle}
            />
            <select value={sourceFilter} onChange={(event) => setSourceFilter(event.target.value)} style={selectStyle}>
              <option value="all">All sources</option>
              {sources.map((source) => (
                <option key={source} value={source}>
                  {source}
                </option>
              ))}
            </select>
            <div style={summaryChipStyle}>
              Showing {reflections.length} of {payload?.total_count ?? reflections.length}
            </div>
          </div>

          {!payload ? (
            <div style={emptyStyle}>Loading deep reflections...</div>
          ) : reflections.length === 0 ? (
            <div style={emptyStyle}>
              No deep reflections indexed yet. Save the reflection connection and run sync first.
            </div>
          ) : (
            <div style={{ display: "grid", gap: "12px" }}>
              {reflections.map((item) => (
                <div key={item.id} style={cardStyle}>
                  <div style={{ display: "grid", gap: "8px" }}>
                    <div style={{ fontSize: "18px", fontWeight: 800, color: "var(--app-text-strong)" }}>
                      {item.title || item.id}
                    </div>
                    <div style={{ fontSize: "13px", color: "var(--app-text-muted)" }}>
                      {(item.timestamp || "Unknown time")}
                      {item.source ? ` · ${item.source}` : ""}
                      {item.depth ? ` · ${item.depth}` : ""}
                    </div>
                    {(item.tags || []).length ? (
                      <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                        {(item.tags || []).map((tag) => (
                          <span key={tag} style={tagStyle}>
                            #{tag}
                          </span>
                        ))}
                      </div>
                    ) : null}
                    <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
                      <Link href={`/reflections/detail?id=${encodeURIComponent(item.id)}`} style={buttonLinkStyle}>
                        Open detail
                      </Link>
                      {item.github_url ? (
                        <a href={item.github_url} target="_blank" rel="noreferrer" style={secondaryLinkStyle}>
                          Open on GitHub
                        </a>
                      ) : null}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </SectionCard>
      </RequireAdminAuth>
    </AppContainer>
  );
}

const toolbarStyle = {
  display: "flex",
  gap: "12px",
  flexWrap: "wrap",
  alignItems: "center",
  marginBottom: "16px",
} as const;

const inputStyle = {
  minWidth: "260px",
  border: "1px solid var(--app-input-border)",
  borderRadius: "12px",
  padding: "12px 14px",
  fontSize: "14px",
  color: "var(--app-input-fg)",
  background: "var(--app-input-bg)",
} as const;

const selectStyle = {
  border: "1px solid var(--app-input-border)",
  borderRadius: "12px",
  padding: "12px 14px",
  fontSize: "14px",
  color: "var(--app-input-fg)",
  background: "var(--app-input-bg)",
} as const;

const summaryChipStyle = {
  borderRadius: "999px",
  border: "1px solid var(--app-chip-border)",
  background: "var(--app-chip-bg)",
  color: "var(--app-chip-fg)",
  padding: "10px 14px",
  fontSize: "13px",
  fontWeight: 700,
} as const;

const emptyStyle = {
  color: "var(--app-text-muted)",
  fontSize: "14px",
  padding: "6px 0",
} as const;

const cardStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-bg)",
  padding: "16px",
} as const;

const boundaryGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
  gap: "12px",
} as const;

const boundaryItemStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  padding: "13px",
  display: "grid",
  gap: "7px",
  color: "var(--app-text-muted)",
  fontSize: "14px",
  lineHeight: 1.55,
} as const;

const sectionIntroStyle = {
  color: "var(--app-text-muted)",
  fontSize: "14px",
  lineHeight: 1.7,
  marginBottom: "14px",
  maxWidth: "900px",
} as const;

const sectionHeaderStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-bg)",
  padding: "20px",
  margin: "24px 0 16px",
} as const;

const sectionEyebrowStyle = {
  color: "var(--app-text-subtle)",
  fontSize: "12px",
  fontWeight: 800,
  letterSpacing: "0.5px",
  textTransform: "uppercase",
  marginBottom: "8px",
} as const;

const sectionTitleStyle = {
  color: "var(--app-text-strong)",
  fontSize: "24px",
  lineHeight: 1.25,
  margin: "0 0 8px",
} as const;

const sectionDescriptionStyle = {
  color: "var(--app-text-muted)",
  fontSize: "14px",
  lineHeight: 1.7,
  maxWidth: "880px",
} as const;

const metricCardStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  padding: "14px",
  display: "grid",
  gap: "6px",
} as const;

const metricLabelStyle = {
  fontSize: "12px",
  color: "var(--app-text-subtle)",
  textTransform: "uppercase",
  letterSpacing: "0.4px",
  fontWeight: 700,
} as const;

const metricValueStyle = {
  fontSize: "24px",
  fontWeight: 800,
  color: "var(--app-text-strong)",
} as const;
const windowSelectStyle = {
  border: "1px solid var(--app-input-border)",
  borderRadius: "12px",
  padding: "10px 12px",
  fontSize: "22px",
  fontWeight: 800,
  color: "var(--app-input-fg)",
  background: "var(--app-input-bg)",
  outline: "none",
  width: "100%",
  maxWidth: "120px",
  appearance: "auto",
} as const;

const analyticsPanelStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-bg)",
  padding: "16px",
  display: "grid",
  gap: "12px",
} as const;

const analyticsPanelTitleStyle = {
  fontSize: "14px",
  fontWeight: 800,
  color: "var(--app-text-strong)",
} as const;

const analyticsRowStyle = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  gap: "12px",
  flexWrap: "wrap",
} as const;

const miniLinkStyle = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  padding: "8px 12px",
  borderRadius: "8px",
  border: "1px solid var(--app-secondary-action-border)",
  background: "var(--app-secondary-action-bg)",
  color: "var(--app-secondary-action-fg)",
  textDecoration: "none",
  fontWeight: 700,
  fontSize: "13px",
} as const;

const secondaryLinkButtonStyle = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  padding: "10px 14px",
  borderRadius: "8px",
  border: "1px solid var(--app-secondary-action-border)",
  background: "var(--app-secondary-action-bg)",
  color: "var(--app-secondary-action-fg)",
  textDecoration: "none",
  fontWeight: 700,
  cursor: "pointer",
} as const;

const secondaryGhostButtonStyle = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  padding: "10px 14px",
  borderRadius: "8px",
  border: "1px solid var(--app-ghost-action-border)",
  background: "var(--app-ghost-action-bg)",
  color: "var(--app-ghost-action-fg)",
  textDecoration: "none",
  fontWeight: 700,
  cursor: "pointer",
} as const;

const formLabelStyle = {
  display: "grid",
  gap: "6px",
  fontSize: "13px",
  fontWeight: 700,
  color: "var(--app-text-muted)",
} as const;

const reviewInputStyle = {
  width: "100%",
  boxSizing: "border-box" as const,
  border: "1px solid var(--app-input-border)",
  borderRadius: "12px",
  padding: "10px 12px",
  fontSize: "14px",
  color: "var(--app-input-fg)",
  background: "var(--app-input-bg)",
} as const;

const tagStyle = {
  borderRadius: "999px",
  background: "var(--app-tag-bg)",
  color: "var(--app-tag-fg)",
  padding: "4px 10px",
  fontSize: "12px",
  fontWeight: 700,
} as const;

const buttonLinkStyle = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  padding: "10px 14px",
  borderRadius: "8px",
  border: "1px solid var(--app-primary-action-border)",
  background: "var(--app-primary-action-bg)",
  color: "var(--app-primary-action-fg)",
  textDecoration: "none",
  fontWeight: 700,
} as const;

const secondaryLinkStyle = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  padding: "10px 14px",
  borderRadius: "8px",
  border: "1px solid var(--app-secondary-action-border)",
  background: "var(--app-secondary-action-bg)",
  color: "var(--app-secondary-action-fg)",
  textDecoration: "none",
  fontWeight: 700,
} as const;

const errorStyle = {
  border: "1px solid #fecaca",
  background: "#fff1f2",
  color: "#be123c",
  borderRadius: "12px",
  padding: "12px 14px",
  fontSize: "13px",
  marginBottom: "16px",
} as const;
