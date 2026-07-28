"""
Beat job: every 60s, find due tasks, respect quiet hours, pick target
devices, send a push, and log it.

SCHEDULING MODEL — read this before changing anything here.

`next_due_at` is the SINGLE cursor the scheduler reads. It answers exactly one
question: "when should we next notify about this task?" While a task is still
owed a reminder it always points at a future instant; it is nulled only to mean
"stop reminding" (completed, or muted).

  due_at        descriptive only — what the user set. NEVER read here.
  anchor_time   the durable recurrence schedule, owned by task_service.
  snoozed_until SUPPRESSES next_due_at while it is in the future.

The previous implementation nulled next_due_at after sending and fell back to
matching on due_at. That produced two opposite bugs at once: a one-off task
fired exactly twice (~60s apart) and then went silent forever, while a
recurring task matched the fallback on every single tick and pushed once a
minute regardless of its interval. Both disappear once due_at is out of the
predicate and the cursor is always advanced rather than cleared.

Why UTC everywhere: due_at/next_due_at/snoozed_until are stored in UTC so
"is this due" is a single unambiguous comparison against utcnow() with no
DST or timezone-conversion bugs in the hot scheduling path. We only convert
to the user's local timezone at the edges — for quiet-hours math and for
deciding when "9pm" is for the daily summary — where local time is actually
the meaningful unit.

Why synchronous: Celery uses a prefork model. asyncpg connections are
bound to a specific event loop, and asyncio.run() creates a new loop on
every call, so the old connection's Future ends up attached to a different
loop → RuntimeError. Using psycopg2 (sync) avoids this entirely.
"""
from datetime import datetime, timedelta, timezone
import logging

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Task, TaskStatus, User, Device, NotificationLog
from app.services import push_service
from app.services.push_service import GoneException
from app.workers.celery_app import celery_app
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

# Statuses the scheduler will notify about. `blocked` (surfaced as "Muted") and
# `done` are absent by design — that exclusion is what makes Mute work.
NOTIFIABLE_STATUSES = (TaskStatus.pending, TaskStatus.in_progress, TaskStatus.snoozed)


def _in_quiet_hours(user: User, now_utc: datetime) -> tuple[bool, datetime | None]:
    """Returns (is_quiet, push_to) where push_to is the UTC instant quiet
    hours end, if currently within the user's quiet-hours window."""
    if not user.quiet_hours_start or not user.quiet_hours_end:
        return False, None

    try:
        tz = ZoneInfo(user.timezone or "UTC")
    except Exception:
        # A corrupt timezone must not take down the tick. Signup/update now
        # validate this, but pre-existing rows were never re-validated.
        logger.warning("[Beat] User %s has an invalid timezone %r — ignoring quiet hours",
                       user.id, user.timezone)
        return False, None

    local_now = now_utc.astimezone(tz)
    start, end = user.quiet_hours_start, user.quiet_hours_end

    local_time = local_now.time()
    if start <= end:
        is_quiet = start <= local_time < end
    else:
        # Window wraps midnight, e.g. 22:00 - 07:00
        is_quiet = local_time >= start or local_time < end

    if not is_quiet:
        return False, None

    end_local = local_now.replace(hour=end.hour, minute=end.minute, second=0, microsecond=0)
    if end_local <= local_now:
        end_local += timedelta(days=1)
    return True, end_local.astimezone(timezone.utc)


def is_due(task: Task, now: datetime) -> bool:
    """Pure predicate mirroring the SQL in select_due_tasks().

    Kept in lockstep with that query so the behaviour can be unit-tested
    without a database. If you change one, change both.
    """
    if task.status not in NOTIFIABLE_STATUSES:
        return False
    if task.snoozed_until is not None:
        # An active snooze silences the task outright. Previously this was
        # OR'd with next_due_at, so a snoozed task with a passed cursor still
        # fired — snooze didn't actually snooze.
        return task.snoozed_until <= now
    return task.next_due_at is not None and task.next_due_at <= now


def select_due_tasks(db: Session, now: datetime) -> list[Task]:
    return (
        db.query(Task)
        .filter(
            Task.status.in_(NOTIFIABLE_STATUSES),
            or_(
                Task.snoozed_until.is_not(None) & (Task.snoozed_until <= now),
                Task.snoozed_until.is_(None)
                & Task.next_due_at.is_not(None)
                & (Task.next_due_at <= now),
            ),
        )
        .all()
    )


