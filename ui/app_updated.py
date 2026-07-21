import base64
import json
import os
import re
import sys
from ui.intelligence_blocks import render_intelligence_blocks
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
APP_DIR = PROJECT_ROOT / "app"

if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

try:
    from services.manual_session_service import (
        generate_manual_session_id,
        upload_manual_file_to_s3,
        build_manual_session_payload,
        save_manual_session_to_s3,
        update_manual_latest_sessions,
    )
except ModuleNotFoundError:
    from app.services.manual_session_service import (
        generate_manual_session_id,
        upload_manual_file_to_s3,
        build_manual_session_payload,
        save_manual_session_to_s3,
        update_manual_latest_sessions,
    )

import boto3
import streamlit as st
from typing import Any
from botocore.exceptions import ClientError
from dotenv import load_dotenv
from openai import OpenAI

from intake.processors.cleaner import build_short_summary, clean_text
from intake.scoring.scorer import score_signal
from intake.selector.selector import select_top_signals
from intake.sources.upload_source import build_signal_from_upload
from config import settings
from sources.source_quality import compute_source_quality



client = OpenAI(api_key=settings.openai_api_key)

try:
    import anthropic
except ImportError:
    anthropic = None


# =========================
# Env & Config
# =========================
load_dotenv(PROJECT_ROOT / ".env")

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
S3_BUCKET = os.getenv("S3_BUCKET", "ai-radar-junxiong-data")
MANUAL_S3_BUCKET = S3_BUCKET
MANUAL_AWS_REGION = AWS_REGION

LATEST_DAILY_KEY = "daily/latest/daily_radar.json"
LATEST_SIGNALS_KEY = "signals/latest/signals.json"
LATEST_INSIGHTS_KEY = "insights/latest/insights.json"

BASE_DIR = Path(__file__).resolve().parent.parent
REFLECTIONS_FILE = BASE_DIR / "data" / "output" / "reflections.json"
PERSONAL_CONTEXT_FILE = BASE_DIR / "app" / "context" / "personal_context.json"
MANUAL_UPLOADS_DIR = BASE_DIR / "data" / "manual" / "manual_uploads"
MANUAL_SESSIONS_DIR = BASE_DIR / "data" / "manual" / "manual_sessions"

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DEFAULT_OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-6"

ANTHROPIC_MODEL = os.getenv(
    "ANTHROPIC_MODEL",
    DEFAULT_ANTHROPIC_MODEL
)

ANTHROPIC_MODEL_FALLBACKS = [
    os.getenv("ANTHROPIC_MODEL", "").strip(),
    # Current official model names
    "claude-sonnet-4-6",
    "claude-opus-4-6",
    "claude-sonnet-4-5-20250929",
    "claude-sonnet-4-20250514",
    "claude-haiku-4-5-20251001",
    # Older names kept for backward compatibility with older accounts / rollouts
    "claude-3-7-sonnet-20250219",
    "claude-3-5-sonnet-20241022",
    "claude-3-5-sonnet-20240620",
    "claude-3-5-haiku-20241022",
    "claude-3-haiku-20240307",
]

PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")
DEFAULT_PERPLEXITY_MODEL = os.getenv("PERPLEXITY_MODEL", "sonar-pro")

MODEL_ORDER = ["claude", "chatgpt", "perplexity"]
MODEL_TITLES = {
    "claude": "Claude",
    "chatgpt": "ChatGPT",
    "perplexity": "Perplexity",
}
MODEL_SUBTITLES = {
    "claude": "Writing-focused",
    "chatgpt": "Structured refinement",
    "perplexity": "Research / external context",
}


# =========================
# Page Setup
# =========================
st.set_page_config(
    page_title="AI Radar Workspace",
    layout="wide",
)

