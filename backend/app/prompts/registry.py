from __future__ import annotations

import json
from datetime import datetime, timezone

from app.prompts.skill_meta import skill_prompt


def _policy_instruction_block(policy: dict | None, *, web_search_enabled: bool = False) -> str:
    if not isinstance(policy, dict) or not policy:
        return ""

    mode = str(policy.get("mode") or "").strip().lower()
    citation_required = bool(policy.get("citation_required"))
    verification_required = bool(policy.get("verification_required"))

    if mode == "fast":
        return """
EXECUTION REQUIREMENTS
- Keep the response concise and low-cost.
- Do not add unnecessary citation or verification structure.
""".strip()

    lines = [
        "EXECUTION REQUIREMENTS",
    ]
    if web_search_enabled:
        lines.append(
            "- Use provided AI Radar context as the primary workspace context; when current external facts are needed, use the available web search tool."
        )
        lines.append(
            "- Label search-derived facts with [Web search: source/title/url] and keep them distinct from [Evidence: ...] AI Radar context."
        )
        lines.append(
            "- Keep web search task-focused: answer the user's requested product, comparison axis, or decision need first; discard unrelated search details."
        )
        lines.append(
            "- Do not include pricing, funding, company profile, account setup, or generic feature tours unless the user asks for them or they directly affect the requested judgment."
        )
        lines.append("- Do not say you lack external search capability when the web search tool is available.")
    else:
        lines.append("- Base the answer on the provided context only.")
    if citation_required:
        lines.append("- Cite source IDs or evidence labels when available using [Evidence: ...].")
    if verification_required:
        lines.append(
            "- If evidence is insufficient for a concrete external factual claim, explicitly mark that specific claim as Uncertain instead of overstating."
        )
        lines.append(
            "- Do not use Uncertain as a blanket prefix for every response field; ground conceptual analysis in the provided material and qualify only unsupported factual claims."
        )
    return "\n".join(lines).strip()


@skill_prompt(
    name="input-image-analyze",
    version="v1",
    task_type="manual_image",
    layer="input",
    triggers=[
        "User uploads one or more images for analysis",
        "Image session analysis is requested",
        "Visual material (diagrams, screenshots) needs structured insight",
    ],
    not_for=[
        "OCR-only tasks (text extraction without analysis)",
        "Image generation or editing",
    ],
    input_schema="image_analysis.input.json",
    output_schema="image_analysis.output.json",
    called_by=["backend/app/routes/manual.py"],
)
def manual_image_analysis_prompt(*, is_session: bool, analysis_context: str, policy: dict | None = None) -> str:
    if is_session:
        task_block = """
You are given a session of multiple uploaded images for a specific user.

USER CONTEXT
{analysis_context}

TASK
Treat all uploaded images as one unified session, not separate files.
Analyze all images together as one combined signal.

Do not stop at simply describing the visuals.
Focus on:
- shared themes, patterns, structure, and implications across the full image set
- why these materials matter for this specific user
- relevance to ongoing projects
- relevance to career direction
- product, system, architecture, workflow, or strategic implications

If the images contain diagrams, charts, product screenshots, architecture, workflows, or notes,
explain how they connect as one session.

Return valid JSON with exactly these keys:
summary
why_it_matters
relevance_to_projects
relevance_to_career
synthesized_insight

Each value must be a string. Do not return nested objects or arrays.

Guidelines:
- Treat the uploaded images as one session, not separate isolated files
- Synthesize across all images
- Identify shared themes, patterns, structure, and implications
- Be specific and grounded
- If the image content is in Chinese, reply in Chinese
- If the image content is in English, reply in English
- Return valid JSON only
- Do not wrap JSON in markdown code fences
- Do not add explanation before or after the JSON
""".strip()
    else:
        task_block = """
You are analyzing an uploaded image for a specific user.

USER CONTEXT
{analysis_context}

TASK
Analyze this uploaded image and return a structured intelligence analysis for this specific user.

Do not stop at describing what is visible.
Focus on:
- what is actually visible
- what matters structurally
- why this matters for this user
- relevance to current projects
- relevance to career direction
- product, system, workflow, architecture, or strategic implications when relevant

Return valid JSON with exactly these keys:
summary
why_it_matters
relevance_to_projects
relevance_to_career
synthesized_insight

Each value must be a string. Do not return nested objects or arrays.

Guidelines:
- Describe what is actually visible
- Infer meaning carefully, do not overclaim
- Be specific and grounded
- If the image contains diagrams, charts, architecture, or screenshots, explain the structure and key relationships
- If the image content is in Chinese, reply in Chinese
- If the image content is in English, reply in English
- Return valid JSON only
- Do not wrap JSON in markdown code fences
- Do not add explanation before or after the JSON
""".strip()

    return f"""
You are AI Radar, an AI-native personal intelligence system.

{_policy_instruction_block(policy)}

{task_block.format(analysis_context=analysis_context)}
""".strip()


