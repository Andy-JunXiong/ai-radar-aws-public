"use client";

import Link from "next/link";
import { Suspense, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";

import AppContainer from "@/components/AppContainer";
import RequireAdminAuth from "@/components/RequireAdminAuth";
import { DecisionCard, ReviewRecord, createReview, fetchDecisionCard, fetchReviews } from "@/lib/decisions";

export default function DecisionDetailPage() {
  return (
    <Suspense fallback={<DecisionDetailSkeleton />}>
      <DecisionDetailContent />
    </Suspense>
  );
}

function DecisionDetailContent() {
  const searchParams = useSearchParams();
  const id = searchParams.get("id") || "";

  const [card, setCard] = useState<DecisionCard | null>(null);
  const [reviews, setReviews] = useState<ReviewRecord[]>([]);
  const [loading, setLoading] = useState(Boolean(id));
  const [error, setError] = useState("");
  const [reviewMessage, setReviewMessage] = useState("");
  const [reviewCreating, setReviewCreating] = useState(false);

  useEffect(() => {
    if (!id) return;

    let cancelled = false;

    async function load() {
      try {
        setLoading(true);
        setError("");
        const [loadedCard, loadedReviews] = await Promise.all([
          fetchDecisionCard(id),
          fetchReviews({ decision_card_id: id }),
        ]);
        if (!cancelled) {
          setCard(loadedCard);
          setReviews(loadedReviews);
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : "Failed to load decision detail.");
          setCard(null);
          setReviews([]);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void load();

    return () => {
      cancelled = true;
    };
  }, [id]);

  const latestReview = useMemo(() => reviews[0] || null, [reviews]);
  const hasOpenReview = useMemo(
    () => reviews.some((review) => review.status !== "completed"),
    [reviews],
  );

  const handleCreateReview = async () => {
    if (!card || reviewCreating || hasOpenReview) return;
    try {
      setReviewCreating(true);
      setReviewMessage("");
      const review = await createReview({
        decision_card_id: card.id,
        review_date: card.review_at || null,
        outcome: "unclear",
        what_happened: "",
        confidence_adjustment: 0,
        notes: "",
      });
      setReviews((current) => [review, ...current]);
      setReviewMessage("Review created. It is now available in the Reflections review queue.");
    } catch (createError) {
      setReviewMessage(createError instanceof Error ? createError.message : "Failed to create review.");
    } finally {
      setReviewCreating(false);
    }
  };

  const title = card?.title || "Decision Detail";

  return (
    <AppContainer style={{ paddingTop: "24px" }}>
      <RequireAdminAuth>
        <div style={headerPanelStyle}>
          <div>
            <div style={eyebrowStyle}>Workspace</div>
            <h1 style={pageTitleStyle}>{title}</h1>
            <p style={descriptionStyle}>Review one decision card, its current action state, and its review history.</p>
          </div>
          <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
            <Link href="/workspace" style={primaryButtonStyle}>
              Back to Workspace
            </Link>
            <Link href="/workspace/decisions" style={secondaryButtonStyle}>
              Decision Cards
            </Link>
          </div>
        </div>

        {!id ? <StatePanel title="Missing Decision ID" message="Open this page from a decision card link." /> : null}
        {id && loading ? <StatePanel title="Loading" message="Loading decision detail..." /> : null}
        {id && !loading && error ? <StatePanel title="Error" message={error} tone="error" /> : null}

        {id && !loading && !error && card ? (
          <>
            <section style={panelStyle}>
              <div style={sectionHeaderStyle}>
                <div>
                  <div style={eyebrowStyle}>Decision Summary</div>
                  <h2 style={sectionTitleStyle}>Current decision state</h2>
                </div>
              </div>

              <div style={metaGridStyle}>
                <MetaCard label="Status" value={card.status || "new"} />
                <MetaCard label="Confidence" value={card.confidence_score ?? "n/a"} />
                <MetaCard
                  label="Review Date"
                  value={card.review_at ? new Date(card.review_at).toLocaleDateString() : "n/a"}
                />
              </div>

              {card.thesis ? <TextBlock label="Thesis" value={card.thesis} /> : null}
              {card.recommended_action ? <TextBlock label="Recommended Action" value={card.recommended_action} /> : null}
              {card.counter_argument ? <TextBlock label="Counter Argument" value={card.counter_argument} /> : null}
              {card.invalidation_condition ? (
                <TextBlock label="Invalidation Condition" value={card.invalidation_condition} />
              ) : null}
            </section>

            <section style={panelStyle}>
              <div style={sectionHeaderStyle}>
                <div>
                  <div style={eyebrowStyle}>Action Status</div>
                  <h2 style={sectionTitleStyle}>Latest user action</h2>
                </div>
              </div>

              {card.feedback ? (
                <div style={{ display: "grid", gap: "10px" }}>
                  <div style={bodyTextStyle}>
                    <strong>Action:</strong> {card.feedback.user_action || "n/a"}
                  </div>
                  <div style={bodyTextStyle}>
                    <strong>Updated:</strong>{" "}
                    {card.feedback.updated_at ? new Date(card.feedback.updated_at).toLocaleString() : "n/a"}
                  </div>
                  {card.feedback.action_notes ? (
                    <div style={bodyTextStyle}>
                      <strong>Notes:</strong> {card.feedback.action_notes}
                    </div>
                  ) : null}
                </div>
              ) : (
                <div style={emptyStyle}>No feedback recorded yet.</div>
              )}
            </section>

            <section style={panelStyle}>
              <div style={sectionHeaderStyle}>
                <div>
                  <div style={eyebrowStyle}>Review History</div>
                  <h2 style={sectionTitleStyle}>{reviews.length} review(s)</h2>
                </div>
                <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
                  {!hasOpenReview ? (
                    <button
                      type="button"
                      onClick={() => void handleCreateReview()}
                      disabled={reviewCreating}
                      style={{
                        ...secondaryButtonStyle,
                        cursor: reviewCreating ? "not-allowed" : "pointer",
                        opacity: reviewCreating ? 0.7 : 1,
                      }}
                    >
                      {reviewCreating ? "Creating..." : "Create Review"}
                    </button>
                  ) : null}

                  {latestReview?.status !== "completed" ? (
                    <Link href="/reflections" style={primaryButtonStyle}>
                      Complete Review
                    </Link>
                  ) : null}
                </div>
              </div>

              {reviewMessage ? (
                <div
                  style={{
                    ...messageStyle,
                    color: reviewMessage.startsWith("Failed") ? "#b91c1c" : "#166534",
                    borderColor: reviewMessage.startsWith("Failed") ? "#fecaca" : "#bbf7d0",
                  }}
                >
                  {reviewMessage}
                </div>
              ) : null}

              {reviews.length ? (
                <div style={{ display: "grid", gap: "12px" }}>
                  {reviews.map((review) => (
                    <article key={review.id} style={recordCardStyle}>
                      <div style={recordHeaderStyle}>
                        <h3 style={recordTitleStyle}>
                          {review.status === "completed" ? review.outcome || "completed" : "draft"}
                        </h3>
                        <span style={mutedTextStyle}>
                          {review.updated_at ? new Date(review.updated_at).toLocaleString() : "n/a"}
                        </span>
                      </div>

                      {review.what_happened ? (
                        <div style={{ ...bodyTextStyle, marginTop: "10px" }}>{review.what_happened}</div>
                      ) : null}

                      <div style={metadataRowStyle}>
                        <span>Confidence adj: {review.confidence_adjustment ?? 0}</span>
                        <span>Status: {review.status || "draft"}</span>
                      </div>

                      {review.notes ? (
                        <div style={{ ...noteBlockStyle, marginTop: "10px" }}>
                          <div style={blockLabelStyle}>Notes</div>
                          <div style={bodyTextStyle}>{review.notes}</div>
                        </div>
                      ) : null}
                    </article>
                  ))}
                </div>
              ) : (
                <div style={emptyStyle}>No review history yet.</div>
              )}
            </section>
          </>
        ) : null}
      </RequireAdminAuth>
    </AppContainer>
  );
}

function DecisionDetailSkeleton() {
  return (
    <AppContainer style={{ paddingTop: "24px" }}>
      <RequireAdminAuth>
        <div style={headerPanelStyle}>
          <div>
            <div style={eyebrowStyle}>Workspace</div>
            <h1 style={pageTitleStyle}>Decision Detail</h1>
            <p style={descriptionStyle}>Loading decision detail...</p>
          </div>
          <Link href="/workspace" style={primaryButtonStyle}>
            Back to Workspace
          </Link>
        </div>
        <StatePanel title="Loading" message="Loading decision detail..." />
      </RequireAdminAuth>
    </AppContainer>
  );
}

function StatePanel({ title, message, tone = "neutral" }: { title: string; message: string; tone?: "neutral" | "error" }) {
  return (
    <section style={{ ...panelStyle, borderColor: tone === "error" ? "#fecaca" : "#e5e7eb" }}>
      <div style={eyebrowStyle}>{title}</div>
      <p style={{ ...bodyTextStyle, margin: "6px 0 0", color: tone === "error" ? "#991b1b" : "#6b7280" }}>
        {message}
      </p>
    </section>
  );
}

function MetaCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div style={metaCardStyle}>
      <div style={blockLabelStyle}>{label}</div>
      <div style={metaValueStyle}>{value}</div>
    </div>
  );
}

function TextBlock({ label, value }: { label: string; value: string }) {
  return (
    <div style={noteBlockStyle}>
      <div style={blockLabelStyle}>{label}</div>
      <div style={bodyTextStyle}>{value}</div>
    </div>
  );
}

const headerPanelStyle = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  gap: "18px",
  flexWrap: "wrap" as const,
  border: "1px solid #e5e7eb",
  borderRadius: "20px",
  background: "#ffffff",
  padding: "18px",
  marginBottom: "20px",
  boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
} as const;

