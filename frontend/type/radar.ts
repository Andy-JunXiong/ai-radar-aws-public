export type RadarItem = {
  id: string;
  title: string;
  summary?: string;
  content?: string;

  input_mode: "auto" | "manual";
  source_type: "official" | "creator" | "media" | "rss" | "manual";
  content_type: "article" | "pdf" | "image" | "multi_image" | "note";

  collected_at: string;
  published_at?: string;

  source_name?: string;
  source_url?: string;

  file_urls?: string[];
  file_names?: string[];
  preview_image_urls?: string[];

  topic?: string;
  score?: number;
  relevance_score?: number;
  novelty_score?: number;
  strategic_score?: number;

  status?: "accepted" | "rejected" | "pending";

  why_it_matters?: string;
  relevance_to_projects?: string;
  relevance_to_career?: string;
  strategic_takeaway?: string;

  manual_session_id?: string;
  metadata?: Record<string, unknown>;
};
