---
adr: 0007
title: Incident Attribution Agent Skill for Collaboration Failure Learning
status: Accepted
created: 2026-05-19
layer: L1-engineering-solution
related:
  - L1: docs/adr/0003-runtime-agnostic-skill-registry.md
  - L1: docs/adr/0004-agents-constitution-skill-registry.md
  - L1: docs/adr/0005-dual-gate-pre-sprint-protocol.md
  - L2: AGENTS.md
  - L2: agent-skills/incident-response/SKILL.md
  - L2: agent-skills/incident-attribution/SKILL.md
tags: [agent-skills, incident-attribution, collaboration-failures, process-learning]
---

# ADR-0007: Incident Attribution Agent Skill for Collaboration Failure Learning

## ADR Gate

Create this ADR only if all are yes:

- [x] Hard to reverse: once collaboration incidents are stored in a repo
  structure and fed back into AGENTS.md, agent skills, or operating guidance,
  the schema and attribution model become part of the project's process memory.
- [x] Context would be lost: future readers would ask why AI Radar separates
  operational incident response from multi-agent collaboration attribution, and
  why incident records live outside the skill directory.
- [x] Real tradeoff: plausible alternatives include ordinary bug tracking,
  GitHub Issues, immediate Layer B extraction, or capture-only logging without
  attribution and pattern review.

## Context

AI Radar is developed through a multi-agent collaboration pattern:

- Andy defines the problem, approves direction, and makes final judgment.
- Claude may act as architectural advisor or review partner.
- Codex writes files, runs local tools, reviews code, and implements approved
  changes.

This collaboration can fail in ways that are not ordinary product incidents.
Examples include:

- an upstream architectural synthesis is plausible but insufficiently grounded
- Codex executes with too much autonomy or misses a core-file approval gate
- a handoff omits the validation step that would have prevented rework
- the same agent family reviews its own output without enough external
  grounding
- a recurring local development failure is fixed in the moment but never
  connected to earlier occurrences

AI Radar already has `agent-skills/incident-response/SKILL.md` for operational
incidents such as alerts, failing CI, production errors, and smoke-test
failures. That skill is about diagnosing and remediating the live issue.

The gap here is different. The project needs a way to capture and learn from
multi-agent collaboration failures after or alongside the immediate fix. The
goal is not only "what broke?" but "which part of the human / Claude / Codex
collaboration chain produced the failure, and what should change so this class
of failure becomes less likely?"

The first version should stay inside AI Radar as a Layer A' agent
collaboration protocol. In this repository, Layer A' means repo-local agent
collaboration protocols used by Codex and Claude during AI Radar development,
distinct from product runtime skills used by AI Radar users. It should not be
extracted into a general Layer B / external methodology until real incidents
prove the attribution framework, failure stages, and corrective-action loop.

This ADR also corrects assumptions from the external draft:

- This is ADR-0007, because ADR-0006 is already `Operator Guidance Layer`.
- ADR-0004 in this repository is `AGENTS.md Constitution and Skill Registry`,
  not a verification-aware synthesis ADR.
- The agent skill location is `agent-skills/incident-attribution/SKILL.md` per
  ADR-0003, not `.skills/incident-attribution/`.

## Decision

Create an experimental Layer A' agent skill named `incident-attribution`.

`incident-attribution` is an agent skill that implements an incident
attribution protocol. The skill is the loadable instruction package for
Codex, Claude, or another development agent. The protocol is the collaboration
workflow that the skill instructs the agent to follow.

The implemented skill path is:

```text
agent-skills/incident-attribution/SKILL.md
```

The skill tracks collaboration failures through three layers:

1. **Immediate capture**: record factual incident details with no attribution.
   Capture only what happened, where it happened, the active task, relevant
   evidence, and git/worktree context.
2. **Attribution closeout**: after the immediate issue is understood, assign
   one or more likely failure stages and party contributions. Attribution must
   remain reviewable and may be challenged.
3. **Pattern review**: periodically cluster attributed incidents by shared
   failure mechanism and produce an explicit outcome.

The initial failure-stage model is:

1. `problem_definition`: Andy's problem framing, priority, or success criteria
   were incomplete or misleading.
2. `task_handoff`: the instruction from Andy to an executor omitted important
   scope, validation, permission, or context.
3. `architectural_judgment`: Claude, Codex, or another advisor produced
   plausible but weakly grounded architecture, planning, or synthesis.
4. `execution`: Codex or another executor made a file, tool, implementation, or
   testing mistake.
5. `verification`: one or more parties failed to validate the result against
   the right source, test, browser behavior, status document, ADR, or user
   expectation.

The failure-stage model is provisional. It should be revised after real
incident records show whether the categories are too coarse, too narrow, or
missing a stage.

Incident records live outside `agent-skills/` because skills are operating
protocols while incidents are accumulating process data. The implemented repo
locations are:

```text
incidents/raw/
incidents/attributed/
incidents/patterns/
```

These directories are not created by this ADR. Creating them belongs to the
implementation slice after this ADR is reviewed and approved.

Data handling rules:

- `incidents/raw/` is factual capture. It should not include attribution,
  blame, secrets, credentials, raw sensitive prompts, private user data, full
  external API payloads, or unnecessary runtime data.
- `incidents/attributed/` contains reviewed attribution records. These should
  distinguish evidence from interpretation.
- `incidents/patterns/` contains periodic pattern reviews and approved
  corrective outcomes.
- Incident files may be committed only after the human confirms they contain no
  sensitive content and belong in repo history.

