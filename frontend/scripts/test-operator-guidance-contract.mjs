import assert from "node:assert/strict";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";
import vm from "node:vm";

const require = createRequire(import.meta.url);
const ts = require("typescript");

function loadTsModule(relativePath) {
  const sourcePath = join(process.cwd(), relativePath);
  const source = readFileSync(sourcePath, "utf8");
  const compiled = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2020,
    },
  }).outputText;

  const sandbox = {
    exports: {},
    module: { exports: {} },
    require,
  };
  sandbox.exports = sandbox.module.exports;
  vm.runInNewContext(compiled, sandbox, { filename: sourcePath });
  return sandbox.module.exports;
}

const { buildStateAwareGuidanceResponse } = loadTsModule("components/operatorGuidanceState.ts");
const {
  buildGlobalGuidanceAnswer,
  findGuidanceEntry,
} = loadTsModule("components/operatorGuidanceData.ts");
const {
  buildMiniRagGuidanceResponse,
} = loadTsModule("components/operatorGuidanceRetriever.ts");

function runCase(testCase) {
  const answer = buildStateAwareGuidanceResponse(
    testCase.question,
    {
      pathname: testCase.pathname,
      text: testCase.pageText,
    },
    testCase.language || "zh"
  );

  assert.ok(answer, `${testCase.name}: expected a guidance answer`);

  for (const phrase of testCase.mustInclude || []) {
    assert.ok(
      answer.includes(phrase),
      `${testCase.name}: expected answer to include "${phrase}"\n\nActual:\n${answer}`
    );
  }

  for (const phrase of testCase.mustNotInclude || []) {
    assert.ok(
      !answer.includes(phrase),
      `${testCase.name}: expected answer not to include "${phrase}"\n\nActual:\n${answer}`
    );
  }
}

function collectPageRoutes(dir, prefix = "") {
  const routes = [];

  for (const entry of readdirSync(dir)) {
    const fullPath = join(dir, entry);
    const stat = statSync(fullPath);

    if (stat.isDirectory()) {
      routes.push(...collectPageRoutes(fullPath, `${prefix}/${entry}`));
      continue;
    }

    if (entry !== "page.tsx") continue;

    const route = prefix || "/";
    routes.push(route.replace(/\\/g, "/"));
  }

  return routes.sort();
}

const signalListText = [
  "AI Radar Signal Timeline",
  "Latest collection batch",
  "Latest information date",
  "The default timeline uses Information date. If S3 has a newer daily batch, switch to Collection batch to verify backend pickup.",
  "FILTERS All Sources All Review",
  "Open Detail",
  "Open Source",
  "Rejected",
  "Action gate: Do not action yet",
  "Published: 2026/5/20",
  "Collected: 2026/5/24",
].join("\n");

const operatingHomeText = [
  "AI Radar",
  "PRIMARY LOOP",
  "Signal to Strategic Intelligence",
  "Intake",
  "Signal Review",
  "Project Review",
  "Trajectory",
  "REVIEW FOCUS",
  "What Needs Judgment",
  "WORK SURFACES",
  "Open a Surface",
].join("\n");

const manualUploadText = [
  "Manual Upload",
  "Upload text, PDF, or image files",
  "Source link",
  "Upload reason",
  "Intended use",
  "Cognitive layer",
  "Upload Source",
  "Analyze Session",
  "View Signal Records",
  "Saved Manual Sessions",
].join("\n");

const projectReviewInboxText = [
  "Project Takeaway Review Inbox",
  "Review verified signal takeaways before they become confirmed project improvements",
  "Review Loop Follow-up",
  "Watch Due",
  "Action Due",
  "Learning Memory",
  "Pending",
  "Closed",
  "Watch",
  "Action",
  "Records",
].join("\n");

const trajectoryTimelineText = [
  "Trajectory Timeline",
  "Manual Source Contribution",
  "Upload Reason Mix",
  "Intended Use Mix",
  "Cognitive Layer Mix",
  "Open Review Record",
  "Review Inbox",
].join("\n");

const reviewRecordDetailText = [
  "Review Record Detail",
  "Project Review",
  "Decision Snapshot",
  "Reuse Posture",
  "Risk Posture",
  "Review Boundary",
  "Claim Support",
  "Audit Trail",
  "Current Review Record",
  "Not recorded",
  "Open Related Surfaces",
  "Review Records",
  "Trajectory",
].join("\n");

