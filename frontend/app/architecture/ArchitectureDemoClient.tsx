"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import type { CSSProperties } from "react";
import { judgmentFlowStages } from "@/components/architecture/judgment-flow/stages";
import type { DaoFaShuItem, Layer, LayerId } from "@/lib/types";

type Props = {
  layers: Layer[];
  daoFaShu: DaoFaShuItem[];
};

export default function ArchitectureDemoClient({
  layers,
  daoFaShu,
}: Props) {
  const [expandedLayer, setExpandedLayer] = useState<LayerId>("signal");
  const [activeStageIndex, setActiveStageIndex] = useState(0);
  const [speed, setSpeed] = useState(1);
  const [playing, setPlaying] = useState(false);

  useEffect(() => {
    if (!playing) return;

    const timer = window.setInterval(() => {
      setActiveStageIndex((current) => {
        if (current >= judgmentFlowStages.length - 1) {
          setPlaying(false);
          return current;
        }
        return current + 1;
      });
    }, 2500 / speed);

    return () => window.clearInterval(timer);
  }, [playing, speed]);

  const activeLayer = layers.find((layer) => layer.id === expandedLayer) ?? layers[0];
  const activeStage = judgmentFlowStages[activeStageIndex] ?? judgmentFlowStages[0];

  return (
    <div style={pageStackStyle}>
      <section style={heroPanelStyle}>
        <div>
          <div style={eyebrowStyle}>System walkthrough</div>
          <h2 style={panelTitleStyle}>Five layers, one operating loop.</h2>
          <p style={descriptionStyle}>
            AI Radar turns raw ecosystem signals into reviewed knowledge,
            project decisions, and durable strategic intelligence.
          </p>
        </div>
        <div style={heroActionsStyle}>
          <a href="#signal-flow" style={primaryButtonStyle}>
            Run signal
          </a>
          <Link href="/architecture/signal-lifecycle-demo" style={secondaryButtonStyle}>
            Three-view demo
          </Link>
        </div>
      </section>

      <section style={sectionCardStyle}>
        <div style={sectionHeaderStyle}>
          <div>
            <div style={eyebrowStyle}>Architecture</div>
            <h2 style={sectionTitleStyle}>Layer responsibilities</h2>
          </div>
          <span style={statusPillStyle}>System model</span>
        </div>

        <div style={overviewAdrCardStyle}>
          <div>
            <div style={detailLabelStyle}>ADR-000</div>
            <strong style={overviewAdrTitleStyle}>The five-layer architecture</strong>
            <p style={overviewAdrDescriptionStyle}>
              Signal, Insight, Knowledge, and Project form the operational pipeline; Reflection is the cognitive context side-channel.
            </p>
          </div>
          <Link href="/architecture/adrs/architecture-overview" style={layerAdrButtonStyle}>
            Read Architecture ADR
          </Link>
        </div>

        <div style={layerGridStyle}>
          {layers.map((layer) => {
            const selected = layer.id === expandedLayer;

            return (
              <button
                key={layer.id}
                type="button"
                onClick={() => setExpandedLayer(layer.id)}
                style={{
                  ...layerButtonStyle,
                  borderColor: selected ? "var(--app-primary-action-border)" : "var(--app-surface-border)",
                  background: selected ? "var(--app-surface-soft-bg)" : "var(--app-surface-bg)",
                }}
              >
                <span style={layerNumStyle}>{layer.num}</span>
                <strong style={layerNameStyle}>{layer.name}</strong>
                <span style={layerTaglineStyle}>{layer.tagline}</span>
              </button>
            );
          })}
        </div>

        {activeLayer ? (
          <div style={layerDetailStyle}>
            <div>
              <div style={detailLabelStyle}>Why</div>
              <p style={detailLeadStyle}>{activeLayer.why}</p>
            </div>
            <div>
              <div style={detailLabelStyle}>How</div>
              <div style={detailTextStackStyle}>
                {activeLayer.how.map((item) => (
                  <p key={item} style={detailBodyStyle}>
                    {item}
                  </p>
                ))}
              </div>
            </div>
            <div>
              <div style={detailLabelStyle}>Stack</div>
              <div style={chipGridStyle}>
                {activeLayer.stack.map((item) => (
                  <span key={item} style={chipStyle}>
                    {item}
                  </span>
                ))}
              </div>
              <Link
                href={`/architecture/adrs/${activeLayer.adr_slug}`}
                style={layerAdrButtonStyle}
              >
                Read {activeLayer.name} ADR
              </Link>
            </div>
          </div>
        ) : null}
      </section>

      <section id="signal-flow" style={sectionCardStyle}>
        <div style={sectionHeaderStyle}>
          <div>
            <div style={eyebrowStyle}>Judgment flow</div>
            <h2 style={sectionTitleStyle}>From signal to reviewed project judgment</h2>
            <p style={sectionDescriptionStyle}>
              Follow one real signal as it moves through verification gates. The Reflection track runs in parallel, informing judgment without becoming evidence.
            </p>
          </div>
          <div style={flowControlsStyle}>
            <label style={speedControlStyle}>
              <span style={detailLabelStyle}>Speed</span>
              <select
                value={speed}
                onChange={(event) => setSpeed(Number(event.target.value))}
                style={speedSelectStyle}
              >
                <option value={0.5}>0.5x</option>
                <option value={1}>1x</option>
                <option value={2}>2x</option>
              </select>
            </label>
            <button
              type="button"
              onClick={() => setPlaying((current) => !current)}
              style={primaryButtonStyle}
            >
              {playing ? "Pause" : "Play"}
            </button>
            <button
              type="button"
              onClick={() => {
                setPlaying(false);
                setActiveStageIndex(0);
              }}
              style={secondaryButtonStyle}
            >
              Reset
            </button>
          </div>
        </div>

        <div style={flowTimelineShellStyle}>
          <div style={operationalTrackLabelStyle}>Operational Track</div>
          <div style={operationalTrackStyle}>
            <div style={trackLineStyle} />
            <div
              style={{
                ...trackProgressStyle,
                width: `${(activeStageIndex / (judgmentFlowStages.length - 1)) * 100}%`,
              }}
            />
            {judgmentFlowStages.map((stage, index) => {
              const active = index === activeStageIndex;
              const completed = index < activeStageIndex;

              return (
                <button
                  key={stage.id}
                  type="button"
                  onClick={() => {
                    setPlaying(false);
                    setActiveStageIndex(index);
                  }}
                  style={trackStageButtonStyle}
                >
                  <span
                    style={{
                      ...trackNodeStyle,
                      ...(active ? activeTrackNodeStyle : {}),
                      ...(completed ? completedTrackNodeStyle : {}),
                    }}
                  />
                  <span style={trackStageTextStyle}>
                    <strong style={active ? activeTrackLabelStyle : trackLabelStyle}>{stage.trackLabel}</strong>
                    <span style={trackSubLabelStyle}>{stage.subLabel}</span>
                  </span>
                  <span
                    title={stage.gateLabel}
                    style={{
                      ...gateMarkerStyle,
                      ...(stage.gateKind === "human" ? humanGateMarkerStyle : {}),
                      ...(active ? activeGateMarkerStyle : {}),
                    }}
                  />
                </button>
              );
            })}
          </div>
        </div>

        {activeStage ? (
          <div style={stageDetailShellStyle}>
            <div style={{ ...stagePanelStyle, ...stageCopyPanelStyle }}>
              <div style={detailLabelStyle}>Currently at</div>
              <h3 style={flowTitleStyle}>{activeStage.stageLabel}</h3>
              <div style={gateLineStyle}>
                <span style={activeStage.gateKind === "human" ? humanGateBadgeStyle : gateBadgeStyle}>
                  {activeStage.gateKind === "human" ? "Human gate" : "System gate"}
                </span>
                <span>{activeStage.gateLabel}</span>
              </div>
              <p style={descriptionStyle}>{activeStage.whatHappens}</p>
              {activeStage.reflectionEvent ? (
                <div style={reflectionInlineNoteStyle}>
                  <div style={reflectionInlineHeaderStyle}>
                    <span style={detailLabelStyle}>Reflection boundary</span>
                    <span style={reflectionContextPillStyle}>context only</span>
                  </div>
                  <p style={reflectionContextDescriptionStyle}>
                    {activeStage.reflectionEvent.contentSummary}. Stored in{" "}
                    <strong>{activeStage.reflectionEvent.location}</strong>;
                    informs judgment, but does not enter evidence.
                  </p>
                </div>
              ) : null}
            </div>
            <div style={{ ...stagePanelStyle, ...stageStatePanelStyle }}>
              <div style={detailLabelStyle}>State written</div>
              <pre style={snapshotStyle}>
                {JSON.stringify(activeStage.stateDiff, null, 2)}
              </pre>
            </div>
            <details style={designDecisionStyle}>
              <summary style={designDecisionSummaryStyle}>Design Decision</summary>
              <p style={designDecisionBodyStyle}>{activeStage.designDecision}</p>
            </details>
          </div>
        ) : null}
      </section>

      <section style={sectionCardStyle}>
        <div style={sectionHeaderStyle}>
          <div>
            <div style={eyebrowStyle}>Dao / Fa / Shu</div>
            <h2 style={sectionTitleStyle}>Principle to execution</h2>
          </div>
        </div>
        <div style={principleGridStyle}>
          {daoFaShu.map((item) => (
            <div key={item.ch} style={principleCardStyle}>
              <div style={principleGlyphStyle}>{item.ch}</div>
              <div style={detailLabelStyle}>
                {item.pinyin} / {item.en}
              </div>
              <p style={descriptionStyle}>{item.body}</p>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

const pageStackStyle: CSSProperties = {
  display: "grid",
  gap: "20px",
};

const heroPanelStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  gap: "18px",
  flexWrap: "wrap",
  border: "1px solid var(--app-surface-strong-border)",
  borderRadius: "8px",
  background: "var(--app-surface-bg)",
  padding: "22px",
  boxShadow: "var(--app-surface-shadow)",
};

const sectionCardStyle: CSSProperties = {
  border: "1px solid var(--app-surface-strong-border)",
  borderRadius: "8px",
  background: "var(--app-surface-bg)",
  padding: "22px",
  boxShadow: "var(--app-surface-shadow)",
};

const sectionHeaderStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  gap: "14px",
  alignItems: "center",
  flexWrap: "wrap",
  marginBottom: "18px",
};

const eyebrowStyle: CSSProperties = {
  color: "var(--app-text-subtle)",
  fontSize: "12px",
  fontWeight: 700,
  textTransform: "uppercase",
  letterSpacing: 0,
};

const panelTitleStyle: CSSProperties = {
  margin: "5px 0 0",
  color: "var(--app-text-strong)",
  fontSize: "22px",
  lineHeight: 1.25,
  fontWeight: 750,
  letterSpacing: 0,
};

const sectionTitleStyle: CSSProperties = {
  margin: "4px 0 0",
  color: "var(--app-text-strong)",
  fontSize: "20px",
  lineHeight: 1.3,
  fontWeight: 750,
};

const sectionDescriptionStyle: CSSProperties = {
  margin: "8px 0 0",
  color: "var(--app-text-muted)",
  fontSize: "14px",
  lineHeight: 1.6,
  maxWidth: "720px",
};

const descriptionStyle: CSSProperties = {
  margin: "8px 0 0",
  color: "var(--app-text-muted)",
  fontSize: "14px",
  lineHeight: 1.65,
  maxWidth: "820px",
};

const heroActionsStyle: CSSProperties = {
  display: "flex",
  alignItems: "flex-start",
  gap: "10px",
  flexWrap: "wrap",
};

const primaryButtonStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  border: "1px solid var(--app-primary-action-border)",
  borderRadius: "8px",
  background: "var(--app-primary-action-bg)",
  color: "var(--app-primary-action-fg)",
  padding: "8px 13px",
  textDecoration: "none",
  fontSize: "13px",
  fontWeight: 700,
  cursor: "pointer",
};

const secondaryButtonStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  border: "1px solid var(--app-secondary-action-border)",
  borderRadius: "8px",
  background: "var(--app-secondary-action-bg)",
  color: "var(--app-secondary-action-fg)",
  padding: "8px 13px",
  textDecoration: "none",
  fontSize: "13px",
  fontWeight: 700,
  cursor: "pointer",
};

const statusPillStyle: CSSProperties = {
  border: "1px solid var(--app-chip-border)",
  borderRadius: "999px",
  background: "var(--app-chip-bg)",
  color: "var(--app-chip-fg)",
  padding: "6px 10px",
  fontSize: "12px",
  fontWeight: 700,
};

const layerGridStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))",
  gap: "12px",
};

const overviewAdrCardStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  gap: "14px",
  flexWrap: "wrap",
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  padding: "16px",
  marginBottom: "14px",
};

const overviewAdrTitleStyle: CSSProperties = {
  display: "block",
  marginTop: "6px",
  color: "var(--app-text-strong)",
  fontSize: "16px",
  lineHeight: 1.35,
};

const overviewAdrDescriptionStyle: CSSProperties = {
  margin: "6px 0 0",
  color: "var(--app-text-muted)",
  fontSize: "13px",
  lineHeight: 1.55,
  maxWidth: "740px",
};

const layerButtonStyle: CSSProperties = {
  textAlign: "left",
  borderWidth: "1px",
  borderStyle: "solid",
  borderColor: "var(--app-surface-border)",
  borderRadius: "8px",
  padding: "16px",
  cursor: "pointer",
  transition: "border-color 0.15s ease, background 0.15s ease",
};

const layerNumStyle: CSSProperties = {
  display: "block",
  color: "var(--app-text-subtle)",
  fontSize: "12px",
  fontWeight: 700,
  marginBottom: "10px",
};

const layerNameStyle: CSSProperties = {
  display: "block",
  color: "var(--app-text-strong)",
  fontSize: "16px",
  lineHeight: 1.35,
};

const layerTaglineStyle: CSSProperties = {
  display: "block",
  color: "var(--app-text-muted)",
  fontSize: "13px",
  lineHeight: 1.5,
  marginTop: "6px",
};

const layerDetailStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
  gap: "18px",
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  padding: "18px",
  marginTop: "14px",
};

const detailLabelStyle: CSSProperties = {
  color: "var(--app-text-subtle)",
  fontSize: "12px",
  fontWeight: 800,
  textTransform: "uppercase",
  letterSpacing: 0,
};

const detailLeadStyle: CSSProperties = {
  margin: "8px 0 0",
  color: "var(--app-text-strong)",
  fontSize: "16px",
  lineHeight: 1.6,
  fontWeight: 600,
};

const detailTextStackStyle: CSSProperties = {
  margin: "8px 0 0",
  display: "grid",
  gap: "8px",
};

const detailBodyStyle: CSSProperties = {
  ...detailLeadStyle,
  margin: 0,
};

const chipGridStyle: CSSProperties = {
  display: "flex",
  flexWrap: "wrap",
  gap: "8px",
  marginTop: "10px",
};

const chipStyle: CSSProperties = {
  border: "1px solid var(--app-chip-border)",
  borderRadius: "999px",
  background: "var(--app-chip-bg)",
  color: "var(--app-chip-fg)",
  padding: "5px 9px",
  fontSize: "12px",
  fontWeight: 700,
};

const layerAdrButtonStyle: CSSProperties = {
  ...secondaryButtonStyle,
  marginTop: "14px",
  border: "1px solid var(--app-secondary-action-border)",
  background: "var(--app-secondary-action-bg)",
  color: "var(--app-secondary-action-fg)",
};

const flowControlsStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: "10px",
  flexWrap: "wrap",
};

const speedControlStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: "8px",
};

const speedSelectStyle: CSSProperties = {
  border: "1px solid var(--app-input-border)",
  borderRadius: "8px",
  background: "var(--app-input-bg)",
  color: "var(--app-input-fg)",
  padding: "7px 9px",
  fontSize: "13px",
  fontWeight: 700,
};

const flowTimelineShellStyle: CSSProperties = {
  display: "grid",
  gap: "10px",
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  padding: "16px",
  marginBottom: "14px",
};

const operationalTrackLabelStyle: CSSProperties = {
  color: "var(--app-text-muted)",
  fontSize: "12px",
  fontWeight: 800,
  textTransform: "uppercase",
  letterSpacing: 0,
};

const operationalTrackStyle: CSSProperties = {
  position: "relative",
  display: "grid",
  gridTemplateColumns: "repeat(5, minmax(120px, 1fr))",
  gap: "10px",
  alignItems: "start",
  minHeight: "92px",
  overflowX: "auto",
  paddingTop: "6px",
};

const trackLineStyle: CSSProperties = {
  position: "absolute",
  top: "21px",
  left: "24px",
  right: "24px",
  height: "2px",
  background: "var(--app-info-border)",
};

