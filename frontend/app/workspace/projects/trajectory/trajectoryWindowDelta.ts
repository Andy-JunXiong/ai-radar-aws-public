export type ComparableTrajectoryWindow = "7d" | "30d" | "90d";

export type TrajectoryWindowMetric = "events" | "watch" | "action" | "risk";

export type TrajectoryWindowMetrics = Record<TrajectoryWindowMetric, number>;

export type TrajectoryWindowEvent = {
  timestamp: string;
  outcome: string;
  riskLevel: string;
};

export type TrajectoryWindowDelta = {
  windowDays: number;
  asOf: string;
  current: TrajectoryWindowMetrics;
  previous: TrajectoryWindowMetrics;
  delta: TrajectoryWindowMetrics;
  hasPreviousActivity: boolean;
};

export const trajectoryWindowDays: Record<ComparableTrajectoryWindow, number> = {
  "7d": 7,
  "30d": 30,
  "90d": 90,
};

const DAY_MS = 24 * 60 * 60 * 1000;

function eventTimestampMs(event: TrajectoryWindowEvent) {
  const timestamp = new Date(event.timestamp).getTime();
  return Number.isNaN(timestamp) ? null : timestamp;
}

function isWatchOutcome(outcome: string) {
  return outcome.toLowerCase().includes("watch");
}

function isActionOutcome(outcome: string) {
  const normalized = outcome.toLowerCase();
  return normalized.includes("action") || normalized === "confirmed";
}

function summarizeWindow(events: TrajectoryWindowEvent[]): TrajectoryWindowMetrics {
  return {
    events: events.length,
    watch: events.filter((event) => isWatchOutcome(event.outcome)).length,
    action: events.filter((event) => isActionOutcome(event.outcome)).length,
    risk: events.filter((event) => event.riskLevel !== "low").length,
  };
}

export function filterTrajectoryEventsForCurrentWindow<T extends TrajectoryWindowEvent>(
  events: T[],
  window: ComparableTrajectoryWindow,
  asOfMs: number = Date.now()
) {
  const currentStartMs = asOfMs - trajectoryWindowDays[window] * DAY_MS;
  return events.filter((event) => {
    const timestamp = eventTimestampMs(event);
    return timestamp !== null && timestamp >= currentStartMs && timestamp <= asOfMs;
  });
}

export function buildTrajectoryWindowDelta(
  events: TrajectoryWindowEvent[],
  window: ComparableTrajectoryWindow,
  asOfMs: number = Date.now()
): TrajectoryWindowDelta {
  const windowDays = trajectoryWindowDays[window];
  const currentStartMs = asOfMs - windowDays * DAY_MS;
  const previousStartMs = currentStartMs - windowDays * DAY_MS;
  const currentEvents: TrajectoryWindowEvent[] = [];
  const previousEvents: TrajectoryWindowEvent[] = [];

  for (const event of events) {
    const timestamp = eventTimestampMs(event);
    if (timestamp === null || timestamp > asOfMs || timestamp < previousStartMs) continue;
    if (timestamp >= currentStartMs) {
      currentEvents.push(event);
    } else {
      previousEvents.push(event);
    }
  }

  const current = summarizeWindow(currentEvents);
  const previous = summarizeWindow(previousEvents);
  const delta = (Object.keys(current) as TrajectoryWindowMetric[]).reduce<TrajectoryWindowMetrics>(
    (summary, metric) => {
      summary[metric] = current[metric] - previous[metric];
      return summary;
    },
    { events: 0, watch: 0, action: 0, risk: 0 }
  );

  return {
    windowDays,
    asOf: new Date(asOfMs).toISOString(),
    current,
    previous,
    delta,
    hasPreviousActivity: previous.events > 0,
  };
}
