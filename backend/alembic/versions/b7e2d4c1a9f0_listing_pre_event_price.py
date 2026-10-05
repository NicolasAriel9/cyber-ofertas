"""listing pre_event_price

Revision ID: b7e2d4c1a9f0
Revises: a3c1f0b7e9d2
Create Date: 2026-10-04 22:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7e2d4c1a9f0'
down_revision: Union[str, None] = 'a3c1f0b7e9d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('listing', sa.Column('pre_event_price', sa.Numeric(precision=12, scale=2), nullable=True))


def downgrade() -> None:
    op.drop_column('listing', 'pre_event_price')
