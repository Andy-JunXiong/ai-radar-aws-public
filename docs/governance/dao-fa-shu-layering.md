# Dao / Fa / Shu Layer Classification

Date: 2026-05-30
Status: lightweight review vocabulary
Scope: architecture and development review classification

## Purpose

Dao / Fa / Shu is a small classification tool for deciding how heavy a change
is before implementation. It is not a directory layout, CI rule, or runtime
schema by default.

Use it when a proposed change touches AI Radar's intent, methodology, tool
choices, verification spine, Project Takeaway gates, agent protocols, or model
execution boundaries.

## Layers

### Dao: Intent Invariants

Dao is the project's non-negotiable reason for existing and the cognitive
principles that make AI Radar itself.

Examples:

- epistemic honesty
- verified-before-action
- human-owned decision authority
- Reflection is cognitive context, not factual evidence
- Project Takeaway gates cannot be bypassed by ordinary flows

Changing Dao usually means changing the project. Treat Dao changes as requiring
ADR/core-doc preflight before implementation.

### Fa: Methodology

Fa is how AI Radar implements Dao.

Examples:

- verification spine
- claim extraction and claim support classification
- evidence pack and bounded source excerpt policy
- Project Takeaway candidate policy
- three-layer agent-skill architecture
- Operator Guidance contract rules

Fa may evolve, but it needs explicit rationale, focused validation, and often
ADR or invariant review.

### Shu: Tooling

Shu is the current technical implementation choice.

Examples:

- FastAPI route organization
- Pydantic or plain dict validation choices
- OpenAI, Anthropic, or other model provider choices
- storage client details
- import-linter, tach, or custom boundary checker

Shu should be replaceable. It usually needs tests and status/changelog tracking,
not ADR. If a Shu choice starts constraining Fa, pause and classify the change
again.

## Classification Questions

Ask these before meaningful architecture or workflow changes:

1. Does this change what AI Radar is allowed to believe, claim, or act on?
   - likely Dao
2. Does this change how evidence, verification, reflection, guidance, or review
   decisions are produced?
   - likely Fa
3. Does this only change a specific library, model, storage path, or execution
   mechanism while preserving behavior?
   - likely Shu
4. Is a tool limitation forcing a change in verification or review semantics?
   - Shu may be contaminating Fa

## Immediate Use

For now, this is a review vocabulary:

- classify the proposed change
- state whether ADR/core-doc preflight is needed
- identify whether work can proceed under current approval
- record deferred triggers in `docs/coordination/trigger-watchlist.md`

## Deferred Work

Do not introduce directory restructuring, import-linter, tach, or CI enforcement
until at least one of these conditions is true:

- repeated boundary failures show the vocabulary is not enough
- provider/tooling imports leak into verification or evidence methodology
- the user explicitly approves an architecture-boundary enforcement slice
- a planned migration window exists
