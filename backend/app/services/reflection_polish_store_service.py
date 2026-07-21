from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.reflection_polish_pair_service import (
    build_reflection_polish_review,
    validate_reflection_polish_pair,
    validate_reflection_polish_review,
)


DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "reflection_polish"
PAIRS_DIR = DATA_DIR / "pairs"
REVIEWS_DIR = DATA_DIR / "reviews"
INDEX_FILE = DATA_DIR / "index.json"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _ensure_dirs() -> None:
    PAIRS_DIR.mkdir(parents=True, exist_ok=True)
    REVIEWS_DIR.mkdir(parents=True, exist_ok=True)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    _ensure_dirs()
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    temp_path.replace(path)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _empty_index() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "record_type": "reflection_polish_index",
        "updated_at": _utc_now_iso(),
        "pairs": [],
    }


def load_reflection_polish_index() -> dict[str, Any]:
    if not INDEX_FILE.exists():
        return _empty_index()
    payload = _read_json(INDEX_FILE)
    if not isinstance(payload, dict):
        return _empty_index()
    pairs = payload.get("pairs")
    if not isinstance(pairs, list):
        pairs = []
    return {
        "schema_version": 1,
        "record_type": "reflection_polish_index",
        "updated_at": str(payload.get("updated_at") or _utc_now_iso()),
        "pairs": pairs,
    }


def _save_index(index: dict[str, Any]) -> None:
    index["updated_at"] = _utc_now_iso()
    _write_json(INDEX_FILE, index)


def save_reflection_polish_pair(pair: dict[str, Any]) -> dict[str, Any]:
    validated = validate_reflection_polish_pair(pair)
    pair_id = str(validated["id"])
    _write_json(PAIRS_DIR / f"{pair_id}.json", validated)

    index = load_reflection_polish_index()
    index["pairs"] = [entry for entry in index["pairs"] if entry.get("id") != pair_id]
    index["pairs"].insert(
        0,
        {
            "id": pair_id,
            "created_at": validated.get("created_at"),
            "status": validated.get("status"),
            "review_outcome": None,
            "signal_id": validated.get("context", {}).get("signal_id"),
        },
    )
    _save_index(index)
    return validated


def load_reflection_polish_pair(pair_id: str) -> dict[str, Any]:
    safe_pair_id = str(pair_id or "").strip()
    if not safe_pair_id:
        raise FileNotFoundError("reflection polish pair id is required.")
    path = PAIRS_DIR / f"{safe_pair_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"reflection polish pair not found: {safe_pair_id}")
    return validate_reflection_polish_pair(_read_json(path))


def load_reflection_polish_review(review_id: str) -> dict[str, Any]:
    safe_review_id = str(review_id or "").strip()
    if not safe_review_id:
        raise FileNotFoundError("reflection polish review id is required.")
    path = REVIEWS_DIR / f"{safe_review_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"reflection polish review not found: {safe_review_id}")
    return validate_reflection_polish_review(_read_json(path))


def list_reflection_polish_pairs(*, limit: int = 50) -> dict[str, Any]:
    index = load_reflection_polish_index()
    safe_limit = max(1, min(int(limit or 50), 200))
    pairs = index["pairs"][:safe_limit]
    return {
        "schema_version": 1,
        "record_type": "reflection_polish_pair_list",
        "updated_at": index["updated_at"],
        "count": len(pairs),
        "pairs": pairs,
    }


def get_reflection_polish_pair_detail(pair_id: str) -> dict[str, Any]:
    pair = load_reflection_polish_pair(pair_id)
    index = load_reflection_polish_index()
    index_entry = next((entry for entry in index["pairs"] if entry.get("id") == pair["id"]), {})
    review = None
    review_id = index_entry.get("review_id")
    if review_id:
        review = load_reflection_polish_review(str(review_id))
    return {
        "schema_version": 1,
        "record_type": "reflection_polish_pair_detail",
        "pair": pair,
        "review": review,
        "index_entry": index_entry or None,
    }


def save_reflection_polish_review(
    *,
    pair_id: str,
    outcome: str,
    dimension_results: dict[str, str],
    reviewer_id: str,
    reviewer_note: str = "",
    final_reflection_text: str = "",
    save_reflection_ref: dict[str, Any] | None = None,
) -> dict[str, Any]:
    pair = load_reflection_polish_pair(pair_id)
    review = build_reflection_polish_review(
        pair=pair,
        outcome=outcome,
        dimension_results=dimension_results,
        reviewer_id=reviewer_id,
        reviewer_note=reviewer_note,
        final_reflection_text=final_reflection_text,
        save_reflection_ref=save_reflection_ref,
    )
    validated_review = validate_reflection_polish_review(review, pair=pair)
    review_id = str(validated_review["id"])
    _write_json(REVIEWS_DIR / f"{review_id}.json", validated_review)

    index = load_reflection_polish_index()
    for entry in index["pairs"]:
        if entry.get("id") == pair["id"]:
            entry["review_outcome"] = validated_review.get("outcome")
            entry["review_id"] = review_id
            break
    _save_index(index)
    return validated_review
