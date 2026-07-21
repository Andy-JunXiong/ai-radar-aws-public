export type GuidanceEntry = {
  stateIdentifier: string;
  stateLabel: string;
  stateLabelZh: string;
  appliesWhen: string[];
  appliesWhenZh: string[];
  nextActions: string[];
  nextActionsZh: string[];
  notAllowed: string[];
  notAllowedZh: string[];
  governingSources: string[];
  keywords: string[];
};

export const guidanceEntries: GuidanceEntry[] = [
  {
    stateIdentifier: "signal.status.saved_for_later_explanation",
    stateLabel: "Save for Later meaning",
    stateLabelZh: "Save for Later meaning",
    appliesWhen: [
      "The operator asks what Save for Later means on a signal.",
      "The signal is not low-value enough to reject, but it should not consume current review or completion attention.",
    ],
    appliesWhenZh: [
      "The operator asks what Save for Later means on a signal.",
      "The signal is not low-value enough to reject, but it should not consume current review or completion attention.",
    ],
    nextActions: [
      "Use Save for Later when the signal may be useful later but is not urgent or strong enough for current analysis.",
      "Select one or more save reasons so future review can understand why it was kept.",
      "Saved means revisit later; it does not mean analyzed, completed, verified, or added to Workspace.",
      "When the signal becomes relevant again, reopen it from Saved and choose Generate Insight, Mark Processed, Reject, or completion based on the new context.",
    ],
    nextActionsZh: [
      "Use Save for Later when the signal may be useful later but is not urgent or strong enough for current analysis.",
      "Select one or more save reasons so future review can understand why it was kept.",
      "Saved means revisit later; it does not mean analyzed, completed, verified, or added to Workspace.",
      "When the signal becomes relevant again, reopen it from Saved and choose Generate Insight, Mark Processed, Reject, or completion based on the new context.",
    ],
    notAllowed: [
      "Do not treat Saved as a completed review.",
      "Do not treat Saved as evidence or verification.",
      "Do not use Save for Later for signals that are clearly low value now; use Reject instead.",
    ],
    notAllowedZh: [
      "Do not treat Saved as a completed review.",
      "Do not treat Saved as evidence or verification.",
      "Do not use Save for Later for signals that are clearly low value now; use Reject instead.",
    ],
    governingSources: [
      "frontend/app/signals/page.tsx",
      "frontend/app/signals/detail/SignalDetailClient.tsx",
      "docs/adr/0006-operator-guidance-layer.md",
    ],
    keywords: [
      "save for later",
      "saved",
      "save reason",
      "revisit",
      "later",
    ],
  },
  {
    stateIdentifier: "signal.bookmark.starred_explanation",
    stateLabel: "Starred signal meaning",
    stateLabelZh: "Starred signal meaning",
    appliesWhen: [
      "The operator asks what Starred means on a signal.",
      "The operator wants to mark a signal for quick return without changing workflow status.",
    ],
    appliesWhenZh: [
      "The operator asks what Starred means on a signal.",
      "The operator wants to mark a signal for quick return without changing workflow status.",
    ],
    nextActions: [
      "Use Starred as a lightweight bookmark when you are mid-review and want to find the signal again quickly.",
      "Starred does not change Pending, Saved, Analyzed, Completed, or Rejected status.",
      "Use the Starred filter on the Signal Timeline to return to bookmarked signals.",
      "Use Save for Later instead when the workflow decision is to pause the signal for future review.",
    ],
    nextActionsZh: [
      "Use Starred as a lightweight bookmark when you are mid-review and want to find the signal again quickly.",
      "Starred does not change Pending, Saved, Analyzed, Completed, or Rejected status.",
      "Use the Starred filter on the Signal Timeline to return to bookmarked signals.",
      "Use Save for Later instead when the workflow decision is to pause the signal for future review.",
    ],
    notAllowed: [
      "Do not treat Starred as a workflow decision.",
      "Do not treat Starred as saved for later, analyzed, completed, verified, or added to Workspace.",
      "Do not use Starred to bypass review or evidence gates.",
    ],
    notAllowedZh: [
      "Do not treat Starred as a workflow decision.",
      "Do not treat Starred as saved for later, analyzed, completed, verified, or added to Workspace.",
      "Do not use Starred to bypass review or evidence gates.",
    ],
    governingSources: [
      "frontend/app/signals/page.tsx",
      "frontend/app/signals/detail/SignalDetailClient.tsx",
      "backend/app/routes/signals.py",
    ],
    keywords: [
      "star",
      "starred",
      "bookmark",
      "quick return",
      "find again",
    ],
  },
  {
    stateIdentifier: "signal.workflow.completion_workspace_gate_explanation",
    stateLabel: "Completion / Workspace gate explanation",
    stateLabelZh: "Completion / Workspace gate explanation",
    appliesWhen: [
      "The operator asks why completion / Workspace requires a useful completion note and allowed evidence or verification gates.",
      "A signal may be useful as context, but may not yet be safe to preserve as durable Workspace memory.",
    ],
    appliesWhenZh: [
      "The operator asks why completion / Workspace requires a useful completion note and allowed evidence or verification gates.",
      "A signal may be useful as context, but may not yet be safe to preserve as durable Workspace memory.",
    ],
    nextActions: [
      "Read this as two gates, not one button: the note must contain a useful judgment, and the evidence state must allow downstream use.",
      "The completion note gate asks whether you added real interpretation, decision context, or project relevance instead of copying the source.",
      "The evidence / verification gate asks whether the claim is supported enough, whether blocked_downstream_actions exist, and whether the signal should remain Watch-only.",
      "If the note is useful but the evidence is weak, prefer Watch, Save for Later, or cautious context instead of Workspace completion.",
      "Use Workspace completion only when the signal is useful enough to become durable project memory.",
    ],
    nextActionsZh: [
      "Read this as two gates, not one button: the note must contain a useful judgment, and the evidence state must allow downstream use.",
      "The completion note gate asks whether you added real interpretation, decision context, or project relevance instead of copying the source.",
      "The evidence / verification gate asks whether the claim is supported enough, whether blocked_downstream_actions exist, and whether the signal should remain Watch-only.",
      "If the note is useful but the evidence is weak, prefer Watch, Save for Later, or cautious context instead of Workspace completion.",
      "Use Workspace completion only when the signal is useful enough to become durable project memory.",
    ],
    notAllowed: [
      "Do not treat a nice completion note as proof that the external claim is true.",
      "Do not use Workspace completion to bypass verification or blocked downstream actions.",
      "Do not complete every interesting signal; completion is for reusable memory, not ordinary reading history.",
    ],
    notAllowedZh: [
      "Do not treat a nice completion note as proof that the external claim is true.",
      "Do not use Workspace completion to bypass verification or blocked downstream actions.",
      "Do not complete every interesting signal; completion is for reusable memory, not ordinary reading history.",
    ],
    governingSources: [
      "AGENTS.md#Intelligence-Quality-Boundaries",
      "frontend/app/signals/detail/SignalDetailClient.tsx",
      "docs/adr/0006-operator-guidance-layer.md",
    ],
    keywords: [
      "completion note",
      "workspace",
      "completion / workspace",
      "evidence",
      "verification gate",
    ],
  },
  {
    stateIdentifier: "signal.workflow.end_to_end",
    stateLabel: "Signal review workflow from intake to terminal states",
    stateLabelZh: "Signal review workflow from intake to terminal states",
    appliesWhen: [
      "The operator is on Signals or Signal Detail and wants to understand the whole flow.",
      "A signal may be pending, saved, analyzed, rejected, completed, or routed into Review Inbox.",
      "The operator needs to know what each branch means before choosing the next action.",
    ],
    appliesWhenZh: [
      "The operator is on Signals or Signal Detail and wants to understand the whole flow.",
      "A signal may be pending, saved, analyzed, rejected, completed, or routed into Review Inbox.",
      "The operator needs to know what each branch means before choosing the next action.",
    ],
    nextActions: [
      "Start at Pending: decide whether the signal is worth more review now.",
      "Use Reject when the signal is reviewed and low value for the current work. Rejected locks downstream actions unless editing is explicitly enabled.",
      "Use Save for Later when the signal may matter later but should not consume current review attention.",
      "Use Generate Insight or Generate with Claude when the signal is worth analysis and needs structured insight.",
      "Use Mark Processed when the signal has been reviewed enough for the current pass but is not being completed into Workspace.",
      "Use completion / Workspace paths only when there is a useful completion note and the relevant evidence or verification gates allow the downstream use.",
      "Use Final Takeaway Confirmation when a Completion Note is ready to become Andy-confirmed wording against an immutable Review Bundle snapshot.",
      "Use Send Final Takeaway to Review after confirmation when the confirmed_final_takeaway provider should create a Project Takeaway candidate for Review Inbox.",
      "In Review Inbox, Final Takeaway Handoff is a provenance label; Manual Override can still appear when the ordinary Project Takeaway gate was blocked.",
      "The confirmed_final_takeaway provider preserves verification gates; if the ordinary gate is blocked, an explicit Final Takeaway override is required before handoff.",
    ],
    nextActionsZh: [
      "Start at Pending: decide whether the signal is worth more review now.",
      "Use Reject when the signal is reviewed and low value for the current work. Rejected locks downstream actions unless editing is explicitly enabled.",
      "Use Save for Later when the signal may matter later but should not consume current review attention.",
      "Use Generate Insight or Generate with Claude when the signal is worth analysis and needs structured insight.",
      "Use Mark Processed when the signal has been reviewed enough for the current pass but is not being completed into Workspace.",
      "Use completion / Workspace paths only when there is a useful completion note and the relevant evidence or verification gates allow the downstream use.",
      "Use Final Takeaway Confirmation when a Completion Note is ready to become Andy-confirmed wording against an immutable Review Bundle snapshot.",
      "Use Send Final Takeaway to Review after confirmation when the confirmed_final_takeaway provider should create a Project Takeaway candidate for Review Inbox.",
      "In Review Inbox, Final Takeaway Handoff is a provenance label; Manual Override can still appear when the ordinary Project Takeaway gate was blocked.",
      "The confirmed_final_takeaway provider preserves verification gates; if the ordinary gate is blocked, an explicit Final Takeaway override is required before handoff.",
    ],
    notAllowed: [
      "Do not treat a generated insight as verified evidence unless verification metadata supports that use.",
      "Do not continue downstream actions from rejected signals without explicit editing confirmation.",
      "Do not use Project Takeaway or Action paths to bypass blocked_downstream_actions.",
      "Do not treat confirmed_final_takeaway as low-risk Action evidence; it is a Review Inbox handoff source.",
      "Do not read the Final Takeaway Handoff chip as gate approval; it only explains the candidate origin.",
      "Do not treat Save for Later, Mark Processed, Reject, and Completed as the same kind of endpoint.",
    ],
    notAllowedZh: [
      "Do not treat a generated insight as verified evidence unless verification metadata supports that use.",
      "Do not continue downstream actions from rejected signals without explicit editing confirmation.",
      "Do not use Project Takeaway or Action paths to bypass blocked_downstream_actions.",
      "Do not treat confirmed_final_takeaway as low-risk Action evidence; it is a Review Inbox handoff source.",
      "Do not read the Final Takeaway Handoff chip as gate approval; it only explains the candidate origin.",
      "Do not treat Save for Later, Mark Processed, Reject, and Completed as the same kind of endpoint.",
    ],
    governingSources: [
      "AGENTS.md#Intelligence-Quality-Boundaries",
      "frontend/app/signals/page.tsx",
      "frontend/app/signals/detail/SignalDetailClient.tsx",
      "docs/adr/0006-operator-guidance-layer.md",
    ],
    keywords: [
      "signal workflow",
      "signal flow",
      "signal",
      "workflow",
      "flow",
      "process",
      "branch",
      "pending",
      "saved",
      "analyzed",
      "processed",
      "rejected",
      "completed",
      "completion note",
      "final takeaway",
      "review bundle",
      "snapshot",
      "confirm final takeaway",
      "reject",
      "save",
      "processed",
    ],
  },
  {
    stateIdentifier: "project_takeaway.candidate_created_pending_review",
    stateLabel: "Project Takeaway candidate is ready for Review Inbox",
    stateLabelZh: "Project Takeaway candidate is ready for Review Inbox",
    appliesWhen: [
      "A Signal Detail or Manual Detail flow has created a Project Takeaway candidate.",
      "The operator needs to know where to continue review after candidate creation.",
      "The candidate still needs human review before it becomes durable project intelligence or an Action path.",
    ],
    appliesWhenZh: [
      "A Signal Detail or Manual Detail flow has created a Project Takeaway candidate.",
      "The operator needs to know where to continue review after candidate creation.",
      "The candidate still needs human review before it becomes durable project intelligence or an Action path.",
    ],
    nextActions: [
      "Open the Review Inbox and find the candidate linked to the current signal or project.",
      "Inspect project fit, evidence note, verification status, and blocked downstream actions before choosing an outcome.",
      "Use Confirm only when the project fit is clear and the gate does not block the relevant downstream path.",
      "Use Watch when the candidate is promising but evidence, project fit, or action eligibility is still incomplete.",
      "Use Reject, Dismiss, or the explicit override path only when the review reason is clear and auditable.",
    ],
    nextActionsZh: [
      "Open the Review Inbox and find the candidate linked to the current signal or project.",
      "Inspect project fit, evidence note, verification status, and blocked downstream actions before choosing an outcome.",
      "Use Confirm only when the project fit is clear and the gate does not block the relevant downstream path.",
      "Use Watch when the candidate is promising but evidence, project fit, or action eligibility is still incomplete.",
      "Use Reject, Dismiss, or the explicit override path only when the review reason is clear and auditable.",
    ],
    notAllowed: [
      "Do not treat candidate creation as confirmation.",
      "Do not use ordinary Confirm or Action paths to bypass blocked_downstream_actions.",
      "Do not treat a Project Takeaway candidate as verified evidence unless verification metadata supports that use.",
    ],
    notAllowedZh: [
      "Do not treat candidate creation as confirmation.",
      "Do not use ordinary Confirm or Action paths to bypass blocked_downstream_actions.",
      "Do not treat a Project Takeaway candidate as verified evidence unless verification metadata supports that use.",
    ],
    governingSources: [
      "AGENTS.md#Intelligence-Quality-Boundaries",
      "backend/app/services/project_takeaway_constants.py",
      "frontend/app/workspace/projects/review/page.tsx",
      "docs/adr/0006-operator-guidance-layer.md",
    ],
    keywords: [
      "project takeaway",
      "create candidate",
      "created candidate",
      "candidate created",
      "review inbox",
      "confirm candidate",
      "signal candidate",
    ],
  },
  {
    stateIdentifier: "project_review.reasoning_assessment_advisory",
    stateLabel: "Reasoning Assessment Advisory",
    stateLabelZh: "Reasoning Assessment Advisory",
    appliesWhen: [
      "Project Review Inbox shows a Reasoning Assessment Advisory on a pending candidate.",
      "The operator asks whether the candidate conclusion is stronger than the recorded claim and evidence packet.",
      "The operator needs a reviewer-only prompt for the original insight, load-bearing claims, warrant, and counter-conclusion risk.",
    ],
    appliesWhenZh: [
      "Project Review Inbox shows a Reasoning Assessment Advisory on a pending candidate.",
      "The operator asks whether the candidate conclusion is stronger than the recorded claim and evidence packet.",
      "The operator needs a reviewer-only prompt for the original insight, load-bearing claims, warrant, and counter-conclusion risk.",
    ],
    nextActions: [
      "Use the advisory as a reviewer-only prompt, not as a verdict.",
      "Inspect the original insight / takeaway beside the load-bearing packet, then state the warrant that connects the evidence to the proposed takeaway.",
      "Use Composition Bridge to name the composed conclusion and inspect the extra inference load between packet facts and the candidate takeaway, including Application Mapping Load when one packet is being applied to several projects or modules.",
      "Treat Packet Integrity Check as a referential consistency warning, such as stale, misattached, or wrong-signal evidence; inspect it before relying on the packet. When it appears, the composed conclusion is collapsed until packet integrity is reviewed, and the expanded text remains marked unverified pending packet integrity review.",
      "Use Framing Checklist to check benchmark caveats, artifact/evidence boundaries, precise capability lists, scope wording, and producer provenance before accepting a polished framing.",
      "Run the counter-conclusion check as a reviewer answer, not a system answer: mark Yes / No / Unclear on whether the same evidence also supports an opposite conclusion, incompatible conclusion, weaker conclusion, Watch posture, or no Project Takeaway.",
      "Use Generate Counter-Check when you want an LLM counter-check draft; after one exists, Regenerate Counter-Check replaces the persisted reviewer-advisory draft while keeping the final decision with the reviewer.",
      "If the warrant is missing or underdetermined, prefer Watch, Reject, or an explicit reviewer note before Confirm or Action.",
      "The advisory does not change verification_status, the Project Takeaway gate, blocked_downstream_actions, or Action eligibility.",
    ],
    nextActionsZh: [
      "Use the advisory as a reviewer-only prompt, not as a verdict.",
      "Inspect the original insight / takeaway beside the load-bearing packet, then state the warrant that connects the evidence to the proposed takeaway.",
      "Use Composition Bridge to name the composed conclusion and inspect the extra inference load between packet facts and the candidate takeaway, including Application Mapping Load when one packet is being applied to several projects or modules.",
      "Treat Packet Integrity Check as a referential consistency warning, such as stale, misattached, or wrong-signal evidence; inspect it before relying on the packet. When it appears, the composed conclusion is collapsed until packet integrity is reviewed, and the expanded text remains marked unverified pending packet integrity review.",
      "Use Framing Checklist to check benchmark caveats, artifact/evidence boundaries, precise capability lists, scope wording, and producer provenance before accepting a polished framing.",
      "Run the counter-conclusion check as a reviewer answer, not a system answer: mark Yes / No / Unclear on whether the same evidence also supports an opposite conclusion, incompatible conclusion, weaker conclusion, Watch posture, or no Project Takeaway.",
      "Use Generate Counter-Check when you want an LLM counter-check draft; after one exists, Regenerate Counter-Check replaces the persisted reviewer-advisory draft while keeping the final decision with the reviewer.",
      "If the warrant is missing or underdetermined, prefer Watch, Reject, or an explicit reviewer note before Confirm or Action.",
      "The advisory does not change verification_status, the Project Takeaway gate, blocked_downstream_actions, or Action eligibility.",
    ],
    notAllowed: [
      "Do not treat Reasoning Assessment Advisory as proof that the candidate is true or false.",
      "Do not treat Framing Checklist as a system verdict, automatic rejection, or factual verification.",
      "Do not treat Packet Integrity Check as an automatic gate mutation; it is a reviewer-visible integrity warning until a separate integrity gate exists.",
      "Do not use it to bypass Project Takeaway gates, blocked_downstream_actions, or low-risk Action eligibility.",
      "Do not persist a counter-conclusion as external evidence.",
      "Do not treat a persisted counter-check draft as a review decision, factual verification, or gate mutation.",
      "Do not treat cross-provider agreement or disagreement as automatic verification.",
    ],
    notAllowedZh: [
      "Do not treat Reasoning Assessment Advisory as proof that the candidate is true or false.",
      "Do not treat Framing Checklist as a system verdict, automatic rejection, or factual verification.",
      "Do not treat Packet Integrity Check as an automatic gate mutation; it is a reviewer-visible integrity warning until a separate integrity gate exists.",
      "Do not use it to bypass Project Takeaway gates, blocked_downstream_actions, or low-risk Action eligibility.",
      "Do not persist a counter-conclusion as external evidence.",
      "Do not treat a persisted counter-check draft as a review decision, factual verification, or gate mutation.",
      "Do not treat cross-provider agreement or disagreement as automatic verification.",
    ],
    governingSources: [
      "docs/adr/0015-claim-set-composition-underdetermination-gate.md",
      "agent-skills/grill-the-inference/SKILL.md",
      "frontend/app/workspace/projects/review/page.tsx",
    ],
    keywords: [
      "reasoning assessment",
      "reasoning assessment advisory",
      "composition bridge",
      "composed conclusion",
      "extra inference load",
      "application mapping load",
      "application mapping",
      "mapping leap",
      "integrity-first",
      "packet integrity",
      "packet integrity check",
      "referential consistency",
      "signal mismatch",
      "framing checklist",
      "benchmark caveat",
      "artifact vs evidence",
      "capability list",
      "scope wording",
      "producer provenance",
      "load-bearing",
      "load bearing",
      "original insight",
      "original takeaway",
      "warrant",
      "counter-conclusion",
      "counter conclusion",
      "counter-check alternative",
      "generate counter-check",
      "llm counter-check draft",
      "cross-provider",
      "comparison mode",
      "underdetermined",
      "composition risk",
      "adr-0015",
    ],
  },
  {
    stateIdentifier: "manual_source.completed_to_project_memory",
    stateLabel: "Manual-source intelligence completed into project memory",
    stateLabelZh: "Manual-source intelligence completed into project memory",
    appliesWhen: [
      "A manual upload or manual link source has generated insight.",
      "The operator has captured source-stated limits or confidence boundaries for the manual material.",
      "The source has moved through Signal Detail or Manual Detail completion.",
      "The operator needs to know what to inspect next.",
    ],
    appliesWhenZh: [
      "A manual upload or manual link source has generated insight.",
      "The operator has captured source-stated limits or confidence boundaries for the manual material.",
      "The source has moved through Signal Detail or Manual Detail completion.",
      "The operator needs to know what to inspect next.",
    ],
    nextActions: [
      "Inspect the completed Signal Detail or Manual Detail source preview.",
      "Check source-stated limits as provenance metadata; use them to preserve caveats, not to prove the external claim.",
      "Confirm the durable Workspace record preserves manual-source identity.",
      "Inspect the related Project Takeaway candidate before Confirm, Watch, Action, Reject, or Dismiss.",
      "Check Review Records and Trajectory for manual-source contribution after review.",
    ],
    nextActionsZh: [
      "Inspect the completed Signal Detail or Manual Detail source preview.",
      "Check source-stated limits as provenance metadata; use them to preserve caveats, not to prove the external claim.",
      "Confirm the durable Workspace record preserves manual-source identity.",
      "Inspect the related Project Takeaway candidate before Confirm, Watch, Action, Reject, or Dismiss.",
      "Check Review Records and Trajectory for manual-source contribution after review.",
    ],
    notAllowed: [
      "Do not treat the manual source as factual evidence for external claims unless verification metadata supports that use.",
      "Do not treat source-stated limits as a Project Takeaway gate bypass or source-quality score.",
      "Do not skip Signal Detail, Workspace, or Project Takeaway gates because the source was manually selected.",
    ],
    notAllowedZh: [
      "Do not treat the manual source as factual evidence for external claims unless verification metadata supports that use.",
      "Do not treat source-stated limits as a Project Takeaway gate bypass or source-quality score.",
      "Do not skip Signal Detail, Workspace, or Project Takeaway gates because the source was manually selected.",
    ],
    governingSources: [
      "AGENTS.md#Intelligence-Quality-Boundaries",
      "DEVELOPMENT_PLAN.md#Trajectory-Memory",
      "docs/adr/0006-operator-guidance-layer.md",
      "backend/app/routes/signals.py",
    ],
    keywords: [
      "manual",
      "upload",
      "completion",
      "workspace",
      "signal detail",
      "manual detail",
      "source-stated limits",
      "source stated limits",
      "source confidence",
    ],
  },
  {
    stateIdentifier: "verified_insight.blocked_downstream_actions_present",
    stateLabel: "Verified insight has blocked downstream actions",
    stateLabelZh: "Verified insight has blocked downstream actions",
    appliesWhen: [
      "A signal, insight, candidate, or review object exposes blocked_downstream_actions.",
      "The operator is deciding whether a Project Takeaway or low-risk Action path is allowed.",
    ],
    appliesWhenZh: [
      "A signal, insight, candidate, or review object exposes blocked_downstream_actions.",
      "The operator is deciding whether a Project Takeaway or low-risk Action path is allowed.",
    ],
    nextActions: [
      "Read the visible gate note or verification summary before choosing an outcome.",
      "Prefer Watch or further review when evidence is partial, inferred, unsupported, contradicted, or not verifiable.",
      "Use only the explicit override-confirm or override-action path if an exceptional human override is needed.",
      "Record the reviewer note and expected outcome when using an override path.",
    ],
    nextActionsZh: [
      "Read the visible gate note or verification summary before choosing an outcome.",
      "Prefer Watch or further review when evidence is partial, inferred, unsupported, contradicted, or not verifiable.",
      "Use only the explicit override-confirm or override-action path if an exceptional human override is needed.",
      "Record the reviewer note and expected outcome when using an override path.",
    ],
    notAllowed: [
      "Do not use ordinary Confirm or Action paths to bypass blocked_downstream_actions.",
      "Do not label missing or empty verification metadata as verified_insight.",
      "Do not treat fallback LLM explanation as evidence or claim support.",
    ],
    notAllowedZh: [
      "Do not use ordinary Confirm or Action paths to bypass blocked_downstream_actions.",
      "Do not label missing or empty verification metadata as verified_insight.",
      "Do not treat fallback LLM explanation as evidence or claim support.",
    ],
    governingSources: [
      "AGENTS.md#Intelligence-Quality-Boundaries",
      "DEVELOPMENT_PLAN.md#Unified-Reasoning--Verification-Layer",
      "backend/app/services/verified_insight_service.py",
      "backend/app/services/project_takeaway_constants.py",
    ],
    keywords: ["blocked", "downstream", "verified", "verification", "gate", "override", "do not act"],
  },
  {
    stateIdentifier: "knowledge_convergence.review_candidate_pending",
    stateLabel: "Knowledge convergence candidate is pending review",
    stateLabelZh: "Knowledge convergence candidate is pending review",
    appliesWhen: [
      "A Knowledge convergence brief has been sent to Review Inbox.",
      "The candidate is marked as knowledge_convergence or knowledge_convergence_review_candidate.",
      "The operator is deciding whether the convergence should become reusable project intelligence.",
    ],
    appliesWhenZh: [
      "A Knowledge convergence brief has been sent to Review Inbox.",
      "The candidate is marked as knowledge_convergence or knowledge_convergence_review_candidate.",
      "The operator is deciding whether the convergence should become reusable project intelligence.",
    ],
    nextActions: [
      "Inspect the Knowledge context panel and matched project fit before acting.",
      "Check source count, shared topic overlap, project match reason, and evidence profile.",
      "Use Watch when the convergence is promising but still needs stronger project fit or evidence.",
      "Keep low-risk Action blocked unless further verified evidence or explicit override supports action.",
    ],
    nextActionsZh: [
      "Inspect the Knowledge context panel and matched project fit before acting.",
      "Check source count, shared topic overlap, project match reason, and evidence profile.",
      "Use Watch when the convergence is promising but still needs stronger project fit or evidence.",
      "Keep low-risk Action blocked unless further verified evidence or explicit override supports action.",
    ],
    notAllowed: [
      "Do not treat Knowledge convergence as automatic action evidence.",
      "Do not create reusable project memory from generic topic overlap alone.",
      "Do not hide missing project fit behind a Confirm outcome.",
    ],
    notAllowedZh: [
      "Do not treat Knowledge convergence as automatic action evidence.",
      "Do not create reusable project memory from generic topic overlap alone.",
      "Do not hide missing project fit behind a Confirm outcome.",
    ],
    governingSources: [
      "DEVELOPMENT_PLAN.md#Agent-Watch--Friction-Signals-Convergence",
      "AGENTS.md#Intelligence-Quality-Boundaries",
      "docs/adr/0006-operator-guidance-layer.md",
    ],
    keywords: ["knowledge", "convergence", "review", "candidate", "watch", "project fit"],
  },
];

