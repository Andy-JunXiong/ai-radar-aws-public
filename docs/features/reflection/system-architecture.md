# Reflection System Architecture (v2.0)

> 这份文档定义整个 reflection 系统的分工:深度 reflection 走 GitHub 手工整理,
> 高频 reflection 留在 AI Radar 自动处理。两者通过 matching 连接。
>
> **本文档替代之前的 `01-reflection-mvp.md` / `02-reflection-integration.md`,
> 它们归档到 `docs/archive/reflection-history/` 作为思考过程的证据。**

---

## Part A — 核心判断

### A.1 Reflection 的两种节奏

经过对真实认知节奏的诚实评估,我们认识到:**reflection 不是一种东西,是两种**。

| 维度 | 高频浅层 reflection | 低频深层 reflection |
|------|---------------------|---------------------|
| **发生频率** | 每天多次 | 每 3 天左右一次 |
| **触发场景** | AI signal / Agent Watch / 日常信息流 | 深度对话 / 思想转折点 / 框架重建 |
| **信息密度** | 低(快速标注、打分、过滤) | 高(需要消化、压缩、结构化) |
| **自动化容忍度** | 高(低质量可以直接拒绝) | 零(必须手工,是二次学习) |
| **价值判断** | 可以用 score 机制 | 只有自己知道什么值得留十年 |
| **载体** | AI Radar 内部 | GitHub private repo + markdown |
| **数量规模** | 每年数千条 | 每年 100 条左右 |
| **生命周期** | 可过期、可清理 | 终身保留 |

### A.2 为什么必须分开

强行用一套系统处理两种 reflection,会导致:
- **用高频系统处理深层**:自动抽取会抹平冲突、丢失所有权、失去二次学习机会
- **用深层标准处理高频**:每条 AI signal 都手工整理不可持续,最终什么都不整理

**分开处理,各司其职,两者才能都做好。**

### A.3 费曼学习法类比

深度 reflection 的手工整理**不是工作,是学习动作**:

```
输入:原始对话(如 160 分钟的 Claude 对话)
消化:手工压缩成结构化 markdown
输出:500–800 字的 reflection
验证:如果整理不出来,说明没真正理解
```

**手工整理过程中的发现,是自动化永远给不了的礼物**。
例如:在整理过程中发明了 `corrections` / `retained_judgements` 字段,
这是自动抽取不会主动创造的 schema。

---

## Part B — 系统架构

### B.1 整体数据流

```
┌─────────────────────────────────────┐
│   内部世界(你自己)                  │
│   深度对话/思考/阅读                  │
└────────────┬────────────────────────┘
             │ 手工整理(30–60 分钟)
             ▼
┌─────────────────────────────────────┐
│   GitHub Private Repo                │ ← Source of Truth
│   reflections/                       │
│   ├─ 2026-04-12-ai-radar-eval.md    │
│   ├─ 2026-04-15-agent-memory.md     │
│   └─ frontmatter + content           │
└────────────┬────────────────────────┘
             │ 每日定时 pull(增量)
             ▼
┌─────────────────────────────────────┐
│   AI Radar                           │
│                                      │
│   ┌──────────────────────────────┐   │
│   │  Reflection Index(只读)       │   │ ← 只存 metadata + link
│   │  reflections/index.json       │   │
│   └──────────┬──────────────────┘    │
│              │ 被查询                  │
│              ▼                        │
│   ┌──────────────────────────────┐   │
│   │  Signal Pipeline              │   │
│   │  Agent Watch                  │   │ ← 高频 signal 处理
│   │  Insight Engine               │   │
│   └──────────┬──────────────────┘    │
│              │                        │
│              │ Matching               │
│              ▼                        │
│   ┌──────────────────────────────┐   │
│   │  Reflection 独立页面          │   │ ← 新 UI
│   │  Daily Radar with cross-refs  │   │
│   └──────────────────────────────┘   │
└─────────────────────────────────────┘

         数据流永远是:
         GitHub → AI Radar
         不反向
```

### B.2 三条不可破的设计原则

**原则 1:GitHub 是 Source of Truth**
- 所有深度 reflection 的原始数据在 GitHub
- AI Radar 只是 GitHub 的索引和查询层
- AI Radar 崩溃不影响任何 reflection 数据
- 换掉 AI Radar 不丢任何 reflection

**原则 2:AI Radar 只读**
- AI Radar 永远不写入 GitHub
- AI Radar 永远不修改 reflection 内容
- 所有修改都在 GitHub 上(用你习惯的编辑器)
- AI Radar 下一次 pull 时自动感知变更