st.markdown(
    """
    <style>
    .block-container {
        padding-top: 1rem;
        padding-bottom: 2rem;
        max-width: 96rem;
    }
    .section-title {
        font-size: 1.05rem;
        font-weight: 700;
        margin-bottom: 0.25rem;
    }
    .section-subtitle {
        font-size: 0.86rem;
        opacity: 0.82;
        margin-bottom: 0.8rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# =========================
# S3 Load
# =========================
@st.cache_data(ttl=60)
def load_json_from_s3(bucket: str, key: str, region: str = AWS_REGION):
    s3 = boto3.client("s3", region_name=region)
    try:
        response = s3.get_object(Bucket=bucket, Key=key)
        content = response["Body"].read().decode("utf-8")
        return json.loads(content)
    except ClientError as e:
        st.error(f"Failed to load s3://{bucket}/{key}")
        st.exception(e)
        return None


# =========================
# Normalize Functions (FIX)
# =========================
def normalize_signals(signals_data, daily_radar):
    if not signals_data:
        return []

    if isinstance(signals_data, list):
        return signals_data

    if isinstance(signals_data, dict):
        if isinstance(signals_data.get("signals"), list):
            return signals_data.get("signals", [])
        if isinstance(signals_data.get("items"), list):
            return signals_data.get("items", [])

    return []


def normalize_source_stats(daily_radar, signals):
    if isinstance(daily_radar, dict):
        source_stats = daily_radar.get("source_stats", {})
        if isinstance(source_stats, dict) and source_stats:
            return source_stats

    stats = {}
    for s in signals or []:
        if not isinstance(s, dict):
            continue
        source = (s.get("source") or "unknown").strip() or "unknown"
        if source not in stats:
            stats[source] = {"raw_count": 0, "quality_score": 0}
        stats[source]["raw_count"] += 1
    return stats


def normalize_insights(insights_data, daily_radar):
    if not insights_data:
        return []

    if isinstance(insights_data, list):
        return insights_data

    if isinstance(insights_data, dict):
        if isinstance(insights_data.get("insights"), list):
            return insights_data.get("insights", [])
        if isinstance(insights_data.get("items"), list):
            return insights_data.get("items", [])

    return []


def normalize_trend_summary(daily_radar) -> dict:
    if not isinstance(daily_radar, dict):
        return {}

    trend_summary = daily_radar.get("trend_summary", {})
    if isinstance(trend_summary, dict):
        return trend_summary

    return {}


def get_signal_metric(signal: dict, field: str, default=0.0):
    if not isinstance(signal, dict):
        return default
    value = signal.get(field, default)
    try:
        return float(value)
    except Exception:
        return default


def get_signal_title(signal: dict, fallback_index: int) -> str:
    if not isinstance(signal, dict):
        return f"Signal {fallback_index}"
    title = str(signal.get("title") or "").strip()
    if title:
        return title
    summary = str(signal.get("summary") or "").strip()
    if summary:
        return summary[:80]
    return f"Signal {fallback_index}"


def get_signal_summary(signal: dict) -> str:
    if not isinstance(signal, dict):
        return ""
    summary = str(signal.get("summary") or "").strip()
    if summary:
        return summary
    content = str(signal.get("content") or "").strip()
    return content


def get_quality_badge(signal: dict) -> str:
    if not isinstance(signal, dict):
        return "⚪"
    level = str(signal.get("quality_level") or "").lower().strip()
    if level == "high":
        return "🟢"
    if level == "medium":
        return "🟡"
    if level == "low":
        return "🔴"
    return "⚪"


def build_insight_map(insights: list[dict]) -> dict:
    result = {}
    for item in insights or []:
        if not isinstance(item, dict):
            continue
        title = str(item.get("signal_title") or item.get("title") or "").strip()
        if title:
            result[title] = item
    return result


def build_context_bundle(
    signal_title: str,
    signal_summary: str,
    why_it_matters: str,
    relevance_to_projects: str,
    relevance_to_career: str,
    synthesized_insight: str,
    personal_context: dict,
) -> dict:
    return {
        "signal_title": signal_title,
        "signal_summary": signal_summary,
        "why_it_matters": why_it_matters,
        "relevance_to_projects": relevance_to_projects,
        "relevance_to_career": relevance_to_career,
        "synthesized_insight": synthesized_insight,
        "personal_context": personal_context or {},
    }


def safe_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)

def list_available_anthropic_models(client) -> list[str]:
    """Best effort: ask Anthropic which models this API key can actually use."""
    names: list[str] = []
    try:
        page = client.models.list(limit=100)
        data = getattr(page, "data", None) or []
        for item in data:
            model_id = safe_text(getattr(item, "id", "")).strip()
            if model_id and model_id not in names:
                names.append(model_id)
    except Exception:
        return []
    return names


def get_anthropic_model_candidates(client=None, preferred_model: str | None = None) -> list[str]:
    candidates = []

    for model in [
        preferred_model,
        st.session_state.get("claude_model_name", ""),
        ANTHROPIC_MODEL,
        DEFAULT_ANTHROPIC_MODEL,
        *ANTHROPIC_MODEL_FALLBACKS,
    ]:
        model = safe_text(model).strip()
        if model and model not in candidates:
            candidates.append(model)

    available = list_available_anthropic_models(client) if client is not None else []

    # If the API key can list models, prefer those first because they are authoritative
    if available:
        prioritized = []
        for model in available + candidates:
            model = safe_text(model).strip()
            if model and model not in prioritized:
                prioritized.append(model)
        return prioritized

    return candidates


def is_anthropic_model_not_found_error(error: Exception) -> bool:
    message = safe_text(error).lower()
    return "not_found_error" in message or "error code: 404" in message or "model:" in message and "not found" in message


def join_anthropic_response_text(response) -> str:
    parts = []
    for block in response.content:
        block_text = getattr(block, "text", "")
        if block_text:
            parts.append(block_text)
    return "\n".join(parts).strip()


def call_anthropic_with_fallback(system_prompt: str, messages: list[dict], max_tokens: int, temperature: float | None = None) -> tuple[object | None, str | None, str | None]:
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    attempted_models = []
    last_error = None
    available_models = list_available_anthropic_models(client)

    for model_name in get_anthropic_model_candidates(client=client):
        attempted_models.append(model_name)
        try:
            kwargs = {
                "model": model_name,
                "max_tokens": max_tokens,
                "system": system_prompt,
                "messages": messages,
            }
            if temperature is not None:
                kwargs["temperature"] = temperature

            response = client.messages.create(**kwargs)
            st.session_state["last_successful_claude_model"] = model_name
            return response, model_name, None
        except Exception as e:
            last_error = e
            if is_anthropic_model_not_found_error(e):
                continue
            return None, None, f"Claude error: {e}"

    attempted = ", ".join(attempted_models) if attempted_models else "(none)"
    if available_models:
        available_text = ", ".join(available_models)
        return None, None, (
            f"Claude error: no available Anthropic model was found. "
            f"Tried: {attempted}. API key can see these models: {available_text}. Last error: {last_error}"
        )
    return None, None, f"Claude error: no available Anthropic model was found. Tried: {attempted}. Last error: {last_error}"


def empty_decision_payload() -> dict:
    return {
        "decision_summary": "",
        "recommendations": []
    }


def normalize_decision_payload(data: dict) -> dict:
    if not isinstance(data, dict):
        return empty_decision_payload()

    decision_summary = data.get("decision_summary", "")
    recommendations = data.get("recommendations", [])

    if not isinstance(recommendations, list):
        recommendations = []

    normalized_recommendations = []
    for item in recommendations[:3]:
        if not isinstance(item, dict):
            continue

        normalized_recommendations.append({
            "type": item.get("type", "action_suggestion"),
            "title": item.get("title", "Untitled recommendation"),
            "action": item.get("action", ""),
            "priority": item.get("priority", "medium"),
            "reason": item.get("reason", "")
        })

    return {
        "decision_summary": str(decision_summary),
        "recommendations": normalized_recommendations
    }

def get_mock_decision_payload() -> dict:
    return normalize_decision_payload({
        "decision_summary": "Recent signals are becoming more concentrated around agent systems, memory, and tool orchestration. The system should now shift from passive observation to more selective interpretation and action.",
        "recommendations": [
            {
                "type": "source_strategy",
                "title": "Reduce repetitive sources",
                "action": "Lower the attention on sources that repeat similar ideas without adding much novelty.",
                "priority": "high",
                "reason": "Signal volume is growing, but not all sources are contributing new insight."
            },
            {
                "type": "topic_focus",
                "title": "Track agent infrastructure more closely",
                "action": "Pay more attention to memory systems, tool routing, and execution layer topics in upcoming runs.",
                "priority": "high",
                "reason": "These themes are showing stronger continuity and are highly relevant to your current projects."
            },
            {
                "type": "action_suggestion",
                "title": "Write one reflection note",
                "action": "Turn this trend cluster into a short reflection connecting AI Radar with GLAP as parallel decision systems.",
                "priority": "medium",
                "reason": "This trend has strong conceptual relevance and can be converted into a useful personal insight."
            }
        ]
    })

def format_history_overview_for_llm(history_overview) -> str:
    if not history_overview:
        return "No history overview available."

    lines = ["Recent history overview:"]

    if isinstance(history_overview, list):
        for item in history_overview[:7]:
            if isinstance(item, dict):
                date = item.get("date", "unknown_date")
                signal_count = item.get("signal_count", "n/a")
                insight_count = item.get("insight_count", "n/a")
                lines.append(
                    f"- {date}: signal_count={signal_count}, insight_count={insight_count}"
                )
            else:
                lines.append(f"- {str(item)}")
    else:
        lines.append(str(history_overview))

    return "\n".join(lines)

def generate_decision_recommendation(history_overview, trend_insight: str) -> dict:
    try:
        formatted_history = format_history_overview_for_llm(history_overview)
        system_prompt = """
You are the decision layer of a personalized AI signal intelligence system.

Your job is to read the trend insight and recommend what the user should do next.

Return valid JSON only with this structure:
{
  "decision_summary": "...",
  "recommendations": [
    {
      "type": "source_strategy",
      "title": "...",
      "action": "...",
      "priority": "high",
      "reason": "..."
    },
    {
      "type": "topic_focus",
      "title": "...",
      "action": "...",
      "priority": "medium",
      "reason": "..."
    },
    {
      "type": "action_suggestion",
      "title": "...",
      "action": "...",
      "priority": "medium",
      "reason": "..."
    }
  ]
}

Rules:
- Return exactly 3 recommendations
- recommendation types must be:
  - source_strategy
  - topic_focus
  - action_suggestion
- priority must be one of:
  - high
  - medium
  - low
- Do not return markdown
- Do not return code fences
- Do not return any explanation outside JSON
""".strip()

        user_prompt = f"""
Here is the recent history overview:

{formatted_history}

Here is the current trend insight:

{trend_insight}

Based on the history overview and trend insight, generate:
1. one decision summary
2. exactly 3 recommendations

Focus on:
- source strategy
- topic focus
- action suggestion
""".strip()

        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            temperature=0.3,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )

        content = response.choices[0].message.content
        data = json.loads(content)

        return normalize_decision_payload(data)

    except Exception as e:
        return {
            "decision_summary": f"Failed to generate decision recommendation: {str(e)}",
            "recommendations": []
        }

@st.cache_data(ttl=60)
def load_history_overview(bucket: str, dates: list[str], max_days: int = 7) -> list[dict]:
    rows = []
    dates_to_load = dates[:max_days]

    for d in dates_to_load:
        key = f"daily/{d}/daily_radar.json"
        data = load_json_from_s3(bucket, key)

        if not isinstance(data, dict):
            continue

        source_stats = data.get("source_stats", {})
        avg_quality = 0.0
        if isinstance(source_stats, dict) and source_stats:
            scores = [
                stats.get("quality_score", 0)
                for stats in source_stats.values()
                if isinstance(stats, dict)
            ]
            if scores:
                avg_quality = round(sum(scores) / len(scores), 2)

        top_sources = []
        if isinstance(source_stats, dict):
            ranked_sources = sorted(
                source_stats.items(),
                key=lambda x: x[1].get("raw_count", 0),
                reverse=True,
            )
            top_sources = [name for name, _ in ranked_sources[:3]]

        rows.append(
            {
                "date": data.get("date", d),
                "signal_count": data.get("signal_count", 0),
                "insight_count": data.get("insight_count", 0),
                "avg_quality_score": avg_quality,
                "top_sources": ", ".join(top_sources),
            }
        )

    return rows


@st.cache_data(ttl=60)
def list_available_dates(bucket: str, prefix: str = "daily/", region: str = AWS_REGION) -> list[str]:
    s3 = boto3.client("s3", region_name=region)
    try:
        response = s3.list_objects_v2(
            Bucket=bucket,
            Prefix=prefix,
            Delimiter="/",
        )

        dates = []
        for item in response.get("CommonPrefixes", []):
            folder = item.get("Prefix", "")
            parts = folder.strip("/").split("/")
            if len(parts) == 2:
                date_part = parts[1]
                if date_part != "latest":
                    dates.append(date_part)

        dates.sort(reverse=True)
        return dates

    except Exception as e:
        st.error("Failed to list available dates from S3.")
        st.exception(e)
        return []


def build_s3_keys(selected_date: str) -> tuple[str, str, str]:
    if selected_date == "latest":
        return (
            "daily/latest/daily_radar.json",
            "signals/latest/signals.json",
            "insights/latest/insights.json",
        )

    return (
        f"daily/{selected_date}/daily_radar.json",
        f"signals/{selected_date}/signals.json",
        f"insights/{selected_date}/insights.json",
    )


# =========================
# Reflection Storage
# =========================
def ensure_reflections_file() -> None:
    REFLECTIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not REFLECTIONS_FILE.exists():
        with open(REFLECTIONS_FILE, "w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False, indent=2)


def load_reflections() -> list[dict]:
    ensure_reflections_file()
    try:
        with open(REFLECTIONS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def compute_preference_profile(reflections: list[dict]) -> dict:
    category_counts = {}
    source_counts = {}
    author_counts = {}
    reflection_lengths = []

    linkedin_category_counts = {}
    linkedin_source_counts = {}

    for item in reflections:
        category = safe_text(item.get("category", "")).strip()
        source = safe_text(item.get("source", "")).strip()
        author = safe_text(item.get("author", "")).strip()
        reflection_length = item.get("reflection_length", 0)
        used_for_linkedin = item.get("used_for_linkedin", False)

        if category:
            category_counts[category] = category_counts.get(category, 0) + 1
        if source:
            source_counts[source] = source_counts.get(source, 0) + 1
        if author:
            author_counts[author] = author_counts.get(author, 0) + 1

        if isinstance(reflection_length, int) and reflection_length > 0:
            reflection_lengths.append(reflection_length)

        if used_for_linkedin:
            if category:
                linkedin_category_counts[category] = linkedin_category_counts.get(category, 0) + 1
            if source:
                linkedin_source_counts[source] = linkedin_source_counts.get(source, 0) + 1

    top_categories = sorted(category_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    top_sources = sorted(source_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    top_authors = sorted(author_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    top_linkedin_categories = sorted(linkedin_category_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    top_linkedin_sources = sorted(linkedin_source_counts.items(), key=lambda x: x[1], reverse=True)[:5]

    avg_reflection_length = (
        round(sum(reflection_lengths) / len(reflection_lengths), 1)
        if reflection_lengths else 0
    )

    linkedin_used_count = sum(
        1 for item in reflections if item.get("used_for_linkedin", False)
    )

    return {
        "top_categories": top_categories,
        "top_sources": top_sources,
        "top_authors": top_authors,
        "top_linkedin_categories": top_linkedin_categories,
        "top_linkedin_sources": top_linkedin_sources,
        "avg_reflection_length": avg_reflection_length,
        "reflection_count": len(reflections),
        "linkedin_used_count": linkedin_used_count,
    }


def save_reflection(
    signal_title: str,
    reflection: str,
    source: str = "",
    author: str = "",
    category: str = "",
    used_for_linkedin: bool = False,
    tags: list[str] | None = None,
) -> None:
    ensure_reflections_file()
    reflections = load_reflections()

    now = datetime.now(timezone.utc)
    item = {
        "created_at": now.isoformat(),
        "date": now.strftime("%Y-%m-%d"),
        "signal_title": signal_title,
        "source": source,
        "author": author,
        "category": category,
        "used_for_linkedin": used_for_linkedin,
        "reflection_length": len(reflection.strip()),
        "reflection": reflection.strip(),
        "tags": tags or [],
    }

    reflections.insert(0, item)

    with open(REFLECTIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(reflections, f, ensure_ascii=False, indent=2)


def mark_reflection_used_for_linkedin(signal_title: str) -> bool:
    ensure_reflections_file()
    reflections = load_reflections()
    updated = False

    for item in reflections:
        if safe_text(item.get("signal_title", "")).strip() == signal_title.strip():
            item["used_for_linkedin"] = True
            updated = True
            break

    if updated:
        with open(REFLECTIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(reflections, f, ensure_ascii=False, indent=2)

    return updated


def get_latest_saved_reflection_for_signal(signal_title: str) -> str:
    reflections = load_reflections()
    for item in reflections:
        if safe_text(item.get("signal_title", "")).strip() == signal_title.strip():
            return safe_text(item.get("reflection", "")).strip()
    return ""


# =========================
# Personal Context
# =========================
def load_personal_context() -> dict:
    if not PERSONAL_CONTEXT_FILE.exists():
        return {}
    try:
        with open(PERSONAL_CONTEXT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def format_personal_context(context: dict) -> str:
    if not context:
        return "No personal context available."
    return json.dumps(context, ensure_ascii=False, indent=2)



# =========================
# Manual Vision Sessions
# =========================
def ensure_manual_session_dirs() -> None:
    """
    Legacy local dirs are kept only for backward compatibility.
    New sessions are stored in S3.
    """
    MANUAL_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    MANUAL_SESSIONS_DIR.mkdir(parents=True, exist_ok=True)


def safe_slug(value: str) -> str:
    value = safe_text(value).strip().lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = value.strip("_")
    return value or "session"


def build_manual_session_id(session_title: str = "") -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    slug = safe_slug(session_title) if session_title else "manual_vision"
    return f"{ts}_{slug}"


def guess_media_type(filename: str) -> str:
    name = safe_text(filename).lower()
    if name.endswith(".png"):
        return "image/png"
    if name.endswith(".webp"):
        return "image/webp"
    return "image/jpeg"


def prepare_uploaded_files_for_processing(uploaded_files: list) -> list[dict]:
    prepared = []
    for uploaded_file in uploaded_files or []:
        try:
            file_bytes = uploaded_file.getvalue()
        except Exception:
            file_bytes = b""

        prepared.append({
            "file_name": safe_text(getattr(uploaded_file, "name", "uploaded_file")).strip() or "uploaded_file",
            "file_bytes": file_bytes,
            "uploaded_file": uploaded_file,
        })
    return prepared


def save_manual_session_to_s3_from_result(
    session_title: str,
    instruction: str,
    prepared_files: list[dict],
    personal_context_snapshot: dict,
    summary: str,
    insights_for_me: str,
    project_takeaways: list[str],
    career_takeaways: list[str],
    summary_zh: str = "",
    insights_for_me_zh: str = "",
    project_takeaways_zh: list[str] | None = None,
    career_takeaways_zh: list[str] | None = None,
    reflection: str = "",
    extracted_signals: list[dict] | None = None,
    raw_response: str = "",
    status: str = "completed",
) -> tuple[str, str, list[dict]]:
    session_id = generate_manual_session_id()

    uploaded_files_meta = []
    for file_item in prepared_files or []:
        uploaded_file_meta = upload_manual_file_to_s3(
            bucket_name=MANUAL_S3_BUCKET,
            session_id=session_id,
            file_name=file_item.get("file_name", "uploaded_file"),
            file_bytes=file_item.get("file_bytes", b""),
            aws_region=MANUAL_AWS_REGION,
        )
        uploaded_files_meta.append(uploaded_file_meta)

    session_payload = build_manual_session_payload(
        session_id=session_id,
        title=session_title or f"Manual analysis - {session_id}",
        instruction=instruction,
        uploaded_files=uploaded_files_meta,
        personal_context_snapshot=personal_context_snapshot or {},
        summary=summary,
        insights_for_me=insights_for_me,
        project_takeaways="\n".join(project_takeaways or []),
        career_takeaways="\n".join(career_takeaways or []),
        reflection=reflection,
        extracted_signals=extracted_signals or [],
        raw_response=raw_response,
        status=status,
    )

    session_payload["session_title"] = session_title or "Manual vision session"
    session_payload["summary_zh"] = summary_zh
    session_payload["insights_for_me_zh"] = insights_for_me_zh
    session_payload["project_takeaways_zh"] = project_takeaways_zh or []
    session_payload["career_takeaways_zh"] = career_takeaways_zh or []
    session_payload["file_count"] = len(uploaded_files_meta)
    session_payload["images"] = [
        item["s3_key"] for item in uploaded_files_meta
        if safe_text(item.get("file_type", "")).lower() in {"png", "jpg", "jpeg", "webp"}
    ]
    session_payload["files"] = [item["s3_key"] for item in uploaded_files_meta]

    session_s3_key = save_manual_session_to_s3(
        bucket_name=MANUAL_S3_BUCKET,
        session_payload=session_payload,
        aws_region=MANUAL_AWS_REGION,
    )

    update_manual_latest_sessions(
        bucket_name=MANUAL_S3_BUCKET,
        session_payload=session_payload,
        aws_region=MANUAL_AWS_REGION,
        max_sessions=20,
    )

    return session_id, session_s3_key, uploaded_files_meta


def load_manual_sessions() -> list[dict]:
    """
    Prefer manual_latest/latest_sessions.json for ordering, then read each full session.json.
    Fallback to scanning manual_sessions/ when latest index is missing.
    """
    s3 = boto3.client("s3", region_name=MANUAL_AWS_REGION)
    sessions = []

    latest_index = load_json_from_s3(
        MANUAL_S3_BUCKET,
        "manual_latest/latest_sessions.json",
        region=MANUAL_AWS_REGION,
    ) or {}
    latest_items = latest_index.get("latest_sessions", []) if isinstance(latest_index, dict) else []

    if isinstance(latest_items, list) and latest_items:
        for item in latest_items:
            session_id = safe_text((item or {}).get("session_id", "")).strip()
            if not session_id:
                continue
            key = f"manual_sessions/{session_id}/session.json"
            try:
                response = s3.get_object(Bucket=MANUAL_S3_BUCKET, Key=key)
                content = response["Body"].read().decode("utf-8")
                data = json.loads(content)
                if isinstance(data, dict):
                    data["_s3_key"] = key
                    sessions.append(data)
            except Exception:
                continue
        if sessions:
            return sessions

    try:
        paginator = s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=MANUAL_S3_BUCKET, Prefix="manual_sessions/"):
            for obj in page.get("Contents", []):
                key = obj.get("Key", "")
                if not key.endswith("/session.json"):
                    continue
                try:
                    response = s3.get_object(Bucket=MANUAL_S3_BUCKET, Key=key)
                    content = response["Body"].read().decode("utf-8")
                    data = json.loads(content)
                    if isinstance(data, dict):
                        data["_s3_key"] = key
                        sessions.append(data)
                except Exception:
                    continue
    except Exception:
        return []

    sessions.sort(key=lambda x: safe_text(x.get("created_at", "")), reverse=True)
    return sessions


def build_manual_result_from_saved_session(session: dict) -> tuple[dict, dict]:
    """Convert a saved manual session back into the runtime result structures used by the UI."""
    project_takeaways = normalize_saved_takeaways(session.get("project_takeaways", []))
    career_takeaways = normalize_saved_takeaways(session.get("career_takeaways", []))
    project_takeaways_zh = normalize_saved_takeaways(session.get("project_takeaways_zh", []))
    career_takeaways_zh = normalize_saved_takeaways(session.get("career_takeaways_zh", []))

    result = {
        "summary": safe_text(session.get("summary", "")),
        "insights_for_me": safe_text(session.get("insights_for_me", "")),
        "project_takeaways": project_takeaways,
        "career_takeaways": career_takeaways,
        "raw_response": safe_text(session.get("raw_response", "")),
        "parse_status": "ok",
    }

    result_zh = {
        "summary_zh": safe_text(session.get("summary_zh", "")) or safe_text(session.get("summary", "")),
        "insights_for_me_zh": safe_text(session.get("insights_for_me_zh", "")) or safe_text(session.get("insights_for_me", "")),
        "project_takeaways_zh": project_takeaways_zh or project_takeaways,
        "career_takeaways_zh": career_takeaways_zh or career_takeaways,
    }

    return result, result_zh


def save_uploaded_files_to_session(session_id: str, uploaded_files: list) -> list[str]:
    """
    Legacy local helper kept for backward compatibility.
    New flow uses save_manual_session_to_s3_from_result instead.
    """
    ensure_manual_session_dirs()
    session_dir = MANUAL_UPLOADS_DIR / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    saved_paths = []
    for idx, uploaded_file in enumerate(uploaded_files, start=1):
        suffix = Path(uploaded_file.name).suffix or ".png"
        file_path = session_dir / f"upload_{idx}{suffix}"
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getvalue())
        saved_paths.append(str(file_path))
    return saved_paths


def save_manual_session(session_data: dict) -> Path:
    """
    Legacy local helper kept for backward compatibility.
    """
    ensure_manual_session_dirs()
    session_id = safe_text(session_data.get("session_id", "")).strip()
    if not session_id:
        session_id = build_manual_session_id()
        session_data["session_id"] = session_id

    path = MANUAL_SESSIONS_DIR / f"{session_id}.json"
    path.write_text(json.dumps(session_data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def parse_manual_vision_json(raw_text: str) -> dict:
    default = {
        "summary": "",
        "insights_for_me": "",
        "project_takeaways": [],
        "career_takeaways": [],
        "raw_response": raw_text or "",
        "parse_status": "empty",
    }

    if not raw_text or not raw_text.strip():
        return default

    text = raw_text.strip()

    # Remove markdown fences if Claude wrapped JSON in ```json ... ```
    if text.startswith("```"):
        if text.startswith("```json"):
            text = text[len("```json"):].strip()
        else:
            text = text[3:].strip()
        if text.endswith("```"):
            text = text[:-3].strip()

    data = None

    try:
        data = json.loads(text)
    except Exception:
        data = None

    if data is None:
        json_start = text.find("{")
        json_end = text.rfind("}")
        if json_start != -1 and json_end != -1 and json_end > json_start:
            candidate = text[json_start:json_end + 1]
            try:
                data = json.loads(candidate)
            except Exception:
                data = None

    if not isinstance(data, dict):
        return {
            **default,
            "parse_status": "failed",
        }

    def normalize_list(value):
        if isinstance(value, list):
            return [safe_text(x).strip() for x in value if safe_text(x).strip()]
        if isinstance(value, str) and value.strip():
            lines = []
            for line in value.splitlines():
                cleaned = line.strip().lstrip("-•").strip()
                if cleaned:
                    lines.append(cleaned)
            return lines if lines else [value.strip()]
        return []

    result = {
        "summary": safe_text(data.get("summary", "")).strip(),
        "insights_for_me": safe_text(data.get("insights_for_me", "")).strip(),
        "project_takeaways": normalize_list(data.get("project_takeaways", [])),
        "career_takeaways": normalize_list(data.get("career_takeaways", [])),
        "raw_response": raw_text,
        "parse_status": "ok",
    }

    if not result["summary"]:
        result["summary"] = safe_text(
            data.get("image_summary", "") or data.get("summary_for_images", "")
        ).strip()

    if not result["insights_for_me"]:
        result["insights_for_me"] = safe_text(
            data.get("insight_for_me", "") or data.get("personal_insight", "")
        ).strip()

    if not result["project_takeaways"]:
        result["project_takeaways"] = normalize_list(
            data.get("key_takeaways_for_projects", []) or data.get("projects_takeaways", [])
        )

    if not result["career_takeaways"]:
        result["career_takeaways"] = normalize_list(
            data.get("key_takeaways_for_career", []) or data.get("career_and_skill_takeaways", [])
        )

    return result

def build_manual_vision_system_prompt(personal_context: dict, user_instruction: str = "") -> str:
    return f"""
You are an AI assistant helping analyze images for a specific user.

=====================
USER PERSONAL CONTEXT (MUST USE)
=====================
{json.dumps(personal_context, indent=2, ensure_ascii=False)}

IMPORTANT:
- You MUST use this personal context when generating insights
- Do NOT generate generic insights
- All "insights_for_me" must be SPECIFIC to this user's background, projects, and goals

=====================
TASK
=====================

The user has uploaded multiple images.

You need to:

1. Understand and summarize what these images are about
2. Generate personalized insights BASED ON the user's context
3. Extract takeaways for:
   - the user's projects
   - the user's career and skill development

User additional instruction:
{user_instruction}

=====================
OUTPUT FORMAT (STRICT JSON ONLY)
=====================

{{
  "summary": "...",

  "insights_for_me": "... (must reference user's projects / background / goals)",

  "project_takeaways": [
    "...",
    "..."
  ],

  "career_takeaways": [
    "...",
    "..."
  ]
}}

RULES:
- Do NOT output anything outside JSON
- Do NOT include markdown
- Return the JSON content in English
- Be concrete and specific
"""


def analyze_images_with_claude(uploaded_files: list, personal_context: dict, user_instruction: str = "") -> dict:
    if anthropic is None:
        return {
            "error": "Claude error: anthropic package not installed. Run: pip install anthropic"
        }

    if not ANTHROPIC_API_KEY:
        return {
            "error": "Claude error: ANTHROPIC_API_KEY not found."
        }

    if not uploaded_files:
        return {"error": "No images uploaded."}

    content_blocks: list[dict[str, Any]] = []
    for uploaded_file in uploaded_files[:12]:
        media_type = guess_media_type(uploaded_file.name)
        content_blocks.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": base64.b64encode(uploaded_file.getvalue()).decode("utf-8"),
                },
            }
        )

    instruction = f"""
Please analyze these uploaded images as one batch.

Extra user instruction:
{user_instruction or "Use the default AI Radar interpretation framework."}
""".strip()

    content_blocks.append({"type": "text", "text": instruction})

    try:
        response, used_model, error_message = call_anthropic_with_fallback(
            system_prompt=build_manual_vision_system_prompt(personal_context, user_instruction),
            messages=[{"role": "user", "content": content_blocks}],
            max_tokens=2200,
            temperature=0,
        )

        if error_message:
            return {"error": error_message}

        if response is None:
            return {"error": "Claude error: empty response object."}

        raw_text = join_anthropic_response_text(response)

        if not raw_text:
            return {
                "error": "Claude returned empty content.",
                "raw_response": "",
                "parse_status": "empty_response",
                "used_model": used_model,
            }

        parsed = parse_manual_vision_json(raw_text)

        if parsed.get("parse_status") != "ok":
            parsed = {
                "summary": raw_text[:3000],
                "insights_for_me": "",
                "project_takeaways": [],
                "career_takeaways": [],
                "raw_response": raw_text,
                "parse_status": "raw_fallback",
                "used_model": used_model,
            }

        all_empty = (
            not safe_text(parsed.get("summary", "")).strip()
            and not safe_text(parsed.get("insights_for_me", "")).strip()
            and not (parsed.get("project_takeaways", []) or [])
            and not (parsed.get("career_takeaways", []) or [])
        )

        if all_empty:
            parsed = {
                "summary": raw_text[:3000],
                "insights_for_me": "",
                "project_takeaways": [],
                "career_takeaways": [],
                "raw_response": raw_text,
                "parse_status": "empty_fields_fallback",
                "used_model": used_model,
            }

        parsed["raw_response"] = raw_text
        if used_model:
            parsed["used_model"] = used_model
        return parsed
    except Exception as e:
        return {"error": f"Claude error: {e}"}

def format_takeaways_list(items: list[str]) -> str:
    if not items:
        return "-"
    return "\n".join([f"- {safe_text(item)}" for item in items if safe_text(item).strip()])

def translate_text(text: str, target_language: str = "Chinese") -> str:
    text = safe_text(text).strip()
    if not text:
        return ""

    try:
        response = client.chat.completions.create(
            model=DEFAULT_OPENAI_MODEL,
            temperature=0.1,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a professional translator. "
                        f"Translate the user's text into {target_language}. "
                        "Keep the meaning precise and natural. "
                        "Return only the translated text."
                    ),
                },
                {"role": "user", "content": text},
            ],
        )
        return safe_text(response.choices[0].message.content).strip()
    except Exception:
        return text


def translate_list(items: list[str], target_language: str = "Chinese") -> list[str]:
    return [translate_text(item, target_language=target_language) for item in items if safe_text(item).strip()]


def translate_manual_result_for_display(result: dict) -> dict:
    if not isinstance(result, dict):
        return {
            "summary_zh": "",
            "insights_for_me_zh": "",
            "project_takeaways_zh": [],
            "career_takeaways_zh": [],
        }

    summary_src = safe_text(result.get("summary", "")).strip()
    insight_src = safe_text(result.get("insights_for_me", "")).strip()
    project_src = result.get("project_takeaways", []) or []
    career_src = result.get("career_takeaways", []) or []

    summary_zh = translate_text(summary_src, target_language="Chinese") if summary_src else ""
    insights_for_me_zh = translate_text(insight_src, target_language="Chinese") if insight_src else ""
    project_takeaways_zh = translate_list(project_src, target_language="Chinese") if project_src else []
    career_takeaways_zh = translate_list(career_src, target_language="Chinese") if career_src else []

    return {
        "summary_zh": summary_zh or summary_src,
        "insights_for_me_zh": insights_for_me_zh or insight_src,
        "project_takeaways_zh": project_takeaways_zh or project_src,
        "career_takeaways_zh": career_takeaways_zh or career_src,
    }


def translate_manual_result_back_to_english(summary_zh: str, insights_for_me_zh: str, project_takeaways_zh: list[str], career_takeaways_zh: list[str]) -> dict:
    return {
        "summary": translate_text(summary_zh, target_language="English"),
        "insights_for_me": translate_text(insights_for_me_zh, target_language="English"),
        "project_takeaways": [translate_text(x, target_language="English") for x in project_takeaways_zh if safe_text(x).strip()],
        "career_takeaways": [translate_text(x, target_language="English") for x in career_takeaways_zh if safe_text(x).strip()],
    }


def normalize_uploaded_files(files) -> list:
    return files[:12] if files else []


def split_uploaded_items(files: list) -> tuple[list, list]:
    images = []
    docs = []
    for f in files or []:
        name = safe_text(getattr(f, "name", "")).lower()
        if name.endswith((".png", ".jpg", ".jpeg", ".webp")):
            images.append(f)
        else:
            docs.append(f)
    return images, docs


def render_uploaded_file_list(title: str, files: list):
    st.markdown(f"**{title}**")
    if not files:
        st.info("No files available.")
        return

    for idx, f in enumerate(files, start=1):
        if isinstance(f, dict):
            filename = safe_text(f.get("file_name", "")).strip() or f"File {idx}"
            size_bytes = f.get("size", 0) or 0
        elif isinstance(f, str):
            filename = Path(f).name or f"File {idx}"
            size_bytes = 0
        else:
            filename = safe_text(getattr(f, "name", f"File {idx}"))
            size_bytes = getattr(f, "size", 0) or 0

        size_kb = round(size_bytes / 1024, 1) if size_bytes else 0
        suffix = f" ({size_kb} KB)" if size_kb else ""
        st.write(f"{idx}. {filename}{suffix}")


def read_uploaded_document_text(uploaded_file) -> str:
    name = safe_text(getattr(uploaded_file, "name", "")).lower()
    try:
        data = uploaded_file.getvalue()
    except Exception:
        return ""

    try:
        if name.endswith((".txt", ".md", ".json", ".csv")):
            return data.decode("utf-8", errors="ignore")

        if name.endswith(".pdf"):
            try:
                from PyPDF2 import PdfReader
                import io
                reader = PdfReader(io.BytesIO(data))
                pages = []
                for page in reader.pages:
                    try:
                        pages.append(page.extract_text() or "")
                    except Exception:
                        continue
                return "\n\n".join([p for p in pages if p.strip()])
            except Exception as e:
                return f"[PDF parse error] {e}"
    except Exception as e:
        return f"[File read error] {e}"

    return ""

def build_signals_from_uploaded_docs(uploaded_files: list) -> list:
    signals = []

    for f in uploaded_files[:12]:
        text = read_uploaded_document_text(f)

        if not safe_text(text).strip():
            continue

        signal = build_signal_from_upload(
            file_name=getattr(f, "name", "uploaded_file"),
            content=text,
            source_type="upload",
            source="manual_upload",
        )
        signals.append(signal)

    return signals

def run_pipeline_on_signals(signals: list) -> list:
    cleaned_signals = []

    for signal in signals:
        signal.clean_text = clean_text(signal.raw_text)
        signal.summary = build_short_summary(signal.clean_text, max_chars=100)
        cleaned_signals.append(signal)

    scored_signals = []
    for signal in cleaned_signals:
        scored = score_signal(signal)
        scored_signals.append(scored)

    curated_signals = select_top_signals(
        scored_signals,
        top_n=min(5, len(scored_signals))
    )

    return curated_signals

def analyze_uploaded_files_with_openai(uploaded_files: list, personal_context: dict, user_instruction: str = "") -> dict:
    if not OPENAI_API_KEY:
        return {"error": "OpenAI error: OPENAI_API_KEY not found."}

    docs = []
    for f in uploaded_files[:12]:
        text = read_uploaded_document_text(f)
        if text.strip():
            docs.append({"name": getattr(f, "name", "uploaded_file"), "text": text[:12000]})

    if not docs:
        return {"error": "No readable file content found. Supported text extraction currently works best for txt / md / json / csv / pdf."}

    documents_text = "\n\n".join(
        [f"FILE: {d['name']}\nCONTENT:\n{d['text']}" for d in docs]
    )

    system_prompt = f"""
You are an AI assistant helping analyze uploaded files for a specific user.

USER PERSONAL CONTEXT:
{json.dumps(personal_context, indent=2, ensure_ascii=False)}

Return valid JSON only with this structure:
{{
  "summary": "...",
  "insights_for_me": "...",
  "project_takeaways": ["...", "..."],
  "career_takeaways": ["...", "..."]
}}

Rules:
- Use the user's personal context
- Do not output markdown
- Keep output concrete
- Return JSON only
""".strip()

    user_prompt = f"""
Analyze these uploaded files as one batch.

Extra user instruction:
{user_instruction or 'Use the default AI Radar interpretation framework.'}

Uploaded file contents:
{documents_text}
""".strip()

    try:
        response = client.chat.completions.create(
            model=st.session_state.get("chatgpt_model_name", DEFAULT_OPENAI_MODEL),
            temperature=0.2,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        raw_text = safe_text(response.choices[0].message.content).strip()
        parsed = parse_manual_vision_json(raw_text)
        parsed["raw_response"] = raw_text
        parsed["used_model"] = st.session_state.get("chatgpt_model_name", DEFAULT_OPENAI_MODEL)
        parsed["input_type"] = "file"
        return parsed
    except Exception as e:
        return {"error": f"OpenAI file analysis error: {e}"}


def load_s3_object_bytes(s3_key: str, bucket_name: str = "ai-radar-junxiong-data", aws_region: str = "us-east-1"):
    """Read object bytes from S3 by key. Return bytes or None."""
    try:
        s3_client = boto3.client("s3", region_name=aws_region)
        obj = s3_client.get_object(Bucket=bucket_name, Key=s3_key)
        return obj["Body"].read()
    except Exception as e:
        st.warning(f"Failed to load from S3: {s3_key} | {e}")
        return None


def is_s3_manual_key(value) -> bool:
    return isinstance(value, str) and value.startswith("manual_uploads/")


def normalize_saved_takeaways(value) -> list[str]:
    if isinstance(value, list):
        return [safe_text(v).strip() for v in value if safe_text(v).strip()]
    if isinstance(value, str):
        items = []
        for line in value.splitlines():
            cleaned = safe_text(line).strip().lstrip("-•").strip()
            if cleaned:
                items.append(cleaned)
        return items
    return []


def render_gallery(title: str, images: list, state_prefix: str, is_uploaded: bool = True):
    st.markdown(f"**{title}**")

    if not images:
        st.info("No images available.")
        return

    def _render_single_image(img, fallback_index: int):
        if is_uploaded:
            caption = getattr(img, "name", f"Image {fallback_index}")
            st.image(img, caption=caption, use_container_width=True)
            return

        if isinstance(img, dict):
            s3_key = safe_text(img.get("s3_key", "")).strip()
            caption = safe_text(img.get("file_name", "")).strip() or Path(s3_key).name or f"Image {fallback_index}"
            if s3_key:
                image_bytes = load_s3_object_bytes(s3_key)
                if image_bytes:
                    st.image(image_bytes, caption=caption, use_container_width=True)
                else:
                    st.caption(f"Unable to load: {caption}")
            else:
                st.caption(f"Unable to load: {caption}")
            return

        if is_s3_manual_key(img):
            s3_key = str(img)
            image_bytes = load_s3_object_bytes(s3_key)
            caption = Path(s3_key).name or f"Image {fallback_index}"
            if image_bytes:
                st.image(image_bytes, caption=caption, use_container_width=True)
            else:
                st.caption(f"Unable to load: {caption}")
            return

        caption = Path(str(img)).name or f"Image {fallback_index}"
        st.image(str(img), caption=caption, use_container_width=True)

    thumb_cols = st.columns(3)
    for idx, img in enumerate(images):
        with thumb_cols[idx % 3]:
            _render_single_image(img, idx + 1)

    if not is_uploaded:
        return

    st.markdown("**大图查看**")
    options = list(range(1, len(images) + 1))
    selected_num = st.selectbox(
        "选择查看图片",
        options,
        index=0,
        key=f"{state_prefix}_viewer_select",
        label_visibility="collapsed",
    )

    selected = images[selected_num - 1]
    st.caption(f"{selected_num} / {len(images)}")
    _render_single_image(selected, selected_num)

def render_scroll_text_box(title: str, content: str, height: int = 220):
    st.markdown(f"**{title}**")
    box = st.container(height=height, border=True)
    with box:
        if safe_text(content).strip():
            st.write(content)
        else:
            st.caption("No content generated yet.")

def generate_trend_insight(history_overview: list[dict]) -> str:
    if not history_overview:
        return "No history data available."

    rows = sorted(history_overview, key=lambda x: x.get("date", ""))
    first = rows[0]
    last = rows[-1]

    first_signals = first.get("signal_count", 0)
    last_signals = last.get("signal_count", 0)

    first_insights = first.get("insight_count", 0)
    last_insights = last.get("insight_count", 0)

    first_quality = first.get("avg_quality_score", 0)
    last_quality = last.get("avg_quality_score", 0)

    quality_direction = "improved"
    if last_quality < first_quality:
        quality_direction = "declined"
    elif last_quality == first_quality:
        quality_direction = "stayed flat"

    latest_top_sources = last.get("top_sources", "")

    lines = [
        f"Over the last {len(rows)} tracked days, signal volume moved from {first_signals} to {last_signals}.",
        f"Insight volume moved from {first_insights} to {last_insights}.",
        f"Average source quality {quality_direction} from {first_quality} to {last_quality}.",
    ]

    if latest_top_sources:
        lines.append(f"Latest top sources: {latest_top_sources}.")

    if last_signals > first_signals and last_quality >= first_quality:
        lines.append("This suggests the system is not only collecting more signals, but also improving source quality.")
    elif last_signals > first_signals and last_quality < first_quality:
        lines.append("This suggests signal volume is growing faster than source quality, so filtering may need to be tightened.")
    else:
        lines.append("The recent trend is still early, so more daily runs are needed before drawing stronger conclusions.")

    return "\n\n".join(lines)

# =========================
# Session State
# =========================
def ensure_session_state() -> None:
    defaults = {
        "selected_signal_idx": 0,
        "selected_source_filter": "All",
        "selected_date": "latest",
        "last_selected_date": "latest",
        "active_signal_title_for_compare": "",
        "model_chats": {
            "claude": [],
            "chatgpt": [],
            "perplexity": [],
        },
        "linkedin_building_blocks": "",
        "linkedin_post_output": "",
        "manual_vision_result": None,
        "manual_vision_result_zh": None,
        "manual_vision_saved_session_id": "",
        "manual_uploader_version": 0,
        "manual_prepared_files": [],
        "manual_selected_saved_session_id": "",
        "manual_session_search": "",
        "manual_session_search_input": "",
        "manual_session_search_triggered": False,
        "manual_pending_load_session": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def reset_compare_if_signal_changed(signal_title: str) -> None:
    if st.session_state.active_signal_title_for_compare != signal_title:
        st.session_state.active_signal_title_for_compare = signal_title
        st.session_state.model_chats = {
            "claude": [],
            "chatgpt": [],
            "perplexity": [],
        }
        st.session_state.linkedin_building_blocks = ""
        st.session_state.linkedin_post_output = ""


# =========================
# Provider Prompts
# =========================
def build_provider_system_prompt(model_key: str, context: dict, reflection_text: str) -> str:
    provider_style = {
        "claude": (
            "You are Claude, primarily used here as a writing partner. "
            "Your strength is editing, rewriting, clarifying, deepening, and improving expression."
        ),
        "chatgpt": (
            "You are ChatGPT, primarily used here for structured refinement, reasoning, and improving clarity."
        ),
        "perplexity": (
            "You are Perplexity, primarily used here for research-grounded refinement and broader context."
        ),
    }.get(model_key, "You are a helpful AI assistant.")

    return f"""
{provider_style}

You are inside an AI Radar workspace.

Personal context:
{format_personal_context(context["personal_context"])}

Current signal:
Title: {context["signal_title"]}
Summary: {context["signal_summary"]}

Current AI insight:
Why it matters: {context["why_it_matters"]}
Relevance to projects: {context["relevance_to_projects"]}
Relevance to career: {context["relevance_to_career"]}
Synthesized insight: {context["synthesized_insight"]}

Current reflection draft:
{reflection_text}

Rules:
- Stay grounded in the signal summary and AI insight.
- Use the user's personal context to avoid generic replies.
- If the user writes in Chinese, reply in Chinese.
- If the user writes in English, reply in English.
- Be concise, useful, and natural.
""".strip()


def build_seed_message(reflection_text: str) -> str:
    return (
        "Please help me refine the following reflection based on the signal and insight context. "
        "Make it more aligned with my background, projects, and goals:\n\n"
        f"{reflection_text.strip()}"
    )


def build_linkedin_building_blocks_prompt(context: dict) -> str:
    return f"""
You are Claude, acting as a strategic writing editor.

Based on the following materials, generate the following three sections only:

1. What this article is about
3. Key takeaways for my projects
4. Key takeaways for my career and skill development

Do NOT generate section 2 yet.

Personal context:
{format_personal_context(context["personal_context"])}

Signal:
Title: {context["signal_title"]}
Summary: {context["signal_summary"]}

Insight:
Why it matters: {context["why_it_matters"]}
Relevance to projects: {context["relevance_to_projects"]}
Relevance to career: {context["relevance_to_career"]}
Synthesized insight: {context["synthesized_insight"]}

Requirements:
- Write in English unless the source content is clearly better handled in Chinese
- Be clear, concise, thoughtful, and specific
- Use exactly these headings:
1. What this article is about
3. Key takeaways for my projects
4. Key takeaways for my career and skill development
""".strip()


def build_final_linkedin_post_prompt(context: dict, saved_reflection_text: str) -> str:
    return f"""
You are Claude, acting as a strong writing editor for a final LinkedIn-ready post.

Based on the following materials, write a polished LinkedIn-ready note in 4 clearly labeled sections.

Personal context:
{format_personal_context(context["personal_context"])}

Signal:
Title: {context["signal_title"]}
Summary: {context["signal_summary"]}

Insight:
Why it matters: {context["why_it_matters"]}
Relevance to projects: {context["relevance_to_projects"]}
Relevance to career: {context["relevance_to_career"]}
Synthesized insight: {context["synthesized_insight"]}

Saved reflection:
{saved_reflection_text}

Requirements:
- Total length must be under 3000 characters
- Write in English unless the saved reflection is mainly Chinese
- Use the following 4-section structure exactly:

1. What this article is about
2. My reflection
3. Key takeaways for my projects
4. Key takeaways for my career and skill development

Style:
- thoughtful
- professional
- clear
- strategic
- not generic
- suitable for LinkedIn but not overly promotional
""".strip()


# =========================
# Provider Calls
# =========================
def call_chatgpt(messages: list[dict], system_prompt: str, model_name: str) -> str:
    if not OPENAI_API_KEY:
        return "ChatGPT error: OPENAI_API_KEY not found."

    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "system", "content": system_prompt}] + messages,
            temperature=0.7,
        )
        return safe_text(response.choices[0].message.content).strip()
    except Exception as e:
        return f"ChatGPT error: {e}"


def call_claude(messages: list[dict], system_prompt: str, model_name: str) -> str:
    if anthropic is None:
        return "Claude error: anthropic package not installed. Run: pip install anthropic"

    if not ANTHROPIC_API_KEY:
        return "Claude error: ANTHROPIC_API_KEY not found."

    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        response = client.messages.create(
            model=model_name,
            max_tokens=1200,
            system=system_prompt,
            messages=messages,
        )
        parts = []
        for block in response.content:
            text = getattr(block, "text", "")
            if text:
                parts.append(text)
        return "\n".join(parts).strip()
    except Exception as e:
        return f"Claude error: {e}"


def call_perplexity(messages: list[dict], system_prompt: str, model_name: str) -> str:
    if not PERPLEXITY_API_KEY:
        return "Perplexity error: PERPLEXITY_API_KEY not found."

    try:
        client = OpenAI(
            api_key=PERPLEXITY_API_KEY,
            base_url="https://api.perplexity.ai",
        )
        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "system", "content": system_prompt}] + messages,
            temperature=0.2,
        )
        return safe_text(response.choices[0].message.content).strip()
    except Exception as e:
        return f"Perplexity error: {e}"


def call_model(model_key: str, messages: list[dict], system_prompt: str) -> str:
    chatgpt_model_name = st.session_state.get("chatgpt_model_name", DEFAULT_OPENAI_MODEL)
    claude_model_name = st.session_state.get("claude_model_name", DEFAULT_ANTHROPIC_MODEL)
    perplexity_model_name = st.session_state.get("perplexity_model_name", DEFAULT_PERPLEXITY_MODEL)

    if model_key == "claude":
        return call_claude(messages, system_prompt, claude_model_name)
    if model_key == "chatgpt":
        return call_chatgpt(messages, system_prompt, chatgpt_model_name)
    if model_key == "perplexity":
        return call_perplexity(messages, system_prompt, perplexity_model_name)
    return f"Unknown model: {model_key}"


# =========================
# Chat State Helpers
# =========================
@st.cache_data(ttl=1800)
def generate_trend_insight_llm(history_overview_json: str) -> str:
    history_overview = json.loads(history_overview_json) if history_overview_json else []
    if not history_overview:
        return "No history data available."

    prompt = f"""
You are an AI system analyzing trend data.

Here is the history overview:

{json.dumps(history_overview, indent=2)}

Generate a concise but insightful analysis covering:
1. Signal trend
2. Insight trend
3. Source quality trend
4. What this implies about system behavior

Keep it structured and high-signal.
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.5,
        messages=[
            {"role": "system", "content": "You are a decision intelligence analyst."},
            {"role": "user", "content": prompt},
        ],
    )

    return response.choices[0].message.content