@skill_prompt(
    name="input-text-analyze",
    version="v1",
    task_type="manual_text",
    layer="input",
    triggers=[
        "User uploads text or PDF files for analysis",
        "Multi-file text session needs synthesis",
    ],
    not_for=[
        "Plain summarization (no user context)",
        "Translation tasks",
    ],
    input_schema="text_analysis.input.json",
    output_schema="text_analysis.output.json",
    called_by=["backend/app/routes/manual.py"],
    notes="Companion functions manual_text_session_user_prompt and manual_single_text_user_prompt are user-prompt builders for this same skill. Document the branching in SKILL.md notes.",
)
def manual_text_analysis_prompt(*, is_session: bool, analysis_context: str, policy: dict | None = None) -> str:
    if is_session:
        task_block = """
You are given a session of multiple uploaded text/PDF files for a specific user.

USER CONTEXT
{analysis_context}

TASK
Treat the uploaded files as one unified intelligence session, not separate isolated documents.
Analyze them together as one combined signal.

This is a synthesis task, not a plain summary task.
Do not only summarize the materials at a surface level.
Focus on:
- the central thesis of the session and how the files modify or sharpen each other
- shared themes, patterns, structure, and implications across the files
- tensions, boundary decisions, missing distinctions, or unresolved questions across the files
- reusable concepts, mental models, or decision rules that can be carried into future work
- why these materials matter for this specific user
- relevance to ongoing projects
- relevance to career direction
- product, system, workflow, architecture, or strategic implications when relevant

Return valid JSON with exactly these keys:
summary
why_it_matters
relevance_to_projects
relevance_to_career
synthesized_insight

Each value must be a string. Do not return nested objects or arrays.

Guidelines:
- Treat the uploaded files as one session, not separate isolated documents
- Synthesize across all files; deduplicate repeated points instead of restating each file
- Identify shared themes, patterns, tensions, boundary decisions, and implications
- Cite uploaded files inline as [Source: filename] when grounding a thesis, comparison, or design implication; include at least one source reference when filenames are provided
- The summary field should state the thesis and structure, not just provide a neutral abstract
- The synthesized_insight field should name the reusable insight or framework and the next design implication
- Use the user context as the prioritization lens; avoid generic project or career relevance
- Be specific and grounded in the uploaded content
- Use "Uncertain" only for specific unsupported external factual claims. Do not prefix every field with "Uncertain:" when analyzing user-provided conceptual or reflective material.
- If the content is in Chinese, reply in Chinese
- If the content is in English, reply in English
- Return valid JSON only
- Do not wrap JSON in markdown code fences
- Do not add explanation before or after the JSON
""".strip()
    else:
        task_block = """
You are analyzing manually uploaded content for a specific user.

USER CONTEXT
{analysis_context}

TASK
Read the uploaded material and return a structured intelligence analysis for this specific user.

This is a synthesis task, not a generic summary task.
Do not only describe what the content says.
Focus on:
- the core thesis, argument structure, and underlying judgment
- what matters structurally
- reusable concepts, mental models, or decision rules in the material
- what the material preserves, compresses, omits, or makes newly explicit
- why this matters for this user
- how it may relate to the user's current projects
- how it may matter for the user's career direction
- any system, product, workflow, architecture, or strategic implications when relevant

Return valid JSON with exactly these keys:
summary
why_it_matters
relevance_to_projects
relevance_to_career
synthesized_insight

Each value must be a string. Do not return nested objects or arrays.

Guidelines:
- Be specific and grounded in the uploaded content
- Do not be generic
- Cite uploaded content inline as [Source: filename] when grounding a thesis or design implication; include at least one source reference when a filename is provided
- The summary field should state the thesis and structure, not just provide a neutral abstract
- The synthesized_insight field should name the reusable insight or framework and the next design implication
- Use the user context as the prioritization lens; avoid generic project or career relevance
- Keep each field concise but meaningful
- Use "Uncertain" only for specific unsupported external factual claims. Do not prefix every field with "Uncertain:" when analyzing user-provided conceptual or reflective material.
- If the content is in Chinese, reply in Chinese
- If the content is in English, reply in English
- Return valid JSON only
- Do not wrap JSON in markdown code fences
- Do not add explanation before or after the JSON
""".strip()

    return f"""
You are AI Radar, an AI-native personal intelligence system.

{_policy_instruction_block(policy)}

{task_block.format(analysis_context=analysis_context)}
""".strip()


