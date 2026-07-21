---
title: Generate Insight Soft-Recording Implementation Plan
date: 2026-05-22
layer: L2-implementation-plan
status: implemented-local
related:
  - docs/adr/0008-signal-lifecycle-event-spine.md
  - docs/adr/INVARIANTS.md
  - docs/features/signal-lifecycle/2026-05-22-stage-b-minimal-event-schema-design.md
  - docs/features/signal-lifecycle/2026-05-22-stage-b-readiness-checklist.md
tags: [signal-lifecycle, generate-insight, soft-recording, implementation-plan]
---

# Generate Insight Soft-Recording Implementation Plan

## Implementation Result

Implemented locally on 2026-05-22.

Implemented files:

- `backend/app/services/signal_lifecycle_event_service.py`
- `backend/app/routes/signals.py`
- `tests/test_signal_lifecycle_event_service.py`
- `tests/test_backend_signal_workflows.py`

Validation:

- `py_compile` passed for the lifecycle service, signals route, and related
  tests.
- Targeted pytest passed:
  - `19 passed`

Current manual follow-up:

- run one real generate-insight smoke tomorrow
- confirm `backend/data/signal_lifecycle/<signal_id>.json` is written
- keep generated lifecycle data files out of commits unless deliberately
  converted into fixtures

## Goal

Plan the first ADR-0008 Stage B soft-recording implementation for
`/signals/generate-insight`.

The implementation should record lifecycle events for newly generated insights
without changing insight generation behavior, verification gates, response
shape, or downstream eligibility.

## Original Non-Goals

- Do not add hard enforcement.
- Do not create a legal transition table.
- Do not change insight generation prompts, model routing, or fallback logic.
- Do not change Project Takeaway gates.
- Do not store raw LLM prompts or full source payloads in lifecycle events.
- Do not make Reflection factual evidence.
- Do not backfill historical signals.
- Do not write to S3 from a new lifecycle path in the first implementation.

## Current Generate-Insight Paths

`POST /signals/generate-insight` has two primary branches:

1. Manual signal branch:
   - finds a manual signal
   - generates insight
   - updates manual session `analysis`, `analysis_status`, status, model
     fields, verification metadata, policy metadata, and evidence pack
   - saves manual session detail and index item
   - writes a debug record
   - returns the current manual insight response shape

2. Automatic signal branch:
   - loads the current signal
   - generates insight
   - calls `update_signal_insight_by_signal_id(..., new_status="analyzed")`
   - reloads the signal
   - writes a debug record
   - returns the current automatic insight response shape

Both branches already have the data needed for first soft-recording:

- signal id
- before content fingerprint
- generated/stored content fingerprint
- provider/model/provenance metadata
- verification metadata
- status before/after
- route
- event time / recorded time

## First Implementation Scope

Implement a small lifecycle event service with only the methods needed for this
path.

Suggested module:

```text
backend/app/services/signal_lifecycle_event_service.py
```

Initial functions:

```text
build_generate_insight_events(...)
append_signal_lifecycle_events(signal_id, events)
load_signal_lifecycle_events(signal_id)
```

Do not expose a public API route in the first slice.

## Storage Decision For First Slice

Use local file-backed storage first.

Suggested development path:

```text
backend/data/signal_lifecycle/<signal_id>.json
```

Rationale:

- avoids S3 write-path expansion
- avoids production storage commitment before the event shape is proven
- keeps tests simple
- preserves current signal records unchanged except for existing
  generate-insight writes

Rules:

- The lifecycle service should tolerate missing event files.
- The write should be best-effort only for the first soft-recording slice.
- A lifecycle write failure must not fail insight generation.
- Test mode should use temp paths or monkeypatched path helpers.
- Do not add S3 writes until a later storage decision.

## Event Emission Decision

Emit two events when verification metadata exists:

1. `insight_generated`
2. `verification_completed`

Emit only `insight_generated` when verification metadata is absent.

Rationale:

- Stage A gap report identified generation and verification as separate
  non-persisted service outputs.
- Verification may eventually need its own hard-enforcement readiness checks.
- A separate event keeps future source-level aggregation clearer.

Both events may share the same `event_time` and `recorded_at` in the first
implementation.

## Event Draft Rules

### `insight_generated`

Required:

- `event_type`: `insight_generated`
- `provenance_class`: `direct`
- `actor`: `{ "type": "system", "id": "ai-radar-backend" }`
- `route`: `/signals/generate-insight`
- `source_ref.record_family`: `manual_session` or `signal`
- `source_ref.record_id`: manual session id or signal id
- `state.before`: preexisting status when available
- `state.after`: stored status after generation, usually `analyzed`
- `model_provenance_ref`: compact reference if `produced_by_model` is v1
- no raw prompt or full external payload

