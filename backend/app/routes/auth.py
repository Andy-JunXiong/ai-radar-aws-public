import os

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from app.services.admin_auth import (
    add_admin_token,
    create_admin_account,
    has_admin_account,
    is_valid_admin_token,
    issue_admin_token,
    load_admin_auth_payload,
    remove_admin_token,
    verify_password,
)


router = APIRouter()


class AdminSetupRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=6)


class AdminLoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class AdminPasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=6)


@router.get("/auth/status")
def auth_status():
    payload = load_admin_auth_payload()
    return {
        "has_admin_account": has_admin_account(),
        "username": payload.get("username") or "",
    }


@router.post("/auth/setup")
def auth_setup(payload: AdminSetupRequest, x_ai_radar_setup_secret: str | None = Header(default=None)):
    if has_admin_account():
        raise HTTPException(status_code=400, detail="Admin account already exists.")
    expected_secret = str(os.getenv("ADMIN_SETUP_SECRET", "")).strip()
    if not expected_secret or x_ai_radar_setup_secret != expected_secret:
        raise HTTPException(status_code=403, detail="Admin setup is disabled.")

    create_admin_account(payload.username, payload.password)
    return {"message": "Admin account created successfully."}


@router.post("/auth/login")
def auth_login(payload: AdminLoginRequest):
    auth_payload = load_admin_auth_payload()

    if not has_admin_account():
        raise HTTPException(status_code=400, detail="Admin account is not configured yet.")

    if payload.username.strip() != str(auth_payload.get("username") or "").strip():
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    if not verify_password(payload.password, auth_payload):
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    token = issue_admin_token()
    add_admin_token(token)
    return {"message": "Login successful.", "token": token, "username": auth_payload.get("username")}


@router.get("/auth/verify")
def auth_verify(x_ai_radar_admin_token: str | None = Header(default=None)):
    return {
        "authenticated": is_valid_admin_token(x_ai_radar_admin_token),
    }


@router.post("/auth/logout")
def auth_logout(x_ai_radar_admin_token: str | None = Header(default=None)):
    if x_ai_radar_admin_token:
        remove_admin_token(x_ai_radar_admin_token)
    return {"message": "Logged out."}


@router.post("/auth/change-password")
def auth_change_password(
    payload: AdminPasswordChangeRequest,
    x_ai_radar_admin_token: str | None = Header(default=None),
):
    if not is_valid_admin_token(x_ai_radar_admin_token):
        raise HTTPException(status_code=401, detail="Admin authentication required.")

    auth_payload = load_admin_auth_payload()
    if not verify_password(payload.current_password, auth_payload):
        raise HTTPException(status_code=401, detail="Current password is incorrect.")

    create_admin_account(str(auth_payload.get("username") or "admin"), payload.new_password)

    return {"message": "Password updated successfully. Please sign in again."}
