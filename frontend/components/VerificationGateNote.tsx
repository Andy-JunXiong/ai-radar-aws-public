"use client";

import type { CSSProperties } from "react";

import {
  getVerificationGateNote,
  getVerificationGateTone,
  type VerificationGateMetadata,
  type VerificationGateTone,
} from "@/lib/verificationGateNote";

type VerificationGateNoteProps = {
  verification: VerificationGateMetadata;
  accentColor?: string;
  background?: string;
  style?: CSSProperties;
};

export default function VerificationGateNote({
  verification,
  accentColor,
  background,
  style,
}: VerificationGateNoteProps) {
  const note = getVerificationGateNote(verification);
  if (!note) return null;

  const tone = getVerificationGateTone(verification);
  const toneStyle = gateToneStyles[tone];
  const decisionHint = gateDecisionHints[tone];

  return (
    <div
      style={{
        border: `1px solid ${toneStyle.borderColor}`,
        borderLeft: `4px solid ${accentColor || toneStyle.accentColor}`,
        borderRadius: "8px",
        background: background || toneStyle.background,
        color: toneStyle.color,
        padding: "9px 11px",
        fontSize: "13px",
        lineHeight: 1.55,
        ...style,
      }}
    >
      <strong>Action gate:</strong> {note}
      <div style={decisionHintStyle}>{decisionHint}</div>
    </div>
  );
}

const gateToneStyles: Record<
  VerificationGateTone,
  { accentColor: string; borderColor: string; background: string; color: string }
> = {
  blocked: {
    accentColor: "var(--app-danger-border)",
    borderColor: "var(--app-danger-border)",
    background: "var(--app-danger-bg)",
    color: "var(--app-danger-fg)",
  },
  watch: {
    accentColor: "var(--app-warning-border)",
    borderColor: "var(--app-warning-border)",
    background: "var(--app-warning-bg)",
    color: "var(--app-warning-fg)",
  },
  review: {
    accentColor: "var(--app-info-border)",
    borderColor: "var(--app-info-border)",
    background: "var(--app-info-bg)",
    color: "var(--app-info-fg)",
  },
  ready: {
    accentColor: "var(--app-success-border)",
    borderColor: "var(--app-success-border)",
    background: "var(--app-success-bg)",
    color: "var(--app-success-fg)",
  },
  neutral: {
    accentColor: "var(--app-surface-strong-border)",
    borderColor: "var(--app-surface-border)",
    background: "var(--app-surface-muted-bg)",
    color: "var(--app-text-muted)",
  },
};

const gateDecisionHints: Record<VerificationGateTone, string> = {
  blocked: "Decision path: Reject, Watch, or explicit override review. Do not treat this as ordinary Action evidence.",
  watch: "Decision path: Watch until evidence improves, or reject if project fit is weak.",
  review: "Decision path: Review Inbox should decide Confirm / Watch / Reject before downstream action.",
  ready: "Decision path: Project fit still needs human confirmation before durable takeaway or action.",
  neutral: "Decision path: inspect evidence and project fit before choosing a review outcome.",
};

const decisionHintStyle: CSSProperties = {
  marginTop: "4px",
  color: "inherit",
  opacity: 0.88,
  fontSize: "12px",
  fontWeight: 700,
};