export function detectGuidanceLanguage(text: string): "en" {
  void text;
  return "en";
}

function asksMetricsLocation(question: string) {
  const text = question.toLowerCase();
  return (
    (text.includes("metric") || text.includes("metrics")) &&
    (text.includes("where") ||
      text.includes("which page") ||
      text.includes("see") ||
      text.includes("look"))
  );
}

function currentSurfaceLabel(currentPath?: string) {
  const path = currentPath || "";
  if (path.startsWith("/signals")) return "Signals";
  if (path.startsWith("/friction-signals")) return "Friction Signals";
  if (path.startsWith("/watch-learning")) return "Watch Learning";
  if (path.startsWith("/workspace/projects/review")) return "Project Review Inbox";
  if (path.startsWith("/manual")) return "Manual Upload";
  if (path.startsWith("/admin/background-update-candidates")) return "Background Update Candidates";
  if (path.startsWith("/admin/metrics")) return "Metrics";
  if (path.startsWith("/admin")) return "Admin";
  if (path.startsWith("/knowledge")) return "Knowledge";
  if (path.startsWith("/reflections")) return "Reflections";
  return "this page";
}

function scopePrefix(
  currentPath: string | undefined,
  target: string,
  language: "en" | "zh"
) {
  const surface = currentSurfaceLabel(currentPath);
  if (surface === target || surface === "this page") return "";
  void language;
  return `You are currently on ${surface}, but this question belongs to ${target}.`;
}

