"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";

import AppContainer from "@/components/AppContainer";
import PageHeader from "@/components/PageHeader";
import SectionCard from "@/components/SectionCard";
import VerificationGateNote from "@/components/VerificationGateNote";
import { apiUrl } from "@/lib/api";
import { adminFetch } from "@/lib/adminAuth";

type Highlight = {
  title?: string;
  summary?: string;
  url?: string;
  entity_id?: string;
  subtopic?: string;
  source?: string;
  score?: number;
};

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
};

type ExistingCandidate = {
  signal_id?: string;
  signal_title?: string;
  signal_summary?: string;
  takeaway?: string;
  why_it_matters?: string;
  synthesized_insight?: string;
  project_id?: string;
  project_name?: string;
  status?: string;
  review_outcome?: string;
  action_completed_at?: string;
  action_state?: string;
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
    verification_status?: string;
    allowed_downstream_actions?: string[];
    blocked_downstream_actions?: string[];
    quality?: KnowledgeQuality;
    review_readiness?: ConvergenceBrief["review_readiness"];
    evidence_profile?: ConvergenceBrief["evidence_profile"];
  };
};

function getCandidateDisplayStatus(item: ExistingCandidate) {
  const status = (item.status || "").toLowerCase();
  if (status === "action_completed" || item.action_completed_at || item.action_state === "completed") {
    return "action_completed";
  }
  return item.review_outcome || item.status;
}

type CandidateActionState = {
  creating?: boolean;
  created?: boolean;
  message?: string;
  error?: string;
};

type SynthesisPayload = {
  supply_demand?: {
    convergence_briefs?: ConvergenceBrief[];
  };
};

function clean(value?: string) {
  return value?.trim() || "";
}

