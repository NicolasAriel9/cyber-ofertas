"""listing.updated_at, for the API's in-memory catalog

The browse endpoints scanned the whole listing table on every request; on
Supabase's free plan, once the day's I/O burst is spent, a scan takes minutes
(Oct 5 2026). The API now keeps a compact copy in memory and refreshes it
with the rows written since the last refresh, found through this column.
Existing rows stay NULL: they're read by the initial full load.

Revision ID: f3c9d1e7a2b4
Revises: e7b3a1d9c5f2
Create Date: 2026-10-06 00:10:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'f3c9d1e7a2b4'
down_revision: Union[str, None] = 'e7b3a1d9c5f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('listing', sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True))
    if op.get_bind().dialect.name == 'postgresql':
        # The scraper keeps writing while the index builds.
        with op.get_context().autocommit_block():
            op.create_index('ix_listing_updated_at', 'listing', ['updated_at'], postgresql_concurrently=True)
    else:
        op.create_index('ix_listing_updated_at', 'listing', ['updated_at'])


def downgrade() -> None:
    op.drop_index('ix_listing_updated_at', table_name='listing')
    op.drop_column('listing', 'updated_at')
