from __future__ import annotations

import json
import os
from datetime import date as Date
from pathlib import Path
from typing import Any

from .metrics_event_service import METRICS_DIR


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            events.append(payload)
    return events


def _load_output_signals(root: Path) -> list[dict[str, Any]]:
    payload = _read_json(root.parent / "signals.json")
    if isinstance(payload, dict):
        raw_signals = payload.get("signals")
    else:
        raw_signals = payload
    if not isinstance(raw_signals, list):
        return []
    return [item for item in raw_signals if isinstance(item, dict)]


def _s3_metrics_enabled(metrics_dir: Path | None) -> bool:
    if metrics_dir is not None:
        return False
    value = str(os.getenv("AI_RADAR_METRICS_S3_ENABLED", "true")).strip().lower()
    return value not in {"0", "false", "no", "off"}


def _read_s3_metrics_json(key: str) -> dict[str, Any] | None:
    try:
        from .s3_reader import read_json

        payload = read_json(key)
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _list_s3_metrics_keys() -> list[str]:
    try:
        from .s3_reader import list_keys

        return list_keys("metrics/")
    except Exception:
        return []


def _signal_activity_dates(root: Path) -> set[str]:
    dates: set[str] = set()
    for signal in _load_output_signals(root):
        date_key = _date_prefix(signal.get("collected_at"))
        if len(date_key) == 10:
            try:
                Date.fromisoformat(date_key)
            except ValueError:
                continue
            dates.add(date_key)
    return dates


def _raw_metric_event_dates(root: Path) -> set[str]:
    dates: set[str] = set()
    categories = {
        "artifact_writes": "jsonl",
        "pipeline_runs": "json",
        "collector_runs": "jsonl",
        "llm_calls": "jsonl",
        "verification_events": "jsonl",
        "signal_timeline_loads": "jsonl",
    }
    for category, extension in categories.items():
        category_dir = root / category
        if not category_dir.exists():
            continue
        for path in category_dir.glob(f"*.{extension}"):
            try:
                Date.fromisoformat(path.stem)
            except ValueError:
                continue
            dates.add(path.stem)
    return dates


def _date_prefix(value: Any) -> str:
    if not value:
        return ""
    return str(value)[:10]


