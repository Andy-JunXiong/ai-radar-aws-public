export type GuidanceLanguage = "en" | "zh";

export type GuidancePageState = {
  pathname: string;
  text: string;
};

function normalize(value: string) {
  return value.toLowerCase().replace(/\s+/g, " ").trim();
}

function hasAny(text: string, needles: string[]) {
  return needles.some((needle) => text.includes(needle));
}

function wantsNextStep(question: string) {
  const text = normalize(question);
  return hasAny(text, [
    "next",
    "what should",
    "what do",
    "do next",
    "meaning",
    "means",
    "explain",
    "what is this page",
    "why",
    "recommend",
    "record watch",
    "watch follow-up",
    "watch follow up",
    "add watch",
    "source intent",
    "upload reason mix",
    "manual source contribution",
    "cognitive layer mix",
    "open review record",
    "review record",
    "record detail",
    "audit trail",
    "calibration event",
    "calibration events",
    "ai discussion",
    "challenge",
    "assumption",
    "source health",
    "invalid feed",
    "check source",
  ]);
}

function asksPageMeaning(question: string) {
  const text = normalize(question);
  return hasAny(text, ["meaning", "means", "explain", "what is this page", "what does this page mean"]);
}

function asksActionRecommendation(question: string) {
  const text = normalize(question);
  return hasAny(text, ["next", "what should", "what do i do", "do next", "recommend"]);
}

function asksWatchFollowup(question: string, pageText: string) {
  const text = normalize(`${question} ${pageText}`);
  return hasAny(text, [
    "record watch follow-up",
    "record watch follow up",
    "add watch follow-up",
    "add watch follow up",
    "watch follow-up",
    "watch follow up",
  ]);
}

function asksAiDiscussionChallenge(question: string, pageText: string) {
  const questionText = normalize(question);
  const contextText = normalize(`${question} ${pageText}`);
  return contextText.includes("ai discussion") && hasAny(questionText, ["challenge", "assumption", "assumptions"]);
}

function asksAiDiscussionThinkingStyle(question: string, pageText: string) {
  const questionText = normalize(question);
  const contextText = normalize(`${question} ${pageText}`);
  return (
    contextText.includes("thinking style") &&
    hasAny(questionText, ["thinking style", "andy default", "framework", "frameworks", "evidence grading", "valence", "negative roi", "tension axis"])
  );
}

function asksAiDiscussionRecentContext(question: string, pageText: string) {
  const questionText = normalize(question);
  const contextText = normalize(`${question} ${pageText}`);
  return (
    contextText.includes("ai discussion") &&
    hasAny(questionText, ["recent context", "discussion context", "chat history", "history", "memory", "conversation context"])
  );
}

function asksEvidenceGroundingOrGateSnapshot(question: string) {
  const questionText = normalize(question);
  return (
    hasAny(questionText, ["verified insight object", "verified insight", "evidence grounding", "gate snapshot", "presentation fidelity", "source limits"]) ||
    (questionText.includes("claim") && questionText.includes("grounding"))
  );
}

function asksReasoningAssessmentAdvisory(question: string, pageText: string) {
  const text = normalize(`${question} ${pageText}`);
  return hasAny(text, [
    "reasoning assessment",
    "reasoning advisory",
    "composition bridge",
    "composed conclusion",
    "extra inference load",
    "application mapping load",
    "application mapping",
    "mapping leap",
    "integrity-first",
    "integrity first",
    "packet integrity",
    "packet integrity check",
    "referential consistency",
    "signal mismatch",
    "framing checklist",
    "benchmark caveat",
    "artifact vs evidence",
    "capability-list",
    "capability list",
    "scope wording",
    "producer provenance",
    "load-bearing",
    "load bearing",
    "original insight",
    "original takeaway",
    "warrant",
    "counter-check",
    "counter check",
    "counter-check alternative",
    "counter check alternative",
    "generate counter-check",
    "generate counter check",
    "llm counter-check draft",
    "llm counter check draft",
    "cross-provider",
    "cross provider",
    "comparison mode",
    "counter-conclusion",
    "counter conclusion",
    "underdetermined",
    "composition risk",
    "adr-0015",
  ]);
}

function asksFinalTakeawayConfirmation(question: string, pageText: string) {
  const questionText = normalize(question);
  const contextText = normalize(`${question} ${pageText}`);
  return (
    contextText.includes("final takeaway") &&
    hasAny(questionText, [
      "final takeaway",
      "confirm final takeaway",
      "review bundle",
      "snapshot",
      "completion note",
      "project review",
      "candidate",
      "confirmation",
      "send final takeaway",
      "confirmed_final_takeaway",
    ])
  );
}

function asksClaimReviewFeedback(question: string, pageText: string) {
  const questionText = normalize(question);
  const contextText = normalize(`${question} ${pageText}`);
  return (
    contextText.includes("not right") ||
    contextText.includes("relationship annotation") ||
    hasAny(questionText, ["feedback", "reason slot", "why not right", "claim feedback", "relationship annotation"])
  );
}

function asksReflectionPolish(question: string, pageText: string) {
  const questionText = normalize(question);
  const contextText = normalize(`${question} ${pageText}`);
  return (
    contextText.includes("ai polish") ||
    hasAny(questionText, [
      "reflection polish",
      "polish reflection",
      "polish pair",
      "review pair",
      "human review pair",
      "recorded pair",
      "polish review",
    ])
  );
}

function formatAnswer(language: GuidanceLanguage, zh: string[], en: string[]) {
  return (language === "zh" ? zh : en).filter(Boolean).join("\n\n");
}

function suggestedButton(language: GuidanceLanguage, label: string) {
  void language;
  return `Recommended next button: ${label}.`;
}

type PageGuidance = {
  match: (path: string) => boolean;
  button: string;
  zhMeaning: string[];
  zhNext: string[];
  enMeaning: string[];
  enNext: string[];
};

