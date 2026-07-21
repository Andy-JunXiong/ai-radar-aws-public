"use client";

import { useEffect, useMemo, useState, type ReactNode } from "react";
import Link from "next/link";
import { ArrowRight, BookOpenCheck, Gauge, Radar, Settings, type LucideIcon } from "lucide-react";
import AppContainer from "@/components/AppContainer";
import { apiUrl } from "@/lib/api";

type SignalItem = {
  id?: string;
  signal_id?: string;
  title?: string;
  summary?: string;
  why_it_matters?: string;
  source?: string;
  source_name?: string;
  source_type?: string;
  published_at?: string;
  collected_at?: string;
  topic?: string;
  score?: number | string | null;
  status?: string;
  insight_status?: string;
  insight_status_label?: string;
  is_manual?: boolean;
  content_type?: string;
  file_count?: number;
  file_types?: string[];
  files?: Array<{ original_filename?: string }>;
  analysis_status?: string;
};

type TopicTrendItem = {
  topic?: string;
  label?: string;
  score?: number | string | null;
  count?: number | string | null;
  topic_count?: number | string | null;
  rising_score?: number | string | null;
  recent_3d_count?: number | string | null;
  earlier_4d_count?: number | string | null;
  momentum_delta?: number | string | null;
  priority_score?: number | string | null;
  signal_count?: number | string | null;
  momentum_score?: number | string | null;
  name?: string;
};

type RadarPayload = {
  topic_trends?: TopicTrendItem[] | Record<string, unknown> | { items?: TopicTrendItem[] | Record<string, unknown> };
  rising_topics?: TopicTrendItem[] | string[] | { items?: TopicTrendItem[] | Record<string, unknown> };
  weekly_momentum?: TopicTrendItem[] | Record<string, unknown> | { items?: TopicTrendItem[] | Record<string, unknown> };
  strategic_priority?: {
    top_priority_topics?: TopicTrendItem[] | string[];
    strategic_priority_topics?: TopicTrendItem[] | string[];
    strategic_priorities?: string[];
    key_actions?: string[];
  };
};