def append_user_message(model_key: str, content: str) -> None:
    st.session_state.model_chats[model_key].append(
        {"role": "user", "content": content.strip()}
    )


def append_assistant_message(model_key: str, content: str) -> None:
    st.session_state.model_chats[model_key].append(
        {"role": "assistant", "content": content.strip()}
    )


def clear_model_chat(model_key: str) -> None:
    st.session_state.model_chats[model_key] = []


def generate_model_reply(model_key: str, context: dict, reflection_text: str) -> None:
    messages = st.session_state.model_chats[model_key]
    system_prompt = build_provider_system_prompt(model_key, context, reflection_text)
    reply = call_model(model_key, messages, system_prompt)
    append_assistant_message(model_key, reply)


def seed_model_from_reflection(model_key: str, context: dict, reflection_text: str) -> str:
    if not reflection_text.strip():
        return "Please write a reflection first."
    append_user_message(model_key, build_seed_message(reflection_text))
    generate_model_reply(model_key, context, reflection_text)
    return ""


def run_all_models_from_reflection(context: dict, reflection_text: str) -> str:
    if not reflection_text.strip():
        return "Please write a reflection first."

    for model_key in MODEL_ORDER:
        append_user_message(model_key, build_seed_message(reflection_text))
        generate_model_reply(model_key, context, reflection_text)

    return ""


