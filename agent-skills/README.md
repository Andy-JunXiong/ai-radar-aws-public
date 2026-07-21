# AI Radar Agent Skills

This directory is the runtime-agnostic registry for AI Radar agent
collaboration protocols.

Agent skills are development-time and operations-time instructions for coding
agents that work on this repository. They are not AI Radar product runtime
skills, and they are not user-facing prompt capabilities.

## Boundary

AI Radar uses two separate skill concepts:

| Layer | Purpose | Audience | Location |
|---|---|---|---|
| Layer A product skills | Product runtime prompt capabilities | AI Radar users and backend services | Backend prompt registry and exported product skill data |
| Layer A' agent skills | Development / operations collaboration protocols | Codex CLI, Claude Code, and future repo-maintenance agents | `agent-skills/<name>/SKILL.md` |

Layer A' skills must not be loaded into AI Radar product runtime by default.
Making an agent skill available to product runtime requires an explicit
per-skill review.

## Directory Contract

Each agent skill lives at:

```text
agent-skills/<name>/SKILL.md
```

`<name>` should be kebab-case and stable once referenced.

Each `SKILL.md` should start with YAML frontmatter:

```yaml
---
name: <kebab-case-name>
description: |
  <Single paragraph describing what the skill does and when it should trigger.>
status: experimental | mandatory | deprecated
intended_consumers:
  - codex-cli
  - claude-code
---
```

`intended_consumers` records design intent. It is not runtime enforcement. If an
agent or product path wants to consume a skill outside its declared consumers,
that use needs review.

## Current Skills

- `development-slice`: meaningful Development Mode planning, implementation,
  validation, and handoff.
- `incident-response`: alerts, production errors, failing CI, smoke-test
  failures, and operational incidents.
- `grill-before-sprint`: experimental project-axis gate for concrete sprint
  proposals before meaningful implementation.
- `grill-before-absorb`: experimental cognitive-axis gate for concepts or
  decisions that need human ownership before adoption.
- `grill-after-validation`: experimental framing-level gate for external
  validation events connected to existing AI Radar design choices.
- `context-first-review`: experimental repo-grounded review protocol for
  architecture, migration, prompt, or external-analysis briefs that make claims
  about the current repository.
- `grill-the-inference`: experimental Layer A' review protocol for testing
  whether a load-bearing claim set sufficiently supports an insight conclusion,
  without turning counter-conclusions into source evidence or runtime gates.
- `action-loop-stagnation`: experimental Layer A' protocol for interrupting
  repeated action-loop failure, forcing structurally different next hypotheses,
  and requiring a verification oracle when one exists.
- `reconcile-invariants`: experimental scoped closeout protocol for proposing
  invariant-alignment diffs across AGENTS.md, ADR metadata, and the agent-skill
  registry without automatic core-file edits or repo-wide scans.
- `incident-attribution`: experimental process-learning protocol for
  collaboration failures that need factual capture, reviewable attribution, or
  recurring-pattern analysis.
- `credibility-audit`: experimental external-content review protocol that
  separates value from provenance, checks load-bearing facts, and names
  canonical or specimen distortion patterns before external material is trusted
  or absorbed.

## Current Implementation Phase

This registry is introduced by ADR-0003 as the canonical home for Layer A'
agent protocols.

ADR-0004 Phase 1 introduced AGENTS.md discovery and the initial extracted
`development-slice` and `incident-response` skills.

ADR-0005 Phase 1 introduces the experimental dual-gate skills and the
`docs/cognitive-log/` home for absorption records. ADR-0005 remains `Proposed`
until its experimental-period requirements are met.

ADR-0007 introduces the experimental `incident-attribution` skill and the
`incidents/` home for raw incident records, attributed closeouts, and pattern
reviews.

MADR-0001 introduces the experimental `grill-after-validation` skill and the
`docs/cognitive-log/validation/` home for validation-event records.

The `context-first-review` skill was added after a brief-review incident where
stale paths and over-tight Project Takeaway assumptions were caught only after
repo inspection. It keeps future reviews grounded in path discovery and current
boundary discovery before rewrite.

The `grill-the-inference` skill was added as a Layer A' protocol after
ADR-0015 recognized a claim-set composition / underdetermination gap in the
verification spine. It remains agent-only process evidence and calibration
machinery; it is not a product runtime gate.

ADR-0016 introduces the experimental `action-loop-stagnation` and
`reconcile-invariants` skills, plus the shared counter-conclusion reference at
`agent-skills/_shared/references/counter-conclusion.md`. The action-loop
protocol is agent-only and does not connect to runtime hooks, Project Takeaway,
Action eligibility, or `blocked_downstream_actions`.

The `credibility-audit` skill was added as a repo-internal Layer A' incubation
skill after external skill-repo and social-card reviews showed recurring need
for value/provenance separation, primary-source checks, and promotion-layer
distortion labeling. It is not a Layer C distributable package, not installed
outside the repo by default, and not product runtime.

Do not move AGENTS.md rules into this directory unless the specific extraction
has been approved.

## Related Decisions

- `docs/adr/0003-runtime-agnostic-skill-registry.md`
- `docs/adr/0004-agents-constitution-skill-registry.md`
- `docs/adr/0005-dual-gate-pre-sprint-protocol.md`
- `docs/adr/0007-incident-attribution-skill.md`
- `docs/adr/0015-claim-set-composition-underdetermination-gate.md`
- `docs/adr/0016-action-loop-stagnation-protocol.md`
- `docs/meta-adr/MADR-0001-validation-triggers-framing-grill.md`
