export type VerificationGateMetadata = {
  verification_status?: string;
  verification_required?: boolean;
  knowledge_convergence?: boolean;
  manual_project_takeaway_override?: boolean;
  allowed_downstream_actions?: string[];
  blocked_downstream_actions?: string[];
  claim_support_summary?: Record<string, number | string>;
};

export type VerificationGateTone = "blocked" | "watch" | "review" | "ready" | "neutral";

function safeCount(value?: number | string): number {
  const count = Number(value || 0);
  return Number.isFinite(count) ? count : 0;
}

function evaluateVerificationGate(verification: VerificationGateMetadata): {
  note: string;
  tone: VerificationGateTone;
} {
  const status = String(verification.verification_status || "").toLowerCase();
  const blockedActions = verification.blocked_downstream_actions || [];
  const allowedActions = verification.allowed_downstream_actions || [];
  const supportSummary = verification.claim_support_summary || {};
  const hasSupportSummary = Object.values(supportSummary).some((count) => safeCount(count) > 0);
  const hasGateMetadata =
    Boolean(status) ||
    Boolean(verification.verification_required) ||
    Boolean(verification.knowledge_convergence) ||
    Boolean(verification.manual_project_takeaway_override) ||
    blockedActions.length > 0 ||
    allowedActions.length > 0 ||
    hasSupportSummary;

  if (!hasGateMetadata) {
    return { note: "", tone: "neutral" };
  }

  const unsupportedCount = safeCount(supportSummary.unsupported) + safeCount(supportSummary.contradicted);
  const inferredCount = safeCount(supportSummary.inferred);

  if (blockedActions.includes("project_takeaway_candidate")) {
    return {
      note: "Project Takeaway blocked: verification metadata explicitly blocks candidate creation.",
      tone: "blocked",
    };
  }
  if (unsupportedCount > 0) {
    return {
      note: `Do not action yet: ${unsupportedCount} claim(s) are unsupported or contradicted.`,
      tone: "blocked",
    };
  }
  if (status === "unsupported" || status === "contradicted") {
    return {
      note: "Do not action yet: the core claim is unsupported or contradicted.",
      tone: "blocked",
    };
  }
  if (status === "not_verifiable") {
    return {
      note: "Keep as observation or watch: source evidence is not traceable enough.",
      tone: "watch",
    };
  }
  if (status === "unverified_manual_entry" || verification.verification_required) {
    return {
      note: "Verification still required: this manual entry can be reviewed, but it is not verified evidence yet.",
      tone: "blocked",
    };
  }
  if (status === "knowledge_convergence_review_candidate" || verification.knowledge_convergence) {
    return {
      note: "Knowledge convergence needs human review: use Review Inbox before treating it as Project Takeaway or Action.",
      tone: "review",
    };
  }
  if (status === "weakly_supported") {
    return {
      note: "Watch first: evidence is weak and needs stronger support before action.",
      tone: "watch",
    };
  }
  if (blockedActions.includes("low_risk_action_candidate")) {
    return {
      note: "Low-risk Action blocked: keep this in review or Watch until claim checks support action.",
      tone: "review",
    };
  }
  if (blockedActions.includes("strong_recommendation")) {
    return {
      note: "Strong recommendation blocked: keep this in review before acting.",
      tone: "review",
    };
  }
  if (inferredCount > 0) {
    return {
      note: `Review required: ${inferredCount} claim(s) rely on inference rather than direct support.`,
      tone: "review",
    };
  }
  if (allowedActions.includes("project_takeaway_candidate")) {
    return {
      note: "Project Takeaway review available: confirm project fit before creating or confirming a candidate.",
      tone: "ready",
    };
  }
  if (status === "verified") {
    return {
      note: "Verified enough for low-risk review; still requires human judgment before action.",
      tone: "ready",
    };
  }
  return {
    note: "Verification metadata is present, but downstream action eligibility is not explicit yet.",
    tone: "neutral",
  };
}

export function getVerificationGateNote(verification: VerificationGateMetadata): string {
  return evaluateVerificationGate(verification).note;
}

export function getVerificationGateTone(verification: VerificationGateMetadata): VerificationGateTone {
  return evaluateVerificationGate(verification).tone;
}
