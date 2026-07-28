"""initial schema

Revision ID: 66914678e306
Revises:
Create Date: 2026-06-30 00:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "66914678e306"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="UTC"),
        sa.Column("primary_device_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("quiet_hours_start", sa.Time(), nullable=True),
        sa.Column("quiet_hours_end", sa.Time(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "devices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("push_token", sa.String(2000), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("last_active_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("push_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_devices_user_id", "devices", ["user_id"])

    op.create_foreign_key(
        "fk_user_primary_device", "users", "devices", ["primary_device_id"], ["id"], ondelete="SET NULL"
    )

    task_status = postgresql.ENUM("pending", "in_progress", "done", "snoozed", "blocked", name="task_status", create_type=False)
    recurrence_type = postgresql.ENUM("none", "interval", "daily", "weekly", name="recurrence_type", create_type=False)
    task_source = postgresql.ENUM("voice", "text", name="task_source", create_type=False)
    task_status.create(op.get_bind(), checkfirst=True)
    recurrence_type.create(op.get_bind(), checkfirst=True)
    task_source.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("status", task_status, nullable=False, server_default="pending"),
        sa.Column("recurrence", recurrence_type, nullable=False, server_default="none"),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("anchor_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("interval_minutes", sa.Integer(), nullable=True),
        sa.Column("next_due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("snoozed_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("snoozed_count_today", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("snoozed_count_total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("source", task_source, nullable=False, server_default="text"),
        sa.Column("last_action_client_ts", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_tasks_user_id", "tasks", ["user_id"])
    op.create_index("ix_tasks_next_due_at", "tasks", ["next_due_at"])
    op.create_index("ix_tasks_status", "tasks", ["status"])

    op.create_table(
        "task_notes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("text", sa.String(1000), nullable=False),
        sa.Column("done", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_task_notes_task_id", "task_notes", ["task_id"])

    op.create_table(
        "notifications_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("channel", sa.String(50), nullable=False, server_default="push"),
        sa.Column("acknowledged", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("action", sa.String(50), nullable=True),
        sa.Column("client_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("device_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("devices.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_notifications_log_task_id", "notifications_log", ["task_id"])


def downgrade() -> None:
    op.drop_table("notifications_log")
    op.drop_table("task_notes")
    op.drop_table("tasks")
    op.execute("DROP TYPE IF EXISTS task_status")
    op.execute("DROP TYPE IF EXISTS recurrence_type")
    op.execute("DROP TYPE IF EXISTS task_source")
    op.drop_constraint("fk_user_primary_device", "users", type_="foreignkey")
    op.drop_table("devices")
    op.drop_table("users")
