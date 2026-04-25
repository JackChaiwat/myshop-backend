"""merge heads: coupons_settings + chat_messages

Revision ID: d2e3f4a5b6c7
Revises: b7d4c1aaddb7, c1a2b3d4e5f6
Create Date: 2026-04-24 00:01:00.000000
"""
from typing import Sequence, Union

revision: str = 'd2e3f4a5b6c7'
down_revision: Union[str, None] = ('b7d4c1aaddb7', 'c1a2b3d4e5f6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
