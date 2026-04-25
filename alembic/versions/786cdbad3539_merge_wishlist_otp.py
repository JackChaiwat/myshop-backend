"""merge_wishlist_otp

Revision ID: 786cdbad3539
Revises: b2c3d4e5f6a7, e1f2a3b4c5d6
Create Date: 2026-04-25 07:33:57.181494

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '786cdbad3539'
down_revision: Union[str, None] = ('b2c3d4e5f6a7', 'e1f2a3b4c5d6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
