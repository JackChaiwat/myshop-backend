"""alter otp_codes purpose length to 100

Revision ID: f1a2b3c4d5e6
Revises: 786cdbad3539
Create Date: 2026-04-25 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'f1a2b3c4d5e6'
down_revision = '786cdbad3539'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column('otp_codes', 'purpose',
        existing_type=sa.String(30),
        type_=sa.String(100),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column('otp_codes', 'purpose',
        existing_type=sa.String(100),
        type_=sa.String(30),
        existing_nullable=False,
    )
