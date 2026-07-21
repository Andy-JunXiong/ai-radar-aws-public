"use client";

import Link from "next/link";

import AppContainer from "@/components/AppContainer";

const primaryActions = [
  { label: "Manual Upload", href: "/manual" },
  { label: "Signals", href: "/signals" },
  { label: "Review Inbox", href: "/workspace/projects/review" },
  { label: "Trajectory", href: "/workspace/projects/trajectory" },
  { label: "Metrics", href: "/admin/metrics" },
];

const intelligenceLoop = [
  {
    step: "1",
    title: "Intake",
    description: "Collect manual sources and feed signals before they become durable project memory.",
    href: "/manual",
    state: "Manual + Auto",
  },
  {
    step: "2",
    title: "Signal Review",
    description: "Inspect generated insight, evidence status, and Workspace completion readiness.",
    href: "/signals",
    state: "Evidence gated",
  },
  {
    step: "3",
    title: "Project Review",
    description: "Confirm, Watch, Action, Reject, or calibrate Project Takeaway candidates.",
    href: "/workspace/projects/review",
    state: "Human review",
  },
  {
    step: "4",
    title: "Trajectory",
    description: "Read the judgment timeline produced by Review Records and Calibration Events.",
    href: "/workspace/projects/trajectory",
    state: "Learning loop",
  },
];

const focusCards = [
  {
    title: "Manual-Source Intelligence",
    label: "Current loop",
    description:
      "Manual uploads should keep source intent as they move through Signal Detail, Workspace, Review, Calibration, and Trajectory.",
    href: "/workspace/projects/review",
  },
  {
    title: "Evidence Gates",
    label: "Review discipline",
    description:
      "Unsupported, inferred, low-confidence, and blocked-action signals stay visible before any low-risk Action route.",
    href: "/workspace/projects/review",
  },
  {
    title: "Operating Metrics",
    label: "Production signal",
    description:
      "Daily, weekly, and monthly metrics should read backend-backed summaries instead of frontend-local assumptions.",
    href: "/admin/metrics",
  },
  {
    title: "Knowledge Fit",
    label: "Project match",
    description:
      "Knowledge convergence should stay tied to explicit project fit before it becomes reusable project intelligence.",
    href: "/knowledge",
  },
];

const surfaceCards = [
  {
    title: "Workspace",
    description: "Open the structured review surfaces for project memory, completion notes, and strategic insight.",
    href: "/workspace",
  },
  {
    title: "Project Takeaways",
    description: "Browse durable project intelligence organized by active project.",
    href: "/workspace/projects",
  },
  {
    title: "Radar",
    description: "Scan topic momentum and strategic signal clusters.",
    href: "/radar",
  },
  {
    title: "Admin",
    description: "Manage source settings, projects, subscriptions, metrics, and private beta controls.",
    href: "/admin",
  },
];

export default function OverviewPage() {
  return (
    <AppContainer style={{ paddingTop: "24px" }}>
      <section style={headerPanelStyle}>
        <div style={{ minWidth: 0 }}>
          <div style={eyebrowStyle}>AI Radar</div>
          <h1 style={pageTitleStyle}>Operating Home</h1>
          <p style={descriptionStyle}>
            Start from intake, review the evidence gate, and move finished intelligence into project memory.
          </p>
        </div>
        <div style={actionRowStyle}>
          {primaryActions.map((action, index) => (
            <Link key={action.href} href={action.href} style={index === 0 ? primaryButtonStyle : secondaryButtonStyle}>
              {action.label}
            </Link>
          ))}
        </div>
      </section>

      <section style={panelStyle}>
        <div style={sectionHeaderStyle}>
          <div>
            <div style={eyebrowStyle}>Primary Loop</div>
            <h2 style={sectionTitleStyle}>Signal to Strategic Intelligence</h2>
          </div>
          <Link href="/dashboard" style={secondaryButtonStyle}>
            Dashboard
          </Link>
        </div>
        <div style={loopGridStyle}>
          {intelligenceLoop.map((item) => (
            <Link key={item.title} href={item.href} style={cardLinkStyle}>
              <article style={loopCardStyle}>
                <div style={loopStepStyle}>{item.step}</div>
                <div>
                  <div style={cardMetaStyle}>{item.state}</div>
                  <h3 style={cardTitleStyle}>{item.title}</h3>
                  <p style={cardDescriptionStyle}>{item.description}</p>
                </div>
              </article>
            </Link>
          ))}
        </div>
      </section>

      <section style={twoColumnGridStyle}>
        <div style={panelStyle}>
          <div style={eyebrowStyle}>Review Focus</div>
          <h2 style={sectionTitleStyle}>What Needs Judgment</h2>
          <div style={focusGridStyle}>
            {focusCards.map((card) => (
              <Link key={card.title} href={card.href} style={cardLinkStyle}>
                <article style={recordCardStyle}>
                  <span style={chipStyle}>{card.label}</span>
                  <h3 style={cardTitleStyle}>{card.title}</h3>
                  <p style={cardDescriptionStyle}>{card.description}</p>
                </article>
              </Link>
            ))}
          </div>
        </div>

        <div style={panelStyle}>
          <div style={eyebrowStyle}>Work Surfaces</div>
          <h2 style={sectionTitleStyle}>Open a Surface</h2>
          <div style={surfaceGridStyle}>
            {surfaceCards.map((card) => (
              <Link key={card.title} href={card.href} style={surfaceLinkStyle}>
                <div>
                  <h3 style={surfaceTitleStyle}>{card.title}</h3>
                  <p style={surfaceDescriptionStyle}>{card.description}</p>
                </div>
                <span style={openLabelStyle}>Open</span>
              </Link>
            ))}
          </div>
        </div>
      </section>
    </AppContainer>
  );
}

