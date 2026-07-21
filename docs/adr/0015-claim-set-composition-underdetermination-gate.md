---
adr: 0015
title: Claim-Set Composition Underdetermination Gate
status: Proposed
created: 2026-07-05
layer: L1-governance-decision
related:
  - L1: docs/adr/0010-external-insight-admission-gate.md
  - L2: agent-skills/grill-the-inference/SKILL.md
  - L2: agent-skills/grill-the-inference/validation/001-dual-model-cross-execution.md
tags: [verification, underdetermination, claim-composition, agent-skill, layer-a-prime]
---

# ADR-0015: Claim-Set Composition Underdetermination Gate

## ADR Gate

Create this ADR only if all are yes:

- [x] Hard to reverse: once verified insights can be promoted from individually
  verified claims without a composition-level check, downstream intelligence can
  inherit over-strong conclusions that are costly to unwind.
- [x] Context would be lost: future readers would ask why per-claim
  verification, `inference_distance`, and low-evidence gating do not already
  cover claim-set-to-conclusion reasoning.
- [x] Real tradeoff: plausible alternatives include treating the issue as a
  prompt-quality problem, extending existing claim verification, or deferring
  all composition checks to human review with no explicit protocol.

## ADR-0010 Admission Gate Result

Outcome: `admit`, in modified form.

Smallest admitted scope:

- recognize a confirmed verification-spine gap at the claim-set composition
  layer
- keep `grill-the-inference` as a Layer A' review protocol and calibration
  artifact
- record validation evidence and open items for future runtime consideration
- do not authorize runtime blocking, schema migration, service creation,
  Project Takeaway changes, or `blocked_downstream_actions` changes

This admission does not approve an automatic runtime gate.

## Context

AI Radar's verification spine promotes insights through per-claim verification
and aggregation. Repo inspection in 2026-07 confirmed that the current
promotion path verifies claims individually and aggregates claim-level results
into a verification status, but does not check whether the load-bearing claim
set is sufficient to support the aggregate insight conclusion.

Confirmed code-level evidence:

- `backend/app/services/claim_verification_service.py:608`
  `verify_claims_against_evidence()` iterates per claim, emitting
  `support_level`, `inference_distance`, `risk_level`,
  `presentation_fidelity`, and `scalar_fidelity` as single-claim measures.
- `backend/app/services/verified_insight_service.py:18`
  `_normalized_status()` reads the set of per-claim `support_level` values and
  `evidence_level`.
- `backend/app/services/verified_insight_service.py:253`
  `build_verified_insight_metadata()` has no `warrant`,
  `load_bearing_claims`, composition, or underdetermination field.
- `backend/app/services/low_evidence_gate_service.py:6`
  `build_low_evidence_gate()` gates on evidence quality level only.

Clarification: `inference_distance` is a per-claim measure
(claim-to-evidence), not a claim-set-to-conclusion measure. It does not close
this gap.

The gap was surfaced by the Brain2Qwerty v2 review: an insight such as
"approaching implant-level accuracy" can be supported by individually verified
claims while the same claim set also supports a materially weaker conclusion,
such as "still substantially behind implants." The distortion lives in the
composition of claims, not inside any single claim.

## Decision

Recognize the claim-set composition / underdetermination gate as a net-new
operator acting on the claim set, distinct from existing per-claim verification
and aggregation logic in the promotion path.

Mechanism, as validated at Layer A' by `grill-the-inference`: given an insight
conclusion and its load-bearing claims, attempt to construct a plausible
contrary conclusion from the same claims. If such a counter-conclusion is
constructible and the warrant does not distinguish the original conclusion as
preferred, mark the conclusion `underdetermined`.

This ADR does not authorize any change to the `verified_insight` schema. Future
runtime promotion would require either `warrant` / `load_bearing_claims` fields
or an attached `reasoning_assessment` object. That choice is deferred to a
separate runtime-admission ADR and is explicitly out of scope here.

Hard boundary:

- The gate judges underdetermination only, never truth. Output is about whether
  a claim set is sufficient to determine a conclusion, not whether the opposite
  conclusion is true.
- Reasoning validity is not fully auto-decidable. Final adjudication remains
  with a human reviewer or a separately admitted higher-authority agent path.

## Owns

- The architectural recognition that claim-set-to-conclusion support is a
  distinct verification layer.
- The rule that this layer is not already covered by per-claim
  `inference_distance`, per-claim verification, status aggregation, or the
  low-evidence gate.
- The Layer A' status of `grill-the-inference` as the current review protocol
  and calibration path for this operator.
