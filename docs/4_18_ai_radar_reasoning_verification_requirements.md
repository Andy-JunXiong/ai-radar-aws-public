# AI Radar Requirement: Add Unified Reasoning + Verification Layer

## 0. Context

AI Radar currently has multiple reasoning modules:

- Signal Insight
- Manual Upload Analysis
- Decision Card
- Reflection / Reflection Polish
- Friction -> Opportunity
- Agent Watch / Repo Profile

The system already performs some verification, but mostly at the structural/runtime level:

- JSON contract parsing
- fallback policy
- provider routing
- weak quality checks
- review loop
- human-in-loop for reflection

The main gap is that verification is not yet unified, evidence-grounded, or claim-level.

Current issue:

Reasoning exists in many places, but Verification is mostly fragmented and shape-based. The system can generate plausible insights from thin signals, and those weak insights can flow downstream into Decision Cards.

The goal of this requirement is to add a lightweight but systematic Verification layer.

---

## 1. Primary Goal

Add a unified `Reasoning + Verification` layer that turns raw LLM-generated insight into a verified, evidence-aware object before it is used downstream.

Target pipeline:

```text
Signal
→ Evidence Pack
→ Evidence Sufficiency Check
→ Raw Insight
→ Claim Extraction
→ Claim Verification
→ Verified Insight
→ Decision Card Gate
→ Decision Card / Watch Card / Observation
```

The system should stop treating every generated insight as equally reliable.

Instead, it should distinguish:

- directly supported claims
- partially supported claims
- inferred claims
- unsupported claims
- speculative claims
- low-evidence outputs

---

## 2. Non-Goals

Do not build a heavy formal proof system.

Do not remove existing reasoning modules.

Do not remove human-in-loop from Reflection.

Do not store raw chain-of-thought.

Do not make the system block all thin signals. Thin signals should be downgraded, not necessarily discarded.

---

## 3. Design Principles

### 3.1 Evidence first

Before generating strong insight or action, the system must know whether the source signal contains enough evidence.

### 3.2 Claim-level verification

Do not verify a whole paragraph as one blob.

Break insight into claims and verify each claim separately.

### 3.3 Confidence discipline

Confidence should not be just an LLM-generated number.

Confidence should be derived from:

- evidence strength
- source quality
- claim support
- inference distance
- corroboration
- historical consistency
- contradiction penalty
- thin signal penalty

### 3.4 Graceful degradation

Low-evidence input should produce weaker output:

```text
strong insight → weak insight → observation only → needs review
```

### 3.5 Downstream action gating

Decision Cards should not directly rely on raw insight when a verified insight is available.

---

## 4. Existing Files to Inspect

Please inspect existing implementations before making changes:

```text
backend/app/services/signal_insight_service.py
backend/app/services/decision_card_service.py
backend/app/routes/decision_cards.py
backend/app/routes/manual.py
backend/app/prompts/registry.py
```

Also inspect existing models/schemas, database patterns, service conventions, test structure, and provider fallback utilities before adding new files.

---

## 5. New Concepts to Add

### 5.1 Evidence Pack

Add a normalized evidence object that captures what the system actually knows about a signal.

Suggested model:

```python
class EvidenceItem(BaseModel):
    evidence_id: str
    source_id: str
    source_type: str  # "signal", "manual_upload", "repo", "friction", etc.
    source_field: str # "title", "summary", "content", "url", etc.
    text: str
    reliability: str  # "low", "medium", "high", "unknown"
    timestamp: Optional[datetime] = None
    metadata: dict = {}
```

Suggested aggregate:

```python
class EvidencePack(BaseModel):
    source_id: str
    source_type: str
    title: Optional[str] = None
    summary: Optional[str] = None
    content_excerpt: Optional[str] = None
    url: Optional[str] = None
    source_name: Optional[str] = None
    published_at: Optional[datetime] = None
    evidence_items: list[EvidenceItem]
    evidence_quality: "EvidenceQuality"
```

---

### 5.2 Evidence Quality

