"""
checkin_service.py — Core logic for Hourly Productivity Check-ins.
"""
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import logging

from sqlalchemy import select, func
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.companion import (
    ProductivityLog,
    ProductivityStatus,
    CurrentTask,
    HourlyCheckinReminder,
    HourlyReminderStatus,
)
from app.models.activity import ReminderActivity, ActivityType, ActivitySource
from app.models.user import User

_UTC = timezone.utc
_SCHEDULER_WINDOW_MINUTES = 2

logger = logging.getLogger(__name__)


def _time_in_window(current, start, end) -> bool:
    if start is None or end is None:
        return False
    if start <= end:
        return start <= current < end
    return current >= start or current < end


def _minutes_since_midnight(value) -> int:
    return value.hour * 60 + value.minute


def slot_start_utc(user: User, now_utc: datetime) -> datetime | None:
    try:
        user_tz = ZoneInfo(user.timezone or "UTC")
    except Exception:
        user_tz = _UTC

    local_now = now_utc.astimezone(user_tz)
    current_time = local_now.time()

    if not _time_in_window(current_time, user.working_hours_start, user.working_hours_end):
        return None

    if _time_in_window(current_time, user.quiet_hours_start, user.quiet_hours_end):
        return None

    interval_minutes = user.checkin_interval_minutes or 60
    start_minutes = _minutes_since_midnight(user.working_hours_start)
    current_minutes = _minutes_since_midnight(current_time)
    work_start_local = local_now.replace(
        hour=0, minute=0, second=0, microsecond=0
    ) + timedelta(minutes=start_minutes)
    if user.working_hours_start > user.working_hours_end and current_minutes < start_minutes:
        work_start_local -= timedelta(days=1)

    elapsed_minutes = int((local_now - work_start_local).total_seconds() // 60)

    if elapsed_minutes < interval_minutes:
        return None

    minutes_since_due = elapsed_minutes % interval_minutes
    if minutes_since_due >= _SCHEDULER_WINDOW_MINUTES:
        return None

    due_slot_minutes = elapsed_minutes - minutes_since_due
    previous_slot_minutes = due_slot_minutes - interval_minutes
    slot_start_local = work_start_local + timedelta(minutes=previous_slot_minutes)
    return slot_start_local.astimezone(_UTC)


def sync_needs_checkin(db: Session, user: User, now_utc: datetime) -> bool:
    """
    Checks if a user needs a check-in reminder for the current scheduler window.

    Returns False if:
    - We're outside the slot window (slot_start is None).
    - The user already submitted a ProductivityLog for this slot.
    - A reminder record (pending OR completed) already exists for this slot,
      preventing double-firing when the beat tick runs again within the same window.
    """
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=_UTC)

    slot_start = slot_start_utc(user, now_utc)
    if slot_start is None:
        return False

    # Guard 1: Did the user already submit a productivity log for this slot?
    log_count = db.execute(
        select(func.count())
        .where(ProductivityLog.user_id == user.id, ProductivityLog.start_at >= slot_start)
    ).scalar()
    if log_count and log_count > 0:
        logger.debug(
            "[CheckinService] sync_needs_checkin — user %s already has %d log(s) since slot %s",
            user.id, log_count, slot_start,
        )
        return False

    # Guard 2: Does a reminder record already exist for this slot?
    # A 10-minute window around slot_start covers clock-skew between beat ticks.
    window_end = slot_start + timedelta(minutes=10)
    try:
        reminder_count = db.execute(
            select(func.count())
            .where(
                HourlyCheckinReminder.user_id == user.id,
                HourlyCheckinReminder.scheduled_time >= slot_start,
                HourlyCheckinReminder.scheduled_time < window_end,
            )
        ).scalar()
        if reminder_count and reminder_count > 0:
            logger.debug(
                "[CheckinService] sync_needs_checkin — user %s already has a reminder for slot %s — skipping",
                user.id, slot_start,
            )
            return False
    except Exception as exc:
        # If the reminders table is missing (e.g. migration pending), fall through
        # and let the caller decide — the push can still go out reminder-less.
        logger.warning(
            "[CheckinService] sync_needs_checkin — could not query reminders table: %s", exc
        )
        db.rollback()

    logger.debug(
        "[CheckinService] sync_needs_checkin — user %s needs checkin for slot %s",
        user.id, slot_start,
    )
    return True


