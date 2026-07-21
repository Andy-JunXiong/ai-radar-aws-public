---
adr: 0013
title: AI Discussion Governed Claim Boundary
status: Accepted
created: 2026-06-24
accepted: 2026-06-24
layer: L1-architecture-decision
related:
  - L1: docs/adr/0010-external-insight-admission-gate.md
  - L1: docs/adr/0011-evidence-pack-source-excerpt-policy.md
  - L1: docs/adr/0012-signal-claim-review-feedback-capture.md
  - L1-index: docs/adr/INVARIANTS.md
tags: [memory-layer, ai-discussion, governed-claim, verification-boundary, audit-boundary]
---

# ADR-0013: AI Discussion Governed Claim Boundary

## ADR Gate

Create this ADR only if all are yes:

- [x] Hard to reverse: once AI Discussion memory stores claim-like objects,
  their boundary will shape future memory, retrieval, review, and verification
  behavior.
- [x] Context would be lost: future readers would ask why AI Discussion memory
  claims do not directly become verified evidence or action-eligible
  intelligence.
- [x] Real tradeoff: plausible alternatives include treating all memory as
  generic notes, making `governed_claim` the universal AI Radar claim atom, or
  letting external memory frameworks define the schema.

## ADR-0010 Admission Gate Result

Outcome: `admit`, in modified form.

Smallest admitted scope:

- define a boundary for AI Discussion memory-layer claim objects
- keep `governed_claim` scoped to AI Discussion memory only
- preserve existing verification spine objects and Project Takeaway gates
- preserve Reflection, Signal, Manual Upload, Workspace, and external Signal
  boundaries
- do not authorize implementation, schema migration, service creation, or
  historical backfill

This admission does not approve ADR-0014, external memory framework absorption,
Mem0/Zep/Letta/Cognee/Hindsight integration, or code changes.

## Context

AI Radar already has a verification spine:

```text
evidence_pack -> claim_verification -> verified_insight -> low_evidence_gate
```

That spine determines whether generated claims are supported by source evidence
and what downstream actions are allowed or blocked.

AI Radar also has Reflection and discussion-style cognitive surfaces. These
surfaces can preserve reasoning, judgment, disagreement, and evolving
interpretation, but they are not factual evidence for external claims by
default.

The proposed memory layer needs a claim-like atom, but that atom must not
swallow existing verification objects or silently convert discussion judgments
into evidence. The memory layer also must not import external memory-system
worldviews wholesale. Its boundary should be AI Radar-native:
verification-aware, audit-visible, and resistant to scope creep.

## Decision

Adopt `governed_claim` as the memory-layer wrapper for AI Discussion claims.

`governed_claim` is scoped only to the AI Discussion memory layer. It is not the
universal claim atom for all of AI Radar.

Initial admitted surface:

```text
AI Discussion collaboration records only
```

Out of scope unless separately admitted:

```text
Reflection
Workspace chat
Manual Upload
external Signals
Project Takeaway records
existing verified_insight records
historical review records
```

The boundary is defined by product surface and evidence boundary, not by vendor
or implementation source. The ontology must not be named after Claude, Codex,
OpenAI, Anthropic, or any provider-specific API path.

ADR-0013 separates subject from origin. A governed claim may discuss an
external source as its subject while remaining supported only by AI Discussion
context. That does not admit external sources, Signals, Reflection, Workspace,
Manual Upload, or external memory systems as direct capture or write origins.
Direct external/import origins remain out of scope unless separately admitted.

### Load-Bearing Decision 1: Live-State Forms

Within live mutable `governed_claim` state, mechanisms must reduce to one of:

```text
attribute
edge
operator
```

- `attribute`: state of one governed claim
- `edge`: typed relation between governed claims
- `operator`: rule that reads or changes attributes/edges over time

This exhaustiveness claim applies only to live mutable governed-claim state.

Audit and provenance are not a fourth live-state form. They belong to an
append-only audit/provenance plane outside the mutable ontology.

### Load-Bearing Decision 2: Audit Obligation

Plane separation does not make audit optional.

Any write that changes a `governed_claim` attribute or edge must leave an audit
trace, such as `audit_refs` or an append-only audit record.

This obligation is action-based, not ownership-based. It applies regardless of
which service, operator, import path, or future bridge initiates the change.

Existing verification-spine paths are not made invalid by this ADR because they
do not currently mutate `governed_claim`.

### Load-Bearing Decision 3: Axis Orthogonality

The following axes are orthogonal and must not substitute for each other:

```text
traceability
verification_support
temporal_validity
salience
```

