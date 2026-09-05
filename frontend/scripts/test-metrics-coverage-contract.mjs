import assert from "node:assert/strict";
import { readFileSync, existsSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join, resolve } from "node:path";
import vm from "node:vm";

const require = createRequire(import.meta.url);
const ts = require("typescript");
const React = require("react");
const { renderToStaticMarkup } = require("react-dom/server");
const cache = new Map();
function load(path) {
  path = resolve(path);
  if (cache.has(path)) return cache.get(path);
  const module = { exports: {} };
  const compiled = ts.transpileModule(readFileSync(path, "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true },
  }).outputText;
  function localRequire(name) {
    if (!name.startsWith(".") && !name.startsWith("@/")) return require(name);
    const base = name.startsWith("@/") ? join(process.cwd(), name.slice(2)) : resolve(dirname(path), name);
    return load([base, `${base}.ts`, `${base}.tsx`].find(existsSync));
  }
  vm.runInNewContext(compiled, { module, exports: module.exports, require: localRequire, Intl, Date }, { filename: path });
  cache.set(path, module.exports);
  return module.exports;
}
const { collectionCoverage, formatMetricValue } = load("app/admin/metrics/collectionCoverage.ts");
const { OpsAnalysis, SummarySection, PeriodOpsAnalysis } = load("app/admin/metrics/shared.tsx");
const complete = {
  plan_version: "collector-coverage-v1", completeness: "complete", unit_counts_complete: true,
  expected_step_count: 8, attempted_step_count: 8, reported_step_count: 8,
  expected_unit_count: 59, attempted_unit_count: 59, succeeded_unit_count: 59,
  failed_unit_count: 0, skipped_unit_count: 0, unit_details_available: true,
  missing_step_ids: [], failed_step_ids: [], unavailable_step_ids: [], failed_units: [], skipped_units: [],
};
const partial = {
  ...complete, completeness: "partial", succeeded_unit_count: 55, failed_unit_count: 4,
  failed_units: [
    { unit_id: "rss_source_008", reason_code: "http_error" },
    { unit_id: "rss_source_009", reason_code: "http_error" },
    { unit_id: "official_source_005", reason_code: "http_error" },
    { unit_id: "producthunt_request_001", reason_code: "invalid_response" },
  ],
};
function summary(coverage) {
  return { date: "2026-08-31", pipeline: { success: true }, collectors: { success_rate: 1, total_runs: 8, coverage }, timeline_loads: { source_mix: { local: 2 } } };
}
function render(Component, props) { return renderToStaticMarkup(React.createElement(Component, props)); }
function analysis(coverage) { return render(OpsAnalysis, { summary: summary(coverage), title: "Daily Summary", periodLabel: "Reporting day" }); }

const partialHtml = analysis(partial);
assert.match(partialHtml, /55\/59/);
assert.match(partialHtml, /Incomplete/);
assert.match(partialHtml, /Collector run success/);
assert.match(partialHtml, /100%/); // Step success remains visible alongside coverage failure.
assert.doesNotMatch(partialHtml, /No major operational gaps|Healthy/);
assert.doesNotMatch(partialHtml, /skipped\.\./);
const details = render(SummarySection, { summary: summary(partial), title: "Daily Detail" });
for (const failure of partial.failed_units) assert.ok(details.includes(failure.unit_id));
assert.match(details, /http error/);
assert.match(details, /invalid response/);
assert.doesNotMatch(details, /\[object Object\]/);
assert.match(details, /local: 2/);

assert.equal(collectionCoverage(complete).state, "Complete");
assert.match(analysis(complete), /59\/59/);
assert.match(analysis(complete), /No major operational gaps/);
for (const missing of [undefined, null, {}, { completeness: "complete" }]) {
  assert.equal(collectionCoverage(missing).state, "Unknown");
  assert.doesNotMatch(analysis(missing), /No major operational gaps/);
}
assert.equal(collectionCoverage({ ...complete, failed_unit_count: 1 }).state, "Incomplete");
assert.equal(collectionCoverage({ ...complete, unit_counts_complete: false }).state, "Unknown");
assert.equal(collectionCoverage({ ...complete, expected_unit_count: 0, succeeded_unit_count: 0, attempted_unit_count: 0 }).state, "Unknown");
assert.match(collectionCoverage({ ...partial, unit_counts_complete: false }).description, /reported/);
const legacy = { ...partial, unit_details_available: undefined, failed_units: undefined };
assert.match(render(SummarySection, { summary: summary(legacy), title: "Legacy" }), /Not fully available/);
const period = render(PeriodOpsAnalysis, { summaries: [{ ...summary(undefined), period_id: "2026-W36", period_type: "week" }], title: "Weekly", comparisonLabel: "WoW" });
assert.doesNotMatch(period, /No major operational gaps|Collection Health/);
assert.match(period, /Source-unit completeness is not aggregated/);
assert.equal(formatMetricValue([{ name: "unit", reasons: ["timeout", "http_error"] }]), "name: unit; reasons: timeout; http_error");
console.log("Metrics coverage contracts passed (partial, complete, missing, conflicting, legacy, period, rendered details).");
