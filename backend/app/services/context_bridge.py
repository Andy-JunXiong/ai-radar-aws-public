import json
from pathlib import Path
from typing import Any, Optional

from app.services.project_intelligence_service import build_project_analysis_context
from app.services.subscription_settings_service import build_subscription_settings_context


PROJECT_ROOT = Path(__file__).resolve().parents[3]
PERSONAL_CONTEXT_PATH = PROJECT_ROOT / "app" / "context" / "personal_context.json"
USER_CONTEXTS_DIR = PROJECT_ROOT / "app" / "context" / "users"
DECISION_CARDS_INDEX_PATH = PROJECT_ROOT / "backend" / "data" / "decision_cards" / "index.json"
REVIEWS_INDEX_PATH = PROJECT_ROOT / "backend" / "data" / "reviews" / "index.json"
REFLECTION_INDEX_PATH = PROJECT_ROOT / "backend" / "data" / "reflections" / "index.json"

 
def _normalize_user_id(user_id: Optional[str]) -> Optional[str]:
    if user_id is None:
        return None

    normalized = str(user_id).strip()
    if not normalized:
        return None

    safe = normalized.replace("/", "_").replace("\\", "_")
    return safe or None


def get_personal_context_path(user_id: Optional[str] = None) -> Path:
    normalized_user_id = _normalize_user_id(user_id)
    if normalized_user_id:
        return USER_CONTEXTS_DIR / normalized_user_id / "personal_context.json"

    return PERSONAL_CONTEXT_PATH


def load_personal_context_data(user_id: Optional[str] = None) -> dict[str, Any]:
    candidate_paths = []
    user_specific_path = get_personal_context_path(user_id)
    candidate_paths.append(user_specific_path)

    if user_specific_path != PERSONAL_CONTEXT_PATH:
        candidate_paths.append(PERSONAL_CONTEXT_PATH)

    for path in candidate_paths:
        if not path.exists():
            continue

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue

        if isinstance(data, dict):
            return data

    return {}


def get_context_scope(user_id: Optional[str] = None) -> str:
    normalized_user_id = _normalize_user_id(user_id)
    if not normalized_user_id:
        return "demo_default"

    user_specific_path = get_personal_context_path(normalized_user_id)
    if user_specific_path.exists():
        return "user_specific"

    return "demo_default"


def save_personal_context_data(user_id: str, data: dict[str, Any]) -> Path:
    normalized_user_id = _normalize_user_id(user_id)
    if not normalized_user_id:
        raise ValueError("user_id is required to save personal context.")

    if not isinstance(data, dict):
        raise ValueError("personal context payload must be a JSON object.")

    target_path = get_personal_context_path(normalized_user_id)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return target_path


def _load_json_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def _build_behavior_context() -> str:
    decision_cards = _load_json_list(DECISION_CARDS_INDEX_PATH)
    reviews = _load_json_list(REVIEWS_INDEX_PATH)

    total_decisions = len(decision_cards)
    saved_decisions = sum(1 for item in decision_cards if str(item.get("status") or "") == "saved")
    acted_decisions = sum(1 for item in decision_cards if str(item.get("status") or "") == "acted")
    reviewed_decisions = sum(1 for item in decision_cards if str(item.get("status") or "") == "reviewed")

    source_context_counts: dict[str, int] = {}
    for item in decision_cards:
        key = str(item.get("source_context") or "unknown").strip() or "unknown"
        source_context_counts[key] = source_context_counts.get(key, 0) + 1

    completed_reviews = sum(1 for item in reviews if str(item.get("status") or "") == "completed")

    total_reflections = 0
    if REFLECTION_INDEX_PATH.exists():
        try:
            payload = json.loads(REFLECTION_INDEX_PATH.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                reflections = payload.get("reflections")
                if isinstance(reflections, list):
                    total_reflections = len([item for item in reflections if isinstance(item, dict)])
        except Exception:
            total_reflections = 0

    summary = {
        "total_decision_cards": total_decisions,
        "saved_decisions": saved_decisions,
        "acted_decisions": acted_decisions,
        "reviewed_decisions": reviewed_decisions,
        "total_reviews": len(reviews),
        "completed_reviews": completed_reviews,
        "source_context_breakdown": source_context_counts,
        "indexed_reflections": total_reflections,
    }

    if total_decisions == 0 and len(reviews) == 0 and total_reflections == 0:
        return ""

    return json.dumps(summary, ensure_ascii=False, indent=2)


def build_analysis_context(user_id: Optional[str] = None) -> str:
    data = load_personal_context_data(user_id)
    if not data:
        return "No personal context available."

    resolved_user_id = _normalize_user_id(user_id)

    sections = []

    if resolved_user_id:
        sections.append("USER ID")
        sections.append(resolved_user_id)

    user_profile = data.get("user_profile")
    if user_profile:
        sections.append("USER PROFILE")
        sections.append(json.dumps(user_profile, ensure_ascii=False, indent=2))

    projects = data.get("projects")
    if projects:
        sections.append("ACTIVE PROJECTS")
        sections.append(json.dumps(projects, ensure_ascii=False, indent=2))

    preferences = data.get("interpretation_preference")
    if preferences:
        sections.append("INTERPRETATION PREFERENCES")
        sections.append(json.dumps(preferences, ensure_ascii=False, indent=2))

    subscription_context = build_subscription_settings_context(resolved_user_id)
    if subscription_context:
        sections.append("SIGNAL SUBSCRIPTION SETTINGS")
        sections.append(subscription_context)

    project_context = build_project_analysis_context(user_id=resolved_user_id)
    if project_context:
        sections.append(project_context)

    behavior_context = _build_behavior_context()
    if behavior_context:
        sections.append("AI RADAR BEHAVIOR CONTEXT")
        sections.append(behavior_context)

    if not sections:
        return json.dumps(data, ensure_ascii=False, indent=2)

    return "\n\n".join(sections)