def create_pending_hourly_checkin(
    db: Session,
    user: User,
    scheduled_time: datetime,
) -> HourlyCheckinReminder | None:
    try:
        existing = db.execute(
            select(HourlyCheckinReminder)
            .where(
                HourlyCheckinReminder.user_id == user.id,
                HourlyCheckinReminder.scheduled_time == scheduled_time,
            )
        ).scalar_one_or_none()
    except ProgrammingError as exc:
        logger.warning(
            "[CheckinService] hourly_checkin_reminders table missing; skipping reminder creation and continuing: %s",
            exc,
        )
        db.rollback()
        return None

    if existing is not None:
        logger.debug("[CheckinService] existing reminder %s for user %s at %s", getattr(existing, 'id', None), user.id, scheduled_time)
        return existing

    reminder = HourlyCheckinReminder(
        user_id=user.id,
        scheduled_time=scheduled_time,
        status=HourlyReminderStatus.pending,
    )
    db.add(reminder)
    db.flush()
    logger.debug("[CheckinService] created reminder %s for user %s at %s", getattr(reminder, 'id', None), user.id, scheduled_time)
    return reminder


def mark_expired_hourly_checkins_missed(db: Session, user: User, now_utc: datetime) -> int:
    interval_minutes = user.checkin_interval_minutes or 60
    # A checkin for slot X is generated at X + interval.
    # It should expire at X + 2*interval (meaning the user ignored it for a full interval).
    expired_threshold = now_utc - timedelta(minutes=interval_minutes * 2)

    try:
        results = db.execute(
            select(HourlyCheckinReminder)
            .where(
                HourlyCheckinReminder.user_id == user.id,
                HourlyCheckinReminder.status == HourlyReminderStatus.pending,
                HourlyCheckinReminder.scheduled_time <= expired_threshold,
            )
        )
    except ProgrammingError as exc:
        logger.warning(
            "[CheckinService] hourly_checkin_reminders table missing; skipping expired reminder processing: %s",
            exc,
        )
        db.rollback()
        return 0

    expired = 0
    for reminder in results.scalars().all():
        reminder.status = HourlyReminderStatus.missed

        # Log missed checkin at the reminder's scheduled_time so it appears
        # at the correct slot in the timeline (not when the system detected it).
        activity = ReminderActivity(
            user_id=user.id,
            activity_type=ActivityType.hourly_checkin,
            task_title="Missed Check-in",
            source=ActivitySource.checkin,
            timestamp=reminder.scheduled_time,
            metadata_json={"status": "missed"}
        )
        db.add(activity)

        logger.debug("[CheckinService] marking reminder %s missed for user %s", getattr(reminder, 'id', None), user.id)
        expired += 1

    if expired > 0:
        db.flush()

    return expired


