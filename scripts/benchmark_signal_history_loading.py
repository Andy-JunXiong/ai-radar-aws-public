"""Offline serial/batched/rolling comparison; never reads AWS or runtime data.

Run with the repository Python. All input is synthetic, storage is mocked,
and network/cloud calls are denied. Results are not a production latency SLA.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack, redirect_stdout
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
import hashlib
import io
import json
from pathlib import Path
import socket
import sys
import time
import tracemalloc
from unittest.mock import Mock, patch


def deny_network(*args, **kwargs):
    raise RuntimeError("Offline benchmark: network/cloud operation blocked")


def digest(value):
    result = hashlib.sha256()
    for chunk in json.JSONEncoder(sort_keys=True).iterencode(value):
        result.update(chunk.encode("utf-8"))
    return result.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=220)
    parser.add_argument("--delay-ms", type=float, default=10)
    parser.add_argument("--uneven", action="store_true",
                        help="Sixfold delay at positions 3 and 4 of every eight history reads")
    args = parser.parse_args()
    if not 4 <= args.days <= 366 or not 0 <= args.delay_ms <= 100:
        parser.error("days must be 4..366 and delay-ms must be 0..100")

    # Patch before importing application code: no dotenv/credential lookup or
    # unmocked network is needed even to initialize its module-level client.
    import boto3
    import dotenv
    from botocore.client import BaseClient

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
    with ExitStack() as stack:
        stack.enter_context(patch.object(socket.socket, "connect", deny_network))
        stack.enter_context(patch.object(socket.socket, "connect_ex", deny_network))
        stack.enter_context(patch.object(BaseClient, "_make_api_call", deny_network))
        stack.enter_context(patch.object(dotenv, "load_dotenv", return_value=False))
        stack.enter_context(patch.object(boto3, "client", return_value=Mock()))
        from app.services import s3_reader

        keys = [f"signals/{date(2026, 10, 19) - timedelta(days=i)}/signals.json"
                for i in range(args.days)]
        latest = "signals/latest/signals.json"
        positions = {key: i for i, key in enumerate(keys)}
        positions[latest] = -1
        calls = 0
        delay = args.delay_ms / 1000

        def read(key):
            nonlocal calls
            calls += 1
            if delay:
                factor = 6 if args.uneven and positions[key] >= 0 and positions[key] % 8 in {3, 4} else 1
                time.sleep(delay * factor)
            offset = positions[key] * 25
            return {"signals": [{
                "title": f"Synthetic record {(offset + j) % 1910}",
                "url": f"https://example.test/signal/{(offset + j) % 1910}",
                "source": "synthetic",
                "collected_at": "2026-10-19T00:00:00+00:00",
                "content": f"Record {offset + j}: " + "x" * 2048,
                "verification_metadata": {
                    "verification_status": "weakly_supported",
                    "blocked_downstream_actions": ["low_risk_action_candidate"],
                    "claim_support_summary": {},
                },
            } for j in range(25)]}

        def serial_load():
            # The pre-repair successful-read order, using the same transforms.
            items = s3_reader.normalize_items(s3_reader.read_json(latest))
            for key in sorted(s3_reader.list_json_keys("signals/"), reverse=True):
                items.extend(s3_reader.normalize_items(s3_reader.read_json(key)))
            items = s3_reader.assign_stable_ids(s3_reader.sort_by_collected_at_desc(
                s3_reader.dedupe_signals(items)))
            s3_reader.write_local_json(s3_reader.LOCAL_SIGNALS_FILE, {"signals": items})
            return items

        def batched_load():
            # Deployed four-at-a-time scheduling, before the rolling window.
            items = s3_reader.normalize_items(s3_reader.read_json(latest))
            ordered_keys = sorted(s3_reader.list_json_keys("signals/"), reverse=True)
            with ThreadPoolExecutor(max_workers=4) as pool:
                for offset in range(0, len(ordered_keys), 4):
                    pending = [pool.submit(s3_reader.read_json, key)
                               for key in ordered_keys[offset:offset + 4]]
                    for future in pending:
                        items.extend(s3_reader.normalize_items(future.result()))
            items = s3_reader.assign_stable_ids(s3_reader.sort_by_collected_at_desc(
                s3_reader.dedupe_signals(items)))
            s3_reader.write_local_json(s3_reader.LOCAL_SIGNALS_FILE, {"signals": items})
            return items

        stack.enter_context(patch.object(s3_reader, "read_json", side_effect=read))
        stack.enter_context(patch.object(s3_reader, "list_json_keys", return_value=keys))
        # A plain no-op avoids mock call history retaining completed payloads.
        stack.enter_context(patch.object(s3_reader, "write_local_json", lambda *a: None))
        rows = []
        for label, loader in [("serial", serial_load), ("batched", batched_load),
                              ("rolling", s3_reader._load_signals_from_s3)]:
            calls = 0
            with redirect_stdout(io.StringIO()):
                started = time.perf_counter()
                result = loader()
                elapsed = time.perf_counter() - started
            rows.append({"mode": label, "seconds": round(elapsed, 3),
                         "storage_reads": calls, "records": len(result), "sha256": digest(result)})
            del result
            # Separate allocation measurement from timing instrumentation.
            delay = 0
            tracemalloc.start()
            try:
                with redirect_stdout(io.StringIO()):
                    result = loader()
                _, peak = tracemalloc.get_traced_memory()
            finally:
                tracemalloc.stop()
            rows[-1]["peak_mib"] = round(peak / (1024 * 1024), 2)
            del result
            delay = args.delay_ms / 1000
        assert len({row["sha256"] for row in rows}) == 1, "result semantics changed"
        assert all(row["storage_reads"] == args.days + 1 for row in rows)
        print(json.dumps({"synthetic": True, "history_days": args.days,
                          "base_read_delay_ms": args.delay_ms, "uneven": args.uneven,
                          "runs": rows,
                          "batched_to_rolling_speedup": round(rows[1]["seconds"] / rows[2]["seconds"], 2)}, indent=2))


if __name__ == "__main__":
    main()
