"use client";

import type { CSSProperties } from "react";
import { Suspense, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import AppContainer from "@/components/AppContainer";
import PageHeader from "@/components/PageHeader";
import SectionCard from "@/components/SectionCard";
import { apiUrl } from "@/lib/api";
import { cleanDisplayList, cleanDisplayText } from "@/lib/displayText";

type AgentWatchDetail = {
  entity_id?: string | null;
  found?: boolean;
  message?: string;
  title?: string;
  canonical_url?: string;
  source?: string;
  agent_subtopic?: string;
  summary?: string;
  published_at?: string;
  agent_watch_score?: number | string | null;
  metadata?: {
    repo_name?: string;
    repo_stars?: number | string | null;
    language?: string;
    matched_keywords?: string[];
    hn_points?: number | string | null;
    hn_comments?: number | string | null;
    product_hunt_votes?: number | string | null;
  };
  tracking?: {
    first_seen?: string | null;
    last_seen?: string | null;
    days_observed?: number | null;
    observations?: number | null;
    latest_score?: number | null;
    previous_score?: number | null;
    score_change?: number | null;
  };
  profile?: {
    generated_at?: string;
    repo_summary?: string;
    what_it_does?: string;
    why_it_matters?: string;
    project_fit?: string;
    suggested_use_cases?: string[];
    risks?: string[];
    confidence?: string;
    provider_used?: string | null;
    model_used?: string | null;
  };
  history?: Array<{
    captured_at?: string;
    agent_watch_score?: number | string | null;
    repo_stars?: number | string | null;
    source?: string;
  }>;
};

type AgentWatchAnalyzeResponse = {
  ok?: boolean;
  message?: string;
  detail?: AgentWatchDetail;
};

function compactDateLabel(value?: string | null) {
  if (!value) return "N/A";
  const parsed = Date.parse(value);
  if (Number.isNaN(parsed)) return "N/A";
  return new Intl.DateTimeFormat("en-AU", {
    year: "numeric",
    month: "short",
    day: "numeric",
  }).format(new Date(parsed));
}

function scoreLabel(value: number | string | null | undefined) {
  if (value === null || value === undefined || value === "") return "N/A";
  return String(value);
}

function deltaLabel(value?: number | null) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "N/A";
  }
  const numeric = Number(value);
  if (numeric === 0) return "0";
  return `${numeric > 0 ? "+" : ""}${numeric.toFixed(1)}`;
}

function getTrackingState(tracking?: AgentWatchDetail["tracking"]) {
  if (!tracking) return "untracked";
  const observations = Number(tracking.observations ?? 0);
  const delta = Number(tracking.score_change ?? 0);
  if (observations <= 1) return "new";
  if (delta >= 5) return "rising";
  if (delta <= -5) return "cooling";
  return "stable";
}

function buildWhyTrackNow(item: AgentWatchDetail, trackingState: string) {
  const projectFit = cleanDisplayText(item.profile?.project_fit);
  const whyItMatters = cleanDisplayText(item.profile?.why_it_matters);
  const title = cleanDisplayText(item.title) || cleanDisplayText(item.metadata?.repo_name) || "This repo";

  if (trackingState === "new") {
    return `${title} is newly tracked and needs an initial read before it disappears into the general signal flow.`;
  }
  if (trackingState === "rising") {
    return `${title} is rising across recent observations, so it is worth checking whether the momentum is durable.`;
  }
  if (projectFit) {
    return projectFit;
  }
  if (whyItMatters) {
    return whyItMatters;
  }
  if (trackingState === "stable") {
    return `${title} is staying active over time, which makes it worth monitoring for sustained relevance.`;
  }
  if (trackingState === "cooling") {
    return `${title} is cooling, so this is mainly worth checking to see whether the earlier momentum was real or temporary.`;
  }
  return `${title} is on the watchlist, but it still needs a stronger reason-to-track summary.`;
}

