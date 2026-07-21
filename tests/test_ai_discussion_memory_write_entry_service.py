import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services import ai_discussion_memory_store_service as store  # noqa: E402
from app.services import ai_discussion_memory_write_entry_service as entry  # noqa: E402
from app.services import governed_claim_service as governed  # noqa: E402


def _message_ref():
    return {
        "message_id": "msg_1",
        "role": "assistant",
        "sequence": 1,
        "content_excerpt": "We judged the write entry should stay service-only.",
        "content_fingerprint": "fp_msg_1",
    }


def _subject(subject_type="ai_radar_design"):
    return {
        "subject_type": subject_type,
        "label": "ADR-0013 write entry",
        "source_url": "",
        "source_id": "",
        "project_id": "ai_radar",
        "notes": "",
    }


def _request(*, caller_type="explicit_human_or_agent_selection", source_type="ai_discussion_session", fingerprint="fp_entry_1", subject_type="ai_radar_design"):
    return {
        "caller": {
            "caller_type": caller_type,
            "actor": {"type": "human_or_agent", "id": "codex"},
        },
        "capture": {
            "source": {
                "source_type": source_type,
                "source_label": "ADR-0013 session",
                "source_url": "",
                "provider": "codex",
                "captured_from": "",
            },
            "message_refs": [_message_ref()],
            "discussion_excerpt": "Selected write-entry discussion excerpt.",
            "discussion_fingerprint": fingerprint,
            "selection_reason": "ADR-0013 write-entry boundary review",
        },
        "governed_claims": [
            {
                "claim_text": "In this discussion, we judged write-entry should call the store service.",
                "claim_posture": "discussion_judgment",
                "asserted_subject": _subject(subject_type),
                "boundary_review": (
                    {"status": "pending_human_check", "reviewed_by": "", "reviewed_at": "", "note": ""}
                    if subject_type == "external_source"
                    else None
                ),
                "verification_ref": None,
                "claim_snapshot": None,
                "salience": None,
            }
        ],
    }


def _patch_data_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "DATA_DIR", tmp_path)


def test_explicit_selection_request_commits_capture_claim_and_audit(monkeypatch, tmp_path):
    _patch_data_dir(monkeypatch, tmp_path)

    response = entry.create_ai_discussion_memory_from_selection(_request())

    assert response["status"] == "committed"
    assert response["write_batch_id"].startswith("aimb_")
    assert response["capture_id"].startswith("aid_")
    assert len(response["governed_claim_ids"]) == 1
    assert len(response["audit_event_ids"]) == 2
    assert response["capture_reused"] is False
    assert response["claims_created"] is True
    assert (tmp_path / "write_batches").exists()


def test_request_rejects_automatic_transcript_and_importer_callers(monkeypatch, tmp_path):
    _patch_data_dir(monkeypatch, tmp_path)

    with pytest.raises(ValueError, match="caller_type"):
        entry.create_ai_discussion_memory_from_selection(_request(caller_type="automatic_transcript_capture"))

    with pytest.raises(ValueError, match="caller_type"):
        entry.create_ai_discussion_memory_from_selection(_request(caller_type="signal_import"))


def test_request_rejects_empty_discussion_fingerprint(monkeypatch, tmp_path):
    _patch_data_dir(monkeypatch, tmp_path)

    with pytest.raises(ValueError, match="discussion_fingerprint"):
        entry.create_ai_discussion_memory_from_selection(_request(fingerprint=""))


def test_request_rejects_provider_specific_source_type(monkeypatch, tmp_path):
    _patch_data_dir(monkeypatch, tmp_path)

    with pytest.raises(ValueError, match="source_type"):
        entry.create_ai_discussion_memory_from_selection(_request(source_type="claude_session"))


def test_request_rejects_reflection_workspace_manual_upload_and_signal_sources(monkeypatch, tmp_path):
    _patch_data_dir(monkeypatch, tmp_path)

    for source_type in ("reflection_import", "workspace_chat_import", "manual_upload_import", "signal_import"):
        with pytest.raises(ValueError, match="source_type"):
            entry.create_ai_discussion_memory_from_selection(_request(source_type=source_type, fingerprint=f"fp_{source_type}"))


def test_request_rejects_caller_supplied_discussion_ref(monkeypatch, tmp_path):
    _patch_data_dir(monkeypatch, tmp_path)
    request = _request()
    request["governed_claims"][0]["discussion_ref"] = {"record_family": "ai_discussion_capture", "record_id": "aid_other"}

    with pytest.raises(ValueError, match="discussion_ref"):
        entry.create_ai_discussion_memory_from_selection(request)


def test_request_rejects_non_discussion_support_boundary(monkeypatch, tmp_path):
    _patch_data_dir(monkeypatch, tmp_path)
    request = _request()
    request["governed_claims"][0]["support_boundary"] = "discussion_context_with_verification_ref"

    with pytest.raises(ValueError, match="support_boundary"):
        entry.create_ai_discussion_memory_from_selection(request)


