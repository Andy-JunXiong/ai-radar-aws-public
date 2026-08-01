---
adr: 0002
title: Hypothesis Monitoring Boundary
status: Proposed
created: 2026-05-15
layer: L1-engineering-solution
related:
  - L2: ai-radar/AGENTS.md
  - L2: ai-radar/DEVELOPMENT_PLAN.md
tags: [hypothesis-watch, monitoring-boundary, verification, strategic-intelligence]
---

# ADR-0002: Hypothesis Monitoring Boundary

## ADR Gate

Create this ADR only if all are yes:

- [x] Hard to reverse: creating a monitoring subsystem without clear boundaries would shape future schema, ingestion, and review flows
- [x] Context would be lost: future readers would ask why AI Radar tracks some strategic hypotheses without immediately activating monitors
- [x] Real tradeoff: we could implement a full state-monitor directory now, keep this only as a planning note, or define the boundary first

## Context

AI Radar increasingly receives strategic observations that are not ordinary
single-source signals. Some are hypothesis-shaped: they ask whether a pattern is
emerging across vendors, product categories, or technical architectures over a
time window.

One proposed example is `agent-team-skill-loop-watch`: tracking whether AI
workspace products converge on Agent Team orchestration, Skill persistence, and
inter-Agent Verifier mechanisms as a joint co-occurrence pattern. The valuable
signal is not any one feature in isolation, but whether multiple vendors ship
the loop together within a defined window.

The repository does not yet have a `signal/state-monitor/` subsystem or a
baseline `harness-absorption-watch` schema to mirror. Creating the proposed
watch directly would therefore invent a monitoring architecture before the
boundary is clear.

AI Radar also has hard intelligence-quality constraints: reflection and
strategic analysis can provide context, but they must not be treated as factual
evidence for external claims without an explicit evidence conversion path.
Project Takeaway gates and verification metadata remain hard boundaries.

## Decision

Define a lightweight hypothesis-monitoring boundary before creating any
state-monitor subsystem.

AI Radar may record a **hypothesis watch** when a strategic observation needs to
be tracked over time, but the default status is **proposed**, not active.
Proposed hypothesis watches are planning and review objects. They do not run
scrapers, collectors, monitors, scheduled jobs, or automatic downstream actions.

This boundary distinguishes two Watch categories:

```text
evidence_followup  !=  hypothesis_monitor
```

An `evidence_followup` is a project-scoped, human-created follow-up task whose
origin is an eligible Signal. It schedules human review and stores
human-accepted observations. After Generate Insight succeeds, a deterministic
matcher may compare that Signal with active evidence follow-ups and create an
explainable `review_candidate_only` attention item. It does not run a scheduled
monitor, activate a collector, or evaluate whether a strategic hypothesis is
becoming true.

A `hypothesis_monitor` is the deferred active-monitoring category. Scheduled
evaluation, raw-ingestion-triggered alerts, LLM or embedding matching, and topic
or entity monitoring belong to that category and remain unapproved by this
ADR. The post-Generate-Insight deterministic matcher is not a hypothesis
monitor: it creates no Observation until a human accepts the candidate, and it
does not change evidence, verification, or downstream eligibility.

An evidence-followup Observation is always review context:

```text
evidence_role = review_context_only
```

The number or accumulation of Observations must not change verification status,
count as claim support, create Project Takeaway or Action eligibility, or bypass
`blocked_downstream_actions`. Any promotion into stronger evidence semantics
requires an explicit evidence and verification path.

A hypothesis watch is allowed to own:

- the hypothesis statement
- trigger, counter-evidence, and null conditions
- scope boundaries and vendor/category set under observation
- references to source signals or future evidence objects
- proposed review criteria for later activation

A hypothesis watch does not own:

- scraping or monitoring code
- quality judgment on individual implementations
- vendor winner prediction
- product recommendations
- Project Takeaway candidate creation
- low-risk Action eligibility
- bypassing verification or blocked downstream gates

An `evidence_followup` additionally does not own:

- scheduled or collector-level related-Signal discovery
- automatic acceptance of a related-Signal candidate
- verification-status mutation
- claim-support accumulation
- Project Takeaway candidate creation
- Action creation or eligibility

Activation of a `hypothesis_monitor` requires a later explicit implementation
decision. That decision should define schema, storage path, ingestion source,
review surface, and test coverage. Until then, proposed hypothesis watches
remain documentation-level objects.

## Owns

- Boundary language for hypothesis-shaped strategic monitoring.
- The distinction between proposed watches and active monitoring.
- The rule that co-occurrence hypotheses must define trigger,
  counter-evidence, and null conditions before activation.
- The rule that external analysis can trigger a hypothesis, but cannot by
  itself establish the hypothesis as verified.

## Does Not Own

- The `signal/state-monitor/` directory structure.
- A YAML schema for hypothesis specs.
- Any active monitoring rotation.
- Any scraping, browser automation, scheduled collector, or data pipeline task.
- Any Project Takeaway or Action-path eligibility.

## Consequences

This makes AI Radar more disciplined about strategic pattern tracking. We can
preserve useful hypotheses without prematurely turning them into product
features or data pipelines.

It also creates a small amount of process overhead. Future hypothesis-watch work
must first decide whether the watch remains proposed documentation or is ready
for an explicit active-monitoring implementation.

The `agent-team-skill-loop-watch` idea remains valuable, but it should be
treated as a proposed example until a baseline monitoring schema and review path
exist.

## Alternatives Considered

### Alternative 1: Implement `agent-team-skill-loop-watch` directly

Rejected for now. The requested task references a missing
`harness-absorption-watch` ADR, a missing YAML schema, and a missing
`signal/state-monitor/` directory. Implementing it directly would force this
slice to invent the foundation it was supposed to mirror.

### Alternative 2: Create the full `signal/state-monitor/` subsystem now

Rejected for now. That is a broader architectural slice than the current need.
It would require schema design, storage boundaries, activation rules, review
surfaces, and tests.

### Alternative 3: Keep the idea only in chat or planning notes

Rejected. The boundary decision is likely to recur, and future readers need a
stable explanation for why hypothesis watches are proposed before they become
active monitors.

## Implementation Plan

1. Keep project-scoped `evidence_followup` creation and candidate acceptance
   human-controlled and verification-neutral.
2. Allow only the explainable post-Generate-Insight deterministic matcher to
   create `review_candidate_only` attention items for active follow-ups.
3. Do not create `signal/state-monitor/` yet.
4. Treat `agent-team-skill-loop-watch` as a proposed future hypothesis example.
5. If a later sprint activates hypothesis monitoring, create a separate ADR or
   implementation plan covering schema, storage, review path, and validation.

## References

- [AGENTS.md](../../AGENTS.md)
- [DEVELOPMENT_PLAN.md](../../DEVELOPMENT_PLAN.md)
- Proposed example: `agent-team-skill-loop-watch`
