import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services import signal_lifecycle_event_service as service


@pytest.fixture(autouse=True)
def disable_lifecycle_s3(monkeypatch):
    monkeypatch.setattr(service, "_s3_enabled", lambda: False)
    monkeypatch.setattr(service, "_read_s3_lifecycle_payload", lambda signal_id: None)
    monkeypatch.setattr(service, "_write_s3_lifecycle_payload", lambda signal_id, payload: None)
    monkeypatch.setattr(service, "_list_s3_lifecycle_payloads", lambda: ([], []))


def _verification():
    return {
        "verification_status": "partially_verified",
        "allowed_downstream_actions": ["project_takeaway_candidate"],
        "blocked_downstream_actions": ["low_risk_action_candidate"],
        "claim_support_summary": {
            "directly_supported": 1,
            "unsupported": 0,
        },
        "confidence_label": "high",
        "confidence_score": 0.75,
        "review_priority": "review_required",
        "evidence_note": "Evidence is partial.",
    }


def _model_provenance():
    return {
        "provider": "openai",
        "model_id": "gpt-5.5",
        "deterministic_fingerprint": "57827a90abcdef",
        "provenance_schema_version": 1,
    }


def test_build_generate_insight_events_records_insight_and_verification():
    events = service.build_generate_insight_events(
        signal_id="sig-1",
        source_record_family="signal",
        source_record_id="sig-1",
        status_before="pending",
        status_after="analyzed",
        verification=_verification(),
        produced_by_model=_model_provenance(),
        preexisting_fingerprint="old",
        generated_fingerprint="new",
        stored_fingerprint="new",
        fingerprint_changed=True,
        event_time="2026-05-22T00:00:00Z",
        recorded_at="2026-05-22T00:00:00Z",
    )

    assert [event["event_type"] for event in events] == [
        "insight_generated",
        "verification_completed",
    ]
    assert events[0]["provenance_class"] == "direct"
    assert events[0]["state"] == {"before": "pending", "after": "analyzed"}
    assert events[0]["support"]["stored_fingerprint"] == "new"
    assert events[0]["support"]["fingerprint_changed"] is True
    assert events[0]["model_provenance_ref"] == {
        "provider": "openai",
        "model_id": "gpt-5.5",
        "fingerprint_prefix": "57827a90",
        "schema_version": 1,
    }

    verification_event = events[1]
    assert verification_event["support"]["verification_status"] == "partially_verified"
    assert verification_event["support"]["blocked_downstream_actions"] == ["low_risk_action_candidate"]
    assert verification_event["support"]["claim_support_summary"]["directly_supported"] == 1
    assert verification_event["support"]["evaluation_summary"] == "Evidence is partial."
    assert "raw_prompt" not in str(events)


def test_build_generate_insight_events_omits_verification_event_when_missing():
    events = service.build_generate_insight_events(
        signal_id="sig-2",
        source_record_family="signal",
        source_record_id="sig-2",
        status_before="saved",
        status_after="analyzed",
        verification=None,
        produced_by_model=None,
    )

    assert [event["event_type"] for event in events] == ["insight_generated"]
    assert events[0]["model_provenance_ref"] is None


def test_build_generate_insight_events_keeps_manual_session_source_ref():
    events = service.build_generate_insight_events(
        signal_id="manual_manual-1",
        source_record_family="manual_session",
        source_record_id="manual-1",
        status_before="pending",
        status_after="analyzed",
        verification=_verification(),
    )

    assert events[0]["source_ref"] == {
        "record_family": "manual_session",
        "record_id": "manual-1",
    }