def generate_linkedin_building_blocks(context: dict) -> str:
    prompt = build_linkedin_building_blocks_prompt(context)
    messages = [{"role": "user", "content": prompt}]
    system_prompt = "You are Claude, a strategic writing editor."
    output = call_claude(
        messages,
        system_prompt,
        st.session_state.get("claude_model_name", DEFAULT_ANTHROPIC_MODEL),
    )
    st.session_state.linkedin_building_blocks = output
    return ""


def generate_final_linkedin_post(context: dict, signal_title: str) -> str:
    saved_reflection = get_latest_saved_reflection_for_signal(signal_title)
    if not saved_reflection:
        return "Please save your reflection first, then generate the final LinkedIn post."

    prompt = build_final_linkedin_post_prompt(context, saved_reflection)
    messages = [{"role": "user", "content": prompt}]
    system_prompt = "You are Claude, a strong editor for professional LinkedIn writing."
    output = call_claude(
        messages,
        system_prompt,
        st.session_state.get("claude_model_name", DEFAULT_ANTHROPIC_MODEL),
    )

    if len(output) > 3000:
        output = output[:2997] + "..."

    st.session_state.linkedin_post_output = output

    if output.strip() and not output.lower().startswith("claude error:"):
        mark_reflection_used_for_linkedin(signal_title)

    return ""