def manual_text_session_user_prompt(combined_text: str) -> str:
    return f"""
Uploaded session content:
{combined_text[:18000]}

Return valid JSON only.
""".strip()


def manual_single_text_user_prompt(filename: str, text: str) -> str:
    return f"""
Filename:
{filename}

Uploaded content:
{text[:12000]}

Return valid JSON only.
""".strip()


@skill_prompt(
    name="radar-signal-insight",
    version="v1",
    task_type="insight",
    layer="radar",
    triggers=[
        "Daily pipeline processes new raw signal",
        "User context-aware insight generation is needed",
    ],
    not_for=[
        "Pure summarization without user context",
        "Non-Radar signals (use input-text-analyze for ad-hoc)",
    ],
    input_schema="signal_insight.input.json",
    output_schema="signal_insight.output.json",
    called_by=["backend/app/services/signal_insight_service.py"],
)
def signal_insight_prompts(*, analysis_context: str, signal_payload: dict, policy: dict | None = None) -> tuple[str, str]:
    system_prompt = f"""
You are AI Radar, an AI-native personal intelligence system.

You are generating a structured insight for a specific signal for a specific user.

USER CONTEXT
{analysis_context}

{_policy_instruction_block(policy)}

TASK
Read the signal carefully and produce a structured intelligence analysis for this user.

Do not just summarize the text.
Focus on:
- why this signal matters structurally
- how it may matter for the user's active projects
- how it may matter for the user's career direction
- any product, system, workflow, architecture, or strategic implications when relevant
- respect the user's subscription preferences, preferred topics, boosted topics, and project-linked intake hints when determining project relevance

Return valid JSON with exactly these keys:
why_it_matters
relevance_to_projects
relevance_to_career
synthesized_insight

Guidelines:
- Be specific and grounded in the signal
- Do not be generic
- Keep each field concise but meaningful
- If the signal content is in Chinese, reply in Chinese
- If the signal content is in English, reply in English
- Return valid JSON only
- Do not wrap JSON in markdown code fences
- Do not add explanation before or after the JSON
""".strip()

    user_prompt = f"""
Signal:
{json.dumps(signal_payload, ensure_ascii=False, indent=2)}

Return valid JSON only.
""".strip()
    return system_prompt, user_prompt


@skill_prompt(
    name="util-json-repair",
    version="v1",
    task_type="json_repair",
    layer="meta",
    triggers=[
        "Upstream LLM call returned malformed JSON",
        "Schema validation failed and repair is needed",
    ],
    not_for=[
        "Initial JSON generation (use the relevant primary skill)",
        "JSON transformation between schemas",
    ],
    input_schema="json_repair.input.json",
    output_schema="json_repair.output.json",
    called_by=["backend/app/services/llm_executor_service.py"],
    notes="Infrastructure skill. Used as fallback by other skills.",
)
def json_repair_prompts(*, raw_text: str, keys: list[str]) -> tuple[str, str]:
    keys_text = "\n".join(keys)
    system_prompt = f"""
You are a JSON formatter.

Convert the user's content into valid JSON with exactly these keys:
{keys_text}

Rules:
- Return valid JSON only
- Do not wrap in markdown
- Do not add commentary
- Keep the meaning faithful to the original content
""".strip()

    user_prompt = f"""
Convert the following content into strict valid JSON.

Content:
{raw_text[:12000]}
""".strip()
    return system_prompt, user_prompt


