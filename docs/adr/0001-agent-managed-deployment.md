---
adr: 0001
title: Agent-Managed Deployment Architecture
status: Proposed
created: 2026-04-30
layer: L1-engineering-solution
related:
  - L2: ai-radar/docs/ops/deployment-runbook.md
  - L2: ai-radar/AGENTS.md
  - L2-existing: ai-radar/RUNBOOK.md (code-level debugging, separate concern)
  - L3: cognitive-assets/narratives/linkedin/2026-04-vibe-ops-boundary-design.md
  - L4: cognitive-assets/meta-reflections/2026-04-30-pattern-recognition-from-chat.md
tags: [aws, ecs-fargate, ci-cd, oidc, agent-ops, security-boundary]
---

# ADR-0001: Agent-Managed Deployment Architecture

## Context

AI Radar 当前已部署在 AWS 上,采用以下生产架构:

- **Frontend**: Next.js 静态导出 → S3 + CloudFront (`app.ai-radar-lab.com`)
- **Backend API**: FastAPI on ECS Fargate + ALB (`api.ai-radar-lab.com`)
- **Daily Ingestion**: EventBridge Scheduler 触发 ECS Fargate task
- **Storage**: S3 共享数据层
- **Secrets**: AWS Secrets Manager / SSM Parameter Store

但**发布流程仍是手工的**:本地 `docker build` → `docker push` → AWS Console 点击更新 task definition → Force deployment。

这个手工瓶颈带来三个问题:
1. 部署成本高,导致迭代频率被压制
2. 不可追溯——image tag 只有 `latest`,无法关联到具体 commit
3. 无法 scale 到多项目——每个新项目都要重复这套手工流程

更深层的问题是:在 AI 编程工具(Codex / Claude Code)产出代码速度提升一个量级后,
**部署和运维已成为新的瓶颈**。一些资深开发者(参见 source-materials/2026-04-30-hermes-chat)
开始讨论"让 AI agent 自主运维小项目"的模式,但直接照搬有显著风险——
特别是把生产凭证交给 agent 这种做法。

本 ADR 决定如何安全地把 AI Radar 的发布与运维链路改造为 **agent 可自主操作**的形态。

## Decision

采用 **OIDC 联邦凭证 + 最小权限只读 role + CI 强制路径 + 告警闭环**的组合方案。
核心原则:**人定义边界,agent 执行细节,权限做硬隔离**。

### 架构总览

```
Telegram (指令入口)
    ↓
ductor → Codex CLI (本地开发环境)
    ↓ git push
GitHub Repo
    ↓ 触发
GitHub Actions
    ├─ 跑测试
    ├─ docker build
    ├─ OIDC 换 AWS 临时凭证
    ├─ docker push to ECR
    └─ 触发 ECS service update / EventBridge target update
         ↓
    AWS 生产环境 (ECS Fargate / S3+CloudFront)
         ↓
    CloudWatch Logs + Alarms
         ↓ 异常时
    SNS → Lambda → Telegram Bot
         ↓
    Codex 拉日志 (read-only IAM) → 定位 → 改代码 → git push → 闭环
```

### 五道护栏(Guardrails)

1. **OIDC 联邦凭证替代长期 access key**
   GitHub Actions 通过 OIDC 换取 AWS 临时凭证,无任何长期凭证落地

2. **Agent 写权限完全不接触 AWS**
   Codex 只能通过 `git push → CI` 路径影响生产,不能直接调 AWS API 改资源

3. **只读运维权限**
   Codex 拥有 `YourReadOnlyRole` role,只能读 CloudWatch logs / ECS service status / S3 数据桶

4. **Secrets Manager 完全隔离**
   Codex 的 IAM role **绝不**包含 `secretsmanager:GetSecretValue`,
   仅 ECS task execution role 能在容器启动时注入

5. **Budget Alarm 兜底**
   AWS 账户级别月度预算告警,超过阈值立即 Telegram 通知人工

### 三条 Deployment Pipeline

#### Pipeline 1: Backend API (`backend/**` 改动触发)
- 文件: `.github/workflows/deploy-backend.yml`
- 流程: build → push to `ai-radar-api` ECR → register new task definition → update ECS service → wait for stability → smoke test
- Image tag 策略: `${git-sha}` + `latest` 双 tag,保证可追溯

#### Pipeline 2: Frontend (`frontend/**` 改动触发)
- 文件: `.github/workflows/deploy-frontend.yml`
- 流程: `npm run build` → S3 sync → CloudFront invalidation
- **关键细节**: HTML/JSON 设置 `no-cache`,其他静态资源 `max-age=31536000,immutable`
  (Next.js 文件名带 hash 兜底)

#### Pipeline 3: Daily Ingestion (`app/**` 或 root `Dockerfile` 改动触发)
- 文件: `.github/workflows/deploy-ingestion.yml`
- 流程: build → push to `ai-radar-ingestion` ECR → register new task definition →
  **更新 EventBridge schedule target 指向新 task def revision**
- ⚠️ 与 backend 不同——ingestion 是 scheduled task 而非 long-running service,
  必须更新 EventBridge target 而不是 update service

### IAM Role 设计

