from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_TARGETS = (
    REPO_ROOT / "backend" / "app" / "services" / "claim_verification_service.py",
    REPO_ROOT / "backend" / "app" / "services" / "evidence_pack_service.py",
    REPO_ROOT / "backend" / "app" / "services" / "evidence_sufficiency_service.py",
    REPO_ROOT / "backend" / "app" / "services" / "project_intelligence_service.py",
    REPO_ROOT / "backend" / "app" / "services" / "verified_insight_service.py",
    REPO_ROOT / "backend" / "app" / "routes" / "projects.py",
)

PROHIBITED_IMPORT_PREFIXES = (
    "scripts.radar_doctor",
    "scripts.check_github_scalar_coverage",
    "scripts.check_github_scalar_backfill_readiness",
    "scripts.check_github_scalar_live_refresh",
    "app.services.source_health_service",
    "backend.app.services.source_health_service",
)


@dataclass(frozen=True)
class ImportBoundaryViolation:
    path: str
    line: int
    imported_module: str
    matched_prefix: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "line": self.line,
            "imported_module": self.imported_module,
            "matched_prefix": self.matched_prefix,
        }


def _relative_path(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _candidate_imports(node: ast.AST) -> list[tuple[str, int]]:
    imports: list[tuple[str, int]] = []
    if isinstance(node, ast.Import):
        for alias in node.names:
            imports.append((alias.name, node.lineno))
    elif isinstance(node, ast.ImportFrom):
        module = node.module or ""
        if module:
            imports.append((module, node.lineno))
        for alias in node.names:
            if module:
                imports.append((f"{module}.{alias.name}", node.lineno))
            else:
                imports.append((alias.name, node.lineno))
    return imports


def _matching_prefix(imported_module: str, prohibited_prefixes: tuple[str, ...]) -> str:
    normalized = imported_module.strip()
    for prefix in prohibited_prefixes:
        if normalized == prefix or normalized.startswith(f"{prefix}."):
            return prefix
    return ""


def _scan_file(
    path: Path,
    *,
    root: Path,
    prohibited_prefixes: tuple[str, ...],
) -> tuple[list[ImportBoundaryViolation], str | None]:
    text = _read_text(path)
    relative = _relative_path(path, root)
    if text is None:
        return [], "unreadable"
    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError:
        return [], "syntax_error"

    violations: list[ImportBoundaryViolation] = []
    seen: set[tuple[str, int, str]] = set()
    for node in ast.walk(tree):
        for imported_module, line in _candidate_imports(node):
            matched = _matching_prefix(imported_module, prohibited_prefixes)
            if matched:
                key = (relative, line, matched)
                if key in seen:
                    continue
                seen.add(key)
                violations.append(
                    ImportBoundaryViolation(
                        path=relative,
                        line=line,
                        imported_module=imported_module,
                        matched_prefix=matched,
                    )
                )
    return violations, None


def build_operational_import_boundary_report(
    *,
    targets: list[Path],
    root: Path = REPO_ROOT,
    prohibited_prefixes: tuple[str, ...] = PROHIBITED_IMPORT_PREFIXES,
    include_records: bool = True,
) -> dict[str, Any]:
    violations: list[ImportBoundaryViolation] = []
    file_statuses: dict[str, str] = {}

    for raw_path in targets:
        path = raw_path if raw_path.is_absolute() else root / raw_path
        file_violations, error = _scan_file(
            path,
            root=root,
            prohibited_prefixes=prohibited_prefixes,
        )
        relative = _relative_path(path, root)
        if error:
            file_statuses[relative] = error
        else:
            file_statuses[relative] = "ok"
        violations.extend(file_violations)

    report: dict[str, Any] = {
        "report_boundary": {
            "mode": "read_only_static_ast_advisory",
            "quality_boundary": (
                "This checker reports operational-health imports inside verification/action paths; "
                "it does not infer source truth, source quality, or action eligibility."
            ),
        },
        "summary": {
            "target_count": len(targets),
            "violation_count": len(violations),
            "file_statuses": file_statuses,
            "prohibited_import_prefixes": list(prohibited_prefixes),
        },
    }
    if include_records:
        report["violations"] = [violation.to_dict() for violation in violations]
    return report


def operational_import_boundary_exit_code(report: dict[str, Any], *, fail_on_violations: bool = False) -> int:
    if not fail_on_violations:
        return 0
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return 1 if int(summary.get("violation_count") or 0) else 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only AST checker for operational-health import leakage into "
            "verification/action paths."
        )
    )
    parser.add_argument("--root", default=str(REPO_ROOT), help="Repository root. Defaults to current checkout.")
    parser.add_argument(
        "--path",
        dest="paths",
        action="append",
        help="Python file to scan. Can be passed multiple times. Defaults to verification/action targets.",
    )
    parser.add_argument("--summary-only", action="store_true", help="Omit violation rows from JSON output.")
    parser.add_argument("--format", choices=["text", "json"], default="text", help="Report format.")
    parser.add_argument(
        "--fail-on-violations",
        action="store_true",
        help="Exit with code 1 when prohibited imports are found.",
    )
    return parser.parse_args()


def _print_text_report(report: dict[str, Any]) -> None:
    summary = report["summary"]
    boundary = report["report_boundary"]
    print("[operational-import-boundary] scope: read-only static AST advisory")
    print(f"[operational-import-boundary] mode: {boundary['mode']}")
    print(f"[operational-import-boundary] boundary: {boundary['quality_boundary']}")
    print(
        "[operational-import-boundary] summary: "
        f"targets={summary['target_count']} violations={summary['violation_count']}"
    )
    for path, status in summary["file_statuses"].items():
        print(f"[operational-import-boundary] file: {path} status={status}")
    for violation in report.get("violations") or []:
        print(
            "- violation: "
            f"path={violation['path']} line={violation['line']} "
            f"import={violation['imported_module']} matched={violation['matched_prefix']}"
        )


def main() -> int:
    args = _parse_args()
    root = Path(args.root)
    targets = [Path(path) for path in args.paths] if args.paths else list(DEFAULT_TARGETS)
    report = build_operational_import_boundary_report(
        targets=targets,
        root=root,
        include_records=not args.summary_only,
    )
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        _print_text_report(report)
    return operational_import_boundary_exit_code(report, fail_on_violations=args.fail_on_violations)


if __name__ == "__main__":
    raise SystemExit(main())
