from __future__ import annotations

from typing import Any, Dict, List

from app.project_mapper import find_relevant_projects
from app.project_registry import map_signal_to_project


def link_signal_to_projects(
    signal_id: str,
    text: str,
    min_score: int = 2,
) -> List[Dict[str, Any]]:
    """
    Find relevant projects for a signal text and write the signal_id
    into each matched project's related_signals list.
    """
    matched_projects = find_relevant_projects(text, min_score=min_score)

    linked_projects: List[Dict[str, Any]] = []

    for project in matched_projects:
        project_id = project.get("project_id")
        if not project_id:
            continue

        updated_project = map_signal_to_project(project_id, signal_id)

        linked_projects.append(
            {
                "project_id": updated_project.get("project_id"),
                "name": updated_project.get("name"),
                "status": updated_project.get("status"),
                "score": project.get("score", 0),
                "related_signals": updated_project.get("related_signals", []),
            }
        )

    return linked_projects