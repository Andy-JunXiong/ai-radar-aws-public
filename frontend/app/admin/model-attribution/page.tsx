"use client";

import Link from "next/link";
import { FormEvent, type ReactNode, useEffect, useMemo, useState } from "react";

import AppContainer from "@/components/AppContainer";
import PageHeader from "@/components/PageHeader";
import RequireAdminAuth from "@/components/RequireAdminAuth";
import SectionCard from "@/components/SectionCard";
import { apiUrl } from "@/lib/api";
import { adminFetch } from "@/lib/adminAuth";

type CoverageSummary = {
  total_records?: number;
  v1_records?: number;
  legacy_v0_records?: number;
  malformed_records?: number;
  manual_unverified_records?: number;
  attribution_eligible_records?: number;
};

type FamilyRow = CoverageSummary & {
  record_family?: string;
};

type ModelRow = {
  provider?: string;
  model_id?: string;
  count?: number;
};

type RouteRow = {
  route_key?: string;
  task_type?: string;
  prompt_template_id?: string;
  prompt_template_version?: string;
  count?: number;
};

type OutcomeRow = {
  outcome?: string;
  provider?: string;
  model_id?: string;
  route_key?: string;
  fingerprint_prefix?: string;
  count?: number;
};

type GateRow = {
  verification_status?: string;
  review_priority?: string;
  blocked_downstream_actions?: string[];
  allowed_downstream_actions?: string[];
  provider?: string;
  model_id?: string;
  count?: number;
};

type AttributionSummary = {
  schema_version?: number;
  generated_at?: string;
  scope?: {
    days?: number;
    project_id?: string | null;
    signal_id?: string | null;
    record_families?: string[];
  };
  coverage?: CoverageSummary;
  excluded?: {
    legacy_v0?: number;
    malformed?: number;
    manual_unverified?: number;
  };
  by_record_family?: FamilyRow[];
  by_model?: ModelRow[];
  by_route?: RouteRow[];
  review_outcomes?: OutcomeRow[];
  gate_outcomes?: GateRow[];
};

type AttributionResponse = {
  summary?: AttributionSummary;
  message?: string;
};

const dayOptions = [7, 30, 90];