type DashboardRadarItem = {
  id: string;
  title: string;
  summary: string;
  topic: string;
  score: number | null;
  status: string;
  insightStatusLabel: string;
  source: string;
  publishedAt?: string;
  collectedAt?: string;
  inputMode: "auto" | "manual";
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

export default function DashboardHome() {
  const [signals, setSignals] = useState<SignalItem[]>([]);
  const [radar, setRadar] = useState<RadarPayload | null>(null);
  const [loadingSignals, setLoadingSignals] = useState(true);
  const [loadingRadar, setLoadingRadar] = useState(true);

  useEffect(() => {
    fetch(apiUrl("/signals"))
      .then((res) => res.json())
      .then((data) => {
        const items = Array.isArray(data) ? data : data.signals || data.items || [];
        setSignals(Array.isArray(items) ? items : []);
      })
      .catch((err) => {
        console.error("Failed to load signals:", err);
        setSignals([]);
      })
      .finally(() => setLoadingSignals(false));
  }, []);

  useEffect(() => {
    Promise.all([
      fetch(apiUrl("/radar")).then((res) => res.json()),
      fetch(apiUrl("/radar/intelligence")).then((res) => res.json()),
    ])
      .then(([radarData, intelligenceData]) =>
        setRadar({
          ...(radarData || {}),
          ...(intelligenceData || {}),
        })
      )
      .catch((err) => {
        console.error("Failed to load radar:", err);
        setRadar(null);
      })
      .finally(() => setLoadingRadar(false));
  }, []);

  const dashboardItems = useMemo<DashboardRadarItem[]>(() => {
    return signals.map((item, index) => {
      const rawScore = item.score;
      const score =
        rawScore === null || rawScore === undefined || rawScore === "" ? null : Number(rawScore);
      const sourceLabel =
        item.is_manual || item.source === "manual"
          ? "Manual Upload"
          : item.source_name || item.source || item.source_type || "Unknown source";

      return {
        id: item.id || item.signal_id || `signal-${index}`,
        title: item.title || "Untitled Signal",
        summary: item.summary || item.why_it_matters || buildManualSummary(item) || "No summary",
        topic: normalizeTopic(item.topic),
        score: Number.isFinite(score) ? score : null,
        status: normalizeStatus(item.status),
        insightStatusLabel: normalizeInsightLabel(item),
        source: sourceLabel,
        publishedAt: item.published_at,
        collectedAt: item.collected_at,
        inputMode: item.is_manual || item.source === "manual" ? "manual" : "auto",
      };
    });
  }, [signals]);

  const stats = useMemo(() => {
    const pending = dashboardItems.filter((s) => s.status === "pending").length;
    const analyzed = dashboardItems.filter((s) => s.status === "analyzed").length;
    const rejected = dashboardItems.filter((s) => s.status === "rejected").length;
    const saved = dashboardItems.filter((s) => s.status === "saved").length;
    const auto = dashboardItems.filter((s) => s.inputMode === "auto").length;
    const manual = dashboardItems.filter((s) => s.inputMode === "manual").length;

    return { total: dashboardItems.length, pending, analyzed, rejected, saved, auto, manual };
  }, [dashboardItems]);

  const topItems = useMemo(() => {
    return [...dashboardItems]
      .sort((a, b) => {
        const scoreA = a.score ?? -1;
        const scoreB = b.score ?? -1;
        if (scoreB !== scoreA) return scoreB - scoreA;
        const dateA = new Date(a.publishedAt || a.collectedAt || 0).getTime();
        const dateB = new Date(b.publishedAt || b.collectedAt || 0).getTime();
        return dateB - dateA;
      })
      .slice(0, 5);
  }, [dashboardItems]);

  const topicDistribution = useMemo(() => {
    const counter = new Map<
      string,
      { count: number; totalScore: number; scoredCount: number; autoCount: number; manualCount: number }
    >();
    for (const item of dashboardItems) {
      const topic = item.topic || "General AI";
      const existing = counter.get(topic) || {
        count: 0,
        totalScore: 0,
        scoredCount: 0,
        autoCount: 0,
        manualCount: 0,
      };
      existing.count += 1;
      if (item.inputMode === "auto") existing.autoCount += 1;
      else existing.manualCount += 1;
      if (item.score !== null) {
        existing.totalScore += item.score;
        existing.scoredCount += 1;
      }
      counter.set(topic, existing);
    }

    return Array.from(counter.entries())
      .map(([topic, value]) => ({
        topic,
        count: value.count,
        autoCount: value.autoCount,
        manualCount: value.manualCount,
        avgScore: value.scoredCount > 0 ? value.totalScore / value.scoredCount : null,
      }))
      .sort((a, b) =>
        b.count !== a.count ? b.count - a.count : (b.avgScore ?? -1) - (a.avgScore ?? -1)
      )
      .slice(0, 8);
  }, [dashboardItems]);

  const topicMomentum = useMemo(() => {
    return {
      dominant: normalizeTopicItems(radar?.topic_trends).slice(0, 5),
      rising: normalizeTopicItems(radar?.rising_topics).slice(0, 5),
      weekly: normalizeTopicItems(radar?.weekly_momentum).slice(0, 5),
    };
  }, [radar]);

  const strategicPriorityItems = useMemo(() => {
    const explicit =
      radar?.strategic_priority?.strategic_priorities || radar?.strategic_priority?.key_actions || [];
    if (Array.isArray(explicit) && explicit.length > 0) return explicit.slice(0, 3);
    const topicBased = normalizeTopicItems(
      radar?.strategic_priority?.top_priority_topics || radar?.strategic_priority?.strategic_priority_topics
    ).slice(
      0,
      3
    );
    if (topicBased.length > 0) {
      return topicBased.map((item, index) => buildPriorityText(item.label, item.score, index));
    }
    return [];
  }, [radar]);

  return (
    <AppContainer style={dashboardShellStyle}>
      <section style={heroSectionStyle}>
        <div style={{ minWidth: 0 }}>
          <div style={eyebrowStyle}>Dashboard</div>
          <h1 style={heroTitleStyle}>Operating cockpit for today's intelligence loop.</h1>
          <p style={heroDescriptionStyle}>
            Track signal intake, topic momentum, strategic priorities, and the handoff from evidence-aware intelligence into review.
          </p>
          <div style={quickActionRowStyle}>
            <QuickAction href="/signals" label="Review signals" icon={Radar} />
            <QuickAction href="/workspace/projects/review" label="Open review inbox" icon={BookOpenCheck} />
            <QuickAction href="/settings" label="Beta settings" icon={Settings} />
          </div>
        </div>

        <div style={heroSummaryStyle}>
          <div style={summaryHeaderStyle}>
            <Gauge size={18} aria-hidden="true" />
            <span>Pipeline snapshot</span>
          </div>
          <div style={summaryGridStyle}>
            <SummaryMetric label="Total" value={stats.total} />
            <SummaryMetric label="Pending" value={stats.pending} />
            <SummaryMetric label="Analyzed" value={stats.analyzed} />
            <SummaryMetric label="Manual" value={stats.manual} />
          </div>
        </div>
      </section>

      <DashboardSection
        eyebrow="Controls"
        title="Private beta context"
        action={
          <Link href="/settings" style={sectionActionStyle}>
            Open settings
            <ArrowRight size={15} aria-hidden="true" />
          </Link>
        }
      >
        <p style={sectionBodyTextStyle}>
          Manage private beta personalization inputs before testing signal insight, manual analysis, and workspace chat with a beta user context.
        </p>
      </DashboardSection>

      <DashboardSection eyebrow="Pipeline" title="Intelligence pipeline status">
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 170px), 1fr))",
            gap: "12px",
          }}
        >
          <StatCard label="Total Intelligence Items" value={stats.total} />
          <StatCard label="Auto Signals" value={stats.auto} />
          <StatCard label="Manual Inputs" value={stats.manual} />
          <StatCard label="Pending Review" value={stats.pending} />
          <StatCard label="Analyzed" value={stats.analyzed} />
          <StatCard label="Rejected" value={stats.rejected} />
          <StatCard label="Saved" value={stats.saved} />
        </div>
      </DashboardSection>

      <DashboardSection eyebrow="Radar" title="Topic momentum">
        {loadingRadar ? (
          <div style={{ color: "var(--app-text-muted)" }}>Loading topic momentum...</div>
        ) : (
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 240px), 1fr))",
              gap: "12px",
            }}
          >
            <MomentumColumn
              title="Dominant Topics"
              items={topicMomentum.dominant}
              emptyText="No dominant topics available."
            />
            <MomentumColumn
              title="Rising Topics"
              items={topicMomentum.rising}
              emptyText="No rising topics available."
            />
            <MomentumColumn
              title="Weekly Momentum"
              items={topicMomentum.weekly}
              emptyText="No weekly momentum available."
            />
          </div>
        )}
      </DashboardSection>

      <DashboardSection eyebrow="Coverage" title="Topic distribution">
        {loadingSignals ? (
          <div style={{ color: "var(--app-text-muted)" }}>Loading topic distribution...</div>
        ) : topicDistribution.length ? (
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 220px), 1fr))",
              gap: "12px",
            }}
          >
            {topicDistribution.map((item) => (
              <div
                key={item.topic}
                style={{
                  border: "1px solid var(--app-surface-border)",
                  borderRadius: "8px",
                  padding: "14px",
                  background: "var(--app-surface-muted-bg)",
                }}
              >
                <div
                  style={{
                    fontWeight: 700,
                    fontSize: "15px",
                    color: "var(--app-text-strong)",
                    lineHeight: 1.4,
                  }}
                >
                  {item.topic}
                </div>
                <div style={{ marginTop: "10px", display: "flex", gap: "8px", flexWrap: "wrap" }}>
                  <InfoBadge label={`${item.count} items`} />
                  <InfoBadge label={`Auto ${item.autoCount}`} />
                  <InfoBadge label={`Manual ${item.manualCount}`} />
                  <InfoBadge
                    label={
                      item.avgScore !== null ? `Avg score ${item.avgScore.toFixed(2)}` : "Avg score N/A"
                    }
                  />
                </div>
                <div style={{ marginTop: "10px", fontSize: "13px", color: "var(--app-text-muted)", lineHeight: 1.6 }}>
                  {item.count >= 5
                    ? "High current coverage in this topic."
                    : item.count >= 2
                      ? "Moderate current coverage in this topic."
                      : "Early coverage signal in this topic."}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div style={{ color: "var(--app-text-muted)" }}>No topic distribution available.</div>
        )}
      </DashboardSection>

      <DashboardSection eyebrow="Strategic readout" title="Strategic priorities">
        {loadingRadar ? (
          <div style={{ color: "var(--app-text-muted)" }}>Loading strategic priorities...</div>
        ) : strategicPriorityItems.length ? (
          <div style={{ display: "grid", gap: "12px" }}>
            {strategicPriorityItems.map((item, index) => (
              <div
                key={`${item}-${index}`}
                style={{
                  padding: "14px 16px",
                  borderRadius: "8px",
                  border: "1px solid var(--app-surface-border)",
                  background: "var(--app-surface-muted-bg)",
                  color: "var(--app-text-muted)",
                  lineHeight: 1.7,
                }}
              >
                <strong style={{ color: "var(--app-text-strong)" }}>{index + 1}.</strong> {item}
              </div>
            ))}
          </div>
        ) : (
          <div style={{ color: "var(--app-text-muted)" }}>No strategic priorities available.</div>
        )}
      </DashboardSection>

      <DashboardSection eyebrow="Review queue" title="Top intelligence items today" marginBottom="0">
        {loadingSignals ? (
          <div style={{ color: "var(--app-text-muted)" }}>Loading intelligence items...</div>
        ) : topItems.length ? (
          <div style={{ display: "grid", gap: "12px" }}>
            {topItems.map((item) => (
              <div
                key={item.id}
                style={{
                  padding: "16px",
                  borderRadius: "8px",
                  border: "1px solid var(--app-surface-border)",
                  background: "var(--app-surface-muted-bg)",
                }}
              >
                <div style={{ fontWeight: 700, fontSize: "16px", color: "var(--app-text-strong)", lineHeight: 1.4 }}>
                  {item.title}
                </div>
                <div style={{ fontSize: "14px", color: "var(--app-text-muted)", marginTop: "8px", lineHeight: 1.6 }}>
                  {item.summary}
                </div>
                <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", marginTop: "10px" }}>
                  <InfoBadge label={item.topic} />
                  <InfoBadge label={item.score !== null ? `Score ${item.score.toFixed(2)}` : "Score N/A"} />
                  <InfoBadge label={item.insightStatusLabel} />
                  <InfoBadge label={item.inputMode === "manual" ? "Manual" : "Auto"} />
                </div>
                <div
                  style={{
                    marginTop: "10px",
                    fontSize: "12px",
                    color: "var(--app-text-subtle)",
                    display: "flex",
                    gap: "12px",
                    flexWrap: "wrap",
                  }}
                >
                  <span>{item.source}</span>
                  <span>{formatDate(item.publishedAt || item.collectedAt)}</span>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div style={{ color: "var(--app-text-muted)" }}>No intelligence items available.</div>
        )}
      </DashboardSection>
    </AppContainer>
  );
}

function QuickAction({
  href,
  label,
  icon: Icon,
}: {
  href: string;
  label: string;
  icon: LucideIcon;
}) {
  return (
    <Link href={href} style={quickActionStyle}>
      <Icon size={16} aria-hidden="true" />
      {label}
    </Link>
  );
}

function SummaryMetric({ label, value }: { label: string; value: number }) {
  return (
    <div style={summaryMetricStyle}>
      <div style={summaryMetricValueStyle}>{value}</div>
      <div style={summaryMetricLabelStyle}>{label}</div>
    </div>
  );
}

function DashboardSection({
  eyebrow,
  title,
  children,
  action,
  marginBottom = "14px",
}: {
  eyebrow: string;
  title: string;
  children: ReactNode;
  action?: ReactNode;
  marginBottom?: string;
}) {
  return (
    <section style={{ ...sectionCardStyle, marginBottom }}>
      <div style={sectionHeaderStyle}>
        <div>
          <div style={eyebrowStyle}>{eyebrow}</div>
          <h2 style={sectionTitleStyle}>{title}</h2>
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <div style={statCardStyle}>
      <div style={statLabelStyle}>{label}</div>
      <div style={statValueStyle}>{value}</div>
    </div>
  );
}

function MomentumColumn({
  title,
  items,
  emptyText,
}: {
  title: string;
  items: Array<{ label: string; score: number | null; count: number | null }>;
  emptyText: string;
}) {
  return (
    <div style={momentumColumnStyle}>
      <div style={momentumTitleStyle}>{title}</div>
      {items.length ? (
        <div style={{ display: "grid", gap: "10px" }}>
          {items.map((item, index) => (
            <div
              key={`${title}-${item.label}-${index}`}
              style={momentumItemStyle}
            >
              <div style={{ color: "var(--app-text-strong)", fontWeight: 600 }}>{item.label}</div>
              <div style={{ marginTop: "6px", display: "flex", gap: "8px", flexWrap: "wrap" }}>
                {item.count !== null ? <InfoBadge label={`${item.count} signals`} /> : null}
                <InfoBadge label={item.score !== null ? `Score ${item.score}` : "Score N/A"} />
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div style={{ color: "var(--app-text-muted)" }}>{emptyText}</div>
      )}
    </div>
  );
}

function InfoBadge({ label }: { label: string }) {
  return (
    <span style={infoBadgeStyle}>
      {label}
    </span>
  );
}

const dashboardShellStyle = {
  paddingTop: "28px",
  color: "var(--app-page-fg)",
} as const;

const heroSectionStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 420px), 1fr))",
  gap: "18px",
  alignItems: "stretch",
  marginBottom: "16px",
} as const;

const eyebrowStyle = {
  color: "var(--app-text-subtle)",
  fontSize: "12px",
  fontWeight: 760,
  textTransform: "uppercase" as const,
  letterSpacing: "0",
} as const;

const heroTitleStyle = {
  margin: "10px 0 0",
  color: "var(--app-text-strong)",
  fontSize: "38px",
  fontWeight: 780,
  lineHeight: 1.08,
  maxWidth: "780px",
} as const;

const heroDescriptionStyle = {
  margin: "14px 0 0",
  color: "var(--app-text-muted)",
  fontSize: "16px",
  lineHeight: 1.62,
  maxWidth: "780px",
} as const;

const quickActionRowStyle = {
  display: "flex",
  gap: "9px",
  flexWrap: "wrap" as const,
  marginTop: "20px",
} as const;

const quickActionStyle = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  gap: "7px",
  border: "1px solid var(--app-secondary-action-border)",
  borderRadius: "8px",
  background: "var(--app-secondary-action-bg)",
  color: "var(--app-secondary-action-fg)",
  padding: "10px 12px",
  textDecoration: "none",
  fontSize: "13px",
  fontWeight: 720,
  whiteSpace: "nowrap" as const,
} as const;

const heroSummaryStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-bg)",
  padding: "16px",
  boxShadow: "var(--app-surface-shadow)",
} as const;

const summaryHeaderStyle = {
  display: "inline-flex",
  alignItems: "center",
  gap: "8px",
  color: "var(--app-text-strong)",
  fontSize: "14px",
  fontWeight: 760,
} as const;

const summaryGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
  gap: "10px",
  marginTop: "14px",
} as const;

const summaryMetricStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  padding: "13px",
} as const;

const summaryMetricValueStyle = {
  color: "var(--app-text-strong)",
  fontSize: "28px",
  fontWeight: 780,
  lineHeight: 1,
} as const;

const summaryMetricLabelStyle = {
  marginTop: "7px",
  color: "var(--app-text-subtle)",
  fontSize: "12px",
  fontWeight: 720,
} as const;

const sectionCardStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  padding: "18px",
  background: "var(--app-surface-bg)",
  boxShadow: "var(--app-surface-shadow)",
} as const;

const sectionHeaderStyle = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  gap: "12px",
  flexWrap: "wrap" as const,
  marginBottom: "14px",
} as const;

const sectionTitleStyle = {
  margin: "6px 0 0",
  color: "var(--app-text-strong)",
  fontSize: "22px",
  fontWeight: 760,
  lineHeight: 1.2,
} as const;

