"use client";

import AppContainer from "@/components/AppContainer";
import VerificationGateNote from "@/components/VerificationGateNote";
import Link from "next/link";
import { Suspense, useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { useSearchParams } from "next/navigation";
import { Activity, Database, FileUp, Pin, PinOff, Radar, Search, SlidersHorizontal, Star, X } from "lucide-react";
import { API_BASE } from "@/lib/api";
import { adminFetch } from "@/lib/adminAuth";
import { buildBetaUserHeaders, getStoredBetaUserId } from "@/lib/betaUser";
import { createTimeoutController, isAbortError } from "@/lib/requestTimeout";
const SIGNALS_CACHE_KEY = "ai-radar-signals-cache-v9";
const SIGNALS_CACHE_TTL_MS = 60 * 60 * 1000;
const SIGNALS_STALE_CACHE_TTL_MS = 24 * 60 * 60 * 1000;
const SIGNALS_REQUEST_TIMEOUT_MS = 20000;
const SIGNALS_AUTO_RETRY_DELAY_MS = 1500;
const SIGNALS_AUTO_RETRY_TIMEOUT_MS = 60000;

type SignalStatus = "all" | "pending" | "saved" | "analyzed" | "completed" | "rejected";
type SourceFilter = "all" | "auto" | "manual";
type ReviewPriorityFilter =
  | "all"
  | "do_not_act"
  | "review_required"
  | "review_before_action"
  | "ready_for_low_risk_review"
  | "unknown";

type TimelineDateMode = "collected" | "published";

type VerificationMetadata = {
  verification_status?: string;
  confidence_score?: number;
  confidence_label?: string;
  allowed_downstream_actions?: string[];
  blocked_downstream_actions?: string[];
  claim_support_summary?: Record<string, number>;
};

type SignalItem = {
  id: string;
  signal_id: string;
  title: string;
  summary: string;
  source: string;
  published_at?: string | null;
  collected_at?: string | null;
  status?: string;
  saved_reason?: string | null;
  starred?: boolean;
  starred_at?: string | null;
  url?: string | null;
  link?: string | null;
  source_url?: string | null;
  source_excerpt?: string | null;
  source_excerpt_length?: number | null;
  topic?: string;
  insight_status?: string;
  insight_status_label?: string;
  score?: number;
  is_manual?: boolean;
  file_count?: number;
  file_types?: string[];
  manual_session_id?: string | null;
  analysis_status?: string;
  workspace_saved?: boolean;
  workspace_file_name?: string | null;
  workspace_saved_at?: string | null;
  provider_used?: string | null;
  subscription_score_percent?: number | null;
  subscription_topic_priority?: string;
  auto_action_hint?: string;
  verification?: VerificationMetadata | null;
  policy_metadata?: {
    verification?: VerificationMetadata | null;
  } | null;
};

type Counts = {
  all: number;
  pending: number;
  saved: number;
  analyzed: number;
  completed: number;
  rejected: number;
};

type SignalsCachePayload = {
  signals: SignalItem[];
  manualSignals: SignalItem[];
  counts: Counts;
};

type ActionNotice = {
  tone: "info" | "success" | "error";
  message: string;
};

type SignalsCacheStore = {
  timestamp: number;
  payload: SignalsCachePayload | null;
};

type TimelineLoadState = {
  source: "none" | "cache" | "api";
  loadedAt: number | null;
  requestMs: number | null;
  cacheAgeMs: number | null;
};

const DEFAULT_COUNTS: Counts = {
  all: 0,
  pending: 0,
  saved: 0,
  analyzed: 0,
  completed: 0,
  rejected: 0,
};

function formatDateTime(value?: string | null) {
  if (!value) return "N/A";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

function normalizeStatus(status?: string): Exclude<SignalStatus, "all"> {
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
        background: "var(--app-tag-bg)",
        color: "var(--app-tag-fg)",
        border: "1px solid var(--app-chip-border)",
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

function getStatusSubLabel(statusKey: SignalStatus) {
  switch (statusKey) {
    case "pending":
      return "Waiting to review";
    case "saved":
      return "Keep for later";
    case "analyzed":
      return "Ready for completion note";
    case "completed":
      return "In workspace";
    case "rejected":
      return "Low value now";
    default:
      return "All intelligence";
  }
}

function getSourceSubLabel(sourceKey: SourceFilter) {
  switch (sourceKey) {
    case "auto":
      return "RSS and feed signals";
    case "manual":
      return "Uploaded sessions";
    default:
      return "All sources";
  }
}

function getStatusFilterLabel(statusKey: SignalStatus) {
  switch (statusKey) {
    case "all":
      return "All";
    default:
      return getStatusLabel(statusKey);
  }
}

function getSourceFilterLabel(sourceKey: SourceFilter) {
  switch (sourceKey) {
    case "auto":
      return "Auto";
    case "manual":
      return "Manual";
    default:
      return "All Sources";
  }
}

function getProcessingBadgeStyle(status?: string, isManual?: boolean) {
  if (isManual) {
    return {
      background: "var(--app-tag-bg)",
      color: "var(--app-tag-fg)",
      border: "1px solid var(--app-chip-border)",
    };
  }

  if (status === "auto_generated") {
    return {
      background: "var(--app-success-bg)",
      color: "var(--app-success-fg)",
      border: "1px solid var(--app-success-border)",
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

function formatScore(score?: number) {
  if (typeof score !== "number" || Number.isNaN(score)) return "N/A";
  return score.toFixed(2);
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
      return normalized
        .replace(/_/g, " ")
        .replace(/\b\w/g, (char) => char.toUpperCase());
  }
}

function getReviewPrioritySubLabel(priorityKey: ReviewPriorityFilter) {
  switch (priorityKey) {
    case "do_not_act":
      return "Unsupported or contradicted";
    case "review_required":
      return "Needs human check";
    case "review_before_action":
      return "Partial support";
    case "ready_for_low_risk_review":
      return "Verified enough to review";
    case "unknown":
      return "No verification yet";
    default:
      return "All verification states";
  }
}

function getReviewPriorityFilterLabel(priorityKey: ReviewPriorityFilter) {
  switch (priorityKey) {
    case "do_not_act":
      return "Do Not Act";
    case "review_required":
      return "Review Required";
    case "review_before_action":
      return "Review Before Action";
    case "ready_for_low_risk_review":
      return "Low-Risk Review";
    case "unknown":
      return "Unknown";
    default:
      return "All Review";
  }
}

function formatClaimSupportSummary(summary?: Record<string, number>): string {
  const entries = Object.entries(summary || {}).filter(([, count]) => count > 0);
  return entries
    .map(([supportLevel, count]) => `${formatCompactLabel(supportLevel)}: ${count}`)
    .join(" | ");
}

function getReviewPriority({
  verificationStatus,
  blockedActions,
  supportSummary,
}: {
  verificationStatus?: string;
  blockedActions: string[];
  supportSummary: Record<string, number>;
}): { key: ReviewPriorityFilter; label: string; color: string; background: string; border: string } {
  const status = String(verificationStatus || "").toLowerCase();
  const unsupported = (supportSummary.unsupported || 0) + (supportSummary.contradicted || 0);
  const inferred = supportSummary.inferred || 0;
  const blocksAction =
    blockedActions.includes("low_risk_action_candidate") ||
    blockedActions.includes("strong_recommendation");

  if (status === "unsupported" || status === "contradicted" || unsupported > 0) {
    return { key: "do_not_act", label: "Do Not Act", color: "var(--app-danger-fg)", background: "var(--app-danger-bg)", border: "1px solid var(--app-danger-border)" };
  }
  if (status === "not_verifiable" || status === "weakly_supported" || inferred > 0) {
    return { key: "review_required", label: "Review Required", color: "var(--app-warning-fg)", background: "var(--app-warning-bg)", border: "1px solid var(--app-warning-border)" };
  }
  if (status === "partially_verified" || blocksAction) {
    return { key: "review_before_action", label: "Review Before Action", color: "var(--app-warning-fg)", background: "var(--app-warning-bg)", border: "1px solid var(--app-warning-border)" };
  }
  if (status === "verified") {
    return { key: "ready_for_low_risk_review", label: "Ready For Low-Risk Review", color: "var(--app-success-fg)", background: "var(--app-success-bg)", border: "1px solid var(--app-success-border)" };
  }
  return { key: "unknown", label: "Review Unknown", color: "var(--app-chip-fg)", background: "var(--app-chip-bg)", border: "1px solid var(--app-chip-border)" };
}

function getSignalVerification(signal: SignalItem): VerificationMetadata | null {
  return signal.verification || signal.policy_metadata?.verification || null;
}

function getSignalReviewPriority(signal: SignalItem) {
  const verification = getSignalVerification(signal);
  if (!verification) {
    return null;
  }

  return getReviewPriority({
    verificationStatus: verification.verification_status,
    blockedActions: verification.blocked_downstream_actions || [],
    supportSummary: verification.claim_support_summary || {},
  });
}

function isManualSignal(item: Pick<SignalItem, "is_manual" | "source" | "manual_session_id" | "signal_id" | "id">) {
  return (
    !!item.is_manual ||
    !!item.manual_session_id ||
    String(item.source || "").trim().toLowerCase() === "manual" ||
    String(item.signal_id || item.id || "").startsWith("manual_")
  );
}

function getSignalSearchText(item: SignalItem) {
  return [
    item.id,
    item.signal_id,
    item.title,
    item.summary,
    item.source,
    item.topic,
    item.status,
    item.insight_status,
    item.insight_status_label,
    item.provider_used,
    item.url,
    item.link,
    item.source_url,
    item.manual_session_id,
    item.analysis_status,
    item.saved_reason,
    item.verification?.verification_status,
    item.policy_metadata?.verification?.verification_status,
    item.source_excerpt,
    ...(item.file_types || []),
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
}

function getHighlightTokens(query: string) {
  return Array.from(
    new Set(
      query
        .trim()
        .toLowerCase()
        .split(/\s+/)
        .filter(Boolean)
    )
  ).sort((left, right) => right.length - left.length);
}

function findNextHighlight(text: string, tokens: string[], fromIndex: number) {
  const lowerText = text.toLowerCase();
  let nextStart = -1;
  let nextToken = "";

  for (const token of tokens) {
    const start = lowerText.indexOf(token, fromIndex);
    if (start === -1) continue;
    if (nextStart === -1 || start < nextStart || (start === nextStart && token.length > nextToken.length)) {
      nextStart = start;
      nextToken = token;
    }
  }

  if (nextStart === -1) return null;
  return { start: nextStart, end: nextStart + nextToken.length };
}

function HighlightedText({ text, query }: { text: string; query: string }) {
  const tokens = getHighlightTokens(query);
  if (!text || tokens.length === 0) return <>{text}</>;

  const parts: ReactNode[] = [];
  let cursor = 0;

  while (cursor < text.length) {
    const match = findNextHighlight(text, tokens, cursor);
    if (!match) {
      parts.push(text.slice(cursor));
      break;
    }

    if (match.start > cursor) {
      parts.push(text.slice(cursor, match.start));
    }

    parts.push(
      <mark key={`${match.start}-${match.end}-${parts.length}`} style={searchHighlightStyle}>
        {text.slice(match.start, match.end)}
      </mark>
    );
    cursor = match.end;
  }

  return <>{parts}</>;
}

function textMatchesHighlightQuery(text: string | null | undefined, query: string) {
  if (!text) return false;
  const lowerText = text.toLowerCase();
  return getHighlightTokens(query).some((token) => lowerText.includes(token));
}

function getHighlightSnippet(text: string | null | undefined, query: string, maxLength = 220) {
  if (!text || !textMatchesHighlightQuery(text, query)) return "";

  const lowerText = text.toLowerCase();
  const tokens = getHighlightTokens(query);
  const firstMatch = tokens
    .map((token) => lowerText.indexOf(token))
    .filter((index) => index >= 0)
    .sort((left, right) => left - right)[0];

  if (firstMatch === undefined) return "";
  const start = Math.max(0, firstMatch - 70);
  const end = Math.min(text.length, start + maxLength);
  const prefix = start > 0 ? "... " : "";
  const suffix = end < text.length ? " ..." : "";
  return `${prefix}${text.slice(start, end).trim()}${suffix}`;
}

function getSubscriptionBadgeStyle(kind?: string) {
  switch ((kind || "").trim()) {
    case "boosted":
      return {
        background: "var(--app-tag-bg)",
        color: "var(--app-tag-fg)",
        border: "1px solid var(--app-chip-border)",
      };
    case "preferred":
      return {
        background: "var(--app-info-bg)",
        color: "var(--app-info-fg)",
        border: "1px solid var(--app-info-border)",
      };
    case "auto_analyze_candidate":
      return {
        background: "var(--app-success-bg)",
        color: "var(--app-success-fg)",
        border: "1px solid var(--app-success-border)",
      };
    case "auto_backlog_candidate":
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

function getDateKeyFromRaw(raw?: string | null) {
  if (!raw) return "Unknown Date";

  const date = new Date(raw);
  if (Number.isNaN(date.getTime())) return "Unknown Date";

  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");

  return `${year}-${month}-${day}`;
}

function getTimelineDateKey(
  signal: Pick<SignalItem, "collected_at" | "published_at" | "is_manual">,
  mode: TimelineDateMode,
) {
  const raw = mode === "collected"
    ? signal.collected_at || signal.published_at
    : signal.is_manual
      ? signal.collected_at || signal.published_at
      : signal.published_at || signal.collected_at;

  return getDateKeyFromRaw(raw);
}

function getTimelineDateSource(
  signal: Pick<SignalItem, "collected_at" | "published_at" | "is_manual">,
  mode: TimelineDateMode,
) {
  if (mode === "collected") {
    return signal.collected_at ? "Collection batch" : "Information date";
  }

  if (signal.is_manual) {
    return signal.collected_at ? "Collection batch" : "Information date";
  }

  return signal.published_at ? "Information date" : "Collection batch";
}

function getTimelineGroupDescription(
  items: Array<Pick<SignalItem, "collected_at" | "published_at" | "is_manual">>,
  mode: TimelineDateMode,
) {
  const sources = new Set(items.map((item) => getTimelineDateSource(item, mode)));

  if (sources.size === 1) {
    const [source] = Array.from(sources);
    return source === "Information date"
      ? "Source published or originated on this date"
      : "Entered the backend snapshot on this date";
  }

  return "Published/originated or entered the backend snapshot on this date";
}

function formatDateHeading(dateKey: string) {
  if (dateKey === "Unknown Date") return dateKey;

  const date = new Date(`${dateKey}T00:00:00`);
  if (Number.isNaN(date.getTime())) return dateKey;

  return date.toLocaleDateString(undefined, {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

function getLatestKnownDateKey(keys: string[]) {
  return keys.filter((key) => key !== "Unknown Date").sort().pop() || "Unknown Date";
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function readSignalsCache(): SignalsCacheStore | null {
  if (typeof window === "undefined") return null;

  try {
    const raw = sessionStorage.getItem(SIGNALS_CACHE_KEY);
    if (!raw) return null;
    const parsed: unknown = JSON.parse(raw);
    if (!isRecord(parsed)) return null;
    const timestamp = parsed.timestamp;
    const payload = parsed.payload;

    if (typeof timestamp !== "number") {
      return null;
    }

    return {
      timestamp,
      payload: isValidCachedPayload(payload) ? payload : null,
    };
  } catch {
    return null;
  }
}

function writeSignalsCache(
  payload: {
    signals: SignalItem[];
    manualSignals: SignalItem[];
    counts: Counts;
  }
) {
  if (typeof window === "undefined") return;

  try {
    const existing: SignalsCacheStore = readSignalsCache() || {
      timestamp: Date.now(),
      payload: null,
    };
    existing.timestamp = Date.now();
    existing.payload = payload;
    sessionStorage.setItem(SIGNALS_CACHE_KEY, JSON.stringify(existing));
  } catch {
    // ignore cache errors
  }
}

function isValidCachedPayload(payload: unknown): payload is SignalsCachePayload {
  if (!isRecord(payload)) return false;
  if (!Array.isArray(payload.signals)) return false;
  if (!Array.isArray(payload.manualSignals)) return false;
  if (!isRecord(payload.counts)) return false;

  return (
    typeof payload.counts.all === "number" &&
  typeof payload.counts.pending === "number" &&
  typeof payload.counts.saved === "number" &&
  typeof payload.counts.analyzed === "number" &&
  typeof payload.counts.completed === "number" &&
  typeof payload.counts.rejected === "number"
  );
}

function getCachedSignals({ allowStale = false }: { allowStale?: boolean } = {}): SignalsCachePayload | null {
  const cache = readSignalsCache();
  if (!cache) return null;
  if (!cache.timestamp) return null;

  const cacheAgeMs = Date.now() - cache.timestamp;
  const maxCacheAgeMs = allowStale ? SIGNALS_STALE_CACHE_TTL_MS : SIGNALS_CACHE_TTL_MS;
  if (cacheAgeMs > maxCacheAgeMs) return null;

  const payload = cache.payload;
  if (!isValidCachedPayload(payload)) return null;

  return payload;
}

function getSignalsCacheAgeMs(): number | null {
  const cache = readSignalsCache();
  if (!cache?.timestamp) return null;
  return Math.max(0, Date.now() - cache.timestamp);
}

function formatLoadTimestamp(value: number | null): string {
  if (!value) return "Not loaded yet";
  return new Date(value).toLocaleTimeString();
}

function formatDuration(value: number | null): string {
  if (typeof value !== "number") return "N/A";
  if (value < 1000) return `${Math.round(value)} ms`;
  return `${(value / 1000).toFixed(1)} s`;
}

async function fetchSignalsTimeline(
  signal?: AbortSignal,
  subscriptionUserId?: string,
) {
  const attempt = async (headers: HeadersInit = {}) => {
    const response = await fetch(`${API_BASE}/signals?status=all`, {
      cache: "no-store",
      headers,
      signal,
    });

    if (!response.ok) {
      throw new Error(`Failed to load signals (${response.status})`);
    }

    return response.json();
  };

  const preferredHeaders = buildBetaUserHeaders(subscriptionUserId);

  try {
    return await attempt(preferredHeaders);
  } catch (error) {
    if (signal?.aborted) {
      throw error;
    }

    const hasPreferredHeaders = Object.keys(preferredHeaders).length > 0;
    if (!hasPreferredHeaders) {
      throw error;
    }

    return attempt();
  }
}

async function updateSignalStatus(signal: SignalItem, status: string, savedReason?: string) {
  if (signal.is_manual) {
    return { ok: true };
  }

  const res = await adminFetch(`${API_BASE}/signals/update-status`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      signal_id: signal.signal_id || signal.id,
      title: signal.title || "",
      source: signal.source || "",
      published_at: signal.published_at || "",
      collected_at: signal.collected_at || "",
      status,
      saved_reason: savedReason || null,
    }),
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `Failed to update status (${res.status})`);
  }

  return res.json();
}

async function updateSignalStar(signal: SignalItem, starred: boolean) {
  const res = await adminFetch(`${API_BASE}/signals/update-star`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      signal_id: signal.signal_id || signal.id,
      title: signal.title || "",
      source: signal.source || "",
      published_at: signal.published_at || "",
      collected_at: signal.collected_at || "",
      starred,
    }),
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `Failed to update star (${res.status})`);
  }

  return res.json();
}

function actionButtonStyle(border: string, background: string, busy: boolean) {
  return {
    padding: "7px 12px",
    borderRadius: "8px",
    border: `1px solid ${border}`,
    background,
    color: "var(--app-danger-fg)",
    cursor: busy ? "not-allowed" : "pointer",
    opacity: busy ? 0.7 : 1,
    fontSize: "13px",
    fontWeight: 600 as const,
  };
}

function FilterButton({
  label,
  subLabel,
  count,
  active,
  onClick,
}: {
  label: string;
  subLabel: string;
  count: number;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      style={{
        border: active ? "1px solid var(--app-primary-action-border)" : "1px solid var(--app-secondary-action-border)",
        background: active ? "var(--app-primary-action-bg)" : "var(--app-secondary-action-bg)",
        color: active ? "var(--app-primary-action-fg)" : "var(--app-secondary-action-fg)",
        borderRadius: "8px",
        padding: "12px 14px",
        cursor: "pointer",
        minWidth: "138px",
        textAlign: "left",
        transition: "all 0.18s ease",
        boxShadow: active ? "var(--app-surface-shadow)" : "none",
      }}
    >
      <div style={{ fontSize: "14px", fontWeight: 700 }}>
        {label} ({count})
      </div>
      <div style={{ fontSize: "12px", opacity: active ? 0.9 : 0.7, marginTop: "4px" }}>
        {subLabel}
      </div>
    </button>
  );
}

function SummaryCard({
  label,
  value,
  subLabel,
}: {
  label: string;
  value: number;
  subLabel: string;
}) {
  return (
    <div
      style={{
        border: "1px solid var(--app-surface-border)",
        borderRadius: "8px",
        padding: "18px",
        background: "var(--app-surface-muted-bg)",
        minWidth: "180px",
        boxShadow: "var(--app-surface-shadow)",
      }}
    >
      <div style={{ fontSize: "12px", color: "var(--app-text-subtle)", marginBottom: "10px", fontWeight: 600 }}>
        {label}
      </div>
      <div style={{ fontSize: "32px", fontWeight: 800, color: "var(--app-text-strong)", lineHeight: 1 }}>
        {value}
      </div>
      <div style={{ fontSize: "12px", color: "var(--app-text-subtle)", marginTop: "8px", lineHeight: 1.5 }}>
        {subLabel}
      </div>
    </div>
  );
}

function SectionShell({
  title,
  subtitle,
  children,
  sticky = false,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
  sticky?: boolean;
}) {
  return (
    <section
      style={{
        marginBottom: "24px",
        position: sticky ? "sticky" : "static",
        top: sticky ? "68px" : undefined,
        zIndex: sticky ? 20 : undefined,
      }}
    >
      <div
        style={{
          border: "1px solid var(--app-surface-border)",
          borderRadius: "8px",
          background: sticky ? "var(--app-surface-bg)" : "var(--app-surface-bg)",
          backdropFilter: sticky ? "blur(12px)" : undefined,
          padding: "18px",
          boxShadow: "var(--app-surface-shadow)",
        }}
      >
        <div style={{ marginBottom: "14px" }}>
          <div
            style={{
              fontSize: "13px",
              fontWeight: 700,
              color: "var(--app-text-muted)",
              textTransform: "uppercase",
              letterSpacing: "0",
              marginBottom: subtitle ? "4px" : 0,
            }}
          >
            {title}
          </div>
          {subtitle ? (
            <div style={{ fontSize: "13px", color: "var(--app-text-subtle)", lineHeight: 1.5 }}>{subtitle}</div>
          ) : null}
        </div>
        {children}
      </div>
    </section>
  );
}
function SignalsHero({
  totalItems,
  autoItems,
  manualItems,
  visibleItems,
  source,
}: {
  totalItems: number;
  autoItems: number;
  manualItems: number;
  visibleItems: number;
  source: TimelineLoadState["source"];
}) {
  const sourceLabel = source === "api" ? "Fresh API" : source === "cache" ? "Cache" : "Loading";

  return (
    <section style={signalsHeroStyle}>
      <div style={{ minWidth: 0 }}>
        <div style={signalsEyebrowStyle}>Signal Timeline</div>
        <h1 style={signalsHeroTitleStyle}>Raw intelligence, ready for review.</h1>
        <p style={signalsHeroDescriptionStyle}>
          Signals are the front door of AI Radar: auto-collected ecosystem movement and manual uploads stay reviewable before they become insights, takeaways, or actions.
        </p>
        <div style={signalsQuickActionRowStyle}>
          <Link href="/manual" style={signalsQuickActionStyle}>
            <FileUp size={16} aria-hidden="true" />
            Manual Upload
          </Link>
          <Link href="/radar" style={signalsQuickActionStyle}>
            <Radar size={16} aria-hidden="true" />
            Open Radar
          </Link>
          <Link href="/knowledge" style={signalsQuickActionStyle}>
            <Database size={16} aria-hidden="true" />
            Knowledge
          </Link>
        </div>
      </div>

      <div style={signalsHeroPanelStyle}>
        <div style={signalsHeroPanelHeaderStyle}>
          <Activity size={18} aria-hidden="true" />
          <span>{sourceLabel} timeline</span>
        </div>
        <div style={signalsHeroMetricGridStyle}>
          <SignalsHeroMetric label="Total" value={String(totalItems)} />
          <SignalsHeroMetric label="Visible" value={String(visibleItems)} />
          <SignalsHeroMetric label="Auto" value={String(autoItems)} />
          <SignalsHeroMetric label="Manual" value={String(manualItems)} />
        </div>
      </div>
    </section>
  );
}

function SignalsHeroMetric({ label, value }: { label: string; value: string }) {
  return (
    <div style={signalsHeroMetricStyle}>
      <div style={signalsHeroMetricValueStyle}>{value}</div>
      <div style={signalsHeroMetricLabelStyle}>{label}</div>
    </div>
  );
}

function buildCounts(items: SignalItem[]): Counts {
  const counts: Counts = {
    all: items.length,
    pending: 0,
    saved: 0,
    analyzed: 0,
    completed: 0,
    rejected: 0,
  };

  for (const item of items) {
    const status = normalizeStatus(item.status);
    counts[status] += 1;
  }

  return counts;
}

function SignalCard({
  signal,
  onStatusChanged,
  onStarChanged,
  onActionNotice,
  timelineDateMode,
  searchQuery,
}: {
  signal: SignalItem;
  onStatusChanged: (signalId: string, nextStatus: string, savedReason?: string | null) => void;
  onStarChanged: (signalId: string, starred: boolean, starredAt?: string | null) => void;
  onActionNotice: (notice: ActionNotice) => void;
  timelineDateMode: TimelineDateMode;
  searchQuery: string;
}) {
  const [busy, setBusy] = useState(false);
  const [starBusy, setStarBusy] = useState(false);
  const [localNotice, setLocalNotice] = useState<ActionNotice | null>(null);

  async function handleReject(e: React.MouseEvent<HTMLButtonElement>) {
    e.preventDefault();
    e.stopPropagation();

    if (signal.is_manual) return;

    const signalId = signal.signal_id || signal.id;
    const previousStatus = normalizeStatus(signal.status);
    const previousSavedReason = signal.saved_reason || null;

    setBusy(true);
    setLocalNotice({ tone: "success", message: "Rejected. Status is being saved." });
    onActionNotice({ tone: "success", message: `Rejected "${signal.title || "signal"}". Saving status...` });
    onStatusChanged(signalId, "rejected", null);

    try {
      await updateSignalStatus(signal, "rejected");
      setLocalNotice({ tone: "success", message: "Rejected. Signal status saved." });
      onActionNotice({ tone: "success", message: `Rejected "${signal.title || "signal"}". Signal status saved.` });
    } catch (error) {
      console.error(error);
      onStatusChanged(signalId, previousStatus, previousSavedReason);
      setLocalNotice({ tone: "error", message: "Failed to reject signal." });
      onActionNotice({ tone: "error", message: `Failed to reject "${signal.title || "signal"}".` });
    } finally {
      setBusy(false);
    }
  }

  const resolvedId = signal.signal_id || signal.id;
  const isStarred = Boolean(signal.starred);

  async function handleToggleStar(e: React.MouseEvent<HTMLButtonElement>) {
    e.preventDefault();
    e.stopPropagation();

    const nextStarred = !isStarred;
    const signalId = signal.signal_id || signal.id;
    const previousStarred = isStarred;
    const previousStarredAt = signal.starred_at || null;

    setStarBusy(true);
    onStarChanged(signalId, nextStarred, nextStarred ? new Date().toISOString() : null);
    onActionNotice({
      tone: "success",
      message: nextStarred
        ? `Starred "${signal.title || "signal"}".`
        : `Removed star from "${signal.title || "signal"}".`,
    });

    try {
      const data = await updateSignalStar(signal, nextStarred);
      onStarChanged(signalId, Boolean(data?.starred), data?.starred_at || null);
    } catch (error) {
      console.error(error);
      onStarChanged(signalId, previousStarred, previousStarredAt);
      setLocalNotice({ tone: "error", message: "Failed to update star." });
      onActionNotice({ tone: "error", message: `Failed to update star for "${signal.title || "signal"}".` });
    } finally {
      setStarBusy(false);
    }
  }

  let manualSessionId: string | null = null;
  if (signal.is_manual) {
    if (typeof signal.signal_id === "string" && signal.signal_id.startsWith("manual_")) {
      manualSessionId = signal.signal_id;
    } else if (typeof signal.id === "string" && signal.id.startsWith("manual_")) {
      manualSessionId = signal.id;
    } else {
      manualSessionId = signal.signal_id || signal.id;
    }
  }

  const looksManualFallback =
    !!signal.is_manual ||
    !!signal.manual_session_id ||
    String(signal.signal_id || signal.id || "").startsWith("manual_");

  const detailId = looksManualFallback
    ? signal.manual_session_id || manualSessionId || signal.signal_id || signal.id
    : resolvedId;

  const sourceUrl = signal.url || signal.link || signal.source_url || "";
  const isManual = isManualSignal(signal);
  const normalizedStatus = normalizeStatus(signal.status);
  const canRejectFromList = !isManual && normalizedStatus !== "completed" && normalizedStatus !== "rejected";
  const verification = getSignalVerification(signal);
  const claimSupportSummary = verification?.claim_support_summary || {};
  const claimSupportSummaryText = formatClaimSupportSummary(claimSupportSummary);
  const reviewPriority = getSignalReviewPriority(signal);
  const showManualHandoffEntry = isManual && normalizedStatus !== "completed";
  const topicLabel = isManual ? "Manual Upload" : signal.topic || "General AI";
  const processingLabel = isManual
    ? signal.insight_status_label || "Manual session"
    : signal.insight_status_label || "Status unknown";
  const sourceLabel = signal.source || "Unknown";
  const statusLabel = getStatusLabel(signal.status);
  const signalIdLabel = signal.signal_id || signal.id || "";
  const showSignalIdMatch = textMatchesHighlightQuery(signalIdLabel, searchQuery);
  const showSourceExcerptSnippet =
    textMatchesHighlightQuery(signal.source_excerpt, searchQuery) &&
    !textMatchesHighlightQuery(signal.title, searchQuery) &&
    !textMatchesHighlightQuery(signal.summary, searchQuery);
  const sourceExcerptSnippet = showSourceExcerptSnippet
    ? getHighlightSnippet(signal.source_excerpt, searchQuery)
    : "";

  return (
    <div
      style={{
        border: isManual ? "1px solid var(--app-surface-strong-border)" : "1px solid var(--app-surface-border)",
        padding: "18px",
        marginTop: "14px",
        borderRadius: "8px",
        background: isManual ? "var(--app-surface-muted-bg)" : "var(--app-surface-bg)",
        transition: "box-shadow 0.18s ease, transform 0.18s ease, border-color 0.18s ease",
        boxShadow: "var(--app-surface-shadow)",
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.boxShadow = "var(--app-surface-shadow)";
        e.currentTarget.style.transform = "translateY(-1px)";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.boxShadow = "var(--app-surface-shadow)";
        e.currentTarget.style.transform = "translateY(0)";
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          gap: "12px",
          alignItems: "flex-start",
        }}
      >
        <div style={{ flex: 1, minWidth: 0 }}>
          <h3
            style={{
              marginTop: 0,
              marginBottom: "10px",
              color: "var(--app-text-strong)",
              lineHeight: 1.35,
              fontSize: "18px",
            }}
          >
            <HighlightedText text={signal.title} query={searchQuery} />
          </h3>

          <div
            style={{
              display: "flex",
              gap: "8px",
              flexWrap: "wrap",
              marginBottom: "12px",
            }}
          >
            <span
              style={{
                padding: "5px 10px",
                borderRadius: "999px",
                background: "var(--app-tag-bg)",
                color: "var(--app-tag-fg)",
                border: "1px solid var(--app-chip-border)",
                fontSize: "12px",
                fontWeight: 700,
              }}
            >
              <HighlightedText text={topicLabel} query={searchQuery} />
            </span>

            <span
              style={{
                padding: "5px 10px",
                borderRadius: "999px",
                fontSize: "12px",
                fontWeight: 700,
                ...getProcessingBadgeStyle(signal.insight_status, isManual),
              }}
            >
              <HighlightedText text={processingLabel} query={searchQuery} />
            </span>

            <span
              style={{
                padding: "5px 10px",
                borderRadius: "999px",
                background: "var(--app-surface-muted-bg)",
                color: "var(--app-text-muted)",
                border: "1px solid var(--app-surface-border)",
                fontSize: "12px",
                fontWeight: 700,
              }}
            >
              {isManual ? `Files: ${signal.file_count ?? 0}` : `Score: ${formatScore(signal.score)}`}
            </span>

            {signal.subscription_topic_priority === "preferred" || signal.subscription_topic_priority === "boosted" ? (
              <span
                style={{
                  padding: "5px 10px",
                  borderRadius: "999px",
                  fontSize: "12px",
                  fontWeight: 700,
                  ...getSubscriptionBadgeStyle(signal.subscription_topic_priority),
                }}
              >
                {signal.subscription_topic_priority === "boosted" ? "Boosted Topic" : "Preferred Topic"}
              </span>
            ) : null}

            {signal.auto_action_hint ? (
              <span
                style={{
                  padding: "5px 10px",
                  borderRadius: "999px",
                  fontSize: "12px",
                  fontWeight: 700,
                  ...getSubscriptionBadgeStyle(signal.auto_action_hint),
                }}
              >
                {signal.auto_action_hint === "auto_analyze_candidate"
                  ? "Auto Analyze Candidate"
                  : "Auto Backlog Candidate"}
              </span>
            ) : null}

            {reviewPriority ? (
              <span
                style={{
                  padding: "5px 10px",
                  borderRadius: "999px",
                  fontSize: "12px",
                  fontWeight: 700,
                  background: reviewPriority.background,
                  color: reviewPriority.color,
                  border: reviewPriority.border,
                }}
              >
                {reviewPriority.label}
              </span>
            ) : null}
          </div>

          <p
            style={{
              marginTop: 0,
              marginBottom: "14px",
              lineHeight: "1.72",
              color: "var(--app-text-muted)",
              fontSize: "14px",
            }}
          >
            <HighlightedText text={signal.summary || "No summary available."} query={searchQuery} />
          </p>

          {sourceExcerptSnippet ? (
            <p style={searchMatchSnippetStyle}>
              Source excerpt: <HighlightedText text={sourceExcerptSnippet} query={searchQuery} />
            </p>
          ) : null}

          {verification ? (
            <div
              style={{
                marginTop: "-4px",
                marginBottom: "14px",
                color: "var(--app-text-subtle)",
                fontSize: "13px",
                lineHeight: 1.6,
              }}
            >
              Verification: {formatCompactLabel(verification.verification_status)}
              {verification.confidence_label ? ` | Confidence: ${formatCompactLabel(verification.confidence_label)}` : ""}
              {typeof verification.confidence_score === "number" ? ` (${verification.confidence_score.toFixed(2)})` : ""}
              {claimSupportSummaryText ? ` | ${claimSupportSummaryText}` : ""}
            </div>
          ) : null}

          {verification ? (
            <VerificationGateNote
              verification={verification}
              accentColor={reviewPriority?.color}
              style={{ marginTop: "-4px", marginBottom: "14px" }}
            />
          ) : null}

          {showManualHandoffEntry ? (
            <div
              style={{
                border: "1px solid var(--app-info-border)",
                borderRadius: "8px",
                background: "var(--app-info-bg)",
                color: "var(--app-info-fg)",
                padding: "9px 11px",
                fontSize: "13px",
                lineHeight: 1.55,
                marginTop: "-4px",
                marginBottom: "14px",
              }}
            >
              <strong>Manual handoff:</strong> open the detail page to review Manual Signal Handoff and the right-side Manual Completion Route before saving to Workspace.
            </div>
          ) : null}
        </div>

        <div
          style={{
            ...getStatusStyle(signal.status),
            borderRadius: "999px",
            padding: "6px 10px",
            fontSize: "12px",
            whiteSpace: "nowrap",
            fontWeight: 700,
          }}
        >
          <HighlightedText text={statusLabel} query={searchQuery} />
        </div>

        <button
          type="button"
          onClick={handleToggleStar}
          disabled={starBusy}
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
            cursor: starBusy ? "not-allowed" : "pointer",
            opacity: starBusy ? 0.7 : 1,
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            flex: "0 0 auto",
          }}
        >
          <Star size={17} fill={isStarred ? "currentColor" : "none"} aria-hidden="true" />
        </button>
      </div>

      <div
        style={{
          fontSize: "13px",
          color: "var(--app-text-subtle)",
          display: "flex",
          flexWrap: "wrap",
          gap: "14px",
          lineHeight: 1.6,
        }}
      >
        <span>
          Source: <HighlightedText text={sourceLabel} query={searchQuery} />
        </span>
        {showSignalIdMatch ? (
          <span>
            ID: <HighlightedText text={signalIdLabel} query={searchQuery} />
          </span>
        ) : null}
        <span>Timeline date: {getTimelineDateSource(signal, timelineDateMode)}</span>
        <span>Published: {formatDateTime(signal.published_at)}</span>
        <span>Collected: {formatDateTime(signal.collected_at)}</span>
        {signal.is_manual && signal.file_types?.length ? (
          <span>Types: {signal.file_types.join(", ")}</span>
        ) : null}
      </div>

      {normalizeStatus(signal.status) === "saved" && signal.saved_reason ? (
        <div
          style={{
            marginTop: "12px",
            fontSize: "13px",
            color: "var(--app-tag-fg)",
            lineHeight: 1.6,
          }}
        >
          <strong>Saved reason:</strong> {signal.saved_reason}
        </div>
      ) : null}

      {localNotice ? (
        <div
          style={{
            marginTop: "12px",
            border:
              localNotice.tone === "error"
                ? "1px solid var(--app-danger-border)"
                : localNotice.tone === "success"
                  ? "1px solid var(--app-success-border)"
                  : "1px solid var(--app-info-border)",
            background:
              localNotice.tone === "error"
                ? "var(--app-danger-bg)"
                : localNotice.tone === "success"
                  ? "var(--app-success-bg)"
                  : "var(--app-info-bg)",
            color:
              localNotice.tone === "error"
                ? "var(--app-danger-fg)"
                : localNotice.tone === "success"
                  ? "var(--app-success-fg)"
                  : "var(--app-info-fg)",
            borderRadius: "8px",
            padding: "9px 11px",
            fontSize: "13px",
            fontWeight: 600,
            lineHeight: 1.5,
          }}
        >
          {localNotice.message}
        </div>
      ) : null}

      <div
        style={{
          marginTop: "14px",
          display: "flex",
          gap: "8px",
          flexWrap: "wrap",
        }}
      >
        {canRejectFromList ? (
          <button
            onClick={handleReject}
            disabled={busy}
            style={actionButtonStyle("var(--app-danger-border)", "var(--app-danger-bg)", busy)}
          >
            Reject
          </button>
        ) : null}

        <Link
          href={`/signals/detail?id=${encodeURIComponent(detailId)}`}
          style={{
            padding: "7px 12px",
            borderRadius: "8px",
            border: "1px solid var(--app-secondary-action-border)",
            background: "var(--app-secondary-action-bg)",
            color: "var(--app-text-strong)",
            textDecoration: "none",
            display: "inline-flex",
            alignItems: "center",
            fontSize: "13px",
            fontWeight: 600,
          }}
        >
          {showManualHandoffEntry ? "Open Handoff" : "Open Detail"}
        </Link>

        {!isManual && sourceUrl ? (
          <a
            href={sourceUrl}
            target="_blank"
            rel="noreferrer"
            style={{
              padding: "7px 12px",
              borderRadius: "8px",
              border: "1px solid var(--app-secondary-action-border)",
              background: "var(--app-secondary-action-bg)",
              color: "var(--app-text-strong)",
              textDecoration: "none",
              display: "inline-flex",
              alignItems: "center",
              fontSize: "13px",
              fontWeight: 600,
            }}
          >
            Open Source
          </a>
        ) : null}
      </div>
    </div>
  );
}

export default function SignalsPage() {
  return (
    <Suspense fallback={<SignalsPageSkeleton />}>
      <SignalsPageContent />
    </Suspense>
  );
}

function SignalsPageContent() {
  const searchParams = useSearchParams();
  const [signals, setSignals] = useState<SignalItem[]>([]);
  const [manualSignals, setManualSignals] = useState<SignalItem[]>([]);
  const [counts, setCounts] = useState<Counts>(DEFAULT_COUNTS);
  const [selectedStatus, setSelectedStatus] = useState<SignalStatus>("all");
  const [selectedSource, setSelectedSource] = useState<SourceFilter>("all");
  const [selectedReviewPriority, setSelectedReviewPriority] = useState<ReviewPriorityFilter>("all");
  const [starredOnly, setStarredOnly] = useState(false);
  const [keywordQuery, setKeywordQuery] = useState("");
  const [timelineDateMode, setTimelineDateMode] = useState<TimelineDateMode>("published");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [actionNotice, setActionNotice] = useState<ActionNotice | null>(null);
  const [filtersPinned, setFiltersPinned] = useState(false);
  const [timelineLoadState, setTimelineLoadState] = useState<TimelineLoadState>({
    source: "none",
    loadedAt: null,
    requestMs: null,
    cacheAgeMs: null,
  });
  const [subscriptionUserId, setSubscriptionUserId] = useState("demo_default");

  useEffect(() => {
    const storedUserId = getStoredBetaUserId().trim();
    if (storedUserId) setSubscriptionUserId(storedUserId);
  }, []);

  useEffect(() => {
    const requestedSource = (searchParams.get("source") || "").trim().toLowerCase();
    if (requestedSource === "manual" || requestedSource === "auto") {
      setSelectedSource(requestedSource);
    }
  }, [searchParams]);

  const loadSignals = useCallback(async (useCache = true, signal?: AbortSignal) => {
    const cached = useCache ? getCachedSignals({ allowStale: true }) : null;

    if (cached) {
      const cacheAgeMs = getSignalsCacheAgeMs();
      setSignals(cached.signals);
      setManualSignals(cached.manualSignals);
      setCounts(cached.counts);
      setTimelineLoadState({
        source: "cache",
        loadedAt: Date.now(),
        requestMs: null,
        cacheAgeMs,
      });
      setLoading(false);

      if (cacheAgeMs !== null && cacheAgeMs < SIGNALS_CACHE_TTL_MS) {
        return true;
      }
    }

    try {
      setErrorMessage("");

      if (!cached) {
        setLoading(true);
        setRefreshing(false);
      } else {
        setRefreshing(true);
      }

      const requestStartedAt = performance.now();
      const signalsData = await fetchSignalsTimeline(signal, subscriptionUserId);
      const requestMs = performance.now() - requestStartedAt;

      const rawSignals: SignalItem[] = Array.isArray(signalsData)
        ? signalsData
        : signalsData.signals || signalsData.items || [];
      const nextSignals: SignalItem[] = rawSignals.filter((item) => !isManualSignal(item));
      const nextManualSignals: SignalItem[] = rawSignals.filter((item) => isManualSignal(item));

      setSignals(nextSignals);
      setManualSignals(nextManualSignals);

      const mergedCounts = buildCounts([...nextSignals, ...nextManualSignals]);
      setCounts(mergedCounts);

      writeSignalsCache({
        signals: nextSignals,
        manualSignals: nextManualSignals,
        counts: mergedCounts,
      });
      setTimelineLoadState({
        source: "api",
        loadedAt: Date.now(),
        requestMs,
        cacheAgeMs: null,
      });
      return true;
    } catch (err) {
      if (isAbortError(err)) {
        setErrorMessage(
          cached
            ? "Signal timeline refresh timed out after 20 seconds. Showing cached data while the backend catches up."
            : "Signal timeline request timed out after 20 seconds. Confirm the backend is running, then refresh this page."
        );
        if (!cached) {
          setSignals([]);
          setManualSignals([]);
          setCounts(DEFAULT_COUNTS);
        }
        return Boolean(cached);
      }
      setErrorMessage(
        cached
          ? "Signal timeline refresh failed. Showing cached data while you retry."
          : "We could not load the signal timeline right now. Please refresh or try again in a moment."
      );

      if (!cached) {
        setSignals([]);
        setManualSignals([]);
        setCounts(DEFAULT_COUNTS);
      }
      return Boolean(cached);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [subscriptionUserId]);

  function handleLocalStatusChange(
    signalId: string,
    nextStatus: string,
    savedReason?: string | null
  ) {
    const normalizedNext = normalizeStatus(nextStatus);

    setSignals((prevSignals) => {
      const updatedSignals = prevSignals
        .map((item) =>
          (item.signal_id || item.id) === signalId
            ? {
                ...item,
                status: normalizedNext,
                saved_reason: normalizedNext === "saved" ? savedReason || null : null,
              }
            : item
        );

      const mergedCounts = buildCounts([...updatedSignals, ...manualSignals]);
      setCounts(mergedCounts);

      writeSignalsCache({
        signals: updatedSignals,
        manualSignals,
        counts: mergedCounts,
      });

      return updatedSignals;
    });
  }

  function handleLocalStarChange(
    signalId: string,
    starred: boolean,
    starredAt?: string | null
  ) {
    const updateItem = (item: SignalItem) =>
      (item.signal_id || item.id) === signalId
        ? {
            ...item,
            starred,
            starred_at: starred ? starredAt || item.starred_at || new Date().toISOString() : null,
          }
        : item;

    const updatedSignals = signals.map(updateItem);
    const updatedManualSignals = manualSignals.map(updateItem);

    setSignals(updatedSignals);
    setManualSignals(updatedManualSignals);
    writeSignalsCache({
      signals: updatedSignals,
      manualSignals: updatedManualSignals,
      counts,
    });
  }

  useEffect(() => {
    const timeout = createTimeoutController(SIGNALS_REQUEST_TIMEOUT_MS);
    let retryTimeout: ReturnType<typeof createTimeoutController> | null = null;
    let retryTimer: ReturnType<typeof setTimeout> | null = null;
    let isMounted = true;

    void loadSignals(true, timeout.signal)
      .then((hasReadableTimeline) => {
        if (hasReadableTimeline || !isMounted) return;

        retryTimer = setTimeout(() => {
          retryTimeout = createTimeoutController(SIGNALS_AUTO_RETRY_TIMEOUT_MS);
          void loadSignals(true, retryTimeout.signal).finally(retryTimeout.clear);
        }, SIGNALS_AUTO_RETRY_DELAY_MS);
      })
      .finally(timeout.clear);

    return () => {
      isMounted = false;
      if (retryTimer) clearTimeout(retryTimer);
      timeout.abort();
      retryTimeout?.abort();
    };
  }, [loadSignals]);

  function refreshSignalTimeline() {
    const timeout = createTimeoutController(SIGNALS_REQUEST_TIMEOUT_MS);
    void loadSignals(false, timeout.signal).finally(timeout.clear);
  }
  const visibleItems = useMemo(() => {
    const merged = [...signals, ...manualSignals];
    const normalizedKeywordQuery = keywordQuery.trim().toLowerCase();

    return merged.filter((item) => {
      const statusMatch =
        selectedStatus === "all" ? true : normalizeStatus(item.status) === selectedStatus;

      const sourceMatch =
        selectedSource === "all"
          ? true
          : selectedSource === "manual"
            ? isManualSignal(item)
            : !isManualSignal(item);

      const reviewPriority = getSignalReviewPriority(item);
      const reviewMatch =
        selectedReviewPriority === "all"
          ? true
          : selectedReviewPriority === "unknown"
            ? !reviewPriority
            : reviewPriority?.key === selectedReviewPriority;

      const starredMatch = starredOnly ? Boolean(item.starred) : true;

      const keywordMatch = normalizedKeywordQuery
        ? getSignalSearchText(item).includes(normalizedKeywordQuery)
        : true;

      return statusMatch && sourceMatch && reviewMatch && starredMatch && keywordMatch;
    });
  }, [signals, manualSignals, selectedStatus, selectedSource, selectedReviewPriority, starredOnly, keywordQuery]);

  const sourceCounts = useMemo(() => {
    const bySelectedStatus = (items: SignalItem[]) =>
      items.filter((item) => {
        const statusMatch =
          selectedStatus === "all" ? true : normalizeStatus(item.status) === selectedStatus;
        const starredMatch = starredOnly ? Boolean(item.starred) : true;
        return statusMatch && starredMatch;
      }).length;

    const autoCount = bySelectedStatus(signals);
    const manualCount = bySelectedStatus(manualSignals);

    return {
      all: autoCount + manualCount,
      auto: autoCount,
      manual: manualCount,
    };
  }, [signals, manualSignals, selectedStatus, starredOnly]);

  const reviewPriorityCounts = useMemo(() => {
    const merged = [...signals, ...manualSignals].filter((item) => {
      const statusMatch =
        selectedStatus === "all" ? true : normalizeStatus(item.status) === selectedStatus;

      const sourceMatch =
        selectedSource === "all"
          ? true
          : selectedSource === "manual"
            ? isManualSignal(item)
            : !isManualSignal(item);

      const starredMatch = starredOnly ? Boolean(item.starred) : true;

      return statusMatch && sourceMatch && starredMatch;
    });

    const countsByPriority: Record<ReviewPriorityFilter, number> = {
      all: merged.length,
      do_not_act: 0,
      review_required: 0,
      review_before_action: 0,
      ready_for_low_risk_review: 0,
      unknown: 0,
    };

    for (const item of merged) {
      const priority = getSignalReviewPriority(item);
      countsByPriority[priority?.key || "unknown"] += 1;
    }

    return countsByPriority;
  }, [signals, manualSignals, selectedStatus, selectedSource, starredOnly]);

  const groupedByDate = useMemo(() => {
    const groups = new Map<string, SignalItem[]>();

    for (const item of visibleItems) {
      const key = getTimelineDateKey(item, timelineDateMode);
      if (!groups.has(key)) {
        groups.set(key, []);
      }
      groups.get(key)!.push(item);
    }

    return Array.from(groups.entries()).sort((a, b) => {
      if (a[0] === "Unknown Date") return 1;
      if (b[0] === "Unknown Date") return -1;
      return a[0] < b[0] ? 1 : -1;
    });
  }, [visibleItems, timelineDateMode]);

  const filtersExpanded = filtersPinned;
  const activeStatusSummary = `${getStatusFilterLabel(selectedStatus)} (${counts[selectedStatus]})`;
  const activeSourceSummary = `${getSourceFilterLabel(selectedSource)} (${sourceCounts[selectedSource]})`;
  const activeReviewSummary = `${getReviewPriorityFilterLabel(selectedReviewPriority)} (${reviewPriorityCounts[selectedReviewPriority]})`;
  const starredCount = useMemo(
    () => [...signals, ...manualSignals].filter((item) => Boolean(item.starred)).length,
    [signals, manualSignals]
  );
  const hasKeywordQuery = keywordQuery.trim().length > 0;
  const trimmedKeywordQuery = keywordQuery.trim();

  const timelineSummary = useMemo(() => {
    const allItems = [...signals, ...manualSignals];
    const todayKey = getDateKeyFromRaw(new Date().toISOString());
    const informationDateKeys = allItems.map((item) => getTimelineDateKey(item, "published"));
    const collectionDateKeys = allItems.map((item) => getDateKeyFromRaw(item.collected_at));
    const latestInformationDate = getLatestKnownDateKey(informationDateKeys);
    const latestCollectionDate = getLatestKnownDateKey(collectionDateKeys);

    return {
      totalItems: allItems.length,
      autoItems: signals.length,
      manualItems: manualSignals.length,
      publishedToday: allItems.filter((item) => getTimelineDateKey(item, "published") === todayKey).length,
      collectedToday: allItems.filter((item) => getDateKeyFromRaw(item.collected_at) === todayKey).length,
      latestInformationDate,
      latestInformationCount: informationDateKeys.filter((key) => key === latestInformationDate).length,
      latestCollectionDate,
      latestCollectionCount: collectionDateKeys.filter((key) => key === latestCollectionDate).length,
    };
  }, [signals, manualSignals]);
  const hasVisibleTimelineItems = groupedByDate.length > 0;

  return (
    <AppContainer style={signalsShellStyle}>
      <SignalsHero
        totalItems={timelineSummary.totalItems}
        autoItems={timelineSummary.autoItems}
        manualItems={timelineSummary.manualItems}
        visibleItems={visibleItems.length}
        source={timelineLoadState.source}
      />

      <SectionShell title="Timeline Summary">
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 220px), 1fr))",
            gap: "12px",
          }}
        >
          <SummaryCard
            label="Total Items"
            value={timelineSummary.totalItems}
            subLabel="All items in timeline"
          />
          <SummaryCard
            label="Auto Signals"
            value={timelineSummary.autoItems}
            subLabel="Feed and RSS items"
          />
          <SummaryCard
            label="Manual Sessions"
            value={timelineSummary.manualItems}
            subLabel="Uploaded intelligence"
          />
          <SummaryCard
            label="Information Today"
            value={timelineSummary.publishedToday}
            subLabel="Published or originated today"
          />
          <SummaryCard
            label="Collected Today"
            value={timelineSummary.collectedToday}
            subLabel="Loaded into today's backend snapshot"
          />
        </div>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "8px",
            flexWrap: "wrap",
            marginTop: "14px",
          }}
        >
          <span style={{ fontSize: "12px", color: "var(--app-text-subtle)", fontWeight: 700 }}>
            Group by
          </span>
          {(["published", "collected"] as TimelineDateMode[]).map((mode) => {
            const active = timelineDateMode === mode;
            return (
              <button
                key={mode}
                type="button"
                onClick={() => setTimelineDateMode(mode)}
                aria-pressed={active}
                style={{
                  border: active ? "1px solid var(--app-primary-action-border)" : "1px solid var(--app-secondary-action-border)",
                  background: active ? "var(--app-primary-action-bg)" : "var(--app-secondary-action-bg)",
                  color: active ? "var(--app-primary-action-fg)" : "var(--app-secondary-action-fg)",
                  borderRadius: "999px",
                  padding: "7px 12px",
                  fontSize: "12px",
                  fontWeight: 700,
                  cursor: "pointer",
                }}
              >
                {mode === "collected" ? "Collection batch" : "Information date"}
              </button>
            );
          })}
        </div>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 260px), 1fr))",
            gap: "10px",
            marginTop: "14px",
            border: "1px solid var(--app-info-border)",
            background: "var(--app-info-bg)",
            borderRadius: "8px",
            padding: "12px",
          }}
        >
          <div>
            <div style={{ fontSize: "12px", color: "var(--app-info-fg)", fontWeight: 800 }}>
              Latest collection batch
            </div>
            <div style={{ fontSize: "14px", color: "var(--app-text-strong)", fontWeight: 800, marginTop: "4px" }}>
              {formatDateHeading(timelineSummary.latestCollectionDate)}
            </div>
            <div style={{ fontSize: "12px", color: "var(--app-text-muted)", marginTop: "4px", lineHeight: 1.5 }}>
              {timelineSummary.latestCollectionCount} item{timelineSummary.latestCollectionCount === 1 ? "" : "s"} entered the backend snapshot on this date.
            </div>
          </div>
          <div>
            <div style={{ fontSize: "12px", color: "var(--app-info-fg)", fontWeight: 800 }}>
              Latest information date
            </div>
            <div style={{ fontSize: "14px", color: "var(--app-text-strong)", fontWeight: 800, marginTop: "4px" }}>
              {formatDateHeading(timelineSummary.latestInformationDate)}
            </div>
            <div style={{ fontSize: "12px", color: "var(--app-text-muted)", marginTop: "4px", lineHeight: 1.5 }}>
              {timelineSummary.latestInformationCount} item{timelineSummary.latestInformationCount === 1 ? "" : "s"} were published or originated on this date.
            </div>
          </div>
          <div style={{ fontSize: "12px", color: "var(--app-text-muted)", lineHeight: 1.55 }}>
            The default timeline uses Information date. If S3 has a newer daily batch, switch to Collection batch to verify backend pickup.
          </div>
        </div>
      </SectionShell>

      <SectionShell
        title="Load Status"
        subtitle="Timeline should be readable from cache or the backend snapshot before a full upstream refresh is needed."
      >
        <div style={{ display: "grid", gap: "10px" }}>
          <div style={{ fontSize: "13px", color: "var(--app-text-muted)", lineHeight: 1.55 }}>
            {timelineLoadState.source === "api"
              ? "Fresh API data loaded. If the request is near the timeout, check backend snapshot freshness before treating the UI as broken."
              : timelineLoadState.source === "cache"
                ? "Cached timeline is visible while the API refresh runs in the background."
                : "Waiting for the first readable timeline response."}
          </div>
          <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
            <span style={loadStatusPillStyle}>
              Source: {timelineLoadState.source === "api" ? "Fresh API" : timelineLoadState.source === "cache" ? "Cache" : "Not loaded"}
            </span>
            <span style={loadStatusPillStyle}>Loaded: {formatLoadTimestamp(timelineLoadState.loadedAt)}</span>
            <span style={loadStatusPillStyle}>Request: {formatDuration(timelineLoadState.requestMs)}</span>
            {timelineLoadState.cacheAgeMs !== null ? (
              <span style={loadStatusPillStyle}>Cache age: {formatDuration(timelineLoadState.cacheAgeMs)}</span>
            ) : null}
            <span style={loadStatusPillStyle}>Timeout: {Math.round(SIGNALS_REQUEST_TIMEOUT_MS / 1000)} s</span>
          </div>
        </div>
      </SectionShell>

      <section
        style={{
          marginBottom: filtersExpanded ? "12px" : "16px",
          position: "sticky",
          top: "68px",
          zIndex: 30,
        }}
      >
        <div
          style={{
            border: "1px solid var(--app-surface-border)",
            borderRadius: "8px",
            background: "var(--app-surface-bg)",
            backdropFilter: "blur(12px)",
            padding: "10px 12px",
            boxShadow: "var(--app-surface-shadow)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: "12px",
            flexWrap: "wrap",
          }}
        >
          <div style={filterHeaderLeftStyle}>
            <SlidersHorizontal size={18} color="var(--app-text-muted)" aria-hidden="true" />
            <strong
              style={{
                fontSize: "13px",
                color: "var(--app-text-strong)",
                textTransform: "uppercase",
                letterSpacing: "0.4px",
              }}
            >
              Filters
            </strong>
            {[
              activeStatusSummary,
              activeSourceSummary,
              activeReviewSummary,
              starredOnly ? `Starred (${starredCount})` : "",
              hasKeywordQuery ? "Search active" : "",
              `${visibleItems.length} visible`,
            ]
              .filter(Boolean)
              .map(
              (summary) => (
                <span key={summary} style={compactFilterChipStyle}>
                  {summary}
                </span>
              )
            )}
          </div>

          <div style={filterHeaderSearchStyle}>
            <div style={keywordSearchWrapStyle}>
              <Search size={15} color="var(--app-text-subtle)" aria-hidden="true" />
              <input
                value={keywordQuery}
                onChange={(event) => setKeywordQuery(event.target.value)}
                placeholder="Search signals"
                aria-label="Search signals by keyword"
                style={keywordSearchInputStyle}
              />
              {hasKeywordQuery ? (
                <button
                  type="button"
                  onClick={() => setKeywordQuery("")}
                  aria-label="Clear signal search"
                  title="Clear search"
                  style={keywordSearchClearStyle}
                >
                  <X size={14} aria-hidden="true" />
                </button>
              ) : null}
            </div>
          </div>

          <div style={filterHeaderActionsStyle}>
            {refreshing ? <span style={{ fontSize: "12px", color: "var(--app-text-subtle)" }}>Refreshing...</span> : null}
            <button
              type="button"
              onClick={() => setFiltersPinned((value) => !value)}
              title={filtersPinned ? "Unpin filters" : "Pin filters open"}
              aria-pressed={filtersPinned}
              aria-label={filtersPinned ? "Unpin filters" : "Pin filters open"}
              style={{
                width: "36px",
                height: "36px",
                borderRadius: "8px",
                border: filtersPinned ? "1px solid var(--app-primary-action-border)" : "1px solid var(--app-secondary-action-border)",
                background: filtersPinned ? "var(--app-primary-action-bg)" : "var(--app-secondary-action-bg)",
                color: filtersPinned ? "var(--app-primary-action-fg)" : "var(--app-secondary-action-fg)",
                cursor: "pointer",
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              {filtersPinned ? <PinOff size={17} aria-hidden="true" /> : <Pin size={17} aria-hidden="true" />}
            </button>
            <button
              type="button"
              onClick={refreshSignalTimeline}
              style={{
                padding: "8px 14px",
                borderRadius: "8px",
                border: "1px solid var(--app-secondary-action-border)",
                background: "var(--app-surface-bg)",
                cursor: "pointer",
                fontSize: "13px",
                fontWeight: 600,
              }}
            >
              Refresh
            </button>
          </div>
        </div>
      </section>

      {filtersExpanded ? (
        <SectionShell
        title="Filters"
        subtitle="Review intelligence by workflow status and source."
      >
        <div style={{ display: "grid", gap: "18px" }}>
          <div>
            <div
              style={{
                fontSize: "12px",
                fontWeight: 700,
                color: "var(--app-text-subtle)",
                textTransform: "uppercase",
                letterSpacing: "0",
                marginBottom: "10px",
              }}
            >
              Status
            </div>

            <div style={{ display: "flex", flexWrap: "wrap", gap: "10px" }}>
              <FilterButton
                label="All"
                subLabel={getStatusSubLabel("all")}
                count={counts.all}
                active={selectedStatus === "all"}
                onClick={() => setSelectedStatus("all")}
              />
              <FilterButton
                label="Pending"
                subLabel={getStatusSubLabel("pending")}
                count={counts.pending}
                active={selectedStatus === "pending"}
                onClick={() => setSelectedStatus("pending")}
              />
              <FilterButton
                label="Saved"
                subLabel={getStatusSubLabel("saved")}
                count={counts.saved}
                active={selectedStatus === "saved"}
                onClick={() => setSelectedStatus("saved")}
              />
              <FilterButton
                label="Analyzed"
                subLabel={getStatusSubLabel("analyzed")}
                count={counts.analyzed}
                active={selectedStatus === "analyzed"}
                onClick={() => setSelectedStatus("analyzed")}
              />
              <FilterButton
                label="Completed"
                subLabel={getStatusSubLabel("completed")}
                count={counts.completed}
                active={selectedStatus === "completed"}
                onClick={() => setSelectedStatus("completed")}
              />
              <FilterButton
                label="Rejected"
                subLabel={getStatusSubLabel("rejected")}
                count={counts.rejected}
                active={selectedStatus === "rejected"}
                onClick={() => setSelectedStatus("rejected")}
              />
            </div>
          </div>

          <div>
            <div
              style={{
                fontSize: "12px",
                fontWeight: 700,
                color: "var(--app-text-subtle)",
                textTransform: "uppercase",
                letterSpacing: "0",
                marginBottom: "10px",
              }}
            >
              Bookmark
            </div>

            <div style={{ display: "flex", flexWrap: "wrap", gap: "10px" }}>
              <FilterButton
                label="Starred"
                subLabel="Quick return"
                count={starredCount}
                active={starredOnly}
                onClick={() => setStarredOnly((value) => !value)}
              />
            </div>
          </div>

          <div>
            <div
              style={{
                fontSize: "12px",
                fontWeight: 700,
                color: "var(--app-text-subtle)",
                textTransform: "uppercase",
                letterSpacing: "0",
                marginBottom: "10px",
              }}
            >
              Source
            </div>

            <div style={{ display: "flex", flexWrap: "wrap", gap: "10px" }}>
              <FilterButton
                label="All Sources"
                subLabel={getSourceSubLabel("all")}
                count={sourceCounts.all}
                active={selectedSource === "all"}
                onClick={() => setSelectedSource("all")}
              />
              <FilterButton
                label="Auto"
                subLabel={getSourceSubLabel("auto")}
                count={sourceCounts.auto}
                active={selectedSource === "auto"}
                onClick={() => setSelectedSource("auto")}
              />
              <FilterButton
                label="Manual"
                subLabel={getSourceSubLabel("manual")}
                count={sourceCounts.manual}
                active={selectedSource === "manual"}
                onClick={() => setSelectedSource("manual")}
              />
            </div>
          </div>

          <div>
            <div
              style={{
                fontSize: "12px",
                fontWeight: 700,
                color: "var(--app-text-subtle)",
                textTransform: "uppercase",
                letterSpacing: "0",
                marginBottom: "10px",
              }}
            >
              Review Priority
            </div>

            <div style={{ display: "flex", flexWrap: "wrap", gap: "10px" }}>
              <FilterButton
                label="All Review"
                subLabel={getReviewPrioritySubLabel("all")}
                count={reviewPriorityCounts.all}
                active={selectedReviewPriority === "all"}
                onClick={() => setSelectedReviewPriority("all")}
              />
              <FilterButton
                label="Do Not Act"
                subLabel={getReviewPrioritySubLabel("do_not_act")}
                count={reviewPriorityCounts.do_not_act}
                active={selectedReviewPriority === "do_not_act"}
                onClick={() => setSelectedReviewPriority("do_not_act")}
              />
              <FilterButton
                label="Review Required"
                subLabel={getReviewPrioritySubLabel("review_required")}
                count={reviewPriorityCounts.review_required}
                active={selectedReviewPriority === "review_required"}
                onClick={() => setSelectedReviewPriority("review_required")}
              />
              <FilterButton
                label="Review Before Action"
                subLabel={getReviewPrioritySubLabel("review_before_action")}
                count={reviewPriorityCounts.review_before_action}
                active={selectedReviewPriority === "review_before_action"}
                onClick={() => setSelectedReviewPriority("review_before_action")}
              />
              <FilterButton
                label="Low-Risk Review"
                subLabel={getReviewPrioritySubLabel("ready_for_low_risk_review")}
                count={reviewPriorityCounts.ready_for_low_risk_review}
                active={selectedReviewPriority === "ready_for_low_risk_review"}
                onClick={() => setSelectedReviewPriority("ready_for_low_risk_review")}
              />
              <FilterButton
                label="Unknown"
                subLabel={getReviewPrioritySubLabel("unknown")}
                count={reviewPriorityCounts.unknown}
                active={selectedReviewPriority === "unknown"}
                onClick={() => setSelectedReviewPriority("unknown")}
              />
            </div>
          </div>

          <div
            style={{
              display: "flex",
              gap: "10px",
              alignItems: "center",
              justifyContent: "space-between",
              flexWrap: "wrap",
              paddingTop: "4px",
            }}
          >
            <div style={{ fontSize: "12px", color: "var(--app-text-subtle)", lineHeight: 1.6 }}>
              Pending = to review | Saved = revisit | Analyzed = processed | Rejected = low value
            </div>

            <div style={{ display: "flex", gap: "10px", alignItems: "center", flexWrap: "wrap" }}>
              {refreshing ? (
                <span style={{ fontSize: "12px", color: "var(--app-text-subtle)" }}>Refreshing...</span>
              ) : null}
              <button
                onClick={refreshSignalTimeline}
                style={{
                  padding: "8px 14px",
                  borderRadius: "8px",
                  border: "1px solid var(--app-secondary-action-border)",
                  background: "var(--app-surface-bg)",
                  cursor: "pointer",
                  fontSize: "13px",
                  fontWeight: 600,
                }}
              >
                Refresh
              </button>
            </div>
          </div>
        </div>
          </SectionShell>
      ) : null}

      {actionNotice ? (
        <div
          style={{
            border:
              actionNotice.tone === "error"
                ? "1px solid var(--app-danger-border)"
                : actionNotice.tone === "success"
                  ? "1px solid var(--app-success-border)"
                  : "1px solid var(--app-info-border)",
            background:
              actionNotice.tone === "error"
                ? "var(--app-danger-bg)"
                : actionNotice.tone === "success"
                  ? "var(--app-success-bg)"
                  : "var(--app-info-bg)",
            color:
              actionNotice.tone === "error"
                ? "var(--app-danger-fg)"
                : actionNotice.tone === "success"
                  ? "var(--app-success-fg)"
                  : "var(--app-info-fg)",
            borderRadius: "8px",
            padding: "11px 13px",
            marginBottom: "14px",
            fontSize: "13px",
            fontWeight: 700,
            lineHeight: 1.5,
          }}
        >
          {actionNotice.message}
        </div>
      ) : null}

      {loading ? (
        <SignalStateCard
          title="Loading signal timeline"
          description="Requesting /signals?status=all from the local API."
        />
      ) : null}

      {!!errorMessage && !loading ? (
        <SignalStateCard
          title={hasVisibleTimelineItems ? "Signal refresh timed out" : "Signal timeline could not load"}
          description={
            hasVisibleTimelineItems
              ? `${errorMessage} Showing the current timeline while refresh catches up. Probe http://127.0.0.1:8000/signals?status=all if this keeps happening.`
              : `${errorMessage} Probe http://127.0.0.1:8000/signals?status=all if this keeps happening.`
          }
          tone={hasVisibleTimelineItems ? "neutral" : "error"}
          actionLabel="Refresh"
          onAction={refreshSignalTimeline}
        />
      ) : null}

      {!loading && groupedByDate.length === 0 ? (
        <SignalStateCard
          title="No signal records match this view"
          description="Signals loaded, but the current source, status, review-priority, or search filters hide all records."
          actionLabel="Refresh"
          onAction={refreshSignalTimeline}
        />
      ) : null}

      {!loading &&
        groupedByDate.map(([dateKey, items]) => (
          <section key={dateKey} style={{ marginBottom: "34px" }}>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "10px",
                marginBottom: "8px",
              }}
            >
              <h2
                style={{
                  fontSize: "22px",
                  margin: 0,
                  color: "var(--app-text-strong)",
                  lineHeight: 1.2,
                }}
              >
                {formatDateHeading(dateKey)}
              </h2>
              <span
                style={{
                  fontSize: "12px",
                  color: "var(--app-text-subtle)",
                  border: "1px solid var(--app-surface-border)",
                  background: "var(--app-surface-bg)",
                  borderRadius: "999px",
                  padding: "4px 10px",
                  fontWeight: 600,
                }}
              >
                {items.length} item{items.length > 1 ? "s" : ""}
              </span>
            </div>

            <div
              style={{
                fontSize: "13px",
                color: "var(--app-text-subtle)",
                marginBottom: "12px",
                paddingBottom: "10px",
                borderBottom: "1px solid var(--app-surface-border)",
              }}
            >
              {getTimelineGroupDescription(items, timelineDateMode)}
            </div>

            <div>
              {items.map((signal, index) => (
                <SignalCard
                  key={`${signal.signal_id || signal.id}-${index}`}
                  signal={signal}
                  onStatusChanged={handleLocalStatusChange}
                  onStarChanged={handleLocalStarChange}
                  onActionNotice={setActionNotice}
                  timelineDateMode={timelineDateMode}
                  searchQuery={trimmedKeywordQuery}
                />
              ))}
            </div>
          </section>
        ))}
    </AppContainer>
  );
}

