"use client";

import { useState, type CSSProperties } from "react";

type DecisionTraceEvent = {
  event_type?: string;
  actor?: string;
  timestamp?: string;
  status_before?: string;
  status_after?: string;
  route?: string;
  support?: {
    saved_reason?: string | null;
    verification_status?: string | null;
    blocked_downstream_actions?: string[];
    allowed_downstream_actions?: string[];
    claim_support_summary?: Record<string, number>;
    evidence_level?: string | null;
    evidence_pack_id?: string | null;
  };
};

type VerificationMetadata = {
  verified_insight?: {
    status?: string;
    evidence?: {
      level?: string;
      pack_id?: string | null;
    };
    claims?: {
      support_summary?: Record<string, number>;
    };
    action_policy?: {
      allowed?: string[];
      blocked?: string[];
    };
  };
  verification_status?: string;
  allowed_downstream_actions?: string[];
  blocked_downstream_actions?: string[];
  claim_support_summary?: Record<string, number>;
  evidence_quality?: {
    level?: string;
    score?: number;
    reason_codes?: string[];
  };
  limitations?: string[];
  downgrade_reason?: string | null;
};

type ProjectCandidateSummary = {
  projectId?: string;
  projectName?: string;
  status?: string;
  reviewOutcome?: string;
  watchStatus?: string;
  actionCompletedAt?: string;
};

type NodeTone = "future" | "chosen" | "current" | "blocked" | "paused" | "support";
type DecisionMapView = "trajectory" | "schema";
type LifecycleProvenance = "direct" | "derived" | "inferred" | "missing" | "legacy" | "unknown";

type LifecycleProbeStep = {
  step_id?: string;
  label?: string;
  state?: string;
  provenance?: "direct" | "derived" | "inferred" | "missing" | string;
  source?: string;
  timestamp?: string;
  actor?: string;
  detail?: string;
  support?: Record<string, unknown>;
  gaps?: string[];
};

type SignalLifecycleProbe = {
  adapter?: string;
  contract_version?: string;
  authoritative?: boolean;
  signal_id?: string;
  title?: string;
  status?: string;
  steps?: LifecycleProbeStep[];
  gap_report?: {
    direct_fields?: string[];
    service_outputs_not_persisted?: string[];
    architecture_gaps?: string[];
  };
  project_context?: {
    review_records_count?: number;
    calibration_events_count?: number;
  };
};

type MapNode = {
  id: string;
  title: string;
  detail: string;
  tone: NodeTone;
  chips?: string[];
  stateLabel?: string;
  rationale?: string[];
  statusBadge?: string;
};

type SignalDecisionFlowProps = {
  status?: string;
  source?: string;
  publishedAt?: string | null;
  savedReason?: string | null;
  hasInsight: boolean;
  workspaceSaved?: boolean;
  modelUsed?: string;
  generationMode?: string;
  verification?: VerificationMetadata;
  decisionTrace?: DecisionTraceEvent[];
  projectCandidates?: ProjectCandidateSummary[];
  lifecycleProbe?: SignalLifecycleProbe | null;
  lifecycleProbeLoading?: boolean;
  lifecycleProbeError?: string;
};

const normalizeStatus = (value?: string) => {
  const status = (value || "pending").toLowerCase();
  return ["pending", "saved", "analyzed", "completed", "rejected"].includes(status) ? status : "pending";
};

const hasTraceEvent = (trace: DecisionTraceEvent[], eventTypes: string[]) =>
  trace.some((event) => eventTypes.includes(event.event_type || ""));

const compactList = (items?: string[]) => {
  if (!items || items.length === 0) return "";
  const prettyItems = items.map((item) => prettyStatus(item));
  if (prettyItems.length <= 2) return prettyItems.join(", ");
  return `${prettyItems.slice(0, 2).join(", ")} +${prettyItems.length - 2}`;
};

const summarizeClaims = (summary?: Record<string, number>) => {
  if (!summary || Object.keys(summary).length === 0) return "";
  return Object.entries(summary)
    .filter(([, count]) => count > 0)
    .map(([key, count]) => `${key.replaceAll("_", " ")} ${count}`)
    .slice(0, 4)
    .join(", ");
};

const prettyStatus = (value?: string) => (value || "").replaceAll("_", " ");

const compactDate = (value?: string | null) => {
  if (!value) return "";
  return value.slice(0, 10);
};

const normalizeProvenance = (value?: string): LifecycleProvenance => {
  const provenance = (value || "").toLowerCase();
  if (["direct", "derived", "inferred", "missing", "legacy"].includes(provenance)) {
    return provenance as LifecycleProvenance;
  }
  return "unknown";
};

const provenanceMeta = (provenance: LifecycleProvenance, source?: string) => {
  const directEvent = provenance === "direct" && (source || "").toLowerCase() === "signal_lifecycle_event";
  if (directEvent) {
    return {
      label: "Direct Event",
      shortLabel: "DIRECT EVENT",
      detail: "Recorded lifecycle event",
      color: "var(--app-success-fg)",
      background: "var(--app-success-bg)",
      border: "var(--app-success-border)",
    };
  }
  const meta: Record<LifecycleProvenance, { label: string; shortLabel: string; detail: string; color: string; background: string; border: string }> = {
    direct: {
      label: "Direct Field",
      shortLabel: "DIRECT FIELD",
      detail: "Stored signal field",
      color: "var(--app-success-fg)",
      background: "var(--app-success-bg)",
      border: "var(--app-success-border)",
    },
    derived: {
      label: "Derived",
      shortLabel: "DERIVED",
      detail: "Joined from project-side records",
      color: "var(--app-tag-fg)",
      background: "var(--app-tag-bg)",
      border: "var(--app-surface-strong-border)",
    },
    inferred: {
      label: "Inferred",
      shortLabel: "INFERRED",
      detail: "Reconstructed from current state",
      color: "var(--app-warning-fg)",
      background: "var(--app-warning-bg)",
      border: "var(--app-warning-border)",
    },
    missing: {
      label: "Missing",
      shortLabel: "MISSING",
      detail: "No durable evidence attached",
      color: "var(--app-danger-fg)",
      background: "var(--app-danger-bg)",
      border: "var(--app-danger-border)",
    },
    legacy: {
      label: "Legacy",
      shortLabel: "LEGACY",
      detail: "Pre-lifecycle record shape",
      color: "var(--app-chip-fg)",
      background: "var(--app-chip-bg)",
      border: "var(--app-chip-border)",
    },
    unknown: {
      label: "Unknown",
      shortLabel: "UNKNOWN",
      detail: "Unclassified provenance",
      color: "var(--app-chip-fg)",
      background: "var(--app-chip-bg)",
      border: "var(--app-chip-border)",
    },
  };
  return meta[provenance];
};