const knownPageGuidance: PageGuidance[] = [
  {
    match: (path) => path === "/architecture/signal-lifecycle-demo" || path.startsWith("/architecture/signal-lifecycle-demo/"),
    button: "Node View / Event Stream / Output View",
    zhMeaning: [
      "This is the Signal Lifecycle Demo, a static architecture fixture for comparing Node View, Event Stream, and Output View over the same signal lifecycle.",
      "It is an architecture explanation surface, not the live Signal workflow, not evidence verification, and not a Project Takeaway confirmation path.",
    ],
    zhNext: [
      "Use Node View for relationship shape, Event Stream for lifecycle order, and Output View for review-state outcomes. Treat it as a demo model before inspecting live Signals, Knowledge, or Project Review data.",
    ],
    enMeaning: [
      "This is the Signal Lifecycle Demo, a static architecture fixture for comparing Node View, Event Stream, and Output View over the same signal lifecycle.",
      "It is an architecture explanation surface, not the live Signal workflow, not evidence verification, and not a Project Takeaway confirmation path.",
    ],
    enNext: [
      "Use Node View for relationship shape, Event Stream for lifecycle order, and Output View for review-state outcomes. Treat it as a demo model before inspecting live Signals, Knowledge, or Project Review data.",
    ],
  },
  {
    match: (path) => path === "/architecture" || path.startsWith("/architecture/"),
    button: "Read Architecture",
    zhMeaning: [
      "This is the Architecture page for AI Radar's system architecture, ADRs, layer responsibilities, and the flow from external signals into structured intelligence.",
      "It is a product-internal architecture walkthrough, not ordinary Signal review or the Project Takeaway review queue.",
    ],
    zhNext: ["Start with the five-layer architecture and ADR notes; use Three-view demo for the static relationship model, then use Run signal or the Signals / Knowledge / Workspace pages when you want to inspect the real data flow."],
    enMeaning: [
      "This is the Architecture page for AI Radar's system architecture, ADRs, layer responsibilities, and the flow from external signals into structured intelligence.",
      "It is a product-internal architecture walkthrough, not ordinary Signal review or the Project Takeaway review queue.",
    ],
    enNext: ["Start with the five-layer architecture and ADR notes; use Three-view demo for the static relationship model, then use Run signal or the Signals / Knowledge / Workspace pages when you want to inspect the real data flow."],
  },
  {
    match: (path) => path === "/codex-workbench" || path.startsWith("/codex-workbench/"),
    button: "Save draft / Mark done / Copy local handoff",
    zhMeaning: [
      "Dev Inbox is a lightweight AI Radar development intake surface, not a browser IDE and not a Codex execution runtime.",
      "Use it to capture AI Radar bugs, product ideas, and scoped development prompts before sending them to local Codex, VS Code, Codex Cloud, or GitHub PR workflow.",
      "Request type, Priority, and Affected surface are handoff metadata for the next coding-agent run. They help preserve triage context without starting execution from this page.",
      "Draft Quality Gate is an advisory checklist for handoff completeness. It does not block copying, but it flags vague scope, weak task specificity, missing route checks, or mismatched priority.",
      "Save draft stores the current bug or development idea in the backend Dev Inbox draft store. Mark done closes a saved draft after the work is finished; Reopen moves it back to open. Copy draft copies a compact prompt. Copy local handoff copies a fuller local Codex task package with scope, boundaries, validation, and manual verification steps. Handoff on a saved draft copies that same full package for that saved item without restoring the form first.",
      "Inbox filters help triage saved drafts by request type, priority, and open/done status. GitHub read-only loop links open repo, branch, PR, and Actions pages without calling GitHub APIs.",
      "Legacy browser drafts are migrated once when the backend draft store is available. The page does not store OpenAI credentials, does not write GitHub, does not create PRs, and does not deploy.",
    ],
    zhNext: [
      "Write the repo, branch, request type, priority, affected surface, and development request, then check Draft Quality Gate before copying the handoff. Save draft if you are just capturing the idea, Mark done after the work is complete, or Copy local handoff when you are ready to send it to local Codex or VS Code. Use Handoff on a saved draft when you are picking up an older item.",
      "Keep actual code edits, tests, git operations, and deployment in VS Code, Codex Cloud, GitHub, or CI with explicit human approval.",
    ],
    enMeaning: [
      "Dev Inbox is a lightweight AI Radar development intake surface, not a browser IDE and not a Codex execution runtime.",
      "Use it to capture AI Radar bugs, product ideas, and scoped development prompts before sending them to local Codex, VS Code, Codex Cloud, or GitHub PR workflow.",
      "Request type, Priority, and Affected surface are handoff metadata for the next coding-agent run. They help preserve triage context without starting execution from this page.",
      "Draft Quality Gate is an advisory checklist for handoff completeness. It does not block copying, but it flags vague scope, weak task specificity, missing route checks, or mismatched priority.",
      "Save draft stores the current bug or development idea in the backend Dev Inbox draft store. Mark done closes a saved draft after the work is finished; Reopen moves it back to open. Copy draft copies a compact prompt. Copy local handoff copies a fuller local Codex task package with scope, boundaries, validation, and manual verification steps. Handoff on a saved draft copies that same full package for that saved item without restoring the form first.",
      "Inbox filters help triage saved drafts by request type, priority, and open/done status. GitHub read-only loop links open repo, branch, PR, and Actions pages without calling GitHub APIs.",
      "Legacy browser drafts are migrated once when the backend draft store is available. The page does not store OpenAI credentials, does not write GitHub, does not create PRs, and does not deploy.",
    ],
    enNext: [
      "Write the repo, branch, request type, priority, affected surface, and development request, then check Draft Quality Gate before copying the handoff. Save draft if you are just capturing the idea, Mark done after the work is complete, or Copy local handoff when you are ready to send it to local Codex or VS Code. Use Handoff on a saved draft when you are picking up an older item.",
      "Keep actual code edits, tests, git operations, and deployment in VS Code, Codex Cloud, GitHub, or CI with explicit human approval.",
    ],
  },
  {
    match: (path) => path === "/admin/subscriptions" || path.startsWith("/admin/subscriptions/"),
    button: "Save Subscription Settings",
    zhMeaning: [
      "This page manages subscribed signal sources, source health checks, topic preferences, and project intake links.",
      "A saved source affects the AWS data pipeline only after the save response reports Cloud sync succeeded, because the scheduled ingestion task reads the S3 subscription settings.",
    ],
    zhNext: [
      "Use Check Source Health for advisory RSS/Atom warnings, then after saving check the success banner: Cloud sync succeeded means the next AWS data pipeline run can read the updated S3 subscription settings.",
    ],
    enMeaning: [
      "This page manages subscribed signal sources, source health checks, topic preferences, and project intake links.",
      "A saved source affects the AWS data pipeline only after the save response reports Cloud sync succeeded, because the scheduled ingestion task reads the S3 subscription settings.",
    ],
    enNext: [
      "Use Check Source Health for advisory RSS/Atom warnings, then after saving check the success banner: Cloud sync succeeded means the next AWS data pipeline run can read the updated S3 subscription settings.",
    ],
  },
  {
    match: (path) => path === "/admin/background-update-candidates" || path.startsWith("/admin/background-update-candidates/"),
    button: "Confirm",
    zhMeaning: [
      "Background Update Candidates is the read-only downstream candidate queue and confirmation ledger for ADR-0012 Signal claim feedback.",
      "It derives inactive candidates only from not_me / blind_spot feedback. Confirm or Dismiss records a human ledger decision only. These candidates and decisions are not external factual evidence, do not update background context, and do not change verification_status, Project Takeaway gates, or action eligibility.",
    ],
    zhNext: [
      "Inspect the reason slot, feedback note, claim snapshot, boundary flags, and latest decision. Use Confirm to record that the candidate should remain available for future context-review work, or Dismiss to record that it should not be pursued. Open the original Signal when you need context. Neither button applies a background update.",
    ],
    enMeaning: [
      "Background Update Candidates is the read-only downstream candidate queue and confirmation ledger for ADR-0012 Signal claim feedback.",
      "It derives inactive candidates only from not_me / blind_spot feedback. Confirm or Dismiss records a human ledger decision only. These candidates and decisions are not external factual evidence, do not update background context, and do not change verification_status, Project Takeaway gates, or action eligibility.",
    ],
    enNext: [
      "Inspect the reason slot, feedback note, claim snapshot, boundary flags, and latest decision. Use Confirm to record that the candidate should remain available for future context-review work, or Dismiss to record that it should not be pursued. Open the original Signal when you need context. Neither button applies a background update.",
    ],
  },
  {
    match: (path) => path === "/admin/reflection-polish" || path.startsWith("/admin/reflection-polish/"),
    button: "Record Review",
    zhMeaning: [
      "Reflection Polish Review is the human review surface for reflection-polish before/after pairs.",
      "It compares the original draft with the polished output and records reviewer outcome plus six checklist dimensions. It does not save the final reflection, create evidence, enter Project Takeaway, or change action eligibility.",
    ],
    zhNext: [
      "Select a pair, compare Original Draft and Polished Output, inspect all six dimensions, then use Record Review only when you want to persist the human checklist outcome. Save the final reflection through the separate reflection save flow.",
    ],
    enMeaning: [
      "Reflection Polish Review is the human review surface for reflection-polish before/after pairs.",
      "It compares the original draft with the polished output and records reviewer outcome plus six checklist dimensions. It does not save the final reflection, create evidence, enter Project Takeaway, or change action eligibility.",
    ],
    enNext: [
      "Select a pair, compare Original Draft and Polished Output, inspect all six dimensions, then use Record Review only when you want to persist the human checklist outcome. Save the final reflection through the separate reflection save flow.",
    ],
  },
  {
    match: (path) => path === "/admin" || path.startsWith("/admin/"),
    button: "Admin Diagnostics",
    zhMeaning: [
      "This is the Admin area for system settings, diagnostics, metrics, subscriptions, and operational status.",
      "Operating Home is a direct link to the internal AI Radar operating overview; it is intentionally not promoted into the main navigation.",
      "It is an ops and configuration surface, not the Signal review or Project Takeaway decision page.",
    ],
    zhNext: ["Use Operating Home when you want the older intake-to-review shortcut surface, Admin Diagnostics when debugging system state, and Signals, Knowledge, or Workspace when processing content."],
    enMeaning: [
      "This is the Admin area for system settings, diagnostics, metrics, subscriptions, and operational status.",
      "Operating Home is a direct link to the internal AI Radar operating overview; it is intentionally not promoted into the main navigation.",
      "It is an ops and configuration surface, not the Signal review or Project Takeaway decision page.",
    ],
    enNext: ["Use Operating Home when you want the older intake-to-review shortcut surface, Admin Diagnostics when debugging system state, and Signals, Knowledge, or Workspace when processing content."],
  },
  {
    match: (path) => path === "/overview" || path.startsWith("/overview/"),
    button: "Signals",
    zhMeaning: [
      "Operating Home is the internal AI Radar shortcut surface for intake, signal review, Project Review, trajectory, metrics, and work-surface navigation.",
      "It is a navigation and orientation page, not a Project Takeaway decision page and not the public AI Radar home.",
    ],
    zhNext: [
      "Use Manual Upload for new sources, Signals for individual signal review, Review Inbox for Project Takeaway candidates, Trajectory for learning history, or Metrics for operational health.",
    ],
    enMeaning: [
      "Operating Home is the internal AI Radar shortcut surface for intake, signal review, Project Review, trajectory, metrics, and work-surface navigation.",
      "It is a navigation and orientation page, not a Project Takeaway decision page and not the public AI Radar home.",
    ],
    enNext: [
      "Use Manual Upload for new sources, Signals for individual signal review, Review Inbox for Project Takeaway candidates, Trajectory for learning history, or Metrics for operational health.",
    ],
  },
  {
    match: (path) => path === "/dashboard" || path.startsWith("/dashboard/"),
    button: "Signals",
    zhMeaning: [
      "This is the Dashboard page for a quick overview of AI Radar operations and content.",
      "It is an observation entry point, not where you process individual signals or confirm project memory.",
    ],
    zhNext: ["Use Signals to process content; use Admin or Metrics for deeper operational health checks."],
    enMeaning: [
      "This is the Dashboard page for a quick overview of AI Radar operations and content.",
      "It is an observation entry point, not where you process individual signals or confirm project memory.",
    ],
    enNext: ["Use Signals to process content; use Admin or Metrics for deeper operational health checks."],
  },
  {
    match: (path) => path === "/knowledge" || path.startsWith("/knowledge/"),
    button: "Knowledge",
    zhMeaning: [
      "This is the Knowledge page for triaging synthesized convergence briefs, paired supply-demand signals, and project-fit quality.",
      "Use Convergence Freshness first to see whether the Top 5 changed since your last browser view; list cards then show the pair, one verdict, project fit, and action boundary.",
    ],
    zhNext: ["Start with Freshness / Delta. If New and Changed are zero, skim or skip; otherwise read the single verdict on changed briefs, open Brief Detail only when you need full reasoning, and send to Review Inbox only when project fit is real enough for human review."],
    enMeaning: [
      "This is the Knowledge page for triaging synthesized convergence briefs, paired supply-demand signals, and project-fit quality.",
      "Use Convergence Freshness first to see whether the Top 5 changed since your last browser view; list cards then show the pair, one verdict, project fit, and action boundary.",
    ],
    enNext: ["Start with Freshness / Delta. If New and Changed are zero, skim or skip; otherwise read the single verdict on changed briefs, open Brief Detail only when you need full reasoning, and send to Review Inbox only when project fit is real enough for human review."],
  },
  {
    match: (path) => path === "/radar" || path.startsWith("/radar/"),
    button: "Radar Summary",
    zhMeaning: [
      "This is the Radar Summary page for topic momentum, trend clusters, and strategic signal summaries.",
      "It is a higher-level observation surface, not the workflow for one signal.",
    ],
    zhNext: ["Start by identifying which themes are strengthening; use Signals or Knowledge when you need source-level detail."],
    enMeaning: [
      "This is the Radar Summary page for topic momentum, trend clusters, and strategic signal summaries.",
      "It is a higher-level observation surface, not the workflow for one signal.",
    ],
    enNext: ["Start by identifying which themes are strengthening; use Signals or Knowledge when you need source-level detail."],
  },
  {
    match: (path) => path === "/agent-watch" || path.startsWith("/agent-watch/"),
    button: "Agent Watch",
    zhMeaning: [
      "This is the Agent Watch page for monitoring agent-native cloud, coding agents, and related ecosystem movement, including tracking states like new, heating, sustained, cooling, dropped, and revived.",
      "It is a topic-monitoring surface, not the Project Takeaway review queue.",
    ],
    zhNext: ["Start with tracking state and big-mover filters; open detail or move into Signal / Knowledge workflow if an item needs action."],
    enMeaning: [
      "This is the Agent Watch page for monitoring agent-native cloud, coding agents, and related ecosystem movement, including tracking states like new, heating, sustained, cooling, dropped, and revived.",
      "It is a topic-monitoring surface, not the Project Takeaway review queue.",
    ],
    enNext: ["Start with tracking state and big-mover filters; open detail or move into Signal / Knowledge workflow if an item needs action."],
  },
  {
    match: (path) => path === "/friction-signals" || path.startsWith("/friction-signals/"),
    button: "Friction Signals",
    zhMeaning: [
      "This is the Friction Signals page for market, product, or user-flow friction signals, including advisory tracking states like new, heating, sustained, cooling, dropped, and revived.",
      "Tracking-state and big-mover filters help surface changing friction patterns.",
      "It helps surface resistance and opportunity, but it is not already-verified project judgment and does not create low-risk Action readiness by itself.",
    ],
    zhNext: ["Start with tracking state and big-mover filters, then read the friction pattern. Use detail, Signal, or Knowledge workflow if it should be preserved or paired with Agent Watch supply."],
    enMeaning: [
      "This is the Friction Signals page for market, product, or user-flow friction signals, including advisory tracking states like new, heating, sustained, cooling, dropped, and revived.",
      "Tracking-state and big-mover filters help surface changing friction patterns.",
      "It helps surface resistance and opportunity, but it is not already-verified project judgment and does not create low-risk Action readiness by itself.",
    ],
    enNext: ["Start with tracking state and big-mover filters, then read the friction pattern. Use detail, Signal, or Knowledge workflow if it should be preserved or paired with Agent Watch supply."],
  },
  {
    match: (path) => path === "/reflections" || path.startsWith("/reflections/"),
    button: "Reflections",
    zhMeaning: [
      "This is the Reflections page for cognitive context, observations, and thinking notes.",
      "Reflection is cognitive material, not external factual evidence; it should not directly verify claims.",
    ],
    zhNext: ["Review or record the reflection first; if it needs factual evidence status, move through a separate signal / evidence workflow."],
    enMeaning: [
      "This is the Reflections page for cognitive context, observations, and thinking notes.",
      "Reflection is cognitive material, not external factual evidence; it should not directly verify claims.",
    ],
    enNext: ["Review or record the reflection first; if it needs factual evidence status, move through a separate signal / evidence workflow."],
  },
  {
    match: (path) => path === "/feed" || path.startsWith("/feed/"),
    button: "Signals",
    zhMeaning: [
      "This is the Feed page for viewing or debugging raw feed and source content entering the system.",
      "It is intake observation, not final evidence judgment or project memory.",
    ],
    zhNext: ["First confirm the feed is entering correctly; use Signals to handle specific items."],
    enMeaning: [
      "This is the Feed page for viewing or debugging raw feed and source content entering the system.",
      "It is intake observation, not final evidence judgment or project memory.",
    ],
    enNext: ["First confirm the feed is entering correctly; use Signals to handle specific items."],
  },
  {
    match: (path) => path === "/login" || path.startsWith("/login/"),
    button: "Log in",
    zhMeaning: [
      "This is the login page for establishing an admin session before accessing protected AI Radar work surfaces.",
      "Credentials are retained only for the current browser session; 60 idle minutes on protected pages requires signing in again.",
      "It is only the authentication entry point, not a signal, knowledge, or review decision page.",
    ],
    zhNext: ["Log in first if you need a protected surface; if the session expired or this is a new browser session, enter the username and password again."],
    enMeaning: [
      "This is the login page for establishing an admin session before accessing protected AI Radar work surfaces.",
      "Credentials are retained only for the current browser session; 60 idle minutes on protected pages requires signing in again.",
      "It is only the authentication entry point, not a signal, knowledge, or review decision page.",
    ],
    enNext: ["Log in first if you need a protected surface; if the session expired or this is a new browser session, enter the username and password again."],
  },
  {
    match: (path) => path === "/manual" || path.startsWith("/manual/"),
    button: "Analyze Session",
    zhMeaning: [
      "This is the Manual Upload area for bringing manually found articles, PDFs, images, or links into AI Radar and inspecting manual session details.",
      "It is not final project memory; material should preserve source-stated limits when available and go through session analysis before moving to Signal records, Workspace, or Project Review.",
    ],
    zhNext: ["For new material, fill source link, upload reason, intended use, and source-stated limits, then Analyze Session. On detail pages, inspect the analysis before moving into the next workflow."],
    enMeaning: [
      "This is the Manual Upload area for bringing manually found articles, PDFs, images, or links into AI Radar and inspecting manual session details.",
      "It is not final project memory; material should preserve source-stated limits when available and go through session analysis before moving to Signal records, Workspace, or Project Review.",
    ],
    enNext: ["For new material, fill source link, upload reason, intended use, and source-stated limits, then Analyze Session. On detail pages, inspect the analysis before moving into the next workflow."],
  },
  {
    match: (path) => path === "/saved" || path.startsWith("/saved/"),
    button: "Signals",
    zhMeaning: [
      "This is the Saved page for items kept because they may be useful later.",
      "Saved does not mean verified or completed; it is retained context, not a project conclusion.",
    ],
    zhNext: ["Review the save reason first; if it is worth handling now, return to Signals or the relevant detail page."],
    enMeaning: [
      "This is the Saved page for items kept because they may be useful later.",
      "Saved does not mean verified or completed; it is retained context, not a project conclusion.",
    ],
    enNext: ["Review the save reason first; if it is worth handling now, return to Signals or the relevant detail page."],
  },
  {
    match: (path) => path === "/settings" || path.startsWith("/settings/"),
    button: "Settings",
    zhMeaning: [
      "This is the Settings area for preferences, forms, and reflection-related configuration.",
      "It is a configuration page, not content review, evidence gate, or Project Takeaway judgment.",
    ],
    zhNext: ["Identify the setting you intend to change first; before saving, check whether it affects upload, reflection, or workflow display."],
    enMeaning: [
      "This is the Settings area for preferences, forms, and reflection-related configuration.",
      "It is a configuration page, not content review, evidence gate, or Project Takeaway judgment.",
    ],
    enNext: ["Identify the setting you intend to change first; before saving, check whether it affects upload, reflection, or workflow display."],
  },
  {
    match: (path) => path === "/watch-learning" || path.startsWith("/watch-learning/"),
    button: "Project Review Inbox",
    zhMeaning: [
      "This is the Watch Learning page for reviewing Watch items and follow-up learning signals.",
      "It helps extract learning from watched project items, not ingest new signals.",
    ],
    zhNext: ["Check which Watch items have new evidence or are due; return to Project Review Inbox when a decision is needed."],
    enMeaning: [
      "This is the Watch Learning page for reviewing Watch items and follow-up learning signals.",
      "It helps extract learning from watched project items, not ingest new signals.",
    ],
    enNext: ["Check which Watch items have new evidence or are due; return to Project Review Inbox when a decision is needed."],
  },
  {
    match: (path) => path === "/workspace" || path.startsWith("/workspace/"),
    button: "Workspace",
    zhMeaning: [
      "This is the Workspace area for work memory, project judgment, and follow-up outputs.",
      "It is closer to durable work surface, not raw intake.",
    ],
    zhNext: ["Choose the specific surface first: project review, trajectory, insights, decisions, or backlog. Do not treat unverified content as final judgment."],
    enMeaning: [
      "This is the Workspace area for work memory, project judgment, and follow-up outputs.",
      "It is closer to durable work surface, not raw intake.",
    ],
    enNext: ["Choose the specific surface first: project review, trajectory, insights, decisions, or backlog. Do not treat unverified content as final judgment."],
  },
];

