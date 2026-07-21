---
name: incident-attribution
description: |
  Use after or alongside a collaboration failure involving Andy, Claude, Codex, or another AI Radar development agent, when the team needs to capture facts, assign reviewable attribution, and decide whether a repeated process pattern should change agent guidance.
status: experimental
intended_consumers:
  - codex-cli
  - claude-code
---

# Incident Attribution

Use this protocol in Development Mode after or alongside a collaboration
failure. Keep AGENTS.md hard boundaries, worktree safety, core-file approval
gates, and sensitive-data rules in force.

This is not the operational incident-response skill. Use
`agent-skills/incident-response/SKILL.md` for alerts, production failures,
failing CI, smoke-test failures, AWS investigation, and live remediation.

## Trigger

Use this skill when a failure appears to involve the collaboration process
itself, such as:

- plausible but weakly grounded architecture or planning
- unclear task handoff, missing context, or missing success criteria
- agent execution that violates repo rules, approval gates, or validation
  expectations
- a review or verification gap that allows an avoidable issue through
- a recurring development failure that was fixed once but not connected to a
  larger pattern

Do not use this skill for every ordinary bug. Use it when the failure teaches
something about how the human and agents should collaborate.

## Stage Model

Use these provisional attribution stages:

1. `problem_definition`: Andy's problem framing, priority, or success criteria
   were incomplete or misleading.
2. `task_handoff`: the instruction to an executor omitted important scope,
   validation, permission, or context.
3. `architectural_judgment`: Claude, Codex, or another advisor produced
   plausible but weakly grounded architecture, planning, or synthesis.
4. `execution`: Codex or another executor made a file, tool, implementation,
   or testing mistake.
5. `verification`: one or more parties failed to validate the result against
   the right source, test, browser behavior, status document, ADR, or user
   expectation.

## Workflow

### 1. Immediate Capture

Create a raw incident record under:

```text
incidents/raw/
```

Capture only facts:

- date
- active task
- what happened
- where the issue appeared
- evidence and repo references
- immediate impact
- immediate fix or current status

Do not assign blame in the raw record.

### 2. Attribution Closeout

Create or update an attribution record under:

```text
incidents/attributed/
```

Separate:

- facts
- interpretation
- stage attribution
- party contributions
- what worked in the recovery
- candidate recurring pattern
- approved or proposed corrective action

Attribution is reviewable and may be challenged by Andy.

### 3. Pattern Review

Create pattern reviews under:

```text
incidents/patterns/
```

Only create a pattern review when an incident seems to recur, or when Andy asks
for a pattern review.

Pattern reviews must produce one explicit outcome:

- approved file change
- proposed file change requiring separate approval
- backlog item
- no-change decision with rationale
- continued observation

Pattern review must not automatically modify core files.

## Data Handling

Incident records must not include:

- credentials, tokens, API keys, or secret-like strings
- AWS credentials or session details
- raw sensitive prompts
- private user data
- full external API payloads
- unnecessary runtime data

Commit incident files only after Andy confirms they contain no sensitive
content and belong in repo history.

## Core File Boundary

Do not modify `AGENTS.md`, `CURRENT_DEVELOPMENT_STATUS.md`, ADRs, `docs/ops/`,
or other core files from an attribution outcome unless Andy explicitly
approves that specific core-file change.

## Handoff

After using this skill, report:

- raw incident record path, if created
- attribution record path, if created
- candidate pattern, if any
- proposed next corrective action
- whether any core-file change needs separate approval
