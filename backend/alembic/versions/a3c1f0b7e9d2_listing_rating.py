"""listing rating

Revision ID: a3c1f0b7e9d2
Revises: d5f85a89cda8
Create Date: 2026-10-03 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3c1f0b7e9d2'
down_revision: Union[str, None] = 'd5f85a89cda8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('listing', sa.Column('rating', sa.Float(), nullable=True))
    op.add_column('listing', sa.Column('review_count', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('listing', 'review_count')
    op.drop_column('listing', 'rating')
