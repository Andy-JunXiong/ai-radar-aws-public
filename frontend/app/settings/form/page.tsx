"use client";

import { useEffect, useMemo, useState } from "react";
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

type ContextShape = {
  user_profile?: {
    role?: string;
    experience_level?: string;
    industry?: string;
    goals?: string[];
  };
  interpretation_preference?: {
    topics_of_interest?: string[] | string;
    signal_filters?: string[] | string;
    intelligence_focus?: string[] | string;
    writing_style?: string;
  };
};

const DEFAULT_CONTEXT: ContextShape = {
  user_profile: {
    role: "",
    experience_level: "",
    industry: "",
    goals: [],
  },
  interpretation_preference: {
    topics_of_interest: [],
    signal_filters: [],
    intelligence_focus: [],
    writing_style: "",
  },
};

function toCommaString(value?: string[] | string): string {
  if (Array.isArray(value)) return value.join(", ");
  return value || "";
}

function toArray(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function normalizeContext(input: unknown): ContextShape {
  if (!input || typeof input !== "object") return DEFAULT_CONTEXT;
  const value = input as ContextShape;

  return {
    user_profile: {
      role: value.user_profile?.role || "",
      experience_level: value.user_profile?.experience_level || "",
      industry: value.user_profile?.industry || "",
      goals: Array.isArray(value.user_profile?.goals) ? value.user_profile?.goals : [],
    },
    interpretation_preference: {
      topics_of_interest: Array.isArray(value.interpretation_preference?.topics_of_interest)
        ? value.interpretation_preference?.topics_of_interest
        : typeof value.interpretation_preference?.topics_of_interest === "string"
          ? toArray(value.interpretation_preference.topics_of_interest)
          : [],
      signal_filters: Array.isArray(value.interpretation_preference?.signal_filters)
        ? value.interpretation_preference?.signal_filters
        : typeof value.interpretation_preference?.signal_filters === "string"
          ? toArray(value.interpretation_preference.signal_filters)
          : [],
      intelligence_focus: Array.isArray(value.interpretation_preference?.intelligence_focus)
        ? value.interpretation_preference?.intelligence_focus
        : typeof value.interpretation_preference?.intelligence_focus === "string"
          ? toArray(value.interpretation_preference.intelligence_focus)
          : [],
      writing_style: value.interpretation_preference?.writing_style || "",
    },
  };
}

export default function SettingsFormPage() {
  const [userId, setUserId] = useState("");
  const [scope, setScope] = useState("demo_default");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [errorMessage, setErrorMessage] = useState("");

  const [role, setRole] = useState("");
  const [experienceLevel, setExperienceLevel] = useState("");
  const [industry, setIndustry] = useState("");
  const [goals, setGoals] = useState("");
  const [topicsOfInterest, setTopicsOfInterest] = useState("");
  const [signalFilters, setSignalFilters] = useState("");
  const [intelligenceFocus, setIntelligenceFocus] = useState("");
  const [writingStyle, setWritingStyle] = useState("");

  function hydrateForm(context: unknown) {
    const normalized = normalizeContext(context);

    setRole(normalized.user_profile?.role || "");
    setExperienceLevel(normalized.user_profile?.experience_level || "");
    setIndustry(normalized.user_profile?.industry || "");
    setGoals(toCommaString(normalized.user_profile?.goals));
    setTopicsOfInterest(toCommaString(normalized.interpretation_preference?.topics_of_interest));
    setSignalFilters(toCommaString(normalized.interpretation_preference?.signal_filters));
    setIntelligenceFocus(toCommaString(normalized.interpretation_preference?.intelligence_focus));
    setWritingStyle(normalized.interpretation_preference?.writing_style || "");
  }

  async function loadContext(nextUserId: string) {
    setLoading(true);
    setMessage("");
    setErrorMessage("");

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
      hydrateForm(data.context || DEFAULT_CONTEXT);
    } catch (error) {
      console.error(error);
      setErrorMessage("Failed to load personal context.");
      hydrateForm(DEFAULT_CONTEXT);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const storedUserId = getStoredBetaUserId();
    setUserId(storedUserId);
    void loadContext(storedUserId);
  }, []);

  const builtContext = useMemo<ContextShape>(
    () => ({
      user_profile: {
        role: role.trim(),
        experience_level: experienceLevel.trim(),
        industry: industry.trim(),
        goals: toArray(goals),
      },
      projects: [],
      interpretation_preference: {
        topics_of_interest: toArray(topicsOfInterest),
        signal_filters: toArray(signalFilters),
        intelligence_focus: toArray(intelligenceFocus),
        writing_style: writingStyle.trim(),
      },
    }),
    [
      role,
      experienceLevel,
      industry,
      goals,
      topicsOfInterest,
      signalFilters,
      intelligenceFocus,
      writingStyle,
    ]
  );

  async function handleReload() {
    setStoredBetaUserId(userId);
    await loadContext(userId);
  }

  async function handleSave() {
    const normalizedUserId = userId.trim();
    if (!normalizedUserId) {
      setErrorMessage("A beta user id is required before saving context.");
      setMessage("");
      return;
    }

    setSaving(true);
    setMessage("");
    setErrorMessage("");

    try {
      const response = await adminFetch(apiUrl("/settings/context"), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...buildBetaUserHeaders(normalizedUserId),
        },
        body: JSON.stringify({
          context: builtContext,
        }),
      });

      if (!response.ok) {
        const text = await response.text();
        throw new Error(text || `Failed to save context (${response.status})`);
      }

      setStoredBetaUserId(normalizedUserId);
      setMessage("Personal context saved from the Q&A editor.");
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
          title="Q&A Context Editor"
          description="Use a guided form to build personal context without editing raw JSON. Project intake now lives in Admin so project records have a single source of truth."
        />

        <SectionCard title="Context Identity">
        <div style={{ display: "grid", gap: "12px" }}>
          <label htmlFor="beta-user-id-form" style={labelStyle}>
            Beta User ID
          </label>
          <input
            id="beta-user-id-form"
            value={userId}
            onChange={(event) => setUserId(event.target.value)}
            placeholder="beta-user"
            style={inputStyle}
          />
          <div style={{ display: "flex", gap: "10px", flexWrap: "wrap", alignItems: "center" }}>
            <button onClick={() => void handleReload()} disabled={loading} style={secondaryButtonStyle}>
              {loading ? "Loading..." : "Load Context"}
            </button>
            <div style={{ fontSize: "13px", color: "#6b7280" }}>
              Current scope: <strong style={{ color: "#111827" }}>{scope}</strong>
            </div>
          </div>
        </div>
        </SectionCard>

        <SectionCard title="User Profile">
        <div style={formGridStyle}>
          <Field label="What is your current role?">
            <input value={role} onChange={(e) => setRole(e.target.value)} style={inputStyle} placeholder="Product manager, founder, engineer..." />
          </Field>
          <Field label="What is your experience level?">
            <input value={experienceLevel} onChange={(e) => setExperienceLevel(e.target.value)} style={inputStyle} placeholder="Junior, mid, senior..." />
          </Field>
          <Field label="What industry are you focused on?">
            <input value={industry} onChange={(e) => setIndustry(e.target.value)} style={inputStyle} placeholder="AI products, SaaS, consulting..." />
          </Field>
          <Field label="What are your current goals?">
            <textarea value={goals} onChange={(e) => setGoals(e.target.value)} style={textareaStyle} placeholder="Comma-separated goals" />
          </Field>
        </div>
        </SectionCard>

        <SectionCard title="Project Intake Lives In Admin">
        <div style={{ display: "grid", gap: "12px" }}>
          <div style={{ fontSize: "14px", color: "#4b5563", lineHeight: 1.7 }}>
            Project records are now managed separately so they do not conflict with personal context.
            Add or update projects from the dedicated admin intake flow, then come back here for user profile
            and interpretation preferences.
          </div>
          <div>
            <Link href="/admin/projects" style={secondaryLinkStyle}>
              Open Project Intake
            </Link>
          </div>
        </div>
        </SectionCard>

        <SectionCard title="Interpretation Preference">
        <div style={formGridStyle}>
          <Field label="What topics should AI Radar pay attention to?">
            <textarea value={topicsOfInterest} onChange={(e) => setTopicsOfInterest(e.target.value)} style={textareaStyle} placeholder="Comma-separated topics of interest" />
          </Field>
          <Field label="Are there any signal filters or boundaries?">
            <textarea value={signalFilters} onChange={(e) => setSignalFilters(e.target.value)} style={textareaStyle} placeholder="Comma-separated filters or exclusions" />
          </Field>
          <Field label="What kind of intelligence do you care about most?">
            <textarea value={intelligenceFocus} onChange={(e) => setIntelligenceFocus(e.target.value)} style={textareaStyle} placeholder="Projects, career moves, positioning, product strategy..." />
          </Field>
          <Field label="Preferred writing or reasoning style">
            <input value={writingStyle} onChange={(e) => setWritingStyle(e.target.value)} style={inputStyle} placeholder="Concise, strategic, recruiter-friendly..." />
          </Field>
        </div>
        </SectionCard>

        <SectionCard title="Generated Context Preview">
        <div style={{ display: "grid", gap: "12px" }}>
          <textarea
            readOnly
            value={JSON.stringify(builtContext, null, 2)}
            spellCheck={false}
            style={{
              ...textareaStyle,
              minHeight: "320px",
              fontFamily:
                'ui-monospace, SFMono-Regular, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace',
              fontSize: "13px",
            }}
          />

          <div style={{ display: "flex", gap: "10px", flexWrap: "wrap", alignItems: "center" }}>
            <button onClick={() => void handleSave()} disabled={saving} style={primaryButtonStyle}>
              {saving ? "Saving..." : "Save Context"}
            </button>
            <Link href="/settings" style={secondaryLinkStyle}>
              Back to JSON Editor
            </Link>
            <Link href="/admin" style={secondaryLinkStyle}>
              Back to Previous Page
            </Link>
          </div>

          {message ? <Notice tone="success" text={message} /> : null}
          {errorMessage ? <Notice tone="error" text={errorMessage} /> : null}
        </div>
        </SectionCard>
      </RequireAdminAuth>
    </AppContainer>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label style={{ display: "grid", gap: "8px" }}>
      <span style={labelStyle}>{label}</span>
      {children}
    </label>
  );
}

