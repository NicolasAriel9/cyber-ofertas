"""listing.updated_at, for the API's in-memory catalog

The browse endpoints scanned the whole listing table on every request; on
Supabase's free plan, once the day's I/O burst is spent, a scan takes minutes
(Oct 5 2026). The API now keeps a compact copy in memory and refreshes it
with the rows written since the last refresh, found through this column.
Existing rows stay NULL: they're read by the initial full load.

Deploying it took several tries (Oct 6 2026):
- Supabase cancels statements after ~2 minutes, and building the index on
  the throttled disk took longer; CREATE INDEX CONCURRENTLY can't lift that
  limit through the transaction pooler. It now runs in one transaction with
  SET LOCAL statement_timeout = 0.
- The API being replaced kept full scans of listing running, each longer
  than 10 minutes, so the ALTER never got its lock. Long queries on listing
  are now cancelled first (they only read; the old API serves its cached
  copy), and the lock is retried.

Revision ID: f3c9d1e7a2b4
Revises: e7b3a1d9c5f2
Create Date: 2026-10-06 00:10:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.exc import DBAPIError, OperationalError


# revision identifiers, used by Alembic.
revision: str = 'f3c9d1e7a2b4'
down_revision: Union[str, None] = 'e7b3a1d9c5f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ATTEMPTS = 10

CANCEL_LONG_QUERIES_ON_LISTING = sa.text("""
    SELECT pg_cancel_backend(pid) FROM pg_stat_activity
    WHERE datname = current_database() AND pid <> pg_backend_pid()
      AND usename = current_user
      AND state = 'active' AND query ILIKE '%listing%'
      AND now() - query_start > interval '15 seconds'
""")

# A session that opened a transaction and went quiet holds its locks until it
# ends: a stuck client of ours (one sat there for minutes on Oct 6 2026).
END_STUCK_TRANSACTIONS = sa.text("""
    SELECT pg_terminate_backend(pid) FROM pg_stat_activity
    WHERE datname = current_database() AND pid <> pg_backend_pid()
      AND usename = current_user
      AND state = 'idle in transaction' AND now() - state_change > interval '1 minute'
""")


def _with_lock(statement: str) -> None:
    """Runs a statement that needs a lock on listing, cancelling the long
    queries holding it and retrying. A savepoint keeps the transaction usable
    after a lock timeout."""
    bind = op.get_bind()
    for attempt in range(1, ATTEMPTS + 1):
        # Only our own role's queries (the API and the scraper): Supabase's
        # monitoring runs as a superuser, which can't be cancelled (the first
        # try failed on it). Cancelling is best effort.
        for clear in (CANCEL_LONG_QUERIES_ON_LISTING, END_STUCK_TRANSACTIONS):
            bind.execute(sa.text("SAVEPOINT clear_way"))
            try:
                bind.execute(clear)
            except DBAPIError:
                bind.execute(sa.text("ROLLBACK TO SAVEPOINT clear_way"))
            else:
                bind.execute(sa.text("RELEASE SAVEPOINT clear_way"))
        bind.execute(sa.text("SAVEPOINT take_lock"))
        try:
            bind.execute(sa.text(statement))
        except OperationalError:
            bind.execute(sa.text("ROLLBACK TO SAVEPOINT take_lock"))
            if attempt == ATTEMPTS:
                raise
            continue
        bind.execute(sa.text("RELEASE SAVEPOINT take_lock"))
        return


def upgrade() -> None:
    if op.get_bind().dialect.name != 'postgresql':
        op.add_column('listing', sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True))
        op.create_index('ix_listing_updated_at', 'listing', ['updated_at'])
        return
    # SET LOCAL lasts until this transaction ends, on the server session the
    # pooler gave it. While a statement waits for its lock, new queries on
    # listing queue behind it, so the wait is kept short and retried.
    op.execute("SET LOCAL statement_timeout = 0")
    op.execute("SET LOCAL lock_timeout = '1min'")
    _with_lock("ALTER TABLE listing ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE")
    # A failed CONCURRENTLY build leaves an invalid index behind.
    _with_lock("DROP INDEX IF EXISTS ix_listing_updated_at")
    # Blocks the scraper's writes (not reads) while it builds.
    _with_lock("CREATE INDEX ix_listing_updated_at ON listing (updated_at)")


def downgrade() -> None:
    op.drop_index('ix_listing_updated_at', table_name='listing')
    op.drop_column('listing', 'updated_at')