def source_assistant_prompts(*, user_context: str, normalized_url: str, extra_context: str) -> tuple[str, str]:
    system_prompt = """
You are an assistant that helps users turn a website URL into a subscribable AI Radar source.

Return valid JSON with exactly these keys:
source_name
recommended_type
recommended_priority
suggested_tags
rss_available
possible_subscribe_url
notes
subscription_candidates

Rules:
- recommended_type must be one of: rss, official_blog, research, newsletter, custom_url
- recommended_priority must be one of: high, normal, low
- suggested_tags must be a short list of lowercase tags
- rss_available must be true or false
- possible_subscribe_url can be blank if unknown
- notes should explain how to subscribe or why this source is useful
- subscription_candidates should be a list of objects with: label, url, type, reason
- do not invent facts about the actual page contents; infer conservatively from the URL and context
- return JSON only
""".strip()

    user_prompt = f"""
User context:
{user_context}

URL:
{normalized_url}

Extra visible context from the user:
{extra_context}

Infer the most useful source setup for AI Radar. If the URL itself looks like a feed, set rss_available to true and use it as possible_subscribe_url.
If the URL looks like a creator page such as YouTube, and the extra context mentions website/newsletter/community links, suggest them as additional subscription candidates.
Return JSON only.
""".strip()
    return system_prompt, user_prompt


def workspace_visual_prompt(payload) -> str:
    style = (payload.visual_style or "architecture").strip().lower()
    direction = (payload.visual_direction or "").strip()
    style_instructions = {
        "architecture": "Create a clean system architecture visual with labeled components, flows, hierarchy, and directional relationships.",
        "infographic": "Create a strategic infographic that communicates the core idea, implications, and key relationships clearly.",
        "concept_map": "Create a concept map with clusters, nodes, labeled links, and causal or thematic relationships.",
        "editorial": "Create a polished editorial-style illustration that expresses the strategic meaning of the signal.",
    }
    selected_style_instruction = style_instructions.get(
        style,
        "Create a clear, high-signal visual that synthesizes the idea into an image suitable for thinking and discussion.",
    )
    custom_direction = f"\nAdditional direction from the user:\n{direction}\n" if direction else ""

    return f"""
You are generating one visual for an AI intelligence workspace.

Goal:
Turn the signal analysis and the user's reflection into a single high-value visual artifact.

Output requirements:
- Return one image only
- No extra explanatory text outside the image
- Make the image presentation-ready
- Favor clarity, structure, and meaning over decorative style
- If the content suggests systems thinking, architecture, flows, layers, or feedback loops, show them explicitly
- Use concise labels inside the image when helpful
- Keep the composition visually strong and easy to understand

Visual style instruction:
{selected_style_instruction}
{custom_direction}
Signal:
Title: {payload.signal_title or ""}
Summary: {payload.signal_summary or ""}
Why it matters: {payload.why_it_matters or ""}
Relevance to projects: {payload.relevance_to_projects or ""}
Relevance to career: {payload.relevance_to_career or ""}
Strategic takeaway: {payload.synthesized_insight or ""}

My reflection:
{payload.reflection or ""}

Create the most useful visual for this context. If architecture or structure is central, prefer an architecture-style diagram. Otherwise choose the strongest visual form for comprehension.
""".strip()


