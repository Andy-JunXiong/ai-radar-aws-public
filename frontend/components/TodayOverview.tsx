"use client";

import { useEffect, useMemo, useState, type CSSProperties, type ReactNode } from "react";
import Link from "next/link";
import AppContainer from "@/components/AppContainer";
import PageHeader from "@/components/PageHeader";
import { adminFetch } from "@/lib/adminAuth";
import { apiUrl } from "@/lib/api";
import { evaluateTodayMateriality } from "./todayOverviewMateriality";
import {
  evaluateTodayOverviewState,
  selectTodayObservedSignals,
  type TodayOverviewGateCode,
  type TodayOverviewStateResult,
} from "./todayOverviewState";

type JsonRecord = Record<string, unknown>;

type SignalItem = JsonRecord & {
  id?: string;
  signal_id?: string;
  title?: string;
  summary?: string;
  why_it_matters?: string;
  source?: string;
  source_name?: string;
  source_url?: string;
  url?: string;
  collected_at?: string;
  topic?: string;
  score?: number | string | null;
  status?: string;
  is_manual?: boolean;
  verification_status?: string;
  importance_level?: string;
  importance_reason?: string[];
  verification?: JsonRecord;
  verification_metadata?: JsonRecord;
};

type CandidateItem = JsonRecord & {
  signal_id?: string;
  project_id?: string;
  project_name?: string;
  status?: string;
  review_outcome?: string;
  candidate_source?: string;
  saved_at?: string;
  verification_metadata?: JsonRecord & { convergence_brief_id?: string };
};

type ConvergenceMember = JsonRecord & {
  entity_id?: string;
  title?: string;
};

type ConvergenceBrief = JsonRecord & {
  cluster_id?: string;
  label?: string;
  brief?: string;
  supply_read?: string;
  demand_read?: string;
  why_paired?: string;
  review_boundary?: string;
  score?: number;
  agent_watch_item?: ConvergenceMember;
  friction_item?: ConvergenceMember;
  evidence_profile?: JsonRecord & { support_note?: string };
};

type LoadedPayload = {
  operatorDate: string;
  operatorTimeZone: string;
  pageAsOf: string;
  signals: SignalItem[];
  radar: JsonRecord;
  synthesis: JsonRecord;
  candidates: CandidateItem[];
  metricsStatus: JsonRecord;
  dailySummary: JsonRecord;
  failedReadGroups: string[];
};

type TopicItem = { label: string; score: number | null; source: string };

const REQUIRED_RADAR_ARTIFACTS = [
  "topic_trends",
  "topic_momentum",
  "rising_topics",
  "strategic_priority",
  "weekly_momentum",
] as const;

const GATE_LABELS: Record<TodayOverviewGateCode, string> = {
  latest_signal_activity_not_today: "Latest signal activity is not Today",
  pipeline_run_missing: "Today pipeline run is missing",
  collector_run_missing: "Today collector run is missing",
  daily_summary_date_mismatch: "Daily summary date does not match Today",
  pipeline_unsuccessful: "Today pipeline did not complete successfully",
  signals_artifact_missing: "Signals artifact is missing",
  daily_radar_artifact_missing: "Daily Radar artifact is missing",
  artifact_write_failed: "One or more artifact writes failed",
  collector_coverage_incomplete: "Collector coverage is incomplete",
  materiality_incomplete: "Signal materiality metadata is incomplete",
  radar_artifact_not_today: "A displayed Radar artifact is stale or undated",
  signal_after_page_as_of: "A displayed signal is later than the page as-of time",
};

