"""Add reminder repeat tracking (last_notified_at, notify_count)

Supports "re-notify until the user acts". Previously the scheduler nulled its
due cursor after sending, so a one-off task fired exactly twice and then went
silent forever, while a recurring task fell through to a due_at fallback that
re-fired every 60 seconds regardless of its interval.

Revision ID: e5f6a1b2c3d4
Revises: 3a411409b853
Create Date: 2026-07-25 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'e5f6a1b2c3d4'
down_revision: Union[str, None] = '3a411409b853'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('tasks', sa.Column('last_notified_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        'tasks',
        sa.Column('notify_count', sa.Integer(), nullable=False, server_default='0'),
    )

    # Composite index matching the new scan predicate exactly.
    op.create_index('ix_tasks_scheduler_scan', 'tasks', ['status', 'next_due_at'])

    # Backfill. The old scheduler nulled next_due_at after firing and relied on
    # the due_at fallback (now deleted) to pick the task up again. Without this
    # those live tasks would have no cursor at all and go permanently silent.
    op.execute(
        """
        UPDATE tasks
           SET next_due_at = due_at
         WHERE next_due_at IS NULL
           AND due_at IS NOT NULL
           AND status IN ('pending', 'in_progress', 'snoozed')
        """
    )


def downgrade() -> None:
    op.drop_index('ix_tasks_scheduler_scan', table_name='tasks')
    op.drop_column('tasks', 'notify_count')
    op.drop_column('tasks', 'last_notified_at')
