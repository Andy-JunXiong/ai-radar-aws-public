from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ARTIFACT_DIR = REPO_ROOT / "docs" / "codex-assessments"

REQUIRED_SECTION_GROUPS = {
    "sources": {
        "code": "missing_source_citations",
        "severity": "error",
        "headings": {
            "sources",
            "citations",
            "source boundary",
            "source citations",
            "reference inputs",
        },
        "message": (
            "Artifact should name the source files, commands, reports, or external references "
            "used to produce the judgment."
        ),
    },
    "inference_boundary": {
        "code": "missing_inference_boundary",
        "severity": "error",
        "headings": {
            "inference boundary",
            "interpretation boundary",
            "reasoning boundary",
        },
        "message": (
            "Artifact should distinguish source-backed facts from agent interpretation or synthesis."
        ),
    },
    "evidence_status": {
        "code": "missing_evidence_status",
        "severity": "error",
        "headings": {
            "evidence status",
            "verification status",
            "evidence boundary",
            "verification boundary",
        },
        "message": (
            "Artifact should state whether it is using verified evidence, repo-grounded context, "
            "external analogy, or proposal-only support."
        ),
    },
    "actionability_boundary": {
        "code": "missing_actionability_boundary",
        "severity": "warning",
        "headings": {
            "actionability boundary",
            "action boundary",
            "implementation boundary",
            "next-step boundary",
        },
        "message": (
            "Artifact should say which recommendations are actionable now and which require "
            "separate approval, trusted data, or implementation planning."
        ),
    },
}

REQUIRED_SECTION_GROUP_REPORT = [
    {
        "name": name,
        "code": str(config["code"]),
        "severity": str(config["severity"]),
        "accepted_headings": sorted(str(heading) for heading in config["headings"]),
    }
    for name, config in REQUIRED_SECTION_GROUPS.items()
]

SOURCE_REFERENCE_PATTERN = re.compile(
    r"(`[^`]+`|\b(?:docs|backend|frontend|scripts|tests|app|data)/[^\s,;:)]+|\bpython\b|\bpytest\b)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ArtifactCitationFinding:
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


@dataclass(frozen=True)
class ArtifactCitationRow:
    path: str
    artifact_ok: bool
    present_sections: list[str]
    missing_sections: list[str]
    finding_count: int
    error_count: int
    warning_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "artifact_ok": self.artifact_ok,
            "present_sections": self.present_sections,
            "missing_sections": self.missing_sections,
            "finding_count": self.finding_count,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
        }


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _relative_path(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)


