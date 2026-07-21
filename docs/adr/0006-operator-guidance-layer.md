---
adr: 0006
title: Operator Guidance Layer
status: Proposed
created: 2026-05-19
layer: L1-engineering-solution
related:
  - L2: AGENTS.md
  - L2: DEVELOPMENT_PLAN.md
  - L2: docs/operator-guidance/state-action-map.yaml
  - L1: docs/adr/0002-hypothesis-monitoring-boundary.md
tags: [operator-guidance, state-guidance, verification-boundary, admin]
---

# ADR-0006: Operator Guidance Layer

## ADR Gate

Create this ADR only if all are yes:

- [x] Hard to reverse: once AI Radar starts surfacing next-action guidance in
  operator or user workflows, the guidance source, citation rules, and mutation
  boundaries become product expectations.
- [x] Context would be lost: future readers would ask why AI Radar prefers
  static state guidance before an LLM assistant, and why cited LLM fallback is
  treated as traceable but not verified.
- [x] Real tradeoff: plausible options include static mapping only, pure LLM
  assistant, relying on documentation, or a hybrid static-first guidance layer.

## Context

AI Radar's product loop now contains enough state semantics that even the
current sole operator can lose time at state transitions. Examples include:

- after a Signal or manual-derived item is completed, the next legitimate step
  may involve Signal Detail, Workspace completion, Project Takeaway review,
  Knowledge visibility, or Trajectory memory
- when claim or verification metadata blocks downstream action, the operator
  must remember which gate or review path explains the block
- when `blocked_downstream_actions` is present, the ordinary path must not
  silently bypass that gate, but the UI does not always explain the next safe
  move

AI Radar already has hard intelligence-quality boundaries in `AGENTS.md` and a
current verification architecture described in `DEVELOPMENT_PLAN.md`. The
system distinguishes evidence, verification metadata, cognitive context,
manual entries, Project Takeaway eligibility, low-risk Action eligibility, and
explicit override paths.

Those boundaries are also relevant to operator guidance. A guidance surface can
look authoritative even when it is only an LLM explanation. If AI Radar exposes
operator guidance, the system must not let uncited LLM synthesis become primary
guidance, evidence, `verified_insight`, or a state mutation path.

The first consumer is the admin/operator surface used by Andy. Future ordinary
user-facing guidance may be valuable, but it needs separate review for wording,
permissions, hidden state, and whether internal ADR or override language should
be visible to non-admin users.

This ADR corrects an earlier draft assumption: ADR-0004 in this repository is
`AGENTS.md Constitution and Skill Registry`; it is not a verification-aware
synthesis ADR. Verification-related grounding for this decision comes from
`AGENTS.md`, `DEVELOPMENT_PLAN.md`, ADR-0002 where relevant, and the current
verification / Project Takeaway service boundaries.

## Decision

Adopt a static-first operator guidance layer with traceable LLM fallback.

1. AI Radar should maintain a state-to-next-action mapping for admin/operator
   guidance. When a mapping exists for the current state, the UI should surface
   the static mapping directly with no LLM in the path.

2. During the observation phase, the mapping lives as a manually maintained
   docs asset:

   ```text
   docs/operator-guidance/state-action-map.yaml
   ```

   This Phase 2 location is intentionally not the final product runtime
   location. It allows the project to learn which state transitions actually
   need guidance before committing to backend schema, API, or UI coupling.

3. LLM fallback is permitted only when the static mapping does not answer the
   operator's question. Fallback responses must follow these constraints:

   - **Traceability invariant**: every fallback response must cite at least one
     specific ADR, agent skill, source document, or code/service boundary by
     identifier.
   - **No verification inflation**: a cited fallback is not verified guidance
     merely because it cites a document. Citation creates traceability, not
     truth.
   - **No state mutation invariant**: fallback is read-only. It may explain,
     point to sources, or draft a possible next step for human review. It must
     not trigger state transitions, write to the Knowledge Engine, modify
     claims, create Project Takeaway candidates, bypass gates, or alter evidence
     / insight records.
   - **Synthesis disclosure invariant**: fallback responses are labeled as
     LLM-generated and must not be persisted as `verified_insight`, factual
     evidence, claim support, or calibration truth.

4. The mapping is operator-authored / operator-approved guidance. It is not
   "verified by construction." It is authoritative as approved operating
   guidance for the admin/operator surface, while still needing review when
   product behavior, state names, or downstream gates change.

5. The mapping should be versioned and auditable. It must not be silently
   overwritten. It does not need to be append-only; states may be deprecated,
   renamed, split, or superseded as long as the change is explicit.

