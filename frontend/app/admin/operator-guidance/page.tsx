"use client";

import Link from "next/link";
import { FormEvent, useMemo, useState } from "react";

import AppContainer from "@/components/AppContainer";
import PageHeader from "@/components/PageHeader";
import RequireAdminAuth from "@/components/RequireAdminAuth";
import SectionCard from "@/components/SectionCard";
import { buildGuidanceAnswer, guidanceEntries, type GuidanceEntry } from "@/components/operatorGuidanceData";

type ChatMessage = {
  id: string;
  role: "operator" | "assistant";
  content: string;
};

export default function OperatorGuidancePage() {
  const [selectedState, setSelectedState] = useState(guidanceEntries[0].stateIdentifier);
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "assistant-welcome",
      role: "assistant",
      content:
        "Ask what to do next after choosing a mapped state. I only answer from the static operator guidance map.",
    },
  ]);

  const selectedEntry = useMemo(
    () => guidanceEntries.find((entry) => entry.stateIdentifier === selectedState) || guidanceEntries[0],
    [selectedState]
  );

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmedQuestion = question.trim();
    if (!trimmedQuestion) {
      return;
    }

    const operatorMessage: ChatMessage = {
      id: `operator-${Date.now()}`,
      role: "operator",
      content: trimmedQuestion,
    };
    const assistantMessage: ChatMessage = {
      id: `assistant-${Date.now()}`,
      role: "assistant",
      content: buildGuidanceAnswer(selectedEntry),
    };

    setMessages((current) => [...current, operatorMessage, assistantMessage]);
    setQuestion("");
  }

  return (
    <AppContainer>
      <RequireAdminAuth>
        <PageHeader
          title="Operator Guidance"
          description="Static admin guidance for known AI Radar state transitions. These notes are operating guidance only; they are not evidence, verification, or a state mutation path."
          size="compact"
        />

        <SectionCard title="Guidance Boundary">
          <div style={boundaryGridStyle}>
            <BoundaryCard
              label="Source"
              value="docs/operator-guidance/state-action-map.yaml"
              description="This page mirrors the current Phase 2 docs mapping for local operator use."
            />
            <BoundaryCard
              label="Allowed"
              value="Static next-action guidance"
              description="Use it to remember safe review paths and the governing source to inspect."
            />
            <BoundaryCard
              label="Not Allowed"
              value="Evidence or verification"
              description="Guidance does not prove external claims, bypass gates, or create Project Takeaway eligibility."
            />
          </div>
          <div style={linkRowStyle}>
            <Link href="/workspace/projects/review" style={secondaryButtonStyle}>
              Review Inbox
            </Link>
            <Link href="/knowledge" style={secondaryButtonStyle}>
              Knowledge
            </Link>
            <Link href="/manual" style={secondaryButtonStyle}>
              Manual Upload
            </Link>
          </div>
        </SectionCard>

        <SectionCard title="Ask Next Step">
          <div style={chatLayoutStyle}>
            <div style={chatControlPanelStyle}>
              <label htmlFor="guidance-state" style={fieldLabelStyle}>
                Current mapped state
              </label>
              <select
                id="guidance-state"
                value={selectedState}
                onChange={(event) => setSelectedState(event.target.value)}
                style={selectStyle}
              >
                {guidanceEntries.map((entry) => (
                  <option key={entry.stateIdentifier} value={entry.stateIdentifier}>
                    {entry.stateLabel}
                  </option>
                ))}
              </select>
              <div style={selectedStateStyle}>{selectedEntry.stateIdentifier}</div>
              <div style={chatBoundaryNoteStyle}>
                This assistant is static-map only. It cannot verify claims, trigger actions, create records, or bypass gates.
              </div>
            </div>

            <div style={chatPanelStyle}>
              <div style={messageListStyle}>
                {messages.map((message) => (
                  <div
                    key={message.id}
                    style={message.role === "operator" ? operatorMessageStyle : assistantMessageStyle}
                  >
                    <div style={messageRoleStyle}>{message.role === "operator" ? "You" : "Operator Guidance"}</div>
                    <div style={messageContentStyle}>{message.content}</div>
                  </div>
                ))}
              </div>
              <form onSubmit={handleSubmit} style={chatFormStyle}>
                <input
                  aria-label="Ask operator guidance"
                  value={question}
                  onChange={(event) => setQuestion(event.target.value)}
                  placeholder="What should I do next?"
                  style={chatInputStyle}
                />
                <button type="submit" style={chatButtonStyle}>
                  Ask
                </button>
              </form>
            </div>
          </div>
        </SectionCard>

        <div style={entryGridStyle}>
          {guidanceEntries.map((entry) => (
            <GuidanceCard key={entry.stateIdentifier} entry={entry} />
          ))}
        </div>
      </RequireAdminAuth>
    </AppContainer>
  );
}

