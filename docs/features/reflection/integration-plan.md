# Reflection AI Radar Integration (v2.0)

> 这份文档是 AI Radar 侧的具体实施方案。
> 前置:先读 [`system-architecture.md`](./system-architecture.md),理解整体架构和分工。
> 前置:完成架构文档 Part E 的连通性测试。

---

## Part A — 实施总览

本文档覆盖 AI Radar 侧的:
- GitHub reflection ingestion(定时 pull + 增量同步)
- Reflection 索引数据结构
- Matching 机制(高频 signal ↔ 深度 reflection)
- 独立 Reflection 页面的 UI
- Daily Radar 里的入口组件

**总工作量估计:3–4 周**(分 3 个 Phase)
**前置条件**:架构文档 Part E 的连通性测试已通过

---

## Part B — 模块划分

### B.1 新增目录结构

```
ai-radar/
├── app/
│   ├── reflection/                        ← 新增
│   │   ├── __init__.py
│   │   ├── github_client.py               # GitHub API wrapper
│   │   ├── frontmatter_parser.py          # 解析 YAML frontmatter
│   │   ├── index_builder.py               # 构建/更新索引
│   │   ├── matcher.py                     # Signal ↔ Reflection matching
│   │   └── schemas.py                     # Pydantic models
│   │
│   └── ... (现有代码不动)
│
├── backend/
│   ├── app/
│   │   ├── routes/
│   │   │   └── reflection.py              ← 新增 API 路由
│   │   └── services/
│   │       └── reflection_service.py      ← 服务层
│
├── frontend/
│   ├── src/
│   │   └── app/
│   │       └── reflections/               ← 新增独立页面
│   │           ├── page.tsx               # 时间线页面
│   │           ├── [id]/page.tsx          # 详情页
│   │           └── components/
│   │               ├── reflection-list.tsx
│   │               ├── reflection-detail.tsx
│   │               └── tag-filter.tsx
│
├── scripts/
│   ├── test_github_connection.py          # Phase 0 已实现
│   └── sync_reflections.py                # 手动触发同步
│
└── tests/
    └── reflection/
        ├── test_github_client.py
        ├── test_frontmatter_parser.py
        ├── test_index_builder.py
        └── test_matcher.py
```

### B.2 S3 存储(复用现有模式)

```
s3://<ai-radar-bucket>/
├── signals/                    (现有)
├── insights/                   (现有)
├── daily/                      (现有)
└── reflections/                ← 新增
    ├── index.json              ← 主索引(所有 reflection 的 metadata)
    ├── sync_state.json         ← 同步状态(last_sync_at, last_commit_sha)
    └── matches/                ← matching 结果
        └── YYYY/MM/DD/
            └── daily_matches.json
```

**不存 content**(content 在 GitHub),只存:
- Metadata(id / title / tags / timestamp / source 等)
- GitHub URL(用于 UI 点击跳转)
- Matching 结果(缓存查询性能)

---

## Part C — 核心 Schema

### C.1 Pydantic 模型(`app/reflection/schemas.py`)

```python
from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, Literal
from datetime import datetime
from enum import Enum


class ReflectionDepth(str, Enum):
    DEEP = "deep"
    MEDIUM = "medium"
    SHALLOW = "shallow"


class ReflectionSource(str, Enum):
    CLAUDE_CHAT = "claude_chat"
    OBSIDIAN = "obsidian"
    MANUAL = "manual"
    BOOK = "book"
    PODCAST = "podcast"
    OTHER = "other"


class ReflectionMetadata(BaseModel):
    """Reflection 索引条目。只存 metadata,不存 content。"""

    # === 必填字段 ===
    id: str = Field(..., description="refl_YYYY-MM-DD_<slug>")
    title: str = Field(..., max_length=200)
    timestamp: datetime
    source: ReflectionSource
    tags: list[str] = Field(default_factory=list)

    # === GitHub 引用 ===
    github_path: str = Field(..., description="repo 内的相对路径")
    github_url: HttpUrl = Field(..., description="GitHub 上的 markdown 链接")
    github_raw_url: HttpUrl = Field(..., description="raw content 链接")
    last_modified: datetime = Field(..., description="GitHub 上的最后修改时间")
    commit_sha: str = Field(..., description="上次同步时的 commit SHA")

    # === 选填字段 ===
    depth: Optional[ReflectionDepth] = None
    duration_minutes: Optional[int] = None
    self_correction_count: Optional[int] = None
    related: list[str] = Field(default_factory=list, description="关联的其他 reflection id")
    raw_archive: Optional[str] = None

    # === 系统字段 ===
    synced_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))


class ReflectionIndex(BaseModel):
    """主索引文件结构"""
    schema_version: str = "2.0"
    last_updated: datetime
    total_count: int
    reflections: list[ReflectionMetadata]


class SyncState(BaseModel):
    """同步状态,用于增量同步"""
    last_sync_at: datetime
    last_commit_sha: Optional[str] = None
    last_success: bool = True
    last_error: Optional[str] = None
    total_reflections: int = 0


class Match(BaseModel):
    """Signal ↔ Reflection 的匹配结果"""
    signal_id: str
    reflection_id: str
    match_type: Literal["tag_overlap", "entity_overlap", "title_semantic"]
    score: float = Field(..., ge=0.0, le=1.0)
    matched_on: list[str] = Field(..., description="具体匹配的 tag/entity")


class DailyMatches(BaseModel):
    """每日 matching 结果"""
    date: datetime
    total_signals: int
    total_reflections_checked: int
    matches: list[Match]
```