function formatLabel(value?: string) {
  return clean(value)
    .replaceAll("_", " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function detailHref(item: Highlight | undefined, detailPath: string) {
  const entityId = clean(item?.entity_id) || clean(item?.url);
  return entityId ? `${detailPath}?entity_id=${encodeURIComponent(entityId)}` : "";
}

function scoreLabel(value?: number) {
  if (typeof value !== "number" || Number.isNaN(value)) return "n/a";
  return String(Math.round(value * 100) / 100);
}

function isKnowledgeCandidate(item: ExistingCandidate, id: string) {
  const metadata = item.verification_metadata || {};
  const key = clean(metadata.convergence_brief_id) || clean(item.signal_id);
  return (
    key === id &&
    Boolean(
      metadata.knowledge_convergence ||
        item.candidate_source === "knowledge_convergence" ||
        clean(item.signal_id).startsWith("knowledge-convergence-")
    )
  );
}

function formatProjectMatchType(project: ProjectMatch) {
  if (project.match_type === "shared_topic") return "Shared topic";
  if (project.match_type === "context_overlap") return "Context fit";
  return "Project fit";
}

function formatProjectMatchScore(project: ProjectMatch) {
  return typeof project.score === "number" ? `score ${project.score}` : "";
}

function formatProjectMatchReason(project: ProjectMatch) {
  if (project.reason && !project.reason.toLowerCase().startsWith("matches project context through")) {
    return project.reason;
  }
  const terms = project.context_matches?.filter(Boolean) || project.matched_topics?.filter(Boolean) || [];
  if (terms.length) return `Matched terms: ${terms.slice(0, 6).join(", ")}.`;
  return "Matched through project context.";
}

function candidateStatus(items: ExistingCandidate[]) {
  if (!items.length) return "Not in Review Inbox";
  const counts = items.reduce<Record<string, number>>((acc, item) => {
    const key = clean(item.review_outcome) || clean(item.status) || "candidate";
    acc[key] = (acc[key] || 0) + 1;
    return acc;
  }, {});
  return Object.entries(counts)
    .map(([status, count]) => `${formatLabel(status)} ${count}`)
    .join(", ");
}

function buildProjectTakeawayMap(brief: ConvergenceBrief) {
  const matchedProjects = brief.project_relevance?.matched_projects || [];
  const sharedTopics = brief.shared_topics?.filter(Boolean).join(", ") || "supply-demand convergence";
  return matchedProjects.reduce<Record<string, string>>((acc, project) => {
    const key = clean(project.project_name) || clean(project.project_id);
    if (!key) return acc;
    acc[key] = `Review ${clean(brief.label) || "this convergence brief"} for ${key}. Shared topics: ${sharedTopics}.`;
    return acc;
  }, {});
}

function buildKnowledgeQuality(brief: ConvergenceBrief): Required<KnowledgeQuality> {
  if (brief.quality?.score !== undefined || brief.evidence_profile?.quality_score !== undefined) {
    return {
      score: brief.quality?.score ?? brief.evidence_profile?.quality_score ?? 0,
      label: clean(brief.quality?.label) || clean(brief.evidence_profile?.quality_label) || "Review quality",
      reason: clean(brief.quality?.reason) || clean(brief.evidence_profile?.quality_reason) || "Quality factors recorded by synthesis.",
      recommendation: clean(brief.quality?.recommendation),
    };
  }

  const sharedTopicCount = brief.evidence_profile?.shared_topic_count ?? brief.shared_topics?.length ?? 0;
  const sourceCount = brief.evidence_profile?.source_count ?? brief.review_readiness?.source_count ?? 0;
  const projectCount = brief.project_relevance?.match_count ?? brief.project_relevance?.matched_projects?.length ?? 0;
  const strategicOverlap = brief.evidence_profile?.strategic_topic_overlap_count ?? 0;
  const score = Math.min(100, sourceCount * 20 + sharedTopicCount * 12 + projectCount * 18 + strategicOverlap * 10);
  const label = score >= 70 ? "Strong review candidate" : score >= 45 ? "Review with caution" : "Needs stronger evidence";
  const reason = [
    `${sourceCount} source${sourceCount === 1 ? "" : "s"}`,
    `${sharedTopicCount} shared topic${sharedTopicCount === 1 ? "" : "s"}`,
    `${projectCount} project match${projectCount === 1 ? "" : "es"}`,
    strategicOverlap ? `${strategicOverlap} strategic overlap${strategicOverlap === 1 ? "" : "s"}` : "",
  ].filter(Boolean).join(" / ");

  return { score, label, reason, recommendation: "" };
}

function buildKnowledgeQualityExplanation(brief: ConvergenceBrief, quality: Required<KnowledgeQuality>) {
  const sourceCount = brief.evidence_profile?.source_count ?? brief.review_readiness?.source_count ?? 0;
  const sharedTopicCount = brief.evidence_profile?.shared_topic_count ?? brief.shared_topics?.length ?? 0;
  const projectCount = brief.project_relevance?.match_count ?? brief.project_relevance?.matched_projects?.length ?? 0;
  const band =
    quality.score >= 70 && projectCount > 0
      ? "Strong Fit"
      : quality.score >= 45 && projectCount > 0
        ? "Review Caution"
        : projectCount === 0
          ? "No Project Fit"
          : "Thin Fit";
  return {
    band,
    reason: `${band}: ${sourceCount} source${sourceCount === 1 ? "" : "s"}, ${sharedTopicCount} shared topic${sharedTopicCount === 1 ? "" : "s"}, ${projectCount} project match${projectCount === 1 ? "" : "es"}.`,
    projectNeed: projectCount
      ? "This has project context; use Review Inbox to decide Confirm, Watch, or Reject."
      : "This needs clearer registered project topics, roadmap context, or project takeaway criteria before review handoff.",
  };
}

function buildFallbackBriefFromCandidates(id: string, items: ExistingCandidate[]): ConvergenceBrief | null {
  if (!items.length) return null;
  const first = items[0];
  const metadata = first.verification_metadata || {};
  const matchedProjects = items.map((item) => ({
    project_id: item.project_id,
    project_name: item.project_name || item.project_id,
    status: getCandidateDisplayStatus(item),
    match_type: "review_inbox_candidate",
  }));

  return {
    cluster_id: id,
    label: clean(first.signal_title) || "Knowledge convergence candidate",
    confidence: metadata.verification_status || "review",
    brief: clean(first.signal_summary) || clean(first.takeaway) || clean(metadata.why_paired),
    why_it_matters: clean(first.why_it_matters),
    recommended_next_step: clean(first.synthesized_insight) || "Continue review from the Review Inbox record.",
    supply_read: metadata.supply_read,
    demand_read: metadata.demand_read,
    why_paired: metadata.why_paired,
    review_boundary: metadata.review_boundary,
    action_gate: "human_review_required",
    quality: metadata.quality,
    review_readiness: metadata.review_readiness,
    evidence_profile: metadata.evidence_profile,
    project_relevance: {
      matched_projects: matchedProjects,
      match_count: matchedProjects.length,
    },
  };
}

export default function KnowledgeBriefDetailPage() {
  return (
    <Suspense fallback={<DetailSkeleton />}>
      <KnowledgeBriefDetailContent />
    </Suspense>
  );
}

function KnowledgeBriefDetailContent() {
  const searchParams = useSearchParams();
  const id = searchParams.get("id") || "";
  const [payload, setPayload] = useState<SynthesisPayload | null>(null);
  const [candidates, setCandidates] = useState<ExistingCandidate[]>([]);
  const [candidateAction, setCandidateAction] = useState<CandidateActionState>({});
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    let active = true;

    async function loadDetail() {
      if (!id) {
        setLoading(false);
        return;
      }
      setLoading(true);
      setErrorMessage("");
      try {
        const [synthesisResponse, candidatesResponse] = await Promise.all([
          adminFetch(apiUrl("/radar/strategic-synthesis"), { cache: "no-store" }),
          adminFetch(apiUrl("/projects/takeaway-candidates?include_confirmed=true&include_closed=true"), {
            cache: "no-store",
          }),
        ]);
        const synthesis = (await synthesisResponse.json().catch(() => null)) as SynthesisPayload | { detail?: string } | null;
        if (!synthesisResponse.ok) {
          throw new Error((synthesis as { detail?: string } | null)?.detail || "Knowledge brief detail is unavailable.");
        }
        const candidatePayload = (await candidatesResponse.json().catch(() => null)) as { items?: ExistingCandidate[] } | null;
        if (!active) return;
        setPayload(synthesis as SynthesisPayload);
        setCandidates((candidatePayload?.items || []).filter((item) => isKnowledgeCandidate(item, id)));
      } catch (error) {
        if (active) {
          setErrorMessage(error instanceof Error ? error.message : "Knowledge brief detail is unavailable.");
        }
      } finally {
        if (active) setLoading(false);
      }
    }

    void loadDetail();
    return () => {
      active = false;
    };
  }, [id]);

  const synthesisBrief = useMemo(
    () => (payload?.supply_demand?.convergence_briefs || []).find((item) => item.cluster_id === id),
    [id, payload?.supply_demand?.convergence_briefs]
  );
  const fallbackBrief = useMemo(() => buildFallbackBriefFromCandidates(id, candidates), [id, candidates]);
  const brief = synthesisBrief || fallbackBrief;

  if (!id) {
    return (
      <AppContainer>
        <PageHeader title="Knowledge Brief" description="Missing convergence brief id." />
        <Link href="/knowledge" style={secondaryLinkStyle}>
          Back to Knowledge
        </Link>
      </AppContainer>
    );
  }

  if (loading) return <DetailSkeleton />;

  if (errorMessage || !brief) {
    return (
      <AppContainer>
        <PageHeader title="Knowledge Brief" description={errorMessage || "This convergence brief was not found in the current synthesis."} />
        <Link href="/knowledge" style={secondaryLinkStyle}>
          Back to Knowledge
        </Link>
      </AppContainer>
    );
  }

  const currentBrief = brief;
  const agentHref = detailHref(currentBrief.agent_watch_item, "/agent-watch/detail");
  const frictionHref = detailHref(currentBrief.friction_item, "/friction-signals/detail");
  const matchedProjects = currentBrief.project_relevance?.matched_projects || [];
  const evidence = currentBrief.evidence_profile || {};
  const readiness = currentBrief.review_readiness || {};
  const quality = buildKnowledgeQuality(currentBrief);
  const qualityExplanation = buildKnowledgeQualityExplanation(currentBrief, quality);
  const canCreateCandidate = matchedProjects.length > 0;
  const alreadyInReview = candidates.length > 0 || candidateAction.created;

  async function handleCreateCandidate() {
    if (!currentBrief.cluster_id) return;
    const takeawayMap = buildProjectTakeawayMap(currentBrief);
    if (!matchedProjects.length || !Object.keys(takeawayMap).length) {
      setCandidateAction({ error: "No matched project is available for this convergence brief yet." });
      return;
    }

    setCandidateAction({ creating: true });
    try {
      const response = await adminFetch(apiUrl("/projects/takeaway-candidates"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          signal_id: currentBrief.cluster_id,
          signal_title: `Knowledge Brief: ${clean(currentBrief.label) || "Supply / demand convergence"}`,
          signal_summary: clean(currentBrief.brief),
          why_it_matters: clean(currentBrief.why_it_matters),
          relevance_to_projects: takeawayMap,
          synthesized_insight: clean(currentBrief.recommended_next_step),
          final_reflection:
            "Created from Knowledge convergence review detail. Human review is required before this becomes project memory or action.",
          subscription_project_links: matchedProjects.map((project) => ({
            project_id: project.project_id,
            enabled: true,
            source: "knowledge_convergence",
          })),
          verification_metadata: {
            knowledge_convergence: true,
            verification_status: "knowledge_convergence_review_candidate",
            confidence_label: clean(currentBrief.confidence) || "review",
            allowed_downstream_actions: ["project_takeaway_candidate"],
            blocked_downstream_actions: ["low_risk_action_candidate", "strong_recommendation"],
            convergence_brief_id: currentBrief.cluster_id,
            supply_read: clean(currentBrief.supply_read),
            demand_read: clean(currentBrief.demand_read),
            why_paired: clean(currentBrief.why_paired || currentBrief.brief),
            review_boundary: clean(currentBrief.review_boundary),
            review_readiness: currentBrief.review_readiness || {},
            quality: currentBrief.quality || buildKnowledgeQuality(currentBrief),
            evidence_profile: currentBrief.evidence_profile || {},
            project_relevance: currentBrief.project_relevance || {},
          },
        }),
      });
      const data = (await response.json().catch(() => null)) as { created_count?: number; detail?: string; message?: string } | null;
      if (!response.ok) {
        throw new Error(data?.detail || data?.message || "Failed to create Project Takeaway candidate.");
      }
      const createdCount = data?.created_count ?? 0;
      if (createdCount > 0) {
        setCandidates([
          {
            signal_id: currentBrief.cluster_id,
            status: "candidate",
            candidate_source: "knowledge_convergence",
            project_name: matchedProjects.map((project) => project.project_name || project.project_id).filter(Boolean).join(", "),
            verification_metadata: {
              knowledge_convergence: true,
              convergence_brief_id: currentBrief.cluster_id,
              supply_read: clean(currentBrief.supply_read),
              demand_read: clean(currentBrief.demand_read),
              why_paired: clean(currentBrief.why_paired || currentBrief.brief),
              review_boundary: clean(currentBrief.review_boundary),
              verification_status: "knowledge_convergence_review_candidate",
              allowed_downstream_actions: ["project_takeaway_candidate"],
              blocked_downstream_actions: ["low_risk_action_candidate", "strong_recommendation"],
            },
          },
        ]);
      }
      setCandidateAction({
        created: createdCount > 0,
        message:
          createdCount > 0
            ? `Created ${createdCount} Review Inbox candidate(s).`
            : "No candidate was created because no registered project matched this brief.",
      });
    } catch (error) {
      setCandidateAction({
        error: error instanceof Error ? error.message : "Failed to create Project Takeaway candidate.",
      });
    }
  }

  return (
    <AppContainer>
      <div style={backRowStyle}>
        <Link href="/knowledge" style={secondaryLinkStyle}>
          Back to Knowledge
        </Link>
        <Link href="/workspace/projects/review" style={secondaryLinkStyle}>
          Review Inbox
        </Link>
      </div>

      <PageHeader
        title={clean(currentBrief.label) || "Knowledge Brief"}
        description={
          clean(currentBrief.brief) ||
          (synthesisBrief ? "Supply and demand convergence detail." : "Loaded from Review Inbox candidate metadata.")
        }
      />

      <section style={summaryGridStyle}>
        <Metric label="Confidence" value={formatLabel(currentBrief.confidence) || "Review"} />
        <Metric label="Quality" value={`${quality.score}/100`} />
        <Metric label="Readiness" value={clean(readiness.label) || formatLabel(readiness.status) || "Review"} />
        <Metric label="Review State" value={candidateStatus(candidates)} />
      </section>

      <section style={actionPanelStyle}>
        <div>
          <div style={smallCapsStyle}>Human Review Gate</div>
          <strong style={actionTitleStyle}>
            {candidates.length ? "This brief is already in Review Inbox" : "Send this brief to Review Inbox"}
          </strong>
          <p style={bodyTextStyle}>
            Knowledge can prepare the candidate, but Review Inbox remains the place where you confirm, watch, act, reject, or dismiss.
          </p>
          {canCreateCandidate ? (
            <VerificationGateNote
              verification={{
                verification_status: "knowledge_convergence_review_candidate",
                knowledge_convergence: true,
                allowed_downstream_actions: ["project_takeaway_candidate"],
                blocked_downstream_actions: ["low_risk_action_candidate", "strong_recommendation"],
              }}
              style={{ marginTop: "10px" }}
            />
          ) : null}
        </div>
        <div style={actionRowStyle}>
          <button
            type="button"
            onClick={() => void handleCreateCandidate()}
            disabled={!canCreateCandidate || candidateAction.creating || alreadyInReview}
            style={{
              ...primaryButtonStyle,
              opacity: !canCreateCandidate || candidateAction.creating || alreadyInReview ? 0.65 : 1,
              cursor: !canCreateCandidate || candidateAction.creating || alreadyInReview ? "not-allowed" : "pointer",
            }}
          >
            {candidateAction.creating
              ? "Creating..."
              : alreadyInReview
                ? "Already in Review Inbox"
                : "Send to Review Inbox"}
          </button>
          <Link href="/workspace/projects/review" style={secondaryLinkStyle}>
            Open Review Inbox
          </Link>
        </div>
        {candidateAction.message ? <div style={successTextStyle}>{candidateAction.message}</div> : null}
        {candidateAction.error ? <div style={errorTextStyle}>{candidateAction.error}</div> : null}
      </section>

      <div style={{ display: "grid", gap: "16px", marginTop: "18px" }}>
        <SectionCard title="Review Decision Context">
          <p style={bodyTextStyle}>{clean(readiness.reason) || "Human review is required before this becomes project memory or action."}</p>
          <div style={decisionPathStyle}>
            <div style={smallCapsStyle}>Decision Path</div>
            <strong>Knowledge -&gt; Review Inbox -&gt; Confirm / Watch / Reject</strong>
            <p style={bodyTextStyle}>
              Confirm saves project fit. Watch preserves incomplete convergence. Action remains separate from this Knowledge handoff.
            </p>
          </div>
          <div style={qualityPanelStyle}>
            <div>
              <div style={smallCapsStyle}>Fit Quality</div>
              <strong style={qualityTitleStyle}>{quality.label}</strong>
            </div>
            <div style={qualityScoreStyle}>{quality.score}/100</div>
            <p style={qualityReasonStyle}>{quality.reason}</p>
            {quality.recommendation ? <p style={qualityRecommendationStyle}>{quality.recommendation}</p> : null}
            <div style={qualityExplanationStyle}>
              <span>{qualityExplanation.reason}</span>
              <strong>{qualityExplanation.projectNeed}</strong>
            </div>
          </div>
          <div style={chipRowStyle}>
            {(currentBrief.shared_topics || []).map((topic) => (
              <span key={topic} style={topicChipStyle}>
                {topic}
              </span>
            ))}
          </div>
          <p style={bodyTextStyle}>{clean(currentBrief.why_it_matters)}</p>
          <p style={bodyTextStyle}>{clean(currentBrief.recommended_next_step)}</p>
        </SectionCard>

        <SectionCard title="Supply / Demand Rationale">
          <div style={rationaleGridStyle}>
            <RationaleBlock label="Supply read" value={currentBrief.supply_read} />
            <RationaleBlock label="Demand read" value={currentBrief.demand_read} />
            <RationaleBlock label="Why paired" value={currentBrief.why_paired || currentBrief.brief} />
            <RationaleBlock label="Review boundary" value={currentBrief.review_boundary} />
          </div>
        </SectionCard>

        <section style={twoColumnStyle}>
          <LinkedItemCard title="Supply Signal" item={currentBrief.agent_watch_item} href={agentHref} />
          <LinkedItemCard title="Demand Signal" item={currentBrief.friction_item} href={frictionHref} />
        </section>

        <SectionCard title="Matched Projects">
          {matchedProjects.length ? (
            <div style={projectGridStyle}>
              {matchedProjects.map((project) => (
                <article key={project.project_id || project.project_name} style={panelStyle}>
                  <div style={smallCapsStyle}>{project.status || "project"}</div>
                  <h2 style={cardTitleStyle}>{project.project_name || project.project_id || "Project"}</h2>
                  <div style={matchTypeStyle}>
                    {[formatProjectMatchType(project), formatProjectMatchScore(project)].filter(Boolean).join(" / ")}
                  </div>
                  <p style={bodyTextStyle}>{formatProjectMatchReason(project)}</p>
                  {project.shared_topic_matches?.length ? (
                    <div style={matchGroupStyle}>
                      <span style={smallCapsStyle}>Shared Topic Match</span>
                      <span>{project.shared_topic_matches.join(", ")}</span>
                    </div>
                  ) : null}
                  {project.context_matches?.length ? (
                    <div style={matchGroupStyle}>
                      <span style={smallCapsStyle}>Supporting Context</span>
                      <span>{project.context_matches.slice(0, 6).join(", ")}</span>
                    </div>
                  ) : null}
                  {project.matched_topics?.length ? (
                    <div style={chipRowStyle}>
                      {project.matched_topics.map((topic) => (
                        <span key={`${project.project_id}-${topic}`} style={topicChipStyle}>
                          {topic}
                        </span>
                      ))}
                    </div>
                  ) : null}
                </article>
              ))}
            </div>
          ) : (
            <div style={mutedPanelStyle}>No matched project yet. Keep this brief in Knowledge until project fit is clearer.</div>
          )}
        </SectionCard>

        <SectionCard title="Evidence Profile">
          <section style={summaryGridStyle}>
            <Metric label="Sources" value={String(evidence.source_count ?? readiness.source_count ?? 0)} />
            <Metric label="Shared Topics" value={String(evidence.shared_topic_count ?? readiness.shared_topic_count ?? 0)} />
            <Metric label="Strategic Overlap" value={String(evidence.strategic_topic_overlap_count ?? 0)} />
            <Metric label="Project Matches" value={String(currentBrief.project_relevance?.match_count ?? matchedProjects.length)} />
          </section>
          <p style={bodyTextStyle}>{clean(evidence.support_note)}</p>
        </SectionCard>

        <SectionCard title="Review Inbox State">
          {candidates.length ? (
            <div style={candidateListStyle}>
              {candidates.map((candidate) => (
                <div key={`${candidate.project_id || "project"}-${candidate.signal_id || id}`} style={candidateStateStyle}>
                  <strong>{candidate.project_name || candidate.project_id || "Project"}</strong>
                  <span>{formatLabel(candidate.review_outcome || candidate.status || "candidate")}</span>
                  <span>{candidate.reviewed_at || candidate.saved_at || "No timestamp"}</span>
                </div>
              ))}
            </div>
          ) : (
            <div style={mutedPanelStyle}>This brief has not been sent to Review Inbox yet.</div>
          )}
        </SectionCard>
      </div>
    </AppContainer>
  );
}

