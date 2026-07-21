from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from app.services.execution_policy_service import ExecutionPolicy


CITATION_PATTERN = re.compile(r"\[(evidence|source|citation)\s*:", re.IGNORECASE)


@dataclass(frozen=True)
class ValidationResult:
    passed: bool
    citation_count: int
    verification_status: str
    citation_validation_passed: bool | None
    verification_passed: bool | None
    unsupported_claims: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _collect_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        collected: list[str] = []
        for nested in value.values():
            collected.extend(_collect_strings(nested))
        return collected
    if isinstance(value, list):
        collected = []
        for nested in value:
            collected.extend(_collect_strings(nested))
        return collected
    return []


def count_citations(value: Any) -> int:
    return sum(len(CITATION_PATTERN.findall(text)) for text in _collect_strings(value))


def _extract_unsupported_claims(value: Any) -> list[str]:
    claims: list[str] = []
    for text in _collect_strings(value):
        stripped = text.strip()
        if not stripped:
            continue
        first_sentence = stripped.split(".")[0].strip()
        if first_sentence:
            claims.append(first_sentence[:180])
    return claims[:5]


def mark_output_uncertain(value: Any) -> Any:
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return text
        if text.lower().startswith("uncertain:"):
            return text
        return f"Uncertain: {text}"
    if isinstance(value, dict):
        updated: dict[str, Any] = {}
        for key, nested in value.items():
            if str(key).lower() in {
                "provider_used",
                "model_used",
                "status",
                "execution_policy",
                "policy_metadata",
                "evidence_pack",
            }:
                updated[key] = nested
            else:
                updated[key] = mark_output_uncertain(nested)
        return updated
    if isinstance(value, list):
        return [mark_output_uncertain(item) for item in value]
    return value


def validate_output(*, policy: ExecutionPolicy, output: Any, context_available: bool) -> ValidationResult:
    failures: list[str] = []
    notes: list[str] = []
    citation_count = count_citations(output)
    citation_validation_passed: bool | None = None

    if policy.citation_required and context_available and citation_count <= 0:
        failures.append("missing_citations")
        citation_validation_passed = False
        notes.append("citation_required_but_missing")
    elif policy.citation_required and context_available:
        citation_validation_passed = True

    verification_status = "not_required"
    verification_passed: bool | None = None
    unsupported_claims: list[str] = []
    if policy.verification_required:
        if context_available and citation_count > 0:
            verification_status = "basic_verified"
            verification_passed = True
        else:
            verification_status = "uncertain"
            failures.append("verification_incomplete")
            verification_passed = False
            unsupported_claims = _extract_unsupported_claims(output)
            if unsupported_claims:
                notes.append("unsupported_claims_marked_uncertain")
            else:
                notes.append("verification_required_but_no_supported_claims_found")

    return ValidationResult(
        passed=not failures,
        citation_count=citation_count,
        verification_status=verification_status,
        citation_validation_passed=citation_validation_passed,
        verification_passed=verification_passed,
        unsupported_claims=unsupported_claims,
        notes=notes,
        failures=failures,
    )