Add an evidence sufficiency assessment.

Suggested model:

```python
class EvidenceQuality(BaseModel):
    level: str  # "insufficient", "thin", "sufficient", "strong"
    score: float
    has_title: bool
    has_summary: bool
    has_content: bool
    text_length: int
    source_reliability: str
    is_thin_signal: bool
    notes: list[str] = []
```

Suggested rule:

```python
def assess_evidence_sufficiency(signal) -> EvidenceQuality:
    score = 0.0

    if signal.title:
        score += 0.15

    if signal.summary and len(signal.summary) > 200:
        score += 0.35

    if signal.content and len(signal.content) > 500:
        score += 0.30

    if getattr(signal, "source_reliability", None) in ["high", "medium"]:
        score += 0.10

    if signal.url:
        score += 0.10

    if score < 0.35:
        level = "insufficient"
    elif score < 0.65:
        level = "thin"
    elif score < 0.85:
        level = "sufficient"
    else:
        level = "strong"

    return EvidenceQuality(...)
```

This does not need to be perfect initially. The purpose is to prevent thin signals from producing strong conclusions.

---

### 5.3 Low Evidence Gate

Add a gate that caps confidence and restricts downstream actions based on evidence quality.

Suggested policy:

```python
if evidence_quality.level == "insufficient":
    max_confidence = 0.35
    output_mode = "observation_only"
    decision_card_allowed = False

elif evidence_quality.level == "thin":
    max_confidence = 0.55
    output_mode = "weak_insight_with_uncertainty"
    decision_card_allowed = "watch_only"

elif evidence_quality.level == "sufficient":
    max_confidence = 0.85
    output_mode = "normal_insight"
    decision_card_allowed = True

elif evidence_quality.level == "strong":
    max_confidence = 0.95
    output_mode = "normal_insight"
    decision_card_allowed = True
```

Important: low evidence should not necessarily fail the request. It should downgrade the output.

---

### 5.4 Claim Model

Add a claim-level representation.

Suggested model:

```python
class Claim(BaseModel):
    claim_id: str
    claim_text: str
    claim_type: str
    support_level: str
    evidence_refs: list[str] = []
    inference_distance: str
    risk_level: str
    unsupported_parts: list[str] = []
    recommended_rewrite: Optional[str] = None
    verification_notes: list[str] = []
```

Suggested `claim_type` values:

```python
ClaimType = Literal[
    "factual",
    "descriptive",
    "interpretive",
    "strategic_relevance",
    "career_relevance",
    "recommendation",
    "forecast",
    "speculative"
]
```

Suggested `support_level` values:

```python
SupportLevel = Literal[
    "supported",
    "partially_supported",
    "unsupported",
    "contradicted",
    "not_checkable"
]
```

Suggested `inference_distance` values:

```python
InferenceDistance = Literal[
    "direct",
    "near",
    "medium",
    "far",
    "speculative"
]
```

Rules:

- `factual` claims require direct evidence.
- `descriptive` claims require source text support.
- `interpretive` claims may be partially supported but need inference distance.
- `forecast` claims should usually be capped at low/medium confidence.
- `recommendation` claims require sufficient evidence and should be gated.
- `speculative` claims should not trigger strong action.

---

### 5.5 Verified Insight

Add a new verified insight object between raw insight and decision card.

Suggested model:

```python
class VerifiedInsight(BaseModel):
    verified_insight_id: str
    source_signal_id: Optional[str] = None
    raw_insight_id: Optional[str] = None

    raw_insight: dict

    evidence_items: list[EvidenceItem]
    evidence_quality: EvidenceQuality

    claims: list[Claim]

    uncertainty_boundaries: list[str] = []

    confidence_score: float
    confidence_label: str  # "low", "medium", "high"
    confidence_reason: list[str] = []

    verification_status: str
    allowed_downstream_actions: list[str] = []
    blocked_downstream_actions: list[str] = []

    reasoning_trace_id: Optional[str] = None
    metadata: dict = {}
```

