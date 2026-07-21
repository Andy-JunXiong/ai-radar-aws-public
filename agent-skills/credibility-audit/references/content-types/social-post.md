# Social Post Playbook

Use this reference for screenshots, social cards, Xiaohongshu-style posts,
Reddit comments, X threads, listicles, and viral recommendation posts.

## Checks

1. Transcribe the load-bearing claim before judging it.
2. Separate the card/post claim from the source artifact it references.
3. Treat engagement as value-routing metadata, not credibility.
4. Verify repo names, star counts, dates, quotes, and numeric claims against
   primary sources when they matter.
5. Look for promotion-layer distortions even when the underlying artifact is
   clean.

## Common Distortions

Use canonical tags when they fit:

- `[canonical] pseudo_precision`: exact numbers presented as typical or
  general.
- `[canonical] juxtaposition_fusion`: repo popularity, author status, and
  specific feature claims placed together without proof.
- `[canonical] caveat_stripping`: limits removed from a README, paper, docs
  page, or headline.
- `[canonical] category_collapse`: popularity treated as evidence of truth or
  fit.
- `[canonical] source_asserted_but_unsubstantiated`: first-party claims treated
  as observed implementation facts.

Use promotion-layer specimen terms when the card's main distortion is
rhetorical framing:

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

## Output Bias

Be crisp. The user usually needs a decision:

- read primary source
- ignore card
- save as specimen
- run deeper repo inspection
- route through ADR-0010
