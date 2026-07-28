import inspect
from datetime import date, datetime, time, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import ActivitySource, ActivityType, ReminderActivity
from app.models.task import Task
from app.models.user import User


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _coerce_type(activity_type: ActivityType | str) -> ActivityType:
    return activity_type if isinstance(activity_type, ActivityType) else ActivityType(activity_type)


def _coerce_source(source: ActivitySource | str) -> ActivitySource:
    return source if isinstance(source, ActivitySource) else ActivitySource(source)


def _task_title(task: Task | None, fallback: str | None) -> str:
    title = fallback or (task.title if task is not None else None)
    return (title or "General activity").strip()[:500]


async def record_activity(
    db: AsyncSession,
    *,
    user_id: UUID,
    activity_type: ActivityType | str,
    source: ActivitySource | str,
    task: Task | None = None,
    task_id: UUID | None = None,
    task_title: str | None = None,
    optional_notes: str | None = None,
    metadata: dict[str, Any] | None = None,
    timestamp: datetime | None = None,
) -> ReminderActivity:
    """
    Append one canonical activity row without committing the transaction.

    Callers should invoke this exactly once per successful user-visible action,
    then commit alongside the state change that caused the activity.
    """
    if task is not None:
        task_id = task.id

    activity = ReminderActivity(
        user_id=user_id,
        task_id=task_id,
        activity_type=_coerce_type(activity_type),
        task_title=_task_title(task, task_title),
        optional_notes=optional_notes[:1000] if optional_notes else None,
        source=_coerce_source(source),
        timestamp=timestamp or _now(),
        metadata_json=metadata,
    )
    add_result = db.add(activity)
    if inspect.isawaitable(add_result):
        await add_result
    await db.flush()
    return activity


def day_bounds(target_date: date, timezone_name: str | None) -> tuple[datetime, datetime]:
    from zoneinfo import ZoneInfo

    tz = ZoneInfo(timezone_name or "UTC")
    start_local = datetime.combine(target_date, time.min, tzinfo=tz)
    end_local = datetime.combine(target_date, time.max, tzinfo=tz)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def local_today(timezone_name: str | None) -> date:
    from zoneinfo import ZoneInfo

    tz = ZoneInfo(timezone_name or "UTC")
    return datetime.now(tz).date()


def activities_query(
    user: User,
    *,
    today: bool = False,
    target_date: date | None = None,
    activity_type: ActivityType | None = None,
    source: ActivitySource | None = None,
) -> Select[tuple[ReminderActivity]]:
    statement = select(ReminderActivity).where(ReminderActivity.user_id == user.id)

    if today or target_date is not None:
        chosen_date = target_date or local_today(user.timezone)
        start_utc, end_utc = day_bounds(chosen_date, user.timezone)
        statement = statement.where(
            ReminderActivity.timestamp >= start_utc,
            ReminderActivity.timestamp <= end_utc,
        )

    if activity_type is not None:
        statement = statement.where(ReminderActivity.activity_type == activity_type)

    if source is not None:
        statement = statement.where(ReminderActivity.source == source)

    return statement.order_by(ReminderActivity.timestamp.desc())
