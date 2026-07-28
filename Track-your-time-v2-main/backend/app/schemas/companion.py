"""
Pydantic schemas for the AI Productivity Companion.

Follows the same pattern as app/schemas/task.py:
  - *In / *Create  → request bodies (write)
  - *Out           → response bodies (read), with from_attributes=True
  - *Update        → PATCH bodies (all fields optional)
"""

from datetime import datetime, date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.companion import MessageRole, ProductivityStatus, HourlyReminderStatus


# ---------------------------------------------------------------------------
# ProductivityLog
# ---------------------------------------------------------------------------


class ProductivityLogCreate(BaseModel):
    task_id: UUID | None = None
    reminder_id: UUID | None = None
    status: ProductivityStatus = ProductivityStatus.idle
    start_at: datetime | None = None
    end_at: datetime | None = None
    duration_seconds: int | None = Field(default=None, ge=0)
    note: str | None = Field(default=None, max_length=1000)
    transcript: str | None = Field(default=None, min_length=1, max_length=800)
    source: Literal["voice", "text"] | None = None


class ProductivityLogOut(BaseModel):
    id: UUID
    user_id: UUID
    task_id: UUID | None
    status: ProductivityStatus
    start_at: datetime
    end_at: datetime | None
    duration_seconds: int | None
    note: str | None

    model_config = {"from_attributes": True}


class HourlyCheckinEditRequest(BaseModel):
    """
    Edits a hourly check-in entry after the fact — whether it was already
    answered or missed entirely. No time cutoff: a slot from hours ago is
    just as editable as one from a minute ago.
    """

    status: ProductivityStatus
    note: str | None = Field(default=None, max_length=1000)


class HourlyCheckinReminderOut(BaseModel):
    id: UUID
    user_id: UUID
    scheduled_time: datetime
    status: HourlyReminderStatus
    response_id: UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# CurrentTask
# ---------------------------------------------------------------------------


class CurrentTaskSet(BaseModel):
    """Body for setting / updating the user's current focus task."""

    task_id: UUID | None = Field(
        default=None,
        description="Pass null to clear the current task.",
    )
    context_note: str | None = Field(default=None, max_length=2000)
    is_active: bool = True


class CurrentTaskOut(BaseModel):
    user_id: UUID
    task_id: UUID | None
    context_note: str | None
    is_active: bool
    started_at: datetime | None
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# ChatMessage
# ---------------------------------------------------------------------------


class ChatMessageCreate(BaseModel):
    """Sent by the client when the user types a message to the AI companion."""

    content: str = Field(..., min_length=1, max_length=32_000)
    task_id: UUID | None = None


class ChatMessageOut(BaseModel):
    id: UUID
    user_id: UUID
    task_id: UUID | None
    role: MessageRole
    content: str
    token_count: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatHistoryOut(BaseModel):
    """Paginated list wrapper for the conversation history endpoint."""

    messages: list[ChatMessageOut]
    total: int


# ---------------------------------------------------------------------------
# DailySummary
# ---------------------------------------------------------------------------


class DailySummaryOut(BaseModel):
    id: UUID
    user_id: UUID
    date: date
    content: dict
    created_at: datetime

    model_config = {"from_attributes": True}


class SummaryHistoryOut(BaseModel):
    summaries: list[DailySummaryOut]
    total: int