const trackProgressStyle: CSSProperties = {
  position: "absolute",
  top: "21px",
  left: "24px",
  height: "2px",
  background: "var(--app-info-fg)",
  transition: "width 0.35s ease",
  maxWidth: "calc(100% - 48px)",
};

const trackStageButtonStyle: CSSProperties = {
  position: "relative",
  display: "grid",
  gap: "8px",
  justifyItems: "center",
  border: 0,
  background: "transparent",
  color: "var(--app-text-muted)",
  padding: "0 4px",
  cursor: "pointer",
  minWidth: "120px",
  zIndex: 1,
};

const trackNodeStyle: CSSProperties = {
  width: "18px",
  height: "18px",
  borderRadius: "999px",
  borderWidth: "2px",
  borderStyle: "solid",
  borderColor: "var(--app-info-border)",
  background: "var(--app-surface-bg)",
  boxShadow: "0 0 0 4px var(--app-surface-muted-bg)",
};

const activeTrackNodeStyle: CSSProperties = {
  borderColor: "var(--app-info-fg)",
  background: "var(--app-info-fg)",
};

const completedTrackNodeStyle: CSSProperties = {
  borderColor: "var(--app-info-fg)",
  background: "var(--app-info-bg)",
};

const trackStageTextStyle: CSSProperties = {
  display: "grid",
  gap: "2px",
  textAlign: "center",
  minHeight: "38px",
};

const trackLabelStyle: CSSProperties = {
  color: "var(--app-text-strong)",
  fontSize: "13px",
  lineHeight: 1.25,
};

const activeTrackLabelStyle: CSSProperties = {
  ...trackLabelStyle,
  color: "var(--app-info-fg)",
};

const trackSubLabelStyle: CSSProperties = {
  color: "var(--app-text-subtle)",
  fontSize: "12px",
  fontWeight: 700,
};

const gateMarkerStyle: CSSProperties = {
  width: "11px",
  height: "11px",
  transform: "rotate(45deg)",
  borderWidth: "1px",
  borderStyle: "solid",
  borderColor: "var(--app-info-border)",
  background: "var(--app-info-bg)",
};

const activeGateMarkerStyle: CSSProperties = {
  borderColor: "var(--app-info-fg)",
  background: "var(--app-info-fg)",
};

