"""listing_change table, for the API's in-memory catalog

The browse endpoints scanned the whole listing table on every request; on
Supabase's free plan, once the day's I/O burst is spent, a scan takes minutes
(Oct 5 2026). The API now keeps a compact copy in memory and refreshes it
with the listings written since its last refresh, which the app records in
this table (see ListingChange in app/models.py).

This revision first added a listing.updated_at column instead, and never got
deployed: the ALTER needs an exclusive lock on listing, and an autovacuum
ANALYZE of listing ran for hours on the throttled disk without yielding it
(Oct 6 2026). Creating a separate table, with no foreign key to listing,
takes no lock on listing at all.

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
    op.create_table(
        'listing_change',
        sa.Column('listing_id', sa.Integer(), autoincrement=False, nullable=False),
        sa.Column('changed_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('listing_id'),
    )
    op.create_index('ix_listing_change_changed_at', 'listing_change', ['changed_at'])


def downgrade() -> None:
    op.drop_index('ix_listing_change_changed_at', table_name='listing_change')
    op.drop_table('listing_change')
