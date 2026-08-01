import hashlib
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.intelligence_lineage_validator import (  # noqa: E402
    IntelligenceLineageContractError,
    validate_intelligence_lineage,
)


def _evidence_pack(*, signal_id="sig-1", traceable=True, provenance="source_excerpt"):
    content = "The source reports a bounded and directly quoted result."
    return {
        "source_signal_id": signal_id,
        "evidence_items": [
            {
                "evidence_id": f"ev_{signal_id}_source_excerpt",
                "source_id": signal_id,
                "source_field": "source_excerpt",
                "content": content,
                "provenance": provenance,
                "traceable": traceable,
            }
        ],
    }


def _direct_claim(*, signal_id="sig-1"):
    evidence_id = f"ev_{signal_id}_source_excerpt"
    content = "The source reports a bounded and directly quoted result."
    return {
        "claim_id": "claim-1",
        "support_level": "directly_supported",
        "evidence_refs": [evidence_id],
        "source_span": {
            "evidence_id": evidence_id,
            "char_start": 0,
            "char_end": len(content),
            "content_hash": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        },
    }


def test_valid_direct_support_lineage_passes():
    validate_intelligence_lineage(
        evidence_pack_id="sig-1",
        evidence_pack=_evidence_pack(),
        claim_results=[_direct_claim()],
    )

def test_missing_claim_evidence_reference_is_rejected():
    claim = _direct_claim()
    claim["evidence_refs"] = ["ev_missing"]
    claim["source_span"]["evidence_id"] = "ev_missing"

    with pytest.raises(IntelligenceLineageContractError) as raised:
        validate_intelligence_lineage(
            evidence_pack_id="sig-1",
            evidence_pack=_evidence_pack(),
            claim_results=[claim],
        )

    assert raised.value.code == "unresolved_claim_evidence_ref"


def test_direct_support_requires_traceable_primary_evidence():
    with pytest.raises(IntelligenceLineageContractError) as raised:
        validate_intelligence_lineage(
            evidence_pack_id="sig-1",
            evidence_pack=_evidence_pack(traceable=False, provenance="llm_generated"),
            claim_results=[_direct_claim()],
        )

    assert raised.value.code == "direct_support_not_traceable_primary"


def test_direct_support_requires_source_span():
    claim = _direct_claim()
    claim["source_span"] = None

    with pytest.raises(IntelligenceLineageContractError) as raised:
        validate_intelligence_lineage(
            evidence_pack_id="sig-1",
            evidence_pack=_evidence_pack(),
            claim_results=[claim],
        )

    assert raised.value.code == "direct_support_missing_source_span"


def test_evidence_pack_identity_must_match_verified_insight_reference():
    with pytest.raises(IntelligenceLineageContractError) as raised:
        validate_intelligence_lineage(
            evidence_pack_id="sig-other",
            evidence_pack=_evidence_pack(),
            claim_results=[],
        )

    assert raised.value.code == "evidence_pack_identity_mismatch"


def test_unsupported_claim_may_have_no_evidence_reference():
    validate_intelligence_lineage(
        evidence_pack_id="sig-1",
        evidence_pack=_evidence_pack(),
        claim_results=[
            {
                "claim_id": "claim-unsupported",
                "support_level": "unsupported",
                "evidence_refs": [],
                "source_span": None,
            }
        ],
    )