**原则 3:数据格式永远是 markdown**
- 不用 proprietary format
- 不用数据库只读
- Markdown + YAML frontmatter 是 30 年后还能打开的格式
- 这是"认知轨迹可伴随一生"的底层保障

---

## Part C — GitHub Repo 规范

### C.1 Repo 结构

```
reflections/                           # 你的私有 repo
├── README.md                          # 说明 + 索引(可选)
├── 2026/                              # 按年份分目录(方便浏览)
│   ├── 04/
│   │   ├── 2026-04-12-ai-radar-eval.md
│   │   ├── 2026-04-15-agent-memory.md
│   │   └── 2026-04-20-business-model-thinking.md
│   └── 05/
│       └── ...
├── archives/                          # 归档的旧对话原文(可选)
│   └── 2026-04-12-claude-chat.html
└── .github/
    └── workflows/                     # 可选:validate frontmatter 的 CI
        └── validate.yml
```

**命名规范**: `YYYY-MM-DD-<kebab-slug>.md`
- 日期基于 reflection 产生时间,不是整理时间
- slug 3–6 个单词,描述核心主题,用 hyphen 连接

### C.2 Frontmatter Schema

每个 markdown 文件**必须**有以下 frontmatter:

```yaml
---
id: refl_2026-04-12_ai-radar-evaluation
timestamp: 2026-04-12T19:30:00+10:00
source: claude_chat              # claude_chat | obsidian | manual | book | podcast
title: AI Radar 定位与商业模式深度拆解
tags:                            # 自由填写,不强制枚举
  - ai-radar
  - business-model
  - cognitive-tools
  - reflection-design

# 以下字段选填,但推荐
duration_minutes: 160
depth: deep                      # deep | medium | shallow
self_correction_count: 3
related:                         # 关联到其他 reflection
  - refl_2026-04-08_agent-memory

# 可选:link 到原始对话/笔记归档
raw_archive: archives/2026-04-12-claude-chat.html
---
```

**必填字段说明**:

| 字段 | 作用 |
|------|------|
| `id` | 全局唯一,格式 `refl_YYYY-MM-DD_<slug>` |
| `timestamp` | reflection 产生时间(ISO 8601,带时区) |
| `source` | 来源类型,用于未来分类统计 |
| `title` | 一句话概括,用于列表展示 |
| `tags` | 自由填写,AI Radar 的 matching 依赖它 |

**为什么 tags 自由填写不强制枚举**:
- 让你形成真实的 tag 使用习惯,不被 predefined 清单扭曲
- AI Radar 在 matching 时做模糊匹配(同义词、子串)
- 3 个月后回看真实 tag 分布,再决定要不要收敛

### C.3 Content 结构

正文部分建议(不强制)包含以下 section:

```markdown
# [Title]

## 🎯 Compressed Core(十年后还想看的)
- 核心判断 1
- 核心判断 2
- 核心判断 3

## 📋 Cognitive Skeleton(认知骨架)
思考的流向,用箭头或阶段表示:

A → B → C → D

或

Stage 1: 扩散
Stage 2: 框架迁移
Stage 3: 反驳与校准
Stage 4: 收敛

## 🔄 Stance Evolution(判断演变)
- 从 X 到 Y,触发:...
- 从 A 到 B,触发:...

## ⚙️ Corrections & Retained(反驳与保留)
### Corrections(被反驳修正的)
- [topic]: 原判断 → 更新判断

### Retained(反驳后保留的)
- [topic]: 判断

## 💡 Key Insights
- Insight 1(attribution: user_origin | ai_prompted | co_created | rebuttal)
- Insight 2

## ❓ Unresolved Questions
- 未解决问题 1
- 未解决问题 2

## 🔭 Meta Observations
- 关于这次思考本身的观察
```

**关键字段的必要性**:

- **Compressed Core**: 未来 Matching 主要基于这个
- **Corrections & Retained**: 这次对话中发明的 schema,保留反驳痕迹
- **Key Insights + attribution**: 保留所有权,避免混淆"谁说的"

其他 section 都是**可选增强**,核心是 Compressed Core + Corrections & Retained。

### C.4 判定标准:什么该写进 GitHub

**应该写进 GitHub 的**:
- 持续 30 分钟以上的深度对话
- 包含明确的判断变化(你改变了看法)
- 产生了可以压缩成 3–5 句核心 insight 的内容
- 你有意愿花 30–60 分钟整理
- 未来可能影响你后续决策的

**不应该写进 GitHub 的**:
- 事实查询("今天天气")
- 任务执行("帮我写代码")
- 纯情绪表达
- 信息摘要(没有你的独立判断)
- 可以被一条 AI Radar signal 替代的