# =========================
# UI Components
# =========================
def render_model_chat_panel(model_key: str, context: dict, reflection_text: str):
    st.markdown(f"### {MODEL_TITLES[model_key]}")
    st.caption(MODEL_SUBTITLES[model_key])

    b1, b2 = st.columns(2)
    with b1:
        if st.button(
            "Use Reflection",
            key=f"use_reflection_{model_key}_{st.session_state.selected_signal_idx}",
            use_container_width=True,
        ):
            with st.spinner(f"Running {MODEL_TITLES[model_key]}..."):
                error_msg = seed_model_from_reflection(model_key, context, reflection_text)
            if error_msg:
                st.warning(error_msg)
            st.rerun()

    with b2:
        if st.button(
            "Clear Chat",
            key=f"clear_chat_{model_key}_{st.session_state.selected_signal_idx}",
            use_container_width=True,
        ):
            clear_model_chat(model_key)
            st.rerun()

    chat_box = st.container(height=430, border=True)
    with chat_box:
        if not st.session_state.model_chats[model_key]:
            st.info("No conversation yet.")
        else:
            for msg in st.session_state.model_chats[model_key]:
                role = msg.get("role", "")
                content = safe_text(msg.get("content", ""))

                if role == "user":
                    with st.chat_message("user"):
                        st.write(content)
                else:
                    with st.chat_message("assistant"):
                        st.write(content)

    form_key = f"{model_key}_chat_form_{st.session_state.selected_signal_idx}"
    input_key = f"{model_key}_chat_input_{st.session_state.selected_signal_idx}"

    with st.form(key=form_key, clear_on_submit=True):
        user_text = st.text_input(
            f"Continue chatting with {MODEL_TITLES[model_key]}",
            key=input_key,
            placeholder="Ask follow-up questions, request rewrite, summarize, translate, or change tone...",
            label_visibility="collapsed",
        )
        sent = st.form_submit_button("Send", use_container_width=True)

    if sent:
        if not user_text.strip():
            st.warning("Please enter a message.")
        else:
            with st.spinner(f"{MODEL_TITLES[model_key]} is thinking..."):
                append_user_message(model_key, user_text)
                generate_model_reply(model_key, context, reflection_text)
            st.rerun()


# =========================
# Main
# =========================
ensure_session_state()

available_dates = list_available_dates(S3_BUCKET)
selected_date = st.session_state.get("selected_date", "latest")
daily_key, signals_key, insights_key = build_s3_keys(selected_date)

daily_radar = load_json_from_s3(S3_BUCKET, daily_key)
signals_data = load_json_from_s3(S3_BUCKET, signals_key)
insights_data = load_json_from_s3(S3_BUCKET, insights_key)

# ⭐ 关键：新增这一行（解决报错）
history_overview = load_history_overview(S3_BUCKET, available_dates, max_days=7)
trend_insight = generate_trend_insight_llm(json.dumps(history_overview, ensure_ascii=False, sort_keys=True))

signals = normalize_signals(signals_data, daily_radar)
source_stats = normalize_source_stats(daily_radar, signals)
insights = normalize_insights(insights_data, daily_radar)
trend_summary = normalize_trend_summary(daily_radar)

# ⭐ 新增：Intelligence Blocks
render_intelligence_blocks(daily_radar)

st.title("AI Radar Workspace")
st.caption("Signal → Insight → Trend → Reflection → Multi-Model Compare")

