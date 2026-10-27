"""Malformed optional cache results must not interrupt ingestion analysis."""

import importlib.util
from pathlib import Path

import pytest

# This pure helper needs no runtime package. Load it directly so these tests
# cannot mix ingestion's `app` with the backend's separate `app` package.
spec = importlib.util.spec_from_file_location(
    "analysis_reuse_under_test",
    Path(__file__).resolve().parents[1] / "app/intelligence/analysis_reuse.py",
)
reuse_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reuse_module)
AnalysisReuse = reuse_module.AnalysisReuse
REQUIRED_TEXT = reuse_module.REQUIRED_TEXT
valid_analysis = reuse_module.valid_analysis


KEY = "a" * 64
GENERATED_AT = "2026-10-27T00:00:00Z"


def analysis(kind):
    result = {field: "A useful interpretation." for field in REQUIRED_TEXT[kind]}
    result.update(provider_used="test-provider", model_used="test-model")
    if kind == "insight":
        result.update(
            signal_title="Observation", signal_summary="Observed behavior.",
            execution_policy={},
            execution={"validation_passed": True, "fallback_used": False},
        )
    else:
        result["confidence"] = "medium"
        if kind == "repo":
            result.update(suggested_use_cases=["Inspect"], risks=["Partial evidence"])
        else:
            result["suggested_response"] = ["Inspect"]
    return result


@pytest.mark.parametrize("kind", ["repo", "friction"])
@pytest.mark.parametrize("confidence", [[], {}, ["medium"]])
def test_non_string_confidence_is_rejected(kind, confidence):
    result = analysis(kind)
    result["confidence"] = confidence
    assert valid_analysis(kind, result) is False


@pytest.mark.parametrize("kind", ["insight", "repo", "friction"])
def test_unencodable_result_does_not_interrupt_or_replace_valid_cache(kind):
    reuse = AnalysisReuse()
    original = analysis(kind)
    reuse.remember(KEY, kind, original, GENERATED_AT)
    before = reuse.snapshot()

    malformed = analysis(kind)
    malformed[REQUIRED_TEXT[kind][0]] = "Invalid Unicode: \ud800"
    reuse.remember(KEY, kind, malformed, GENERATED_AT)

    assert reuse.snapshot() == before
    assert reuse.lookup(KEY, kind)["result"] == original


@pytest.mark.parametrize("kind", ["insight", "repo", "friction"])
def test_valid_unicode_result_survives_persistence(kind):
    result = analysis(kind)
    result[REQUIRED_TEXT[kind][0]] = "Valid analysis — café — \U0001f600"
    reuse = AnalysisReuse()
    reuse.remember(KEY, kind, result, GENERATED_AT)
    restored = AnalysisReuse(reuse.snapshot())
    assert restored.lookup(KEY, kind)["result"] == result


def test_unserializable_optional_execution_metadata_is_not_cached():
    result = analysis("insight")
    result["execution"]["unexpected"] = object()
    reuse = AnalysisReuse()
    reuse.remember(KEY, "insight", result, GENERATED_AT)
    assert reuse.snapshot()["entries"] == {}
