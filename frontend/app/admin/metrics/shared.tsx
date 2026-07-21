import Link from "next/link";

import SectionCard from "@/components/SectionCard";

export type CategoryStatus = {
  exists: boolean;
  fileCount: number;
  latestDate: string | null;
  latestPath: string | null;
};

export type MetricsStatus = {
  metricsDir: string;
  dataSource?: string;
  hasAnyMetrics: boolean;
  availableDates: string[];
  latestRawEventDate: string | null;
  latestSignalActivityDate: string | null;
  latestSummaryDate: string | null;
  latestSummaryPath: string | null;
  isSummaryStale: boolean;
  missingSummaryDates: string[];
  signalDatesMissingPipelineRuns: string[];
  signalDatesMissingCollectorRuns: string[];
  categories: Record<string, CategoryStatus>;
};

export type MetricsSummary = {
  date?: string;
  period_type?: string;
  period_id?: string;
  date_count?: number;
  dates?: string[];
  pipeline?: Record<string, unknown>;
  artifacts?: Record<string, unknown>;
  collectors?: Record<string, unknown>;
  signals?: Record<string, unknown>;
  timeline_loads?: Record<string, unknown>;
  llm?: Record<string, unknown>;
  verification?: Record<string, unknown>;
};

type TrendMetric = {
  label: string;
  section: "pipeline" | "artifacts" | "collectors" | "signals" | "timeline_loads" | "llm" | "verification";
  field: string;
  format?: "number" | "percent" | "currency";
};

export const CATEGORY_CONFIG = {
  artifact_writes: { label: "Artifact Writes", extension: "jsonl" },
  pipeline_runs: { label: "Pipeline Runs", extension: "json" },
  collector_runs: { label: "Collector Runs", extension: "jsonl" },
  llm_calls: { label: "LLM Calls", extension: "jsonl" },
  verification_events: { label: "Verification Events", extension: "jsonl" },
  signal_timeline_loads: { label: "Signal Timeline Loads", extension: "jsonl" },
  daily_summary: { label: "Daily Summary", extension: "json" },
  weekly_summary: { label: "Weekly Summary", extension: "json" },
  monthly_summary: { label: "Monthly Summary", extension: "json" },
} as const;

const TREND_METRICS: TrendMetric[] = [
  { label: "Pipeline Runs", section: "pipeline", field: "run_count", format: "number" },
  { label: "Pipeline Success Rate", section: "pipeline", field: "success_rate", format: "percent" },
  { label: "Pipeline Avg Duration", section: "pipeline", field: "avg_duration_seconds", format: "number" },
  { label: "Artifact Writes", section: "artifacts", field: "write_count", format: "number" },
  { label: "Collector Runs", section: "collectors", field: "total_runs", format: "number" },
  { label: "Collector Success Rate", section: "collectors", field: "success_rate", format: "percent" },
  { label: "Items Written", section: "collectors", field: "total_items_written", format: "number" },
  { label: "Signals Collected", section: "signals", field: "collected_count", format: "number" },
  { label: "Signals Published", section: "signals", field: "published_count", format: "number" },
  { label: "Timeline Loads", section: "timeline_loads", field: "load_count", format: "number" },
  { label: "Slow Timeline Loads", section: "timeline_loads", field: "slow_load_count", format: "number" },
  { label: "LLM Calls", section: "llm", field: "call_count", format: "number" },
  { label: "LLM Success Rate", section: "llm", field: "success_rate", format: "percent" },
  { label: "Fallback Rate", section: "llm", field: "fallback_rate", format: "percent" },
  { label: "Avg LLM Latency", section: "llm", field: "avg_latency_ms", format: "number" },
  { label: "Estimated Cost", section: "llm", field: "estimated_cost", format: "currency" },
  { label: "Verification Downgrade Rate", section: "verification", field: "downgrade_rate", format: "percent" },
  { label: "Action Blocked Count", section: "verification", field: "action_blocked_count", format: "number" },
];

const METRICS_SMOKE_COMMAND = String.raw`.\.venv\Scripts\python.exe scripts\metrics_smoke.py`;
const METRICS_SMOKE_SUMMARY_COMMAND = String.raw`.\.venv\Scripts\python.exe scripts\metrics_smoke.py --show-summary`;
const METRICS_REFRESH_COMMAND = String.raw`.\.venv\Scripts\python.exe scripts\refresh_metrics_summaries.py --all`;
const METRICS_SAMPLE_COMMAND = String.raw`.\.venv\Scripts\python.exe scripts\generate_metrics_sample.py`;

export function getLocalDateKey(date = new Date()) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function getPreviousLocalDateKey(date = new Date()) {
  const previous = new Date(date);
  previous.setDate(previous.getDate() - 1);
  return getLocalDateKey(previous);
}

export function MetricsNav({ active }: { active: "daily" | "weekly" | "monthly" }) {
  return (
    <div style={toolbarStyle}>
      <Link href="/admin/metrics/" style={active === "daily" ? primaryLinkStyle : secondaryLinkStyle}>
        Daily
      </Link>
      <Link href="/admin/metrics/weekly/" style={active === "weekly" ? primaryLinkStyle : secondaryLinkStyle}>
        Weekly
      </Link>
      <Link href="/admin/metrics/monthly/" style={active === "monthly" ? primaryLinkStyle : secondaryLinkStyle}>
        Monthly
      </Link>
      <Link href="/admin" style={secondaryLinkStyle}>
        Back to Admin
      </Link>
    </div>
  );
}

export function InfoBlock({ title, text }: { title: string; text: string }) {
  return (
    <div style={infoBlockStyle}>
      <div style={infoTitleStyle}>{title}</div>
      <div style={infoTextStyle}>{text}</div>
    </div>
  );
}

export function StatusCards({ status }: { status: MetricsStatus }) {
  return (
    <SectionCard title="Status">
      <div style={statusGridStyle}>
        <MetricCard label="Data Source" value={formatMetricsDataSource(status.dataSource)} />
        <MetricCard label="Metrics Data" value={status.hasAnyMetrics ? "Present" : "Missing"} />
        <MetricCard label="Latest Daily Summary" value={status.latestSummaryDate || "None"} />
        <MetricCard label="Latest Raw Event" value={status.latestRawEventDate || "None"} />
        <MetricCard label="Latest Signal Activity" value={status.latestSignalActivityDate || "None"} />
        <MetricCard label="Summary State" value={status.isSummaryStale ? "Refresh Needed" : "Current"} />
        <MetricCard label="Available Dates" value={String(status.availableDates.length)} />
        <MetricCard label="Metrics Directory" value={status.metricsDir} compact />
      </div>
    </SectionCard>
  );
}

