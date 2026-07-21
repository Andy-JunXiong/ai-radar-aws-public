---
adr: 0012
title: Signal Claim Review Feedback Capture
status: Accepted
created: 2026-06-13
accepted: 2026-06-13
layer: L1-engineering-solution
related:
  - L1: docs/adr/0008-signal-lifecycle-event-spine.md
  - L1: docs/adr/0009-model-provenance-schema.md
  - L1: docs/adr/0010-external-insight-admission-gate.md
  - L1: docs/adr/0011-evidence-pack-source-excerpt-policy.md
  - L1-index: docs/adr/INVARIANTS.md
tags: [signal-review, claim-feedback, input-provenance, verification-boundary]
---

# ADR-0012: Signal Claim Review Feedback Capture

## ADR Gate

Create this ADR only if all are yes:

- [x] Hard to reverse: once claim-level review feedback becomes part of Signal
  Detail, its record shape and downstream boundaries will affect future review,
  learning, and calibration features.
- [x] Context would be lost: future readers would ask why AI Radar captures
  "not right" feedback without immediately changing source scoring, background
  context, prompts, Project Takeaway gates, or claim verification status.
- [x] Real tradeoff: plausible alternatives include reusing Project
  CalibrationEvent as the primary store, adding fields directly to verified
  insight, auto-updating background context, or postponing feedback capture
  until all downstream loops are designed.

## ADR-0010 Admission Gate Result

Outcome: `admit`, scoped to an ADR draft and future minimal capture slice.

Smallest admitted scope:

- add a claim-level Signal review feedback record
- add an independent `input_provenance` envelope
- define a four-slot `reason_slot` enum
- define advisory distortion tags
- preserve existing verification, Project Takeaway, Reflection, source excerpt,
  and lifecycle boundaries

This scope is admitted because it maps to an observed product gap: Signal
Detail can show Evidence Grounding and claim checks, but a human who finds a
claim "not right" has no structured place to record why. The admitted work is
replacement-oriented because it uses the existing claim verification and
Evidence Grounding surfaces as the substrate instead of creating another review
framework. It is not an implementation approval for automatic source scoring,
background context mutation, prompt mutation, or Project Takeaway gate changes.

## Context

AI Radar already has most of the structural claim-verification layer:

- `claim_extraction_service.py` extracts claims from generated insights.
- `claim_verification_service.py` checks claims against evidence packs and
  emits support level, origin, source-span, risk, and verification notes.
- `evidence_pack_service.py` builds traceable evidence items, including bounded
  source excerpts when allowed by ADR-0011.
- `verified_insight_service.py` derives verification status, confidence,
  allowed downstream actions, and blocked downstream actions.
- Signal Detail already renders Evidence Grounding, review priority, source
  span coverage, and Project Takeaway gate state.

The missing piece is not another structural verifier. The missing piece is a
human feedback capture layer for cases where the user sees that a claim or
insight is "not right" and needs to preserve why.

The four feedback slots are:

- `stale_input`: the signal, source, project snapshot, or context used by the
  insight appears out of date.
- `not_me`: the generated insight does not match the user's actual background,
  priorities, judgment style, or project understanding.
- `reasoning_gap`: the generated insight jumps from evidence to conclusion too
  quickly or fuses claims that should stay separate.
- `blind_spot`: the generated insight exposes something the user may not have
  previously considered.

Current downstream improvement loops are not all ready:

- source quality and source health exist, but there is no user-feedback-driven
  source scoring loop for this slice
- personal and project context inputs exist, but automatic background mutation
  would make the review reference frame drift
- prompt provenance exists, but there is no live prompt scorer or prompt update
  loop for claim-level review failures
- Reflection and cognitive-log surfaces exist, but cognitive context must not
  become factual evidence or bypass verification gates

This ADR therefore chooses capture first. Routing into improvement loops is a
future decision.

## Decision

Adopt a dedicated Signal claim review feedback capture model.

The primary record should be a new feedback record, not a Project
CalibrationEvent. A future implementation may also soft-record a lifecycle-style
audit event for visibility, but the canonical feedback store is separate from
Project Takeaway review and calibration.

Implemented service and storage shape:

```text
backend/app/services/signal_review_feedback_service.py
backend/data/signal_review_feedback/index.json
backend/data/signal_review_feedback/<feedback_id>.json
```

Record schema shape:

