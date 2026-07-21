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
    "有什么用",
    "用来",
    "做什么",
    "下一步",
    "怎么做",
    "什么意思",
    "为什么",
    "解释",
    "建议",
  ]);
}

function asksPageMeaning(question: string) {
  const text = normalize(question);
  return hasAny(text, ["meaning", "means", "explain", "what is this page", "这个页面", "是什么意思", "解释"]);
}

function asksActionRecommendation(question: string) {
  const text = normalize(question);
  return hasAny(text, ["next", "what should", "what do", "do next", "recommend", "下一步", "怎么做", "建议"]);
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
  return language === "zh" ? `推荐下一步按钮：${label}。` : `Recommended next button: ${label}.`;
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
      "这是 Signal Lifecycle Demo 页面，用静态 fixture 展示同一条 signal 在 Node View、Event Stream 和 Output View 里的关系。",
      "它是架构说明面，不是实时 Signal workflow，不做证据验证，也不是 Project Takeaway confirmation 路径。",
    ],
    zhNext: [
      "先用 Node View 看关系形状，用 Event Stream 看生命周期顺序，用 Output View 看 review-state 输出；然后再去 Signals、Knowledge 或 Project Review 查看真实数据。",
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
      "这是 Architecture 页面，用来展示 AI Radar 的系统架构、ADR、分层职责和从外部 signal 到结构化 intelligence 的工作流。",
      "它是产品内部架构 walkthrough，不是普通 Signal review，也不是 Project Takeaway 审查队列。",
    ],
    zhNext: ["先看五层架构和 ADR 说明；如果想看静态关系 demo，打开 Three-view demo；如果你想验证真实数据流，再点 Run signal 或进入 Signals / Knowledge / Workspace 对应页面。"],
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
      "Background Update Candidates 是 ADR-0012 Signal claim feedback 的只读下游候选队列。",
      "它只从 not_me / blind_spot feedback 派生 inactive candidates；这些 candidate 不是外部事实证据，不会更新 background context，也不会改变 verification_status、Project Takeaway gates 或 action eligibility。",
    ],
    zhNext: [
      "先看 reason slot、feedback note、claim snapshot 和 boundary flags；需要追溯上下文时打开原 Signal。只有未来单独确认的 background update 流程才能应用候选。",
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
      "Reflection Polish Review 是 reflection-polish 的人工审查页面，用来比较 original draft 和 polished output，并记录 reviewer outcome。",
      "这个页面只记录 human-in-loop checklist 判断；它不会保存 final reflection，不会创建 evidence，不会进入 Project Takeaway，也不会改变 action eligibility。",
    ],
    zhNext: [
      "先选择一个 pair，对比 Original Draft 和 Polished Output，再检查六个维度。只有人工判断通过时才用 Record Review 写入 review outcome；如果需要正式保存反思，仍然走单独的 reflection save flow。",
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
      "这是 Admin 区域，用来查看系统设置、诊断、指标、订阅和后台运行状态。",
      "这里主要是运维和配置入口，不是 Signal review 或 Project Takeaway 判断页面。",
    ],
    zhNext: ["如果你在排查系统状态，先看 Admin Diagnostics；如果只是处理内容，回到 Signals、Knowledge 或 Workspace。"],
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
      "这是 Dashboard 页面，用来快速查看 AI Radar 的总体运行和内容概况。",
      "它是观察入口，不是逐条处理 signal 或确认项目记忆的地方。",
    ],
    zhNext: ["如果你要开始处理内容，进入 Signals；如果你要看更具体的后台健康情况，进入 Admin 或 Metrics。"],
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
      "这是 Knowledge 页面，用来查看综合后的 knowledge briefs、供给/需求配对信号和项目匹配质量。",
      "它关注的是信息是否形成可复用的项目认知，而不是上传原始材料或处理单条 signal。",
    ],
    zhNext: ["先看每张 brief 顶部的供给/需求配对，再看 fit / quality 解释；如果有 Review Queue Candidate，再打开 detail 或进入相关 review。"],
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
      "这是 Radar Summary 页面，用来查看主题动量、趋势聚合和战略信号摘要。",
      "它是高层观察面，不是单条 signal 的处理入口。",
    ],
    zhNext: ["先看哪些主题或趋势正在变强；需要追溯来源时，再回到 Signals 或 Knowledge。"],
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
      "这是 Agent Watch 页面，用来观察 agent-native cloud、coding agents 和相关生态动态，包括 new、heating、sustained、cooling、dropped、revived 等 tracking state。",
      "它是专题监控页面，不是 Project Takeaway review 队列。",
    ],
    zhNext: ["先看 tracking state 和 big movers；如果某条内容需要处理，再打开详情或转入 Signal / Knowledge 工作流。"],
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
      "这是 Friction Signals 页面，用来查看市场、产品或用户流程里的摩擦信号，包括 new、heating、sustained、cooling、dropped、revived 等 advisory tracking states 和 big-mover filters。",
      "它帮助发现阻力和机会，不等同于已经验证的项目结论，也不会自动创建 low-risk Action readiness。",
    ],
    zhNext: ["先看 tracking state 和 big-mover filters，再看 friction 的来源和模式；如果它值得沉淀，再进入 detail、Signal 或 Knowledge 流程。"],
    enMeaning: [
      "This is the Friction Signals page for market, product, or user-flow friction signals, including advisory tracking states like new, heating, sustained, cooling, dropped, and revived.",
      "It helps surface resistance and opportunity, but it is not already-verified project judgment and does not create low-risk Action readiness by itself.",
    ],
    enNext: ["Start with tracking state and big-mover filters, then read the friction pattern. Use detail, Signal, or Knowledge workflow if it should be preserved or paired with Agent Watch supply."],
  },
  {
    match: (path) => path === "/reflections" || path.startsWith("/reflections/"),
    button: "Reflections",
    zhMeaning: [
      "这是 Reflections 页面，用来记录和查看认知上下文、观察和思考。",
      "Reflection 是认知材料，不是外部事实证据；不能直接当作 claim verification。",
    ],
    zhNext: ["先查看或记录 reflection；如果要变成事实证据，需要走单独的 signal / evidence 流程。"],
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
      "这是 Feed 页面，用来查看或调试进入系统的原始 feed / source 内容。",
      "它偏 intake 观察，不是最终 evidence judgment 或 project memory。",
    ],
    zhNext: ["先确认 feed 是否正常进入系统；如果要处理具体条目，进入 Signals。"],
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
      "这是登录页面，用来建立 admin session，访问受保护的 AI Radar 工作页面。",
      "登录凭证只保存在当前浏览器会话中；连续 60 分钟没有受保护页面活动后，需要重新输入账户密码。",
      "它只是认证入口，不承载 signal、knowledge 或 review 判断。",
    ],
    zhNext: ["如果你需要进入受保护页面，先完成登录；如果 session 过期或打开新的浏览器会话，请重新输入账户密码。"],
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
      "这是 Manual Upload 区域，用来把手动找到的文章、PDF、图片或链接放进 AI Radar，并查看手动 session 详情。",
      "它还不是最终项目记忆；内容需要先经过 session analysis，再进入 Signal records、Workspace 或 Project Review。",
    ],
    zhNext: ["如果有新材料，先填 source link / upload reason / intended use 并 Analyze Session；如果在 detail 页，检查分析结果再决定是否进入后续工作流。"],
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
      "这是 Saved 页面，用来查看暂时保留、以后可能有用的内容。",
      "Saved 不等于 verified 或 completed；它只是暂时保留，不应该直接当成项目结论。",
    ],
    zhNext: ["先查看保存原因；如果现在值得处理，再回到 Signals 或对应 detail 页面继续 review。"],
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
      "这是 Settings 区域，用来配置偏好、表单或 reflection 相关设置。",
      "它是配置页面，不是内容 review、evidence gate 或 Project Takeaway 判断页面。",
    ],
    zhNext: ["先确认你要修改的配置项；保存前检查它是否会影响上传、reflection 或工作流显示。"],
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
      "这是 Watch Learning 页面，用来查看 Watch 项和后续学习信号。",
      "它帮助你从等待观察的项目里提取学习，不是新 signal 的 intake 页面。",
    ],
    zhNext: ["先看哪些 Watch 项已经产生新证据或到期；需要决策时回到 Project Review Inbox。"],
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
      "这是 Workspace 区域，用来查看和整理已经进入工作记忆、项目判断或后续输出的内容。",
      "它更接近 durable work surface，不是原始 intake 页面。",
    ],
    zhNext: ["先选择具体工作面：项目 review、trajectory、insights、decisions 或 backlog；不要把未验证内容直接当成最终结论。"],
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
    return formatAnswer(language, entry.zhMeaning, entry.enMeaning);
  }

  return formatAnswer(
    language,
    [`${suggestedButton(language, entry.button)}${entry.zhNext[0] || ""}`, ...entry.zhNext.slice(1)],
    [`${suggestedButton(language, entry.button)} ${entry.enNext[0] || ""}`, ...entry.enNext.slice(1)]
  );
}

