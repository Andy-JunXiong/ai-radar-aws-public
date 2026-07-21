# Provenance Tiers

Use this reference when grading the source posture of an external claim.

## Current Source Of Truth

AI Radar does not yet have a standalone documentation registry for a general
provenance ladder.

Current implementation-derived tier names are visible in:

- `backend/app/services/claim_verification_service.py`
- `backend/app/services/canonical_scalar_resolver_service.py`
- `tests/test_claim_verification_service.py`

Do not invent a new canonical ladder in this skill. If exact tier semantics
matter, inspect the current implementation before using a tier as canonical.

## Implementation-Derived Tier Names

Observed names include:

- `canonical_conflicted`
- `canonical_platform_delta`
- `canonical_api_observed`
- `source_self_reported`
- `third_party_summary`
- `model_inferred`
- `unknown`

Use these cautiously. They are claim-verification metadata, not a full
cross-domain trust ontology.

## Practical Review Postures

When a formal tier is not necessary, use one of these plain-language source
postures:

- `primary / authoritative`: official repo, canonical API, formal spec,
  original paper, official docs, or direct source artifact.
- `source self-report`: first-party README, launch post, vendor page, or
  author statement that states what the source claims.
- `third-party summary`: listicle, social thread, roundup, repost, or
  second-hand explanation.
- `engagement signal`: stars, likes, upvotes, comments, views, or popularity.
- `model-inferred`: generated interpretation or relationship not directly
  stated by the source.
- `unknown`: source path or authorial status cannot be established.

## Hard Distinctions

- Provenance is not truth.
- Engagement is not credibility.
- First-party self-report proves that the source says something; it does not
  prove that the implementation works.
- Canonical scalar checks can refute or downgrade precise numeric claims, but
  platform deltas may still require review.