function asksFrictionWatch(question: string) {
  const text = question.toLowerCase();
  const mentionsFriction = text.includes("friction");
  const mentionsWatch = text.includes("watch") || text.includes("follow-up") || text.includes("follow up");
  return mentionsFriction && mentionsWatch;
}

function asksProjectTakeaway(question: string) {
  const text = question.toLowerCase();
  return (
    text.includes("project takeaway") ||
    text.includes("review inbox") ||
    text.includes("candidate")
  );
}

function asksManualSource(question: string) {
  const text = question.toLowerCase();
  return (
    text.includes("manual") ||
    text.includes("upload") ||
    text.includes("source intent")
  );
}

export function buildGlobalGuidanceAnswer(
  question: string,
  language: "en" | "zh" = "en",
  currentPath?: string
) {
    if (asksMetricsLocation(question)) {
    return [
      scopePrefix(currentPath, "Metrics", language),
      "System metrics live at `/admin/metrics`.",
      "Open Metrics from the home page, or go through Admin -> Metrics. The page reads backend `/metrics/status`, `/metrics/daily-summary`, and `/metrics/summaries`.",
      "Current metrics cover pipeline, collector, artifact write, LLM, verification, and signal activity summary. Frontend timeline timeout / stale local snapshot events are not recorded automatically yet.",
    ].filter(Boolean).join("\n\n");
  }

  if (asksFrictionWatch(question)) {
    return [
      scopePrefix(currentPath, "Friction / Watch", language),
      "You can ask Friction Watch questions from any page; you do not need to move to the matching page first.",
      "The main surfaces are `/friction-signals`, `/watch-learning`, and the Watch queue in Review Inbox. Friction signals capture resistance, market/product tension, or opportunity; Watch means keep observing, not confirmed and not automatically actionable.",
      "The usual next step is to inspect the friction source and pattern, keep it in Watch while evidence or project fit is incomplete, and only move toward Confirm or Action when the gate allows it.",
    ].filter(Boolean).join("\n\n");
  }

  if (asksProjectTakeaway(question)) {
    return [
      scopePrefix(currentPath, "Project Takeaway", language),
      "Project Takeaway is the human review flow for reusable project memory, not something completed directly from the ordinary signal list.",
      "Use `/workspace/projects/review`. Candidate creation is not confirmation; review project fit, evidence note, verification status, and blocked_downstream_actions before choosing Confirm, Watch, Reject, Dismiss, or Action.",
    ].filter(Boolean).join("\n\n");
  }

  if (asksManualSource(question)) {
    return [
      scopePrefix(currentPath, "Manual Source", language),
      "Manual Source is the intake path for articles, PDFs, images, or links you found by hand. The main page is `/manual`.",
      "Start with source link, upload reason, intended use, and cognitive layer, then Analyze Session. Manual analysis can feed Signals, Knowledge, or Project Review, but it does not automatically become verified project memory.",
    ].filter(Boolean).join("\n\n");
  }

  return null;
}

