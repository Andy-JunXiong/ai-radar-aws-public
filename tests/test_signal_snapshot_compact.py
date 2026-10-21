"""Contract tests for compact local Signals snapshots."""

import json
import sys
import tracemalloc
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.services import s3_reader


def _signal(title="Signal", **extra):
    return {
        "title": title,
        "url": f"https://example.test/{title}",
        "source": "official",
        "published_at": "2026-10-21T00:00:00+00:00",
        **extra,
    }


def test_compact_write_is_exact_ordered_unicode_and_memory_bounded(tmp_path):
    path = tmp_path / "signals.json"
    data = {
        "signals": [
            _signal(
                "café😀",
                verification_metadata={
                    "verification_status": "weakly_supported",
                    "blocked_downstream_actions": ["low_risk_action_candidate"],
                },
            )
        ],
        "meta": {"ordered": True},
    }

    s3_reader.write_local_json(path, data, compact=True)

    assert path.read_text(encoding="utf-8") == json.dumps(
        data, ensure_ascii=False, indent=None, separators=(",", ":")
    )

    large_data = {"signals": [{"text": "😀" * 1024} for _ in range(2048)]}
    large_path = tmp_path / "large-signals.json"
    tracemalloc.start()
    try:
        s3_reader.write_local_json(large_path, large_data, compact=True)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert json.loads(large_path.read_text(encoding="utf-8")) == large_data
    assert peak < 1024 * 1024


def test_compact_write_serialization_error_preserves_old_bytes_and_cleans_temp(tmp_path):
    path = tmp_path / "signals.json"
    old_bytes = b'{"signals":[{"title":"old"}]}'
    path.write_bytes(old_bytes)

    try:
        s3_reader.write_local_json(path, {"signals": [object()]}, compact=True)
    except TypeError:
        pass
    else:
        raise AssertionError("an unserializable payload must fail")

    assert path.read_bytes() == old_bytes
    assert list(tmp_path.glob(f".{path.name}.*.tmp")) == []


def test_compact_write_replace_error_preserves_old_bytes_and_cleans_temp(tmp_path):
    path = tmp_path / "signals.json"
    old_bytes = b'{"signals":[{"title":"old"}]}'
    path.write_bytes(old_bytes)

    with patch.object(s3_reader.os, "replace", side_effect=OSError("synthetic replace failure")):
        try:
            s3_reader.write_local_json(path, {"signals": [_signal()]}, compact=True)
        except OSError:
            pass
        else:
            raise AssertionError("replace failure must propagate")

    assert path.read_bytes() == old_bytes
    assert list(tmp_path.glob(f".{path.name}.*.tmp")) == []


def test_loader_writes_compact_snapshot(tmp_path):
    path = tmp_path / "signals.json"
    payload = {"signals": [_signal("loaded") ]}

    with patch.object(s3_reader, "LOCAL_SIGNALS_FILE", path), patch.object(
        s3_reader, "read_json", return_value=payload
    ), patch.object(s3_reader, "list_json_keys", return_value=[]):
        items = s3_reader._load_signals_from_s3()

    assert path.read_text(encoding="utf-8") == json.dumps(
        {"signals": items}, ensure_ascii=False, indent=None, separators=(",", ":")
    )


def test_targeted_snapshot_update_writes_compact_without_reload(tmp_path):
    path = tmp_path / "signals.json"
    item = _signal("patchable", status="pending")
    item["signal_id"] = s3_reader.build_signal_identity(item)
    path.write_text(json.dumps({"signals": [item]}), encoding="utf-8")
    cache = {"data": None, "by_id": {}, "last_loaded": 0}

    def update(current):
        current["status"] = "saved"

    with patch.object(s3_reader, "LOCAL_SIGNALS_FILE", path), patch.object(
        s3_reader, "SIGNALS_CACHE", cache
    ), patch.object(s3_reader, "load_signals", return_value=[]) as reload:
        s3_reader._refresh_signals_after_targeted_update(item["signal_id"], update)

    reload.assert_not_called()
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["signals"][0]["status"] == "saved"
    assert path.read_text(encoding="utf-8") == json.dumps(
        saved, ensure_ascii=False, indent=None, separators=(",", ":")
    )
