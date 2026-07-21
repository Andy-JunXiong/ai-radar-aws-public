---
madr: 0001
title: Validation Events Trigger Framing Grill
status: Accepted
created: 2026-06-05
accepted: 2026-06-05
domain: Human Operator Cognition
owner: Human operator (Andy)
related:
  - L2: agent-skills/grill-after-validation/SKILL.md
  - L2: AGENTS.md
tags: [meta-adr, validation-events, framing-grill, operator-cognition]
---

# MADR-0001: Validation Events Trigger Framing Grill

## Context

AI Radar's existing reflection mechanisms (`grill-before-sprint`,
`grill-before-absorb`, ADR-0010 admission gate) were designed under an
implicit baseline: "I might be drifting."

External validation events change this baseline. A validation event is any
external signal - a frontier lab naming a pattern already implemented in AI
Radar, a respected source endorsing the architectural direction, or a paper
supporting a core design choice - that shifts the operator's stance toward "I
was roughly right."

In that stance, existing grill mechanisms may continue to run, but their grain
can silently shift from framing-level to detail-level. The operator may not
perceive the shift because the grill still appears to be running.

The convergence event of 2026-06-04, where Anthropic's "A harness for every
task" named primitives already implemented in AI Radar, surfaced this risk.
This MADR is the structural response.

This is not a system-layer concern. No service executes it. It binds the human
operator's cognitive discipline.

## Decision

Any validation event must surface a framing-level review reminder before any
new ADR, MADR, service, or skill is added to AI Radar.

The review is conducted via
`agent-skills/grill-after-validation/SKILL.md`. This MADR establishes the
obligation; the skill defines the execution.

The authority model is:

- surfacing the reminder is mandatory
- invoking the grill is the human operator's choice
- if the operator declines, Codex must write a declined validation record under
  `docs/cognitive-log/validation/`
- the declined record activates a 72-hour retroactive framing-review label for
  subsequent architecture, ADR, MADR, service, or agent-skill changes

Declined reminder records use:

All timestamps in cognitive-log validation records use UTC with a trailing `Z`.

```text
Date: YYYY-MM-DDTHH:MM:SSZ
Triggered by: [validation event]
Authority: MADR-0001
Status: declined
Retroactive review label active until: YYYY-MM-DDTHH:MM:SSZ
```

A validation event is defined as any of:

1. A frontier lab, paper, or recognized source names, endorses, or structurally
   parallels an existing AI Radar framing-level design choice.
2. The operator cites "X also does this", "convergence with Y", or equivalent
   language to justify an AI Radar design choice.
3. The operator's internal narrative shifts from "I might be wrong" to "I was
   right" about an architectural decision due to external validation.

## Owns

- The obligation to surface validation events as a distinct event class
- The requirement that framing-level, not detail-level, grill is the response
- The mandatory reminder / optional invocation authority model
- The 72-hour retroactive review label when the reminder is declined

## Does Not Own

- The execution mechanics of the grill itself, owned by
  `agent-skills/grill-after-validation/SKILL.md`
- Detection during Codex sessions, owned by `AGENTS.md` Validation Event
  Detection
- Judging whether the validation itself is factually correct
- Decisions about whether to act on grill outputs

## Consequences

Positive:

- Preserves framing-level reflection even when external validation raises
  confidence
- Turns convergence events into recorded learning artifacts rather than silent
  confidence boosts
- Keeps external validation separate from internal architectural commitment
- Preserves the epistemic stance under which AI Radar's verification spine was
  designed

Negative / accepted trade-offs:

- Adds a pause to momentum-driven decisions
- Can ritualize if the grill becomes a checkbox
- Adds a Meta-ADR file class that must not proliferate
- Creates a new ambiguity: who counts as "external" when Codex cites an
  external source during architecture discussion

Neutral observations:

- This MADR is itself the product of a framing-level grill triggered by the
  2026-06-04 convergence event.
- Future invocations should normally produce cognitive-log records, not new
  MADRs.

## Open Questions

- Future MADR-0002 may need to answer who counts as "external", especially
  when Codex introduces or cites an external source during architecture
  discussion.