Pattern reviews must produce an explicit outcome. Valid outcomes include:

- approved file change
- proposed file change requiring separate approval
- backlog item
- no-change decision with rationale
- continued observation

Pattern review must not automatically modify core files. Changes to `AGENTS.md`,
`CURRENT_DEVELOPMENT_STATUS.md`, ADRs, `docs/ops/`, `docs/adr/`, or other core
files still require the normal core-file approval gate.

Reminder mechanism:

- Primary reminder is a human-created calendar reminder or equivalent personal
  task reminder.
- Codex may record that a reminder exists if the user reports it.
- GitHub Actions, Google Calendar connector automation, or other scheduled
  automation is out of scope for the initial implementation.

## Owns

- The decision to create a Layer A' `incident-attribution` agent skill.
- The separation between operational `incident-response` and collaboration
  `incident-attribution`.
- The initial three-layer incident workflow: capture, attribution, pattern
  review.
- The provisional five-stage attribution model.
- The implemented incident data locations outside `agent-skills/`.
- The sensitive-data and commit-boundary rules for incident records.
- The rule that pattern reviews produce explicit outcomes but do not
  automatically change core files.

## Does Not Own

- Production incident diagnosis or remediation; that remains owned by
  `agent-skills/incident-response/SKILL.md`.
- Any AWS, S3, deployment, CI, or workflow automation.
- Any Google Calendar connector implementation.
- Any automatic modification of AGENTS.md or other core files.
- Extraction to Layer B / external methodology.
- Notebook publication decisions.
- A permanent failure-stage taxonomy.

## Consequences

The project gains a way to distinguish "a bug happened" from "a collaboration
failure pattern is recurring." That makes it easier to improve AGENTS.md, agent
skills, handoff prompts, and validation discipline based on evidence instead of
vibes.

The protocol makes upstream causes more visible. A failure that appears during
execution may have started in problem definition, task handoff, architectural
judgment, or verification.

It also creates overhead. Immediate capture, attribution closeout, and periodic
pattern review are only useful if they stay lightweight and lead to explicit
outcomes. A heavy process that records incidents but never changes behavior
would become ceremony.

Attribution bias remains a risk. Andy, Claude, and Codex can all be involved in
the failure under review. Attribution records should therefore separate facts,
interpretation, and approved corrective action.

Storing incident data in the repo can be valuable, but it creates privacy and
security risk. Raw incident records must be minimal and must not become a dump
of sensitive prompts, credentials, logs, or local runtime data.

## Alternatives Considered

### Alternative 1: GitHub Issues as the incident store

Rejected for the initial version. GitHub Issues are useful for work tracking,
but they do not naturally enforce structured multi-stage attribution. They also
move the process memory outside the repo and complicate offline review.

### Alternative 2: Ordinary bug tracker only

Rejected. A bug tracker captures surface failures but usually loses the
judgment chain that produced the failure. The value of this protocol is
attribution and pattern learning, not only issue tracking.

### Alternative 3: Create a Layer B methodology immediately

Rejected. The method may become generalizable, but the failure stages and
review cadence are unproven. Per ADR-0003 and ADR-0005's discipline, the
protocol should be validated inside AI Radar before extraction.

### Alternative 4: Capture-only logging

Rejected as insufficient. Capture without attribution and pattern review is
just a log. The desired improvement comes from connecting incidents to repeated
failure mechanisms and approved corrective outcomes.

### Alternative 5: Fold this into incident-response

Rejected. Incident response and incident attribution have different goals.
`incident-response` should remain focused on diagnosing and fixing operational
or production failures. `incident-attribution` should focus on post-fix process
learning across Andy / Claude / Codex collaboration.

## Implementation Plan

1. Keep this ADR `Proposed` until reviewed by Andy. Completed on 2026-05-19.
2. After approval, create the initial skill and incident directories.
   Completed on 2026-05-19:
   - `agent-skills/incident-attribution/SKILL.md`
   - `incidents/raw/.gitkeep`
   - `incidents/attributed/.gitkeep`
   - `incidents/patterns/.gitkeep`
3. Draft minimal templates. Completed on 2026-05-19:
   - immediate raw capture
   - attribution closeout
   - pattern review
4. Add a narrow AGENTS.md registry entry only after the skill exists and the
   user explicitly approves the core-file update. The minimum registry entry
   should include the skill name, trigger condition, path, and one-line
   purpose. It should not embed the full workflow, templates, Daily Closeout
   rules, or pattern-review policy. Completed on 2026-05-19.
5. Do not update Daily Closeout rules until further use proves the
   workflow is not too heavy.
6. Use the first real incident to test the workflow end to end. Completed on
   2026-05-19 with the ADR-0007 collaboration draft incident.
7. Revisit the failure-stage model after at least four attributed incidents or
   one month of use, whichever comes later.
8. Reconsider Layer B extraction only after at least four pattern reviews and
   evidence that corrective outcomes improved future behavior.

## References

- [ADR-0003: Runtime-Agnostic Skill Registry](./0003-runtime-agnostic-skill-registry.md)
- [ADR-0004: AGENTS.md Constitution and Skill Registry](./0004-agents-constitution-skill-registry.md)
- [ADR-0005: Dual-Gate Pre-Sprint Protocol](./0005-dual-gate-pre-sprint-protocol.md)
- [AGENTS.md](../../AGENTS.md)
- Existing operational skill:
  `agent-skills/incident-response/SKILL.md`
- Implemented skill:
  `agent-skills/incident-attribution/SKILL.md`