- Traceability says where material came from and whether it can be followed.
- Verification support says whether a claim is supported by evidence.
- Temporal validity says whether the claim or reference is current,
  superseded, or valid as of a time.
- Salience says whether the claim deserves retrieval, formalization, or review
  attention.

Salience must not determine action eligibility. It may influence retrieval,
formalization, or review priority, but it must not bypass verification support
or `blocked_downstream_actions`.

### Load-Bearing Decision 4: Wrapper, Not Replacement

`governed_claim` must not replace or rename:

```text
claim_verification
verified_insight
evidence_pack
low_evidence_gate
```

A governed claim may reference verification-spine objects, but it does not own
or duplicate their authority.

Required semantic slots, exact names pending repo-signature alignment:

```text
verification_ref        # pending repo-signature alignment
verification_ref.as_of  # pending repo-signature alignment
claim_snapshot          # pending repo-signature alignment
```

A `verification_ref` may point to an existing `verified_insight_id`, claim
result snapshot, or other existing spine object as of a specific time.

### Load-Bearing Decision 5: Discussion Judgment Boundary

A governed claim may be about an external paper, repository, company, product,
or source. That does not make it external evidence.

The difference is not what the claim is about. The difference is the support
boundary.

This is also the subject/origin boundary: an external source may be the
`asserted_subject` of a discussion judgment, but it must not become the
capture/write origin for AI Discussion memory unless a future admission and
write path explicitly allow that origin.

Allowed memory-layer shape:

```text
In this AI Discussion, we judged that Paper X may support Y, pending verification.
```

Not allowed as memory-layer evidence:

```text
Paper X proves Y.
```

ADR-0013 requires semantic slots equivalent to:

```text
claim_posture     # pending repo-signature alignment
asserted_subject  # pending repo-signature alignment
support_boundary  # pending repo-signature alignment
verification_ref  # pending repo-signature alignment
```

The `verification_ref` slot here is the same semantic slot introduced in
Load-Bearing Decision 4, not a second field.

`claim_posture` distinguishes discussion judgment, pending verification
judgment, decision rationale, and other non-evidence postures.

`asserted_subject` may point to an external topic.

`support_boundary` must identify the claim as supported by discussion context,
not external evidence, unless and until a separate explicit promotion path
connects it to the verification spine.

Do not name this slot `evidence_basis` in the final schema unless a later schema
review proves it cannot be confused with verification-spine evidence semantics.

### Load-Bearing Decision 6: Promotion And Re-Reference

Discussion-origin or Reflection-origin claims must not become evidence or feed
Project Takeaway low-risk action unless an explicit promotion path is designed
and used.

Promotion direction:

```text
discussion/reflection context -> verification/evidence path
```

must be explicit, audited, and gate-preserving.

Synchronization direction:

```text
verification spine update -> memory reference update
```

must also be explicit.

A governed claim holds an as-of reference or snapshot. If the source
`verified_insight` or claim verification state later changes, the governed
claim is not automatically updated.

Updating the memory reference requires an explicit `re-reference` action and
audit trace.

### Load-Bearing Decision 7: Non-Retroactive Scope

This ADR does not require historical records to be converted into governed
claims.

No automatic backfill is approved for:

```text
Reflection records
verified_insight records
claim_verification results
Project ReviewRecords
CalibrationEvents
Signal lifecycle events
Manual Upload sessions
Workspace records
```

Future import or backfill may be proposed separately, but this ADR does not
authorize it.

## Owns

- The boundary of `governed_claim` for AI Discussion memory.
- The rule that governed claims are memory-layer wrappers, not
  verification-spine replacements.
- The live-state ontology for governed claims: attribute, edge, operator.
- The separation between live mutable claim state and append-only
  audit/provenance plane.
- The audit obligation for any write that mutates governed-claim attributes or
  edges.
- The orthogonality of traceability, verification support, temporal validity,
  and salience.
- The rule that discussion judgments can be about external subjects without
  becoming external evidence.
- The as-of snapshot / explicit re-reference rule for verification references.
- The non-retroactive boundary.

## Does Not Own

- Implementation schema names or field types.
- Backend services, routes, storage paths, or migrations.
- ADR-0014 or any external memory mechanism ingestion lifecycle.
- The existing verification spine.
- Project Takeaway gates, overrides, or action eligibility.
- Reflection schema or Reflection-to-evidence promotion design.
- Signal, Manual Upload, Workspace, or Project Review storage semantics.
- Historical backfill.
- AGENTS.md invariants.

## Consequences

Positive:

- AI Discussion memory gains a governed claim boundary without polluting
  existing verification objects.
- Discussion judgments can be preserved without pretending to be external
  evidence.
