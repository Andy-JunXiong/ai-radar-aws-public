---
name: credibility-audit
description: |
  Use when reviewing external content before trusting, adopting, citing, or turning it into AI Radar work. Apply to social posts, screenshots, GitHub READMEs, marketing pages, vendor claims, articles, framework claims, and tool recommendations when the user asks whether the content is real, credible, useful, distorted, or worth absorbing. The protocol separates value from provenance, verifies load-bearing facts against primary sources when needed, and reports distortion patterns without taking downstream action.
status: experimental
intended_consumers:
  - codex-cli
  - claude-code
---

# Credibility Audit

Use this protocol to judge external content without collapsing two separate
questions:

```text
VALUE: what is useful here if the claim is true?
PROVENANCE: how much trust does the source earn?
```

Never let one axis contaminate the other. A low-trust source can contain a real
signal. A high-trust source can contain a trivial or irrelevant idea.

## Boundary

This is a read-only review protocol. It does not:

- rewrite the source
- create AI Radar product scope
- modify `verified_insight`
- modify Project Takeaway or Action eligibility
- treat popularity, stars, engagement, or polished prose as truth
- bypass ADR-0010 when an external idea may enter AI Radar scope

If the audit leads to a possible AI Radar feature, architecture change,
workflow, agent protocol, durable method, or implementation task, run the
ADR-0010 admission gate before recommending implementation.

## Trigger

Use this protocol when the user asks whether to trust, believe, adopt, cite, or
absorb an external artifact, including casual prompts such as:

- "is this real?"
- "should I believe this?"
- "is this useful?"
- "can AI Radar learn from this?"
- "does this repo actually do what the post says?"
- "look at this card / README / vendor claim"

For a proposal that makes claims about current AI Radar repo files, run
`context-first-review` as well.

## Process

1. Identify the artifact type and the concrete assertion.
   - For screenshots, transcribe the load-bearing claim before reasoning.
   - Separate artifact-body claims from promotion-layer claims.

2. Extract VALUE first.
   - State the strongest useful insight in one sentence.
   - Do not grade provenance during this step.
   - If no transferable value exists, say so plainly.

3. Grade PROVENANCE separately.
   - Use `references/provenance-tiers.md`.
   - Prefer primary or authoritative sources over summaries, listicles, and
     engagement-bait.
   - Do not turn provenance into truth. Provenance says where a claim came
     from, not whether the claim is correct.

4. Detect distortions.
   - Use `references/distortion-taxonomy.md`.
   - Name the tag registration status, the tag or specimen term, and the
     location where it appears.
   - Keep registration status and location separate:
     - status is `[canonical]` or `[specimen]`
     - location starts with `artifact-body` or `promotion-layer`

5. Verify load-bearing facts.
   - Check facts that the verdict depends on against primary sources when
     available.
   - If current or unstable facts matter, browse or fetch authoritative
     sources.
   - If verification is not possible, mark the fact `unverified`; do not
     upgrade memory or marketing copy to fact.

6. Produce a verdict and a single next action.

## Reference Routing

Read only the references needed for the artifact:

- `references/value-axis.md`: how to extract value before provenance.
- `references/provenance-tiers.md`: current AI Radar provenance-tier guidance
  and source-of-truth caveats.
- `references/distortion-taxonomy.md`: current advisory distortion tags and
  known drift from older working sets.
- `references/content-types/social-post.md`: screenshots, social cards,
  Reddit/X/Xiaohongshu-style posts, and engagement-heavy claims.
- `references/content-types/readme.md`: GitHub README or repository claims.
- `references/content-types/vendor-claim.md`: marketing pages, launch posts,
  landing pages, and product claims.
- `examples/before-after.md`: concise worked examples for regression checking.

## Output Format

Use this compact format:

```text
VALUE: <one sentence with the strongest useful insight, if true>
PROVENANCE: <tier or source posture> - <why this source earns that posture>
DISTORTIONS: <none, or one item per line: [status] tag @ location - discount>
VERIFY: <load-bearing fact> -> verified | unverified | refuted
DISCOUNT: <what the reader should mentally subtract>
ACTION: <single next step>
```

For distortions, use one item per line when any are present:

```text
DISTORTIONS:
- [canonical] caveat_stripping @ promotion-layer/headline - <discount implied>
- [specimen] scope_inflation @ promotion-layer/title - <discount implied>
```

`[canonical]` means the tag is in AI Radar's current advisory
`DISTORTION_TAGS` set. `[specimen]` means the term is a governed
promotion-layer specimen term, not a canonical AI Radar tag. Do not use
`[promotion]` as a status. Location is a separate axis: use `artifact-body` or
`promotion-layer`. Allowed concrete sublocations are:

- `promotion-layer/headline`
- `promotion-layer/title`
- `promotion-layer/social-card`
- `promotion-layer/marketing-copy`
- `promotion-layer/benchmark-card`
- `artifact-body/README`
- `artifact-body/docs`
- `artifact-body/benchmark-methodology`
- `artifact-body/source-code`
- `artifact-body/test`

If none fits, use only the main location axis.

If the artifact may enter AI Radar as product, architecture, workflow, or
agent-protocol work, add:

```text
ADR-0010: admit | replace | inbox | reject - <smallest scope>
```

## Stop Conditions

Pause and ask for user review before:

- implementing from the audit
- creating or changing an ADR
- adding a new taxonomy item
- treating the audit as evidence for an external factual claim
- installing this skill outside the repo
- uploading private content to an external service
