import json
import os
import shutil
import sys
import time
import uuid
from contextlib import contextmanager
from datetime import datetime
from datetime import timezone
from pathlib import Path
from unittest.mock import patch

BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services import s3_reader  # noqa: E402

TEST_TMP_ROOT = Path(__file__).resolve().parents[1] / ".tmp-tests"


@contextmanager
def workspace_temp_dir():
    path = TEST_TMP_ROOT / f"signal_snapshot_{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def recent_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def test_load_signals_uses_recent_local_snapshot_before_s3_on_cache_miss():
    with workspace_temp_dir() as temp_dir:
        local_file = temp_dir / "signals.json"
        local_file.write_text(
            json.dumps(
                {
                    "signals": [
                        {
                            "title": "Local signal",
                            "source": "local",
                            "published_at": recent_timestamp(),
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )

        cache = {"data": None, "by_id": {}, "last_loaded": 0}
        with patch.object(s3_reader, "LOCAL_SIGNALS_FILE", local_file), patch.object(
            s3_reader, "SIGNALS_CACHE", cache
        ), patch.object(
            s3_reader,
            "_load_signals_from_s3",
            return_value=[
                {
                    "title": "S3 signal",
                    "source": "s3",
                    "published_at": "2026-05-07T00:00:00+00:00",
                }
            ],
        ) as load_s3:
            items = s3_reader.load_signals()

        assert len(items) == 1
        assert items[0]["title"] == "Local signal"
        load_s3.assert_not_called()
        assert cache["data"] == items


def test_load_signals_force_refresh_uses_s3_even_with_recent_local_snapshot():
    with workspace_temp_dir() as temp_dir:
        local_file = temp_dir / "signals.json"
        local_file.write_text(
            json.dumps(
                {
                    "signals": [
                        {
                            "title": "Local signal",
                            "source": "local",
                            "published_at": "2026-05-05T00:00:00+00:00",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )

        cache = {"data": None, "by_id": {}, "last_loaded": 0}
        with patch.object(s3_reader, "LOCAL_SIGNALS_FILE", local_file), patch.object(
            s3_reader, "SIGNALS_CACHE", cache
        ), patch.object(
            s3_reader,
            "_load_signals_from_s3",
            return_value=[
                {
                    "title": "S3 signal",
                    "source": "s3",
                    "published_at": "2026-05-07T00:00:00+00:00",
                }
            ],
        ) as load_s3:
            items = s3_reader.load_signals(force_refresh=True)

        assert len(items) == 1
        assert items[0]["title"] == "S3 signal"
        load_s3.assert_called_once()
        assert cache["data"] == items


def test_load_signals_falls_back_to_recent_local_snapshot_when_s3_unavailable():
    with workspace_temp_dir() as temp_dir:
        local_file = temp_dir / "signals.json"
        local_file.write_text(
            json.dumps(
                {
                    "signals": [
                        {
                            "title": "Stale local signal",
                            "source": "local",
                            "published_at": recent_timestamp(),
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )

        cache = {"data": None, "by_id": {}, "last_loaded": 0}
        with patch.object(s3_reader, "LOCAL_SIGNALS_FILE", local_file), patch.object(
            s3_reader, "SIGNALS_CACHE", cache
        ), patch.object(s3_reader, "_load_signals_from_s3", return_value=None) as load_s3:
            items = s3_reader.load_signals()

        assert len(items) == 1
        assert items[0]["title"] == "Stale local signal"
        load_s3.assert_not_called()
        assert cache["data"] == items


def test_load_signals_ignores_content_stale_local_snapshot_with_fresh_file_mtime():
    with workspace_temp_dir() as temp_dir:
        local_file = temp_dir / "signals.json"
        local_file.write_text(
            json.dumps(
                {
                    "signals": [
                        {
                            "title": "Fresh mtime but old content",
                            "source": "local",
                            "published_at": "2026-05-05T00:00:00+00:00",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )

        cache = {"data": None, "by_id": {}, "last_loaded": 0}
        with patch.object(s3_reader, "LOCAL_SIGNALS_FILE", local_file), patch.object(
            s3_reader, "SIGNALS_CACHE", cache
        ), patch.object(
            s3_reader,
            "_load_signals_from_s3",
            return_value=[
                {
                    "title": "S3 replacement signal",
                    "source": "s3",
                    "published_at": recent_timestamp(),
                }
            ],
        ) as load_s3:
            items = s3_reader.load_signals()

        assert len(items) == 1
        assert items[0]["title"] == "S3 replacement signal"
        load_s3.assert_called_once()
        assert cache["data"] == items


def test_load_signals_ignores_stale_local_snapshot_when_s3_unavailable():
    with workspace_temp_dir() as temp_dir:
        local_file = temp_dir / "signals.json"
        local_file.write_text(
            json.dumps(
                {
                    "signals": [
                        {
                            "title": "Stale local signal",
                            "source": "local",
                            "published_at": "2026-05-05T00:00:00+00:00",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        stale_time = time.time() - (s3_reader.LOCAL_SIGNALS_SNAPSHOT_TTL * 2)
        os.utime(local_file, (stale_time, stale_time))

        cache = {"data": None, "by_id": {}, "last_loaded": 0}
        with patch.object(s3_reader, "LOCAL_SIGNALS_FILE", local_file), patch.object(
            s3_reader, "SIGNALS_CACHE", cache
        ), patch.object(s3_reader, "_load_signals_from_s3", return_value=None) as load_s3:
            items = s3_reader.load_signals()

        assert items == []
        load_s3.assert_called_once()
        assert cache["data"] == []


def test_s3_load_writes_local_signal_snapshot():
    with workspace_temp_dir() as temp_dir:
        local_file = temp_dir / "signals.json"
        s3_items = [
            {
                "title": "S3 signal",
                "source": "s3",
                "published_at": "2026-05-05T00:00:00+00:00",
            }
        ]

        with patch.object(s3_reader, "LOCAL_SIGNALS_FILE", local_file), patch.object(
            s3_reader, "read_json", return_value={"signals": s3_items}
        ), patch.object(s3_reader, "list_json_keys", return_value=[]):
            items = s3_reader._load_signals_from_s3()

        assert len(items) == 1
        saved = json.loads(local_file.read_text(encoding="utf-8"))
        assert saved["signals"][0]["title"] == "S3 signal"


def test_s3_load_ignores_sidecar_signal_history_documents():
    with workspace_temp_dir() as temp_dir:
        local_file = temp_dir / "signals.json"

        def fake_read_json(key):
            payloads = {
                "signals/latest/signals.json": {
                    "signals": [
                        {
                            "title": "Latest signal",
                            "source": "main",
                            "published_at": "2026-05-21T00:00:00+00:00",
                        }
                    ]
                },
                "signals/2026-05-20/signals.json": {
                    "signals": [
                        {
                            "title": "Daily main signal",
                            "source": "main",
                            "published_at": "2026-05-20T00:00:00+00:00",
                        }
                    ]
                },
            }
            if key not in payloads:
                raise AssertionError(f"unexpected S3 read: {key}")
            return payloads[key]

        listed_keys = [
            "signals/2026-05-20/signals.json",
            "signals/2026-05-20/friction_signals.json",
            "signals/2026-05-20/agent_watch_signals.json",
            "signals/latest/signals.json",
            "signals/latest/friction_signals.json",
        ]

        with patch.object(s3_reader, "LOCAL_SIGNALS_FILE", local_file), patch.object(
            s3_reader, "read_json", side_effect=fake_read_json
        ), patch.object(s3_reader, "list_json_keys", return_value=listed_keys):
            items = s3_reader._load_signals_from_s3()

        assert [item["title"] for item in items] == [
            "Latest signal",
            "Daily main signal",
        ]
        saved = json.loads(local_file.read_text(encoding="utf-8"))
        assert [item["title"] for item in saved["signals"]] == [
            "Latest signal",
            "Daily main signal",
        ]


def test_targeted_update_patches_cached_and_local_signal_snapshot_without_s3_reload():
    with workspace_temp_dir() as temp_dir:
        local_file = temp_dir / "signals.json"
        signal = {
            "title": "Patchable signal",
            "source": "main",
            "published_at": "2026-05-21T00:00:00+00:00",
            "status": "pending",
        }
        signal_id = s3_reader.build_signal_identity(signal)
        signal["signal_id"] = signal_id
        local_file.write_text(json.dumps({"signals": [signal]}), encoding="utf-8")

        cache = {"data": None, "by_id": {}, "last_loaded": 0}

        def update_fn(item):
            item["status"] = "saved"
            item["saved_reason"] = "keep"

        with patch.object(s3_reader, "LOCAL_SIGNALS_FILE", local_file), patch.object(
            s3_reader, "SIGNALS_CACHE", cache
        ), patch.object(s3_reader, "load_signals", return_value=[]) as load_s3:
            s3_reader._refresh_signals_after_targeted_update(signal_id, update_fn)

        load_s3.assert_not_called()
        assert cache["data"][0]["status"] == "saved"
        assert cache["by_id"][signal_id]["saved_reason"] == "keep"

        saved = json.loads(local_file.read_text(encoding="utf-8"))
        assert saved["signals"][0]["status"] == "saved"
        assert saved["signals"][0]["saved_reason"] == "keep"


def test_s3_load_returns_none_without_overwriting_local_snapshot_when_s3_unavailable():
    with workspace_temp_dir() as temp_dir:
        local_file = temp_dir / "signals.json"
        local_file.write_text(
            json.dumps({"signals": [{"title": "Existing local signal"}]}),
            encoding="utf-8",
        )

        with patch.object(s3_reader, "LOCAL_SIGNALS_FILE", local_file), patch.object(
            s3_reader, "read_json", side_effect=RuntimeError("missing credentials")
        ), patch.object(s3_reader, "list_json_keys", side_effect=RuntimeError("missing credentials")):
            items = s3_reader._load_signals_from_s3()

        assert items is None
        saved = json.loads(local_file.read_text(encoding="utf-8"))
        assert saved["signals"][0]["title"] == "Existing local signal"