Suggested `verification_status` values:

```python
VerificationStatus = Literal[
    "verified",
    "verified_with_limitations",
    "weak_evidence",
    "unsupported",
    "contradicted",
    "needs_human_review"
]
```

---

### 5.6 Reasoning Trace

Add an audit trace, but do not store raw chain-of-thought.

Suggested model:

```python
class ReasoningTrace(BaseModel):
    trace_id: str
    input_refs: list[str]
    evidence_refs: list[str]
    claims_generated: list[str]
    verification_results: list[dict]
    rules_triggered: list[str]
    confidence_before_review: Optional[float] = None
    final_output_id: Optional[str] = None
    metadata: dict = {}
```

This trace should be useful for debugging and quality review.

It should not contain hidden model reasoning or long free-form chain-of-thought.

---

## 6. New Services to Add

Please follow existing project conventions for naming, imports, logging, error handling, async patterns, and tests.

Suggested files:

```text
backend/app/services/evidence_pack_service.py
backend/app/services/evidence_sufficiency_service.py
backend/app/services/low_evidence_gate_service.py
backend/app/services/claim_extraction_service.py
backend/app/services/claim_verification_service.py
backend/app/services/confidence_scoring_service.py
backend/app/services/verified_insight_service.py
backend/app/services/reasoning_trace_service.py
```

If the project already has a better place for schemas/models, use the existing convention.

---

## 7. Service Responsibilities

### 7.1 EvidencePackService

Input:

```text
signal / manual upload / repo profile / friction signal
```

Output:

```text
EvidencePack
```

Responsibilities:

- normalize source text into evidence items
- include field-level evidence references
- compute text length
- preserve source field names
- avoid hallucinating missing content

---

### 7.2 EvidenceSufficiencyService

Input:

```text
EvidencePack
```

Output:

```text
EvidenceQuality
```

Responsibilities:

- classify evidence as insufficient/thin/sufficient/strong
- attach notes explaining weakness
- provide score usable by confidence service

---

### 7.3 LowEvidenceGateService

Input:

```text
EvidenceQuality
```

Output:

```text
max_confidence
output_mode
decision_card_allowed
required_uncertainty_notes
```

Responsibilities:

- prevent low-evidence signals from generating strong conclusions
- enforce confidence cap
- determine whether downstream decision cards are allowed

---

### 7.4 ClaimExtractionService

Input:

```text
raw insight fields
evidence pack
```

Output:

```text
list[Claim]
```

Responsibilities:

- extract key claims from generated insight
- classify claim type
- avoid over-extracting trivial claims
- include claims from:
  - why_it_matters
  - relevance_to_projects
  - relevance_to_career
  - synthesized_insight
  - decision thesis, if applicable

This service may use LLM, but output must be structured JSON.

---

### 7.5 ClaimVerificationService

Input:

```text
claims
evidence_items
personal context, if available
```

Output:

```text
verified claims
```

Responsibilities:

- assign support level
- attach evidence refs
- identify unsupported parts
- recommend safer rewrites for overclaimed claims
- assign inference distance
- assign risk level

Important:

Do not only ask an LLM “is this true?”. Combine deterministic checks with LLM judgment where appropriate.

---

### 7.6 ConfidenceScoringService

Input:

```text
EvidenceQuality
verified claims
source metadata
historical/review metadata if available
```

Output:

```text
confidence_score
confidence_label
confidence_reason
```

Suggested formula:

```python
confidence_score = (
    0.30 * evidence_strength +
    0.20 * source_quality +
    0.25 * claim_support +
    0.10 * corroboration +
    0.10 * historical_consistency
    - 0.15 * inference_distance_penalty
    - 0.20 * contradiction_penalty
    - 0.15 * thin_signal_penalty
)
```

Clamp score between 0 and 1.

Then apply `LowEvidenceGate.max_confidence`.

Confidence labels:

```python
if score < 0.45:
    label = "low"
elif score < 0.75:
    label = "medium"
else:
    label = "high"
```

---

