from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES_DIR = REPO_ROOT / "docs" / "evaluation" / "seeded_cases"
DEFAULT_TEMPLATE_CASE_ID = "case-template"
DEFAULT_MIN_ACCEPTED_SEEDS = 20
VALID_STATUSES = {"seed_candidate", "accepted_seed", "retired"}
VALID_SOURCE_BOUNDARIES = {"human_seeded", "trusted_historical", "blocked_action_case"}
EXPECTED_FIELD_KEYS = (
    "verification_status",
    "required_blocked_actions",
    "max_unsupported_or_contradicted_claims",
    "requires_model_provenance",
    "notes",
)
PLACEHOLDER_MARKERS = (
    "replace with",
    "case-template",
)


@dataclass(frozen=True)
class InsightEvalCaseFinding:
    code: str
    severity: str
    path: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "severity": self.severity,
            "path": self.path,
            "message": self.message,
        }


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _relative_path(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)


def build_seed_case_template(
    *,
    case_id: str = DEFAULT_TEMPLATE_CASE_ID,
    status: str = "seed_candidate",
    source_boundary: str = "human_seeded",
) -> dict[str, Any]:
    normalized_status = status if status in VALID_STATUSES else "seed_candidate"
    normalized_source_boundary = (
        source_boundary
        if source_boundary in VALID_SOURCE_BOUNDARIES
        else "human_seeded"
    )
    return {
        "case_id": _safe_text(case_id) or DEFAULT_TEMPLATE_CASE_ID,
        "schema_version": "insight_eval_case.v1",
        "status": normalized_status,
        "source_boundary": normalized_source_boundary,
        "input": {
            "query_or_signal_summary": "Replace with a concise trusted signal or query summary.",
            "source_refs": [
                "Replace with source file, record ID, URL, or human note reference."
            ],
        },
        "expected": {
            "verification_status": "partially_verified",
            "required_blocked_actions": ["low_risk_action_candidate"],
            "max_unsupported_or_contradicted_claims": 0,
            "requires_model_provenance": True,
            "notes": "Replace with the human-owned reason this case belongs in the held-out set.",
        },
    }


def _contains_placeholder(value: Any) -> bool:
    text = _safe_text(value).lower()
    return any(marker in text for marker in PLACEHOLDER_MARKERS)


def _source_refs(payload: dict[str, Any]) -> list[str]:
    input_payload = payload.get("input")
    if not isinstance(input_payload, dict):
        return []
    refs = input_payload.get("source_refs")
    if not isinstance(refs, list):
        return []
    return [_safe_text(ref) for ref in refs if _safe_text(ref)]


def _expected_field_presence(payload: dict[str, Any]) -> set[str]:
    expected = payload.get("expected")
    if not isinstance(expected, dict):
        return set()
    present: set[str] = set()
    for key in EXPECTED_FIELD_KEYS:
        if key not in expected:
            continue
        value = expected.get(key)
        if isinstance(value, str) and not value.strip():
            continue
        if isinstance(value, list) and not value:
            continue
        if value is None:
            continue
        present.add(key)
    return present


def _validate_optional_expected_fields(
    expected: dict[str, Any],
    *,
    rel_path: str,
) -> list[InsightEvalCaseFinding]:
    findings: list[InsightEvalCaseFinding] = []

    if "verification_status" in expected and not isinstance(expected.get("verification_status"), str):
        findings.append(
            InsightEvalCaseFinding(
                code="invalid_expected_verification_status",
                severity="error",
                path=rel_path,
                message="expected.verification_status must be a string when present.",
            )
        )

    if "required_blocked_actions" in expected:
        actions = expected.get("required_blocked_actions")
        if not isinstance(actions, list) or any(not isinstance(action, str) or not action.strip() for action in actions):
            findings.append(
                InsightEvalCaseFinding(
                    code="invalid_expected_required_blocked_actions",
                    severity="error",
                    path=rel_path,
                    message="expected.required_blocked_actions must be a list of non-empty strings when present.",
                )
            )

    if "max_unsupported_or_contradicted_claims" in expected:
        value = expected.get("max_unsupported_or_contradicted_claims")
        if not isinstance(value, int) or value < 0:
            findings.append(
                InsightEvalCaseFinding(
                    code="invalid_expected_max_unsupported_or_contradicted_claims",
                    severity="error",
                    path=rel_path,
                    message="expected.max_unsupported_or_contradicted_claims must be a non-negative integer.",
                )
            )

    if "requires_model_provenance" in expected and not isinstance(expected.get("requires_model_provenance"), bool):
        findings.append(
            InsightEvalCaseFinding(
                code="invalid_expected_requires_model_provenance",
                severity="error",
                path=rel_path,
                message="expected.requires_model_provenance must be a boolean when present.",
            )
        )

    if "notes" in expected and not isinstance(expected.get("notes"), str):
        findings.append(
            InsightEvalCaseFinding(
                code="invalid_expected_notes",
                severity="error",
                path=rel_path,
                message="expected.notes must be a string when present.",
            )
        )

    unknown_fields = sorted(str(key) for key in expected if key not in EXPECTED_FIELD_KEYS)
    if unknown_fields:
        findings.append(
            InsightEvalCaseFinding(
                code="unknown_expected_field",
                severity="error",
                path=rel_path,
                message=f"Unknown expected field(s): {', '.join(unknown_fields)}.",
            )
        )

    return findings


