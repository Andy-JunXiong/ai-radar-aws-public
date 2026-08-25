---
title: Private And Public GitHub Synchronization
last_updated: 2026-08-26
layer: L2-operating-guidance
audience: AI agents + human collaborators
tags: [github, public-release, sanitization, sync]
---

# Private And Public GitHub Synchronization

## User Command Contract

### Current repository-only operation

`commit and push current repository` authorizes the approved scope in the
current repository only.
Completion depends only on that authorized operation. The normal private-source
workflow uses `Andy-JunXiong/ai-radar-aws`.

### Standalone public synchronization

`sync public repo` explicitly authorizes sanitized public synchronization.
Completion depends on successful public synchronization and all required
public-safety checks.

### Dual-repository main operation

`commit and push` explicitly authorizes both the private-source operation and
independent sanitized public synchronization. `commit, push, and sync public`
has the same dual-repository meaning. Full completion requires both to succeed.
If either side fails or is blocked, report the result as partial.

## Deterministic Private Release Mechanics

Derive a private release candidate from changed paths rather than a
repository-wide reread:

1. enumerate tracked and untracked changes with Git-native, NUL-safe commands
   such as `git diff --name-only -z` and
   `git ls-files --others --exclude-standard -z`;
2. intersect them with the approved task scope and normal release roots such as
   `app/`, `backend/app/`, `backend/tests/`, `frontend/`,
   `signal_collectors/`, `tests/`, `scripts/`, and explicitly approved root or
   documentation files;
3. subtract runtime data, uploads, debug output, caches, temporary paths,
   personal/generated material, workflows, credentials, and anything outside
   the approved scope;
4. review the resulting explicit file list and content before staging.

Do not stream Git patch bytes through a PowerShell text pipeline. Prefer Git
commits plus `cherry-pick` or `merge` in a clean worktree. If a patch file is
needed, have Git write it directly with a binary-safe output option and pass
that file to `git apply --3way`; do not route patch content through shell text
encoding or line-ending conversion. Conflict detection and three-way review
remain required.

After reconciliation, select validation from effective changed files,
conflicts/path overlap, shared contracts and dependencies,
schema/API/invariant/runtime coupling, and behavioral risk. Run the smallest
set that provides fresh evidence for effective post-reconciliation behavior.
Use full regression when the behavior is cross-cutting, high-risk, or cannot
be isolated; do not infer behavioral independence from path non-overlap alone.

## Primary Main After An Isolated Release

After the private remote push succeeds:

- if the primary `main` worktree is clean, run `git fetch origin` and
  `git merge --ff-only origin/main`, or the equivalent safe fast-forward;
- if it is dirty, leave the checked-out local `main`, index, and working files
  unchanged and report that `origin/main` is ahead until the worktree is clean.

Never reset, force-update or move the checked-out branch ref underneath a dirty
worktree, rewrite its index, stash automatically, or discard/reinterpret user
changes to remove the divergence.

## History Boundary

The public repository is not a second remote for the private commit graph.
Never push private `main`, private commit SHAs, tags, or private Git history to
the public repository. Work from a clean checkout of the public repository and
copy only approved content from the committed private tree.

## Public Include Boundary

Public candidates normally include:

- application, backend, frontend, collector, and test source code;
- public product overview and roadmap;
- selected ADR, architecture, feature, governance, and evaluation documents;
- anonymous examples and public-safe configuration templates.

Every candidate still needs content review. Being source code does not make a
file automatically safe to publish.

For an authorized public synchronization, derive the proposed public allowlist
mechanically from the approved committed private release range's changed
paths, intersect it with the Public Include Boundary, and subtract every
Mandatory Exclusion. This produces the review candidate; it does not replace
file-by-file content, credential, English-language, or public-safety review.

## Mandatory Exclusions

Do not publish:

- runtime data or generated Signal, Insight, metrics, model-debug, workspace,
  reflection, review, calibration, lifecycle, or Final Takeaway records;
- subscription libraries, user configuration, manual uploads, PDFs, images,
  session metadata, or private fixtures;
- internal assessments, cognitive logs, incident records, interview material,
  current/daily status detail, or archived status logs;
- deployment workflows, private operations material, credentials, tokens,
  machine-specific paths, or secret-like values;
- local caches and temporary test or release directories, including
  `.pytest_cache/`, `.tmp-run/`, and `public-release/`;
- private Git history.

## Required Checks

Before a public push:

1. start from the current public `main` and confirm it is not behind its remote;
2. copy an explicit allowlist from the committed private tree, never the dirty
   private working tree;
3. review the public diff and confirm excluded path classes are absent;
4. run `python scripts/check_public_english.py`;
5. run the relevant feature tests and public-repository pre-commit checks;
6. run a credential/secret scan when the available release tooling supports
   it;
7. commit in the public repository and push its `main` independently;
8. report both private and public SHAs and any validation not performed.

## Local Remote Names

- `origin`: private repository
- `public`: public repository URL for read/fetch convenience

Do not use `git push public private-main:main`. Public writes must originate
from the sanitized public checkout so the independent-history boundary remains
visible and reviewable.
