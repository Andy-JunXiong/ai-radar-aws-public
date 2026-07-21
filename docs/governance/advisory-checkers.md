# Advisory Checkers

Date: 2026-05-28
Status: local governance index
Scope: read-only advisory scripts only

This index lists local checkers that help review AI Radar governance and
intelligence-quality boundaries. These scripts do not replace runtime gates,
human review, trusted data selection, or CI policy.

## Verification Metadata Contract

Command:

```bash
python scripts/check_verification_metadata_contract.py --summary-only
```

Purpose:
- report whether stored insight, Project Takeaway, and lifecycle verification
  metadata has the expected contract shape
- surface missing fields and allowed/blocked downstream action conflicts

Boundary:
- read-only
- soft report only
- not a schema migration
- not factual claim verification
- not runtime enforcement

## Verification Metadata Schema Hardening

Command:

```bash
python scripts/check_verification_metadata_schema_hardening.py --format json
```

Purpose:
- identify code and test touchpoints that would matter before making
  `verification_metadata` schema stricter

Boundary:
- migration-risk audit only
- not a runtime behavior change
- not approval to harden schema

## Artifact Citation Integrity

Command:

```bash
python scripts/check_artifact_citation_integrity.py --format text
```

Optional strict local mode:

```bash
python scripts/check_artifact_citation_integrity.py --fail-on-gaps
```

Purpose:
- check whether agent-authored markdown artifacts name sources and separate
  inference, evidence, and actionability boundaries

Boundary:
- read-only
- not external factual verification
- not automatic ADR absorption
- strict mode is local only unless a future CI slice is explicitly approved

## Source Excerpt Preservation Contract

Command:

```bash
python scripts/check_source_excerpt_preservation_contract.py --format text
```

Report schema:

```text
docs/governance/source-excerpt-preservation-contract.schema.json
```

Optional strict local mode:

```bash
python scripts/check_source_excerpt_preservation_contract.py --fail-on-gaps
```

Purpose:
- check whether ADR-0011 source excerpt preservation still has the expected
  static code contract
- confirm the official collector writes canonical `source_excerpt`
- confirm merge normalization preserves bounded `source_excerpt`
- confirm `content == summary` is not promoted to source excerpt evidence
- confirm final pipeline signal output does not preserve full-text-like fields
  such as `raw_text`, `raw_content`, `full_text`, or `article_body`

Boundary:
- read-only static contract check
- not a fresh ingestion run
- not source truth judgment
- not historical backfill
- not prompt/schema expansion
- strict mode is local only unless a future CI slice is explicitly approved

## Project Takeaway Claim Dependency

Command:

```bash
python scripts/check_project_takeaway_claim_dependencies.py --format json
python scripts/check_project_takeaway_claim_dependencies.py --summary-only
```

Purpose:
- measure whether Project Takeaway records can be linked to specific verified
  claim IDs or only aggregate support summaries
- summarize linkability by `candidate_source`, `status`, and `project_id` so
  Phase 2 schema work can distinguish linked records, summary-only records, and
  dependency-unknown records before proposing `depends_on_claim_ids`
- emit source-policy hints for Phase 2 design only:
  `eligible_for_claim_id_schema_probe`,
  `requires_claim_item_backfill_or_summary_only_boundary`,
  `mark_dependency_unknown_or_exclude_from_claim_dag`, and
  `requires_source_specific_split_policy`

Boundary:
- architecture-readiness input only
- not a production metric claim
- not approval for DAG, cascade, or schema migration
- not automatic backfill or source migration

## Project Takeaway A1 Gaps

Command:

```bash
python scripts/check_project_takeaway_a1_gaps.py
```

Purpose:
- report known Project Takeaway verification-boundary risks, including missing
  verification metadata, blocked action issues, and ambiguous candidate source
  states

Boundary:
- advisory by default
- `--fail-on-gaps` is for explicit local strict checking only
- not a replacement for runtime verification services

## Signal Near-Duplicates

Command:

```bash
python scripts/check_signal_near_duplicates.py --format text
```

Optional JSON summary:

```bash
python scripts/check_signal_near_duplicates.py --format json --summary-only
```

Purpose:
- report local signal records that share a content fingerprint across distinct
  URLs
- identify category-vs-article groups and ambiguous same-content groups
- recommend preferred canonical article records for clear category-vs-article
  cases
- separate report-only cleanup advice from human-review-required groups

Boundary:
- read-only local signal output check
- not ingestion
- not deduplication
- not a data rewrite
- not a replacement for human review of ambiguous duplicate groups

## GitHub Scalar Coverage

Command:

```bash
python scripts/check_github_scalar_coverage.py --summary-only --format text
```

Optional strict local mode:

```bash
python scripts/check_github_scalar_coverage.py --fail-on-gaps
```

Purpose:
- report local GitHub signal records that do or do not carry canonical scalar
  metadata such as stars, license, archived state, created date, and updated
  date
- quantify historical coverage gaps before proposing a backfill, collector
  rerun, or broader canonical scalar resolver slice

Boundary:
- read-only local coverage audit only
- not a GitHub API fetch
- not source-truth verification by itself
- not action eligibility, source scoring, or Project Takeaway gate logic

## GitHub Scalar Backfill Readiness

Command:

```bash
python scripts/check_github_scalar_backfill_readiness.py --summary-only --format text
```

Optional strict local mode:

```bash
python scripts/check_github_scalar_backfill_readiness.py --fail-on-live-required
```

Purpose:
- dry-run whether historical GitHub signal records can be locally standardized
  into canonical scalar metadata or require live GitHub API refresh
- separate locally available scalar fields from fields that cannot be inferred
  without a fresh canonical source lookup

Boundary:
- read-only dry-run only
- not a GitHub API fetch
- not a data rewrite or backfill
- not source-truth verification, source scoring, or action eligibility logic

## GitHub Scalar Live Refresh

Command:

```bash
python scripts/check_github_scalar_live_refresh.py --summary-only --format text --max-records 5
```

Purpose:
- fetch a bounded number of public GitHub repo records and report which
  canonical scalar fields would be added or updated
- validate live refresh feasibility before any data rewrite or backfill slice

Boundary:
- read-only live HTTP GET dry-run only

## Operational Import Boundary

Command:

```bash
python scripts/check_operational_import_boundary.py --summary-only --format text
```

Optional strict local mode:

```bash
python scripts/check_operational_import_boundary.py --fail-on-violations
```

Purpose:
- statically scan verification/action-path Python files for imports from
  operational-health helpers such as `radar_doctor`, GitHub scalar advisory
  checkers, and source-health probing
- keep operational health and coverage diagnostics from leaking into epistemic
  eligibility or action-gate code paths

Boundary:
- read-only AST scan only
- not a runtime import graph
- not source-truth verification
- not source scoring, Project Takeaway gate logic, or Action eligibility logic
- not a data rewrite or backfill
- not source scoring, Project Takeaway gate logic, or action eligibility
- star-count differences are temporal refresh candidates, not automatically
  historical source errors

## Insight Eval Seed Cases

Command:

```bash
python scripts/check_insight_eval_seed_cases.py --format json
```

Purpose:
- validate the held-out insight evaluation case fixture shape once trusted
  seed cases are selected

Boundary:
- eval substrate readiness only
- not automatic seed-case generation
- not a production quality claim