export function MetricsRunState({
  status,
  today,
  todaySummary,
}: {
  status: MetricsStatus;
  today: string;
  todaySummary: MetricsSummary | null;
}) {
  const latestDailyDate = status.latestSummaryDate;
  const dailySummaryCount = status.categories.daily_summary?.fileCount || 0;
  const dataSourceLabel = formatMetricsDataSource(status.dataSource);
  const sourceIsProduction = (status.dataSource || "").toLowerCase() === "s3";
  const hasReportingSummary = Boolean(todaySummary);
  const hasStaleLatest = Boolean(latestDailyDate && latestDailyDate < today);
  const hasRawAhead = status.isSummaryStale;
  const tone = hasRawAhead ? "watch" : hasReportingSummary ? "good" : hasStaleLatest ? "watch" : "neutral";
  const title = hasRawAhead
    ? "Summary Refresh Needed"
    : hasReportingSummary
      ? "Reporting Summary Ready"
      : hasStaleLatest
        ? "Reporting Summary Missing"
        : "No Daily Summary Yet";
  const text = hasRawAhead
    ? `Raw metrics exist through ${status.latestRawEventDate}, but the newest daily summary is ${latestDailyDate || "missing"}. Run the summary refresh command before reading rollups as current.`
    : hasReportingSummary
      ? `Daily metrics are available for the previous local day from ${dataSourceLabel}.`
      : hasStaleLatest
      ? `The newest daily summary is ${latestDailyDate}. Summary generation has not produced a ${today} reporting-day file yet.`
      : sourceIsProduction
        ? "Production metrics storage is reachable, but no daily summary has been returned for this reporting window yet."
        : "No daily summary file is available, so the metrics event foundation has not produced a readable daily rollup yet.";

  return (
    <SectionCard title="Run State">
      <div style={runStateBoxStyle(tone)}>
        <div>
          <div style={runStateTitleStyle}>{title}</div>
          <div style={runStateTextStyle}>{text}</div>
        </div>
        <div style={runStateFactsStyle}>
          <SummaryRow label="Data Through" value={today} />
          <SummaryRow label="Data Source" value={dataSourceLabel} />
          <SummaryRow label="Latest Raw Event" value={status.latestRawEventDate || "None"} />
          <SummaryRow label="Signal Activity" value={status.latestSignalActivityDate || "None"} />
          <SummaryRow label="Latest Daily" value={latestDailyDate || "None"} />
          <SummaryRow label="Missing Summaries" value={formatUnitCount(status.missingSummaryDates.length, "date")} />
          <SummaryRow label="Signal/Pipeline Gaps" value={formatUnitCount(status.signalDatesMissingPipelineRuns.length, "date")} />
          <SummaryRow label="Signal/Collector Gaps" value={formatUnitCount(status.signalDatesMissingCollectorRuns.length, "date")} />
          <SummaryRow label="Daily Files" value={String(dailySummaryCount)} />
          <SummaryRow label="Metrics Data" value={status.hasAnyMetrics ? "Present" : "Missing"} />
        </div>
      </div>
    </SectionCard>
  );
}

export function MetricsReadinessChecklist({
  status,
  todaySummary,
  summariesUnavailable,
}: {
  status: MetricsStatus;
  todaySummary: MetricsSummary | null;
  summariesUnavailable: boolean;
}) {
  const dataSourceLabel = formatMetricsDataSource(status.dataSource);
  const sourceIsProduction = (status.dataSource || "").toLowerCase() === "s3";
  const hasReportingSummary = Boolean(todaySummary);
  const summaryPosture = status.isSummaryStale
    ? "Refresh local summaries before reading rollups as current."
    : hasReportingSummary
      ? "Reporting-day summary is readable."
      : "Reporting-day summary is not available yet.";
  const productionPosture = sourceIsProduction
    ? status.hasAnyMetrics
      ? "Production metrics storage is reachable. Fresh production numbers still depend on a deployed writer and a future pipeline run."
      : "Production metrics storage is reachable, but no metrics artifacts were returned for this window."
    : "Production follow-up requires deploying the backend/ingestion metrics writer and waiting for a future pipeline run.";

  return (
    <SectionCard title="Readiness Checkpoints">
      <div style={validationGridStyle}>
        <InfoBlock
          title="Backend Source"
          text={`${dataSourceLabel}: metrics pages are reading the backend API, not frontend build-time files.`}
        />
        <InfoBlock
          title="Summary Readiness"
          text={summaryPosture}
        />
        <InfoBlock
          title="History API"
          text={
            summariesUnavailable
              ? "Summary history is unavailable from the backend; restart or deploy the backend with /metrics/summaries before trusting trend views."
              : "Summary history route is available. Empty trend rows mean no summary payload was returned, not a real zero metric."
          }
        />
        <InfoBlock
          title="Production Follow-up"
          text={productionPosture}
        />
      </div>
    </SectionCard>
  );
}

function formatMetricsDataSource(value?: string) {
  const normalized = String(value || "").toLowerCase();
  if (normalized === "s3") return "Production S3";
  if (normalized === "local_file") return "Local File";
  if (normalized === "local_raw_events") return "Local Raw Events";
  return "Unknown";
}

export function MetricsValidationGuide() {
  return (
    <SectionCard title="Local Validation">
      <div style={validationGridStyle}>
        <ValidationCommand
          title="Smoke Check"
          command={METRICS_SMOKE_COMMAND}
          text="Runs the focused metrics service, route, app-route, mocked pipeline, LLM executor, and verification metrics checks."
        />
        <ValidationCommand
          title="Smoke + Summary"
          command={METRICS_SMOKE_SUMMARY_COMMAND}
          text="Runs the same checks and prints the latest local daily summary when one exists."
        />
        <ValidationCommand
          title="Refresh Summaries"
          command={METRICS_REFRESH_COMMAND}
          text="Regenerates daily, weekly, and monthly summaries from existing raw metrics events."
        />
        <ValidationCommand
          title="Sample Data"
          command={METRICS_SAMPLE_COMMAND}
          text="Writes dev-only sample metrics files for UI validation under data/output/metrics."
        />
      </div>
      <div style={validationNoteStyle}>
        These commands validate local file-backed metrics behavior. They do not prove a real daily pipeline run,
        ECS scheduling, live external APIs, AWS cost data, or production alerting.
      </div>
      <div style={validationNoteStyle}>
        Smoke posture: first confirm Run State has readable local metrics, then run Smoke Check. Use Refresh Summaries only
        when raw local event files already exist; do not treat this page as permission to run production pipeline or AWS writes.
      </div>
    </SectionCard>
  );
}