**边界模糊时的原则**:**宁可不写,不要写烂**。
未整理的对话只是"信息",低质量的 reflection 会污染你的认知档案。

---

## Part D — AI Radar 侧的集成定位

详细实现见 [`integration-plan.md`](./integration-plan.md)。
这里只定义边界:

### D.1 AI Radar 侧做什么

- **每天从 GitHub 拉取**新增/更新的 reflection
- **维护一个轻量索引**(metadata + link,不存 content)
- **提供 matching 能力**:高频 signal 匹配到相关 reflection
- **独立 Reflection 页面**:按时间线/tag 浏览你的深度 reflection
- **Daily Radar 集成**:每个 topic 后面标注"相关深度反思"

### D.2 AI Radar 侧不做什么

- **不做 reflection 抽取**(手工做)
- **不做 reflection 编辑**(GitHub 做)
- **不存储 content**(GitHub 存)
- **不做 taxonomy 强制**(tags 自由填写)
- **不做一致性验证**(手工保证)

### D.3 两种 reflection 在 AI Radar 里的角色

**高频浅层 reflection(AI Radar 内部生成)**:
- 你对某条 signal 的快速标注("重要"/"忽略"/"关注")
- score 低的可以直接拒绝
- 存在 AI Radar 里,生命周期短

**低频深层 reflection(从 GitHub 读取)**:
- 你手工整理后 push 到 GitHub
- AI Radar 定时拉取索引
- 只读引用,终身保留

**两者通过 tag/entity 在 Daily Radar 里遇见**——高频 signal 触发"这和你某条深度 reflection 有关"。

---

## Part E — Phase 0:连通性验证(30 分钟)

在做任何集成工作前,**先验证技术基础**:

### E.1 准备工作

**1. 在 GitHub 生成 Fine-grained Personal Access Token**
- Settings → Developer settings → Personal access tokens → Fine-grained
- Repository access: 只选 `reflections` repo
- Permissions:
  - `Contents: Read-only`
  - `Metadata: Read-only`
- 生成后立即复制 token(只显示一次)

**2. 创建测试 reflection**
在 reflections repo 里 commit 一个测试文件:

```markdown
---
id: refl_2026-04-12_test
timestamp: 2026-04-12T19:30:00+10:00
source: manual
title: 连通性测试
tags: [test]
---

# 测试

这是连通性测试 reflection。
```

### E.2 连通性测试脚本

保存到 AI Radar 项目的 `scripts/test_github_connection.py`:

```python
"""
GitHub Reflection Connectivity Test.
目的:验证 AI Radar 能成功从私有 reflections repo 拉取内容。
用法:python scripts/test_github_connection.py
"""
import os
import sys
import requests
from pathlib import Path

# 从环境变量读 token
GITHUB_TOKEN = os.getenv("GITHUB_REFLECTIONS_PAT")
REPO = os.getenv("GITHUB_REFLECTIONS_REPO")  # 格式: "username/reflections"

if not GITHUB_TOKEN or not REPO:
    print("❌ 缺少环境变量 GITHUB_REFLECTIONS_PAT 或 GITHUB_REFLECTIONS_REPO")
    sys.exit(1)

headers = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

# Test 1: 能访问 repo metadata
print("Test 1: Repo metadata...")
r = requests.get(f"https://api.github.com/repos/{REPO}", headers=headers)
if r.status_code != 200:
    print(f"❌ Failed: {r.status_code} - {r.text}")
    sys.exit(1)
print(f"✓ Repo: {r.json()['full_name']}, Private: {r.json()['private']}")

# Test 2: 能列出文件
print("\nTest 2: List contents...")
r = requests.get(
    f"https://api.github.com/repos/{REPO}/contents/",
    headers=headers,
)
if r.status_code != 200:
    print(f"❌ Failed: {r.status_code} - {r.text}")
    sys.exit(1)
files = [item for item in r.json() if item["type"] == "file"]
dirs = [item for item in r.json() if item["type"] == "dir"]
print(f"✓ Root: {len(files)} files, {len(dirs)} dirs")

# Test 3: 能读取一个 markdown 文件
print("\nTest 3: Read a markdown file...")
# 简单递归找第一个 .md 文件
def find_first_md(path=""):
    r = requests.get(
        f"https://api.github.com/repos/{REPO}/contents/{path}",
        headers=headers,
    )
    if r.status_code != 200:
        return None
    for item in r.json():
        if item["type"] == "file" and item["name"].endswith(".md"):
            return item
        if item["type"] == "dir":
            result = find_first_md(item["path"])
            if result:
                return result
    return None

md_file = find_first_md()
if not md_file:
    print("⚠️  No .md file found. Create a test reflection first.")
else:
    r = requests.get(md_file["download_url"], headers=headers)
    if r.status_code != 200:
        print(f"❌ Download failed: {r.status_code}")
        sys.exit(1)
    print(f"✓ Read {md_file['path']}: {len(r.text)} bytes")
    print(f"  First 200 chars: {r.text[:200]}")

# Test 4: Rate limit 检查
print("\nTest 4: Rate limit status...")
r = requests.get("https://api.github.com/rate_limit", headers=headers)
limit = r.json()["rate"]
print(f"✓ Rate limit: {limit['remaining']}/{limit['limit']}, reset at {limit['reset']}")

print("\n" + "="*50)
print("✅ All tests passed. Ready to build integration.")
print("="*50)
```

