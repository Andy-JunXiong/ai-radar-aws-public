import os
import sys
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os.environ["AI_RADAR_BACKEND_PRELOAD_CACHE"] = "false"

from app.main import app  # noqa: E402
from app.routes.signals import normalize_manual_session, normalize_signal  # noqa: E402


def _raw_signal(
    signal_id: str,
    *,
    importance_level=None,
    importance_reason=None,
    status: str = "pending",
) -> dict:
    signal = {
        "id": signal_id,
        "title": f"Signal {signal_id}",
        "summary": "Stored signal summary.",
        "source": "test",
        "url": f"https://example.com/{signal_id}",
        "published_at": "2026-08-25T01:00:00Z",
        "collected_at": "2026-08-25T02:00:00Z",
        "status": status,
    }
    if importance_level is not None:
        signal["importance_level"] = importance_level
    if importance_reason is not None:
        signal["importance_reason"] = importance_reason
    return signal


def test_normalize_signal_preserves_exact_importance_metadata():
    normalized = normalize_signal(
        _raw_signal(
            "high-signal",
            importance_level="high",
            importance_reason=["high_final_score", "strategic_topic"],
        ),
        0,
    )

    assert normalized["importance_level"] == "high"
    assert normalized["importance_reason"] == [
        "high_final_score",
        "strategic_topic",
    ]


def test_normalize_signal_does_not_default_missing_or_invalid_importance_to_low():
    missing = normalize_signal(_raw_signal("missing-signal"), 0)
    invalid = normalize_signal(
        _raw_signal(
            "invalid-signal",
            importance_level="unexpected",
            importance_reason="not-a-list",
        ),
        1,
    )

    assert missing["importance_level"] is None
    assert missing["importance_reason"] is None
    assert invalid["importance_level"] == "unexpected"
    assert invalid["importance_reason"] == "not-a-list"


def test_manual_signal_preserves_importance_metadata_for_same_fail_closed_shape():
    normalized = normalize_manual_session(
        {
            "session_id": "manual-high",
            "title": "Manual high signal",
            "created_at": "2026-08-25T02:00:00Z",
            "importance_level": "high",
            "importance_reason": ["high_final_score"],
        },
        0,
    )

    assert normalized["importance_level"] == "high"
    assert normalized["importance_reason"] == ["high_final_score"]


def test_signals_route_projects_high_medium_low_and_missing_importance():
    stored_signals = [
        _raw_signal(
            "high-signal",
            importance_level="high",
            importance_reason=["high_final_score", "strategic_topic"],
        ),
        _raw_signal(
            "medium-signal",
            importance_level="medium",
            importance_reason=["moderate_final_score"],
        ),
        _raw_signal(
            "low-signal",
            importance_level="low",
            importance_reason=[],
        ),
        _raw_signal("missing-signal"),
    ]

    with (
        patch("app.routes.signals.load_signals", return_value=stored_signals),
        patch("app.routes.signals.load_local_manual_sessions", return_value=[]),
        patch("app.routes.signals.load_subscription_settings", return_value={}),
        patch(
            "app.routes.signals.apply_subscription_settings_to_signals",
            side_effect=lambda items, _settings: items,
        ),
        patch("app.routes.signals.get_last_signal_load_diagnostic", return_value={}),
        patch("app.routes.signals.record_signal_timeline_load", return_value=None),
    ):
        response = TestClient(app).get("/signals?status=all")

    assert response.status_code == 200
    by_id = {item["signal_id"]: item for item in response.json()["signals"]}
    assert by_id["high-signal"]["importance_level"] == "high"
    assert by_id["high-signal"]["importance_reason"] == [
        "high_final_score",
        "strategic_topic",
    ]
    assert by_id["medium-signal"]["importance_level"] == "medium"
    assert by_id["low-signal"]["importance_level"] == "low"
    assert by_id["low-signal"]["importance_reason"] == []
    assert by_id["missing-signal"]["importance_level"] is None
    assert by_id["missing-signal"]["importance_reason"] is None


def test_high_importance_projection_does_not_create_candidate_or_change_verification():
    raw = _raw_signal(
        "high-without-candidate",
        importance_level="high",
        importance_reason=["high_final_score"],
    )
    raw["verification"] = {
        "verification_status": "unverified",
        "blocked_downstream_actions": ["action"],
    }

    with (
        patch("app.routes.signals.load_signals", return_value=[raw]),
        patch("app.routes.signals.load_local_manual_sessions", return_value=[]),
        patch("app.routes.signals.load_subscription_settings", return_value={}),
        patch(
            "app.routes.signals.apply_subscription_settings_to_signals",
            side_effect=lambda items, _settings: items,
        ),
        patch("app.routes.signals.get_last_signal_load_diagnostic", return_value={}),
        patch("app.routes.signals.record_signal_timeline_load", return_value=None),
    ):
        response = TestClient(app).get("/signals?status=all")

    item = response.json()["signals"][0]
    assert item["importance_level"] == "high"
    assert item["verification"] == raw["verification"]
    assert item["verification"]["blocked_downstream_actions"] == ["action"]
    assert "takeaway_candidate" not in item
    assert "review_action" not in item
