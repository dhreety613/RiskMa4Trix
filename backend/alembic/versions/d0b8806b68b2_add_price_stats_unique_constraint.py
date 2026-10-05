"""add price_stats unique constraint

Revision ID: d0b8806b68b2
Revises: 6248751bc321
Create Date: 2026-10-03 19:22:17.357567

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd0b8806b68b2'
down_revision: Union[str, None] = '6248751bc321'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Autogenerate also proposed dropping the two HNSW indexes from
    # migration 001 - it doesn't know about them since they're raw SQL,
    # not declared Index objects. Left out deliberately; only the real
    # schema change (idempotent upsert key for price_stats) is here.
    op.create_unique_constraint('uq_price_stat_company_asof', 'price_stats', ['company_id', 'as_of'])


def downgrade() -> None:
    op.drop_constraint('uq_price_stat_company_asof', 'price_stats', type_='unique')
