from __future__ import annotations

import argparse
import ast
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_SCAN_PATHS = [
    "backend/app/routes",
    "backend/app/services",
    "tests",
]


@dataclass(frozen=True)
class VerificationMetadataFinding:
    code: str
    severity: str
    path: str
    line: int
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "path": self.path,
            "line": self.line,
            "message": self.message,
        }


def _relative_path(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)


def _is_empty_dict(node: ast.AST | None) -> bool:
    return isinstance(node, ast.Dict) and not node.keys and not node.values


def _is_none(node: ast.AST | None) -> bool:
    return isinstance(node, ast.Constant) and node.value is None


def _annotation_text(node: ast.AST | None) -> str:
    if node is None:
        return ""
    try:
        return ast.unparse(node)
    except Exception:
        return ""


def _arg_defaults(function: ast.FunctionDef | ast.AsyncFunctionDef) -> dict[str, ast.AST]:
    args = list(function.args.posonlyargs) + list(function.args.args)
    defaults = list(function.args.defaults)
    default_offset = len(args) - len(defaults)
    default_map: dict[str, ast.AST] = {}
    for index, default in enumerate(defaults):
        default_map[args[default_offset + index].arg] = default
    for kw_arg, default in zip(function.args.kwonlyargs, function.args.kw_defaults):
        if default is not None:
            default_map[kw_arg.arg] = default
    return default_map


def _scan_ast(tree: ast.AST, *, path: Path, root: Path) -> list[VerificationMetadataFinding]:
    findings: list[VerificationMetadataFinding] = []
    rel_path = _relative_path(path, root)

    for node in ast.walk(tree):
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id == "verification_metadata":
                annotation = _annotation_text(node.annotation)
                if _is_empty_dict(node.value):
                    findings.append(
                        VerificationMetadataFinding(
                            code="schema_default_empty_dict",
                            severity="warning",
                            path=rel_path,
                            line=node.lineno,
                            message=(
                                "verification_metadata has an empty dict default. "
                                "Runtime gates may still protect this path, but schema hardening would require caller audit."
                            ),
                        )
                    )
                elif _is_none(node.value) and "ProjectTakeaway" in rel_path:
                    findings.append(
                        VerificationMetadataFinding(
                            code="project_takeaway_schema_default_none",
                            severity="warning",
                            path=rel_path,
                            line=node.lineno,
                            message=(
                                "Project Takeaway verification_metadata permits None at schema level. "
                                f"Annotation: {annotation or 'unknown'}."
                            ),
                        )
                    )

        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            default_map = _arg_defaults(node)
            for arg in list(node.args.args) + list(node.args.kwonlyargs):
                if arg.arg != "verification_metadata":
                    continue
                default = default_map.get(arg.arg)
                if _is_none(default):
                    findings.append(
                        VerificationMetadataFinding(
                            code="function_default_none",
                            severity="info",
                            path=rel_path,
                            line=arg.lineno,
                            message=(
                                f"{node.name} accepts verification_metadata=None. "
                                "This may be correct for internal normalization, but it is a caller migration point."
                            ),
                        )
                    )

        if isinstance(node, ast.Call):
            for keyword in node.keywords:
                if keyword.arg == "verification_metadata" and _is_empty_dict(keyword.value):
                    findings.append(
                        VerificationMetadataFinding(
                            code="empty_dict_call_site",
                            severity="info",
                            path=rel_path,
                            line=keyword.value.lineno,
                            message=(
                                "Call site passes verification_metadata={}. "
                                "Usually a negative-path test fixture, but it must be enumerated before schema hardening."
                            ),
                        )
                    )

    return findings


def scan_python_file(path: Path, *, root: Path) -> list[VerificationMetadataFinding]:
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return [
            VerificationMetadataFinding(
                code="scan_error",
                severity="warning",
                path=_relative_path(path, root),
                line=0,
                message="Could not parse file during verification metadata hardening audit.",
            )
        ]
    return _scan_ast(tree, path=path, root=root)


def scan_paths(paths: list[Path], *, root: Path) -> list[VerificationMetadataFinding]:
    findings: list[VerificationMetadataFinding] = []
    for scan_path in paths:
        path = scan_path if scan_path.is_absolute() else root / scan_path
        if path.is_file() and path.suffix == ".py":
            findings.extend(scan_python_file(path, root=root))
        elif path.is_dir():
            for file_path in sorted(path.rglob("*.py")):
                findings.extend(scan_python_file(file_path, root=root))
    return findings


def summarize_findings(findings: list[VerificationMetadataFinding]) -> dict[str, Any]:
    code_counts = Counter(finding.code for finding in findings)
    severity_counts = Counter(finding.severity for finding in findings)
    return {
        "finding_count": len(findings),
        "code_counts": dict(sorted(code_counts.items())),
        "severity_counts": dict(sorted(severity_counts.items())),
        "schema_hardening_readiness": (
            "needs_caller_fixture_audit"
            if findings
            else "no_static_default_or_empty_call_sites_found"
        ),
        "decision_boundary": "migration_risk_audit_only",
        "not_for": [
            "runtime_behavior_change",
            "schema_change_without_manual_review",
            "production_data_quality_judgment",
        ],
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Static advisory audit for verification_metadata schema hardening. "
            "It reports migration touchpoints and never changes runtime behavior."
        )
    )
    parser.add_argument(
        "paths",
        nargs="*",
        default=DEFAULT_SCAN_PATHS,
        help="Files or directories to scan. Defaults to backend routes/services and tests.",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Report format.",
    )
    return parser.parse_args()


def _print_text_report(findings: list[VerificationMetadataFinding], *, root: Path) -> None:
    summary = summarize_findings(findings)
    print("[verification-metadata-hardening] scope: static migration-risk audit only", flush=True)
    print(f"[verification-metadata-hardening] root: {root}", flush=True)
    print(f"[verification-metadata-hardening] findings: {summary['finding_count']}", flush=True)
    print(f"[verification-metadata-hardening] readiness: {summary['schema_hardening_readiness']}", flush=True)
    for finding in findings:
        print(
            f"- {finding.severity.upper()} {finding.code} {finding.path}:{finding.line} "
            f"{finding.message}",
            flush=True,
        )


def main() -> int:
    args = _parse_args()
    root = Path(__file__).resolve().parents[1]
    findings = scan_paths([Path(path) for path in args.paths], root=root)
    if args.format == "json":
        print(
            json.dumps(
                {
                    "summary": summarize_findings(findings),
                    "findings": [finding.to_dict() for finding in findings],
                },
                indent=2,
                sort_keys=True,
            ),
            flush=True,
        )
    else:
        _print_text_report(findings, root=root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
