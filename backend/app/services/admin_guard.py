from fastapi import Header, HTTPException

from app.services.admin_auth import is_valid_admin_token


def require_admin_auth(x_ai_radar_admin_token: str | None = Header(default=None)) -> None:
    if not is_valid_admin_token(x_ai_radar_admin_token):
        raise HTTPException(status_code=401, detail="Admin authentication required.")
