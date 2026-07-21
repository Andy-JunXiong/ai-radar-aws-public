# AI Radar Future Feature Spec (V2 Concepts)

This document consolidates several future enhancements discussed for AI
Radar. These features are NOT required for the current MVP but define
potential evolution paths for the system.

They can be implemented incrementally later without breaking the current
architecture.

------------------------------------------------------------------------

# 1. AI Agent Watch

Goal: Track the evolution of the AI agent ecosystem by monitoring:

-   GitHub
-   Product Hunt
-   Hacker News

Purpose:

Detect:

-   new agent frameworks
-   agent infrastructure tools
-   multi‑agent systems
-   autonomous AI projects

Integration:

Signal Collectors → Processing → Scoring → Insight Generation

New topic:

topic = "ai_agents"

Example Output:

AI Agent Watch

1.  CrewAI gaining traction with new multi‑agent orchestration framework
2.  Open‑source agent debugging tool released
3.  Autonomous coding agent trending on GitHub

------------------------------------------------------------------------

# 2. Model Routing Layer

Goal:

Use different LLM models depending on task complexity.

Model Tiers

Tier 1 --- Extraction

Used for: - keyword extraction - metadata parsing - translation - topic
classification

Tier 2 --- Structured Reasoning

Used for: - summaries - "why it matters" - signal normalization -
relevance mapping

Tier 3 --- Strategic Intelligence

Used for: - strategic synthesis - deep insights - weekly radar reports

Routing Flow

Signal arrives ↓ Tier 1 → metadata extraction ↓ Tier 2 → structured
insight ↓ If signal importance high ↓ Tier 3 → deep reasoning

------------------------------------------------------------------------

# 3. Knowledge Distillation Layer

Goal:

Transform repeated insights into reusable reasoning patterns.

Distillation Flow

Signal ↓ Insight ↓ Pattern Extraction ↓ Skill Creation ↓ Skill Library

Example Skill

Skill: Evaluate Agent Framework

Questions:

-   Is this a real framework or a wrapper?
-   Does it enable reusable infrastructure?
-   Is there ecosystem adoption?

Storage

knowledge/skills/

Example files:

-   agent_framework_evaluation.md
-   infra_trend_analysis.md
-   open_source_momentum.md

------------------------------------------------------------------------

# 4. Friction Signals

Goal:

Capture negative signals, frustrations, and pain points.

These signals reveal innovation opportunities.

Signal Schema Extension

signal_type:

-   discovery
-   insight
-   friction

Example

title: "Most AI agent frameworks are just wrappers" signal_type:
"friction" source: "HN discussion" topic: "ai_agents"

Radar Section

Friction Radar

Example

Top Frictions This Week

1.  AI agent frameworks lack observability
2.  AI coding agents struggle with large repositories
3.  Many AI demos fail outside controlled environments

------------------------------------------------------------------------

# 5. Trajectory Memory

Goal:

Enable long‑term signal tracking to reveal trends across time.

Principle:

Insights often appear when looking back across time.

Minimal Implementation

signal_id topic timestamp importance_score

Example Evolution

Topic: AI Agents

January → agent hype February → agent frameworks March → agent
orchestration April → agent infrastructure

This creates trajectory insights.

------------------------------------------------------------------------

# 6. AI Radar Evolution Path

Current System

Signal Discovery ↓ Insight Generation

Future System

Signal Discovery ↓ Insight Generation ↓ Model Routing ↓ Knowledge
Distillation ↓ Trajectory Memory ↓ Reusable Intelligence

AI Radar evolves from a signal system into an intelligence system.

------------------------------------------------------------------------

# Implementation Priority

Phase 1 (Immediate)

-   AI Agent Watch

Phase 2 (Optimization)

-   Model Routing Layer

Phase 3 (Future Intelligence)

-   Knowledge Distillation
-   Friction Signals
-   Trajectory Memory
