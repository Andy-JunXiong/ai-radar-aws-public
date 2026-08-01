from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.verification_metadata_reader import (
    build_action_eligibility_summary,
    get_blocked_downstream_actions,
)


BASE_DIR = Path(__file__).resolve().parents[2] / "data"
PROJECT_WATCH_ITEMS_DIR = BASE_DIR / "project_watch_items"

WATCH_KIND_EVIDENCE_FOLLOWUP = "evidence_followup"
WATCH_STATE_ACTIVE = "active"
WATCH_STATE_RESOLVED = "resolved"
WATCH_OBSERVATION_EVIDENCE_ROLE = "review_context_only"
WATCH_MATCH_CANDIDATE_ROLE = "review_candidate_only"
WATCH_MATCH_DECISIONS = frozenset({"accept", "ignore", "not_related"})

MATCH_STOP_WORDS = frozenset(
    {
        "about",
        "after",
        "agent",
        "agents",
        "also",
        "because",
        "before",
        "could",
        "evidence",
        "from",
        "have",
        "into",
        "more",
        "model",
        "models",
        "new",
        "observation",
        "pattern",
        "platform",
        "project",
        "related",
        "review",
        "signal",
        "should",
        "source",
        "sources",
        "support",
        "supports",
        "that",
        "their",
        "this",
        "tool",
        "tools",
        "watch",
        "what",
        "when",
        "where",
        "which",
        "with",
        "would",
    }
)

