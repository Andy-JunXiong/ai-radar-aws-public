from intake.schemas import Signal, SignalScore

KEYWORDS = [
    "agent",
    "memory",
    "ai system",
    "architecture",
    "decision",
    "signal",
    "input",
    "quality",
    "rag",
    "reasoning",
]


def compute_relevance_score(signal: Signal) -> float:
    text = f"{signal.title} {signal.clean_text}".lower()
    matches = sum(1 for keyword in KEYWORDS if keyword in text)
    return min(matches / 5, 1.0)


def compute_quality_score(signal: Signal) -> float:
    text_len = len(signal.clean_text.strip())

    if text_len >= 400:
        return 1.0
    if text_len >= 250:
        return 0.8
    if text_len >= 120:
        return 0.6
    if text_len >= 60:
        return 0.4
    return 0.2

PERSONAL_KEYWORDS = [
    "agent",
    "ai system",
    "architecture",
    "memory",
    "reasoning",
    "signal",
    "input",
    "decision",
    "multimodal",
    "tool use",
    "coding",
    "monitoring",
    "evaluation",
    "deployment",
    "workflow",
    "orchestration",
    "developer",
]

def compute_personal_fit_score(signal: Signal) -> float:
    text = f"{signal.title} {signal.clean_text}".lower()
    matches = sum(1 for keyword in PERSONAL_KEYWORDS if keyword in text)
    return min(matches / 5, 1.0)

def score_signal(signal: Signal) -> Signal:
    relevance = compute_relevance_score(signal)
    quality = compute_quality_score(signal)
    personal_fit = compute_personal_fit_score(signal)

    total = round(0.5 * relevance + 0.2 * quality + 0.3 * personal_fit, 4)

    signal.scores = SignalScore(
        relevance=round(relevance, 4),
        quality=round(quality, 4),
        personal_fit=round(personal_fit, 4),
        total=total,
    )
    return signal