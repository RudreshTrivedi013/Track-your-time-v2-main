"""merge

Revision ID: 4b7ec721f457
Revises: 9c51f800dc41, d4e5f6a1b2c3
Create Date: 2026-07-20 12:37:12.409443

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4b7ec721f457'
down_revision: Union[str, None] = ('9c51f800dc41', 'd4e5f6a1b2c3')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
