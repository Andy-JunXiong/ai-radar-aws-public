"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import Link from "next/link";

import AppContainer from "@/components/AppContainer";
import PageHeader from "@/components/PageHeader";
import RequireAdminAuth from "@/components/RequireAdminAuth";
import SectionCard from "@/components/SectionCard";
import { apiUrl } from "@/lib/api";
import { adminFetch } from "@/lib/adminAuth";

type BufferItem = {
  record_id?: string;
  project_id?: string;
  signal_id?: string;
  signal_title?: string;
  outcome?: string;
  review_reason?: string;
  candidate_source?: string;
  verification_status?: string;
  blocked_downstream_actions?: string[];
  unsupported_claim_count?: number;
  inferred_claim_count?: number;
  confidence_label?: string;
  reviewed_at?: string;
  pattern_key?: string;
  caution?: string;
};

type RejectedLearningBuffer = {
  schema_version?: number;
  context_role?: string;
  source?: string;
  evidence_boundary?: string;
  project_id?: string;
  signal_id?: string;
  limit?: number;
  source_record_count?: number;
  outcome_counts?: Record<string, number>;
  buffer_outcomes?: string[];
  prompt_readiness?: {
    status?: string;
    safe_for_prompt_injection?: boolean;
    reasons?: string[];
    next_action?: string;
  };
  item_count?: number;
  items?: BufferItem[];
  message?: string;
};

const DEFAULT_LIMIT = 10;