export default function ModelAttributionDiagnosticsPage() {
  const [summary, setSummary] = useState<AttributionSummary | null>(null);
  const [days, setDays] = useState(30);
  const [projectId, setProjectId] = useState("");
  const [signalId, setSignalId] = useState("");
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState("");

  const queryString = useMemo(() => {
    const params = new URLSearchParams();
    params.set("days", String(days));
    if (projectId.trim()) {
      params.set("project_id", projectId.trim());
    }
    if (signalId.trim()) {
      params.set("signal_id", signalId.trim());
    }
    return params.toString();
  }, [days, projectId, signalId]);

  async function loadSummary() {
    setLoading(true);
    setErrorMessage("");

    try {
      const response = await adminFetch(apiUrl(`/projects/model-attribution/summary?${queryString}`));
      if (!response.ok) {
        throw new Error(`Request failed with ${response.status}`);
      }

      const data = (await response.json()) as AttributionResponse;
      setSummary(data.summary || null);
    } catch (error) {
      console.error("Failed to load model attribution diagnostics:", error);
      setSummary(null);
      setErrorMessage(
        "Model attribution diagnostics could not be loaded. Confirm the backend is running with the latest Slice B route."
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadSummary();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [queryString]);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    loadSummary();
  }

  const coverage = summary?.coverage || {};
  const excluded = summary?.excluded || {};
  const generatedAt = summary?.generated_at ? new Date(summary.generated_at).toLocaleString() : "Not loaded";

  return (
    <AppContainer>
      <RequireAdminAuth>
        <PageHeader
          title="Model Attribution"
          description="Read-only diagnostics for model provenance coverage and v1-only attribution. This page describes observed records; it does not rank models, route traffic, or change verification gates."
          size="compact"
        />

        <SectionCard title="Diagnostics Scope">
          <form onSubmit={handleSubmit} style={scopeGridStyle}>
            <div style={controlGroupStyle}>
              <div style={fieldLabelStyle}>Window</div>
              <div style={dayButtonRowStyle}>
                {dayOptions.map((option) => (
                  <button
                    key={option}
                    type="button"
                    onClick={() => setDays(option)}
                    style={option === days ? selectedDayButtonStyle : dayButtonStyle}
                  >
                    {option}d
                  </button>
                ))}
              </div>
            </div>

            <label style={controlGroupStyle}>
              <span style={fieldLabelStyle}>Project ID</span>
              <input
                value={projectId}
                onChange={(event) => setProjectId(event.target.value)}
                placeholder="Optional"
                style={inputStyle}
              />
            </label>

            <label style={controlGroupStyle}>
              <span style={fieldLabelStyle}>Signal ID</span>
              <input
                value={signalId}
                onChange={(event) => setSignalId(event.target.value)}
                placeholder="Optional"
                style={inputStyle}
              />
            </label>

            <div style={actionGroupStyle}>
              <button type="submit" style={primaryButtonStyle} disabled={loading}>
                {loading ? "Loading" : "Refresh"}
              </button>
              <Link href="/admin" style={secondaryButtonStyle}>
                Back to Admin
              </Link>
            </div>
          </form>

          <div style={scopeNoteStyle}>
            <span>Generated: {generatedAt}</span>
            <span>Schema: {summary?.schema_version || "n/a"}</span>
            <span>Families: {(summary?.scope?.record_families || []).join(", ") || "n/a"}</span>
          </div>
        </SectionCard>

        {errorMessage ? (
          <div style={errorStyle}>{errorMessage}</div>
        ) : null}

        <SectionCard title="Coverage">
          {loading ? (
            <LoadingLine />
          ) : (
            <div style={metricGridStyle}>
              <MetricCell label="Total records" value={coverage.total_records} />
              <MetricCell label="V1 provenance" value={coverage.v1_records} />
              <MetricCell label="Eligible attribution" value={coverage.attribution_eligible_records} />
              <MetricCell label="Legacy/v0" value={coverage.legacy_v0_records} tone="muted" />
              <MetricCell label="Malformed" value={coverage.malformed_records} tone="warning" />
              <MetricCell label="Manual unverified" value={coverage.manual_unverified_records} tone="muted" />
            </div>
          )}
        </SectionCard>

        <SectionCard title="Exclusions">
          {loading ? (
            <LoadingLine />
          ) : (
            <div style={exclusionLayoutStyle}>
              <ExclusionCell
                label="Legacy/v0"
                value={excluded.legacy_v0}
                description="Counted for coverage only; not used in attribution distribution."
              />
              <ExclusionCell
                label="Malformed"
                value={excluded.malformed}
                description="Stored records with incomplete or invalid provenance fields."
              />
              <ExclusionCell
                label="Manual unverified"
                value={excluded.manual_unverified}
                description="Manual records that remain outside claim-support attribution semantics."
              />
            </div>
          )}
        </SectionCard>

        <SectionCard title="Record Families">
          <CoverageTable rows={summary?.by_record_family || []} loading={loading} />
        </SectionCard>

        <div style={twoColumnStyle}>
          <SectionCard title="Model Distribution">
            <ModelTable rows={summary?.by_model || []} loading={loading} />
          </SectionCard>

          <SectionCard title="Route Distribution">
            <RouteTable rows={summary?.by_route || []} loading={loading} />
          </SectionCard>
        </div>

        <SectionCard title="Review Outcomes">
          <OutcomeTable rows={summary?.review_outcomes || []} loading={loading} />
        </SectionCard>

        <SectionCard title="Gate Outcomes">
          <GateTable rows={summary?.gate_outcomes || []} loading={loading} />
        </SectionCard>
      </RequireAdminAuth>
    </AppContainer>
  );
}

function LoadingLine() {
  return <div style={emptyStateStyle}>Loading model attribution diagnostics...</div>;
}

function EmptyLine({ label }: { label: string }) {
  return <div style={emptyStateStyle}>{label}</div>;
}

function MetricCell({
  label,
  value,
  tone = "default",
}: {
  label: string;
  value?: number;
  tone?: "default" | "muted" | "warning";
}) {
  return (
    <div style={metricCellStyle}>
      <div style={{ ...metricLabelStyle, color: metricToneColor[tone] }}>{label}</div>
      <div style={metricValueStyle}>{value ?? 0}</div>
    </div>
  );
}

function ExclusionCell({
  label,
  value,
  description,
}: {
  label: string;
  value?: number;
  description: string;
}) {
  return (
    <div style={exclusionCellStyle}>
      <div style={exclusionHeaderStyle}>
        <span>{label}</span>
        <strong>{value ?? 0}</strong>
      </div>
      <div style={exclusionDescriptionStyle}>{description}</div>
    </div>
  );
}

function CoverageTable({ rows, loading }: { rows: FamilyRow[]; loading: boolean }) {
  if (loading) {
    return <LoadingLine />;
  }
  if (!rows.length) {
    return <EmptyLine label="No record family coverage for this scope." />;
  }
  return (
    <Table>
      <thead>
        <tr>
          <Th>Family</Th>
          <Th>Total</Th>
          <Th>V1</Th>
          <Th>Eligible</Th>
          <Th>Legacy/v0</Th>
          <Th>Malformed</Th>
          <Th>Manual unverified</Th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.record_family || "unknown"}>
            <Td>{row.record_family || "unknown"}</Td>
            <Td>{row.total_records ?? 0}</Td>
            <Td>{row.v1_records ?? 0}</Td>
            <Td>{row.attribution_eligible_records ?? 0}</Td>
            <Td>{row.legacy_v0_records ?? 0}</Td>
            <Td>{row.malformed_records ?? 0}</Td>
            <Td>{row.manual_unverified_records ?? 0}</Td>
          </tr>
        ))}
      </tbody>
    </Table>
  );
}

