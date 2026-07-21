# AI Radar UI Design Style Guide

Last updated: 2026-05-06

## Purpose

This document captures the current AI Radar product UI style so future frontend work stays consistent.

Use this guide when building or polishing:

- Manual Upload
- Signal Detail
- Project Takeaways
- Review Inbox
- Trajectory Timeline
- Admin / project intake pages
- other operational Workspace surfaces

The target feel is:

- calm
- compact
- operational
- review-friendly
- clearly human-in-the-loop

AI Radar is an intelligence workbench, not a marketing site. Prefer dense but readable product surfaces over decorative hero layouts.

## Core Visual Language

Use a white-panel, light-border system:

- page background: very light gray
- main panels: white
- panel border: light gray, usually `#e5e7eb`
- panel radius: `20px` for page-level toolbar / grouped sections
- repeated item cards: `8px` radius
- subtle shadow only for major white panels:
  - `0 1px 3px rgba(0,0,0,0.04)`

Avoid:

- large decorative gradients
- heavy color blocks
- nested card-in-card layouts
- marketing-page spacing
- oversized hero typography inside operational tools

Semantic color exception:

- high-information-density tracking pages may keep purposeful color when it improves scanning and preserves product meaning
- current accepted exceptions:
  - `Agent Watch` can keep colored status, provenance, profile, and tracking cues
  - `Friction Signals` can keep orange friction / pain / translation cues
- do not flatten these pages into the neutral card style unless there is a new product decision
- neutral Workspace / Review styling remains the default for Project Takeaways, Review Inbox, Trajectory Timeline, Manual Upload, Signal Detail, and ordinary record/detail pages

## Layout Rules

Use constrained, scannable layouts:

- primary page controls should sit in a white toolbar panel near the top
- filters should be grouped in compact white panels
- repeated records should be full-width cards with clear title, meta, chips, and compact details
- details should be collapsible when the content is dense
- avoid long always-expanded detail sections when a page is used for repeated review

Good examples already implemented:

- `/manual`
- `/manual/detail`
- `/workspace/projects`
- `/workspace/projects/review`
- `/workspace/projects/trajectory`

## Buttons And Navigation

Use clear button hierarchy:

- primary command:
  - dark background `#111827`
  - white text
  - 8-10px radius
  - used for the main action or main return path
- secondary command:
  - white background
  - light gray border
  - dark text
- destructive or caution actions:
  - soft red or amber background
  - matching border and text color

Navigation rule:

- if a user enters a child page from Project Takeaways, the child page must include a clear `Back to Project Takeaways` control near the top
- if a page has both `Back to Project Takeaways` and another parent such as Admin, `Back to Project Takeaways` should be the primary button when the entry point came from Project Takeaways

## Filters And Tabs

Use pill-style controls for review states and filters:

- active filter:
  - dark background
  - white text
  - dark border
- inactive filter:
  - white background
  - light gray border
  - dark gray text
- include counts in labels when counts help review flow

Examples:

- `All Review (27)`
- `Do Not Act (3)`
- `Manual Overrides (2)`
- `Review Required (3)`

Avoid underline-only tabs for operational review pages.

## Cards And Records

Repeated item cards should use:

- white background
- `1px solid #e5e7eb`
- `8px` radius
- 14-18px padding
- title first
- timestamp / project / source metadata second
- chips for state and provenance
- compact summary line
- expandable details for dense verification or record metadata

Record cards should make provenance visible:

- `Manual upload`
- `Collected signal`
- `Manual Override`
- verification status
- confidence
- blocked actions or claim risk

Manual or human-selected material should not be hidden deep in details.

## Status And Evidence Messaging

Status text should explain the operational meaning briefly:

- `Analyzed = insight is ready...`
- `Pending = this manual session still needs analysis...`
- `Synced to Signals`
- `Not yet in Signals`

Evidence and verification should be visible but compact:

- use chips and short summary rows
- use collapsible sections for claim-level details
- call out fallback generation clearly
- distinguish low-confidence / unsupported / inferred evidence from verified evidence

## Manual Upload Pattern

Manual Upload is the reference style for current AI Radar operational UI.

Important patterns from Manual Upload:

- upload controls and metadata live in the upload card, not in history
- saved sessions use compact cards
- review priority filters are pill buttons with counts
- session cards show:
  - title
  - created time
  - file count / type
  - analysis status
  - Signals availability
  - review priority
  - cognitive layer
  - verification / confidence summary
- actions are clear:
  - primary upload/generate actions
  - secondary refresh/view/open actions

## Workspace Pattern

Workspace pages should follow the same operational style:

- Project Takeaways has a white toolbar with clear navigation
- Review Inbox uses pill tabs and compact candidate/record cards
- Trajectory Timeline uses white summary and timeline panels
- Add / Manage Projects must always provide a clear return to Project Takeaways

When adding a new Workspace page, start from this structure:

1. PageHeader
2. white toolbar panel with return/navigation buttons
3. optional summary panel
4. filter/tabs panel
5. repeated record cards
6. empty/error states that name the endpoint or missing data clearly

## Copywriting

UI copy should be short and functional.

Prefer:

- `Back to Project Takeaways`
- `Manual Override`
- `Synced to Signals`
- `Generate with Claude`
- `Review Required`

Avoid:

- long explanatory paragraphs in the main flow
- vague labels such as `Open` when the destination matters
- hidden terminology without helper copy, such as `cognitive_layer` without an explanation

## Validation Checklist

Before calling a UI polish slice complete:

- page still works on desktop and narrow widths
- toolbar controls wrap cleanly
- buttons have clear primary / secondary hierarchy
- filter counts still fit in pills
- no text overlaps inside cards or buttons
- manual-source and human-override provenance is visible
- child pages have a clear return path
- focused frontend ESLint passes
- `tsc --noEmit` passes when TypeScript types changed or shared UI code changed
