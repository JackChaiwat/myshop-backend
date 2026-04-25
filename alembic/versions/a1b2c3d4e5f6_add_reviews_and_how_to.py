"""add reviews table and how_to to products

Revision ID: a1b2c3d4e5f6
Revises: 7c8770f677b2
Create Date: 2026-04-22 15:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '7c8770f677b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add how_to column to products
    op.add_column('products',
        sa.Column('how_to', postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default='[]')
    )

    # Create reviews table
    op.create_table('reviews',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('product_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('rating', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=True),
        sa.Column('body', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint('rating >= 1 AND rating <= 5', name='review_rating_range'),
    )
    op.create_index('ix_reviews_product_id', 'reviews', ['product_id'])
    op.create_index('ix_reviews_user_product', 'reviews', ['user_id', 'product_id'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_reviews_user_product', table_name='reviews')
    op.drop_index('ix_reviews_product_id', table_name='reviews')
    op.drop_table('reviews')
    op.drop_column('products', 'how_to')

from alembic import op
import sqlalchemy as sa
 
revision = 'a1b2c3d4e5f6'
down_revision = None  # แก้เป็น revision id ล่าสุดของโปรเจกต์
branch_labels = None
depends_on = None
 
 
def upgrade() -> None:
    op.add_column('users', sa.Column('avatar_url', sa.String(500), nullable=True))
 
 
def downgrade() -> None:
    op.drop_column('users', 'avatar_url')