with st.sidebar:
    st.header("Signals & Controls")

    if st.button("Refresh"):
        st.cache_data.clear()
        st.rerun()

    st.markdown("---")
    st.subheader("Date")

    date_options = ["latest"] + available_dates

    if st.session_state.selected_date not in date_options:
        st.session_state.selected_date = "latest"

    selected_date_ui = st.selectbox(
        "Select date",
        date_options,
        index=date_options.index(st.session_state.selected_date),
        key="selected_date_selectbox",
    )

    if "last_selected_date" not in st.session_state:
        st.session_state.last_selected_date = selected_date_ui

    if selected_date_ui != st.session_state.selected_date:
        st.session_state.selected_date = selected_date_ui
        st.session_state.selected_signal_idx = 0
        st.session_state.last_selected_date = selected_date_ui
        st.rerun()

    if selected_date_ui != st.session_state.last_selected_date:
        st.session_state.selected_signal_idx = 0
        st.session_state.last_selected_date = selected_date_ui
        st.rerun()

    if not daily_radar:
        st.warning("No daily_radar.json found for the selected date.")
        st.stop()

    if not signals:
        st.info("No signals found for the selected date.")
        st.stop()

    st.markdown("---")
    st.subheader("Model Settings")

    st.text_input(
        "Claude model",
        value=st.session_state.get("claude_model_name", DEFAULT_ANTHROPIC_MODEL),
        key="claude_model_name",
    )
    if st.session_state.get("last_successful_claude_model"):
        st.caption(f"Last successful Claude model: {st.session_state.get('last_successful_claude_model')}")
    st.text_input(
        "ChatGPT model",
        value=st.session_state.get("chatgpt_model_name", DEFAULT_OPENAI_MODEL),
        key="chatgpt_model_name",
    )
    st.text_input(
        "Perplexity model",
        value=st.session_state.get("perplexity_model_name", DEFAULT_PERPLEXITY_MODEL),
        key="perplexity_model_name",
    )

    st.markdown("---")
    st.subheader("Filter")

    source_options = ["All"] + sorted(
        {
            safe_text(signal.get("source", "")).strip()
            for signal in signals
            if safe_text(signal.get("source", "")).strip()
        }
    )

    current_filter = st.session_state.selected_source_filter
    if current_filter not in source_options:
        current_filter = "All"
        st.session_state.selected_source_filter = "All"

    selected_source = st.selectbox(
        "Filter by source",
        source_options,
        index=source_options.index(current_filter),
    )

    filter_changed = selected_source != st.session_state.selected_source_filter
    if filter_changed:
        st.session_state.selected_source_filter = selected_source

    filtered_indices = []
    for idx, signal in enumerate(signals):
        source = safe_text(signal.get("source", "")).strip()
        if selected_source == "All" or source == selected_source:
            filtered_indices.append(idx)

    if filtered_indices:
        if filter_changed or st.session_state.selected_signal_idx not in filtered_indices:
            st.session_state.selected_signal_idx = filtered_indices[0]
            st.rerun()

    st.markdown("---")
    st.subheader("Signal List")

    if not filtered_indices:
        st.info("No signals match the current filter.")
        st.stop()

    for idx in filtered_indices:
        signal = signals[idx]
        title = get_signal_title(signal, idx + 1)
        source = safe_text(signal.get("source", "")).strip()
        author = safe_text(signal.get("author", "")).strip()
        category = safe_text(signal.get("category", "")).strip()
        summary_length = signal.get("summary_length")
        quality_badge = get_quality_badge(signal)

        is_selected = idx == st.session_state.selected_signal_idx
        button_label = f"👉 {quality_badge} — {title}" if is_selected else f"{quality_badge} — {title}"

        if st.button(button_label, key=f"signal_btn_{idx}", use_container_width=True):
            st.session_state.selected_signal_idx = idx
            st.rerun()

        meta_parts = []
        if source:
            meta_parts.append(source)
        if author:
            meta_parts.append(author)
        if category:
            meta_parts.append(category)
        if summary_length:
            meta_parts.append(f"{summary_length} chars")

        if meta_parts:
            st.caption(" | ".join(meta_parts))
        st.markdown("---")

    st.markdown("---")
    st.subheader("Source Quality")

    for source_name, stats in sorted(
        source_stats.items(),
        key=lambda x: x[1]["quality_score"],
        reverse=True
    ):
        st.caption(
            f"{source_name} | score: {stats['quality_score']} | count: {stats['raw_count']}"
        )


insight_map = build_insight_map(insights)
reflections = load_reflections()
personal_context = load_personal_context()
preference_profile = compute_preference_profile(reflections)


# =========================
# Manual Vision Workspace
# =========================
st.markdown('<div class="section-title">Manual Vision Workspace</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="section-subtitle">Upload up to 12 images or files, let AI interpret them using your saved background, then save each batch as a reusable session</div>',
    unsafe_allow_html=True,
)

manual_left, manual_right = st.columns([1.2, 1.8], gap="large")

with manual_left:
    st.markdown("**上传与分析**")
    top_action_1, top_action_2 = st.columns(2)
    with top_action_1:
        if st.button("新建上传批次", use_container_width=True, key="manual_new_batch_btn"):
            st.session_state.manual_uploader_version += 1
            st.session_state.manual_vision_result = None
            st.session_state.manual_vision_result_zh = None
            st.session_state.manual_vision_saved_session_id = ""
            st.session_state.manual_prepared_files = []
            st.session_state.curated_upload_signals = []
            st.rerun()
    with top_action_2:
        st.caption("开始新批次后，旧内容会被清空，不需要一项项删除。当前支持纯图片批次或纯文件批次。下一步建议：把文件内容也接入统一 signal pipeline，形成 image/text/pdf → signal → insight 的完整闭环。")

    pending_manual_load = st.session_state.get("manual_pending_load_session")
    if isinstance(pending_manual_load, dict):
        pending_result, pending_result_zh = build_manual_result_from_saved_session(pending_manual_load)
        st.session_state.manual_vision_result = pending_result
        st.session_state.manual_vision_result_zh = pending_result_zh
        st.session_state.manual_session_title = safe_text(pending_manual_load.get("session_title", pending_manual_load.get("title", "Manual vision session"))).strip()
        st.session_state.manual_user_instruction = safe_text(pending_manual_load.get("instruction", "")).strip()
        st.session_state.manual_vision_saved_session_id = safe_text(pending_manual_load.get("session_id", "")).strip()
        st.session_state.manual_selected_saved_session_id = safe_text(pending_manual_load.get("session_id", "")).strip()
        st.session_state.manual_pending_load_session = None

    manual_session_title = st.text_input(
        "Session title",
        key="manual_session_title",
        placeholder="例如：Agent 架构截图 / 小红书批量截图 / AI notebook ideas",
    )

    manual_user_instruction = st.text_area(
        "Instruction for this upload batch",
        key="manual_user_instruction",
        height=120,
        value=(
            "Follow the current AI Radar workflow. "
            "First summarize the images. "
            "Second, give insights specifically for me based on my background. "
            "Third, give key takeaways for my projects. "
            "Fourth, give key takeaways for my career and skill development."
        ),
    )

    uploader_key = f"manual_vision_uploader_{st.session_state.get('manual_uploader_version', 0)}"
    uploaded_manual_files = st.file_uploader(
        "Upload images or files (max 12)",
        type=["png", "jpg", "jpeg", "webp", "pdf", "txt", "md", "json", "csv"],
        accept_multiple_files=True,
        key=uploader_key,
    )

    preview_files = normalize_uploaded_files(uploaded_manual_files)
    preview_images, preview_docs = split_uploaded_items(preview_files)
    upload_count = len(preview_files)
    st.caption(f"Current upload count: {upload_count} / 12")

    if uploaded_manual_files and len(uploaded_manual_files) > 12:
        st.warning("Please upload no more than 12 items in one batch.")

    if preview_images:
        render_gallery("预览图片", preview_images, "manual_preview", is_uploaded=True)
    if preview_docs:
        render_uploaded_file_list("预览文件", preview_docs)

    has_mixed_inputs = bool(preview_images and preview_docs)
    if has_mixed_inputs:
        st.warning("当前版本暂不支持图片和文件混合分析。请分两批上传：一批图片，或一批文件。")

    analyze_btn_disabled = not preview_files or len(preview_files) > 12 or has_mixed_inputs
    analyze_button_label = "Analyze Uploads"
    if preview_images and not preview_docs:
        analyze_button_label = "Analyze Images with Claude"
    elif preview_docs and not preview_images:
        analyze_button_label = "Analyze Files with AI"

    if st.button(analyze_button_label, use_container_width=True, disabled=analyze_btn_disabled):
        prepared_files = prepare_uploaded_files_for_processing(preview_files)
        st.session_state["manual_prepared_files"] = prepared_files

        if preview_images and not preview_docs:
            with st.spinner("Claude is reading your uploaded images..."):
                result = analyze_images_with_claude(
                    preview_images,
                    personal_context,
                    manual_user_instruction,
                )
            st.session_state["curated_upload_signals"] = []
        elif preview_docs and not preview_images:
            with st.spinner("AI is reading your uploaded files..."):
                result = analyze_uploaded_files_with_openai(
                    preview_docs,
                    personal_context,
                    manual_user_instruction,
                )

            docs_signals = build_signals_from_uploaded_docs(preview_docs)

            if not docs_signals:
                st.warning("No readable document content found.")
                st.session_state["curated_upload_signals"] = []
            else:
                curated_upload_signals = run_pipeline_on_signals(docs_signals)
                st.session_state["curated_upload_signals"] = [
                    s.to_dict() for s in curated_upload_signals
                ]
        else:
            result = {"error": "Unsupported upload combination."}
            st.session_state["curated_upload_signals"] = []

        st.session_state.manual_vision_result = result
        st.session_state.manual_vision_result_zh = translate_manual_result_for_display(result)
        st.session_state.manual_vision_saved_session_id = ""
        st.rerun()

with manual_right:
    st.markdown("**当前分析（中文显示）**")
    current_manual_result = st.session_state.get("manual_vision_result")
    current_manual_result_zh = st.session_state.get("manual_vision_result_zh")

    if current_manual_result:
        if current_manual_result.get("error"):
            st.error(current_manual_result["error"])
        else:
            parse_status = safe_text(current_manual_result.get("parse_status", "unknown"))
            if parse_status != "ok":
                st.warning(
                    f"Claude returned content, but structured parsing was not fully successful. Current status: {parse_status}"
                )

            zh_summary = safe_text((current_manual_result_zh or {}).get("summary_zh", "")).strip()
            zh_insight = safe_text((current_manual_result_zh or {}).get("insights_for_me_zh", "")).strip()
            zh_projects = (current_manual_result_zh or {}).get("project_takeaways_zh", []) or []
            zh_career = (current_manual_result_zh or {}).get("career_takeaways_zh", []) or []

            if not zh_summary:
                zh_summary = safe_text(current_manual_result.get("summary", "")).strip()

            if not zh_insight:
                zh_insight = safe_text(current_manual_result.get("insights_for_me", "")).strip()

            if not zh_projects:
                zh_projects = current_manual_result.get("project_takeaways", []) or []

            if not zh_career:
                zh_career = current_manual_result.get("career_takeaways", []) or []

            render_scroll_text_box("1. Claude 总结", zh_summary, height=180)

            insight_edit_key = "manual_insight_for_me_zh_edit"
            result_signature = (
                zh_summary,
                zh_insight,
                "|".join([safe_text(x) for x in zh_projects]),
                "|".join([safe_text(x) for x in zh_career]),
            )
            if st.session_state.get("manual_insight_result_signature") != result_signature:
                st.session_state["manual_insight_result_signature"] = result_signature
                st.session_state[insight_edit_key] = zh_insight

            st.markdown("**2. 我的见解（AI辅助生成，可编辑）**")
            edited_insight_zh = st.text_area(
                "我的见解（AI辅助生成，可编辑）",
                height=180,
                key=insight_edit_key,
                label_visibility="collapsed",
            )

            render_scroll_text_box(
                "3. 对我项目的关键 takeaways",
                format_takeaways_list(zh_projects),
                height=180,
            )
            render_scroll_text_box(
                "4. 对我职业和技能发展的关键 takeaways",
                format_takeaways_list(zh_career),
                height=180,
            )

            with st.expander("Show Claude raw response"):
                st.code(current_manual_result.get("raw_response", ""), language="json")
                st.caption(f"Parse status: {safe_text(current_manual_result.get('parse_status', 'unknown'))}")

            if st.button("Save This Manual Vision Session", use_container_width=True):
                session_title_value = st.session_state.get("manual_session_title", "").strip()
                prepared_files = st.session_state.get("manual_prepared_files", [])

                if not prepared_files:
                    st.error("No uploaded files found for this session. Please analyze the batch again before saving.")
                else:
                    english_payload = translate_manual_result_back_to_english(
                        zh_summary,
                        edited_insight_zh,
                        zh_projects,
                        zh_career,
                    )

                    project_takeaways_en = english_payload.get("project_takeaways", []) or []
                    career_takeaways_en = english_payload.get("career_takeaways", []) or []
                    extracted_signals = st.session_state.get("curated_upload_signals", []) or []

                    session_id, session_s3_key, _ = save_manual_session_to_s3_from_result(
                        session_title=session_title_value or "Manual vision session",
                        instruction=st.session_state.get("manual_user_instruction", ""),
                        prepared_files=prepared_files,
                        personal_context_snapshot=personal_context,
                        summary=english_payload.get("summary", ""),
                        insights_for_me=english_payload.get("insights_for_me", ""),
                        project_takeaways=project_takeaways_en,
                        career_takeaways=career_takeaways_en,
                        summary_zh=zh_summary,
                        insights_for_me_zh=edited_insight_zh,
                        project_takeaways_zh=zh_projects,
                        career_takeaways_zh=zh_career,
                        reflection=edited_insight_zh,
                        extracted_signals=extracted_signals,
                        raw_response=current_manual_result.get("raw_response", ""),
                        status="completed",
                    )

                    st.session_state.manual_vision_saved_session_id = session_id
                    st.session_state.manual_selected_saved_session_id = session_id
                    load_json_from_s3.clear()
                    st.success(f"Saved session: {session_id}")
                    st.caption(f"Session JSON: {session_s3_key}")
                    st.session_state.manual_uploader_version += 1
                    st.session_state.manual_vision_result = None
                    st.session_state.manual_vision_result_zh = None
                    st.session_state.manual_prepared_files = []
                    st.session_state.manual_session_search = ""
                    st.session_state.manual_session_search_input = ""
                    st.session_state.manual_session_search_triggered = False
                    st.rerun()
    else:
        st.info("No manual vision analysis yet.")

