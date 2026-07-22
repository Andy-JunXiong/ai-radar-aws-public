const PUBLIC_CONTENT_ROUTES = new Set(["/", "/portfolio"]);

export function normalizeRoutePath(pathname: string): string {
  if (!pathname) return "/";
  if (pathname === "/") return pathname;
  return pathname.replace(/\/+$/, "") || "/";
}

export function isPublicRoute(pathname: string): boolean {
  return PUBLIC_CONTENT_ROUTES.has(normalizeRoutePath(pathname));
}

export function isLoginRoute(pathname: string): boolean {
  return normalizeRoutePath(pathname) === "/login";
}