function isRecord(value: unknown): value is JsonRecord {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function text(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function numberOrNull(value: unknown): number | null {
  const parsed = Number(value);
  return value !== null && value !== "" && Number.isFinite(parsed) ? parsed : null;
}

function localDateKey(value: unknown, timeZone: string): string | null {
  if (typeof value !== "string" || !value.trim()) return null;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return null;
  const parts = new Intl.DateTimeFormat("en-AU", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(parsed);
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return `${values.year}-${values.month}-${values.day}`;
}

function operatorContext() {
  const operatorTimeZone = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  const now = new Date();
  return {
    operatorTimeZone,
    operatorDate: localDateKey(now.toISOString(), operatorTimeZone) || now.toISOString().slice(0, 10),
  };
}

function extractSignals(payload: unknown): SignalItem[] | null {
  if (Array.isArray(payload)) return payload.filter(isRecord) as SignalItem[];
  if (!isRecord(payload)) return null;
  const items = payload.signals ?? payload.items;
  return Array.isArray(items) ? (items.filter(isRecord) as SignalItem[]) : null;
}

function artifactItems(artifact: unknown): JsonRecord {
  if (!isRecord(artifact)) return {};
  return isRecord(artifact.items) ? artifact.items : artifact;
}

function normalizeTopic(raw: unknown): { label: string; score: number | null } | null {
  if (typeof raw === "string") return raw.trim() ? { label: raw.trim(), score: null } : null;
  if (Array.isArray(raw) && raw.length) {
    const label = text(raw[0]);
    return label ? { label, score: numberOrNull(raw[1]) } : null;
  }
  if (!isRecord(raw)) return null;
  const label = text(raw.topic) || text(raw.label) || text(raw.name);
  const score =
    numberOrNull(raw.priority_score) ??
    numberOrNull(raw.rising_score) ??
    numberOrNull(raw.momentum_delta) ??
    numberOrNull(raw.score) ??
    numberOrNull(raw.count) ??
    numberOrNull(raw.topic_count);
  return label ? { label, score } : null;
}

function collectTopics(radar: JsonRecord): TopicItem[] {
  const priority = artifactItems(radar.strategic_priority).strategic_priority_topics;
  const rising = artifactItems(radar.rising_topics).rising_topics;
  const weeklyItems = artifactItems(radar.weekly_momentum);
  const weekly = [
    ...(Array.isArray(weeklyItems.rising_this_week) ? weeklyItems.rising_this_week : []),
    ...(Array.isArray(weeklyItems.stable_this_week) ? weeklyItems.stable_this_week : []),
    ...(Array.isArray(weeklyItems.cooling_this_week) ? weeklyItems.cooling_this_week : []),
  ];
  const trends = artifactItems(radar.topic_trends).top_topics;
  const groups: Array<{ source: string; items: unknown[] }> = [
    { source: "Strategic priority", items: Array.isArray(priority) ? priority : [] },
    { source: "Rising", items: Array.isArray(rising) ? rising : [] },
    { source: "Weekly", items: weekly },
    { source: "Trend", items: Array.isArray(trends) ? trends : [] },
  ];
  const seen = new Map<string, TopicItem>();
  for (const group of groups) {
    for (const raw of group.items) {
      const item = normalizeTopic(raw);
      if (!item) continue;
      const key = item.label.toLocaleLowerCase();
      const existing = seen.get(key);
      if (existing) {
        if (!existing.source.includes(group.source)) existing.source += ` · ${group.source}`;
        continue;
      }
      seen.set(key, { ...item, source: group.source });
    }
  }
  return [...seen.values()]
    .sort((a, b) => (b.score ?? -Infinity) - (a.score ?? -Infinity) || a.label.localeCompare(b.label))
    .slice(0, 5);
}

function convergenceBriefs(synthesis: JsonRecord): ConvergenceBrief[] {
  const supplyDemand = isRecord(synthesis.supply_demand) ? synthesis.supply_demand : {};
  return Array.isArray(supplyDemand.convergence_briefs)
    ? (supplyDemand.convergence_briefs.filter(isRecord) as ConvergenceBrief[])
    : [];
}

function candidateClusterId(candidate: CandidateItem): string {
  return text(candidate.verification_metadata?.convergence_brief_id);
}

function signalId(signal: SignalItem): string {
  return text(signal.signal_id) || text(signal.id);
}

function verificationView(signal: SignalItem): { status: string; blocked: string[] } {
  const verification = isRecord(signal.verification_metadata)
    ? signal.verification_metadata
    : isRecord(signal.verification)
      ? signal.verification
      : {};
  const blocked = Array.isArray(verification.blocked_downstream_actions)
    ? verification.blocked_downstream_actions.filter((item): item is string => typeof item === "string")
    : [];
  return {
    status: text(signal.verification_status) || text(verification.verification_status) || "not recorded",
    blocked,
  };
}

async function readJson(
  group: string,
  path: string,
  secure: boolean,
  signal: AbortSignal,
): Promise<{ group: string; data: unknown }> {
  const response = await (secure ? adminFetch : fetch)(apiUrl(path), { cache: "no-store", signal });
  if (!response.ok) throw new Error(`${group}: HTTP ${response.status}`);
  try {
    return { group, data: await response.json() };
  } catch {
    throw new Error(`${group}: malformed JSON`);
  }
}

function validateRead(group: string, value: unknown): unknown {
  if (group === "Signals") {
    const signals = extractSignals(value);
    if (!signals) throw new Error(`${group}: malformed response`);
    return signals;
  }
  if (!isRecord(value)) throw new Error(`${group}: malformed response`);
  if (group === "Radar intelligence" && REQUIRED_RADAR_ARTIFACTS.some((key) => !isRecord(value[key]))) {
    throw new Error(`${group}: required artifact missing`);
  }
  if (
    group === "Strategic synthesis" &&
    (!text(value.generated_at) || !Array.isArray(value.strategic_topics) || !isRecord(value.supply_demand))
  ) {
    throw new Error(`${group}: synthesis shape missing`);
  }
  if (group === "Review candidates" && !Array.isArray(value.items)) {
    throw new Error(`${group}: items missing`);
  }
  if (
    group === "Metrics status" &&
    (!Object.prototype.hasOwnProperty.call(value, "latest_signal_activity_date") ||
      !Array.isArray(value.signal_dates_missing_pipeline_runs) ||
      !Array.isArray(value.signal_dates_missing_collector_runs))
  ) {
    throw new Error(`${group}: status shape missing`);
  }
  if (group === "Daily metrics" && (!text(value.date) || !isRecord(value.summary))) {
    throw new Error(`${group}: summary missing`);
  }
  return value;
}

export default function TodayOverview() {
  const [refreshKey, setRefreshKey] = useState(0);
  const [loading, setLoading] = useState(true);
  const [payload, setPayload] = useState<LoadedPayload | null>(null);

  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), 12_000);
    const { operatorDate, operatorTimeZone } = operatorContext();
    const specs = [
      ["Signals", "/signals?status=all", false],
      ["Radar intelligence", "/radar/intelligence", false],
      ["Strategic synthesis", "/radar/strategic-synthesis", true],
      ["Review candidates", "/projects/takeaway-candidates?include_confirmed=true&include_closed=true", true],
      ["Metrics status", "/metrics/status", true],
      ["Daily metrics", `/metrics/daily-summary?date=${encodeURIComponent(operatorDate)}`, true],
    ] as const;

    Promise.allSettled(
      specs.map(([group, path, secure]) =>
        readJson(group, path, secure, controller.signal).then(({ data }) => ({
          group,
          data: validateRead(group, data),
        })),
      ),
    ).then((results) => {
      if (!active) return;
      const values = new Map<string, unknown>();
      const failedReadGroups: string[] = [];
      results.forEach((result, index) => {
        const group = specs[index][0];
        if (result.status === "fulfilled") values.set(group, result.value.data);
        else failedReadGroups.push(group);
      });
      const candidatePayload = values.get("Review candidates");
      setPayload({
        operatorDate,
        operatorTimeZone,
        pageAsOf: new Date().toISOString(),
        signals: (values.get("Signals") as SignalItem[] | undefined) || [],
        radar: (values.get("Radar intelligence") as JsonRecord | undefined) || {},
        synthesis: (values.get("Strategic synthesis") as JsonRecord | undefined) || {},
        candidates:
          isRecord(candidatePayload) && Array.isArray(candidatePayload.items)
            ? (candidatePayload.items.filter(isRecord) as CandidateItem[])
            : [],
        metricsStatus: (values.get("Metrics status") as JsonRecord | undefined) || {},
        dailySummary: (values.get("Daily metrics") as JsonRecord | undefined) || {},
        failedReadGroups,
      });
      setLoading(false);
    });

    return () => {
      active = false;
      window.clearTimeout(timeoutId);
      controller.abort();
    };
  }, [refreshKey]);

  const view = useMemo(() => (payload ? buildView(payload) : null), [payload]);

  return (
    <AppContainer style={{ maxWidth: "1120px" }}>
      <PageHeader
        title="Today Overview"
        description="A read-only operational view of today’s data health, observed signals, current interpretation, and governed review context."
        size="compact"
        marginBottom="20px"
      />

      {loading || !payload || !view ? (
        <Panel><p style={mutedTextStyle}>Loading today’s required reads…</p></Panel>
      ) : (
        <>
          <DataHealthPanel
            payload={payload}
            state={view.state}
            onRetry={() => {
              setLoading(true);
              setPayload(null);
              setRefreshKey((value) => value + 1);
            }}
          />

          {view.state.state !== "load_failed" ? (
            <div style={{ display: "grid", gap: "16px", marginTop: "16px" }}>
              {view.state.state === "stale_or_partial" ? (
                <div style={contextLabelStyle}>Available context · not a complete daily conclusion</div>
              ) : null}
              <ObservedToday signals={view.observed} />
              <CurrentInterpretation
                topics={view.topics}
                briefs={view.briefs}
                candidateByCluster={view.candidateByCluster}
              />
              <NeedsJudgment candidates={view.pendingCandidates} />
            </div>
          ) : null}
        </>
      )}
    </AppContainer>
  );
}

