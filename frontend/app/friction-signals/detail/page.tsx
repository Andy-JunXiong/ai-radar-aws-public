"use client";

import type { CSSProperties } from "react";
import { Suspense, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import AppContainer from "@/components/AppContainer";
import PageHeader from "@/components/PageHeader";
import SectionCard from "@/components/SectionCard";
import { apiUrl } from "@/lib/api";
import { adminFetch } from "@/lib/adminAuth";
import { cleanDisplayList, cleanDisplayText } from "@/lib/displayText";

type FrictionDetail = {
  entity_id?: string | null;
  found?: boolean;
  message?: string;
  title?: string;
  url?: string;
  source?: string;
  published_at?: string;
  summary?: string;
  friction_subtopic?: string;
  friction_score?: number | string | null;
  pain_severity_score?: number | string | null;
  ecosystem_relevance_score?: number | string | null;
  repo_name?: string;
  matched_keywords?: string[];
  profile?: {
    problem_summary?: string;
    why_this_matters?: string;
    who_is_affected?: string;
    product_opportunity?: string;
    suggested_response?: string[];
    confidence?: string;
    provider_used?: string;
    model_used?: string;
  };
  related_signals?: Array<{
    title?: string;
    source?: string;
    published_at?: string;
    friction_score?: number | string | null;
    pain_severity_score?: number | string | null;
    ecosystem_relevance_score?: number | string | null;
  }>;
};

type FrictionDetailTranslation = {
  title?: string;
  summary?: string;
  friction_subtopic?: string;
  profile?: {
    problem_summary?: string;
    why_this_matters?: string;
    who_is_affected?: string;
    product_opportunity?: string;
    suggested_response?: string[];
  };
  matched_keywords?: string[];
  related_signals?: Array<{
    title?: string;
    source?: string;
  }>;
};

const FRICTION_TRANSLATION_STORAGE_KEY = "frictionSignalTranslations";

function readStoredTranslation(entityId: string): FrictionDetailTranslation | null {
  if (typeof window === "undefined" || !entityId) return null;
  try {
    const raw = window.sessionStorage.getItem(FRICTION_TRANSLATION_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    const current = parsed?.[entityId];
    return current?.translatedFields ?? null;
  } catch {
    return null;
  }
}

function writeStoredDetailLanguage(entityId: string, translation: FrictionDetailTranslation | null, showChinese: boolean) {
  if (typeof window === "undefined" || !entityId) return;
  try {
    const raw = window.sessionStorage.getItem(FRICTION_TRANSLATION_STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : {};
    parsed[entityId] = {
      ...(parsed[entityId] || {}),
      translatedFields: translation || parsed[entityId]?.translatedFields,
      showChinese,
      error: "",
    };
    window.sessionStorage.setItem(FRICTION_TRANSLATION_STORAGE_KEY, JSON.stringify(parsed));
  } catch {
    // Ignore storage errors and keep UI usable.
  }
}

function scoreLabel(value: number | string | null | undefined) {
  if (value === null || value === undefined || value === "") return "N/A";
  return String(value);
}

function compactDateLabel(value?: string | null) {
  if (!value) return "N/A";
  const parsed = Date.parse(value);
  if (Number.isNaN(parsed)) return "N/A";
  return new Intl.DateTimeFormat("en-AU", {
    year: "numeric",
    month: "short",
    day: "numeric",
  }).format(new Date(parsed));
}

export default function FrictionSignalDetailPage() {
  return (
    <Suspense fallback={<FrictionSignalDetailSkeleton />}>
      <FrictionSignalDetailPageContent />
    </Suspense>
  );
}

function FrictionSignalDetailPageContent() {
  const searchParams = useSearchParams();
  const entityId = searchParams.get("entity_id") || "";
  const initialLanguage = searchParams.get("lang") === "zh" ? "zh" : "en";
  const [payload, setPayload] = useState<FrictionDetail | null>(null);
  const [loadError, setLoadError] = useState("");
  const [translation, setTranslation] = useState<FrictionDetailTranslation | null>(() =>
    entityId ? readStoredTranslation(entityId) : null,
  );
  const [translationError, setTranslationError] = useState("");
  const [translationLoading, setTranslationLoading] = useState(false);
  const [language, setLanguage] = useState<"en" | "zh">(initialLanguage);

  useEffect(() => {
    if (!entityId) return;
    adminFetch(apiUrl(`/radar/friction-signals/detail?entity_id=${encodeURIComponent(entityId)}`))
      .then((res) => res.json())
      .then((data) => {
        setPayload(data);
        setLoadError("");
      })
      .catch(() => setLoadError("Failed to load friction signal detail."));
  }, [entityId]);

  useEffect(() => {
    if (language !== "zh" || !entityId || translation || translationLoading) return;

    let active = true;

    async function loadTranslation() {
      setTranslationLoading(true);
      setTranslationError("");

      try {
        const res = await adminFetch(
          apiUrl(`/radar/friction-signals/detail/translate?entity_id=${encodeURIComponent(entityId)}`),
        );
        const data = await res.json();
        if (!res.ok) {
          throw new Error(cleanDisplayText(data?.detail || data?.message) || "Translation failed.");
        }
        const translated = data?.translated || null;
        if (!active) return;
        setTranslation(translated);
        writeStoredDetailLanguage(entityId, translated, true);
      } catch (error) {
        if (!active) return;
        const message =
          error instanceof Error && cleanDisplayText(error.message)
            ? cleanDisplayText(error.message)
            : "Translation failed.";
        setTranslationError(message);
        setLanguage("en");
        writeStoredDetailLanguage(entityId, translation, false);
      } finally {
        if (active) {
          setTranslationLoading(false);
        }
      }
    }

    void loadTranslation();

    return () => {
      active = false;
    };
  }, [entityId, language, translation, translationLoading]);

  const relatedSignals = useMemo(
    () => (Array.isArray(payload?.related_signals) ? payload.related_signals : []),
    [payload],
  );

  if (!entityId) {
    return (
      <AppContainer>
        <div style={{ color: "var(--app-text-muted)" }}>Missing friction detail target.</div>
      </AppContainer>
    );
  }

  if (!payload) {
    return (
      <AppContainer>
        <div style={{ color: "var(--app-text-muted)" }}>Loading friction signal detail...</div>
      </AppContainer>
    );
  }

  if (payload.found === false) {
    return (
      <AppContainer>
        <PageHeader title="Friction Signal Detail" description={payload.message || "Signal detail not found."} />
        <Link href="/friction-signals" style={{ color: "var(--app-info-fg)", textDecoration: "none", fontWeight: 700 }}>
          Back to Friction Signals
        </Link>
      </AppContainer>
    );
  }

  const profile = payload.profile;
  const translatedProfile = translation?.profile;
  const showChinese = language === "zh" && Boolean(translation);
  const insightReady = Boolean(
    profile?.problem_summary || profile?.why_this_matters || profile?.product_opportunity,
  );
  const decisionBits = [
    cleanDisplayText(showChinese ? translatedProfile?.who_is_affected : profile?.who_is_affected),
    cleanDisplayText(showChinese ? translatedProfile?.product_opportunity : profile?.product_opportunity),
    payload.pain_severity_score ? `Pain severity ${scoreLabel(payload.pain_severity_score)}` : "",
    payload.ecosystem_relevance_score ? `Ecosystem relevance ${scoreLabel(payload.ecosystem_relevance_score)}` : "",
  ].filter(Boolean);

  return (
    <AppContainer>
      <div style={{ display: "flex", justifyContent: "space-between", gap: "16px", flexWrap: "wrap", marginBottom: "20px" }}>
        <div>
          <PageHeader
            title={cleanDisplayText(showChinese ? translation?.title : payload.title) || cleanDisplayText(payload.repo_name) || "Tracked Friction Signal"}
            description={cleanDisplayText(showChinese ? translation?.summary : payload.summary) || "AI ecosystem pain signal detail"}
            marginBottom="10px"
          />
          <div style={{ color: "var(--app-text-muted)", fontSize: "14px" }}>
            {cleanDisplayText(showChinese ? translation?.friction_subtopic : payload.friction_subtopic) || "general_friction"} · {cleanDisplayText(payload.source) || "unknown"}
          </div>
          <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", marginTop: "10px" }}>
            <span style={insightReady ? readyBadgeStyle : pendingBadgeStyle}>
              {insightReady ? "LLM Insight Ready" : "Insight Pending"}
            </span>
          </div>
        </div>
        <div style={{ display: "flex", gap: "12px", alignItems: "flex-start", flexWrap: "wrap" }}>
          <Link href="/friction-signals" style={buttonLinkStyle}>
            Back
          </Link>
          {showChinese ? (
            <button
              type="button"
              onClick={() => {
                setLanguage("en");
                writeStoredDetailLanguage(entityId, translation, false);
              }}
              style={buttonActionStyle}
            >
              English
            </button>
          ) : (
            <button
              type="button"
              onClick={() => {
                setLanguage("zh");
                writeStoredDetailLanguage(entityId, translation, true);
              }}
              style={buttonActionStyle}
            >
              {translationLoading ? "Translating..." : "中文"}
            </button>
          )}
          {payload.url ? (
            <a href={payload.url} target="_blank" rel="noreferrer" style={buttonLinkStyle}>
              Open Discussion
            </a>
          ) : null}
        </div>
      </div>

      {loadError ? <div style={messagePanelStyle}>{loadError}</div> : null}
      {translationError ? <div style={messagePanelStyle}>{translationError}</div> : null}

      <SectionCard title="Signal Snapshot">
        <div style={metricsGridStyle}>
          <Metric label="Friction score" value={scoreLabel(payload.friction_score)} />
          <Metric label="Pain severity" value={scoreLabel(payload.pain_severity_score)} />
          <Metric label="Relevance" value={scoreLabel(payload.ecosystem_relevance_score)} />
          <Metric label="Published" value={compactDateLabel(payload.published_at)} />
          <Metric label="Source" value={cleanDisplayText(payload.source) || "N/A"} />
          <Metric label="Repo" value={cleanDisplayText(payload.repo_name) || "N/A"} />
        </div>
        <div style={{ marginTop: "16px", color: "var(--app-text-muted)", lineHeight: 1.8 }}>
          {cleanDisplayText(showChinese ? translation?.summary : payload.summary) || "No friction summary available yet."}
        </div>
      </SectionCard>

      <SectionCard title="Why This Pain May Matter To Product Strategy">
        <div style={{ display: "grid", gap: "14px" }}>
          <DecisionBlock
            label="Quick read"
            value={
              cleanDisplayText(showChinese ? translatedProfile?.why_this_matters : profile?.why_this_matters) ||
              cleanDisplayText(showChinese ? translatedProfile?.problem_summary : profile?.problem_summary) ||
              "No decision-oriented interpretation generated yet."
            }
          />
          <div style={decisionGridStyle}>
            <DecisionCard
              label="Who feels this pain"
              value={cleanDisplayText(showChinese ? translatedProfile?.who_is_affected : profile?.who_is_affected) || "Affected audience not identified yet."}
            />
            <DecisionCard
              label="Opportunity implied"
              value={cleanDisplayText(showChinese ? translatedProfile?.product_opportunity : profile?.product_opportunity) || "No product opportunity surfaced yet."}
            />
            <DecisionCard
              label="Suggested response"
              value={
                cleanDisplayText(showChinese ? translatedProfile?.suggested_response?.[0] : profile?.suggested_response?.[0]) ||
                "No suggested response generated yet."
              }
            />
          </div>
          {decisionBits.length ? (
            <div style={decisionStripStyle}>
              {decisionBits.map((bit, index) => (
                <span key={`${bit}-${index}`}>{bit}</span>
              ))}
            </div>
          ) : null}
        </div>
      </SectionCard>

      <SectionCard title="Why This Pain Matters">
        <div style={{ display: "grid", gap: "14px" }}>
          <InsightBlock
            label="Pain signal"
            value={
              cleanDisplayText(showChinese ? translation?.summary : payload.summary) ||
              "This friction signal highlights a problem worth investigating in the current AI ecosystem."
            }
          />
          <InsightBlock
            label="Subtopic"
            value={
              cleanDisplayText(showChinese ? translation?.friction_subtopic : payload.friction_subtopic)
                ? `This issue currently clusters under ${cleanDisplayText(showChinese ? translation?.friction_subtopic : payload.friction_subtopic)}.`
                : "This issue has not been assigned to a more specific friction subtopic yet."
            }
          />
          <InsightBlock
            label="Interpretation"
            value={
              payload.pain_severity_score || payload.ecosystem_relevance_score
                ? `Pain severity ${scoreLabel(payload.pain_severity_score)} and ecosystem relevance ${scoreLabel(payload.ecosystem_relevance_score)} suggest how serious and how widely applicable this issue may be.`
                : "Severity and relevance have not been fully populated for this signal yet."
            }
          />
        </div>
      </SectionCard>

      <SectionCard title="LLM Interpretation">
        {profile ? (
          <div style={{ display: "grid", gap: "14px" }}>
            <InsightBlock
              label="Problem summary"
              value={cleanDisplayText(showChinese ? translatedProfile?.problem_summary : profile.problem_summary) || "No LLM problem summary generated yet."}
            />
            <InsightBlock
              label="Why this matters"
              value={cleanDisplayText(showChinese ? translatedProfile?.why_this_matters : profile.why_this_matters) || "No LLM interpretation generated yet."}
            />
            <InsightBlock
              label="Who is affected"
              value={cleanDisplayText(showChinese ? translatedProfile?.who_is_affected : profile.who_is_affected) || "No affected audience generated yet."}
            />
            <InsightBlock
              label="Product opportunity"
              value={cleanDisplayText(showChinese ? translatedProfile?.product_opportunity : profile.product_opportunity) || "No product opportunity generated yet."}
            />
            <div style={{ display: "grid", gap: "8px" }}>
              <div style={smallSectionTitleStyle}>Suggested response</div>
              {Array.isArray(profile.suggested_response) && profile.suggested_response.length ? (
                <div style={{ display: "grid", gap: "8px" }}>
                  {cleanDisplayList(showChinese ? translatedProfile?.suggested_response || [] : profile.suggested_response).map((item, index) => (
                    <div key={`${item}-${index}`} style={suggestedResponseStyle}>
                      {item}
                    </div>
                  ))}
                </div>
              ) : (
                <div style={{ color: "var(--app-text-muted)" }}>No suggested response generated yet.</div>
              )}
            </div>
            <div style={{ color: "var(--app-text-muted)", fontSize: "13px" }}>
              Confidence: {cleanDisplayText(profile.confidence) || "N/A"}
              {(profile.provider_used || profile.model_used)
                ? ` · ${cleanDisplayText(profile.provider_used) || "provider"}${profile.model_used ? ` / ${cleanDisplayText(profile.model_used)}` : ""}`
                : ""}
            </div>
          </div>
        ) : (
          <div style={{ color: "var(--app-text-muted)" }}>No LLM interpretation generated yet.</div>
        )}
      </SectionCard>

      <SectionCard title="Matched Keywords">
        {Array.isArray(showChinese ? translation?.matched_keywords : payload.matched_keywords) && (showChinese ? translation?.matched_keywords : payload.matched_keywords)?.length ? (
          <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
            {cleanDisplayList(showChinese ? translation?.matched_keywords || [] : payload.matched_keywords || []).map((keyword) => (
              <span key={keyword} style={keywordStyle}>
                {keyword}
              </span>
            ))}
          </div>
        ) : (
          <div style={{ color: "var(--app-text-muted)" }}>No matched keywords available.</div>
        )}
      </SectionCard>

      <SectionCard title="Related Signals">
        {relatedSignals.length ? (
          <div style={{ display: "grid", gap: "10px" }}>
            {relatedSignals.map((item, index) => (
              <div key={`${item.title || "friction"}-${index}`} style={historyRowStyle}>
                <div>
                  <div style={{ color: "var(--app-text-strong)", fontWeight: 700 }}>
                    {cleanDisplayText(showChinese ? translation?.related_signals?.[index]?.title : item.title) || "Untitled friction signal"}
                  </div>
                  <div style={{ color: "var(--app-text-muted)", fontSize: "13px" }}>
                    {cleanDisplayText(showChinese ? translation?.related_signals?.[index]?.source : item.source) || "unknown"} · {compactDateLabel(item.published_at)}
                  </div>
                </div>
                <div style={{ color: "var(--app-text-strong)", fontWeight: 700 }}>Score {scoreLabel(item.friction_score)}</div>
                <div style={{ color: "var(--app-text-muted)" }}>
                  Pain {scoreLabel(item.pain_severity_score)} · Relevance {scoreLabel(item.ecosystem_relevance_score)}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div style={{ color: "var(--app-text-muted)" }}>No related friction signals available.</div>
        )}
      </SectionCard>
    </AppContainer>
  );
}

function FrictionSignalDetailSkeleton() {
  return (
    <AppContainer>
      <div style={{ color: "var(--app-text-muted)" }}>Loading friction signal detail...</div>
    </AppContainer>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div style={metricCardStyle}>
      <div style={{ color: "var(--app-text-subtle)", fontSize: "12px", textTransform: "uppercase" }}>{label}</div>
      <div style={{ color: "var(--app-text-strong)", fontWeight: 800, fontSize: "24px", lineHeight: 1.1 }}>{value}</div>
    </div>
  );
}

function InsightBlock({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: "grid", gap: "6px" }}>
      <div style={{ color: "var(--app-warning-fg)", fontSize: "12px", fontWeight: 700, textTransform: "uppercase" }}>{label}</div>
      <div style={{ color: "var(--app-text-muted)", lineHeight: 1.8 }}>{value}</div>
    </div>
  );
}

function DecisionBlock({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: "grid", gap: "6px" }}>
      <div style={{ color: "var(--app-success-fg)", fontSize: "12px", fontWeight: 700, textTransform: "uppercase" }}>{label}</div>
      <div style={{ color: "var(--app-text-muted)", lineHeight: 1.8 }}>{value}</div>
    </div>
  );
}

function DecisionCard({ label, value }: { label: string; value: string }) {
  return (
    <div style={decisionCardStyle}>
      <div style={{ color: "var(--app-success-fg)", fontSize: "12px", fontWeight: 700, textTransform: "uppercase" }}>{label}</div>
      <div style={{ color: "var(--app-text-muted)", lineHeight: 1.7 }}>{value}</div>
    </div>
  );
}

const buttonLinkStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  padding: "10px 14px",
  borderRadius: "12px",
  border: "1px solid var(--app-surface-border)",
  background: "var(--app-secondary-action-bg)",
  color: "var(--app-text-strong)",
  fontWeight: 600,
  textDecoration: "none",
};

const buttonActionStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  padding: "10px 14px",
  borderRadius: "12px",
  border: "1px solid var(--app-warning-border)",
  background: "var(--app-warning-bg)",
  color: "var(--app-warning-fg)",
  fontWeight: 600,
  cursor: "pointer",
};

