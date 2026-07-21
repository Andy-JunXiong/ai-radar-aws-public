# AI Radar Product Specification

## Purpose

This document defines the product direction for AI Radar in a way that stays aligned with current repository reality.

It should answer:

1. What AI Radar is now
2. What it is becoming next
3. What product lines belong inside this repo
4. Which directions are explicitly out of scope

This document is not the daily execution tracker.

Use:

- `CURRENT_DEVELOPMENT_STATUS.md` for day-to-day reality
- `DEVELOPMENT_PLAN.md` for active implementation tracks

---

## Product Positioning

AI Radar is an AI-native intelligence system for the AI ecosystem.

Its purpose is to transform external signals into structured intelligence that can support:

- situational awareness
- project relevance mapping
- strategic interpretation
- lightweight decision support
- review and learning over time

Core intelligence pipeline:

**Signal -> Insight -> Trend -> Strategic Intelligence**

Current product extension:

**Strategic Intelligence -> Decision -> Review -> Learning**

AI Radar is not:

- a generic news reader
- a general knowledge management product
- an Obsidian replacement
- a GitHub project management system
- a broad personal productivity platform

---

## Product Goal

Help the user:

- detect meaningful AI signals early
- understand why a signal matters
- connect signals to active projects and longer-term goals
- distinguish weak evidence from strong evidence
- turn intelligence into action candidates
- review what happened later and learn from outcomes

The product should sit between:

- information overload
- and human judgment

It should not merely collect information. It should improve decision quality.

---

## Current Product Reality

AI Radar is already a live, usable system with multiple implemented product surfaces.

Current reality includes:

- Signals
- Radar
- Workspace
- Project Takeaways
- Subscriptions
- Manual analysis flows
- AI Agent Watch MVP
- Friction Signals MVP
- Decision Layer & Review Loop MVP
- Reflection scaffold and UI

AI Radar is no longer only a signal-processing engine. It is now a multi-surface intelligence product with an early closed loop.

---

## Product Layers

### 1. Signal Layer

This is the observation layer.

Responsibilities:

- collect signals from external sources
- normalize them
- classify topics
- score importance
- preserve source metadata

Typical inputs:

- AI blogs
- research announcements
- infrastructure releases
- ecosystem commentary
- manual uploads

Canonical signal outputs should remain structured, queryable, and reusable by downstream layers.

### 2. Insight Layer

This is the interpretation layer.

Responsibilities:

- explain why a signal matters
- map signals to projects and career context
- generate synthesized interpretation
- produce reusable structured insight fields

This layer should increasingly distinguish between:

- direct observation
- supported interpretation
- inferred relevance
- speculative claims

### 3. Trend and Strategic Intelligence Layer

This is the synthesis layer across signals and time.

Responsibilities:

- summarize topic movement
- identify rising or important topics
- generate daily radar outputs
- surface strategic relevance beyond single items

This layer exists to prevent the product from collapsing into a feed of isolated items.

### 4. Decision Layer

This is the action recommendation layer.

Responsibilities:

- turn verified intelligence into project-level judgment objects
- support candidate review
- support accept / reject / watch / action / merge decisions
- support review queue and review completion
- build lightweight learning and calibration summaries from outcomes

This layer should remain thin and tightly coupled to intelligence quality.

AI Radar should not generate strong downstream action from weak upstream evidence.

Current primary direction:

- `Project Takeaways` should become the main review / watch / action layer
- `Decision Card` remains a legacy MVP object, not the primary future-facing object

### 5. Reflection Layer

This is the long-horizon cognitive layer.

Responsibilities:

- connect AI Radar with deeper human reflection
- preserve read-only links to GitHub-backed reflection artifacts
- support reflection browsing, sync, and matching
- enrich intelligence with deeper historical context when appropriate

Important design rule:

- GitHub remains the source of truth for deep reflection content
- AI Radar reads and indexes
- AI Radar does not become the authoring source for deep reflection
- HTML-backed deep conversations / deep reflections should not be forced into a
  rigid schema in the near term
- Treat highly variable deep reflections as Layer 3 / stream-of-consciousness
  cognition material: preserve and expose them first, then derive structured
  judgment events only when the user explicitly marks a decision or review moment
- Do not turn deep reflections directly into externalized skills or automatic
  trajectory-memory objects until real usage patterns prove the schema is stable
