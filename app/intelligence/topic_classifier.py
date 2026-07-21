from typing import Dict, List


TOPIC_KEYWORDS: Dict[str, List[str]] = {
    "AI Policy": [
        "policy",
        "regulation",
        "government",
        "compliance",
        "safety",
        "governance",
        "law",
        "risk",
        "standard",
        "eu ai act",
        "copyright",
        "licensing",
    ],
    "AI Hardware": [
        "chip",
        "semiconductor",
        "hardware",
        "accelerator",
        "npu",
        "gpu architecture",
        "blackwell",
        "h200",
        "h100",
        "device ai",
        "edge device",
    ],
    "AI Infrastructure": [
        "gpu",
        "inference",
        "training",
        "compute",
        "latency",
        "serving",
        "deployment",
        "infrastructure",
        "cluster",
        "cuda",
        "vector database",
        "vector db",
        "embedding infrastructure",
        "cloud",
        "aws",
        "azure",
        "gcp",
        "runtime",
        "orchestration",
    ],
    "AI Agents": [
        "agent",
        "agents",
        "agentic",
        "autonomous agent",
        "multi-agent",
        "workflow agent",
        "langgraph",
        "autogpt",
        "operator",
        "tool use",
        "planning",
        "task execution",
        "memory system",
    ],
    "AI Economics & Labor": [
        "economic impact",
        "economics",
        "labor",
        "labour",
        "workforce",
        "employment",
        "jobs",
        "job market",
        "wages",
        "productivity",
        "worker",
        "workers",
        "labor market",
        "labour market",
        "future of work",
        "automation impact",
    ],
    "AI Models": [
        "gpt",
        "llm",
        "large language model",
        "foundation model",
        "multimodal",
        "model release",
        "gemini",
        "claude",
        "mistral",
        "reasoning model",
        "context window",
        "token",
    ],
    "AI Products": [
        "product",
        "launch",
        "release",
        "feature",
        "rollout",
        "app",
        "assistant",
        "platform",
        "copilot",
        "workspace",
        "integration",
        "enterprise ai",
        "developer tool",
        "user adoption",
    ],
    "AI Research": [
        "paper",
        "research",
        "arxiv",
        "benchmark",
        "evaluation",
        "experiment",
        "study",
        "method",
        "dataset",
        "leaderboard",
        "scientific",
    ],
    "AI Business": [
        "funding",
        "revenue",
        "pricing",
        "market",
        "startup",
        "enterprise",
        "business",
        "investment",
        "valuation",
        "monetization",
        "sales",
        "profit",
    ],
}


TOPIC_PRIORITY: List[str] = [
    "AI Economics & Labor",
    "AI Policy",
    "AI Hardware",
    "AI Infrastructure",
    "AI Agents",
    "AI Models",
    "AI Products",
    "AI Research",
    "AI Business",
]


def normalize_text(text: str) -> str:
    """
    Normalize input text for keyword matching.
    """
    if not text:
        return ""
    return text.strip().lower()


def classify_topic(text: str) -> str:
    """
    Classify topic based on keyword rules.
    Returns the first matched topic by priority order,
    otherwise 'General AI'.
    """
    normalized = normalize_text(text)

    for topic in TOPIC_PRIORITY:
        keywords = TOPIC_KEYWORDS.get(topic, [])
        for keyword in keywords:
            if keyword in normalized:
                return topic

    return "General AI"


def attach_topic_to_signal(signal: dict) -> dict:
    """
    Add a 'topic' field to one signal.
    Expected signal keys may include:
    - title
    - summary
    - content
    - source
    """
    title = signal.get("title", "")
    summary = signal.get("summary", "")
    content = signal.get("content", "")

    combined_text = f"{title} {summary} {content}"
    topic = classify_topic(combined_text)

    enriched_signal = dict(signal)
    enriched_signal["topic"] = topic
    return enriched_signal


def attach_topics_to_signals(signals: list[dict]) -> list[dict]:
    """
    Add topic to all signals.
    """
    if not signals:
        return []

    return [attach_topic_to_signal(signal) for signal in signals]
