# app/context/context_builder.py

import json
from pathlib import Path


BASE_DIR = Path(__file__).parent


def load_personal_context():
    path = BASE_DIR / "personal_context.json"

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_analysis_context():
    ctx = load_personal_context()

    profile = ctx.get("user_profile", {})
    projects = ctx.get("projects", {})
    prefs = ctx.get("interpretation_preference", [])

    context_text = f"""
USER PROFILE
Background:
{profile.get("background","")}

Skills:
{", ".join(profile.get("skills", []))}

Career Direction:
{profile.get("career_direction","")}

CURRENT PROJECTS

AI Radar:
{projects.get("ai_radar","")}

GLAP:
{projects.get("glap","")}

AI Cognitive:
{projects.get("ai_cognitive","")}

INTERPRETATION PREFERENCES
{" ".join(prefs)}
"""

    return context_text