function buildWhatChanged(item: AgentWatchDetail, trackingState: string) {
  const delta = deltaLabel(item.tracking?.score_change);
  const observations = Number(item.tracking?.observations ?? 0);
  if (trackingState === "new") {
    return "First observation in tracking history.";
  }
  if (trackingState === "rising") {
    return `Recent score delta moved to ${delta} across ${observations || "recent"} observations.`;
  }
  if (trackingState === "cooling") {
    return `Recent score delta cooled to ${delta} after prior tracking activity.`;
  }
  if (trackingState === "stable") {
    return `Tracking is stable with ${observations || 0} observations and no large recent score swing.`;
  }
  return "No meaningful tracking change is available yet.";
}

export default function AgentWatchDetailPage() {
  return (
    <Suspense fallback={<AgentWatchDetailSkeleton />}>
      <AgentWatchDetailPageContent />
    </Suspense>
  );
}

function AgentWatchDetailPageContent() {
  const searchParams = useSearchParams();
  const entityId = searchParams.get("entity_id") || "";
  const [payload, setPayload] = useState<AgentWatchDetail | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [reloadToken, setReloadToken] = useState(0);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [actionMessage, setActionMessage] = useState("");

  useEffect(() => {
    if (!entityId) return;

    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 15000);

    async function loadDetail() {
      setIsLoading(true);
      setLoadError("");
      try {
        const response = await fetch(
          apiUrl(`/radar/agent-watch/detail?entity_id=${encodeURIComponent(entityId)}`),
          { signal: controller.signal },
        );
        let data: AgentWatchDetail | null = null;
        try {
          data = await response.json();
        } catch {
          data = null;
        }
        if (!response.ok) {
          throw new Error(data?.message || `Failed to load repo detail (${response.status}).`);
        }
        if (!data) {
          throw new Error("Repo detail response was empty.");
        }
        setPayload(data);
      } catch (error) {
        const message =
          error instanceof DOMException && error.name === "AbortError"
            ? "Repo detail request timed out. Try again or go back to Agent Watch."
            : error instanceof Error
              ? error.message
              : "Failed to load repo detail.";
        setLoadError(message);
      } finally {
        window.clearTimeout(timeout);
        setIsLoading(false);
      }
    }

    loadDetail();

    return () => {
      window.clearTimeout(timeout);
      controller.abort();
    };
  }, [entityId, reloadToken]);

  const history = useMemo(() => (Array.isArray(payload?.history) ? payload.history : []), [payload]);

  if (!entityId) {
    return (
      <AppContainer>
        <div style={{ color: "var(--app-text-muted)" }}>Missing repo detail target.</div>
      </AppContainer>
    );
  }

  if (loadError && !payload) {
    return (
      <AppContainer>
        <SectionCard title="Repo Detail Unavailable">
          <div style={errorPanelStyle}>
            <div>{loadError}</div>
            <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
              <button type="button" onClick={() => setReloadToken((value) => value + 1)} style={secondaryActionButtonStyle}>
                Retry
              </button>
              <Link href="/agent-watch" style={buttonLinkStyle}>
                Back to Agent Watch
              </Link>
            </div>
          </div>
        </SectionCard>
      </AppContainer>
    );
  }

  if (isLoading && !payload) {
    return (
      <AppContainer>
        <div style={{ color: "var(--app-text-muted)" }}>Loading repo detail...</div>
      </AppContainer>
    );
  }

  if (!payload) {
    return (
      <AppContainer>
        <SectionCard title="Repo Detail Unavailable">
          <div style={errorPanelStyle}>
            <div>Repo detail did not return any data.</div>
            <button type="button" onClick={() => setReloadToken((value) => value + 1)} style={secondaryActionButtonStyle}>
              Retry
            </button>
          </div>
        </SectionCard>
      </AppContainer>
    );
  }

  if (payload.found === false) {
    return (
      <AppContainer>
        <PageHeader title="Agent Watch Detail" description={payload.message || "Repo detail not found."} />
        <Link href="/agent-watch" style={{ color: "var(--app-info-fg)", textDecoration: "none", fontWeight: 700 }}>
          Back to Agent Watch
        </Link>
      </AppContainer>
    );
  }

  const meta = payload.metadata || {};
  const tracking = payload.tracking;
  const profile = payload.profile;
  const trackingState = getTrackingState(tracking);
  const profileReady = Boolean(profile?.what_it_does || profile?.project_fit || profile?.why_it_matters);
  const analyzeLabel = profileReady ? "Re-analyze" : "Analyze Repo";
  const whyTrackNow = buildWhyTrackNow(payload, trackingState);
  const whatChanged = buildWhatChanged(payload, trackingState);
  const analysisMetaBits = [
    compactDateLabel(profile?.generated_at),
    cleanDisplayText(profile?.provider_used),
    cleanDisplayText(profile?.model_used),
  ].filter((value) => value && value !== "N/A");
  const decisionSummaryBits = [
    cleanDisplayText(profile?.project_fit),
    cleanDisplayText(profile?.why_it_matters),
    tracking?.score_change != null && !Number.isNaN(Number(tracking.score_change))
      ? `Recent score delta ${deltaLabel(tracking.score_change)}`
      : "",
    trackingState !== "untracked" ? `Tracking state ${trackingState}` : "",
    tracking?.days_observed != null
      ? `Observed for ${tracking.days_observed} day${tracking.days_observed === 1 ? "" : "s"}`
      : "",
  ].filter(Boolean);

  return (
    <AppContainer>
      <div style={{ display: "flex", justifyContent: "space-between", gap: "16px", flexWrap: "wrap", marginBottom: "20px" }}>
        <div>
          <PageHeader
            title={cleanDisplayText(payload.title) || cleanDisplayText(meta.repo_name) || "Tracked Agent Repo"}
            description={cleanDisplayText(payload.canonical_url) || cleanDisplayText(payload.entity_id) || ""}
            marginBottom="10px"
          />
          <div style={{ color: "var(--app-text-muted)", fontSize: "14px" }}>
            {(cleanDisplayText(payload.agent_subtopic) || "agent_repo")} · {(cleanDisplayText(payload.source) || "unknown")}
          </div>
          <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", marginTop: "10px" }}>
            <span style={profileReady ? readyBadgeStyle : pendingBadgeStyle}>
              {profileReady ? "LLM Profile Ready" : "Profile Pending"}
            </span>
            {tracking ? <span style={trackingBadgeStyle}>Tracking Active</span> : null}
            <span style={trackingStateBadgeStyle(trackingState)}>{trackingState}</span>
            {profileReady && analysisMetaBits.length ? (
              <span style={analysisMetaBadgeStyle}>{analysisMetaBits.join(" · ")}</span>
            ) : null}
          </div>
        </div>
        <div style={{ display: "flex", gap: "12px", alignItems: "flex-start", flexWrap: "wrap" }}>
          <Link href="/agent-watch" style={buttonLinkStyle}>
            Back
          </Link>
          <button
            type="button"
            onClick={async () => {
              if (!entityId || isAnalyzing) return;
              setIsAnalyzing(true);
              setActionMessage("");
              try {
                const response = await fetch(
                  apiUrl(`/radar/agent-watch/analyze?entity_id=${encodeURIComponent(entityId)}`),
                );
                let data: AgentWatchAnalyzeResponse | null = null;
                try {
                  data = await response.json();
                } catch {
                  data = null;
                }
                if (!response.ok || data?.ok === false) {
                  throw new Error(data?.message || `Failed to analyze repo (${response.status}).`);
                }
                if (data?.detail) {
                  setPayload(data.detail);
                }
                setActionMessage(data?.message || "Agent watch repo analysis completed.");
              } catch (error) {
                setActionMessage(error instanceof Error ? error.message : "Failed to analyze repo.");
              } finally {
                setIsAnalyzing(false);
              }
            }}
            style={primaryActionButtonStyle}
          >
            {isAnalyzing ? "Analyzing..." : analyzeLabel}
          </button>
          {payload.canonical_url ? (
            <a href={payload.canonical_url} target="_blank" rel="noreferrer" style={buttonLinkStyle}>
              Open Source
            </a>
          ) : null}
        </div>
      </div>

      {actionMessage ? (
        <div style={actionMessageStyle}>
          {actionMessage}
        </div>
      ) : null}

      <SectionCard title="Repo Snapshot">
        <div style={metricsGridStyle}>
          <Metric label="Current score" value={scoreLabel(payload.agent_watch_score)} />
          <Metric label="Stars" value={scoreLabel(meta.repo_stars)} />
          <Metric label="Language" value={cleanDisplayText(meta.language) || "N/A"} />
          <Metric label="First seen" value={compactDateLabel(tracking?.first_seen)} />
          <Metric label="Last seen" value={compactDateLabel(tracking?.last_seen)} />
          <Metric label="Days observed" value={tracking?.days_observed != null ? String(tracking.days_observed) : "N/A"} />
          <Metric label="Observations" value={tracking?.observations != null ? String(tracking.observations) : "N/A"} />
          <Metric label="Score delta" value={deltaLabel(tracking?.score_change)} />
          <Metric label="Tracking state" value={trackingState} />
        </div>
        <div style={{ marginTop: "16px", color: "var(--app-text-muted)", lineHeight: 1.8 }}>
          {cleanDisplayText(payload.summary) || cleanDisplayText(profile?.repo_summary) || "No repo summary available yet."}
        </div>
      </SectionCard>

      <SectionCard title="Why This Repo May Matter To AI Radar">
        <div style={{ display: "grid", gap: "14px" }}>
          <div style={decisionGridStyle}>
            <DecisionCard label="Why track now" value={whyTrackNow} />
            <DecisionCard label="What changed" value={whatChanged} />
          </div>
          <DecisionBlock
            label="Quick read"
            value={
              cleanDisplayText(profile?.why_it_matters) ||
              cleanDisplayText(profile?.project_fit) ||
              "No decision-oriented summary generated yet."
            }
          />
          <div style={decisionGridStyle}>
            <DecisionCard
              label="AI Radar fit"
              value={cleanDisplayText(profile?.project_fit) || "Not assessed yet."}
            />
            <DecisionCard
              label="Use this when"
              value={
                cleanDisplayText(profile?.suggested_use_cases?.[0]) ||
                "No concrete use case has been surfaced yet."
              }
            />
            <DecisionCard
              label="Watch out for"
              value={cleanDisplayText(profile?.risks?.[0]) || "No major risk flagged yet."}
            />
          </div>
          {decisionSummaryBits.length ? (
            <div style={decisionStripStyle}>
              {decisionSummaryBits.map((bit, index) => (
                <span key={`${bit}-${index}`}>{bit}</span>
              ))}
            </div>
          ) : null}
        </div>
      </SectionCard>

      <SectionCard title="LLM Repo Profile">
        <div style={{ display: "grid", gap: "14px" }}>
          <ProfileBlock label="What it does" value={cleanDisplayText(profile?.what_it_does) || "Not generated yet."} />
          <ProfileBlock label="Why it matters" value={cleanDisplayText(profile?.why_it_matters) || "Not generated yet."} />
          <ProfileBlock label="Project fit" value={cleanDisplayText(profile?.project_fit) || "Not generated yet."} />
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: "14px" }}>
            <ListBlock
              label="Suggested use cases"
              items={cleanDisplayList(profile?.suggested_use_cases || [])}
              emptyLabel="No use cases generated yet."
            />
            <ListBlock
              label="Risks"
              items={cleanDisplayList(profile?.risks || [])}
              emptyLabel="No risks generated yet."
            />
          </div>
          <div style={{ color: "var(--app-text-muted)", fontSize: "13px" }}>
            Confidence: {cleanDisplayText(profile?.confidence) || "N/A"}
            {profile?.provider_used || profile?.model_used
              ? ` · ${cleanDisplayText(profile?.provider_used) || "provider"}${profile?.model_used ? ` / ${cleanDisplayText(profile?.model_used)}` : ""}`
              : ""}
          </div>
        </div>
      </SectionCard>

      <SectionCard title="History">
        {history.length ? (
          <div style={{ display: "grid", gap: "10px" }}>
            {history.map((item, index) => (
              <div key={`${item.captured_at || "snapshot"}-${index}`} style={historyRowStyle}>
                <div>
                  <div style={{ color: "var(--app-text-strong)", fontWeight: 700 }}>{compactDateLabel(item.captured_at)}</div>
                  <div style={{ color: "var(--app-text-muted)", fontSize: "13px" }}>{cleanDisplayText(item.source) || "unknown source"}</div>
                </div>
                <div style={{ color: "var(--app-text-strong)", fontWeight: 700 }}>Score {scoreLabel(item.agent_watch_score)}</div>
                <div style={{ color: "var(--app-text-muted)" }}>Stars {scoreLabel(item.repo_stars)}</div>
              </div>
            ))}
          </div>
        ) : (
          <div style={{ color: "var(--app-text-muted)" }}>No history snapshots available yet.</div>
        )}
      </SectionCard>
    </AppContainer>
  );
}

