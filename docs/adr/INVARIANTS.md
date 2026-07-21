---
title: AI Radar Architecture Invariants
last_updated: 2026-06-25
layer: L1-architecture-index
status: living-index
related:
  - docs/adr/0002-hypothesis-monitoring-boundary.md
  - docs/adr/0006-operator-guidance-layer.md
  - docs/adr/0008-signal-lifecycle-event-spine.md
  - docs/adr/0009-model-provenance-schema.md
  - docs/adr/0013-ai-discussion-governed-claim-boundary.md
tags: [adr-index, invariants, verification, project-takeaway, provenance, memory-layer]
---

# AI Radar Architecture Invariants

## Purpose

This file is a mutable index of cross-ADR invariants.

It is not an ADR and does not supersede any ADR. It exists because several AI
Radar safety boundaries are distributed across multiple ADRs. When a slice
touches verification, Project Takeaway gates, Reflection, operator guidance,
model provenance, or lifecycle enforcement, this file is the reading map before
implementation.

## How To Use

Read this file before changing any path that:

- creates or mutates verification metadata
- creates Project Takeaway candidates
- confirms, rejects, watches, actions, or overrides Project Takeaway records
- interprets Reflection as evidence or context
- creates or mutates AI Discussion governed claims
- turns rejected or dismissed review history into future context
- surfaces operator guidance as next-action advice
- records model provenance or model-attribution analytics
- designs Signal Lifecycle Event Spine behavior

Then open the referenced ADRs for the governing decision text.

## Verification Boundary

Verification is a product and data invariant, not just UI wording.

Governing ADRs:

- ADR-0002: Hypothesis watches remain proposed until explicitly activated.
- ADR-0006: Operator guidance is traceable guidance, not evidence or
  verification.
- ADR-0008: Lifecycle enforcement must preserve verification gates and make
  bypasses structurally harder.
- ADR-0009: Model provenance is judgment provenance, not source evidence.

Rules:

1. External claims need evidence and verification metadata before they can
   support downstream action.
2. Proposed hypotheses, strategic analysis, operator guidance, Reflection, and
   model provenance do not become verified evidence by being well explained.
3. Missing or empty verification metadata must not be labeled as
   `verified_insight`.
4. Lifecycle or trajectory UI may explain a path, but it must not imply
   authoritative verification history when the underlying data is inferred,
   legacy, or missing.

## Project Takeaway Gates

Project Takeaway review is governed by verification metadata and explicit human
review outcomes.

Governing ADRs:

- ADR-0006 for guidance boundaries around next actions.
- ADR-0008 for lifecycle enforcement and bypass prevention.
- ADR-0009 for model provenance as audit metadata only.

Rules:

1. Ordinary Confirm and Action paths must not bypass
   `blocked_downstream_actions`.
2. Low-risk Action eligibility must come from verification metadata and action
   gate logic, not from UI confidence, operator guidance, model provenance, or
   Reflection linkage.
3. Override paths must remain separate, explicit, auditable, and exceptional.
4. Override review requires a reviewer note and expected outcome.
5. `action_completed` is an Action lifecycle state, not a Project Takeaway
   review outcome.
6. Manual or unverified entries must be explicitly marked as unverified until
   they pass a designed verification or review path.
7. `knowledge_convergence_review_candidate` is review context. It may prepare
   Project Takeaway review, but it must block low-risk Action by default until
   further review or explicit override.
8. Local test, fixture, demo, or legacy records must not be treated as real
   intelligence-flow evidence without explicit classification.

## Rejected Learning Boundary

Rejected or dismissed review history can be useful caution context. It is not
source evidence.

Rules:

1. Rejected learning context must come from explicit review artifacts such as
   Project ReviewRecords, not from Reflection as factual evidence.
2. Rejected learning output is bounded caution context for future generation or
   diagnostics.
3. Rejected learning output must not count as claim support, external evidence,
   or verification metadata.
4. Generator integration, when added, must label the buffer as prior review
   feedback and keep it out of evidence semantics.
5. Confirmed, Watch, Action, and Action-completed lifecycle states must not be
   misclassified as rejected learning.

## Reflection Boundary

Reflection is cognitive context.

Governing ADRs:

- ADR-0002 for the boundary between strategic context and active monitoring.
- ADR-0008 for explicit exclusion from automatic lifecycle linkage.
- ADR-0009 for deferred reflection polish pair provenance.

Rules:

