"use client";

import { useEffect, useState } from "react";
import type { ReactNode } from "react";

import AppContainer from "@/components/AppContainer";
import PageHeader from "@/components/PageHeader";
import SectionCard from "@/components/SectionCard";
import { adminFetch } from "@/lib/adminAuth";
import { apiUrl } from "@/lib/api";

import {
  EventFiles,
  InfoBlock,
  MetricsNav,
  MetricsReadinessChecklist,
  MetricsRunState,
  MetricsStatus,
  MetricsSummary,
  MetricsValidationGuide,
  OpsAnalysis,
  PeriodOpsAnalysis,
  StatusCards,
  SummarySection,
  TrendSection,
  explanationGridStyle,
  getLocalDateKey,
} from "./shared";

type MetricsMode = "daily" | "weekly" | "monthly";

type ApiCategoryStatus = {
  exists?: boolean;
  file_count?: number;
  latest_date?: string | null;
  latest_path?: string | null;
};

type ApiMetricsStatus = {
  metrics_dir?: string;
  data_source?: string;
  has_any_metrics?: boolean;
  available_dates?: string[];
  latest_raw_event_date?: string | null;
  latest_signal_activity_date?: string | null;
  latest_summary_date?: string | null;
  latest_summary_path?: string | null;
  is_summary_stale?: boolean;
  missing_summary_dates?: string[];
  signal_dates_missing_pipeline_runs?: string[];
  signal_dates_missing_collector_runs?: string[];
  categories?: Record<string, ApiCategoryStatus>;
};

type DailySummaryResponse = {
  summary?: MetricsSummary;
};

type SummariesResponse = {
  summaries?: MetricsSummary[];
};

type LoadState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | {
      status: "ready";
      metricsStatus: MetricsStatus;
      reportingDate: string;
      reportingSummary: MetricsSummary | null;
      summaries: MetricsSummary[];
      summariesUnavailable: boolean;
    };

