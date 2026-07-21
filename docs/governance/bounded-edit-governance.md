# Bounded Edit Governance

Date: 2026-05-28
Status: guidance scaffold, not CI enforcement
Scope: high-risk agent-authored edits

## Purpose

Bounded edit governance keeps high-risk AI-assisted changes small enough to
review. It borrows SkillOpt's add / delete / replace discipline without
importing the full optimizer loop.

## Applies First To

- invariant documents
- prompt and guidance documents
- Operator Guidance routing or contract data
- Project Takeaway review-policy documents
- agent skills under `agent-skills/`

## Rule

For high-risk governance surfaces, each proposed edit should be expressible as
one of:

- `add`: insert a bounded block
- `delete`: remove a bounded block
- `replace`: replace one bounded block with another bounded block
- `skip`: explicitly decline a proposed edit

Each edit should carry:

- target path
- bounded target identifier or line anchor
- rationale
- expected behavior change
- validation performed
- accept / skip decision

## Non-Goals

- no `.github/workflows/` change
- no automatic CI hard gate
- no broad repo refactor
- no bypass of runtime verification gates

## Upgrade Path

This starts as documentation and local reporting only. A hard gate should not be
considered until:

- the report shape is stable
- false positives have named categories
- human maintainers explicitly approve enforcement
- the target surface is narrow enough to avoid blocking routine development
