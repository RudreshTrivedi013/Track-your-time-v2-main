"""
Activities API.
"""
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.database import get_db
from app.models import User
from app.models.activity import ActivitySource, ActivityType
from app.schemas.activity import ActivityOut, ActivitySubmitRequest
from app.services import activity_service
from app.services.intent_service import extract_intent

router = APIRouter(prefix="/activities", tags=["activities"])


@router.get("", response_model=list[ActivityOut])
async def list_activities(
    today: bool = Query(default=False),
    date_: date | None = Query(default=None, alias="date"),
    limit: int = Query(default=50, ge=1, le=200),
    activity_type: ActivityType | None = Query(default=None),
    source: ActivitySource | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ActivityOut]:
    statement = activity_service.activities_query(
        user,
        today=today,
        target_date=date_,
        activity_type=activity_type,
        source=source,
    ).limit(limit)
    result = await db.execute(statement)
    return list(result.scalars().all())


@router.post("/submit", response_model=ActivityOut, status_code=201)
async def submit_activity(
    payload: ActivitySubmitRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Parse a reminder response utterance and persist one structured activity.
    """
    intent = extract_intent(payload.text)
    activity_type = ActivityType(intent.activity_type)
    if activity_type == ActivityType.status_update:
        activity_type = (
            ActivityType.voice_update
            if payload.source == ActivitySource.voice.value
            else ActivityType.text_update
        )
    activity = await activity_service.record_activity(
        db,
        user_id=user.id,
        task_id=payload.task_id,
        activity_type=activity_type,
        task_title=intent.task_title,
        optional_notes=intent.optional_notes,
        source=ActivitySource(payload.source),
        metadata={
            "event": "reminder_response",
            "raw_text": payload.text,
        },
    )
    await db.commit()
    await db.refresh(activity)
    return activity