```json
{
  "id": "srf_<stable-or-random-id>",
  "schema_version": 1,
  "record_type": "signal_claim_review_feedback",
  "signal_id": "signal-id",
  "insight_id": "optional-insight-id",
  "content_fingerprint": "optional-content-fingerprint",
  "claim_id": "claim_1",
  "claim_text_snapshot": "The claim text at review time.",
  "claim_source_field": "synthesized_insight",
  "reason_slot": "reasoning_gap",
  "distortion_tags": ["juxtaposition_fusion"],
  "note": "Short user feedback explaining what is not right.",
  "verification_snapshot": {
    "verification_status": "partially_verified",
    "evidence_level": "thin",
    "claim_support_summary": {
      "directly_supported": 0,
      "partially_supported": 1,
      "inferred": 3,
      "unsupported": 1,
      "contradicted": 0
    },
    "confidence_score": 0.55,
    "confidence_label": "medium",
    "allowed_downstream_actions": ["reflection_draft", "watch_only"],
    "blocked_downstream_actions": [
      "decision_card",
      "project_takeaway_candidate",
      "low_risk_action_candidate"
    ],
    "claim_result_snapshot": {}
  },
  "input_provenance_snapshot": {},
  "downstream_effect": "none",
  "evidence_boundary": "not_external_claim_evidence",
  "background_update_candidate_id": "",
  "created_by": "human",
  "created_at": "2026-06-13T00:00:00+00:00"
}
```

### Reason Slot Enum

The initial `reason_slot` values are:

```text
stale_input
not_me
reasoning_gap
blind_spot
```

These are routing labels for future review and analysis. They do not imply an
automatic downstream action in this ADR.

### Advisory Distortion Tags

`distortion_tags` are optional advisory tags. They do not replace claim support
status and they do not change verification status.

Initial tags may include:

```text
fabricated_attribution
source_asserted_but_unsubstantiated
pseudo_precision
juxtaposition_fusion
causal_overreach
category_collapse
context_drift
personal_context_mismatch
```

The canonical claim support labels remain:

```text
directly_supported
partially_supported
inferred
unsupported
contradicted
```

### Input Provenance Envelope

Adopt a separate `input_provenance` envelope for review-time input freshness.

This envelope is independent from ADR-0009 `produced_by_model`. Model
provenance records which model path produced a judgment. Input provenance
records which source and context inputs were used or visible when the judgment
was reviewed.

Envelope shape:

```json
{
  "schema_version": 1,
  "captured_at": "2026-06-13T00:00:00+00:00",
  "signal": {
    "published_at": "",
    "collected_at": "",
    "source_excerpt_length": 0
  },
  "user_context": {
    "context_scope": "user_specific",
    "captured_at": ""
  },
  "project_context": {
    "repo_snapshot_scanned_at": "",
    "repo_snapshot_status": ""
  },
  "project_context_cache": {
    "fetched_at": "",
    "ttl_hours": 12
  },
  "freshness": {
    "stale_flags": [],
    "freshness_penalty": 0,
    "summary": "No stale input detected."
  }
}
```

`freshness_penalty` is deterministic and bounded. It may contribute to a future
review uncertainty score, but it does not change claim verification status or
downstream action eligibility.

### Deterministic Review Uncertainty

Future implementation may derive a review uncertainty score without asking an
LLM to produce confidence.

The initial formula direction is:

```text
review_uncertainty =
  1 - confidence_score
  + unsupported_claim_penalty
  + inferred_claim_penalty
  + stale_input_penalty
```

The score is a review triage aid only. It must not unlock or block Project
Takeaway, low-risk Action, claim verification status, or source evidence status.

### Boundary Decision A: Blind Spot Sink

Blind-spot feedback can change the system's understanding of the user. It
cannot change the system's claims about the external world.

Allowed downstream posture:

- user attention calibration
- future review prioritization
- candidate context for user-confirmed background model updates
- cognitive context clearly marked as not external claim evidence

Blind-spot feedback may become candidate context for a future background update
queue only when it represents a possible change in the system's understanding
of the user. A blind-spot record is not itself a background update. It remains
review context until the user explicitly confirms a separate background update
candidate.

Forbidden downstream posture:

- evidence pack input
- claim verification support
- verified insight status upgrade
- Project Takeaway eligibility
- low-risk Action eligibility
- any bypass of `blocked_downstream_actions`
- any automatic background context update

Code and schema should preserve this by writing:

