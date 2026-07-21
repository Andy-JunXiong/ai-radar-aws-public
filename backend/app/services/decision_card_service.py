from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import os
from dotenv import load_dotenv

from app.prompts.registry import decision_card_generate_prompts
from app.services.execution_policy_service import PolicyInput
from app.services.fallback_policy_service import execute_policy_text_json
from app.services.llm_executor_service import execute_text_json_task


ROOT_ENV_PATH = Path(__file__).resolve().parents[3] / ".env"
load_dotenv(ROOT_ENV_PATH, override=True)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "decision_cards"
INDEX_PATH = DATA_DIR / "index.json"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _parse_iso_datetime(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None

    normalized = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except Exception:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _normalize_decision_text(value: Any, *, fallback: str = "") -> str:
    text = str(value or "").strip()
    if not text:
        return fallback

    prefixes = ("uncertain:", "maybe:", "possibly:", "tentative:")
    lowered = text.lower()
    for prefix in prefixes:
        if lowered.startswith(prefix):
            text = text[len(prefix):].strip()
            lowered = text.lower()
    return text or fallback


def _replace_leading_route_verbs(text: str, replacements: dict[str, str]) -> str:
    normalized = text.strip()
    if not normalized:
        return normalized
    lowered = normalized.lower()
    for source, target in replacements.items():
        if lowered.startswith(source):
            return target + normalized[len(source):]
    return normalized


def _normalize_route_copy(*, title: str, thesis: str, recommended_action: str, action_type: str) -> tuple[str, str, str]:
    normalized_title = title.strip()
    normalized_thesis = thesis.strip()
    normalized_action = recommended_action.strip()

    if action_type == "watch":
        normalized_title = _replace_leading_route_verbs(
            normalized_title,
            {
                "implement ": "Monitor ",
                "adopt ": "Track ",
                "leverage ": "Track ",
                "incorporate ": "Monitor ",
                "build ": "Monitor ",
                "design ": "Monitor ",
                "prototype ": "Monitor ",
                "integrate ": "Track ",
                "evaluate ": "Monitor ",
            },
        )
        watch_prefixes = ("monitor ", "track ", "follow ", "review ", "watch ")
        if normalized_action and not normalized_action.lower().startswith(watch_prefixes):
            normalized_action = "Monitor developments, benchmarks, and adoption signals before committing project work."

    elif action_type == "learn":
        normalized_title = _replace_leading_route_verbs(
            normalized_title,
            {
                "implement ": "Learn about ",
                "adopt ": "Study ",
                "leverage ": "Study ",
                "incorporate ": "Learn about ",
                "build ": "Learn about ",
                "design ": "Study ",
                "prototype ": "Study ",
                "integrate ": "Learn about ",
                "evaluate ": "Study ",
            },
        )
        learn_prefixes = ("learn ", "study ", "review ", "read ", "compare ", "understand ")
        if normalized_action and not normalized_action.lower().startswith(learn_prefixes):
            normalized_action = "Study this topic further and capture practical takeaways before deciding on project work."

    return normalized_title, normalized_thesis, normalized_action


def _normalize_review_at(value: Any) -> str:
    parsed = _parse_iso_datetime(value)
    if parsed is not None:
        return parsed.replace(microsecond=0).isoformat()
    return (datetime.now(timezone.utc) + timedelta(days=7)).replace(microsecond=0).isoformat()


def _normalize_expiry_at(value: Any) -> str | None:
    parsed = _parse_iso_datetime(value)
    if parsed is None:
        return None
    return parsed.replace(microsecond=0).isoformat()


def _normalize_action_type(value: Any) -> str:
    allowed = {"project", "watch", "learn", "ignore"}
    text = str(value or "").strip().lower()
    legacy_map = {
        "build": "project",
        "apply": "project",
    }
    text = legacy_map.get(text, text)
    if text in allowed:
        return text
    return "watch"


def _sanitize_decision_card_payload(card: dict[str, Any]) -> dict[str, Any]:
    sanitized = dict(card)
    sanitized["title"] = _normalize_decision_text(sanitized.get("title"), fallback=str(sanitized.get("id") or ""))
    sanitized["thesis"] = _normalize_decision_text(sanitized.get("thesis"))
    sanitized["recommended_action"] = _normalize_decision_text(sanitized.get("recommended_action"))
    sanitized["action_type"] = _normalize_action_type(sanitized.get("action_type"))
    sanitized["review_at"] = _normalize_review_at(sanitized.get("review_at"))
    sanitized["expiry_at"] = _normalize_expiry_at(sanitized.get("expiry_at"))
    return sanitized


def _decision_card_signature(card: dict[str, Any]) -> str:
    sanitized = _sanitize_decision_card_payload(card)
    signal_refs = ",".join(sorted(str(value).strip() for value in (sanitized.get("signal_refs") or []) if str(value).strip()))
    project_refs = ",".join(sorted(str(value).strip() for value in (sanitized.get("project_refs") or []) if str(value).strip()))
    return "|".join(
        [
            str(sanitized.get("source_context") or "").strip().lower(),
            str(sanitized.get("title") or "").strip().lower(),
            signal_refs.lower(),
            project_refs.lower(),
        ]
    )


def _find_reusable_decision_card(
    *,
    signal_refs: list[str],
    source_context: str | None,
) -> dict[str, Any] | None:
    if not signal_refs or source_context not in {"signal_detail", "manual_signal_detail"}:
        return None

    candidates = list_decision_cards(signal_id=signal_refs[0], source_context=source_context)
    if not candidates:
        return None

    def sort_key(card: dict[str, Any]) -> tuple[float, str]:
        updated_at = str(card.get("updated_at") or "")
        try:
            parsed = datetime.fromisoformat(updated_at.replace("Z", "+00:00")) if updated_at else None
        except Exception:
            parsed = None
        timestamp = parsed.timestamp() if parsed is not None else 0.0
        return (timestamp, str(card.get("id") or ""))

    return sorted(candidates, key=sort_key, reverse=True)[0]


def _ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not INDEX_PATH.exists():
        INDEX_PATH.write_text("[]", encoding="utf-8")


def _card_path(card_id: str) -> Path:
    safe = str(card_id).replace("/", "_").replace("\\", "_")
    return DATA_DIR / f"{safe}.json"


def _load_index() -> list[dict[str, Any]]:
    _ensure_data_dir()
    try:
        payload = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            return payload
    except Exception:
        pass
    return []


def _save_index(items: list[dict[str, Any]]) -> None:
    _ensure_data_dir()
    INDEX_PATH.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def build_decision_card(
    *,
    title: str,
    signal_refs: list[str],
    project_refs: list[str],
    thesis: str,
    importance_score: int,
    confidence_score: int,
    counter_argument: str,
    recommended_action: str,
    action_type: str,
    invalidation_condition: str,
    expiry_at: str | None,
    review_at: str,
    status: str = "new",
    execution_policy: dict[str, Any] | None = None,
    source_context: str | None = None,
) -> dict[str, Any]:
    card_id = f"dc_{uuid.uuid4().hex[:12]}"
    created_at = _utc_now_iso()
    return _sanitize_decision_card_payload(
        {
        "id": card_id,
        "title": title.strip(),
        "signal_refs": signal_refs,
        "project_refs": project_refs,
        "thesis": thesis.strip(),
        "importance_score": max(0, min(100, int(importance_score))),
        "confidence_score": max(0, min(100, int(confidence_score))),
        "counter_argument": counter_argument.strip(),
        "recommended_action": recommended_action.strip(),
        "action_type": action_type.strip() or "watch",
        "invalidation_condition": invalidation_condition.strip(),
        "expiry_at": expiry_at,
        "review_at": review_at,
        "status": status,
        "created_at": created_at,
        "updated_at": created_at,
        "latest_feedback_id": None,
        "latest_review_id": None,
        "execution_policy": execution_policy,
        "source_context": source_context,
        }
    )


def save_decision_card(card: dict[str, Any]) -> dict[str, Any]:
    _ensure_data_dir()
    card = _sanitize_decision_card_payload(card)
    card_path = _card_path(card["id"])
    card_path.write_text(json.dumps(card, ensure_ascii=False, indent=2), encoding="utf-8")

    index_items = [item for item in _load_index() if item.get("id") != card["id"]]
    index_items.append(
        {
            "id": card["id"],
            "title": card.get("title"),
            "status": card.get("status"),
            "review_at": card.get("review_at"),
            "updated_at": card.get("updated_at"),
            "signal_refs": card.get("signal_refs", []),
            "project_refs": card.get("project_refs", []),
            "source_context": card.get("source_context"),
        }
    )
    _save_index(sorted(index_items, key=lambda item: str(item.get("updated_at") or ""), reverse=True))
    return card


def get_decision_card(card_id: str) -> dict[str, Any] | None:
    path = _card_path(card_id)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return _sanitize_decision_card_payload(payload) if isinstance(payload, dict) else None
    except Exception:
        return None


def list_decision_cards(
    *,
    status: str | None = None,
    signal_id: str | None = None,
    project_id: str | None = None,
    source_context: str | None = None,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for item in _load_index():
        card = get_decision_card(str(item.get("id") or ""))
        if not card:
            continue
        if status and str(card.get("status") or "") != status:
            continue
        if signal_id and signal_id not in (card.get("signal_refs") or []):
            continue
        if project_id and project_id not in (card.get("project_refs") or []):
            continue
        if source_context and str(card.get("source_context") or "") != source_context:
            continue
        items.append(card)
    return items


def update_decision_feedback(
    *,
    card_id: str,
    feedback_id: str,
    user_action: str,
    action_notes: str,
    updated_at: str,
) -> dict[str, Any]:
    card = get_decision_card(card_id)
    if not card:
        raise ValueError("Decision card not found.")
    status_map = {
        "saved": "saved",
        "ignored": "ignored",
        "acted": "acted",
        "deferred": card.get("status") or "new",
    }
    card["status"] = status_map.get(user_action, card.get("status") or "new")
    card["latest_feedback_id"] = feedback_id
    card["feedback"] = {
        "id": feedback_id,
        "decision_card_id": card_id,
        "user_action": user_action,
        "action_notes": action_notes,
        "updated_at": updated_at,
    }
    card["updated_at"] = updated_at
    return save_decision_card(card)


def attach_review_to_decision(card_id: str, review_id: str, *, review_date: str) -> dict[str, Any]:
    card = get_decision_card(card_id)
    if not card:
        raise ValueError("Decision card not found.")
    card["latest_review_id"] = review_id
    card["status"] = "reviewed"
    card["updated_at"] = review_date
    return save_decision_card(card)


def generate_decision_card_from_context(
    *,
    title: str,
    signal_refs: list[str],
    project_refs: list[str],
    context_payload: dict[str, Any],
    importance_score: float | int | None = None,
    source_context: str | None = None,
) -> dict[str, Any]:
    system_prompt, user_prompt = decision_card_generate_prompts(
        title=title,
        context_payload=context_payload,
    )
    policy_input = PolicyInput(
        task_type="decision_support",
        query=title,
        user_visible=True,
        importance_score=importance_score or 80,
        requires_traceability=True,
        source_count=max(1, len(signal_refs)),
        metadata={"source_count": max(1, len(signal_refs)), "decision_support": True},
    )
    parsed, route, policy_metadata = execute_policy_text_json(
        policy_input=policy_input,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        metadata={"source_count": max(1, len(signal_refs)), "context_label": "decision_context"},
        executor=lambda effective_task_type, patched_system_prompt, patched_user_prompt: execute_text_json_task(
            task_type=effective_task_type,
            system_prompt=patched_system_prompt,
            user_prompt=patched_user_prompt,
            temperature=0.2,
            max_tokens=1800,
            openai_api_key=OPENAI_API_KEY,
            anthropic_api_key=ANTHROPIC_API_KEY,
        ),
    )

    normalized_title = _normalize_decision_text(parsed.get("title"), fallback=title)
    normalized_thesis = _normalize_decision_text(parsed.get("thesis"))
    normalized_action = _normalize_decision_text(parsed.get("recommended_action"))
    normalized_counter = str(parsed.get("counter_argument") or "").strip()
    normalized_source_context = source_context or None
    normalized_action_type = _normalize_action_type(parsed.get("action_type"))
    normalized_title, normalized_thesis, normalized_action = _normalize_route_copy(
        title=normalized_title,
        thesis=normalized_thesis,
        recommended_action=normalized_action,
        action_type=normalized_action_type,
    )

    candidate_signature = _decision_card_signature(
        {
            "title": normalized_title,
            "signal_refs": signal_refs,
            "project_refs": project_refs,
            "source_context": normalized_source_context,
        }
    )

    existing_match = _find_reusable_decision_card(
        signal_refs=signal_refs,
        source_context=normalized_source_context,
    )
    if existing_match is None:
        for existing in list_decision_cards(signal_id=signal_refs[0] if signal_refs else None, source_context=normalized_source_context):
            if _decision_card_signature(existing) == candidate_signature:
                existing_match = existing
                break

    card = build_decision_card(
        title=normalized_title,
        signal_refs=signal_refs,
        project_refs=project_refs,
        thesis=normalized_thesis,
        importance_score=int(parsed.get("importance_score") or importance_score or 80),
        confidence_score=int(parsed.get("confidence_score") or 70),
        counter_argument=normalized_counter,
        recommended_action=normalized_action,
        action_type=normalized_action_type,
        invalidation_condition=str(parsed.get("invalidation_condition") or ""),
        expiry_at=_normalize_expiry_at(parsed.get("expiry_at")),
        review_at=_normalize_review_at(parsed.get("review_at")),
        execution_policy=policy_metadata.get("execution_policy"),
        source_context=normalized_source_context,
    )
    card["policy_metadata"] = policy_metadata
    card["provider_used"] = route.provider
    card["model_used"] = route.model
    if existing_match:
        card["id"] = existing_match["id"]
        card["created_at"] = existing_match.get("created_at") or card["created_at"]
        card["status"] = existing_match.get("status") or card["status"]
        card["latest_feedback_id"] = existing_match.get("latest_feedback_id")
        card["latest_review_id"] = existing_match.get("latest_review_id")
        card["feedback"] = existing_match.get("feedback")
    return save_decision_card(card)
