"""backfill pre_event_price from price history

Cyber prices showed up the day before the event (Oct 4 2026), so each
offer's reference price is its last recorded price before midnight Oct 4 in
Chile (event_windows.event_start), read from price_snapshot. Overwrites any
value captured at the old cutoff (Oct 5), which was already a Cyber price.

Revision ID: c4a8f2e6b1d3
Revises: b7e2d4c1a9f0
Create Date: 2026-10-04 23:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4a8f2e6b1d3'
down_revision: Union[str, None] = 'b7e2d4c1a9f0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Midnight Oct 4 in Chile (UTC-3).
CUTOFF_UTC = "2026-10-04 03:00:00"


def upgrade() -> None:
    # Also speeds up the price history endpoint, which filters by listing.
    op.create_index('ix_price_snapshot_listing_scraped', 'price_snapshot', ['listing_id', 'scraped_at'])
    cutoff = f"'{CUTOFF_UTC}+00'::timestamptz" if op.get_bind().dialect.name == "postgresql" else f"'{CUTOFF_UTC}'"
    op.execute(
        f"""
        UPDATE listing SET pre_event_price = (
            SELECT ps.price FROM price_snapshot ps
            WHERE ps.listing_id = listing.id AND ps.scraped_at < {cutoff}
            ORDER BY ps.scraped_at DESC, ps.id DESC
            LIMIT 1
        )
        """
    )


def downgrade() -> None:
    op.drop_index('ix_price_snapshot_listing_scraped', table_name='price_snapshot')
