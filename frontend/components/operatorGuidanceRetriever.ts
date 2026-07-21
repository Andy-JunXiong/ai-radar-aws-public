export type GuidanceLanguage = "en" | "zh";

type GuidanceChunk = {
  id: string;
  title: string;
  pageHints: string[];
  intents: string[];
  keywords: string[];
  content: {
    en: string;
    zh: string;
  };
  sources: string[];
};

const guidanceChunks: GuidanceChunk[] = [
  {
    id: "signal-save-for-later-meaning",
    title: "Save for Later meaning",
    pageHints: ["/signals", "/signals/detail"],
    intents: ["explain", "status", "button"],
    keywords: ["save for later", "saved", "save reason", "revisit", "later", "保存", "以后", "什么意思", "解释"],
    content: {
      en: [
        "Save for Later means the signal may be useful later, but it should not consume current review or completion attention.",
        "It is not the same as Reject, because the signal still has potential value.",
        "It is also not the same as Analyzed, Completed, Verified, or Workspace memory.",
        "Use one or more save reasons so future review can understand why you kept it.",
      ].join("\n"),
      zh: [
        "Save for Later 的意思是：这个 signal 以后可能有用，但现在不应该占用当前 review 或 completion 注意力。",
        "它不是 Reject，因为这个 signal 还有潜在价值。",
        "它也不是 Analyzed、Completed、Verified，或者已经进入 Workspace memory。",
        "保存时选择一个或多个 reason，是为了未来重新看它时知道当时为什么保留。",
      ].join("\n"),
    },
    sources: ["frontend/app/signals/detail/SignalDetailClient.tsx", "frontend/app/signals/page.tsx"],
  },
  {
    id: "signal-starred-meaning",
    title: "Starred signal meaning",
    pageHints: ["/signals", "/signals/detail"],
    intents: ["explain", "button", "filter"],
    keywords: ["star", "starred", "bookmark", "quick return", "find again", "标星", "收藏", "快速找到"],
    content: {
      en: [
        "Starred is a lightweight bookmark for quick return while you are reviewing a signal.",
        "It does not change Pending, Saved, Analyzed, Completed, or Rejected status.",
        "Use the Starred filter on the Signal Timeline to find bookmarked signals again.",
        "Use Save for Later instead when the workflow decision is to pause the signal for future review.",
      ].join("\n"),
      zh: [
        "Starred is a lightweight bookmark for quick return while you are reviewing a signal.",
        "It does not change Pending, Saved, Analyzed, Completed, or Rejected status.",
        "Use the Starred filter on the Signal Timeline to find bookmarked signals again.",
        "Use Save for Later instead when the workflow decision is to pause the signal for future review.",
      ].join("\n"),
    },
    sources: ["frontend/app/signals/page.tsx", "frontend/app/signals/detail/SignalDetailClient.tsx"],
  },
  {
    id: "signal-decision-lock",
    title: "Signal decision lock",
    pageHints: ["/signals/detail"],
    intents: ["explain", "button", "status", "next_step"],
    keywords: ["enable editing", "locked", "grey", "gray", "disabled", "reject", "saved", "mark processed", "按钮", "灰", "锁", "解锁"],
    content: {
      en: [
        "After Reject, Save for Later, or Mark Processed, the signal is treated as decided for this pass.",
        "Most actions are disabled so the operator does not accidentally continue downstream work from a closed decision.",
        "Open Source remains available because it is read-only inspection.",
        "Enable Editing is the explicit confirmation to reopen the signal in this session; it does not change status by itself.",
      ].join("\n"),
      zh: [
        "当你选择 Reject、Save for Later 或 Mark Processed 后，这个 signal 在当前这一轮就被视为已经做过处理决定。",
        "大部分按钮会变灰，是为了防止你在一个已经处理完的 signal 上误继续下游动作。",
        "Open Source 仍然可用，因为它只是只读查看来源。",
        "Enable Editing 是显式确认：你要在当前 session 重新打开这个 signal；它本身不会改变状态。",
      ].join("\n"),
    },
    sources: ["frontend/app/signals/detail/SignalDetailClient.tsx"],
  },
  {
    id: "signal-workflow-overview",
    title: "Signal workflow overview",
    pageHints: ["/signals", "/signals/detail"],
    intents: ["workflow", "next_step", "explain"],
    keywords: ["signal", "workflow", "flow", "status", "pending", "saved", "analyzed", "completed", "rejected", "流程", "分支", "状态", "最后"],
    content: {
      en: [
        "Signal starts as Pending when it needs review.",
        "Reject means reviewed and low value for the current work.",
        "Save for Later means useful enough to keep, but not worth current attention.",
        "Generate Insight creates structured analysis; it does not by itself verify external claims.",
        "Mark Processed means this review pass is done without completing it into Workspace.",
        "Complete / Workspace is only for reusable memory when the note and evidence gates allow it.",
        "Final Takeaway Confirmation turns a Completion Note into Andy-confirmed wording against an immutable Review Bundle snapshot.",
        "On Signal Detail, Project Review handoff starts from Send Final Takeaway to Review, not a separate manual candidate entry.",
      ].join("\n"),
      zh: [
        "Signal 一开始通常是 Pending，表示需要 review。",
        "Reject 表示已经看过，但对当前工作价值低。",
        "Save for Later 表示值得保留，但现在不值得继续占用注意力。",
        "Generate Insight 会生成结构化分析，但它本身不等于验证外部 claim。",
        "Mark Processed 表示这一轮处理结束，但不进入 Workspace。",
        "Complete / Workspace 只适合可复用记忆，而且 completion note 和 evidence gate 都要允许。",
        "Project Takeaway candidate 是把项目相关 insight 送进 Review Inbox，经过 review 后才可能成为 durable project memory。",
      ].join("\n"),
    },
    sources: ["frontend/app/signals/page.tsx", "frontend/app/signals/detail/SignalDetailClient.tsx"],
  },
  {
    id: "workspace-completion-gate",
    title: "Completion / Workspace gate",
    pageHints: ["/signals/detail", "/workspace"],
    intents: ["explain", "gate", "workflow"],
    keywords: ["completion note", "workspace", "evidence", "verification", "gate", "有价值", "允许", "路径", "解释"],
    content: {
      en: [
        "Completion / Workspace has a higher bar than ordinary review.",
        "The completion note must add useful judgment, interpretation, or project relevance.",
        "The evidence or verification state must allow the signal to be used downstream.",
        "If the note is useful but evidence is weak or blocked, prefer Watch, Save for Later, or cautious context instead of durable Workspace memory.",
      ].join("\n"),
      zh: [
        "Completion / Workspace 的门槛比普通 review 更高。",
        "completion note 必须有真实判断、解释或项目相关性，而不是复制来源内容。",
        "evidence / verification 状态也必须允许它被下游使用。",
        "如果 note 有价值但证据弱或存在 blocked downstream actions，通常应该 Watch、Save for Later，或谨慎保留上下文，而不是进入 durable Workspace memory。",
      ].join("\n"),
    },
    sources: ["AGENTS.md#Intelligence-Quality-Boundaries", "frontend/app/signals/detail/SignalDetailClient.tsx"],
  },
  {
    id: "project-takeaway-review-inbox",
    title: "Project Takeaway candidate review",
    pageHints: ["/signals/detail", "/workspace/projects/review"],
    intents: ["next_step", "workflow", "gate"],
    keywords: ["project takeaway", "candidate", "review inbox", "confirm", "watch", "action", "项目", "候选", "review"],
    content: {
      en: [
        "Creating a Project Takeaway candidate is not the same as confirming it.",
        "After candidate creation, continue in Review Inbox.",
        "Review project fit, evidence note, verification status, and blocked downstream actions before choosing Confirm, Watch, Reject, Dismiss, or Action.",
      ].join("\n"),
      zh: [
        "创建 Project Takeaway candidate 不等于已经确认。",
        "candidate 创建后，下一步应该去 Review Inbox。",
        "在那里先看 project fit、evidence note、verification status 和 blocked_downstream_actions，再决定 Confirm、Watch、Reject、Dismiss 或 Action。",
      ].join("\n"),
    },
    sources: ["AGENTS.md#Intelligence-Quality-Boundaries", "frontend/app/workspace/projects/review/page.tsx"],
  },
];