const sectionActionStyle = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  gap: "6px",
  border: "1px solid var(--app-primary-action-border)",
  borderRadius: "8px",
  background: "var(--app-primary-action-bg)",
  color: "var(--app-primary-action-fg)",
  padding: "9px 12px",
  textDecoration: "none",
  fontSize: "13px",
  fontWeight: 720,
  whiteSpace: "nowrap" as const,
} as const;

const sectionBodyTextStyle = {
  margin: 0,
  color: "var(--app-text-muted)",
  fontSize: "14px",
  lineHeight: 1.65,
  maxWidth: "860px",
} as const;

const statCardStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  padding: "15px",
  background: "var(--app-surface-muted-bg)",
} as const;

const statLabelStyle = {
  color: "var(--app-text-subtle)",
  fontSize: "12px",
  fontWeight: 720,
  marginBottom: "9px",
} as const;

const statValueStyle = {
  color: "var(--app-text-strong)",
  fontSize: "28px",
  fontWeight: 780,
  lineHeight: 1,
} as const;

const momentumColumnStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  padding: "14px",
  background: "var(--app-surface-muted-bg)",
} as const;

const momentumTitleStyle = {
  color: "var(--app-text-strong)",
  fontSize: "15px",
  fontWeight: 760,
  marginBottom: "12px",
} as const;

