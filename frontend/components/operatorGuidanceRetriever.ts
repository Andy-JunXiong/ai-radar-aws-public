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
    keywords: ["save for later", "saved", "save reason", "revisit", "later"],
    content: {
      en: [
        "Save for Later means the signal may be useful later, but it should not consume current review or completion attention.",
        "It is not the same as Reject, because the signal still has potential value.",
        "It is also not the same as Analyzed, Completed, Verified, or Workspace memory.",
        "Use one or more save reasons so future review can understand why you kept it.",
      ].join("\n"),
      zh: [
        "Save for Later means the signal may be useful later, but it should not consume current review or completion attention.",
        "It is not the same as Reject, because the signal still has potential value.",
        "It is also not the same as Analyzed, Completed, Verified, or Workspace memory.",
        "Use one or more save reasons so future review can understand why you kept it.",
      ].join("\n"),
    },
    sources: ["frontend/app/signals/detail/SignalDetailClient.tsx", "frontend/app/signals/page.tsx"],
  },
  {
    id: "signal-starred-meaning",
    title: "Starred signal meaning",
    pageHints: ["/signals", "/signals/detail"],
    intents: ["explain", "button", "filter"],
    keywords: ["star", "starred", "bookmark", "quick return", "find again"],
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
    keywords: ["enable editing", "locked", "grey", "gray", "disabled", "reject", "saved", "mark processed"],
    content: {
      en: [
        "After Reject, Save for Later, or Mark Processed, the signal is treated as decided for this pass.",
        "Most actions are disabled so the operator does not accidentally continue downstream work from a closed decision.",
        "Open Source remains available because it is read-only inspection.",
        "Enable Editing is the explicit confirmation to reopen the signal in this session; it does not change status by itself.",
      ].join("\n"),
      zh: [
        "After Reject, Save for Later, or Mark Processed, the signal is treated as decided for this pass.",
        "Most actions are disabled so the operator does not accidentally continue downstream work from a closed decision.",
        "Open Source remains available because it is read-only inspection.",
        "Enable Editing is the explicit confirmation to reopen the signal in this session; it does not change status by itself.",
      ].join("\n"),
    },
    sources: ["frontend/app/signals/detail/SignalDetailClient.tsx"],
  },
  {
    id: "signal-workflow-overview",
    title: "Signal workflow overview",
    pageHints: ["/signals", "/signals/detail"],
    intents: ["workflow", "next_step", "explain"],
    keywords: ["signal", "workflow", "flow", "status", "pending", "saved", "analyzed", "completed", "rejected"],
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
        "Signal starts as Pending when it needs review.",
        "Reject means reviewed and low value for the current work.",
        "Save for Later means useful enough to keep, but not worth current attention.",
        "Generate Insight creates structured analysis; it does not by itself verify external claims.",
        "Mark Processed means this review pass is done without completing it into Workspace.",
        "Complete / Workspace is only for reusable memory when the note and evidence gates allow it.",
        "Final Takeaway Confirmation turns a Completion Note into Andy-confirmed wording against an immutable Review Bundle snapshot.",
        "On Signal Detail, Project Review handoff starts from Send Final Takeaway to Review, not a separate manual candidate entry.",
      ].join("\n"),
    },
    sources: ["frontend/app/signals/page.tsx", "frontend/app/signals/detail/SignalDetailClient.tsx"],
  },
  {
    id: "workspace-completion-gate",
    title: "Completion / Workspace gate",
    pageHints: ["/signals/detail", "/workspace"],
    intents: ["explain", "gate", "workflow"],
    keywords: ["completion note", "workspace", "evidence", "verification", "gate"],
    content: {
      en: [
        "Completion / Workspace has a higher bar than ordinary review.",
        "The completion note must add useful judgment, interpretation, or project relevance.",
        "The evidence or verification state must allow the signal to be used downstream.",
        "If the note is useful but evidence is weak or blocked, prefer Watch, Save for Later, or cautious context instead of durable Workspace memory.",
      ].join("\n"),
      zh: [
        "Completion / Workspace has a higher bar than ordinary review.",
        "The completion note must add useful judgment, interpretation, or project relevance.",
        "The evidence or verification state must allow the signal to be used downstream.",
        "If the note is useful but evidence is weak or blocked, prefer Watch, Save for Later, or cautious context instead of durable Workspace memory.",
      ].join("\n"),
    },
    sources: ["AGENTS.md#Intelligence-Quality-Boundaries", "frontend/app/signals/detail/SignalDetailClient.tsx"],
  },
  {
    id: "project-takeaway-review-inbox",
    title: "Project Takeaway candidate review",
    pageHints: ["/signals/detail", "/workspace/projects/review"],
    intents: ["next_step", "workflow", "gate"],
    keywords: ["project takeaway", "candidate", "review inbox", "confirm", "watch", "action", "review"],
    content: {
      en: [
        "Creating a Project Takeaway candidate is not the same as confirming it.",
        "After candidate creation, continue in Review Inbox.",
        "Review project fit, evidence note, verification status, and blocked downstream actions before choosing Confirm, Watch, Reject, Dismiss, or Action.",
      ].join("\n"),
      zh: [
        "Creating a Project Takeaway candidate is not the same as confirming it.",
        "After candidate creation, continue in Review Inbox.",
        "Review project fit, evidence note, verification status, and blocked downstream actions before choosing Confirm, Watch, Reject, Dismiss, or Action.",
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
    .split(/[\s,.;:!?()[\]{}"']+/)
    .map((term) => term.trim())
    .filter((term) => term.length >= 2);
}

function inferIntent(question: string) {
  const text = normalizeText(question);
  if (text.includes("what should") || text.includes("next")) return "next_step";
  if (text.includes("explain") || text.includes("meaning") || text.includes("why")) return "explain";
  if (text.includes("workflow") || text.includes("flow")) return "workflow";
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
  return question.includes("this") || question.includes("that") || question.includes("it");
}

export function retrieveOperatorGuidance(question: string, currentPath: string, previousAssistantText?: string) {
  const normalizedQuestion = normalizeText(question);
  if (normalizedQuestion.includes("metric") || normalizedQuestion.includes("metrics")) return [];

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
