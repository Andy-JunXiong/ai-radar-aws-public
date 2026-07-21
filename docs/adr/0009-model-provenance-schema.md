---
adr: 0009
title: Model Provenance Schema
status: Accepted
created: 2026-05-22
accepted: 2026-05-22
layer: L1-engineering-solution
related:
  - L2: AGENTS.md
  - L2: CURRENT_DEVELOPMENT_STATUS.md
  - L1: docs/adr/0008-signal-lifecycle-event-spine.md
  - L2: docs/features/signal-lifecycle/2026-05-22-stage-a-gap-report.md
tags: [model-provenance, verification, judgment-versioning, audit]
---

# ADR-0009: Model Provenance Schema

## ADR Gate

Create this ADR only if all are yes:

- [x] Hard to reverse: once model provenance becomes part of verified insight,
  claim support, Project Takeaway, calibration, or reflection records, the
  field shape becomes part of AI Radar's judgment audit contract.
- [x] Context would be lost: future readers would ask why AI Radar records the
  model and prompt provenance for judgments separately from source evidence and
  from model routing policy.
- [x] Real tradeoff: plausible alternatives include continuing with loose
  `provider_used` / `model_used` fields, backfilling historical records, or
  combining provenance schema with route-selection policy in one ADR.

## Context

AI Radar's core product claim is epistemic rigor: the system helps decide what
is trustworthy, what remains uncertain, and which downstream actions are
allowed or blocked.

The system already records some model information in individual outputs:

- signal insight generation can carry `provider_used` and `model_used`
- model-router telemetry records task, provider, model, mode, and outcome
- workspace chat records can carry provider/model fields

That is useful operational telemetry, but it is not a complete judgment
provenance schema. A verified insight, claim-support decision, Project Takeaway
candidate, calibration event, or reflection polish pair may all depend on a
model judgment. If the model identity, prompt template version, inference
parameters, and route provenance are not stored with the produced judgment, AI
Radar cannot later distinguish:

- a change in evidence
- a change in model behavior
- a change in prompt/template behavior
- a change in inference parameters
- a routing fallback or degraded route

ADR-0008's Stage A gap report showed the same general problem from another
angle: AI Radar can often render useful current state, but cannot yet prove the
full path that produced that state. Model provenance is part of that path for
LLM-produced judgments.

## Decision

Adopt a structured `produced_by_model` field for new judgment-producing
records.

The field records model provenance. It does not record source evidence, and it
does not by itself make a judgment more trustworthy.

Initial schema:

```json
{
  "produced_by_model": {
    "provider": "anthropic",
    "model_id": "claude-opus-4-7",
    "model_version": "",
    "task_type": "insight",
    "route_key": "insight.synthesize",
    "router_source": "env",
    "prompt_template_id": "signal_insight",
    "prompt_template_version": "v1",
    "inference_params": {
      "temperature": 0.3,
      "max_tokens": 1800,
      "top_p": null,
      "stop_sequences": []
    },
    "deterministic_fingerprint": "full-sha256",
    "generated_at": "2026-05-22T00:00:00+00:00",
    "provenance_schema_version": 1
  }
}
```

### Required Semantics

- `provider`: normalized provider label, such as `openai`, `anthropic`, or
  `fallback`.
- `model_id`: exact configured model id used for the call. Empty string is
  allowed only for non-LLM fallback/template output.
- `model_version`: provider-specific model version when available. Empty
  string is allowed when the provider does not expose a separate version.
- `task_type`: the current model-router task type or equivalent execution
  category.
- `route_key`: stable operation key when known, such as `insight.synthesize` or
  `verification.claim_support`. Until route-key routing exists, write paths may
  use the closest stable task key.
- `router_source`: actual source of the route that produced the judgment, such
  as `env`, `config`, `fallback_from_primary`, `hard_default`, or `manual`.
- `prompt_template_id`: stable id for the prompt template or prompt family.
- `prompt_template_version`: version string for the prompt template or prompt
  registry entry. Use `unknown` only when the current path has not yet been
  migrated.
- `inference_params`: structured parameters that can affect judgment output.
- `deterministic_fingerprint`: full SHA-256 over normalized provider, model,
  model version, prompt template version, and inference params. UI and reports
  may display a short prefix, but storage keeps the full hash.
- `generated_at`: timestamp when the judgment was produced.
- `provenance_schema_version`: required integer. New writes use `1`.

### Initial Record Types

The schema applies to new records in these judgment-producing families:

- verified insight
- claim verification / claim support decisions
- LLM-mediated evidence pack generation
- Project Takeaway candidate creation
- calibration event creation
- reflection polish pairs

The implementation may migrate these write paths in small slices. ADR-0009
defines the target schema for all of them; it does not require all paths to be
migrated in one code change.

### Reflection Polish Pairs

Reflection polish pairs must not share a single provenance object for both
sides.

Use separate provenance where both sides are model-produced or derived from
model-produced content. A shared object would create false consistency when the
before side may come from an older model, another route, or a prior day.

### Legacy / No-Backfill Rule

Do not backfill historical records.

Historical records must remain byte-for-byte unchanged unless a separate
explicit migration is approved. Reading code should interpret missing
`produced_by_model` as legacy provenance:

