"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import AppContainer from "@/components/AppContainer";
import PageHeader from "@/components/PageHeader";
import RequireAdminAuth from "@/components/RequireAdminAuth";
import SectionCard from "@/components/SectionCard";
import { apiUrl } from "@/lib/api";
import { adminFetch } from "@/lib/adminAuth";

type CounterMap = Record<string, number>;
type LifecycleProvenance = "direct" | "derived" | "inferred" | "missing" | "legacy" | "unknown";

type LifecycleRecentEvent = {
  event_id?: string;
  signal_id?: string;
  event_type?: string;
  event_time?: string | null;
  recorded_at?: string | null;
  route?: string;
  provenance_class?: string;
  source_ref?: {
    record_family?: string;
    record_id?: string;
  };
  state?: {
    before?: string;
    after?: string;
  };
  project_ref?: {
    project_id?: string;
  } | null;
};

type LifecycleTransition = {
  before?: string;
  after?: string;
  count?: number;
};

type HardReadinessCheck = {
  id?: string;
  label?: string;
  status?: "ready" | "warning" | "not_ready" | string;
  detail?: string;
};

type HardEnforcementReadiness = {
  selected_path?: string;
  event_type?: string;
  status?: "ready" | "warning" | "not_ready" | string;
  flag?: {
    env_var?: string;
    configured_value?: string;
    defaulted?: boolean;
    status?: string;
    effective_mode?: string;
    enforcement_active?: boolean;
    blocks_mutations?: boolean;
    reason?: string;
  };
  atomicity_preflight?: {
    path?: string;
    status?: string;
    atomicity_ready?: boolean;
    current_order?: string;
    safe_to_block_mutation?: boolean;
    blocking_recommendation?: string;
    summary?: string;
    checked_subpaths?: Array<{
      id?: string;
      owner?: string;
      current_order?: string[];
      atomicity_ready?: boolean;
      risk?: string;
    }>;
    required_before_blocking?: string[];
  };
  event_count?: number;
  direct_event_count?: number;
  complete_event_count?: number;
  checks?: HardReadinessCheck[];
  blocking_gaps?: string[];
  warnings?: string[];
  next_action?: string;
};

type LifecycleSummary = {
  message?: string;
  schema_version?: number;
  generated_at?: string;
  storage?: {
    adapter?: string;
    shared_storage_enabled?: boolean;
    local_fallback_enabled?: boolean;
    s3_prefix?: string;
  };
  authoritative?: boolean;
  summary_scope?: string;
  file_count?: number;
  s3_file_count?: number;
  malformed_file_count?: number;
  malformed_files?: string[];
  s3_malformed_key_count?: number;
  s3_malformed_keys?: string[];
  signal_count?: number;
  event_count?: number;
  event_types?: CounterMap;
  provenance_classes?: CounterMap;
  source_record_families?: CounterMap;
  routes?: CounterMap;
  state_transitions?: LifecycleTransition[];
  latest_recorded_at?: string | null;
  latest_event_time?: string | null;
  recent_events?: LifecycleRecentEvent[];
  hard_enforcement_readiness?: HardEnforcementReadiness;
  warnings?: string[];
};

type ReadinessTone = "ready" | "watch" | "blocked";

type ReadinessRow = {
  label: string;
  value: string;
  tone: ReadinessTone;
};

