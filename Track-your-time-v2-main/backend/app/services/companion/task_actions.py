"""
task_actions.py — Executes database side-effects based on the parsed LLM intent.

Actions:
- chat_only
- set_current_task
- complete_task
- create_task
- list_tasks
- log_productivity
- update_task
- block_task
- resume_task
- unknown
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.companion import CurrentTask, ProductivityLog, ProductivityStatus
from app.models.activity import ActivitySource, ActivityType
from app.models.task import Recurrence, Task, TaskSource, TaskStatus
from app.models.user import User
from app.services import activity_service
from app.services.companion.intent_parser import ParsedIntent
from app.services.task_service import apply_action

_UTC = timezone.utc


def _now() -> datetime:
    return datetime.now(_UTC)


async def _find_task_by_name(
    db: AsyncSession, user_id: uuid.UUID, task_name: str
) -> Optional[Task]:
    """Find a pending task by title (case-insensitive substring match)."""
    result = await db.execute(
        select(Task).where(
            Task.user_id == user_id,
            Task.title.ilike(f"%{task_name}%"),
            Task.status.notin_([TaskStatus.done, TaskStatus.blocked]),
        )
    )
    # Return the first match or None
    return result.scalars().first()


async def execute_intent(db: AsyncSession, user: User, intent: ParsedIntent) -> bool:
    """
    Executes the DB side effects for the given intent.
    Does NOT commit the transaction; the caller is responsible for committing.
    Returns True when it records an activity.
    """
    now = _now()

    if intent.action in ("chat_only", "list_tasks", "unknown"):
        # No DB side effects for these actions.
        return False

    elif intent.action == "set_current_task":
        resolved_task_id = None
        if intent.task_id:
            try:
                resolved_task_id = uuid.UUID(intent.task_id)
            except ValueError:
                pass

        if not resolved_task_id and intent.task_name:
            task = await _find_task_by_name(db, user.id, intent.task_name)
            if task:
                resolved_task_id = task.id

        ct_result = await db.execute(
            select(CurrentTask).where(CurrentTask.user_id == user.id)
        )
        record = ct_result.scalar_one_or_none()

        if record is None:
            record = CurrentTask(
                user_id=user.id,
                task_id=resolved_task_id,
                is_active=True,
                started_at=now,
                updated_at=now,
            )
            db.add(record)
        else:
            was_inactive = not record.is_active
            record.task_id = resolved_task_id
            record.is_active = True
            record.updated_at = now
            if was_inactive:
                record.started_at = now
        await activity_service.record_activity(
            db,
            user_id=user.id,
            task_id=resolved_task_id,
            activity_type=ActivityType.working,
            source=ActivitySource.companion,
            task_title=intent.task_name or "Current task",
            optional_notes=intent.note,
            timestamp=now,
            metadata={"event": "companion_set_current_task", "action": intent.action},
        )
        return True

    elif intent.action == "complete_task":
        task_to_complete = None
        if intent.task_id:
            try:
                tid = uuid.UUID(intent.task_id)
                res = await db.execute(
                    select(Task).where(Task.id == tid, Task.user_id == user.id)
                )
                task_to_complete = res.scalar_one_or_none()
            except ValueError:
                pass

        if not task_to_complete and intent.task_name:
            task_to_complete = await _find_task_by_name(db, user.id, intent.task_name)

        if not task_to_complete:
            # Fall back to completing the current focus task
            ct_result = await db.execute(
                select(CurrentTask).where(CurrentTask.user_id == user.id)
            )
            record = ct_result.scalar_one_or_none()
            if record and record.task_id:
                res = await db.execute(
                    select(Task).where(Task.id == record.task_id, Task.user_id == user.id)
                )
                task_to_complete = res.scalar_one_or_none()

        if task_to_complete:
            changed = apply_action(task_to_complete, "done", now)
            if changed:
                await activity_service.record_activity(
                    db,
                    user_id=user.id,
                    task=task_to_complete,
                    activity_type=ActivityType.completed,
                    source=ActivitySource.companion,
                    timestamp=now,
                    metadata={"event": "companion_task_action", "action": intent.action},
                )
                return True
        return False

    elif intent.action == "create_task":
        if intent.task_name:
            new_task = Task(
                id=uuid.uuid4(),
                user_id=user.id,
                title=intent.task_name,
                recurrence=Recurrence.none,
                status=TaskStatus.pending,
                source=TaskSource.text,
            )
            db.add(new_task)
            await activity_service.record_activity(
                db,
                user_id=user.id,
                task=new_task,
                activity_type=ActivityType.created,
                source=ActivitySource.companion,
                timestamp=now,
                metadata={"event": "companion_task_action", "action": intent.action},
            )
            return True
        return False

    elif intent.action == "update_task":
        if intent.task_name:
            task_to_update = None
            if intent.task_id:
                try:
                    tid = uuid.UUID(intent.task_id)
                    res = await db.execute(
                        select(Task).where(Task.id == tid, Task.user_id == user.id)
                    )
                    task_to_update = res.scalar_one_or_none()
                except ValueError:
                    pass
            
            if not task_to_update:
                task_to_update = await _find_task_by_name(db, user.id, intent.task_name)
                
            if task_to_update:
                task_to_update.title = intent.task_name
                task_to_update.updated_at = now
                await activity_service.record_activity(
                    db,
                    user_id=user.id,
                    task=task_to_update,
                    activity_type=ActivityType.updated,
                    source=ActivitySource.companion,
                    timestamp=now,
                    metadata={"event": "companion_task_action", "action": intent.action},
                )
                return True
        return False
                
    elif intent.action in ("block_task", "resume_task"):
        task_to_toggle = None
        if intent.task_id:
            try:
                tid = uuid.UUID(intent.task_id)
                res = await db.execute(
                    select(Task).where(Task.id == tid, Task.user_id == user.id)
                )
                task_to_toggle = res.scalar_one_or_none()
            except ValueError:
                pass
                
        if not task_to_toggle and intent.task_name:
            task_to_toggle = await _find_task_by_name(db, user.id, intent.task_name)
            
        if not task_to_toggle:
            # Fallback to current focus task
            ct_result = await db.execute(
                select(CurrentTask).where(CurrentTask.user_id == user.id)
            )
            record = ct_result.scalar_one_or_none()
            if record and record.task_id:
                res = await db.execute(
                    select(Task).where(Task.id == record.task_id, Task.user_id == user.id)
                )
                task_to_toggle = res.scalar_one_or_none()
                
        if task_to_toggle:
            action_name = "block" if intent.action == "block_task" else "reopen"
            changed = apply_action(task_to_toggle, action_name, now)
            if changed:
                await activity_service.record_activity(
                    db,
                    user_id=user.id,
                    task=task_to_toggle,
                    activity_type=(
                        ActivityType.blocked
                        if intent.action == "block_task"
                        else ActivityType.resumed
                    ),
                    source=ActivitySource.companion,
                    optional_notes=intent.note,
                    timestamp=now,
                    metadata={"event": "companion_task_action", "action": intent.action},
                )
                return True
        return False

    elif intent.action == "log_productivity":
        status_val = (
            ProductivityStatus(intent.productivity_status)
            if intent.productivity_status
            else ProductivityStatus.focused
        )
        duration = (intent.duration_minutes * 60) if intent.duration_minutes else None

        start_at = now
        if duration:
            start_at = now - timedelta(seconds=duration)

        # Attempt to associate this log with the current task
        task_id = None
        ct_result = await db.execute(
            select(CurrentTask).where(CurrentTask.user_id == user.id)
        )
        record = ct_result.scalar_one_or_none()
        if record and record.task_id:
            task_id = record.task_id

        log = ProductivityLog(
            id=uuid.uuid4(),
            user_id=user.id,
            task_id=task_id,
            status=status_val,
            start_at=start_at,
            end_at=now if duration else None,
            duration_seconds=duration,
            note=intent.note,
        )
        db.add(log)
        await activity_service.record_activity(
            db,
            user_id=user.id,
            task_id=task_id,
            activity_type=ActivityType.companion_action,
            source=ActivitySource.companion,
            task_title="Productivity log",
            optional_notes=intent.note,
            timestamp=now,
            metadata={
                "event": "companion_productivity_log",
                "status": status_val.value,
                "duration_seconds": duration,
            },
        )
        return True

    return False
