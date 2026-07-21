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

from app.services.project_intelligence_service import PROJECT_IMPROVEMENTS_DIR  # noqa: E402
from app.services.verification_metadata_reader import (  # noqa: E402
    get_claim_support_summary,
    get_verification_status,
    get_verified_insight_object,
)


WEAK_OR_NEGATIVE_SUPPORT_LEVELS = {
    "inferred",
    "unsupported",
    "contradicted",
}

REVIEWABLE_STATUSES = {
    "candidate",
    "confirmed",
    "watch",
    "action",
}


@dataclass(frozen=True)
class ClaimDependencyAuditRow:
    project_id: str
    signal_id: str
    status: str
    candidate_source: str
    verification_status: str
    claim_link_status: str
    claim_count: int
    linked_claim_id_count: int
    weak_or_negative_claim_count: int
    support_summary: dict[str, int]
    claim_ids: list[str]
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "signal_id": self.signal_id,
            "status": self.status,
            "candidate_source": self.candidate_source,
            "verification_status": self.verification_status,
            "claim_link_status": self.claim_link_status,
            "claim_count": self.claim_count,
            "linked_claim_id_count": self.linked_claim_id_count,
            "weak_or_negative_claim_count": self.weak_or_negative_claim_count,
            "support_summary": self.support_summary,
            "claim_ids": self.claim_ids,
            "message": self.message,
        }