export default function LifecycleDiagnosticsPage() {
  const [summary, setSummary] = useState<LifecycleSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [signalSearch, setSignalSearch] = useState("");
  const [eventTypeFilter, setEventTypeFilter] = useState("all");
  const [routeFilter, setRouteFilter] = useState("all");

  const loadSummary = async (mode: "initial" | "refresh" = "initial") => {
    if (mode === "initial") {
      setLoading(true);
    } else {
      setRefreshing(true);
    }
    setErrorMessage("");

    try {
      const response = await adminFetch(apiUrl("/signals/lifecycle-summary?limit=10"), {
        cache: "no-store",
      });
      const data = (await response.json()) as LifecycleSummary & { detail?: string };
      if (!response.ok) {
        throw new Error(data.detail || data.message || `Lifecycle summary failed with ${response.status}`);
      }
      setSummary(data);
    } catch (error) {
      setSummary(null);
      setErrorMessage(error instanceof Error ? error.message : "Lifecycle diagnostics could not load.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    void loadSummary("initial");
  }, []);

  const storageLabel = useMemo(() => {
    const storage = summary?.storage || {};
    if (storage.shared_storage_enabled) return "Shared storage + local fallback";
    if (storage.adapter) return `${storage.adapter} storage`;
    return "Local diagnostics";
  }, [summary?.storage]);
  const recentEvents = useMemo(() => summary?.recent_events || [], [summary?.recent_events]);
  const eventTypeOptions = useMemo(
    () => ["all", ...Array.from(new Set(recentEvents.map((event) => event.event_type || "unknown_event"))).sort()],
    [recentEvents]
  );
  const routeOptions = useMemo(
    () => ["all", ...Array.from(new Set(recentEvents.map((event) => event.route || "unknown"))).sort()],
    [recentEvents]
  );
  const filteredEvents = useMemo(() => {
    const query = signalSearch.trim().toLowerCase();
    return recentEvents.filter((event) => {
      const signalId = (event.signal_id || "").toLowerCase();
      const eventType = event.event_type || "unknown_event";
      const route = event.route || "unknown";
      if (query && !signalId.includes(query)) return false;
      if (eventTypeFilter !== "all" && eventType !== eventTypeFilter) return false;
      if (routeFilter !== "all" && route !== routeFilter) return false;
      return true;
    });
  }, [eventTypeFilter, recentEvents, routeFilter, signalSearch]);
  const storageComparison = useMemo(() => buildStorageComparison(summary), [summary]);
  const readinessSnapshot = useMemo(() => buildReadinessSnapshot(summary), [summary]);

  return (
    <AppContainer>
      <RequireAdminAuth>
        <PageHeader
          title="Lifecycle Diagnostics"
          description="Inspect soft-recorded signal lifecycle events without treating them as authoritative history."
          size="compact"
        />

        <div style={toolbarStyle}>
          <Link href="/admin" style={secondaryLinkStyle}>
            Back to Admin
          </Link>
          <button
            type="button"
            onClick={() => void loadSummary("refresh")}
            disabled={loading || refreshing}
            style={{
              ...primaryButtonStyle,
              cursor: loading || refreshing ? "not-allowed" : "pointer",
              opacity: loading || refreshing ? 0.7 : 1,
            }}
          >
            {refreshing ? "Refreshing..." : "Refresh"}
          </button>
        </div>

        <SectionCard title="Lifecycle Readiness">
          {errorMessage ? <div style={errorStyle}>{errorMessage}</div> : null}
          {loading ? (
            <div style={mutedTextStyle}>Loading lifecycle diagnostics...</div>
          ) : summary ? (
            <div style={summaryGridStyle}>
              <Metric label="Events" value={summary.event_count ?? 0} />
              <Metric label="Signals" value={summary.signal_count ?? 0} />
              <Metric label="Local Files" value={summary.file_count ?? 0} />
              <Metric label="Shared Files" value={summary.s3_file_count ?? 0} />
              <Metric label="Malformed" value={(summary.malformed_file_count ?? 0) + (summary.s3_malformed_key_count ?? 0)} />
            </div>
          ) : null}

          {summary ? (
            <div style={noticeGridStyle}>
              <div style={summaryNoticeStyle}>
                <strong>Authority</strong>
                <span>{summary.authoritative ? "Authoritative" : "Non-authoritative soft-recorded events"}</span>
              </div>
              <div style={summaryNoticeStyle}>
                <strong>Storage</strong>
                <span>{storageLabel}</span>
              </div>
              <div style={summaryNoticeStyle}>
                <strong>Generated</strong>
                <span>{formatDateTime(summary.generated_at)}</span>
              </div>
              <div style={summaryNoticeStyle}>
                <strong>Latest Event</strong>
                <span>{formatDateTime(summary.latest_event_time || summary.latest_recorded_at)}</span>
              </div>
            </div>
          ) : null}
          {summary ? (
            <div style={storageDiffStyle}>
              <div style={storageDiffSummaryStyle}>
                <strong>Local vs shared storage</strong>
                <span>{storageComparison.summary}</span>
              </div>
              <div style={storageDiffMetricRowStyle}>
                <span>Local {summary.file_count ?? 0}</span>
                <span>Shared {summary.s3_file_count ?? 0}</span>
                <span>Delta {storageComparison.delta}</span>
              </div>
            </div>
          ) : null}
        </SectionCard>

        {summary ? (
          <>
            <SectionCard title="Stage B Readiness Snapshot">
              <div style={readinessGridStyle}>
                {readinessSnapshot.rows.map((row) => (
                  <div key={row.label} style={readinessItemStyle}>
                    <span style={readinessLabelStyle}>{row.label}</span>
                    <strong style={{ ...readinessValueStyle, color: readinessToneColors[row.tone] }}>
                      {row.value}
                    </strong>
                  </div>
                ))}
              </div>
              <div style={nextActionStyle}>
                <strong>Next operating action</strong>
                <span>{readinessSnapshot.nextAction}</span>
              </div>
            </SectionCard>

            <SectionCard title="Hard Enforcement Readiness">
              <HardEnforcementReadinessPanel readiness={summary.hard_enforcement_readiness} />
            </SectionCard>

            <div style={twoColumnStyle}>
              <CounterPanel title="Event Types" items={summary.event_types || {}} />
              <CounterPanel title="Provenance" items={summary.provenance_classes || {}} formatLabel={formatProvenanceLabel} />
              <CounterPanel title="Routes" items={summary.routes || {}} />
              <CounterPanel title="Source Families" items={summary.source_record_families || {}} />
            </div>

            <SectionCard title="State Transitions">
              <TransitionRows items={summary.state_transitions || []} />
            </SectionCard>

            <SectionCard title="Recent Lifecycle Events">
              <div style={provenanceLegendPanelStyle}>
                {provenanceLegendItems.map((item) => {
                  const meta = provenanceMeta(item);
                  return (
                    <span
                      key={item}
                      style={{
                        border: `1px solid ${meta.border}`,
                        borderRadius: "999px",
                        background: meta.background,
                        color: meta.color,
                        padding: "4px 8px",
                        fontSize: "11px",
                        fontWeight: 900,
                      }}
                      title={meta.detail}
                    >
                      {meta.label}
                    </span>
                  );
                })}
              </div>
              <div style={filterPanelStyle}>
                <label style={filterLabelStyle}>
                  Signal ID
                  <input
                    type="search"
                    value={signalSearch}
                    onChange={(event) => setSignalSearch(event.target.value)}
                    placeholder="Search signal_id"
                    style={filterInputStyle}
                  />
                </label>
                <label style={filterLabelStyle}>
                  Event type
                  <select value={eventTypeFilter} onChange={(event) => setEventTypeFilter(event.target.value)} style={filterInputStyle}>
                    {eventTypeOptions.map((option) => (
                      <option key={option} value={option}>
                        {option === "all" ? "All event types" : option}
                      </option>
                    ))}
                  </select>
                </label>
                <label style={filterLabelStyle}>
                  Route
                  <select value={routeFilter} onChange={(event) => setRouteFilter(event.target.value)} style={filterInputStyle}>
                    {routeOptions.map((option) => (
                      <option key={option} value={option}>
                        {option === "all" ? "All routes" : option}
                      </option>
                    ))}
                  </select>
                </label>
                <button
                  type="button"
                  onClick={() => {
                    setSignalSearch("");
                    setEventTypeFilter("all");
                    setRouteFilter("all");
                  }}
                  style={resetButtonStyle}
                >
                  Reset
                </button>
              </div>
              {filteredEvents.length ? (
                <div style={eventListStyle}>
                  {filteredEvents.map((event, index) => (
                    <div key={`${event.event_id || event.signal_id || "event"}-${index}`} style={eventCardStyle}>
                      <div style={eventHeaderStyle}>
                        <strong>{event.event_type || "unknown_event"}</strong>
                        <span style={provenancePillStyle(event.provenance_class)}>
                          {formatProvenanceLabel(event.provenance_class)}
                        </span>
                      </div>
                      <div style={eventMetaStyle}>
                        {event.signal_id ? (
                          <Link href={`/signals/detail?id=${encodeURIComponent(event.signal_id)}`} style={inlineSignalLinkStyle}>
                            Signal: {event.signal_id}
                          </Link>
                        ) : (
                          <span>Signal: unknown</span>
                        )}
                        <span>Route: {event.route || "unknown"}</span>
                        <span>Recorded: {formatDateTime(event.recorded_at || event.event_time)}</span>
                      </div>
                      <div style={eventMetaStyle}>
                        <span>
                          State: {event.state?.before || "unknown"} {"->"} {event.state?.after || "unknown"}
                        </span>
                        <span>Source: {event.source_ref?.record_family || "unknown"}</span>
                        {event.project_ref?.project_id ? <span>Project: {event.project_ref.project_id}</span> : null}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div style={mutedTextStyle}>
                  {recentEvents.length ? "No recent lifecycle events match the current filters." : "No recent lifecycle events recorded yet."}
                </div>
              )}
            </SectionCard>

            {(summary.warnings?.length ||
              summary.malformed_files?.length ||
              summary.s3_malformed_keys?.length) ? (
              <SectionCard title="Warnings">
                <div style={warningListStyle}>
                  {(summary.warnings || []).map((warning) => (
                    <div key={warning} style={warningStyle}>{warning}</div>
                  ))}
                  {(summary.malformed_files || []).map((file) => (
                    <div key={file} style={warningStyle}>
                      <strong>Malformed local file: {file}</strong>
                      <span>{malformedFixSuggestion(file, "local")}</span>
                    </div>
                  ))}
                  {(summary.s3_malformed_keys || []).map((key) => (
                    <div key={key} style={warningStyle}>
                      <strong>Malformed shared object: {key}</strong>
                      <span>{malformedFixSuggestion(key, "shared")}</span>
                    </div>
                  ))}
                </div>
              </SectionCard>
            ) : null}
          </>
        ) : null}
      </RequireAdminAuth>
    </AppContainer>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div style={metricStyle}>
      <div style={metricLabelStyle}>{label}</div>
      <div style={metricValueStyle}>{value}</div>
    </div>
  );
}

function CounterPanel({
  title,
  items,
  formatLabel = (value: string) => value,
}: {
  title: string;
  items: CounterMap;
  formatLabel?: (value: string) => string;
}) {
  return (
    <SectionCard title={title}>
      <CounterRows items={items} emptyText={`No ${title.toLowerCase()} recorded yet.`} formatLabel={formatLabel} />
    </SectionCard>
  );
}

function CounterRows({
  items,
  emptyText,
  formatLabel = (value: string) => value,
}: {
  items: CounterMap;
  emptyText: string;
  formatLabel?: (value: string) => string;
}) {
  const rows = Object.entries(items).sort((left, right) => right[1] - left[1]);
  if (!rows.length) return <div style={mutedTextStyle}>{emptyText}</div>;
  return (
    <div style={counterRowsStyle}>
      {rows.map(([label, count]) => (
        <div key={label} style={counterRowStyle}>
          <span>{formatLabel(label)}</span>
          <strong>{count}</strong>
        </div>
      ))}
    </div>
  );
}

function TransitionRows({ items }: { items: LifecycleTransition[] }) {
  if (!items.length) return <div style={mutedTextStyle}>No state transitions recorded yet.</div>;
  return (
    <div style={counterRowsStyle}>
      {items.map((item, index) => (
        <div key={`${item.before || "unknown"}-${item.after || "unknown"}-${index}`} style={counterRowStyle}>
          <span>
            {item.before || "unknown"} {"->"} {item.after || "unknown"}
          </span>
          <strong>{item.count ?? 0}</strong>
        </div>
      ))}
    </div>
  );
}

function HardEnforcementReadinessPanel({ readiness }: { readiness?: HardEnforcementReadiness }) {
  if (!readiness) {
    return <div style={mutedTextStyle}>No hard-enforcement readiness report is attached to this summary.</div>;
  }

  const status = readinessStatus(readiness.status);
  return (
    <div style={hardReadinessPanelStyle}>
      <div style={hardReadinessHeaderStyle}>
        <div>
          <div style={hardReadinessEyebrowStyle}>Candidate Path</div>
          <strong>{readiness.selected_path || "Not selected"}</strong>
        </div>
        <span style={hardReadinessStatusStyle(status)}>{formatReadinessStatus(readiness.status)}</span>
      </div>

      {readiness.flag ? (
        <div style={hardReadinessFlagStyle}>
          <div>
            <div style={hardReadinessEyebrowStyle}>Enforcement Flag</div>
            <strong>{readiness.flag.env_var || "AI_RADAR_SIGNAL_STATUS_HARD_ENFORCEMENT"}</strong>
          </div>
          <div style={hardReadinessFlagGridStyle}>
            <span>Configured: {readiness.flag.configured_value || "off"}</span>
            <span>Effective: {formatCompactValue(readiness.flag.effective_mode || "off")}</span>
            <span>Blocks mutations: {readiness.flag.blocks_mutations ? "Yes" : "No"}</span>
          </div>
          <span>{readiness.flag.reason || "No flag reason recorded."}</span>
        </div>
      ) : null}

      {readiness.atomicity_preflight ? (
        <div style={atomicityPanelStyle}>
          <div style={hardReadinessHeaderStyle}>
            <div>
              <div style={hardReadinessEyebrowStyle}>Atomicity Preflight</div>
              <strong>{formatReadinessStatus(readiness.atomicity_preflight.status)}</strong>
            </div>
            <span style={hardReadinessStatusStyle(readiness.atomicity_preflight.atomicity_ready ? "ready" : "blocked")}>
              {readiness.atomicity_preflight.atomicity_ready ? "Atomic" : "Not atomic"}
            </span>
          </div>
          <div style={atomicitySummaryStyle}>
            <span>{readiness.atomicity_preflight.summary || "No atomicity summary recorded."}</span>
            <span>Current order: {formatCompactValue(readiness.atomicity_preflight.current_order)}</span>
            <span>Recommendation: {formatCompactValue(readiness.atomicity_preflight.blocking_recommendation)}</span>
          </div>
          <div style={atomicitySubpathGridStyle}>
            {(readiness.atomicity_preflight.checked_subpaths || []).map((subpath) => (
              <div key={subpath.id || subpath.owner} style={atomicitySubpathStyle(subpath.atomicity_ready)}>
                <span style={hardReadinessCheckLabelStyle}>{formatCompactValue(subpath.id || subpath.owner || "subpath")}</span>
                <strong>{subpath.atomicity_ready ? "Ready" : "Not ready"}</strong>
                <span>{subpath.risk || "No risk recorded."}</span>
              </div>
            ))}
          </div>
          {(readiness.atomicity_preflight.required_before_blocking || []).length ? (
            <details>
              <summary style={atomicityDetailsSummaryStyle}>Required before blocking</summary>
              <ul style={atomicityListStyle}>
                {(readiness.atomicity_preflight.required_before_blocking || []).map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </details>
          ) : null}
        </div>
      ) : null}

      <div style={hardReadinessMetricsStyle}>
        <Metric label="Path Events" value={readiness.event_count ?? 0} />
        <Metric label="Direct Events" value={readiness.direct_event_count ?? 0} />
        <Metric label="Complete Events" value={readiness.complete_event_count ?? 0} />
      </div>

      <div style={hardReadinessChecksStyle}>
        {(readiness.checks || []).map((check) => {
          const checkStatus = readinessStatus(check.status);
          return (
            <div key={check.id || check.label} style={hardReadinessCheckStyle(checkStatus)}>
              <span style={hardReadinessCheckLabelStyle}>{check.label || check.id || "Check"}</span>
              <strong>{formatReadinessStatus(check.status)}</strong>
              <span>{check.detail || "No detail recorded."}</span>
            </div>
          );
        })}
      </div>

      {(readiness.blocking_gaps?.length || readiness.warnings?.length || readiness.next_action) ? (
        <div style={hardReadinessNotesStyle}>
          {(readiness.blocking_gaps || []).map((gap) => (
            <div key={gap} style={hardReadinessGapStyle}>{gap}</div>
          ))}
          {(readiness.warnings || []).map((warning) => (
            <div key={warning} style={hardReadinessWarningStyle}>{warning}</div>
          ))}
          {readiness.next_action ? (
            <div style={hardReadinessNextStyle}>
              <strong>Next action</strong>
              <span>{readiness.next_action}</span>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function formatDateTime(value?: string | null) {
  if (!value) return "Not recorded";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

function readinessStatus(value?: string): ReadinessTone {
  if (value === "ready") return "ready";
  if (value === "not_ready") return "blocked";
  return "watch";
}

function formatReadinessStatus(value?: string) {
  if (value === "not_ready") return "Not ready";
  if (value === "ready") return "Ready";
  if (value === "warning") return "Warning";
  return value || "Unknown";
}

function formatCompactValue(value?: string) {
  return (value || "").replaceAll("_", " ") || "Unknown";
}

function normalizeProvenance(value?: string): LifecycleProvenance {
  const provenance = (value || "").toLowerCase();
  if (["direct", "derived", "inferred", "missing", "legacy"].includes(provenance)) {
    return provenance as LifecycleProvenance;
  }
  return "unknown";
}

function provenanceMeta(value?: string) {
  const provenance = normalizeProvenance(value);
  const meta: Record<LifecycleProvenance, { label: string; detail: string; color: string; background: string; border: string }> = {
    direct: {
      label: "Direct",
      detail: "Stored lifecycle event or source field",
      color: "var(--app-success-fg)",
      background: "var(--app-success-bg)",
      border: "var(--app-success-border)",
    },
    derived: {
      label: "Derived",
      detail: "Joined from project-side records",
      color: "var(--app-tag-fg)",
      background: "var(--app-tag-bg)",
      border: "var(--app-surface-strong-border)",
    },
    inferred: {
      label: "Inferred",
      detail: "Reconstructed from current state",
      color: "var(--app-warning-fg)",
      background: "var(--app-warning-bg)",
      border: "var(--app-warning-border)",
    },
    missing: {
      label: "Missing",
      detail: "No durable evidence attached",
      color: "var(--app-danger-fg)",
      background: "var(--app-danger-bg)",
      border: "var(--app-danger-border)",
    },
    legacy: {
      label: "Legacy",
      detail: "Pre-lifecycle record shape",
      color: "var(--app-chip-fg)",
      background: "var(--app-chip-bg)",
      border: "var(--app-chip-border)",
    },
    unknown: {
      label: "Unknown",
      detail: "Unclassified provenance",
      color: "var(--app-chip-fg)",
      background: "var(--app-chip-bg)",
      border: "var(--app-chip-border)",
    },
  };
  return meta[provenance];
}

function formatProvenanceLabel(value?: string) {
  const meta = provenanceMeta(value);
  const provenance = normalizeProvenance(value);
  return provenance === "unknown" && value ? value : meta.label;
}

function provenancePillStyle(value?: string) {
  const meta = provenanceMeta(value);
  return {
    ...pillStyle,
    border: `1px solid ${meta.border}`,
    background: meta.background,
    color: meta.color,
  };
}

const provenanceLegendItems: LifecycleProvenance[] = ["direct", "derived", "inferred", "missing", "legacy"];

function buildStorageComparison(summary: LifecycleSummary | null) {
  if (!summary) return { delta: 0, summary: "No lifecycle summary loaded yet." };
  const localCount = summary.file_count ?? 0;
  const sharedCount = summary.s3_file_count ?? 0;
  const delta = sharedCount - localCount;
  if (!summary.storage?.shared_storage_enabled) {
    return {
      delta,
      summary: "Shared storage is not enabled for this environment; local files are the visible diagnostic source.",
    };
  }
  if (delta === 0) {
    return {
      delta,
      summary: "Local fallback and shared storage have the same file count in this summary.",
    };
  }
  if (delta > 0) {
    return {
      delta,
      summary: "Shared storage has more files than the local cache. This computer may not have all lifecycle cache files yet.",
    };
  }
  return {
    delta,
    summary: "Local cache has more files than shared storage. Check whether shared writes are configured and whether recent local events synced.",
  };
}

function buildReadinessSnapshot(summary: LifecycleSummary | null): {
  rows: ReadinessRow[];
  nextAction: string;
} {
  if (!summary) {
    return {
      rows: [],
      nextAction: "Load lifecycle summary before selecting the next Stage B action.",
    };
  }

  const eventCount = summary.event_count ?? 0;
  const signalCount = summary.signal_count ?? 0;
  const localMalformed = summary.malformed_file_count ?? 0;
  const sharedMalformed = summary.s3_malformed_key_count ?? 0;
  const malformedCount = localMalformed + sharedMalformed;
  const recentEventCount = summary.recent_events?.length ?? 0;
  const sharedStorageEnabled = Boolean(summary.storage?.shared_storage_enabled);
  const localFiles = summary.file_count ?? 0;
  const sharedFiles = summary.s3_file_count ?? 0;
  const storageDelta = sharedFiles - localFiles;

  let nextAction = "Keep observing lifecycle event coverage before migrating another write path.";
  if (malformedCount > 0) {
    nextAction = "Repair malformed lifecycle records before expanding Stage B coverage.";
  } else if (eventCount === 0) {
    nextAction = "Generate or update a signal to create a soft lifecycle event before further Stage B work.";
  } else if (recentEventCount === 0) {
    nextAction = "Increase the recent-event limit or inspect stored lifecycle files before changing write paths.";
  } else if (!sharedStorageEnabled) {
    nextAction = "Local diagnostics are usable; shared-storage validation can remain a later ops step.";
  } else if (storageDelta !== 0) {
    nextAction = "Compare local and shared lifecycle stores before treating shared coverage as complete.";
  }

  return {
    rows: [
      {
        label: "Authority",
        value: summary.authoritative ? "Authoritative" : "Soft recorded",
        tone: summary.authoritative ? "ready" : "watch",
      },
      {
        label: "Event coverage",
        value: eventCount > 0 ? `${eventCount} events / ${signalCount} signals` : "No events",
        tone: eventCount > 0 ? "ready" : "blocked",
      },
      {
        label: "Recent visibility",
        value: recentEventCount > 0 ? `${recentEventCount} recent events` : "No recent events",
        tone: recentEventCount > 0 ? "ready" : "watch",
      },
      {
        label: "Malformed records",
        value: malformedCount > 0 ? `${malformedCount} to inspect` : "Clean",
        tone: malformedCount > 0 ? "blocked" : "ready",
      },
      {
        label: "Storage parity",
        value: sharedStorageEnabled ? `Delta ${storageDelta}` : "Local only",
        tone: !sharedStorageEnabled || storageDelta === 0 ? "ready" : "watch",
      },
    ],
    nextAction,
  };
}

function malformedFixSuggestion(path: string, kind: "local" | "shared") {
  const target = kind === "local" ? "local JSON file" : "shared storage object";
  if (path.endsWith("index.json")) {
    return `Check whether this ${target} is valid JSON and contains the expected index shape. Regenerate from lifecycle events if it is only an index artifact.`;
  }
  return `Open this ${target}, verify it is valid JSON, and confirm required lifecycle fields such as event_id, signal_id, event_type, and recorded_at are present.`;
}

const toolbarStyle = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  gap: "12px",
  flexWrap: "wrap" as const,
  marginBottom: "18px",
};

const primaryButtonStyle = {
  border: "1px solid var(--app-primary-action-border)",
  borderRadius: "8px",
  background: "var(--app-primary-action-bg)",
  color: "var(--app-primary-action-fg)",
  minHeight: "40px",
  padding: "0 14px",
  fontSize: "13px",
  fontWeight: 800,
};

const secondaryLinkStyle = {
  display: "inline-flex",
  alignItems: "center",
  minHeight: "40px",
  border: "1px solid var(--app-secondary-action-border)",
  borderRadius: "8px",
  background: "var(--app-secondary-action-bg)",
  color: "var(--app-secondary-action-fg)",
  padding: "0 14px",
  textDecoration: "none",
  fontSize: "13px",
  fontWeight: 800,
};

const summaryGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))",
  gap: "12px",
};

const metricStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  padding: "14px",
  minWidth: 0,
  overflowWrap: "anywhere" as const,
  wordBreak: "break-word" as const,
};

const metricLabelStyle = {
  fontSize: "12px",
  color: "var(--app-text-subtle)",
  fontWeight: 800,
  textTransform: "uppercase" as const,
  letterSpacing: 0,
};

const metricValueStyle = {
  marginTop: "8px",
  fontSize: "30px",
  lineHeight: 1,
  color: "var(--app-text-strong)",
  fontWeight: 850,
};

const noticeGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
  gap: "10px",
  marginTop: "14px",
};

const summaryNoticeStyle = {
  border: "1px solid var(--app-info-border)",
  borderRadius: "8px",
  background: "var(--app-info-bg)",
  padding: "11px 12px",
  display: "grid",
  gap: "4px",
  color: "var(--app-info-fg)",
  fontSize: "13px",
};

const storageDiffStyle = {
  marginTop: "14px",
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  padding: "12px",
  display: "flex",
  justifyContent: "space-between",
  gap: "12px",
  flexWrap: "wrap" as const,
  color: "var(--app-text-muted)",
  fontSize: "13px",
  lineHeight: 1.55,
};

const storageDiffSummaryStyle = {
  display: "grid",
  gap: "3px",
};

const storageDiffMetricRowStyle = {
  display: "flex",
  gap: "8px",
  flexWrap: "wrap" as const,
  alignItems: "center",
  fontSize: "12px",
  fontWeight: 800,
  color: "var(--app-info-fg)",
};

const readinessToneColors: Record<ReadinessTone, string> = {
  ready: "var(--app-success-fg)",
  watch: "var(--app-warning-fg)",
  blocked: "var(--app-danger-fg)",
};

const readinessGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))",
  gap: "10px",
};

const readinessItemStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  padding: "11px 12px",
  display: "grid",
  gap: "6px",
};

const readinessLabelStyle = {
  color: "var(--app-text-subtle)",
  fontSize: "12px",
  fontWeight: 800,
  textTransform: "uppercase" as const,
  letterSpacing: 0,
};

const readinessValueStyle = {
  fontSize: "15px",
  lineHeight: 1.25,
};

const nextActionStyle = {
  marginTop: "12px",
  border: "1px solid var(--app-info-border)",
  borderRadius: "8px",
  background: "var(--app-info-bg)",
  color: "var(--app-info-fg)",
  padding: "11px 12px",
  display: "grid",
  gap: "4px",
  fontSize: "13px",
  lineHeight: 1.5,
};

const hardReadinessPanelStyle = {
  display: "grid",
  gap: "12px",
};

const hardReadinessHeaderStyle = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  gap: "12px",
  flexWrap: "wrap" as const,
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  padding: "12px",
  color: "var(--app-text-strong)",
  minWidth: 0,
  overflowWrap: "anywhere" as const,
  wordBreak: "break-word" as const,
};

const hardReadinessEyebrowStyle = {
  color: "var(--app-text-subtle)",
  fontSize: "12px",
  fontWeight: 800,
  textTransform: "uppercase" as const,
  letterSpacing: 0,
  marginBottom: "4px",
};

const hardReadinessMetricsStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
  gap: "10px",
};

