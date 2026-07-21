from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"

repo_root_text = str(REPO_ROOT)
if repo_root_text not in sys.path:
    sys.path.insert(0, repo_root_text)

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

from app.services.model_router_service import router_startup_diagnostics  # noqa: E402
from app.services.source_health_service import check_subscription_source_health  # noqa: E402
from scripts.check_github_scalar_backfill_readiness import (  # noqa: E402
    build_github_scalar_backfill_readiness_report,
)
from scripts.check_github_scalar_coverage import (  # noqa: E402
    DEFAULT_SIGNAL_FILES,
    build_github_scalar_coverage_report,
)


DEFAULT_SUBSCRIPTION_SETTINGS_DIR = BACKEND_ROOT / "data" / "settings" / "subscriptions"
TELEMETRY_SUMMARY_PATH = BACKEND_ROOT / "data" / "output" / "model_router_usage_summary.json"
MODEL_CREDENTIAL_ENV_KEYS = (
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "PERPLEXITY_API_KEY",
)
SOURCE_CREDENTIAL_ENV_KEYS = (
    "GITHUB_TOKEN",
    "GITHUB_API_TOKEN",
)
GITHUB_RATE_LIMIT_URL = "https://api.github.com/rate_limit"
LiveFetcher = Callable[[str], tuple[int | None, str, bytes]]


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_read_json(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None


def _relative_path(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _env_presence(keys: tuple[str, ...]) -> dict[str, bool]:
    return {key: bool(str(os.getenv(key) or "").strip()) for key in keys}


def _github_token() -> str:
    return str(os.getenv("GITHUB_TOKEN") or os.getenv("GITHUB_API_TOKEN") or "").strip()


def _default_route_summary() -> dict[str, Any]:
    return {
        "total_events": 0,
        "last_event_at": None,
        "success_rate": 0.0,
        "failure_rate": 0.0,
        "fallback_count": 0,
        "time_windows": {},
    }


def load_route_summary() -> dict[str, Any]:
    payload = _safe_read_json(TELEMETRY_SUMMARY_PATH)
    if not isinstance(payload, dict):
        return _default_route_summary()
    summary = _default_route_summary()
    summary.update(payload)
    return summary


def _subscription_settings_summary(
    *,
    settings_dir: Path,
    user_id: str,
    root: Path,
) -> dict[str, Any]:
    safe_user_id = (user_id or "admin_default").strip().replace("/", "_").replace("\\", "_") or "admin_default"
    path = settings_dir / f"{safe_user_id}.json"
    payload = _safe_read_json(path)
    sources = payload.get("sources") if isinstance(payload, dict) else []
    source_items = [item for item in sources if isinstance(item, dict)] if isinstance(sources, list) else []
    enabled_count = sum(1 for item in source_items if item.get("enabled", True))
    source_type_counts = Counter(str(item.get("type") or "custom_url").strip() or "custom_url" for item in source_items)
    last_updated_epoch = None
    if path.exists():
        try:
            last_updated_epoch = path.stat().st_mtime
        except OSError:
            last_updated_epoch = None

    status = "ok" if isinstance(payload, dict) else "warning"
    warnings = [] if isinstance(payload, dict) else [f"subscription settings not found or unreadable for {safe_user_id}"]
    return {
        "status": status,
        "warnings": warnings,
        "user_id": safe_user_id,
        "local_path": _relative_path(path, root),
        "exists": path.exists(),
        "source_count": len(source_items),
        "enabled_source_count": enabled_count,
        "source_type_counts": dict(sorted(source_type_counts.items())),
        "last_updated_epoch": last_updated_epoch,
    }


def _load_subscription_sources(*, settings_dir: Path, user_id: str) -> list[dict[str, Any]]:
    safe_user_id = (user_id or "admin_default").strip().replace("/", "_").replace("\\", "_") or "admin_default"
    payload = _safe_read_json(settings_dir / f"{safe_user_id}.json")
    sources = payload.get("sources") if isinstance(payload, dict) else []
    return [item for item in sources if isinstance(item, dict)] if isinstance(sources, list) else []


def _signal_output_inventory(*, signal_files: list[Path], root: Path) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    missing_count = 0
    unreadable_count = 0
    for raw_path in signal_files:
        path = raw_path if raw_path.is_absolute() else root / raw_path
        payload = _safe_read_json(path)
        exists = path.exists()
        if not exists:
            missing_count += 1
        elif payload is None:
            unreadable_count += 1
        stat = None
        if exists:
            try:
                stat = path.stat()
            except OSError:
                stat = None
        files.append(
            {
                "path": _relative_path(path, root),
                "exists": exists,
                "readable_json": payload is not None,
                "size_bytes": stat.st_size if stat else None,
                "last_updated_epoch": stat.st_mtime if stat else None,
            }
        )

    warnings = []
    if missing_count:
        warnings.append(f"{missing_count} configured signal output file(s) are missing")
    if unreadable_count:
        warnings.append(f"{unreadable_count} configured signal output file(s) are unreadable JSON")
    return {
        "status": "warning" if warnings else "ok",
        "warnings": warnings,
        "files": files,
        "summary": {
            "file_count": len(files),
            "existing_files": sum(1 for item in files if item["exists"]),
            "readable_json_files": sum(1 for item in files if item["readable_json"]),
            "missing_files": missing_count,
            "unreadable_json_files": unreadable_count,
        },
    }


def _model_router_report() -> dict[str, Any]:
    diagnostics = router_startup_diagnostics()
    telemetry = load_route_summary()
    warnings = [str(item) for item in diagnostics.get("warnings") or []]
    env_presence = _env_presence(MODEL_CREDENTIAL_ENV_KEYS)
    return {
        "status": "warning" if warnings else "ok",
        "warnings": warnings,
        "routes": diagnostics.get("routes") or {},
        "route_count": len(_as_dict(diagnostics.get("routes"))),
        "telemetry": {
            "total_events": telemetry.get("total_events", 0),
            "last_event_at": telemetry.get("last_event_at"),
            "success_rate": telemetry.get("success_rate", 0.0),
            "failure_rate": telemetry.get("failure_rate", 0.0),
            "fallback_count": telemetry.get("fallback_count", 0),
            "time_windows": telemetry.get("time_windows", {}),
        },
        "credential_env_presence": env_presence,
    }


def _github_scalar_reports(
    *,
    signal_files: list[Path],
    root: Path,
    include_records: bool,
) -> dict[str, Any]:
    coverage = build_github_scalar_coverage_report(
        signal_files=signal_files,
        root=root,
        include_records=include_records,
    )
    backfill = build_github_scalar_backfill_readiness_report(
        signal_files=signal_files,
        root=root,
        include_records=include_records,
    )

    coverage_summary = _as_dict(coverage.get("summary"))
    backfill_summary = _as_dict(backfill.get("summary"))
    mismatch_count = int(coverage_summary.get("rows_with_scalar_mismatch") or 0)
    coverage_counts = _as_dict(coverage_summary.get("coverage_state_counts"))
    gap_count = sum(
        int(count or 0)
        for state, count in coverage_counts.items()
        if state != "complete_core_scalar_coverage"
    )
    live_required_counts = _as_dict(backfill_summary.get("live_api_required_scalar_counts"))
    live_required_count = sum(int(count or 0) for count in live_required_counts.values())
    warnings = []
    if mismatch_count:
        warnings.append(f"{mismatch_count} GitHub record(s) have scalar mismatches")
    if gap_count:
        warnings.append(f"{gap_count} GitHub record(s) lack complete core scalar coverage")
    if live_required_count:
        warnings.append(f"{live_required_count} scalar field(s) require live GitHub API for full coverage")

    return {
        "status": "warning" if warnings else "ok",
        "warnings": warnings,
        "credential_env_presence": _env_presence(SOURCE_CREDENTIAL_ENV_KEYS),
        "coverage": coverage,
        "backfill_readiness": backfill,
    }


def _default_github_api_fetcher(url: str) -> tuple[int | None, str, bytes]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "AI-Radar-Doctor/1.0",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = _github_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, headers=headers, method="GET")
    with urlopen(request, timeout=10) as response:  # noqa: S310 - explicit opt-in live probe
        return response.status, response.headers.get("content-type", ""), response.read(4096)


def _github_api_probe(*, fetcher: LiveFetcher | None = None) -> dict[str, Any]:
    checker = fetcher or _default_github_api_fetcher
    try:
        status_code, content_type, _body = checker(GITHUB_RATE_LIMIT_URL)
    except HTTPError as exc:
        return {
            "status": "warning",
            "checked": True,
            "url": GITHUB_RATE_LIMIT_URL,
            "http_status": exc.code,
            "content_type": exc.headers.get("content-type", "") if exc.headers else "",
            "reason_code": f"http_{exc.code}",
            "message": f"GitHub API probe returned HTTP {exc.code}.",
        }
    except (TimeoutError, URLError, OSError) as exc:
        return {
            "status": "warning",
            "checked": True,
            "url": GITHUB_RATE_LIMIT_URL,
            "http_status": None,
            "content_type": "",
            "reason_code": type(exc).__name__,
            "message": "GitHub API probe failed before a response was received.",
        }

    ok = status_code is not None and 200 <= status_code < 400
    return {
        "status": "ok" if ok else "warning",
        "checked": True,
        "url": GITHUB_RATE_LIMIT_URL,
        "http_status": status_code,
        "content_type": content_type,
        "reason_code": "github_api_reachable" if ok else f"http_{status_code}",
        "message": "GitHub API probe succeeded." if ok else f"GitHub API probe returned HTTP {status_code}.",
    }


def _live_source_probe_report(
    *,
    enabled: bool,
    settings_dir: Path,
    user_id: str,
    max_sources: int,
    source_health_fetcher: LiveFetcher | None = None,
    github_fetcher: LiveFetcher | None = None,
) -> dict[str, Any]:
    if not enabled:
        return {
            "status": "skipped",
            "warnings": [],
            "mode": "skipped_by_default",
            "summary": {
                "source_probe_count": 0,
                "source_probe_limit": max_sources,
                "source_probe_truncated": False,
                "github_api_checked": False,
            },
            "subscription_source_health": {"items": [], "summary": {}},
            "github_api": {"status": "skipped", "checked": False},
        }

    source_probe_limit = max(0, max_sources)
    sources = [
        item
        for item in _load_subscription_sources(settings_dir=settings_dir, user_id=user_id)
        if item.get("enabled", True)
    ]
    limited_sources = sources[:source_probe_limit]
    source_health = check_subscription_source_health(limited_sources, fetcher=source_health_fetcher)
    source_summary = _as_dict(source_health.get("summary"))
    github_api = _github_api_probe(fetcher=github_fetcher)

    warnings: list[str] = []
    warning_count = int(source_summary.get("warning") or 0)
    error_count = int(source_summary.get("error") or 0)
    if warning_count or error_count:
        warnings.append(f"{warning_count} source probe warning(s), {error_count} source probe error(s)")
    if github_api.get("status") != "ok":
        warnings.append(str(github_api.get("message") or "GitHub API probe did not report ok status"))
    if len(sources) > len(limited_sources):
        warnings.append(f"source probe limited to {len(limited_sources)} of {len(sources)} enabled source(s)")

    return {
        "status": "warning" if warnings else "ok",
        "warnings": warnings,
        "mode": "explicit_live_probe",
        "summary": {
            "source_probe_count": len(limited_sources),
            "source_probe_limit": source_probe_limit,
            "source_probe_truncated": len(sources) > len(limited_sources),
            "github_api_checked": True,
        },
        "subscription_source_health": source_health,
        "github_api": github_api,
    }


def build_radar_doctor_report(
    *,
    root: Path = REPO_ROOT,
    signal_files: list[Path] | None = None,
    subscription_settings_dir: Path | None = None,
    user_id: str = "admin_default",
    include_records: bool = False,
    live_source_probe: bool = False,
    max_live_sources: int = 10,
    source_health_fetcher: LiveFetcher | None = None,
    github_fetcher: LiveFetcher | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    files = signal_files if signal_files is not None else list(DEFAULT_SIGNAL_FILES)
    settings_dir = subscription_settings_dir or DEFAULT_SUBSCRIPTION_SETTINGS_DIR
    signal_inventory = _signal_output_inventory(signal_files=files, root=root)
    source_settings = _subscription_settings_summary(
        settings_dir=settings_dir,
        user_id=user_id,
        root=root,
    )
    model_router = _model_router_report()
    github_scalars = _github_scalar_reports(
        signal_files=files,
        root=root,
        include_records=include_records,
    )
    live_probe = _live_source_probe_report(
        enabled=live_source_probe,
        settings_dir=settings_dir,
        user_id=user_id,
        max_sources=max_live_sources,
        source_health_fetcher=source_health_fetcher,
        github_fetcher=github_fetcher,
    )

    section_statuses = {
        "model_router": model_router["status"],
        "subscription_settings": source_settings["status"],
        "signal_outputs": signal_inventory["status"],
        "github_scalars": github_scalars["status"],
        "live_source_probe": live_probe["status"],
    }
    all_warnings = [
        *model_router["warnings"],
        *source_settings["warnings"],
        *signal_inventory["warnings"],
        *github_scalars["warnings"],
        *live_probe["warnings"],
    ]
    overall_status = "warning" if any(status not in {"ok", "skipped"} for status in section_statuses.values()) else "ok"

    return {
        "report_boundary": {
            "mode": "read_only_local_doctor",
            "generated_at": _utc_now_iso(),
            "write_boundary": "This doctor does not write, backfill, deploy, or mutate runtime state.",
            "network_boundary": (
                "Live connector probes are skipped by default and run only when --live-source-probe is explicitly set."
            ),
            "quality_boundary": (
                "Operational health, credential presence, and coverage gaps are advisory diagnostics only; "
                "they are not source scoring, source-truth judgments, Project Takeaway gates, or action eligibility."
            ),
            "credential_boundary": "Credential checks report environment-variable presence only; secret values are never emitted.",
            "telemetry_summary_path": _relative_path(TELEMETRY_SUMMARY_PATH, root),
        },
        "summary": {
            "overall_status": overall_status,
            "section_statuses": section_statuses,
            "warning_count": len(all_warnings),
            "warnings": all_warnings,
        },
        "model_router": model_router,
        "sources": {
            "subscription_settings": source_settings,
            "signal_outputs": signal_inventory,
            "live_source_probe": live_probe,
        },
        "github_scalars": github_scalars,
    }


def radar_doctor_exit_code(report: dict[str, Any], *, fail_on_warning: bool = False) -> int:
    if not fail_on_warning:
        return 0
    return 1 if _as_dict(report.get("summary")).get("overall_status") != "ok" else 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only local AI Radar doctor. Aggregates model-router diagnostics, "
            "source configuration inventory, GitHub scalar coverage, and backfill readiness."
        )
    )
    parser.add_argument("--root", default=str(REPO_ROOT), help="Repository root. Defaults to current checkout.")
    parser.add_argument("--user-id", default="admin_default", help="Local subscription settings user id.")
    parser.add_argument(
        "--subscription-settings-dir",
        default=str(DEFAULT_SUBSCRIPTION_SETTINGS_DIR),
        help="Directory containing local subscription settings JSON files.",
    )
    parser.add_argument(
        "--file",
        dest="files",
        action="append",
        help="Signal JSON file to scan. Can be passed multiple times. Defaults to local GitHub signal outputs.",
    )
    parser.add_argument("--include-records", action="store_true", help="Include per-record GitHub scalar rows.")
    parser.add_argument(
        "--live-source-probe",
        action="store_true",
        help="Opt in to live connector probes for subscription feed URLs and GitHub API reachability.",
    )
    parser.add_argument(
        "--max-live-sources",
        type=int,
        default=10,
        help="Maximum enabled subscription sources to probe when --live-source-probe is set.",
    )
    parser.add_argument("--format", choices=["text", "json"], default="text", help="Report format.")
    parser.add_argument(
        "--fail-on-warning",
        action="store_true",
        help="Exit with code 1 when any doctor section reports warning status.",
    )
    return parser.parse_args()


