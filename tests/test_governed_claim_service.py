import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services import governed_claim_service as service  # noqa: E402


def _discussion_ref():
    return {
        "record_family": "ai_discussion_capture",
        "record_id": "aid_discussion_1",
        "message_ids": ["msg-1"],
        "captured_at": "2026-06-24T00:00:00+00:00",
    }


def _subject(subject_type="concept"):
    return {
        "subject_type": subject_type,
        "label": "Memory ontology",
        "source_url": "https://example.test/source",
        "source_id": "source-1",
        "project_id": "ai_radar",
        "notes": "",
    }


def _verification(status="unsupported"):
    return {
        "verification_status": status,
        "evidence_level": "thin",
        "allowed_downstream_actions": ["reflection_draft", "watch_only"],
        "blocked_downstream_actions": ["project_takeaway_candidate", "low_risk_action_candidate"],
        "claim_support_summary": {"unsupported": 1},
        "confidence_label": "low",
        "confidence_score": 0.35,
    }


def test_build_governed_claim_adds_required_creation_audit_ref():
    record, audit_event = service.build_governed_claim_record(
        claim_text="In this discussion, we judged the memory boundary should stay narrow.",
        asserted_subject=_subject("ai_radar_design"),
        discussion_ref=_discussion_ref(),
        created_at="2026-06-24T00:00:00+00:00",
        record_id="gc_test",
    )

    assert record["record_type"] == "ai_discussion_governed_claim"
    assert record["support_boundary"] == "discussion_context"
    assert record["boundary_review"]["status"] == "not_required"
    assert record["audit_refs"] == [
        {
            "record_family": "governed_claim_audit_event",
            "record_id": audit_event["id"],
            "action": "created",
            "recorded_at": "2026-06-24T00:00:00+00:00",
        }
    ]
    assert audit_event["record_type"] == "governed_claim_audit_event"
    assert audit_event["action"] == "created"


def test_external_source_requires_boundary_review_gate():
    record, _ = service.build_governed_claim_record(
        claim_text="In this discussion, we judged the source may support the design, pending verification.",
        asserted_subject=_subject("external_source"),
        discussion_ref=_discussion_ref(),
        created_at="2026-06-24T00:00:00+00:00",
        record_id="gc_external",
    )

    assert record["boundary_review"]["status"] == "pending_human_check"

    record["boundary_review"]["status"] = "not_required"
    with pytest.raises(ValueError, match="external_source.*not_required"):
        service.validate_governed_claim_record(record)


def test_support_boundary_is_single_value_even_with_verification_ref():
    verification_ref = service.build_verification_ref(
        verification=_verification(status="verified"),
        verified_insight_id="vi_123",
        signal_id="sig-1",
        claim_id="claim_1",
        as_of="2026-06-24T00:00:00+00:00",
    )
    record, _ = service.build_governed_claim_record(
        claim_text="In this discussion, we judged the source may support the design.",
        asserted_subject=_subject("external_source"),
        discussion_ref=_discussion_ref(),
        boundary_review={"status": "boundary_checked", "reviewed_by": "andy", "reviewed_at": "2026-06-24T00:01:00+00:00", "note": ""},
        verification_ref=verification_ref,
        claim_snapshot={
            "claim_text_snapshot": "The source may support the design.",
            "claim_source_field": "synthesized_insight",
            "claim_result_snapshot": {"support_level": "directly_supported"},
            "content_fingerprint": "abc",
        },
        created_at="2026-06-24T00:00:00+00:00",
        record_id="gc_with_ref",
    )

    assert record["support_boundary"] == "discussion_context"
    assert record["verification_ref"]["verification_snapshot"]["verification_status"] == "verified"

    record["support_boundary"] = "discussion_context_with_verification_ref"
    with pytest.raises(ValueError, match="support_boundary"):
        service.validate_governed_claim_record(record)


def test_verification_ref_does_not_imply_positive_verification_or_action():
    verification_ref = service.build_verification_ref(
        verification=_verification(status="contradicted"),
        verified_insight_id="vi_bad",
        as_of="2026-06-24T00:00:00+00:00",
    )
    record, _ = service.build_governed_claim_record(
        claim_text="In this discussion, we judged the source claim is contradicted.",
        asserted_subject=_subject("external_source"),
        discussion_ref=_discussion_ref(),
        boundary_review={"status": "boundary_checked", "reviewed_by": "andy", "reviewed_at": "2026-06-24T00:01:00+00:00", "note": ""},
        verification_ref=verification_ref,
        claim_snapshot={"claim_text_snapshot": "Source claim", "claim_source_field": "synthesized_insight"},
        record_id="gc_contradicted",
    )

    snapshot = record["verification_ref"]["verification_snapshot"]
    assert snapshot["verification_status"] == "contradicted"
    assert "low_risk_action_candidate" in snapshot["blocked_downstream_actions"]


