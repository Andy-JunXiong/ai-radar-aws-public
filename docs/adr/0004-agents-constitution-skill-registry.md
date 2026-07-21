---
adr: 0004
title: AGENTS.md Constitution and Skill Registry
status: Proposed
created: 2026-05-17
layer: L1-engineering-solution
related:
  - L1: docs/adr/0003-runtime-agnostic-skill-registry.md
  - L2: AGENTS.md
  - L2: agent-skills/README.md
tags: [agents-md, agent-skills, operating-guidance, documentation-architecture]
---

# ADR-0004: AGENTS.md Constitution and Skill Registry

## ADR Gate

Create this ADR only if all are yes:

- [x] Hard to reverse: once sections are extracted from AGENTS.md into skill
  files, agent invocations begin depending on the skill registry and reversing
  the decision requires re-inlining content and rewriting references.
- [x] Context would be lost: future readers would ask why AGENTS.md is shorter
  than before and why substantial operating procedures live in separate skill
  files.
- [x] Real tradeoff: plausible options include leaving AGENTS.md as a single
  long file, extracting only new gate skills, or restructuring it into
  constitution plus routing plus skill registry.

## Context

AGENTS.md currently mixes several kinds of L2 operating guidance:

- constitution-level rules that must always be loaded, such as non-negotiable
  security boundaries, commit/push/deploy restrictions, worktree safety, and the
  trust hierarchy
- routing guidance that helps agents decide which context files to inspect
- long conditional workflows, such as Development Slice Lifecycle and Incident
  Response Flow, that apply only in specific situations
- specialised self-checks, such as the Project Takeaway verification checklist,
  that should run only when a change touches a matching area

This makes AGENTS.md large and causes conditional workflows to be loaded on
every agent task, including tasks where they are irrelevant. At the same time,
over-extracting would be risky: core boundaries must remain visible even if a
skill fails to trigger.

This ADR decides how AGENTS.md should use the runtime-agnostic skill registry.

## Dependencies

- [per ADR-0003, assumed: `agent-skills/` directory chosen]
- [per ADR-0003, assumed: Layer A' skill files use
  `agent-skills/<name>/SKILL.md`]

## Decision

Restructure AGENTS.md into a constitution plus routing plus skill registry.

AGENTS.md should retain:

- repository identity and scope
- non-negotiable rules
- main narrow-change rule
- operating mode names and mode declaration requirement
- execution context distinctions
- core-file approval gate
- sensitive-data and system operation boundaries
- worktree safety
- intelligence-quality invariants
- security model and trust hierarchy
- compact routing tables for key context files and skills

AGENTS.md should delegate long conditional workflows to
`agent-skills/<name>/SKILL.md` files. The skill registry section in AGENTS.md
is the cross-runtime discovery mechanism: agents that read AGENTS.md can locate
the right skill file when a trigger applies.

Implement the restructuring in two phases:

1. Phase 1: extract the largest and clearest conditional workflows:
   `incident-response` and `development-slice`. Add the skill registry section
   to AGENTS.md and keep mini routing tables in AGENTS.md as fallback context.
2. Phase 2: after a two-week observation period, extract `context-loader` and
   `project-takeaway-self-check` if the Phase 1 pattern works. Delete the stale
   Future Refactoring Note only during this phase.

The observation period exists to verify that skill triggers are discoverable in
real use before extracting more subtle routing and self-check content.

## Owns

- The decision that AGENTS.md should become constitution plus routing plus skill
  registry, not a single long SOP file.
- The decision to keep hard boundaries and compact routing tables in AGENTS.md.
- The phased migration plan for extracting conditional workflows.
- The decision that `incident-response` and `development-slice` are Phase 1
  extraction targets.
- The decision that `context-loader` and `project-takeaway-self-check` are
  Phase 2 candidates after observation.

## Does Not Own

- The canonical skill location; that is owned by ADR-0003.
- The content of individual skill files.
- The dual-gate pre-sprint protocol; that is owned by ADR-0005.
- Any change to non-negotiable security boundaries or intelligence-quality
  invariants.
- The runtime implementation of any vendor-specific skill loader.

## Consequences

AGENTS.md becomes smaller and more readable while preserving the rules that
must remain always visible. Agents should spend less context on irrelevant
conditional workflows during ordinary tasks.

The main risk is under-triggering: a conditional workflow might not be loaded
when it should be. Keeping a compact skill registry and mini routing tables in
AGENTS.md mitigates this by leaving trigger names and file paths always visible.

The two-phase migration reduces blast radius. If Phase 1 causes confusion, the
project can pause before extracting subtler workflows.

## Alternatives Considered

### Alternative 1: Leave AGENTS.md as one long file

Rejected. This maximizes always-loaded safety but keeps every conditional SOP in
context for every task and makes future maintenance harder.

### Alternative 2: Extract only the new gate skills

Rejected. This avoids touching existing AGENTS.md structure but leaves the
largest source of token and readability cost unresolved: Development Slice
Lifecycle and Incident Response Flow.

### Alternative 3: Extract every conditional section in one sprint

Rejected. A single broad extraction would touch too many rules at once and make
it harder to tell whether later agent behaviour changes came from the registry
pattern or from a specific extracted workflow.

## Implementation Plan

1. Wait for human approval to proceed with this ADR's implementation.
2. Once the `agent-skills/` directory exists per ADR-0003's implementation,
   which runs ahead of this ADR's Phase 1, proceed with AGENTS.md discovery
   changes.
3. Phase 1:
   - create `agent-skills/incident-response/SKILL.md`
   - create `agent-skills/development-slice/SKILL.md`
   - add a skill registry section to AGENTS.md
   - replace the extracted AGENTS.md sections with compact pointers
4. Replace draft dependency markers with plain references once ADR-0003's
   decision text is stable and before marking this ADR `Accepted`.
5. Observe agent triggering behaviour for two weeks.
6. Phase 2:
   - create `agent-skills/context-loader/SKILL.md` if Phase 1 is working
   - create `agent-skills/project-takeaway-self-check/SKILL.md` if Phase 1 is
     working
   - delete the stale Future Refactoring Note from AGENTS.md
7. After Phase 2 is implemented and validated, mark this ADR `Accepted`.

The deployment runbook filename hygiene task is intentionally out of scope for
this ADR and should remain a separate docs hygiene change.

## References

- [AGENTS.md](../../AGENTS.md)
- [ADR-0003: Runtime-Agnostic Skill Registry](./0003-runtime-agnostic-skill-registry.md)
- Documentation architecture source: `docs/documentation-architecture.md`
  (preserved as `documentation-architecture-v3.md` during drafting)
