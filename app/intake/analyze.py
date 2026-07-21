from pathlib import Path

from dotenv import load_dotenv

from app.intelligence.llm_executor import execute_routed_task
from app.prompts.registry import intake_signal_analysis_prompt


BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")


def analyze_signal(signal) -> str:
    prompt = intake_signal_analysis_prompt(
        title=signal.title,
        analysis_input=signal.analysis_input,
        why_it_matters_to_user=signal.why_it_matters_to_me,
    )

    result = execute_routed_task(
        task_type="extract",
        messages=[
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,
    )

    return result.raw_text.strip()