---

## Part D — GitHub Client 实现

### D.1 配置(`.env`)

```bash
# GitHub 集成
GITHUB_REFLECTIONS_PAT=<fine-grained PAT>
GITHUB_REFLECTIONS_REPO=<username>/reflections
GITHUB_REFLECTIONS_BRANCH=main
```

### D.2 Client 核心(`app/reflection/github_client.py`)

```python
"""
GitHub Reflection Client.
封装所有 GitHub API 交互。
使用 fine-grained PAT,只读访问 reflections repo。
"""
import os
import httpx
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel


class GitHubFile(BaseModel):
    path: str
    name: str
    size: int
    sha: str
    download_url: str
    html_url: str
    last_modified: Optional[datetime] = None


class GitHubReflectionClient:
    """GitHub API wrapper for reflections repo."""

    BASE_URL = "https://api.github.com"

    def __init__(self):
        self.token = os.getenv("GITHUB_REFLECTIONS_PAT")
        self.repo = os.getenv("GITHUB_REFLECTIONS_REPO")
        self.branch = os.getenv("GITHUB_REFLECTIONS_BRANCH", "main")

        if not self.token or not self.repo:
            raise ValueError("Missing GitHub config in environment")

        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        self.client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers=self.headers,
            timeout=30.0,
        )

    async def get_latest_commit_sha(self) -> str:
        """获取 main 分支的最新 commit SHA(用于增量同步)"""
        r = await self.client.get(
            f"/repos/{self.repo}/commits/{self.branch}",
            params={"per_page": 1},
        )
        r.raise_for_status()
        return r.json()["sha"]

    async def list_markdown_files(
        self,
        path: str = "",
        since_sha: Optional[str] = None,
    ) -> list[GitHubFile]:
        """
        列出所有 .md 文件。
        如果提供 since_sha,只返回变更的文件(增量同步)。
        """
        if since_sha:
            return await self._list_changed_since(since_sha)
        return await self._list_all(path)

    async def _list_all(self, path: str = "") -> list[GitHubFile]:
        """递归列出所有 .md 文件"""
        files = []
        r = await self.client.get(f"/repos/{self.repo}/contents/{path}")
        r.raise_for_status()

        for item in r.json():
            if item["type"] == "file" and item["name"].endswith(".md"):
                if item["name"] == "README.md":
                    continue
                files.append(GitHubFile(
                    path=item["path"],
                    name=item["name"],
                    size=item["size"],
                    sha=item["sha"],
                    download_url=item["download_url"],
                    html_url=item["html_url"],
                ))
            elif item["type"] == "dir":
                # 跳过隐藏目录和 archives
                if item["name"].startswith(".") or item["name"] == "archives":
                    continue
                sub_files = await self._list_all(item["path"])
                files.extend(sub_files)

        return files

    async def _list_changed_since(self, since_sha: str) -> list[GitHubFile]:
        """
        基于 git diff 的增量同步。
        比较当前 commit 和 since_sha,返回变更的 .md 文件。
        """
        r = await self.client.get(
            f"/repos/{self.repo}/compare/{since_sha}...{self.branch}"
        )
        r.raise_for_status()

        files = []
        for file_info in r.json().get("files", []):
            if not file_info["filename"].endswith(".md"):
                continue
            if file_info["status"] == "removed":
                continue  # 删除的文件另外处理
            if file_info["filename"].endswith("README.md"):
                continue

            files.append(GitHubFile(
                path=file_info["filename"],
                name=file_info["filename"].split("/")[-1],
                size=0,  # compare API 不返回 size
                sha=file_info["sha"],
                download_url=file_info["raw_url"],
                html_url=file_info["blob_url"],
            ))
        return files

    async def get_file_content(self, download_url: str) -> str:
        """下载单个文件的 raw content"""
        r = await self.client.get(download_url)
        r.raise_for_status()
        return r.text

    async def get_file_metadata(self, path: str) -> dict:
        """获取文件的详细 metadata(包括最后提交时间)"""
        # 用 commits API 获取这个文件的最新 commit
        r = await self.client.get(
            f"/repos/{self.repo}/commits",
            params={"path": path, "per_page": 1},
        )
        r.raise_for_status()
        commits = r.json()
        if not commits:
            return {}
        return {
            "last_modified": commits[0]["commit"]["committer"]["date"],
            "commit_sha": commits[0]["sha"],
        }

    async def check_rate_limit(self) -> dict:
        """检查 rate limit 状态"""
        r = await self.client.get("/rate_limit")
        r.raise_for_status()
        return r.json()["rate"]

    async def close(self):
        await self.client.aclose()
```

