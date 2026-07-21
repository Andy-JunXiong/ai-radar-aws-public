# AI Radar --- Model Routing Architecture

## Goal

Introduce a multi‑model routing layer inside AI Radar to optimize: -
cost - speed - reasoning quality

Instead of using a single LLM for every task, AI Radar routes tasks to
different model tiers depending on complexity.

------------------------------------------------------------------------

# Architecture Overview

Signal Flow:

External Signals ↓ Signal Collectors ↓ Signal Processing ↓ Model Routing
Layer ↓ LLM Tasks ↓ Insights / Radar Output

------------------------------------------------------------------------

# Three Model Tiers

## Tier 1 --- Fast Extraction Models

Purpose: High‑volume lightweight tasks.

Examples: - keyword extraction - translation - metadata extraction -
topic classification - title normalization

Characteristics: - cheap - fast - scalable

------------------------------------------------------------------------

## Tier 2 --- Structured Reasoning Models

Purpose: Medium complexity analysis.

Examples: - structured summaries - why‑it‑matters explanation - signal
normalization - topic mapping - project relevance mapping

Characteristics: - moderate cost - good reasoning

------------------------------------------------------------------------

## Tier 3 --- Strategic Intelligence Models

Purpose: High value reasoning tasks.

Examples: - strategic insight synthesis - weekly radar summary -
reflection polishing - cross‑signal reasoning - long‑form intelligence
output

Characteristics: - strongest reasoning - expensive - used selectively

------------------------------------------------------------------------

# Routing Logic

Example pipeline:

Signal arrives ↓ Tier 1 model → extract metadata ↓ Tier 2 model →
generate structured insight ↓ Signal scoring ↓ If score \> threshold ↓
Tier 3 model → strategic reasoning

------------------------------------------------------------------------

# Implementation Layer

Module:

app/intelligence/model_router.py

Current MVP slice now implemented:

- `extract` tasks route to Tier 1 model selection
- `structure` / `insight` tasks route to Tier 2 model selection
- `reason` / `strategy` tasks resolve to Tier 3 model selection
- execution is now provider-aware through:
  - `app/intelligence/llm_executor.py`
  - OpenAI chat completions
  - Anthropic messages API

Current environment overrides:

- `MODEL_ROUTER_TIER1_PROVIDER`
- `MODEL_ROUTER_TIER2_PROVIDER`
- `MODEL_ROUTER_TIER3_PROVIDER`
- `MODEL_ROUTER_TIER1_MODEL`
- `MODEL_ROUTER_TIER2_MODEL`
- `MODEL_ROUTER_TIER3_MODEL`

Pseudo code:

def route_task(task_type):

    if task_type == "extract":
        return TIER1_MODEL

    if task_type == "structure":
        return TIER2_MODEL

    if task_type == "reason":
        return TIER3_MODEL

------------------------------------------------------------------------

# Benefits

-   lower cost
-   faster pipeline
-   strong reasoning where it matters