```text
evidence_boundary = "not_external_claim_evidence"
downstream_effect = "none"
```

Any future consumer of blind-spot records must answer this boundary question:

```text
Does this change the system's understanding of the user, or the system's claim
about the external world?
```

Only the first is allowed under this ADR.

### Boundary Decision B: Background Update Candidate Queue

`not_me` feedback must not automatically update personal context, project
context, or any background model.

The correct future sink is a user-confirmed background update candidate queue.
No update becomes active until the user explicitly confirms it.

If a future slice allows both `not_me` and `blind_spot` records to create
background update candidates, both paths must obey the same three gates:

1. The feedback record can create only a candidate, not an active update.
2. The candidate must remain inactive until explicit user confirmation.
3. The candidate can update only user/system-understanding context, never
   external-world claims, verification status, Project Takeaway eligibility,
   low-risk Action eligibility, or any other action gate.

The reason is reference-frame stability. Background context is part of the
reference frame the user uses during review. If "not me" feedback automatically
rewrites the reference frame, the user can no longer tell whether the insight
was wrong or the reference frame drifted.

This ADR only defines the boundary. It does not create the queue. A future
slice may add a queue such as:

```text
backend/app/services/background_update_candidate_service.py
backend/data/background_update_candidates/
```

## Owns

- The existence and purpose of Signal claim review feedback records.
- The rule that feedback capture is the first slice and does not automatically
  route into source scoring, background mutation, prompt mutation, or Project
  Takeaway gates.
- The initial `reason_slot` enum.
- The advisory distortion-tag posture.
- The independent `input_provenance` envelope for review-time input freshness.
- The blind-spot sink boundary: cognitive/user-understanding only, not external
  claim evidence.
- The background update boundary: `not_me` feedback creates candidates only,
  never automatic context mutation.
- The rule that review uncertainty is deterministic and advisory.

## Does Not Own

- Claim extraction, claim support labels, source-span verification, or evidence
  sufficiency scoring.
- Project Takeaway candidate policy, review outcomes, Watch, Action, overrides,
  or `blocked_downstream_actions`.
- Source scoring formulas, source removal policy, or source health checks.
- Prompt template changes, prompt scoring, or automatic regeneration policy.
- Background update candidate queue implementation.
- Reflection editing, cognitive-log schema, or Reflection-to-evidence
  conversion paths.
- Model provenance schema, which remains governed by ADR-0009.
- Source excerpt retention policy, which remains governed by ADR-0011.
- Lifecycle hard enforcement, which remains governed by ADR-0008.

## Consequences

AI Radar gains a structured way to preserve human disagreement with generated
claims without pretending the disagreement is source evidence.

This makes future review and learning loops possible while keeping the first
implementation slice narrow.

The main benefit is epistemic separation:

- claim verification still answers whether the claim is supported by evidence
- review feedback records why the human thinks the generated claim or framing
  is not right
- input provenance makes stale inputs visible at review time
- background updates remain user-confirmed

The main cost is another small persisted record family. The mitigation is that
the record is explicitly a capture layer, not a new action gate or review
framework.

The UI cost is non-trivial. Adding a visible "Not right" action in Signal
Detail changes user-facing workflow semantics and therefore triggers the
Operator Guidance contract rule. The implementation slice must update guidance
logic and add or adjust `npm.cmd run test:guidance` cases.

## Alternatives Considered

### Alternative 1: Reuse Project CalibrationEvent As The Primary Store

Rejected.

Project CalibrationEvent is tied to Project Takeaway, Watch, Action, manual
override, and project review memory. Claim-level "not right" feedback happens
earlier and can apply even when a signal is not eligible for Project Takeaway.
Using CalibrationEvent as the primary store would blur Project review semantics.

A future lifecycle-style audit event may reference feedback records, but the
feedback record itself should remain the canonical store.

### Alternative 2: Add Feedback Directly To Verified Insight

Rejected.

Verified insight metadata carries evidence support, verification state,
confidence, and downstream action policy. Human disagreement feedback is
review context, not support evidence. Embedding it directly into verified
insight risks making review feedback look like a verification input.

### Alternative 3: Automatically Update Background Context

Rejected.

Automatic background mutation breaks reference-frame stability. `not_me`
feedback must enter a candidate queue and wait for explicit user confirmation.

### Alternative 4: Immediately Route Each Reason Slot To Its Improvement Loop

Rejected for this slice.