### D.3 Frontmatter 解析(`app/reflection/frontmatter_parser.py`)

```python
"""
解析 reflection markdown 的 YAML frontmatter。
"""
import frontmatter
from datetime import datetime
from app.reflection.schemas import (
    ReflectionMetadata,
    ReflectionSource,
    ReflectionDepth,
)


class FrontmatterParseError(Exception):
    pass


def parse_reflection(
    content: str,
    github_path: str,
    github_url: str,
    github_raw_url: str,
    commit_sha: str,
    last_modified: datetime,
) -> ReflectionMetadata:
    """
    解析 markdown content,返回 ReflectionMetadata。
    如果 frontmatter 不合规,抛出 FrontmatterParseError。
    """
    try:
        post = frontmatter.loads(content)
    except Exception as e:
        raise FrontmatterParseError(f"YAML parse failed: {e}")

    meta = post.metadata

    # 必填字段检查
    required = ["id", "title", "timestamp", "source", "tags"]
    missing = [k for k in required if k not in meta]
    if missing:
        raise FrontmatterParseError(f"Missing required fields: {missing}")

    try:
        return ReflectionMetadata(
            id=meta["id"],
            title=meta["title"],
            timestamp=meta["timestamp"] if isinstance(meta["timestamp"], datetime)
                      else datetime.fromisoformat(str(meta["timestamp"])),
            source=ReflectionSource(meta["source"]),
            tags=meta["tags"] if isinstance(meta["tags"], list) else [],

            github_path=github_path,
            github_url=github_url,
            github_raw_url=github_raw_url,
            commit_sha=commit_sha,
            last_modified=last_modified,

            depth=ReflectionDepth(meta["depth"]) if "depth" in meta else None,
            duration_minutes=meta.get("duration_minutes"),
            self_correction_count=meta.get("self_correction_count"),
            related=meta.get("related", []),
            raw_archive=meta.get("raw_archive"),
        )
    except Exception as e:
        raise FrontmatterParseError(f"Schema validation failed: {e}")
```

---

## Part E — Index 构建与同步

### E.1 主同步逻辑(`app/reflection/index_builder.py`)

