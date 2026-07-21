from __future__ import annotations

import re
from typing import Any


SCALAR_RESOLUTION_SCHEMA_VERSION = 1
CANONICAL_GITHUB_API = "github_api"
PROVENANCE_CANONICAL_API = "canonical_api_observed"
PROVENANCE_THIRD_PARTY_SUMMARY = "third_party_summary"
PROVENANCE_UNKNOWN = "unknown"

SUPPORTED_SCALARS = ("stars", "license", "archived", "created_at", "updated_at")
LOW_CONFIDENCE_LICENSE_VALUES = {"", "noassertion", "unknown", "other", "none", "null"}


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _scalar_display_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).strip().split())


def _metadata(signal: dict[str, Any]) -> dict[str, Any]:
    metadata = signal.get("metadata")
    return metadata if isinstance(metadata, dict) else {}


def _github_repo_from_url(url: str) -> str:
    match = re.search(r"github\.com/([^/\s]+)/([^/\s#?]+)", url or "", flags=re.IGNORECASE)
    if not match:
        return ""
    owner = match.group(1).strip()
    repo = match.group(2).strip().replace(".git", "")
    return f"{owner}/{repo}".strip("/")


def _github_repo_id(signal: dict[str, Any], metadata: dict[str, Any]) -> str:
    repo_name = _clean_text(
        metadata.get("repo_name")
        or metadata.get("full_name")
        or metadata.get("repository")
        or signal.get("repo_name")
    )
    if repo_name:
        return repo_name
    return _github_repo_from_url(_clean_text(signal.get("url") or signal.get("link") or signal.get("source_url")))


def _normalize_scalar_name(name: str) -> str:
    normalized = _clean_text(name).lower()
    aliases = {
        "repo_stars": "stars",
        "stargazers_count": "stars",
        "star_count": "stars",
        "license_spdx_id": "license",
        "license_key": "license",
        "is_archived": "archived",
    }
    return aliases.get(normalized, normalized)


