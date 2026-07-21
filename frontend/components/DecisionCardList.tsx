"use client";

import Link from "next/link";
import { type CSSProperties, useState } from "react";

import { DecisionCard, updateDecisionFeedback } from "@/lib/decisions";

type Props = {
  items: DecisionCard[];
  emptyText: string;
  compact?: boolean;
  onUpdated?: (card: DecisionCard) => void;
};

const buttonStyle: CSSProperties = {
  border: "1px solid var(--app-secondary-action-border)",
  borderRadius: "8px",
  padding: "7px 12px",
  background: "var(--app-secondary-action-bg)",
  cursor: "pointer",
  color: "var(--app-secondary-action-fg)",
  fontSize: "13px",
  fontWeight: 600,
};

const primaryButtonStyle: CSSProperties = {
  ...buttonStyle,
  border: "1px solid var(--app-primary-action-border)",
  background: "var(--app-primary-action-bg)",
  color: "var(--app-primary-action-fg)",
};

const metadataPillStyle: CSSProperties = {
  border: "1px solid var(--app-chip-border)",
  borderRadius: "999px",
  background: "var(--app-chip-bg)",
  color: "var(--app-chip-fg)",
  padding: "5px 9px",
  fontSize: "12px",
  fontWeight: 600,
};

const noteBlockStyle: CSSProperties = {
  marginTop: "12px",
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-soft-bg)",
  padding: "12px 14px",
};

const noteLabelStyle: CSSProperties = {
  color: "var(--app-text-muted)",
  fontSize: "12px",
  fontWeight: 700,
  textTransform: "uppercase",
  letterSpacing: "0.4px",
  marginBottom: "4px",
};