### 7.7 VerifiedInsightService

Input:

```text
raw insight
evidence pack
verified claims
confidence result
low evidence policy
```

Output:

```text
VerifiedInsight
```

Responsibilities:

- assemble final verified object
- generate uncertainty boundaries
- decide allowed/blocked downstream actions
- create reasoning trace
- expose output to downstream decision card service

---

### 7.8 ReasoningTraceService

Responsibilities:

- save structured trace
- include evidence refs, claim ids, rules triggered, final output id
- do not save hidden chain-of-thought

---

## 8. Integration Points

### 8.1 Signal Insight

Current flow is approximately:

```text
Signal → signal_insight_service.py → raw insight
```

New flow should become:

```text
Signal
→ EvidencePackService
→ EvidenceSufficiencyService
→ LowEvidenceGateService
→ Raw Insight Generation
→ ClaimExtractionService
→ ClaimVerificationService
→ ConfidenceScoringService
→ VerifiedInsightService
→ Return raw insight + verification metadata
```

Do not break existing API consumers.

If existing routes expect the original fields, keep them.

Add verification metadata in a backward-compatible way:

```json
{
  "summary": "...",
  "why_it_matters": "...",
  "relevance_to_projects": "...",
  "relevance_to_career": "...",
  "synthesized_insight": "...",
  "verification": {
    "verified_insight_id": "...",
    "evidence_quality": "...",
    "confidence_score": 0.62,
    "confidence_label": "medium",
    "verification_status": "verified_with_limitations",
    "uncertainty_boundaries": [],
    "claims": []
  }
}
```

---

### 8.2 Decision Card

Current flow is approximately:

```text
Insight → Decision Card
```

New preferred flow:

```text
Verified Insight → Decision Card
```

Add a gate before generating a decision card.

Suggested gate:

```python
def can_generate_decision_card(verified_insight):
    if verified_insight.verification_status in ["unsupported", "contradicted"]:
        return False

    if verified_insight.confidence_score < 0.45:
        return False

    if "strong_recommendation" in verified_insight.blocked_downstream_actions:
        return False

    return True
```

Decision Card behavior by verification status:

```text
high confidence       → allow action card
medium confidence     → allow watch/review card
low evidence          → observation only, no action card
unsupported           → block decision card
speculative           → hypothesis/watch card only
```

Add fields to Decision Card where possible:

```json
{
  "based_on_verified_insight_id": "...",
  "evidence_strength": "medium",
  "claim_support_summary": "...",
  "decision_grade": "watch",
  "action_permission": "review_before_action"
}
```

Do not remove existing decision card fields.

---

### 8.3 Manual Upload Analysis

Manual upload analysis can use the same verification layer, but it should be slightly more permissive because user-uploaded content can be richer and may require interpretation.

Add:

- evidence pack from uploaded content
- claim extraction
- uncertainty boundaries
- confidence metadata

Do not block manual analysis too aggressively.

---

### 8.4 Reflection

Do not remove human-in-loop.

Reflection can consume verified insight metadata later, but this requirement should not force a major reflection rewrite.

For now:

- preserve current reflection behavior
- optionally include verification metadata where available
- keep human review as the highest-quality verification path

---

## 9. Prompt Changes

Update prompts in `registry.py` where relevant.

Signal Insight prompt should include rules like:

```text
Only make claims supported by the provided signal.
If the signal is thin, say so explicitly.
Separate direct observations from inferences.
Do not make market-level claims from a single weak source.
Do not turn one weak signal into a broad strategic trend.
Return uncertainty boundaries when evidence is limited.
Prefer cautious language when evidence is thin.
```

Claim extraction prompt should produce structured JSON.

Claim verification prompt should judge support against provided evidence only.

Unsupported claim rewriter should rewrite overclaimed statements into safer versions.

Example rewrite:

Original:

```text
This proves agent infrastructure is becoming production-ready.
```

Safer:

```text
This signal suggests one project is moving toward more production-oriented agent infrastructure, but it does not by itself prove a broader market shift.
```

