"use client";

import { useMemo, useState } from "react";
import type { CSSProperties } from "react";

type DemoView = "node" | "events" | "outputs";
type NodeKind = "source" | "signal" | "insight" | "gate" | "reflection" | "knowledge" | "project";
type EdgeKind = "source" | "parent" | "context" | "conflict";

type DemoNode = {
  id: string;
  title: string;
  layer: string;
  kind: NodeKind;
  status: string;
  summary: string;
  evidenceRole: string;
  x: number;
  y: number;
};

type DemoEdge = {
  id: string;
  from: string;
  to: string;
  kind: EdgeKind;
  label: string;
  note: string;
};

type DemoEvent = {
  id: string;
  time: string;
  actor: string;
  event: string;
  nodeId: string;
  detail: string;
};

type DemoOutput = {
  id: string;
  title: string;
  state: string;
  nodeId: string;
  body: string;
};

const nodes: DemoNode[] = [
  {
    id: "source",
    title: "Source Item",
    layer: "External",
    kind: "source",
    status: "Captured",
    summary: "A collected ecosystem item enters the intake queue with source metadata.",
    evidenceRole: "External claim source",
    x: 10,
    y: 48,
  },
  {
    id: "signal",
    title: "Signal",
    layer: "Signal",
    kind: "signal",
    status: "Analyzed",
    summary: "AI Radar normalizes the item into a signal record and prepares claim checks.",
    evidenceRole: "Candidate evidence carrier",
    x: 28,
    y: 48,
  },
  {
    id: "insight",
    title: "Insight",
    layer: "Insight",
    kind: "insight",
    status: "Drafted",
    summary: "A structured interpretation is created, but downstream eligibility still depends on gates.",
    evidenceRole: "Interpretation, not automatic proof",
    x: 46,
    y: 30,
  },
  {
    id: "gate",
    title: "Verification Gate",
    layer: "Gate",
    kind: "gate",
    status: "Watch allowed",
    summary: "Gate metadata separates reviewable context from low-risk action readiness.",
    evidenceRole: "Eligibility control",
    x: 46,
    y: 66,
  },
  {
    id: "reflection",
    title: "Reflection",
    layer: "Reflection",
    kind: "reflection",
    status: "Context only",
    summary: "Operator reasoning can inform judgment without becoming external factual evidence.",
    evidenceRole: "Cognitive context, not evidence",
    x: 64,
    y: 18,
  },
  {
    id: "knowledge",
    title: "Knowledge Brief",
    layer: "Knowledge",
    kind: "knowledge",
    status: "Review candidate",
    summary: "A reusable synthesis can be prepared when source support and project fit are visible.",
    evidenceRole: "Synthesized review context",
    x: 70,
    y: 48,
  },
  {
    id: "project",
    title: "Project Takeaway",
    layer: "Project",
    kind: "project",
    status: "Pending review",
    summary: "Durable project memory waits for human review before Confirm, Watch, Action, or Reject.",
    evidenceRole: "Human-reviewed project memory candidate",
    x: 89,
    y: 48,
  },
];

const edges: DemoEdge[] = [
  {
    id: "source-signal",
    from: "source",
    to: "signal",
    kind: "source",
    label: "source",
    note: "The raw source is preserved as the claim origin.",
  },
  {
    id: "signal-insight",
    from: "signal",
    to: "insight",
    kind: "parent",
    label: "parent",
    note: "The insight is derived from this signal record.",
  },
  {
    id: "signal-gate",
    from: "signal",
    to: "gate",
    kind: "source",
    label: "gate input",
    note: "Verification metadata controls downstream eligibility.",
  },
  {
    id: "insight-knowledge",
    from: "insight",
    to: "knowledge",
    kind: "parent",
    label: "synthesis",
    note: "A knowledge brief can cite the insight while keeping source support visible.",
  },
  {
    id: "reflection-knowledge",
    from: "reflection",
    to: "knowledge",
    kind: "context",
    label: "context",
    note: "Reflection informs interpretation, but is not external evidence.",
  },
  {
    id: "gate-project",
    from: "gate",
    to: "project",
    kind: "conflict",
    label: "blocks action",
    note: "The gate allows Watch but blocks low-risk Action until support improves.",
  },
  {
    id: "knowledge-project",
    from: "knowledge",
    to: "project",
    kind: "parent",
    label: "candidate",
    note: "Knowledge prepares a Project Takeaway candidate for human review.",
  },
];

