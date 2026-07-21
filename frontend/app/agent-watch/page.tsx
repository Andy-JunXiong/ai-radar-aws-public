"use client";

import type { CSSProperties } from "react";
import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import AppContainer from "@/components/AppContainer";
import PageHeader from "@/components/PageHeader";
import SectionCard from "@/components/SectionCard";
import { apiUrl } from "@/lib/api";
import { cleanDisplayList, cleanDisplayText } from "@/lib/displayText";

type AgentWatchSignal = {
  title?: string;
  summary?: string;
  url?: string;
  source?: string;
  source_type?: string;
  published_at?: string;
  agent_subtopic?: string;
  agent_watch_score?: number | string | null;
  repo_stars?: number | string | null;
  language?: string;
  tracking?: {
    status?: string | null;
    first_seen?: string | null;
    first_seen_at?: string | null;
    last_seen?: string | null;
    last_seen_at?: string | null;
    days_observed?: number | null;
    seen_days?: number | null;
    observations?: number | null;
    latest_score?: number | null;
    current_score?: number | null;
    previous_score?: number | null;
    score_change?: number | null;
    score_delta_1d?: number | null;
    metric_delta_1d?: number | null;
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
  metadata?: {
    repo_stars?: number | string | null;
    language?: string;
    hn_points?: number | string | null;
    hn_comments?: number | string | null;
    matched_keywords?: string[];
  };
};

type AgentWatchPayload = {
  generated_at?: string;
  source?: string;
  count?: number;
  signals?: AgentWatchSignal[];
  summary?: {
    signal_count?: number;
    top_signal_count?: number;
    runtime_sources?: string[];
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
};

function scoreLabel(value: number | string | null | undefined) {
  if (value === null || value === undefined || value === "") return "N/A";
  return String(value);
}

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

function deltaLabel(value?: number | null) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "N/A";
  }
  const numeric = Number(value);
  if (numeric === 0) return "0";
  return `${numeric > 0 ? "+" : ""}${numeric.toFixed(1)}`;
}

function getTrackingState(tracking?: AgentWatchSignal["tracking"]) {
  if (!tracking) return "untracked";
  const status = cleanDisplayText(tracking.status).toLowerCase();
  if (["new", "heating", "sustained", "cooling", "dropped", "revived"].includes(status)) {
    return status;
  }
  const observations = Number(tracking.observations ?? 0);
  const delta = Number(tracking.score_change ?? 0);
  if (observations <= 1) return "new";
  if (delta >= 5) return "heating";
  if (delta <= -5) return "cooling";
  return "sustained";
}

function trackingStateLabel(state: string) {
  const labels: Record<string, string> = {
    new: "New",
    heating: "Heating",
    sustained: "Sustained",
    cooling: "Cooling",
    dropped: "Dropped",
    revived: "Revived",
    untracked: "Untracked",
  };
  return labels[state] || state;
}

function trackingDeltaValue(tracking?: AgentWatchSignal["tracking"]) {
  if (!tracking) return null;
  const value = tracking.metric_delta_1d ?? tracking.score_delta_1d ?? tracking.score_change;
  if (value === null || value === undefined || Number.isNaN(Number(value))) return null;
  return Number(value);
}

function buildWhyTrackNow(item: AgentWatchSignal, trackingState: string) {
  const projectFit = cleanDisplayText(item.profile?.project_fit);
  const whyItMatters = cleanDisplayText(item.profile?.why_it_matters);
  const title = cleanDisplayText(item.title) || "This repo";

  if (trackingState === "new") {
    return `${title} is newly tracked and needs an initial read before it disappears into the general signal flow.`;
  }
  if (trackingState === "heating") {
    return `${title} is rising across recent observations, so it is worth checking whether the momentum is durable.`;
  }
  if (trackingState === "revived") {
    return `${title} has reappeared after a quiet period, so it is worth checking whether the renewed signal is meaningful.`;
  }
  if (projectFit) {
    return projectFit;
  }
  if (whyItMatters) {
    return whyItMatters;
  }
  if (trackingState === "sustained") {
    return `${title} is staying active over time, which makes it worth monitoring for sustained relevance.`;
  }
  if (trackingState === "cooling") {
    return `${title} is cooling, so this is mainly worth checking to see whether the earlier momentum was real or temporary.`;
  }
  if (trackingState === "dropped") {
    return `${title} has dropped out of the latest active set; keep it visible only if prior momentum still matters.`;
  }
  return `${title} is on the watchlist, but it still needs a stronger reason-to-track summary.`;
}

