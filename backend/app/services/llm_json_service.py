import json
import os
import re
from json import JSONDecodeError
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from app.prompts.registry import json_repair_prompts

ROOT_ENV_PATH = Path(__file__).resolve().parents[3] / ".env"

load_dotenv(ROOT_ENV_PATH)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")


def repair_output_to_json_with_openai(
    raw_text: str,
    *,
    schema_keys: Optional[list[str]] = None,
) -> Dict[str, Any]:
    from app.services.llm_executor_service import execute_text_json_task

    if not OPENAI_API_KEY and not ANTHROPIC_API_KEY:
        raise ValueError("No supported LLM API key found for JSON repair")

    keys = schema_keys or [
        "summary",
        "why_it_matters",
        "relevance_to_projects",
        "relevance_to_career",
        "synthesized_insight",
    ]
    system_prompt, user_prompt = json_repair_prompts(raw_text=raw_text, keys=keys)

    parsed, route = execute_text_json_task(
        task_type="structure",
        openai_api_key=OPENAI_API_KEY,
        anthropic_api_key=ANTHROPIC_API_KEY,
        max_tokens=1800,
        temperature=0,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
    )
    return parsed


def parse_model_json(
    raw_output: str,
    *,
    repair_with_openai: bool = False,
    schema_keys: Optional[list[str]] = None,
) -> Dict[str, Any]:
    if not raw_output or not raw_output.strip():
        raise ValueError("Model returned empty content.")

    text = raw_output.strip().lstrip("\ufeff").strip()

    if text.startswith("```"):
        text = re.sub(r"^```json\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"^```\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    text = text.strip()

    try:
        return json.loads(text)
    except JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = text[start : end + 1]
        try:
            return json.loads(candidate)
        except JSONDecodeError:
            pass

    if repair_with_openai:
        return repair_output_to_json_with_openai(text, schema_keys=schema_keys)

    raise ValueError(f"Model did not return valid JSON. Raw output: {raw_output[:500]}")