export function EventFiles({ status }: { status: MetricsStatus }) {
  const categoryEntries = Object.entries(CATEGORY_CONFIG);
  const missingLabels = categoryEntries
    .filter(([key]) => !status.categories[key]?.exists)
    .map(([, config]) => config.label);
  const presentCount = categoryEntries.length - missingLabels.length;

  return (
    <SectionCard title="Diagnostics">
      <details>
        <summary style={diagnosticsSummaryStyle}>
          Data availability for generated metrics files
        </summary>
        <p style={diagnosticsTextStyle}>
          This area is for debugging the metrics pipeline itself. It shows whether each
          JSON / JSONL artifact family exists locally, how many files were found, and the
          latest file for each category. AWS production runs can exist even when local
          pipeline run files are missing.
        </p>
        <DiagnosticsOverview
          presentCount={presentCount}
          totalCount={categoryEntries.length}
          missingLabels={missingLabels}
          latestDailyDate={status.latestSummaryDate}
          signalPipelineGapCount={status.signalDatesMissingPipelineRuns.length}
          signalCollectorGapCount={status.signalDatesMissingCollectorRuns.length}
        />
        <div style={categoryGridStyle}>
          {categoryEntries.map(([key, config]) => (
            <CategoryCard key={key} label={config.label} status={status.categories[key] || EMPTY_CATEGORY_STATUS} />
          ))}
        </div>
      </details>
    </SectionCard>
  );
}

const EMPTY_CATEGORY_STATUS: CategoryStatus = {
  exists: false,
  fileCount: 0,
  latestDate: null,
  latestPath: null,
};

function DiagnosticsOverview({
  presentCount,
  totalCount,
  missingLabels,
  latestDailyDate,
  signalPipelineGapCount,
  signalCollectorGapCount,
}: {
  presentCount: number;
  totalCount: number;
  missingLabels: string[];
  latestDailyDate: string | null;
  signalPipelineGapCount: number;
  signalCollectorGapCount: number;
}) {
  return (
    <div style={diagnosticsOverviewStyle}>
      <div style={diagnosticsOverviewItemStyle}>
        <span style={diagnosticsOverviewLabelStyle}>Artifact Families</span>
        <strong style={diagnosticsOverviewValueStyle}>{presentCount} / {totalCount} present</strong>
      </div>
      <div style={diagnosticsOverviewItemStyle}>
        <span style={diagnosticsOverviewLabelStyle}>Latest Daily</span>
        <strong style={diagnosticsOverviewValueStyle}>{latestDailyDate || "None"}</strong>
      </div>
      <div style={diagnosticsOverviewItemStyle}>
        <span style={diagnosticsOverviewLabelStyle}>Missing</span>
        <strong style={diagnosticsOverviewValueStyle}>
          {missingLabels.length ? missingLabels.join(", ") : "None"}
        </strong>
      </div>
      <div style={diagnosticsOverviewItemStyle}>
        <span style={diagnosticsOverviewLabelStyle}>Signal / Pipeline Gaps</span>
        <strong style={diagnosticsOverviewValueStyle}>{formatUnitCount(signalPipelineGapCount, "date")}</strong>
      </div>
      <div style={diagnosticsOverviewItemStyle}>
        <span style={diagnosticsOverviewLabelStyle}>Signal / Collector Gaps</span>
        <strong style={diagnosticsOverviewValueStyle}>{formatUnitCount(signalCollectorGapCount, "date")}</strong>
      </div>
    </div>
  );
}

export function OpsAnalysis({
  title,
  summary,
  emptyMessage,
  emptyDetail,
  periodLabel,
}: {
  title: string;
  summary: MetricsSummary | null;
  emptyMessage: string;
  emptyDetail?: string;
  periodLabel: string;
}) {
  const items = summary ? buildAnalysisItems(summary, periodLabel) : [];
  const narrative = summary ? buildDailyNarrative(summary, periodLabel) : null;

  return (
    <SectionCard title={title}>
      {summary ? (
        <>
          <NarrativeBlock narrative={narrative} />
          <div style={analysisGridStyle}>
            {items.map((item) => (
              <div key={item.title} style={analysisCardStyle(item.tone)}>
                <div style={analysisTitleStyle}>{item.title}</div>
                <div style={analysisValueStyle}>{item.value}</div>
                <div style={analysisTextStyle}>{item.text}</div>
              </div>
            ))}
          </div>
        </>
      ) : (
        <MetricsEmptyState title={emptyMessage} detail={emptyDetail} />
      )}
    </SectionCard>
  );
}

export function PeriodOpsAnalysis({
  title,
  summaries,
  comparisonLabel,
  emptyMessage,
  emptyDetail,
}: {
  title: string;
  summaries: MetricsSummary[];
  comparisonLabel: string;
  emptyMessage: string;
  emptyDetail?: string;
}) {
  const latest = summaries.at(-1) || null;
  const previous = summaries.at(-2) || null;
  const items = latest ? buildPeriodAnalysisItems(latest, previous, comparisonLabel) : [];
  const narrative = latest ? buildPeriodNarrative(latest, previous, comparisonLabel) : null;

  return (
    <SectionCard title={title}>
      {latest ? (
        <>
          <NarrativeBlock narrative={narrative} />
          <div style={analysisGridStyle}>
            {items.map((item) => (
              <div key={item.title} style={analysisCardStyle(item.tone)}>
                <div style={analysisTitleStyle}>{item.title}</div>
                <div style={analysisValueStyle}>{item.value}</div>
                <div style={analysisTextStyle}>{item.text}</div>
              </div>
            ))}
          </div>
        </>
      ) : (
        <MetricsEmptyState title={emptyMessage} detail={emptyDetail} />
      )}
    </SectionCard>
  );
}

