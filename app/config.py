import os
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv


# Project root directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env
load_dotenv(BASE_DIR / ".env")


class Settings:
    def __init__(self) -> None:
        # ===== API =====
        self.openai_api_key: str | None = os.getenv("OPENAI_API_KEY")

        # ===== AWS =====
        self.aws_region: str = os.getenv("AWS_REGION", "ap-southeast-2")
        self.s3_bucket: str = os.getenv("S3_BUCKET") or os.getenv("AI_RADAR_S3_BUCKET", "")

        # ===== Radar Config =====
        self.radar_time_window_hours: int = int(
            os.getenv("RADAR_TIME_WINDOW_HOURS", "24")
        )
        self.max_signals_per_run: int = int(
            os.getenv("MAX_SIGNALS_PER_RUN", "20")
        )

        # ===== Timezone =====
        self.radar_timezone: str = os.getenv("RADAR_TIMEZONE", "Australia/Sydney")
        self.timezone = ZoneInfo(self.radar_timezone)

        # ===== Model =====
        self.llm_model: str = os.getenv("LLM_MODEL", "gpt-4o-mini")

        # ===== Logging =====
        self.log_level: str = os.getenv("LOG_LEVEL", "INFO")

    def validate(self) -> None:
        """Check that required configuration is present."""
        missing = []

        if not self.openai_api_key:
            missing.append("OPENAI_API_KEY")

        if not self.s3_bucket:
            missing.append("S3_BUCKET")

        if missing:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing)}"
            )


settings = Settings()
