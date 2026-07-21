---
adr: 0016
title: Action-Loop Stagnation Protocol
status: Proposed
created: 2026-07-05
layer: L1-governance-decision
related:
  - L1: docs/adr/0010-external-insight-admission-gate.md
  - L1: docs/adr/0015-claim-set-composition-underdetermination-gate.md
  - L2: agent-skills/grill-the-inference/SKILL.md
  - L2: agent-skills/action-loop-stagnation/SKILL.md
  - L2: agent-skills/_shared/references/counter-conclusion.md
tags: [agent-skill, layer-a-prime, action-loop, stagnation]
---

# ADR-0016: Action-Loop Stagnation Protocol

## ADR Gate

Create this ADR only if all are yes:

- [x] Hard to reverse: once an action-loop stagnation protocol becomes part of
  the Layer A' operating vocabulary, future agents may depend on its boundary
  and trigger semantics.
- [x] Context would be lost: future readers would ask why claim/inference
  protocols cover underdetermination while repeated action-loop failure has no
  corresponding review protocol.
- [x] Real tradeoff: plausible alternatives include extending
  `grill-the-inference`, treating stagnation as ordinary debugging discipline,
  or deferring the issue to runtime hooks.

## ADR-0010 Admission Gate Result

Outcome: `admit`, in modified form.

Smallest admitted scope:

- design two proposed Layer A' protocols:
  `reconcile-invariants` and `action-loop-stagnation`
- introduce a shared counter-conclusion reference at
  `agent-skills/_shared/references/counter-conclusion.md`
- keep all artifacts agent-only and proposed
- do not install external skills
- do not add hooks, remote services, product runtime prompts, runtime gates,
  Project Takeaway changes, or `blocked_downstream_actions` mapping

## Context

AI Radar already has Layer A' and verification-spine protocols for claim and
inference review. ADR-0015 recognized claim-set composition
underdetermination as distinct from per-claim verification, and
`grill-the-inference` currently handles that review at the agent-protocol
layer.

A separate failure mode occurs when an agent repeats the same action hypothesis
class, changes only local details, claims completion without verification, or
hands work back to the user before safe diagnostic checks are exhausted. That
failure is not a claim-set composition problem. Its object is the action loop,
not the evidence-to-conclusion relationship.

The useful transferable mechanism is counter-conclusion construction: forcing a
different interpretation of the same packet. For action loops, the packet is a
failure packet rather than a claim set, and the output is a different next
action hypothesis rather than a weaker or contrary factual conclusion.

The PUA skill repository also contains non-transferable elements: personality
pressure, remote registration, analytics, feedback collection, optional session
upload, payments, leaderboards, hooks, and platform-specific automation. Those
are explicitly out of scope for AI Radar.

## Decision

Introduce `agent-skills/action-loop-stagnation/SKILL.md` as an experimental
Layer A' agent protocol for detecting and interrupting action-loop stagnation.

Introduce `agent-skills/reconcile-invariants/SKILL.md` as an experimental
Layer A' closeout protocol that produces scoped assessments or proposed diffs
for invariant drift without automatically patching core files or scanning the
entire repository.

Introduce `agent-skills/_shared/references/counter-conclusion.md` as the shared
reference for counter-conclusion construction and the three-branch verdict
vocabulary used by `grill-the-inference` and `action-loop-stagnation`. This ADR
does not establish a general convention for all future shared references.

`action-loop-stagnation` uses:

- repeated same-hypothesis-class failure
- completion claims without available verification
- handoff-before-evidence or effort-asymmetry language as experimental Layer A'
  trigger signals
- at least two structurally different alternative hypotheses
- a verification oracle when an executable acceptance signal exists
- verdicts of `pass`, `underdetermined`, and `needs_human_judgment`

For this protocol, `underdetermined` means the current failure packet is
insufficient to choose among materially different next action hypotheses. It
does not mean an external claim lacks evidential support.

## Owns

- The Layer A' recognition of action-loop stagnation as a distinct agent
  failure mode.
- The decision that the action-loop protocol is separate from
  `grill-the-inference`, because its object is action control rather than
  claim-set support.
- The shared counter-conclusion reference at
  `agent-skills/_shared/references/counter-conclusion.md`.
- The boundary that the new protocol is agent-only and does not create a
  runtime gate.
- The experimental borrowing of `effort_asymmetry_framing` language as a
  Layer A' trigger label only.