export function SummarySection({
  title,
  summary,
  emptyMessage,
  emptyDetail,
}: {
  title: string;
  summary: MetricsSummary | null;
  emptyMessage: string;
  emptyDetail?: string;
}) {
  return (
    <SectionCard title={title}>
      {summary ? (
        <div style={summaryLayoutStyle}>
          <SummaryGroup title="Pipeline" rows={summaryRows(summary.pipeline)} />
          <SummaryGroup title="Collectors" rows={summaryRows(summary.collectors)} />
          <SummaryGroup title="Timeline Loads" rows={summaryRows(summary.timeline_loads)} />
          <SummaryGroup title="LLM" rows={summaryRows(summary.llm)} />
          <SummaryGroup title="Verification" rows={summaryRows(summary.verification)} />
        </div>
      ) : (
        <MetricsEmptyState title={emptyMessage} detail={emptyDetail} />
      )}
    </SectionCard>
  );
}

export function TrendSection({
  title,
  summaries,
  comparisonLabel,
  emptyMessage,
  emptyDetail,
}: {
  title: string;
  summaries: MetricsSummary[];
  comparisonLabel: string;
  emptyMessage: string;
  emptyDetail?: string;
}) {
  const hasSummaryPayload = summaries.some(hasMetricPayload);

  return (
    <SectionCard title={title}>
      {summaries.length && hasSummaryPayload ? (
        <div style={tableScrollStyle}>
          <table style={trendTableStyle}>
            <thead>
              <tr>
                <th style={trendHeaderMetricStyle}>Metric</th>
                {summaries.map((summary) => (
                  <th key={summary.period_id || summary.date} style={trendHeaderStyle}>
                    {summary.period_id || summary.date || "Period"}
                  </th>
                ))}
                <th style={trendHeaderStyle}>{comparisonLabel}</th>
              </tr>
            </thead>
            <tbody>
              {TREND_METRICS.map((metric) => (
                <TrendRow
                  key={`${metric.section}.${metric.field}`}
                  metric={metric}
                  summaries={summaries}
                />
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <MetricsEmptyState title={emptyMessage} detail={emptyDetail} />
      )}
    </SectionCard>
  );
}

function hasMetricPayload(summary: MetricsSummary) {
  return Boolean(
    summary.pipeline ||
      summary.artifacts ||
      summary.collectors ||
      summary.signals ||
      summary.llm ||
      summary.verification,
  );
}

export const explanationGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
  gap: "12px",
} as const;

function NarrativeBlock({
  narrative,
}: {
  narrative: { achieved: string; missed: string; next: string } | null;
}) {
  if (!narrative) return null;

  return (
    <div style={narrativeStyle}>
      <div style={narrativeRowStyle}>
        <span style={narrativeLabelStyle}>Achieved</span>
        <span style={narrativeTextStyle}>{narrative.achieved}</span>
      </div>
      <div style={narrativeRowStyle}>
        <span style={narrativeLabelStyle}>Gaps</span>
        <span style={narrativeTextStyle}>{narrative.missed}</span>
      </div>
      <div style={narrativeRowStyle}>
        <span style={narrativeLabelStyle}>Next Focus</span>
        <span style={narrativeTextStyle}>{narrative.next}</span>
      </div>
    </div>
  );
}

function buildAnalysisItems(summary: MetricsSummary, periodLabel: string) {
  const pipelineSuccess = getBoolean(summary, "pipeline", "success");
  const collectorSuccessRate = getNumber(summary, "collectors", "success_rate");
  const llmSuccessRate = getNumber(summary, "llm", "success_rate");
  const fallbackRate = getNumber(summary, "llm", "fallback_rate");
  const downgradeRate = getNumber(summary, "verification", "downgrade_rate");
  const blockedActions = getNumber(summary, "verification", "action_blocked_count");
  const llmCalls = getNumber(summary, "llm", "call_count");
  const cost = getNumber(summary, "llm", "estimated_cost");

  return [
    {
      title: "Pipeline",
      value: pipelineSuccess === true ? "Healthy" : pipelineSuccess === false ? "Failed" : "Unknown",
      tone: pipelineSuccess === true ? "good" : pipelineSuccess === false ? "bad" : "neutral",
      text:
        pipelineSuccess === true
          ? `${periodLabel} pipeline completed successfully.`
          : pipelineSuccess === false
            ? `${periodLabel} pipeline reported a failed run.`
            : `${periodLabel} pipeline status is not available yet.`,
    },
    {
      title: "Collection",
      value: formatRate(collectorSuccessRate),
      tone: rateTone(collectorSuccessRate),
      text: `Collector success rate for ${periodLabel.toLowerCase()}.`,
    },
    {
      title: "LLM Reliability",
      value: formatRate(llmSuccessRate),
      tone: rateTone(llmSuccessRate),
      text: `${formatCount(llmCalls)} LLM calls with ${formatRate(fallbackRate)} fallback usage.`,
    },
    {
      title: "Verification Gate",
      value: `${formatRate(downgradeRate)} downgrade`,
      tone: blockedActions && blockedActions > 0 ? "watch" : "neutral",
      text: `${formatCount(blockedActions)} downstream actions were blocked by verification.`,
    },
    {
      title: "Estimated Cost",
      value: formatCurrency(cost),
      tone: "neutral",
      text: `Rough LLM cost captured in metrics events for ${periodLabel.toLowerCase()}.`,
    },
  ];
}

function buildDailyNarrative(summary: MetricsSummary, periodLabel: string) {
  const pipelineSuccess = getBoolean(summary, "pipeline", "success");
  const collectorSuccessRate = getNumber(summary, "collectors", "success_rate");
  const llmSuccessRate = getNumber(summary, "llm", "success_rate");
  const fallbackRate = getNumber(summary, "llm", "fallback_rate");
  const blockedActions = getNumber(summary, "verification", "action_blocked_count");
  const downgradeRate = getNumber(summary, "verification", "downgrade_rate");
  const llmCalls = getNumber(summary, "llm", "call_count");
  const cost = getNumber(summary, "llm", "estimated_cost");
  const itemsWritten = getNumber(summary, "collectors", "total_items_written");

  const achieved =
    pipelineSuccess === true
      ? `${periodLabel} pipeline completed and produced ${formatCount(itemsWritten)} written collector items, ${formatCount(llmCalls)} LLM calls, and ${formatCurrency(cost)} estimated LLM cost.`
      : pipelineSuccess === false
        ? `${periodLabel} pipeline produced metrics, but the run ended in a failed state.`
        : `${periodLabel} metrics exist, but pipeline completion status is not available.`;

  const gaps = [
    collectorSuccessRate !== null && collectorSuccessRate < 1
      ? `collector success is ${formatRate(collectorSuccessRate)}`
      : null,
    llmSuccessRate !== null && llmSuccessRate < 1
      ? `LLM success is ${formatRate(llmSuccessRate)}`
      : null,
    fallbackRate !== null && fallbackRate > 0
      ? `fallback was used on ${formatRate(fallbackRate)} of LLM calls`
      : null,
    blockedActions !== null && blockedActions > 0
      ? `${formatCount(blockedActions)} downstream actions were blocked`
      : null,
  ].filter(Boolean);

  const next = [
    pipelineSuccess === false ? "inspect pipeline failure logs" : null,
    collectorSuccessRate !== null && collectorSuccessRate < 1
      ? "review failed collectors and source availability"
      : null,
    fallbackRate !== null && fallbackRate > 0 ? "check whether model fallback is expected" : null,
    downgradeRate !== null && downgradeRate > 0 ? "sample downgraded insights for evidence quality" : null,
  ].filter(Boolean);

  return {
    achieved,
    missed: gaps.length ? gaps.join("; ") + "." : "No major operational gaps are visible in today's metrics.",
    next: next.length ? next.join("; ") + "." : "Continue monitoring the next run for regressions in collector success, fallback rate, and verification blocks.",
  };
}

function buildPeriodAnalysisItems(
  latest: MetricsSummary,
  previous: MetricsSummary | null,
  comparisonLabel: string,
) {
  const period = latest.period_id || latest.date || "latest period";
  const dateCount = latest.date_count;
  const llmCalls = getNumber(latest, "llm", "call_count");
  const fallbackRate = getNumber(latest, "llm", "fallback_rate");
  const downgradeRate = getNumber(latest, "verification", "downgrade_rate");
  const blockedActions = getNumber(latest, "verification", "action_blocked_count");
  const collectorSuccessRate = getNumber(latest, "collectors", "success_rate");
  const previousFallbackRate = previous ? getNumber(previous, "llm", "fallback_rate") : null;
  const fallbackChange = calculateChange(previousFallbackRate, fallbackRate);

  return [
    {
      title: "Coverage",
      value: formatUnitCount(dateCount, "day"),
      tone: "neutral",
      text: `${period} includes ${formatUnitCount(dateCount, "daily summary file")}.`,
    },
    {
      title: "Collection Health",
      value: formatRate(collectorSuccessRate),
      tone: rateTone(collectorSuccessRate),
      text: "Collector success across the period.",
    },
    {
      title: "LLM Volume",
      value: formatCount(llmCalls),
      tone: "neutral",
      text: "Total LLM calls recorded for this period.",
    },
    {
      title: `${comparisonLabel} Fallback`,
      value: formatComparison(fallbackChange),
      tone: fallbackChange === null ? "neutral" : fallbackChange > 0 ? "bad" : fallbackChange < 0 ? "good" : "neutral",
      text: `Fallback rate is ${formatRate(fallbackRate)} in the latest period.`,
    },
    {
      title: "Verification Pressure",
      value: `${formatRate(downgradeRate)} downgrade`,
      tone: blockedActions && blockedActions > 0 ? "watch" : "neutral",
      text: `${formatCount(blockedActions)} actions blocked in the latest period.`,
    },
  ];
}

function buildPeriodNarrative(
  latest: MetricsSummary,
  previous: MetricsSummary | null,
  comparisonLabel: string,
) {
  const period = latest.period_id || latest.date || "latest period";
  const dateCount = latest.date_count;
  const collectorSuccessRate = getNumber(latest, "collectors", "success_rate");
  const llmCalls = getNumber(latest, "llm", "call_count");
  const llmSuccessRate = getNumber(latest, "llm", "success_rate");
  const fallbackRate = getNumber(latest, "llm", "fallback_rate");
  const downgradeRate = getNumber(latest, "verification", "downgrade_rate");
  const blockedActions = getNumber(latest, "verification", "action_blocked_count");
  const cost = getNumber(latest, "llm", "estimated_cost");
  const previousFallbackRate = previous ? getNumber(previous, "llm", "fallback_rate") : null;
  const previousCost = previous ? getNumber(previous, "llm", "estimated_cost") : null;
  const fallbackChange = calculateChange(previousFallbackRate, fallbackRate);
  const costChange = calculateChange(previousCost, cost);

  const achieved = `${period} covers ${formatUnitCount(dateCount, "daily summary")}, ${formatUnitCount(llmCalls, "LLM call")}, ${formatRate(collectorSuccessRate)} collector success, and ${formatCurrency(cost)} estimated LLM cost.`;

  const gaps = [
    collectorSuccessRate !== null && collectorSuccessRate < 1
      ? `collector reliability is not perfect at ${formatRate(collectorSuccessRate)}`
      : null,
    llmSuccessRate !== null && llmSuccessRate < 1
      ? `LLM success rate is ${formatRate(llmSuccessRate)}`
      : null,
    fallbackRate !== null && fallbackRate > 0
      ? `fallback rate is ${formatRate(fallbackRate)}`
      : null,
    blockedActions !== null && blockedActions > 0
      ? `${formatCount(blockedActions)} actions were blocked by verification`
      : null,
  ].filter(Boolean);

  const next = [
    fallbackChange !== null && fallbackChange > 0
      ? `${comparisonLabel} fallback increased by ${formatComparison(fallbackChange)}`
      : null,
    costChange !== null && costChange > 25
      ? `${comparisonLabel} estimated cost increased by ${formatComparison(costChange)}`
      : null,
    downgradeRate !== null && downgradeRate > 0
      ? "review downgraded insights to separate healthy evidence gating from source-quality problems"
      : null,
    collectorSuccessRate !== null && collectorSuccessRate < 1
      ? "prioritize the least reliable collector before expanding metrics scope"
      : null,
  ].filter(Boolean);

  return {
    achieved,
    missed: gaps.length ? gaps.join("; ") + "." : `No major operational gaps are visible in ${period}.`,
    next: next.length ? next.join("; ") + "." : `Use the next ${comparisonLabel} comparison to watch for fallback, cost, collector, and verification regressions.`,
  };
}

function TrendRow({
  metric,
  summaries,
}: {
  metric: TrendMetric;
  summaries: MetricsSummary[];
}) {
  const values = summaries.map((summary) => getMetricValue(summary, metric));
  const latest = values.at(-1);
  const previous = values.at(-2);
  const change = calculateChange(previous, latest);

  return (
    <tr>
      <th style={trendMetricCellStyle}>{metric.label}</th>
      {values.map((value, index) => (
        <td key={`${metric.label}-${index}`} style={trendCellStyle}>
          {formatTrendCell(summaries[index], metric, value)}
        </td>
      ))}
      <td style={trendCellStyle}>
        <span style={comparisonPillStyle(change)}>{formatComparison(change)}</span>
      </td>
    </tr>
  );
}

function getMetricValue(summary: MetricsSummary, metric: TrendMetric) {
  const section = summary[metric.section];
  if (!section) return null;
  const value = section[metric.field];
  if (typeof value === "number") return value;

  if (metric.section === "pipeline" && metric.field === "success_rate") {
    const success = section.success;
    if (typeof success === "boolean") return success ? 1 : 0;
  }

  if (metric.section === "pipeline" && metric.field === "avg_duration_seconds") {
    const duration = section.duration_seconds;
    if (typeof duration === "number") return duration;
  }

  return null;
}

function getNumber(
  summary: MetricsSummary,
  section: TrendMetric["section"],
  field: string,
) {
  const payload = summary[section];
  if (!payload) return null;
  const value = payload[field];
  return typeof value === "number" ? value : null;
}

function getBoolean(
  summary: MetricsSummary,
  section: TrendMetric["section"],
  field: string,
) {
  const payload = summary[section];
  if (!payload) return null;
  const value = payload[field];
  return typeof value === "boolean" ? value : null;
}

function calculateChange(previous: number | null | undefined, latest: number | null | undefined) {
  if (typeof previous !== "number" || typeof latest !== "number") return null;
  if (previous === 0) return latest === 0 ? 0 : null;
  return ((latest - previous) / Math.abs(previous)) * 100;
}

function formatTrendValue(value: number | null | undefined, format: TrendMetric["format"]) {
  if (typeof value !== "number") return "N/A";
  if (format === "percent") return `${Math.round(value * 1000) / 10}%`;
  if (format === "currency") return `$${value.toFixed(2)}`;
  if (Math.abs(value) >= 1000) return Math.round(value).toLocaleString("en-US");
  return String(Math.round(value * 100) / 100);
}

function formatTrendCell(
  summary: MetricsSummary,
  metric: TrendMetric,
  value: number | null | undefined,
) {
  if (typeof value === "number") return formatTrendValue(value, metric.format);

  if (
    metric.section === "pipeline" &&
    ["success_rate", "avg_duration_seconds"].includes(metric.field) &&
    getNumber(summary, "pipeline", "run_count") === 0
  ) {
    return "No local run record";
  }

  if (
    metric.section === "collectors" &&
    metric.field === "success_rate" &&
    getNumber(summary, "collectors", "total_runs") === 0
  ) {
    return "No local run record";
  }

  return "N/A";
}

function formatComparison(change: number | null) {
  if (change === null) return "N/A";
  if (change === 0) return "0%";
  const prefix = change > 0 ? "+" : "";
  return `${prefix}${change.toFixed(1)}%`;
}

function formatRate(value: number | null | undefined) {
  if (typeof value !== "number") return "N/A";
  return `${Math.round(value * 1000) / 10}%`;
}

function formatCount(value: number | null | undefined) {
  if (typeof value !== "number") return "N/A";
  return Math.round(value).toLocaleString("en-US");
}

function formatUnitCount(value: number | null | undefined, unit: string) {
  const irregularPlurals: Record<string, string> = {
    day: "days",
    "daily summary": "daily summaries",
  };
  const pluralUnit = irregularPlurals[unit] ?? `${unit}s`;
  if (typeof value !== "number") return `N/A ${pluralUnit}`;
  const rounded = Math.round(value);
  return `${rounded.toLocaleString("en-US")} ${rounded === 1 ? unit : pluralUnit}`;
}

function formatCurrency(value: number | null | undefined) {
  if (typeof value !== "number") return "N/A";
  return `$${value.toFixed(2)}`;
}

function rateTone(value: number | null | undefined) {
  if (typeof value !== "number") return "neutral";
  if (value >= 0.95) return "good";
  if (value >= 0.8) return "watch";
  return "bad";
}

function summaryRows(payload?: Record<string, unknown>) {
  if (!payload) return [];
  return Object.entries(payload).map(([key, value]) => ({
    label: humanizeKey(key),
    value: formatUnknown(value),
  }));
}

function humanizeKey(value: string) {
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function formatUnknown(value: unknown) {
  if (value === null || value === undefined) return "N/A";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (Array.isArray(value)) return value.length ? value.join(", ") : "None";
  return String(value);
}

function MetricCard({
  label,
  value,
  compact = false,
}: {
  label: string;
  value: string;
  compact?: boolean;
}) {
  return (
    <div style={metricCardStyle}>
      <div style={metricLabelStyle}>{label}</div>
      <div style={{ ...metricValueStyle, fontSize: compact ? "14px" : "24px" }}>{value}</div>
    </div>
  );
}

function ValidationCommand({
  title,
  command,
  text,
}: {
  title: string;
  command: string;
  text: string;
}) {
  return (
    <div style={validationCardStyle}>
      <div style={validationTitleStyle}>{title}</div>
      <code style={commandStyle}>{command}</code>
      <div style={validationTextStyle}>{text}</div>
    </div>
  );
}

function MetricsEmptyState({
  title,
  detail,
}: {
  title: string;
  detail?: string;
}) {
  return (
    <div style={emptyStateStyle}>
      <div style={emptyStateTitleStyle}>{title}</div>
      {detail ? <div style={emptyStateDetailStyle}>{detail}</div> : null}
    </div>
  );
}

function CategoryCard({ label, status }: { label: string; status: CategoryStatus }) {
  return (
    <div style={categoryCardStyle}>
      <div style={categoryHeaderStyle}>
        <span style={categoryTitleStyle}>{label}</span>
        <span style={statusPillStyle(status.exists)}>{status.exists ? "Present" : "Missing"}</span>
      </div>
      <SummaryRow label="Files" value={String(status.fileCount)} />
      <SummaryRow label="Latest Date" value={status.latestDate || "None"} />
      <SummaryRow
        label="Latest File"
        value={status.latestPath ? status.latestPath.split(/[\\/]/).at(-1) || status.latestPath : "None"}
        title={status.latestPath || undefined}
      />
    </div>
  );
}

function SummaryGroup({
  title,
  rows,
}: {
  title: string;
  rows: Array<{ label: string; value: string }>;
}) {
  return (
    <div style={summaryColumnStyle}>
      <h3 style={subheadStyle}>{title}</h3>
      {rows.length ? (
        rows.map((row) => <SummaryRow key={row.label} label={row.label} value={row.value} />)
      ) : (
        <div style={mutedTextStyle}>No data</div>
      )}
    </div>
  );
}

function SummaryRow({
  label,
  value,
  title,
}: {
  label: string;
  value: string;
  title?: string;
}) {
  return (
    <div style={summaryRowStyle}>
      <span style={summaryLabelStyle}>{label}</span>
      <span style={summaryValueStyle} title={title}>
        {value}
      </span>
    </div>
  );
}

const toolbarStyle = {
  display: "flex",
  gap: "10px",
  flexWrap: "wrap",
  alignItems: "center",
  marginBottom: "18px",
} as const;

const primaryLinkStyle = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  border: "1px solid var(--app-primary-action-border)",
  borderRadius: "8px",
  background: "var(--app-primary-action-bg)",
  color: "var(--app-primary-action-fg)",
  padding: "10px 14px",
  fontWeight: 750,
  textDecoration: "none",
} as const;

const secondaryLinkStyle = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  border: "1px solid var(--app-secondary-action-border)",
  borderRadius: "8px",
  background: "var(--app-secondary-action-bg)",
  color: "var(--app-secondary-action-fg)",
  padding: "10px 14px",
  fontWeight: 750,
  textDecoration: "none",
} as const;

const statusGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
  gap: "12px",
} as const;

const categoryGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
  gap: "12px",
} as const;

const infoBlockStyle = {
  border: "1px solid rgba(148, 163, 184, 0.18)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  padding: "14px",
} as const;

const infoTitleStyle = {
  color: "var(--app-text-strong)",
  fontSize: "14px",
  fontWeight: 850,
  marginBottom: "6px",
} as const;

const infoTextStyle = {
  color: "var(--app-text-muted)",
  fontSize: "13px",
  lineHeight: 1.55,
} as const;

const analysisGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))",
  gap: "12px",
} as const;

const narrativeStyle = {
  display: "grid",
  gap: "10px",
  border: "1px solid rgba(148, 163, 184, 0.18)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  padding: "14px",
  marginBottom: "14px",
} as const;

const narrativeRowStyle = {
  display: "grid",
  gridTemplateColumns: "120px minmax(0, 1fr)",
  gap: "12px",
  alignItems: "start",
} as const;

const narrativeLabelStyle = {
  color: "var(--app-text-muted)",
  fontSize: "12px",
  fontWeight: 850,
  textTransform: "uppercase",
} as const;

const narrativeTextStyle = {
  color: "var(--app-text-strong)",
  fontSize: "14px",
  lineHeight: 1.6,
  fontWeight: 600,
} as const;

function analysisCardStyle(tone: string) {
  const colors =
    tone === "good"
      ? { border: "#bbf7d0", background: "#f0fdf4" }
      : tone === "bad"
        ? { border: "#fecaca", background: "#fef2f2" }
        : tone === "watch"
          ? { border: "#fed7aa", background: "#fff7ed" }
          : { border: "rgba(148, 163, 184, 0.18)", background: "var(--app-surface-muted-bg)" };

  return {
    border: `1px solid ${colors.border}`,
    borderRadius: "8px",
    background: colors.background,
    padding: "14px",
    minWidth: 0,
  } as const;
}