export default function DecisionCardList({ items, emptyText, compact = false, onUpdated }: Props) {
  const [pendingId, setPendingId] = useState("");

  const stripHedgePrefix = (value?: string | null) => {
    const text = (value || "").trim();
    if (!text) return "";
    return text.replace(/^(uncertain|maybe|possibly|tentative)\s*:\s*/i, "").trim();
  };

  const formatReviewDate = (value?: string | null) => {
    if (!value) return "n/a";
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? "n/a" : parsed.toLocaleDateString();
  };

  const normalizeActionType = (value?: string | null) => {
    const raw = String(value || "").trim().toLowerCase();
    if (raw === "build" || raw === "apply") return "project";
    if (raw === "project" || raw === "watch" || raw === "learn" || raw === "ignore") return raw;
    return "watch";
  };

  const getActionTypeMeta = (value?: string | null) => {
    const normalized = normalizeActionType(value);
    if (normalized === "project") {
      return {
        label: "Project Route",
        help: "Ready to flow into project takeaway or roadmap work.",
        nextLabel: "Project next step",
      };
    }
    if (normalized === "learn") {
      return {
        label: "Learning Queue",
        help: "Worth studying before we decide on project changes.",
        nextLabel: "Learning plan",
      };
    }
    if (normalized === "ignore") {
      return {
        label: "Ignore",
        help: "No follow-up is recommended right now.",
        nextLabel: "Disposition",
      };
    }
    return {
      label: "Watch Queue",
      help: "Track this over time before turning it into project work.",
      nextLabel: "Watch plan",
    };
  };

  const dedupedItems = items.reduce<DecisionCard[]>((acc, item) => {
    const sourceContext = String(item.source_context || "").toLowerCase();
    const signalSignature = (item.signal_refs || []).slice().sort().join(",").toLowerCase();
    const projectSignature = (item.project_refs || []).slice().sort().join(",").toLowerCase();
    const signature =
      sourceContext === "signal_detail" || sourceContext === "manual_signal_detail"
        ? [sourceContext, signalSignature].join("|")
        : [sourceContext, stripHedgePrefix(item.title).toLowerCase(), signalSignature, projectSignature].join("|");

    const existingIndex = acc.findIndex((candidate) => {
      const candidateSourceContext = String(candidate.source_context || "").toLowerCase();
      const candidateSignalSignature = (candidate.signal_refs || []).slice().sort().join(",").toLowerCase();
      const candidateProjectSignature = (candidate.project_refs || []).slice().sort().join(",").toLowerCase();
      const candidateSignature =
        candidateSourceContext === "signal_detail" || candidateSourceContext === "manual_signal_detail"
          ? [candidateSourceContext, candidateSignalSignature].join("|")
          : [
              candidateSourceContext,
              stripHedgePrefix(candidate.title).toLowerCase(),
              candidateSignalSignature,
              candidateProjectSignature,
            ].join("|");
      return candidateSignature === signature;
    });

    if (existingIndex === -1) {
      acc.push(item);
      return acc;
    }

    const existingUpdatedAt = Date.parse(acc[existingIndex].updated_at || "");
    const nextUpdatedAt = Date.parse(item.updated_at || "");
    if (Number.isNaN(existingUpdatedAt) || (!Number.isNaN(nextUpdatedAt) && nextUpdatedAt > existingUpdatedAt)) {
      acc[existingIndex] = item;
    }
    return acc;
  }, []);

  if (!dedupedItems.length) {
    return <div style={{ color: "var(--app-text-muted)", fontSize: "14px" }}>{emptyText}</div>;
  }

  const handleAction = async (
    cardId: string,
    action: "saved" | "ignored" | "acted" | "deferred",
  ) => {
    try {
      setPendingId(cardId);
      const updated = await updateDecisionFeedback(cardId, action);
      onUpdated?.(updated);
    } catch (error) {
      console.error(error);
    } finally {
      setPendingId("");
    }
  };

  return (
    <div style={{ display: "grid", gap: compact ? "12px" : "16px" }}>
      {dedupedItems.map((item) => {
        const actionMeta = getActionTypeMeta(item.action_type);
        return (
        <div
          key={item.id}
          style={{
            border: "1px solid var(--app-surface-border)",
            borderRadius: "8px",
            padding: compact ? "14px" : "18px",
            background: "var(--app-surface-bg)",
            boxShadow: "var(--app-surface-shadow)",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", gap: "12px", flexWrap: "wrap" }}>
            <div style={{ flex: 1, minWidth: "240px" }}>
              <div
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "8px",
                  border: "1px solid var(--app-chip-border)",
                  background: "var(--app-chip-bg)",
                  color: "var(--app-chip-fg)",
                  borderRadius: "999px",
                  padding: "5px 10px",
                  fontSize: "12px",
                  fontWeight: 600,
                  marginBottom: "10px",
                }}
              >
                <span>{actionMeta.label}</span>
              </div>
              <div style={{ fontWeight: 500, color: "var(--app-text-strong)", marginBottom: "8px", fontSize: compact ? "16px" : "18px", lineHeight: 1.35 }}>
                {stripHedgePrefix(item.title) || item.id}
              </div>
              <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", fontSize: "12px", color: "var(--app-text-muted)" }}>
                <span style={metadataPillStyle}>Status: {item.status || "new"}</span>
                <span style={metadataPillStyle}>Confidence: {item.confidence_score ?? "-"}</span>
              </div>
              <div style={{ fontSize: "13px", color: "var(--app-text-muted)", marginTop: "8px", lineHeight: 1.5 }}>{actionMeta.help}</div>
              {item.source_context ? (
                <div style={{ fontSize: "12px", color: "var(--app-text-subtle)", marginTop: "4px" }}>
                  Source: {item.source_context}
                </div>
              ) : null}
            </div>
            <div style={{ fontSize: "12px", color: "var(--app-text-muted)", whiteSpace: "nowrap" }}>
              Review: {formatReviewDate(item.review_at)}
            </div>
          </div>

          {item.thesis ? (
            <div style={{ marginTop: "12px", fontSize: "14px", color: "var(--app-text-muted)", lineHeight: 1.7 }}>
              {stripHedgePrefix(item.thesis)}
            </div>
          ) : null}

          {item.recommended_action ? (
            <div style={noteBlockStyle}>
              <div style={noteLabelStyle}>{actionMeta.nextLabel}</div>
              <div style={{ fontSize: "14px", color: "var(--app-text-muted)", lineHeight: 1.7 }}>{stripHedgePrefix(item.recommended_action)}</div>
            </div>
          ) : null}

          {!compact && item.counter_argument ? (
            <div style={{ marginTop: "10px", fontSize: "13px", color: "var(--app-text-muted)", lineHeight: 1.6 }}>
              <strong>Counter:</strong> {item.counter_argument}
            </div>
          ) : null}

          <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", marginTop: "14px" }}>
            <Link
              href={`/workspace/decisions/detail?id=${encodeURIComponent(item.id)}`}
              style={{
                ...primaryButtonStyle,
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                textDecoration: "none",
              }}
            >
              Open Detail
            </Link>
            <button style={buttonStyle} onClick={() => void handleAction(item.id, "saved")} disabled={pendingId === item.id}>
              Save
            </button>
            <button style={buttonStyle} onClick={() => void handleAction(item.id, "ignored")} disabled={pendingId === item.id}>
              Ignore
            </button>
            <button style={buttonStyle} onClick={() => void handleAction(item.id, "acted")} disabled={pendingId === item.id}>
              Mark as Acted
            </button>
            <button style={buttonStyle} onClick={() => void handleAction(item.id, "deferred")} disabled={pendingId === item.id}>
              Review Later
            </button>
          </div>
        </div>
        );
      })}
    </div>
  );
}