def test_build_signal_completion_events_records_workspace_without_reflection_body():
    events = service.build_signal_completion_events(
        signal_id="manual_manual-1",
        source_record_family="manual_session",
        source_record_id="manual-1",
        status_before="analyzed",
        verification=_verification(),
        workspace_file_name="workspace.json",
        workspace_saved_at="2026-05-23T00:00:00Z",
        project_improvements=[
            {
                "signal_id": "manual_manual-1",
                "project_id": "ai_radar",
                "status": "new",
                "candidate_source": "unverified_manual_entry",
                "source_type": "manual_upload",
                "manual_session_id": "manual-1",
                "verification_metadata": {
                    **_verification(),
                    "upload_reason": "Compare against roadmap",
                    "intended_use": "Watch for project fit",
                    "cognitive_layer": "L2",
                },
                "produced_by_model": _model_provenance(),
                "final_reflection": "Do not store this reflection text.",
            }
        ],
        event_time="2026-05-23T00:00:00Z",
        recorded_at="2026-05-23T00:00:00Z",
    )

    assert [event["event_type"] for event in events] == [
        "workspace_completed",
        "project_candidate_created",
    ]
    assert events[0]["route"] == "/signals/complete"
    assert events[0]["state"] == {"before": "analyzed", "after": "completed"}
    assert events[0]["support"]["workspace_file_name"] == "workspace.json"
    assert events[0]["support"]["project_improvements_written"] == 1
    assert events[0]["support"]["verification"]["verification_status"] == "partially_verified"

    project_event = events[1]
    assert project_event["project_ref"] == {
        "project_id": "ai_radar",
        "record_family": "project_improvement",
        "record_id": "ai_radar:manual_manual-1",
        "outcome": "new",
    }
    assert project_event["support"]["candidate_source"] == "unverified_manual_entry"
    assert project_event["support"]["upload_reason"] == "Compare against roadmap"
    assert project_event["support"]["intended_use"] == "Watch for project fit"
    assert project_event["support"]["cognitive_layer"] == "L2"
    assert project_event["model_provenance_ref"]["fingerprint_prefix"] == "57827a90"
    assert "Do not store this reflection text." not in str(events)


def test_build_project_review_attached_events_derives_project_side_records_without_notes():
    events = service.build_project_review_attached_events(
        signal_id="manual_123",
        review_records=[
            {
                "id": "prv_1",
                "project_id": "ai_radar",
                "project_name": "AI Radar",
                "signal_id": "manual_123",
                "outcome": "watch",
                "source_status": "new",
                "source_type": "manual_upload",
                "manual_session_id": "123",
                "upload_reason": "Compare against roadmap",
                "intended_use": "Watch for project fit",
                "cognitive_layer": "L2",
                "verification_status": "partially_verified",
                "claim_support_summary": {"unsupported": 1},
                "blocked_downstream_actions": ["low_risk_action_candidate"],
                "manual_override_note": "Do not expose this reviewer note.",
                "reviewed_at": "2026-05-24T00:00:00Z",
            }
        ],
        calibration_events=[
            {
                "id": "pce_1",
                "event_type": "takeaway_watch_started",
                "project_id": "ai_radar",
                "signal_id": "manual_123",
                "outcome": "watch",
                "review_record_id": "prv_1",
                "created_at": "2026-05-24T00:01:00Z",
            }
        ],
        recorded_at="2026-05-24T00:02:00Z",
    )

    assert [event["event_type"] for event in events] == [
        "project_review_attached",
        "project_review_attached",
    ]
    assert events[0]["provenance_class"] == "derived"
    assert events[0]["route"] == "project_review_records"
    assert events[0]["source_ref"] == {
        "record_family": "project_review_record",
        "record_id": "prv_1",
    }
    assert events[0]["project_ref"] == {
        "project_id": "ai_radar",
        "project_name": "AI Radar",
        "record_family": "project_review_record",
        "record_id": "prv_1",
        "outcome": "watch",
    }
    assert events[0]["support"]["upload_reason"] == "Compare against roadmap"
    assert events[0]["support"]["blocked_downstream_actions"] == ["low_risk_action_candidate"]
    assert events[1]["source_ref"]["record_family"] == "project_calibration_event"
    assert events[1]["support"]["review_record_id"] == "prv_1"
    assert "Do not expose this reviewer note." not in str(events)