- The first acceptable schema bridge is a minimal optional `cognitive_layer`
  marker, not a full deep-reflection schema rewrite:
  - `L1`: infrastructure / externalizable skill material
  - `L2`: reusable public structure with private judgment content
  - `L3`: stream-of-consciousness / judgment trajectory material
  - `unclassified`: default until the user or a future reviewed process marks it

### 6. Quality and Control Layer

This is the discipline layer that governs how intelligence is produced.

Responsibilities:

- model routing
- execution policy
- context strategy
- output validation
- fallback policy
- reasoning + verification
- metrics / monitoring

This layer is now strategically important.

The product should not treat every generated output as equally trustworthy.

Over time, this layer should enforce:

- evidence sensitivity
- uncertainty boundaries
- confidence discipline
- claim-aware verification
- downstream action gating
- pipeline and LLM reliability visibility

Current verification design rule:

- evidence sufficiency answers whether source material is traceable enough to attempt verification
- claim verification answers whether specific claims are supported by specific evidence items
- downstream action gating should use both evidence level and claim support, not evidence level alone
- LLM-generated summaries are interpretation/context and should not be treated as primary evidence

The verification module should be framed as an `Evidence-Bounded Verification Layer`.

Current monitoring design rule:

- metrics should observe system health and quality-gate outcomes without becoming a broad analytics platform
- the first monitoring layer should be file-backed and additive
- metrics must not log prompt text, response text, uploaded content, secrets, credentials, or raw private user content
- Metrics / Monitoring is separate from Project Review calibration:
  - monitoring asks whether the system ran reliably and what happened at runtime
  - calibration asks whether the product improved judgment quality over time

It should not promise:

- automatic proof that a signal is true
- automatic proof that a signal is valuable
- automatic roadmap or action changes

It should promise:

- automatic evidence classification
- automatic claim-level downgrade
- automatic downstream action gating
- semi-automatic project relevance recommendation
- human final review for strategic value and action commitments

The product philosophy is:

```text
AI Radar does not automatically prove signals true.
It classifies the evidential status of claims and controls downstream action eligibility.
```

This creates a tiered verification system:

- Level 1: source traceability and evidence sufficiency, highly automated
- Level 2: claim extraction and claim type, highly automated
- Level 3: claim-evidence matching, medium automation
- Level 4: support status and caveats, medium automation
- Level 5: value to active projects, semi-automated with human review
- Level 6: strategic action or roadmap change, human-controlled

The closer a judgment is to factual traceability, the more it can be automated.
The closer a judgment is to strategic value or action, the more human review it needs.

Example judgment split:

- a claim that a repo recently gained activity can be directly supported if traceable repo metrics exist
- a claim that the repo represents a market trend should be downgraded unless corroborated by broader evidence
- a claim that the trend matters to AI Radar requires project relevance mapping plus human review
- a recommendation to change roadmap should not become an automatic action

Current Project Takeaway invariant:

- Project Takeaway writes must flow through the guarded candidate/write path
  and carry Project Takeaway verification context, or be explicitly marked as
  unverified/manual/knowledge-review/override with corresponding blocked
  actions and audit metadata
- valid source categories are distinct: `verified_insight`,
  `knowledge_convergence`, `signal_completion`, `unverified_manual_entry`, and
  `manual_project_takeaway_override`
- `knowledge_convergence_review_candidate` is review context; it can prepare
  Project Takeaway review and Watch, but it is not verified low-risk Action
  evidence without further review or explicit override
- `signal_completion` writes without sufficient verification context must be
  marked as `unverified_manual_entry` with `verification_required=true`
- missing verification metadata must not be labeled as `verified_insight`
- `blocked_downstream_actions` controls automatic Project Takeaway and
  low-risk Action eligibility
- blocked Confirm / Action decisions require dedicated override paths with a
  manual note and expected outcome so they can be calibrated later
- Confirm and Action are review decisions over a candidate; `action_completed`
  is an Action lifecycle state, not a sixth review outcome
- Backend outcome constants live in
  `backend/app/services/project_takeaway_constants.py`: `ReviewOutcome`
  covers `confirmed`, `rejected`, `dismissed`, `watch`, and `action`; Action
  lifecycle state is tracked separately as `open` / `completed`

### 7. Skills Layer

AI Radar also includes an internal Skills System for turning repeated prompt-defined capabilities into managed, testable product skills.

This layer sits across the intelligence pipeline rather than existing as a separate end-user page.

Its purpose is to make prompt capabilities:

- explicit
- reusable
- evaluable
- exportable
- easier to improve without losing product discipline