### E.3 验证完成标准

- [ ] 能成功访问 repo metadata
- [ ] 能列出 repo 文件
- [ ] 能读取单个 markdown 文件的 raw content
- [ ] Rate limit 显示足够(authenticated 有 5000/hour,完全够用)

**如果 Phase 0 失败,先解决这里,不要继续往下做。**

---

## Part F — 演进路线

### F.1 分阶段目标

**Phase 0(1 天)**: 连通性验证(见 §E)

**Phase 1(1 周)**:基础 ingestion
- 定时 pull GitHub reflections
- 解析 frontmatter,维护索引
- 暴露查询 API

**Phase 2(1 周)**:Reflection 独立页面
- 时间线浏览
- Tag 过滤
- 单条详情(从 GitHub 实时读取 content)

**Phase 3(1–2 周)**:Matching v1(tag-based)
- 每条 signal/topic 后标注相关 reflection
- Daily Radar 集成入口组件

**Phase 4(未定期)**:Matching v2(语义增强)
- 仅在 v1 不够用时启动
- 从 tag-based 升级到 embedding-based

**Phase 5(6 个月+)**:Cross-referencing
- 追踪"这个 reflection 的 insight 在后续 signal 中被验证/反驳几次"
- 只在真的有 50+ reflection 时做

### F.2 停止信号

在任何阶段,如果出现这些情况,**立即停止后续开发**:

- 3 个月后,GitHub repo 里只有 < 5 条 reflection → 使用意愿不足,手工整理习惯没形成
- Phase 2 完成后,你从不打开 Reflection 页面 → UI 设计错了,或者功能不必要
- Matching 结果频繁不准 → 说明 tag 系统或匹配逻辑需要重新设计,不要急着升级

**停止信号不是失败,是数据告诉你该调整方向**。

---

## Part G — 对旧文档的处理

| 旧文档 | 状态 | 处理方式 |
|--------|------|---------|
| `01-reflection-mvp.md` | 部分失效 | 已移到 `docs/archive/reflection-history/`,作为 MVP 阶段思考的证据 |
| `02-reflection-integration.md` | 基本失效 | 已移到 `docs/archive/reflection-history/`,部分 schema 思路已融入本文档 |
| `03-resonance-v1.1.md` | 重新定位 | 已移到 `docs/archive/reflection-history/`,场景从"召回相似 reflection"改为"用 reflection 激活 signal 的解读" |
| `00-reflection-docs-navigation.md` | 历史导航 | 已移到 `docs/archive/reflection-history/`,当前入口改用 `docs/README.md` |

**归档不删除的原因**:它们记录了思考的演化路径。
未来某天你可能想知道"为什么当时放弃了 resonance retrieval"——那些文档是证据。

---

## Part H — 给 Codex 的任务说明(用于 Phase 1)

具体实施的 prompt 见 [`integration-plan.md`](./integration-plan.md) 的 Part H。
本文档只是架构和规范,不给 Codex 直接用。

---

## 最后的判断

这次架构调整的本质是**承认认知的两种节奏,并尊重它们各自的自然形态**:

- 高频浅层的 signal 处理,AI Radar 已经做得很好,继续做
- 低频深层的 reflection 沉淀,手工整理才是正确方式
- 两者不强行合并,但通过 matching 互相激活

**这个架构比之前所有方案都更轻,但也更真实**。它不追求完整性,追求**可持续性**——你能不能 10 年持续用它。

markdown 文件放在 GitHub 上,10 年后依然能打开。
AI Radar 的 matching 换了也不影响你的认知档案。
这才是"赛博记忆永存"的真正技术保障。

---

*v2.0 — 2026-04-13*
*本文档替代之前的 MVP / Integration 设计,基于"深度 reflection 必须手工"的核心判断重构。*
