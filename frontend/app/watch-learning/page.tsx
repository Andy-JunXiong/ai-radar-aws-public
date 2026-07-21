"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import AppContainer from "@/components/AppContainer";
import DecisionCardList from "@/components/DecisionCardList";
import RequireAdminAuth from "@/components/RequireAdminAuth";
import { DecisionCard, fetchDecisionCards } from "@/lib/decisions";

type QueueFilter = "all" | "watch" | "learn";

const queueOptions: Array<{ value: QueueFilter; label: string }> = [
  { value: "all", label: "All items" },
  { value: "watch", label: "Watch only" },
  { value: "learn", label: "Learning only" },
];

function normalizeActionType(value?: string | null): "watch" | "learn" | "other" {
  const normalized = String(value || "").trim().toLowerCase();
  if (normalized === "watch") return "watch";
  if (normalized === "learn") return "learn";
  return "other";
}

export default function WatchLearningPage() {
  const [items, setItems] = useState<DecisionCard[]>([]);
  const [loading, setLoading] = useState(true);
  const [queueFilter, setQueueFilter] = useState<QueueFilter>("all");

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        setLoading(true);
        const loaded = await fetchDecisionCards();
        if (!cancelled) setItems(loaded);
      } catch {
        if (!cancelled) setItems([]);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void load();

    return () => {
      cancelled = true;
    };
  }, []);

  const watchItems = useMemo(
    () => items.filter((item) => normalizeActionType(item.action_type) === "watch"),
    [items],
  );
  const learnItems = useMemo(
    () => items.filter((item) => normalizeActionType(item.action_type) === "learn"),
    [items],
  );

  const filteredItems = useMemo(() => {
    if (queueFilter === "watch") return watchItems;
    if (queueFilter === "learn") return learnItems;
    return [...watchItems, ...learnItems].sort((a, b) =>
      String(b.updated_at || "").localeCompare(String(a.updated_at || "")),
    );
  }, [learnItems, queueFilter, watchItems]);

  return (
    <AppContainer style={{ paddingTop: "24px" }}>
      <RequireAdminAuth>
        <div style={headerPanelStyle}>
          <div>
            <div style={eyebrowStyle}>Workspace</div>
            <h1 style={pageTitleStyle}>Watch & Learning</h1>
            <p style={descriptionStyle}>
              Keep promising signals that need watching or learning before they become project takeaways.
            </p>
          </div>
          <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
            <Link href="/workspace" style={primaryButtonStyle}>
              Back to Workspace
            </Link>
            <Link href="/workspace/decisions" style={secondaryButtonStyle}>
              Decision Cards
            </Link>
          </div>
        </div>

        <section style={panelStyle}>
          <div style={sectionHeaderStyle}>
            <div>
              <div style={eyebrowStyle}>Queues</div>
              <h2 style={sectionTitleStyle}>Items not ready for project memory</h2>
            </div>
          </div>

          <div style={summaryGridStyle}>
            <SummaryCard
              label="Watch Queue"
              value={watchItems.length}
              help="Signals worth monitoring before committing them into a project."
            />
            <SummaryCard
              label="Learning Queue"
              value={learnItems.length}
              help="Ideas or methods to learn before they become project work."
            />
          </div>
        </section>

        <section style={panelStyle}>
          <div style={sectionHeaderStyle}>
            <div>
              <div style={eyebrowStyle}>Browse</div>
              <h2 style={sectionTitleStyle}>{loading ? "Loading queue" : `${filteredItems.length} item(s)`}</h2>
            </div>

            <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
              {queueOptions.map((option) => {
                const active = queueFilter === option.value;
                return (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() => setQueueFilter(option.value)}
                    style={active ? activeFilterButtonStyle : filterButtonStyle}
                  >
                    {option.label}
                  </button>
                );
              })}
            </div>
          </div>

          {loading ? (
            <div style={stateCardStyle}>Loading watch and learning items...</div>
          ) : (
            <DecisionCardList
              items={filteredItems}
              emptyText="No watch or learning items yet. Generate a decision card from a signal and classify it as watch or learn to seed this module."
              onUpdated={(updated) =>
                setItems((current) => current.map((item) => (item.id === updated.id ? updated : item)))
              }
            />
          )}
        </section>
      </RequireAdminAuth>
    </AppContainer>
  );
}

