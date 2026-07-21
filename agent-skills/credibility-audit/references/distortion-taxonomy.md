# Distortion Taxonomy

Use this reference when naming distortion patterns in external artifacts.

## Current Source Of Truth

The current code-level advisory tag set lives in:

- `backend/app/services/signal_review_feedback_service.py`
  - `DISTORTION_TAGS`

ADR-0012 also documents an initial advisory set:

- `docs/adr/0012-signal-claim-review-feedback-capture.md`

The code-level set is more current than the initial ADR example. Do not rely on
older working sets from conversation memory without reconciling them against
the service constant.

<!-- SNAPSHOT-OF: DISTORTION_TAGS @ unregistered-draft -->

## Distortion Output Axes

Keep tag registration status and location separate.

Status has exactly two values:

- `[canonical]`: the tag is present in AI Radar's current advisory
  `DISTORTION_TAGS` set.
- `[specimen]`: the term is a governed specimen term for promotion-layer audit,
  not a canonical AI Radar tag.

Location starts with one of two values:

- `artifact-body`
- `promotion-layer`

Add a concrete sublocation only when useful, for example
`promotion-layer/headline`, `promotion-layer/title`, or
`artifact-body/README`.

Allowed concrete sublocations:

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

If none fits, use only `artifact-body` or `promotion-layer`.

Never encode location as status. Do not write `[promotion]`.

## Canonical Claim-Layer Tags

As of this unregistered draft, `DISTORTION_TAGS` includes:

- `fabricated_attribution`
- `source_asserted_but_unsubstantiated`
- `pseudo_precision`
- `juxtaposition_fusion`
- `causal_overreach`
- `caveat_stripping`
- `category_collapse`
- `context_drift`
- `personal_context_mismatch`

These tags are advisory. They do not modify claim support, verification status,
Project Takeaway eligibility, or Action eligibility.

## Canonical Working Definitions

- `fabricated_attribution`: assigns a quote, position, fact, or endorsement to
  a source without support.
- `source_asserted_but_unsubstantiated`: treats a source's own claim as
  implementation fact before external or primary verification.
- `pseudo_precision`: uses precise numbers or decimal values in a way that
  implies unjustified certainty or typicality.
- `juxtaposition_fusion`: places facts side by side so readers infer a
  relationship the artifact has not established.
- `causal_overreach`: implies causation from evidence that supports only
  correlation, sequence, association, or possibility.
- `caveat_stripping`: removes limits, uncertainty, scope boundaries, or
  conditions that materially change the claim.
- `category_collapse`: blurs distinct categories such as demo vs production,
  value vs provenance, popularity vs truth, or review context vs evidence.
- `context_drift`: moves a claim into a new setting where its original support
  no longer applies.
- `personal_context_mismatch`: recommends or frames something as fit for the
  user's context when the artifact has not established that fit.

## Promotion-Layer Specimen Terms

Use these as `[specimen]` terms when the distortion is mainly promotional
framing. They are not canonical AI Radar tags.

Each term carries a name, definition, minimal example, and implied discount.

### `scope_inflation`

- Definition: expands a bounded claim into a universal, mandatory, or
  all-context claim.
- Minimal example: "must-install for every Codex user" from a general skill
  roundup.
- Discount: subtract universality and ask which context the claim actually
  supports.

### `valence_inflation`

- Definition: intensifies the emotional or outcome promise beyond what the
  source establishes.
- Minimal example: "makes AI 10x smarter" from a tool card that only lists a
  feature.
- Discount: keep the possible capability, discard the exaggerated outcome
  framing.

### `terminology_laundering`

- Definition: borrows a trusted or fashionable term to make an artifact appear
  more specific, official, or relevant than it is.
- Minimal example: labeling a generic prompt pack as a "Codex skill" without
  showing Codex-specific packaging.
- Discount: verify whether the named platform, standard, or term is actually
  involved.

### `framework_density_inflation`

- Definition: stacks framework names, primitives, or methodology labels so the
  artifact feels more rigorous than the underlying evidence supports.
- Minimal example: a card lists "agents + memory + MCP + workflow OS" while
  linking to a simple README.
- Discount: reduce the claim to the concrete mechanism shown by the primary
  source.

### `effort_asymmetry_framing`

- Definition: Infers trust or importance from claimed effort or investment
  (hours spent, iteration count, "300 hours of testing", "I read every page")
  rather than from exposed evidence. Visible effort is asymmetric with
  verification: the effort is asserted, the proof is not. Popularity, stars,
  likes, and engagement do NOT belong here - route those to the provenance
  engagement-signal posture, not to this tag.
- Minimal example: "'curated after 300 hours of testing' used as a credibility
  claim without exposing the test evidence."
- Discount: treat asserted effort as a routing signal, not as provenance or
  proof.

## Specimen Accretion Path

Specimen terms can mature, but not inside this skill by assertion.

Recommended path:

1. Reuse the specimen term across multiple audits with clear examples.
2. Record representative cases in a specimen library or assessment note.
3. Promote to a candidate taxonomy proposal only when the term catches a
   recurring failure mode that canonical tags cannot express cleanly.
4. Trigger the stop condition before canonicalization: create a separate
   taxonomy / ADR / schema review and update backend constants and tests in
   that dedicated slice.

## Historical Note

Earlier external-analysis notes used these promotion-layer names loosely. This
draft now governs them as `[specimen]` terms in the mini-registry above. They
remain non-canonical unless a separate taxonomy / ADR / schema review promotes
them into AI Radar's backend advisory tag set.
