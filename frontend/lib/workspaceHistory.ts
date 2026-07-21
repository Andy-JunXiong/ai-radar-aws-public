"use client";

import { apiUrl } from "@/lib/api";
import { adminFetch } from "@/lib/adminAuth";

type WorkspaceHistoryResponse = {
  items?: unknown[];
};

const WORKSPACE_HISTORY_TTL_MS = 30_000;
const WORKSPACE_HISTORY_STORAGE_KEY = "ai-radar.workspace-history-cache";

const workspaceHistoryCache: {
  loadedAt: number;
  items: unknown[];
  promise: Promise<unknown[]> | null;
} = {
  loadedAt: 0,
  items: [],
  promise: null,
};

function hydrateWorkspaceHistoryCacheFromSession(): void {
  if (typeof window === "undefined" || workspaceHistoryCache.items.length > 0) {
    return;
  }

  try {
    const raw = window.sessionStorage.getItem(WORKSPACE_HISTORY_STORAGE_KEY);
    if (!raw) return;

    const parsed = JSON.parse(raw) as { loadedAt?: number; items?: unknown[] } | null;
    if (!parsed || !Array.isArray(parsed.items) || typeof parsed.loadedAt !== "number") {
      return;
    }

    const age = Date.now() - parsed.loadedAt;
    if (age >= WORKSPACE_HISTORY_TTL_MS) {
      window.sessionStorage.removeItem(WORKSPACE_HISTORY_STORAGE_KEY);
      return;
    }

    workspaceHistoryCache.items = parsed.items;
    workspaceHistoryCache.loadedAt = parsed.loadedAt;
  } catch {
    return;
  }
}

function persistWorkspaceHistoryCacheToSession(items: unknown[], loadedAt: number): void {
  if (typeof window === "undefined") {
    return;
  }

  try {
    window.sessionStorage.setItem(
      WORKSPACE_HISTORY_STORAGE_KEY,
      JSON.stringify({
        loadedAt,
        items,
      })
    );
  } catch {
    return;
  }
}

export async function fetchWorkspaceHistoryCached(forceRefresh = false): Promise<unknown[]> {
  hydrateWorkspaceHistoryCacheFromSession();

  const now = Date.now();

  if (!forceRefresh && workspaceHistoryCache.items.length > 0) {
    const age = now - workspaceHistoryCache.loadedAt;
    if (age < WORKSPACE_HISTORY_TTL_MS) {
      return workspaceHistoryCache.items;
    }
  }

  if (!forceRefresh && workspaceHistoryCache.promise) {
    return workspaceHistoryCache.promise;
  }

  workspaceHistoryCache.promise = adminFetch(apiUrl("/workspace_history/summary"), {
    cache: "no-store",
  })
    .then(async (res) => {
      if (!res.ok) {
        throw new Error(`Failed to load workspace history summary (${res.status})`);
      }

      const data = (await res.json().catch(() => null)) as WorkspaceHistoryResponse | null;
      const items = Array.isArray(data?.items) ? data.items : [];

      workspaceHistoryCache.items = items;
      workspaceHistoryCache.loadedAt = Date.now();
      persistWorkspaceHistoryCacheToSession(items, workspaceHistoryCache.loadedAt);
      return items;
    })
    .catch(async () => {
      const res = await adminFetch(apiUrl("/workspace_history"), {
        cache: "no-store",
      });
      if (!res.ok) {
        throw new Error(`Failed to load workspace history (${res.status})`);
      }

      const data = (await res.json().catch(() => null)) as WorkspaceHistoryResponse | null;
      const items = Array.isArray(data?.items) ? data.items : [];

      workspaceHistoryCache.items = items;
      workspaceHistoryCache.loadedAt = Date.now();
      persistWorkspaceHistoryCacheToSession(items, workspaceHistoryCache.loadedAt);
      return items;
    })
    .finally(() => {
      workspaceHistoryCache.promise = null;
    });

  return workspaceHistoryCache.promise;
}

export function getWorkspaceHistoryCachedSnapshot(): unknown[] {
  hydrateWorkspaceHistoryCacheFromSession();

  if (workspaceHistoryCache.items.length === 0) {
    return [];
  }

  return workspaceHistoryCache.items;
}
