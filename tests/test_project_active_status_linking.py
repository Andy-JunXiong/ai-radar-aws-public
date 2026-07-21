import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services import project_intelligence_service  # noqa: E402
from app.services import subscription_settings_service  # noqa: E402


def _projects():
    return [
        {
            "project_id": "active_project",
            "name": "Active Project",
            "status": "active",
            "enabled": True,
            "topics": ["agent memory"],
            "description": "Active project description",
        },
        {
            "project_id": "research_project",
            "name": "Research Project",
            "status": "research",
            "enabled": True,
            "topics": ["agent memory"],
            "description": "Research project description",
        },
        {
            "project_id": "disabled_project",
            "name": "Disabled Project",
            "status": "active",
            "enabled": False,
            "topics": ["agent memory"],
            "description": "Disabled project description",
        },
    ]


def test_subscription_project_links_only_match_active_registry_projects(monkeypatch):
    monkeypatch.setattr(
        subscription_settings_service,
        "list_active_projects",
        lambda: [_projects()[0]],
    )

    settings = {
        "project_links": [
            {
                "project_id": "active_project",
                "enabled": True,
                "topic_keywords": ["agent memory"],
            },
            {
                "project_id": "research_project",
                "enabled": True,
                "topic_keywords": ["agent memory"],
            },
            {
                "project_id": "disabled_project",
                "enabled": True,
                "topic_keywords": ["agent memory"],
            },
        ]
    }

    matches = subscription_settings_service.match_subscription_project_links(
        "This paper studies agent memory.",
        settings,
    )

    assert [item["project_id"] for item in matches] == ["active_project"]


def test_subscription_context_excludes_non_active_project_links(monkeypatch):
    monkeypatch.setattr(
        subscription_settings_service,
        "list_active_projects",
        lambda: [_projects()[0]],
    )
    monkeypatch.setattr(
        subscription_settings_service,
        "load_subscription_settings",
        lambda _: {
            "sources": [],
            "topic_preferences": {},
            "signal_rules": {},
            "project_links": [
                {"project_id": "active_project", "enabled": True, "topic_keywords": ["agent memory"]},
                {"project_id": "research_project", "enabled": True, "topic_keywords": ["agent memory"]},
            ],
        },
    )

    context = json.loads(subscription_settings_service.build_subscription_settings_context("demo"))

    assert context["project_linked_intake"] == [
        {"project_id": "active_project", "topic_keywords": ["agent memory"]}
    ]


def test_apply_subscription_settings_to_signals_only_adds_active_project_links(monkeypatch):
    monkeypatch.setattr(
        subscription_settings_service,
        "list_active_projects",
        lambda: [_projects()[0]],
    )

    signals = [
        {
            "title": "Agent memory paper",
            "summary": "New agent memory technique.",
            "score": 90,
        }
    ]
    settings = {
        "sources": [],
        "topic_preferences": {},
        "signal_rules": {},
        "project_links": [
            {"project_id": "active_project", "enabled": True, "topic_keywords": ["agent memory"]},
            {"project_id": "research_project", "enabled": True, "topic_keywords": ["agent memory"]},
        ],
    }

    enriched = subscription_settings_service.apply_subscription_settings_to_signals(signals, settings)

    assert [item["project_id"] for item in enriched[0]["subscription_project_links"]] == ["active_project"]


def test_project_analysis_context_only_lists_active_projects(monkeypatch):
    monkeypatch.setattr(project_intelligence_service, "list_active_projects", lambda: [_projects()[0]])
    monkeypatch.setattr(project_intelligence_service, "load_cached_project_context", lambda _: None)

    context = project_intelligence_service.build_project_analysis_context()

    assert "Active Project" in context
    assert "Research Project" not in context
    assert "Disabled Project" not in context


def test_project_takeaway_resolution_only_uses_active_projects(monkeypatch):
    monkeypatch.setattr(project_intelligence_service, "list_active_projects", lambda: [_projects()[0]])

    resolved = project_intelligence_service._resolve_projects_for_takeaway_map(
        {
            "Active Project": "Useful for active project.",
            "Research Project": "Should not resolve while non-active.",
        },
        subscription_project_links=[
            {"project_id": "active_project", "match_score": 2},
            {"project_id": "research_project", "match_score": 2},
        ],
    )

    assert [item["project"]["project_id"] for item in resolved] == ["active_project"]