const headerPanelStyle = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  gap: "18px",
  flexWrap: "wrap" as const,
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-bg)",
  padding: "18px",
  marginBottom: "16px",
  boxShadow: "var(--app-surface-shadow)",
} as const;

const eyebrowStyle = {
  color: "var(--app-text-subtle)",
  fontSize: "12px",
  fontWeight: 700,
  textTransform: "uppercase" as const,
  letterSpacing: "0.4px",
} as const;

const pageTitleStyle = {
  margin: "4px 0 0",
  color: "var(--app-text-strong)",
  fontSize: "28px",
  fontWeight: 700,
  lineHeight: 1.2,
} as const;

const descriptionStyle = {
  margin: "8px 0 0",
  color: "var(--app-text-muted)",
  fontSize: "14px",
  lineHeight: 1.6,
  maxWidth: "720px",
} as const;

const actionRowStyle = {
  display: "flex",
  gap: "8px",
  flexWrap: "wrap" as const,
  justifyContent: "flex-end",
} as const;

const primaryButtonStyle = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  border: "1px solid var(--app-primary-action-border)",
  borderRadius: "8px",
  background: "var(--app-primary-action-bg)",
  color: "var(--app-primary-action-fg)",
  padding: "9px 12px",
  textDecoration: "none",
  fontSize: "13px",
  fontWeight: 700,
  whiteSpace: "nowrap" as const,
} as const;

const secondaryButtonStyle = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  border: "1px solid var(--app-secondary-action-border)",
  borderRadius: "8px",
  background: "var(--app-secondary-action-bg)",
  color: "var(--app-secondary-action-fg)",
  padding: "9px 12px",
  textDecoration: "none",
  fontSize: "13px",
  fontWeight: 650,
  whiteSpace: "nowrap" as const,
} as const;

const panelStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-bg)",
  padding: "18px",
  boxShadow: "var(--app-surface-shadow)",
} as const;

const sectionHeaderStyle = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  gap: "12px",
  flexWrap: "wrap" as const,
  marginBottom: "14px",
} as const;

const sectionTitleStyle = {
  margin: "4px 0 0",
  color: "var(--app-text-strong)",
  fontSize: "18px",
  fontWeight: 650,
  lineHeight: 1.35,
} as const;

const loopGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(230px, 1fr))",
  gap: "12px",
} as const;

const cardLinkStyle = {
  display: "flex",
  color: "inherit",
  textDecoration: "none",
} as const;

const loopCardStyle = {
  display: "grid",
  gridTemplateColumns: "36px minmax(0, 1fr)",
  gap: "12px",
  width: "100%",
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  padding: "14px",
  boxSizing: "border-box" as const,
} as const;

const loopStepStyle = {
  width: "32px",
  height: "32px",
  borderRadius: "999px",
  border: "1px solid var(--app-chip-border)",
  background: "var(--app-chip-bg)",
  color: "var(--app-chip-fg)",
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  fontSize: "13px",
  fontWeight: 800,
} as const;

const cardMetaStyle = {
  color: "var(--app-text-subtle)",
  fontSize: "12px",
  fontWeight: 700,
  textTransform: "uppercase" as const,
  letterSpacing: "0.3px",
} as const;

const cardTitleStyle = {
  margin: "5px 0 0",
  color: "var(--app-text-strong)",
  fontSize: "16px",
  fontWeight: 650,
  lineHeight: 1.35,
} as const;

const cardDescriptionStyle = {
  margin: "7px 0 0",
  color: "var(--app-text-muted)",
  fontSize: "13px",
  lineHeight: 1.55,
} as const;

const twoColumnGridStyle = {
  display: "grid",
  gridTemplateColumns: "minmax(0, 1.15fr) minmax(320px, 0.85fr)",
  gap: "16px",
  marginTop: "16px",
} as const;

const focusGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
  gap: "10px",
  marginTop: "14px",
} as const;

const recordCardStyle = {
  width: "100%",
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  padding: "14px",
  boxSizing: "border-box" as const,
} as const;

const chipStyle = {
  display: "inline-flex",
  alignItems: "center",
  border: "1px solid var(--app-chip-border)",
  borderRadius: "999px",
  background: "var(--app-chip-bg)",
  color: "var(--app-chip-fg)",
  padding: "5px 9px",
  fontSize: "12px",
  fontWeight: 650,
} as const;

const surfaceGridStyle = {
  display: "grid",
  gap: "10px",
  marginTop: "14px",
} as const;

const surfaceLinkStyle = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  gap: "12px",
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  color: "inherit",
  padding: "12px",
  textDecoration: "none",
} as const;

const surfaceTitleStyle = {
  margin: 0,
  color: "var(--app-text-strong)",
  fontSize: "15px",
  fontWeight: 650,
  lineHeight: 1.35,
} as const;

const surfaceDescriptionStyle = {
  margin: "5px 0 0",
  color: "var(--app-text-muted)",
  fontSize: "13px",
  lineHeight: 1.5,
} as const;

const openLabelStyle = {
  ...secondaryButtonStyle,
  padding: "7px 10px",
  flexShrink: 0,
} as const;
