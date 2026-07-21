"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import AppContainer from "@/components/AppContainer";
import PageHeader from "@/components/PageHeader";
import SectionCard from "@/components/SectionCard";
import RequireAdminAuth from "@/components/RequireAdminAuth";
import { apiUrl } from "@/lib/api";
import { adminFetch } from "@/lib/adminAuth";
import { getStoredBetaUserId } from "@/lib/betaUser";

type SignalItem = {
  status?: string;
  is_manual?: boolean;
};

type WorkspaceItem = {
  source_type?: string;
  content_type?: string;
  final_reflection?: string;
};

function normalizeStatus(status?: string) {
  const value = (status || "pending").toLowerCase();
  if (
    value === "pending" ||
    value === "saved" ||
    value === "analyzed" ||
    value === "completed" ||
    value === "rejected"
  ) {
    return value;
  }
  return "pending";
}

export default function AdminPage() {
  const [signals, setSignals] = useState<SignalItem[]>([]);
  const [workspaceItems, setWorkspaceItems] = useState<WorkspaceItem[]>([]);
  const [loadingSignals, setLoadingSignals] = useState(true);
  const [loadingWorkspace, setLoadingWorkspace] = useState(true);
  const [adminId] = useState(() => getStoredBetaUserId().trim() || "admin");
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    fetch(apiUrl("/signals"))
      .then((res) => res.json())
      .then((data) => {
        const items = Array.isArray(data) ? data : data.signals || data.items || [];
        setSignals(Array.isArray(items) ? items : []);
      })
      .catch((error) => {
        console.error("Failed to load signals:", error);
        setSignals([]);
        setErrorMessage((prev) =>
          prev || "Some admin data could not be loaded. The backend may be unavailable."
        );
      })
      .finally(() => setLoadingSignals(false));
  }, []);

  useEffect(() => {
    adminFetch(apiUrl("/workspace_history"))
      .then((res) => res.json())
      .then((data) => {
        const items = Array.isArray(data) ? data : data.items || [];
        setWorkspaceItems(Array.isArray(items) ? items : []);
      })
      .catch((error) => {
        console.error("Failed to load workspace history:", error);
        setWorkspaceItems([]);
        setErrorMessage((prev) =>
          prev || "Some admin data could not be loaded. The backend may be unavailable."
        );
      })
      .finally(() => setLoadingWorkspace(false));
  }, []);

  const stats = useMemo(() => {
    const normalizedSignals = signals.map((item) => normalizeStatus(item.status));
    const workspaceReflections = workspaceItems.filter(
      (item) =>
        item.source_type === "signal" &&
        (!item.content_type || item.content_type === "signal") &&
        !!item.final_reflection?.trim()
    ).length;

    return {
      totalSignals: signals.length,
      pending: normalizedSignals.filter((status) => status === "pending").length,
      analyzed: normalizedSignals.filter((status) => status === "analyzed").length,
      completed: normalizedSignals.filter((status) => status === "completed").length,
      rejected: normalizedSignals.filter((status) => status === "rejected").length,
      manual: signals.filter((item) => !!item.is_manual).length,
      workspaceReflections,
    };
  }, [signals, workspaceItems]);

  const loading = loadingSignals || loadingWorkspace;

  return (
    <AppContainer>
      <RequireAdminAuth>
        <PageHeader
          title="Admin"
          description="This page is the personal admin surface. It stays separate from the dashboard so the dashboard can remain focused on intelligence monitoring. Use the top navigation to move across admin, dashboard, signals, and workspace."
        />

        <SectionCard title="Admin Identity">
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1.1fr 0.9fr",
            gap: "18px",
          }}
        >
          <div
            style={{
              border: "1px solid var(--app-surface-strong-border)",
              borderRadius: "8px",
              background: "var(--app-surface-muted-bg)",
              padding: "18px",
            }}
          >
            <div
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "8px",
                padding: "5px 10px",
                borderRadius: "999px",
                background: "#dbeafe",
                color: "#1d4ed8",
                fontSize: "12px",
                fontWeight: 700,
                textTransform: "uppercase",
                letterSpacing: 0,
              }}
            >
              Active Role
            </div>

            <div
              style={{
                marginTop: "14px",
                fontSize: "28px",
                fontWeight: 800,
                color: "var(--app-text-strong)",
                letterSpacing: "-0.03em",
              }}
            >
              Admin
            </div>

            <div style={{ marginTop: "8px", fontSize: "14px", color: "var(--app-text-muted)", lineHeight: 1.7 }}>
              Current admin id: <strong>{adminId}</strong>
            </div>

            <div style={{ marginTop: "12px", fontSize: "14px", color: "var(--app-text-muted)", lineHeight: 1.7 }}>
              This role currently owns the full workflow: signal review, reflection, completion,
              and workspace governance.
            </div>

            <div style={{ marginTop: "16px" }}>
              <Link href="/settings" style={buttonStyle("var(--app-primary-action-bg)", "var(--app-primary-action-fg)")}>
                Open Admin Settings
              </Link>
            </div>
          </div>

          <div
            style={{
              border: "1px dashed var(--app-surface-strong-border)",
              borderRadius: "8px",
              background: "var(--app-surface-bg)",
              padding: "18px",
            }}
          >
            <div style={{ fontSize: "18px", fontWeight: 700, color: "var(--app-text-strong)" }}>
              Next Phase
            </div>
            <div style={{ marginTop: "10px", fontSize: "14px", color: "var(--app-text-muted)", lineHeight: 1.7 }}>
              The system is still in single-admin mode. After this phase, we can add:
            </div>
            <div style={{ marginTop: "12px", display: "grid", gap: "8px", fontSize: "14px", color: "var(--app-text-muted)" }}>
              <div>1. User application entry</div>
              <div>2. Admin approval queue</div>
              <div>3. Member roles with private workspaces</div>
            </div>
          </div>
        </div>
        </SectionCard>

        <SectionCard title="Admin Snapshot">
          {errorMessage ? (
            <div
              style={{
                marginBottom: "14px",
                border: "1px solid #fecaca",
                background: "#fff1f2",
                color: "#be123c",
                borderRadius: "8px",
                padding: "12px 14px",
                fontSize: "13px",
              }}
            >
              {errorMessage}
            </div>
          ) : null}
          {loading ? (
            <div style={{ color: "var(--app-text-muted)", fontSize: "14px" }}>Loading admin snapshot...</div>
          ) : (
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 180px), 1fr))",
              gap: "12px",
            }}
          >
            <StatCard label="Total Signals" value={stats.totalSignals} />
            <StatCard label="Pending" value={stats.pending} />
            <StatCard label="Analyzed" value={stats.analyzed} />
            <StatCard label="Completed" value={stats.completed} />
            <StatCard label="Rejected" value={stats.rejected} />
            <StatCard label="Manual Inputs" value={stats.manual} />
            <StatCard label="Workspace Completion Notes" value={stats.workspaceReflections} />
          </div>
        )}
        </SectionCard>

        <SectionCard title="Admin Configuration">
          <div style={{ display: "grid", gap: "18px" }}>
            <div style={configGroupStyle}>
              <div style={configGroupHeaderStyle}>
                <div style={configGroupTitleStyle}>Context</div>
                <div style={configGroupDescriptionStyle}>
                  Manage your profile, background, and interpretation preferences.
                </div>
              </div>
              <div style={configGroupGridStyle}>
                <EntryCard href="/settings" title="JSON Context" description="Edit personal context as raw JSON." />
                <EntryCard href="/settings/form" title="Q&A Context Builder" description="Fill profile and interpretation preferences through guided questions." />
                <EntryCard href="/settings/reflection" title="Deep Reflection Source" description="Set the GitHub repo and branch used for long-form deep reflection sync." />
              </div>
            </div>

            <div style={configGroupStyle}>
              <div style={configGroupHeaderStyle}>
                <div style={configGroupTitleStyle}>Signals</div>
                <div style={configGroupDescriptionStyle}>
                  Configure your subscription sources and review what is already being tracked.
                </div>
              </div>
              <div style={configGroupGridStyle}>
                <EntryCard href="/admin/subscriptions" title="Signal Sources" description="Configure source subscriptions, topic preferences, and signal intake rules." />
                <EntryCard href="/admin/subscriptions/library" title="My Subscriptions" description="Review the sources already subscribed under the current admin scope." />
              </div>
            </div>

            <div style={configGroupStyle}>
              <div style={configGroupHeaderStyle}>
                <div style={configGroupTitleStyle}>Operating Surface</div>
                <div style={configGroupDescriptionStyle}>
                  Open the internal operating home without promoting it into the main navigation.
                </div>
              </div>
              <div style={configGroupGridStyle}>
                <EntryCard href="/overview" title="Operating Home" description="Open the historical AI Radar operating overview for intake, review, metrics, and work-surface shortcuts." />
              </div>
            </div>

            <div style={diagnosticsGroupStyle}>
              <div style={configGroupHeaderStyle}>
                <div style={configGroupTitleStyle}>Admin Diagnostics</div>
                <div style={configGroupDescriptionStyle}>
                  Operational readouts for model provenance, metrics health, lifecycle events, and operator guidance.
                </div>
              </div>
              <div style={configGroupGridStyle}>
                <EntryCard href="/admin/model-attribution" title="Model Attribution" description="Review provenance coverage and v1-only attribution diagnostics." />
                <EntryCard href="/admin/metrics" title="Metrics" description="Check pipeline, collector, LLM, and verification run health." />
                <EntryCard href="/admin/rejected-learning-buffer" title="Rejected Learning Buffer" description="Inspect caution context from rejected or dismissed Project Review records." />
                <EntryCard href="/admin/background-update-candidates" title="Background Updates" description="Inspect inactive context candidates from Signal claim feedback." />
                <EntryCard href="/admin/reflection-polish" title="Reflection Polish" description="Review persisted reflection polish pairs and record human checklist outcomes." />
                <EntryCard href="/admin/lifecycle-diagnostics" title="Lifecycle Diagnostics" description="Inspect soft-recorded signal lifecycle events and storage readiness." />
                <EntryCard href="/admin/operator-guidance" title="Operator Guidance" description="Review static next-action guidance for known AI Radar state transitions." />
              </div>
            </div>

            <div style={configGroupStyle}>
              <div style={configGroupHeaderStyle}>
                <div style={configGroupTitleStyle}>Projects & Access</div>
                <div style={configGroupDescriptionStyle}>
                  Maintain project intake and admin-level security settings.
                </div>
              </div>
              <div style={configGroupGridStyle}>
                <EntryCard href="/admin/projects" title="Project Intake" description="Create projects, maintain roadmap context, and connect GitHub repos." />
                <EntryCard href="/admin/access" title="Admin Access" description="Set or change the admin password from the web interface." />
              </div>
            </div>
          </div>
        </SectionCard>
      </RequireAdminAuth>
    </AppContainer>
  );
}

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <div style={{ border: "1px solid var(--app-surface-border)", borderRadius: "8px", background: "var(--app-surface-soft-bg)", padding: "16px" }}>
      <div style={{ fontSize: "12px", fontWeight: 700, color: "var(--app-text-subtle)", textTransform: "uppercase", letterSpacing: 0 }}>{label}</div>
      <div style={{ marginTop: "10px", fontSize: "32px", fontWeight: 850, color: "var(--app-text-strong)", letterSpacing: "-0.04em" }}>{value}</div>
    </div>
  );
}