function buildUnknownPageGuidance(path: string, meaningQuestion: boolean, language: GuidanceLanguage) {
  if (meaningQuestion) {
    return formatAnswer(
      language,
      [
        "这是 AI Radar 的一个工作页面，但当前还没有更细的页面专属指导。",
        "先以页面标题、主要按钮和可见状态为准；不要把它自动理解成 Signal workflow 或 Project Review。",
      ],
      [
        "This is an AI Radar work page, but there is no more specific page guidance yet.",
        "Use the visible title, primary buttons, and status labels first. Do not automatically treat it as Signal workflow or Project Review.",
      ]
    );
  }

  return formatAnswer(
    language,
    [
      "这个页面还没有专属下一步规则。",
      "下一步先选择页面上最主要的按钮或返回上一级导航；如果涉及证据、Project Review 或 action gate，再进入对应的专门页面判断。",
    ],
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
    "标星",
    "收藏",
    "快速找到",
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
        `${suggestedButton(language, "Save Subscription Settings")}Save first, then use the success banner to confirm whether the AWS pipeline can see the update.`,
      ],
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
        `${suggestedButton(language, "Check Source Health")}Run it before saving a source batch when you want confidence that the AWS daily pipeline can actually parse the feed URLs.`,
      ],
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
      ],
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
          "这是 AI Radar 的操作首页，不是单个 Signal 页面。",
          "它把主流程放在一起：Intake 收集信息，Signal Review 做证据和状态判断，Project Review 做人工判断，Trajectory 查看学习和判断历史。",
          "下面的 Review Focus 和 Work Surfaces 是入口导航，帮助你决定今天从哪个工作面开始。",
        ],
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
        "这里是 AI Radar 的操作首页。下一步取决于你今天要处理什么。",
        `${suggestedButton(language, "Signals")}如果你要处理新收集的信息，先进入 Signals。`,
        "如果你要处理已经进入项目判断的内容，进入 Project Takeaways 或 Workspace。",
      ],
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
          "这是 Manual Upload 页面，用来把你手动找到的文章、PDF、图片或链接放进 AI Radar。",
          "它还不是最终项目记忆。你先补充来源、上传原因、用途和 cognitive layer，再 Analyze Session，让系统生成可继续处理的 manual session。",
          "分析完成后，合适的内容可以继续进入 Signal records、Workspace 或 Project Review。",
        ],
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
        "这里是 Manual Upload。下一步先把来源和用途补完整。",
        `${suggestedButton(language, "Analyze Session")}如果已经填好文件或 source link，就先分析；如果你想看已生成的 signal，点 View Signal Records。`,
      ],
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
          "Verified Insight Object 是 Review Record Detail 上的只读记录边界摘要，不是新的 verification 结论。",
          "它把已记录的 outcome、verification_status、confidence、claim support / claim risk 和 blocked_downstream_actions 投影成回看视图。",
          "它不重新确认 review，不创建 evidence，不修改 verification_status，也不改变 Action eligibility。",
        ],
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
          `${suggestedButton(language, "Review Boundary")}Use Review Boundary to inspect the exact gate and claim-support context.`,
        ],
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
        ],
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
          "这是 Review Record Detail 页面，用来回看一条 Project Takeaway 人工 review decision。",
          "它是只读判断记录：展示 Decision Snapshot、outcome、reason、source context、verification gate、claim support 和相关跳转；它不会重新确认、覆盖或绕过任何 gate。",
          "如果要继续处理同一项目判断，回到 Review Inbox；如果要看它如何进入学习历史，打开 Trajectory。",
        ],
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
        `${suggestedButton(language, "Review Records")}如果你要找同一类判断，回到 Records 列表筛选 project / outcome / quality。`,
        `${suggestedButton(language, "Trajectory")}如果你要看这条记录是否正在影响学习历史，打开 Trajectory。`,
      ],
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
        ],
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
        ],
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
          "Add Watch Follow-up 是给当前 Watch item 追加一条观察记录，不是关闭它，也不是把它变成 Action。",
          "它的用途是记录这次复盘看到的新证据、仍然不确定的地方、下一次 review date，以及这条 Watch 是否开始接近 Action / Reject / Continue Watching。",
          `${suggestedButton(language, "Add Watch Follow-up")}填 follow-up result 和 evidence update 后点击；记录会进入 Trajectory，Watch item 会继续留在 Watch 队列，直到你做新的 review decision。`,
        ],
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
        ],
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
          "Verified Insight Object / Evidence Grounding / Gate Snapshot 是 Signal Detail 或 Project Review Inbox 上的只读诊断区，不是新的 verification 结论。",
          "Verified Insight Object 把现有 verification_status、claim support、confidence 和 downstream gate metadata 汇总成产品视图。它不创建 evidence，也不覆盖后端 gate。",
          "Gate Snapshot 只投影当前 allowed_downstream_actions / blocked_downstream_actions；没有记录的项不能当成新的建议。",
          "这个视图不修改 verification_status，不解锁 action，也不得作为任何 gate 决策输入。真正的 gate 仍然来自 verification metadata 和后端 gate 逻辑。",
        ],
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
          "这是 Project Takeaway Review Inbox，用来人工审查已经从 signal 或 knowledge 流程进入项目判断的候选项。",
          "这里不是上传入口，也不是普通 Signal list。它关注的是候选项目记忆是否应该 Confirm、Watch、Action、Reject，或作为 calibration / learning memory 保留。",
          "上方的 Watch、Action 和 Learning Memory 区块是在提醒你哪些 review follow-up 需要优先处理。",
        ],
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
        "这里是 Project Review Inbox。下一步先处理最需要人工判断的队列。",
        `${suggestedButton(language, "Watch Due / Action Due / Pending")}如果有 due 的 Watch 或 Action，先点对应卡片；否则从 Pending 开始逐条判断 Confirm、Watch、Action 或 Reject。`,
      ],
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
          "Verified Insight Object 是 Trajectory 上的只读事件边界摘要，不是新的 verification 结论。",
          "它把已记录的 outcome、verification_status、confidence、claim risk 和 blocked_downstream_actions 投影成回看视图。",
          "它不重新打开 review，不创建 evidence，不修改 verification_status，也不改变 Action eligibility。",
        ],
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
          "Open Review Record 会从 Trajectory 的 review event 打开当时写入的单条 Project Takeaway 判断记录。",
          "它适合用来检查 outcome、reason、verification gate、claim support 和 source context；这是只读回看，不会改变 Trajectory 或重新执行 review。",
          `${suggestedButton(language, "Open Review Record")}如果你要审计这一次判断，先打开 record；如果要继续处理候选项，再回 Review Inbox。`,
        ],
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
          "Manual Source Contribution / Source Intent Mix 鏄敤鏉ョ湅 manual upload 材料如何进入 review / trajectory 记忆的来源解释。",
          "Upload Reason、Intended Use 和 Cognitive Layer 只说明用户当时为什么上传、准备用在哪里、属于哪层认知材料；它们不是 verification evidence，也不会改变 action gate。",
          `${suggestedButton(language, "Review Inbox")}如果某条 manual-source event 要变成项目判断，回到 Review Inbox 走 Confirm / Watch / Action / Reject。`,
        ],
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
        ],
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
            "这是 Signal 时间线页面，用来按收集日期或发布日期浏览所有 signal。",
            "当前页面还显示了刷新状态。出现 timeout 时，意思是最新刷新可能没完成，但已经加载出来的列表仍然可以继续使用。",
          ],
          [
            "This is the Signal timeline. It lets you browse collected signals by collection date or publication date.",
            "The timeout message means the latest refresh may not have completed, but the visible list can still be used.",
          ]
        );
      }
      return formatAnswer(
        language,
        [
          "当前列表已经有可读数据，但最新刷新可能超时了。",
          `${suggestedButton(language, "Refresh")}先点一次刷新；如果仍然超时，再检查后端 snapshot 和 /signals 接口响应时间。`,
          "不要先把它当成页面坏了。你可以继续使用当前可见列表。",
        ],
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
            "这是 Signal 时间线页面。它的作用是先筛选和浏览 signal，而不是直接做项目判断。",
            "顶部过滤栏代表当前列表视图：你可以按状态、来源、review 范围缩小要看的 signal。",
          ],
          [
            "This is the Signal timeline. Its job is browsing and filtering signals, not making the project decision directly.",
            "The filter bar describes the current list view: status, source, and review scope.",
          ]
        );
      }
      return formatAnswer(
        language,
        [
          "这里是 Signal 时间线。顶部过滤栏用于切换状态、来源和 review 范围。",
          `${suggestedButton(language, "Open Detail")}先用过滤器找到要处理的 signal，再打开详情页决定 Reject、Save for Later、Generate Insight，或进入 Project Review。`,
        ],
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
          "这是 Signal list 页面，用来浏览系统已经收集到的 signals。",
          "这里不负责直接完成 Workspace 或 Project Review 判断。你先在列表里看标题、状态、来源、发布日期、收集日期和 gate 提醒，再决定打开哪一条详情。",
        ],
        [
          "This is the Signal list page. It is for browsing signals already collected by the system.",
          "It does not directly complete Workspace or Project Review decisions. Use the list to inspect title, status, source, dates, and gate warnings, then open the right detail page.",
        ]
      );
    }

    return formatAnswer(
      language,
      [
        "这里是 Signal list。下一步先选一条值得处理的 signal。",
        `${suggestedButton(language, "Open Detail")}打开详情后再决定 Reject、Save for Later、Generate Insight，或进入 Project Review。`,
      ],
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
      ],
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
      ],
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
        "Evidence Grounding / Gate Snapshot 是 Signal Detail 上的只读诊断区，不是新的 verification 结论。",
        "Evidence Grounding 只显示当前 claim check 的裸计数和覆盖率：Direct、Partial、Inferred、Unsupported/Contradicted、evidence refs coverage、source span coverage。它不生成 Well-grounded/Thin 这类阈值裁决，也不评价 source trust。",
        "Gate Snapshot 只把当前 allowed_downstream_actions / blocked_downstream_actions 投影成 Project Takeaway、Watch、Low-risk Action 三行。没有出现在 gate metadata 里的项会显示为未记录，而不是新的建议。",
        "这个 snapshot 不修改 verification_status，不解锁 action，也不得作为任何 gate 决策输入。真正的 gate 仍然来自 verification metadata 和后端 gate 逻辑。",
      ],
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
      ],
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
      ],
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
      ],
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
        "AI Discussion 鐨?challenge 鍙槸瀵逛綘鐨勬帹鐞嗗拰鍋囪鍋氬嵆鏃惰川璇紝涓嶆槸澶栭儴浜嬪疄 verification銆?",
        "瀹冧笉浼氭敼鍙?verification status銆乧laim support 鎴?action eligibility锛涘鏋滃畠鎸戞垬浜嗕竴涓垽鏂紝浣犲彲浠ュ洖澶?可 / 止 / 深入 鏉ユ帹杩涖€佸仠姝紝鎴栫户缁繁鎸栥€?",
      ],
      [
        "AI Discussion challenge is an in-conversation check on your reasoning and assumptions, not external factual verification.",
        "It does not change verification status, claim support, or action eligibility. If it challenges a judgment, reply 可, 止, or 深入 to continue, stop the challenge, or go deeper.",
      ]
    );
  }

  if (hasDeepProjectMatch) {
    if (meaningQuestion) {
      return formatAnswer(
        language,
        [
          "Deep Project Match 表示这条 signal 已经和项目有关，但相关性还不能只靠一句话进入 Confirm 或 Action。",
          "它要求你把外部 signal 的事实、AI Radar 里对应的项目模块、匹配类型和证据边界分开看清楚。",
        ],
        [
          "Deep Project Match means this signal appears project-relevant, but the project fit is not strong enough to move straight into Confirm or Action.",
          "It asks you to separate the external signal fact, the matching AI Radar module, the match type, and the evidence boundary.",
        ]
      );
    }
    return formatAnswer(
      language,
      [
        `${suggestedButton(language, "Generate Deep Match Analysis")}如果基础 checklist 太泛，就手动生成 metadata-tier hypothesis；它是 review aid，不是 verification，也不是 full-source conclusion。`,
        `${suggestedButton(language, "Project Review Inbox")}先读 Deep Project Match Review 的 checklist，再改写 Review note。`,
        "如果出现 Source Claim Reading，先看 source claim reliability 和 claim type；它说明源自己说的是什么断言，不会自动让 signal 变成 verified。",
        "如果 matched project 或 relevant module 不清楚，优先 Watch；如果只是类比相关，不要把它当成已经被 source 证明的外部事实。",
        "Review note 应该写清楚：这条 signal 对应 AI Radar 哪个模块、为什么相关、哪里还只是 internal judgment。",
      ],
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
          "这个页面显示的是一个已经完成到 Workspace 的 signal。",
          "它的意思是：这条 signal 不再只是待处理信息，已经进入可复用的工作记录或项目 review 记忆。",
        ],
        [
          "This page is showing a signal that has already been completed into Workspace.",
          "That means it is no longer just pending information; it has become reusable work context or review memory.",
        ]
      );
    }
    return formatAnswer(
      language,
      [
        "这个 signal 已经完成并进入 Workspace。",
        `${suggestedButton(language, "Project Review Inbox")}优先看它是否已经变成可复用的项目记忆或 review 记录。`,
        "如果还要继续思考，可以用 AI Discussion 追问，但不需要重复完成同一个 signal。",
      ],
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
          "这个页面显示的是一个 Rejected signal。",
          "它的意思是：当前判断认为这条信息价值不足、项目相关性弱，或暂时不值得继续处理。",
        ],
        [
          "This page is showing a Rejected signal.",
          "That means the current judgment treats it as low value, weak project fit, or not worth continuing right now.",
        ]
      );
    }
    return formatAnswer(
      language,
      [
        "这个 signal 当前是 Rejected，系统把它视为低价值或暂时不适合继续处理。",
        `${suggestedButton(language, "Back to Signal Records")}通常保持 rejected，不要把它推进 Workspace 或 Action。`,
        "如果你觉得判断错了，先重新检查证据和拒绝原因，再考虑恢复处理。",
      ],
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
          "这个页面显示的是一个带 verification / action gate 风险的 signal。",
          "它的意思是：系统并没有说这条信息一定没用，而是说证据还不足以直接支持 action 或强项目结论。",
        ],
        [
          "This page is showing a signal with verification or action-gate risk.",
          "That does not mean the signal is useless; it means the evidence is not strong enough for direct action or a strong project conclusion.",
        ]
      );
    }
    return formatAnswer(
      language,
      [
        "这个 signal 现在有 verification 或 action gate 提醒。",
        `${suggestedButton(language, hasProjectReview ? "Project Review Inbox" : "Show Decision Map")}不要直接做 action；先看 claim checks，确认哪些 claim 被支持，哪些 unsupported 或 contradicted。`,
        hasProjectReview
          ? "如果它和项目有关，进入 Project Review Inbox 后优先选择 Watch 或 Reject；只有证据足够时再 Confirm。"
          : "如果证据还不够，优先 Save for Later 或保持 review，不要急着完成到 Workspace。",
      ],
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
          "这个页面显示的是一个已经 analyzed、但还没有最终完成进 Workspace 的 signal。",
          "它的意思是：基础分析已经可读，但还需要你判断是否值得保存、继续 review，或写成 completion note。",
        ],
        [
          "This page is showing an analyzed signal that has not yet become a final Workspace record.",
          "That means the analysis is readable, but you still need to decide whether to save, review, or complete it.",
        ]
      );
    }
    return formatAnswer(
      language,
      [
        "这个 signal 已经完成基础分析，但还没有变成最终 Workspace 记录。",
        hasCompletionNote
          ? `${suggestedButton(language, "Generate Draft / Save Note")}先写 Completion Note，确认它是否真的包含可复用判断。`
          : `${suggestedButton(language, "Generate Insight / Project Review Inbox")}先确认分析是否有价值，再决定 Save、Reject 或进入 Project Review。`,
        hasAiDiscussion ? "如果不确定，先用 AI Discussion 追问影响、证据或项目相关性。" : "",
      ],
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
          "这是一个 signal 详情页。它把单条信息的来源、状态、分析、verification gate、项目 review 入口放在一起。",
          "这个页面的核心问题不是“马上执行什么”，而是判断这条 signal 是否值得继续进入 insight、Workspace 或 Project Review。",
        ]
      : [
          "这是一个 signal 详情页。",
          `${suggestedButton(language, "Generate Insight / Reject")}先判断价值：低价值就 Reject，以后可能有用就 Save for Later，值得深入就 Generate Insight 或进入 Project Review。`,
          hasAiDiscussion ? "不确定时，先用 AI Discussion 问清楚影响、风险和项目相关性。" : "",
        ],
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
