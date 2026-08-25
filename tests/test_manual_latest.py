import sys
import tempfile
from pathlib import Path
from unittest.mock import patch


BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.routes import manual as manual_route  # noqa: E402


def test_manual_latest_index_orders_newest_session_first():
    with tempfile.TemporaryDirectory() as temp_dir:
        sessions_dir = Path(temp_dir) / "manual_uploads" / "sessions"
        index_path = sessions_dir / "index.json"
        sessions_dir.mkdir(parents=True)

        older = {
            "session_id": "manual-older",
            "title": "Older session",
            "created_at": "2026-08-24T00:00:00+00:00",
        }
        newer = {
            "session_id": "manual-newer",
            "title": "Newer session",
            "created_at": "2026-08-25T00:00:00+00:00",
        }

        with (
            patch.object(manual_route, "SESSIONS_DIR", sessions_dir),
            patch.object(manual_route, "SESSIONS_INDEX_PATH", index_path),
            patch.object(manual_route, "_manual_sessions_prefer_s3_reads", return_value=False),
            patch.object(manual_route, "_read_s3_json", return_value=None),
            patch.object(manual_route, "_write_s3_json") as write_s3_json,
        ):
            manual_route.upsert_session_index_item(older)
            manual_route.upsert_session_index_item(newer)
            items = manual_route.load_sessions_index()

    assert [item["session_id"] for item in items] == ["manual-newer", "manual-older"]
    assert write_s3_json.call_count == 2