function EntryCard({ href, title, description }: { href: string; title: string; description: string }) {
  return (
    <Link href={href} style={{ textDecoration: "none", color: "inherit" }}>
      <div style={{ border: "1px solid var(--app-surface-border)", borderRadius: "8px", padding: "16px", background: "var(--app-surface-muted-bg)", minHeight: "108px", display: "grid", alignContent: "start" }}>
        <div style={{ fontSize: "17px", fontWeight: 800, color: "var(--app-text-strong)" }}>{title}</div>
        <div style={{ marginTop: "6px", fontSize: "14px", lineHeight: 1.7, color: "var(--app-text-muted)" }}>{description}</div>
      </div>
    </Link>
  );
}

function buttonStyle(background: string, color: string) {
  return {
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    padding: "10px 14px",
    borderRadius: "999px",
    background,
    color,
    textDecoration: "none",
    fontSize: "14px",
    fontWeight: 700,
  } as const;
}

const configGroupStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-soft-bg)",
  padding: "16px",
  display: "grid",
  gap: "14px",
} as const;

const diagnosticsGroupStyle = {
  ...configGroupStyle,
  border: "1px solid var(--app-surface-strong-border)",
  background: "var(--app-surface-muted-bg)",
} as const;

const configGroupHeaderStyle = {
  display: "grid",
  gap: "6px",
} as const;

const configGroupTitleStyle = {
  fontSize: "18px",
  fontWeight: 800,
  color: "var(--app-text-strong)",
} as const;

const configGroupDescriptionStyle = {
  fontSize: "14px",
  color: "var(--app-text-muted)",
  lineHeight: 1.7,
} as const;

const configGroupGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 240px), 1fr))",
  gap: "12px",
  alignItems: "stretch",
} as const;
