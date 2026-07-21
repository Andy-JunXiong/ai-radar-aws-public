"use client";

import { Suspense } from "react";

import SignalDetailClient from "./SignalDetailClient";

export default function SignalDetailPage() {
  return (
    <Suspense fallback={<SignalDetailFallback />}>
      <SignalDetailClient />
    </Suspense>
  );
}

function SignalDetailFallback() {
  return (
    <main
      style={{
        maxWidth: "1280px",
        margin: "0 auto",
        padding: "28px 24px 56px",
        fontFamily:
          '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif',
      }}
    >
      <div style={{ color: "#6b7280", fontSize: "15px" }}>Loading signal detail...</div>
    </main>
  );
}
