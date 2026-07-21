---
name: development-slice
description: |
  Use when Codex is planning, implementing, validating, or handing off a meaningful AI Radar development slice, especially new product direction, changed priority, ambiguous feature work, or any non-trivial backend/frontend/docs slice that needs matched implementation and business-logic validation.
status: experimental
intended_consumers:
  - codex-cli
  - claude-code
---

# Development Slice

Use this protocol in Development Mode for meaningful implementation work. Keep
AGENTS.md hard boundaries, worktree safety, core-file approval gates, and
security rules in force.

## Planning Gate

Do not jump from broad product direction straight into implementation.

Before starting meaningful implementation from a new product direction or
changed priority:

1. Read the relevant planning/context docs.
2. Extract proposed work from:
   - `DEVELOPMENT_PLAN.md`
   - `CURRENT_DEVELOPMENT_STATUS.md`
   - `AI_RADAR_PRODUCT_SPEC.md`
   - `AI_CONTEXT.md` when architecture context matters
3. Show the proposed plan to the user.
4. Wait for confirmation that the plan is correct.
5. Only then implement.

This gate does not apply to a clearly scoped bug fix, typo fix, small test
addition, or narrow implementation task already approved by the user.

## ADR / Core-Doc Trigger Preflight

Before reviewing, recommending, or implementing a proposal derived from an
external framework, product, article, paper, lecture, advisor brief, or other
outside source, check whether ADR-0010 is triggered. If the idea may enter AI
Radar as a feature, architecture change, workflow, skill, agent protocol, or
implementation task, explicitly run the ADR-0010 admission gate before
recommending implementation or treating user agreement as scope approval.
State the outcome (`admit`, `replace`, `inbox`, or `reject`) and the smallest
admitted scope. If the idea is admitted only in modified form, record that
under the admitted scope instead of inventing a new outcome.

Before implementing a slice that touches accepted or proposed ADR work,
`docs/adr/INVARIANTS.md`, Project Takeaway gates, verification metadata,
source evidence flow, lifecycle enforcement, or other ADR-owned invariants,
state the preflight explicitly:

1. which ADR, invariant section, or core-doc boundary is triggered
2. whether the requested code work can proceed under the user's current
   approval
3. which core docs or status files would need separate approval before editing
4. which related ADRs or invariant sections are not directly triggered

If the trigger is discovered after investigation rather than at task start,
pause before editing files and give the same preflight before continuing. Do
not wait until final handoff to tell the user that an ADR or core-doc boundary
was triggered.

## Slice Contract

Frame each implementation slice with:

- goal
- non-goals
- key objects or schema involved
- relevant files or modules to inspect
- backend/API requirements
- frontend requirements when applicable
- tests or validation expectations
- manual verification steps
- definition of done

Prefer a small vertical slice over a broad multi-feature prompt.

## Closed Loop Contract

Default meaningful development slices to a closed loop: Codex owns the
iteration inside the approved scope until the acceptance signals pass, a stop
condition is reached, or the user changes direction. Human control remains at
the goal, boundary, review, and final approval layers.

Before implementation, make the loop contract explicit:

- Goal: the concrete outcome this slice should reach.
- Loop owner: whether Codex should self-iterate after failures within the
  approved scope.
- Acceptance signals: the 0/1 checks that decide pass or fail.
- Stop conditions: ambiguity, risk, approval gates, or repeated failures that
  require pausing for the user.
- Open-loop boundary: whether exploration is allowed and where it must stop.
- Next step artifact: the handoff or `next_steps` that should seed the next
  slice.

Keep acceptance signals machine-checkable where possible: tests pass or fail,
lint passes or fails, enum values are legal or illegal, snapshot anchors are
present or missing, guidance contract cases hit the intended answer or fall
back incorrectly, and gate invariants are respected or bypassed.

Use open-loop exploration only for research, diagnosis, or external review
where the goal cannot yet be reduced to a narrow implementation slice. Even
then, define a budget, evidence boundary, and stop condition before exploring.

See `references/closed-loop-contract.md` for the detailed pattern.

## Feature And Business Logic Validation

For every meaningful feature slice:

1. Keep the feature implementation plan and business-logic plan together.
2. Define implementation and business-logic checklists side by side.
3. Map business rules directly to feature checklist items where possible.
4. Do not treat unit tests as code-only verification.
5. Use tests to check both functional behavior and intended business logic.

After implementation, produce a matched validation view:

- feature development list
- business logic checklist
- tests that cover each item
- manual verification for uncovered business rules
- whether user manual testing is needed
- recommended next development step

Manual verification steps must be directly executable. Include:

- exact route, page, command, or object
- preconditions such as login state, servers, token, real ID, or data shape
- user action
- expected visible result or API response
- covered business rule or regression risk
- whether required for completion or optional confidence checking

Trivial changes may use a one-line validation summary.

## Handoff

After every completed development slice, tell the user:

1. Whether manual testing is needed.
2. If yes, provide detailed test steps with paths/commands, preconditions,
   actions, expected results, and covered business rules.
3. If no, explain why automated validation is enough.
4. The recommended next closed-loop slice, including goal, acceptance signals,
   likely files, and stop condition when a follow-up is warranted.

For documentation or ADR slices, also check whether the document creates a
future implementation milestone, validation step, gap report, or planning
follow-up. If it does, state where that reminder should live and whether it was
recorded.

Do not commit, push, open a PR, or deploy unless the user explicitly asks.

## Status Tracking

Update `CURRENT_DEVELOPMENT_STATUS.md` when:

- a development slice is completed
- the user reports manual testing or offline progress
- the user gives a closeout trigger
- the user explicitly asks for status tracking
- a new or materially changed ADR creates a concrete next milestone,
  especially when the ADR is `Proposed` or has an implementation plan

Distinguish Codex-run validation from user-reported/manual validation. Record
unresolved gaps, whether more manual testing is needed, and the next
recommended slice.

Because `CURRENT_DEVELOPMENT_STATUS.md` is a core file, follow the core-file
approval gate before editing it.

If a new ADR changes the top-level development direction rather than only the
next slice, ask whether `DEVELOPMENT_PLAN.md` should also be updated. Follow
the core-file approval gate before editing it.