const panelStyle = {
  border: "1px solid #e5e7eb",
  borderRadius: "20px",
  background: "#ffffff",
  padding: "18px",
  marginBottom: "20px",
  boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
} as const;

const sectionHeaderStyle = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  gap: "12px",
  flexWrap: "wrap" as const,
  marginBottom: "14px",
} as const;

const metaGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
  gap: "12px",
  marginBottom: "14px",
} as const;

const metaCardStyle = {
  border: "1px solid #e5e7eb",
  borderRadius: "18px",
  background: "#ffffff",
  padding: "18px",
  boxShadow: "0 4px 14px rgba(15, 23, 42, 0.04)",
} as const;

const recordCardStyle = {
  border: "1px solid #e5e7eb",
  borderRadius: "18px",
  background: "#ffffff",
  padding: "18px",
  boxShadow: "0 4px 14px rgba(15, 23, 42, 0.04)",
} as const;

const recordHeaderStyle = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  gap: "12px",
  flexWrap: "wrap" as const,
} as const;

const metadataRowStyle = {
  display: "flex",
  gap: "12px",
  flexWrap: "wrap" as const,
  marginTop: "10px",
  color: "#6b7280",
  fontSize: "13px",
} as const;

const noteBlockStyle = {
  border: "1px solid #e5e7eb",
  borderRadius: "8px",
  background: "#ffffff",
  padding: "14px 16px",
  marginTop: "12px",
} as const;