```python
"""
维护 reflection 索引。
支持全量同步和增量同步。
"""
import asyncio
from datetime import datetime, timezone
from app.reflection.github_client import GitHubReflectionClient
from app.reflection.frontmatter_parser import parse_reflection, FrontmatterParseError
from app.reflection.schemas import ReflectionIndex, SyncState
from app.storage import s3_get_json, s3_put_json  # 复用现有 S3 client


REFLECTIONS_INDEX_KEY = "reflections/index.json"
SYNC_STATE_KEY = "reflections/sync_state.json"


async def sync_reflections(force_full: bool = False) -> SyncState:
    """
    同步 GitHub reflections 到 S3 索引。

    Args:
        force_full: True 则强制全量同步,忽略 sync_state

    Returns:
        更新后的 SyncState
    """
    client = GitHubReflectionClient()
    errors = []

    try:
        # 读取当前同步状态
        try:
            state_data = await s3_get_json(SYNC_STATE_KEY)
            state = SyncState(**state_data)
        except Exception:
            state = SyncState(
                last_sync_at=datetime.now(tz=timezone.utc),
                last_commit_sha=None,
            )

        # 决定同步策略
        current_sha = await client.get_latest_commit_sha()

        if force_full or state.last_commit_sha is None:
            print("📦 Full sync...")
            files = await client.list_markdown_files()
            existing_index = ReflectionIndex(
                last_updated=datetime.now(tz=timezone.utc),
                total_count=0,
                reflections=[],
            )
        else:
            if state.last_commit_sha == current_sha:
                print("✓ Already up to date")
                state.last_sync_at = datetime.now(tz=timezone.utc)
                state.last_success = True
                await s3_put_json(SYNC_STATE_KEY, state.model_dump(mode="json"))
                return state

            print(f"🔄 Incremental sync from {state.last_commit_sha[:7]} to {current_sha[:7]}")
            files = await client.list_markdown_files(since_sha=state.last_commit_sha)
            # 加载现有索引
            try:
                index_data = await s3_get_json(REFLECTIONS_INDEX_KEY)
                existing_index = ReflectionIndex(**index_data)
            except Exception:
                # 索引丢失,fallback 到全量
                print("⚠️  Index not found, falling back to full sync")
                files = await client.list_markdown_files()
                existing_index = ReflectionIndex(
                    last_updated=datetime.now(tz=timezone.utc),
                    total_count=0,
                    reflections=[],
                )

        print(f"📥 Processing {len(files)} files...")

        # 解析每个文件
        reflections_by_id = {r.id: r for r in existing_index.reflections}

        for f in files:
            try:
                content = await client.get_file_content(f.download_url)
                metadata_info = await client.get_file_metadata(f.path)

                reflection = parse_reflection(
                    content=content,
                    github_path=f.path,
                    github_url=f.html_url,
                    github_raw_url=f.download_url,
                    commit_sha=metadata_info.get("commit_sha", current_sha),
                    last_modified=datetime.fromisoformat(
                        metadata_info.get("last_modified", datetime.now(tz=timezone.utc).isoformat())
                    ),
                )
                reflections_by_id[reflection.id] = reflection
                print(f"  ✓ {reflection.id}")

            except FrontmatterParseError as e:
                errors.append(f"{f.path}: {e}")
                print(f"  ✗ {f.path}: {e}")
                continue
            except Exception as e:
                errors.append(f"{f.path}: unexpected error: {e}")
                print(f"  ✗ {f.path}: {e}")
                continue

        # 保存索引
        new_index = ReflectionIndex(
            schema_version="2.0",
            last_updated=datetime.now(tz=timezone.utc),
            total_count=len(reflections_by_id),
            reflections=sorted(
                reflections_by_id.values(),
                key=lambda r: r.timestamp,
                reverse=True,
            ),
        )
        await s3_put_json(REFLECTIONS_INDEX_KEY, new_index.model_dump(mode="json"))

        # 更新 sync state
        state.last_sync_at = datetime.now(tz=timezone.utc)
        state.last_commit_sha = current_sha
        state.last_success = len(errors) == 0
        state.last_error = "; ".join(errors[:5]) if errors else None
        state.total_reflections = new_index.total_count
        await s3_put_json(SYNC_STATE_KEY, state.model_dump(mode="json"))

        print(f"\n✅ Sync complete: {new_index.total_count} reflections, {len(errors)} errors")
        return state

    finally:
        await client.close()
```

### E.2 定时任务(对接 EventBridge)

新增 `app/reflection/cron_sync.py`:

```python
"""
每日定时同步入口。
由 EventBridge 触发,和现有 daily radar 的 cron 对齐。
"""
import asyncio
from app.reflection.index_builder import sync_reflections


def handler(event, context):
    """AWS Lambda / ECS entry point"""
    state = asyncio.run(sync_reflections())
    return {
        "statusCode": 200,
        "body": state.model_dump(mode="json"),
    }


if __name__ == "__main__":
    # 本地测试
    asyncio.run(sync_reflections())
```

**EventBridge rule**(加到现有 infra):

```yaml
ReflectionSyncRule:
  Type: AWS::Events::Rule
  Properties:
    ScheduleExpression: "cron(0 22 * * ? *)"  # 每天 UTC 22:00 = 澳东 09:00
    State: ENABLED
    Targets:
      - Arn: !GetAtt ReflectionSyncFunction.Arn
```

**选择每日凌晨同步的原因**:
- 你的 reflection 通常在晚上整理
- 凌晨 sync 保证第二天的 Daily Radar 能用上最新的 reflection
- 和现有 daily radar cron 时间错开,减少资源冲突

---

## Part F — Matching 实现(v1: tag-based)

### F.1 匹配逻辑(`app/reflection/matcher.py`)

