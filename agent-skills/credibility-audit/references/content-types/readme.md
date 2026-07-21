# README Playbook

Use this reference for GitHub repositories, README claims, package pages, and
tool documentation.

## Checks

1. Separate README claims from implementation evidence.
2. Check whether the claimed behavior is backed by code, tests, examples,
   releases, or only prose.
3. Verify current repo metadata only when it matters to the verdict.
4. Treat first-party README prose as source self-report until inspected.
5. If adopting a concept into AI Radar, run ADR-0010 even if the repo is good.

## Common Distortions

- `source_asserted_but_unsubstantiated`: README claim not found in code/tests.
- `pseudo_precision`: benchmark or token-saving number lifted out of scope.
- `caveat_stripping`: setup, limits, data assumptions, or evaluation conditions
  removed.
- `context_drift`: narrow repo behavior generalized to all projects.
- `category_collapse`: installability treated as product fit or truth.

## Review Depth

Use three levels:

- README-only: label implementation details as unverified.
- Source-inspected: cite the file or behavior inspected.
- Executed: note the command, result, and local limits.
