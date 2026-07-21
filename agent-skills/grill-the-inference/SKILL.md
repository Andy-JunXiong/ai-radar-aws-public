---
name: grill-the-inference
description: |
  Use when an AI Radar insight, takeaway, sprint proposal, or promotion candidate depends on combining multiple claims into a conclusion, especially when the user asks whether the reasoning is underdetermined, over-composed, caveat-stripped, or vulnerable to an equally plausible counter-conclusion. Not a runtime gate.
status: experimental
intended_consumers:
  - codex-cli
  - claude-code
---

# Grill The Inference

Use this protocol to test whether a conclusion is actually determined by the
claims used to support it.

The core move is counter-conclusion construction: try to use the same
load-bearing claim set to construct a plausible conclusion that contradicts or
materially weakens the original. If that succeeds and the original warrant
cannot explain why the original conclusion is preferred, report the original as
`underdetermined`.

This protocol is a Layer A' review skill. It does not create a product runtime
gate by itself.

Shared counter-conclusion vocabulary lives in
`agent-skills/_shared/references/counter-conclusion.md`. This skill remains
self-contained so it can be run from this file alone; the shared reference is
for consistency across Layer A' protocols that use the same verdict language.

## Boundary

This protocol may:

- make a hidden warrant explicit
- identify load-bearing claims
- test for composition failures across claims
- label the conclusion `pass`, `underdetermined`, or `needs_human_judgment`
- recommend a narrower rewrite or manual review

This protocol must not:

- claim that the counter-conclusion is true
- mark a source claim false merely because the conclusion is underdetermined
- modify `verified_insight`, Project Takeaway, Action eligibility, or
  `blocked_downstream_actions`
- bypass ADR-0010 if the result becomes product, architecture, workflow, skill,
  or runtime implementation scope
- treat agent review output as external-world evidence
- persist the generated counter-conclusion as reusable evidence, source data,
  or a future risk record without a separate approved design

The verdict is always about support sufficiency:

```text
This evidence set is or is not sufficient to determine this conclusion.
```

Never turn it into:

```text
The opposite conclusion is therefore true.
```

## Trigger

Run this protocol before trusting or promoting a conclusion when one or more
of these are true:

- the conclusion combines multiple verified or partially verified claims
- the conclusion uses comparison, trend, causal, analogy, or aggregation logic
- the supporting claims are individually plausible but the conclusion feels
  stronger than any single claim
- a user or reviewer suspects scope inflation, caveat stripping, or
  juxtaposition fusion
- an insight is being considered for Project Takeaway review, public framing,
  strategic recommendation, or future runtime gate design

Do not run this protocol for a single descriptive claim that can be checked
directly against a source span.

## Inputs

Start from the smallest available packet:

- original conclusion
- cited claims
- source excerpts or verification notes when available
- intended downstream use, if any

If the cited claims are too broad, identify the load-bearing subset before
testing. Load-bearing claims are the claims the conclusion would materially
weaken or fail without.

## Process

1. State the conclusion.
   - Preserve the exact strong wording that needs to be tested.
   - Identify any scalar, comparative, temporal, causal, or scope terms.

2. Extract load-bearing claims.
   - Include only claims that carry the conclusion.
   - Separate background context from support.
   - Keep claim IDs or source anchors when available.

3. Write the warrant.
   - Name the reasoning type: `aggregation`, `trend_extrapolation`,
     `comparison`, `causal`, `analogy`, or `other`.
   - Explain in one or two sentences how the claims are supposed to imply the
     conclusion.
   - If the warrant is missing from the input, write a provisional warrant and
     mark it `provisional`.
   - If no coherent warrant can be reconstructed, stop the verdict at
     `needs_human_judgment`. Do not treat missing warrant data as proof of
     underdetermination.

4. Attempt counter-conclusion construction.
   - Use the shared counter-conclusion vocabulary from
     `agent-skills/_shared/references/counter-conclusion.md` when aligning this
     output with other Layer A' protocols.
   - Use the same load-bearing claims.
   - Do not add external facts unless the task explicitly allows external
     evidence review.
   - Construct the strongest plausible contradiction or material weakening.
   - If a counter-conclusion requires facts outside the packet, mark that
     dependency instead of smuggling it in.
   - A counter-conclusion counts only if it uses the same load-bearing claims,
     does not ignore a decisive claim, and does not rely on new evidence.
   - If no compliant counter-conclusion can be constructed, record
     `no_valid_counter` and do not use the failed attempt to support an
     `underdetermined` verdict.

