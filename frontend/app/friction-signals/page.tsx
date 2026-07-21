"use client";

import type { CSSProperties } from "react";
import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import AppContainer from "@/components/AppContainer";
import PageHeader from "@/components/PageHeader";
import SectionCard from "@/components/SectionCard";
import { apiUrl } from "@/lib/api";
import { adminFetch } from "@/lib/adminAuth";
import { cleanDisplayList, cleanDisplayText } from "@/lib/displayText";

type FrictionProfile = {
  problem_summary?: string;
  why_this_matters?: string;
  who_is_affected?: string;
  product_opportunity?: string;
  suggested_response?: string[];
  confidence?: string;
  provider_used?: string;
  model_used?: string;
};

type FrictionSignal = {
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
    current_metric?: number | null;
    metric_name?: string | null;
    pain_cluster_key?: string | null;
    missed_days?: number | null;
  };
  profile?: FrictionProfile;
};

type FrictionPayload = {
  generated_at?: string;
  source?: string;
  count?: number;
  signals?: FrictionSignal[];
  summary?: {
    signal_count?: number;
    top_signal_count?: number;
    runtime_sources?: string[];
    highlights?: FrictionSignal[];
  };
};

type TranslationState = {
  loading?: boolean;
  translatedText?: string;
  translatedFields?: {
    title?: string;
    summary?: string;
    friction_subtopic?: string;
    profile?: {
      why_this_matters?: string;
      product_opportunity?: string;
    };
  };
  showChinese?: boolean;
  error?: string;
};

const FRICTION_TRANSLATION_STORAGE_KEY = "frictionSignalTranslations";
const FRICTION_STARRED_STORAGE_KEY = "frictionSignalStarred";

function getFrictionEntityId(item: FrictionSignal, index: number) {
  return item.url || `${item.title || "friction"}-${index}`;
}

