import json
from app.intelligence.llm_executor import execute_routed_task
from app.models import Insight
from app.prompts.registry import personalized_radar_insight_prompts


def generate_insight(signal, personal_context):

    signal_dict = signal.to_dict()

    system_prompt, user_prompt = personalized_radar_insight_prompts(
        personal_context=personal_context,
        signal_payload=signal_dict,
    )

    result = execute_routed_task(
        task_type="structure",
        temperature=0.7,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        json_mode=True,
    )

    parsed = result.parsed_json or json.loads(result.raw_text)

    return Insight(
        signal_title=signal.title,
        signal_summary=signal.summary,
        why_it_matters=parsed.get("why_it_matters", ""),
        relevance_to_projects=parsed.get("relevance_to_projects", ""),
        relevance_to_career=parsed.get("relevance_to_career", ""),
        synthesized_insight=parsed.get("synthesized_insight", ""),
    )