function buildView(payload: LoadedPayload) {
  const observed = selectTodayObservedSignals(
    payload.signals,
    payload.operatorDate,
    payload.operatorTimeZone,
  );
  const materiality = evaluateTodayMateriality(
    payload.signals,
    payload.operatorDate,
    payload.operatorTimeZone,
  );
  const briefs = convergenceBriefs(payload.synthesis);
  const briefIds = new Set(briefs.map((brief) => text(brief.cluster_id)).filter(Boolean));
  const candidateByCluster = new Map<string, CandidateItem>();
  for (const candidate of payload.candidates) {
    const clusterId = candidateClusterId(candidate);
    if (clusterId && briefIds.has(clusterId) && !candidateByCluster.has(clusterId)) {
      candidateByCluster.set(clusterId, candidate);
    }
  }
  const radarArtifactDates: Array<{ name: string; value: unknown }> = REQUIRED_RADAR_ARTIFACTS.map((name) => {
    const artifact = isRecord(payload.radar[name]) ? payload.radar[name] : {};
    return { name, value: artifact.date || artifact.generated_at };
  });
  radarArtifactDates.push({
    name: "strategic_synthesis",
    value: payload.synthesis.date || payload.synthesis.generated_at,
  });
  const state = evaluateTodayOverviewState({
    operatorDate: payload.operatorDate,
    operatorTimeZone: payload.operatorTimeZone,
    failedReadGroups: payload.failedReadGroups,
    metricsStatus: payload.metricsStatus,
    dailySummary: payload.dailySummary,
    radarArtifactDates,
    newestDisplayedSignalAt:
      observed
        .map((signal) => text(signal.collected_at))
        .filter(Boolean)
        .sort((a, b) => new Date(b).getTime() - new Date(a).getTime())[0] || null,
    pageAsOf: payload.pageAsOf,
    materiality,
    governedConvergenceCount: candidateByCluster.size,
  });
  const pendingCandidates = payload.candidates
    .filter((candidate) => candidate.status === "candidate")
    .sort(
      (a, b) =>
        new Date(text(b.saved_at) || 0).getTime() - new Date(text(a.saved_at) || 0).getTime() ||
        text(a.project_id).localeCompare(text(b.project_id)) ||
        text(a.signal_id).localeCompare(text(b.signal_id)),
    )
    .slice(0, 5);

  return {
    state,
    observed,
    topics: collectTopics(payload.radar),
    briefs: [...briefs]
      .sort((a, b) => (numberOrNull(b.score) ?? -Infinity) - (numberOrNull(a.score) ?? -Infinity))
      .slice(0, 3),
    candidateByCluster,
    pendingCandidates,
  };
}

