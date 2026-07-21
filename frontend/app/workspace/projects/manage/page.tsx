"use client";

import Link from "next/link";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import AppContainer from "@/components/AppContainer";
import PageHeader from "@/components/PageHeader";

export default function LegacyManageProjectsRedirectPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/admin/projects");
  }, [router]);

  return (
    <AppContainer>
      <PageHeader
        title="Project Intake Has Moved"
        description="Project creation and configuration now live under Admin so there is a single source of truth for project records."
      />

      <div style={toolbarStyle}>
        <Link href="/workspace/projects" style={primaryLinkStyle}>
          Back to Project Takeaways
        </Link>
        <Link href="/workspace/projects/review" style={linkStyle}>
          Review Inbox
        </Link>
      </div>

      <div
        style={{
          border: "1px solid #e5e7eb",
          borderRadius: "20px",
          background: "#ffffff",
          padding: "20px",
          display: "grid",
          gap: "12px",
          boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
        }}
      >
        <div style={{ fontSize: "14px", color: "#4b5563", lineHeight: 1.7 }}>
          Redirecting you to the new admin project intake page.
        </div>
        <div style={{ display: "flex", gap: "12px", flexWrap: "wrap" }}>
          <Link href="/admin/projects" style={linkStyle}>
            Open Project Intake
          </Link>
        </div>
      </div>
    </AppContainer>
  );
}

const linkStyle = {
  textDecoration: "none",
  color: "#111827",
  fontSize: "14px",
  fontWeight: 700,
  border: "1px solid #d1d5db",
  borderRadius: "8px",
  background: "#ffffff",
  padding: "10px 14px",
} as const;

const primaryLinkStyle = {
  ...linkStyle,
  border: "1px solid #111827",
  background: "#111827",
  color: "#ffffff",
} as const;

const toolbarStyle = {
  marginBottom: "20px",
  display: "flex",
  gap: "12px",
  flexWrap: "wrap",
  border: "1px solid #e5e7eb",
  borderRadius: "20px",
  background: "#ffffff",
  padding: "16px 18px",
  boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
} as const;