function SummaryCard({ label, value, help }: { label: string; value: number; help: string }) {
  return (
    <div style={summaryCardStyle}>
      <div style={summaryLabelStyle}>{label}</div>
      <div style={summaryValueStyle}>{value}</div>
      <div style={summaryHelpStyle}>{help}</div>
    </div>
  );
}

const headerPanelStyle = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  gap: "18px",
  flexWrap: "wrap" as const,
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-bg)",
  padding: "18px",
  marginBottom: "20px",
  boxShadow: "var(--app-surface-shadow)",
} as const;

const panelStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-bg)",
  padding: "18px",
  marginBottom: "20px",
  boxShadow: "var(--app-surface-shadow)",
} as const;

const sectionHeaderStyle = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  gap: "12px",
  flexWrap: "wrap" as const,
  marginBottom: "14px",
} as const;

const summaryGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
  gap: "12px",
} as const;

const summaryCardStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  padding: "18px",
  boxShadow: "var(--app-surface-shadow)",
} as const;

const stateCardStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  padding: "20px",
  background: "var(--app-surface-muted-bg)",
  color: "var(--app-text-muted)",
  boxShadow: "var(--app-surface-shadow)",
} as const;

const eyebrowStyle = {
  color: "var(--app-text-subtle)",
  fontSize: "12px",
  fontWeight: 700,
  textTransform: "uppercase" as const,
  letterSpacing: "0.4px",
} as const;

const pageTitleStyle = {
  margin: "4px 0 0",
  color: "var(--app-text-strong)",
  fontSize: "18px",
  fontWeight: 600,
  lineHeight: 1.35,
} as const;

const sectionTitleStyle = {
  margin: "4px 0 0",
  color: "var(--app-text-strong)",
  fontSize: "16px",
  fontWeight: 600,
  lineHeight: 1.35,
} as const;

const descriptionStyle = {
  margin: "6px 0 0",
  color: "var(--app-text-muted)",
  fontSize: "13px",
  lineHeight: 1.5,
  maxWidth: "760px",
} as const;

const summaryLabelStyle = {
  color: "var(--app-text-muted)",
  fontSize: "13px",
  marginBottom: "8px",
} as const;

const summaryValueStyle = {
  color: "var(--app-text-strong)",
  fontSize: "30px",
  fontWeight: 700,
  lineHeight: 1,
} as const;

const summaryHelpStyle = {
  color: "var(--app-text-muted)",
  fontSize: "13px",
  lineHeight: 1.6,
  marginTop: "8px",
} as const;

const primaryButtonStyle = {
  display: "inline-flex",
  alignItems: "center",
  border: "1px solid var(--app-primary-action-border)",
  borderRadius: "8px",
  background: "var(--app-primary-action-bg)",
  color: "var(--app-primary-action-fg)",
  padding: "7px 12px",
  textDecoration: "none",
  fontSize: "13px",
  fontWeight: 600,
} as const;

const secondaryButtonStyle = {
  display: "inline-flex",
  alignItems: "center",
  border: "1px solid var(--app-secondary-action-border)",
  borderRadius: "8px",
  background: "var(--app-secondary-action-bg)",
  color: "var(--app-secondary-action-fg)",
  padding: "7px 12px",
  textDecoration: "none",
  fontSize: "13px",
  fontWeight: 600,
} as const;

const filterButtonStyle = {
  ...secondaryButtonStyle,
  cursor: "pointer",
} as const;

const activeFilterButtonStyle = {
  ...filterButtonStyle,
  border: "1px solid var(--app-primary-action-border)",
  background: "var(--app-primary-action-bg)",
  color: "var(--app-primary-action-fg)",
} as const;