def test_build_signal_status_change_events_records_saved_reason():
    events = service.build_signal_status_change_events(
        signal_id="sig-1",
        source_record_family="signal",
        source_record_id="sig-1",
        status_before="pending",
        status_after="saved",
        saved_reason="Review later",
        decision_trace_event="operator_saved_for_later",
        updated_keys=["signals/latest/signals.json"],
        event_time="2026-05-23T00:00:00Z",
        recorded_at="2026-05-23T00:00:00Z",
    )

    assert len(events) == 1
    event = events[0]
    assert event["event_type"] == "signal_status_changed"
    assert event["route"] == "/signals/update-status"
    assert event["state"] == {"before": "pending", "after": "saved"}
    assert event["support"] == {
        "saved_reason": "Review later",
        "decision_trace_event": "operator_saved_for_later",
        "updated_keys": ["signals/latest/signals.json"],
    }


def test_append_and_load_signal_lifecycle_events_uses_local_file(tmp_path, monkeypatch):
    monkeypatch.setattr(service, "LIFECYCLE_DATA_DIR", tmp_path)
    events = service.build_generate_insight_events(
        signal_id="sig/unsafe",
        source_record_family="signal",
        source_record_id="sig/unsafe",
        status_before="pending",
        status_after="analyzed",
    )

    saved = service.append_signal_lifecycle_events("sig/unsafe", events)
    loaded = service.load_signal_lifecycle_events("sig/unsafe")

    assert saved == loaded
    assert len(loaded) == 1
    assert service.lifecycle_event_file_path("sig/unsafe").name == "sig_unsafe.json"


def test_append_signal_lifecycle_events_writes_shared_payload_when_available(tmp_path, monkeypatch):
    monkeypatch.setattr(service, "LIFECYCLE_DATA_DIR", tmp_path)
    writes = []
    monkeypatch.setattr(service, "_write_s3_lifecycle_payload", lambda signal_id, payload: writes.append((signal_id, payload)))

    events = service.build_signal_status_change_events(
        signal_id="sig-1",
        source_record_family="signal",
        source_record_id="sig-1",
        status_before="pending",
        status_after="saved",
        event_time="2026-05-24T00:00:00Z",
        recorded_at="2026-05-24T00:00:00Z",
    )

    saved = service.append_signal_lifecycle_events("sig-1", events)

    assert len(saved) == 1
    assert writes[0][0] == "sig-1"
    assert writes[0][1]["events"] == saved
    assert writes[0][1]["signal_id"] == "sig-1"


def test_load_signal_lifecycle_events_merges_shared_and_local_events(tmp_path, monkeypatch):
    monkeypatch.setattr(service, "LIFECYCLE_DATA_DIR", tmp_path)
    shared_event = service.build_signal_status_change_events(
        signal_id="sig-1",
        source_record_family="signal",
        source_record_id="sig-1",
        status_before="pending",
        status_after="saved",
        event_time="2026-05-24T00:00:00Z",
        recorded_at="2026-05-24T00:00:00Z",
    )[0]
    local_event = service.build_signal_completion_events(
        signal_id="sig-1",
        source_record_family="signal",
        source_record_id="sig-1",
        status_before="saved",
        event_time="2026-05-24T00:01:00Z",
        recorded_at="2026-05-24T00:01:00Z",
    )[0]
    monkeypatch.setattr(
        service,
        "_read_s3_lifecycle_payload",
        lambda signal_id: {"signal_id": signal_id, "events": [shared_event]},
    )
    path = service.lifecycle_event_file_path("sig-1")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        service.json.dumps({"signal_id": "sig-1", "events": [local_event]}, ensure_ascii=False),
        encoding="utf-8",
    )

    loaded = service.load_signal_lifecycle_events("sig-1")

    assert [event["event_type"] for event in loaded] == [
        "signal_status_changed",
        "workspace_completed",
    ]


def test_load_signal_lifecycle_events_returns_empty_for_malformed_payload(tmp_path, monkeypatch):
    monkeypatch.setattr(service, "LIFECYCLE_DATA_DIR", tmp_path)
    path = service.lifecycle_event_file_path("sig-1")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not json", encoding="utf-8")

    assert service.load_signal_lifecycle_events("sig-1") == []


