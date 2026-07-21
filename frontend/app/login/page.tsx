"use client";

import Link from "next/link";
import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";

import AppContainer from "@/components/AppContainer";
import PageHeader from "@/components/PageHeader";
import SectionCard from "@/components/SectionCard";
import { API_BASE, apiUrl } from "@/lib/api";
import { getStoredAdminToken, setStoredAdminToken, verifyAdminSession } from "@/lib/adminAuth";

export default function LoginPage() {
  return (
    <Suspense fallback={<LoginPageSkeleton />}>
      <LoginPageContent />
    </Suspense>
  );
}

function LoginPageContent() {
  const searchParams = useSearchParams();
  const rawNextPath = searchParams.get("next") || "/admin";
  const nextPath = rawNextPath.startsWith("/") && !rawNextPath.startsWith("//") ? rawNextPath : "/admin";

  const [hasAdminAccount, setHasAdminAccount] = useState(true);
  const [loadingStatus, setLoadingStatus] = useState(true);
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [setupSecret, setSetupSecret] = useState("");
  const [message, setMessage] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [apiStatusMessage, setApiStatusMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    let active = true;
    const token = getStoredAdminToken();
    if (!token) return () => {
      active = false;
    };

    setMessage("Checking existing admin session...");
    verifyAdminSession()
      .then((authenticated) => {
        if (!active) return;
        if (authenticated) {
          window.location.replace(nextPath);
          return;
        }
        setMessage("");
      })
      .catch(() => {
        if (!active) return;
        setMessage("");
      });

    return () => {
      active = false;
    };
  }, [nextPath]);

  useEffect(() => {
    const controller = new AbortController();

    fetch(apiUrl("/auth/status"), { cache: "no-store", signal: controller.signal })
      .then((res) => res.json())
      .then((data) => {
        setApiStatusMessage(`API connected: ${API_BASE}`);
        setHasAdminAccount(Boolean(data?.has_admin_account));
        if (data?.username) {
          setUsername(String(data.username));
        }
      })
      .catch((error) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setHasAdminAccount(true);
        setApiStatusMessage(`API unavailable: ${API_BASE}`);
        setErrorMessage(
          "We could not confirm the current admin account status. You can still try signing in, or refresh the page in a moment."
        );
      })
      .finally(() => setLoadingStatus(false));

    return () => {
      controller.abort();
    };
  }, []);

  async function handleSetup() {
    if (password.trim().length < 6) {
      setErrorMessage("Password must be at least 6 characters.");
      setMessage("");
      return;
    }
    if (password !== confirmPassword) {
      setErrorMessage("Password confirmation does not match.");
      setMessage("");
      return;
    }

    setSubmitting(true);
    setErrorMessage("");
    setMessage("");

    try {
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (setupSecret.trim()) {
        headers["X-AI-Radar-Setup-Secret"] = setupSecret.trim();
      }

      const response = await fetch(apiUrl("/auth/setup"), {
        method: "POST",
        headers,
        body: JSON.stringify({ username, password }),
      });

      const data = (await response.json().catch(() => null)) as { detail?: string; message?: string } | null;
      if (!response.ok) {
        throw new Error(data?.detail || data?.message || `Setup failed (${response.status})`);
      }

      setHasAdminAccount(true);
      setMessage("Admin account created. You can now log in.");
      setPassword("");
      setConfirmPassword("");
      setSetupSecret("");
    } catch (error) {
      setErrorMessage(
        error instanceof Error
          ? error.message
          : "We could not create the admin account right now. Please try again."
      );
    } finally {
      setSubmitting(false);
    }
  }

  async function handleLogin() {
    setSubmitting(true);
    setErrorMessage("");
    setMessage("");

    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), 12000);

    try {
      const response = await fetch(apiUrl("/auth/login"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        signal: controller.signal,
        body: JSON.stringify({ username, password }),
      });

      const data = (await response.json().catch(() => null)) as
        | { detail?: string; message?: string; token?: string }
        | null;

      if (!response.ok || !data?.token) {
        throw new Error(data?.detail || data?.message || `Login failed (${response.status})`);
      }

      setStoredAdminToken(data.token);
      window.location.assign(nextPath);
    } catch (error) {
      setErrorMessage(
        error instanceof DOMException && error.name === "AbortError"
          ? "Sign-in is taking too long. Please check that the local backend is still responding and try again."
          : error instanceof Error ? error.message : "We could not sign you in right now. Please try again."
      );
    } finally {
      window.clearTimeout(timeoutId);
      setSubmitting(false);
    }
  }

  return (
    <AppContainer>
      <PageHeader
        title="Admin Login"
        description="Use the admin account to access subscriptions, project intelligence, and the private operating surface."
      />

      <SectionCard title={hasAdminAccount ? "Sign In" : "Create Admin Account"}>
        {loadingStatus ? (
          <div style={{ color: "var(--app-text-muted)", fontSize: "14px" }}>
            Loading account status...
          </div>
        ) : (
          <div style={{ display: "grid", gap: "12px", maxWidth: "620px" }}>
            {apiStatusMessage ? (
              <div style={apiStatusMessage.startsWith("API connected") ? apiOkStyle : apiErrorStyle}>
                {apiStatusMessage}
              </div>
            ) : null}

            <Field label="Admin Username">
              <input value={username} onChange={(e) => setUsername(e.target.value)} style={inputStyle} />
            </Field>

            <Field label="Password">
              <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} style={inputStyle} />
            </Field>

            {!hasAdminAccount ? (
              <>
                <Field label="Confirm Password">
                  <input type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} style={inputStyle} />
                </Field>

                <Field label="Setup Secret">
                  <input type="password" value={setupSecret} onChange={(e) => setSetupSecret(e.target.value)} style={inputStyle} />
                </Field>
              </>
            ) : null}

            <div style={{ display: "flex", gap: "10px", flexWrap: "wrap", alignItems: "center" }}>
              <button
                onClick={() => void (hasAdminAccount ? handleLogin() : handleSetup())}
                disabled={submitting}
                style={primaryButtonStyle}
              >
                {submitting
                  ? hasAdminAccount
                    ? "Signing In..."
                    : "Creating..."
                  : hasAdminAccount
                    ? "Sign In"
                    : "Create Admin Account"}
              </button>

              <Link href="/" style={secondaryLinkStyle}>
                Back to Public Page
              </Link>
            </div>

            {message ? <Notice tone="success" text={message} /> : null}
            {errorMessage ? <Notice tone="error" text={errorMessage} /> : null}
          </div>
        )}
      </SectionCard>
    </AppContainer>
  );
}

