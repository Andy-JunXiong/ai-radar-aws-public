"use client";

import { useEffect, useMemo, useState, type ReactNode } from "react";
import Link from "next/link";
import { BookOpenCheck, BrainCircuit, GitBranch, Radar } from "lucide-react";

import AppContainer from "@/components/AppContainer";
import { apiUrl } from "@/lib/api";
import { adminFetch } from "@/lib/adminAuth";

type StrategicTopic = {
  topic?: string;
  score?: number;
  reason?: string;
};

type Highlight = {
  title?: string;
  summary?: string;
  url?: string;
  entity_id?: string;
  canonical_url?: string;
  repo_url?: string;
  subtopic?: string;
  source?: string;
  type?: string;
  score?: number;
};

type ConvergenceBrief = {
  cluster_id?: string;
  label?: string;
  confidence?: string;
  score?: number;
  shared_topics?: string[];
  agent_watch_item?: Highlight;
  friction_item?: Highlight;
  brief?: string;
  supply_read?: string;
  demand_read?: string;
  why_paired?: string;
  review_boundary?: string;
  why_it_matters?: string;
  recommended_next_step?: string;
  action_gate?: string;
  quality?: KnowledgeQuality;
  review_readiness?: {
    status?: string;
    label?: string;
    reason?: string;
    source_count?: number;
    shared_topic_count?: number;
    matched_project_count?: number;
  };
  project_relevance?: {
    matched_projects?: ProjectMatch[];
    match_count?: number;
    project_takeaway_map?: Record<string, string>;
  };
  evidence_profile?: {
    source_count?: number;
    shared_topic_count?: number;
    strategic_topic_overlap_count?: number;
    agent_watch_score?: number;
    friction_score?: number;
    quality_score?: number;
    quality_label?: string;
    quality_reason?: string;
    support_note?: string;
  };
};

type KnowledgeQuality = {
  score?: number;
  label?: string;
  reason?: string;
  recommendation?: string;
  factors?: Record<string, number>;
};

type CandidateActionState = {
  creating?: boolean;
  created?: boolean;
  message?: string;
  error?: string;
};

type ExistingCandidate = {
  signal_id?: string;
  project_id?: string;
  project_name?: string;
  status?: string;
  review_outcome?: string;
  candidate_source?: string;
  saved_at?: string;
  reviewed_at?: string;
  verification_metadata?: {
    knowledge_convergence?: boolean;
    convergence_brief_id?: string;
    supply_read?: string;
    demand_read?: string;
    why_paired?: string;
    review_boundary?: string;
  };
};

type ExistingCandidatesResponse = {
  items?: ExistingCandidate[];
};

type BriefFreshnessItem = {
  cluster_id: string;
  label: string;
  score: number;
  supply_title: string;
  demand_title: string;
};

type BriefFreshnessSnapshot = {
  captured_at: string;
  response_generated_at: string;
  brief_count: number;
  briefs: BriefFreshnessItem[];
};

type BriefDeltaState = {
  status: "new" | "changed" | "repeated";
  previous_score?: number;
  score_delta?: number;
};

type FreshnessState = {
  previousCapturedAt: string;
  currentCapturedAt: string;
  firstSnapshot: boolean;
  newCount: number;
  changedCount: number;
  repeatedCount: number;
  droppedCount: number;
  deltas: Record<string, BriefDeltaState>;
};

type BriefFilter =
  | "all"
  | "strong_fit"
  | "review_caution"
  | "thin_fit"
  | "ready"
  | "watch"
  | "needs_evidence"
  | "has_project"
  | "in_review";
type BriefSort = "score" | "readiness" | "project_match" | "evidence_density";

const KNOWLEDGE_FRESHNESS_STORAGE_KEY = "ai-radar:knowledge-convergence-snapshot:v1";

type ProjectMatch = {
  project_id?: string;
  project_name?: string;
  status?: string;
  matched_topics?: string[];
  shared_topic_matches?: string[];
  context_matches?: string[];
  match_type?: string;
  score?: number;
  reason?: string;
};

type StrategicSynthesisPayload = {
  generated_at?: string;
  summary?: {
    strategic_topic_count?: number;
    agent_watch_count?: number;
    friction_signal_count?: number;
    convergence_brief_count?: number;
    review_record_count?: number;
    calibration_event_count?: number;
    manual_source_event_count?: number;
    blocked_action_rate?: number;
    latest_reviewed_at?: string;
    latest_calibration_event_at?: string;
  };
  strategic_topics?: StrategicTopic[];
  supply_demand?: {
    agent_watch_highlights?: Highlight[];
    friction_highlights?: Highlight[];
    convergence_briefs?: ConvergenceBrief[];
    interpretation?: string;
  };
  review_quality?: {
    ops_summary?: {
      achieved?: string[];
      gaps?: string[];
      next_focus?: string[];
    };
  };
};

function percent(value?: number) {
  if (!value) return "0%";
  return `${Math.round(value * 1000) / 10}%`;
}

function clean(value?: string) {
  return value?.trim() || "";
}

function briefFreshnessId(brief: ConvergenceBrief, index = 0) {
  return clean(brief.cluster_id) || `${clean(brief.label) || "brief"}-${index}`;
}

function buildBriefFreshnessSnapshot(briefs: ConvergenceBrief[], responseGeneratedAt?: string): BriefFreshnessSnapshot {
  const capturedAt = new Date().toISOString();
  return {
    captured_at: capturedAt,
    response_generated_at: clean(responseGeneratedAt) || capturedAt,
    brief_count: briefs.length,
    briefs: briefs.map((brief, index) => ({
      cluster_id: briefFreshnessId(brief, index),
      label: clean(brief.label) || "Supply / demand convergence",
      score: Math.round((buildKnowledgeQuality(brief).score ?? brief.score ?? 0) * 100) / 100,
      supply_title: clean(brief.agent_watch_item?.title) || "No supply signal",
      demand_title: clean(brief.friction_item?.title) || "No demand pain",
    })),
  };
}

function parseBriefFreshnessSnapshot(raw: string | null): BriefFreshnessSnapshot | null {
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as BriefFreshnessSnapshot | null;
    if (!parsed || !Array.isArray(parsed.briefs)) return null;
    return parsed;
  } catch {
    return null;
  }
}

function buildFreshnessState(current: BriefFreshnessSnapshot, previous: BriefFreshnessSnapshot | null): FreshnessState {
  const previousItems = new Map((previous?.briefs || []).map((item) => [item.cluster_id, item]));
  const currentIds = new Set(current.briefs.map((item) => item.cluster_id));
  const deltas: Record<string, BriefDeltaState> = {};
  let newCount = 0;
  let changedCount = 0;
  let repeatedCount = 0;

  for (const item of current.briefs) {
    const previousItem = previousItems.get(item.cluster_id);
    if (!previousItem) {
      deltas[item.cluster_id] = { status: "new" };
      newCount += 1;
      continue;
    }

    const scoreDelta = Math.round((item.score - previousItem.score) * 100) / 100;
    const titleChanged = item.label !== previousItem.label || item.supply_title !== previousItem.supply_title || item.demand_title !== previousItem.demand_title;
    if (Math.abs(scoreDelta) >= 1 || titleChanged) {
      deltas[item.cluster_id] = {
        status: "changed",
        previous_score: previousItem.score,
        score_delta: scoreDelta,
      };
      changedCount += 1;
      continue;
    }

    deltas[item.cluster_id] = { status: "repeated", previous_score: previousItem.score, score_delta: scoreDelta };
    repeatedCount += 1;
  }

  const droppedCount = (previous?.briefs || []).filter((item) => !currentIds.has(item.cluster_id)).length;
  return {
    previousCapturedAt: previous?.captured_at || "",
    currentCapturedAt: current.captured_at,
    firstSnapshot: !previous,
    newCount,
    changedCount,
    repeatedCount,
    droppedCount,
    deltas,
  };
}