const knownPageCases = [
  {
    name: "architecture page has architecture-scoped guidance",
    pathname: "/architecture",
    pageText: "Architecture Demo five layers ADR Run signal",
    mustInclude: ["Architecture"],
  },
  {
    name: "dev inbox page has dev-inbox-scoped guidance",
    pathname: "/codex-workbench",
    pageText: "Dev Inbox Save draft Mark done Reopen Copy draft Copy local handoff Handoff Draft Quality Gate Filter GitHub read-only loop backend draft store Request type Priority Affected surface Open Codex Cloud GitHub PR Loop",
    mustInclude: [
      "Dev Inbox",
      "development intake",
      "Request type",
      "Affected surface",
      "Draft Quality Gate",
      "backend Dev Inbox draft store",
      "Save draft",
      "Mark done",
      "Reopen",
      "Copy draft",
      "Copy local handoff",
      "Handoff",
      "Inbox filters",
      "GitHub read-only loop",
      "without calling GitHub APIs",
      "Legacy browser drafts",
      "validation",
      "does not write GitHub",
    ],
  },
  {
    name: "admin page has admin-scoped guidance",
    pathname: "/admin",
    pageText: "Admin Operating Home Admin Diagnostics Model Attribution Metrics Lifecycle Diagnostics Operator Guidance",
    mustInclude: ["Admin"],
  },
  {
    name: "background update candidates stay inactive and capture-derived",
    pathname: "/admin/background-update-candidates",
    pageText: "Background Update Candidates Candidate Queue not_me blind_spot inactive_review_only Evidence Boundary Open Signal",
    question: "What does Background Update Candidates mean?",
    language: "en",
    mustInclude: [
      "Background Update Candidates",
      "ADR-0012 Signal claim feedback",
      "read-only downstream candidate queue",
      "not_me / blind_spot",
      "inactive candidates",
      "not external factual evidence",
      "do not update background context",
      "do not change verification_status",
      "Project Takeaway gates",
      "action eligibility",
    ],
    mustNotInclude: ["Signal workflow overview", "Manual Upload", "Action is allowed"],
  },
  {
    name: "operating home has overview-scoped guidance",
    pathname: "/overview",
    pageText: "Operating Home Manual Upload Signals Review Inbox Trajectory Metrics Work Surfaces",
    mustInclude: ["Operating Home", "internal AI Radar shortcut surface"],
  },
  {
    name: "dashboard page has dashboard-scoped guidance",
    pathname: "/dashboard",
    pageText: "Dashboard overview status metrics intelligence",
    mustInclude: ["Dashboard"],
  },
  {
    name: "knowledge page has knowledge-scoped guidance",
    pathname: "/knowledge",
    pageText: "Knowledge Review Queue Candidate Strong Fit Thin Fit Paired Signals Supply signal Demand pain",
    mustInclude: ["Knowledge", "supply", "demand"],
  },
  {
    name: "radar page has radar-scoped guidance",
    pathname: "/radar",
    pageText: "Radar Summary topic momentum strategic signal clusters",
    mustInclude: ["Radar Summary"],
  },
  {
    name: "agent watch page has agent-watch-scoped guidance",
    pathname: "/agent-watch",
    pageText: "Agent Watch Tracking active Newly tracked Heating Sustained Big movers agent-native cloud coding agents ecosystem",
    mustInclude: ["Agent Watch", "tracking"],
  },
  {
    name: "friction signals page has friction-scoped guidance",
    pathname: "/friction-signals",
    pageText: "Friction Signals Tracking active Newly tracked Heating Sustained Big movers product market user flow friction",
    language: "en",
    mustInclude: ["Friction Signals", "tracking states", "big-mover filters"],
  },
  {
    name: "reflections page has reflection-scoped guidance",
    pathname: "/reflections",
    pageText: "Reflections cognitive context observations notes",
    mustInclude: ["Reflections"],
  },
  {
    name: "workspace page has workspace-scoped guidance",
    pathname: "/workspace",
    pageText: "Workspace Review Workbench project memory completion notes strategic insight",
    mustInclude: ["Workspace"],
  },
  {
    name: "feed page has feed-scoped guidance",
    pathname: "/feed",
    pageText: "Feed source raw content intake",
    mustInclude: ["Feed"],
  },
  {
    name: "admin subscriptions page explains cloud sync boundary",
    pathname: "/admin/subscriptions",
    pageText: "Signal Source & Subscription Settings Cloud sync Save Subscription Settings AWS data pipeline",
    question: "What does Cloud sync mean?",
    language: "en",
    mustInclude: ["Cloud sync", "S3", "scheduled ingestion task"],
    mustNotInclude: ["Signal workflow overview", "Manual Upload", "Project Takeaway Review Inbox"],
  },
  {
    name: "admin subscriptions page explains source health boundary",
    pathname: "/admin/subscriptions",
    pageText: "Signal Source & Subscription Settings Check Source Health invalid feed RSS Atom",
    question: "What does Source Health check?",
    language: "en",
    mustInclude: ["Source Health", "advisory", "Check Source Health"],
    mustNotInclude: ["Signal workflow overview", "Manual Upload", "Project Takeaway Review Inbox"],
  },
  {
    name: "login page has login-scoped guidance",
    pathname: "/login",
    pageText: "Login admin session sign in",
    mustInclude: ["login page", "60 idle minutes", "admin session"],
  },
  {
    name: "saved page has saved-scoped guidance",
    pathname: "/saved",
    pageText: "Saved saved for later retained items",
    mustInclude: ["Saved"],
  },
  {
    name: "settings page has settings-scoped guidance",
    pathname: "/settings/form",
    pageText: "Settings form preferences controls",
    mustInclude: ["Settings"],
  },
  {
    name: "watch learning page has watch-learning-scoped guidance",
    pathname: "/watch-learning",
    pageText: "Watch Learning watch items follow-up learning",
    mustInclude: ["Watch Learning"],
  },
];

const signalDetailGateText = [
  "Signal",
  "Analyzed",
  "Project Review Inbox",
  "Signal Completion Notes",
  "Completion Note",
  "Verification: Partially Verified",
  "Action gate: Do not action yet",
  "Verified Insight Object",
  "Evidence Grounding",
  "Gate Snapshot",
  "Source Limits Record",
  "Presentation fidelity",
  "Source limit exceeded",
  "Source limits coverage gap",
  "Direct 0 | Partial 1 | Inferred 4 | Unsupported 0",
  "Project Takeaway Allowed Watch Not recorded Low-risk Action Blocked",
  "Claim checks",
  "AI Discussion",
  "Discussion may challenge assumptions. It does not verify external facts or change action eligibility.",
  "Claude uses recent discussion context for continuity; discussion history is not verified evidence.",
  "Thinking Style: Andy Default",
  "Evidence grading",
  "Tension axis",
  "Valence check",
  "Negative ROI gate",
].join("\n");

