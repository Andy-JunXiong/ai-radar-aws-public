# Grill-The-Inference Validation Record 001

date: 2026-07

method: dual-model cross-execution (Codex + Claude, distinct model IDs,
satisfying the "judge model ID != insight producer" invariant)

skill version: post caveat_stripping not_checkable disambiguation

test set: 5 samples across both verdict directions

- underdetermination direction (3): cs-004 DALL·E 2, cs-007 AlphaGeometry,
  Brain2Qwerty (calibration 001)
- pass direction (2): P1 (WMT14 BLEU comparison), P2 (retrieval ablation)

## Results

| sample | Codex verdict | Claude verdict | agree |
|---|---|---|---|
| cs-004 | underdetermined | underdetermined | yes |
| cs-007 | underdetermined | underdetermined | yes |
| B2Q | underdetermined | underdetermined | yes |
| P1 | pass | pass | yes |
| P2 | pass | pass | yes |

verdict agreement: 5/5 (100%)

## Key Findings

1. Both failure modes we designed against did NOT occur:
   - no drift-to-underdetermined on sound conclusions (P1/P2 both pass)
   - no forced counter-conclusion construction (P2's "noise/significance"
     lure correctly declined as requiring outside facts, not used to judge
     underdetermined)
2. One divergence surfaced and was FIXED (source of the skill upgrade above):
   on P1, Claude judged caveat_stripping=pass, Codex judged=not_checkable.
   Codex was correct per protocol (absence of caveat text != pass). This
   divergence drove the step5/step6 disambiguation now in the skill.
3. needs_human_judgment path NOT YET tested by these 5 samples — pending
   a dedicated abstention-path test round.

## Status

Two of three verdict branches (pass, underdetermined) validated by dual-model
agreement. needs_human_judgment branch remains unvalidated.

Recommend: do NOT promote skill to runtime gate until abstention path is tested
and until sample count is expanded beyond 5.

## Boundary

This validation record is Layer A' process evidence for `grill-the-inference`.
It is not a calibration sample, source evidence, claim support, Project
Takeaway verification metadata, product runtime data, or a runtime gate output.

---

# Appended Section: needs_human_judgment Branch

date: 2026-07

scope: needs_human_judgment (abstention) branch — the third verdict branch,
untested in the initial 5-sample round.

method note: this round is Claude-prediction vs Codex-execution comparison, NOT
two independent agent runs. Agreement here is therefore ONE tier weaker than
the first 5 samples (which were true dual-model). Recorded honestly so future
readers do not over-read the agreement.

test samples (2), both designed to have no testable inference:

- N1: warrant-not-reconstructable
  CONCLUSION: "This approach is the right architecture for the system."
  (claims: team framework experience; a past project used a different approach)
- N2: comparison-anchor-missing
  CONCLUSION: "Model A is more accurate than Model B on this task."
  (claims: A scored 71 on internal eval; B evaluated on a different,
  unspecified benchmark)

## Appended Results

| sample | Claude (predicted) | Codex (executed) | agree |
|---|---|---|---|
| N1 | needs_human_judgment | needs_human_judgment | yes |
| N2 | needs_human_judgment | needs_human_judgment | yes |

verdict agreement: 2/2

## Appended Key Findings

1. Both correctly separated abstention from underdetermination. In particular
   N2 — surface-similar to "evidence insufficient to decide" — was correctly
   judged not_attemptable → needs_human_judgment (no comparable anchor to test),
   NOT underdetermined. The abstention/underdetermined boundary held on a real
   tempting sample.
2. counter-conclusion status = not_attemptable in both; warrant = missing in
   both.
3. OPEN ITEM (unresolved, not a bug): under a missing warrant, whether an attack
   path should read `risk` or `not_applicable` is not specified by the skill.
   Codex filled `risk` (defensible: the conclusion wording does overreach);
   another executor could fill `not_applicable`. This does NOT affect the
   verdict (needs_human_judgment is set by not_attemptable, not by attack
   paths). Flagged for observation; do NOT patch the skill until a true
   dual-model run reproduces the divergence.

## Appended Status Update

- All three verdict branches (pass / underdetermined / needs_human_judgment)
  now have agreeing test evidence.
- Caveat: needs_human round is prediction-vs-execution, one tier weaker than
  dual-model; sample count remains small (7 total across all branches).
- Recommendation UNCHANGED: do NOT promote skill to runtime gate. Remaining
  before runtime: (a) true dual-model rerun of the abstention branch, (b)
  resolve the OPEN ITEM above, (c) expand sample count.