def _validate_optional_input_fields(
    input_payload: dict[str, Any],
    *,
    rel_path: str,
) -> list[InsightEvalCaseFinding]:
    findings: list[InsightEvalCaseFinding] = []
    if "source_refs" in input_payload:
        refs = input_payload.get("source_refs")
        if not isinstance(refs, list) or any(not isinstance(ref, str) or not ref.strip() for ref in refs):
            findings.append(
                InsightEvalCaseFinding(
                    code="invalid_input_source_refs",
                    severity="error",
                    path=rel_path,
                    message="input.source_refs must be a list of non-empty strings when present.",
                )
            )
    return findings


def _accepted_seed_quality_findings(
    payload: dict[str, Any],
    *,
    rel_path: str,
) -> list[InsightEvalCaseFinding]:
    if payload.get("status") != "accepted_seed":
        return []

    findings: list[InsightEvalCaseFinding] = []
    input_payload = payload.get("input") if isinstance(payload.get("input"), dict) else {}
    expected = payload.get("expected") if isinstance(payload.get("expected"), dict) else {}
    refs = _source_refs(payload)

    if _contains_placeholder(payload.get("case_id")):
        findings.append(
            InsightEvalCaseFinding(
                code="accepted_seed_uses_template_case_id",
                severity="error",
                path=rel_path,
                message="accepted_seed cases must replace the template case_id.",
            )
        )

    if _contains_placeholder(input_payload.get("query_or_signal_summary")):
        findings.append(
            InsightEvalCaseFinding(
                code="accepted_seed_has_placeholder_summary",
                severity="error",
                path=rel_path,
                message="accepted_seed cases must replace the template signal summary.",
            )
        )

    if not refs:
        findings.append(
            InsightEvalCaseFinding(
                code="accepted_seed_missing_source_refs",
                severity="error",
                path=rel_path,
                message="accepted_seed cases must include at least one source reference.",
            )
        )
    elif any(_contains_placeholder(ref) for ref in refs):
        findings.append(
            InsightEvalCaseFinding(
                code="accepted_seed_has_placeholder_source_refs",
                severity="error",
                path=rel_path,
                message="accepted_seed source_refs must replace template placeholder text.",
            )
        )

    if not _safe_text(expected.get("notes")):
        findings.append(
            InsightEvalCaseFinding(
                code="accepted_seed_missing_human_notes",
                severity="error",
                path=rel_path,
                message="accepted_seed cases must include notes explaining why this case is trusted.",
            )
        )
    elif _contains_placeholder(expected.get("notes")):
        findings.append(
            InsightEvalCaseFinding(
                code="accepted_seed_has_placeholder_notes",
                severity="error",
                path=rel_path,
                message="accepted_seed notes must replace template placeholder text.",
            )
        )

    return findings


