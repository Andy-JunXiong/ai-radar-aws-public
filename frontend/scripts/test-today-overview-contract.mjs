import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";
import vm from "node:vm";

const require = createRequire(import.meta.url);
const ts = require("typescript");

function loadTsModule(relativePath) {
  const sourcePath = join(process.cwd(), relativePath);
  const source = readFileSync(sourcePath, "utf8");
  const compiled = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2020,
    },
  }).outputText;
  const sandbox = {
    exports: {},
    module: { exports: {} },
    require,
    Date,
    Intl,
    Set,
    Object,
    Number,
    Error,
  };
  sandbox.exports = sandbox.module.exports;
  vm.runInNewContext(compiled, sandbox, { filename: sourcePath });
  return sandbox.module.exports;
}

const {
  TODAY_MATERIALITY_CONTRACT_VERSION,
  evaluateTodayMateriality,
} = loadTsModule("components/todayOverviewMateriality.ts");
const { evaluateTodayOverviewState, selectTodayObservedSignals } = loadTsModule("components/todayOverviewState.ts");

const operatorDate = "2026-08-25";
const operatorTimeZone = "Australia/Sydney";

function signal(id, level, reasons, overrides = {}) {
  return {
    signal_id: id,
    collected_at: "2026-08-25T02:00:00Z",
    status: "pending",
    importance_level: level,
    importance_reason: reasons,
    ...overrides,
  };
}

{
  const result = evaluateTodayMateriality(
    [
      signal("high", "high", ["high_final_score", "strategic_topic"]),
      signal("medium", "medium", ["moderate_final_score"]),
      signal("low", "low", []),
    ],
    operatorDate,
    operatorTimeZone,
    operatorTimeZone,
  );
  assert.equal(result.contractVersion, TODAY_MATERIALITY_CONTRACT_VERSION);
  assert.equal(result.contractVersion, "signal_importance_high_v1");
  assert.equal(result.completeness, "complete");
  assert.equal(result.materialChangeCount, 1);
  assert.deepEqual([...result.materialSignalIds], ["high"]);
  assert.deepEqual(
    [...result.materialReasonsBySignalId.high],
    ["high_final_score", "strategic_topic"],
  );
}

{
  const observed = selectTodayObservedSignals(
    [
      { signal_id: "same-title-a", title: "Same title", collected_at: "2026-08-25T02:00:00Z", score: 4 },
      { signal_id: "same-title-b", title: "Same title", collected_at: "2026-08-25T03:00:00Z", score: 4 },
      { signal_id: "same-title-b", title: "Duplicate id", collected_at: "2026-08-25T04:00:00Z", score: 9 },
      { signal_id: "rejected", title: "Rejected", collected_at: "2026-08-25T04:00:00Z", score: 10, status: "rejected" },
    ],
    operatorDate,
    operatorTimeZone,
  );
  assert.deepEqual([...observed].map((item) => item.signal_id), ["same-title-b", "same-title-a"]);
}

{
  const result = evaluateTodayMateriality(
    [
      signal("rejected-high", "high", ["high_final_score"], { status: "rejected" }),
      signal("wrong-day-high", "high", ["high_final_score"], {
        collected_at: "2026-08-23T02:00:00Z",
      }),
      signal("blocked-high", "high", ["high_final_score"], {
        verification: { blocked_downstream_actions: ["action"] },
      }),
    ],
    operatorDate,
    operatorTimeZone,
  );
  assert.equal(result.completeness, "complete");
  assert.equal(result.materialChangeCount, 1);
  assert.deepEqual([...result.materialSignalIds], ["blocked-high"]);
}

{
  const result = evaluateTodayMateriality(
    [
      signal("missing-level", undefined, undefined),
      signal("unknown-level", "urgent", ["high_final_score"]),
      signal("high-without-reason", "high", []),
      signal("medium-invalid-reason", "medium", "not-a-list"),
      signal("low-empty-reason", "low", []),
    ],
    operatorDate,
    operatorTimeZone,
  );
  assert.equal(result.completeness, "incomplete");
  assert.equal(result.materialChangeCount, 0);
  assert.deepEqual(
    [...result.issues].map((issue) => issue.reasonCode),
    [
      "invalid_importance_level",
      "invalid_importance_level",
      "invalid_importance_reason",
      "invalid_importance_reason",
    ],
  );
}