function buildKnownPageGuidance(path: string, meaningQuestion: boolean, language: GuidanceLanguage) {
  const entry = knownPageGuidance.find((candidate) => candidate.match(path));
  if (!entry) return null;

  if (meaningQuestion) {
    return formatAnswer(language, entry.enMeaning, entry.enMeaning);
  }

  return formatAnswer(
    language,
    [`${suggestedButton(language, entry.button)} ${entry.enNext[0] || ""}`, ...entry.enNext.slice(1)]
  ,
    [`${suggestedButton(language, entry.button)} ${entry.enNext[0] || ""}`, ...entry.enNext.slice(1)]
  );
}

function buildUnknownPageGuidance(path: string, meaningQuestion: boolean, language: GuidanceLanguage) {
  if (meaningQuestion) {
    return formatAnswer(
      language,
      [
        "This is an AI Radar work page, but there is no more specific page guidance yet.",
        "Use the visible title, primary buttons, and status labels first. Do not automatically treat it as Signal workflow or Project Review.",
      ]
    ,
      [
        "This is an AI Radar work page, but there is no more specific page guidance yet.",
        "Use the visible title, primary buttons, and status labels first. Do not automatically treat it as Signal workflow or Project Review.",
      ]
    );
  }

  return formatAnswer(
    language,
    [
      "This page does not have a dedicated next-step rule yet.",
      "Use the main visible button or return to the parent navigation first. If evidence, Project Review, or action gates are involved, move to that dedicated surface before deciding.",
    ]
  ,
    [
      "This page does not have a dedicated next-step rule yet.",
      "Use the main visible button or return to the parent navigation first. If evidence, Project Review, or action gates are involved, move to that dedicated surface before deciding.",
    ]
  );
}

