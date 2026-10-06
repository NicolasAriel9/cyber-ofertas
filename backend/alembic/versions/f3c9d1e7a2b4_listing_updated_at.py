"""listing.updated_at, for the API's in-memory catalog

The browse endpoints scanned the whole listing table on every request; on
Supabase's free plan, once the day's I/O burst is spent, a scan takes minutes
(Oct 5 2026). The API now keeps a compact copy in memory and refreshes it
with the rows written since the last refresh, found through this column.
Existing rows stay NULL: they're read by the initial full load.

On Postgres it runs as one transaction that can be retried: the first deploy
failed halfway (Supabase cancels statements after ~2 minutes, and building the
index on the throttled disk took longer; CREATE INDEX CONCURRENTLY can't lift
that limit through the transaction pooler, where every statement may land on
a different server session).

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
    if op.get_bind().dialect.name != 'postgresql':
        op.add_column('listing', sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True))
        op.create_index('ix_listing_updated_at', 'listing', ['updated_at'])
        return
    # SET LOCAL lasts until this transaction ends, on the server session the
    # pooler gave it. The lock wait is capped so that, behind a long scraper
    # transaction, every other query on listing doesn't queue up behind us:
    # better to fail and retry the deploy.
    op.execute("SET LOCAL statement_timeout = 0")
    op.execute("SET LOCAL lock_timeout = '30s'")
    op.execute("ALTER TABLE listing ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE")
    # A failed CONCURRENTLY build leaves an invalid index behind.
    op.execute("DROP INDEX IF EXISTS ix_listing_updated_at")
    # Blocks the scraper's writes (not reads) while it builds.
    op.execute("CREATE INDEX ix_listing_updated_at ON listing (updated_at)")


def downgrade() -> None:
    op.drop_index('ix_listing_updated_at', table_name='listing')
    op.drop_column('listing', 'updated_at')
