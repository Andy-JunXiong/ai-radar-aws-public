"use client";

import { apiUrl } from "@/lib/api";

const ADMIN_TOKEN_KEY = "ai-radar-admin-token";
const ADMIN_TOKEN_VERIFIED_AT_KEY = "ai-radar-admin-token-verified-at";
const ADMIN_SESSION_IDLE_TIMEOUT_MS = 60 * 60 * 1000;
export const ADMIN_UNAUTHORIZED_EVENT = "ai-radar-admin-unauthorized";
export const ADMIN_AUTH_CHANGED_EVENT = "ai-radar-admin-auth-changed";

export function getAdminLoginPath(nextPath?: string): string {
  const fallbackPath =
    typeof window === "undefined"
      ? "/admin"
      : `${window.location.pathname}${window.location.search}`;
  const resolvedNext = nextPath || fallbackPath || "/admin";
  return `/login/?next=${encodeURIComponent(resolvedNext)}`;
}

export function getStoredAdminToken(): string {
  if (typeof window === "undefined") return "";
  return window.localStorage.getItem(ADMIN_TOKEN_KEY) || window.sessionStorage.getItem(ADMIN_TOKEN_KEY) || "";
}

export function setStoredAdminToken(token: string): void {
  if (typeof window === "undefined") return;
  const normalized = token.trim();
  if (!normalized) {
    window.localStorage.removeItem(ADMIN_TOKEN_KEY);
    window.sessionStorage.removeItem(ADMIN_TOKEN_KEY);
    window.localStorage.removeItem(ADMIN_TOKEN_VERIFIED_AT_KEY);
    window.sessionStorage.removeItem(ADMIN_TOKEN_VERIFIED_AT_KEY);
    window.dispatchEvent(new CustomEvent(ADMIN_AUTH_CHANGED_EVENT));
    return;
  }
  // Keep the token visible to newly opened tabs; backend idle timeout remains
  // the source of truth for whether the token is still valid.
  window.localStorage.setItem(ADMIN_TOKEN_KEY, normalized);
  window.sessionStorage.setItem(ADMIN_TOKEN_KEY, normalized);
  markStoredAdminTokenVerified();
  window.dispatchEvent(new CustomEvent(ADMIN_AUTH_CHANGED_EVENT));
}

export function clearStoredAdminToken(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(ADMIN_TOKEN_KEY);
  window.sessionStorage.removeItem(ADMIN_TOKEN_KEY);
  window.localStorage.removeItem(ADMIN_TOKEN_VERIFIED_AT_KEY);
  window.sessionStorage.removeItem(ADMIN_TOKEN_VERIFIED_AT_KEY);
  window.dispatchEvent(new CustomEvent(ADMIN_AUTH_CHANGED_EVENT));
}

function markStoredAdminTokenVerified(): void {
  if (typeof window === "undefined") return;
  const value = String(Date.now());
  window.localStorage.setItem(ADMIN_TOKEN_VERIFIED_AT_KEY, value);
  window.sessionStorage.setItem(ADMIN_TOKEN_VERIFIED_AT_KEY, value);
}

function hasRecentlyVerifiedAdminToken(): boolean {
  if (typeof window === "undefined") return false;
  const raw =
    window.localStorage.getItem(ADMIN_TOKEN_VERIFIED_AT_KEY) ||
    window.sessionStorage.getItem(ADMIN_TOKEN_VERIFIED_AT_KEY) ||
    "";
  const verifiedAt = Number(raw);
  return Number.isFinite(verifiedAt) && Date.now() - verifiedAt <= ADMIN_SESSION_IDLE_TIMEOUT_MS;
}

export function redirectToAdminLogin(nextPath?: string): void {
  if (typeof window === "undefined") return;
  if (window.location.pathname === "/login" || window.location.pathname === "/login/") return;
  window.location.replace(getAdminLoginPath(nextPath));
}

export function buildAdminAuthHeaders(): HeadersInit {
  const token = getStoredAdminToken();
  if (!token) return {};
  return {
    "x-ai-radar-admin-token": token,
  };
}

export function handleAdminUnauthorizedStatus(status: number): void {
  if (status !== 401 && status !== 403) return;
  clearStoredAdminToken();
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent(ADMIN_UNAUTHORIZED_EVENT));
    redirectToAdminLogin();
  }
}

export async function adminFetch(input: RequestInfo | URL, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers || {});
  const adminHeaders = buildAdminAuthHeaders();

  for (const [key, value] of Object.entries(adminHeaders)) {
    headers.set(key, value);
  }

  const response = await fetch(input, {
    ...init,
    headers,
  });
  handleAdminUnauthorizedStatus(response.status);
  return response;
}

export async function logoutAdminSession(): Promise<void> {
  const token = getStoredAdminToken();

  try {
    if (token) {
      await fetch(apiUrl("/auth/logout"), {
        method: "POST",
        headers: buildAdminAuthHeaders(),
      });
    }
  } finally {
    clearStoredAdminToken();
  }
}

export async function verifyAdminSession(): Promise<boolean> {
  const token = getStoredAdminToken();
  if (!token) return false;
  if (hasRecentlyVerifiedAdminToken()) return true;

  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), 8000);

  try {
    const response = await adminFetch(apiUrl("/auth/verify"), {
      cache: "no-store",
      signal: controller.signal,
    });
    if (!response.ok) return false;
    const data = (await response.json()) as { authenticated?: boolean };
    const authenticated = Boolean(data.authenticated);
    if (authenticated) {
      markStoredAdminTokenVerified();
    } else {
      clearStoredAdminToken();
    }
    return authenticated;
  } catch {
    return hasRecentlyVerifiedAdminToken();
  } finally {
    window.clearTimeout(timeoutId);
  }
}
