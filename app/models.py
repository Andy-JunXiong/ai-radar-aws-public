from dataclasses import dataclass, asdict
from typing import Any


@dataclass
class Signal:
    title: str
    summary: str
    url: str
    author: str
    source: str
    category: str
    published_at: str
    collected_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Insight:
    signal_title: str
    signal_summary: str
    why_it_matters: str
    relevance_to_projects: str
    relevance_to_career: str
    synthesized_insight: str
    provider_used: str | None = None
    model_used: str | None = None
    execution_policy: dict[str, Any] | None = None
    execution: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