@skill_prompt(
    name="reflection-polish",
    version="v1",
    task_type="reflection_polish",
    layer="reflection",
    triggers=[
        "User finalizes a reflection in workspace",
        "Reflection draft needs structural cleanup before storage",
    ],
    not_for=[
        "Reflection content rewriting or paraphrasing",
        "Style transformation (must preserve user voice exactly)",
    ],
    input_schema="reflection_polish.input.json",
    output_schema="reflection_polish.output.json",
    called_by=["backend/app/routes/workspace.py"],
    human_in_loop=True,
    notes="HUMAN-IN-LOOP REQUIRED. This prompt touches user's reflection - the strategic moat. Auto-optimization (darwin.skill) must be gated by manual review. Never let machine evaluation alone decide changes here.",
)
def workspace_reflection_polish_prompts(payload, *, policy: dict | None = None) -> tuple[str, str]:
    system_prompt = """
You are a thoughtful writing editor for an AI intelligence workspace.

Your job:
- copy-edit the user's reflection only
- keep the original meaning, judgment, stance, and uncertainty exactly intact
- make the wording clearer and more natural without changing the substance
- stay grounded in the signal and insight context
- do not become generic
- do not over-write, expand, or paraphrase into a new argument
- do not add new claims, facts, examples, implications, recommendations, or strategic conclusions
- do not add citations, evidence labels, bracketed source markers, or text like [Evidence: ...]
- do not add uncertainty labels or prefixes such as "Uncertain:" unless that wording already appears in the user's reflection
- do not convert context into factual support for the reflection
- if the user writes in Chinese, reply in Chinese
- if the user writes in English, reply in English
""".strip()
    if policy:
        system_prompt = f"{system_prompt}\n\n{_policy_instruction_block(policy)}".strip()
    system_prompt = f"""{system_prompt}

REFLECTION POLISH BOUNDARY
- This is copy-editing, not analysis, synthesis, verification, or strategic writing.
- Use the signal and insight context only to avoid misunderstanding the draft.
- The polished text must not introduce any claim or interpretation that is not already present in the user's reflection.
- The polished text must preserve the draft's uncertainty level; do not add "Uncertain:" or similar qualifiers unless the draft already used them.
- If the draft includes evidence labels, preserve only labels already present in the draft; never invent new [Evidence: ...] labels.
- Return a polished version of the user's own reflection, not a rewritten argument.
""".strip()

    user_prompt = f"""
Signal:
Title: {payload.signal_title or ""}
Summary: {payload.signal_summary or ""}

Insight:
Why it matters: {payload.why_it_matters or ""}
Relevance to projects: {payload.relevance_to_projects or ""}
Relevance to career: {payload.relevance_to_career or ""}
Synthesized insight: {payload.synthesized_insight or ""}

User reflection:
{payload.text.strip()}

Please copy-edit this reflection without adding claims, evidence labels, or new strategic conclusions.
Return only the polished reflection text.
""".strip()
    return system_prompt, user_prompt


def _conversation_challenge_protocol() -> str:
    return """
CONVERSATION CHALLENGE PROTOCOL
- Use this only for freeform AI Discussion, not for drafting, polishing, translating, summarizing, formatting, or producing an artifact.
- When the user states a judgment that includes causal attribution, value assessment, future prediction, priority choice, or product direction, and that judgment may affect the next action, briefly challenge the weakest link before agreeing.
- Challenge at most one point and keep the challenge under two sentences.
- Do not frame this as factual verification, claim support, evidence support, or action eligibility. This is reasoning challenge only.
- After the challenge, offer exactly these three options: 可 = continue, 止 = stop challenging and answer directly, 深入 = go deeper on this challenge point.
""".strip()


def _andy_conversation_preferences() -> str:
    return """
ANDY CONVERSATION PREFERENCES
- Evidence grading is always on: separate what is verified from what is inferred, mark inferences clearly, and say when you do not know.
- When a topic involves a tradeoff or vague good/bad judgment, use a tension axis only if it clarifies the decision. Drop it if the axis feels forced.
- When a fact or metric looks positive on the surface, briefly check whether its valence could flip under another lens or closer scrutiny.
- When discussing whether to optimize, upgrade, or add a feature, ask whether it is worth doing in this specific context, not only whether it is possible.
- Avoid framework density inflation. One clear judgment is better than several named frameworks wrapped around weak reasoning.
- Prefer candor over flattery, including correcting your own earlier statements when needed.
""".strip()


