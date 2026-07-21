"use client";

import { useEffect, useState } from "react";
import type { CSSProperties } from "react";
import Link from "next/link";

import AppContainer from "@/components/AppContainer";
import PageHeader from "@/components/PageHeader";
import SectionCard from "@/components/SectionCard";
import RequireAdminAuth from "@/components/RequireAdminAuth";
import { apiUrl } from "@/lib/api";
import { adminFetch } from "@/lib/adminAuth";
import {
  buildBetaUserHeaders,
  getStoredBetaUserId,
  setStoredBetaUserId,
} from "@/lib/betaUser";

const DEFAULT_CONTEXT_TEMPLATE = {
  user_profile: {
    role: "",
    experience_level: "",
    industry: "",
    goals: [],
  },
  projects: [],
  interpretation_preference: {},
};

function prettyJson(value: unknown): string {
  return JSON.stringify(value, null, 2);
}

function formatPercent(value?: number): string {
  const normalized = typeof value === "number" ? value : 0;
  return `${(normalized * 100).toFixed(1)}%`;
}

function renderCandidateValue(value?: string | null): string {
  return value && value.trim() ? value : "not configured";
}

const fieldLabelStyle: CSSProperties = {
  fontSize: "13px",
  fontWeight: 700,
  color: "var(--app-text-muted)",
};

const inputStyle: CSSProperties = {
  border: "1px solid var(--app-input-border)",
  borderRadius: "10px",
  padding: "12px 14px",
  fontSize: "14px",
  color: "var(--app-input-fg)",
  background: "var(--app-input-bg)",
  outline: "none",
};

const textareaStyle: CSSProperties = {
  ...inputStyle,
  width: "100%",
  minHeight: "420px",
  lineHeight: 1.7,
  fontSize: "13px",
  fontFamily:
    'ui-monospace, SFMono-Regular, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace',
  resize: "vertical",
};

const secondaryButtonStyle: CSSProperties = {
  padding: "10px 14px",
  borderRadius: "8px",
  border: "1px solid var(--app-secondary-action-border)",
  background: "var(--app-secondary-action-bg)",
  color: "var(--app-secondary-action-fg)",
  cursor: "pointer",
  fontWeight: 700,
};

const primaryButtonStyle: CSSProperties = {
  padding: "10px 14px",
  borderRadius: "8px",
  border: "1px solid var(--app-primary-action-border)",
  background: "var(--app-primary-action-bg)",
  color: "var(--app-primary-action-fg)",
  cursor: "pointer",
  fontWeight: 700,
};

const secondaryLinkStyle: CSSProperties = {
  ...secondaryButtonStyle,
  textDecoration: "none",
};

const diagnosticCardStyle: CSSProperties = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "10px",
  padding: "12px 14px",
  background: "var(--app-surface-muted-bg)",
};

const metricChipStyle: CSSProperties = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  padding: "10px 12px",
  background: "var(--app-surface-muted-bg)",
  fontSize: "13px",
  color: "var(--app-text-muted)",
};

const countRowStyle: CSSProperties = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  padding: "10px 12px",
  background: "var(--app-surface-muted-bg)",
  display: "flex",
  justifyContent: "space-between",
  gap: "12px",
  fontSize: "13px",
  color: "var(--app-text-muted)",
};

function candidateRowStyle(candidate: {
  used?: boolean;
  compatible?: boolean;
}): CSSProperties {
  const incompatible = candidate.compatible === false;

  return {
    border: candidate.used
      ? "1px solid var(--app-success-border)"
      : incompatible
        ? "1px solid var(--app-danger-border)"
        : "1px solid var(--app-surface-border)",
    borderRadius: "8px",
    padding: "9px 10px",
    background: candidate.used
      ? "var(--app-success-bg)"
      : incompatible
        ? "var(--app-danger-bg)"
        : "var(--app-surface-muted-bg)",
    fontSize: "12px",
    color: "var(--app-text-muted)",
  };
}

function noticeStyle(tone: "success" | "error" | "warning"): CSSProperties {
  const token =
    tone === "success" ? "success" : tone === "error" ? "danger" : "warning";

  return {
    border: `1px solid var(--app-${token}-border)`,
    background: `var(--app-${token}-bg)`,
    color: `var(--app-${token}-fg)`,
    borderRadius: "10px",
    padding: "12px 14px",
    fontSize: "13px",
  };
}