const events: DemoEvent[] = [
  {
    id: "e1",
    time: "09:12",
    actor: "Collector",
    event: "source captured",
    nodeId: "source",
    detail: "Original source metadata is retained for later traceability.",
  },
  {
    id: "e2",
    time: "09:15",
    actor: "Signal pipeline",
    event: "signal analyzed",
    nodeId: "signal",
    detail: "The source becomes a normalized signal with review state.",
  },
  {
    id: "e3",
    time: "09:21",
    actor: "Insight layer",
    event: "interpretation drafted",
    nodeId: "insight",
    detail: "The insight describes why the signal may matter.",
  },
  {
    id: "e4",
    time: "09:23",
    actor: "Verification gate",
    event: "action blocked",
    nodeId: "gate",
    detail: "Watch is allowed; low-risk Action remains blocked.",
  },
  {
    id: "e5",
    time: "09:29",
    actor: "Operator",
    event: "reflection linked",
    nodeId: "reflection",
    detail: "Cognitive context is attached without upgrading factual support.",
  },
  {
    id: "e6",
    time: "09:34",
    actor: "Knowledge layer",
    event: "brief prepared",
    nodeId: "knowledge",
    detail: "The brief keeps source support and project fit visible.",
  },
  {
    id: "e7",
    time: "09:38",
    actor: "Review layer",
    event: "takeaway queued",
    nodeId: "project",
    detail: "Human review decides Confirm, Watch, Action, or Reject.",
  },
];

const outputs: DemoOutput[] = [
  {
    id: "o1",
    title: "Signal record",
    state: "Analyzed",
    nodeId: "signal",
    body: "A durable record exists, but it is not yet a project conclusion.",
  },
  {
    id: "o2",
    title: "Gate summary",
    state: "Watch only",
    nodeId: "gate",
    body: "Project Takeaway can be reviewed; low-risk Action remains blocked.",
  },
  {
    id: "o3",
    title: "Knowledge brief",
    state: "Candidate",
    nodeId: "knowledge",
    body: "Synthesis is useful only with source support and project fit attached.",
  },
  {
    id: "o4",
    title: "Project Takeaway",
    state: "Pending human review",
    nodeId: "project",
    body: "The candidate is queued; creation is not confirmation.",
  },
];

const nodeById = new Map(nodes.map((node) => [node.id, node]));

