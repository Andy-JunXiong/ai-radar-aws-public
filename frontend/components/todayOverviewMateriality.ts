export const TODAY_MATERIALITY_CONTRACT_VERSION = "signal_importance_high_v1" as const;

export type TodayMaterialitySignal = {
  id?: unknown;
  signal_id?: unknown;
  collected_at?: unknown;
  status?: unknown;
  importance_level?: unknown;
  importance_reason?: unknown;
};

export type TodayMaterialityIssueCode =
  | "missing_signal_id"
  | "invalid_importance_level"
  | "invalid_importance_reason";

export type TodayMaterialityIssue = {
  signalId: string | null;
  reasonCode: TodayMaterialityIssueCode;
};

export type TodayMaterialityResult = {
  contractVersion: typeof TODAY_MATERIALITY_CONTRACT_VERSION;
  operatorDate: string;
  operatorTimeZone: string;
  completeness: "complete" | "incomplete";
  materialChangeCount: number;
  materialSignalIds: string[];
  materialReasonsBySignalId: Record<string, string[]>;
  issues: TodayMaterialityIssue[];
};

const VALID_IMPORTANCE_LEVELS = new Set(["high", "medium", "low"]);

function signalId(signal: TodayMaterialitySignal): string {
  const value = signal.signal_id ?? signal.id;
  return typeof value === "string" ? value.trim() : "";
}

function operatorDateKey(value: unknown, timeZone: string): string | null {
  if (typeof value !== "string" || !value.trim()) return null;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return null;

  const parts = new Intl.DateTimeFormat("en-AU", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(parsed);
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return `${values.year}-${values.month}-${values.day}`;
}

function importanceReasons(value: unknown): string[] | null {
  if (!Array.isArray(value)) return null;
  if (!value.every((reason) => typeof reason === "string" && reason.trim())) {
    return null;
  }
  return value.map((reason) => reason.trim());
}

export function evaluateTodayMateriality(
  signals: TodayMaterialitySignal[],
  operatorDate: string,
  operatorTimeZone: string,
): TodayMaterialityResult {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(operatorDate)) {
    throw new Error("operatorDate must use YYYY-MM-DD");
  }

  const seenSignalIds = new Set<string>();
  const materialSignalIds: string[] = [];
  const materialReasonsBySignalId: Record<string, string[]> = {};
  const issues: TodayMaterialityIssue[] = [];

  for (const signal of signals) {
    if (operatorDateKey(signal.collected_at, operatorTimeZone) !== operatorDate) {
      continue;
    }
    if (signal.status === "rejected") continue;

    const id = signalId(signal);
    if (!id) {
      issues.push({ signalId: null, reasonCode: "missing_signal_id" });
      continue;
    }
    if (seenSignalIds.has(id)) continue;
    seenSignalIds.add(id);

    const level = signal.importance_level;
    if (typeof level !== "string" || !VALID_IMPORTANCE_LEVELS.has(level)) {
      issues.push({ signalId: id, reasonCode: "invalid_importance_level" });
      continue;
    }

    const reasons = importanceReasons(signal.importance_reason);
    const reasonsRequired = level === "high" || level === "medium";
    if (reasons === null || (reasonsRequired && reasons.length === 0)) {
      issues.push({ signalId: id, reasonCode: "invalid_importance_reason" });
      continue;
    }

    if (level === "high") {
      materialSignalIds.push(id);
      materialReasonsBySignalId[id] = reasons;
    }
  }

  return {
    contractVersion: TODAY_MATERIALITY_CONTRACT_VERSION,
    operatorDate,
    operatorTimeZone,
    completeness: issues.length ? "incomplete" : "complete",
    materialChangeCount: materialSignalIds.length,
    materialSignalIds,
    materialReasonsBySignalId,
    issues,
  };
}
