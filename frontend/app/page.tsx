"use client";

import Link from "next/link";
import {
  ArrowRight,
  BarChart3,
  BookOpenCheck,
  BrainCircuit,
  FileSearch,
  Gauge,
  GitBranch,
  Layers3,
  Radar,
  Route,
  ShieldCheck,
} from "lucide-react";

import AppContainer from "@/components/AppContainer";

const pipelineStages = [
  {
    label: "Signal",
    href: "/signals",
    detail: "External AI ecosystem events, uploads, repo activity, product launches, and friction reports.",
  },
  {
    label: "Insight",
    href: "/signals/detail",
    detail: "Structured interpretation: why it matters, project fit, career relevance, and synthesis.",
  },
  {
    label: "Trend",
    href: "/radar",
    detail: "Topic momentum, rising themes, and repeated patterns across signals over time.",
  },
  {
    label: "Strategic Intelligence",
    href: "/knowledge",
    detail: "Evidence-aware synthesis that connects market movement to active project judgment.",
  },
  {
    label: "Decision",
    href: "/workspace/projects/review",
    detail: "Project Takeaways convert intelligence into confirm, watch, action, reject, or dismiss choices.",
  },
  {
    label: "Review",
    href: "/workspace/projects/review/record",
    detail: "Human judgment records whether the system's interpretation was useful, weak, or wrong.",
  },
  {
    label: "Learning",
    href: "/workspace/projects/trajectory",
    detail: "ReviewRecords and CalibrationEvents become trajectory memory and project learning context.",
  },
];

const valueCards = [
  {
    title: "Track AI ecosystem signals",
    description: "Collect RSS, official sources, GitHub, Hacker News, Product Hunt, and manual material into one signal stream.",
    href: "/signals",
    icon: Radar,
    accent: "#2563eb",
  },
  {
    title: "Separate relevance from evidence",
    description: "A signal can be strategically relevant while still too weak to support automatic action.",
    href: "/knowledge",
    icon: ShieldCheck,
    accent: "#059669",
  },
  {
    title: "Turn intelligence into judgment",
    description: "Project Takeaways make strategy reviewable, watchable, actionable, and learnable over time.",
    href: "/workspace/projects/review",
    icon: BookOpenCheck,
    accent: "#b45309",
  },
];

const controlItems = [
  {
    title: "Model routing",
    description: "Different tasks receive different execution policies instead of routing everything through one model path.",
    icon: Route,
  },
  {
    title: "Claim verification",
    description: "Generated claims stay separate from source evidence and carry support labels before downstream use.",
    icon: FileSearch,
  },
  {
    title: "Blocked downstream actions",
    description: "Weak evidence can enter Watch or Review, but it cannot quietly become low-risk Action.",
    icon: ShieldCheck,
  },
  {
    title: "Runtime metrics",
    description: "Pipeline runs, collector runs, LLM calls, artifacts, and verification events are observable.",
    icon: Gauge,
  },
];

const heroFlowItems = [
  {
    title: "Signal intake",
    description: "Messy external and manual inputs enter one normalized review stream.",
    icon: Radar,
  },
  {
    title: "Evidence gate",
    description: "Relevance is separated from evidence before downstream actions are allowed.",
    icon: ShieldCheck,
  },
  {
    title: "Project judgment",
    description: "Project Takeaways move into Confirm, Watch, Action, Reject, or Dismiss.",
    icon: BookOpenCheck,
  },
  {
    title: "Learning loop",
    description: "ReviewRecords and CalibrationEvents become durable trajectory context.",
    icon: GitBranch,
  },
];

const surfaceLinks = [
  {
    title: "Dashboard",
    description: "Daily operating cockpit for intake, review, and metrics.",
    href: "/dashboard",
    icon: BarChart3,
  },
  {
    title: "Signals",
    description: "Inspect signal detail, evidence grounding, and generated insight.",
    href: "/signals",
    icon: Radar,
  },
  {
    title: "Radar",
    description: "Read daily topic momentum and strategic priority output.",
    href: "/radar",
    icon: Layers3,
  },
  {
    title: "Knowledge",
    description: "Review convergence across supply-side and demand-side signals.",
    href: "/knowledge",
    icon: BrainCircuit,
  },
  {
    title: "Project Review",
    description: "Confirm, Watch, Action, Reject, or calibrate Project Takeaways.",
    href: "/workspace/projects/review",
    icon: BookOpenCheck,
  },
  {
    title: "Trajectory",
    description: "Trace how review and calibration history becomes learning.",
    href: "/workspace/projects/trajectory",
    icon: GitBranch,
  },
];