function AgentWatchDetailSkeleton() {
  return (
    <AppContainer>
      <div style={{ color: "var(--app-text-muted)" }}>Loading repo detail...</div>
    </AppContainer>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div style={metricCardStyle}>
      <div style={{ color: "var(--app-text-subtle)", fontSize: "12px", textTransform: "uppercase" }}>{label}</div>
      <div style={{ color: "var(--app-text-strong)", fontWeight: 800, fontSize: "24px", lineHeight: 1.1 }}>{value}</div>
    </div>
  );
}

function DecisionBlock({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: "grid", gap: "6px" }}>
      <div style={{ color: "var(--app-success-fg)", fontSize: "12px", fontWeight: 700, textTransform: "uppercase" }}>{label}</div>
      <div style={{ color: "var(--app-text-muted)", lineHeight: 1.8 }}>{value}</div>
    </div>
  );
}

function DecisionCard({ label, value }: { label: string; value: string }) {
  return (
    <div style={decisionCardStyle}>
      <div style={{ color: "var(--app-success-fg)", fontSize: "12px", fontWeight: 700, textTransform: "uppercase" }}>{label}</div>
      <div style={{ color: "var(--app-text-muted)", lineHeight: 1.7 }}>{value}</div>
    </div>
  );
}

function ProfileBlock({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: "grid", gap: "6px" }}>
      <div style={{ color: "var(--app-info-fg)", fontSize: "12px", fontWeight: 700, textTransform: "uppercase" }}>{label}</div>
      <div style={{ color: "var(--app-text-muted)", lineHeight: 1.8 }}>{value}</div>
    </div>
  );
}

