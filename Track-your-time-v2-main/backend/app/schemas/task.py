from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.task import TaskStatus, Recurrence, TaskSource


class TaskNoteIn(BaseModel):
    text: str
    done: bool = False
    order_index: int = 0


class TaskNoteOut(TaskNoteIn):
    id: UUID
    model_config = {"from_attributes": True}


class TaskCreate(BaseModel):
    title: str
    recurrence: Recurrence = Recurrence.none
    due_at: datetime | None = None
    interval_minutes: int | None = None
    category: str | None = None
    source: TaskSource = TaskSource.text
    notes: list[TaskNoteIn] = []


class TaskUpdate(BaseModel):
    title: str | None = None
    status: TaskStatus | None = None
    recurrence: Recurrence | None = None
    due_at: datetime | None = None
    interval_minutes: int | None = None
    category: str | None = None


class TaskOut(BaseModel):
    id: UUID
    user_id: UUID
    title: str
    status: TaskStatus
    recurrence: Recurrence
    due_at: datetime | None
    anchor_time: datetime | None
    interval_minutes: int | None
    next_due_at: datetime | None
    snoozed_until: datetime | None
    snoozed_count_today: int
    snoozed_count_total: int
    last_notified_at: datetime | None = None
    notify_count: int = 0
    category: str | None
    source: TaskSource
    created_at: datetime
    updated_at: datetime
    notes: list[TaskNoteOut] = []

    model_config = {"from_attributes": True}


class TaskActionRequest(BaseModel):
    action: str = Field(description="One of: done, snooze, start, block, reopen")
    client_timestamp: datetime
    snooze_minutes: int | None = Field(default=None, description="Required when action == snooze")
