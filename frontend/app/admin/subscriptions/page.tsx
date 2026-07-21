"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import AppContainer from "@/components/AppContainer";
import PageHeader from "@/components/PageHeader";
import SectionCard from "@/components/SectionCard";
import RequireAdminAuth from "@/components/RequireAdminAuth";
import { apiUrl } from "@/lib/api";
import { adminFetch } from "@/lib/adminAuth";
import {
  buildBetaUserHeaders,
  getStoredBetaUserId,
  setStoredBetaUserId,
} from "@/lib/betaUser";

type SourceItem = {
  id: string;
  name: string;
  url: string;
  type: string;
  enabled: boolean;
  priority: string;
  tags: string[];
};

type TopicPreferences = {
  preferred_topics: string[];
  blocked_topics: string[];
  boosted_topics: string[];
};

type SignalRules = {
  min_score: number;
  auto_analyze_score: number;
  auto_backlog_score: number;
  max_signals_per_day: number;
};

type ProjectLink = {
  project_id: string;
  enabled: boolean;
  topic_keywords: string[];
};

type SubscriptionSettings = {
  user_id?: string;
  sources: SourceItem[];
  topic_preferences: TopicPreferences;
  signal_rules: SignalRules;
  project_links: ProjectLink[];
};

type SubscriptionResponse = {
  settings?: SubscriptionSettings;
  scope?: string;
  status?: {
    local_path?: string;
    s3_bucket?: string;
    s3_key?: string;
    saved_source_count?: number;
    last_updated_epoch?: number | null;
  };
  runtime?: {
    date?: string;
    generated_at?: string;
    subscription_scope?: string;
    configured_source_count?: number | null;
    matched_subscription_source_count?: number | null;
    configured_active_source_count?: number | null;
    runtime_signal_sources?: string[];
  };
};

type SubscriptionSaveResponse = {
  message?: string;
  source_count?: number;
  s3_sync?: string;
  s3_key?: string;
  s3_error_type?: string;
};

type SourceAssistantSuggestion = {
  url: string;
  source_name: string;
  recommended_type: string;
  recommended_priority: string;
  suggested_tags: string[];
  rss_available: boolean;
  possible_subscribe_url: string;
  notes: string;
  subscription_candidates?: {
    label: string;
    url: string;
    type: string;
    reason: string;
  }[];
};

type SourceAssistantResponse = {
  suggestion?: SourceAssistantSuggestion;
};

type SourceHealthItem = {
  source_id?: string;
  name: string;
  url: string;
  source_type: string;
  enabled: boolean;
  health_status: "ok" | "warning" | "error" | "skipped";
  severity: "ok" | "warning" | "error" | "info";
  reason_code: string;
  message: string;
  checked_as: string;
  http_status?: number | null;
  content_type?: string;
  entry_count?: number | null;
};

type SourceHealthResponse = {
  items: SourceHealthItem[];
  summary: {
    total: number;
    checked_count: number;
    ok: number;
    warning: number;
    error: number;
    skipped: number;
    severity_counts?: Record<string, number>;
  };
};

type ProjectItem = {
  project_id: string;
  name?: string;
};

type ProjectsResponse = {
  items?: ProjectItem[];
};

type SourcePreset = {
  name: string;
  url: string;
  type: string;
  priority: string;
  tags: string[];
};

const DEFAULT_SETTINGS: SubscriptionSettings = {
  sources: [],
  topic_preferences: {
    preferred_topics: [],
    blocked_topics: [],
    boosted_topics: [],
  },
  signal_rules: {
    min_score: 45,
    auto_analyze_score: 70,
    auto_backlog_score: 60,
    max_signals_per_day: 25,
  },
  project_links: [],
};

const DEFAULT_SUBSCRIPTION_USER_ID = "admin_default";
const SOURCE_PRESET_GROUPS: {
  key: string;
  label: string;
  description: string;
  sources: SourcePreset[];
}[] = [
  {
    key: "ai",
    label: "AI",
    description: "A strong starting set for model releases, platform updates, and applied AI product news.",
    sources: [
      { name: "OpenAI News", url: "https://openai.com/news/rss.xml", type: "rss", priority: "high", tags: ["ai", "openai", "official"] },
      { name: "Anthropic News", url: "https://www.anthropic.com/news/rss.xml", type: "rss", priority: "high", tags: ["ai", "anthropic", "official"] },
      { name: "Google DeepMind Blog", url: "https://deepmind.google/discover/blog/rss.xml", type: "rss", priority: "normal", tags: ["ai", "google", "research"] },
      { name: "Hugging Face Blog", url: "https://huggingface.co/blog/feed.xml", type: "rss", priority: "normal", tags: ["ai", "open_source", "models"] },
      { name: "Google AI Blog", url: "https://blog.google/technology/ai/rss/", type: "rss", priority: "normal", tags: ["ai", "google", "official"] },
      { name: "NVIDIA Blog", url: "https://blogs.nvidia.com/feed/", type: "rss", priority: "normal", tags: ["ai", "chips", "infra"] },
      { name: "Meta AI Blog", url: "https://ai.meta.com/blog/rss/", type: "rss", priority: "normal", tags: ["ai", "meta", "research"] },
      { name: "OpenAI Developer Updates", url: "https://developers.openai.com/blog/rss.xml", type: "rss", priority: "high", tags: ["ai", "openai", "developer"] },
      { name: "Latent Space", url: "https://www.latent.space/feed", type: "rss", priority: "normal", tags: ["ai", "newsletter", "analysis"] },
      { name: "The Batch", url: "https://www.deeplearning.ai/the-batch/feed/", type: "rss", priority: "normal", tags: ["ai", "newsletter", "industry"] },
    ],
  },
  {
    key: "finance",
    label: "Finance",
    description: "Macro, markets, and financial system sources that help interpret AI signals in business context.",
    sources: [
      { name: "Financial Times", url: "https://www.ft.com/rss/home", type: "rss", priority: "normal", tags: ["finance", "markets", "macro"] },
      { name: "Bloomberg Technology", url: "https://feeds.bloomberg.com/technology/news.rss", type: "rss", priority: "normal", tags: ["finance", "technology", "markets"] },
      { name: "CoinDesk", url: "https://www.coindesk.com/arc/outboundfeeds/rss/", type: "rss", priority: "low", tags: ["finance", "crypto", "markets"] },
      { name: "Reuters Business", url: "https://feeds.reuters.com/reuters/businessNews", type: "rss", priority: "normal", tags: ["finance", "business", "markets"] },
      { name: "MarketWatch Top Stories", url: "https://feeds.content.dowjones.io/public/rss/mw_topstories", type: "rss", priority: "low", tags: ["finance", "markets", "news"] },
      { name: "WSJ Markets", url: "https://feeds.a.dj.com/rss/RSSMarketsMain.xml", type: "rss", priority: "normal", tags: ["finance", "markets", "macro"] },
      { name: "Seeking Alpha", url: "https://seekingalpha.com/feed.xml", type: "rss", priority: "low", tags: ["finance", "stocks", "analysis"] },
      { name: "The Economist Finance", url: "https://www.economist.com/finance-and-economics/rss.xml", type: "rss", priority: "low", tags: ["finance", "macro", "economics"] },
    ],
  },
  {
    key: "engineering",
    label: "Engineering",
    description: "Engineering and infrastructure sources for product teams shipping software and AI systems.",
    sources: [
      { name: "GitHub Blog", url: "https://github.blog/feed/", type: "rss", priority: "normal", tags: ["engineering", "github", "devtools"] },
      { name: "Cloudflare Blog", url: "https://blog.cloudflare.com/rss/", type: "rss", priority: "normal", tags: ["engineering", "infra", "security"] },
      { name: "Stripe Engineering", url: "https://stripe.com/blog/feed.rss", type: "rss", priority: "low", tags: ["engineering", "payments", "product"] },
      { name: "Netflix TechBlog", url: "https://netflixtechblog.com/feed", type: "rss", priority: "normal", tags: ["engineering", "scaling", "platform"] },
      { name: "Vercel Blog", url: "https://vercel.com/atom", type: "rss", priority: "normal", tags: ["engineering", "frontend", "platform"] },
      { name: "InfoQ", url: "https://feed.infoq.com/", type: "rss", priority: "normal", tags: ["engineering", "architecture", "software"] },
      { name: "Martin Fowler", url: "https://martinfowler.com/feed.atom", type: "rss", priority: "low", tags: ["engineering", "architecture", "software"] },
      { name: "AWS News Blog", url: "https://aws.amazon.com/blogs/aws/feed/", type: "rss", priority: "normal", tags: ["engineering", "cloud", "aws"] },
    ],
  },
  {
    key: "investment",
    label: "Investment",
    description: "Venture, startup, and investment-oriented sources for understanding where capital and conviction are moving.",
    sources: [
      { name: "a16z", url: "https://a16z.com/feed/", type: "rss", priority: "normal", tags: ["investment", "venture", "startups"] },
      { name: "Sequoia", url: "https://www.sequoiacap.com/feed/", type: "rss", priority: "normal", tags: ["investment", "venture", "operators"] },
      { name: "First Round Review", url: "https://review.firstround.com/rss/", type: "rss", priority: "low", tags: ["investment", "operators", "startups"] },
      { name: "Y Combinator Blog", url: "https://www.ycombinator.com/blog/rss", type: "rss", priority: "normal", tags: ["investment", "startups", "operators"] },
      { name: "NFX", url: "https://www.nfx.com/feed", type: "rss", priority: "low", tags: ["investment", "venture", "growth"] },
      { name: "Tomasz Tunguz", url: "https://tomtunguz.com/rss/", type: "rss", priority: "normal", tags: ["investment", "saas", "venture"] },
      { name: "Both Sides of the Table", url: "https://bothsidesofthetable.com/feed", type: "rss", priority: "low", tags: ["investment", "venture", "industry"] },
      { name: "AVC", url: "https://avc.com/feed/", type: "rss", priority: "low", tags: ["investment", "venture", "commentary"] },
    ],
  },
];

