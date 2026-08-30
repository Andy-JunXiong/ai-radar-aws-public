from __future__ import annotations

import re
from copy import deepcopy
from typing import Any


TRUTH_MAP_SCHEMA_VERSION = 1
TRUTH_MAP_MAX_ANCHORS = 20
TRUTH_MAP_PATH_MAX_CHARS = 240
TRUTH_MAP_EXCERPT_MIN_CHARS = 400
TRUTH_MAP_EXCERPT_MAX_CHARS = 4000
TRUTH_MAP_DEFAULT_EXCERPT_CHARS = 1600
TRUTH_MAP_CONTENT_MODES = {"excerpt", "metadata_only"}

_TRUTH_MAP_FIELDS = {"schema_version", "anchors"}
_ANCHOR_FIELDS = {"kind", "path", "required", "content_mode", "max_chars"}
_KIND_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,39}$")
_DRIVE_PATH_PATTERN = re.compile(r"^[a-zA-Z]:")
_SECRET_FILENAMES = {
    "credentials",
    "credentials.json",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
    "id_rsa",
    "secret",
    "secrets",
    "secrets.json",
    "token",
    "token.json",
}
_SECRET_DIRECTORIES = {".aws", ".gnupg", ".ssh"}
_SECRET_SUFFIXES = {".key", ".p12", ".pem", ".pfx"}


class TruthMapValidationError(ValueError):
    def __init__(self, errors: list[dict[str, str]]):
        self.errors = errors
        super().__init__("Project Truth Map validation failed.")


def _add_error(errors: list[dict[str, str]], path: str, code: str, message: str) -> None:
    errors.append({"path": path, "code": code, "message": message})


def _is_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_secret_like_path(path: str) -> bool:
    segments = [segment.casefold() for segment in path.split("/")]
    filename = segments[-1]
    if any(segment in _SECRET_DIRECTORIES for segment in segments):
        return True
    if filename == ".env" or filename.startswith(".env."):
        return True
    if filename in _SECRET_FILENAMES:
        return True
    return any(filename.endswith(suffix) for suffix in _SECRET_SUFFIXES)


def _normalize_anchor_path(value: Any, *, error_path: str, errors: list[dict[str, str]]) -> str | None:
    if not isinstance(value, str) or not value.strip():
        _add_error(errors, error_path, "required", "path must be a non-empty repository-relative file path.")
        return None

    normalized = value.strip().replace("\\", "/")
    if len(normalized) > TRUTH_MAP_PATH_MAX_CHARS:
        _add_error(
            errors,
            error_path,
            "path_too_long",
            f"path must be at most {TRUTH_MAP_PATH_MAX_CHARS} characters.",
        )
        return None
    if normalized.startswith("/") or _DRIVE_PATH_PATTERN.match(normalized) or "://" in normalized:
        _add_error(errors, error_path, "absolute_path", "path must be repository-relative.")
        return None
    if normalized.endswith("/"):
        _add_error(errors, error_path, "directory_path", "path must identify a file, not a directory.")
        return None
    if any(character in normalized for character in ("*", "?", "[", "]")):
        _add_error(errors, error_path, "wildcard_path", "wildcards and bracket patterns are not allowed.")
        return None
    if any(ord(character) < 32 for character in normalized):
        _add_error(errors, error_path, "control_character", "path must not contain control characters.")
        return None

    segments = normalized.split("/")
    if any(segment in {"", ".", ".."} for segment in segments):
        _add_error(errors, error_path, "unsafe_segment", "path must not contain empty, '.' or '..' segments.")
        return None
    if _is_secret_like_path(normalized):
        _add_error(errors, error_path, "secret_like_path", "secret-like repository paths cannot be Truth Map anchors.")
        return None
    return normalized


