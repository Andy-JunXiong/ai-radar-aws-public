"use client";

import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import Link from "next/link";
import { BarChart3, BookOpenCheck, BrainCircuit, Gauge, Radar, RefreshCw } from "lucide-react";
import AppContainer from "@/components/AppContainer";
import { apiUrl } from "@/lib/api";
import { adminFetch } from "@/lib/adminAuth";
import { cleanDisplayList, cleanDisplayText } from "@/lib/displayText";

const RADAR_SUMMARY_TIMEOUT_MS = 8000;

type RadarTopicItem = {
  topic?: string;
  label?: string;
  score?: number | string | null;
  priority_score?: number | string | null;
  count?: number | string | null;
  rising_score?: number | string | null;
  momentum_delta?: number | string | null;
  summary?: string;
  reason?: string[] | string;
  momentum?: string;
  ["7d"]?: number | string | null;
  ["30d"]?: number | string | null;
};

type RadarPayload = {
  agent_watch?: {
    signal_count?: number;
    top_signal_count?: number;
    runtime_sources?: string[];
    signals?: Array<{
      title?: string;
      url?: string;
      source?: string;
      summary?: string;
      agent_subtopic?: string;
      profile?: {
        what_it_does?: string;
        project_fit?: string;
        why_it_matters?: string;
      };
      tracking?: Record<string, unknown>;
    }>;
    highlights?: Array<{
      title?: string;
      summary?: string;
      url?: string;
      source?: string;
      published_at?: string;
      agent_subtopic?: string;
      agent_watch_score?: number | string | null;
      repo_stars?: number | string | null;
      language?: string;
      matched_keywords?: string[];
    }>;
  };
  friction_signals?: {
    signal_count?: number;
    top_signal_count?: number;
    runtime_sources?: string[];
    signals?: Array<{
      title?: string;
      url?: string;
      source?: string;
      summary?: string;
      friction_subtopic?: string;
      profile?: {
        problem_summary?: string;
        why_this_matters?: string;
        product_opportunity?: string;
      };
    }>;
    highlights?: Array<{
      title?: string;
      summary?: string;
      url?: string;
      source?: string;
      published_at?: string;
      friction_subtopic?: string;
      friction_score?: number | string | null;
      pain_severity_score?: number | string | null;
      ecosystem_relevance_score?: number | string | null;
      repo_name?: string;
      matched_keywords?: string[];
    }>;
  };
  topic_trends?: {
    date?: string;
    generated_at?: string;
    items?: {
      topic_counts?: Record<string, number>;
      top_topics?: Array<[string, number]> | RadarTopicItem[];
      high_importance_topics?: Record<string, number>;
    };
  };
  topic_momentum?: {
    date?: string;
    generated_at?: string;
    items?: Record<
      string,
      {
        ["7d"]?: number;
        ["30d"]?: number;
        momentum?: string;
      }
    >;
  };
  rising_topics?: {
    date?: string;
    generated_at?: string;
    items?: {
      topic_scores?: Record<string, unknown>;
      rising_topics?: RadarTopicItem[];
    };
  };
  strategic_priority?: {
    date?: string;
    generated_at?: string;
    items?: {
      strategic_priority_topics?: RadarTopicItem[];
      priority_topic_map?: Record<string, unknown>;
    };
  };
  weekly_momentum?: {
    date?: string;
    generated_at?: string;
    items?: {
      topic_momentum?: Record<string, unknown>;
      rising_this_week?: RadarTopicItem[];
      cooling_this_week?: RadarTopicItem[];
      stable_this_week?: RadarTopicItem[];
    };
  };
};

type AgentWatchSignal = NonNullable<NonNullable<RadarPayload["agent_watch"]>["signals"]>[number];
type FrictionSignal = NonNullable<NonNullable<RadarPayload["friction_signals"]>["signals"]>[number];

type RelatedReflection = {
  id: string;
  title?: string;
  timestamp?: string;
  source?: string;
  tags?: string[];
  match_score?: number;
  matched_topics?: string[];
  matched_terms?: string[];
};

type TopicLike = RadarTopicItem | [string, number] | string | undefined;

function getTopicLabel(topicItem: TopicLike) {
  if (Array.isArray(topicItem)) return topicItem[0] || "General AI";
  if (typeof topicItem === "string" && topicItem.trim()) return topicItem;
  if (typeof topicItem === "object" && topicItem !== null) {
    if (topicItem.topic) return topicItem.topic;
    if (topicItem.label) return topicItem.label;
  }
  return "General AI";
}

function getTopicScore(topicItem: TopicLike): number | string | null {
  if (Array.isArray(topicItem)) {
    const raw = topicItem[1];
    if (raw === null || raw === undefined) return null;
    const num = Number(raw);
    return Number.isFinite(num) ? num : raw;
  }

  if (typeof topicItem === "object" && topicItem !== null) {
    const raw =
      topicItem.priority_score ??
      topicItem.rising_score ??
      topicItem.momentum_delta ??
      topicItem.score ??
      topicItem.count ??
      null;

    if (raw === null || raw === undefined || raw === "") return null;

    const num = Number(raw);
    return Number.isFinite(num) ? num : raw;
  }

  return null;
}

function buildPriorityText(topicLabel: string, score: number | string | null, index: number) {
  if (index === 0) {
    return `Prioritize ${topicLabel} because it currently carries the strongest strategic weight in the radar.`;
  }

  if (index === 1) {
    return `Watch ${topicLabel} closely for downstream project and product impact as related signals continue to accumulate.`;
  }

  if (score !== null && score !== undefined) {
    return `${topicLabel} remains worth attention because it is still showing meaningful priority strength in the current batch.`;
  }

  return `${topicLabel} should stay on the watchlist as part of the current signal environment.`;
}

