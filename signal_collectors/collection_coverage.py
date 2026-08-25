from __future__ import annotations

from collections.abc import Iterable
from typing import Any


COVERAGE_SCHEMA_VERSION = "collector-coverage-v1"


class InvalidCollectionResponse(ValueError):
    pass


def failure_reason_code(exc: BaseException) -> str:
    """Return a bounded reason code without persisting exception details."""
    if isinstance(exc, InvalidCollectionResponse):
        return "invalid_response"
    class_name = type(exc).__name__.lower()
    if "timeout" in class_name:
        return "timeout"
    if "http" in class_name:
        return "http_error"
    if "url" in class_name or "connection" in class_name:
        return "connection_error"
    return "request_error"


class CollectionCoverageTracker:
    def __init__(self, *, unit_type: str, expected_count: int, unit_prefix: str):
        if expected_count < 0:
            raise ValueError("expected_count must be non-negative")
        self.unit_type = unit_type
        self._expected_unit_ids = [
            f"{unit_prefix}_{index:03d}" for index in range(1, expected_count + 1)
        ]
        self._attempted_unit_ids: list[str] = []
        self._succeeded_unit_ids: list[str] = []
        self._zero_result_unit_ids: list[str] = []
        self._failed_units: dict[str, str] = {}
        self._skipped_units: dict[str, str] = {}

    def _unit_id(self, index: int) -> str:
        try:
            return self._expected_unit_ids[index]
        except IndexError as exc:
            raise ValueError(f"unknown coverage unit index: {index}") from exc

    def attempt(self, index: int) -> None:
        unit_id = self._unit_id(index)
        if unit_id not in self._attempted_unit_ids:
            self._attempted_unit_ids.append(unit_id)

    def succeed(self, index: int, *, item_count: int) -> None:
        unit_id = self._unit_id(index)
        self.attempt(index)
        self._failed_units.pop(unit_id, None)
        self._skipped_units.pop(unit_id, None)
        if unit_id not in self._succeeded_unit_ids:
            self._succeeded_unit_ids.append(unit_id)
        if item_count == 0 and unit_id not in self._zero_result_unit_ids:
            self._zero_result_unit_ids.append(unit_id)
        elif item_count > 0 and unit_id in self._zero_result_unit_ids:
            self._zero_result_unit_ids.remove(unit_id)

    def fail(self, index: int, *, reason_code: str) -> None:
        unit_id = self._unit_id(index)
        self.attempt(index)
        if unit_id in self._succeeded_unit_ids:
            self._succeeded_unit_ids.remove(unit_id)
        if unit_id in self._zero_result_unit_ids:
            self._zero_result_unit_ids.remove(unit_id)
        self._skipped_units.pop(unit_id, None)
        self._failed_units[unit_id] = reason_code

    def skip(self, index: int, *, reason_code: str) -> None:
        unit_id = self._unit_id(index)
        if unit_id in self._succeeded_unit_ids:
            self._succeeded_unit_ids.remove(unit_id)
        if unit_id in self._zero_result_unit_ids:
            self._zero_result_unit_ids.remove(unit_id)
        self._failed_units.pop(unit_id, None)
        self._skipped_units[unit_id] = reason_code

    def to_dict(self) -> dict[str, Any]:
        terminal_unit_ids = set(self._succeeded_unit_ids)
        terminal_unit_ids.update(self._failed_units)
        terminal_unit_ids.update(self._skipped_units)
        expected_unit_ids = set(self._expected_unit_ids)
        complete = (
            set(self._attempted_unit_ids) == expected_unit_ids
            and terminal_unit_ids == expected_unit_ids
            and not self._failed_units
            and not self._skipped_units
        )
        return {
            "plan_version": COVERAGE_SCHEMA_VERSION,
            "unit_type": self.unit_type,
            "expected_unit_ids": list(self._expected_unit_ids),
            "attempted_unit_ids": list(self._attempted_unit_ids),
            "succeeded_unit_ids": list(self._succeeded_unit_ids),
            "zero_result_unit_ids": list(self._zero_result_unit_ids),
            "failed_units": [
                {"unit_id": unit_id, "reason_code": reason_code}
                for unit_id, reason_code in self._failed_units.items()
            ],
            "skipped_units": [
                {"unit_id": unit_id, "reason_code": reason_code}
                for unit_id, reason_code in self._skipped_units.items()
            ],
            "complete": complete,
        }


class CollectedItems(list):
    """List-compatible collector result carrying additive coverage telemetry."""

    def __init__(self, items: Iterable[Any] = (), *, coverage: dict[str, Any]):
        super().__init__(items)
        self.coverage = coverage


def with_collection_coverage(
    items: Iterable[Any],
    tracker: CollectionCoverageTracker,
) -> CollectedItems:
    return CollectedItems(items, coverage=tracker.to_dict())
