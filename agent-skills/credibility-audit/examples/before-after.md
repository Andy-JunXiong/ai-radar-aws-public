# Credibility Audit Examples

These examples are compact regression cases. They are not evidence that the
named external claims are current.

## Example 1: Repo Card With Popularity And Capability Claims

Input:

```text
A social card says a GitHub skill repo has "145k stars" and implies a specific
skill inside the repo can "teach you anything."
```

Output:

```text
VALUE: A stateful teaching skill may be useful as a Layer C structural specimen.
PROVENANCE: third-party summary - the card is a promotion-layer social artifact, not the canonical repo or skill file.
DISTORTIONS:
- [canonical] juxtaposition_fusion @ promotion-layer/social-card - repo-level popularity is fused with one skill's capability.
- [canonical] caveat_stripping @ promotion-layer/headline - "teach you anything" removes domain and workflow limits.
- [specimen] scope_inflation @ promotion-layer/headline - a bounded teaching workflow is framed as universal capability.
VERIFY: skill file behavior -> unverified until the canonical repo blob is read.
DISCOUNT: subtract the popularity halo and universal capability framing.
ACTION: read the canonical skill file, then decide whether it is a specimen, not a product dependency.
```

## Example 2: README Benchmark Number Reposted As General Savings

Input:

```text
A README says "71.5x per query vs raw files"; a repost says "large projects
reduce tokens 71x every session."
```

Output:

```text
VALUE: Content-addressed or graph-backed retrieval may reduce repeated source reads.
PROVENANCE: mixed - the benchmark phrase is first-party README self-report, while the repost is a third-party promotion-layer rewrite.
DISTORTIONS:
- [canonical] pseudo_precision @ promotion-layer/social-card - "71.5x" is reused as if it were a typical result.
- [canonical] context_drift @ promotion-layer/social-card - per-query benchmark framing becomes every-session project behavior.
- [canonical] caveat_stripping @ promotion-layer/social-card - benchmark conditions are omitted.
- [specimen] valence_inflation @ promotion-layer/social-card - the repost turns an optimization measurement into a broad promise.
VERIFY: exact benchmark conditions -> unverified until the README and evaluation setup are read.
DISCOUNT: keep the caching/retrieval idea, discard the universal token-saving number.
ACTION: inspect the repo implementation and benchmark scope before adopting any claim.
```

## Example 3: README Body Claims Implementation Fact

Input:

```text
A README says "Production-ready agent memory with persistent graph retrieval,"
but the implementation section only shows a prototype setup and no persistence
tests.
```

Output:

```text
VALUE: The repo may still contain useful prototype patterns for graph-backed memory.
PROVENANCE: source self-report - the README is first-party, but source self-report is not implementation verification.
DISTORTIONS:
- [canonical] caveat_stripping @ artifact-body/README - the README presents production readiness while omitting prototype limits.
- [canonical] source_asserted_but_unsubstantiated @ artifact-body/README - implementation maturity is asserted before code/tests verify it.
VERIFY: persistence tests -> unverified until source code or tests are inspected.
DISCOUNT: keep the prototype pattern, subtract production-readiness certainty.
ACTION: inspect source-code and tests before treating the README claim as implementation fact.
```

## Example 4: Codex Skill List Card

Input:

```text
A social card says "Codex must-install Skill TOP 9: agents + memory + MCP +
workflow OS, doubles AI capability, curated after 300 hours of testing."
```

Output:

```text
VALUE: A curated skill list may surface useful tools worth primary-source inspection.
PROVENANCE: third-party summary - the card is a promotion-layer list, not an install manifest or compatibility proof.
DISTORTIONS:
- [specimen] terminology_laundering @ promotion-layer/title - "Codex Skill" borrows platform specificity before packaging is shown.
- [specimen] framework_density_inflation @ promotion-layer/social-card - "agents + memory + MCP + workflow OS" stacks framework terms without mechanism proof.
- [specimen] scope_inflation @ promotion-layer/headline - "must-install" turns a recommendation into a universal requirement.
- [specimen] valence_inflation @ promotion-layer/marketing-copy - "doubles AI capability" overstates the likely effect of a list.
- [specimen] effort_asymmetry_framing @ promotion-layer/marketing-copy - "300 hours of testing" is used as credibility without exposing test evidence.
VERIFY: Codex-compatible packaging for each listed item -> unverified until each primary repo or package manifest is checked.
DISCOUNT: treat the card as a discovery queue, not as proof of compatibility or quality.
ACTION: inspect one listed repo at a time and keep unverified items out of AI Radar scope.
```
