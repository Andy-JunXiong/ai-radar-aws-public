from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"

backend_root_text = str(BACKEND_ROOT)
if backend_root_text in sys.path:
    sys.path.remove(backend_root_text)
sys.path.insert(0, backend_root_text)

existing_app = sys.modules.get("app")
existing_app_file = Path(str(getattr(existing_app, "__file__", ""))).resolve() if existing_app else None
if existing_app_file and not str(existing_app_file).startswith(str(BACKEND_ROOT.resolve())):
    for module_name in list(sys.modules):
        if module_name == "app" or module_name.startswith("app."):
            del sys.modules[module_name]

from app.services.signal_near_duplicate_service import (  # noqa: E402
    DEFAULT_SIGNAL_FILES,
    build_signal_near_duplicate_report,
    signal_near_duplicate_exit_code,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only near-duplicate report for local signal outputs. "
            "It reports likely category-vs-article duplicates but does not rewrite data."
        )
    )
    parser.add_argument("--root", default=str(REPO_ROOT), help="Repository root. Defaults to current checkout.")
    parser.add_argument(
        "--file",
        dest="files",
        action="append",
        help="Signal JSON file to scan. Can be passed multiple times. Defaults to local output files.",
    )
    parser.add_argument("--summary-only", action="store_true", help="Omit duplicate group records from JSON output.")
    parser.add_argument("--format", choices=["text", "json"], default="text", help="Report format.")
    parser.add_argument(
        "--fail-on-findings",
        action="store_true",
        help="Exit with code 1 when near-duplicate groups are found.",
    )
    return parser.parse_args()


def _print_text_report(report: dict) -> None:
    summary = report["summary"]
    boundary = report["report_boundary"]
    print("[signal-near-duplicates] scope: read-only local signal output near-duplicate report")
    print(f"[signal-near-duplicates] mode: {boundary['mode']}")
    print(
        "[signal-near-duplicates] records: "
        f"files={summary['files_scanned']} scannable={summary['scannable_record_count']}"
    )
    print(
        "[signal-near-duplicates] groups: "
        f"total={summary['duplicate_group_count']} "
        f"category_vs_article={summary['category_vs_article_group_count']} "
        f"same_content_different_url={summary['same_content_different_url_group_count']}"
    )
    print(
        "[signal-near-duplicates] cleanup: "
        f"recommendations={summary['cleanup_recommendation_counts']} "
        f"requires_human_review={summary['groups_requiring_human_review']}"
    )
    print(f"[signal-near-duplicates] readiness: {summary['readiness']}")
    for path, count in summary["file_record_counts"].items():
        print(f"[signal-near-duplicates] file: {path} records={count}")

    for index, group in enumerate(report["groups"], start=1):
        print(
            f"- GROUP {index} type={group['duplicate_type']} "
            f"records={group['record_count']} urls={group['distinct_url_count']} "
            f"paths={','.join(group['paths'])}"
        )
        preferred = group.get("preferred_record")
        if preferred:
            print(
                "  preferred: "
                f"title={preferred['title']!r} source={preferred['source']!r} url={preferred['normalized_url']}"
            )
        recommendation = group["cleanup_recommendation"]
        print(
            "  recommendation: "
            f"safe_action={recommendation['safe_action']} "
            f"requires_human_review={recommendation['requires_human_review']} "
            f"demote_candidates={recommendation['demote_candidate_ids']}"
        )
        print(f"  reason: {recommendation['reason']}")
        for record in group["records"]:
            print(
                "  record: "
                f"path={record['path']} source={record['source']!r} "
                f"title={record['title']!r} url={record['normalized_url']} "
                f"source_excerpt_length={record['source_excerpt_length']}"
            )


def main() -> int:
    args = _parse_args()
    root = Path(args.root)
    files = [Path(file) for file in args.files] if args.files else list(DEFAULT_SIGNAL_FILES)
    report = build_signal_near_duplicate_report(
        signal_files=files,
        root=root,
        include_records=not args.summary_only,
    )
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        _print_text_report(report)
    return signal_near_duplicate_exit_code(report, fail_on_findings=args.fail_on_findings)


if __name__ == "__main__":
    raise SystemExit(main())
