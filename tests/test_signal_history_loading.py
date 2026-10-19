"""History throughput must preserve merge order, gates and bounded work."""
import copy
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event, Lock
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.services import s3_reader


def history_keys(count=8):
    return [f"signals/2026-10-{day:02d}/signals.json" for day in range(count, 0, -1)]


def signal(label, **extra):
    return {"title": label, "url": f"https://example.test/{label}",
            "source": "official", "collected_at": "2026-10-19T00:00:00+00:00",
            **extra}


class ObservedLoadLock:
    """Expose a contending caller without timing-based sleeps in the test."""
    def __init__(self):
        self.lock = Lock()
        self.counter_lock = Lock()
        self.entries = 0
        self.second_attempt = Event()

    def __enter__(self):
        with self.counter_lock:
            self.entries += 1
            if self.entries == 2:
                self.second_attempt.set()
        self.lock.acquire()

    def __exit__(self, *args):
        self.lock.release()


def test_history_reads_overlap_but_do_not_run_ahead_of_the_four_result_window():
    keys = history_keys()
    first_started, batch_started, release = Event(), Event(), Event()
    seen, lock = [], Lock()

    def read(key):
        if key == "signals/latest/signals.json":
            return {"signals": []}
        with lock:
            seen.append(key)
            if len(seen) == 4:
                batch_started.set()
        if key == keys[0]:
            first_started.set()
            assert release.wait(5), "test did not release first history read"
        return {"signals": [signal(key)]}

    with patch.object(s3_reader, "read_json", side_effect=read), patch.object(
        s3_reader, "list_json_keys", return_value=keys
    ), patch.object(s3_reader, "write_local_json"), ThreadPoolExecutor(max_workers=1) as caller:
        future = caller.submit(s3_reader._load_signals_from_s3)
        try:
            assert first_started.wait(2)
            assert batch_started.wait(2), "history reads are still sequential"
            with lock:
                assert set(seen) == set(keys[:4])
        finally:
            release.set()
        result = future.result(timeout=5)
    assert len(result) == len(keys)
    assert sorted(seen) == sorted(keys)


def test_consumed_slot_is_replenished_without_waiting_for_later_reads():
    keys = history_keys()
    initial_four_started, fifth_started, release = Event(), Event(), Event()
    seen, lock = [], Lock()

    def read(key):
        if key == "signals/latest/signals.json":
            return {"signals": []}
        with lock:
            seen.append(key)
            if len(seen) == 4:
                initial_four_started.set()
        if key == keys[0]:
            assert initial_four_started.wait(2)
        if key == keys[1]:
            assert release.wait(5), "test did not release second read"
        if key == keys[4]:
            fifth_started.set()
        return {"signals": [signal(key)]}

    with patch.object(s3_reader, "read_json", side_effect=read), patch.object(
        s3_reader, "list_json_keys", return_value=keys
    ), patch.object(s3_reader, "write_local_json"), ThreadPoolExecutor(max_workers=1) as caller:
        future = caller.submit(s3_reader._load_signals_from_s3)
        try:
            assert fifth_started.wait(2), "a completed slot still waits for the whole batch"
            with lock:
                assert set(seen) == set(keys[:5]), "more than four results ran ahead of consumption"
        finally:
            release.set()
        result = future.result(timeout=5)
    assert len(result) == len(keys)
    assert sorted(seen) == sorted(keys)


def test_history_merge_matches_serial_order_even_when_later_reads_finish_first():
    keys = history_keys(2)
    older_finished = Event()
    payloads = {
        "signals/latest/signals.json": {"signals": [signal("shared", status="pending")]},
        keys[0]: {"signals": [signal("shared", status="saved", saved_reason="newer",
            verification_metadata={"verification_status": "weakly_supported",
                "blocked_downstream_actions": ["low_risk_action_candidate"],
                "claim_support_summary": {}}), signal("newer-only")]},
        keys[1]: {"signals": [signal("shared", status="completed", saved_reason="older"),
                              signal("old-only")]},
    }
    ordered = [item for key in ["signals/latest/signals.json", *keys]
               for item in copy.deepcopy(payloads[key])["signals"]]
    expected = s3_reader.assign_stable_ids(s3_reader.sort_by_collected_at_desc(
        s3_reader.dedupe_signals(ordered)))

    def read(key):
        if key == keys[0]:
            assert older_finished.wait(2)
        if key == keys[1]:
            older_finished.set()
        return copy.deepcopy(payloads[key])

    with patch.object(s3_reader, "read_json", side_effect=read), patch.object(
        s3_reader, "list_json_keys", return_value=list(reversed(keys))
    ), patch.object(s3_reader, "write_local_json") as write:
        actual = s3_reader._load_signals_from_s3()
    assert actual == expected
    write.assert_called_once_with(s3_reader.LOCAL_SIGNALS_FILE, {"signals": expected})
    shared = next(item for item in actual if item["title"] == "shared")
    assert shared["verification_metadata"]["blocked_downstream_actions"] == ["low_risk_action_candidate"]
    assert shared["saved_reason"] == "older"