- Future memory operators must be auditable by construction.
- External-memory-system concepts cannot enter as free-floating grafts.
- Salience, provenance, verification, and time validity remain separate.

Negative / accepted tradeoffs:

- The memory layer cannot be implemented by dropping in a generic memory
  framework unchanged.
- More explicit audit work will be required for future memory writes.
- Some useful external-memory mechanisms must wait for ADR-0014.
- Field names remain pending until repo-signature alignment is performed.

Review lineage:

- Accepted from Codex review: `governed_claim` must wrap/reference, not replace
  `verified_insight`; provenance must not mean trust; salience must not become
  action eligibility; ADR-0013 is not a MADR.
- Accepted from Claude review: choose plane separation instead of adding
  `audit_record` as a fourth live-state form; define audit obligation as
  load-bearing; add bidirectional promotion/re-reference boundary.
- Joint refinement: define AI Discussion by product surface and evidence
  boundary, not provider; structure the external-subject/discussion-judgment
  distinction through pending semantic slots.

## Acceptance Notes

Accepted on 2026-06-24 after human review.

The accepted boundary is architecture-only. Acceptance does not authorize
schema, service, route, storage, migration, ADR-0014, external memory framework
integration, or historical backfill work.

## Alternatives Considered

### Alternative 1: Make governed_claim the universal AI Radar claim atom

Rejected. This would imply migration pressure on existing Signal, verification,
Project Takeaway, and Reflection objects. It would collapse too much of the
system into one ontology.

### Alternative 2: Add audit_record as a fourth live-state form

Rejected. Audit/provenance is already a separate plane in AI Radar's
architecture. Adding it as a fourth form would mix live mutable state with
append-only history.

### Alternative 3: Treat provenance as trustworthiness

Rejected. Traceability and verification support are separate axes. Knowing
where material came from does not prove the claim.

### Alternative 4: Store external-world claims directly in memory

Rejected. External claims belong in Signal/evidence/verification paths. AI
Discussion memory may store discussion judgments about external subjects, but
not external evidence itself.

### Alternative 5: Let external memory frameworks define the ontology

Rejected. External mechanisms may be studied later, but they must deform to AI
Radar boundaries rather than importing their source worldview.

## Implementation Plan

No implementation is approved by this ADR.

Future work, if separately approved:

1. Perform repo-signature alignment for the pending semantic slots.
2. Draft a minimal schema proposal for governed claims.
3. Define append-only audit record requirements for governed-claim mutation.
4. Define a read-only importer or capture path for AI Discussion collaboration
   records.
5. Design explicit promotion and re-reference actions.
6. Only after ADR-0013 is accepted, draft ADR-0014 for external memory
   mechanism ingestion.

## Future ADR-0014 Must Respect

ADR-0014 may define an ingestion lifecycle for borrowed mechanisms, but
ADR-0013 does not approve that lifecycle.

Future candidate lifecycle may resemble:

```text
candidate -> provisional_no_influence -> absorbed
```

Any `absorbed` mechanism may influence governed claims only through declared
operator/read paths and must preserve audit, support-boundary, and action-gate
rules.

## INVARIANTS.md Update

On acceptance, add the following section to `docs/adr/INVARIANTS.md`:

```text
## AI Discussion Memory Boundary

Governing ADR:

- ADR-0013: AI Discussion Governed Claim Boundary

Rules:

1. governed_claim is scoped to AI Discussion memory and does not replace claim_verification or verified_insight.
2. Discussion judgments may be about external subjects, but they are not external evidence.
3. External-source subjects are distinct from direct external/import origins; direct external/import origins are out of scope unless separately admitted.
4. Traceability, verification support, temporal validity, and salience are orthogonal.
5. Salience must not determine action eligibility or bypass blocked_downstream_actions.
6. Any write that changes governed_claim attributes or edges must leave an audit trace.
7. governed_claim verification references are as-of snapshots; source-spine updates do not automatically update memory references.
8. Reflection, Workspace, Manual Upload, Signals, and historical records are out of scope unless separately admitted.
```

This section was added to `INVARIANTS.md` on 2026-06-24 and clarified on
2026-06-25 to distinguish external-source subjects from external/import
origins.

## References

- ADR-0010: External Insight Intake Requires Author-Side Admission Gate
- ADR-0011: Evidence Pack Source Excerpt Policy
- ADR-0012: Signal Claim Review Feedback Capture
- docs/adr/INVARIANTS.md
- backend/app/services/evidence_pack_service.py
- backend/app/services/claim_verification_service.py
- backend/app/services/verified_insight_service.py
- backend/app/services/low_evidence_gate_service.py