def test_summarize_signal_lifecycle_events_counts_soft_recorded_events():
    events = []
    events.extend(
        service.build_generate_insight_events(
            signal_id="sig-1",
            source_record_family="signal",
            source_record_id="sig-1",
            status_before="pending",
            status_after="analyzed",
            verification=_verification(),
            event_time="2026-05-22T00:00:00Z",
            recorded_at="2026-05-22T00:00:00Z",
        )
    )
    events.extend(
        service.build_signal_status_change_events(
            signal_id="manual_session-1",
            source_record_family="manual_session",
            source_record_id="session-1",
            status_before="analyzed",
            status_after="saved",
            event_time="2026-05-23T00:00:00Z",
            recorded_at="2026-05-23T00:00:00Z",
        )
    )

    summary = service.summarize_signal_lifecycle_events(events, file_count=2, recent_limit=2)

    assert summary["authoritative"] is False
    assert summary["summary_scope"] == "soft_recorded_lifecycle_events"
    assert summary["file_count"] == 2
    assert summary["signal_count"] == 2
    assert summary["event_count"] == 3
    assert summary["event_types"] == {
        "insight_generated": 1,
        "signal_status_changed": 1,
        "verification_completed": 1,
    }
    assert summary["source_record_families"] == {
        "manual_session": 1,
        "signal": 2,
    }
    assert summary["routes"]["/signals/generate-insight"] == 2
    assert summary["routes"]["/signals/update-status"] == 1
    assert summary["hard_enforcement_readiness"]["selected_path"] == "/signals/update-status"
    assert summary["hard_enforcement_readiness"]["status"] == "ready"
    assert summary["hard_enforcement_readiness"]["direct_event_count"] == 1
    assert summary["hard_enforcement_readiness"]["complete_event_count"] == 1
    assert summary["hard_enforcement_readiness"]["atomicity_preflight"]["atomicity_ready"] is False
    assert summary["hard_enforcement_readiness"]["atomicity_preflight"]["blocking_recommendation"] == "keep_report_only"
    assert "Atomicity preflight is not ready; do not enable mutation blocking for update-status." in summary["hard_enforcement_readiness"]["warnings"]
    assert summary["state_transitions"] == [
        {"before": "pending", "after": "analyzed", "count": 2},
        {"before": "analyzed", "after": "saved", "count": 1},
    ]
    assert [event["event_type"] for event in summary["recent_events"]] == [
        "signal_status_changed",
        "insight_generated",
    ]
    assert "raw_prompt" not in str(summary)


def test_hard_enforcement_readiness_blocks_when_update_status_event_is_missing():
    summary = service.summarize_signal_lifecycle_events([], recent_limit=2)

    readiness = summary["hard_enforcement_readiness"]

    assert readiness["status"] == "not_ready"
    assert readiness["event_count"] == 0
    assert readiness["blocking_gaps"] == ["No /signals/update-status lifecycle events were found."]
    assert readiness["checks"][1]["status"] == "not_ready"


def test_hard_enforcement_readiness_reports_incomplete_direct_event():
    event = service.build_signal_status_change_events(
        signal_id="sig-1",
        source_record_family="signal",
        source_record_id="sig-1",
        status_before="pending",
        status_after="saved",
        event_time="2026-05-24T00:00:00Z",
        recorded_at="2026-05-24T00:00:00Z",
    )[0]
    event["state"] = {"after": "saved"}

    readiness = service.build_lifecycle_hard_enforcement_readiness([event])

    assert readiness["status"] == "not_ready"
    assert readiness["event_count"] == 1
    assert readiness["direct_event_count"] == 1
    assert readiness["complete_event_count"] == 0
    assert readiness["incomplete_events"][0]["missing_fields"] == ["state.before"]
    assert "One or more direct update-status events are missing required envelope fields." in readiness["blocking_gaps"]


def test_hard_enforcement_flag_defaults_off(monkeypatch):
    monkeypatch.delenv("AI_RADAR_SIGNAL_STATUS_HARD_ENFORCEMENT", raising=False)

    flag = service.signal_status_hard_enforcement_flag()

    assert flag["status"] == "off"
    assert flag["effective_mode"] == "off"
    assert flag["defaulted"] is True
    assert flag["enforcement_active"] is False
    assert flag["blocks_mutations"] is False


