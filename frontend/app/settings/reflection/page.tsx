"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import type { CSSProperties } from "react";

import AppContainer from "@/components/AppContainer";
import PageHeader from "@/components/PageHeader";
import RequireAdminAuth from "@/components/RequireAdminAuth";
import SectionCard from "@/components/SectionCard";
import { apiUrl } from "@/lib/api";
import { adminFetch } from "@/lib/adminAuth";
import { buildBetaUserHeaders, getStoredBetaUserId, setStoredBetaUserId } from "@/lib/betaUser";

type ReflectionSettings = {
  enabled?: boolean;
  repo?: string;
  repo_url?: string;
  branch?: string;
};

type ReflectionStatus = {
  local_path?: string;
  s3_bucket?: string;
  s3_key?: string;
  repo_url?: string;
  has_pat?: string;
};

type ReflectionResponse = {
  user_id?: string;
  scope?: string;
  settings?: ReflectionSettings;
  status?: ReflectionStatus;
};

type ReflectionSyncStatus = {
  last_sync_at?: string;
  last_commit_sha?: string | null;
  last_success?: boolean;
  last_error?: string | null;
  total_reflections?: number;
};

const DEFAULT_USER_ID = "admin_default";

export default function ReflectionSettingsPage() {
  const [userId, setUserId] = useState(DEFAULT_USER_ID);
  const [scope, setScope] = useState("demo_default");
  const [enabled, setEnabled] = useState(true);
  const [repoInput, setRepoInput] = useState("");
  const [branch, setBranch] = useState("main");
  const [status, setStatus] = useState<ReflectionStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [syncing, setSyncing] = useState(false);
  const [syncStatus, setSyncStatus] = useState<ReflectionSyncStatus | null>(null);
  const [syncStatusMessage, setSyncStatusMessage] = useState("");

  async function loadSettings(nextUserId: string) {
    setLoading(true);
    setErrorMessage("");
    setMessage("");
    try {
      const response = await adminFetch(apiUrl("/settings/reflection"), {
        headers: {
          ...buildBetaUserHeaders(nextUserId),
        },
        cache: "no-store",
      });
      if (!response.ok) {
        throw new Error(`Failed to load reflection settings (${response.status})`);
      }
      const data = (await response.json()) as ReflectionResponse;
      setScope(data.scope || "demo_default");
      setEnabled(Boolean(data.settings?.enabled ?? true));
      setRepoInput(data.settings?.repo || data.settings?.repo_url || "");
      setBranch(data.settings?.branch || "main");
      setStatus(data.status || null);
    } catch {
      setStatus(null);
      setErrorMessage("Failed to load reflection settings.");
    } finally {
      setLoading(false);
    }
  }

  async function loadSyncStatus() {
    setSyncStatusMessage("");
    try {
      const response = await fetch(apiUrl("/reflection/sync/status"), { cache: "no-store" });
      if (!response.ok) {
        throw new Error(`Failed to load deep reflection sync status (${response.status})`);
      }
      const data = (await response.json()) as ReflectionSyncStatus;
      setSyncStatus(data);
    } catch {
      setSyncStatus(null);
      setSyncStatusMessage("Deep reflection sync status is temporarily unavailable.");
    }
  }

  useEffect(() => {
    const stored = getStoredBetaUserId().trim() || DEFAULT_USER_ID;
    setUserId(stored);
    void loadSettings(stored);
    void loadSyncStatus();
  }, []);

  async function handleSave() {
    const normalized = userId.trim() || DEFAULT_USER_ID;
    setSaving(true);
    setErrorMessage("");
    setMessage("");
    try {
      const response = await adminFetch(apiUrl("/settings/reflection"), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...buildBetaUserHeaders(normalized),
        },
        body: JSON.stringify({
          settings: {
            enabled,
            repo: repoInput,
            branch,
          },
        }),
      });
      if (!response.ok) {
        const text = await response.text();
        throw new Error(text || `Failed to save reflection settings (${response.status})`);
      }
      setStoredBetaUserId(normalized);
      setMessage("Reflection connection saved successfully.");
      await loadSettings(normalized);
      await loadSyncStatus();
    } catch {
      setErrorMessage("Failed to save reflection settings.");
    } finally {
      setSaving(false);
    }
  }

  async function handleSync() {
    if (!enabled) {
      setMessage("");
      setErrorMessage("Enable Deep Reflection Sync and save the source before running sync.");
      return;
    }
    setSyncing(true);
    setErrorMessage("");
    setMessage("");
    try {
      const response = await adminFetch(apiUrl("/reflection/sync/run"), {
        method: "GET",
        cache: "no-store",
      });
      if (!response.ok) {
        const text = await response.text();
        throw new Error(text || `Failed to sync deep reflections (${response.status})`);
      }
      setMessage("Deep reflection sync completed.");
      await loadSyncStatus();
    } catch {
      setErrorMessage("Failed to sync deep reflections. Check that the PAT is configured and the repo is reachable.");
    } finally {
      setSyncing(false);
    }
  }

  return (
    <AppContainer>
      <RequireAdminAuth>
        <PageHeader
          title="Deep Reflection Source"
          description="Point AI Radar at the GitHub repo that stores your long-form deep conversation reflections. The repo and branch are editable here; the PAT stays on the backend."
          size="compact"
        />

        <SectionCard title="Connection Settings">
          <div style={gridStyle}>
            <label style={labelStyle}>
              Admin User ID
              <input value={userId} onChange={(e) => setUserId(e.target.value)} style={inputStyle} />
            </label>

            <label style={labelStyle}>
              Deep Reflection Repo
              <input
                value={repoInput}
                onChange={(e) => setRepoInput(e.target.value)}
                placeholder="Andy-JunXiong/Andy-Reflection-Schema or full GitHub URL"
                style={inputStyle}
              />
            </label>

            <label style={labelStyle}>
              Branch
              <input value={branch} onChange={(e) => setBranch(e.target.value)} placeholder="main" style={inputStyle} />
            </label>

            <label style={{ ...labelStyle, alignItems: "start" }}>
              Deep Reflection Sync Enabled
              <div style={toggleWrapStyle}>
                <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />
                <span style={{ fontSize: "14px", color: "var(--app-text-muted)", lineHeight: 1.5 }}>
                  Allow this repo configuration to be used by deep reflection sync.
                </span>
              </div>
            </label>

            <div style={actionRowStyle}>
              <button
                onClick={() => void handleSave()}
                disabled={saving}
                style={{
                  ...primaryButtonStyle,
                  opacity: saving ? 0.72 : 1,
                  cursor: saving ? "not-allowed" : "pointer",
                }}
              >
                {saving ? "Saving..." : "Save Deep Reflection Source"}
              </button>
              <button
                onClick={() => void handleSync()}
                disabled={syncing || !enabled}
                style={{
                  ...secondaryButtonStyle,
                  cursor: syncing || !enabled ? "not-allowed" : "pointer",
                  opacity: syncing || !enabled ? 0.62 : 1,
                }}
              >
                {syncing ? "Syncing..." : "Run Deep Reflection Sync"}
              </button>
              <Link href="/reflections" style={linkButtonStyle}>
                Open Deep Reflections
              </Link>
              <Link href="/settings" style={linkButtonStyle}>
                Back to Settings
              </Link>
            </div>

            {message ? <div style={successStyle}>{message}</div> : null}
            {errorMessage ? <div style={errorStyle}>{errorMessage}</div> : null}
          </div>
        </SectionCard>

        <SectionCard title="Current Status">
          <div style={statusGridStyle}>
            <StatusRow label="Scope" value={scope} />
            <StatusRow label="Deep reflection sync enabled" value={enabled ? "yes" : "no"} tone={enabled ? "success" : "muted"} />
            <StatusRow label="Normalized repo URL" value={status?.repo_url || "Not configured"} />
            <StatusRow label="GitHub PAT configured" value={status?.has_pat || "no"} tone={status?.has_pat === "yes" ? "success" : "warning"} />
            <StatusRow label="S3 bucket" value={status?.s3_bucket || "unset"} />
            <StatusRow label="S3 key" value={status?.s3_key || "unset"} />
            <StatusRow label="Local path" value={status?.local_path || "unset"} mono />
            <StatusRow label="Last sync" value={syncStatus?.last_sync_at || "Never"} />
            <StatusRow label="Last commit SHA" value={syncStatus?.last_commit_sha || "Unavailable"} mono />
            <StatusRow label="Indexed deep reflections" value={String(syncStatus?.total_reflections ?? 0)} />
            <StatusRow
              label="Last sync success"
              value={syncStatus?.last_success === undefined ? "Unknown" : syncStatus.last_success ? "yes" : "no"}
              tone={syncStatus?.last_success === undefined ? "muted" : syncStatus.last_success ? "success" : "warning"}
            />
            {syncStatus?.last_error ? <StatusRow label="Last sync error" value={syncStatus.last_error} tone="warning" /> : null}
            {syncStatusMessage ? <div style={statusNoteStyle}>{syncStatusMessage}</div> : null}
            {!enabled ? (
              <div style={statusNoteStyle}>
                Deep reflection sync is currently disabled. Leave this switched on in most cases. Turn it off only if you want to pause indexing for this repo.
              </div>
            ) : null}
          </div>
        </SectionCard>

        <SectionCard title="Notes">
          <div style={notesListStyle}>
            <div>You can paste either a full GitHub URL or an <code>owner/repo</code> string.</div>
            <div>The Personal Access Token is intentionally not editable from the browser.</div>
            <div>Deep reflection sync stays read-only. AI Radar reads from GitHub and builds an index; it does not write back.</div>
            <div><code>Run Deep Reflection Sync</code> pulls from GitHub and rebuilds the deep reflection index. It only runs when the sync checkbox is enabled.</div>
          </div>
        </SectionCard>
      </RequireAdminAuth>
    </AppContainer>
  );
}

