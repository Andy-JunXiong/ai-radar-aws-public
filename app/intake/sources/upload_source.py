from datetime import datetime, timezone
import uuid

from intake.schemas import Signal


def build_signal_from_upload(
    file_name: str,
    content: str,
    source_type: str = "upload",
    source: str = "manual_upload",
) -> Signal:
    return Signal(
        id=str(uuid.uuid4()),
        title=file_name,
        url="",
        source=source,
        source_type=source_type,
        published_at=datetime.now(timezone.utc).isoformat(),
        raw_text=content or "",
        clean_text="",
        summary="",
        analysis_input="",
        tags=[],
        why_it_matters_to_me="",
    )