const signalDetailRejectedText = [
  "Signal",
  "Rejected",
  "Back to Signal Records",
  "Open Source",
  "AI Discussion",
].join("\n");

const cases = [
  {
    name: "signal lifecycle demo meaning stays architecture-demo scoped",
    pathname: "/architecture/signal-lifecycle-demo",
    pageText: "Signal Lifecycle Demo Node View Event Stream Output View Verification Gate Project Takeaway",
    question: "What is this page?",
    language: "en",
    mustInclude: ["Signal Lifecycle Demo", "Node View", "Event Stream", "Output View"],
    mustNotInclude: ["Signal workflow overview", "Open Detail", "Manual Upload"],
  },
  {
    name: "signal lifecycle demo next step recommends demo views",
    pathname: "/architecture/signal-lifecycle-demo",
    pageText: "Signal Lifecycle Demo Node View Event Stream Output View Verification Gate Project Takeaway",
    question: "What should I do next?",
    language: "en",
    mustInclude: ["Recommended next button: Node View / Event Stream / Output View", "demo model"],
    mustNotInclude: ["Open Detail", "Generate Insight", "Manual Upload"],
  },
  {
    name: "operating home meaning stays home-scoped",
    pathname: "/",
    pageText: operatingHomeText,
    question: "What does this page mean?",
    mustInclude: ["AI Radar operating home", "Intake", "Project Review", "Work Surfaces"],
    mustNotInclude: ["Signal workflow overview", "Completion Note", "Workspace completion"],
  },
  {
    name: "operating home next step recommends a surface",
    pathname: "/",
    pageText: operatingHomeText,
    question: "What should I do next?",
    mustInclude: ["Recommended next button: Signals", "operating home"],
    mustNotInclude: ["Signal workflow overview", "Completion Note"],
  },
  {
    name: "manual upload meaning stays upload-scoped",
    pathname: "/manual",
    pageText: manualUploadText,
    question: "What does this page mean?",
    mustInclude: ["Manual Upload", "upload reason", "Analyze Session"],
    mustNotInclude: ["Signal workflow overview", "Confirm, Watch, Action", "Project Takeaway Review Inbox"],
  },
  {
    name: "manual upload next step recommends analyze session",
    pathname: "/manual",
    pageText: manualUploadText,
    question: "What should I do next?",
    mustInclude: ["Recommended next button: Analyze Session", "source link"],
    mustNotInclude: ["Signal workflow overview", "Watch Due", "Pending"],
  },
  {
    name: "manual upload source-stated limits guidance stays provenance-scoped",
    pathname: "/manual",
    pageText: "Manual Upload Source link Upload reason Intended use Cognitive layer Source-stated limits Source-stated confidence Analyze Session",
    question: "What should I fill in Manual Upload before Analyze Session?",
    language: "en",
    mustInclude: ["Manual Upload", "source-stated limits", "Analyze Session"],
    mustNotInclude: ["Project Takeaway gate bypass", "source-quality score", "Action is allowed"],
  },
  ...knownPageCases.flatMap((knownCase) => [
    {
      name: `${knownCase.name} meaning`,
      pathname: knownCase.pathname,
      pageText: knownCase.pageText,
      question: "What does this page mean?",
      mustInclude: knownCase.mustInclude,
      mustNotInclude: ["Signal workflow overview", "Completion Note", "Open Detail"],
    },
    {
      name: `${knownCase.name} next step`,
      pathname: knownCase.pathname,
      pageText: knownCase.pageText,
      question: "What should I do next?",
      mustInclude: ["Recommended next button"],
      mustNotInclude: ["Signal workflow overview", "Completion Note", "Open Detail"],
    },
  ]),
  {
    name: "admin page explains operating home in English guidance",
    pathname: "/admin",
    pageText: "Admin Operating Home Admin Diagnostics Model Attribution Metrics Lifecycle Diagnostics Operator Guidance",
    question: "What is this page?",
    language: "en",
    mustInclude: ["Admin", "Operating Home", "internal AI Radar operating overview"],
    mustNotInclude: ["Signal workflow overview", "Completion Note", "Open Detail"],
  },
  {
    name: "background update candidate confirm dismiss stays ledger-only",
    pathname: "/admin/background-update-candidates",
    pageText: "Background Update Candidates Candidate Queue not_me blind_spot inactive_review_only Evidence Boundary Confirm Dismiss Latest decision Open Signal",
    question: "What should I do with Confirm or Dismiss?",
    language: "en",
    mustInclude: [
      "Recommended next button: Confirm.",
      "latest decision",
      "Confirm",
      "Dismiss",
      "Neither button applies a background update",
    ],
    mustNotInclude: ["Signal workflow overview", "Manual Upload", "Action is allowed"],
  },
  {
    name: "reflection polish review stays human-review scoped",
    pathname: "/admin/reflection-polish",
    pageText: "Reflection Polish Review Original Draft Polished Output Human Review Meaning preservation User voice No new claims Record Review",
    question: "What is this page?",
    language: "en",
    mustInclude: [
      "Reflection Polish Review",
      "human review surface",
      "original draft",
      "polished output",
      "reviewer outcome",
      "six checklist dimensions",
      "does not save the final reflection",
      "create evidence",
      "Project Takeaway",
      "action eligibility",
    ],
    mustNotInclude: ["Signal workflow overview", "Manual Upload", "Action is allowed"],
  },
  {
    name: "reflection polish record review does not save memory or evidence",
    pathname: "/admin/reflection-polish",
    pageText: "Reflection Polish Review Original Draft Polished Output Human Review Record Review Final Reflection Text",
    question: "What should I do with Record Review?",
    language: "en",
    mustInclude: [
      "Recommended next button: Record Review",
      "Select a pair",
      "Original Draft",
      "Polished Output",
      "six dimensions",
      "human checklist outcome",
      "separate reflection save flow",
    ],
    mustNotInclude: ["Signal workflow overview", "Manual Upload", "Action is allowed"],
  },
  {
    name: "knowledge compact triage guidance explains verdict and project fit",
    pathname: "/knowledge",
    pageText: "Knowledge Convergence Freshness Freshness / Delta New Changed Repeated Pattern Confidence Triage Verdict Watch - no project match Add Project Match First Open Brief Detail",
    question: "What should I do next?",
    language: "en",
    mustInclude: ["Freshness / Delta", "single verdict", "project fit", "Review Inbox", "Brief Detail"],
    mustNotInclude: ["Signal workflow overview", "Manual Upload", "Project Takeaway Review Inbox"],
  },
  {
    name: "nonexistent work page uses conservative fallback",
    pathname: "/experimental/unknown",
    pageText: "Experimental unknown page",
    question: "What does this page mean?",
    mustInclude: ["no more specific page guidance yet"],
    mustNotInclude: ["Signal workflow overview", "Completion Note", "Project Takeaway Review Inbox"],
  },
  {
    name: "project review inbox meaning stays review-scoped",
    pathname: "/workspace/projects/review",
    pageText: projectReviewInboxText,
    question: "What does this page mean?",
    mustInclude: ["Project Takeaway Review Inbox", "human review", "Watch, Action"],
    mustNotInclude: ["Signal workflow overview", "Manual Upload", "Open Detail"],
  },
  {
    name: "project review inbox next step recommends review queues",
    pathname: "/workspace/projects/review",
    pageText: projectReviewInboxText,
    question: "What should I do next?",
    mustInclude: ["Recommended next button: Watch Due / Action Due / Pending", "Confirm, Watch, Action"],
    mustNotInclude: ["Signal workflow overview", "Analyze Session", "Open Detail"],
  },
  {
    name: "project review inbox watch follow-up explains observation semantics",
    pathname: "/workspace/projects/review",
    pageText: `${projectReviewInboxText}\nAdd Watch Follow-up\nLatest watch observation\nOpen Trajectory`,
    question: "What is Add Watch Follow-up for?",
    language: "en",
    mustInclude: ["Add Watch Follow-up appends an observation", "does not close the item", "Trajectory"],
    mustNotInclude: ["Signal workflow overview", "Generate Insight", "Manual Upload"],
  },
  {
    name: "project review inbox verified insight object stays read-only",
    pathname: "/workspace/projects/review",
    pageText: `${projectReviewInboxText}\nVerified Insight Object\nVerification\nClaims\nProject Takeaway\nLow-risk Action`,
    question: "What does Verified Insight Object mean?",
    language: "en",
    mustInclude: [
      "Verified Insight Object",
      "Project Review Inbox",
      "read-only diagnostic area",
      "verification_status",
      "claim support",
      "downstream gate metadata",
      "does not create evidence",
      "does not change verification_status",
      "does not unlock actions",
    ],
    mustNotInclude: ["Signal workflow overview", "Generate Insight", "Manual Upload"],
  },
  {
    name: "project review inbox reasoning advisory stays visible but non-adjudicating",
    pathname: "/workspace/projects/review",
    pageText: `${projectReviewInboxText}\nReasoning Assessment Advisory\nLoad-bearing packet\nComposition Bridge\nComposed conclusion\nHidden until packet integrity is reviewed\nUnverified pending packet integrity review\nExtra inference load\nApplication Mapping Load\nIntegrity-first review required\nPacket Integrity Check\nReferential consistency warnings\nSignal mismatch\nFraming Checklist\nBenchmark caveat\nArtifact vs evidence\nCapability-list precision\nScope wording\nProducer provenance\nOriginal insight / takeaway\nWarrant + Counter-check\nGenerate Counter-Check\nRegenerate Counter-Check\nLLM counter-check draft\nOriginal insight\nCounter-check alternative\ncross-provider\ncomparison mode\nADR-0015 reviewer-only`,
    question: "What does Reasoning Assessment Advisory mean?",
    language: "en",
    mustInclude: [
      "Reasoning Assessment Advisory",
      "reviewer-only prompt",
      "original insight / takeaway",
      "load-bearing packet",
      "warrant",
      "Composition Bridge",
      "composed conclusion",
      "extra inference load",
      "Application Mapping Load",
      "several projects or modules",
      "Packet Integrity Check",
      "referential consistency warning",
      "stale, misattached, or wrong-signal evidence",
      "composed conclusion is collapsed until packet integrity is reviewed",
      "unverified pending packet integrity review",
      "Framing Checklist",
      "benchmark caveats",
      "artifact/evidence boundaries",
      "precise capability lists",
      "scope wording",
      "producer provenance",
      "counter-conclusion check",
      "Generate Counter-Check",
      "Regenerate Counter-Check",
      "LLM counter-check draft",
      "persisted reviewer-advisory LLM counter-check draft",
      "replaces that draft",
      "reviewer answer",
      "not a system answer",
      "Yes / No / Unclear",
      "opposite conclusion",
      "incompatible conclusion",
      "weaker conclusion",
      "does not change verification_status",
      "does not mutate gates",
      "Project Takeaway gate",
      "blocked_downstream_actions",
      "Action eligibility",
    ],
    mustNotInclude: ["Action is allowed", "Signal workflow overview", "Generate Insight", "Manual Upload"],
  },
  {
    name: "project review inbox framing checklist stays reviewer-only",
    pathname: "/workspace/projects/review",
    pageText: `${projectReviewInboxText}\nReasoning Assessment Advisory\nFraming Checklist\nBenchmark caveat\nArtifact vs evidence\nCapability-list precision\nScope wording\nProducer provenance\nNo keyword-triggered framing warning\nADR-0015 reviewer-only`,
    question: "What does Framing Checklist mean?",
    language: "en",
    mustInclude: [
      "Framing Checklist",
      "reviewer-only",
      "benchmark caveats",
      "artifact/evidence boundaries",
      "precise capability lists",
      "scope wording",
      "producer provenance",
      "polished framing",
      "does not change verification_status",
      "Project Takeaway gate",
      "blocked_downstream_actions",
      "Action eligibility",
    ],
    mustNotInclude: ["Action is allowed", "Signal workflow overview", "Generate Insight", "Manual Upload", "automatic rejection"],
  },
  {
    name: "project review inbox learning profile stays read-only context",
    pathname: "/workspace/projects/review",
    pageText: `${projectReviewInboxText}\nProject Learning Profile\nEvidence Boundary\nGate Risk\nManual Source Learning`,
    question: "What does Project Learning Profile mean?",
    language: "en",
    mustInclude: ["Project Learning Profile", "read-only summary", "ReviewRecord", "CalibrationEvent", "not external claim evidence", "not approval for low-risk Action"],
    mustNotInclude: ["Signal workflow overview", "Analyze Session", "Manual Upload"],
  },
  {
    name: "review record detail meaning stays read-only review scoped",
    pathname: "/workspace/projects/review/record",
    pageText: reviewRecordDetailText,
    question: "What is this page?",
    language: "en",
    mustInclude: ["Review Record Detail", "Decision Snapshot", "read-only judgment memory", "does not reconfirm", "Not recorded", "not approval", "Trajectory"],
    mustNotInclude: ["Signal workflow overview", "Manual Upload", "Action is allowed"],
  },
  {
    name: "review record detail decision snapshot stays read-only derived summary",
    pathname: "/workspace/projects/review/record",
    pageText: reviewRecordDetailText,
    question: "What should I do with Decision Snapshot?",
    language: "en",
    mustInclude: ["Decision Snapshot", "review outcome", "reuse posture", "risk posture", "not a new gate", "Review Boundary"],
    mustNotInclude: ["Action is allowed", "Generate Insight", "Manual Upload"],
  },
  {
    name: "review record detail verified insight object stays record-boundary scoped",
    pathname: "/workspace/projects/review/record",
    pageText: `${reviewRecordDetailText}\nVerified Insight Object\nOutcome\nVerification\nConfidence\nClaims\nLow-risk Action`,
    question: "What does Verified Insight Object mean?",
    language: "en",
    mustInclude: [
      "Verified Insight Object",
      "read-only record-boundary summary",
      "verification_status",
      "claim support",
      "blocked_downstream_actions",
      "does not reconfirm review",
      "does not change Action eligibility",
    ],
    mustNotInclude: ["Action is allowed", "Generate Insight", "Manual Upload"],
  },
  {
    name: "review record detail next step recommends records or trajectory",
    pathname: "/workspace/projects/review/record",
    pageText: reviewRecordDetailText,
    question: "What should I do next?",
    language: "en",
    mustInclude: ["Recommended next button: Review Records", "Recommended next button: Trajectory"],
    mustNotInclude: ["Open Detail", "Generate Insight"],
  },
  {
    name: "review record detail audit trail stays audit-context scoped",
    pathname: "/workspace/projects/review/record",
    pageText: reviewRecordDetailText,
    question: "What is the Audit Trail?",
    language: "en",
    mustInclude: ["Audit Trail", "calibration events", "Current Review Record", "audit context", "does not make the source more verified"],
    mustNotInclude: ["Action is allowed", "Generate Insight", "Manual Upload"],
  },
  {
    name: "trajectory manual source intent stays non-verification",
    pathname: "/workspace/projects/trajectory",
    pageText: trajectoryTimelineText,
    question: "What does Source Intent Mix mean?",
    language: "en",
    mustInclude: ["Source Intent Mix", "manual-upload material", "not verification evidence", "Review Inbox"],
    mustNotInclude: ["Action is allowed", "Signal workflow overview", "Generate Insight"],
  },
  {
    name: "trajectory open review record explains read-only audit path",
    pathname: "/workspace/projects/trajectory",
    pageText: trajectoryTimelineText,
    question: "What is Open Review Record for?",
    language: "en",
    mustInclude: ["Open Review Record", "Trajectory review event", "read-only", "Review Inbox"],
    mustNotInclude: ["Action is allowed", "Generate Insight", "Manual Upload"],
  },
  {
    name: "trajectory verified insight object stays event-boundary scoped",
    pathname: "/workspace/projects/trajectory",
    pageText: `${trajectoryTimelineText}\nVerified Insight Object\nOutcome\nVerification\nConfidence\nClaims\nLow-risk Action`,
    question: "What does Verified Insight Object mean?",
    language: "en",
    mustInclude: [
      "Verified Insight Object",
      "read-only event-boundary summary",
      "verification_status",
      "claim risk",
      "blocked_downstream_actions",
      "does not reopen review",
      "does not change Action eligibility",
    ],
    mustNotInclude: ["Action is allowed", "Generate Insight", "Manual Upload"],
  },
  {
    name: "signal timeline explains collection batch versus information date",
    pathname: "/signals",
    pageText: signalListText,
    question: "Why does S3 have today's data but the timeline top date is older?",
    language: "en",
    mustInclude: ["Latest collection batch", "Latest information date", "Information date", "S3 batch", "Collection batch"],
    mustNotInclude: ["Manual Upload", "Project Takeaway"],
  },
  {
    name: "signal list page meaning stays list-scoped",
    pathname: "/signals",
    pageText: signalListText,
    question: "What does this page mean?",
    mustInclude: ["Signal timeline", "browsing and filtering"],
    mustNotInclude: ["Completion Note", "Workspace completion", "already completed into Workspace", "Project Takeaway"],
  },
  {
    name: "signal list next step recommends opening detail",
    pathname: "/signals",
    pageText: signalListText,
    question: "What should I do next?",
    mustInclude: ["Recommended next button: Open Detail", "open detail"],
    mustNotInclude: ["Completion Note", "already completed into Workspace", "Project Takeaway"],
  },
  {
    name: "signal starred explains bookmark semantics",
    pathname: "/signals",
    pageText: `${signalListText}\nStarred\nQuick return`,
    question: "What does Starred mean on a signal?",
    language: "en",
    mustInclude: ["lightweight bookmark", "does not change", "Starred filter", "Save for Later instead"],
    mustNotInclude: ["Workspace completion", "verified"],
  },
  {
    name: "signal detail gate meaning explains verification gate",
    pathname: "/signals/detail",
    pageText: signalDetailGateText,
    question: "What does this page mean?",
    mustInclude: ["verification or action-gate risk", "evidence is not strong enough"],
    mustNotInclude: ["Signal list", "browsing and filtering"],
  },
  {
    name: "signal detail gate next step recommends review path",
    pathname: "/signals/detail",
    pageText: signalDetailGateText,
    question: "What should I do next?",
    mustInclude: ["Recommended next button: Project Review Inbox", "Do not take action directly"],
    mustNotInclude: ["Signal list", "Open Detail"],
  },
  {
    name: "signal detail source spans explain evidence review path",
    pathname: "/signals/detail",
    pageText: `${signalDetailGateText}\nSource span\nParaphrase Grounded To Source Span`,
    question: "What should I do next?",
    language: "en",
    mustInclude: ["Review claim checks and source spans first", "Project Review Inbox"],
    mustNotInclude: ["Signal list", "Open Detail", "Manual Upload"],
  },
  {
    name: "signal detail evidence grounding and gate snapshot stay read-only",
    pathname: "/signals/detail",
    pageText: signalDetailGateText,
    question: "What do Evidence Grounding and Gate Snapshot mean?",
    language: "en",
    mustInclude: [
      "read-only diagnostic area",
      "raw claim-check counts and coverage",
      "does not create Well-grounded/Thin threshold labels",
      "Source Limits Record",
      "source-side provenance",
      "not a new source quality score",
      "Presentation fidelity is also read-only",
      "Source limit exceeded",
      "source limits coverage gap",
      "not proof that a caveat was stripped",
      "allowed_downstream_actions / blocked_downstream_actions",
      "does not change verification_status",
      "does not unlock actions",
      "must not be used as input to any gate decision",
    ],
    mustNotInclude: ["Action is allowed", "Source Value", "Signal workflow overview", "Manual Upload"],
  },
  {
    name: "signal detail verified insight object stays read-only",
    pathname: "/signals/detail",
    pageText: signalDetailGateText,
    question: "What does Verified Insight Object mean?",
    language: "en",
    mustInclude: [
      "Verified Insight Object",
      "read-only diagnostic area",
      "verification_status",
      "claim support",
      "downstream gate metadata",
      "does not create evidence",
      "does not change verification_status",
      "does not unlock actions",
    ],
    mustNotInclude: ["Action is allowed", "Source Value", "Signal workflow overview", "Manual Upload"],
  },
  {
    name: "signal detail not right feedback stays capture-only",
    pathname: "/signals/detail",
    pageText: `${signalDetailGateText}\nClaim Checks\nNot right\nReason\nNote\nFeedback recorded\nRelationship Annotation\nGrounding\nDerivation\nReview Required`,
    question: "What does Relationship Annotation mean?",
    language: "en",
    mustInclude: [
      "claim-level review feedback only",
      "reason slot",
      "diverges from your judgment",
      "Recorded feedback",
      "read-only list",
      "Relationship Annotation",
      "read-only review metadata",
      "grounding source",
      "derivation mechanism",
      "rule-generated review reasons",
      "review context",
      "does not change verification_status",
      "Project Takeaway gates",
      "action eligibility",
      "later triage",
    ],
    mustNotInclude: ["Action is allowed", "updates background context", "proves the external fact", "Manual Upload"],
  },
  {
    name: "signal detail separates project relevance judgment from external claim evidence",
    pathname: "/signals/detail",
    pageText: `${signalDetailGateText}\nProject relevance judgment\nInternal judgment\nRelevance To Projects\nEvidence refs: 0`,
    question: "What should I do next?",
    language: "en",
    mustInclude: ["external claim checks", "project relevance judgments", "internal fit interpretations", "not source-proven external facts"],
    mustNotInclude: ["Signal list", "Manual Upload", "Action is allowed"],
  },
  {
    name: "signal detail deep project match explains review note and module fit",
    pathname: "/signals/detail",
    pageText: `${signalDetailGateText}\nDeep Project Match Review\nGenerate Deep Match Analysis\nSource Claim Reading\nSource claim reliability\nClaim type\nMatched project\nRelevant module\nReview note\nEvidence boundary`,
    question: "What should I do next?",
    language: "en",
    mustInclude: ["Generate Deep Match Analysis", "metadata-tier hypothesis", "not a full-source conclusion", "Source Claim Reading", "source claim reliability", "claim type", "does not make the signal verified", "Deep Project Match checklist", "Review note", "AI Radar module", "internal judgment"],
    mustNotInclude: ["Signal list", "Manual Upload", "Action is allowed"],
  },
  {
    name: "signal detail ai discussion challenge boundary is not verification",
    pathname: "/signals/detail",
    pageText: signalDetailGateText,
    question: "What does AI Discussion challenge assumptions mean?",
    language: "en",
    mustInclude: ["AI Discussion challenge", "not external factual verification", "does not change verification status", "continue", "stop", "go deeper"],
    mustNotInclude: ["Claim checks verify this", "Action is allowed", "Project Takeaway Review Inbox"],
  },
  {
    name: "signal detail thinking style explains trigger-based conversation preference",
    pathname: "/signals/detail",
    pageText: signalDetailGateText,
    question: "What does Thinking Style Andy Default do?",
    language: "en",
    mustInclude: [
      "conversation preference",
      "Evidence grading is always on",
      "tension axis",
      "valence check",
      "negative ROI gate",
      "does not change verification status",
    ],
    mustNotInclude: ["Project Takeaway Review Inbox", "Signal list", "Action is allowed"],
  },
  {
    name: "signal detail ai discussion recent context stays non-evidence",
    pathname: "/signals/detail",
    pageText: signalDetailGateText,
    question: "Does AI Discussion use recent chat history as memory?",
    language: "en",
    mustInclude: [
      "short recent conversation context",
      "not full long-term memory",
      "conversation memory only",
      "not AI Radar verified evidence",
      "Project Takeaway evidence",
      "does not change verification status",
      "action eligibility",
    ],
    mustNotInclude: ["Action is allowed", "Claim checks verify this", "Manual Upload"],
  },
  {
    name: "signal detail ai polish records review pair without saving final reflection",
    pathname: "/signals/detail",
    pageText: [
      signalDetailGateText,
      "Signal Completion Notes",
      "Completion Note",
      "AI Polish",
      "Human review pair",
      "Open Reflection Polish Review",
    ].join("\n"),
    question: "What does AI Polish do?",
    language: "en",
    mustInclude: [
      "AI Polish",
      "Completion Note draft",
      "dedicated reflection-polish path",
      "persisted before/after review pair",
      "human review",
      "does not save the final reflection",
      "create evidence",
      "Project Takeaway",
      "action eligibility",
      "Reflection Polish Review",
    ],
    mustNotInclude: ["Signal workflow overview", "Manual Upload", "Action is allowed"],
  },
  {
    name: "signal detail final takeaway confirmation keeps artifact and handoff steps separate",
    pathname: "/signals/detail",
    pageText: [
      signalDetailGateText,
      "Final Takeaway Confirmation",
      "External Synthesis Source",
      "Review Bundle snapshot to Andy Confirm",
      "Create Snapshot",
      "Confirm Final Takeaway",
      "Send Final Takeaway to Review",
      "confirmed_final_takeaway provider",
    ].join("\n"),
    question: "What does Final Takeaway Confirmation do, and how does Send Final Takeaway to Review work?",
    language: "en",
    mustInclude: [
      "Completion Note is the draft",
      "External Synthesis Source is optional long-form review context",
      ".md/.txt/.html upload",
      "not verified external evidence",
      "non-blocking content-shape warning",
      "chat export/UI dump",
      "encoding-damaged text",
      "weak topical overlap",
      "recorded in source and snapshot metadata",
      "review-context audit metadata",
      "does not judge truth or change evidence status",
      "available only after Complete Signal",
      "save it first or clear it before generating the bundle",
      "immutable source bundle",
      "Andy's confirmed wording",
      "Completion Note editing and Complete Signal are locked",
      "second Workspace completion path",
      "Confirm Final Takeaway creates durable artifacts only",
      "Send Final Takeaway to Review",
      "confirmed_final_takeaway provider path",
      "Final Takeaway Handoff chip is provenance",
      "Project Takeaway candidate for Review Inbox",
      "does not bypass verification gates",
      "blocked_downstream_actions",
      "explicit Final Takeaway override",
      "human Review Inbox review",
    ],
    mustNotInclude: ["Action is allowed", "Claim checks verify this", "Manual Upload"],
  },
  {
    name: "review inbox final takeaway handoff chip explains provenance without bypass",
    pathname: "/workspace/projects/review",
    pageText: [
      "Project Review Inbox",
      "Manual Override",
      "Final Takeaway Handoff",
      "confirmed_final_takeaway provider",
      "Action Blocked",
      "blocked_downstream_actions",
    ].join("\n"),
    question: "What does Final Takeaway Handoff mean here?",
    language: "en",
    mustInclude: [
      "Final Takeaway Handoff is a provenance chip",
      "Send Final Takeaway to Review",
      "Manual Override can still appear",
      "ordinary Project Takeaway gate was blocked",
      "does not bypass verification gates",
      "blocked_downstream_actions",
      "human Review Inbox review",
    ],
    mustNotInclude: ["Action is allowed", "Claim checks verify this", "Manual Upload"],
  },
  {
    name: "signal detail rejected meaning stays rejected-scoped",
    pathname: "/signals/detail",
    pageText: signalDetailRejectedText,
    question: "What does this page mean?",
    mustInclude: ["Rejected signal", "low value"],
    mustNotInclude: ["Signal list", "Completion Note"],
  },
  {
    name: "signal detail rejected next step recommends back navigation",
    pathname: "/signals/detail",
    pageText: signalDetailRejectedText,
    question: "What should I do next?",
    mustInclude: ["Recommended next button: Back to Signal Records", "do not move it into Workspace"],
    mustNotInclude: ["Signal list", "Open Detail"],
  },
];

