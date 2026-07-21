"use client";

import Link from "next/link";
import type { CSSProperties } from "react";
import type { LucideIcon } from "lucide-react";
import {
  ArrowRight,
  BriefcaseBusiness,
  ClipboardCheck,
  Database,
  FileCheck2,
  GitBranch,
  Lightbulb,
  ShieldCheck,
} from "lucide-react";
import AppContainer from "@/components/AppContainer";

type WorkspaceCard = {
  title: string;
  description: string;
  href: string;
  tag: string;
  icon: LucideIcon;
  emphasis: string;
};

const cards: WorkspaceCard[] = [
  {
    title: "Project Takeaways",
    description:
      "Browse signal takeaways organized by project, such as AI Radar, GLAP, and AI Cognitive.",
    href: "/workspace/projects",
    tag: "Project review",
    icon: Database,
    emphasis: "Project memory",
  },
  {
    title: "Review Inbox",
    description:
      "Confirm, watch, action, or reject Project Takeaway candidates before they become project memory.",
    href: "/workspace/projects/review",
    tag: "Human review",
    icon: ClipboardCheck,
    emphasis: "Decision queue",
  },
  {
    title: "Trajectory Timeline",
    description:
      "Review judgment events created from Review Records and calibration outcomes.",
    href: "/workspace/projects/trajectory",
    tag: "Judgment history",
    icon: GitBranch,
    emphasis: "Learning trail",
  },
  {
    title: "Career Takeaways",
    description:
      "Review signals that contribute to your career direction, positioning, and skill development.",
    href: "/workspace/career",
    tag: "Career",
    icon: BriefcaseBusiness,
    emphasis: "Career memory",
  },
  {
    title: "Signal Completion Notes",
    description:
      "Look through final notes saved when signal analysis sessions are completed into Workspace.",
    href: "/workspace/reflection",
    tag: "Completion",
    icon: FileCheck2,
    emphasis: "Completion record",
  },
  {
    title: "Strategic Insight",
    description:
      "Review synthesized strategic insights extracted from signals and analysis sessions.",
    href: "/workspace/insights",
    tag: "Synthesis",
    icon: Lightbulb,
    emphasis: "Strategic output",
  },
];

export default function WorkspacePage() {
  return (
    <AppContainer style={workspaceShellStyle}>
      <section style={workspaceHeroStyle}>
        <div style={workspaceHeroCopyStyle}>
          <div style={workspaceEyebrowStyle}>
            <ShieldCheck size={16} strokeWidth={2.3} />
            Durable Intelligence
          </div>
          <h1 style={workspaceTitleStyle}>Workspace</h1>
          <p style={workspaceDescriptionStyle}>
            The place where reviewed signals become durable project memory, career context, completion records, and judgment history.
          </p>
          <div style={workspaceActionRowStyle}>
            <Link href="/workspace/projects/review" style={primaryActionStyle}>
              <ClipboardCheck size={16} strokeWidth={2.3} />
              Review Inbox
            </Link>
            <Link href="/workspace/projects" style={secondaryActionStyle}>
              <Database size={16} strokeWidth={2.3} />
              Project Takeaways
            </Link>
          </div>
        </div>

        <div style={workspaceRouteMapStyle}>
          <div style={routeMapHeaderStyle}>Workspace flow</div>
          <div style={routeMapStepStyle}>
            <span>1</span>
            <strong>Review candidates</strong>
          </div>
          <div style={routeMapStepStyle}>
            <span>2</span>
            <strong>Preserve durable records</strong>
          </div>
          <div style={routeMapStepStyle}>
            <span>3</span>
            <strong>Learn from calibration</strong>
          </div>
        </div>
      </section>

      <section style={workspacePanelStyle}>
        <div style={workspacePanelHeaderStyle}>
          <div>
            <div style={workspacePanelEyebrowStyle}>Workspace surfaces</div>
            <h2 style={workspacePanelTitleStyle}>Choose the review surface</h2>
          </div>
          <span style={workspaceCountChipStyle}>{cards.length} surfaces</span>
        </div>

        <div style={workspaceGridStyle}>
          {cards.map((card) => {
            const Icon = card.icon;
            return (
              <Link key={card.title} href={card.href} style={cardLinkStyle}>
                <article style={workspaceCardStyle}>
                  <div style={cardTopRowStyle}>
                    <span style={iconShellStyle}>
                      <Icon size={18} strokeWidth={2.3} />
                    </span>
                    <span style={chipStyle}>{card.tag}</span>
                  </div>
                  <h2 style={cardTitleStyle}>{card.title}</h2>
                  <p style={cardDescriptionStyle}>{card.description}</p>
                  <div style={cardFooterStyle}>
                    <span>{card.emphasis}</span>
                    <span style={cardActionStyle}>
                      Open
                      <ArrowRight size={14} strokeWidth={2.4} />
                    </span>
                  </div>
                </article>
              </Link>
            );
          })}
        </div>
      </section>
    </AppContainer>
  );
}

const workspaceShellStyle: CSSProperties = {
  maxWidth: "1360px",
  paddingTop: "28px",
};

const workspaceHeroStyle: CSSProperties = {
  border: "1px solid var(--app-surface-strong-border)",
  borderRadius: "8px",
  background: "var(--app-surface-bg)",
  padding: "clamp(22px, 3vw, 34px)",
  marginBottom: "22px",
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 360px), 1fr))",
  gap: "22px",
  alignItems: "stretch",
};

const workspaceHeroCopyStyle: CSSProperties = {
  minWidth: 0,
  display: "flex",
  flexDirection: "column",
  justifyContent: "center",
};

const workspaceEyebrowStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: "8px",
  width: "fit-content",
  color: "var(--app-text-subtle)",
  fontSize: "12px",
  fontWeight: 850,
  letterSpacing: 0,
  textTransform: "uppercase",
};

const workspaceTitleStyle: CSSProperties = {
  margin: "12px 0 0",
  color: "var(--app-text-strong)",
  fontSize: "clamp(34px, 5vw, 58px)",
  lineHeight: 0.98,
  fontWeight: 850,
  letterSpacing: 0,
};

const workspaceDescriptionStyle: CSSProperties = {
  margin: "16px 0 0",
  color: "var(--app-text-muted)",
  fontSize: "16px",
  lineHeight: 1.7,
  maxWidth: "760px",
};

const workspaceActionRowStyle: CSSProperties = {
  marginTop: "22px",
  display: "flex",
  gap: "10px",
  flexWrap: "wrap",
};

const primaryActionStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: "8px",
  border: "1px solid var(--app-primary-action-border)",
  borderRadius: "8px",
  background: "var(--app-primary-action-bg)",
  color: "var(--app-primary-action-fg)",
  padding: "10px 13px",
  textDecoration: "none",
  fontSize: "14px",
  fontWeight: 800,
};

const secondaryActionStyle: CSSProperties = {
  ...primaryActionStyle,
  border: "1px solid var(--app-secondary-action-border)",
  background: "var(--app-secondary-action-bg)",
  color: "var(--app-secondary-action-fg)",
};

const workspaceRouteMapStyle: CSSProperties = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-soft-bg)",
  padding: "14px",
  display: "grid",
  gap: "10px",
  alignContent: "center",
  boxShadow: "var(--app-surface-shadow)",
};

const routeMapHeaderStyle: CSSProperties = {
  color: "var(--app-text-subtle)",
  fontSize: "12px",
  fontWeight: 850,
  letterSpacing: 0,
  textTransform: "uppercase",
};

const routeMapStepStyle: CSSProperties = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-bg)",
  padding: "10px 12px",
  display: "flex",
  alignItems: "center",
  gap: "10px",
  color: "var(--app-text-strong)",
};

const workspacePanelStyle: CSSProperties = {
  border: "1px solid var(--app-surface-strong-border)",
  borderRadius: "8px",
  padding: "20px",
  background: "var(--app-surface-bg)",
  boxShadow: "var(--app-surface-shadow)",
};

const workspacePanelHeaderStyle: CSSProperties = {
  display: "flex",
  alignItems: "flex-start",
  justifyContent: "space-between",
  gap: "14px",
  flexWrap: "wrap",
  marginBottom: "16px",
};

const workspacePanelEyebrowStyle: CSSProperties = {
  color: "var(--app-text-subtle)",
  fontSize: "12px",
  fontWeight: 850,
  letterSpacing: 0,
  textTransform: "uppercase",
};

const workspacePanelTitleStyle: CSSProperties = {
  margin: "5px 0 0",
  color: "var(--app-text-strong)",
  fontSize: "22px",
  lineHeight: 1.15,
  fontWeight: 850,
  letterSpacing: 0,
};

const workspaceCountChipStyle: CSSProperties = {
  border: "1px solid var(--app-chip-border)",
  borderRadius: "999px",
  background: "var(--app-chip-bg)",
  color: "var(--app-chip-fg)",
  padding: "7px 10px",
  fontSize: "12px",
  fontWeight: 800,
};

const workspaceGridStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 260px), 1fr))",
  gap: "14px",
};

const secondaryButtonStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: "7px",
  border: "1px solid var(--app-secondary-action-border)",
  borderRadius: "8px",
  background: "var(--app-secondary-action-bg)",
  color: "var(--app-secondary-action-fg)",
  padding: "7px 12px",
  textDecoration: "none",
  fontSize: "13px",
  fontWeight: 700,
};

const cardLinkStyle: CSSProperties = {
  display: "flex",
  textDecoration: "none",
  color: "inherit",
};

const workspaceCardStyle: CSSProperties = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  padding: "18px",
  background: "var(--app-surface-muted-bg)",
  minHeight: "218px",
  width: "100%",
  boxSizing: "border-box",
  display: "flex",
  flexDirection: "column",
  cursor: "pointer",
};

const cardTopRowStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  gap: "10px",
};

const iconShellStyle: CSSProperties = {
  width: "34px",
  height: "34px",
  borderRadius: "8px",
  border: "1px solid var(--app-surface-border)",
  background: "var(--app-surface-bg)",
  color: "var(--app-text-muted)",
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  flexShrink: 0,
};

const cardTitleStyle: CSSProperties = {
  marginTop: "12px",
  marginBottom: "10px",
  fontSize: "19px",
  fontWeight: 850,
  color: "var(--app-text-strong)",
  lineHeight: 1.35,
  letterSpacing: 0,
};

const cardDescriptionStyle: CSSProperties = {
  margin: "0 0 16px",
  color: "var(--app-text-muted)",
  fontSize: "14px",
  lineHeight: "1.7",
};

const cardFooterStyle: CSSProperties = {
  marginTop: "auto",
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  gap: "10px",
  flexWrap: "wrap",
  color: "var(--app-text-subtle)",
  fontSize: "12px",
  fontWeight: 800,
};

const cardActionStyle: CSSProperties = {
  ...secondaryButtonStyle,
  width: "fit-content",
};

const chipStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  border: "1px solid var(--app-chip-border)",
  borderRadius: "999px",
  background: "var(--app-chip-bg)",
  color: "var(--app-chip-fg)",
  padding: "5px 10px",
  fontSize: "12px",
  fontWeight: 700,
  whiteSpace: "nowrap",
};