```python
"""
Signal ↔ Reflection matching。
v1 版本:基于 tag 和 entity 的硬匹配。
"""
from app.reflection.schemas import Match, DailyMatches, ReflectionMetadata
from datetime import datetime, timezone


# Tag 同义词映射(手工维护,避免"ai-agent" vs "ai-agents"不匹配)
TAG_SYNONYMS = {
    "ai-agent": "ai-agents",
    "agent-memory": "agent-memory",
    "llm-system": "llm-systems",
    # 根据实际使用情况逐步添加
}


def normalize_tag(tag: str) -> str:
    """标准化 tag(小写 + synonym 替换)"""
    tag = tag.lower().strip()
    return TAG_SYNONYMS.get(tag, tag)


def compute_tag_overlap(
    signal_tags: list[str],
    reflection_tags: list[str],
) -> tuple[float, list[str]]:
    """
    计算 tag 重合度。
    返回 (score, 匹配的 tag 列表)。
    """
    signal_set = {normalize_tag(t) for t in signal_tags}
    reflection_set = {normalize_tag(t) for t in reflection_tags}

    overlap = signal_set & reflection_set
    if not overlap:
        return 0.0, []

    # Jaccard similarity
    union = signal_set | reflection_set
    score = len(overlap) / len(union)
    return score, list(overlap)


def match_signal_to_reflections(
    signal_id: str,
    signal_tags: list[str],
    signal_entities: list[str],
    reflections: list[ReflectionMetadata],
    min_score: float = 0.2,
    top_k: int = 3,
) -> list[Match]:
    """
    给一个 signal 找最相关的 reflection。

    Args:
        min_score: 最低匹配分数阈值
        top_k: 返回 top K 个匹配
    """
    candidates = []

    # 把 entities 也当作 tags 参与匹配
    signal_all_tags = signal_tags + signal_entities

    for r in reflections:
        score, matched = compute_tag_overlap(signal_all_tags, r.tags)
        if score >= min_score:
            candidates.append(Match(
                signal_id=signal_id,
                reflection_id=r.id,
                match_type="tag_overlap",
                score=score,
                matched_on=matched,
            ))

    # 按分数排序,取 top K
    candidates.sort(key=lambda m: m.score, reverse=True)
    return candidates[:top_k]


async def compute_daily_matches(
    signals: list[dict],  # 来自 signal pipeline 的输出
    reflections: list[ReflectionMetadata],
) -> DailyMatches:
    """计算当日所有 signal 的 reflection 匹配"""
    all_matches = []

    for signal in signals:
        signal_tags = signal.get("tags", [])
        signal_entities = signal.get("entities", [])
        signal_id = signal["id"]

        matches = match_signal_to_reflections(
            signal_id=signal_id,
            signal_tags=signal_tags,
            signal_entities=signal_entities,
            reflections=reflections,
        )
        all_matches.extend(matches)

    return DailyMatches(
        date=datetime.now(tz=timezone.utc),
        total_signals=len(signals),
        total_reflections_checked=len(reflections),
        matches=all_matches,
    )
```

### F.2 集成到 Daily Radar Pipeline

在 `app/main_summary_v2.py` 的 daily radar 生成流程中,**添加一步 matching**:

```python
# 在生成 daily radar 之后,添加:
from app.reflection.matcher import compute_daily_matches
from app.storage import s3_get_json

# 加载 reflection 索引
index_data = await s3_get_json("reflections/index.json", default={"reflections": []})
reflections = [ReflectionMetadata(**r) for r in index_data["reflections"]]

# 对每个 signal 做 matching
daily_matches = await compute_daily_matches(
    signals=daily_radar_data["signals"],
    reflections=reflections,
)

# 存储 matches(用于 UI 查询)
date_path = datetime.now().strftime("%Y/%m/%d")
await s3_put_json(
    f"reflections/matches/{date_path}/daily_matches.json",
    daily_matches.model_dump(mode="json"),
)

# 把 match 信息注入到 daily_radar(供 UI 展示)
matches_by_signal = {m.signal_id: [] for m in daily_matches.matches}
for m in daily_matches.matches:
    matches_by_signal.setdefault(m.signal_id, []).append({
        "reflection_id": m.reflection_id,
        "score": m.score,
        "matched_on": m.matched_on,
    })

for signal in daily_radar_data["signals"]:
    signal["related_reflections"] = matches_by_signal.get(signal["id"], [])
```

---

## Part G — API 路由

### G.1 Backend 路由(`backend/app/routes/reflection.py`)