Current source-of-truth rule:

- `backend/app/prompts/registry.py` is the source of truth for AI Radar prompt capabilities

The Skills System should remain aligned with code reality:

- prompt definitions live in code
- exported skill artifacts are generated from those definitions
- documentation should follow the registry, not drift away from it

Current layer model:

- Input skills
  - `input-image-analyze`
  - `input-text-analyze`
- Processing skills
  - `radar-friction-to-opportunity`
  - `radar-agent-repo-profile`
  - `radar-signal-insight`
- Output / utility skills
  - `reflection-polish`
  - `util-json-repair`

Current engineering rules for Skills:

- Prompt Registry and Skill definitions should behave as one system
- strictly separate observed LLM output contract from persisted output observations
- do not fabricate missing data in pre-schema or pre-persistence stages
- use baseline evaluation as an improvement discipline
- judge fallback behavior by output quality, not provider identity

Current evaluation method:

- horizontal baseline scoring
- 8-dimension, 100-point scoring
- same-skill golden cases are scored together for comparison

Current Wave 1 status:

- 4 of 7 internal prompt skills are baseline locked:
  - `radar-friction-to-opportunity`
  - `radar-agent-repo-profile`
  - `input-image-analyze`
  - `radar-signal-insight`
- 3 of 7 remain survey / blocker-driven:
  - `reflection-polish`
  - `input-text-analyze`
  - `util-json-repair`
- the current average across the four locked skills is about `76.25 / 100`
- the main cross-skill prompt-contract issue is the boundary of
  `synthesized_insight`: it should synthesize without drifting beyond the
  input context or duplicating summary text

Core dimensions:

- Specificity
- Accuracy
- Structural Coherence
- Project Mapping
- Career Insight
- Synthesis Quality
- Actionability
- Conciseness

The Skills System is not a side experiment.

It is part of how AI Radar improves prompt quality, output reliability, and internal capability boundaries over time.

Boundary with cognitive-assets concept-skills:

- AI Radar internal prompt skills are system production capabilities
- `cognitive-assets/concept-skills/` are human judgment frameworks
- current concept-skills include:
  - `five-layer-ai-system-architecture`
  - `cross-layer-objects-deserve-own-layer`
  - `memory-specialization-for-decision-intelligence`
- concept-skills track lineage, `application_log`, maturity, open questions,
  and falsification conditions
- concept-skills should not be folded into AI Radar's prompt registry or
  signal/reflection matching logic
- a future AI Radar UI may show `Linked Concept Skills` on reflection detail
  only as a conditional reverse-reference display from
  `extracted_from_reflections`

---

## Current Implemented Product Lines

### AI Agent Watch

Current position:

- implemented as a usable MVP

Current role:

- discover and summarize agent ecosystem movement
- support early repo tracking
- expose high-signal items in radar and dedicated UI

### Friction Signals

Current position:

- implemented as a working MVP

Current role:

- identify ecosystem pain points
- turn friction into structured signals
- support opportunity interpretation later

### Decision Layer & Review Loop

Current position:

- implemented as a usable legacy MVP / Phase 1 shipped
- product direction now shifts toward `Project Takeaway Review Loop`

Current role:

- preserve useful review / learning loop logic from the legacy MVP
- provide concepts and compatibility for the next `Project Takeaway Review Loop`

### Project Takeaway Review Loop

Current position:

- design confirmed
- implementation not yet aligned

Current role:

- become the main project judgment layer
- receive `VerifiedInsight` candidates
- own:
  - review inbox
  - accepted project takeaways
  - watch list
  - action list
  - review records
  - learning / calibration hooks

### Reflection

Current position:

- in progress, meaningful scaffold exists

Current role:

- connect short-horizon signals with longer-horizon cognition

### Manual Intelligence

Current position:

- implemented as a meaningful product slice

Current role:

- allow user-supplied materials to enter the intelligence flow

### Skills System

Current position:

- actively in progress
- Wave 1 is partially locked and partially blocked / pending

Current role:

- formalize prompt capabilities inside the product
- provide evaluation discipline for prompt quality
- support repeatable improvement of internal LLM skills

Current progress snapshot:

- locked:
  - `radar-friction-to-opportunity`
  - `radar-agent-repo-profile`
  - `input-image-analyze`
  - `radar-signal-insight`
- blocked:
  - `reflection-polish`
- survey pending:
  - `input-text-analyze`
  - `util-json-repair`

---

## Active Product Directions