function readStoredTranslations(): Record<string, TranslationState> {
  if (typeof window === "undefined") return {};
  try {
    const raw = window.sessionStorage.getItem(FRICTION_TRANSLATION_STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function readStoredStarred(): Record<string, boolean> {
  if (typeof window === "undefined") return {};
  try {
    const raw = window.localStorage.getItem(FRICTION_STARRED_STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function writeStoredStarred(value: Record<string, boolean>) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(FRICTION_STARRED_STORAGE_KEY, JSON.stringify(value));
  } catch {
    // Ignore storage errors and keep UI usable.
  }
}

function writeStoredTranslations(value: Record<string, TranslationState>) {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.setItem(FRICTION_TRANSLATION_STORAGE_KEY, JSON.stringify(value));
  } catch {
    // Ignore storage errors and keep UI usable.
  }
}

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

function getTrackingState(tracking?: FrictionSignal["tracking"]) {
  if (!tracking) return "untracked";
  const status = cleanDisplayText(tracking.status).toLowerCase();
  if (["new", "heating", "sustained", "cooling", "dropped", "revived"].includes(status)) {
    return status;
  }
  const observations = Number(tracking.observations ?? 0);
  const delta = Number(tracking.metric_delta_1d ?? tracking.score_delta_1d ?? tracking.score_change ?? 0);
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

function trackingDeltaValue(tracking?: FrictionSignal["tracking"]) {
  if (!tracking) return null;
  const value = tracking.metric_delta_1d ?? tracking.score_delta_1d ?? tracking.score_change;
  if (value === null || value === undefined || Number.isNaN(Number(value))) return null;
  return Number(value);
}

function buildWhyTrackNow(item: FrictionSignal, trackingState: string) {
  const productOpportunity = cleanDisplayText(item.profile?.product_opportunity);
  const whyThisMatters = cleanDisplayText(item.profile?.why_this_matters);
  const title = cleanDisplayText(item.title) || "This friction signal";

  if (trackingState === "new") {
    return `${title} is newly tracked demand-side pain and needs a first read before it becomes background noise.`;
  }
  if (trackingState === "heating") {
    return `${title} is gaining pressure across recent observations, so it is worth checking whether the pain is durable.`;
  }
  if (trackingState === "revived") {
    return `${title} has reappeared after a quiet period, so the renewed demand may deserve another look.`;
  }
  if (productOpportunity) {
    return productOpportunity;
  }
  if (whyThisMatters) {
    return whyThisMatters;
  }
  if (trackingState === "sustained") {
    return `${title} is staying visible over time, which makes it worth monitoring for recurring product demand.`;
  }
  if (trackingState === "cooling") {
    return `${title} is cooling, so check whether the earlier demand pressure has faded.`;
  }
  if (trackingState === "dropped") {
    return `${title} has dropped out of the latest active set; keep it visible only if prior demand still matters.`;
  }
  return `${title} is visible, but it still needs a stronger reason-to-track summary.`;
}

function buildWhatChanged(item: FrictionSignal, trackingState: string) {
  const delta = deltaLabel(trackingDeltaValue(item.tracking));
  const observations = Number(item.tracking?.observations ?? item.tracking?.days_observed ?? item.tracking?.seen_days ?? 0);
  if (trackingState === "new") {
    return "First observation in friction tracking history.";
  }
  if (trackingState === "heating") {
    return `Recent friction delta moved to ${delta} across ${observations || "recent"} observations.`;
  }
  if (trackingState === "cooling") {
    return `Recent friction cooled to ${delta} after prior tracking activity.`;
  }
  if (trackingState === "sustained") {
    return `Friction is sustained with ${observations || 0} observations and no large recent swing.`;
  }
  if (trackingState === "revived") {
    return "The friction signal re-entered the active set after being absent from recent observations.";
  }
  if (trackingState === "dropped") {
    return "The friction signal is absent from the latest active set after previous tracking.";
  }
  return "No meaningful tracking change is available yet.";
}

export default function FrictionSignalsPage() {
  const [payload, setPayload] = useState<FrictionPayload | null>(null);
  const [loadError, setLoadError] = useState("");
  const [sourceFilter, setSourceFilter] = useState("all");
  const [subtopicFilter, setSubtopicFilter] = useState("all");
  const [insightFilter, setInsightFilter] = useState("all");
  const [trackingFilter, setTrackingFilter] = useState("all");
  const [stateFilter, setStateFilter] = useState("all");
  const [starredFilter, setStarredFilter] = useState("all");
  const [searchTerm, setSearchTerm] = useState("");
  const [sortMode, setSortMode] = useState("score");
  const [translations, setTranslations] = useState<Record<string, TranslationState>>({});
  const [starred, setStarred] = useState<Record<string, boolean>>({});
  const [actionMessage, setActionMessage] = useState("");

  useEffect(() => {
    setTranslations(readStoredTranslations());
    setStarred(readStoredStarred());
    adminFetch(apiUrl("/radar/friction-signals"))
      .then((res) => res.json())
      .then((data) => {
        setPayload(data);
        setLoadError("");
      })
      .catch(() => {
        setLoadError("Failed to load friction signals. Please confirm the local backend is running.");
      });
  }, []);

  const summary = payload?.summary;

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
        new Set(signals.map((item) => cleanDisplayText(item.friction_subtopic)).filter(Boolean)),
      ).sort((a, b) => a.localeCompare(b)),
    [signals],
  );

  const filteredSignals = useMemo(() => {
    const loweredSearch = searchTerm.trim().toLowerCase();
    const next = signals.filter((item, index) => {
      const entityId = getFrictionEntityId(item, index);
      const source = cleanDisplayText(item.source);
      const subtopic = cleanDisplayText(item.friction_subtopic);
      const tracking = item.tracking;
      const trackingState = getTrackingState(tracking);
      const isStarred = Boolean(starred[entityId]);
      const insightReady = Boolean(
        item.profile?.problem_summary ||
          item.profile?.why_this_matters ||
          item.profile?.product_opportunity,
      );
      const matchesSource = sourceFilter === "all" || source === sourceFilter;
      const matchesSubtopic = subtopicFilter === "all" || subtopic === subtopicFilter;
      const matchesStarred =
        starredFilter === "all" ||
        (starredFilter === "starred" && isStarred) ||
        (starredFilter === "unstarred" && !isStarred);
      const matchesInsight =
        insightFilter === "all" ||
        (insightFilter === "ready" && insightReady) ||
        (insightFilter === "pending" && !insightReady);
      const matchesTracking =
        trackingFilter === "all" ||
        (trackingFilter === "active" && Boolean(tracking)) ||
        (trackingFilter === "untracked" && !tracking) ||
        (trackingFilter === "new" && trackingState === "new") ||
        (trackingFilter === "movers" && Boolean(tracking) && Math.abs(trackingDeltaValue(tracking) ?? 0) >= 5);
      const matchesState = stateFilter === "all" || trackingState === stateFilter;
      const haystack = [
        item.title,
        item.summary,
        item.source,
        item.friction_subtopic,
        item.repo_name,
        item.profile?.problem_summary,
        item.profile?.why_this_matters,
        item.profile?.product_opportunity,
        trackingState,
        ...(item.matched_keywords || []),
      ]
        .map((value) => cleanDisplayText(value))
        .filter(Boolean)
        .join(" ")
        .toLowerCase();

      return (
        matchesSource &&
        matchesSubtopic &&
        matchesStarred &&
        matchesInsight &&
        matchesTracking &&
        matchesState &&
        (!loweredSearch || haystack.includes(loweredSearch))
      );
    });

    next.sort((a, b) => {
      const scoreA = Number(a.friction_score ?? -1);
      const scoreB = Number(b.friction_score ?? -1);
      const painA = Number(a.pain_severity_score ?? -1);
      const painB = Number(b.pain_severity_score ?? -1);
      const relevanceA = Number(a.ecosystem_relevance_score ?? -1);
      const relevanceB = Number(b.ecosystem_relevance_score ?? -1);
      const dateA = Date.parse(a.published_at || "") || 0;
      const dateB = Date.parse(b.published_at || "") || 0;
      const deltaA = Math.abs(trackingDeltaValue(a.tracking) ?? -1);
      const deltaB = Math.abs(trackingDeltaValue(b.tracking) ?? -1);
      const observedA = Number(a.tracking?.days_observed ?? a.tracking?.seen_days ?? -1);
      const observedB = Number(b.tracking?.days_observed ?? b.tracking?.seen_days ?? -1);

      if (sortMode === "recent") return dateB - dateA;
      if (sortMode === "delta") return deltaB - deltaA || scoreB - scoreA;
      if (sortMode === "observed") return observedB - observedA || scoreB - scoreA;
      if (sortMode === "pain") return painB - painA || scoreB - scoreA;
      if (sortMode === "relevance") return relevanceB - relevanceA || scoreB - scoreA;
      return scoreB - scoreA || painB - painA || dateB - dateA;
    });

    return next;
  }, [
    signals,
    insightFilter,
    searchTerm,
    sortMode,
    sourceFilter,
    starred,
    starredFilter,
    stateFilter,
    subtopicFilter,
    trackingFilter,
  ]);

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
      const key = cleanDisplayText(item.friction_subtopic) || "general_friction";
      counts.set(key, (counts.get(key) || 0) + 1);
    }
    return Array.from(counts.entries()).sort((a, b) => b[1] - a[1]);
  }, [signals]);

  const starredCount = useMemo(
    () => signals.filter((item, index) => starred[getFrictionEntityId(item, index)]).length,
    [signals, starred],
  );

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

  async function translateItem(item: FrictionSignal, index: number) {
    const entityId = item.url || `${item.title || "friction"}-${index}`;
    if (!item.url) {
      setActionMessage("This item does not have enough text to translate yet.");
      return;
    }

    setTranslations((current) => {
      const next = {
        ...current,
        [entityId]: {
          loading: true,
          translatedText: current[entityId]?.translatedText || "",
          translatedFields: current[entityId]?.translatedFields,
          showChinese: current[entityId]?.showChinese,
          error: "",
        },
      };
      writeStoredTranslations(next);
      return next;
    });

    try {
      const response = await adminFetch(
        apiUrl(`/radar/friction-signals/translate?entity_id=${encodeURIComponent(item.url)}`),
      );

      const data = await response.json();
      if (!response.ok) {
        throw new Error(cleanDisplayText(data?.detail || data?.message || data?.translated_text) || "Translation failed.");
      }

      const translatedText = cleanDisplayText(data?.translated_text);
      if (!translatedText) {
        throw new Error("Translation returned an empty result.");
      }

      setTranslations((current) => {
        const next = {
          ...current,
          [entityId]: {
            loading: false,
            translatedText,
            translatedFields: data?.translated_fields || current[entityId]?.translatedFields,
            showChinese: true,
            error: "",
          },
        };
        writeStoredTranslations(next);
        return next;
      });
      setActionMessage("Chinese translation generated.");
    } catch (error) {
      const message =
        error instanceof Error && cleanDisplayText(error.message)
          ? cleanDisplayText(error.message)
          : "Translation failed.";
      setTranslations((current) => {
        const next = {
          ...current,
          [entityId]: {
            loading: false,
            translatedText: current[entityId]?.translatedText || "",
            translatedFields: current[entityId]?.translatedFields,
            showChinese: current[entityId]?.showChinese,
            error: message,
          },
        };
        writeStoredTranslations(next);
        return next;
      });
      setActionMessage(message);
    }
  }

  function showEnglish(entityId: string) {
    setTranslations((current) => {
      const next = {
        ...current,
        [entityId]: {
          ...current[entityId],
          translatedText: "",
          showChinese: false,
          error: "",
        },
      };
      writeStoredTranslations(next);
      return next;
    });
    setActionMessage("English content restored.");
  }

  function enableChinese(entityId: string) {
    setTranslations((current) => {
      const next = {
        ...current,
        [entityId]: {
          ...current[entityId],
          showChinese: true,
          error: "",
        },
      };
      writeStoredTranslations(next);
      return next;
    });
    setActionMessage("Chinese translation restored.");
  }

  function toggleStar(entityId: string) {
    setStarred((current) => {
      const nextValue = !current[entityId];
      const next = {
        ...current,
        [entityId]: nextValue,
      };
      writeStoredStarred(next);
      setActionMessage(nextValue ? "Added to starred friction signals." : "Removed from starred friction signals.");
      return next;
    });
  }

  if (!payload) {
    return (
      <AppContainer>
        <div style={{ color: "var(--app-text-subtle)", fontSize: "15px" }}>Loading friction signals...</div>
      </AppContainer>
    );
  }

  return (
    <AppContainer>
      <PageHeader
        title="Friction Signals"
        description="Track where the AI ecosystem is failing, frustrating users, or showing repeated implementation pain."
      />

      {loadError ? <div style={emptyPanelStyle}>{loadError}</div> : null}
      {actionMessage ? <div style={messagePanelStyle}>{actionMessage}</div> : null}

      <SectionCard title="Runtime Snapshot">
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
            gap: "12px",
          }}
        >
          <InfoCard label="Signals" value={String(summary?.signal_count ?? payload?.count ?? 0)} />
          <InfoCard label="Highlights" value={String(summary?.top_signal_count ?? 0)} />
          <InfoCard label="Visible list" value={String(signals.length)} />
          <InfoCard label="Starred" value={String(starredCount)} />
          <InfoCard label="Sources" value={(summary?.runtime_sources || []).join(", ") || "N/A"} />
          <InfoCard
            label="Coverage"
            value={summary?.signal_count ? "Daily pipeline active" : "No friction output yet"}
          />
        </div>
      </SectionCard>

      <SectionCard title="Knowledge Convergence Bridge">
        <div style={bridgePanelStyle}>
          <div style={bridgeTextStyle}>
            Friction Signals are the demand-side surface: they show where users are blocked, frustrated, or repeatedly
            asking for better workflows. Use Knowledge to compare this pain against Agent Watch supply before sending
            anything into Project Takeaway review.
          </div>
          <div style={bridgeStepGridStyle}>
            <div style={bridgeStepStyle}>
              <strong>Demand</strong>
              <span>User pain, implementation gaps, workflow friction, and repeated discussion pressure.</span>
            </div>
            <div style={bridgeStepStyle}>
              <strong>Supply</strong>
              <span>Agent Watch shows whether the ecosystem is producing a credible response.</span>
            </div>
            <div style={bridgeStepStyle}>
              <strong>Review</strong>
              <span>Knowledge convergence keeps project action gated by evidence and human review; demand pressure alone is not an action signal.</span>
            </div>
          </div>
          <Link href="/knowledge" style={surfacePrimaryButtonStyle}>
            Open Knowledge Convergence
          </Link>
        </div>
      </SectionCard>

      <SectionCard title="Coverage Snapshot">
        {signals.length ? (
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
              gap: "12px",
            }}
          >
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
          <div style={emptyPanelStyle}>
            No friction signals are loaded yet. This usually means the local output or
            daily pipeline has not produced friction signal data yet.
          </div>
        )}
      </SectionCard>

      <SectionCard title="Friction Tracking Snapshot">
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
            gap: "12px",
          }}
        >
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
                key={`${item.url || item.title || "friction-mover"}-${index}`}
                href={`/friction-signals/detail?entity_id=${encodeURIComponent(item.url || "")}`}
                style={trackingMoverLinkStyle}
              >
                <div>
                  <div style={{ color: "var(--app-text-strong)", fontWeight: 700 }}>
                    {cleanDisplayText(item.title) || "Untitled friction signal"}
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
            No tracked friction movers yet.
          </div>
        )}
      </SectionCard>

      <SectionCard title="Tracked Friction Signals" marginBottom="0">
        {signals.length ? (
          <div style={{ display: "grid", gap: "12px" }}>
            <div style={filterPanelStyle}>
              <label style={{ display: "grid", gap: "6px" }}>
                <span style={{ color: "var(--app-text-subtle)", fontSize: "13px" }}>Source</span>
                <select
                  value={sourceFilter}
                  onChange={(event) => setSourceFilter(event.target.value)}
                  style={controlStyle}
                >
                  <option value="all">All sources</option>
                  {sourceOptions.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              </label>

              <label style={{ display: "grid", gap: "6px" }}>
                <span style={{ color: "var(--app-text-subtle)", fontSize: "13px" }}>Subtopic</span>
                <select
                  value={subtopicFilter}
                  onChange={(event) => setSubtopicFilter(event.target.value)}
                  style={controlStyle}
                >
                  <option value="all">All subtopics</option>
                  {subtopicOptions.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              </label>

              <label style={{ display: "grid", gap: "6px" }}>
                <span style={{ color: "var(--app-text-subtle)", fontSize: "13px" }}>Insight</span>
                <select
                  value={insightFilter}
                  onChange={(event) => setInsightFilter(event.target.value)}
                  style={controlStyle}
                >
                  <option value="all">All insights</option>
                  <option value="ready">Insight ready</option>
                  <option value="pending">Insight pending</option>
                </select>
              </label>

              <label style={{ display: "grid", gap: "6px" }}>
                <span style={{ color: "var(--app-text-subtle)", fontSize: "13px" }}>Tracking</span>
                <select
                  value={trackingFilter}
                  onChange={(event) => setTrackingFilter(event.target.value)}
                  style={controlStyle}
                >
                  <option value="all">All tracking</option>
                  <option value="active">Tracking active</option>
                  <option value="new">Newly tracked</option>
                  <option value="movers">Big movers</option>
                  <option value="untracked">Untracked</option>
                </select>
              </label>

              <label style={{ display: "grid", gap: "6px" }}>
                <span style={{ color: "var(--app-text-subtle)", fontSize: "13px" }}>State</span>
                <select
                  value={stateFilter}
                  onChange={(event) => setStateFilter(event.target.value)}
                  style={controlStyle}
                >
                  <option value="all">All states</option>
                  <option value="new">New</option>
                  <option value="heating">Heating</option>
                  <option value="sustained">Sustained</option>
                  <option value="cooling">Cooling</option>
                  <option value="dropped">Dropped</option>
                  <option value="revived">Revived</option>
                  <option value="untracked">Untracked</option>
                </select>
              </label>

              <label style={{ display: "grid", gap: "6px" }}>
                <span style={{ color: "var(--app-text-subtle)", fontSize: "13px" }}>Starred</span>
                <select
                  value={starredFilter}
                  onChange={(event) => setStarredFilter(event.target.value)}
                  style={controlStyle}
                >
                  <option value="all">All signals</option>
                  <option value="starred">Starred only</option>
                  <option value="unstarred">Unstarred only</option>
                </select>
              </label>

              <label style={{ display: "grid", gap: "6px" }}>
                <span style={{ color: "var(--app-text-subtle)", fontSize: "13px" }}>Sort</span>
                <select
                  value={sortMode}
                  onChange={(event) => setSortMode(event.target.value)}
                  style={controlStyle}
                >
                  <option value="score">Friction score</option>
                  <option value="pain">Pain severity</option>
                  <option value="relevance">Ecosystem relevance</option>
                  <option value="delta">Tracking delta</option>
                  <option value="observed">Days observed</option>
                  <option value="recent">Most recent</option>
                </select>
              </label>

              <label style={{ display: "grid", gap: "6px" }}>
                <span style={{ color: "var(--app-text-subtle)", fontSize: "13px" }}>Search</span>
                <input
                  value={searchTerm}
                  onChange={(event) => setSearchTerm(event.target.value)}
                  placeholder="Search title, summary, repo, or keywords"
                  style={controlStyle}
                />
              </label>
            </div>

            <div style={{ color: "var(--app-text-subtle)", fontSize: "14px" }}>
              Showing {filteredSignals.length} of {signals.length} tracked friction signals.
            </div>

            {filteredSignals.map((item, index) => {
              const entityId = getFrictionEntityId(item, index);
              const translation = translations[entityId];
              const translatedFields = translation?.translatedFields;
              const isChinese = Boolean(translation?.showChinese && translatedFields);
              const isStarred = Boolean(starred[entityId]);
              const tracking = item.tracking;
              const trackingState = getTrackingState(tracking);
              const whyTrackNow = buildWhyTrackNow(item, trackingState);
              const whatChanged = buildWhatChanged(item, trackingState);
              const metaBits = [
                cleanDisplayText(isChinese ? translatedFields?.friction_subtopic : item.friction_subtopic),
                cleanDisplayText(item.repo_name),
                cleanDisplayText(item.source),
                cleanDisplayText(item.published_at),
              ].filter(Boolean);

              return (
                <div
                  key={`${item.title || "friction"}-${index}`}
                  style={{
                    padding: "16px",
                    borderRadius: "8px",
                    background: "var(--app-surface-muted-bg)",
                    border: "1px solid var(--app-surface-strong-border)",
                    display: "grid",
                    gap: "8px",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", gap: "12px", flexWrap: "wrap" }}>
                    <div style={{ color: "var(--app-text-strong)", fontSize: "18px", fontWeight: 700 }}>
                      {cleanDisplayText(isChinese ? translatedFields?.title : item.title) || "Untitled Friction Signal"}
                    </div>
                    <div style={{ display: "flex", gap: "8px", alignItems: "center", flexWrap: "wrap" }}>
                      {isStarred ? <span style={starBadgeStyle}>Starred</span> : null}
                      <span style={scoreBadgeStyle}>Score {scoreLabel(item.friction_score)}</span>
                    </div>
                  </div>

                  {metaBits.length ? (
                    <div style={{ color: "var(--app-text-subtle)", fontSize: "13px" }}>{metaBits.join(" | ")}</div>
                  ) : null}

                  <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                    <span style={scoreBadgeStyle}>
                      {item.profile ? "LLM Insight Ready" : "Insight Pending"}
                    </span>
                    {tracking ? <span style={trackingBadgeStyle}>Tracking Active</span> : null}
                    <span style={trackingStateBadgeStyle(trackingState)}>
                      {trackingStateLabel(trackingState)}
                    </span>
                  </div>

                  <div style={{ color: "var(--app-text-muted)", lineHeight: 1.7 }}>
                    {cleanDisplayText(isChinese ? translatedFields?.summary : item.summary) || "No friction summary available."}
                  </div>

                  <div style={trackingReadoutGridStyle}>
                    <ProfileBlock label="Why track now" value={whyTrackNow} />
                    <ProfileBlock label="What changed" value={whatChanged} />
                  </div>

                  {(isChinese ? translatedFields?.profile?.why_this_matters : item.profile?.why_this_matters) ? (
                    <ProfileBlock
                      label="Why This Matters"
                      value={cleanDisplayText(isChinese ? translatedFields?.profile?.why_this_matters : item.profile?.why_this_matters)}
                    />
                  ) : null}

                  {(isChinese ? translatedFields?.profile?.product_opportunity : item.profile?.product_opportunity) ? (
                    <ProfileBlock
                      label="Product Opportunity"
                      value={cleanDisplayText(isChinese ? translatedFields?.profile?.product_opportunity : item.profile?.product_opportunity)}
                    />
                  ) : null}

                  {translation?.translatedText && false ? (
                    <div
                      style={{
                        display: "grid",
                        gap: "6px",
                        padding: "12px 14px",
                        borderRadius: "12px",
                        background: "var(--app-info-bg)",
                        border: "1px solid var(--app-info-border)",
                      }}
                    >
                      <div
                        style={{
                          color: "var(--app-info-fg)",
                          fontSize: "12px",
                          fontWeight: 700,
                          textTransform: "uppercase",
                        }}
                      >
                        Chinese translation
                      </div>
                      <div style={{ color: "var(--app-info-fg)", lineHeight: 1.8, whiteSpace: "pre-wrap" }}>
                        {translation.translatedText}
                      </div>
                    </div>
                  ) : null}

                  {translation?.error ? (
                    <div style={{ color: "var(--app-danger-fg)", fontSize: "13px" }}>{translation.error}</div>
                  ) : null}

                  <div style={{ color: "var(--app-text-subtle)", fontSize: "13px" }}>
                    Friction score {scoreLabel(item.friction_score)} | Pain {scoreLabel(item.pain_severity_score)} | Relevance {scoreLabel(item.ecosystem_relevance_score)}
                  </div>

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

                  {item.matched_keywords?.length ? (
                    <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                      {cleanDisplayList(item.matched_keywords).map((keyword) => (
                        <span key={`${item.title || "friction"}-${keyword}`} style={keywordStyle}>
                          {keyword}
                        </span>
                      ))}
                    </div>
                  ) : null}

                  {item.url ? (
                    <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                      <button
                        type="button"
                        onClick={() => toggleStar(entityId)}
                        style={surfaceActionButtonStyle}
                      >
                        {isStarred ? "Unstar" : "Star"}
                      </button>
                      <Link
                        href={`/friction-signals/detail?entity_id=${encodeURIComponent(item.url)}${isChinese ? "&lang=zh" : ""}`}
                        style={surfaceActionLinkStyle}
                      >
                        View Details
                      </Link>
                      {isChinese ? (
                        <button
                          type="button"
                          onClick={() => showEnglish(entityId)}
                          style={surfaceActionButtonStyle}
                        >
                          English
                        </button>
                      ) : (
                        <button
                          type="button"
                          onClick={() => (translation?.translatedFields ? enableChinese(entityId) : translateItem(item, index))}
                          style={surfaceActionButtonStyle}
                        >
                          {translation?.loading ? "Translating..." : "Chinese"}
                        </button>
                      )}
                      <a href={item.url} target="_blank" rel="noreferrer" style={surfaceActionLinkStyle}>
                        Open Discussion
                      </a>
                    </div>
                  ) : null}
                </div>
              );
            })}

            {!filteredSignals.length ? (
              <div style={emptyPanelStyle}>No friction signals match the current filters.</div>
            ) : null}
          </div>
        ) : (
          <div style={{ color: "var(--app-text-subtle)" }}>No friction signals available yet.</div>
        )}
      </SectionCard>
    </AppContainer>
  );
}

function InfoCard({ label, value }: { label: string; value: string }) {
  return (
    <div
      style={{
        borderRadius: "14px",
        border: "1px solid var(--app-surface-border)",
        background: "var(--app-surface-bg)",
        padding: "16px 18px",
        display: "grid",
        gap: "6px",
      }}
    >
      <div style={{ color: "var(--app-text-subtle)", fontSize: "13px" }}>{label}</div>
      <div style={{ color: "var(--app-text-strong)", fontSize: "15px", fontWeight: 700 }}>{value}</div>
    </div>
  );
}

function BreakdownCard({
  label,
  items,
  emptyLabel,
}: {
  label: string;
  items: Array<[string, number]>;
  emptyLabel: string;
}) {
  return (
    <div
      style={{
        border: "1px solid var(--app-surface-border)",
        borderRadius: "14px",
        padding: "16px",
        background: "var(--app-surface-bg)",
        display: "grid",
        gap: "12px",
      }}
    >
      <div style={{ color: "var(--app-text-strong)", fontWeight: 700 }}>{label}</div>
      {items.length ? (
        <div style={{ display: "grid", gap: "10px" }}>
          {items.map(([name, count]) => (
            <div
              key={`${label}-${name}`}
              style={{ display: "flex", justifyContent: "space-between", gap: "12px", color: "var(--app-text-muted)" }}
            >
              <span>{name}</span>
              <span style={{ fontWeight: 700 }}>{count}</span>
            </div>
          ))}
        </div>
      ) : (
        <div style={{ color: "var(--app-text-subtle)" }}>{emptyLabel}</div>
      )}
    </div>
  );
}

function ProfileBlock({ label, value }: { label: string; value: string }) {
  return (
    <div
      style={{
        display: "grid",
        gap: "6px",
        padding: "12px 14px",
        borderRadius: "8px",
        background: "var(--app-surface-bg)",
        border: "1px solid var(--app-surface-border)",
      }}
    >
      <div
        style={{
          color: "var(--app-text-subtle)",
          fontSize: "12px",
          fontWeight: 700,
          textTransform: "uppercase",
        }}
      >
        {label}
      </div>
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

const controlStyle: CSSProperties = {
  border: "1px solid var(--app-secondary-action-border)",
  borderRadius: "10px",
  padding: "10px 12px",
  fontSize: "14px",
  background: "var(--app-surface-bg)",
  color: "var(--app-text-strong)",
};

const keywordStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  padding: "4px 10px",
  borderRadius: "999px",
  background: "var(--app-chip-bg)",
  border: "1px solid var(--app-chip-border)",
  color: "var(--app-chip-fg)",
  fontSize: "12px",
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

const starBadgeStyle: CSSProperties = {
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

const trackingReadoutGridStyle: CSSProperties = {
  display: "grid",
  gap: "10px",
  gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
};

const trackingGridStyle: CSSProperties = {
  display: "grid",
  gap: "10px",
  gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
};

const miniMetricStyle: CSSProperties = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
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

const trackingMoverLinkStyle: CSSProperties = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  padding: "12px 14px",
  background: "var(--app-surface-muted-bg)",
  textDecoration: "none",
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  gap: "12px",
  flexWrap: "wrap",
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
  textDecoration: "none",
  fontSize: "13px",
  fontWeight: 700,
};

const surfaceActionButtonStyle: CSSProperties = {
  padding: "7px 12px",
  borderRadius: "8px",
  border: "1px solid var(--app-secondary-action-border)",
  background: "var(--app-secondary-action-bg)",
  color: "var(--app-secondary-action-fg)",
  display: "inline-flex",
  alignItems: "center",
  fontSize: "13px",
  fontWeight: 600,
  cursor: "pointer",
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

const emptyPanelStyle: CSSProperties = {
  color: "var(--app-text-subtle)",
  border: "1px dashed var(--app-secondary-action-border)",
  borderRadius: "14px",
  padding: "18px",
  background: "var(--app-surface-muted-bg)",
  lineHeight: 1.7,
};

const messagePanelStyle: CSSProperties = {
  color: "var(--app-info-fg)",
  border: "1px solid var(--app-info-border)",
  borderRadius: "14px",
  padding: "14px 16px",
  background: "var(--app-info-bg)",
  lineHeight: 1.6,
};

const scoreBadgeStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  padding: "4px 10px",
  borderRadius: "999px",
  background: "var(--app-surface-bg)",
  border: "1px solid var(--app-warning-border)",
  color: "var(--app-warning-fg)",
  fontSize: "12px",
  fontWeight: 700,
};
