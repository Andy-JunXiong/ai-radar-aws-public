"use client";

import { useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import AppContainer from "@/components/AppContainer";
import PageHeader from "@/components/PageHeader";
import SectionCard from "@/components/SectionCard";

export default function SavedRedirectPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/workspace/backlog");
  }, [router]);

  return (
    <AppContainer>
      <PageHeader
        title="Workspace Backlog"
        description="Saved Backlog has moved into Workspace as the working queue for saved signals."
      />

      <SectionCard title="Redirecting">
        <div style={{ display: "grid", gap: "12px", maxWidth: "680px" }}>
          <p style={descriptionStyle}>
            Saved signals are now managed from Workspace Backlog so the workflow stays with completion notes,
            project memory, and Workspace outputs.
          </p>
          <Link href="/workspace/backlog" style={buttonStyle}>
            Open Workspace Backlog
          </Link>
        </div>
      </SectionCard>
    </AppContainer>
  );
}

const descriptionStyle = {
  margin: 0,
  color: "var(--app-text-muted)",
  fontSize: "14px",
  lineHeight: 1.6,
} as const;

const buttonStyle = {
  display: "inline-flex",
  width: "fit-content",
  border: "1px solid var(--app-primary-action-border)",
  borderRadius: "8px",
  background: "var(--app-primary-action-bg)",
  color: "var(--app-primary-action-fg)",
  padding: "9px 13px",
  fontSize: "13px",
  fontWeight: 700,
  textDecoration: "none",
} as const;
