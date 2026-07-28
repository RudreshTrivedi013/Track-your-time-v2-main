"""
context_builder.py — collects everything the AI needs to answer intelligently.

Responsibilities
----------------
- Fetch the user's current focus task (current_task table).
- Fetch pending tasks (tasks table, status != done).
- Fetch tasks completed today.
- Fetch the last N chat messages (conversation memory).
- Fetch today's productivity log entries.
- Return a single ``CompanionContext`` dataclass.

The context object is intentionally plain Python (no SQLAlchemy objects) so it
can be freely serialised into the system prompt without hitting lazy-load traps.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.companion import ChatMessage, CurrentTask, MessageRole, ProductivityLog
from app.models.task import Task, TaskStatus

_UTC = timezone.utc

# How many recent chat messages to include in context
_HISTORY_WINDOW = 10
# How many completed-today tasks to list
_DONE_TODAY_LIMIT = 10


# ---------------------------------------------------------------------------
# Plain-data structures (no ORM objects escape this module)
# ---------------------------------------------------------------------------


@dataclass
class TaskSnapshot:
    id: str
    title: str
    status: str
    due_at: Optional[str]
    category: Optional[str]


@dataclass
class ChatTurn:
    role: str   # "user" | "assistant"
    content: str


@dataclass
class ProductivitySnapshot:
    status: str
    start_at: str
    duration_seconds: Optional[int]
    note: Optional[str]


@dataclass
class CompanionContext:
    user_id: str
    user_email: str
    current_task: Optional[TaskSnapshot]
    pending_tasks: list[TaskSnapshot]
    completed_today: list[TaskSnapshot]
    recent_chat: list[ChatTurn]
    productivity_logs_today: list[ProductivitySnapshot]
    now_utc: str = field(default_factory=lambda: datetime.now(_UTC).isoformat())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _task_to_snapshot(task: Task) -> TaskSnapshot:
    return TaskSnapshot(
        id=str(task.id),
        title=task.title,
        status=task.status.value,
        due_at=task.due_at.isoformat() if task.due_at else None,
        category=task.category,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def build_context(db: AsyncSession, user) -> CompanionContext:
    """
    Gather all data from the DB and return a self-contained ``CompanionContext``.

    Parameters
    ----------
    db   : async SQLAlchemy session (from FastAPI's get_db dependency)
    user : User ORM instance (from get_current_user)
    """
    now = datetime.now(_UTC)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # ------------------------------------------------------------------
    # 1. Current focus task
    # ------------------------------------------------------------------
    ct_result = await db.execute(
        select(CurrentTask).where(CurrentTask.user_id == user.id)
    )
    ct_record = ct_result.scalar_one_or_none()

    current_task_snapshot: Optional[TaskSnapshot] = None
    if ct_record and ct_record.task_id:
        task_result = await db.execute(
            select(Task).where(Task.id == ct_record.task_id, Task.user_id == user.id)
        )
        ct_task = task_result.scalar_one_or_none()
        if ct_task:
            current_task_snapshot = _task_to_snapshot(ct_task)

    # ------------------------------------------------------------------
    # 2. Pending tasks (everything not done)
    # ------------------------------------------------------------------
    pending_result = await db.execute(
        select(Task)
        .where(
            Task.user_id == user.id,
            Task.status.notin_([TaskStatus.done]),
        )
        .order_by(Task.due_at.asc().nullsfirst())
        .limit(20)
    )
    pending_tasks = [_task_to_snapshot(t) for t in pending_result.scalars().all()]

    # ------------------------------------------------------------------
    # 3. Completed today
    # ------------------------------------------------------------------
    done_result = await db.execute(
        select(Task)
        .where(
            Task.user_id == user.id,
            Task.status == TaskStatus.done,
            Task.updated_at >= today_start,
        )
        .order_by(Task.updated_at.desc())
        .limit(_DONE_TODAY_LIMIT)
    )
    completed_today = [_task_to_snapshot(t) for t in done_result.scalars().all()]

    # ------------------------------------------------------------------
    # 4. Recent chat history (last N turns, oldest first for prompt order)
    # ------------------------------------------------------------------
    chat_result = await db.execute(
        select(ChatMessage)
        .where(
            ChatMessage.user_id == user.id,
            ChatMessage.role.in_([MessageRole.user, MessageRole.assistant]),
        )
        .order_by(ChatMessage.created_at.desc())
        .limit(_HISTORY_WINDOW)
    )
    recent_rows = list(reversed(chat_result.scalars().all()))
    recent_chat = [
        ChatTurn(role=msg.role.value, content=msg.content) for msg in recent_rows
    ]

    # ------------------------------------------------------------------
    # 5. Productivity logs today
    # ------------------------------------------------------------------
    logs_result = await db.execute(
        select(ProductivityLog)
        .where(
            ProductivityLog.user_id == user.id,
            ProductivityLog.start_at >= today_start,
        )
        .order_by(ProductivityLog.start_at.asc())
    )
    productivity_logs_today = [
        ProductivitySnapshot(
            status=log.status.value,
            start_at=log.start_at.isoformat(),
            duration_seconds=log.duration_seconds,
            note=log.note,
        )
        for log in logs_result.scalars().all()
    ]

    return CompanionContext(
        user_id=str(user.id),
        user_email=user.email,
        current_task=current_task_snapshot,
        pending_tasks=pending_tasks,
        completed_today=completed_today,
        recent_chat=recent_chat,
        productivity_logs_today=productivity_logs_today,
        now_utc=now.isoformat(),
    )