6. Future ordinary user-facing guidance is deferred. User-facing guidance may
   reuse concepts from the operator map, but it must not automatically expose
   admin-only state, internal ADR references, override semantics, or raw
   verification internals without a separate review.

7. Final layer-of-residence is deferred to a later decision. Candidate future
   homes include `backend/app/operator_guidance/`, a Knowledge Engine sublayer,
   or a dedicated meta/operator layer. That later decision should be based on
   real mapping entries gathered during manual use.

## Owns

- The decision to prefer static state guidance before LLM fallback.
- The rule that LLM fallback is traceable synthesis, not verified guidance.
- The read-only, no-state-mutation boundary for fallback.
- The Phase 2 manual mapping location:
  `docs/operator-guidance/state-action-map.yaml`.
- The current consumer boundary: admin/operator first, ordinary user-facing
  guidance deferred.
- The rule that the mapping is versioned and auditable, not silently
  overwritten.

## Does Not Own

- The final backend/runtime storage location for guidance mappings.
- The UI implementation of the guidance surface.
- The LLM fallback model choice.
- A full canonical state registry for every AI Radar object.
- A completeness gate for new states.
- Any change to Project Takeaway, low-risk Action, verification, override, or
  `blocked_downstream_actions` behavior.
- Any exposure of operator guidance to ordinary users.

## Consequences

Static-first guidance reduces repeated operator recalibration without letting an
LLM invent primary operating procedure at the moment of need.

The traceability requirement makes fallback answers auditable, while avoiding
the false claim that citation equals verification. A fallback can still cite a
weakly relevant document, so cited fallback must remain secondary to static
guidance and human judgment.

The docs-first Phase 2 location keeps the experiment cheap. It avoids locking
in backend schema before the project knows which state transitions actually
need guidance. The tradeoff is that docs-based mapping can drift from runtime
state unless it is reviewed deliberately.

Making the mapping versioned and auditable creates maintenance work. Every
meaningful state or next-action change may require a mapping review. This cost
is acceptable for the admin/operator phase, but should be re-evaluated before
ordinary users depend on the guidance surface.

Deferring ordinary user-facing exposure prevents admin-only language from
leaking into product UI. It also means a later user-facing guidance feature must
make its own wording and permission decisions.

## Alternatives Considered

### Alternative 1: Pure static mapping

Rejected as the whole solution. Static mapping is the source of truth for known
states, but it cannot reasonably answer every causal or exploratory question,
such as why a specific item was blocked or which document explains a rare edge
case.

### Alternative 2: Pure LLM assistant

Rejected. A pure LLM assistant would make every guidance answer a fresh
synthesis. That is too risky in AI Radar's own domain, where plausible but
nonexistent procedures are a known failure mode and where downstream action
eligibility is controlled by hard gates.

### Alternative 3: Rely on existing documentation

Rejected. Existing docs remain necessary, but guidance that requires the
operator to remember which doc to open is missing at the moment of state
transition. The point of the guidance layer is to surface the relevant next
action near the state where it matters.

### Alternative 4: Put the mapping directly under backend runtime now

Rejected for Phase 2. Backend storage will likely be appropriate if UI/API
surfaces depend on the mapping, but doing that before a manual observation
period would prematurely freeze schema and ownership.

## Implementation Plan

1. Keep this ADR `Proposed` while the guidance shape is tested manually.
2. Create `docs/operator-guidance/state-action-map.yaml` as a hand-maintained
   admin/operator mapping file.
3. Add only a small initial set of mapping entries from real friction, not a
   speculative full state inventory.
4. Observe manual use before adding UI, LLM fallback, or completeness gates.
5. If the mapping proves useful, draft a later decision for final
   layer-of-residence and runtime ownership.
6. Implement static UI guidance before adding LLM fallback.
7. Add LLM fallback only after citation/traceability enforcement and no-mutation
   boundaries are designed.
8. Review ordinary user-facing exposure separately.

## References

- [AGENTS.md](../../AGENTS.md)
- [DEVELOPMENT_PLAN.md](../../DEVELOPMENT_PLAN.md)
- [ADR-0002: Hypothesis Monitoring Boundary](./0002-hypothesis-monitoring-boundary.md)
- Planned Phase 2 mapping: `docs/operator-guidance/state-action-map.yaml`
- Related services:
  - `backend/app/services/verified_insight_service.py`
  - `backend/app/services/low_evidence_gate_service.py`
  - `backend/app/services/claim_verification_service.py`
  - `backend/app/services/project_takeaway_constants.py`
