from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.metrics_event_service import METRICS_DIR  # noqa: E402
from app.services.metrics_summary_service import write_daily_metrics_summary  # noqa: E402
from app.services.metrics_summary_service import write_monthly_metrics_summary  # noqa: E402
from app.services.metrics_summary_service import write_weekly_metrics_summary  # noqa: E402


RAW_EVENT_CATEGORIES = {
    "artifact_writes": "jsonl",
    "pipeline_runs": "json",
    "collector_runs": "jsonl",
    "llm_calls": "jsonl",
    "verification_events": "jsonl",
}


def _date_key_from_path(path: Path) -> str | None:
    try:
        date.fromisoformat(path.stem)
    except ValueError:
        return None
    return path.stem


def discover_metric_dates(metrics_dir: Path) -> list[str]:
    dates: set[str] = set()

    for category, extension in RAW_EVENT_CATEGORIES.items():
        category_dir = metrics_dir / category
        if not category_dir.exists():
            continue
        for path in category_dir.glob(f"*.{extension}"):
            date_key = _date_key_from_path(path)
            if date_key:
                dates.add(date_key)

    return sorted(dates)


def refresh_metrics_summaries(metrics_dir: Path, dates: list[str]) -> list[Path]:
    written: list[Path] = []
    touched_weeks: set[str] = set()
    touched_months: set[str] = set()

    for date_key in sorted(set(dates)):
        parsed_date = date.fromisoformat(date_key)
        iso_week = parsed_date.isocalendar()
        week_key = f"{iso_week.year}-W{iso_week.week:02d}"
        month_key = date_key[:7]

        written.append(write_daily_metrics_summary(date_key, metrics_dir=metrics_dir))
        touched_weeks.add(week_key)
        touched_months.add(month_key)

    for week_key in sorted(touched_weeks):
        written.append(write_weekly_metrics_summary(week_key, metrics_dir=metrics_dir))

    for month_key in sorted(touched_months):
        written.append(write_monthly_metrics_summary(month_key, metrics_dir=metrics_dir))

    return written


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Refresh file-backed Metrics / Monitoring daily, weekly, and monthly summaries."
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--date",
        help="Refresh one YYYY-MM-DD date. Weekly and monthly rollups for that date are refreshed too.",
    )
    group.add_argument(
        "--all",
        action="store_true",
        help="Refresh summaries for every raw metrics event date found locally.",
    )
    parser.add_argument(
        "--metrics-dir",
        default=str(METRICS_DIR),
        help="Metrics root directory. Defaults to data/output/metrics.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    metrics_dir = Path(args.metrics_dir).resolve()

    if args.date:
        try:
            date.fromisoformat(args.date)
        except ValueError:
            print(f"[metrics-refresh] invalid --date value: {args.date}", flush=True)
            return 2
        dates = [args.date]
    elif args.all:
        dates = discover_metric_dates(metrics_dir)
    else:
        dates = [date.today().isoformat()]

    if not dates:
        print(f"[metrics-refresh] no raw metrics dates found under {metrics_dir}", flush=True)
        return 0

    written = refresh_metrics_summaries(metrics_dir, dates)
    print(f"[metrics-refresh] refreshed dates: {', '.join(dates)}", flush=True)
    for path in written:
        print(f"[metrics-refresh] wrote: {path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
