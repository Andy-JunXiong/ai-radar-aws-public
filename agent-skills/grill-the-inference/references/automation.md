# Grill The Inference Automation Preconditions

Use this reference only after the main `SKILL.md` automation guardrails are
satisfied. This file gives per-attack-path criteria; it does not authorize
runtime automation by itself.

Only consider automating `caveat_stripping` when same-source limitation or
caveat capture is explicit and coverage is measured. For AI Radar source data,
that means source-stated limits, caveats, failure modes, or boundary conditions
must be captured as structured metadata or traceable source spans. If coverage
is unknown or sparse, report `not_checkable` instead of treating missing
caveats as absent.

Only consider automating `scope_inflation` when the conclusion terms and source
claim terms can be compared with stable rules or reviewed examples.

Only consider automating `juxtaposition_fusion` after human-reviewed examples
show the difference between valid synthesis and unsupported meaning created by
adjacency.
