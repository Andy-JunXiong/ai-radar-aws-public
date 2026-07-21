---
title: ADR-0008 Stage B Readiness Checklist
date: 2026-05-22
layer: L2-feature-planning
status: readiness-draft
related:
  - docs/adr/0008-signal-lifecycle-event-spine.md
  - docs/features/signal-lifecycle/2026-05-22-stage-a-gap-report.md
  - docs/features/signal-lifecycle/2026-05-22-governance-preflight-audit.md
tags: [signal-lifecycle, stage-b, verification-boundary, governance]
---

# ADR-0008 Stage B Readiness Checklist

## Goal

Prepare ADR-0008 Stage B without jumping into final
`SignalLifecycleEvent` implementation.

This slice defines:

- current legacy or partial write paths
- intended fate for each path
- hard-enforcement readiness criteria
- Reflection-layer exclusion
- invariant-index draft content for a future `docs/adr/INVARIANTS.md`

## Non-Goals

- Do not implement `SignalLifecycleEvent`.
- Do not add `record_transition()`.
- Do not create a legal transition table yet.
- Do not refactor write paths.
- Do not backfill historical signals.
- Do not create `docs/adr/INVARIANTS.md` without explicit core-file approval.
- Do not weaken Project Takeaway gates or override requirements.
- Do not treat Reflection content as factual evidence.

## Current Path Inventory

This is a readiness inventory, not a full static analysis.

| Path | Current behavior | Stage B fate |
|---|---|---|
| `/signals/update-status` for automatic signals | Mutates stored signal status through `s3_reader` and returns a decision-trace-style event label. | Migrate to soft lifecycle event recording for status transitions. |
| `/signals/update-status` for manual sessions | Mutates manual session status and appends current decision trace metadata. | Migrate first or second; keep legacy/manual marker visible. |
| `/signals/generate-insight` | Writes generated insight, verification metadata, evidence pack, and model provenance, but not authoritative lifecycle transition history. | Migrate to soft event recording for insight generation and verification completion. |
| `/signals/complete` | Saves workspace reflection, writes project improvements, and marks signal or manual session completed. | High-priority migration candidate because it joins workspace completion and project fan-out. |
| `add_signal_to_project_improvements()` | Creates Project Takeaway candidate records with verification metadata and manual-entry safeguards. | Record project fan-out lifecycle event or derived signal event; preserve existing verification gates. |
| Project Takeaway confirm / reject / dismiss / watch / action routes | Mutate project candidate state and append ReviewRecord / CalibrationEvent metadata. | Keep as project-side review records initially; expose derived lifecycle attachment before migrating. |
| Project Takeaway override-confirm / override-action routes | Dedicated explicit override paths with note and expected outcome. | Preserve as exceptional override transitions; never merge into ordinary confirm/action flow. |
| Project action completion / reopen | Mutates project item lifecycle after review decision. | Treat as project-side lifecycle first, not a blocker for signal lifecycle hard enforcement. |
| Project fit refresh / review generation / document generation / GitHub submission | Downstream project operations, some with additional external repo constraints. | Keep outside initial signal lifecycle enforcement; consider later project lifecycle events. |
| Reflection browsing and reflection sync | Cognitive context, not factual evidence for external claims. | Explicitly excluded from verification lifecycle enforcement unless a human promotes content into Knowledge or Project review. |

## Fate Categories

Use these categories when expanding the inventory:

- `migrate`: path should call the lifecycle service once Stage B exists
- `derive`: path should remain owned by another record family but be attached
  to signal trajectory through references
- `exclude`: path should stay outside lifecycle enforcement
- `permanent-legacy`: path remains legacy by design and must show why
- `deprecate`: path should be removed after replacement is stable

No path should remain in `unknown` after Stage B schema design.

## Hard-Enforcement Readiness Criteria

Do not turn on hard enforcement until all of these are true for the selected
path:

1. The event schema is defined and covered by focused tests.
2. Soft event recording exists for the path.
3. Existing UI labels legacy, inferred, and authoritative trajectory states
   honestly.
4. The path has tests proving required verification metadata is present when
   the transition depends on verification.
5. Ordinary Confirm and Action paths still respect `blocked_downstream_actions`.
6. Override paths remain separate and auditable.
7. Reflection content remains outside factual verification unless explicitly
   promoted into a review object.
8. Rollback is clear: disabling hard enforcement should not corrupt stored
   signal or project records.

## Reflection Exclusion

Reflection is cognitive context.

Stage B must not force ordinary Reflection browsing, sync, or polish output
through factual verification gates. Reflection only enters the verification
spine when a human or explicit product path promotes it into a Knowledge,
Signal, or Project review object.

Allowed:

- display Reflection as cognitive context
- link Reflection to related signals as non-evidence context
- create an explicit future promotion path with verification requirements

Not allowed:

- use Reflection text as factual evidence for external claims by default
- treat Reflection polish output as a verified insight
- use Reflection linkage to bypass Project Takeaway gates

## Draft Invariant Index Content

These are the minimum sections a future `docs/adr/INVARIANTS.md` should carry
once the core-file approval gate is satisfied:

- Verification boundary:
  - ADR-0002: hypothesis watches remain proposed until activated
  - ADR-0006: operator guidance is not evidence or verification
  - ADR-0008: lifecycle enforcement must preserve verification gates
  - ADR-0009: model provenance is judgment provenance, not source evidence
- Project Takeaway gates:
  - ordinary Confirm / Action cannot bypass `blocked_downstream_actions`
  - override paths require explicit note and expected outcome
- Reflection boundary:
  - Reflection is cognitive context until explicitly promoted
- Provenance boundary:
  - `produced_by_model` does not raise trust by itself
  - legacy/v0 provenance is a coverage state, not a quality failure

## Suggested Stage B Slice Order

1. Done on 2026-05-22: create `docs/adr/INVARIANTS.md` after explicit
   core-file approval.
2. Done on 2026-05-22: draft a minimal event schema and lifecycle service
   interface.
3. Done locally on 2026-05-22: add soft event recording to
   `/signals/generate-insight`.
4. Next candidate: add soft event recording to `/signals/complete`.
5. Attach project review/calibration records as derived trajectory events.
6. Add UI labels for authoritative / inferred / legacy lifecycle data.
7. Only then select one path for hard enforcement.

## Definition Of Done

This readiness checklist is complete when:

- governance preflight confirms artifact usage is non-zero
- current path inventory has initial fate assignments
- hard-enforcement criteria are explicit
- Reflection exclusion is explicit
- future invariant-index content is drafted
- no runtime code or schema has been changed

## Current Decision

Stage B may proceed to a design slice, but it should not begin with broad
write-path rewrites.

The safest next implementation after this document is an invariant-index doc
or a minimal event-schema design doc, not code.
