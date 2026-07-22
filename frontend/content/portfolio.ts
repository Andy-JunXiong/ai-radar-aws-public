export type PortfolioEvidenceLink = {
  label: string;
  href: string;
  kind: "linkedin" | "github" | "adr" | "code" | "product";
};

export type PortfolioCaseStudy = {
  notebookNumber: 5 | 6 | 9;
  stage: "Ingestion" | "Enforcement" | "Admission";
  title: string;
  skimmer: string;
  capabilities: string[];
  summary: string;
  caveat: string;
  provenance: string;
  primaryEvidence: PortfolioEvidenceLink;
  supportingEvidence: PortfolioEvidenceLink[];
};

const repo = "https://github.com/Andy-JunXiong/ai-radar-aws-public";

export const portfolioCases: PortfolioCaseStudy[] = [
  {
    notebookNumber: 5,
    stage: "Ingestion",
    title: "Three Borrowed Shells",
    skimmer:
      "I stopped three plausible conclusions from carrying more weight than their evidence allowed.",
    capabilities: ["Evidence-aware AI", "Product judgment", "Quality diagnosis"],
    summary:
      "An external insight, a source match, and a clean metric each tried to carry a stronger conclusion than the evidence allowed. I rejected additive scope, replaced token overlap with traceable source-span grounding, and audited 175 claims. The audit returned zero quoted claims, but mostly summary-level evidence packs meant the number could not support a verdict about the whole product. Relevance is not provenance, and a real symptom is not automatically a diagnosis.",
    caveat:
      "The bounded source-excerpt policy was a downstream consequence later admitted through ADR-0011, not part of the original three-shell judgment.",
    provenance: "Public reasoning + repository ADRs + bounded audit claim",
    primaryEvidence: {
      label: "Read Notebook #5 on LinkedIn",
      href: "https://www.linkedin.com/posts/jun-xiong-48123856_airadar-verification-aiproductmanagement-activity-7476042800837468160-9RZU",
      kind: "linkedin",
    },
    supportingEvidence: [
      { label: "ADR-0010", href: `${repo}/blob/main/docs/adr/0010-external-insight-admission-gate.md`, kind: "adr" },
      { label: "ADR-0011", href: `${repo}/blob/main/docs/adr/0011-evidence-pack-source-excerpt-policy.md`, kind: "adr" },
      { label: "Claim-origin audit", href: `${repo}/blob/main/scripts/check_claim_origin_support.py`, kind: "code" },
    ],
  },
  {
    notebookNumber: 6,
    stage: "Enforcement",
    title: "A Constraint Is Only as Strong as Its Layer",
    skimmer:
      "I turned a written rule into an enforced boundary that prevents an unverified manual entry from becoming an ordinary Project Takeaway.",
    capabilities: ["Agent governance", "Enforcement architecture", "System design"],
    summary:
      "The repository path is code-traced and test-supported: an ordinary Project Takeaway request is classified and evaluated before persistence, and policy failure returns HTTP 400. The boundary is deliberately source-aware rather than one-size-fits-all. Knowledge convergence remains review context; insufficiently verified signal completion is marked unverified; and manual override requires a separate, explicit, audited exception.",
    caveat:
      "This claim is limited to ordinary Project Takeaway candidate creation. It is not a claim that every invalid write or downstream commitment is blocked.",
    provenance: "Code-traced + test-supported",
    primaryEvidence: {
      label: "Read Notebook #6 on LinkedIn",
      href: "https://www.linkedin.com/posts/jun-xiong-48123856_airadar-agentengineering-aiproductmanagement-activity-7477129961393397761-1cY_",
      kind: "linkedin",
    },
    supportingEvidence: [
      { label: "Candidate policy", href: `${repo}/blob/main/backend/app/services/project_takeaway_candidate_policy.py`, kind: "code" },
      { label: "Enforcing route", href: `${repo}/blob/main/backend/app/routes/projects.py`, kind: "code" },
      { label: "Policy tests", href: `${repo}/blob/main/tests/test_project_takeaway_candidate_policy.py`, kind: "code" },
    ],
  },
  {
    notebookNumber: 9,
    stage: "Admission",
    title: "A Gate You Can Pass Without Understanding Isn't One",
    skimmer:
      "I found a comprehension gate that could be passed without comprehension, located the same assumption in my system, and did not rush to build a feature.",
    capabilities: ["Human-in-the-loop evaluation", "Gate diagnosis", "Epistemic restraint"],
    summary:
      "Reported answer-pattern leakage made an explain-diff quiz passable without demonstrating comprehension. That exposed a distinction in AI Radar: artifact gates can inspect claims, evidence, and inference while still assuming the admitter is competent to judge. Comprehension may resist reliable proxy measurement, so the result remains tracking-only until multiple admitters or operator load makes the failure mode real.",
    caveat:
      "This is a tracked framing gap, not a shipped comprehension feature or a new ADR requirement.",
    provenance: "External specimen + public reasoning + tracking-only validation record",
    primaryEvidence: {
      label: "Read Notebook #9 on LinkedIn",
      href: "https://www.linkedin.com/posts/jun-xiong-48123856_airadar-agentengineering-aiproductmanagement-activity-7485116442091147264-E2io",
      kind: "linkedin",
    },
    supportingEvidence: [
      { label: "Geoffrey Litt's explain-diff", href: "https://gist.github.com/geoffreylitt/a29df1b5f9865506e8952488eac3d524", kind: "github" },
      { label: "ADR-0015", href: `${repo}/blob/main/docs/adr/0015-claim-set-composition-underdetermination-gate.md`, kind: "adr" },
    ],
  },
];