export default function KnowledgePage() {
  const [payload, setPayload] = useState<StrategicSynthesisPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState("");
  const [candidateActions, setCandidateActions] = useState<Record<string, CandidateActionState>>({});
  const [existingCandidates, setExistingCandidates] = useState<Record<string, ExistingCandidate[]>>({});
  const [briefFilter, setBriefFilter] = useState<BriefFilter>("all");
  const [briefSort, setBriefSort] = useState<BriefSort>("score");
  const [freshnessState, setFreshnessState] = useState<FreshnessState | null>(null);

  useEffect(() => {
    let active = true;

    async function loadKnowledgeState() {
      setLoading(true);
      setErrorMessage("");
      try {
        const [synthesisResponse, candidatesResponse] = await Promise.all([
          adminFetch(apiUrl("/radar/strategic-synthesis"), {
            cache: "no-store",
          }),
          adminFetch(apiUrl("/projects/takeaway-candidates?include_confirmed=true&include_closed=true"), {
            cache: "no-store",
          }),
        ]);
        const data = (await synthesisResponse.json().catch(() => null)) as StrategicSynthesisPayload | { detail?: string } | null;
        if (!synthesisResponse.ok) {
          throw new Error((data as { detail?: string } | null)?.detail || `Strategic synthesis failed (${synthesisResponse.status})`);
        }
        const candidateData = (await candidatesResponse.json().catch(() => null)) as ExistingCandidatesResponse | null;
        if (active) {
          setPayload(data as StrategicSynthesisPayload);
          setExistingCandidates(indexKnowledgeCandidates(candidateData?.items || []));
        }
      } catch (error) {
        if (active) {
          setErrorMessage(error instanceof Error ? error.message : "Strategic synthesis is unavailable right now.");
        }
      } finally {
        if (active) setLoading(false);
      }
    }

    void loadKnowledgeState();

    return () => {
      active = false;
    };
  }, []);

  const summary = payload?.summary || {};
  const topics = payload?.strategic_topics || [];
  const agentHighlights = payload?.supply_demand?.agent_watch_highlights || [];
  const frictionHighlights = payload?.supply_demand?.friction_highlights || [];
  const convergenceBriefs = useMemo(
    () => payload?.supply_demand?.convergence_briefs || [],
    [payload?.supply_demand?.convergence_briefs]
  );

  useEffect(() => {
    if (loading || !payload || !convergenceBriefs.length) return;
    const currentSnapshot = buildBriefFreshnessSnapshot(convergenceBriefs, payload.generated_at);
    let previousSnapshot: BriefFreshnessSnapshot | null = null;
    try {
      previousSnapshot = parseBriefFreshnessSnapshot(window.localStorage.getItem(KNOWLEDGE_FRESHNESS_STORAGE_KEY));
      setFreshnessState(buildFreshnessState(currentSnapshot, previousSnapshot));
      window.localStorage.setItem(KNOWLEDGE_FRESHNESS_STORAGE_KEY, JSON.stringify(currentSnapshot));
    } catch {
      setFreshnessState(buildFreshnessState(currentSnapshot, null));
    }
  }, [convergenceBriefs, loading, payload]);

  const ops = payload?.review_quality?.ops_summary || {};
  const visibleConvergenceBriefs = useMemo(
    () =>
      convergenceBriefs
        .filter((brief) => briefMatchesFilter(brief, briefFilter, existingCandidates))
        .sort((left, right) => compareBriefs(left, right, briefSort)),
    [briefFilter, briefSort, convergenceBriefs, existingCandidates]
  );
  const briefFilterOptions = useMemo(
    () =>
      [
        { value: "all" as const, label: "All", count: convergenceBriefs.length },
        { value: "strong_fit" as const, label: "Strong Fit", count: countBriefs(convergenceBriefs, "strong_fit", existingCandidates) },
        {
          value: "review_caution" as const,
          label: "Review Caution",
          count: countBriefs(convergenceBriefs, "review_caution", existingCandidates),
        },
        { value: "thin_fit" as const, label: "Thin Fit", count: countBriefs(convergenceBriefs, "thin_fit", existingCandidates) },
        { value: "ready" as const, label: "Ready", count: countBriefs(convergenceBriefs, "ready", existingCandidates) },
        { value: "watch" as const, label: "Watch", count: countBriefs(convergenceBriefs, "watch", existingCandidates) },
        {
          value: "needs_evidence" as const,
          label: "Needs Evidence",
          count: countBriefs(convergenceBriefs, "needs_evidence", existingCandidates),
        },
        {
          value: "has_project" as const,
          label: "Has Project",
          count: countBriefs(convergenceBriefs, "has_project", existingCandidates),
        },
        {
          value: "in_review" as const,
          label: "In Review",
          count: countBriefs(convergenceBriefs, "in_review", existingCandidates),
        },
      ],
    [convergenceBriefs, existingCandidates]
  );
  const qualitySummary = useMemo(
    () => summarizeKnowledgeQuality(convergenceBriefs, existingCandidates),
    [convergenceBriefs, existingCandidates]
  );

  const healthLabel = useMemo(() => {
    const blockedRate = summary.blocked_action_rate || 0;
    if (blockedRate >= 0.4) return "High friction in action gates";
    if ((summary.review_record_count || 0) > 0) return "Review loop active";
    return "Synthesis ready";
  }, [summary.blocked_action_rate, summary.review_record_count]);

  async function handleCreateCandidate(brief: ConvergenceBrief) {
    const clusterId = clean(brief.cluster_id);
    if (!clusterId) return;
    const matchedProjects = brief.project_relevance?.matched_projects || [];
    const takeawayMap = buildProjectTakeawayMap(brief);
    if (!matchedProjects.length || !Object.keys(takeawayMap).length) {
      setCandidateActions((current) => ({
        ...current,
        [clusterId]: {
          error: "No matched project is available for this convergence brief yet.",
        },
      }));
      return;
    }

    setCandidateActions((current) => ({
      ...current,
      [clusterId]: { creating: true },
    }));

    try {
      const response = await adminFetch(apiUrl("/projects/takeaway-candidates"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          signal_id: clusterId,
          signal_title: `Knowledge Brief: ${clean(brief.label) || "Supply / demand convergence"}`,
          signal_summary: clean(brief.brief),
          why_it_matters: clean(brief.why_it_matters),
          relevance_to_projects: takeawayMap,
          synthesized_insight: clean(brief.recommended_next_step),
          final_reflection:
            "Created from Knowledge convergence review. Human review is required before this becomes project memory or action.",
          subscription_project_links: matchedProjects.map((project) => ({
            project_id: project.project_id,
            enabled: true,
            source: "knowledge_convergence",
          })),
          verification_metadata: {
            knowledge_convergence: true,
            verification_status: "knowledge_convergence_review_candidate",
            confidence_label: clean(brief.confidence) || "review",
            allowed_downstream_actions: ["project_takeaway_candidate"],
            blocked_downstream_actions: ["low_risk_action_candidate", "strong_recommendation"],
            convergence_brief_id: clusterId,
            supply_read: clean(brief.supply_read),
            demand_read: clean(brief.demand_read),
            why_paired: clean(brief.why_paired || brief.brief),
            review_boundary: clean(brief.review_boundary),
            review_readiness: brief.review_readiness || {},
            quality: brief.quality || buildKnowledgeQuality(brief),
            evidence_profile: brief.evidence_profile || {},
            project_relevance: brief.project_relevance || {},
          },
        }),
      });
      const data = (await response.json().catch(() => null)) as { created_count?: number; detail?: string; message?: string } | null;
      if (!response.ok) {
        throw new Error(data?.detail || data?.message || "Failed to create Project Takeaway candidate.");
      }
      const createdCount = data?.created_count ?? 0;
      if (createdCount > 0) {
        setExistingCandidates((current) => ({
          ...current,
          [clusterId]: matchedProjects.slice(0, createdCount).map((project) => ({
              signal_id: clusterId,
              status: "candidate",
              candidate_source: "knowledge_convergence",
              project_id: project.project_id,
              project_name: project.project_name || project.project_id,
              verification_metadata: {
                knowledge_convergence: true,
                convergence_brief_id: clusterId,
                supply_read: clean(brief.supply_read),
                demand_read: clean(brief.demand_read),
                why_paired: clean(brief.why_paired || brief.brief),
                review_boundary: clean(brief.review_boundary),
                verification_status: "knowledge_convergence_review_candidate",
                allowed_downstream_actions: ["project_takeaway_candidate"],
                blocked_downstream_actions: ["low_risk_action_candidate", "strong_recommendation"],
              },
            })),
        }));
      }
      setCandidateActions((current) => ({
        ...current,
        [clusterId]: {
          created: createdCount > 0,
          message:
            createdCount > 0
              ? `Created ${createdCount} Review Inbox candidate(s).`
              : "No candidate was created because no registered project matched this brief.",
        },
      }));
    } catch (error) {
      setCandidateActions((current) => ({
        ...current,
        [clusterId]: {
          error: error instanceof Error ? error.message : "Failed to create Project Takeaway candidate.",
        },
      }));
    }
  }

  return (
    <AppContainer style={knowledgeShellStyle}>
      <KnowledgeHeader
        loading={loading}
        topicCount={summary.strategic_topic_count ?? 0}
        briefCount={summary.convergence_brief_count ?? 0}
        blockedActionRate={percent(summary.blocked_action_rate)}
        healthLabel={healthLabel}
      />

      {loading ? (
        <KnowledgeSection eyebrow="Load state" title="Loading synthesis">
          <div style={mutedTextStyle}>Requesting /radar/strategic-synthesis from the configured API.</div>
        </KnowledgeSection>
      ) : errorMessage ? (
        <KnowledgeSection eyebrow="Load state" title="Synthesis unavailable">
          <div style={errorTextStyle}>{errorMessage}</div>
        </KnowledgeSection>
      ) : (
        <div style={{ display: "grid", gap: "18px" }}>
          <section style={summaryGridStyle}>
            <Metric label="Topics" value={String(summary.strategic_topic_count ?? 0)} />
            <Metric label="Agent Watch" value={String(summary.agent_watch_count ?? 0)} />
            <Metric label="Friction" value={String(summary.friction_signal_count ?? 0)} />
            <Metric label="Briefs" value={String(summary.convergence_brief_count ?? 0)} />
            <Metric label="Review Records" value={String(summary.review_record_count ?? 0)} />
            <Metric label="Manual Source" value={String(summary.manual_source_event_count ?? 0)} />
            <Metric label="Blocked Actions" value={percent(summary.blocked_action_rate)} />
            <Metric label="State" value={healthLabel} />
          </section>

          <KnowledgeSection eyebrow="Strategic map" title="Strategic topics">
            {topics.length ? (
              <div style={topicGridStyle}>
                {topics.map((item, index) => (
                  <article key={`${item.topic || "topic"}-${index}`} style={panelStyle}>
                    <div style={smallCapsStyle}>#{index + 1}</div>
                    <h2 style={itemTitleStyle}>{clean(item.topic) || "General AI"}</h2>
                    <div style={scoreStyle}>Score {Math.round((item.score || 0) * 100) / 100}</div>
                    <p style={bodyTextStyle}>{clean(item.reason) || "This topic is visible in the current radar synthesis."}</p>
                  </article>
                ))}
              </div>
            ) : (
              <div style={mutedTextStyle}>No strategic topics are available from the current radar cycle.</div>
            )}
          </KnowledgeSection>

          <KnowledgeSection eyebrow="Quality layer" title="Knowledge quality interpretation">
            <div style={qualitySummaryGridStyle}>
              <Metric label="Strong Fit" value={String(qualitySummary.strongFit)} />
              <Metric label="Review Caution" value={String(qualitySummary.reviewCaution)} />
              <Metric label="Thin Fit" value={String(qualitySummary.thinFit)} />
              <Metric label="No Project Fit" value={String(qualitySummary.noProjectFit)} />
              <Metric label="In Review" value={String(qualitySummary.inReview)} />
            </div>
            <div style={qualityInterpretationStyle}>
              <strong>{qualitySummary.title}</strong>
              <span>{qualitySummary.guidance}</span>
            </div>
            {qualitySummary.topBrief ? (
              <div style={qualityTopBriefStyle}>
                <div>
                  <div style={smallCapsStyle}>Highest priority brief</div>
                  <strong>{clean(qualitySummary.topBrief.label) || "Untitled convergence brief"}</strong>
                  <p style={bodyTextStyle}>{buildKnowledgeReviewPosture(qualitySummary.topBrief, buildKnowledgeQuality(qualitySummary.topBrief))}</p>
                </div>
                <Link
                  href={`/knowledge/detail?id=${encodeURIComponent(clean(qualitySummary.topBrief.cluster_id))}`}
                  style={detailLinkStyle}
                >
                  Open Brief Detail
                </Link>
              </div>
            ) : null}
          </KnowledgeSection>

          <KnowledgeSection eyebrow="Freshness" title="Convergence freshness">
            <FreshnessDeltaPanel
              freshness={freshnessState}
              briefCount={convergenceBriefs.length}
              agentCount={summary.agent_watch_count ?? 0}
              frictionCount={summary.friction_signal_count ?? 0}
            />
          </KnowledgeSection>

          <KnowledgeSection eyebrow="Review candidates" title="Convergence briefs">
            {convergenceBriefs.length ? (
              <div style={{ display: "grid", gap: "14px" }}>
                <div style={briefToolbarStyle}>
                  <div style={briefFilterRowStyle}>
                    {briefFilterOptions.map((filter) => (
                      <button
                        key={filter.value}
                        type="button"
                        onClick={() => setBriefFilter(filter.value)}
                        style={briefFilter === filter.value ? activeFilterButtonStyle : filterButtonStyle}
                      >
                        {filter.label} ({filter.count})
                      </button>
                    ))}
                  </div>
                  <label style={sortControlStyle}>
                    <span style={smallCapsStyle}>Sort</span>
                    <select value={briefSort} onChange={(event) => setBriefSort(event.target.value as BriefSort)} style={selectStyle}>
                      <option value="score">Review Queue Candidate</option>
                      <option value="readiness">Readiness</option>
                      <option value="project_match">Project Match</option>
                      <option value="evidence_density">Evidence Density</option>
                    </select>
                    {visibleConvergenceBriefs.length <= 1 ? (
                      <span style={sortHintStyle}>Need 2+ briefs to visibly reorder</span>
                    ) : null}
                  </label>
                </div>
                {visibleConvergenceBriefs.length ? (
                  <div style={briefGridStyle}>
                    {visibleConvergenceBriefs.map((brief, index) => (
                      <ConvergenceBriefCard
                        key={brief.cluster_id || `${brief.label || "brief"}-${index}`}
                        brief={brief}
                        freshness={freshnessState?.deltas[briefFreshnessId(brief, index)]}
                        actionState={candidateActions[clean(brief.cluster_id)] || {}}
                        existingCandidates={existingCandidates[clean(brief.cluster_id)] || []}
                        onCreateCandidate={handleCreateCandidate}
                      />
                    ))}
                  </div>
                ) : (
                  <div style={mutedPanelStyle}>
                    No convergence briefs match this filter. Switch back to All or choose another readiness view.
                  </div>
                )}
              </div>
            ) : (
              <div style={mutedPanelStyle}>
                No convergence briefs are available yet. Filters, Brief Detail, and Send to Review Inbox appear after at
                least one brief is generated. This usually means Agent Watch or Friction Signals are missing, or the
                current backend has not loaded the latest convergence synthesis code.
              </div>
            )}
          </KnowledgeSection>

          <KnowledgeSection eyebrow="Signal pairing" title="Supply / demand">
            <p style={bodyTextStyle}>
              {payload?.supply_demand?.interpretation ||
                "Compare supply-side agent movement against demand-side friction before creating project actions."}
            </p>
            <div style={twoColumnStyle}>
              <HighlightColumn title="Agent Watch" items={agentHighlights} detailPath="/agent-watch/detail" />
              <HighlightColumn title="Friction Signals" items={frictionHighlights} detailPath="/friction-signals/detail" />
            </div>
          </KnowledgeSection>

          <KnowledgeSection eyebrow="Review loop" title="Review quality">
            <div style={threeColumnStyle}>
              <ListPanel title="Achieved" items={ops.achieved || []} />
              <ListPanel title="Gaps" items={ops.gaps || []} />
              <ListPanel title="Next Focus" items={ops.next_focus || []} />
            </div>
          </KnowledgeSection>
        </div>
      )}
    </AppContainer>
  );
}