---

## 10. Verification Policy

Add a simple policy service.

Suggested policy:

```python
def verification_policy(verified_insight):
    if verified_insight.evidence_quality.level == "insufficient":
        return {
            "publish_level": "observation_only",
            "max_confidence": 0.35,
            "decision_card_allowed": False
        }

    if any(
        claim.support_level == "unsupported" and claim.risk_level == "high"
        for claim in verified_insight.claims
    ):
        return {
            "publish_level": "needs_review",
            "max_confidence": 0.50,
            "decision_card_allowed": False
        }

    if verified_insight.confidence_score >= 0.75:
        return {
            "publish_level": "verified_insight",
            "decision_card_allowed": True
        }

    return {
        "publish_level": "weak_insight",
        "decision_card_allowed": "watch_only"
    }
```

---

## 11. Downstream Action Rules

Use this rule table:

| Evidence / Verification State | Allowed Output |
|---|---|
| Strong evidence + supported claims | Full insight + decision card |
| Sufficient evidence + partially supported claims | Insight + watch/review card |
| Thin evidence | Weak insight + uncertainty + no strong action |
| Insufficient evidence | Observation only |
| Unsupported high-risk claim | Needs review / block decision card |
| Speculative claim | Hypothesis / watch only |
| Contradicted claim | Block or require human review |

---

## 12. Required Tests

Add tests based on existing test conventions.

### 12.1 Evidence Sufficiency Tests

Test cases:

1. Signal with only title should be `insufficient`.
2. Signal with title + short summary should be `thin`.
3. Signal with title + long summary should be `sufficient`.
4. Signal with title + summary + content + reliable source should be `strong`.

---

### 12.2 Low Evidence Gate Tests

Test cases:

1. `insufficient` evidence caps confidence at 0.35.
2. `thin` evidence caps confidence at 0.55.
3. `insufficient` evidence blocks decision card.
4. `thin` evidence allows watch-only but blocks strong recommendation.

---

### 12.3 Claim Verification Tests

Test cases:

1. Directly supported factual claim returns `supported`.
2. Broad market claim from one weak signal returns `partially_supported` or `unsupported`.
3. Forecast claim gets `speculative` or high inference distance.
4. Unsupported claim includes `recommended_rewrite`.

---

### 12.4 Confidence Scoring Tests

Test cases:

1. Supported claims with sufficient evidence produce medium/high confidence.
2. Thin signal penalty lowers score.
3. Far inference distance lowers score.
4. Contradiction penalty lowers score.
5. Score is clamped between 0 and 1.

---

### 12.5 Decision Card Gate Tests

Test cases:

1. Verified insight with low confidence blocks action card.
2. Verified insight with unsupported high-risk claim blocks card.
3. Medium confidence allows watch/review card.
4. High confidence allows full decision card.
5. Existing raw insight path remains backward-compatible.

---

### 12.6 Reasoning Trace Tests

Test cases:

1. Trace contains input refs, evidence refs, claim ids, rules triggered.
2. Trace does not store raw chain-of-thought.
3. Trace links final output id.

---

## 13. MVP Implementation Order

Please implement in phases.

### Phase 1: Low-Evidence Protection

Implement:

- `EvidencePackService`
- `EvidenceSufficiencyService`
- `LowEvidenceGateService`
- confidence cap
- signal insight integration
- decision card pre-gate

Goal:

Prevent thin signals from creating strong insights or strong decision cards.

---

### Phase 2: Claim-Level Verification

Implement:

- `ClaimExtractionService`
- `ClaimVerificationService`
- `VerifiedInsight` schema
- basic claim statuses
- uncertainty boundaries
- unsupported claim rewrite

Goal:

Turn raw insight into a claim-level verified object.

---

### Phase 3: Decision Card Consumes Verified Insight

Update `decision_card_service.py` so that decision card generation prefers verified insight.

Goal:

Avoid downstream action based on unverified raw insight.

---

### Phase 4: Reasoning Trace + Review Feedback

