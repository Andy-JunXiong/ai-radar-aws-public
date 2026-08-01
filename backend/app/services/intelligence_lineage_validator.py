from __future__ import annotations

import hashlib
from typing import Any

from app.services.claim_verification_service import PRIMARY_EVIDENCE_PROVENANCE


SUPPORTED_CLAIM_LEVELS = frozenset({"directly_supported", "partially_supported"})


class IntelligenceLineageContractError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(f"{code}: {message}")


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _evidence_items_by_id(evidence_pack: dict[str, Any]) -> dict[str, dict[str, Any]]:
    items = evidence_pack.get("evidence_items")
    if not isinstance(items, list):
        raise IntelligenceLineageContractError(
            "invalid_evidence_items",
            "evidence_pack.evidence_items must be a list.",
        )

    indexed: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise IntelligenceLineageContractError(
                "invalid_evidence_item",
                f"evidence_pack.evidence_items[{index}] must be an object.",
            )
        evidence_id = _safe_text(item.get("evidence_id"))
        if not evidence_id:
            raise IntelligenceLineageContractError(
                "missing_evidence_id",
                f"evidence_pack.evidence_items[{index}].evidence_id is required.",
            )
        if evidence_id in indexed:
            raise IntelligenceLineageContractError(
                "duplicate_evidence_id",
                f"evidence_id {evidence_id} appears more than once in the evidence pack.",
            )
        indexed[evidence_id] = item
    return indexed


def _claim_evidence_refs(claim: dict[str, Any], *, index: int) -> list[str]:
    raw_refs = claim.get("evidence_refs")
    if raw_refs is None:
        return []
    if not isinstance(raw_refs, list):
        raise IntelligenceLineageContractError(
            "invalid_claim_evidence_refs",
            f"claim_results[{index}].evidence_refs must be a list.",
        )

    refs = [_safe_text(ref) for ref in raw_refs]
    if any(not ref for ref in refs):
        raise IntelligenceLineageContractError(
            "empty_claim_evidence_ref",
            f"claim_results[{index}].evidence_refs must not contain empty IDs.",
        )
    if len(refs) != len(set(refs)):
        raise IntelligenceLineageContractError(
            "duplicate_claim_evidence_ref",
            f"claim_results[{index}].evidence_refs must not contain duplicate IDs.",
        )
    return refs


def _validate_direct_support_span(
    claim: dict[str, Any],
    *,
    claim_index: int,
    evidence_refs: list[str],
    evidence_by_id: dict[str, dict[str, Any]],
) -> None:
    source_span = claim.get("source_span")
    if not isinstance(source_span, dict):
        raise IntelligenceLineageContractError(
            "direct_support_missing_source_span",
            f"claim_results[{claim_index}] is directly_supported but has no source_span.",
        )

    span_evidence_id = _safe_text(source_span.get("evidence_id"))
    if not span_evidence_id or span_evidence_id not in evidence_refs:
        raise IntelligenceLineageContractError(
            "source_span_evidence_mismatch",
            f"claim_results[{claim_index}].source_span must reference one of its evidence_refs.",
        )

    evidence_item = evidence_by_id[span_evidence_id]
    provenance = _safe_text(evidence_item.get("provenance")).lower()
    if not bool(evidence_item.get("traceable")) or provenance not in PRIMARY_EVIDENCE_PROVENANCE:
        raise IntelligenceLineageContractError(
            "direct_support_not_traceable_primary",
            f"claim_results[{claim_index}] directly_supported evidence must be traceable primary evidence.",
        )

    content = str(evidence_item.get("content") or "")
    try:
        char_start = int(source_span.get("char_start"))
        char_end = int(source_span.get("char_end"))
    except (TypeError, ValueError):
        raise IntelligenceLineageContractError(
            "invalid_source_span_bounds",
            f"claim_results[{claim_index}].source_span bounds must be integers.",
        )

    if char_start < 0 or char_end <= char_start or char_end > len(content):
        raise IntelligenceLineageContractError(
            "invalid_source_span_bounds",
            f"claim_results[{claim_index}].source_span is outside the referenced evidence content.",
        )

    expected_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    if _safe_text(source_span.get("content_hash")) != expected_hash:
        raise IntelligenceLineageContractError(
            "source_span_content_hash_mismatch",
            f"claim_results[{claim_index}].source_span content_hash does not match the evidence content.",
        )


def validate_intelligence_lineage(
    *,
    evidence_pack_id: str | None,
    evidence_pack: dict[str, Any] | None,
    claim_results: list[dict[str, Any]] | None,
) -> None:
    if claim_results is None and evidence_pack is None:
        return
    if not isinstance(evidence_pack, dict):
        raise IntelligenceLineageContractError(
            "missing_evidence_pack",
            "new claim-level verification metadata requires the complete evidence pack.",
        )

    pack_identity = _safe_text(evidence_pack.get("source_signal_id"))
    if not pack_identity:
        raise IntelligenceLineageContractError(
            "missing_evidence_pack_identity",
            "evidence_pack.source_signal_id is required.",
        )
    if _safe_text(evidence_pack_id) != pack_identity:
        raise IntelligenceLineageContractError(
            "evidence_pack_identity_mismatch",
            "evidence_pack_id must match evidence_pack.source_signal_id.",
        )

    evidence_by_id = _evidence_items_by_id(evidence_pack)
    if claim_results is None:
        return
    if not isinstance(claim_results, list):
        raise IntelligenceLineageContractError(
            "invalid_claim_results",
            "claim_results must be a list.",
        )

    for index, claim in enumerate(claim_results):
        if not isinstance(claim, dict):
            raise IntelligenceLineageContractError(
                "invalid_claim_result",
                f"claim_results[{index}] must be an object.",
            )
        support_level = _safe_text(claim.get("support_level")).lower()
        evidence_refs = _claim_evidence_refs(claim, index=index)
        missing_refs = [ref for ref in evidence_refs if ref not in evidence_by_id]
        if missing_refs:
            raise IntelligenceLineageContractError(
                "unresolved_claim_evidence_ref",
                f"claim_results[{index}] references missing evidence IDs: {', '.join(missing_refs)}.",
            )

        if support_level in SUPPORTED_CLAIM_LEVELS and not evidence_refs:
            raise IntelligenceLineageContractError(
                "supported_claim_missing_evidence_ref",
                f"claim_results[{index}] with support_level={support_level} requires evidence_refs.",
            )

        if support_level == "directly_supported":
            _validate_direct_support_span(
                claim,
                claim_index=index,
                evidence_refs=evidence_refs,
                evidence_by_id=evidence_by_id,
            )