function buildWhatChanged(item: AgentWatchSignal, trackingState: string) {
  const delta = deltaLabel(trackingDeltaValue(item.tracking));
  const observations = Number(item.tracking?.observations ?? 0);
  if (trackingState === "new") {
    return "First observation in tracking history.";
  }
  if (trackingState === "heating") {
    return `Recent tracking delta moved to ${delta} across ${observations || "recent"} observations.`;
  }
  if (trackingState === "cooling") {
    return `Recent score delta cooled to ${delta} after prior tracking activity.`;
  }
  if (trackingState === "sustained") {
    return `Tracking is sustained with ${observations || 0} observations and no large recent score swing.`;
  }
  if (trackingState === "revived") {
    return `The repo re-entered the active watch set after being absent from recent observations.`;
  }
  if (trackingState === "dropped") {
    return `The repo is absent from the latest active watch set after previous tracking.`;
  }
  return "No meaningful tracking change is available yet.";
}

export default function AgentWatchPage() {
  const [payload, setPayload] = useState<AgentWatchPayload | null>(null);
  const [loadError, setLoadError] = useState("");
  const [actionMessage, setActionMessage] = useState("");
  const [sourceFilter, setSourceFilter] = useState("all");
  const [subtopicFilter, setSubtopicFilter] = useState("all");
  const [profileFilter, setProfileFilter] = useState("all");
  const [trackingFilter, setTrackingFilter] = useState("all");
  const [stateFilter, setStateFilter] = useState("all");
  const [searchTerm, setSearchTerm] = useState("");
  const [sortMode, setSortMode] = useState("score");
  const [expandedUseCases, setExpandedUseCases] = useState<Record<string, boolean>>({});
  const [analyzingIds, setAnalyzingIds] = useState<Record<string, boolean>>({});

  useEffect(() => {
    fetch(apiUrl("/radar/agent-watch"))
      .then((res) => res.json())
      .then((data) => {
        setPayload(data);
        setLoadError("");
      })
      .catch(() => {
        setLoadError("Failed to load agent watch. Please confirm the local backend is running.");
      });
  }, []);

  const signals = useMemo(() => {
    const raw = payload?.signals || [];
    return Array.isArray(raw) ? raw : [];
  }, [payload]);

  const sourceOptions = useMemo(
    () =>
      Array.from(
        new Set(signals.map((item) => cleanDisplayText(item.source)).filter(Boolean)),
      ).sort((a, b) => a.localeCompare(b)),
    [signals],
  );

  const subtopicOptions = useMemo(
    () =>
      Array.from(
        new Set(signals.map((item) => cleanDisplayText(item.agent_subtopic)).filter(Boolean)),
      ).sort((a, b) => a.localeCompare(b)),
    [signals],
  );

  const filteredSignals = useMemo(() => {
    const loweredSearch = searchTerm.trim().toLowerCase();
    const next = signals.filter((item) => {
      const source = cleanDisplayText(item.source);
      const subtopic = cleanDisplayText(item.agent_subtopic);
      const tracking = item.tracking;
      const trackingState = getTrackingState(tracking);
      const profileReady = Boolean(
        item.profile?.what_it_does || item.profile?.project_fit || item.profile?.why_it_matters,
      );
      const haystack = [
        cleanDisplayText(item.title),
        cleanDisplayText(item.summary),
        source,
        subtopic,
        cleanDisplayText(item.language),
        cleanDisplayText(item.metadata?.language),
        ...cleanDisplayList(item.metadata?.matched_keywords || []),
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();

      const matchesSource = sourceFilter === "all" || source === sourceFilter;
      const matchesSubtopic = subtopicFilter === "all" || subtopic === subtopicFilter;
      const matchesProfile =
        profileFilter === "all" ||
        (profileFilter === "ready" && profileReady) ||
        (profileFilter === "pending" && !profileReady);
      const matchesTracking =
        trackingFilter === "all" ||
        (trackingFilter === "active" && Boolean(tracking)) ||
        (trackingFilter === "untracked" && !tracking) ||
        (trackingFilter === "new" && trackingState === "new") ||
        (trackingFilter === "movers" && Boolean(tracking) && Math.abs(trackingDeltaValue(tracking) ?? 0) >= 5);
      const matchesState = stateFilter === "all" || trackingState === stateFilter;
      return (
        matchesSource &&
        matchesSubtopic &&
        matchesProfile &&
        matchesTracking &&
        matchesState &&
        (!loweredSearch || haystack.includes(loweredSearch))
      );
    });

    next.sort((a, b) => {
      const scoreA = Number(a.agent_watch_score ?? -1);
      const scoreB = Number(b.agent_watch_score ?? -1);
      const starsA = Number(a.metadata?.repo_stars ?? a.repo_stars ?? -1);
      const starsB = Number(b.metadata?.repo_stars ?? b.repo_stars ?? -1);
      const pointsA = Number(a.metadata?.hn_points ?? -1);
      const pointsB = Number(b.metadata?.hn_points ?? -1);
      const dateA = Date.parse(a.published_at || "") || 0;
      const dateB = Date.parse(b.published_at || "") || 0;
      const deltaA = Math.abs(Number(a.tracking?.score_change ?? -1));
      const deltaB = Math.abs(Number(b.tracking?.score_change ?? -1));
      const observedA = Number(a.tracking?.days_observed ?? -1);
      const observedB = Number(b.tracking?.days_observed ?? -1);

      if (sortMode === "recent") return dateB - dateA;
      if (sortMode === "delta") return deltaB - deltaA || scoreB - scoreA;
      if (sortMode === "observed") return observedB - observedA || scoreB - scoreA;
      if (sortMode === "stars") return starsB - starsA || scoreB - scoreA;
      if (sortMode === "discussion") return pointsB - pointsA || scoreB - scoreA;
      return scoreB - scoreA || starsB - starsA || dateB - dateA;
    });

    return next;
  }, [profileFilter, trackingFilter, stateFilter, searchTerm, signals, sortMode, sourceFilter, subtopicFilter]);

  const sourceBreakdown = useMemo(() => {
    const counts = new Map<string, number>();
    for (const item of signals) {
      const key = cleanDisplayText(item.source) || "unknown";
      counts.set(key, (counts.get(key) || 0) + 1);
    }
    return Array.from(counts.entries()).sort((a, b) => b[1] - a[1]);
  }, [signals]);

  const subtopicBreakdown = useMemo(() => {
    const counts = new Map<string, number>();
    for (const item of signals) {
      const key = cleanDisplayText(item.agent_subtopic) || "unclassified";
      counts.set(key, (counts.get(key) || 0) + 1);
    }
    return Array.from(counts.entries()).sort((a, b) => b[1] - a[1]);
  }, [signals]);

  const trackingStats = useMemo(() => {
    const tracked = signals.filter((item) => Boolean(item.tracking));
    const newTracked = tracked.filter((item) => getTrackingState(item.tracking) === "new");
    const movers = tracked.filter((item) => Math.abs(trackingDeltaValue(item.tracking) ?? 0) >= 5);
    const heating = tracked.filter((item) => getTrackingState(item.tracking) === "heating");
    const sustained = tracked.filter((item) => getTrackingState(item.tracking) === "sustained");
    const revived = tracked.filter((item) => getTrackingState(item.tracking) === "revived");
    return {
      tracked: tracked.length,
      newTracked: newTracked.length,
      movers: movers.length,
      heating: heating.length,
      sustained: sustained.length,
      revived: revived.length,
    };
  }, [signals]);

  const biggestMovers = useMemo(() => {
    return signals
      .filter((item) => Boolean(item.tracking))
      .sort(
        (a, b) =>
          Math.abs(trackingDeltaValue(b.tracking) ?? 0) -
          Math.abs(trackingDeltaValue(a.tracking) ?? 0),
      )
      .slice(0, 3);
  }, [signals]);

  if (!payload) {
    return (
      <AppContainer>
        <div style={{ color: "var(--app-text-subtle)", fontSize: "15px" }}>Loading agent watch...</div>
      </AppContainer>
    );
  }

  return (
    <AppContainer>
      <PageHeader
        title="Agent Watch"
        description="Track emerging agent frameworks, applications, and infrastructure across GitHub, Hacker News, and future sources."
      />

      {loadError ? <InlineMessage tone="error">{loadError}</InlineMessage> : null}
      {actionMessage ? <InlineMessage tone="success">{actionMessage}</InlineMessage> : null}

      <SectionCard title="Runtime Snapshot">
        <div style={infoGridStyle}>
          <InfoCard label="Signals" value={String(payload.count ?? signals.length)} />
          <InfoCard label="Summary signals" value={String(payload.summary?.signal_count ?? signals.length)} />
          <InfoCard label="Highlights" value={String(payload.summary?.top_signal_count ?? 0)} />
          <InfoCard
            label="Sources"
            value={cleanDisplayList(payload.summary?.runtime_sources || []).join(", ") || "N/A"}
          />
          <InfoCard label="Generated" value={cleanDisplayText(payload.generated_at) || "Unavailable"} />
        </div>
      </SectionCard>

      <SectionCard title="Knowledge Convergence Bridge">
        <div style={bridgePanelStyle}>
          <div style={bridgeTextStyle}>
            Agent Watch is the supply-side surface: it shows new tools, repos, frameworks, and infrastructure movement.
            Use Knowledge when this supply signal should be compared with demand-side friction before it becomes a
            Project Takeaway candidate.
          </div>
          <div style={bridgeStepGridStyle}>
            <div style={bridgeStepStyle}>
              <strong>Supply</strong>
              <span>Agent ecosystem movement, repo traction, and tool capability.</span>
            </div>
            <div style={bridgeStepStyle}>
              <strong>Demand</strong>
              <span>Friction Signals show pain, blocked workflows, and repeated user demand.</span>
            </div>
            <div style={bridgeStepStyle}>
              <strong>Review</strong>
              <span>Knowledge creates convergence briefs for human review; it does not turn supply movement into automatic action.</span>
            </div>
          </div>
          <Link href="/knowledge" style={surfacePrimaryButtonStyle}>
            Open Knowledge Convergence
          </Link>
        </div>
      </SectionCard>

      <SectionCard title="Coverage Snapshot">
        {signals.length ? (
          <div style={coverageGridStyle}>
            <BreakdownCard
              label="Source breakdown"
              items={sourceBreakdown}
              emptyLabel="No sources available yet."
            />
            <BreakdownCard
              label="Subtopic breakdown"
              items={subtopicBreakdown}
              emptyLabel="No subtopics available yet."
            />
          </div>
        ) : (
          <EmptyState>
            No Agent Watch signals are loaded yet. This usually means the local smoke test
            or the daily pipeline has not produced agent-watch output yet.
          </EmptyState>
        )}
      </SectionCard>

      <SectionCard title="Repo Tracking Snapshot">
        <div style={infoGridStyle}>
          <InfoCard label="Tracking active" value={String(trackingStats.tracked)} />
          <InfoCard label="Newly tracked" value={String(trackingStats.newTracked)} />
          <InfoCard label="Heating" value={String(trackingStats.heating)} />
          <InfoCard label="Sustained" value={String(trackingStats.sustained)} />
          <InfoCard label="Revived" value={String(trackingStats.revived)} />
          <InfoCard label="Big movers" value={String(trackingStats.movers)} />
        </div>

        {biggestMovers.length ? (
          <div style={{ display: "grid", gap: "10px", marginTop: "16px" }}>
            {biggestMovers.map((item, index) => (
              <Link
                key={`${item.url || item.title || "mover"}-${index}`}
                href={`/agent-watch/detail?entity_id=${encodeURIComponent(item.url || "")}`}
                style={trackingMoverLinkStyle}
              >
                <div>
                  <div style={{ color: "var(--app-text-strong)", fontWeight: 700 }}>
                    {cleanDisplayText(item.title) || "Untitled repo"}
                  </div>
                  <div style={{ color: "var(--app-text-subtle)", fontSize: "13px" }}>
                    {cleanDisplayText(item.source) || "unknown"} | delta {deltaLabel(trackingDeltaValue(item.tracking))}
                  </div>
                </div>
                <div style={{ color: "var(--app-text-strong)", fontWeight: 700 }}>Open detail</div>
              </Link>
            ))}
          </div>
        ) : (
          <div style={{ marginTop: "14px", color: "var(--app-text-subtle)", fontSize: "14px" }}>
            No tracked movers yet.
          </div>
        )}
      </SectionCard>

      <SectionCard title="Tracked Agent Signals" marginBottom="0">
        {signals.length ? (
          <div style={{ display: "grid", gap: "12px" }}>
            <div style={filterPanelStyle}>
              <label style={fieldLabelStyle}>
                <span style={fieldNameStyle}>Source</span>
                <select value={sourceFilter} onChange={(event) => setSourceFilter(event.target.value)} style={controlStyle}>
                  <option value="all">All sources</option>
                  {sourceOptions.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              </label>

              <label style={fieldLabelStyle}>
                <span style={fieldNameStyle}>Subtopic</span>
                <select value={subtopicFilter} onChange={(event) => setSubtopicFilter(event.target.value)} style={controlStyle}>
                  <option value="all">All subtopics</option>
                  {subtopicOptions.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              </label>

              <label style={fieldLabelStyle}>
                <span style={fieldNameStyle}>Profile</span>
                <select value={profileFilter} onChange={(event) => setProfileFilter(event.target.value)} style={controlStyle}>
                  <option value="all">All profiles</option>
                  <option value="ready">Profile ready</option>
                  <option value="pending">Profile pending</option>
                </select>
              </label>

              <label style={fieldLabelStyle}>
                <span style={fieldNameStyle}>Tracking</span>
                <select value={trackingFilter} onChange={(event) => setTrackingFilter(event.target.value)} style={controlStyle}>
                  <option value="all">All tracking</option>
                  <option value="active">Tracking active</option>
                  <option value="new">Newly tracked</option>
                  <option value="movers">Big movers</option>
                  <option value="untracked">Untracked</option>
                </select>
              </label>

              <label style={fieldLabelStyle}>
                <span style={fieldNameStyle}>State</span>
                <select value={stateFilter} onChange={(event) => setStateFilter(event.target.value)} style={controlStyle}>
                  <option value="all">All states</option>
                  <option value="new">New</option>
                  <option value="heating">Heating</option>
                  <option value="sustained">Sustained</option>
                  <option value="cooling">Cooling</option>
                  <option value="dropped">Dropped</option>
                  <option value="revived">Revived</option>
                </select>
              </label>

              <label style={fieldLabelStyle}>
                <span style={fieldNameStyle}>Sort</span>
                <select value={sortMode} onChange={(event) => setSortMode(event.target.value)} style={controlStyle}>
                  <option value="score">Agent watch score</option>
                  <option value="recent">Most recent</option>
                  <option value="delta">Largest score delta</option>
                  <option value="observed">Longest observed</option>
                  <option value="stars">Repo stars</option>
                  <option value="discussion">HN discussion</option>
                </select>
              </label>

              <label style={fieldLabelStyle}>
                <span style={fieldNameStyle}>Search</span>
                <input
                  value={searchTerm}
                  onChange={(event) => setSearchTerm(event.target.value)}
                  placeholder="Search title, summary, or keywords"
                  style={controlStyle}
                />
              </label>
            </div>

            <div style={{ color: "var(--app-text-subtle)", fontSize: "14px" }}>
              Showing {filteredSignals.length} of {signals.length} tracked agent signals.
            </div>

            {filteredSignals.map((item, index) => {
              const meta = item.metadata || {};
              const tracking = item.tracking;
              const trackingState = getTrackingState(tracking);
              const profile = item.profile;
              const title = cleanDisplayText(item.title) || "Untitled Agent Signal";
              const summary = cleanDisplayText(item.summary) || "No summary available.";
              const source = cleanDisplayText(item.source);
              const subtopic = cleanDisplayText(item.agent_subtopic);
              const language = cleanDisplayText(item.language) || cleanDisplayText(meta.language);
              const matchedKeywords = cleanDisplayList(meta.matched_keywords || []);
              const suggestedUseCases = cleanDisplayList(profile?.suggested_use_cases || []);
              const itemKey = `${item.url || title}-${index}`;
              const showAllUseCases = !!expandedUseCases[itemKey];
              const visibleUseCases = showAllUseCases ? suggestedUseCases : suggestedUseCases.slice(0, 2);
              const profileReady = Boolean(profile?.what_it_does || profile?.project_fit || profile?.why_it_matters);
              const analyzeLabel = profileReady ? "Re-analyze" : "Analyze Repo";
              const whyTrackNow = buildWhyTrackNow(item, trackingState);
              const whatChanged = buildWhatChanged(item, trackingState);
              const analysisMetaBits = [
                compactDateLabel(profile?.generated_at),
                cleanDisplayText(profile?.provider_used),
                cleanDisplayText(profile?.model_used),
              ].filter((value) => value && value !== "N/A");

              const metaBits: string[] = [];
              if (subtopic) metaBits.push(subtopic);
              if (language) metaBits.push(language);
              if (source) metaBits.push(source);
              if (meta.repo_stars !== null && meta.repo_stars !== undefined && meta.repo_stars !== "") {
                metaBits.push(`${meta.repo_stars} stars`);
              }
              if (meta.hn_points !== null && meta.hn_points !== undefined && meta.hn_points !== "") {
                metaBits.push(`${meta.hn_points} points`);
              }

              return (
                <div key={`${title}-${index}`} style={signalCardStyle}>
                  <div style={signalHeaderStyle}>
                    <div style={{ color: "var(--app-text-strong)", fontWeight: 700 }}>{title}</div>
                    <span style={scoreBadgeStyle}>Score {scoreLabel(item.agent_watch_score)}</span>
                  </div>

                  <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                    <span style={profileReady ? readyBadgeStyle : pendingBadgeStyle}>
                      {profileReady ? "LLM Profile Ready" : "Profile Pending"}
                    </span>
                    {tracking ? <span style={trackingBadgeStyle}>Tracking Active</span> : null}
                    <span style={trackingStateBadgeStyle(trackingState)}>
                      {trackingStateLabel(trackingState)}
                    </span>
                    {profileReady && analysisMetaBits.length ? (
                      <span style={analysisMetaBadgeStyle}>
                        {analysisMetaBits.join(" · ")}
                      </span>
                    ) : null}
                  </div>

                  {metaBits.length ? <div style={metaLineStyle}>{metaBits.join(" · ")}</div> : null}

                  <div style={{ color: "var(--app-text-muted)", lineHeight: 1.7 }}>{summary}</div>

                  <div style={trackingReadoutGridStyle}>
                    <ProfileBlurb label="Why track now" value={whyTrackNow} />
                    <ProfileBlurb label="What changed" value={whatChanged} />
                  </div>

                  {profile?.what_it_does || profile?.project_fit || profile?.why_it_matters ? (
                    <div style={profileGridStyle}>
                      {profile.what_it_does ? (
                        <ProfileBlurb label="What it does" value={cleanDisplayText(profile.what_it_does)} />
                      ) : null}
                      {profile.project_fit ? (
                        <ProfileBlurb label="Project fit" value={cleanDisplayText(profile.project_fit)} />
                      ) : null}
                      {profile.why_it_matters ? (
                        <ProfileBlurb label="Why it matters" value={cleanDisplayText(profile.why_it_matters)} />
                      ) : null}
                    </div>
                  ) : null}

                  {suggestedUseCases.length ? (
                    <div style={suggestedPanelStyle}>
                      <div style={smallSectionTitleStyle}>Suggested use cases</div>
                      <div style={{ display: "grid", gap: "6px" }}>
                        {visibleUseCases.map((useCase, useCaseIndex) => (
                          <div key={`${itemKey}-use-case-${useCaseIndex}`} style={{ color: "var(--app-text-muted)", lineHeight: 1.7 }}>
                            {useCase}
                          </div>
                        ))}
                      </div>
                      {suggestedUseCases.length > 2 ? (
                        <button
                          type="button"
                          onClick={() =>
                            setExpandedUseCases((prev) => ({
                              ...prev,
                              [itemKey]: !prev[itemKey],
                            }))
                          }
                          style={surfaceGhostButtonStyle}
                        >
                          {showAllUseCases ? "Show less" : "Show use cases"}
                        </button>
                      ) : null}
                    </div>
                  ) : null}

                  {tracking ? (
                    <div style={trackingGridStyle}>
                      <MiniMetric label="First seen" value={compactDateLabel(tracking.first_seen ?? tracking.first_seen_at)} />
                      <MiniMetric label="Last seen" value={compactDateLabel(tracking.last_seen ?? tracking.last_seen_at)} />
                      <MiniMetric
                        label="Days observed"
                        value={
                          tracking.days_observed != null
                            ? String(tracking.days_observed)
                            : tracking.seen_days != null
                              ? String(tracking.seen_days)
                              : "N/A"
                        }
                      />
                      <MiniMetric
                        label="Observations"
                        value={tracking.observations != null ? String(tracking.observations) : "N/A"}
                      />
                      <MiniMetric label="Latest score" value={scoreLabel(tracking.latest_score ?? tracking.current_score)} />
                      <MiniMetric label="Tracking delta" value={deltaLabel(trackingDeltaValue(tracking))} />
                    </div>
                  ) : null}

                  {matchedKeywords.length ? (
                    <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                      {matchedKeywords.map((keyword) => (
                        <span key={`${title}-${keyword}`} style={keywordStyle}>
                          {keyword}
                        </span>
                      ))}
                    </div>
                  ) : null}

                  {item.url ? (
                    <div style={{ display: "flex", gap: "14px", flexWrap: "wrap" }}>
                      <button
                        type="button"
                        onClick={async () => {
                          const entityId = item.url || "";
                          if (!entityId || analyzingIds[entityId]) return;
                          setAnalyzingIds((prev) => ({ ...prev, [entityId]: true }));
                          try {
                            const response = await fetch(
                              apiUrl(`/radar/agent-watch/analyze?entity_id=${encodeURIComponent(entityId)}`),
                            );
                            let data: { ok?: boolean; message?: string } | null = null;
                            try {
                              data = await response.json();
                            } catch {
                              data = null;
                            }
                            if (!response.ok || data?.ok === false) {
                              throw new Error(data?.message || `Failed to analyze repo (${response.status}).`);
                            }
                            const refreshed = await fetch(apiUrl("/radar/agent-watch"));
                            const refreshedData = await refreshed.json();
                            setPayload(refreshedData);
                            setActionMessage("Repo analysis completed.");
                          } catch (error) {
                            setActionMessage(error instanceof Error ? error.message : "Failed to analyze repo.");
                          } finally {
                            setAnalyzingIds((prev) => ({ ...prev, [entityId]: false }));
                          }
                        }}
                        style={surfacePrimaryButtonStyle}
                      >
                        {analyzingIds[item.url || ""] ? "Analyzing..." : analyzeLabel}
                      </button>
                      <Link href={`/agent-watch/detail?entity_id=${encodeURIComponent(item.url)}`} style={surfaceActionLinkStyle}>
                        View Details
                      </Link>
                      <a href={item.url} target="_blank" rel="noreferrer" style={surfaceActionLinkStyle}>
                        Open Source
                      </a>
                    </div>
                  ) : null}
                </div>
              );
            })}

            {!filteredSignals.length ? (
              <EmptyState>No agent watch signals match the current filters.</EmptyState>
            ) : null}
          </div>
        ) : (
          <div style={{ color: "var(--app-text-subtle)" }}>
            No agent watch signals available yet. Run the smoke test or daily pipeline to
            populate this view.
          </div>
        )}
      </SectionCard>
    </AppContainer>
  );
}

function InlineMessage({
  tone,
  children,
}: {
  tone: "success" | "error";
  children: React.ReactNode;
}) {
  const isSuccess = tone === "success";
  return (
    <div
      style={{
        marginBottom: "16px",
        padding: "12px 14px",
        borderRadius: "12px",
        border: `1px solid ${isSuccess ? "var(--app-success-border)" : "var(--app-danger-border)"}`,
        background: isSuccess ? "var(--app-success-bg)" : "var(--app-danger-bg)",
        color: isSuccess ? "var(--app-success-fg)" : "var(--app-danger-fg)",
        fontWeight: 600,
      }}
    >
      {children}
    </div>
  );
}

function ProfileBlurb({ label, value }: { label: string; value: string }) {
  return (
    <div style={profileBlurbStyle}>
      <div style={profileBlurbLabelStyle}>{label}</div>
      <div style={{ color: "var(--app-text-muted)", lineHeight: 1.7 }}>{value}</div>
    </div>
  );
}

function MiniMetric({ label, value }: { label: string; value: string }) {
  return (
    <div style={miniMetricStyle}>
      <div style={miniMetricLabelStyle}>{label}</div>
      <div style={{ color: "var(--app-text-strong)", fontWeight: 700 }}>{value}</div>
    </div>
  );
}

function InfoCard({ label, value }: { label: string; value: string }) {
  return (
    <div style={infoCardStyle}>
      <div style={{ color: "var(--app-text-subtle)", fontSize: "13px", marginBottom: "6px" }}>{label}</div>
      <div style={{ color: "var(--app-text-strong)", fontWeight: 700, lineHeight: 1.5 }}>{value}</div>
    </div>
  );
}

function BreakdownCard({
  label,
  items,
  emptyLabel,
}: {
  label: string;
  items: [string, number][];
  emptyLabel: string;
}) {
  return (
    <div style={breakdownCardStyle}>
      <div style={{ color: "var(--app-text-strong)", fontWeight: 700 }}>{label}</div>
      {items.length ? (
        <div style={{ display: "grid", gap: "8px" }}>
          {items.map(([name, count]) => (
            <div key={`${label}-${name}`} style={breakdownRowStyle}>
              <span>{name}</span>
              <span style={{ color: "var(--app-text-strong)", fontWeight: 600 }}>{count}</span>
            </div>
          ))}
        </div>
      ) : (
        <div style={{ color: "var(--app-text-subtle)" }}>{emptyLabel}</div>
      )}
    </div>
  );
}

function EmptyState({ children }: { children: React.ReactNode }) {
  return (
    <div style={emptyStateStyle}>
      {children}
    </div>
  );
}

const infoGridStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
  gap: "12px",
};

const coverageGridStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
  gap: "12px",
};

const bridgePanelStyle: CSSProperties = {
  display: "grid",
  gap: "12px",
};

const bridgeTextStyle: CSSProperties = {
  color: "var(--app-text-muted)",
  fontSize: "14px",
  lineHeight: 1.65,
};

const bridgeStepGridStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))",
  gap: "10px",
};

