import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.run_pytest_suites import (  # noqa: E402
    BACKEND_ROOT,
    INGESTION_TESTS,
    PYTEST_BASETEMP_ROOT,
    build_suite_command,
    build_suite_environment,
    main,
    prepare_basetemp_parent,
)


def test_ingestion_suite_contains_only_explicit_ingestion_targets():
    command = build_suite_command("ingestion", ("--collect-only",))

    assert all(path in command for path in INGESTION_TESTS)
    assert "tests" not in command
    assert "backend/tests" not in command
    assert command[-1] == "--collect-only"


def test_backend_suite_excludes_every_ingestion_target():
    command = build_suite_command("backend")

    assert "tests" in command
    assert "backend/tests" in command
    assert all(f"--ignore={path}" in command for path in INGESTION_TESTS)


def test_each_suite_uses_a_unique_ignored_repository_basetemp():
    first_command = build_suite_command("ingestion")
    second_command = build_suite_command("ingestion")

    first_option = next(
        argument for argument in first_command if argument.startswith("--basetemp=")
    )
    second_option = next(
        argument for argument in second_command if argument.startswith("--basetemp=")
    )
    first_path = Path(first_option.split("=", 1)[1])
    second_path = Path(second_option.split("=", 1)[1])

    assert first_path.is_relative_to(PYTEST_BASETEMP_ROOT)
    assert first_path.name == "ingestion"
    assert first_path != second_path
    ignored = subprocess.run(
        [
            "git",
            "check-ignore",
            "--quiet",
            str(first_path.relative_to(REPO_ROOT)),
        ],
        cwd=REPO_ROOT,
        check=False,
    )
    assert ignored.returncode == 0


@pytest.mark.parametrize(
    "pytest_args",
    (("--basetemp=custom-temp",), ("--basetemp", "custom-temp")),
)
def test_explicit_basetemp_override_is_preserved(pytest_args):
    command = build_suite_command("backend", pytest_args)

    assert sum(argument.startswith("--basetemp") for argument in command) == 1
    assert all("codex-basetemp" not in argument for argument in command)


@pytest.mark.parametrize(
    "option_builder",
    (
        lambda path: (f"--basetemp={path}",),
        lambda path: ("--basetemp", str(path)),
    ),
)
def test_prepare_basetemp_parent_creates_missing_parent(tmp_path, option_builder):
    basetemp = tmp_path / "missing" / "nested" / "suite"

    prepare_basetemp_parent(("pytest", *option_builder(basetemp)))

    assert basetemp.parent.is_dir()
    assert not basetemp.exists()


def test_each_suite_receives_its_own_import_root(monkeypatch):
    monkeypatch.delenv("PYTHONPATH", raising=False)

    ingestion_paths = build_suite_environment("ingestion")["PYTHONPATH"].split(
        os.pathsep
    )
    backend_paths = build_suite_environment("backend")["PYTHONPATH"].split(os.pathsep)

    assert ingestion_paths == [str(REPO_ROOT)]
    assert backend_paths == [str(BACKEND_ROOT), str(REPO_ROOT)]


def test_unknown_suite_is_rejected():
    with pytest.raises(ValueError, match="Unknown suite"):
        build_suite_command("unknown")

    with pytest.raises(ValueError, match="Unknown suite"):
        build_suite_environment("unknown")


def test_main_preserves_a_real_suite_failure_exit_code(monkeypatch):
    def fake_run_suite(suite, pytest_args):
        return 7 if suite == "backend" else 0

    monkeypatch.setattr("scripts.run_pytest_suites.run_suite", fake_run_suite)

    assert main([]) == 1
