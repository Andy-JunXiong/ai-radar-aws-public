import "./globals.css";
import AppAuthGate from "@/components/AppAuthGate";
import OperatorGuidanceWidget from "@/components/OperatorGuidanceWidget";
import TopNav from "@/components/TopNav";

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `try{var t=localStorage.getItem("ai-radar-bg-theme");if(t==="deep"||t==="light"){document.documentElement.dataset.bgTheme=t;}}catch(e){}`,
          }}
        />
      </head>
      <body
        style={{
          margin: 0,
          fontFamily:
            '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif',
          background: "var(--app-bg)",
          color: "var(--app-fg)",
        }}
      >
        <TopNav />

        <main
          style={{
            paddingTop: "36px",
          }}
        >
          <AppAuthGate>{children}</AppAuthGate>
        </main>
        <OperatorGuidanceWidget />
      </body>
    </html>
  );
}