function LoginPageSkeleton() {
  return (
    <AppContainer>
      <PageHeader
        title="Admin Login"
        description="Use the admin account to access subscriptions, project intelligence, and the private operating surface."
      />
      <SectionCard title="Loading">
          <div style={{ color: "var(--app-text-muted)", fontSize: "14px" }}>Preparing the sign-in experience...</div>
      </SectionCard>
    </AppContainer>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label style={{ display: "grid", gap: "8px" }}>
      <span style={{ fontSize: "13px", fontWeight: 700, color: "var(--app-text-muted)" }}>{label}</span>
      {children}
    </label>
  );
}

function Notice({ tone, text }: { tone: "success" | "error"; text: string }) {
  const styles =
    tone === "success"
      ? { border: "1px solid #bbf7d0", background: "#ecfdf3", color: "#166534" }
      : { border: "1px solid #fecaca", background: "#fff1f2", color: "#be123c" };

  return <div style={{ ...styles, borderRadius: "12px", padding: "12px 14px", fontSize: "13px" }}>{text}</div>;
}

const inputStyle = {
  border: "1px solid var(--app-input-border)",
  borderRadius: "12px",
  padding: "12px 14px",
  fontSize: "14px",
  color: "var(--app-input-fg)",
  background: "var(--app-input-bg)",
} as const;

const apiOkStyle = {
  border: "1px solid #bbf7d0",
  borderRadius: "10px",
  background: "#ecfdf5",
  color: "#047857",
  padding: "10px 12px",
  fontSize: "13px",
  fontWeight: 700,
  overflowWrap: "anywhere" as const,
} as const;

const apiErrorStyle = {
  border: "1px solid #fecaca",
  borderRadius: "10px",
  background: "#fff1f2",
  color: "#be123c",
  padding: "10px 12px",
  fontSize: "13px",
  fontWeight: 700,
  overflowWrap: "anywhere" as const,
} as const;

const primaryButtonStyle = {
  padding: "10px 14px",
  borderRadius: "8px",
  border: "1px solid var(--app-primary-action-border)",
  background: "var(--app-primary-action-bg)",
  color: "var(--app-primary-action-fg)",
  cursor: "pointer",
  fontWeight: 700,
} as const;

const secondaryLinkStyle = {
  padding: "10px 14px",
  borderRadius: "8px",
  border: "1px solid var(--app-secondary-action-border)",
  background: "var(--app-secondary-action-bg)",
  color: "var(--app-secondary-action-fg)",
  textDecoration: "none",
  fontWeight: 600,
} as const;