export function buildStateAwareGuidanceResponse(
  question: string,
  state: GuidancePageState,
  language: GuidanceLanguage
) {
  if (!wantsNextStep(question)) return null;

  const pageText = normalize(state.text);
  const path = state.pathname || "/";
  const isSignalDetail = path.startsWith("/signals/detail");
  const isSignalTimeline = !isSignalDetail && (path === "/signals" || path === "/signals/" || path.startsWith("/signals?"));
  const isOperatingHome = path === "/" || path === "";
  const isManualUpload = path === "/manual" || path === "/manual/";
  const isAdminSubscriptions = path === "/admin/subscriptions" || path.startsWith("/admin/subscriptions/");
  const isProjectReviewInbox = path.startsWith("/workspace/projects/review");
  const isReviewRecordDetail = path.startsWith("/workspace/projects/review/record");
  const isTrajectoryTimeline = path.startsWith("/workspace/projects/trajectory");
  const meaningQuestion = asksPageMeaning(question) && !asksActionRecommendation(question);
  const watchFollowupQuestion = asksWatchFollowup(question, pageText);
  const aiDiscussionChallengeQuestion = asksAiDiscussionChallenge(question, pageText);
  const aiDiscussionThinkingStyleQuestion = asksAiDiscussionThinkingStyle(question, pageText);
  const claimReviewFeedbackQuestion = asksClaimReviewFeedback(question, pageText);
  const starredQuestion = hasAny(normalize(question), [
    "starred",
    "star signal",
    "bookmark",
    "quick return",
    "find again",
  ]);

  if (
    isAdminSubscriptions &&
    hasAny(normalize(question), ["cloud sync", "s3 sync", "aws data pipeline", "subscription settings"])
  ) {
    return formatAnswer(
      language,
      [
        "Cloud sync is the handoff between this settings page and the AWS data pipeline.",
        "Saved locally means the backend file was updated. Cloud sync succeeded means the same subscription settings were written to S3, where the scheduled ingestion task reads them on its next run.",
        `${suggestedButton(language, "Save Subscription Settings")} Save first, then use the success banner to confirm whether the AWS pipeline can see the update.`,
      ]
    ,
      [
        "Cloud sync is the handoff between this settings page and the AWS data pipeline.",
        "Saved locally means the backend file was updated. Cloud sync succeeded means the same subscription settings were written to S3, where the scheduled ingestion task reads them on its next run.",
        `${suggestedButton(language, "Save Subscription Settings")} Save first, then use the success banner to confirm whether the AWS pipeline can see the update.`,
      ]
    );
  }

  if (
    isAdminSubscriptions &&
    hasAny(normalize(`${question} ${pageText}`), ["source health", "invalid feed", "check source", "404 feed"])
  ) {
    return formatAnswer(
      language,
      [
        "Source Health is an advisory check for subscribed RSS or Atom feeds.",
        "It flags feed-like URLs that return HTML, 404, or no entries, while custom URLs and disabled sources are skipped instead of blocked.",
        `${suggestedButton(language, "Check Source Health")} Run it before saving a source batch when you want confidence that the AWS daily pipeline can actually parse the feed URLs.`,
      ]
    ,
      [
        "Source Health is an advisory check for subscribed RSS or Atom feeds.",
        "It flags feed-like URLs that return HTML, 404, or no entries, while custom URLs and disabled sources are skipped instead of blocked.",
        `${suggestedButton(language, "Check Source Health")} Run it before saving a source batch when you want confidence that the AWS daily pipeline can actually parse the feed URLs.`,
      ]
    );
  }

  if ((isSignalTimeline || isSignalDetail) && starredQuestion) {
    return formatAnswer(
      language,
      [
        "Starred is a lightweight bookmark for quick return while you are reviewing a signal.",
        "It does not change Pending, Saved, Analyzed, Completed, or Rejected status.",
        `${suggestedButton(language, "Starred filter")} Use the Starred filter on the Signal Timeline to find bookmarked signals again.`,
        "Use Save for Later instead when the workflow decision is to pause the signal for future review.",
      ]
    ,
      [
        "Starred is a lightweight bookmark for quick return while you are reviewing a signal.",
        "It does not change Pending, Saved, Analyzed, Completed, or Rejected status.",
        `${suggestedButton(language, "Starred filter")} Use the Starred filter on the Signal Timeline to find bookmarked signals again.`,
        "Use Save for Later instead when the workflow decision is to pause the signal for future review.",
      ]
    );
  }

  if (isOperatingHome) {
    if (meaningQuestion) {
      return formatAnswer(
        language,
        [
          "This is the AI Radar operating home, not an individual Signal page.",
          "It summarizes the main loop: Intake collects information, Signal Review handles evidence and status, Project Review handles human judgment, and Trajectory shows learning history.",
          "Review Focus and Work Surfaces are navigation entry points that help you choose where to work next.",
        ]
      ,
        [
          "This is the AI Radar operating home, not an individual Signal page.",
          "It summarizes the main loop: Intake collects information, Signal Review handles evidence and status, Project Review handles human judgment, and Trajectory shows learning history.",
          "Review Focus and Work Surfaces are navigation entry points that help you choose where to work next.",
        ]
      );
    }

    return formatAnswer(
      language,
      [
        "This is the AI Radar operating home. The next step depends on the work you want to do today.",
        `${suggestedButton(language, "Signals")} Use Signals if you want to review newly collected information.`,
        "Use Project Takeaways or Workspace if you want to handle project-level judgment or reusable memory.",
      ]
    ,
      [
        "This is the AI Radar operating home. The next step depends on the work you want to do today.",
        `${suggestedButton(language, "Signals")} Use Signals if you want to review newly collected information.`,
        "Use Project Takeaways or Workspace if you want to handle project-level judgment or reusable memory.",
      ]
    );
  }

  if (isManualUpload) {
    if (meaningQuestion) {
      return formatAnswer(
        language,
        [
          "This is the Manual Upload page. It lets you add articles, PDFs, images, or links you found manually into AI Radar.",
          "It is not final project memory yet. Add source, upload reason, intended use, cognitive layer, and source-stated limits, then Analyze Session to create a manual session.",
          "After analysis, useful material can move toward Signal records, Workspace, or Project Review.",
        ]
      ,
        [
          "This is the Manual Upload page. It lets you add articles, PDFs, images, or links you found manually into AI Radar.",
          "It is not final project memory yet. Add source, upload reason, intended use, cognitive layer, and source-stated limits, then Analyze Session to create a manual session.",
          "After analysis, useful material can move toward Signal records, Workspace, or Project Review.",
        ]
      );
    }

    return formatAnswer(
      language,
      [
        "This is Manual Upload. Next, complete the source, intended-use, and source-stated limits fields.",
        `${suggestedButton(language, "Analyze Session")} If a file or source link is ready, analyze it first; use View Signal Records to inspect generated signals.`,
      ]
    ,
      [
        "This is Manual Upload. Next, complete the source, intended-use, and source-stated limits fields.",
        `${suggestedButton(language, "Analyze Session")} If a file or source link is ready, analyze it first; use View Signal Records to inspect generated signals.`,
      ]
    );
  }

  if (isReviewRecordDetail) {
    const decisionSnapshotQuestion = hasAny(normalize(question), [
      "decision snapshot",
      "current judgment",
      "reuse posture",
      "risk posture",
    ]);
    const auditTrailQuestion = hasAny(normalize(question), [
      "audit trail",
      "calibration event",
      "calibration events",
    ]);
    if (asksEvidenceGroundingOrGateSnapshot(question)) {
      return formatAnswer(
        language,
        [
          "Verified Insight Object is a read-only record-boundary summary on Review Record Detail, not a new verification conclusion.",
          "It projects recorded outcome, verification_status, confidence, claim support / claim risk, and blocked_downstream_actions into a review-memory view.",
          "It does not reconfirm review, create evidence, change verification_status, or change Action eligibility; in short, it does not change Action eligibility.",
        ]
      ,
        [
          "Verified Insight Object is a read-only record-boundary summary on Review Record Detail, not a new verification conclusion.",
          "It projects recorded outcome, verification_status, confidence, claim support / claim risk, and blocked_downstream_actions into a review-memory view.",
          "It does not reconfirm review, create evidence, change verification_status, or change Action eligibility; in short, it does not change Action eligibility.",
        ]
      );
    }
    if (decisionSnapshotQuestion) {
      return formatAnswer(
        language,
        [
          "Decision Snapshot summarizes the recorded review outcome, reuse posture, risk posture, and the next surface to inspect.",
          "It is a read-only interpretation of fields already stored on the Review Record; it is not a new gate, not a new approval, and not a fresh review decision.",
          "If the snapshot shows risk or caution, read Review Boundary before reusing the record as project memory.",
          `${suggestedButton(language, "Review Boundary")} Use Review Boundary to inspect the exact gate and claim-support context.`,
        ]
      ,
        [
          "Decision Snapshot summarizes the recorded review outcome, reuse posture, risk posture, and the next surface to inspect.",
          "It is a read-only interpretation of fields already stored on the Review Record; it is not a new gate, not a new approval, and not a fresh review decision.",
          "If the snapshot shows risk or caution, read Review Boundary before reusing the record as project memory.",
          `${suggestedButton(language, "Review Boundary")} Use Review Boundary to inspect the exact gate and claim-support context.`,
        ]
      );
    }
    if (auditTrailQuestion) {
      return formatAnswer(
        language,
        [
          "Audit Trail shows calibration events around the same project and signal, such as the review-record-created event and any outcome event.",
          "Current Review Record marks the event directly linked to this record id; other rows are same-project/same-signal audit context.",
          "It is audit context for reconstructing what happened; it does not make the source more verified, reopen the review, or bypass downstream gates.",
          `${suggestedButton(language, "Trajectory")} Use Trajectory when you need the longer learning-history view for this decision.`,
        ]
      ,
        [
          "Audit Trail shows calibration events around the same project and signal, such as the review-record-created event and any outcome event.",
          "Current Review Record marks the event directly linked to this record id; other rows are same-project/same-signal audit context.",
          "It is audit context for reconstructing what happened; it does not make the source more verified, reopen the review, or bypass downstream gates.",
          `${suggestedButton(language, "Trajectory")} Use Trajectory when you need the longer learning-history view for this decision.`,
        ]
      );
    }

    if (meaningQuestion) {
      return formatAnswer(
        language,
        [
          "This is the Review Record Detail page for inspecting one Project Takeaway human review decision.",
          "It is read-only judgment memory: Decision Snapshot, outcome, reason, source context, verification gate, claim support, and related links. It does not reconfirm, overwrite, or bypass any gate.",
          "If a gate field says Not recorded, no eligibility snapshot was returned for that field; it is not approval for downstream action.",
          "Use Review Inbox to continue the judgment workflow, or Trajectory to see how the record contributes to learning history.",
        ]
      ,
        [
          "This is the Review Record Detail page for inspecting one Project Takeaway human review decision.",
          "It is read-only judgment memory: Decision Snapshot, outcome, reason, source context, verification gate, claim support, and related links. It does not reconfirm, overwrite, or bypass any gate.",
          "If a gate field says Not recorded, no eligibility snapshot was returned for that field; it is not approval for downstream action.",
          "Use Review Inbox to continue the judgment workflow, or Trajectory to see how the record contributes to learning history.",
        ]
      );
    }

    return formatAnswer(
      language,
      [
        `${suggestedButton(language, "Review Records")} Return to the Records list if you need to filter related decisions by project, outcome, or quality.`,
        `${suggestedButton(language, "Trajectory")} Open Trajectory if you need to see whether this record is shaping learning history.`,
      ]
    ,
      [
        `${suggestedButton(language, "Review Records")} Return to the Records list if you need to filter related decisions by project, outcome, or quality.`,
        `${suggestedButton(language, "Trajectory")} Open Trajectory if you need to see whether this record is shaping learning history.`,
      ]
    );
  }

  if (isProjectReviewInbox) {
    if (asksReasoningAssessmentAdvisory(question, pageText)) {
      return formatAnswer(
        language,
        [
          "Reasoning Assessment Advisory is a reviewer-only prompt on pending Review Inbox candidates, not a verdict.",
          "Use it to inspect the original insight / takeaway beside the load-bearing packet, state the warrant connecting evidence to the takeaway, and run a counter-conclusion check as a reviewer answer, not a system answer.",
          "Composition Bridge names the composed conclusion and the extra inference load between packet facts and candidate takeaway; Application Mapping Load highlights when one packet is being applied to several projects or modules.",
          "Packet Integrity Check is a referential consistency warning for stale, misattached, or wrong-signal evidence. When it appears, the composed conclusion is collapsed until packet integrity is reviewed, and expanded text remains marked unverified pending packet integrity review, but it still does not mutate gates.",
          "Framing Checklist is part of the same reviewer-only surface. Use it to check benchmark caveats, artifact/evidence boundaries, precise capability lists, scope wording, and producer provenance before accepting a polished framing.",
          "Generate Counter-Check produces a persisted reviewer-advisory LLM counter-check draft; once one exists, Regenerate Counter-Check replaces that draft, but the reviewer still decides Yes / No / Unclear and writes the final note.",
          "If the same evidence also supports an opposite conclusion, incompatible conclusion, weaker conclusion, Watch posture, or no Project Takeaway, keep the decision conservative and write the reviewer note.",
          "Mark the counter-check Yes / No / Unclear in your review note when it matters.",
          "It does not change verification_status, the Project Takeaway gate, blocked_downstream_actions, or Action eligibility.",
        ]
      ,
        [
          "Reasoning Assessment Advisory is a reviewer-only prompt on pending Review Inbox candidates, not a verdict.",
          "Use it to inspect the original insight / takeaway beside the load-bearing packet, state the warrant connecting evidence to the takeaway, and run a counter-conclusion check as a reviewer answer, not a system answer.",
          "Composition Bridge names the composed conclusion and the extra inference load between packet facts and candidate takeaway; Application Mapping Load highlights when one packet is being applied to several projects or modules.",
          "Packet Integrity Check is a referential consistency warning for stale, misattached, or wrong-signal evidence. When it appears, the composed conclusion is collapsed until packet integrity is reviewed, and expanded text remains marked unverified pending packet integrity review, but it still does not mutate gates.",
          "Framing Checklist is part of the same reviewer-only surface. Use it to check benchmark caveats, artifact/evidence boundaries, precise capability lists, scope wording, and producer provenance before accepting a polished framing.",
          "Generate Counter-Check produces a persisted reviewer-advisory LLM counter-check draft; once one exists, Regenerate Counter-Check replaces that draft, but the reviewer still decides Yes / No / Unclear and writes the final note.",
          "If the same evidence also supports an opposite conclusion, incompatible conclusion, weaker conclusion, Watch posture, or no Project Takeaway, keep the decision conservative and write the reviewer note.",
          "Mark the counter-check Yes / No / Unclear in your review note when it matters.",
          "It does not change verification_status, the Project Takeaway gate, blocked_downstream_actions, or Action eligibility.",
        ]
      );
    }

    const learningProfileQuestion =
      hasAny(normalize(question), [
        "project learning profile",
        "learning profile",
        "evidence boundary",
        "gate risk",
        "learning memory",
      ]) ||
      (pageText.includes("project learning profile") &&
        hasAny(normalize(question), ["this panel", "this section", "what does this mean"]));
    if (learningProfileQuestion) {
      return formatAnswer(
        language,
        [
          "Project Learning Profile is a read-only summary of ReviewRecord and CalibrationEvent history.",
          "It helps you see action memory, Watch memory, manual-source learning, and gate-risk pressure. It is not a new review gate, not external claim evidence, and not approval for low-risk Action.",
          `${suggestedButton(language, "Records / Trajectory")} Use Records to inspect individual decisions, or Trajectory to see how those decisions became learning history.`,
        ]
      ,
        [
          "Project Learning Profile is a read-only summary of ReviewRecord and CalibrationEvent history.",
          "It helps you see action memory, Watch memory, manual-source learning, and gate-risk pressure. It is not a new review gate, not external claim evidence, and not approval for low-risk Action.",
          `${suggestedButton(language, "Records / Trajectory")} Use Records to inspect individual decisions, or Trajectory to see how those decisions became learning history.`,
        ]
      );
    }

    if (watchFollowupQuestion) {
      return formatAnswer(
        language,
        [
          "Add Watch Follow-up appends an observation to the current Watch item. It does not close the item and does not convert it into Action.",
          "Use it to record new evidence, remaining uncertainty, the next review date, and whether the Watch is moving toward Action, Reject, or Continue Watching.",
          `${suggestedButton(language, "Add Watch Follow-up")} Fill follow-up result and evidence update, then click it. The record appears in Trajectory while the item remains in Watch until a later review decision.`,
        ]
      ,
        [
          "Add Watch Follow-up appends an observation to the current Watch item. It does not close the item and does not convert it into Action.",
          "Use it to record new evidence, remaining uncertainty, the next review date, and whether the Watch is moving toward Action, Reject, or Continue Watching.",
          `${suggestedButton(language, "Add Watch Follow-up")} Fill follow-up result and evidence update, then click it. The record appears in Trajectory while the item remains in Watch until a later review decision.`,
        ]
      );
    }

    if (asksFinalTakeawayConfirmation(question, pageText)) {
      return formatAnswer(
        language,
        [
          "Final Takeaway Handoff is a provenance chip in Review Inbox.",
          "It means the candidate came from Send Final Takeaway to Review after Andy confirmed a Final Takeaway artifact.",
          "Manual Override can still appear beside it when the ordinary Project Takeaway gate was blocked.",
          "The chip does not bypass verification gates or blocked_downstream_actions, and it is not approval for low-risk Action.",
          "The candidate still needs human Review Inbox review before it becomes durable project memory or any Action path.",
        ]
      ,
        [
          "Final Takeaway Handoff is a provenance chip in Review Inbox.",
          "It means the candidate came from Send Final Takeaway to Review after Andy confirmed a Final Takeaway artifact.",
          "Manual Override can still appear beside it when the ordinary Project Takeaway gate was blocked.",
          "The chip does not bypass verification gates or blocked_downstream_actions, and it is not approval for low-risk Action.",
          "The candidate still needs human Review Inbox review before it becomes durable project memory or any Action path.",
        ]
      );
    }

    if (asksEvidenceGroundingOrGateSnapshot(question)) {
      return formatAnswer(
        language,
        [
          "Verified Insight Object / Evidence Grounding / Gate Snapshot is a read-only diagnostic area on Signal Detail or Project Review Inbox, not a new verification conclusion.",
          "Verified Insight Object summarizes existing verification_status, claim support, confidence, and downstream gate metadata into a product view. It does not create evidence or override backend gates.",
          "Gate Snapshot only projects the current allowed_downstream_actions / blocked_downstream_actions; missing entries are not new recommendations.",
          "This view does not change verification_status, does not unlock actions, and must not be used as input to any gate decision. The actual gate remains the verification metadata and backend gate logic.",
        ]
      ,
        [
          "Verified Insight Object / Evidence Grounding / Gate Snapshot is a read-only diagnostic area on Signal Detail or Project Review Inbox, not a new verification conclusion.",
          "Verified Insight Object summarizes existing verification_status, claim support, confidence, and downstream gate metadata into a product view. It does not create evidence or override backend gates.",
          "Gate Snapshot only projects the current allowed_downstream_actions / blocked_downstream_actions; missing entries are not new recommendations.",
          "This view does not change verification_status, does not unlock actions, and must not be used as input to any gate decision. The actual gate remains the verification metadata and backend gate logic.",
        ]
      );
    }

    if (meaningQuestion) {
      return formatAnswer(
        language,
        [
          "This is the Project Takeaway Review Inbox. It is for human review of candidates that entered project-level judgment from signal or knowledge workflows.",
          "It is not an upload surface or a normal Signal list. It decides whether candidate project memory should be Confirmed, Watched, Actioned, Rejected, or retained as learning memory.",
          "The Watch, Action, and Learning Memory panels show follow-up queues that may need attention first.",
        ]
      ,
        [
          "This is the Project Takeaway Review Inbox. It is for human review of candidates that entered project-level judgment from signal or knowledge workflows.",
          "It is not an upload surface or a normal Signal list. It decides whether candidate project memory should be Confirmed, Watched, Actioned, Rejected, or retained as learning memory.",
          "The Watch, Action, and Learning Memory panels show follow-up queues that may need attention first.",
        ]
      );
    }

    return formatAnswer(
      language,
      [
        "This is Project Review Inbox. Next, handle the queue that needs human judgment most urgently.",
        `${suggestedButton(language, "Watch Due / Action Due / Pending")} If Watch or Action items are due, open those cards first; otherwise start from Pending and decide Confirm, Watch, Action, or Reject.`,
      ]
    ,
      [
        "This is Project Review Inbox. Next, handle the queue that needs human judgment most urgently.",
        `${suggestedButton(language, "Watch Due / Action Due / Pending")} If Watch or Action items are due, open those cards first; otherwise start from Pending and decide Confirm, Watch, Action, or Reject.`,
      ]
    );
  }

  if (isTrajectoryTimeline) {
    const asksManualIntent = hasAny(normalize(question), [
      "source intent",
      "upload reason mix",
      "manual source contribution",
      "cognitive layer mix",
      "manual source",
    ]);
    const asksOpenReviewRecord = hasAny(normalize(question), ["open review record", "review record"]);
    if (asksEvidenceGroundingOrGateSnapshot(question)) {
      return formatAnswer(
        language,
        [
          "Verified Insight Object is a read-only event-boundary summary on Trajectory, not a new verification conclusion.",
          "It projects recorded outcome, verification_status, confidence, claim risk, and blocked_downstream_actions into a review-history view.",
          "It does not reopen review, create evidence, change verification_status, or change Action eligibility; in short, it does not change Action eligibility.",
        ]
      ,
        [
          "Verified Insight Object is a read-only event-boundary summary on Trajectory, not a new verification conclusion.",
          "It projects recorded outcome, verification_status, confidence, claim risk, and blocked_downstream_actions into a review-history view.",
          "It does not reopen review, create evidence, change verification_status, or change Action eligibility; in short, it does not change Action eligibility.",
        ]
      );
    }
    if (asksOpenReviewRecord) {
      return formatAnswer(
        language,
        [
          "Open Review Record opens the single Project Takeaway judgment record behind a Trajectory review event.",
          "Use it to inspect outcome, reason, verification gate, claim support, and source context. It is read-only and does not change Trajectory or rerun review.",
          `${suggestedButton(language, "Open Review Record")} Open the record first when auditing this decision; return to Review Inbox if you need to continue handling the candidate.`,
        ]
      ,
        [
          "Open Review Record opens the single Project Takeaway judgment record behind a Trajectory review event.",
          "Use it to inspect outcome, reason, verification gate, claim support, and source context. It is read-only and does not change Trajectory or rerun review.",
          `${suggestedButton(language, "Open Review Record")} Open the record first when auditing this decision; return to Review Inbox if you need to continue handling the candidate.`,
        ]
      );
    }
    if (asksManualIntent) {
      return formatAnswer(
        language,
        [
          "Manual Source Contribution and Source Intent Mix explain how manual-upload material is showing up in review and trajectory memory.",
          "Upload Reason, Intended Use, and Cognitive Layer describe why the user uploaded it and how it was meant to be used; they are not verification evidence and do not change action gates.",
          `${suggestedButton(language, "Review Inbox")} If a manual-source event should become project judgment, return to Review Inbox and use Confirm, Watch, Action, or Reject.`,
        ]
      ,
        [
          "Manual Source Contribution and Source Intent Mix explain how manual-upload material is showing up in review and trajectory memory.",
          "Upload Reason, Intended Use, and Cognitive Layer describe why the user uploaded it and how it was meant to be used; they are not verification evidence and do not change action gates.",
          `${suggestedButton(language, "Review Inbox")} If a manual-source event should become project judgment, return to Review Inbox and use Confirm, Watch, Action, or Reject.`,
        ]
      );
    }
  }

  const knownPageAnswer = buildKnownPageGuidance(path, meaningQuestion, language);
  if (knownPageAnswer) return knownPageAnswer;

  if (isSignalTimeline) {
    const hasFilters = pageText.includes("filters");
    const hasTimeout = pageText.includes("signal refresh timed out") || pageText.includes("timeline could not load");
    const hasDateModeSummary =
      pageText.includes("latest collection batch") ||
      pageText.includes("latest information date") ||
      pageText.includes("collection batch");
    const asksDateModeQuestion = hasAny(normalize(question), [
      "collection batch",
      "information date",
      "latest collection",
      "latest information",
      "s3",
      "published date",
      "collected date",
    ]);

    if (hasDateModeSummary && asksDateModeQuestion) {
      return formatAnswer(
        language,
        [
          "Latest collection batch shows when signals entered the backend snapshot, which is the closest UI check for a same-day S3 signal batch.",
          "Latest information date shows when those signals were published or originated. The timeline defaults to Information date, so a May 30 S3 batch can still appear under May 29 if the source items were published on May 29.",
          `${suggestedButton(language, "Collection batch")} Use this mode when you are checking whether today's backend/S3 pickup succeeded.`,
        ]
      ,
        [
          "Latest collection batch shows when signals entered the backend snapshot, which is the closest UI check for a same-day S3 signal batch.",
          "Latest information date shows when those signals were published or originated. The timeline defaults to Information date, so a May 30 S3 batch can still appear under May 29 if the source items were published on May 29.",
          `${suggestedButton(language, "Collection batch")} Use this mode when you are checking whether today's backend/S3 pickup succeeded.`,
        ]
      );
    }

    if (hasTimeout) {
      if (meaningQuestion) {
        return formatAnswer(
          language,
          [
            "This is the Signal timeline. It lets you browse collected signals by collection date or publication date.",
            "The timeout message means the latest refresh may not have completed, but the visible list can still be used.",
          ]
        ,
          [
            "This is the Signal timeline. It lets you browse collected signals by collection date or publication date.",
            "The timeout message means the latest refresh may not have completed, but the visible list can still be used.",
          ]
        );
      }
      return formatAnswer(
        language,
        [
          "The timeline still has readable data, but the latest refresh may have timed out.",
          `${suggestedButton(language, "Refresh")} Press it once; if it keeps timing out, check backend snapshot freshness and the /signals response time.`,
          "Do not treat the page as broken yet. You can keep using the visible list.",
        ]
      ,
        [
          "The timeline still has readable data, but the latest refresh may have timed out.",
          `${suggestedButton(language, "Refresh")} Press it once; if it keeps timing out, check backend snapshot freshness and the /signals response time.`,
          "Do not treat the page as broken yet. You can keep using the visible list.",
        ]
      );
    }

    if (hasFilters) {
      if (meaningQuestion) {
        return formatAnswer(
          language,
          [
            "This is the Signal timeline. Its job is browsing and filtering signals, not making the project decision directly.",
            "The filter bar describes the current list view: status, source, and review scope.",
          ]
        ,
          [
            "This is the Signal timeline. Its job is browsing and filtering signals, not making the project decision directly.",
            "The filter bar describes the current list view: status, source, and review scope.",
          ]
        );
      }
      return formatAnswer(
        language,
        [
          "This is the Signal timeline. The sticky filter bar lets you change status, source, and review scope while scrolling.",
          `${suggestedButton(language, "Open Detail")} Use filters to find the signal, then open detail and decide whether to Reject, Save for Later, Generate Insight, or enter Project Review.`,
        ]
      ,
        [
          "This is the Signal timeline. The sticky filter bar lets you change status, source, and review scope while scrolling.",
          `${suggestedButton(language, "Open Detail")} Use filters to find the signal, then open detail and decide whether to Reject, Save for Later, Generate Insight, or enter Project Review.`,
        ]
      );
    }

    if (meaningQuestion) {
      return formatAnswer(
        language,
        [
          "This is the Signal list page. It is for browsing signals already collected by the system.",
          "It does not directly complete Workspace or Project Review decisions. Use the list to inspect title, status, source, dates, and gate warnings, then open the right detail page.",
        ]
      ,
        [
          "This is the Signal list page. It is for browsing signals already collected by the system.",
          "It does not directly complete Workspace or Project Review decisions. Use the list to inspect title, status, source, dates, and gate warnings, then open the right detail page.",
        ]
      );
    }

    return formatAnswer(
      language,
      [
        "This is the Signal list. Next, choose one signal worth handling.",
        `${suggestedButton(language, "Open Detail")} Open the detail page before deciding Reject, Save for Later, Generate Insight, or Project Review.`,
      ]
    ,
      [
        "This is the Signal list. Next, choose one signal worth handling.",
        `${suggestedButton(language, "Open Detail")} Open the detail page before deciding Reject, Save for Later, Generate Insight, or Project Review.`,
      ]
    );
  }

  if (!isSignalDetail) return buildUnknownPageGuidance(path, meaningQuestion, language);

  const isRejected = pageText.includes("rejected");
  const isCompleted = pageText.includes("completed in workspace") || pageText.includes("workspace record is already saved");
  const isAnalyzed = pageText.includes("analyzed");
  const hasActionGate =
    pageText.includes("action gate") ||
    pageText.includes("do not act") ||
    pageText.includes("blocked") ||
    pageText.includes("review claim checks");
  const hasPartialVerification =
    pageText.includes("partially verified") ||
    pageText.includes("unsupported") ||
    pageText.includes("contradicted");
  const hasProjectReview = pageText.includes("project review inbox");
  const hasAiDiscussion = pageText.includes("ai discussion");
  const hasCompletionNote = pageText.includes("completion note");
  const hasDeepProjectMatch = pageText.includes("deep project match review") || pageText.includes("deep project match");

  if (hasCompletionNote && asksReflectionPolish(question, pageText)) {
    return formatAnswer(
      language,
      [
        "AI Polish is scoped to the current Completion Note draft.",
        "It sends the draft through the dedicated reflection-polish path and, on success, records a persisted before/after review pair for human review.",
        "The persisted pair is review context only. It does not save the final reflection, create evidence, change Project Takeaway status, or change action eligibility.",
        `${suggestedButton(language, "AI Polish")} Use it after writing or generating a Completion Note. Then open Reflection Polish Review to approve, request revision, or reject the polished output before using any final reflection text elsewhere.`,
      ]
    ,
      [
        "AI Polish is scoped to the current Completion Note draft.",
        "It sends the draft through the dedicated reflection-polish path and, on success, records a persisted before/after review pair for human review.",
        "The persisted pair is review context only. It does not save the final reflection, create evidence, change Project Takeaway status, or change action eligibility.",
        `${suggestedButton(language, "AI Polish")} Use it after writing or generating a Completion Note. Then open Reflection Polish Review to approve, request revision, or reject the polished output before using any final reflection text elsewhere.`,
      ]
    );
  }

  if (asksFinalTakeawayConfirmation(question, pageText)) {
    return formatAnswer(
      language,
      [
        "Final Takeaway Confirmation keeps Completion Note, Review Bundle, and Project Review as separate steps.",
        "External Synthesis Source is optional long-form review context for the Review Bundle. It can come from paste or .md/.txt/.html upload, but it is not verified external evidence.",
        "If an External Synthesis Source looks like dependency, config, log, very short text, chat export/UI dump, encoding-damaged text, or weak topical overlap, the page shows a non-blocking content-shape warning. That warning is recorded in source and snapshot metadata as review-context audit metadata, but it does not judge truth or change evidence status.",
        "Generate Bundle Draft and the later Final Takeaway actions are available only after Complete Signal. If an External Synthesis Source is loaded or edited, save it first or clear it before generating the bundle.",
        "Completion Note is the draft. Create Snapshot freezes the Review Bundle as an immutable source bundle. Confirm Final Takeaway records Andy's confirmed wording against that snapshot.",
        "After a Final Takeaway is confirmed, Completion Note editing and Complete Signal are locked for that signal. Continue through Send Final Takeaway to Review instead of creating a second Workspace completion path.",
        "Confirm Final Takeaway creates durable artifacts only. Send Final Takeaway to Review is the later confirmed_final_takeaway provider path that creates a Project Takeaway candidate for Review Inbox.",
        "In Review Inbox, the Final Takeaway Handoff chip is provenance: it means the candidate came from Send Final Takeaway to Review, while Manual Override still means the ordinary Project Takeaway gate was blocked.",
        "That provider does not bypass verification gates or blocked_downstream_actions. If the ordinary gate is blocked, the UI requires an explicit Final Takeaway override before handoff.",
        "The candidate still needs human Review Inbox review before it becomes durable project memory or any Action path.",
      ]
    ,
      [
        "Final Takeaway Confirmation keeps Completion Note, Review Bundle, and Project Review as separate steps.",
        "External Synthesis Source is optional long-form review context for the Review Bundle. It can come from paste or .md/.txt/.html upload, but it is not verified external evidence.",
        "If an External Synthesis Source looks like dependency, config, log, very short text, chat export/UI dump, encoding-damaged text, or weak topical overlap, the page shows a non-blocking content-shape warning. That warning is recorded in source and snapshot metadata as review-context audit metadata, but it does not judge truth or change evidence status.",
        "Generate Bundle Draft and the later Final Takeaway actions are available only after Complete Signal. If an External Synthesis Source is loaded or edited, save it first or clear it before generating the bundle.",
        "Completion Note is the draft. Create Snapshot freezes the Review Bundle as an immutable source bundle. Confirm Final Takeaway records Andy's confirmed wording against that snapshot.",
        "After a Final Takeaway is confirmed, Completion Note editing and Complete Signal are locked for that signal. Continue through Send Final Takeaway to Review instead of creating a second Workspace completion path.",
        "Confirm Final Takeaway creates durable artifacts only. Send Final Takeaway to Review is the later confirmed_final_takeaway provider path that creates a Project Takeaway candidate for Review Inbox.",
        "In Review Inbox, the Final Takeaway Handoff chip is provenance: it means the candidate came from Send Final Takeaway to Review, while Manual Override still means the ordinary Project Takeaway gate was blocked.",
        "That provider does not bypass verification gates or blocked_downstream_actions. If the ordinary gate is blocked, the UI requires an explicit Final Takeaway override before handoff.",
        "The candidate still needs human Review Inbox review before it becomes durable project memory or any Action path.",
      ]
    );
  }

  if (asksEvidenceGroundingOrGateSnapshot(question)) {
    return formatAnswer(
      language,
      [
        "Verified Insight Object / Evidence Grounding / Gate Snapshot is a read-only diagnostic area on Signal Detail or Project Review Inbox, not a new verification conclusion.",
        "Verified Insight Object summarizes existing verification_status, claim support, confidence, and downstream gate metadata into a product view. It does not create evidence or override backend gates.",
        "Evidence Grounding only shows raw claim-check counts and coverage: Direct, Partial, Inferred, Unsupported/Contradicted, evidence refs coverage, and source span coverage. It does not create Well-grounded/Thin threshold labels or score source trust.",
        "Source Limits Record shows whether source-stated limits were recorded, explicitly not applicable, or absent. It is source-side provenance for reviewing caveat preservation, not a new source quality score.",
        "Presentation fidelity is also read-only. Source limit exceeded flags claim wording that outruns recorded source-stated limits; source limits coverage gap means no source-stated limits metadata was recorded, not proof that a caveat was stripped.",
        "Gate Snapshot only projects the current allowed_downstream_actions / blocked_downstream_actions into Project Takeaway, Watch, and Low-risk Action rows. If an action is absent from gate metadata, it is shown as not recorded, not as a new recommendation.",
        "This snapshot does not change verification_status, does not unlock actions, and must not be used as input to any gate decision. The actual gate remains the verification metadata and backend gate logic.",
      ]
    ,
      [
        "Verified Insight Object / Evidence Grounding / Gate Snapshot is a read-only diagnostic area on Signal Detail or Project Review Inbox, not a new verification conclusion.",
        "Verified Insight Object summarizes existing verification_status, claim support, confidence, and downstream gate metadata into a product view. It does not create evidence or override backend gates.",
        "Evidence Grounding only shows raw claim-check counts and coverage: Direct, Partial, Inferred, Unsupported/Contradicted, evidence refs coverage, and source span coverage. It does not create Well-grounded/Thin threshold labels or score source trust.",
        "Source Limits Record shows whether source-stated limits were recorded, explicitly not applicable, or absent. It is source-side provenance for reviewing caveat preservation, not a new source quality score.",
        "Presentation fidelity is also read-only. Source limit exceeded flags claim wording that outruns recorded source-stated limits; source limits coverage gap means no source-stated limits metadata was recorded, not proof that a caveat was stripped.",
        "Gate Snapshot only projects the current allowed_downstream_actions / blocked_downstream_actions into Project Takeaway, Watch, and Low-risk Action rows. If an action is absent from gate metadata, it is shown as not recorded, not as a new recommendation.",
        "This snapshot does not change verification_status, does not unlock actions, and must not be used as input to any gate decision. The actual gate remains the verification metadata and backend gate logic.",
      ]
    );
  }

  if (hasAiDiscussion && asksAiDiscussionRecentContext(question, pageText)) {
    return formatAnswer(
      language,
      [
        "AI Discussion uses a short recent conversation context for continuity, not full long-term memory.",
        "Recent discussion context is conversation memory only. It is not AI Radar verified evidence, source support, claim support, or Project Takeaway evidence.",
        "It can help Claude answer follow-up questions more coherently, but it does not change verification status, Project Takeaway gates, or action eligibility.",
      ]
    ,
      [
        "AI Discussion uses a short recent conversation context for continuity, not full long-term memory.",
        "Recent discussion context is conversation memory only. It is not AI Radar verified evidence, source support, claim support, or Project Takeaway evidence.",
        "It can help Claude answer follow-up questions more coherently, but it does not change verification status, Project Takeaway gates, or action eligibility.",
      ]
    );
  }

  if (claimReviewFeedbackQuestion) {
    return formatAnswer(
      language,
      [
        "Not right records claim-level review feedback only.",
        "Choose the reason slot and write a short note about where the claim or insight diverges from your judgment.",
        "Recorded feedback is a read-only list of prior notes for that claim.",
        "Relationship Annotation is also read-only review metadata. It separates relation type, grounding source, derivation mechanism, support posture, and rule-generated review reasons.",
        "The record is review context. It does not change verification_status, claim support, source scoring, background context, Project Takeaway gates, or action eligibility.",
        "Use it when the claim needs later triage, not when you want to prove or disprove the external fact from the UI.",
      ]
    ,
      [
        "Not right records claim-level review feedback only.",
        "Choose the reason slot and write a short note about where the claim or insight diverges from your judgment.",
        "Recorded feedback is a read-only list of prior notes for that claim.",
        "Relationship Annotation is also read-only review metadata. It separates relation type, grounding source, derivation mechanism, support posture, and rule-generated review reasons.",
        "The record is review context. It does not change verification_status, claim support, source scoring, background context, Project Takeaway gates, or action eligibility.",
        "Use it when the claim needs later triage, not when you want to prove or disprove the external fact from the UI.",
      ]
    );
  }

  if (hasAiDiscussion && aiDiscussionThinkingStyleQuestion) {
    return formatAnswer(
      language,
      [
        "Thinking Style: Andy Default is a conversation preference for Claude discussion, not an insight-generation or verification rule.",
        "Evidence grading is always on; tension axis, valence check, and negative ROI gate are used only when the topic triggers them.",
        "It can change how the conversation reasons, but it does not change verification status, claim support, Project Takeaway gates, or action eligibility.",
      ]
    ,
      [
        "Thinking Style: Andy Default is a conversation preference for Claude discussion, not an insight-generation or verification rule.",
        "Evidence grading is always on; tension axis, valence check, and negative ROI gate are used only when the topic triggers them.",
        "It can change how the conversation reasons, but it does not change verification status, claim support, Project Takeaway gates, or action eligibility.",
      ]
    );
  }

  if (hasAiDiscussion && aiDiscussionChallengeQuestion) {
    return formatAnswer(
      language,
      [
        "AI Discussion challenge is an in-conversation check on your reasoning and assumptions, not external factual verification.",
        "It does not change verification status, claim support, or action eligibility. If it challenges a judgment, reply continue, stop, or go deeper.",
      ]
    ,
      [
        "AI Discussion challenge is an in-conversation check on your reasoning and assumptions, not external factual verification.",
        "It does not change verification status, claim support, or action eligibility. If it challenges a judgment, reply continue, stop, or go deeper.",
      ]
    );
  }

  if (hasDeepProjectMatch) {
    if (meaningQuestion) {
      return formatAnswer(
        language,
        [
          "Deep Project Match means this signal appears project-relevant, but the project fit is not strong enough to move straight into Confirm or Action.",
          "It asks you to separate the external signal fact, the matching AI Radar module, the match type, and the evidence boundary.",
        ]
      ,
        [
          "Deep Project Match means this signal appears project-relevant, but the project fit is not strong enough to move straight into Confirm or Action.",
          "It asks you to separate the external signal fact, the matching AI Radar module, the match type, and the evidence boundary.",
        ]
      );
    }
    return formatAnswer(
      language,
      [
        `${suggestedButton(language, "Generate Deep Match Analysis")} Use this optional button when the basic checklist is too generic; it generates a metadata-tier hypothesis paragraph and structured review fields, not a full-source conclusion.`,
        `${suggestedButton(language, "Project Review Inbox")} Read the Deep Project Match checklist first, then adjust the Review note before sending or reviewing the candidate.`,
        "If Source Claim Reading appears, check source claim reliability and claim type first; it describes what the source asserts and does not make the signal verified.",
        "If the matched project or relevant module is unclear, prefer Watch. If the fit is only analogous, do not treat it as source-proven external evidence.",
        "The Review note should state which AI Radar module this signal maps to, why it matters, and which part is still internal judgment.",
      ]
    ,
      [
        `${suggestedButton(language, "Generate Deep Match Analysis")} Use this optional button when the basic checklist is too generic; it generates a metadata-tier hypothesis paragraph and structured review fields, not a full-source conclusion.`,
        `${suggestedButton(language, "Project Review Inbox")} Read the Deep Project Match checklist first, then adjust the Review note before sending or reviewing the candidate.`,
        "If Source Claim Reading appears, check source claim reliability and claim type first; it describes what the source asserts and does not make the signal verified.",
        "If the matched project or relevant module is unclear, prefer Watch. If the fit is only analogous, do not treat it as source-proven external evidence.",
        "The Review note should state which AI Radar module this signal maps to, why it matters, and which part is still internal judgment.",
      ]
    );
  }

  if (isCompleted) {
    if (meaningQuestion) {
      return formatAnswer(
        language,
        [
          "This page is showing a signal that has already been completed into Workspace.",
          "That means it is no longer just pending information; it has become reusable work context or review memory.",
        ]
      ,
        [
          "This page is showing a signal that has already been completed into Workspace.",
          "That means it is no longer just pending information; it has become reusable work context or review memory.",
        ]
      );
    }
    return formatAnswer(
      language,
      [
        "This signal is already completed into Workspace.",
        `${suggestedButton(language, "Project Review Inbox")} Check whether it became reusable project memory or a review record.`,
        "You can still use AI Discussion for follow-up thinking, but you do not need to complete the same signal again.",
      ]
    ,
      [
        "This signal is already completed into Workspace.",
        `${suggestedButton(language, "Project Review Inbox")} Check whether it became reusable project memory or a review record.`,
        "You can still use AI Discussion for follow-up thinking, but you do not need to complete the same signal again.",
      ]
    );
  }

  if (isRejected) {
    if (meaningQuestion) {
      return formatAnswer(
        language,
        [
          "This page is showing a Rejected signal.",
          "That means the current judgment treats it as low value, weak project fit, or not worth continuing right now.",
        ]
      ,
        [
          "This page is showing a Rejected signal.",
          "That means the current judgment treats it as low value, weak project fit, or not worth continuing right now.",
        ]
      );
    }
    return formatAnswer(
      language,
      [
        "This signal is currently Rejected, so it is treated as low value or not suitable for further processing.",
        `${suggestedButton(language, "Back to Signal Records")} Usually leave it rejected and do not move it into Workspace or Action.`,
        "If the decision looks wrong, review the evidence and reason first before reopening the workflow.",
      ]
    ,
      [
        "This signal is currently Rejected, so it is treated as low value or not suitable for further processing.",
        `${suggestedButton(language, "Back to Signal Records")} Usually leave it rejected and do not move it into Workspace or Action.`,
        "If the decision looks wrong, review the evidence and reason first before reopening the workflow.",
      ]
    );
  }

  if (hasActionGate || hasPartialVerification) {
    if (meaningQuestion) {
      return formatAnswer(
        language,
        [
          "This page is showing a signal with verification or action-gate risk.",
          "That does not mean the signal is useless; it means the evidence is not strong enough for direct action or a strong project conclusion.",
        ]
      ,
        [
          "This page is showing a signal with verification or action-gate risk.",
          "That does not mean the signal is useless; it means the evidence is not strong enough for direct action or a strong project conclusion.",
        ]
      );
    }
    return formatAnswer(
      language,
      [
        "This signal currently has a verification or action gate warning.",
        `${suggestedButton(language, hasProjectReview ? "Project Review Inbox" : "Show Decision Map")} Do not take action directly. Review claim checks and source spans first when present; external claim checks test source evidence, while project relevance judgments are internal fit interpretations, not source-proven external facts.`,
        hasProjectReview
          ? "If it is project-relevant, use Project Review Inbox and choose Watch, Reject, or Confirm only when evidence is strong enough."
          : "If evidence is weak, prefer Save for Later or review rather than completing it into Workspace.",
      ]
    ,
      [
        "This signal currently has a verification or action gate warning.",
        `${suggestedButton(language, hasProjectReview ? "Project Review Inbox" : "Show Decision Map")} Do not take action directly. Review claim checks and source spans first when present; external claim checks test source evidence, while project relevance judgments are internal fit interpretations, not source-proven external facts.`,
        hasProjectReview
          ? "If it is project-relevant, use Project Review Inbox and choose Watch, Reject, or Confirm only when evidence is strong enough."
          : "If evidence is weak, prefer Save for Later or review rather than completing it into Workspace.",
      ]
    );
  }

  if (isAnalyzed) {
    if (meaningQuestion) {
      return formatAnswer(
        language,
        [
          "This page is showing an analyzed signal that has not yet become a final Workspace record.",
          "That means the analysis is readable, but you still need to decide whether to save, review, or complete it.",
        ]
      ,
        [
          "This page is showing an analyzed signal that has not yet become a final Workspace record.",
          "That means the analysis is readable, but you still need to decide whether to save, review, or complete it.",
        ]
      );
    }
    return formatAnswer(
      language,
      [
        "This signal has been analyzed, but it is not yet a final Workspace record.",
        hasCompletionNote
          ? `${suggestedButton(language, "Generate Draft / Save Note")} Write a Completion Note and check whether it contains a reusable judgment.`
          : `${suggestedButton(language, "Generate Insight / Project Review Inbox")} Decide whether the analysis is valuable enough to Save, Reject, or move into Project Review.`,
        hasAiDiscussion ? "If you are unsure, use AI Discussion to ask about impact, evidence, or project relevance first." : "",
      ]
    ,
      [
        "This signal has been analyzed, but it is not yet a final Workspace record.",
        hasCompletionNote
          ? `${suggestedButton(language, "Generate Draft / Save Note")} Write a Completion Note and check whether it contains a reusable judgment.`
          : `${suggestedButton(language, "Generate Insight / Project Review Inbox")} Decide whether the analysis is valuable enough to Save, Reject, or move into Project Review.`,
        hasAiDiscussion ? "If you are unsure, use AI Discussion to ask about impact, evidence, or project relevance first." : "",
      ]
    );
  }

  return formatAnswer(
    language,
    meaningQuestion
      ? [
          "This is a signal detail page. It gathers source, status, analysis, verification gates, and project-review entry points for one signal.",
          "The core question is not immediate execution; it is whether this signal deserves insight work, Workspace completion, or Project Review.",
        ]
      : [
          "This is a signal detail page.",
          `${suggestedButton(language, "Generate Insight / Reject")} Judge value first: Reject low-value items, Save for Later if it may matter later, or Generate Insight / enter Project Review if it is worth deeper work.`,
          hasAiDiscussion ? "If you are unsure, use AI Discussion to clarify impact, risk, and project relevance first." : "",
        ]
  ,
    meaningQuestion
      ? [
          "This is a signal detail page. It gathers source, status, analysis, verification gates, and project-review entry points for one signal.",
          "The core question is not immediate execution; it is whether this signal deserves insight work, Workspace completion, or Project Review.",
        ]
      : [
          "This is a signal detail page.",
          `${suggestedButton(language, "Generate Insight / Reject")} Judge value first: Reject low-value items, Save for Later if it may matter later, or Generate Insight / enter Project Review if it is worth deeper work.`,
          hasAiDiscussion ? "If you are unsure, use AI Discussion to clarify impact, risk, and project relevance first." : "",
        ]
  );
}