const bridgeStepStyle: CSSProperties = {
  border: "1px solid var(--app-info-border)",
  borderRadius: "12px",
  background: "var(--app-surface-muted-bg)",
  padding: "12px",
  display: "grid",
  gap: "6px",
  color: "var(--app-text-muted)",
  lineHeight: 1.45,
};

const filterPanelStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
  gap: "12px",
  padding: "14px",
  borderRadius: "14px",
  border: "1px solid var(--app-surface-border)",
  background: "var(--app-surface-bg)",
};

const fieldLabelStyle: CSSProperties = {
  display: "grid",
  gap: "6px",
};

const fieldNameStyle: CSSProperties = {
  color: "var(--app-text-subtle)",
  fontSize: "13px",
};

const controlStyle: CSSProperties = {
  width: "100%",
  border: "1px solid var(--app-secondary-action-border)",
  borderRadius: "10px",
  padding: "10px 12px",
  fontSize: "14px",
  color: "var(--app-text-strong)",
  background: "var(--app-surface-bg)",
};

const signalCardStyle: CSSProperties = {
  padding: "16px",
  borderRadius: "14px",
  border: "1px solid var(--app-surface-border)",
  background: "var(--app-surface-muted-bg)",
  display: "grid",
  gap: "8px",
};

const signalHeaderStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  gap: "12px",
  flexWrap: "wrap",
};

const scoreBadgeStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  padding: "4px 10px",
  borderRadius: "999px",
  background: "var(--app-info-bg)",
  border: "1px solid var(--app-info-border)",
  color: "var(--app-info-fg)",
  fontSize: "12px",
  fontWeight: 600,
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
    heating: { border: "var(--app-success-border)", background: "var(--app-success-bg)", color: "var(--app-success-fg)" },
    sustained: { border: "var(--app-surface-border)", background: "var(--app-surface-muted-bg)", color: "var(--app-text-muted)" },
    cooling: { border: "var(--app-warning-border)", background: "var(--app-warning-bg)", color: "var(--app-warning-fg)" },
    dropped: { border: "var(--app-danger-border)", background: "var(--app-danger-bg)", color: "var(--app-danger-fg)" },
    revived: { border: "var(--app-info-border)", background: "var(--app-info-bg)", color: "var(--app-info-fg)" },
    untracked: { border: "var(--app-surface-border)", background: "var(--app-surface-muted-bg)", color: "var(--app-text-subtle)" },
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
  background: "var(--app-chip-bg)",
  border: "1px solid var(--app-warning-border)",
  color: "var(--app-warning-fg)",
  fontSize: "12px",
  fontWeight: 700,
};

const metaLineStyle: CSSProperties = {
  color: "var(--app-text-subtle)",
  fontSize: "13px",
};