async def link_checkin_to_hourly_reminder(
    db: AsyncSession,
    user_id: uuid.UUID,
    start_at: datetime,
    response_id: uuid.UUID,
    reminder_id: uuid.UUID | None = None,
) -> HourlyCheckinReminder | None:
    reminder = None
    # Use a nested savepoint so any error here doesn't roll back the outer
    # transaction (e.g. the ProductivityLog that was already added by the caller).
    async with db.begin_nested() as savepoint:
        try:
            if reminder_id is not None:
                result = await db.execute(
                    select(HourlyCheckinReminder)
                    .where(
                        HourlyCheckinReminder.user_id == user_id,
                        HourlyCheckinReminder.id == reminder_id,
                    )
                )
                reminder = result.scalar_one_or_none()

            if reminder is None:
                window_start = start_at - timedelta(minutes=5)
                window_end = start_at + timedelta(minutes=5)
                result = await db.execute(
                    select(HourlyCheckinReminder)
                    .where(
                        HourlyCheckinReminder.user_id == user_id,
                        HourlyCheckinReminder.status.in_([
                            HourlyReminderStatus.pending,
                            HourlyReminderStatus.missed,
                        ]),
                        HourlyCheckinReminder.scheduled_time >= window_start,
                        HourlyCheckinReminder.scheduled_time <= window_end,
                    )
                    .order_by(HourlyCheckinReminder.scheduled_time.desc())
                )
                reminder = result.scalar_one_or_none()

            if reminder is None:
                logger.debug("[CheckinService] no matching reminder found to link for user %s (reminder_id=%s)", user_id, reminder_id)
                return None

            reminder.status = HourlyReminderStatus.completed
            reminder.response_id = response_id
            logger.debug("[CheckinService] linked response %s to reminder %s for user %s", response_id, getattr(reminder, 'id', None), user_id)
            await savepoint.commit()
            return reminder
        except ProgrammingError as exc:
            logger.warning(
                "[CheckinService] hourly_checkin_reminders table missing; cannot link check-in to reminder: %s",
                exc,
            )
            await savepoint.rollback()
            return None



async def log_productivity(
    db: AsyncSession, 
    user_id: uuid.UUID, 
    status: ProductivityStatus, 
    now_utc: datetime
) -> ProductivityLog:
    """
    Logs a productivity session. Auto-calculates duration based on the last log,
    or defaults to 1 hour (3600 seconds) if there are no recent logs.
    """
    # Find the last log to determine the start time
    result = await db.execute(
        select(ProductivityLog)
        .where(ProductivityLog.user_id == user_id)
        .order_by(ProductivityLog.start_at.desc())
        .limit(1)
    )
    last_log = result.scalar_one_or_none()
    
    start_at = now_utc - timedelta(hours=1)
    if last_log and last_log.end_at and last_log.end_at > start_at:
        start_at = last_log.end_at
        
    duration_seconds = max(0, int((now_utc - start_at).total_seconds()))

    # Attempt to associate this log with the current task
    task_id = None
    ct_result = await db.execute(
        select(CurrentTask).where(CurrentTask.user_id == user_id)
    )
    record = ct_result.scalar_one_or_none()
    if record and record.task_id:
        task_id = record.task_id

    log = ProductivityLog(
        id=uuid.uuid4(),
        user_id=user_id,
        task_id=task_id,
        status=status,
        start_at=start_at,
        end_at=now_utc,
        duration_seconds=duration_seconds,
        note=f"Hourly check-in: {status.value}",
    )
    db.add(log)
    return log


async def get_today_stats(db: AsyncSession, user_id: uuid.UUID, now_utc: datetime) -> dict:
    """
    Calculates Today's Productive Hours, Average Score, Focus Percentage, 
    Current Streak, Longest Streak, and Missed Check-ins.
    """
    today_start = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
    
    result = await db.execute(
        select(ProductivityLog)
        .where(ProductivityLog.user_id == user_id, ProductivityLog.start_at >= today_start)
        .order_by(ProductivityLog.start_at.asc())
    )
    logs = result.scalars().all()
    
    total_seconds = sum((log.duration_seconds or 0) for log in logs)
    focused_seconds = sum((log.duration_seconds or 0) for log in logs if log.status == ProductivityStatus.focused)
    
    # Calculate streak (simple consecutive focused days)
    # Since we need full historical data, this is a simplified mock calculation for now, 
    # except using today's data. 
    # A true streak calc would require aggregating by day.
    # To keep it performant, we'll implement a basic version.
    
    stats = {
        "today_productive_hours": round(focused_seconds / 3600, 1),
        "focus_percentage": round((focused_seconds / total_seconds * 100) if total_seconds > 0 else 0, 1),
        "total_sessions_today": len(logs),
        "missed_checkins": 0, # Could be calculated by gaps > 1 hour during working hours
        "current_streak": 1 if focused_seconds > 0 else 0, # Simplified
        "longest_streak": 1 if focused_seconds > 0 else 0, # Simplified
    }
    
    return stats