def _normalize_heading(value: str) -> str:
    text = value.strip().lower()
    text = re.sub(r"[`*_#:\[\]()]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _extract_headings(markdown: str) -> set[str]:
    headings: set[str] = set()
    for line in markdown.splitlines():
        match = re.match(r"^\s{0,3}#{1,6}\s+(.+?)\s*$", line)
        if match:
            headings.add(_normalize_heading(match.group(1)))
    return headings


def _has_source_reference(markdown: str) -> bool:
    return bool(SOURCE_REFERENCE_PATTERN.search(markdown))


def validate_artifact_markdown(
    markdown: str,
    *,
    path: Path,
    root: Path = REPO_ROOT,
) -> tuple[ArtifactCitationRow, list[ArtifactCitationFinding]]:
    rel_path = _relative_path(path, root)
    headings = _extract_headings(markdown)
    findings: list[ArtifactCitationFinding] = []
    present_sections: list[str] = []
    missing_sections: list[str] = []

    for section_name, config in REQUIRED_SECTION_GROUPS.items():
        section_present = bool(headings.intersection(config["headings"]))
        if section_present:
            present_sections.append(section_name)
            continue
        missing_sections.append(section_name)
        findings.append(
            ArtifactCitationFinding(
                code=str(config["code"]),
                severity=str(config["severity"]),
                path=rel_path,
                message=str(config["message"]),
            )
        )

    if present_sections and "sources" in present_sections and not _has_source_reference(markdown):
        findings.append(
            ArtifactCitationFinding(
                code="source_section_without_reference",
                severity="warning",
                path=rel_path,
                message=(
                    "Source section exists but does not appear to name a file path, command, "
                    "or backtick-quoted reference."
                ),
            )
        )

    severity_counts = Counter(finding.severity for finding in findings)
    row = ArtifactCitationRow(
        path=rel_path,
        artifact_ok=severity_counts.get("error", 0) == 0,
        present_sections=present_sections,
        missing_sections=missing_sections,
        finding_count=len(findings),
        error_count=severity_counts.get("error", 0),
        warning_count=severity_counts.get("warning", 0),
    )
    return row, findings


def _iter_markdown_paths(paths: list[Path], *, root: Path) -> list[Path]:
    markdown_paths: list[Path] = []
    for raw_path in paths:
        path = raw_path if raw_path.is_absolute() else root / raw_path
        if path.is_file() and path.suffix.lower() == ".md":
            markdown_paths.append(path)
        elif path.is_dir():
            markdown_paths.extend(sorted(path.glob("*.md")))
    return sorted(set(markdown_paths))


def check_artifact_citation_integrity(
    paths: list[Path] | None = None,
    *,
    root: Path = REPO_ROOT,
) -> dict[str, Any]:
    scan_paths = paths or [DEFAULT_ARTIFACT_DIR]
    markdown_paths = _iter_markdown_paths(scan_paths, root=root)
    findings: list[ArtifactCitationFinding] = []
    rows: list[ArtifactCitationRow] = []

    for markdown_path in markdown_paths:
        try:
            markdown = markdown_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            rel_path = _relative_path(markdown_path, root)
            finding = ArtifactCitationFinding(
                code="artifact_read_error",
                severity="warning",
                path=rel_path,
                message="Could not read artifact markdown for citation integrity audit.",
            )
            findings.append(finding)
            rows.append(
                ArtifactCitationRow(
                    path=rel_path,
                    artifact_ok=True,
                    present_sections=[],
                    missing_sections=[],
                    finding_count=1,
                    error_count=0,
                    warning_count=1,
                )
            )
            continue

        row, row_findings = validate_artifact_markdown(markdown, path=markdown_path, root=root)
        rows.append(row)
        findings.extend(row_findings)

    severity_counts = Counter(finding.severity for finding in findings)
    code_counts = Counter(finding.code for finding in findings)
    artifact_count = len(rows)
    error_count = severity_counts.get("error", 0)
    readiness = "no_artifacts_found"
    if artifact_count and error_count:
        readiness = "citation_retrofit_needed"
    elif artifact_count:
        readiness = "ready_for_human_absorption"

    return {
        "schema_version": "artifact_citation_report.v1",
        "report_boundary": {
            "mode": "read_only",
            "decision_boundary": "artifact_review_readiness_only",
            "writes_data": False,
            "hard_enforcement": False,
            "not_for": [
                "runtime_behavior_change",
                "automatic_adr_absorption",
                "production_evidence_quality_claim",
                "external_claim_verification",
            ],
        },
        "summary": {
            "artifact_count": artifact_count,
            "artifact_ok_count": sum(1 for row in rows if row.artifact_ok),
            "finding_count": len(findings),
            "error_count": error_count,
            "warning_count": severity_counts.get("warning", 0),
            "severity_counts": dict(sorted(severity_counts.items())),
            "finding_code_counts": dict(sorted(code_counts.items())),
            "readiness": readiness,
        },
        "required_section_groups": REQUIRED_SECTION_GROUP_REPORT,
        "rows": [row.to_dict() for row in rows],
        "findings": [finding.to_dict() for finding in findings],
    }


def artifact_citation_exit_code(report: dict[str, Any], *, fail_on_gaps: bool = False) -> int:
    if fail_on_gaps and int(report.get("summary", {}).get("finding_count") or 0) > 0:
        return 1
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only citation integrity audit for agent-authored markdown artifacts. "
            "It reports missing source, inference, evidence, and actionability boundaries."
        )
    )
    parser.add_argument(
        "paths",
        nargs="*",
        default=[str(DEFAULT_ARTIFACT_DIR)],
        help="Markdown files or directories to scan. Defaults to docs/codex-assessments.",
    )
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument(
        "--fail-on-gaps",
        action="store_true",
        help="Return a non-zero exit code when citation gaps are found. Default remains advisory.",
    )
    return parser.parse_args()


def _print_text_report(report: dict[str, Any]) -> None:
    summary = report["summary"]
    print("[artifact-citation] scope: read-only artifact review readiness audit", flush=True)
    print(
        "[artifact-citation] artifacts: "
        f"{summary['artifact_count']} ok={summary['artifact_ok_count']} "
        f"errors={summary['error_count']} warnings={summary['warning_count']}",
        flush=True,
    )
    print(f"[artifact-citation] readiness: {summary['readiness']}", flush=True)
    for finding in report["findings"]:
        print(
            f"- {finding['severity'].upper()} {finding['code']} {finding['path']}: "
            f"{finding['message']}",
            flush=True,
        )


def main() -> int:
    args = _parse_args()
    root = REPO_ROOT
    report = check_artifact_citation_integrity([Path(path) for path in args.paths], root=root)
    if args.format == "json":
        print(json.dumps(report, indent=2, sort_keys=True), flush=True)
    else:
        _print_text_report(report)
    return artifact_citation_exit_code(report, fail_on_gaps=args.fail_on_gaps)


if __name__ == "__main__":
    raise SystemExit(main())