const hardReadinessFlagStyle = {
  border: "1px solid var(--app-info-border)",
  borderRadius: "8px",
  background: "var(--app-info-bg)",
  color: "var(--app-info-fg)",
  padding: "12px",
  display: "grid",
  gap: "8px",
  fontSize: "13px",
  lineHeight: 1.5,
  minWidth: 0,
  overflowWrap: "anywhere" as const,
  wordBreak: "break-word" as const,
};

const hardReadinessFlagGridStyle = {
  display: "flex",
  gap: "8px",
  flexWrap: "wrap" as const,
  color: "var(--app-info-fg)",
  fontSize: "12px",
  fontWeight: 800,
};

const atomicityPanelStyle = {
  border: "1px solid var(--app-warning-border)",
  borderRadius: "8px",
  background: "var(--app-warning-bg)",
  padding: "12px",
  display: "grid",
  gap: "10px",
};

const atomicitySummaryStyle = {
  display: "grid",
  gap: "5px",
  color: "var(--app-warning-fg)",
  fontSize: "13px",
  lineHeight: 1.5,
};

const atomicitySubpathGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
  gap: "10px",
};

function atomicitySubpathStyle(ready?: boolean) {
  return {
    border: `1px solid ${ready ? "var(--app-success-border)" : "var(--app-warning-border)"}`,
    borderRadius: "8px",
    background: ready ? "var(--app-success-bg)" : "var(--app-warning-bg)",
    color: ready ? "var(--app-success-fg)" : "var(--app-warning-fg)",
    padding: "11px 12px",
    display: "grid",
    gap: "5px",
    fontSize: "13px",
    lineHeight: 1.45,
    minWidth: 0,
    overflowWrap: "anywhere" as const,
    wordBreak: "break-word" as const,
  };
}