WATCH_RESOLUTION_BASES = frozenset(
    {
        "success_criteria_met",
        "exit_criteria_met",
        "no_longer_relevant",
        "manual_close",
    }
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _safe_text(value: object) -> str:
    return str(value or "").strip()


def _safe_project_id(project_id: str) -> str:
    normalized = _safe_text(project_id)
    if not normalized or not re.fullmatch(r"[A-Za-z0-9_-]+", normalized):
        raise ValueError("Invalid project id.")
    return normalized


def _watch_file_path(project_id: str) -> Path:
    return PROJECT_WATCH_ITEMS_DIR / f"{_safe_project_id(project_id)}.json"


def _parse_datetime(value: object) -> datetime | None:
    text = _safe_text(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _flatten_text(value: object) -> str:
    if isinstance(value, dict):
        return " ".join(_flatten_text(item) for item in value.values())
    if isinstance(value, (list, tuple, set)):
        return " ".join(_flatten_text(item) for item in value)
    return _safe_text(value)


def _meaningful_tokens(value: object) -> set[str]:
    text = _flatten_text(value).lower()
    latin_tokens = {
        token
        for token in re.findall(r"[a-z0-9][a-z0-9._+-]{2,}", text)
        if token not in MATCH_STOP_WORDS and not token.isdigit()
    }
    return latin_tokens


def _signal_match_text(signal: dict[str, Any]) -> str:
    fields = (
        "title",
        "signal_title",
        "summary",
        "signal_summary",
        "topic",
        "topics",
        "tags",
        "why_it_matters",
        "relevance_to_projects",
        "synthesized_insight",
        "strategy",
        "repo",
        "repository",
        "product",
        "company",
    )
    return " ".join(_flatten_text(signal.get(field)) for field in fields)


def _signal_project_ids(signal: dict[str, Any]) -> set[str]:
    project_ids: set[str] = set()
    for field in ("subscription_project_links", "project_links"):
        values = signal.get(field)
        if not isinstance(values, list):
            continue
        for value in values:
            if isinstance(value, dict):
                project_id = _safe_text(value.get("project_id") or value.get("id"))
            else:
                project_id = _safe_text(value)
            if project_id:
                project_ids.add(project_id)
    projects = signal.get("projects")
    if isinstance(projects, list):
        project_ids.update(_safe_text(value) for value in projects if _safe_text(value))
    return project_ids


def _build_match_reasons(watch: dict[str, Any], signal: dict[str, Any]) -> list[dict[str, Any]]:
    signal_text_tokens = _meaningful_tokens(_signal_match_text(signal))
    signal_title_tokens = _meaningful_tokens(signal.get("title") or signal.get("signal_title"))
    reasons: list[dict[str, Any]] = []

    if _safe_text(watch.get("project_id")) in _signal_project_ids(signal):
        reasons.append({"code": "same_project_link", "label": "Same project link", "matched_terms": []})

    origin_terms = sorted(_meaningful_tokens(watch.get("origin_signal_title")) & (signal_title_tokens | signal_text_tokens))
    if origin_terms:
        reasons.append(
            {
                "code": "shared_origin_terms",
                "label": "Shares terms with the origin Signal",
                "matched_terms": origin_terms[:6],
            }
        )

    watch_terms = sorted(
        _meaningful_tokens(
            " ".join((_safe_text(watch.get("watch_question")), _safe_text(watch.get("watch_reason"))))
        )
        & signal_text_tokens
    )
    if len(watch_terms) >= 2:
        reasons.append(
            {
                "code": "shared_watch_terms",
                "label": "Matches the Watch question or reason",
                "matched_terms": watch_terms[:8],
            }
        )

    success_terms = sorted(_meaningful_tokens(watch.get("success_criteria")) & signal_text_tokens)
    if len(success_terms) >= 2:
        reasons.append(
            {
                "code": "success_criteria_terms",
                "label": "May relate to success criteria",
                "matched_terms": success_terms[:8],
            }
        )

    exit_terms = sorted(_meaningful_tokens(watch.get("exit_criteria")) & signal_text_tokens)
    if len(exit_terms) >= 2:
        reasons.append(
            {
                "code": "exit_criteria_terms",
                "label": "May relate to exit criteria",
                "matched_terms": exit_terms[:8],
            }
        )
    return reasons


def _is_match_candidate(reasons: list[dict[str, Any]]) -> bool:
    reason_codes = {_safe_text(reason.get("code")) for reason in reasons}
    if len(reason_codes) < 2:
        return False
    return bool(
        "same_project_link" in reason_codes
        or "shared_origin_terms" in reason_codes
        or {"shared_watch_terms", "success_criteria_terms"}.issubset(reason_codes)
    )


def _normalize_payload(project_id: str, payload: object) -> dict[str, Any]:
    raw = payload if isinstance(payload, dict) else {}
    raw_items = raw.get("items") if isinstance(raw.get("items"), list) else []
    items = [item for item in raw_items if isinstance(item, dict)]
    return {
        "project_id": _safe_project_id(project_id),
        "updated_at": _safe_text(raw.get("updated_at")),
        "items": items,
    }


def load_project_watch_items(project_id: str) -> dict[str, Any]:
    path = _watch_file_path(project_id)
    if not path.exists():
        return {"project_id": _safe_project_id(project_id), "updated_at": "", "items": []}
    try:
        return _normalize_payload(project_id, json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError):
        return {"project_id": _safe_project_id(project_id), "updated_at": "", "items": []}


def _save_project_watch_items(project_id: str, items: list[dict[str, Any]]) -> dict[str, Any]:
    normalized_project_id = _safe_project_id(project_id)
    payload = {
        "project_id": normalized_project_id,
        "updated_at": _utc_now_iso(),
        "items": items,
    }
    PROJECT_WATCH_ITEMS_DIR.mkdir(parents=True, exist_ok=True)
    path = _watch_file_path(normalized_project_id)
    temporary_path = path.with_suffix(".json.tmp")
    temporary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary_path.replace(path)
    return payload


def _with_attention_state(item: dict[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    current_time = now or datetime.now(timezone.utc)
    next_review = _parse_datetime(item.get("next_review_at"))
    active = _safe_text(item.get("state")) == WATCH_STATE_ACTIVE
    is_due = bool(active and next_review and next_review <= current_time)
    related_candidates = item.get("related_signal_candidates") if isinstance(item.get("related_signal_candidates"), list) else []
    new_match_count = sum(
        1
        for candidate in related_candidates
        if isinstance(candidate, dict) and _safe_text(candidate.get("status")) == "unseen"
    )
    return {
        **item,
        "is_due": is_due,
        "is_overdue": is_due,
        "new_match_count": new_match_count,
        "has_new_matches": new_match_count > 0,
        "needs_plan": not all(
            _safe_text(item.get(field))
            for field in ("success_criteria", "exit_criteria", "next_review_at")
        ),
    }


def list_project_watch_items(
    project_id: str,
    *,
    state: str = "",
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    normalized_state = _safe_text(state).lower()
    items = load_project_watch_items(project_id)["items"]
    if normalized_state:
        items = [item for item in items if _safe_text(item.get("state")).lower() == normalized_state]
    enriched = [_with_attention_state(item, now=now) for item in items]
    return sorted(
        enriched,
        key=lambda item: (
            not bool(item.get("has_new_matches")),
            not bool(item.get("is_due")),
            _safe_text(item.get("next_review_at")) or "9999-12-31T23:59:59+00:00",
            _safe_text(item.get("created_at")),
        ),
    )


def create_project_watch_item(
    project_id: str,
    *,
    origin_signal_id: str,
    origin_signal_title: str,
    watch_question: str,
    watch_reason: str,
    success_criteria: str,
    exit_criteria: str,
    next_review_at: str,
    verification_metadata: dict[str, Any] | None,
) -> dict[str, Any]:
    required = {
        "origin signal id": origin_signal_id,
        "watch question": watch_question,
        "watch reason": watch_reason,
        "success criteria": success_criteria,
        "exit criteria": exit_criteria,
        "next review date": next_review_at,
    }
    missing = [label for label, value in required.items() if not _safe_text(value)]
    if missing:
        raise ValueError(f"Watch details required: {', '.join(missing)}.")
    if _parse_datetime(next_review_at) is None:
        raise ValueError("Next review date must be a valid ISO date or datetime.")

    metadata = verification_metadata if isinstance(verification_metadata, dict) else {}
    eligibility = build_action_eligibility_summary(metadata)
    blocked_actions = get_blocked_downstream_actions(metadata)
    watch_gate = eligibility.get("watch_only") if isinstance(eligibility.get("watch_only"), dict) else {}
    if "watch_only" in blocked_actions or not bool(watch_gate.get("allowed")):
        raise ValueError(_safe_text(watch_gate.get("reason")) or "Verification blocks Watch creation.")

    payload = load_project_watch_items(project_id)
    items = payload["items"]
    normalized_signal_id = _safe_text(origin_signal_id)
    duplicate = next(
        (
            item
            for item in items
            if _safe_text(item.get("origin_signal_id")) == normalized_signal_id
            and _safe_text(item.get("state")) == WATCH_STATE_ACTIVE
        ),
        None,
    )
    if duplicate:
        raise ValueError("An active Project Watch already exists for this Signal and project.")

    now = _utc_now_iso()
    item = {
        "watch_id": f"watch_{uuid.uuid4().hex[:12]}",
        "project_id": _safe_project_id(project_id),
        "watch_kind": WATCH_KIND_EVIDENCE_FOLLOWUP,
        "origin_type": "signal",
        "origin_signal_id": normalized_signal_id,
        "origin_signal_title": _safe_text(origin_signal_title),
        "watch_question": _safe_text(watch_question),
        "watch_reason": _safe_text(watch_reason),
        "success_criteria": _safe_text(success_criteria),
        "exit_criteria": _safe_text(exit_criteria),
        "next_review_at": _parse_datetime(next_review_at).isoformat(),
        "state": WATCH_STATE_ACTIVE,
        "created_at": now,
        "updated_at": now,
        "observations": [],
        "observation_count": 0,
    }
    items.append(item)
    _save_project_watch_items(project_id, items)
    return _with_attention_state(item)


def add_project_watch_observation(
    project_id: str,
    watch_id: str,
    *,
    summary: str,
    source_signal_id: str = "",
    next_review_at: str = "",
) -> dict[str, Any]:
    if not _safe_text(summary):
        raise ValueError("Observation summary is required.")
    if _safe_text(next_review_at) and _parse_datetime(next_review_at) is None:
        raise ValueError("Next review date must be a valid ISO date or datetime.")

    payload = load_project_watch_items(project_id)
    items = payload["items"]
    for index, existing in enumerate(items):
        if _safe_text(existing.get("watch_id")) != _safe_text(watch_id):
            continue
        if _safe_text(existing.get("state")) != WATCH_STATE_ACTIVE:
            raise ValueError("Only active Watch items can receive observations.")
        now = _utc_now_iso()
        observations = existing.get("observations") if isinstance(existing.get("observations"), list) else []
        observation = {
            "observation_id": f"obs_{uuid.uuid4().hex[:12]}",
            "watch_id": _safe_text(watch_id),
            "summary": _safe_text(summary),
            "source_signal_id": _safe_text(source_signal_id),
            "evidence_role": WATCH_OBSERVATION_EVIDENCE_ROLE,
            "observed_at": now,
        }
        updated = {
            **existing,
            "observations": [*observations, observation],
            "observation_count": len(observations) + 1,
            "last_observed_at": now,
            "updated_at": now,
        }
        if _safe_text(next_review_at):
            updated["next_review_at"] = _parse_datetime(next_review_at).isoformat()
        items[index] = updated
        _save_project_watch_items(project_id, items)
        return _with_attention_state(updated)
    raise ValueError(f"Watch item not found: {watch_id}")


def match_signal_to_active_project_watches(
    signal: dict[str, Any],
    *,
    project_ids: list[str],
) -> dict[str, Any]:
    signal_id = _safe_text(signal.get("signal_id") or signal.get("id"))
    if not signal_id:
        raise ValueError("Signal id is required for Watch matching.")

    summary = {
        "signal_id": signal_id,
        "scanned_watch_count": 0,
        "created_count": 0,
        "existing_count": 0,
        "matches": [],
    }
    for project_id in project_ids:
        payload = load_project_watch_items(project_id)
        items = payload["items"]
        changed = False
        for index, existing in enumerate(items):
            if _safe_text(existing.get("state")) != WATCH_STATE_ACTIVE:
                continue
            if _safe_text(existing.get("origin_signal_id")) == signal_id:
                continue
            summary["scanned_watch_count"] += 1
            observations = existing.get("observations") if isinstance(existing.get("observations"), list) else []
            if any(
                isinstance(observation, dict)
                and _safe_text(observation.get("source_signal_id")) == signal_id
                for observation in observations
            ):
                summary["existing_count"] += 1
                continue
            candidates = (
                existing.get("related_signal_candidates")
                if isinstance(existing.get("related_signal_candidates"), list)
                else []
            )
            if any(
                isinstance(candidate, dict) and _safe_text(candidate.get("signal_id")) == signal_id
                for candidate in candidates
            ):
                summary["existing_count"] += 1
                continue

            reasons = _build_match_reasons(existing, signal)
            if not _is_match_candidate(reasons):
                continue
            now = _utc_now_iso()
            candidate = {
                "match_id": f"match_{uuid.uuid4().hex[:12]}",
                "watch_id": _safe_text(existing.get("watch_id")),
                "project_id": _safe_project_id(project_id),
                "signal_id": signal_id,
                "signal_title": _safe_text(signal.get("title") or signal.get("signal_title")),
                "signal_summary": _safe_text(signal.get("summary") or signal.get("signal_summary")),
                "candidate_role": WATCH_MATCH_CANDIDATE_ROLE,
                "status": "unseen",
                "match_reasons": reasons,
                "created_at": now,
            }
            updated = {
                **existing,
                "related_signal_candidates": [*candidates, candidate],
                "updated_at": now,
            }
            items[index] = updated
            changed = True
            summary["created_count"] += 1
            summary["matches"].append(
                {
                    "project_id": _safe_project_id(project_id),
                    "watch_id": candidate["watch_id"],
                    "match_id": candidate["match_id"],
                    "match_reasons": reasons,
                }
            )
        if changed:
            _save_project_watch_items(project_id, items)
    return summary


def review_project_watch_match(
    project_id: str,
    watch_id: str,
    signal_id: str,
    *,
    decision: str,
    review_note: str = "",
) -> dict[str, Any]:
    normalized_decision = _safe_text(decision).lower()
    if normalized_decision not in WATCH_MATCH_DECISIONS:
        raise ValueError("Match decision must be accept, ignore, or not_related.")
    normalized_review_note = _safe_text(review_note)
    if normalized_decision == "accept" and not normalized_review_note:
        raise ValueError("A reviewer note is required to accept a related Signal candidate.")

    payload = load_project_watch_items(project_id)
    items = payload["items"]
    for item_index, existing in enumerate(items):
        if _safe_text(existing.get("watch_id")) != _safe_text(watch_id):
            continue
        if _safe_text(existing.get("state")) != WATCH_STATE_ACTIVE:
            raise ValueError("Only active Watch items can review related Signal candidates.")
        candidates = (
            existing.get("related_signal_candidates")
            if isinstance(existing.get("related_signal_candidates"), list)
            else []
        )
        for candidate_index, candidate in enumerate(candidates):
            if not isinstance(candidate, dict) or _safe_text(candidate.get("signal_id")) != _safe_text(signal_id):
                continue
            if _safe_text(candidate.get("status")) != "unseen":
                raise ValueError("This related Signal candidate has already been reviewed.")
            now = _utc_now_iso()
            reviewed_candidate = {
                **candidate,
                "status": "accepted" if normalized_decision == "accept" else normalized_decision,
                "review_note": normalized_review_note,
                "reviewed_at": now,
            }
            updated_candidates = list(candidates)
            updated_candidates[candidate_index] = reviewed_candidate
            updated = {
                **existing,
                "related_signal_candidates": updated_candidates,
                "updated_at": now,
            }
            observation = None
            if normalized_decision == "accept":
                observations = existing.get("observations") if isinstance(existing.get("observations"), list) else []
                observation = {
                    "observation_id": f"obs_{uuid.uuid4().hex[:12]}",
                    "watch_id": _safe_text(watch_id),
                    "summary": normalized_review_note,
                    "source_signal_id": _safe_text(signal_id),
                    "evidence_role": WATCH_OBSERVATION_EVIDENCE_ROLE,
                    "observed_at": now,
                    "related_match_id": _safe_text(candidate.get("match_id")),
                }
                updated["observations"] = [*observations, observation]
                updated["observation_count"] = len(observations) + 1
                updated["last_observed_at"] = now
            items[item_index] = updated
            _save_project_watch_items(project_id, items)
            return {
                "item": _with_attention_state(updated),
                "candidate": reviewed_candidate,
                "observation": observation,
            }
        raise ValueError(f"Related Signal candidate not found: {signal_id}")
    raise ValueError(f"Watch item not found: {watch_id}")


def resolve_project_watch_item(
    project_id: str,
    watch_id: str,
    *,
    resolution_basis: str,
    resolution_note: str,
) -> dict[str, Any]:
    normalized_basis = _safe_text(resolution_basis).lower()
    if normalized_basis not in WATCH_RESOLUTION_BASES:
        raise ValueError("Resolution basis must be success_criteria_met, exit_criteria_met, no_longer_relevant, or manual_close.")
    if not _safe_text(resolution_note):
        raise ValueError("Resolution note is required.")

    payload = load_project_watch_items(project_id)
    items = payload["items"]
    for index, existing in enumerate(items):
        if _safe_text(existing.get("watch_id")) != _safe_text(watch_id):
            continue
        if _safe_text(existing.get("state")) != WATCH_STATE_ACTIVE:
            raise ValueError("Only active Watch items can be resolved.")
        now = _utc_now_iso()
        updated = {
            **existing,
            "state": WATCH_STATE_RESOLVED,
            "resolution_basis": normalized_basis,
            "resolution_note": _safe_text(resolution_note),
            "resolved_at": now,
            "updated_at": now,
        }
        items[index] = updated
        _save_project_watch_items(project_id, items)
        return _with_attention_state(updated)
    raise ValueError(f"Watch item not found: {watch_id}")
