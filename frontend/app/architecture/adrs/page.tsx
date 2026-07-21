import Link from "next/link";
import AppContainer from "@/components/AppContainer";
import PageHeader from "@/components/PageHeader";
import SectionCard from "@/components/SectionCard";
import { getLayers } from "@/lib/content";

export const metadata = {
  title: "Architecture ADRs | AI Radar",
};

export default function ADRIndexPage() {
  const layers = getLayers();

  return (
    <AppContainer style={{ paddingTop: "24px" }}>
      <PageHeader
        title="Architecture ADRs"
        description="Decision records behind the current AI Radar operating model and product architecture."
        marginBottom="22px"
      />
      <SectionCard>
        <div style={listStyle}>
          <Link href="/architecture/adrs/architecture-overview" style={overviewRowStyle}>
            <div>
              <div style={metaStyle}>ADR-000 / Architecture</div>
              <div style={titleStyle}>The five-layer architecture</div>
            </div>
            <span style={openStyle}>Open</span>
          </Link>
          {layers.map((layer) => (
            <Link
              key={layer.adr_slug}
              href={`/architecture/adrs/${layer.adr_slug}`}
              style={rowStyle}
            >
              <div>
                <div style={metaStyle}>
                  Layer {layer.num} / {layer.name}
                </div>
                <div style={titleStyle}>{layer.tagline}</div>
              </div>
              <span style={openStyle}>Open</span>
            </Link>
          ))}
        </div>
      </SectionCard>
    </AppContainer>
  );
}

const listStyle = {
  display: "grid",
  gap: "12px",
} as const;

const rowStyle = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  gap: "16px",
  border: "1px solid #e5e7eb",
  borderRadius: "16px",
  background: "#f8fafc",
  color: "inherit",
  padding: "16px",
  textDecoration: "none",
} as const;

const overviewRowStyle = {
  ...rowStyle,
  border: "1px solid #bfdbfe",
  background: "#eff6ff",
} as const;

const metaStyle = {
  color: "#64748b",
  fontSize: "12px",
  fontWeight: 800,
  textTransform: "uppercase",
  letterSpacing: "0.4px",
} as const;

const titleStyle = {
  marginTop: "6px",
  color: "#111827",
  fontSize: "16px",
  fontWeight: 700,
  lineHeight: 1.4,
} as const;

const openStyle = {
  border: "1px solid #dbeafe",
  borderRadius: "999px",
  background: "#eff6ff",
  color: "#1d4ed8",
  padding: "6px 10px",
  fontSize: "12px",
  fontWeight: 800,
  whiteSpace: "nowrap",
} as const;
