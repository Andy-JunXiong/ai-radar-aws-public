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
- No screenshots, static binary assets, or private test fixtures are included.
- The public repository must be initialized from this directory so the private
  repository's history is never copied.
- Deployment workflows remain excluded and require a separate public-safety
  review before they can be added.

No credentials or private data are required to inspect the source code.
