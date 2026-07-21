---
name: action-loop-stagnation
description: |
  Use when an agent appears stuck in the same action hypothesis class, repeatedly fails without changing approach, claims completion without verification, or shifts effort back to the user before exhausting available diagnostic moves. This Layer A' protocol interrupts action-loop stagnation, forces structurally different next hypotheses, and uses an executable verification oracle when one exists; it is agent-only and does not create a product runtime gate.
status: experimental
intended_consumers:
  - codex-cli
  - claude-code
---

# Action Loop Stagnation

Use this protocol when the problem is no longer a single failed attempt, but an
action loop that is failing to learn.

The protocol is the action-layer mirror of counter-conclusion construction:
instead of asking whether a claim set determines a conclusion, ask whether the
current failure packet determines the next action. If multiple structurally
different next actions remain plausible and the current loop cannot distinguish
between them, narrow the task or route to human judgment.

This is a Layer A' agent protocol. It is not a product runtime gate, hook,
deployment control, or `blocked_downstream_actions` integration.

## Boundary

This protocol may:

- name the repeated hypothesis class
- identify repeated failures, false completion, or handoff-before-evidence
- require at least two structurally different next hypotheses
- require a verification oracle when an executable acceptance signal exists
- return `pass`, `underdetermined`, or `needs_human_judgment`
- request `<loop-abort>` or a human handoff when the loop has hit a stop
  condition

This protocol must not:

- use shame, role-play pressure, or personality attacks
- install or invoke external skills
- call remote registration, analytics, feedback, upload, payment, or leaderboard
  services
- modify hooks, CI, runtime gates, Project Takeaway, Action eligibility, or
  `blocked_downstream_actions`
- treat `effort_asymmetry_framing` as an authorized runtime or action operator
- bypass worktree safety, core-file approval, or user approval gates

`effort_asymmetry_framing` is borrowed only as an experimental Layer A' trigger
label for review language. It remains a credibility-audit specimen tag unless a
separate taxonomy or runtime review promotes it.

Layer A' has no mechanical halt authority. A "hard stop" in this skill is a
protocol request: output `<loop-abort>`, `needs_human_judgment`, or a handoff to
the user. Mechanical enforcement would require a separately admitted hook or
runtime slice.

## Trigger

Run this protocol when one or more of these are true:

- the same hypothesis class has failed repeatedly
- the agent is changing parameters, wording, or nearby code without changing
  the underlying approach
- the agent claims completion without running the available verification
- the agent proposes that the user manually check something the agent can still
  inspect safely
- the agent cites effort or iteration count as a reason to trust the result
  without exposing evidence
- the user says the work is stuck, looping, still failing, or needs a different
  approach

Do not run this protocol for a calm first attempt, a task that has a clear next
diagnostic step, or a genuine approval boundary that requires the user.

## Inputs

Start from the smallest available failure packet:

- task intent
- acceptance signal or expected behavior
- recent failed attempts
- latest error output or missing evidence
- files, commands, or environment facts already checked
- user-imposed boundaries or approval gates

If the task intent or acceptance signal is missing, ask for it or route to
`needs_human_judgment` rather than continuing the loop.

## Process

1. Stop and name the loop.
   - State the current hypothesis class.
   - Explain why recent attempts did not advance the task.
   - Separate repeated evidence from new evidence.

2. Build alternative action hypotheses.
   - Construct at least two structurally different hypotheses from the same
     failure packet.
   - A hypothesis is structurally different only if it changes the suspected
     layer, data shape, execution path, environment assumption, or verification
     method.
   - Discard alternatives that merely rename the same approach.

3. Choose or define the verification oracle.
   - If an executable acceptance signal exists, `verification_oracle` is
     required. Prefer the smallest command, route, script, or reproducible
     check that can decide whether this round advanced.
   - If no executable oracle exists, record why no oracle is available and
     narrow the task or route to human judgment sooner.
   - Do not claim completion without oracle output when an oracle exists.

4. Run the next action only when it is inside the approved scope.
   - Respect worktree safety and core-file approval gates.
   - Do not edit tests, scoring assets, hooks, CI, secrets, or deployment paths
     to manufacture success.
   - If the next action crosses a boundary, stop and ask.

5. Decide the verdict.
   - `pass`: a structurally different hypothesis was tried, the oracle or
     evidence advanced, and the next step is clear.
   - `underdetermined`: the failure packet supports multiple materially
     different next hypotheses and does not distinguish which should be tried
     next. In this protocol, `underdetermined` is about action choice, not
     external claim evidence.
   - `needs_human_judgment`: the protocol cannot continue because user intent,
     permission, domain judgment, environment access, or an executable oracle is
     missing.

6. Recommend the smallest safe next step.
   - Continue with the verified approach.
   - Narrow the reproduction.
   - Gather the missing oracle or evidence.
   - Handoff to the user with facts already verified.
   - Output `<loop-abort>` if repeated attempts have reached the stop condition.

## Output Format

Use this compact structure:

```text
LOOP: <current hypothesis class>
WHY STUCK: <why recent attempts did not advance>
FAILURE PACKET:
- <error, attempt, or evidence>
ALTERNATIVE HYPOTHESES:
- H1: <structurally different approach> - oracle: <command/check or none>
- H2: <structurally different approach> - oracle: <command/check or none>
VERIFICATION_ORACLE: <required command/check, or unavailable because ...>
VERDICT: pass | underdetermined | needs_human_judgment
NEXT STEP: <single smallest safe action>
```

Keep the output short and operational. The point is to change the loop, not to
write a retrospective.

## Stop Conditions

Stop before:

- repeating the same hypothesis class again
- claiming completion without an available oracle
- shifting work to the user while safe agent-side checks remain
- modifying tests, hooks, CI, runtime gates, scoring assets, secrets, or
  deployment paths to make the task appear solved
- bypassing a core-file, ADR, or runtime approval boundary
- treating Layer A' review output as product runtime enforcement