function DataHealthPanel({
  payload,
  state,
  onRetry,
}: {
  payload: LoadedPayload;
  state: TodayOverviewStateResult;
  onRetry: () => void;
}) {
  const coverage = isRecord(payload.dailySummary.summary)
    ? isRecord(payload.dailySummary.summary.collectors)
      ? isRecord(payload.dailySummary.summary.collectors.coverage)
        ? text(payload.dailySummary.summary.collectors.coverage.completeness)
        : ""
      : ""
    : "";
  const tone =
    state.state === "load_failed"
      ? "var(--app-danger-border)"
      : state.state === "stale_or_partial"
        ? "var(--app-warning-border)"
        : "var(--app-success-border)";
  return (
    <Panel style={{ borderTop: `3px solid ${tone}` }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: "20px", alignItems: "flex-start", flexWrap: "wrap" }}>
        <div style={{ maxWidth: "760px" }}>
          <Eyebrow>Data health</Eyebrow>
          <h2 style={{ margin: "6px 0 8px", fontSize: "24px", lineHeight: 1.25 }}>{state.headline}</h2>
          <p style={mutedTextStyle}>
            As of {formatDateTime(payload.pageAsOf)} · {payload.operatorTimeZone} · Today {payload.operatorDate}
          </p>
        </div>
        <button type="button" onClick={onRetry} style={buttonStyle}>Retry required reads</button>
      </div>

      {state.failedReadGroups.length ? (
        <Notice title="Failed read groups" items={state.failedReadGroups} tone="danger" />
      ) : state.failedGates.length ? (
        <Notice
          title="Failed freshness or completeness gates"
          items={state.failedGates.map((gate) => GATE_LABELS[gate])}
          tone="warning"
        />
      ) : (
        <div style={{ display: "flex", flexWrap: "wrap", gap: "8px", marginTop: "16px" }}>
          <Chip tone="success">Required reads loaded</Chip>
          <Chip tone="info">Coverage: {coverage || "not recorded"}</Chip>
          <Chip tone="success">Freshness: current</Chip>
        </div>
      )}

      <div style={{ display: "flex", gap: "14px", flexWrap: "wrap", marginTop: "16px" }}>
        <TextLink href="/admin/metrics">Metrics</TextLink>
        <TextLink href="/radar">Radar</TextLink>
        <TextLink href="/signals">All Signals</TextLink>
      </div>
    </Panel>
  );
}