const probeStateTone = (step: LifecycleProbeStep): NodeTone => {
  const state = (step.state || "").toLowerCase();
  const provenance = normalizeProvenance(step.provenance);
  if (provenance === "missing" || state === "not_reached") return "future";
  if (state === "unknown") return "paused";
  if (state === "waiting" || state === "possible") return "current";
  if (state === "rejected") return "blocked";
  if (state === "saved") return "paused";
  if (provenance === "derived") return "support";
  if (provenance === "inferred") return "paused";
  return "chosen";
};

const supportChips = (support?: Record<string, unknown>) => {
  if (!support) return [];
  return Object.entries(support)
    .map(([key, value]) => {
      if (value === null || typeof value === "undefined" || value === "") return "";
      if (Array.isArray(value)) return value.length ? `${prettyStatus(key)}: ${value.length}` : "";
      if (typeof value === "object") return Object.keys(value as Record<string, unknown>).length ? prettyStatus(key) : "";
      return `${prettyStatus(key)}: ${String(value)}`;
    })
    .filter(Boolean)
    .slice(0, 4);
};

const isDirectLifecycleStep = (step: LifecycleProbeStep) =>
  (step.source || "").toLowerCase() === "signal_lifecycle_event" &&
  (step.provenance || "").toLowerCase() === "direct";

const probeStepToNode = (step: LifecycleProbeStep, index: number): MapNode => {
  const provenance = normalizeProvenance(step.provenance);
  const meta = provenanceMeta(provenance, step.source);
  const state = step.state || "unknown";
  const gaps = step.gaps || [];
  return {
    id: step.step_id || `probe-step-${index}`,
    title: step.label || prettyStatus(step.step_id) || `Step ${index + 1}`,
    detail: step.detail || "No detail attached.",
    tone: probeStateTone(step),
    stateLabel: prettyStatus(state).toUpperCase(),
    statusBadge: meta.shortLabel,
    chips: [
      `${meta.label}: ${meta.detail}`,
      step.source ? `source: ${prettyStatus(step.source)}` : "",
      step.timestamp ? `date: ${compactDate(step.timestamp)}` : "",
      step.actor ? `actor: ${step.actor}` : "",
      gaps.length ? `gaps: ${gaps.length}` : "",
      ...supportChips(step.support),
    ].filter(Boolean),
    rationale: [
      step.timestamp ? `timestamp: ${step.timestamp}` : "",
      step.actor ? `actor: ${step.actor}` : "",
      ...gaps,
    ].filter(Boolean),
  };
};

const nodeStyle = (tone: NodeTone): CSSProperties => {
  const styles: Record<NodeTone, CSSProperties> = {
    future: {
      borderColor: "var(--app-chip-border)",
      borderStyle: "dashed",
      background: "var(--app-surface-muted-bg)",
      color: "var(--app-chip-fg)",
    },
    chosen: {
      borderColor: "var(--app-success-border)",
      borderStyle: "solid",
      background: "var(--app-success-bg)",
      color: "var(--app-success-fg)",
    },
    current: {
      borderColor: "var(--app-info-border)",
      borderStyle: "solid",
      background: "var(--app-info-bg)",
      color: "var(--app-info-fg)",
      boxShadow: "0 0 0 3px color-mix(in srgb, var(--app-info-border) 24%, transparent)",
    },
    blocked: {
      borderColor: "var(--app-danger-border)",
      borderStyle: "solid",
      background: "var(--app-danger-bg)",
      color: "var(--app-danger-fg)",
    },
    paused: {
      borderColor: "var(--app-warning-border)",
      borderStyle: "solid",
      background: "var(--app-warning-bg)",
      color: "var(--app-warning-fg)",
    },
    support: {
      borderColor: "var(--app-surface-strong-border)",
      borderStyle: "solid",
      background: "var(--app-tag-bg)",
      color: "var(--app-tag-fg)",
    },
  };
  return styles[tone];
};

const toneAccent = (tone: NodeTone) => {
  const accents: Record<NodeTone, string> = {
    future: "var(--app-chip-border)",
    chosen: "var(--app-success-border)",
    current: "var(--app-info-border)",
    blocked: "var(--app-danger-border)",
    paused: "var(--app-warning-border)",
    support: "var(--app-surface-strong-border)",
  };
  return accents[tone];
};

const toneText = (tone: NodeTone) => {
  const colors: Record<NodeTone, string> = {
    future: "var(--app-chip-fg)",
    chosen: "var(--app-success-fg)",
    current: "var(--app-info-fg)",
    blocked: "var(--app-danger-fg)",
    paused: "var(--app-warning-fg)",
    support: "var(--app-tag-fg)",
  };
  return colors[tone];
};

const stateLabel = (tone: NodeTone) => {
  const labels: Record<NodeTone, string> = {
    future: "POSSIBLE",
    chosen: "CHOSEN",
    current: "CURRENT",
    blocked: "BLOCKED",
    paused: "PAUSED",
    support: "GATE",
  };
  return labels[tone];
};

const statusBadgeStyle = (tone: NodeTone): CSSProperties => {
  const styles: Record<NodeTone, CSSProperties> = {
    future: {
      background: "var(--app-chip-bg)",
      color: "var(--app-chip-fg)",
      border: "1px solid var(--app-chip-border)",
    },
    chosen: {
      background: "var(--app-success-bg)",
      color: "var(--app-success-fg)",
      border: "1px solid var(--app-success-border)",
    },
    current: {
      background: "var(--app-info-bg)",
      color: "var(--app-info-fg)",
      border: "1px solid var(--app-info-border)",
    },
    blocked: {
      background: "var(--app-danger-bg)",
      color: "var(--app-danger-fg)",
      border: "1px solid var(--app-danger-border)",
    },
    paused: {
      background: "var(--app-warning-bg)",
      color: "var(--app-warning-fg)",
      border: "1px solid var(--app-warning-border)",
    },
    support: {
      background: "var(--app-tag-bg)",
      color: "var(--app-tag-fg)",
      border: "1px solid var(--app-surface-strong-border)",
    },
  };
  return styles[tone];
};