export default function LandingPage() {
  return (
    <AppContainer style={pageShellStyle}>
      <section style={heroSectionStyle}>
        <div style={heroCopyStyle}>
          <div style={eyebrowStyle}>AI Radar</div>
          <h1 style={heroTitleStyle}>Evidence-aware intelligence for AI ecosystem decisions.</h1>
          <p style={heroDescriptionStyle}>
            AI Radar turns messy AI ecosystem signals into structured insight, trend awareness, project judgment, and learning without letting weak evidence become automatic action.
          </p>
          <div style={heroActionRowStyle}>
            <Link href="/dashboard" style={primaryButtonStyle}>
              <BarChart3 size={17} aria-hidden="true" />
              Open dashboard
            </Link>
            <Link href="/signals" style={secondaryButtonStyle}>
              <Radar size={17} aria-hidden="true" />
              Review signals
            </Link>
          </div>
        </div>

        <div style={heroVisualStyle} aria-label="AI Radar intelligence flow summary">
          <div style={visualHeaderStyle}>
            <div>
              <div style={visualEyebrowStyle}>Operating Model</div>
              <h2 style={visualTitleStyle}>Quality-controlled intelligence loop</h2>
            </div>
            <span style={visualStatusPillStyle}>Weak evidence stays gated</span>
          </div>

          <div style={visualFlowStyle}>
            {heroFlowItems.map((item, index) => {
              const Icon = item.icon;
              return (
                <div key={item.title} style={visualStepStyle}>
                  <div style={visualStepIconStyle}>
                    <Icon size={18} aria-hidden="true" />
                  </div>
                  <div style={{ minWidth: 0 }}>
                    <div style={visualStepTitleStyle}>{item.title}</div>
                    <div style={visualStepDescriptionStyle}>{item.description}</div>
                  </div>
                  {index < heroFlowItems.length - 1 ? (
                    <ArrowRight size={16} aria-hidden="true" style={visualStepArrowStyle} />
                  ) : null}
                </div>
              );
            })}
          </div>

          <div style={visualControlBarStyle}>
            <span>Model routing</span>
            <span>Claim verification</span>
            <span>Blocked actions</span>
            <span>Metrics</span>
          </div>
        </div>
      </section>

      <section style={pipelineSectionStyle}>
        <div style={sectionIntroStyle}>
          <div style={eyebrowStyle}>Pipeline</div>
          <h2 style={sectionTitleStyle}>Signal to learning, with gates between the steps.</h2>
        </div>
        <div style={pipelineGridStyle}>
          {pipelineStages.map((stage, index) => (
            <Link key={stage.label} href={stage.href} style={pipelineCardStyle}>
              <span style={stageNumberStyle}>{String(index + 1).padStart(2, "0")}</span>
              <h3 style={cardTitleStyle}>{stage.label}</h3>
              <p style={cardDescriptionStyle}>{stage.detail}</p>
            </Link>
          ))}
        </div>
      </section>

      <section style={valueGridStyle}>
        {valueCards.map((card) => {
          const Icon = card.icon;
          return (
            <Link key={card.title} href={card.href} style={valueCardStyle}>
              <span style={{ ...iconBadgeStyle, color: card.accent, background: `${card.accent}14`, borderColor: `${card.accent}33` }}>
                <Icon size={20} aria-hidden="true" />
              </span>
              <h2 style={valueTitleStyle}>{card.title}</h2>
              <p style={valueDescriptionStyle}>{card.description}</p>
              <span style={inlineLinkStyle}>
                Open surface
                <ArrowRight size={15} aria-hidden="true" />
              </span>
            </Link>
          );
        })}
      </section>

      <section style={controlSectionStyle}>
        <div style={sectionIntroStyle}>
          <div style={eyebrowStyle}>Quality Layer</div>
          <h2 style={sectionTitleStyle}>The distinctive work happens below the visible workflow.</h2>
          <p style={sectionDescriptionStyle}>
            AI Radar is built to keep interpretation useful without treating every generated sentence as evidence.
          </p>
        </div>
        <div style={controlGridStyle}>
          {controlItems.map((item) => {
            const Icon = item.icon;
            return (
              <article key={item.title} style={controlItemStyle}>
                <Icon size={19} aria-hidden="true" />
                <div>
                  <h3 style={compactTitleStyle}>{item.title}</h3>
                  <p style={compactDescriptionStyle}>{item.description}</p>
                </div>
              </article>
            );
          })}
        </div>
      </section>

      <section style={surfacesSectionStyle}>
        <div style={sectionIntroStyle}>
          <div style={eyebrowStyle}>Work Surfaces</div>
          <h2 style={sectionTitleStyle}>Open the product from the stage you need.</h2>
        </div>
        <div style={surfaceGridStyle}>
          {surfaceLinks.map((surface) => {
            const Icon = surface.icon;
            return (
              <Link key={surface.title} href={surface.href} style={surfaceLinkStyle}>
                <span style={surfaceIconStyle}>
                  <Icon size={18} aria-hidden="true" />
                </span>
                <span style={{ minWidth: 0 }}>
                  <span style={surfaceTitleStyle}>{surface.title}</span>
                  <span style={surfaceDescriptionStyle}>{surface.description}</span>
                </span>
                <ArrowRight size={16} aria-hidden="true" />
              </Link>
            );
          })}
        </div>
      </section>
    </AppContainer>
  );
}

