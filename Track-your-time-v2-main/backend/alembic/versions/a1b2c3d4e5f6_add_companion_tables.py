"""add companion tables

Revision ID: a1b2c3d4e5f6
Revises: 66914678e306
Create Date: 2026-07-02 14:11:00

Tables added
------------
- productivity_logs
- current_task
- chat_messages

Enum types added
----------------
- productivity_status
- message_role
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "66914678e306"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # Create ENUM types first (PostgreSQL requires them to exist before
    # the columns that reference them are created).
    # ------------------------------------------------------------------
    productivity_status = postgresql.ENUM(
        "focused", "distracted", "break", "idle",
        name="productivity_status",
        create_type=False,
    )
    productivity_status.create(op.get_bind(), checkfirst=True)

    message_role = postgresql.ENUM(
        "user", "assistant", "system",
        name="message_role",
        create_type=False,
    )
    message_role.create(op.get_bind(), checkfirst=True)

    # ------------------------------------------------------------------
    # productivity_logs
    # ------------------------------------------------------------------
    op.create_table(
        "productivity_logs",
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
        sa.Column(
            "status",
            productivity_status,
            nullable=False,
            server_default="idle",
        ),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("note", sa.String(1000), nullable=True),
    )
    op.create_index("ix_productivity_logs_user_id", "productivity_logs", ["user_id"])
    op.create_index("ix_productivity_logs_start_at", "productivity_logs", ["start_at"])
    op.create_index(
        "ix_productivity_logs_user_start",
        "productivity_logs",
        ["user_id", "start_at"],
    )
    op.create_index(
        "ix_productivity_logs_task_id", "productivity_logs", ["task_id"]
    )

    # ------------------------------------------------------------------
    # current_task
    # (user_id IS the primary key — one row per user, upsert-friendly)
    # ------------------------------------------------------------------
    op.create_table(
        "current_task",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "task_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tasks.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("context_note", sa.String(2000), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_current_task_task_id", "current_task", ["task_id"])

    # ------------------------------------------------------------------
    # chat_messages
    # ------------------------------------------------------------------
    op.create_table(
        "chat_messages",
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
        sa.Column("role", message_role, nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_chat_messages_user_id", "chat_messages", ["user_id"])
    op.create_index(
        "ix_chat_messages_user_created",
        "chat_messages",
        ["user_id", "created_at"],
    )
    op.create_index("ix_chat_messages_task_id", "chat_messages", ["task_id"])


def downgrade() -> None:
    op.drop_table("chat_messages")
    op.drop_table("current_task")
    op.drop_table("productivity_logs")
    op.execute("DROP TYPE IF EXISTS productivity_status")
    op.execute("DROP TYPE IF EXISTS message_role")
