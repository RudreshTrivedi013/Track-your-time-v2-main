"""
Day-end summary Celery task.

After generating the AI summary for a user:
1. Sends a Web Push notification to every push-enabled device with the full
   summary embedded in the payload (so the OS notification body is meaningful).
2. Publishes a Redis pub/sub message on channel ``summary:{user_id}`` so that
   any open WebSocket connections receive the summary in real time without the
   user having to tap the notification.
"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import asyncio
import json
import logging

from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.models import User, Task, TaskStatus, TaskSource, Device
from app.models.companion import DailySummary
from app.services import push_service, summary_service
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _build_stats_payload(tasks: list, activities: list) -> dict:
    completed = [t for t in tasks if t.status == TaskStatus.done]
    open_tasks = [t for t in tasks if t.status != TaskStatus.done]
    total_snoozes = sum(t.snoozed_count_today for t in tasks)
    
    # Format activities as a timeline
    timeline = []
    for a in sorted(activities, key=lambda x: x.timestamp):
        # Format time as HH:MM
        time_str = a.timestamp.strftime("%H:%M")
        action = f"[{time_str}] {a.activity_type.value}: '{a.task_title}'"
        if a.optional_notes:
            action += f" (Note: {a.optional_notes})"
        timeline.append(action)

    return {
        "completed_tasks": [t.title for t in completed],
        "open_tasks": [t.title for t in open_tasks],
        "snooze_count": total_snoozes,
        "activity_timeline": timeline,
    }


# Async version — used by the FastAPI /summary/trigger endpoint
async def build_daily_stats(db: AsyncSession, user_id) -> dict:
    # Get today's local boundaries
    from datetime import datetime, timezone
    from zoneinfo import ZoneInfo
    user = await db.get(User, user_id)
    tz = ZoneInfo(user.timezone or "UTC") if user else ZoneInfo("UTC")
    now = datetime.now(timezone.utc).astimezone(tz)
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = now.replace(hour=23, minute=59, second=59, microsecond=999999)

    # Fetch tasks
    tasks_result = await db.execute(select(Task).where(Task.user_id == user_id))
    tasks = list(tasks_result.scalars().all())

    # Fetch today's activities
    from app.models.activity import ReminderActivity
    act_result = await db.execute(
        select(ReminderActivity).where(
            ReminderActivity.user_id == user_id,
            ReminderActivity.timestamp >= start_of_day,
            ReminderActivity.timestamp <= end_of_day
        )
    )
    activities = list(act_result.scalars().all())

    return _build_stats_payload(tasks, activities)


# Sync version — used by the Celery beat task
def build_daily_stats_sync(db: Session, user_id) -> dict:
    from datetime import datetime, timezone
    from zoneinfo import ZoneInfo
    user = db.query(User).get(user_id)
    tz = ZoneInfo(user.timezone or "UTC") if user else ZoneInfo("UTC")
    now = datetime.now(timezone.utc).astimezone(tz)
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = now.replace(hour=23, minute=59, second=59, microsecond=999999)

    tasks = db.query(Task).filter(Task.user_id == user_id).all()
    
    from app.models.activity import ReminderActivity
    activities = db.query(ReminderActivity).filter(
        ReminderActivity.user_id == user_id,
        ReminderActivity.timestamp >= start_of_day,
        ReminderActivity.timestamp <= end_of_day
    ).all()

    return _build_stats_payload(tasks, activities)


def _publish_ws_summary(user_id: str, result: dict) -> None:
    """Publish the summary to a Redis pub/sub channel so that any open
    WebSocket connections pick it up and forward it to the browser tab.

    Uses the synchronous redis-py client since this runs inside a Celery worker
    (no asyncio event loop available at this point).
    """
    try:
        import redis as sync_redis
        from app.config import settings

        r = sync_redis.from_url(settings.REDIS_URL, decode_responses=True)
        message = json.dumps({
            "event": "summary_ready",
            "summary": result,
        })
        r.publish(f"summary:{user_id}", message)
        r.close()
    except Exception as exc:
        logger.warning("Failed to publish summary over Redis pub/sub: %s", exc)


def _run_for_user_sync(db: Session, user: User):
    stats = build_daily_stats_sync(db, user.id)
    try:
        # summary_service.generate_day_end_summary is async — run it in its own loop
        result = asyncio.run(summary_service.generate_day_end_summary(stats))
        
        # Save / Upsert to the DB
        tz = ZoneInfo(user.timezone or "UTC")
        local_date = datetime.now(timezone.utc).astimezone(tz).date()

        # Check if a summary already exists for today (may have user edits)
        existing = (
            db.query(DailySummary)
            .filter(DailySummary.user_id == user.id, DailySummary.date == local_date)
            .first()
        )

        if existing and existing.content.get("is_edited"):
            # User has edited today's summary — only update generated_bullets,
            # preserve their edited_bullets and is_edited flag.
            content = dict(existing.content)
            content["generated_bullets"] = result["generated_bullets"]
            existing.content = content
        else:
            # No existing summary or it hasn't been edited — full upsert
            stmt = insert(DailySummary).values(
                user_id=user.id,
                date=local_date,
                content=result,
            ).on_conflict_do_update(
                constraint="uq_daily_summary_user_date",
                set_={"content": result, "created_at": datetime.now(timezone.utc)},
            )
            db.execute(stmt)
        db.commit()
    except Exception as exc:
        logger.error("Summary generation failed for user %s: %s", user.id, exc)
        return

    # 1. Send Web Push to every device with the full summary embedded.
    devices = (
        db.query(Device)
        .filter(Device.user_id == user.id, Device.push_enabled == True)  # noqa: E712
        .all()
    )
    from app.services.push_service import GoneException
    payload = push_service.build_summary_ready_payload(result)
    push_sent = 0
    push_removed = 0
    for d in devices:
        try:
            push_service.send_push(d.push_token, payload)
            push_sent += 1
            logger.info("[Push] Summary sent to device %s (user %s)", d.id, user.id)
        except GoneException:
            logger.info("[Push] Device %s subscription gone — removing (user %s)", d.id, user.id)
            db.delete(d)
            push_removed += 1
        except Exception as exc:
            logger.warning("[Push] Summary push to device %s failed: %s", d.id, exc)

    # Commit device deletions before publishing the WS summary.
    db.commit()
    logger.info("[Push] Summary result for user %s: sent=%d removed=%d", user.id, push_sent, push_removed)

    # 2. Broadcast via Redis pub/sub so open browser tabs get it instantly.
    _publish_ws_summary(str(user.id), result)


def _run_day_end_summaries_sync():
    from app.database import SyncSessionLocal

    now_utc = datetime.now(timezone.utc)
    with SyncSessionLocal() as db:
        # Filter in SQL rather than fetching every user and skipping in Python.
        # (The local-hour == 21 check below still has to happen in Python, since
        # it depends on each user's timezone.)
        users = db.query(User).filter(User.daily_summary_enabled.is_(True)).all()
        for user in users:
            tz = ZoneInfo(user.timezone or "UTC")
            local_hour = now_utc.astimezone(tz).hour
            if local_hour == 21:  # 9pm local — beat runs hourly on the hour
                _run_for_user_sync(db, user)


@celery_app.task(name="app.workers.summary_tasks.run_day_end_summaries")
def run_day_end_summaries():
    _run_day_end_summaries_sync()
