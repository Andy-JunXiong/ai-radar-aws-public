# AI Radar Glossary

Last updated: 2026-05-14

This glossary is a lightweight domain reference for stable AI Radar terms. Use
it when a term is ambiguous or when a planning / implementation discussion needs
a canonical name. Do not treat this file as required startup reading for every
sprint.

## Verified Insight

A structured intelligence judgment produced from evidence sufficiency and claim
verification results, carrying verification status, confidence, claim support,
and downstream action policy.

Reference: [Reasoning and Verification Requirements](./4_18_ai_radar_reasoning_verification_requirements.md#55-verified-insight)

## Evidence Pack

The traceable evidence container attached to a signal or insight, including the
source material and provenance used to evaluate whether claims can be supported.

Reference: [Reasoning and Verification Requirements](./4_18_ai_radar_reasoning_verification_requirements.md#51-evidence-pack)

## Claim Support Status

The canonical support labels for a verified claim: `directly_supported`,
`partially_supported`, `inferred`, `unsupported`, and `contradicted`.

Reference: [Reasoning and Verification Requirements](./4_18_ai_radar_reasoning_verification_requirements.md#175-claim-verification-rules)

## allowed_downstream_actions

The actions a verified insight is eligible to enter automatically or with normal
review, based on evidence quality, claim support, and confidence.

Reference: [Reasoning and Verification Requirements](./4_18_ai_radar_reasoning_verification_requirements.md#177-downstream-action-gate)

## blocked_downstream_actions

The actions a verified insight must not enter through ordinary flows because the
evidence, claim support, confidence, or verification status is not strong enough.

Reference: [Reasoning and Verification Requirements](./4_18_ai_radar_reasoning_verification_requirements.md#177-downstream-action-gate)

## Project Takeaway Candidate

A reviewable proposal that a verified or manually reviewed intelligence item may
become durable project memory, subject to Project Takeaway review gates.

Reference: [AI Radar Product Spec](../AI_RADAR_PRODUCT_SPEC.md#project-takeaway-review-loop)

## Unverified Manual Entry

A manual-source intelligence entry that lacks verification metadata and is
therefore marked as requiring verification before it can support ordinary
Project Takeaway or low-risk Action paths.

Reference: [AI Radar Product Spec](../AI_RADAR_PRODUCT_SPEC.md#1-stronger-intelligence-quality-control)

## Low-Risk Action Candidate

An action proposal that can be considered only when downstream action gates allow
it; unsupported, contradicted, weak, or insufficiently verified claims block this
path unless an explicit override route is used.

Reference: [Reasoning and Verification Requirements](./4_18_ai_radar_reasoning_verification_requirements.md#11-downstream-action-rules)