function KnowledgeHeader({
  loading,
  topicCount,
  briefCount,
  blockedActionRate,
  healthLabel,
}: {
  loading: boolean;
  topicCount: number;
  briefCount: number;
  blockedActionRate: string;
  healthLabel: string;
}) {
  return (
    <section style={knowledgeHeroStyle}>
      <div style={{ minWidth: 0 }}>
        <div style={eyebrowStyle}>Knowledge Synthesis</div>
        <h1 style={knowledgeHeroTitleStyle}>Convergence layer for strategic judgment.</h1>
        <p style={knowledgeHeroDescriptionStyle}>
          Knowledge connects radar topics, Agent Watch movement, Friction Signals, project fit, and review quality before anything becomes a durable takeaway.
        </p>
        <div style={quickActionRowStyle}>
          <QuickAction href="/radar" label="Open Radar" icon={Radar} />
          <QuickAction href="/workspace/projects/review" label="Open Review" icon={BookOpenCheck} />
          <QuickAction href="/workspace/projects/trajectory" label="Open Trajectory" icon={GitBranch} />
        </div>
      </div>

      <div style={knowledgeHeroPanelStyle}>
        <div style={summaryHeaderStyle}>
          <BrainCircuit size={18} aria-hidden="true" />
          <span>{loading ? "Loading synthesis" : "Synthesis ready"}</span>
        </div>
        <div style={heroMetricGridStyle}>
          <HeroMetric label="Topics" value={String(topicCount)} />
          <HeroMetric label="Briefs" value={String(briefCount)} />
          <HeroMetric label="Blocked actions" value={blockedActionRate} />
          <HeroMetric label="State" value={healthLabel} />
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

function HeroMetric({ label, value }: { label: string; value: string }) {
  return (
    <div style={heroMetricStyle}>
      <div style={heroMetricValueStyle}>{value}</div>
      <div style={heroMetricLabelStyle}>{label}</div>
    </div>
  );
}

function KnowledgeSection({
  eyebrow,
  title,
  children,
  marginBottom = "0",
}: {
  eyebrow: string;
  title: string;
  children: ReactNode;
  marginBottom?: string;
}) {
  return (
    <section style={{ ...knowledgeSectionStyle, marginBottom }}>
      <div style={sectionHeaderStyle}>
        <div style={eyebrowStyle}>{eyebrow}</div>
        <h2 style={sectionTitleStyle}>{title}</h2>
      </div>
      {children}
    </section>
  );
}

function githubRepoUrlFromTitle(title: string) {
  const match = title.match(/(?:^|\s)([A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+)(?:\s|$)/);
  return match ? `https://github.com/${match[1]}` : "";
}

function detailEntityId(item: Highlight | undefined, detailPath: string) {
  const explicitId = clean(item?.entity_id) || clean(item?.url) || clean(item?.canonical_url) || clean(item?.repo_url);
  if (explicitId) return explicitId;

  const title = clean(item?.title);
  if (!title) return "";

  if (detailPath.includes("/agent-watch/")) {
    return githubRepoUrlFromTitle(title);
  }

  if (detailPath.includes("/friction-signals/")) {
    return title;
  }

  return "";
}

function detailHref(item: Highlight | undefined, detailPath: string) {
  const entityId = detailEntityId(item, detailPath);
  return entityId ? `${detailPath}?entity_id=${encodeURIComponent(entityId)}` : "";
}

function buildProjectTakeawayMap(brief: ConvergenceBrief) {
  const existing = brief.project_relevance?.project_takeaway_map || {};
  if (Object.keys(existing).length) return existing;
  const matchedProjects = brief.project_relevance?.matched_projects || [];
  const sharedTopics = brief.shared_topics?.filter(Boolean).join(", ") || "supply-demand convergence";
  return matchedProjects.reduce<Record<string, string>>((acc, project) => {
    const key = clean(project.project_name) || clean(project.project_id);
    if (!key) return acc;
    acc[key] = `Review ${clean(brief.label) || "this convergence brief"} for ${key}. Shared topics: ${sharedTopics}.`;
    return acc;
  }, {});
}

function indexKnowledgeCandidates(items: ExistingCandidate[]) {
  return items.reduce<Record<string, ExistingCandidate[]>>((acc, item) => {
    const metadata = item.verification_metadata || {};
    const isKnowledgeCandidate =
      metadata.knowledge_convergence ||
      item.candidate_source === "knowledge_convergence" ||
      clean(item.signal_id).startsWith("knowledge-convergence-");
    const key = clean(metadata.convergence_brief_id) || clean(item.signal_id);
    if (!isKnowledgeCandidate || !key) return acc;
    acc[key] = [...(acc[key] || []), item];
    return acc;
  }, {});
}

function formatCandidateStatus(items: ExistingCandidate[]) {
  if (!items.length) return "";
  const statusCounts = items.reduce<Record<string, number>>((acc, item) => {
    const key = clean(item.review_outcome) || clean(item.status) || "candidate";
    acc[key] = (acc[key] || 0) + 1;
    return acc;
  }, {});
  return Object.entries(statusCounts)
    .map(([status, count]) => `${formatLabel(status)} ${count}`)
    .join(", ");
}

function shortBriefId(value?: string) {
  const id = clean(value);
  if (!id) return "";
  return id.replace(/^knowledge-convergence-/, "").slice(0, 8);
}

function formatLabel(value?: string) {
  return clean(value)
    .replaceAll("_", " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function briefReadinessRank(brief: ConvergenceBrief) {
  const status = clean(brief.review_readiness?.status).toLowerCase();
  if (status === "ready_for_project_review") return 3;
  if (status === "watch_first") return 2;
  if (status === "needs_more_evidence") return 1;
  return 0;
}

function briefQualityScore(brief: ConvergenceBrief) {
  return brief.quality?.score ?? brief.evidence_profile?.quality_score ?? brief.score ?? 0;
}

function briefEvidenceDensity(brief: ConvergenceBrief) {
  const sourceCount = brief.evidence_profile?.source_count ?? brief.review_readiness?.source_count ?? 0;
  const sharedTopicCount = brief.evidence_profile?.shared_topic_count ?? brief.shared_topics?.length ?? 0;
  const projectCount = brief.project_relevance?.match_count ?? brief.project_relevance?.matched_projects?.length ?? 0;
  const strategicOverlap = brief.evidence_profile?.strategic_topic_overlap_count ?? 0;
  return sourceCount * 20 + sharedTopicCount * 12 + projectCount * 14 + strategicOverlap * 8;
}

function briefQualityBand(brief: ConvergenceBrief) {
  const score = briefQualityScore(brief);
  if (score >= 70) return "strong_fit";
  if (score >= 45) return "review_caution";
  return "thin_fit";
}

function briefMatchesFilter(
  brief: ConvergenceBrief,
  filter: BriefFilter,
  existingCandidates: Record<string, ExistingCandidate[]>
) {
  if (filter === "all") return true;
  if (filter === "strong_fit") return briefQualityBand(brief) === "strong_fit";
  if (filter === "review_caution") return briefQualityBand(brief) === "review_caution";
  if (filter === "thin_fit") return briefQualityBand(brief) === "thin_fit";
  const status = clean(brief.review_readiness?.status).toLowerCase();
  const alreadyInReview = (existingCandidates[clean(brief.cluster_id)] || []).length > 0;
  if (filter === "ready") return status === "ready_for_project_review" && !alreadyInReview;
  if (filter === "watch") return status === "watch_first";
  if (filter === "needs_evidence") return status === "needs_more_evidence";
  if (filter === "has_project") return (brief.project_relevance?.matched_projects || []).length > 0;
  if (filter === "in_review") return alreadyInReview;
  return true;
}

function countBriefs(
  briefs: ConvergenceBrief[],
  filter: BriefFilter,
  existingCandidates: Record<string, ExistingCandidate[]>
) {
  return briefs.filter((brief) => briefMatchesFilter(brief, filter, existingCandidates)).length;
}

function compareBriefs(left: ConvergenceBrief, right: ConvergenceBrief, sort: BriefSort) {
  if (sort === "readiness") {
    return briefReadinessRank(right) - briefReadinessRank(left) || (right.score || 0) - (left.score || 0);
  }
  if (sort === "project_match") {
    return (
      (right.project_relevance?.matched_projects || []).length -
        (left.project_relevance?.matched_projects || []).length ||
      (right.score || 0) - (left.score || 0)
    );
  }
  if (sort === "evidence_density") {
    return briefEvidenceDensity(right) - briefEvidenceDensity(left) || briefQualityScore(right) - briefQualityScore(left);
  }
  return briefQualityScore(right) - briefQualityScore(left);
}

function buildKnowledgeQuality(brief: ConvergenceBrief) {
  const fallbackFactors = buildKnowledgeQualityFactors(brief);
  if (brief.quality?.score !== undefined || brief.evidence_profile?.quality_score !== undefined) {
    const backendFactors = brief.quality?.factors || {};
    return {
      score: brief.quality?.score ?? brief.evidence_profile?.quality_score ?? 0,
      label: clean(brief.quality?.label) || clean(brief.evidence_profile?.quality_label) || "Review quality",
      reason: clean(brief.quality?.reason) || clean(brief.evidence_profile?.quality_reason) || "Quality factors recorded by synthesis.",
      recommendation: clean(brief.quality?.recommendation),
      factors: qualityFactorsFromRecord(backendFactors).length ? backendFactors : fallbackFactors,
    };
  }
  const sharedTopicCount = fallbackFactors.shared_topic_count || 0;
  const sourceCount = fallbackFactors.source_count || 0;
  const projectCount = fallbackFactors.project_match_count || 0;
  const strategicOverlap = fallbackFactors.strategic_overlap_count || 0;
  const score = Math.min(100, sourceCount * 20 + sharedTopicCount * 12 + projectCount * 18 + strategicOverlap * 10);
  const label = score >= 70 ? "Strong review candidate" : score >= 45 ? "Review with caution" : "Needs stronger evidence";
  const reason = [
    `${sourceCount} source${sourceCount === 1 ? "" : "s"}`,
    `${sharedTopicCount} shared topic${sharedTopicCount === 1 ? "" : "s"}`,
    `${projectCount} project match${projectCount === 1 ? "" : "es"}`,
    strategicOverlap ? `${strategicOverlap} strategic overlap${strategicOverlap === 1 ? "" : "s"}` : "",
  ].filter(Boolean).join(" / ");

  return { score, label, reason, recommendation: "", factors: fallbackFactors };
}

function buildKnowledgeReviewPosture(brief: ConvergenceBrief, quality: KnowledgeQuality) {
  const matchedProjects = brief.project_relevance?.matched_projects || [];
  const score = quality.score ?? 0;
  if (matchedProjects.length === 0) {
    return "Keep in Knowledge until a registered project match appears.";
  }
  if (score >= 70) {
    return "Ready for Review Inbox candidate creation; confirm project fit before any Project Takeaway decision.";
  }
  if (score >= 45) {
    return "Useful for Watch or review, but fit still needs human judgment before confirmation.";
  }
  return "Treat as weak convergence. Review only if the topic is strategically important.";
}

function buildKnowledgeCardVerdict({
  quality,
  canCreateCandidate,
  alreadyInReview,
}: {
  quality: KnowledgeQuality;
  canCreateCandidate: boolean;
  alreadyInReview: boolean;
}) {
  const score = quality.score ?? 0;

  if (alreadyInReview) {
    return {
      label: "In Review",
      reason: "Decision has moved to Review Inbox. Continue there with Confirm, Watch, or Reject.",
      actionLabel: "Already in Review Inbox",
      tone: "review",
    };
  }

  if (!canCreateCandidate) {
    return {
      label: "Watch - no project match",
      reason: "Keep this in Knowledge until a registered project match appears.",
      actionLabel: "Add Project Match First",
      tone: "watch",
    };
  }

  if (score >= 70) {
    return {
      label: "Ready for Review",
      reason: "Project fit is visible. Review Inbox should still confirm fit before downstream action.",
      actionLabel: "Send to Review Inbox",
      tone: "ready",
    };
  }

  if (score >= 45) {
    return {
      label: "Review with caution",
      reason: "Useful for Watch or project-fit review, but evidence limits should stay visible.",
      actionLabel: "Send to Review Inbox",
      tone: "caution",
    };
  }

  return {
    label: "Watch - evidence thin",
    reason: "Keep in Knowledge unless this weak convergence is strategically important enough for human review.",
    actionLabel: "Send to Review Inbox",
    tone: "watch",
  };
}

function buildKnowledgeQualityFactors(brief: ConvergenceBrief) {
  const sourceCount = brief.evidence_profile?.source_count ?? brief.review_readiness?.source_count ?? 0;
  const sharedTopicCount = brief.evidence_profile?.shared_topic_count ?? brief.shared_topics?.length ?? 0;
  const projectCount = brief.project_relevance?.match_count ?? brief.project_relevance?.matched_projects?.length ?? 0;
  const strategicOverlap = brief.evidence_profile?.strategic_topic_overlap_count ?? 0;
  const agentScore = brief.evidence_profile?.agent_watch_score ?? brief.agent_watch_item?.score ?? 0;
  const frictionScore = brief.evidence_profile?.friction_score ?? brief.friction_item?.score ?? 0;
  let penalty = 0;
  if (sourceCount < 2) penalty += 14;
  if (sharedTopicCount === 0) penalty += 16;
  if (projectCount === 0) penalty += 12;
  if (agentScore < 0.35 || frictionScore < 0.35) penalty += 8;
  return {
    source_count: sourceCount,
    shared_topic_count: sharedTopicCount,
    project_match_count: projectCount,
    strategic_overlap_count: strategicOverlap,
    evidence_score: Math.min(34, sourceCount * 10 + sharedTopicCount * 7),
    fit_score: Math.min(38, projectCount * 12),
    strategy_score: Math.min(12, strategicOverlap * 4),
    signal_score: Math.min(20, Math.round(((agentScore + frictionScore) / 2) * 20)),
    penalty,
  };
}

function qualityFactorsFromRecord(factors: Record<string, number>) {
  return [
    { label: "Evidence", value: factors.evidence_score },
    { label: "Fit", value: factors.fit_score },
    { label: "Strategy", value: factors.strategy_score },
    { label: "Signal", value: factors.signal_score },
    { label: "Penalty", value: factors.penalty },
  ].filter((item) => typeof item.value === "number");
}

function summarizeKnowledgeQuality(
  briefs: ConvergenceBrief[],
  existingCandidates: Record<string, ExistingCandidate[]>
) {
  const scored = briefs.map((brief) => ({
    brief,
    quality: buildKnowledgeQuality(brief),
    inReview: Boolean(existingCandidates[clean(brief.cluster_id)]?.length),
    projectCount: brief.project_relevance?.matched_projects?.length || 0,
  }));

  const strongFit = scored.filter((item) => (item.quality.score || 0) >= 70 && item.projectCount > 0).length;
  const reviewCaution = scored.filter((item) => {
    const score = item.quality.score || 0;
    return score >= 45 && score < 70 && item.projectCount > 0;
  }).length;
  const thinFit = scored.filter((item) => (item.quality.score || 0) < 45).length;
  const noProjectFit = scored.filter((item) => item.projectCount === 0).length;
  const inReview = scored.filter((item) => item.inReview).length;
  const topBrief = [...scored]
    .filter((item) => item.projectCount > 0 && !item.inReview)
    .sort((left, right) => (right.quality.score || 0) - (left.quality.score || 0))[0]?.brief;

  let title = "Knowledge is ready for triage";
  let guidance = "Use Strong Fit first, keep Thin Fit in Knowledge, and send only project-relevant briefs to Review Inbox.";
  if (!briefs.length) {
    title = "No convergence briefs yet";
    guidance = "Wait for Agent Watch and Friction Signals to produce paired supply-demand evidence before reviewing Knowledge.";
  } else if (strongFit > 0) {
    title = "Strong review candidates are available";
    guidance = "Start with Strong Fit briefs. Confirm project fit in Review Inbox before treating them as durable project memory.";
  } else if (reviewCaution > 0) {
    title = "Review with caution";
    guidance = "These briefs may be useful as Watch items, but they need stronger fit or evidence before confirmation.";
  } else if (noProjectFit === briefs.length) {
    title = "Project fit is missing";
    guidance = "Keep these briefs in Knowledge until a registered project match appears.";
  }

  return {
    strongFit,
    reviewCaution,
    thinFit,
    noProjectFit,
    inReview,
    title,
    guidance,
    topBrief,
  };
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div style={metricStyle}>
      <div style={smallCapsStyle}>{label}</div>
      <div style={metricValueStyle}>{value}</div>
    </div>
  );
}

function formatSnapshotTime(value: string) {
  if (!value) return "Not recorded";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function FreshnessDeltaPanel({
  freshness,
  briefCount,
  agentCount,
  frictionCount,
}: {
  freshness: FreshnessState | null;
  briefCount: number;
  agentCount: number;
  frictionCount: number;
}) {
  const title = freshness?.firstSnapshot
    ? "First local snapshot saved"
    : freshness
      ? `${freshness.newCount} new / ${freshness.changedCount} changed / ${freshness.repeatedCount} repeated`
      : "Waiting for convergence snapshot";
  const guidance = freshness?.firstSnapshot
    ? "This browser will start showing New / Changed / Repeated after the next Knowledge load."
    : freshness
      ? "Use this to decide whether the Top 5 deserves attention today. Repeated means it was already visible in your last browser view."
      : "Freshness appears after convergence briefs load.";

  return (
    <div style={freshnessPanelStyle}>
      <div>
        <div style={smallCapsStyle}>Freshness / Delta</div>
        <strong style={freshnessTitleStyle}>{title}</strong>
        <p style={bodyTextStyle}>{guidance}</p>
      </div>
      <div style={freshnessMetricGridStyle}>
        <Metric label="Top Briefs Shown" value={String(briefCount)} />
        <Metric label="New" value={String(freshness?.newCount ?? 0)} />
        <Metric label="Changed" value={String(freshness?.changedCount ?? 0)} />
        <Metric label="Repeated" value={String(freshness?.repeatedCount ?? 0)} />
        <Metric label="Dropped" value={String(freshness?.droppedCount ?? 0)} />
        <Metric label="Agent Inputs" value={String(agentCount)} />
        <Metric label="Friction Inputs" value={String(frictionCount)} />
        <Metric label="Previous View" value={formatSnapshotTime(freshness?.previousCapturedAt || "")} />
      </div>
      <p style={freshnessFootnoteStyle}>
        Delta is local to this browser and compares the current Top 5 snapshot with the previous browser-seen snapshot. It does not change evidence gates or Review Inbox eligibility.
      </p>
    </div>
  );
}

function HighlightColumn({ title, items, detailPath }: { title: string; items: Highlight[]; detailPath: string }) {
  return (
    <div style={columnStyle}>
      <h2 style={columnTitleStyle}>{title}</h2>
      {items.length ? (
        items.map((item, index) => {
          const href = detailHref(item, detailPath);
          return (
            <article key={`${item.title || title}-${index}`} style={highlightStyle}>
              <div style={smallCapsStyle}>{clean(item.source) || clean(item.type) || "source"}</div>
              <h3 style={highlightTitleStyle}>{clean(item.title) || "Untitled"}</h3>
              <p style={bodyTextStyle}>{clean(item.summary) || "No synthesis note available."}</p>
              {href ? (
                <Link href={href} style={linkStyle}>
                  Open Detail
                </Link>
              ) : null}
            </article>
          );
        })
      ) : (
        <div style={mutedTextStyle}>No highlights available.</div>
      )}
    </div>
  );
}

function FreshnessBadge({ freshness }: { freshness: BriefDeltaState }) {
  const label =
    freshness.status === "new"
      ? "New"
      : freshness.status === "changed"
        ? `Changed${typeof freshness.score_delta === "number" && freshness.score_delta !== 0 ? ` ${freshness.score_delta > 0 ? "+" : ""}${freshness.score_delta}` : ""}`
        : "Repeated";
  const style =
    freshness.status === "new"
      ? freshnessNewBadgeStyle
      : freshness.status === "changed"
        ? freshnessChangedBadgeStyle
        : freshnessRepeatedBadgeStyle;

  return <div style={style}>{label}</div>;
}

function ConvergenceBriefCard({
  brief,
  freshness,
  actionState,
  existingCandidates,
  onCreateCandidate,
}: {
  brief: ConvergenceBrief;
  freshness?: BriefDeltaState;
  actionState: CandidateActionState;
  existingCandidates: ExistingCandidate[];
  onCreateCandidate: (brief: ConvergenceBrief) => void;
}) {
  const agentHref = detailHref(brief.agent_watch_item, "/agent-watch/detail");
  const frictionHref = detailHref(brief.friction_item, "/friction-signals/detail");
  const sharedTopics = brief.shared_topics?.filter(Boolean) || [];
  const matchedProjects = brief.project_relevance?.matched_projects || [];
  const evidence = brief.evidence_profile;
  const quality = buildKnowledgeQuality(brief);
  const factors = buildKnowledgeQualityFactors(brief);
  const canCreateCandidate = matchedProjects.length > 0;
  const existingStatus = formatCandidateStatus(existingCandidates);
  const alreadyInReview = existingCandidates.length > 0;
  const candidateButtonDisabled = !canCreateCandidate || actionState.creating || alreadyInReview || actionState.created;
  const briefDetailHref = clean(brief.cluster_id)
    ? `/knowledge/detail?id=${encodeURIComponent(clean(brief.cluster_id))}`
    : "";
  const verdict = buildKnowledgeCardVerdict({ quality, canCreateCandidate, alreadyInReview });
  const supplyTitle = clean(brief.agent_watch_item?.title) || "No supply signal";
  const demandTitle = clean(brief.friction_item?.title) || "No demand pain";
  const visibleTopics = sharedTopics.slice(0, 4);
  const hiddenTopicCount = Math.max(0, sharedTopics.length - visibleTopics.length);
  const primaryActionLabel = actionState.creating
    ? "Creating..."
    : actionState.created
      ? "Created in Review Inbox"
      : verdict.actionLabel;

  return (
    <article style={briefCardStyle}>
      <div style={briefHeaderStyle}>
        <div>
          <div style={smallCapsStyle}>Convergence</div>
          <h2 style={briefTitleStyle}>{clean(brief.label) || "Supply / demand cluster"}</h2>
          {shortBriefId(brief.cluster_id) ? (
            <div style={briefIdStyle}>Brief {shortBriefId(brief.cluster_id)}</div>
          ) : null}
          {briefDetailHref ? (
            <Link href={briefDetailHref} style={inlineDetailLinkStyle}>
              Open Brief Detail
            </Link>
          ) : null}
        </div>
        <div style={headerBadgeColumnStyle}>
          {freshness ? <FreshnessBadge freshness={freshness} /> : null}
          <div style={briefScoreStyle}>
            <strong style={briefScoreNumberStyle}>{quality.score ?? 0}</strong>
            <span>/100</span>
          </div>
          <div style={confidenceStyle}>
            <span style={confidenceLabelStyle}>Pattern Confidence</span>
            <strong>{clean(brief.confidence) || "review"}</strong>
          </div>
          {alreadyInReview ? (
            <div style={inReviewHeaderBadgeStyle}>
              <span style={confidenceLabelStyle}>In Review</span>
              <strong>{existingStatus || "Candidate"}</strong>
            </div>
          ) : null}
        </div>
      </div>

      <div style={pairedSignalSummaryStyle}>
        <div style={pairedSignalHeaderStyle}>
          <div style={smallCapsStyle}>Paired Signals</div>
          <span style={pairedSignalHintStyle}>Supply meets demand</span>
        </div>
        <div style={pairedSignalGridStyle}>
          <SignalPairSummary label="Supply signal" title={supplyTitle} href={agentHref} />
          <SignalPairSummary label="Demand pain" title={demandTitle} href={frictionHref} />
        </div>
      </div>

      <div style={triageVerdictStyle}>
        <div style={smallCapsStyle}>Triage Verdict</div>
        <strong style={readinessLabelStyle}>{verdict.label}</strong>
        <p style={bodyTextStyle}>{verdict.reason}</p>
      </div>

      {sharedTopics.length ? (
        <div style={chipRowStyle}>
          {visibleTopics.map((topic) => (
            <span key={`${brief.cluster_id || brief.label}-${topic}`} style={topicChipStyle}>
              {topic}
            </span>
          ))}
          {hiddenTopicCount ? <span style={topicChipStyle}>+{hiddenTopicCount} more</span> : null}
        </div>
      ) : null}

      <div style={compactMetricGridStyle}>
        <EvidenceMetric label="Sources" value={String(evidence?.source_count ?? factors.source_count ?? 0)} />
        <EvidenceMetric label="Shared Topics" value={String(evidence?.shared_topic_count ?? factors.shared_topic_count ?? 0)} />
        <EvidenceMetric label="Project Fit" value={String(factors.project_match_count ?? 0)} />
        <EvidenceMetric label="Strategy" value={String(evidence?.strategic_topic_overlap_count ?? factors.strategic_overlap_count ?? 0)} />
        <EvidenceMetric label="Penalty" value={String(factors.penalty ?? 0)} />
      </div>

      <div style={projectMatchStyle}>
        <div style={smallCapsStyle}>Matched Projects</div>
        {matchedProjects.length ? (
          <div style={projectListStyle}>
            {matchedProjects.map((project) => (
              <div key={project.project_id || project.project_name} style={projectPillStyle}>
                <span>{clean(project.project_name) || clean(project.project_id) || "Project"}</span>
                <span style={projectMatchBadgeStyle}>{formatProjectMatchType(project)}</span>
                <span style={projectTopicStyle}>{formatProjectMatchPreview(project)}</span>
              </div>
            ))}
          </div>
        ) : (
          <p style={bodyTextStyle}>No project match yet. Keep this in Knowledge until the project fit is clearer.</p>
        )}
      </div>

      <div style={compactBoundaryStyle}>
        <div style={smallCapsStyle}>Action Boundary</div>
        <p style={bodyTextStyle}>
          Knowledge brief is review context only. It can prepare Review Inbox or Watch, but it does not create verified evidence or low-risk Action readiness by itself.
        </p>
        {alreadyInReview ? (
          <div style={existingCandidateStyle}>
            <div style={smallCapsStyle}>Review Inbox State</div>
            <strong>{existingStatus || "Already in Review Inbox"}</strong>
            <p style={bodyTextStyle}>
              This brief already has {existingCandidates.length} Review Inbox candidate
              {existingCandidates.length === 1 ? "" : "s"} across matched projects.
            </p>
          </div>
        ) : null}
      </div>

      <div style={candidateActionRowStyle}>
        <button
          type="button"
          onClick={() => onCreateCandidate(brief)}
          disabled={candidateButtonDisabled}
          style={{
            ...candidateButtonStyle,
            opacity: candidateButtonDisabled ? 0.65 : 1,
            cursor: candidateButtonDisabled ? "not-allowed" : "pointer",
          }}
        >
          {primaryActionLabel}
        </button>
        {briefDetailHref ? (
          <Link href={briefDetailHref} style={secondaryActionStyle}>
            Open Brief Detail
          </Link>
        ) : null}
        {canCreateCandidate || alreadyInReview ? (
          <Link href="/workspace/projects/review" style={secondaryActionStyle}>
            Open Review Inbox
          </Link>
        ) : null}
      </div>

      <details style={compactDetailsStyle}>
        <summary style={compactSummaryStyle}>Why watch / reasoning</summary>
        <p style={bodyTextStyle}>{clean(brief.brief) || "This cluster needs review before it becomes a product action."}</p>
        {clean(brief.why_it_matters) ? <p style={bodyTextStyle}>{clean(brief.why_it_matters)}</p> : null}
        <ConvergenceRationale brief={brief} />
      </details>

      {actionState.message ? (
        <div style={successPanelStyle}>
          <strong>{actionState.message}</strong>
          <span>Open Review Inbox or use the In Review filter to inspect the candidate state.</span>
        </div>
      ) : null}
      {actionState.error ? <div style={errorTextStyle}>{actionState.error}</div> : null}
    </article>
  );
}

function SignalPairSummary({ label, title, href }: { label: string; title: string; href: string }) {
  const content = (
    <>
      <span style={pairedSignalLabelStyle}>{label}</span>
      <strong style={pairedSignalTitleStyle}>{title}</strong>
      {href ? <span style={pairedSignalOpenStyle}>Open detail</span> : null}
    </>
  );

  if (!href) {
    return <div style={pairedSignalItemStyle}>{content}</div>;
  }

  return (
    <Link href={href} style={{ ...pairedSignalItemStyle, ...pairedSignalLinkStyle }}>
      {content}
    </Link>
  );
}

function EvidenceMetric({ label, value }: { label: string; value: string }) {
  return (
    <div style={evidenceMetricStyle}>
      <div style={smallCapsStyle}>{label}</div>
      <div style={evidenceValueStyle}>{value}</div>
    </div>
  );
}

function formatProjectMatchType(project: ProjectMatch) {
  if (project.match_type === "shared_topic") return "Shared topic";
  if (project.match_type === "context_overlap") return "Context fit";
  return "Project fit";
}

function formatProjectMatchPreview(project: ProjectMatch) {
  const shared = project.shared_topic_matches?.filter(Boolean) || [];
  const score = typeof project.score === "number" ? `score ${project.score}` : "";
  if (shared.length) return [`shared: ${shared.slice(0, 2).join(", ")}`, score].filter(Boolean).join(" / ");
  const context = project.context_matches?.filter(Boolean) || project.matched_topics?.filter(Boolean) || [];
  if (context.length) return [`context: ${context.slice(0, 2).join(", ")}`, score].filter(Boolean).join(" / ");
  return score || "Review fit";
}

function ConvergenceRationale({ brief }: { brief: ConvergenceBrief }) {
  const rows = [
    { label: "Supply read", value: clean(brief.supply_read) },
    { label: "Demand read", value: clean(brief.demand_read) },
    { label: "Why paired", value: clean(brief.why_paired || brief.brief) },
    { label: "Review boundary", value: clean(brief.review_boundary) },
  ].filter((row) => row.value);

  if (!rows.length) return null;

  return (
    <div style={rationaleGridStyle}>
      {rows.map((row) => (
        <div key={row.label} style={rationaleItemStyle}>
          <div style={smallCapsStyle}>{row.label}</div>
          <p style={bodyTextStyle}>{row.value}</p>
        </div>
      ))}
    </div>
  );
}

function ListPanel({ title, items }: { title: string; items: string[] }) {
  return (
    <div style={panelStyle}>
      <h2 style={columnTitleStyle}>{title}</h2>
      {items.length ? (
        <ul style={listStyle}>
          {items.map((item, index) => (
            <li key={`${title}-${index}`} style={listItemStyle}>
              {item}
            </li>
          ))}
        </ul>
      ) : (
        <div style={mutedTextStyle}>No current notes.</div>
      )}
    </div>
  );
}

const summaryGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 150px), 1fr))",
  gap: "12px",
} as const;