function ModelTable({ rows, loading }: { rows: ModelRow[]; loading: boolean }) {
  if (loading) {
    return <LoadingLine />;
  }
  if (!rows.length) {
    return <EmptyLine label="No v1 model distribution records in this scope." />;
  }
  return (
    <Table>
      <thead>
        <tr>
          <Th>Provider</Th>
          <Th>Model</Th>
          <Th>Records</Th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={`${row.provider || "unknown"}:${row.model_id || "unknown"}`}>
            <Td>{row.provider || "unknown"}</Td>
            <Td>{row.model_id || "unknown"}</Td>
            <Td>{row.count ?? 0}</Td>
          </tr>
        ))}
      </tbody>
    </Table>
  );
}

function RouteTable({ rows, loading }: { rows: RouteRow[]; loading: boolean }) {
  if (loading) {
    return <LoadingLine />;
  }
  if (!rows.length) {
    return <EmptyLine label="No route distribution records in this scope." />;
  }
  return (
    <Table>
      <thead>
        <tr>
          <Th>Route</Th>
          <Th>Task</Th>
          <Th>Prompt</Th>
          <Th>Records</Th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr
            key={`${row.route_key || "unknown"}:${row.task_type || "unknown"}:${
              row.prompt_template_id || "none"
            }`}
          >
            <Td>{row.route_key || "unknown"}</Td>
            <Td>{row.task_type || "unknown"}</Td>
            <Td>
              {row.prompt_template_id || "none"}
              {row.prompt_template_version ? ` / ${row.prompt_template_version}` : ""}
            </Td>
            <Td>{row.count ?? 0}</Td>
          </tr>
        ))}
      </tbody>
    </Table>
  );
}