#### Role A: `AIRadarDeployRole` (GitHub Actions 用)
权限范围:
- `ecr:*` 仅限 `ai-radar-api` 和 `ai-radar-ingestion` 两个 repo
- `ecs:RegisterTaskDefinition` / `UpdateService` / `DescribeServices`
- `iam:PassRole` 仅限 `ecsTaskExecutionRole` 和 `aiRadarTaskRole`
- `s3:PutObject/DeleteObject` 仅限 `ai-radar-frontend-bucket`
- `cloudfront:CreateInvalidation`
- `scheduler:UpdateSchedule` 仅限 `ai-radar-daily-ingestion`

信任策略: 仅信任 `repo:YOUR_GITHUB_USERNAME/ai-radar:*` 通过 OIDC

#### Role B: `YourReadOnlyRole` (本地 Codex 用)
权限范围:
- `logs:*Read*` 仅限 `/ecs/ai-radar-*` log groups
- `ecs:Describe*` / `List*`
- `s3:GetObject/ListBucket` 仅限 `your-ai-radar-data-bucket`
- **明确不包含**: Secrets Manager / KMS decrypt / 任何写权限

凭证获取: 通过 `aws sts assume-role` 获取 1 小时有效期临时凭证

### 可观测性闭环

- **CloudWatch Alarms** 监控:
  - Backend ALB 5xx > 5%
  - Backend CPU/Memory > 80% 持续 5 分钟
  - Ingestion task 失败 (exit code != 0)
  - Health check 失败
- **告警路径**: CloudWatch Alarm → SNS Topic → Lambda → Telegram Bot (Topic 路由匹配 ductor)
- **Codex 故障响应**: 收到告警 → 拉日志 → 本地复现 → 修复 + 测试 → push → CI → 验证

## Consequences

### 正面

- ✅ Agent 可安全自主运维生产服务,人只需介入边界级决策
- ✅ 部署可追溯到 git SHA,任何问题可精确回滚
- ✅ 故障响应闭环时间从小时级降到分钟级
- ✅ 多项目可复用同一套 IAM/CI 模板,边际成本极低
- ✅ 提供了一个可对外讲述的"AI 时代边界设计"工程案例

### 负面 / 成本

- ⚠️ IAM + OIDC 一次性配置投入约 4 小时
- ⚠️ 需要严格遵守"agent 不接触生产凭证"原则,不能图省事开后门
- ⚠️ ECR lifecycle policy 必须配置(否则镜像存储费会偷偷涨)
- ⚠️ EventBridge target 更新逻辑与 ECS service update 不同,新人易踩坑
- ⚠️ 每个新项目仍需复制一遍 workflow 模板(可未来抽成 reusable workflow)

### 风险与缓解

| 风险 | 缓解措施 |
|---|---|
| Agent 误改 workflow 把自己权限放大 | AGENTS.md 明确禁止改 `.github/workflows/`,且 main 分支 protect |
| 镜像被注入恶意代码 | ECR scan on push + 人工 review PR(重要项目开 environment protection) |
| 失控烧钱 | AWS Budget alarm + ECS service max instances 上限 |
| 凭证泄露 | OIDC 替代长期 key + Codex role 不含 secrets 权限 |

## Alternatives Considered

### Alt 1: 直接给 Codex prod ssh key / AWS access key
**拒绝理由**: 风险不可控,失败爆炸半径过大。这正是 Hermes 群里"把 prod ssh key 交给小龙虾"调侃的反例。

### Alt 2: 完全迁移到 App Runner / Lambda Serverless
**拒绝理由**: 现有 ECS Fargate 架构沉没成本和定制度高;App Runner 心智负担虽低但牺牲灵活性;
Lambda 不适合 FastAPI 长连接和大模型调用的延迟特性。

### Alt 3: 维持手工部署
**拒绝理由**: 不能 scale 到多项目,且与"AI 时代工作方式"的探索方向背道而驰。

### Alt 4: 使用 AWS CodePipeline 而非 GitHub Actions
**拒绝理由**: GitHub Actions 与代码托管同源,debugging 体验更好,且 OIDC 集成成熟。
CodePipeline 在多 AWS 账户场景下更优,但 AI Radar 暂不需要。

## Implementation Plan

落地优先级(按 ROI 排序):

1. **Week 1**: 配置 IAM OIDC + Role A + Role B (一次性投入)
2. **Week 1**: Backend deploy workflow (最高频,收益最大)
3. **Week 2**: Telegram 告警 Lambda + CloudWatch Alarms (让闭环跑起来)
4. **Week 2**: Frontend deploy workflow
5. **Week 3**: Ingestion deploy workflow (最复杂,频率低,可延后)
6. **Week 3**: AGENTS.md + agent-runbook.md (让 Codex 知道游戏规则)
7. **Week 4**: ECR lifecycle policy + Budget alarm (收尾护栏)

## References

- Source: `cognitive-assets/source-materials/2026-04-30-hermes-chat-screenshot.png`
- Discussion: `cognitive-assets/source-materials/2026-04-30-ai-radar-vibe-ops-discussion.md`
- AWS OIDC for GitHub Actions: https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/configuring-openid-connect-in-amazon-web-services
- Related ADRs: (none yet — this is the first)

## Revision History

| Date | Change | Author |
|---|---|---|
| 2026-04-30 | Initial draft | Andy |