const analysisTitleStyle = {
  color: "var(--app-text-muted)",
  fontSize: "12px",
  fontWeight: 800,
  textTransform: "uppercase",
} as const;

const analysisValueStyle = {
  color: "var(--app-text-strong)",
  fontSize: "22px",
  fontWeight: 850,
  marginTop: "8px",
} as const;

const analysisTextStyle = {
  color: "var(--app-text-muted)",
  fontSize: "13px",
  lineHeight: 1.5,
  marginTop: "8px",
} as const;

const summaryLayoutStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
  gap: "14px",
} as const;

const tableScrollStyle = {
  overflowX: "auto",
  border: "1px solid rgba(148, 163, 184, 0.14)",
  borderRadius: "8px",
} as const;

const trendTableStyle = {
  width: "100%",
  minWidth: "760px",
  borderCollapse: "separate",
  borderSpacing: 0,
  background: "var(--app-surface-bg)",
  fontSize: "13px",
} as const;

const trendHeaderMetricStyle = {
  width: "240px",
  background: "var(--app-surface-muted-bg)",
  color: "var(--app-text-muted)",
  textAlign: "left",
  padding: "12px",
  borderBottom: "1px solid rgba(148, 163, 184, 0.18)",
  fontWeight: 850,
} as const;

const trendHeaderStyle = {
  background: "var(--app-surface-muted-bg)",
  color: "var(--app-text-muted)",
  textAlign: "right",
  padding: "12px",
  borderBottom: "1px solid rgba(148, 163, 184, 0.18)",
  fontWeight: 850,
  whiteSpace: "nowrap",
} as const;

