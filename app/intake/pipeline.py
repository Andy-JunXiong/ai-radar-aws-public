import json
from pathlib import Path

from intake.analyze import analyze_signal
from intake.processors.cleaner import build_short_summary, clean_text
from intake.scoring.scorer import score_signal
from intake.selector.selector import select_top_signals
from intake.sources.openai_blog_source import collect_openai_blog_signals


BASE_DIR = Path(__file__).resolve().parent.parent.parent
OUTPUT_DIR = BASE_DIR / "output"
RAW_DIR = OUTPUT_DIR / "raw"
CLEAN_DIR = OUTPUT_DIR / "clean"
CURATED_DIR = OUTPUT_DIR / "curated"
CONTEXT_FILE = BASE_DIR / "app" / "context" / "personal_context.json"


def ensure_output_dirs() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    CURATED_DIR.mkdir(parents=True, exist_ok=True)


def write_json(filepath: Path, data: list[dict]) -> None:
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def build_analysis_input(signal, threshold: float = 0.5) -> str:
    # 如果 clean_text 本来就不长，直接用 clean_text
    if len(signal.clean_text) <= 300:
        return signal.clean_text

    # 长文本再按分数决定
    if signal.scores.total >= threshold:
        return signal.clean_text

    return signal.summary

def run_pipeline_on_signals(signals: list) -> list:
    personal_context = load_personal_context()

    cleaned_signals = []
    for signal in signals:
        signal.clean_text = clean_text(signal.raw_text)
        signal.summary = build_short_summary(signal.clean_text, max_chars=100)
        cleaned_signals.append(signal)

    scored_signals = []
    for signal in cleaned_signals:
        scored = score_signal(signal)
        scored.analysis_input = build_analysis_input(scored, threshold=0.5)
        scored.why_it_matters_to_me = build_why_it_matters(scored, personal_context)
        scored_signals.append(scored)

    curated_signals = select_top_signals(
        scored_signals,
        top_n=min(5, len(scored_signals))
    )

    return curated_signals

def build_why_it_matters(signal, personal_context: dict) -> str:
    text = f"{signal.title} {signal.clean_text}".lower()

    reasons = []

    if "agent" in text:
        reasons.append("it relates to agent design, which is central to your AI systems work")

    if "architecture" in text or "system" in text:
        reasons.append("it is relevant to system architecture, especially for AI Radar and GLAP")

    if "signal" in text or "input" in text:
        reasons.append("it can improve your signal intake and ranking pipeline in AI Radar")

    if "decision" in text:
        reasons.append("it may inform decision-making logic in your GLAP system")

    if "memory" in text or "reasoning" in text:
        reasons.append("it connects to reasoning and memory design, relevant to AI Cognitive")

    if "monitoring" in text or "evaluation" in text:
        reasons.append("it relates to evaluation and monitoring, which are critical for production AI systems")

    if "developer" in text or "coding" in text:
        reasons.append("it is relevant to developer tools and practical AI system usage")

    if not reasons:
        return "This signal is a general AI update with limited direct relevance to your current systems."

    return "This signal matters because " + "; ".join(reasons) + "."

def run_pipeline_on_signals(signals: list) -> list:
    personal_context = load_personal_context()

    # Step 1: clean
    cleaned_signals = []
    for signal in signals:
        signal.clean_text = clean_text(signal.raw_text)
        signal.summary = build_short_summary(signal.clean_text, max_chars=100)
        cleaned_signals.append(signal)

    # Step 2: score + personalization
    scored_signals = []
    for signal in cleaned_signals:
        scored = score_signal(signal)
        scored.analysis_input = build_analysis_input(scored, threshold=0.5)
        scored.why_it_matters_to_me = build_why_it_matters(scored, personal_context)
        scored_signals.append(scored)

    # Step 3: select
    curated_signals = select_top_signals(scored_signals, top_n=min(5, len(scored_signals)))

    # Step 4: optional analyze
    for signal in curated_signals:
        try:
            analysis = analyze_signal(signal)
            # 如果 analyze_signal 返回字符串，可以先挂到 signal 上备用
            setattr(signal, "ai_analysis", analysis)
        except Exception as e:
            setattr(signal, "ai_analysis", f"AI ANALYSIS ERROR: {e}")

    return curated_signals

def load_personal_context() -> dict:
    if not CONTEXT_FILE.exists():
        return {
            "background": "",
            "projects": [],
            "focus_areas": [],
            "career_goals": [],
        }

    with open(CONTEXT_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def run_intake_pipeline() -> None:
    ensure_output_dirs()
    personal_context = load_personal_context()

    # Step 1: collect raw signals
    raw_signals = collect_openai_blog_signals(limit=5)
    write_json(
        RAW_DIR / "raw_signals.json",
        [signal.to_dict() for signal in raw_signals],
    )

    # Step 2: clean
    cleaned_signals = []
    for signal in raw_signals:
        signal.clean_text = clean_text(signal.raw_text)
        signal.summary = build_short_summary(signal.clean_text, max_chars=100)

        print("TITLE:", signal.title)
        print("RAW LEN:", len(signal.raw_text))
        print("CLEAN LEN:", len(signal.clean_text))
        print("SUMMARY LEN:", len(signal.summary))
        print("SUMMARY VALUE:", signal.summary)
        print("-" * 50)

        cleaned_signals.append(signal)

    write_json(
        CLEAN_DIR / "clean_signals.json",
        [signal.to_dict() for signal in cleaned_signals],
    )

    # Step 3: score + personalization
    scored_signals = []
    for signal in cleaned_signals:
        scored = score_signal(signal)
        scored.analysis_input = build_analysis_input(scored, threshold=0.5)
        scored.why_it_matters_to_me = build_why_it_matters(scored, personal_context)

        print("TITLE:", scored.title)
        print("TOTAL SCORE:", scored.scores.total)
        print("PERSONAL FIT:", scored.scores.personal_fit)
        print(
            "ANALYSIS INPUT TYPE:",
            "clean_text" if scored.analysis_input == scored.clean_text else "summary",
        )
        print("WHY IT MATTERS:", scored.why_it_matters_to_me)
        print("-" * 50)

        scored_signals.append(scored)

    # Step 4: select
    curated_signals = select_top_signals(scored_signals, top_n=5)
    print("\n=== AI ANALYSIS (Top 3) ===")

    for signal in curated_signals[:3]:
        try:
            analysis = analyze_signal(signal)
            print("TITLE:", signal.title)
            print("AI ANALYSIS:")
            print(analysis)
            print("-" * 80)
        except Exception as e:
            print("TITLE:", signal.title)
            print(f"AI ANALYSIS ERROR: {e}")
            print("-" * 80)
    write_json(
        CURATED_DIR / "latest_signals.json",
        [signal.to_dict() for signal in curated_signals],
    )

    print("Intake pipeline completed successfully.")
    print(f"Raw signals: {len(raw_signals)}")
    print(f"Curated signals: {len(curated_signals)}")


if __name__ == "__main__":
    run_intake_pipeline()
