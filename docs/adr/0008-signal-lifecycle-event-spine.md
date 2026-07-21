---
adr: 0008
title: Signal Lifecycle Event Spine
status: Proposed
created: 2026-05-21
layer: L1-engineering-solution
related:
  - L2: AGENTS.md
  - L2: CURRENT_DEVELOPMENT_STATUS.md
  - L2: docs/cognitive-log/2026-05-21-signal-lifecycle-event-spine.md
  - L1: docs/adr/0002-hypothesis-monitoring-boundary.md
  - L1: docs/adr/0006-operator-guidance-layer.md
tags: [signal-lifecycle, event-spine, verification-boundary, audit, trajectory-view]
---

# ADR-0008: Signal Lifecycle Event Spine

## ADR Gate

Create this ADR only if all are yes:

- [x] Hard to reverse: once AI Radar exposes signal trajectory as an audit
  surface or routes state mutation through a lifecycle service, the event
  schema, transition names, and enforcement boundary become product
  expectations.
- [x] Context would be lost: future readers would ask why AI Radar moved from
  status fields and inferred UI paths toward lifecycle events, and why UI probe
  work precedes lifecycle schema design.
- [x] Real tradeoff: plausible alternatives include keeping the current
  status-field model, directly designing a full event schema now, or treating
  the signal trajectory UI as a frontend-only visualization.

## Absorption Status

This ADR follows a `grill-before-absorb` review with outcome `partial`.

The project owns the product need: each signal should have a readable path, and
each important decision should expose its support. The final lifecycle event
metadata schema is not fully owned yet and must be derived from a UI probe and
gap report before it is treated as durable.

## Context

AI Radar transforms signals into structured intelligence through Signal,
Insight, Reflection, Knowledge Engine, and Project Engine layers.

The system already has a verification spine made from services such as
evidence pack creation, claim verification, verified insight derivation, and
low-evidence gating. However, signal lifecycle changes are still primarily
represented by stored fields, inferred status, and service-specific writes.

Known bypass patterns show the weakness of a status-only model:

- a Project Takeaway candidate path can accept missing or empty verification
  metadata and still present itself as eligible downstream intelligence
- ordinary project improvement confirmation can bypass
  `blocked_downstream_actions` if it does not enter through an explicit
  override path
- legacy completion paths can write project improvement state without passing
  through the verification services that should govern eligibility

These issues are not only UI problems. They indicate that verification is still
partly an after-the-fact classification layer, not a structural invariant that
all important transitions must pass through.

The Signal Decision Map work introduced two useful UI concepts:

1. **Trajectory View**: a compact vertical replay of what happened to one
   signal, with decision support available on demand.
2. **Schema Map**: a full branch map of possible signal paths, useful for
   understanding the system but too noisy as the default audit view.

The UI revealed that AI Radar needs an explicit lifecycle model, but the exact
schema should not be invented ahead of real examples.

## Decision

Adopt a staged direction toward a signal lifecycle event spine.

### Stage A: UI Probe And Schema Discovery

Before implementing a durable lifecycle event schema, AI Radar should use the
Trajectory View as a schema probe.

Stage A should define a UI consumption contract for a signal trajectory, select
two to three real historical signals, and implement a temporary probe adapter
that maps current stored fields into that contract.

The probe adapter should produce a gap report with at least these categories:

1. fields that current storage can render directly
2. fields that existing services calculate but do not persist
3. fields that require architectural changes or a lifecycle event spine

The adapter is not the final architecture. It should be clearly named as a
probe or legacy adapter and should not become the long-term source of truth.

### Stage B: Lifecycle Event Spine

After Stage A produces a gap report, AI Radar should design a
`SignalLifecycleEvent` model and a lifecycle service.

The intended long-term direction is a single lifecycle transition entry point,
for example:

```text
signal_lifecycle_service.record_transition(...)
```

That entry point should eventually enforce:

- legal state transitions
- required metadata for verification-dependent states
- explicit override semantics
- auditability of project promotion and review paths

