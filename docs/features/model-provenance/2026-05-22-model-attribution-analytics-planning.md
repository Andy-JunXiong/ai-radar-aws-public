---
title: Model Attribution Analytics Planning Slice
date: 2026-05-22
layer: L2-feature-planning
status: slice-c-implemented
related:
  - docs/adr/0009-model-provenance-schema.md
  - CURRENT_DEVELOPMENT_STATUS.md
tags: [model-provenance, analytics, calibration, review-quality]
---

# Model Attribution Analytics Planning Slice

## Goal

Define the first safe analytics layer that can use ADR-0009
`produced_by_model` metadata without changing model routing, trust scoring, or
Project Takeaway gates.

The purpose is to help answer operational questions such as:

- Which model / prompt fingerprint produced the reviewed judgment?
- How much of the current review corpus has v1 provenance versus legacy/v0?
- Are review outcomes clustered by model, route, prompt template, or fingerprint?
- Which records are eligible for future model-attribution analysis?

This slice is planning only. It does not implement analytics code, APIs, UI, or
model comparison tooling.

## Non-Goals

- Do not compare model quality or declare one model better than another.
- Do not change routing policy, route selection, env variables, or fallback
  behavior.
- Do not add YAML route config.
- Do not add `compare_models`.
- Do not add a third LLM executor path.
- Do not change verification score, evidence score, review priority, or
  Project Takeaway gate logic.
- Do not backfill historical records.
- Do not infer v1 provenance from loose `provider_used` / `model_used` fields.

## Eligible Record Set

Analytics may include a record only when it has structured v1 provenance:

```json
{
  "produced_by_model": {
    "provenance_schema_version": 1,
    "provider": "openai",
    "model_id": "gpt-5.5",
    "route_key": "insight.synthesize",
    "prompt_template_id": "signal_insight",
    "prompt_template_version": "v1",
    "deterministic_fingerprint": "full-sha256"
  }
}
```

Legacy records remain visible in coverage counts but must be excluded from
model-attribution calculations:

```json
{
  "provenance_schema_version": 0,
  "provenance_completeness": "legacy"
}
```

Legacy/v0 is not a negative quality label. It means the record was created
before the ADR-0009 write path stored full provenance.

## Candidate Data Sources

Initial analytics should read from local/backend read layers that already
surface Project Takeaway and review records. Do not query S3 directly from a
new analytics implementation unless the existing service layer already does so.

Candidate sources:

- Project Takeaway candidates:
  - candidate-level `produced_by_model`
  - `verification_metadata.produced_by_model`
  - `verification_metadata.verified_insight.produced_by_model`
- Project ReviewRecords:
  - preserved `produced_by_model`
  - review outcome: `confirmed`, `rejected`, `dismissed`, `watch`, `action`
- CalibrationEvents:
  - preserved `produced_by_model`
  - event type and review outcome metadata
- Signals:
  - top-level `produced_by_model`
  - `verification.produced_by_model`
  - nested verified-insight provenance

Root model-router telemetry remains operational telemetry, not judgment
provenance. It can be used later for infrastructure usage summaries, but it
should not be mixed with judgment attribution unless there is a durable record
join.

## First Metrics

### Provenance Coverage

Count records by provenance state:

- v1 provenance present
- legacy/v0
- malformed provenance
- missing record family support

Suggested slices:

- by record family: signal, candidate, review record, calibration event
- by project
- by route key
- by day / week

### Model / Route Distribution

For v1-only records:

- provider
- model_id
- route_key
- prompt_template_id
- prompt_template_version
- deterministic_fingerprint prefix

This should be descriptive only. It must not imply quality ranking.

### Review Outcome Distribution

For v1 Project ReviewRecords only:

- count by review outcome
- count by provider / model_id
- count by route_key
- count by deterministic_fingerprint

This is safe only as an observation surface. It should be labelled as
correlation, not causation.

### Gate Outcome Distribution

For v1 candidate / verification metadata only:

- review_priority
- verification_status
- blocked_downstream_actions
- allowed_downstream_actions
- claim_support_summary

