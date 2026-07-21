# AI Radar — Portfolio Architecture

## Purpose

This document gives recruiters and technical reviewers a compact view of AI Radar's implemented system shape and trust boundaries.

## System Context

```mermaid
flowchart LR
    Operator[Human operator]
    Sources[External ecosystem sources]
    Uploads[Manual source uploads]
    Radar[AI Radar]
    Projects[Active project context]
    Providers[LLM providers]
    AWS[AWS runtime and storage]

    Sources --> Radar
    Uploads --> Radar
    Projects <--> Radar
    Radar <--> Providers
    Radar <--> AWS
    Radar --> Operator
    Operator --> Radar
```

AI Radar sits between information overload and human judgment. It owns collection, interpretation, synthesis, verification metadata, project relevance, and review preparation. The operator retains strategic confirmation and action commitment.

## Runtime Components

```mermaid
flowchart TB
    subgraph Collection
        Collectors[Source collectors]
        Manual[Manual intelligence intake]
        Orchestrator[Daily ingestion and summary orchestration]
    end

    subgraph Backend
        FastAPI[FastAPI application]
        Routes[Route layer]
        Services[Domain and orchestration services]
        ModelRouter[Model router and execution policy]
        PromptRegistry[Prompt and skill registry]
        Verification[Verification and admission services]
    end

    subgraph Frontend
        Next[Next.js application]
        Surfaces[Signals, Radar, Workspace, Review and Learning]
    end

    subgraph Storage
        S3[(S3 artifacts)]
        JSON[(JSON-backed state)]
    end

    subgraph External
        LLM[Provider-routed LLM APIs]
        SourceAPIs[Source APIs and feeds]
    end

    SourceAPIs --> Collectors
    Collectors --> Orchestrator
    Manual --> Services
    Orchestrator --> S3
    Orchestrator --> JSON
    FastAPI --> Routes --> Services
    Services --> Verification
    Services --> ModelRouter --> LLM
    PromptRegistry --> ModelRouter
    Services <--> S3
    Services <--> JSON
    Next --> Surfaces
    Surfaces <--> FastAPI
```

## Deployment Shape

```mermaid
flowchart LR
    Browser[Browser]
    CDN[S3 + CloudFront frontend]
    ECS[FastAPI backend on ECS]
    Store[(S3 runtime artifacts)]
    Providers[External model providers]
    Sources[External source systems]

    Browser --> CDN
    CDN --> ECS
    ECS <--> Store
    ECS <--> Providers
    Sources --> Store
```

The public repository intentionally excludes private deployment workflows and operations material. This diagram describes the published runtime shape, not a public deployment template.

## Trust Boundaries

### 1. Source content versus generated interpretation

Observed source material and model-generated interpretation are different artifact types. Generated summaries cannot silently become primary evidence.

### 2. Relevance versus support

A signal can be highly relevant to a project while remaining unsupported as evidence for a factual claim. Project matching does not grant verified status.

### 3. Verification versus action eligibility

Verification metadata contributes to downstream eligibility, but final action remains separate. `blocked_downstream_actions` prevent unsupported or thin-evidence paths from automatically producing Project Takeaways or low-risk Actions.

### 4. Reflection versus external evidence

Reflection can provide cognitive and historical context. It cannot support an external factual claim without an explicit conversion and review path.

### 5. Open-ended discussion versus governed state

AI Discussion may use external search for investigation, but it has no direct write or promotion path into verified evidence, verification state, or downstream action.

### 6. Public source versus private operations

The public repository includes source code and selected documentation. It excludes runtime data, personal context, uploads, deployment operations, private fixtures, and private Git history.

## Core Admission Invariant

```text
A downstream judgment object must carry sufficient verification context,
or be explicitly categorised as unverified, manual, review-only, or override,
with corresponding blocked actions and audit metadata.
```

This prevents missing metadata from being interpreted as clean verification.

## Model Execution Boundary

```mermaid
flowchart LR
    Feature[Feature request]
    Policy[Execution policy]
    Router[Model router]
    Contract[Prompt contract]
    Provider[Selected provider]
    Validation[Output validation]
    Persistence[Governed persistence path]

    Feature --> Policy --> Router
    Contract --> Router
    Router --> Provider --> Validation --> Persistence
```

The prompt registry is the source of truth for managed prompt capabilities. Provider choice and execution rules are controlled separately from feature semantics.

## Review and Learning Model

```mermaid
stateDiagram-v2
    [*] --> Candidate
    Candidate --> Confirmed: Confirm
    Candidate --> Rejected: Reject
    Candidate --> Dismissed: Dismiss
    Candidate --> Watching: Watch
    Candidate --> ActionOpen: Action
    Watching --> Watching: Follow-up observation
    Watching --> Candidate: Re-review
    ActionOpen --> ActionCompleted: Complete with outcome
    Confirmed --> ReviewRecord
    Rejected --> ReviewRecord
    Dismissed --> ReviewRecord
    Watching --> ReviewRecord
    ActionCompleted --> ReviewRecord
    ReviewRecord --> CalibrationEvent
    CalibrationEvent --> Trajectory
```

Rejected and dismissed outcomes may shape bounded caution context, but do not become evidence for later claims.

## Code Map

| Concern | Primary location |
|---|---|
| Backend composition | [`../../backend/app/main.py`](../../backend/app/main.py) |
| Routes | [`../../backend/app/routes/`](../../backend/app/routes/) |
| Services and policies | [`../../backend/app/services/`](../../backend/app/services/) |
| Prompt registry | [`../../backend/app/prompts/registry.py`](../../backend/app/prompts/registry.py) |
| Frontend | [`../../frontend/app/`](../../frontend/app/) |
| Daily orchestration | [`../../app/main_summary_v2.py`](../../app/main_summary_v2.py) |
| Collectors | [`../../signal_collectors/`](../../signal_collectors/) |
| Architecture decisions | [`../adr/`](../adr/) |
| Governance | [`../governance/`](../governance/) |
| Evaluation | [`../evaluation/`](../evaluation/) |

## Architectural Trade-offs

### Why not automatically promote high-scoring signals?

Importance and project relevance do not prove factual support. Automatic promotion would optimise throughput at the cost of epistemic integrity.

### Why retain human review?

Strategic value depends on context, opportunity cost, timing, and project commitment. Those judgments are not reducible to source verification alone.

### Why use a public snapshot rather than mirror the private repository?

The production repository contains sensitive runtime and operational material. A sanitised snapshot preserves inspectable engineering evidence without exposing private state or copying historical secrets.

### Why use explicit prompt contracts?

LLM behaviour is part of the product. Managed capabilities make ownership, expected output, evaluation, and model routing easier to reason about than scattered inline prompts.

## Related Documents

- [Portfolio case study](CASE_STUDY.md)
- [Product specification](../../AI_RADAR_PRODUCT_SPEC.md)
- [Roadmap](../../ROADMAP.md)
- [ADR index](../adr/README.md)
- [Public release notes](../../PUBLIC_RELEASE_NOTES.md)