function DetailSkeleton() {
  return (
    <AppContainer>
      <SectionCard title="Loading Knowledge Brief">
        <div style={bodyTextStyle}>Requesting the current strategic synthesis and Review Inbox state.</div>
      </SectionCard>
    </AppContainer>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div style={metricStyle}>
      <div style={smallCapsStyle}>{label}</div>
      <strong style={metricValueStyle}>{value}</strong>
    </div>
  );
}

function LinkedItemCard({ title, item, href }: { title: string; item?: Highlight; href: string }) {
  return (
    <article style={panelStyle}>
      <div style={smallCapsStyle}>{title}</div>
      <h2 style={cardTitleStyle}>{clean(item?.title) || "No linked item"}</h2>
      <p style={bodyTextStyle}>{clean(item?.summary) || "No synthesis note available."}</p>
      <div style={metaRowStyle}>
        {item?.source ? <span>{item.source}</span> : null}
        {item?.subtopic ? <span>{item.subtopic}</span> : null}
        {typeof item?.score === "number" ? <span>Score {scoreLabel(item.score)}</span> : null}
      </div>
      {href ? (
        <Link href={href} style={primaryLinkStyle}>
          Open Detail
        </Link>
      ) : null}
    </article>
  );
}

function RationaleBlock({ label, value }: { label: string; value?: string }) {
  return (
    <div style={rationaleItemStyle}>
      <div style={smallCapsStyle}>{label}</div>
      <p style={bodyTextStyle}>{clean(value) || "No rationale available for this brief yet."}</p>
    </div>
  );
}

