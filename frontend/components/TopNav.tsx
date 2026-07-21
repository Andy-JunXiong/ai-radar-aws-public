"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";

import {
  ADMIN_AUTH_CHANGED_EVENT,
  getAdminLoginPath,
  getStoredAdminToken,
  logoutAdminSession,
  verifyAdminSession,
} from "@/lib/adminAuth";

const navItems = [
  { label: "Admin", href: "/admin" },
  { label: "Dashboard", href: "/dashboard" },
  { label: "Signals", href: "/signals" },
  { label: "Knowledge", href: "/knowledge" },
  { label: "Radar", href: "/radar" },
  { label: "Agent Watch", href: "/agent-watch" },
  { label: "Friction", href: "/friction-signals" },
  { label: "Reflections", href: "/reflections" },
  { label: "Workspace", href: "/workspace" },
  { label: "Dev Inbox", href: "/codex-workbench" },
  { label: "Manual Upload", href: "/manual" },
];

type BackgroundTheme = "light" | "deep";

const BACKGROUND_THEME_STORAGE_KEY = "ai-radar-bg-theme";

export default function TopNav() {
  const pathname = usePathname();
  const router = useRouter();
  const [hasAdminSession, setHasAdminSession] = useState(false);
  const [loggingOut, setLoggingOut] = useState(false);
  const [backgroundTheme, setBackgroundTheme] = useState<BackgroundTheme>("light");

  const isActive = (href: string) => {
    if (href === "/") return pathname === "/";
    return pathname === href || pathname.startsWith(href + "/");
  };

  useEffect(() => {
    let active = true;

    async function refreshSessionState() {
      const token = getStoredAdminToken();
      if (!token) {
        if (!active) return;
        setHasAdminSession(false);
        return;
      }

      const authenticated = await verifyAdminSession();
      if (!active) return;
      setHasAdminSession(authenticated);
    }

    void refreshSessionState();

    const handleAuthChange = () => {
      void refreshSessionState();
    };

    window.addEventListener(ADMIN_AUTH_CHANGED_EVENT, handleAuthChange);
    return () => {
      active = false;
      window.removeEventListener(ADMIN_AUTH_CHANGED_EVENT, handleAuthChange);
    };
  }, [pathname]);

  useEffect(() => {
    const storedTheme =
      typeof window !== "undefined"
        ? window.localStorage.getItem(BACKGROUND_THEME_STORAGE_KEY)
        : null;
    const nextTheme = storedTheme === "deep" ? "deep" : "light";
    setBackgroundTheme(nextTheme);
    document.documentElement.dataset.bgTheme = nextTheme;
  }, []);

  const loginHref = getAdminLoginPath(pathname || "/admin");

  async function handleLogout() {
    setLoggingOut(true);
    try {
      await logoutAdminSession();
      router.replace(getAdminLoginPath(pathname || "/admin"));
    } finally {
      setLoggingOut(false);
    }
  }

  function handleBackgroundThemeChange(nextTheme: BackgroundTheme) {
    setBackgroundTheme(nextTheme);
    document.documentElement.dataset.bgTheme = nextTheme;
    try {
      window.localStorage.setItem(BACKGROUND_THEME_STORAGE_KEY, nextTheme);
    } catch {
      // Ignore storage failures; the theme still applies for this session.
    }
  }

  return (
    <header
      style={{
        position: "sticky",
        top: 0,
        zIndex: 100,
        backdropFilter: "blur(14px)",
        WebkitBackdropFilter: "blur(14px)",
        background: "var(--app-nav-bg)",
        borderBottom: "1px solid var(--app-nav-border)",
      }}
    >
      <div
        style={{
          width: "100%",
          boxSizing: "border-box",
          margin: "0 auto",
          padding: "12px clamp(24px, 4vw, 72px)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          position: "relative",
          minWidth: 0,
        }}
      >
        <div style={topNavThemeSlotStyle}>
          <div style={themeSegmentStyle} aria-label="Background theme">
            <button
              type="button"
              onClick={() => handleBackgroundThemeChange("light")}
              style={themeButtonStyle(backgroundTheme === "light")}
            >
              Light
            </button>
            <button
              type="button"
              onClick={() => handleBackgroundThemeChange("deep")}
              style={themeButtonStyle(backgroundTheme === "deep")}
            >
              Navy
            </button>
          </div>
        </div>

        <div style={topNavMainStyle}>
          <div
            style={{
              fontSize: "20px",
              fontWeight: 700,
              color: "var(--app-nav-brand)",
              whiteSpace: "nowrap",
              flex: "0 0 auto",
            }}
          >
            <Link href="/" style={{ color: "inherit", textDecoration: "none" }}>
              AI Radar
            </Link>
          </div>

          <nav
            style={{
              display: "flex",
              alignItems: "center",
              gap: "9px",
              flex: "0 1 auto",
              flexWrap: "nowrap",
              overflowX: "auto",
              overflowY: "hidden",
              minWidth: 0,
              scrollbarWidth: "thin",
              whiteSpace: "nowrap",
              paddingBottom: "2px",
            }}
          >
            {navItems.map((item) => {
              const active = isActive(item.href);

              return (
                <Link
                  key={item.href}
                  href={item.href}
                  style={{
                    textDecoration: "none",
                    padding: "10px 14px",
                    borderRadius: "999px",
                    fontSize: "15px",
                    fontWeight: active ? 700 : 500,
                    color: active ? "var(--app-nav-link-active)" : "var(--app-nav-link)",
                    background: active ? "var(--app-nav-link-active-bg)" : "transparent",
                    border: active
                      ? "1px solid var(--app-nav-link-active-border)"
                      : "1px solid transparent",
                    transition: "all 0.2s ease",
                    flex: "0 0 auto",
                  }}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>
        </div>

        <div style={topNavUtilityStyle}>
          <Link href="/architecture" style={architectureLinkStyle}>
            Architecture
          </Link>
          {hasAdminSession ? (
            <>
              <Link href="/admin/access" style={sessionPillStyle}>
                Logged in
              </Link>
              <button
                type="button"
                onClick={() => void handleLogout()}
                disabled={loggingOut}
                style={{
                  ...logoutButtonStyle,
                  cursor: loggingOut ? "not-allowed" : "pointer",
                  opacity: loggingOut ? 0.7 : 1,
                }}
              >
                {loggingOut ? "Logging out..." : "Log out"}
              </button>
            </>
          ) : (
            <Link href={loginHref} style={loginLinkStyle}>
              Log in
            </Link>
          )}
        </div>
      </div>
    </header>
  );
}

const topNavThemeSlotStyle = {
  display: "flex",
  alignItems: "center",
  position: "absolute",
  left: "clamp(24px, 4vw, 72px)",
  top: "50%",
  transform: "translateY(-50%)",
} as const;

const topNavMainStyle = {
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  gap: "16px",
  minWidth: 0,
  maxWidth: "100%",
} as const;

const topNavUtilityStyle = {
  display: "flex",
  alignItems: "center",
  gap: "8px",
  position: "absolute",
  right: "clamp(12px, 2vw, 36px)",
  top: "50%",
  transform: "translateY(-50%)",
} as const;

const themeSegmentStyle = {
  display: "inline-flex",
  alignItems: "center",
  gap: "2px",
  border: "1px solid var(--app-surface-border)",
  borderRadius: "999px",
  background: "var(--app-surface-muted-bg)",
  padding: "2px",
} as const;

const themeButtonStyle = (active: boolean) =>
  ({
    border: active ? "1px solid var(--app-primary-action-border)" : "1px solid transparent",
    borderRadius: "999px",
    background: active ? "var(--app-primary-action-bg)" : "transparent",
    color: active ? "var(--app-primary-action-fg)" : "var(--app-text-muted)",
    padding: "7px 10px",
    fontSize: "13px",
    fontWeight: 800,
    cursor: "pointer",
  }) as const;

const architectureLinkStyle = {
  border: "1px solid var(--app-info-border)",
  borderRadius: "999px",
  background: "var(--app-info-bg)",
  color: "var(--app-info-fg)",
  padding: "8px 11px",
  fontSize: "13px",
  fontWeight: 700,
  textDecoration: "none",
  whiteSpace: "nowrap" as const,
} as const;

const sessionPillStyle = {
  border: "1px solid var(--app-success-border)",
  borderRadius: "999px",
  background: "var(--app-success-bg)",
  color: "var(--app-success-fg)",
  padding: "8px 11px",
  fontSize: "12px",
  fontWeight: 700,
  textDecoration: "none",
  whiteSpace: "nowrap" as const,
} as const;

const loginLinkStyle = {
  border: "1px solid var(--app-primary-action-border)",
  borderRadius: "999px",
  background: "var(--app-primary-action-bg)",
  color: "var(--app-primary-action-fg)",
  padding: "8px 11px",
  fontSize: "13px",
  fontWeight: 700,
  textDecoration: "none",
  whiteSpace: "nowrap" as const,
} as const;

const logoutButtonStyle = {
  border: "1px solid var(--app-secondary-action-border)",
  borderRadius: "999px",
  background: "var(--app-secondary-action-bg)",
  color: "var(--app-secondary-action-fg)",
  padding: "8px 11px",
  fontSize: "13px",
  fontWeight: 700,
  whiteSpace: "nowrap" as const,
} as const;
