# AI Radar Roadmap

This roadmap summarizes the current direction of AI Radar for humans and for lightweight GitHub project-context readers.

AI Radar is moving from an AI ecosystem signal engine into a closed-loop intelligence product:

```text
Signal -> Insight -> Trend -> Strategic Intelligence -> Decision -> Review -> Learning
```

The roadmap is intentionally product-facing. Day-to-day implementation status lives in `CURRENT_DEVELOPMENT_STATUS.md`; detailed implementation planning lives in `DEVELOPMENT_PLAN.md`.

## Product North Star

AI Radar should help a user:

- detect meaningful AI ecosystem signals early
- understand why a signal matters
- map signals to active projects and long-term goals
- separate weak evidence from strong evidence
- turn intelligence into reviewable project-level judgment
- learn from decisions and outcomes over time

The system should improve judgment quality, not merely collect more content.

## Current Foundation

Already usable:

- signal ingestion and normalization
- signal detail and insight generation
- topic classification and scoring
- radar summaries
- workspace project surfaces
- Project Takeaways
- Knowledge Synthesis
- Manual Upload / Manual Intelligence
- AI Agent Watch MVP plus advisory tracking state
- Friction Signals MVP plus advisory tracking state
- Reflection scaffold and UI
- Reflection polish pair persistence and human review scaffold, keeping
  polished drafts separate from final reflection saves, evidence, and Project
  Takeaway / Action gates
- Dev Inbox for lightweight bug / improvement capture and coding-agent handoff
  drafts
- Signal Detail Final Takeaway confirmation foundation:
  Completion Note -> immutable Review Bundle snapshot -> Andy-confirmed
  Final Takeaway artifact
- External Synthesis Source intake for Final Takeaway Review Bundles:
  paste plus markdown/plaintext/html upload as review context, not verified
  external evidence
- `confirmed_final_takeaway` Project Review handoff provider:
  explicit Signal Detail handoff from a confirmed Final Takeaway into Review
  Inbox while preserving Project Takeaway verification and override gates
- ReviewRecord / CalibrationEvent / Trajectory event foundations
- model routing and execution policy foundations
- internal prompt / skill registry discipline
- governance and evaluation scaffolds for invariants, bounded edits, edit
  reports, metadata hardening audits, claim-dependency audits, and held-out
  insight evaluation seed cases

## Phase 1: Intelligence Engine Hardening

Goal: make signal-to-insight output more reliable, explainable, and reusable.

Focus areas:

- improve source normalization and signal metadata quality
- improve topic taxonomy consistency
- strengthen signal scoring and project-match precision
- preserve first-seen / collected-at semantics during ingestion reruns
- improve model provenance attribution on generated outputs
- keep ingestion collectors free of direct LLM execution paths

Expected result:

- Signals remain structured and stable enough for downstream insight, knowledge, and review flows.

## Phase 2: Project Takeaway Review Loop

Goal: make Project Takeaways the primary project-level judgment, watch, action, and learning surface.

Focus areas:

- candidate creation with explicit verification context
- clearer Review Inbox provenance for `confirmed_final_takeaway` handoffs while
  preserving blocked low-risk Action behavior
- confirmed / rejected / dismissed / watch / action review outcomes
- Watch follow-up observations
- Action completion with outcome metadata
- ReviewRecord detail pages
- CalibrationEvent and trajectory integration
- advisory invariant checks for Project Takeaway gates and source categories
- typed Project Takeaway candidate envelope / builder for source-specific
  admission policy before writes
- bounded caution context from rejected / dismissed review history
- Decision Card legacy entrypoint downgrade / migration path
- advisory claim-dependency readiness audits before adding
  `depends_on_claim_ids` or cascade behavior

Important boundary:

- Project Takeaway writes must carry verification context, or be explicitly marked as unverified/manual/knowledge-review/override with corresponding blocked actions and audit metadata.
- Project Takeaway candidate construction should preserve source-specific
  policy boundaries rather than collapsing all candidates into
  `verified_insight`.
- Empty verification metadata must not create a clean `verified_insight` candidate.
- Human override must remain explicit, auditable, and exceptional.
- Rejected learning is caution context, not factual evidence or claim support.

Expected result:

- AI Radar can turn intelligence into project-level review objects without overclaiming evidence strength.

## Phase 3: Manual Intelligence End-to-End Loop

Goal: make user-provided material a first-class intelligence source.

Focus areas:

- upload PDF/image/text-style sources
- generate structured manual analysis
- recover manual-session-derived signal detail context
- connect manual outputs to Signal Detail, Insight, Workspace, Review Inbox, Knowledge, and Trajectory views
- preserve manual-source provenance

Expected result:

- Important material that did not arrive through automated ingestion can still become structured intelligence with clear provenance.

## Phase 4: Knowledge Quality and Project Matching

Goal: improve the reliability of project relevance and knowledge convergence.

Focus areas:

- shared topic taxonomy quality
- project match precision
- knowledge-created candidate source clarity
- candidate source labels that distinguish verified insight, knowledge convergence, signal completion, unverified manual entry, and manual override
- clearer blocked-action behavior for weak evidence paths

Expected result:

- Project relevance becomes more trustworthy and less dependent on broad keyword overlap.

## Phase 4A: Agent/Friction Tracking Memory

Goal: help Agent Watch and Friction Signals distinguish first-seen items,
persistent signals, fast-growing entities, cooling items, and early
supply-demand convergence.

Focus areas:

- daily Agent Watch tracking state
- daily Friction Signals tracking state
- local read-only tracking report
- status labels for `new`, `heating`, `sustained`, `cooling`, `dropped`, and
  `revived`
- recurring friction cluster summaries
- advisory supply-demand convergence candidates

Important boundary:

- tracking state is advisory until real daily pipeline output has been observed
  and calibrated; it must not control Project Takeaway gates, low-risk Action
  eligibility, or verification metadata.

Expected result:

- Agent Watch and Friction Signals become useful for trend memory, not just
  same-day discovery lists.

## Phase 5: Trajectory Timeline

Goal: give projects a useful history of judgments, reviews, actions, and learning moments.

Focus areas:

- project/topic trend grouping
- time-window summary deltas
- manual upload reason metadata in trajectory views
- ReviewRecord and CalibrationEvent event linking
- follow-up observations for Watch and Action states

Expected result:

- A project workspace can show not only current state, but how judgment changed over time.

## Phase 6: Reflection Integration

Goal: connect structured intelligence with long-horizon cognitive context without turning reflection into unsupported factual evidence.

Focus areas:

- reflection sync hardening
- reflection-polish human review calibration before any golden-output baseline
- reflection matching quality
- validation and observability
- deeper relationship UI
- optional resonance retrieval only after the base workflow is stable

Important boundary:

- Reflection content is cognitive context.
- Reflection content should not be treated as evidence for external claims unless a future explicit evidence-conversion path is designed.

Expected result:

- AI Radar can use reflection to improve context and judgment without confusing private cognition with external verification.

## Phase 7: GitHub Project Context Snapshots

Goal: let AI Radar understand connected project repositories well enough to discuss project relevance when model APIs cannot browse GitHub directly.

Light snapshot scope:

- README excerpt
- roadmap excerpt
- top-level repository tree
- recent commits
- manifest files
- lightweight architecture hints
- cached snapshot status: `fresh`, `partial`, `stale`, `failed`, `missing`, or `not_connected`

Deep scan scope, not yet implemented:

- broader file discovery
- architecture map generation
- module-level summaries
- implementation progress inference
- stronger repo-state comparison over time

Important boundary:

- Repo snapshots are project context, not verification evidence.
- A repo snapshot can help explain why a signal may be relevant to a project, but it cannot prove an external market, technical, or strategic claim.

Expected result:

- AI Radar API conversations can use cached project repo context instead of relying on model-side browsing.

## Phase 8: Skills System and Prompt Contract Hardening

Goal: make AI Radar's LLM capabilities more explicit, testable, and bounded.

Focus areas:

- keep `backend/app/prompts/registry.py` as the source of truth
- maintain clear prompt contracts
- distinguish observed LLM output from persisted output
- improve baseline evaluation for prompt skills
- finish or clearly block remaining Wave 1 skills
- avoid adding a third LLM executor path
- keep bounded edit governance and edit apply reports advisory until human
  maintainers explicitly approve any enforcement path

Expected result:

- AI Radar's LLM behavior becomes easier to evaluate, reason about, and improve.

## Phase 8.5: Insight Evaluation Substrate

Goal: prepare deterministic held-out insight evaluation before any strict gate.

Focus areas:

- human-selected 20 to 30 seeded cases
- case schema and local validator
- deterministic checks before any LLM judge
- clear separation between test/local data and trusted evaluation cases

Important boundary:

- An empty or unreviewed case set must not be treated as a benchmark.
- Strict-greater-than gates should wait until the held-out case set is stable.

Expected result:

- AI Radar can evaluate insight-quality changes without pretending local
  fixtures are production truth.

## Phase 9: Verification Spine

Goal: prevent weak or unsupported claims from becoming automatic actions.

Focus areas:

- evidence pack quality
- claim verification behavior
- verified insight creation
- low-evidence gates
- blocked downstream actions
- clear UI display of unsupported / thin-evidence interpretations
- schema-hardening audits for verification metadata before any breaking API
  contract change

Important boundary:

- Relevance and support are different concepts.
- A signal can be highly relevant to a project while still unsupported as evidence.
- Unsupported relevance should prompt deeper verification, not immediate downstream action.

Expected result:

- AI Radar can surface useful weak signals while preserving decision discipline.

## Out Of Scope

AI Radar should not become:

- a generic productivity app
- a broad Obsidian replacement
- a generic GitHub project management system
- a universal personal knowledge graph
- a tool that treats every generated interpretation as verified fact

Adjacent concepts from AI Systems Lab can inform AI Radar, but this repository should stay focused on intelligence generation, project relevance, review, and learning.

## Near-Term Development Queue

Current useful next slices:

- Project Learning Profile P1: summarize ReviewRecord / CalibrationEvent
  outcomes into project-level learning context for future judgment
- deeper repo scan: move beyond light README / ROADMAP / manifest context only
  when a concrete project-understanding gap appears
- improve Knowledge Quality and project match precision
- harden Manual Upload E2E behavior
- improve Reflection matching and observability
- keep verification and blocked-action gates aligned with real behavior

## Source Of Truth

Use these docs by purpose:

- `README.md` - project overview
- `ROADMAP.md` - product roadmap and current direction
- `AI_RADAR_PRODUCT_SPEC.md` - product boundaries and layer definitions
- `DEVELOPMENT_PLAN.md` - implementation planning
- `CURRENT_DEVELOPMENT_STATUS.md` - current execution status and validation queue
- `AI_CONTEXT.md` - compact architecture context
- `AGENTS.md` - coding-agent operating rules
- `docs/README.md` - broader docs index