const backRowStyle = {
  display: "flex",
  gap: "10px",
  flexWrap: "wrap",
  marginBottom: "14px",
} as const;

const summaryGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))",
  gap: "12px",
} as const;

const twoColumnStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
  gap: "14px",
} as const;

const rationaleGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
  gap: "12px",
} as const;

const rationaleItemStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  padding: "12px 14px",
} as const;

const projectGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
  gap: "12px",
} as const;

const metricStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-bg)",
  padding: "13px",
} as const;

const metricValueStyle = {
  display: "block",
  marginTop: "7px",
  color: "var(--app-text-strong)",
  fontSize: "18px",
  lineHeight: 1.25,
} as const;

const panelStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-bg)",
  padding: "14px",
} as const;

const actionPanelStyle = {
  display: "flex",
  justifyContent: "space-between",
  gap: "14px",
  alignItems: "center",
  flexWrap: "wrap",
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-bg)",
  marginTop: "16px",
  padding: "14px",
} as const;

const actionTitleStyle = {
  display: "block",
  marginTop: "6px",
  color: "var(--app-text-strong)",
  fontSize: "17px",
} as const;

const actionRowStyle = {
  display: "flex",
  gap: "10px",
  flexWrap: "wrap",
  alignItems: "center",
} as const;

