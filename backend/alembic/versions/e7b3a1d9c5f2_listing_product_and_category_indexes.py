"""index listing.product_id and product.category_id

Every page joins listing to product and filters products by category; the
product page and favorites look listings up by product. Without these indexes
each of those read all ~230k listings during the Cyber.

Revision ID: e7b3a1d9c5f2
Revises: c4a8f2e6b1d3
Create Date: 2026-10-05 23:30:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'e7b3a1d9c5f2'
down_revision: Union[str, None] = 'c4a8f2e6b1d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index('ix_listing_product_id', 'listing', ['product_id'])
    op.create_index('ix_product_category_id', 'product', ['category_id'])


def downgrade() -> None:
    op.drop_index('ix_product_category_id', table_name='product')
    op.drop_index('ix_listing_product_id', table_name='listing')