export default function ThreeViewDemoClient() {
  const [activeView, setActiveView] = useState<DemoView>("node");
  const [selectedNodeId, setSelectedNodeId] = useState("signal");

  const selectedNode = nodeById.get(selectedNodeId) ?? nodes[0];
  const selectedEdges = useMemo(
    () => edges.filter((edge) => edge.from === selectedNode.id || edge.to === selectedNode.id),
    [selectedNode.id]
  );
  const selectedEvents = useMemo(
    () => events.filter((event) => event.nodeId === selectedNode.id),
    [selectedNode.id]
  );
  const selectedOutputs = useMemo(
    () => outputs.filter((output) => output.nodeId === selectedNode.id),
    [selectedNode.id]
  );

  return (
    <div style={pageStackStyle}>
      <section style={introBandStyle}>
        <div>
          <div style={eyebrowStyle}>Architecture fixture</div>
          <h2 style={sectionTitleStyle}>One signal, three synchronized perspectives.</h2>
          <p style={descriptionStyle}>
            The same static lifecycle is rendered as a graph, an event stream, and a set of review outputs.
          </p>
        </div>
        <div style={summaryGridStyle}>
          <Metric label="Nodes" value={nodes.length.toString()} />
          <Metric label="Edges" value={edges.length.toString()} />
          <Metric label="Outputs" value={outputs.length.toString()} />
        </div>
      </section>

      <section style={workspaceStyle}>
        <div style={tabsStyle} role="tablist" aria-label="Lifecycle demo views">
          {[
            ["node", "Node View"],
            ["events", "Event Stream"],
            ["outputs", "Output View"],
          ].map(([viewId, label]) => {
            const selected = activeView === viewId;
            return (
              <button
                key={viewId}
                type="button"
                role="tab"
                aria-selected={selected}
                onClick={() => setActiveView(viewId as DemoView)}
                style={{
                  ...tabButtonStyle,
                  ...(selected ? activeTabButtonStyle : {}),
                }}
              >
                {label}
              </button>
            );
          })}
        </div>

        <div style={contentGridStyle}>
          <div style={mainPanelStyle}>
            {activeView === "node" ? (
              <NodeView selectedNodeId={selectedNode.id} onSelectNode={setSelectedNodeId} />
            ) : null}
            {activeView === "events" ? (
              <EventStreamView selectedNodeId={selectedNode.id} onSelectNode={setSelectedNodeId} />
            ) : null}
            {activeView === "outputs" ? (
              <OutputView selectedNodeId={selectedNode.id} onSelectNode={setSelectedNodeId} />
            ) : null}
          </div>

          <aside style={detailPanelStyle}>
            <div style={detailHeaderStyle}>
              <span style={{ ...kindDotStyle, background: nodePalette[selectedNode.kind].accent }} />
              <div>
                <div style={detailLabelStyle}>{selectedNode.layer}</div>
                <h3 style={detailTitleStyle}>{selectedNode.title}</h3>
              </div>
            </div>
            <div style={statusPillStyle}>{selectedNode.status}</div>
            <p style={detailBodyStyle}>{selectedNode.summary}</p>
            <div style={detailBlockStyle}>
              <div style={detailLabelStyle}>Evidence role</div>
              <p style={detailMicrocopyStyle}>{selectedNode.evidenceRole}</p>
            </div>
            <div style={detailBlockStyle}>
              <div style={detailLabelStyle}>Linked edges</div>
              <div style={edgeListStyle}>
                {selectedEdges.length ? (
                  selectedEdges.map((edge) => (
                    <EdgeRow key={edge.id} edge={edge} />
                  ))
                ) : (
                  <span style={emptyTextStyle}>No linked edges</span>
                )}
              </div>
            </div>
            <div style={detailBlockStyle}>
              <div style={detailLabelStyle}>Events and outputs</div>
              <p style={detailMicrocopyStyle}>
                {selectedEvents.length} event{selectedEvents.length === 1 ? "" : "s"} and{" "}
                {selectedOutputs.length} output{selectedOutputs.length === 1 ? "" : "s"} reference this node.
              </p>
            </div>
          </aside>
        </div>
      </section>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div style={metricStyle}>
      <span style={metricValueStyle}>{value}</span>
      <span style={metricLabelStyle}>{label}</span>
    </div>
  );
}

