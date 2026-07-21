---
adr: 0011
title: Evidence Pack Source Excerpt Policy
status: Accepted
created: 2026-05-28
accepted: 2026-05-28
layer: L1-engineering-solution
related:
  - L1: docs/adr/0009-model-provenance-schema.md
  - L1: docs/adr/0010-external-insight-admission-gate.md
  - L2: docs/notes/insight-admission-gate.md
  - L2: CURRENT_DEVELOPMENT_STATUS.md
tags: [evidence-pack, source-excerpt, claim-origin, verification, provenance]
---

# ADR-0011: Evidence Pack Source Excerpt Policy

## ADR Gate

Create this ADR only if all are yes:

- [x] Hard to reverse: once source excerpts enter evidence packs, their field
  shape, retention boundary, and provenance semantics become part of AI
  Radar's verification contract.
- [x] Context would be lost: future readers would ask why claim-origin
  verification requires bounded excerpts instead of continuing with summary-only
  evidence packs or storing full article text.
- [x] Real tradeoff: plausible alternatives include keeping thin evidence
  packs, storing full text, fetching source text only at verification time, or
  using LLM-generated quote anchors.

## ADR-0010 Admission Gate Result

This decision is admitted as scoped AI Radar work because it passes the current
author-side admission gate:

- Real pain already encountered: the local claim-origin support report found
  `records=35`, `claims=175`, `quoted=0`, and `source_excerpt_records=0`.
  The report also showed evidence packs with `collector_extracted` summaries
  and structured metadata but no source-text fields. The verification layer had
  no original text to match.
- Replacement, not additive accretion: this policy replaces the implicit
  thin-cache assumption that title, summary, source, and URL are enough evidence
  for quote-anchored verification. It must not become a parallel full-text
  archive. The bounded excerpt field is allowed only as the minimal source-text
  substrate needed for claim-origin checks.
- Six-month regret test: without a stable source-excerpt path, AI Radar's
  verification-aware claim cannot land. Future claim support would remain
  mostly `inferred` even when collectors had access to source text.

The second criterion remains the main risk. This ADR is accepted with a bounded
scope: source excerpts are allowed only as the minimal verification substrate,
not as a general full-text storage layer.

## Context

AI Radar's claim-origin work added deterministic source-span support:
`directly_supported` claims require a match against traceable evidence content,
while token-overlap-only matches remain `inferred`.

The first read-only impact report showed:

```text
records=35 claims=175 quoted=0 inferred=175 token_only_inferred=141
source_excerpt_records=0 full_text_like_records=0 source_text_fields={}
```

A follow-up provenance check narrowed the conclusion. The result did not prove
that AI Radar is inherently a paraphrase-only product. It proved a smaller,
more actionable fact: the current evidence packs are too thin for source-span
verification. They contain summary-level evidence and structured metadata, but
not stable source excerpts.

Current implementation facts:

- `build_signal_evidence_pack` builds evidence items from `title`, `summary`,
  `source`, and `source_url`.
- RSS collection commonly stores feed `summary` / `description`, not full
  article text.
- Some collectors can produce short `content` fields, such as official article
  body snippets, but that source text is not consistently preserved through the
  final signal and evidence-pack path.
- Manual link fetch can retrieve public article text for manual sessions, but
  that is a separate path and does not solve automatic signal evidence packs.

The policy question is therefore not "can AI Radar quote from current cached
records?" It cannot. The policy question is whether future evidence packs
should carry a bounded source excerpt so deterministic quote anchoring has real
source text to inspect.

## Decision

Evidence packs may include a bounded source excerpt when a collector or
upstream signal path has already obtained source text.

The source excerpt is a minimal verification substrate, not a full-text store.

Initial policy:

- Maximum stored source excerpt length: 1200 normalized characters.
- Allowed candidate fields: `source_excerpt`, `full_text`, `article_body`,
  `raw_content`, `raw_text`, and `content`.
- Evidence item semantics:
  - `source_field`: the original field used, such as `content` or
    `source_excerpt`
  - `kind`: `source_excerpt`
  - `provenance`: `source_excerpt`
  - `traceable`: true when content is non-empty
- `summary` must not be silently promoted to `source_excerpt`.
- If `content` is only a duplicate of `summary`, it must not become a source
  excerpt.
- Full article text must not be stored by default.
- Historical records must not be backfilled merely to improve report metrics.
- Source excerpts may support deterministic claim-span matching, but they do
  not by themselves make a source true, sufficient, or action-eligible.

The current local bounded-excerpt patch in
`backend/app/services/evidence_pack_service.py` is ratified as the first
implementation slice under this ADR.

## Owns