Implement:

- `ReasoningTraceService`
- structured trace persistence
- review loop metadata hooks where feasible

Goal:

Make insight quality auditable and future learning possible.

---

## 14. Acceptance Criteria

The implementation is acceptable when:

1. Existing signal insight output remains backward-compatible.
2. Thin signals are explicitly marked as thin/low-evidence.
3. Thin signals cannot produce high confidence.
4. Thin or unsupported insight cannot produce strong decision cards.
5. Insights include verification metadata.
6. Claims are classified by type and support level.
7. Unsupported or over-broad claims are identified.
8. Confidence includes reasons, not just a score.
9. Decision cards can reference verified insight ids.
10. Reasoning trace exists and stores audit metadata, not chain-of-thought.
11. Tests cover evidence sufficiency, low evidence gating, claim verification, confidence scoring, and decision card gating.

---

## 15. Important Implementation Notes

- Keep changes backward-compatible.
- Reuse existing provider routing and fallback where possible.
- Do not over-refactor existing services in the first pass.
- Prefer additive changes.
- Add logging around verification decisions.
- Avoid making LLM verifier the only source of truth.
- Use deterministic checks wherever possible.
- Keep Reflection human-in-loop unchanged.
- Treat verification as a system discipline, not just a prompt.

---

## 16. Recommended First Implementation Target

Start with Phase 1:

```text
EvidencePackService
EvidenceSufficiencyService
LowEvidenceGateService
DecisionCardGate
```

This gives the highest immediate quality gain with the lowest implementation risk.

The most urgent problem to solve is:

```text
Thin signal → overconfident insight → strong decision card
```

After Phase 1, move to claim-level verification.

---

## 17. Signal Verification MVP v1 Update

Updated: 2026-04-28

This section refines the next implementation target after the initial evidence-pack, evidence-sufficiency, low-evidence gate, provenance, and lightweight `VerifiedInsight` metadata foundations.

### 17.0 Module Doctrine: Evidence-Bounded Verification Layer

This capability should be treated as a first-class module:

```text
Evidence-Bounded Verification Layer
```

The module should not be designed as an automatic truth engine.

It should be designed as:

```text
AI Radar does not automatically prove signals true.
It classifies the evidential status of claims and controls downstream action eligibility.
```

Core product promise:

- automatically classify evidence
- automatically downgrade claims
- automatically gate downstream actions
- semi-automatically recommend project relevance
- preserve human final review for strategic value, project takeaways, roadmap changes, and actions

Core non-promise:

- do not automatically prove that an external signal is true
- do not automatically prove that a signal is valuable
- do not automatically change roadmap or create high-risk action items
- do not treat fluent LLM interpretation as verified evidence

Full architecture direction:

```text
Raw Signal / Raw Insight
-> Evidence Pack
-> Evidence Classification
-> Claim Extraction
-> Claim Verification
-> Project Relevance Assessment
-> VerifiedInsight
-> Downstream Action Gate
-> Human Review
```

MVP architecture:

```text
Raw Signal / Raw Insight
-> Evidence Pack
-> Evidence Sufficiency
-> Claim Extraction
-> Claim Verification
-> VerifiedInsight
-> Downstream Action Gate
```

Project relevance should be included in the model as a semi-automated next layer, but the first MVP may keep it as metadata or a later integration point if the claim verification slice is not ready to feed Project Takeaway Review.

The intended judgment split:

- truth / evidence support: classify at claim level
- reliability: classify from source traceability, provenance, excerpt availability, source count, and summary provenance
- project value: compare with project registry, current priorities, open questions, and active bets
- action eligibility: gate based on evidence level, claim support, claim type, caveats, and human review status

Tiered automation model:

| Level | Automation | Judgment |
| --- | --- | --- |
| Level 1 | High | source traceability / evidence sufficiency |
| Level 2 | High | claim extraction / claim type |
| Level 3 | Medium | claim-evidence matching |
| Level 4 | Medium | support status / caveats |
| Level 5 | Medium-low | value to active projects |
| Level 6 | Low | strategic action / roadmap change |

