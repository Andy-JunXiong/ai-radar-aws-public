import hashlib
import json
import secrets
import os
import time
from pathlib import Path
from typing import Any

import boto3
from botocore.config import Config


LEGACY_AUTH_FILE = Path(__file__).resolve().parents[2] / "data" / "auth" / "admin_auth.json"
AWS_REGION = os.getenv("AWS_REGION", "ap-southeast-2")
DEFAULT_S3_BUCKET = "ai-radar-junxiong-data"
ADMIN_AUTH_S3_KEY = (
    os.getenv("ADMIN_AUTH_S3_KEY")
    or os.getenv("AI_RADAR_ADMIN_AUTH_S3_KEY")
    or "settings/admin_auth.json"
).strip().lstrip("/")


def _resolve_auth_dir() -> Path:
    configured = str(os.getenv("AI_RADAR_ADMIN_AUTH_DIR", "")).strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return Path.home() / ".ai-radar" / "auth"


AUTH_DIR = _resolve_auth_dir()
AUTH_FILE = AUTH_DIR / "admin_auth.json"
ACTIVE_TOKENS: set[str] = set()
ADMIN_SESSION_IDLE_TIMEOUT_SECONDS = 60 * 60


def _ensure_auth_dir() -> None:
    AUTH_DIR.mkdir(parents=True, exist_ok=True)


def _s3_bucket() -> str:
    return (
        os.getenv("S3_BUCKET")
        or os.getenv("AI_RADAR_S3_BUCKET")
        or DEFAULT_S3_BUCKET
    ).strip()


def _s3_auth_enabled() -> bool:
    value = str(os.getenv("AI_RADAR_AUTH_S3_ENABLED", "")).strip().lower()
    if value:
        return value not in {"0", "false", "no", "off"}
    return bool(
        os.getenv("AWS_EXECUTION_ENV")
        or os.getenv("ECS_CONTAINER_METADATA_URI")
        or os.getenv("ECS_CONTAINER_METADATA_URI_V4")
    )


def _s3_client():
    if not _s3_auth_enabled():
        return None
    if not _s3_bucket():
        return None
    try:
        return boto3.client(
            "s3",
            region_name=AWS_REGION,
            config=Config(
                connect_timeout=1,
                read_timeout=2,
                retries={"max_attempts": 1},
            ),
        )
    except Exception:
        return None


def _default_payload() -> dict[str, Any]:
    return {
        "username": "",
        "password_hash": "",
        "salt": "",
        "tokens": [],
    }


def _now() -> float:
    return time.time()


def _token_value(item: Any) -> str:
    if isinstance(item, dict):
        return str(item.get("token") or "").strip()
    return ""


def _coerce_timestamp(value: Any) -> float | None:
    try:
        coerced = float(value)
    except (TypeError, ValueError):
        return None
    return coerced if coerced > 0 else None


def _normalize_token_session(item: Any) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None

    token = _token_value(item)
    if not token:
        return None

    issued_at = _coerce_timestamp(item.get("issued_at"))
    last_seen_at = _coerce_timestamp(item.get("last_seen_at"))
    if issued_at is None or last_seen_at is None:
        return None

    return {
        "token": token,
        "issued_at": issued_at,
        "last_seen_at": last_seen_at,
    }


def _is_token_session_active(session: dict[str, Any], now: float | None = None) -> bool:
    token = _token_value(session)
    last_seen_at = _coerce_timestamp(session.get("last_seen_at"))
    if not token or last_seen_at is None:
        return False
    return (_now() if now is None else now) - last_seen_at <= ADMIN_SESSION_IDLE_TIMEOUT_SECONDS


def _normalize_token_sessions(items: Any) -> list[dict[str, Any]]:
    now = _now()
    sessions = [
        session
        for session in (_normalize_token_session(item) for item in (items or []))
        if session is not None and _is_token_session_active(session, now)
    ]
    sessions.sort(key=lambda item: float(item.get("last_seen_at") or 0))
    return sessions[-12:]


def _normalize_payload(data: Any) -> dict[str, Any] | None:
    if not isinstance(data, dict):
        return None

    payload = _default_payload()
    payload.update(data)
    payload["tokens"] = _normalize_token_sessions(payload.get("tokens"))
    return payload


def _loads_auth_json(raw: str) -> dict[str, Any] | None:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        try:
            payload, _ = json.JSONDecoder().raw_decode(raw.lstrip("\ufeff \t\r\n"))
        except json.JSONDecodeError:
            return None
    return _normalize_payload(payload)


def _read_s3_payload() -> dict[str, Any] | None:
    client = _s3_client()
    bucket = _s3_bucket()
    if client is None or not bucket or not ADMIN_AUTH_S3_KEY:
        return None

    try:
        response = client.get_object(Bucket=bucket, Key=ADMIN_AUTH_S3_KEY)
        raw = response["Body"].read().decode("utf-8-sig")
        return _loads_auth_json(raw)
    except Exception:
        return None


