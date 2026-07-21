from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.decision_card_service import get_decision_card
from app.services.decision_review_service import get_review_record


DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "decision_memory"
SUMMARY_PATH = DATA_DIR / "calibration_summary.json"
REVIEWS_INDEX_PATH = Path(__file__).resolve().parents[2] / "data" / "reviews" / "index.json"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _load_reviews_index() -> list[dict[str, Any]]:
    try:
      payload = json.loads(REVIEWS_INDEX_PATH.read_text(encoding="utf-8"))
      if isinstance(payload, list):
          return payload
    except Exception:
      return []
    return []


def build_learning_summary() -> dict[str, Any]:
    completed_reviews: list[dict[str, Any]] = []

    for item in _load_reviews_index():
        review = get_review_record(str(item.get("id") or ""))
        if not review:
            continue
        if str(review.get("status") or "") != "completed":
            continue
        completed_reviews.append(review)

    outcome_counts = {
        "correct": 0,
        "partially_correct": 0,
        "wrong": 0,
        "unclear": 0,
    }
    confidence_buckets = [
        {"label": "0-40", "min": 0, "max": 40, "total": 0, "correct": 0, "partially_correct": 0, "wrong": 0, "unclear": 0},
        {"label": "41-70", "min": 41, "max": 70, "total": 0, "correct": 0, "partially_correct": 0, "wrong": 0, "unclear": 0},
        {"label": "71-100", "min": 71, "max": 100, "total": 0, "correct": 0, "partially_correct": 0, "wrong": 0, "unclear": 0},
    ]

    total_confidence_adjustment = 0
    reviewed_with_cards = 0

    for review in completed_reviews:
        outcome = str(review.get("outcome") or "unclear")
        if outcome not in outcome_counts:
            outcome = "unclear"
        outcome_counts[outcome] += 1
        total_confidence_adjustment += int(review.get("confidence_adjustment") or 0)

        card = get_decision_card(str(review.get("decision_card_id") or ""))
        if not card:
            continue
        reviewed_with_cards += 1
        confidence_score = int(card.get("confidence_score") or 0)
        for bucket in confidence_buckets:
            if bucket["min"] <= confidence_score <= bucket["max"]:
                bucket["total"] += 1
                bucket[outcome] += 1
                break

    summary = {
        "generated_at": _utc_now_iso(),
        "total_completed_reviews": len(completed_reviews),
        "reviewed_with_linked_cards": reviewed_with_cards,
        "average_confidence_adjustment": (
            round(total_confidence_adjustment / len(completed_reviews), 2)
            if completed_reviews
            else 0
        ),
        "outcome_counts": outcome_counts,
        "confidence_buckets": confidence_buckets,
    }
    return summary


def save_learning_summary(summary: dict[str, Any]) -> dict[str, Any]:
    _ensure_data_dir()
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def refresh_learning_summary() -> dict[str, Any]:
    summary = build_learning_summary()
    return save_learning_summary(summary)


def get_learning_summary() -> dict[str, Any]:
    if SUMMARY_PATH.exists():
        try:
            payload = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                return payload
        except Exception:
            pass
    return refresh_learning_summary()