const atomicityDetailsSummaryStyle = {
  cursor: "pointer",
  color: "var(--app-warning-fg)",
  fontSize: "13px",
  fontWeight: 900,
};

const atomicityListStyle = {
  margin: "8px 0 0",
  paddingLeft: "18px",
  color: "var(--app-warning-fg)",
  fontSize: "13px",
  lineHeight: 1.55,
};

const hardReadinessChecksStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
  gap: "10px",
};

const hardReadinessCheckLabelStyle = {
  color: "var(--app-text-subtle)",
  fontSize: "12px",
  fontWeight: 800,
  textTransform: "uppercase" as const,
  letterSpacing: 0,
};

const hardReadinessNotesStyle = {
  display: "grid",
  gap: "8px",
};

const hardReadinessGapStyle = {
  border: "1px solid var(--app-danger-border)",
  borderRadius: "8px",
  background: "var(--app-danger-bg)",
  color: "var(--app-danger-fg)",
  padding: "9px 11px",
  fontSize: "13px",
  fontWeight: 800,
  overflowWrap: "anywhere" as const,
  wordBreak: "break-word" as const,
};

const hardReadinessWarningStyle = {
  border: "1px solid var(--app-warning-border)",
  borderRadius: "8px",
  background: "var(--app-warning-bg)",
  color: "var(--app-warning-fg)",
  padding: "9px 11px",
  fontSize: "13px",
  fontWeight: 700,
  overflowWrap: "anywhere" as const,
  wordBreak: "break-word" as const,
};

