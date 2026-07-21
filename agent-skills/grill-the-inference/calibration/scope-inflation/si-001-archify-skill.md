# Scope Inflation Calibration Record si-001

id: si-001

case: archify described as a standalone architecture tool

claim axis: agent skill promoted as independent tool + semantic validation implied by rendered output

CLAIM: "Archify is an independent architecture diagram tool that generates validated architecture diagrams."

SOURCE: secondary social post / tool comparison framing reviewed in the four-tools brief

PRIMARY-SOURCE CHECK:
- Archify README states it is an agent skill for Claude, Codex CLI, and opencode.
- Its GitHub Pages surface is a project page and example host, not the primary tool surface.
- Archify is based on Cocoon-AI/architecture-diagram-generator v1.0 and preserves attribution.
- Current Archify has real schema, layout, and post-render artifact validation.
- Local smoke showed schema validation caught a malformed card, layout validation caught label/component overlap, and final `validate` / `render` / `check` passed after fixes.

LIMITATION / CORRECTION:
Archify's validation is mechanical and artifact-level. It checks schema shape, geometry, labels, references, and SVG sanity. It does not prove that a generated diagram faithfully captures the real system, includes all components, or assigns correct semantics.

VERDICT: scope_inflation + semantic caveat_stripping

severity: medium

verification: primary-source repo review + local smoke

evidence:
- https://github.com/tt-a1i/archify
- https://raw.githubusercontent.com/tt-a1i/archify/main/CHANGELOG.md
- https://raw.githubusercontent.com/tt-a1i/archify/main/archify/SKILL.md
- local smoke: `.tmp-run/archify-fit/ai-radar-mixed.html`

recommended rewrite:
"Archify is an agent skill that can produce mechanically validated diagram artifacts. The diagram remains semantically unverified unless separately checked against source evidence."

AI Radar boundary:
This record is Layer A' `grill-the-inference` scope_inflation calibration only. It is not product runtime data, source evidence, claim support, Project Takeaway verification metadata, or a runtime gate output.