def _as_runs(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        return [payload]
    return []


def _success_rate(events: list[dict[str, Any]]) -> float | None:
    if not events:
        return None
    successes = sum(1 for event in events if event.get("success") is True)
    return round(successes / len(events), 4)


def _sum_number(events: list[dict[str, Any]], field: str) -> float:
    total = 0.0
    for event in events:
        value = event.get(field)
        if isinstance(value, (int, float)):
            total += float(value)
    return total


def _avg_number(events: list[dict[str, Any]], field: str) -> float | None:
    values = [
        float(event[field])
        for event in events
        if isinstance(event.get(field), (int, float))
    ]
    if not values:
        return None
    return round(sum(values) / len(values), 2)


def _as_number(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0


def _weighted_rate(
    summaries: list[dict[str, Any]],
    section: str,
    rate_field: str,
    weight_field: str,
) -> float | None:
    weighted_total = 0.0
    total_weight = 0.0

    for summary in summaries:
        payload = summary.get(section)
        if not isinstance(payload, dict):
            continue
        rate = payload.get(rate_field)
        weight = payload.get(weight_field)
        if not isinstance(rate, (int, float)) or not isinstance(weight, (int, float)):
            continue
        if weight <= 0:
            continue
        weighted_total += float(rate) * float(weight)
        total_weight += float(weight)

    if not total_weight:
        return None
    return round(weighted_total / total_weight, 4)


def _sum_summary_field(
    summaries: list[dict[str, Any]],
    section: str,
    field: str,
) -> float:
    return sum(
        _as_number(summary.get(section, {}).get(field))
        for summary in summaries
        if isinstance(summary.get(section), dict)
    )


def _avg_summary_field(
    summaries: list[dict[str, Any]],
    section: str,
    field: str,
) -> float | None:
    values = [
        float(summary[section][field])
        for summary in summaries
        if isinstance(summary.get(section), dict)
        and isinstance(summary[section].get(field), (int, float))
    ]
    if not values:
        return None
    return round(sum(values) / len(values), 2)


def _load_daily_summaries(root: Path) -> list[dict[str, Any]]:
    summary_dir = root / "daily_summary"
    if not summary_dir.exists():
        return []

    summaries: list[dict[str, Any]] = []
    for path in sorted(summary_dir.glob("*.json")):
        payload = _read_json(path)
        if isinstance(payload, dict) and isinstance(payload.get("date"), str):
            summaries.append(payload)
    return summaries


def _load_effective_daily_summaries(
    root: Path,
    *,
    through_date: str | None = None,
) -> list[dict[str, Any]]:
    persisted_dates = {
        str(summary.get("date"))
        for summary in _load_daily_summaries(root)
        if summary.get("date")
    }
    candidate_dates = sorted(
        persisted_dates | _raw_metric_event_dates(root) | _signal_activity_dates(root)
    )
    if through_date:
        candidate_dates = [date_key for date_key in candidate_dates if date_key <= through_date]

    summaries: list[dict[str, Any]] = []
    for date_key in candidate_dates:
        loaded = load_daily_metrics_summary(date_key, metrics_dir=root)
        if isinstance(loaded, dict) and isinstance(loaded.get("summary"), dict):
            summaries.append(loaded["summary"])
    return summaries


def _period_ids_from_daily_summaries(
    category: str,
    daily_summaries: list[dict[str, Any]],
    *,
    limit: int,
) -> list[str]:
    if category == "weekly_summary":
        period_ids = sorted(
            {
                f"{Date.fromisoformat(str(summary['date'])).isocalendar().year}-W{Date.fromisoformat(str(summary['date'])).isocalendar().week:02d}"
                for summary in daily_summaries
                if summary.get("date")
            }
        )
    else:
        period_ids = sorted(
            {
                str(summary.get("date"))[:7]
                for summary in daily_summaries
                if summary.get("date")
            }
        )
    return period_ids[-max(limit, 0) :] if limit > 0 else []


def _build_period_summaries_from_daily(
    category: str,
    daily_summaries: list[dict[str, Any]],
    *,
    limit: int,
) -> list[dict[str, Any]]:
    period_ids = _period_ids_from_daily_summaries(
        category,
        daily_summaries,
        limit=limit,
    )
    if category == "weekly_summary":
        return [
            _build_period_metrics_summary(
                "week",
                period_id,
                [
                    summary
                    for summary in daily_summaries
                    if _date_matches_week(str(summary.get("date")), period_id)
                ],
            )
            for period_id in period_ids
        ]

    return [
        _build_period_metrics_summary(
            "month",
            period_id,
            [
                summary
                for summary in daily_summaries
                if _date_matches_month(str(summary.get("date")), period_id)
            ],
        )
        for period_id in period_ids
    ]


def _date_matches_week(date_text: str, year_week: str) -> bool:
    try:
        parsed = Date.fromisoformat(date_text)
    except ValueError:
        return False
    iso = parsed.isocalendar()
    return f"{iso.year}-W{iso.week:02d}" == year_week


def _date_matches_month(date_text: str, month: str) -> bool:
    return date_text.startswith(f"{month}-")


def _build_period_metrics_summary(
    period_type: str,
    period_id: str,
    summaries: list[dict[str, Any]],
) -> dict[str, Any]:
    summaries = sorted(summaries, key=lambda item: str(item.get("date")))
    dates = [str(summary["date"]) for summary in summaries]
    pipeline_run_count = int(_sum_summary_field(summaries, "pipeline", "run_count"))
    pipeline_success_count = sum(
        1
        for summary in summaries
        if isinstance(summary.get("pipeline"), dict)
        and summary["pipeline"].get("success") is True
    )
    verified_insight_count = int(
        _sum_summary_field(summaries, "verification", "verified_insight_count")
    )
    llm_cost = _sum_summary_field(summaries, "llm", "estimated_cost")
    artifact_write_count = int(
        _sum_summary_field(summaries, "artifacts", "write_count")
    )
    artifact_failed_write_count = int(
        _sum_summary_field(summaries, "artifacts", "failed_write_count")
    )
    artifact_total_bytes = int(_sum_summary_field(summaries, "artifacts", "total_bytes"))
    latest_signal_collected_at = max(
        (
            str(summary["signals"]["latest_collected_at"])
            for summary in summaries
            if isinstance(summary.get("signals"), dict)
            and summary["signals"].get("latest_collected_at")
        ),
        default=None,
    )

    failed_collectors: set[str] = set()
    for summary in summaries:
        collectors = summary.get("collectors")
        if not isinstance(collectors, dict):
            continue
        for collector_name in collectors.get("failed_collectors") or []:
            if isinstance(collector_name, str):
                failed_collectors.add(collector_name)

    return {
        "period_type": period_type,
        "period_id": period_id,
        "date_count": len(summaries),
        "dates": dates,
        "pipeline": {
            "run_count": pipeline_run_count,
            "success_count": pipeline_success_count,
            "success_rate": (
                round(pipeline_success_count / len(summaries), 4)
                if summaries
                else None
            ),
            "avg_duration_seconds": _avg_summary_field(
                summaries, "pipeline", "duration_seconds"
            ),
            "error_count": int(_sum_summary_field(summaries, "pipeline", "error_count")),
            "artifact_written_count": int(
                _sum_summary_field(summaries, "pipeline", "artifact_written_count")
            ),
        },
        "artifacts": {
            "write_count": artifact_write_count,
            "signals_file_written": any(
                isinstance(summary.get("artifacts"), dict)
                and summary["artifacts"].get("signals_file_written") is True
                for summary in summaries
            ),
            "daily_radar_file_written": any(
                isinstance(summary.get("artifacts"), dict)
                and summary["artifacts"].get("daily_radar_file_written") is True
                for summary in summaries
            ),
            "total_bytes": artifact_total_bytes,
            "failed_write_count": artifact_failed_write_count,
        },
        "collectors": {
            "total_runs": int(_sum_summary_field(summaries, "collectors", "total_runs")),
            "success_rate": _weighted_rate(
                summaries, "collectors", "success_rate", "total_runs"
            ),
            "total_items_fetched": int(
                _sum_summary_field(summaries, "collectors", "total_items_fetched")
            ),
            "total_items_normalized": int(
                _sum_summary_field(summaries, "collectors", "total_items_normalized")
            ),
            "total_items_written": int(
                _sum_summary_field(summaries, "collectors", "total_items_written")
            ),
            "error_count": int(_sum_summary_field(summaries, "collectors", "error_count")),
            "retry_count": int(_sum_summary_field(summaries, "collectors", "retry_count")),
            "failed_collectors": sorted(failed_collectors),
        },
        "signals": {
            "collected_count": int(
                _sum_summary_field(summaries, "signals", "collected_count")
            ),
            "published_count": int(
                _sum_summary_field(summaries, "signals", "published_count")
            ),
            "latest_collected_at": latest_signal_collected_at,
            "source_count": int(_sum_summary_field(summaries, "signals", "source_count")),
        },
        "timeline_loads": {
            "load_count": int(
                _sum_summary_field(summaries, "timeline_loads", "load_count")
            ),
            "success_rate": _weighted_rate(
                summaries, "timeline_loads", "success_rate", "load_count"
            ),
            "avg_duration_ms": _weighted_rate(
                summaries, "timeline_loads", "avg_duration_ms", "load_count"
            ),
            "slow_load_count": int(
                _sum_summary_field(summaries, "timeline_loads", "slow_load_count")
            ),
            "stale_local_snapshot_count": int(
                _sum_summary_field(
                    summaries,
                    "timeline_loads",
                    "stale_local_snapshot_count",
                )
            ),
        },
            "llm": {
                "call_count": int(_sum_summary_field(summaries, "llm", "call_count")),
                "success_rate": _weighted_rate(summaries, "llm", "success_rate", "call_count"),
                "fallback_rate": _weighted_rate(summaries, "llm", "fallback_rate", "call_count"),
                "error_count": int(_sum_summary_field(summaries, "llm", "error_count")),
            "retry_count": int(_sum_summary_field(summaries, "llm", "retry_count")),
            "avg_latency_ms": _weighted_rate(
                summaries, "llm", "avg_latency_ms", "call_count"
            ),
            "estimated_cost": round(llm_cost, 6),
            "estimated_cost_per_verified_insight": (
                round(llm_cost / verified_insight_count, 6)
                if verified_insight_count
                else None
            ),
            "json_validation_pass_rate": _weighted_rate(
                summaries, "llm", "json_validation_pass_rate", "call_count"
            ),
            "json_repair_count": int(_sum_summary_field(summaries, "llm", "json_repair_count")),
        },
        "verification": {
            "verified_insight_count": verified_insight_count,
            "downgrade_rate": _weighted_rate(
                summaries, "verification", "downgrade_rate", "verified_insight_count"
            ),
            "unsupported_claim_rate": _weighted_rate(
                summaries,
                "verification",
                "unsupported_claim_rate",
                "verified_insight_count",
            ),
            "watch_only_count": int(
                _sum_summary_field(summaries, "verification", "watch_only_count")
            ),
            "action_blocked_count": int(
                _sum_summary_field(summaries, "verification", "action_blocked_count")
            ),
        },
    }


def build_daily_metrics_summary(
    date: str,
    *,
    metrics_dir: Path | None = None,
) -> dict[str, Any]:
    root = metrics_dir or METRICS_DIR
    pipeline_runs = _as_runs(_read_json(root / "pipeline_runs" / f"{date}.json"))
    artifact_writes = _read_jsonl(root / "artifact_writes" / f"{date}.jsonl")
    collector_runs = _read_jsonl(root / "collector_runs" / f"{date}.jsonl")
    llm_calls = _read_jsonl(root / "llm_calls" / f"{date}.jsonl")
    verification_events = _read_jsonl(root / "verification_events" / f"{date}.jsonl")
    signal_timeline_loads = _read_jsonl(root / "signal_timeline_loads" / f"{date}.jsonl")
    signals = _load_output_signals(root)

    latest_pipeline = pipeline_runs[-1] if pipeline_runs else {}
    collected_signals = [
        signal for signal in signals if _date_prefix(signal.get("collected_at")) == date
    ]
    published_signals = [
        signal for signal in signals if _date_prefix(signal.get("published_at")) == date
    ]
    signal_sources = {
        str(signal.get("source"))
        for signal in collected_signals
        if signal.get("source")
    }
    latest_signal_collected_at = max(
        (str(signal.get("collected_at")) for signal in collected_signals if signal.get("collected_at")),
        default=None,
    )
    fallback_count = sum(1 for event in llm_calls if event.get("fallback_used") is True)
    llm_error_count = sum(1 for event in llm_calls if event.get("success") is False)
    llm_cost = _sum_number(llm_calls, "estimated_cost")
    llm_json_validation_events = [
        event for event in llm_calls if isinstance(event.get("json_validation_passed"), bool)
    ]
    llm_json_validation_pass_count = sum(
        1 for event in llm_json_validation_events if event.get("json_validation_passed") is True
    )
    verified_insight_count = len(verification_events)
    downgrade_count = sum(
        1 for event in verification_events if event.get("downgrade_applied") is True
    )
    unsupported_claim_count = int(_sum_number(verification_events, "unsupported_claim_count"))
    claim_count = int(_sum_number(verification_events, "claim_count"))
    timeline_load_source_mix: dict[str, int] = {}
    for event in signal_timeline_loads:
        source = str(event.get("load_source") or "unknown")
        timeline_load_source_mix[source] = timeline_load_source_mix.get(source, 0) + 1
    timeline_stale_snapshot_count = sum(
        1
        for event in signal_timeline_loads
        if event.get("local_snapshot_status") == "stale"
    )

    return {
        "date": date,
        "pipeline": {
            "success": latest_pipeline.get("success"),
            "duration_seconds": latest_pipeline.get("duration_seconds"),
            "error_count": latest_pipeline.get("error_count", 0),
            "run_count": len(pipeline_runs),
            "artifact_written_count": latest_pipeline.get("artifact_written_count"),
        },
        "artifacts": {
            "write_count": len(artifact_writes),
            "signals_file_written": any(
                event.get("artifact_name") == "signals" for event in artifact_writes
            ),
            "daily_radar_file_written": any(
                event.get("artifact_name") == "daily_radar"
                for event in artifact_writes
            ),
            "total_bytes": int(_sum_number(artifact_writes, "size_bytes")),
            "failed_write_count": sum(
                1 for event in artifact_writes if event.get("success") is False
            ),
        },
        "collectors": {
            "total_runs": len(collector_runs),
            "success_rate": _success_rate(collector_runs),
            "total_items_fetched": int(_sum_number(collector_runs, "items_fetched")),
            "total_items_normalized": int(_sum_number(collector_runs, "items_normalized")),
            "total_items_written": int(_sum_number(collector_runs, "items_written")),
            "error_count": int(_sum_number(collector_runs, "error_count")),
            "retry_count": int(_sum_number(collector_runs, "retry_count")),
            "failed_collectors": [
                event.get("collector_name")
                for event in collector_runs
                if event.get("success") is False and event.get("collector_name")
            ],
        },
        "signals": {
            "collected_count": len(collected_signals),
            "published_count": len(published_signals),
            "latest_collected_at": latest_signal_collected_at,
            "source_count": len(signal_sources),
        },
        "timeline_loads": {
            "load_count": len(signal_timeline_loads),
            "success_rate": _success_rate(signal_timeline_loads),
            "avg_duration_ms": _avg_number(signal_timeline_loads, "duration_ms"),
            "slow_load_count": sum(
                1
                for event in signal_timeline_loads
                if isinstance(event.get("duration_ms"), (int, float))
                and float(event.get("duration_ms")) >= 20000
            ),
            "stale_local_snapshot_count": timeline_stale_snapshot_count,
            "source_mix": timeline_load_source_mix,
            "latest_published_date": max(
                (
                    str(event.get("latest_published_date"))
                    for event in signal_timeline_loads
                    if event.get("latest_published_date")
                ),
                default=None,
            ),
            "latest_collected_date": max(
                (
                    str(event.get("latest_collected_date"))
                    for event in signal_timeline_loads
                    if event.get("latest_collected_date")
                ),
                default=None,
            ),
        },
        "llm": {
            "call_count": len(llm_calls),
            "success_rate": _success_rate(llm_calls),
            "fallback_rate": (
                round(fallback_count / len(llm_calls), 4) if llm_calls else None
            ),
            "error_count": llm_error_count,
            "retry_count": int(_sum_number(llm_calls, "retry_count")),
            "avg_latency_ms": _avg_number(llm_calls, "latency_ms"),
            "estimated_cost": round(llm_cost, 6),
            "estimated_cost_per_verified_insight": (
                round(llm_cost / verified_insight_count, 6)
                if verified_insight_count
                else None
            ),
            "json_validation_pass_rate": (
                round(llm_json_validation_pass_count / len(llm_json_validation_events), 4)
                if llm_json_validation_events
                else None
            ),
            "json_repair_count": sum(
                1 for event in llm_calls if event.get("json_repair_used") is True
            ),
        },
        "verification": {
            "verified_insight_count": verified_insight_count,
            "downgrade_rate": (
                round(downgrade_count / len(verification_events), 4)
                if verification_events
                else None
            ),
            "unsupported_claim_rate": (
                round(unsupported_claim_count / claim_count, 4) if claim_count else None
            ),
            "watch_only_count": sum(
                1
                for event in verification_events
                if "watch_only" in (event.get("allowed_downstream_actions") or [])
            ),
            "action_blocked_count": sum(
                1
                for event in verification_events
                if "action" in (event.get("blocked_downstream_actions") or [])
            ),
        },
    }


def write_daily_metrics_summary(
    date: str,
    *,
    metrics_dir: Path | None = None,
) -> Path:
    root = metrics_dir or METRICS_DIR
    summary = build_daily_metrics_summary(date, metrics_dir=root)
    summary_dir = root / "daily_summary"
    summary_dir.mkdir(parents=True, exist_ok=True)
    summary_path = summary_dir / f"{date}.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return summary_path


def build_weekly_metrics_summary(
    year_week: str,
    *,
    metrics_dir: Path | None = None,
) -> dict[str, Any]:
    root = metrics_dir or METRICS_DIR
    summaries = [
        summary
        for summary in _load_daily_summaries(root)
        if _date_matches_week(str(summary.get("date")), year_week)
    ]
    return _build_period_metrics_summary("week", year_week, summaries)


def write_weekly_metrics_summary(
    year_week: str,
    *,
    metrics_dir: Path | None = None,
) -> Path:
    root = metrics_dir or METRICS_DIR
    summary = build_weekly_metrics_summary(year_week, metrics_dir=root)
    summary_dir = root / "weekly_summary"
    summary_dir.mkdir(parents=True, exist_ok=True)
    summary_path = summary_dir / f"{year_week}.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return summary_path


def build_monthly_metrics_summary(
    month: str,
    *,
    metrics_dir: Path | None = None,
) -> dict[str, Any]:
    root = metrics_dir or METRICS_DIR
    summaries = [
        summary
        for summary in _load_daily_summaries(root)
        if _date_matches_month(str(summary.get("date")), month)
    ]
    return _build_period_metrics_summary("month", month, summaries)


def write_monthly_metrics_summary(
    month: str,
    *,
    metrics_dir: Path | None = None,
) -> Path:
    root = metrics_dir or METRICS_DIR
    summary = build_monthly_metrics_summary(month, metrics_dir=root)
    summary_dir = root / "monthly_summary"
    summary_dir.mkdir(parents=True, exist_ok=True)
    summary_path = summary_dir / f"{month}.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return summary_path


def load_daily_metrics_summary(
    date: str | None = None,
    *,
    metrics_dir: Path | None = None,
) -> dict[str, Any] | None:
    root = metrics_dir or METRICS_DIR
    summary_dir = root / "daily_summary"
    use_s3 = _s3_metrics_enabled(metrics_dir)

    if date:
        if use_s3:
            s3_key = f"metrics/daily_summary/{date}.json"
            payload = _read_s3_metrics_json(s3_key)
            if isinstance(payload, dict):
                return {
                    "date": str(payload.get("date") or date),
                    "summary": payload,
                    "path": s3_key,
                    "exists": True,
                    "data_source": "s3",
                }

        summary_path = summary_dir / f"{date}.json"
        payload = _read_json(summary_path)
        if isinstance(payload, dict):
            return {
                "date": str(payload.get("date") or date),
                "summary": payload,
                "path": str(summary_path),
                "exists": True,
                "data_source": "local_file",
            }

        # Read-only fallback: aggregate from raw event files without writing a summary file.
        summary = build_daily_metrics_summary(date, metrics_dir=root)
        has_any_events = any(
            [
                summary["pipeline"]["run_count"],
                summary["artifacts"]["write_count"],
                summary["collectors"]["total_runs"],
                summary["signals"]["collected_count"],
                summary["signals"]["published_count"],
                summary["llm"]["call_count"],
                summary["verification"]["verified_insight_count"],
                summary["timeline_loads"]["load_count"],
            ]
        )
        if not has_any_events:
            return None
        return {
            "date": date,
            "summary": summary,
            "path": str(summary_path),
            "exists": False,
            "data_source": "local_raw_events",
        }

    if use_s3:
        s3_key = "metrics/latest/daily_summary.json"
        payload = _read_s3_metrics_json(s3_key)
        if isinstance(payload, dict):
            return {
                "date": str(payload.get("date") or ""),
                "summary": payload,
                "path": s3_key,
                "exists": True,
                "data_source": "s3",
            }

    if not summary_dir.exists():
        return None

    candidates = sorted(summary_dir.glob("*.json"))
    if not candidates:
        return None

    latest_path = candidates[-1]
    payload = _read_json(latest_path)
    if not isinstance(payload, dict):
        return None

    return {
        "date": str(payload.get("date") or latest_path.stem),
        "summary": payload,
        "path": str(latest_path),
        "exists": True,
        "data_source": "local_file",
    }


def load_metrics_summaries(
    category: str = "daily_summary",
    *,
    through_date: str | None = None,
    limit: int = 5,
    metrics_dir: Path | None = None,
) -> list[dict[str, Any]]:
    categories = {
        "daily_summary": "json",
        "weekly_summary": "json",
        "monthly_summary": "json",
    }
    if category not in categories:
        return []

    if _s3_metrics_enabled(metrics_dir):
        prefix = f"metrics/{category}/"
        keys = sorted(
            key
            for key in _list_s3_metrics_keys()
            if key.startswith(prefix) and key.endswith(".json")
        )
        if through_date and category == "daily_summary":
            keys = [key for key in keys if Path(key).stem <= through_date]
        keys = keys[-max(limit, 0) :] if limit > 0 else []

        summaries: list[dict[str, Any]] = []
        for key in keys:
            payload = _read_s3_metrics_json(key)
            if isinstance(payload, dict):
                summaries.append(payload)
        if summaries:
            if category in {"weekly_summary", "monthly_summary"}:
                daily_payloads: list[dict[str, Any]] = []
                daily_keys = sorted(
                    key
                    for key in _list_s3_metrics_keys()
                    if key.startswith("metrics/daily_summary/")
                    and key.endswith(".json")
                )
                for daily_key in daily_keys:
                    payload = _read_s3_metrics_json(daily_key)
                    if isinstance(payload, dict) and payload.get("date"):
                        daily_payloads.append(payload)
                period_summaries = _build_period_summaries_from_daily(
                    category,
                    daily_payloads,
                    limit=limit,
                )
                if period_summaries:
                    return period_summaries
            return summaries

    root = metrics_dir or METRICS_DIR
    category_dir = root / category
    paths = sorted(category_dir.glob("*.json")) if category_dir.exists() else []

    if through_date and category == "daily_summary":
        paths = [path for path in paths if path.stem <= through_date]

    fallback_dates = sorted(_raw_metric_event_dates(root) | _signal_activity_dates(root))
    if through_date:
        fallback_dates = [date_key for date_key in fallback_dates if date_key <= through_date]

    if category == "daily_summary":
        candidate_dates = sorted({path.stem for path in paths} | set(fallback_dates))
        candidate_dates = candidate_dates[-max(limit, 0) :] if limit > 0 else []
        summaries: list[dict[str, Any]] = []
        for date_key in candidate_dates:
            loaded = load_daily_metrics_summary(date_key, metrics_dir=root)
            if isinstance(loaded, dict) and isinstance(loaded.get("summary"), dict):
                summaries.append(loaded["summary"])
        return summaries

    daily_summaries = _load_effective_daily_summaries(root, through_date=through_date)
    if daily_summaries:
        return _build_period_summaries_from_daily(
            category,
            daily_summaries,
            limit=limit,
        )

    paths = paths[-max(limit, 0) :] if limit > 0 else []

    summaries: list[dict[str, Any]] = []
    for path in paths:
        payload = _read_json(path)
        if isinstance(payload, dict):
            summaries.append(payload)
    if summaries:
        return summaries

    if category in {"weekly_summary", "monthly_summary"}:
        daily_summaries: list[dict[str, Any]] = []
        for date_key in fallback_dates:
            loaded = load_daily_metrics_summary(date_key, metrics_dir=root)
            if isinstance(loaded, dict) and isinstance(loaded.get("summary"), dict):
                daily_summaries.append(loaded["summary"])

        return _build_period_summaries_from_daily(
            category,
            daily_summaries,
            limit=limit,
        )
    return summaries


def _load_s3_metrics_status(categories: dict[str, str]) -> dict[str, Any] | None:
    keys = [key for key in _list_s3_metrics_keys() if not key.startswith("metrics/latest/")]
    if not keys:
        return None

    category_status: dict[str, dict[str, Any]] = {}
    all_dates: set[str] = set()
    raw_event_dates: set[str] = set()
    latest_summary_date: str | None = None
    latest_summary_path: str | None = None

    for category, extension in categories.items():
        prefix = f"metrics/{category}/"
        suffix = f".{extension}"
        category_keys = sorted(
            key for key in keys if key.startswith(prefix) and key.endswith(suffix)
        )
        dates = [Path(key).stem for key in category_keys]

        if category in {
            "artifact_writes",
            "pipeline_runs",
            "collector_runs",
            "llm_calls",
            "verification_events",
            "signal_timeline_loads",
            "daily_summary",
        }:
            all_dates.update(dates)
        if category in {
            "artifact_writes",
            "pipeline_runs",
            "collector_runs",
            "llm_calls",
            "verification_events",
            "signal_timeline_loads",
        }:
            raw_event_dates.update(dates)

        if category == "daily_summary" and category_keys:
            latest_summary_date = dates[-1]
            latest_summary_path = category_keys[-1]

        category_status[category] = {
            "exists": bool(category_keys),
            "file_count": len(category_keys),
            "latest_date": dates[-1] if dates else None,
            "latest_path": category_keys[-1] if category_keys else None,
        }

    latest_raw_event_date = sorted(raw_event_dates)[-1] if raw_event_dates else None
    pipeline_event_dates = {
        Path(key).stem
        for key in keys
        if key.startswith("metrics/pipeline_runs/") and key.endswith(".json")
    }
    collector_event_dates = {
        Path(key).stem
        for key in keys
        if key.startswith("metrics/collector_runs/") and key.endswith(".jsonl")
    }
    reportable_signal_dates = set(all_dates)
    latest_signal_activity_date = (
        sorted(reportable_signal_dates)[-1] if reportable_signal_dates else None
    )
    missing_summary_dates = sorted(
        date
        for date in raw_event_dates
        if latest_summary_date is None or date > latest_summary_date
    )

    return {
        "metrics_dir": "s3://metrics",
        "data_source": "s3",
        "has_any_metrics": any(item["exists"] for item in category_status.values()) or bool(signal_activity_dates),
        "available_dates": sorted(all_dates),
        "latest_raw_event_date": latest_raw_event_date,
        "latest_signal_activity_date": latest_signal_activity_date,
        "latest_summary_date": latest_summary_date,
        "latest_summary_path": latest_summary_path,
        "is_summary_stale": bool(missing_summary_dates),
        "missing_summary_dates": missing_summary_dates,
        "signal_dates_missing_pipeline_runs": sorted(
            reportable_signal_dates - pipeline_event_dates
        ),
        "signal_dates_missing_collector_runs": sorted(
            reportable_signal_dates - collector_event_dates
        ),
        "categories": category_status,
    }


def load_metrics_status(*, metrics_dir: Path | None = None) -> dict[str, Any]:
    root = metrics_dir or METRICS_DIR
    categories = {
        "artifact_writes": "jsonl",
        "pipeline_runs": "json",
        "collector_runs": "jsonl",
        "llm_calls": "jsonl",
        "verification_events": "jsonl",
        "signal_timeline_loads": "jsonl",
        "daily_summary": "json",
        "weekly_summary": "json",
        "monthly_summary": "json",
    }
    if _s3_metrics_enabled(metrics_dir):
        s3_status = _load_s3_metrics_status(categories)
        if s3_status is not None:
            return s3_status

    category_status: dict[str, dict[str, Any]] = {}
    all_dates: set[str] = set()
    raw_event_dates: set[str] = set()
    signal_activity_dates = _signal_activity_dates(root)
    latest_summary_date: str | None = None
    latest_summary_path: str | None = None

    for category, extension in categories.items():
        category_dir = root / category
        files = sorted(category_dir.glob(f"*.{extension}")) if category_dir.exists() else []
        dates = [path.stem for path in files]
        if category in {
            "artifact_writes",
            "pipeline_runs",
            "collector_runs",
            "llm_calls",
            "verification_events",
            "signal_timeline_loads",
            "daily_summary",
        }:
            all_dates.update(dates)
        if category in {
            "artifact_writes",
            "pipeline_runs",
            "collector_runs",
            "llm_calls",
            "verification_events",
            "signal_timeline_loads",
        }:
            raw_event_dates.update(dates)

        if category == "daily_summary" and files:
            latest_summary = files[-1]
            latest_summary_date = latest_summary.stem
            latest_summary_path = str(latest_summary)

        category_status[category] = {
            "exists": bool(files),
            "file_count": len(files),
            "latest_date": dates[-1] if dates else None,
            "latest_path": str(files[-1]) if files else None,
        }

    latest_raw_event_date = sorted(raw_event_dates)[-1] if raw_event_dates else None
    if raw_event_dates:
        earliest_raw_event_date = sorted(raw_event_dates)[0]
        reportable_signal_dates = {
            date for date in signal_activity_dates if date >= earliest_raw_event_date
        }
    else:
        reportable_signal_dates = signal_activity_dates
    all_dates.update(reportable_signal_dates)
    latest_signal_activity_date = (
        sorted(reportable_signal_dates)[-1] if reportable_signal_dates else None
    )
    pipeline_event_dates = {
        path.stem
        for path in (root / "pipeline_runs").glob("*.json")
        if (root / "pipeline_runs").exists()
    }
    collector_event_dates = {
        path.stem
        for path in (root / "collector_runs").glob("*.jsonl")
        if (root / "collector_runs").exists()
    }
    missing_summary_dates = sorted(
        date
        for date in (raw_event_dates | reportable_signal_dates)
        if latest_summary_date is None or date > latest_summary_date
    )
    signal_dates_missing_pipeline_runs = sorted(
        reportable_signal_dates - pipeline_event_dates
    )
    signal_dates_missing_collector_runs = sorted(
        reportable_signal_dates - collector_event_dates
    )

    return {
        "metrics_dir": str(root),
        "data_source": "local_file",
        "has_any_metrics": any(item["exists"] for item in category_status.values()) or bool(signal_activity_dates),
        "available_dates": sorted(all_dates),
        "latest_raw_event_date": latest_raw_event_date,
        "latest_signal_activity_date": latest_signal_activity_date,
        "latest_summary_date": latest_summary_date,
        "latest_summary_path": latest_summary_path,
        "is_summary_stale": bool(missing_summary_dates),
        "missing_summary_dates": missing_summary_dates,
        "signal_dates_missing_pipeline_runs": signal_dates_missing_pipeline_runs,
        "signal_dates_missing_collector_runs": signal_dates_missing_collector_runs,
        "categories": category_status,
    }