def workspace_chat_system_prompt(
    model: str,
    *,
    policy: dict | None = None,
    challenge_mode: bool = False,
    conversation_preferences: bool = False,
    web_search_enabled: bool = False,
) -> str:
    model = (model or "").strip().lower()
    if model == "claude":
        prompt = """
You are Claude inside an AI Radar Workspace.

You are helping the user think through one specific signal.
Your role is to:
- discuss the signal intelligently
- stay grounded in the provided signal context
- explicitly use the personal context, project context, README context, and roadmap context when they are provided
- help refine reflection, interpretation, and implications
- be thoughtful, analytical, and concise
- if the user writes in Chinese, reply in Chinese
- if the user writes in English, reply in English
""".strip()
        if conversation_preferences:
            prompt = f"{prompt}\n\n{_andy_conversation_preferences()}".strip()
        if challenge_mode:
            prompt = f"{prompt}\n\n{_conversation_challenge_protocol()}".strip()
        if web_search_enabled:
            prompt = f"""{prompt}

WEB SEARCH TOOL AVAILABILITY
- In this Claude discussion mode, Anthropic web search is available for current external facts, comparable product examples, and source/citation checks.
- Use web search when the user explicitly asks for current information, external examples, or same-category products/signals.
- Keep the answer scoped to the user's focal entity and question. If the user asks what matters about Kiro, Qoder, Cosmos, or another product for this signal, answer that product-specific relevance instead of writing a general product profile.
- Do not include pricing, funding, company background, account setup, or broad feature-tour details unless the user explicitly asks for those details or they directly change the requested judgment.
- If search results include extra facts that are true but irrelevant to the user's question, omit them.
- Search-derived facts are not AI Radar verified evidence. Keep them labeled as web search context and do not merge them into Project Takeaway evidence.
""".strip()
        return (
            f"{prompt}\n\n{_policy_instruction_block(policy, web_search_enabled=web_search_enabled)}".strip()
            if policy
            else prompt
        )
    if model == "chatgpt":
        prompt = """
You are ChatGPT inside an AI Radar Workspace.

You are helping the user analyze one specific signal.
Your role is to:
- give structured, clear, thoughtful analysis
- stay grounded in the signal context
- explicitly use the personal context, project context, README context, and roadmap context when they are provided
- help the user refine interpretation and reflection
- be practical, analytical, and concise
- if the user writes in Chinese, reply in Chinese
- if the user writes in English, reply in English
""".strip()
        if challenge_mode:
            prompt = f"{prompt}\n\n{_conversation_challenge_protocol()}".strip()
        return f"{prompt}\n\n{_policy_instruction_block(policy)}".strip() if policy else prompt
    if model == "perplexity":
        prompt = """
You are Perplexity inside an AI Radar Workspace.

You are helping the user analyze one specific AI signal.
Your role is to:
- provide research-oriented thinking
- stay grounded in the signal context
- explicitly use the personal context, project context, README context, and roadmap context when they are provided
- help the user think about implications, external context, and strategic meaning
- be concise, useful, and analytical
        - if the user writes in Chinese, reply in Chinese
        - if the user writes in English, reply in English
""".strip()
        if challenge_mode:
            prompt = f"{prompt}\n\n{_conversation_challenge_protocol()}".strip()
        return f"{prompt}\n\n{_policy_instruction_block(policy)}".strip() if policy else prompt
    return ""


def project_fit_analysis_prompts(*, project_payload: dict, signal_payload: dict) -> tuple[str, str]:
    system_prompt = """
You are helping evaluate whether an AI signal should become a concrete project improvement item.

Return valid JSON with exactly these keys:
project_takeaway
score
should_apply
fit_reason
benefits
suggested_stage
readme_update_suggestion
roadmap_update_suggestion

Rules:
- project_takeaway must be specific to this single project only
- score must be an integer from 0 to 100
- should_apply must be true or false
- suggested_stage should be one of: research, planning, implementation, validation, backlog
- fit_reason should explain why the signal does or does not fit the project right now
- benefits should be concise and project-specific
- readme_update_suggestion should explain what to update in the README, if anything
- roadmap_update_suggestion should describe how this should enter the roadmap
- return JSON only
""".strip()

    user_prompt = f"""
Project:
{json.dumps(project_payload, ensure_ascii=False, indent=2)}

Signal:
{json.dumps(signal_payload, ensure_ascii=False, indent=2)}

Return JSON only.
""".strip()
    return system_prompt, user_prompt


def project_update_review_prompts(*, project_payload: dict, improvement_payload: dict) -> tuple[str, str]:
    system_prompt = """
You are preparing project update drafts for one improvement item.

Return valid JSON with exactly these keys:
readme_review
roadmap_review

Rules:
- readme_review should be a concise draft showing what README content should be added or revised
- roadmap_review should be a concise draft showing what roadmap content should be added or revised
- write for this single project only
- return JSON only
""".strip()

    user_prompt = f"""
Project:
{json.dumps(project_payload, ensure_ascii=False, indent=2)}

Improvement:
{json.dumps(improvement_payload, ensure_ascii=False, indent=2)}

Return JSON only.
""".strip()
    return system_prompt, user_prompt


