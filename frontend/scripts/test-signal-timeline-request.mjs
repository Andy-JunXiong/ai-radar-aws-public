import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { test } from "node:test";
import vm from "node:vm";

const require = createRequire(import.meta.url);
const ts = require("typescript");
const path = "app/signals/page.tsx";
const source = readFileSync(path, "utf8");
const ast = ts.createSourceFile(path, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
let loadInitializer;
let effectCallback;
function visit(node) {
  if (ts.isVariableDeclaration(node) && node.name.getText(ast) === "loadSignals") {
    loadInitializer = node.initializer.getText(ast);
  }
  if (ts.isCallExpression(node) && node.expression.getText(ast) === "useEffect"
      && node.arguments[1]?.getText(ast) === "[loadSignals]") {
    effectCallback = node.arguments[0].getText(ast);
  }
  ts.forEachChild(node, visit);
}
visit(ast);
assert.ok(loadInitializer && effectCallback, "exercise the real page callback and effect");
const compiled = ts.transpileModule(
  `exports.load = ${loadInitializer}; const loadSignals = exports.load; exports.mount = ${effectCallback};`,
  { compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS } },
).outputText;

function harness() {
  const state = { signals: [], manualSignals: [], error: "", loading: false, refreshing: false };
  const requests = [];
  const writes = [];
  const timers = new Map();
  let cached = null;
  let cacheAge = 0;
  let timerId = 0;
  const context = {
    exports: {},
    useCallback: (fn) => fn,
    timelineRequestVersion: { current: 0 },
    subscriptionUserId: "fixture-user",
    getCachedSignals: () => cached,
    getSignalsCacheAgeMs: () => cacheAge,
    SIGNALS_CACHE_TTL_MS: 3600000,
    SIGNALS_REQUEST_TIMEOUT_MS: 20000,
    SIGNALS_AUTO_RETRY_DELAY_MS: 1500,
    SIGNALS_AUTO_RETRY_TIMEOUT_MS: 60000,
    DEFAULT_COUNTS: { all: 0 },
    setSignals: (value) => { state.signals = value; },
    setManualSignals: (value) => { state.manualSignals = value; },
    setCounts: (value) => { state.counts = value; },
    setTimelineLoadState: (value) => { state.load = value; },
    setErrorMessage: (value) => { state.error = value; },
    setLoading: (value) => { state.loading = value; },
    setRefreshing: (value) => { state.refreshing = value; },
    writeSignalsCache: (value) => writes.push(value),
    isManualSignal: (item) => Boolean(item.is_manual),
    buildCounts: (items) => ({ all: items.length }),
    isAbortError: (error) => error.name === "AbortError",
    performance: { now: () => 100 },
    Date,
    fetchSignalsTimeline: (signal) => new Promise((resolve, reject) => {
      requests.push({ resolve, reject });
      signal?.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")));
    }),
    createTimeoutController: () => {
      const controller = new AbortController();
      return { signal: controller.signal, clear() {}, abort: () => controller.abort() };
    },
    setTimeout: (fn) => { const id = ++timerId; timers.set(id, fn); return id; },
    clearTimeout: (id) => timers.delete(id),
  };
  vm.runInNewContext(compiled, context, { filename: path });
  return {
    ...context.exports, state, requests, writes, timers,
    setCache: (value, age = 0) => { cached = value; cacheAge = age; },
  };
}
const payload = (id) => ({ signals: [{ id, verification_metadata: { blocked_downstream_actions: ["action"] } }] });
const flush = async () => { for (let i = 0; i < 6; i++) await Promise.resolve(); };

test("late cancelled request cannot erase a newer successful timeline or add a timeout", async () => {
  const h = harness();
  const old = h.load(false);
  const current = h.load(false);
  h.requests[1].resolve(payload("current"));
  await current;
  h.requests[0].reject(new DOMException("Cancelled", "AbortError"));
  await old;
  assert.equal(h.state.signals[0]?.id, "current");
  assert.equal(h.state.error, "");
  assert.equal(h.writes.length, 1);
});

test("late success cannot overwrite the newer result or cache", async () => {
  const h = harness();
  const old = h.load(false);
  const current = h.load(false);
  h.requests[1].resolve(payload("current"));
  await current;
  h.requests[0].resolve(payload("obsolete"));
  await old;
  assert.equal(h.state.signals[0]?.id, "current");
  assert.equal(h.writes.length, 1);
  assert.deepEqual(h.state.signals[0].verification_metadata.blocked_downstream_actions, ["action"]);
});

test("obsolete failure/finally cannot stop the current loading indicator", async () => {
  const h = harness();
  const old = h.load(false);
  const current = h.load(false);
  h.requests[0].reject(new Error("Old network failure"));
  await old;
  assert.equal(h.state.loading, true);
  assert.equal(h.state.error, "");
  h.requests[1].resolve(payload("current"));
  await current;
  assert.equal(h.state.loading, false);
});

test("active timeout stays visible and successful recovery clears it", async () => {
  const h = harness();
  const first = h.load(false);
  h.requests[0].reject(new DOMException("Timed out", "AbortError"));
  assert.equal(await first, false);
  assert.match(h.state.error, /timed out/);
  const retry = h.load(false);
  h.requests[1].resolve(payload("recovered"));
  await retry;
  assert.equal(h.state.error, "");
  assert.equal(h.state.signals.length, 1);
});

test("active network failure retains stale cache and fresh cache reuse clears warning", async () => {
  const h = harness();
  const cache = { signals: payload("cached").signals, manualSignals: [], counts: { all: 1 } };
  h.setCache(cache, 3600001);
  const pending = h.load();
  h.requests[0].reject(new Error("Unavailable"));
  assert.equal(await pending, true);
  assert.match(h.state.error, /refresh failed/);
  assert.equal(h.state.signals[0].id, "cached");
  h.setCache(cache);
  await h.load();
  assert.equal(h.state.error, "");
  assert.equal(h.requests.length, 1);
});

test("effect cleanup aborts without mutating state or scheduling a retry", async () => {
  const h = harness();
  const cleanup = h.mount();
  const before = JSON.stringify(h.state);
  cleanup();
  await flush();
  assert.equal(JSON.stringify(h.state), before);
  assert.equal(h.timers.size, 0);
  assert.equal(h.writes.length, 0);
});

test("a queued automatic retry cannot supersede a newer manual success", async () => {
  const h = harness();
  const cleanup = h.mount();
  h.requests[0].reject(new DOMException("Timed out", "AbortError"));
  await flush();
  assert.equal(h.timers.size, 1);
  const current = h.load(false);
  h.requests[1].resolve(payload("manual"));
  await current;
  for (const fn of h.timers.values()) fn();
  assert.equal(h.requests.length, 2);
  assert.equal(h.state.signals[0].id, "manual");
  cleanup();
});

test("the current failed initial request still gets its automatic retry", async () => {
  const h = harness();
  const cleanup = h.mount();
  h.requests[0].reject(new DOMException("Timed out", "AbortError"));
  await flush();
  assert.match(h.state.error, /timed out/);
  assert.equal(h.timers.size, 1);
  for (const fn of h.timers.values()) fn();
  assert.equal(h.requests.length, 2);
  h.requests[1].resolve(payload("automatic-recovery"));
  await flush();
  assert.equal(h.state.signals[0].id, "automatic-recovery");
  assert.equal(h.state.error, "");
  cleanup();
});