const knowledgeShellStyle = {
  paddingTop: "28px",
  color: "var(--app-page-fg)",
} as const;

const knowledgeHeroStyle = {
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

const knowledgeHeroTitleStyle = {
  margin: "10px 0 0",
  color: "var(--app-text-strong)",
  fontSize: "38px",
  fontWeight: 780,
  lineHeight: 1.08,
  maxWidth: "820px",
} as const;

const knowledgeHeroDescriptionStyle = {
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

const knowledgeHeroPanelStyle = {
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

const heroMetricGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
  gap: "10px",
  marginTop: "14px",
} as const;

const heroMetricStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  padding: "13px",
  minWidth: 0,
} as const;

const heroMetricValueStyle = {
  color: "var(--app-text-strong)",
  fontSize: "18px",
  fontWeight: 780,
  lineHeight: 1.2,
  overflowWrap: "anywhere" as const,
} as const;

const heroMetricLabelStyle = {
  marginTop: "7px",
  color: "var(--app-text-subtle)",
  fontSize: "12px",
  fontWeight: 720,
} as const;

const knowledgeSectionStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  padding: "18px",
  background: "var(--app-surface-bg)",
  boxShadow: "var(--app-surface-shadow)",
} as const;

const sectionHeaderStyle = {
  marginBottom: "14px",
} as const;