const trendMetricCellStyle = {
  color: "var(--app-text-strong)",
  textAlign: "left",
  padding: "11px 12px",
  borderBottom: "1px solid rgba(148, 163, 184, 0.12)",
  fontWeight: 750,
  background: "var(--app-surface-bg)",
} as const;

const trendCellStyle = {
  color: "var(--app-text-strong)",
  textAlign: "right",
  padding: "11px 12px",
  borderBottom: "1px solid rgba(148, 163, 184, 0.12)",
  fontWeight: 650,
  whiteSpace: "nowrap",
} as const;

const summaryColumnStyle = {
  border: "1px solid rgba(148, 163, 184, 0.18)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  padding: "14px",
  display: "grid",
  gap: "8px",
} as const;

const metricCardStyle = {
  border: "1px solid rgba(148, 163, 184, 0.18)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  padding: "14px",
  minWidth: 0,
} as const;

const metricLabelStyle = {
  color: "var(--app-text-muted)",
  fontSize: "12px",
  fontWeight: 750,
  textTransform: "uppercase",
} as const;

const metricValueStyle = {
  color: "var(--app-text-strong)",
  fontWeight: 850,
  marginTop: "8px",
  overflowWrap: "anywhere",
} as const;

const runStateFactsStyle = {
  display: "grid",
  gap: "8px",
  minWidth: "240px",
} as const;