const provenanceLegendItems: LifecycleProvenance[] = ["direct", "derived", "inferred", "missing", "legacy"];

function ProvenanceLegend() {
  return (
    <div style={provenanceLegendStyle}>
      {provenanceLegendItems.map((provenance) => {
        const meta = provenanceMeta(provenance);
        return (
          <span
            key={provenance}
            style={{
              border: `1px solid ${meta.border}`,
              borderRadius: "999px",
              background: meta.background,
              color: meta.color,
              padding: "4px 8px",
              fontSize: "11px",
              fontWeight: 900,
              whiteSpace: "nowrap",
            }}
            title={meta.detail}
          >
            {meta.label}
          </span>
        );
      })}
    </div>
  );
}

const layerTitleStyle: CSSProperties = {
  margin: "0 0 10px",
  fontSize: "11px",
  color: "var(--app-text-subtle)",
  textTransform: "uppercase",
  fontWeight: 900,
  letterSpacing: "0",
};

const connectorStyle = (active: boolean): CSSProperties => ({
  width: "2px",
  minHeight: "14px",
  background: active ? "var(--app-surface-strong-border)" : "var(--app-surface-border)",
  margin: "0 auto",
});

const provenanceLegendStyle: CSSProperties = {
  display: "flex",
  gap: "6px",
  flexWrap: "wrap",
  marginTop: "8px",
};

function DecisionNode({ node }: { node: MapNode }) {
  const chips = node.chips || [];
  const visibleChips = chips.slice(0, 4);
  const hiddenChipCount = chips.length - visibleChips.length;
  const label = node.stateLabel || stateLabel(node.tone);
  const rationale = node.rationale || [];

  return (
    <div
      style={{
        border: "1px solid",
        borderLeft: `4px solid ${toneAccent(node.tone)}`,
        borderRadius: "8px",
        padding: "9px",
        minHeight: "82px",
        display: "flex",
        flexDirection: "column",
        gap: "6px",
        overflow: "visible",
        minWidth: 0,
        ...nodeStyle(node.tone),
      }}
    >
      {node.statusBadge ? (
        <div
          style={{
            alignSelf: "flex-start",
            borderRadius: "999px",
            padding: "4px 8px",
            fontSize: "11px",
            fontWeight: 900,
            lineHeight: 1,
            ...statusBadgeStyle(node.tone),
          }}
        >
          {node.statusBadge}
        </div>
      ) : null}
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: "6px", flexWrap: "wrap" }}>
        <div
          style={{
            fontSize: "12px",
            fontWeight: 900,
            lineHeight: 1.25,
            textTransform: "uppercase",
            minWidth: 0,
            overflowWrap: "anywhere",
          }}
        >
          {node.title}
        </div>
        <span
          style={{
            border: "1px solid var(--app-chip-border)",
            borderRadius: "999px",
            padding: "2px 5px",
            fontSize: "10px",
            fontWeight: 900,
            background: "var(--app-chip-bg)",
            color: toneText(node.tone),
            whiteSpace: "nowrap",
            maxWidth: "100%",
            overflow: "hidden",
            textOverflow: "ellipsis",
          }}
        >
          {label}
        </span>
      </div>
      <div
        style={{
          fontSize: "12px",
          lineHeight: 1.4,
          display: "-webkit-box",
          WebkitLineClamp: 3,
          WebkitBoxOrient: "vertical",
          overflow: "hidden",
          overflowWrap: "anywhere",
        }}
      >
        {node.detail}
      </div>
      {chips.length > 0 ? (
        <div style={{ display: "flex", flexWrap: "wrap", gap: "6px", marginTop: "auto" }}>
          {visibleChips.map((chip) => (
            <span
              key={chip}
              style={{
                border: "1px solid var(--app-chip-border)",
                borderRadius: "999px",
                padding: "3px 7px",
                fontSize: "11px",
                background: "var(--app-chip-bg)",
                color: "var(--app-chip-fg)",
                fontWeight: 700,
                maxWidth: "100%",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {chip}
            </span>
          ))}
          {hiddenChipCount > 0 ? (
            <span
              style={{
                border: "1px solid var(--app-chip-border)",
                borderRadius: "999px",
                padding: "3px 7px",
                fontSize: "11px",
                background: "var(--app-chip-bg)",
                color: "var(--app-chip-fg)",
                fontWeight: 700,
              }}
            >
              +{hiddenChipCount}
            </span>
          ) : null}
        </div>
      ) : null}
      {rationale.length > 0 ? (
        <details style={{ marginTop: "2px" }}>
          <summary style={{ cursor: "pointer", fontSize: "11px", fontWeight: 800 }}>Why</summary>
          <ul style={{ margin: "6px 0 0", paddingLeft: "16px", fontSize: "11px", lineHeight: 1.45 }}>
            {rationale.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </details>
      ) : null}
    </div>
  );
}

function NodeGrid({
  children,
  min = 170,
}: {
  children: React.ReactNode;
  min?: number;
}) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: `repeat(auto-fit, minmax(${min}px, 1fr))`, gap: "10px" }}>
      {children}
    </div>
  );
}