def validate_and_normalize_truth_map(value: Any) -> dict[str, Any]:
    root_path = "metadata.repo_context.truth_map"
    errors: list[dict[str, str]] = []
    if not isinstance(value, dict):
        raise TruthMapValidationError(
            [{"path": root_path, "code": "invalid_type", "message": "truth_map must be an object."}]
        )

    for field in sorted(set(value) - _TRUTH_MAP_FIELDS):
        _add_error(errors, f"{root_path}.{field}", "unknown_field", "field is not allowed in Truth Map schema version 1.")

    schema_version = value.get("schema_version")
    if not _is_integer(schema_version) or schema_version != TRUTH_MAP_SCHEMA_VERSION:
        _add_error(
            errors,
            f"{root_path}.schema_version",
            "unsupported_schema_version",
            f"schema_version must be the integer {TRUTH_MAP_SCHEMA_VERSION}.",
        )

    anchors = value.get("anchors")
    if not isinstance(anchors, list):
        _add_error(errors, f"{root_path}.anchors", "invalid_type", "anchors must be a list.")
        anchors = []
    elif not 1 <= len(anchors) <= TRUTH_MAP_MAX_ANCHORS:
        _add_error(
            errors,
            f"{root_path}.anchors",
            "anchor_count",
            f"anchors must contain between 1 and {TRUTH_MAP_MAX_ANCHORS} entries.",
        )

    normalized_anchors: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    for index, anchor in enumerate(anchors[:TRUTH_MAP_MAX_ANCHORS]):
        anchor_path = f"{root_path}.anchors[{index}]"
        if not isinstance(anchor, dict):
            _add_error(errors, anchor_path, "invalid_type", "anchor must be an object.")
            continue

        anchor_error_count = len(errors)
        for field in sorted(set(anchor) - _ANCHOR_FIELDS):
            _add_error(errors, f"{anchor_path}.{field}", "unknown_field", "field is not allowed for a Truth Map anchor.")

        kind = anchor.get("kind")
        if not isinstance(kind, str) or not _KIND_PATTERN.fullmatch(kind):
            _add_error(
                errors,
                f"{anchor_path}.kind",
                "invalid_kind",
                "kind must be lowercase snake case and contain 1 to 40 characters.",
            )

        normalized_path = _normalize_anchor_path(anchor.get("path"), error_path=f"{anchor_path}.path", errors=errors)
        if normalized_path:
            path_key = normalized_path.casefold()
            if path_key in seen_paths:
                _add_error(errors, f"{anchor_path}.path", "duplicate_path", "anchor paths must be unique.")
            else:
                seen_paths.add(path_key)

        required = anchor.get("required", False)
        if not isinstance(required, bool):
            _add_error(errors, f"{anchor_path}.required", "invalid_type", "required must be a boolean.")

        content_mode = anchor.get("content_mode", "excerpt")
        if not isinstance(content_mode, str) or content_mode not in TRUTH_MAP_CONTENT_MODES:
            _add_error(
                errors,
                f"{anchor_path}.content_mode",
                "invalid_content_mode",
                "content_mode must be 'excerpt' or 'metadata_only'.",
            )

        max_chars = anchor.get("max_chars", TRUTH_MAP_DEFAULT_EXCERPT_CHARS)
        if content_mode == "metadata_only":
            if "max_chars" in anchor:
                _add_error(
                    errors,
                    f"{anchor_path}.max_chars",
                    "field_not_allowed",
                    "max_chars is not allowed when content_mode is metadata_only.",
                )
        elif not _is_integer(max_chars) or not TRUTH_MAP_EXCERPT_MIN_CHARS <= max_chars <= TRUTH_MAP_EXCERPT_MAX_CHARS:
            _add_error(
                errors,
                f"{anchor_path}.max_chars",
                "invalid_excerpt_limit",
                f"max_chars must be an integer from {TRUTH_MAP_EXCERPT_MIN_CHARS} to {TRUTH_MAP_EXCERPT_MAX_CHARS}.",
            )

        if len(errors) == anchor_error_count:
            normalized_anchor: dict[str, Any] = {
                "kind": kind,
                "path": normalized_path,
                "required": required,
                "content_mode": content_mode,
            }
            if content_mode == "excerpt":
                normalized_anchor["max_chars"] = max_chars
            normalized_anchors.append(normalized_anchor)

    if errors:
        raise TruthMapValidationError(errors)
    return {"schema_version": TRUTH_MAP_SCHEMA_VERSION, "anchors": normalized_anchors}


def merge_project_metadata(existing: Any, incoming: Any) -> dict[str, Any]:
    if incoming is None:
        return deepcopy(existing) if isinstance(existing, dict) else {}
    if not isinstance(incoming, dict):
        raise TruthMapValidationError(
            [{"path": "metadata", "code": "invalid_type", "message": "metadata must be an object."}]
        )

    merged = deepcopy(existing) if isinstance(existing, dict) else {}
    for key, value in incoming.items():
        if key != "repo_context":
            merged[key] = deepcopy(value)

    if "repo_context" not in incoming:
        return merged

    incoming_repo_context = incoming["repo_context"]
    if not isinstance(incoming_repo_context, dict):
        raise TruthMapValidationError(
            [
                {
                    "path": "metadata.repo_context",
                    "code": "invalid_type",
                    "message": "repo_context must be an object.",
                }
            ]
        )

    existing_repo_context = merged.get("repo_context")
    repo_context = deepcopy(existing_repo_context) if isinstance(existing_repo_context, dict) else {}
    for key, value in incoming_repo_context.items():
        if key != "truth_map":
            repo_context[key] = deepcopy(value)

    if "truth_map" in incoming_repo_context:
        truth_map = incoming_repo_context["truth_map"]
        if truth_map is None:
            repo_context.pop("truth_map", None)
        else:
            repo_context["truth_map"] = validate_and_normalize_truth_map(truth_map)

    merged["repo_context"] = repo_context
    return merged


def resolve_project_truth_map(project: Any) -> dict[str, Any]:
    absent = {"mode": "heuristic", "config_status": "absent", "config_errors": [], "truth_map": None}
    if not isinstance(project, dict):
        return absent

    metadata = project.get("metadata")
    if not isinstance(metadata, dict) or "repo_context" not in metadata:
        return absent

    repo_context = metadata.get("repo_context")
    if not isinstance(repo_context, dict):
        return {
            "mode": "configured",
            "config_status": "invalid",
            "config_errors": [
                {
                    "path": "metadata.repo_context",
                    "code": "invalid_type",
                    "message": "repo_context must be an object.",
                }
            ],
            "truth_map": None,
        }

    if repo_context.get("truth_map") is None:
        return absent

    try:
        truth_map = validate_and_normalize_truth_map(repo_context.get("truth_map"))
    except TruthMapValidationError as exc:
        return {
            "mode": "configured",
            "config_status": "invalid",
            "config_errors": exc.errors,
            "truth_map": None,
        }

    return {
        "mode": "configured",
        "config_status": "valid",
        "config_errors": [],
        "truth_map": truth_map,
    }
