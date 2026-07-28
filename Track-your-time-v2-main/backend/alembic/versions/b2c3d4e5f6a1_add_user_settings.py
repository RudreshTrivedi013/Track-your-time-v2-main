"""add user settings

Revision ID: b2c3d4e5f6a1
Revises: a1b2c3d4e5f6
Create Date: 2026-07-02 22:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a1'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new columns to users table
    op.add_column('users', sa.Column('working_hours_start', sa.Time(), nullable=False, server_default='09:00:00'))
    op.add_column('users', sa.Column('working_hours_end', sa.Time(), nullable=False, server_default='17:00:00'))
    op.add_column('users', sa.Column('checkin_interval_minutes', sa.Integer(), nullable=False, server_default='60'))
    op.add_column('users', sa.Column('daily_summary_enabled', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('users', sa.Column('reminders_enabled', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('users', sa.Column('checkin_enabled', sa.Boolean(), nullable=False, server_default='true'))


def downgrade() -> None:
    op.drop_column('users', 'checkin_enabled')
    op.drop_column('users', 'reminders_enabled')
    op.drop_column('users', 'daily_summary_enabled')
    op.drop_column('users', 'checkin_interval_minutes')
    op.drop_column('users', 'working_hours_end')
    op.drop_column('users', 'working_hours_start')
