import io
import json
import sys
import tracemalloc
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.services.json_read_service import load_json_stream


@pytest.mark.parametrize("text", [
    'null', 'true', '42', '1.25', '"text"', '[]', '{}',
    '{"x":1,"x":2}',
    '[123456789012345678901234567890, 1e400, -1e400, 1e-400, -0.0]',
    '{"signals":[{"raw":{"items":[1,2]},"summary":"\\u03b1\\ud83d\\ude00"}]}',
])
def test_stream_decoder_preserves_stdlib_values(text):
    expected = json.loads(text)
    actual = load_json_stream(io.BytesIO(text.encode("utf-8")))
    assert actual == expected
    if isinstance(expected, list):
        assert [type(value) for value in actual] == [type(value) for value in expected]


@pytest.mark.parametrize("text", ['', ' ', '{', '[1,', '{} trailing', '{} {}', '[01]', '{"a":}'])
def test_stream_decoder_rejects_incomplete_or_trailing_json(text):
    with pytest.raises(json.JSONDecodeError):
        load_json_stream(io.BytesIO(text.encode("utf-8")))


def test_large_ascii_document_with_unicode_has_bounded_decode_peak():
    # A supplementary character widens a whole-document Unicode buffer.
    payload = [{"content": "a" * 4096} for _ in range(2048)]
    payload[-1]["content"] += chr(0x1F600)
    encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    stream = io.BytesIO(encoded)
    tracemalloc.start()
    try:
        decoded = load_json_stream(stream)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert decoded == payload
    assert peak < len(encoded) * 2