function ObservedToday({ signals }: { signals: SignalItem[] }) {
  return (
    <Section
      title="Observed today"
      description="Distinct, non-rejected signals collected on the operator’s local date."
      tone="observed"
    >
      {signals.length ? signals.map((signal) => {
        const id = signalId(signal);
        const verification = verificationView(signal);
        const source = signal.is_manual || signal.source === "manual"
          ? "Manual input"
          : text(signal.source_name) || text(signal.source) || "Source not recorded";
        return (
          <ItemCard key={id} tone="signal">
            <div style={{ display: "flex", justifyContent: "space-between", gap: "14px", alignItems: "flex-start" }}>
              <div>
                <h3 style={itemTitleStyle}>{text(signal.title) || "Untitled signal"}</h3>
                <p style={bodyTextStyle}>{text(signal.summary) || text(signal.why_it_matters) || "No summary recorded."}</p>
              </div>
              <Score value={numberOrNull(signal.score)} />
            </div>
            <div style={metaRowStyle}>
              <Chip tone="info">{source}</Chip>
              <Chip tone="tag">{text(signal.topic) || "General AI"}</Chip>
              <span>{formatDateTime(signal.collected_at)}</span>
              <Chip>Status: {text(signal.status) || "unknown"}</Chip>
              <Chip>Verification: {verification.status}</Chip>
            </div>
            {verification.blocked.length ? (
              <p style={{ ...mutedTextStyle, marginTop: "9px", color: "var(--app-danger-fg)" }}>
                Blocked downstream: {verification.blocked.join(", ")}
              </p>
            ) : null}
            <div style={{ display: "flex", gap: "12px", marginTop: "12px", flexWrap: "wrap" }}>
              <TextLink href={`/signals/detail?id=${encodeURIComponent(id)}`}>Open Signal</TextLink>
              {text(signal.source_url) || text(signal.url) ? (
                <a href={text(signal.source_url) || text(signal.url)} target="_blank" rel="noreferrer" style={linkStyle}>Source ↗</a>
              ) : null}
            </div>
          </ItemCard>
        );
      }) : <Empty>No valid signals were collected for this operator date.</Empty>}
    </Section>
  );
}