const sectionTitleStyle = {
  margin: "6px 0 0",
  color: "var(--app-text-strong)",
  fontSize: "22px",
  fontWeight: 760,
  lineHeight: 1.2,
} as const;

const metricStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  padding: "14px",
  minHeight: "82px",
} as const;

const metricValueStyle = {
  marginTop: "8px",
  color: "var(--app-text-strong)",
  fontSize: "22px",
  fontWeight: 800,
  overflowWrap: "anywhere" as const,
} as const;

const topicGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 220px), 1fr))",
  gap: "12px",
} as const;

const briefGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 320px), 1fr))",
  gap: "14px",
} as const;

const qualitySummaryGridStyle = {
  ...summaryGridStyle,
  marginBottom: "12px",
};

const qualityInterpretationStyle = {
  border: "1px solid var(--app-info-border)",
  borderRadius: "8px",
  background: "var(--app-info-bg)",
  color: "var(--app-info-fg)",
  padding: "12px",
  display: "grid",
  gap: "5px",
  fontSize: "14px",
  lineHeight: 1.6,
} as const;

const qualityTopBriefStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-secondary-action-bg)",
  padding: "12px",
  marginTop: "12px",
  display: "flex",
  justifyContent: "space-between",
  alignItems: "flex-start",
  gap: "12px",
  flexWrap: "wrap" as const,
};

