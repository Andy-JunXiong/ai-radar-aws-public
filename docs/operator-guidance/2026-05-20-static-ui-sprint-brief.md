# Static Operator Guidance UI Sprint Brief

Date: 2026-05-20
Related:
- ADR-0006 Operator Guidance Layer
- `docs/operator-guidance/state-action-map.yaml`
- `docs/cognitive-log/2026-05-20-operator-guidance-layer.md`
- `agent-skills/grill-before-sprint/SKILL.md`

## Proposal

Build the smallest static admin/operator surface that makes the current
operator guidance map visible in the product UI.

## Grill Before Sprint

### 1. What concrete AI Radar gap does this close?

AI Radar has approved state guidance in docs, but the operator cannot see it at
the moment of work. The gap is not missing intelligence; it is missing visible
operating context near review and completion workflows.

### 2. Why should this happen now instead of staying in backlog or observation?

ADR-0006 already created three real guidance entries from current friction. A
small static UI can test whether the map is useful before committing to backend
runtime storage, LLM fallback, or user-facing guidance.

### 3. What is the smallest useful slice that proves the direction?

Add one admin/operator-only static guidance page or panel that renders the
three existing map entries:

- `manual_source.completed_to_project_memory`
- `verified_insight.blocked_downstream_actions_present`
- `knowledge_convergence.review_candidate_pending`

The first slice can use a local frontend constant copied from the current map,
with clear references back to ADR-0006 and the docs mapping.

### 4. What could this accidentally mix, weaken, or make harder to maintain?

- It could make docs guidance look like verified evidence.
- It could imply that citation means truth.
- It could expose admin-only language to ordinary users.
- It could drift from `docs/operator-guidance/state-action-map.yaml`.
- It could tempt the project to add LLM fallback before traceability and
  no-mutation boundaries are designed.

### 5. What validation would prove the slice worked without relying on vibes?

- Frontend lint/build passes for the changed page.
- The UI shows exactly the three current guidance entries.
- Each entry separates applies-when, next actions, not-allowed actions, and
  governing sources.
- The page copy makes clear that guidance is operator guidance, not evidence or
  verification.
- Browser check confirms the page loads from an admin/operator route and does
  not alter Review, Knowledge, Project Takeaway, verification, or override
  behavior.

## Outcome

narrow

The direction is worth testing, but only as a static UI experiment. Do not
expand into runtime storage, LLM fallback, or state mutation.

## Implementation Contract

Final goal:
- add a static admin/operator guidance surface for the three current mapping
  entries

Non-goals:
- no LLM fallback
- no backend runtime storage
- no ordinary user-facing guidance
- no schema changes
- no Project Takeaway gate changes
- no verification, override, or `blocked_downstream_actions` behavior changes
- no `.github/workflows/` changes
- no AWS, S3, deploy, commit, push, or PR action

Changed files or ownership area:
- likely `frontend/app/admin/operator-guidance/page.tsx`
- optional link from `frontend/app/admin/page.tsx` or root operating home only
  after inspecting existing navigation density

Validation commands:
- `npm.cmd run lint -- app\admin\operator-guidance\page.tsx`
- `npm.cmd run build`

Manual checks:
- open `http://127.0.0.1:3000/admin/operator-guidance`
- confirm the three known state entries are visible
- confirm each entry shows applies-when, next actions, not-allowed actions, and
  governing sources
- confirm the page states, through UI structure/copy, that this is
  admin/operator guidance rather than evidence or verification
- confirm existing Review, Knowledge, and Metrics pages still open normally

Definition of done:
- the static page exists and loads locally
- the three current map entries are represented accurately
- no runtime intelligence behavior changed
- no new source of truth is introduced beyond the existing docs mapping
- validation commands pass