pipeline_signals = st.session_state.get("curated_upload_signals", [])

if pipeline_signals:
    st.markdown("### Upload → Signal Pipeline Output")

    for idx, signal in enumerate(pipeline_signals, start=1):
        st.markdown(f"**{idx}. {signal.get('title', 'Untitled')}**")
        st.write(f"Source: {signal.get('source', '')}")
        st.write(f"Type: {signal.get('source_type', '')}")
        st.write(f"Summary: {signal.get('summary', '')}")
        st.write(f"Why it matters: {signal.get('why_it_matters_to_me', '')}")

        scores = signal.get("scores", {})
        if isinstance(scores, dict):
            st.write(
                f"Scores → relevance: {scores.get('relevance', 0)}, "
                f"quality: {scores.get('quality', 0)}, "
                f"personal_fit: {scores.get('personal_fit', 0)}, "
                f"total: {scores.get('total', 0)}"
            )

        st.markdown("---")

st.markdown(" ")

st.markdown("**Saved Manual Vision Sessions**")
manual_sessions = load_manual_sessions()

if manual_sessions:
    search_cols = st.columns([1.6, 0.7, 1.2])
    with search_cols[0]:
        st.text_input(
            "Search saved sessions",
            key="manual_session_search_input",
            placeholder="Search by title, summary, insight, session ID, or file name",
        )
    with search_cols[1]:
        if st.button("Search", use_container_width=True, key="manual_session_search_button"):
            st.session_state.manual_session_search = safe_text(st.session_state.get("manual_session_search_input", "")).strip()
            st.session_state.manual_session_search_triggered = True
            st.session_state.manual_selected_saved_session_id = ""
            st.rerun()
    with search_cols[2]:
        if st.button("Clear search", use_container_width=True, key="manual_session_clear_search_button"):
            st.session_state.manual_session_search_input = ""
            st.session_state.manual_session_search = ""
            st.session_state.manual_session_search_triggered = False
            st.session_state.manual_selected_saved_session_id = ""
            st.rerun()

    st.caption("Search works across title, summary, insight, session ID, and uploaded file names.")

    active_search = safe_text(st.session_state.get("manual_session_search", "")).strip()
    filtered_manual_sessions = []
    keyword = active_search.lower()
    for sess in manual_sessions:
        searchable_parts = [
            safe_text(sess.get("session_id", "")),
            safe_text(sess.get("session_title", "")),
            safe_text(sess.get("title", "")),
            safe_text(sess.get("summary", "")),
            safe_text(sess.get("insights_for_me", "")),
        ]
        for f in (sess.get("files", []) or []):
            if isinstance(f, dict):
                searchable_parts.append(safe_text(f.get("file_name", "")))
                searchable_parts.append(safe_text(f.get("s3_key", "")))
            else:
                searchable_parts.append(Path(str(f)).name)
                searchable_parts.append(safe_text(f))

        haystack = " ".join([p for p in searchable_parts if p]).lower()
        if (not keyword) or (keyword in haystack):
            filtered_manual_sessions.append(sess)

    if active_search:
        result_rows = []
        for sess in filtered_manual_sessions:
            sess_files = sess.get("files", []) or sess.get("images", []) or []
            first_file = ""
            if sess_files:
                first_item = sess_files[0]
                if isinstance(first_item, dict):
                    first_file = safe_text(first_item.get("file_name", "")) or Path(safe_text(first_item.get("s3_key", ""))).name
                else:
                    first_file = Path(str(first_item)).name
            result_rows.append({
                "created_at": safe_text(sess.get("created_at", ""))[:19],
                "session_title": safe_text(sess.get("session_title", sess.get("title", "Manual vision session"))),
                "first_file": first_file or "-",
                "session_id": safe_text(sess.get("session_id", "")),
            })

        st.markdown("**Search results**")
        if result_rows:
            st.dataframe(result_rows, use_container_width=True, hide_index=True)
        else:
            st.info("No saved sessions matched your search.")

    if not filtered_manual_sessions:
        if not active_search:
            st.info("No saved sessions matched your search.")
    else:
        summary_rows = []
        for sess in filtered_manual_sessions:
            sess_files = sess.get("files", []) or sess.get("images", []) or []
            first_file = ""
            if sess_files:
                first_item = sess_files[0]
                if isinstance(first_item, dict):
                    first_file = safe_text(first_item.get("file_name", "")) or Path(safe_text(first_item.get("s3_key", ""))).name
                else:
                    first_file = Path(str(first_item)).name
            summary_rows.append({
                "created_at": safe_text(sess.get("created_at", ""))[:19],
                "session_title": safe_text(sess.get("session_title", sess.get("title", "Manual vision session"))),
                "files": sess.get("file_count", sess.get("image_count", len(sess_files))),
                "first_file": first_file or "-",
                "session_id": safe_text(sess.get("session_id", "")),
            })

        st.caption("Manual uploads list")
        st.dataframe(summary_rows, use_container_width=True, hide_index=True)

        session_labels = []
        for sess in filtered_manual_sessions:
            session_labels.append(
                f"{safe_text(sess.get('created_at', ''))} | {safe_text(sess.get('session_title', sess.get('title', 'Manual vision session')))} | {sess.get('file_count', sess.get('image_count', len(sess.get('files', []) or sess.get('images', []) or [])))} files"
            )

        selected_saved_session_id = st.session_state.get("manual_selected_saved_session_id", "")
        default_idx = 0
        if selected_saved_session_id:
            for idx, sess in enumerate(filtered_manual_sessions):
                if safe_text(sess.get("session_id", "")) == selected_saved_session_id:
                    default_idx = idx
                    break

        selected_session_label = st.selectbox(
            "Select saved manual session",
            session_labels,
            index=default_idx,
            key="manual_session_selector",
        )

        selected_session_idx = session_labels.index(selected_session_label)
        selected_manual_session = filtered_manual_sessions[selected_session_idx]
        st.session_state.manual_selected_saved_session_id = safe_text(selected_manual_session.get("session_id", ""))

        ms1, ms2, ms3, ms4 = st.columns(4)
        ms1.metric("Saved sessions", len(filtered_manual_sessions))
        ms2.metric("Files", selected_manual_session.get("file_count", selected_manual_session.get("image_count", len(selected_manual_session.get("files", []) or selected_manual_session.get("images", []) or []))))
        ms3.metric("Session ID", safe_text(selected_manual_session.get("session_id", ""))[:18] or "-")
        if ms4.button("Load this session", use_container_width=True, key=f"load_manual_session_{safe_text(selected_manual_session.get('session_id', 'x'))}"):
            st.session_state.manual_pending_load_session = selected_manual_session
            st.rerun()

        saved_images = selected_manual_session.get("images", [])
        saved_files = selected_manual_session.get("files", []) or saved_images
        if saved_images:
            render_gallery("已保存图片", saved_images, f"saved_manual_{safe_text(selected_manual_session.get('session_id', 'x'))}", is_uploaded=False)
        non_image_files = [p for p in saved_files if not str(p).lower().endswith((".png", ".jpg", ".jpeg", ".webp"))]
        if non_image_files:
            render_uploaded_file_list("已保存文件", non_image_files)

        s1, s2 = st.columns(2, gap="small")
        with s1:
            render_scroll_text_box("Saved summary (English)", selected_manual_session.get("summary", ""), height=220)
            render_scroll_text_box("Saved insight / 我的见解（English）", selected_manual_session.get("insights_for_me", ""), height=220)
        with s2:
            render_scroll_text_box(
                "Saved project takeaways (English)",
                format_takeaways_list(normalize_saved_takeaways(selected_manual_session.get("project_takeaways", []))),
                height=220,
            )
            render_scroll_text_box(
                "Saved career takeaways (English)",
                format_takeaways_list(normalize_saved_takeaways(selected_manual_session.get("career_takeaways", []))),
                height=220,
            )
else:
    st.info("No saved manual vision sessions yet.")

st.markdown(" ")
st.markdown(" ")


date_str = safe_text(daily_radar.get("date", ""))
timezone_str = safe_text(daily_radar.get("timezone", ""))
generated_at = safe_text(daily_radar.get("generated_at", ""))

signal_count = daily_radar.get("signal_count")
insight_count = daily_radar.get("insight_count")

if signal_count is None:
    signal_count = len(signals)
if insight_count is None:
    insight_count = len(insights)

top1, top2, top3, top4 = st.columns(4)
top1.metric("Date", date_str or "-")
top2.metric("Timezone", timezone_str or "-")
top3.metric("Signals", signal_count)
top4.metric("Insights", insight_count)

st.markdown(f"**Generated at:** {generated_at or '-'}")
st.markdown(f"**Viewing:** {selected_date}")
st.markdown("---")

selected_signal = signals[st.session_state.selected_signal_idx]
selected_signal_title = get_signal_title(selected_signal, st.session_state.selected_signal_idx + 1)
selected_signal_summary = get_signal_summary(selected_signal)
selected_signal_source = safe_text(selected_signal.get("source", ""))
selected_signal_author = safe_text(selected_signal.get("author", ""))
selected_signal_url = safe_text(selected_signal.get("url", ""))
selected_signal_category = safe_text(selected_signal.get("category", ""))
selected_signal_quality = safe_text(selected_signal.get("quality_level", "unknown")).upper()
selected_signal_quality_badge = get_quality_badge(selected_signal)
selected_signal_summary_length = selected_signal.get("summary_length")
selected_signal_timestamp = safe_text(
    selected_signal.get("published_at")
    or selected_signal.get("timestamp")
    or selected_signal.get("collected_at")
    or ""
)
selected_signal_score = get_signal_metric(selected_signal, "score", 0.0)
selected_signal_recency = get_signal_metric(selected_signal, "recency_score", 0.0)
selected_signal_relevance = get_signal_metric(selected_signal, "keyword_relevance", 0.0)
selected_signal_novelty = get_signal_metric(selected_signal, "novelty_score", 0.0)
selected_signal_source_weight = get_signal_metric(selected_signal, "source_weight", 0.0)

reset_compare_if_signal_changed(selected_signal_title)

selected_insight = insight_map.get(selected_signal_title)

why_it_matters = ""
relevance_to_projects = ""
relevance_to_career = ""
synthesized_insight = ""

if selected_insight:
    why_it_matters = safe_text(selected_insight.get("why_it_matters", ""))
    relevance_to_projects = safe_text(selected_insight.get("relevance_to_projects", ""))
    relevance_to_career = safe_text(selected_insight.get("relevance_to_career", ""))
    synthesized_insight = safe_text(selected_insight.get("synthesized_insight", ""))

context_bundle = build_context_bundle(
    signal_title=selected_signal_title,
    signal_summary=selected_signal_summary,
    why_it_matters=why_it_matters,
    relevance_to_projects=relevance_to_projects,
    relevance_to_career=relevance_to_career,
    synthesized_insight=synthesized_insight,
    personal_context=personal_context,
)

latest_saved_reflection = get_latest_saved_reflection_for_signal(selected_signal_title)

# =========================
# 0. Today's Ranking Snapshot
# =========================
st.markdown('<div class="section-title">Top Signals Today</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="section-subtitle">Current ranking output with recency, relevance, novelty, and final score</div>',
    unsafe_allow_html=True,
)

ranking_rows = []
for signal in signals[:10]:
    ranking_rows.append(
        {
            "title": get_signal_title(signal, 0),
            "source": safe_text(signal.get("source", "")),
            "quality": safe_text(signal.get("quality_level", "unknown")),
            "recency": round(get_signal_metric(signal, "recency_score", 0.0), 2),
            "relevance": round(get_signal_metric(signal, "keyword_relevance", 0.0), 2),
            "novelty": round(get_signal_metric(signal, "novelty_score", 0.0), 2),
            "score": round(get_signal_metric(signal, "score", 0.0), 2),
        }
    )

