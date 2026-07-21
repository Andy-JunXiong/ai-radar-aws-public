from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from dataclasses import replace
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
DEFAULT_CLASSIFICATION_OVERRIDES_PATH = (
    BACKEND_ROOT / "data" / "settings" / "project_takeaway_a1_classification_overrides.json"
)

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.project_intelligence_service import PROJECT_IMPROVEMENTS_DIR  # noqa: E402
from app.services.verification_metadata_reader import (  # noqa: E402
    build_action_eligibility_summary,
    get_blocked_downstream_actions,
    get_claim_support_summary,
    get_verification_status,
    get_verified_insight_object,
    has_project_takeaway_verification_context,
)


KNOWN_CANDIDATE_SOURCES = {
    "verified_insight",
    "knowledge_convergence",
    "signal_completion",
    "unverified_manual_entry",
    "manual_project_takeaway_override",
}

REVIEW_STATUSES = {
    "candidate",
    "confirmed",
    "rejected",
    "dismissed",
    "watch",
    "action",
}

TEST_OR_LEGACY_SCOPES = {
    "local_test_data_only",
    "legacy_fixture_or_demo_data",
    "test_data",
    "fixture",
    "demo_data",
}

METADATA_CLEANUP_CODES = {
    "missing_candidate_source",
    "missing_verification_context",
    "signal_completion_not_normalized",
}

CLASSIFICATION_PRIORITY_ORDER = {
    "p1_reviewed_record": 1,
    "p2_new_record": 2,
    "p3_partial_metadata": 3,
    "p4_inspect": 4,
}

OVERRIDE_TEST_OR_LEGACY_CLASSIFICATIONS = {
    "test_or_legacy",
    "test_data",
    "legacy_test_data",
    "legacy_fixture_or_demo_data",
}


@dataclass(frozen=True)
class ProjectTakeawayGap:
    code: str
    severity: str
    project_id: str
    signal_id: str
    status: str
    candidate_source: str
    message: str
    data_scope: str = "production_like"
    data_bucket: str = "production_like"
    signal_title: str = ""
    project_name: str = ""
    saved_at: str = ""

    @property
    def report_severity(self) -> str:
        if self.data_bucket == "test_or_legacy" and self.severity == "error":
            return "info"
        return self.severity

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "severity": self.severity,
            "report_severity": self.report_severity,
            "project_id": self.project_id,
            "signal_id": self.signal_id,
            "status": self.status,
            "candidate_source": self.candidate_source,
            "data_scope": self.data_scope,
            "data_bucket": self.data_bucket,
            "signal_title": self.signal_title,
            "project_name": self.project_name,
            "saved_at": self.saved_at,
            "message": self.message,
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


def _is_manual_override(item: dict[str, Any], verification: dict[str, Any]) -> bool:
    return bool(verification.get("manual_project_takeaway_override")) or _safe_text(
        item.get("candidate_source")
    ) == "manual_project_takeaway_override"


def _positive_claim_support_keys(verification: dict[str, Any]) -> list[str]:
    claim_support = get_claim_support_summary(verification)
    positive_keys = {
        "supported",
        "directly_supported",
        "partially_supported",
        "verified",
        "verified_with_limitations",
    }
    return sorted(
        key
        for key, value in claim_support.items()
        if key.strip().lower() in positive_keys and _safe_int(value) > 0
    )


def _manual_override_value(item: dict[str, Any], verification: dict[str, Any], key: str) -> str:
    return _safe_text(item.get(key)) or _safe_text(verification.get(key))


def _data_scope_value(item: dict[str, Any], verification: dict[str, Any]) -> str:
    for key in [
        "data_scope",
        "record_scope",
        "manual_override_scope",
        "source_scope",
        "data_purpose",
    ]:
        value = _safe_text(item.get(key)) or _safe_text(verification.get(key))
        if value:
            return value.lower()
    return ""


def _classify_data_bucket(
    item: dict[str, Any],
    verification: dict[str, Any],
    *,
    candidate_source: str,
    has_context: bool,
) -> tuple[str, str]:
    data_scope = _data_scope_value(item, verification)
    if data_scope in TEST_OR_LEGACY_SCOPES:
        return data_scope, "test_or_legacy"
    if not candidate_source or not has_context:
        return data_scope or "needs_classification", "needs_classification"
    return data_scope or "production_like", "production_like"