export default function RadarPage() {
  const [radar, setRadar] = useState<RadarPayload | null>(null);
  const [relatedReflections, setRelatedReflections] = useState<RelatedReflection[]>([]);
  const [radarLoading, setRadarLoading] = useState(true);
  const [radarError, setRadarError] = useState("");
  const [radarRequestMs, setRadarRequestMs] = useState<number | null>(null);

  const loadRadarSummary = useCallback(() => {
    const controller = new AbortController();
    let cancelled = false;
    let timedOut = false;
    const timeout = window.setTimeout(() => {
      timedOut = true;
      controller.abort("timeout");
    }, RADAR_SUMMARY_TIMEOUT_MS);
    const startedAt = performance.now();

    adminFetch(apiUrl("/radar/intelligence"), { signal: controller.signal, cache: "no-store" })
      .then((res) => {
        if (!res.ok) {
          throw new Error(`Radar summary request failed (${res.status})`);
        }
        return res.json();
      })
      .then((data) => {
        if (cancelled) return;
        setRadar(data);
        setRadarRequestMs(performance.now() - startedAt);
      })
      .catch((err) => {
        if (
          cancelled ||
          (err instanceof DOMException && err.name === "AbortError" && !timedOut)
        ) {
          return;
        }

        const message =
          err instanceof DOMException && err.name === "AbortError"
            ? "Radar summary request timed out. Confirm the backend is running, then retry."
            : err instanceof Error
              ? err.message
              : "Failed to load radar summary.";
        console.error("Failed to load radar:", err);
        setRadarError(message);
        setRadar(null);
        setRadarRequestMs(null);
      })
      .finally(() => {
        window.clearTimeout(timeout);
        if (cancelled) return;
        setRadarLoading(false);
      });

    return () => {
      cancelled = true;
      window.clearTimeout(timeout);
      controller.abort("cleanup");
    };
  }, []);

  useEffect(() => {
    return loadRadarSummary();
  }, [loadRadarSummary]);

  const dominantTopics = useMemo(() => {
    const raw = radar?.topic_trends?.items?.top_topics || [];

    return (Array.isArray(raw) ? raw : []).slice(0, 4).map((item) => ({
      label: getTopicLabel(item),
      score: getTopicScore(item),
    }));
  }, [radar]);

  const risingTopics = useMemo(() => {
    const raw = radar?.rising_topics?.items?.rising_topics || [];

    return (Array.isArray(raw) ? raw : []).slice(0, 4).map((item) => ({
      label: getTopicLabel(item),
      score: getTopicScore(item),
    }));
  }, [radar]);

  const coolingTopics = useMemo(() => {
    const raw = radar?.weekly_momentum?.items?.cooling_this_week || [];

    return (Array.isArray(raw) ? raw : []).slice(0, 4).map((item) => ({
      label: getTopicLabel(item),
      score: getTopicScore(item),
    }));
  }, [radar]);

  const priorityItems = useMemo(() => {
    const rawTopics =
      radar?.strategic_priority?.items?.strategic_priority_topics || [];

    const topicBased = (Array.isArray(rawTopics) ? rawTopics : [])
      .slice(0, 4)
      .map((item, index) => {
        const label = getTopicLabel(item);
        const score = getTopicScore(item);
        return buildPriorityText(label, score, index);
      });

    if (topicBased.length > 0) return topicBased;

    return [
      "Use high-score signals as the first filter for strategic attention.",
      "Track topic momentum before turning weak signals into deep analysis tasks.",
      "Prioritize repeated patterns across stronger sources over isolated updates.",
    ];
  }, [radar]);

  const whatMattersNow = useMemo(() => {
    const dominant = dominantTopics[0]?.label;
    const rising = risingTopics[0]?.label;
    const priority =
      radar?.strategic_priority?.items?.strategic_priority_topics?.[0]?.topic;

    if (priority && dominant && rising) {
      return `Current attention is led by ${dominant}, while ${rising} is showing the clearest momentum. Strategic priority should go first to ${priority}, because it sits at the intersection of frequency, momentum, and priority scoring.`;
    }

    if (dominant && rising) {
      return `Current attention is led by ${dominant}, while ${rising} is the clearest momentum signal in the recent batch. Strategic focus should go to the highest-priority topics rather than raw volume alone.`;
    }

    if (dominant) {
      return `Current attention is concentrated around ${dominant}. Strategic focus should go to repeated patterns across stronger topics instead of isolated updates.`;
    }

    return "The radar is active, but the current batch still needs stronger topic structure before a sharper strategic summary can be produced.";
  }, [radar, dominantTopics, risingTopics]);

  const weeklyReadout = useMemo(() => {
    const topPriority =
      radar?.strategic_priority?.items?.strategic_priority_topics?.[0];
    const fastestRising = radar?.weekly_momentum?.items?.rising_this_week?.[0];
    const leadTopic = dominantTopics[0]?.label;

    const priorityLabel = getTopicLabel(topPriority);
    const risingLabel = getTopicLabel(fastestRising);

    if (priorityLabel && risingLabel && leadTopic) {
      return `This week, keep primary attention on ${priorityLabel}. ${risingLabel} is accelerating fastest in the weekly view, while ${leadTopic} still leads overall attention. The best move is to focus on topics where frequency and momentum reinforce each other.`;
    }

    if (priorityLabel && leadTopic) {
      return `This week, keep primary attention on ${priorityLabel}, while continuing to monitor ${leadTopic} as the dominant topic in the current radar batch.`;
    }

    if (leadTopic) {
      return `This week, keep attention centered on ${leadTopic} and prioritize repeated topic patterns over isolated updates.`;
    }

    return "This week, use dominant topics and rising momentum as the main filters for strategic attention.";
  }, [radar, dominantTopics]);

  const topSignalCount = useMemo(() => {
    const topicCounts = radar?.topic_trends?.items?.topic_counts || {};
    return Object.values(topicCounts).reduce((sum, value) => {
      const num = Number(value);
      return sum + (Number.isFinite(num) ? num : 0);
    }, 0);
  }, [radar]);

  const agentWatchHighlights = useMemo(() => {
    const raw = radar?.agent_watch?.highlights || [];
    return (Array.isArray(raw) ? raw : []).slice(0, 3);
  }, [radar]);

  const agentWatchSignals = useMemo(() => {
    const raw = radar?.agent_watch?.signals;
    return (Array.isArray(raw) ? raw : []) as AgentWatchSignal[];
  }, [radar]);

  const frictionHighlights = useMemo(() => {
    const raw = radar?.friction_signals?.highlights || [];
    return (Array.isArray(raw) ? raw : []).slice(0, 3);
  }, [radar]);

  const frictionSignals = useMemo(() => {
    const raw = radar?.friction_signals?.signals;
    return (Array.isArray(raw) ? raw : []) as FrictionSignal[];
  }, [radar]);

  const agentWatchProfileReadyCount = useMemo(
    () =>
      agentWatchSignals.filter((item) =>
        item?.profile?.what_it_does || item?.profile?.project_fit || item?.profile?.why_it_matters,
      ).length,
    [agentWatchSignals],
  );

  const agentWatchTrackingReadyCount = useMemo(
    () => agentWatchSignals.filter((item) => item?.tracking).length,
    [agentWatchSignals],
  );
  const agentWatchProfilePendingCount = useMemo(
    () =>
      agentWatchSignals.filter(
        (item) =>
          !(item?.profile?.what_it_does || item?.profile?.project_fit || item?.profile?.why_it_matters),
      ).length,
    [agentWatchSignals],
  );

  const frictionInsightReadyCount = useMemo(
    () =>
      frictionSignals.filter((item) =>
        item?.profile?.problem_summary || item?.profile?.why_this_matters || item?.profile?.product_opportunity,
      ).length,
    [frictionSignals],
  );
  const frictionInsightPendingCount = useMemo(
    () =>
      frictionSignals.filter(
        (item) =>
          !(item?.profile?.problem_summary || item?.profile?.why_this_matters || item?.profile?.product_opportunity),
      ).length,
    [frictionSignals],
  );

  const strongestAgentWatchItem = useMemo(() => {
    if (agentWatchHighlights.length) return agentWatchHighlights[0];
    return agentWatchSignals[0] || null;
  }, [agentWatchHighlights, agentWatchSignals]);

  const nextPendingAgentWatchItem = useMemo(
    () =>
      agentWatchSignals.find(
        (item) =>
          !(item?.profile?.what_it_does || item?.profile?.project_fit || item?.profile?.why_it_matters),
      ) || null,
    [agentWatchSignals],
  );

  const strongestFrictionItem = useMemo(() => {
    if (frictionHighlights.length) return frictionHighlights[0];
    return frictionSignals[0] || null;
  }, [frictionHighlights, frictionSignals]);

  const nextPendingFrictionItem = useMemo(
    () =>
      frictionSignals.find(
        (item) =>
          !(item?.profile?.problem_summary || item?.profile?.why_this_matters || item?.profile?.product_opportunity),
      ) || null,
    [frictionSignals],
  );

  const reflectionTopics = useMemo(() => {
    const topics = [
      ...dominantTopics.map((item) => item.label),
      ...risingTopics.map((item) => item.label),
      ...(agentWatchHighlights.length ? ["ai agents"] : []),
      ...(frictionHighlights.length ? ["friction"] : []),
    ]
      .map((item) => item.trim().toLowerCase())
      .filter(Boolean);
    return Array.from(new Set(topics)).slice(0, 4);
  }, [dominantTopics, risingTopics, agentWatchHighlights, frictionHighlights]);

  useEffect(() => {
    if (!reflectionTopics.length) {
      return;
    }

    const query = reflectionTopics.map((topic) => `topics=${encodeURIComponent(topic)}`).join("&");
    adminFetch(apiUrl(`/reflection/related?limit=3&${query}`), { cache: "no-store" })
      .then((res) => {
        if (!res.ok) {
          throw new Error("Failed to load related reflections.");
        }
        return res.json();
      })
      .then((data) => {
        setRelatedReflections(Array.isArray(data?.reflections) ? data.reflections : []);
      })
      .catch(() => {
        setRelatedReflections([]);
      });
  }, [reflectionTopics]);

  if (radarLoading && !radar) {
    return (
      <AppContainer style={radarShellStyle}>
        <RadarHeader
          loading={radarLoading}
          requestMs={radarRequestMs}
          topSignalCount={topSignalCount}
          leadTopic={dominantTopics[0]?.label || "General AI"}
          fastestMomentum={risingTopics[0]?.label || "N/A"}
        />
        <RadarSection eyebrow="Load state" title="Loading radar summary">
          <div style={radarLoadPanelStyle}>
            <strong>Reading `/radar/intelligence`</strong>
            <span>
              This request times out after {(RADAR_SUMMARY_TIMEOUT_MS / 1000).toFixed(0)}s and will show a retry path instead of sitting on an ambiguous loading state.
            </span>
          </div>
        </RadarSection>
      </AppContainer>
    );
  }

  if (radarError && !radar) {
    return (
      <AppContainer style={radarShellStyle}>
        <RadarHeader
          loading={radarLoading}
          requestMs={radarRequestMs}
          topSignalCount={topSignalCount}
          leadTopic={dominantTopics[0]?.label || "General AI"}
          fastestMomentum={risingTopics[0]?.label || "N/A"}
        />
        <RadarSection eyebrow="Load state" title="Radar summary unavailable">
          <div style={{ display: "grid", gap: "12px" }}>
            <div style={{ color: "var(--app-danger-fg)", fontSize: "14px", lineHeight: 1.65 }}>{radarError}</div>
            <div style={{ color: "var(--app-text-muted)", fontSize: "13px", lineHeight: 1.6 }}>
              Check `http://127.0.0.1:8000/radar/intelligence` if this persists.
            </div>
            <button
              type="button"
              onClick={() => {
                setRadarLoading(true);
                setRadarError("");
                loadRadarSummary();
              }}
              style={{
                width: "fit-content",
                border: "1px solid var(--app-primary-action-bg)",
                borderRadius: "8px",
                background: "var(--app-primary-action-bg)",
                color: "var(--app-primary-action-fg)",
                padding: "9px 13px",
                fontWeight: 800,
                cursor: "pointer",
              }}
            >
              Retry Radar Summary
            </button>
          </div>
        </RadarSection>
      </AppContainer>
    );
  }

  return (
    <AppContainer style={radarShellStyle}>
      <RadarHeader
        loading={radarLoading}
        requestMs={radarRequestMs}
        topSignalCount={topSignalCount}
        leadTopic={dominantTopics[0]?.label || "General AI"}
        fastestMomentum={risingTopics[0]?.label || "N/A"}
      />

      <RadarSection eyebrow="Load state" title="Radar readiness">
        <div style={radarLoadStateStyle(radarLoading ? "watch" : "good")}>
          <strong>{radarLoading ? "Refreshing radar summary" : "Radar summary ready"}</strong>
          <span>
            Loaded from `/radar/intelligence`
            {typeof radarRequestMs === "number" ? ` in ${(radarRequestMs / 1000).toFixed(2)}s` : ""}.
          </span>
          {radarLoading ? <span>Keeping the current summary visible while refresh completes.</span> : null}
        </div>
      </RadarSection>

      <RadarSection eyebrow="Handoff" title="Review handoff">
        <div style={radarHandoffGridStyle}>
          <QuickLaunchCard
            title="Knowledge Review"
            description="Open convergence briefs when Radar points to a theme that needs supply/demand context before review."
            href="/knowledge"
            ctaLabel="Open Knowledge"
          />
          <QuickLaunchCard
            title="Review Inbox"
            description="Turn a matched brief or signal into Confirm, Watch, Reject, or Action after checking project fit and evidence gates."
            href="/workspace/projects/review"
            ctaLabel="Open Review"
          />
          <QuickLaunchCard
            title="Metrics"
            description="Check whether production summaries are fresh before trusting operational counts or trend movement."
            href="/admin/metrics"
            ctaLabel="Open Metrics"
          />
          <QuickLaunchCard
            title="Manual Completion"
            description="Finish manual-derived signals through upload intent, Signal Detail review, and Workspace durability."
            href="/manual"
            ctaLabel="Open Manual"
          />
        </div>
      </RadarSection>

      <RadarSection eyebrow="Strategic readout" title="What matters now">
        <div style={{ display: "grid", gap: "12px" }}>
          <div
            style={{
              color: "var(--app-text-muted)",
              lineHeight: 1.8,
              fontSize: "15px",
            }}
          >
            {whatMattersNow}
          </div>

          <div
            style={{
              display: "flex",
              gap: "10px",
              flexWrap: "wrap",
            }}
          >
            <InfoBadge label={`Top signals: ${topSignalCount}`} />
            <InfoBadge
              label={`Lead topic: ${dominantTopics[0]?.label || "General AI"}`}
            />
            <InfoBadge
              label={`Fastest momentum: ${risingTopics[0]?.label || "N/A"}`}
            />
          </div>
        </div>
      </RadarSection>

      <RadarSection eyebrow="Momentum" title="Topic momentum">
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 220px), 1fr))",
            gap: "12px",
          }}
        >
          <MomentumColumn
            title="Dominant Topics"
            items={dominantTopics}
            emptyText="No dominant topics available."
          />
          <MomentumColumn
            title="Rising Topics"
            items={risingTopics}
            emptyText="No rising topics available."
          />
          <MomentumColumn
            title="Cooling Topics"
            items={coolingTopics}
            emptyText="No cooling topics available."
          />
        </div>
      </RadarSection>

      <RadarSection eyebrow="Priorities" title="Strategic priorities">
        {priorityItems.length ? (
          <div style={{ display: "grid", gap: "12px" }}>
            {priorityItems.map((item, index) => (
              <div
                key={`${item}-${index}`}
                style={{
                  padding: "14px 16px",
                  borderRadius: "8px",
                  background: "var(--app-surface-muted-bg)",
                  border: "1px solid var(--app-surface-border)",
                  color: "var(--app-text-muted)",
                  lineHeight: 1.7,
                }}
              >
                <strong style={{ color: "var(--app-text-strong)" }}>{index + 1}.</strong>{" "}
                {item}
              </div>
            ))}
          </div>
        ) : (
          <div style={{ color: "var(--app-text-subtle)" }}>
            No strategic priorities available.
          </div>
        )}
      </RadarSection>

      <RadarSection eyebrow="Reflection context" title="Related deep reflections">
        {relatedReflections.length ? (
          <div style={{ display: "grid", gap: "12px" }}>
            <QuickLaunchCard
              title="Open Most Relevant Reflection Today"
              description={
                `${
                  cleanDisplayText(relatedReflections[0]?.title) ||
                  cleanDisplayText(relatedReflections[0]?.id) ||
                  "Open the reflection most aligned with today's radar topics."
                }${
                  relatedReflections[0]?.match_score !== undefined
                    ? ` | match ${relatedReflections[0]?.match_score}`
                    : ""
                }`
              }
              href={`/reflections/detail?id=${encodeURIComponent(relatedReflections[0]?.id || "")}`}
              ctaLabel="Open reflection"
            />
            {relatedReflections.map((item) => (
              <div
                key={item.id}
                style={{
                  padding: "14px 16px",
                  borderRadius: "8px",
                  background: "var(--app-surface-muted-bg)",
                  border: "1px solid var(--app-surface-border)",
                  display: "grid",
                  gap: "8px",
                }}
              >
                <div style={{ color: "var(--app-text-strong)", fontWeight: 700 }}>
                  {item.title || item.id}
                </div>
                <div style={{ color: "var(--app-text-subtle)", fontSize: "13px" }}>
                  {(item.source || "unknown source")}
                  {item.timestamp ? ` | ${item.timestamp}` : ""}
                  {item.match_score !== undefined ? ` | match ${item.match_score}` : ""}
                </div>
                {(item.matched_topics || []).length ? (
                  <div style={{ color: "var(--app-text-muted)", fontSize: "13px" }}>
                    Matched topics: {(item.matched_topics || []).join(", ")}
                  </div>
                ) : null}
                {(item.matched_terms || []).length ? (
                  <div style={{ color: "var(--app-text-subtle)", fontSize: "13px" }}>
                    Matched terms: {(item.matched_terms || []).join(", ")}
                  </div>
                ) : null}
                {(item.tags || []).length ? (
                  <div style={{ color: "var(--app-text-muted)", fontSize: "13px" }}>
                    Tags: {(item.tags || []).join(", ")}
                  </div>
                ) : null}
                <div>
                  <Link
                    href={`/reflections/detail?id=${encodeURIComponent(item.id)}`}
                    style={{
                      color: "var(--app-info-fg)",
                      fontWeight: 700,
                      textDecoration: "none",
                    }}
                  >
                    Open reflection
                  </Link>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div style={{ color: "var(--app-text-subtle)" }}>
            No related reflections matched the current radar topics yet.
          </div>
        )}
      </RadarSection>

      <RadarSection eyebrow="Supply side" title="AI Agent Watch">
        <div style={{ display: "grid", gap: "12px" }}>
          <div
            style={{
              display: "flex",
              gap: "10px",
              flexWrap: "wrap",
            }}
          >
            <InfoBadge
              label={`Agent signals: ${radar?.agent_watch?.signal_count ?? 0}`}
            />
            <InfoBadge
              label={`Highlights: ${radar?.agent_watch?.top_signal_count ?? 0}`}
            />
            <InfoBadge
              label={`Sources: ${
                cleanDisplayList(radar?.agent_watch?.runtime_sources || []).join(", ") || "N/A"
              }`}
            />
            <InfoBadge label={`Profiles ready: ${agentWatchProfileReadyCount}`} />
            <InfoBadge label={`Tracking ready: ${agentWatchTrackingReadyCount}`} />
          </div>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 220px), 1fr))",
              gap: "12px",
            }}
          >
            <ReadinessCard
              title="List Ready"
              value={`${radar?.agent_watch?.signal_count ?? 0} repos surfaced`}
              tone="blue"
              description="The watchlist has daily-discovered agent repos ready to review."
            />
            <ReadinessCard
              title="Tracking Ready"
              value={`${agentWatchTrackingReadyCount} repos tracked`}
              tone="indigo"
              description="These repos already have snapshot history such as first seen, days observed, and score delta."
            />
            <ReadinessCard
              title="LLM Profile Ready"
              value={`${agentWatchProfileReadyCount} repos analyzed`}
              tone="green"
              description="These repos already have what-it-does, why-it-matters, and project-fit analysis."
            />
          </div>

          {strongestAgentWatchItem ? (
            <QuickLaunchCard
              title="Open Strongest Agent Watch Item"
              description={
                cleanDisplayText(strongestAgentWatchItem.title) ||
                "Open the top repo from today’s agent watch run."
              }
              href={
                strongestAgentWatchItem.url
                  ? `/agent-watch/detail?entity_id=${encodeURIComponent(strongestAgentWatchItem.url)}`
                  : "/agent-watch"
              }
              ctaLabel="Open strongest item"
            />
          ) : null}

          {nextPendingAgentWatchItem ? (
            <QuickLaunchCard
              title="Open Next Pending Repo For Analysis"
              description={
                `${
                  cleanDisplayText(nextPendingAgentWatchItem.title) ||
                  "Open the next tracked repo that still needs LLM analysis."
                }${agentWatchProfilePendingCount ? ` | ${agentWatchProfilePendingCount} repos still pending` : ""}`
              }
              href={
                nextPendingAgentWatchItem.url
                  ? `/agent-watch/detail?entity_id=${encodeURIComponent(nextPendingAgentWatchItem.url)}`
                  : "/agent-watch"
              }
              ctaLabel="Open pending repo"
            />
          ) : null}

          {agentWatchHighlights.length ? (
            <div style={{ display: "grid", gap: "12px" }}>
              {agentWatchHighlights.map((item, index) => {
                const metaBits = [];
                if (item.repo_stars !== null && item.repo_stars !== undefined && item.repo_stars !== "") {
                  metaBits.push(`${item.repo_stars} stars`);
                }
                if (item.language) {
                  metaBits.push(cleanDisplayText(item.language));
                }
                if (item.agent_subtopic) {
                  metaBits.push(cleanDisplayText(item.agent_subtopic));
                }
                if (item.source) {
                  metaBits.push(cleanDisplayText(item.source));
                }

                return (
                  <div
                    key={`${item.title || "agent"}-${index}`}
                    style={{
                      padding: "14px 16px",
                      borderRadius: "8px",
                      background: "var(--app-surface-muted-bg)",
                      border: "1px solid var(--app-surface-border)",
                      display: "grid",
                      gap: "8px",
                    }}
                  >
                    <div style={{ color: "var(--app-text-strong)", fontWeight: 700 }}>
                      {cleanDisplayText(item.title) || "Untitled Agent Signal"}
                    </div>
                    {metaBits.length ? (
                      <div style={{ color: "var(--app-text-subtle)", fontSize: "13px" }}>
                        {metaBits.join(" | ")}
                      </div>
                    ) : null}
                    <div style={{ color: "var(--app-text-muted)", lineHeight: 1.7 }}>
                      {cleanDisplayText(item.summary) || "No summary available."}
                    </div>
                    {item.url ? (
                      <a
                        href={item.url}
                        target="_blank"
                        rel="noreferrer"
                        style={{
                          color: "var(--app-info-fg)",
                          fontWeight: 600,
                          textDecoration: "none",
                        }}
                      >
                        Open source
                      </a>
                    ) : null}
                  </div>
                );
              })}
            </div>
          ) : (
            <div style={{ color: "var(--app-text-subtle)" }}>
              No AI agent watch highlights available yet.
            </div>
          )}
        </div>
      </RadarSection>

      <RadarSection eyebrow="Demand side" title="Friction Signals">
        <div style={{ display: "grid", gap: "12px" }}>
          <div
            style={{
              display: "flex",
              gap: "10px",
              flexWrap: "wrap",
            }}
          >
            <InfoBadge
              label={`Friction signals: ${radar?.friction_signals?.signal_count ?? 0}`}
            />
            <InfoBadge
              label={`Highlights: ${radar?.friction_signals?.top_signal_count ?? 0}`}
            />
            <InfoBadge
              label={`Sources: ${
                cleanDisplayList(radar?.friction_signals?.runtime_sources || []).join(", ") || "N/A"
              }`}
            />
            <InfoBadge label={`Insights ready: ${frictionInsightReadyCount}`} />
          </div>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 220px), 1fr))",
              gap: "12px",
            }}
          >
            <ReadinessCard
              title="Signal Ready"
              value={`${radar?.friction_signals?.signal_count ?? 0} pain signals`}
              tone="amber"
              description="The pain watchlist is populated and ready for scanning."
            />
            <ReadinessCard
              title="Insight Ready"
              value={`${frictionInsightReadyCount} interpreted`}
              tone="green"
              description="These pain items already include why-it-matters and product-opportunity analysis."
            />
            <ReadinessCard
              title="Highlights Ready"
              value={`${radar?.friction_signals?.top_signal_count ?? 0} surfaced`}
              tone="orange"
              description="Top friction items have been promoted for faster review."
            />
          </div>

          {strongestFrictionItem ? (
            <QuickLaunchCard
              title="Open Strongest Friction Signal"
              description={
                cleanDisplayText(strongestFrictionItem.title) ||
                "Open the top pain signal from today’s friction run."
              }
              href={
                strongestFrictionItem.url
                  ? `/friction-signals/detail?entity_id=${encodeURIComponent(strongestFrictionItem.url)}`
                  : "/friction-signals"
              }
              ctaLabel="Open strongest item"
            />
          ) : null}

          {nextPendingFrictionItem ? (
            <QuickLaunchCard
              title="Open Next Pending Friction Item"
              description={
                `${
                  cleanDisplayText(nextPendingFrictionItem.title) ||
                  "Open the next friction item that still needs LLM interpretation."
                }${frictionInsightPendingCount ? ` | ${frictionInsightPendingCount} items still pending` : ""}`
              }
              href={
                nextPendingFrictionItem.url
                  ? `/friction-signals/detail?entity_id=${encodeURIComponent(nextPendingFrictionItem.url)}`
                  : "/friction-signals"
              }
              ctaLabel="Open pending friction"
            />
          ) : null}

          {frictionHighlights.length ? (
            <div style={{ display: "grid", gap: "12px" }}>
              {frictionHighlights.map((item, index) => {
                const metaBits = [];
                if (item.friction_subtopic) {
                  metaBits.push(cleanDisplayText(item.friction_subtopic));
                }
                if (item.repo_name) {
                  metaBits.push(cleanDisplayText(item.repo_name));
                }
                if (item.source) {
                  metaBits.push(cleanDisplayText(item.source));
                }

                return (
                  <div
                    key={`${item.title || "friction"}-${index}`}
                    style={{
                      padding: "14px 16px",
                      borderRadius: "8px",
                      background: "var(--app-warning-bg)",
                      border: "1px solid var(--app-warning-border)",
                      display: "grid",
                      gap: "8px",
                    }}
                  >
                    <div style={{ color: "var(--app-text-strong)", fontWeight: 700 }}>
                      {cleanDisplayText(item.title) || "Untitled Friction Signal"}
                    </div>
                    {metaBits.length ? (
                      <div style={{ color: "var(--app-warning-fg)", fontSize: "13px" }}>
                        {metaBits.join(" | ")}
                      </div>
                    ) : null}
                    <div style={{ color: "var(--app-warning-fg)", lineHeight: 1.7 }}>
                      {cleanDisplayText(item.summary) || "No friction summary available."}
                    </div>
                    <div style={{ color: "var(--app-warning-fg)", fontSize: "13px" }}>
                      Friction score {item.friction_score ?? "N/A"} | Pain {item.pain_severity_score ?? "N/A"}
                    </div>
                    {item.url ? (
                      <a
                        href={item.url}
                        target="_blank"
                        rel="noreferrer"
                        style={{
                          color: "var(--app-warning-fg)",
                          fontWeight: 600,
                          textDecoration: "none",
                        }}
                      >
                        Open discussion
                      </a>
                    ) : null}
                  </div>
                );
              })}
            </div>
          ) : (
            <div style={{ color: "var(--app-text-subtle)" }}>
              No friction signals available yet.
            </div>
          )}
        </div>
      </RadarSection>

      <RadarSection eyebrow="Weekly view" title="Weekly strategic readout" marginBottom="0">
        <div
          style={{
            color: "var(--app-text-muted)",
            lineHeight: 1.8,
            fontSize: "15px",
          }}
        >
          {weeklyReadout}
        </div>
      </RadarSection>
    </AppContainer>
  );
}

