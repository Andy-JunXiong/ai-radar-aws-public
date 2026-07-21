# Agent Watch Tracking Roadmap

Last updated: 2026-04-14

## Purpose

This document explains how `Agent Watch` should evolve from a discovery/watchlist
feature into a lightweight repo tracking system.

The goal is not to replace the existing daily watchlist.
The goal is to add history gradually on top of it.

---

## Current State

Today, `Agent Watch` already does these things well:

- discovers candidate agent projects from GitHub, Hacker News, and Product Hunt
- normalizes them into a shared signal shape
- deduplicates and classifies them
- scores them into a daily watchlist
- publishes:
  - `signals/latest/agent_watch_signals.json`
  - `daily/latest/daily_radar.json -> agent_watch`

This means the feature already works as a daily discovery layer.

What it does **not** do yet is deep longitudinal tracking of the same repo/entity.

---

## Discovery vs Tracking

### Discovery / Watchlist

Discovery answers:

- what is newly worth watching today?
- which agent projects are surfacing now?
- which frameworks / apps / infra tools are getting traction?

### Tracking

Tracking answers:

- how has this repo changed over time?
- did attention sustain or fade?
- are stars, discussion, or launches accelerating?
- is this one-off noise or an emerging durable signal?

---

## Roadmap

### Phase 0. Read-Only Tracking State Helper

Status:
- `Implemented as local helper`

What this adds:

- a pure tracking layer that compares today's artifacts with an optional prior
  tracking state
- current code:
  - `app/intelligence/tracking/agent_friction_tracking.py`
  - `scripts/check_agent_friction_tracking.py`
- local report sections for:
  - new entities
  - heating entities
  - sustained entities
  - cooling / dropped entities
  - fastest-growing entities
  - recurring friction clusters
  - early supply-demand convergence candidates
- supported labels:
  - `new`
  - `heating`
  - `sustained`
  - `cooling`
  - `dropped`
  - `revived`

Current behavior:

- Agent Watch tracking uses `agent_watch_repo_snapshots.json`
- Friction tracking uses `friction_signals.json`
- first runs without prior state mark active entities as `new`
- true 1-day growth requires a previous tracking state
- daily pipeline now writes advisory tracking artifacts:
  - `data/output/agent_watch_tracking_state.json`
  - `data/output/friction_tracking_state.json`
  - `signals/latest/agent_watch_tracking_state.json`
  - `signals/<date>/agent_watch_tracking_state.json`
  - `signals/latest/friction_tracking_state.json`
  - `signals/<date>/friction_tracking_state.json`
- no pipeline enforcement or downstream action gates are introduced by this
  helper

Why this matters:

- it creates a safe way to inspect "new vs persistent vs heating" before
  promoting the logic into the daily pipeline or UI
- it keeps tracking advisory until real daily data can calibrate thresholds

### Phase 1. Preserve Daily Repo Snapshots

Status:
- `Started`

What this adds:

- a daily snapshot layer for canonical agent entities
- current output:
  - `data/output/agent_watch_repo_snapshots.json`
  - `signals/latest/agent_watch_repo_snapshots.json`
  - `signals/<date>/agent_watch_repo_snapshots.json`

Why this matters:

- it gives us a history-ready artifact immediately
- it does not require a major schema redesign
- it keeps the current Agent Watch MVP intact

Current snapshot fields include:

- `entity_id`
- `title`
- `canonical_url`
- `source`
- `source_type`
- `agent_subtopic`
- `published_at`
- `captured_at`
- `agent_watch_score`
- source-specific metadata such as:
  - `repo_stars`
  - `language`
  - `hn_points`
  - `hn_comments`
  - `product_hunt_votes`

### Phase 2. Build Entity History Views

Planned:

- load current snapshot plus prior dated snapshots
- show:
  - first seen date
  - days observed
  - latest score vs prior score
  - basic repo momentum

This can start with top tracked entities only.

### Phase 3. Add Repo Detail Pages

Planned:

- `/agent-watch/[entity_id]`
- show:
  - timeline
  - source mentions
  - score changes
  - subtopic history
  - why this repo is still worth tracking

### Phase 4. Upgrade Tracking Quality

Planned:

- stronger cross-source entity merging
- canonical repo identity resolution
- better heuristics for:
  - releases
  - contributor signals
  - issue / PR health
  - discussion velocity

### Phase 5. Add LLM Repo Profiles

Planned:

- generate an `agent_watch_repo_profiles.json` artifact for tracked repos
- use a Claude-first reasoning task for repo understanding
- summarize for each repo:
  - what the repo actually does
  - which agent category it belongs to
  - who it seems built for
  - why it may matter for AI Radar
  - how it could help the owner's personal projects
  - which risks or limitations are visible from the repo surface

Recommended inputs:

- repo title and description
- README excerpt
- top topics / tags
- language and star level
- recent watchlist signals and matched keywords
- basic trend context from snapshot history

Recommended output shape:

- `entity_id`
- `generated_at`
- `provider_used`
- `model_used`
- `repo_summary`
- `what_it_does`
- `why_it_matters`
- `project_fit`
- `suggested_use_cases`
- `risks`
- `confidence`

Design note:

- this should be a profile layer on top of tracking, not part of raw signal collection
- start with the top tracked repos only
- refresh profiles on a slower cadence than the daily watchlist
- preserve the raw watchlist score separately from the LLM judgment

---

## Design Principle

Do not jump directly from watchlist MVP to a heavy monitoring system.

Preferred path:

1. keep the daily discovery layer
2. preserve stable daily snapshots
3. build history views on top
4. only then add richer entity-level tracking
5. add LLM repo profiles as an interpretation layer

This keeps the system lightweight while still creating real memory over time.