const momentumItemStyle = {
  padding: "10px 12px",
  borderRadius: "8px",
  background: "var(--app-surface-soft-bg)",
  border: "1px solid var(--app-surface-border)",
} as const;

const infoBadgeStyle = {
  display: "inline-flex",
  alignItems: "center",
  padding: "4px 9px",
  borderRadius: "999px",
  border: "1px solid var(--app-chip-border)",
  background: "var(--app-chip-bg)",
  fontSize: "12px",
  color: "var(--app-chip-fg)",
  fontWeight: 650,
} as const;

function normalizeStatus(value?: string) {
  const status = (value || "pending").toLowerCase();
  if (status === "saved" || status === "analyzed" || status === "rejected" || status === "completed") {
    return status === "completed" ? "analyzed" : status;
  }
  return "pending";
}

function normalizeTopic(value?: string) {
  if (!value || !String(value).trim()) return "General AI";
  return String(value).trim();
}

function buildManualSummary(item: Pick<SignalItem, "is_manual" | "source" | "file_types" | "file_count" | "files">) {
  if (!item.is_manual && item.source !== "manual") return "";
  const fileNames: string[] =
    item.files?.map((f) => f.original_filename).filter((name): name is string => Boolean(name)) || [];
  const fileTypes: string[] = item.file_types || [];
  const fileCount = item.file_count ?? item.files?.length ?? 0;
  if (fileNames.length > 0) return `Manual session with ${fileCount} file(s): ${fileNames.join(", ")}`;
  if (fileTypes.length > 0) return `Manual session with ${fileCount} file(s), including ${fileTypes.join(", ")}.`;
  return `Manual session with ${fileCount} uploaded file(s).`;
}

