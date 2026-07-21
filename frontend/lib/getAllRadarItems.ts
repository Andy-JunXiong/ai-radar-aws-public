import type { RadarItem } from "../type/radar";
import {
  normalizeSignalToRadarItem,
  normalizeManualToRadarItem,
} from "./normalizeRadarItem";

export function getAllRadarItems(
  signals: Array<Record<string, unknown>> = [],
  manualItems: Array<Record<string, unknown>> = []
): RadarItem[] {
  const normalizedSignals = signals.map(normalizeSignalToRadarItem);
  const normalizedManualItems = manualItems.map(normalizeManualToRadarItem);

  return [...normalizedSignals, ...normalizedManualItems].sort((a, b) => {
    return (
      new Date(b.collected_at).getTime() - new Date(a.collected_at).getTime()
    );
  });
}
