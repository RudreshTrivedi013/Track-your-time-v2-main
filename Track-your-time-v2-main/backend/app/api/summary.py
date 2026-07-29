from datetime import datetime, timezone
from uuid import UUID
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.database import get_db
from app.models import User
from app.models.companion import DailySummary
from app.schemas.companion import (
    SummaryHistoryOut,
    DailySummaryOut,
    SummaryUpdateIn,
    SummaryRegenerateOut,
)
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


@router.patch("/{summary_id}", response_model=SummaryOut)
async def update_summary(
    summary_id: str,
    body: SummaryUpdateIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Save user edits to a summary. Sets is_edited=True and stores edited_bullets."""
    if summary_id == "latest":
        stmt = select(DailySummary).where(
            DailySummary.user_id == user.id
        ).order_by(DailySummary.date.desc()).limit(1)
    else:
        stmt = select(DailySummary).where(
            DailySummary.id == UUID(summary_id),
            DailySummary.user_id == user.id,
        )
    
    result = await db.execute(stmt)
    summary = result.scalar_one_or_none()

    if not summary:
        raise HTTPException(status_code=404, detail="Summary not found")

    content = dict(summary.content)
    content["edited_bullets"] = body.edited_bullets
    content["is_edited"] = True

    summary.content = content
    await db.commit()
    await db.refresh(summary)

    return summary.content


@router.post("/{summary_id}/regenerate", response_model=SummaryRegenerateOut)
async def regenerate_summary(
    summary_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Revision-style regenerate: refines the user's edited draft using the raw day data.

    Backend enforces: only allowed when is_edited is True.
    """
    if summary_id == "latest":
        stmt = select(DailySummary).where(
            DailySummary.user_id == user.id
        ).order_by(DailySummary.date.desc()).limit(1)
    else:
        stmt = select(DailySummary).where(
            DailySummary.id == UUID(summary_id),
            DailySummary.user_id == user.id,
        )
    
    result = await db.execute(stmt)
    summary = result.scalar_one_or_none()

    if not summary:
        raise HTTPException(status_code=404, detail="Summary not found")

    content = dict(summary.content)
    if not content.get("is_edited"):
        raise HTTPException(
            status_code=409,
            detail="Cannot regenerate — summary has not been edited",
        )

    edited_bullets = content.get("edited_bullets", [])
    if not edited_bullets:
        raise HTTPException(
            status_code=409,
            detail="Cannot regenerate — no edited bullets found",
        )

    # Build fresh stats from current task data
    stats = await build_daily_stats(db, user.id)

    # Ask the AI to revise (not replace) the user's draft
    new_generated = await summary_service.regenerate_summary(stats, edited_bullets)

    # Update: replace generated_bullets, keep edited_bullets, keep is_edited=True
    content["generated_bullets"] = new_generated
    summary.content = content
    await db.commit()
    await db.refresh(summary)

    return summary.content


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