function normalizeInsightLabel(item: SignalItem) {
  if (item.insight_status_label) return item.insight_status_label;
  if (item.insight_status) return formatInsightStatus(item.insight_status);
  if (item.is_manual || item.source === "manual") {
    if (item.analysis_status === "completed") return "Manual session analyzed";
    if (item.analysis_status === "not_started") return "Manual session pending";
    return "Manual analysis item";
  }
  return "Status unknown";
}

function formatInsightStatus(value?: string) {
  switch (value) {
    case "auto_generated":
      return "Insight auto-generated";
    case "manual_candidate":
      return "Insight available on demand";
    case "archived_only":
      return "Archived signal only";
    case "immediate":
      return "Immediate insight";
    case "on_demand":
      return "Insight available on demand";
    case "archive":
      return "Archive only";
    default:
      return "Status unknown";
  }
}

function formatDate(value?: string) {
  if (!value) return "No date";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString();
}

function normalizeTopicItems(input: RadarPayload[keyof RadarPayload]) {
  if (!input) return [];
  if (isRecord(input) && "items" in input) {
    return normalizeTopicItems((input as { items?: TopicTrendItem[] | Record<string, unknown> }).items);
  }
  let items: Array<string | TopicTrendItem> = [];
  if (Array.isArray(input)) items = input;
  else if (isRecord(input)) {
    const data = input as Record<string, unknown>;
    if (Array.isArray(data.top_topics)) {
      items = data.top_topics.map((entry: unknown) => {
        if (Array.isArray(entry)) {
          const numericValue = Number(entry[1] || 0);
          return { topic: String(entry[0] || ""), count: numericValue, score: numericValue };
        }
        return entry as TopicTrendItem;
      });
    } else if (Array.isArray(data.rising_topics)) {
      items = data.rising_topics as Array<string | TopicTrendItem>;
    } else if (Array.isArray(data.rising_this_week)) {
      items = data.rising_this_week as Array<string | TopicTrendItem>;
    } else if (Array.isArray(data.strategic_priority_topics)) {
      items = data.strategic_priority_topics as Array<string | TopicTrendItem>;
    } else if (Array.isArray(data.top_priority_topics)) {
      items = data.top_priority_topics as Array<string | TopicTrendItem>;
    } else {
      items = Object.entries(data).map(([key, value]) => {
        if (isRecord(value)) return { topic: key, ...value };
        return {
          topic: key,
          score: typeof value === "string" || typeof value === "number" || value === null ? value : undefined,
        };
      });
    }
  }

  return items
    .map((item) => {
      if (typeof item === "string") return { label: item, score: null, count: null };
      const label = item.topic || item.label || item.name || "General AI";
      const rawScore =
        item.priority_score ??
        item.rising_score ??
        item.momentum_delta ??
        item.score ??
        item.momentum_score ??
        item.count ??
        item.topic_count ??
        item.recent_3d_count ??
        null;
      const rawCount =
        item.count ??
        item.topic_count ??
        item.signal_count ??
        item.recent_3d_count ??
        null;
      const score = rawScore === null || rawScore === undefined || rawScore === "" ? null : Number(rawScore);
      const count = rawCount === null || rawCount === undefined || rawCount === "" ? null : Number(rawCount);
      return { label, score: Number.isFinite(score) ? score : null, count: Number.isFinite(count) ? count : null };
    })
    .filter((item) => item.label)
    .sort((a, b) => ((b.count ?? -1) !== (a.count ?? -1) ? (b.count ?? -1) - (a.count ?? -1) : (b.score ?? -1) - (a.score ?? -1)));
}

function buildPriorityText(topicLabel: string, score: number | null, index: number) {
  if (index === 0) return `Focus first on ${topicLabel} because it currently leads the strongest strategic signals.`;
  if (index === 1) return `Watch ${topicLabel} closely for downstream project and product impact as related signals continue to accumulate.`;
  if (score !== null) return `${topicLabel} remains worth attention because it is still showing meaningful priority strength in the current radar cycle.`;
  return `${topicLabel} should remain on the watchlist as part of the current AI signal environment.`;
}
