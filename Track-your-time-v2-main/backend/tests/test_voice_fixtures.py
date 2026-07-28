"""
Validates the voice-parsing output against the fixture file shape, and
(if OPENAI_API_KEY is set) actually calls the live API and checks the
schema validates + title is non-empty for each transcript.

This is a schema/shape test, not an exact-output test, because LLM phrasing
varies — we assert structure and key fields, not byte-for-byte JSON equality.

Run with: pytest tests/test_voice_fixtures.py -v
(skips live-API assertions automatically if OPENAI_API_KEY is unset)
"""
import json
import os
from pathlib import Path

import pytest

from app.schemas.voice import ParsedVoiceResult

FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "voice_transcripts.json"


def load_fixtures():
    return json.loads(FIXTURE_PATH.read_text())


@pytest.mark.parametrize("fixture", load_fixtures(), ids=lambda f: f["name"])
def test_fixture_expected_shape_is_schema_valid(fixture):
    """Every fixture's hand-authored 'expected' value must itself validate
    against ParsedVoiceResult — this catches fixture authoring mistakes."""
    result = ParsedVoiceResult.model_validate(fixture["expected"])
    assert len(result.tasks) >= 1
    for task in result.tasks:
        assert task.title
        assert task.recurrence in {"none", "interval", "daily", "weekly"}


@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") == "placeholder",
    reason="requires live OPENAI_API_KEY"
)
@pytest.mark.asyncio
@pytest.mark.parametrize("fixture", load_fixtures(), ids=lambda f: f["name"])
async def test_live_voice_parses_transcript_validly(fixture):
    from app.services.voice_service import parse_voice_transcript

    result = await parse_voice_transcript(fixture["transcript"], fixture["current_datetime"])
    assert len(result.tasks) == len(fixture["expected"]["tasks"])
    for task in result.tasks:
        assert task.title
