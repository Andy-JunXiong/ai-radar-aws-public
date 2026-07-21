import fs from "fs";
import path from "path";
import Link from "next/link";
import { notFound } from "next/navigation";
import AppContainer from "@/components/AppContainer";
import PageHeader from "@/components/PageHeader";

const ADR_DIR = path.join(process.cwd(), "content", "adrs");

function readFrontmatter(raw: string) {
  const match = raw.match(/^---\r?\n([\s\S]*?)\r?\n---/);
  if (!match) return {};

  return match[1].split(/\r?\n/).reduce<Record<string, string>>((values, line) => {
    const separatorIndex = line.indexOf(":");
    if (separatorIndex === -1) return values;
    const key = line.slice(0, separatorIndex).trim();
    const value = line.slice(separatorIndex + 1).trim().replace(/^"|"$/g, "");
    if (key) values[key] = value;
    return values;
  }, {});
}

export function generateStaticParams() {
  const files = fs.readdirSync(ADR_DIR).filter((file) => file.endsWith(".mdx"));
  return files.map((file) => ({ slug: file.replace(/\.mdx$/, "") }));
}

export default async function ADRPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const filePath = path.join(ADR_DIR, `${slug}.mdx`);

  if (!fs.existsSync(filePath)) notFound();

  const raw = fs.readFileSync(filePath, "utf8");
  const frontmatter = readFrontmatter(raw);
  const title = frontmatter.title || slug
    .split("-")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
  const descriptionParts = [
    frontmatter.layer ? `Layer: ${frontmatter.layer}` : "",
    frontmatter.status ? `Status: ${frontmatter.status}` : "",
    frontmatter.date ? `Date: ${frontmatter.date}` : "",
  ].filter(Boolean);

  return (
    <AppContainer style={{ paddingTop: "24px" }}>
      <div style={stickyHeaderStyle}>
        <Link href="/architecture/adrs" style={backLinkStyle}>
          Back to ADRs
        </Link>
        <PageHeader
          title={title}
          description={descriptionParts.length > 0 ? descriptionParts.join(" / ") : "Architecture decision record rendered inside the product UI shell."}
          marginBottom="0"
        />
      </div>
      <section style={adrContentCardStyle}>
        <pre style={preStyle}>{raw}</pre>
      </section>
    </AppContainer>
  );
}

const stickyHeaderStyle = {
  position: "sticky",
  top: 0,
  zIndex: 10,
  marginBottom: "22px",
  paddingTop: "8px",
  paddingBottom: "18px",
  background: "#f8fafc",
  borderBottom: "1px solid #e5e7eb",
} as const;

const backLinkStyle = {
  display: "inline-flex",
  marginBottom: "18px",
  color: "#2563eb",
  textDecoration: "none",
  fontSize: "13px",
  fontWeight: 800,
} as const;

const adrContentCardStyle = {
  border: "1px solid #e5e7eb",
  borderRadius: "20px",
  padding: "24px",
  background: "#ffffff",
  marginBottom: "22px",
  boxShadow: "0 8px 24px rgba(15, 23, 42, 0.05)",
} as const;

const preStyle = {
  margin: 0,
  border: "1px solid #e5e7eb",
  borderRadius: "16px",
  background: "#0f172a",
  color: "#dbeafe",
  padding: "18px",
  overflowX: "auto",
  overflowY: "auto",
  maxHeight: "calc(100vh - 260px)",
  whiteSpace: "pre-wrap",
  fontSize: "12px",
  lineHeight: 1.65,
} as const;