function Notice({ tone, text }: { tone: "success" | "error"; text: string }) {
  const styles =
    tone === "success"
      ? {
          border: "1px solid #bbf7d0",
          background: "#ecfdf3",
          color: "#166534",
        }
      : {
          border: "1px solid #fecaca",
          background: "#fff1f2",
          color: "#be123c",
        };

  return (
    <div
      style={{
        ...styles,
        borderRadius: "12px",
        padding: "12px 14px",
        fontSize: "13px",
      }}
    >
      {text}
    </div>
  );
}

const formGridStyle = {
  display: "grid",
  gap: "16px",
} as const;

const labelStyle = {
  fontSize: "13px",
  fontWeight: 700,
  color: "#374151",
} as const;

const inputStyle = {
  border: "1px solid #d1d5db",
  borderRadius: "12px",
  padding: "12px 14px",
  fontSize: "14px",
  color: "#111827",
} as const;

const textareaStyle = {
  width: "100%",
  minHeight: "120px",
  border: "1px solid #d1d5db",
  borderRadius: "16px",
  padding: "14px 16px",
  fontSize: "14px",
  lineHeight: 1.7,
  color: "#111827",
  resize: "vertical" as const,
} as const;

const primaryButtonStyle = {
  padding: "10px 14px",
  borderRadius: "10px",
  border: "1px solid #111827",
  background: "#111827",
  color: "#ffffff",
  cursor: "pointer",
  fontWeight: 700,
} as const;

const secondaryButtonStyle = {
  padding: "10px 14px",
  borderRadius: "10px",
  border: "1px solid #d1d5db",
  background: "#ffffff",
  cursor: "pointer",
  fontWeight: 600,
} as const;

const secondaryLinkStyle = {
  padding: "10px 14px",
  borderRadius: "10px",
  border: "1px solid #d1d5db",
  color: "#111827",
  textDecoration: "none",
  fontWeight: 600,
} as const;
