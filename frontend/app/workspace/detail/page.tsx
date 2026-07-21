"use client";

import Image from "next/image";
import Link from "next/link";
import { Suspense, type ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import AppContainer from "@/components/AppContainer";
import VerificationGateNote from "@/components/VerificationGateNote";
import { apiUrl } from "@/lib/api";
import { adminFetch } from "@/lib/adminAuth";
import type { VerificationGateMetadata } from "@/lib/verificationGateNote";

type WorkspaceItem = {
  file_name: string;
  saved_at?: string;
  source_type?: string;
  content_type?: string;
  topic?: string;
  signal_id?: string;
  manual_session_id?: string;
  is_manual_source?: boolean;
  upload_reason?: string;
  intended_use?: string;
  cognitive_layer?: string;
  signal_title?: string;
  selected_model?: string;
  user_input?: string;
  ai_response?: string;
  final_reflection?: string;
  signal_summary?: string;
  why_it_matters?: string;
  relevance_to_projects?: string | Record<string, unknown>;
  relevance_to_career?: string;
  synthesized_insight?: string;
  verification_metadata?: Record<string, unknown> | null;
  reflection_context?: string;
  image_url?: string;
  image_file_name?: string;
  image_metadata_url?: string;
  image_metadata_file_name?: string;
  visual_style?: string;
  visual_direction?: string;
  chat_messages?: Array<{
    role?: string;
    content?: string;
  }>;
  chat_message_count?: number;
};

function normalizeText(value?: unknown): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);

  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function parseJsonStringObject(value?: unknown): Record<string, string> | null {
  if (value === null || value === undefined) return null;

  if (typeof value === "object" && !Array.isArray(value)) {
    const result: Record<string, string> = {};

    for (const [key, val] of Object.entries(value)) {
      const normalized = normalizeText(val).trim();
      if (normalized) result[key] = normalized;
    }

    return Object.keys(result).length > 0 ? result : null;
  }

  const normalizedValue = normalizeText(value).trim();
  if (!normalizedValue) return null;

  try {
    const parsed = JSON.parse(normalizedValue);

    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      const result: Record<string, string> = {};

      for (const [key, val] of Object.entries(parsed)) {
        result[key] = normalizeText(val).trim();
      }

      return Object.keys(result).length > 0 ? result : null;
    }
  } catch {
    return null;
  }

  return null;
}