```python
from fastapi import APIRouter, HTTPException, Query
from app.reflection.schemas import ReflectionIndex, ReflectionMetadata, DailyMatches
from backend.app.services.reflection_service import ReflectionService

router = APIRouter(prefix="/api/reflection", tags=["reflection"])
service = ReflectionService()


@router.get("/", response_model=list[ReflectionMetadata])
async def list_reflections(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    tag: str | None = None,
    source: str | None = None,
):
    """列出 reflection(支持分页和过滤)"""
    return await service.list_reflections(
        limit=limit, offset=offset, tag=tag, source=source,
    )


@router.get("/tags", response_model=dict[str, int])
async def list_tags():
    """返回所有 tag 及其使用次数(用于 tag cloud / filter UI)"""
    return await service.get_tag_distribution()


@router.get("/{reflection_id}", response_model=dict)
async def get_reflection(reflection_id: str):
    """
    获取单条 reflection 的完整内容。
    metadata 来自索引,content 实时从 GitHub 拉取。
    """
    result = await service.get_reflection_full(reflection_id)
    if not result:
        raise HTTPException(status_code=404, detail="Reflection not found")
    return result


@router.get("/{reflection_id}/related-signals", response_model=list[dict])
async def get_related_signals(reflection_id: str, days: int = 30):
    """查询过去 N 天内与该 reflection 匹配的 signals"""
    return await service.get_related_signals(reflection_id, days=days)


@router.post("/sync")
async def trigger_sync(force_full: bool = False):
    """手动触发同步(用于开发/调试)"""
    state = await service.trigger_sync(force_full=force_full)
    return state.model_dump(mode="json")


@router.get("/sync/status")
async def get_sync_status():
    """查询同步状态"""
    return await service.get_sync_state()
```

### G.2 服务层(`backend/app/services/reflection_service.py`)

负责:
- 从 S3 读取 index
- 按条件过滤
- 实时从 GitHub 拉取单条 content(缓存 5 分钟)
- 处理 tag distribution、related signals 查询
- 触发 sync

实现略,按 §G.1 的接口展开。

---

## Part H — 前端 UI 设计

### H.1 独立 Reflection 页面

**路径**: `/reflections`

**布局**:

```
┌────────────────────────────────────────────────────────┐
│  Reflections                                           │
│  总数: 42  |  本月新增: 8  |  上次同步: 2 小时前        │
│                                                         │
│  [搜索框]                  [Tag filter ▾] [Source ▾]   │
├────────────────────────────────────────────────────────┤
│                                                         │
│  2026 04                                                │
│  ┌──────────────────────────────────────────────────┐ │
│  │  2026-04-12 · AI Radar 定位与商业模式深度拆解    │ │
│  │  #ai-radar #business-model #cognitive-tools      │ │
│  │  Deep · 160 min · 3 corrections                  │ │
│  │  [查看详情 →]                                     │ │
│  └──────────────────────────────────────────────────┘ │
│  ┌──────────────────────────────────────────────────┐ │
│  │  2026-04-15 · Agent Memory 架构的演化思考         │ │
│  │  #ai-agents #agent-memory                        │ │
│  │  Deep · 90 min                                   │ │
│  │  [查看详情 →]                                     │ │
│  └──────────────────────────────────────────────────┘ │
│                                                         │
│  2026 03                                                │
│  ...                                                    │
└────────────────────────────────────────────────────────┘
```

**关键交互**:
- 点击条目跳转到详情页 `/reflections/{id}`
- Tag filter 多选,支持 AND 逻辑
- Source filter 下拉
- 搜索框搜 title + tag(不搜 content,content 在 GitHub)

### H.2 详情页

**路径**: `/reflections/[id]`

**布局**:

```
┌────────────────────────────────────────────────────────┐
│  ← 返回列表                          [在 GitHub 中打开]│
├────────────────────────────────────────────────────────┤
│                                                         │
│  AI Radar 定位与商业模式深度拆解                       │
│  2026-04-12 · Deep · 160 min · 3 corrections           │
│  #ai-radar #business-model #cognitive-tools             │
│                                                         │
│  ─────────────────────────────────────────────────     │
│                                                         │
│  (实时从 GitHub 拉取的 markdown content,渲染为 HTML)  │
│                                                         │
│  ## 🎯 Compressed Core                                 │
│  - ...                                                  │
│                                                         │
│  ## 📋 Cognitive Skeleton                              │
│  ...                                                    │
│                                                         │
│  ─────────────────────────────────────────────────     │
│                                                         │
│  📡 相关 Signal(过去 30 天)                          │
│  ┌──────────────────────────────────────────────────┐ │
│  │  [Signal] Anthropic 发布 Claude Opus 5           │ │
│  │  匹配 tags: ai-agents, llm-systems               │ │
│  │  2026-04-20                                      │ │
│  └──────────────────────────────────────────────────┘ │
│                                                         │
└────────────────────────────────────────────────────────┘
```

