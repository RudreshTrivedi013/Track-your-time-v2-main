import logging
from datetime import datetime, timezone
import uuid

from sqlalchemy import select

from app.database import SyncSessionLocal
from app.workers.celery_app import celery_app
from app.models.user import User
from app.models.notification_log import Device
from app.services.push_service import send_push, GoneException
from app.core.security import create_action_token
from app.services.companion import checkin_service

logger = logging.getLogger(__name__)


@celery_app.task
def run_hourly_checkins():
    """
    Runs every 5 minutes. Finds users whose local time is within their configured
    working hours, who have checkins enabled, and who haven't checked in 
    within their configured checkin interval.
    """
    logger.info("[Beat] run_hourly_checkins — starting")
    with SyncSessionLocal() as db:
        # Filter in SQL, not Python. This runs every 60 seconds, so pulling the
        # entire users table across the wire each tick just to skip most of them
        # was the single largest recurring query in the app.
        users = db.execute(
            select(User).where(User.checkin_enabled.is_(True))
        ).scalars().all()
        now_utc = datetime.now(timezone.utc)
        triggered = 0

        for user in users:

            try:
                from zoneinfo import ZoneInfo
                tz = ZoneInfo(user.timezone)
            except Exception:
                tz = timezone.utc

            local_time = now_utc.astimezone(tz)
            
            # Check if current local time is within working hours
            current_time = local_time.time()
            is_working_hours = False
            
            if user.working_hours_start <= user.working_hours_end:
                is_working_hours = user.working_hours_start <= current_time < user.working_hours_end
            else:
                # Spans midnight
                is_working_hours = current_time >= user.working_hours_start or current_time < user.working_hours_end

            if is_working_hours:
                expired = checkin_service.mark_expired_hourly_checkins_missed(db, user, now_utc)
                if expired:
                    logger.debug("[Beat] Marked %d expired reminders missed for user %s", expired, user.id)
                    try:
                        db.commit()
                    except Exception:
                        logger.exception("[Beat] Failed to commit expired reminder updates for user %s", user.id)

                if checkin_service.sync_needs_checkin(db, user, now_utc):
                    slot_start = checkin_service.slot_start_utc(user, now_utc)
                    reminder = None
                    if slot_start is not None:
                        reminder = checkin_service.create_pending_hourly_checkin(db, user, slot_start)
                        logger.info("[Beat] Created pending reminder %s for user %s at %s", getattr(reminder, 'id', None), user.id, slot_start)
                        try:
                            db.commit()
                        except Exception:
                            logger.exception("[Beat] Failed to commit created reminder for user %s", user.id)

                    logger.info("[Beat] Sending checkin to user %s (local hour=%d)", user.id, local_time.hour)
                    try:
                        _send_checkin_reminder(db, user, reminder)
                    except Exception:
                        logger.exception("[Beat] _send_checkin_reminder failed for user %s", user.id)
                    triggered += 1
@celery_app.task
def send_delayed_checkin_reminder(user_id_str: str):
    """
    Sends a checkin reminder after a delay (e.g., 'Remind me later').
    """
    logger.info("[Task] send_delayed_checkin_reminder — user %s", user_id_str)
    with SyncSessionLocal() as db:
        user = db.execute(
            select(User).where(User.id == uuid.UUID(user_id_str))
        ).scalar_one_or_none()
        if user:
            _send_checkin_reminder(db, user)
        else:
            logger.warning("[Task] send_delayed_checkin_reminder — user %s not found", user_id_str)


def _send_checkin_reminder(db, user: User, reminder: 'HourlyCheckinReminder | None' = None):
    """
    Builds the payload and sends the push notification to all of the user's devices.
    """
    try:
        logger.debug("[Push] _send_checkin_reminder invoked for user %s reminder=%s", user.id, getattr(reminder, 'id', None))
    except Exception:
        pass
    devices = db.execute(
        select(Device).where(
            Device.user_id == user.id,
            Device.push_enabled.is_(True),
            Device.push_token.is_not(None),
        )
    ).scalars().all()

    if not devices:
        logger.debug("[Push] No devices found for user %s — skipping checkin push", user.id)
        try:
            db.commit()
        except Exception:
            logger.exception("[Push] Failed to commit db before skipping pushes for user %s", user.id)
        return

    payload = {
        "type": "checkin",
        "tag": "hourly-checkin",
        "title": "Hourly Reminder",
        "body": "What are you working on right now?",
        "action_token": create_action_token(str(user.id)),
        "reminder_id": str(reminder.id) if reminder is not None else None,
    }

    sent = 0
    removed = 0
    for device in devices:
        try:
            success = send_push(device.push_token, payload)
            if success:
                sent += 1
                logger.info("[Push] Checkin sent to device %s (user %s) reminder=%s", device.id, user.id, getattr(reminder, 'id', None))
                # also log a Notification delivered marker for observability
                logger.debug("[Push] Notification delivered to device %s (user %s) reminder=%s", device.id, user.id, getattr(reminder, 'id', None))
        except GoneException:
            logger.info("[Push] Device %s subscription gone — removing (user %s)", device.id, user.id)
            db.delete(device)
            removed += 1
        except Exception as exc:
            logger.warning("[Push] Checkin push to device %s failed: %s", device.id, exc)

    db.commit()
    logger.info("[Push] Checkin result for user %s: sent=%d removed=%d", user.id, sent, removed)
