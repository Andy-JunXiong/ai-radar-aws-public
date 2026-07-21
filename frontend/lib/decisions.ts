"use client";

import { apiUrl } from "@/lib/api";
import { adminFetch } from "@/lib/adminAuth";

export type DecisionCard = {
  id: string;
  title?: string;
  source_context?: string | null;
  signal_refs?: string[];
  project_refs?: string[];
  thesis?: string;
  importance_score?: number;
  confidence_score?: number;
  counter_argument?: string;
  recommended_action?: string;
  action_type?: string;
  invalidation_condition?: string;
  expiry_at?: string | null;
  review_at?: string;
  status?: string;
  created_at?: string;
  updated_at?: string;
  latest_feedback_id?: string | null;
  latest_review_id?: string | null;
  provider_used?: string;
  model_used?: string;
  execution_policy?: {
    mode?: "fast" | "guarded" | "critical";
    rag_enabled?: boolean;
    citation_required?: boolean;
    verification_required?: boolean;
    max_context_chunks?: number;
    model_tier?: "cheap" | "standard" | "strong";
    fallback_allowed?: boolean;
    output_mode?: "draft" | "grounded" | "verified";
    reason?: string;
    validation_rules?: string[];
  };
  policy_metadata?: {
    final_mode?: string;
    fallback_count?: number;
    citation_validation_passed?: boolean | null;
    verification_passed?: boolean | null;
    unsupported_claims?: string[];
    notes?: string[];
    provider_used?: string;
    model_used?: string;
    execution_policy?: DecisionCard["execution_policy"];
    execution?: {
      mode?: string;
      final_mode?: string;
      validation_passed?: boolean;
    };
  };
  feedback?: {
    id?: string;
    decision_card_id?: string;
    user_action?: string;
    action_notes?: string;
    updated_at?: string;
  };
};

export type ReviewRecord = {
  id: string;
  decision_card_id?: string;
  review_date?: string;
  outcome?: string;
  what_happened?: string;
  confidence_adjustment?: number;
  notes?: string;
  status?: string;
  created_at?: string;
  updated_at?: string;
};

export type GenerateDecisionCardRequest = {
  title: string;
  signal_refs?: string[];
  project_refs?: string[];
  importance_score?: number;
  source_context?: string | null;
  context_payload: Record<string, unknown>;
};

export type CompleteReviewRequest = {
  outcome: "correct" | "partially_correct" | "wrong" | "unclear";
  what_happened: string;
  confidence_adjustment?: number;
  notes?: string;
};

export type CreateReviewRequest = {
  decision_card_id: string;
  review_date?: string | null;
  outcome?: "correct" | "partially_correct" | "wrong" | "unclear";
  what_happened?: string;
  confidence_adjustment?: number;
  notes?: string;
};

export type LearningSummary = {
  generated_at?: string;
  total_completed_reviews?: number;
  reviewed_with_linked_cards?: number;
  average_confidence_adjustment?: number;
  outcome_counts?: {
    correct?: number;
    partially_correct?: number;
    wrong?: number;
    unclear?: number;
  };
  confidence_buckets?: Array<{
    label: string;
    min: number;
    max: number;
    total: number;
    correct: number;
    partially_correct: number;
    wrong: number;
    unclear: number;
  }>;
};

export async function fetchDecisionCards(params?: {
  status?: string;
  signal_id?: string;
  project_id?: string;
  source_context?: string;
}): Promise<DecisionCard[]> {
  const url = new URL(apiUrl("/decision-cards"), window.location.origin);
  if (params?.status) url.searchParams.set("status", params.status);
  if (params?.signal_id) url.searchParams.set("signal_id", params.signal_id);
  if (params?.project_id) url.searchParams.set("project_id", params.project_id);
  if (params?.source_context) url.searchParams.set("source_context", params.source_context);
  const response = await adminFetch(url.toString(), { cache: "no-store" });
  if (!response.ok) throw new Error("Failed to load decision cards.");
  const payload = (await response.json()) as { items?: DecisionCard[] };
  return Array.isArray(payload.items) ? payload.items : [];
}

export async function fetchDecisionCard(cardId: string): Promise<DecisionCard> {
  const response = await adminFetch(apiUrl(`/decision-cards/${encodeURIComponent(cardId)}`), { cache: "no-store" });
  if (!response.ok) throw new Error("Failed to load decision card.");
  const payload = (await response.json()) as { card?: DecisionCard };
  if (!payload.card) throw new Error("Decision detail did not return a card.");
  return payload.card;
}

export async function updateDecisionFeedback(
  cardId: string,
  userAction: "saved" | "ignored" | "acted" | "deferred",
  actionNotes = "",
): Promise<DecisionCard> {
  const response = await adminFetch(apiUrl(`/decision-cards/${encodeURIComponent(cardId)}/feedback`), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      user_action: userAction,
      action_notes: actionNotes,
    }),
  });
  if (!response.ok) throw new Error("Failed to update decision status.");
  const payload = (await response.json()) as { card?: DecisionCard };
  if (!payload.card) throw new Error("Decision update did not return a card.");
  return payload.card;
}

export async function fetchDueReviews(): Promise<ReviewRecord[]> {
  const response = await adminFetch(apiUrl("/reviews/due"), { cache: "no-store" });
  if (!response.ok) throw new Error("Failed to load due reviews.");
  const payload = (await response.json()) as { items?: ReviewRecord[] };
  return Array.isArray(payload.items) ? payload.items : [];
}

export async function fetchReviews(params?: {
  decision_card_id?: string;
  status?: string;
}): Promise<ReviewRecord[]> {
  const url = new URL(apiUrl("/reviews"), window.location.origin);
  if (params?.decision_card_id) url.searchParams.set("decision_card_id", params.decision_card_id);
  if (params?.status) url.searchParams.set("status", params.status);
  const response = await adminFetch(url.toString(), { cache: "no-store" });
  if (!response.ok) throw new Error("Failed to load reviews.");
  const payload = (await response.json()) as { items?: ReviewRecord[] };
  return Array.isArray(payload.items) ? payload.items : [];
}

export async function generateDecisionCard(payload: GenerateDecisionCardRequest): Promise<DecisionCard> {
  const response = await adminFetch(apiUrl("/decision-cards/generate"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error("Failed to generate decision card.");
  const data = (await response.json()) as { card?: DecisionCard };
  if (!data.card) throw new Error("Decision generation did not return a card.");
  return data.card;
}

export async function completeReview(reviewId: string, payload: CompleteReviewRequest): Promise<ReviewRecord> {
  const response = await adminFetch(apiUrl(`/reviews/${encodeURIComponent(reviewId)}/complete`), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error("Failed to complete review.");
  const data = (await response.json()) as { review?: ReviewRecord };
  if (!data.review) throw new Error("Review completion did not return a review.");
  return data.review;
}

export async function createReview(payload: CreateReviewRequest): Promise<ReviewRecord> {
  const response = await adminFetch(apiUrl("/reviews"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error("Failed to create review.");
  const data = (await response.json()) as { review?: ReviewRecord };
  if (!data.review) throw new Error("Review creation did not return a review.");
  return data.review;
}

export async function fetchLearningSummary(): Promise<LearningSummary> {
  const response = await adminFetch(apiUrl("/reviews/learning-summary"), { cache: "no-store" });
  if (!response.ok) throw new Error("Failed to load learning summary.");
  const data = (await response.json()) as { summary?: LearningSummary };
  return data.summary || {};
}