function RadarHeader({
  loading,
  requestMs,
  topSignalCount,
  leadTopic,
  fastestMomentum,
}: {
  loading: boolean;
  requestMs: number | null;
  topSignalCount: number;
  leadTopic: string;
  fastestMomentum: string;
}) {
  return (
    <section style={radarHeroStyle}>
      <div style={{ minWidth: 0 }}>
        <div style={eyebrowStyle}>Radar Summary</div>
        <h1 style={radarHeroTitleStyle}>Strategic readout for what matters now.</h1>
        <p style={radarHeroDescriptionStyle}>
          Radar turns topic movement, Agent Watch, Friction Signals, and related reflection context into a daily strategic intelligence view.
        </p>
        <div style={quickActionRowStyle}>
          <QuickAction href="/knowledge" label="Open Knowledge" icon={BrainCircuit} />
          <QuickAction href="/workspace/projects/review" label="Open Review" icon={BookOpenCheck} />
          <QuickAction href="/admin/metrics" label="Open Metrics" icon={BarChart3} />
        </div>
      </div>

      <div style={radarHeroPanelStyle}>
        <div style={summaryHeaderStyle}>
          {loading ? <RefreshCw size={18} aria-hidden="true" /> : <Gauge size={18} aria-hidden="true" />}
          <span>{loading ? "Refreshing radar" : "Radar ready"}</span>
        </div>
        <div style={summaryMetricGridStyle}>
          <SummaryMetric label="Top signals" value={String(topSignalCount)} />
          <SummaryMetric label="Lead topic" value={leadTopic} />
          <SummaryMetric label="Fastest momentum" value={fastestMomentum} />
          <SummaryMetric
            label="Load time"
            value={typeof requestMs === "number" ? `${(requestMs / 1000).toFixed(2)}s` : "n/a"}
          />
        </div>
      </div>
    </section>
  );
}

