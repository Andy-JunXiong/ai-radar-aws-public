type RecordValue = Record<string, unknown>;

function record(value: unknown): RecordValue {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? value as RecordValue : {};
}

function count(value: unknown): number | null {
  return typeof value === "number" && Number.isInteger(value) && value >= 0 ? value : null;
}

function strings(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

export function formatMetricValue(value: unknown): string {
  if (value === null || value === undefined) return "N/A";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (Array.isArray(value)) return value.length ? value.map(formatMetricValue).join("; ") : "None";
  if (typeof value === "object") {
    const entries = Object.entries(value);
    return entries.length ? entries.map(([key, item]) => `${key}: ${formatMetricValue(item)}`).join("; ") : "None";
  }
  return String(value);
}

// Presentation only. The backend completeness contract remains authoritative.
export function collectionCoverage(value: unknown) {
  const coverage = record(value);
  const supported = coverage.plan_version === "collector-coverage-v1";
  const expected = supported ? count(coverage.expected_unit_count) : null;
  const succeeded = supported ? count(coverage.succeeded_unit_count) : null;
  const attempted = supported ? count(coverage.attempted_unit_count) : null;
  const failed = supported ? count(coverage.failed_unit_count) : null;
  const skipped = supported ? count(coverage.skipped_unit_count) : null;
  const expectedSteps = count(coverage.expected_step_count);
  const complete = supported && coverage.completeness === "complete"
    && coverage.unit_counts_complete === true
    && expected !== null && expected > 0 && succeeded === expected && attempted === expected
    && failed === 0 && skipped === 0 && expectedSteps !== null && expectedSteps > 0
    && coverage.attempted_step_count === expectedSteps && coverage.reported_step_count === expectedSteps
    && ["missing_step_ids", "failed_step_ids", "unavailable_step_ids"].every(
      key => Array.isArray(coverage[key]) && coverage[key].length === 0,
    );
  const partial = supported && (coverage.completeness === "partial" || (failed ?? 0) > 0 || (skipped ?? 0) > 0);
  const state = complete ? "Complete" : partial ? "Incomplete" : "Unknown";
  const ratio = expected !== null && succeeded !== null ? `${succeeded}/${expected}` : "Unknown";
  const reportedOnly = coverage.unit_counts_complete !== true;
  const description = expected !== null && succeeded !== null
    ? `${ratio} ${reportedOnly ? "reported " : "expected "}units succeeded; ${failed ?? "unknown"} failed, ${skipped ?? "unknown"} skipped.${reportedOnly ? " Some collector counts are unavailable." : ""}`
    : "Source-unit coverage was not recorded in this summary.";
  const gap = complete ? null : `Collector coverage is ${state.toLowerCase()}: ${description.replace(/\.$/, "")}`;
  const rows = [
    { label: "Completeness", value: state },
    { label: reportedOnly ? "Reported units succeeded" : "Expected units succeeded", value: ratio },
    { label: "Failed units", value: failed === null ? "Unknown" : String(failed) },
    { label: "Skipped units", value: skipped === null ? "Unknown" : String(skipped) },
  ];
  for (const [key, label] of [
    ["failed_units", "Failed"], ["skipped_units", "Skipped"],
  ]) {
    const items = supported && Array.isArray(coverage[key]) ? coverage[key] : [];
    for (const item of items) {
      const detail = record(item);
      if (typeof detail.unit_id === "string" && typeof detail.reason_code === "string") {
        rows.push({ label: `${label}: ${detail.unit_id}`, value: detail.reason_code.replaceAll("_", " ") });
      }
    }
  }
  if (supported && coverage.unit_details_available !== true) {
    rows.push({ label: "Unit details", value: "Not fully available in this summary; consult the matching run's collector records." });
  }
  for (const [key, label] of [
    ["missing_step_ids", "Missing steps"], ["failed_step_ids", "Failed steps"],
    ["unavailable_step_ids", "Steps without coverage"], ["reason_codes", "Reasons"],
  ]) {
    const items = supported ? strings(coverage[key]) : [];
    if (items.length) rows.push({ label, value: items.join(", ") });
  }
  return { state, ratio, description, gap, rows, tone: complete ? "good" : "watch" };
}
