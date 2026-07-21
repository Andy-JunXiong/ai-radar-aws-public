import type { JudgmentStage } from "./types";

export const judgmentFlowStages: JudgmentStage[] = [
  {
    id: "signal-collect",
    trackLabel: "Signal",
    stageLabel: "Signal: collect",
    subLabel: "collect",
    gateLabel: "provenance captured",
    gateKind: "system",
    whatHappens:
      "The collector picks up Anthropic's Agent Skills announcement and persists it as a raw signal record. No interpretation yet: only provenance, scoring, and operational metadata.",
    stateDiff: {
      signal_id: "sig_2025_claude_skills_announce",
      headline: "Anthropic releases Claude Skills as a new agent capability format",
      source: "anthropic.com/news/skills",
      source_type: "official_blog",
      raw_score: 0.7,
      subscription_priority: "high",
      captured_at: "2025-10-16T08:30:00Z",
      processing_tier: "fast_path",
    },
    designDecision:
      "Signals are append-only observation records. Later stages can correct interpretation, but they do not rewrite the raw signal; that audit trail is what makes later calibration possible.",
  },
  {
    id: "insight-extract",
    trackLabel: "Insight",
    stageLabel: "Insight: extract",
    subLabel: "extract",
    gateLabel: "claim isolated",
    gateKind: "system",
    whatHappens:
      "The Insight layer extracts an evidence-bounded claim and records what still needs support. The claim is useful, but it is not yet allowed to behave like settled project intelligence.",
    stateDiff: {
      stage: "insight.extract",
      claim: "Skills is a packaging format for agent capabilities",
      claim_type: "product_announcement",
      evidence_status: "single_source",
      supporting_signal_count: 1,
      verification_status: "needs_review",
      allowed_downstream_actions: ["watch", "project_takeaway_candidate"],
      blocked_downstream_actions: ["action_without_review"],
    },
    designDecision:
      "Official-source authority is valuable but not the same as broad support. The system can preserve the claim and prepare it for review without letting one fluent source become an automatic action.",
  },
  {
    id: "insight-verify",
    trackLabel: "Insight",
    stageLabel: "Insight: verify",
    subLabel: "verify",
    gateLabel: "support improved",
    gateKind: "system",
    whatHappens:
      "A second external discussion signal is matched to the same claim cluster. Support improves, and Reflection activates in parallel as context, but the private note still does not count as evidence.",
    stateDiff: {
      stage: "insight.verify",
      supporting_signal_count: 2,
      supporting_sources: ["anthropic.com/news/skills", "news.ycombinator.com"],
      verification_status: "supported",
      confidence_label: "medium",
      blocked_downstream_actions: ["auto_action"],
    },
    reflectionEvent: {
      type: "manual_note",
      location: "private_github_repo",
      contentSummary: "Skills makes me reconsider ai-pm-skills positioning",
      feedsIntoEvidence: false,
      feedsIntoContext: true,
    },
    designDecision:
      "Reflection can inform judgment, but it never promotes verification status. Personal interpretation is allowed to shape context; only external source evidence can improve claim support.",
  },
  {
    id: "knowledge-cluster",
    trackLabel: "Knowledge",
    stageLabel: "Knowledge: synthesize",
    subLabel: "cluster",
    gateLabel: "project relevance shaped",
    gateKind: "system",
    whatHappens:
      "The supported claim is merged into the agent capability packaging topic cluster. Knowledge synthesis turns the item into strategic context while keeping verification metadata visible.",
    stateDiff: {
      stage: "knowledge",
      topic_cluster: "agent_capability_packaging",
      cluster_signals_count: 7,
      strategic_interpretation: {
        text: "Capability packaging format is a 2025-2026 main thread",
        author: "operator",
        confidence: "directional",
      },
      project_relevance: ["ai-radar-aws", "ai-pm-skills"],
    },
    designDecision:
      "Knowledge is not just topic clustering. The system surfaces structure and evidence-aware context; the operator writes the judgment. That separation keeps the layer useful as a thinking tool rather than an answer engine.",
  },
  {
    id: "project-review",
    trackLabel: "Project",
    stageLabel: "Project: review",
    subLabel: "review",
    gateLabel: "human review",
    gateKind: "human",
    whatHappens:
      "The Project Engine creates a Project Takeaway candidate, but does not execute it. A human review gate decides whether it becomes Confirm, Watch, Action, Reject, or Dismiss.",
    stateDiff: {
      stage: "project",
      candidate_status: "candidate",
      proposed_takeaway: "Evaluate whether ai-pm-skills should adapt to the Skills format",
      review_gate: "human_required",
      available_outcomes: ["confirm", "watch", "action", "reject", "dismiss"],
      operator_decision: "action",
      calibration_event: {
        system_recommendation: "action",
        operator_decision: "action",
        agreement: true,
        logged_at: "2025-10-17T09:15:00Z",
      },
    },
    designDecision:
      "Auto-promoting high-confidence candidates was rejected. A short human review is cheaper than a polluted project memory. Calibration events let the system earn trust over time instead of bypassing review.",
  },
];