export function buildGuidanceAnswer(entry: GuidanceEntry, language: "en" | "zh" = "en") {
  const label = language === "zh" ? entry.stateLabelZh : entry.stateLabel;
  const applies = language === "zh" ? entry.appliesWhenZh : entry.appliesWhen;
  const actions = language === "zh" ? entry.nextActionsZh : entry.nextActions;
  const blocked = language === "zh" ? entry.notAllowedZh : entry.notAllowed;
  const appliesWhen = applies.map((item, index) => `${index + 1}. ${item}`).join("\n");
  const nextActions = actions.map((action, index) => `${index + 1}. ${action}`).join("\n");
  const notAllowed = blocked.map((action, index) => `${index + 1}. ${action}`).join("\n");

    return [
    `For ${label}, use the mapped next-action path:`,
    `Applies when:\n${appliesWhen}`,
    nextActions,
    `Do not: ${notAllowed}`,
  ].join("\n\n");
}

function hasExplanationIntent(text: string) {
  const haystack = text.toLowerCase();
  return (
    haystack.includes("explain") ||
    haystack.includes("what does") ||
    haystack.includes("what means") ||
    haystack.includes("why")
  );
}

function buildCompletionWorkspaceExplanation(language: "en" | "zh") {
    return [
    "It means not every signal should become Workspace memory.",
    "Use completion / Workspace only when the completion note contains a useful judgment and the signal's evidence or verification state allows that downstream use.",
    "There are two gates:",
    "1. Completion note gate: did you actually capture a useful judgment, rather than copy the source?",
    "2. Evidence / verification gate: is the claim supported enough, are blocked_downstream_actions present, or should this remain watch-only context?",
    "If the note is useful but evidence is weak, prefer Watch, Save for Later, or cautious context instead of durable Workspace memory.",
  ].join("\n\n");
}