Stage B should begin with soft enforcement before hard enforcement. In soft
enforcement, new write paths record lifecycle events and legacy paths may be
marked as inferred or legacy. In hard enforcement, key mutation paths reject
illegal transitions once they have been migrated.

Lifecycle events serve two distinct consumers and value lines:

1. **Per-signal trajectory**: consumed by Trajectory View UI to explain how one
   signal moved through the system. This is the verification enforcement value
   line.
2. **Source-level aggregation**: consumed by an operator/admin analytics,
   reporting, or query surface to expose source quality and utilization metrics
   derived from accumulated events. This is the operational feedback value line.

Both consumers share the same event stream but query it at different
granularities. Stage A may stay focused on the per-signal trajectory probe, but
Stage B schema decisions must consider both consumers before the event model is
treated as durable.

#### Stage B Schema Design Principles

Beyond the UI gap report inputs from Stage A, the event schema must satisfy
these direction constraints to support source-level analysis:

- canonical source identity must be available as a first-class indexed field on
  every event, not embedded only in metadata
- key metadata fields such as `verification_status`, `evidence_level`,
  `allowed_downstream_actions`, `blocked_downstream_actions`, `rule_id`, and
  `evaluation_summary` should use stable structured keys and queryable
  extraction paths, not free-text reasons only
- `allowed_downstream_actions` and `blocked_downstream_actions` are
  verification policy gates, not the full list of UI paths that were possible
  but not taken; Trajectory View may use these gates to label downstream paths,
  but it must not treat them as a complete transition graph
- when a transition involves evaluation of alternatives, such as checking
  multiple claims and producing a final verification state, the structured
  evaluation summary should be retained without storing raw prompts, full
  external payloads, or other sensitive material
- the schema should support downstream materialized views or equivalent
  aggregation outputs without requiring immediate schema migration

## Owns

- The decision to use UI probe work before final lifecycle event schema design.
- The distinction between Trajectory View and Schema Map:
  - Trajectory View is the default audit view for a single signal.
  - Schema Map is a system-understanding view for possible paths.
- The staged approach:
  - Stage A: probe adapter and gap report
  - Stage B: lifecycle event spine and transition enforcement
- The principle that lifecycle metadata should be derived from real UI and
  audit needs, not speculative completeness.
- The principle that Stage B schema must serve both per-signal trajectory and
  source-level aggregation consumers.
- The intended long-term direction that important signal state mutations should
  enter through a lifecycle transition service.
- The rule that legacy or inferred trajectory data must be labeled as such in
  the UI and should not be presented as authoritative lifecycle history.

## Does Not Own

- The final `SignalLifecycleEvent` metadata schema.
- The complete legal transition table.
- The final database table, storage engine, or migration format.
- A full backfill of historical signals.
- Automated backlog processing or automated historical backfill for source
  scoring.
- The complete judgment versioning UI.
- Automatic Reflection-layer linkage to lifecycle events.
- The final source scoring formula, source weighting policy, source removal
  policy, or new-source expansion workflow.
- Immediate deletion or refactor of all legacy write paths.
- Any change to deployment, CI, IAM, S3 storage paths, or `.github/workflows/`.

## Consequences

The staged approach reduces the risk of over-designing lifecycle metadata. It
lets the UI expose real schema gaps before the backend event model is frozen.

Trajectory View becomes a useful audit surface, but it also creates pressure to
distinguish authoritative lifecycle events from inferred legacy summaries. The
UI must be honest when data is missing, inferred, partial, or legacy-derived.

Soft enforcement creates an intermediate period where some paths record
lifecycle events and some paths remain legacy. That period must be visible in
the gap report and not mistaken for completion.

Hard enforcement, when reached, should make verification bypasses physically
harder to introduce. This also means state mutation code will become more
centralized and may require more explicit metadata at call sites.

The transition from status fields to lifecycle events will add maintenance
cost. Every new mutation path must decide whether it is a lifecycle transition,
what actor performed it, what upstream fields justified it, and whether it
needs override semantics.

