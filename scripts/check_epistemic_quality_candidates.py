from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SIGNAL_FILES = (REPO_ROOT / "data" / "output" / "signals.json",)

INSIGHT_FIELDS = (
    "why_it_matters",
    "relevance_to_projects",
    "relevance_to_career",
    "synthesized_insight",
    "final_reflection",
)

INFLATED_TERMS = {
    "breakthrough",
    "disrupt",
    "disruptive",
    "game changer",
    "game-changing",
    "inevitable",
    "paradigm",
    "revolution",
    "revolutionary",
    "solved",
    "transformative",
    "颠覆",
    "革命",
    "范式",
    "终局",
}

BOUNDARY_TERMS = {
    "appears",
    "could",
    "early",
    "experimental",
    "likely",
    "may",
    "prototype",
    "suggests",
    "uncertain",
    "unknown",
    "可能",
    "实验",
    "早期",
    "不确定",
}

PRODUCTION_TERMS = {
    "production",
    "enterprise",
    "deployed",
    "at scale",
    "生产",
    "企业级",
    "规模化",
}


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _read_json(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None


def _records_from_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        if isinstance(payload.get("signals"), list):
            return [item for item in payload["signals"] if isinstance(item, dict)]
        if isinstance(payload.get("items"), list):
            return [item for item in payload["items"] if isinstance(item, dict)]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def _relative_path(path: Path, root: Path = REPO_ROOT) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)


def _combined_text(record: dict[str, Any]) -> str:
    values = [
        _safe_text(record.get("title")),
        _safe_text(record.get("summary")),
        *[_safe_text(record.get(field)) for field in INSIGHT_FIELDS],
    ]
    return "\n".join(value for value in values if value)


def _contains_any(text: str, terms: set[str]) -> list[str]:
    lowered = text.lower()
    return sorted(term for term in terms if term.lower() in lowered)


@dataclass(frozen=True)
class EpistemicQualityCandidate:
    path: str
    signal_id: str
    title: str
    source: str
    knowledge_honesty: str
    transmission_adaptability: str
    primary_issue: str
    advisory_reasons: list[str]
    matched_terms: dict[str, list[str]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "signal_id": self.signal_id,
            "title": self.title,
            "source": self.source,
            "knowledge_honesty": self.knowledge_honesty,
            "transmission_adaptability": self.transmission_adaptability,
            "primary_issue": self.primary_issue,
            "advisory_reasons": self.advisory_reasons,
            "matched_terms": self.matched_terms,
        }


def evaluate_epistemic_quality_candidate(
    record: dict[str, Any],
    *,
    path: Path | None = None,
    root: Path = REPO_ROOT,
) -> EpistemicQualityCandidate | None:
    text = _combined_text(record)
    if not text:
        return None

    inflated = _contains_any(text, INFLATED_TERMS)
    boundary = _contains_any(text, BOUNDARY_TERMS)
    production = _contains_any(text, PRODUCTION_TERMS)
    long_text = len(text) > 1800

    reasons: list[str] = []
    knowledge_honesty = "unknown"
    transmission_adaptability = "unknown"
    primary_issue = "none"

    if inflated and not boundary:
        knowledge_honesty = "low"
        primary_issue = "overconfident_framing"
        reasons.append("inflated_terms_without_boundary_language")
    elif inflated:
        knowledge_honesty = "medium"
        primary_issue = "framing_needs_review"
        reasons.append("inflated_terms_with_some_boundary_language")
    elif production and not boundary:
        knowledge_honesty = "medium"
        primary_issue = "production_readiness_needs_review"
        reasons.append("production_or_scale_language_without_boundary_language")
    else:
        knowledge_honesty = "unknown"
        reasons.append("no_simple_framing_trigger_detected")

    if long_text and inflated:
        transmission_adaptability = "low"
        if primary_issue == "none":
            primary_issue = "dense_persuasive_framing"
        reasons.append("long_content_with_inflated_terms")
    elif long_text:
        transmission_adaptability = "medium"
        if primary_issue == "none":
            primary_issue = "transmission_density_review"
        reasons.append("long_content_may_need_transmission_review")
    elif inflated:
        transmission_adaptability = "medium"
        reasons.append("compressed_or_persuasive_framing_needs_review")
    else:
        transmission_adaptability = "unknown"

    if knowledge_honesty == "unknown" and transmission_adaptability == "unknown":
        return None

    return EpistemicQualityCandidate(
        path=_relative_path(path, root) if path else "",
        signal_id=_safe_text(record.get("signal_id")) or _safe_text(record.get("id")),
        title=_safe_text(record.get("title"))[:160],
        source=_safe_text(record.get("source")),
        knowledge_honesty=knowledge_honesty,
        transmission_adaptability=transmission_adaptability,
        primary_issue=primary_issue,
        advisory_reasons=list(dict.fromkeys(reasons)),
        matched_terms={
            "inflated_terms": inflated,
            "boundary_terms": boundary,
            "production_terms": production,
        },
    )


