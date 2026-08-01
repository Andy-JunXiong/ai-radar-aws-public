import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from scripts.classify_verification_contract_legacy import (  # noqa: E402
    classify_contract_error_row,
)


def _row(source: str, path: str, record_id: str, *codes: str):
    return {
        "source": source,
        "path": path,
        "record_id": record_id,
        "findings": [{"code": code, "severity": "error"} for code in codes],
    }


def test_classifies_manual_session_as_manual_data():
    result = classify_contract_error_row(
        _row(
            "insight_records",
            "backend/data/manual_uploads/sessions/session-1.json",
            "session-1",
            "missing_verification_metadata",
        )
    )
    assert result["classification"] == "manual_data"
    assert result["automatic_backfill_allowed"] is False


def test_classifies_numeric_backend_signal_seed_as_fixture_demo():
    result = classify_contract_error_row(
        _row("insight_records", "backend/data/signals.json", "1", "missing_verification_metadata")
    )
    assert result["classification"] == "fixture_demo"


def test_classifies_pre_contract_takeaway_without_metadata_as_legacy():
    result = classify_contract_error_row(
        _row("project_takeaway", "backend/data/project_improvements/ai_radar.json", "old", "missing_verification_metadata")
    )
    assert result["classification"] == "legacy"


def test_classifies_structured_partial_contract_record_as_authoritative():
    result = classify_contract_error_row(
        _row("project_takeaway", "backend/data/project_improvements/ai_radar.json", "current", "missing_claim_support_summary")
    )
    assert result["classification"] == "authoritative"