const pageShellStyle = {
  paddingTop: "28px",
  color: "var(--app-page-fg)",
} as const;

const heroSectionStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 420px), 1fr))",
  gap: "28px",
  alignItems: "center",
  minHeight: "calc(100vh - 132px)",
  paddingBottom: "26px",
} as const;

const heroCopyStyle = {
  minWidth: 0,
} as const;

const eyebrowStyle = {
  color: "var(--app-text-subtle)",
  fontSize: "12px",
  fontWeight: 760,
  textTransform: "uppercase" as const,
  letterSpacing: "0",
} as const;

const heroTitleStyle = {
  margin: "12px 0 0",
  color: "var(--app-text-strong)",
  fontSize: "44px",
  fontWeight: 780,
  lineHeight: 1.02,
  maxWidth: "880px",
} as const;

const heroDescriptionStyle = {
  margin: "20px 0 0",
  color: "var(--app-text-muted)",
  fontSize: "18px",
  lineHeight: 1.65,
  maxWidth: "760px",
} as const;

const heroActionRowStyle = {
  display: "flex",
  gap: "10px",
  flexWrap: "wrap" as const,
  marginTop: "26px",
} as const;

const primaryButtonStyle = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  gap: "8px",
  border: "1px solid var(--app-primary-action-border)",
  borderRadius: "8px",
  background: "var(--app-primary-action-bg)",
  color: "var(--app-primary-action-fg)",
  padding: "11px 14px",
  textDecoration: "none",
  fontSize: "14px",
  fontWeight: 720,
  whiteSpace: "nowrap" as const,
} as const;

const secondaryButtonStyle = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  gap: "8px",
  border: "1px solid var(--app-secondary-action-border)",
  borderRadius: "8px",
  background: "var(--app-secondary-action-bg)",
  color: "var(--app-secondary-action-fg)",
  padding: "11px 14px",
  textDecoration: "none",
  fontSize: "14px",
  fontWeight: 700,
  whiteSpace: "nowrap" as const,
} as const;

const heroVisualStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-bg)",
  minHeight: "430px",
  padding: "20px",
  display: "grid",
  alignContent: "space-between",
  gap: "18px",
  boxShadow: "var(--app-surface-shadow)",
} as const;

const visualHeaderStyle = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "flex-start",
  gap: "14px",
  flexWrap: "wrap" as const,
} as const;

const visualEyebrowStyle = {
  color: "var(--app-text-subtle)",
  fontSize: "12px",
  fontWeight: 780,
  textTransform: "uppercase" as const,
  letterSpacing: "0",
} as const;

const visualTitleStyle = {
  margin: "8px 0 0",
  color: "var(--app-text-strong)",
  fontSize: "24px",
  lineHeight: 1.18,
  fontWeight: 780,
} as const;

const visualStatusPillStyle = {
  border: "1px solid var(--app-info-border)",
  borderRadius: "999px",
  background: "var(--app-info-bg)",
  color: "var(--app-info-fg)",
  padding: "8px 10px",
  fontSize: "12px",
  fontWeight: 760,
  whiteSpace: "nowrap" as const,
} as const;

const visualFlowStyle = {
  display: "grid",
  gap: "10px",
} as const;

const visualStepStyle = {
  display: "grid",
  gridTemplateColumns: "38px minmax(0, 1fr) 18px",
  alignItems: "center",
  gap: "12px",
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  padding: "13px",
} as const;

const visualStepIconStyle = {
  width: "36px",
  height: "36px",
  border: "1px solid var(--app-chip-border)",
  borderRadius: "8px",
  background: "var(--app-chip-bg)",
  color: "var(--app-chip-fg)",
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
} as const;

const visualStepTitleStyle = {
  color: "var(--app-text-strong)",
  fontSize: "15px",
  fontWeight: 780,
  lineHeight: 1.25,
} as const;

const visualStepDescriptionStyle = {
  marginTop: "4px",
  color: "var(--app-text-muted)",
  fontSize: "13px",
  lineHeight: 1.5,
} as const;

const visualStepArrowStyle = {
  color: "var(--app-text-subtle)",
} as const;

const visualControlBarStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))",
  gap: "8px",
  borderTop: "1px solid var(--app-surface-border)",
  paddingTop: "14px",
  color: "var(--app-text-muted)",
  fontSize: "12px",
  fontWeight: 760,
} as const;

const pipelineSectionStyle = {
  borderTop: "1px solid var(--app-surface-border)",
  paddingTop: "28px",
} as const;

const sectionIntroStyle = {
  maxWidth: "780px",
  marginBottom: "16px",
} as const;

const sectionTitleStyle = {
  margin: "7px 0 0",
  color: "var(--app-text-strong)",
  fontSize: "28px",
  fontWeight: 760,
  lineHeight: 1.15,
} as const;

const sectionDescriptionStyle = {
  margin: "10px 0 0",
  color: "var(--app-text-muted)",
  fontSize: "15px",
  lineHeight: 1.6,
} as const;

const pipelineGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 210px), 1fr))",
  gap: "10px",
} as const;

const pipelineCardStyle = {
  display: "flex",
  flexDirection: "column" as const,
  minHeight: "196px",
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-bg)",
  color: "inherit",
  padding: "15px",
  textDecoration: "none",
  boxSizing: "border-box" as const,
} as const;

const stageNumberStyle = {
  color: "var(--app-text-subtle)",
  fontSize: "12px",
  fontWeight: 780,
} as const;

const cardTitleStyle = {
  margin: "12px 0 0",
  color: "var(--app-text-strong)",
  fontSize: "18px",
  fontWeight: 740,
  lineHeight: 1.25,
} as const;

const cardDescriptionStyle = {
  margin: "9px 0 0",
  color: "var(--app-text-muted)",
  fontSize: "13px",
  lineHeight: 1.55,
} as const;

const valueGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 260px), 1fr))",
  gap: "12px",
  marginTop: "26px",
} as const;

const valueCardStyle = {
  display: "flex",
  flexDirection: "column" as const,
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-bg)",
  color: "inherit",
  padding: "18px",
  textDecoration: "none",
  minHeight: "220px",
} as const;

const iconBadgeStyle = {
  width: "38px",
  height: "38px",
  border: "1px solid var(--app-chip-border)",
  borderRadius: "8px",
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
} as const;

const valueTitleStyle = {
  margin: "18px 0 0",
  color: "var(--app-text-strong)",
  fontSize: "21px",
  fontWeight: 760,
  lineHeight: 1.22,
} as const;

const valueDescriptionStyle = {
  margin: "9px 0 0",
  color: "var(--app-text-muted)",
  fontSize: "14px",
  lineHeight: 1.58,
} as const;

const inlineLinkStyle = {
  display: "inline-flex",
  alignItems: "center",
  gap: "6px",
  marginTop: "auto",
  paddingTop: "18px",
  color: "var(--app-text-strong)",
  fontSize: "13px",
  fontWeight: 760,
} as const;

const controlSectionStyle = {
  marginTop: "28px",
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  padding: "22px",
} as const;

const controlGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 240px), 1fr))",
  gap: "12px",
} as const;

const controlItemStyle = {
  display: "grid",
  gridTemplateColumns: "24px minmax(0, 1fr)",
  gap: "10px",
  alignItems: "start",
  color: "var(--app-text-muted)",
  background: "var(--app-surface-bg)",
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  padding: "14px",
} as const;

const compactTitleStyle = {
  margin: 0,
  color: "var(--app-text-strong)",
  fontSize: "15px",
  fontWeight: 760,
  lineHeight: 1.25,
} as const;

const compactDescriptionStyle = {
  margin: "5px 0 0",
  color: "var(--app-text-muted)",
  fontSize: "13px",
  lineHeight: 1.5,
} as const;

const surfacesSectionStyle = {
  marginTop: "28px",
} as const;

const surfaceGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 260px), 1fr))",
  gap: "10px",
} as const;

const surfaceLinkStyle = {
  display: "grid",
  gridTemplateColumns: "38px minmax(0, 1fr) 18px",
  alignItems: "center",
  gap: "10px",
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-bg)",
  color: "var(--app-text-muted)",
  padding: "13px",
  textDecoration: "none",
} as const;

const surfaceIconStyle = {
  width: "36px",
  height: "36px",
  border: "1px solid var(--app-chip-border)",
  borderRadius: "8px",
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  color: "var(--app-chip-fg)",
  background: "var(--app-chip-bg)",
} as const;

const surfaceTitleStyle = {
  display: "block",
  color: "var(--app-text-strong)",
  fontSize: "15px",
  fontWeight: 760,
  lineHeight: 1.3,
} as const;

const surfaceDescriptionStyle = {
  display: "block",
  marginTop: "4px",
  color: "var(--app-text-muted)",
  fontSize: "13px",
  lineHeight: 1.45,
} as const;
