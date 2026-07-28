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


SUMMARY_SYSTEM_PROMPT = (
    "You write a short, encouraging end-of-day task summary for a productivity app.\n"
    "Output ONLY valid JSON, no markdown fences, no commentary, matching exactly:\n"
    '{"summary": str, "highlight": str, "concern": str, "tomorrow_suggestion": str}\n'
    "Keep each field to 1-2 sentences, friendly and specific to the data given."
)


def _strip_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("```", 2)[1]
        if t.startswith("json"):
            t = t[4:]
    return t.strip().strip("`").strip()


async def generate_day_end_summary(stats: dict) -> dict:
    """Call Groq (llama-3.3-70b-versatile) for the day-end summary.

    Always validates against SummaryOut — never returns raw model text.
    """
    client = _get_client()
    response = await client.chat.completions.create(
        model=settings.GROQ_MODEL,
        max_tokens=600,
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

    try:
        validated = SummaryOut.model_validate(data)
    except ValidationError as e:
        raise ValueError(f"Groq output failed schema validation: {e}") from e

    return validated.model_dump()