function QuickAction({
  href,
  label,
  icon: Icon,
}: {
  href: string;
  label: string;
  icon: typeof Radar;
}) {
  return (
    <Link href={href} style={quickActionStyle}>
      <Icon size={16} aria-hidden="true" />
      {label}
    </Link>
  );
}

function SummaryMetric({ label, value }: { label: string; value: string }) {
  return (
    <div style={summaryMetricStyle}>
      <div style={summaryMetricValueStyle}>{value}</div>
      <div style={summaryMetricLabelStyle}>{label}</div>
    </div>
  );
}

function RadarSection({
  eyebrow,
  title,
  children,
  marginBottom = "14px",
}: {
  eyebrow: string;
  title: string;
  children: ReactNode;
  marginBottom?: string;
}) {
  return (
    <section style={{ ...radarSectionStyle, marginBottom }}>
      <div style={radarSectionHeaderStyle}>
        <div style={eyebrowStyle}>{eyebrow}</div>
        <h2 style={radarSectionTitleStyle}>{title}</h2>
      </div>
      {children}
    </section>
  );
}

function MomentumColumn({
  title,
  items,
  emptyText,
}: {
  title: string;
  items: Array<{ label: string; score: number | string | null }>;
  emptyText: string;
}) {
  return (
    <div style={momentumColumnStyle}>
      <div style={momentumTitleStyle}>
        {title}
      </div>

      {items.length ? (
        <div style={{ display: "grid", gap: "10px" }}>
          {items.map((item, index) => (
            <div
              key={`${title}-${item.label}-${index}`}
              style={momentumItemStyle}
            >
              <div style={{ color: "var(--app-text-strong)", fontWeight: 600 }}>
                {item.label}
              </div>
              <div
                style={{
                  marginTop: "4px",
                  color: "var(--app-text-subtle)",
                  fontSize: "13px",
                }}
              >
                {item.score !== null && item.score !== undefined
                  ? `Score ${item.score}`
                  : "Score N/A"}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div style={{ color: "var(--app-text-subtle)" }}>{emptyText}</div>
      )}
    </div>
  );
}

function InfoBadge({ label }: { label: string }) {
  return (
    <span style={infoBadgeStyle}>
      {label}
    </span>
  );
}

function ReadinessCard({
  title,
  value,
  description,
  tone,
}: {
  title: string;
  value: string;
  description: string;
  tone: "blue" | "indigo" | "green" | "amber" | "orange";
}) {
  const toneMap = {
    blue: {
      border: "var(--app-info-border)",
      background: "var(--app-info-bg)",
      accent: "var(--app-info-fg)",
    },
    indigo: {
      border: "var(--app-info-border)",
      background: "var(--app-info-bg)",
      accent: "var(--app-info-fg)",
    },
    green: {
      border: "var(--app-success-border)",
      background: "var(--app-success-bg)",
      accent: "var(--app-success-fg)",
    },
    amber: {
      border: "var(--app-warning-border)",
      background: "var(--app-warning-bg)",
      accent: "var(--app-warning-fg)",
    },
    orange: {
      border: "var(--app-warning-border)",
      background: "var(--app-warning-bg)",
      accent: "var(--app-warning-fg)",
    },
  } as const;

  const palette = toneMap[tone];

  return (
    <div
      style={{
        border: `1px solid ${palette.border}`,
        borderRadius: "8px",
        padding: "14px 16px",
        background: palette.background,
        display: "grid",
        gap: "8px",
      }}
    >
      <div
        style={{
          color: palette.accent,
          fontSize: "12px",
          fontWeight: 700,
          textTransform: "uppercase",
        }}
      >
        {title}
      </div>
      <div style={{ color: "var(--app-text-strong)", fontWeight: 800, fontSize: "22px", lineHeight: 1.1 }}>
        {value}
      </div>
      <div style={{ color: "var(--app-text-muted)", lineHeight: 1.7, fontSize: "14px" }}>{description}</div>
    </div>
  );
}

function QuickLaunchCard({
  title,
  description,
  href,
  ctaLabel,
}: {
  title: string;
  description: string;
  href: string;
  ctaLabel: string;
}) {
  return (
    <div
      style={{
        border: "1px solid var(--app-surface-border)",
        borderRadius: "8px",
        padding: "14px 16px",
        background: "var(--app-surface-muted-bg)",
        display: "grid",
        gap: "10px",
      }}
    >
      <div style={{ color: "var(--app-text-strong)", fontWeight: 700 }}>{title}</div>
      <div style={{ color: "var(--app-text-muted)", lineHeight: 1.7 }}>{description}</div>
      <div>
        <Link
          href={href}
          style={{
            display: "inline-flex",
            alignItems: "center",
            padding: "8px 12px",
            borderRadius: "8px",
            border: "1px solid var(--app-secondary-action-border)",
            background: "var(--app-secondary-action-bg)",
            color: "var(--app-secondary-action-fg)",
            textDecoration: "none",
            fontSize: "13px",
            fontWeight: 600,
          }}
        >
          {ctaLabel}
        </Link>
      </div>
    </div>
  );
}

const radarLoadPanelStyle = {
  border: "1px solid var(--app-info-border)",
  borderRadius: "8px",
  background: "var(--app-info-bg)",
  color: "var(--app-info-fg)",
  padding: "14px",
  display: "grid",
  gap: "8px",
  fontSize: "14px",
  lineHeight: 1.6,
} as const;

const radarLoadStateStyle = (tone: "good" | "watch") =>
  ({
    border: `1px solid ${tone === "good" ? "var(--app-success-border)" : "var(--app-warning-border)"}`,
    borderRadius: "8px",
    background: tone === "good" ? "var(--app-success-bg)" : "var(--app-warning-bg)",
    color: tone === "good" ? "var(--app-success-fg)" : "var(--app-warning-fg)",
    padding: "12px 14px",
    display: "grid",
    gap: "5px",
    fontSize: "13px",
    lineHeight: 1.6,
  }) as const;

const radarHandoffGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 220px), 1fr))",
  gap: "12px",
} as const;

