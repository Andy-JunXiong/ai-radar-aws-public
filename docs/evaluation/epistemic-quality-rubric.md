# Epistemic Quality Rubric

Date: 2026-05-30
Status: advisory rubric, not a gate
Scope: Knowledge Honesty x Transmission Adaptability

## Purpose

Verification asks whether claims have evidence support. Epistemic quality asks
whether the content's framing honestly represents the state of knowledge and
whether its simplification helps or distorts understanding.

This rubric is advisory. It does not change `verified_insight`, Project
Takeaway eligibility, claim support, or downstream action gates.

## Axis 1: Knowledge Honesty

Knowledge Honesty measures whether content accurately reflects boundaries,
uncertainty, category, and relationship to existing knowledge.

Labels:

- `high`: states scope and uncertainty; distinguishes demo, research,
  production, opinion, and trend; avoids overclaiming.
- `medium`: mostly accurate but misses some caveats, category boundaries, or
  uncertainty language.
- `low`: facts may be individually supportable, but framing exaggerates,
  collapses categories, hides uncertainty, or implies a stronger conclusion
  than the evidence supports.
- `unknown`: not enough content or context to judge.

Common low-honesty signals:

- treats a demo as a production paradigm
- treats a single case as a general industry shift
- uses "revolution", "paradigm", "solved", "inevitable", or equivalent strong
  terms without evidence scope
- omits that the result is benchmark-only, vendor-authored, or early-stage
- blurs factual claims with interpretation or strategy

## Axis 2: Transmission Adaptability

Transmission Adaptability measures whether simplification, analogy, visuals, or
format choices preserve the original idea while making it easier to use.

Labels:

- `high`: simplifies without distorting; makes boundaries easier to see; helps
  the operator decide what to do next.
- `medium`: useful but loses some nuance or over-compresses relationships.
- `low`: packaging, visual framing, analogy, or headline changes the meaning or
  pushes the reader toward a misleading takeaway.
- `unknown`: not enough content or context to judge.

Common low-adaptability signals:

- attractive infographic hides critical caveats
- metaphor replaces the actual mechanism
- headline implies causality or maturity not present in the source
- compressed summary removes the only important limitation

## Four Quadrants

| Knowledge Honesty | Transmission Adaptability | Interpretation |
|---|---|---|
| high | high | strong educational or intelligence artifact |
| high | low | accurate but difficult, dense, or poorly adapted |
| low | high | compelling but misleading; high-priority advisory review |
| low | low | low-quality noise or confused content |

## Required Reviewer Notes

Every reviewed case should include:

- the main claim or framing being judged
- what evidence or source context supports the judgment
- uncertainty or missing context
- whether the issue is factual verification, epistemic framing, transmission
  simplification, or a mix

## Stop Conditions

Pause before moving from advisory review to product behavior if the next step
would:

- add fields to verified insight schema
- affect Project Takeaway review or action eligibility
- introduce an LLM scorer into production paths
- change prompt contracts for Generate Insight
- add UI labels that users may treat as verification status