const signalsShellStyle = {
  paddingTop: "28px",
  color: "var(--app-page-fg)",
} as const;

const signalsHeroStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 420px), 1fr))",
  gap: "18px",
  alignItems: "stretch",
  marginBottom: "16px",
} as const;

const signalsEyebrowStyle = {
  color: "var(--app-text-subtle)",
  fontSize: "12px",
  fontWeight: 760,
  textTransform: "uppercase" as const,
  letterSpacing: "0",
} as const;

const signalsHeroTitleStyle = {
  margin: "10px 0 0",
  color: "var(--app-text-strong)",
  fontSize: "38px",
  fontWeight: 780,
  lineHeight: 1.08,
  maxWidth: "820px",
} as const;

const signalsHeroDescriptionStyle = {
  margin: "14px 0 0",
  color: "var(--app-text-muted)",
  fontSize: "16px",
  lineHeight: 1.62,
  maxWidth: "820px",
} as const;

const signalsQuickActionRowStyle = {
  display: "flex",
  gap: "9px",
  flexWrap: "wrap" as const,
  marginTop: "20px",
} as const;

const signalsQuickActionStyle = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  gap: "7px",
  border: "1px solid var(--app-secondary-action-border)",
  borderRadius: "8px",
  background: "var(--app-secondary-action-bg)",
  color: "var(--app-secondary-action-fg)",
  padding: "10px 12px",
  textDecoration: "none",
  fontSize: "13px",
  fontWeight: 720,
  whiteSpace: "nowrap" as const,
} as const;

const signalsHeroPanelStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-bg)",
  padding: "16px",
  boxShadow: "var(--app-surface-shadow)",
} as const;

const signalsHeroPanelHeaderStyle = {
  display: "inline-flex",
  alignItems: "center",
  gap: "8px",
  color: "var(--app-text-strong)",
  fontSize: "14px",
  fontWeight: 760,
} as const;

const signalsHeroMetricGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
  gap: "10px",
  marginTop: "14px",
} as const;

const signalsHeroMetricStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  padding: "13px",
  minWidth: 0,
} as const;

const signalsHeroMetricValueStyle = {
  color: "var(--app-text-strong)",
  fontSize: "18px",
  fontWeight: 780,
  lineHeight: 1.2,
  overflowWrap: "anywhere" as const,
} as const;

const signalsHeroMetricLabelStyle = {
  marginTop: "7px",
  color: "var(--app-text-subtle)",
  fontSize: "12px",
  fontWeight: 720,
} as const;

const loadStatusPillStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "999px",
  background: "var(--app-secondary-action-bg)",
  color: "var(--app-text-muted)",
  padding: "7px 10px",
  fontSize: "12px",
  fontWeight: 700,
} as const;

const compactFilterChipStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "999px",
  background: "var(--app-surface-muted-bg)",
  color: "var(--app-text-muted)",
  padding: "6px 9px",
  fontSize: "12px",
  fontWeight: 700,
  whiteSpace: "nowrap",
} as const;