def analyze_project_takeaway_items(
    items: list[dict[str, Any]],
    *,
    project_id: str,
) -> list[ProjectTakeawayGap]:
    gaps: list[ProjectTakeawayGap] = []

    for item in items:
        if not isinstance(item, dict):
            continue

        signal_id = _safe_text(item.get("signal_id")) or "unknown"
        signal_title = _safe_text(item.get("signal_title"))
        project_name = _safe_text(item.get("project_name"))
        saved_at = _safe_text(item.get("saved_at"))
        status = _safe_text(item.get("status")).lower()
        candidate_source = _safe_text(item.get("candidate_source"))
        verification = _as_dict(item.get("verification_metadata"))
        verification_status = get_verification_status(verification)
        has_context = has_project_takeaway_verification_context(verification)
        blocked_actions = set(get_blocked_downstream_actions(verification))
        action_eligibility = _as_dict(item.get("action_eligibility")) or build_action_eligibility_summary(verification)
        project_takeaway_gate = _as_dict(action_eligibility.get("project_takeaway_candidate"))
        low_risk_action_gate = _as_dict(action_eligibility.get("low_risk_action_candidate"))
        manual_override = _is_manual_override(item, verification)
        unverified_manual = candidate_source == "unverified_manual_entry" or verification_status == "unverified_manual_entry"
        item_gap_start = len(gaps)

        if not candidate_source:
            gaps.append(
                ProjectTakeawayGap(
                    code="missing_candidate_source",
                    severity="warning",
                    project_id=project_id,
                    signal_id=signal_id,
                    status=status,
                    candidate_source=candidate_source,
                    message="Project Takeaway item has no candidate_source, so its review boundary is ambiguous.",
                )
            )
        elif candidate_source not in KNOWN_CANDIDATE_SOURCES:
            gaps.append(
                ProjectTakeawayGap(
                    code="unknown_candidate_source",
                    severity="warning",
                    project_id=project_id,
                    signal_id=signal_id,
                    status=status,
                    candidate_source=candidate_source,
                    message=f"candidate_source is not one of the known Project Takeaway source categories: {candidate_source}",
                )
            )

        if not has_context:
            gaps.append(
                ProjectTakeawayGap(
                    code="missing_verification_context",
                    severity="error" if status in REVIEW_STATUSES else "warning",
                    project_id=project_id,
                    signal_id=signal_id,
                    status=status,
                    candidate_source=candidate_source,
                    message="Item has no Project Takeaway verification context.",
                )
            )

        if (
            candidate_source == "signal_completion"
            and not has_context
            and verification_status != "unverified_manual_entry"
        ):
            gaps.append(
                ProjectTakeawayGap(
                    code="signal_completion_not_normalized",
                    severity="error",
                    project_id=project_id,
                    signal_id=signal_id,
                    status=status,
                    candidate_source=candidate_source,
                    message="Signal completion item without verification context should be normalized to unverified_manual_entry.",
                )
            )

        if (
            unverified_manual and not bool(verification.get("verification_required"))
        ):
            gaps.append(
                ProjectTakeawayGap(
                    code="unverified_manual_missing_required_flag",
                    severity="error",
                    project_id=project_id,
                    signal_id=signal_id,
                    status=status,
                    candidate_source=candidate_source,
                    message="unverified_manual_entry must carry verification_required=true.",
                )
            )

        if (
            unverified_manual and bool(project_takeaway_gate.get("allowed"))
        ):
            gaps.append(
                ProjectTakeawayGap(
                    code="unverified_manual_allows_project_takeaway",
                    severity="error",
                    project_id=project_id,
                    signal_id=signal_id,
                    status=status,
                    candidate_source=candidate_source,
                    message="unverified_manual_entry should not be eligible as a clean Project Takeaway candidate.",
                )
            )

        positive_claim_support = _positive_claim_support_keys(verification) if unverified_manual else []
        if positive_claim_support:
            gaps.append(
                ProjectTakeawayGap(
                    code="unverified_manual_has_claim_support",
                    severity="error",
                    project_id=project_id,
                    signal_id=signal_id,
                    status=status,
                    candidate_source=candidate_source,
                    message=(
                        "unverified_manual_entry must not carry clean claim-support semantics: "
                        + ", ".join(positive_claim_support)
                    ),
                )
            )

        verified_insight = get_verified_insight_object(verification)
        if unverified_manual and _safe_text(verified_insight.get("status")).lower() in {
            "verified",
            "verified_with_limitations",
        }:
            gaps.append(
                ProjectTakeawayGap(
                    code="unverified_manual_has_verified_insight_status",
                    severity="error",
                    project_id=project_id,
                    signal_id=signal_id,
                    status=status,
                    candidate_source=candidate_source,
                    message="unverified_manual_entry must not embed a clean verified_insight status.",
                )
            )

        if manual_override:
            if not _manual_override_value(item, verification, "manual_override_note"):
                gaps.append(
                    ProjectTakeawayGap(
                        code="manual_override_missing_note",
                        severity="error",
                        project_id=project_id,
                        signal_id=signal_id,
                        status=status,
                        candidate_source=candidate_source,
                        message="Manual Project Takeaway override requires a reviewer note.",
                    )
                )
            if not _manual_override_value(item, verification, "manual_override_expected_outcome"):
                gaps.append(
                    ProjectTakeawayGap(
                        code="manual_override_missing_expected_outcome",
                        severity="error",
                        project_id=project_id,
                        signal_id=signal_id,
                        status=status,
                        candidate_source=candidate_source,
                        message="Manual Project Takeaway override requires an expected outcome.",
                    )
                )
            if candidate_source != "manual_project_takeaway_override" and not _safe_text(
                verification.get("manual_override_type")
            ):
                gaps.append(
                    ProjectTakeawayGap(
                        code="manual_override_missing_audit_marker",
                        severity="warning",
                        project_id=project_id,
                        signal_id=signal_id,
                        status=status,
                        candidate_source=candidate_source,
                        message="Manual override should carry candidate_source or manual_override_type audit metadata.",
                    )
                )

        if _safe_text(item.get("review_outcome")).lower() == "action_completed":
            gaps.append(
                ProjectTakeawayGap(
                    code="action_completed_stored_as_review_outcome",
                    severity="error",
                    project_id=project_id,
                    signal_id=signal_id,
                    status=status,
                    candidate_source=candidate_source,
                    message="action_completed is an Action lifecycle state, not a Project Takeaway review outcome.",
                )
            )

        if (
            candidate_source == "knowledge_convergence"
            or bool(verification.get("knowledge_convergence"))
            or verification_status == "knowledge_convergence_review_candidate"
        ):
            if "low_risk_action_candidate" not in blocked_actions:
                gaps.append(
                    ProjectTakeawayGap(
                        code="knowledge_convergence_action_not_blocked",
                        severity="error",
                        project_id=project_id,
                        signal_id=signal_id,
                        status=status,
                        candidate_source=candidate_source,
                        message="knowledge_convergence_review_candidate should block low-risk Action by default.",
                    )
                )

        if "project_takeaway_candidate" in blocked_actions and status in {"candidate", "confirmed"} and not manual_override:
            gaps.append(
                ProjectTakeawayGap(
                    code="blocked_project_takeaway_stored_as_reviewable",
                    severity="error",
                    project_id=project_id,
                    signal_id=signal_id,
                    status=status,
                    candidate_source=candidate_source,
                    message="Item is reviewable/confirmed while verification blocks project_takeaway_candidate.",
                )
            )

        if (
            "low_risk_action_candidate" in blocked_actions
            and status == "action"
            and not manual_override
            and not bool(low_risk_action_gate.get("allowed"))
        ):
            gaps.append(
                ProjectTakeawayGap(
                    code="blocked_low_risk_action_stored_as_action",
                    severity="error",
                    project_id=project_id,
                    signal_id=signal_id,
                    status=status,
                    candidate_source=candidate_source,
                    message="Item is an Action while verification blocks low-risk Action and no manual override is present.",
                )
            )

        if len(gaps) > item_gap_start:
            data_scope, data_bucket = _classify_data_bucket(
                item,
                verification,
                candidate_source=candidate_source,
                has_context=has_context,
            )
            for gap_index in range(item_gap_start, len(gaps)):
                gaps[gap_index] = replace(
                    gaps[gap_index],
                    data_scope=data_scope,
                    data_bucket=data_bucket,
                    signal_title=signal_title,
                    project_name=project_name,
                    saved_at=saved_at,
                )

    return gaps


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
        items = payload.get("items") if isinstance(payload, dict) else []
        projects.append((path.stem, [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []))

    return projects


def analyze_project_improvements_dir(project_improvements_dir: Path) -> list[ProjectTakeawayGap]:
    gaps: list[ProjectTakeawayGap] = []
    for project_id, items in load_project_improvement_items(project_improvements_dir):
        gaps.extend(analyze_project_takeaway_items(items, project_id=project_id))
    return gaps


def load_classification_overrides(path: Path | None = None) -> dict[str, dict[str, Any]]:
    override_path = path or DEFAULT_CLASSIFICATION_OVERRIDES_PATH
    if not override_path.exists():
        return {}

    try:
        payload = json.loads(override_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    raw_decisions = payload.get("decisions") if isinstance(payload, dict) else []
    if not isinstance(raw_decisions, list):
        return {}

    overrides: dict[str, dict[str, Any]] = {}
    for raw_decision in raw_decisions:
        if not isinstance(raw_decision, dict):
            continue
        signal_id = _safe_text(raw_decision.get("signal_id") or raw_decision.get("decision_group_id"))
        if not signal_id:
            continue
        overrides[signal_id] = {
            "classification": _safe_text(raw_decision.get("classification")),
            "data_scope": _safe_text(raw_decision.get("data_scope")) or "test_data",
            "reviewer": _safe_text(raw_decision.get("reviewer")),
            "reviewed_at": _safe_text(raw_decision.get("reviewed_at")),
            "note": _safe_text(raw_decision.get("note")),
        }
    return overrides


def apply_classification_overrides(
    gaps: list[ProjectTakeawayGap],
    overrides: dict[str, dict[str, Any]],
) -> list[ProjectTakeawayGap]:
    updated: list[ProjectTakeawayGap] = []
    for gap in gaps:
        decision = overrides.get(gap.signal_id)
        classification = _safe_text(decision.get("classification") if decision else "").lower()
        if classification in OVERRIDE_TEST_OR_LEGACY_CLASSIFICATIONS:
            updated.append(
                replace(
                    gap,
                    data_bucket="test_or_legacy",
                    data_scope=_safe_text(decision.get("data_scope")) or "test_data",
                )
            )
            continue
        updated.append(gap)
    return updated


def summarize_project_takeaway_gaps(
    gaps: list[ProjectTakeawayGap],
    *,
    classification_overrides: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    bucket_counts = Counter(gap.data_bucket for gap in gaps)
    code_counts = Counter(gap.code for gap in gaps)
    report_severity_counts = Counter(gap.report_severity for gap in gaps)
    candidate_source_counts = Counter(gap.candidate_source or "missing" for gap in gaps)
    metadata_cleanup_counts = {
        code: code_counts.get(code, 0)
        for code in sorted(METADATA_CLEANUP_CODES)
        if code_counts.get(code, 0)
    }
    needs_classification_signals = {
        f"{gap.project_id}:{gap.signal_id}"
        for gap in gaps
        if gap.data_bucket == "needs_classification"
    }
    production_like_error_signals = {
        f"{gap.project_id}:{gap.signal_id}"
        for gap in gaps
        if gap.data_bucket == "production_like" and gap.report_severity == "error"
    }
    classification_queue = build_classification_queue(gaps)
    decision_queue = build_classification_decision_queue(gaps)
    override_count = len(classification_overrides or {})

    return {
        "gap_count": len(gaps),
        "bucket_counts": dict(sorted(bucket_counts.items())),
        "code_counts": dict(sorted(code_counts.items())),
        "report_severity_counts": dict(sorted(report_severity_counts.items())),
        "candidate_source_counts": dict(sorted(candidate_source_counts.items())),
        "metadata_cleanup_counts": metadata_cleanup_counts,
        "needs_classification_record_count": len(needs_classification_signals),
        "classification_queue_record_count": len(classification_queue),
        "classification_decision_group_count": len(decision_queue),
        "classification_override_count": override_count,
        "production_like_error_record_count": len(production_like_error_signals),
        "advisory_cleanup_ready": len(production_like_error_signals) == 0 and len(needs_classification_signals) == 0,
    }


def build_repair_proposal(gaps: list[ProjectTakeawayGap]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[ProjectTakeawayGap]] = {}
    for gap in gaps:
        if gap.data_bucket != "test_or_legacy":
            continue
        grouped.setdefault((gap.project_id, gap.signal_id), []).append(gap)

    proposals: list[dict[str, Any]] = []
    for (project_id, signal_id), record_gaps in sorted(grouped.items()):
        gap_codes = sorted({gap.code for gap in record_gaps})
        signal_titles = sorted({gap.signal_title for gap in record_gaps if gap.signal_title})
        project_names = sorted({gap.project_name for gap in record_gaps if gap.project_name})
        data_scopes = sorted({gap.data_scope for gap in record_gaps if gap.data_scope})

        proposals.append(
            {
                "project_id": project_id,
                "project_name": project_names[0] if len(project_names) == 1 else ",".join(project_names),
                "signal_id": signal_id,
                "signal_title": signal_titles[0] if len(signal_titles) == 1 else ",".join(signal_titles),
                "gap_codes": gap_codes,
                "proposed_metadata_patch": {
                    "data_scope": data_scopes[0] if len(data_scopes) == 1 else "test_data",
                    "record_scope": "legacy_fixture_or_demo_data",
                    "a1_classification": "test_or_legacy",
                },
                "write_action": "dry_run_only",
                "safety_note": "Do not add verified_insight or claim-support metadata to test/legacy records.",
            }
        )

    return proposals


def build_classification_queue(gaps: list[ProjectTakeawayGap]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[ProjectTakeawayGap]] = {}
    for gap in gaps:
        if gap.data_bucket != "needs_classification":
            continue
        grouped.setdefault((gap.project_id, gap.signal_id), []).append(gap)

    rows: list[dict[str, Any]] = []
    for (project_id, signal_id), record_gaps in sorted(grouped.items()):
        statuses = sorted({gap.status or "n/a" for gap in record_gaps})
        candidate_sources = sorted({gap.candidate_source or "missing" for gap in record_gaps})
        gap_codes = sorted({gap.code for gap in record_gaps})
        report_severities = sorted({gap.report_severity for gap in record_gaps})
        status = statuses[0] if len(statuses) == 1 else ",".join(statuses)
        classification_hint = _classification_hint(status=status, gap_codes=gap_codes)
        priority = _classification_priority(classification_hint, report_severities)
        signal_titles = sorted({gap.signal_title for gap in record_gaps if gap.signal_title})
        project_names = sorted({gap.project_name for gap in record_gaps if gap.project_name})
        saved_at_values = sorted({gap.saved_at for gap in record_gaps if gap.saved_at})

        rows.append(
            {
                "queue_id": f"{project_id}:{signal_id}",
                "decision_group_id": signal_id,
                "project_id": project_id,
                "project_name": project_names[0] if len(project_names) == 1 else ",".join(project_names),
                "signal_id": signal_id,
                "signal_title": signal_titles[0] if len(signal_titles) == 1 else ",".join(signal_titles),
                "status": status,
                "candidate_source": candidate_sources[0] if len(candidate_sources) == 1 else ",".join(candidate_sources),
                "gap_codes": gap_codes,
                "report_severities": report_severities,
                "classification_hint": classification_hint,
                "priority": priority,
                "suggested_classification": _suggested_classification(classification_hint),
                "recommended_next_action": _recommended_next_action(classification_hint),
                "repair_policy": _repair_policy(classification_hint),
                "saved_at": saved_at_values[-1] if saved_at_values else "",
            }
        )

    return sorted(
        rows,
        key=lambda row: (
            CLASSIFICATION_PRIORITY_ORDER.get(str(row["priority"]), 99),
            str(row["project_id"]).lower(),
            str(row["signal_id"]).lower(),
        ),
    )


def build_classification_decision_queue(gaps: list[ProjectTakeawayGap]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in build_classification_queue(gaps):
        grouped.setdefault(str(row["decision_group_id"]), []).append(row)

    decision_rows: list[dict[str, Any]] = []
    for signal_id, rows in grouped.items():
        priorities = sorted({str(row["priority"]) for row in rows}, key=lambda value: CLASSIFICATION_PRIORITY_ORDER.get(value, 99))
        hints = sorted({str(row["classification_hint"]) for row in rows})
        suggested = sorted({str(row["suggested_classification"]) for row in rows})
        actions = sorted({str(row["recommended_next_action"]) for row in rows})
        titles = sorted({str(row["signal_title"]) for row in rows if row.get("signal_title")})

        decision_rows.append(
            {
                "decision_group_id": signal_id,
                "signal_id": signal_id,
                "signal_title": titles[0] if len(titles) == 1 else ",".join(titles),
                "priority": priorities[0] if priorities else "p4_inspect",
                "record_count": len(rows),
                "project_ids": sorted({str(row["project_id"]) for row in rows}),
                "statuses": sorted({str(row["status"]) for row in rows}),
                "classification_hints": hints,
                "suggested_classifications": suggested,
                "recommended_next_actions": actions,
                "repair_policy": "classify_group_before_any_metadata_repair",
                "queue_ids": [str(row["queue_id"]) for row in rows],
            }
        )

    return sorted(
        decision_rows,
        key=lambda row: (
            CLASSIFICATION_PRIORITY_ORDER.get(str(row["priority"]), 99),
            str(row["signal_id"]).lower(),
        ),
    )


def _classification_hint(*, status: str, gap_codes: list[str]) -> str:
    has_missing_source = "missing_candidate_source" in gap_codes
    has_missing_context = "missing_verification_context" in gap_codes
    if has_missing_source and has_missing_context and status in REVIEW_STATUSES:
        return "reviewed_record_missing_metadata"
    if has_missing_source and has_missing_context and status in {"new", "n/a", ""}:
        return "new_record_missing_metadata"
    if has_missing_source:
        return "candidate_source_missing"
    if has_missing_context:
        return "verification_context_missing"
    return "needs_manual_classification"


def _recommended_next_action(classification_hint: str) -> str:
    if classification_hint == "reviewed_record_missing_metadata":
        return "human_classify_before_repair"
    if classification_hint == "new_record_missing_metadata":
        return "classify_as_legacy_or_backlog_before_repair"
    return "inspect_record_before_repair"


def _classification_priority(classification_hint: str, report_severities: list[str]) -> str:
    if classification_hint == "reviewed_record_missing_metadata" or "error" in report_severities:
        return "p1_reviewed_record"
    if classification_hint == "new_record_missing_metadata":
        return "p2_new_record"
    if classification_hint in {"candidate_source_missing", "verification_context_missing"}:
        return "p3_partial_metadata"
    return "p4_inspect"


def _suggested_classification(classification_hint: str) -> str:
    if classification_hint == "reviewed_record_missing_metadata":
        return "legacy_reviewed_record_requires_human_label"
    if classification_hint == "new_record_missing_metadata":
        return "legacy_backlog_or_test_record_requires_human_label"
    if classification_hint == "candidate_source_missing":
        return "candidate_source_repair_candidate"
    if classification_hint == "verification_context_missing":
        return "verification_context_repair_candidate"
    return "manual_inspection_required"


def _repair_policy(classification_hint: str) -> str:
    if classification_hint in {"reviewed_record_missing_metadata", "new_record_missing_metadata"}:
        return "do_not_auto_repair_without_classification"
    return "inspect_before_repair"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Advisory A1 detector for Project Takeaway verification-boundary gaps. It never writes data."
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
        "--fail-on-gaps",
        action="store_true",
        help="Return exit code 1 when gaps are found. Default is advisory exit code 0.",
    )
    parser.add_argument(
        "--classification-overrides",
        default=str(DEFAULT_CLASSIFICATION_OVERRIDES_PATH),
        help="Optional JSON file containing human classification overrides by signal_id.",
    )
    return parser.parse_args()


def _print_text_report(
    gaps: list[ProjectTakeawayGap],
    project_improvements_dir: Path,
    *,
    classification_overrides: dict[str, dict[str, Any]],
) -> None:
    summary = summarize_project_takeaway_gaps(gaps, classification_overrides=classification_overrides)
    classification_queue = build_classification_queue(gaps)
    repair_proposal = build_repair_proposal(gaps)
    bucket_counts = summary["bucket_counts"]
    metadata_cleanup_counts = summary["metadata_cleanup_counts"]
    print(f"[project-takeaway-a1] scanned: {project_improvements_dir}", flush=True)
    print(f"[project-takeaway-a1] gaps: {summary['gap_count']}", flush=True)
    print(
        "[project-takeaway-a1] buckets: "
        f"production_like={bucket_counts.get('production_like', 0)} "
        f"test_or_legacy={bucket_counts.get('test_or_legacy', 0)} "
        f"needs_classification={bucket_counts.get('needs_classification', 0)}",
        flush=True,
    )
    print(
        "[project-takeaway-a1] metadata cleanup: "
        f"missing_candidate_source={metadata_cleanup_counts.get('missing_candidate_source', 0)} "
        f"missing_verification_context={metadata_cleanup_counts.get('missing_verification_context', 0)} "
        f"signal_completion_not_normalized={metadata_cleanup_counts.get('signal_completion_not_normalized', 0)} "
        f"needs_classification_records={summary['needs_classification_record_count']} "
        f"production_like_error_records={summary['production_like_error_record_count']} "
        f"advisory_cleanup_ready={str(summary['advisory_cleanup_ready']).lower()}",
        flush=True,
    )
    if repair_proposal:
        print("[project-takeaway-a1] dry-run repair proposal:", flush=True)
        for row in repair_proposal:
            print(
                f"  - project={row['project_id']} signal={row['signal_id']} "
                f"classification={row['proposed_metadata_patch']['a1_classification']} "
                f"scope={row['proposed_metadata_patch']['data_scope']} action={row['write_action']}",
                flush=True,
            )
    if classification_queue:
        print("[project-takeaway-a1] classification queue:", flush=True)
        for row in classification_queue:
            print(
                f"  - project={row['project_id']} signal={row['signal_id']} "
                f"status={row['status']} source={row['candidate_source']} "
                f"priority={row['priority']} hint={row['classification_hint']} "
                f"classify={row['suggested_classification']} action={row['recommended_next_action']} "
                f"gaps={','.join(row['gap_codes'])}",
                flush=True,
            )
        print("[project-takeaway-a1] decision queue:", flush=True)
        for row in build_classification_decision_queue(gaps):
            print(
                f"  - signal={row['signal_id']} priority={row['priority']} records={row['record_count']} "
                f"projects={','.join(row['project_ids'])} classify={','.join(row['suggested_classifications'])} "
                f"action={','.join(row['recommended_next_actions'])}",
                flush=True,
            )
    for gap in gaps:
        print(
            f"- {gap.report_severity.upper()} {gap.code} "
            f"project={gap.project_id} signal={gap.signal_id} "
            f"status={gap.status or 'n/a'} source={gap.candidate_source or 'n/a'} "
            f"bucket={gap.data_bucket} scope={gap.data_scope}: {gap.message}",
            flush=True,
        )


def main() -> int:
    args = _parse_args()
    project_improvements_dir = Path(args.project_improvements_dir).resolve()
    classification_overrides = load_classification_overrides(Path(args.classification_overrides).resolve())
    raw_gaps = analyze_project_improvements_dir(project_improvements_dir)
    gaps = apply_classification_overrides(raw_gaps, classification_overrides)

    if args.format == "json":
        summary = summarize_project_takeaway_gaps(gaps, classification_overrides=classification_overrides)
        print(
            json.dumps(
                {
                    "project_improvements_dir": str(project_improvements_dir),
                    "gap_count": summary["gap_count"],
                    "bucket_counts": summary["bucket_counts"],
                    "summary": summary,
                    "classification_queue": build_classification_queue(gaps),
                    "classification_decision_queue": build_classification_decision_queue(gaps),
                    "repair_proposal": build_repair_proposal(gaps),
                    "gaps": [gap.to_dict() for gap in gaps],
                },
                indent=2,
                sort_keys=True,
            ),
            flush=True,
        )
    else:
        _print_text_report(
            gaps,
            project_improvements_dir,
            classification_overrides=classification_overrides,
        )

    return 1 if args.fail_on_gaps and gaps else 0


if __name__ == "__main__":
    raise SystemExit(main())
