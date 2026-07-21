import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional

import boto3

from app.context.context_builder import load_personal_context


def generate_manual_session_id() -> str:
    """
    Generate session id like:
    manual_20260325_103500
    """
    return "manual_" + datetime.now().strftime("%Y%m%d_%H%M%S")


def get_personal_context_snapshot(
    personal_context_snapshot: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Return the provided snapshot if available.
    Otherwise load the latest personal context from app/context/personal_context.json.

    This ensures every saved manual session can carry a context snapshot,
    even if the caller does not explicitly pass one.
    """
    if personal_context_snapshot is not None:
        return personal_context_snapshot

    try:
        return load_personal_context()
    except Exception:
        return {}


def build_manual_session_payload(
    title: str,
    instruction: str,
    uploaded_files: List[Dict[str, Any]],
    personal_context_snapshot: Optional[Dict[str, Any]] = None,
    summary: str = "",
    insights_for_me: str = "",
    project_takeaways: str = "",
    career_takeaways: str = "",
    reflection: str = "",
    extracted_signals: Optional[List[Dict[str, Any]]] = None,
    raw_response: str = "",
    status: str = "completed",
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Build the session.json payload for manual analysis sessions.
    """
    if not session_id:
        session_id = generate_manual_session_id()

    personal_context_snapshot = get_personal_context_snapshot(
        personal_context_snapshot
    )

    if extracted_signals is None:
        extracted_signals = []

    payload = {
        "session_id": session_id,
        "created_at": datetime.now().astimezone().isoformat(),
        "title": title,
        "source_mode": "manual_upload",
        "uploaded_files": uploaded_files,
        "instruction": instruction,
        "personal_context_snapshot": personal_context_snapshot,
        "summary": summary,
        "insights_for_me": insights_for_me,
        "project_takeaways": project_takeaways,
        "career_takeaways": career_takeaways,
        "reflection": reflection,
        "extracted_signals": extracted_signals,
        "raw_response": raw_response,
        "status": status,
    }
    return payload


def save_manual_session_to_s3(
    bucket_name: str,
    session_payload: Dict[str, Any],
    aws_region: str = "us-east-1",
) -> str:
    """
    Save session payload to:
    manual_sessions/{session_id}/session.json
    """
    session_id = session_payload["session_id"]
    s3_key = f"manual_sessions/{session_id}/session.json"

    s3_client = boto3.client("s3", region_name=aws_region)

    s3_client.put_object(
        Bucket=bucket_name,
        Key=s3_key,
        Body=json.dumps(session_payload, ensure_ascii=False, indent=2).encode("utf-8"),
        ContentType="application/json",
    )

    return s3_key


def upload_manual_file_to_s3(
    bucket_name: str,
    session_id: str,
    file_name: str,
    file_bytes: bytes,
    aws_region: str = "us-east-1",
) -> Dict[str, Any]:
    """
    Upload one manual source file to:
    manual_uploads/{session_id}/source_files/{file_name}

    Returns uploaded file metadata for session.json
    """
    s3_client = boto3.client("s3", region_name=aws_region)

    s3_key = f"manual_uploads/{session_id}/source_files/{file_name}"

    content_type = "application/octet-stream"
    lower_name = file_name.lower()

    if lower_name.endswith(".pdf"):
        content_type = "application/pdf"
    elif lower_name.endswith(".png"):
        content_type = "image/png"
    elif lower_name.endswith(".jpg") or lower_name.endswith(".jpeg"):
        content_type = "image/jpeg"
    elif lower_name.endswith(".txt"):
        content_type = "text/plain"
    elif lower_name.endswith(".md"):
        content_type = "text/markdown"
    elif lower_name.endswith(".json"):
        content_type = "application/json"

    s3_client.put_object(
        Bucket=bucket_name,
        Key=s3_key,
        Body=file_bytes,
        ContentType=content_type,
    )

    file_ext = os.path.splitext(file_name)[1].lower().replace(".", "")
    file_type = file_ext if file_ext else "unknown"

    return {
        "file_name": file_name,
        "file_type": file_type,
        "s3_key": s3_key,
    }


def load_json_from_s3(
    bucket_name: str,
    s3_key: str,
    aws_region: str = "us-east-1",
) -> Dict[str, Any]:
    """
    Load JSON object from S3.
    Return {} if not exists.
    """
    s3_client = boto3.client("s3", region_name=aws_region)

    try:
        response = s3_client.get_object(Bucket=bucket_name, Key=s3_key)
        content = response["Body"].read().decode("utf-8")
        return json.loads(content)
    except s3_client.exceptions.NoSuchKey:
        return {}
    except Exception:
        return {}


def save_json_to_s3(
    bucket_name: str,
    s3_key: str,
    data: Dict[str, Any],
    aws_region: str = "us-east-1",
) -> None:
    """
    Save JSON object to S3.
    """
    s3_client = boto3.client("s3", region_name=aws_region)

    s3_client.put_object(
        Bucket=bucket_name,
        Key=s3_key,
        Body=json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"),
        ContentType="application/json",
    )


def update_manual_latest_sessions(
    bucket_name: str,
    session_payload: Dict[str, Any],
    aws_region: str = "us-east-1",
    latest_key: str = "manual_latest/latest_sessions.json",
    max_sessions: int = 20,
) -> str:
    """
    Update latest manual sessions index in S3.
    """
    latest_data = load_json_from_s3(
        bucket_name=bucket_name,
        s3_key=latest_key,
        aws_region=aws_region,
    )

    latest_sessions = latest_data.get("latest_sessions", [])
    uploaded_files = session_payload.get("uploaded_files", [])

    thumbnail = ""
    if uploaded_files:
        thumbnail = uploaded_files[0].get("s3_key", "")

    session_item = {
        "session_id": session_payload.get("session_id", ""),
        "title": session_payload.get("title", ""),
        "created_at": session_payload.get("created_at", ""),
        "summary": session_payload.get("summary", ""),
        "thumbnail": thumbnail,
        "files_count": len(uploaded_files),
        "status": session_payload.get("status", "completed"),
    }

    # Remove duplicate if the same session_id already exists
    latest_sessions = [
        item for item in latest_sessions
        if item.get("session_id") != session_item["session_id"]
    ]

    # Put newest first
    latest_sessions.insert(0, session_item)

    # Keep at most max_sessions
    latest_sessions = latest_sessions[:max_sessions]

    save_json_to_s3(
        bucket_name=bucket_name,
        s3_key=latest_key,
        data={"latest_sessions": latest_sessions},
        aws_region=aws_region,
    )

    return latest_key