from __future__ import annotations

import argparse
import json

from app.services.project_snapshot_refresh_service import refresh_due_project_snapshots


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Refresh due Light Snapshots for active connected projects.")
    parser.add_argument("--interval-hours", type=int, default=24)
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main() -> int:
    args = _parser().parse_args()
    result = refresh_due_project_snapshots(
        interval_hours=max(1, args.interval_hours),
        dry_run=bool(args.dry_run),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result["counts"]["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