function buildEvidenceGroundingGateSnapshotExplanation(language: "en" | "zh") {
    return [
    "Verified Insight Object / Evidence Grounding / Gate Snapshot is a read-only diagnostic area on Signal Detail or Project Review Inbox, not a new verification conclusion.",
    "Verified Insight Object summarizes existing verification_status, claim support, confidence, and downstream gate metadata into a product view. It does not create evidence or override backend gates.",
    "Evidence Grounding only shows raw claim-check counts and coverage: Direct, Partial, Inferred, Unsupported/Contradicted, evidence refs coverage, and source span coverage. It does not create Well-grounded/Thin threshold labels or score source trust.",
    "Gate Snapshot only projects the current allowed_downstream_actions / blocked_downstream_actions into Project Takeaway, Watch, and Low-risk Action rows. If an action is absent from gate metadata, it is shown as not recorded, not as a new recommendation.",
    "This snapshot does not change verification_status, does not unlock actions, and must not be used as input to any gate decision. The actual gate remains the verification metadata and backend gate logic.",
  ].join("\n\n");
}

export function buildOperatorGuidanceResponse(question: string, currentPath: string, language: "en" | "zh" = "en") {
  const globalAnswer = buildGlobalGuidanceAnswer(question, language);
  if (globalAnswer) return globalAnswer;

  const haystack = `${question} ${currentPath}`.toLowerCase();

  if (
    hasExplanationIntent(question) &&
    (haystack.includes("verified insight object") ||
      haystack.includes("verified insight") ||
      haystack.includes("evidence grounding") ||
      haystack.includes("gate snapshot") ||
      (haystack.includes("claim") && haystack.includes("grounding")))
  ) {
    return buildEvidenceGroundingGateSnapshotExplanation(language);
  }

  if (
    hasExplanationIntent(question) &&
    (haystack.includes("completion note") ||
      haystack.includes("workspace") ||
      haystack.includes("completion / workspace") ||
      haystack.includes("evidence") ||
      haystack.includes("verification") ||
      haystack.includes("gate"))
  ) {
    return buildCompletionWorkspaceExplanation(language);
  }

  const matchedEntry = findGuidanceEntry(question, currentPath);
  if (matchedEntry) {
    return buildGuidanceAnswer(matchedEntry, language);
  }

    return [
    "I do not have a clear recommendation for this exact step yet.",
    "Try asking what the current status means, what the next review action should be, or why a button is disabled.",
  ].join("\n\n");
}

