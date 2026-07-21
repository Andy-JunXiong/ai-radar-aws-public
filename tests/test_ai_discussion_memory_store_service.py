import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services import ai_discussion_capture_service as capture_service  # noqa: E402
from app.services import ai_discussion_memory_store_service as store  # noqa: E402
from app.services import governed_claim_service  # noqa: E402


def _message_ref(content="We judged ADR-0013 should persist via committed batches."):
    return {
        "message_id": "msg_1",
        "role": "assistant",
        "sequence": 1,
        "content_excerpt": content,
        "content_fingerprint": "fp_msg_1",
    }


def _subject():
    return {
        "subject_type": "ai_radar_design",
        "label": "ADR-0013 write path",
        "source_url": "",
        "source_id": "",
        "project_id": "ai_radar",
        "notes": "",
    }


def _build_capture_and_claim(*, fingerprint="fp_discussion_1", capture_id="aid_1", claim_id="gc_1"):
    capture, capture_audit = capture_service.build_ai_discussion_capture_record(
        message_refs=[_message_ref()],
        discussion_excerpt="Selected ADR-0013 write-path discussion.",
        discussion_fingerprint=fingerprint,
        captured_at="2026-06-25T00:00:00+00:00",
        record_id=capture_id,
    )
    claim, claim_audit = governed_claim_service.build_governed_claim_record(
        claim_text="In this discussion, we judged write batches should be authoritative.",
        asserted_subject=_subject(),
        discussion_ref={
            "record_family": "ai_discussion_capture",
            "record_id": capture["id"],
            "message_ids": ["msg_1"],
            "captured_at": capture["captured_at"],
        },
        created_at="2026-06-25T00:00:00+00:00",
        record_id=claim_id,
    )
    return capture, capture_audit, claim, claim_audit


def _patch_data_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "DATA_DIR", tmp_path)


def test_commit_creates_authoritative_batch_and_materialized_views(monkeypatch, tmp_path):
    _patch_data_dir(monkeypatch, tmp_path)
    capture, capture_audit, claim, claim_audit = _build_capture_and_claim()

    batch = store.create_capture_with_governed_claims(
        capture=capture,
        capture_audit_event=capture_audit,
        governed_claims=[claim],
        governed_claim_audit_events=[claim_audit],
        created_at="2026-06-25T00:00:00+00:00",
        batch_id="aimb_1",
    )

    assert batch["record_type"] == "ai_discussion_memory_write_batch"
    assert batch["status"] == "committed"
    assert (tmp_path / "write_batches" / "aimb_1.json").exists()
    assert (tmp_path / "captures" / "aid_1.json").exists()
    assert (tmp_path / "governed_claims" / "gc_1.json").exists()
    assert (tmp_path / "audit_events" / capture_audit["id"]).with_suffix(".json").exists()
    index = store.load_memory_index()
    assert index["captures"][0]["discussion_fingerprint"] == "fp_discussion_1"
    assert index["governed_claims"][0]["boundary_review_status"] == "not_required"


def test_write_batch_rejects_persistent_intermediate_status(monkeypatch, tmp_path):
    _patch_data_dir(monkeypatch, tmp_path)
    capture, capture_audit, claim, claim_audit = _build_capture_and_claim()
    batch = store.build_memory_write_batch(
        capture=capture,
        governed_claims=[claim],
        audit_events=[capture_audit, claim_audit],
        batch_id="aimb_pending",
    )
    batch["status"] = "pending"

    with pytest.raises(ValueError, match="status"):
        store.validate_memory_write_batch(batch)


def test_batch_requires_matching_capture_creation_audit(monkeypatch, tmp_path):
    _patch_data_dir(monkeypatch, tmp_path)
    capture, _capture_audit, claim, claim_audit = _build_capture_and_claim()

    with pytest.raises(ValueError, match="capture records require matching creation audit"):
        store.build_memory_write_batch(
            capture=capture,
            governed_claims=[claim],
            audit_events=[claim_audit],
            batch_id="aimb_missing_capture_audit",
        )


def test_batch_requires_matching_governed_claim_creation_audit(monkeypatch, tmp_path):
    _patch_data_dir(monkeypatch, tmp_path)
    capture, capture_audit, claim, _claim_audit = _build_capture_and_claim()

    with pytest.raises(ValueError, match="governed claims require matching creation audit"):
        store.build_memory_write_batch(
            capture=capture,
            governed_claims=[claim],
            audit_events=[capture_audit],
            batch_id="aimb_missing_claim_audit",
        )


def test_batch_rejects_governed_claim_reference_outside_capture_family(monkeypatch, tmp_path):
    _patch_data_dir(monkeypatch, tmp_path)
    capture, capture_audit, claim, claim_audit = _build_capture_and_claim()
    claim["discussion_ref"]["record_family"] = "ai_discussion"

    with pytest.raises(ValueError, match="discussion_ref.record_family"):
        store.build_memory_write_batch(
            capture=capture,
            governed_claims=[claim],
            audit_events=[capture_audit, claim_audit],
            batch_id="aimb_bad_ref",
        )