const freshnessPanelStyle = {
  display: "grid",
  gap: "12px",
} as const;

const freshnessTitleStyle = {
  display: "block",
  color: "var(--app-text-strong)",
  fontSize: "18px",
  lineHeight: 1.25,
  marginTop: "5px",
} as const;

const freshnessMetricGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 130px), 1fr))",
  gap: "10px",
} as const;

const freshnessFootnoteStyle = {
  border: "1px solid var(--app-info-border)",
  borderRadius: "8px",
  background: "var(--app-info-bg)",
  color: "var(--app-info-fg)",
  padding: "10px 12px",
  fontSize: "13px",
  lineHeight: 1.5,
  margin: 0,
} as const;

const detailLinkStyle = {
  display: "inline-flex",
  alignItems: "center",
  minHeight: "36px",
  border: "1px solid var(--app-secondary-action-border)",
  borderRadius: "8px",
  background: "var(--app-secondary-action-bg)",
  color: "var(--app-text-strong)",
  padding: "0 12px",
  textDecoration: "none",
  fontSize: "13px",
  fontWeight: 800,
} as const;

const briefToolbarStyle = {
  display: "flex",
  justifyContent: "space-between",
  gap: "12px",
  alignItems: "center",
  flexWrap: "wrap",
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-bg)",
  padding: "12px",
} as const;

