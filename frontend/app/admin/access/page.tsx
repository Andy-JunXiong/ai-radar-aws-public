"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import AppContainer from "@/components/AppContainer";
import PageHeader from "@/components/PageHeader";
import SectionCard from "@/components/SectionCard";
import RequireAdminAuth from "@/components/RequireAdminAuth";
import { apiUrl } from "@/lib/api";
import { buildAdminAuthHeaders, clearStoredAdminToken, getAdminLoginPath } from "@/lib/adminAuth";

export default function AdminAccessPage() {
  const router = useRouter();
  const [username, setUsername] = useState("admin");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [message, setMessage] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetch(apiUrl("/auth/status"), { cache: "no-store" })
      .then((res) => res.json())
      .then((data) => {
        if (data?.username) setUsername(String(data.username));
      })
      .catch((error) => {
        console.error("Failed to load auth status:", error);
      });
  }, []);

  async function handleChangePassword() {
    if (newPassword.trim().length < 6) {
      setErrorMessage("New password must be at least 6 characters.");
      setMessage("");
      return;
    }
    if (newPassword !== confirmPassword) {
      setErrorMessage("Password confirmation does not match.");
      setMessage("");
      return;
    }

    setSaving(true);
    setMessage("");
    setErrorMessage("");

    try {
      const response = await fetch(apiUrl("/auth/change-password"), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...buildAdminAuthHeaders(),
        },
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword,
        }),
      });

      const data = (await response.json().catch(() => null)) as { detail?: string; message?: string } | null;
      if (!response.ok) {
        throw new Error(data?.detail || data?.message || `Password update failed (${response.status})`);
      }

      setMessage(data?.message || "Password updated successfully. Please sign in again.");
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      clearStoredAdminToken();
      router.replace(getAdminLoginPath("/admin/access"));
    } catch (error) {
      console.error(error);
      setErrorMessage(error instanceof Error ? error.message : "Failed to update password.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <AppContainer>
      <RequireAdminAuth>
        <PageHeader
          title="Admin Access"
          description="Manage the current admin account password from the web interface."
        />

        <SectionCard title="Account">
          <div style={{ display: "grid", gap: "12px", maxWidth: "620px" }}>
            <label style={{ display: "grid", gap: "8px" }}>
              <span style={labelStyle}>Admin Username</span>
              <input value={username} readOnly style={{ ...inputStyle, background: "#f8fafc" }} />
            </label>

            <label style={{ display: "grid", gap: "8px" }}>
              <span style={labelStyle}>Current Password</span>
              <input type="password" value={currentPassword} onChange={(e) => setCurrentPassword(e.target.value)} style={inputStyle} />
            </label>

            <label style={{ display: "grid", gap: "8px" }}>
              <span style={labelStyle}>New Password</span>
              <input type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} style={inputStyle} />
            </label>

            <label style={{ display: "grid", gap: "8px" }}>
              <span style={labelStyle}>Confirm New Password</span>
              <input type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} style={inputStyle} />
            </label>

            <div style={{ display: "flex", gap: "10px", flexWrap: "wrap", alignItems: "center" }}>
              <button onClick={() => void handleChangePassword()} disabled={saving} style={primaryButtonStyle}>
                {saving ? "Saving..." : "Update Password"}
              </button>
              <Link href="/admin" style={secondaryLinkStyle}>
                Back to Previous Page
              </Link>
            </div>

            {message ? <Notice tone="success" text={message} /> : null}
            {errorMessage ? <Notice tone="error" text={errorMessage} /> : null}
          </div>
        </SectionCard>
      </RequireAdminAuth>
    </AppContainer>
  );
}

function Notice({ tone, text }: { tone: "success" | "error"; text: string }) {
  const styles =
    tone === "success"
      ? { border: "1px solid #bbf7d0", background: "#ecfdf3", color: "#166534" }
      : { border: "1px solid #fecaca", background: "#fff1f2", color: "#be123c" };

  return <div style={{ ...styles, borderRadius: "12px", padding: "12px 14px", fontSize: "13px" }}>{text}</div>;
}

const labelStyle = {
  fontSize: "13px",
  fontWeight: 700,
  color: "#374151",
} as const;

const inputStyle = {
  border: "1px solid #d1d5db",
  borderRadius: "12px",
  padding: "12px 14px",
  fontSize: "14px",
  color: "#111827",
} as const;

const primaryButtonStyle = {
  padding: "10px 14px",
  borderRadius: "10px",
  border: "1px solid #111827",
  background: "#111827",
  color: "#ffffff",
  cursor: "pointer",
  fontWeight: 700,
} as const;

const secondaryLinkStyle = {
  padding: "10px 14px",
  borderRadius: "10px",
  border: "1px solid #d1d5db",
  color: "#111827",
  textDecoration: "none",
  fontWeight: 600,
} as const;