5. Apply the three attack paths.
   - `scope_inflation`: the conclusion asserts degree, maturity, breadth, or
     proximity not carried by the claims.
   - `caveat_stripping`: same-source limitations, caveats, failure modes, or
     boundary conditions weaken the conclusion but were omitted.
     Assign the three values strictly:
     - `risk`: the packet contains same-source caveat/limitation text that
       weakens the conclusion and was omitted from it.
     - `pass`: the packet contains same-source caveat/limitation text and it
       does NOT weaken the conclusion (i.e. checked, and clean).
     - `not_checkable`: the packet contains no same-source caveat/limitation
       text to check against. Absence of caveat text is NOT a pass — a pass
       requires having checked present caveat text. When in doubt between
       `pass` and `not_checkable`, choose `not_checkable`.
   - `juxtaposition_fusion`: the conclusion relies on meaning created between
     claims that no individual claim states.

6. Decide support sufficiency.
   - `pass`: no valid counter-conclusion can be constructed, or the warrant
     explains why the claims support the conclusion better than the valid
     counter-conclusion.
   - `underdetermined`: the same claims support the original and a materially
     weaker or contrary conclusion with similar plausibility, and the warrant
     does not distinguish between them.
   - `needs_human_judgment`: the protocol cannot complete the support test
     because the warrant, claim anchors, source context, domain standard, or
     policy boundary is missing. This is an abstention state, not a weaker
     form of `underdetermined`.
   - Map counter-conclusion status to verdict with this table:

     | Counter-conclusion status | Warrant | Attack paths | Verdict |
     |---|---|---|---|
     | `valid_counter` | does not distinguish original from counter | any | `underdetermined` |
     | `valid_counter` | distinguishes why the original is preferred | any | `pass` |
     | `no_valid_counter` | coherent | every path is `pass`, `not_applicable`, or `not_checkable`; none is `risk` | `pass` |
     | `no_valid_counter` | coherent | any path is `risk` | `needs_human_judgment` or narrow/rewrite; not `underdetermined` |
     | `not_attemptable` | any | any | `needs_human_judgment` |
     | `invalid_external_fact` / `invalid_ignores_claim` | any | any | discard for the underdetermination test; does not support `underdetermined` |

     A `not_checkable` attack path does not by itself block a `pass`; it only
     records that one check could not be performed for lack of in-packet text.

7. Recommend the smallest safe next step.
   - Narrow or rewrite the conclusion.
   - Ask for source excerpts or missing claim IDs.
   - Route to human review.
   - Keep as observation-only.
   - Log to a calibration set when this is part of sample calibration.
   - Propose a future runtime design only after ADR-0010 and core boundary
     approval.

## Output Format

Use this compact structure:

```text
CONCLUSION: <original conclusion>
LOAD-BEARING CLAIMS:
- <claim id or short text>
WARRANT: <type; explicit | provisional | missing> - <how the claims are supposed to imply the conclusion>
COUNTER-CONCLUSION ATTEMPT: <plausible contrary or weakening conclusion, or why none can be constructed>
COUNTER-CONCLUSION STATUS: valid_counter | no_valid_counter | invalid_external_fact | invalid_ignores_claim | not_attemptable
ATTACK PATHS:
- scope_inflation: pass | risk | not_applicable - <reason>
- caveat_stripping: pass | risk | not_checkable - <reason>
- juxtaposition_fusion: pass | risk | not_applicable - <reason>
VERDICT: pass | underdetermined | needs_human_judgment
NEXT STEP: <single smallest action>
CALIBRATION_NOTE: <optional: expected false positive/false negative risk or sample-log note>
```

Keep the output short enough that a human can inspect the warrant and verdict
without reading an essay.

## Calibration Notes

When this protocol is being used to calibrate the future
`composition_underdetermination_gate`, follow
`agent-skills/grill-the-inference/references/calibration.md`.

Every calibration record must include `packet_scope`: the exact material fed
into the protocol for that run. Calibration notes are process evidence about
the protocol. They are not claim support, source evidence, Project Takeaway
verification metadata, product runtime data, or runtime gate output.

## Automation Preconditions

This protocol may guide future automation, but it is not itself an automated
blocking gate.

For per-attack-path automation criteria, consult
`agent-skills/grill-the-inference/references/automation.md`.

Any runtime automation that changes verification status, Project Takeaway
eligibility, Action eligibility, or `blocked_downstream_actions` requires a
separate admitted implementation slice and the relevant ADR/core-doc preflight.

## Stop Conditions

Pause and ask for user or human-review direction before:

- treating underdetermination as proof that the opposite conclusion is true
- adding external evidence to rescue or defeat the conclusion
- persisting counter-conclusions beyond the immediate review scratchpad
- changing any runtime verification schema or gate
- creating or editing ADRs, `docs/adr/INVARIANTS.md`, AGENTS.md, or status docs
- converting this protocol into a product runtime prompt or user-facing skill
- using this review as the sole basis for a high-stakes recommendation