def test_external_source_requires_boundary_review_and_admitted_posture(monkeypatch, tmp_path):
    _patch_data_dir(monkeypatch, tmp_path)
    valid = _request(subject_type="external_source")
    response = entry.create_ai_discussion_memory_from_selection(valid)
    assert response["claims_created"] is True

    missing_review = _request(subject_type="external_source", fingerprint="fp_missing_review")
    missing_review["governed_claims"][0]["boundary_review"] = {"status": "not_required"}
    with pytest.raises(ValueError, match="not_required"):
        entry.create_ai_discussion_memory_from_selection(missing_review)

    bad_posture = _request(subject_type="external_source", fingerprint="fp_bad_posture")
    bad_posture["governed_claims"][0]["claim_posture"] = "decision_rationale"
    with pytest.raises(ValueError, match="posture"):
        entry.create_ai_discussion_memory_from_selection(bad_posture)


def test_response_reports_capture_reuse_separately_from_claim_creation(monkeypatch, tmp_path):
    _patch_data_dir(monkeypatch, tmp_path)
    first = entry.create_ai_discussion_memory_from_selection(_request(fingerprint="fp_reuse"))
    second = entry.create_ai_discussion_memory_from_selection(_request(fingerprint="fp_reuse"))

    assert first["capture_reused"] is False
    assert first["claims_created"] is True
    assert second["capture_reused"] is True
    assert second["claims_created"] is False
    assert second["capture_id"] == first["capture_id"]


def test_duplicate_fingerprint_request_still_validates_source_and_claim_payload(monkeypatch, tmp_path):
    _patch_data_dir(monkeypatch, tmp_path)
    entry.create_ai_discussion_memory_from_selection(_request(fingerprint="fp_reuse_validate"))

    bad_source = _request(fingerprint="fp_reuse_validate", source_type="reflection_import")
    with pytest.raises(ValueError, match="source_type"):
        entry.create_ai_discussion_memory_from_selection(bad_source)

    bad_claim = _request(fingerprint="fp_reuse_validate")
    bad_claim["governed_claims"][0]["discussion_ref"] = {"record_family": "ai_discussion_capture", "record_id": "aid_other"}
    with pytest.raises(ValueError, match="discussion_ref"):
        entry.create_ai_discussion_memory_from_selection(bad_claim)


def test_verification_ref_may_carry_blocked_downstream_actions_snapshot(monkeypatch, tmp_path):
    _patch_data_dir(monkeypatch, tmp_path)
    request = _request(fingerprint="fp_with_verification_ref")
    request["governed_claims"][0]["verification_ref"] = governed.build_verification_ref(
        verification={
            "verification_status": "partially_verified",
            "confidence": "medium",
            "confidence_score": 0.58,
            "summary": "Contract snapshot preserves blocked actions.",
            "allowed_downstream_actions": ["watch"],
            "blocked_downstream_actions": ["low_risk_action_candidate"],
        },
        verified_insight_id="vi_entry_1",
        signal_id="sig_entry_1",
        content_fingerprint="fp_contract_1",
        claim_id="claim_entry_1",
        as_of="2026-06-25T00:00:00+00:00",
    )
    request["governed_claims"][0]["claim_snapshot"] = {
        "claim_text": request["governed_claims"][0]["claim_text"],
        "captured_as_of": "2026-06-25T00:00:00+00:00",
    }

    response = entry.create_ai_discussion_memory_from_selection(request)

    assert response["claims_created"] is True
    assert "blocked_downstream_actions" not in response


def test_response_does_not_include_verification_or_action_eligibility(monkeypatch, tmp_path):
    _patch_data_dir(monkeypatch, tmp_path)

    response = entry.create_ai_discussion_memory_from_selection(_request())

    assert "verification_status" not in response
    assert "allowed_downstream_actions" not in response
    assert "blocked_downstream_actions" not in response
    assert "project_takeaway" not in response


def test_write_entry_calls_store_service_and_does_not_write_directly(monkeypatch, tmp_path):
    _patch_data_dir(monkeypatch, tmp_path)
    called = {}

    def fake_create_capture_with_governed_claims(**kwargs):
        called["kwargs"] = kwargs
        capture = kwargs["capture"]
        governed_claims = kwargs["governed_claims"]
        return {
            "id": "aimb_fake",
            "status": "committed",
            "captures": [capture],
            "governed_claims": governed_claims,
            "audit_events": [kwargs["capture_audit_event"], *kwargs["governed_claim_audit_events"]],
        }

    monkeypatch.setattr(entry.store_service, "list_committed_write_batches", lambda: [])
    monkeypatch.setattr(entry.store_service, "create_capture_with_governed_claims", fake_create_capture_with_governed_claims)
    response = entry.create_ai_discussion_memory_from_selection(_request())

    assert called["kwargs"]["capture"]["record_type"] == "ai_discussion_capture"
    assert response["write_batch_id"] == "aimb_fake"
    assert not (tmp_path / "write_batches").exists()
