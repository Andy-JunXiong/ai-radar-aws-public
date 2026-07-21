---
adr: 0005
title: Dual-Gate Pre-Sprint Protocol
status: Proposed
created: 2026-05-17
layer: L1-engineering-solution
related:
  - L1: docs/adr/0003-runtime-agnostic-skill-registry.md
  - L1: docs/adr/0004-agents-constitution-skill-registry.md
  - L2: agent-skills/grill-before-sprint/SKILL.md
  - L2: agent-skills/grill-before-absorb/SKILL.md
  - L2: docs/cognitive-log/README.md
tags: [agent-skills, sprint-gate, cognitive-sovereignty, documentation-architecture]
---

# ADR-0005: Dual-Gate Pre-Sprint Protocol

## ADR Gate

Create this ADR only if all are yes:

- [x] Hard to reverse: once dual-gate review becomes the default sprint
  authorisation protocol, human review habits, agent expectations, and audit
  artefacts reshape around it.
- [x] Context would be lost: future readers would ask why AI Radar has separate
  project-axis and cognitive-axis gates instead of one combined planning gate.
- [x] Real tradeoff: plausible options include keeping only a project-axis gate,
  folding cognitive questions into that gate, or introducing a separate
  cognitive-axis gate that runs in parallel.

## Context

AI Radar increasingly uses LLM agents to plan and implement work. That speed
creates two different risks:

1. The project may do technically plausible work that does not actually close a
   meaningful AI Radar gap.
2. Andy may approve or absorb a concept that is useful but not yet owned deeply
   enough to explain, maintain, or defend without re-querying an LLM.

These risks are related but not identical. The first is a project-axis question:
should AI Radar do this? The second is a cognitive-axis question: can Andy own
this?

Combining both questions into one gate would make the protocol harder to reason
about and would blur the distinction between project value and human ownership.
Keeping only the project-axis gate would miss the specific failure mode where
AI-assisted work grows faster than Andy's cognitive footprint.

## Dependencies

- [per ADR-0003, assumed: `agent-skills/` directory chosen]
- [per ADR-0004, assumed: skill registry section in AGENTS.md exists]

## Decision

Adopt a dual-gate pre-sprint protocol:

- `grill-before-sprint` is the project-axis gate. It asks whether AI Radar
  should do the proposed work.
- `grill-before-absorb` is the cognitive-axis gate. It asks whether Andy can
  own the concept or decision well enough to proceed.

Both gates run after a planning conversation has produced a concrete proposal
and before Codex CLI or another coding agent is authorised to execute a
meaningful sprint.

The gates are independent:

- passing `grill-before-sprint` does not imply passing `grill-before-absorb`
- passing `grill-before-absorb` does not imply the project should do the work
- if the project-axis gate passes but the cognitive-axis gate fails, the work is
  paused for digestion rather than abandoned

Records:

- `grill-before-sprint` outputs are recorded in the sprint brief or future
  sprint-contract artefact.
- `grill-before-absorb` outputs are recorded in
  `docs/cognitive-log/YYYY-MM-DD-*.md`.

Both gate skills start with:

```yaml
status: experimental
intended_consumers:
  - codex-cli
  - claude-code
```

The experimental period lasts four weeks. After that, the project should decide
whether to promote the gates to mandatory, revise their scope, or keep them
experimental longer.

## Owns

- The decision to introduce a cognitive-axis gate alongside the project-axis
  sprint gate.
- The independence rule between the two gates.
- The rule that project-axis pass plus cognitive-axis fail means pause and
  digest before sprinting.
- The use of `docs/cognitive-log/` as the absorption audit trail.
- The four-week experimental period before possible promotion to mandatory.

## Does Not Own

- The exact five questions inside each gate skill.
- The canonical skill location; that is owned by ADR-0003.
- The AGENTS.md skill registry structure; that is owned by ADR-0004.
- The cognitive WIP limit as a hard-enforced mechanism.
- Any automation for enforcing cognitive WIP limits.
- Whether or how cognitive-log entries are later published as L3 narratives.

## Consequences

The dual-gate protocol makes it harder for AI Radar to mistake agent speed for
project readiness or human ownership. A sprint can be valuable but not yet
digestible; the process now has a formal way to say "pause and digest" without
discarding the proposal.

The protocol adds friction. Some proposed work will take longer to reach
implementation because Andy must articulate ownership before delegating. This is
an intentional cost for meaningful features, architectural decisions, new
skills, and other work that affects future maintainability or public narrative.

The experimental period limits risk. If the protocol proves too heavy or
under-triggered, it can be revised before becoming mandatory.

## Alternatives Considered

### Alternative 1: Keep only the project-axis gate

Rejected. This can prevent low-value sprints, but it does not address the
distinct risk that Andy approves concepts he cannot yet defend or maintain.

### Alternative 2: Add cognitive questions to the project-axis gate

Rejected. This keeps one checklist but mixes two different decisions. The
project can be ready while Andy is not, or Andy can understand an idea that the
project should still reject.

### Alternative 3: Make both gates mandatory immediately

Rejected for now. The protocol is promising but should be observed in real
development before becoming mandatory.

## Implementation Plan

1. Wait for human approval to proceed with this ADR's implementation.
2. Implement ADR-0003 and ADR-0004 enough for `agent-skills/` and the AGENTS.md
   skill registry to exist.
3. Create `agent-skills/grill-before-sprint/SKILL.md` with experimental status.
4. Create `agent-skills/grill-before-absorb/SKILL.md` with experimental status.
5. Create `docs/cognitive-log/README.md` for absorb-gate outputs.
6. Use the gates during real planning for four weeks.
7. Replace draft dependency markers with plain references once ADR-0003 and
   ADR-0004 decision text is stable and before marking this ADR `Accepted`.
8. Re-evaluate whether to promote the gates to mandatory, revise them, or keep
   them experimental.
9. Mark this ADR `Accepted` only after the four-week experimental period and at
   least three sprint decisions have been run through both gates.

## References

- [ADR-0003: Runtime-Agnostic Skill Registry](./0003-runtime-agnostic-skill-registry.md)
- [ADR-0004: AGENTS.md Constitution and Skill Registry](./0004-agents-constitution-skill-registry.md)
- Documentation architecture source: `docs/documentation-architecture.md`
  (preserved as `documentation-architecture-v3.md` during drafting)
