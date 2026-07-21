# AI Radar --- AI Agent Watch Feature

## Goal

Add a new signal discovery dimension to AI Radar:

**AI Agent Watch**

The goal is to automatically track new AI agent projects from:

-   GitHub
-   Product Hunt
-   Hacker News

This feature should detect emerging agent frameworks, tools, and
systems.

Examples:

AutoGPT\
CrewAI\
LangGraph\
OpenDevin\
AgentOps\
Multi-agent frameworks

------------------------------------------------------------------------

# Architecture Context

AI Radar pipeline:

collectors\
→ processors\
→ scoring\
→ selector\
→ analysis\
→ summary

Main entry:

app/main_summary_v2.py

Signals output:

signals/latest/signals.json

------------------------------------------------------------------------

# Feature Overview

This feature introduces a new topic:

topic = "ai_agents"

Signals related to AI agents should be collected and processed like
existing signals.

------------------------------------------------------------------------

# Step 1 --- Implement Agent Collectors

Create collectors for agent-related sources.

## GitHub collector

Detect new repos with keywords:

-   agent
-   autonomous agent
-   multi agent
-   agent framework
-   ai agent
-   agentic

Example sources:

-   GitHub Trending\
-   GitHub Search API

Signals to capture:

-   repo_name
-   description
-   stars
-   language
-   created_at
-   repo_url

------------------------------------------------------------------------

## Product Hunt collector

Detect launches tagged with:

-   AI agent
-   AI automation
-   autonomous AI
-   AI assistant
-   agent platform

Signals:

-   product_name
-   tagline
-   votes
-   launch_date
-   product_url

------------------------------------------------------------------------

## Hacker News collector

Detect posts with keywords:

-   AI agent
-   agent framework
-   autonomous AI
-   multi-agent system

Signals:

-   title
-   url
-   points
-   comments
-   posted_time

------------------------------------------------------------------------

# Step 2 --- Signal Normalization

Normalize agent signals into existing schema.

Example:

{ "title": "...", "summary": "...", "source": "github", "topic":
"ai_agents", "score": null, "published_at": "...", "metadata": {
"repo_stars": 1200, "repo_url": "...", "tags": \["agent","framework"\] }
}

------------------------------------------------------------------------

# Step 3 --- Scoring Logic

Add a new scoring dimension:

**Agent relevance score**

Example scoring rules:

-   GitHub stars \> 1000 → high signal
-   Product Hunt votes \> 200 → high signal
-   Hacker News points \> 100 → high signal

Optional fields:

-   agent_relevance_score
-   buildability_score
-   strategic_relevance_score

------------------------------------------------------------------------

# Step 4 --- Integrate with Pipeline

Agent signals should flow through the same pipeline:

collectors\
→ processors\
→ scoring\
→ selector\
→ analysis\
→ summary

Do NOT build a separate pipeline.

------------------------------------------------------------------------

# Step 5 --- Radar Output

Add a new section in Daily Radar:

AI Agent Watch

Example:

AI Agent Watch

1.  CrewAI gaining traction with new multi-agent orchestration
    framework.
2.  New open-source agent debugging tool released.
3.  Autonomous coding agent project trending on GitHub.

------------------------------------------------------------------------

# Implementation Constraints

Keep MVP simple.

Do NOT:

-   redesign the pipeline
-   introduce heavy LLM analysis
-   add complex infrastructure

Focus on:

-   clean signal discovery
-   low noise
-   good scoring

------------------------------------------------------------------------

# Expected Result

AI Radar should automatically surface:

-   new agent frameworks
-   trending open-source agent projects
-   agent ecosystem tools

This becomes a dedicated intelligence layer:

**Agent Ecosystem Intelligence**

------------------------------------------------------------------------

# Current MVP Status

The current MVP implementation already includes:

-   GitHub agent collector
-   Hacker News agent collector
-   Product Hunt agent collector
-   signal normalization into `topic = "ai_agents"`
-   lightweight classifier:
    -   `agent_framework`
    -   `agent_app`
    -   `agent_infra`
-   agent scoring:
    -   `agent_relevance_score`
    -   `buildability_score`
    -   `strategic_relevance_score`
    -   `agent_watch_score`
-   merge into the existing collector output
-   Daily Radar `agent_watch` block
-   frontend visibility:
    -   `/radar`
    -   `/agent-watch`

Current local output files:

-   `data/output/github_agent_signals.json`
-   `data/output/hackernews_agent_signals.json`
-   `data/output/agent_watch_signals.json`
-   `data/output/agent_watch_smoke_test.json`
-   `data/output/daily_radar.json`

Current S3 upload targets for deployed daily runs:

-   `signals/latest/agent_watch_signals.json`
-   `signals/<date>/agent_watch_signals.json`
-   `daily/latest/daily_radar.json`
-   `daily/<date>/daily_radar.json`

------------------------------------------------------------------------

# Local Verification

## Fast smoke test

Run the local smoke test entrypoint:

`python -m app.intelligence.agent_watch_smoke_test`

Expected local outputs:

-   `data/output/github_agent_signals.json`
-   `data/output/agent_watch_signals.json`
-   `data/output/collected_signals.json`
-   `data/output/agent_watch_smoke_test.json`

Check:

-   raw GitHub/HN signals exist
-   normalized signals have `topic = "ai_agents"`
-   scored signals have `agent_watch_score`
-   smoke summary includes `highlights`

## Local frontend check

If local frontend/backend are running, validate:

-   `/radar`
-   `/agent-watch`

Expected:

-   `AI Agent Watch` appears in Radar Summary
-   `/agent-watch` shows runtime snapshot, source/subtopic breakdown, and tracked signals

------------------------------------------------------------------------

# AWS / Daily Pipeline Verification

After deploying backend code and running the daily pipeline:

1. Confirm collector stage ran
2. Confirm `agent_watch_signals.json` uploaded to S3
3. Confirm `daily_radar.json` contains `agent_watch`
4. Confirm frontend can read:
   - `/radar/intelligence`
   - `/radar/agent-watch`

Suggested checks:

-   S3 key exists:
    -   `signals/latest/agent_watch_signals.json`
-   S3 key exists:
    -   `daily/latest/daily_radar.json`
-   `daily/latest/daily_radar.json` contains:
    -   `agent_watch.signal_count`
    -   `agent_watch.top_signal_count`
    -   `agent_watch.highlights`

Frontend checks:

-   `/radar`
-   `/agent-watch`

Expected:

-   runtime source list is non-empty
-   signals/highlights counts are non-zero when collector finds results
-   cards show subtopic, score, and source metadata

------------------------------------------------------------------------

# Remaining Step

Product Hunt note:

-   the collector uses `PRODUCT_HUNT_API_TOKEN`
-   if the token is not configured, Product Hunt collection safely returns no signals