function StatusRow({
  label,
  value,
  mono = false,
  tone = "muted",
}: {
  label: string;
  value: string;
  mono?: boolean;
  tone?: "muted" | "success" | "warning";
}) {
  return (
    <div style={statusRowStyle}>
      <div style={statusLabelStyle}>{label}</div>
      <div
        style={{
          ...statusValueStyle,
          ...(mono ? monoValueStyle : null),
          ...(tone === "success"
            ? { color: "var(--app-success-fg)" }
            : tone === "warning"
              ? { color: "var(--app-warning-fg)" }
              : null),
        }}
      >
        {value}
      </div>
    </div>
  );
}

const gridStyle = {
  display: "grid",
  gap: "14px",
} as const;

const labelStyle = {
  display: "grid",
  gap: "8px",
  fontSize: "13px",
  fontWeight: 700,
  color: "var(--app-text-muted)",
} as const;

const inputStyle = {
  border: "1px solid var(--app-input-border)",
  borderRadius: "10px",
  padding: "12px 14px",
  fontSize: "14px",
  color: "var(--app-input-fg)",
  background: "var(--app-input-bg)",
  outline: "none",
} as const;

const toggleWrapStyle = {
  display: "flex",
  gap: "10px",
  alignItems: "center",
  padding: "10px 0",
} as const;