Optional:

- content fingerprint summary:
  - `preexisting_fingerprint`
  - `generated_fingerprint`
  - `stored_fingerprint`
  - `fingerprint_changed`

### `verification_completed`

Required when verification exists:

- `event_type`: `verification_completed`
- `provenance_class`: `direct`
- same `actor`, `route`, and `source_ref` as the insight event
- `support.verification_status`
- `support.allowed_downstream_actions`
- `support.blocked_downstream_actions`
- `support.claim_support_summary` when available
- `support.confidence_label` and `support.confidence_score` when available
- sanitized `support.evaluation_summary` when available

Must not:

- convert missing metadata into `verified_insight`
- change blocked/allowed actions
- create Project Takeaway candidates
- raise trust from model provenance

## Response Shape

The first implementation must not change the API response shape.

Allowed:

- internal event file write
- tests that load event files directly
- future optional debug-only response field only in a later slice

Not allowed in the first implementation:

- adding `lifecycle_events` to the browser response
- changing `status`, `verification`, `policy_metadata`, or `evidence_pack`
  semantics
- failing insight generation because soft recording failed

## Legacy And Inferred Display

No frontend display change is required in the first implementation.

After events exist, a later UI slice can read:

- direct lifecycle events from event storage
- inferred trajectory from existing signal fields
- derived project review/calibration attachments

Until that UI slice exists, the existing Trajectory View should remain honest:
legacy/inferred probe output is not authoritative lifecycle history.

## Test Plan

Backend unit tests for `signal_lifecycle_event_service`:

- builds `insight_generated` for automatic signal generation
- builds `insight_generated` for manual session generation
- builds `verification_completed` only when verification metadata exists
- extracts support fields without mutating verification metadata
- creates compact `model_provenance_ref` without treating it as evidence
- omits raw prompt/source payload fields
- appends and reloads events from a temp local path

Route/service integration tests:

- automatic `/signals/generate-insight` still returns the existing response
  shape and records lifecycle events
- manual `/signals/generate-insight` still returns the existing response shape
  and records lifecycle events
- lifecycle write failure does not fail insight generation
- missing verification metadata records only `insight_generated`
- generated lifecycle support preserves `blocked_downstream_actions`

Regression tests to keep:

- model provenance service tests
- verified insight tests
- Project Takeaway review-flow tests
- backend signal workflow tests

## Business Logic Checklist

- Project Takeaway gates remain unchanged.
- `blocked_downstream_actions` are copied into lifecycle support but not
  overwritten.
- Lifecycle events do not create `verified_insight`.
- Model provenance remains audit metadata only.
- Manual sessions remain manual sessions; lifecycle recording must not promote
  manual content into verified evidence.
- Reflection content is not stored in lifecycle event support.
- Soft recording is additive and non-blocking.

## First Implementation Checklist

1. Add `backend/app/services/signal_lifecycle_event_service.py`.
2. Add path helper for local lifecycle event files.
3. Add event builder helpers:
   - `build_insight_generated_event`
   - `build_verification_completed_event`
4. Add append/load helpers.
5. Call helpers from both branches of `/signals/generate-insight` after the
   existing signal/session write succeeds.
6. Wrap lifecycle append in a best-effort guard.
7. Add focused tests.
8. Run targeted backend tests.

## Open Questions Before Coding

- Should lifecycle storage live under `backend/data/signal_lifecycle/` or
  `backend/data/output/signal_lifecycle/` for local/dev?
- Should event id be deterministic from signal id + event type + stored
  fingerprint, or generated with a timestamp/random suffix?
- Should `verification_completed` event time equal `insight_generated`, or
  should it use a separate timestamp even in the same route call?
- Should failed lifecycle writes be logged only to server logs, or should a
  debug counter be added later?

## Definition Of Done For The Future Implementation

The implementation slice is done when:

- automatic and manual generate-insight paths soft-record lifecycle events
- response shape and existing insight semantics are unchanged
- tests prove soft-recording is additive and non-blocking
- blocked downstream actions remain preserved
- no hard enforcement, backfill, S3 write, or frontend claim of authoritative
  lifecycle history is introduced

## Current Decision

The first code implementation should target `/signals/generate-insight` and
local file-backed soft recording only.

Do not implement hard enforcement or project-review derived events in the same
slice.
