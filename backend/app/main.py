import os
import threading
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

ROOT_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"

# Load the repo root `.env` before importing route/service modules so local
# development consistently uses the canonical config file.
load_dotenv(ROOT_ENV_PATH, override=True)

from app.services.s3_reader import (
    BUCKET_NAME,
    load_insights,
    load_radar,
    load_radar_intelligence,
    load_signals,
)
from app.services.model_router_service import router_startup_diagnostics
from app.routes import auth, settings, signals, insights, trends, radar, workspace, manual, feed, saved, projects, reflection, decision_cards, reviews, metrics, signal_review_feedback, dev_inbox, final_takeaways, ai_discussion_memory

app = FastAPI()


def _cors_allowed_origins() -> list[str]:
    raw = os.getenv("CORS_ALLOWED_ORIGINS", "").strip()
    if not raw:
        return [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:3001",
            "http://127.0.0.1:3001",
        ]

    return [value.strip() for value in raw.split(",") if value.strip()]


def _cors_allowed_origin_regex() -> str:
    return r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"


def _startup_summary() -> dict[str, str]:
    def _secret_state(name: str) -> str:
        value = (os.getenv(name) or "").strip()
        return "set" if value else "unset"

    return {
        "aws_region": os.getenv("AWS_REGION", "").strip() or "unset",
        "has_s3_bucket": "yes" if (os.getenv("S3_BUCKET") or os.getenv("AI_RADAR_S3_BUCKET") or BUCKET_NAME) else "no",
        "cors_origin_count": str(len(_cors_allowed_origins())),
        "openai_key": _secret_state("OPENAI_API_KEY"),
        "anthropic_key": _secret_state("ANTHROPIC_API_KEY"),
        "anthropic_model": os.getenv("ANTHROPIC_MODEL", "").strip() or os.getenv("CLAUDE_MODEL", "").strip() or "unset",
    }


def _env_flag_enabled(name: str, *, default: bool = True) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@app.on_event("startup")
def preload_cache():
    print("===== APP STARTUP: PRELOADING CACHE =====")
    print(f"===== APP STARTUP CONFIG: {_startup_summary()} =====")
    router_diag = router_startup_diagnostics()
    warning_count = len(router_diag.get("warnings", []))
    if warning_count:
        print(f"===== MODEL ROUTER WARNINGS: {warning_count} =====")

    if not _env_flag_enabled("AI_RADAR_BACKEND_PRELOAD_CACHE"):
        print("===== APP STARTUP: CACHE PRELOAD SKIPPED BY AI_RADAR_BACKEND_PRELOAD_CACHE =====")
        return

    thread = threading.Thread(target=_preload_cache_background, daemon=True)
    thread.start()


def _preload_cache_background():
    print("===== APP STARTUP: BACKGROUND CACHE PRELOAD STARTED =====")

    try:
        load_signals()
        print("===== SIGNALS CACHE PRELOADED =====")
    except Exception as e:
        print(f"===== FAILED TO PRELOAD SIGNALS CACHE: {e} =====")

    try:
        load_insights(force_refresh=True)
        print("===== INSIGHTS CACHE PRELOADED =====")
    except Exception as e:
        print(f"===== FAILED TO PRELOAD INSIGHTS CACHE: {e} =====")

    try:
        load_radar(force_refresh=True)
        print("===== RADAR CACHE PRELOADED =====")
    except Exception as e:
        print(f"===== FAILED TO PRELOAD RADAR CACHE: {e} =====")

    try:
        load_radar_intelligence(force_refresh=True)
        print("===== RADAR INTELLIGENCE CACHE PRELOADED =====")
    except Exception as e:
        print(f"===== FAILED TO PRELOAD RADAR INTELLIGENCE CACHE: {e} =====")


app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_allowed_origins(),
    allow_origin_regex=_cors_allowed_origin_regex(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(signals.router)
app.include_router(insights.router)
app.include_router(trends.router)
app.include_router(radar.router)
app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(settings.router)
app.include_router(manual.router)
app.include_router(workspace.router)
app.include_router(feed.router)
app.include_router(saved.router)
app.include_router(reflection.router)
app.include_router(decision_cards.router)
app.include_router(reviews.router)
app.include_router(metrics.router)
app.include_router(signal_review_feedback.router)
app.include_router(dev_inbox.router)
app.include_router(final_takeaways.router)
app.include_router(ai_discussion_memory.router)


@app.get("/")
def root():
    return {"message": "hello"}

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/healthz")
def healthz():
    return {"status": "ok"}