def test_verification_ref_rejects_embedded_evidence_pack_and_requires_claim_snapshot():
    verification_ref = service.build_verification_ref(
        verification=_verification(),
        as_of="2026-06-24T00:00:00+00:00",
    )
    verification_ref["evidence_pack"] = {"evidence_items": []}

    with pytest.raises(ValueError, match="evidence_pack"):
        service.build_governed_claim_record(
            claim_text="In this discussion, we judged this needs verification.",
            asserted_subject=_subject("external_source"),
            discussion_ref=_discussion_ref(),
            boundary_review={"status": "pending_human_check", "reviewed_by": "", "reviewed_at": "", "note": ""},
            verification_ref=verification_ref,
            claim_snapshot={"claim_text_snapshot": "Claim"},
        )

    clean_ref = service.build_verification_ref(
        verification=_verification(),
        as_of="2026-06-24T00:00:00+00:00",
    )
    with pytest.raises(ValueError, match="claim_snapshot"):
        service.build_governed_claim_record(
            claim_text="In this discussion, we judged this needs verification.",
            asserted_subject=_subject("external_source"),
            discussion_ref=_discussion_ref(),
            boundary_review={"status": "pending_human_check", "reviewed_by": "", "reviewed_at": "", "note": ""},
            verification_ref=clean_ref,
        )


def test_audit_snapshots_reject_evidence_pack_and_full_verification_snapshot():
    with pytest.raises(ValueError, match="evidence_pack"):
        service.build_governed_claim_audit_event(
            governed_claim_id="gc_1",
            action="attribute_updated",
            after_snapshot={"evidence_pack": {"evidence_items": []}},
        )

    with pytest.raises(ValueError, match="verification_snapshot"):
        service.build_governed_claim_audit_event(
            governed_claim_id="gc_1",
            action="attribute_updated",
            after_snapshot={"verification_snapshot": {"verification_status": "verified"}},
        )


def test_created_audit_ref_is_required_for_persistence_validity():
    record, _ = service.build_governed_claim_record(
        claim_text="In this discussion, we judged the boundary should be narrow.",
        asserted_subject=_subject("concept"),
        discussion_ref=_discussion_ref(),
        record_id="gc_no_audit",
    )
    record["audit_refs"] = []

    with pytest.raises(ValueError, match="created audit ref"):
        service.validate_governed_claim_record(record)


def test_discussion_ref_must_point_to_ai_discussion_capture():
    record, _ = service.build_governed_claim_record(
        claim_text="In this discussion, we judged the capture boundary should stay narrow.",
        asserted_subject=_subject("concept"),
        discussion_ref=_discussion_ref(),
        record_id="gc_discussion_ref",
    )

    record["discussion_ref"]["record_family"] = "ai_discussion"
    with pytest.raises(ValueError, match="discussion_ref.record_family"):
        service.validate_governed_claim_record(record)

    record["discussion_ref"] = {"record_family": "ai_discussion_capture", "record_id": "", "captured_at": ""}
    with pytest.raises(ValueError, match="discussion_ref.record_id"):
        service.validate_governed_claim_record(record)


def test_source_spine_changes_do_not_auto_update_verification_ref_as_of():
    verification = _verification(status="partially_verified")
    verification_ref = service.build_verification_ref(
        verification=verification,
        as_of="2026-06-24T00:00:00+00:00",
    )
    record, _ = service.build_governed_claim_record(
        claim_text="In this discussion, we judged this source might support the design.",
        asserted_subject=_subject("external_source"),
        discussion_ref=_discussion_ref(),
        boundary_review={"status": "boundary_checked", "reviewed_by": "andy", "reviewed_at": "2026-06-24T00:01:00+00:00", "note": ""},
        verification_ref=verification_ref,
        claim_snapshot={"claim_text_snapshot": "Claim"},
        record_id="gc_as_of",
    )

    verification["verification_status"] = "verified"
    verification["blocked_downstream_actions"] = []

    assert record["verification_ref"]["as_of"] == "2026-06-24T00:00:00+00:00"
    assert record["verification_ref"]["verification_snapshot"]["verification_status"] == "partially_verified"
    assert record["verification_ref"]["verification_snapshot"]["blocked_downstream_actions"] == [
        "project_takeaway_candidate",
        "low_risk_action_candidate",
    ]


def test_salience_cannot_create_action_eligibility_metadata():
    record, _ = service.build_governed_claim_record(
        claim_text="In this discussion, we judged this is important to review later.",
        asserted_subject=_subject("concept"),
        discussion_ref=_discussion_ref(),
        salience={"label": "high", "score": 0.9, "reason": ["important"]},
        record_id="gc_salience",
    )

    assert record["salience"]["label"] == "high"
    assert "allowed_downstream_actions" not in record["salience"]
    assert "blocked_downstream_actions" not in record["salience"]

    record["salience"]["label"] = "review"
    with pytest.raises(ValueError, match="salience.label"):
        service.validate_governed_claim_record(record)
