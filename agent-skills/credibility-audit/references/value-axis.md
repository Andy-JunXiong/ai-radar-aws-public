# Value Axis

Use this reference when extracting value from an external artifact.

## Rule

Extract value before provenance.

Ask:

```text
If this claim were true, what useful insight, capability, warning, or pattern
would remain?
```

Do not discard value because the source is low-trust. Do not inflate value
because the source is prestigious.

## Value Levels

Use plain language instead of a numeric score unless the user asks for a score.

- `high`: identifies a transferable pattern, structural primitive, failure
  mode, or concrete capability that can inform AI Radar judgment.
- `medium`: useful as a specimen, comparison point, cautionary example, or
  prompt for later review.
- `low`: locally interesting but not meaningfully reusable.
- `none`: no separable insight remains after removing hype or unsupported
  claims.

## AI Radar Boundary

Value does not imply admission into AI Radar.

If the artifact suggests product, architecture, workflow, agent-skill, or
implementation work, run ADR-0010 separately. Most useful external insights
should still land in notebook, specimen, assessment, or known-gap space unless
they pass the admission gate.

## Useful Output Phrases

- "Useful as a specimen, not as a dependency."
- "Good signal, weak source."
- "Strong implementation clue, but not yet product scope."
- "Valuable failure mode, not a feature request."
- "No transferable value after removing the promotion layer."
