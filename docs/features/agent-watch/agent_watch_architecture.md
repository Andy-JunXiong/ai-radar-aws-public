# AI Radar --- Agent Watch Architecture

## Overview

Agent Watch is a new intelligence track inside AI Radar designed to
detect and track new AI agent frameworks, tools, and projects across the
internet.

Sources:

-   GitHub
-   Product Hunt
-   Hacker News

Agent Watch integrates into the existing AI Radar pipeline and does NOT
introduce a separate system.

------------------------------------------------------------------------

# Existing AI Radar Pipeline

AI Radar architecture:

collectors\
→ processors\
→ scoring\
→ selector\
→ analysis\
→ summary

Main pipeline entry:

app/main_summary_v2.py

Signals output:

signals/latest/signals.json

Agent Watch must plug into this architecture.

------------------------------------------------------------------------

# High-Level Architecture

Agent Watch components:

Agent Collectors\
→ Agent Classifier\
→ Agent Scoring\
→ Pipeline Integration\
→ Radar Output

Architecture:

External Sources ↓ Agent Collectors ↓ Signal Normalization ↓ Agent
Classifier ↓ Agent Scorer ↓ AI Radar Pipeline ↓ signals.json ↓ Daily
Radar Summary

------------------------------------------------------------------------

# Directory Structure

Suggested structure inside the AI Radar project:

app/

    intelligence/

        collectors/
            github_agent_collector.py
            producthunt_agent_collector.py
            hackernews_agent_collector.py

        classifiers/
            agent_classifier.py

        scorers/
            agent_signal_scorer.py

        processors/
            agent_signal_processor.py

------------------------------------------------------------------------

# Component Design

## 1. GitHub Agent Collector

File:

github_agent_collector.py

Purpose:

Collect repositories related to AI agents.

Example data sources:

GitHub Search API\
GitHub Trending

Keywords:

agent\
ai agent\
agent framework\
multi-agent\
agentic

Signals collected:

repo_name\
description\
stars\
created_at\
repo_url

------------------------------------------------------------------------

## 2. Product Hunt Agent Collector

File:

producthunt_agent_collector.py

Purpose:

Detect newly launched AI agent tools.

Signals collected:

product_name\
tagline\
votes\
launch_date\
product_url

------------------------------------------------------------------------

## 3. Hacker News Agent Collector

File:

hackernews_agent_collector.py

Purpose:

Detect discussions and launches related to agent projects.

Signals collected:

title\
url\
points\
comments\
posted_time

------------------------------------------------------------------------

# Signal Normalization

All signals must be normalized into the existing AI Radar signal schema.

Example normalized signal:

{ "title": "...", "summary": "...", "source": "github", "topic":
"ai_agents", "published_at": "...", "score": null, "metadata": {
"repo_stars": 1200, "repo_url": "...", "tags": \["agent","framework"\] }
}

------------------------------------------------------------------------

# Agent Classifier

File:

agent_classifier.py

Purpose:

Determine if a signal truly represents an AI agent project.

Rules:

keyword detection\
metadata signals\
repo description analysis

Output:

subtopic classification:

agent_framework\
agent_app\
agent_infra

------------------------------------------------------------------------

# Agent Scoring

File:

agent_signal_scorer.py

Add scoring fields:

agent_relevance_score\
buildability_score\
strategic_relevance_score

Example heuristics:

GitHub stars \> 1000 → high signal

Product Hunt votes \> 200 → strong signal

HN points \> 100 → strong signal

------------------------------------------------------------------------

# Pipeline Integration

Agent signals must be inserted into the existing AI Radar pipeline.

Example integration point:

collectors stage

Pseudo flow:

signals = collect_agent_signals()

signals = classify_agent_signals(signals)

signals = score_agent_signals(signals)

signals = merge_with_existing_signals(signals)

------------------------------------------------------------------------

# Daily Radar Integration

Daily radar should include a new block:

AI Agent Watch

Example:

AI Agent Watch

1.  CrewAI gaining traction with new multi-agent orchestration
    framework.
2.  New open-source agent debugging tool released.
3.  Autonomous coding agent trending on GitHub.

------------------------------------------------------------------------

# Data Output

Agent signals are stored in:

signals/latest/signals.json

Additional Agent Watch outputs:

-   `signals/latest/agent_watch_signals.json`
-   `daily/latest/daily_radar.json` → `agent_watch`
-   local dev fallback:
    -   `data/output/agent_watch_smoke_test.json`

Example entry:

{ "title": "CrewAI multi-agent framework gaining traction", "source":
"github", "topic": "ai_agents", "score": 0.91, "published_at":
"2026-04-11", "metadata": { "repo_stars": 5400, "repo_url":
"https://github.com/crewAI/crewAI" } }

------------------------------------------------------------------------

# MVP Implementation Steps

Step 1

Implement GitHub agent collector.

Step 2

Add agent classifier.

Step 3

Add agent scoring logic.

Step 4

Integrate into main pipeline.

Step 5

Add Daily Radar Agent Watch block.

------------------------------------------------------------------------

# Design Principles

Keep the system:

simple\
modular\
integrated with existing pipeline

Avoid:

heavy LLM analysis\
separate services\
complex orchestration

Goal:

high-quality agent ecosystem signals.

------------------------------------------------------------------------

# Current Runtime Notes

Current implemented runtime sources:

-   GitHub
-   Hacker News
-   Product Hunt

Current frontend surfaces:

-   `/radar`
-   `/agent-watch`

Current fallback behavior:

-   `daily_radar.agent_watch` is preferred
-   if daily output is missing in local dev, backend can fall back to:
    -   `agent_watch_smoke_test.json`
