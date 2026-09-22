import io
import json
import sys
import tracemalloc
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from botocore.response import StreamingBody
from botocore.exceptions import IncompleteReadError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.services import s3_reader


def test_s3_stream_matches_json_and_closes_body():
    encoded = json.dumps({"signals": [{"signal_id": "s1", "score": 0.8}]}).encode()
    raw = io.BytesIO(encoded)
    body = StreamingBody(raw, len(encoded))
    client = Mock()
    client.get_object.return_value = {"Body": body}
    with patch.object(s3_reader, "s3", client):
        assert s3_reader.read_json("signals/latest/signals.json") == json.loads(encoded)
    assert raw.closed


def test_invalid_s3_json_is_not_a_successful_partial_payload():
    raw = io.BytesIO(b'{"signals":[]} garbage')
    body = StreamingBody(raw, len(raw.getvalue()))
    client = Mock()
    client.get_object.return_value = {"Body": body}
    with patch.object(s3_reader, "s3", client), pytest.raises(json.JSONDecodeError):
        s3_reader.read_json("signals/latest/signals.json")
    assert raw.closed


def test_s3_stream_preserves_content_length_validation():
    raw = io.BytesIO(b'{}')
    body = StreamingBody(raw, 50)
    client = Mock()
    client.get_object.return_value = {"Body": body}
    with patch.object(s3_reader, "s3", client), pytest.raises(IncompleteReadError):
        s3_reader.read_json("signals/latest/signals.json")
    assert raw.closed


def test_snapshot_write_preserves_previous_file_on_serialization_failure(tmp_path):
    path = tmp_path / "signals.json"
    before = b'{"signals": [{"signal_id": "previous"}]}'
    path.write_bytes(before)
    with pytest.raises(TypeError):
        s3_reader.write_local_json(path, {"signals": ["started", object()]})
    assert path.read_bytes() == before
    assert list(tmp_path.iterdir()) == [path]


def test_snapshot_write_has_bounded_peak_and_identical_json(tmp_path):
    path = tmp_path / "signals.json"
    payload = {"signals": [{"content": "a" * 4096} for _ in range(2048)]}
    payload["signals"][-1]["content"] += chr(0x1F600)
    expected = json.dumps(payload, ensure_ascii=False, indent=2)
    tracemalloc.start()
    try:
        s3_reader.write_local_json(path, payload)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert peak < 1024 * 1024
    assert path.read_text(encoding="utf-8") == expected
    assert s3_reader.read_local_json(path) == payload
    assert list(tmp_path.iterdir()) == [path]