function CurrentInterpretation({
  topics,
  briefs,
  candidateByCluster,
}: {
  topics: TopicItem[];
  briefs: ConvergenceBrief[];
  candidateByCluster: Map<string, CandidateItem>;
}) {
  return (
    <Section
      title="Current interpretation"
      description="Radar synthesis remains interpretation, not verified support."
      tone="interpretation"
    >
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(250px, 1fr))", gap: "10px" }}>
        {topics.length ? topics.map((topic) => (
          <ItemCard key={topic.label} tone="topic">
            <div style={{ display: "flex", justifyContent: "space-between", gap: "12px" }}>
              <h3 style={itemTitleStyle}>{topic.label}</h3><Score value={topic.score} />
            </div>
            <p style={mutedTextStyle}>Contributing artifacts: {topic.source}</p>
          </ItemCard>
        )) : <Empty>No current topic interpretation is available.</Empty>}
      </div>

      {briefs.length ? (
        <div style={{ marginTop: "16px" }}>
          <Eyebrow>Interpretation / review context</Eyebrow>
          {briefs.map((brief, index) => {
            const clusterId = text(brief.cluster_id);
            const candidate = candidateByCluster.get(clusterId);
            const agentId = text(brief.agent_watch_item?.entity_id);
            const frictionId = text(brief.friction_item?.entity_id);
            return (
              <ItemCard key={clusterId || `brief-${index}`} tone="brief" style={{ marginTop: "9px" }}>
                <h3 style={itemTitleStyle}>{text(brief.label) || "Convergence brief"}</h3>
                <p style={bodyTextStyle}>{text(brief.brief) || text(brief.why_paired) || "No brief recorded."}</p>
                <div style={{ display: "grid", gap: "5px", marginTop: "10px" }}>
                  {text(brief.supply_read) ? <p style={mutedTextStyle}>{text(brief.supply_read)}</p> : null}
                  {text(brief.demand_read) ? <p style={mutedTextStyle}>{text(brief.demand_read)}</p> : null}
                  {text(brief.why_paired) ? <p style={mutedTextStyle}>Why paired: {text(brief.why_paired)}</p> : null}
                  {text(brief.evidence_profile?.support_note) ? (
                    <p style={mutedTextStyle}>Support note: {text(brief.evidence_profile?.support_note)}</p>
                  ) : null}
                </div>
                {text(brief.review_boundary) ? <p style={boundaryStyle}>Review boundary: {text(brief.review_boundary)}</p> : null}
                <div style={{ display: "flex", gap: "12px", marginTop: "12px", flexWrap: "wrap" }}>
                  {clusterId ? <TextLink href={`/knowledge/detail?id=${encodeURIComponent(clusterId)}`}>Knowledge detail</TextLink> : null}
                  {agentId ? <TextLink href={`/agent-watch/detail?entity_id=${encodeURIComponent(agentId)}`}>Supply signal</TextLink> : null}
                  {frictionId ? <TextLink href={`/friction-signals/detail?entity_id=${encodeURIComponent(frictionId)}`}>Demand signal</TextLink> : null}
                  {candidate ? <TextLink href="/workspace/projects/review">Open Review Inbox</TextLink> : null}
                </div>
              </ItemCard>
            );
          })}
        </div>
      ) : null}
    </Section>
  );
}

