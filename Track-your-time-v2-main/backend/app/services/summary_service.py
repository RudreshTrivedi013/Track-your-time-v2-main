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


# ── Prompt: strict factual bullets ───────────────────────────────────────────
SUMMARY_SYSTEM_PROMPT = (
    "You generate a concise end-of-day summary from a user's hourly check-in notes.\n\n"
    "Output ONLY valid JSON — no markdown fences, no commentary.\n"
    "Shape: {\"bullets\": [\"...\", \"...\"]}\n\n"
    "Rules (follow every one strictly):\n"
    "1. 2–4 bullets MAX. Fewer is better when there is less to report.\n"
    "2. Each bullet MUST be under 12 words.\n"
    "3. Only reference tasks/events explicitly stated in the notes. "
    "NEVER infer mood, effort, energy level, or attitude.\n"
    "4. BANNED filler phrases — never use any of these: 'started strong', "
    "'steady progress', 'renewed energy', 'sense of satisfaction', "
    "'maintained momentum', 'productive', 'great job', 'big win', "
    "'stayed on track', 'avoided distractions', 'kept momentum', "
    "'positive tone', 'hard work paid off', 'significant headway'.\n"
    "5. Prefer concrete details: use task names, times, and outcomes "
    "(e.g., 'Finished Project Report (2 PM)') over vague descriptions.\n"
    "6. If there are NO check-in notes (only missed check-in gaps, or nothing at all), "
    "output EXACTLY: {\"bullets\": [\"No activity logged today.\"]} — "
    "do NOT mention the missed check-ins in this case.\n"
    "7. NO closing sentence, NO encouragement, NO performance assessment.\n"
    "8. If there ARE real activity notes AND also missed check-in gaps, "
    "you MAY add a single plain bullet listing the gaps "
    "(e.g., 'Missed check-ins: 11 AM, 2 PM') — do not judge them.\n"
)

# ── Prompt: revision (regenerate after user edit) ────────────────────────────
REGENERATE_SYSTEM_PROMPT = (
    "You are revising a day-end bullet summary the user has manually edited.\n"
    "Improve their draft using the raw check-in data — do NOT replace their points.\n\n"
    "Output ONLY valid JSON — no markdown fences, no commentary.\n"
    "Shape: {\"bullets\": [\"...\", \"...\"]}\n\n"
    "Rules:\n"
    "1. 4 bullets MAX. Keep EVERY point the user made; do not drop any.\n"
    "2. Each bullet MUST be under 12 words.\n"
    "3. You may rephrase for clarity, but never change meaning.\n"
    "4. Only add a bullet if the raw data clearly covers something the user missed.\n"
    "5. BANNED filler phrases — never use: 'started strong', 'steady progress', "
    "'renewed energy', 'sense of satisfaction', 'maintained momentum', "
    "'productive', 'great job', 'positive tone', 'hard work paid off'.\n"
    "6. NO closing sentence, NO encouragement, NO performance assessment.\n"
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
