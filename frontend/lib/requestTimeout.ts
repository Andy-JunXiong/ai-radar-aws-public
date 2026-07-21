"use client";

import { adminFetch } from "@/lib/adminAuth";

export const PAGE_REQUEST_TIMEOUT_MS = 8000;

export function isAbortError(error: unknown) {
  return error instanceof DOMException && error.name === "AbortError";
}

export function createTimeoutController(timeoutMs = PAGE_REQUEST_TIMEOUT_MS) {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs);

  return {
    controller,
    signal: controller.signal,
    clear: () => window.clearTimeout(timeoutId),
    abort: () => {
      window.clearTimeout(timeoutId);
      controller.abort();
    },
  };
}

export async function fetchWithTimeout(input: RequestInfo | URL, init: RequestInit = {}) {
  const timeout = createTimeoutController();

  try {
    return await fetch(input, {
      ...init,
      signal: timeout.signal,
    });
  } finally {
    timeout.clear();
  }
}

export async function adminFetchWithTimeout(input: RequestInfo | URL, init: RequestInit = {}) {
  const timeout = createTimeoutController();

  try {
    return await adminFetch(input, {
      ...init,
      signal: timeout.signal,
    });
  } finally {
    timeout.clear();
  }
}
