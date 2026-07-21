---
adr: 0010
title: External Insight Intake Requires Author-Side Admission Gate
status: Accepted
created: 2026-05-28
accepted: 2026-05-28
layer: L1-governance-decision
related:
  - L2: docs/notes/insight-admission-gate.md
  - L2: AGENTS.md
tags: [governance, admission-gate, authorial-stance, external-insights]
---

# ADR-0010: External Insight Intake Requires Author-Side Admission Gate

## ADR Gate

Create this ADR only if all are yes:

- [x] Hard to reverse: once external frameworks start entering AI Radar as
  features, architecture, or agent protocols, removing them later has product
  and narrative cost.
- [x] Context would be lost: future readers would ask why the project rejects
  useful external insights by default instead of continuously absorbing them.
- [x] Real tradeoff: plausible alternatives include evaluating each insight
  case-by-case, queueing insights for later alerts, or keeping the rule as a
  private habit outside the repository.

## Context

AI Radar already applies admission discipline to system information. Evidence
sufficiency, verification metadata, and `blocked_downstream_actions` decide
which outputs can support downstream action. The system has gates for what can
enter a trusted action path.

The author-side design workflow did not have the same gate. A recurring pattern
was to read an external article, paper, lecture, or framework, extract a strong
insight, and immediately ask whether it should be added to AI Radar. Evaluating
each insight individually made the default disposition drift toward inclusion.

That creates two risks:

1. Functional weight: the product and architecture surface can grow faster than
   observed usage or incidents justify.
2. Loss of authorship: AI Radar's value depends on a clear point of view about
   human-led problem definition, verification-aware synthesis, and cognitive
   sovereignty. Absorbing every elegant external framework can turn that stance
   into a collage.

The deciding observation is self-referential: indiscriminate author-side
absorption is the kind of failure AI Radar's internal verification architecture
is designed to prevent. This ADR extends the admission principle one level up:
from signals entering the system to design decisions entering the system's
authorial boundary.

This ADR locks the existence of the gate. The gate criteria are mutable and
live in the companion note.

## Decision

External insight intake is rejection-by-default.

The default destination of any external insight is the author's notebook or
insight inbox, not AI Radar product scope.

Admission into AI Radar as a feature, architecture change, agent skill,
workflow, or durable project method requires an explicit author-side admission
gate before implementation work begins. The gate is not bypassed because an
insight is elegant, current, prestigious, or personally exciting.

The gate's existence is an invariant and is effective immediately. The exact
criteria and wording are versioned as living guidance in
[docs/notes/insight-admission-gate.md](../notes/insight-admission-gate.md).

## Owns

- The rejection-by-default rule for external-insight intake.
- The requirement that external insights pass an author-side admission gate
  before becoming AI Radar product, architecture, skill, or agent-protocol work.
- The default routing of unadmitted insights to notebook / insight inbox space.
- The distinction between the gate's fixed existence and its tunable criteria.

## Does Not Own

- Product runtime signal ingestion or internal evidence sufficiency.
- Project Takeaway verification gates, override paths, or
  `blocked_downstream_actions` behavior.
- Claim-origin enforcement or source-span verification, which are separate
  implementation concerns.
- The exact wording of admission criteria, which belongs to the companion note.
- Writing, publishing, learning, or discarding external insights outside AI
  Radar product scope.

## Consequences

AI Radar should stay leaner and keep a clearer authorial stance.

Most external insights will remain useful as writing material, notebook
material, or future context without entering the product. This is intentional.
The notebook can preserve intellectual history; AI Radar remains the authored
system being built from selected decisions.

The gate adds friction before implementation. That friction is the point: it
turns "this is valuable" into the harder question "this belongs in AI Radar
now."

A new failure mode exists: if this ADR is accepted but future work routinely
bypasses the author-side gate, the ADR becomes a governance-layer analogue of a
bypassed verification gate. The gate is real only when it is allowed to reject.

## Alternatives Considered

### Alert or Scheduled-Trigger Model

Rejected as the primary mechanism. Alerts assume an insight eventually belongs
in the system and merely defer timing. That treats the symptom, not the default
inclusion bias. Alerts may be useful only after an insight has already passed
the admission gate.

### Case-by-Case Evaluation

Rejected. Case-by-case evaluation with an inclusion-leaning default is not a
gate. It preserves the behavior that created the concern.

### Private Habit Outside the Repository

Rejected. This decision affects whether agents are allowed to begin product or
architecture work from external insights. It needs to be visible to future
AI-assisted development sessions.

### Defer ADR Until Criteria Are Proven

Rejected. The gate's existence is the invariant. The criteria are deliberately
kept in a living note so they can be tuned without reopening the ADR.

## Implementation Plan

1. Create the companion criteria note and treat it as the current gate checklist.
2. Before any future external-insight-driven feature, architecture, skill, or
   agent-protocol work begins, run the companion checklist.
3. If an insight does not pass, route it to notebook / insight inbox space and
   do not start implementation.
4. Adjust the companion criteria after real use, without changing this ADR
   unless the existence or authority of the gate changes.

## Acceptance Notes

Accepted on 2026-05-28 because the decision is about the existence of a gate,
not the final wording of the gate criteria.

The accepted invariant:

- external insights default to rejection from AI Radar product scope
- admission requires an explicit author-side gate
- gate criteria can evolve in the companion note

## Implementation Notes

2026-05-29:

- A CCG / AI Radar invariant-enforcement review passed the author-side
  admission gate in modified form.
- The accepted implementation slice did not import CCG prompt structure or add
  a runtime injection harness.
- The slice implemented a Project Takeaway typed candidate envelope / builder
  so candidate construction flows through source-specific policy before the
  write path:
  - `backend/app/services/project_takeaway_candidate_policy.py`
  - `backend/app/routes/projects.py`
- The implementation preserved the existing multi-source Project Takeaway
  boundary: `verified_insight`, `knowledge_convergence`,
  `unverified_manual_entry`, and `manual_project_takeaway_override`.
- ADR-0011 was not directly triggered by this slice because no source excerpt,
  claim-origin, or evidence-flow storage behavior changed.
- A process correction was also added to require ADR / core-doc trigger
  preflight before future ADR-owned invariant implementation slices.

## References

- [External Insight Admission Gate Companion Note](../notes/insight-admission-gate.md)
- [AGENTS.md](../../AGENTS.md)