const filterHeaderLeftStyle = {
  display: "flex",
  alignItems: "center",
  gap: "10px",
  minWidth: "min(460px, 100%)",
  flex: "1 1 460px",
  flexWrap: "wrap",
} as const;

const filterHeaderSearchStyle = {
  display: "flex",
  alignItems: "center",
  flex: "1 1 280px",
  minWidth: "220px",
  maxWidth: "420px",
} as const;

const filterHeaderActionsStyle = {
  display: "flex",
  alignItems: "center",
  justifyContent: "flex-end",
  gap: "8px",
  flex: "0 0 auto",
  flexWrap: "nowrap",
} as const;

const keywordSearchWrapStyle = {
  width: "100%",
  minWidth: 0,
  height: "36px",
  border: "1px solid var(--app-secondary-action-border)",
  borderRadius: "8px",
  background: "var(--app-secondary-action-bg)",
  color: "var(--app-text-strong)",
  display: "flex",
  alignItems: "center",
  gap: "8px",
  padding: "0 10px",
} as const;

const keywordSearchInputStyle = {
  width: "100%",
  minWidth: 0,
  border: "0",
  outline: "none",
  background: "transparent",
  color: "var(--app-text-strong)",
  fontSize: "13px",
  fontWeight: 600,
} as const;

