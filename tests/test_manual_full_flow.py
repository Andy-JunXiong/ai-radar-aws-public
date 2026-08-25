import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient


BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os.environ["AI_RADAR_BACKEND_PRELOAD_CACHE"] = "false"

from app.main import app  # noqa: E402
from app.routes import manual as manual_route  # noqa: E402
from app.routes import signals as signals_route  # noqa: E402
from app.services.admin_guard import require_admin_auth  # noqa: E402


def test_manual_upload_http_reaches_canonical_signal_detail():
    with tempfile.TemporaryDirectory() as temp_dir:
        upload_dir = Path(temp_dir) / "manual_uploads"
        sessions_dir = upload_dir / "sessions"
        index_path = sessions_dir / "index.json"
        upload_dir.mkdir(parents=True)
        sessions_dir.mkdir(parents=True)

        app.dependency_overrides[require_admin_auth] = lambda: None
        try:
            with (
                patch.object(manual_route, "UPLOAD_DIR", upload_dir),
                patch.object(manual_route, "SESSIONS_DIR", sessions_dir),
                patch.object(manual_route, "SESSIONS_INDEX_PATH", index_path),
                patch.object(manual_route, "resolve_request_user_id", return_value=None),
                patch.object(manual_route, "resolve_analysis_context", return_value=({}, "test")),
                patch.object(manual_route, "_manual_sessions_prefer_s3_reads", return_value=False),
                patch.object(manual_route, "_read_s3_json", return_value=None),
                patch.object(manual_route, "_write_s3_file") as write_s3_file,
                patch.object(manual_route, "_write_s3_json") as write_s3_json,
                patch.object(signals_route, "MANUAL_SESSIONS_DIR", sessions_dir),
                patch.object(signals_route, "MANUAL_SESSIONS_INDEX_PATH", index_path),
                patch.object(signals_route, "resolve_request_user_id", return_value=None),
                patch.object(signals_route, "load_subscription_settings", return_value={}),
                patch.object(
                    signals_route,
                    "apply_subscription_settings_to_signals",
                    side_effect=lambda items, _settings: items,
                ),
            ):
                client = TestClient(app)
                upload_response = client.post(
                    "/manual/upload",
                    files={
                        "files": (
                            "flow-fixture.md",
                            b"# Manual fixture\nObservation only; not verified evidence.",
                            "text/markdown",
                        )
                    },
                    data={
                        "upload_reason": "Validate canonical handoff",
                        "intended_use": "Signal Detail regression",
                        "cognitive_layer": "L2",
                    },
                )
                session_id = upload_response.json()["session_id"]

                manual_route.update_session_analysis(
                    session_id,
                    {
                        "summary": "A safe Manual Upload fixture.",
                        "why_it_matters": "It checks the current local handoff contract.",
                        "relevance_to_projects": {"AI Radar": "Regression coverage only."},
                        "relevance_to_career": "No external claim is introduced.",
                        "synthesized_insight": "Keep manual provenance explicit.",
                        "topic": "Manual Upload",
                    },
                )

                signal_response = client.get(f"/signals/manual_{session_id}")
                signal = signal_response.json()
        finally:
            app.dependency_overrides.pop(require_admin_auth, None)

    assert upload_response.status_code == 200
    assert signal_response.status_code == 200
    assert signal["id"] == f"manual_{session_id}"
    assert signal["signal_id"] == f"manual_{session_id}"
    assert signal["manual_session_id"] == session_id
    assert signal["is_manual"] is True
    assert signal["analysis_status"] == "completed"
    assert signal["summary"] == "A safe Manual Upload fixture."
    assert signal["upload_reason"] == "Validate canonical handoff"
    assert signal["intended_use"] == "Signal Detail regression"
    assert signal["verification"] is None
    assert write_s3_file.call_count == 2
    assert write_s3_json.call_count == 4