```json
{
  "provenance_schema_version": 0,
  "provenance_completeness": "legacy"
}
```

This interpretation belongs in read/normalization layers and analysis code. It
must not be written back into historical files merely to mark them.

Downstream rules:

- legacy/v0 records are excluded from model-attribution analysis
- legacy/v0 records do not gain elevated trust from missing provenance
- missing provenance is not a reason to bypass `blocked_downstream_actions`
- missing provenance must not be silently upgraded to v1 by inference

## Owns

- The existence and shape of `produced_by_model`.
- The rule that new judgment-producing records must carry structured model
  provenance once their write path is migrated.
- The no-backfill rule for historical records.
- The read-layer interpretation of missing provenance as legacy/v0.
- The distinction between judgment provenance and source evidence.
- The use of full-hash storage with short-hash display allowed.

## Does Not Own

- Which model should be used for each route.
- The future per-route YAML model configuration format.
- Model comparison / evaluation tooling.
- Runtime user model selection.
- Admin UI or admin endpoint for model comparison.
- SSM, DynamoDB, or other external model config storage.
- Any new LLM executor path.
- Any change to `.github/workflows/`, deployment, IAM, S3 paths, or CI.
- Any bypass or weakening of Project Takeaway verification gates.

## Consequences

AI Radar gains a durable way to distinguish judgment evolution from model,
prompt, and inference-parameter changes.

Supersession and calibration analysis can compare whether two judgments were
produced under the same model-provenance fingerprint before attributing a
change to evidence or reasoning.

The schema creates migration work across several write paths. To control risk,
implementation should start with a narrow C slice and avoid route-policy
changes in the same sprint.

The no-backfill rule preserves historical integrity but means old records will
remain less analyzable. That is acceptable: missing provenance is a truthful
legacy state, not a data quality issue to paper over.

Storing model provenance can tempt downstream logic to treat stronger models as
more trustworthy. That is explicitly not allowed by this ADR. Trust still comes
from evidence, verification metadata, support status, and policy gates.

## Alternatives Considered

### Alternative 1: Keep loose `provider_used` and `model_used`

Rejected. These fields are useful for display and telemetry but do not capture
prompt version, inference parameters, route source, or schema version.

### Alternative 2: Backfill historical records with version 0

Rejected. Writing `provenance_schema_version: 0` into historical records is
still a backfill. Legacy interpretation should happen at read time.

### Alternative 3: Combine schema and model-routing policy in one ADR

Rejected. Provenance schema changes rarely and affects data migration. Routing
policy changes more often as models change. Combining them would make future
supersession coarse and confusing.

### Alternative 4: Let users choose models per request

Rejected for ordinary product use. AI Radar optimizes epistemic rigor and
comparability, not preference matching. Runtime user model selection may be
considered only for explicit admin/debug comparison tools that do not write
production judgments.

## Implementation Plan

1. Add a small provenance builder/helper that accepts the actual route,
   prompt/template metadata, inference params, and timestamp.
2. Add read-layer normalization for missing provenance as legacy/v0 without
   mutating historical records.
3. Migrate the first narrow write paths:
   - verified insight
   - claim support / verification decisions
   - Project Takeaway candidate creation
4. Add focused tests proving:
   - new writes carry `provenance_schema_version=1`
   - legacy records without `produced_by_model` read as v0
   - v0 records do not bypass Project Takeaway gates
   - deterministic fingerprints are full SHA-256 values
5. Record any deferred write paths explicitly before closing the slice.
6. Only after the C slice is validated, open a separate routing-policy ADR for
   compare-models tooling and per-route model configuration.

## Acceptance Notes

Accepted on 2026-05-22 after the first C slice and visibility slice were
implemented and browser-validated.

Validated behavior:

- new generated signal insights write structured `produced_by_model` metadata
- verification and nested verified-insight metadata preserve model provenance
- Project Takeaway candidate writes carry model provenance when available
- ReviewRecord and CalibrationEvent creation preserve model provenance
- missing historical provenance reads as legacy/v0 without backfilling
- Signal Detail and Review Inbox show compact v1 / legacy-v0 provenance labels
- model provenance remains audit metadata only and does not satisfy evidence or
  Project Takeaway verification gates

Deferred beyond this ADR's accepted first implementation:

- reflection polish pair provenance migration
- model-attribution analytics
- compare-models tooling
- YAML route config or model-routing policy ADR

## Open Questions

- Which current prompt registry ids should become the canonical
  `prompt_template_id` values for write paths beyond the first migrated signal
  insight path?
- Should non-LLM deterministic fallback outputs use provider `fallback` or a
  more specific provider such as `template` in future non-insight paths?

## References

- [ADR-0008: Signal Lifecycle Event Spine](./0008-signal-lifecycle-event-spine.md)
- [ADR-0008 Stage A Signal Lifecycle Gap Report](../features/signal-lifecycle/2026-05-22-stage-a-gap-report.md)
- [AGENTS.md](../../AGENTS.md)
- [CURRENT_DEVELOPMENT_STATUS.md](../../CURRENT_DEVELOPMENT_STATUS.md)