def _print_text_report(report: dict[str, Any]) -> None:
    boundary = report["report_boundary"]
    summary = report["summary"]
    model = report["model_router"]
    sources = report["sources"]
    github = report["github_scalars"]
    coverage_summary = github["coverage"]["summary"]
    backfill_summary = github["backfill_readiness"]["summary"]

    print("[radar-doctor] scope: read-only local AI Radar doctor")
    print(f"[radar-doctor] mode: {boundary['mode']}")
    print(f"[radar-doctor] write-boundary: {boundary['write_boundary']}")
    print(f"[radar-doctor] network-boundary: {boundary['network_boundary']}")
    print(f"[radar-doctor] quality-boundary: {boundary['quality_boundary']}")
    print(f"[radar-doctor] status: {summary['overall_status']} warnings={summary['warning_count']}")
    print(f"[radar-doctor] sections: {summary['section_statuses']}")
    print(
        "[radar-doctor] model-router: "
        f"routes={model['route_count']} telemetry_events={model['telemetry']['total_events']} "
        f"fallbacks={model['telemetry']['fallback_count']} warnings={len(model['warnings'])}"
    )
    subscription = sources["subscription_settings"]
    signal_outputs = sources["signal_outputs"]["summary"]
    print(
        "[radar-doctor] sources: "
        f"subscription_sources={subscription['source_count']} enabled={subscription['enabled_source_count']} "
        f"signal_files={signal_outputs['readable_json_files']}/{signal_outputs['file_count']}"
    )
    live_probe = sources["live_source_probe"]
    live_summary = live_probe["summary"]
    github_api = live_probe["github_api"]
    print(
        "[radar-doctor] live-source-probe: "
        f"status={live_probe['status']} mode={live_probe['mode']} "
        f"sources={live_summary['source_probe_count']}/{live_summary['source_probe_limit']} "
        f"github_api={github_api.get('status')}"
    )
    print(
        "[radar-doctor] github-scalars: "
        f"github_records={coverage_summary['github_record_count']} "
        f"with_resolution={coverage_summary['rows_with_scalar_resolution']} "
        f"with_mismatch={coverage_summary['rows_with_scalar_mismatch']}"
    )
    print(
        "[radar-doctor] github-coverage: "
        f"states={coverage_summary['coverage_state_counts']} "
        f"missing={coverage_summary['missing_scalar_counts']}"
    )
    print(
        "[radar-doctor] github-backfill: "
        f"states={backfill_summary['refresh_state_counts']} "
        f"live_api_required={backfill_summary['live_api_required_scalar_counts']}"
    )
    for warning in summary.get("warnings") or []:
        print(f"- warning: {warning}")


def main() -> int:
    args = _parse_args()
    root = Path(args.root)
    files = [Path(file) for file in args.files] if args.files else list(DEFAULT_SIGNAL_FILES)
    report = build_radar_doctor_report(
        root=root,
        signal_files=files,
        subscription_settings_dir=Path(args.subscription_settings_dir),
        user_id=args.user_id,
        include_records=args.include_records,
        live_source_probe=args.live_source_probe,
        max_live_sources=args.max_live_sources,
    )
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        _print_text_report(report)
    return radar_doctor_exit_code(report, fail_on_warning=args.fail_on_warning)


if __name__ == "__main__":
    raise SystemExit(main())
