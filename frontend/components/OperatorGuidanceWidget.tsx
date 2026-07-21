"use client";

import { FormEvent, Suspense, useMemo, useState } from "react";
import { usePathname, useSearchParams } from "next/navigation";

import { buildGlobalGuidanceAnswer, buildGuidanceAnswer, detectGuidanceLanguage, findGuidanceEntry } from "./operatorGuidanceData";
import { buildMiniRagGuidanceResponse } from "./operatorGuidanceRetriever";
import { buildStateAwareGuidanceResponse } from "./operatorGuidanceState";

type WidgetMessage = {
  id: string;
  role: "operator" | "assistant";
  content: string;
};

export default function OperatorGuidanceWidget() {
  return (
    <Suspense fallback={null}>
      <OperatorGuidanceWidgetInner />
    </Suspense>
  );
}

function OperatorGuidanceWidgetInner() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const contextKey = useMemo(() => {
    const query = searchParams.toString();
    return `${pathname || "/"}${query ? `?${query}` : ""}`;
  }, [pathname, searchParams]);
  const [isOpen, setIsOpen] = useState(false);
  const [question, setQuestion] = useState("");
  const initialMessages = useMemo<WidgetMessage[]>(() => [
    {
      id: "welcome",
      role: "assistant",
      content: "Ask about this page, another workflow, metrics, or what to do next. I can answer cross-page questions and explain when a topic belongs somewhere else.",
    },
  ], []);
  const [messagesByContext, setMessagesByContext] = useState<Record<string, WidgetMessage[]>>({});
  const messages = messagesByContext[contextKey] || initialMessages;

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = question.trim();
    if (!trimmed) return;

    const language = detectGuidanceLanguage(trimmed);
    const currentPath = typeof window === "undefined" ? pathname || "" : window.location.pathname;
    const pageState = {
      pathname: currentPath,
      text: typeof document === "undefined" ? "" : document.body.innerText,
    };
    const globalAnswer = buildGlobalGuidanceAnswer(trimmed, language, currentPath);
    const stateAwareAnswer = buildStateAwareGuidanceResponse(trimmed, pageState, language);
    const matchedEntry = globalAnswer ? null : findGuidanceEntry(trimmed, currentPath);
    const answer = stateAwareAnswer || (matchedEntry
      ? buildGuidanceAnswer(matchedEntry, language)
      : language === "zh"
        ? [
            "我还没有找到这个步骤的明确建议。",
            "你可以问：当前状态是什么意思、下一步应该怎么 review，或者为什么某个按钮不可用。",
          ].join("\n\n")
      : [
            "I do not have a clear recommendation for this exact step yet.",
            "Try asking what the current status means, what the next review action should be, or why a button is disabled.",
          ].join("\n\n"));
    const previousAssistantText = [...messages].reverse().find((message) => message.role === "assistant")?.content || "";
    const groundedAnswer =
      globalAnswer ||
      stateAwareAnswer ||
      (matchedEntry ? answer : buildMiniRagGuidanceResponse(trimmed, currentPath, language, previousAssistantText)) ||
      answer;

    setMessagesByContext((current) => {
      const currentMessages = current[contextKey] || initialMessages;
      return {
        ...current,
        [contextKey]: [
          ...currentMessages,
          { id: `operator-${Date.now()}`, role: "operator", content: trimmed },
          { id: `assistant-${Date.now()}`, role: "assistant", content: groundedAnswer },
        ],
      };
    });
    setQuestion("");
  }

  return (
    <div style={widgetRootStyle}>
      {isOpen ? (
        <section style={panelStyle} aria-label="Operator guidance dialog">
          <div style={panelHeaderStyle}>
            <div>
              <div style={eyebrowStyle}>Operator Guidance</div>
              <div style={titleStyle}>Ask AI Radar</div>
            </div>
            <button type="button" onClick={() => setIsOpen(false)} style={iconButtonStyle} aria-label="Close operator guidance">
              x
            </button>
          </div>

          <div style={messagesStyle}>
            {messages.map((message) => (
              <div key={message.id} style={message.role === "operator" ? operatorBubbleStyle : assistantBubbleStyle}>
                <div style={messageRoleStyle}>{message.role === "operator" ? "You" : "Guidance"}</div>
                <div style={messageContentStyle}>{message.content}</div>
              </div>
            ))}
          </div>

          <form onSubmit={handleSubmit} style={formStyle}>
            <input
              aria-label="Ask operator guidance"
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="Ask about a page, workflow, or metrics"
              style={inputStyle}
            />
            <button type="submit" style={sendButtonStyle}>
              Ask
            </button>
          </form>
        </section>
      ) : null}

      <button type="button" onClick={() => setIsOpen((current) => !current)} style={launcherStyle}>
        Guidance
      </button>
    </div>
  );
}