function OutcomeTable({ rows, loading }: { rows: OutcomeRow[]; loading: boolean }) {
  if (loading) {
    return <LoadingLine />;
  }
  if (!rows.length) {
    return <EmptyLine label="No review outcome attribution records in this scope." />;
  }
  return (
    <Table>
      <thead>
        <tr>
          <Th>Outcome</Th>
          <Th>Provider</Th>
          <Th>Model</Th>
          <Th>Route</Th>
          <Th>Fingerprint</Th>
          <Th>Records</Th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr
            key={`${row.outcome || "unknown"}:${row.provider || "unknown"}:${
              row.model_id || "unknown"
            }:${row.route_key || "unknown"}:${row.fingerprint_prefix || "none"}`}
          >
            <Td>{row.outcome || "unknown"}</Td>
            <Td>{row.provider || "unknown"}</Td>
            <Td>{row.model_id || "unknown"}</Td>
            <Td>{row.route_key || "unknown"}</Td>
            <Td>{row.fingerprint_prefix || "none"}</Td>
            <Td>{row.count ?? 0}</Td>
          </tr>
        ))}
      </tbody>
    </Table>
  );
}

function GateTable({ rows, loading }: { rows: GateRow[]; loading: boolean }) {
  if (loading) {
    return <LoadingLine />;
  }
  if (!rows.length) {
    return <EmptyLine label="No gate outcome attribution records in this scope." />;
  }
  return (
    <Table>
      <thead>
        <tr>
          <Th>Verification</Th>
          <Th>Review priority</Th>
          <Th>Blocked</Th>
          <Th>Allowed</Th>
          <Th>Provider</Th>
          <Th>Model</Th>
          <Th>Records</Th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr
            key={`${row.verification_status || "unknown"}:${row.review_priority || "unknown"}:${
              row.provider || "unknown"
            }:${row.model_id || "unknown"}:${(row.blocked_downstream_actions || []).join("|")}`}
          >
            <Td>{row.verification_status || "unknown"}</Td>
            <Td>{row.review_priority || "unknown"}</Td>
            <Td>{formatActionList(row.blocked_downstream_actions)}</Td>
            <Td>{formatActionList(row.allowed_downstream_actions)}</Td>
            <Td>{row.provider || "unknown"}</Td>
            <Td>{row.model_id || "unknown"}</Td>
            <Td>{row.count ?? 0}</Td>
          </tr>
        ))}
      </tbody>
    </Table>
  );
}

function formatActionList(items?: string[]) {
  if (!items || !items.length) {
    return "none";
  }
  return items.join(", ");
}

function Table({ children }: { children: ReactNode }) {
  return (
    <div style={tableScrollStyle}>
      <table style={tableStyle}>{children}</table>
    </div>
  );
}

function Th({ children }: { children: ReactNode }) {
  return <th style={thStyle}>{children}</th>;
}

function Td({ children }: { children: ReactNode }) {
  return <td style={tdStyle}>{children}</td>;
}

const scopeGridStyle = {
  display: "grid",
  gridTemplateColumns: "minmax(220px, 0.8fr) minmax(180px, 1fr) minmax(180px, 1fr) auto",
  gap: "12px",
  alignItems: "end",
} as const;

const controlGroupStyle = {
  display: "grid",
  gap: "8px",
  minWidth: 0,
} as const;

const actionGroupStyle = {
  display: "flex",
  gap: "8px",
  flexWrap: "wrap",
  alignItems: "center",
} as const;

const fieldLabelStyle = {
  fontSize: "12px",
  fontWeight: 850,
  color: "var(--app-text-muted)",
  textTransform: "uppercase",
  letterSpacing: 0,
} as const;

const dayButtonRowStyle = {
  display: "inline-flex",
  gap: "6px",
  flexWrap: "wrap",
} as const;

const dayButtonStyle = {
  minHeight: "42px",
  border: "1px solid var(--app-secondary-action-border)",
  borderRadius: "8px",
  background: "var(--app-secondary-action-bg)",
  color: "var(--app-secondary-action-fg)",
  padding: "8px 12px",
  fontSize: "14px",
  fontWeight: 800,
  cursor: "pointer",
} as const;

const selectedDayButtonStyle = {
  ...dayButtonStyle,
  border: "1px solid var(--app-primary-action-border)",
  background: "var(--app-primary-action-bg)",
  color: "var(--app-primary-action-fg)",
} as const;

const inputStyle = {
  width: "100%",
  minHeight: "42px",
  border: "1px solid var(--app-input-border)",
  borderRadius: "8px",
  background: "var(--app-input-bg)",
  color: "var(--app-input-fg)",
  padding: "8px 10px",
  fontSize: "14px",
  fontWeight: 650,
} as const;

