"""
Developer-only tooling endpoints.

Only mounted when ENVIRONMENT=development (see main.py).

Endpoints
---------
POST /dev/trigger-checkin         → trigger run_hourly_checkins for the authed user immediately
POST /dev/trigger-reminder-check  → trigger check_due_reminders immediately
GET  /dev/scheduler-status        → show beat schedule config + next run times
POST /dev/test-push               → send a test push to all of the authed user's devices
"""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.database import get_db
from app.models import User, Device
from app.services.push_service import send_push, GoneException, build_reminder_payload
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dev", tags=["dev"])


@router.post("/trigger-checkin")
async def trigger_checkin(user: User = Depends(get_current_user)):
    """Trigger the hourly check-in task immediately for the authenticated user."""
    from app.workers.checkin_tasks import send_delayed_checkin_reminder
    result = send_delayed_checkin_reminder.delay(str(user.id))
    logger.info("[Dev] trigger-checkin dispatched for user %s — task_id=%s", user.id, result.id)
    return {
        "status": "dispatched",
        "task_id": result.id,
        "user_id": str(user.id),
        "triggered_at": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/trigger-reminder-check")
async def trigger_reminder_check(user: User = Depends(get_current_user)):
    """Trigger check_due_reminders immediately (checks ALL users)."""
    from app.workers.reminder_tasks import check_due_reminders
    result = check_due_reminders.delay()
    logger.info("[Dev] trigger-reminder-check dispatched by user %s — task_id=%s", user.id, result.id)
    return {
        "status": "dispatched",
        "task_id": result.id,
        "triggered_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/scheduler-status")
async def scheduler_status(user: User = Depends(get_current_user)):
    """Return the Celery Beat schedule configuration so devs can verify timings."""
    schedule = {}
    for name, entry in celery_app.conf.beat_schedule.items():
        sched = entry.get("schedule")
        if hasattr(sched, "run_every"):
            # timedelta-based
            schedule[name] = {
                "task": entry["task"],
                "schedule": f"every {sched.run_every.total_seconds()}s",
            }
        elif hasattr(sched, "minute"):
            # crontab-based
            schedule[name] = {
                "task": entry["task"],
                "schedule": f"crontab(minute={sched._orig_minute}, hour={sched._orig_hour})",
            }
        else:
            schedule[name] = {"task": entry["task"], "schedule": str(sched)}

    return {
        "beat_schedule": schedule,
        "broker": celery_app.conf.broker_url,
        "timezone": celery_app.conf.timezone,
        "server_time_utc": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/test-push")
async def test_push(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Send a test push notification to all registered devices of the authenticated user."""
    result = await db.execute(
        select(Device).where(Device.user_id == user.id, Device.push_enabled == True)  # noqa: E712
    )
    devices = result.scalars().all()

    if not devices:
        return {"status": "no_devices", "message": "No push-enabled devices found for this user."}

    payload = {
        "type": "checkin",
        "tag": "dev-test-push",
        "title": "🧪 Test Notification",
        "body": "Push notifications are working correctly!",
        "action_token": "",
    }

    results = []
    for device in devices:
        try:
            send_push(device.push_token, payload)
            results.append({"device_id": str(device.id), "status": "sent"})
            logger.info("[Dev] Test push sent to device %s", device.id)
        except GoneException:
            results.append({"device_id": str(device.id), "status": "gone_expired"})
            db.delete(device)
            logger.info("[Dev] Device %s expired — removed", device.id)
        except Exception as exc:
            results.append({"device_id": str(device.id), "status": "error", "error": str(exc)})
            logger.warning("[Dev] Test push to device %s failed: %s", device.id, exc)

    await db.commit()
    return {
        "status": "done",
        "devices_targeted": len(devices),
        "results": results,
        "sent_at": datetime.now(timezone.utc).isoformat(),
    }