function ListBlock({
  label,
  items,
  emptyLabel,
}: {
  label: string;
  items: string[];
  emptyLabel: string;
}) {
  return (
    <div style={listBlockStyle}>
      <div style={{ color: "var(--app-text-strong)", fontWeight: 700 }}>{label}</div>
      {items.length ? (
        <div style={{ display: "grid", gap: "8px" }}>
          {items.map((item, index) => (
            <div key={`${label}-${index}`} style={{ color: "var(--app-text-muted)", lineHeight: 1.7 }}>
              {item}
            </div>
          ))}
        </div>
      ) : (
        <div style={{ color: "var(--app-text-muted)" }}>{emptyLabel}</div>
      )}
    </div>
  );
}

const buttonLinkStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  padding: "10px 14px",
  borderRadius: "12px",
  border: "1px solid var(--app-surface-border)",
  background: "var(--app-secondary-action-bg)",
  color: "var(--app-text-strong)",
  fontWeight: 600,
  textDecoration: "none",
};

const metricsGridStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))",
  gap: "12px",
};

const metricCardStyle: CSSProperties = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "14px",
  padding: "14px 16px",
  background: "var(--app-surface-muted-bg)",
  display: "grid",
  gap: "8px",
};

const decisionGridStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
  gap: "12px",
};