type RoutingDiagnostics = {
  routes?: Record<
    string,
    {
      tier?: string;
      provider?: string;
      model?: string;
    }
  >;
  route_details?: Record<
    string,
    {
      tier?: string;
      provider?: string;
      model?: string;
      source?: string;
      provider_resolution?: {
        selected?: string;
        selected_from?: string;
        candidates?: Array<{
          source?: string;
          value?: string | null;
          used?: boolean;
        }>;
      };
      model_resolution?: {
        selected?: string;
        selected_from?: string;
        candidates?: Array<{
          source?: string;
          value?: string | null;
          compatible?: boolean;
          used?: boolean;
        }>;
      };
    }
  >;
  warnings?: string[];
  telemetry?: {
    total_events?: number;
    last_event_at?: string | null;
    providers?: Record<string, number>;
    tiers?: Record<string, number>;
    tasks?: Record<string, number>;
    modes?: Record<string, number>;
    models?: Record<string, number>;
    outcomes?: Record<string, number>;
    fallback_count?: number;
    success_count?: number;
    failure_count?: number;
    success_rate?: number;
    failure_rate?: number;
    recent_window_size?: number;
    recent_providers?: Record<string, number>;
    recent_models?: Record<string, number>;
    recent_tasks?: Record<string, number>;
    time_windows?: Record<
      string,
      {
        total_events?: number;
        last_event_at?: string | null;
        providers?: Record<string, number>;
        models?: Record<string, number>;
        tasks?: Record<string, number>;
        outcomes?: Record<string, number>;
        fallback_count?: number;
        success_count?: number;
        failure_count?: number;
        success_rate?: number;
        failure_rate?: number;
      }
    >;
  };
};