function toArray(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function toComma(value?: string[]) {
  return Array.isArray(value) ? value.join(", ") : "";
}

function buildSourceId() {
  return `source_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

function normalizeSourceUrl(url?: string) {
  return (url || "").trim().toLowerCase();
}

function getPresetSourceStatusCounts(
  group: { sources: SourcePreset[] },
  savedSourceUrls: Set<string>,
  stagedSourceUrls: Set<string>,
) {
  let subscribedCount = 0;
  let stagedCount = 0;
  let availableCount = 0;

  for (const source of group.sources) {
    const normalizedUrl = normalizeSourceUrl(source.url);
    if (!normalizedUrl) continue;
    if (savedSourceUrls.has(normalizedUrl)) {
      subscribedCount += 1;
    } else if (stagedSourceUrls.has(normalizedUrl)) {
      stagedCount += 1;
    } else {
      availableCount += 1;
    }
  }

  return {
    subscribedCount,
    stagedCount,
    availableCount,
  };
}

export default function AdminSubscriptionsPage() {
  const [userId, setUserId] = useState("");
  const [scope, setScope] = useState("demo_default");
  const [savedSources, setSavedSources] = useState<SourceItem[]>([]);
  const [sources, setSources] = useState<SourceItem[]>([]);
  const [preferredTopics, setPreferredTopics] = useState("");
  const [blockedTopics, setBlockedTopics] = useState("");
  const [boostedTopics, setBoostedTopics] = useState("");
  const [minScore, setMinScore] = useState("45");
  const [autoAnalyzeScore, setAutoAnalyzeScore] = useState("70");
  const [autoBacklogScore, setAutoBacklogScore] = useState("60");
  const [maxSignalsPerDay, setMaxSignalsPerDay] = useState("25");
  const [projects, setProjects] = useState<ProjectItem[]>([]);
  const [projectLinks, setProjectLinks] = useState<ProjectLink[]>([]);
  const [assistantUrl, setAssistantUrl] = useState("");
  const [assistantContext, setAssistantContext] = useState("");
  const [assistantLoading, setAssistantLoading] = useState(false);
  const [assistantErrorMessage, setAssistantErrorMessage] = useState("");
  const [sourceHealth, setSourceHealth] = useState<SourceHealthResponse | null>(null);
  const [checkingSourceHealth, setCheckingSourceHealth] = useState(false);
  const [importingLegacy, setImportingLegacy] = useState(false);
  const [assistantSuggestion, setAssistantSuggestion] = useState<SourceAssistantSuggestion | null>(null);
  const [showAdvancedTopicControls, setShowAdvancedTopicControls] = useState(false);
  const [showSourceEditor, setShowSourceEditor] = useState(true);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [presetPicker, setPresetPicker] = useState<{
    groupKey: string;
    selectedUrls: string[];
  } | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [subscriptionStatus, setSubscriptionStatus] = useState<SubscriptionResponse["status"] | null>(null);
  const [subscriptionRuntime, setSubscriptionRuntime] = useState<SubscriptionResponse["runtime"] | null>(null);

  function resolveEffectiveUserId(rawUserId?: string) {
    const normalized = (rawUserId || "").trim();
    return normalized || DEFAULT_SUBSCRIPTION_USER_ID;
  }

  function hydrate(settings?: SubscriptionSettings) {
    const value = settings || DEFAULT_SETTINGS;
    setSavedSources(Array.isArray(value.sources) ? value.sources : []);
    setSources([]);
    setPreferredTopics(toComma(value.topic_preferences?.preferred_topics));
    setBlockedTopics(toComma(value.topic_preferences?.blocked_topics));
    setBoostedTopics(toComma(value.topic_preferences?.boosted_topics));
    setMinScore(String(value.signal_rules?.min_score ?? 45));
    setAutoAnalyzeScore(String(value.signal_rules?.auto_analyze_score ?? 70));
    setAutoBacklogScore(String(value.signal_rules?.auto_backlog_score ?? 60));
    setMaxSignalsPerDay(String(value.signal_rules?.max_signals_per_day ?? 25));
    setProjectLinks(Array.isArray(value.project_links) ? value.project_links : []);
  }

  function formatStatusTime(epoch?: number | null) {
    if (!epoch) return "Not saved yet";
    try {
      return new Date(epoch * 1000).toLocaleString();
    } catch {
      return "Not saved yet";
    }
  }

  function buildSaveMessage(result: SubscriptionSaveResponse, duplicateSavedCount: number) {
    const baseMessage =
      duplicateSavedCount > 0
        ? `Subscription settings saved. ${duplicateSavedCount} duplicate source${duplicateSavedCount > 1 ? "s were" : " was"} skipped because ${duplicateSavedCount > 1 ? "they are" : "it is"} already subscribed.`
        : "Signal source and subscription settings saved successfully.";
    const sourceCount = typeof result.source_count === "number" ? ` ${result.source_count} sources are now saved.` : "";
    const s3Key = result.s3_key ? ` (${result.s3_key})` : "";

    if (result.s3_sync === "succeeded") {
      return `${baseMessage}${sourceCount} Cloud sync succeeded${s3Key}.`;
    }
    if (result.s3_sync === "failed") {
      const errorType = result.s3_error_type ? ` ${result.s3_error_type}.` : "";
      return `${baseMessage}${sourceCount} Cloud sync failed${errorType} AWS data pipeline may not see this update until S3 sync succeeds.`;
    }
    if (result.s3_sync === "skipped") {
      return `${baseMessage}${sourceCount} Cloud sync was skipped because no S3 target was configured for this backend process.`;
    }

    return `${baseMessage}${sourceCount}`;
  }

  async function loadSettings(nextUserId: string) {
    setLoading(true);
    setMessage("");
    setErrorMessage("");
    try {
      const [settingsResponse, projectsResponse] = await Promise.all([
        adminFetch(apiUrl("/settings/subscriptions"), {
          headers: {
            ...buildBetaUserHeaders(nextUserId),
          },
          cache: "no-store",
        }),
        fetch(apiUrl("/projects"), { cache: "no-store" }),
      ]);

      if (!settingsResponse.ok) {
        throw new Error(`Failed to load subscription settings (${settingsResponse.status})`);
      }
      if (!projectsResponse.ok) {
        throw new Error(`Failed to load projects (${projectsResponse.status})`);
      }

      const settingsData = (await settingsResponse.json()) as SubscriptionResponse;
      const projectData = (await projectsResponse.json()) as ProjectsResponse;
      setScope(settingsData.scope || "demo_default");
      setSubscriptionStatus(settingsData.status || null);
      setSubscriptionRuntime(settingsData.runtime || null);
      const loadedProjects = Array.isArray(projectData.items) ? projectData.items : [];
      setProjects(loadedProjects);
      hydrate(settingsData.settings);
    } catch (error) {
      console.error(error);
      hydrate(DEFAULT_SETTINGS);
      setProjects([]);
      setSubscriptionStatus(null);
      setSubscriptionRuntime(null);
      setErrorMessage("Failed to load source subscription settings.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const storedUserId = getStoredBetaUserId();
    const effectiveUserId = resolveEffectiveUserId(storedUserId);
    setUserId(effectiveUserId);
    if (!storedUserId.trim()) {
      setStoredBetaUserId(effectiveUserId);
    }
    void loadSettings(effectiveUserId);
  }, []);

  const mergedProjectLinks = useMemo(() => {
    return projects.map((project) => {
      const existing = projectLinks.find((item) => item.project_id === project.project_id);
      return (
        existing || {
          project_id: project.project_id,
          enabled: false,
          topic_keywords: [],
        }
      );
    });
  }, [projects, projectLinks]);

  const savedSourceUrls = useMemo(() => {
    return new Set(savedSources.map((item) => normalizeSourceUrl(item.url)).filter(Boolean));
  }, [savedSources]);

  const stagedSourceUrls = useMemo(() => {
    return new Set(sources.map((item) => normalizeSourceUrl(item.url)).filter(Boolean));
  }, [sources]);

  const configuredActiveSourceCount =
    subscriptionRuntime?.configured_active_source_count ??
    savedSources.filter((source) => source.enabled).length;
  const sourceHealthTotal = savedSources.length + sources.length;
  const sourceHealthAttentionItems = sourceHealth?.items.filter(
    (item) => item.health_status === "error" || item.health_status === "warning"
  ) || [];

  function upsertProjectLink(projectId: string, updates: Partial<ProjectLink>) {
    setProjectLinks((current) => {
      const existing = current.find((item) => item.project_id === projectId);
      if (existing) {
        return current.map((item) =>
          item.project_id === projectId ? { ...item, ...updates } : item
        );
      }
      return [
        ...current,
        {
          project_id: projectId,
          enabled: false,
          topic_keywords: [],
          ...updates,
        },
      ];
    });
  }

  function addSource() {
    setShowSourceEditor(true);
    setSaveSuccess(false);
    setSourceHealth(null);
    setSources((current) => [
      ...current,
      {
        id: buildSourceId(),
        name: "",
        url: "",
        type: "rss",
        enabled: true,
        priority: "normal",
        tags: [],
      },
    ]);
  }

  function openPresetPicker(groupKey: string) {
    const group = SOURCE_PRESET_GROUPS.find((item) => item.key === groupKey);
    if (!group) return;
    const availableUrls = group.sources
      .map((source) => source.url)
      .filter((url) => {
        const normalizedUrl = normalizeSourceUrl(url);
        return normalizedUrl && !savedSourceUrls.has(normalizedUrl) && !stagedSourceUrls.has(normalizedUrl);
      });
    setPresetPicker({
      groupKey,
      selectedUrls: availableUrls,
    });
    setMessage("");
    setErrorMessage("");
    if (availableUrls.length === 0) {
      setErrorMessage(`${group.label} starter sources are already in your Source Library.`);
      return;
    }

    const alreadySubscribedCount = group.sources.filter((source) =>
      savedSourceUrls.has(normalizeSourceUrl(source.url))
    ).length;
    const alreadyStagedCount = group.sources.filter((source) =>
      stagedSourceUrls.has(normalizeSourceUrl(source.url))
    ).length;
    if (alreadySubscribedCount > 0 || alreadyStagedCount > 0) {
      const notes: string[] = [];
      if (alreadySubscribedCount > 0) {
        notes.push(`${alreadySubscribedCount} already subscribed`);
      }
      if (alreadyStagedCount > 0) {
        notes.push(`${alreadyStagedCount} already staged`);
      }
      setMessage(`${group.label} bundle checked your current subscriptions. ${notes.join(", ")} and locked to avoid duplicates.`);
    }
  }

  function confirmPresetSelection() {
    if (!presetPicker) return;
    const group = SOURCE_PRESET_GROUPS.find((item) => item.key === presetPicker.groupKey);
    if (!group) return;
    let addedCount = 0;
    let skippedSavedCount = 0;
    let skippedStagedCount = 0;
    setSources((current) => {
      const existingUrls = new Set(current.map((item) => item.url.trim().toLowerCase()));
      const next = [...current];
      for (const source of group.sources.filter((item) => presetPicker.selectedUrls.includes(item.url))) {
        const normalizedUrl = source.url.trim().toLowerCase();
        if (savedSourceUrls.has(normalizedUrl)) {
          skippedSavedCount += 1;
          continue;
        }
        if (existingUrls.has(normalizedUrl)) {
          skippedStagedCount += 1;
          continue;
        }
        next.push({
          id: buildSourceId(),
          name: source.name,
          url: source.url,
          type: source.type,
          enabled: true,
          priority: source.priority,
          tags: source.tags,
        });
        existingUrls.add(normalizedUrl);
        addedCount += 1;
      }
      return next;
    });

    if (addedCount > 0) {
      setShowSourceEditor(true);
      setSaveSuccess(false);
      const notes: string[] = [];
      if (skippedSavedCount > 0) {
        notes.push(`${skippedSavedCount} already subscribed`);
      }
      if (skippedStagedCount > 0) {
        notes.push(`${skippedStagedCount} already staged`);
      }
      setMessage(
        `${group.label} starter sources added: ${addedCount}. Review them below and save when ready.${
          notes.length ? ` We skipped ${notes.join(" and ")}.` : ""
        }`
      );
      setErrorMessage("");
    } else {
      setErrorMessage(
        skippedStagedCount > 0
          ? `${group.label} starter sources are already subscribed or already staged in this intake batch.`
          : `${group.label} starter sources are already in your Source Library.`
      );
      setMessage("");
    }
    setPresetPicker(null);
  }

  function togglePresetUrl(url: string) {
    setPresetPicker((current) => {
      if (!current) return current;
      const normalizedUrl = normalizeSourceUrl(url);
      if (savedSourceUrls.has(normalizedUrl) || stagedSourceUrls.has(normalizedUrl)) {
        return current;
      }
      const exists = current.selectedUrls.includes(url);
      return {
        ...current,
        selectedUrls: exists
          ? current.selectedUrls.filter((item) => item !== url)
          : [...current.selectedUrls, url],
      };
    });
  }

  function selectAllPresetSources() {
    setPresetPicker((current) => {
      if (!current) return current;
      const group = SOURCE_PRESET_GROUPS.find((item) => item.key === current.groupKey);
      if (!group) return current;
      return {
        ...current,
        selectedUrls: group.sources
          .map((source) => source.url)
          .filter((url) => {
            const normalizedUrl = normalizeSourceUrl(url);
            return normalizedUrl && !savedSourceUrls.has(normalizedUrl) && !stagedSourceUrls.has(normalizedUrl);
          }),
      };
    });
  }

  function clearAllPresetSources() {
    setPresetPicker((current) => {
      if (!current) return current;
      return {
        ...current,
        selectedUrls: [],
      };
    });
  }

  function applyAssistantSuggestion(candidate?: {
    label: string;
    url: string;
    type: string;
    reason: string;
  }) {
    if (!assistantSuggestion) return;
    setShowSourceEditor(true);
    setSaveSuccess(false);
    const selectedUrl = candidate?.url || assistantSuggestion.possible_subscribe_url || assistantSuggestion.url;
    const normalizedUrl = normalizeSourceUrl(selectedUrl);
    if (normalizedUrl && savedSourceUrls.has(normalizedUrl)) {
      setMessage("");
      setErrorMessage("This source is already in My Subscriptions.");
      return;
    }
    if (normalizedUrl && stagedSourceUrls.has(normalizedUrl)) {
      setMessage("");
      setErrorMessage("This source is already staged in the current intake batch.");
      return;
    }
    const selectedType = candidate?.type || assistantSuggestion.recommended_type || "custom_url";
    setSources((current) => [
      ...current,
      {
        id: buildSourceId(),
        name: assistantSuggestion.source_name || _guessSourceName(assistantSuggestion.url),
        url: selectedUrl,
        type: selectedType,
        enabled: true,
        priority: assistantSuggestion.recommended_priority || "normal",
        tags: Array.isArray(assistantSuggestion.suggested_tags)
          ? assistantSuggestion.suggested_tags
          : [],
      },
    ]);
    setMessage("Suggested source was added to Source Library. Review it and save when ready.");
    setErrorMessage("");
  }

  async function handleAssistantAnalyze() {
    const normalizedUserId = resolveEffectiveUserId(userId);
    const targetUrl = assistantUrl.trim();
    if (!targetUrl) {
      setAssistantErrorMessage("Enter a website or feed URL before analyzing.");
      setMessage("");
      setErrorMessage("");
      return;
    }

    setAssistantLoading(true);
    setAssistantSuggestion(null);
    setAssistantErrorMessage("");
    setErrorMessage("");
    setMessage("");
    try {
      const response = await adminFetch(apiUrl("/settings/subscriptions/source-assistant"), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...buildBetaUserHeaders(normalizedUserId || "demo_default"),
        },
        body: JSON.stringify({ url: targetUrl, extra_context: assistantContext }),
      });
      if (!response.ok) {
        const text = await response.text();
        throw new Error(text || `Failed to analyze source URL (${response.status})`);
      }
      const data = (await response.json()) as SourceAssistantResponse;
      if (data.suggestion) {
        setAssistantSuggestion(data.suggestion);
      } else {
        setAssistantErrorMessage("AI Source Assistant could not generate a suggestion for this URL.");
      }
    } catch (error) {
      console.error(error);
      setAssistantErrorMessage("Failed to analyze this URL with AI Source Assistant.");
    } finally {
      setAssistantLoading(false);
    }
  }

  async function handleSourceHealthCheck() {
    const normalizedUserId = resolveEffectiveUserId(userId);
    const healthSources = [...savedSources, ...sources];
    if (!healthSources.length) {
      setErrorMessage("Add or load sources before running a source health check.");
      return;
    }

    setCheckingSourceHealth(true);
    setSourceHealth(null);
    setErrorMessage("");
    setMessage("");
    try {
      const response = await adminFetch(apiUrl("/settings/subscriptions/source-health"), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...buildBetaUserHeaders(normalizedUserId),
        },
        body: JSON.stringify({ sources: healthSources }),
      });
      if (!response.ok) {
        const text = await response.text();
        throw new Error(text || `Failed to check source health (${response.status})`);
      }
      const data = (await response.json()) as SourceHealthResponse;
      setSourceHealth(data);
    } catch (error) {
      console.error(error);
      setErrorMessage("Failed to check source health.");
    } finally {
      setCheckingSourceHealth(false);
    }
  }

  async function handleLegacyImport() {
    const normalizedUserId = resolveEffectiveUserId(userId);
    setImportingLegacy(true);
    setMessage("");
    setErrorMessage("");
    setSaveSuccess(false);
    try {
      const response = await adminFetch(apiUrl("/settings/subscriptions/import-legacy-rss"), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...buildBetaUserHeaders(normalizedUserId),
        },
        body: JSON.stringify({ confirm: true }),
      });
      if (!response.ok) {
        throw new Error(`Failed to import legacy sources (${response.status})`);
      }
      const result = (await response.json()) as { imported_count?: number; total_legacy_sources?: number };
      await loadSettings(normalizedUserId);
      setMessage(
        (result.imported_count || 0) > 0
          ? `Imported ${result.imported_count} legacy RSS sources into My Subscriptions.`
          : `No new legacy RSS sources were found. ${result.total_legacy_sources || 0} legacy sources are already covered.`
      );
    } catch (error) {
      console.error(error);
      setErrorMessage("Failed to import legacy RSS sources.");
    } finally {
      setImportingLegacy(false);
    }
  }

  function updateSource(id: string, updates: Partial<SourceItem>) {
    setSaveSuccess(false);
    setSourceHealth(null);
    setSources((current) => current.map((item) => (item.id === id ? { ...item, ...updates } : item)));
  }

  function removeSource(id: string) {
    setSaveSuccess(false);
    setSourceHealth(null);
    setSources((current) => current.filter((item) => item.id !== id));
  }

  async function handleSave() {
    const normalizedUserId = resolveEffectiveUserId(userId);
    const mergedSources = [...savedSources];
    const existingUrls = new Set(savedSources.map((item) => item.url.trim().toLowerCase()));
    let duplicateSavedCount = 0;
    for (const source of sources) {
      const normalizedUrl = source.url.trim().toLowerCase();
      if (normalizedUrl && existingUrls.has(normalizedUrl)) {
        duplicateSavedCount += 1;
        continue;
      }
      mergedSources.push(source);
      if (normalizedUrl) {
        existingUrls.add(normalizedUrl);
      }
    }

    const payload: SubscriptionSettings = {
      sources: mergedSources,
      topic_preferences: {
        preferred_topics: toArray(preferredTopics),
        blocked_topics: toArray(blockedTopics),
        boosted_topics: toArray(boostedTopics),
      },
      signal_rules: {
        min_score: Number(minScore) || 0,
        auto_analyze_score: Number(autoAnalyzeScore) || 0,
        auto_backlog_score: Number(autoBacklogScore) || 0,
        max_signals_per_day: Number(maxSignalsPerDay) || 0,
      },
      project_links: mergedProjectLinks,
    };

    setSaving(true);
    setMessage("");
    setErrorMessage("");
    setSaveSuccess(false);

    try {
      const response = await adminFetch(apiUrl("/settings/subscriptions"), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...buildBetaUserHeaders(normalizedUserId),
        },
        body: JSON.stringify({ settings: payload }),
      });

      if (!response.ok) {
        const text = await response.text();
        throw new Error(text || `Failed to save subscription settings (${response.status})`);
      }

      const saveResult = (await response.json()) as SubscriptionSaveResponse;
      const saveMessage = buildSaveMessage(saveResult, duplicateSavedCount);
      setUserId(normalizedUserId);
      setStoredBetaUserId(normalizedUserId);
      await loadSettings(normalizedUserId);
      setMessage(saveMessage);
      setSources([]);
      setAssistantSuggestion(null);
      setAssistantUrl("");
      setAssistantContext("");
      setShowSourceEditor(false);
      setSaveSuccess(true);
    } catch (error) {
      console.error(error);
      setErrorMessage("Failed to save signal source and subscription settings.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <AppContainer>
      <RequireAdminAuth>
        <PageHeader
          title="Signal Source & Subscription Settings"
          description="Configure what sources should be monitored, which topics deserve more attention, and what rules determine how signals enter your workflow."
          size="compact"
        />

        <div style={toolbarRowStyle}>
          <Link href="/admin" style={toolbarPrimaryLinkStyle}>
            Back to Admin
          </Link>
          <Link href="/admin/subscriptions/library" style={toolbarSecondaryLinkStyle}>
            View My Subscriptions
          </Link>
        </div>

        <SectionCard title="Subscription Identity">
          <div style={{ display: "grid", gap: "12px" }}>
            <label style={{ display: "grid", gap: "8px", fontSize: "13px", fontWeight: 700, color: "var(--app-text-muted)" }}>
              Subscription Scope ID
              <input
                value={userId}
                onChange={(event) => setUserId(event.target.value)}
                placeholder={DEFAULT_SUBSCRIPTION_USER_ID}
                style={inputStyle}
              />
            </label>
            <div style={{ fontSize: "13px", color: "var(--app-text-muted)" }}>
              Current scope: <strong style={{ color: "var(--app-text-strong)" }}>{scope}</strong>
            </div>
            <div style={{ fontSize: "12px", color: "var(--app-text-subtle)", lineHeight: 1.6 }}>
              This field defaults to a stable admin scope automatically. You only need to change it later if you want separate subscription profiles.
            </div>
          </div>
        </SectionCard>

        <SectionCard title="Source Library">
          <div style={{ display: "grid", gap: "12px" }}>
            <div style={{ fontSize: "14px", color: "var(--app-text-muted)", lineHeight: 1.7 }}>
              Use this page to discover and stage new information sources. Your saved subscriptions live in `My Subscriptions`.
            </div>
            <div style={savedSummaryHintStyle}>
              <div style={{ fontSize: "14px", fontWeight: 700, color: "var(--app-success-fg)" }}>
                Saved subscriptions: {savedSources.length}
              </div>
              <div style={{ fontSize: "13px", color: "var(--app-success-fg)", lineHeight: 1.7 }}>
                This page is for adding new sources. Existing subscriptions are managed separately so this intake flow stays clean.
              </div>
            </div>
            <div style={runtimeStatusPanelStyle}>
              <div style={{ fontSize: "14px", fontWeight: 800, color: "var(--app-text-strong)" }}>Subscription Runtime Status</div>
              <div style={runtimeStatusGridStyle}>
                <div style={runtimeStatusItemStyle}>
                  <div style={runtimeStatusLabelStyle}>Current scope</div>
                  <div style={runtimeStatusValueStyle}>{scope}</div>
                </div>
                <div style={runtimeStatusItemStyle}>
                  <div style={runtimeStatusLabelStyle}>Saved source count</div>
                  <div style={runtimeStatusValueStyle}>{subscriptionStatus?.saved_source_count ?? savedSources.length}</div>
                </div>
                <div style={runtimeStatusItemStyle}>
                  <div style={runtimeStatusLabelStyle}>Last saved</div>
                  <div style={runtimeStatusValueStyle}>{formatStatusTime(subscriptionStatus?.last_updated_epoch)}</div>
                </div>
                <div style={runtimeStatusItemStyle}>
                  <div style={runtimeStatusLabelStyle}>S3 bucket</div>
                  <div style={runtimeStatusValueStyle}>{subscriptionStatus?.s3_bucket || "Not configured"}</div>
                </div>
              </div>
              <div style={{ display: "grid", gap: "6px" }}>
                <div style={runtimeStatusPathStyle}>
                  <strong>S3 key:</strong> {subscriptionStatus?.s3_key || "Unavailable"}
                </div>
                <div style={runtimeStatusPathStyle}>
                  <strong>Local path:</strong> {subscriptionStatus?.local_path || "Unavailable"}
                </div>
              </div>
            </div>
            <div style={runtimeStatusPanelStyle}>
              <div style={{ fontSize: "14px", fontWeight: 800, color: "var(--app-text-strong)" }}>Daily Runtime Snapshot</div>
              <div style={runtimeStatusGridStyle}>
                <div style={runtimeStatusItemStyle}>
                  <div style={runtimeStatusLabelStyle}>Last run date</div>
                  <div style={runtimeStatusValueStyle}>{subscriptionRuntime?.date || "Unavailable"}</div>
                </div>
                <div style={runtimeStatusItemStyle}>
                  <div style={runtimeStatusLabelStyle}>Configured active sources</div>
                  <div style={runtimeStatusValueStyle}>{configuredActiveSourceCount}</div>
                </div>
                <div style={runtimeStatusItemStyle}>
                  <div style={runtimeStatusLabelStyle}>Matched subscription sources</div>
                  <div style={runtimeStatusValueStyle}>
                    {subscriptionRuntime?.matched_subscription_source_count ?? "Unavailable"}
                  </div>
                </div>
                <div style={runtimeStatusItemStyle}>
                  <div style={runtimeStatusLabelStyle}>Runtime source count</div>
                  <div style={runtimeStatusValueStyle}>
                    {subscriptionRuntime?.runtime_signal_sources?.length ?? 0}
                  </div>
                </div>
              </div>
              <div style={runtimeStatusPathStyle}>
                <strong>Runtime sources:</strong>{" "}
                {subscriptionRuntime?.runtime_signal_sources?.length
                  ? subscriptionRuntime.runtime_signal_sources.join(", ")
                  : "No runtime source list available yet."}
              </div>
            </div>
            <div style={assistantPanelStyle}>
              <div style={{ display: "grid", gap: "8px" }}>
                <div style={{ fontSize: "16px", fontWeight: 700, color: "var(--app-text-strong)" }}>Quick starter collections</div>
                <div style={{ fontSize: "14px", color: "var(--app-text-muted)", lineHeight: 1.7 }}>
                  If you already know the direction you care about, start from a curated bundle instead of building the
                  source library one URL at a time.
                </div>
              </div>
              <div style={presetGridStyle}>
                {SOURCE_PRESET_GROUPS.map((group) => {
                  const statusCounts = getPresetSourceStatusCounts(group, savedSourceUrls, stagedSourceUrls);
                  const helperNotes: string[] = [];
                  if (statusCounts.subscribedCount > 0) {
                    helperNotes.push(`${statusCounts.subscribedCount} subscribed`);
                  }
                  if (statusCounts.stagedCount > 0) {
                    helperNotes.push(`${statusCounts.stagedCount} staged`);
                  }
                  return (
                    <div key={group.key} style={presetCardStyle}>
                      <div style={{ display: "grid", gap: "6px" }}>
                      <div style={{ fontSize: "16px", fontWeight: 700, color: "var(--app-text-strong)" }}>{group.label}</div>
                      <div style={{ fontSize: "13px", color: "var(--app-text-muted)", lineHeight: 1.7 }}>{group.description}</div>
                        <div style={{ fontSize: "12px", color: "var(--app-text-subtle)" }}>
                      {group.sources.map((source) => source.name).join(" • ")}
                        </div>
                        <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", alignItems: "center" }}>
                          <span style={bundleCountBadgeStyle}>{statusCounts.availableCount} available</span>
                          {helperNotes.length ? (
                            <span style={bundleMutedNoteStyle}>{helperNotes.join(" · ")}</span>
                          ) : null}
                        </div>
                      </div>
                    <button
                      onClick={() => openPresetPicker(group.key)}
                      disabled={statusCounts.availableCount === 0}
                      style={
                        statusCounts.availableCount === 0
                          ? buttonStyle("#e5e7eb", "#94a3b8", "#cbd5e1")
                          : buttonStyle("#111827", "#ffffff")
                      }
                    >
                      {statusCounts.availableCount === 0 ? `${group.label} Already Added` : `Choose ${group.label} Sources`}
                    </button>
                  </div>
                  );
                })}
              </div>
            </div>
            <div style={assistantPanelStyle}>
              <div style={{ display: "grid", gap: "8px" }}>
                <div style={{ fontSize: "16px", fontWeight: 700, color: "#111827" }}>AI Source Assistant</div>
                <div style={{ fontSize: "14px", color: "#64748b", lineHeight: 1.7 }}>
                  Paste a website or feed URL. AI Radar will suggest the best source type, tags, and subscribe URL so users do
                  not need to know whether it is RSS, research, or a newsletter ahead of time.
                </div>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: "10px", alignItems: "center" }}>
                <input
                  value={assistantUrl}
                  onChange={(event) => {
                    setAssistantUrl(event.target.value);
                    if (assistantErrorMessage) {
                      setAssistantErrorMessage("");
                    }
                  }}
                  placeholder="https://example.com/blog or https://example.com/rss.xml"
                  aria-invalid={Boolean(assistantErrorMessage)}
                  style={assistantErrorMessage ? { ...inputStyle, borderColor: "#fca5a5" } : inputStyle}
                />
                <button
                  onClick={() => void handleAssistantAnalyze()}
                  disabled={assistantLoading}
                  style={buttonStyle("#111827", "#ffffff")}
                >
                  {assistantLoading ? "Analyzing..." : "Analyze URL"}
                </button>
              </div>
              {assistantErrorMessage ? (
                <div style={assistantInlineErrorStyle}>{assistantErrorMessage}</div>
              ) : null}
              <textarea
                value={assistantContext}
                onChange={(event) => setAssistantContext(event.target.value)}
                placeholder="Optional: paste visible links or notes from the page, for example newsletter links, website links, or what you saw on the profile page."
                style={{ ...textAreaStyle, minHeight: "96px" }}
              />
              {assistantSuggestion ? (
                <div style={assistantResultStyle}>
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: "12px" }}>
                    <div>
                      <div style={assistantLabelStyle}>Suggested name</div>
                      <div style={assistantValueStyle}>{assistantSuggestion.source_name || "Untitled source"}</div>
                    </div>
                    <div>
                      <div style={assistantLabelStyle}>Recommended type</div>
                      <div style={assistantValueStyle}>{assistantSuggestion.recommended_type || "custom_url"}</div>
                    </div>
                    <div>
                      <div style={assistantLabelStyle}>Priority</div>
                      <div style={assistantValueStyle}>{assistantSuggestion.recommended_priority || "normal"}</div>
                    </div>
                    <div>
                      <div style={assistantLabelStyle}>RSS available</div>
                      <div style={assistantValueStyle}>{assistantSuggestion.rss_available ? "Yes" : "Unknown / no direct feed detected"}</div>
                    </div>
                  </div>
                  <div>
                    <div style={assistantLabelStyle}>Suggested tags</div>
                    <div style={assistantValueStyle}>
                      {assistantSuggestion.suggested_tags?.length ? assistantSuggestion.suggested_tags.join(", ") : "No tags suggested"}
                    </div>
                  </div>
                  <div>
                    <div style={assistantLabelStyle}>Suggested subscribe URL</div>
                    <div style={assistantValueStyle}>{assistantSuggestion.possible_subscribe_url || assistantSuggestion.url || "None suggested"}</div>
                  </div>
                  <div>
                    <div style={assistantLabelStyle}>Assistant notes</div>
                    <div style={{ ...assistantValueStyle, lineHeight: 1.7 }}>{assistantSuggestion.notes || "No notes generated."}</div>
                  </div>
                  {assistantSuggestion.subscription_candidates?.length ? (
                    <div style={{ display: "grid", gap: "10px" }}>
                      <div style={assistantLabelStyle}>Suggested subscription candidates</div>
                      {assistantSuggestion.subscription_candidates.map((candidate, index) => {
                        const normalizedCandidateUrl = normalizeSourceUrl(candidate.url);
                        const candidateAlreadySubscribed = normalizedCandidateUrl
                          ? savedSourceUrls.has(normalizedCandidateUrl)
                          : false;
                        const candidateAlreadyStaged = normalizedCandidateUrl
                          ? stagedSourceUrls.has(normalizedCandidateUrl)
                          : false;
                        const candidateLocked = candidateAlreadySubscribed || candidateAlreadyStaged;
                        return (
                        <div key={`${candidate.label}-${index}`} style={candidateCardStyle}>
                          <div style={{ display: "grid", gap: "4px" }}>
                            <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", alignItems: "center" }}>
                              <div style={{ fontSize: "14px", fontWeight: 700, color: "#111827" }}>
                                {candidate.label}
                              </div>
                              {candidateAlreadySubscribed ? (
                                <span style={alreadySubscribedBadgeStyle}>Already in My Subscriptions</span>
                              ) : null}
                              {!candidateAlreadySubscribed && candidateAlreadyStaged ? (
                                <span style={alreadySubscribedBadgeStyle}>Already staged</span>
                              ) : null}
                            </div>
                            <div style={{ fontSize: "13px", color: "#6b7280" }}>
                              {candidate.type || "custom_url"}{candidate.url ? ` · ${candidate.url}` : ""}
                            </div>
                            <div style={{ fontSize: "13px", color: "#475569", lineHeight: 1.6 }}>{candidate.reason}</div>
                          </div>
                          <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                            <button
                              onClick={() => applyAssistantSuggestion(candidate)}
                              disabled={candidateLocked}
                              style={
                                candidateLocked
                                  ? buttonStyle("#e5e7eb", "#94a3b8", "#cbd5e1")
                                  : buttonStyle("#111827", "#ffffff")
                              }
                            >
                              {candidateAlreadySubscribed
                                ? "Already Subscribed"
                                : candidateAlreadyStaged
                                  ? "Already Staged"
                                  : "Add This Source"}
                            </button>
                            {candidate.url ? (
                              <a
                                href={candidate.url}
                                target="_blank"
                                rel="noreferrer"
                                style={buttonStyle("#ffffff", "#111827", "#d1d5db")}
                              >
                                Open
                              </a>
                            ) : null}
                          </div>
                        </div>
                        );
                      })}
                    </div>
                  ) : null}
                  {!assistantSuggestion.subscription_candidates?.length ? (
                    <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
                      {(() => {
                        const normalizedSuggestedUrl = normalizeSourceUrl(
                          assistantSuggestion.possible_subscribe_url || assistantSuggestion.url
                        );
                        const suggestedAlreadySubscribed = normalizedSuggestedUrl
                          ? savedSourceUrls.has(normalizedSuggestedUrl)
                          : false;
                        const suggestedAlreadyStaged = normalizedSuggestedUrl
                          ? stagedSourceUrls.has(normalizedSuggestedUrl)
                          : false;
                        const suggestedLocked = suggestedAlreadySubscribed || suggestedAlreadyStaged;
                        return (
                          <button
                            onClick={() => applyAssistantSuggestion()}
                            disabled={suggestedLocked}
                            style={
                              suggestedLocked
                                ? buttonStyle("#e5e7eb", "#94a3b8", "#cbd5e1")
                                : buttonStyle("#111827", "#ffffff")
                            }
                          >
                            {suggestedAlreadySubscribed
                              ? "Already Subscribed"
                              : suggestedAlreadyStaged
                                ? "Already Staged"
                                : "Add Suggested Source"}
                          </button>
                        );
                      })()}
                      {assistantSuggestion.possible_subscribe_url ? (
                        <a
                          href={assistantSuggestion.possible_subscribe_url}
                          target="_blank"
                          rel="noreferrer"
                          style={buttonStyle("#ffffff", "#111827", "#d1d5db")}
                        >
                          Open Suggested Feed
                        </a>
                      ) : null}
                    </div>
                  ) : null}
                </div>
              ) : null}
            </div>
            <div>
              <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
                <button onClick={addSource} style={buttonStyle("#111827", "#ffffff")}>
                  Add Source
                </button>
                <button
                  onClick={() => void handleLegacyImport()}
                  disabled={importingLegacy}
                  style={buttonStyle("#ffffff", "#111827", "#d1d5db")}
                >
                  {importingLegacy ? "Importing..." : "Import Legacy RSS Sources"}
                </button>
                <Link href="/admin/subscriptions/library" style={buttonStyle("#ffffff", "#111827", "#d1d5db")}>
                  View My Subscriptions
                </Link>
                <button
                  onClick={() => void handleSourceHealthCheck()}
                  disabled={checkingSourceHealth || sourceHealthTotal === 0}
                  style={
                    checkingSourceHealth || sourceHealthTotal === 0
                      ? buttonStyle("#e5e7eb", "#94a3b8", "#cbd5e1")
                      : buttonStyle("#ffffff", "#111827", "#d1d5db")
                  }
                >
                  {checkingSourceHealth ? "Checking..." : "Check Source Health"}
                </button>
                {sources.length > 0 ? (
                  <button
                    onClick={() => setShowSourceEditor((current) => !current)}
                    style={buttonStyle("#ffffff", "#111827", "#d1d5db")}
                  >
                    {showSourceEditor ? "Hide Source Editor" : "Edit Source Library"}
                  </button>
                ) : null}
              </div>
            </div>
            {sourceHealth ? (
              <div style={sourceHealthPanelStyle}>
                <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", alignItems: "center" }}>
                  <span style={sourceHealthBadgeStyle("#dcfce7", "#166534")}>OK {sourceHealth.summary.ok}</span>
                  <span style={sourceHealthBadgeStyle("#fef3c7", "#92400e")}>Warnings {sourceHealth.summary.warning}</span>
                  <span style={sourceHealthBadgeStyle("#fee2e2", "#991b1b")}>Errors {sourceHealth.summary.error}</span>
                  <span style={sourceHealthBadgeStyle("#e0f2fe", "#075985")}>Skipped {sourceHealth.summary.skipped}</span>
                  <span style={{ fontSize: "13px", color: "#475569" }}>
                    Checked {sourceHealth.summary.checked_count} feed-like sources out of {sourceHealth.summary.total}.
                  </span>
                </div>
                {sourceHealthAttentionItems.length ? (
                  <div style={{ display: "grid", gap: "8px" }}>
                    {sourceHealthAttentionItems.slice(0, 8).map((item) => (
                      <div key={`${item.source_id || item.url}-${item.reason_code}`} style={sourceHealthIssueStyle}>
                        <div style={{ fontWeight: 800, color: item.health_status === "error" ? "#991b1b" : "#92400e" }}>
                          {item.name || "Untitled source"} · {item.reason_code}
                        </div>
                        <div style={{ color: "#475569", wordBreak: "break-all" }}>{item.url || "No URL"}</div>
                        <div style={{ color: "#475569" }}>
                          {item.message}
                          {typeof item.http_status === "number" ? ` HTTP ${item.http_status}.` : ""}
                          {typeof item.entry_count === "number" ? ` Entries: ${item.entry_count}.` : ""}
                        </div>
                      </div>
                    ))}
                    {sourceHealthAttentionItems.length > 8 ? (
                      <div style={{ fontSize: "13px", color: "#64748b" }}>
                        {sourceHealthAttentionItems.length - 8} more source health findings are hidden here to keep the page readable.
                      </div>
                    ) : null}
                  </div>
                ) : (
                  <div style={{ fontSize: "13px", color: "#166534", fontWeight: 700 }}>
                    Feed-like active sources parsed successfully. Custom pages and disabled sources remain advisory/skipped.
                  </div>
                )}
              </div>
            ) : null}
            {sources.length === 0 ? (
              <div style={emptyStateStyle}>No new sources staged yet. Add a source here, then save to move it into My Subscriptions.</div>
            ) : showSourceEditor ? (
              <div style={{ display: "grid", gap: "14px" }}>
                {sources.map((source) => (
                  <div key={source.id} style={subPanelStyle}>
                    <div style={{ display: "grid", gridTemplateColumns: "1.4fr 1.8fr 0.9fr 0.9fr 0.8fr", gap: "10px" }}>
                      <input
                        value={source.name}
                        onChange={(event) => updateSource(source.id, { name: event.target.value })}
                        placeholder="Source name"
                        style={inputStyle}
                      />
                      <input
                        value={source.url}
                        onChange={(event) => updateSource(source.id, { url: event.target.value })}
                        placeholder="https://..."
                        style={inputStyle}
                      />
                      <select
                        value={source.type}
                        onChange={(event) => updateSource(source.id, { type: event.target.value })}
                        style={inputStyle}
                      >
                        <option value="rss">RSS</option>
                        <option value="official_blog">Official Blog</option>
                        <option value="research">Research</option>
                        <option value="newsletter">Newsletter</option>
                        <option value="custom_url">Custom URL</option>
                      </select>
                      <select
                        value={source.priority}
                        onChange={(event) => updateSource(source.id, { priority: event.target.value })}
                        style={inputStyle}
                      >
                        <option value="high">High</option>
                        <option value="normal">Normal</option>
                        <option value="low">Low</option>
                      </select>
                      <label style={checkboxLabelStyle}>
                        <input
                          type="checkbox"
                          checked={source.enabled}
                          onChange={(event) => updateSource(source.id, { enabled: event.target.checked })}
                        />
                        Active
                      </label>
                    </div>
                    <div style={{ marginTop: "10px", display: "grid", gridTemplateColumns: "1fr auto", gap: "10px" }}>
                      <input
                        value={toComma(source.tags)}
                        onChange={(event) => updateSource(source.id, { tags: toArray(event.target.value) })}
                        placeholder="Tags, comma separated"
                        style={inputStyle}
                      />
                      <button onClick={() => removeSource(source.id)} style={buttonStyle("#ffffff", "#111827", "#d1d5db")}>
                        Delete
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div style={{ display: "grid", gap: "12px" }}>
                <div style={savedSummaryHintStyle}>
                  Source Library saved. Click `Edit Source Library` if you want to change any source.
                </div>
                {sources.map((source) => (
                  <div key={source.id} style={savedSourceCardStyle}>
                    <div style={{ display: "grid", gap: "6px" }}>
                      <div style={{ fontSize: "15px", fontWeight: 700, color: "#111827" }}>
                        {source.name || "Untitled source"}
                      </div>
                      <div style={{ fontSize: "13px", color: "#475569", lineHeight: 1.6, wordBreak: "break-all" }}>
                        {source.url || "No URL yet"}
                      </div>
                    </div>
                    <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", alignItems: "center" }}>
                      <span style={savedBadgeStyle}>{source.type || "custom_url"}</span>
                      <span style={savedBadgeStyle}>{source.priority || "normal"}</span>
                      <span style={savedBadgeStyle}>{source.enabled ? "active" : "paused"}</span>
                    </div>
                    {source.tags.length ? (
                      <div style={{ fontSize: "12px", color: "#64748b" }}>{source.tags.join(", ")}</div>
                    ) : null}
                  </div>
                ))}
              </div>
            )}
          </div>
        </SectionCard>

        <SectionCard title="Topic Focus">
          <div style={sectionIntroStyle}>
            This part is optional. In most cases you subscribe to the sources you care about and stop there. If you want a little
            extra steering, add a few focus topics here and AI Radar will favor signals around them.
          </div>
          <div style={{ display: "grid", gap: "10px" }}>
            <div style={{ display: "grid", gap: "8px" }}>
              <div style={fieldTitleStyle}>Focus topics</div>
              <div style={fieldHelpStyle}>Optional keywords or themes you want AI Radar to lean toward, such as AI agents, policy, or property AI.</div>
              <textarea
                value={preferredTopics}
                onChange={(event) => setPreferredTopics(event.target.value)}
                placeholder="Focus topics, comma separated"
                style={textAreaStyle}
              />
            </div>
            <button
              type="button"
              onClick={() => setShowAdvancedTopicControls((current) => !current)}
              style={buttonStyle("#ffffff", "#111827", "#d1d5db")}
            >
              {showAdvancedTopicControls ? "Hide Advanced Topic Controls" : "Show Advanced Topic Controls"}
            </button>
          </div>
          {showAdvancedTopicControls ? (
            <div style={{ ...formGridStyle, marginTop: "12px" }}>
              <div style={{ display: "grid", gap: "8px" }}>
                <div style={fieldTitleStyle}>Boosted topics</div>
                <div style={fieldHelpStyle}>A stronger version of focus topics. Only use this if you want these themes to consistently rank above everything else.</div>
                <textarea
                  value={boostedTopics}
                  onChange={(event) => setBoostedTopics(event.target.value)}
                  placeholder="Boosted topics, comma separated"
                  style={textAreaStyle}
                />
              </div>
              <div style={{ display: "grid", gap: "8px" }}>
                <div style={fieldTitleStyle}>Blocked topics</div>
                <div style={fieldHelpStyle}>Topics you explicitly want removed from the feed. Most users can leave this blank at first.</div>
                <textarea
                  value={blockedTopics}
                  onChange={(event) => setBlockedTopics(event.target.value)}
                  placeholder="Blocked topics, comma separated"
                  style={textAreaStyle}
                />
              </div>
              <div style={advancedHintCardStyle}>
                <div style={{ fontSize: "13px", fontWeight: 700, color: "#111827" }}>When to use these</div>
                <div style={{ fontSize: "13px", color: "#64748b", lineHeight: 1.7 }}>
                  `Focus topics` are the normal option. `Boosted topics` are only for themes you want to heavily prioritize. `Blocked topics`
                  are a cleanup tool for later, once you already know what noise you want to suppress.
                </div>
              </div>
            </div>
          ) : null}
        </SectionCard>

        <SectionCard title="Signal Rules">
          <div style={sectionIntroStyle}>
            These numbers control how strict the intake should be. Scores are percent-like thresholds from 0 to 100.
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, minmax(0, 1fr))", gap: "12px" }}>
            <div style={{ display: "grid", gap: "8px" }}>
              <div style={fieldTitleStyle}>Minimum score</div>
              <div style={fieldHelpStyle}>Signals below this score are filtered out of the auto feed.</div>
              <input value={minScore} onChange={(event) => setMinScore(event.target.value)} placeholder="Min score" style={inputStyle} />
            </div>
            <div style={{ display: "grid", gap: "8px" }}>
              <div style={fieldTitleStyle}>Auto analyze score</div>
              <div style={fieldHelpStyle}>Signals at or above this score are marked as auto-analyze candidates.</div>
              <input value={autoAnalyzeScore} onChange={(event) => setAutoAnalyzeScore(event.target.value)} placeholder="Auto analyze score" style={inputStyle} />
            </div>
            <div style={{ display: "grid", gap: "8px" }}>
              <div style={fieldTitleStyle}>Auto backlog score</div>
              <div style={fieldHelpStyle}>Signals at or above this score can be recommended for backlog review.</div>
              <input value={autoBacklogScore} onChange={(event) => setAutoBacklogScore(event.target.value)} placeholder="Auto backlog score" style={inputStyle} />
            </div>
            <div style={{ display: "grid", gap: "8px" }}>
              <div style={fieldTitleStyle}>Max signals per day</div>
              <div style={fieldHelpStyle}>Soft cap for how many signals should survive the daily intake.</div>
              <input value={maxSignalsPerDay} onChange={(event) => setMaxSignalsPerDay(event.target.value)} placeholder="Max signals per day" style={inputStyle} />
            </div>
          </div>
        </SectionCard>

        <SectionCard title="Project-linked Intake">
          <div style={{ display: "grid", gap: "12px" }}>
            <div style={{ fontSize: "14px", color: "#64748b", lineHeight: 1.7 }}>
              Decide which current projects should influence signal intake. Each enabled project can contribute its own
              topic keywords for future ranking and matching.
            </div>
            {mergedProjectLinks.length === 0 ? (
              <div style={emptyStateStyle}>No projects available yet. Add projects in Project Intake first.</div>
            ) : (
              mergedProjectLinks.map((link) => {
                const project = projects.find((item) => item.project_id === link.project_id);
                return (
                  <div key={link.project_id} style={subPanelStyle}>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: "12px", alignItems: "center" }}>
                      <div>
                        <div style={{ fontSize: "16px", fontWeight: 700, color: "#111827" }}>
                          {project?.name || link.project_id}
                        </div>
                        <div style={{ fontSize: "12px", color: "#6b7280", marginTop: "4px" }}>{link.project_id}</div>
                      </div>
                      <label style={checkboxLabelStyle}>
                        <input
                          type="checkbox"
                          checked={link.enabled}
                          onChange={(event) => upsertProjectLink(link.project_id, { enabled: event.target.checked })}
                        />
                        Include in intake
                      </label>
                    </div>
                    <textarea
                      value={toComma(link.topic_keywords)}
                      onChange={(event) => upsertProjectLink(link.project_id, { topic_keywords: toArray(event.target.value) })}
                      placeholder="Project-specific topic keywords, comma separated"
                      style={{ ...textAreaStyle, marginTop: "10px" }}
                    />
                  </div>
                );
              })
            )}
          </div>
        </SectionCard>

        <div style={{ marginTop: "18px", display: "flex", gap: "12px", flexWrap: "wrap", alignItems: "center" }}>
          <button onClick={() => void handleSave()} disabled={saving || loading} style={buttonStyle("#111827", "#ffffff")}>
            {saving ? "Saving..." : "Save Subscription Settings"}
          </button>
          {message && !saveSuccess ? <span style={successTextStyle}>{message}</span> : null}
          {errorMessage ? <span style={errorTextStyle}>{errorMessage}</span> : null}
        </div>
        {saveSuccess ? (
          <div style={saveSuccessBannerStyle}>
            <div style={{ fontSize: "15px", fontWeight: 800, color: "#166534" }}>Subscription settings saved</div>
            <div style={{ fontSize: "14px", color: "#166534", lineHeight: 1.7 }}>
              {message ||
                "New sources were added to My Subscriptions, and this intake area has been cleared so you can start the next batch cleanly."}
            </div>
            <div>
              <Link href="/admin/subscriptions/library" style={buttonStyle("#ffffff", "#166534", "#86efac")}>
                Go to My Subscriptions
              </Link>
            </div>
          </div>
        ) : null}

        {presetPicker ? (
          <div style={modalOverlayStyle}>
            <div style={modalCardStyle}>
              <div style={{ display: "grid", gap: "8px" }}>
                <div style={{ fontSize: "22px", fontWeight: 800, color: "#111827" }}>
                  Choose Sources to Subscribe
                </div>
                <div style={{ fontSize: "14px", color: "#64748b", lineHeight: 1.7 }}>
                  Pick the sources you want to add from this direction bundle. You can change the selection before adding them to your Source Library.
                </div>
              </div>
              <div style={{ display: "grid", gap: "10px", marginTop: "12px" }}>
                <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
                  <button onClick={selectAllPresetSources} style={buttonStyle("#ffffff", "#111827", "#d1d5db")}>
                    Select All
                  </button>
                  <button onClick={clearAllPresetSources} style={buttonStyle("#ffffff", "#111827", "#d1d5db")}>
                    Clear All
                  </button>
                </div>
                {(SOURCE_PRESET_GROUPS.find((item) => item.key === presetPicker.groupKey)?.sources || []).map((source) => {
                  const checked = presetPicker.selectedUrls.includes(source.url);
                  const normalizedUrl = normalizeSourceUrl(source.url);
                  const isAlreadySubscribed = savedSourceUrls.has(normalizedUrl);
                  const isAlreadyStaged = stagedSourceUrls.has(normalizedUrl);
                  const isLocked = isAlreadySubscribed || isAlreadyStaged;
                  return (
                    <label key={source.url} style={presetSelectionCardStyle}>
                      <div style={{ display: "flex", gap: "10px", alignItems: "flex-start" }}>
                        <input
                          type="checkbox"
                          checked={checked}
                          disabled={isLocked}
                          onChange={() => togglePresetUrl(source.url)}
                          style={{ marginTop: "3px" }}
                        />
                        <div style={{ display: "grid", gap: "4px" }}>
                          <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", alignItems: "center" }}>
                            <div style={{ fontSize: "15px", fontWeight: 700, color: "#111827" }}>{source.name}</div>
                            {isAlreadySubscribed ? (
                              <span style={alreadySubscribedBadgeStyle}>Already in My Subscriptions</span>
                            ) : null}
                            {!isAlreadySubscribed && isAlreadyStaged ? (
                              <span style={alreadySubscribedBadgeStyle}>Already staged</span>
                            ) : null}
                          </div>
                          <div style={{ fontSize: "13px", color: "#6b7280" }}>
                            {source.type} · {source.priority}
                          </div>
                          <div style={{ fontSize: "13px", color: "#475569", lineHeight: 1.6 }}>{source.url}</div>
                          <div style={{ fontSize: "12px", color: "#64748b" }}>{source.tags.join(", ")}</div>
                        </div>
                      </div>
                    </label>
                  );
                })}
              </div>
              <div style={{ display: "flex", gap: "10px", flexWrap: "wrap", marginTop: "18px" }}>
                <button onClick={confirmPresetSelection} style={buttonStyle("#111827", "#ffffff")}>
                  Add Selected Sources
                </button>
                <button onClick={() => setPresetPicker(null)} style={buttonStyle("#ffffff", "#111827", "#d1d5db")}>
                  Cancel
                </button>
              </div>
            </div>
          </div>
        ) : null}
      </RequireAdminAuth>
    </AppContainer>
  );
}

const toolbarRowStyle = {
  marginBottom: "20px",
  display: "flex",
  gap: "12px",
  flexWrap: "wrap" as const,
  alignItems: "center",
} as const;

const toolbarPrimaryLinkStyle = {
  textDecoration: "none",
  color: "var(--app-secondary-action-fg)",
  fontSize: "14px",
  fontWeight: 700,
  border: "1px solid var(--app-secondary-action-border)",
  borderRadius: "8px",
  padding: "10px 14px",
  background: "var(--app-secondary-action-bg)",
} as const;

const toolbarSecondaryLinkStyle = {
  ...toolbarPrimaryLinkStyle,
  textDecoration: "none",
} as const;

const formGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
  gap: "12px",
} as const;

const subPanelStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  padding: "14px",
} as const;

const emptyStateStyle = {
  border: "1px dashed var(--app-surface-border)",
  borderRadius: "8px",
  padding: "16px",
  color: "var(--app-text-muted)",
  background: "var(--app-surface-muted-bg)",
  fontSize: "14px",
} as const;

const inputStyle = {
  border: "1px solid var(--app-input-border)",
  borderRadius: "10px",
  padding: "12px 14px",
  fontSize: "14px",
  color: "var(--app-input-fg)",
  background: "var(--app-input-bg)",
} as const;

const textAreaStyle = {
  ...inputStyle,
  minHeight: "120px",
  resize: "vertical" as const,
  lineHeight: 1.7,
} as const;

const checkboxLabelStyle = {
  display: "inline-flex",
  alignItems: "center",
  gap: "8px",
  fontSize: "13px",
  color: "var(--app-text-muted)",
  fontWeight: 600,
} as const;

const successTextStyle = {
  fontSize: "13px",
  color: "var(--app-success-fg)",
  fontWeight: 600,
} as const;

const saveSuccessBannerStyle = {
  marginTop: "14px",
  border: "1px solid var(--app-success-border)",
  borderRadius: "8px",
  background: "var(--app-success-bg)",
  padding: "14px 16px",
  display: "grid",
  gap: "6px",
} as const;

const savedSummaryHintStyle = {
  border: "1px solid var(--app-success-border)",
  borderRadius: "8px",
  background: "var(--app-success-bg)",
  padding: "12px 14px",
  fontSize: "13px",
  color: "var(--app-success-fg)",
  lineHeight: 1.7,
} as const;

const runtimeStatusPanelStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  padding: "14px 16px",
  display: "grid",
  gap: "12px",
} as const;

const runtimeStatusGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(4, minmax(0, 1fr))",
  gap: "10px",
} as const;

const runtimeStatusItemStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-bg)",
  padding: "12px",
  display: "grid",
  gap: "4px",
} as const;

const runtimeStatusLabelStyle = {
  fontSize: "12px",
  color: "var(--app-text-muted)",
  fontWeight: 700,
} as const;

const runtimeStatusValueStyle = {
  fontSize: "14px",
  color: "var(--app-text-strong)",
  fontWeight: 700,
  lineHeight: 1.5,
  wordBreak: "break-word" as const,
} as const;

const runtimeStatusPathStyle = {
  fontSize: "12px",
  color: "var(--app-text-subtle)",
  lineHeight: 1.7,
  wordBreak: "break-all" as const,
} as const;

const bundleCountBadgeStyle = {
  display: "inline-flex",
  alignItems: "center",
  padding: "4px 10px",
  borderRadius: "999px",
  background: "var(--app-info-bg)",
  border: "1px solid var(--app-info-border)",
  fontSize: "12px",
  color: "var(--app-info-fg)",
  fontWeight: 700,
} as const;

const bundleMutedNoteStyle = {
  fontSize: "12px",
  color: "var(--app-text-muted)",
  lineHeight: 1.6,
} as const;

const savedSourceCardStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-bg)",
  padding: "14px",
  display: "grid",
  gap: "10px",
} as const;

const savedBadgeStyle = {
  display: "inline-flex",
  alignItems: "center",
  padding: "4px 10px",
  borderRadius: "999px",
  background: "var(--app-chip-bg)",
  border: "1px solid var(--app-chip-border)",
  fontSize: "12px",
  color: "var(--app-chip-fg)",
  fontWeight: 600,
} as const;

const alreadySubscribedBadgeStyle = {
  display: "inline-flex",
  alignItems: "center",
  padding: "4px 10px",
  borderRadius: "999px",
  background: "#eff6ff",
  border: "1px solid #bfdbfe",
  fontSize: "12px",
  color: "#1d4ed8",
  fontWeight: 700,
} as const;

const assistantPanelStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  padding: "16px",
  background: "var(--app-surface-bg)",
  display: "grid",
  gap: "14px",
} as const;

const assistantResultStyle = {
  border: "1px solid #e5e7eb",
  borderRadius: "16px",
  padding: "14px",
  background: "#f8fafc",
  display: "grid",
  gap: "12px",
} as const;

const assistantLabelStyle = {
  fontSize: "12px",
  fontWeight: 700,
  color: "#6b7280",
  textTransform: "uppercase" as const,
  letterSpacing: "0.04em",
  marginBottom: "4px",
} as const;

const assistantValueStyle = {
  fontSize: "14px",
  color: "#111827",
  fontWeight: 600,
} as const;

const candidateCardStyle = {
  border: "1px solid #dbe3f0",
  borderRadius: "14px",
  padding: "12px",
  background: "#ffffff",
  display: "grid",
  gap: "10px",
} as const;

const sectionIntroStyle = {
  fontSize: "14px",
  color: "#64748b",
  lineHeight: 1.7,
  marginBottom: "12px",
} as const;

const fieldTitleStyle = {
  fontSize: "13px",
  fontWeight: 700,
  color: "#111827",
} as const;

const fieldHelpStyle = {
  fontSize: "12px",
  color: "#6b7280",
  lineHeight: 1.6,
} as const;

const assistantInlineErrorStyle = {
  border: "1px solid #fecaca",
  borderRadius: "10px",
  background: "#fef2f2",
  color: "#991b1b",
  fontSize: "13px",
  fontWeight: 700,
  padding: "10px 12px",
} as const;

const sourceHealthPanelStyle = {
  border: "1px solid #bfdbfe",
  borderRadius: "14px",
  background: "#eff6ff",
  padding: "14px",
  display: "grid",
  gap: "12px",
} as const;

const sourceHealthIssueStyle = {
  border: "1px solid #e5e7eb",
  borderRadius: "10px",
  background: "#ffffff",
  padding: "10px 12px",
  display: "grid",
  gap: "4px",
  fontSize: "13px",
} as const;

const advancedHintCardStyle = {
  border: "1px solid #e5e7eb",
  borderRadius: "14px",
  background: "#fafafa",
  padding: "14px",
  display: "grid",
  gap: "8px",
} as const;

const presetGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
  gap: "12px",
} as const;

const presetCardStyle = {
  border: "1px solid var(--app-surface-border)",
  borderRadius: "8px",
  background: "var(--app-surface-muted-bg)",
  padding: "14px",
  display: "grid",
  gap: "12px",
} as const;

const modalOverlayStyle = {
  position: "fixed",
  inset: 0,
  background: "rgba(15, 23, 42, 0.42)",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  padding: "24px",
  zIndex: 1000,
} as const;

const modalCardStyle = {
  width: "min(760px, 100%)",
  maxHeight: "85vh",
  overflowY: "auto" as const,
  borderRadius: "24px",
  background: "#ffffff",
  border: "1px solid #e5e7eb",
  padding: "22px",
  boxShadow: "0 24px 60px rgba(15, 23, 42, 0.18)",
} as const;

const presetSelectionCardStyle = {
  border: "1px solid #e5e7eb",
  borderRadius: "16px",
  background: "#fafafa",
  padding: "14px",
  cursor: "pointer",
} as const;

function _guessSourceName(url: string) {
  try {
    const host = new URL(url).hostname.replace(/^www\./, "");
    const root = host.split(".")[0]?.replace(/[-_]/g, " ").trim();
    return root ? root.replace(/\b\w/g, (char) => char.toUpperCase()) : "New Source";
  } catch {
    return "New Source";
  }
}

const errorTextStyle = {
  fontSize: "13px",
  color: "#b91c1c",
  fontWeight: 600,
} as const;

function sourceHealthBadgeStyle(background: string, color: string) {
  return {
    display: "inline-flex",
    alignItems: "center",
    minHeight: "28px",
    borderRadius: "999px",
    background,
    color,
    padding: "4px 10px",
    fontSize: "12px",
    fontWeight: 800,
  } as const;
}

function buttonStyle(background: string, color: string, borderColor = background) {
  return {
    padding: "10px 14px",
    borderRadius: "10px",
    border: `1px solid ${borderColor}`,
    background,
    color,
    cursor: "pointer",
    fontWeight: 700,
    textDecoration: "none",
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
  } as const;
}