const humanGateMarkerStyle: CSSProperties = {
  width: "14px",
  height: "14px",
  borderColor: "var(--app-warning-border)",
  background: "var(--app-warning-bg)",
};

const reflectionContextDescriptionStyle: CSSProperties = {
  margin: 0,
  color: "var(--app-text-muted)",
  fontSize: "13px",
  lineHeight: 1.55,
};

const reflectionContextPillStyle: CSSProperties = {
  border: "1px solid var(--app-chip-border)",
  borderRadius: "999px",
  background: "var(--app-chip-bg)",
  color: "var(--app-chip-fg)",
  padding: "6px 10px",
  fontSize: "12px",
  fontWeight: 800,
  whiteSpace: "nowrap",
};

const stageDetailShellStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "minmax(260px, 0.8fr) minmax(0, 1.2fr)",
  gap: "14px",
  alignItems: "stretch",
};

const stagePanelStyle: CSSProperties = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  padding: "18px",
  background: "var(--app-surface-muted-bg)",
  minWidth: 0,
};

const stageCopyPanelStyle: CSSProperties = {
  minHeight: "260px",
};

const stageStatePanelStyle: CSSProperties = {
  display: "grid",
  gridTemplateRows: "auto 1fr",
};

const reflectionInlineNoteStyle: CSSProperties = {
  display: "grid",
  gap: "8px",
  marginTop: "16px",
  borderWidth: "1px",
  borderStyle: "solid",
  borderColor: "var(--app-info-border)",
  borderRadius: "8px",
  background: "var(--app-info-bg)",
  padding: "12px",
};

const reflectionInlineHeaderStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  gap: "10px",
  flexWrap: "wrap",
};

const gateLineStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: "8px",
  flexWrap: "wrap",
  marginTop: "10px",
  color: "var(--app-text-muted)",
  fontSize: "13px",
  fontWeight: 700,
};

const gateBadgeStyle: CSSProperties = {
  borderWidth: "1px",
  borderStyle: "solid",
  borderColor: "var(--app-info-border)",
  borderRadius: "999px",
  background: "var(--app-info-bg)",
  color: "var(--app-info-fg)",
  padding: "5px 8px",
  fontSize: "12px",
  fontWeight: 800,
};

const humanGateBadgeStyle: CSSProperties = {
  ...gateBadgeStyle,
  borderColor: "var(--app-warning-border)",
  background: "var(--app-warning-bg)",
  color: "var(--app-warning-fg)",
};

const flowTitleStyle: CSSProperties = {
  margin: "8px 0 0",
  color: "var(--app-text-strong)",
  fontSize: "18px",
  lineHeight: 1.35,
  fontWeight: 750,
};

const snapshotStyle: CSSProperties = {
  margin: "10px 0 0",
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "#0f172a",
  color: "#dbeafe",
  padding: "18px",
  overflowX: "auto",
  width: "100%",
  boxSizing: "border-box",
  minHeight: "260px",
  maxHeight: "430px",
  fontSize: "12px",
  lineHeight: 1.6,
};

const designDecisionStyle: CSSProperties = {
  gridColumn: "1 / -1",
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-bg)",
  padding: "14px",
};

const designDecisionSummaryStyle: CSSProperties = {
  cursor: "pointer",
  color: "var(--app-text-strong)",
  fontSize: "13px",
  fontWeight: 800,
};

const designDecisionBodyStyle: CSSProperties = {
  margin: "10px 0 0",
  color: "var(--app-text-muted)",
  fontSize: "13px",
  lineHeight: 1.65,
};

const principleGridStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(230px, 1fr))",
  gap: "12px",
};

const principleCardStyle: CSSProperties = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  padding: "18px",
  background: "var(--app-surface-muted-bg)",
};

const principleGlyphStyle: CSSProperties = {
  color: "var(--app-info-fg)",
  fontSize: "34px",
  lineHeight: 1,
  fontWeight: 800,
  marginBottom: "10px",
};
