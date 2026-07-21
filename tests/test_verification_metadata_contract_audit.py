import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services import signal_lifecycle_event_service
from app.services import verification_metadata_reader as reader


def _finding_codes(report):
    return {finding["code"] for finding in report["findings"]}


def test_contract_audit_normalizes_nested_verified_insight_metadata():
    report = reader.audit_verification_metadata_contract(
        {
            "verified_insight": {
                "status": "partially_verified",
                "evidence": {"level": "sufficient"},
                "claims": {"support_summary": {"partially_supported": 1}},
                "confidence": {"score": 0.72, "label": "medium"},
                "action_policy": {
                    "allowed": ["project_takeaway_candidate", "watch_only"],
                    "blocked": ["low_risk_action_candidate"],
                },
            }
        },
        context="project_takeaway_candidate",
    )

    assert report["audit_mode"] == "soft_report_only"
    assert report["contract_ok"] is True
    assert report["normalized"]["verification_status"] == "partially_verified"
    assert report["normalized"]["evidence_level"] == "sufficient"
    assert report["normalized"]["claim_support_summary"] == {"partially_supported": 1}
    assert report["normalized"]["blocked_downstream_actions"] == ["low_risk_action_candidate"]
    assert report["normalized"]["confidence_score"] == 0.72
    assert report["findings"] == []


def test_insight_write_contract_requires_evidence_level_but_does_not_block_runtime():
    report = reader.audit_verification_metadata_contract(
        {
            "verification_status": "partially_verified",
            "allowed_downstream_actions": ["project_takeaway_candidate"],
            "blocked_downstream_actions": ["low_risk_action_candidate"],
            "claim_support_summary": {"inferred": 1},
        },
        context="insight_write",
    )

    assert report["contract_ok"] is False
    assert "missing_evidence_level" in _finding_codes(report)
    assert report["normalized"]["verification_status"] == "partially_verified"
    assert report["normalized"]["blocked_downstream_actions"] == ["low_risk_action_candidate"]
    assert report["audit_mode"] == "soft_report_only"


def test_project_takeaway_contract_warns_when_blocked_status_lacks_action_gates():
    report = reader.audit_verification_metadata_contract(
        {
            "verification_status": "unsupported",
            "blocked_downstream_actions": [],
            "claim_support_summary": {"unsupported": 1},
        },
        context="project_takeaway_candidate",
    )

    assert report["contract_ok"] is True
    assert "blocked_status_missing_downstream_blocks" in _finding_codes(report)
    warning = report["findings"][0]
    assert warning["severity"] == "warning"
    assert "project_takeaway_candidate" in warning["message"]
    assert "low_risk_action_candidate" in warning["message"]


def test_knowledge_convergence_contract_warns_when_action_block_is_missing():
    report = reader.audit_verification_metadata_contract(
        {
            "knowledge_convergence": True,
            "verification_status": "knowledge_convergence_review_candidate",
            "allowed_downstream_actions": ["project_takeaway_candidate"],
            "blocked_downstream_actions": [],
            "claim_support_summary": {},
        },
        context="project_takeaway_candidate",
    )

    assert report["contract_ok"] is True
    assert "knowledge_convergence_missing_action_block" in _finding_codes(report)


def test_contract_audit_warns_when_allowed_and_blocked_actions_conflict():
    report = reader.audit_verification_metadata_contract(
        {
            "verification_status": "partially_verified",
            "allowed_downstream_actions": ["project_takeaway_candidate", "watch_only"],
            "blocked_downstream_actions": ["watch_only", "low_risk_action_candidate"],
            "claim_support_summary": {"inferred": 1},
        },
        context="project_takeaway_candidate",
    )

    assert report["contract_ok"] is True
    assert report["normalized"]["conflicting_downstream_actions"] == ["watch_only"]
    assert "conflicting_downstream_actions" in _finding_codes(report)


def test_lifecycle_support_snapshot_contract_accepts_existing_soft_event_support():
    verification = {
        "verification_status": "partially_verified",
        "evidence_quality": {"level": "thin"},
        "allowed_downstream_actions": ["project_takeaway_candidate"],
        "blocked_downstream_actions": ["low_risk_action_candidate"],
        "claim_support_summary": {"inferred": 1},
        "confidence_label": "medium",
        "confidence_score": 0.52,
    }
    support = signal_lifecycle_event_service.build_verification_support_snapshot(verification)

    report = reader.audit_verification_metadata_contract(
        support,
        context="lifecycle_support_snapshot",
    )

    assert report["contract_ok"] is True
    assert report["normalized"]["verification_status"] == "partially_verified"
    assert report["normalized"]["blocked_downstream_actions"] == ["low_risk_action_candidate"]
    assert report["normalized"]["claim_support_summary"] == {"inferred": 1}
    assert report["findings"] == []


def test_missing_contract_metadata_is_report_only_error():
    report = reader.audit_verification_metadata_contract({}, context="insight_write")

    assert report["contract_ok"] is False
    assert report["context"] == "insight_write"
    assert report["finding_count"] >= 1
    assert "missing_verification_metadata" in _finding_codes(report)
    assert report["audit_mode"] == "soft_report_only"