def test_index_is_rebuildable_from_committed_batches(monkeypatch, tmp_path):
    _patch_data_dir(monkeypatch, tmp_path)
    capture, capture_audit, claim, claim_audit = _build_capture_and_claim()
    store.create_capture_with_governed_claims(
        capture=capture,
        capture_audit_event=capture_audit,
        governed_claims=[claim],
        governed_claim_audit_events=[claim_audit],
        batch_id="aimb_rebuild",
    )
    (tmp_path / "index.json").unlink()

    index = store.rebuild_memory_index()

    assert index["record_type"] == "ai_discussion_memory_index"
    assert index["write_batches"][0]["id"] == "aimb_rebuild"
    assert index["governed_claims"][0]["capture_id"] == "aid_1"


def test_materialized_failure_after_batch_commit_is_repairable(monkeypatch, tmp_path):
    _patch_data_dir(monkeypatch, tmp_path)
    capture, capture_audit, claim, claim_audit = _build_capture_and_claim()

    def fail_materialize(_batch):
        raise RuntimeError("boom")

    monkeypatch.setattr(store, "_materialize_batch", fail_materialize)
    with pytest.raises(RuntimeError, match="boom"):
        store.create_capture_with_governed_claims(
            capture=capture,
            capture_audit_event=capture_audit,
            governed_claims=[claim],
            governed_claim_audit_events=[claim_audit],
            batch_id="aimb_repair",
        )

    assert (tmp_path / "write_batches" / "aimb_repair.json").exists()
    assert not (tmp_path / "captures" / "aid_1.json").exists()

    monkeypatch.undo()
    monkeypatch.setattr(store, "DATA_DIR", tmp_path)
    index = store.materialize_committed_write_batches()

    assert (tmp_path / "captures" / "aid_1.json").exists()
    assert index["captures"][0]["id"] == "aid_1"


def test_duplicate_fingerprint_does_not_create_second_authoritative_capture(monkeypatch, tmp_path):
    _patch_data_dir(monkeypatch, tmp_path)
    capture, capture_audit, claim, claim_audit = _build_capture_and_claim()
    first = store.create_capture_with_governed_claims(
        capture=capture,
        capture_audit_event=capture_audit,
        governed_claims=[claim],
        governed_claim_audit_events=[claim_audit],
        batch_id="aimb_first",
    )

    duplicate = store.create_capture_with_governed_claims(
        capture=capture,
        capture_audit_event=capture_audit,
        governed_claims=[claim],
        governed_claim_audit_events=[claim_audit],
        batch_id="aimb_duplicate",
    )

    assert duplicate["id"] == first["id"]
    assert not (tmp_path / "write_batches" / "aimb_duplicate.json").exists()
    assert len(list((tmp_path / "captures").glob("*.json"))) == 1


def test_duplicate_fingerprint_with_different_claim_is_rejected(monkeypatch, tmp_path):
    _patch_data_dir(monkeypatch, tmp_path)
    capture, capture_audit, claim, claim_audit = _build_capture_and_claim()
    store.create_capture_with_governed_claims(
        capture=capture,
        capture_audit_event=capture_audit,
        governed_claims=[claim],
        governed_claim_audit_events=[claim_audit],
        batch_id="aimb_first",
    )
    duplicate_capture, duplicate_capture_audit, new_claim, new_claim_audit = _build_capture_and_claim(
        fingerprint="fp_discussion_1",
        capture_id="aid_dupe",
        claim_id="gc_new",
    )

    with pytest.raises(ValueError, match="duplicate discussion_fingerprint"):
        store.create_capture_with_governed_claims(
            capture=duplicate_capture,
            capture_audit_event=duplicate_capture_audit,
            governed_claims=[new_claim],
            governed_claim_audit_events=[new_claim_audit],
            batch_id="aimb_dupe_new_claim",
        )


def test_empty_discussion_fingerprint_is_rejected(monkeypatch, tmp_path):
    _patch_data_dir(monkeypatch, tmp_path)
    capture, capture_audit, claim, claim_audit = _build_capture_and_claim()
    capture["discussion_fingerprint"] = ""

    with pytest.raises(ValueError, match="discussion_fingerprint"):
        store.build_memory_write_batch(
            capture=capture,
            governed_claims=[claim],
            audit_events=[capture_audit, claim_audit],
            batch_id="aimb_empty_fp",
        )


def test_write_batch_rejects_direct_import_operations(monkeypatch, tmp_path):
    _patch_data_dir(monkeypatch, tmp_path)
    capture, capture_audit, claim, claim_audit = _build_capture_and_claim()
    batch = store.build_memory_write_batch(
        capture=capture,
        governed_claims=[claim],
        audit_events=[capture_audit, claim_audit],
        batch_id="aimb_import",
    )
    batch["source"]["operation"] = "import_signal"

    with pytest.raises(ValueError, match="unsupported write operation"):
        store.validate_memory_write_batch(batch)


def test_write_batch_rejects_evidence_pack_and_full_transcript_payloads(monkeypatch, tmp_path):
    _patch_data_dir(monkeypatch, tmp_path)
    capture, capture_audit, claim, claim_audit = _build_capture_and_claim()
    batch = store.build_memory_write_batch(
        capture=capture,
        governed_claims=[claim],
        audit_events=[capture_audit, claim_audit],
        batch_id="aimb_forbidden",
    )
    batch["evidence_pack"] = {"items": []}
    with pytest.raises(ValueError, match="evidence_pack"):
        store.validate_memory_write_batch(batch)

    batch.pop("evidence_pack")
    batch["captures"][0]["boundary"]["full_transcript"] = True
    with pytest.raises(ValueError, match="full_transcript"):
        store.validate_memory_write_batch(batch)
