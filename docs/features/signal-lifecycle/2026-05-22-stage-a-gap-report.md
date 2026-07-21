---
title: ADR-0008 Stage A Signal Lifecycle Gap Report
date: 2026-05-22
adr: docs/adr/0008-signal-lifecycle-event-spine.md
stage: Stage A UI Probe And Schema Discovery
status: completed-probe-report
---

# ADR-0008 Stage A Signal Lifecycle Gap Report

## Purpose

This report closes ADR-0008 Stage A.

Stage A used the Signal Detail `Trajectory View` and the backend probe adapter
to inspect real signal paths before designing a durable lifecycle event schema.
The probe is intentionally not authoritative.

Probe adapter:

```text
signal_lifecycle_probe_legacy_adapter_v0
```

Contract:

```text
trajectory_view_contract_v0
```

All sample outputs reported `authoritative=false`.

## Sample Set

The Stage A sample set covered three real signals:

| Signal | Path Type | Observed Status | Project Context |
|---|---|---:|---:|
| `8db68a5936af4a22970a11ee9ca7cdfc` | completed manual / workspace-like path | `completed` | 0 review records, 0 calibration events |
| `f1417be3f0a04171a03695f0f54d86c9` | project-review / action path | `analyzed` | 3 review records, 6 calibration events |
| `49b9ea4609a27386` | paused / saved path | `saved` | 0 review records, 0 calibration events |

The selected signals are sufficient for Stage A because they exercise:

- signal ingestion
- insight generation
- verification metadata
- signal-level operator decision
- workspace completion metadata
- project review/calibration joins
- project outcomes derived from project-side records
- saved/paused state without downstream fan-out

## Direct Fields

Current storage can directly render these trajectory inputs:

- `signal.signal_id`
- `signal.title`
- `signal.published_at_or_collected_at`
- `signal.insight_fields`
- `signal.verification`
- `signal.status`
- `signal.workspace_saved` for completed workspace-linked records
- `project_review_records` when review records exist
- `project_calibration_events` when calibration events exist

These direct fields are enough to render a useful operator-facing trajectory.
They are not enough to claim authoritative lifecycle history.

## Non-Persisted Service Outputs

The probe showed three recurring service-output gaps:

1. Insight generation can be inferred from persisted insight fields, but the
   generation transition metadata is incomplete.
2. Verification services produce metadata, but the verification transition
   timestamp and actor are not persisted as lifecycle event data.
3. Project trajectory can be assembled from review/calibration services, but
   project fan-out creation is not persisted as a single signal-owned lifecycle
   transition.

These are not frontend gaps. They are write-path/provenance gaps. Stage B must
decide which service outputs become lifecycle events and which remain attached
metadata.

## Architecture Gaps

The probe exposed four architecture gaps that Stage B must address:

1. No authoritative `decision_trace` / lifecycle event history is attached to
   the sampled signals.
2. Signal status is stored, but status transition history is not authoritative
   for legacy/current records.
3. Project outcomes cannot be shown as signal-owned lifecycle history without
   joining project-side review and calibration records.
4. `allowed_downstream_actions` and `blocked_downstream_actions` explain
   verification policy gates, but they are not a full transition graph.

The most important finding is that AI Radar can render useful trajectory now,
but cannot yet prove how the signal reached each state.

## Stage B Schema Inputs

Stage B should design a `SignalLifecycleEvent` model around real transition
needs rather than speculative completeness.

The first event schema should be able to represent:

- signal ingestion / observation
- insight generation
- verification gate completion
- signal-level decisions such as saved, rejected, analyzed, and completed
- workspace completion
- project fan-out / candidate creation
- project review outcome attachment
- explicit override or legacy/inferred markers

Each event should be able to carry:

- signal id
- event type
- previous state and next state when applicable
- timestamp
- actor
- source id / source family when available
- provenance class: direct, derived, inferred, missing, or legacy
- verification status and evidence level when the transition depends on
  verification
- allowed and blocked downstream actions when relevant
- structured evaluation summary for claim or gate decisions
- project id when the transition concerns project fan-out or review
- source record references without storing raw prompts or external payloads

## Stage B Guardrails

Stage B should not begin by replacing every write path.

Recommended order:

1. Define the event schema and lifecycle service.
2. Add soft event recording to the highest-value write path first.
3. Label legacy or inferred trajectory data honestly in the UI.
4. Add focused tests for event creation and gate metadata.
5. Only after migrated paths are stable, introduce hard rejections for selected
   illegal transitions.

Do not use Stage B to:

- backfill all historical signals
- redesign Project Takeaway gates
- add a third LLM executor path
- bypass `blocked_downstream_actions`
- treat reflection content as factual evidence
- change deployment, CI, IAM, S3 paths, or workflow files

## Decision

ADR-0008 Stage A is complete.

The probe validates the ADR premise: Trajectory View is useful now, but current
storage is not authoritative enough for lifecycle enforcement. Stage B should
proceed only after a dedicated schema/design slice, using this report as the
input.

The next implementation step should not be Stage B immediately if another
higher-priority architecture slice is selected. If Stage B is selected, it
should start with schema design and soft event recording, not broad write-path
rewrites.