@dataclass(frozen=True)
class ClaimDependencyAuditFilters:
    project_ids: set[str]
    candidate_sources: set[str]
    statuses: set[str]
    only_reviewable: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_ids": sorted(self.project_ids),
            "candidate_sources": sorted(self.candidate_sources),
            "statuses": sorted(self.statuses),
            "only_reviewable": self.only_reviewable,
        }


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _claim_items_from_verification(verification: dict[str, Any]) -> list[dict[str, Any]]:
    verified_insight = get_verified_insight_object(verification)
    claims = verified_insight.get("claims")
    if not isinstance(claims, dict):
        return []
    items = claims.get("items")
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def _support_summary_from_claim_items(claim_items: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for claim in claim_items:
        support_level = _safe_text(claim.get("support_level")).lower() or "unknown"
        counts[support_level] += 1
    return dict(sorted(counts.items()))


def _claim_dependency_key(signal_id: str, claim_id: str) -> str:
    return f"{signal_id}:{claim_id}" if signal_id else claim_id


def _build_row(item: dict[str, Any], *, project_id: str) -> ClaimDependencyAuditRow:
    signal_id = _safe_text(item.get("signal_id")) or "unknown"
    status = _safe_text(item.get("status")).lower()
    candidate_source = _safe_text(item.get("candidate_source"))
    verification = _as_dict(item.get("verification_metadata"))
    verification_status = get_verification_status(verification)
    claim_items = _claim_items_from_verification(verification)
    claim_ids = [
        _claim_dependency_key(signal_id, _safe_text(claim.get("claim_id")))
        for claim in claim_items
        if _safe_text(claim.get("claim_id"))
    ]
    claim_item_support_summary = _support_summary_from_claim_items(claim_items)
    aggregate_support_summary = get_claim_support_summary(verification)
    support_summary = claim_item_support_summary or aggregate_support_summary
    weak_or_negative_claim_count = sum(
        _safe_int(support_summary.get(level))
        for level in WEAK_OR_NEGATIVE_SUPPORT_LEVELS
    )

    if claim_ids:
        claim_link_status = "linked_claims_present"
        message = "Record embeds verified claim items with claim IDs."
    elif aggregate_support_summary:
        claim_link_status = "claim_summary_only"
        message = "Record has aggregate claim support summary but no claim IDs to link."
    else:
        claim_link_status = "no_claim_dependency_data"
        message = "Record does not expose claim dependency data."

    return ClaimDependencyAuditRow(
        project_id=project_id,
        signal_id=signal_id,
        status=status,
        candidate_source=candidate_source,
        verification_status=verification_status,
        claim_link_status=claim_link_status,
        claim_count=len(claim_items) or sum(_safe_int(value) for value in aggregate_support_summary.values()),
        linked_claim_id_count=len(claim_ids),
        weak_or_negative_claim_count=weak_or_negative_claim_count,
        support_summary=dict(sorted(support_summary.items())),
        claim_ids=claim_ids,
        message=message,
    )


def analyze_project_takeaway_claim_dependencies(
    items: list[dict[str, Any]],
    *,
    project_id: str,
    filters: ClaimDependencyAuditFilters | None = None,
) -> list[ClaimDependencyAuditRow]:
    rows: list[ClaimDependencyAuditRow] = []
    for item in items:
        if isinstance(item, dict):
            row = _build_row(item, project_id=project_id)
            if _matches_filters(row, filters):
                rows.append(row)
    return rows


def _matches_filters(
    row: ClaimDependencyAuditRow,
    filters: ClaimDependencyAuditFilters | None,
) -> bool:
    if filters is None:
        return True
    if filters.project_ids and row.project_id not in filters.project_ids:
        return False
    if filters.candidate_sources and row.candidate_source not in filters.candidate_sources:
        return False
    if filters.statuses and row.status not in filters.statuses:
        return False
    if filters.only_reviewable and row.status not in REVIEWABLE_STATUSES:
        return False
    return True


def load_project_improvement_items(project_improvements_dir: Path) -> list[tuple[str, list[dict[str, Any]]]]:
    projects: list[tuple[str, list[dict[str, Any]]]] = []
    if not project_improvements_dir.exists():
        return projects

    for path in sorted(project_improvements_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            projects.append((path.stem, []))
            continue
        project_id = _safe_text(payload.get("project_id")) if isinstance(payload, dict) else ""
        items = payload.get("items") if isinstance(payload, dict) else []
        project_items = [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []
        projects.append((project_id or path.stem, project_items))

    return projects


def analyze_project_improvements_dir(
    project_improvements_dir: Path,
    *,
    filters: ClaimDependencyAuditFilters | None = None,
) -> list[ClaimDependencyAuditRow]:
    rows: list[ClaimDependencyAuditRow] = []
    for project_id, items in load_project_improvement_items(project_improvements_dir):
        rows.extend(analyze_project_takeaway_claim_dependencies(items, project_id=project_id, filters=filters))
    return rows


def summarize_rows(rows: list[ClaimDependencyAuditRow]) -> dict[str, Any]:
    link_status_counts = Counter(row.claim_link_status for row in rows)
    support_level_counts: Counter[str] = Counter()
    for row in rows:
        support_level_counts.update(row.support_summary)

    return {
        "record_count": len(rows),
        "link_status_counts": dict(sorted(link_status_counts.items())),
        "linked_record_count": link_status_counts.get("linked_claims_present", 0),
        "linked_claim_id_count": sum(row.linked_claim_id_count for row in rows),
        "weak_or_negative_claim_count": sum(row.weak_or_negative_claim_count for row in rows),
        "support_level_counts": dict(sorted(support_level_counts.items())),
        "breakdowns": build_linkability_breakdowns(rows),
    }


def _breakdown_key(value: str) -> str:
    return _safe_text(value) or "(missing)"


def _empty_breakdown_entry() -> dict[str, Any]:
    return {
        "record_count": 0,
        "link_status_counts": Counter(),
        "linked_record_count": 0,
        "summary_only_record_count": 0,
        "no_dependency_record_count": 0,
        "linked_claim_id_count": 0,
        "weak_or_negative_claim_count": 0,
        "support_level_counts": Counter(),
    }


def _record_breakdown_row(group: dict[str, Any], row: ClaimDependencyAuditRow) -> None:
    group["record_count"] += 1
    group["link_status_counts"][row.claim_link_status] += 1
    if row.claim_link_status == "linked_claims_present":
        group["linked_record_count"] += 1
    elif row.claim_link_status == "claim_summary_only":
        group["summary_only_record_count"] += 1
    elif row.claim_link_status == "no_claim_dependency_data":
        group["no_dependency_record_count"] += 1
    group["linked_claim_id_count"] += row.linked_claim_id_count
    group["weak_or_negative_claim_count"] += row.weak_or_negative_claim_count
    group["support_level_counts"].update(row.support_summary)


def _finalize_breakdown_entry(group: dict[str, Any]) -> dict[str, Any]:
    record_count = int(group["record_count"])
    linked_record_count = int(group["linked_record_count"])
    return {
        "record_count": record_count,
        "link_status_counts": dict(sorted(group["link_status_counts"].items())),
        "linked_record_count": linked_record_count,
        "summary_only_record_count": int(group["summary_only_record_count"]),
        "no_dependency_record_count": int(group["no_dependency_record_count"]),
        "linked_record_coverage": round(linked_record_count / record_count, 4) if record_count else 0.0,
        "linked_claim_id_count": int(group["linked_claim_id_count"]),
        "weak_or_negative_claim_count": int(group["weak_or_negative_claim_count"]),
        "support_level_counts": dict(sorted(group["support_level_counts"].items())),
    }


def _build_breakdown(rows: list[ClaimDependencyAuditRow], attr: str) -> dict[str, dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = _breakdown_key(str(getattr(row, attr)))
        if key not in groups:
            groups[key] = _empty_breakdown_entry()
        _record_breakdown_row(groups[key], row)
    return {
        key: _finalize_breakdown_entry(group)
        for key, group in sorted(groups.items())
    }


def build_linkability_breakdowns(rows: list[ClaimDependencyAuditRow]) -> dict[str, dict[str, dict[str, Any]]]:
    return {
        "by_project_id": _build_breakdown(rows, "project_id"),
        "by_candidate_source": _build_breakdown(rows, "candidate_source"),
        "by_status": _build_breakdown(rows, "status"),
    }


def _candidate_source_schema_policy(source: str, breakdown: dict[str, Any]) -> dict[str, Any]:
    record_count = int(breakdown.get("record_count") or 0)
    linked_count = int(breakdown.get("linked_record_count") or 0)
    summary_only_count = int(breakdown.get("summary_only_record_count") or 0)
    no_dependency_count = int(breakdown.get("no_dependency_record_count") or 0)

    if record_count == 0:
        policy = "needs_trusted_sample"
        next_step = "Collect a trusted sample before deciding claim dependency handling for this source."
    elif linked_count == record_count:
        policy = "eligible_for_claim_id_schema_probe"
        next_step = "May be included in a narrow depends_on_claim_ids schema probe."
    elif summary_only_count == record_count:
        policy = "requires_claim_item_backfill_or_summary_only_boundary"
        next_step = "Do not require depends_on_claim_ids until claim items are backfilled or summary-only handling is designed."
    elif no_dependency_count == record_count:
        policy = "mark_dependency_unknown_or_exclude_from_claim_dag"
        next_step = "Keep out of claim-level dependency DAGs unless a separate dependency-unknown state is accepted."
    else:
        policy = "requires_source_specific_split_policy"
        next_step = "Split this source by record shape, status, or generation route before schema work."

    return {
        "candidate_source": source,
        "policy": policy,
        "record_count": record_count,
        "linked_record_count": linked_count,
        "summary_only_record_count": summary_only_count,
        "no_dependency_record_count": no_dependency_count,
        "linked_record_coverage": breakdown.get("linked_record_coverage", 0.0),
        "next_step": next_step,
    }


def build_phase2_schema_inputs(rows: list[ClaimDependencyAuditRow]) -> dict[str, Any]:
    by_candidate_source = build_linkability_breakdowns(rows)["by_candidate_source"]
    source_policies = {
        source: _candidate_source_schema_policy(source, breakdown)
        for source, breakdown in by_candidate_source.items()
    }

    def _sources_for_policy(policy: str) -> list[str]:
        return sorted(
            source
            for source, item in source_policies.items()
            if item["policy"] == policy
        )

    return {
        "decision_boundary": "schema_design_input_only",
        "not_for": [
            "schema_migration_approval",
            "cascade_behavior_approval",
            "automatic_backfill",
            "production_metric_claim",
        ],
        "candidate_source_policies": source_policies,
        "eligible_candidate_sources": _sources_for_policy("eligible_for_claim_id_schema_probe"),
        "backfill_or_summary_only_candidate_sources": _sources_for_policy(
            "requires_claim_item_backfill_or_summary_only_boundary"
        ),
        "dependency_unknown_candidate_sources": _sources_for_policy(
            "mark_dependency_unknown_or_exclude_from_claim_dag"
        ),
        "mixed_shape_candidate_sources": _sources_for_policy("requires_source_specific_split_policy"),
    }


def build_phase2_readiness_summary(rows: list[ClaimDependencyAuditRow]) -> dict[str, Any]:
    summary = summarize_rows(rows)
    record_count = summary["record_count"]
    linked_record_count = summary["linked_record_count"]
    summary_only_count = summary["link_status_counts"].get("claim_summary_only", 0)
    no_dependency_count = summary["link_status_counts"].get("no_claim_dependency_data", 0)
    linked_record_coverage = linked_record_count / record_count if record_count else 0.0

    if record_count == 0:
        readiness = "needs_trusted_sample"
        next_step = "Select a trusted dataset or narrower filters before evaluating Phase 2 schema work."
    elif linked_record_count == 0:
        readiness = "not_ready_for_schema_design"
        next_step = "Do not add depends_on_claim_ids yet; the selected records do not expose claim IDs."
    elif linked_record_count < record_count:
        readiness = "needs_backfill_or_source_boundary_design"
        next_step = (
            "Before adding depends_on_claim_ids, design how summary-only and no-dependency records "
            "would be excluded, backfilled, or marked as dependency-unknown."
        )
    else:
        readiness = "ready_for_schema_design_probe"
        next_step = (
            "The selected records expose claim IDs; a narrow schema design probe can be considered, "
            "still without cascade behavior."
        )

    return {
        "decision_boundary": "architecture_readiness_only",
        "not_for": [
            "factual_quality_judgment",
            "production_metric_claim",
            "automatic_review_state_change",
        ],
        "readiness": readiness,
        "selected_record_count": record_count,
        "linked_record_count": linked_record_count,
        "summary_only_record_count": summary_only_count,
        "no_dependency_record_count": no_dependency_count,
        "linked_record_coverage": round(linked_record_coverage, 4),
        "next_step": next_step,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only Project Takeaway claim dependency audit. It measures "
            "claim-ID linkability and never writes project data."
        )
    )
    parser.add_argument(
        "--project-improvements-dir",
        default=str(PROJECT_IMPROVEMENTS_DIR),
        help="Directory containing project improvement JSON files.",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Report format.",
    )
    parser.add_argument(
        "--project-id",
        action="append",
        default=[],
        help="Filter to a project_id. Repeat to include multiple projects.",
    )
    parser.add_argument(
        "--candidate-source",
        action="append",
        default=[],
        help="Filter to a candidate_source. Repeat to include multiple source categories.",
    )
    parser.add_argument(
        "--status",
        action="append",
        default=[],
        help="Filter to a Project Takeaway status. Repeat to include multiple statuses.",
    )
    parser.add_argument(
        "--only-reviewable",
        action="store_true",
        help="Only include statuses with downstream review meaning: candidate, confirmed, watch, action.",
    )
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Print aggregate and breakdown lines without per-record rows in text output.",
    )
    return parser.parse_args()


def _normalize_filter_values(values: list[str]) -> set[str]:
    return {_safe_text(value) for value in values if _safe_text(value)}


def _normalize_lower_filter_values(values: list[str]) -> set[str]:
    return {_safe_text(value).lower() for value in values if _safe_text(value)}


def build_filters(args: argparse.Namespace) -> ClaimDependencyAuditFilters:
    return ClaimDependencyAuditFilters(
        project_ids=_normalize_filter_values(args.project_id),
        candidate_sources=_normalize_filter_values(args.candidate_source),
        statuses=_normalize_lower_filter_values(args.status),
        only_reviewable=bool(args.only_reviewable),
    )


def _print_text_report(
    rows: list[ClaimDependencyAuditRow],
    project_improvements_dir: Path,
    filters: ClaimDependencyAuditFilters,
    *,
    summary_only: bool = False,
) -> None:
    summary = summarize_rows(rows)
    link_status_counts = summary["link_status_counts"]
    readiness = build_phase2_readiness_summary(rows)
    schema_inputs = build_phase2_schema_inputs(rows)
    print(f"[project-takeaway-claim-dependencies] scanned: {project_improvements_dir}", flush=True)
    print(
        "[project-takeaway-claim-dependencies] scope: read-only local measurement; "
        "do not treat local/test fixtures as production judgment",
        flush=True,
    )
    print(f"[project-takeaway-claim-dependencies] filters: {filters.to_dict()}", flush=True)
    print(f"[project-takeaway-claim-dependencies] records: {summary['record_count']}", flush=True)
    print(
        "[project-takeaway-claim-dependencies] linkability: "
        f"linked_claims_present={link_status_counts.get('linked_claims_present', 0)} "
        f"claim_summary_only={link_status_counts.get('claim_summary_only', 0)} "
        f"no_claim_dependency_data={link_status_counts.get('no_claim_dependency_data', 0)}",
        flush=True,
    )
    print(
        "[project-takeaway-claim-dependencies] "
        f"linked_claim_ids={summary['linked_claim_id_count']} "
        f"weak_or_negative_claims={summary['weak_or_negative_claim_count']}",
        flush=True,
    )
    print(
        "[project-takeaway-claim-dependencies] phase2_readiness: "
        f"{readiness['readiness']} coverage={readiness['linked_record_coverage']} "
        f"next_step={readiness['next_step']}",
        flush=True,
    )
    breakdowns = summary["breakdowns"]
    for label, breakdown in [
        ("by_candidate_source", breakdowns["by_candidate_source"]),
        ("by_status", breakdowns["by_status"]),
        ("by_project_id", breakdowns["by_project_id"]),
    ]:
        formatted = " | ".join(
            f"{key}: linked={value['linked_record_count']}/{value['record_count']} "
            f"summary_only={value['summary_only_record_count']} "
            f"no_data={value['no_dependency_record_count']}"
            for key, value in breakdown.items()
        )
        print(f"[project-takeaway-claim-dependencies] {label}: {formatted or 'none'}", flush=True)
    for label, sources in [
        ("eligible_for_claim_id_schema_probe", schema_inputs["eligible_candidate_sources"]),
        ("backfill_or_summary_only", schema_inputs["backfill_or_summary_only_candidate_sources"]),
        ("dependency_unknown_or_exclude", schema_inputs["dependency_unknown_candidate_sources"]),
        ("mixed_shape", schema_inputs["mixed_shape_candidate_sources"]),
    ]:
        print(
            f"[project-takeaway-claim-dependencies] source_policy {label}: "
            f"{', '.join(sources) if sources else 'none'}",
            flush=True,
        )
    if summary_only:
        return
    for row in rows:
        print(
            f"- {row.claim_link_status} project={row.project_id} "
            f"signal={row.signal_id} status={row.status or 'n/a'} "
            f"source={row.candidate_source or 'n/a'} claims={row.linked_claim_id_count}/"
            f"{row.claim_count} weak_or_negative={row.weak_or_negative_claim_count}: "
            f"{row.message}",
            flush=True,
        )


def main() -> int:
    args = _parse_args()
    project_improvements_dir = Path(args.project_improvements_dir).resolve()
    filters = build_filters(args)
    rows = analyze_project_improvements_dir(project_improvements_dir, filters=filters)

    if args.format == "json":
        print(
            json.dumps(
                {
                    "project_improvements_dir": str(project_improvements_dir),
                    "filters": filters.to_dict(),
                    "report_boundary": {
                        "mode": "read_only",
                        "scope": "local_measurement",
                        "writes_data": False,
                        "interpretation": (
                            "Use this report to assess claim-linkability shape only; "
                            "do not treat local/test fixtures as production intelligence judgment."
                        ),
                    },
                    "summary": summarize_rows(rows),
                    "phase2_readiness": build_phase2_readiness_summary(rows),
                    "phase2_schema_inputs": build_phase2_schema_inputs(rows),
                    "rows": [row.to_dict() for row in rows],
                },
                indent=2,
                sort_keys=True,
            ),
            flush=True,
        )
    else:
        _print_text_report(rows, project_improvements_dir, filters, summary_only=bool(args.summary_only))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