const actionRowStyle = {
  display: "flex",
  gap: "10px",
  flexWrap: "wrap",
  alignItems: "center",
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

const secondaryButtonStyle = {
  padding: "10px 14px",
  borderRadius: "8px",
  border: "1px solid var(--app-secondary-action-border)",
  background: "var(--app-secondary-action-bg)",
  color: "var(--app-secondary-action-fg)",
  cursor: "pointer",
  fontWeight: 700,
} as const;

const linkButtonStyle = {
  ...secondaryButtonStyle,
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  textDecoration: "none",
} as const;

const successStyle = {
  border: "1px solid var(--app-success-border)",
  background: "var(--app-success-bg)",
  color: "var(--app-success-fg)",
  borderRadius: "10px",
  padding: "12px 14px",
  fontSize: "13px",
} as const;

const errorStyle = {
  border: "1px solid var(--app-danger-border)",
  background: "var(--app-danger-bg)",
  color: "var(--app-danger-fg)",
  borderRadius: "10px",
  padding: "12px 14px",
  fontSize: "13px",
} as const;

const statusGridStyle = {
  display: "grid",
  gap: "8px",
  fontSize: "14px",
  color: "var(--app-text-muted)",
} as const;

const statusRowStyle = {
  display: "grid",
  gridTemplateColumns: "minmax(180px, 0.34fr) minmax(0, 1fr)",
  gap: "12px",
  alignItems: "start",
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  padding: "10px 12px",
} as const;

const statusLabelStyle = {
  fontSize: "12px",
  fontWeight: 800,
  color: "var(--app-text-muted)",
} as const;

const statusValueStyle = {
  color: "var(--app-text-strong)",
  overflowWrap: "anywhere",
  lineHeight: 1.45,
} as CSSProperties;

const monoValueStyle = {
  fontFamily:
    'ui-monospace, SFMono-Regular, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace',
  fontSize: "12px",
} as const;

const statusNoteStyle = {
  border: "1px solid var(--app-info-border)",
  background: "var(--app-info-bg)",
  color: "var(--app-info-fg)",
  borderRadius: "10px",
  padding: "12px 14px",
  fontSize: "13px",
} as const;

const notesListStyle = {
  display: "grid",
  gap: "8px",
  fontSize: "14px",
  color: "var(--app-text-muted)",
  lineHeight: 1.7,
} as const;