function TrajectoryStep({
  node,
  isLast = false,
  aside,
}: {
  node: MapNode;
  isLast?: boolean;
  aside?: React.ReactNode;
}) {
  const chips = node.chips || [];
  const label = node.stateLabel || stateLabel(node.tone);
  const rationale = node.rationale || [];

  return (
    <div style={{ display: "grid", gridTemplateColumns: "28px minmax(0, 1fr)", gap: "10px" }}>
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
        <div
          style={{
            width: "14px",
            height: "14px",
            borderRadius: "999px",
            border: `3px solid ${toneAccent(node.tone)}`,
            background: "var(--app-surface-bg)",
          }}
        />
        {!isLast ? (
          <div
            style={{
              width: "2px",
              flex: 1,
              minHeight: "34px",
              background: "var(--app-surface-border)",
            }}
          />
        ) : null}
      </div>
      <div
        style={{
          border: "1px solid",
          borderLeft: `4px solid ${toneAccent(node.tone)}`,
          borderRadius: "10px",
          padding: "10px 12px",
          display: "grid",
          gap: "7px",
          ...nodeStyle(node.tone),
        }}
      >
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "10px", flexWrap: "wrap" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
            {node.statusBadge ? (
              <span
                style={{
                  borderRadius: "999px",
                  padding: "4px 8px",
                  fontSize: "11px",
                  fontWeight: 900,
                  lineHeight: 1,
                  ...statusBadgeStyle(node.tone),
                }}
              >
                {node.statusBadge}
              </span>
            ) : null}
            <strong style={{ fontSize: "13px", textTransform: "uppercase" }}>{node.title}</strong>
          </div>
          <span
            style={{
              border: "1px solid var(--app-chip-border)",
              borderRadius: "999px",
              padding: "2px 7px",
              fontSize: "10px",
              fontWeight: 900,
              background: "var(--app-chip-bg)",
              color: toneText(node.tone),
            }}
          >
            {label}
          </span>
        </div>
        <div style={{ fontSize: "12px", lineHeight: 1.45 }}>{node.detail}</div>
        {chips.length > 0 ? (
          <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
            {chips.slice(0, 6).map((chip) => (
              <span
                key={chip}
                style={{
                  border: "1px solid var(--app-chip-border)",
                  borderRadius: "999px",
                  padding: "3px 7px",
                  fontSize: "11px",
                  background: "var(--app-chip-bg)",
                  color: "var(--app-chip-fg)",
                  fontWeight: 700,
                }}
              >
                {chip}
              </span>
            ))}
            {chips.length > 6 ? (
              <span
                style={{
                  border: "1px solid var(--app-chip-border)",
                  borderRadius: "999px",
                  padding: "3px 7px",
                  fontSize: "11px",
                  background: "var(--app-chip-bg)",
                  color: "var(--app-chip-fg)",
                  fontWeight: 700,
                }}
              >
                +{chips.length - 6}
              </span>
            ) : null}
          </div>
        ) : null}
        {aside}
        {rationale.length > 0 ? (
          <details>
            <summary style={{ cursor: "pointer", fontSize: "11px", fontWeight: 900 }}>Why</summary>
            <ul style={{ margin: "6px 0 0", paddingLeft: "16px", fontSize: "11px", lineHeight: 1.45 }}>
              {rationale.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </details>
        ) : null}
      </div>
    </div>
  );
}

function Layer({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div
      style={{
        marginTop: "10px",
        border: "1px solid var(--app-surface-border)",
        borderRadius: "10px",
        background: "var(--app-surface-muted-bg)",
        padding: "10px",
      }}
    >
      <h3 style={layerTitleStyle}>{title}</h3>
      {children}
    </div>
  );
}

function projectTone(candidate: ProjectCandidateSummary): NodeTone {
  const status = (candidate.reviewOutcome || candidate.status || "").toLowerCase();
  if (status === "rejected" || status === "dismissed") return "blocked";
  if (status === "watch") return "paused";
  if (status === "candidate" || status === "new" || status === "reopened") return "current";
  return status ? "chosen" : "future";
}

function projectDisplayStatus(candidate: ProjectCandidateSummary) {
  const status = (candidate.status || "").toLowerCase();
  if (status === "action_completed" || candidate.actionCompletedAt) return "action_completed";
  return candidate.reviewOutcome || candidate.status || "";
}

export default function SignalDecisionFlow({
  status,
  source,
  publishedAt,
  savedReason,
  hasInsight,
  workspaceSaved,
  modelUsed,
  generationMode,
  verification,
  decisionTrace = [],
  projectCandidates = [],
  lifecycleProbe,
  lifecycleProbeLoading = false,
  lifecycleProbeError = "",
}: SignalDecisionFlowProps) {
  const [showMap, setShowMap] = useState(false);
  const [view, setView] = useState<DecisionMapView>("trajectory");
  const normalizedStatus = normalizeStatus(status);
  const verifiedInsight = verification?.verified_insight;
  const blockedActions =
    verification?.blocked_downstream_actions || verifiedInsight?.action_policy?.blocked || [];
  const allowedActions =
    verification?.allowed_downstream_actions || verifiedInsight?.action_policy?.allowed || [];
  const verificationStatus = verification?.verification_status || verifiedInsight?.status || "";
  const claimSummary = verification?.claim_support_summary || verifiedInsight?.claims?.support_summary;
  const evidenceLevel = verification?.evidence_quality?.level || verifiedInsight?.evidence?.level || "";
  const reasonCodes = verification?.evidence_quality?.reason_codes || [];
  const limitations = verification?.limitations || [];

  const insightOccurred =
    hasInsight ||
    hasTraceEvent(decisionTrace, ["insight_generated"]) ||
    ["analyzed", "saved", "completed", "rejected"].includes(normalizedStatus);
  const verificationOccurred = Boolean(verificationStatus || evidenceLevel || Object.keys(claimSummary || {}).length > 0);
  const savedOccurred =
    normalizedStatus === "saved" || hasTraceEvent(decisionTrace, ["operator_saved_for_later"]);
  const rejectedOccurred = normalizedStatus === "rejected" || hasTraceEvent(decisionTrace, ["operator_rejected"]);
  const completedOccurred =
    normalizedStatus === "completed" ||
    Boolean(workspaceSaved) ||
    hasTraceEvent(decisionTrace, ["completed_to_workspace"]);
  const processedOccurred =
    normalizedStatus === "analyzed" || hasTraceEvent(decisionTrace, ["operator_marked_processed"]);
  const latestTrace = decisionTrace.length ? decisionTrace[decisionTrace.length - 1] : null;
  const traceStamp = latestTrace?.timestamp ? `trace: ${compactDate(latestTrace.timestamp)}` : "";
  const traceActor = latestTrace?.actor ? `actor: ${latestTrace.actor}` : "";
  const evidenceRationale = [
    verificationStatus ? `verification status: ${prettyStatus(verificationStatus)}` : "",
    evidenceLevel ? `evidence level: ${prettyStatus(evidenceLevel)}` : "",
    summarizeClaims(claimSummary) ? `claim support: ${summarizeClaims(claimSummary)}` : "",
  ].filter(Boolean);

  const signalNode: MapNode = {
    id: "signal",
    title: "Signal",
    detail: [source || "source recorded", compactDate(publishedAt) ? `published ${compactDate(publishedAt)}` : ""]
      .filter(Boolean)
      .join(" | "),
    tone: "chosen",
  };
  const insightNode: MapNode = {
    id: "insight",
    title: "Insight Generation",
    detail: insightOccurred
      ? [generationMode || "generated", modelUsed || ""].filter(Boolean).join(" | ")
      : "Future: generate or regenerate an insight.",
    tone: insightOccurred ? "chosen" : normalizedStatus === "pending" ? "current" : "future",
    chips: insightOccurred ? ["generated"] : ["Claude", "ChatGPT", "fallback possible"],
  };
  const evidenceNode: MapNode = {
    id: "evidence",
    title: "Evidence / Verification Gate",
    detail: verificationOccurred
      ? `${prettyStatus(verificationStatus || "verified")} with ${prettyStatus(evidenceLevel || "recorded")} evidence.`
      : insightOccurred
        ? "Current: evidence and claim support are not attached yet."
        : "Future: classify evidence, claims, and downstream gates.",
    tone: verificationOccurred ? (blockedActions.length ? "paused" : "support") : insightOccurred ? "current" : "future",
    stateLabel: verificationOccurred ? "VERIFIED" : stateLabel(insightOccurred ? "current" : "future"),
    chips: [
      verificationStatus ? `status: ${prettyStatus(verificationStatus)}` : "",
      evidenceLevel ? `evidence: ${prettyStatus(evidenceLevel)}` : "",
      summarizeClaims(claimSummary) ? `claims: ${summarizeClaims(claimSummary)}` : "",
      reasonCodes.length ? `reasons: ${compactList(reasonCodes)}` : "",
      limitations.length ? `limits: ${compactList(limitations)}` : "",
    ].filter(Boolean),
    rationale: verificationOccurred ? evidenceRationale : [],
  };

  const signalDecisionNodes: MapNode[] = [
    {
      id: "reject",
      title: "Reject",
      detail: rejectedOccurred ? "Chosen path." : "Possible branch.",
      tone: rejectedOccurred ? "blocked" : "future",
      rationale: rejectedOccurred ? [traceStamp, traceActor].filter(Boolean) : [],
    },
    {
      id: "save",
      title: "Save Later",
      detail: savedOccurred ? savedReason || "Paused for future context." : "Possible branch.",
      tone: savedOccurred ? "paused" : "future",
      chips: savedReason ? [`reason: ${savedReason}`] : [],
      rationale: savedOccurred ? [savedReason ? `reason: ${savedReason}` : "", traceStamp, traceActor].filter(Boolean) : [],
    },
    {
      id: "processed",
      title: "Mark Processed",
      detail: processedOccurred ? "Reviewed but not durable memory." : "Possible branch.",
      tone: processedOccurred && !completedOccurred ? "current" : processedOccurred ? "chosen" : "future",
      rationale: processedOccurred ? [traceStamp, traceActor].filter(Boolean) : [],
    },
    {
      id: "workspace",
      title: "Complete to Workspace",
      detail: completedOccurred ? "Durable Workspace memory exists." : "Possible branch.",
      tone: completedOccurred ? "chosen" : "future",
      rationale: completedOccurred ? [...evidenceRationale, traceStamp, traceActor].filter(Boolean) : [],
    },
  ];

  const constraintNodes: MapNode[] = [
    {
      id: "allowed",
      title: "Allowed Downstream",
      detail: allowedActions.length ? compactList(allowedActions) : "No explicit allowed actions attached.",
      tone: allowedActions.length ? "support" : "future",
      stateLabel: allowedActions.length ? "ALLOWED" : "NONE",
      rationale: allowedActions.map((action) => `allowed: ${prettyStatus(action)}`),
    },
    {
      id: "blocked",
      title: "Blocked Downstream",
      detail: blockedActions.length ? compactList(blockedActions) : "No explicit blocked actions attached.",
      tone: blockedActions.length ? "blocked" : "future",
      stateLabel: blockedActions.length ? "BLOCKED" : "NONE",
      rationale: blockedActions.map((action) => `blocked: ${prettyStatus(action)}`),
    },
  ];
  const overrideNode: MapNode = {
    id: "override",
    title: "Manual Override",
    detail: "Exceptional path with reviewer note and expected outcome.",
    tone: "future",
    stateLabel: "AUDITED ONLY",
    rationale: ["Override should write an audit record.", "Ordinary confirm/action paths must not bypass gates."],
  };

  const projectNodes: MapNode[] =
    projectCandidates.length > 0
      ? projectCandidates.map((candidate, index) => {
          const statusText = projectDisplayStatus(candidate) || "candidate";
          return {
            id: `project-${candidate.projectId || index}`,
            title: candidate.projectName || candidate.projectId || "Project",
            detail: `Project path: ${prettyStatus(statusText)}.`,
            tone: projectTone(candidate),
            statusBadge: prettyStatus(statusText).toUpperCase(),
            chips: [
              candidate.status ? `status: ${prettyStatus(candidate.status)}` : "",
              candidate.reviewOutcome ? `review: ${prettyStatus(candidate.reviewOutcome)}` : "",
              candidate.watchStatus ? `watch: ${prettyStatus(candidate.watchStatus)}` : "",
              candidate.actionCompletedAt ? "action completed" : "",
            ].filter(Boolean),
            rationale: [
              candidate.projectId ? `project id: ${candidate.projectId}` : "",
              candidate.reviewOutcome ? `review outcome: ${prettyStatus(candidate.reviewOutcome)}` : "",
              candidate.status ? `candidate status: ${prettyStatus(candidate.status)}` : "",
              candidate.actionCompletedAt ? `action completed at: ${candidate.actionCompletedAt}` : "",
            ].filter(Boolean),
          };
        })
      : [
          {
            id: "project-future",
            title: "Project Fan-out",
            detail: "Future: one branch per relevant project.",
            tone: blockedActions.includes("project_takeaway_candidate")
              ? "blocked"
              : completedOccurred
                ? "current"
                : "future",
            statusBadge: blockedActions.includes("project_takeaway_candidate")
              ? "BLOCKED"
              : completedOccurred
                ? "READY"
                : "POSSIBLE",
            chips: blockedActions.includes("project_takeaway_candidate") ? ["blocked by gate"] : [],
          },
        ];

  const reviewBaseNodes: MapNode[] = [
    { id: "confirmed", title: "Confirmed", detail: "Review outcome: accepted as project takeaway.", tone: "future" },
    { id: "watch", title: "Watch", detail: "Track and revisit later.", tone: "future" },
    { id: "action", title: "Action", detail: "Create low-risk action.", tone: "future" },
    { id: "rejected", title: "Rejected", detail: "Not useful for this project.", tone: "future" },
    { id: "dismissed", title: "Dismissed", detail: "Close without learning/action.", tone: "future" },
    { id: "action-completed", title: "Action Completed", detail: "Action lifecycle state.", tone: "future" },
  ];

  const reviewNodes: MapNode[] = reviewBaseNodes.map((node) => {
    const active = projectCandidates.some((candidate) => {
      const statusText = (candidate.reviewOutcome || candidate.status || "").toLowerCase();
      if (node.id === "action-completed") return statusText === "action_completed" || Boolean(candidate.actionCompletedAt);
      return statusText === node.id;
    });
    return active
      ? {
          ...node,
          tone: node.id === "rejected" || node.id === "dismissed" ? "blocked" : "chosen",
          statusBadge: node.title.toUpperCase(),
        }
      : node;
  });

  const hasProjectReview = projectCandidates.some((candidate) => {
    const statusText = (candidate.reviewOutcome || candidate.status || "").toLowerCase();
    return ["confirmed", "watch", "action", "rejected", "dismissed", "action_completed"].includes(statusText);
  });
  const hasCompletedAction = projectCandidates.some((candidate) => Boolean(candidate.actionCompletedAt));
  const auditNodes: MapNode[] = [
    {
      id: "review-record",
      title: "Audit Context",
      detail: hasProjectReview
        ? "Review outcomes are visible for audit and future calibration."
        : "Future: review outcomes can provide audit context.",
      tone: hasProjectReview ? "support" : projectCandidates.length > 0 ? "current" : "future",
      stateLabel: hasProjectReview ? "CONTEXT" : projectCandidates.length > 0 ? "CURRENT" : "POSSIBLE",
      rationale: hasProjectReview
        ? ["Project review outcomes exist.", "This does not imply a separate audit object was created."]
        : [],
    },
    {
      id: "calibration",
      title: "Calibration Event",
      detail: hasProjectReview
        ? "Chosen: outcome can feed calibration and judgment quality tracking."
        : "Future: outcome can be used for calibration once reviewed.",
      tone: hasProjectReview ? "support" : "future",
      rationale: hasProjectReview ? ["review outcome available for calibration"] : [],
    },
    {
      id: "trajectory",
      title: "Trajectory Memory",
      detail: hasCompletedAction
        ? "Chosen: completed action can update project trajectory memory."
        : "Future: durable memory can be updated after confirmed/action paths.",
      tone: hasCompletedAction ? "chosen" : "future",
      rationale: hasCompletedAction ? ["action completion timestamp exists"] : [],
    },
  ];

  const selectedSignalDecisionNode =
    signalDecisionNodes.find((node) => ["chosen", "current", "blocked", "paused"].includes(node.tone)) || {
      id: "decision-current",
      title: "Signal Decision",
      detail: insightOccurred ? "Current: waiting for an operator decision." : "Future: choose the signal-level path.",
      tone: insightOccurred ? "current" : "future",
      stateLabel: insightOccurred ? "CURRENT" : "POSSIBLE",
    };
  const notTakenSignalDecisionCount = signalDecisionNodes.filter((node) => node.id !== selectedSignalDecisionNode.id).length;
  const projectPathSummary =
    projectCandidates.length > 0
      ? projectCandidates
          .slice(0, 3)
          .map((candidate) => {
            const name = candidate.projectName || candidate.projectId || "Project";
            return `${name}: ${prettyStatus(candidate.status || "candidate")}`;
          })
          .join(" | ")
      : completedOccurred
        ? "No project candidates are attached yet."
        : "Project fan-out has not been reached.";
  const projectTrajectoryNode: MapNode = {
    id: "trajectory-projects",
    title: "Project Fan-out",
    detail:
      projectCandidates.length > 0
        ? `${projectCandidates.length} project candidate${projectCandidates.length === 1 ? "" : "s"} attached.`
        : projectPathSummary,
    tone: projectCandidates.length > 0 ? "chosen" : completedOccurred ? "current" : "future",
    stateLabel: projectCandidates.length > 0 ? "FAN-OUT" : completedOccurred ? "CURRENT" : "POSSIBLE",
    chips: projectCandidates.map((candidate) => {
      const name = candidate.projectName || candidate.projectId || "Project";
      return `${name}: ${prettyStatus(candidate.status || "candidate")}`;
    }),
    rationale: projectCandidates
      .map((candidate) => {
        const name = candidate.projectName || candidate.projectId || "Project";
        return `${name} candidate status: ${prettyStatus(candidate.status || "candidate")}`;
      })
      .filter(Boolean),
  };
  const reviewTrajectoryOutcomes = projectCandidates
    .map((candidate) => projectDisplayStatus(candidate))
    .filter(Boolean);
  const reviewOutcomeDetails = projectCandidates
    .map((candidate) => {
      const outcome = projectDisplayStatus(candidate);
      if (!outcome) return "";
      const name = candidate.projectName || candidate.projectId || "Project";
      return `${name}: ${prettyStatus(outcome)}`;
    })
    .filter(Boolean);
  const reviewTrajectoryNode: MapNode = {
    id: "trajectory-review",
    title: "Project Outcomes",
    detail:
      reviewOutcomeDetails.length > 0
        ? `Project outcomes: ${compactList(reviewOutcomeDetails)}.`
        : projectCandidates.length > 0
          ? "Current: project candidates are waiting for outcomes."
          : "Future: project outcomes happen after fan-out.",
    tone: reviewTrajectoryOutcomes.length > 0 ? "chosen" : projectCandidates.length > 0 ? "current" : "future",
    stateLabel: reviewTrajectoryOutcomes.length > 0 ? "OUTCOMES" : projectCandidates.length > 0 ? "CURRENT" : "POSSIBLE",
    chips: reviewOutcomeDetails,
    rationale: reviewOutcomeDetails.map((outcome) => `project outcome: ${outcome}`),
  };
  const legacyTrajectoryNodes = [
    signalNode,
    insightNode,
    evidenceNode,
    selectedSignalDecisionNode,
    completedOccurred || projectCandidates.length > 0 ? projectTrajectoryNode : null,
    projectCandidates.length > 0 ? reviewTrajectoryNode : null,
    hasProjectReview || hasCompletedAction ? auditNodes.find((node) => node.id === "review-record") || null : null,
  ].filter(Boolean) as MapNode[];
  const probeTrajectoryNodes = (lifecycleProbe?.steps || []).map(probeStepToNode);
  const hasProbeTrajectory = probeTrajectoryNodes.length > 0;
  const directLifecycleSteps = (lifecycleProbe?.steps || []).filter(isDirectLifecycleStep);
  const directLifecycleStepLabels = directLifecycleSteps
    .map((step) => step.label || prettyStatus(step.step_id))
    .filter(Boolean);
  const trajectoryNodes = hasProbeTrajectory ? probeTrajectoryNodes : legacyTrajectoryNodes;
  const probeGapReport = lifecycleProbe?.gap_report;
  const probeGapCount =
    (probeGapReport?.service_outputs_not_persisted || []).length +
    (probeGapReport?.architecture_gaps || []).length;

  const chosenProjects = projectCandidates.length;
  const selectedSummary = completedOccurred
    ? chosenProjects > 0
      ? `Workspace -> ${chosenProjects} project path${chosenProjects === 1 ? "" : "s"}`
      : "Workspace, waiting for project fan-out"
    : rejectedOccurred
      ? "Rejected at signal layer"
      : savedOccurred
        ? "Saved for later at signal layer"
        : processedOccurred
          ? "Processed at signal layer"
          : insightOccurred
            ? "Waiting at signal decision"
            : "Waiting at insight generation";

  return (
    <section
      style={{
        marginTop: "18px",
        border: "1px solid var(--app-surface-border)",
        borderRadius: "12px",
        background: "var(--app-surface-bg)",
        color: "var(--app-text-strong)",
        padding: "16px",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", gap: "12px", flexWrap: "wrap" }}>
        <div>
          <h2 style={{ margin: 0, fontSize: "16px", color: "var(--app-text-strong)" }}>Signal Decision Map</h2>
          <p style={{ margin: "6px 0 0", fontSize: "13px", color: "var(--app-text-muted)", lineHeight: 1.5 }}>
            Current path: {selectedSummary}. The map separates signal actions from project review fan-out.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setShowMap((current) => !current)}
          style={{
            alignSelf: "flex-start",
            border: showMap ? "1px solid var(--app-primary-action-border)" : "1px solid var(--app-secondary-action-border)",
            borderRadius: "8px",
            background: showMap ? "var(--app-primary-action-bg)" : "var(--app-secondary-action-bg)",
            color: showMap ? "var(--app-primary-action-fg)" : "var(--app-secondary-action-fg)",
            padding: "8px 12px",
            fontSize: "13px",
            fontWeight: 800,
            cursor: "pointer",
          }}
        >
          {showMap ? "Hide Decision Map" : "Show Decision Map"}
        </button>
      </div>

      {showMap ? (
        <div style={{ marginTop: "14px", paddingBottom: "2px" }}>
          <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", marginBottom: "12px" }}>
            {(["trajectory", "schema"] as DecisionMapView[]).map((mode) => (
              <button
                key={mode}
                type="button"
                onClick={() => setView(mode)}
                style={{
                  border: view === mode ? "1px solid var(--app-primary-action-border)" : "1px solid var(--app-secondary-action-border)",
                  borderRadius: "999px",
                  background: view === mode ? "var(--app-primary-action-bg)" : "var(--app-secondary-action-bg)",
                  color: view === mode ? "var(--app-primary-action-fg)" : "var(--app-secondary-action-fg)",
                  padding: "7px 12px",
                  fontSize: "13px",
                  fontWeight: 900,
                  cursor: "pointer",
                }}
              >
                {mode === "trajectory" ? "Trajectory View" : "Schema Map"}
              </button>
            ))}
          </div>

          {view === "trajectory" ? (
            <div style={{ display: "grid", gap: "0", maxWidth: "880px" }}>
              <div
                style={{
                  marginBottom: "12px",
                  border: hasProbeTrajectory ? "1px solid var(--app-info-border)" : "1px solid var(--app-warning-border)",
                  borderRadius: "8px",
                  background: hasProbeTrajectory ? "var(--app-info-bg)" : "var(--app-warning-bg)",
                  color: hasProbeTrajectory ? "var(--app-info-fg)" : "var(--app-warning-fg)",
                  padding: "10px 12px",
                  fontSize: "12px",
                  lineHeight: 1.5,
                }}
              >
                {hasProbeTrajectory ? (
                  <>
                    Probe adapter: {lifecycleProbe?.adapter || "unknown"} | Contract:{" "}
                    {lifecycleProbe?.contract_version || "unknown"} | Authoritative:{" "}
                    {lifecycleProbe?.authoritative ? "yes" : "no"} | Direct event steps:{" "}
                    {directLifecycleSteps.length} | Gap count: {probeGapCount}
                    {directLifecycleStepLabels.length ? (
                      <div style={{ marginTop: "6px", color: "var(--app-success-fg)", fontWeight: 800 }}>
                        Direct event-backed step{directLifecycleStepLabels.length === 1 ? "" : "s"}:{" "}
                        {directLifecycleStepLabels.join(", ")}
                      </div>
                    ) : null}
                    <div style={{ marginTop: "4px", color: "inherit", opacity: 0.86 }}>
                      Observed, inferred, derived, and missing steps remain separate from direct lifecycle evidence.
                    </div>
                    <ProvenanceLegend />
                  </>
                ) : lifecycleProbeLoading ? (
                  "Loading lifecycle probe. Showing the current Signal Detail fallback trajectory until the probe returns."
                ) : lifecycleProbeError ? (
                  `Lifecycle probe unavailable: ${lifecycleProbeError}. Showing the current Signal Detail fallback trajectory.`
                ) : (
                  "Lifecycle probe is not loaded yet. Showing the current Signal Detail fallback trajectory."
                )}
              </div>
              {trajectoryNodes.map((node, index) => (
                <TrajectoryStep
                  key={node.id}
                  node={node}
                  isLast={index === trajectoryNodes.length - 1}
                  aside={
                    node.id === selectedSignalDecisionNode.id && notTakenSignalDecisionCount > 0 ? (
                      <details>
                        <summary style={{ cursor: "pointer", fontSize: "11px", fontWeight: 900 }}>
                          +{notTakenSignalDecisionCount} signal-level paths not taken
                        </summary>
                        <div style={{ marginTop: "8px" }}>
                          <NodeGrid min={135}>
                            {signalDecisionNodes
                              .filter((branch) => branch.id !== selectedSignalDecisionNode.id)
                              .map((branch) => (
                                <DecisionNode key={branch.id} node={branch} />
                              ))}
                          </NodeGrid>
                        </div>
                      </details>
                    ) : node.id === "trajectory-projects" && projectCandidates.length > 3 ? (
                      <details>
                        <summary style={{ cursor: "pointer", fontSize: "11px", fontWeight: 900 }}>
                          Show all project paths
                        </summary>
                        <div style={{ marginTop: "8px" }}>
                          <NodeGrid min={145}>
                            {projectNodes.map((projectNode) => (
                              <DecisionNode key={projectNode.id} node={projectNode} />
                            ))}
                          </NodeGrid>
                        </div>
                      </details>
                    ) : null
                  }
                />
              ))}
              {hasProbeTrajectory && probeGapReport ? (
                <details style={{ marginTop: "14px" }}>
                  <summary style={{ cursor: "pointer", color: "var(--app-text-strong)", fontSize: "13px", fontWeight: 900 }}>
                    Probe Gap Report
                  </summary>
                  <div style={{ marginTop: "10px", display: "grid", gap: "8px", fontSize: "12px", color: "var(--app-text-muted)" }}>
                    <div>
                      <strong>Direct fields:</strong>{" "}
                      {(probeGapReport.direct_fields || []).length
                        ? (probeGapReport.direct_fields || []).join(", ")
                        : "None recorded"}
                    </div>
                    <div>
                      <strong>Service outputs not persisted:</strong>{" "}
                      {(probeGapReport.service_outputs_not_persisted || []).length
                        ? (probeGapReport.service_outputs_not_persisted || []).join("; ")
                        : "None recorded"}
                    </div>
                    <div>
                      <strong>Architecture gaps:</strong>{" "}
                      {(probeGapReport.architecture_gaps || []).length
                        ? (probeGapReport.architecture_gaps || []).join("; ")
                        : "None recorded"}
                    </div>
                  </div>
                </details>
              ) : null}
            </div>
          ) : (
            <div style={{ display: "grid", gap: "8px", maxWidth: "100%" }}>
            <Layer title="Input">
              <NodeGrid min={220}>
                <DecisionNode node={signalNode} />
              </NodeGrid>
            </Layer>
            <div style={connectorStyle(insightOccurred)} />
            <Layer title="Insight Generation">
              <NodeGrid min={220}>
                <DecisionNode node={insightNode} />
              </NodeGrid>
            </Layer>
            <div style={connectorStyle(verificationOccurred)} />
            <Layer title="Evidence Verification">
              <NodeGrid min={240}>
                <DecisionNode node={evidenceNode} />
              </NodeGrid>
            </Layer>
            <div style={connectorStyle(verificationOccurred)} />
            <Layer title="Evidence-Based Constraints">
              <NodeGrid min={190}>
                {constraintNodes.map((node) => (
                  <DecisionNode key={node.id} node={node} />
                ))}
              </NodeGrid>
            </Layer>
            <div style={connectorStyle(false)} />
            <Layer title="Override">
              <NodeGrid min={220}>
                <DecisionNode node={overrideNode} />
              </NodeGrid>
            </Layer>
            <div style={connectorStyle(insightOccurred)} />
            <Layer title="Signal-Level Decision">
              <NodeGrid min={145}>
                {signalDecisionNodes.map((node) => (
                  <DecisionNode key={node.id} node={node} />
                ))}
              </NodeGrid>
            </Layer>
            <div style={connectorStyle(completedOccurred)} />
            <Layer title="Project Candidate Fan-out">
              <NodeGrid min={145}>
                {projectNodes.map((node) => (
                  <DecisionNode key={node.id} node={node} />
                ))}
              </NodeGrid>
            </Layer>
            <div style={connectorStyle(projectCandidates.length > 0)} />
            <Layer title="Project Review Outcomes">
              <NodeGrid min={150}>
                {reviewNodes.map((node) => (
                  <DecisionNode key={node.id} node={node} />
                ))}
              </NodeGrid>
            </Layer>
            <div style={connectorStyle(hasProjectReview)} />
            <Layer title="Audit And Memory Trail">
              <NodeGrid min={170}>
                {auditNodes.map((node) => (
                  <DecisionNode key={node.id} node={node} />
                ))}
              </NodeGrid>
            </Layer>
            </div>
          )}

          {decisionTrace.length > 0 ? (
            <details style={{ marginTop: "14px" }}>
              <summary style={{ cursor: "pointer", color: "var(--app-text-strong)", fontSize: "13px", fontWeight: 800 }}>
                Decision Trace ({decisionTrace.length})
              </summary>
              <div style={{ marginTop: "10px", display: "grid", gap: "8px" }}>
                {decisionTrace
                  .slice()
                  .reverse()
                  .slice(0, 6)
                  .map((event, index) => (
                    <div
                      key={`${event.event_type || "event"}-${event.timestamp || index}`}
                      style={{
                        border: "1px solid var(--app-surface-border)",
                        borderRadius: "8px",
                        padding: "10px",
                        fontSize: "12px",
                        color: "var(--app-text-muted)",
                        background: "var(--app-surface-muted-bg)",
                        lineHeight: 1.5,
                      }}
                    >
                      <strong>{(event.event_type || "event").replaceAll("_", " ")}</strong>
                      {event.status_before || event.status_after ? (
                        <span>
                          {" "}
                          {event.status_before || "unknown"}
                          {" -> "}
                          {event.status_after || "unknown"}
                        </span>
                      ) : null}
                      {event.timestamp ? <span> at {event.timestamp}</span> : null}
                      {event.support?.saved_reason ? <div>Reason: {event.support.saved_reason}</div> : null}
                      {event.support?.verification_status ? <div>Verification: {event.support.verification_status}</div> : null}
                    </div>
                  ))}
              </div>
            </details>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
