"use client";

const BETA_USER_ID_KEY = "ai-radar-beta-user-id";

export function getStoredBetaUserId(): string {
  if (typeof window === "undefined") {
    return "";
  }

  return window.localStorage.getItem(BETA_USER_ID_KEY) || "";
}

export function setStoredBetaUserId(userId: string): void {
  if (typeof window === "undefined") {
    return;
  }

  const normalized = userId.trim();
  if (!normalized) {
    window.localStorage.removeItem(BETA_USER_ID_KEY);
    return;
  }

  window.localStorage.setItem(BETA_USER_ID_KEY, normalized);
}

export function buildBetaUserHeaders(userId?: string): HeadersInit {
  const normalized = (userId || "").trim();
  if (!normalized) {
    return {};
  }

  return {
    "x-ai-radar-user-id": normalized,
  };
}