function NeedsJudgment({ candidates }: { candidates: CandidateItem[] }) {
  return (
    <Section
      title="Needs judgment"
      description="Only already-created Project Takeaway candidates appear here."
      tone="judgment"
    >
      {candidates.length ? (
        <>
          {candidates.map((candidate, index) => (
            <ItemCard key={`${text(candidate.project_id)}:${text(candidate.signal_id)}:${index}`} tone="candidate">
              <h3 style={itemTitleStyle}>{text(candidate.project_name) || text(candidate.project_id) || "Project review candidate"}</h3>
              <div style={metaRowStyle}>
                <Chip tone="warning">Status: {text(candidate.status)}</Chip>
                <span>Saved: {formatDateTime(candidate.saved_at)}</span>
                <span>Signal: {text(candidate.signal_id) || "not recorded"}</span>
              </div>
            </ItemCard>
          ))}
          <div style={{ marginTop: "12px" }}><TextLink href="/workspace/projects/review">Open Review Inbox</TextLink></div>
        </>
      ) : <Empty>No pending Project Takeaway candidates are returned by Review Inbox.</Empty>}
    </Section>
  );
}

function Panel({ children, style }: { children: ReactNode; style?: CSSProperties }) {
  return <section style={{ ...panelStyle, ...style }}>{children}</section>;
}

function Section({
  title,
  description,
  children,
  tone,
}: {
  title: string;
  description: string;
  children: ReactNode;
  tone: "observed" | "interpretation" | "judgment";
}) {
  const accent =
    tone === "observed"
      ? "var(--app-info-border)"
      : tone === "interpretation"
        ? "var(--app-nav-link-active-border)"
        : "var(--app-warning-border)";
  return (
    <Panel style={{ borderTop: `3px solid ${accent}` }}>
      <h2 style={{ margin: 0, fontSize: "20px" }}>{title}</h2>
      <p style={{ ...mutedTextStyle, marginTop: "6px", marginBottom: "14px" }}>{description}</p>
      <div style={{ display: "grid", gap: "9px" }}>{children}</div>
    </Panel>
  );
}

function ItemCard({
  children,
  style,
  tone = "neutral",
}: {
  children: ReactNode;
  style?: CSSProperties;
  tone?: "neutral" | "signal" | "topic" | "brief" | "candidate";
}) {
  const toneStyle: CSSProperties =
    tone === "signal"
      ? { borderLeft: "3px solid var(--app-info-border)" }
      : tone === "topic"
        ? {
            borderColor: "var(--app-nav-link-active-border)",
            background: "var(--app-tag-bg)",
          }
        : tone === "brief"
          ? {
              borderColor: "var(--app-info-border)",
              background: "var(--app-info-bg)",
            }
          : tone === "candidate"
            ? { borderLeft: "3px solid var(--app-warning-border)" }
            : {};
  return <article style={{ ...itemCardStyle, ...toneStyle, ...style }}>{children}</article>;
}

function Eyebrow({ children }: { children: ReactNode }) {
  return <div style={{ color: "var(--app-text-muted)", fontSize: "12px", fontWeight: 800, letterSpacing: "0.08em", textTransform: "uppercase" }}>{children}</div>;
}

function Score({ value }: { value: number | null }) {
  return value === null ? null : <Chip tone="info">Score {value.toFixed(1)}</Chip>;
}

function Chip({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: "neutral" | "info" | "tag" | "success" | "warning";
}) {
  const palette =
    tone === "info"
      ? { border: "var(--app-info-border)", background: "var(--app-info-bg)", color: "var(--app-info-fg)" }
      : tone === "tag"
        ? { border: "var(--app-nav-link-active-border)", background: "var(--app-tag-bg)", color: "var(--app-tag-fg)" }
        : tone === "success"
          ? { border: "var(--app-success-border)", background: "var(--app-success-bg)", color: "var(--app-success-fg)" }
          : tone === "warning"
            ? { border: "var(--app-warning-border)", background: "var(--app-warning-bg)", color: "var(--app-warning-fg)" }
            : { border: "var(--app-chip-border)", background: "var(--app-chip-bg)", color: "var(--app-chip-fg)" };
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        border: `1px solid ${palette.border}`,
        background: palette.background,
        borderRadius: "999px",
        padding: "4px 9px",
        fontSize: "12px",
        lineHeight: 1.35,
        color: palette.color,
        whiteSpace: "nowrap",
      }}
    >
      {children}
    </span>
  );
}

