"""
Handles day-end summary generation using the Groq API (OpenAI-compatible SDK).
The Groq endpoint returns JSON-only output; we always validate against SummaryOut
before passing anything to the rest of the system.
"""
import json

from openai import AsyncOpenAI
from pydantic import ValidationError

from app.config import settings
from app.schemas.device import SummaryOut

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key=settings.GROQ_API_KEY,
            base_url="https://api.groq.com/openai/v1",
        )
    return _client


# ── Prompt: narrative bullets, no counts ─────────────────────────────────────
SUMMARY_SYSTEM_PROMPT = (
    "You write short, natural end-of-day bullet-point summaries for a personal "
    "productivity companion app.\n\n"
    "Rules:\n"
    "- Output ONLY valid JSON, no markdown fences, no commentary.\n"
    "- Shape: {\"bullets\": [\"...\", \"...\"]}\n"
    "- Write MAXIMUM 4 bullets. If the day was quiet, write 1-2 bullets.\n"
    "- Every bullet MUST reference concrete input data (a specific task title, "
    "a timestamp, or a check-in note). If a bullet doesn't point to real input data, omit it.\n"
    "- If there is very little or no activity, be honest and short (e.g., 'Not much logged today' "
    "or 'Only worked on \"Check\" today'). Do NOT pad the summary.\n"
    "- NO meta-commentary or performance assessments. Do NOT narrate your opinion of the day. "
    "Only report factual events.\n"
    "- NO counts, NO statistics. Describe events, not metrics.\n"
    "- BAN these filler/sentiment phrases entirely (do not use them): 'started strong', "
    "'great progress', 'variety of tasks', 'big win', 'feeling accomplished', "
    "'in a good position', 'likely challenging', 'dive back in'.\n"
    "- Each bullet is a short narrative sentence written in second person (\"you\").\n"
)

# ── Prompt: revision (regenerate after user edit) ────────────────────────────
REGENERATE_SYSTEM_PROMPT = (
    "You are revising a day-end bullet summary that the user has manually edited. "
    "Your job is to IMPROVE their draft using the raw day data, not replace it.\n\n"
    "Rules:\n"
    "- Output ONLY valid JSON, no markdown fences, no commentary.\n"
    "- Shape: {\"bullets\": [\"...\", \"...\"]}\n"
    "- Write MAXIMUM 4 bullets total.\n"
    "- Keep EVERY point the user made. Do not drop any of their bullets.\n"
    "- You may rephrase for clarity or flow, but do not change meaning.\n"
    "- Only add a new bullet if the raw day data clearly supports something the "
    "user missed. Every new bullet MUST reference concrete input data.\n"
    "- NO meta-commentary or performance assessments. Only report factual events.\n"
    "- NO counts, NO statistics. Narrative sentences only.\n"
    "- BAN these filler/sentiment phrases entirely (do not use them): 'started strong', "
    "'great progress', 'variety of tasks', 'big win', 'feeling accomplished', "
    "'in a good position', 'likely challenging', 'dive back in'.\n"
)


def _strip_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("```", 2)[1]
        if t.startswith("json"):
            t = t[4:]
    return t.strip().strip("`").strip()


def _validate_bullets(data: dict) -> list[str]:
    """Extract and validate the bullets list from LLM output."""
    bullets = data.get("bullets")
    if not isinstance(bullets, list) or len(bullets) == 0:
        raise ValueError("LLM output missing or empty 'bullets' array")
    # Ensure every element is a non-empty string
    cleaned = [str(b).strip() for b in bullets if str(b).strip()]
    if not cleaned:
        raise ValueError("All bullets were empty after cleanup")
    return cleaned


async def generate_day_end_summary(stats: dict) -> dict:
    """Call Groq for the day-end narrative bullet summary.

    Returns: {"generated_bullets": [...], "edited_bullets": None, "is_edited": False}
    """
    client = _get_client()
    response = await client.chat.completions.create(
        model=settings.GROQ_MODEL,
        max_tokens=800,
        messages=[
            {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
            {"role": "user", "content": f"Today's stats: {json.dumps(stats, default=str)}"},
        ],
    )
    raw_text = response.choices[0].message.content or ""
    cleaned = _strip_fences(raw_text)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"Groq did not return valid JSON: {e}") from e

    bullets = _validate_bullets(data)

    return {
        "generated_bullets": bullets,
        "edited_bullets": None,
        "is_edited": False,
    }


async def regenerate_summary(stats: dict, user_edited_bullets: list[str]) -> list[str]:
    """Revision-style regenerate: refines the user's edit using raw day data.

    Returns the new generated_bullets list. Does NOT touch edited_bullets —
    that's the caller's job.
    """
    client = _get_client()

    user_msg = (
        f"Raw day data:\n{json.dumps(stats, default=str)}\n\n"
        f"User's edited summary (treat as draft to refine):\n"
        + "\n".join(f"• {b}" for b in user_edited_bullets)
    )

    response = await client.chat.completions.create(
        model=settings.GROQ_MODEL,
        max_tokens=800,
        messages=[
            {"role": "system", "content": REGENERATE_SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
    )
    raw_text = response.choices[0].message.content or ""
    cleaned = _strip_fences(raw_text)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"Groq did not return valid JSON: {e}") from e

    return _validate_bullets(data)
