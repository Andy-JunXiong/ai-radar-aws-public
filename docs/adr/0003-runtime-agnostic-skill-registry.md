---
adr: 0003
title: Runtime-Agnostic Skill Registry
status: Accepted
created: 2026-05-17
layer: L1-engineering-solution
related:
  - L2: AGENTS.md
  - L2: agent-skills/README.md
tags: [agent-skills, runtime-neutral, skills, documentation-architecture]
---

# ADR-0003: Runtime-Agnostic Skill Registry

## ADR Gate

Create this ADR only if all are yes:

- [x] Hard to reverse: once a skill directory is established and skills
  accumulate, migration costs grow with every reference, agent instruction, and
  downstream consumer.
- [x] Context would be lost: future readers would ask why agent collaboration
  protocols live at a vendor-neutral path instead of under a vendor-specific
  loader directory such as `.claude/skills/`.
- [x] Real tradeoff: plausible alternatives include `.claude/skills/`,
  `skills/`, `docs/skills/`, and `protocols/`.

## Context

AI Radar has two different things that can reasonably be called "skills".

The existing product-time skills are AI Radar runtime prompt capabilities. They
are user-facing behaviours managed through the product's prompt registry, such
as reflection polishing or signal grading. These belong to the application
runtime and are governed by product evaluation flow.

The new skills under discussion are different. Examples include
`grill-before-sprint`, `grill-before-absorb`, `incident-response`,
`development-slice`, `context-loader`, and
`project-takeaway-self-check`. These are agent collaboration protocols:
developer-facing process artefacts that tell Codex CLI, Claude Code, and future
maintenance agents how to work on the AI Radar repository.

Storing those protocols under a single vendor's loader directory would make a
runtime-neutral governance layer look vendor-bound. Storing them in a generic
`skills/` directory would blur the boundary between product runtime skills and
agent collaboration protocols. AI Radar needs an explicit location and minimum
format contract before more agent protocols are added.

## Decision

Create a runtime-agnostic agent collaboration protocol registry at:

```text
agent-skills/<name>/SKILL.md
```

This registry is the canonical home for Layer A' agent collaboration protocols:
plain-markdown instructions consumed at development or operations time by LLM
agents working on AI Radar.

Layer A product runtime skills and Layer A' agent protocols remain separate:

| Dimension | Layer A product skills | Layer A' agent protocols |
|---|---|---|
| Time | Product runtime | Development / operations time |
| Audience | AI Radar end users | LLM agents working on AI Radar |
| Invocation | Backend runtime prompt registry | Agent reads markdown when triggered |
| Storage | `@skill_prompt` registry and exported product skill data | `agent-skills/<name>/SKILL.md` |
| Examples | `reflection-polish`, `signal-grading` | `grill-before-sprint`, `incident-response` |

Each Layer A' skill uses plain markdown with YAML frontmatter. The minimum
contract is:

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

`intended_consumers` is design-intent metadata, not runtime enforcement. It
tells humans and reviewing agents which consumers have been considered for a
skill. Loading a skill outside its declared consumers is an out-of-design action
that requires review.

AI Radar's product runtime is not a default Layer A' consumer. A specific agent
protocol may become available to the product runtime only after explicit
per-skill review confirms that doing so does not mix dev/ops procedures with
user-facing product reasoning or violate intelligence-quality boundaries.

## Owns

- The decision that agent collaboration protocols are runtime-agnostic Layer A'
  artefacts.
- The choice of `agent-skills/` as the canonical repository location for those
  protocols.
- The minimum `SKILL.md` format contract for Layer A' protocols.
- The `intended_consumers` metadata semantics.
- The distinction between product runtime skills and agent collaboration
  protocols at the documentation architecture level.
- The default exclusion of AI Radar product runtime from Layer A' consumers.

## Does Not Own

- The content of individual `SKILL.md` files.
- The implementation of the product runtime prompt registry.
- The future extraction plan for any open-source `ai-pm-skills` package.
- Vendor-specific loader integration, such as a Claude Code symlink or pointer.
- Per-skill decisions to opt AI Radar product runtime in as a consumer.
- The AGENTS.md restructuring plan; that is a dependent decision for a later
  ADR.

## Consequences

The registry gives AI Radar one neutral place for agent collaboration protocols.
Codex CLI, Claude Code, and future agents can all discover the same source of
truth through AGENTS.md or direct file references.

The decision prevents product runtime skills from being mixed with dev/ops
agent procedures. That reduces the risk of nonsensical or unsafe behaviour, such
as exposing an incident-response protocol to a user-facing reflection request.

The tradeoff is that vendor-native discovery is not automatic for every runtime.
Claude Code may need an explicit pointer from AGENTS.md or a lightweight
vendor-specific bridge. That bridge is an implementation convenience, not the
source of truth.

## Alternatives Considered

### Alternative 1: `.claude/skills/`

Rejected. Claude Code can discover this path natively, but it binds a
runtime-neutral AI Radar protocol layer to one vendor's loader convention and
makes the skills less visible to Codex CLI by default.

### Alternative 2: `skills/`

Rejected. The name is short, but it collides with the product runtime skill
registry and makes it easier to confuse Layer A product capabilities with Layer
A' agent collaboration protocols.

### Alternative 3: `docs/skills/`

Rejected. This emphasizes documentation but understates that the files are
operational protocols agents are expected to follow when triggered.

### Alternative 4: `protocols/`

Rejected for now. It is precise, but it loses continuity with the team's
existing "skill" vocabulary and may make the relationship to existing skill
drafts less obvious.

## Implementation Status

Accepted on 2026-05-18 after Phase 1 implementation:

- `agent-skills/README.md` describes the Layer A' boundary, minimum
  `SKILL.md` contract, and distinction from product runtime skills.
- `AGENTS.md` includes a skill registry section pointing agents to
  `agent-skills/`.
- Phase 1 agent collaboration protocols now exist under
  `agent-skills/<name>/SKILL.md`:
  - `agent-skills/development-slice/SKILL.md`
  - `agent-skills/incident-response/SKILL.md`
- New Layer A' skills remain outside AI Radar product runtime unless a separate
  per-skill review explicitly opts them in.

The cross-ADR dependency is intentionally satisfied through ADR-0004 Phase 1:
ADR-0003 owns the skill location and format, while ADR-0004 owns discovery
through AGENTS.md. ADR-0004 remains `Proposed` while its broader restructuring
and observation period continue.

## References

- [AGENTS.md](../../AGENTS.md)
- [ADR README](./README.md)
- [ADR template](./TEMPLATE.md)
- Documentation architecture source: `docs/documentation-architecture.md`
  (preserved as `documentation-architecture-v3.md` during drafting)