def test_hard_enforcement_flag_supports_report_only(monkeypatch):
    monkeypatch.setenv("AI_RADAR_SIGNAL_STATUS_HARD_ENFORCEMENT", "report_only")

    flag = service.signal_status_hard_enforcement_flag()

    assert flag["status"] == "report_only"
    assert flag["effective_mode"] == "report_only"
    assert flag["defaulted"] is False
    assert flag["enforcement_active"] is False


def test_hard_enforcement_flag_does_not_silently_enable_enforcement(monkeypatch):
    monkeypatch.setenv("AI_RADAR_SIGNAL_STATUS_HARD_ENFORCEMENT", "enforce")
    event = service.build_signal_status_change_events(
        signal_id="sig-1",
        source_record_family="signal",
        source_record_id="sig-1",
        status_before="pending",
        status_after="saved",
        event_time="2026-05-24T00:00:00Z",
        recorded_at="2026-05-24T00:00:00Z",
    )[0]

    readiness = service.build_lifecycle_hard_enforcement_readiness([event])

    assert readiness["flag"]["status"] == "enforce_requested"
    assert readiness["flag"]["effective_mode"] == "report_only"
    assert readiness["flag"]["enforcement_active"] is False
    assert readiness["flag"]["blocks_mutations"] is False
    assert "Hard enforcement was requested by flag, but mutation blocking is not wired in this release." in readiness["warnings"]


def test_update_status_atomicity_preflight_keeps_blocking_disabled():
    preflight = service.build_update_status_atomicity_preflight()

    assert preflight["status"] == "not_ready"
    assert preflight["atomicity_ready"] is False
    assert preflight["safe_to_block_mutation"] is False
    assert preflight["blocking_recommendation"] == "keep_report_only"
    assert preflight["current_order"] == "mutation_then_lifecycle_append"
    assert [item["id"] for item in preflight["checked_subpaths"]] == [
        "manual_session",
        "automatic_signal_by_id",
        "automatic_signal_by_identity",
    ]
    assert all(item["atomicity_ready"] is False for item in preflight["checked_subpaths"])


def test_summarize_signal_lifecycle_store_reads_files_and_reports_malformed(tmp_path, monkeypatch):
    monkeypatch.setattr(service, "LIFECYCLE_DATA_DIR", tmp_path)
    service.append_signal_lifecycle_events(
        "sig-1",
        service.build_signal_status_change_events(
            signal_id="sig-1",
            source_record_family="signal",
            source_record_id="sig-1",
            status_before="pending",
            status_after="rejected",
            event_time="2026-05-23T01:00:00Z",
            recorded_at="2026-05-23T01:00:00Z",
        ),
    )
    (tmp_path / "broken.json").write_text("{not json", encoding="utf-8")

    summary = service.summarize_signal_lifecycle_store(recent_limit=5)

    assert summary["file_count"] == 2
    assert summary["malformed_file_count"] == 1
    assert summary["malformed_files"] == ["broken.json"]
    assert summary["signal_count"] == 1
    assert summary["event_count"] == 1
    assert summary["event_types"] == {"signal_status_changed": 1}
    assert summary["latest_recorded_at"] == "2026-05-23T01:00:00Z"


def test_summarize_signal_lifecycle_store_includes_shared_payloads(tmp_path, monkeypatch):
    monkeypatch.setattr(service, "LIFECYCLE_DATA_DIR", tmp_path)
    shared_event = service.build_signal_status_change_events(
        signal_id="sig-s3",
        source_record_family="signal",
        source_record_id="sig-s3",
        status_before="pending",
        status_after="saved",
        event_time="2026-05-24T00:00:00Z",
        recorded_at="2026-05-24T00:00:00Z",
    )[0]
    monkeypatch.setattr(
        service,
        "_list_s3_lifecycle_payloads",
        lambda: ([("signal_lifecycle/sig-s3.json", {"signal_id": "sig-s3", "events": [shared_event]})], []),
    )
    monkeypatch.setattr(service, "_s3_enabled", lambda: True)

    summary = service.summarize_signal_lifecycle_store(recent_limit=5)

    assert summary["storage"] == "s3_with_local_cache"
    assert summary["file_count"] == 0
    assert summary["s3_file_count"] == 1
    assert summary["event_count"] == 1
    assert summary["event_types"] == {"signal_status_changed": 1}
