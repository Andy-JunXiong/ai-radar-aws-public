from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SIGNAL_FILES = (
    REPO_ROOT / "data" / "output" / "signals.json",
    REPO_ROOT / "data" / "output" / "collected_signals.json",
    REPO_ROOT / "data" / "output" / "official_signals.json",
    REPO_ROOT / "data" / "output" / "rss_signals.json",
)
TEXT_FIELDS = ("source_excerpt", "content", "summary", "description")
URL_FIELDS = ("source_url", "url", "link")
MIN_FINGERPRINT_TOKENS = 10
FINGERPRINT_TOKEN_LIMIT = 48


@dataclass(frozen=True)
class SignalRecordSnapshot:
    path: str
    index: int
    record_id: str
    title: str
    source: str
    url: str
    normalized_url: str
    published_at: str
    collected_at: str
    source_excerpt_length: int | None
    fingerprint: str
    is_category_url: bool
    is_article_url: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "index": self.index,
            "record_id": self.record_id,
            "title": self.title,
            "source": self.source,
            "url": self.url,
            "normalized_url": self.normalized_url,
            "published_at": self.published_at,
            "collected_at": self.collected_at,
            "source_excerpt_length": self.source_excerpt_length,
            "is_category_url": self.is_category_url,
            "is_article_url": self.is_article_url,
        }


@dataclass(frozen=True)
class CleanupRecommendation:
    safe_action: str
    reason: str
    requires_human_review: bool
    preferred_record_id: str
    demote_candidate_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "safe_action": self.safe_action,
            "reason": self.reason,
            "requires_human_review": self.requires_human_review,
            "preferred_record_id": self.preferred_record_id,
            "demote_candidate_ids": list(self.demote_candidate_ids),
        }


@dataclass(frozen=True)
class NearDuplicateGroup:
    duplicate_type: str
    fingerprint: str
    record_count: int
    distinct_url_count: int
    paths: tuple[str, ...]
    sources: tuple[str, ...]
    preferred_record: SignalRecordSnapshot | None
    cleanup_recommendation: CleanupRecommendation
    records: tuple[SignalRecordSnapshot, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "duplicate_type": self.duplicate_type,
            "fingerprint": self.fingerprint,
            "record_count": self.record_count,
            "distinct_url_count": self.distinct_url_count,
            "paths": list(self.paths),
            "sources": list(self.sources),
            "preferred_record": self.preferred_record.to_dict() if self.preferred_record else None,
            "cleanup_recommendation": self.cleanup_recommendation.to_dict(),
            "records": [record.to_dict() for record in self.records],
        }


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _relative_path(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)