def test_failed_history_read_keeps_successful_siblings_and_remaining_batches():
    keys = history_keys(5)

    def read(key):
        if key in {keys[1], "signals/latest/signals.json"}:
            raise OSError("synthetic unavailable object")
        return {"signals": [signal(key)]}

    with patch.object(s3_reader, "read_json", side_effect=read) as reads, patch.object(
        s3_reader, "list_json_keys", return_value=keys
    ), patch.object(s3_reader, "write_local_json"):
        actual = s3_reader._load_signals_from_s3()
    assert len(actual) == 4
    assert reads.call_count == 6


@pytest.mark.parametrize("snapshot_fails", [False, True])
def test_load_completion_marker_includes_the_snapshot_attempt(snapshot_fails):
    events = []

    def write(*args):
        events.append("snapshot_attempt")
        if snapshot_fails:
            raise OSError("synthetic snapshot failure")

    with patch.object(s3_reader, "read_json", return_value={"signals": [signal("one")]}), patch.object(
        s3_reader, "list_json_keys", return_value=[]
    ), patch.object(s3_reader, "write_local_json", side_effect=write), patch(
        "builtins.print", side_effect=lambda message: events.append(message)
    ):
        result = s3_reader._load_signals_from_s3()
    assert len(result) == 1
    assert events.index("snapshot_attempt") < events.index("===== LOADED 1 SIGNALS FROM S3 =====")
    if snapshot_fails:
        assert any("failed writing local signals snapshot" in event for event in events)


def test_concurrent_cache_misses_share_one_reload():
    entered, release = Event(), Event()
    load_lock = ObservedLoadLock()
    items = [signal("loaded", signal_id="loaded")]

    def load():
        entered.set()
        assert release.wait(5)
        return items

    with patch.object(s3_reader, "SIGNALS_CACHE", {"data": None, "by_id": {}, "last_loaded": 0}), patch.object(
        s3_reader, "SIGNALS_LOAD_LOCK", load_lock
    ), patch.object(
        s3_reader, "_local_output_enabled", return_value=False
    ), patch.object(s3_reader, "_load_signals_from_local", return_value=None), patch.object(
        s3_reader, "_load_signals_from_s3", side_effect=load
    ) as loads, ThreadPoolExecutor(max_workers=2) as callers:
        first = callers.submit(s3_reader.load_signals)
        try:
            assert entered.wait(2)
            second = callers.submit(s3_reader.load_signals)
            assert load_lock.second_attempt.wait(2)
        finally:
            release.set()
        assert first.result(timeout=5) == items
        assert second.result(timeout=5) == items
        assert loads.call_count == 1


def test_invalidation_during_reload_is_not_overwritten_by_its_completion():
    entered, release = Event(), Event()
    load_lock = ObservedLoadLock()
    cache = {"data": None, "by_id": {}, "last_loaded": 0}

    def load():
        entered.set()
        assert release.wait(5)
        return [signal("loaded", signal_id="loaded")]

    with patch.object(s3_reader, "SIGNALS_CACHE", cache), patch.object(
        s3_reader, "SIGNALS_LOAD_LOCK", load_lock
    ), patch.object(s3_reader, "_local_output_enabled", return_value=False), patch.object(
        s3_reader, "_load_signals_from_local", return_value=None
    ), patch.object(s3_reader, "_load_signals_from_s3", side_effect=load), ThreadPoolExecutor(max_workers=2) as callers:
        first = callers.submit(s3_reader.load_signals)
        try:
            assert entered.wait(2)
            invalidation = callers.submit(s3_reader.invalidate_signals_cache)
            assert load_lock.second_attempt.wait(2)
        finally:
            release.set()
        first.result(timeout=5)
        invalidation.result(timeout=5)
    assert cache == {"data": None, "by_id": {}, "last_loaded": 0}


@pytest.mark.parametrize("empty_success", [False, True])
def test_history_unavailable_does_not_fabricate_a_successful_empty_snapshot(empty_success):
    keys = history_keys(5)

    def read(key):
        if empty_success and key == keys[-1]:
            return {"signals": []}
        raise OSError("synthetic unavailable object")

    with patch.object(s3_reader, "read_json", side_effect=read), patch.object(
        s3_reader, "list_json_keys", return_value=keys
    ), patch.object(s3_reader, "write_local_json") as write:
        actual = s3_reader._load_signals_from_s3()
    if empty_success:
        assert actual == []
        write.assert_called_once_with(s3_reader.LOCAL_SIGNALS_FILE, {"signals": []})
    else:
        assert actual is None
        write.assert_not_called()


def test_reload_failure_releases_lock_for_next_request():
    with patch.object(s3_reader, "SIGNALS_CACHE", {"data": None, "by_id": {}, "last_loaded": 0}), patch.object(
        s3_reader, "_local_output_enabled", return_value=False
    ), patch.object(s3_reader, "_load_signals_from_local", return_value=None), patch.object(
        s3_reader, "_load_signals_from_s3", side_effect=[RuntimeError("synthetic failure"), []]
    ):
        with pytest.raises(RuntimeError, match="synthetic failure"):
            s3_reader.load_signals()
        assert s3_reader.load_signals() == []