const primaryButtonStyle = {
  border: "1px solid var(--app-primary-action-border)",
  borderRadius: "8px",
  background: "var(--app-primary-action-bg)",
  color: "var(--app-primary-action-fg)",
  padding: "8px 12px",
  fontSize: "13px",
  fontWeight: 800,
} as const;

const smallCapsStyle = {
  color: "var(--app-text-subtle)",
  fontSize: "12px",
  fontWeight: 800,
  textTransform: "uppercase" as const,
  letterSpacing: "0",
} as const;

const cardTitleStyle = {
  margin: "7px 0 0",
  color: "var(--app-text-strong)",
  fontSize: "17px",
  lineHeight: 1.3,
} as const;

const matchTypeStyle = {
  color: "var(--app-text-muted)",
  fontSize: "12px",
  fontWeight: 800,
  marginTop: "8px",
} as const;

const matchGroupStyle = {
  display: "grid",
  gap: "4px",
  color: "var(--app-text-muted)",
  fontSize: "13px",
  marginTop: "10px",
} as const;

const bodyTextStyle = {
  margin: "9px 0 0",
  color: "var(--app-text-muted)",
  fontSize: "14px",
  lineHeight: 1.55,
} as const;

const chipRowStyle = {
  display: "flex",
  gap: "8px",
  flexWrap: "wrap",
  marginTop: "12px",
} as const;