export default function RejectedLearningBufferPage() {
  const [projectId, setProjectId] = useState("");
  const [signalId, setSignalId] = useState("");
  const [limit, setLimit] = useState(DEFAULT_LIMIT);
  const [buffer, setBuffer] = useState<RejectedLearningBuffer | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const querySummary = useMemo(() => {
    const parts = [
      projectId.trim() ? `project_id=${projectId.trim()}` : "all projects",
      signalId.trim() ? `signal_id=${signalId.trim()}` : "all signals",
      `limit=${limit}`,
    ];
    return parts.join(" / ");
  }, [projectId, signalId, limit]);

  async function loadBuffer() {
    setLoading(true);
    setError("");

    const params = new URLSearchParams();
    if (projectId.trim()) params.set("project_id", projectId.trim());
    if (signalId.trim()) params.set("signal_id", signalId.trim());
    params.set("limit", String(limit));

    try {
      const response = await adminFetch(
        apiUrl(`/projects/rejected-learning-buffer?${params.toString()}`),
        { cache: "no-store" },
      );
      if (!response.ok) {
        throw new Error(`Rejected learning buffer failed with HTTP ${response.status}`);
      }
      const payload = (await response.json()) as RejectedLearningBuffer;
      setBuffer(payload);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Rejected learning buffer could not load.");
      setBuffer(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadBuffer();
    // Initial load should use the default query only.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void loadBuffer();
  }

  const items = buffer?.items || [];

  return (
    <AppContainer>
      <RequireAdminAuth>
        <PageHeader
          title="Rejected Learning Buffer"
          description="Read-only caution context from rejected or dismissed Project Takeaway review records. This diagnostic is not factual evidence and is not wired into generator prompts."
          size="compact"
        />

        <SectionCard title="Boundary">
          <div style={boundaryGridStyle}>
            <BoundaryCard label="Context Role" value={buffer?.context_role || "bounded_caution"} />
            <BoundaryCard label="Source" value={buffer?.source || "project_review_records"} />
            <BoundaryCard label="Evidence Boundary" value={buffer?.evidence_boundary || "not_factual_evidence"} />
            <BoundaryCard label="Items" value={String(buffer?.item_count ?? items.length)} />
            <BoundaryCard label="Source Records" value={String(buffer?.source_record_count ?? 0)} />
            <BoundaryCard label="Buffer Outcomes" value={(buffer?.buffer_outcomes || ["dismissed", "rejected"]).join(", ")} />
          </div>
        </SectionCard>

        <SectionCard title="Prompt Readiness">
          <div style={readinessGridStyle}>
            <BoundaryCard label="Status" value={buffer?.prompt_readiness?.status || "not_loaded"} />
            <BoundaryCard
              label="Safe For Prompt Injection"
              value={buffer?.prompt_readiness?.safe_for_prompt_injection ? "yes" : "no"}
            />
          </div>
          <div style={readinessBodyStyle}>
            {(buffer?.prompt_readiness?.reasons || ["Load the buffer to inspect prompt readiness."]).map((reason) => (
              <div key={reason} style={readinessReasonStyle}>{reason}</div>
            ))}
            {buffer?.prompt_readiness?.next_action ? (
              <div style={nextActionStyle}>
                <strong>Next:</strong> {buffer.prompt_readiness.next_action}
              </div>
            ) : null}
          </div>
        </SectionCard>

        <SectionCard title="Query">
          <form onSubmit={handleSubmit} style={queryFormStyle}>
            <label style={fieldStyle}>
              <span style={fieldLabelStyle}>Project ID</span>
              <input
                value={projectId}
                onChange={(event) => setProjectId(event.target.value)}
                placeholder="optional"
                style={inputStyle}
              />
            </label>
            <label style={fieldStyle}>
              <span style={fieldLabelStyle}>Signal ID</span>
              <input
                value={signalId}
                onChange={(event) => setSignalId(event.target.value)}
                placeholder="optional"
                style={inputStyle}
              />
            </label>
            <label style={fieldStyle}>
              <span style={fieldLabelStyle}>Limit</span>
              <input
                type="number"
                min={1}
                max={20}
                value={limit}
                onChange={(event) => setLimit(Math.max(1, Math.min(20, Number(event.target.value) || DEFAULT_LIMIT)))}
                style={inputStyle}
              />
            </label>
            <button type="submit" style={primaryButtonStyle} disabled={loading}>
              {loading ? "Loading" : "Load Buffer"}
            </button>
          </form>
          <div style={querySummaryStyle}>{querySummary}</div>
        </SectionCard>

        <SectionCard title="Caution Items">
          {error ? <div style={errorStyle}>{error}</div> : null}
          {loading ? <div style={mutedStyle}>Loading rejected learning buffer...</div> : null}
          {!loading && !error && items.length === 0 ? (
            <div style={emptyDiagnosticStyle}>
              <div style={emptyTitleStyle}>No rejected or dismissed review records matched this query.</div>
              <div style={mutedStyle}>
                The buffer only includes outcomes listed under Buffer Outcomes. Current matching review records:
              </div>
              <OutcomeMix counts={buffer?.outcome_counts || {}} />
            </div>
          ) : null}
          <div style={itemListStyle}>
            {items.map((item, index) => (
              <article key={item.record_id || `${item.signal_id || "item"}-${index}`} style={itemCardStyle}>
                <div style={itemHeaderStyle}>
                  <div>
                    <div style={eyebrowStyle}>{item.outcome || "closed"} caution</div>
                    <h2 style={itemTitleStyle}>{item.signal_title || "Untitled review record"}</h2>
                  </div>
                  <span style={badgeStyle}>{item.verification_status || "unknown verification"}</span>
                </div>

                <p style={cautionStyle}>{item.caution || "No caution text was generated for this record."}</p>

                <div style={metaGridStyle}>
                  <Meta label="Project" value={item.project_id || "unknown"} />
                  <Meta label="Signal" value={item.signal_id || "unknown"} />
                  <Meta label="Source" value={item.candidate_source || "unknown"} />
                  <Meta label="Confidence" value={item.confidence_label || "unknown"} />
                  <Meta label="Unsupported Claims" value={String(item.unsupported_claim_count ?? 0)} />
                  <Meta label="Inferred Claims" value={String(item.inferred_claim_count ?? 0)} />
                </div>

                {item.blocked_downstream_actions?.length ? (
                  <div style={chipRowStyle}>
                    {item.blocked_downstream_actions.map((action) => (
                      <span key={action} style={chipStyle}>{action}</span>
                    ))}
                  </div>
                ) : null}

                {item.review_reason ? (
                  <div style={reasonStyle}>
                    <strong>Review reason:</strong> {item.review_reason}
                  </div>
                ) : null}

                <div style={linkRowStyle}>
                  {item.record_id ? (
                    <Link href={`/workspace/projects/review/record?id=${encodeURIComponent(item.record_id)}`} style={secondaryLinkStyle}>
                      Open Review Record
                    </Link>
                  ) : null}
                  {item.signal_id ? (
                    <Link href={`/signals/detail?id=${encodeURIComponent(item.signal_id)}`} style={secondaryLinkStyle}>
                      Open Signal
                    </Link>
                  ) : null}
                </div>
              </article>
            ))}
          </div>
        </SectionCard>
      </RequireAdminAuth>
    </AppContainer>
  );
}

function BoundaryCard({ label, value }: { label: string; value: string }) {
  return (
    <div style={boundaryCardStyle}>
      <div style={eyebrowStyle}>{label}</div>
      <div style={boundaryValueStyle}>{value}</div>
    </div>
  );
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div style={metaItemStyle}>
      <span style={metaLabelStyle}>{label}</span>
      <strong style={metaValueStyle}>{value}</strong>
    </div>
  );
}

function OutcomeMix({ counts }: { counts: Record<string, number> }) {
  const entries = Object.entries(counts);
  if (!entries.length) {
    return <div style={mutedStyle}>No Project ReviewRecords were found for the current query.</div>;
  }
  return (
    <div style={chipRowStyle}>
      {entries.map(([outcome, count]) => (
        <span key={outcome} style={neutralChipStyle}>{outcome}: {count}</span>
      ))}
    </div>
  );
}

const boundaryGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))",
  gap: "12px",
} as const;

const readinessGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
  gap: "12px",
} as const;

const readinessBodyStyle = {
  marginTop: "14px",
  display: "grid",
  gap: "9px",
} as const;

const readinessReasonStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  padding: "10px",
  background: "var(--app-surface-muted-bg)",
  color: "var(--app-text-muted)",
  fontSize: "13px",
  lineHeight: 1.55,
} as const;

const nextActionStyle = {
  border: "1px solid var(--app-info-border)",
  borderRadius: "8px",
  padding: "10px",
  background: "var(--app-info-bg)",
  color: "var(--app-info-fg)",
  fontSize: "13px",
  lineHeight: 1.55,
} as const;

const boundaryCardStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  padding: "14px",
  background: "var(--app-surface-muted-bg)",
} as const;

const boundaryValueStyle = {
  marginTop: "7px",
  fontSize: "16px",
  fontWeight: 800,
  color: "var(--app-text-strong)",
  overflowWrap: "anywhere",
} as const;

const queryFormStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr)) auto",
  alignItems: "end",
  gap: "12px",
} as const;

const fieldStyle = {
  display: "grid",
  gap: "6px",
} as const;

const fieldLabelStyle = {
  fontSize: "12px",
  fontWeight: 800,
  color: "var(--app-text-muted)",
} as const;

const inputStyle = {
  minHeight: "40px",
  border: "1px solid var(--app-input-border)",
  borderRadius: "8px",
  padding: "8px 10px",
  fontSize: "14px",
  color: "var(--app-input-fg)",
  background: "var(--app-input-bg)",
} as const;

const primaryButtonStyle = {
  minHeight: "40px",
  border: "1px solid var(--app-primary-action-border)",
  borderRadius: "8px",
  background: "var(--app-primary-action-bg)",
  color: "var(--app-primary-action-fg)",
  padding: "8px 14px",
  fontWeight: 850,
  cursor: "pointer",
} as const;

const querySummaryStyle = {
  marginTop: "12px",
  fontSize: "13px",
  color: "var(--app-text-muted)",
} as const;

