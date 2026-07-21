type PageHeaderProps = {
  title: string;
  description?: string;
  marginBottom?: string;
  size?: "default" | "compact";
};

export default function PageHeader({
  title,
  description,
  marginBottom = "28px",
  size = "default",
}: PageHeaderProps) {
  const compact = size === "compact";

  return (
    <div
      style={{
        marginBottom,
      }}
    >
      <h1
        style={{
          margin: 0,
          fontSize: compact ? "36px" : "52px",
          lineHeight: compact ? 1.15 : 1.08,
          fontWeight: 800,
          letterSpacing: 0,
          color: "var(--app-text-strong)",
        }}
      >
        {title}
      </h1>

      {description ? (
        <p
          style={{
            marginTop: "14px",
            marginBottom: 0,
            fontSize: "15px",
            lineHeight: 1.7,
            color: "var(--app-text-muted)",
            maxWidth: "900px",
          }}
        >
          {description}
        </p>
      ) : null}
    </div>
  );
}
