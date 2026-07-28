"""
ReminderActivity model.

Stores one structured activity row for every reminder response submitted by a user
(via voice or text).  Intent extraction happens in ``intent_service`` before
this row is written; this table is the canonical persistence layer.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, Enum, Index, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ActivityType(str, enum.Enum):
    created = "created"
    started = "started"
    working = "working"
    updated = "updated"
    completed = "completed"
    blocked = "blocked"
    resumed = "resumed"
    snoozed = "snoozed"
    deleted = "deleted"
    reminder_response = "reminder_response"
    hourly_checkin = "hourly_checkin"
    voice_update = "voice_update"
    text_update = "text_update"
    companion_action = "companion_action"
    status_update = "status_update"


class ActivitySource(str, enum.Enum):
    voice = "voice"
    text = "text"
    task = "task"
    reminder = "reminder"
    checkin = "checkin"
    companion = "companion"
    system = "system"


class ReminderActivity(Base):
    """
    Immutable record of a single reminder response event.

    Every time a user responds to a reminder (by speaking or typing), one row
    is appended here with the structured outcome of intent extraction.
    """

    __tablename__ = "reminder_activities"
    __table_args__ = (
        Index("ix_reminder_activities_user_id", "user_id"),
        Index("ix_reminder_activities_timestamp", "timestamp"),
        Index("ix_reminder_activities_user_ts", "user_id", "timestamp"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Optional back-reference to the task the user was responding about.
    # SET NULL on delete so activity history survives task deletion.
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    activity_type: Mapped[ActivityType] = mapped_column(
        Enum(ActivityType, name="activity_type_enum"),
        nullable=False,
    )

    # Extracted task title from the utterance (e.g. "authentication", "frontend")
    task_title: Mapped[str] = mapped_column(String(500), nullable=False)

    # Remainder of the utterance after intent + title extraction
    # (e.g. "Docker won't start" when blocked)
    optional_notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    source: Mapped[ActivitySource] = mapped_column(
        Enum(ActivitySource, name="activity_source_enum"),
        nullable=False,
    )

    metadata_json: Mapped[dict | None] = mapped_column(
        "metadata",
        JSON,
        nullable=True,
    )

    # UTC timestamp of when the activity was recorded
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )

    # Relationships
    user: Mapped["User"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "User", foreign_keys=[user_id]
    )
    task: Mapped["Task | None"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Task", foreign_keys=[task_id]
    )