- The existence of bounded source excerpts in evidence packs.
- The maximum excerpt length and no-full-text default.
- The rule that summaries cannot borrow the `source_excerpt` label.
- The provenance semantics for source-excerpt evidence items.
- The no-backfill rule for historical signal records.
- The requirement that collector / merge changes remain scoped to preserving a
  bounded excerpt, not creating a source archive.

## Does Not Own

- LLM prompt changes for insight generation.
- Claim extraction phrasing or quote-rate targets.
- Project Takeaway gates, overrides, or downstream action policy.
- Model provenance, which remains governed by ADR-0009.
- External insight intake, which remains governed by ADR-0010.
- A full crawler, readability service, content warehouse, or search index.
- Any AWS write, S3 schema migration, deployment, or CI workflow change.

## Consequences

AI Radar gains a real source-text substrate for deterministic source-span
verification when collectors can provide one.

Claim-origin reports become more meaningful: a `quoted=0` result can be
interpreted against explicit source-text availability instead of being confused
with prompt behavior or product positioning.

The policy intentionally adds a small amount of data to future records. That is
the cost. The boundary is the mitigation: bounded excerpts only, no full-text
default, no historical backfill, and no summary-as-excerpt promotion.

Collector and merge paths will need narrow updates if this ADR is accepted.
Those updates must be proposed with a file list before implementation,
especially if they touch core ingestion files.

## Alternatives Considered

### Alternative 1: Keep Thin Evidence Packs

Rejected if this ADR is accepted. Thin evidence packs are simple, but they leave
deterministic source-span verification without source text. Claim support then
falls back to inferred or unsupported results even when an upstream collector
had enough source material.

### Alternative 2: Store Full Text

Rejected. Full text increases storage, copyright, privacy, and schema surface
area beyond what claim-origin verification needs. AI Radar needs enough source
text to anchor claims, not a source archive.

### Alternative 3: Fetch Source Text Lazily During Verification

Deferred. Lazy fetching avoids storing excerpts, but it makes verification
non-deterministic, network-dependent, and hard to reproduce later when pages
change or disappear.

### Alternative 4: Ask an LLM to Produce Quote Anchors

Rejected as a primary mechanism. LLM-produced quote anchors can be useful as
candidates, but deterministic quote support must be grounded in stored source
text, not generated quotation-like prose.

### Alternative 5: Treat Summary as Source Excerpt

Rejected. This is a borrowed-shell failure: a collector or LLM summary would
borrow the authority of a source excerpt without being original source text.

## Implementation Plan

This ADR does not authorize broad collector or ingestion changes without a
separate file list and implementation confirmation.

First implementation slice:

1. Ratify the current local prototype in
   `backend/app/services/evidence_pack_service.py`.
2. Keep tests proving:
   - bounded excerpts are capped at 1200 characters
   - duplicate `summary` / `content` is not promoted to `source_excerpt`
   - source-excerpt evidence items are traceable and carry explicit provenance
3. Inspect collector and merge paths and propose the exact file list before
   changing them. Likely candidates include:
   - `signal_collectors/official_collector.py`
   - `signal_collectors/merge_signals.py`
   - `app/main_summary_v2.py`
   - backend signal insight / evidence-pack integration tests
4. Preserve source excerpts only when upstream source text exists. Do not add a
   new crawler or article-fetching subsystem in this slice.
5. Rerun the claim-origin support report and record:
   - records with source excerpts
   - quoted / inferred counts
   - evidence provenance counts
   - any remaining thin-cache paths

## Acceptance Notes

Accepted on 2026-05-28 after the author accepted the bounded source-excerpt
direction.

Ratified first slice:

- `backend/app/services/evidence_pack_service.py` may create a bounded
  `source_excerpt` evidence item when upstream signal data already includes
  source-like text.
- `tests/test_evidence_pack_service.py` covers the 1200-character cap and the
  rule that duplicate `summary` / `content` is not promoted to
  `source_excerpt`.
- Existing cached signal records remain unchanged and are not backfilled.
- Collector / merge / ingestion changes remain deferred until their exact file
  list is confirmed before implementation.

## Open Questions

- Is 1200 characters the right initial cap, or should it be lower for RSS and
  official-source records?
- Should collector outputs use a canonical `source_excerpt` field, or should
  evidence-pack building continue to accept several legacy source-text fields?
- Should source excerpts be persisted in final signal snapshots, or only in
  generated evidence packs?
- Which collector paths are allowed to extract source excerpts without
  becoming a crawler or source archive?

## References

- [ADR-0009: Model Provenance Schema](./0009-model-provenance-schema.md)
- [ADR-0010: External Insight Intake Requires Author-Side Admission Gate](./0010-external-insight-admission-gate.md)
- [External Insight Admission Gate Companion Note](../notes/insight-admission-gate.md)
- [CURRENT_DEVELOPMENT_STATUS.md](../../CURRENT_DEVELOPMENT_STATUS.md)
