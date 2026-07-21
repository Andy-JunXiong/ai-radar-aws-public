# Grill-The-Inference Validation Record 002

date: 2026-07-08

scope: structural pruning pilot for `agent-skills/grill-the-inference/SKILL.md`

packet_scope: Codex review brief pasted by Andy, Claude critique of the first
solution, current `grill-the-inference` skill text, existing calibration and
validation directory shape, and ADR-0010 admission boundary.

## Admission

ADR-0010 outcome: admitted in modified form.

Smallest admitted scope: one agent-skill pruning pilot for
`grill-the-inference`, preserving verdict logic, runtime-gate boundaries,
Project Takeaway boundaries, and downstream-action gates.

## What Changed

- Shortened the YAML description second sentence to `Not a runtime gate.`
- Replaced the Step 6 counter-conclusion-status bullet mapping with a decision
  table.
- Moved detailed calibration capture fields into
  `agent-skills/grill-the-inference/references/calibration.md`.
- Moved per-attack-path automation criteria into
  `agent-skills/grill-the-inference/references/automation.md`.
- Created a per-skill `references/` directory because the existing
  `calibration/` directory stores sample/record artifacts, not procedural
  reference text.

## What Did Not Change

- No product runtime gate was added.
- No `verified_insight`, Project Takeaway, Action eligibility, or
  `blocked_downstream_actions` behavior changed.
- No ADR, `docs/adr/INVARIANTS.md`, AGENTS.md, status schema, backend route,
  frontend workflow, or model-executor path changed.
- The `needs_human_judgment` abstention-state clarification stayed in the main
  skill.
- The `not_checkable` caveat-stripping rule stayed in the main skill.
- The Boundary must-not list stayed intact.

## Consciously Admitted Tradeoffs

- The description lost the longer explanatory sentence, but retained an
  always-loaded `Not a runtime gate.` reminder.
- Calibration details were moved behind a reference pointer, but
  `packet_scope` remains explicitly required in the main skill.
- Automation criteria were moved behind a reference pointer, but both
  automation guardrails remain in the main skill:
  - this protocol is not itself an automated blocking gate
  - any runtime automation changing verification status, Project Takeaway
    eligibility, Action eligibility, or `blocked_downstream_actions` requires a
    separate admitted implementation slice and ADR/core-doc preflight
- The broader Item 4 single-sourcing proposal was not implemented. Runtime-gate
  guardrails intentionally remain prominent at multiple sites.

## Drift Check

Step 6 decision table row mapping:

| Table row | Existing source rule preserved |
|---|---|
| `valid_counter` + non-distinguishing warrant -> `underdetermined` | "`valid_counter` plus an indistinguishable warrant means `underdetermined`" |
| `valid_counter` + distinguishing warrant -> `pass` | "`valid_counter` plus a distinguishing warrant means `pass`" |
| `no_valid_counter` + coherent warrant + no attack-path `risk` -> `pass` | "`no_valid_counter` means `pass` only when the warrant is coherent and no attack path is `risk`" |
| `no_valid_counter` + any attack-path `risk` -> `needs_human_judgment` or narrow/rewrite, not `underdetermined` | "`no_valid_counter` with any attack-path `risk` means `needs_human_judgment` or a narrow/rewrite recommendation, not `underdetermined`" |
| `not_attemptable` -> `needs_human_judgment` | "`not_attemptable` means `needs_human_judgment`" |
| `invalid_external_fact` / `invalid_ignores_claim` -> discard for underdetermination test | "must be discarded for the underdetermination test" |

No new verdict path was introduced.

## Pilot Lesson For Future Skill Pruning

Before classifying any section as low-risk branch detail, first scan the section
for embedded high-risk guardrails. If present, upgrade the risk classification
or split the section so the guardrail remains prominent while branch-local
detail moves to a reference file.

## Validation

- `git diff --check` passed for the modified skill and new reference files.
- Anchor check confirmed `packet_scope` remains discoverable in the main skill.
- Anchor check confirmed both automation runtime guardrails remain discoverable
  in the main skill.
- Codex reviewed the existing `calibration/` directory shape and confirmed it
  contains calibration records, not procedural reference docs.

## Boundary

This record is Layer A' process evidence for the evolution of
`grill-the-inference`. It is not source evidence, claim support, Project
Takeaway verification metadata, product runtime data, or runtime gate output.