function NodeView({
  selectedNodeId,
  onSelectNode,
}: {
  selectedNodeId: string;
  onSelectNode: (nodeId: string) => void;
}) {
  return (
    <div style={graphShellStyle}>
      <div style={graphCanvasStyle}>
        <svg aria-hidden="true" viewBox="0 0 100 100" preserveAspectRatio="none" style={edgeSvgStyle}>
          {edges.map((edge) => {
            const from = nodeById.get(edge.from);
            const to = nodeById.get(edge.to);
            if (!from || !to) return null;
            const active = selectedNodeId === edge.from || selectedNodeId === edge.to;
            return (
              <line
                key={edge.id}
                x1={from.x}
                y1={from.y}
                x2={to.x}
                y2={to.y}
                stroke={edgePalette[edge.kind]}
                strokeWidth={active ? 0.9 : 0.55}
                strokeDasharray={edge.kind === "context" ? "2 2" : edge.kind === "conflict" ? "3 1" : undefined}
                opacity={active ? 0.95 : 0.42}
                vectorEffect="non-scaling-stroke"
              />
            );
          })}
        </svg>
        {nodes.map((node) => {
          const selected = node.id === selectedNodeId;
          const palette = nodePalette[node.kind];
          return (
            <button
              key={node.id}
              type="button"
              onClick={() => onSelectNode(node.id)}
              style={{
                ...nodeButtonStyle,
                left: `${node.x}%`,
                top: `${node.y}%`,
                borderColor: selected ? palette.accent : palette.border,
                background: selected ? palette.selectedBackground : palette.background,
                boxShadow: selected ? `0 0 0 3px ${palette.ring}` : "0 8px 18px rgba(15, 23, 42, 0.08)",
              }}
            >
              <span style={{ ...nodeLayerStyle, color: palette.accent }}>{node.layer}</span>
              <strong style={nodeTitleStyle}>{node.title}</strong>
              <span style={nodeStatusStyle}>{node.status}</span>
            </button>
          );
        })}
        <div style={legendStyle}>
          <LegendItem color={edgePalette.parent} label="parent" />
          <LegendItem color={edgePalette.source} label="source" />
          <LegendItem color={edgePalette.context} label="context" />
          <LegendItem color={edgePalette.conflict} label="blocked" />
        </div>
      </div>
    </div>
  );
}

function EventStreamView({
  selectedNodeId,
  onSelectNode,
}: {
  selectedNodeId: string;
  onSelectNode: (nodeId: string) => void;
}) {
  return (
    <div style={eventListStyle}>
      {events.map((event) => {
        const node = nodeById.get(event.nodeId);
        const selected = event.nodeId === selectedNodeId;
        return (
          <button
            key={event.id}
            type="button"
            onClick={() => onSelectNode(event.nodeId)}
            style={{
              ...eventRowStyle,
              ...(selected ? selectedEventRowStyle : {}),
            }}
          >
            <span style={eventTimeStyle}>{event.time}</span>
            <span style={eventCopyStyle}>
              <strong style={eventTitleStyle}>{event.event}</strong>
              <span style={eventMetaStyle}>
                {event.actor} / {node?.title ?? event.nodeId}
              </span>
              <span style={eventDetailStyle}>{event.detail}</span>
            </span>
          </button>
        );
      })}
    </div>
  );
}

function OutputView({
  selectedNodeId,
  onSelectNode,
}: {
  selectedNodeId: string;
  onSelectNode: (nodeId: string) => void;
}) {
  return (
    <div style={outputGridStyle}>
      {outputs.map((output) => {
        const selected = output.nodeId === selectedNodeId;
        return (
          <button
            key={output.id}
            type="button"
            onClick={() => onSelectNode(output.nodeId)}
            style={{
              ...outputCardStyle,
              ...(selected ? selectedOutputCardStyle : {}),
            }}
          >
            <span style={outputStateStyle}>{output.state}</span>
            <strong style={outputTitleStyle}>{output.title}</strong>
            <span style={outputBodyStyle}>{output.body}</span>
          </button>
        );
      })}
    </div>
  );
}

function EdgeRow({ edge }: { edge: DemoEdge }) {
  const from = nodeById.get(edge.from);
  const to = nodeById.get(edge.to);
  return (
    <div style={edgeRowStyle}>
      <span style={{ ...edgeKindStyle, borderColor: edgePalette[edge.kind], color: edgePalette[edge.kind] }}>
        {edge.label}
      </span>
      <span style={edgeTextStyle}>
        {from?.title ?? edge.from}
        {" -> "}
        {to?.title ?? edge.to}
      </span>
      <span style={edgeNoteStyle}>{edge.note}</span>
    </div>
  );
}

