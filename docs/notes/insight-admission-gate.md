---
title: External Insight Admission Gate
last_updated: 2026-05-28
status: living
related:
  - docs/adr/0010-external-insight-admission-gate.md
tags: [admission-gate, external-insights, governance]
---

# External Insight Admission Gate

This is the mutable companion note for
[ADR-0010](../adr/0010-external-insight-admission-gate.md).

ADR-0010 owns the invariant: external insights are rejected from AI Radar
product scope by default unless they pass an author-side admission gate.

This note owns the current criteria and can evolve with use.

## Scope

Use this gate before turning an external article, paper, lecture, framework, or
conversation into any of the following:

- AI Radar feature work
- architecture change
- agent skill or protocol
- durable project method
- implementation task for Codex or Claude

Do not use this gate to decide whether an idea can enter a private notebook,
writing queue, reading log, or LinkedIn draft. Those destinations remain open
by default.

## Current Criteria v1

An insight may enter AI Radar only if it passes the reverse burden of proof.
The question is not "does this have value?" Most serious insights have value.
The question is "does this belong in AI Radar now?"

### 1. Real Pain Already Encountered

Does the insight map to a concrete pain, incident, recurring failure, or
observed usage gap that AI Radar has already encountered?

If there is no corresponding lived pain or observed system pressure, do not
admit it yet.

### 2. Replacement, Not Additive Accretion

If the insight conflicts with or overlaps something already in the system, what
does it retire, replace, simplify, or make unnecessary?

Do not admit purely additive frameworks that leave the old structure in place
and add another parallel layer.

### 3. Six-Month Regret Test

Six months from now, would excluding this insight from AI Radar likely be a
meaningful product, architecture, or authorship mistake?

If the honest answer is no, keep it in the notebook / insight inbox.

## Decision Outcomes

Use one of these outcomes:

- `admit`: the insight passes the gate and may become scoped AI Radar work.
- `inbox`: the insight is valuable but stays outside product scope for now.
- `reject`: the insight should not shape AI Radar.
- `replace`: the insight may enter only as part of retiring or simplifying an
  existing structure.

## Minimum Record

For admitted insights, record:

- external insight source or short description
- real pain / incident / usage pressure it maps to
- what it replaces or why no replacement is needed
- six-month regret answer
- resulting scope boundary

For `inbox` and `reject`, a short note is enough.

## Use With Agent Work

Before asking an agent to implement external-insight-driven work, state the gate
outcome and the smallest admitted scope.

If the gate has not been run, the default agent response should be to pause and
ask for the admission decision rather than start implementation.

## Revision Notes

- 2026-05-28: v1 created with three criteria: real pain, replacement over
  additive accretion, and six-month regret.