const widgetRootStyle = {
  position: "fixed",
  right: "22px",
  bottom: "22px",
  zIndex: 80,
  display: "grid",
  justifyItems: "end",
  gap: "10px",
} as const;

const panelStyle = {
  width: "min(420px, calc(100vw - 32px))",
  maxHeight: "min(680px, calc(100vh - 110px))",
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-bg)",
  boxShadow: "0 24px 70px rgba(15, 23, 42, 0.24)",
  padding: "16px",
  display: "grid",
  gap: "12px",
} as const;

const panelHeaderStyle = {
  display: "flex",
  alignItems: "flex-start",
  justifyContent: "space-between",
  gap: "12px",
} as const;

const eyebrowStyle = {
  fontSize: "11px",
  fontWeight: 850,
  color: "var(--app-text-subtle)",
  textTransform: "uppercase",
  letterSpacing: "0.06em",
} as const;

const titleStyle = {
  marginTop: "4px",
  fontSize: "19px",
  lineHeight: 1.2,
  fontWeight: 850,
  color: "var(--app-text-strong)",
} as const;

const iconButtonStyle = {
  width: "32px",
  height: "32px",
  borderRadius: "999px",
  border: "1px solid var(--app-secondary-action-border)",
  background: "var(--app-secondary-action-bg)",
  color: "var(--app-secondary-action-fg)",
  cursor: "pointer",
  fontWeight: 850,
} as const;

const messagesStyle = {
  display: "grid",
  gap: "9px",
  maxHeight: "280px",
  overflowY: "auto",
  paddingRight: "4px",
} as const;

const assistantBubbleStyle = {
  justifySelf: "start",
  maxWidth: "94%",
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  padding: "10px",
  whiteSpace: "pre-wrap",
  overflowWrap: "anywhere",
} as const;

const operatorBubbleStyle = {
  justifySelf: "end",
  maxWidth: "88%",
  border: "1px solid var(--app-info-border)",
  borderRadius: "8px",
  background: "var(--app-info-bg)",
  padding: "10px",
  whiteSpace: "pre-wrap",
  overflowWrap: "anywhere",
} as const;

const messageRoleStyle = {
  fontSize: "11px",
  fontWeight: 850,
  color: "var(--app-text-subtle)",
  textTransform: "uppercase",
  letterSpacing: "0.06em",
} as const;

const messageContentStyle = {
  marginTop: "5px",
  fontSize: "13px",
  lineHeight: 1.55,
  color: "var(--app-text-strong)",
} as const;

const formStyle = {
  display: "grid",
  gridTemplateColumns: "minmax(0, 1fr) auto",
  gap: "8px",
} as const;

const inputStyle = {
  minWidth: 0,
  minHeight: "40px",
  border: "1px solid var(--app-input-border)",
  borderRadius: "8px",
  padding: "8px 10px",
  fontSize: "13px",
  color: "var(--app-input-fg)",
  background: "var(--app-input-bg)",
} as const;

const sendButtonStyle = {
  minHeight: "40px",
  border: "1px solid var(--app-primary-action-border)",
  borderRadius: "8px",
  background: "var(--app-primary-action-bg)",
  color: "var(--app-primary-action-fg)",
  padding: "8px 12px",
  fontSize: "13px",
  fontWeight: 850,
  cursor: "pointer",
} as const;

const launcherStyle = {
  minHeight: "44px",
  border: "1px solid var(--app-primary-action-border)",
  borderRadius: "999px",
  background: "var(--app-primary-action-bg)",
  color: "var(--app-primary-action-fg)",
  padding: "10px 16px",
  fontSize: "14px",
  fontWeight: 850,
  cursor: "pointer",
  boxShadow: "0 14px 34px rgba(15, 23, 42, 0.22)",
} as const;
