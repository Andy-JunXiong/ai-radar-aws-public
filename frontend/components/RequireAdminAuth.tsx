"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";

import {
  ADMIN_UNAUTHORIZED_EVENT,
  getAdminLoginPath,
  getStoredAdminToken,
  verifyAdminSession,
} from "@/lib/adminAuth";

export default function RequireAdminAuth({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const [hasLocalToken, setHasLocalToken] = useState(false);
  const [checking, setChecking] = useState(true);
  const [allowed, setAllowed] = useState(false);
  const [verificationWarning, setVerificationWarning] = useState("");
  const loginHref = pathname ? getAdminLoginPath(pathname) : "/login";

  useEffect(() => {
    let active = true;

    const redirectToLogin = () => {
      setHasLocalToken(false);
      setAllowed(false);
      setChecking(false);
      router.replace(loginHref);
    };

    async function runCheck() {
      setChecking(true);
      const authenticated = await verifyAdminSession();
      if (!active) return;

      if (!authenticated) {
        redirectToLogin();
        return;
      }

      setAllowed(true);
      setChecking(false);
      setVerificationWarning("");
    }

    const startId = window.setTimeout(() => {
      if (!active) return;
      const localToken = getStoredAdminToken();

      if (!localToken) {
        redirectToLogin();
        return;
      }

      setHasLocalToken(true);
      setAllowed(true);
      setChecking(false);
      setVerificationWarning("");
      void runCheck();
    }, 0);

    const handleUnauthorized = () => {
      if (!active) return;
      redirectToLogin();
    };

    window.addEventListener(ADMIN_UNAUTHORIZED_EVENT, handleUnauthorized);
    return () => {
      active = false;
      window.clearTimeout(startId);
      window.removeEventListener(ADMIN_UNAUTHORIZED_EVENT, handleUnauthorized);
    };
  }, [loginHref, pathname, router]);

  if (allowed && hasLocalToken) {
    return (
      <>
        {checking || verificationWarning ? (
          <div
            style={{
              border: "1px solid var(--app-info-border)",
              borderRadius: "8px",
              background: "var(--app-info-bg)",
              color: "var(--app-info-fg)",
              padding: "10px 12px",
              marginBottom: "16px",
              fontSize: "13px",
              fontWeight: 700,
            }}
          >
            {verificationWarning || "Admin verification is running in the background. The page is available while protected actions continue to verify access."}
          </div>
        ) : null}
        {children}
      </>
    );
  }

  if (!allowed) {
    return (
      <div
        style={{
          padding: "40px 0",
          color: "var(--app-text-muted)",
          fontSize: "14px",
        }}
      >
        Admin login is required.
        <a
          href={loginHref}
          style={{
            marginLeft: "8px",
            color: "var(--app-text-strong)",
            fontWeight: 700,
            textDecoration: "none",
          }}
        >
          Open login
        </a>
      </div>
    );
  }

  if (checking) {
    return (
      <div
        aria-busy="true"
        style={{
          padding: "40px 0",
          color: "var(--app-text-muted)",
          fontSize: "14px",
        }}
      />
    );
  }

  return <>{children}</>;
}