function LegendItem({ color, label }: { color: string; label: string }) {
  return (
    <span style={legendItemStyle}>
      <span style={{ ...legendSwatchStyle, background: color }} />
      {label}
    </span>
  );
}

const nodePalette: Record<
  NodeKind,
  { accent: string; border: string; ring: string; background: string; selectedBackground: string }
> = {
  source: {
    accent: "var(--app-info-fg)",
    border: "var(--app-info-border)",
    ring: "var(--app-info-border)",
    background: "var(--app-surface-muted-bg)",
    selectedBackground: "var(--app-info-bg)",
  },
  signal: {
    accent: "var(--app-info-fg)",
    border: "var(--app-info-border)",
    ring: "var(--app-info-border)",
    background: "var(--app-surface-muted-bg)",
    selectedBackground: "var(--app-info-bg)",
  },
  insight: {
    accent: "var(--app-chip-fg)",
    border: "var(--app-chip-border)",
    ring: "var(--app-chip-border)",
    background: "var(--app-surface-muted-bg)",
    selectedBackground: "var(--app-chip-bg)",
  },
  gate: {
    accent: "var(--app-warning-fg)",
    border: "var(--app-warning-border)",
    ring: "var(--app-warning-border)",
    background: "var(--app-warning-bg)",
    selectedBackground: "var(--app-warning-bg)",
  },
  reflection: {
    accent: "var(--app-text-muted)",
    border: "var(--app-surface-border)",
    ring: "var(--app-surface-border)",
    background: "var(--app-surface-muted-bg)",
    selectedBackground: "var(--app-surface-soft-bg)",
  },
  knowledge: {
    accent: "var(--app-success-fg)",
    border: "var(--app-success-border)",
    ring: "var(--app-success-border)",
    background: "var(--app-success-bg)",
    selectedBackground: "var(--app-success-bg)",
  },
  project: {
    accent: "var(--app-danger-fg)",
    border: "var(--app-danger-border)",
    ring: "var(--app-danger-border)",
    background: "var(--app-danger-bg)",
    selectedBackground: "var(--app-danger-bg)",
  },
};

const edgePalette: Record<EdgeKind, string> = {
  source: "var(--app-info-fg)",
  parent: "var(--app-info-fg)",
  context: "var(--app-text-muted)",
  conflict: "var(--app-warning-fg)",
};

const pageStackStyle: CSSProperties = {
  display: "grid",
  gap: "18px",
};

const introBandStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  gap: "18px",
  flexWrap: "wrap",
  border: "1px solid var(--app-surface-strong-border)",
  borderRadius: "8px",
  background: "var(--app-surface-bg)",
  padding: "20px",
  boxShadow: "var(--app-surface-shadow)",
};

const eyebrowStyle: CSSProperties = {
  color: "var(--app-text-subtle)",
  fontSize: "12px",
  fontWeight: 800,
  letterSpacing: 0,
  textTransform: "uppercase",
};

const sectionTitleStyle: CSSProperties = {
  margin: "5px 0 0",
  color: "var(--app-text-strong)",
  fontSize: "21px",
  lineHeight: 1.3,
  fontWeight: 760,
};

const descriptionStyle: CSSProperties = {
  margin: "8px 0 0",
  color: "var(--app-text-muted)",
  fontSize: "14px",
  lineHeight: 1.6,
  maxWidth: "740px",
};

const summaryGridStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(3, minmax(76px, 1fr))",
  gap: "10px",
};

const metricStyle: CSSProperties = {
  minWidth: "76px",
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  padding: "10px",
};

const metricValueStyle: CSSProperties = {
  display: "block",
  color: "var(--app-text-strong)",
  fontSize: "20px",
  lineHeight: 1,
  fontWeight: 800,
};

const metricLabelStyle: CSSProperties = {
  display: "block",
  marginTop: "5px",
  color: "var(--app-text-subtle)",
  fontSize: "12px",
  fontWeight: 700,
};

