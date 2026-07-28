"""expand reminder activities for productivity timeline

Revision ID: 9c51f800dc41
Revises: c3d4e5f6a1b2
Create Date: 2026-07-04 19:03:10.240652

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "9c51f800dc41"
down_revision: Union[str, None] = "c3d4e5f6a1b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ACTIVITY_TYPES = (
    "created",
    "updated",
    "resumed",
    "snoozed",
    "deleted",
    "reminder_response",
    "hourly_checkin",
    "voice_update",
    "text_update",
    "companion_action",
)

ACTIVITY_SOURCES = (
    "task",
    "reminder",
    "checkin",
    "companion",
    "system",
)


def upgrade() -> None:
    for value in ACTIVITY_TYPES:
        op.execute(f"ALTER TYPE activity_type_enum ADD VALUE IF NOT EXISTS '{value}'")

    for value in ACTIVITY_SOURCES:
        op.execute(f"ALTER TYPE activity_source_enum ADD VALUE IF NOT EXISTS '{value}'")

    op.add_column(
        "reminder_activities",
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("reminder_activities", "metadata")
    # PostgreSQL enum values cannot be dropped safely without recreating the
    # type and rewriting dependent columns, so downgrade leaves added values.