if ranking_rows:
    st.dataframe(ranking_rows, use_container_width=True, hide_index=True)
else:
    st.info("No ranking output available yet.")

st.markdown(" ")

# =========================
# 1. Signal Article
# =========================
st.markdown('<div class="section-title">Signal Article</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="section-subtitle">High-quality summary with source information</div>',
    unsafe_allow_html=True,
)

article_box = st.container(height=420, border=True)
with article_box:
    st.markdown(f"### {selected_signal_quality_badge} — {selected_signal_title}")

    meta_parts = []
    meta_parts.append(f"Quality Level: {selected_signal_quality}")
    meta_parts.append(f"Score: {selected_signal_score:.2f}")
    meta_parts.append(f"Recency: {selected_signal_recency:.2f}")
    meta_parts.append(f"Relevance: {selected_signal_relevance:.2f}")
    meta_parts.append(f"Novelty: {selected_signal_novelty:.2f}")
    meta_parts.append(f"Weight: {selected_signal_source_weight:.2f}")
    if selected_signal_source:
        meta_parts.append(f"Source: {selected_signal_source}")
    if selected_signal_author:
        meta_parts.append(f"Author: {selected_signal_author}")
    if selected_signal_category:
        meta_parts.append(f"Category: {selected_signal_category}")
    if selected_signal_timestamp:
        meta_parts.append(f"Time: {selected_signal_timestamp}")
    if selected_signal_summary_length:
        meta_parts.append(f"Summary length: {selected_signal_summary_length}")

    if meta_parts:
        st.caption(" | ".join(meta_parts))

    if selected_signal_url:
        st.markdown(f"[Open source link]({selected_signal_url})")
    elif selected_signal_source:
        st.caption(f"No direct URL available for this signal. Source: {selected_signal_source}")

    st.markdown("---")
    if selected_signal_summary.strip():
        st.markdown("**Summary**")
        st.write(selected_signal_summary)
    else:
        st.warning("No summary found in current signal fields.")

st.markdown(" ")

# =========================
# 2. Insight Detail
# =========================
st.markdown('<div class="section-title">Insight Detail</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="section-subtitle">Four fixed modules across the full page</div>',
    unsafe_allow_html=True,
)

i1, i2, i3, i4 = st.columns(4, gap="small")
with i1:
    render_scroll_text_box("Why it matters", why_it_matters, height=250)
with i2:
    render_scroll_text_box("Relevance to projects", relevance_to_projects, height=250)
with i3:
    render_scroll_text_box("Relevance to career", relevance_to_career, height=250)
with i4:
    render_scroll_text_box("Synthesized insight", synthesized_insight, height=250)

st.markdown(" ")

# =========================
# 3. My Reflection
# =========================
st.markdown('<div class="section-title">My Reflection</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="section-subtitle">Your interpretation, reaction, or next-step idea</div>',
    unsafe_allow_html=True,
)

reflection_key = f"reflection_input_{st.session_state.selected_signal_idx}"
if reflection_key not in st.session_state:
    st.session_state[reflection_key] = latest_saved_reflection

reflection_text = st.text_area(
    "Reflection",
    height=230,
    key=reflection_key,
    placeholder="Write what you think about this signal and why it matters to you...",
    label_visibility="collapsed",
)

r1, r2, r3 = st.columns([1.8, 1.2, 2.2], gap="small")

with r1:
    tags_input = st.text_input(
        "Tags",
        value="",
        placeholder="career, product, AI systems",
        label_visibility="collapsed",
        key=f"tags_input_{st.session_state.selected_signal_idx}",
    )

with r2:
    if st.button("Save Reflection", use_container_width=True):
        if reflection_text.strip():
            tags = [tag.strip() for tag in tags_input.split(",") if tag.strip()]
            save_reflection(
                signal_title=selected_signal_title,
                reflection=reflection_text,
                source=selected_signal_source,
                author=selected_signal_author,
                category=selected_signal_category,
                used_for_linkedin=False,
                tags=tags,
            )
            st.success("Reflection saved.")
            st.rerun()
        else:
            st.warning("Please write something before saving.")

with r3:
    if st.button("Compare All Models", use_container_width=True):
        with st.spinner("Running Claude, ChatGPT, and Perplexity..."):
            error_msg = run_all_models_from_reflection(context_bundle, reflection_text)
        if error_msg:
            st.warning(error_msg)
        st.rerun()

st.markdown(" ")

# =========================
# 4. Model Compare
# =========================
st.markdown('<div class="section-title">Model Compare</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="section-subtitle">Three chat panels, fixed height, scroll inside each box</div>',
    unsafe_allow_html=True,
)

c1, c2, c3 = st.columns(3, gap="small")
with c1:
    render_model_chat_panel("claude", context_bundle, reflection_text)
with c2:
    render_model_chat_panel("chatgpt", context_bundle, reflection_text)
with c3:
    render_model_chat_panel("perplexity", context_bundle, reflection_text)

st.markdown(" ")

# =========================
# 5. LinkedIn Building Blocks
# =========================
st.markdown('<div class="section-title">LinkedIn Building Blocks</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="section-subtitle">Generate sections 1, 3, and 4 first</div>',
    unsafe_allow_html=True,
)

lb1, lb2 = st.columns([1.4, 4.6])
with lb1:
    if st.button("Generate 1 / 3 / 4", use_container_width=True):
        with st.spinner("Claude is generating sections 1, 3, and 4..."):
            generate_linkedin_building_blocks(context_bundle)
        st.rerun()

with lb2:
    st.caption("Includes: 1) What this article is about  3) Key takeaways for my projects  4) Key takeaways for my career and skill development")

building_box = st.container(height=320, border=True)
with building_box:
    if st.session_state.linkedin_building_blocks.strip():
        st.write(st.session_state.linkedin_building_blocks)
    else:
        st.info("No building blocks generated yet.")

st.markdown(" ")

# =========================
# 6. Final LinkedIn Post
# =========================
st.markdown('<div class="section-title">Final LinkedIn Post</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="section-subtitle">After saving reflection, generate the final LinkedIn-ready post (under 3000 characters)</div>',
    unsafe_allow_html=True,
)

lp1, lp2 = st.columns([1.4, 4.6])
with lp1:
    if st.button("Generate LinkedIn Post", use_container_width=True):
        with st.spinner("Claude is drafting final LinkedIn post..."):
            error_msg = generate_final_linkedin_post(context_bundle, selected_signal_title)
        if error_msg:
            st.warning(error_msg)
        st.rerun()

with lp2:
    st.caption("Structure: 1) What this article is about  2) My reflection  3) Key takeaways for my projects  4) Key takeaways for my career and skill development")

linkedin_box = st.container(height=360, border=True)
with linkedin_box:
    if st.session_state.linkedin_post_output.strip():
        st.write(st.session_state.linkedin_post_output)
        st.caption(f"Character count: {len(st.session_state.linkedin_post_output)} / 3000")
    else:
        st.info("No final LinkedIn post generated yet.")

st.markdown(" ")

# =========================
# 7. Preference Profile
# =========================
st.markdown('<div class="section-title">Preference Profile</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="section-subtitle">What the system is learning from your reflections and outputs</div>',
    unsafe_allow_html=True,
)

p1, p2, p3 = st.columns(3, gap="small")

with p1:
    top_category_text = ", ".join(
        [f"{name} ({count})" for name, count in preference_profile["top_categories"][:3]]
    )
    render_scroll_text_box("Top categories", top_category_text, height=140)

with p2:
    top_source_text = ", ".join(
        [f"{name} ({count})" for name, count in preference_profile["top_sources"][:3]]
    )
    render_scroll_text_box("Top sources", top_source_text, height=140)

with p3:
    top_author_text = ", ".join(
        [f"{name} ({count})" for name, count in preference_profile["top_authors"][:3]]
    )
    render_scroll_text_box("Top authors", top_author_text, height=140)

st.markdown(" ")

p4, p5, p6 = st.columns(3, gap="small")

with p4:
    top_linkedin_category_text = ", ".join(
        [f"{name} ({count})" for name, count in preference_profile["top_linkedin_categories"][:3]]
    )
    render_scroll_text_box("Top LinkedIn categories", top_linkedin_category_text, height=140)

with p5:
    top_linkedin_source_text = ", ".join(
        [f"{name} ({count})" for name, count in preference_profile["top_linkedin_sources"][:3]]
    )
    render_scroll_text_box("Top LinkedIn sources", top_linkedin_source_text, height=140)

with p6:
    stats_text = (
        f"Reflections: {preference_profile['reflection_count']}\n\n"
        f"Used for LinkedIn: {preference_profile['linkedin_used_count']}\n\n"
        f"Avg reflection length: {preference_profile['avg_reflection_length']}"
    )
    render_scroll_text_box("Preference stats", stats_text, height=140)

st.markdown(" ")

# =========================
# 8. Recent Reflections
# =========================
st.markdown("**Recent Reflections for This Signal**")

matched_reflections = [
    item
    for item in reflections
    if safe_text(item.get("signal_title", "")).strip() == selected_signal_title
]

recent_box = st.container(height=220, border=True)
with recent_box:
    if matched_reflections:
        for item in matched_reflections[:5]:
            created_at = safe_text(item.get("created_at", ""))
            item_reflection = safe_text(item.get("reflection", ""))
            tags = item.get("tags", [])

            st.caption(created_at)
            st.write(item_reflection)

            if tags:
                st.caption("Tags: " + ", ".join(tags))
            st.markdown("---")
    else:
        st.info("No reflection saved for this signal yet.")

# =========================
# 9. History Overview
# =========================
st.markdown('<div class="section-title">History Overview</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="section-subtitle">Recent daily snapshots across signals, insights, and source quality</div>',
    unsafe_allow_html=True,
)

if trend_summary:
    st.markdown("### Daily Trend Summary")

    trend_top_keywords = trend_summary.get("top_keywords", [])
    if isinstance(trend_top_keywords, list) and trend_top_keywords:
        trend_cols = st.columns(min(5, len(trend_top_keywords)))
        for idx, item in enumerate(trend_top_keywords[:5]):
            keyword = safe_text(item.get("keyword", "")).strip()
            count = item.get("count", 0)
            with trend_cols[idx]:
                st.metric(keyword or f"trend_{idx+1}", count)

    trend_summary_text = safe_text(trend_summary.get("summary", "")).strip()
    if trend_summary_text:
        trend_daily_box = st.container(height=100, border=True)
        with trend_daily_box:
            st.write(trend_summary_text)

if history_overview:
    st.dataframe(history_overview, use_container_width=True)

    # =========================
    # Trend Charts
    # =========================
    st.markdown("### Trend Charts")

    import pandas as pd

    df = pd.DataFrame(history_overview)

    if not df.empty:
        df = df.sort_values("date")

        st.markdown("**Signals Trend**")
        st.line_chart(df.set_index("date")[["signal_count"]])

        st.markdown("**Insights Trend**")
        st.line_chart(df.set_index("date")[["insight_count"]])

        st.markdown("**Quality Trend**")
        st.line_chart(df.set_index("date")[["avg_quality_score"]])
    st.markdown("### Trend Insight")
    trend_box = st.container(height=180, border=True)
    with trend_box:
        st.write(trend_insight)
        
    st.markdown("### Decision Recommendation")

    if USE_MOCK_DECISION:
        decision_data = get_mock_decision_payload()
    else:
        decision_data = generate_decision_recommendation(history_overview, trend_insight)

    decision_box = st.container(border=True)
    with decision_box:
        st.write("**Decision Summary**")
        st.write(decision_data["decision_summary"])

        st.write("**Recommendations**")

        for idx, rec in enumerate(decision_data["recommendations"], start=1):
            st.markdown(f"#### {idx}. {rec['title']}")
            st.write(f"**Type:** {rec['type']}")
            st.write(f"**Priority:** {rec['priority']}")
            st.write(f"**Action:** {rec['action']}")
            st.write(f"**Reason:** {rec['reason']}")
            st.divider()
else:
    st.info("No history overview available yet.")

st.markdown(" ")

st.markdown(" ")

with st.expander("Debug: selected signal raw json"):
    st.json(selected_signal)

with st.expander("Debug: raw daily_radar.json"):
    st.json(daily_radar)

with st.expander("Debug: source_stats"):
    st.json(source_stats)

with st.expander("Debug: available dates"):
    st.json(available_dates)

with st.expander("Debug: personal_context.json"):
    st.json(personal_context)
