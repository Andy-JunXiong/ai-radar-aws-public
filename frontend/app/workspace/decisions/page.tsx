"use client";

import Link from "next/link";
import AppContainer from "@/components/AppContainer";
import RequireAdminAuth from "@/components/RequireAdminAuth";

export default function WorkspaceDecisionsPage() {
  return (
    <AppContainer style={{ paddingTop: "24px" }}>
      <RequireAdminAuth>
        <div style={headerPanelStyle}>
          <div>
            <div style={eyebrowStyle}>Workspace</div>
            <h1 style={pageTitleStyle}>Decision Cards</h1>
            <p style={descriptionStyle}>
              This feature is currently paused while Project Takeaways remains the primary workspace path.
            </p>
          </div>
          <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
            <Link href="/workspace" style={primaryButtonStyle}>
              Back to Workspace
            </Link>
            <Link href="/workspace/projects" style={secondaryButtonStyle}>
              Project Takeaways
            </Link>
          </div>
        </div>

        <section style={panelStyle}>
          <div style={eyebrowStyle}>Paused Module</div>
          <h2 style={sectionTitleStyle}>Decision cards are not part of the active review loop.</h2>
          <p style={bodyTextStyle}>
            Decision cards and signal routing are temporarily hidden from the active workflow. The underlying data and
            code stay in place so the module can be revisited later without rebuilding from scratch.
          </p>
        </section>
      </RequireAdminAuth>
    </AppContainer>
  );
}

const headerPanelStyle = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  gap: "18px",
  flexWrap: "wrap" as const,
  border: "1px solid #e5e7eb",
  borderRadius: "20px",
  background: "#ffffff",
  padding: "18px",
  marginBottom: "20px",
  boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
} as const;

const panelStyle = {
  border: "1px solid #e5e7eb",
  borderRadius: "20px",
  background: "#ffffff",
  padding: "18px",
  boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
} as const;

const eyebrowStyle = {
  color: "#6b7280",
  fontSize: "12px",
  fontWeight: 700,
  textTransform: "uppercase" as const,
  letterSpacing: "0.4px",
} as const;

const pageTitleStyle = {
  margin: "4px 0 0",
  color: "#111827",
  fontSize: "18px",
  fontWeight: 600,
  lineHeight: 1.35,
} as const;

const sectionTitleStyle = {
  margin: "6px 0 0",
  color: "#111827",
  fontSize: "18px",
  fontWeight: 500,
  lineHeight: 1.35,
} as const;

const descriptionStyle = {
  margin: "6px 0 0",
  color: "#6b7280",
  fontSize: "13px",
  lineHeight: 1.5,
  maxWidth: "760px",
} as const;

const bodyTextStyle = {
  margin: "12px 0 0",
  color: "#374151",
  fontSize: "14px",
  lineHeight: 1.7,
  maxWidth: "820px",
} as const;

const primaryButtonStyle = {
  display: "inline-flex",
  alignItems: "center",
  border: "1px solid #111827",
  borderRadius: "10px",
  background: "#111827",
  color: "#ffffff",
  padding: "7px 12px",
  textDecoration: "none",
  fontSize: "13px",
  fontWeight: 600,
} as const;

const secondaryButtonStyle = {
  display: "inline-flex",
  alignItems: "center",
  border: "1px solid #d1d5db",
  borderRadius: "10px",
  background: "#ffffff",
  color: "#111827",
  padding: "7px 12px",
  textDecoration: "none",
  fontSize: "13px",
  fontWeight: 600,
} as const;
