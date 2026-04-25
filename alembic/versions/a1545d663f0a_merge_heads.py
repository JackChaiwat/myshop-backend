"""merge_heads

Revision ID: a1545d663f0a
Revises: a1b2c3d4e5f6, d648719b886f
Create Date: 2026-04-22 14:21:16.069846

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1545d663f0a'
down_revision: Union[str, None] = ('a1b2c3d4e5f6', 'd648719b886f')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