def _validate_case(payload: Any, *, path: Path, root: Path) -> list[InsightEvalCaseFinding]:
    rel_path = _relative_path(path, root)
    findings: list[InsightEvalCaseFinding] = []
    if not isinstance(payload, dict):
        return [
            InsightEvalCaseFinding(
                code="case_not_object",
                severity="error",
                path=rel_path,
                message="Insight eval case must be a JSON object.",
            )
        ]

    required = ["case_id", "schema_version", "status", "source_boundary", "input", "expected"]
    for key in required:
        if key not in payload:
            findings.append(
                InsightEvalCaseFinding(
                    code="missing_required_field",
                    severity="error",
                    path=rel_path,
                    message=f"Missing required field: {key}",
                )
            )

    if payload.get("schema_version") != "insight_eval_case.v1":
        findings.append(
            InsightEvalCaseFinding(
                code="schema_version_mismatch",
                severity="error",
                path=rel_path,
                message="schema_version must be insight_eval_case.v1.",
            )
        )

    if payload.get("status") not in VALID_STATUSES:
        findings.append(
            InsightEvalCaseFinding(
                code="invalid_status",
                severity="error",
                path=rel_path,
                message="status must be seed_candidate, accepted_seed, or retired.",
            )
        )

    if payload.get("source_boundary") not in VALID_SOURCE_BOUNDARIES:
        findings.append(
            InsightEvalCaseFinding(
                code="invalid_source_boundary",
                severity="error",
                path=rel_path,
                message="source_boundary must name a trusted case source category.",
            )
        )

    input_payload = payload.get("input")
    if not isinstance(input_payload, dict) or not _safe_text(input_payload.get("query_or_signal_summary")):
        findings.append(
            InsightEvalCaseFinding(
                code="missing_query_or_signal_summary",
                severity="error",
                path=rel_path,
                message="input.query_or_signal_summary is required.",
            )
        )
    elif not isinstance(input_payload.get("query_or_signal_summary"), str):
        findings.append(
            InsightEvalCaseFinding(
                code="invalid_query_or_signal_summary",
                severity="error",
                path=rel_path,
                message="input.query_or_signal_summary must be a string.",
            )
        )
    else:
        findings.extend(_validate_optional_input_fields(input_payload, rel_path=rel_path))

    expected = payload.get("expected")
    if not isinstance(expected, dict):
        findings.append(
            InsightEvalCaseFinding(
                code="expected_not_object",
                severity="error",
                path=rel_path,
                message="expected must be a JSON object.",
            )
        )
    else:
        findings.extend(_validate_optional_expected_fields(expected, rel_path=rel_path))

    findings.extend(_accepted_seed_quality_findings(payload, rel_path=rel_path))

    return findings