const topicChipStyle = {
  border: "1px solid var(--app-chip-border)",
  borderRadius: "999px",
  background: "var(--app-chip-bg)",
  color: "var(--app-chip-fg)",
  padding: "5px 9px",
  fontSize: "12px",
  fontWeight: 800,
} as const;

const qualityPanelStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  padding: "12px",
  marginTop: "12px",
  display: "grid",
  gridTemplateColumns: "minmax(0, 1fr) auto",
  gap: "8px",
  alignItems: "start",
} as const;

const decisionPathStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  padding: "12px",
  marginTop: "12px",
  display: "grid",
  gap: "6px",
  color: "var(--app-text-muted)",
} as const;

const qualityTitleStyle = {
  display: "block",
  color: "var(--app-info-fg)",
  fontSize: "14px",
  lineHeight: 1.35,
  marginTop: "4px",
} as const;

const qualityScoreStyle = {
  border: "1px solid var(--app-info-border)",
  borderRadius: "999px",
  background: "var(--app-info-bg)",
  color: "var(--app-info-fg)",
  padding: "6px 10px",
  fontSize: "12px",
  fontWeight: 900,
} as const;

const qualityReasonStyle = {
  gridColumn: "1 / -1",
  color: "var(--app-text-muted)",
  fontSize: "14px",
  lineHeight: 1.55,
  margin: "9px 0 0",
} as const;