def _normalize_scalar_map(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    scalars: dict[str, Any] = {}
    raw_values = value.get("values") if isinstance(value.get("values"), dict) else value
    for raw_name, raw_value in raw_values.items():
        name = _normalize_scalar_name(str(raw_name))
        if name in SUPPORTED_SCALARS and raw_value not in (None, ""):
            scalars[name] = raw_value
    return scalars


def _canonical_scalars(signal: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
    explicit = _normalize_scalar_map(
        signal.get("canonical_scalars") or metadata.get("canonical_scalars")
    )
    if explicit:
        return explicit

    scalars: dict[str, Any] = {}
    for source_name, scalar_name in (
        ("repo_stars", "stars"),
        ("stargazers_count", "stars"),
        ("license", "license"),
        ("license_spdx_id", "license"),
        ("archived", "archived"),
        ("created_at", "created_at"),
        ("updated_at", "updated_at"),
    ):
        value = metadata.get(source_name)
        if value not in (None, ""):
            scalars[scalar_name] = value
    return scalars


def _claimed_scalars(signal: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
    return _normalize_scalar_map(signal.get("claimed_scalars") or metadata.get("claimed_scalars"))


def _license_raw_value(metadata: dict[str, Any], canonical_value: Any) -> Any:
    if metadata.get("license") not in (None, ""):
        return metadata.get("license")
    if metadata.get("license_spdx_id") not in (None, ""):
        return metadata.get("license_spdx_id")
    return canonical_value


def _scalar_resolution_metadata(name: str, canonical_value: Any, metadata: dict[str, Any]) -> dict[str, Any]:
    if name != "license":
        return {
            "resolution_confidence": "high",
            "can_contradict_claim": True,
            "resolution_notes": ["platform_scalar_machine_observed"],
        }

    detected = _clean_text(canonical_value)
    normalized = detected.lower()
    if normalized in LOW_CONFIDENCE_LICENSE_VALUES:
        confidence = "low"
        notes = [
            "github_license_detection_observed",
            "github_license_noassertion_or_unknown",
            "license_detection_not_definitive",
        ]
    else:
        confidence = "medium"
        notes = [
            "github_license_detection_observed",
            "license_detection_not_definitive",
        ]

    return {
        "resolution_confidence": confidence,
        "can_contradict_claim": False,
        "raw_value": _license_raw_value(metadata, canonical_value),
        "detected_spdx_id": detected,
        "resolution_notes": notes,
    }


def _scalar_status(name: str, canonical_value: Any, claimed_value: Any, resolution: dict[str, Any]) -> str:
    if claimed_value in (None, ""):
        return "canonical_observed"
    if _clean_text(canonical_value).lower() == _clean_text(claimed_value).lower():
        return "matched"
    if name == "license":
        if resolution.get("resolution_confidence") == "low":
            return "uncertain"
        return "platform_delta"
    return "mismatch"


def build_canonical_scalar_resolution(signal: dict[str, Any]) -> dict[str, Any]:
    """Build advisory canonical scalar metadata from already-available signal fields.

    This helper does not perform network calls. It records canonical-looking
    values only when an upstream collector or caller already provided them.
    """

    if not isinstance(signal, dict):
        return {}

    metadata = _metadata(signal)
    repo_id = _github_repo_id(signal, metadata)
    canonical = _canonical_scalars(signal, metadata)
    if not repo_id or not canonical:
        return {}

    claimed = _claimed_scalars(signal, metadata)
    resolved_at = _clean_text(
        signal.get("canonical_scalars_resolved_at")
        or metadata.get("canonical_scalars_resolved_at")
        or signal.get("collected_at")
        or signal.get("timestamp")
    )
    scalars: list[dict[str, Any]] = []
    status_counts: dict[str, int] = {}

    for name in SUPPORTED_SCALARS:
        if name not in canonical:
            continue
        resolution_metadata = _scalar_resolution_metadata(name, canonical[name], metadata)
        status = _scalar_status(name, canonical[name], claimed.get(name), resolution_metadata)
        item = {
            "name": name,
            "canonical_value": canonical[name],
            "claimed_value": claimed.get(name),
            "status": status,
            "canonical_source": CANONICAL_GITHUB_API,
            "canonical_provenance_tier": PROVENANCE_CANONICAL_API,
            "claimed_provenance_tier": (
                PROVENANCE_THIRD_PARTY_SUMMARY if name in claimed else PROVENANCE_UNKNOWN
            ),
            **resolution_metadata,
        }
        scalars.append(item)
        status_counts[item["status"]] = status_counts.get(item["status"], 0) + 1

    if not scalars:
        return {}

    return {
        "schema_version": SCALAR_RESOLUTION_SCHEMA_VERSION,
        "entity_type": "github_repo",
        "entity_id": repo_id,
        "canonical_source": CANONICAL_GITHUB_API,
        "resolved_at": resolved_at,
        "provenance_tier": PROVENANCE_CANONICAL_API,
        "scalars": scalars,
        "summary": {
            "total": len(scalars),
            **dict(sorted(status_counts.items())),
            "matched": status_counts.get("matched", 0),
            "mismatch": status_counts.get("mismatch", 0),
            "canonical_observed": status_counts.get("canonical_observed", 0),
        },
    }


def scalar_resolution_text(resolution: dict[str, Any]) -> str:
    if not isinstance(resolution, dict):
        return ""
    entity_id = _clean_text(resolution.get("entity_id"))
    source = _clean_text(resolution.get("canonical_source")) or CANONICAL_GITHUB_API
    parts = []
    for scalar in resolution.get("scalars") or []:
        if not isinstance(scalar, dict):
            continue
        name = _clean_text(scalar.get("name"))
        canonical_value = _scalar_display_text(scalar.get("canonical_value"))
        if name and canonical_value:
            parts.append(f"{name}={canonical_value}")
    if not entity_id or not parts:
        return ""
    return f"{source} observed {entity_id}: {', '.join(parts)}."
