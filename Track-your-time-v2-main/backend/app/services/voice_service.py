"""
Handles voice transcript parsing using OpenAI (gpt-4o-mini by default).
The model must return JSON-only output; we always validate the result
against ParsedVoiceResult before returning — never trust raw model text.
"""
import json
import logging

from groq import AsyncGroq
from pydantic import ValidationError

from app.config import settings
from app.schemas.voice import ParsedVoiceResult

logger = logging.getLogger(__name__)

_client: AsyncGroq | None = None


def _get_client() -> AsyncGroq:
    global _client
    if _client is None:
        _client = AsyncGroq(api_key=settings.GROQ_API_KEY)
    return _client


VOICE_SYSTEM_PROMPT = """You convert spoken task transcripts into structured JSON.
Output ONLY valid JSON, no markdown fences, no commentary, matching exactly this shape:

{"tasks": [{"title": str, "due_date": str|null, "due_time": str|null, "recurrence": "none"|"interval"|"daily"|"weekly", "interval_minutes": int|null, "notes": [{"text": str}], "ambiguous_fields": [str]}]}

Rules:
- due_date: ISO format YYYY-MM-DD if a specific date is stated or can be resolved from "today"/"tomorrow" relative to the given current date. If genuinely ambiguous (e.g. "tomorrow morning" with no exact time), still give the date but list "due_time" as null and add "due_time" to ambiguous_fields.
- due_time: 24-hour "HH:MM" if stated or inferable (e.g. "morning" is ambiguous -> null). For relative times like "in 20 minutes", compute the absolute due_date/due_time from the given current datetime.
- recurrence: "interval" for "every N minutes/hours", "daily" for once-a-day repeats, "weekly" for once-a-week, "none" for one-off.
- interval_minutes: only set when recurrence == "interval".
- Default start time for recurrence: If the transcript specifies an interval or recurrence but NO explicit start time (e.g., "drink water every two minutes"), you MUST extract the due_date and due_time directly from the provided current datetime. Do not leave them null.
- Multiple tasks in one transcript -> multiple entries in "tasks".
- ambiguous_fields: list any field names you could not confidently resolve.
- Never include any text outside the JSON object."""


def _strip_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("```", 2)[1]
        if t.startswith("json"):
            t = t[4:]
    return t.strip().strip("`").strip()


def _loads_lenient(text: str):
    """
    Parse the first JSON value in `text`, tolerating trailing prose.

    LLMs routinely append a sentence after the JSON ("Here's the task I
    created…"), which makes json.loads fail with "Extra data: line 3 column 1".
    The JSON itself is perfectly good — only the tail is junk — so a strict
    parse throws away a usable answer and surfaces a 502 to the user.

    json.JSONDecoder().raw_decode stops at the end of the first complete value
    and reports where it stopped, which is exactly the behaviour we want. We
    also skip any preamble before the opening brace.
    """
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    if start == -1:
        raise ValueError("no JSON object found in model output")

    obj, _end = json.JSONDecoder().raw_decode(text[start:])
    return obj


async def parse_voice_transcript(transcript: str, current_datetime_iso: str) -> ParsedVoiceResult:
    """Call Groq to parse a voice transcript into structured tasks.

    Always validates against ParsedVoiceResult — never returns raw model text.
    """
    client = _get_client()
    response = await client.chat.completions.create(
        model=settings.GROQ_MODEL,
        max_tokens=2000,
        messages=[
            {"role": "system", "content": VOICE_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Current datetime (ISO, use for resolving relative times): {current_datetime_iso}\n\n"
                    f"Transcript:\n{transcript}"
                ),
            },
        ],
        temperature=0.1,
        # Constrain the model to emit a bare JSON object. This is the actual fix
        # for the "Extra data: line 3 column 1" failures — the model was
        # appending a sentence after the JSON. _loads_lenient below still
        # handles it if a model ignores this.
        response_format={"type": "json_object"},
    )
    raw_text = response.choices[0].message.content or ""
    cleaned = _strip_fences(raw_text)

    try:
        data = _loads_lenient(cleaned)
    except (json.JSONDecodeError, ValueError) as e:
        # Log the actual output — without it this failure is undebuggable,
        # since the model text never reaches the client.
        logger.warning("[Voice] Unparseable model output (%s): %r", e, raw_text[:500])
        raise ValueError(f"Could not parse the model's response: {e}") from e

    try:
        return ParsedVoiceResult.model_validate(data)
    except ValidationError as e:
        raise ValueError(f"OpenAI output failed schema validation: {e}") from e