const workspaceStyle: CSSProperties = {
  border: "1px solid var(--app-surface-strong-border)",
  borderRadius: "8px",
  background: "var(--app-surface-bg)",
  padding: "18px",
  boxShadow: "var(--app-surface-shadow)",
};

const tabsStyle: CSSProperties = {
  display: "flex",
  gap: "8px",
  flexWrap: "wrap",
  marginBottom: "14px",
};

const tabButtonStyle: CSSProperties = {
  border: "1px solid var(--app-secondary-action-border)",
  borderRadius: "8px",
  background: "var(--app-secondary-action-bg)",
  color: "var(--app-secondary-action-fg)",
  padding: "8px 12px",
  fontSize: "13px",
  fontWeight: 800,
  cursor: "pointer",
};

const activeTabButtonStyle: CSSProperties = {
  borderColor: "var(--app-primary-action-border)",
  background: "var(--app-primary-action-bg)",
  color: "var(--app-primary-action-fg)",
};

const contentGridStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "minmax(0, 1.65fr) minmax(270px, 0.75fr)",
  gap: "14px",
  alignItems: "stretch",
};

const mainPanelStyle: CSSProperties = {
  minWidth: 0,
};

const graphShellStyle: CSSProperties = {
  overflowX: "auto",
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
};

const graphCanvasStyle: CSSProperties = {
  position: "relative",
  minWidth: "850px",
  height: "430px",
};

const edgeSvgStyle: CSSProperties = {
  position: "absolute",
  inset: 0,
  width: "100%",
  height: "100%",
  pointerEvents: "none",
};

const nodeButtonStyle: CSSProperties = {
  position: "absolute",
  width: "142px",
  minHeight: "86px",
  transform: "translate(-50%, -50%)",
  display: "grid",
  gap: "5px",
  alignContent: "center",
  borderWidth: "1px",
  borderStyle: "solid",
  borderRadius: "8px",
  padding: "11px",
  textAlign: "left",
  cursor: "pointer",
  transition: "border-color 0.15s ease, box-shadow 0.15s ease, background 0.15s ease",
};

const nodeLayerStyle: CSSProperties = {
  fontSize: "11px",
  lineHeight: 1,
  fontWeight: 800,
  textTransform: "uppercase",
  letterSpacing: 0,
};

const nodeTitleStyle: CSSProperties = {
  color: "var(--app-text-strong)",
  fontSize: "14px",
  lineHeight: 1.2,
};

const nodeStatusStyle: CSSProperties = {
  color: "var(--app-text-muted)",
  fontSize: "12px",
  lineHeight: 1.25,
  fontWeight: 700,
};

const legendStyle: CSSProperties = {
  position: "absolute",
  left: "16px",
  bottom: "14px",
  display: "flex",
  gap: "8px",
  flexWrap: "wrap",
  maxWidth: "calc(100% - 32px)",
};

const legendItemStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: "6px",
  border: "1px solid var(--app-surface-border)",
  borderRadius: "999px",
  background: "var(--app-surface-bg)",
  padding: "5px 8px",
  color: "var(--app-text-muted)",
  fontSize: "12px",
  fontWeight: 800,
};

const legendSwatchStyle: CSSProperties = {
  width: "8px",
  height: "8px",
  borderRadius: "999px",
};

const eventListStyle: CSSProperties = {
  display: "grid",
  gap: "10px",
};

const eventRowStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "68px minmax(0, 1fr)",
  gap: "12px",
  width: "100%",
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  padding: "13px",
  textAlign: "left",
  cursor: "pointer",
};

const selectedEventRowStyle: CSSProperties = {
  borderColor: "var(--app-primary-action-border)",
  background: "var(--app-surface-soft-bg)",
};

const eventTimeStyle: CSSProperties = {
  color: "var(--app-info-fg)",
  fontSize: "13px",
  fontWeight: 800,
};

const eventCopyStyle: CSSProperties = {
  display: "grid",
  gap: "4px",
};