def _write_s3_payload(payload: dict[str, Any]) -> None:
    client = _s3_client()
    bucket = _s3_bucket()
    if client is None or not bucket or not ADMIN_AUTH_S3_KEY:
        return

    client.put_object(
        Bucket=bucket,
        Key=ADMIN_AUTH_S3_KEY,
        Body=json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"),
        ContentType="application/json; charset=utf-8",
    )


def _write_json_file_atomic(path: Path, payload: dict[str, Any]) -> None:
    _ensure_auth_dir()
    tmp_path = path.with_name(f".{path.name}.{os.getpid()}.{time.time_ns()}.tmp")
    tmp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    tmp_path.replace(path)


def _activate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    ACTIVE_TOKENS.clear()
    ACTIVE_TOKENS.update(_token_value(session) for session in payload["tokens"])
    return payload


def load_admin_auth_payload() -> dict[str, Any]:
    _ensure_auth_dir()
    source_files = [AUTH_FILE]
    if LEGACY_AUTH_FILE not in source_files:
        source_files.append(LEGACY_AUTH_FILE)

    s3_payload = _read_s3_payload()
    if s3_payload is not None:
        try:
            _write_json_file_atomic(AUTH_FILE, s3_payload)
        except Exception:
            pass
        return _activate_payload(s3_payload)

    for path in source_files:
        if not path.exists():
            continue
        try:
            payload = _loads_auth_json(path.read_text(encoding="utf-8-sig"))
            if payload is not None:
                return _activate_payload(payload)
        except Exception:
            continue

    return _default_payload()


def save_admin_auth_payload(payload: dict[str, Any]) -> None:
    persisted = dict(payload)
    persisted["tokens"] = _normalize_token_sessions(payload.get("tokens"))
    _write_json_file_atomic(AUTH_FILE, persisted)
    try:
        _write_s3_payload(persisted)
    except Exception:
        pass


def has_admin_account() -> bool:
    payload = load_admin_auth_payload()
    return bool(payload.get("username")) and bool(payload.get("password_hash"))


def _has_admin_account_payload(payload: dict[str, Any]) -> bool:
    return bool(payload.get("username")) and bool(payload.get("password_hash"))


def hash_password(password: str, salt: str) -> str:
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        120000,
    )
    return derived.hex()


def verify_password(password: str, payload: dict[str, Any]) -> bool:
    salt = str(payload.get("salt") or "")
    stored_hash = str(payload.get("password_hash") or "")
    if not salt or not stored_hash:
        return False
    return hash_password(password, salt) == stored_hash


def create_admin_account(username: str, password: str) -> dict[str, Any]:
    salt = secrets.token_hex(16)
    payload = {
        "username": username.strip(),
        "password_hash": hash_password(password, salt),
        "salt": salt,
        "tokens": [],
    }
    ACTIVE_TOKENS.clear()
    save_admin_auth_payload(payload)
    return payload


def issue_admin_token() -> str:
    return secrets.token_urlsafe(32)


def add_admin_token(token: str) -> None:
    now = _now()
    ACTIVE_TOKENS.add(token)
    while len(ACTIVE_TOKENS) > 12:
        ACTIVE_TOKENS.pop()
    payload = load_admin_auth_payload()
    if not _has_admin_account_payload(payload):
        return
    tokens = [
        item
        for item in _normalize_token_sessions(payload.get("tokens"))
        if _token_value(item) != token
    ]
    tokens.append({"token": token, "issued_at": now, "last_seen_at": now})
    payload["tokens"] = tokens[-12:]
    save_admin_auth_payload(payload)


def remove_admin_token(token: str) -> None:
    if token in ACTIVE_TOKENS:
        ACTIVE_TOKENS.remove(token)
    payload = load_admin_auth_payload()
    if not _has_admin_account_payload(payload):
        return
    payload["tokens"] = [
        item
        for item in _normalize_token_sessions(payload.get("tokens"))
        if _token_value(item) != token
    ]
    save_admin_auth_payload(payload)


def is_valid_admin_token(token: str | None) -> bool:
    if not token:
        return False

    now = _now()
    payload = load_admin_auth_payload()
    sessions = _normalize_token_sessions(payload.get("tokens"))
    matched = False

    for session in sessions:
        if _token_value(session) == token and _is_token_session_active(session, now):
            session["last_seen_at"] = now
            matched = True
            break

    if not matched:
        if token in ACTIVE_TOKENS:
            ACTIVE_TOKENS.remove(token)
        if not _has_admin_account_payload(payload):
            return False
        payload["tokens"] = sessions
        save_admin_auth_payload(payload)
        return False

    payload["tokens"] = sessions
    save_admin_auth_payload(payload)
    ACTIVE_TOKENS.add(token)
    return True
