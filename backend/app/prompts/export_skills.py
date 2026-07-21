from __future__ import annotations

import argparse
import hashlib
import inspect
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from pydantic import BaseModel
except Exception:  # pragma: no cover - fallback if pydantic import changes
    BaseModel = object  # type: ignore[assignment]

from app.prompts import registry
from app.prompts.skill_meta import SkillMeta


DEFAULT_TARGET = Path.home() / ".claude" / "skills"
REGISTRY_SOURCE = "backend/app/prompts/registry.py"


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _today_iso() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _discover_skills() -> list[tuple[str, Any, SkillMeta]]:
    discovered: list[tuple[str, Any, SkillMeta]] = []
    for func_name, member in inspect.getmembers(registry, inspect.isfunction):
        meta = getattr(member, "_skill_meta", None)
        if isinstance(meta, SkillMeta):
            discovered.append((func_name, member, meta))
    return discovered


def _render_bullets(values: list[str], *, fallback: str) -> str:
    if not values:
        return fallback
    return "\n".join(f"- {value}" for value in values)


def _render_skill_markdown(*, func_name: str, meta: SkillMeta, now_iso: str, purpose: str) -> str:
    triggers_joined = " ".join(meta.triggers).strip()
    not_for_joined = " ".join(meta.not_for).strip()
    description = triggers_joined
    if not_for_joined:
        description += f" Do NOT use for: {not_for_joined}."

    human_block = ""
    if meta.human_in_loop:
        human_block = f"""
## Human-in-loop required
This skill is marked `human_in_loop=True`. Any optimization (manual or via
darwin.skill) MUST be reviewed before being merged. Reason from decorator:

> {meta.notes or "(no notes provided)"}
""".strip()

    notes_text = meta.notes or "(no additional notes provided)"

    parts = [
        "---",
        f"name: {meta.name}",
        f"description: {description}",
        f"version: {meta.version}",
        f"layer: {meta.layer}",
        f"task_type: {meta.task_type}",
        f"last_updated: {now_iso}",
        "auto_generated: true",
        f"human_in_loop: {str(meta.human_in_loop).lower()}",
        "---",
        "",
        f"# {meta.name}",
        "",
        f"> This file is auto-generated from `registry.py::{func_name}`.",
        "> Do not edit directly. Run `python -m app.prompts.export_skills` to regenerate.",
        "> Manual content belongs in `references/` only.",
        "",
        "## Purpose",
        purpose,
        "",
        "## Triggers",
        _render_bullets(meta.triggers, fallback="(no triggers defined)"),
        "",
        "## Do NOT use for",
        _render_bullets(meta.not_for, fallback="(no negative triggers defined)"),
        "",
        "## Source",
        f"- Code: `{REGISTRY_SOURCE}::{func_name}`",
        "- Called by:",
        _render_bullets(meta.called_by, fallback="- (no call sites declared)"),
        f'- Routed via: `model_router_service` with `task_type="{meta.task_type}"`',
        "",
        "## Input contract",
        (
            f"See `references/{meta.input_schema}`"
            if meta.input_schema
            else "(input_schema not defined in decorator)"
        ),
        "",
        "## Output contract",
        (
            f"See `references/{meta.output_schema}`"
            if meta.output_schema
            else "(output_schema not defined in decorator)"
        ),
        "",
        "## Quality criteria (8-dimension, darwin.skill compatible)",
        "This section is **manually maintained** in `references/quality-notes.md`.",
        "",
    ]

    if human_block:
        parts.extend([human_block, ""])

    parts.extend(
        [
            "## Notes",
            notes_text,
            "",
            "## Version history",
            "See `references/version-history.md` (manually maintained).",
            "",
        ]
    )

    return "\n".join(parts)


def _schema_placeholder(signature_text: str) -> str:
    return (
        "{\n"
        f'  "$comment": "TODO: define input schema. Function signature was: {signature_text}",\n'
        '  "type": "object",\n'
        '  "properties": {}\n'
        "}\n"
    )


def _maybe_generate_schema_from_signature(func: Any) -> str | None:
    try:
        signature = inspect.signature(func)
    except Exception:
        return None

    for parameter in signature.parameters.values():
        annotation = parameter.annotation
        if annotation is inspect._empty:
            continue
        if inspect.isclass(annotation) and issubclass(annotation, BaseModel):
            try:
                model_schema = annotation.model_json_schema()
                import json

                return json.dumps(model_schema, ensure_ascii=False, indent=2) + "\n"
            except Exception:
                return None
    return None


def _ensure_reference_file(path: Path, content: str) -> None:
    if not path.exists():
        path.write_text(content, encoding="utf-8")