export function findGuidanceEntry(question: string, currentPath: string) {
  const questionHaystack = question.toLowerCase();
  const haystack = `${question} ${currentPath}`.toLowerCase();
  const isSignalOrManualDetail = currentPath.includes("/signals/detail") || currentPath.includes("/manual/detail");
  const mentionsProjectTakeaway =
    haystack.includes("project takeaway") ||
    haystack.includes("create candidate") ||
    haystack.includes("created candidate") ||
    haystack.includes("candidate created") ||
    haystack.includes("review inbox") ||
    haystack.includes("record watch follow-up") ||
    haystack.includes("record watch follow up") ||
    haystack.includes("add watch follow-up") ||
    haystack.includes("add watch follow up") ||
    haystack.includes("watch follow-up") ||
    haystack.includes("watch follow up");
  const mentionsKnowledge = haystack.includes("knowledge") || haystack.includes("convergence");
  const mentionsManual = haystack.includes("manual") || haystack.includes("upload");
  const mentionsBlocked =
    haystack.includes("blocked") ||
    haystack.includes("verification") ||
    haystack.includes("gate") ||
    haystack.includes("do not act");
  const asksReasoningAssessment =
    haystack.includes("reasoning assessment") ||
    haystack.includes("reasoning advisory") ||
    haystack.includes("load-bearing") ||
    haystack.includes("load bearing") ||
    haystack.includes("warrant") ||
    haystack.includes("counter-conclusion") ||
    haystack.includes("counter conclusion") ||
    haystack.includes("underdetermined") ||
    haystack.includes("composition risk") ||
    haystack.includes("adr-0015");
  const asksCompletionWorkspaceExplanation =
    (haystack.includes("explain") ||
      haystack.includes("what does") ||
      haystack.includes("why")) &&
    (haystack.includes("completion note") ||
      haystack.includes("workspace") ||
      haystack.includes("completion / workspace") ||
      haystack.includes("evidence") ||
      haystack.includes("verification") ||
      haystack.includes("gate"));
  const asksSaveForLaterExplanation =
    haystack.includes("save for later") ||
    haystack.includes("saved") ||
    haystack.includes("save reason") ||
    (haystack.includes("save") && (haystack.includes("meaning") || haystack.includes("explain")));
  const asksStarredExplanation =
    haystack.includes("starred") ||
    haystack.includes("star signal") ||
    haystack.includes("bookmark") ||
    haystack.includes("quick return") ||
    haystack.includes("find again");
  const mentionsSignalWorkflow =
    haystack.includes("signal") &&
    (haystack.includes("workflow") ||
      haystack.includes("flow") ||
      haystack.includes("process") ||
      haystack.includes("branch") ||
      haystack.includes("status") ||
      haystack.includes("pending") ||
      haystack.includes("saved") ||
      haystack.includes("analyzed") ||
      haystack.includes("rejected") ||
      haystack.includes("completed"));

  if (asksCompletionWorkspaceExplanation) {
    return guidanceEntries.find((entry) => entry.stateIdentifier === "signal.workflow.completion_workspace_gate_explanation") || null;
  }

  if (asksStarredExplanation) {
    return guidanceEntries.find((entry) => entry.stateIdentifier === "signal.bookmark.starred_explanation") || null;
  }

  if (asksSaveForLaterExplanation) {
    return guidanceEntries.find((entry) => entry.stateIdentifier === "signal.status.saved_for_later_explanation") || null;
  }

  if (asksReasoningAssessment) {
    return guidanceEntries.find((entry) => entry.stateIdentifier === "project_review.reasoning_assessment_advisory") || null;
  }

  if (mentionsProjectTakeaway || (isSignalOrManualDetail && haystack.includes("candidate") && !mentionsKnowledge)) {
    return guidanceEntries.find((entry) => entry.stateIdentifier === "project_takeaway.candidate_created_pending_review") || null;
  }

  if (mentionsSignalWorkflow) {
    return guidanceEntries.find((entry) => entry.stateIdentifier === "signal.workflow.end_to_end") || null;
  }

  if (mentionsKnowledge) {
    return guidanceEntries.find((entry) => entry.stateIdentifier === "knowledge_convergence.review_candidate_pending") || null;
  }

  if (mentionsBlocked) {
    return guidanceEntries.find((entry) => entry.stateIdentifier === "verified_insight.blocked_downstream_actions_present") || null;
  }

  if (mentionsManual || currentPath.includes("/manual")) {
    return guidanceEntries.find((entry) => entry.stateIdentifier === "manual_source.completed_to_project_memory") || null;
  }

  const scored = guidanceEntries
    .map((entry) => ({
      entry,
      score:
        entry.keywords.filter((keyword) => questionHaystack.includes(keyword)).length +
        (questionHaystack.includes(entry.stateIdentifier.toLowerCase()) ? 3 : 0),
    }))
    .sort((left, right) => right.score - left.score);

  return scored[0]?.score > 0 ? scored[0].entry : null;
}
