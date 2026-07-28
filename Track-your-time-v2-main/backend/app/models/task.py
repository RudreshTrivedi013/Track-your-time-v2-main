import enum
import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, Integer, Enum, Index, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TaskStatus(str, enum.Enum):
    pending = "pending"
    in_progress = "in_progress"
    done = "done"
    snoozed = "snoozed"
    blocked = "blocked"


class Recurrence(str, enum.Enum):
    none = "none"
    interval = "interval"
    daily = "daily"
    weekly = "weekly"


class TaskSource(str, enum.Enum):
    voice = "voice"
    text = "text"


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        Index("ix_tasks_user_id", "user_id"),
        Index("ix_tasks_next_due_at", "next_due_at"),
        Index("ix_tasks_status", "status"),
        # Matches the scheduler's scan predicate (status IN (...) AND next_due_at <= now).
        Index("ix_tasks_scheduler_scan", "status", "next_due_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[TaskStatus] = mapped_column(Enum(TaskStatus, name="task_status"), default=TaskStatus.pending, nullable=False)

    recurrence: Mapped[Recurrence] = mapped_column(Enum(Recurrence, name="recurrence_type"), default=Recurrence.none, nullable=False)

    # due_at is DESCRIPTIVE: what the user set, shown in the UI and used to
    # anchor recurrence. The scheduler must never read it — see next_due_at.
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # anchor_time: the original reference instant recurrence math is always computed from,
    # never from "now", so repeated completions don't drift the schedule.
    anchor_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    interval_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # next_due_at is the SINGLE scheduler cursor: "the next instant we should
    # notify". While a task is still owed a reminder this is always in the
    # future — it is nulled only to mean "stop reminding" (done / muted).
    next_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # snoozed_until SUPPRESSES next_due_at while it is in the future.
    snoozed_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    snoozed_count_today: Mapped[int] = mapped_column(Integer, default=0)
    snoozed_count_total: Mapped[int] = mapped_column(Integer, default=0)

    # Repeat-until-acknowledged bookkeeping. notify_count also tells
    # apply_action whether next_due_at currently holds a real recurrence
    # occurrence (0) or a nag cursor (>0) — see the snooze merge logic.
    last_notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notify_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False, server_default="0")

    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source: Mapped[TaskSource] = mapped_column(Enum(TaskSource, name="task_source"), default=TaskSource.text, nullable=False)

    # last_write_wins guard: the client_timestamp of the last action applied
    last_action_client_ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="tasks", foreign_keys=[user_id])
    notes: Mapped[list["TaskNote"]] = relationship(back_populates="task", cascade="all, delete-orphan", order_by="TaskNote.order_index")


class TaskNote(Base):
    __tablename__ = "task_notes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    text: Mapped[str] = mapped_column(String(1000), nullable=False)
    done: Mapped[bool] = mapped_column(Boolean, default=False)
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    task: Mapped["Task"] = relationship(back_populates="notes")
