from __future__ import annotations

from typing import Any


def build_low_evidence_gate(evidence_quality: dict[str, Any]) -> dict[str, Any]:
    level = str(evidence_quality.get("level") or "thin").lower()

    if level == "insufficient":
        return {
            "max_confidence": 0.35,
            "output_mode": "observation_only",
            "decision_card_allowed": False,
            "required_uncertainty_notes": [
                "Evidence is insufficient for strong conclusions.",
                "Treat this output as an observation, not a reliable strategic recommendation.",
            ],
        }

    if level == "thin":
        return {
            "max_confidence": 0.55,
            "output_mode": "weak_insight_with_uncertainty",
            "decision_card_allowed": "watch_only",
            "required_uncertainty_notes": [
                "Evidence is thin and supports only cautious interpretation.",
                "Avoid broad market or strategic claims from this single signal.",
            ],
        }

    if level == "strong":
        return {
            "max_confidence": 0.95,
            "output_mode": "normal_insight",
            "decision_card_allowed": True,
            "required_uncertainty_notes": [],
        }

    return {
        "max_confidence": 0.85,
        "output_mode": "normal_insight",
        "decision_card_allowed": True,
        "required_uncertainty_notes": [],
    }
