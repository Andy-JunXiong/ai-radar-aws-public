# AI Radar — Portfolio Case Study

## Executive Summary

AI Radar is a live AI-native intelligence system designed to turn fast-moving ecosystem signals into structured, project-relevant judgment.

The project began with a practical failure mode: collecting more AI news did not reliably improve decisions. Signals arrived from official announcements, repositories, community discussions, product launches, and manually supplied material, but three distinctions were repeatedly lost:

- observation versus interpretation;
- relevance versus evidential support;
- generated recommendation versus authorised action.

I designed AI Radar around those distinctions. The system collects and normalises signals, generates structured interpretations, synthesises movement across time, maps intelligence to active projects, and applies verification and admission rules before downstream review or action paths become eligible.

## The Problem

A conventional feed has four limitations:

1. individual items do not automatically become a coherent trend;
2. project relevance is often mistaken for factual support;
3. fluent model output can look more certain than its evidence justifies;
4. once recommendations enter a project plan, provenance and authorisation are easily lost.

The product requirement became:

> Build a system that can surface weak signals early without allowing weak evidence to silently become strong action.

## Design Constraints

### Preserve weak signals without overclaiming them

Weak signals are useful because they are early. Discarding them makes the product less useful; promoting them directly into actions makes it unsafe. The system therefore keeps relevance, support, uncertainty, and downstream eligibility separate.

### Keep strategic decisions human-controlled

Automated components can classify evidence, extract claims, identify possible project relevance, and prepare review candidates. They cannot silently change a project roadmap or create a low-risk action merely because generated language sounds convincing.

### Distinguish private cognition from external evidence

Reflections and project notes can improve context, but they are not independent evidence for claims about the external world.

### Govern multi-provider model execution

Model selection, execution policy, provenance, output validation, and prompt contracts remain explicit rather than being embedded independently in every feature.

### Publish safely

The production system contains personal context, runtime artifacts, uploads, project records, and deployment operations. The public repository is therefore a sanitised source snapshot rather than a mirrored production repository.

## System Design

```text
Signal -> Insight -> Trend -> Strategic Intelligence -> Decision -> Review -> Learning
```

### Signal layer

Collectors and manual intake paths preserve source identity, timestamps, metadata, and normalised fields.

### Interpretation and synthesis

Signals become structured interpretations explaining why a development matters, what claims are being made, and which projects may be affected. Radar summaries aggregate movement across time.

### Verification

The system separates source traceability, evidence sufficiency, claim extraction, claim-evidence matching, support status, and downstream eligibility. It is evidence-bounded verification, not automatic truth proof.

### Project judgment

Project Takeaways are reviewable objects rather than final instructions. They support Confirm, Reject, Dismiss, Watch, and Action outcomes while preserving source category, verification metadata, blocked actions, and override provenance.

### Learning

ReviewRecords, CalibrationEvents, trajectory events, watch observations, and action completion metadata create an early learning loop. Rejected history can provide bounded caution context, but cannot become factual evidence.

## Core Engineering Decisions

### External intelligence requires an admission gate

External or model-generated content cannot enter governed downstream state solely because it has a plausible structure. The admission path validates source category, verification context, and blocked-action requirements before a candidate can be written.

See [ADR-0010](../adr/0010-external-insight-admission-gate.md).

### Model provenance is part of the product contract

Generated artifacts retain enough provenance to distinguish model-produced interpretation from observed source content and support later evaluation or debugging.

See [ADR-0009](../adr/0009-model-provenance-schema.md).

### AI Discussion has a separate trust boundary

Open-ended investigation may use current external information, but it has no direct write or promotion path into verified evidence or downstream actions.

See [ADR-0013](../adr/0013-ai-discussion-governed-claim-boundary.md).

### Per-claim support does not prove the combined conclusion

A set of individually supportable claims may still fail to justify the overall narrative. Claim-set composition is therefore treated as a separate judgment problem.

See [ADR-0015](../adr/0015-claim-set-composition-underdetermination-gate.md).

## Technical Implementation

### Backend

The FastAPI backend is organised into route and service layers. Startup includes configuration diagnostics, optional background cache preloading, CORS controls, and health endpoints.

- [`../../backend/app/main.py`](../../backend/app/main.py)
- [`../../backend/app/routes/`](../../backend/app/routes/)
- [`../../backend/app/services/`](../../backend/app/services/)

### Frontend

The Next.js frontend exposes signals, radar summaries, workspace context, project takeaways, manual intelligence, agent and friction views, reflections, review surfaces, and development intake.

- [`../../frontend/app/`](../../frontend/app/)

### Ingestion and collection

Daily orchestration and source collectors are separated from backend request handling. Collectors are not allowed to become independent LLM execution paths.

- [`../../app/main_summary_v2.py`](../../app/main_summary_v2.py)
- [`../../signal_collectors/`](../../signal_collectors/)

### Model execution and prompt contracts

Model routing and execution policy are centralised. Prompt-defined capabilities are registered as explicit product skills rather than scattered as opaque strings.

- [`../../backend/app/prompts/registry.py`](../../backend/app/prompts/registry.py)

## My Role and AI-Assisted Development

I own the product problem, system boundaries, architecture, acceptance criteria, and final judgment about what is allowed to enter governed state.

AI coding assistants accelerate implementation, testing, refactoring, and documentation. They do not own the trust model. Changes are constrained by repository-level operating rules, narrow scope, targeted validation, and explicit restrictions against weakening verification gates or silently modifying deployment behaviour.

This portfolio demonstrates the ability to design and govern an AI-assisted engineering system, not a claim that every line was typed manually.

## Outcome

The project has moved beyond a prototype into a live, multi-surface product with:

- production frontend and API endpoints;
- multi-source collection and manual intelligence intake;
- structured insight and radar generation;
- project relevance mapping;
- review, watch, action, and learning foundations;
- evidence and verification boundaries;
- model routing and prompt contract foundations;
- public source code, tests, ADRs, governance, and evaluation documentation.

The central outcome is architectural: the system preserves a hard distinction between **interesting**, **supported**, **reviewed**, and **authorised**.

## Trade-offs and Limitations

### File-backed state before platform-scale infrastructure

S3 and JSON-backed artifacts keep the architecture inspectable and suitable for a single-operator product, but this is not yet a general multi-tenant data platform.

### Public snapshot versus turnkey demo

The repository excludes private runtime data, production deployment material, and private binary fixtures. It is strong for source and architecture review but not yet a one-command deterministic demo.

### Evaluation scaffolds versus mature benchmark

Evaluation designs and held-out-case foundations exist, but an empty or lightly reviewed case set must not be represented as a production benchmark.

### Human review is deliberate

The closer a judgment is to strategic value or project action, the less appropriate fully automatic promotion becomes.

## Next Improvements

1. Add a fixture-backed public demo mode.
2. Add public non-deployment CI for tests, lint, and builds.
3. Split Python dependencies by runtime boundary.
4. Add a short sanitised product walkthrough.
5. Build public history through focused issues and pull requests rather than importing private Git history.
