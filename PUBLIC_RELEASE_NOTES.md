# Public Snapshot Notes

This directory is a sanitized working-tree snapshot prepared for public review.
It is intentionally separate from the private development repository and does
not include that repository's Git history.

## Excluded

- manual uploads, PDFs, images, and upload-session metadata
- workspace, reflection, review, calibration, and Final Takeaway runtime data
- generated signal, insight, metrics, and model-debug output
- personal context and machine-specific configuration
- private binary test fixtures; manual-upload integration tests need synthetic
  replacements
- interview preparation, external drafts, cognitive logs, incident records,
  internal assessments, and daily status archives
- private deployment and operations material

## Included

- application, backend, frontend, collector, and test source code
- public product overview and roadmap
- selected architecture, feature, ADR, governance, and evaluation documentation
- anonymous configuration and data examples

## Publication Preparation

- Licensed under the MIT License.
- Scanned with Gitleaks 8.30.1 before the first public release; no leaks were
  reported.
- No screenshots, personal images, or private test fixtures are included; the
  only binary asset is the application favicon.
- The public repository must be initialized from this directory so the private
  repository's history is never copied.
- Deployment workflows remain excluded and require a separate public-safety
  review before they can be added.
- Public source, documentation, tests, and UI copy are English-only. Run
  `python scripts/check_public_english.py` before every public update; the same
  check is registered as a local pre-commit hook.

No credentials or private data are required to inspect the source code.

## 2026-08-02 Snapshot Update

- added the verified-insight contract and lineage hardening changes;
- added Project Watch evidence follow-ups and deterministic, explainable
  related-Signal review candidates;
- added the LMArena official collector path without publishing the private
  subscription library;
- added public-safe calibration tools and tests while excluding their private
  reports, labels, runtime records, and status history;
- documented that private and public repositories are synchronized through
  separate commits and independent history, never by pushing private history
  to the public repository.
