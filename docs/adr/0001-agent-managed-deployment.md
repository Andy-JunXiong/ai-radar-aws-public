---
adr: 0001
title: Agent-Managed Deployment Architecture
status: Proposed
created: 2026-04-30
layer: L1-engineering-solution
tags: [aws, ecs-fargate, ci-cd, oidc, agent-ops, security-boundary]
---

# ADR-0001: Agent-Managed Deployment Architecture

## Context

AI Radar uses a static Next.js frontend, a FastAPI backend on ECS Fargate, a
scheduled ingestion task, and S3-backed data exchange. A manual release process
made deployments expensive, weakly traceable, and difficult to reuse across
projects.

Faster AI-assisted development also moved the bottleneck from code generation
to deployment and operations. Giving an agent production credentials would
reduce friction but create an unacceptable blast radius. This ADR defines a
deployment model in which an agent can execute routine work without receiving
unbounded production authority.

## Decision

Use four controls together:

1. GitHub Actions obtains short-lived AWS credentials through OIDC.
2. Production changes follow the enforced `git push -> CI` path.
3. Local agents use a narrowly scoped read-only operations role.
4. Monitoring and budget alerts return operational failures to a human-visible
   channel.

The governing principle is: humans define the boundary, agents execute within
it, and infrastructure permissions enforce it.

## Architecture

```text
Human instruction
      |
Local coding agent
      |
Git push
      |
GitHub Actions -- tests, build, OIDC, deploy
      |
AWS runtime -- ECS, S3, CloudFront, EventBridge
      |
CloudWatch alarms
      |
Human-visible notification and read-only diagnosis
```

## Guardrails

### Short-lived deployment credentials

GitHub Actions exchanges its OIDC identity for temporary AWS credentials. No
long-lived AWS access key is stored in repository secrets.

### No direct agent write access to AWS

The local coding agent can influence production only through reviewed source
changes and CI. It must not call AWS write APIs directly.

### Read-only operational visibility

The local operations role may read the bounded CloudWatch, ECS, and project
data surfaces required for diagnosis. It must not read Secrets Manager, decrypt
protected values, or mutate cloud resources.

### Secret isolation

Runtime secrets are injected by the task execution role. They are unavailable
to the local coding role and must never be copied into source, logs, or chat.

### Cost containment

Account-level budget alerts and service scaling limits provide a final control
against runaway infrastructure cost.

## Deployment paths

### Backend API

Changes under `backend/**` should build a traceable image, publish both a commit
SHA tag and a moving release tag, register a task revision, update the ECS
service, wait for stability, and run a smoke test.

### Frontend

Changes under `frontend/**` should build the static application, sync generated
assets, and invalidate CloudFront. HTML and JSON should avoid stale caching;
content-addressed assets may use long immutable caching.

### Scheduled ingestion

Changes under `app/**` or the ingestion container entry point should build a
traceable image and update the EventBridge schedule target to the new task
definition revision. A scheduled task is not a long-running ECS service, so its
deployment path is intentionally different from the backend path.

Public workflow files are excluded from this repository and require a separate
security review before publication.

## IAM boundaries

The CI deployment role is limited to the specific image repositories, task
definitions, services, frontend bucket, distribution, and schedule used by the
project. `iam:PassRole` is limited to the task roles required by those runtime
definitions.

The local read-only role is limited to describing ECS state, reading selected
logs, and reading the designated project data bucket. It explicitly excludes
Secrets Manager, KMS decryption, and all write actions.

## Observability loop

Monitor at least:

- backend 5xx rate
- sustained CPU or memory pressure
- ingestion task failure
- health-check failure
- budget thresholds

An alert should reach a human-visible channel. Diagnosis may then use the
read-only role, followed by a tested source change and the ordinary CI path.

## Consequences

Benefits:

- deployments are attributable to a Git commit
- local agents can diagnose without holding production write credentials
- the same security model can be reused across small projects
- operational feedback can return to the code workflow quickly

Costs and risks:

- OIDC and least-privilege IAM require deliberate initial setup
- image lifecycle policies and budget alarms require maintenance
- scheduled-task deployment differs from service deployment
- workflow changes remain security-sensitive and need human review

## Alternatives considered

### Give the agent production credentials

Rejected because credential exposure or a mistaken command would have a large
and poorly bounded impact.

### Replace ECS with a different runtime

Rejected for this decision because the existing ECS architecture is serviceable
and a runtime migration would mix deployment safety with platform redesign.

### Keep manual deployment

Rejected because it is difficult to trace, slow to repeat, and unsuitable for
multiple projects.

### Use AWS CodePipeline

Deferred. GitHub Actions aligns with the current source workflow and has mature
OIDC support. CodePipeline may be reconsidered for a multi-account environment.

## Implementation sequence

1. Configure OIDC and the bounded CI and read-only roles.
2. Implement the backend pipeline and smoke test.
3. Add alarms and the notification loop.
4. Implement the frontend pipeline.
5. Implement the scheduled-ingestion pipeline.
6. Document agent and operator boundaries.
7. Add image lifecycle and budget controls.

## References

- [GitHub Actions: Configuring OpenID Connect in Amazon Web Services](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/configuring-openid-connect-in-amazon-web-services)

## Revision history

| Date | Change | Author |
|---|---|---|
| 2026-04-30 | Initial draft | Andy |
| 2026-07-21 | English public edition | Andy |
