import sys
import tempfile
from pathlib import Path
from unittest.mock import patch


BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.routes import manual as manual_route  # noqa: E402


def test_manual_session_persists_current_schema_and_index_locally():
    with tempfile.TemporaryDirectory() as temp_dir:
        upload_dir = Path(temp_dir) / "manual_uploads"
        sessions_dir = upload_dir / "sessions"
        index_path = sessions_dir / "index.json"
        upload_dir.mkdir(parents=True)
        sessions_dir.mkdir(parents=True)

        files = [
            {
                "message": "file uploaded successfully",
                "stored_filename": "fixture-note.txt",
                "original_filename": "fixture-note.txt",
                "file_kind": "text",
                "preview_text": "A bounded Manual Upload fixture.",
            }
        ]

        with (
            patch.object(manual_route, "UPLOAD_DIR", upload_dir),
            patch.object(manual_route, "SESSIONS_DIR", sessions_dir),
            patch.object(manual_route, "SESSIONS_INDEX_PATH", index_path),
            patch.object(manual_route, "resolve_analysis_context", return_value=({}, "test")),
            patch.object(manual_route, "_manual_sessions_prefer_s3_reads", return_value=False),
            patch.object(manual_route, "_read_s3_json", return_value=None),
            patch.object(manual_route, "_write_s3_json") as write_s3_json,
        ):
            session = manual_route.create_manual_session(
                files,
                upload_reason="Exercise the current Manual Upload path",
                intended_use="Regression testing",
                cognitive_layer="L2",
            )
            loaded = manual_route.load_session_detail(session["session_id"])
            index_items = manual_route.load_sessions_index()

    assert session["session_schema_version"] == manual_route.MANUAL_SESSION_SCHEMA_VERSION
    assert session["status"] == "pending"
    assert session["analysis_status"] == "not_started"
    assert session["files"] == files
    assert loaded == session
    assert len(index_items) == 1
    assert index_items[0]["session_id"] == session["session_id"]
    assert index_items[0]["upload_reason"] == "Exercise the current Manual Upload path"
    assert write_s3_json.call_count == 2
    assert all(call.args[0].startswith("manual/sessions/") for call in write_s3_json.call_args_list)