const briefFilterRowStyle = {
  display: "flex",
  gap: "8px",
  flexWrap: "wrap",
} as const;

const filterButtonStyle = {
  border: "1px solid var(--app-secondary-action-border)",
  borderRadius: "999px",
  background: "var(--app-secondary-action-bg)",
  color: "var(--app-text-muted)",
  padding: "7px 10px",
  fontSize: "12px",
  fontWeight: 800,
  cursor: "pointer",
} as const;

const activeFilterButtonStyle = {
  ...filterButtonStyle,
  border: "1px solid var(--app-info-border)",
  background: "var(--app-info-bg)",
  color: "var(--app-info-fg)",
} as const;

const sortControlStyle = {
  display: "flex",
  alignItems: "center",
  gap: "8px",
  flexWrap: "wrap",
} as const;

const sortHintStyle = {
  color: "var(--app-text-subtle)",
  fontSize: "12px",
  fontWeight: 700,
} as const;

const selectStyle = {
  border: "1px solid var(--app-secondary-action-border)",
  borderRadius: "8px",
  background: "var(--app-secondary-action-bg)",
  color: "var(--app-text-strong)",
  padding: "7px 9px",
  fontSize: "13px",
  fontWeight: 700,
} as const;

const mutedPanelStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  color: "var(--app-text-subtle)",
  padding: "14px",
  fontSize: "14px",
  lineHeight: 1.5,
} as const;

const twoColumnStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 280px), 1fr))",
  gap: "14px",
  marginTop: "14px",
} as const;

const threeColumnStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 220px), 1fr))",
  gap: "12px",
} as const;

const columnStyle = {
  display: "grid",
  gap: "10px",
  alignContent: "start",
} as const;

const panelStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  padding: "14px",
} as const;

const highlightStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  padding: "14px",
} as const;

const briefCardStyle = {
  border: "1px solid var(--app-surface-strong-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  padding: "16px",
  boxShadow: "var(--app-surface-shadow)",
} as const;

const briefHeaderStyle = {
  display: "flex",
  justifyContent: "space-between",
  gap: "12px",
  alignItems: "flex-start",
} as const;

const briefTitleStyle = {
  margin: "6px 0 0",
  color: "var(--app-text-strong)",
  fontSize: "19px",
  lineHeight: 1.25,
} as const;

const pairedSignalSummaryStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-bg)",
  padding: "12px",
  marginTop: "14px",
  display: "grid",
  gap: "10px",
} as const;

const pairedSignalHeaderStyle = {
  display: "flex",
  justifyContent: "space-between",
  gap: "10px",
  alignItems: "center",
  flexWrap: "wrap" as const,
} as const;

const pairedSignalHintStyle = {
  color: "var(--app-text-subtle)",
  fontSize: "12px",
  fontWeight: 800,
} as const;

const pairedSignalGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 180px), 1fr))",
  gap: "8px",
} as const;

const pairedSignalItemStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-secondary-action-bg)",
  padding: "10px",
  minHeight: "74px",
  display: "grid",
  alignContent: "start",
  gap: "5px",
  textDecoration: "none",
} as const;

const pairedSignalLinkStyle = {
  color: "inherit",
} as const;

const pairedSignalLabelStyle = {
  color: "var(--app-text-subtle)",
  fontSize: "11px",
  fontWeight: 900,
  textTransform: "uppercase" as const,
} as const;

const pairedSignalTitleStyle = {
  color: "var(--app-text-strong)",
  fontSize: "13px",
  lineHeight: 1.35,
  overflowWrap: "anywhere" as const,
} as const;

const pairedSignalOpenStyle = {
  color: "var(--app-info-fg)",
  fontSize: "12px",
  fontWeight: 800,
} as const;

const briefIdStyle = {
  marginTop: "5px",
  color: "var(--app-text-subtle)",
  fontSize: "12px",
  fontWeight: 800,
} as const;

