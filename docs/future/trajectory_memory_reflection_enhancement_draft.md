# Trajectory Memory Reflection Enhancement Draft

Last updated: 2026-04-15

## Purpose

This document is a drafting bridge for work that belongs in the separate
`trajectory-memory` repository.

It exists here only to:

- capture the agreed scope while implementation is still being coordinated
- preserve the link between AI Radar reflection evolution and trajectory-memory
- make later migration into the target repo straightforward

This is **not** an implementation source of truth for `ai-radar-aws`.
The actual schema, service, and API work should live in `trajectory-memory`.

---

## Recommended Target Doc

When this work moves into the target repository, the main design document should
be created as:

- `docs/design/2026-04-15-reflection-trajectory-enhancement.md`

That target doc should become the primary planning and review artifact.

---

## Problem This Enhancement Solves

The current reflection and trajectory systems can record events and produce
derived slices, but they still lack several pieces needed for stronger
reflection quality, traceability, and long-term observability:

- explicit actor attribution on events
- richer feedback semantics than simple like/dislike patterns
- clean backward/forward references between events, slices, and feedback
- read-only observability over reflection decay and re-use
- an optional adversarial reflection mode for manual stress-testing

---

## Scope Summary

### Phase 1: Schema fields

Add three explicit schema capabilities:

1. `trajectory_events.actor`
   - enum:
     - `user`
     - `llm`
     - `system`
     - `hybrid`
   - no default
   - must be explicitly provided by `RecordService`
   - missing actor should raise a validation error

2. `feedback_signals.stance`
   - enum:
     - `endorse`
     - `resist`
     - `confused`
     - `revise`
   - becomes the preferred feedback field for new code
   - existing simpler feedback fields can remain for compatibility only

3. Reference fields
   - `trajectory_slices.source_event_ids`
     - array of event ids used to construct a slice
   - `feedback_signals.target_reflection_id`
     - reference to the slice/reflection being evaluated

Together these fields improve traceability and make reflection review auditable
in both directions.

### Phase 2: Meta observability

Add a fully independent, read-only observability layer:

- new table:
  - `meta_observability_metrics`
- new table:
  - `meta_observability_alerts`
- new service:
  - `app/services/meta_observability_service.py`
- new threshold config:
  - `config/observability_thresholds.yaml`

Initial daily metrics:

- percentage of recent events with non-null `actor`
- distribution of `stance` values
- 30-day post-reflection reference counts
- 7d / 30d / 90d decay curves for `insight` slices

Important constraint:

- this layer must stay off the hot path
- no LLM should be used for threshold evaluation
- alerts should be deterministic and explainable

### Phase 3: Optional adversarial reflection

If implemented later, this should remain intentionally narrow:

- one manual endpoint:
  - `POST /reflections/{slice_id}/adversarial`
- two isolated LLM calls:
  - defense of the original response
  - critique of deference / conflict avoidance / loss of judgment
- output stored as a comparison slice
- metadata flag:
  - `reflection_type='adversarial'`

---

## Why Full Adversarial Triad Is Not Included

This scope intentionally does **not** implement:

- judge agent orchestration
- multi-role adversarial debate trees
- five-part or multi-stage adjudication structures
- richer courtroom-style role separation

Reason:

- the current goal is to add a lightweight manual contrast mechanism
- not to redesign reflection generation into a full adversarial system
- a larger triad/judge design would expand both architecture and review burden
  too early

This is a deliberate scoping decision, not an omission.

---

## Suggested Supporting Docs In `trajectory-memory`

Beyond the main design doc, the target repo would benefit from two smaller docs:

### 1. Runbook

Suggested path:

- `docs/runbooks/meta-observability.md`

Should cover:

- how to run `daily_aggregate()`
- how to validate metrics writes
- how to trigger and inspect alerts
- how to test threshold config changes safely

### 2. API note

Suggested path:

- `docs/api/reflection-meta-endpoints.md`

Should cover:

- `GET /meta/alerts`
- `POST /reflections/{slice_id}/adversarial`
- response expectations
- non-goals for this phase

---

## Relationship To AI Radar

For `ai-radar-aws`, this work matters because it strengthens the upstream
memory/reflection substrate that future AI Radar reflection intelligence may
rely on.

Expected downstream relevance:

- richer reflection provenance
- stronger feedback semantics
- observability around reflection usefulness over time
- future adversarial reflection inputs for Radar-side interpretation

However, the implementation itself still belongs in the trajectory-memory
repository, not here.