const profileGridStyle: CSSProperties = {
  display: "grid",
  gap: "10px",
  gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
};

const trackingReadoutGridStyle: CSSProperties = {
  display: "grid",
  gap: "10px",
  gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
};

const profileBlurbStyle: CSSProperties = {
  border: "1px solid var(--app-info-border)",
  borderRadius: "12px",
  padding: "12px 14px",
  background: "var(--app-surface-muted-bg)",
  display: "grid",
  gap: "6px",
};

const profileBlurbLabelStyle: CSSProperties = {
  color: "var(--app-info-fg)",
  fontSize: "12px",
  fontWeight: 700,
  textTransform: "uppercase",
};

const suggestedPanelStyle: CSSProperties = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "12px",
  padding: "12px 14px",
  background: "var(--app-surface-bg)",
  display: "grid",
  gap: "8px",
};

const smallSectionTitleStyle: CSSProperties = {
  color: "var(--app-text-subtle)",
  fontSize: "12px",
  textTransform: "uppercase",
  fontWeight: 700,
};

const trackingGridStyle: CSSProperties = {
  display: "grid",
  gap: "10px",
  gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
};

const miniMetricStyle: CSSProperties = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "12px",
  padding: "10px 12px",
  background: "var(--app-surface-bg)",
  display: "grid",
  gap: "4px",
};