These are the main active product-quality directions now.

### 1. Stronger Intelligence Quality Control

This includes:

- model routing expansion
- execution policy hardening
- output validation
- Unified Reasoning & Verification Layer

Why it matters:

- weak signals can currently produce overconfident downstream outputs
- the product must increasingly distinguish evidence-backed intelligence from thin inference

This track now directly supports:

- `Project Takeaway Review Loop`
- review / watch / action eligibility
- future memory seeds

Current staged direction:

- first, maintain evidence-pack, evidence-sufficiency, low-evidence gate, provenance, and transparent reason-code foundations
- next, implement `Signal Verification MVP v1` with claim extraction, claim verification, and `VerifiedInsight` synthesis
- then route verified insights into `Project Takeaway Review`, not legacy `Decision Card`

MVP definition for `Signal Verification MVP v1`:

- automatically classify evidence as `insufficient`, `thin`, `sufficient`, or `strong`
- automatically extract 1-5 typed claims from raw insight content
- automatically downgrade claims using support statuses:
  - `directly_supported`
  - `partially_supported`
  - `inferred`
  - `unsupported`
  - `contradicted`
- automatically gate downstream eligibility:
  - no traceable evidence -> `observation_only`
  - single weak source -> `watch_only`
  - trend / causal / predictive claims -> downgrade unless corroborated
  - only `verified` or `partially_verified` insight can enter `Project Takeaway` review
- keep project relevance semi-automated
- keep final project takeaway, roadmap, and action decisions human-reviewed

### 1A. Skills Wave 1 Completion

Near-term product goal:

- all 7 current skills should either be:
  - locked with a clear baseline
  - or explicitly marked with a written blocker task

Immediate tracks:

- resolve the infra blocker for `reflection-polish`
- move `input-text-analyze` from survey to baseline when viable
- move `util-json-repair` from survey to baseline

The current milestone definition for Wave 1 is:

- all seven skills are either locked
- or have a clearly written blocker task attached

### 1B. Skills System Backlog

After Wave 1, the next improvement path should come from evaluation-discovered engineering issues.

Priority directions currently include:

- investigate output truncation in `synthesized_insight`
- ground `radar-signal-insight` claims more strictly in input context
- improve distinction between insight and summary
- enforce stronger prompt contracts around relevance-to-projects typing
- tag fallback outputs with generation source
- investigate systematic primary-vs-fallback quality differences
- continue persistence unification and confidence/UI clarity work

### 2. Agent Watch Evolution

Direction:

- move from watchlist-style discovery toward lightweight repo tracking

### 3. Reflection Hardening

Direction:

- improve sync quality
- improve matching quality
- improve observability and reliability

### 4. Better Closed-Loop Learning

Direction:

- improve the relationship between insight, decision, review, and memory
- keep the loop lightweight, but make it genuinely useful

Current implementation direction:

- the loop should be implemented through `Project Takeaways`
- not through continued expansion of `Decision Card` as the primary object

### 4A. Metrics / Monitoring Layer

Near-term product goal:

- add a lightweight event foundation for observing pipeline reliability, collector behavior, LLM call health, and verification gating outcomes

Current status:

- MVP implemented locally on 2026-05-04
- no dashboard, alerting, AWS integration, or behavior changes yet

MVP definition:

- record pipeline run events
- record collector run events
- record LLM call metadata
- record verification outcome metadata
- generate a daily summary JSON
- store metrics as file-backed JSON / JSONL artifacts, preferably under `data/output/metrics/`

Explicit non-goals:

- complex dashboard
- Grafana / Datadog integration
- real-time alerting
- AWS CloudWatch Metrics integration
- user behavior analytics
- billing-grade cost accounting
- changes to verification logic, collector architecture, Project Takeaways UI, or Watch / Action / Review behavior

Primary deep doc:

- `docs/metrics-monitoring-mvp.md`

### 5. Skill Framework Evolution

Longer-horizon direction:

- evolve from isolated internal skills toward a more systematic capability framework

Potential milestones:

- Wave 2 skill expansion
- standardized new-skill intake flow:
  - survey
  - pick
  - baseline
  - lock
- single-image revisit coverage for Skill 3
- independent checkpointing around `reflection-polish-review-gate`
- eventual connection to a broader Darwin.skill-style evolution flow when the number of stable skills is high enough

Possible future decoupling path:

