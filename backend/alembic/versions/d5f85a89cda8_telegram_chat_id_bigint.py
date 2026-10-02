"""telegram chat id bigint

Revision ID: d5f85a89cda8
Revises: e252f6926190
Create Date: 2026-10-02 01:54:59.168659

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd5f85a89cda8'
down_revision: Union[str, None] = 'e252f6926190'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Telegram chat ids exceed 32-bit INTEGER. batch_alter_table so SQLite
    # (which can't ALTER a column type) recreates the table instead.
    with op.batch_alter_table("subscriber") as batch:
        batch.alter_column("telegram_chat_id", existing_type=sa.Integer(), type_=sa.BigInteger())


def downgrade() -> None:
    with op.batch_alter_table("subscriber") as batch:
        batch.alter_column("telegram_chat_id", existing_type=sa.BigInteger(), type_=sa.Integer())