### H.3 Daily Radar 入口组件

在现有 Daily Radar 页面,每个 topic 后面添加一个小卡片(折叠式):

```
┌──────────────────────────────────────────────────────┐
│  🔥 Topic: AI Agent Frameworks                       │
│  ...                                                  │
│  (现有 signal 列表)                                   │
│  ...                                                  │
│                                                       │
│  💭 相关深度反思(2) [展开 ▾]                        │
└──────────────────────────────────────────────────────┘
```

展开后:
```
┌──────────────────────────────────────────────────────┐
│  💭 相关深度反思(2)                        [收起 ▴]│
│                                                       │
│  • 2026-04-12 · AI Radar 定位与商业模式深度拆解     │
│    匹配:#ai-agents #ai-radar                        │
│    [查看 →]                                          │
│                                                       │
│  • 2026-04-08 · Agent Memory 架构的演化思考          │
│    匹配:#agent-memory                               │
│    [查看 →]                                          │
└──────────────────────────────────────────────────────┘
```

**设计原则**:
- 默认折叠,不干扰现有 Daily Radar 体验
- 最多显示 3 条(避免信息过载)
- 点击跳转到 Reflection 详情页

---

## Part I — 实施路线图

### Phase 0:连通性验证(1 天)

详见架构文档 Part E。

### Phase 1:基础 Ingestion(1 周)

**Day 1-2: 基础设施**
- [ ] 创建 `app/reflection/` 目录结构
- [ ] 实现 `schemas.py`
- [ ] 实现 `github_client.py`
- [ ] 单元测试覆盖 GitHub client

**Day 3-4: Parser + Index**
- [ ] 实现 `frontmatter_parser.py`
- [ ] 实现 `index_builder.py`
- [ ] 全量同步跑通,确认 S3 索引生成正确

**Day 5: API + Cron**
- [ ] 实现 `backend/app/routes/reflection.py`(只做 list + get)
- [ ] 实现 cron 定时同步
- [ ] curl 测试 API

**出口标准**:
- [ ] 可以从命令行手动触发同步
- [ ] `GET /api/reflection/` 能返回列表
- [ ] `GET /api/reflection/{id}` 能返回单条(含实时拉取的 content)
- [ ] 定时同步 cron 配置完成

### Phase 2:UI(1 周)

**Day 1-3: 列表页**
- [ ] `/reflections` 页面
- [ ] Tag filter + source filter
- [ ] 分页

**Day 4-5: 详情页**
- [ ] `/reflections/[id]` 页面
- [ ] Markdown 实时渲染
- [ ] GitHub 跳转链接

**Day 6-7: Daily Radar 集成入口**
- [ ] 在现有 Daily Radar 里添加 "相关深度反思" 组件(默认空)

**出口标准**:
- [ ] 能浏览所有 reflection
- [ ] 能看单条完整内容
- [ ] 现有 Daily Radar 功能不被破坏

### Phase 3:Matching v1(1–2 周)

**Week 1: Matcher**
- [ ] 实现 `matcher.py`(tag-based)
- [ ] 集成到 daily radar pipeline
- [ ] Matches 结果存 S3

**Week 2: UI 集成**
- [ ] Daily Radar 的 "相关深度反思" 真正显示匹配结果
- [ ] Reflection 详情页显示 "相关 signals"
- [ ] API 支持 `/related-signals` 查询

**出口标准**:
- [ ] 每天 daily radar 生成时,自动算出 matches
- [ ] UI 能看到 signal ↔ reflection 的交叉引用
- [ ] 至少 30% 的 daily signals 有相关 reflection(如果 reflection 足够多)

### Phase 4(非必需):Matching v2(仅在 v1 明显不够时)

**启动条件**:
- v1 跑了至少 2 个月
- 发现明显的语义相关但 tag 不同的漏召
- 你愿意承受 embedding 的存储和 API 成本

**工作内容**:
- Reflection 的 key_insights 生成 embedding
- Signal summary 生成 embedding
- 用 cosine similarity 做语义匹配
- 和 v1 的 tag matching 做混合融合

### Phase 5(6 个月+):Cross-referencing Tracking

在有 50+ reflection 和足够 signal 历史后,才做:
- 追踪某条 reflection 的 insight 被后续 signals 验证/反驳几次
- 时间线视图

---

## Part J — 给 Codex 的任务说明