const miniMetricLabelStyle: CSSProperties = {
  color: "var(--app-text-subtle)",
  fontSize: "12px",
  textTransform: "uppercase",
};

const keywordStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  padding: "4px 10px",
  borderRadius: "999px",
  background: "var(--app-surface-bg)",
  border: "1px solid var(--app-surface-border)",
  color: "var(--app-text-muted)",
  fontSize: "12px",
};

const surfaceActionLinkStyle: CSSProperties = {
  padding: "7px 12px",
  borderRadius: "8px",
  border: "1px solid var(--app-secondary-action-border)",
  background: "var(--app-secondary-action-bg)",
  color: "var(--app-secondary-action-fg)",
  textDecoration: "none",
  display: "inline-flex",
  alignItems: "center",
  fontSize: "13px",
  fontWeight: 600,
};

const trackingMoverLinkStyle: CSSProperties = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "12px",
  padding: "12px 14px",
  background: "var(--app-surface-bg)",
  textDecoration: "none",
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  gap: "12px",
  flexWrap: "wrap",
};

const surfacePrimaryButtonStyle: CSSProperties = {
  padding: "7px 12px",
  borderRadius: "8px",
  border: "1px solid var(--app-primary-action-bg)",
  background: "var(--app-primary-action-bg)",
  color: "var(--app-primary-action-fg)",
  cursor: "pointer",
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  fontSize: "13px",
  fontWeight: 700,
};

const surfaceGhostButtonStyle: CSSProperties = {
  padding: "7px 12px",
  borderRadius: "8px",
  border: "1px solid var(--app-secondary-action-border)",
  background: "var(--app-secondary-action-bg)",
  color: "var(--app-secondary-action-fg)",
  cursor: "pointer",
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  fontSize: "13px",
  fontWeight: 600,
  width: "fit-content",
};

const infoCardStyle: CSSProperties = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "14px",
  padding: "14px 16px",
  background: "var(--app-surface-bg)",
};

const breakdownCardStyle: CSSProperties = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "14px",
  padding: "14px 16px",
  background: "var(--app-surface-bg)",
  display: "grid",
  gap: "10px",
};

const breakdownRowStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  gap: "12px",
  color: "var(--app-text-muted)",
};

const emptyStateStyle: CSSProperties = {
  color: "var(--app-text-subtle)",
  lineHeight: 1.7,
  border: "1px dashed var(--app-secondary-action-border)",
  borderRadius: "14px",
  padding: "18px",
  background: "var(--app-surface-muted-bg)",
};