def scan_signal_file(path: Path, *, root: Path = REPO_ROOT) -> list[EpistemicQualityCandidate]:
    payload = _read_json(path)
    rows: list[EpistemicQualityCandidate] = []
    for record in _records_from_payload(payload):
        candidate = evaluate_epistemic_quality_candidate(record, path=path, root=root)
        if candidate is not None:
            rows.append(candidate)
    return rows


def summarize(candidates: list[EpistemicQualityCandidate]) -> dict[str, Any]:
    honesty = Counter(row.knowledge_honesty for row in candidates)
    adaptability = Counter(row.transmission_adaptability for row in candidates)
    issues = Counter(row.primary_issue for row in candidates)
    return {
        "candidate_count": len(candidates),
        "knowledge_honesty_counts": dict(sorted(honesty.items())),
        "transmission_adaptability_counts": dict(sorted(adaptability.items())),
        "primary_issue_counts": dict(sorted(issues.items())),
    }


def build_epistemic_quality_report(
    *,
    signal_files: list[Path] | None = None,
    include_rows: bool = True,
    root: Path = REPO_ROOT,
) -> dict[str, Any]:
    files = signal_files or list(DEFAULT_SIGNAL_FILES)
    candidates: list[EpistemicQualityCandidate] = []
    for path in files:
        candidates.extend(scan_signal_file(path, root=root))

    return {
        "report_boundary": {
            "mode": "read_only",
            "writes_data": False,
            "uses_llm_scorer": False,
            "changes_verification": False,
            "changes_gates": False,
            "interpretation": (
                "This advisory report uses simple framing heuristics to find "
                "candidate records for human epistemic-quality review. It does "
                "not prove dishonesty and does not change verification status."
            ),
        },
        "paths": {"signal_files": [str(path) for path in files]},
        "summary": summarize(candidates),
        "rows": [row.to_dict() for row in candidates] if include_rows else [],
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read-only epistemic-quality candidate report.")
    parser.add_argument("--signal-file", action="append", default=[])
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--summary-only", action="store_true")
    return parser.parse_args()


def _signal_files_from_args(values: list[str]) -> list[Path] | None:
    files = [Path(value).resolve() for value in values if _safe_text(value)]
    return files or None


def _print_text_report(report: dict[str, Any], *, summary_only: bool = False) -> None:
    summary = report["summary"]
    print("[epistemic-quality] scope: read-only advisory candidate report", flush=True)
    print(
        "[epistemic-quality] candidates: "
        f"{summary['candidate_count']} "
        f"knowledge_honesty={summary['knowledge_honesty_counts']} "
        f"transmission_adaptability={summary['transmission_adaptability_counts']}",
        flush=True,
    )
    print(
        "[epistemic-quality] issues: "
        + ", ".join(f"{key}={value}" for key, value in summary["primary_issue_counts"].items()),
        flush=True,
    )
    if summary_only:
        return
    for row in report["rows"][:50]:
        print(
            f"- {row['signal_id'] or 'missing-id'} "
            f"honesty={row['knowledge_honesty']} "
            f"adaptability={row['transmission_adaptability']} "
            f"issue={row['primary_issue']} "
            f"title={row['title']} path={row['path']}",
            flush=True,
        )


def main() -> int:
    args = _parse_args()
    report = build_epistemic_quality_report(
        signal_files=_signal_files_from_args(args.signal_file),
        include_rows=not args.summary_only,
    )
    if args.format == "json":
        print(json.dumps(report, indent=2, sort_keys=True), flush=True)
    else:
        _print_text_report(report, summary_only=args.summary_only)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
