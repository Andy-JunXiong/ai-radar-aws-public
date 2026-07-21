# Architecture Decision Records

This directory records the major architecture decisions for AI Radar. An ADR
is an immutable historical record: when a decision changes materially, create
a new ADR that supersedes the old one instead of rewriting the old decision.

## ADR format

Each ADR should contain:

- **ADR Gate**: the three-condition admission check for a new ADR
- **Context**: the problem and trigger
- **Decision**: the decision that was made
- **Owns**: the boundary governed by the ADR
- **Does Not Own**: related boundaries governed elsewhere
- **Consequences**: benefits, costs, and known risks
- **Alternatives Considered**: rejected options and reasons
- **Implementation Plan**: the delivery sequence
- **References**: supporting material

## Status values

- **Proposed**: drafted and awaiting implementation evidence
- **Accepted**: implemented and validated
- **Deprecated**: still historically valid but not recommended for new work
- **Superseded by ADR-XXXX**: replaced by a newer decision

## ADR index

| ID | Title | Status | Created |
|---|---|---|---|
| [0001](./0001-agent-managed-deployment.md) | Agent-Managed Deployment Architecture | Proposed | 2026-04-30 |
| [0002](./0002-hypothesis-monitoring-boundary.md) | Hypothesis Monitoring Boundary | Proposed | 2026-05-15 |
| [0003](./0003-runtime-agnostic-skill-registry.md) | Runtime-Agnostic Skill Registry | Accepted | 2026-05-17 |
| [0004](./0004-agents-constitution-skill-registry.md) | AGENTS.md Constitution and Skill Registry | Proposed | 2026-05-17 |
| [0005](./0005-dual-gate-pre-sprint-protocol.md) | Dual-Gate Pre-Sprint Protocol | Proposed | 2026-05-17 |
| [0006](./0006-operator-guidance-layer.md) | Operator Guidance Layer | Proposed | 2026-05-19 |
| [0007](./0007-incident-attribution-skill.md) | Incident Attribution Agent Skill | Accepted | 2026-05-19 |
| [0008](./0008-signal-lifecycle-event-spine.md) | Signal Lifecycle Event Spine | Proposed | 2026-05-21 |
| [0009](./0009-model-provenance-schema.md) | Model Provenance Schema | Accepted | 2026-05-22 |
| [0010](./0010-external-insight-admission-gate.md) | External Insight Admission Gate | Accepted | 2026-05-28 |
| [0011](./0011-evidence-pack-source-excerpt-policy.md) | Evidence Pack Source Excerpt Policy | Accepted | 2026-05-28 |
| [0012](./0012-signal-claim-review-feedback-capture.md) | Signal Claim Review Feedback Capture | Accepted | 2026-06-13 |
| [0013](./0013-ai-discussion-governed-claim-boundary.md) | AI Discussion Governed Claim Boundary | Accepted | 2026-06-24 |
| [0015](./0015-claim-set-composition-underdetermination-gate.md) | Claim-Set Composition Underdetermination Gate | Proposed | 2026-07-05 |
| [0016](./0016-action-loop-stagnation-protocol.md) | Action-Loop Stagnation Protocol | Proposed | 2026-07-05 |

## Adding an ADR

1. Copy `TEMPLATE.md`.
2. Use the next permanent number; never reuse a deleted number.
3. Name the file `NNNN-kebab-case-title.md`.
4. Complete the ADR Gate and proceed only when all three conditions pass.
5. Add the ADR to this index.
6. Record related operational, narrative, or capability assets in frontmatter.

The ADR Gate applies to new ADRs. It is not applied retroactively.

## Cross-layer relationships

ADRs are engineering-decision records. They may produce operational runbooks,
public explanations, or capability reflections. Maintain those relationships
through each document's `related` metadata without merging their purposes.
