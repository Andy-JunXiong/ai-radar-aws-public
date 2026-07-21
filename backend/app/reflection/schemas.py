from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


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
    id: str = Field(..., description="refl_YYYY-MM-DD_<slug>")
    title: str = Field(..., max_length=200)
    timestamp: datetime
    source: ReflectionSource
    tags: list[str] = Field(default_factory=list)

    github_path: str
    github_url: HttpUrl
    github_raw_url: HttpUrl
    last_modified: datetime
    commit_sha: str
    content_format: Literal["markdown", "json_html"] = "markdown"
    schema_path: str | None = None
    schema_url: HttpUrl | None = None
    schema_raw_url: HttpUrl | None = None
    raw_html_path: str | None = None
    raw_html_url: HttpUrl | None = None

    depth: ReflectionDepth | None = None
    duration_minutes: int | None = None
    self_correction_count: int | None = None
    thesis: str | None = None
    key_claims: list[str] = Field(default_factory=list)
    counterpoints: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    final_takeaway: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    evidence_strength: str | None = None
    related: list[str] = Field(default_factory=list)
    raw_archive: str | None = None
    synced_at: datetime = Field(default_factory=datetime.utcnow)


class ReflectionIndex(BaseModel):
    schema_version: str = "2.0"
    last_updated: datetime
    total_count: int
    reflections: list[ReflectionMetadata]


class SyncState(BaseModel):
    last_sync_at: datetime
    last_commit_sha: str | None = None
    last_success: bool = True
    last_error: str | None = None
    total_reflections: int = 0


class Match(BaseModel):
    signal_id: str
    reflection_id: str
    match_type: Literal["tag_overlap", "entity_overlap", "title_semantic"]
    score: float = Field(..., ge=0.0, le=1.0)
    matched_on: list[str] = Field(default_factory=list)


class DailyMatches(BaseModel):
    date: datetime
    total_signals: int
    total_reflections_checked: int
    matches: list[Match] = Field(default_factory=list)
