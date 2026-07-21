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
    stateLabelZh: "Save for Later 的含义",
    appliesWhen: [
      "The operator asks what Save for Later means on a signal.",
      "The signal is not low-value enough to reject, but it should not consume current review or completion attention.",
    ],
    appliesWhenZh: [
      "你在问 Signal 页面里的 Save for Later 是什么意思。",
      "这个 signal 不是低价值到要 reject，但也不应该占用当前 review 或 completion 注意力。",
    ],
    nextActions: [
      "Use Save for Later when the signal may be useful later but is not urgent or strong enough for current analysis.",
      "Select one or more save reasons so future review can understand why it was kept.",
      "Saved means revisit later; it does not mean analyzed, completed, verified, or added to Workspace.",
      "When the signal becomes relevant again, reopen it from Saved and choose Generate Insight, Mark Processed, Reject, or completion based on the new context.",
    ],
    nextActionsZh: [
      "当这个 signal 以后可能有用，但现在不够紧急、不够强，或者不值得马上分析时，用 Save for Later。",
      "保存时选择一个或多个 reason，方便未来知道为什么当时保留它。",
      "Saved 的意思是以后再看；它不等于 analyzed、completed、verified，也不等于已经进 Workspace。",
      "以后这个 signal 重新相关时，再从 Saved 打开，根据当时上下文选择 Generate Insight、Mark Processed、Reject 或 completion。",
    ],
    notAllowed: [
      "Do not treat Saved as a completed review.",
      "Do not treat Saved as evidence or verification.",
      "Do not use Save for Later for signals that are clearly low value now; use Reject instead.",
    ],
    notAllowedZh: [
      "不要把 Saved 当成已经完成 review。",
      "不要把 Saved 当成 evidence 或 verification。",
      "如果 signal 现在已经明确低价值，不要 Save for Later，应该 Reject。",
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
      "什么意思",
      "意思",
      "解释",
      "以后",
      "保存",
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
      "标星",
      "收藏",
      "快速找到",
    ],
  },
  {
    stateIdentifier: "signal.workflow.completion_workspace_gate_explanation",
    stateLabel: "Completion / Workspace gate explanation",
    stateLabelZh: "Completion / Workspace 路径的门槛解释",
    appliesWhen: [
      "The operator asks why completion / Workspace requires a useful completion note and allowed evidence or verification gates.",
      "A signal may be useful as context, but may not yet be safe to preserve as durable Workspace memory.",
    ],
    appliesWhenZh: [
      "你在问为什么 completion / Workspace 需要 completion note 有价值，并且 evidence / verification gate 允许。",
      "一个 signal 可能可以作为上下文参考，但不一定已经适合沉淀成 durable Workspace memory。",
    ],
    nextActions: [
      "Read this as two gates, not one button: the note must contain a useful judgment, and the evidence state must allow downstream use.",
      "The completion note gate asks whether you added real interpretation, decision context, or project relevance instead of copying the source.",
      "The evidence / verification gate asks whether the claim is supported enough, whether blocked_downstream_actions exist, and whether the signal should remain Watch-only.",
      "If the note is useful but the evidence is weak, prefer Watch, Save for Later, or cautious context instead of Workspace completion.",
      "Use Workspace completion only when the signal is useful enough to become durable project memory.",
    ],
    nextActionsZh: [
      "这句话不是说点一个按钮，而是说有两个门槛：note 本身要有判断价值，证据状态也要允许后续使用。",
      "Completion note gate 问的是：你是否真的写出了理解、判断、项目相关性，而不是把原文搬过去。",
      "Evidence / verification gate 问的是：claim 是否有足够支持，是否存在 blocked_downstream_actions，是否只能先 Watch。",
      "如果 note 有价值但证据弱，优先 Watch、Save for Later，或作为谨慎上下文保留，而不是进入 Workspace completion。",
      "只有当这个 signal 足够适合成为 durable project memory 时，才走 Workspace completion。",
    ],
    notAllowed: [
      "Do not treat a nice completion note as proof that the external claim is true.",
      "Do not use Workspace completion to bypass verification or blocked downstream actions.",
      "Do not complete every interesting signal; completion is for reusable memory, not ordinary reading history.",
    ],
    notAllowedZh: [
      "不要因为 completion note 写得好，就把外部 claim 当成已经被证明。",
      "不要用 Workspace completion 绕过 verification 或 blocked_downstream_actions。",
      "不要把每个有趣 signal 都 complete；completion 是给可复用记忆用的，不是普通阅读历史。",
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
      "解释",
      "什么意思",
      "有价值",
      "允许",
      "路径",
    ],
  },
  {
    stateIdentifier: "signal.workflow.end_to_end",
    stateLabel: "Signal review workflow from intake to terminal states",
    stateLabelZh: "Signal 从进入系统到最终状态的完整 review 流程",
    appliesWhen: [
      "The operator is on Signals or Signal Detail and wants to understand the whole flow.",
      "A signal may be pending, saved, analyzed, rejected, completed, or routed into Review Inbox.",
      "The operator needs to know what each branch means before choosing the next action.",
    ],
    appliesWhenZh: [
      "你在 Signals 或 Signal Detail 页面，想理解 signal 的完整处理链路。",
      "一个 signal 可能处于 pending、saved、analyzed、rejected、completed，或进入 Review Inbox 的分支。",
      "你需要先理解每个分支代表什么，再决定下一步操作。",
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
      "从 Pending 开始：先判断这个 signal 现在是否值得继续 review。",
      "如果已经看过但对当前工作价值低，用 Reject。Rejected 后会锁住下游动作，除非显式点击 Enable Editing。",
      "如果可能以后有用，但现在不值得占用 review 注意力，用 Save for Later。",
      "如果值得分析，需要结构化 insight，用 Generate Insight 或 Generate with Claude。",
      "如果当前这一轮已经处理过，但不准备进入 Workspace，用 Mark Processed。",
      "只有当 completion note 有价值，并且相关 evidence / verification gate 允许时，才走 completion / Workspace 路径。",
      "如果这个 signal 对项目有可复用价值，创建 Project Takeaway candidate，然后去 Review Inbox 做人工 review，不能把创建 candidate 当成已经确认。",
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
      "不要把 generated insight 自动当成 verified evidence，除非 verification metadata 支持。",
      "不要在 rejected signal 上继续做下游动作，除非先显式确认 Enable Editing。",
      "不要用 Project Takeaway 或 Action 路径绕过 blocked_downstream_actions。",
      "不要把 Save for Later、Mark Processed、Reject、Completed 当成同一种终点；它们代表不同的处理结论。",
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
      "流程",
      "分支",
      "最后",
      "解释",
      "可能性",
      "reject",
      "save",
      "processed",
    ],
  },
  {
    stateIdentifier: "project_takeaway.candidate_created_pending_review",
    stateLabel: "Project Takeaway candidate is ready for Review Inbox",
    stateLabelZh: "Project Takeaway candidate 已准备进入 Review Inbox",
    appliesWhen: [
      "A Signal Detail or Manual Detail flow has created a Project Takeaway candidate.",
      "The operator needs to know where to continue review after candidate creation.",
      "The candidate still needs human review before it becomes durable project intelligence or an Action path.",
    ],
    appliesWhenZh: [
      "Signal Detail 或 Manual Detail 已经创建了 Project Takeaway candidate。",
      "操作者需要知道 candidate 创建后下一步去哪里继续 review。",
      "candidate 还需要人工 review，不能直接当成 durable project intelligence 或 Action path。",
    ],
    nextActions: [
      "Open the Review Inbox and find the candidate linked to the current signal or project.",
      "Inspect project fit, evidence note, verification status, and blocked downstream actions before choosing an outcome.",
      "Use Confirm only when the project fit is clear and the gate does not block the relevant downstream path.",
      "Use Watch when the candidate is promising but evidence, project fit, or action eligibility is still incomplete.",
      "Use Reject, Dismiss, or the explicit override path only when the review reason is clear and auditable.",
    ],
    nextActionsZh: [
      "打开 Review Inbox，找到和当前 signal 或 project 关联的 candidate。",
      "先检查 project fit、evidence note、verification status 和 blocked downstream actions，再决定 outcome。",
      "只有在 project fit 清楚、gate 没有阻塞相关 downstream path 时，才使用 Confirm。",
      "如果 candidate 有价值但 evidence、project fit 或 action eligibility 还不完整，用 Watch。",
      "只有 review reason 清楚且可审计时，才使用 Reject、Dismiss 或显式 override path。",
    ],
    notAllowed: [
      "Do not treat candidate creation as confirmation.",
      "Do not use ordinary Confirm or Action paths to bypass blocked_downstream_actions.",
      "Do not treat a Project Takeaway candidate as verified evidence unless verification metadata supports that use.",
    ],
    notAllowedZh: [
      "不要把 candidate creation 当成已经 Confirm。",
      "不要用普通 Confirm 或 Action path 绕过 blocked_downstream_actions。",
      "除非 verification metadata 支持，否则不要把 Project Takeaway candidate 当成 verified evidence。",
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
    stateLabelZh: "Manual-source intelligence 已完成到 project memory",
    appliesWhen: [
      "A manual upload or manual link source has generated insight.",
      "The operator has captured source-stated limits or confidence boundaries for the manual material.",
      "The source has moved through Signal Detail or Manual Detail completion.",
      "The operator needs to know what to inspect next.",
    ],
    appliesWhenZh: [
      "manual upload 或 manual link source 已经生成 insight。",
      "source 已经走过 Signal Detail 或 Manual Detail completion。",
      "操作者需要知道下一步该检查什么。",
    ],
    nextActions: [
      "Inspect the completed Signal Detail or Manual Detail source preview.",
      "Check source-stated limits as provenance metadata; use them to preserve caveats, not to prove the external claim.",
      "Confirm the durable Workspace record preserves manual-source identity.",
      "Inspect the related Project Takeaway candidate before Confirm, Watch, Action, Reject, or Dismiss.",
      "Check Review Records and Trajectory for manual-source contribution after review.",
    ],
    nextActionsZh: [
      "检查已完成的 Signal Detail 或 Manual Detail source preview。",
      "确认 durable Workspace record 保留了 manual-source identity。",
      "在 Confirm、Watch、Action、Reject 或 Dismiss 前，先检查相关 Project Takeaway candidate。",
      "review 后检查 Review Records 和 Trajectory 里是否保留 manual-source contribution。",
    ],
    notAllowed: [
      "Do not treat the manual source as factual evidence for external claims unless verification metadata supports that use.",
      "Do not treat source-stated limits as a Project Takeaway gate bypass or source-quality score.",
      "Do not skip Signal Detail, Workspace, or Project Takeaway gates because the source was manually selected.",
    ],
    notAllowedZh: [
      "除非 verification metadata 支持，不要把 manual source 当成外部 claim 的 factual evidence。",
      "不要因为 source 是手动选择的，就跳过 Signal Detail、Workspace 或 Project Takeaway gates。",
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
    stateLabelZh: "Verified insight 存在 blocked downstream actions",
    appliesWhen: [
      "A signal, insight, candidate, or review object exposes blocked_downstream_actions.",
      "The operator is deciding whether a Project Takeaway or low-risk Action path is allowed.",
    ],
    appliesWhenZh: [
      "signal、insight、candidate 或 review object 暴露了 blocked_downstream_actions。",
      "操作者正在判断 Project Takeaway 或 low-risk Action path 是否允许继续。",
    ],
    nextActions: [
      "Read the visible gate note or verification summary before choosing an outcome.",
      "Prefer Watch or further review when evidence is partial, inferred, unsupported, contradicted, or not verifiable.",
      "Use only the explicit override-confirm or override-action path if an exceptional human override is needed.",
      "Record the reviewer note and expected outcome when using an override path.",
    ],
    nextActionsZh: [
      "选择 outcome 前，先读 visible gate note 或 verification summary。",
      "当 evidence 是 partial、inferred、unsupported、contradicted 或 not verifiable 时，优先 Watch 或继续 review。",
      "只有在确实需要 exceptional human override 时，才使用显式 override-confirm 或 override-action path。",
      "使用 override path 时，必须记录 reviewer note 和 expected outcome。",
    ],
    notAllowed: [
      "Do not use ordinary Confirm or Action paths to bypass blocked_downstream_actions.",
      "Do not label missing or empty verification metadata as verified_insight.",
      "Do not treat fallback LLM explanation as evidence or claim support.",
    ],
    notAllowedZh: [
      "不要用普通 Confirm 或 Action path 绕过 blocked_downstream_actions。",
      "不要把 missing 或 empty verification metadata 标成 verified_insight。",
      "不要把 fallback LLM explanation 当成 evidence 或 claim support。",
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
    stateLabelZh: "Knowledge convergence candidate 等待 review",
    appliesWhen: [
      "A Knowledge convergence brief has been sent to Review Inbox.",
      "The candidate is marked as knowledge_convergence or knowledge_convergence_review_candidate.",
      "The operator is deciding whether the convergence should become reusable project intelligence.",
    ],
    appliesWhenZh: [
      "Knowledge convergence brief 已经送到 Review Inbox。",
      "candidate 被标记为 knowledge_convergence 或 knowledge_convergence_review_candidate。",
      "操作者正在判断这个 convergence 是否应该成为 reusable project intelligence。",
    ],
    nextActions: [
      "Inspect the Knowledge context panel and matched project fit before acting.",
      "Check source count, shared topic overlap, project match reason, and evidence profile.",
      "Use Watch when the convergence is promising but still needs stronger project fit or evidence.",
      "Keep low-risk Action blocked unless further verified evidence or explicit override supports action.",
    ],
    nextActionsZh: [
      "行动前先检查 Knowledge context panel 和 matched project fit。",
      "检查 source count、shared topic overlap、project match reason 和 evidence profile。",
      "如果 convergence 有潜力但 project fit 或 evidence 还不够强，用 Watch。",
      "除非有进一步 verified evidence 或显式 override 支持，否则保持 low-risk Action blocked。",
    ],
    notAllowed: [
      "Do not treat Knowledge convergence as automatic action evidence.",
      "Do not create reusable project memory from generic topic overlap alone.",
      "Do not hide missing project fit behind a Confirm outcome.",
    ],
    notAllowedZh: [
      "不要把 Knowledge convergence 当成自动 action evidence。",
      "不要只凭 generic topic overlap 创建 reusable project memory。",
      "不要用 Confirm outcome 掩盖 missing project fit。",
    ],
    governingSources: [
      "DEVELOPMENT_PLAN.md#Agent-Watch--Friction-Signals-Convergence",
      "AGENTS.md#Intelligence-Quality-Boundaries",
      "docs/adr/0006-operator-guidance-layer.md",
    ],
    keywords: ["knowledge", "convergence", "review", "candidate", "watch", "project fit"],
  },
];

export function detectGuidanceLanguage(text: string) {
  return /[\u3400-\u9fff]/.test(text) ? "zh" : "en";
}

function asksMetricsLocation(question: string) {
  const text = question.toLowerCase();
  return (
    (text.includes("metric") || text.includes("metrics") || text.includes("\u6307\u6807") || text.includes("\u6307\u6a19")) &&
    (text.includes("where") ||
      text.includes("which page") ||
      text.includes("see") ||
      text.includes("look") ||
      text.includes("\u54ea") ||
      text.includes("\u5728\u54ea") ||
      text.includes("\u770b") ||
      text.includes("\u91cc"))
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
  return language === "zh"
    ? `\u4f60\u73b0\u5728\u5728 ${surface} \u9875\u9762\uff0c\u4f46\u8fd9\u4e2a\u95ee\u9898\u5c5e\u4e8e ${target} \u8303\u56f4\u3002`
    : `You are currently on ${surface}, but this question belongs to ${target}.`;
}

function asksFrictionWatch(question: string) {
  const text = question.toLowerCase();
  const mentionsFriction = text.includes("friction") || text.includes("\u6469\u64e6");
  const mentionsWatch = text.includes("watch") || text.includes("follow-up") || text.includes("follow up") || text.includes("\u89c2\u5bdf") || text.includes("\u8ddf\u8fdb");
  return mentionsFriction && mentionsWatch;
}

function asksProjectTakeaway(question: string) {
  const text = question.toLowerCase();
  return (
    text.includes("project takeaway") ||
    text.includes("review inbox") ||
    text.includes("candidate") ||
    text.includes("\u9879\u76ee\u8bb0\u5fc6") ||
    text.includes("\u9879\u76ee\u7ed3\u8bba") ||
    text.includes("\u5019\u9009")
  );
}

function asksManualSource(question: string) {
  const text = question.toLowerCase();
  return (
    text.includes("manual") ||
    text.includes("upload") ||
    text.includes("source intent") ||
    text.includes("\u624b\u52a8") ||
    text.includes("\u4e0a\u4f20") ||
    text.includes("\u6765\u6e90\u610f\u56fe")
  );
}

export function buildGlobalGuidanceAnswer(
  question: string,
  language: "en" | "zh" = "en",
  currentPath?: string
) {
  if (language === "zh") {
    if (asksMetricsLocation(question)) {
      return [
        scopePrefix(currentPath, "Metrics", language),
        "\u7cfb\u7edf metrics \u5728 `/admin/metrics` \u770b\u3002",
        "\u5165\u53e3\u662f\u9996\u9875\u7684 Metrics\uff0c\u6216\u8005 Admin -> Metrics\u3002\u8fd9\u4e2a\u9875\u9762\u8bfb\u540e\u7aef `/metrics/status`\u3001`/metrics/daily-summary`\u548c `/metrics/summaries`\u3002",
        "\u76ee\u524d metrics \u8986\u76d6 pipeline\u3001collector\u3001artifact write\u3001LLM\u3001verification \u548c signal activity summary\u3002\u524d\u7aef timeline timeout / stale local snapshot \u8fd8\u6ca1\u6709\u81ea\u52a8\u5199\u5165 metrics\u3002",
      ].filter(Boolean).join("\n\n");
    }

    if (asksFrictionWatch(question)) {
      return [
        scopePrefix(currentPath, "Friction / Watch", language),
        "Friction Watch \u95ee\u9898\u53ef\u4ee5\u76f4\u63a5\u5728\u8fd9\u91cc\u95ee\uff0c\u4e0d\u9700\u8981\u5148\u8df3\u5230\u5bf9\u5e94\u9875\u9762\u3002",
        "\u4e3b\u8981\u5165\u53e3\u662f `/friction-signals`\u3001`/watch-learning`\uff0c\u4ee5\u53ca Review Inbox \u91cc\u7684 Watch \u961f\u5217\u3002Friction \u4fe1\u53f7\u662f\u6469\u64e6/\u963b\u529b/\u673a\u4f1a\u7ebf\u7d22\uff1bWatch \u662f\u7ee7\u7eed\u89c2\u5bdf\uff0c\u4e0d\u7b49\u4e8e\u5df2\u786e\u8ba4\u6216\u53ef action\u3002",
        "\u4e0b\u4e00\u6b65\u901a\u5e38\u662f\uff1a\u770b friction \u6765\u6e90\u548c\u6a21\u5f0f\uff0c\u5982\u679c\u8fd8\u7f3a\u8bc1\u636e\u6216\u9879\u76ee\u9002\u914d\u5ea6\uff0c\u628a\u5b83\u7559\u5728 Watch\uff1b\u53ea\u6709 gate \u5141\u8bb8\u65f6\u624d\u8fdb\u5165 Confirm \u6216 Action\u3002",
      ].filter(Boolean).join("\n\n");
    }

    if (asksProjectTakeaway(question)) {
      return [
        scopePrefix(currentPath, "Project Takeaway", language),
        "Project Takeaway \u662f\u9879\u76ee\u53ef\u590d\u7528\u8bb0\u5fc6\u7684\u4eba\u5de5\u5ba1\u67e5\u6d41\uff0c\u4e0d\u662f\u666e\u901a signal \u5217\u8868\u91cc\u76f4\u63a5\u5b8c\u6210\u7684\u4e1c\u897f\u3002",
        "\u5165\u53e3\u662f `/workspace/projects/review`\u3002Candidate \u521b\u5efa\u540e\u8fd8\u4e0d\u7b49\u4e8e\u786e\u8ba4\uff1b\u9700\u8981\u68c0\u67e5 project fit\u3001evidence note\u3001verification status \u548c blocked_downstream_actions\uff0c\u518d\u9009 Confirm / Watch / Reject / Dismiss / Action\u3002",
      ].filter(Boolean).join("\n\n");
    }

    if (asksManualSource(question)) {
      return [
        scopePrefix(currentPath, "Manual Source", language),
        "Manual Source \u662f\u628a\u4eba\u624b\u627e\u5230\u7684\u6587\u7ae0\u3001PDF\u3001\u56fe\u7247\u6216\u94fe\u63a5\u653e\u5165 AI Radar \u7684\u5165\u53e3\uff0c\u4e3b\u9875\u662f `/manual`\u3002",
        "\u5b83\u9700\u8981\u5148\u6709 source link / upload reason / intended use / cognitive layer\uff0c\u7136\u540e Analyze Session\u3002Manual \u5206\u6790\u7ed3\u679c\u53ef\u4ee5\u8fdb Signals\u3001Knowledge \u6216 Project Review\uff0c\u4f46\u4e0d\u4f1a\u81ea\u52a8\u53d8\u6210\u5df2\u9a8c\u8bc1\u7684\u9879\u76ee\u7ed3\u8bba\u3002",
      ].filter(Boolean).join("\n\n");
    }
  }

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

  if (language === "zh") {
    return [
      `针对 ${label}：`,
      `适用场景：\n${appliesWhen}`,
      "下一步：",
      nextActions,
      `不要做：\n${notAllowed}`,
    ].join("\n\n");
  }

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
    haystack.includes("解释") ||
    haystack.includes("什么意思") ||
    haystack.includes("意思") ||
    haystack.includes("为什么") ||
    haystack.includes("explain") ||
    haystack.includes("what does") ||
    haystack.includes("what means") ||
    haystack.includes("why")
  );
}

function buildCompletionWorkspaceExplanation(language: "en" | "zh") {
  if (language === "zh") {
    return [
      "这句话的意思是：不是每个 signal 都应该进入 Workspace。",
      "只有当你已经写出一个有价值的 completion note，并且这个 signal 的证据状态允许它被当作后续项目记忆使用时，才应该走 completion / Workspace 路径。",
      "这里有两个 gate：",
      "1. Completion note gate：你是否真的沉淀了一个有用判断，而不只是把原文搬过去。",
      "2. Evidence / verification gate：这个 signal 的 claim 是否有足够证据、是否存在 blocked_downstream_actions、是否只能作为待观察材料。",
      "如果 completion note 有价值，但 evidence / verification 不够强，通常应该 Watch、Save for Later，或只保留为谨慎备注，而不是把它推进成 durable Workspace memory。",
    ].join("\n\n");
  }

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
  if (language === "zh") {
    return [
      "Evidence Grounding / Gate Snapshot 是 Signal Detail 上的只读诊断区，不是新的 verification 结论。",
      "Evidence Grounding 只显示当前 claim check 的裸计数和覆盖率：Direct、Partial、Inferred、Unsupported/Contradicted、Evidence refs coverage、Source span coverage。它不生成 Well-grounded/Thin 这类阈值裁决，也不评价 source trust。",
      "Gate Snapshot 只把当前 allowed_downstream_actions / blocked_downstream_actions 投影成 Project Takeaway、Watch、Low-risk Action 三行。没有出现在 gate metadata 里的项会显示为未记录，而不是新的建议。",
      "这个 snapshot 不修改 verification_status，不解锁 action，也不得作为任何 gate 决策输入。真正的 gate 仍然来自 verification metadata 和后端 gate 逻辑。",
    ].join("\n\n");
  }

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

  if (language === "zh") {
    return [
      "我还没有找到这个步骤的明确建议。",
      "你可以问：当前状态是什么意思、下一步应该怎么 review，或者为什么某个按钮不可用。",
    ].join("\n\n");
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
    (haystack.includes("解释") ||
      haystack.includes("什么意思") ||
      haystack.includes("意思") ||
      haystack.includes("explain") ||
      haystack.includes("what does") ||
      haystack.includes("why")) &&
    (haystack.includes("completion note") ||
      haystack.includes("workspace") ||
      haystack.includes("completion / workspace") ||
      haystack.includes("evidence") ||
      haystack.includes("verification") ||
      haystack.includes("gate") ||
      haystack.includes("有价值") ||
      haystack.includes("允许"));
  const asksSaveForLaterExplanation =
    haystack.includes("save for later") ||
    haystack.includes("saved") ||
    haystack.includes("save reason") ||
    (haystack.includes("保存") && (haystack.includes("以后") || haystack.includes("稍后") || haystack.includes("later"))) ||
    (haystack.includes("save") && (haystack.includes("什么意思") || haystack.includes("意思") || haystack.includes("解释")));
  const asksStarredExplanation =
    haystack.includes("starred") ||
    haystack.includes("star signal") ||
    haystack.includes("bookmark") ||
    haystack.includes("quick return") ||
    haystack.includes("find again") ||
    haystack.includes("标星") ||
    haystack.includes("收藏") ||
    haystack.includes("快速找到");
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
      haystack.includes("completed") ||
      haystack.includes("流程") ||
      haystack.includes("分支") ||
      haystack.includes("最后") ||
      haystack.includes("解释") ||
      haystack.includes("可能性") ||
      haystack.includes("状态"));

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