Lifecycle events also accumulate into an operational dataset that can support
decisions about the source ecosystem, such as which sources to keep,
deprioritize, or expand. This feedback channel requires both the event spine
itself and a minimal aggregation surface. The dataset is unlikely to produce
useful source-level insight until lifecycle events have accumulated across the
historical signal backlog, processed by the user through the forward path rather
than automated backfill. The expected timeline from Stage B completion to first
useful source-level insight is determined by user backlog processing pace, not
by system performance alone.

## Alternatives Considered

### Alternative 1: Keep the current status-field model

Rejected as the long-term direction. Status fields can show where a signal is,
but they do not reliably explain how it got there, what decision support was
used, or whether a path bypassed verification.

### Alternative 2: Design the full event schema now

Rejected for the initial phase. The project does not yet know which lifecycle
metadata fields the audit UI and invariant checks actually need. Designing the
schema first would likely produce speculative fields and miss real gaps.

### Alternative 3: Treat the trajectory UI as frontend-only

Rejected. A frontend-only adapter can be useful as a probe, but it cannot make
verification structurally harder to bypass. The long-term system needs backend
events and transition enforcement.

### Alternative 4: Backfill all historical signals immediately

Rejected for Stage B. Full backfill would add complexity before the event
schema is proven. Historical signals should initially display as unavailable,
partial, or inferred rather than pretending to have authoritative lifecycle
events.

## Implementation Plan

1. Keep this ADR `Proposed` while Stage A runs.
2. Define a compact UI consumption contract for Trajectory View.
3. Select two to three real signals:
   - one ideal path through verification and workspace completion
   - one known or suspected legacy/bypass path
   - one paused or partial path
4. Implement a clearly named probe adapter that maps current fields into the
   UI contract. Prefer an admin-only backend service or endpoint over complex
   frontend inference.
5. Produce a gap report with direct fields, non-persisted service outputs, and
   true architecture gaps.
6. Use the gap report to draft the first `SignalLifecycleEvent` schema.
7. Implement lifecycle event recording with soft enforcement first.
8. Migrate key write paths toward the lifecycle service.
9. Only after migration, turn selected illegal transitions into hard rejections.
10. Revisit this ADR after Stage A and decide whether to mark it Accepted,
    revise it, or split Stage B into a more specific ADR.
11. Stage B must include at least one minimal aggregation surface, in whichever
    form is cheapest to validate, that exposes source-level metrics derived
    from lifecycle events. Acceptable forms include a CLI command, scheduled
    markdown report, or admin query endpoint. The minimum metric set is
    per-source promotion rate, rejection rate, and verification pass rate.
    Without this surface, Stage B cannot prove the event schema supports the
    operational feedback consumer.

## Open Questions

- Which exact state names belong in the first legal transition table?
- Should verification completion be a lifecycle state, or should
  `verification_status` remain metadata attached to a broader transition?
- Which write paths are high enough risk to migrate first?
- What mechanism should produce the canonical `source_id`, and how should it
  handle aliases, renamed sources, source URL families, and manual uploads?
- How should Trajectory View reference verification policy gates without
  implying that `allowed_downstream_actions` is a complete list of possible
  lifecycle paths?
- Should probe output live under `/signals/{signal_id}/lifecycle-probe`, a
  dedicated admin endpoint, or an internal service consumed by Signal Detail?
- Which historical signals are best for the first gap report?

## References

- [AGENTS.md](../../AGENTS.md)
- [ADR-0002: Hypothesis Monitoring Boundary](./0002-hypothesis-monitoring-boundary.md)
- [ADR-0006: Operator Guidance Layer](./0006-operator-guidance-layer.md)
- [Cognitive Log: Signal Lifecycle Event Spine](../cognitive-log/2026-05-21-signal-lifecycle-event-spine.md)
- Related services and routes to inspect during Stage A:
  - `backend/app/services/verified_insight_service.py`
  - `backend/app/services/claim_verification_service.py`
  - `backend/app/services/evidence_pack_service.py`
  - `backend/app/services/low_evidence_gate_service.py`
  - `backend/app/routes/projects.py`
  - `backend/app/routes/signals.py`
