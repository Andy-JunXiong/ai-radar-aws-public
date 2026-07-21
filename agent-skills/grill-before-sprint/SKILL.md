---
name: grill-before-sprint
description: |
  Use after a planning conversation has produced a concrete AI Radar sprint proposal and before meaningful implementation begins, especially for feature work, architecture changes, new agent protocols, or cross-module development that could consume substantial effort.
status: experimental
intended_consumers:
  - codex-cli
  - claude-code
---

# Grill Before Sprint

Use this protocol as the project-axis gate for meaningful AI Radar sprint
proposals. It asks whether the project should do the work now.

This gate is independent from `grill-before-absorb`. A sprint can pass this
project-axis gate while still needing cognitive digestion before implementation.

Keep AGENTS.md hard boundaries, worktree safety, core-file approval gates,
security rules, and intelligence-quality invariants in force.

## Trigger

Run this gate after the user and agent have enough context to describe a
specific proposal, and before implementation starts, when the proposal is one
or more of:

- a meaningful product slice
- an architecture or ADR-driven change
- a new agent collaboration protocol
- a cross-module refactor or workflow change
- a task that could create long-lived maintenance obligations

Do not run this gate for trivial typo fixes, narrowly scoped bug fixes,
mechanical test additions, or direct user-approved implementation steps that
already have a clear contract.

## Inputs

Start from a short proposal with:

- goal
- non-goals
- smallest relevant scope
- files or modules likely to change
- expected validation
- known risks or tradeoffs

If those inputs are missing, ask for or draft them before running the gate.

## Five Questions

Answer these before authorising implementation:

1. What concrete AI Radar gap does this close?
2. Why should this happen now instead of staying in backlog or observation?
3. What is the smallest useful slice that proves the direction?
4. What could this accidentally mix, weaken, or make harder to maintain?
5. What validation would prove the slice worked without relying on vibes?

Keep answers short and decision-oriented. The goal is not a long essay; it is a
clear go / pause / narrow decision.

## Outcomes

Choose exactly one:

- `go`: the proposal is worth implementing now at the stated scope
- `narrow`: the proposal is directionally good but must be reduced before work
- `pause`: the proposal should not start yet

If the outcome is `go` or `narrow`, produce the implementation contract:

- final goal
- non-goals
- changed files or ownership area
- validation commands or manual checks
- definition of done

If the outcome is `pause`, state the missing condition or evidence needed to
resume.

## Record

Record the gate result in the sprint brief, task handoff, or status update when
the slice is completed. Do not create a separate cognitive-log entry for this
project-axis gate unless the same conversation also runs `grill-before-absorb`.