export default function MetricsClient({ mode }: { mode: MetricsMode }) {
  const [state, setState] = useState<LoadState>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;
    const controller = new AbortController();

    async function load() {
      setState({ status: "loading" });
      try {
        const statusResponse = await adminFetch(apiUrl("/metrics/status"), {
          cache: "no-store",
          signal: controller.signal,
        });
        if (!statusResponse.ok) {
          throw new Error(`Metrics status failed with HTTP ${statusResponse.status}`);
        }
        const metricsStatus = normalizeMetricsStatus(
          (await statusResponse.json()) as ApiMetricsStatus,
        );
        const reportingDate = resolveReportingDate(metricsStatus);

        let reportingSummary: MetricsSummary | null = null;
        if (mode === "daily") {
          const dailyResponse = await adminFetch(
            apiUrl(`/metrics/daily-summary?date=${encodeURIComponent(reportingDate)}`),
            { cache: "no-store", signal: controller.signal },
          );
          if (dailyResponse.ok) {
            const payload = (await dailyResponse.json()) as DailySummaryResponse;
            reportingSummary = payload.summary || null;
          } else if (dailyResponse.status !== 404) {
            throw new Error(`Daily summary failed with HTTP ${dailyResponse.status}`);
          }
        }

        const summaryCategory =
          mode === "daily" ? "daily_summary" : mode === "weekly" ? "weekly_summary" : "monthly_summary";
        const summariesUrl = new URL(apiUrl("/metrics/summaries"));
        summariesUrl.searchParams.set("category", summaryCategory);
        summariesUrl.searchParams.set("limit", "5");
        if (mode === "daily") {
          summariesUrl.searchParams.set("through_date", reportingDate);
        }
        const summariesResponse = await adminFetch(summariesUrl.toString(), {
          cache: "no-store",
          signal: controller.signal,
        });
        let summariesPayload: SummariesResponse = { summaries: [] };
        let summariesUnavailable = false;
        if (summariesResponse.ok) {
          summariesPayload = (await summariesResponse.json()) as SummariesResponse;
        } else if (summariesResponse.status !== 404) {
          throw new Error(`Metrics summaries failed with HTTP ${summariesResponse.status}`);
        } else {
          summariesUnavailable = true;
        }
        const summaries =
          mode === "daily" && !summariesUnavailable
            ? fillRecentDailySummaries(summariesPayload.summaries || [], reportingDate, 5)
            : summariesPayload.summaries || [];

        if (!cancelled) {
          setState({
            status: "ready",
            metricsStatus,
            reportingDate,
            reportingSummary,
            summaries,
            summariesUnavailable,
          });
        }
      } catch (error) {
        if (cancelled || controller.signal.aborted) return;
        setState({
          status: "error",
          message: error instanceof Error ? error.message : "Metrics API request failed.",
        });
      }
    }

    load();
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [mode]);

  if (state.status === "loading") {
    return <MetricsShell mode={mode} title={pageTitle(mode)} description={pageDescription(mode)} />;
  }

  if (state.status === "error") {
    return (
      <MetricsShell mode={mode} title={pageTitle(mode)} description={pageDescription(mode)}>
        <SectionCard title="Metrics API">
          <div style={apiStateStyle("bad")}>
            <div style={apiStateTitleStyle}>Metrics API could not load</div>
            <div style={apiStateTextStyle}>{state.message}</div>
          </div>
        </SectionCard>
      </MetricsShell>
    );
  }

  if (mode === "weekly" || mode === "monthly") {
    const comparisonLabel = mode === "weekly" ? "WoW" : "MoM";
    return (
      <MetricsShell mode={mode} title={pageTitle(mode)} description={pageDescription(mode)}>
        <SectionCard title="How To Read This">
          <div style={explanationGridStyle}>
            <InfoBlock
              title="Columns"
              text={
                mode === "weekly"
                  ? "Each period column is one ISO week summary loaded from the backend metrics API when a summary payload exists."
                  : "Each period column is one calendar month summary loaded from the backend metrics API when a summary payload exists."
              }
            />
            <InfoBlock
              title={comparisonLabel}
              text={`The final column compares the newest ${mode === "weekly" ? "week" : "month"} with the previous period as a percentage movement.`}
            />
            <InfoBlock
              title="Data Source"
              text={`Current source: ${state.metricsStatus.dataSource || "unknown"}. Period summaries come from backend metrics storage, not frontend build-time files. Empty means no summary payload was returned; it is not the same as a real zero metric.`}
            />
          </div>
        </SectionCard>
        <MetricsReadinessChecklist
          status={state.metricsStatus}
          todaySummary={null}
          summariesUnavailable={state.summariesUnavailable}
        />
        <PeriodOpsAnalysis
          title={mode === "weekly" ? "Weekly Summary" : "Monthly Summary"}
          summaries={state.summaries}
          comparisonLabel={comparisonLabel}
          emptyMessage={`No ${mode} metrics analysis is available yet.`}
          emptyDetail={
            state.summariesUnavailable
              ? "The backend does not expose the metrics summaries API yet. Restart or deploy the backend that includes /metrics/summaries."
              : `The backend metrics API has no ${mode} summary payloads yet.`
          }
        />
        <TrendSection
          title={mode === "weekly" ? "Weekly Trend Table" : "Monthly Trend Table"}
          summaries={state.summaries}
          comparisonLabel={comparisonLabel}
          emptyMessage={`No ${mode} summary is available yet.`}
          emptyDetail={
            state.summariesUnavailable
              ? "The backend does not expose the metrics summaries API yet. Restart or deploy the backend that includes /metrics/summaries."
              : `The trend table needs at least one ${mode} summary from the metrics API.`
          }
        />
      </MetricsShell>
    );
  }

  return (
    <MetricsShell mode={mode} title={pageTitle(mode)} description={pageDescription(mode)}>
      <SectionCard title="How To Read This">
        <div style={explanationGridStyle}>
          <InfoBlock
            title="Data Through"
            text="Daily metrics use the latest available backend metrics or signal-activity date, so a completed same-day pipeline can appear immediately."
          />
          <InfoBlock
            title="Trend Views"
            text="Use Weekly or Monthly for cross-period comparison tables and WoW / MoM movement."
          />
          <InfoBlock
            title="Data Source"
            text={`Current source: ${state.metricsStatus.dataSource || "unknown"}. This page reads the backend metrics API instead of frontend build-time local files. Missing history, stale summary, and real zero values are treated separately.`}
          />
        </div>
      </SectionCard>

      <MetricsRunState
        status={state.metricsStatus}
        today={state.reportingDate}
        todaySummary={state.reportingSummary}
      />
      <MetricsReadinessChecklist
        status={state.metricsStatus}
        todaySummary={state.reportingSummary}
        summariesUnavailable={state.summariesUnavailable}
      />
      <MetricsValidationGuide />
      <StatusCards status={state.metricsStatus} />
      <OpsAnalysis
        title="Daily Summary"
        summary={state.reportingSummary}
        emptyMessage="The reporting-day metrics analysis is not available yet."
        emptyDetail="The metrics API has no daily summary for the previous local date yet."
        periodLabel="Reporting day"
      />
      <SummarySection
        title={`Daily Detail - ${state.reportingDate}`}
        summary={state.reportingSummary}
        emptyMessage="The reporting-day daily summary is not available yet."
        emptyDetail="No production daily summary exists for the previous local date."
      />
      <TrendSection
        title="Recent Daily Metrics"
        summaries={state.summaries}
        comparisonLabel="Latest"
        emptyMessage="No daily metric history is available yet."
        emptyDetail={
          state.summariesUnavailable
            ? "The backend does not expose the metrics summaries API yet. Restart or deploy the backend that includes /metrics/summaries."
            : "The metrics API has not returned daily summary history yet."
        }
      />
      <EventFiles status={state.metricsStatus} />
    </MetricsShell>
  );
}

