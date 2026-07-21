from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any


PROVENANCE_SCHEMA_VERSION = 1
LEGACY_PROVENANCE_SCHEMA_VERSION = 0


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_model_provenance(
    *,
    provider: str,
    model_id: str,
    task_type: str,
    route_key: str,
    router_source: str,
    prompt_template_id: str,
    prompt_template_version: str,
    inference_params: dict[str, Any] | None = None,
    model_version: str = "",
    generated_at: str | None = None,
) -> dict[str, Any]:
    normalized_inference_params = _normalize_inference_params(inference_params)
    normalized_provider = _clean(provider)
    normalized_model_id = _clean(model_id)
    normalized_model_version = _clean(model_version)
    normalized_prompt_version = _clean(prompt_template_version) or "unknown"

    return {
        "provider": normalized_provider,
        "model_id": normalized_model_id,
        "model_version": normalized_model_version,
        "task_type": _clean(task_type),
        "route_key": _clean(route_key),
        "router_source": _normalize_router_source(router_source),
        "prompt_template_id": _clean(prompt_template_id),
        "prompt_template_version": normalized_prompt_version,
        "inference_params": normalized_inference_params,
        "deterministic_fingerprint": build_model_provenance_fingerprint(
            provider=normalized_provider,
            model_id=normalized_model_id,
            model_version=normalized_model_version,
            prompt_template_version=normalized_prompt_version,
            inference_params=normalized_inference_params,
        ),
        "generated_at": generated_at or utc_now_iso(),
        "provenance_schema_version": PROVENANCE_SCHEMA_VERSION,
    }


def build_model_provenance_fingerprint(
    *,
    provider: str,
    model_id: str,
    model_version: str,
    prompt_template_version: str,
    inference_params: dict[str, Any],
) -> str:
    serialized = json.dumps(
        {
            "provider": _clean(provider),
            "model_id": _clean(model_id),
            "model_version": _clean(model_version),
            "prompt_template_version": _clean(prompt_template_version),
            "inference_params": _normalize_inference_params(inference_params),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def normalize_model_provenance(value: Any) -> dict[str, Any]:
    if isinstance(value, dict) and value.get("provenance_schema_version") == PROVENANCE_SCHEMA_VERSION:
        return value

    return {
        "provenance_schema_version": LEGACY_PROVENANCE_SCHEMA_VERSION,
        "provenance_completeness": "legacy",
    }


def _normalize_inference_params(value: dict[str, Any] | None) -> dict[str, Any]:
    params = dict(value) if isinstance(value, dict) else {}
    return {
        "temperature": params.get("temperature"),
        "max_tokens": params.get("max_tokens"),
        "top_p": params.get("top_p"),
        "stop_sequences": params.get("stop_sequences") if isinstance(params.get("stop_sequences"), list) else [],
    }


def _normalize_router_source(value: str) -> str:
    normalized = _clean(value).lower()
    if normalized == "env_router":
        return "env"
    if normalized == "default_router":
        return "hard_default"
    return normalized or "unknown"


def _clean(value: Any) -> str:
    return str(value or "").strip()
