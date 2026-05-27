import json

from openai import AsyncOpenAI

from orbit.config import get_openai_api_key

_client = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=get_openai_api_key())
    return _client

SYSTEM_PROMPT = (
    "You analyze prospect signals and recommend engagement strategies.\n\n"
    "RULES:\n"
    "1. Only reference publicly visible information (posts, comments, public company news, job postings)\n"
    "2. NEVER suggest actions that reveal invisible monitoring or surveillance\n"
    "3. Every recommendation must cite the specific signal(s) it is based on\n"
    "4. Include exact dates and quotes from signals when available\n"
    "5. If you cannot cite a specific signal, say 'insufficient evidence' instead of guessing\n"
    "6. Do NOT generate generic networking advice. Every output must be evidence-based.\n"
    "7. Never produce output that reads as AI-generated empathy or synthetic warmth\n"
    "8. Only reference publicly visible information. Do not suggest actions that would reveal invisible monitoring."
)

MODEL = "gpt-4o-mini"


async def _chat(system: str, user: str, max_tokens: int = 1024) -> str:
    response = await _get_client().chat.completions.create(
        model=MODEL,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return response.choices[0].message.content


async def generate_value_ideas(
    prospect: dict,
    recent_signals: list,
    exa_content: list,
) -> list[dict]:
    prompt = (
        f"Prospect: {prospect.get('name', 'Unknown')} at {prospect.get('company', 'Unknown')}\n"
        f"Context: {prospect.get('context', '')}\n"
        f"Shared interests: {prospect.get('shared_interests', 'None known')}\n\n"
        f"Recent signals:\n{json.dumps(recent_signals[:5], indent=2, default=str)}\n\n"
        f"Available content to share:\n{json.dumps(exa_content[:5], indent=2, default=str)}\n\n"
        "Return 2-3 pieces of content worth sharing. For each, provide:\n"
        "- content_title\n- url\n- why_relevant (cite a specific signal)\n- how_to_share\n\n"
        "Return valid JSON array."
    )
    try:
        text = await _chat(SYSTEM_PROMPT, prompt)
        start = text.find("[")
        end = text.rfind("]") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
        return [{"error": "Could not parse value ideas response."}]
    except Exception as e:
        return [{"error": f"Intelligence layer failed: {e}"}]


async def generate_intro_angle(
    prospect: dict,
    engagement_history: list,
    top_signals: list,
) -> str:
    prompt = (
        f"Prospect: {prospect.get('name', 'Unknown')} at {prospect.get('company', 'Unknown')}\n"
        f"Context: {prospect.get('context', '')}\n"
        f"Relationship state: {prospect.get('relationship_state', 'unknown')}\n"
        f"Past topics: {prospect.get('past_topics', 'None')}\n"
        f"Shared interests: {prospect.get('shared_interests', 'None')}\n\n"
        f"Engagement history:\n{json.dumps(engagement_history[-10:], indent=2, default=str)}\n\n"
        f"Current top signals:\n{json.dumps(top_signals[:5], indent=2, default=str)}\n\n"
        "Write a natural intro angle that references specific past interactions and current timing signals. "
        "Cite exact engagements and signals. Do not produce generic networking advice."
    )
    try:
        return await _chat(SYSTEM_PROMPT, prompt)
    except Exception as e:
        return f"Intelligence layer failed: {e}"


async def analyze_prospect_fit(
    prospect_context: str,
    profile_data: dict,
    signals: list,
    signal_density: float,
) -> dict:
    prompt = (
        f"Prospect context: {prospect_context}\n"
        f"Profile: {json.dumps(profile_data, indent=2, default=str)}\n"
        f"Signal density: {signal_density}/10\n"
        f"Recent signals:\n{json.dumps(signals[:10], indent=2, default=str)}\n\n"
        "Assess this prospect's fit. Return JSON with:\n"
        "- fit_score (0-10)\n- signal_density_assessment\n- recommended_action\n"
        "- flag_for_removal (bool)\n- why_now (or why_not_now)\n\n"
        "If signal_density < 3, flag_for_removal should be true with explanation."
    )
    try:
        text = await _chat(SYSTEM_PROMPT, prompt, max_tokens=512)
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
        return {"error": "Could not parse fit analysis."}
    except Exception as e:
        return {"error": f"Intelligence layer failed: {e}"}


async def update_relationship_memory(
    prospect: dict,
    new_engagement: dict,
    new_signals: list,
) -> dict:
    prompt = (
        f"Prospect: {prospect.get('name', 'Unknown')} at {prospect.get('company', 'Unknown')}\n"
        f"Existing shared interests: {prospect.get('shared_interests', 'None')}\n"
        f"Existing past topics: {prospect.get('past_topics', 'None')}\n"
        f"Existing communication preferences: {prospect.get('communication_preferences', 'None')}\n\n"
        f"New engagement: {json.dumps(new_engagement, indent=2, default=str)}\n"
        f"New signals: {json.dumps(new_signals[:5], indent=2, default=str)}\n\n"
        "Update the relationship memory. Return JSON with:\n"
        "- shared_interests (append to existing, don't overwrite)\n"
        "- past_topics (append to existing, don't overwrite)\n"
        "- communication_preferences (update based on new data)\n\n"
        "Be concise. Each field should be a comma-separated list of items."
    )
    try:
        text = await _chat(SYSTEM_PROMPT, prompt, max_tokens=512)
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
        return {"error": "Could not parse memory update."}
    except Exception as e:
        return {"error": f"Intelligence layer failed: {e}"}