This can help detect whether a route produces many review-blocked candidates,
but it must not automatically change routing.

## Required Exclusions

Exclude from attribution calculations:

- legacy/v0 records
- records with only `provider_used` / `model_used`
- manual entries marked `unverified_manual_entry` without v1 provenance
- reflection content used only as cognitive context
- debug telemetry files
- model-router usage logs without durable judgment linkage

Include excluded records only in coverage/gap counts.

## Suggested API Shape

Future backend endpoint, if implemented:

```text
GET /admin/model-attribution/summary?days=30&project_id=<optional>
```

Suggested response shape:

```json
{
  "schema_version": 1,
  "generated_at": "2026-05-22T00:00:00+00:00",
  "scope": {
    "days": 30,
    "project_id": "all"
  },
  "coverage": {
    "total_records": 0,
    "v1_records": 0,
    "legacy_v0_records": 0,
    "malformed_records": 0
  },
  "by_record_family": [],
  "by_model": [],
  "by_route": [],
  "review_outcomes": [],
  "excluded": {
    "legacy_v0": 0,
    "missing_linkage": 0,
    "manual_unverified": 0
  }
}
```

The endpoint should be admin-only. Do not expose it to ordinary users until the
meaning and limitations are stable.

## Suggested UI Shape

Future UI should be an admin/operator diagnostics surface, not a product
decision card.

Suggested placement:

- `/admin/model-attribution`
- or an Admin tab near model-routing / operator guidance

Display rules:

- lead with coverage and exclusions
- label outcome summaries as correlation
- show legacy/v0 as an audit coverage gap, not an error
- do not rank models
- do not recommend routing changes
- link to example records only after the data join is reliable

## Implementation Slice Proposal

### Slice A: Backend Summary Service

Add a read-only service that accepts already-loaded candidate/review/calibration
records and returns summary aggregates.

Validation:

- unit tests with mixed v1, legacy/v0, malformed, and manual-unverified records
- prove legacy/v0 records are counted in coverage but excluded from attribution
- prove provenance alone does not affect gates

Implementation status:

- implemented on 2026-05-22:
  - `backend/app/services/model_attribution_analytics_service.py`
  - `tests/test_model_attribution_analytics_service.py`
- still intentionally no API or UI
- still no model ranking, route recommendation, or gate behavior change

### Slice B: Admin API

Expose the service through an admin-only endpoint.

Validation:

- auth guard test
- response-shape test
- no S3 write
- no Secrets read

Implementation status:

- implemented on 2026-05-22:
  - `GET /projects/model-attribution/summary`
  - `tests/test_model_attribution_analytics_app_route.py`
- endpoint is admin-only
- endpoint returns the read-only summary under `summary`
- endpoint currently aggregates Project Takeaway candidates, ReviewRecords, and
  CalibrationEvents
- signal-wide attribution remains deferred until the read path is deliberately
  scoped to avoid accidental broad S3/cache work
- still intentionally no UI, model ranking, route recommendation, or routing
  policy change

### Slice C: Admin UI

Add a compact read-only diagnostics page.

Validation:

- v1 / legacy coverage renders clearly
- excluded counts are visible
- no model ranking language
- no routing recommendation language

Implementation status:

- implemented on 2026-05-22:
  - `/admin/model-attribution`
  - Admin home entry under Signals
- UI calls the admin-only backend summary endpoint:
  - `GET /projects/model-attribution/summary`
- UI leads with coverage and exclusions, then record-family, model, route,
  review-outcome, and gate-outcome distributions
- copy explicitly states the page is read-only and does not rank models,
  recommend routing changes, or change verification gates
- still no model ranking, route recommendation, routing policy change, or
  Project Takeaway gate change

## Definition Of Done For This Planning Slice

- Analytics scope is defined.
- Eligible and excluded record sets are explicit.
- First safe metrics are defined.
- API/UI are described only as future slices.
- No runtime code, route policy, or Project Takeaway gate is changed.
- ADR-0009 boundaries remain intact.
