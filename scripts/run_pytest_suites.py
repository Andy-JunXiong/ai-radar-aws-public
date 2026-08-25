from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Sequence
from uuid import uuid4


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
PYTEST_CONFIG = REPO_ROOT / "pytest.ini"
PYTEST_BASETEMP_ROOT = REPO_ROOT / ".pytest_cache" / "codex-basetemp"

INGESTION_TESTS = (
    "tests/test_agent_friction_tracking.py",
    "tests/test_friction_signal_processor.py",
    "tests/test_llm_executor.py",
    "tests/test_model_router.py",
    "tests/test_obsidian_export.py",
    "tests/test_pipeline_metrics_smoke.py",
    "tests/test_pipeline_signal_history_preservation.py",
    "tests/test_topic_classifier.py",
)

SUITE_ORDER = ("ingestion", "backend")


def _has_explicit_basetemp(pytest_args: Sequence[str]) -> bool:
    return any(
        argument == "--basetemp" or argument.startswith("--basetemp=")
        for argument in pytest_args
    )


def build_suite_basetemp(suite: str) -> Path:
    if suite not in SUITE_ORDER:
        raise ValueError(f"Unknown suite: {suite}")
    return PYTEST_BASETEMP_ROOT / uuid4().hex / suite


def prepare_basetemp_parent(command: Sequence[str]) -> None:
    basetemp: str | None = None
    for index, argument in enumerate(command):
        if argument.startswith("--basetemp="):
            basetemp = argument.split("=", 1)[1]
            break
        if argument == "--basetemp" and index + 1 < len(command):
            basetemp = command[index + 1]
            break

    if not basetemp:
        return

    basetemp_path = Path(basetemp)
    if not basetemp_path.is_absolute():
        basetemp_path = REPO_ROOT / basetemp_path
    basetemp_path.parent.mkdir(parents=True, exist_ok=True)


def build_suite_environment(suite: str) -> dict[str, str]:
    environment = os.environ.copy()
    if suite == "ingestion":
        import_roots = [REPO_ROOT]
    elif suite == "backend":
        import_roots = [BACKEND_ROOT, REPO_ROOT]
    else:
        raise ValueError(f"Unknown suite: {suite}")

    existing_pythonpath = environment.get("PYTHONPATH")
    if existing_pythonpath:
        import_roots.append(Path(existing_pythonpath))
    environment["PYTHONPATH"] = os.pathsep.join(str(path) for path in import_roots)
    return environment


def build_suite_command(suite: str, pytest_args: Sequence[str] = ()) -> list[str]:
    base = [
        sys.executable,
        "-m",
        "pytest",
        "-c",
        str(PYTEST_CONFIG),
    ]

    if not _has_explicit_basetemp(pytest_args):
        base.append(f"--basetemp={build_suite_basetemp(suite)}")

    if suite == "ingestion":
        targets = list(INGESTION_TESTS)
    elif suite == "backend":
        targets = ["tests", "backend/tests"]
        targets.extend(f"--ignore={path}" for path in INGESTION_TESTS)
    else:
        raise ValueError(f"Unknown suite: {suite}")

    return [*base, *targets, *pytest_args]


def run_suite(suite: str, pytest_args: Sequence[str] = ()) -> int:
    command = build_suite_command(suite, pytest_args)
    prepare_basetemp_parent(command)
    environment = build_suite_environment(suite)
    print(f"\n===== PYTEST SUITE: {suite} =====", flush=True)
    print(" ".join(command), flush=True)
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        env=environment,
        check=False,
    )
    return completed.returncode


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run ingestion and backend pytest suites in isolated Python processes "
            "so their separate top-level app packages cannot collide."
        )
    )
    parser.add_argument(
        "--suite",
        choices=("all", *SUITE_ORDER),
        default="all",
        help="Run both suites or one isolated suite (default: all).",
    )
    parsed, pytest_args = parser.parse_known_args(argv)
    suites = SUITE_ORDER if parsed.suite == "all" else (parsed.suite,)

    results: dict[str, int] = {}
    for suite in suites:
        results[suite] = run_suite(suite, pytest_args)

    print("\n===== PYTEST SUITE SUMMARY =====", flush=True)
    for suite in suites:
        exit_code = results[suite]
        status = "PASS" if exit_code == 0 else "FAIL"
        print(f"{suite}: {status} (exit {exit_code})", flush=True)

    return 0 if all(code == 0 for code in results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
