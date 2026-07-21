"""Run the prompt skill export check with backend/app importable.

The pre-commit hook runs from the repository root, while the Python package
`app` lives under `backend/app`. This wrapper makes the backend directory
available on PYTHONPATH before delegating to the real module.
"""

from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    backend_dir = repo_root / "backend"

    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH")
    pythonpath_parts = [str(backend_dir)]
    if existing_pythonpath:
        pythonpath_parts.append(existing_pythonpath)
    env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)
    os.environ["PYTHONPATH"] = env["PYTHONPATH"]
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))

    args = sys.argv[1:] or ["--check"]
    sys.argv = ["python -m app.prompts.export_skills", *args]
    try:
        runpy.run_module("app.prompts.export_skills", run_name="__main__", alter_sys=True)
    except SystemExit as exc:
        if isinstance(exc.code, int):
            return exc.code
        return 1 if exc.code else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
