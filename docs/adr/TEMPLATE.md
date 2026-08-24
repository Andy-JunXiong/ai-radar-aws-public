---
adr: NNNN
title: Short Decision Title
status: Proposed
created: YYYY-MM-DD
layer: L1-engineering-solution
related: []
tags: []
---

# ADR-NNNN: Short Decision Title

## ADR Gate

Create this ADR only if all are yes:

- [ ] Hard to reverse: changing this later has meaningful cost
- [ ] Context would be lost: future readers would ask why this choice was made
- [ ] Real tradeoff: there were plausible alternatives

If any answer is no, prefer a lighter planning note, status update, or runbook
entry instead of creating an ADR.

## Origin & Admission

Record the decision provenance. Do not rely on chat history or uploaded
attachments alone.

- Origin type: `user_request | observed_usage_gap | incident | external_source | existing_invariant | technical_constraint`
- Trigger / source references:
- Observed internal pressure:
- Borrowed pattern (if any):
- AI Radar authorial delta:
- ADR-0010 outcome: `not_applicable_internal | admit | replace`
- Replaces or simplifies:
- Human decision owner:
- Resulting scope:
- Implementation references:

For an external origin, complete ADR-0010 before drafting the Decision. An
`inbox` or `reject` outcome means the proposal does not proceed to an
implementation ADR. Decision provenance does not make a source product
evidence or grant implementation authority.

## Context

What decision pressure, operational risk, product change, or architectural
constraint made this decision necessary?

## Decision

What did we decide? Be specific about the chosen path and its boundary.

## Owns

What does this ADR explicitly decide or govern?

## Does Not Own

What related topics, implementation details, or future decisions are outside
this ADR's scope?

## Consequences

What becomes easier? What becomes harder? What new risks or maintenance costs
does this introduce?

## Alternatives Considered

What plausible alternatives were rejected, and why?

## Implementation Plan

What needs to change for this decision to become real? Keep this as a plan, not
a full runbook.

## References

- Link to related status docs, runbooks, product specs, incidents, or external
  references.
