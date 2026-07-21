type SectionCardProps = {
  title?: string;
  children: React.ReactNode;
  marginBottom?: string;
};

export default function SectionCard({
  title,
  children,
  marginBottom = "22px",
}: SectionCardProps) {
  return (
    <section
      style={{
        border: "1px solid var(--app-surface-border)",
        borderRadius: "8px",
        padding: "24px",
        background: "var(--app-surface-bg)",
        marginBottom,
        boxShadow: "var(--app-surface-shadow)",
      }}
    >
      {title ? (
        <h2
          style={{
            marginTop: 0,
            marginBottom: "18px",
            fontSize: "22px",
            lineHeight: 1.25,
            fontWeight: 750,
            color: "var(--app-text-strong)",
            letterSpacing: "-0.025em",
          }}
        >
          {title}
        </h2>
      ) : null}

      {children}
    </section>
  );
}
