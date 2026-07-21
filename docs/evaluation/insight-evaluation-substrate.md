# Insight Evaluation Substrate

Date: 2026-05-28
Status: skeleton, no seeded cases yet
Scope: deterministic evaluation foundation for verification-aware insight quality

## Purpose

This substrate prepares for future held-out insight evaluation without
pretending that current local/test data is a benchmark.

## Phase 0

- define a case schema
- provide a local validator/report runner
- provide a template case file and a `--print-template` helper for manual
  seeded-case creation
- allow zero cases while the trusted seeded set is not selected
- report readiness as `needs_seed_cases`

Template helper:

```bash
python scripts/check_insight_eval_seed_cases.py --print-template --template-case-id case-001
```

Readiness helper:

```bash
python scripts/check_insight_eval_seed_cases.py --format json --min-accepted-seeds 20
```

The default deterministic-eval readiness threshold is 20 accepted seed cases.
The `--min-accepted-seeds` option is for local planning and dry runs; changing
it does not change the product standard that the first real held-out set should
contain 20 to 30 human-selected cases.

Accepted seed guardrails:

- `accepted_seed` cases must replace template placeholder text
- `accepted_seed` cases must include at least one `input.source_refs` entry
- `accepted_seed` cases must include `expected.notes` explaining why the case
  is trusted
- `case_id` values must be unique across the seeded-case directory
- template output remains `seed_candidate` until the human selects and edits it

The report also includes source-boundary distribution counts so the seed set can
be reviewed for mix across `human_seeded`, `trusted_historical`, and
`blocked_action_case` cases.

Schema alignment guardrails:

- `input.source_refs` must be a list of non-empty strings when present
- `expected.verification_status` must be a string when present
- `expected.required_blocked_actions` must be a list of non-empty strings when
  present
- `expected.max_unsupported_or_contradicted_claims` must be a non-negative
  integer when present
- `expected.requires_model_provenance` must be a boolean when present
- `expected.notes` must be a string when present
- unknown `expected` fields are rejected by the validator

The report includes expected-field coverage counts for:

- `verification_status`
- `required_blocked_actions`
- `max_unsupported_or_contradicted_claims`
- `requires_model_provenance`
- `notes`

These counts are review signals only. They do not prove that the expected
answers are correct.

## Future Phase 1

The human-selected case set should contain 20 to 30 seeded cases, mixed from:

- historical verified insights that are trusted
- known blocked-action cases
- manually written edge cases

## Low-Cost Deterministic Metrics

- schema validity
- expected verification status presence
- expected blocked action presence
- expected unsupported / contradicted claim count presence
- model provenance expectation presence

## Non-Goals

- no LLM judge
- no strict-greater-than gate
- no automatic case generation from local/test data
- no production quality claim from an empty or unreviewed case set