const primaryButtonStyle = {
  minHeight: "42px",
  border: "1px solid var(--app-primary-action-border)",
  borderRadius: "8px",
  background: "var(--app-primary-action-bg)",
  color: "var(--app-primary-action-fg)",
  padding: "9px 14px",
  fontSize: "14px",
  fontWeight: 850,
  cursor: "pointer",
} as const;

const secondaryButtonStyle = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  minHeight: "42px",
  border: "1px solid var(--app-secondary-action-border)",
  borderRadius: "8px",
  background: "var(--app-secondary-action-bg)",
  color: "var(--app-secondary-action-fg)",
  padding: "9px 14px",
  fontSize: "14px",
  fontWeight: 800,
  textDecoration: "none",
} as const;

const scopeNoteStyle = {
  display: "flex",
  flexWrap: "wrap",
  gap: "10px 18px",
  marginTop: "16px",
  paddingTop: "14px",
  borderTop: "1px solid rgba(148, 163, 184, 0.16)",
  color: "var(--app-text-muted)",
  fontSize: "13px",
  lineHeight: 1.6,
} as const;

const errorStyle = {
  border: "1px solid var(--app-danger-border)",
  background: "var(--app-danger-bg)",
  color: "var(--app-danger-fg)",
  borderRadius: "8px",
  padding: "14px 16px",
  fontSize: "14px",
  fontWeight: 700,
} as const;

const metricGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))",
  gap: "8px",
} as const;

const metricCellStyle = {
  padding: "16px",
  border: "1px solid rgba(148, 163, 184, 0.18)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  minWidth: 0,
} as const;

const metricLabelStyle = {
  fontSize: "12px",
  fontWeight: 850,
  textTransform: "uppercase",
  letterSpacing: 0,
} as const;

const metricValueStyle = {
  marginTop: "8px",
  color: "var(--app-text-strong)",
  fontSize: "30px",
  fontWeight: 850,
} as const;

const metricToneColor = {
  default: "var(--app-info-fg)",
  muted: "var(--app-text-muted)",
  warning: "var(--app-warning-fg)",
} as const;

const exclusionLayoutStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
  gap: "12px",
} as const;

const exclusionCellStyle = {
  border: "1px solid rgba(148, 163, 184, 0.18)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  padding: "15px",
} as const;

const exclusionHeaderStyle = {
  display: "flex",
  justifyContent: "space-between",
  gap: "12px",
  color: "var(--app-text-strong)",
  fontSize: "15px",
  fontWeight: 850,
} as const;

const exclusionDescriptionStyle = {
  marginTop: "8px",
  color: "var(--app-text-muted)",
  fontSize: "14px",
  lineHeight: 1.65,
} as const;

const twoColumnStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(360px, 1fr))",
  gap: "18px",
  alignItems: "start",
} as const;

const emptyStateStyle = {
  color: "var(--app-text-muted)",
  fontSize: "14px",
  lineHeight: 1.65,
} as const;

const tableScrollStyle = {
  width: "100%",
  overflowX: "auto",
  border: "1px solid rgba(148, 163, 184, 0.14)",
  borderRadius: "8px",
} as const;

const tableStyle = {
  width: "100%",
  borderCollapse: "separate",
  borderSpacing: 0,
  minWidth: "640px",
  fontSize: "14px",
} as const;

const thStyle = {
  textAlign: "left",
  padding: "10px 12px",
  borderBottom: "1px solid rgba(148, 163, 184, 0.18)",
  color: "var(--app-text-muted)",
  fontSize: "12px",
  fontWeight: 850,
  textTransform: "uppercase",
  letterSpacing: 0,
  whiteSpace: "nowrap",
} as const;

const tdStyle = {
  padding: "11px 12px",
  borderBottom: "1px solid rgba(148, 163, 184, 0.12)",
  color: "var(--app-text-strong)",
  fontWeight: 650,
  verticalAlign: "top",
  overflowWrap: "anywhere",
} as const;
