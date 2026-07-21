# Architecture Decision Records (ADR)

本目录记录 AI Radar 项目的关键架构决策。每个 ADR 是一份不可变的历史文档——
一旦决策被 supersede,创建新 ADR 引用旧的,而不是修改旧的。

## ADR 格式

每份 ADR 包含:
- **ADR Gate**: 新增 ADR 前的三条件检查
- **Context**: 决策背景和触发原因
- **Decision**: 实际采取的决策
- **Owns**: 该 ADR 明确拥有和治理的边界
- **Does Not Own**: 相关但不由该 ADR 决定的边界
- **Consequences**: 正面影响、负面成本、已知风险
- **Alternatives Considered**: 评估过但拒绝的方案及理由
- **Implementation Plan**: 落地步骤
- **References**: 相关资料链接

## 状态说明

- **Proposed**: 已起草,等待落地验证
- **Accepted**: 已实施并验证
- **Deprecated**: 决策仍有效但不再推荐用于新场景
- **Superseded by ADR-XXXX**: 已被新决策取代

## ADR 列表

| ID | 标题 | 状态 | 创建日期 |
|---|---|---|---|
| [0001](./0001-agent-managed-deployment.md) | Agent-Managed Deployment Architecture | Proposed | 2026-04-30 |
| [0002](./0002-hypothesis-monitoring-boundary.md) | Hypothesis Monitoring Boundary | Proposed | 2026-05-15 |
| [0003](./0003-runtime-agnostic-skill-registry.md) | Runtime-Agnostic Skill Registry | Accepted | 2026-05-17 |
| [0004](./0004-agents-constitution-skill-registry.md) | AGENTS.md Constitution and Skill Registry | Proposed | 2026-05-17 |
| [0005](./0005-dual-gate-pre-sprint-protocol.md) | Dual-Gate Pre-Sprint Protocol | Proposed | 2026-05-17 |
| [0006](./0006-operator-guidance-layer.md) | Operator Guidance Layer | Proposed | 2026-05-19 |
| [0007](./0007-incident-attribution-skill.md) | Incident Attribution Agent Skill for Collaboration Failure Learning | Accepted | 2026-05-19 |
| [0008](./0008-signal-lifecycle-event-spine.md) | Signal Lifecycle Event Spine | Proposed | 2026-05-21 |
| [0009](./0009-model-provenance-schema.md) | Model Provenance Schema | Accepted | 2026-05-22 |
| [0010](./0010-external-insight-admission-gate.md) | External Insight Intake Requires Author-Side Admission Gate | Accepted | 2026-05-28 |
| [0011](./0011-evidence-pack-source-excerpt-policy.md) | Evidence Pack Source Excerpt Policy | Accepted | 2026-05-28 |
| [0012](./0012-signal-claim-review-feedback-capture.md) | Signal Claim Review Feedback Capture | Accepted | 2026-06-13 |
| [0013](./0013-ai-discussion-governed-claim-boundary.md) | AI Discussion Governed Claim Boundary | Accepted | 2026-06-24 |
| [0015](./0015-claim-set-composition-underdetermination-gate.md) | Claim-Set Composition Underdetermination Gate | Proposed | 2026-07-05 |
| [0016](./0016-action-loop-stagnation-protocol.md) | Action-Loop Stagnation Protocol | Proposed | 2026-07-05 |

## 如何添加新 ADR

1. 复制 `TEMPLATE.md` 作为模板
2. 编号递增(0002, 0003, ...),不复用已删除的编号
3. 文件名格式: `NNNN-kebab-case-title.md`
4. 先完成 `ADR Gate`; 三项都为 yes 才创建 ADR
5. 在本 README 的列表中追加一行
6. 在文档头部 metadata 中关联 L2/L3/L4 资产路径

现有 ADR 不回溯套用 `ADR Gate`; 该检查只用于新增 ADR。

## 跨层级关联

ADR 属于 L1 工程方案层,
通常会向下衍生 L2 运营手册、向上提炼 L3 对外叙事和 L4 元能力反思。
通过文档头部的 `related` metadata 维护双向链接。
