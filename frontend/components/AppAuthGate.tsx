"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";

import {
  ADMIN_AUTH_CHANGED_EVENT,
  getAdminLoginPath,
  getStoredAdminToken,
  verifyAdminSession,
} from "@/lib/adminAuth";
import { isPublicRoute } from "@/lib/publicRoutes";

export default function AppAuthGate({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [checking, setChecking] = useState(true);
  const [allowed, setAllowed] = useState(false);

  const isLoginPage = pathname === "/login" || pathname === "/login/";
  const isPublicPage = isPublicRoute(pathname || "/");

  useEffect(() => {
    let active = true;

    async function verifyAccess() {
      if (isLoginPage || isPublicPage) {
        if (!active) return;
        setAllowed(true);
        setChecking(false);
        return;
      }

      const token = getStoredAdminToken();
      if (!token) {
        if (!active) return;
        setAllowed(false);
        setChecking(false);
        router.replace(getAdminLoginPath(pathname || "/admin"));
        return;
      }

      if (active) {
        setAllowed(true);
        setChecking(false);
      }

      const authenticated = await verifyAdminSession();
      if (!active) return;

      if (!authenticated) {
        setAllowed(false);
        setChecking(false);
        router.replace(getAdminLoginPath(pathname || "/admin"));
        return;
      }

      setAllowed(true);
      setChecking(false);
    }

    void verifyAccess();

    const handleAuthChange = () => {
      void verifyAccess();
    };

    window.addEventListener(ADMIN_AUTH_CHANGED_EVENT, handleAuthChange);
    return () => {
      active = false;
      window.removeEventListener(ADMIN_AUTH_CHANGED_EVENT, handleAuthChange);
    };
  }, [isLoginPage, isPublicPage, pathname, router]);

  if (isLoginPage || isPublicPage) return <>{children}</>;

  if (checking && !allowed) {
    return <div aria-busy="true" style={stateShellStyle} />;
  }

  if (!allowed) {
    return <div aria-busy="true" style={stateShellStyle} />;
  }

  return <>{children}</>;
}

const stateShellStyle = {
  maxWidth: "1320px",
  margin: "0 auto",
  padding: "24px",
  minHeight: "64px",
} as const;