- generic skills may later be extracted into a reusable package
- AI Radar-specific `radar-*` skills should remain product-internal unless there is a strong reason to externalize them
- open-sourced skill assets can become portfolio artifacts without dissolving the AI Radar product core

---

## Product Quality Rules

### 1. Do not collapse into a generic feed

Signal volume is not the goal.

The system must emphasize:

- signal quality
- structured interpretation
- strategic relevance
- action discipline

### 2. Do not collapse into generic note-taking

Reflection and knowledge should support the intelligence engine, not replace it with a broad writing workspace.

### 3. Do not collapse into ungrounded AI fluency

The product should increasingly separate:

- observation
- interpretation
- recommendation
- speculation

Outputs with thin evidence should be downgraded rather than overconfidently polished.

### 4. Preserve a thin product core

AI Radar should remain centered on:

- intelligence generation
- relevance mapping
- decision support
- review and learning

It should not become a broad platform with unrelated adjacent features.

---

## Non-Goals

The following are currently out of scope unless explicitly re-scoped later.

- turning AI Radar into a generic team collaboration platform
- turning AI Radar into a general project tracker
- replacing GitHub or Obsidian as a full authoring environment
- building a heavy database-first platform before the current lightweight patterns prove insufficient
- introducing large architectural rewrites without clear execution need

---

## Storage and State Direction

Current repo reality:

- file-backed JSON state is normal
- S3-backed patterns are already part of the system
- mutable state is often stored through lightweight local-first files

Near-term rule:

- keep using the current lightweight storage patterns where they fit
- prefer additive hardening over premature infrastructure expansion

Do not treat database migration as a prerequisite for product progress.

---

## Product Boundary With Adjacent Systems

AI Radar can integrate with broader AI Systems Lab ideas, but this repo should remain focused on the AI Radar intelligence engine.

Important example:

- deep reflection provenance and some memory-heavy capabilities may depend on a separate `trajectory-memory` repository

Trajectory Memory should now be treated in two levels:

1. AI Radar internal trajectory seed
- already being produced by the Verification + Project Takeaway Review Loop
- derived from `VerifiedInsights`, `ProjectTakeaways`, `ReviewRecords`,
  `CalibrationEvents`, and review/watch/action outcomes
- lightweight
- not a separate heavy product inside this repo

2. External `trajectory-memory` repository
- longer-horizon memory modeling
- richer external memory architecture
- should not block AI Radar's internal review/learning implementation

That means:

- AI Radar may connect to adjacent systems
- but should not absorb every adjacent capability into this repo
- deep reflection HTML, schema evolution, and Trajectory Memory should stay
  loosely connected for now: AI Radar can preserve links and lightweight
  metadata, but should not standardize every deep conversation as a trajectory
  event or reusable skill
- Layer 3 and Trajectory Memory should be understood as aligned concepts:
  Layer 3 preserves the user's judgment trajectory; Trajectory Memory is the
  longer-horizon structure and visualization of that trajectory

Near-term AI Radar opportunity:

- `Trajectory Timeline` MVP now exists as the first AI Radar-side
  trajectory visualization surface over existing `ReviewRecord` and
  `CalibrationEvent` data
- current backend surface:
  - `GET /projects/trajectory-events`
  - returns normalized trajectory events, derived risk level, trajectory signal
    type, query filters, and summary mixes
- current frontend surface:
  - `/workspace/projects/trajectory`
  - shows review/calibration judgment events over time by project, outcome,
    source, risk level, signal type, and verification quality
- next opportunity is to keep refining this timeline into a clearer judgment
  evolution view before building the full external `trajectory-memory` system
- Manual Upload should eventually capture why the user chose to upload a
  material, because that choice is itself a judgment signal:
  - `upload_reason`
  - `intended_use`
  - optional `cognitive_layer`

---

## Future Product Directions

The following directions are real, but not yet mature product lines in this repo:

- Knowledge Distillation
- full external Trajectory Memory as a first-class system layer
- richer AI Radar-side Trajectory Timeline / visualization over existing
  review/calibration events
- deeper semantic reflection retrieval
- richer verified reasoning across all intelligence outputs

These should be treated as deliberate future tracks, not implied current capabilities.

---

## Practical Reading Order

If you need current execution reality:

1. `CURRENT_DEVELOPMENT_STATUS.md`
2. `DEVELOPMENT_PLAN.md`

If you need current product direction:

1. this file
2. `DEVELOPMENT_PLAN.md`
3. the relevant deep doc in `docs/`

If you need implementation rules:

1. `AGENTS.md`
