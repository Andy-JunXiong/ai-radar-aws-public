---
title: Private And Public GitHub Synchronization
last_updated: 2026-08-02
layer: L2-operating-guidance
audience: AI agents + human collaborators
tags: [github, public-release, sanitization, sync]
---

# Private And Public GitHub Synchronization

## User Command Contract

Unless the authenticated user names only one target, `commit and push` means:

1. commit and push the approved private scope to
   `Andy-JunXiong/ai-radar-aws`;
2. prepare an independently committed sanitized snapshot and push it to
   `Andy-JunXiong/ai-radar-aws-public`.

Do not report the operation as complete until both targets succeed. A failure
or safety blocker on either target makes the result partial.

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