Rule of thumb:

```text
The closer a judgment is to factual traceability, the more it can be automated.
The closer a judgment is to strategic value or action, the more human review it needs.
```

The next slice should implement the signal verification judgment path:

```text
Raw Signal / Raw Insight
-> Evidence Pack
-> Evidence Sufficiency
-> Claim Extraction
-> Claim Verification
-> VerifiedInsight
-> Downstream Action Gate
```

This remains scoped to signal verification. It should not implement Project Takeaway Review UI, Decision Card expansion, Agent Watch / Friction convergence, Trajectory Memory, a new database layer, or live web verification.

### 17.1 Key Design Rule

Verification is claim-level, not insight-level.

A long summary, a source URL, or a high-level source reliability hint should not automatically make an insight verified. Evidence sufficiency only answers whether there is enough traceable material to attempt verification. Claim verification answers whether specific claims are supported by specific evidence items.

LLM-generated summaries are interpretation/context. They must not directly support claims as primary evidence.

### 17.2 EvidenceItem

Future evidence packs should be composed of evidence items.

Suggested fields:

```python
EvidenceItem(
    id: str,
    kind: str,  # primary_excerpt | structured_fact | collector_excerpt | interpreted_summary | context_note
    source_type: str | None,
    source_url: str | None,
    source_id: str | None,
    content: str,
    provenance: str,  # source_excerpt | structured_metadata | collector_extracted | manual_user_written | llm_generated | unknown
    traceable: bool,
    reliability_hint: str | None,  # high | medium | low | unknown
    metadata: dict = {},
)
```

Evidence roles:

- `source_excerpt`: primary evidence if traceable to `source_url` or `source_id`
- `structured_metadata`: primary evidence for metadata-level claims
- `collector_extracted`: usable evidence only when traceable
- `manual_user_written`: user context, not external factual evidence by default
- `llm_generated`: interpretation only, not direct evidence
- `unknown`: context only unless linked to traceable raw source material

### 17.3 Evidence Sufficiency

Evidence sufficiency should be rule-based and should not use summary length as a major evidence strength signal.

It answers:

```text
Do we have enough traceable material to attempt claim verification?
```

It does not answer:

```text
Is the insight true?
```

Suggested levels:

- `insufficient`: no traceable evidence item, only LLM-generated/unknown summaries, or no primary/structured/traceable collector evidence
- `thin`: one traceable item, weak/single-source evidence, or evidence that only supports that the signal exists
- `sufficient`: at least one direct traceable primary excerpt or structured fact suitable for descriptive claim verification
- `strong`: multiple independent traceable evidence items, or primary/structured evidence plus corroboration/recurrence metadata

### 17.4 Claim Extraction

Extract 1 to 5 claims from raw insight fields.

Claim types:

- `descriptive`
- `comparative`
- `trend`
- `causal`
- `predictive`
- `prescriptive`

Implementation should use deterministic sentence-level fallback first. LLM-assisted extraction can be added through existing routed execution helpers only if it remains behind a small service boundary and returns structured JSON.

Prescriptive claims are downstream action suggestions, not factual verification anchors.

### 17.5 Claim Verification

Claim verification answers:

```text
Does the evidence support this specific claim?
```

Support statuses:

- `directly_supported`
- `partially_supported`
- `inferred`
- `unsupported`
- `contradicted`

Deterministic caps:

- no matched evidence -> `unsupported`
- only `llm_generated` or `unknown` summary evidence -> cannot exceed `inferred`
- descriptive claim + primary excerpt / structured fact -> can be `directly_supported`
- comparative claim without baseline / peer comparison / metric -> cannot exceed `inferred` or `partially_supported`
- trend claim without multi-source evidence, recurrence, or repeated signals -> cannot exceed `partially_supported`
- causal claim defaults to `inferred` unless explicit causal evidence exists
- predictive claim should not be `directly_supported`
- prescriptive claim should be treated as action eligibility, not factual verification

