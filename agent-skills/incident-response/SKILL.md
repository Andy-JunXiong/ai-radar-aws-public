---
name: incident-response
description: |
  Use when Codex receives an alert, failing CI signal, production error, smoke-test failure, Telegram-triggered incident, or other AI Radar operational failure that requires diagnosis, classification, narrow remediation, and escalation discipline.
status: experimental
intended_consumers:
  - codex-cli
  - claude-code
---

# Incident Response

Use this protocol in Incident Response Mode. Keep AGENTS.md hard boundaries,
system-operation boundaries, credential rules, worktree safety, and security
model in force.

## Boundaries

Allowed system-level actions:

- read source code, modify business logic, and write tests
- use `AWS_PROFILE=your-readonly-profile` for CloudWatch logs and ECS service status
- read `s3://your-ai-radar-data-bucket/` for data investigation

Forbidden actions:

- do not run AWS write commands
- do not read AWS Secrets Manager
- do not write to any S3 bucket
- do not modify `.github/workflows/`; read and propose only
- do not skip, delete, or weaken failing tests
- do not commit, push, open PRs, or deploy unless explicitly asked
- do not log, persist, or commit credentials or secret-like strings

If the read-only AWS profile is unavailable or expired, stop the AWS-dependent
task and report that the human must refresh it. Do not ask for pasted
credentials.

## Step 1: Pull Logs

Use the read-only AWS profile:

```bash
export AWS_PROFILE=your-readonly-profile
aws logs tail /ecs/ai-radar-api --since 30m
aws logs tail /ecs/ai-radar-ingestion --since 1d
```

Use local reproduction and source inspection when AWS logs are unavailable or
when the failure is not production-specific.

## Step 2: Classify

Classify the issue before fixing:

| Type | Signal | Action |
|---|---|---|
| A. Code bug | Stack trace points to specific file, reproducible locally | Reproduce, write test, fix narrowly, validate locally, recommend next git step |
| B. External dependency | OpenAI, Anthropic, or third-party API errors | Classify transient vs permanent; improve retry/backoff for transient; improve classification, logging, user-facing message, or config validation for permanent |
| C. Infrastructure | ECS task will not start, ALB health fails, CloudFront 502 | Notify human immediately |

Do not hide permanent dependency errors behind generic retry.

## Step 3: Fix Type A Incidents

Prepare the fix locally. Keep investigation as broad as needed to find root
cause, but keep the code change narrow.

Recommended local flow:

```bash
docker build -f backend/Dockerfile.api -t ai-radar-api-local .
docker run -p 8000:8000 --env-file .env.local ai-radar-api-local
pytest backend/tests/
```

After validating, report:

- files changed
- tests run
- manual verification needed
- recommended git command, if any

Only run git branch/commit/push or deployment commands after explicit user
instruction.

## Step 4: Verify After Deployment

Only after a user-approved deployment path:

```bash
sleep 60
curl -f https://api.ai-radar-lab.com/auth/status
curl -f https://api.ai-radar-lab.com/signals?status=all
aws logs tail /ecs/ai-radar-api --since 5m
```

## Stop Conditions

Stop and escalate if:

- 2 consecutive deployments fail
- smoke tests still fail after deployment
- IAM, Secrets, or AWS account-level issues are suspected
- the stack points to code areas you are unfamiliar with
- the fix would require destructive operations

## Notification Format

When escalating, use:

```text
Codex Status: <NEEDS_ATTENTION | BLOCKED | INFO>
Project: ai-radar
Context: <one-line summary>
What I tried: <chronological attempts>
What I need from you: <specific ask>
Logs: <key log excerpts, max 10 lines>
```

Do not attempt to send Telegram messages or call out-of-band webhooks. The
final response is the notification surface.
