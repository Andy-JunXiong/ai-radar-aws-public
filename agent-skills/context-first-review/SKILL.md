---
name: context-first-review
description: |
  Use when Codex reviews an architecture brief, migration proposal, prompt proposal, external analysis, or cross-module implementation plan that makes claims about the current AI Radar repository. The protocol forces repo-grounded path and boundary discovery before accepting, rejecting, or rewriting the proposal.
status: experimental
intended_consumers:
  - codex-cli
  - claude-code
---

# Context-First Review

Use this protocol when a user asks for review of a brief, migration proposal,
architecture proposal, prompt proposal, or external analysis that describes the
current repository.

The goal is to prevent review based on stale memory, guessed paths, or assumed
system boundaries.

## Trigger

Apply this skill when the artifact under review:

- names repository files, routes, services, schemas, skills, or docs
- proposes changing AI Radar architecture, verification, Project Takeaway,
  prompt behavior, agent skills, or workflow semantics
- asks Codex for `go / no-go / modify` on a migration or implementation brief
- contains claims that can be checked against the local repository

Do not use this skill for tiny typo edits, single-file bug fixes, or purely
conceptual brainstorming with no repository claims.

## Required Context Pass

Before judging the proposal, perform a narrow repository pass:

1. Path discovery
   - Verify every path named by the proposal.
   - If a path is stale, find the nearest current path or mark it missing.
   - Treat user- or LLM-provided paths as seed hints, not facts.

2. Boundary discovery
   - Identify the current code/docs boundary for the proposal's core claim.
   - Prefer implementation call chains and canonical constants over planning
     prose when they conflict.
   - Note whether the claim touches AGENTS.md hard rules, Project Takeaway
     gates, verification metadata, override paths, product runtime prompts, or
     agent-only skills.
   - If the proposal derives from an external framework, product, article,
     paper, lecture, advisor brief, or other outside source and may enter AI
     Radar as feature, architecture, workflow, skill, agent protocol, or
     implementation work, explicitly run ADR-0010 admission discovery before
     recommending implementation or treating user agreement as scope approval.
     Record the admission outcome and smallest admitted scope.

3. Conflict discovery
   - List where the proposal over-tightens, under-specifies, or bypasses the
     current boundary.
   - Separate ordinary paths from exceptional override or manual paths.

Do not propose a rewrite until the required context pass is complete.

## Review Output

Return findings in this order:

1. `Decision`: `go`, `modify`, or `no-go`.
2. `Grounded Facts`: paths and boundaries verified from the repository.
3. `Conflicts`: stale paths, false assumptions, unsafe scope, or missing
   stop conditions.
4. `Recommended Shape`: the smallest revised scope that preserves current
   boundaries.
5. `Stop Conditions`: what would require user approval or a separate slice.

For external-insight-driven proposals, include the ADR-0010 admission result in
`Decision` or `Grounded Facts`. If the gate has not been run, pause and ask for
the admission decision instead of recommending implementation.

When useful, create or update an assessment file under
`docs/codex-assessments/` so the review is git-trackable. Assessment files are
for Codex review outputs, not product runtime instructions.

## Project Takeaway Review Notes

When the proposal touches Project Takeaway candidate creation or review:

- Do not describe the boundary as "only from `verified_insight_service`".
- Confirm the current write path and candidate-source categories first.
- Keep `blocked_downstream_actions` and derived action eligibility as hard
  gates for ordinary flows.
- Keep manual override explicit, auditable, and exceptional.
- Keep `unverified_manual_entry` out of clean claim-support semantics.
- Keep `knowledge_convergence_review_candidate` as review context, not verified
  action evidence.

## Non-Goals

- Do not edit code or docs merely because the proposal suggests it.
- Do not load agent skills into product runtime.
- Do not create a second skill registry outside `agent-skills/`.
- Do not turn an advisory review into a replacement for verification services.
