from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.intelligence.tracking.agent_friction_tracking import (  # noqa: E402
    build_agent_friction_tracking_report,
    build_agent_watch_tracking_state,
    build_friction_tracking_state,
)


DEFAULT_OUTPUT_DIR = REPO_ROOT / "data" / "output"


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _print_section(title: str, items: list[dict[str, Any]], *, limit: int) -> None:
    print(f"\n{title}")
    if not items:
        print("  none")
        return
    for item in items[:limit]:
        metric_name = item.get("metric_name") or "metric"
        metric_delta = item.get("metric_delta_1d")
        delta_label = "n/a" if metric_delta is None else str(metric_delta)
        seen_days = item.get("seen_days")
        seen_label = f" seen={seen_days}d" if seen_days is not None else ""
        print(
            "  - "
            f"{item.get('title') or item.get('entity_id')} "
            f"[{item.get('status')}] "
            f"momentum={item.get('momentum_score')} "
            f"{metric_name}={item.get('current_metric')} "
            f"delta={delta_label}"
            f"{seen_label}"
        )


def _print_counts(title: str, counts: dict[str, Any]) -> None:
    ordered_statuses = ["new", "heating", "revived", "sustained", "cooling", "dropped"]
    parts = [f"{status}={counts.get(status, 0)}" for status in ordered_statuses]
    print(f"{title}: " + ", ".join(parts))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a read-only Agent Watch / Friction Signals tracking report from local artifacts."
    )
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory containing AI Radar output JSON.")
    parser.add_argument("--limit", type=int, default=5, help="Number of rows to print per section.")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    generated_at = datetime.now(timezone.utc).isoformat()
    agent_snapshots = _load_json(output_dir / "agent_watch_repo_snapshots.json")
    friction_signals = _load_json(output_dir / "friction_signals.json")
    previous_agent_state = _load_json(output_dir / "agent_watch_tracking_state.json")
    previous_friction_state = _load_json(output_dir / "friction_tracking_state.json")
    has_previous_state = bool(previous_agent_state or previous_friction_state)

    agent_state = build_agent_watch_tracking_state(
        agent_snapshots,
        previous_agent_state or None,
        generated_at=generated_at,
    )
    friction_state = build_friction_tracking_state(
        friction_signals,
        previous_friction_state or None,
        generated_at=generated_at,
    )
    report = build_agent_friction_tracking_report(
        agent_state,
        friction_state,
        generated_at=generated_at,
    )

    print("Agent/Friction Tracking Report")
    print(f"generated_at: {generated_at}")
    if not has_previous_state:
        print("note: no prior tracking state found; first run can classify active items as new, not true 1-day growth.")
    _print_counts("agent counts", agent_state.get("counts_by_status", {}))
    _print_counts("friction counts", friction_state.get("counts_by_status", {}))

    _print_section("Agent Watch - New Today", report["agent_watch"]["new_today"], limit=args.limit)
    _print_section("Agent Watch - Heating", report["agent_watch"]["heating"], limit=args.limit)
    _print_section("Agent Watch - Sustained", report["agent_watch"]["sustained"], limit=args.limit)
    _print_section("Agent Watch - Fastest Growing", report["agent_watch"]["fastest_growing"], limit=args.limit)
    _print_section("Agent Watch - Cooling / Dropped", report["agent_watch"]["cooling_or_dropped"], limit=args.limit)

    _print_section("Friction - New Today", report["friction_signals"]["new_today"], limit=args.limit)
    _print_section("Friction - Heating", report["friction_signals"]["heating"], limit=args.limit)
    _print_section("Friction - Sustained", report["friction_signals"]["sustained"], limit=args.limit)
    _print_section("Friction - Fastest Growing", report["friction_signals"]["fastest_growing"], limit=args.limit)
    _print_section("Friction - Cooling / Dropped", report["friction_signals"]["cooling_or_dropped"], limit=args.limit)

    print("\nFriction - Recurring Pain Clusters")
    clusters = report["friction_signals"]["recurring_pain_clusters"][: args.limit]
    if not clusters:
        print("  none")
    for cluster in clusters:
        print(f"  - {cluster.get('pain_cluster_key')}: {cluster.get('active_signal_count')}")

    print("\nConvergence Candidates")
    candidates = report["convergence_candidates"][: args.limit]
    if not candidates:
        print("  none")
    for candidate in candidates:
        agent = candidate.get("agent", {})
        topics = ", ".join(candidate.get("overlapping_friction_topics", []))
        print(f"  - {agent.get('title') or agent.get('entity_id')} overlaps: {topics}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
