"use client";

import { Suspense } from "react";

import ManualSessionDetailClient from "./ManualSessionDetailClient";

export default function ManualSessionDetailPage() {
  return (
    <Suspense fallback={<ManualSessionDetailFallback />}>
      <ManualSessionDetailClient />
    </Suspense>
  );
}

function ManualSessionDetailFallback() {
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
      <div style={{ color: "#6b7280", fontSize: "15px" }}>Loading manual session detail...</div>
    </main>
  );
}