export default function SettingsPage() {
  const [userId, setUserId] = useState("");
  const [jsonValue, setJsonValue] = useState(prettyJson(DEFAULT_CONTEXT_TEMPLATE));
  const [scope, setScope] = useState("demo_default");
  const [routingDiagnostics, setRoutingDiagnostics] = useState<RoutingDiagnostics | null>(null);
  const [message, setMessage] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [routingLoading, setRoutingLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  async function loadContext(nextUserId: string) {
    setLoading(true);
    setErrorMessage("");
    setMessage("");

    try {
      const response = await adminFetch(apiUrl("/settings/context"), {
        headers: {
          ...buildBetaUserHeaders(nextUserId),
        },
        cache: "no-store",
      });

      if (!response.ok) {
        throw new Error(`Failed to load context (${response.status})`);
      }

      const data = (await response.json()) as {
        scope?: string;
        context?: unknown;
      };

      setScope(data.scope || "demo_default");
      setJsonValue(prettyJson(data.context || DEFAULT_CONTEXT_TEMPLATE));
    } catch (error) {
      console.error(error);
      setErrorMessage("Failed to load personal context.");
    } finally {
      setLoading(false);
    }
  }

  async function loadRoutingStatus() {
    setRoutingLoading(true);

    try {
      const response = await fetch(apiUrl("/settings/model-routing"), {
        cache: "no-store",
      });

      if (!response.ok) {
        throw new Error(`Failed to load model routing (${response.status})`);
      }

      const data = (await response.json()) as RoutingDiagnostics;
      setRoutingDiagnostics(data);
    } catch (error) {
      console.error(error);
      setRoutingDiagnostics(null);
    } finally {
      setRoutingLoading(false);
    }
  }

  useEffect(() => {
    const storedUserId = getStoredBetaUserId();
    setUserId(storedUserId);
    void loadContext(storedUserId);
    void loadRoutingStatus();
  }, []);

  async function handleReload() {
    setStoredBetaUserId(userId);
    await loadContext(userId);
    await loadRoutingStatus();
  }

  async function handleSave() {
    const normalizedUserId = userId.trim();
    if (!normalizedUserId) {
      setErrorMessage("A beta user id is required before saving context.");
      setMessage("");
      return;
    }

    let parsedContext: unknown;
    try {
      parsedContext = JSON.parse(jsonValue);
    } catch {
      setErrorMessage("Context must be valid JSON before saving.");
      setMessage("");
      return;
    }

    setSaving(true);
    setErrorMessage("");
    setMessage("");

    try {
      const response = await adminFetch(apiUrl("/settings/context"), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...buildBetaUserHeaders(normalizedUserId),
        },
        body: JSON.stringify({
          context: parsedContext,
        }),
      });

      if (!response.ok) {
        const text = await response.text();
        throw new Error(text || `Failed to save context (${response.status})`);
      }

      const data = (await response.json()) as {
        message?: string;
      };

      setStoredBetaUserId(normalizedUserId);
      setMessage(data.message || "Personal context saved successfully.");
      await loadContext(normalizedUserId);
    } catch (error) {
      console.error(error);
      setErrorMessage("Failed to save personal context.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <AppContainer>
      <RequireAdminAuth>
        <PageHeader
          title="Beta Settings"
          description="Manage the personal context used for private beta personalization. This page currently uses a beta user id header instead of full authentication."
          size="compact"
        />

        <SectionCard title="Context Identity">
        <div
          style={{
            display: "grid",
            gap: "12px",
          }}
        >
          <label
            htmlFor="beta-user-id"
            style={fieldLabelStyle}
          >
            Beta User ID
          </label>

          <input
            id="beta-user-id"
            value={userId}
            onChange={(event) => setUserId(event.target.value)}
            placeholder="beta-user"
            style={inputStyle}
          />

          <div
            style={{
              display: "flex",
              gap: "10px",
              flexWrap: "wrap",
              alignItems: "center",
            }}
          >
            <button
              onClick={() => void handleReload()}
              disabled={loading}
              style={{
                ...secondaryButtonStyle,
                cursor: loading ? "not-allowed" : "pointer",
                opacity: loading ? 0.72 : 1,
              }}
            >
              {loading ? "Loading..." : "Load Context"}
            </button>

            <div
              style={{
                fontSize: "13px",
                color: "var(--app-text-muted)",
              }}
            >
              Current scope: <strong style={{ color: "var(--app-text-strong)" }}>{scope}</strong>
            </div>
          </div>
        </div>
        </SectionCard>

        <SectionCard title="Personal Context JSON">
        <div style={{ display: "grid", gap: "12px" }}>
          <textarea
            value={jsonValue}
            onChange={(event) => setJsonValue(event.target.value)}
            spellCheck={false}
            style={textareaStyle}
          />

          <div
            style={{
              display: "flex",
              gap: "10px",
              flexWrap: "wrap",
              alignItems: "center",
            }}
          >
            <button
              onClick={() => void handleSave()}
              disabled={saving}
              style={{
                ...primaryButtonStyle,
                cursor: saving ? "not-allowed" : "pointer",
                opacity: saving ? 0.72 : 1,
              }}
            >
              {saving ? "Saving..." : "Save Context"}
            </button>

            <Link
              href="/settings/form"
              style={secondaryLinkStyle}
            >
              Open Q&A Editor
            </Link>

            <Link
              href="/admin"
              style={secondaryLinkStyle}
            >
              Back to Previous Page
            </Link>
          </div>

          {message ? (
            <div
              style={noticeStyle("success")}
            >
              {message}
            </div>
          ) : null}

          {errorMessage ? (
            <div
              style={noticeStyle("error")}
            >
              {errorMessage}
            </div>
          ) : null}
        </div>
        </SectionCard>

        <SectionCard title="Model Routing Status">
        <div style={{ display: "grid", gap: "12px" }}>
          <div
            style={{
              display: "flex",
              gap: "10px",
              flexWrap: "wrap",
              alignItems: "center",
            }}
          >
            <button
              onClick={() => void loadRoutingStatus()}
              disabled={routingLoading}
              style={{
                ...secondaryButtonStyle,
                cursor: routingLoading ? "not-allowed" : "pointer",
                opacity: routingLoading ? 0.72 : 1,
              }}
            >
              {routingLoading ? "Loading..." : "Refresh Routing Status"}
            </button>

            <div
              style={{
                fontSize: "13px",
                color: "var(--app-text-muted)",
              }}
            >
              Shows the current default task to provider to model mapping from the backend router.
            </div>
          </div>

          {routingDiagnostics?.routes ? (
            <div
              style={{
                display: "grid",
                gap: "10px",
              }}
            >
              {Object.entries(routingDiagnostics.routes).map(([task, route]) => {
                const detail = routingDiagnostics.route_details?.[task];

                return (
                  <div
                    key={task}
                    style={{
                      ...diagnosticCardStyle,
                      display: "grid",
                      gap: "8px",
                    }}
                  >
                    <div
                      style={{
                        fontSize: "13px",
                        fontWeight: 700,
                        color: "var(--app-text-strong)",
                      }}
                    >
                      {task}
                    </div>
                    <div style={{ fontSize: "13px", color: "var(--app-text-muted)" }}>
                      Tier: <strong>{route.tier || "unknown"}</strong>
                    </div>
                    <div style={{ fontSize: "13px", color: "var(--app-text-muted)" }}>
                      Provider: <strong>{route.provider || "unknown"}</strong>
                    </div>
                    <div style={{ fontSize: "13px", color: "var(--app-text-muted)" }}>
                      Model: <strong>{route.model || "unknown"}</strong>
                    </div>

                    {detail ? (
                      <div
                        style={{
                          borderTop: "1px solid var(--app-surface-border)",
                          paddingTop: "8px",
                          display: "grid",
                          gap: "8px",
                        }}
                      >
                        <div style={{ fontSize: "12px", fontWeight: 700, color: "var(--app-text-muted)" }}>
                          Resolution
                        </div>
                        <div style={{ fontSize: "12px", color: "var(--app-text-muted)" }}>
                          Provider selected from:{" "}
                          <strong>{detail.provider_resolution?.selected_from || "fallback"}</strong>
                        </div>
                        <div style={{ fontSize: "12px", color: "var(--app-text-muted)" }}>
                          Model selected from:{" "}
                          <strong>{detail.model_resolution?.selected_from || "fallback"}</strong>
                        </div>

                        {detail.provider_resolution?.candidates?.length ? (
                          <div style={{ display: "grid", gap: "6px" }}>
                            <div style={{ fontSize: "12px", fontWeight: 700, color: "var(--app-text-muted)" }}>
                              Provider Inputs
                            </div>
                            {detail.provider_resolution.candidates.map((candidate) => (
                              <div
                                key={`${task}-provider-${candidate.source}`}
                                style={{
                                  ...candidateRowStyle(candidate),
                                  display: "flex",
                                  justifyContent: "space-between",
                                  gap: "12px",
                                }}
                              >
                                <span>{candidate.source}</span>
                                <strong>{renderCandidateValue(candidate.value)}</strong>
                              </div>
                            ))}
                          </div>
                        ) : null}

                        {detail.model_resolution?.candidates?.length ? (
                          <div style={{ display: "grid", gap: "6px" }}>
                            <div style={{ fontSize: "12px", fontWeight: 700, color: "var(--app-text-muted)" }}>
                              Model Inputs
                            </div>
                            {detail.model_resolution.candidates.map((candidate) => (
                              <div
                                key={`${task}-model-${candidate.source}`}
                                style={{
                                  ...candidateRowStyle(candidate),
                                  display: "grid",
                                  gap: "4px",
                                }}
                              >
                                <div
                                  style={{
                                    display: "flex",
                                    justifyContent: "space-between",
                                    gap: "12px",
                                  }}
                                >
                                  <span>{candidate.source}</span>
                                  <strong>{renderCandidateValue(candidate.value)}</strong>
                                </div>
                                <div style={{ color: "var(--app-text-muted)" }}>
                                  {candidate.used
                                    ? "used"
                                    : candidate.compatible === false
                                      ? "ignored: incompatible with selected provider"
                                      : "available but not selected"}
                                </div>
                              </div>
                            ))}
                          </div>
                        ) : null}
                      </div>
                    ) : null}
                  </div>
                );
              })}
            </div>
          ) : (
            <div
              style={{
                border: "1px solid var(--app-surface-border)",
                background: "var(--app-surface-muted-bg)",
                color: "var(--app-text-muted)",
                borderRadius: "12px",
                padding: "12px 14px",
                fontSize: "13px",
              }}
            >
              Routing diagnostics are not available yet.
            </div>
          )}

          {routingDiagnostics?.warnings?.length ? (
            <div
              style={{
                display: "grid",
                gap: "8px",
              }}
            >
              {routingDiagnostics.warnings.map((warning) => (
                <div
                  key={warning}
                  style={{
                    ...noticeStyle("warning"),
                  }}
                >
                  {warning}
                </div>
              ))}
            </div>
          ) : null}

          <div
            style={{
              borderTop: "1px solid var(--app-surface-border)",
              paddingTop: "8px",
              display: "grid",
              gap: "10px",
            }}
          >
            <div
              style={{
                fontSize: "13px",
                fontWeight: 700,
                color: "var(--app-text-strong)",
              }}
            >
              Recent Routing Usage
            </div>

            <div
              style={{
                display: "flex",
                gap: "10px",
                flexWrap: "wrap",
              }}
            >
              <div
                style={metricChipStyle}
              >
                Total events: <strong>{routingDiagnostics?.telemetry?.total_events ?? 0}</strong>
              </div>
              <div
                style={metricChipStyle}
              >
                Last event: <strong>{routingDiagnostics?.telemetry?.last_event_at || "N/A"}</strong>
              </div>
              <div
                style={metricChipStyle}
              >
                Success rate: <strong>{formatPercent(routingDiagnostics?.telemetry?.success_rate)}</strong>
              </div>
              <div
                style={metricChipStyle}
              >
                Failure rate: <strong>{formatPercent(routingDiagnostics?.telemetry?.failure_rate)}</strong>
              </div>
              <div
                style={metricChipStyle}
              >
                Fallbacks: <strong>{routingDiagnostics?.telemetry?.fallback_count ?? 0}</strong>
              </div>
            </div>

            {(["outcomes", "providers", "models", "tasks"] as const).map((section) => {
              const entries = Object.entries(routingDiagnostics?.telemetry?.[section] || {});
              if (!entries.length) {
                return null;
              }

              return (
                <div
                  key={section}
                  style={{
                    display: "grid",
                    gap: "8px",
                  }}
                >
                  <div
                    style={{
                      fontSize: "12px",
                      fontWeight: 700,
                      color: "var(--app-text-muted)",
                      textTransform: "capitalize",
                    }}
                  >
                    {section}
                  </div>
                  <div
                    style={{
                      display: "grid",
                      gap: "8px",
                    }}
                  >
                    {entries.map(([label, count]) => (
                      <div
                        key={`${section}-${label}`}
                        style={countRowStyle}
                      >
                        <span>{label}</span>
                        <strong>{count}</strong>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}

            {(["recent_providers", "recent_models", "recent_tasks"] as const).map((section) => {
              const entries = Object.entries(routingDiagnostics?.telemetry?.[section] || {});
              if (!entries.length) {
                return null;
              }

              const label = section.replace("recent_", "Recent ").replace("_", " ");
              return (
                <div
                  key={section}
                  style={{
                    display: "grid",
                    gap: "8px",
                  }}
                >
                  <div
                    style={{
                      fontSize: "12px",
                      fontWeight: 700,
                      color: "var(--app-text-muted)",
                    }}
                  >
                    {label} (last {routingDiagnostics?.telemetry?.recent_window_size ?? 0} events)
                  </div>
                  <div
                    style={{
                      display: "grid",
                      gap: "8px",
                    }}
                  >
                    {entries.map(([labelValue, count]) => (
                      <div
                        key={`${section}-${labelValue}`}
                        style={countRowStyle}
                      >
                        <span>{labelValue}</span>
                        <strong>{count}</strong>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}

            {Object.entries(routingDiagnostics?.telemetry?.time_windows || {}).map(([windowLabel, windowData]) => (
              <div
                key={windowLabel}
                style={{
                  borderTop: "1px solid var(--app-surface-border)",
                  paddingTop: "10px",
                  display: "grid",
                  gap: "10px",
                }}
              >
                <div
                  style={{
                    fontSize: "13px",
                    fontWeight: 700,
                    color: "var(--app-text-strong)",
                  }}
                >
                  {windowLabel} Routing Trend
                </div>

                <div
                  style={{
                    display: "flex",
                    gap: "10px",
                    flexWrap: "wrap",
                  }}
                >
                  <div
                    style={metricChipStyle}
                  >
                    Events: <strong>{windowData.total_events ?? 0}</strong>
                  </div>
                  <div
                    style={metricChipStyle}
                  >
                    Success: <strong>{formatPercent(windowData.success_rate)}</strong>
                  </div>
                  <div
                    style={metricChipStyle}
                  >
                    Failure: <strong>{formatPercent(windowData.failure_rate)}</strong>
                  </div>
                  <div
                    style={metricChipStyle}
                  >
                    Fallbacks: <strong>{windowData.fallback_count ?? 0}</strong>
                  </div>
                </div>

                {(["providers", "models", "tasks"] as const).map((section) => {
                  const entries = Object.entries(windowData[section] || {});
                  if (!entries.length) {
                    return null;
                  }

                  return (
                    <div
                      key={`${windowLabel}-${section}`}
                      style={{
                        display: "grid",
                        gap: "8px",
                      }}
                    >
                      <div
                        style={{
                          fontSize: "12px",
                          fontWeight: 700,
                          color: "var(--app-text-muted)",
                          textTransform: "capitalize",
                        }}
                      >
                        {section}
                      </div>
                      <div
                        style={{
                          display: "grid",
                          gap: "8px",
                        }}
                      >
                        {entries.map(([label, count]) => (
                          <div
                            key={`${windowLabel}-${section}-${label}`}
                            style={countRowStyle}
                          >
                            <span>{label}</span>
                            <strong>{count}</strong>
                          </div>
                        ))}
                      </div>
                    </div>
                  );
                })}
              </div>
            ))}
          </div>
        </div>
        </SectionCard>
      </RequireAdminAuth>
    </AppContainer>
  );
}