1. Reflection content is not factual evidence for external claims by default.
2. Reflection browsing, sync, and polish output do not need factual
   verification gates while they remain cognitive context.
3. Reflection enters the verification spine only when a human or explicit
   product path promotes it into a Signal, Knowledge, or Project review object.
4. Reflection linkage must not bypass Project Takeaway gates.
5. Any future Reflection-to-evidence conversion path needs its own explicit
   design and validation.

## AI Discussion Memory Boundary

AI Discussion memory preserves governed discussion judgments. It does not create
a new universal claim atom for AI Radar.

Governing ADR:

- ADR-0013: AI Discussion Governed Claim Boundary.

Rules:

1. `governed_claim` is scoped to AI Discussion memory and does not replace
   `claim_verification`, `verified_insight`, `evidence_pack`, or
   `low_evidence_gate`.
2. Discussion judgments may be about external subjects, but they are not
   external evidence.
3. External-source subjects are distinct from direct external/import origins;
   direct external/import origins are out of scope unless separately admitted.
4. Traceability, verification support, temporal validity, and salience are
   orthogonal.
5. Salience must not determine action eligibility or bypass
   `blocked_downstream_actions`.
6. Any write that changes `governed_claim` attributes or edges must leave an
   audit trace.
7. `governed_claim` verification references are as-of snapshots; source-spine
   updates do not automatically update memory references.
8. Reflection, Workspace, Manual Upload, Signals, and historical records are out
   of scope unless separately admitted.

## Operator Guidance Boundary

Operator guidance helps the operator choose safe next steps. It does not mutate
state or prove claims.

Governing ADR:

- ADR-0006.

Rules:

1. Static guidance is preferred before LLM fallback.
2. LLM fallback is read-only and must be traceable to a specific ADR, skill,
   source document, or code/service boundary.
3. Citation creates traceability, not verification.
4. Guidance must not trigger state transitions, create candidates, modify
   claims, or bypass gates.
5. Admin/operator guidance is not automatically safe for ordinary user-facing
   exposure.

## Model Provenance Boundary

Model provenance records which model path produced a judgment. It does not make
the judgment true.

Governing ADR:

- ADR-0009.

Rules:

1. `produced_by_model` is judgment provenance, not source evidence.
2. `produced_by_model` does not raise trust by itself.
3. Historical records are not backfilled. Missing provenance reads as legacy/v0
   at read time.
4. Legacy/v0 is a coverage state, not a negative quality label.
5. Legacy/v0 or malformed provenance is excluded from attribution analytics but
   counted in coverage.
6. New provenance fields need either an existing consumer or an approved next
   slice consumer. Do not add fields only because they may be useful someday.

## Signal Lifecycle Boundary

Lifecycle events are intended to make important state transitions auditable and
harder to bypass.

Governing ADR:

- ADR-0008.

Rules:

1. Stage B must start with schema design and soft event recording, not broad
   write-path rewrites.
2. Legacy, inferred, partial, and authoritative trajectory data must be labeled
   honestly.
3. Hard enforcement should be enabled only after the selected path has soft
   recording, tests, clear rollback, and preserved verification gates.
4. Lifecycle events should support both per-signal trajectory and future
   source-level aggregation.
5. Reflection is excluded from automatic lifecycle enforcement unless promoted
   into a review object.

## Required Reading By Slice Type

| Slice touches | Read first |
|---|---|
| Hypothesis watches or strategic monitoring | ADR-0002 |
| Operator guidance, next-action advice, fallback guidance | ADR-0006 |
| Signal lifecycle, trajectory, status mutation, hard enforcement | ADR-0008 |
| Model provenance, attribution analytics, model labels | ADR-0009 |
| Project Takeaway candidate creation or review gates | ADR-0006, ADR-0008, ADR-0009 |
| Reflection as evidence, context, or review input | ADR-0002, ADR-0008, ADR-0009 |
| AI Discussion governed claims or memory-layer claim mutation | ADR-0013 |
| Rejected learning or caution-context feedback | This invariant index, then future owning ADR if the buffer becomes generator input |

## Maintenance Rule

Update this file when:

- a new ADR owns a boundary that affects verification, gates, Reflection,
  provenance, operator guidance, or lifecycle enforcement
- an accepted implementation changes which ADR governs a cross-cutting
  invariant
- a review or incident shows that agents are missing a boundary because it is
  scattered across ADRs

Do not use this file to create new policy without an owning ADR or an explicitly
approved implementation note.