function MetricsShell({
  mode,
  title,
  description,
  children,
}: {
  mode: MetricsMode;
  title: string;
  description: string;
  children?: ReactNode;
}) {
  return (
    <AppContainer>
      <PageHeader title={title} description={description} size="compact" />
      <MetricsNav active={mode} />
      {children || (
        <SectionCard title="Metrics API">
          <div style={apiStateStyle("neutral")}>
            <div style={apiStateTitleStyle}>Loading metrics API</div>
            <div style={apiStateTextStyle}>Reading backend metrics status and summaries.</div>
          </div>
        </SectionCard>
      )}
    </AppContainer>
  );
}

function normalizeMetricsStatus(payload: ApiMetricsStatus): MetricsStatus {
  const categories: MetricsStatus["categories"] = {};
  for (const [key, value] of Object.entries(payload.categories || {})) {
    categories[key] = {
      exists: Boolean(value.exists),
      fileCount: Number(value.file_count || 0),
      latestDate: value.latest_date || null,
      latestPath: value.latest_path || null,
    };
  }

  return {
    metricsDir: payload.metrics_dir || "unknown",
    dataSource: payload.data_source || "unknown",
    hasAnyMetrics: Boolean(payload.has_any_metrics),
    availableDates: payload.available_dates || [],
    latestRawEventDate: payload.latest_raw_event_date || null,
    latestSignalActivityDate: payload.latest_signal_activity_date || null,
    latestSummaryDate: payload.latest_summary_date || null,
    latestSummaryPath: payload.latest_summary_path || null,
    isSummaryStale: Boolean(payload.is_summary_stale),
    missingSummaryDates: payload.missing_summary_dates || [],
    signalDatesMissingPipelineRuns: payload.signal_dates_missing_pipeline_runs || [],
    signalDatesMissingCollectorRuns: payload.signal_dates_missing_collector_runs || [],
    categories,
  };
}

function resolveReportingDate(status: MetricsStatus) {
  return (
    status.latestSummaryDate ||
    status.latestRawEventDate ||
    status.latestSignalActivityDate ||
    status.availableDates.at(-1) ||
    getLocalDateKey()
  );
}

function fillRecentDailySummaries(
  summaries: MetricsSummary[],
  throughDate: string,
  limit: number,
) {
  const byDate = new Map(
    summaries
      .filter((summary) => summary.date)
      .map((summary) => [summary.date as string, summary]),
  );
  const dates: string[] = [];
  const cursor = new Date(`${throughDate}T00:00:00`);

  for (let index = limit - 1; index >= 0; index -= 1) {
    const date = new Date(cursor);
    date.setDate(cursor.getDate() - index);
    dates.push(getLocalDateKey(date));
  }

  return dates.map(
    (dateKey) =>
      byDate.get(dateKey) || {
        date: dateKey,
        period_type: "day",
        period_id: dateKey,
      },
  );
}

function pageTitle(mode: MetricsMode) {
  if (mode === "weekly") return "Weekly Metrics";
  if (mode === "monthly") return "Monthly Metrics";
  return "Metrics";
}

function pageDescription(mode: MetricsMode) {
  if (mode === "weekly") {
    return "Latest five weekly operational summaries with week-over-week movement.";
  }
  if (mode === "monthly") {
    return "Latest five monthly operational summaries with month-over-month movement.";
  }
  return "Operational health for AI Radar pipeline, collector, LLM, verification, and signal-activity metrics through the latest available backend date.";
}

const apiStateStyle = (tone: "neutral" | "bad") =>
  ({
    border: `1px solid ${tone === "bad" ? "var(--app-danger-border)" : "rgba(148, 163, 184, 0.18)"}`,
    background: tone === "bad" ? "var(--app-danger-bg)" : "var(--app-surface-muted-bg)",
    borderRadius: "8px",
    padding: "14px",
  }) as const;

const apiStateTitleStyle = {
  fontSize: "14px",
  fontWeight: 900,
  color: "var(--app-text-strong)",
  marginBottom: "6px",
} as const;

const apiStateTextStyle = {
  fontSize: "13px",
  color: "var(--app-text-muted)",
  lineHeight: 1.6,
} as const;