const itemListStyle = {
  display: "grid",
  gap: "14px",
} as const;

const itemCardStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  padding: "16px",
  background: "var(--app-surface-muted-bg)",
} as const;

const itemHeaderStyle = {
  display: "flex",
  justifyContent: "space-between",
  gap: "12px",
  alignItems: "flex-start",
} as const;

const eyebrowStyle = {
  fontSize: "11px",
  fontWeight: 850,
  color: "var(--app-text-subtle)",
  textTransform: "uppercase",
  letterSpacing: 0,
} as const;

const itemTitleStyle = {
  margin: "5px 0 0",
  fontSize: "20px",
  lineHeight: 1.3,
  color: "var(--app-text-strong)",
} as const;

const badgeStyle = {
  border: "1px solid var(--app-chip-border)",
  borderRadius: "999px",
  padding: "5px 9px",
  fontSize: "12px",
  fontWeight: 800,
  color: "var(--app-chip-fg)",
  background: "var(--app-chip-bg)",
  whiteSpace: "nowrap",
} as const;

const cautionStyle = {
  margin: "14px 0",
  fontSize: "14px",
  lineHeight: 1.65,
  color: "var(--app-text-muted)",
} as const;

const metaGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
  gap: "9px",
} as const;

const metaItemStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  padding: "9px",
  background: "var(--app-surface-bg)",
  display: "grid",
  gap: "4px",
} as const;

const metaLabelStyle = {
  fontSize: "11px",
  color: "var(--app-text-subtle)",
  fontWeight: 800,
} as const;

const metaValueStyle = {
  fontSize: "13px",
  color: "var(--app-text-strong)",
  overflowWrap: "anywhere",
} as const;

const chipRowStyle = {
  display: "flex",
  flexWrap: "wrap",
  gap: "8px",
  marginTop: "12px",
} as const;

const chipStyle = {
  border: "1px solid var(--app-danger-border)",
  borderRadius: "999px",
  background: "var(--app-danger-bg)",
  color: "var(--app-danger-fg)",
  padding: "5px 9px",
  fontSize: "12px",
  fontWeight: 800,
} as const;

const neutralChipStyle = {
  border: "1px solid var(--app-chip-border)",
  borderRadius: "999px",
  background: "var(--app-chip-bg)",
  color: "var(--app-chip-fg)",
  padding: "5px 9px",
  fontSize: "12px",
  fontWeight: 800,
} as const;

const emptyDiagnosticStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  padding: "14px",
  background: "var(--app-surface-muted-bg)",
  display: "grid",
  gap: "10px",
} as const;

const emptyTitleStyle = {
  fontSize: "15px",
  fontWeight: 850,
  color: "var(--app-text-strong)",
} as const;

const reasonStyle = {
  marginTop: "12px",
  padding: "10px",
  border: "1px solid var(--app-warning-border)",
  borderRadius: "8px",
  background: "var(--app-warning-bg)",
  fontSize: "13px",
  lineHeight: 1.55,
  color: "var(--app-warning-fg)",
} as const;

const linkRowStyle = {
  marginTop: "12px",
  display: "flex",
  gap: "10px",
  flexWrap: "wrap",
} as const;

const secondaryLinkStyle = {
  border: "1px solid var(--app-secondary-action-border)",
  borderRadius: "8px",
  padding: "7px 10px",
  textDecoration: "none",
  color: "var(--app-secondary-action-fg)",
  background: "var(--app-secondary-action-bg)",
  fontSize: "13px",
  fontWeight: 800,
} as const;

const mutedStyle = {
  color: "var(--app-text-muted)",
  fontSize: "14px",
} as const;

const errorStyle = {
  border: "1px solid var(--app-danger-border)",
  borderRadius: "8px",
  background: "var(--app-danger-bg)",
  color: "var(--app-danger-fg)",
  padding: "12px",
  marginBottom: "12px",
  fontSize: "14px",
} as const;
