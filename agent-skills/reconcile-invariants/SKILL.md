---
name: reconcile-invariants
description: |
  Use at scoped session closeout or when the user asks to reconcile, align, or sync the current work with AI Radar operating invariants. This Layer A' protocol reviews only the declared task scope and produces assessment notes or proposed diffs for AGENTS.md, ADR metadata, and agent-skill registry drift; it does not automatically patch core docs or scan the entire repository.
status: experimental
intended_consumers:
  - codex-cli
  - claude-code
---

# Reconcile Invariants

Use this protocol to reconcile the current task scope with AI Radar's operating
invariants. The role is knowledge-base editor, not recorder: remove drift,
duplication, and stale claims before adding more text.

This skill has no admission authority. Core or governance files require the
usual approval gates before any edit is applied.

## Boundary

This protocol may:

- inspect files explicitly declared in the current task scope
- identify AGENTS.md, ADR registry, or agent-skill registry drift
- produce an assessment or proposed diff
- recommend that stable information move out of always-loaded guidance
- flag stale ADR references, missing registry rows, or missing skill files

This protocol must not:

- scan or refactor the entire repository without explicit user request
- automatically patch `AGENTS.md`, `docs/adr/*`,
  `CURRENT_DEVELOPMENT_STATUS.md`, or other core files
- turn session history into permanent rules without admission
- move Layer A' agent protocols into product runtime
- create a second skill registry outside `agent-skills/`

## Scope Contract

Before reviewing, state the smallest file set in scope. A file is in scope only
when one of these is true:

- the user named it
- the current task changed it
- an in-scope file directly references it as a registry or governance source

The completion check applies only to files declared in this scoped file set.
Missing a declared in-scope file invalidates the reconciliation. This rule must
not be used to justify repo-wide scanning.

## Process

1. Size check.
   - Check whether always-loaded guidance is growing toward the point where
     important rules become easy to miss.
   - For AI Radar, treat size concerns as an assessment signal first; do not
     edit `AGENTS.md` without explicit approval.
   - Mark likely bloat: historical narrative, detailed mechanism already owned
     by docs, single-incident recap, or duplicate pointers.

2. Reduction pass.
   - Ask whether the next agent would make a material mistake if the item were
     absent.
   - Keep hard boundaries, prohibitions, permission model, command quick
     references, routing tables, and recurring gotchas.
   - Move or propose moving historical narrative, detailed mechanism, and
     one-off retrospectives to narrower docs or assessment files.

3. Three-way alignment.
   - Compare the scoped claims across:
     `AGENTS.md`;
     `docs/adr/README.md` plus `docs/adr/*.md` frontmatter;
     `agent-skills/README.md` plus `agent-skills/*/SKILL.md`.
   - Verify that claimed skills have real directories.
   - Verify that referenced ADR IDs exist and that status claims match the ADR
     frontmatter or registry row.
   - List drift separately when it touches core files or cannot be resolved
     from the scoped evidence.

4. Proposed update.
   - For each scoped file, mark `assessed`, `change proposed`, or `no change`.
   - Do not summarize until every scoped file has been assessed.
   - Present proposed diffs or edit descriptions and wait for admission before
     patching core files.

## Output Format

Use this compact structure:

```text
SCOPE:
- <file> - assessed | change proposed | no change

DRIFT:
- <finding> - <evidence> - <proposed action>

PROPOSED DIFFS:
- <file> - <summary or patch pointer>

BLOCKED / NEEDS ADMISSION:
- <core-file or unresolved decision>

NEXT STEP:
- <single smallest action>
```

## Stop Conditions

Pause before:

- editing core files
- broadening the file set beyond declared scope
- deleting or moving files
- changing ADR status
- converting an external framework into AI Radar scope without ADR-0010
  admission
- modifying product runtime skills or prompts