const inlineDetailLinkStyle = {
  display: "inline-flex",
  marginTop: "7px",
  color: "var(--app-info-fg)",
  fontSize: "13px",
  fontWeight: 800,
  textDecoration: "none",
} as const;

const confidenceStyle = {
  border: "1px solid var(--app-info-border)",
  borderRadius: "999px",
  background: "var(--app-info-bg)",
  color: "var(--app-info-fg)",
  padding: "5px 10px",
  fontSize: "12px",
  fontWeight: 800,
  textTransform: "capitalize" as const,
  whiteSpace: "nowrap" as const,
  display: "grid",
  gap: "2px",
} as const;

const headerBadgeColumnStyle = {
  display: "grid",
  gap: "8px",
  justifyItems: "end",
} as const;

const freshnessBadgeBaseStyle = {
  borderRadius: "999px",
  padding: "5px 10px",
  fontSize: "12px",
  fontWeight: 900,
  whiteSpace: "nowrap" as const,
} as const;

const freshnessNewBadgeStyle = {
  ...freshnessBadgeBaseStyle,
  border: "1px solid var(--app-success-border)",
  background: "var(--app-success-bg)",
  color: "var(--app-success-fg)",
} as const;

const freshnessChangedBadgeStyle = {
  ...freshnessBadgeBaseStyle,
  border: "1px solid var(--app-warning-border)",
  background: "var(--app-warning-bg)",
  color: "var(--app-warning-fg)",
} as const;

const freshnessRepeatedBadgeStyle = {
  ...freshnessBadgeBaseStyle,
  border: "1px solid var(--app-surface-border)",
  background: "var(--app-surface-muted-bg)",
  color: "var(--app-text-muted)",
} as const;

const briefScoreStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-secondary-action-bg)",
  color: "var(--app-text-strong)",
  padding: "7px 10px",
  display: "inline-flex",
  alignItems: "baseline",
  gap: "2px",
  fontSize: "12px",
  fontWeight: 800,
  whiteSpace: "nowrap" as const,
} as const;

const briefScoreNumberStyle = {
  fontSize: "22px",
  lineHeight: 1,
  fontWeight: 900,
} as const;

const inReviewHeaderBadgeStyle = {
  border: "1px solid var(--app-success-border)",
  borderRadius: "999px",
  background: "var(--app-success-bg)",
  color: "var(--app-success-fg)",
  padding: "5px 10px",
  fontSize: "12px",
  fontWeight: 800,
  whiteSpace: "nowrap" as const,
  display: "grid",
  gap: "2px",
  textAlign: "right" as const,
} as const;

const confidenceLabelStyle = {
  color: "var(--app-info-fg)",
  fontSize: "10px",
  fontWeight: 900,
  textTransform: "uppercase" as const,
} as const;

const readinessLabelStyle = {
  marginTop: "5px",
  color: "var(--app-text-strong)",
  fontSize: "16px",
  fontWeight: 800,
} as const;

const triageVerdictStyle = {
  border: "1px solid var(--app-info-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  marginTop: "12px",
  padding: "12px",
  display: "grid",
  gap: "6px",
} as const;

const chipRowStyle = {
  display: "flex",
  gap: "8px",
  flexWrap: "wrap",
  marginTop: "12px",
} as const;

const topicChipStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "999px",
  background: "var(--app-surface-muted-bg)",
  color: "var(--app-text-muted)",
  padding: "5px 9px",
  fontSize: "12px",
  fontWeight: 700,
} as const;

const projectMatchStyle = {
  borderTop: "1px solid var(--app-surface-border)",
  marginTop: "14px",
  paddingTop: "12px",
} as const;

const projectListStyle = {
  display: "flex",
  gap: "8px",
  flexWrap: "wrap",
  marginTop: "10px",
} as const;

const projectPillStyle = {
  display: "inline-flex",
  alignItems: "center",
  gap: "8px",
  border: "1px solid var(--app-success-border)",
  borderRadius: "999px",
  background: "var(--app-success-bg)",
  color: "var(--app-success-fg)",
  padding: "6px 10px",
  fontSize: "12px",
  fontWeight: 800,
  maxWidth: "100%",
} as const;

const projectTopicStyle = {
  color: "var(--app-success-fg)",
  fontWeight: 600,
  overflowWrap: "anywhere" as const,
} as const;

const projectMatchBadgeStyle = {
  border: "1px solid var(--app-success-border)",
  borderRadius: "999px",
  background: "var(--app-success-bg)",
  color: "var(--app-success-fg)",
  padding: "3px 7px",
  fontSize: "12px",
  fontWeight: 900,
} as const;

const compactMetricGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))",
  gap: "8px",
  marginTop: "12px",
} as const;

const evidenceMetricStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-secondary-action-bg)",
  padding: "10px",
} as const;

const evidenceValueStyle = {
  marginTop: "5px",
  color: "var(--app-text-strong)",
  fontSize: "18px",
  fontWeight: 800,
} as const;

const rationaleGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))",
  gap: "10px",
  marginTop: "14px",
} as const;

const rationaleItemStyle = {
  border: "1px solid var(--app-success-border)",
  borderRadius: "8px",
  background: "var(--app-success-bg)",
  padding: "12px",
} as const;

const compactBoundaryStyle = {
  borderTop: "1px solid var(--app-surface-border)",
  marginTop: "14px",
  paddingTop: "12px",
} as const;

const existingCandidateStyle = {
  border: "1px solid var(--app-success-border)",
  borderRadius: "8px",
  background: "var(--app-success-bg)",
  color: "var(--app-success-fg)",
  marginTop: "12px",
  padding: "12px",
} as const;

const candidateActionRowStyle = {
  display: "flex",
  gap: "10px",
  flexWrap: "wrap",
  alignItems: "center",
  marginTop: "12px",
} as const;

const candidateButtonStyle = {
  border: "1px solid var(--app-primary-action-bg)",
  borderRadius: "8px",
  background: "var(--app-primary-action-bg)",
  color: "var(--app-primary-action-fg)",
  padding: "8px 12px",
  fontSize: "13px",
  fontWeight: 800,
} as const;

const secondaryActionStyle = {
  border: "1px solid var(--app-secondary-action-border)",
  borderRadius: "8px",
  background: "var(--app-secondary-action-bg)",
  color: "var(--app-text-strong)",
  padding: "8px 12px",
  fontSize: "13px",
  fontWeight: 800,
  textDecoration: "none",
} as const;

const compactDetailsStyle = {
  borderTop: "1px solid var(--app-surface-border)",
  marginTop: "12px",
  paddingTop: "10px",
} as const;

const compactSummaryStyle = {
  color: "var(--app-info-fg)",
  cursor: "pointer",
  fontSize: "13px",
  fontWeight: 800,
} as const;

const successPanelStyle = {
  display: "grid",
  gap: "4px",
  border: "1px solid var(--app-success-border)",
  borderRadius: "8px",
  background: "var(--app-success-bg)",
  color: "var(--app-success-fg)",
  marginTop: "12px",
  padding: "10px 12px",
  fontSize: "13px",
  lineHeight: 1.45,
} as const;

const smallCapsStyle = {
  color: "var(--app-text-subtle)",
  fontSize: "12px",
  fontWeight: 800,
  textTransform: "uppercase" as const,
  letterSpacing: "0",
} as const;

const itemTitleStyle = {
  margin: "8px 0",
  color: "var(--app-text-strong)",
  fontSize: "18px",
  lineHeight: 1.25,
} as const;

const columnTitleStyle = {
  margin: 0,
  color: "var(--app-text-strong)",
  fontSize: "17px",
  lineHeight: 1.25,
} as const;

const highlightTitleStyle = {
  margin: "6px 0",
  color: "var(--app-text-strong)",
  fontSize: "15px",
  lineHeight: 1.3,
} as const;

const scoreStyle = {
  display: "inline-flex",
  width: "fit-content",
  border: "1px solid var(--app-info-border)",
  borderRadius: "999px",
  background: "var(--app-info-bg)",
  color: "var(--app-info-fg)",
  padding: "4px 9px",
  fontSize: "12px",
  fontWeight: 800,
} as const;

const bodyTextStyle = {
  margin: "8px 0 0",
  color: "var(--app-text-muted)",
  fontSize: "14px",
  lineHeight: 1.55,
} as const;

const mutedTextStyle = {
  color: "var(--app-text-subtle)",
  fontSize: "14px",
  lineHeight: 1.5,
} as const;

const errorTextStyle = {
  color: "var(--app-danger-fg)",
  fontSize: "14px",
  lineHeight: 1.5,
} as const;

const linkStyle = {
  display: "inline-flex",
  marginTop: "10px",
  color: "var(--app-info-fg)",
  fontSize: "13px",
  fontWeight: 800,
  textDecoration: "none",
} as const;

const listStyle = {
  margin: "10px 0 0",
  paddingLeft: "18px",
  display: "grid",
  gap: "8px",
} as const;

const listItemStyle = {
  color: "var(--app-text-muted)",
  fontSize: "14px",
  lineHeight: 1.45,
} as const;