def _safe_positive_int(value: Any, *, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _readiness_summary(
    *,
    accepted_seed_count: int,
    finding_count: int,
    min_accepted_seeds: int,
) -> dict[str, Any]:
    remaining = max(min_accepted_seeds - accepted_seed_count, 0)
    reasons: list[str] = []
    readiness = "needs_seed_cases"

    if finding_count:
        readiness = "schema_fixes_needed"
        reasons.append("Fix schema or accepted-seed guardrail findings before using this set.")
    elif accepted_seed_count >= min_accepted_seeds:
        readiness = "ready_for_deterministic_eval"
        reasons.append("Accepted seed count meets the configured deterministic-eval threshold.")
    elif accepted_seed_count > 0:
        readiness = "partial_seed_set"
        reasons.append(f"Add {remaining} more accepted seed case(s) to reach the configured threshold.")
    else:
        reasons.append("Add human-selected accepted seed cases before running deterministic eval.")

    return {
        "readiness": readiness,
        "min_accepted_seeds": min_accepted_seeds,
        "remaining_accepted_seed_count": remaining,
        "readiness_reasons": reasons,
    }


def check_seed_cases(
    cases_dir: Path,
    *,
    root: Path = REPO_ROOT,
    min_accepted_seeds: int = DEFAULT_MIN_ACCEPTED_SEEDS,
) -> dict[str, Any]:
    min_accepted_seeds = _safe_positive_int(min_accepted_seeds, default=DEFAULT_MIN_ACCEPTED_SEEDS)
    case_paths = sorted(path for path in cases_dir.glob("*.json")) if cases_dir.exists() else []
    findings: list[InsightEvalCaseFinding] = []
    accepted_seed_count = 0
    status_counts: Counter[str] = Counter()
    source_boundary_counts: Counter[str] = Counter()
    accepted_seed_source_boundary_counts: Counter[str] = Counter()
    expected_field_counts: Counter[str] = Counter()
    accepted_seed_expected_field_counts: Counter[str] = Counter()
    case_id_paths: dict[str, list[str]] = {}

    for path in case_paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            findings.append(
                InsightEvalCaseFinding(
                    code="invalid_json",
                    severity="error",
                    path=_relative_path(path, root),
                    message="Case file is not valid JSON.",
                )
            )
            continue
        if isinstance(payload, dict):
            status = _safe_text(payload.get("status"))
            source_boundary = _safe_text(payload.get("source_boundary"))
            case_id = _safe_text(payload.get("case_id"))
            status_counts[status or "unknown"] += 1
            source_boundary_counts[source_boundary or "unknown"] += 1
            if case_id:
                case_id_paths.setdefault(case_id, []).append(_relative_path(path, root))
            expected_fields = _expected_field_presence(payload)
            expected_field_counts.update(expected_fields)
            if status == "accepted_seed":
                accepted_seed_count += 1
                accepted_seed_source_boundary_counts[source_boundary or "unknown"] += 1
                accepted_seed_expected_field_counts.update(expected_fields)
        findings.extend(_validate_case(payload, path=path, root=root))

    for case_id, paths in sorted(case_id_paths.items()):
        if len(paths) <= 1:
            continue
        findings.append(
            InsightEvalCaseFinding(
                code="duplicate_case_id",
                severity="error",
                path=", ".join(paths),
                message=f"case_id {case_id!r} appears in multiple seed case files.",
            )
        )

    readiness = _readiness_summary(
        accepted_seed_count=accepted_seed_count,
        finding_count=len(findings),
        min_accepted_seeds=min_accepted_seeds,
    )

    return {
        "cases_dir": str(cases_dir),
        "case_count": len(case_paths),
        "accepted_seed_count": accepted_seed_count,
        "min_accepted_seeds": readiness["min_accepted_seeds"],
        "remaining_accepted_seed_count": readiness["remaining_accepted_seed_count"],
        "status_counts": dict(sorted(status_counts.items())),
        "source_boundary_counts": dict(sorted(source_boundary_counts.items())),
        "accepted_seed_source_boundary_counts": dict(sorted(accepted_seed_source_boundary_counts.items())),
        "expected_field_counts": dict(sorted(expected_field_counts.items())),
        "accepted_seed_expected_field_counts": dict(sorted(accepted_seed_expected_field_counts.items())),
        "finding_count": len(findings),
        "readiness": readiness["readiness"],
        "readiness_reasons": readiness["readiness_reasons"],
        "decision_boundary": "eval_substrate_readiness_only",
        "not_for": [
            "strict_greater_than_gate",
            "production_quality_claim",
            "automatic_case_generation_from_local_data",
        ],
        "findings": [finding.to_dict() for finding in findings],
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate the skeleton held-out insight evaluation case set."
    )
    parser.add_argument(
        "--cases-dir",
        default=str(DEFAULT_CASES_DIR),
        help="Directory containing seeded insight eval case JSON files.",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Report format.",
    )
    parser.add_argument(
        "--min-accepted-seeds",
        type=int,
        default=DEFAULT_MIN_ACCEPTED_SEEDS,
        help="Accepted seed count required for ready_for_deterministic_eval readiness.",
    )
    parser.add_argument(
        "--print-template",
        action="store_true",
        help="Print a valid seed-case template JSON and exit without scanning cases.",
    )
    parser.add_argument(
        "--template-case-id",
        default=DEFAULT_TEMPLATE_CASE_ID,
        help="case_id to use with --print-template.",
    )
    parser.add_argument(
        "--template-source-boundary",
        choices=sorted(VALID_SOURCE_BOUNDARIES),
        default="human_seeded",
        help="source_boundary to use with --print-template.",
    )
    return parser.parse_args()


def _print_text_report(report: dict[str, Any]) -> None:
    print(f"[insight-eval-seed-cases] cases_dir: {report['cases_dir']}", flush=True)
    print(f"[insight-eval-seed-cases] case_count: {report['case_count']}", flush=True)
    print(f"[insight-eval-seed-cases] accepted_seed_count: {report['accepted_seed_count']}", flush=True)
    print(f"[insight-eval-seed-cases] min_accepted_seeds: {report['min_accepted_seeds']}", flush=True)
    print(
        "[insight-eval-seed-cases] remaining_accepted_seed_count: "
        f"{report['remaining_accepted_seed_count']}",
        flush=True,
    )
    print(f"[insight-eval-seed-cases] readiness: {report['readiness']}", flush=True)
    for reason in report["readiness_reasons"]:
        print(f"- REASON {reason}", flush=True)
    for finding in report["findings"]:
        print(
            f"- {finding['severity'].upper()} {finding['code']} {finding['path']}: {finding['message']}",
            flush=True,
        )


def main() -> int:
    args = _parse_args()
    if args.print_template:
        print(
            json.dumps(
                build_seed_case_template(
                    case_id=args.template_case_id,
                    source_boundary=args.template_source_boundary,
                ),
                indent=2,
                sort_keys=True,
            ),
            flush=True,
        )
        return 0

    report = check_seed_cases(
        Path(args.cases_dir),
        min_accepted_seeds=args.min_accepted_seeds,
    )
    if args.format == "json":
        print(json.dumps(report, indent=2, sort_keys=True), flush=True)
    else:
        _print_text_report(report)
    return 1 if report["finding_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
