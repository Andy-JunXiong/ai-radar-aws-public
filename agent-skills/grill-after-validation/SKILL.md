---
name: grill-after-validation
description: |
  Use when an external validation event names, endorses, or structurally parallels an existing AI Radar framing-level design choice, especially before creating a new ADR, MADR, service, or agent skill. The skill restores framing-level interrogation after validation may have shifted the operator's confidence baseline.
status: experimental
intended_consumers:
  - codex-cli
  - claude-code
---

# Skill: Grill After Validation

## Purpose

Validation events can shift the operator's baseline from "I might be drifting"
to "I was right." Existing grill mechanisms may still run, but silently slide
from framing-level interrogation to detail-level checking.

This skill restores framing-level depth at the moment it is most likely to
erode.

Authority is established by
`docs/meta-adr/MADR-0001-validation-triggers-framing-grill.md`.

## Trigger

Offer this skill when both are true:

1. An external source has named, endorsed, or structurally paralleled an
   existing AI Radar design choice.
2. The connection is framing-level, not merely implementation detail.

Also offer it when the operator is about to write a new ADR, MADR, service, or
agent skill and the motivation references external validation. Run the skill
only after the operator accepts the surfaced reminder.

## Do Not Invoke

- For routine `grill-before-absorb` cases where the issue is cognitive
  ownership of a new concept
- For routine `grill-before-sprint` cases where the issue is project timing and
  scope
- For detail-level validation, such as using the same library or UI pattern
- For external ideas that have not been connected to an existing AI Radar
  design choice

## Procedure

### Step 1: Hold

Do not produce a new ADR, MADR, service, or skill until the operator has
accepted or declined the grill.

If accepted, continue with the four framing questions.

If declined, write a declined validation record under:

```text
docs/cognitive-log/validation/YYYY-MM-DD-<event-shorthand>-declined.md
```

Use this format:

All timestamps in cognitive-log validation records use UTC with a trailing `Z`.

```text
Date: YYYY-MM-DDTHH:MM:SSZ
Triggered by: [validation event]
Authority: MADR-0001
Status: declined
Retroactive review label active until: YYYY-MM-DDTHH:MM:SSZ
```

The declined record activates a 72-hour retroactive framing-review label for
subsequent architecture, ADR, MADR, service, or agent-skill changes.

### Step 2: Four Framing Questions

Answer each in writing.

1. **Is this validation about framing or detail?**
   Framing means the underlying problem decomposition. Detail means a specific
   implementation choice. If this is detail-level, exit and proceed normally.

2. **What assumption about AI Radar's own context, users, data, or maintenance
   burden does this validation not touch?**
   Validation of structure does not validate every assumption embedded in the
   structure.

3. **If I were starting AI Radar from zero today, with current knowledge, would
   I make the same framing choice?**
   If yes, say why specifically. If no, say what would change.

4. **Which layer of AI Radar is most ablation-fragile?**
   If one layer were removed, which would degrade output quality most visibly?
   Which would degrade it least visibly? The least-visible degradation is the
   candidate for redundant scaffolding.

### Step 3: Self-Check

Choose one:

- `found-nothing`: acceptable, but if this happens three times consecutively,
  review the skill for ritualization
- `found-something`: record what surfaced and decide whether it needs a new
  ADR, ADR revision, tracking only, or no action

### Step 4: Record

Write a short cognitive-log record:

```text
# Grill-After-Validation Record

Date: YYYY-MM-DDTHH:MM:SSZ
Triggered by: [validation event]
Authority: MADR-0001

Q1 (framing or detail): [answer]
Q2 (untouched assumption): [answer]
Q3 (would I do it again): [answer]
Q4 (ablation-fragile layer): [answer]

Action: [none / new ADR / ADR revision / tracking only]
```

Store under:

```text
docs/cognitive-log/validation/YYYY-MM-DD-<event-shorthand>.md
```

## Owns

- The four-question framing-level interrogation procedure
- The reflection record format
- The `docs/cognitive-log/validation/` output location
- The ritualization self-check

## What This Skill Does Not Do

- It does not block the user.
- It does not evaluate whether the external source is correct.
- It does not produce ADRs or MADRs autonomously.
- It does not trigger on detail-level validation.
- It does not answer who counts as external when Codex cites an external
  source; that is a future MADR question.

## Failure Modes To Avoid

- Over-detection: treating every external source mention as validation
- Under-detection: missing validation when the user clearly uses external
  endorsement to justify an existing AI Radar framing
- Reminder fatigue: surfacing the same reminder repeatedly

## Does Not Own

- Detection of validation events, owned by `AGENTS.md`
- The rule that validation events require a surfaced reminder, owned by
  MADR-0001
- Judging whether the external validation is factually correct
- Decisions to act on the record's findings
