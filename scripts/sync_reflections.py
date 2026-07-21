from __future__ import annotations

import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.reflection_service import trigger_sync  # noqa: E402


def main() -> None:
    state = trigger_sync(force_full="--full" in sys.argv)
    print("Reflection sync completed")
    print(state.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
