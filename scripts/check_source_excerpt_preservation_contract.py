from __future__ import annotations

import argparse
import ast
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class SourceExcerptContractFinding:
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


def _relative_path(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)


def _read_source(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _function_source(source: str, function_name: str) -> str:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return ""

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name:
            return ast.get_source_segment(source, node) or ""
    return ""


def _missing_fragment_finding(
    *,
    code: str,
    path: Path,
    root: Path,
    message: str,
) -> SourceExcerptContractFinding:
    return SourceExcerptContractFinding(
        code=code,
        severity="error",
        path=_relative_path(path, root),
        message=message,
    )


def _check_required_fragments(
    *,
    source: str,
    path: Path,
    root: Path,
    requirements: dict[str, tuple[str, str]],
) -> list[SourceExcerptContractFinding]:
    findings: list[SourceExcerptContractFinding] = []
    for code, (fragment, message) in requirements.items():
        if fragment not in source:
            findings.append(
                _missing_fragment_finding(
                    code=code,
                    path=path,
                    root=root,
                    message=message,
                )
            )
    return findings


def _check_file_exists(path: Path, *, root: Path) -> list[SourceExcerptContractFinding]:
    if path.exists():
        return []
    return [
        SourceExcerptContractFinding(
            code="contract_file_missing",
            severity="error",
            path=_relative_path(path, root),
            message="Required source-excerpt preservation contract file is missing.",
        )
    ]


def _check_official_collector(root: Path) -> list[SourceExcerptContractFinding]:
    path = root / "signal_collectors" / "official_collector.py"
    findings = _check_file_exists(path, root=root)
    if findings:
        return findings
    source = _read_source(path)
    return _check_required_fragments(
        source=source,
        path=path,
        root=root,
        requirements={
            "official_collector_bounds_excerpt": (
                'source_excerpt = body_text[:1200] if body_text else ""',
                "Official collector should bound body text before preserving it as source_excerpt.",
            ),
            "official_collector_writes_source_excerpt": (
                '"source_excerpt": source_excerpt',
                "Official collector should write canonical source_excerpt.",
            ),
            "official_collector_writes_excerpt_length": (
                '"source_excerpt_length": len(source_excerpt)',
                "Official collector should write source_excerpt_length for observability.",
            ),
        },
    )


def _check_merge_normalizer(root: Path) -> list[SourceExcerptContractFinding]:
    path = root / "signal_collectors" / "merge_signals.py"
    findings = _check_file_exists(path, root=root)
    if findings:
        return findings
    source = _read_source(path)
    return _check_required_fragments(
        source=source,
        path=path,
        root=root,
        requirements={
            "merge_bounds_excerpt": (
                "MAX_SOURCE_EXCERPT_CHARS = 1200",
                "Merge normalization should retain the ADR-0011 1200-character bound.",
            ),
            "merge_accepts_canonical_source_excerpt": (
                '"source_excerpt"',
                "Merge normalization should accept canonical source_excerpt.",
            ),
            "merge_rejects_summary_content": (
                'if field == "content" and value.lower() == normalized_summary',
                "Merge normalization should not promote content that merely duplicates summary.",
            ),
            "merge_writes_source_excerpt": (
                'normalized["source_excerpt"] = source_excerpt',
                "Merge normalization should preserve canonical source_excerpt.",
            ),
        },
    )


def _check_pipeline_preservation(root: Path) -> list[SourceExcerptContractFinding]:
    path = root / "app" / "main_summary_v2.py"
    findings = _check_file_exists(path, root=root)
    if findings:
        return findings
    source = _read_source(path)
    findings.extend(
        _check_required_fragments(
            source=source,
            path=path,
            root=root,
            requirements={
                "pipeline_bounds_excerpt": (
                    "MAX_SOURCE_EXCERPT_CHARS = 1200",
                    "Pipeline should retain the ADR-0011 1200-character source_excerpt bound.",
                ),
                "pipeline_has_copy_helper": (
                    "def _copy_source_excerpt_to_signal",
                    "Pipeline should keep a dedicated helper for canonical source_excerpt preservation.",
                ),
                "pipeline_calls_copy_helper": (
                    "_copy_source_excerpt_to_signal(signal, item)",
                    "Pipeline should copy source_excerpt while converting dictionaries back to Signal objects.",
                ),
            },
        )
    )

    output_function = _function_source(source, "signal_to_output_dict")
    if not output_function:
        findings.append(
            SourceExcerptContractFinding(
                code="pipeline_output_function_missing",
                severity="error",
                path=_relative_path(path, root),
                message="signal_to_output_dict is required for final signal output contract checks.",
            )
        )
        return findings

    findings.extend(
        _check_required_fragments(
            source=output_function,
            path=path,
            root=root,
            requirements={
                "pipeline_output_writes_source_excerpt": (
                    'data["source_excerpt"]',
                    "Final signal output should write canonical source_excerpt when present.",
                ),
                "pipeline_output_writes_excerpt_length": (
                    'data["source_excerpt_length"]',
                    "Final signal output should write source_excerpt_length for observability.",
                ),
            },
        )
    )

    forbidden_fields = {"full_text", "raw_text", "raw_content", "article_body"}
    for field in sorted(forbidden_fields):
        if field in output_function:
            findings.append(
                SourceExcerptContractFinding(
                    code="pipeline_output_preserves_full_text_like_field",
                    severity="error",
                    path=_relative_path(path, root),
                    message=(
                        f"signal_to_output_dict mentions {field!r}. Final signal output should preserve "
                        "canonical source_excerpt only, not full-text-like fields."
                    ),
                )
            )

    return findings


def summarize_findings(findings: list[SourceExcerptContractFinding]) -> dict[str, Any]:
    severity_counts = Counter(finding.severity for finding in findings)
    code_counts = Counter(finding.code for finding in findings)
    error_count = severity_counts.get("error", 0)
    return {
        "finding_count": len(findings),
        "error_count": error_count,
        "warning_count": severity_counts.get("warning", 0),
        "code_counts": dict(sorted(code_counts.items())),
        "readiness": "contract_ok" if error_count == 0 else "contract_gap_found",
    }


def check_source_excerpt_preservation_contract(root: Path = REPO_ROOT) -> dict[str, Any]:
    findings: list[SourceExcerptContractFinding] = []
    findings.extend(_check_official_collector(root))
    findings.extend(_check_merge_normalizer(root))
    findings.extend(_check_pipeline_preservation(root))
    return {
        "schema_version": "source_excerpt_preservation_contract.v1",
        "report_boundary": {
            "mode": "read_only_static_contract_check",
            "writes_data": False,
            "runs_ingestion": False,
            "hard_enforcement": False,
            "not_for": [
                "fresh_data_validation",
                "historical_backfill",
                "source_truth_judgment",
                "prompt_or_schema_expansion",
            ],
        },
        "contract": {
            "adr": "docs/adr/0011-evidence-pack-source-excerpt-policy.md",
            "canonical_field": "source_excerpt",
            "max_source_excerpt_chars": 1200,
            "required_paths": [
                "signal_collectors/official_collector.py",
                "signal_collectors/merge_signals.py",
                "app/main_summary_v2.py",
            ],
        },
        "summary": summarize_findings(findings),
        "findings": [finding.to_dict() for finding in findings],
    }


def source_excerpt_contract_exit_code(report: dict[str, Any], *, fail_on_gaps: bool) -> int:
    if not fail_on_gaps:
        return 0
    return 1 if int(report.get("summary", {}).get("error_count") or 0) > 0 else 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only static contract check for ADR-0011 source_excerpt preservation. "
            "It does not run ingestion or judge source truth."
        )
    )
    parser.add_argument(
        "--root",
        default=str(REPO_ROOT),
        help="Repository root to scan. Defaults to the current checkout.",
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
        help="Exit with code 1 when static contract gaps are found.",
    )
    return parser.parse_args()


def _print_text_report(report: dict[str, Any]) -> None:
    summary = report["summary"]
    boundary = report["report_boundary"]
    print("[source-excerpt-contract] scope: ADR-0011 static preservation contract")
    print(f"[source-excerpt-contract] mode: {boundary['mode']}")
    print(f"[source-excerpt-contract] readiness: {summary['readiness']}")
    print(
        "[source-excerpt-contract] findings: "
        f"{summary['finding_count']} errors={summary['error_count']} warnings={summary['warning_count']}"
    )
    for finding in report["findings"]:
        print(
            f"- {finding['severity'].upper()} {finding['code']} "
            f"{finding['path']} {finding['message']}"
        )


def main() -> int:
    args = _parse_args()
    report = check_source_excerpt_preservation_contract(Path(args.root))
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        _print_text_report(report)
    return source_excerpt_contract_exit_code(report, fail_on_gaps=args.fail_on_gaps)


if __name__ == "__main__":
    raise SystemExit(main())
