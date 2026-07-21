from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
METRICS_DIR = REPO_ROOT / "data" / "output" / "metrics"


TEST_GROUPS = [
    [
        "tests/test_metrics_services.py",
        "tests/test_metrics_route.py",
        "tests/test_metrics_app_route.py",
    ],
    [
        "tests/test_pipeline_metrics_smoke.py",
        "tests/test_llm_executor.py",
    ],
    [
        "tests/test_backend_llm_executor_service.py",
        "tests/test_verified_insight_service.py",
        "tests/test_metrics_services.py",
        "tests/test_metrics_route.py",
        "tests/test_metrics_app_route.py",
    ],
]


def _run_pytest(test_paths: list[str]) -> int:
    command = [
        sys.executable,
        "-m",
        "pytest",
        *test_paths,
        "-q",
        "-p",
        "no:cacheprovider",
    ]
    print(f"\n[metrics-smoke] running: {' '.join(command)}", flush=True)
    completed = subprocess.run(command, cwd=REPO_ROOT)
    return completed.returncode


def _latest_summary_path() -> Path | None:
    summary_dir = METRICS_DIR / "daily_summary"
    if not summary_dir.exists():
        return None
    candidates = sorted(summary_dir.glob("*.json"))
    if not candidates:
        return None
    return candidates[-1]


def _print_latest_summary() -> None:
    summary_path = _latest_summary_path()
    if summary_path is None:
        print("\n[metrics-smoke] no local metrics daily summary found.", flush=True)
        return

    try:
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        print(
            f"\n[metrics-smoke] latest summary is not valid JSON: {summary_path}",
            flush=True,
        )
        return

    print(f"\n[metrics-smoke] latest local daily summary: {summary_path}", flush=True)
    print(json.dumps(payload, indent=2, ensure_ascii=False), flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the local Metrics / Monitoring MVP smoke checks."
    )
    parser.add_argument(
        "--show-summary",
        action="store_true",
        help="Print the latest local data/output/metrics daily summary if one exists.",
    )
    args = parser.parse_args()

    for test_group in TEST_GROUPS:
        exit_code = _run_pytest(test_group)
        if exit_code != 0:
            print("\n[metrics-smoke] failed.", flush=True)
            return exit_code

    if args.show_summary:
        _print_latest_summary()

    print("\n[metrics-smoke] passed.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
