# AI Radar Model Provider Policy

Last updated: 2026-04-13

## Purpose

This document explains how AI Radar currently chooses models and providers.

Use it when you need to answer:

1. Which provider should this task use by default?
2. Which model env vars matter?
3. Why did a task route to Claude, OpenAI, or Gemini?

This is the practical policy layer.
Use [`model_routing_architecture.md`](./model_routing_architecture.md) for the broader architectural rationale.

---

## Core Principle

AI Radar does not treat every LLM task as interchangeable.

The current policy is task-shaped:

- reasoning-heavy tasks prefer quality
- light structured tasks prefer speed and reliability
- image generation remains separate

So the router is not “randomly multi-model.”
It is a centralized task policy system.

---

## Current Default Policy

### Claude-first tasks

These default to Anthropic / Claude:

- manual text analysis
- manual image analysis
- workspace chat paths that use Claude
- reflection polish
- insight tasks
- reason tasks
- summary tasks
- strategy tasks

Why:

- stronger reasoning
- better long-context behavior
- stronger image understanding

### OpenAI-friendly tasks

These remain suitable for OpenAI defaults:

- extract
- classify
- normalize
- structure
- translation-style lightweight transforms

Why:

- usually cheaper or simpler
- better fit for high-volume structured operations

### Gemini-specific tasks

These stay outside the text router:

- image generation

Why:

- this is a separate capability path, not a normal text reasoning route

---

## Current Env Vars

### Required provider keys

- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `PERPLEXITY_API_KEY`
- `GEMINI_API_KEY`

### Provider model defaults

- `OPENAI_MODEL`
- `ANTHROPIC_MODEL`
- `PERPLEXITY_MODEL`
- `GEMINI_IMAGE_MODEL`

Optional legacy compatibility:

- `CLAUDE_MODEL`

Preferred rule:

- use `ANTHROPIC_MODEL`
- keep `CLAUDE_MODEL` only as compatibility fallback

### Tier overrides

- `MODEL_ROUTER_TIER1_PROVIDER`
- `MODEL_ROUTER_TIER2_PROVIDER`
- `MODEL_ROUTER_TIER3_PROVIDER`
- `MODEL_ROUTER_TIER1_MODEL`
- `MODEL_ROUTER_TIER2_MODEL`
- `MODEL_ROUTER_TIER3_MODEL`

These are override tools, not the main policy surface.

---

## Recommended Defaults

These are the current practical defaults we should optimize for.

### OpenAI

Recommended:

- `OPENAI_MODEL=gpt-5.5`

Use for:

- OpenAI-backed structured tasks when the route resolves to OpenAI
- local operator-managed model upgrades
- comparison against Anthropic-backed routes during evaluation

Important:

- Model IDs are operator-managed configuration, not a user-facing runtime
  choice.
- If route-specific `MODEL_ROUTER_*_MODEL` variables are set, they take
  precedence over `OPENAI_MODEL`.

### Anthropic

Recommended:

- `ANTHROPIC_MODEL=claude-sonnet-4-6`

Use for:

- manual analysis
- signal reasoning
- insight / summary / strategy tasks

Important:

- do not assume `claude-3-5-sonnet-latest` is available on every account
- validate the actual model list for the current Anthropic account

### Perplexity

Recommended:

- `PERPLEXITY_MODEL=sonar-pro`

Use for:

- web-grounded or search-style tasks where applicable

### Gemini

Recommended:

- `GEMINI_IMAGE_MODEL=gemini-3.1-flash-image-preview`

Use for:

- image generation only

---

## Runtime Behavior

At backend startup, AI Radar prints a model router defaults snapshot.

Use that to confirm:

- which provider is assigned to each task family
- which model name is currently active

During execution, routed tasks also emit lightweight routing logs.

You should see values like:

- `task=...`
- `tier=...`
- `provider=...`
- `model=...`
- `mode=...`

Telemetry summaries also accumulate locally:

- `backend/data/output/model_router_usage_summary.json`
- `output/model_router_usage_summary.json`

---

## Failure Patterns To Remember

### Anthropic key works but Claude model fails

This usually means:

- the API key is valid
- but `ANTHROPIC_MODEL` is not valid for that account

Fix:

- choose a model name from the actual available-model list for that account

### Manual analysis succeeds after fallback

This usually means:

- Claude-first route was attempted
- model availability or provider error triggered fallback
- OpenAI completed the task

That is acceptable behavior.

### Frontend shows a provider error but upload succeeded

This usually means:

- transport path is fine
- provider/model config is wrong
- not that the upload path itself is broken

---

## Practical Rule Of Thumb

If the task is:

- image understanding
- reasoning
- signal interpretation
- strategic synthesis

Start with Claude.

If the task is:

- extraction
- structure
- normalization
- light classification

Start with OpenAI.

If the task is:

- image generation

Use Gemini.

This is the current best-fit policy for AI Radar.
