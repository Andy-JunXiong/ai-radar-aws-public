import type { TodayMaterialityResult } from "./todayOverviewMateriality";

export type TodayOverviewState =
  | "load_failed"
  | "stale_or_partial"
  | "current_no_material_change"
  | "current_change_without_convergence"
  | "current_with_convergence";

export type TodayOverviewGateCode =
  | "latest_signal_activity_not_today"
  | "pipeline_run_missing"
  | "collector_run_missing"
  | "daily_summary_date_mismatch"
  | "pipeline_unsuccessful"
  | "signals_artifact_missing"
  | "daily_radar_artifact_missing"
  | "artifact_write_failed"
  | "collector_coverage_incomplete"
  | "materiality_incomplete"
  | "radar_artifact_not_today"
  | "signal_after_page_as_of";

export type TodayOverviewStateInput = {
  operatorDate: string;
  operatorTimeZone: string;
  failedReadGroups: string[];
  metricsStatus: {
    latest_signal_activity_date?: unknown;
    signal_dates_missing_pipeline_runs?: unknown;
    signal_dates_missing_collector_runs?: unknown;
  };
  dailySummary: {
    date?: unknown;
    summary?: {
      pipeline?: { success?: unknown };
      artifacts?: {
        signals_file_written?: unknown;
        daily_radar_file_written?: unknown;
        failed_write_count?: unknown;
      };
      collectors?: { coverage?: { completeness?: unknown } };
    };
  };
  radarArtifactDates: Array<{ name: string; value: unknown }>;
  newestDisplayedSignalAt: string | null;
  pageAsOf: string;
  materiality: TodayMaterialityResult;
  governedConvergenceCount: number;
};

export type TodayOverviewStateResult = {
  state: TodayOverviewState;
  headline: string;
  failedReadGroups: string[];
  failedGates: TodayOverviewGateCode[];
};

export type TodayObservedSignal = {
  id?: unknown;
  signal_id?: unknown;
  title?: unknown;
  collected_at?: unknown;
  status?: unknown;
  score?: unknown;
};

const HEADLINES: Record<TodayOverviewState, string> = {
  load_failed: "Today's intelligence could not be loaded.",
  stale_or_partial: "Today's view is incomplete.",
  current_no_material_change: "Nothing materially changed today.",
  current_change_without_convergence:
    "New activity is visible, but it has not converged into a governed review candidate.",
  current_with_convergence: "New activity and governed review context are available.",
};

function stringList(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

function dateKey(value: unknown, operatorTimeZone: string): string | null {
  if (typeof value !== "string" || !value.trim()) return null;
  const normalized = value.trim();
  if (/^\d{4}-\d{2}-\d{2}$/.test(normalized)) return normalized;
  const parsed = new Date(normalized);
  if (Number.isNaN(parsed.getTime())) return null;
  const parts = new Intl.DateTimeFormat("en-AU", {
    timeZone: operatorTimeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(parsed);
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return `${values.year}-${values.month}-${values.day}`;
}

function isTodayDate(value: unknown, operatorDate: string, operatorTimeZone: string): boolean {
  return dateKey(value, operatorTimeZone) === operatorDate;
}

function observedSignalId(signal: TodayObservedSignal): string {
  const value = signal.signal_id ?? signal.id;
  return typeof value === "string" ? value.trim() : "";
}

function observedScore(value: unknown): number {
  if (value === null || value === undefined || value === "") return -Infinity;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : -Infinity;
}

export function selectTodayObservedSignals<T extends TodayObservedSignal>(
  signals: T[],
  operatorDate: string,
  operatorTimeZone: string,
  limit = 5,
): T[] {
  const seen = new Set<string>();
  return signals
    .filter(
      (signal) =>
        signal.status !== "rejected" &&
        dateKey(signal.collected_at, operatorTimeZone) === operatorDate,
    )
    .filter((signal) => {
      const id = observedSignalId(signal);
      if (!id || seen.has(id)) return false;
      seen.add(id);
      return true;
    })
    .sort((a, b) => {
      const scoreDelta = observedScore(b.score) - observedScore(a.score);
      if (scoreDelta) return scoreDelta;
      const collectedDelta =
        new Date(String(b.collected_at || "")).getTime() -
        new Date(String(a.collected_at || "")).getTime();
      return collectedDelta || observedSignalId(a).localeCompare(observedSignalId(b));
    })
    .slice(0, Math.max(0, limit));
}

export function evaluateTodayOverviewState(input: TodayOverviewStateInput): TodayOverviewStateResult {
  const failedReadGroups = [...new Set(input.failedReadGroups.filter(Boolean))];
  if (failedReadGroups.length) {
    return {
      state: "load_failed",
      headline: HEADLINES.load_failed,
      failedReadGroups,
      failedGates: [],
    };
  }

  const failedGates: TodayOverviewGateCode[] = [];
  const status = input.metricsStatus;
  const summary = input.dailySummary.summary;
  const artifacts = summary?.artifacts;

  if (status.latest_signal_activity_date !== input.operatorDate) {
    failedGates.push("latest_signal_activity_not_today");
  }
  if (stringList(status.signal_dates_missing_pipeline_runs).includes(input.operatorDate)) {
    failedGates.push("pipeline_run_missing");
  }
  if (stringList(status.signal_dates_missing_collector_runs).includes(input.operatorDate)) {
    failedGates.push("collector_run_missing");
  }
  if (input.dailySummary.date !== input.operatorDate) {
    failedGates.push("daily_summary_date_mismatch");
  }
  if (summary?.pipeline?.success !== true) failedGates.push("pipeline_unsuccessful");
  if (artifacts?.signals_file_written !== true) failedGates.push("signals_artifact_missing");
  if (artifacts?.daily_radar_file_written !== true) failedGates.push("daily_radar_artifact_missing");
  if (artifacts?.failed_write_count !== 0) failedGates.push("artifact_write_failed");
  if (summary?.collectors?.coverage?.completeness !== "complete") {
    failedGates.push("collector_coverage_incomplete");
  }
  if (input.materiality.completeness !== "complete") failedGates.push("materiality_incomplete");
  if (
    input.radarArtifactDates.some(
      (artifact) => !isTodayDate(artifact.value, input.operatorDate, input.operatorTimeZone),
    )
  ) {
    failedGates.push("radar_artifact_not_today");
  }

  if (input.newestDisplayedSignalAt) {
    const newest = new Date(input.newestDisplayedSignalAt).getTime();
    const asOf = new Date(input.pageAsOf).getTime();
    if (Number.isNaN(newest) || Number.isNaN(asOf) || newest > asOf) {
      failedGates.push("signal_after_page_as_of");
    }
  }

  const uniqueFailedGates = [...new Set(failedGates)];
  if (uniqueFailedGates.length) {
    return {
      state: "stale_or_partial",
      headline: HEADLINES.stale_or_partial,
      failedReadGroups: [],
      failedGates: uniqueFailedGates,
    };
  }

  const state: TodayOverviewState =
    input.materiality.materialChangeCount === 0
      ? "current_no_material_change"
      : input.governedConvergenceCount === 0
        ? "current_change_without_convergence"
        : "current_with_convergence";

  return { state, headline: HEADLINES[state], failedReadGroups: [], failedGates: [] };
}
