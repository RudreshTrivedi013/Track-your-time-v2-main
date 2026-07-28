"""add hourly checkin reminders

Revision ID: d4e5f6a1b2c3
Revises: c3d4e5f6a1b2
Create Date: 2026-07-17 12:00:00

Tables added
------------
- hourly_checkin_reminders

Enum types added
----------------
- hourly_checkin_reminder_status
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "d4e5f6a1b2c3"
down_revision: Union[str, None] = "c3d4e5f6a1b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    hourly_checkin_reminder_status = postgresql.ENUM(
        "pending",
        "completed",
        "missed",
        name="hourly_checkin_reminder_status",
        create_type=False,
    )
    hourly_checkin_reminder_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "hourly_checkin_reminders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("scheduled_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "status",
            hourly_checkin_reminder_status,
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "response_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("productivity_logs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index(
        "ix_hourly_checkin_reminders_user_id",
        "hourly_checkin_reminders",
        ["user_id"],
    )
    op.create_index(
        "ix_hourly_checkin_reminders_scheduled_time",
        "hourly_checkin_reminders",
        ["scheduled_time"],
    )
    op.create_index(
        "ix_hourly_checkin_reminders_user_scheduled_time",
        "hourly_checkin_reminders",
        ["user_id", "scheduled_time"],
    )


def downgrade() -> None:
    op.drop_index("ix_hourly_checkin_reminders_user_scheduled_time", "hourly_checkin_reminders")
    op.drop_index("ix_hourly_checkin_reminders_scheduled_time", "hourly_checkin_reminders")
    op.drop_index("ix_hourly_checkin_reminders_user_id", "hourly_checkin_reminders")
    op.drop_table("hourly_checkin_reminders")
    op.execute("DROP TYPE IF EXISTS hourly_checkin_reminder_status")
