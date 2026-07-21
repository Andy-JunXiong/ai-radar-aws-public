"use client";

import { useEffect, useMemo, useState } from "react";
import { API_BASE } from "@/lib/api";

type FeedActivityItem = {
  date: string;
  rss_fetched: number;
  new_signals: number;
};

type FeedActivityResponse = {
  items: FeedActivityItem[];
  summary: {
    total_days: number;
    total_rss_fetched: number;
    total_new_signals: number;
    latest_date: string | null;
    error?: string;
  };
};

function getErrorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}

function formatDate(dateStr: string) {
  const d = new Date(dateStr);
  if (Number.isNaN(d.getTime())) return dateStr;
  return d.toLocaleDateString("en-AU", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

export default function FeedPage() {
  const [data, setData] = useState<FeedActivityResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const run = async () => {
      try {
        setLoading(true);
        setError("");

        const res = await fetch(`${API_BASE}/feed/activity`, {
          cache: "no-store",
        });

        if (!res.ok) {
          throw new Error(`Failed to fetch feed activity: ${res.status}`);
        }

        const json = (await res.json()) as FeedActivityResponse;
        setData(json);
      } catch (err: unknown) {
        setError(getErrorMessage(err, "Failed to load feed activity."));
      } finally {
        setLoading(false);
      }
    };

    run();
  }, []);

  const items = useMemo(() => data?.items ?? [], [data]);
  const summary = data?.summary;

  const totals = useMemo(() => {
    return {
      zeroDays: items.filter((x) => x.rss_fetched === 0).length,
      dedupDays: items.filter((x) => x.rss_fetched > 0 && x.new_signals === 0).length,
      activeDays: items.filter((x) => x.new_signals > 0).length,
    };
  }, [items]);

  return (
    <main className="min-h-screen bg-neutral-950 text-white px-6 py-8">
      <div className="mx-auto max-w-6xl">
        <div className="mb-8">
          <h1 className="text-3xl font-semibold tracking-tight">Feed Activity</h1>
          <p className="mt-3 text-sm text-neutral-400 max-w-3xl">
            This page shows daily RSS collection activity versus newly added AI Radar
            signals. It helps explain why the Signals Timeline may be empty on some
            days: either no articles were fetched, or fetched articles were fully
            deduplicated.
          </p>
        </div>

        {loading ? (
          <div className="rounded-2xl border border-neutral-800 bg-neutral-900 p-6">
            Loading feed activity...
          </div>
        ) : error ? (
          <div className="rounded-2xl border border-red-800 bg-red-950/40 p-6 text-red-200">
            {error}
          </div>
        ) : (
          <>
            <section className="grid gap-4 md:grid-cols-3 xl:grid-cols-6 mb-8">
              <div className="rounded-2xl border border-neutral-800 bg-neutral-900 p-5">
                <div className="text-xs uppercase tracking-wide text-neutral-500">
                  Total Days
                </div>
                <div className="mt-2 text-2xl font-semibold">
                  {summary?.total_days ?? 0}
                </div>
              </div>

              <div className="rounded-2xl border border-neutral-800 bg-neutral-900 p-5">
                <div className="text-xs uppercase tracking-wide text-neutral-500">
                  Total RSS Fetched
                </div>
                <div className="mt-2 text-2xl font-semibold">
                  {summary?.total_rss_fetched ?? 0}
                </div>
              </div>

              <div className="rounded-2xl border border-neutral-800 bg-neutral-900 p-5">
                <div className="text-xs uppercase tracking-wide text-neutral-500">
                  Total New Signals
                </div>
                <div className="mt-2 text-2xl font-semibold">
                  {summary?.total_new_signals ?? 0}
                </div>
              </div>

              <div className="rounded-2xl border border-neutral-800 bg-neutral-900 p-5">
                <div className="text-xs uppercase tracking-wide text-neutral-500">
                  Zero Fetch Days
                </div>
                <div className="mt-2 text-2xl font-semibold">{totals.zeroDays}</div>
              </div>

              <div className="rounded-2xl border border-neutral-800 bg-neutral-900 p-5">
                <div className="text-xs uppercase tracking-wide text-neutral-500">
                  Dedup-Only Days
                </div>
                <div className="mt-2 text-2xl font-semibold">{totals.dedupDays}</div>
              </div>

              <div className="rounded-2xl border border-neutral-800 bg-neutral-900 p-5">
                <div className="text-xs uppercase tracking-wide text-neutral-500">
                  Active Signal Days
                </div>
                <div className="mt-2 text-2xl font-semibold">{totals.activeDays}</div>
              </div>
            </section>

            <section className="rounded-2xl border border-neutral-800 bg-neutral-900 overflow-hidden">
              <div className="border-b border-neutral-800 px-5 py-4">
                <h2 className="text-lg font-medium">Daily Feed Stats</h2>
                <p className="mt-1 text-sm text-neutral-400">
                  RSS fetched = raw collector output. New signals = unique signals that
                  entered AI Radar after deduplication.
                </p>
              </div>

              {items.length === 0 ? (
                <div className="p-6 text-neutral-400">No feed activity data yet.</div>
              ) : (
                <div className="divide-y divide-neutral-800">
                  {items.map((item) => {
                    const status =
                      item.rss_fetched === 0
                        ? "No fetch"
                        : item.new_signals === 0
                        ? "Fully deduped"
                        : "New signals found";

                    return (
                      <div
                        key={item.date}
                        className="grid gap-4 px-5 py-5 md:grid-cols-4 md:items-center"
                      >
                        <div>
                          <div className="text-base font-medium">
                            {formatDate(item.date)}
                          </div>
                          <div className="mt-1 text-sm text-neutral-500">{status}</div>
                        </div>

                        <div>
                          <div className="text-xs uppercase tracking-wide text-neutral-500">
                            RSS Fetched
                          </div>
                          <div className="mt-1 text-xl font-semibold">
                            {item.rss_fetched}
                          </div>
                        </div>

                        <div>
                          <div className="text-xs uppercase tracking-wide text-neutral-500">
                            New Signals
                          </div>
                          <div className="mt-1 text-xl font-semibold">
                            {item.new_signals}
                          </div>
                        </div>

                        <div>
                          <div className="text-xs uppercase tracking-wide text-neutral-500">
                            Interpretation
                          </div>
                          <div className="mt-1 text-sm text-neutral-300">
                            {item.rss_fetched === 0
                              ? "No RSS articles were collected on this day."
                              : item.new_signals === 0
                              ? "Articles were fetched, but none entered the timeline because all matched existing signals."
                              : "At least some fetched articles became new timeline signals."}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </section>
          </>
        )}
      </div>
    </main>
  );
}