const keywordSearchClearStyle = {
  width: "24px",
  height: "24px",
  border: "0",
  borderRadius: "8px",
  background: "var(--app-ghost-action-bg)",
  color: "var(--app-ghost-action-fg)",
  cursor: "pointer",
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  flex: "0 0 auto",
} as const;

const searchHighlightStyle = {
  background: "var(--app-warning-bg)",
  color: "var(--app-warning-fg)",
  borderRadius: "3px",
  padding: "0 2px",
} as const;

const searchMatchSnippetStyle = {
  marginTop: "-6px",
  marginBottom: "14px",
  borderLeft: "3px solid var(--app-warning-border)",
  padding: "8px 10px",
  background: "var(--app-warning-bg)",
  color: "var(--app-warning-fg)",
  fontSize: "13px",
  lineHeight: 1.65,
} as const;

function SignalsPageSkeleton() {
  return (
    <AppContainer style={signalsShellStyle}>
      <SignalsHero
        totalItems={0}
        autoItems={0}
        manualItems={0}
        visibleItems={0}
        source="none"
      />
      <SignalStateCard
        title="Loading signal timeline"
        description="Requesting /signals?status=all from the local API."
      />
    </AppContainer>
  );
}

function SignalStateCard({
  title,
  description,
  tone = "neutral",
  actionLabel,
  onAction,
}: {
  title: string;
  description: string;
  tone?: "neutral" | "error";
  actionLabel?: string;
  onAction?: () => void;
}) {
  const isError = tone === "error";
  return (
    <div
      style={{
        border: isError ? "1px solid var(--app-danger-border)" : "1px solid var(--app-surface-border)",
        borderRadius: "8px",
        background: isError ? "var(--app-danger-bg)" : "var(--app-surface-bg)",
        color: isError ? "var(--app-danger-fg)" : "var(--app-text-muted)",
        padding: "16px",
        marginBottom: "16px",
        display: "grid",
        gap: "10px",
        fontSize: "13px",
        lineHeight: 1.6,
      }}
    >
      <strong style={{ color: isError ? "var(--app-danger-fg)" : "var(--app-text-strong)", fontSize: "15px" }}>{title}</strong>
      <p style={{ margin: 0 }}>{description}</p>
      {actionLabel && onAction ? (
        <button
          type="button"
          onClick={onAction}
          style={{
            width: "fit-content",
            border: "1px solid var(--app-secondary-action-border)",
            borderRadius: "8px",
            background: "var(--app-secondary-action-bg)",
            color: "var(--app-text-strong)",
            padding: "8px 10px",
            fontSize: "13px",
            fontWeight: 700,
            cursor: "pointer",
          }}
        >
          {actionLabel}
        </button>
      ) : null}
    </div>
  );
}