def mark_notified(task: Task, now: datetime, *, sent: bool) -> None:
    """Advance the cursor after a notification attempt.

    IMPORTANT: this must never touch `last_action_client_ts`. That field is the
    last-write-wins guard for *client* actions; stamping it with server time
    would make every subsequent user action with an older client_timestamp get
    silently discarded, leaving the task permanently unactionable.
    """
    task.snoozed_until = None
    if task.status == TaskStatus.snoozed:
        # The snooze has elapsed and we just notified — it is pending again.
        task.status = TaskStatus.pending

    if sent:
        task.last_notified_at = now
        task.notify_count = (task.notify_count or 0) + 1
        task.next_due_at = now + timedelta(minutes=settings.REMINDER_REPEAT_MINUTES)
    else:
        # Nothing actually reached the user, so don't count it as a reminder;
        # just back off briefly and try again.
        task.next_due_at = now + timedelta(minutes=settings.REMINDER_RETRY_MINUTES)


def defer_to(task: Task, when: datetime) -> None:
    """Postpone without notifying (quiet hours, reminders disabled).

    Does not touch notify_count — the user was never disturbed.
    """
    if task.snoozed_until is not None and task.snoozed_until <= when:
        # Don't silently extend the snooze past its natural end; the deferral
        # belongs on next_due_at.
        task.snoozed_until = None
    task.next_due_at = when


def _process_one(db: Session, task: Task, now: datetime) -> None:
    user = db.query(User).filter(User.id == task.user_id).first()
    if not user:
        # Orphaned row — park the cursor so it stops being rescanned.
        task.next_due_at = None
        return

    if not user.reminders_enabled:
        # Push the cursor forward instead of `continue`-ing, otherwise this
        # task is re-selected and re-examined on every 60s tick forever.
        defer_to(task, now + timedelta(minutes=settings.REMINDER_REPEAT_MINUTES))
        return

    is_quiet, push_to = _in_quiet_hours(user, now)
    if is_quiet and push_to:
        logger.info("[Beat] Task %s deferred — user in quiet hours until %s", task.id, push_to.isoformat())
        defer_to(task, push_to)
        return

    devices = (
        db.query(Device)
        .filter(Device.user_id == user.id, Device.push_enabled == True)  # noqa: E712
        .all()
    )
    if not devices:
        logger.debug("[Beat] Task %s has no push-enabled devices — backing off", task.id)
        mark_notified(task, now, sent=False)
        return

    due_at_iso = (task.next_due_at or task.snoozed_until or task.due_at or now).isoformat()
    payload = push_service.build_reminder_payload(str(task.id), task.title, due_at_iso, str(user.id))

    sent_any = False
    for device in devices:
        try:
            if push_service.send_push(device.push_token, payload):
                sent_any = True
                db.add(NotificationLog(task_id=task.id, channel="push", device_id=device.id))
        except GoneException:
            logger.info("[Push] Removing expired subscription — device %s (task %s)", device.id, task.id)
            db.delete(device)
        except Exception as exc:
            logger.warning("[Push] Push to device %s failed: %s", device.id, exc)

    mark_notified(task, now, sent=sent_any)


def _check_due_reminders_sync(session_factory=None):
    from app.database import SyncSessionLocal

    session_factory = session_factory or SyncSessionLocal
    now = datetime.now(timezone.utc)
    logger.info("[Beat] check_due_reminders — starting at %s", now.isoformat())

    with session_factory() as db:
        due_tasks = select_due_tasks(db, now)
        logger.info("[Beat] check_due_reminders — found %d due task(s)", len(due_tasks))

        for task in due_tasks:
            # Commit per task. A single commit for the whole tick meant one bad
            # row rolled back everyone's bookkeeping *after* their pushes had
            # already gone out — guaranteeing duplicates on the next tick.
            try:
                _process_one(db, task, now)
                db.commit()
            except Exception:
                db.rollback()
                logger.exception("[Beat] Task %s failed to process — continuing", task.id)

    logger.info("[Beat] check_due_reminders — done")


@celery_app.task(name="app.workers.reminder_tasks.check_due_reminders")
def check_due_reminders():
    _check_due_reminders_sync()