- The underdetermination-only safety boundary for counter-conclusion
  construction.
- The requirement that future runtime promotion must be separately admitted.

## Does Not Own

- `verified_insight` schema changes.
- Backend services, routes, storage paths, migrations, or prompt execution.
- Project Takeaway gates, overrides, review outcomes, or action eligibility.
- `blocked_downstream_actions` behavior.
- `docs/adr/INVARIANTS.md`.
- Automatic caveat-stripping, source-limit capture, or runtime
  `source_stated_limits` coverage policy.
- Historical backfill of existing insights.

## Admitted Scope

Admitted now:

- Layer A' review protocol: `agent-skills/grill-the-inference/SKILL.md`
- Layer A' calibration and validation records under
  `agent-skills/grill-the-inference/`
- ADR-level recognition of the claim-set composition gap and the net-new
  operator shape

Not admitted now:

- automatic runtime blocking gate
- schema migration or required new fields
- `blocked_downstream_actions` mapping
- Project Takeaway integration
- full automation of `caveat_stripping`

Rationale: `grill-the-inference` has initial validation evidence across all
three verdict branches, but only two branches have true dual-model validation:

- `pass` and `underdetermined`: true dual-model validated
- `needs_human_judgment`: prediction-vs-execution only, one tier weaker
- total sample count remains small
- one open item remains: attack-path value under a missing warrant

## Consequences

Positive:

- Closes a confirmed spine gap: composition-level distortion is currently
  invisible to promotion.
- Keeps the operator substrate-independent from per-claim verification, so it
  can be calibrated as Layer A' process before any runtime work.
- Preserves the distinction between "evidence supports each claim" and "the
  claim set determines this conclusion."

Negative / accepted risks:

- Adds a new review concept that future contributors must distinguish from
  ordinary claim verification.
- If later promoted to runtime, mapping `underdetermined` to
  `blocked_downstream_actions` would touch an invariant-level boundary and
  require separate admission.
- Any `warrant` / `load_bearing_claims` representation carries migration cost
  against current `verified_insight` data. The field-vs-attached-object choice
  is deliberately deferred.

## Alternatives Considered

### Treat as Prompt Quality Only

Rejected. Prompt improvements may reduce over-strong conclusions, but they do
not create an auditable check for whether verified claims compose into the
insight conclusion.

### Extend Per-Claim Verification

Rejected. The failure mode is not inside a single claim. Extending
single-claim measures such as `inference_distance` would blur the distinction
between claim-to-evidence support and claim-set-to-conclusion support.

### Use Existing Low-Evidence Gate

Rejected. The low-evidence gate is evidence-level based. A conclusion can be
underdetermined even when its component claims have sufficient evidence.

### Promote Directly to Runtime Gate

Rejected for this ADR. The Layer A' protocol has useful validation evidence,
but sample count is still small, the abstention branch is not true dual-model
validated, and runtime integration would touch schema and downstream-action
boundaries.

## Implementation Plan

No runtime implementation is approved by this ADR.

Allowed current work:

1. Continue using `grill-the-inference` as a Layer A' review protocol.
2. Expand calibration samples across `pass`, `underdetermined`, and
   `needs_human_judgment`.
3. Run a true dual-model validation round for the abstention branch.
4. Observe whether the missing-warrant attack-path open item reproduces before
   changing the skill.
5. Measure and improve source-limit capture before proposing any automated
   `caveat_stripping` path.

Future runtime work, if separately admitted:

1. Choose a representation: schema fields or attached `reasoning_assessment`.
2. Define provenance and audit requirements for composition verdicts.
3. Decide whether, and how, `underdetermined` maps to
   `blocked_downstream_actions`.
4. Add tests proving that ordinary Project Takeaway and low-risk Action paths
   cannot bypass the new boundary.

## Open Items

- OI-1: Under a missing warrant, whether an attack path should read `risk` or
  `not_applicable` is unspecified. Do not patch until a true dual-model run
  reproduces the divergence.
- OI-2: Same-source caveat capture depends on source-limit metadata quality.
  Do not automate `caveat_stripping` until coverage and capture semantics are
  measured and improved.

## References

- ADR-0010: External Insight Intake Requires Author-Side Admission Gate
- `agent-skills/grill-the-inference/SKILL.md`
- `agent-skills/grill-the-inference/calibration/001-brain2qwerty-v2-announcement.md`
- `agent-skills/grill-the-inference/validation/001-dual-model-cross-execution.md`
- `backend/app/services/claim_verification_service.py`
- `backend/app/services/verified_insight_service.py`
- `backend/app/services/low_evidence_gate_service.py`
