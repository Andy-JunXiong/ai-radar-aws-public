from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Literal


@dataclass
class SkillMeta:
    name: str
    version: str
    task_type: str
    layer: Literal["radar", "input", "reflection", "workspace", "project", "meta"]
    triggers: list[str]
    not_for: list[str] = field(default_factory=list)
    input_schema: str | None = None
    output_schema: str | None = None
    called_by: list[str] = field(default_factory=list)
    human_in_loop: bool = False
    notes: str = ""


def skill_prompt(**kwargs):
    """Decorator that attaches SkillMeta to a prompt function without changing behavior."""

    def wrapper(func: Callable):
        func._skill_meta = SkillMeta(**kwargs)
        return func

    return wrapper