## Does Not Own

- Product runtime prompts, skills, services, schemas, routes, or storage.
- Hooks, CI controls, verifier infrastructure, or mechanical loop enforcement.
- Project Takeaway gates, overrides, review outcomes, Action eligibility, or
  `blocked_downstream_actions`.
- Promotion of `effort_asymmetry_framing` into a canonical runtime or action
  operator.
- Installation, vendoring, or execution of external skill repositories.
- Any change to AWS, deployment, `.github/workflows/`, or production systems.

## Consequences

Positive:

- Gives agents an explicit Layer A' protocol for repeated action-loop failure
  without contaminating claim/inference review semantics.
- Reuses the counter-conclusion pattern while keeping claim-set and action-loop
  payloads separate.
- Makes verification evidence explicit by requiring a `verification_oracle`
  when an executable acceptance signal exists.
- Keeps external skill inspiration behind ADR-0010 admission boundaries.

Negative / accepted risks:

- Adds one new Layer A' skill and one shared counter-conclusion reference.
- Introduces another use of the `underdetermined` verdict that must be clearly
  scoped to action choice, not evidential claim support.
- The action-loop stop remains a protocol request, not a mechanical halt.

Hard boundary:

- Layer A' has no mechanical halt authority. A hard stop here can only request
  `<loop-abort>`, `needs_human_judgment`, or handoff to the user. Mechanical
  enforcement would require a separately admitted hook or runtime slice.
- `blocked_downstream_actions` is not connected to this protocol.
- `effort_asymmetry_framing` remains a credibility-audit specimen tag unless a
  separate taxonomy or runtime review promotes it.

## Alternatives Considered

### Extend `grill-the-inference`

Rejected. `grill-the-inference` acts on claim sets and conclusions. Adding
behavioral triggers and debugging checklists would blur its description and
reduce trigger precision.

### Use `anti-stagnation-gate` Naming

Rejected for this repository. In AI Radar, "gate" can imply product runtime or
`blocked_downstream_actions` enforcement. This ADR chooses
`action-loop-stagnation` to name the object and failure mode without implying a
runtime gate.

### Runtime Hook First

Rejected for this ADR. Hook-based enforcement could be useful later, but it
would require a separate admitted runtime or tool-integration slice. The
current scope is Layer A' protocol design only.

### Treat As Ordinary Debugging Discipline

Rejected. Ordinary debugging advice does not capture the specific failure of an
agent using effort, repetition, or unverifiable completion as a substitute for
changing hypotheses and producing evidence.

## Implementation Plan

Allowed current work:

1. Add `agent-skills/action-loop-stagnation/SKILL.md`.
2. Add `agent-skills/reconcile-invariants/SKILL.md`.
3. Add `agent-skills/_shared/references/counter-conclusion.md`.
4. Update `agent-skills/grill-the-inference/SKILL.md` only enough to reference
   the shared vocabulary while preserving its self-contained process.
5. Update Layer A' and ADR registries so future agents can discover the
   proposed protocol and ADR.

Not admitted now:

1. Runtime hooks or mechanical halt enforcement.
2. Product runtime prompt or skill exposure.
3. Project Takeaway, Action eligibility, or `blocked_downstream_actions`
   integration.
4. Taxonomy promotion of `effort_asymmetry_framing`.
5. External skill installation, remote service use, or telemetry.

## Open Items

- Observe whether `action-loop-stagnation` catches repeated failure without
  over-triggering on ordinary first-attempt debugging.
- Collect examples where no executable oracle exists and verify whether the
  protocol routes to `needs_human_judgment` early enough.
- If mechanical enforcement becomes desirable, run ADR-0010 and the relevant
  core-boundary preflight for a separate hook/runtime slice.
- If `effort_asymmetry_framing` should become more than a borrowed label, run a
  separate taxonomy or schema review.
- If future Layer A' protocols need unrelated shared references, review that
  convention separately instead of treating this ADR as blanket approval.

## References

- ADR-0010: External Insight Intake Requires Author-Side Admission Gate
- ADR-0015: Claim-Set Composition Underdetermination Gate
- `agent-skills/grill-the-inference/SKILL.md`
- `agent-skills/action-loop-stagnation/SKILL.md`
- `agent-skills/reconcile-invariants/SKILL.md`
- `agent-skills/_shared/references/counter-conclusion.md`
