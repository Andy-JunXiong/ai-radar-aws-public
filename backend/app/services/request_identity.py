from typing import Optional

from app.services.admin_auth import is_valid_admin_token


USER_ID_HEADER_CANDIDATES = (
    "x-ai-radar-user-id",
    "x-user-id",
)


def _normalize_user_id(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None

    normalized = str(value).strip()
    return normalized or None


def resolve_request_user_id(request) -> Optional[str]:
    if request is None:
        return None

    headers = getattr(request, "headers", None)
    if headers is None:
        return None

    for header_name in USER_ID_HEADER_CANDIDATES:
        explicit_user_id = _normalize_user_id(headers.get(header_name))
        if explicit_user_id:
            return explicit_user_id

    admin_token = _normalize_user_id(headers.get("x-ai-radar-admin-token"))
    if is_valid_admin_token(admin_token):
        return "admin_default"

    return None