const eventTitleStyle: CSSProperties = {
  color: "var(--app-text-strong)",
  fontSize: "14px",
  lineHeight: 1.25,
};

const eventMetaStyle: CSSProperties = {
  color: "var(--app-text-subtle)",
  fontSize: "12px",
  fontWeight: 800,
};

const eventDetailStyle: CSSProperties = {
  color: "var(--app-text-muted)",
  fontSize: "13px",
  lineHeight: 1.45,
};

const outputGridStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(230px, 1fr))",
  gap: "12px",
};

const outputCardStyle: CSSProperties = {
  display: "grid",
  gap: "8px",
  minHeight: "164px",
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  padding: "16px",
  textAlign: "left",
  cursor: "pointer",
};

const selectedOutputCardStyle: CSSProperties = {
  borderColor: "var(--app-primary-action-border)",
  background: "var(--app-surface-soft-bg)",
};

const outputStateStyle: CSSProperties = {
  color: "var(--app-info-fg)",
  fontSize: "12px",
  fontWeight: 800,
  textTransform: "uppercase",
  letterSpacing: 0,
};

const outputTitleStyle: CSSProperties = {
  color: "var(--app-text-strong)",
  fontSize: "16px",
  lineHeight: 1.25,
};

const outputBodyStyle: CSSProperties = {
  color: "var(--app-text-muted)",
  fontSize: "13px",
  lineHeight: 1.55,
};

const detailPanelStyle: CSSProperties = {
  display: "grid",
  alignContent: "start",
  gap: "14px",
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  padding: "16px",
  minWidth: 0,
};

const detailHeaderStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: "10px",
};

const kindDotStyle: CSSProperties = {
  flex: "0 0 auto",
  width: "12px",
  height: "12px",
  borderRadius: "999px",
};

const detailLabelStyle: CSSProperties = {
  color: "var(--app-text-subtle)",
  fontSize: "12px",
  fontWeight: 800,
  textTransform: "uppercase",
  letterSpacing: 0,
};

const detailTitleStyle: CSSProperties = {
  margin: "3px 0 0",
  color: "var(--app-text-strong)",
  fontSize: "18px",
  lineHeight: 1.3,
};

const statusPillStyle: CSSProperties = {
  justifySelf: "start",
  border: "1px solid var(--app-chip-border)",
  borderRadius: "999px",
  background: "var(--app-chip-bg)",
  color: "var(--app-chip-fg)",
  padding: "6px 9px",
  fontSize: "12px",
  fontWeight: 800,
};

const detailBodyStyle: CSSProperties = {
  margin: 0,
  color: "var(--app-text-muted)",
  fontSize: "14px",
  lineHeight: 1.6,
};

const detailBlockStyle: CSSProperties = {
  display: "grid",
  gap: "8px",
};

const detailMicrocopyStyle: CSSProperties = {
  margin: 0,
  color: "var(--app-text-muted)",
  fontSize: "13px",
  lineHeight: 1.55,
};

const edgeListStyle: CSSProperties = {
  display: "grid",
  gap: "8px",
};

const edgeRowStyle: CSSProperties = {
  display: "grid",
  gap: "5px",
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-bg)",
  padding: "10px",
};

const edgeKindStyle: CSSProperties = {
  justifySelf: "start",
  borderWidth: "1px",
  borderStyle: "solid",
  borderRadius: "999px",
  padding: "4px 7px",
  fontSize: "11px",
  fontWeight: 800,
  textTransform: "uppercase",
  letterSpacing: 0,
};

const edgeTextStyle: CSSProperties = {
  color: "var(--app-text-strong)",
  fontSize: "13px",
  lineHeight: 1.35,
  fontWeight: 800,
};

const edgeNoteStyle: CSSProperties = {
  color: "var(--app-text-muted)",
  fontSize: "12px",
  lineHeight: 1.45,
};

const emptyTextStyle: CSSProperties = {
  color: "var(--app-text-muted)",
  fontSize: "13px",
};
