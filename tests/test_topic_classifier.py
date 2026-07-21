import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.intelligence.topic_classifier import attach_topic_to_signal, classify_topic


def test_openai_economic_labor_signal_is_not_classified_as_model():
    text = (
        "OpenAI Economic Research Exchange will fund studies on labor market "
        "impacts, workforce productivity, jobs, and wages before regulation."
    )

    assert classify_topic(text) == "AI Economics & Labor"


def test_provider_name_alone_does_not_override_business_topic():
    text = "OpenAI announces startup investment, enterprise revenue, and market expansion."

    assert classify_topic(text) == "AI Business"


def test_model_specific_terms_still_classify_as_models():
    text = "OpenAI releases a GPT reasoning model with a larger context window."

    assert classify_topic(text) == "AI Models"


def test_attach_topic_to_signal_uses_title_summary_and_content():
    signal = {
        "title": "Economic Research Exchange",
        "summary": "A research program about AI workforce and employment impacts.",
        "content": "The source discusses productivity and labor market evidence.",
    }

    enriched = attach_topic_to_signal(signal)

    assert enriched["topic"] == "AI Economics & Labor"
    assert "topic" not in signal