function Notice({
  title,
  items,
  tone,
}: {
  title: string;
  items: string[];
  tone: "warning" | "danger";
}) {
  const colors =
    tone === "danger"
      ? {
          background: "var(--app-danger-bg)",
          border: "var(--app-danger-border)",
          foreground: "var(--app-danger-fg)",
        }
      : {
          background: "var(--app-warning-bg)",
          border: "var(--app-warning-border)",
          foreground: "var(--app-warning-fg)",
        };
  return (
    <div
      style={{
        marginTop: "16px",
        padding: "12px 14px",
        borderRadius: "8px",
        background: colors.background,
        border: `1px solid ${colors.border}`,
        color: colors.foreground,
      }}
    >
      <strong style={{ fontSize: "13px" }}>{title}</strong>
      <ul style={{ margin: "8px 0 0", paddingLeft: "20px", color: "inherit", fontSize: "13px", lineHeight: 1.6 }}>
        {items.map((item) => <li key={item}>{item}</li>)}
      </ul>
    </div>
  );
}

function Empty({ children }: { children: ReactNode }) {
  return <div style={{ padding: "14px", border: "1px dashed var(--app-surface-border)", borderRadius: "8px", color: "var(--app-text-muted)", fontSize: "13px" }}>{children}</div>;
}

function TextLink({ href, children }: { href: string; children: ReactNode }) {
  return <Link href={href} style={linkStyle}>{children} →</Link>;
}

function formatDateTime(value: unknown): string {
  if (typeof value !== "string" || !value) return "not recorded";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

const panelStyle: CSSProperties = {
  border: "1px solid var(--app-surface-border)", borderRadius: "20px", padding: "20px",
  background: "var(--app-surface-bg)", boxShadow: "var(--app-surface-shadow)",
};
const itemCardStyle: CSSProperties = { border: "1px solid var(--app-surface-border)", borderRadius: "8px", padding: "14px", background: "var(--app-surface-muted-bg)" };
const itemTitleStyle: CSSProperties = { margin: 0, fontSize: "15px", lineHeight: 1.4, color: "var(--app-text-strong)" };
const bodyTextStyle: CSSProperties = { margin: "7px 0 0", fontSize: "13px", lineHeight: 1.6, color: "var(--app-text-muted)" };
const mutedTextStyle: CSSProperties = { margin: 0, fontSize: "13px", lineHeight: 1.6, color: "var(--app-text-muted)" };
const metaRowStyle: CSSProperties = { display: "flex", flexWrap: "wrap", gap: "6px 14px", marginTop: "10px", color: "var(--app-text-muted)", fontSize: "12px" };
const linkStyle: CSSProperties = { color: "var(--app-text-strong)", fontSize: "13px", fontWeight: 700, textDecoration: "none" };
const buttonStyle: CSSProperties = { border: "1px solid var(--app-secondary-action-border)", borderRadius: "8px", padding: "9px 12px", background: "var(--app-secondary-action-bg)", color: "var(--app-secondary-action-fg)", fontWeight: 700, cursor: "pointer" };
const boundaryStyle: CSSProperties = {
  ...mutedTextStyle,
  marginTop: "10px",
  padding: "8px 10px",
  border: "1px solid var(--app-warning-border)",
  borderRadius: "6px",
  background: "var(--app-warning-bg)",
  color: "var(--app-warning-fg)",
};
const contextLabelStyle: CSSProperties = {
  border: "1px solid var(--app-warning-border)",
  background: "var(--app-warning-bg)",
  borderRadius: "8px",
  padding: "10px 12px",
  color: "var(--app-warning-fg)",
  fontSize: "13px",
  fontWeight: 700,
};
