"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import AppContainer from "@/components/AppContainer";
import PageHeader from "@/components/PageHeader";
import RequireAdminAuth from "@/components/RequireAdminAuth";
import SectionCard from "@/components/SectionCard";
import { apiUrl } from "@/lib/api";
import { adminFetch } from "@/lib/adminAuth";

type ReflectionMetadata = {
  id: string;
  title?: string;
  timestamp?: string;
  source?: string;
  tags?: string[];
  depth?: string | null;
  duration_minutes?: number | null;
  self_correction_count?: number | null;
  thesis?: string | null;
  key_claims?: string[];
  counterpoints?: string[];
  open_questions?: string[];
  final_takeaway?: string | null;
  confidence?: number | null;
  evidence_strength?: string | null;
  content_format?: "markdown" | "json_html";
  github_url?: string;
  raw_html_url?: string | null;
  schema_url?: string | null;
};

type ReflectionDetailPayload = {
  metadata?: ReflectionMetadata;
  content?: string;
  schema_json?: unknown;
  raw_html_content?: string | null;
};

type RelatedSignal = {
  signal_id?: string;
  title?: string;
  url?: string;
  source?: string;
  published_at?: string;
  matched_tags?: string[];
  score?: number;
};

type RelatedManualSession = {
  session_id?: string;
  title?: string;
  created_at?: string;
  updated_at?: string;
  analysis_status?: string;
  upload_reason?: string;
  intended_use?: string;
  cognitive_layer?: string;
  matched_tags?: string[];
  matched_terms?: string[];
  score?: number;
};

type BackfillSuggestion = {
  id?: string;
  title?: string;
  missing_fields?: string[];
  suggested_thesis?: string;
  suggested_key_claims?: string[];
  suggested_counterpoints?: string[];
  suggested_open_questions?: string[];
  suggested_final_takeaway?: string;
  suggested_frontmatter_patch?: string;
};

type BackfillDraftResult = {
  reflection_id?: string;
  file_path?: string;
  missing_fields?: string[];
  suggested_frontmatter_patch?: string;
};

type BackfillApplyResult = {
  reflection_id?: string;
  github_path?: string;
  changed_fields?: string[];
  commit_message?: string;
  commit_sha?: string;
  content_url?: string;
};

type ConversationMessage = {
  id: string;
  role: "user" | "assistant" | "system";
  label: string;
  html: string;
};

type ViewMode = "overview" | "conversation" | "source";