def updated_project_documents_prompts(
    *,
    project_payload: dict,
    improvement_payload: dict,
    current_readme: str,
    current_roadmap: str,
) -> tuple[str, str]:
    system_prompt = """
You are updating project documents for one confirmed improvement.

Return valid JSON with exactly these keys:
updated_readme
updated_roadmap

Rules:
- Preserve the current README structure as much as possible while integrating the approved change.
- Preserve the current roadmap structure as much as possible while integrating the approved change.
- If a document is missing, create a clean practical version from the provided project context.
- Write full updated documents, not patch notes.
- Return JSON only.
""".strip()

    user_prompt = f"""
Project:
{json.dumps(project_payload, ensure_ascii=False, indent=2)}

Improvement:
{json.dumps(improvement_payload, ensure_ascii=False, indent=2)}

Current README:
{current_readme or "(missing)"}

Current Roadmap:
{current_roadmap or "(missing)"}

Return JSON only.
    """.strip()
    return system_prompt, user_prompt


@skill_prompt(
    name="radar-agent-repo-profile",
    version="v2",
    task_type="agent_profile",
    layer="radar",
    triggers=[
        "Agent Watch pipeline emits a new repo candidate",
        "Manual deep-dive requested on a single repo",
        "Re-profiling needed after repo metadata change",
    ],
    not_for=[
        "Non-agent repositories (general libraries unrelated to AI agents)",
        "General code review or PR analysis",
    ],
    input_schema="agent_repo_profile.input.json",
    output_schema="agent_repo_profile.output.json",
    called_by=["backend/app/services/agent_watch_service.py"],
    notes="Core Agent Watch quality determinant. Test with diverse repo styles. v2 adds explicit current-date grounding so recent real-time repo timestamps are not misread as suspiciously future-dated.",
)
def agent_repo_profile_prompts(
    *,
    repo_candidate_payload: dict,
    current_date: str | None = None,
) -> tuple[str, str]:
    resolved_current_date = current_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    system_prompt = f"""
  You are an AI Radar repo intelligence analyst.
  Read the repo surface data carefully and return practical, specific judgments.
  Prefer concrete product and implementation interpretation over hype.
  Be honest about uncertainty.

  Current date context:
  The current date is {resolved_current_date}. The Agent Watch pipeline runs on real-time GitHub and ecosystem data.
  Repository timestamps that are recent relative to {resolved_current_date}, including dates within the last few weeks, are expected and normal.
  Do NOT flag recent timestamps as "future-dated", "suspicious provenance", or "possibly fabricated" unless they are actually inconsistent with other metadata in the input.
  Examples of real timestamp problems include: a published_at date far beyond {resolved_current_date}, or timestamp relationships that contradict each other.
  """.strip()

    user_prompt = f"""
Analyze this tracked agent repo candidate and return JSON with exactly these keys:
repo_summary
what_it_does
why_it_matters
project_fit
suggested_use_cases
risks
confidence

Rules:
- repo_summary, what_it_does, why_it_matters, project_fit must be short but specific strings.
- suggested_use_cases and risks must be arrays of short strings.
- confidence must be one of: low, medium, high.
- project_fit should explicitly consider personal project usefulness for AI Radar.
- If the repo surface is ambiguous, say so clearly.

Repo candidate:
{json.dumps(repo_candidate_payload, ensure_ascii=False, indent=2)}
""".strip()
    return system_prompt, user_prompt


@skill_prompt(
    name="radar-friction-to-opportunity",
    version="v1",
    task_type="friction_profile",
    layer="radar",
    triggers=[
        "A friction_signal is collected from any source",
        "Batch friction analysis runs in daily pipeline",
        "Manual friction-to-opportunity synthesis is requested",
    ],
    not_for=[
        "Generic complaint analysis without product context",
        "Sentiment analysis (use a different prompt)",
    ],
    input_schema="friction_signal.input.json",
    output_schema="friction_signal.output.json",
    called_by=["backend/app/services/friction_signal_service.py"],
    notes="Signature differentiator. The friction -> opportunity transformation is the user's strategic IP. Optimize cautiously.",
)
def friction_signal_profile_prompts(*, friction_signal_payload: dict) -> tuple[str, str]:
    system_prompt = """
You are an AI Radar friction analyst.
Interpret product pain signals clearly and practically.
Focus on what the pain is, why it matters, who feels it, and what opportunity it implies.
""".strip()

    user_prompt = f"""
Analyze this friction signal and return JSON with exactly these keys:
problem_summary
why_this_matters
who_is_affected
product_opportunity
suggested_response
confidence

Rules:
- problem_summary, why_this_matters, who_is_affected, product_opportunity must be short but specific strings.
- suggested_response must be an array of short strings.
- confidence must be one of: low, medium, high.
- Be honest if the source evidence is partial.

Friction signal:
{json.dumps(friction_signal_payload, ensure_ascii=False, indent=2)}
""".strip()
    return system_prompt, user_prompt