def _read_json(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None


def _records_from_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [record for record in payload if isinstance(record, dict)]
    if isinstance(payload, dict):
        for key in ("signals", "items", "records"):
            records = payload.get(key)
            if isinstance(records, list):
                return [record for record in records if isinstance(record, dict)]
    return []


def _first_text(record: dict[str, Any], fields: tuple[str, ...]) -> str:
    for field in fields:
        value = _safe_text(record.get(field))
        if value:
            return value
    return ""


def _best_content_text(record: dict[str, Any]) -> str:
    values = [_safe_text(record.get(field)) for field in TEXT_FIELDS]
    values = [value for value in values if value]
    if not values:
        return ""
    return max(values, key=len)


def _normalize_url(url: str) -> str:
    if not url:
        return ""
    parsed = urlparse(url)
    scheme = parsed.scheme.lower() or "https"
    netloc = parsed.netloc.lower()
    path = re.sub(r"/+", "/", parsed.path).rstrip("/")
    return f"{scheme}://{netloc}{path}"


def _is_category_url(url: str) -> bool:
    return "/category/" in urlparse(url).path.lower()


def _is_article_url(url: str) -> bool:
    path = urlparse(url).path.lower().strip("/")
    return bool(path) and "/category/" not in f"/{path}/"


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _content_fingerprint(record: dict[str, Any]) -> str:
    tokens = _tokens(_best_content_text(record))
    if len(tokens) < MIN_FINGERPRINT_TOKENS:
        return ""
    return " ".join(tokens[:FINGERPRINT_TOKEN_LIMIT])


def _record_snapshot(
    *,
    record: dict[str, Any],
    path: Path,
    root: Path,
    index: int,
) -> SignalRecordSnapshot | None:
    fingerprint = _content_fingerprint(record)
    url = _first_text(record, URL_FIELDS)
    normalized_url = _normalize_url(url)
    if not fingerprint or not normalized_url:
        return None

    record_id = (
        _safe_text(record.get("id"))
        or _safe_text(record.get("signal_id"))
        or _safe_text(record.get("source_id"))
        or f"record-{index}"
    )
    return SignalRecordSnapshot(
        path=_relative_path(path, root),
        index=index,
        record_id=record_id,
        title=_safe_text(record.get("title")),
        source=_safe_text(record.get("source")),
        url=url,
        normalized_url=normalized_url,
        published_at=_safe_text(record.get("published_at")) or _safe_text(record.get("published")),
        collected_at=_safe_text(record.get("collected_at")),
        source_excerpt_length=_safe_int(record.get("source_excerpt_length")),
        fingerprint=fingerprint,
        is_category_url=_is_category_url(normalized_url),
        is_article_url=_is_article_url(normalized_url),
    )


def _title_quality(record: SignalRecordSnapshot) -> int:
    title = record.title.lower()
    score = len(_tokens(record.title))
    if record.is_article_url:
        score += 10
    if record.is_category_url:
        score -= 10
    if title in {"artificial intelligence | artificial intelligence", "artificial intelligence"}:
        score -= 8
    if record.source_excerpt_length:
        score += 2
    return score


def _preferred_record(records: list[SignalRecordSnapshot]) -> SignalRecordSnapshot | None:
    article_records = [record for record in records if record.is_article_url]
    candidates = article_records or records
    if not candidates:
        return None
    return sorted(
        candidates,
        key=lambda record: (
            _title_quality(record),
            record.source_excerpt_length or 0,
            -record.index,
        ),
        reverse=True,
    )[0]


def _duplicate_type(records: list[SignalRecordSnapshot]) -> str:
    has_category = any(record.is_category_url for record in records)
    has_article = any(record.is_article_url for record in records)
    if has_category and has_article:
        return "category_vs_article"
    return "same_content_different_url"


def _cleanup_recommendation(
    *,
    duplicate_type: str,
    preferred: SignalRecordSnapshot | None,
    records: list[SignalRecordSnapshot],
) -> CleanupRecommendation:
    preferred_record_id = preferred.record_id if preferred else ""
    demote_candidates = tuple(
        record.record_id
        for record in records
        if preferred is None or record.record_id != preferred.record_id
    )

    if duplicate_type == "category_vs_article" and preferred and preferred.is_article_url:
        return CleanupRecommendation(
            safe_action="prefer_canonical_for_display_and_insight_generation",
            reason=(
                "A category URL and a canonical article URL share the same content fingerprint. "
                "Prefer the canonical article URL/title while keeping category records reviewable."
            ),
            requires_human_review=False,
            preferred_record_id=preferred_record_id,
            demote_candidate_ids=demote_candidates,
        )

    return CleanupRecommendation(
        safe_action="review_before_cleanup",
        reason=(
            "Records share a content fingerprint across distinct URLs, but the group is not a clear "
            "category-vs-article pair. Keep report-only until a human confirms whether URLs represent "
            "duplicates or related-but-distinct articles."
        ),
        requires_human_review=True,
        preferred_record_id=preferred_record_id,
        demote_candidate_ids=demote_candidates,
    )


def build_signal_near_duplicate_report(
    *,
    signal_files: list[Path] | None = None,
    root: Path = REPO_ROOT,
    include_records: bool = True,
) -> dict[str, Any]:
    files = signal_files or list(DEFAULT_SIGNAL_FILES)
    snapshots: list[SignalRecordSnapshot] = []
    file_record_counts: dict[str, int] = {}

    for path in files:
        payload = _read_json(path)
        records = _records_from_payload(payload)
        relative = _relative_path(path, root)
        file_record_counts[relative] = len(records)
        for index, record in enumerate(records):
            snapshot = _record_snapshot(record=record, path=path, root=root, index=index)
            if snapshot:
                snapshots.append(snapshot)

    by_fingerprint: dict[str, list[SignalRecordSnapshot]] = defaultdict(list)
    for snapshot in snapshots:
        by_fingerprint[snapshot.fingerprint].append(snapshot)

    duplicate_groups: list[NearDuplicateGroup] = []
    for fingerprint, records in by_fingerprint.items():
        distinct_urls = {record.normalized_url for record in records}
        if len(records) < 2 or len(distinct_urls) < 2:
            continue
        sorted_records = tuple(sorted(records, key=lambda record: (record.normalized_url, record.path, record.index)))
        duplicate_type = _duplicate_type(records)
        preferred = _preferred_record(records)
        duplicate_groups.append(
            NearDuplicateGroup(
                duplicate_type=duplicate_type,
                fingerprint=fingerprint,
                record_count=len(records),
                distinct_url_count=len(distinct_urls),
                paths=tuple(sorted({record.path for record in records})),
                sources=tuple(sorted({record.source or "unknown" for record in records})),
                preferred_record=preferred,
                cleanup_recommendation=_cleanup_recommendation(
                    duplicate_type=duplicate_type,
                    preferred=preferred,
                    records=records,
                ),
                records=sorted_records,
            )
        )

    duplicate_groups.sort(
        key=lambda group: (
            0 if group.duplicate_type == "category_vs_article" else 1,
            -group.record_count,
            group.fingerprint,
        )
    )
    duplicate_type_counts = Counter(group.duplicate_type for group in duplicate_groups)
    safe_action_counts = Counter(group.cleanup_recommendation.safe_action for group in duplicate_groups)
    human_review_count = sum(1 for group in duplicate_groups if group.cleanup_recommendation.requires_human_review)
    summary = {
        "files_scanned": len(files),
        "file_record_counts": dict(sorted(file_record_counts.items())),
        "scannable_record_count": len(snapshots),
        "duplicate_group_count": len(duplicate_groups),
        "category_vs_article_group_count": duplicate_type_counts.get("category_vs_article", 0),
        "same_content_different_url_group_count": duplicate_type_counts.get("same_content_different_url", 0),
        "duplicate_type_counts": dict(sorted(duplicate_type_counts.items())),
        "cleanup_recommendation_counts": dict(sorted(safe_action_counts.items())),
        "groups_requiring_human_review": human_review_count,
        "readiness": "near_duplicates_found" if duplicate_groups else "no_near_duplicates_found",
    }
    return {
        "schema_version": "signal_near_duplicate_report.v1",
        "report_boundary": {
            "mode": "read_only_local_signal_output_check",
            "writes_data": False,
            "runs_ingestion": False,
            "deduplicates_records": False,
            "hard_enforcement": False,
        },
        "heuristic": {
            "content_fields": list(TEXT_FIELDS),
            "url_fields": list(URL_FIELDS),
            "min_fingerprint_tokens": MIN_FINGERPRINT_TOKENS,
            "fingerprint_token_limit": FINGERPRINT_TOKEN_LIMIT,
            "duplicate_rule": "same normalized content fingerprint across two or more distinct normalized URLs",
            "category_url_rule": "URL path contains /category/",
        },
        "summary": summary,
        "groups": [group.to_dict() for group in duplicate_groups] if include_records else [],
    }


def signal_near_duplicate_exit_code(report: dict[str, Any], *, fail_on_findings: bool) -> int:
    if not fail_on_findings:
        return 0
    return 1 if int(report.get("summary", {}).get("duplicate_group_count") or 0) > 0 else 0
