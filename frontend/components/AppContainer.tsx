export default function AppContainer({
  children,
  style,
}: {
  children: React.ReactNode;
  style?: React.CSSProperties;
}) {
  return (
    <div
      style={{
        maxWidth: "1320px",
        margin: "0 auto",
        paddingTop: "36px",
        paddingBottom: "72px",
        paddingLeft: "24px",
        paddingRight: "24px",
        fontFamily:
          '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif',
        ...style,
      }}
    >
      {children}
    </div>
  );
}