const decisionCardStyle: CSSProperties = {
  border: "1px solid var(--app-success-border)",
  borderRadius: "14px",
  padding: "14px 16px",
  background: "var(--app-success-bg)",
  display: "grid",
  gap: "8px",
};

const decisionStripStyle: CSSProperties = {
  display: "flex",
  gap: "10px",
  flexWrap: "wrap",
  padding: "12px 14px",
  borderRadius: "12px",
  border: "1px solid var(--app-success-border)",
  background: "var(--app-success-bg)",
  color: "var(--app-success-fg)",
  fontSize: "13px",
  fontWeight: 600,
};

const listBlockStyle: CSSProperties = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "14px",
  padding: "14px 16px",
  background: "var(--app-surface-muted-bg)",
  display: "grid",
  gap: "10px",
};

const historyRowStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "minmax(140px, 1.2fr) minmax(120px, 0.8fr) minmax(120px, 0.8fr)",
  gap: "12px",
  alignItems: "center",
  border: "1px solid var(--app-surface-border)",
  borderRadius: "12px",
  padding: "12px 14px",
  background: "var(--app-surface-muted-bg)",
};

const readyBadgeStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  padding: "4px 10px",
  borderRadius: "999px",
  background: "var(--app-success-bg)",
  border: "1px solid var(--app-success-border)",
  color: "var(--app-success-fg)",
  fontSize: "12px",
  fontWeight: 700,
};

const pendingBadgeStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  padding: "4px 10px",
  borderRadius: "999px",
  background: "var(--app-chip-bg)",
  border: "1px solid var(--app-chip-border)",
  color: "var(--app-chip-fg)",
  fontSize: "12px",
  fontWeight: 700,
};

const trackingBadgeStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  padding: "4px 10px",
  borderRadius: "999px",
  background: "var(--app-info-bg)",
  border: "1px solid var(--app-info-border)",
  color: "var(--app-info-fg)",
  fontSize: "12px",
  fontWeight: 700,
};

function trackingStateBadgeStyle(state: string): CSSProperties {
  const palette = {
    new: { border: "var(--app-info-border)", background: "var(--app-info-bg)", color: "var(--app-info-fg)" },
    rising: { border: "var(--app-success-border)", background: "var(--app-success-bg)", color: "var(--app-success-fg)" },
    stable: { border: "var(--app-chip-border)", background: "var(--app-chip-bg)", color: "var(--app-chip-fg)" },
    cooling: { border: "var(--app-warning-border)", background: "var(--app-warning-bg)", color: "var(--app-warning-fg)" },
    untracked: { border: "var(--app-chip-border)", background: "var(--app-chip-bg)", color: "var(--app-chip-fg)" },
  } as const;

  const selected = palette[state as keyof typeof palette] || palette.untracked;
  return {
    display: "inline-flex",
    alignItems: "center",
    padding: "4px 10px",
    borderRadius: "999px",
    border: `1px solid ${selected.border}`,
    background: selected.background,
    color: selected.color,
    fontSize: "12px",
    fontWeight: 700,
    textTransform: "capitalize",
  };
}

const analysisMetaBadgeStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  padding: "4px 10px",
  borderRadius: "999px",
  background: "var(--app-warning-bg)",
  border: "1px solid var(--app-warning-border)",
  color: "var(--app-warning-fg)",
  fontSize: "12px",
  fontWeight: 700,
};

const primaryActionButtonStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  padding: "10px 14px",
  borderRadius: "12px",
  border: "1px solid var(--app-primary-action-border)",
  background: "var(--app-primary-action-bg)",
  color: "var(--app-primary-action-fg)",
  fontWeight: 700,
  cursor: "pointer",
};

const secondaryActionButtonStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  padding: "10px 14px",
  borderRadius: "12px",
  border: "1px solid var(--app-surface-border)",
  background: "var(--app-secondary-action-bg)",
  color: "var(--app-text-strong)",
  fontWeight: 700,
  cursor: "pointer",
};

const actionMessageStyle: CSSProperties = {
  marginBottom: "16px",
  padding: "12px 14px",
  borderRadius: "12px",
  border: "1px solid var(--app-success-border)",
  background: "var(--app-success-bg)",
  color: "var(--app-success-fg)",
  fontWeight: 600,
};

const errorPanelStyle: CSSProperties = {
  display: "grid",
  gap: "14px",
  padding: "14px 16px",
  borderRadius: "12px",
  border: "1px solid var(--app-danger-border)",
  background: "var(--app-danger-bg)",
  color: "var(--app-danger-fg)",
  fontWeight: 600,
};
