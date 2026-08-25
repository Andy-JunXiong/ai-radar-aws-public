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
from app.services.admin_guard import require_admin_auth  # noqa: E402


def test_manual_file_upload_http_uses_local_storage_and_preserves_intent():
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
            ):
                client = TestClient(app)
                response = client.post(
                    "/manual/upload",
                    files={
                        "files": (
                            "fixture-note.txt",
                            b"Manual Upload HTTP fixture with bounded local content.",
                            "text/plain",
                        )
                    },
                    data={
                        "upload_reason": "Validate multipart upload",
                        "intended_use": "Manual E2E regression",
                        "cognitive_layer": "L2",
                    },
                )

                payload = response.json()
                session_id = payload["session_id"]
                detail_response = client.get(f"/manual/session/{session_id}")
                detail = detail_response.json()["session"]

                stored_path = upload_dir / payload["files"][0]["stored_filename"]
                stored_content = stored_path.read_text(encoding="utf-8")
        finally:
            app.dependency_overrides.pop(require_admin_auth, None)

    assert response.status_code == 200
    assert detail_response.status_code == 200
    assert session_id
    assert payload["files"][0]["message"] == "file uploaded successfully"
    assert payload["files"][0]["file_kind"] == "text"
    assert stored_content == "Manual Upload HTTP fixture with bounded local content."
    assert detail["session_id"] == session_id
    assert detail["upload_reason"] == "Validate multipart upload"
    assert detail["intended_use"] == "Manual E2E regression"
    assert detail["cognitive_layer"] == "L2"
    assert write_s3_file.call_count == 2
    assert write_s3_json.call_count == 2
