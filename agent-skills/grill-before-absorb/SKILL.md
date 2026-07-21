---
name: grill-before-absorb
description: |
  Use after a concrete AI Radar concept, decision, or sprint proposal has emerged and before it is treated as cognitively owned, especially for ideas Andy may need to explain, maintain, defend, publish, or use as future project judgment.
status: experimental
intended_consumers:
  - codex-cli
  - claude-code
---

# Grill Before Absorb

Use this protocol as the cognitive-axis gate for meaningful AI Radar concepts
or sprint proposals. It asks whether Andy can own the idea well enough to
proceed without outsourcing the whole judgment back to an LLM.

This gate is independent from `grill-before-sprint`. A proposal can be valuable
for AI Radar while still needing pause-and-digest time before implementation.

Keep AGENTS.md hard boundaries, worktree safety, core-file approval gates,
security rules, and intelligence-quality invariants in force.

## Trigger

Run this gate when a concept, decision, or proposed sprint would become part of
Andy's durable project judgment, especially when it affects:

- an ADR or architecture decision
- AI Radar's public narrative or methodology
- a new agent collaboration protocol
- future maintenance expectations
- cognitive ownership of a concept introduced or sharpened by an LLM

Do not run this gate for routine implementation details, small UI polish,
ordinary bug fixes, or decisions Andy does not need to later explain or defend.

## Inputs

Start from a concrete concept or decision with:

- the claim or proposal in plain language
- why it matters
- what would change if it is accepted
- what Andy would need to explain later
- open doubts or terms that still feel fuzzy

If the concept cannot be stated plainly yet, pause before evaluating it.

## Five Questions

Answer these before treating the concept as absorbed:

1. Can Andy explain the idea without repeating the agent's wording?
2. What part of the idea feels genuinely owned, and what still feels borrowed?
3. What would Andy say to a skeptical reviewer who thinks this is unnecessary?
4. What concrete future decision would this concept help make?
5. What should be paused, rewritten, or tested before this becomes durable?

Keep the answers candid. A failed absorption gate is not a rejection; it means
the work needs digestion before it becomes a sprint, ADR, or durable method.

## Outcomes

Choose exactly one:

- `absorbed`: Andy can explain and use the concept well enough to proceed
- `partial`: the concept is promising, but a smaller or clearer version should
  be used for now
- `digest`: pause implementation or formal adoption until the unclear parts are
  worked through

If the outcome is `absorbed` or `partial`, state what is safe to proceed with.

If the outcome is `digest`, state the specific confusion, missing example, or
rewording needed before resuming.

## ADR Follow-Up Rule

When this gate leads to creating or materially changing an ADR, do not stop at
the ADR file.

After the ADR is drafted, explicitly check whether the ADR creates a follow-up
work item. Treat a follow-up as present when any of these are true:

- the ADR status is `Proposed`
- the ADR has an `Implementation Plan`
- the ADR names a next stage, milestone, gap report, validation step, or open
  question that should affect near-term work
- the ADR outcome is `partial`, meaning only a smaller or staged version is
  safe to proceed with

If a follow-up exists, tell Andy which milestone or status document should carry
the reminder. Prefer `CURRENT_DEVELOPMENT_STATUS.md` for next-session work
queue updates. Use `DEVELOPMENT_PLAN.md` only when the top-level development
plan changes.

Respect the core-file approval gate before editing either status document. If
approval is not present, explicitly ask whether to update the specific file.

In the final handoff, state:

- the absorption outcome
- whether an ADR was created or changed
- the next concrete milestone implied by the ADR
- whether that milestone has been recorded in status/planning docs or still
  needs approval

## Record

Record absorption outputs under:

```text
docs/cognitive-log/YYYY-MM-DD-<short-topic>.md
```

Use the cognitive-log README for the entry shape. Keep entries short,
first-person, and honest about uncertainty. Do not use the cognitive log as a
runtime evidence source for external claims.
