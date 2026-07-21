// ───────────────────────────────────────────────────────────────
//  Content types
//  These shapes define the contract between the UI components and
//  the data source. The MVP reads from JSON in /content; the
//  production wiring (Codex's job) replaces these reads with API
//  calls or DB queries while keeping the same shapes.
// ───────────────────────────────────────────────────────────────

export type LayerId =
  | "signal"
  | "insight"
  | "reflection"
  | "knowledge"
  | "project";

export interface Layer {
  id: LayerId;
  num: string;
  name: string;
  /** lucide-react icon name; mapped to component in components/architecture/icon-map.ts */
  icon: string;
  tagline: string;
  why: string;
  how: string[];
  stack: string[];
  adr_slug: string;
}

export interface FlowStep {
  layer: LayerId;
  title: string;
  detail: string;
  /** Free-form JSON shown in the snapshot panel. Keep it small — pretty-printed in <pre>. */
  snapshot: Record<string, unknown>;
}

export interface DaoFaShuItem {
  ch: string;
  pinyin: string;
  en: string;
  body: string;
}