const messageStyle = {
  border: "1px solid #e5e7eb",
  borderRadius: "8px",
  background: "#ffffff",
  padding: "12px 14px",
  marginBottom: "12px",
  fontSize: "14px",
  lineHeight: 1.6,
} as const;

const eyebrowStyle = {
  color: "#6b7280",
  fontSize: "12px",
  fontWeight: 700,
  textTransform: "uppercase" as const,
  letterSpacing: "0.4px",
} as const;

const pageTitleStyle = {
  margin: "4px 0 0",
  color: "#111827",
  fontSize: "18px",
  fontWeight: 600,
  lineHeight: 1.35,
} as const;

const sectionTitleStyle = {
  margin: "4px 0 0",
  color: "#111827",
  fontSize: "16px",
  fontWeight: 600,
  lineHeight: 1.35,
} as const;

const descriptionStyle = {
  margin: "6px 0 0",
  color: "#6b7280",
  fontSize: "13px",
  lineHeight: 1.5,
  maxWidth: "760px",
} as const;

const blockLabelStyle = {
  color: "#6b7280",
  fontSize: "12px",
  fontWeight: 700,
  textTransform: "uppercase" as const,
  letterSpacing: "0.4px",
  marginBottom: "6px",
} as const;

const bodyTextStyle = {
  color: "#374151",
  fontSize: "14px",
  lineHeight: 1.7,
} as const;

const emptyStyle = {
  color: "#6b7280",
  fontSize: "14px",
} as const;

const mutedTextStyle = {
  color: "#6b7280",
  fontSize: "13px",
} as const;

const metaValueStyle = {
  color: "#111827",
  fontSize: "24px",
  fontWeight: 700,
  lineHeight: 1.1,
} as const;

const recordTitleStyle = {
  margin: 0,
  color: "#111827",
  fontSize: "18px",
  fontWeight: 500,
  lineHeight: 1.35,
  textTransform: "capitalize" as const,
} as const;

const primaryButtonStyle = {
  display: "inline-flex",
  alignItems: "center",
  border: "1px solid #111827",
  borderRadius: "10px",
  background: "#111827",
  color: "#ffffff",
  padding: "7px 12px",
  textDecoration: "none",
  fontSize: "13px",
  fontWeight: 600,
} as const;

const secondaryButtonStyle = {
  display: "inline-flex",
  alignItems: "center",
  border: "1px solid #d1d5db",
  borderRadius: "10px",
  background: "#ffffff",
  color: "#111827",
  padding: "7px 12px",
  textDecoration: "none",
  fontSize: "13px",
  fontWeight: 600,
} as const;