function formatLabel(value?: unknown): string {
  const normalized = normalizeText(value).trim();
  if (!normalized) return "";

  return normalized
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function formatStringList(value?: unknown): string {
  if (Array.isArray(value)) {
    return value.map((item) => normalizeText(item).trim()).filter(Boolean).join(", ");
  }

  return normalizeText(value).trim();
}

function parseStringList(value?: unknown): string[] {
  if (Array.isArray(value)) {
    return value.map((item) => normalizeText(item).trim()).filter(Boolean);
  }

  return normalizeText(value)
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function buildVerificationGateMetadata(metadata: Record<string, unknown>): VerificationGateMetadata {
  return {
    verification_status: normalizeText(metadata.verification_status).trim(),
    verification_required: Boolean(metadata.verification_required),
    knowledge_convergence: Boolean(metadata.knowledge_convergence),
    manual_project_takeaway_override: Boolean(metadata.manual_project_takeaway_override),
    allowed_downstream_actions: parseStringList(metadata.allowed_downstream_actions),
    blocked_downstream_actions: parseStringList(metadata.blocked_downstream_actions),
    claim_support_summary: parseJsonStringObject(metadata.claim_support_summary) || {},
  };
}

function buildActionPolicyLine(metadata: Record<string, unknown>) {
  const allowed = formatStringList(metadata.allowed_downstream_actions);
  const blocked = formatStringList(metadata.blocked_downstream_actions);
  if (blocked) return `Blocked downstream actions: ${blocked}. Treat this record as review/watch context before action.`;
  if (allowed) return `Allowed downstream actions: ${allowed}. Keep the original evidence and claim support visible when acting on it.`;
  return "No downstream action policy was recorded for this workspace item.";
}

function buildActionEligibilityRows(metadata: Record<string, unknown>) {
  const hasActionEligibility =
    metadata.action_eligibility && typeof metadata.action_eligibility === "object" && !Array.isArray(metadata.action_eligibility);
  const eligibility =
    hasActionEligibility
      ? metadata.action_eligibility as Record<string, unknown>
      : {};

  return ([
    ["Project Takeaway", eligibility.project_takeaway_candidate],
    ["Watch", eligibility.watch_only],
    ["Low-risk Action", eligibility.low_risk_action_candidate],
  ] as Array<[string, unknown]>).map(([label, value]) => {
    const decision = value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
    const allowed = decision.allowed;
    const reason = normalizeText(decision.reason).trim();
    return {
      label,
      value: typeof allowed === "boolean" ? (allowed ? "Allowed" : "Blocked") : "Not recorded",
      reason,
      blocked: allowed === false,
    };
  }).filter((row) => hasActionEligibility || row.value !== "Not recorded" || row.reason);
}

function buildKnowledgeQualityRows(metadata: Record<string, unknown>) {
  const quality = metadata.quality && typeof metadata.quality === "object" && !Array.isArray(metadata.quality)
    ? metadata.quality as Record<string, unknown>
    : {};
  const evidence = metadata.evidence_profile && typeof metadata.evidence_profile === "object" && !Array.isArray(metadata.evidence_profile)
    ? metadata.evidence_profile as Record<string, unknown>
    : {};

  return [
    ["Knowledge Quality", quality.score !== undefined ? `${normalizeText(quality.score)}/100` : evidence.quality_score !== undefined ? `${normalizeText(evidence.quality_score)}/100` : ""],
    ["Quality Label", normalizeText(quality.label || evidence.quality_label).trim()],
    ["Quality Reason", normalizeText(quality.reason || evidence.quality_reason).trim()],
  ].filter(([, value]) => value);
}

function ManualSourceSummary({ item }: { item: WorkspaceItem }) {
  const metadata = item.verification_metadata && typeof item.verification_metadata === "object" ? item.verification_metadata : {};
  const rows = ([
    ["Manual Session", item.manual_session_id || metadata.manual_session_id],
    ["Upload Reason", item.upload_reason || metadata.upload_reason],
    ["Intended Use", item.intended_use || metadata.intended_use],
    ["Cognitive Layer", formatLabel(item.cognitive_layer || metadata.cognitive_layer)],
  ] as Array<[string, unknown]>).filter(([, value]) => normalizeText(value).trim());

  const isManual = item.is_manual_source || item.source_type === "manual_upload" || Boolean(rows.length);
  if (!isManual) return null;

  return (
    <ContentSection title="Manual Source Context">
      <div style={summaryGridStyle}>
        {rows.map(([label, value]) => (
          <div key={label} style={summaryTileStyle}>
            <div style={sectionEyebrowStyle}>{label}</div>
            <div style={summaryValueStyle}>{normalizeText(value)}</div>
          </div>
        ))}
      </div>
    </ContentSection>
  );
}

function VerificationSummary({ metadata }: { metadata?: Record<string, unknown> | null }) {
  if (!metadata || typeof metadata !== "object") return null;

  const rows = [
    ["Verification", formatLabel(metadata.verification_status)],
    ["Review Priority", formatLabel(metadata.review_priority)],
    ["Confidence", formatLabel(metadata.confidence_label)],
    [
      "Confidence Score",
      typeof metadata.confidence_score === "number" ? String(metadata.confidence_score) : "",
    ],
    ["Allowed Actions", formatStringList(metadata.allowed_downstream_actions)],
    ["Blocked Actions", formatStringList(metadata.blocked_downstream_actions)],
    ["Downgrade Reason", normalizeText(metadata.downgrade_reason).trim()],
    ...buildKnowledgeQualityRows(metadata),
  ].filter(([, value]) => value);

  const supportSummary = parseJsonStringObject(metadata.claim_support_summary);
  const gateMetadata = buildVerificationGateMetadata(metadata);
  const actionEligibilityRows = buildActionEligibilityRows(metadata);

  if (rows.length === 0 && !supportSummary) return null;

  return (
    <ContentSection title="Verification Summary">
      <div style={summaryGridStyle}>
        {rows.map(([label, value]) => (
          <div key={label} style={summaryTileStyle}>
            <div style={sectionEyebrowStyle}>{label}</div>
            <div style={summaryValueStyle}>{value}</div>
          </div>
        ))}
      </div>
      {supportSummary ? (
        <div style={{ marginTop: "12px" }}>
          <div style={sectionEyebrowStyle}>Claim Support</div>
          <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
            {Object.entries(supportSummary).map(([key, value]) => (
              <span key={key} style={neutralPillStyle}>
                {formatLabel(key)}: {value}
              </span>
            ))}
          </div>
        </div>
      ) : null}
      <VerificationGateNote verification={gateMetadata} style={{ marginTop: "12px" }} />
      <div style={actionPolicyLineStyle}>{buildActionPolicyLine(metadata)}</div>
      <div style={actionEligibilityTitleStyle}>Action Eligibility</div>
      {actionEligibilityRows.length ? (
        <div style={actionEligibilityGridStyle}>
          {actionEligibilityRows.map((row) => (
            <div key={row.label} style={row.blocked ? actionEligibilityBlockedStyle : actionEligibilityTileStyle}>
              <div style={sectionEyebrowStyle}>{row.label}</div>
              <div style={summaryValueStyle}>{row.value}</div>
              {row.reason ? <div style={actionEligibilityReasonStyle}>{row.reason}</div> : null}
            </div>
          ))}
        </div>
      ) : null}
    </ContentSection>
  );
}

function TextBlock({ value }: { value?: unknown }) {
  const normalizedValue = normalizeText(value).trim();
  if (!normalizedValue) return null;

  return <div style={textBlockStyle}>{normalizedValue}</div>;
}

function HighlightBlock({ value }: { value?: unknown }) {
  const normalizedValue = normalizeText(value).trim();
  if (!normalizedValue) return null;

  return <div style={highlightBlockStyle}>{normalizedValue}</div>;
}

function ProjectMap({ value }: { value?: unknown }) {
  const parsed = parseJsonStringObject(value);

  if (!parsed) {
    return <HighlightBlock value={value} />;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
      {Object.entries(parsed).map(([project, takeaway]) => (
        <div key={project} style={highlightBlockStyle}>
          <div style={sectionEyebrowStyle}>{project}</div>
          <div style={textBlockStyle}>{takeaway}</div>
        </div>
      ))}
    </div>
  );
}

function ContentSection({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  if (!children) return null;

  return (
    <section style={{ marginTop: "18px" }}>
      <h2 style={sectionTitleStyle}>{title}</h2>
      {children}
    </section>
  );
}

function WorkspaceDetailContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const fileName = searchParams.get("file_name") || "";

  const [item, setItem] = useState<WorkspaceItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    if (!fileName) return;

    let cancelled = false;
    const cacheKey = `workspace-detail:${fileName}`;
    const cachedValue = window.sessionStorage.getItem(cacheKey);
    if (cachedValue) {
      try {
        const cachedItem = JSON.parse(cachedValue) as WorkspaceItem;
        window.queueMicrotask(() => {
          if (cancelled) return;
          setItem(cachedItem);
          setLoading(false);
          setRefreshing(true);
        });
      } catch {
        window.sessionStorage.removeItem(cacheKey);
      }
    } else {
      window.queueMicrotask(() => {
        if (cancelled) return;
        setLoading(true);
        setRefreshing(false);
      });
    }

    adminFetch(apiUrl(`/workspace_history/${encodeURIComponent(fileName)}`), {
      cache: "no-store",
    })
      .then(async (res) => {
        const data = (await res.json()) as { item?: WorkspaceItem | null; message?: string };
        if (cancelled) return;

        if (!res.ok) {
          setErrorMessage(data.message || `Failed to load workspace record: ${res.status}`);
          setItem(null);
          return;
        }

        setItem(data.item || null);
        if (data.item) {
          window.sessionStorage.setItem(cacheKey, JSON.stringify(data.item));
        }
        setErrorMessage(data.item ? "" : data.message || "Workspace record not found.");
      })
      .catch((error) => {
        if (cancelled) return;
        console.error("Failed to load workspace item:", error);
        setErrorMessage("Failed to load workspace record.");
        setItem(null);
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
          setRefreshing(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [fileName]);

  const metadata = useMemo(
    () =>
      [
        item?.saved_at ? `Saved: ${item.saved_at}` : "",
        item?.source_type ? `Source: ${item.source_type}` : "",
        item?.content_type ? `Content: ${item.content_type}` : "",
        item?.selected_model ? `Model: ${item.selected_model}` : "",
      ].filter(Boolean),
    [item],
  );

  const handleDelete = async () => {
    const confirmed = window.confirm("Delete this workspace record?");
    if (!confirmed) return;

    try {
      const res = await adminFetch(apiUrl(`/workspace_history/${encodeURIComponent(fileName)}`), {
        method: "DELETE",
      });
      const data = (await res.json()) as { message?: string };

      if (res.ok && data.message?.includes("successfully")) {
        router.push("/workspace");
        return;
      }

      window.alert(data.message || "Failed to delete workspace record.");
    } catch (error) {
      console.error("Delete workspace item failed:", error);
      window.alert("Failed to delete workspace record.");
    }
  };

  if (!fileName) {
    return (
      <AppContainer style={{ paddingTop: "24px" }}>
        <div style={headerPanelStyle}>
          <div>
            <div style={eyebrowStyle}>Workspace Record</div>
            <h1 style={pageTitleStyle}>Record not found</h1>
            <p style={descriptionStyle}>Workspace record file name is missing.</p>
          </div>
          <Link href="/workspace" style={primaryButtonStyle}>
            Back to Workspace
          </Link>
        </div>
      </AppContainer>
    );
  }

  if (loading) {
    return (
      <AppContainer style={{ paddingTop: "24px" }}>
        <div style={headerPanelStyle}>
          <div>
            <div style={eyebrowStyle}>Workspace Record</div>
            <h1 style={pageTitleStyle}>Opening workspace record</h1>
            <p style={descriptionStyle}>Loading the saved artifact and verification context for this record.</p>
          </div>
          <Link href="/workspace" style={primaryButtonStyle}>
            Back to Workspace
          </Link>
        </div>
        <div style={stateCardStyle}>Loading workspace record...</div>
      </AppContainer>
    );
  }

  if (!item) {
    return (
      <AppContainer style={{ paddingTop: "24px" }}>
        <div style={headerPanelStyle}>
          <div>
            <div style={eyebrowStyle}>Workspace Record</div>
            <h1 style={pageTitleStyle}>Record not found</h1>
            <p style={descriptionStyle}>{errorMessage || "This workspace record is not available."}</p>
          </div>
          <Link href="/workspace" style={primaryButtonStyle}>
            Back to Workspace
          </Link>
        </div>
      </AppContainer>
    );
  }

  return (
    <AppContainer style={{ paddingTop: "24px" }}>
      <div style={headerPanelStyle}>
        <div>
          <div style={eyebrowStyle}>Workspace Record</div>
          <h1 style={pageTitleStyle}>{item.signal_title || "Untitled workspace record"}</h1>
          {metadata.length > 0 ? <p style={descriptionStyle}>{metadata.join(" | ")}</p> : null}
        </div>
        <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
          <Link href="/workspace" style={primaryButtonStyle}>
            Back to Workspace
          </Link>
          {item.signal_id ? (
            <Link href={`/signals/detail?id=${encodeURIComponent(item.signal_id)}`} style={secondaryButtonStyle}>
              Open Signal
            </Link>
          ) : null}
          <button onClick={handleDelete} style={dangerButtonStyle}>
            Delete
          </button>
        </div>
      </div>

      <article style={recordCardStyle}>
        {refreshing ? (
          <div style={refreshingNoticeStyle}>
            Showing the last opened copy while refreshing the workspace record.
          </div>
        ) : null}

        {(item.topic || item.content_type) && (
          <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", marginBottom: "16px" }}>
            {item.topic ? <span style={topicPillStyle}>{item.topic}</span> : null}
            {item.content_type ? <span style={neutralPillStyle}>{item.content_type}</span> : null}
          </div>
        )}

        {item.image_url ? (
          <ContentSection title="Visual Preview">
            <div style={imageFrameStyle}>
              <Image
                src={apiUrl(item.image_url)}
                alt={item.signal_title || "Workspace visual"}
                width={1600}
                height={1000}
                unoptimized
                style={{ display: "block", width: "100%", height: "auto" }}
              />
            </div>
            <div style={{ display: "flex", gap: "10px", flexWrap: "wrap", marginTop: "12px" }}>
              <a href={apiUrl(item.image_url)} target="_blank" rel="noreferrer" style={secondaryButtonStyle}>
                Open Image
              </a>
              {item.image_metadata_url ? (
                <a href={apiUrl(item.image_metadata_url)} target="_blank" rel="noreferrer" style={secondaryButtonStyle}>
                  Open Metadata
                </a>
              ) : null}
            </div>
            {item.visual_style || item.visual_direction ? (
              <div style={{ marginTop: "12px" }}>
                <HighlightBlock
                  value={[item.visual_style ? `Visual style: ${item.visual_style}` : "", item.visual_direction || ""]
                    .filter(Boolean)
                    .join("\n\n")}
                />
              </div>
            ) : null}
          </ContentSection>
        ) : null}

        {Array.isArray(item.chat_messages) && item.chat_messages.length > 0 ? (
          <ContentSection title="Conversation History">
            <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
              {item.chat_messages.map((message, index) => {
                const isUser = message.role === "user";
                return (
                  <div
                    key={`${message.role || "message"}-${index}`}
                    style={{
                      ...chatBubbleStyle,
                      alignSelf: isUser ? "flex-end" : "flex-start",
                      background: isUser ? "#111827" : "#ffffff",
                      color: isUser ? "#ffffff" : "#374151",
                      borderColor: isUser ? "#111827" : "#e5e7eb",
                    }}
                  >
                    <div style={{ ...sectionEyebrowStyle, color: isUser ? "#ffffff" : "#6b7280" }}>
                      {isUser ? "User" : "Assistant"}
                    </div>
                    {message.content || ""}
                  </div>
                );
              })}
            </div>
          </ContentSection>
        ) : null}

        {normalizeText(item.reflection_context).trim() ? (
          <ContentSection title="Reflection Context">
            <HighlightBlock value={item.reflection_context} />
          </ContentSection>
        ) : null}

        <ManualSourceSummary item={item} />
        <VerificationSummary metadata={item.verification_metadata} />

        {normalizeText(item.signal_summary).trim() ? (
          <ContentSection title="Signal Summary">
            <TextBlock value={item.signal_summary} />
          </ContentSection>
        ) : null}

        {normalizeText(item.why_it_matters).trim() ? (
          <ContentSection title="Why It Matters">
            <TextBlock value={item.why_it_matters} />
          </ContentSection>
        ) : null}

        {normalizeText(item.relevance_to_projects).trim() ? (
          <ContentSection title="Project Takeaways">
            <ProjectMap value={item.relevance_to_projects} />
          </ContentSection>
        ) : null}

        {normalizeText(item.relevance_to_career).trim() ? (
          <ContentSection title="Career Takeaway">
            <HighlightBlock value={item.relevance_to_career} />
          </ContentSection>
        ) : null}

        {normalizeText(item.synthesized_insight).trim() ? (
          <ContentSection title="Strategic Insight">
            <HighlightBlock value={item.synthesized_insight} />
          </ContentSection>
        ) : null}

        {normalizeText(item.final_reflection).trim() ? (
          <ContentSection title="My Reflection">
            <HighlightBlock value={item.final_reflection} />
          </ContentSection>
        ) : null}

        {normalizeText(item.user_input).trim() ? (
          <ContentSection title="Last User Prompt">
            <HighlightBlock value={item.user_input} />
          </ContentSection>
        ) : null}

        {normalizeText(item.ai_response).trim() ? (
          <ContentSection title="Last AI Response">
            <HighlightBlock value={item.ai_response} />
          </ContentSection>
        ) : null}
      </article>
    </AppContainer>
  );
}

export default function WorkspaceDetailPage() {
  return (
    <Suspense
      fallback={
        <AppContainer style={{ paddingTop: "24px" }}>
          <div style={stateCardStyle}>Loading workspace record...</div>
        </AppContainer>
      }
    >
      <WorkspaceDetailContent />
    </Suspense>
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

const recordCardStyle = {
  border: "1px solid #e5e7eb",
  borderRadius: "18px",
  background: "#ffffff",
  padding: "20px",
  boxShadow: "0 4px 14px rgba(15, 23, 42, 0.04)",
} as const;

const stateCardStyle = {
  ...recordCardStyle,
  color: "#6b7280",
} as const;

const refreshingNoticeStyle = {
  border: "1px solid #bfdbfe",
  borderRadius: "8px",
  background: "#eff6ff",
  color: "#1e40af",
  padding: "10px 12px",
  fontSize: "13px",
  fontWeight: 700,
  marginBottom: "14px",
} as const;

const actionPolicyLineStyle = {
  marginTop: "10px",
  border: "1px solid #e5e7eb",
  borderRadius: "8px",
  background: "#f8fafc",
  color: "#334155",
  padding: "10px 12px",
  fontSize: "13px",
  fontWeight: 700,
  lineHeight: 1.55,
} as const;

const actionEligibilityGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))",
  gap: "10px",
  marginTop: "8px",
} as const;

const actionEligibilityTitleStyle = {
  marginTop: "14px",
  color: "#64748b",
  fontSize: "12px",
  fontWeight: 800,
  textTransform: "uppercase" as const,
  letterSpacing: "0",
} as const;

const actionEligibilityTileStyle = {
  border: "1px solid #dbeafe",
  borderRadius: "8px",
  background: "#f8fafc",
  padding: "11px",
} as const;

const actionEligibilityBlockedStyle = {
  ...actionEligibilityTileStyle,
  borderColor: "#fecaca",
  background: "#fff7f7",
} as const;

const actionEligibilityReasonStyle = {
  marginTop: "7px",
  color: "#475569",
  fontSize: "13px",
  lineHeight: 1.45,
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

const descriptionStyle = {
  margin: "6px 0 0",
  color: "#6b7280",
  fontSize: "13px",
  lineHeight: 1.5,
  maxWidth: "780px",
} as const;

const sectionTitleStyle = {
  margin: "0 0 10px",
  color: "#111827",
  fontSize: "16px",
  fontWeight: 600,
  lineHeight: 1.35,
} as const;

const sectionEyebrowStyle = {
  color: "#6b7280",
  fontSize: "12px",
  fontWeight: 700,
  textTransform: "uppercase" as const,
  letterSpacing: "0.4px",
  marginBottom: "8px",
} as const;

const textBlockStyle = {
  color: "#374151",
  fontSize: "14px",
  lineHeight: 1.75,
  whiteSpace: "pre-wrap" as const,
} as const;

const highlightBlockStyle = {
  border: "1px solid #e5e7eb",
  borderRadius: "8px",
  background: "#ffffff",
  color: "#374151",
  padding: "14px 16px",
  fontSize: "14px",
  lineHeight: 1.75,
  whiteSpace: "pre-wrap" as const,
} as const;

const imageFrameStyle = {
  border: "1px solid #e5e7eb",
  borderRadius: "12px",
  background: "#ffffff",
  overflow: "hidden",
} as const;

const chatBubbleStyle = {
  maxWidth: "92%",
  border: "1px solid #e5e7eb",
  borderRadius: "12px",
  padding: "14px 16px",
  whiteSpace: "pre-wrap" as const,
  lineHeight: 1.7,
  fontSize: "14px",
} as const;

const summaryGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))",
  gap: "10px",
} as const;

const summaryTileStyle = {
  border: "1px solid #e5e7eb",
  borderRadius: "8px",
  background: "#ffffff",
  padding: "12px",
} as const;

const summaryValueStyle = {
  color: "#111827",
  fontSize: "13px",
  fontWeight: 700,
  lineHeight: 1.45,
  whiteSpace: "pre-wrap" as const,
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
  cursor: "pointer",
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
  cursor: "pointer",
} as const;

const dangerButtonStyle = {
  ...secondaryButtonStyle,
  border: "1px solid #f43f5e",
  color: "#be123c",
} as const;

const topicPillStyle = {
  border: "1px solid #c7d2fe",
  borderRadius: "999px",
  background: "#eef2ff",
  color: "#4338ca",
  padding: "6px 10px",
  fontSize: "12px",
  fontWeight: 600,
} as const;

const neutralPillStyle = {
  border: "1px solid #e5e7eb",
  borderRadius: "999px",
  background: "#ffffff",
  color: "#374151",
  padding: "6px 10px",
  fontSize: "12px",
  fontWeight: 600,
} as const;