LLM-assisted matching may help with semantic matching and caveats, but must use only provided evidence items and must return matched evidence item IDs.

### 17.6 VerifiedInsight Synthesis

`VerifiedInsight` should be synthesized from evidence sufficiency plus claim verification results.

Suggested statuses:

- `not_verifiable`: evidence level is insufficient
- `unsupported`: core claims are unsupported or contradicted
- `weakly_supported`: core claims are inferred only
- `partially_verified`: core descriptive claims are supported, but broader trend/causal/predictive claims are partial or inferred
- `verified`: core claims are directly supported and evidence level is sufficient or strong

Suggested fields:

```python
VerifiedInsight(
    verified_insight_id: str,
    source_signal_id: str | None,
    source_insight_id: str | None,
    evidence_pack_id: str,
    evidence_level: str,
    verification_status: str,
    claim_results: list[ClaimVerificationResult],
    limitations: list[str],
    allowed_downstream_actions: list[str],
    blocked_downstream_actions: list[str],
    max_confidence: float,
    downgrade_reason: str | None,
)
```

### 17.7 Downstream Action Gate

The action gate should combine:

- evidence level
- claim support status
- claim type
- limitations/caveats

It should not gate only on evidence level.

Suggested outputs:

- `observation_only`
- `watch_only`
- `project_takeaway_candidate`
- `low_risk_action_candidate`
- `action_blocked`

Rules:

- `insufficient` -> `observation_only`
- `thin` -> `watch_only` at most
- `sufficient + partially_verified` -> `project_takeaway_candidate`, action blocked
- `sufficient/strong + verified` -> `project_takeaway_candidate`, low-risk action candidate if no major unresolved caveat
- causal, predictive, and prescriptive claims should not create action eligibility unless the underlying descriptive/trend claims are verified

### 17.7A MVP Business Rules

The first MVP should enforce these rules even if LLM-assisted matching is not yet implemented:

1. LLM-generated summaries cannot count as primary evidence.
2. No traceable evidence means `observation_only`.
3. A single weak or non-corroborated source means `watch_only` at most.
4. Trend, causal, predictive, and prescriptive claims are automatically downgraded unless claim-appropriate corroborating evidence exists.
5. Only `verified` or `partially_verified` insights can become `project_takeaway_candidate`.
6. Roadmap changes and strategic actions require human review even when upstream factual claims are supported.

Example:

```text
Claim 1: This repo has recently become more active.
-> can be directly supported if traceable stars, commits, issues, or release data exist.

Claim 2: This repo represents an agent market trend.
-> should be partially supported or inferred unless broader multi-source trend evidence exists.

Claim 3: This trend matters to AI Radar.
-> requires project relevance mapping plus human review.

Claim 4: We should adjust the roadmap.
-> cannot become automatic action; it can only become watch/review/action-candidate after human judgment.
```

### 17.8 Integration Target

The first integration point should be signal insight generation.

After raw signal insight generation, run:

```python
SignalVerificationService.verify_signal_insight(signal, raw_insight)
```

Attach the resulting `VerifiedInsight` metadata to the signal insight response and persistence path in a backward-compatible way.

Do not route this into legacy `Decision Card` as the primary path. The intended downstream consumer is `Project Takeaway Review`.

### 17.9 Tests

Add deterministic tests for:

- title + LLM-generated summary only -> `insufficient`, `not_verifiable`, observation only
- one traceable collector excerpt -> `thin`, no action eligibility
- one primary excerpt supporting descriptive claim -> descriptive claim `directly_supported`, project takeaway candidate allowed
- trend claim with one source -> no higher than `partially_supported`
- comparative claim without baseline -> caveat and capped support
- causal claim with only correlation -> `inferred`
- predictive claim -> not directly supported
- multiple independent traceable evidence items -> `strong`
- LLM-generated summary cannot directly support a claim

Existing evidence-pack, evidence-sufficiency, verified-insight metadata, and backend signal workflow tests should continue to pass.