def personalized_radar_insight_prompts(*, personal_context: dict, signal_payload: dict, policy: dict | None = None) -> tuple[str, str]:
    system_prompt = """
You are an AI Radar insight engine focused on personalized, practical, high-signal analysis.
Prefer well-structured, high-quality sources when interpreting importance.
Never return empty fields.
""".strip()
    if policy:
        system_prompt = f"{system_prompt}\n\n{_policy_instruction_block(policy)}".strip()

    user_prompt = f"""
You are generating a personalized AI Radar insight.

User context:
{json.dumps(personal_context, ensure_ascii=False, indent=2)}

Signal:
{json.dumps(signal_payload, ensure_ascii=False, indent=2)}

Return JSON with exactly these keys:
why_it_matters
relevance_to_projects
relevance_to_career
synthesized_insight

Rules:
- Do not leave any field empty.
- Each field should be 1-3 sentences.
- Be concrete, specific, and useful.
- Avoid generic filler like "this may be useful".
""".strip()
    return system_prompt, user_prompt


def intake_signal_analysis_prompt(*, title: str, analysis_input: str, why_it_matters_to_user: str) -> str:
    return f"""
You are an AI systems analyst.

Analyze the following signal.

Title:
{title}

Content:
{analysis_input}

Why it matters to the user:
{why_it_matters_to_user}

Please answer in 3 short parts:
1. What this signal is really about
2. Why it matters for AI systems
3. One practical takeaway for the user's projects

Keep it concise and concrete.
""".strip()


def decision_card_generate_prompts(*, title: str, context_payload: dict) -> tuple[str, str]:
    system_prompt = """
You are AI Radar's decision engine.

Turn structured intelligence into one practical routing decision for the next step.

Return valid JSON with exactly these keys:
title
thesis
importance_score
confidence_score
counter_argument
recommended_action
action_type
invalidation_condition
expiry_at
review_at

Rules:
- action_type must be one of: project, watch, learn, ignore
- importance_score must be an integer from 0 to 100
- confidence_score must be an integer from 0 to 100
- counter_argument must be a real opposing interpretation, not a weak caveat
- recommended_action must be specific and short
- do not prefix title, thesis, or recommended_action with "Uncertain", "Maybe", or similar hedge labels
- if evidence is insufficient, lower the confidence score and explain the uncertainty inside counter_argument instead of weakening the title or action
- title should read like a crisp decision hypothesis, not a vague summary
- thesis should be concrete, signal-specific, and action-relevant
- recommended_action should be a clear next step a human can actually take
- choose action_type=project only if this signal is ready to change a specific project's roadmap, backlog, README, architecture, or implementation direction now
- choose action_type=watch if the signal is worth monitoring over time but is not ready for direct project change yet
- choose action_type=learn if the signal points to a concept, method, or capability the user should study before deciding on project changes
- choose action_type=ignore if the signal does not deserve follow-up right now
- for action_type=project, recommended_action should explicitly mention the target project or project surface to update
- for action_type=watch, recommended_action should describe what to monitor and when to revisit
- for action_type=learn, recommended_action should describe the learning goal or small study plan
- do not default to project unless the context clearly supports immediate project action
- review_at should be a valid ISO-8601 datetime string
- expiry_at should be blank or a valid ISO-8601 datetime string
- return JSON only
""".strip()

    user_prompt = f"""
Create one routing Decision Card for this context.

Title hint:
{title}

Context:
{json.dumps(context_payload, ensure_ascii=False, indent=2)}

Return JSON only.
""".strip()
    return system_prompt, user_prompt