function GuidanceCard({ entry }: { entry: GuidanceEntry }) {
  return (
    <article style={entryCardStyle}>
      <div style={entryHeaderStyle}>
        <div>
          <div style={identifierStyle}>{entry.stateIdentifier}</div>
          <h2 style={entryTitleStyle}>{entry.stateLabel}</h2>
        </div>
        <span style={statusPillStyle}>Static</span>
      </div>

      <div style={sectionGridStyle}>
        <GuidanceList title="Applies When" items={entry.appliesWhen} tone="neutral" />
        <GuidanceList title="Next Actions" items={entry.nextActions} tone="positive" />
        <GuidanceList title="Not Allowed" items={entry.notAllowed} tone="warning" />
        <GuidanceList title="Governing Sources" items={entry.governingSources} tone="source" />
      </div>
    </article>
  );
}

function GuidanceList({
  title,
  items,
  tone,
}: {
  title: string;
  items: string[];
  tone: "neutral" | "positive" | "warning" | "source";
}) {
  return (
    <section style={listSectionStyle}>
      <div style={{ ...listTitleStyle, color: toneColor[tone] }}>{title}</div>
      <ul style={listStyle}>
        {items.map((item) => (
          <li key={item} style={listItemStyle}>
            {item}
          </li>
        ))}
      </ul>
    </section>
  );
}

function BoundaryCard({
  label,
  value,
  description,
}: {
  label: string;
  value: string;
  description: string;
}) {
  return (
    <div style={boundaryCardStyle}>
      <div style={boundaryLabelStyle}>{label}</div>
      <div style={boundaryValueStyle}>{value}</div>
      <div style={boundaryDescriptionStyle}>{description}</div>
    </div>
  );
}

const boundaryGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
  gap: "12px",
} as const;

const boundaryCardStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  padding: "16px",
} as const;

const boundaryLabelStyle = {
  fontSize: "12px",
  fontWeight: 800,
  color: "var(--app-text-subtle)",
  textTransform: "uppercase",
  letterSpacing: 0,
} as const;

const boundaryValueStyle = {
  marginTop: "8px",
  fontSize: "17px",
  fontWeight: 850,
  color: "var(--app-text-strong)",
} as const;

const boundaryDescriptionStyle = {
  marginTop: "8px",
  fontSize: "14px",
  lineHeight: 1.65,
  color: "var(--app-text-muted)",
} as const;

const linkRowStyle = {
  display: "flex",
  flexWrap: "wrap",
  gap: "10px",
  marginTop: "18px",
} as const;

const chatLayoutStyle = {
  display: "grid",
  gridTemplateColumns: "minmax(240px, 0.8fr) minmax(320px, 1.2fr)",
  gap: "16px",
  alignItems: "stretch",
} as const;

const chatControlPanelStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  padding: "16px",
  display: "grid",
  alignContent: "start",
  gap: "10px",
  minWidth: 0,
} as const;

const fieldLabelStyle = {
  fontSize: "12px",
  fontWeight: 850,
  color: "var(--app-text-subtle)",
  textTransform: "uppercase",
  letterSpacing: 0,
} as const;

const selectStyle = {
  width: "100%",
  minHeight: "42px",
  border: "1px solid var(--app-input-border)",
  borderRadius: "8px",
  background: "var(--app-input-bg)",
  color: "var(--app-input-fg)",
  padding: "8px 10px",
  fontSize: "14px",
  fontWeight: 650,
} as const;

const selectedStateStyle = {
  fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace',
  fontSize: "12px",
  color: "var(--app-text-subtle)",
  overflowWrap: "anywhere",
} as const;

const chatBoundaryNoteStyle = {
  borderTop: "1px solid var(--app-surface-border)",
  marginTop: "4px",
  paddingTop: "12px",
  fontSize: "14px",
  lineHeight: 1.65,
  color: "var(--app-text-muted)",
} as const;

const chatPanelStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  padding: "14px",
  display: "grid",
  gap: "12px",
  minWidth: 0,
} as const;

