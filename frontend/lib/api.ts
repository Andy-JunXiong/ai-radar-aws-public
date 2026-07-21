const DEV_API_BASE = "http://127.0.0.1:8000";

const rawApiBase =
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  process.env.NEXT_PUBLIC_API_BASE ||
  (process.env.NODE_ENV === "development" ? DEV_API_BASE : "");

export const API_BASE = rawApiBase.replace(/\/$/, "");

export function apiUrl(path: string): string {
  if (!API_BASE) {
    throw new Error(
      "NEXT_PUBLIC_API_BASE_URL is required in production for static frontend builds.",
    );
  }

  if (!path) {
    return API_BASE;
  }

  if (/^https?:\/\//i.test(path)) {
    return path;
  }

  return `${API_BASE}${path.startsWith("/") ? path : `/${path}`}`;
}