for (const testCase of cases) {
  runCase(testCase);
}

const discoveredRoutes = collectPageRoutes(join(process.cwd(), "app"));
const routesWithoutOperatorGuidance = new Set(["/portfolio"]);
const appChromeSource = readFileSync(join(process.cwd(), "components/AppChrome.tsx"), "utf8");
assert.ok(
  appChromeSource.includes("if (isPortfolio)") &&
    appChromeSource.indexOf("if (isPortfolio)") < appChromeSource.indexOf("<OperatorGuidanceWidget />"),
  "portfolio must exit to public chrome before Operator Guidance is mounted"
);

const guidanceRoutes = discoveredRoutes.filter((route) => !routesWithoutOperatorGuidance.has(route));
for (const route of guidanceRoutes) {
  const sampleText = `AI Radar route ${route} page title main button status`;

  runCase({
    name: `auto route coverage meaning ${route}`,
    pathname: route,
    pageText: sampleText,
    question: "What does this page mean?",
    mustNotInclude: route.startsWith("/signals")
      ? ["Signal workflow overview"]
      : ["Signal workflow overview", "Completion Note", "Open Detail", "no more specific page guidance yet"],
  });

  runCase({
    name: `auto route coverage next step ${route}`,
    pathname: route,
    pageText: sampleText,
    question: "What should I do next?",
    mustNotInclude: route.startsWith("/signals")
      ? ["Signal workflow overview"]
      : ["Signal workflow overview", "Completion Note", "Open Detail", "dedicated next-step rule"],
  });
}

