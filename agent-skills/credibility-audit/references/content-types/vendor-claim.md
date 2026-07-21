# Vendor Claim Playbook

Use this reference for launch posts, product pages, marketing claims, benchmark
cards, and vendor-authored articles.

## Checks

1. Identify whether the vendor is making a factual, capability, benchmark,
   roadmap, or positioning claim.
2. Separate "the vendor says X" from "X is true in practice."
3. Check for benchmark scope, dataset, date, model/version, and evaluation
   method when they carry the verdict.
4. Look for missing caveats: availability, pricing, region, plan tier,
   platform, preview/beta status, and dependency constraints.
5. If the claim affects buying, implementation, legal, security, or roadmap
   decisions, verify against authoritative current docs.

## Common Distortions

Use canonical tags when they fit:

- `[canonical] caveat_stripping`: benchmark or availability limits omitted.
- `[canonical] causal_overreach`: customer outcome attributed to product
  without support.
- `[canonical] pseudo_precision`: a precise metric used beyond its evaluation
  setup.
- `[canonical] category_collapse`: demo, preview, roadmap, and shipped product
  blurred.
- `[canonical] source_asserted_but_unsubstantiated`: vendor statement treated
  as external verification.

Use promotion-layer specimen terms when the vendor framing is the main issue:

- `[specimen] scope_inflation`
- `[specimen] valence_inflation`
- `[specimen] terminology_laundering`
- `[specimen] framework_density_inflation`
- `[specimen] effort_asymmetry_framing`

Specimen terms must be labeled `[specimen]` and located with
`@ promotion-layer/...`. They are audit labels, not canonical AI Radar
distortion tags. Use the closed location set from
`references/distortion-taxonomy.md`; if no sublocation fits, use
`@ promotion-layer`.

## Action Choices

- verify against official docs
- read benchmark methodology
- ask for source data
- save as vendor-self-report only
- reject as marketing noise
