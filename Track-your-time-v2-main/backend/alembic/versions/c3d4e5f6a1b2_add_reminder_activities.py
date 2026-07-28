"""add reminder_activities table
Revision ID: c3d4e5f6a1b2
Revises: b2c3d4e5f6a1
Create Date: 2026-07-04 17:41:00
Tables added
------------
- reminder_activities
Enum types added
----------------
- activity_type_enum   (started, working, completed, blocked, status_update)
- activity_source_enum (voice, text)
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision: str = "c3d4e5f6a1b2"
down_revision: Union[str, None] = "b2c3d4e5f6a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
def upgrade() -> None:
    # ------------------------------------------------------------------
    # Create ENUM types first
    # ------------------------------------------------------------------
    activity_type_enum = postgresql.ENUM(
        "started", "working", "completed", "blocked", "status_update",
        name="activity_type_enum",
        create_type=False,
    )
    activity_type_enum.create(op.get_bind(), checkfirst=True)
    activity_source_enum = postgresql.ENUM(
        "voice", "text",
        name="activity_source_enum",
        create_type=False,
    )
    activity_source_enum.create(op.get_bind(), checkfirst=True)
    # ------------------------------------------------------------------
    # reminder_activities
    # ------------------------------------------------------------------
    op.create_table(
        "reminder_activities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "task_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tasks.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("activity_type", activity_type_enum, nullable=False),
        sa.Column("task_title", sa.String(500), nullable=False),
        sa.Column("optional_notes", sa.String(1000), nullable=True),
        sa.Column("source", activity_source_enum, nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_reminder_activities_user_id", "reminder_activities", ["user_id"]
    )
    op.create_index(
        "ix_reminder_activities_timestamp", "reminder_activities", ["timestamp"]
    )
    op.create_index(
        "ix_reminder_activities_user_ts",
        "reminder_activities",
        ["user_id", "timestamp"],
    )
    op.create_index(
        "ix_reminder_activities_task_id", "reminder_activities", ["task_id"]
    )
def downgrade() -> None:
    op.drop_index("ix_reminder_activities_task_id", "reminder_activities")
    op.drop_index("ix_reminder_activities_user_ts", "reminder_activities")
    op.drop_index("ix_reminder_activities_timestamp", "reminder_activities")
    op.drop_index("ix_reminder_activities_user_id", "reminder_activities")
    op.drop_table("reminder_activities")
    op.execute("DROP TYPE IF EXISTS activity_type_enum")
    op.execute("DROP TYPE IF EXISTS activity_source_enum")