const messageListStyle = {
  display: "grid",
  gap: "10px",
  maxHeight: "390px",
  overflowY: "auto",
  paddingRight: "4px",
} as const;

const assistantMessageStyle = {
  justifySelf: "start",
  maxWidth: "92%",
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-bg)",
  padding: "12px",
  whiteSpace: "pre-wrap",
  overflowWrap: "anywhere",
} as const;

const operatorMessageStyle = {
  justifySelf: "end",
  maxWidth: "86%",
  border: "1px solid var(--app-info-border)",
  borderRadius: "8px",
  background: "var(--app-info-bg)",
  padding: "12px",
  whiteSpace: "pre-wrap",
  overflowWrap: "anywhere",
} as const;

const messageRoleStyle = {
  fontSize: "12px",
  fontWeight: 850,
  color: "var(--app-text-subtle)",
  textTransform: "uppercase",
  letterSpacing: 0,
} as const;

const messageContentStyle = {
  marginTop: "6px",
  fontSize: "14px",
  lineHeight: 1.65,
  color: "var(--app-text-strong)",
} as const;

const chatFormStyle = {
  display: "grid",
  gridTemplateColumns: "minmax(0, 1fr) auto",
  gap: "10px",
} as const;

const chatInputStyle = {
  minWidth: 0,
  minHeight: "42px",
  border: "1px solid var(--app-input-border)",
  borderRadius: "8px",
  padding: "9px 12px",
  fontSize: "14px",
  color: "var(--app-input-fg)",
  background: "var(--app-input-bg)",
} as const;

const chatButtonStyle = {
  minHeight: "42px",
  border: "1px solid var(--app-primary-action-border)",
  borderRadius: "8px",
  background: "var(--app-primary-action-bg)",
  color: "var(--app-primary-action-fg)",
  padding: "9px 16px",
  fontSize: "14px",
  fontWeight: 800,
  cursor: "pointer",
} as const;

const secondaryButtonStyle = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  minHeight: "40px",
  padding: "9px 14px",
  borderRadius: "999px",
  border: "1px solid var(--app-secondary-action-border)",
  background: "var(--app-secondary-action-bg)",
  color: "var(--app-secondary-action-fg)",
  textDecoration: "none",
  fontSize: "14px",
  fontWeight: 750,
} as const;

const entryGridStyle = {
  display: "grid",
  gap: "18px",
} as const;

const entryCardStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-bg)",
  padding: "24px",
  boxShadow: "var(--app-surface-shadow)",
  overflow: "hidden",
} as const;

const entryHeaderStyle = {
  display: "flex",
  justifyContent: "space-between",
  gap: "16px",
  alignItems: "flex-start",
} as const;

const identifierStyle = {
  fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace',
  fontSize: "12px",
  color: "var(--app-text-subtle)",
  overflowWrap: "anywhere",
} as const;

const entryTitleStyle = {
  marginTop: "8px",
  marginBottom: 0,
  fontSize: "24px",
  lineHeight: 1.25,
  fontWeight: 850,
  color: "var(--app-text-strong)",
  letterSpacing: 0,
} as const;

const statusPillStyle = {
  flex: "0 0 auto",
  border: "1px solid var(--app-success-border)",
  background: "var(--app-success-bg)",
  color: "var(--app-success-fg)",
  borderRadius: "999px",
  padding: "6px 10px",
  fontSize: "12px",
  fontWeight: 850,
  textTransform: "uppercase",
  letterSpacing: 0,
} as const;

const sectionGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
  gap: "14px",
  marginTop: "20px",
} as const;

const listSectionStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  padding: "16px",
  minWidth: 0,
} as const;

const listTitleStyle = {
  fontSize: "13px",
  fontWeight: 850,
  textTransform: "uppercase",
  letterSpacing: 0,
} as const;

const listStyle = {
  display: "grid",
  gap: "8px",
  marginTop: "12px",
  marginBottom: 0,
  paddingLeft: "18px",
} as const;

const listItemStyle = {
  fontSize: "14px",
  lineHeight: 1.65,
  color: "var(--app-text-muted)",
  paddingLeft: "2px",
  overflowWrap: "anywhere",
  wordBreak: "break-word",
} as const;

const toneColor = {
  neutral: "var(--app-text-muted)",
  positive: "var(--app-success-fg)",
  warning: "var(--app-warning-fg)",
  source: "var(--app-info-fg)",
} as const;