const runStateTitleStyle = {
  color: "#0f172a",
  fontSize: "18px",
  fontWeight: 850,
  marginBottom: "8px",
} as const;

const runStateTextStyle = {
  color: "#475569",
  fontSize: "14px",
  lineHeight: 1.6,
} as const;

const validationGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
  gap: "12px",
} as const;

const validationCardStyle = {
  border: "1px solid #e5e7eb",
  borderRadius: "12px",
  background: "#f8fafc",
  padding: "14px",
  display: "grid",
  gap: "9px",
  minWidth: 0,
} as const;

const validationTitleStyle = {
  color: "#0f172a",
  fontSize: "14px",
  fontWeight: 850,
} as const;

const commandStyle = {
  display: "block",
  border: "1px solid #dbe4ee",
  borderRadius: "8px",
  background: "#ffffff",
  color: "#111827",
  padding: "8px",
  fontSize: "12px",
  lineHeight: 1.5,
  overflowWrap: "anywhere",
} as const;

const validationTextStyle = {
  color: "#475569",
  fontSize: "13px",
  lineHeight: 1.55,
} as const;

const validationNoteStyle = {
  marginTop: "12px",
  border: "1px solid #fed7aa",
  borderRadius: "10px",
  background: "#fff7ed",
  color: "#9a3412",
  padding: "12px",
  fontSize: "13px",
  lineHeight: 1.55,
  fontWeight: 650,
} as const;

const emptyStateStyle = {
  border: "1px solid rgba(148, 163, 184, 0.18)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  padding: "14px",
  display: "grid",
  gap: "8px",
} as const;

const emptyStateTitleStyle = {
  color: "var(--app-text-strong)",
  fontSize: "14px",
  fontWeight: 850,
} as const;

const emptyStateDetailStyle = {
  color: "var(--app-text-muted)",
  fontSize: "13px",
  lineHeight: 1.55,
} as const;

const categoryCardStyle = {
  border: "1px solid rgba(148, 163, 184, 0.18)",
  borderRadius: "8px",
  background: "var(--app-surface-bg)",
  padding: "14px",
  display: "grid",
  gap: "8px",
  minWidth: 0,
} as const;

const categoryHeaderStyle = {
  display: "flex",
  justifyContent: "space-between",
  gap: "10px",
  alignItems: "center",
} as const;

const categoryTitleStyle = {
  color: "var(--app-text-strong)",
  fontSize: "15px",
  fontWeight: 800,
} as const;

const diagnosticsSummaryStyle = {
  cursor: "pointer",
  color: "var(--app-text-strong)",
  fontWeight: 800,
  marginBottom: "12px",
} as const;

const diagnosticsTextStyle = {
  color: "var(--app-text-muted)",
  fontSize: "13px",
  lineHeight: 1.55,
  marginTop: 0,
  marginBottom: "14px",
} as const;

const diagnosticsOverviewStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
  gap: "10px",
  marginBottom: "14px",
} as const;

const diagnosticsOverviewItemStyle = {
  border: "1px solid rgba(148, 163, 184, 0.18)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  padding: "12px",
  minWidth: 0,
} as const;

const diagnosticsOverviewLabelStyle = {
  display: "block",
  color: "var(--app-text-muted)",
  fontSize: "11px",
  fontWeight: 800,
  textTransform: "uppercase",
  marginBottom: "6px",
} as const;

const diagnosticsOverviewValueStyle = {
  display: "block",
  color: "var(--app-text-strong)",
  fontSize: "13px",
  lineHeight: 1.45,
  overflowWrap: "anywhere",
} as const;

function statusPillStyle(exists: boolean) {
  return {
    border: `1px solid ${exists ? "#bbf7d0" : "#fed7aa"}`,
    borderRadius: "999px",
    background: exists ? "#f0fdf4" : "#fff7ed",
    color: exists ? "#166534" : "#9a3412",
    padding: "4px 8px",
    fontSize: "12px",
    fontWeight: 750,
    whiteSpace: "nowrap",
  } as const;
}

function comparisonPillStyle(change: number | null) {
  const isUp = typeof change === "number" && change > 0;
  const isDown = typeof change === "number" && change < 0;

  return {
    display: "inline-flex",
    justifyContent: "center",
    minWidth: "68px",
    border: `1px solid ${isUp ? "#bbf7d0" : isDown ? "#fecaca" : "#e5e7eb"}`,
    borderRadius: "999px",
    background: isUp ? "#f0fdf4" : isDown ? "#fef2f2" : "#f8fafc",
    color: isUp ? "#166534" : isDown ? "#991b1b" : "#64748b",
    padding: "4px 8px",
    fontSize: "12px",
    fontWeight: 800,
  } as const;
}

const subheadStyle = {
  margin: 0,
  color: "var(--app-text-strong)",
  fontSize: "16px",
  fontWeight: 850,
} as const;

const summaryRowStyle = {
  display: "grid",
  gridTemplateColumns: "120px minmax(0, 1fr)",
  gap: "10px",
  alignItems: "baseline",
  fontSize: "13px",
} as const;

const summaryLabelStyle = {
  color: "var(--app-text-muted)",
  fontWeight: 700,
} as const;

const summaryValueStyle = {
  color: "var(--app-text-strong)",
  fontWeight: 650,
  overflowWrap: "anywhere",
} as const;

const mutedTextStyle = {
  color: "var(--app-text-muted)",
  fontSize: "14px",
} as const;

function runStateBoxStyle(tone: "good" | "watch" | "neutral") {
  const colors =
    tone === "good"
      ? { border: "#bbf7d0", background: "#f0fdf4" }
      : tone === "watch"
        ? { border: "#fed7aa", background: "#fff7ed" }
        : { border: "#e5e7eb", background: "#f8fafc" };

  return {
    border: `1px solid ${colors.border}`,
    borderRadius: "14px",
    background: colors.background,
    padding: "16px",
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
    gap: "16px",
    alignItems: "start",
  } as const;
}