function normalizeText(value: string) {
  return value.toLowerCase().replace(/\s+/g, " ").trim();
}

function splitTerms(question: string) {
  return normalizeText(question)
    .split(/[\s,.;:!?()[\]{}"'，。！？、；：（）【】]+/)
    .map((term) => term.trim())
    .filter((term) => term.length >= 2);
}

function inferIntent(question: string) {
  const text = normalizeText(question);
  if (text.includes("what should") || text.includes("next") || text.includes("下一步")) return "next_step";
  if (text.includes("explain") || text.includes("meaning") || text.includes("什么意思") || text.includes("解释") || text.includes("为什么")) return "explain";
  if (text.includes("workflow") || text.includes("flow") || text.includes("流程") || text.includes("分支")) return "workflow";
  if (text.includes("gate") || text.includes("verification") || text.includes("evidence")) return "gate";
  return "";
}

function scoreChunk(chunk: GuidanceChunk, question: string, currentPath: string, previousAssistantText?: string) {
  const haystack = normalizeText(question);
  const terms = splitTerms(question);
  let score = 0;

  if (chunk.pageHints.some((hint) => currentPath.includes(hint))) score += 3;

  const intent = inferIntent(question);
  if (intent && chunk.intents.includes(intent)) score += 3;

  for (const keyword of chunk.keywords) {
    if (haystack.includes(normalizeText(keyword))) score += 4;
  }

  for (const term of terms) {
    if (normalizeText(chunk.title).includes(term) || normalizeText(chunk.content.en).includes(term) || normalizeText(chunk.content.zh).includes(term)) {
      score += 1;
    }
  }

  if (previousAssistantText && hasFollowupReference(haystack)) {
    const previous = normalizeText(previousAssistantText);
    if (previous.includes(normalizeText(chunk.title))) score += 1;
  }

  return score;
}

function hasFollowupReference(question: string) {
  return question.includes("this") || question.includes("that") || question.includes("it") || question.includes("\u8fd9") || question.includes("\u5b83");
}

export function retrieveOperatorGuidance(question: string, currentPath: string, previousAssistantText?: string) {
  return guidanceChunks
    .map((chunk) => ({
      chunk,
      score: scoreChunk(chunk, question, currentPath, previousAssistantText),
    }))
    .filter((item) => item.score > 0)
    .sort((left, right) => right.score - left.score)
    .slice(0, 3);
}

export function buildMiniRagGuidanceResponse(
  question: string,
  currentPath: string,
  language: GuidanceLanguage,
  previousAssistantText?: string
) {
  const results = retrieveOperatorGuidance(question, currentPath, previousAssistantText);
  if (!results.length || results[0].score < 4) return null;

  const chunks = results.map((result) => result.chunk);
  const primary = chunks[0];
  const supporting = chunks.slice(1);
  if (language === "zh") {
    return [
      `我理解你问的是：${primary.title}`,
      primary.content.zh,
      supporting.length
        ? `相关补充：\n${supporting.map((chunk) => `- ${chunk.content.zh.split("\n")[0]}`).join("\n")}`
        : "",
    ]
      .filter(Boolean)
      .join("\n\n");
  }

  return [
    `I understand the question as: ${primary.title}`,
    primary.content.en,
    supporting.length
      ? `Related context:\n${supporting.map((chunk) => `- ${chunk.content.en.split("\n")[0]}`).join("\n")}`
      : "",
  ]
    .filter(Boolean)
    .join("\n\n");
}
