from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.database import get_db
from app.models import User
from app.models.companion import DailySummary
from app.schemas.companion import SummaryHistoryOut, DailySummaryOut
from app.schemas.device import SummaryOut
from app.workers.summary_tasks import build_daily_stats
from app.services import summary_service

router = APIRouter(prefix="/summary", tags=["summary"])


@router.post("/trigger", response_model=SummaryOut)
async def trigger_summary_manually(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """Manual trigger for testing — the real flow runs via Celery beat at each user's local 9pm."""
    stats = await build_daily_stats(db, user.id)
    result = await summary_service.generate_day_end_summary(stats)

    tz = ZoneInfo(user.timezone or "UTC")
    local_date = datetime.now(timezone.utc).astimezone(tz).date()

    stmt = insert(DailySummary).values(
        user_id=user.id,
        date=local_date,
        content=result,
    ).on_conflict_do_update(
        constraint="uq_daily_summary_user_date",
        set_={"content": result, "created_at": datetime.now(timezone.utc)},
    )
    await db.execute(stmt)
    await db.commit()

    return result


@router.get("/history", response_model=SummaryHistoryOut)
async def get_summary_history(
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Fetch past daily summaries for the user."""
    # Count total
    count_stmt = select(func.count()).select_from(DailySummary).where(DailySummary.user_id == user.id)
    total = await db.scalar(count_stmt) or 0

    # Fetch summaries
    stmt = (
        select(DailySummary)
        .where(DailySummary.user_id == user.id)
        .order_by(DailySummary.date.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    summaries = result.scalars().all()

    return SummaryHistoryOut(summaries=list(summaries), total=total)
