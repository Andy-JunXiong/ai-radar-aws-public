"""Bounded reuse of completed ingestion analyses; never executes an LLM."""

from copy import deepcopy
from datetime import datetime
import hashlib
import json
from typing import Any


SCHEMA_VERSION = 1
MAX_ENTRIES = 256
MAX_STATE_BYTES = 1_000_000
MAX_ENTRY_BYTES = 64_000
REQUIRED_TEXT = {
    "insight": (
        "why_it_matters", "relevance_to_projects", "relevance_to_career",
        "synthesized_insight",
    ),
    "repo": ("repo_summary", "what_it_does", "why_it_matters", "project_fit"),
    "friction": (
        "problem_summary", "why_this_matters", "who_is_affected", "product_opportunity",
    ),
}


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def analysis_fingerprint(*, kind: str, provider: str, model: str, messages: list,
                         context: dict | None = None) -> str:
    """Persist only this digest, not the prompts or personal context."""
    payload = [SCHEMA_VERSION, kind, provider, model, messages, context or {}]
    return hashlib.sha256(_json(payload).encode("utf-8")).hexdigest()


def valid_analysis(kind: str, result: object) -> bool:
    if not isinstance(kind, str) or kind not in REQUIRED_TEXT or not isinstance(result, dict):
        return False
    if not all(isinstance(result.get(k), str) and result[k].strip()
               for k in REQUIRED_TEXT[kind]):
        return False
    if not result.get("provider_used") or not result.get("model_used"):
        return False
    if kind == "insight":
        execution = result.get("execution")
        allowed = {*REQUIRED_TEXT[kind], "signal_title", "signal_summary",
                   "provider_used", "model_used", "execution_policy", "execution"}
        return (set(result) <= allowed
                and isinstance(result.get("signal_title"), str)
                and isinstance(result.get("signal_summary"), str)
                and isinstance(result.get("execution_policy"), dict)
                and isinstance(execution, dict)
                and execution.get("validation_passed") is True
                and execution.get("fallback_used") is False)
    if result.get("confidence") not in {"low", "medium", "high"}:
        return False
    arrays = ("suggested_use_cases", "risks") if kind == "repo" else ("suggested_response",)
    return all(isinstance(result.get(k), list)
               and all(isinstance(v, str) for v in result[k]) for k in arrays)


class AnalysisReuse:
    def __init__(self, state: object = None) -> None:
        self.entries: dict[str, dict] = {}
        self.hits = 0
        if not isinstance(state, dict) or state.get("version") != SCHEMA_VERSION:
            return
        entries = state.get("entries")
        if not isinstance(entries, dict):
            return
        for key, entry in entries.items():
            if self._valid_entry(key, entry):
                self.entries[key] = deepcopy(entry)
        self._trim()

    @staticmethod
    def _valid_entry(key: object, entry: object) -> bool:
        if not isinstance(key, str) or len(key) != 64 or not isinstance(entry, dict):
            return False
        try:
            int(key, 16)
            timestamp = datetime.fromisoformat(entry["generated_at"].replace("Z", "+00:00"))
            if timestamp.tzinfo is None:
                return False
            if not valid_analysis(entry.get("kind"), entry.get("result")):
                return False
            return (len(_json(entry).encode("utf-8")) <= MAX_ENTRY_BYTES
                    and entry.get("result_digest") == hashlib.sha256(
                        _json(entry["result"]).encode("utf-8")).hexdigest())
        except (KeyError, ValueError, TypeError, AttributeError):
            return False

    def _trim(self) -> None:
        while self.entries and (len(self.entries) > MAX_ENTRIES or
                                len(_json(self.entries).encode("utf-8")) > MAX_STATE_BYTES):
            del self.entries[next(iter(self.entries))]

    def lookup(self, key: str, kind: str) -> dict | None:
        entry = self.entries.get(key)
        if not entry or entry["kind"] != kind:
            return None
        self.entries[key] = self.entries.pop(key)  # Retain recently used objects.
        self.hits += 1
        return deepcopy(entry)

    def remember(self, key: str, kind: str, result: dict, generated_at: str) -> None:
        entry = {
            "kind": kind, "result": deepcopy(result), "generated_at": generated_at,
            "result_digest": hashlib.sha256(_json(result).encode("utf-8")).hexdigest(),
        }
        if self._valid_entry(key, entry):
            self.entries.pop(key, None)
            self.entries[key] = entry
            self._trim()

    def snapshot(self) -> dict:
        return {"version": SCHEMA_VERSION, "entries": deepcopy(self.entries)}
