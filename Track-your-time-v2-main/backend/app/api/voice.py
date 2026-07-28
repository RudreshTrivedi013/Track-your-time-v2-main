from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.database import get_db
from app.models import User
from app.models.activity import ActivitySource, ActivityType
from app.schemas.voice import VoiceTranscriptRequest, ParsedVoiceResult
from app.services import activity_service, voice_service

router = APIRouter(prefix="/tasks", tags=["voice"])


@router.post("/parse-voice", response_model=ParsedVoiceResult)
async def parse_voice(
    payload: VoiceTranscriptRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Returns a parsed draft only — never persists anything. The client shows
    this to the user for confirmation/edits before calling POST /tasks.
    """
    from zoneinfo import ZoneInfo
    user_tz = ZoneInfo(user.timezone or "UTC")
    now_iso = datetime.now(user_tz).isoformat()
    try:
        result = await voice_service.parse_voice_transcript(payload.transcript, now_iso)
    except ValueError as e:
        raise HTTPException(status_code=502, detail=f"Voice parsing failed: {e}")
    await activity_service.record_activity(
        db,
        user_id=user.id,
        activity_type=ActivityType.voice_update,
        source=ActivitySource.voice,
        task_title="Voice input",
        optional_notes=payload.transcript[:1000],
        metadata={
            "event": "voice_parse",
            "parsed_task_count": len(result.tasks),
        },
    )
    await db.commit()
    return result