def _ensure_reference_scaffolding(skill_dir: Path, *, func_name: str, func: Any, meta: SkillMeta) -> None:
    references_dir = skill_dir / "references"
    golden_dir = references_dir / "golden-examples"
    failure_dir = references_dir / "failure-cases"
    references_dir.mkdir(parents=True, exist_ok=True)
    golden_dir.mkdir(parents=True, exist_ok=True)
    failure_dir.mkdir(parents=True, exist_ok=True)

    try:
        signature_text = str(inspect.signature(func))
    except Exception:
        signature_text = "(signature unavailable)"

    generated_schema = _maybe_generate_schema_from_signature(func)
    input_schema_content = generated_schema or _schema_placeholder(signature_text)
    output_schema_content = _schema_placeholder(signature_text)

    if meta.input_schema:
        _ensure_reference_file(references_dir / meta.input_schema, input_schema_content)
    if meta.output_schema:
        _ensure_reference_file(references_dir / meta.output_schema, output_schema_content)

    _ensure_reference_file(
        references_dir / "quality-notes.md",
        f"""# Quality criteria for {meta.name}

8-dimension scoring (darwin.skill compatible):

| Dimension | Max | Current | Notes |
|---|---|---|---|
| Frontmatter completeness | 8 | TODO | |
| Workflow clarity | 15 | TODO | |
| Boundary conditions | 10 | TODO | |
| Checkpoints | 7 | TODO | |
| Instruction specificity | 15 | TODO | |
| Reference paths | 5 | TODO | |
| Architecture | 15 | TODO | |
| Empirical (golden examples pass rate) | 25 | TODO | |
| **TOTAL** | **100** | **TODO** | |

## Baseline established: TODO date
## Last evaluated: TODO date
""",
    )
    _ensure_reference_file(
        references_dir / "version-history.md",
        f"""# Version history for {meta.name}

| Version | Date | Change | Score before | Score after |
|---|---|---|---|---|
| v1 | {_today_iso()} | Initial extraction from registry.py | N/A | TODO baseline |
""",
    )
    _ensure_reference_file(
        golden_dir / "README.md",
        f"""# Golden examples for {meta.name}

Each example is a JSON file with this structure:
{{
  "name": "case-01-short-description",
  "input": {{ ... matches input-schema.json ... }},
  "expected_output_properties": {{
    "schema_compliant": true,
    "must_contain_keys": [...],
    "quality_signals": "free-text description of what good looks like"
  }},
  "notes": "why this case is in the golden set"
}}

Aim for 3-5 examples covering:
- A typical case
- An edge case
- A known-hard case
- (optional) A case the prompt previously failed on
""",
    )
    _ensure_reference_file(
        failure_dir / "README.md",
        f"""# Failure cases for {meta.name}

When this skill produces a wrong/bad output, document it here.
File format: `case-NN-short-description.md`

Each file should contain:
- What input triggered the failure
- What output was produced
- What output was expected
- Hypothesis for the cause
- Whether/how it was fixed (link to commit if applicable)

These cases feed into golden-examples/ once a fix is verified.
""",
    )


def _compute_skill_hash(func: Any) -> str:
    source = inspect.getsource(func).encode("utf-8")
    return hashlib.sha256(source).hexdigest()


def _export_skill(target_dir: Path, *, func_name: str, func: Any, meta: SkillMeta) -> str:
    skill_dir = target_dir / meta.name
    skill_dir.mkdir(parents=True, exist_ok=True)
    _ensure_reference_scaffolding(skill_dir, func_name=func_name, func=func, meta=meta)

    purpose = inspect.getdoc(func) or "(no docstring on registry function - please add one)"
    now_iso = _now_iso()
    markdown = _render_skill_markdown(
        func_name=func_name,
        meta=meta,
        now_iso=now_iso,
        purpose=purpose,
    )
    (skill_dir / "SKILL.md").write_text(markdown, encoding="utf-8")
    skill_hash = _compute_skill_hash(func)
    (skill_dir / ".skill-hash").write_text(skill_hash + "\n", encoding="utf-8")
    return skill_hash


def _check_skill(target_dir: Path, *, func_name: str, func: Any, meta: SkillMeta) -> str | None:
    skill_dir = target_dir / meta.name
    hash_path = skill_dir / ".skill-hash"
    if not hash_path.exists():
        return f"{meta.name}: missing .skill-hash"
    expected = _compute_skill_hash(func)
    current = hash_path.read_text(encoding="utf-8").strip()
    if current != expected:
        return f"{meta.name}: prompt source drift detected"
    return None


def _clean_generated_files(target_dir: Path) -> None:
    if not target_dir.exists():
        return
    for skill_dir in target_dir.iterdir():
        if not skill_dir.is_dir():
            continue
        skill_md = skill_dir / "SKILL.md"
        hash_file = skill_dir / ".skill-hash"
        if skill_md.exists():
            skill_md.unlink()
        if hash_file.exists():
            hash_file.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description="Export decorated prompt functions as Claude skills.")
    parser.add_argument("--target", type=Path, default=DEFAULT_TARGET)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--skill", type=str, default=None)
    parser.add_argument("--clean", action="store_true")
    args = parser.parse_args()

    target_dir: Path = args.target.expanduser()
    if args.clean:
        _clean_generated_files(target_dir)
        print(f"Cleaned generated SKILL.md and .skill-hash files under {target_dir}")
        return 0

    discovered = _discover_skills()
    if args.skill:
        discovered = [item for item in discovered if item[2].name == args.skill]

    if args.check:
        drift_messages = []
        for func_name, func, meta in discovered:
            message = _check_skill(target_dir, func_name=func_name, func=func, meta=meta)
            if message:
                drift_messages.append(message)
        if drift_messages:
            for message in drift_messages:
                print(message)
            return 1
        print("Skill export check passed.")
        return 0

    target_dir.mkdir(parents=True, exist_ok=True)
    for func_name, func, meta in discovered:
        _export_skill(target_dir, func_name=func_name, func=func, meta=meta)
        print(f"Exported {meta.name} -> {target_dir / meta.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
