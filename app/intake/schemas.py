from dataclasses import dataclass, asdict, field
from typing import Any


@dataclass
class SignalScore:
    relevance: float = 0.0
    quality: float = 0.0
    total: float = 0.0
    personal_fit: float = 0.0


@dataclass
class Signal:
    id: str
    title: str
    url: str
    source: str
    source_type: str
    published_at: str = ""
    raw_text: str = ""
    clean_text: str = ""
    summary: str = ""
    analysis_input: str = ""
    tags: list[str] = field(default_factory=list)
    scores: SignalScore = field(default_factory=SignalScore)
    why_it_matters_to_me: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        return data