const metricsLocationAnswer = buildGlobalGuidanceAnswer("Where can I see system metrics?", "en", "/signals");
assert.ok(metricsLocationAnswer, "metrics location question should have global guidance");
assert.ok(
  metricsLocationAnswer.includes("/admin/metrics"),
  `metrics location answer should point to /admin/metrics\n\nActual:\n${metricsLocationAnswer}`
);
assert.ok(
  metricsLocationAnswer.includes("Signals") && metricsLocationAnswer.includes("Metrics"),
  `cross-page metrics answer should disclose current and target scope\n\nActual:\n${metricsLocationAnswer}`
);
assert.ok(
  !metricsLocationAnswer.includes("Signal workflow overview"),
  `metrics location answer must not fall back to signal workflow\n\nActual:\n${metricsLocationAnswer}`
);

assert.equal(
  findGuidanceEntry("Where can I see system metrics?", "/signals"),
  null,
  "metrics location question on /signals must not match signal workflow"
);

const metricsRagAnswer = buildMiniRagGuidanceResponse(
  "Where can I see system metrics?",
  "/signals",
  "zh",
  "Ask what this page means or what to do next. I can suggest the next button and explain the current workflow step."
);
assert.equal(
  metricsRagAnswer,
  null,
  "mini-RAG must not use prior welcome text to turn a metrics question into signal workflow guidance"
);