const qualityRecommendationStyle = {
  gridColumn: "1 / -1",
  color: "var(--app-info-fg)",
  fontSize: "14px",
  fontWeight: 800,
  lineHeight: 1.55,
  margin: "9px 0 0",
} as const;

const qualityExplanationStyle = {
  gridColumn: "1 / -1",
  border: "1px solid var(--app-info-border)",
  borderRadius: "8px",
  background: "var(--app-info-bg)",
  color: "var(--app-info-fg)",
  padding: "9px 10px",
  display: "grid",
  gap: "5px",
  fontSize: "13px",
  lineHeight: 1.5,
} as const;

const metaRowStyle = {
  display: "flex",
  gap: "8px",
  flexWrap: "wrap",
  marginTop: "10px",
  color: "var(--app-text-subtle)",
  fontSize: "12px",
  fontWeight: 700,
} as const;

const primaryLinkStyle = {
  display: "inline-flex",
  marginTop: "12px",
  color: "var(--app-info-fg)",
  fontSize: "13px",
  fontWeight: 800,
  textDecoration: "none",
} as const;

const secondaryLinkStyle = {
  border: "1px solid var(--app-secondary-action-border)",
  borderRadius: "8px",
  background: "var(--app-secondary-action-bg)",
  color: "var(--app-secondary-action-fg)",
  padding: "8px 12px",
  fontSize: "13px",
  fontWeight: 800,
  textDecoration: "none",
} as const;

const mutedPanelStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  color: "var(--app-text-muted)",
  padding: "14px",
  fontSize: "14px",
  lineHeight: 1.5,
} as const;

const successTextStyle = {
  width: "100%",
  color: "var(--app-success-fg)",
  fontSize: "13px",
  fontWeight: 800,
} as const;

const errorTextStyle = {
  width: "100%",
  color: "var(--app-danger-fg)",
  fontSize: "13px",
  fontWeight: 800,
} as const;

const candidateListStyle = {
  display: "grid",
  gap: "8px",
} as const;

const candidateStateStyle = {
  display: "grid",
  gridTemplateColumns: "minmax(140px, 1fr) auto auto",
  gap: "10px",
  alignItems: "center",
  border: "1px solid var(--app-success-border)",
  borderRadius: "8px",
  background: "var(--app-success-bg)",
  color: "var(--app-success-fg)",
  padding: "10px",
  fontSize: "13px",
} as const;