```markdown
任务:在现有 AI Radar 项目中实现 Reflection 集成(Phase 1)。

# 前置条件

1. 架构文档 `system-architecture.md` 已读
2. Phase 0 连通性测试已通过(scripts/test_github_connection.py)
3. GitHub reflections repo 已创建,至少有 3 条测试 reflection

# 硬约束

1. 不修改 app/main_summary_v2.py 及现有 signal pipeline 核心代码
2. 所有 LLM 调用(如果有)必须走 app/intelligence/model_router.py
3. S3 路径严格按照本文档 §B.2 规范
4. AI Radar 对 GitHub 永远只读,禁止任何写入操作
5. 不存 reflection content 到 S3,只存 metadata + link
6. 严格按 Pydantic schema(见 §C.1),所有 API 返回值都要校验

# Phase 1 交付物

- app/reflection/ 下所有模块(见 §B.1)
  - schemas.py
  - github_client.py
  - frontmatter_parser.py
  - index_builder.py
  - cron_sync.py(EventBridge 入口)
- backend/app/routes/reflection.py(4 个 endpoint,见 §G.1 的前 4 个)
- backend/app/services/reflection_service.py
- scripts/sync_reflections.py(手动触发)
- tests/reflection/ 下至少 12 个单元测试
- 更新 docker-compose 或 lambda 配置,加入 GITHUB_REFLECTIONS_* 环境变量

# 不要做的事

- 不要做前端(Phase 2 独立任务)
- 不要做 Matching(Phase 3 独立任务)
- 不要做 Webhook 实时同步(只做定时同步)
- 不要做 write API(AI Radar 只读)
- 不要引入 vector DB(这是深度 reflection 索引,量级小)
- 不要自己设计 frontmatter schema 扩展(严格按 §C.1)

# 验收标准

1. pytest tests/reflection/ 全绿
2. 手动跑 python scripts/sync_reflections.py 能完成一次全量同步
3. S3 上 reflections/index.json 生成且 schema 合规
4. curl GET /api/reflection/ 返回索引
5. curl GET /api/reflection/{id} 返回完整 content(实时从 GitHub 拉取)
6. curl POST /api/reflection/sync 手动触发同步
7. EventBridge rule 配置到位,每天定时触发
8. 代码风格符合现有 app/ 和 backend/app/ 约定

# 依赖

已有:
- FastAPI backend
- Pydantic
- Boto3 / AWS S3
- EventBridge / ECS Fargate

新增依赖(最小化):
- httpx (可能已有)
- python-frontmatter (用于解析 YAML frontmatter)
- 无新增 DB,无新增 queue
```

---

## Part K — 运维注意事项

### K.1 GitHub API Rate Limit

- Fine-grained PAT: **5000 requests/hour**
- 每日同步一次:消耗大约 `2 + N files × 2` 次请求(N = 变更文件数)
- 正常情况下每天 < 50 请求,完全不会触发 rate limit
- 如果触发:`check_rate_limit()` 会返回,优雅降级即可

### K.2 监控指标

建议接入现有 observability,监控:
- `reflection.sync.last_success` (bool)
- `reflection.sync.error_count` (int)
- `reflection.sync.total_reflections` (int)
- `reflection.sync.duration_seconds` (float)
- `reflection.matching.match_rate` (float, 0-1)

### K.3 数据一致性

**场景 1:GitHub 里删除了一个 reflection 文件**
- 增量同步的 `compare` API 会返回 `status=removed`
- 当前代码**跳过 removed** 文件(见 `_list_changed_since`)
- TODO:Phase 1 之后,加入"从索引里移除"的逻辑

**场景 2:frontmatter 解析失败**
- 当前代码跳过该文件,记录 error
- 索引里保留上一次成功的版本(如果有)
- 下次同步时会重试

**场景 3:索引文件损坏**
- `sync_reflections(force_full=True)` 可重建
- 因为 GitHub 是 source of truth,永远可以全量重建

---

## 最后的判断

这个方案的**工程复杂度是中等的,但需要你做的决策很少**。大部分复杂度在工程实现上,对你的心智负担小:

- Schema 已定义清楚,不需要 taxonomy 迭代
- Matching v1 是硬规则,不需要调参
- Frontend 是标准 CRUD 页面
- 没有 LLM 调用(Phase 1-3),成本可控

**真正影响成败的不是工程,是两件事**:
1. 你能不能持续手工整理 reflection(每 3 天一次)
2. 你整理的 reflection 质量够不够高

这两件事工程解决不了。工程能保证的只是:**一旦你开始做,系统不会成为你的阻碍**。

---

*v2.0 — 2026-04-13*
*配套文档:`system-architecture.md`(架构与规范)*