const frictionWatchAnswer = buildGlobalGuidanceAnswer("How should I handle friction watch?", "en", "/signals");
assert.ok(frictionWatchAnswer, "friction watch question should have global guidance");
assert.ok(
  frictionWatchAnswer.includes("Signals") && frictionWatchAnswer.includes("Friction / Watch"),
  `friction watch answer should disclose cross-page scope\n\nActual:\n${frictionWatchAnswer}`
);
assert.ok(
  frictionWatchAnswer.includes("/friction-signals") && frictionWatchAnswer.includes("/watch-learning"),
  `friction watch answer should point to friction/watch surfaces\n\nActual:\n${frictionWatchAnswer}`
);
assert.ok(
  !frictionWatchAnswer.includes("Signal workflow overview"),
  `friction watch answer must not fall back to signal workflow\n\nActual:\n${frictionWatchAnswer}`
);

const projectTakeawayAnswer = buildGlobalGuidanceAnswer("Where should a Project Takeaway candidate be reviewed?", "en", "/manual");
assert.ok(projectTakeawayAnswer, "project takeaway question should have global guidance");
assert.ok(
  projectTakeawayAnswer.includes("Manual Upload") && projectTakeawayAnswer.includes("Project Takeaway"),
  `project takeaway answer should disclose cross-page scope\n\nActual:\n${projectTakeawayAnswer}`
);
assert.ok(
  projectTakeawayAnswer.includes("/workspace/projects/review") && projectTakeawayAnswer.includes("Candidate"),
  `project takeaway answer should point to review inbox and candidate boundary\n\nActual:\n${projectTakeawayAnswer}`
);

const manualSourceAnswer = buildGlobalGuidanceAnswer("What does manual upload source intent mean?", "en", "/workspace/projects/review");
assert.ok(manualSourceAnswer, "manual source question should have global guidance");
assert.ok(
  manualSourceAnswer.includes("Project Review Inbox") && manualSourceAnswer.includes("Manual Source"),
  `manual source answer should disclose cross-page scope\n\nActual:\n${manualSourceAnswer}`
);
assert.ok(
  manualSourceAnswer.includes("/manual") && manualSourceAnswer.includes("Analyze Session"),
  `manual source answer should point to manual intake flow\n\nActual:\n${manualSourceAnswer}`
);

console.log(`Guidance contract tests passed: ${cases.length + guidanceRoutes.length * 2} (${guidanceRoutes.length} guidance-enabled routes; ${routesWithoutOperatorGuidance.size} public route excluded by contract)`);
