# AI Radar as an Epistemic Trust Layer

Last updated: 2026-05-30
Status: advisory positioning, not normative architecture
Admission result: ADR-0010 modified admission

## Purpose

This document records a positioning frame for AI Radar in relation to agent
coordination protocols such as Foundation Protocol, MCP, A2A, or similar future
protocol layers.

It is intentionally advisory. It does not create a new ADR, modify runtime
gates, add CI enforcement, or change `AGENTS.md` invariants.

Use it to answer:

1. What role does AI Radar play if agent ecosystems develop coordination
   protocols?
2. Which parts of the current system support that role today?
3. Which parts are only positioning language, partial implementation, or future
   design work?
4. What should AI Radar explicitly not own?

## Positioning

AI Radar is not an agent coordination protocol.

It does not define how agents identify each other, discover one another, route
messages, form organizations, meter work, or settle economic claims.

AI Radar's stronger role is:

> AI Radar is an Epistemic Trust Layer: a system that turns external information
> flow into reviewable, evidence-aware intelligence and gates downstream action
> through verification metadata.

The useful metaphor is an epistemic notary, with one caution: the metaphor must
not overstate current implementation. Some notary-like actions are implemented
today; others are partial or not yet defined.

## Relation To Coordination Protocols

Agent coordination protocols mostly address identity, addressing, routing,
session, organization, permission, audit, and settlement surfaces.

AI Radar addresses a different trust problem:

| Concern | Coordination protocol layer | AI Radar |
|---|---|---|
| Trust target | Actor, credential, session, message, process | Claim, evidence, insight, downstream action |
| Central question | Who said it, over which channel, under which policy? | What is claimed, what supports it, what can safely follow? |
| Primary risk | Impersonation, routing failure, unauthorized action | Unsupported claims driving downstream decisions |
| Best interface | Entity envelope, route, session, audit event | Evidence pack, verification metadata, action eligibility |

AI Radar can consume protocol metadata if upstream systems provide it, and its
verified outputs could later be wrapped in an external envelope. It should not
become the protocol that defines agent identity or transport.

## Current Grounded Shape

Current implementation supports part of the epistemic trust positioning:

- Claim registration exists through claim extraction.
- Notarization exists through claim verification and support status.
- Issuance exists through verified insight metadata emitted with generated
  insights.
- Evidence custody exists partially through evidence packs, source excerpts,
  evidence links, and source-span work, but remains governed by ADR-0011 style
  source-excerpt policy.
- Revocation is not a clean verified-insight revocation mechanism today.
  Current equivalents are review outcomes, rejected/dismissed records, watch
  follow-up, action lifecycle, calibration events, and rejected-learning context.

This means the notary metaphor is useful only if it is stated honestly:

| Notary-like action | Current status | Current implementation shape |
|---|---|---|
| Registration | Present | Claim extraction and typing |
| Notarization | Present | Claim verification with support status |
| Issuance | Present but embedded | Verified insight metadata inside insight output |
| Custody of evidence | Partial | Evidence packs, excerpts, links, span-oriented policy |
| Revocation | Not yet a single mechanism | Review outcomes, lifecycle, calibration, rejected learning |

## Four-Plane Narrative

The following planes are a positioning narrative and review vocabulary, not a
claim that the current codebase is already cleanly separated this way.

| AI Radar plane | Owns | Current caveat |
|---|---|---|
| Claim Plane | Content entities and extracted claims | Claim extraction is real, but claim identity is not yet a full registry |
| Verification Plane | Evidence sufficiency, claim support, source traceability | Stronger than other planes, but source-span policy is still evolving |
| Insight Plane | Which insights can enter review, watch, or action paths | Intertwined with Project Takeaway and Action workflows |
| Audit Plane | Review records, calibration, lifecycle, and metrics | Distributed across several services, not one audit subsystem |

The intended dependency direction is:

```text
Claim -> Verification -> Insight -> Audit
```

Today, this is a review ideal rather than a fully enforced module boundary.

## Verified Insight Service Boundary

`verified_insight_service` should be described carefully:

- It is not a cache layer.
- It is not merely a query layer.
- It is an action-eligibility metadata issuer.
- It is not yet a single runtime Policy Enforcement Point.

Current enforcement is distributed. `allowed_downstream_actions` and
`blocked_downstream_actions` are generated with verified insight metadata, then
read by downstream policy readers and Project Takeaway / review / action paths.

The safe invariant is:

> Ordinary Project Takeaway confirmation and low-risk Action paths must pass
> verification metadata and action eligibility checks.

The unsafe overstatement is:

> Every downstream action must trace to one verified insight that explicitly
> allows it.

That stronger statement would incorrectly collapse legitimate exception paths.

## Legitimate Exception Paths

Any future hard invariant must define its exception paths at the same time as
the rule. Otherwise the invariant will either block valid work or encourage
workarounds.

Current legitimate exception paths include:

- `manual_project_takeaway_override`: explicit, auditable, exceptional human
  override.
- `knowledge_convergence_review_candidate`: review context, not low-risk
  Action evidence by default.
- `unverified_manual_entry`: allowed to exist as unverified/manual context, but
  not clean claim support.
- `watch_only`: observation and monitoring path for limited evidence.
- legacy, fixture, demo, and test records: must be classified honestly before
  being treated as real intelligence-flow evidence.

Meta-principle:

> Invariants must include explicit legitimate exceptions. A hard rule without
> exception semantics is fragile governance.

## Does Not Own

AI Radar should remain orthogonal to coordination protocols.

It does not own:

- agent identity management
- inter-agent transport
- routing or discovery protocols
- session, organization, and role abstractions for agent societies
- metering, settlement, or economic primitives
- universal protocol envelopes
- protocol-level dispute resolution

If future work needs these surfaces, AI Radar should consume or emit compatible
metadata rather than define the coordination layer itself.

## Promotion Ladder

This positioning can become stronger only when the trigger justifies it.

| Level | Container | Trigger |
|---|---|---|
| Advisory | This document and trigger watchlist | Current state |
| Architecture decision | ADR | Positioning starts shaping interfaces, schema, public claims, or project identity |
| Agent instruction | `AGENTS.md` | Agents repeatedly bypass this boundary 2-3 times, or user explicitly requests hard process |
| CI / checker | Script or CI rule | A narrow, machine-checkable boundary is repeatedly violated and has clear exceptions |
| Runtime gate | Product code | Existing distributed enforcement creates real ambiguity or bypass risk |

## Current Decision

The current decision is to keep this as advisory positioning.

Do not add:

- a new ADR
- `AGENTS.md` hard invariant
- CI enforcement
- directory restructuring
- runtime gate changes
- schema changes

without a separate trigger and approval.