{
  const result = evaluateTodayMateriality(
    [
      signal("duplicate-high", "high", ["high_final_score"]),
      signal("duplicate-high", "high", ["strategic_topic"]),
    ],
    operatorDate,
    operatorTimeZone,
  );
  assert.equal(result.materialChangeCount, 1);
  assert.deepEqual([...result.materialReasonsBySignalId["duplicate-high"]], ["high_final_score"]);
}

{
  const result = evaluateTodayMateriality(
    [
      signal("sydney-boundary", "high", ["high_final_score"], {
        collected_at: "2026-08-24T14:30:00Z",
      }),
    ],
    operatorDate,
    operatorTimeZone,
  );
  assert.equal(result.materialChangeCount, 1);
}

assert.throws(
  () => evaluateTodayMateriality([], "25-08-2026", operatorTimeZone),
  /YYYY-MM-DD/,
);

function completeStateInput(overrides = {}) {
  return {
    operatorDate,
    failedReadGroups: [],
    metricsStatus: {
      latest_signal_activity_date: operatorDate,
      signal_dates_missing_pipeline_runs: [],
      signal_dates_missing_collector_runs: [],
    },
    dailySummary: {
      date: operatorDate,
      summary: {
        pipeline: { success: true },
        artifacts: {
          signals_file_written: true,
          daily_radar_file_written: true,
          failed_write_count: 0,
        },
        collectors: { coverage: { completeness: "complete" } },
      },
    },
    radarArtifactDates: [
      { name: "topic_trends", value: operatorDate },
      { name: "rising_topics", value: "2026-08-25T08:00:00+10:00" },
    ],
    newestDisplayedSignalAt: "2026-08-25T05:00:00Z",
    pageAsOf: "2026-08-25T06:00:00Z",
    materiality: {
      contractVersion: "signal_importance_high_v1",
      operatorDate,
      operatorTimeZone,
      completeness: "complete",
      materialChangeCount: 0,
      materialSignalIds: [],
      materialReasonsBySignalId: {},
      issues: [],
    },
    governedConvergenceCount: 0,
    ...overrides,
  };
}

{
  const result = evaluateTodayOverviewState(
    completeStateInput({
      failedReadGroups: ["Metrics", "Metrics"],
      metricsStatus: {},
    }),
  );
  assert.equal(result.state, "load_failed");
  assert.deepEqual([...result.failedReadGroups], ["Metrics"]);
  assert.deepEqual([...result.failedGates], []);
}

{
  const result = evaluateTodayOverviewState(
    completeStateInput({
      dailySummary: {
        date: operatorDate,
        summary: {
          pipeline: { success: true },
          artifacts: {
            signals_file_written: true,
            daily_radar_file_written: true,
            failed_write_count: 0,
          },
          collectors: { coverage: { completeness: "partial" } },
        },
      },
      materiality: {
        ...completeStateInput().materiality,
        materialChangeCount: 2,
      },
      governedConvergenceCount: 1,
    }),
  );
  assert.equal(result.state, "stale_or_partial");
  assert.deepEqual([...result.failedGates], ["collector_coverage_incomplete"]);
}

assert.equal(
  evaluateTodayOverviewState(completeStateInput()).state,
  "current_no_material_change",
);

assert.equal(
  evaluateTodayOverviewState(
    completeStateInput({
      materiality: { ...completeStateInput().materiality, materialChangeCount: 2 },
    }),
  ).state,
  "current_change_without_convergence",
);

assert.equal(
  evaluateTodayOverviewState(
    completeStateInput({
      materiality: { ...completeStateInput().materiality, materialChangeCount: 2 },
      governedConvergenceCount: 1,
    }),
  ).state,
  "current_with_convergence",
);

{
  const result = evaluateTodayOverviewState(
    completeStateInput({
      radarArtifactDates: [{ name: "topic_trends", value: "2026-08-24" }],
      newestDisplayedSignalAt: "2026-08-25T07:00:00Z",
    }),
  );
  assert.equal(result.state, "stale_or_partial");
  assert.deepEqual(
    [...result.failedGates],
    ["radar_artifact_not_today", "signal_after_page_as_of"],
  );
}

console.log("Today Overview contract tests passed: 13");
