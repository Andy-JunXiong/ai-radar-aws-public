from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.claim_extraction_service import extract_claims_from_insight  # noqa: E402
from app.services.claim_verification_service import verify_claims_against_evidence  # noqa: E402


DEFAULT_SIGNAL_FILES = (
    REPO_ROOT / "data" / "output" / "signals.json",
    BACKEND_ROOT / "data" / "signals.json",
)
DEFAULT_MANUAL_SESSIONS_DIR = BACKEND_ROOT / "data" / "manual_uploads" / "sessions"
INSIGHT_FIELDS = (
    "why_it_matters",
    "relevance_to_projects",
    "relevance_to_career",
    "synthesized_insight",
)
SOURCE_TEXT_FIELDS = (
    "source_excerpt",
    "full_text",
    "article_body",
    "raw_content",
    "raw_text",
    "content",
)
SOURCE_TEXT_EVIDENCE_FIELDS = SOURCE_TEXT_FIELDS + (
    "body",
    "article",
)


@dataclass(frozen=True)
class ClaimOriginSupportRow:
    source: str
    path: str
    record_id: str
    signal_id: str
    signal_source: str
    generation_mode: str
    provider: str
    model: str
    summary_provenance: str
    evidence_item_provenance_counts: dict[str, int]
    evidence_item_source_field_counts: dict[str, int]
    has_source_excerpt: bool
    has_full_text_like_field: bool
    source_text_field_counts: dict[str, int]
    evidence_item_count: int
    existing_verification_status: str
    claim_count: int
    support_counts: dict[str, int]
    origin_counts: dict[str, int]
    direct_supported_count: int
    quoted_count: int
    inferred_count: int
    token_only_inferred_count: int
    source_span_count: int
    existing_claim_support_summary: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "path": self.path,
            "record_id": self.record_id,
            "signal_id": self.signal_id,
            "signal_source": self.signal_source,
            "generation_mode": self.generation_mode,
            "provider": self.provider,
            "model": self.model,
            "summary_provenance": self.summary_provenance,
            "evidence_item_provenance_counts": self.evidence_item_provenance_counts,
            "evidence_item_source_field_counts": self.evidence_item_source_field_counts,
            "has_source_excerpt": self.has_source_excerpt,
            "has_full_text_like_field": self.has_full_text_like_field,
            "source_text_field_counts": self.source_text_field_counts,
            "evidence_item_count": self.evidence_item_count,
            "existing_verification_status": self.existing_verification_status,
            "claim_count": self.claim_count,
            "support_counts": self.support_counts,
            "origin_counts": self.origin_counts,
            "direct_supported_count": self.direct_supported_count,
            "quoted_count": self.quoted_count,
            "inferred_count": self.inferred_count,
            "token_only_inferred_count": self.token_only_inferred_count,
            "source_span_count": self.source_span_count,
            "existing_claim_support_summary": self.existing_claim_support_summary,
        }


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _read_json(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None


def _relative_path(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)


def _verification_from_record(record: dict[str, Any]) -> dict[str, Any]:
    verification = _as_dict(record.get("verification"))
    if verification:
        return verification
    return _as_dict(_as_dict(record.get("policy_metadata")).get("verification"))


def _evidence_pack_from_record(record: dict[str, Any]) -> dict[str, Any]:
    evidence_pack = _as_dict(record.get("evidence_pack"))
    if evidence_pack:
        return evidence_pack
    return _as_dict(_as_dict(record.get("policy_metadata")).get("evidence_pack"))


def _record_signal_id(record: dict[str, Any], fallback: str) -> str:
    return (
        _safe_text(record.get("signal_id"))
        or _safe_text(record.get("id"))
        or _safe_text(record.get("session_id"))
        or _safe_text(record.get("manual_session_id"))
        or fallback
    )


def _has_insight_fields(record: dict[str, Any]) -> bool:
    return any(_safe_text(record.get(field)) for field in INSIGHT_FIELDS)


def _int_counts(value: Any) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    counts: dict[str, int] = {}
    for key, raw_count in value.items():
        try:
            count = int(raw_count or 0)
        except (TypeError, ValueError):
            continue
        counts[_safe_text(key)] = count
    return counts


def _model_provider(record: dict[str, Any]) -> str:
    produced_by_model = _as_dict(record.get("produced_by_model"))
    if produced_by_model:
        return _safe_text(produced_by_model.get("provider"))
    return _safe_text(record.get("actual_provider")) or _safe_text(record.get("provider_used"))


def _model_id(record: dict[str, Any]) -> str:
    produced_by_model = _as_dict(record.get("produced_by_model"))
    if produced_by_model:
        return _safe_text(produced_by_model.get("model_id"))
    return _safe_text(record.get("model_used"))


def _counts(values: list[str]) -> dict[str, int]:
    return dict(sorted(Counter(value or "missing" for value in values).items()))


def _source_text_field_counts(record: dict[str, Any], evidence_pack: dict[str, Any]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for field in SOURCE_TEXT_FIELDS:
        if _safe_text(record.get(field)):
            counts[field] += 1
        if _safe_text(evidence_pack.get(field)):
            counts[f"evidence_pack.{field}"] += 1
    for item in evidence_pack.get("evidence_items") or []:
        if not isinstance(item, dict):
            continue
        source_field = _safe_text(item.get("source_field")).lower()
        kind = _safe_text(item.get("kind")).lower()
        if source_field in SOURCE_TEXT_EVIDENCE_FIELDS:
            counts[f"evidence_item.source_field.{source_field}"] += 1
        if kind in {"source_excerpt", "primary_excerpt", "full_text", "article_body"}:
            counts[f"evidence_item.kind.{kind}"] += 1
    return dict(sorted(counts.items()))


def _has_source_excerpt(evidence_pack: dict[str, Any]) -> bool:
    if _safe_text(evidence_pack.get("source_excerpt")):
        return True
    for item in evidence_pack.get("evidence_items") or []:
        if not isinstance(item, dict):
            continue
        if _safe_text(item.get("provenance")).lower() == "source_excerpt":
            return True
        if _safe_text(item.get("kind")).lower() in {"source_excerpt", "primary_excerpt"}:
            return True
    return False


def _row_from_record(
    *,
    source: str,
    path: Path,
    root: Path,
    record: dict[str, Any],
    fallback_id: str,
) -> ClaimOriginSupportRow | None:
    if not _has_insight_fields(record):
        return None

    evidence_pack = _evidence_pack_from_record(record)
    if not isinstance(evidence_pack.get("evidence_items"), list):
        return None

    claims = extract_claims_from_insight(record)
    if not claims:
        return None

    claim_results = verify_claims_against_evidence(claims, evidence_pack)
    support_counts = Counter(_safe_text(claim.get("support_level")) or "unknown" for claim in claim_results)
    origin_counts = Counter(_safe_text(claim.get("origin")) or "missing" for claim in claim_results)
    token_only_inferred_count = sum(
        1
        for claim in claim_results
        if claim.get("support_level") == "inferred"
        and "matched_evidence_without_source_span" in (claim.get("verification_notes") or [])
    )
    source_span_count = sum(1 for claim in claim_results if isinstance(claim.get("source_span"), dict))
    verification = _verification_from_record(record)
    signal_id = _record_signal_id(record, fallback_id)
    evidence_items = [item for item in evidence_pack.get("evidence_items") or [] if isinstance(item, dict)]
    source_text_field_counts = _source_text_field_counts(record, evidence_pack)

    return ClaimOriginSupportRow(
        source=source,
        path=_relative_path(path, root),
        record_id=signal_id,
        signal_id=signal_id,
        signal_source=_safe_text(record.get("source")) or _safe_text(evidence_pack.get("source_type")),
        generation_mode=_safe_text(record.get("generation_mode")),
        provider=_model_provider(record),
        model=_model_id(record),
        summary_provenance=_safe_text(evidence_pack.get("summary_provenance")),
        evidence_item_provenance_counts=_counts(
            [_safe_text(item.get("provenance")) for item in evidence_items]
        ),
        evidence_item_source_field_counts=_counts(
            [_safe_text(item.get("source_field")) for item in evidence_items]
        ),
        has_source_excerpt=_has_source_excerpt(evidence_pack),
        has_full_text_like_field=bool(source_text_field_counts),
        source_text_field_counts=source_text_field_counts,
        evidence_item_count=len(evidence_items),
        existing_verification_status=_safe_text(verification.get("verification_status")),
        claim_count=len(claim_results),
        support_counts=dict(sorted(support_counts.items())),
        origin_counts=dict(sorted(origin_counts.items())),
        direct_supported_count=support_counts.get("directly_supported", 0),
        quoted_count=origin_counts.get("quoted", 0),
        inferred_count=origin_counts.get("inferred", 0),
        token_only_inferred_count=token_only_inferred_count,
        source_span_count=source_span_count,
        existing_claim_support_summary=_int_counts(verification.get("claim_support_summary")),
    )


def scan_signal_file(path: Path, *, root: Path, source: str = "signal_file") -> list[ClaimOriginSupportRow]:
    payload = _read_json(path) if path.exists() else None
    if isinstance(payload, dict) and isinstance(payload.get("signals"), list):
        records = payload["signals"]
    else:
        records = payload if isinstance(payload, list) else []
    rows: list[ClaimOriginSupportRow] = []
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            continue
        row = _row_from_record(
            source=source,
            path=path,
            root=root,
            record=record,
            fallback_id=str(index + 1),
        )
        if row is not None:
            rows.append(row)
    return rows


def scan_manual_sessions_dir(path: Path, *, root: Path) -> list[ClaimOriginSupportRow]:
    if not path.exists():
        return []

    rows: list[ClaimOriginSupportRow] = []
    for file_path in sorted(path.glob("*.json")):
        if file_path.name == "index.json":
            continue
        payload = _read_json(file_path)
        if not isinstance(payload, dict):
            continue
        row = _row_from_record(
            source="manual_session",
            path=file_path,
            root=root,
            record=payload,
            fallback_id=file_path.stem,
        )
        if row is not None:
            rows.append(row)
    return rows


def summarize_rows(rows: list[ClaimOriginSupportRow]) -> dict[str, Any]:
    source_counts = Counter(row.source for row in rows)
    signal_source_counts = Counter(row.signal_source or "missing" for row in rows)
    generation_mode_counts = Counter(row.generation_mode or "missing" for row in rows)
    provider_counts = Counter(row.provider or "missing" for row in rows)
    summary_provenance_counts = Counter(row.summary_provenance or "missing" for row in rows)
    evidence_item_provenance_counts: Counter[str] = Counter()
    evidence_item_source_field_counts: Counter[str] = Counter()
    source_text_field_counts: Counter[str] = Counter()
    support_counts: Counter[str] = Counter()
    origin_counts: Counter[str] = Counter()
    for row in rows:
        support_counts.update(row.support_counts)
        origin_counts.update(row.origin_counts)
        evidence_item_provenance_counts.update(row.evidence_item_provenance_counts)
        evidence_item_source_field_counts.update(row.evidence_item_source_field_counts)
        source_text_field_counts.update(row.source_text_field_counts)

    return {
        "record_count": len(rows),
        "claim_count": sum(row.claim_count for row in rows),
        "direct_supported_count": sum(row.direct_supported_count for row in rows),
        "quoted_count": sum(row.quoted_count for row in rows),
        "inferred_count": sum(row.inferred_count for row in rows),
        "token_only_inferred_count": sum(row.token_only_inferred_count for row in rows),
        "source_span_count": sum(row.source_span_count for row in rows),
        "source_counts": dict(sorted(source_counts.items())),
        "signal_source_counts": dict(sorted(signal_source_counts.items())),
        "generation_mode_counts": dict(sorted(generation_mode_counts.items())),
        "provider_counts": dict(sorted(provider_counts.items())),
        "summary_provenance_counts": dict(sorted(summary_provenance_counts.items())),
        "evidence_item_provenance_counts": dict(sorted(evidence_item_provenance_counts.items())),
        "evidence_item_source_field_counts": dict(sorted(evidence_item_source_field_counts.items())),
        "records_with_source_excerpt": sum(1 for row in rows if row.has_source_excerpt),
        "records_with_full_text_like_field": sum(1 for row in rows if row.has_full_text_like_field),
        "source_text_field_counts": dict(sorted(source_text_field_counts.items())),
        "evidence_item_count": sum(row.evidence_item_count for row in rows),
        "support_counts": dict(sorted(support_counts.items())),
        "origin_counts": dict(sorted(origin_counts.items())),
    }


def build_claim_origin_support_report(
    *,
    signal_files: list[Path] | None = None,
    manual_sessions_dir: Path = DEFAULT_MANUAL_SESSIONS_DIR,
    include_rows: bool = True,
    root: Path = REPO_ROOT,
) -> dict[str, Any]:
    rows: list[ClaimOriginSupportRow] = []
    for index, signal_file in enumerate(signal_files or list(DEFAULT_SIGNAL_FILES)):
        rows.extend(scan_signal_file(signal_file, root=root, source=f"signal_file_{index + 1}"))
    rows.extend(scan_manual_sessions_dir(manual_sessions_dir, root=root))

    return {
        "report_boundary": {
            "mode": "read_only",
            "writes_data": False,
            "regenerates_llm_output": False,
            "hard_enforcement": False,
            "interpretation": (
                "This report rebuilds claim extraction and claim verification from stored "
                "insight text plus stored evidence packs. It measures source-span support "
                "impact only; it does not update records or prove external factual truth."
            ),
        },
        "paths": {
            "signal_files": [str(path) for path in (signal_files or list(DEFAULT_SIGNAL_FILES))],
            "manual_sessions_dir": str(manual_sessions_dir),
        },
        "summary": summarize_rows(rows),
        "rows": [row.to_dict() for row in rows] if include_rows else [],
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only claim origin/source-span support report. Rebuilds claim "
            "verification from local stored insight text and evidence packs."
        )
    )
    parser.add_argument(
        "--signal-file",
        action="append",
        default=[],
        help="Signal JSON file to scan. Repeat to include multiple files.",
    )
    parser.add_argument("--manual-sessions-dir", default=str(DEFAULT_MANUAL_SESSIONS_DIR))
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--summary-only", action="store_true")
    return parser.parse_args()


def _signal_files_from_args(values: list[str]) -> list[Path] | None:
    files = [Path(value).resolve() for value in values if _safe_text(value)]
    return files or None


def _print_text_report(report: dict[str, Any], *, summary_only: bool = False) -> None:
    summary = report["summary"]
    print("[claim-origin] scope: read-only local source-span support report", flush=True)
    print(
        "[claim-origin] records: "
        f"{summary['record_count']} claims={summary['claim_count']} "
        f"quoted={summary['quoted_count']} inferred={summary['inferred_count']} "
        f"token_only_inferred={summary['token_only_inferred_count']}",
        flush=True,
    )
    print(
        "[claim-origin] support: "
        + ", ".join(f"{key}={value}" for key, value in summary["support_counts"].items()),
        flush=True,
    )
    print(
        "[claim-origin] sample provenance: "
        f"generation={summary['generation_mode_counts']} "
        f"summary_provenance={summary['summary_provenance_counts']} "
        f"evidence_provenance={summary['evidence_item_provenance_counts']}",
        flush=True,
    )
    print(
        "[claim-origin] source text availability: "
        f"source_excerpt_records={summary['records_with_source_excerpt']} "
        f"full_text_like_records={summary['records_with_full_text_like_field']} "
        f"source_text_fields={summary['source_text_field_counts']}",
        flush=True,
    )
    if summary_only:
        return

    for row in report["rows"]:
        if row["token_only_inferred_count"] == 0 and row["direct_supported_count"] == 0:
            continue
        print(
            f"- {row['record_id']} claims={row['claim_count']} "
            f"direct={row['direct_supported_count']} quoted={row['quoted_count']} "
            f"token_only_inferred={row['token_only_inferred_count']} "
            f"generation={row['generation_mode'] or 'missing'} "
            f"summary_provenance={row['summary_provenance'] or 'missing'} "
            f"source_excerpt={row['has_source_excerpt']} "
            f"full_text_like={row['has_full_text_like_field']} path={row['path']}",
            flush=True,
        )


def main() -> int:
    args = _parse_args()
    report = build_claim_origin_support_report(
        signal_files=_signal_files_from_args(args.signal_file),
        manual_sessions_dir=Path(args.manual_sessions_dir).resolve(),
        include_rows=not args.summary_only,
    )
    if args.format == "json":
        print(json.dumps(report, indent=2, sort_keys=True), flush=True)
    else:
        _print_text_report(report, summary_only=args.summary_only)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
