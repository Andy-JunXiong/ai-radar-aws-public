---
title: Closed Loop Contract
layer: A-prime-agent-protocol
status: experimental
source_boundary: inspired by external Loop Engineering and Superpowers material; product, marketplace, and vendor claims are not absorbed here
---

# Closed Loop Contract

Use this reference when a development slice is meaningful enough that Codex
should not merely perform one command or one edit, but should iterate inside an
approved boundary until the slice is genuinely handled.

## Core Rule

A closed-loop slice moves Codex into the loop body while keeping the human at
the control surface:

- the human owns purpose, boundaries, approval, and final review
- Codex owns iteration, checks, local diagnosis, and next-step handoff inside
  the approved scope

Do not treat this as permission to broaden scope. Closed loop means stronger
execution discipline, not larger autonomy.

## Contract Fields

Use these fields in the plan or first substantial update when the slice is not
trivial:

```text
Goal:
Loop owner:
Acceptance signals:
Stop conditions:
Open-loop boundary:
Next step artifact:
```

### Goal

Name the outcome in terms of user-visible or repo-visible state, not effort.

Good:

```text
Add relationship annotation review metadata to feedback payloads and render it
in the Signal Review UI.
```

Weak:

```text
Look into relationship annotations.
```

### Loop Owner

Say whether Codex should self-iterate after failed checks within the approved
scope.

Use `Codex` when failures are local and recoverable, such as a failing targeted
test, formatting issue, missing import, or contract-case mismatch.

Use `Human` or pause when the next step changes product semantics, touches a
core-file approval gate, requires credentials, needs a destructive operation,
or would broaden the slice.

### Acceptance Signals

Prefer 0/1 checks. Examples:

- targeted tests pass
- lint or typecheck passes
- expected route returns the documented shape
- guidance contract case resolves to the intended page answer
- enum value is in the closed set
- snapshot anchor exists
- blocked action gate remains enforced
- manual test step shows the expected visible result

Avoid acceptance language that asks the model to guess quality, such as "looks
good", "probably enough", or "seems polished", unless it is paired with a
specific checkable condition.

### Verification Before Completion

Do not claim a slice is complete, fixed, passing, or verified unless the claim
is backed by fresh evidence from this turn or by an explicitly labeled
user-reported/manual validation result.

Fresh evidence can include:

- a command that just ran and its pass/fail outcome
- a route, API, or browser smoke result from this turn
- a targeted diff or grep check that directly verifies a documentation-only
  change
- a user-reported validation result, labeled as user-reported rather than
  Codex-run

If verification was not run, say so. If verification is partial, name the gap.
If a claim rests on older memory, previous-session results, or source
self-report, do not phrase it as newly verified.

Completion wording must match evidence:

- use `implemented` for code or document changes that were applied
- use `Codex-validated` only for checks Codex ran in this turn
- use `user-reported validation` only for checks reported by the user
- use `not run` or `not covered` when evidence is absent

This rule prevents unearned completion claims: do not inflate "I made the
change" into "it is verified" without evidence.

### Stop Conditions

Stop and ask before proceeding when:

- a core file would need editing without explicit approval
- a workflow, deployment, AWS write, credential, or secret boundary appears
- the next change would add a new architecture path or executor path
- external factual claims would need live verification and the user has not
  approved browsing or source inspection
- the same blocking condition repeats and local iteration is no longer adding
  evidence
- the patch would move from the approved closed-loop slice into open-ended
  exploration

### Open-Loop Boundary

Open-loop work is allowed only when the task is explicitly exploratory, such as
an architecture review, external-content audit, incident diagnosis, or unknown
failure investigation.

Before open-loop work, define:

- evidence boundary: which files, sources, or logs may be inspected
- budget: how far to search before reporting back
- stop condition: what finding or uncertainty ends exploration
- conversion point: what would turn the exploration into a closed-loop slice

### Next Step Artifact

End meaningful slices with the next useful loop seed:

```text
Next closed-loop slice:
- Goal:
- Acceptance signals:
- Files likely touched:
- Stop condition:
```

If no follow-up is needed, say so explicitly. If the follow-up would require a
core-file status update, ADR, PR, commit, push, or deployment, call out that it
needs separate user approval.

## Multi-Agent Boundary

This contract does not add a multi-agent executor path. If multiple agents are
ever used for one slice, one orchestrator must own goal tracking, task
division, result synthesis, and the decision to deliver, retry, or stop.

Until that orchestrator design is explicitly approved, keep this protocol as a
single-agent Codex loop discipline.
