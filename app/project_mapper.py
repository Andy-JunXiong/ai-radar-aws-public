from __future__ import annotations

from typing import Any, Dict, List

from app.project_registry import list_active_projects


def _normalize_text(text: str) -> str:
    return (text or "").strip().lower()


def _project_match_score(project: Dict[str, Any], text: str) -> int:
    normalized_text = _normalize_text(text)
    if not normalized_text:
        return 0

    score = 0

    name = _normalize_text(project.get("name", ""))
    description = _normalize_text(project.get("description", ""))
    topics = [_normalize_text(t) for t in project.get("topics", [])]

    if name and name in normalized_text:
        score += 5

    if description:
        desc_words = [w for w in description.split() if len(w) >= 5]
        for word in desc_words:
            if word in normalized_text:
                score += 1

    for topic in topics:
        if topic and topic in normalized_text:
            score += 3
        else:
            topic_words = [w for w in topic.split() if len(w) >= 4]
            for word in topic_words:
                if word in normalized_text:
                    score += 1

    return score


def find_relevant_projects(text: str, min_score: int = 2) -> List[Dict[str, Any]]:
    projects = list_active_projects()
    scored_projects = []

    for project in projects:
        score = _project_match_score(project, text)
        if score >= min_score:
            scored_projects.append(
                {
                    "project_id": project.get("project_id"),
                    "name": project.get("name"),
                    "status": project.get("status"),
                    "score": score,
                    "topics": project.get("topics", []),
                }
            )

    scored_projects.sort(key=lambda x: x["score"], reverse=True)
    return scored_projects
