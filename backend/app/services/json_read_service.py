"""Decode JSON streams without allocating a document-sized text buffer."""

from decimal import Decimal
from json import JSONDecodeError
from typing import Any, BinaryIO

import ijson


def load_json_stream(stream: BinaryIO) -> Any:
    # Keep arbitrary-size integers and stdlib float semantics. ijson's
    # use_float option can also constrain integers on its C backend.
    events = (
        (prefix, event, float(value) if isinstance(value, Decimal) else value)
        for prefix, event, value in ijson.parse(stream)
    )
    objects = ijson.items(events, "")
    missing = object()
    try:
        value = next(objects, missing)
        # Consume EOF so trailing garbage cannot turn into a successful read.
        extra = next(objects, missing)
    except ijson.JSONError as exc:
        raise JSONDecodeError("Invalid JSON document", "", 0) from exc
    if value is missing or extra is not missing:
        raise JSONDecodeError("Expected one JSON document", "", 0)
    return value
