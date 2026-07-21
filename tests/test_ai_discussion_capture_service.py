import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services import ai_discussion_capture_service as service  # noqa: E402


def _message_ref(content="We judged ADR-0013 should use a narrow capture boundary."):
    return {
        "message_id": "msg_1",
        "role": "assistant",
        "sequence": 1,
        "content_excerpt": content,
        "content_fingerprint": "fp_msg_1",
    }


def test_build_capture_adds_required_creation_audit_ref():
    record, audit_event = service.build_ai_discussion_capture_record(
        message_refs=[_message_ref()],
        discussion_excerpt="Selected discussion excerpt about ADR-0013 capture boundaries.",
        discussion_fingerprint="fp_discussion_1",
        captured_at="2026-06-24T00:00:00+00:00",
        record_id="aid_test",
    )

    assert record["record_type"] == "ai_discussion_capture"
    assert record["capture_mode"] == "selected_excerpt"
    assert record["source"]["source_type"] == "ai_discussion_session"
    assert record["boundary"] == {
        "evidence_boundary": "discussion_context_not_external_evidence",
        "external_fact_evidence": False,
        "full_transcript": False,
        "automatic_import": False,
    }
    assert record["audit_refs"] == [
        {
            "record_family": "ai_discussion_capture_audit_event",
            "record_id": audit_event["id"],
            "action": "created",
            "recorded_at": "2026-06-24T00:00:00+00:00",
        }
    ]
    assert audit_event["action"] == "created"


def test_capture_rejects_non_v1_capture_modes_and_full_transcript_boundary():
    record, _ = service.build_ai_discussion_capture_record(
        message_refs=[_message_ref()],
        discussion_fingerprint="fp_mode",
        record_id="aid_mode",
    )

    record["capture_mode"] = "full_session"
    with pytest.raises(ValueError, match="capture_mode"):
        service.validate_ai_discussion_capture_record(record)

    record["capture_mode"] = "selected_excerpt"
    record["boundary"]["full_transcript"] = True
    with pytest.raises(ValueError, match="boundary.full_transcript"):
        service.validate_ai_discussion_capture_record(record)


def test_capture_rejects_provider_specific_source_types():
    record, _ = service.build_ai_discussion_capture_record(
        message_refs=[_message_ref()],
        discussion_fingerprint="fp_source",
        record_id="aid_source",
    )

    record["source"]["source_type"] = "claude_session"
    with pytest.raises(ValueError, match="source.source_type"):
        service.validate_ai_discussion_capture_record(record)


def test_capture_requires_selected_excerpt_or_message_ref():
    record, _ = service.build_ai_discussion_capture_record(
        message_refs=[_message_ref()],
        discussion_fingerprint="fp_empty",
        record_id="aid_empty",
    )
    record["message_refs"] = []
    record["discussion_excerpt"] = ""

    with pytest.raises(ValueError, match="selected excerpt or message ref"):
        service.validate_ai_discussion_capture_record(record)


def test_capture_enforces_excerpt_length_caps():
    with pytest.raises(ValueError, match="message_refs\\[0\\].content_excerpt"):
        service.build_ai_discussion_capture_record(
            message_refs=[_message_ref("x" * (service.MAX_MESSAGE_EXCERPT_CHARS + 1))],
            discussion_fingerprint="fp_long_message",
            record_id="aid_long_message",
        )

    with pytest.raises(ValueError, match="discussion_excerpt"):
        service.build_ai_discussion_capture_record(
            discussion_excerpt="x" * (service.MAX_DISCUSSION_EXCERPT_CHARS + 1),
            discussion_fingerprint="fp_long_discussion",
            record_id="aid_long_discussion",
        )


def test_capture_rejects_obvious_secret_like_text():
    with pytest.raises(ValueError, match="secret-like"):
        service.build_ai_discussion_capture_record(
            message_refs=[_message_ref("api_key=[redacted]")],
            discussion_fingerprint="fp_secret_message",
            record_id="aid_secret_message",
        )

    with pytest.raises(ValueError, match="secret-like"):
        service.build_ai_discussion_capture_record(
            discussion_excerpt="Authorization: Bearer secret-token-value",
            discussion_fingerprint="fp_secret_discussion",
            record_id="aid_secret_discussion",
        )


def test_capture_creation_audit_ref_is_required_for_persistence_validity():
    record, _ = service.build_ai_discussion_capture_record(
        message_refs=[_message_ref()],
        discussion_fingerprint="fp_no_audit",
        record_id="aid_no_audit",
    )
    record["audit_refs"] = []

    with pytest.raises(ValueError, match="created audit ref"):
        service.validate_ai_discussion_capture_record(record)


def test_capture_discussion_fingerprint_is_required():
    with pytest.raises(ValueError, match="discussion_fingerprint"):
        service.build_ai_discussion_capture_record(
            message_refs=[_message_ref()],
            discussion_fingerprint="",
            record_id="aid_no_fingerprint",
        )


def test_capture_audit_actions_are_v1_only_and_do_not_prove_external_claims():
    event = service.build_ai_discussion_capture_audit_event(
        capture_id="aid_test",
        action="metadata_updated",
        recorded_at="2026-06-24T00:00:00+00:00",
    )

    assert event["record_type"] == "ai_discussion_capture_audit_event"
    assert "verification_status" not in event
    assert "allowed_downstream_actions" not in event

    with pytest.raises(ValueError, match="action"):
        service.build_ai_discussion_capture_audit_event(capture_id="aid_test", action="linked_governed_claim")