The source scoring loop, background update flow, prompt improvement loop, and
blind-spot cognitive sink are not all implemented or governed at equal maturity.
Capturing structured feedback first avoids coupling the UI to immature
downstream loops.

### Alternative 5: Ask The LLM To Produce A Fresh Confidence Score

Rejected.

AI Radar already has evidence quality, claim support, confidence caps, and UI
review priority. Review uncertainty should be deterministic and explainable
before any model-based scorer is considered.

## Implementation Status

This ADR was accepted after the minimal capture slice was implemented and
validated on 2026-06-13. The slice list below records the implemented shape
and the deferred boundaries that remain outside this ADR.

Implemented:

- backend feedback record service and JSON-backed local record family
- independent input provenance helper
- admin-guarded create/list API route at `/signal-review-feedback`
- Signal Detail `Not right` claim-level feedback UI
- read-only recorded feedback count/list on Signal Detail
- Operator Guidance contract coverage for the capture-only boundary

Still out of scope:

- source scoring updates
- background context mutation
- prompt or generation changes
- Project Takeaway gate changes
- cognitive-log routing
- downstream action eligibility changes

### Implemented Slice 1: Backend Capture Model

Created:

- `backend/app/services/signal_review_feedback_service.py`
- `backend/data/signal_review_feedback/index.json`
- per-record JSON files under `backend/data/signal_review_feedback/`
- focused tests for enum validation, snapshot preservation, and no mutation of
  verification metadata

No database table is required for the local-file implementation. A database
table would be a later storage decision.

### Implemented Slice 2: Input Provenance Helper

Created a small helper to build `input_provenance_snapshot` from existing
fields:

- signal `published_at`
- signal `collected_at`
- signal `source_excerpt_length`
- context `context_scope`
- project repo snapshot `scanned_at`
- project repo snapshot `status`
- project context cache `fetched_at`
- project context cache TTL, initially `12`

This is a field/helper extension, not a new subsystem.

### Implemented Slice 3: Signal Detail Feedback UI

Added a "Not right" affordance under existing claim rows in Signal Detail.

The UI collects:

- reason slot
- optional advisory distortion tag
- one short note

The UI must not show the feedback as changing verification status, Project
Takeaway gate state, source reliability, or Action eligibility.

This slice triggered the Guidance Contract Rule. Operator Guidance was updated
and `npm.cmd run test:guidance` was run before handoff.

### Implemented Slice 4: Read-Only Feedback Visibility

Shows recent feedback records as read-only review context on Signal Detail.

### Deferred Slice: Background Update Candidate Queue

If `not_me` feedback proves useful, design a separate user-confirmed background
update candidate queue. This requires a separate slice because it changes how
personal/project context becomes active.

### Deferred Slice: Downstream Loop Routing

Route feedback into source scoring, prompt improvement, cognitive-log, or
background update flows only after each target loop has its own boundary and
tests.

## Acceptance Criteria

- Feedback records preserve claim, verification, and input provenance snapshots
  as they existed at review time.
- Creating feedback does not mutate verified insight, claim support status,
  evidence packs, Project Takeaway candidates, source scoring, personal
  context, project context, or prompts.
- `blind_spot` feedback is marked as cognitive/user-understanding context only.
- `not_me` feedback does not update background context automatically.
- Any `blind_spot` or `not_me` background update candidate remains inactive
  until explicit user confirmation and cannot update external-world claims,
  verification status, Project Takeaway eligibility, low-risk Action
  eligibility, or any other action gate.
- UI review uncertainty remains advisory and deterministic.
- `review_uncertainty`, `freshness_penalty`, and related stale-input summaries
  must not be read by Project Takeaway, Action, claim verification, source
  scoring, or source-health paths as gate inputs.
- Operator Guidance explains the new feedback action without implying it is a
  verification result or action gate.
- Tests prove no ordinary Confirm, Action, or Project Takeaway path bypasses
  `blocked_downstream_actions`.

## References

- [ADR-0008: Signal Lifecycle Event Spine](./0008-signal-lifecycle-event-spine.md)
- [ADR-0009: Model Provenance Schema](./0009-model-provenance-schema.md)
- [ADR-0010: External Insight Intake Requires Author-Side Admission Gate](./0010-external-insight-admission-gate.md)
- [ADR-0011: Evidence Pack Source Excerpt Policy](./0011-evidence-pack-source-excerpt-policy.md)
- [Architecture Invariants](./INVARIANTS.md)