export default function ReflectionDetailClient() {
  const searchParams = useSearchParams();
  const reflectionId = decodeURIComponent(searchParams.get("id") || "");
  const [payload, setPayload] = useState<ReflectionDetailPayload | null>(null);
  const [relatedSignals, setRelatedSignals] = useState<RelatedSignal[]>([]);
  const [relatedManualSessions, setRelatedManualSessions] = useState<RelatedManualSession[]>([]);
  const [backfillSuggestion, setBackfillSuggestion] = useState<BackfillSuggestion | null>(null);
  const [backfillDraftResult, setBackfillDraftResult] = useState<BackfillDraftResult | null>(null);
  const [backfillDraftLoading, setBackfillDraftLoading] = useState(false);
  const [backfillApplyResult, setBackfillApplyResult] = useState<BackfillApplyResult | null>(null);
  const [backfillApplyLoading, setBackfillApplyLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [activeView, setActiveView] = useState<ViewMode>("conversation");
  const [isExpanded, setIsExpanded] = useState(false);
  const [showBackfillDraft, setShowBackfillDraft] = useState(false);

  const metadata = payload?.metadata;
  const displayTitle = useMemo(() => getDisplayTitle(metadata, reflectionId), [metadata, reflectionId]);
  const primarySourceUrl = metadata?.raw_html_url || metadata?.github_url || undefined;
  const sourceButtonLabel = metadata?.raw_html_url ? "Source" : "GitHub";
  const rawHtmlContent = payload?.raw_html_content ?? "";

  useEffect(() => {
    if (!reflectionId) return;

    fetch(apiUrl(`/reflection/${encodeURIComponent(reflectionId)}`), { cache: "no-store" })
      .then((res) => {
        if (!res.ok) throw new Error("Failed to load reflection detail.");
        return res.json();
      })
      .then((data) => {
        setPayload(data);
        setErrorMessage("");
      })
      .catch(() => {
        setPayload(null);
        setErrorMessage("Failed to load reflection detail.");
      });

    fetch(apiUrl(`/reflection/${encodeURIComponent(reflectionId)}/related-signals?days=30`), { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : []))
      .then((data) => setRelatedSignals(Array.isArray(data) ? data : []))
      .catch(() => setRelatedSignals([]));

    fetch(apiUrl(`/reflection/${encodeURIComponent(reflectionId)}/related-manual-sessions?limit=8`), { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : []))
      .then((data) => setRelatedManualSessions(Array.isArray(data) ? data : []))
      .catch(() => setRelatedManualSessions([]));

    fetch(apiUrl(`/reflection/${encodeURIComponent(reflectionId)}/backfill-preview`), { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => setBackfillSuggestion(data))
      .catch(() => setBackfillSuggestion(null));
  }, [reflectionId]);

  const parsedConversation = useMemo(() => {
    if (!rawHtmlContent) return [];
    return parseConversationMessages(rawHtmlContent);
  }, [rawHtmlContent]);

  const sourceSrcDoc = useMemo(() => {
    if (!rawHtmlContent) return "";
    if (parsedConversation.length) return buildArtifactConversationSrcDoc(parsedConversation);
    return buildConversationSrcDoc(rawHtmlContent, "source");
  }, [rawHtmlContent, parsedConversation]);

  const summaryItems = [
    { label: "Source", value: metadata?.source || "Unknown" },
    { label: "Depth", value: metadata?.depth || "Unknown" },
    { label: "Duration", value: metadata?.duration_minutes ? `${metadata.duration_minutes} min` : "N/A" },
    { label: "Turns", value: parsedConversation.length ? `${parsedConversation.length}` : "HTML" },
    { label: "Connections", value: `${relatedSignals.length + relatedManualSessions.length}` },
  ];

  const overviewBlocks = [
    metadata?.thesis ? { label: "Thesis", kind: "text" as const, value: metadata.thesis } : null,
    metadata?.final_takeaway ? { label: "Final Takeaway", kind: "text" as const, value: metadata.final_takeaway } : null,
    { label: "Key Claims", kind: "list" as const, items: metadata?.key_claims || [], emptyLabel: "No key claims captured." },
    { label: "Counterpoints", kind: "list" as const, items: metadata?.counterpoints || [], emptyLabel: "No counterpoints captured." },
    { label: "Open Questions", kind: "list" as const, items: metadata?.open_questions || [], emptyLabel: "No open questions captured." },
  ].filter(Boolean) as Array<
    | { label: string; kind: "text"; value: string }
    | { label: string; kind: "list"; items: string[]; emptyLabel: string }
  >;

  const visibleOverviewBlocks = isExpanded ? overviewBlocks : overviewBlocks.slice(0, 2);
  const hiddenOverviewCount = Math.max(0, overviewBlocks.length - visibleOverviewBlocks.length);
  const visibleConversation = isExpanded ? parsedConversation : parsedConversation.slice(0, 3);
  const hiddenConversationCount = Math.max(0, parsedConversation.length - visibleConversation.length);

  const createBackfillDraft = async () => {
    try {
      setBackfillDraftLoading(true);
      const res = await adminFetch(apiUrl(`/reflection/${encodeURIComponent(reflectionId)}/backfill-draft`), {
        method: "POST",
      });
      if (!res.ok) {
        throw new Error("Failed to create backfill draft.");
      }
      const data = (await res.json()) as BackfillDraftResult;
      setBackfillDraftResult(data);
    } catch {
      setBackfillDraftResult(null);
    } finally {
      setBackfillDraftLoading(false);
    }
  };

  const applyBackfillToSource = async () => {
    try {
      setBackfillApplyLoading(true);
      const res = await adminFetch(apiUrl(`/reflection/${encodeURIComponent(reflectionId)}/backfill-apply`), {
        method: "POST",
      });
      if (!res.ok) {
        throw new Error("Failed to apply backfill to source.");
      }
      const data = (await res.json()) as BackfillApplyResult;
      setBackfillApplyResult(data);
    } catch {
      setBackfillApplyResult(null);
    } finally {
      setBackfillApplyLoading(false);
    }
  };

  return (
    <AppContainer>
      <RequireAdminAuth>
        <style>{conversationRichTextCss}</style>
        <PageHeader
          title={displayTitle}
          description="Read the structured summary, inspect the original deep conversation, and connect this deep reflection to recent signals."
        />

        {errorMessage ? <div style={errorStyle}>{errorMessage}</div> : null}

        <section style={heroStyle}>
          <div style={heroTopStyle}>
            <div style={{ display: "grid", gap: "10px" }}>
              <div style={eyebrowStyle}>Deep Reflection {metadata?.id || reflectionId}</div>
              <h1 style={titleStyle}>{displayTitle}</h1>
              <div style={subtleStyle}>
                {[formatDate(metadata?.timestamp), metadata?.evidence_strength || "No evidence label", confidenceLabel(metadata?.confidence)]
                  .filter(Boolean)
                  .join(" · ")}
              </div>
            </div>
            <div style={actionRowStyle}>
              <Link href="/reflections" style={primaryButtonStyle}>
                Back
              </Link>
              {primarySourceUrl ? (
                <a href={primarySourceUrl} target="_blank" rel="noreferrer" style={secondaryButtonStyle}>
                  {sourceButtonLabel}
                </a>
              ) : null}
              {metadata?.schema_url ? (
                <a href={metadata.schema_url} target="_blank" rel="noreferrer" style={secondaryButtonStyle}>
                  Schema
                </a>
              ) : null}
            </div>
          </div>

          {(metadata?.tags || []).length ? (
            <div style={chipRowStyle}>
              {(metadata?.tags || []).map((tag) => (
                <span key={tag} style={chipStyle}>{tag}</span>
              ))}
            </div>
          ) : null}

          <div style={statGridStyle}>
            {summaryItems.map((item) => (
              <div key={item.label} style={statCardStyle}>
                <div style={statLabelStyle}>{item.label}</div>
                <div style={statValueStyle}>{item.value}</div>
              </div>
            ))}
          </div>

          <div style={metaGridStyle}>
            <MetaItem label="Format" value={metadata?.content_format === "json_html" ? "JSON + HTML" : "Markdown"} />
            <MetaItem label="Self Corrections" value={metadata?.self_correction_count != null ? `${metadata.self_correction_count}` : "N/A"} />
            <MetaItem label="Signals" value={`${relatedSignals.length}`} />
            <MetaItem label="Manual Matches" value={`${relatedManualSessions.length}`} />
          </div>
        </section>

        <SectionCard title="Cognition Boundary">
          <div style={boundaryGridStyle}>
            <div style={boundaryItemStyle}>
              <strong>Context, not evidence</strong>
              <span>This reflection may shape interpretation, but it should not verify external claims or bypass signal evidence checks.</span>
            </div>
            <div style={boundaryItemStyle}>
              <strong>Human-marked trajectory</strong>
              <span>Only explicit review decisions, project takeaways, watch/action outcomes, or future marked judgment moments should become trajectory seed.</span>
            </div>
            <div style={boundaryItemStyle}>
              <strong>Skill boundary</strong>
              <span>Potential concept-skill material belongs in a reviewed cross-repo workflow, not automatic AI Radar routing.</span>
            </div>
          </div>
        </SectionCard>

        {backfillSuggestion?.missing_fields?.length ? (
          <SectionCard title="Maintenance Tools">
            <div style={{ display: "grid", gap: "12px" }}>
              <div style={backfillCollapsedNoticeStyle}>
                <div>
                  <strong>Backfill Draft is hidden by default.</strong>
                  <span>
                    Use it only when you intentionally want to repair missing structured fields in an older deep reflection.
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => setShowBackfillDraft((value) => !value)}
                  style={secondaryButtonStyle}
                >
                  {showBackfillDraft ? "Hide Backfill Draft" : "Show Backfill Draft"}
                </button>
              </div>

              {showBackfillDraft ? (
            <div style={{ display: "grid", gap: "14px" }}>
              <div style={{ color: "var(--app-text-muted)", fontSize: "14px", lineHeight: 1.7 }}>
                Missing fields: {(backfillSuggestion.missing_fields || []).join(", ")}
              </div>
              {backfillSuggestion.suggested_thesis ? (
                <StructuredBlock label="Suggested Thesis" value={backfillSuggestion.suggested_thesis} />
              ) : null}
              {(backfillSuggestion.suggested_key_claims || []).length ? (
                <StructuredListBlock
                  label="Suggested Key Claims"
                  items={backfillSuggestion.suggested_key_claims || []}
                  emptyLabel="No suggested claims."
                />
              ) : null}
              {(backfillSuggestion.suggested_counterpoints || []).length ? (
                <StructuredListBlock
                  label="Suggested Counterpoints"
                  items={backfillSuggestion.suggested_counterpoints || []}
                  emptyLabel="No suggested counterpoints."
                />
              ) : null}
              {(backfillSuggestion.suggested_open_questions || []).length ? (
                <StructuredListBlock
                  label="Suggested Open Questions"
                  items={backfillSuggestion.suggested_open_questions || []}
                  emptyLabel="No suggested questions."
                />
              ) : null}
              {backfillSuggestion.suggested_final_takeaway ? (
                <StructuredBlock
                  label="Suggested Final Takeaway"
                  value={backfillSuggestion.suggested_final_takeaway}
                />
              ) : null}
              {backfillSuggestion.suggested_frontmatter_patch ? (
                <div style={blockStyle}>
                  <div style={blockLabelStyle}>Copy-ready Frontmatter Patch</div>
                  <pre style={patchBlockStyle}>{backfillSuggestion.suggested_frontmatter_patch}</pre>
                </div>
              ) : null}
              <div style={{ display: "flex", gap: "12px", flexWrap: "wrap" }}>
                <button
                  type="button"
                  onClick={createBackfillDraft}
                  disabled={backfillDraftLoading}
                  style={secondaryButtonStyle}
                >
                  {backfillDraftLoading ? "Creating..." : "Create Draft File"}
                </button>
                <button
                  type="button"
                  onClick={applyBackfillToSource}
                  disabled={backfillApplyLoading}
                  style={primaryButtonStyle}
                >
                  {backfillApplyLoading ? "Applying..." : "Apply to Source Repo"}
                </button>
              </div>
              {backfillDraftResult?.file_path ? (
                <div style={blockStyle}>
                  <div style={blockLabelStyle}>Draft File Created</div>
                  <div style={{ color: "var(--app-text-muted)", lineHeight: 1.7 }}>
                    {backfillDraftResult.file_path}
                  </div>
                </div>
              ) : null}
              {backfillApplyResult?.commit_sha ? (
                <div style={blockStyle}>
                  <div style={blockLabelStyle}>Source Repo Updated</div>
                  <div style={{ color: "var(--app-text-muted)", lineHeight: 1.7 }}>
                    Commit: {backfillApplyResult.commit_sha}
                  </div>
                  {(backfillApplyResult.changed_fields || []).length ? (
                    <div style={{ color: "var(--app-text-muted)", lineHeight: 1.7 }}>
                      Changed: {(backfillApplyResult.changed_fields || []).join(", ")}
                    </div>
                  ) : null}
                  {backfillApplyResult.content_url ? (
                    <a href={backfillApplyResult.content_url} target="_blank" rel="noreferrer" style={secondaryButtonStyle}>
                      Open Updated File
                    </a>
                  ) : null}
                </div>
              ) : null}
            </div>
              ) : null}
            </div>
          </SectionCard>
        ) : null}

        <SectionCard title="Deep Reflection View">
          <div style={{ display: "grid", gap: "16px" }}>
            <div style={viewControlRowStyle}>
              <div style={tabRowStyle}>
                <button type="button" style={tabStyle(activeView === "overview")} onClick={() => { setActiveView("overview"); setIsExpanded(false); }}>
                  Structured Summary
                </button>
                <button type="button" style={tabStyle(activeView === "conversation")} onClick={() => { setActiveView("conversation"); setIsExpanded(false); }}>
                  Conversation View
                </button>
                <button type="button" style={tabStyle(activeView === "source")} onClick={() => { setActiveView("source"); setIsExpanded(false); }}>
                  Original HTML
                </button>
              </div>
              <div style={expandActionRowStyle}>
                <button type="button" style={utilityButtonStyle(!isExpanded)} onClick={() => setIsExpanded(true)} disabled={isExpanded}>
                  Open All
                </button>
                <button type="button" style={utilityButtonStyle(isExpanded)} onClick={() => setIsExpanded(false)} disabled={!isExpanded}>
                  Collapse
                </button>
              </div>
            </div>

            {activeView === "overview" ? (
              <div style={{ display: "grid", gap: "14px" }}>
                <div style={leadStyle}>This is the fastest way to understand what the deep reflection concluded and where its reasoning ended up.</div>
                <div style={{ ...contentCardStyle, ...(isExpanded ? {} : collapsedPanelStyle) }}>
                  <div style={contentStyle}>{payload?.content?.trim() ? payload.content : "No deep reflection content available."}</div>
                </div>
                {visibleOverviewBlocks.map((block) =>
                  block.kind === "text" ? (
                    <StructuredBlock key={block.label} label={block.label} value={block.value} />
                  ) : (
                    <StructuredListBlock key={block.label} label={block.label} items={block.items} emptyLabel={block.emptyLabel} />
                  ),
                )}
                {!isExpanded && hiddenOverviewCount > 0 ? (
                  <div style={collapsedHintStyle}>Open All to see {hiddenOverviewCount} more summary section{hiddenOverviewCount > 1 ? "s" : ""}.</div>
                ) : null}
              </div>
            ) : null}

            {activeView === "conversation" ? (
              <div style={{ display: "grid", gap: "14px" }}>
                <div style={leadStyle}>This view turns the deep conversation into a cleaner transcript. User turns stay lighter and right-aligned, while assistant turns feel more grounded and editorial.</div>
                {parsedConversation.length ? (
                  <div style={conversationShellStyle}>
                      {visibleConversation.map((message, index) => (
                        <div
                          key={message.id}
                          style={{
                            ...conversationRowStyle,
                            justifyContent: message.role === "user" ? "flex-end" : "flex-start",
                          }}
                        >
                          {message.role !== "user" ? (
                            <div
                              style={{
                                ...avatarStyle,
                                background: message.role === "assistant" ? "var(--app-success-fg)" : "var(--app-chip-bg)",
                              }}
                              title={message.label}
                            >
                              {message.role === "assistant" ? "AI" : "SYS"}
                            </div>
                          ) : null}
                          <div
                            style={{
                              ...messageCardStyle,
                              background:
                                message.role === "assistant"
                                  ? "var(--app-success-bg)"
                                  : message.role === "user"
                                    ? "var(--app-surface-bg)"
                                    : "var(--app-surface-muted-bg)",
                              borderColor: message.role === "assistant" ? "var(--app-success-border)" : message.role === "user" ? "var(--app-surface-border)" : "var(--app-chip-border)",
                              boxShadow:
                                message.role === "assistant"
                                  ? "0 16px 36px rgba(15, 118, 110, 0.10)"
                                  : "0 12px 28px rgba(15, 23, 42, 0.06)",
                              maxWidth: message.role === "assistant" ? "min(860px, calc(100% - 68px))" : "min(760px, calc(100% - 68px))",
                              borderTopLeftRadius: message.role === "assistant" ? "12px" : "24px",
                              borderTopRightRadius: message.role === "user" ? "12px" : "24px",
                            }}
                          >
                            <div style={messageHeaderStyle}>
                              <div style={messageLabelStyle}>{message.label}</div>
                              <div style={messageIndexStyle}>{String(index + 1).padStart(2, "0")}</div>
                            </div>
                            <div className="reflection-conversation-body" style={messageBodyStyle} dangerouslySetInnerHTML={{ __html: message.html }} />
                          </div>
                          {message.role === "user" ? (
                            <div style={{ ...avatarStyle, background: "var(--app-primary-action-bg)" }} title={message.label}>
                              You
                            </div>
                          ) : null}
                        </div>
                      ))}
                      {!isExpanded && hiddenConversationCount > 0 ? (
                        <div style={collapsedHintStyle}>Open All to continue through the remaining {hiddenConversationCount} message turns.</div>
                      ) : null}
                  </div>
                ) : (
                  <div style={emptyStyle}>We still could not reconstruct a full transcript from this export. Use Original HTML as the fallback view.</div>
                )}
              </div>
            ) : null}

            {activeView === "source" ? (
              sourceSrcDoc ? (
                <div style={sourceArtifactShellStyle}>
                  <div style={sourceArtifactHeaderStyle}>
                    <div>
                      <div style={sourceArtifactEyebrowStyle}>Origin HTML</div>
                      <div style={sourceArtifactTitleStyle}>Claude-style source document</div>
                    </div>
                    <div style={sourceArtifactMetaStyle}>
                      {metadata?.content_format === "json_html" ? "JSON + HTML" : "HTML source"}
                    </div>
                  </div>
                  <iframe title="Original conversation" sandbox="" srcDoc={sourceSrcDoc} style={{ ...iframeStyle, minHeight: isExpanded ? "860px" : "460px" }} />
                  {!isExpanded ? <div style={collapsedHintStyle}>Open All to expand the full HTML reading area.</div> : null}
                </div>
              ) : (
                <div style={emptyStyle}>No paired HTML source is available for this deep reflection yet.</div>
              )
            ) : null}
          </div>
        </SectionCard>

        <div style={twoColStyle}>
          <SectionCard title="Related Signals">
            <div style={connectionBoundaryStyle}>
              Related signals are retrieval context only. Use Signal Detail evidence and Review Inbox gates before
              turning a reflection match into project judgment.
            </div>
            {relatedSignals.length ? (
              <div style={{ display: "grid", gap: "12px" }}>
                {relatedSignals.map((item, index) => (
                  <div key={item.signal_id || index} style={listCardStyle}>
                    <div style={listTitleStyle}>{item.title || "Untitled Signal"}</div>
                    <div style={listMetaStyle}>
                      {[item.source || "Unknown source", formatDate(item.published_at), typeof item.score === "number" ? item.score.toFixed(2) : ""]
                        .filter(Boolean)
                        .join(" · ")}
                    </div>
                    {(item.matched_tags || []).length ? (
                      <div style={chipRowStyle}>
                        {(item.matched_tags || []).map((tag) => (
                          <span key={`${item.signal_id || index}-${tag}`} style={chipStyle}>{tag}</span>
                        ))}
                      </div>
                    ) : null}
                  </div>
                ))}
              </div>
            ) : (
              <div style={emptyStyle}>No related signals yet.</div>
            )}
          </SectionCard>

          <SectionCard title="Related Manual Sessions">
            <div style={connectionBoundaryStyle}>
              Related manual sessions preserve your intent and source material context, but they still need signal
              review before becoming durable Workspace or Project Takeaway evidence.
            </div>
            {relatedManualSessions.length ? (
              <div style={{ display: "grid", gap: "12px" }}>
                {relatedManualSessions.map((item, index) => (
                  <div key={item.session_id || index} style={listCardStyle}>
                    <div style={listTitleStyle}>{item.title || "Untitled Manual Session"}</div>
                    <div style={listMetaStyle}>
                      {[item.analysis_status || "Unknown status", formatDate(item.updated_at || item.created_at), typeof item.score === "number" ? item.score.toFixed(2) : ""]
                        .filter(Boolean)
                        .join(" · ")}
                    </div>
                    <div style={manualIntentRowStyle}>
                      {item.session_id ? (
                        <Link href={`/manual/detail?id=${encodeURIComponent(item.session_id)}`} style={manualSessionLinkStyle}>
                          Open Manual Session
                        </Link>
                      ) : null}
                      {item.upload_reason ? <span>Reason: {item.upload_reason}</span> : null}
                      {item.intended_use ? <span>Use: {item.intended_use}</span> : null}
                      <span>Layer: {formatPlainLabel(item.cognitive_layer || "unclassified")}</span>
                    </div>
                    {(item.matched_tags || []).length || (item.matched_terms || []).length ? (
                      <div style={chipRowStyle}>
                        {(item.matched_tags || []).map((tag) => (
                          <span key={`${item.session_id || index}-tag-${tag}`} style={chipStyle}>{tag}</span>
                        ))}
                        {(item.matched_terms || []).map((term) => (
                          <span key={`${item.session_id || index}-term-${term}`} style={mutedChipStyle}>{term}</span>
                        ))}
                      </div>
                    ) : null}
                  </div>
                ))}
              </div>
            ) : (
              <div style={emptyStyle}>No related manual sessions yet.</div>
            )}
          </SectionCard>
        </div>
      </RequireAdminAuth>
    </AppContainer>
  );
}

function MetaItem({ label, value }: { label: string; value: string }) {
  return (
    <div style={metaItemStyle}>
      <div style={metaLabelStyle}>{label}</div>
      <div style={metaValueStyle}>{value}</div>
    </div>
  );
}

function formatDate(value?: string | null) {
  if (!value) return "Unknown";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function formatPlainLabel(value?: string) {
  return (value || "")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase())
    .trim();
}

function getDisplayTitle(metadata: ReflectionMetadata | undefined, reflectionId: string) {
  const raw = (metadata?.title || "").trim();
  if (!raw) return metadata?.id || reflectionId || "Reflection";
  if (/[^\x00-\x7F]/.test(raw)) return metadata?.id || reflectionId || "Reflection";
  if (/^refl?[_-]/i.test(raw) || raw.length > 48) return metadata?.id || reflectionId || raw;
  return raw;
}

function confidenceLabel(value?: number | null) {
  if (typeof value !== "number") return "Confidence N/A";
  return `${Math.round(value * 100)}% confidence`;
}

function buildConversationSrcDoc(rawHtml: string, mode: "conversation" | "source") {
  return `<!doctype html><html><head><meta charset="utf-8" /><meta name="viewport" content="width=device-width, initial-scale=1" /><style>
  :root{color-scheme:dark}
  *{box-sizing:border-box}
  body{margin:0;background:${mode === "conversation" ? "#07111f" : "#0b1424"};color:#d8e4f2;font:15px/1.76 Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
  body:before{content:"Deep Reflection Source";display:block;max-width:${mode === "conversation" ? "980px" : "1040px"};margin:0 auto;padding:${mode === "conversation" ? "24px 22px 0" : "28px 24px 0"};color:#93a7bd;font-size:12px;font-weight:800;text-transform:uppercase;letter-spacing:0}
  body:after{content:"";display:block;height:34px}
  body > *{max-width:${mode === "conversation" ? "980px" : "1040px"};margin-left:auto;margin-right:auto}
  body > :not(script):not(style){background:${mode === "conversation" ? "transparent" : "#111c2c"};border:${mode === "conversation" ? "0" : "1px solid #26364d"};border-radius:${mode === "conversation" ? "0" : "8px"};box-shadow:${mode === "conversation" ? "none" : "0 18px 42px rgba(0,0,0,.22)"};padding:${mode === "conversation" ? "0 22px" : "28px"}}
  h1,h2,h3,h4{color:#f6f9ff;line-height:1.16;margin:1.2em 0 .55em;letter-spacing:0}
  h1{font-size:34px}h2{font-size:24px;border-top:1px solid #26364d;padding-top:18px}h3{font-size:19px}h4{font-size:16px}
  p{margin:.7em 0}strong{color:#f6f9ff}a{color:#8cc8ff;text-decoration-thickness:1px;text-underline-offset:3px}
  ul,ol{padding-left:1.35rem;margin:.75em 0 1em}li{margin:.35em 0}
  img{max-width:100%;height:auto;border-radius:8px;border:1px solid #26364d;box-shadow:0 12px 28px rgba(0,0,0,.22)}
  pre{overflow:auto;padding:15px 17px;border-radius:8px;background:#07111f;color:#d8e4f2;font:13px/1.65 Consolas,"Courier New",monospace}
  code{font-family:Consolas,"Courier New",monospace}:not(pre)>code{background:#172337;border:1px solid #26364d;padding:2px 6px;border-radius:6px;color:#f6f9ff}
  table{width:100%;border-collapse:separate;border-spacing:0;margin:1em 0;border:1px solid #26364d;border-radius:8px;overflow:hidden}th,td{border-bottom:1px solid #26364d;padding:10px 12px;text-align:left;vertical-align:top}th{background:#172337;color:#f6f9ff;font-weight:750}tr:last-child td{border-bottom:0}
  blockquote{margin:1em 0;padding:12px 16px;border-left:4px solid #60d6c9;background:#172337;border-radius:0 8px 8px 0;color:#d8e4f2}
  hr{border:0;border-top:1px solid #26364d;margin:1.35em 0}
  .conversation-shell{display:block}
  .message,.chat-message,.conversation-turn,.turn,[data-message-author-role],[class*="message"],[class*="turn"],[class*="font-user-message"],[class*="font-claude-response"]{margin:16px 0;padding:16px 18px;border:1px solid #26364d;border-radius:8px;background:#111c2c;box-shadow:0 8px 24px rgba(0,0,0,.18)}
  [data-message-author-role="assistant"],[class*="assistant"],[class*="font-claude-response"]{background:#102d2d;border-color:#1f6f68}
  [data-message-author-role="user"],[class*="user"],[class*="font-user-message"]{background:#111c2c;border-color:#26364d}
  [class*="font-user-message"]:before,[data-message-author-role="user"]:before{content:"You";display:inline-flex;margin-bottom:10px;color:#93a7bd;font-size:11px;font-weight:900;text-transform:uppercase;letter-spacing:0}
  [class*="font-claude-response"]:before,[data-message-author-role="assistant"]:before{content:"Claude";display:inline-flex;margin-bottom:10px;color:#60d6c9;font-size:11px;font-weight:900;text-transform:uppercase;letter-spacing:0}
  ${mode === "conversation" ? `
    body > *:not(.conversation-shell){display:none !important}
    [role="note"], [data-disclaimer="true"]{display:none !important}
    .conversation-shell [class*="thumbnail"], .conversation-shell [class*="toolbar"], .conversation-shell [class*="sidebar"], .conversation-shell [class*="drawer"]{display:none !important}
    .conversation-shell [class*="message"], .conversation-shell [data-message-author-role], .conversation-shell article, .conversation-shell section{max-width:820px;margin-left:auto;margin-right:auto}
  ` : `
    [class*="sidebar"],[class*="drawer"],[class*="toolbar"],[class*="sticky"],[class*="fixed"],nav,header,footer{display:none !important}
    [class*="max-w"],[class*="container"]{max-width:100% !important}
    [class*="rounded"]{border-radius:8px !important}
    [class*="shadow"]{box-shadow:none !important}
  `}
  </style></head><body>${rawHtml}</body></html>`;
}

function buildArtifactConversationSrcDoc(messages: ConversationMessage[]) {
  const renderedMessages = messages
    .map((message, index) => {
      const roleLabelText = message.role === "user" ? "You" : message.role === "system" ? "System" : "Claude";
      return `<article class="turn ${message.role}">
        <h2>${escapeHtml(roleLabelText)} <span>Turn ${String(index + 1).padStart(2, "0")}</span></h2>
        <section class="turn-content">${semanticizeMessageHtml(message.html)}</section>
      </article>`;
    })
    .join("");

  return `<!doctype html><html><head><meta charset="utf-8" /><meta name="viewport" content="width=device-width, initial-scale=1" /><style>
    :root{
      color-scheme:dark;
      --bg:#0b1424;
      --bg-subtle:#111c2c;
      --border:#26364d;
      --text:#f6f9ff;
      --text-muted:#93a7bd;
      --accent:#60d6c9;
      --accent-soft:#102d2d;
      --font-sans:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Hiragino Sans GB","Microsoft YaHei",Roboto,Helvetica,sans-serif;
      --font-mono:"SF Mono","JetBrains Mono","Fira Code",Consolas,"Liberation Mono",monospace;
      --measure:min(100%, 1080px);
      --radius:6px;
      --space:1rem;
    }
    *{box-sizing:border-box}
    body{margin:0;background:var(--bg);color:var(--text);font-family:var(--font-sans);font-size:16px;line-height:1.65;-webkit-font-smoothing:antialiased}
    .content{max-width:var(--measure);margin:0 auto;padding:2.2rem clamp(1.25rem,3vw,3rem) 5rem}
    .document-kicker{margin:0 0 .5rem;color:var(--text-muted);font-size:.78rem;font-weight:700;text-transform:uppercase;letter-spacing:0}
    h1,h2,h3,h4{line-height:1.25;font-weight:650;color:var(--text)}
    h1{font-size:2rem;margin:0 0 1.25rem;letter-spacing:-.01em}
    h2{font-size:1.4rem;margin:2.75rem 0 .85rem}
    h2 span{display:block;margin-top:.2rem;color:var(--text-muted);font-size:.78rem;font-weight:600;text-transform:uppercase;letter-spacing:0}
    h3{font-size:1.12rem;margin:2rem 0 .6rem}
    h4{font-size:1rem;margin:1.5rem 0 .5rem;color:var(--text-muted)}
    p{margin:0 0 1.15rem}
    a{color:var(--accent);text-decoration:none;border-bottom:1px solid color-mix(in srgb,var(--accent) 35%,transparent)}
    a:hover{border-bottom-color:var(--accent)}
    strong{font-weight:650}em{font-style:italic}
    ul,ol{margin:0 0 1.15rem;padding-left:1.4rem}li{margin:.3rem 0}li::marker{color:var(--text-muted)}
    blockquote{margin:1.5rem 0;padding:.2rem 0 .2rem 1.1rem;border-left:3px solid var(--accent);color:var(--text-muted);font-style:italic}
    blockquote p:last-child{margin-bottom:0}
    code{font-family:var(--font-mono);font-size:.875em;background:var(--bg-subtle);padding:.15em .4em;border-radius:4px;border:1px solid var(--border)}
    pre{margin:1.5rem 0;padding:1rem 1.1rem;background:var(--bg-subtle);border:1px solid var(--border);border-radius:var(--radius);overflow-x:auto;line-height:1.55}
    pre code{background:none;border:none;padding:0;font-size:.85rem;color:var(--text)}
    table{width:100%;border-collapse:collapse;margin:1.5rem 0;font-size:.92rem}
    th,td{text-align:left;padding:.6rem .8rem;border-bottom:1px solid var(--border)}
    thead th{background:var(--bg-subtle);font-weight:600;color:var(--text-muted);border-bottom:2px solid var(--border)}
    tbody tr:hover{background:var(--bg-subtle)}
    hr{border:none;border-top:1px solid var(--border);margin:3rem 0}
    img{max-width:100%;height:auto;border-radius:var(--radius)}
    figure{margin:1.5rem 0}figcaption{font-size:.85rem;color:var(--text-muted);margin-top:.5rem;text-align:center}
    .lead{color:var(--text-muted);margin-bottom:2rem}
    .turn{margin:0;padding:0;border:0;background:transparent}
    .turn + .turn{border-top:1px solid var(--border)}
    .turn-content{margin:0 0 2rem}
    .callout{margin:1.5rem 0;padding:.9rem 1.1rem;background:var(--accent-soft);border-radius:var(--radius);font-size:.95rem}
    button,select,input,textarea,svg,[role="button"],[aria-label*="Copy"],[aria-label*="copy"],[class*="toolbar"],[class*="menu"],[class*="popover"],[class*="sticky"],[class*="fixed"]{display:none!important}
  </style></head><body>
    <main class="content">
      <header>
        <p class="document-kicker">Origin HTML reformatted</p>
        <h1>Deep Reflection Review</h1>
        <p class="lead">Parsed from the original Claude export and rendered as a semantic reading document. Source chrome and interaction controls are intentionally removed.</p>
      </header>
      ${renderedMessages}
    </main>
  </body></html>`;
}

function semanticizeMessageHtml(html: string) {
  if (typeof window === "undefined") return sanitizeArtifactHtml(html);

  const parser = new window.DOMParser();
  const doc = parser.parseFromString(`<main>${html}</main>`, "text/html");
  doc.querySelectorAll(
    'script,style,iframe,noscript,button,select,input,textarea,svg,[role="button"],[aria-label*="Copy"],[aria-label*="copy"],[class*="toolbar"],[class*="menu"],[class*="popover"],[class*="sticky"],[class*="fixed"]',
  ).forEach((node) => node.remove());

  const root = doc.body.querySelector("main");
  if (!root) return sanitizeArtifactHtml(html);

  const blocks: string[] = [];
  root.childNodes.forEach((node) => appendSemanticNode(node, blocks));

  const result = blocks.join("\n").trim();
  if (result) return result;

  const fallback = stripHtml(html).replace(/\s+/g, " ").trim();
  return fallback ? `<p>${escapeHtml(fallback)}</p>` : "";
}

function appendSemanticNode(node: Node, blocks: string[]) {
  if (node.nodeType === Node.TEXT_NODE) {
    const text = node.textContent?.replace(/\s+/g, " ").trim();
    if (text) blocks.push(`<p>${escapeHtml(text)}</p>`);
    return;
  }

  if (!(node instanceof Element)) return;
  const tag = node.tagName.toLowerCase();
  const text = node.textContent?.replace(/\s+/g, " ").trim() || "";
  if (!text && tag !== "img") return;

  if (["h1", "h2"].includes(tag)) {
    blocks.push(`<h3>${sanitizeArtifactHtml(node.innerHTML)}</h3>`);
    return;
  }
  if (["h3", "h4", "p", "ul", "ol", "blockquote", "pre", "table", "figure", "img", "hr"].includes(tag)) {
    blocks.push(sanitizeArtifactHtml(node.outerHTML));
    return;
  }
  if (tag === "br") {
    return;
  }

  const hasBlockChildren = Array.from(node.children).some((child) =>
    ["h1", "h2", "h3", "h4", "p", "ul", "ol", "blockquote", "pre", "table", "figure", "div", "section", "article"].includes(child.tagName.toLowerCase()),
  );

  if (hasBlockChildren) {
    node.childNodes.forEach((child) => appendSemanticNode(child, blocks));
    return;
  }

  blocks.push(`<p>${sanitizeArtifactHtml(node.innerHTML || text)}</p>`);
}

function sanitizeArtifactHtml(html: string) {
  return sanitizeHtml(html)
    .replace(/\sclass="[^"]*"/gi, "")
    .replace(/\sclass='[^']*'/gi, "")
    .replace(/\sstyle="[^"]*"/gi, "")
    .replace(/\sstyle='[^']*'/gi, "");
}

function parseConversationMessages(rawHtml: string): ConversationMessage[] {
  if (typeof window === "undefined") return [];
  const parser = new window.DOMParser();
  const doc = parser.parseFromString(rawHtml, "text/html");
  doc.querySelectorAll("script, style, iframe, noscript").forEach((node) => node.remove());

  const claudeExportMessages = extractClaudeExportMessages(doc);
  if (claudeExportMessages.length >= 2) {
    return claudeExportMessages;
  }

  const explicitNodes = Array.from(doc.querySelectorAll("[data-message-author-role]"));
  if (explicitNodes.length) {
    return explicitNodes
      .map((node, index) => {
        const role = normalizeRole(node.getAttribute("data-message-author-role") || "");
        return { id: `attr-${index}`, role, label: roleLabel(role), html: sanitizeHtml(node.innerHTML) };
      })
      .filter((item) => stripHtml(item.html).trim());
  }

  const candidates = Array.from(doc.querySelectorAll("article, section, div, li")).filter((node) => {
    const text = (node.textContent || "").trim();
    const role = detectRole(node);
    return text.length > 40 && !!role && node.childElementCount > 0 && node.childElementCount < 40;
  });

  const deduped: Element[] = [];
  for (const node of candidates) {
    if (deduped.some((existing) => existing.contains(node) || node.contains(existing))) continue;
    deduped.push(node);
  }

  return deduped
    .map((node, index) => {
      const role = detectRole(node) || "assistant";
      return { id: `heuristic-${index}`, role, label: roleLabel(role), html: sanitizeHtml(stripRoleLabel(node.innerHTML)) };
    })
    .filter((item) => stripHtml(item.html).trim())
    .concat(extractTranscriptFallback(doc))
    .filter((item, index, arr) => {
      const text = stripHtml(item.html).replace(/\s+/g, " ").trim();
      return !!text && arr.findIndex((candidate) => stripHtml(candidate.html).replace(/\s+/g, " ").trim() === text && candidate.role === item.role) === index;
    });
}

function extractClaudeExportMessages(doc: Document): ConversationMessage[] {
  const nodes = Array.from(
    doc.querySelectorAll('[class*="font-user-message"], [class*="font-claude-response"], [data-testid*="user"], [data-testid*="assistant"]'),
  ).filter((node) => {
    const text = (node.textContent || "").replace(/\s+/g, " ").trim();
    return text.length > 0;
  });

  if (!nodes.length) {
    return [];
  }

  const compactNodes: Element[] = [];
  for (const node of nodes) {
    if (compactNodes.some((existing) => existing.contains(node))) {
      continue;
    }
    compactNodes.push(node);
  }

  const grouped: ConversationMessage[] = [];
  let currentRole: "user" | "assistant" | "system" | null = null;
  let currentParts: string[] = [];

  for (const node of compactNodes) {
    const classText = `${node.className || ""}`.toLowerCase();
    const testId = `${node.getAttribute("data-testid") || ""}`.toLowerCase();
    const role: "user" | "assistant" | "system" =
      classText.includes("font-user-message") || testId.includes("user")
        ? "user"
        : classText.includes("font-claude-response") || testId.includes("assistant")
          ? "assistant"
          : "assistant";

    const html = sanitizeHtml(node.innerHTML || node.outerHTML);
    const text = stripHtml(html).replace(/\s+/g, " ").trim();
    if (!text) {
      continue;
    }

    if (currentRole && role !== currentRole && currentParts.length) {
      grouped.push({
        id: `claude-${grouped.length}`,
        role: currentRole,
        label: roleLabel(currentRole),
        html: currentParts.join(""),
      });
      currentParts = [];
    }

    currentRole = role;
    currentParts.push(html);
  }

  if (currentRole && currentParts.length) {
    grouped.push({
      id: `claude-${grouped.length}`,
      role: currentRole,
      label: roleLabel(currentRole),
      html: currentParts.join(""),
    });
  }

  return grouped;
}

function extractTranscriptFallback(doc: Document): ConversationMessage[] {
  const bodyText = cleanTranscriptText((doc.body?.innerText || doc.body?.textContent || "").replace(/\r/g, "").trim());
  if (!bodyText) return [];

  const normalized = bodyText
    .replace(/\n{3,}/g, "\n\n")
    .replace(/(^|\n)\s*(Human|User|You)\s*:/gi, "$1[[USER]] ")
    .replace(/(^|\n)\s*(Assistant|Claude|AI)\s*:/gi, "$1[[ASSISTANT]] ")
    .replace(/(^|\n)\s*(System)\s*:/gi, "$1[[SYSTEM]] ");

  if (!normalized.includes("[[USER]]") && !normalized.includes("[[ASSISTANT]]") && !normalized.includes("[[SYSTEM]]")) {
    return [];
  }

  const parts = normalized.split(/(\[\[(?:USER|ASSISTANT|SYSTEM)\]\])/g).filter(Boolean);
  const messages: ConversationMessage[] = [];
  let currentRole: "user" | "assistant" | "system" | null = null;
  let buffer = "";

  for (const part of parts) {
    if (part === "[[USER]]" || part === "[[ASSISTANT]]" || part === "[[SYSTEM]]") {
      if (currentRole && buffer.trim()) {
        messages.push({
          id: `fallback-${messages.length}`,
          role: currentRole,
          label: roleLabel(currentRole),
          html: textBlockToHtml(buffer),
        });
      }
      currentRole = part === "[[USER]]" ? "user" : part === "[[SYSTEM]]" ? "system" : "assistant";
      buffer = "";
      continue;
    }
    buffer += `${buffer ? "\n" : ""}${part}`;
  }

  if (currentRole && buffer.trim()) {
    messages.push({
      id: `fallback-${messages.length}`,
      role: currentRole,
      label: roleLabel(currentRole),
      html: textBlockToHtml(buffer),
    });
  }

  return messages;
}

function cleanTranscriptText(text: string) {
  return text
    .replace(/\b(AI Radar|Admin|Dashboard|Signals|Radar Summary|Agent Watch|Friction Signals|Reflections|Saved Backlog|Workspace|Manual Upload|Share|Claude is AI and can make mistakes\.)\b/g, "")
    .replace(/\b(Opus 4\.6|Sonnet 4\.6|Use voice mode|Open sidebar|Content)\b/g, "")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function textBlockToHtml(text: string) {
  return escapeHtml(text.trim())
    .replace(/\n{2,}/g, "</p><p>")
    .replace(/\n/g, "<br />")
    .replace(/^/, "<p>")
    .replace(/$/, "</p>");
}

function escapeHtml(text: string) {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function detectRole(node: Element): "user" | "assistant" | "system" | null {
  const attr = node.getAttribute("data-message-author-role");
  if (attr) return normalizeRole(attr);
  const classText = `${node.className || ""}`.toLowerCase();
  const text = (node.textContent || "").trim().toLowerCase();
  if (classText.includes("assistant") || text.startsWith("assistant:") || text.startsWith("claude:")) return "assistant";
  if (classText.includes("user") || classText.includes("human") || text.startsWith("user:") || text.startsWith("human:")) return "user";
  if (classText.includes("system") || text.startsWith("system:")) return "system";
  return null;
}

function normalizeRole(value: string): "user" | "assistant" | "system" {
  const normalized = value.trim().toLowerCase();
  if (normalized.includes("user") || normalized.includes("human")) return "user";
  if (normalized.includes("system")) return "system";
  return "assistant";
}

function roleLabel(role: "user" | "assistant" | "system") {
  if (role === "user") return "You";
  if (role === "system") return "System";
  return "Assistant";
}

function stripRoleLabel(html: string) {
  return html.replace(/^\s*(User|Human|Assistant|Claude|System)\s*:\s*/i, "");
}

function sanitizeHtml(html: string) {
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, "")
    .replace(/<style[\s\S]*?<\/style>/gi, "")
    .replace(/\son\w+="[^"]*"/gi, "")
    .replace(/\son\w+='[^']*'/gi, "");
}

function stripHtml(html: string) {
  return html.replace(/<[^>]+>/g, " ");
}

function StructuredBlock({ label, value }: { label: string; value: string }) {
  return (
    <div style={blockStyle}>
      <div style={blockLabelStyle}>{label}</div>
      <div style={{ color: "var(--app-text-muted)", lineHeight: 1.75 }}>{value}</div>
    </div>
  );
}

function StructuredListBlock({ label, items, emptyLabel }: { label: string; items: string[]; emptyLabel: string }) {
  return (
    <div style={blockStyle}>
      <div style={blockLabelStyle}>{label}</div>
      {items.length ? (
        <ul style={{ margin: 0, paddingLeft: "18px", color: "var(--app-text-muted)", lineHeight: 1.75 }}>
          {items.map((item, index) => (
            <li key={`${label}-${index}`}>{item}</li>
          ))}
        </ul>
      ) : (
        <div style={{ color: "var(--app-text-muted)" }}>{emptyLabel}</div>
      )}
    </div>
  );
}

const heroStyle = { display: "grid", gap: "18px", padding: "28px", borderRadius: "26px", border: "1px solid var(--app-surface-border)", background: "var(--app-surface-bg)", boxShadow: "var(--app-surface-shadow)", marginBottom: "20px" } as const;
const heroTopStyle = { display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "18px", flexWrap: "wrap" } as const;
const eyebrowStyle = { fontSize: "12px", fontWeight: 800, letterSpacing: ".08em", textTransform: "uppercase", color: "var(--app-success-fg)" } as const;
const titleStyle = { margin: 0, fontSize: "36px", lineHeight: 1.08, color: "var(--app-text-strong)" } as const;
const subtleStyle = { color: "var(--app-text-muted)", fontSize: "15px", lineHeight: 1.7 } as const;
const actionRowStyle = { display: "flex", gap: "10px", flexWrap: "wrap" } as const;
const chipRowStyle = { display: "flex", gap: "8px", flexWrap: "wrap" } as const;
const chipStyle = { display: "inline-flex", alignItems: "center", padding: "6px 10px", borderRadius: "999px", background: "var(--app-info-bg)", border: "1px solid var(--app-info-border)", color: "var(--app-info-fg)", fontSize: "13px", fontWeight: 600 } as const;
const mutedChipStyle = { display: "inline-flex", alignItems: "center", padding: "6px 10px", borderRadius: "999px", background: "var(--app-chip-bg)", border: "1px solid var(--app-chip-border)", color: "var(--app-chip-fg)", fontSize: "13px", fontWeight: 600 } as const;
const statGridStyle = { display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(150px,1fr))", gap: "12px" } as const;
const statCardStyle = { padding: "16px", borderRadius: "18px", border: "1px solid var(--app-surface-border)", background: "var(--app-surface-muted-bg)", display: "grid", gap: "6px" } as const;
const statLabelStyle = { fontSize: "12px", textTransform: "uppercase", letterSpacing: ".06em", fontWeight: 800, color: "var(--app-text-subtle)" } as const;
const statValueStyle = { fontSize: "28px", fontWeight: 800, color: "var(--app-text-strong)", lineHeight: 1.05 } as const;
const metaGridStyle = { display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(170px,1fr))", gap: "12px" } as const;
const metaItemStyle = { padding: "14px 16px", borderRadius: "16px", border: "1px solid var(--app-surface-border)", background: "var(--app-surface-muted-bg)", display: "grid", gap: "4px" } as const;
const metaLabelStyle = { fontSize: "12px", fontWeight: 800, letterSpacing: ".05em", textTransform: "uppercase", color: "var(--app-text-subtle)" } as const;
const metaValueStyle = { fontSize: "15px", fontWeight: 700, color: "var(--app-text-strong)" } as const;
const boundaryGridStyle = { display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))", gap: "12px" } as const;
const boundaryItemStyle = { border: "1px solid var(--app-surface-border)", borderRadius: "14px", background: "var(--app-surface-muted-bg)", padding: "14px", display: "grid", gap: "7px", color: "var(--app-text-muted)", fontSize: "14px", lineHeight: 1.55 } as const;
const tabRowStyle = { display: "flex", gap: "10px", flexWrap: "wrap" } as const;
const viewControlRowStyle = { display: "flex", justifyContent: "space-between", alignItems: "center", gap: "12px", flexWrap: "wrap" } as const;
const expandActionRowStyle = { display: "flex", gap: "8px", flexWrap: "wrap" } as const;
const leadStyle = { color: "var(--app-text-muted)", fontSize: "14px", lineHeight: 1.8, maxWidth: "840px" } as const;
const contentCardStyle = { padding: "20px", borderRadius: "20px", background: "var(--app-surface-muted-bg)", border: "1px solid var(--app-surface-border)" } as const;
const contentStyle = { whiteSpace: "pre-wrap" as const, color: "var(--app-text-muted)", lineHeight: 1.85, fontSize: "15px" };
const emptyStyle = { padding: "18px 20px", borderRadius: "18px", background: "var(--app-surface-muted-bg)", border: "1px dashed var(--app-surface-strong-border)", color: "var(--app-text-muted)", lineHeight: 1.7 } as const;
const collapsedPanelStyle = { maxHeight: "240px", overflow: "hidden" as const, position: "relative" as const } as const;
const collapsedHintStyle = { padding: "12px 14px", borderRadius: "14px", border: "1px dashed var(--app-surface-strong-border)", background: "var(--app-surface-muted-bg)", color: "var(--app-text-muted)", fontSize: "13px", lineHeight: 1.6 } as const;
const messageCardStyle = { display: "grid", gap: "12px", padding: "20px 22px", borderRadius: "24px", border: "1px solid var(--app-surface-border)", boxShadow: "var(--app-surface-shadow)", position: "relative" as const, overflow: "hidden" as const };
const messageLabelStyle = { fontSize: "11px", fontWeight: 900, color: "var(--app-text-subtle)", letterSpacing: ".08em", textTransform: "uppercase" } as const;
const messageHeaderStyle = { display: "flex", alignItems: "center", justifyContent: "space-between", gap: "12px", paddingBottom: "8px", borderBottom: "1px solid rgba(148, 163, 184, 0.15)" } as const;
const messageIndexStyle = { fontSize: "11px", fontWeight: 800, color: "var(--app-text-subtle)", letterSpacing: ".05em" } as const;
const messageBodyStyle = { color: "var(--app-text-muted)", lineHeight: 1.85, fontSize: "15px" } as const;
const conversationShellStyle = { display: "grid", gap: "18px", padding: "18px 10px 10px", background: "var(--app-surface-muted-bg)", borderRadius: "28px", border: "1px solid var(--app-surface-border)", boxShadow: "var(--app-surface-shadow)" } as const;
const conversationRowStyle = { display: "flex", alignItems: "flex-end", gap: "14px", padding: "0 16px" } as const;
const avatarStyle = { display: "inline-flex", alignItems: "center", justifyContent: "center", width: "42px", height: "42px", borderRadius: "999px", color: "var(--app-primary-action-fg)", fontSize: "12px", fontWeight: 800, flexShrink: 0, boxShadow: "var(--app-surface-shadow)", border: "1px solid var(--app-surface-border)" } as const;
const backfillCollapsedNoticeStyle = { display: "flex", alignItems: "center", justifyContent: "space-between", gap: "12px", flexWrap: "wrap", padding: "12px 14px", borderRadius: "8px", border: "1px dashed var(--app-surface-strong-border)", background: "var(--app-surface-muted-bg)", color: "var(--app-text-muted)", fontSize: "13px", lineHeight: 1.6 } as const;
const sourceArtifactShellStyle = { display: "grid", gap: "12px", border: "1px solid var(--app-surface-border)", borderRadius: "8px", background: "var(--app-surface-muted-bg)", padding: "14px", boxShadow: "var(--app-surface-shadow)" } as const;
const sourceArtifactHeaderStyle = { display: "flex", alignItems: "center", justifyContent: "space-between", gap: "12px", flexWrap: "wrap", padding: "2px 2px 4px" } as const;
const sourceArtifactEyebrowStyle = { color: "var(--app-text-subtle)", fontSize: "12px", fontWeight: 800, textTransform: "uppercase", letterSpacing: "0" } as const;
const sourceArtifactTitleStyle = { marginTop: "4px", color: "var(--app-text-strong)", fontSize: "18px", fontWeight: 800, lineHeight: 1.2 } as const;
const sourceArtifactMetaStyle = { border: "1px solid var(--app-surface-border)", borderRadius: "999px", background: "var(--app-chip-bg)", color: "var(--app-chip-fg)", padding: "6px 10px", fontSize: "12px", fontWeight: 750 } as const;
const iframeStyle = { width: "100%", minHeight: "780px", borderRadius: "8px", border: "1px solid var(--app-surface-border)", background: "var(--app-surface-bg)" } as const;
const twoColStyle = { display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(320px,1fr))", gap: "20px" } as const;
const connectionBoundaryStyle = { marginBottom: "12px", padding: "12px 14px", borderRadius: "14px", border: "1px solid var(--app-surface-border)", background: "var(--app-surface-muted-bg)", color: "var(--app-text-muted)", fontSize: "13px", lineHeight: 1.65 } as const;
const listCardStyle = { display: "grid", gap: "10px", padding: "16px", borderRadius: "18px", border: "1px solid var(--app-surface-border)", background: "var(--app-surface-muted-bg)" } as const;
const listTitleStyle = { fontWeight: 700, color: "var(--app-text-strong)" } as const;
const listMetaStyle = { color: "var(--app-text-muted)", fontSize: "14px" } as const;
const manualIntentRowStyle = { display: "flex", gap: "8px", flexWrap: "wrap" as const, alignItems: "center", color: "var(--app-text-muted)", fontSize: "13px", lineHeight: 1.5 } as const;
const manualSessionLinkStyle = { color: "var(--app-info-fg)", fontWeight: 800, textDecoration: "underline" } as const;
const errorStyle = { marginBottom: "16px", padding: "14px 16px", borderRadius: "12px", background: "var(--app-danger-bg)", color: "var(--app-danger-fg)", border: "1px solid var(--app-danger-border)" } as const;
const primaryButtonStyle = { display: "inline-flex", alignItems: "center", justifyContent: "center", padding: "11px 16px", borderRadius: "12px", background: "var(--app-primary-action-bg)", color: "var(--app-primary-action-fg)", textDecoration: "none", fontWeight: 700, border: "1px solid var(--app-primary-action-border)" } as const;
const secondaryButtonStyle = { display: "inline-flex", alignItems: "center", justifyContent: "center", padding: "11px 16px", borderRadius: "12px", background: "var(--app-secondary-action-bg)", color: "var(--app-text-strong)", textDecoration: "none", fontWeight: 700, border: "1px solid var(--app-surface-border)" } as const;
const blockStyle = { border: "1px solid var(--app-surface-border)", borderRadius: "16px", background: "var(--app-surface-muted-bg)", padding: "16px 18px" } as const;
const blockLabelStyle = { fontSize: "12px", fontWeight: 800, color: "var(--app-text-subtle)", textTransform: "uppercase", letterSpacing: ".4px", marginBottom: "8px" } as const;
const patchBlockStyle = { margin: 0, whiteSpace: "pre-wrap" as const, color: "var(--app-text-muted)", lineHeight: 1.75, fontSize: "13px", fontFamily: 'Consolas, Monaco, "Courier New", monospace' } as const;
const conversationRichTextCss = `
  .reflection-conversation-body {
    word-break: break-word;
    overflow-wrap: anywhere;
  }
  .reflection-conversation-body > * + * {
    margin-top: 0.8em;
  }
  .reflection-conversation-body p { margin: 0 0 0.95em; }
  .reflection-conversation-body p:last-child { margin-bottom: 0; }
  .reflection-conversation-body h1,
  .reflection-conversation-body h2,
  .reflection-conversation-body h3,
  .reflection-conversation-body h4 {
    margin: 0 0 0.7em;
    line-height: 1.3;
    color: var(--app-text-strong);
  }
  .reflection-conversation-body ul,
  .reflection-conversation-body ol { margin: 0.6em 0 0.95em; padding-left: 1.35em; }
  .reflection-conversation-body li { margin: 0.32em 0; }
  .reflection-conversation-body [class*="flex"],
  .reflection-conversation-body [style*="display:flex"],
  .reflection-conversation-body [style*="display: flex"],
  .reflection-conversation-body [class*="grid"],
  .reflection-conversation-body [style*="display:grid"],
  .reflection-conversation-body [style*="display: grid"] {
    display: block !important;
  }
  .reflection-conversation-body [class*="justify-between"],
  .reflection-conversation-body [class*="justify-around"],
  .reflection-conversation-body [class*="justify-evenly"],
  .reflection-conversation-body [class*="items-center"] {
    justify-content: flex-start !important;
    align-items: flex-start !important;
  }
  .reflection-conversation-body span {
    white-space: normal;
  }
  .reflection-conversation-body blockquote {
    margin: 1em 0;
    padding: 12px 14px;
    border-left: 4px solid var(--app-surface-strong-border);
    background: var(--app-surface-bg);
    border-radius: 0 12px 12px 0;
    color: var(--app-text-muted);
  }
  .reflection-conversation-body pre {
    margin: 1em 0;
    padding: 14px 16px;
    border-radius: 16px;
    background: var(--app-surface-bg);
    color: var(--app-text-muted);
    overflow: auto;
    font: 13px/1.65 Consolas, "Courier New", monospace;
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.04);
  }
  .reflection-conversation-body code {
    font-family: Consolas, "Courier New", monospace;
  }
  .reflection-conversation-body :not(pre) > code {
    background: rgba(15, 23, 42, 0.07);
    padding: 2px 6px;
    border-radius: 8px;
    color: var(--app-text-strong);
    font-size: 0.92em;
  }
  .reflection-conversation-body table {
    width: 100%;
    border-collapse: collapse;
    margin: 1em 0;
    overflow: hidden;
    border-radius: 14px;
  }
  .reflection-conversation-body th,
  .reflection-conversation-body td {
    border: 1px solid var(--app-surface-border);
    padding: 10px 12px;
    vertical-align: top;
    text-align: left;
  }
  .reflection-conversation-body th {
    background: var(--app-surface-bg);
    font-weight: 700;
  }
  .reflection-conversation-body img {
    max-width: 100%;
    height: auto;
    border-radius: 16px;
    margin: 10px 0;
    border: 1px solid var(--app-surface-border);
    box-shadow: 0 10px 24px rgba(15, 23, 42, 0.08);
  }
  .reflection-conversation-body hr {
    border: 0;
    border-top: 1px solid var(--app-surface-border);
    margin: 1.2em 0;
  }
`;
function tabStyle(active: boolean) {
  return {
    padding: "10px 14px",
    borderRadius: "12px",
    border: active ? "1px solid var(--app-info-border)" : "1px solid var(--app-surface-border)",
    background: active ? "var(--app-info-bg)" : "var(--app-secondary-action-bg)",
    color: active ? "var(--app-info-fg)" : "var(--app-text-strong)",
    fontWeight: 700,
    cursor: "pointer",
  } as const;
}

function utilityButtonStyle(active: boolean) {
  return {
    padding: "10px 14px",
    borderRadius: "12px",
    border: active ? "1px solid var(--app-info-border)" : "1px solid var(--app-surface-border)",
    background: active ? "var(--app-info-bg)" : "var(--app-secondary-action-bg)",
    color: active ? "var(--app-info-fg)" : "var(--app-text-strong)",
    fontWeight: 700,
    cursor: "pointer",
    opacity: active ? 1 : 0.96,
  } as const;
}

