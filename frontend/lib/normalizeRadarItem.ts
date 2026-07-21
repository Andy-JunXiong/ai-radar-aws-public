import type { RadarItem } from "../type/radar";

type RadarSourceRecord = Record<string, unknown>;

function getString(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : fallback;
}

function getStringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

function getNumber(value: unknown): number | undefined {
  return typeof value === "number" ? value : undefined;
}

function getId(value: unknown, fallback: string): string {
  if (typeof value === "string" && value.trim()) return value;
  if (typeof value === "number" && Number.isFinite(value)) return String(value);
  return fallback;
}

export function normalizeSignalToRadarItem(signal: RadarSourceRecord): RadarItem {
  return {
    id: getId(signal.id ?? signal.signal_id, crypto.randomUUID()),
    title: getString(signal.title, "Untitled Signal"),
    summary: getString(signal.summary) || getString(signal.signal_summary),
    content: getString(signal.content),

    input_mode: "auto",
    source_type: getString(signal.source_type, "rss") as RadarItem["source_type"],
    content_type: "article",

    collected_at: getString(signal.collected_at, new Date().toISOString()),
    published_at: getString(signal.published_at) || undefined,

    source_name: getString(signal.source_name) || getString(signal.source),
    source_url: getString(signal.link) || getString(signal.url),

    topic: getString(signal.topic) || getString(signal.category) || undefined,
    score: getNumber(signal.score),

    status: getString(signal.status, "accepted") as RadarItem["status"],

    why_it_matters: getString(signal.why_it_matters) || undefined,
    relevance_to_projects: getString(signal.relevance_to_projects) || undefined,
    relevance_to_career: getString(signal.relevance_to_career) || undefined,
    strategic_takeaway: getString(signal.strategic_takeaway) || undefined,

    metadata: signal,
  };
}

export function normalizeManualToRadarItem(manual: RadarSourceRecord): RadarItem {
  const fileUrls = getStringArray(manual.file_urls);
  const previewImages = getStringArray(manual.preview_image_urls);

  return {
    id: getId(manual.id ?? manual.session_id, crypto.randomUUID()),
    title: getString(manual.title) || getString(manual.signal_title, "Untitled Manual Input"),
    summary: getString(manual.summary) || getString(manual.signal_summary),
    content: getString(manual.content),

    input_mode: "manual",
    source_type: "manual",
    content_type: getString(manual.content_type, "pdf") as RadarItem["content_type"],

    collected_at:
      getString(manual.created_at) ||
      getString(manual.collected_at, new Date().toISOString()),

    file_urls: fileUrls,
    file_names: getStringArray(manual.file_names),
    preview_image_urls: previewImages,

    topic: getString(manual.topic) || getString(manual.category) || undefined,
    score: getNumber(manual.score),

    status: getString(manual.status, "accepted") as RadarItem["status"],

    why_it_matters: getString(manual.why_it_matters) || undefined,
    relevance_to_projects: getString(manual.relevance_to_projects) || undefined,
    relevance_to_career: getString(manual.relevance_to_career) || undefined,
    strategic_takeaway: getString(manual.strategic_takeaway) || undefined,

    manual_session_id: getString(manual.session_id) || undefined,
    metadata: manual,
  };
}