const radarShellStyle = {
  paddingTop: "28px",
  color: "var(--app-page-fg)",
} as const;

const radarHeroStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 420px), 1fr))",
  gap: "18px",
  alignItems: "stretch",
  marginBottom: "16px",
} as const;

const eyebrowStyle = {
  color: "var(--app-text-subtle)",
  fontSize: "12px",
  fontWeight: 760,
  textTransform: "uppercase" as const,
  letterSpacing: "0",
} as const;

const radarHeroTitleStyle = {
  margin: "10px 0 0",
  color: "var(--app-text-strong)",
  fontSize: "38px",
  fontWeight: 780,
  lineHeight: 1.08,
  maxWidth: "820px",
} as const;

const radarHeroDescriptionStyle = {
  margin: "14px 0 0",
  color: "var(--app-text-muted)",
  fontSize: "16px",
  lineHeight: 1.62,
  maxWidth: "820px",
} as const;

const quickActionRowStyle = {
  display: "flex",
  gap: "9px",
  flexWrap: "wrap" as const,
  marginTop: "20px",
} as const;

const quickActionStyle = {
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

const radarHeroPanelStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-bg)",
  padding: "16px",
  boxShadow: "var(--app-surface-shadow)",
} as const;

const summaryHeaderStyle = {
  display: "inline-flex",
  alignItems: "center",
  gap: "8px",
  color: "var(--app-text-strong)",
  fontSize: "14px",
  fontWeight: 760,
} as const;

const summaryMetricGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
  gap: "10px",
  marginTop: "14px",
} as const;

const summaryMetricStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  padding: "13px",
  minWidth: 0,
} as const;

const summaryMetricValueStyle = {
  color: "var(--app-text-strong)",
  fontSize: "18px",
  fontWeight: 780,
  lineHeight: 1.2,
  overflowWrap: "anywhere" as const,
} as const;

const summaryMetricLabelStyle = {
  marginTop: "7px",
  color: "var(--app-text-subtle)",
  fontSize: "12px",
  fontWeight: 720,
} as const;

const radarSectionStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  padding: "18px",
  background: "var(--app-surface-bg)",
  boxShadow: "var(--app-surface-shadow)",
} as const;

const radarSectionHeaderStyle = {
  marginBottom: "14px",
} as const;

const radarSectionTitleStyle = {
  margin: "6px 0 0",
  color: "var(--app-text-strong)",
  fontSize: "22px",
  fontWeight: 760,
  lineHeight: 1.2,
} as const;

const momentumColumnStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  padding: "14px",
  background: "var(--app-surface-muted-bg)",
} as const;

const momentumTitleStyle = {
  color: "var(--app-text-strong)",
  fontSize: "15px",
  fontWeight: 760,
  marginBottom: "12px",
} as const;

const momentumItemStyle = {
  padding: "10px 12px",
  borderRadius: "8px",
  background: "var(--app-surface-bg)",
  border: "1px solid var(--app-surface-border)",
} as const;

const infoBadgeStyle = {
  display: "inline-flex",
  alignItems: "center",
  padding: "4px 9px",
  borderRadius: "999px",
  border: "1px solid var(--app-chip-border)",
  background: "var(--app-chip-bg)",
  fontSize: "12px",
  color: "var(--app-chip-fg)",
  fontWeight: 650,
} as const;