const hardReadinessNextStyle = {
  border: "1px solid var(--app-info-border)",
  borderRadius: "8px",
  background: "var(--app-info-bg)",
  color: "var(--app-info-fg)",
  padding: "9px 11px",
  display: "grid",
  gap: "4px",
  fontSize: "13px",
  lineHeight: 1.5,
  minWidth: 0,
  overflowWrap: "anywhere" as const,
  wordBreak: "break-word" as const,
};

function hardReadinessStatusStyle(tone: ReadinessTone) {
  return {
    border: `1px solid ${
      tone === "ready"
        ? "var(--app-success-border)"
        : tone === "blocked"
          ? "var(--app-danger-border)"
          : "var(--app-warning-border)"
    }`,
    borderRadius: "999px",
    background:
      tone === "ready"
        ? "var(--app-success-bg)"
        : tone === "blocked"
          ? "var(--app-danger-bg)"
          : "var(--app-warning-bg)",
    color: readinessToneColors[tone],
    padding: "5px 9px",
    fontSize: "12px",
    fontWeight: 900,
  };
}

function hardReadinessCheckStyle(tone: ReadinessTone) {
  return {
    border: `1px solid ${
      tone === "ready"
        ? "var(--app-success-border)"
        : tone === "blocked"
          ? "var(--app-danger-border)"
          : "var(--app-warning-border)"
    }`,
    borderRadius: "8px",
    background:
      tone === "ready"
        ? "var(--app-success-bg)"
        : tone === "blocked"
          ? "var(--app-danger-bg)"
          : "var(--app-warning-bg)",
    color: readinessToneColors[tone],
    padding: "11px 12px",
    display: "grid",
    gap: "5px",
    fontSize: "13px",
    lineHeight: 1.45,
    minWidth: 0,
    overflowWrap: "anywhere" as const,
    wordBreak: "break-word" as const,
  };
}

const twoColumnStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
  gap: "16px",
};

const counterRowsStyle = {
  display: "grid",
  gap: "8px",
};

const counterRowStyle = {
  display: "flex",
  justifyContent: "space-between",
  gap: "12px",
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  padding: "9px 11px",
  fontSize: "13px",
  color: "var(--app-text-muted)",
};

const eventListStyle = {
  display: "grid",
  gap: "10px",
};

const provenanceLegendPanelStyle = {
  display: "flex",
  gap: "6px",
  flexWrap: "wrap" as const,
  marginBottom: "12px",
};

const filterPanelStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
  gap: "10px",
  marginBottom: "12px",
  alignItems: "end",
};

const filterLabelStyle = {
  display: "grid",
  gap: "6px",
  color: "var(--app-text-subtle)",
  fontSize: "12px",
  fontWeight: 800,
  textTransform: "uppercase" as const,
  letterSpacing: 0,
};

const filterInputStyle = {
  minHeight: "38px",
  border: "1px solid var(--app-input-border)",
  borderRadius: "8px",
  background: "var(--app-input-bg)",
  color: "var(--app-input-fg)",
  padding: "0 10px",
  fontSize: "13px",
  fontWeight: 600,
};

const resetButtonStyle = {
  minHeight: "38px",
  border: "1px solid var(--app-secondary-action-border)",
  borderRadius: "8px",
  background: "var(--app-secondary-action-bg)",
  color: "var(--app-secondary-action-fg)",
  padding: "0 12px",
  fontSize: "13px",
  fontWeight: 800,
  cursor: "pointer",
};

const eventCardStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  padding: "13px",
  display: "grid",
  gap: "9px",
};

const eventHeaderStyle = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  gap: "10px",
  flexWrap: "wrap" as const,
  color: "var(--app-text-strong)",
};

const eventMetaStyle = {
  display: "flex",
  gap: "12px",
  flexWrap: "wrap" as const,
  color: "var(--app-text-muted)",
  fontSize: "12px",
};

const inlineSignalLinkStyle = {
  color: "var(--app-info-fg)",
  textDecoration: "none",
  fontWeight: 800,
};

const pillStyle = {
  border: "1px solid var(--app-chip-border)",
  borderRadius: "999px",
  background: "var(--app-chip-bg)",
  color: "var(--app-chip-fg)",
  padding: "4px 9px",
  fontSize: "12px",
  fontWeight: 800,
};

const warningListStyle = {
  display: "grid",
  gap: "8px",
};

const warningStyle = {
  border: "1px solid var(--app-warning-border)",
  borderRadius: "8px",
  background: "var(--app-warning-bg)",
  color: "var(--app-warning-fg)",
  padding: "9px 11px",
  fontSize: "13px",
  display: "grid",
  gap: "5px",
};

const errorStyle = {
  border: "1px solid var(--app-danger-border)",
  borderRadius: "8px",
  background: "var(--app-danger-bg)",
  color: "var(--app-danger-fg)",
  padding: "11px 12px",
  marginBottom: "12px",
  fontSize: "13px",
};

const mutedTextStyle = {
  color: "var(--app-text-muted)",
  fontSize: "14px",
  lineHeight: 1.6,
};