const messagePanelStyle: CSSProperties = {
  marginBottom: "16px",
  padding: "12px 14px",
  borderRadius: "12px",
  background: "var(--app-info-bg)",
  border: "1px solid var(--app-info-border)",
  color: "var(--app-info-fg)",
  fontSize: "14px",
};

const metricsGridStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))",
  gap: "12px",
};

const metricCardStyle: CSSProperties = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "14px",
  padding: "14px 16px",
  background: "var(--app-surface-muted-bg)",
  display: "grid",
  gap: "8px",
};

const decisionGridStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
  gap: "12px",
};

const decisionCardStyle: CSSProperties = {
  border: "1px solid var(--app-success-border)",
  borderRadius: "14px",
  padding: "14px 16px",
  background: "var(--app-success-bg)",
  display: "grid",
  gap: "8px",
};

const decisionStripStyle: CSSProperties = {
  display: "flex",
  gap: "10px",
  flexWrap: "wrap",
  padding: "12px 14px",
  borderRadius: "12px",
  border: "1px solid var(--app-success-border)",
  background: "var(--app-success-bg)",
  color: "var(--app-success-fg)",
  fontSize: "13px",
  fontWeight: 600,
};

const keywordStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  padding: "4px 10px",
  borderRadius: "999px",
  background: "var(--app-warning-bg)",
  border: "1px solid var(--app-warning-border)",
  color: "var(--app-warning-fg)",
  fontSize: "12px",
};

const historyRowStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "minmax(220px, 1.5fr) minmax(120px, 0.7fr) minmax(180px, 1fr)",
  gap: "12px",
  alignItems: "center",
  border: "1px solid var(--app-surface-border)",
  borderRadius: "12px",
  padding: "12px 14px",
  background: "var(--app-surface-muted-bg)",
};

const suggestedResponseStyle: CSSProperties = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "12px",
  padding: "10px 12px",
  background: "var(--app-surface-muted-bg)",
  color: "var(--app-text-muted)",
  lineHeight: 1.7,
};

const smallSectionTitleStyle: CSSProperties = {
  color: "var(--app-warning-fg)",
  fontSize: "12px",
  fontWeight: 700,
  textTransform: "uppercase",
};

const readyBadgeStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  padding: "4px 10px",
  borderRadius: "999px",
  background: "var(--app-success-bg)",
  border: "1px solid var(--app-success-border)",
  color: "var(--app-success-fg)",
  fontSize: "12px",
  fontWeight: 700,
};

const pendingBadgeStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  padding: "4px 10px",
  borderRadius: "999px",
  background: "var(--app-chip-bg)",
  border: "1px solid var(--app-chip-border)",
  color: "var(--app-chip-fg)",
  fontSize: "12px",
  fontWeight: 700,
};
