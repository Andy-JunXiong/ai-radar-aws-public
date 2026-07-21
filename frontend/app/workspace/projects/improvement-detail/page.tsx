"use client";

import { Suspense } from "react";

import ProjectImprovementDetailClient from "./ProjectImprovementDetailClient";

export default function ProjectImprovementDetailPage() {
  return (
    <Suspense fallback={<ProjectImprovementDetailFallback />}>
      <ProjectImprovementDetailClient />
    </Suspense>
  );
}

function ProjectImprovementDetailFallback() {
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
      <div style={{ color: "#6b7280", fontSize: "15px" }}>Loading project improvement detail...</div>
    </main>
  );
}
